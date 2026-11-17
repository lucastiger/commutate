# ModuleForge status
_generated 2026-11-17T04:46:35+00:00 from repository state — do not edit_

## Founder inbox (2 open)
- **I0205** [external_action] [O008] Burst VM for E011's development L2 draws (band bound, joint operating characteristic, dev rows)
- **I0209** [external_action] [O004] O004: two F7 burst-VM runs before E004 registration, and a budget warning

## Objectives
| id | status | verdict | evals | spent | title |
|---|---|---|---|---|---|
| O000 | passed | PASS | 1/2 | $0.50/$20 | Framework canary — the loop carries a known-answer hypothesis from plan to verdict |
| O001 | passed | PASS | 1/3 | $287.86/$315 | L1 PEEC ranks half-bridge layouts faithfully enough to drive layout search |
| O002 | active | - | 0/1 | $56.44/$120 | A fast L1 thermal model predicts each die's average junction temperature, the spread across paralleled dies and layout-to-layout differences well enough to drive search |
| O003 | needs_founder | - | 0/1 | $258.22/$265 | Reference wire-bonded half-bridge layouts leave >= 20 % loop-inductance headroom inside their own housing at <= +2 K Tj |
| O004 | active | - | 0/1 | $74.03/$100 | The L2 inductance reference agrees with an independent field solver on the inductance ratios of re-layouts of PowerSynth public sample designs |
| O005 | draft | - | 0/2 | $7.65/$60 | L1 picks near-best layouts within a fixed family and die count, the regime derivative re-layout searches |
| O006 | active | INCONCLUSIVE | 1/1 | $137.91/$140 | The thermal L2 reference matches converged analytic solutions and an independent FEM, and design pilots measure what O002-O004 must fix |
| O007 | passed | PASS | 1/1 | $92.55/$110 | The scikit-fem thermal reference matches converged analytic solutions and the in-house finite-volume L2 on generator layouts |
| O008 | active | - | 0/2 | $66.18/$140 | A search seeded at a degraded copy of a near-optimal layout recovers it, where inductance-blind heuristics do not, on every designer-derived development layout |
| O901 | passed | PASS | 1/2 | $9.19/$30 | Infrastructure canary v2 - a known answer through registered, sealed, recomputed and null-checked evidence |

## Usage (from run records)
| objective | runs | usd | output tokens | thinking | denials | limit hits |
|---|---|---|---|---|---|---|
| O002 | 27 | $56.44 | 1165244 | 632816 | 88 | 0 |
| O003 | 135 | $258.22 | 4105839 | 2002393 | 280 | 0 |
| O004 | 38 | $74.03 | 1291737 | 789492 | 95 | 0 |
| O005 | 4 | $7.65 | 185443 | 108670 | 29 | 0 |
| O006 | 69 | $137.91 | 2633380 | 1435121 | 137 | 0 |
| O007 | 50 | $92.55 | 1684141 | 838123 | 79 | 1 |
| O008 | 35 | $66.18 | 1174562 | 681708 | 101 | 0 |
| O901 | 3 | $5.05 | 101607 | 52842 | 14 | 0 |

## Tasks
cancelled: 45, done: 375, failed: 4, running: 3, todo: 7

- T0382 `running` scientist/design_experiment: Design E011: draft spec and runner (selftest, smoke, development mode with the burst job manifest) (attempt 2)
- T0388 `running` scientist/design_experiment: E004 design, part 1: draft spec and registration stage (frozen references, sealed-seed pairs, F2/F4 checks on L1) (attempt 1)
- T0397 `running` scientist/design_experiment: E007 design: draft spec and runner (sealed seeds, per-stratum P_ref, level-1 judging with a level-2 subset, F2 nulls, F4/F6/F7 reports, code freeze, cost plan) (attempt 1)

## Recent events
- 2026-11-17T04:08:25+00:00 run_finished {"run": "T0433-critic-20261116T200236-ec02", "status": "completed", "cost": 2.174218, "subtype": "success", "report": "structured_output"}
- 2026-11-17T04:20:01+00:00 inbox_opened {"id": "I0233", "kind": "protected_change", "subject": "T0387: merge needs founder approval"}
- 2026-11-17T04:20:08+00:00 run_started {"run": "T0419-builder-20261116T202008-a7e3", "task": "T0419", "role": "builder", "session": "a93ed5af-d43b-43bd-b972-d9b7190fa28e"}
- 2026-11-17T04:20:44+00:00 run_finished {"run": "T0432-critic-20261116T200148-ee9f", "status": "completed", "cost": 2.016062, "subtype": "success", "report": "structured_output"}
- 2026-11-17T04:20:44+00:00 run_finished {"run": "T0434-critic-20261116T200238-d529", "status": "completed", "cost": 2.186503, "subtype": "success", "report": "structured_output"}
- 2026-11-17T04:20:47+00:00 task_failed_attempt {"task": "T0382", "signal": "review_rejected", "action": "repair"}
- 2026-11-17T04:25:17+00:00 founder_decision_recorded {"objective": "O002", "summary": "cpu_hours counts process CPU time, not VM vCPU-hours; m decided before registration from T0398 power figures"}
- 2026-11-17T04:26:21+00:00 inbox_resolved {"id": "I0233", "status": "approved", "note": "T0387 merge approved (reviews T0429, T0433 accept with caveats). F7(c) pending burst 1 (I0209). Founder decisions
- 2026-11-17T04:31:59+00:00 merged {"task": "T0396"}
- 2026-11-17T04:32:06+00:00 run_started {"run": "T0382-scientist-20261116T203206-7d22", "task": "T0382", "role": "scientist", "session": "73706935-ec37-4464-be34-f830d2b13e2b"}
- 2026-11-17T04:32:07+00:00 run_started {"run": "T0397-scientist-20261116T203207-5b71", "task": "T0397", "role": "scientist", "session": "5072e1f5-521e-4316-9c8d-f94880d2ed87"}
- 2026-11-17T04:45:37+00:00 merged {"task": "T0387"}
- 2026-11-17T04:46:25+00:00 run_finished {"run": "T0419-builder-20261116T202008-a7e3", "status": "completed", "cost": 0.488094, "subtype": "success", "report": "structured_output"}
- 2026-11-17T04:46:25+00:00 task_failed_attempt {"task": "T0419", "signal": "scope_violation", "action": "repair"}
- 2026-11-17T04:46:35+00:00 run_started {"run": "T0388-scientist-20261116T204635-8522", "task": "T0388", "role": "scientist", "session": "c2354df4-f911-45a7-bcc2-2913c851964c"}
