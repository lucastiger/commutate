"""Test T5 (L1 only): is the L1 ruggedness along die-row coordinates an artefact of L1's 4 mm trace mesh?

Repeats T3b's die-row scans (and the row_LS_u0 scan at W*) with ``physics.peec.loop_inductance`` at hmax = 4 mm (the
frozen L1, ``twin._l1``), 2 mm and 1 mm, at twin.L1_FREQ_HZ.  If the dents vanish under refinement, they are discretisation
noise of the screen, not physics.  Ratios are to W* at the same hmax.

Run: ``uv run python research/o008_e011_diag/t5_l1_mesh.py`` -> research/o008_e011_diag/t5_l1_mesh.json
"""
from __future__ import annotations

import time

import numpy as np

import common as C

STEP = 0.5
HMAX = (4e-3, 2e-3, 1e-3)
CASES = [(None, "row_LS_u0", 0, 12), (7, "row_LS_u0", -1, 13), (4, "row_LS_u0", -1, 14), (1, "row_HS_u0", -1, 8),
         (6, "row_LS_u0", -1, 5)]


def main() -> None:
    from moduleforge.generate.twin import L1_FREQ_HZ
    from moduleforge.physics.peec import loop_inductance

    lay = C.manifest()["layouts"][C.LAYOUT]
    l1 = C.L1()
    names = l1.names
    P = C.params_by_fp()
    w = np.asarray(lay["Wstar"]["params"], float)
    lw = l1.build(w)

    def L(lay_, h):
        return float(loop_inductance(lay_, [L1_FREQ_HZ], hmax=h).L_H[0])

    ref = {h: L(lw, h) for h in HMAX}
    assert abs(ref[4e-3] - l1(w)) < 1e-15 * ref[4e-3] + 1e-18, "hmax 4 mm must equal twin._l1"
    out = {"freq_hz": L1_FREQ_HZ, "hmax_m": HMAX, "cases": []}
    for draw, pname, k0, k1 in CASES:
        i = names.index(pname)
        start = w if draw is None else np.asarray(P[C.roles_of_draw(draw)["search"]], float)
        sgn = 1.0 if draw is None else np.sign(w[i] - start[i])
        rec = {"draw": draw, "param": pname, "start": float(start[i]), "Wstar": float(w[i]), "rows": []}
        for k in range(k0, k1 + 1):
            v = start.copy()
            v[i] = start[i] + sgn * k * STEP
            ok, why = l1.valid(v)
            if not ok:
                continue
            lay_ = l1.build(v)
            t = time.perf_counter()
            vals = {f"{h * 1e3:g}mm": L(lay_, h) / ref[h] for h in HMAX}
            rec["rows"].append({"k": k, "value": float(v[i]), **vals, "secs": time.perf_counter() - t})
        out["cases"].append(rec)
        print(f"draw {draw} {pname} start {start[i]:+.1f} W* {w[i]:+.1f}")
        for h in HMAX:
            key = f"{h * 1e3:g}mm"
            print(f"   {key:>4s}:", " ".join(f"{r[key]:.4f}" for r in rec["rows"]))
    C.dump(out, C.OUT / "t5_l1_mesh.json")


if __name__ == "__main__":
    main()
