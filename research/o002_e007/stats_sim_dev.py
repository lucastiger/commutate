"""O002 F3 follow-up simulation for E007 (T0398): the selected bound V4 on the development rows' structure, power of the
as-measured L1 at m = 20, 24, 32, 40, and kill-side firing probabilities. Not evidence; design-time only.

Run from the repository root: ``uv run python research/o002_e007/stats_sim_dev.py [--rows experiments/drafts/E007.dev_rows.json]``.
Checkpoints every cell to sim_checkpoint_t0398.json (resume by re-running); writes f3_dev_simulation.json.

Reuses stats_sim.py (T0396, n5) unchanged: its generative model (gen), truth, calibrate, die rows -> layout/switch rows
through e007_metrics, and the bound through e007_metrics.quantile_ci with V4's variant (t(K-1), outward rounding,
Bonferroni ratio, CISpec level 0.94 = one-sided 97 %), i.e. the implementation that judges. Seeds: SEED = 20261399
(listed in E007's config.seeds.forbidden), one fresh sub-seed per cell.

Scenarios (targets A1 K, A2, A4 at the max over loads / P_ref; A3 follows):
  n1        n5's as-measured L1 (A1 0.189 K, A2 0.0102, A4 0.366), stats_sim.SCENARIOS['n1']
  dev       the same model re-targeted to A1, A2 and A4 as measured on T0398's development rows (point estimates)
  dev_cells error scales measured on the development rows per (family, band) cell: layout-level error sd (sc),
            die-level error sd (sd), per-stratum mean bias (b_s), reference mean rise R and mean switch spread S per
            stratum; the reference's layout and die variation (sa, sv) stay n1's (3 layouts per stratum cannot measure
            them). No calibration: the truth follows from the measured scales (reported)
  alt, edge, kill   as n5 (0.6 x each threshold; at the pass thresholds; at the kill thresholds)
  beyond_kill  1.2 x each kill threshold (A1 1.8 K, A2 0.18, A4 1.2): the probability that K1, K2, K3 each fire
Parts:
  f3_dev   coverage of V4 (A1-A4 upper, K1-K3 lower) at the development rows' structure (m = 3 per stratum, 15 strata,
           2 loads) in every scenario, normal and t3 errors; reported as min over scenarios per statistic and model
  power    joint power and each criterion's power (A4 alone) for n1, dev and dev_cells at m = 20, 24, 32, 40
  kill     P(K1), P(K2), P(K3) fire (lower bound above the kill threshold) and P(any) in beyond_kill at the same m
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import e007_metrics as em  # noqa: E402
import stats_sim as ss  # noqa: E402

SEED = 20261399
V4 = "V4_t_outward_bonferroni_l094"
VAR = dict(ss.VARIANTS[V4])
M_DEV = 3
M_GRID = (20, 24, 32, 40)
KILL_FACTOR = 1.2
CK = HERE / "sim_checkpoint_t0398.json"
OUT = HERE / "f3_dev_simulation.json"
CELL_BAND = {n: ("2-3" if n <= 3 else "4-6") for n in ss.DIES}


# ------------------------------------------------------------------------------------------------ measured scenario
def measure(rows_path: Path) -> dict:
    """Targets and per-cell error scales from the development rows (die/layout/switch rows of e007_run.py --dev)."""
    d = json.loads(rows_path.read_text())
    rows, met = d["rows"], d["meta"]["metrics"]
    tgt = (met["dtj_pair_err_p95_K_max_load"]["value"], met["tjavg_local_rel_err_p95_max_load"]["value"],
           met["switch_spread_err_ratio_vs_stratum_mean"]["value"])
    die = [r for r in rows if r["kind"] == "die" and r["load"] == "P_ref"]
    strata: dict = {}
    for f, n in ss.STRATA:
        dr = [r for r in die if r["family"] == f and r["dies"] == n]
        lays = sorted({r["layout"] for r in dr})
        e = {lay: np.array([r["tj_l1_K"] - r["tj_ref_K"] for r in dr if r["layout"] == lay]) for lay in lays}
        sp = []
        for lay in lays:
            for sw in ("HS", "LS"):
                v = [r["rise_ref_K"] for r in dr if r["layout"] == lay and r["switch"] == sw]
                sp.append(max(v) - min(v))
        strata[f"{f}/{n}"] = {"R": float(np.mean([r["rise_ref_K"] for r in dr])), "S": float(np.mean(sp)),
                              "bias": float(np.mean(np.concatenate(list(e.values())))),
                              "lay_means": [float(x.mean()) for x in e.values()],
                              "die_dev": np.concatenate([x - x.mean() for x in e.values()]).tolist()}
    cells: dict = {}
    for f in ss.FAMILIES:
        for b in ("2-3", "4-6"):
            ks = [f"{f}/{n}" for n in ss.DIES if CELL_BAND[n] == b]
            lm = np.concatenate([np.array(strata[k]["lay_means"]) - strata[k]["bias"] for k in ks])
            dd = np.concatenate([strata[k]["die_dev"] for k in ks])
            nl = sum(len(strata[k]["lay_means"]) for k in ks)
            cells[f"{f}/{b}"] = {"sc": float(np.sqrt(np.sum(lm ** 2) / max(nl - len(ks), 1))),
                                 "sd": float(np.sqrt(np.sum(dd ** 2) / max(dd.size - nl, 1))), "n_layouts": nl}
    for v in strata.values():
        v.pop("lay_means")
        v.pop("die_dev")
    return {"targets": {"A1": tgt[0], "A2": tgt[1], "A4": tgt[2]}, "strata": strata, "cells": cells,
            "source": str(rows_path),
            "rows_sha256": __import__("hashlib").sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest()}


_GEN0 = ss.gen


def gen(m: int, model: str, par: dict, rng: np.random.Generator) -> list[dict]:
    """stats_sim.gen, or for par['cells'] (dev_cells) the same structure with per-stratum R, S, bias and per-cell sc, sd."""
    if "cells" not in par:
        return _GEN0(m, model, par, rng)
    out, rs = [], math.sqrt(1.0 - ss.RHO ** 2)
    for f, n in ss.STRATA:
        st, ce = par["strata"][f"{f}/{n}"], par["cells"][f"{f}/{CELL_BAND[n]}"]
        sv = ss.lin(n, ss.N1["sv"])
        u = np.linspace(-0.5, 0.5, n)[None, None, :]
        za, zv = (np.clip(ss.zdraw(rng, model, sh), -6.0, 6.0) for sh in ((m, 1, 1), (m, 2, n)))
        rise = st["R"] + st["S"] * u + ss.N1["sa"] * za + sv * zv
        b = st["bias"]
        zc, zd = ss.zdraw(rng, model, (m, 1, 1)), ss.zdraw(rng, model, (m, 2, n))
        zc2, zd2 = ss.zdraw(rng, model, (m, 1, 1)), ss.zdraw(rng, model, (m, 2, n))
        e_p = b + ce["sc"] * zc + ce["sd"] * zd
        e_h = ss.G_HALF * (b + ce["sc"] * (ss.RHO * zc + rs * zc2) + ce["sd"] * (ss.RHO * zd + rs * zd2))
        out.append({"family": f, "dies": n, "rise": {"P_ref": rise, "half_P_ref": ss.G_HALF * rise},
                    "err": {"P_ref": e_p, "half_P_ref": e_h}})
    return out


ss.gen = gen  # truth / calibrate / all_rows look gen up in stats_sim's namespace


# ------------------------------------------------------------------------------------------------ one cell
def judge(rows: list[dict]) -> dict:
    out = {}
    for a, sp in ss.SPECS.items():
        sub = ss.where(rows, sp["where"])
        out[a] = em.quantile_ci(sp["fn"], sub, pred=sp["pred"], ref=sp["ref"], strata=sp["strata"], params=sp["params"],
                                level=VAR["level"], cluster="layout",
                                **{k: v for k, v in VAR.items() if k != "level"})
    return out


def run_cell(m: int, model: str, par: dict, tr: dict, reps: int, seed: int) -> dict:
    rng = np.random.default_rng(seed)
    cov = {s: 0 for s in ss.THR}
    each = {a: 0 for a in ss.SPECS}
    fire = {k: 0 for k in ss.KILL_OF}
    joint = anyk = 0
    for _ in range(reps):
        r = judge(ss.all_rows(gen(m, model, par, rng)))
        for a in ss.SPECS:
            cov[a] += r[a][1][1] >= tr[a]
            each[a] += r[a][1][1] <= ss.THR[a]
        for k, a in ss.KILL_OF.items():
            cov[k] += r[a][1][0] <= tr[a]
            fire[k] += r[a][1][0] > ss.THR[k]
        joint += all(r[a][1][1] <= ss.THR[a] for a in ss.SPECS)
        anyk += any(r[a][1][0] > ss.THR[k] for k, a in ss.KILL_OF.items())
    return {"reps": reps, "coverage": {s: c / reps for s, c in cov.items()}, "power_joint": joint / reps,
            "power_each": {a: c / reps for a, c in each.items()}, "p_fire": {k: c / reps for k, c in fire.items()},
            "p_any_kill": anyk / reps}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", default=None, help="development rows (enables the dev and dev_cells scenarios)")
    ap.add_argument("--reps", type=int, default=1000)
    ap.add_argument("--t-reps", type=int, default=300)
    ap.add_argument("--parts", default="f3_dev,power,kill")
    a = ap.parse_args()
    ck = json.loads(CK.read_text()) if CK.exists() else {"cells": {}}
    meas = measure(Path(a.rows)) if a.rows else None
    scen = dict(ss.SCENARIOS)
    scen["beyond_kill"] = (KILL_FACTOR * ss.THR["K1"], KILL_FACTOR * ss.THR["K2"], KILL_FACTOR * ss.THR["K3"])
    if meas:
        scen["dev"] = (meas["targets"]["A1"], meas["targets"]["A2"], meas["targets"]["A4"])
        ck["measured"] = meas
    t0 = time.time()

    def cell(sc: str, mo: str, m: int) -> dict:
        key = f"{sc}|{mo}|{m}"
        tag = [scen[sc] if sc != "dev_cells" else meas["rows_sha256"], a.reps, a.t_reps]
        old = ck["cells"].get(key)
        if old is not None and old.get("tag") == json.dumps(tag):
            return old
        s_i = (list(scen) + ["dev_cells"]).index(sc)
        cs = SEED + 100003 * s_i + 1009 * ss.MODELS.index(mo) + m
        if sc == "dev_cells":
            par = {"strata": meas["strata"], "cells": meas["cells"]}
            tr_cal = None
        else:
            par, tr_cal = ss.calibrate(scen[sc], mo, m, a.t_reps, cs)
        tr = ss.truth(par, mo, m, 4 * a.t_reps, cs + 7919)
        res = run_cell(m, mo, par, tr, a.reps, cs + 50021)
        ck["cells"][key] = {"tag": json.dumps(tag), "seed": cs, "par": par if sc != "dev_cells" else "measured",
                            "truth_calibration": tr_cal, "truth": tr, **res}
        CK.write_text(json.dumps(ck, indent=1))
        print(f"[{time.time() - t0:7.0f} s] {key} joint {res['power_joint']:.3f} A4 {res['power_each']['A4']:.3f} "
              f"fire {res['p_fire']} cov_min {min(res['coverage'].values()):.3f}", flush=True)
        return ck["cells"][key]

    parts = a.parts.split(",")
    dev_scen = ["n1", "alt", "edge", "kill"] + (["dev", "dev_cells"] if meas else [])
    pow_scen = ["n1"] + (["dev", "dev_cells"] if meas else [])
    if "f3_dev" in parts:
        for sc in dev_scen:
            for mo in ss.MODELS:
                cell(sc, mo, M_DEV)
    if "power" in parts:
        for m in M_GRID:
            for sc in pow_scen:
                for mo in ss.MODELS:
                    cell(sc, mo, m)
    if "kill" in parts:
        for m in M_GRID:
            for mo in ss.MODELS:
                cell("beyond_kill", mo, m)
    C = ck["cells"]
    have = lambda sc, mo, m: f"{sc}|{mo}|{m}" in C  # noqa: E731
    cov = {s: {mo: min(C[f"{sc}|{mo}|{M_DEV}"]["coverage"][s] for sc in dev_scen if have(sc, mo, M_DEV))
               for mo in ss.MODELS} for s in ss.THR} if all(have(sc, mo, M_DEV) for sc in dev_scen for mo in ss.MODELS) else {}
    f3 = json.loads((HERE / "f3_simulation.json").read_text())
    out = {"task": "T0398", "objective": "O002", "experiment": "E007", "kind": "F3 follow-up simulation (not evidence)",
           "generated": time.strftime("%Y-%m-%dT%H:%M:%S"), "seed": SEED, "reps_per_cell": a.reps,
           "truth_reps": 4 * a.t_reps, "bound": V4, "variant": VAR,
           "mc_se_at_0.95": math.sqrt(0.95 * 0.05 / a.reps), "mc_se_at_0.5": math.sqrt(0.25 / a.reps),
           "f3_dev": {"m": M_DEV, "structure": "15 (family, dies) strata x 3 layouts, 2 switches x dies dies, 2 loads",
                      "scenarios": dev_scen, "coverage": cov,
                      "coverage_definition": "min over scenarios of the share of datasets whose V4 bound covers the true "
                                             "value (A1-A4 upper, K1-K3 lower), at the development rows' structure"},
           "power": {sc: {str(m): {mo: {"joint": C[f"{sc}|{mo}|{m}"]["power_joint"],
                                        "A4": C[f"{sc}|{mo}|{m}"]["power_each"]["A4"],
                                        "each": C[f"{sc}|{mo}|{m}"]["power_each"],
                                        "min_coverage": min(C[f"{sc}|{mo}|{m}"]["coverage"].values())}
                                   for mo in ss.MODELS if have(sc, mo, m)} for m in M_GRID} for sc in pow_scen},
           "power_joint_n5_alt": f3.get("power_by_m"),
           "kill_side": {"scenario": "beyond_kill", "factor": KILL_FACTOR, "targets": scen["beyond_kill"],
                         "by_m": {str(m): {mo: {"p_fire": C[f"beyond_kill|{mo}|{m}"]["p_fire"],
                                                "p_any_kill": C[f"beyond_kill|{mo}|{m}"]["p_any_kill"],
                                                "min_coverage": min(C[f"beyond_kill|{mo}|{m}"]["coverage"].values())}
                                           for mo in ss.MODELS if have("beyond_kill", mo, m)} for m in M_GRID}},
           "measured": meas, "cells": C,
           "consistency_max_rel_diff": ss.consistency_check(6)}
    OUT.write_text(json.dumps(out, indent=1, default=float))
    print(f"wrote {OUT}; f3_dev coverage {cov}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
