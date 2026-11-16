"""T0393 (O002 F1, before E007's registration): three-level convergence of die-average Tj, per-switch spreads and
same-stratum pair differences on C004's two generator development layouts (E009 dev_layouts side_by_side_6 and
u_shaped_2) plus one same-stratum partner each, at P_ref and 0.5 P_ref, on the frozen thermal_fem rule
(research/o007_dev3/frozen_config.json).  Decides whether E007 may be judged at level 1 (F1 of
project/objectives/O002/objective.yaml).

Rules applied (F1, as restated in the T0393 packet), each per load level:
  * estimate of a three-level sequence (f0, f1, f2): mfos.metrics.gci_step_floor(f0, f1, f2, 0.01 K), i.e.
    mfos.metrics.gci_capped except that a sequence whose two steps are both below 0.01 K counts as converged with
    estimate 3 max|d|;
  * judged at level 1, the error of a value is |f1 - f2| + estimate(f0, f1, f2) (the level-2 estimate plus the
    distance of the level-1 value from the level-2 value);
  * absolute die average: error <= 1 % of that die's local rise (die average minus the mean baseplate-bottom
    temperature, both at the judged level; O002 A2's denominator);
  * per-switch spread (max - min of die averages over one switch's dies) and same-stratum pair difference (die average
    of each layout's hottest die, ranked by its judged-level die average, a minus b): error <= 0.1 K;
  * level-1 value of every spread and pair difference within 0.1 K of its level-2 value;
  * |Q_out / Q_in - 1| <= 1e-6 on every solve; hottest-node Tj at P_ref <= 175 C on every layout.
The cross-stratum difference (the two development layouts) is reported separately and never gated.

Same-stratum partners (frozen before any solve of this task): from E009's recorded development seed 20261101, the first
layout after the development layout in generate_layouts(n, 20261101, family, dies_per_switch) whose dies all have the
development layout's die size (w, h, thickness, attach thickness), by rejection (T0394's die_size_mm option does not
exist yet).  P_ref of a partner is its stratum's P_ref (equal power per die, calibrated on the development layout,
C004/E009 dev_regression_guard).

Level-2 solves for P_ref on the development layouts come from research/o007_dev3/cache only if this file's level-0 and
level-1 re-solves reproduce the cached tj_mean and tj_max within 1e-6 K at the same power (the reproduction check).

Usage:
  uv run python research/o002_f1/f1_dev_check.py --solve-local      levels 0-1 of every layout and load, one at a time
  uv run python research/o002_f1/f1_dev_check.py --analyse          recompute f1_dev_check.json from stored solves only
  uv run python research/o002_f1/f1_dev_check.py --plan [--ram-gb G] level-2 burst plan (no solve), JSON on stdout
  uv run python research/o002_f1/f1_dev_check.py --solve-level2 K1,K2  (burst VM) the named level-2 solves, scheduled by
                                                                     E009's memory figures; writes burst_out/
  uv run python research/o002_f1/f1_dev_check.py --solve-one KEY    one solve (subprocess of the two above)
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import os
import platform
import resource
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

from mfos.metrics import gci_capped, gci_step_floor

ROOT = Path(__file__).resolve().parents[2]
HERE = ROOT / "research" / "o002_f1"
CACHE = HERE / "cache"  # local solves (levels 0-1)
BURST_OUT = HERE / "burst_out"  # level-2 solves copied back from the burst VM
OUT = HERE / "f1_dev_check.json"
O7 = ROOT / "research" / "o007_dev3" / "cache"
FROZEN = ROOT / "research" / "o007_dev3" / "frozen_config.json"
FEM_FILE = ROOT / "src" / "moduleforge" / "solvers" / "thermal_fem.py"
FEM_SHA_PREFIX = "a216d5fe3209bcee"

COOLANT_K, H_W_M2K = 338.15, 5000.0  # O002 / C004 operating point (E009 config coolant_K, h_W_m2K)
DEV_SEED = 20261101  # E009 config.dev_seed
DEV = {"side_by_side_6": ("side_by_side", 6), "u_shaped_2": ("u_shaped", 2)}  # E009 config.dev_layouts
DEV_FP = {"side_by_side_6": "1f66b68a27b4bbbbc86f6ce81dbb2d1e289671988be5ac718bad7c501409a55b",
          "u_shaped_2": "6aaf383a9b7b672bf03bee01955beeceadbf4d111465db7086731ddf3cf245e6"}  # E009 dev_fingerprints
P_REF_GUARD = {"side_by_side_6": 32.232107, "u_shaped_2": 47.141886}  # E009 dev_regression_guard (rounded)
O7_L0_TAG = {"side_by_side_6": "_cal1", "u_shaped_2": "_cal2"}  # the calibration solve at exactly P_ref (l0_tag)
LOADS = {"P_ref": 1.0, "half_P_ref": 0.5}
LEVELS = (0, 1, 2)
JUDGED = 1
PARTNER_SEARCH_N = 30

STEP_FLOOR_K = 0.01
ABS_REL_TOL = 0.01
DIFF_TOL_K = 0.1
EB_TOL = 1e-6
TJ_LIMIT_K = 175.0 + 273.15
REPRO_TOL_K = 1e-6

# E009's memory figures (config fem_bytes_per_dof, fem_memory_margin, memory_fraction) for the level-2 schedule
FEM_BYTES_PER_DOF, FEM_MARGIN, MEM_FRACTION = 4964.065014991321, 1.15, 0.85
LOCAL_CAP_GB = 5.0  # agent memory rule: a local process stays within 5 GB (measured-basis estimate below)
# Burst VM (E010 spec config.compute.vm: founder's figure 0.612 $/h for n2d-custom-8-81920-ext, 78 GB visible; extended
# memory 0.0086 $/GB-h above it, an assumption to check in the console; 0.5 h set-up overhead per VM)
VM_BASE = {"machine": "n2d-custom-8-81920-ext", "ram_GB": 78.0, "usd_per_h": 0.612, "ext_usd_per_GB_h": 0.0086,
           "overhead_h": 0.5}


# ------------------------------------------------------------------------------------------------ helpers
def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def load_json(p: Path):
    return json.loads(p.read_text())


def write_json(p: Path, obj) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, indent=1, allow_nan=True))
    os.replace(tmp, p)


def fin(x: float):
    return None if x is None or not math.isfinite(x) else float(x)


def p_ref() -> dict:
    out = {}
    for n in DEV:
        cal = load_json(O7 / f"a_q1h4_graded_gs2__{n}__calibration.json")
        if cal["status"] != "ok" or cal["l0_tag"] != O7_L0_TAG[n] or abs(cal["power_W"] - P_REF_GUARD[n]) > 5e-7:
            raise SystemExit(f"{n}: calibration record does not match E009 dev_regression_guard ({cal})")
        out[n] = float(cal["power_W"])
    return out


def rule_from_frozen():
    """The frozen GridRule, key for key as experiments/runners/e009_run.py rule_from."""
    from moduleforge.solvers import thermal_fem as FEM
    fr = load_json(FROZEN)
    eg = fr["edge_grading"]
    return FEM.GridRule(h0=float(fr["h0_m"]), nz={}, default_nz=int(fr["nz_min"]), zrefine=bool(fr["zrefine"]),
                        near_margin=float(fr["near_margin_m"]), min_cells=int(fr["min_cells"]),
                        element_order=int(fr["element_order"]), dz_max=float(fr["dz_max_m"]),
                        edge_grading=(float(eg["first_offset_m"]), float(eg["ratio"]), float(eg["max_offset_m"]),
                                      float(eg["min_gap_fraction"])),
                        amg_gs_sweeps=int(fr["amg_gs_sweeps"]))


def _die_key(lay) -> tuple:
    keys = {(round(d.w, 12), round(d.h, 12), round(d.thickness, 12), round(d.attach_thickness, 12)) for d in lay.dies}
    if len(keys) != 1:
        raise SystemExit("a layout with more than one die size")
    return keys.pop()


_LAYS: dict = {}


def layouts() -> dict:
    """{name: (layout, stratum, role, record)}: the two development layouts and their partners (rule in docstring)."""
    if _LAYS:
        return _LAYS
    from moduleforge.generate.halfbridge import generate_layouts
    for n, (fam, k) in DEV.items():
        lays = generate_layouts(PARTNER_SEARCH_N, DEV_SEED, family=fam, dies_per_switch=k)
        dev = lays[0]
        if dev.fingerprint() != DEV_FP[n]:
            raise SystemExit(f"{n}: fingerprint {dev.fingerprint()} != E009 {DEV_FP[n]}")
        key = _die_key(dev)
        idx = next(i for i in range(1, len(lays)) if _die_key(lays[i]) == key and lays[i].fingerprint() != dev.fingerprint())
        rej = [{"index": i, "die_w_mm": round(lays[i].dies[0].w * 1e3, 6)} for i in range(1, idx)]
        for name, lay, role, i in ((n, dev, "dev", 0), (f"{n}_p", lays[idx], "partner", idx)):
            _LAYS[name] = (lay, n, role, {"family": fam, "dies_per_switch": k, "seed": DEV_SEED, "stream_index": i,
                                          "fingerprint": lay.fingerprint(), "die_w_h_t_attach_m": list(key),
                                          "rejected_before": rej if role == "partner" else [],
                                          "switch": [d.switch for d in lay.dies],
                                          "baseplate_area_m2": float(lay.baseplate_outline.area)})
    return _LAYS


def key_of(name: str, load: str, lv: int) -> str:
    return f"{name}__{load}__L{lv}"


def all_keys(levels=LEVELS) -> list[str]:
    return [key_of(n, ld, lv) for n in ("side_by_side_6", "side_by_side_6_p", "u_shaped_2", "u_shaped_2_p")
            for ld in LOADS for lv in levels]


def parse_key(k: str) -> tuple[str, str, int]:
    n, ld, lv = k.split("__")
    return n, ld, int(lv[1:])


def peak_rss_gb() -> float:
    r = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return r / 1e9 if sys.platform == "darwin" else r * 1024 / 1e9


# ------------------------------------------------------------------------------------------------ solving
def _bottom_mean(r, area: float) -> float:
    """Mean baseplate-bottom temperature: exact integral of the Q1 interpolant over z = 0 (tensor trapezoid on the grid
    lines) divided by the baseplate area; NaN if the bottom nodes are not the full tensor grid."""
    x, y = np.asarray(r.meta["lines"]["x"]), np.asarray(r.meta["lines"]["y"])
    nodes = np.asarray(r.nodes)
    sel = np.abs(nodes[:, 2]) < 1e-12
    if sel.sum() != x.size * y.size:
        return float("nan")
    ix = np.clip(np.searchsorted(x, nodes[sel, 0] - 1e-12), 0, x.size - 1)
    iy = np.clip(np.searchsorted(y, nodes[sel, 1] - 1e-12), 0, y.size - 1)
    T = np.full((x.size, y.size), np.nan)
    T[ix, iy] = np.asarray(r.T)[sel]
    if np.isnan(T).any():
        return float("nan")
    integ = np.trapezoid(np.trapezoid(T, y, axis=1), x)
    return float(integ / ((x[-1] - x[0]) * (y[-1] - y[0]))) if abs((x[-1] - x[0]) * (y[-1] - y[0]) - area) < 1e-12 \
        else float("nan")


def solve_one(key: str, outdir: Path) -> dict:
    from moduleforge.solvers import thermal_fem as FEM
    name, load, lv = parse_key(key)
    lay, stratum, role, rec = layouts()[name]
    P = p_ref()[stratum] * LOADS[load]
    rule = rule_from_frozen()
    est = int(FEM.estimate_dofs(lay, rule, lv))
    t0 = time.time()
    r = FEM.solve_layout(lay, P, H_W_M2K, COOLANT_K, rule=rule, level=lv)
    m = r.meta
    area = rec["baseplate_area_m2"]
    out = {"key": key, "layout": name, "stratum": stratum, "role": role, "load": load, "level": lv, "power_W": P,
           "fingerprint": rec["fingerprint"], "source": "this task", "tj_mean": [float(v) for v in r.tj_mean],
           "tj_max": [float(v) for v in r.tj_max], "tj_max_xyz": m["tj_max_xyz"],
           "energy_balance": float(r.energy_balance), "q_in_W": float(m["q_in_W"]), "q_out_W": float(m["q_out_W"]),
           "bottom_mean_T_K_trapezoid": _bottom_mean(r, area),
           "bottom_mean_T_K_flux": COOLANT_K + float(m["q_out_W"]) / (H_W_M2K * area), "baseplate_area_m2": area,
           "dofs": int(r.dofs), "estimated_dofs": est, "wall_s": float(r.wall_s), "process_wall_s": time.time() - t0,
           "peak_rss_GB": peak_rss_gb(), "picard_iters": int(r.picard_iters), "picard_residual_K": float(r.picard_residual),
           "cg_max_iterations": int(m["cg_max_iterations"]), "cg_hit_maxiter": bool(m["cg_hit_maxiter"]),
           "linear_rel_residual_max": float(m["linear_rel_residual_max"]), "amg_gs_sweeps": m["amg_gs_sweeps"],
           "n_lines": m["n_lines"], "max_snap_m": float(m["max_snap_m"]), "platform": sys.platform,
           "host": platform.node(), "thermal_fem_sha256": sha256(FEM_FILE), "frozen_config_sha256": sha256(FROZEN),
           "status": "ok"}
    write_json(outdir / f"{key}.json", out)
    return out


def _run_sub(key: str, outdir: Path) -> subprocess.Popen:
    return subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "--solve-one", key, "--outdir", str(outdir)])


def measured_bytes_per_dof(stratum: str, lv: int) -> float:
    """Measured peak RSS per DOF of the cached frozen-rule solve of the same stratum's development layout at the same
    level (level 1 for level 0, whose per-DOF figure is larger because of the fixed base RSS: conservative)."""
    d = load_json(O7 / f"a_q1h4_graded_gs2__{stratum}__L{max(lv, 1)}__kT.json")
    return d["peak_rss_bytes"] / d["dofs"]


def solve_local() -> int:
    from moduleforge.solvers import thermal_fem as FEM
    if not sha256(FEM_FILE).startswith(FEM_SHA_PREFIX):
        raise SystemExit("thermal_fem.py is not the frozen bytes: refusing to solve")
    rule = rule_from_frozen()
    for k in all_keys(levels=(0, 1)):
        if (CACHE / f"{k}.json").exists():
            continue
        name, _, lv = parse_key(k)
        bpd = measured_bytes_per_dof(layouts()[name][1], lv) * FEM_MARGIN
        est_gb = FEM.estimate_dofs(layouts()[name][0], rule, lv) * bpd / 1e9
        if est_gb > LOCAL_CAP_GB:
            print(f"{k}: estimated {est_gb:.1f} GB > {LOCAL_CAP_GB} GB local cap: not solved locally", flush=True)
            continue
        t0 = time.time()
        rc = _run_sub(k, CACHE).wait()
        print(f"{k}: rc {rc}, {time.time() - t0:.0f} s, est {est_gb:.2f} GB", flush=True)
        if rc != 0:
            return rc
    return 0


def solve_level2(keys: list[str]) -> int:
    """Burst VM: the named level-2 solves, largest first, a job starting only while the sum of the running jobs' E009
    memory estimates (DOF x fem_bytes_per_dof x margin) stays within memory_fraction x physical memory."""
    from moduleforge.solvers import thermal_fem as FEM
    if not sha256(FEM_FILE).startswith(FEM_SHA_PREFIX):
        raise SystemExit("thermal_fem.py is not the frozen bytes: refusing to solve")
    usable = MEM_FRACTION * FEM.physical_memory_bytes() / 1e9
    rule = rule_from_frozen()
    est = {}
    for k in keys:
        name, _, lv = parse_key(k)
        if lv != 2:
            raise SystemExit(f"{k}: --solve-level2 takes level-2 keys only")
        est[k] = FEM.estimate_dofs(layouts()[name][0], rule, lv) * FEM_BYTES_PER_DOF * FEM_MARGIN / 1e9
    todo = sorted((k for k in keys if not (BURST_OUT / f"{k}.json").exists()), key=lambda k: -est[k])
    if any(est[k] > usable for k in todo):
        raise SystemExit(f"a job exceeds {usable:.1f} GB usable: {[(k, round(est[k], 1)) for k in todo]}")
    running: dict = {}
    fails = 0
    while todo or running:
        for k in list(todo):
            if sum(est[j] for j in running) + est[k] <= usable:
                running[k] = _run_sub(k, BURST_OUT)
                todo.remove(k)
                print(f"started {k} (est {est[k]:.1f} GB; running {sorted(running)})", flush=True)
        time.sleep(10)
        for k, p in list(running.items()):
            if p.poll() is not None:
                print(f"finished {k}: rc {p.returncode}", flush=True)
                fails += p.returncode != 0
                del running[k]
    return 1 if fails else 0


# ------------------------------------------------------------------------------------------------ stored solves
def _o7_record(name: str, lv: int) -> dict | None:
    tag = O7_L0_TAG[name] if lv == 0 else ""
    p = O7 / f"a_q1h4_graded_gs2__{name}__L{lv}__kT{tag}.json"
    if not p.exists():
        return None
    d = load_json(p)
    if d.get("status") != "ok":
        return None
    return {"key": key_of(name, "P_ref", lv), "layout": name, "stratum": name, "role": "dev", "load": "P_ref",
            "level": lv, "power_W": float(d["power_W"]), "source": f"research/o007_dev3/cache/{p.name}",
            "tj_mean": d["tj_mean"], "tj_max": d["tj_max"], "energy_balance": float(d["energy_balance"]),
            "q_in_W": d["q_in_W"], "q_out_W": d["q_out_W"], "dofs": int(d["dofs"]), "wall_s": float(d["wall_s"]),
            "peak_rss_GB": d["peak_rss_bytes"] / 1e9, "picard_iters": d["picard_iters"],
            "picard_residual_K": d["picard_residual"], "cg_max_iterations": d["cg_max_iterations"],
            "cg_hit_maxiter": d["cg_hit_maxiter"], "platform": d["platform"], "status": "ok"}


def reproduction() -> dict:
    """Own level-0/1 re-solves at P_ref against the cached o007_dev3 solves: max |dT| over dies of tj_mean and tj_max."""
    rows, ok = [], True
    for n in DEV:
        for lv in (0, 1):
            own_p, o7 = CACHE / f"{key_of(n, 'P_ref', lv)}.json", _o7_record(n, lv)
            if not own_p.exists() or o7 is None:
                rows.append({"layout": n, "level": lv, "status": "missing"})
                ok = False
                continue
            own = load_json(own_p)
            dm = float(np.max(np.abs(np.subtract(own["tj_mean"], o7["tj_mean"]))))
            dx = float(np.max(np.abs(np.subtract(own["tj_max"], o7["tj_max"]))))
            same_p = own["power_W"] == o7["power_W"]
            passed = dm <= REPRO_TOL_K and dx <= REPRO_TOL_K and same_p
            ok &= passed
            rows.append({"layout": n, "level": lv, "max_abs_dT_mean_K": dm, "max_abs_dT_max_K": dx,
                         "same_power": same_p, "own_thermal_fem_sha256": own["thermal_fem_sha256"], "passed": passed})
    return {"tol_K": REPRO_TOL_K, "passed": ok, "rows": rows}


def stored(repro_ok: bool) -> dict:
    """{key: solve record} for every stored solve; the o007_dev3 level-2 solves at P_ref only if reproduction passed."""
    out = {}
    for d in (CACHE, BURST_OUT):
        if d.exists():
            for p in sorted(d.glob("*__L[012].json")):
                rec = load_json(p)
                if rec.get("status") == "ok":
                    out[rec["key"]] = rec
    if repro_ok:
        for n in DEV:
            k = key_of(n, "P_ref", 2)
            if k not in out:
                rec = _o7_record(n, 2)
                if rec is not None:
                    out[k] = rec
    return out


# ------------------------------------------------------------------------------------------------ F1 analysis
def estimate(seq: list[float]) -> float:
    return gci_step_floor(seq[0], seq[1], seq[2], STEP_FLOOR_K)


def seq_record(seq: list[float | None], tol: float | None) -> dict:
    """One quantity's level sequence: steps, gci_capped (plain), F1 estimate, level-1 error and the gates."""
    have = [v is not None for v in seq]
    r = {"values_by_level": seq, "d1": None, "d2": None}
    if have[0] and have[1]:
        r["d1"] = seq[1] - seq[0]
    if all(have):
        e = estimate(seq)
        r.update(d2=seq[2] - seq[1], gci_capped=fin(gci_capped(*seq)), estimate_L2=fin(e),
                 step_floor_applied=abs(seq[1] - seq[0]) < STEP_FLOOR_K and abs(seq[2] - seq[1]) < STEP_FLOOR_K,
                 error_L1=fin(abs(seq[1] - seq[2]) + e), l1_minus_l2=seq[1] - seq[2])
        if tol is not None:
            r["tol"] = tol
            r["pass_L1"] = bool(math.isfinite(e) and abs(seq[1] - seq[2]) + e <= tol)
            r["pass_L2"] = bool(math.isfinite(e) and e <= tol)
    elif tol is not None:
        r.update(tol=tol, pass_L1=None, pass_L2=None)
    return r


def analyse() -> dict:
    lays = layouts()
    P = p_ref()
    fem_sha = sha256(FEM_FILE)
    rep = reproduction()
    S = stored(rep["passed"])

    def vals(name, load, field):
        return [S[key_of(name, load, lv)][field] if key_of(name, load, lv) in S else None for lv in LEVELS]

    def bottom(name, load, lv):
        k = key_of(name, load, lv)
        if k not in S:
            return None
        return COOLANT_K + S[k]["q_out_W"] / (H_W_M2K * lays[name][3]["baseplate_area_m2"])

    checks = {c: {} for c in ("abs_die_average", "spread", "pair_difference", "level1_vs_level2",
                              "cross_stratum_difference", "energy_balance", "tj_at_P_ref", "sanity")}
    for load in LOADS:
        ab, sp, pr, lvl, xs = [], [], [], [], []
        hot = {}
        for name, (lay, _stratum, role, _rec) in lays.items():
            tm = vals(name, load, "tj_mean")
            n = len(lay.dies)
            if tm[JUDGED] is not None:
                hot[name] = int(np.argmax(tm[JUDGED]))
            for i in range(n):
                seq = [None if t is None else float(t[i]) for t in tm]
                tb = bottom(name, load, JUDGED)
                rise = None if seq[JUDGED] is None else seq[JUDGED] - tb
                r = seq_record(seq, None if rise is None else ABS_REL_TOL * rise)
                tb2 = bottom(name, load, 2)
                rise2 = None if seq[2] is None else seq[2] - tb2
                r["pass_L2"] = None if rise2 is None or r.get("estimate_L2") is None else \
                    bool(r["estimate_L2"] <= ABS_REL_TOL * rise2)
                r.update(layout=name, role=role, die=i, switch=lay.dies[i].switch, local_rise_L1_K=rise,
                         rel_error_L1=None if r.get("error_L1") is None else r["error_L1"] / rise,
                         rel_step_d1=None if r["d1"] is None else abs(r["d1"]) / rise)
                ab.append(r)
            for sw in ("HS", "LS"):
                idx = [i for i, d in enumerate(lay.dies) if d.switch == sw]
                seq = [None if t is None else float(np.max(np.take(t, idx)) - np.min(np.take(t, idx))) for t in tm]
                r = seq_record(seq, DIFF_TOL_K)
                r.update(layout=name, role=role, switch=sw, dies=idx)
                sp.append(r)
                lvl.append(_l1_vs_l2("spread", f"{name}/{sw}", seq))
        for stratum in DEV:
            a, b = stratum, f"{stratum}_p"
            if a in hot and b in hot:
                ta, tb_ = vals(a, load, "tj_mean"), vals(b, load, "tj_mean")
                seq = [None if (x is None or y is None) else float(x[hot[a]] - y[hot[b]]) for x, y in zip(ta, tb_, strict=True)]
                r = seq_record(seq, DIFF_TOL_K)
                own = [None if (x is None or y is None) else float(np.max(x) - np.max(y)) for x, y in zip(ta, tb_, strict=True)]
                r.update(pair=[a, b], stratum=stratum, hottest_die_by_L1={a: hot[a], b: hot[b]},
                         hottest_die_by_L2={k: (None if vals(k, load, "tj_mean")[2] is None else
                                                int(np.argmax(vals(k, load, "tj_mean")[2]))) for k in (a, b)},
                         own_hottest_max_variant=seq_record(own, None))
                pr.append(r)
                lvl.append(_l1_vs_l2("pair_difference", f"{a}-{b}", seq))
        a, b = "side_by_side_6", "u_shaped_2"
        if a in hot and b in hot:
            ta, tb_ = vals(a, load, "tj_mean"), vals(b, load, "tj_mean")
            seq = [None if (x is None or y is None) else float(x[hot[a]] - y[hot[b]]) for x, y in zip(ta, tb_, strict=True)]
            r = seq_record(seq, None)
            r.update(pair=[a, b], note="cross-stratum: reported only, never a same-stratum pair")
            xs.append(r)
        checks["abs_die_average"][load] = _summ(ab)
        checks["spread"][load] = _summ(sp)
        checks["pair_difference"][load] = _summ(pr)
        checks["level1_vs_level2"][load] = _summ(lvl)
        checks["cross_stratum_difference"][load] = {"values": xs}
    # energy balance and Tj at P_ref on every solve / layout
    solves = []
    for k in all_keys():
        if k in S:
            s = S[k]
            solves.append({kk: s.get(kk) for kk in ("key", "layout", "load", "level", "power_W", "source",
                                                    "energy_balance", "dofs", "wall_s", "peak_rss_GB", "picard_iters",
                                                    "picard_residual_K", "cg_max_iterations", "cg_hit_maxiter",
                                                    "platform", "thermal_fem_sha256")})
    ebmax = max(s["energy_balance"] for s in solves)
    checks["energy_balance"] = {"tol": EB_TOL, "max": ebmax, "passed": bool(ebmax <= EB_TOL), "n_solves": len(solves)}
    tj = []
    for name in lays:
        for lv in LEVELS:
            k = key_of(name, "P_ref", lv)
            if k in S:
                tj.append({"layout": name, "level": lv, "tj_max_C": max(S[k]["tj_max"]) - 273.15,
                           "tj_avg_max_C": max(S[k]["tj_mean"]) - 273.15})
    checks["tj_at_P_ref"] = {"limit_C": TJ_LIMIT_K - 273.15, "values": tj,
                             "passed": bool(all(t["tj_max_C"] <= TJ_LIMIT_K - 273.15 for t in tj))}
    checks["sanity"] = sanity(S, lays)
    # verdict
    missing = [k for k in all_keys(levels=(2,)) if k not in S]
    missing01 = [k for k in all_keys(levels=(0, 1)) if k not in S]
    flags = []
    for c in ("abs_die_average", "spread", "pair_difference", "level1_vs_level2"):
        for load in LOADS:
            flags += [v.get("pass_L1") for v in checks[c][load]["values"]]
    hard_fail = (not checks["energy_balance"]["passed"]) or (not checks["tj_at_P_ref"]["passed"])
    if any(f is False for f in flags):
        level1 = "refuted"
    elif hard_fail:
        level1 = "pending"  # the experiment is broken (energy or envelope), not a level-1 verdict
    elif flags and all(f is True for f in flags) and not missing and not missing01:
        level1 = "confirmed"
    else:
        level1 = "pending"
    return {"task": "T0393", "objective": "O002", "failure_mode": "F1",
            "status": "complete" if not missing and not missing01 else "awaiting_level2",
            "level1": level1, "missing_level2": missing, "missing_level0_1": missing01,
            "loads": {ld: {"factor": f, "power_W_per_die": {s: P[s] * f for s in DEV}} for ld, f in LOADS.items()},
            "thermal_fem_sha256": fem_sha, "frozen_config_sha256": sha256(FROZEN),
            "rules": {"estimator": "mfos.metrics.gci_step_floor(f0, f1, f2, 0.01 K) (gci_capped with the step floor)",
                      "error_at_level1": "|f1 - f2| + estimate", "abs_die_average_tol": "0.01 x local rise at level 1",
                      "spread_pair_tol_K": DIFF_TOL_K, "level1_vs_level2_tol_K": DIFF_TOL_K, "energy_balance_tol": EB_TOL,
                      "tj_limit_C": 175.0, "judged_level": JUDGED, "hottest_die": "argmax of the level-1 die average"},
            "layouts": {n: v[3] | {"stratum": v[1], "role": v[2]} for n, v in lays.items()},
            "reproduction_check": rep, "checks": checks, "solves": solves,
            "level2_plan": plan(missing, VM_BASE["ram_GB"]) if missing else None}


def _l1_vs_l2(kind: str, ident: str, seq: list) -> dict:
    ok = None if seq[1] is None or seq[2] is None else bool(abs(seq[1] - seq[2]) <= DIFF_TOL_K)
    return {"quantity": kind, "id": ident, "L1": seq[1], "L2": seq[2],
            "abs_diff_K": None if ok is None else abs(seq[1] - seq[2]), "tol": DIFF_TOL_K, "pass_L1": ok}


def _summ(rows: list[dict]) -> dict:
    flags = [r.get("pass_L1") for r in rows]
    worst = [r.get("error_L1", r.get("abs_diff_K")) for r in rows]
    worst = [w for w in worst if w is not None]
    return {"values": rows, "n": len(rows), "n_pass": sum(f is True for f in flags), "n_fail": sum(f is False for f in flags),
            "n_pending": sum(f is None for f in flags), "max_error_L1": max(worst) if worst else None,
            "passed": None if any(f is None for f in flags) else bool(all(flags))}


def sanity(S: dict, lays: dict) -> dict:
    """Checks that separate 'the experiment is broken' from 'level 1 is insufficient'."""
    out = {}
    fps = {n: v[3]["fingerprint"] for n, v in lays.items()}
    out["dev_fingerprints"] = {"passed": all(fps[n] == DEV_FP[n] for n in DEV), "values": fps}
    out["partners_distinct_same_die"] = {"passed": len(set(fps.values())) == 4 and all(
        lays[f"{n}_p"][3]["die_w_h_t_attach_m"] == lays[n][3]["die_w_h_t_attach_m"] for n in DEV)}
    pic = [s.get("picard_residual_K") for s in S.values()]
    out["picard_converged"] = {"passed": all(p is not None and p < 1e-4 for p in pic), "max_K": max(pic)}
    out["cg_not_capped"] = {"passed": not any(s.get("cg_hit_maxiter") for s in S.values())}
    own = [s for s in S.values() if s.get("source") == "this task"]
    out["own_solves_frozen_bytes"] = {"passed": all(s["thermal_fem_sha256"].startswith(FEM_SHA_PREFIX) for s in own)}
    bm = [abs(s["bottom_mean_T_K_trapezoid"] - s["bottom_mean_T_K_flux"]) for s in own
          if math.isfinite(s.get("bottom_mean_T_K_trapezoid", float("nan")))]
    out["bottom_mean_two_ways"] = {"passed": bool(bm) and max(bm) <= 1e-6 and len(bm) == len(own),
                                   "max_abs_diff_K": max(bm) if bm else None, "n": len(bm),
                                   "basis": "trapezoid of the Q1 field at z = 0 vs T_c + Q_out / (h A)"}
    growth = []
    for n in lays:
        for ld in LOADS:
            d = [S[key_of(n, ld, lv)]["dofs"] for lv in LEVELS if key_of(n, ld, lv) in S]
            growth += [b / a for a, b in itertools.pairwise(d)]
    out["dof_growth_8x"] = {"passed": all(abs(g / 8 - 1) <= 0.15 for g in growth), "ratios": growth}
    # power scaling: k(T) falls with T in these materials, so rise(P/2) < rise(P)/2; the ratio is close to 1/2
    sc = []
    for n in lays:
        for lv in (0, 1):
            a, b = S.get(key_of(n, "P_ref", lv)), S.get(key_of(n, "half_P_ref", lv))
            if a and b:
                ra = np.asarray(a["tj_mean"]) - COOLANT_K
                rb = np.asarray(b["tj_mean"]) - COOLANT_K
                sc.append({"layout": n, "level": lv, "ratio_min": float((rb / ra).min()), "ratio_max": float((rb / ra).max())})
    out["half_load_scaling"] = {"passed": all(0.40 <= s["ratio_min"] and s["ratio_max"] <= 0.5 for s in sc), "values": sc}
    return out


# ------------------------------------------------------------------------------------------------ burst plan
def plan(missing: list[str], ram_gb: float) -> dict:
    from moduleforge.solvers import thermal_fem as FEM
    rule = rule_from_frozen()
    rate = max(load_json(O7 / f"a_q1h4_graded_gs2__{n}__L2__kT.json")["wall_s"] /
               load_json(O7 / f"a_q1h4_graded_gs2__{n}__L2__kT.json")["dofs"] for n in DEV)
    usable = MEM_FRACTION * ram_gb
    jobs = []
    for k in missing:
        name, _, lv = parse_key(k)
        dofs = int(FEM.estimate_dofs(layouts()[name][0], rule, lv))
        jobs.append({"key": k, "est_dofs": dofs, "est_GB_E009": dofs * FEM_BYTES_PER_DOF * FEM_MARGIN / 1e9,
                     "est_wall_h": dofs * rate / 3600})
    jobs.sort(key=lambda j: -j["est_GB_E009"])
    # simulate the greedy memory scheduler of solve_level2
    t, running, todo, start = 0.0, [], list(jobs), {}
    while todo or running:
        for j in list(todo):
            if sum(r["est_GB_E009"] for r in running) + j["est_GB_E009"] <= usable:
                running.append(j)
                todo.remove(j)
                start[j["key"]] = t
                j["end_h"] = t + j["est_wall_h"]
        if not running:
            break
        nxt = min(r["end_h"] for r in running)
        t = nxt
        running = [r for r in running if r["end_h"] > nxt + 1e-12]
    fits = not todo
    vm_h = t + VM_BASE["overhead_h"]
    usd_h = VM_BASE["usd_per_h"] + VM_BASE["ext_usd_per_GB_h"] * max(0.0, ram_gb - VM_BASE["ram_GB"])
    mb = int(round(ram_gb * 1024 / 256)) * 256 if ram_gb != VM_BASE["ram_GB"] else 81920
    return {"machine": f"n2d-custom-8-{mb}-ext", "ram_GB": ram_gb, "usable_GB": usable, "fits": fits,
            "jobs": [{**j, "start_h": start.get(j["key"], -1.0)} for j in jobs], "keys": [j["key"] for j in jobs],
            "peak_job_GB_E009": max((j["est_GB_E009"] for j in jobs), default=0.0),
            "wall_rate_s_per_dof": rate, "makespan_h": t, "vm_hours": vm_h, "usd_per_h": usd_h, "usd": vm_h * usd_h,
            "basis": "DOF from thermal_fem.estimate_dofs; memory DOF x 4964 B x 1.15 (E009); wall at the slowest "
                     "measured s/DOF of the cached level-2 dev solves (linux burst, T0243); price E010 config.compute.vm"}


# ------------------------------------------------------------------------------------------------ main
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--analyse", action="store_true")
    g.add_argument("--solve-local", action="store_true")
    g.add_argument("--solve-one")
    g.add_argument("--solve-level2")
    g.add_argument("--plan", action="store_true")
    ap.add_argument("--outdir", default=str(CACHE))
    ap.add_argument("--ram-gb", type=float, default=VM_BASE["ram_GB"])
    a = ap.parse_args(argv)
    if a.solve_one:
        solve_one(a.solve_one, Path(a.outdir))
        return 0
    if a.solve_local:
        return solve_local()
    if a.solve_level2:
        return solve_level2(a.solve_level2.split(","))
    if a.plan:
        rep = reproduction()
        S = stored(rep["passed"])
        missing = [k for k in all_keys(levels=(2,)) if k not in S]
        print(json.dumps(plan(missing, a.ram_gb), indent=1))
        return 0
    res = analyse()
    write_json(OUT, res)
    print(json.dumps({k: res[k] for k in ("status", "level1", "missing_level2")}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
