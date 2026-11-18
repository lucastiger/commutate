"""T0464: E007's fixed allocation at m = 32 layouts per (family, dies) stratum, 480 layouts (D0027 decision 2, amending
D0025 decision 2). Writes research/o002_e007/allocation_m32.json, which E007.yaml's config.allocation.source names and
the runner's freeze checks read (layouts_per_stratum per stratum, bound.ci_spec). The power and coverage evidence at
m = 32 is T0456's corrected simulation (research/o002_e007/a4_strata/sim_corrected.json, consistency check passed);
figures are copied from it with Wilson 95 % Monte Carlo intervals (Wilson 1927, JASA 22:209; reps per cell from the file).
T0396's m = 20 simulation (f3_simulation.json) is kept unchanged as history. No new simulation is run here."""
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
SIM = HERE / "a4_strata" / "sim_corrected.json"
F3 = HERE / "f3_simulation.json"
STRATA = [f"{f}/{k}" for f in ("side_by_side", "interleaved", "u_shaped") for k in range(2, 7)]
M = 32


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def wilson(p: float, n: int, z: float = 1.959963984540054) -> list[float]:
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(max(0.0, c - h), 4), round(min(1.0, c + h), 4)]


sim = json.loads(SIM.read_text())
f3 = json.loads(F3.read_text())
assert sim["task"] == "T0456" and sim["bound"] == f3["bound"]["selected"] == "V4_t_outward_bonferroni_l094"
assert sim["consistency"]["normal"]["A4"]["pass"] is True
n = int(sim["reps_per_cell"])
ev: dict = {}
for err in ("normal", "t3"):
    pc, kc = sim["cells"][f"power|{err}|{M}"], sim["cells"][f"kill|{err}|{M}"]
    assert pc["reps"] == kc["reps"] == n
    ev[err] = {
        "joint_power": pc["power_joint"], "joint_power_ci95": wilson(pc["power_joint"], n),
        "A4_power": pc["power_each"]["A4"], "A4_power_ci95": wilson(pc["power_each"]["A4"], n),
        "min_V4_coverage_power_cell": min(pc["coverage"].values()),
        "min_V4_coverage_power_cell_ci95": wilson(min(pc["coverage"].values()), n),
        "min_V4_coverage_kill_cell": min(kc["coverage"].values()),
        "kill_side_at_1.2x_kill_thresholds": {k: {"p_fire": v, "ci95": wilson(v, n)} for k, v in kc["p_fire"].items()},
        "kill_cell_scale_factors": kc["k"],
    }
min_cov_all = min(min(c["coverage"].values()) for c in sim["cells"].values())
out = {
    "task": "T0464", "experiment": "E007", "kind": "fixed allocation (registration input, not evidence of the hypothesis)",
    "decision": "D0027 decision 2 (founder, 2026-11-18; amends D0025 decision 2): m = 32 layouts per (family, dies) "
                "stratum, 480 layouts in all, chosen for kill-side power",
    "layouts_per_stratum": {s: M for s in STRATA}, "n_strata": len(STRATA), "n_layouts": M * len(STRATA),
    "bound": {"selected": f3["bound"]["selected"], "variant": f3["bound"]["variant"], "ci_spec": f3["bound"]["ci_spec"],
              "decision": "D0025 decision 1 (unchanged)"},
    "power_coverage_evidence": {
        "source": str(SIM.relative_to(ROOT)), "source_sha256": sha(SIM), "task": "T0456", "seed": sim["seed"],
        "reps_per_cell": n, "truth_reps": sim["truth_reps"],
        "consistency_check": "passed: simulated median A4 0.108 (normal) / 0.107 (t3) against 0.107 measured on T0398's "
                             "rows (sim_corrected.json consistency.*.A4); A3 is over-predicted by 30-40 % (measured "
                             "outside the simulated 5-95 % band), so kill-side rates are approximate (D0027 context)",
        "scenario_power": "the L1 as measured on development rows (T0398 + T0456; kb = kc = kd = 1)",
        "scenario_kill": "every error scale raised so that each kill statistic's truth is 1.2 x its kill threshold",
        "at_m32": ev, "min_V4_coverage_all_cells_all_m": min_cov_all,
        "mc_interval": "Wilson score 95 % on reps_per_cell Bernoulli trials (Monte Carlo uncertainty only; model "
                       "uncertainty is not included)",
    },
    "history": {"source": str(F3.relative_to(ROOT)), "source_sha256": sha(F3), "task": "T0396",
                "note": "T0396's m = 20 allocation and simulation (D0025), with its disclosure of the amended selection "
                        "rule (round 1 kept in f3_simulation_r1_noselection.json); unchanged, superseded for the "
                        "allocation by this file"},
}
p = HERE / "allocation_m32.json"
p.write_text(json.dumps(out, indent=1) + "\n")
print(json.dumps(ev, indent=1))
print("min cov all", min_cov_all)
print(p, sha(p))
