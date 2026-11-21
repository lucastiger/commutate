"""Test T3b (L1 only): from each 2R search end point b, scan every die-row parameter that differs from W* in 0.5 mm steps
toward (and 2 mm past) W*'s value, the others held at b.  Shows whether L1 along the die-row coordinates is monotone or
rugged at the search's step size.  Also the L1 roughness of every movable parameter at W*: the second difference of L1
over three 0.5 mm steps, as a fraction of L1(W*).

Run: ``uv run python research/o008_e011_diag/t3b_dierow_scans.py`` -> research/o008_e011_diag/t3b_dierow_scans.json
"""
from __future__ import annotations

import numpy as np

import common as C

STEP = 0.5


def main() -> None:
    lay = C.manifest()["layouts"][C.LAYOUT]
    l1 = C.L1()
    names = l1.names
    P = C.params_by_fp()
    w = np.asarray(lay["Wstar"]["params"], float)
    Lw = l1(w, lay["Wstar"]["fingerprint"])
    out = {"scans": [], "roughness_at_Wstar": {}}
    for j in range(C.N_DRAWS):
        fp = C.roles_of_draw(j)["search"]
        b = np.asarray(P[fp], float)
        for i in C.MOVABLE:
            if not names[i].startswith("row_") or abs(b[i] - w[i]) < 1e-9:
                continue
            sgn = np.sign(w[i] - b[i])
            n = int(round(abs(w[i] - b[i]) / STEP)) + 4
            prof = []
            for k in range(-2, n + 1):
                v = b.copy()
                v[i] = b[i] + sgn * k * STEP
                ok, why = l1.valid(v)
                prof.append({"k": k, "value": float(v[i]), "valid": ok, "why": why,
                             "l1_ratio": l1(v) / Lw if ok else None})
            vals = [p["l1_ratio"] for p in prof if p["valid"]]
            rec = {"draw": j, "param": names[i], "b": float(b[i]), "Wstar": float(w[i]), "profile": prof}
            out["scans"].append(rec)
            print(j, names[i], f"b {b[i]:+.2f} -> W* {w[i]:+.2f}:",
                  " ".join(f"{p['l1_ratio']:.4f}" if p["valid"] else "x" for p in prof),
                  f"| min {min(vals):.4f}")
    # roughness: second differences along each movable parameter at W*
    for i in C.MOVABLE:
        ls = []
        for k in (-1, 0, 1):
            v = w.copy()
            v[i] += k * STEP
            ls.append(l1(v) / Lw if l1.valid(v)[0] else None)
        if None not in ls:
            out["roughness_at_Wstar"][names[i]] = {"l1": ls, "d2": ls[0] - 2 * ls[1] + ls[2],
                                                   "d1": (ls[2] - ls[0]) / 2}
    C.dump(out, C.OUT / "t3b_dierow_scans.json")
    r = out["roughness_at_Wstar"]
    print("params with a 3-point L1 stencil at W*:", len(r))
    for k, v in sorted(r.items(), key=lambda kv: -abs(kv[1]["d2"]))[:10]:
        print(f"  {k:14s} d1 {v['d1']:+.5f} d2 {v['d2']:+.5f}")


if __name__ == "__main__":
    main()
