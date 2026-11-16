# ModuleForge status
_generated 2026-11-16T15:00:16+00:00 from repository state — do not edit_

## Founder inbox (3 open)
- **I0205** [external_action] [O008] Burst VM for E011's development L2 draws (band bound, joint operating characteristic, dev rows)
- **I0209** [external_action] [O004] O004: two F7 burst-VM runs before E004 registration, and a budget warning
- **I0212** [external_action] [O002] Burst VM run of n2's level-2 development solves (F1 pre-registration check)

## Objectives
| id | status | verdict | evals | spent | title |
|---|---|---|---|---|---|
| O000 | passed | PASS | 1/2 | $0.50/$20 | Framework canary — the loop carries a known-answer hypothesis from plan to verdict |
| O001 | passed | PASS | 1/3 | $287.86/$315 | L1 PEEC ranks half-bridge layouts faithfully enough to drive layout search |
| O002 | active | - | 0/1 | $33.79/$120 | A fast L1 thermal model predicts each die's average junction temperature, the spread across paralleled dies and layout-to-layout differences well enough to drive search |
| O003 | needs_founder | - | 0/1 | $258.22/$265 | Reference wire-bonded half-bridge layouts leave >= 20 % loop-inductance headroom inside their own housing at <= +2 K Tj |
| O004 | active | - | 0/1 | $42.95/$100 | The L2 inductance reference agrees with an independent field solver on the inductance ratios of re-layouts of PowerSynth public sample designs |
| O005 | draft | - | 0/2 | $7.65/$60 | L1 picks near-best layouts within a fixed family and die count, the regime derivative re-layout searches |
| O006 | active | INCONCLUSIVE | 1/1 | $137.91/$140 | The thermal L2 reference matches converged analytic solutions and an independent FEM, and design pilots measure what O002-O004 must fix |
| O007 | passed | PASS | 1/1 | $92.55/$110 | The scikit-fem thermal reference matches converged analytic solutions and the in-house finite-volume L2 on generator layouts |
| O008 | active | - | 0/2 | $40.34/$140 | A search seeded at a degraded copy of a near-optimal layout recovers it, where inductance-blind heuristics do not, on every designer-derived development layout |
| O901 | passed | PASS | 1/2 | $9.19/$30 | Infrastructure canary v2 - a known answer through registered, sealed, recomputed and null-checked evidence |

## Usage (from run records)
| objective | runs | usd | output tokens | thinking | denials | limit hits |
|---|---|---|---|---|---|---|
| O002 | 16 | $33.79 | 746698 | 435011 | 51 | 0 |
| O003 | 135 | $258.22 | 4105839 | 2002393 | 280 | 0 |
| O004 | 26 | $42.95 | 941817 | 611635 | 61 | 0 |
| O005 | 4 | $7.65 | 185443 | 108670 | 29 | 0 |
| O006 | 69 | $137.91 | 2633380 | 1435121 | 137 | 0 |
| O007 | 50 | $92.55 | 1684141 | 838123 | 79 | 1 |
| O008 | 21 | $40.34 | 901416 | 553192 | 68 | 0 |
| O901 | 3 | $5.05 | 101607 | 52842 | 14 | 0 |

## Tasks
cancelled: 45, done: 345, failed: 4, running: 2, todo: 17

- T0384 `running` builder/implement: FastHenry deck exporter in src: Layout -> SI-metre deck with refinable wire section, thickness and plane knobs, F6 model variants (attempt 3)
- T0386 `running` builder/implement: Frozen perturbation rules on the 1 mm lattice: die-row shift, power-trace width, terminal-near copper, wire landing (generate/perturb.py) (attempt 3)

## Recent events
- 2026-11-16T14:11:20+00:00 merged {"task": "T0377"}
- 2026-11-16T14:17:48+00:00 merged {"task": "T0392"}
- 2026-11-16T14:24:10+00:00 merged {"task": "T0393"}
- 2026-11-16T14:30:41+00:00 merged {"task": "T0394"}
- 2026-11-16T14:30:47+00:00 run_started {"run": "T0413-planner-20261116T063047-98ff", "task": "T0413", "role": "planner", "session": "a91cab91-cf42-4072-8063-18f6ae26628f"}
- 2026-11-16T14:30:48+00:00 run_started {"run": "T0378-builder-20261116T063048-cc86", "task": "T0378", "role": "builder", "session": "09c86f72-5b9d-4300-b748-a86c1ca85a30"}
- 2026-11-16T14:30:48+00:00 run_started {"run": "T0384-builder-20261116T063048-5eee", "task": "T0384", "role": "builder", "session": "72b206c3-26b7-4871-9ef2-a405570784a6"}
- 2026-11-16T14:31:23+00:00 sleep_detected {"gap_s": 3289, "runs_extended": 3}
- 2026-11-16T14:33:50+00:00 replan_declined {"objective": "O008", "reason": "T0376 kill shot did not fire; approved plan stands; T0413 stopped"}
- 2026-11-16T14:34:11+00:00 run_stopped_for_founder {"run": "T0413-planner-20261116T063047-98ff", "task": "T0413", "task_status": "cancelled"}
- 2026-11-16T14:34:11+00:00 run_finished {"run": "T0413-planner-20261116T063047-98ff", "status": "error", "cost": 1.211135, "subtype": "error_during_execution", "report": "missing"}
- 2026-11-16T14:34:11+00:00 founder_stopped {"task": "T0413", "run": "T0413-planner-20261116T063047-98ff", "run_status": "error", "task_status": "cancelled"}
- 2026-11-16T14:34:17+00:00 run_started {"run": "T0386-builder-20261116T063417-22a2", "task": "T0386", "role": "builder", "session": "6d2cb963-af9a-4c6b-9ef7-7aeedfedd369"}
- 2026-11-16T15:00:08+00:00 run_finished {"run": "T0378-builder-20261116T063048-cc86", "status": "error", "cost": 0.975169, "subtype": "success", "report": "missing"}
- 2026-11-16T15:00:08+00:00 capacity_backoff {"task": "T0378", "minutes": 5, "parsed_reset": false}
