"""T0456 step 1: per-switch-row anatomy of the per-stratum A4 on E007 development rows (no solves).

Reads a rows file written by e007_run.py (--dev or this task's a4_strata_run.py) and prints, per (layout, load, switch):
reference / L1 / stratum-mean-null spreads, both errors, which dies set each spread (argmax, argmin die_index), and the
per-die L1 - reference bias. Also the per-stratum A4 (P_ref) with numerator and denominator, the isolated-die null's A4,
and two counterfactuals: (i) L1 rises rescaled by the stratum's implied calibration factor, (ii) L1 die biases with the
(layout, switch) mean removed. Statistic = mfos.metrics.quantile_abs_err_ratio (np.quantile, linear), as the runner."""
from __future__ import annotations

import json
import sys
from collections import defaultdict

import numpy as np
from mfos import metrics as M


def p95(x):
    return float(np.quantile(np.abs(np.asarray(x, float)), 0.95))


def main(path, strata, out=None):
    d = json.load(open(path))
    rows = d["rows"]
    meta = d.get("meta", {})
    dies = defaultdict(list)
    for r in rows:
        if r["kind"] == "die":
            dies[(r["layout"], r["load"], r["switch"])].append(r)
    res = {}
    for sn in strata:
        sw = [r for r in rows if r["kind"] == "switch" and r["stratum"] == sn]
        res[sn] = {}
        for load in ("P_ref", "half_P_ref"):
            S = [r for r in sw if r["load"] == load]
            if not S:
                continue
            lines = []
            for r in sorted(S, key=lambda r: (r["layout"], r["switch"])):
                ds = sorted(dies[(r["layout"], load, r["switch"])], key=lambda x: x["die_index"])
                tr = np.array([x["tj_ref_K"] for x in ds])
                tl = np.array([x["tj_l1_K"] for x in ds])
                b = tl - tr
                lines.append({"layout": r["layout"], "switch": r["switch"], "spread_ref": r["spread_ref_K"],
                              "spread_l1": r["spread_l1_K"], "spread_null": r["spread_null_K"],
                              "err_l1": r["spread_l1_K"] - r["spread_ref_K"],
                              "err_null": r["spread_null_K"] - r["spread_ref_K"],
                              "err_iso": r["null_iso"] - r["spread_ref_K"],
                              "ref_hot_cold": [int(np.argmax(tr)), int(np.argmin(tr))],
                              "l1_hot_cold": [int(np.argmax(tl)), int(np.argmin(tl))],
                              "bias_K": b.round(4).tolist(), "bias_mean": float(b.mean()),
                              "bias_dev_range": float(np.ptp(b - b.mean())),
                              "tj_ref_rel": (tr - tr.max()).round(4).tolist()})
            num = p95([x["err_l1"] for x in lines])
            den = p95([x["err_null"] for x in lines])
            iso = p95([x["err_iso"] for x in lines])
            a4 = M.quantile_abs_err_ratio([r["spread_l1_K"] for r in S], [r["spread_null_K"] for r in S],
                                          [r["spread_ref_K"] for r in S])
            chk = meta["l1_dev_check_D0025"].get(sn, {}) if "l1_dev_check_D0025" in meta else {}
            # counterfactual (i): L1 rises scaled by implied_c / c_table (spread scales by the same factor)
            ratio = chk.get("implied_c_P_ref", 1.0) / chk.get("c_table", 1.0) if chk else 1.0
            num_c = p95([x["spread_l1"] * ratio - x["spread_ref"] for x in lines])
            res[sn][load] = {"rows": lines, "A4": a4, "num_p95_K": num, "den_p95_K": den, "iso_A4": iso / den if den else None,
                             "max_err_l1": max(abs(x["err_l1"]) for x in lines),
                             "A4_with_implied_c": num_c / den if den else None, "c_ratio": ratio,
                             "sd_spread_ref": float(np.std([x["spread_ref"] for x in lines], ddof=1)),
                             "mean_spread_ref": float(np.mean([x["spread_ref"] for x in lines]))}
            print(f"\n== {sn} {load}: A4 {a4:.3f} = {num:.4f} / {den:.4f} K; isolated_die A4 {iso / den:.2f}; "
                  f"A4 with implied c {num_c / den:.3f} (ratio {ratio:.5f}); ref spread mean {res[sn][load]['mean_spread_ref']:.3f}"
                  f" sd {res[sn][load]['sd_spread_ref']:.3f} K")
            for x in lines:
                print(f"  {x['layout']:22s} {x['switch']} ref {x['spread_ref']:.4f} l1 {x['spread_l1']:.4f} null "
                      f"{x['spread_null']:.4f} | e_l1 {x['err_l1']:+.4f} e_null {x['err_null']:+.4f} | ref hot/cold "
                      f"{x['ref_hot_cold']} l1 {x['l1_hot_cold']} | bias mean {x['bias_mean']:+.3f} dev-range "
                      f"{x['bias_dev_range']:.3f} {x['bias_K']}")
    if out:
        json.dump(res, open(out, "w"), indent=1)


if __name__ == "__main__":
    p = sys.argv[1]
    o = sys.argv[2] if len(sys.argv) > 2 and sys.argv[2].endswith(".json") else None
    st = [s for s in sys.argv[2:] if not s.endswith(".json")] or ["u_shaped/6", "u_shaped/2", "interleaved/2", "side_by_side/2"]
    main(p, st, o)
