"""T0456 step 1, discriminating tests on T0398's development layouts (seed 20261398, 3 per stratum), P_ref only.

(a) L1 grid rule: the frozen L1 (moduleforge.thermal.evaluate) against moduleforge.thermal.raw_fv on finer lateral/vertical
    grids (raw, c = 1, and with c(s)); the switch spread of each against the level-1 reference spread from T0398's rows.
    If the spread error shrinks toward 0 under refinement, L1's grid rule explains it; if it stays, it does not.
(b) Reference discretization: level-0 reference solves (e007_run Jobs, same GridRule) beside T0398's level-1 solves; the
    change of each switch spread from level 0 to level 1 bounds how much of the L1-minus-reference spread error could be
    reference error (Richardson: level-1 error ~ (S1 - S0) / (r^p - 1), r = 2, p = 2 for the Q2 element if asymptotic).
Writes research/o002_e007/a4_strata/diag_solves.json. usage: diag_solves.py [l1|ref|both]"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "experiments" / "runners"))
import e007_run as E  # noqa: E402

OUTP = ROOT / "research" / "o002_e007" / "a4_strata" / "diag_solves.json"
STRATA = ["u_shaped/6", "u_shaped/2", "interleaved/2", "side_by_side/2"]
GRIDS = {"frozen": None,
         "h0_0.75mm": {"h0_max": 0.75e-3, "lat_frac": 16.0, "edge_frac": 2.0, "z_cells": 2},
         "h0_0.75mm_lat32_z4": {"h0_max": 0.75e-3, "lat_frac": 32.0, "edge_frac": 1.0, "z_cells": 4},
         "h0_0.5mm_lat32_z4": {"h0_max": 0.5e-3, "lat_frac": 32.0, "edge_frac": 1.0, "z_cells": 4}}


def spreads(lay, tj):
    out = {}
    for sw in ("HS", "LS"):
        v = [t for t, d in zip(tj, lay.dies, strict=True) if d.switch == sw]
        out[sw] = float(max(v) - min(v))
    return out


def main(which: str) -> int:
    from moduleforge import thermal as L1
    spec = E.load_spec()
    cfg = spec["config"]
    rows = json.load(open(ROOT / "experiments" / "drafts" / "E007.dev_rows.json"))
    pref = rows["meta"]["pref_W_per_die"]
    sw_ref = {(r["layout"], r["switch"]): r["spread_ref_K"] for r in rows["rows"] if r["kind"] == "switch"
              and r["load"] == "P_ref"}
    sample = E.build_sample(cfg, cfg["dev"]["dev_seed"], "dev", cfg["dev"]["layouts_per_stratum"])
    out = json.load(open(OUTP)) if OUTP.exists() else {}
    if which in ("l1", "both"):
        res = {}
        for sn in STRATA:
            for d in sample["strata"][sn]["judged"]:
                lay = E.get_layout(d)
                P = pref[sn]
                tbp = cfg["coolant_K"] + P * len(lay.dies) / (cfg["h_W_m2K"] * float(lay.baseplate_outline.area))
                c = L1.calibration_factor(d["die_size_mm"])
                rec = {}
                for g, rule in GRIDS.items():
                    fv = L1.raw_fv(lay, P, h=cfg["h_W_m2K"], T_c=cfg["coolant_K"], grid_rule=rule)
                    raw = np.asarray(fv["tj_mean"])
                    s_raw, s_cal = spreads(lay, raw), spreads(lay, tbp + c * (raw - tbp))
                    rec[g] = {"n_cells": int(fv["result"].meta["n_cells"]),
                              "mean_rise_raw_K": float(np.mean(raw - tbp)),
                              **{f"err_raw_{sw}": s_raw[sw] - sw_ref[(d["name"], sw)] for sw in ("HS", "LS")},
                              **{f"err_cal_{sw}": s_cal[sw] - sw_ref[(d["name"], sw)] for sw in ("HS", "LS")}}
                    E.log(f"{d['name']} {g}: cells {rec[g]['n_cells']} err raw HS {rec[g]['err_raw_HS']:+.4f} LS "
                          f"{rec[g]['err_raw_LS']:+.4f} cal HS {rec[g]['err_cal_HS']:+.4f} LS {rec[g]['err_cal_LS']:+.4f}")
                res[d["name"]] = {"stratum": sn, "spread_ref_L1": {sw: sw_ref[(d["name"], sw)] for sw in ("HS", "LS")},
                                  "grids": rec}
        out["l1_grid"] = {"grids": GRIDS, "layouts": res}
        E.write_json(OUTP, out)
    if which in ("ref", "both"):
        c2 = copy.deepcopy(cfg)
        jobs = E.Jobs(c2, ROOT / "research" / "o002_e007" / "a4_strata" / "work_l0", max_procs=1, cap_gb=4.0)
        js = [E.solve_job(d, "P_ref", 0, pref, c2) for sn in STRATA for d in sample["strata"][sn]["judged"]]
        recs = jobs.run(js)
        res = {}
        for sn in STRATA:
            for d in sample["strata"][sn]["judged"]:
                lay = E.get_layout(d)
                r0 = recs[f"{d['name']}__P_ref__L0"]
                s0 = spreads(lay, r0["tj_mean"])
                res[d["name"]] = {"stratum": sn, "dofs_L0": r0["dofs"], "energy_balance": r0["energy_balance"],
                                  "picard_residual_K": r0["picard_residual_K"], "cg_hit_maxiter": r0["cg_hit_maxiter"],
                                  "peak_rss_GB": r0["peak_rss_GB"],
                                  **{f"spread_L0_{sw}": s0[sw] for sw in ("HS", "LS")},
                                  **{f"spread_L1_{sw}": sw_ref[(d["name"], sw)] for sw in ("HS", "LS")},
                                  **{f"dS_L0_to_L1_{sw}": sw_ref[(d["name"], sw)] - s0[sw] for sw in ("HS", "LS")}}
                E.log(f"{d['name']}: L0->L1 spread change HS {res[d['name']]['dS_L0_to_L1_HS']:+.4f} LS "
                      f"{res[d['name']]['dS_L0_to_L1_LS']:+.4f} K")
        out["ref_levels"] = res
        E.write_json(OUTP, out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "both"))
