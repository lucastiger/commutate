"""T0464, review T0463 (5): a second level-2 job for the founder's burst, interleaved_2_j01 (T0398 development layout,
dev seed 20261398, 4.5 mm) at P_ref, the interleaved/2 layout whose reference spread moved most from level 0 to level 1
(-0.078 K HS / -0.084 K LS; research/o002_e007/a4_strata/diag_solves.json ref_levels). Chosen by that fixed rule before
any level-2 result exists. Power = the stratum's P_ref per die used by T0456's level-0 solve of the same layout."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "experiments" / "runners"))
import e007_run as R  # noqa: E402

src = json.loads((ROOT / "research/o002_e007/a4_strata/work_l0/solves/interleaved_2_j01__P_ref__L0.job.json").read_text())
cfg = R.load_spec()["config"]
from moduleforge.solvers import thermal_fem as FEM  # noqa: E402
lay = R.get_layout(src["layout"])
assert lay is not None
dofs = int(FEM.estimate_dofs(lay, R.fem_rule(cfg["fem_rule"]), 2))
cm = cfg["compute"]
gb = dofs * cm["bytes_per_dof"]["2"] * cm["memory_margin"] / 1e9 + cm["base_rss_GB"]
cpu_s = dofs * cm["cpu_s_per_dof"]["2"]
job = {"key": "interleaved_2_j01__P_ref__L2", "kind": "solve", "layout": src["layout"], "load": "P_ref", "level": 2,
       "power_W": src["power_W"], "cfg": cfg, "out": "research/o002_e007/l2_timing/record_interleaved_2_j01.json",
       "compare_to": {"level0": "research/o002_e007/a4_strata/work_l0/solves/interleaved_2_j01__P_ref__L0.json",
                      "level1": "research/o002_e007/dev_work/solves/interleaved_2_j01__P_ref__L1.json"},
       "note": (f"T0464 / review T0463 (5): level-2 reference of interleaved_2_j01 at P_ref, to check whether the "
                f"interleaved/2 reference spread (level 0 -> 1: -0.078 / -0.084 K) has converged at the scale of L1's "
                f"spread errors (-0.019 to -0.055 K); also a second cpu_s / wall_s point. est. DOF {dofs}, est. "
                f"{gb:.1f} GB with margin, est. {cpu_s / 60:.0f} CPU-min at {cm['cpu_s_per_dof']['2'] * 1e6:.0f} us/DOF; "
                "does not fit the local 10 GB limit: burst only")}
p = ROOT / "research/o002_e007/l2_timing/job_interleaved_2_j01.json"
p.write_text(json.dumps(job, indent=1) + "\n")
print(p.name, dofs, round(gb, 1), round(cpu_s / 60, 1))
