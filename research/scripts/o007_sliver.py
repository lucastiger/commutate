"""O007 sliver discriminator (T0235, founder I0124 (c) step 1): LABELLED DIAGNOSTIC, not a candidate configuration.

Question: does T0228's CG-only miss (Case 1a 204/252/316, Case 1b 198/247/318 CG at L0/L1/L2 against the pre-registered
300) come from sliver cells next to near-coincident grid lines, or from the conditioning of the plates? Variants of
candidate 1 (``a_q1h4_graded``, research/o007_dev2/frozen_config.json, production GridRule with edge_grading):
  max_lines      candidate 1 as frozen; values copied from research/o007_dev2/{dev_study.json, plan.json}, not re-solved
  centroid_only  candidate 1 with the frozen-maximum extra_lines removed (built-in source centroid lines kept)
  sliver_free    only if pre-registered in research/notes/o007-sliver.md sec. 0 (see SLIVER_FREE below)
No temperature of any variant is compared with a reference, and none enters any criterion, freeze or spec. Research
only: moduleforge.solvers.thermal_fem is used unchanged. Pre-registration: note sec. 0, committed before any solve; its
hash is in research/o007_sliver/preregistration.json and copied to discriminator.json.

Reused by import (read-only): o007_dev_study2 (rule_of('a_q1h4_graded'), _lines_stats, bpd_max), o007_dev_study
(load_refs with the sha256 gate, box_problem, the cg_only CG counter, the watchdog, the memory gate of Runner,
min_cell_ratio, count_dofs, peak RSS), o007_probe (EST_MARGIN).

Modes
  --survey   grid only (no temperature): L0 sliver survey of every variant -> research/o007_sliver/survey.json
  --plan     grid only: DOF, min ratios per level, L2 memory / wall estimates and the burst command -> plan.json
  (default)  local L0 and L1 solves under T0228's memory rule (one child at a time, <= 5 GB, or <= 10 GB with
             memory_pressure >= 50 % free and swap < 4 GB; watchdog 10 GB RSS / 8 GB swap), then --report
  --full     every level (L2 included) under 0.85 x physical memory (founder burst), then --report:
             scripts/burst_gcp.sh --cmd "uv run python research/scripts/o007_sliver.py --full" research/o007_sliver
  --report   deterministic: the pre-registered verdict rule on the cache -> discriminator.json
  --worker   internal: one solve in a child process
SI units, kelvin, float64.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import threading
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "research" / "scripts")]

import o007_dev_study2 as D2  # noqa: E402  (T0228: rule_of, _lines_stats, bpd_max; binds DS to candidate 1)
import o007_probe as PR  # noqa: E402  (T0225: EST_MARGIN)

DS = D2.DS  # o007_dev_study (T0207), bound by D2._bind() to candidate 1
FEM = DS.FEM
OUT = ROOT / "research" / "o007_sliver"
CACHE = OUT / "cache"
PREREG = OUT / "preregistration.json"
NOTE = ROOT / "research" / "notes" / "o007-sliver.md"
DEV2 = ROOT / "research" / "o007_dev2"
CID = D2.CID  # "a_q1h4_graded"
CASES = ("case1a", "case1b")
SURVEY_EXTRA = ("case2",)  # survey only (T0228 data to explain: ratio 0.010 but CG 162)
LEVELS = (0, 1, 2)
RATIO_LIMIT = 0.1  # survey threshold on the neighbour lateral width ratio (packet)
CG_LIMIT = 300  # pre-registered CG headroom (T0207 sec. 0.2 criterion 2, carried into T0228 sec. 0)
BURST_COMMAND = 'scripts/burst_gcp.sh --cmd "uv run python research/scripts/o007_sliver.py --full" research/o007_sliver'
# Pre-registered (note sec. 0): which solved variants exist and which one decides each case.
VARIANTS_SOLVED: tuple[str, ...] = ("centroid_only",)
DECISIVE = {"case1a": "centroid_only", "case1b": "centroid_only"}


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


# ------------------------------------------------------------------------------------------------ problems and grids
def variant_problem(ser: dict, case: str, variant: str) -> dict:
    """T0207 box_problem with the variant's mandatory extra lines (geometry and physics unchanged)."""
    b = DS.box_problem(ser, case)
    if variant == "max_lines":
        return b
    if variant == "centroid_only":
        return {**b, "extra": None}  # built-in source centroid lines remain (box_stack_grid)
    raise ValueError(f"variant {variant!r} is not pre-registered")


def grid(ser: dict, case: str, variant: str, level: int):
    b = variant_problem(ser, case, variant)
    return FEM.box_stack_grid(b["a"], b["b"], b["layers"], b["h"], b["Tc"], b["srcs"], rule=D2.rule_of(CID),
                              level=level, extra_lines=b["extra"])


def _ratios(v: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    w = np.diff(v)
    return w, np.minimum(w[1:], w[:-1]) / np.maximum(w[1:], w[:-1])


def grid_stats(g) -> dict:
    wx, rx = _ratios(g.x)
    wy, ry = _ratios(g.y)
    return {"min_ratio_x": float(rx.min()), "min_ratio_y": float(ry.min()),
            "min_ratio_lateral": float(min(rx.min(), ry.min())), "min_cell_x_m": float(wx.min()),
            "min_cell_y_m": float(wy.min()), "dofs": int(DS.count_dofs(g)), "cells": [g.x.size - 1, g.y.size - 1,
                                                                                         g.z.size - 1]}


def _labels(v: float, axis: str, b: dict, g, tol: float = 1e-12) -> list[str]:
    """Every role of the level-0 line at ``v`` (a line can have several)."""
    i0, i1 = (0, 2) if axis == "x" else (1, 3)
    end = b["a"] if axis == "x" else b["b"]
    out = []
    if abs(v) <= tol or abs(v - end) <= tol:
        out.append("domain_end")
    out += [f"source_edge({n})" for n, s in zip(b["names"], b["srcs"], strict=True)
            if abs(v - s[i0]) <= tol or abs(v - s[i1]) <= tol]
    out += [f"source_centroid({n})" for n, s in zip(b["names"], b["srcs"], strict=True)
            if abs(v - 0.5 * (s[i0] + s[i1])) <= tol]
    ex = None if b["extra"] is None else b["extra"][0 if axis == "x" else 1]
    if ex is not None:
        mx = [r for r in b["rows"] if r["point"] == "max"]
        out += [f"frozen_max_line({r['source']})" for r, e in zip(mx, ex, strict=True) if abs(v - e) <= tol]
    out += ["grading_line" for e in g.grading[axis] if abs(v - e) <= tol]
    snapped = [s for s in g.snaps[axis] if abs(v - s[1]) <= tol]
    if snapped:
        out.append("snap_target(" + ", ".join(f"{s[0]:.6g}" for s in snapped) + ")")
    return out or ["subdivision"]


def survey_case(ser: dict, case: str, variant: str) -> dict:
    """L0 lateral intervals with a neighbour width ratio < RATIO_LIMIT; the bounding lines of the smaller interval."""
    b, g = variant_problem(ser, case, variant), grid(ser, case, variant, 0)
    rec = {"stats_l0": grid_stats(g), "slivers": [], "grading_lines": {k: len(v) for k, v in g.grading.items()},
           "snaps": {k: [list(s) for s in v] for k, v in g.snaps.items() if k != "z"}}
    for axis in ("x", "y"):
        v = getattr(g, axis)
        w, _ = _ratios(v)
        for i in range(w.size):
            nb = [w[j] for j in (i - 1, i + 1) if 0 <= j < w.size]
            r = min(w[i] / n for n in nb)
            if r < RATIO_LIMIT:
                rec["slivers"].append({"axis": axis, "interval_m": [float(v[i]), float(v[i + 1])],
                                       "width_m": float(w[i]), "neighbour_widths_m": [float(n) for n in nb],
                                       "ratio": float(r), "lo_line": _labels(float(v[i]), axis, b, g),
                                       "hi_line": _labels(float(v[i + 1]), axis, b, g)})
    return rec


def named_removal_check(ser: dict, case: str) -> dict:
    """Grid only. Would a sliver_free variant that removes the survey-named grading lines of centroid_only (the lines
    labelled 'grading_line' that bound an interval with ratio < RATIO_LIMIT) reach a minimum lateral ratio >= 0.1?
    The production _grading_lines is wrapped at run time in this process only (thermal_fem.py is not edited)."""
    named = {round(v, 12) for s in survey_case(ser, case, "centroid_only")["slivers"]
             for lab, v in ((s["lo_line"], s["interval_m"][0]), (s["hi_line"], s["interval_m"][1]))
             if "grading_line" in lab}
    orig = FEM._grading_lines

    def drop(*a, **k):
        return [v for v in orig(*a, **k) if round(v, 12) not in named]

    FEM._grading_lines = drop
    try:
        st = grid_stats(grid(ser, case, "centroid_only", 0))
    finally:
        FEM._grading_lines = orig
    return {"removed_lines_m": sorted(named), "min_ratio_lateral_after": st["min_ratio_lateral"],
            "reaches_0p1": st["min_ratio_lateral"] >= RATIO_LIMIT}


def survey() -> dict:
    ser, _, chk = DS.load_refs()
    out = {"task": "T0235", "candidate": CID, "ratio_limit": RATIO_LIMIT, "references": chk, "level": 0, "cases": {},
           "named_line_removal_check": {}}
    for case in CASES + SURVEY_EXTRA:
        out["cases"][case] = {v: survey_case(ser, case, v) for v in ("max_lines", "centroid_only")}
    for case in CASES:
        out["named_line_removal_check"][case] = named_removal_check(ser, case)
    return out


# ------------------------------------------------------------------------------------------------ worker (one solve)
def worker(spec_path: str) -> int:
    spec = json.loads(Path(spec_path).read_text())
    threading.Thread(target=DS._watchdog, args=(spec["hard_cap_gb"] * 1e9,), daemon=True).start()
    DS.install_cg_logger()
    cap: dict = {}
    orig = FEM._solve_grid

    def captured(*a, **k):
        r = orig(*a, **k)
        cap["r"] = r
        return r

    FEM._solve_grid = captured
    ser = json.loads(DS.SERIES_PATH.read_text())["payload"]  # sha256 checked by the parent (load_refs) before spawning
    b = variant_problem(ser, spec["case"], spec["variant"])
    base, t0 = DS.peak_rss_bytes(), time.perf_counter()
    out: dict = {"spec": spec}
    try:
        r = FEM.solve_box_stack(b["a"], b["b"], b["layers"], b["h"], b["Tc"], b["srcs"], rule=D2.rule_of(CID),
                                level=spec["level"], extra_lines=b["extra"])
        m = r.meta
        out.update(status="ok", dofs=int(r.dofs), energy_balance=float(r.energy_balance),
                   picard_iters=int(r.picard_iters), picard_residual_K=float(r.picard_residual), wall_s=float(r.wall_s),
                   meta_cg_iterations=[int(c) for c in m["cg_iterations"]], grid=D2._lines_stats(r),
                   n_lines=m["n_lines"], grading_lines=m["grading_lines"], snapped_lines=m["snapped_lines"])
    except RuntimeError as e:  # linear-solve failure (e.g. the CG cap): the count is still the measured CG_LOG
        g = grid(ser, spec["case"], spec["variant"], spec["level"])
        out.update(status="cg_failed", error=str(e), dofs=int(DS.count_dofs(g)), grid=grid_stats(g))
    out.update(cg=DS.CG_LOG, cg_max_iters=max((c["iters"] for c in DS.CG_LOG), default=0),
               cg_hit_cap=any(c["hit_cap"] for c in DS.CG_LOG),
               final_true_rel_resid=(DS.CG_LOG[-1]["true_rel"] if DS.CG_LOG else None),
               max_true_rel_resid=max((c["true_rel"] or 0.0 for c in DS.CG_LOG), default=0.0),
               base_rss_bytes=base, peak_rss_bytes=DS.peak_rss_bytes(), process_wall_s=time.perf_counter() - t0,
               platform=sys.platform)
    Path(spec["out"]).write_text(json.dumps(out))
    return 0


# ------------------------------------------------------------------------------------------------ orchestration
class Runner(DS.Runner):
    """T0207/T0228 memory gate (DS.Runner.gate) and bytes/DOF rule (D2.bpd_max) with this script as the child."""

    def __init__(self, ser: dict, full: bool):
        super().__init__(ser, {}, full)
        CACHE.mkdir(parents=True, exist_ok=True)

    def run(self, case: str, variant: str, lv: int) -> dict:
        key = f"{case}__{variant}__L{lv}"
        path = CACHE / f"{key}.json"
        if path.exists():
            d = json.loads(path.read_text())
            if d.get("status") in ("ok", "cg_failed") or not self.full:
                return d
        dofs = DS.count_dofs(grid(self.ser, case, variant, lv))
        est_gb = dofs * D2.bpd_max(1) * PR.EST_MARGIN / 1e9
        ok, why = self.gate(est_gb)
        if not ok:
            log(f"  SKIP {key}: {dofs} DOF, {why}")
            return {"status": "skipped_memory", "dofs": dofs, "est_gb": est_gb}
        hard = 0.9 * self.phys_gb if self.full else DS.LOCAL_HARD_GB
        spec = {"case": case, "variant": variant, "level": lv, "out": str(path), "hard_cap_gb": hard}
        sp = CACHE / f"{key}.spec.json"
        sp.write_text(json.dumps(spec))
        log(f"  solve {key}: {dofs} DOF, {why}")
        t0 = time.perf_counter()
        pr = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--worker", str(sp)], capture_output=True,
                            text=True, timeout=8 * 3600)
        if pr.returncode != 0 or not path.exists():
            st = {3: "killed_memory", 4: "killed_swap"}.get(pr.returncode, "failed")
            rec = {"status": st, "returncode": pr.returncode, "dofs": dofs, "wall_s": time.perf_counter() - t0,
                   "stderr_tail": (pr.stdout + pr.stderr)[-3000:], "spec": spec}
            path.write_text(json.dumps(rec))
            log(f"  {st.upper()} {key}: rc {pr.returncode}")
            return rec
        d = json.loads(path.read_text())
        log(f"  {d['status']} {key}: {d['dofs']} DOF, {d['process_wall_s']:.1f} s, peak "
            f"{d['peak_rss_bytes'] / 1e9:.2f} GB, CG max {d['cg_max_iters']}")
        return d


def study(full: bool) -> None:
    if not PREREG.exists():
        raise SystemExit("no pre-registration commit recorded (research/o007_sliver/preregistration.json): no solve")
    ser, _, _ = DS.load_refs()
    run = Runner(ser, full)
    for lv in LEVELS:  # level-major: every L0 and L1 before any L2
        for case in CASES:
            for var in VARIANTS_SOLVED:
                run.run(case, var, lv)


# ------------------------------------------------------------------------------------------------ plan and report
def _dev2() -> tuple[dict, dict]:
    return (json.loads((DEV2 / "dev_study.json").read_text())["chosen"]["cases"],
            json.loads((DEV2 / "plan.json").read_text()))


def plan() -> dict:
    ser, _, _ = DS.load_refs()
    ds, p2 = _dev2()
    rows = []
    for case in CASES:
        c = ds[case]  # measured L2 of the same plate under max_lines (T0228 burst, e2-highmem-8)
        bpd_l2, s_per_dof = c["peak_rss_GB"][2] * 1e9 / c["dofs"][2], c["wall_s"][2] / c["dofs"][2]
        for var in VARIANTS_SOLVED:
            for lv in LEVELS:
                st = grid_stats(grid(ser, case, var, lv))
                row = {"case": case, "variant": var, "level": lv, **st,
                       "local_est_GB": st["dofs"] * D2.bpd_max(1) * PR.EST_MARGIN / 1e9}
                if lv == 2:
                    row.update(est_peak_GB_S=st["dofs"] * bpd_l2 / 1e9, est_wall_s_S=st["dofs"] * s_per_dof,
                               est_basis="[S] DOF x the measured T0228 L2 peak bytes/DOF and wall s/DOF of the same "
                                         "case under max_lines (e2-highmem-8); wall scales with CG count too")
                rows.append(row)
    l2 = [r for r in rows if r["level"] == 2]
    return {"task": "T0235", "label": "LABELLED DIAGNOSTIC (not a candidate configuration)", "candidate": CID,
            "variants_solved": list(VARIANTS_SOLVED), "decisive_variant": DECISIVE, "rows": rows,
            "l2_solves": len(l2), "l2_max_est_peak_GB_S": max(r["est_peak_GB_S"] for r in l2),
            "l2_total_est_wall_s_S": sum(r["est_wall_s_S"] for r in l2),
            # post-data addition (T0235, after the local L0/L1 solves; plan.json only, no effect on solves or verdict):
            # --full's gate runs an L2 solve only if DOF x bpd_max x 1.15 <= 0.85 x physical memory
            "full_gate_min_physical_GB": max(r["local_est_GB"] for r in l2) / 0.85,
            "dev2_bytes_per_dof_local": p2.get("local_bytes_per_dof"), "burst_command": BURST_COMMAND}


def _max_lines(case: str, ds: dict, p2: dict) -> dict:
    c = ds[case]
    pr = sorted((r for r in p2["rows"] if r["problem"] == case), key=lambda r: r["level"])
    return {"source": "copied from research/o007_dev2/dev_study.json and plan.json (T0228), not re-solved",
            "levels_run": list(c["levels_run"]), "cg_max_per_level": list(c["cg_max_per_level"]),
            "dofs": list(c["dofs"]), "min_ratio_lateral_l0": float(pr[0]["min_cell_ratio_lateral"]),
            "min_ratio_lateral_per_level": [float(r["min_cell_ratio_lateral"]) for r in pr],
            "final_true_rel_resid": list(c["cg_final_true_rel_resid"]), "wall_s": list(c["wall_s"]),
            "meta_cg_max_abs_mismatch": c.get("meta_cg_max_abs_mismatch")}


def _variant(case: str, var: str, ser: dict) -> dict:
    rec: dict = {"levels_run": [], "cg_max_per_level": [], "dofs": [], "min_ratio_x": [], "min_ratio_y": [],
                 "final_true_rel_resid": [], "max_true_rel_resid": [], "wall_s": [], "process_wall_s": [],
                 "peak_rss_GB": [], "status": [], "meta_cg_matches_cg_only": [], "energy_balance": [],
                 "picard_residual_K": [], "levels_missing": []}
    for lv in LEVELS:
        p = CACHE / f"{case}__{var}__L{lv}.json"
        d = json.loads(p.read_text()) if p.exists() else {}
        if d.get("status") not in ("ok", "cg_failed"):
            rec["levels_missing"].append(lv)
            continue
        cg = [int(c["iters"]) for c in d["cg"]]
        rec["levels_run"].append(lv)
        rec["cg_max_per_level"].append(max(cg))
        rec["dofs"].append(d["dofs"])
        rec["min_ratio_x"].append(d["grid"]["min_ratio_x"])
        rec["min_ratio_y"].append(d["grid"]["min_ratio_y"])
        rec["final_true_rel_resid"].append(d["final_true_rel_resid"])
        rec["max_true_rel_resid"].append(d["max_true_rel_resid"])
        rec["wall_s"].append(d.get("wall_s"))
        rec["process_wall_s"].append(d["process_wall_s"])
        rec["peak_rss_GB"].append(d["peak_rss_bytes"] / 1e9)
        rec["status"].append(d["status"])
        rec["meta_cg_matches_cg_only"].append(d.get("meta_cg_iterations") == cg if d["status"] == "ok" else None)
        rec["energy_balance"].append(d.get("energy_balance"))
        rec["picard_residual_K"].append(d.get("picard_residual_K"))
    g0 = grid_stats(grid(ser, case, var, 0))  # grid only; equals the solved L0 grid (checked below when L0 ran)
    rec["min_ratio_lateral_l0"] = float(g0["min_ratio_lateral"])
    rec["min_ratio_lateral_per_level"] = [float(grid_stats(grid(ser, case, var, lv))["min_ratio_lateral"])
                                          for lv in LEVELS]
    if 0 in rec["levels_run"]:
        i = rec["levels_run"].index(0)
        assert min(rec["min_ratio_x"][i], rec["min_ratio_y"][i]) == rec["min_ratio_lateral_l0"], "grid mismatch"
    return rec


def verdict(dv: list[dict]) -> str:
    """Pre-registered rule (note sec. 0.4)."""
    if any(max(x["cg_max_per_level"], default=0) > CG_LIMIT for x in dv):
        return "conditioning"
    if all(x["levels_run"] == list(LEVELS) and max(x["cg_max_per_level"]) <= CG_LIMIT for x in dv):
        return "slivers"
    return "unmeasured"


def report() -> int:
    ser, _, chk = DS.load_refs()
    ds, p2 = _dev2()
    pre = json.loads(PREREG.read_text())
    sv = json.loads((OUT / "survey.json").read_text())
    cases = {}
    for case in CASES:
        vs = {"max_lines": _max_lines(case, ds, p2)}
        vs.update({v: _variant(case, v, ser) for v in VARIANTS_SOLVED})
        cases[case] = {"decisive_variant": DECISIVE[case], "variants": vs}
    dv = [cases[c]["variants"][cases[c]["decisive_variant"]] for c in CASES]
    v = verdict(dv)
    sanity = {}  # note sec. 0.5: separates a broken run from a hypothesis result
    for c in CASES:
        for var in VARIANTS_SOLVED:
            x = cases[c]["variants"][var]
            ok = [i for i, st in enumerate(x["status"]) if st == "ok"]
            sanity[f"{c}/{var}"] = {
                "energy_balance_le_1e-6": all(abs(x["energy_balance"][i]) <= 1e-6 for i in ok),
                "picard_residual_lt_1e-4K": all(x["picard_residual_K"][i] < 1e-4 for i in ok),
                "true_rel_resid_le_10x_rtol": all(x["max_true_rel_resid"][i] <= 10 * 1e-11 for i in ok),
                "cg_only_equals_meta": all(x["meta_cg_matches_cg_only"][i] for i in ok),
                "l0_grid_equals_survey": (0 not in x["levels_run"]) or x["min_ratio_lateral_l0"]
                == sv["cases"][c][var]["stats_l0"]["min_ratio_lateral"]}
    broken = [k for k, d in sanity.items() if not all(d.values())]
    out = {"task": "T0235", "label": "LABELLED DIAGNOSTIC: not a candidate configuration; no temperature of any variant "
           "enters any criterion, freeze or spec", "verdict": v, "preregistration_commit": pre["commit"],
           "verdict_rule": pre["verdict_rule"], "cg_limit": CG_LIMIT, "references": chk, "sanity": sanity,
           "sanity_failed": broken,
           "survey": {c: {var: {"min_ratio_lateral_l0": s["stats_l0"]["min_ratio_lateral"],
                                "n_slivers_below_0p1": len(s["slivers"]), "slivers": s["slivers"]}
                          for var, s in sv["cases"][c].items()} for c in sv["cases"]},
           "cases": cases}
    (OUT / "discriminator.json").write_text(json.dumps(out, indent=1, sort_keys=True) + "\n")
    log(f"verdict: {v}; decisive " + ", ".join(f"{c}: {x['levels_run']} {x['cg_max_per_level']}"
                                                 for c, x in zip(CASES, dv, strict=True)))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--survey", action="store_true")
    g.add_argument("--plan", action="store_true")
    g.add_argument("--full", action="store_true")
    g.add_argument("--report", action="store_true")
    g.add_argument("--worker")
    a = ap.parse_args(argv)
    if a.worker:
        return worker(a.worker)
    OUT.mkdir(parents=True, exist_ok=True)
    if a.survey:
        (OUT / "survey.json").write_text(json.dumps(survey(), indent=1, sort_keys=True) + "\n")
        return 0
    if a.plan:
        (OUT / "plan.json").write_text(json.dumps(plan(), indent=1, sort_keys=True) + "\n")
        return 0
    if a.report:
        return report()
    study(a.full)
    return report()


if __name__ == "__main__":
    sys.exit(main())
