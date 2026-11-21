"""Test T3 (L1 only, local, seconds): the L1 landscape between each 2R search end point and W*.

Per draw j, with b = the search's returned layout (best_j) and w = W*:
  (a) local optimality of b: improving valid single 0.5 mm steps over the 36 movable parameters (the search's
      neighbourhood without the reach jumps and joint moves);
  (b) greedy path b -> w: each step takes, among the valid unit (0.5 mm) steps that move one differing parameter toward w
      and the valid "set one parameter to w's value" jumps, the one with the lowest L1; if none is valid, valid two-parameter
      unit steps toward w are tried; the path stops at w or at a wall.  Reported: the L1 profile (ratio to L1(w)), the barrier
      max(path) - L1(b) and whether w was reached;
  (c) one-at-a-time attribution: w with one parameter set to b's value, and b with one parameter set back to w's value,
      validity and L1 change, per differing parameter;
  (d) L1 scans at w along row_LS_u0 and slot1_u0 (the two parameters that correlate with the L2/L1 residual in T2).
Validity = builds, DRC-clean under the reference's measured rules, inside in_domain(reach=True): the search's constraint.

Run: ``uv run python research/o008_e011_diag/t3_l1_paths.py`` -> research/o008_e011_diag/t3_l1_paths.json
"""
from __future__ import annotations

import itertools

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

    def r1(v) -> float:
        return l1(v) / Lw

    out = {"draws": [], "scans": {}}
    for j in range(C.N_DRAWS):
        fp = C.roles_of_draw(j)["search"]
        b = np.asarray(P[fp], float)
        rb = l1(b, fp) / Lw
        # (a) single-step neighbourhood of b
        imp, nval = [], 0
        for i in C.MOVABLE:
            for d in (-STEP, STEP):
                v = b.copy()
                v[i] += d
                ok, _ = l1.valid(v)
                if ok:
                    nval += 1
                    x = r1(v)
                    if x < rb - 1e-12:
                        imp.append({"name": names[i], "d": d, "l1_ratio": x})
        # (b) greedy path b -> w
        cur, prof, moves, wall = b.copy(), [rb], [], None
        for _ in range(400):
            diff = [i for i in C.MOVABLE if abs(cur[i] - w[i]) > 1e-9]
            if not diff:
                break
            cands = []
            for i in diff:
                v = cur.copy()
                v[i] += STEP * np.sign(w[i] - cur[i])
                cands.append((f"{names[i]}{STEP * np.sign(w[i] - cur[i]):+g}", v))
                if abs(w[i] - cur[i]) > STEP + 1e-9:
                    v2 = cur.copy()
                    v2[i] = w[i]
                    cands.append((f"{names[i]}=W*", v2))
            val = [(r1(v), t, v) for t, v in cands if l1.valid(v)[0]]
            if not val:
                for i, k in itertools.combinations(diff, 2):
                    v = cur.copy()
                    v[i] += STEP * np.sign(w[i] - cur[i])
                    v[k] += STEP * np.sign(w[k] - cur[k])
                    if l1.valid(v)[0]:
                        val.append((r1(v), f"{names[i]}&{names[k]}", v))
            if not val:
                wall = {"remaining": [{"name": names[i], "cur": float(cur[i]), "Wstar": float(w[i])} for i in diff],
                        "reasons": {names[i]: l1.valid(np.where(np.arange(len(cur)) == i,
                                                                cur + STEP * np.sign(w - cur), cur))[1]
                                    for i in diff}}
                break
            x, t, cur = min(val, key=lambda z: z[0])
            prof.append(x)
            moves.append(t)
        reached = bool(np.all(np.abs(cur[list(C.MOVABLE)] - w[list(C.MOVABLE)]) < 1e-9))
        # (c) one-at-a-time attribution
        att = []
        for x in C.diff_params(w, b, names):
            i = names.index(x["name"])
            v1 = w.copy()
            v1[i] = b[i]
            v2 = b.copy()
            v2[i] = w[i]
            ok1, why1 = l1.valid(v1)
            ok2, why2 = l1.valid(v2)
            att.append({**x, "Wstar_plus_valid": ok1, "Wstar_plus_why": why1,
                        "Wstar_plus_dl1": (r1(v1) - 1.0) if ok1 else None,
                        "best_minus_valid": ok2, "best_minus_why": why2,
                        "best_minus_dl1": (r1(v2) - rb) if ok2 else None})
        out["draws"].append({
            "draw": j, "fingerprint": fp, "l1_ratio_best": rb, "n_valid_single_neighbours": nval,
            "improving_single_neighbours": imp, "path_profile": prof, "path_moves": moves, "path_reached_Wstar": reached,
            "path_barrier": float(max(prof) - rb), "path_max": float(max(prof)), "path_wall": wall,
            "attribution": att})
        print(f"draw {j}: L1(b)/L1(w) {rb:.4f}; improving single steps {len(imp)} of {nval} valid; "
              f"path {len(moves)} steps, reached {reached}, barrier {max(prof) - rb:+.4f}, wall {wall is not None}")
    for name in ("row_LS_u0", "slot1_u0", "row_HS_u0"):
        i = names.index(name)
        sc = []
        for k in range(-16, 17):
            v = w.copy()
            v[i] += k * STEP
            ok, why = l1.valid(v)
            sc.append({"delta_mm": k * STEP, "valid": ok, "why": why, "l1_ratio": r1(v) if ok else None})
        out["scans"][name] = sc
        print(name, [(s["delta_mm"], round(s["l1_ratio"], 4)) for s in sc if s["valid"]])
    C.dump(out, C.OUT / "t3_l1_paths.json")


if __name__ == "__main__":
    main()
