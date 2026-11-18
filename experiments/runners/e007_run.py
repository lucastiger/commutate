"""E007 (O002): the frozen L1 thermal model against the frozen scikit-fem reference (C004) on fresh sealed generator layouts.

Modes (spec experiments/drafts/E007.yaml, design note research/notes/e007-design.md):
  (none)           the registered run, under mfos.evidence.ExperimentRun with the sealed seed (MFOS_SEED)
  --selftest       fake solvers on the registered allocation (m = 20); full sample construction, checkpointed job loop,
                   row assembly, nulls, recompute through research/o002_e007/e007_metrics.py and mfos.metrics, the
                   evaluator's null check (applies_to), mutation checks; then the REAL reference path: one level-0 P_ref
                   calibration of a development layout through a real child process (energy balance, Picard, CG, Q1
                   bottom mean = flux mean, DOF and memory estimators) and real DOF growth on the level-2 subset
  --verify-freeze  every frozen hash and value (code, GridRule key for key, L1 grid rule and calibration table)
  --plan           every solve with memory and time, cpu_hours_est, $, local or burst per policy local_cpu_hours_max
  --dev            development geometry only (recorded development seed; never a sealed seed), level 1, for T0398 (n7)
  --child JOB      internal: one reference solve or one P_ref calibration in its own process (checkpoint record)
  --l1-phase JOBS  internal: every L1 evaluation in one single-threaded process, timed, in the sealed order

Order of a run (each step fixed and written to the work directory before the next starts): freeze checks -> sealed
sub-seeds -> per-stratum die size -> judged layouts, F7 pools, level-2 subset, timing order (plan_frozen.json, hashed)
-> P_ref per stratum (level-0 calibration on the stratum's development layout, never judged; pref.json, hashed) -> L1
phase: after every calibration solve has finished and before any judged reference solve, with no solve running (A5
timed block first, then the untimed constant-k ablation, the F7 pools and the F7 optimised layouts at half load) ->
reference solves (level 1 judged; levels 0 and 2 on the subset; F7 optimised layouts) -> rows -> metrics.
SI units, float64. Temperatures in K. Formula citations: e007_metrics.py (bounds), solvers/thermal_series.py (null a).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import resource
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "research" / "o002_e007"))
import e007_metrics as EM  # noqa: E402  (runner helpers and the bound F3 selected; row contract e007_row_contract.md)

EID = "E007"
FAMILIES = ("side_by_side", "interleaved", "u_shaped")
DIE_COUNTS = (2, 3, 4, 5, 6)
BANDS = {"2-3": (2, 3), "4-6": (4, 5, 6)}
STREAMS = {"die_size": 1, "layouts": 2, "f7": 3, "timing_order": 4, "l2_subset": 5, "f7_strata": 6}
THREAD_VARS = ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS",
               "NUMEXPR_NUM_THREADS")
A5_CI_LEVEL = 0.95  # A5's median interval: computed and recorded at this level (reviews T0449/T0450 (1))
FAKE = False  # set by --selftest / --fake: analytic stand-ins for both solvers (never evidence)


# ------------------------------------------------------------------------------------------------ small utilities
def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def sha256_file(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def sha256_obj(o: Any) -> str:
    return hashlib.sha256(json.dumps(o, sort_keys=True, default=str).encode()).hexdigest()


def write_json(p: Path, obj: Any) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o)))
    os.replace(tmp, p)


def read_json(p: Path) -> Any:
    return json.loads(Path(p).read_text())


def load_spec() -> dict:
    env = os.environ.get("MFOS_SPEC_JSON")
    if env:
        return json.loads(env)
    for p in (ROOT / "experiments" / "specs" / f"{EID}.yaml", ROOT / "experiments" / "drafts" / f"{EID}.yaml"):
        if p.exists():
            return yaml.safe_load(p.read_text())
    raise FileNotFoundError(f"no {EID} spec")


def peak_rss_gb(children: bool = False) -> float:
    r = resource.getrusage(resource.RUSAGE_CHILDREN if children else resource.RUSAGE_SELF).ru_maxrss
    return r / 1e9 if sys.platform == "darwin" else r * 1024 / 1e9


def swap_used_gb() -> float:
    if sys.platform != "darwin":
        return 0.0
    try:
        out = subprocess.run(["sysctl", "vm.swapusage"], capture_output=True, text=True, timeout=10).stdout
        used = out.split("used =")[1].split()[0]
        return float(used[:-1]) / (1024.0 if used.endswith("M") else 1.0)
    except Exception:
        return 0.0


def stratum_name(f: str, k: int) -> str:
    return f"{f}/{k}"


def band_of(k: int) -> str:
    return next(b for b, ks in BANDS.items() if k in ks)


def all_strata() -> list[tuple[str, int]]:
    return [(f, k) for f in FAMILIES for k in DIE_COUNTS]


def cells() -> list[tuple[str, str]]:
    return [(f, b) for f in FAMILIES for b in BANDS]


# ------------------------------------------------------------------------------------------------ freeze
def fem_rule(fr: dict):
    """The one scikit-fem GridRule of E007, key for key from the frozen file (as e009_run.rule_from)."""
    from moduleforge.solvers import thermal_fem as FEM
    eg = fr["edge_grading"]
    return FEM.GridRule(h0=float(fr["h0_m"]), nz={}, default_nz=int(fr["nz_min"]), zrefine=bool(fr["zrefine"]),
                        near_margin=float(fr["near_margin_m"]), min_cells=int(fr["min_cells"]),
                        element_order=int(fr["element_order"]), dz_max=float(fr["dz_max_m"]),
                        edge_grading=(float(eg["first_offset_m"]), float(eg["ratio"]), float(eg["max_offset_m"]),
                                      float(eg["min_gap_fraction"])),
                        amg_gs_sweeps=int(fr["amg_gs_sweeps"]))


def freeze_checks(cfg: dict) -> list[dict]:
    """(name, passed, detail) for every frozen hash and value; all run before the first solve of any mode."""
    out: list[dict] = []

    def add(name: str, ok: bool, detail: Any) -> None:
        out.append({"name": name, "passed": bool(ok), "detail": str(detail)[:600]})
    for path, want in cfg["freeze"]["files"].items():
        got = sha256_file(ROOT / path) if (ROOT / path).exists() else "missing"
        add(f"file:{path}", got == want, f"{got[:16]} vs {want[:16]}")
    tf = sha256_file(ROOT / cfg["thermal_fem_path"])
    add("thermal_fem_sha256", tf == cfg["thermal_fem_sha256"] and tf.startswith("a216d5fe3209bcee"), tf)
    frp = ROOT / cfg["fem_rule_path"]
    add("grid_rule_file_sha256", sha256_file(frp) == cfg["fem_rule_file_sha256"], sha256_file(frp))
    disk = read_json(frp)
    diff = sorted(k for k in set(disk) | set(cfg["fem_rule"]) if disk.get(k) != cfg["fem_rule"].get(k))
    add("grid_rule_key_for_key", not diff, "equal" if not diff else f"differs in {diff}")
    from moduleforge.solvers import thermal_fem as FEM
    fr = cfg["fem_rule"]
    prod = {"snap_fraction": FEM.SNAP_FRACTION, "linear_rtol": FEM.LINEAR_RTOL, "cg_maxiter": FEM.CG_MAXITER,
            "amg_seed": FEM.AMG_SEED, "picard_tol_K": FEM.PICARD_TOL_K, "refinement_ratio": FEM.REFINEMENT_RATIO,
            "levels": list(FEM.LEVELS)}
    bad = [k for k, v in prod.items() if fr.get(k) != v]
    add("fem_production_constants", not bad and FEM.DATA_INTORDER == 7 and fr["feasible"] is True
        and not fr["levels_missing"] and fr["amg_gs_sweeps"] == 2, f"differing {bad}; rule {fem_rule(fr)}")
    from moduleforge import thermal as L1
    lc = cfg["l1"]
    cal = {float(k): float(v) for k, v in lc["calibration"].items()}
    add("l1_grid_rule", dict(L1.GRID_RULE) == dict(lc["grid_rule"]), f"{L1.GRID_RULE} vs {lc['grid_rule']}")
    add("l1_calibration_table", {float(k): float(v) for k, v in L1.CALIBRATION.items()} == cal
        and L1.CALIBRATION_VERSION == lc["calibration_version"], f"{L1.CALIBRATION} {L1.CALIBRATION_VERSION}")
    add("l1_picard_tol", L1.PICARD_TOL_K == lc["picard_tol_K"], L1.PICARD_TOL_K)
    al = cfg["allocation"]
    add("allocation_file_sha256", sha256_file(ROOT / al["source"]) == al["source_sha256"], sha256_file(ROOT / al["source"]))
    f3 = read_json(ROOT / al["source"])
    want = {stratum_name(f, k): al["layouts_per_stratum"] for f, k in all_strata()}
    add("allocation_matches_f3", f3["layouts_per_stratum"] == want and f3["bound"]["ci_spec"] == cfg["bound"]["ci_spec"],
        f"f3 {f3['layouts_per_stratum'] == want}, bound {f3['bound']['ci_spec']}")
    return out


def verify_freeze() -> int:
    spec = load_spec()
    res = freeze_checks(spec["config"])
    cm = [c.get("path") for c in spec.get("code_must_match", []) if c.get("objective") == "O007"]
    res.append({"name": "code_must_match_O007", "passed": spec["config"]["thermal_fem_path"] in cm
                and "O007" in spec.get("requires_passed", []), "detail": f"{cm} {spec.get('requires_passed')}"})
    cut = spec.get("code_under_test", [])
    res.append({"name": "code_under_test_covers_freeze", "passed": all(
        any(Path(f).match(g) or f == g for g in cut) for f in spec["config"]["freeze"]["files"]
        if f.startswith("src/")), "detail": str(cut)})
    for r in res:
        print(("OK   " if r["passed"] else "FAIL ") + r["name"] + "  " + r["detail"][:160])
    return 0 if all(r["passed"] for r in res) else 1


# ------------------------------------------------------------------------------------------------ sample (sealed)
def sub_seed(seed: int, stream: str, *idx: int) -> int:
    """A 32-bit seed for one stream of the sealed seed (numpy SeedSequence; streams never share state)."""
    return int(np.random.SeedSequence([int(seed), STREAMS[stream], *[int(i) for i in idx]]).generate_state(1)[0])


_LAY_CACHE: dict = {}


def layout_list(seed: int, family: str, k: int, s: float, n: int) -> list:
    """generate_layouts(n, seed, family, k, die_size_mm=s); prefix-stable in n (one sequential stream)."""
    key = (seed, family, k, s)
    have = _LAY_CACHE.get(key, [])
    if len(have) < n:
        from moduleforge.generate.halfbridge import generate_layouts
        have = generate_layouts(n, seed, family=family, dies_per_switch=k, die_size_mm=s)
        _LAY_CACHE[key] = have
    return have[:n]


def desc(seed: int, f: str, k: int, s: float, i: int, role: str, name: str) -> dict:
    lay = layout_list(seed, f, k, s, i + 1)[i]
    return {"name": name, "family": f, "dies": k, "stratum": stratum_name(f, k), "die_size_mm": s, "seed": seed,
            "index": i, "role": role, "fingerprint": lay.fingerprint(), "n_dies": len(lay.dies)}


def get_layout(d: dict):
    lay = layout_list(d["seed"], d["family"], d["dies"], d["die_size_mm"], d["index"] + 1)[d["index"]]
    if lay.fingerprint() != d["fingerprint"]:
        raise RuntimeError(f"{d['name']}: regenerated fingerprint differs: refusing to continue")
    return lay


def build_sample(cfg: dict, seed: int, mode: str, m: int | None = None) -> dict:
    """Every layout, pool, subset and order of the run from the seed alone, before any solve. ``mode``: 'sealed' (die
    sizes drawn per stratum with draw_die_size_mm from the sealed stream) or 'dev' (die sizes from config.dev)."""
    from moduleforge.generate.halfbridge import draw_die_size_mm
    m = int(m or cfg["allocation"]["layouts_per_stratum"])
    f7c = cfg["f7"]
    out: dict = {"seed_role": mode, "layouts_per_stratum": m, "strata": {}, "f7_pools": [], "l2_subset": [],
                 "sub_seeds": {}}
    ss = out["sub_seeds"]  # every stream seed derived from the seed, recorded and checked (sealed_seeds_fresh)
    ss["f7_strata"], ss["l2_subset"] = sub_seed(seed, "f7_strata"), sub_seed(seed, "l2_subset")
    ss["timing_order"] = sub_seed(seed, "timing_order")
    for si, (f, k) in enumerate(all_strata()):
        sn = stratum_name(f, k)
        ss[f"die_size:{sn}"] = sub_seed(seed, "die_size", si)
        if mode == "sealed":
            s = float(draw_die_size_mm(np.random.default_rng(ss[f"die_size:{sn}"])))
        else:
            s = float(cfg["dev"]["die_size_mm"][sn])
        ls = sub_seed(seed, "layouts", si)
        out["sub_seeds"][f"layouts:{sn}"] = ls
        pref = desc(cfg["seeds"]["pref_dev_seed"], f, k, s, 0, "pref_dev", f"{f}_{k}_pref")
        judged = [desc(ls, f, k, s, i, "judged", f"{f}_{k}_j{i:02d}") for i in range(m)]
        out["strata"][sn] = {"family": f, "dies": k, "band": band_of(k), "die_size_mm": s, "pref_layout": pref,
                             "judged": judged}
    if mode == "sealed" or cfg["dev"].get("f7", False):
        rng = np.random.default_rng(ss["f7_strata"])
        for ci, (f, b) in enumerate(cells()):
            ks = list(BANDS[b])
            chosen = [int(x) for x in rng.choice(ks, size=f7c["pools_per_cell"], replace=False)]
            for j, k in enumerate(chosen):
                sn = stratum_name(f, k)
                ps = sub_seed(seed, "f7", ci, j)
                out["sub_seeds"][f"f7:{f}/{b}/{j}"] = ps
                s = out["strata"][sn]["die_size_mm"]
                out["f7_pools"].append({"cell": f"{f}/{b}", "pool": j, "stratum": sn, "draws": [
                    desc(ps, f, k, s, i, "f7_draw", f"{f}_{k}_f7p{j}_d{i:02d}") for i in range(int(f7c["draws_per_pool"]))]})
    if mode == "sealed" or cfg["dev"].get("l2_subset", False):
        rng = np.random.default_rng(ss["l2_subset"])
        for f, b in cells():
            k = int(rng.choice(list(BANDS[b])))
            idx = sorted(int(i) for i in rng.choice(m, size=int(cfg["f1"]["subset_layouts_per_cell"]), replace=False))
            out["l2_subset"].append({"cell": f"{f}/{b}", "stratum": stratum_name(f, k),
                                     "layouts": [out["strata"][stratum_name(f, k)]["judged"][i]["name"] for i in idx]})
    jobs = [(d["name"], ld) for st in out["strata"].values() for d in st["judged"] for ld in cfg["loads"]]
    perm = np.random.default_rng(ss["timing_order"]).permutation(len(jobs))
    out["timing_order"] = [list(jobs[i]) for i in perm]
    out["sha256"] = sha256_obj({k: v for k, v in out.items() if k != "sha256"})
    return out


def all_descs(sample: dict) -> dict[str, dict]:
    d = {}
    for st in sample["strata"].values():
        d[st["pref_layout"]["name"]] = st["pref_layout"]
        for x in st["judged"]:
            d[x["name"]] = x
    for p in sample["f7_pools"]:
        for x in p["draws"]:
            d[x["name"]] = x
    return d


def seed_checks(cfg: dict, seed: int, sample: dict, mode: str) -> dict:
    forb = {int(v) for v in cfg["seeds"]["forbidden"]}
    subs = set(sample["sub_seeds"].values())
    streams = sorted({k.split(":")[0] for k in sample["sub_seeds"]})
    ok = mode != "sealed" or (seed not in forb and not (subs & forb) and set(streams) == set(STREAMS))
    return {"name": "sealed_seeds_fresh", "passed": ok, "value": float(len(subs & forb) + (seed in forb)),
            "detail": f"mode {mode}; seed in forbidden list: {seed in forb}; {len(sample['sub_seeds'])} derived seeds "
                      f"of streams {streams} (all {sorted(STREAMS)}: {set(streams) == set(STREAMS)}), in it: "
                      f"{sorted(subs & forb)}; forbidden {sorted(forb)}"}


def sample_checks(cfg: dict, sample: dict, mode: str) -> list[dict]:
    out = []
    m = sample["layouts_per_stratum"]
    st = sample["strata"]
    cells_ok = all(any(st[stratum_name(f, k)]["judged"] for k in BANDS[b]) for f, b in cells())
    alloc_ok = len(st) == 15 and all(len(v["judged"]) == m for v in st.values()) and cells_ok
    if mode == "sealed":
        alloc_ok = alloc_ok and m == cfg["allocation"]["layouts_per_stratum"]
    size_ok = True
    for v in st.values():
        for d in [v["pref_layout"], *v["judged"]]:
            lay = get_layout(d)
            size_ok &= {(round(x.w * 1e3, 6), round(x.h * 1e3, 6)) for x in lay.dies} == {(v["die_size_mm"],) * 2}
    out.append({"name": "allocation_fixed", "passed": alloc_ok and size_ok, "value": float(m), "detail":
                f"{len(st)} strata x {m} layouts, every (family, band) cell drawn {cells_ok}, one die size per stratum "
                f"{size_ok}: {{{', '.join(f'{k}: {v['die_size_mm']}' for k, v in st.items())}}}"})
    d = all_descs(sample)
    fps = [x["fingerprint"] for x in d.values()]
    judged_fp = {x["fingerprint"] for v in st.values() for x in v["judged"]}
    pref_fp = {v["pref_layout"]["fingerprint"] for v in st.values()}
    c004 = set(cfg["c004"]["dev_fingerprints"]) | set(cfg["c004"]["fresh_fingerprints"])
    dev_seen = set(cfg["c004"].get("other_dev_fingerprints", []))
    nonpref = [x["fingerprint"] for x in d.values() if x["role"] != "pref_dev"]
    f7_fp = {x["fingerprint"] for x in d.values() if x["role"] == "f7_draw"}
    seen = c004 | dev_seen | pref_fp
    ok = len(set(nonpref)) == len(nonpref) and not (set(nonpref) & seen)
    out.append({"name": "layouts_distinct_and_unseen", "passed": ok, "value": float(len(fps)), "detail":
                f"{len(nonpref)} judged/F7 fingerprints, distinct {len(set(nonpref)) == len(nonpref)}; judged / F7 draws "
                f"in C004's dev/fresh {len(judged_fp & c004)} / {len(f7_fp & c004)}, in other dev sets "
                f"{len(judged_fp & dev_seen)} / {len(f7_fp & dev_seen)}, equal to a P_ref development layout "
                f"{len(judged_fp & pref_fp)} / {len(f7_fp & pref_fp)}"})
    sub = sample["l2_subset"]
    sub_ok = mode != "sealed" or (len(sub) == 6 and all(len(c["layouts"]) >= 2 for c in sub))
    out.append({"name": "subset_frozen_before_solves", "passed": sub_ok, "value": float(len(sub)), "detail":
                f"plan sha256 {sample['sha256'][:16]} written before the first solve; subset {sub}"})
    return out


# ------------------------------------------------------------------------------------------------ reference jobs
def _bottom_mean(r, area: float) -> float:
    """Mean baseplate-bottom temperature: exact integral of the Q1 interpolant over z = 0 (research/o002_f1)."""
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
    return float(np.trapezoid(np.trapezoid(T, y, axis=1), x) / ((x[-1] - x[0]) * (y[-1] - y[0])))


def _fake_field(lay, P, level: int, cfg: dict) -> tuple[np.ndarray, np.ndarray]:
    """Selftest stand-in: per-die rise from self-heating, distance-decaying coupling and a k(T)-like 2 % per 60 K
    stiffening, plus a level error halving per level. Never evidence."""
    Tc, h = cfg["coolant_K"], cfg["h_W_m2K"]
    A = float(lay.baseplate_outline.area)
    c = np.array([[d.cx, d.cy] for d in lay.dies])
    s = lay.dies[0].w
    dist = np.hypot(*(c[:, None, :] - c[None, :, :]).transpose(2, 0, 1)) / s
    K = np.where(dist > 0, 0.25 / (1.0 + dist ** 2), 1.0)
    rise = (K @ P) * 0.62 * (5e-3 / s) ** 1.3
    rise = rise * (1.0 + 0.02 * rise / 60.0) + 0.04 * (2.0 ** -level) * (1 + 0.1 * np.arange(len(P)))
    tj = Tc + P.sum() / (h * A) + rise
    return tj, tj + 2.0 + 0.5 * np.cos(np.arange(len(P))) + 0.1 * 2.0 ** -level


def child_solve(job: dict, cfg: dict) -> dict:
    lay = get_layout(job["layout"])
    P = np.full(len(lay.dies), float(job["power_W"]))
    area = float(lay.baseplate_outline.area)
    Tc, h = cfg["coolant_K"], cfg["h_W_m2K"]
    t0, c0 = time.time(), time.process_time()
    if FAKE:
        tj, tmax = _fake_field(lay, P, job["level"], cfg)
        rec = {"tj_mean": tj.tolist(), "tj_max": tmax.tolist(), "energy_balance": 1e-13, "q_in_W": float(P.sum()),
               "q_out_W": float(P.sum()), "tb_trapz_K": Tc + P.sum() / (h * area), "dofs": int(70000 * 8 ** job["level"]),
               "picard_iters": 4, "picard_residual_K": 1e-5, "cg_hit_maxiter": False, "cg_max_iterations": 50,
               "amg_gs_sweeps": cfg["fem_rule"]["amg_gs_sweeps"], "fake": True}
    else:
        from moduleforge.solvers import thermal_fem as FEM
        r = FEM.solve_layout(lay, P, h, Tc, rule=fem_rule(cfg["fem_rule"]), level=int(job["level"]))
        mm = r.meta
        if mm.get("amg_gs_sweeps") != cfg["fem_rule"]["amg_gs_sweeps"]:
            raise RuntimeError(f"{job['key']}: amg_gs_sweeps {mm.get('amg_gs_sweeps')} != frozen: refusing")
        rec = {"tj_mean": [float(v) for v in r.tj_mean], "tj_max": [float(v) for v in r.tj_max],
               "energy_balance": float(r.energy_balance), "q_in_W": float(mm["q_in_W"]), "q_out_W": float(mm["q_out_W"]),
               "tb_trapz_K": _bottom_mean(r, area), "dofs": int(r.dofs), "picard_iters": int(r.picard_iters),
               "picard_residual_K": float(r.picard_residual), "cg_hit_maxiter": bool(mm["cg_hit_maxiter"]),
               "cg_max_iterations": int(mm["cg_max_iterations"]), "amg_gs_sweeps": mm["amg_gs_sweeps"], "fake": False}
    rec.update({"tb_flux_K": Tc + rec["q_out_W"] / (h * area), "wall_s": time.time() - t0,
                "cpu_s": time.process_time() - c0})
    return rec


def child_calibrate(job: dict, cfg: dict) -> dict:
    """C004's rule (e009_run.calibrate_power): equal power per die from level-0 solves so that the hottest node of the
    stratum's development layout rises target +/- calibration_tol above the coolant (p <- p target / rise)."""
    tgt, tol, Tc = cfg["target_rise_K"], cfg["calibration_tol_K"], cfg["coolant_K"]
    p, hist = float(cfg["power_start_W"]), []
    for _ in range(int(cfg["calibration_max_iters"])):
        rec = child_solve({**job, "power_W": p, "level": 0}, cfg)
        rise = float(max(rec["tj_max"]) - Tc)
        hist.append({"power_W": p, "rise_K": rise, "energy_balance": rec["energy_balance"],
                     "cg_hit_maxiter": rec["cg_hit_maxiter"], "picard_residual_K": rec["picard_residual_K"],
                     "dofs": rec["dofs"], "wall_s": rec["wall_s"], "cpu_s": rec["cpu_s"]})
        if abs(rise - tgt) <= tol:
            return {"power_W": p, "rise_K": rise, "history": hist, "level0": rec}
        p *= tgt / rise
    raise RuntimeError(f"{job['key']}: calibration did not reach {tgt} +/- {tol} K ({hist}); refusing to return a power")


def run_child(job_path: Path) -> int:
    job = read_json(job_path)
    cfg = job["cfg"]
    rec = child_calibrate(job, cfg) if job["kind"] == "calibrate" else child_solve(job, cfg)
    rec.update({"key": job["key"], "kind": job["kind"], "fingerprint": job["layout"]["fingerprint"],
                "level": job.get("level"), "power_W": rec.get("power_W", job.get("power_W")),
                "thermal_fem_sha256": sha256_file(ROOT / cfg["thermal_fem_path"]),
                "fem_rule_sha256": sha256_obj(cfg["fem_rule"]), "host": platform.node(), "platform": platform.platform(),
                "peak_rss_GB": peak_rss_gb(), "fake": FAKE, "status": "ok"})
    write_json(Path(job["out"]), rec)
    return 0


class Jobs:
    """Checkpointed reference jobs: one subprocess per job, its record written atomically to <workdir>/solves/<key>.json;
    a record whose job fields or code hashes differ from the job is stale (an error, never reused). Jobs start only while
    the running jobs' memory estimates fit the cap; swap above swap_stop_GB stops the run (checkpoints kept)."""

    def __init__(self, cfg: dict, workdir: Path, max_procs: int = 1, cap_gb: float | None = None, in_process: bool = False):
        self.cfg, self.dir, self.max_procs, self.in_process = cfg, workdir / "solves", max_procs, in_process
        self.dir.mkdir(parents=True, exist_ok=True)
        self.cap_gb = float(cap_gb if cap_gb is not None else cfg["compute"]["local_cap_GB"])
        self.new = 0
        self.records: dict[str, dict] = {}

    def est_gb(self, job: dict) -> float:
        if FAKE:
            return 0.1
        from moduleforge.solvers import thermal_fem as FEM
        lv = 0 if job["kind"] == "calibrate" else int(job["level"])
        bpd = self.cfg["compute"]["bytes_per_dof"][str(lv)] * self.cfg["compute"]["memory_margin"]
        return (FEM.estimate_dofs(get_layout(job["layout"]), fem_rule(self.cfg["fem_rule"]), lv) * bpd / 1e9
                + self.cfg["compute"]["base_rss_GB"])

    def _valid(self, job: dict, rec: dict) -> bool:
        same = (rec.get("status") == "ok" and rec["fingerprint"] == job["layout"]["fingerprint"]
                and rec["thermal_fem_sha256"] == self.cfg["thermal_fem_sha256"]
                and rec["fem_rule_sha256"] == sha256_obj(self.cfg["fem_rule"]) and bool(rec.get("fake")) == FAKE)
        if job["kind"] == "solve":
            same = same and rec["level"] == job["level"] and math.isclose(rec["power_W"], job["power_W"], rel_tol=1e-12)
        if not same:
            raise RuntimeError(f"{job['key']}: stale checkpoint {self.dir / (job['key'] + '.json')}: remove it or use a "
                               "new work directory")
        return True

    def run(self, jobs: list[dict]) -> dict[str, dict]:
        todo = []
        for j in jobs:
            p = self.dir / f"{j['key']}.json"
            if p.exists() and self._valid(j, read_json(p)):
                self.records[j["key"]] = read_json(p)
            else:
                todo.append(j)
        est = {j["key"]: self.est_gb(j) for j in todo}
        over = [(j["key"], round(est[j["key"]], 1)) for j in todo if est[j["key"]] > self.cap_gb]
        if over and os.environ.get("E007_SKIP_OVER_CAP") == "1":  # option B: solve what fits here, resume elsewhere
            todo = [j for j in todo if est[j["key"]] <= self.cap_gb]
            self._run(todo, est)
        if over:
            raise MemoryError(f"{len(over)} jobs exceed the {self.cap_gb:.1f} GB cap (first: {over[:4]}); checkpoints kept "
                              f"in {self.dir}; resume with --workdir on a machine that fits (see --plan)")
        self._run(todo, est)
        return self.records

    def _run(self, todo: list[dict], est: dict) -> None:
        todo = sorted(todo, key=lambda j: -est[j["key"]])
        running: dict[str, tuple] = {}
        last_swap = 0.0
        while todo or running:
            for j in list(todo):
                if len(running) < self.max_procs and sum(est[k] for k in running) + est[j["key"]] <= self.cap_gb:
                    todo.remove(j)
                    jp = self.dir / f"{j['key']}.job.json"
                    write_json(jp, {**j, "cfg": self.cfg, "out": str(self.dir / f"{j['key']}.json")})
                    if self.in_process:
                        run_child(jp)
                        running[j["key"]] = (None, j, time.time())
                    else:
                        cmd = [sys.executable, str(Path(__file__).resolve()), "--child", str(jp)] + (["--fake"] if FAKE else [])
                        running[j["key"]] = (subprocess.Popen(cmd, cwd=ROOT), j, time.time())
            if not self.in_process:
                time.sleep(0.2 if FAKE else 5.0)
            if time.time() - last_swap > 30.0:
                last_swap = time.time()
                if swap_used_gb() > self.cfg["compute"]["swap_stop_GB"]:
                    for pr, _, _ in running.values():
                        if pr is not None:
                            pr.kill()
                    raise MemoryError(f"swap above {self.cfg['compute']['swap_stop_GB']} GB: stopped (checkpoints kept)")
            for k, (pr, j, t0) in list(running.items()):
                if pr is None or pr.poll() is not None:
                    if pr is not None and pr.returncode != 0:
                        raise RuntimeError(f"{k}: child exited {pr.returncode} (checkpoints kept)")
                    rec = read_json(self.dir / f"{k}.json")
                    self._valid(j, rec)
                    self.records[k] = rec
                    self.new += 1
                    del running[k]
                    log(f"  {k}: {time.time() - t0:.0f} s, {rec.get('dofs', rec.get('level0', {}).get('dofs'))} DOF, "
                        f"peak {rec['peak_rss_GB']:.2f} GB")


def cal_job(st: dict) -> dict:
    return {"key": f"cal__{st['pref_layout']['name']}", "kind": "calibrate", "layout": st["pref_layout"]}


def solve_job(d: dict, load: str, level: int, pref: dict, cfg: dict) -> dict:
    return {"key": f"{d['name']}__{load}__L{level}", "kind": "solve", "layout": d, "load": load, "level": level,
            "power_W": pref[d["stratum"]] * cfg["loads"][load]}


# ------------------------------------------------------------------------------------------------ L1 phase
def l1_eval(lay, P: float, cfg: dict, constant_k: bool = False) -> dict:
    if FAKE:
        Pv = np.full(len(lay.dies), P)
        tj, tmax = _fake_field(lay, Pv, 99, cfg)
        bias = 0.004 * (tj - tj.min()) + 0.03 * np.sin(np.arange(len(Pv)) * 1.7 + lay.dies[0].cx * 1e3)
        if constant_k:
            bias = bias + 0.06 * (tj - cfg["coolant_K"]) / 6.0
        return {"tj_mean": (tj + bias).tolist(), "tj_max": (tmax - 0.5).tolist(), "wall_s": 0.3 + 0.01 * len(Pv),
                "energy_balance": 1e-14, "fake": True}
    from moduleforge import thermal as L1
    r = L1.evaluate(lay, P, h=cfg["h_W_m2K"], T_c=cfg["coolant_K"], constant_k=constant_k)
    return {"tj_mean": [float(v) for v in r.tj_mean], "tj_max": [float(v) for v in r.tj_max], "wall_s": float(r.wall_s),
            "energy_balance": float(r.energy_balance), "picard_iters": int(r.picard_iters), "fake": False}


def run_l1_phase(spec_path: Path) -> int:
    """All L1 evaluations in this one process (thread variables 1, set by the parent before Python started): one
    warm-up evaluation (not counted), the judged evaluations in the sealed timing order (A5); then, untimed for A5,
    the constant-k ablation (F4), the F7 pools at P_ref, the F7 selection (f7_select) and the optimised layouts at
    every other load. Every L1 evaluation of the run happens here."""
    jp = read_json(spec_path)
    cfg = jp["cfg"]
    descs, pref = jp["descs"], jp["pref"]
    out: dict = {"threads_env": {k: os.environ.get(k) for k in THREAD_VARS}, "judged": {}, "constant_k": {}, "f7": {},
                 "f7_other_loads": {}, "fake": FAKE}
    w = descs[jp["warmup"]]
    l1_eval(get_layout(w), pref[w["stratum"]], cfg)
    for name, load in jp["timing_order"]:
        d = descs[name]
        out["judged"][f"{name}__{load}"] = l1_eval(get_layout(d), pref[d["stratum"]] * cfg["loads"][load], cfg)
    for name, load in jp["timing_order"]:
        d = descs[name]
        out["constant_k"][f"{name}__{load}"] = l1_eval(get_layout(d), pref[d["stratum"]] * cfg["loads"][load], cfg, True)
    for p in jp["f7_pools"]:
        for name in p["draws"]:
            d = descs[name]
            out["f7"][name] = l1_eval(get_layout(d), pref[d["stratum"]], cfg)
    out["f7_optimised"] = f7_select(jp["f7_pools"], out["f7"])
    for name in out["f7_optimised"].values():
        d = descs[name]
        for load, fac in cfg["loads"].items():
            if load != "P_ref":
                out["f7_other_loads"][f"{name}__{load}"] = l1_eval(get_layout(d), pref[d["stratum"]] * fac, cfg)
    out["cpu_s"], out["peak_rss_GB"] = time.process_time(), peak_rss_gb()
    out["host"] = {"node": platform.node(), "platform": platform.platform(), "machine": platform.machine(),
                   "processor": platform.processor()}
    write_json(Path(jp["out"]), out)
    return 0


def pool_key(p: dict) -> str:
    return f"{p['cell']}/{p['pool']}"


def f7_select(pools: list[dict], f7_l1: dict) -> dict[str, str]:
    """F7's frozen rule: per pool, the draw with the lowest L1 hottest-die average (max over dies of L1's die average) at
    P_ref; ties to the lowest draw index (np.argmin)."""
    return {pool_key(p): p["draws"][int(np.argmin([max(f7_l1[x]["tj_mean"]) for x in p["draws"]]))] for p in pools}


def l1_phase(cfg: dict, workdir: Path, sample: dict, pref: dict, in_process: bool) -> dict:
    out = workdir / "l1_phase.json"
    descs = all_descs(sample)
    jp = {"cfg": cfg, "descs": descs, "pref": pref, "timing_order": sample["timing_order"], "out": str(out),
          "warmup": next(iter(sample["strata"].values()))["pref_layout"]["name"],
          "f7_pools": [{"cell": p["cell"], "pool": p["pool"], "draws": [x["name"] for x in p["draws"]]}
                       for p in sample["f7_pools"]]}
    phys = {k: cfg[k] for k in ("coolant_K", "h_W_m2K", "loads")} | {"l1": {k: v for k, v in cfg["l1"].items()
                                                                          if k not in ("timing", "freeze_note")}}
    key = sha256_obj({**{k: v for k, v in jp.items() if k not in ("out", "cfg")}, "cfg_l1": phys})
    if out.exists() and read_json(out).get("key") == key:
        return read_json(out)
    write_json(workdir / "l1_phase.job.json", jp)
    if in_process:
        run_l1_phase(workdir / "l1_phase.job.json")
    else:
        env = {**os.environ, **{k: "1" for k in THREAD_VARS}}
        rc = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--l1-phase", str(workdir / "l1_phase.job.json")]
                            + (["--fake"] if FAKE else []), cwd=ROOT, env=env).returncode
        if rc != 0:
            raise RuntimeError(f"L1 phase exited {rc}")
    res = read_json(out)
    res["key"] = key
    write_json(out, res)
    return res


# ------------------------------------------------------------------------------------------------ null (a): isolated die
def isolated_die_null(lay, P: float, cfg: dict) -> np.ndarray:
    """F2 null (a): each die alone (no other die heated: no inter-die coupling) on the laterally uniform five-layer
    substrate over the baseplate rectangle (solvers.thermal_series.box_series, constant k at config temperature), plus
    the 1D series resistance of die and attach over the die area, on top of the exact mean baseplate-bottom temperature
    of the full layout (global energy balance). Die-size aware through the source size; layout-ignorant otherwise."""
    from moduleforge.solvers.thermal_series import box_series
    nc = cfg["nulls"]["isolated_die"]
    Tk, Tc, h = nc["k_at_K"], cfg["coolant_K"], cfg["h_W_m2K"]
    x0, y0, x1, y1 = lay.baseplate_outline.bounds
    a, b = x1 - x0, y1 - y0
    if abs(a * b - float(lay.baseplate_outline.area)) > 1e-12:
        raise ValueError("isolated-die null needs a rectangular baseplate")
    st = lay.stack
    layers = [(la.thickness, la.k_at(Tk)) for la in st.layers]
    n = len(lay.dies)
    t_bp = Tc + n * P / (h * a * b)
    out = []
    for d in lay.dies:
        bx0, by0, bx1, by1 = d.bounds
        if FAKE:
            local = P * 0.55 * (5e-3 / d.w) ** 1.3
        else:
            r = box_series(a, b, layers, [(bx0 - x0, bx1 - x0, by0 - y0, by1 - y0, P)], h=h, T_c=Tc,
                           n_modes=int(nc["n_modes"]))
            local = r["src0.tj_mean"] - (Tc + P / (h * a * b))
        r1d = d.attach_thickness / st.die_attach.k_at(Tk) + d.thickness / st.die.k_at(Tk)
        out.append(t_bp + local + P * r1d / (d.w * d.h))
    return np.asarray(out)


# ------------------------------------------------------------------------------------------------ rows
def die_rows_for(d: dict, lay, load: str, ref: dict, l1: dict, l1k: dict, iso: np.ndarray, role_kind: str = "die") -> list:
    rows, seen = [], {}
    for i, die in enumerate(lay.dies):
        di = seen.get(die.switch, 0)
        seen[die.switch] = di + 1
        tb = ref["tb_flux_K"]
        rows.append({"kind": role_kind, "layout": d["name"], "family": d["family"], "dies": d["dies"],
                     "stratum": d["stratum"], "band": band_of(d["dies"]), "die_size_mm": d["die_size_mm"], "load": load,
                     "switch": die.switch, "die_index": di, "tj_ref_K": ref["tj_mean"][i], "tj_l1_K": l1["tj_mean"][i],
                     "tb_ref_K": tb, "rise_ref_K": ref["tj_mean"][i] - tb, "tj_max_ref_K": ref["tj_max"][i],
                     "tj_max_l1_K": l1["tj_max"][i], "tj_l1_constk_K": l1k["tj_mean"][i] if l1k else float("nan"),
                     "null_iso": float(iso[i]) if iso is not None else float("nan")})
    return rows


def add_lolo_nulls(die_rows: list) -> None:
    """F2 nulls (c) die position: mean tj_ref_K of the other layouts at the same (family, dies, load, switch, die_index);
    (d) stratum mean: mean tj_ref_K of every die of the same switch in the other layouts of (family, dies, load, switch).
    Both leave-one-layout-out."""
    for col, key in (("null_pos", ("family", "dies", "load", "switch", "die_index")),
                     ("null_smean", ("family", "dies", "load", "switch"))):
        groups: dict = {}
        for r in die_rows:
            groups.setdefault(tuple(r[c] for c in key), []).append(r)
        for rs in groups.values():
            by_lay: dict = {}
            for r in rs:
                by_lay.setdefault(r["layout"], []).append(r["tj_ref_K"])
            if len(by_lay) < 2:
                raise ValueError(f"{col}: fewer than 2 layouts in {key}")
            tot, cnt = sum(sum(v) for v in by_lay.values()), sum(len(v) for v in by_lay.values())
            for r in rs:
                own = by_lay[r["layout"]]
                r[col] = (tot - sum(own)) / (cnt - len(own))


def assemble(die_rows: list, l1_wall: dict) -> tuple[list, list]:
    """Layout and switch rows through e007_metrics.layout_rows / switch_rows (the n5 helpers), with every null and the
    constant-k ablation taken at the reference's hottest die (layout rows) or as a spread (switch rows)."""
    lay_rows = EM.layout_rows(die_rows)
    sw_rows = EM.switch_rows(die_rows)
    lk = {(r["layout"], r["load"]): r for r in lay_rows}
    sk = {(r["layout"], r["load"], r["switch"]): r for r in sw_rows}
    for col in ("null_pos", "null_smean", "null_iso", "tj_l1_constk_K"):
        for r in EM.layout_rows(die_rows, l1=col):
            lk[(r["layout"], r["load"])][col] = r["tj_hot_l1_K"]
        for r in EM.switch_rows(die_rows, l1=col):
            sk[(r["layout"], r["load"], r["switch"])][col] = r["spread_l1_K"]
    first = {}
    for r in die_rows:
        first.setdefault(r["layout"], r)
    for r in sw_rows:
        r["null_smean"] = r["spread_null_K"]  # (d) for spreads: the stratum-mean spread, per switch, leave-one-out
        r["stratum"], r["band"] = first[r["layout"]]["stratum"], first[r["layout"]]["band"]
    for r in lay_rows:
        r["l1_eval_s"] = float(l1_wall[(r["layout"], r["load"])])
        r["stratum"], r["band"] = first[r["layout"]]["stratum"], first[r["layout"]]["band"]
        r["die_size_mm"] = first[r["layout"]]["die_size_mm"]
    return lay_rows, sw_rows


GEOMETRY_COLUMNS = ("cx", "cy", "x", "y", "w", "h", "bounds", "fingerprint", "polygon")


def rows_contract(die_rows: list, lay_rows: list, sw_rows: list) -> dict:
    """The row contract, re-derived independently of the helpers: the reference's hottest die by its die average (ties:
    first in (switch, die_index) order), L1 at that die, own-hottest L1, spreads; finiteness; rise > 0; at least 2
    layouts per (stratum, load, switch); one stratum per layout; no geometry columns (F5)."""
    probs = []
    by: dict = {}
    for r in die_rows:
        by.setdefault((r["layout"], r["load"]), []).append(r)
    for r in lay_rows:
        rs = sorted(by[(r["layout"], r["load"])], key=lambda x: (str(x["switch"]), int(x["die_index"])))
        vals = [x["tj_ref_K"] for x in rs]
        hot = vals.index(max(vals))
        if (rs[hot]["switch"], rs[hot]["die_index"]) != (r["hot_switch"], r["hot_die_index"]) \
                or r["tj_hot_l1_K"] != rs[hot]["tj_l1_K"] or r["tj_hot_ref_K"] != rs[hot]["tj_ref_K"] \
                or r["tj_ownhot_l1_K"] != max(x["tj_l1_K"] for x in rs):
            probs.append(f"hottest die of {r['layout']}/{r['load']}")
    for r in sw_rows:
        rs = [x for x in by[(r["layout"], r["load"])] if x["switch"] == r["switch"]]
        for col, src in (("spread_ref_K", "tj_ref_K"), ("spread_l1_K", "tj_l1_K")):
            v = [x[src] for x in rs]
            if not math.isclose(r[col], max(v) - min(v), abs_tol=1e-12):
                probs.append(f"{col} of {r['layout']}/{r['load']}/{r['switch']}")
    for rows, cols in ((die_rows, ("tj_ref_K", "tj_l1_K", "rise_ref_K", "null_pos", "null_smean", "null_iso")),
                       (lay_rows, ("tj_hot_ref_K", "tj_hot_l1_K", "tj_ownhot_l1_K", "l1_eval_s", "null_pos",
                                   "null_smean", "null_iso")),
                       (sw_rows, ("spread_ref_K", "spread_l1_K", "spread_null_K", "null_pos", "null_smean", "null_iso"))):
        for r in rows:
            if not all(isinstance(r.get(c), (int, float)) and math.isfinite(r[c]) for c in cols):
                probs.append(f"non-finite in {r['kind']} {r['layout']}")
                break
            if any(c in r for c in GEOMETRY_COLUMNS):
                probs.append(f"geometry column in {r['kind']} {r['layout']}")
                break
    if any(r["rise_ref_K"] <= 0 for r in die_rows):
        probs.append("rise_ref_K <= 0")
    cnt: dict = {}
    for r in sw_rows:
        cnt.setdefault((r["stratum"], r["load"], r["switch"]), set()).add(r["layout"])
    if any(len(v) < 2 for v in cnt.values()):
        probs.append("a (stratum, load, switch) with fewer than 2 layouts")
    strata_of: dict = {}
    for r in die_rows:
        strata_of.setdefault(r["layout"], set()).add(r["stratum"])
    if any(len(v) != 1 for v in strata_of.values()):
        probs.append("a layout in more than one stratum")
    return {"name": "rows_contract", "passed": not probs, "value": float(len(probs)), "detail": "; ".join(probs[:20])}


# ------------------------------------------------------------------------------------------------ metrics
def recompute_entries(spec: dict) -> list[dict]:
    return [e for e in spec.get("recompute", [])]


def _where(rows: list, where: dict) -> list:
    return [r for r in rows if all(r.get(k) == v for k, v in where.items())]


def quantile_ci(fn, rows, **kw):
    """The bound F3 selected (V4): mfos.metrics.quantile_ci once e007_metrics.patch is applied, else the identical
    draft in research/o002_e007/e007_metrics.py (the patch copies it verbatim; the selftest compares the two)."""
    import mfos.metrics as mx
    f = getattr(mx, "quantile_ci", None) or EM.quantile_ci
    return f(fn, rows, **kw)


def metric_with_bound(rows: list, e: dict, level: float) -> tuple[float, tuple[float, float] | None, int]:
    from mfos.metrics import compute
    sub = _where(rows, e.get("where", {}))
    point = compute(e["fn"], sub, pred=e.get("pred"), ref=e.get("ref"), strata=e.get("strata", []),
                    params=e.get("params", {}))
    if e["fn"] == "median_col":
        v = np.sort([r[e["pred"]] for r in sub])
        n = v.size  # distribution-free A5_CI_LEVEL interval for the median: binomial order statistics
        from scipy.stats import binom
        k = int(binom.ppf((1.0 - A5_CI_LEVEL) / 2.0, n, 0.5))
        return point, (float(v[max(k - 1, 0)]), float(v[min(n - k, n - 1)])), n
    _, ci = quantile_ci(e["fn"], sub, pred=e.get("pred"), ref=e.get("ref"), strata=e.get("strata", []),
                        params=e.get("params", {}), level=level, cluster="layout")
    return point, ci, len(sub)


def entries_for(pred_map: dict, spec: dict) -> list[dict]:
    """Copies of the spec's recompute entries with pred columns replaced (nulls, ablation)."""
    out = []
    for e in recompute_entries(spec):
        if e["fn"] == "median_col":
            continue
        p = pred_map.get(e["pred"])
        if p is not None:
            out.append({**e, "pred": p})
    return out


def per_load(e: dict, load: str) -> dict:
    if e["fn"] != "max_over_groups":
        return {**e, "where": {**e["where"], "load": load}}
    return {**e, "fn": e["params"]["fn"], "params": e["params"].get("inner", {}), "where": {**e["where"], "load": load}}


def all_metrics(rows: list, spec: dict, cfg: dict, loads: list[str]) -> tuple[dict, dict]:
    """(metrics {name: (value, ci, n)}, reports {...}) on the judged rows."""
    lev = float(cfg["bound"]["ci_spec"]["level"])
    met: dict = {}
    E = {e["metric"]: e for e in recompute_entries(spec)}
    for name, e in E.items():
        met[name] = metric_with_bound(rows, e, lev)
    A1, A2, A3, A4 = (cfg["metric_names"][k] for k in ("A1", "A2", "A3", "A4"))
    for ld in loads:
        for nm in (A1, A2, A3):
            met[f"{nm.removesuffix('_max_load')}_{ld}"] = metric_with_bound(rows, per_load(E[nm], ld), lev)
    rep: dict = {"per_stratum_A2": {}, "per_band_A4": {}, "nulls": {}, "f4_constant_k": {}}
    for sn in sorted({r["stratum"] for r in rows if r["kind"] == "die"}):  # F3 rule: A2 per (family, dies) stratum
        sub = [r for r in rows if r.get("stratum") == sn]
        v, ci, n = metric_with_bound(sub, E[A2], lev)
        smax = max(abs(r["tj_l1_K"] - r["tj_ref_K"]) / r["rise_ref_K"] for r in sub if r["kind"] == "die")
        # 20 layouts: the one-sided 97 % Woodruff bound on a p95 often reaches the stratum maximum or +inf (q + c se
        # >= 1; review T0436): reported with this flag, never read as a precise per-stratum bound
        rep["per_stratum_A2"][sn] = {"value": v, "ci": ci, "n": n, "stratum_max": smax,
                                     "upper_informative": bool(math.isfinite(ci[1]) and ci[1] < smax)}
    rep["per_stratum_A2_n_upper_infinite"] = sum(not math.isfinite(x["ci"][1]) for x in rep["per_stratum_A2"].values())
    rep["per_stratum_A2_n_upper_informative"] = sum(x["upper_informative"] for x in rep["per_stratum_A2"].values())
    for b in BANDS:  # F3 rule: A4 per die-count band, at P_ref
        sub = [r for r in rows if r.get("band") == b]
        v, ci, n = metric_with_bound(sub, E[A4], lev)
        rep["per_band_A4"][b] = {"value": v, "ci": ci, "n": n}
        met[f"a4_ratio_band_{b.replace('-', '_')}"] = (v, ci, n)
    rep["max_per_stratum_A2"] = max(x["value"] for x in rep["per_stratum_A2"].values())
    rep["diversity"] = {}  # how different the layouts of a stratum are, by the reference itself (P_ref)
    for sn in sorted({r["stratum"] for r in rows if r["kind"] == "layout"}):
        lr = [r for r in rows if r["kind"] == "layout" and r["stratum"] == sn and r["load"] == "P_ref"]
        rep["diversity"][sn] = {"sd_tj_hot_ref_K": float(np.std([r["tj_hot_ref_K"] for r in lr], ddof=1)),
                                "n_distinct_hot_die": len({(r["hot_switch"], r["hot_die_index"]) for r in lr}),
                                "n_layouts": len(lr)}
    met["diversity_min_sd_tj_hot_ref_K"] = (min(v["sd_tj_hot_ref_K"] for v in rep["diversity"].values()), None, None)
    crit = objective_criteria(spec)
    thr_of = {c["metric"].partition(".")[2]: c for c in crit["pass_all"]}
    nb = {n["name"]: n for n in spec.get("null_baselines", [])}
    for nul, col in (("die_position", "null_pos"), ("stratum_mean", "null_smean"), ("isolated_die", "null_iso")):
        r0: dict = {"column": col, "per_stratum_P_ref": {}, "applies_to": list(nb.get(nul, {}).get("applies_to", [])),
                    "evaluator_view": {}}
        for e in entries_for({"tj_hot_l1_K": col, "tj_l1_K": col, "spread_l1_K": col}, spec):
            r0[e["metric"]] = compute_point(rows, e)  # every criterion's point, A2 and A3 included (reported)
        for mname in r0["applies_to"]:  # what mfos's evaluator does with this null (evaluate.null_values/_annotate)
            c = thr_of[mname]
            v, ci, n = metric_with_bound(rows, {**E[mname], "pred": col}, lev)
            bound = v if c["uncertainty"]["use"] == "point" else ci[1]
            r0["evaluator_view"][mname] = {"criterion": c["id"], "point": v, "ci": ci, "bound_used": bound,
                                           "threshold": c["threshold"], "meets": bool(bound <= c["threshold"])}
        e1, e2 = per_load(E[A1], "P_ref"), per_load(E[A2], "P_ref")
        r0["A1_P_ref_K"] = compute_point(rows, {**e1, "pred": col})
        r0["A1_point_K"] = r0["A1_P_ref_K"]  # T0398 packet name: A1's point estimate at P_ref
        r0["A2_P_ref"] = compute_point(rows, {**e2, "pred": col})
        r0["A3_P_ref_K"] = compute_point(rows, {**per_load(E[A3], "P_ref"), "pred": col})
        r0["A4_point"] = compute_point(rows, {**E[A4], "pred": col})
        for sn in sorted({r["stratum"] for r in rows if r["kind"] == "die"}):
            sub = [r for r in rows if r.get("stratum") == sn]
            r0["per_stratum_P_ref"][sn] = {"A1_K": compute_point(sub, {**e1, "pred": col}),
                                           "A2": compute_point(sub, {**e2, "pred": col})}
        r0["fails_A1_point"] = r0["A1_P_ref_K"] > thr_of[A1]["threshold"]  # F2: the point estimate must fail A1 ...
        r0["fails_A4_point"] = r0["A4_point"] > thr_of[A4]["threshold"]  # ... and the spread nulls' must fail A4
        rep["nulls"][nul] = r0
        met[f"null_{nul}_A1_K_P_ref"] = (r0["A1_P_ref_K"], None, None)
        met[f"null_{nul}_A2_P_ref"] = (r0["A2_P_ref"], None, None)
        met[f"null_{nul}_A4"] = (r0["A4_point"], None, None)
    rep["l1_dev_check"] = l1_dev_check(rows, cfg, E[A2], E[A4], E[A1])
    rep["implied_c_family_spread"] = implied_c_spread(rows, cfg)
    ckmap = {"tj_hot_l1_K": "tj_l1_constk_K", "tj_l1_K": "tj_l1_constk_K", "spread_l1_K": "tj_l1_constk_K"}
    tested = False  # F4 rule (spec f4_kT_tested): 1 if any constant-k POINT estimate exceeds its O002 pass threshold
    thr = {k: float(thr_of[cfg["metric_names"][k]]["threshold"]) for k in ("A1", "A2", "A3", "A4")}  # from O002
    for ld in loads:  # F4: the constant-k ablation at both loads, A1-A4 type
        for k, nm in (("A1", A1), ("A2", A2), ("A3", A3)):
            e = per_load(E[nm], ld)
            v, ci, n = metric_with_bound(rows, {**e, "pred": ckmap[e["pred"]]}, lev)
            met[f"f4_constant_k_{k}_{ld}"] = (v, ci, n)
            tested |= v > thr[k]
        e = {**E[A4], "pred": "tj_l1_constk_K", "where": {**E[A4]["where"], "load": ld}}
        v, ci, n = metric_with_bound(rows, e, lev)
        met[f"f4_constant_k_A4_{ld}"] = (v, ci, n)
        tested |= v > thr["A4"]
    met["f4_kT_tested"] = (1.0 if tested else 0.0, None, None)
    return met, rep


def compute_point(rows: list, e: dict) -> float:
    from mfos.metrics import compute
    return float(compute(e["fn"], _where(rows, e.get("where", {})), pred=e.get("pred"), ref=e.get("ref"),
                         strata=e.get("strata", []), params=e.get("params", {})))


def objective_criteria(spec: dict) -> dict:
    """O002's acceptance block (thresholds, comparators, uncertainty use), read from the objective file."""
    obj = yaml.safe_load((ROOT / "project" / "objectives" / spec["objective"] / "objective.yaml").read_text())
    return obj["acceptance"]


def l1_dev_check(rows: list, cfg: dict, eA2: dict, eA4: dict, eA1: dict | None = None) -> dict:
    """D0025 decision 4 (reported, never gated): per stratum, the implied calibration factor beside c(s)
    (c * sum(rise_ref) / sum(rise_L1), rise_L1 = tj_l1 - tb_ref: T_bp is the same exact energy-balance value in both
    models), the mean per-die bias tj_l1 - tj_ref for HS and LS dies, A2-type per load (point) against the model's
    1.8 % guard, and A4-type (point, P_ref) against 0.3."""
    cal = {float(k): float(v) for k, v in cfg["l1"]["calibration"].items()}
    out = {}
    for sn in sorted({r["stratum"] for r in rows if r["kind"] == "die"}):
        dr = [r for r in rows if r["kind"] == "die" and r["stratum"] == sn]
        c = cal[float(dr[0]["die_size_mm"])]
        rec: dict = {"die_size_mm": dr[0]["die_size_mm"], "c_table": c}
        for ld in sorted({r["load"] for r in dr}):
            x = [r for r in dr if r["load"] == ld]
            rec[f"implied_c_{ld}"] = c * sum(r["rise_ref_K"] for r in x) / sum(r["tj_l1_K"] - r["tb_ref_K"] for r in x)
            for sw in ("HS", "LS"):
                b = [r["tj_l1_K"] - r["tj_ref_K"] for r in x if r["switch"] == sw]
                rec[f"bias_{sw}_K_{ld}"] = float(np.mean(b)) if b else float("nan")
            rec[f"A2_{ld}"] = compute_point([r for r in rows if r.get("stratum") == sn], per_load(eA2, ld))
        rec["A2_max_load"] = max(v for k, v in rec.items() if k.startswith("A2_") and k != "A2_max_load")
        rec["A4_P_ref"] = compute_point([r for r in rows if r.get("stratum") == sn], eA4)
        if eA1 is not None:
            rec["A1_K_max_load"] = compute_point([r for r in rows if r.get("stratum") == sn], eA1)
        lr = [r for r in rows if r["kind"] == "layout" and r.get("stratum") == sn and "l1_eval_s" in r]
        if lr:
            rec["A5_s_p50"] = float(np.median([r["l1_eval_s"] for r in lr]))
        # A2 had L1 used this stratum's implied factor instead of c(s) (rise_L1 x implied / c): the calibration's share
        ic = rec["implied_c_P_ref"]
        rec["A2_recalibrated_max_load"] = max(float(np.quantile([abs(r["tb_ref_K"] + (r["tj_l1_K"] - r["tb_ref_K"]) * ic / c
                                                                    - r["tj_ref_K"]) / r["rise_ref_K"] for r in dr
                                                                if r["load"] == ld], 0.95)) for ld in {r["load"] for r in dr})
        rec["meets_guard_A2_0.018"] = rec["A2_max_load"] <= 0.018
        rec["meets_A4_0.3"] = rec["A4_P_ref"] <= 0.3
        out[sn] = rec
    return out


def implied_c_spread(rows: list, cfg: dict) -> dict:
    """D0025 decision 4 / T0395: per die size, the implied factor per family (pooled over that family's strata at that
    size, P_ref: c * sum rise_ref / sum rise_L1) and its spread over families (max - min; T0395: 0.0059 at 4.0 mm)."""
    cal = {float(k): float(v) for k, v in cfg["l1"]["calibration"].items()}
    out: dict = {}
    for s in sorted({float(r["die_size_mm"]) for r in rows if r["kind"] == "die"}):
        fam = {}
        for f in FAMILIES:
            x = [r for r in rows if r["kind"] == "die" and r["load"] == "P_ref" and float(r["die_size_mm"]) == s
                 and r["family"] == f]
            if x:
                fam[f] = cal[s] * sum(r["rise_ref_K"] for r in x) / sum(r["tj_l1_K"] - r["tb_ref_K"] for r in x)
        out[str(s)] = {"c_table": cal[s], "implied_by_family": fam,
                       "family_spread": (max(fam.values()) - min(fam.values())) if len(fam) > 1 else float("nan"),
                       "strata": sorted({r["stratum"] for r in rows if r["kind"] == "die" and float(r["die_size_mm"]) == s})}
    return out


def f2_check(rep: dict, spec: dict, cfg: dict) -> dict:
    """F2, gated: each null's point estimate at P_ref fails A1 (> 0.5 K) and A4 (> 0.5); a null failing only by a wide
    upper bound does not count (review T0371). Every null's applies_to is exactly A1 and A4 (O002: A3 and A5 are met by
    a layout-ignorant predictor on their own; A1 and A4 separate L1 from the nulls)."""
    A1, A4 = cfg["metric_names"]["A1"], cfg["metric_names"]["A4"]
    bad, txt = [], []
    for nul, r0 in rep["nulls"].items():
        if not (r0["fails_A1_point"] and r0["fails_A4_point"]):
            bad.append(nul)
        if sorted(r0["applies_to"]) != sorted([A1, A4]):
            bad.append(f"{nul}: applies_to {r0['applies_to']}")
        if any(v["meets"] for v in r0["evaluator_view"].values()):
            bad.append(f"{nul}: meets {[k for k, v in r0['evaluator_view'].items() if v['meets']]} at the bound")
        txt.append(f"{nul}: A1(P_ref) {r0['A1_P_ref_K']:.3f} K, A4 {r0['A4_point']:.3f}; reported A2(P_ref) "
                   f"{r0['A2_P_ref']:.4f}, A3(P_ref) {r0['A3_P_ref_K']:.3f} K")
    return {"name": "f2_null_discrimination", "passed": not bad, "value": float(len(bad)),
            "threshold": 0.0, "detail": ("; ".join(txt) + (f"; FAILING {bad}" if bad else ""))[:3900]}


def recompute_consistency(rows: list, spec: dict, met: dict) -> dict:
    """Every recompute entry of the spec recomputed exactly as the evaluator does (mfos.metrics.compute on the
    `where` rows) against the runner's value."""
    bad = []
    for e in recompute_entries(spec):
        v = compute_point(rows, e)
        if not math.isclose(v, met[e["metric"]][0], rel_tol=e.get("rel_tol", 1e-9), abs_tol=e.get("abs_tol", 1e-15)):
            bad.append(f"{e['metric']}: {met[e['metric']][0]} vs {v}")
    return {"name": "recompute_consistency", "passed": not bad, "value": float(len(bad)), "detail": "; ".join(bad) or
            f"{len(recompute_entries(spec))} entries equal"}


# ------------------------------------------------------------------------------------------------ F1, F6, F7
def f1_rows_and_checks(cfg: dict, sample: dict, recs: dict, pref: dict) -> tuple[list, list, dict]:
    """F1 on the level-2 subset (step-floor rule): rows of kind 'f1' (one per quantity with lv0, lv1, lv2), and the
    gated checks. Level-1 error = |v1 - v2| + gci_step_floor(v0, v1, v2, 0.01 K)."""
    from mfos.metrics import gci_step_floor
    f1c = cfg["f1"]
    sf = float(f1c["step_floor_K"])
    rows, worst = [], {"abs_rel": 0.0, "pair_K": 0.0, "spread_K": 0.0, "l1_l2_K": 0.0, "tjmax_gci_K": 0.0}
    descs = all_descs(sample)
    growth = []
    for c in sample["l2_subset"]:
        for ld in cfg["loads"]:
            vals = {}
            for name in c["layouts"]:
                d = descs[name]
                lay = get_layout(d)
                R = [recs[f"{name}__{ld}__L{lv}"] for lv in (0, 1, 2)]
                growth += [R[1]["dofs"] / R[0]["dofs"], R[2]["dofs"] / R[1]["dofs"]]
                sw = [x.switch for x in lay.dies]
                tj = np.array([r["tj_mean"] for r in R])
                tm = np.array([r["tj_max"] for r in R])
                rise1 = tj[1] - R[1]["tb_flux_K"]
                vals[name] = (tj, sw)
                for i in range(tj.shape[1]):
                    est = gci_step_floor(*tj[:, i], sf)
                    err = abs(tj[1, i] - tj[2, i]) + est
                    rel = err / rise1[i]
                    worst["abs_rel"] = max(worst["abs_rel"], rel)
                    gm = gci_step_floor(*tm[:, i], sf)
                    worst["tjmax_gci_K"] = max(worst["tjmax_gci_K"], gm)
                    rows.append({"kind": "f1", "quantity": "die_average", "layout": name, "load": ld, "die": i,
                                 "lv0": tj[0, i], "lv1": tj[1, i], "lv2": tj[2, i], "estimate_K": est, "error_K": err,
                                 "rise_lv1_K": rise1[i], "rel_error": rel, "pass": rel <= f1c["abs_rel_tol"]})
                    rows.append({"kind": "f1", "quantity": "hottest_node", "layout": name, "load": ld, "die": i,
                                 "lv0": tm[0, i], "lv1": tm[1, i], "lv2": tm[2, i], "estimate_K": gm})
                for s in sorted(set(sw)):
                    ix = [j for j, x in enumerate(sw) if x == s]
                    v = tj[:, ix].max(axis=1) - tj[:, ix].min(axis=1)
                    est = gci_step_floor(*v, sf)
                    err = abs(v[1] - v[2]) + est
                    worst["spread_K"] = max(worst["spread_K"], err)
                    worst["l1_l2_K"] = max(worst["l1_l2_K"], abs(v[1] - v[2]))
                    rows.append({"kind": "f1", "quantity": "spread", "layout": name, "load": ld, "switch": s,
                                 "lv0": v[0], "lv1": v[1], "lv2": v[2], "estimate_K": est, "error_K": err,
                                 "pass": err <= f1c["diff_tol_K"] and abs(v[1] - v[2]) <= f1c["l1_vs_l2_tol_K"]})
            names = c["layouts"]
            for a in range(len(names)):
                for b in range(a + 1, len(names)):
                    ta, tb_ = vals[names[a]][0], vals[names[b]][0]
                    ha, hb = int(np.argmax(ta[1])), int(np.argmax(tb_[1]))  # hottest die at the judged level, held fixed
                    v = ta[:, ha] - tb_[:, hb]
                    est = gci_step_floor(*v, sf)
                    err = abs(v[1] - v[2]) + est
                    worst["pair_K"] = max(worst["pair_K"], err)
                    worst["l1_l2_K"] = max(worst["l1_l2_K"], abs(v[1] - v[2]))
                    rows.append({"kind": "f1", "quantity": "pair_difference", "layout": names[a], "layout_b": names[b],
                                 "load": ld, "lv0": v[0], "lv1": v[1], "lv2": v[2], "estimate_K": est, "error_K": err,
                                 "pass": err <= f1c["diff_tol_K"] and abs(v[1] - v[2]) <= f1c["l1_vs_l2_tol_K"]})
    g_ok = all(abs(g / 8.0 - 1.0) <= cfg["f1"]["node_growth_tol"] for g in growth)  # no FAKE bypass (review T0436)
    checks = [
        {"name": "f1_abs_die_average", "passed": worst["abs_rel"] <= f1c["abs_rel_tol"], "value": worst["abs_rel"],
         "threshold": f1c["abs_rel_tol"], "detail": "max over subset dies and loads of level-1 error / level-1 die-local rise"},
        {"name": "f1_pair_difference", "passed": worst["pair_K"] <= f1c["diff_tol_K"], "value": worst["pair_K"],
         "threshold": f1c["diff_tol_K"], "detail": "max level-1 error of subset same-stratum pair differences (K)"},
        {"name": "f1_spread", "passed": worst["spread_K"] <= f1c["diff_tol_K"], "value": worst["spread_K"],
         "threshold": f1c["diff_tol_K"], "detail": "max level-1 error of subset per-switch spreads (K)"},
        {"name": "f1_level1_vs_level2", "passed": worst["l1_l2_K"] <= f1c["l1_vs_l2_tol_K"], "value": worst["l1_l2_K"],
         "threshold": f1c["l1_vs_l2_tol_K"], "detail": "max |level 1 - level 2| of subset pair differences and spreads"},
        {"name": "node_count_growth", "passed": g_ok and bool(growth), "value": float(max(growth, default=0.0)),
         "threshold": 8.0, "detail": f"DOF growth per level {min(growth, default=0):.2f}-{max(growth, default=0):.2f} "
                                     f"(8 +/- {cfg['f1']['node_growth_tol']:.0%})"}]
    return rows, checks, worst


def f6_report(die_rows: list, f1rows: list) -> dict:
    gap: dict = {}
    for r in die_rows:
        k = (r["stratum"], r["load"])
        gap[k] = max(gap.get(k, -math.inf), r["tj_max_ref_K"] - r["tj_ref_K"])
    per = {f"{s}|{ld}": v for (s, ld), v in sorted(gap.items())}
    est = [r["estimate_K"] for r in f1rows if r["quantity"] == "hottest_node"]
    return {"scope": "hottest node of every judged die (reference, and L1's coarse surface maximum, in the die rows); "
                     "its step-floor estimate only on the level-2 subset (12 layouts x 2 loads): levels 0 and 2 on every "
                     "layout are outside the budget (review T0435)",
            "max_gap_K_per_stratum_load": per, "max_gap_K": max(per.values()),
            "n_strata_gap_over_2K": len({s for (s, _), v in gap.items() if v > 2.0}),
            "hottest_node_estimate_K_max": max(est, default=float("nan")),
            "hottest_node_estimate_n_infinite": int(sum(1 for e in est if not math.isfinite(e)))}


def f7_report(sample: dict, l1: dict, judged_lay_rows: list, f7_lay_rows: list, cfg: dict) -> dict:
    """F7: per pool, |(L1_o - L1_r) - (ref_o - ref_r)| at the reference's hottest die for the optimised layout o against
    every random judged layout r of its stratum, at each load; reported beside A1, not gated."""
    out: dict = {"pools": [], "terms": []}
    for p in sample["f7_pools"]:
        o = p["optimised"]
        for ld in cfg["loads"]:
            ro = next(r for r in f7_lay_rows if r["layout"] == o and r["load"] == ld)
            terms = [abs((ro["tj_hot_l1_K"] - r["tj_hot_l1_K"]) - (ro["tj_hot_ref_K"] - r["tj_hot_ref_K"]))
                     for r in judged_lay_rows if r["stratum"] == p["stratum"] and r["load"] == ld]
            out["terms"] += terms
            out["pools"].append({"cell": p["cell"], "pool": p["pool"], "stratum": p["stratum"], "layout": o, "load": ld,
                                 "p95_K": float(np.quantile(terms, 0.95)), "max_K": float(max(terms)),
                                 "l1_hot_K": ro["tj_hot_l1_K"], "ref_hot_K": ro["tj_hot_ref_K"]})
    out["p95_K"] = float(np.quantile(out["terms"], 0.95)) if out["terms"] else float("nan")
    out["max_K"] = float(max(out["terms"])) if out["terms"] else float("nan")
    for ld in cfg["loads"]:
        tl = [t["p95_K"] for t in out["pools"] if t["load"] == ld]
        out[f"max_pool_p95_K_{ld}"] = max(tl) if tl else float("nan")
    del out["terms"]
    return out


# ------------------------------------------------------------------------------------------------ the run
def execute(cfg: dict, spec: dict, seed: int, mode: str, workdir: Path, *, m: int | None = None, max_procs: int = 1,
            cap_gb: float | None = None, in_process: bool = False) -> dict:
    """The whole pipeline; returns everything the reporting needs. ``mode``: 'sealed' (the registered run) or 'dev'."""
    checks = [dict(c, value=None, threshold=None) for c in freeze_checks(cfg)]
    fz = {"name": "freeze", "passed": all(c["passed"] for c in checks), "value": float(sum(not c["passed"] for c in checks)),
          "detail": "; ".join(f"{c['name']}: {'ok' if c['passed'] else 'FAIL ' + c['detail']}" for c in checks)[:3900]}
    if not fz["passed"] and not FAKE:
        raise RuntimeError(f"freeze checks failed before any solve: {fz['detail']}")
    out: dict = {"checks": [fz]}
    workdir.mkdir(parents=True, exist_ok=True)
    sample = build_sample(cfg, seed, mode, m)
    pf = workdir / "plan_frozen.json"
    if pf.exists() and read_json(pf)["sha256"] != sample["sha256"]:
        raise RuntimeError(f"{pf} is from another seed or design: use a new work directory")
    write_json(pf, sample)
    out["checks"] += [seed_checks(cfg, seed, sample, mode), *sample_checks(cfg, sample, mode)]
    if mode == "sealed" and not all(c["passed"] for c in out["checks"][1:]) and not FAKE:
        raise RuntimeError(f"sample checks failed before any solve: {out['checks']}")
    jobs = Jobs(cfg, workdir, max_procs=max_procs, cap_gb=cap_gb, in_process=in_process)
    strata = sample["strata"]
    cal = jobs.run([cal_job(st) for st in strata.values()])
    pref = {sn: float(cal[cal_job(st)["key"]]["power_W"]) for sn, st in strata.items()}
    write_json(workdir / "pref.json", {"pref_W_per_die": pref, "sha256": sha256_obj(pref)})
    cal_recs = [cal[cal_job(st)["key"]] for st in strata.values()]
    out["checks"].append({"name": "operating_point", "passed": all(abs(c["rise_K"] - cfg["target_rise_K"]) <=
                                                                   cfg["calibration_tol_K"] for c in cal_recs),
                          "value": float(max(abs(c["rise_K"] - cfg["target_rise_K"]) for c in cal_recs)),
                          "threshold": cfg["calibration_tol_K"],
                          "detail": f"P_ref per die (W), fixed in pref.json before any judged solve: {pref}"})
    log(f"P_ref fixed: {pref}")
    l1 = l1_phase(cfg, workdir, sample, pref, in_process)
    descs = all_descs(sample)
    sel = f7_select([{"cell": p["cell"], "pool": p["pool"], "draws": [x["name"] for x in p["draws"]]}
                     for p in sample["f7_pools"]], l1["f7"])  # re-derived here from the recorded P_ref evaluations
    if sel != l1.get("f7_optimised", {}):
        raise RuntimeError(f"F7 selection differs from the L1 phase's: {sel} vs {l1.get('f7_optimised')}")
    for p in sample["f7_pools"]:
        p["optimised"] = sel[pool_key(p)]
    loads = list(cfg["loads"])
    jl = [solve_job(d, ld, cfg["judged_level"], pref, cfg) for st in strata.values() for d in st["judged"] for ld in loads]
    jl += [solve_job(descs[p["optimised"]], ld, cfg["judged_level"], pref, cfg) for p in sample["f7_pools"] for ld in loads]
    jl += [solve_job(descs[n], ld, lv, pref, cfg) for c in sample["l2_subset"] for n in c["layouts"] for ld in loads
           for lv in (0, 2)]
    recs = jobs.run(jl)
    out["new_solves"] = jobs.new
    # ---- rows
    judged_level = cfg["judged_level"]
    die_rows, f7_die_rows, l1_wall = [], [], {}
    for st in strata.values():
        for d in st["judged"]:
            lay = get_layout(d)
            for ld in loads:
                ref = recs[f"{d['name']}__{ld}__L{judged_level}"]
                a, b = l1["judged"][f"{d['name']}__{ld}"], l1["constant_k"][f"{d['name']}__{ld}"]
                iso = isolated_die_null(lay, pref[d["stratum"]] * cfg["loads"][ld], cfg)
                die_rows += die_rows_for(d, lay, ld, ref, a, b, iso)
                l1_wall[(d["name"], ld)] = a["wall_s"]
    add_lolo_nulls(die_rows)
    lay_rows, sw_rows = assemble(die_rows, l1_wall)
    f7_lay_rows = []
    for p in sample["f7_pools"]:
        d = descs[p["optimised"]]
        lay = get_layout(d)
        for ld in loads:
            l1o = l1["f7"][d["name"]] if ld == "P_ref" else l1["f7_other_loads"][f"{d['name']}__{ld}"]
            rows = die_rows_for(d, lay, ld, recs[f"{d['name']}__{ld}__L{judged_level}"], l1o, None, None, "f7_die")
            f7_die_rows += rows
            for r in EM.layout_rows(rows):
                f7_lay_rows.append({**r, "kind": "f7_layout", "stratum": d["stratum"], "band": band_of(d["dies"]),
                                    "cell": p["cell"], "pool": p["pool"]})
    f1rows, f1checks, f1worst = (f1_rows_and_checks(cfg, sample, recs, pref) if sample["l2_subset"] else ([], [], {}))
    out.update(sample=sample, pref=pref, l1=l1, recs=recs, die_rows=die_rows, lay_rows=lay_rows, sw_rows=sw_rows,
               f7_die_rows=f7_die_rows, f7_lay_rows=f7_lay_rows, f1_rows=f1rows, f1_worst=f1worst)
    all_rows = die_rows + lay_rows + sw_rows
    # ---- gated sanity checks on the solves
    ref_recs = [r for k, r in recs.items() if not k.startswith("cal__")]
    ebs = [r["energy_balance"] for r in ref_recs] + [h["energy_balance"] for c in cal_recs for h in c["history"]]
    l1_ebs = [v["energy_balance"] for part in ("judged", "constant_k", "f7", "f7_other_loads") for v in l1[part].values()]
    tj_rows = [r for r in die_rows + f7_die_rows if r["load"] == "P_ref"]  # every judged and F7 layout at P_ref
    out["checks"] += [
        {"name": "energy_balance", "passed": max(ebs + l1_ebs) <= cfg["energy_tol"], "value": max(ebs + l1_ebs),
         "threshold": cfg["energy_tol"], "detail": f"max |Q_out/Q_in - 1|: reference {max(ebs):.2e} over {len(ebs)} solves "
                                                   f"(calibration included), L1 {max(l1_ebs):.2e} over {len(l1_ebs)}"},
        {"name": "picard_converged", "passed": all(r["picard_residual_K"] < cfg["picard_tol_K"] for r in ref_recs),
         "value": max(r["picard_residual_K"] for r in ref_recs), "threshold": cfg["picard_tol_K"], "detail": "reference"},
        {"name": "linear_solver_headroom", "passed": not any(r["cg_hit_maxiter"] for r in ref_recs) and not any(
            h["cg_hit_maxiter"] for c in cal_recs for h in c["history"]),
         "value": float(max(r["cg_max_iterations"] for r in ref_recs)), "threshold": float(cfg["fem_rule"]["cg_maxiter"]),
         "detail": "no AMG-CG solve hit its iteration cap"},
        {"name": "tj_max_within_rating", "passed": max(r["tj_max_ref_K"] for r in tj_rows) <= cfg["tj_limit_K"],
         "value": max(r["tj_max_ref_K"] for r in tj_rows), "threshold": cfg["tj_limit_K"],
         "detail": f"reference hottest node of every judged and F7 layout at P_ref, judged level (K); {len(tj_rows)} dies"},
        {"name": "baseplate_mean_consistent", "passed": all(abs(r["tb_trapz_K"] - r["tb_flux_K"]) <= 1e-6 for r in ref_recs),
         "value": max(abs(r["tb_trapz_K"] - r["tb_flux_K"]) for r in ref_recs), "threshold": 1e-6,
         "detail": "Q1 integral of the bottom field vs T_c + Q_out/(h A) (A2's denominator)"},
        rows_contract(die_rows, lay_rows, sw_rows),
        {"name": "l1_timing_single_thread", "passed": FAKE or all(v == "1" for v in l1["threads_env"].values()),
         "value": None, "threshold": None,
         "detail": f"L1 phase in one process after every P_ref calibration solve had finished and before any judged "
                   f"reference solve, none running; thread variables {l1['threads_env']}; sealed order of "
                   f"{len(l1['judged'])} timed evaluations"}]
    out["checks"] += f1checks
    met, rep = all_metrics(all_rows, spec, cfg, loads)
    out["checks"].append(recompute_consistency(all_rows, spec, met))
    out["checks"].append(f2_check(rep, spec, cfg))
    rep["f6"] = f6_report(die_rows, f1rows)
    rep["f7"] = f7_report(sample, l1, lay_rows, f7_lay_rows, cfg) if sample["f7_pools"] else {}
    rep["f1_worst"] = f1worst
    rep["own_hottest_A1"] = met.get(cfg["metric_names"]["A1_own"])
    met["f6_max_hotnode_gap_K"] = (rep["f6"]["max_gap_K"], None, None)
    met["f6_n_strata_gap_over_2K"] = (float(rep["f6"]["n_strata_gap_over_2K"]), None, None)
    if rep["f7"]:
        met["f7_pair_err_p95_K"] = (rep["f7"]["p95_K"], None, None)
        met["f7_pair_err_max_K"] = (rep["f7"]["max_K"], None, None)
    for k, v in f1worst.items():
        met[f"f1_max_{k}"] = (v, None, None)
    out.update(metrics=met, reports=rep, rows=all_rows)
    return out


def metric_units(spec: dict) -> dict:
    """Every metric's unit from the spec's metrics list (reviews T0449/T0450 (2): F4's A1/A3 are in K)."""
    return {m["name"]: m.get("unit", "") for m in spec.get("metrics", [])}


def metric_level(name: str, ci, cfg: dict) -> float:
    if ci is None:
        return 0.0
    return A5_CI_LEVEL if name == cfg["metric_names"]["A5"] else float(cfg["bound"]["ci_spec"]["level"])


def report_rows(res: dict) -> list:
    return res["rows"] + res["f7_die_rows"] + res["f7_lay_rows"] + res["f1_rows"]


def full(args) -> int:
    from mfos.evidence import ExperimentRun
    with ExperimentRun(experiment_id=EID) as run:
        cfg, spec = run.config, (run.spec or load_spec())
        if run.seed is None:
            raise RuntimeError("E007 needs the sealed seed (spec sealed_seed: true)")
        wd = Path(args.workdir) if args.workdir else run.run_dir / "work"
        res = execute(cfg, spec, int(run.seed), "sealed", wd, max_procs=args.max_procs, cap_gb=args.mem_cap_gb)
        run.rows(report_rows(res))
        units = metric_units(spec)
        for name, (v, ci, n) in res["metrics"].items():
            run.metric(name, v, ci=ci, n=n, level=metric_level(name, ci, cfg), unit=units[name])
        for c in res["checks"]:
            run.sanity(c["name"], c["passed"], value=c.get("value"), threshold=c.get("threshold"), detail=c["detail"][:4000])
        for nm, obj in (("reports.json", res["reports"]), ("plan_frozen.json", res["sample"]), ("pref.json", res["pref"]),
                        ("solves.json", {k: {kk: vv for kk, vv in v.items() if kk not in ("tj_mean", "tj_max")}
                                         for k, v in res["recs"].items()})):
            write_json(run.run_dir / nm, obj)
            run.artifact(nm, run.run_dir / nm)
        st = res["sample"]["strata"]
        run.domain(family=sorted({v["family"] for v in st.values()}), dies_per_switch=sorted({v["dies"] for v in st.values()}),
                   die_size_mm=sorted({v["die_size_mm"] for v in st.values()}), load=list(cfg["loads"]),
                   coolant_K=[cfg["coolant_K"]], h_W_m2K=[cfg["h_W_m2K"]], judged_level=[cfg["judged_level"]],
                   stack=["default DBC (Al2O3 0.38 mm) with SAC305 die attach and 4H-SiC die"],
                   cpu=[platform.processor() or platform.machine()])
        run.notes = f"reports {json.dumps(res['reports'], default=str)[:20000]}"
    return 0


def dev(args) -> int:
    """Development rows (T0398): recorded development seed and die sizes, level 1 judged, no sealed seed."""
    spec = load_spec()
    cfg = spec["config"]
    seed = int(cfg["dev"]["dev_seed"])
    wd = Path(args.workdir or ROOT / cfg["dev"]["workdir"])
    res = execute(cfg, spec, seed, "dev", wd, m=args.dev_layouts or cfg["dev"]["layouts_per_stratum"],
                  max_procs=args.max_procs, cap_gb=args.mem_cap_gb)
    units = metric_units(spec)
    met = {k: {"value": v, "ci": ci, "n": n, "level": metric_level(k, ci, cfg), "unit": units.get(k, "")}
           for k, (v, ci, n) in res["metrics"].items()}
    simp = ROOT / "research" / "o002_e007" / "f3_dev_simulation.json"  # T0398's stats_sim_dev.py (run on these rows)
    sim = read_json(simp) if simp.exists() else {}
    meta = {"experiment": EID, "smoke": False, "fake": FAKE, "seed_role": "development", "dev_seed": seed,
            "judged_level": cfg["judged_level"], "pref_W_per_die": res["pref"], "metrics": met,
            "f2_nulls": res["reports"]["nulls"], "per_stratum_A2": res["reports"]["per_stratum_A2"],
            "per_band_A4": res["reports"]["per_band_A4"], "f6": res["reports"]["f6"],
            "l1_dev_check_D0025": res["reports"]["l1_dev_check"],
            "implied_c_family_spread": res["reports"]["implied_c_family_spread"],
            "l1_dev_check_summary": {"strata_missing_A2_guard_0.018": sorted(
                k for k, v in res["reports"]["l1_dev_check"].items() if not v["meets_guard_A2_0.018"]),
                "strata_missing_A4_0.3": sorted(k for k, v in res["reports"]["l1_dev_check"].items()
                                                if not v["meets_A4_0.3"])},
            "f3_dev": {"coverage": sim.get("f3_dev", {}).get("coverage", {}), "source": str(simp.relative_to(ROOT)),
                       "bound": sim.get("bound"), "reps_per_cell": sim.get("reps_per_cell"),
                       "scenarios": sim.get("f3_dev", {}).get("scenarios"), "power": sim.get("power", {}),
                       "kill_side": sim.get("kill_side", {})} if sim else {},
            "l1_phase_host": res["l1"].get("host"), "l1_phase_threads_env": res["l1"].get("threads_env"),
            "reference_cpu_wall": {k: {"cpu_s": v["cpu_s"] if "cpu_s" in v else sum(h["cpu_s"] for h in v["history"]),
                                       "wall_s": v["wall_s"] if "wall_s" in v else sum(h["wall_s"] for h in v["history"]),
                                       "dofs": v.get("dofs", v.get("level0", {}).get("dofs")),
                                       "peak_rss_GB": v["peak_rss_GB"]} for k, v in res["recs"].items()},
            "l1_eval_s_p50": met[cfg["metric_names"]["A5"]]["value"], "checks": res["checks"],
            "die_size_mm": {k: v["die_size_mm"] for k, v in res["sample"]["strata"].items()}}
    out = Path(args.rows_out or ROOT / "experiments" / "drafts" / "E007.dev_rows.json")
    write_json(out, {"schema": "mfos.rows/1", "rows": report_rows(res), "meta": meta})
    log(f"dev rows: {out} ({len(res['rows'])} judged-type rows); checks failing: "
        f"{[c['name'] for c in res['checks'] if not c['passed']]}")
    return 0


# ------------------------------------------------------------------------------------------------ plan
def plan(args) -> int:
    """Every solve with its memory and time on development-seed proxy layouts of the fixed allocation (the sealed layouts
    are unknown until the run), at the expected die-size mix and at the largest die; CPU-hours (process CPU time, O002
    convention, founder 2026-11-17), $, and local or burst per policy local_cpu_hours_max."""
    from moduleforge.solvers import thermal_fem as FEM
    spec = load_spec()
    cfg = spec["config"]
    cm = cfg["compute"]
    rule = fem_rule(cfg["fem_rule"])
    pol = (ROOT / ".mfos" / "policy.toml").read_text()
    local_max = float(next(ln.split("=")[1].split("#")[0] for ln in pol.splitlines()
                           if ln.strip().startswith("local_cpu_hours_max")))
    sizes, wts = (4.0, 4.5, 5.0, 5.5), (1 / 6, 1 / 3, 1 / 3, 1 / 6)  # draw_die_size_mm's support and probabilities
    nprox = int(args.plan_proxies)
    dofs: dict = {}
    for si, (f, k) in enumerate(all_strata()):
        for s in sizes:
            lays = layout_list(sub_seed(cfg["dev"]["dev_seed"], "layouts", si), f, k, s, nprox)
            dofs[(f, k, s)] = [float(np.mean([FEM.estimate_dofs(x, rule, lv) for x in lays])) for lv in (0, 1, 2)]
    m = cfg["allocation"]["layouts_per_stratum"]
    n_load = len(cfg["loads"])

    def job_list(case: str) -> list[dict]:
        J = []
        for f, k in all_strata():
            d = ([sum(w * dofs[(f, k, s)][lv] for s, w in zip(sizes, wts, strict=True)) for lv in (0, 1, 2)] if case == "expected"
                 else dofs[(f, k, 5.5)])
            sn = stratum_name(f, k)
            J += [{"name": f"{sn}:calibration", "level": 0, "dofs": d[0], "n": cm["calibration_solves_expected"]}]
            J += [{"name": f"{sn}:judged", "level": cfg["judged_level"], "dofs": d[1], "n": m * n_load}]
        for f, b in cells():  # F7: 2 optimised layouts per cell at both loads; subset: 2 layouts x 2 loads x levels 0, 2
            kk = max(BANDS[b]) if case == "upper" else BANDS[b][len(BANDS[b]) // 2]
            d = ([sum(w * dofs[(f, kk, s)][lv] for s, w in zip(sizes, wts, strict=True)) for lv in (0, 1, 2)] if case == "expected"
                 else dofs[(f, kk, 5.5)])
            J += [{"name": f"{f}/{b}:f7", "level": cfg["judged_level"], "dofs": d[1], "n": 2 * n_load},
                  {"name": f"{f}/{b}:subset_L0", "level": 0, "dofs": d[0], "n": 2 * n_load},
                  {"name": f"{f}/{b}:subset_L2", "level": 2, "dofs": d[2], "n": 2 * n_load}]
        for j in J:
            j["mem_GB"] = j["dofs"] * cm["bytes_per_dof"][str(j["level"])] * cm["memory_margin"] / 1e9 + cm["base_rss_GB"]
            j["cpu_s_each"] = j["dofs"] * cm["cpu_s_per_dof"][str(j["level"])]
            j["cpu_h"] = j["n"] * j["cpu_s_each"] / 3600.0
            j["fits_local_5GB"] = j["mem_GB"] <= cm["local_cap_GB"]
        return J

    vm = cm["vm"]
    usable = vm["ram_GB"] * vm["memory_fraction"]
    n_l1 = (m * 15 * n_load) * 2 + 12 * cfg["f7"]["draws_per_pool"] + 12 * (n_load - 1) + 1  # + F7 half load, warm-up
    out: dict = {"convention": "cpu_hours = process CPU time (founder decision 2026-11-17, O002 state log); VM time in $",
                 "policy_local_cpu_hours_max": local_max, "vm": vm, "cases": {},
                 "l1_evaluations": n_l1, "l1_cpu_h": n_l1 * cm["l1_s_per_eval"] / 3600.0}
    for case in ("expected", "upper"):
        J = job_list(case)
        cpu = sum(j["cpu_h"] for j in J) + out["l1_cpu_h"]
        big = [j for j in J if not j["fits_local_5GB"]]
        loc = [j for j in J if j["fits_local_5GB"]]
        l2_vm_h = 0.0  # level-2 makespan on the VM: one job at a time unless two fit the usable memory
        for j in big:
            par = max(1, min(vm["vcpus"], int(usable // j["mem_GB"]))) if j["mem_GB"] <= usable else 0
            if par == 0:
                raise SystemExit(f"{j['name']}: {j['mem_GB']:.1f} GB exceeds the VM's {usable:.1f} GB usable")
            l2_vm_h += j["n"] * j["cpu_s_each"] / 3600.0 / min(par, j["n"])
        loc_h = sum(j["cpu_h"] for j in loc) + out["l1_cpu_h"]
        par_loc_vm = max(1, min(vm["vcpus"], int(usable // max(j["mem_GB"] for j in loc))))
        a_vm_h = l2_vm_h + loc_h / par_loc_vm + vm["overhead_h"]
        b_vm_h = l2_vm_h + vm["overhead_h"]
        out["cases"][case] = {
            "solves": [{k: (round(v, 3) if isinstance(v, float) else v) for k, v in j.items()} for j in J],
            "n_reference_solves": int(sum(j["n"] for j in J)), "cpu_hours_est": round(cpu, 1),
            "local_or_burst_per_policy": "burst" if cpu > local_max else "local",
            "jobs_over_local_5GB": [j["name"] for j in big],
            "option_A_all_on_burst": {"vm_hours": round(a_vm_h, 1), "usd": round(a_vm_h * vm["usd_per_h"], 2),
                                      "runner_flags": f"--max-procs {vm['vcpus']} --mem-cap-gb {usable:.1f}",
                                      "note": "the packing priced here needs these flags; the defaults (--max-procs 1, "
                                              "5 GB cap) refuse the over-cap jobs"},
            "option_A_one_at_a_time": {"vm_hours": round(cpu + vm["overhead_h"], 1),
                                       "usd": round((cpu + vm["overhead_h"]) * vm["usd_per_h"], 2),
                                       "runner_flags": f"--max-procs 1 --mem-cap-gb {usable:.1f}"},
            "option_B_local_then_burst": {"local_cpu_hours": round(loc_h, 1), "local_wall_hours_one_at_a_time":
                                          round(loc_h, 1), "vm_hours": round(b_vm_h, 1),
                                          "usd": round(b_vm_h * vm["usd_per_h"], 2),
                                          "runner_flags": f"local: E007_SKIP_OVER_CAP=1 --max-procs 1; VM: --max-procs "
                                                          f"{vm['vcpus']} --mem-cap-gb {usable:.1f} (same --workdir)"}}
    print(json.dumps({k: v for k, v in out.items()} | {"cases": {c: {k: v for k, v in d.items() if k != "solves"}
                                                                  for c, d in out["cases"].items()}}, indent=1))
    for c, d in out["cases"].items():
        for j in d["solves"]:
            print(f"  {c:8s} {j['name']:28s} L{j['level']} x{j['n']:3d}  {j['dofs'] / 1e6:6.2f} M DOF  {j['mem_GB']:6.1f} GB  "
                  f"{j['cpu_s_each'] / 60:6.1f} min  {'local' if j['fits_local_5GB'] else 'burst'}")
    if args.plan_out:
        write_json(Path(args.plan_out), out)
    return 0


# ------------------------------------------------------------------------------------------------ selftest
def _evaluator_null_check(spec: dict, rows: list) -> tuple[list[str], list[str], str]:
    """The evaluator's own registration-time null check (evaluate.null_check) on these rows. If the installed CISpec
    predates the woodruff scheme (a checkout based before da2118fc) the spec is parsed with ci removed: the evaluator
    then judges ci-criteria 'missing' and can flag nothing, so only its null values are compared (mode 'points')."""
    from mfos import evaluate as ev
    from mfos import models as mm
    from mfos.store import Store
    try:
        sp, mode = mm.ExperimentSpec(**spec), "bounds"
    except Exception:
        sp = mm.ExperimentSpec(**{**spec, "recompute": [{**e, "ci": None} for e in spec["recompute"]]})
        mode = "points"
    lines, bad = ev.null_check(Store(ROOT), sp, rows)
    return lines, bad, mode


def selftest() -> int:
    """Fake solvers on the registered allocation (m = 20 per stratum, 300 layouts; F7 pools of 3 draws); the real sample
    construction, job loop (one job through a real child process), resume, rows, nulls, metrics and bounds, and the
    evaluator's null check with the spec's applies_to; mutation checks that a wrong hottest die, a 1 K hottest-die
    error, a null that meets A1, a forbidden stream seed and a seen F7 draw are caught. Then the real physics: L1 and
    null (a) on one layout, one level-0 P_ref calibration through a real child process, DOF growth of the subset."""
    global FAKE
    FAKE = True
    import tempfile
    spec = load_spec()
    cfg = json.loads(json.dumps(spec["config"]))
    cfg["f7"]["draws_per_pool"] = 3
    m = int(cfg["allocation"]["layouts_per_stratum"])
    A1, A3, A4 = (cfg["metric_names"][k] for k in ("A1", "A3", "A4"))
    fails: list[str] = []

    def ok(cond: bool, what: str) -> None:
        print(("ok   " if cond else "FAIL ") + what, flush=True)
        if not cond:
            fails.append(what)
    fz = freeze_checks(cfg)
    ok(all(c["passed"] for c in fz), f"freeze checks ({[c['name'] for c in fz if not c['passed']]})")
    with tempfile.TemporaryDirectory(prefix="e007_selftest_") as td:
        wd = Path(td) / "fake"
        s1, s2 = build_sample(cfg, 12345, "sealed", 3), build_sample(cfg, 12345, "sealed", 3)
        ok(s1["sha256"] == s2["sha256"], "sample deterministic in the seed")
        ok(build_sample(cfg, 12346, "sealed", 3)["sha256"] != s1["sha256"], "sample changes with the seed")
        ok(seed_checks(cfg, 20261395, s1, "sealed")["passed"] is False, "a development seed is refused as sealed")
        streams = {k.split(":")[0] for k in s1["sub_seeds"]}
        ok(streams == set(STREAMS), f"every stream seed recorded ({sorted(streams)})")
        for stream in ("timing_order", "l2_subset", "die_size:u_shaped/4"):  # mutation: a forbidden derived seed
            c2 = json.loads(json.dumps(cfg))
            c2["seeds"]["forbidden"] = [*c2["seeds"]["forbidden"], s1["sub_seeds"][stream]]
            ok(seed_checks(c2, 12345, s1, "sealed")["passed"] is False, f"mutation: forbidden {stream} seed is caught")
        c3 = json.loads(json.dumps(cfg))  # mutation: an F7 draw equal to a seen development layout
        c3["c004"]["other_dev_fingerprints"] = [*c3["c004"]["other_dev_fingerprints"],
                                                s1["f7_pools"][0]["draws"][1]["fingerprint"]]
        ok(not next(c for c in sample_checks(c3, s1, "sealed") if c["name"] == "layouts_distinct_and_unseen")["passed"],
           "mutation: a seen F7 draw is caught by layouts_distinct_and_unseen")
        st0 = next(iter(s1["strata"].values()))  # one job through a real child process (fake physics)
        j = Jobs(cfg, wd, in_process=False)
        j.run([cal_job(st0)])
        ok(j.new == 1 and (wd / "solves" / f"{cal_job(st0)['key']}.json").exists(), "child process writes its checkpoint")
        t0 = time.time()
        res = execute(cfg, spec, 12345, "sealed", wd, m=m, in_process=True)
        ok(res["new_solves"] > 600, f"run at m = {m} solved {res['new_solves']} reference jobs ({time.time() - t0:.0f} s)")
        res2 = execute(cfg, spec, 12345, "sealed", wd, m=m, in_process=True)
        ok(res2["new_solves"] == 0, "resume: a second pass reuses every checkpoint")
        ok(res2["metrics"] == res["metrics"], "resume reproduces every metric")
        try:
            execute(cfg, spec, 999, "sealed", wd, m=m, in_process=True)
            ok(False, "a work directory of another seed is refused")
        except RuntimeError:
            ok(True, "a work directory of another seed is refused")
        failing = [c["name"] for c in res["checks"] if not c["passed"]]
        ok(failing == [], f"every sanity check passes on the fake run at m = {m}, node_count_growth unbypassed ({failing})")
        declared = {s["name"] for s in spec["sanity_checks"]}
        reported = {c["name"] for c in res["checks"]}
        ok(declared == reported, f"declared == reported sanity checks (missing {sorted(declared - reported)}, "
                                 f"undeclared {sorted(reported - declared)})")
        names = {x["name"] for x in spec["metrics"]}
        ok(names <= set(res["metrics"]), f"every declared metric reported (missing {sorted(names - set(res['metrics']))})")
        rows = res["rows"]
        import mfos.metrics as mx
        for e in recompute_entries(spec):  # the evaluator's path, entry by entry, against the runner's metric
            v = compute_point(rows, e)
            ok(math.isclose(v, res["metrics"][e["metric"]][0], rel_tol=1e-12), f"recompute {e['metric']} = {v:.6g}")
            if e["fn"] != "median_col":
                lo, hi = res["metrics"][e["metric"]][1]
                ok(lo <= v <= hi and math.isfinite(hi), f"  finite bound brackets the point ({lo:.4g}, {hi:.4g})")
                ok(e.get("ci") == cfg["bound"]["ci_spec"], f"  spec ci is {cfg['bound']['ci_spec']}")
                sub = _where(rows, e["where"])
                p_em, ci_em = EM.quantile_ci(e["fn"], sub, pred=e["pred"], ref=e["ref"], strata=e.get("strata", []),
                                             params=e["params"], level=0.94, cluster="layout")
                ok(math.isclose(p_em, v, rel_tol=1e-12) and tuple(ci_em) == tuple(res["metrics"][e["metric"]][1]),
                   f"  e007_metrics.quantile_ci == {'mfos.metrics' if hasattr(mx, 'quantile_ci') else 'runner'} bound")
        ok(True, f"mfos.metrics.quantile_ci present: {hasattr(mx, 'quantile_ci')} (merged on main da2118fc; absent in a "
                 "checkout based before it, where the runner uses the verbatim e007_metrics copy)")
        ok(res["metrics"][A1][0] < 0.5, f"fake L1 meets A1 point ({res['metrics'][A1][0]:.3f} K)")
        # ---- F2 / null_baselines (review T0436 blocker): applies_to is exactly A1 and A4 for every null
        nb = {n["name"]: n for n in spec["null_baselines"]}
        ok(set(nb) == {"die_position", "stratum_mean", "isolated_die"}
           and all(sorted(n["applies_to"]) == sorted([A1, A4]) for n in nb.values()),
           f"null_baselines: three nulls, applies_to = [A1, A4] each ({ {k: v['applies_to'] for k, v in nb.items()} })")
        for nul, r0 in res["reports"]["nulls"].items():
            ev = r0["evaluator_view"]
            ok(set(ev) == {A1, A4} and not any(x["meets"] for x in ev.values()),
               f"null {nul}: A1 {r0['A1_P_ref_K']:.3f} K (bound {ev[A1]['bound_used']:.3f}), A4 {r0['A4_point']:.3f} "
               f"(bound {ev[A4]['bound_used']:.3f}) fail; reported A2 {r0['A2_P_ref']:.4f}, A3 {r0['A3_P_ref_K']:.3f} K; "
               f"{len(r0['per_stratum_P_ref'])} strata")
        ok(math.isclose(res["reports"]["nulls"]["stratum_mean"]["A4_point"], 1.0), "stratum-mean null's A4 is exactly 1")
        lines, bad, mode = _evaluator_null_check(spec, rows)
        print("     " + "\n     ".join(lines))
        ok(not bad, f"evaluate.null_check ({mode}): no criterion flagged ({bad})")
        null_lines = [ln for ln in lines if ln.strip().startswith("null ")]
        ok(len(null_lines) == 6, f"  the evaluator applies the three nulls to A1 and A4 only ({len(null_lines)} null lines)")
        ev_pts: dict = {}  # the evaluator's null values equal the runner's (same columns, same rows)
        cur = None
        for ln in lines:
            if not ln.startswith(" "):
                cur = ln.split()[1].partition(".")[2]
            else:
                nm, _, rest = ln.strip()[5:].partition(": ")
                ev_pts[(nm, cur)] = float(rest.split(" -> ")[0])
        ok(len(ev_pts) == 6 and all(math.isclose(v, res["reports"]["nulls"][n]["evaluator_view"][mt]["point"],
                                                 rel_tol=1e-12) for (n, mt), v in ev_pts.items()),
           "  evaluator null values == runner's")
        # what attempt 1's design (applies_to including A3) would have done on these rows
        e3 = next(e for e in recompute_entries(spec) if e["metric"] == A3)
        v3, ci3, _ = metric_with_bound(rows, {**e3, "pred": "null_smean"}, 0.94)
        print(f"     (attempt-1 design) stratum-mean null A3 {v3:.3f} K, upper {ci3[1]:.3f} K: "
              f"{'A3 would be non_discriminating' if ci3[1] <= 1.0 else 'not met on these rows'}")
        # mutation: a null equal to L1 at the hottest die meets A1 -> f2_null_discrimination fails
        rep_m = json.loads(json.dumps(res["reports"], default=str))
        lr = [dict(r, null_pos=r["tj_hot_l1_K"]) if r["kind"] == "layout" else r for r in rows]
        e1p = per_load(next(e for e in recompute_entries(spec) if e["metric"] == A1), "P_ref")
        rep_m["nulls"]["die_position"]["A1_P_ref_K"] = compute_point(lr, {**e1p, "pred": "null_pos"})
        rep_m["nulls"]["die_position"]["fails_A1_point"] = rep_m["nulls"]["die_position"]["A1_P_ref_K"] > 0.5
        ok(not f2_check(rep_m, spec, cfg)["passed"], "mutation: a null that meets A1 fails f2_null_discrimination")
        rep_m = json.loads(json.dumps(res["reports"], default=str))
        rep_m["nulls"]["isolated_die"]["applies_to"] = [A1, A3, A4]
        ok(not f2_check(rep_m, spec, cfg)["passed"], "mutation: applies_to beyond A1/A4 fails f2_null_discrimination")
        ok(len(res["reports"]["per_stratum_A2"]) == 15 and len(res["reports"]["per_band_A4"]) == 2,
           f"per-stratum A2 and per-band A4 reported; per-stratum A2 upper bound informative in "
           f"{res['reports']['per_stratum_A2_n_upper_informative']}/15, infinite in "
           f"{res['reports']['per_stratum_A2_n_upper_infinite']}/15")
        ok(len(res["reports"]["l1_dev_check"]) == 15 and all("implied_c_P_ref" in v for v in
                                                              res["reports"]["l1_dev_check"].values()),
           "D0025 per-stratum L1 check reported (implied c, HS/LS bias, A2 vs 1.8 %, A4 vs 0.3)")
        l1 = read_json(wd / "l1_phase.json")
        ok(len(res["sample"]["f7_pools"]) == 12 and bool(res["reports"]["f7"].get("pools"))
           and len(l1["f7_other_loads"]) == 12 and len(l1["f7_optimised"]) == 12,
           "F7: 12 pools; selection and half-load evaluations inside the L1 phase; errors reported")
        eb = next(c for c in res["checks"] if c["name"] == "energy_balance")
        n_l1 = sum(len(l1[p]) for p in ("judged", "constant_k", "f7", "f7_other_loads"))
        ok(f"over {n_l1}" in eb["detail"], f"energy_balance covers every L1 evaluation ({n_l1})")
        ok("f4_kT_tested" in res["metrics"] and "f4_constant_k_A1_half_P_ref" in res["metrics"], "F4 at both loads")
        ok(bool(res["f1_rows"]) and len(res["sample"]["l2_subset"]) == 6, "F1 subset rows (6 cells x 2 layouts)")
        # mutation: the hottest die taken by L1's ranking instead of the reference's must be caught
        dr = res["die_rows"]
        mut = [dict(r) for r in res["lay_rows"]]
        n_diff = 0
        for r in mut:
            rs = [x for x in dr if x["layout"] == r["layout"] and x["load"] == r["load"]]
            own = max(rs, key=lambda x: x["tj_l1_K"])
            if (own["switch"], own["die_index"]) != (r["hot_switch"], r["hot_die_index"]):
                n_diff += 1
            r["tj_hot_l1_K"] = own["tj_l1_K"]
            r["hot_switch"], r["hot_die_index"] = own["switch"], own["die_index"]
        ok(n_diff > 0, f"fake data has {n_diff} layout-loads whose L1 hottest die is not the reference's")
        ok(not rows_contract(dr, mut, res["sw_rows"])["passed"], "mutation: wrong hottest die is caught by rows_contract")
        # mutation: a 1 K error on each reference-hottest die of half the layouts must move A1 past 0.5 K
        dr2 = [dict(r) for r in dr]
        hot = {(r["layout"], r["load"]): (r["hot_switch"], r["hot_die_index"]) for r in res["lay_rows"]}
        for r in dr2:
            if (r["switch"], r["die_index"]) == hot[(r["layout"], r["load"])] and int(r["layout"][-2:]) % 2 == 0:
                r["tj_l1_K"] += 1.0
        lr2, sr2 = assemble(dr2, {(r["layout"], r["load"]): r["l1_eval_s"] for r in res["lay_rows"]})
        e1 = next(e for e in recompute_entries(spec) if e["metric"] == A1)
        ok(compute_point(dr2 + lr2 + sr2, e1) > 0.5, "mutation: a 1 K hottest-die error on half the layouts fails A1")
        g = [r for r in dr if r["stratum"] == dr[0]["stratum"] and r["load"] == "P_ref" and r["switch"] == "HS"
             and r["die_index"] == 0]
        own_mean = float(np.mean([r["tj_ref_K"] for r in g]))
        ok(all(not math.isclose(r["null_pos"], own_mean, abs_tol=1e-12) for r in g), "die-position null is leave-one-out")
        e4 = next(e for e in recompute_entries(spec) if e["metric"] == A4)
        ok(compute_point(rows, {**e4, "pred": "spread_ref_K"}) == 0.0, "A4 of a perfect predictor is 0")
        # ---- the real physics (review T0436 major): L1, null (a), one real level-0 calibration in a child process
        FAKE = False
        try:
            s20 = res["sample"]
            d0 = s20["strata"]["u_shaped/2"]["judged"][0]
            lay0 = get_layout(d0)
            r_l1 = l1_eval(lay0, 40.0, cfg)
            iso = isolated_die_null(lay0, 40.0, cfg)
            tbp = cfg["coolant_K"] + 40.0 * len(lay0.dies) / (cfg["h_W_m2K"] * float(lay0.baseplate_outline.area))
            ok(all(math.isfinite(v) and v > tbp for v in r_l1["tj_mean"]) and r_l1["energy_balance"] <= 1e-6,
               f"real L1 on {d0['name']}: {r_l1['wall_s']:.2f} s, eb {r_l1['energy_balance']:.1e}")
            ok(bool(np.all(iso > tbp)) and bool(np.all(np.isfinite(iso))),
               f"real isolated-die null: rises {np.round(iso - tbp, 2).tolist()} K above T_bp")
            from moduleforge.solvers import thermal_fem as FEM
            rule = fem_rule(cfg["fem_rule"])
            growth = []
            for c in s20["l2_subset"]:
                for nm in c["layouts"]:
                    dd = [FEM.estimate_dofs(get_layout(all_descs(s20)[nm]), rule, lv) for lv in (0, 1, 2)]
                    growth += [dd[1] / dd[0], dd[2] / dd[1]]
            ok(all(abs(x / 8.0 - 1.0) <= cfg["f1"]["node_growth_tol"] for x in growth),
               f"real DOF growth on the 12 subset layouts {min(growth):.2f}-{max(growth):.2f} (8 +/- 15 %)")
            dev = build_sample(cfg, cfg["dev"]["dev_seed"], "dev", 2)
            prefs = [st["pref_layout"] for st in dev["strata"].values()]
            small = min(prefs, key=lambda d: FEM.estimate_dofs(get_layout(d), rule, 0))
            jr = Jobs(cfg, Path(td) / "real", in_process=False, cap_gb=cfg["compute"]["local_cap_GB"])
            job = {"key": f"cal__{small['name']}", "kind": "calibrate", "layout": small}
            est = jr.est_gb(job)
            t0 = time.time()
            rec = jr.run([job])[job["key"]]
            lv0 = rec["level0"]
            ok(abs(rec["rise_K"] - cfg["target_rise_K"]) <= cfg["calibration_tol_K"],
               f"real calibration of {small['name']} ({small['die_size_mm']} mm): P_ref {rec['power_W']:.3f} W, rise "
               f"{rec['rise_K']:.3f} K after {len(rec['history'])} level-0 solves, {time.time() - t0:.0f} s")
            ok(max(h["energy_balance"] for h in rec["history"]) <= cfg["energy_tol"],
               f"  energy balance {max(h['energy_balance'] for h in rec['history']):.1e} on every solve")
            ok(abs(lv0["tb_trapz_K"] - lv0["tb_flux_K"]) <= 1e-6,
               f"  Q1 bottom mean {lv0['tb_trapz_K']:.9f} K == T_c + Q_out/(hA) {lv0['tb_flux_K']:.9f} K")
            ok(lv0["picard_residual_K"] < cfg["picard_tol_K"] and not any(h["cg_hit_maxiter"] for h in rec["history"]),
               f"  Picard {lv0['picard_residual_K']:.1e} K, CG max {lv0['cg_max_iterations']} iterations, no cap hit")
            ok(lv0["dofs"] == FEM.estimate_dofs(get_layout(small), rule, 0),
               f"  DOF estimator exact at level 0 ({lv0['dofs']})")
            ok(rec["peak_rss_GB"] <= est, f"  peak RSS {rec['peak_rss_GB']:.2f} GB <= admission estimate {est:.2f} GB")
            ok(len(lv0["tj_mean"]) == len(get_layout(small).dies) and rec["fake"] is False, "  real record, one value per die")
        finally:
            FAKE = True
    print(f"selftest: {len(fails)} failure(s)")
    return 1 if fails else 0


# ------------------------------------------------------------------------------------------------ main
def main(argv=None) -> int:
    global FAKE
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--verify-freeze", action="store_true")
    ap.add_argument("--plan", action="store_true")
    ap.add_argument("--plan-out")
    ap.add_argument("--plan-proxies", type=int, default=2)
    ap.add_argument("--dev", action="store_true")
    ap.add_argument("--dev-layouts", type=int)
    ap.add_argument("--rows-out")
    ap.add_argument("--child")
    ap.add_argument("--l1-phase")
    ap.add_argument("--fake", action="store_true")
    ap.add_argument("--workdir")
    ap.add_argument("--max-procs", type=int, default=1)
    ap.add_argument("--mem-cap-gb", type=float)
    a = ap.parse_args(argv)
    # the orchestrator starts the registered run without arguments: the host sets these instead (E007_MEM_CAP_GB,
    # E007_MAX_PROCS, E007_WORKDIR for checkpoint and resume; E007_SKIP_OVER_CAP=1 solves only what fits, then stops)
    if a.mem_cap_gb is None and os.environ.get("E007_MEM_CAP_GB"):
        a.mem_cap_gb = float(os.environ["E007_MEM_CAP_GB"])
    a.max_procs = int(os.environ.get("E007_MAX_PROCS", a.max_procs))
    a.workdir = a.workdir or os.environ.get("E007_WORKDIR")
    os.chdir(ROOT)
    FAKE = bool(a.fake)
    if a.child:
        return run_child(Path(a.child))
    if a.l1_phase:
        return run_l1_phase(Path(a.l1_phase))
    if a.selftest:
        return selftest()
    if a.verify_freeze:
        return verify_freeze()
    if a.plan:
        return plan(a)
    if a.dev:
        return dev(a)
    return full(a)


if __name__ == "__main__":
    sys.exit(main())
