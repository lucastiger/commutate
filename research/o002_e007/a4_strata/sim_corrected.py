"""T0456 step 3 (O002, E007 design-time; not evidence): the corrected per-cell power simulation (review T0420 item 2;
T0398's recommendation). Bound V4 through research/o002_e007/stats_sim_dev.judge/run_cell (the judging implementation).

Generative model, per (family, dies) stratum s, layout j, switch w in {HS, LS}, die position i (die_index), load l:
  reference rise  rise[j,w,i] = R_s + P_s[w,i] + sa_c * za_j + sv_c * zv[j,w,i];  rise at 0.5 P_ref = g_s * rise at P_ref
  L1 error        e_l[j,w,i] = b_{s,w,l} + Q_{s,w,i,l} + sc_{c,l} * zc_l[j,w] + sd_{c,l} * zd_l[j,w,i]
Fixed effects measured per stratum on the development rows: R_s (mean rise), P_s (die-position profile of the reference
rise), g_s (half-load rise ratio), b_{s,w,l} (HS / LS offset), Q_{s,w,i,l} (die-position profile of the L1 die deviation
around its (layout, switch) mean). Random scales pooled per (family, band) cell c from residual sums of squares with
their degrees of freedom: sa (layout mean rise), sv (reference die residual), sc ((layout, switch) mean error around b),
sd (die error residual around Q). Between-load correlation of zc and zd measured (pooled). z ~ N(0,1) or t3/sqrt(3)
(reference terms clipped at 6 sd, as stats_sim). Known bias of the design: a fixed profile estimated from n_lay layouts
carries noise of variance sd^2/n_lay, so die-level error is inflated by ~(1 + 1/n_lay): conservative for A3/A4 power.

Consistency check (declared before any simulated value was seen; gates everything after it): at T0398's structure (15
strata x 3 layouts, both loads) simulate the pooled point A4 in 1000 data sets; PASS iff the measured A4 of
experiments/drafts/E007.dev_rows.json lies within the simulated 5-95 % range AND |median / measured - 1| <= 0.25. A1, A2,
A3 are reported the same way, not gated. Per stratum, for the 3 strata with 9 layouts, the simulated per-stratum A4 at
m = 9 beside the measured one (reported).
Then: joint power, A4's power alone and V4 coverage (every statistic; min reported) at m = 20, 24, 32, 40, normal and
t3; kill side: the model rescaled (offsets kb, layout-level kc, die-level kd) so that the truth is 1.2 x each kill
threshold jointly (A1 1.8 K, A2 0.18, A4 1.2) at each m; P(K1), P(K2), P(K3) fire.
Seeds: numpy SeedSequence([20261456, 7, cell]) (20261456 is in E007's config.seeds.forbidden).
usage: uv run python research/o002_e007/a4_strata/sim_corrected.py [--reps 1000] [--t-reps 300] [--parts check,power,kill]"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE.parent))
import e007_metrics as em  # noqa: E402
import stats_sim as ss  # noqa: E402
import stats_sim_dev as sdv  # noqa: E402

SEED = 20261456
M_GRID = (20, 24, 32, 40)
CK = HERE / "sim_corrected_checkpoint.json"
OUT = HERE / "sim_corrected.json"
T0398 = ROOT / "experiments" / "drafts" / "E007.dev_rows.json"
COMB = HERE / "work" / "combined_9_rows.json"
LOADS = ss.LOADS
BAND = {n: ("2-3" if n <= 3 else "4-6") for n in ss.DIES}


def load_rows() -> tuple[list, dict]:
    rows = json.loads(T0398.read_text())["rows"]
    src = {"T0398": str(T0398.relative_to(ROOT))}
    if COMB.exists():
        comb = json.loads(COMB.read_text())["rows"]
        repl = {r["stratum"] for r in comb if r["kind"] == "die"}
        rows = [r for r in rows if r.get("stratum") not in repl] + comb
        src["combined_9"] = sorted(repl)
    return rows, src


def fit(rows: list) -> dict:
    die = [r for r in rows if r["kind"] == "die"]
    st, ssq = {}, {}
    rho_num = {"c": [0.0, 0.0, 0.0], "d": [0.0, 0.0, 0.0]}
    for f, n in ss.STRATA:
        sn = f"{f}/{n}"
        dr = [r for r in die if r["stratum"] == sn]
        lays = sorted({r["layout"] for r in dr})
        L = len(lays)
        A = {ld: np.zeros((L, 2, n)) for ld in LOADS}
        Er = {ld: np.zeros((L, 2, n)) for ld in LOADS}
        for r in dr:
            j, w = lays.index(r["layout"]), ("HS", "LS").index(r["switch"])
            A[r["load"]][j, w, r["die_index"]] = r["rise_ref_K"]
            Er[r["load"]][j, w, r["die_index"]] = r["tj_l1_K"] - r["tj_ref_K"]
        rise = A["P_ref"]
        mu = rise.mean(axis=(1, 2))
        P = (rise - mu[:, None, None]).mean(axis=0)
        v = rise - mu[:, None, None] - P[None]
        rec = {"n_layouts": L, "R": float(mu.mean()), "P": P.tolist(),
               "g": float(A["half_P_ref"].sum() / rise.sum()), "b": {}, "Q": {}}
        c = f"{f}/{BAND[n]}"
        S = ssq.setdefault(c, {"sa": [0.0, 0], "sv": [0.0, 0], **{f"{k}_{ld}": [0.0, 0] for k in ("sc", "sd")
                                                                    for ld in LOADS}})
        S["sa"][0] += float(np.sum((mu - mu.mean()) ** 2))
        S["sa"][1] += L - 1
        S["sv"][0] += float(np.sum(v ** 2))
        S["sv"][1] += (L - 1) * (2 * n - 1)
        cd, dd = {}, {}
        for ld in LOADS:
            e = Er[ld]
            lsm = e.mean(axis=2)  # (L, 2) layout-switch means
            b = lsm.mean(axis=0)  # (2,)
            d = e - lsm[:, :, None]
            Q = d.mean(axis=0)  # (2, n)
            res = d - Q[None]
            rec["b"][ld], rec["Q"][ld] = b.tolist(), Q.tolist()
            S[f"sc_{ld}"][0] += float(np.sum((lsm - b[None]) ** 2))
            S[f"sc_{ld}"][1] += 2 * (L - 1)
            S[f"sd_{ld}"][0] += float(np.sum(res ** 2))
            S[f"sd_{ld}"][1] += 2 * (L - 1) * (n - 1)
            cd[ld], dd[ld] = (lsm - b[None]).ravel(), res.ravel()
        for k, (x, y) in (("c", (cd["P_ref"], cd["half_P_ref"])), ("d", (dd["P_ref"], dd["half_P_ref"]))):
            rho_num[k][0] += float(x @ y)
            rho_num[k][1] += float(x @ x)
            rho_num[k][2] += float(y @ y)
        st[sn] = rec
    cells = {c: {k: math.sqrt(v[0] / v[1]) if v[1] > 0 else 0.0 for k, v in S.items()} | {
        "dof": {k: v[1] for k, v in S.items()}} for c, S in ssq.items()}
    rho = {k: v[0] / math.sqrt(v[1] * v[2]) if v[1] > 0 and v[2] > 0 else 0.0 for k, v in rho_num.items()}
    return {"strata": st, "cells": cells, "rho": rho, "k": {"kb": 1.0, "kc": 1.0, "kd": 1.0}}


def gen(m: int, model: str, par: dict, rng: np.random.Generator) -> list[dict]:
    out = []
    kb, kc, kd = par["k"]["kb"], par["k"]["kc"], par["k"]["kd"]
    for f, n in ss.STRATA:
        st, ce = par["strata"][f"{f}/{n}"], par["cells"][f"{f}/{BAND[n]}"]
        za, zv = (np.clip(ss.zdraw(rng, model, sh), -6.0, 6.0) for sh in ((m, 1, 1), (m, 2, n)))
        rise = st["R"] + np.asarray(st["P"])[None] + ce["sa"] * za + ce["sv"] * zv
        zc1, zd1 = ss.zdraw(rng, model, (m, 2, 1)), ss.zdraw(rng, model, (m, 2, n))
        zc2, zd2 = ss.zdraw(rng, model, (m, 2, 1)), ss.zdraw(rng, model, (m, 2, n))
        rc, rd = par["rho"]["c"], par["rho"]["d"]
        err = {}
        for ld, (zc, zd) in (("P_ref", (zc1, zd1)), ("half_P_ref", (rc * zc1 + math.sqrt(1 - rc * rc) * zc2,
                                                                    rd * zd1 + math.sqrt(1 - rd * rd) * zd2))):
            b = np.asarray(st["b"][ld])[None, :, None]
            Q = np.asarray(st["Q"][ld])[None]
            err[ld] = kb * b + kd * Q + kc * ce[f"sc_{ld}"] * zc + kd * ce[f"sd_{ld}"] * zd
        out.append({"family": f, "dies": n, "rise": {"P_ref": rise, "half_P_ref": st["g"] * rise}, "err": err})
    return out


ss.gen = gen
sdv.gen = gen


def point_stats(rows: list) -> dict:
    from mfos.metrics import compute
    return {a: float(compute(sp["fn"], ss.where(rows, sp["where"]), pred=sp["pred"], ref=sp["ref"], strata=sp["strata"],
                             params=sp["params"])) for a, sp in ss.SPECS.items()}


def measured(rows: list) -> dict:
    return point_stats([r for r in rows if r["kind"] in ("die", "layout", "switch")])


def gen_struct(par: dict, model: str, rng, m_by: dict) -> list[dict]:
    """gen with a per-stratum layout count (T0398's 3 everywhere, or 9 in the 3 extended strata)."""
    out = []
    for m in sorted(set(m_by.values())):
        keep = [s for s in gen(m, model, par, rng) if m_by[f"{s['family']}/{s['dies']}"] == m]
        out += keep
    return out


def check(par: dict, reps: int, seed: int, meas: dict, meas_strata: dict) -> dict:
    out = {}
    for mo in ss.MODELS:
        rng = np.random.default_rng(np.random.SeedSequence([SEED, 7, 1, ss.MODELS.index(mo)]))
        sims = [point_stats(ss.all_rows(gen(3, mo, par, rng))) for _ in range(reps)]
        r = {}
        for a in ss.SPECS:
            x = np.array([s[a] for s in sims])
            lo, med, hi = (float(v) for v in np.quantile(x, [0.05, 0.5, 0.95]))
            r[a] = {"measured": meas[a], "sim_p05": lo, "sim_median": med, "sim_p95": hi,
                    "within_5_95": bool(lo <= meas[a] <= hi), "median_rel": med / meas[a] - 1.0}
        r["A4"]["pass"] = bool(r["A4"]["within_5_95"] and abs(r["A4"]["median_rel"]) <= 0.25)
        # per-stratum A4 at m = 9 for the extended strata
        ps = {}
        rng = np.random.default_rng(np.random.SeedSequence([SEED, 7, 2, ss.MODELS.index(mo)]))
        for sn, mv in meas_strata.items():
            f, n = sn.split("/")
            vals = []
            for _ in range(max(reps // 2, 100)):
                rows = ss.all_rows([s for s in gen(9, mo, par, rng) if s["family"] == f and s["dies"] == int(n)])
                vals.append(point_stats(rows)["A4"])
            q = np.quantile(vals, [0.05, 0.5, 0.95])
            ps[sn] = {"measured_9": mv, "sim_p05": float(q[0]), "sim_median": float(q[1]), "sim_p95": float(q[2]),
                      "within_5_95": bool(q[0] <= mv <= q[2]), "sim_P_above_0.3": float(np.mean(np.array(vals) > 0.3))}
        r["per_stratum_A4_m9"] = ps
        out[mo] = r
    out["pass"] = all(out[mo]["A4"]["pass"] for mo in ss.MODELS)
    return out


def calibrate_kill(par: dict, model: str, m: int, t_reps: int, seed: int) -> tuple[dict, dict]:
    tgt = {"A1": 1.2 * ss.THR["K1"], "A2": 1.2 * ss.THR["K2"], "A4": 1.2 * ss.THR["K3"]}
    p = json.loads(json.dumps(par))
    for _ in range(14):
        tr = ss.truth(p, model, m, t_reps, seed)
        p["k"]["kd"] *= tgt["A4"] / tr["A4"]
        p["k"]["kc"] *= tgt["A1"] / tr["A1"]
        p["k"]["kb"] *= tgt["A2"] / tr["A2"]
    return p, ss.truth(p, model, m, t_reps, seed)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", type=int, default=1000)
    ap.add_argument("--t-reps", type=int, default=300)
    ap.add_argument("--parts", default="check,power,kill")
    a = ap.parse_args()
    rows, src = load_rows()
    par = fit(rows)
    meas = measured(json.loads(T0398.read_text())["rows"])
    a4s = {}
    if COMB.exists():
        cr = json.loads(COMB.read_text())["rows"]
        for sn in sorted({r["stratum"] for r in cr if r["kind"] == "die"}):
            a4s[sn] = point_stats([r for r in cr if r.get("stratum") == sn])["A4"]
    ck = json.loads(CK.read_text()) if CK.exists() else {}
    tag = json.dumps([a.reps, a.t_reps, src, em.__name__])
    if ck.get("tag") != tag:
        ck = {"tag": tag, "cells": {}}
    t0 = time.time()
    parts = a.parts.split(",")
    if "check" in parts or "consistency" not in ck:
        ck["consistency"] = check(par, a.reps, SEED, meas, a4s)
        CK.write_text(json.dumps(ck, indent=1))
        print(f"[{time.time() - t0:6.0f} s] consistency {json.dumps({mo: ck['consistency'][mo]['A4'] for mo in ss.MODELS})}",
              flush=True)
    if not ck["consistency"]["pass"]:
        print("consistency check FAILED: no power reported")
    else:
        for part in ("power", "kill"):
            if part not in parts:
                continue
            for m in M_GRID:
                for mo in ss.MODELS:
                    key = f"{part}|{mo}|{m}"
                    if key in ck["cells"]:
                        continue
                    ci = (M_GRID.index(m) * 2 + ss.MODELS.index(mo)) + (100 if part == "kill" else 0)
                    cs = int(np.random.SeedSequence([SEED, 7, 3, ci]).generate_state(1)[0])
                    p, trc = (par, None) if part == "power" else calibrate_kill(par, mo, m, a.t_reps, cs)
                    tr = ss.truth(p, mo, m, 4 * a.t_reps, cs + 7919)
                    res = sdv.run_cell(m, mo, p, tr, a.reps, cs + 50021)
                    ck["cells"][key] = {"seed": cs, "k": p["k"], "truth_calibration": trc, "truth": tr, **res}
                    CK.write_text(json.dumps(ck, indent=1))
                    print(f"[{time.time() - t0:6.0f} s] {key} truth A4 {tr['A4']:.3f} joint {res['power_joint']:.3f} "
                          f"A4 {res['power_each']['A4']:.3f} fire {res['p_fire']} cov_min "
                          f"{min(res['coverage'].values()):.3f}", flush=True)
    out = {"task": "T0456", "experiment": "E007", "kind": "corrected per-cell power simulation (not evidence)",
           "generated": time.strftime("%Y-%m-%dT%H:%M:%S"), "seed": SEED, "reps_per_cell": a.reps,
           "truth_reps": 4 * a.t_reps, "bound": sdv.V4, "mc_se_at_0.95": math.sqrt(0.95 * 0.05 / a.reps),
           "mc_se_at_0.5": math.sqrt(0.25 / a.reps), "sources": src, "model": par, "measured_T0398": meas,
           "consistency": ck["consistency"], "cells": ck["cells"]}
    OUT.write_text(json.dumps(out, indent=1, default=float))
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
