"""O006 pilots P1 + P2 (T0167): thermal envelope, O002 load levels, O003 operating point, thermal null predictors.

Research notes only, never evidence (O006 F4).  Rules are frozen in research/notes/o006-p1-thermal-envelope.md and
o006-p2-thermal-nulls.md section 1 (sha256 recorded in raw/prereg.json before the first solve).

  uv run python research/scripts/o006_p1/thermal_envelope.py check            # sanity checks (wrapper, variants)
  uv run python research/scripts/o006_p1/thermal_envelope.py p1 --shard k --nshards 6 # (x6) balanced set: envelope, P60, variants
  uv run python research/scripts/o006_p1/thermal_envelope.py levels           # frozen rule -> raw/levels.json
  uv run python research/scripts/o006_p1/thermal_envelope.py p2 --shard k --nshards 6 # (x6) P2 core: direct solves at P_lo, P_hi
  uv run python research/scripts/o006_p1/thermal_envelope.py bias --shard k --nshards 2 # levels 0 and 2 on 10 layouts
  uv run python research/scripts/o006_p1/thermal_envelope.py report           # -> research/o006_p1/results.json
  add --smoke to run 2 layouts into $TMPDIR/o006_p1_smoke instead.
SI units, kelvin, float64.
"""
from __future__ import annotations

import os

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ.setdefault(_v, "1")

import argparse  # noqa: E402
import hashlib  # noqa: E402
import json  # noqa: E402
import math  # noqa: E402
import time  # noqa: E402
from itertools import combinations  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402

from moduleforge.generate.halfbridge import DIE_COUNTS, FAMILIES, generate_layouts  # noqa: E402
from moduleforge.geometry.stack import K_T_MAX, K_T_MIN  # noqa: E402
from moduleforge.solvers import thermal_layout as tl  # noqa: E402
from moduleforge.solvers.thermal_fv import solve_steady  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
NOTES = [ROOT / "research/notes/o006-p1-thermal-envelope.md", ROOT / "research/notes/o006-p2-thermal-nulls.md"]

LEVEL = 0  # the one fixed level of the frozen grid rule (amended from 1 before production for compute, P1 note s.1)
BIAS_LEVELS = tuple(lv for lv in (0, 1, 2) if lv != LEVEL)  # the other two levels, solved on the bias set
TC, H = 338.15, 5000.0  # K, W/(m2 K)
TJ_LIM = 448.15  # K (175 C)
RISE_LIM, RISE_LO = TJ_LIM - TC, 60.0
PASS = 0.95
DIE_SIZES = (4.0, 4.5, 5.0, 5.5)
SEED_ASSIGN, SEED_POOL0, SEED_BOOT = 916700, 916701, 916799
N_P1, K_P2, POOL_MAX = 2, 10, 400
TOL_K = 0.02
BOOT_B = 2000
BIAS_STRATA = (0, 2, 4, 5, 6, 8, 9, 10, 12, 14)
STRATA = [(f, n) for f in FAMILIES for n in DIE_COUNTS]
VARIANTS = {  # T0157 final note ranges (review T0174: SiC c-axis), one at a time
    "SiC_low_270_n-1.50": {"sic": (270.0, -1.50)},
    "SiC_high_390_n-1.25": {"sic": (390.0, -1.25)},
    "SAC305_alpha_4.0e-3": {"sac": 4.0e-3},
    "SAC305_alpha_5.0e-3": {"sac": 5.0e-3},
}


# ------------------------------------------------------------------------------------------------ design
def design(smoke: bool = False) -> dict:
    """Sample design (no solves): die size per stratum, P1 balanced set, P2 core, level-bias set."""
    rng = np.random.default_rng(SEED_ASSIGN)
    p2_size = [float(s) for s in rng.permutation(np.repeat(DIE_SIZES, 4))[: len(STRATA)]]
    recs: dict[str, dict] = {}
    for k, (fam, n) in enumerate(STRATA):
        seed = SEED_POOL0 + k
        need = {d: max(N_P1, K_P2 if d == p2_size[k] else 0) for d in DIE_SIZES}
        got = {d: 0 for d in DIE_SIZES}
        pool = []
        m = 40
        while any(got[d] < need[d] for d in DIE_SIZES):
            if m > POOL_MAX:
                raise RuntimeError(f"stratum {k}: not enough layouts per die size in {POOL_MAX}")
            pool = generate_layouts(m, seed, family=fam, dies_per_switch=n)
            got = {d: sum(abs(lay.dies[0].w * 1e3 - d) < 1e-9 for lay in pool) for d in DIE_SIZES}
            m *= 2
        cnt = {d: 0 for d in DIE_SIZES}
        for i, lay in enumerate(pool):
            d = round(lay.dies[0].w * 1e3, 6)
            if cnt[d] >= need[d]:
                continue
            sets = (["p1"] if cnt[d] < N_P1 else []) + (["p2"] if d == p2_size[k] and cnt[d] < K_P2 else [])
            cnt[d] += 1
            lid = f"{fam}_{n}_s{seed}_i{i:03d}"
            recs[lid] = {"id": lid, "family": fam, "dies_per_switch": n, "stratum": k, "seed": seed, "pool_index": i,
                         "die_size_mm": d, "p2_die_size_mm": p2_size[k], "fingerprint": lay.fingerprint(),
                         "sets": sets}
    for k in BIAS_STRATA:
        first = min((r for r in recs.values() if r["stratum"] == k and "p2" in r["sets"]), key=lambda r: r["pool_index"])
        first["sets"].append("bias")
    out = {"p2_die_size_by_stratum": {f"{f}/{n}": p2_size[k] for k, (f, n) in enumerate(STRATA)}, "layouts": recs}
    if smoke:
        keep = [next(r for r in recs.values() if r["stratum"] == 0 and "p1" in r["sets"]),
                next(r for r in recs.values() if r["stratum"] == 14 and "bias" in r["sets"])]
        for r in keep:
            r["sets"] = sorted(set(r["sets"]) | {"p1", "p2", "bias"})
        out["layouts"] = {r["id"]: r for r in keep}
    return out


def rebuild(rec: dict):
    lay = generate_layouts(rec["pool_index"] + 1, rec["seed"], family=rec["family"],
                           dies_per_switch=rec["dies_per_switch"])[rec["pool_index"]]
    if lay.fingerprint() != rec["fingerprint"]:
        raise RuntimeError(f"fingerprint mismatch for {rec['id']}")
    return lay


# ------------------------------------------------------------------------------------------------ solves
def _ranged(fn):
    def k(T):
        T = np.asarray(T, dtype=float)
        if not np.all(np.isfinite(T)) or T.min() < K_T_MIN or T.max() > K_T_MAX:
            raise ValueError("k(T) outside its validity range")
        return fn(T)
    return k


def materials(grid, variant: dict | None = None, constant: bool = False) -> list:
    """Materials in MAT_NAMES order: Layer objects (coded k(T)), 300 K constants, or locally varied laws."""
    mats = list(grid.materials)
    if constant:
        return [la.k for la in mats]
    out = list(mats)
    if variant and "sic" in variant:
        k300, ex = variant["sic"]
        assert mats[6].material == "4H-SiC"
        out[6] = _ranged(lambda T, k300=k300, ex=ex: k300 * (T / 300.0) ** ex)
    if variant and "sac" in variant:
        a = variant["sac"]

        def f(T, a=a):
            return (T / 300.0) / (1.0 + a * (T - 300.0))
        for i, la in enumerate(mats):
            if la.material == "SAC305":
                out[i] = _ranged(lambda T, k0=la.k: k0 * f(T) / f(300.0))
    return out


def solve(lay, grid, P: float, mats) -> dict:
    """One L2 solve on a prebuilt grid (identical to ``solve_layout_level`` apart from grid reuse; see ``check``)."""
    q = np.zeros(grid.shape)
    for d, (ii, jj, kk) in zip(lay.dies, grid.die_top_flux_index, strict=True):
        q[np.ix_(ii, jj, [kk])] = P / (d.w * d.h)
    res = solve_steady(grid.x, grid.y, grid.z, grid.cell_material, mats, h=H, T_inf=TC, flux={(2, 1): q},
                       picard_tol=1e-4)
    per = [tl._die_values(res, d.bounds) for d in lay.dies]
    return {"P": float(P), "tj_max": [v["tj_max"] for v in per], "tj_mean": [v["tj_mean"] for v in per],
            "energy_balance": float(res.meta["energy_balance"]), "picard_iters": int(res.meta["picard_iters"]),
            "n_cells": int(res.meta["n_cells"])}


def find_power(f, P0: float, target: float) -> tuple[float, list]:
    """Secant on the hottest-die rise: P with |max Tj - T_c - target| <= TOL_K."""
    pts, P = [], P0
    for _ in range(10):
        s = f(P)
        pts.append(s)
        r = max(s["tj_max"]) - TC
        if abs(r - target) <= TOL_K:
            return P, pts
        if len(pts) == 1:
            P = P * target / r
        else:
            pa, ra = pts[-2]["P"], max(pts[-2]["tj_max"]) - TC
            P = P + (target - r) * (P - pa) / (r - ra)
    raise RuntimeError("secant did not converge")


def fit_rise(pts: list) -> tuple[float, float]:
    """Least squares rise = a P + b P^2 through the origin over k(T) solves (hottest die)."""
    P = np.array([s["P"] for s in pts])
    r = np.array([max(s["tj_max"]) - TC for s in pts])
    A = np.stack([P, P**2], axis=1)
    a, b = np.linalg.lstsq(A, r, rcond=None)[0]
    return float(a), float(b)


def p_at_rise(a: float, b: float, rise: float) -> float:
    if abs(b) < 1e-12:
        return rise / a
    return (-a + math.sqrt(a * a + 4.0 * b * rise)) / (2.0 * b)


def _task(args):
    phase, rec, extra = args
    t0 = time.process_time()
    lay = rebuild(rec)
    out = {"id": rec["id"], "phase": phase}
    if phase == "p1":
        g = tl.build_layout_grid(lay, LEVEL)
        ck = solve(lay, g, 1.0, materials(g, constant=True))
        rpw = [t - TC for t in ck["tj_max"]]
        out["ck"] = {"solve": ck, "rise_per_W": rpw, "P_lim": RISE_LIM / max(rpw), "P60": RISE_LO / max(rpw)}
        nom = materials(g)
        plim, pts = find_power(lambda P: solve(lay, g, P, nom), 0.92 * RISE_LIM / max(rpw), RISE_LIM)
        pts.append(solve(lay, g, 0.55 * plim, nom))
        a, b = fit_rise(pts)
        out["kT"] = {"P_lim": plim, "solves": pts, "fit_a_b": [a, b], "P60": p_at_rise(a, b, RISE_LO)}
        out["variants"] = {}
        for name, spec in VARIANTS.items():
            mv = materials(g, spec)
            pv, ptsv = find_power(lambda P, mv=mv: solve(lay, g, P, mv), plim, RISE_LIM)
            out["variants"][name] = {"P_lim": pv, "solves": ptsv}
    elif phase == "p2":
        g = tl.build_layout_grid(lay, LEVEL)
        out["loads"] = {k: solve(lay, g, P, materials(g)) for k, P in extra.items()}
    elif phase == "bias":
        out["levels"] = {}
        for lv in BIAS_LEVELS:
            g = tl.build_layout_grid(lay, lv)
            out["levels"][str(lv)] = {k: solve(lay, g, P, materials(g)) for k, P in extra.items()}
            del g
    out["cpu_s"] = time.process_time() - t0
    return out


def run_phase(phase: str, outdir: Path, des: dict, shard: int, nshards: int, extra=None):
    """Sequential in this process over shard ``shard`` of ``nshards`` (the shell launches the shards in parallel;
    the sandbox forbids multiprocessing semaphores).  Finished layouts are cached in raw/<phase>/<id>.json."""
    raw = outdir / "raw" / phase
    raw.mkdir(parents=True, exist_ok=True)
    allr = sorted((r for r in des["layouts"].values() if phase in r["sets"]), key=lambda r: r["id"])
    todo = [r for j, r in enumerate(allr) if j % nshards == shard and not (raw / f"{r['id']}.json").exists()]
    print(f"{phase} shard {shard}/{nshards}: {len(todo)} layouts to run", flush=True)
    for r in todo:
        res = _task((phase, r, extra))
        (raw / f"{res['id']}.json").write_text(json.dumps(res))
        print(f"  {res['id']} cpu {res['cpu_s']:.0f} s", flush=True)


# ------------------------------------------------------------------------------------------------ analysis
def env_quantile(v) -> float:
    """Highest P with P_lim >= P on >= 95 % of layouts: order statistic k+1, k = floor(0.05 n)."""
    v = np.sort(np.asarray(v, float))
    return float(v[int(math.floor((1.0 - PASS) * len(v) + 1e-9))])


def boot_ci(v, stat, seed=SEED_BOOT, B=BOOT_B):
    v = np.asarray(v, float)
    rng = np.random.default_rng(seed)
    s = [stat(v[rng.integers(0, len(v), len(v))]) for _ in range(B)]
    return [float(np.percentile(s, 2.5)), float(np.percentile(s, 97.5))]


def load_raw(outdir: Path, phase: str) -> dict:
    return {p.stem: json.loads(p.read_text()) for p in sorted((outdir / "raw" / phase).glob("*.json"))}


def envelope_table(des, p1, key) -> dict:
    out = {}
    for d in DIE_SIZES:
        v = [key(p1[i]) for i, r in des["layouts"].items() if "p1" in r["sets"] and r["die_size_mm"] == d and i in p1]
        if not v:
            continue
        out[f"{d:.1f}"] = {"P_W": env_quantile(v), "ci95_boot": boot_ci(v, env_quantile), "n_layouts": len(v),
                           "min_W": float(min(v)), "median_W": float(np.median(v)), "max_W": float(max(v))}
    return out


def levels(outdir: Path, des: dict) -> dict:
    p1 = load_raw(outdir, "p1")
    env_kT = envelope_table(des, p1, lambda x: x["kT"]["P_lim"])
    env_60 = envelope_table(des, p1, lambda x: x["kT"]["P60"])
    lv = {"P_hi_W": float(math.floor(min(e["P_W"] for e in env_kT.values()))),
          "P_lo_W": float(math.floor(min(e["P_W"] for e in env_60.values()))),
          "rule": "P_hi = floor(min_d envelope_kT(d)); P_lo = floor(min_d same order statistic of P60) (P1 note s.1)",
          "env_kT": env_kT, "env_P60": env_60, "n_p1": len(p1)}
    (outdir / "raw" / "levels.json").write_text(json.dumps(lv, indent=1))
    print(json.dumps({k: lv[k] for k in ("P_hi_W", "P_lo_W")}))
    return lv


def p2_stats(T: np.ndarray, sw_slices, tbp: float) -> dict:
    """T: (K layouts, 2n dies) per-die Tj max of one stratum at one load.  Returns predictor errors and spreads."""
    K = T.shape[0]
    tot = T.sum(axis=0)
    loo_pos = (tot[None, :] - T) / (K - 1)  # die-position LOLO
    loo_cell = (T.sum() - T.sum(axis=1)) / ((K - 1) * T.shape[1])
    err = {"stratum_mean": T - T.mean(), "die_size_cell_mean": T - loo_cell[:, None], "die_position_lookup": T - loo_pos}
    out = {"predictors": {}}
    for name, e in err.items():
        a = np.abs(e)
        rng = np.random.default_rng(SEED_BOOT)
        bs = [np.percentile(a[rng.integers(0, K, K)].ravel(), 95) for _ in range(BOOT_B)]
        out["predictors"][name] = {"p95_abs_err_K": float(np.percentile(a.ravel(), 95)),
                                   "ci95_boot": [float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))],
                                   "max_abs_err_K": float(a.max()),
                                   "p95_rel_err_local": float(np.percentile((a / (T - tbp)).ravel(), 95))}
    tm = T.max(axis=1)
    pairs = np.array([abs(tm[a] - tm[b]) for a, b in combinations(range(K), 2)])
    spreads = np.array([[T[j, s].max() - T[j, s].min() for s in sw_slices] for j in range(K)])  # (K, 2)
    sp_err = np.abs(spreads - spreads.mean())
    out["spread"] = {"tjmax_layout_sd_K": float(tm.std(ddof=1)), "tjmax_layout_range_K": float(np.ptp(tm)),
                     "tj_die_sd_K": float(T.std(ddof=1)),
                     "pair_absdiff_median_K": float(np.median(pairs)),
                     "pair_absdiff_p95_K": float(np.percentile(pairs, 95)), "pair_absdiff_max_K": float(pairs.max()),
                     "n_pairs": int(len(pairs)),
                     "switch_spread_mean_K": float(spreads.mean()), "switch_spread_sd_K": float(spreads.std(ddof=1)),
                     "switch_spread_stratum_mean_err_p95_K": float(np.percentile(sp_err.ravel(), 95)),
                     "rise_hot_median_K": float(np.median(tm) - TC)}
    return out


def report(outdir: Path, des: dict):
    p1, p2, bias = load_raw(outdir, "p1"), load_raw(outdir, "p2"), load_raw(outdir, "bias")
    lv = json.loads((outdir / "raw" / "levels.json").read_text())
    loads = {"lo": lv["P_lo_W"], "hi": lv["P_hi_W"]}
    L = des["layouts"]
    # ---- sanity over every solve
    allsolves = []
    for x in p1.values():
        allsolves += [x["ck"]["solve"], *x["kT"]["solves"], *(s for v in x["variants"].values() for s in v["solves"])]
    for x in p2.values():
        allsolves += list(x["loads"].values())
    for x in bias.values():
        allsolves += [s for lvl in x["levels"].values() for s in lvl.values()]
    sanity = {"n_solves": len(allsolves), "max_energy_balance": max(abs(s["energy_balance"]) for s in allsolves),
              "max_picard_iters": max(s["picard_iters"] for s in allsolves),
              "kT_limit_below_constk_all": all(x["kT"]["P_lim"] < x["ck"]["P_lim"] for x in p1.values()),
              "variant_signs": {n: (lambda s: s)(sum((x["variants"][n]["P_lim"] - x["kT"]["P_lim"]) > 0 for x in
                                                   p1.values())) for n in VARIANTS},
              "n_p1": len(p1)}
    # ---- P1 envelopes
    pw = {"kT_nominal": envelope_table(des, p1, lambda x: x["kT"]["P_lim"]),
          "constant_k": envelope_table(des, p1, lambda x: x["ck"]["P_lim"])}
    for n in VARIANTS:
        pw[f"kT_{n}"] = envelope_table(des, p1, lambda x, n=n: x["variants"][n]["P_lim"])
    by_dies = {}
    for n in DIE_COUNTS:
        v = [p1[i]["kT"]["P_lim"] for i, r in L.items() if i in p1 and r["dies_per_switch"] == n]
        if v:
            by_dies[str(n)] = {"P_W": env_quantile(v), "n_layouts": len(v), "min_W": min(v), "median_W": float(np.median(v))}
    all_lim = [x["kT"]["P_lim"] for x in p1.values()]
    frac60 = {f"{d:.1f}": float(np.mean([p1[i]["kT"]["P_lim"] >= 60.0 for i, r in L.items()
                                         if i in p1 and r["die_size_mm"] == d])) for d in DIE_SIZES}
    # rises at the two levels on the balanced set, from each layout's fit (interpolation; checked below)
    rises = {}
    for key, P in loads.items():
        rr = {i: p1[i]["kT"]["fit_a_b"][0] * P + p1[i]["kT"]["fit_a_b"][1] * P * P for i in p1}
        v = np.array(list(rr.values()))
        rises[key] = {"P_W": P, "median_K": float(np.median(v)), "p05_K": float(np.percentile(v, 5)),
                      "p95_K": float(np.percentile(v, 95)), "max_K": float(v.max()),
                      "frac_in_60_110": float(np.mean((v >= 60) & (v <= RISE_LIM))),
                      "frac_le_110": float(np.mean(v <= RISE_LIM)),
                      "by_dies_median_K": {str(n): float(np.median([rr[i] for i in rr if L[i]["dies_per_switch"] == n]))
                                           for n in DIE_COUNTS}}
    interp_err = [max(p2[i]["loads"][k]["tj_max"]) - TC - (p1[i]["kT"]["fit_a_b"][0] * P + p1[i]["kT"]["fit_a_b"][1] * P * P)
                  for i in p1 if i in p2 for k, P in loads.items()]
    sanity["fit_interp_max_abs_err_K"] = float(np.max(np.abs(interp_err))) if interp_err else None
    sanity["fit_interp_n"] = len(interp_err)
    p60 = {}
    for d in DIE_SIZES:
        for n in DIE_COUNTS:
            v = [p1[i]["kT"]["P60"] for i, r in L.items() if i in p1 and r["die_size_mm"] == d and r["dies_per_switch"] == n]
            if v:
                p60[f"{d:.1f}/{n}"] = {"median_W": float(np.median(v)), "min_W": min(v), "max_W": max(v), "n": len(v)}
    o003 = {"rule": "power per die per reference so that its hottest die rises 60 K above coolant (O003 scope); "
                    "single common value for generator development layouts: P_lo",
            "P_lo_W": loads["lo"], "tj_max_at_60K_rise_C": TC + RISE_LO - 273.15, "headroom_to_175C_K": RISE_LIM - RISE_LO,
            "P60_W_by_die_size": envelope_table(des, p1, lambda x: x["kT"]["P60"]),
            "P60_W_by_die_size_and_dies": p60,
            "P60_over_P_lim_median": float(np.median([x["kT"]["P60"] / x["kT"]["P_lim"] for x in p1.values()]))}
    # ---- level bias
    lb = []
    for i, x in bias.items():
        for key in loads:
            tv = {lv: np.array(x["levels"][str(lv)][key]["tj_max"]) for lv in BIAS_LEVELS}
            tv[LEVEL] = np.array(p2[i]["loads"][key]["tj_max"])
            t0, t1, t2 = tv[0], tv[1], tv[2]
            gci = [tl.gci_three_grid(a, b, c)["gci"] for a, b, c in zip(t0, t1, t2, strict=True)]
            tu = tv[LEVEL]
            a, b = (p1[i]["kT"]["fit_a_b"] if i in p1 else (None, None))
            lb.append({"id": i, "load": key, "P_W": loads[key], "bias_used_minus_L2_per_die_K": (tu - t2).tolist(),
                       "bias_L1_minus_L2_per_die_K": (t1 - t2).tolist(), "gci_L012_per_die_K": gci,
                       "tjmax_bias_used_minus_L2_K": float(tu.max() - t2.max()),
                       "spread_bias_K": float(np.ptp(tu) - np.ptp(t2)),
                       "rise_L2_K": float(t2.max() - TC),
                       "P_lim_bias_W": (None if a is None else float(-(tu.max() - t2.max()) / (a + 2 * b * loads[key])))})
    level_bias = {"layouts": lb, "n_layouts": len(bias), "levels": f"L{LEVEL} (used) minus L2 (finest)"}
    if lb:
        for key in loads:
            sub = [r for r in lb if r["load"] == key]
            perdie = np.concatenate([r["bias_used_minus_L2_per_die_K"] for r in sub])
            level_bias[key] = {"P_W": loads[key], "n_layouts": len(sub), "n_dies": int(perdie.size),
                               "max_abs_per_die_K": float(np.abs(perdie).max()), "mean_per_die_K": float(perdie.mean()),
                               "range_per_die_K": [float(perdie.min()), float(perdie.max())],
                               "sd_layout_tjmax_bias_K": float(np.std([r["tjmax_bias_used_minus_L2_K"] for r in sub], ddof=1)),
                               "max_abs_spread_bias_K": float(max(abs(r["spread_bias_K"]) for r in sub)),
                               "max_gci_K": float(max(max(r["gci_L012_per_die_K"]) for r in sub)),
                               "max_abs_L1_minus_L2_K": float(max(np.abs(r["bias_L1_minus_L2_per_die_K"]).max() for r in sub))}
        pb = [r["P_lim_bias_W"] for r in lb if r["load"] == "hi" and r["P_lim_bias_W"] is not None]
        level_bias["hi"]["P_lim_bias_W_range"] = [min(pb), max(pb)] if pb else None
    # ---- P2 nulls
    nulls, p2_tab = [], {}
    tbp_coef = 1.0 / (H * ((86e-3) * (56e-3)))
    for k, (fam, n) in enumerate(STRATA):
        ids = sorted([i for i, r in L.items() if r["stratum"] == k and "p2" in r["sets"] and i in p2],
                     key=lambda i: L[i]["pool_index"])
        if len(ids) < 3:
            continue
        sw = [slice(0, n), slice(n, 2 * n)]
        for key, P in loads.items():
            T = np.array([p2[i]["loads"][key]["tj_max"] for i in ids])
            st = p2_stats(T, sw, TC + 2 * n * P * tbp_coef)
            p2_tab[f"{fam}/{n}/{key}"] = st
            for name, v in st["predictors"].items():
                nulls.append({"stratum": f"{fam}/{n}", "die_size_mm": L[ids[0]]["die_size_mm"], "load": key,
                              "load_W": P, "predictor": name, "p95_abs_err_K": v["p95_abs_err_K"],
                              "ci95_boot_K": v["ci95_boot"], "max_abs_err_K": v["max_abs_err_K"],
                              "p95_rel_err_local": v["p95_rel_err_local"], "n_layouts": len(ids),
                              "n_dies": int(T.size)})
    layouts_out = []
    for i, r in L.items():
        row = {k: r[k] for k in ("id", "family", "dies_per_switch", "die_size_mm", "seed", "pool_index", "sets",
                                 "fingerprint")}
        if i in p1:
            row.update({"P_lim_ck_W": p1[i]["ck"]["P_lim"], "P_lim_kT_W": p1[i]["kT"]["P_lim"],
                        "P60_kT_W": p1[i]["kT"]["P60"],
                        "P_lim_variants_W": {n: v["P_lim"] for n, v in p1[i]["variants"].items()}})
        if i in p2:
            row["tj_max_per_die_K"] = {k: p2[i]["loads"][k]["tj_max"] for k in loads}
        layouts_out.append(row)
    cpu = sum(x["cpu_s"] for ph in (p1, p2, bias) for x in ph.values())
    res = {"task": "T0167", "objective": "O006", "kind": "research notes, never evidence (O006 F4)",
           "seeds": {"die_size_assignment": SEED_ASSIGN, "generator_pool_by_stratum": {f"{f}/{n}": SEED_POOL0 + k for k, (f, n)
                                                                                     in enumerate(STRATA)},
                     "bootstrap": SEED_BOOT, "list": [SEED_ASSIGN, *(SEED_POOL0 + k for k in range(len(STRATA))), SEED_BOOT]},
           "settings": {"level": LEVEL, "T_c_K": TC, "h_W_m2K": H, "Tj_limit_K": TJ_LIM, "pass_fraction": PASS,
                        "secant_tol_K": TOL_K, "variants": VARIANTS},
           "prereg": json.loads((outdir / "raw" / "prereg.json").read_text()),
           "sample": {"n_layouts": len(L), "n_p1": len(p1), "n_p2": len(p2), "n_bias": len(bias),
                      "p2_die_size_by_stratum": des["p2_die_size_by_stratum"],
                      "p1_cells_family_dies_size": len({(L[i]["family"], L[i]["dies_per_switch"], L[i]["die_size_mm"]) for i in p1})},
           "power_limit_W_by_die_size": pw, "power_limit_kT_W_by_dies": by_dies,
           "power_limit_kT_all_sizes_W": {"P_W": env_quantile(all_lim), "n_layouts": len(all_lim)} if all_lim else None,
           "frac_layouts_tj_le_175C_at_60W": frac60,
           "recommended_load_levels_W": {"P_lo": loads["lo"], "P_hi": loads["hi"], "rule": lv["rule"],
                                         "rises_balanced_set": rises},
           "o003_operating_point": o003, "level_bias_K": level_bias, "nulls": nulls, "p2_tables": p2_tab,
           "sanity": sanity, "compute_cpu_s": cpu, "layouts": layouts_out}
    (outdir / "results.json").write_text(json.dumps(res, indent=1))
    print(json.dumps({k: res[k] for k in ("sanity", "compute_cpu_s")}, indent=1))


# ------------------------------------------------------------------------------------------------ checks
def check():
    """Grid reuse == solve_layout_level; nominal-valued variants reproduce the coded laws; constant k is linear."""
    lay = generate_layouts(1, SEED_POOL0 + 14, family="u_shaped", dies_per_switch=6)[0]
    g = tl.build_layout_grid(lay, 0)
    out = {}
    for ck, P in ((True, 1.0), (False, 40.0)):
        ref = tl.solve_layout_level(lay, level=0, power_W=P, h=H, T_c=TC, constant_k=ck)["values"]
        mine = solve(lay, g, P, materials(g, constant=ck))
        out[f"wrapper_vs_solve_layout_level_ck{ck}"] = max(abs(ref[f"die{i}.tj_max"] - t) for i, t in enumerate(mine["tj_max"]))
    nom = solve(lay, g, 40.0, materials(g))["tj_max"]
    same = solve(lay, g, 40.0, materials(g, {"sic": (370.0, -1.49), "sac": 4.2e-3}))["tj_max"]
    out["nominal_valued_variant_vs_coded"] = max(abs(a - b) for a, b in zip(nom, same, strict=True))
    a = solve(lay, g, 1.0, materials(g, constant=True))["tj_max"]
    b = solve(lay, g, 2.0, materials(g, constant=True))["tj_max"]
    out["constk_linearity"] = max(abs((y - TC) / (x - TC) - 2.0) for x, y in zip(a, b, strict=True))
    print(json.dumps(out, indent=1))
    assert all(v < 1e-8 for v in out.values()), out
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("phase", choices=["design", "check", "p1", "levels", "p2", "bias", "report"])
    ap.add_argument("--shard", type=int, default=0)
    ap.add_argument("--nshards", type=int, default=1)
    ap.add_argument("--smoke", action="store_true")
    a = ap.parse_args()
    outdir = Path(os.environ["TMPDIR"]) / "o006_p1_smoke" if a.smoke else ROOT / "research" / "o006_p1"
    (outdir / "raw").mkdir(parents=True, exist_ok=True)
    dfile = outdir / "raw" / "design.json"
    if a.phase == "check":
        out = check()
        (outdir / "raw" / "check.json").write_text(json.dumps(out, indent=1))
        return
    if not dfile.exists():
        dfile.write_text(json.dumps(design(a.smoke), indent=1))
    des = json.loads(dfile.read_text())
    if a.phase == "design":
        from collections import Counter
        L = des["layouts"].values()
        print(len(des["layouts"]), Counter(s for r in L for s in r["sets"]),
              Counter(r["die_size_mm"] for r in L if "p1" in r["sets"]), des["p2_die_size_by_stratum"])
    elif a.phase == "p1":
        pf = outdir / "raw" / "prereg.json"
        if not pf.exists():
            pf.write_text(json.dumps({"written_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                                      "sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in NOTES}}))
        run_phase("p1", outdir, des, a.shard, a.nshards)
    elif a.phase == "levels":
        levels(outdir, des)
    elif a.phase in ("p2", "bias"):
        lv = json.loads((outdir / "raw" / "levels.json").read_text())
        run_phase(a.phase, outdir, des, a.shard, a.nshards, {"lo": lv["P_lo_W"], "hi": lv["P_hi_W"]})
    elif a.phase == "report":
        report(outdir, des)


if __name__ == "__main__":
    main()
