"""Test T1 (committed data, no solve): per 2R draw, L1 and L2 (0.5 mm; 0.25 mm where solved) of W*, D_j, the search's
shortlist and best, compaction, widen, ablation (e) and the random screen's best, all as ratios to W*; the parameters that
differ between each end point and W*; and which of D_j's changes from W* each end point restored.  Also every 2R layout the
burst solved at 0.5 mm (L1 recomputed), for the L1-L2 fidelity test T2.

Run: ``uv run python research/o008_e011_diag/t1_assemble.py`` -> research/o008_e011_diag/t1_assembled.json
"""
from __future__ import annotations

import numpy as np

import common as C


def main() -> None:
    man = C.manifest()
    lay = man["layouts"][C.LAYOUT]
    l1 = C.L1()
    names = l1.names
    P = C.params_by_fp()
    ws_fp = lay["Wstar"]["fingerprint"]
    ws_vec = lay["Wstar"]["params"]
    l1_ws = l1(ws_vec, ws_fp)
    l2_ws = {lv: C.l2(ws_fp, lv) for lv in ("lat0.5", "lat0.25")}
    W_fp = C.dev_rows()["per_layout"][C.LAYOUT]["W_fingerprint"]

    def rec(fp: str) -> dict:
        v = P[fp]
        r = {"fingerprint": fp, "l1_ratio": l1(v, fp) / l1_ws}
        for lv in ("lat0.5", "lat0.25"):
            x = C.l2(fp, lv)
            r[f"l2_ratio_{lv}"] = None if x is None else x / l2_ws[lv]
        return r

    draws = []
    for j in range(C.N_DRAWS):
        roles = C.roles_of_draw(j)
        d_vec = P[roles["D"]]
        d_changed = {x["name"]: x["delta"] for x in C.diff_params(ws_vec, d_vec, names)}
        out = {"draw": j, "roles": {}}
        for role in ("D", "search", "compact", "widen", "proxy_alone", "random_screen"):
            fp = roles[role]
            r = rec(fp)
            dif = C.diff_params(ws_vec, P[fp], names)
            r["diff_from_Wstar"] = dif
            r["n_diff"] = len(dif)
            r["manhattan_mm"] = float(sum(abs(x["delta"]) for x in dif))
            # restoration of D_j's planted changes: a planted parameter is restored if it equals W*'s value again
            rest = [n for n in d_changed if abs(P[fp][names.index(n)] - ws_vec[names.index(n)]) < 1e-9]
            r["planted_restored"] = len(rest)
            r["planted_total"] = len(d_changed)
            r["new_changes"] = [x["name"] for x in dif if x["name"] not in d_changed]
            by_g: dict[str, float] = {}
            for x in dif:
                by_g[x["group"]] = by_g.get(x["group"], 0.0) + abs(x["delta"])
            r["manhattan_by_group_mm"] = by_g
            out["roles"][role] = r
        sl = []
        for rank, fp in C.shortlist("search_short", j):
            r = rec(fp)
            r["rank"] = rank
            sl.append(r)
        out["search_shortlist"] = sl
        a = np.array([x["l1_ratio"] for x in sl])
        b = np.array([x["l2_ratio_lat0.5"] for x in sl])
        out["shortlist_l1_range"] = [float(a.min()), float(a.max())]
        out["shortlist_l2_range"] = [float(b.min()), float(b.max())]
        # pairwise parameter spread inside the shortlist (mm, Manhattan over the movable set)
        V = np.array([P[x["fingerprint"]] for x in sl])[:, list(C.MOVABLE)]
        dm = np.abs(V[:, None, :] - V[None, :, :]).sum(-1)
        out["shortlist_max_pair_manhattan_mm"] = float(dm.max())
        draws.append(out)

    allrec = []
    for fp in P:
        if C.l2(fp, "lat0.5") is None:
            continue
        r = rec(fp)
        v = np.asarray(P[fp])
        r["manhattan_from_Wstar_mm"] = float(np.abs(v - np.asarray(ws_vec))[list(C.MOVABLE)].sum())
        r["purposes"] = sorted({p for p, lst in C.purposes().items() if any(f == fp for f, _ in lst)})
        allrec.append(r)
    C.dump({"layout": C.LAYOUT, "Wstar_fingerprint": ws_fp, "W_fingerprint": W_fp, "l1_Wstar_H": l1_ws,
            "l2_Wstar_H": l2_ws, "draws": draws, "all_lat05": allrec,
            "W": rec(W_fp) | {"manhattan_from_Wstar_mm": float(np.abs(np.asarray(P[W_fp]) - np.asarray(ws_vec))
                                                                [list(C.MOVABLE)].sum())}},
           C.OUT / "t1_assembled.json")
    for d in draws:
        s = d["roles"]
        print(d["draw"], " ".join(f"{k}:L1 {s[k]['l1_ratio']:.4f} L2 {s[k]['l2_ratio_lat0.5']:.4f}"
                                   for k in ("D", "search", "compact", "proxy_alone")),
              "SL L1", [round(x, 4) for x in d["shortlist_l1_range"]], "SL L2",
              [round(x, 4) for x in d["shortlist_l2_range"]])


if __name__ == "__main__":
    main()
