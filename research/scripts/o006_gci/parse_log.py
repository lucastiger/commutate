"""Rebuild the level 0..6 k(T) strip2d record from research/o006_gci/run.log (values printed to 1e-5 K).

The first strip2d run asked for level 8; level 7 (21 M cells) exceeded the 16 GB host and could not be stopped from the
sandbox, so its JSON was never written.  Levels 0..6 completed and were logged; this re-derives every estimator from them.
Run: ``uv run python research/scripts/o006_gci/parse_log.py``.
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import gci_study as g  # noqa: E402

rows = {}
for ln in (g.OUT / "run.log").read_text().splitlines():
    parts = ln.split(" ", 6)
    if len(parts) == 7 and parts[0] == "strip2d" and parts[1] == "kT":
        rows[int(parts[2])] = {"n_cells": int(parts[3]), "wall_s": float(parts[4]), "peak_rss_gb_so_far": float(parts[5]),
                               "values": ast.literal_eval(parts[6])}
levels = [rows[i] for i in sorted(rows)]
assert [*sorted(rows)] == list(range(len(levels))) and len(levels) >= 4
seq = {}
for n in levels[0]["values"]:
    f = [lv["values"][n] for lv in levels]
    tr = [{"levels": [i, i + 1, i + 2], **g.estimators(*f[i:i + 3])} for i in range(len(f) - 2)]
    fin = tr[-1]
    ref = fin["richardson_value"] if fin["richardson_value"] == fin["richardson_value"] else f[-1]
    ref_unc = max(fin["gci_candidate"], abs(ref - f[-1]), 1e-5)  # 1e-5 K print resolution
    e2 = abs(f[2] - ref)
    rec = {"values_K": f, "triples": tr, "reference": {"value_K": ref, "uncertainty_K": ref_unc, "from_levels": fin["levels"]},
           "true_err_level2_K": e2}
    for est in ("gci_frozen", "gci_candidate", "richardson_err"):
        v = tr[0][est]
        ok = v == v
        rec[f"{est}_L012_vs_true"] = {"estimate_K": v, "ratio_est_over_true": v / e2 if ok and e2 > 0 else None,
                                      "verdict": ("conservative" if v >= e2 + ref_unc else "non-conservative"
                                                  if v < e2 - ref_unc else "undetermined") if ok else "undefined"}
    seq[n] = rec
doc = {"kind": "strip2d", "q_flux_W_m2": 1.03e6, "constant_k": False, "source": "run.log (levels 0..6, 1e-5 K resolution)",
       "levels": [{k: v for k, v in lv.items() if k != "values"} | {"level": i} for i, lv in enumerate(levels)],
       "values": seq, "corner_exponent_lambda": g.corner_exponent(58.0, 385.0), "corner_exponent_homogeneous_check":
       g.corner_exponent(1.0, 1.0)}
(g.OUT / "part_strip2d_kT_L6.json").write_text(json.dumps(g._clean(doc), indent=1) + "\n")
print("wrote part_strip2d_kT_L6.json")
