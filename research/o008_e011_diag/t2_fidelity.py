"""Test T2 (committed data, L1 recomputed, no solve): how well does L1 predict L2 at 0.5 mm over every 2R layout the burst
solved, and what explains the residual?

y = log(L2_0.5 / L2_0.5(W*)), x = log(L1 / L1(W*)) over the 168 2R layouts solved at lat0.5 (t1_assembled.json).
  * the fit y = a x + c, its residual sd and W*'s own residual (-c);
  * correlation of the residual with each movable parameter's offset from W*;
  * the residual on row_LS_u0's offset alone and with slot1_u0, by least squares on all points and on one point per
    scored group (the lowest-L1 member of each search shortlist plus every single end point), and leave-one-draw-out
    slopes, because shortlist members are near-duplicates and are not independent.

Run: ``uv run python research/o008_e011_diag/t2_fidelity.py`` -> research/o008_e011_diag/t2_fidelity.json
"""
from __future__ import annotations

import json

import numpy as np

import common as C


def ols(X: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    A = np.c_[np.ones(len(y)), X]
    coef, *_ = np.linalg.lstsq(A, y, rcond=None)
    return coef, y - A @ coef


def main() -> None:
    d = json.loads((C.OUT / "t1_assembled.json").read_text())
    P = C.params_by_fp()
    from moduleforge.generate.derivative import Params

    names = list(Params.NAMES)
    w = np.asarray(C.manifest()["layouts"][C.LAYOUT]["Wstar"]["params"], float)
    recs = d["all_lat05"]
    x = np.log([r["l1_ratio"] for r in recs])
    y = np.log([r["l2_ratio_lat0.5"] for r in recs])
    V = np.array([P[r["fingerprint"]] for r in recs]) - w
    (c0, a), res = ols(x[:, None], y)
    out = {"n": len(recs), "fit": {"a": float(a), "c": float(c0), "residual_sd": float(res.std(ddof=2)),
                                   "Wstar_residual": float(-c0)}}
    cors = {names[i]: float(np.corrcoef(V[:, i], res)[0, 1]) for i in C.MOVABLE if V[:, i].std() > 1e-9}
    out["residual_correlation"] = dict(sorted(cors.items(), key=lambda kv: -abs(kv[1])))
    iL, iS = names.index("row_LS_u0"), names.index("slot1_u0")
    fits = {}
    for tag, cols in (("rowLS", [iL]), ("rowLS+slot1", [iL, iS])):
        X = np.c_[x, V[:, cols]]
        coef, r2 = ols(X, y)
        fits[tag] = {"intercept": float(coef[0]), "a_l1": float(coef[1]),
                     "per_mm": {names[c]: float(k) for c, k in zip(cols, coef[2:], strict=True)},
                     "residual_sd": float(r2.std(ddof=len(coef))), "R2": float(1 - r2.var() / y.var())}
    out["fits_all_points"] = fits
    # one point per scored group: lowest-L1 member of each search / random-screen shortlist, plus every single end point
    groups: dict[str, int] = {}
    for k, r in enumerate(recs):
        ps = r["purposes"]
        key = next((p for p in ps if "_short_" in p), None) or f"single:{r['fingerprint']}"
        if key not in groups or recs[groups[key]]["l1_ratio"] > r["l1_ratio"]:
            groups[key] = k
    g = sorted(groups.values())
    Xg = np.c_[x[g], V[g][:, [iL, iS]]]
    coef, r2 = ols(Xg, y[g])
    out["fit_one_per_group"] = {"n": len(g), "intercept": float(coef[0]), "a_l1": float(coef[1]),
                                "per_mm": {"row_LS_u0": float(coef[2]), "slot1_u0": float(coef[3])},
                                "residual_sd": float(r2.std(ddof=4))}
    # leave one draw out: drop every layout whose purposes name draw j
    lodo = {}
    for j in range(C.N_DRAWS):
        keep = [k for k, r in enumerate(recs) if not any(p.endswith(f"_d{j}") or f"_d{j}_" in p
                                                         for p in r["purposes"])]
        coef, _ = ols(np.c_[x[keep], V[keep][:, [iL, iS]]], y[keep])
        lodo[str(j)] = {"n": len(keep), "row_LS_u0_per_mm": float(coef[2]), "slot1_u0_per_mm": float(coef[3])}
    out["leave_one_draw_out"] = lodo
    out["row_LS_u0_offsets_of_search_best"] = {
        str(dr["draw"]): next((p["delta"] for p in dr["roles"]["search"]["diff_from_Wstar"] if p["name"] == "row_LS_u0"),
                              0.0) for dr in d["draws"]}
    C.dump(out, C.OUT / "t2_fidelity.json")
    print(json.dumps({k: out[k] for k in ("n", "fit", "fits_all_points", "fit_one_per_group")}, indent=1))
    print("top residual correlations:", list(out["residual_correlation"].items())[:6])
    print("LODO row_LS_u0 %/mm:", [round(100 * v["row_LS_u0_per_mm"], 3) for v in lodo.values()])
    print("LODO slot1_u0 %/mm:", [round(100 * v["slot1_u0_per_mm"], 3) for v in lodo.values()])


if __name__ == "__main__":
    main()
