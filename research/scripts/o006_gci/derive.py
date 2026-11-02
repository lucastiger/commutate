"""Derived difference estimators (T0181; research, not evidence) -> research/o006_gci/part_derived.json.

For a difference D = fA - fB of two monotone level-0/1/2 sequences:
* raw-sequence estimators: frozen / candidate GCI applied to the D sequence itself (as in part_pairs.json);
* component Richardson: |cA - cB| with c = d21 / (2^p_obs - 1) the signed Richardson correction of each component;
* component GCI sum: GCI_A + GCI_B (frozen, candidate), a bound that ignores error correlation.
Checked against the true level-2 error in the strip2d case (reference: Richardson from levels 5-6-7).
"""
from __future__ import annotations

import json
import math

import gci_study as gs

OUT = gs.OUT


def corr(f: list[float]) -> float:
    e = gs.estimators(*f[:3])
    return (f[2] - f[1]) / (2.0 ** e["p_obs"] - 1.0) if e["monotone"] and e["p_obs"] > 0 else float("nan")


def comp(fa: list[float], fb: list[float]) -> dict:
    ea, eb = gs.estimators(*fa[:3]), gs.estimators(*fb[:3])
    d = [a - b for a, b in zip(fa[:3], fb[:3], strict=True)]
    ed = gs.estimators(*d)
    return {"diff_values_K": d, "raw_p_obs": ed["p_obs"], "raw_gci_frozen": ed["gci_frozen"],
            "raw_gci_candidate": ed["gci_candidate"], "component_richardson": abs(corr(fa) - corr(fb)),
            "component_gci_sum_frozen": ea["gci_frozen"] + eb["gci_frozen"],
            "component_gci_sum_candidate": ea["gci_candidate"] + eb["gci_candidate"]}


def main() -> None:
    out = {"strip2d_check": {}, "pairs": []}
    s = json.loads((OUT / "part_strip2d_kT_L6.json").read_text())["values"]
    for name, a, b in (("diff_tj_max", "die0.tj_max", "die1.tj_max"), ("diff_tj_mean", "die0.tj_mean", "die1.tj_mean")):
        r = comp(s[a]["values_K"], s[b]["values_K"])
        ref_d = s[name]["reference"]
        r["true_err_level2_K"] = abs(r["diff_values_K"][2] - ref_d["value_K"])
        r["reference_uncertainty_K"] = ref_d["uncertainty_K"]
        for k in ("raw_gci_frozen", "raw_gci_candidate", "component_richardson", "component_gci_sum_frozen",
                  "component_gci_sum_candidate"):
            g, e, u = r[k], r["true_err_level2_K"], ref_d["uncertainty_K"]
            r[k + "_verdict"] = ("conservative" if g >= e + u else "non-conservative" if g < e - u else "undetermined")
        out["strip2d_check"][name] = r
    pp = json.loads((OUT / "part_pairs.json").read_text())
    for pr in pp["pairs"]:
        if not pr["complete_levels_0_2"]:
            continue
        la, lb = pr["layouts"]
        rec = {"family": pr["family"], "selection": pr["selection"], "gen": pr["pair_gen_indices"],
               "layout_tj_max": comp(la["tj_max"]["tj_max_K"], lb["tj_max"]["tj_max_K"])}
        for da, db in zip(la["per_die"], lb["per_die"], strict=False):
            rec[f"die{da['die']}_tj_max"] = comp(da["tj_max_K"], db["tj_max_K"])
        out["pairs"].append(rec)
    (OUT / "part_derived.json").write_text(json.dumps(gs._clean(out), indent=1) + "\n")
    f = lambda v: "osc" if v is None or (isinstance(v, float) and math.isnan(v)) else f"{v:.3f}"  # noqa: E731
    for k, r in out["strip2d_check"].items():
        print("strip2d", k, "true", f(r["true_err_level2_K"]), "+-", f(r["reference_uncertainty_K"]),
              {kk: (f(r[kk]), r[kk + "_verdict"]) for kk in ("raw_gci_frozen", "raw_gci_candidate", "component_richardson",
                                                            "component_gci_sum_frozen", "component_gci_sum_candidate")})
    print("| pair | value | D levels 0/1/2 (K) | raw p_obs | raw GCI frozen | raw GCI cand. | comp. Richardson | "
          "GCI_A+GCI_B frozen | GCI_A+GCI_B cand. |")
    print("|---|---|---|---|---|---|---|---|---|")
    for rec in out["pairs"]:
        for k, r in rec.items():
            if isinstance(r, dict):
                print(f"| {rec['family']} {rec['selection']} #{rec['gen']} | {k} | "
                      f"{' / '.join(f'{x:.3f}' for x in r['diff_values_K'])} | {f(r['raw_p_obs'])} | "
                      f"{f(r['raw_gci_frozen'])} | {f(r['raw_gci_candidate'])} | {f(r['component_richardson'])} | "
                      f"{f(r['component_gci_sum_frozen'])} | {f(r['component_gci_sum_candidate'])} |")


if __name__ == "__main__":
    main()
