"""Test T7 (L1 only): (a) roughness of L1 along the T5 scans at hmax 4 / 2 / 1 mm: RMS residual of a quadratic fit and the
number of sign changes of the first difference; (b) wall time per L1 evaluation at each hmax on 2R's W* (median of 5),
the cost input for a redesign that refines the screen.  2D_Case_4 timing is attempted and recorded as unavailable if its
development reference cannot be built on this machine.

Run: ``uv run python research/o008_e011_diag/t7_l1_cost_roughness.py`` -> research/o008_e011_diag/t7_l1_cost_roughness.json
"""
from __future__ import annotations

import json
import time

import numpy as np

import common as C


def main() -> None:
    from moduleforge.generate.twin import L1_FREQ_HZ
    from moduleforge.physics.peec import loop_inductance

    t5 = json.loads((C.OUT / "t5_l1_mesh.json").read_text())
    rough = []
    for c in t5["cases"]:
        k = np.array([r["k"] for r in c["rows"]], float)
        rec = {"draw": c["draw"], "param": c["param"]}
        for key in ("4mm", "2mm", "1mm"):
            y = np.array([r[key] for r in c["rows"]])
            fit = np.polyval(np.polyfit(k, y, 2), k)
            d1 = np.diff(y)
            rec[key] = {"rms_resid": float(np.sqrt(np.mean((y - fit) ** 2))),
                        "max_abs_resid": float(np.max(np.abs(y - fit))),
                        "sign_changes_d1": int(np.sum(np.diff(np.sign(d1)) != 0))}
        rough.append(rec)
        print(c["draw"], c["param"], {k2: (round(v["rms_resid"], 5), v["sign_changes_d1"])
                                      for k2, v in rec.items() if k2.endswith("mm")})
    timing = {}
    for name in ("2D_Case_2R", "2D_Case_4"):
        try:
            l1 = C.L1(name)
            lay = l1.lc.W
        except Exception as e:  # recorded, not raised: Case 4's development reference may need files not on this machine
            timing[name] = {"unavailable": f"{type(e).__name__}: {e}"[:200]}
            continue
        rec = {}
        for h in (4e-3, 2e-3, 1e-3):
            ts = []
            for _ in range(5):
                t = time.perf_counter()
                loop_inductance(lay, [L1_FREQ_HZ], hmax=h)
                ts.append(time.perf_counter() - t)
            rec[f"{h * 1e3:g}mm_s"] = float(np.median(ts))
        timing[name] = rec
        print(name, rec)
    C.dump({"roughness": rough, "timing_s_per_eval_on_W": timing}, C.OUT / "t7_l1_cost_roughness.json")


if __name__ == "__main__":
    main()
