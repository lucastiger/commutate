"""O007 cross-check preview (T0204): cost of the in-house L2 at levels 1-3 of its frozen rule and predicted F5 GCI on the
two development layouts.  A diagnostic, not evidence (no ExperimentRun).

Modes
-----
``--dry-run --out research/o007_l2/preview.json`` (local; no level-3 solve)
    Cell counts at levels 0-3 (``thermal_layout.build_layout_grid``; level 3 built in a child process when it fits the
    local budget, else counted exactly as ``8**3`` x the level-0 count, which the frozen rule implies because every
    level bisects every cell in x, y and z and region edges are grid lines; the identity is checked at levels 1-2),
    memory estimates at E006's ``fv_bytes_per_cell``, one measured level-1 solve per layout (wall time, peak RSS, and a
    reproduction check against E006's ``f_lv1``), and per die the levels 0-2 A4 quantities from E006's dev rows plus a
    predicted levels 1-3 GCI under stated assumptions with a sensitivity table.
``--full --out research/o007_l2/full.json`` (founder-run burst VM)
    Levels 1, 2, 3 at O003's operating point (E006 config: 65 degC coolant, h = 5000 W/(m2 K), k(T)) with E006's
    per-layout equal power per die (a PROXY: E009 calibrates power on its scikit-fem level 0).  Every solve runs in its
    own child process (clean peak RSS, memory returned to the OS), after a preflight that refuses a solve above
    ``memory_fraction`` x physical memory (as ``e006_run.preflight``), and is checkpointed under
    ``<out dir>/full_ckpt/`` so an interrupted run resumes.

Only the two dev layouts (dev seed 20261101) and only their E006 rows are used; E006's fresh layouts are O006's held-out
data and are never read here (the row filter is an explicit allow-list).  Never reads data/holdout/.
GCI: ``mfos.metrics.gci_capped`` (O006 A4, D0012/D0013; Roache 1998 ch. 5 for the safety factors), floor 1e-3 K.
"""
from __future__ import annotations

import argparse
import gc
import json
import math
import os
import platform
import re
import resource
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import yaml
from mfos import metrics as MX

from moduleforge.generate.halfbridge import generate_layouts
from moduleforge.solvers import thermal_layout as TL

ROOT = Path(__file__).resolve().parents[2]
E006_SPEC = ROOT / "experiments" / "specs" / "E006.yaml"
E006_RUN = ROOT / "experiments" / "results" / "E006" / "E006-20261102T145940-2815"
DEV_NAMES = ("side_by_side_6", "u_shaped_2")  # allow-list: E006's fresh layouts are O006's held-out data
DEV_SEED = 20261101
LEVELS = (1, 2, 3)
F5_MAX_K = 0.25
FLOOR_K = 1.0e-3
LOCAL_BUDGET_GB = 5.0  # agent memory rule on the 16 GB Mac (one process may use more only with a pressure check)
TWO_LAMBDA = 1.66  # 2*lambda of the attach/copper corner as stated in thermal_layout's docstring ("lambda about 0.83")
GCP_HIGHMEM_GB = (32, 64, 128, 256, 512)  # n2-highmem-{4,8,16,32,64}: 8 GB per vCPU
USABLE_FRACTION = 0.95  # assumed fraction of nominal VM RAM that the guest OS reports as physical memory


# ------------------------------------------------------------------------------------------------ helpers
def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", file=sys.stderr, flush=True)


def peak_rss_gb() -> float:
    r = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return r / 1e9 if sys.platform == "darwin" else r * 1024 / 1e9


def physical_gb() -> float:
    return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 1e9


def load_cfg() -> dict:
    cfg = yaml.safe_load(E006_SPEC.read_text())["config"]
    assert cfg["dev_seed"] == DEV_SEED, cfg["dev_seed"]
    assert [d[0] for d in cfg["dev_layouts"]] == list(DEV_NAMES), cfg["dev_layouts"]
    return cfg


def dev_layouts(cfg: dict) -> dict:
    out = {}
    for name, fam, dps in cfg["dev_layouts"]:
        lay = generate_layouts(1, DEV_SEED, family=fam, dies_per_switch=dps)[0]
        fp = lay.fingerprint()
        assert fp == cfg["dev_fingerprints"][name], f"{name}: fingerprint {fp} != E006 {cfg['dev_fingerprints'][name]}"
        out[name] = lay
    return out


def e006_dev_rows() -> dict:
    """E006 crosscheck rows of the two dev layouts only, per layout sorted by die."""
    rows = json.loads((E006_RUN / "rows.json").read_text())["rows"]
    out = {n: sorted((r for r in rows if r.get("kind") == "crosscheck" and r.get("layout") == n),
                     key=lambda r: r["die"]) for n in DEV_NAMES}
    for n, rs in out.items():
        assert rs and len({r["power_w"] for r in rs}) == 1 and [r["die"] for r in rs] == list(range(len(rs))), n
    return out


def e006_dev_solve_stats() -> dict:
    """E006's recorded L2 solve stats (cells, wall s; E006's burst VM) of the dev layouts only, from result.json, where
    they sit as JSON objects inside a string field (matched by an explicit allow-list of dev tags)."""
    raw = (E006_RUN / "result.json").read_text().replace('\\"', '"')
    found: dict = {}
    for name in DEV_NAMES:
        for lv in ("0", "1", "2"):
            m = re.search(r'\{"tag": "' + re.escape(f"{name}/L{lv}") + r'"[^{}]*\}', raw)
            if m:
                o = json.loads(m.group(0))
                found.setdefault(name, {})[lv] = {"n_cells": int(o["n_cells"]), "wall_s": float(o["wall_s"])}
    return found


def a4(f0: float, f1: float, f2: float) -> dict:
    """A4 estimator (mfos.metrics.gci_capped, floor 1e-3 K) with branch, p_obs and steps; asserts equality with
    thermal_layout.gci_three_grid (the solver's own copy of the rule)."""
    g = MX.gci_capped(f0, f1, f2, FLOOR_K)
    t = TL.gci_three_grid(f0, f1, f2, floor=FLOOR_K)
    assert (g == t["gci"]) or (math.isinf(g) and math.isinf(t["gci"])), (g, t)
    p = t["p_obs"]
    return {"gci_K": g, "branch": t["branch"], "p_obs": None if (p is None or not math.isfinite(p)) else p,
            "d1_K": f1 - f0, "d2_K": f2 - f1, "direction": "from_above" if f2 < f1 else "from_below"}


def two_term_extrapolate(f: list[float], p1: float, p2: float) -> float:
    """f_l = f* + a h**p1 + b h**p2 at h = 1, 1/2, 1/4 (levels 0-2), solved exactly; returns f at h = 1/8 (level 3)."""
    h = np.array([1.0, 0.5, 0.25])
    A = np.column_stack([np.ones(3), h**p1, h**p2])
    fs, a, b = np.linalg.solve(A, np.asarray(f, float))
    return float(fs + a * 0.125**p1 + b * 0.125**p2)


def break_even_ratio(f1: float, f2: float) -> float | None:
    """Largest same-sign step ratio rho' = d3/d2 in [0, 1) with gci_capped(f1, f2, f2 + rho' d2) <= F5_MAX_K.
    gci is non-decreasing in rho' on [0, 1) (metrics docstring: continuous in rho, form 1.25|d2|/(2^p-1)); bisection.
    None if even rho' = 0.25 (order 2) fails."""
    d2 = f2 - f1

    def g(rho):
        return MX.gci_capped(f1, f2, f2 + rho * d2, FLOOR_K)

    if g(0.25) > F5_MAX_K:
        return None
    lo, hi = 0.25, 1.0 - 1e-12
    if g(hi) <= F5_MAX_K:
        return hi
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        lo, hi = (mid, hi) if g(mid) <= F5_MAX_K else (lo, mid)
    return lo


def predict_die(f: list[float]) -> dict:
    """Predicted levels 1-3 GCI from E006's levels 0-2 values f = [f0, f1, f2] under several assumptions about the next
    step d3 = f3 - f2.  Primary assumption: the observed step ratio rho = d2/d1 (i.e. p_obs) holds for one more level."""
    f0, f1, f2 = f
    d1, d2 = f1 - f0, f2 - f1
    rho = d2 / d1 if d1 != 0 else math.nan

    def g13(f3):
        return MX.gci_capped(f1, f2, f3, FLOOR_K)

    sign = 1.0 if d2 >= 0 else -1.0
    sc = {
        "ratio_held": g13(f2 + rho * d2) if math.isfinite(rho) else math.inf,
        "order_2_rho_0.25": g13(f2 + 0.25 * d2),
        "order_1_rho_0.5": g13(f2 + 0.5 * d2),
        "two_term_p1_p2": g13(two_term_extrapolate(f, 1.0, 2.0)),
        "two_term_p1.66_p2": g13(two_term_extrapolate(f, TWO_LAMBDA, 2.0)),
        "stagnant_d3_below_floor": g13(f2 + 0.5 * FLOOR_K * sign),
        "sign_flip_d3": g13(f2 - sign * max(2.0 * FLOOR_K, 0.1 * abs(d2))),
    }
    rb = break_even_ratio(f1, f2)
    return {"rho_02": rho, "pred_gci_13_K": sc["ratio_held"], "scenarios_gci_13_K": sc,
            "break_even_rho": rb, "break_even_p": (math.log2(1.0 / rb) if rb and rb > 0 else None),
            "pred_f5_margin_K": F5_MAX_K - sc["ratio_held"],
            "worst_same_sign_scenario_K": max(v for k, v in sc.items() if k != "sign_flip_d3"),
            "sign_flip_fails_f5": sc["sign_flip_d3"] > F5_MAX_K}


def recommend_ram(max_est_gb: float, fraction: float) -> tuple[float, float]:
    need = max_est_gb / fraction
    for gb in GCP_HIGHMEM_GB:
        if USABLE_FRACTION * gb >= need:
            return float(gb), need
    return math.inf, need


# ------------------------------------------------------------------------------------------------ child processes
def child(task: dict) -> dict:
    """Runs in a fresh process: 'count' (build a grid, count cells) or 'solve' (one L2 level)."""
    cfg = load_cfg()
    lay = dev_layouts(cfg)[task["layout"]]
    lv = int(task["level"])
    t0 = time.perf_counter()
    rss0 = peak_rss_gb()
    g = TL.build_layout_grid(lay, lv)
    active, total = int((g.cell_material >= 0).sum()), int(g.cell_material.size)
    lines = [len(g.x), len(g.y), len(g.z)]
    del g
    gc.collect()
    out = {"layout": task["layout"], "level": lv, "active_cells": active, "total_cells": total, "lines_xyz": lines,
           "build_s": time.perf_counter() - t0, "rss_before_build_gb": rss0, "peak_rss_after_build_gb": peak_rss_gb()}
    if task["kind"] == "count":
        return out
    est = active * cfg["fv_bytes_per_cell"] / 1e9
    cap = float(task["cap_gb"])
    if est > cap:  # same rule as e006_run.preflight, re-checked on the actual grid
        raise MemoryError(f"{task['layout']} L{lv}: {active} cells, est {est:.1f} GB > cap {cap:.1f} GB")
    t1 = time.perf_counter()
    r = TL.solve_layout_level(lay, level=lv, power_W=float(task["power_W"]), h=cfg["h_W_m2K"], T_c=cfg["coolant_K"])
    m = r["result"].meta
    n = len(lay.dies)
    out.update({"power_W_per_die": float(task["power_W"]), "n_cells": int(m["n_cells"]),
                "solve_wall_s": time.perf_counter() - t1, "solver_wall_time_s": float(m["wall_time_s"]),
                "peak_rss_gb": peak_rss_gb(), "energy_balance": float(m["energy_balance"]),
                "picard_residual_K": float(m.get("picard_dT", math.nan)), "picard_iters": int(m["picard_iters"]),
                "linear_residual": float(m["linear_residual"]),
                "tj_max_K": [float(r["values"][f"die{i}.tj_max"]) for i in range(n)]})
    return out


def run_child(task: dict, timeout_s: float | None = None) -> dict:
    p = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--_child", json.dumps(task)],
                       capture_output=True, text=True, timeout=timeout_s, cwd=ROOT)
    if p.returncode != 0:
        raise RuntimeError(f"child {task} failed ({p.returncode}): {p.stderr[-2000:]}")
    return json.loads(p.stdout.strip().splitlines()[-1])


# ------------------------------------------------------------------------------------------------ dry run
def dry_run(out_path: Path) -> int:
    cfg = load_cfg()
    lays = dev_layouts(cfg)
    rows = e006_dev_rows()
    e006_stats = e006_dev_solve_stats()
    bpc, frac = float(cfg["fv_bytes_per_cell"]), float(cfg["memory_fraction"])
    phys = physical_gb()
    local_cap = min(LOCAL_BUDGET_GB, frac * phys)
    res: dict = {"layouts": {}}
    detail: dict = {}
    for name, lay in lays.items():
        log(f"{name}: {len(lay.dies)} dies, fingerprint ok")
        counts = {}
        for lv in (0, 1, 2):
            counts[lv] = run_child({"kind": "count", "layout": name, "level": lv})
            log(f"  L{lv}: {counts[lv]['active_cells']} active cells, peak RSS {counts[lv]['peak_rss_after_build_gb']:.2f} GB")
        a0, t0 = counts[0]["active_cells"], counts[0]["total_cells"]
        bisect_ok = all(counts[lv]["active_cells"] == a0 * 8**lv and counts[lv]["total_cells"] == t0 * 8**lv
                        for lv in (1, 2))
        base = counts[2]["rss_before_build_gb"]  # measure small, extrapolate: level-3 build ~ 8 x the level-2 build
        build3_est_gb = base + 1.5 * 8.0 * max(counts[2]["peak_rss_after_build_gb"] - base, 0.0)
        if build3_est_gb <= local_cap:
            counts[3] = run_child({"kind": "count", "layout": name, "level": 3})
            c3_method = "build_layout_grid (child process)"
        else:
            counts[3] = {"active_cells": a0 * 8**3, "total_cells": t0 * 8**3}
            c3_method = "8**3 x level-0 count (exact under the rule's bisection; verified at levels 1-2)"
        assert counts[3]["active_cells"] == a0 * 8**3, (name, counts[3]["active_cells"], a0 * 8**3)
        cells = {str(lv): int(counts[lv]["active_cells"]) for lv in (1, 2, 3)}
        mem = {str(lv): cells[str(lv)] * bpc / 1e9 for lv in (1, 2, 3)}
        # measured level-1 solve at E006's power (if it fits the local budget)
        P = float(rows[name][0]["power_w"])
        l1 = None
        if mem["1"] <= local_cap:
            l1 = run_child({"kind": "solve", "layout": name, "level": 1, "power_W": P, "cap_gb": local_cap})
            f1_e006 = [r["f_lv1"] for r in rows[name]]
            l1["max_abs_diff_vs_e006_f_lv1_K"] = float(np.max(np.abs(np.subtract(l1["tj_max_K"], f1_e006))))
            l1["measured_bytes_per_cell"] = (l1["peak_rss_gb"] - l1["peak_rss_after_build_gb"]) * 1e9 / l1["n_cells"]
            log(f"  L1 solve: {l1['solve_wall_s']:.1f} s, peak RSS {l1['peak_rss_gb']:.2f} GB, "
                f"|dTj vs E006| {l1['max_abs_diff_vs_e006_f_lv1_K']:.2e} K")
        dies = []
        for r in rows[name]:
            f = [float(r["f_lv0"]), float(r["f_lv1"]), float(r["f_lv2"])]
            e = a4(*f)
            pr = predict_die(f)
            assert abs(e["gci_K"] - float(r["gci"])) <= 1e-12 * max(1.0, abs(e["gci_K"])), (name, r["die"])
            dies.append({"die": int(r["die"]), "e006_f_lv0_2": f, "d1_K": e["d1_K"], "d2_K": e["d2_K"],
                         "p_obs": e["p_obs"], "branch": e["branch"], "direction_02": e["direction"],
                         "gci_02_K": e["gci_K"], **pr})
        # wall-time extrapolation for level 3 from E006's recorded dev-layout solves (levels 0-2)
        st = e006_stats.get(name, {})
        wall3 = None
        if all(k in st for k in ("0", "1", "2")):
            g1, g2 = st["1"]["wall_s"] / st["0"]["wall_s"], st["2"]["wall_s"] / st["1"]["wall_s"]
            wall3 = {"e006_wall_s_lv0_2": [st[k]["wall_s"] for k in ("0", "1", "2")],
                     "growth_lv01_lv12": [g1, g2], "est_wall_s_lv3_same_growth": st["2"]["wall_s"] * g2,
                     "est_wall_s_lv3_growth_x1.5": st["2"]["wall_s"] * g2 * 1.5,
                     "e006_cells_match": all(st[k]["n_cells"] == a0 * 8 ** int(k) for k in ("0", "1", "2"))}
        # power-rescale sensitivity: E009 calibrates on scikit-fem level 0 (E006's skfem_lv0 at E006's power is a proxy
        # for E009's rule); GCI taken as proportional to power (linear conduction; k(T) makes it slightly nonlinear)
        rise_fe0 = max(float(r["skfem_lv0"]) for r in rows[name]) - float(cfg["coolant_K"])
        p_scale = float(cfg["target_rise_K"]) / rise_fe0
        for d in dies:
            d["pred_gci_13_K_power_rescaled"] = d["pred_gci_13_K"] * p_scale
        res["layouts"][name] = {"cells": cells, "mem_gb_est": mem, "dies": dies}
        detail[name] = {"power_scale_e009_proxy": p_scale, "e006_skfem_lv0_hottest_rise_K": rise_fe0,
                        "n_dies": len(lay.dies), "fingerprint": lay.fingerprint(), "e006_power_W_per_die": P,
                        "cells_lv0": a0, "total_cells_incl_void": {str(k): int(v["total_cells"]) for k, v in counts.items()},
                        "level3_count_method": c3_method, "bisection_identity_lv1_lv2": bisect_ok,
                        "grid_builds": {str(k): v for k, v in counts.items() if "build_s" in v},
                        "level1_solve": l1, "level3_wall_estimate": wall3,
                        "max_pred_gci_13_K": max(d["pred_gci_13_K"] for d in dies),
                        "min_pred_f5_margin_K": min(d["pred_f5_margin_K"] for d in dies),
                        "n_dies_fail_if_sign_flip": sum(d["sign_flip_fails_f5"] for d in dies)}
    max_est = max(v["mem_gb_est"]["3"] for v in res["layouts"].values())
    rates = [d["level1_solve"]["measured_bytes_per_cell"] for d in detail.values() if d["level1_solve"]]
    rate = max([bpc, *rates])  # the larger of E006's planning rate and the locally measured level-1 rate
    max_meas = max(v["cells"]["3"] for v in res["layouts"].values()) * rate / 1e9
    ram, need = recommend_ram(max(max_est, max_meas), frac)
    res["memory_model"] = {"fv_bytes_per_cell_e006": bpc, "measured_level1_bytes_per_cell": rates,
                           "rate_used_for_ram": rate, "max_lv3_est_gb_e006_rate": max_est,
                           "max_lv3_est_gb_rate_used": max_meas, "physical_gb_needed": need,
                           "preflight_physical_gb_needed": max_est / frac}
    res["recommended_vm_ram_gb"] = ram
    res["assumptions"] = [
        "Primary prediction (pred_gci_13_K): the levels 0-2 step ratio rho = d2/d1 of E006 holds for one more level, "
        "d3 = rho d2; GCI_13 = gci_capped(f_lv1, f_lv2, f_lv2 + rho d2, floor 1e-3 K). Under this assumption GCI_13 = "
        "rho x GCI_02 in the monotone and fast branches.",
        "E009's L2 levels 1-2 reproduce E006's f_lv1, f_lv2 up to a power rescale: same frozen rule and code "
        "(git diff of solvers/thermal_layout.py, thermal_fv.py, geometry, generate since E006's commit is empty; "
        "level-1 reproduction checked locally); E009's power is calibrated on scikit-fem level 0, not on L2 level 0, so "
        "GCI is expected to scale roughly with power (sensitivity: see power_scale in the note).",
        f"Memory: active cells x fv_bytes_per_cell = {bpc:.0f} B/cell (E006 config); preflight refuses a solve above "
        f"{frac} x physical memory (needs {max_est / frac:.1f} GB physical); RAM sized at the larger of that rate and the "
        f"locally measured level-1 rate ({rate:.0f} B/cell), physical memory taken as {USABLE_FRACTION} x nominal: "
        f"{need:.1f} GB physical -> smallest n2-highmem size {ram:.0f} GB.",
        "Sensitivity scenarios for d3: rho' = 0.25 (order 2), rho' = 0.5 (order 1), two-term fits f* + a h^p1 + b h^2 "
        f"with p1 = 1 and p1 = {TWO_LAMBDA} (2 lambda from thermal_layout's docstring), |d3| below the 1e-3 K floor, and "
        "a sign flip of d3 (oscillatory branch, 3 max(|d2|, |d3|)); break_even_rho is the largest same-sign ratio d3/d2 "
        "that still meets F5 (0.25 K).",
        "Only E006's dev-layout rows (side_by_side_6, u_shaped_2) are used; fresh (held-out) rows are filtered out by an "
        "explicit allow-list. Diagnostic, not evidence.",
    ]
    res["detail"] = detail
    res["environment"] = {"physical_memory_gb": phys, "local_cap_gb": local_cap, "python": sys.version.split()[0],
                          "platform": platform.platform(), "e006_run": E006_RUN.name}
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(res, indent=1, allow_nan=True) + "\n")
    log(f"wrote {out_path}; recommended VM RAM {ram:.0f} GB (level-3 est {max_est:.1f} GB)")
    return 0


# ------------------------------------------------------------------------------------------------ full
def full(out_path: Path, levels: tuple[int, ...], mem_cap_gb: float | None) -> int:
    cfg = load_cfg()
    lays = dev_layouts(cfg)
    rows = e006_dev_rows()
    bpc, frac = float(cfg["fv_bytes_per_cell"]), float(cfg["memory_fraction"])
    phys = physical_gb()
    cap = frac * phys if mem_cap_gb is None else min(mem_cap_gb, frac * phys)
    ck = out_path.parent / "full_ckpt"
    ck.mkdir(parents=True, exist_ok=True)
    res: dict = {"mode": "full", "levels": list(levels), "operating_point": {
        "coolant_K": cfg["coolant_K"], "h_W_m2K": cfg["h_W_m2K"], "k_of_T": True,
        "power": "PROXY: E006's per-layout equal power per die (calibrated on L2 level 0 to a 60 K hottest rise); "
                 "E009 calibrates on scikit-fem level 0"},
        "memory": {"physical_gb": phys, "cap_gb": cap, "fv_bytes_per_cell": bpc, "memory_fraction": frac},
        "layouts": {}, "refused": []}
    status = 0
    for name, lay in lays.items():
        P = float(rows[name][0]["power_w"])
        a0 = run_child({"kind": "count", "layout": name, "level": 0})["active_cells"]
        solves = {}
        for lv in levels:
            est = a0 * 8**lv * bpc / 1e9
            if est > cap:  # e006_run.preflight: refuse, an error result, never a verdict
                msg = f"{name} L{lv}: ~{a0 * 8**lv / 1e6:.1f} M cells, est {est:.1f} GB > cap {cap:.1f} GB"
                log("REFUSED " + msg)
                res["refused"].append(msg)
                status = 3
                continue
            f = ck / f"{name}_L{lv}.json"
            if f.exists():
                s = json.loads(f.read_text())
                if s.get("power_W_per_die") == P and s.get("level") == lv:
                    solves[lv] = s
                    log(f"{name} L{lv}: resumed from {f.name}")
                    continue
            log(f"{name} L{lv}: solving ~{a0 * 8**lv / 1e6:.1f} M cells (est {est:.1f} GB)")
            s = run_child({"kind": "solve", "layout": name, "level": lv, "power_W": P, "cap_gb": cap})
            f.write_text(json.dumps(s, indent=1) + "\n")
            solves[lv] = s
            log(f"  {s['solve_wall_s']:.0f} s, peak RSS {s['peak_rss_gb']:.2f} GB, balance {s['energy_balance']:.1e}, "
                f"Picard {s['picard_residual_K']:.1e} K")
        dies = []
        e006 = {0: "f_lv0", 1: "f_lv1", 2: "f_lv2"}
        for i, r in enumerate(rows[name]):
            vals = [solves[lv]["tj_max_K"][i] if lv in solves else None for lv in levels]
            d = {"die": i, "levels": list(levels), "tj_max_K": vals,
                 "e006_same_level_diff_K": {str(lv): (solves[lv]["tj_max_K"][i] - r[e006[lv]])
                                            for lv in levels if lv in solves and lv in e006}}
            if all(v is not None for v in vals) and len(vals) == 3:
                e = a4(*vals)
                d.update({"gci_capped_K": e["gci_K"], "branch": e["branch"], "p_obs": e["p_obs"], "d1_K": e["d1_K"],
                          "d2_K": e["d2_K"], "direction": e["direction"], "f5_ok": e["gci_K"] <= F5_MAX_K})
            dies.append(d)
        per_solve = {str(lv): {k: s[k] for k in ("n_cells", "solve_wall_s", "solver_wall_time_s", "build_s", "peak_rss_gb",
                                                  "energy_balance", "picard_residual_K", "picard_iters",
                                                  "linear_residual")} for lv, s in solves.items()}
        res["layouts"][name] = {"fingerprint": lay.fingerprint(), "power_W_per_die_proxy": P, "solves": per_solve,
                                "dies": dies}
    g = [d["gci_capped_K"] for v in res["layouts"].values() for d in v["dies"] if "gci_capped_K" in d]
    res["summary"] = {"max_gci_K": max(g) if g else None, "f5_max_K": F5_MAX_K,
                      "f5_all_dies_ok": bool(g) and all(x <= F5_MAX_K for x in g) and not res["refused"],
                      "max_energy_balance": max((s["energy_balance"] for v in res["layouts"].values()
                                                 for s in v["solves"].values()), default=None),
                      "max_picard_residual_K": max((s["picard_residual_K"] for v in res["layouts"].values()
                                                    for s in v["solves"].values()), default=None)}
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(res, indent=1, allow_nan=True) + "\n")
    log(f"wrote {out_path}: {res['summary']}")
    return status


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    m = ap.add_mutually_exclusive_group(required=True)
    m.add_argument("--dry-run", action="store_true")
    m.add_argument("--full", action="store_true")
    m.add_argument("--_child", help=argparse.SUPPRESS)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--levels", type=int, nargs=3, default=list(LEVELS), help="full mode: three consecutive levels")
    ap.add_argument("--mem-cap-gb", type=float, default=None, help="full mode: lower the preflight cap (testing)")
    a = ap.parse_args(argv)
    if a._child:
        print(json.dumps(child(json.loads(a._child))))
        return 0
    if a.out is None:
        ap.error("--out is required")
    out = a.out if a.out.is_absolute() else ROOT / a.out
    if a.dry_run:
        return dry_run(out)
    lv = tuple(a.levels)
    if lv[1] != lv[0] + 1 or lv[2] != lv[0] + 2:
        ap.error("levels must be three consecutive integers")
    return full(out, lv, a.mem_cap_gb)


if __name__ == "__main__":
    sys.exit(main())
