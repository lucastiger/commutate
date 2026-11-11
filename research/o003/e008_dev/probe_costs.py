"""T0262 cost probe (research, not evidence): DOF counts of the frozen scikit-fem rule on 2D_Case_4 at levels 0-2, one
level-0 and one level-1 solve (wall, RSS), and the L1 screen rate (generate + L1) on the Case 4 spec. Single process."""
import json

import numpy as np
import resource
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tools" / "mfos"), str(ROOT / "experiments" / "runners")]
import e008_run as R  # noqa: E402

out = {}
cfg = R.load_spec()["config"]
rc = R.dev_reference("case4", cfg)
FEM = R.FEM()
rule = R.rule_from(cfg["fem_rule"])
for lv in (0, 1, 2):
    out[f"dofs_L{lv}"] = FEM.estimate_dofs(rc.reference, rule, lv)
from moduleforge.solvers import thermal_layout as TL  # noqa: E402
for lv in (1, 2, 3):
    out[f"fv_cells_L{lv}"] = int(np.prod(TL.build_layout_grid(rc.reference, lv).shape))
print(out, flush=True)
for lv in (0, 1):
    t = time.perf_counter()
    r = FEM.solve_layout(rc.reference, 30.0, 5000.0, 338.15, rule=rule, level=lv)
    out[f"wall_L{lv}"] = time.perf_counter() - t
    out[f"rss_GB_after_L{lv}"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e9
    out[f"tj_L{lv}"] = [float(x) for x in r.tj_max]
    print(out, flush=True)
t = time.perf_counter()
from moduleforge.generate import derivative as D  # noqa: E402
lays = D.generate(rc.spec, 20, 99)
tg = time.perf_counter() - t
t = time.perf_counter()
for lay in lays:
    R.l1_of(lay)
out["gen_s_per_cand"] = tg / 20
out["l1_s_per_cand"] = (time.perf_counter() - t) / 20
print(json.dumps(out), flush=True)
(Path(__file__).parent / "probe_costs.json").write_text(json.dumps(out, indent=1))
