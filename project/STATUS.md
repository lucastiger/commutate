# ModuleForge status
_generated 2026-11-17T05:52:22+00:00 from repository state — do not edit_

## Founder inbox (2 open)
- **I0205** [external_action] [O008] Burst VM for E011's development L2 draws (band bound, joint operating characteristic, dev rows)
- **I0209** [external_action] [O004] O004: two F7 burst-VM runs before E004 registration, and a budget warning

## Objectives
| id | status | verdict | evals | spent | title |
|---|---|---|---|---|---|
| O000 | passed | PASS | 1/2 | $0.50/$20 | Framework canary — the loop carries a known-answer hypothesis from plan to verdict |
| O001 | passed | PASS | 1/3 | $287.86/$315 | L1 PEEC ranks half-bridge layouts faithfully enough to drive layout search |
| O002 | active | - | 0/1 | $65.61/$120 | A fast L1 thermal model predicts each die's average junction temperature, the spread across paralleled dies and layout-to-layout differences well enough to drive search |
| O003 | needs_founder | - | 0/1 | $258.22/$265 | Reference wire-bonded half-bridge layouts leave >= 20 % loop-inductance headroom inside their own housing at <= +2 K Tj |
| O004 | active | - | 0/1 | $77.80/$100 | The L2 inductance reference agrees with an independent field solver on the inductance ratios of re-layouts of PowerSynth public sample designs |
| O005 | draft | - | 0/2 | $7.65/$60 | L1 picks near-best layouts within a fixed family and die count, the regime derivative re-layout searches |
| O006 | active | INCONCLUSIVE | 1/1 | $137.91/$140 | The thermal L2 reference matches converged analytic solutions and an independent FEM, and design pilots measure what O002-O004 must fix |
| O007 | passed | PASS | 1/1 | $92.55/$110 | The scikit-fem thermal reference matches converged analytic solutions and the in-house finite-volume L2 on generator layouts |
| O008 | active | - | 0/2 | $66.18/$140 | A search seeded at a degraded copy of a near-optimal layout recovers it, where inductance-blind heuristics do not, on every designer-derived development layout |
| O901 | passed | PASS | 1/2 | $9.19/$30 | Infrastructure canary v2 - a known answer through registered, sealed, recomputed and null-checked evidence |

## Usage (from run records)
| objective | runs | usd | output tokens | thinking | denials | limit hits |
|---|---|---|---|---|---|---|
| O002 | 28 | $65.61 | 1320501 | 693417 | 94 | 0 |
| O003 | 135 | $258.22 | 4105839 | 2002393 | 280 | 0 |
| O004 | 40 | $77.80 | 1357915 | 813085 | 96 | 0 |
| O005 | 4 | $7.65 | 185443 | 108670 | 29 | 0 |
| O006 | 69 | $137.91 | 2633380 | 1435121 | 137 | 0 |
| O007 | 50 | $92.55 | 1684141 | 838123 | 79 | 1 |
| O008 | 35 | $66.18 | 1174562 | 681708 | 101 | 0 |
| O901 | 3 | $5.05 | 101607 | 52842 | 14 | 0 |

## Tasks
cancelled: 45, done: 376, failed: 4, review: 2, running: 3, todo: 11

- T0382 `running` scientist/design_experiment: Design E011: draft spec and runner (selftest, smoke, development mode with the burst job manifest) (attempt 2)
- T0388 `review` scientist/design_experiment: E004 design, part 1: draft spec and registration stage (frozen references, sealed-seed pairs, F2/F4 checks on L1) (attempt 1)
- T0397 `review` scientist/design_experiment: E007 design: draft spec and runner (sealed seeds, per-stratum P_ref, level-1 judging with a level-2 subset, F2 nulls, F4/F6/F7 reports, code freeze, cost plan) (attempt 1)
- T0440 `running` critic/review: Review T0388 (physics) (attempt 1)
- T0441 `running` critic/review: Review T0388 (numerics) (attempt 1)

## Recent events
- 2026-11-17T04:46:25+00:00 task_failed_attempt {"task": "T0419", "signal": "scope_violation", "action": "repair"}
- 2026-11-17T04:46:35+00:00 run_started {"run": "T0388-scientist-20261116T204635-8522", "task": "T0388", "role": "scientist", "session": "c2354df4-f911-45a7-bcc2-2913c851964c"}
- 2026-11-17T04:47:12+00:00 task_reassigned {"task": "T0419", "frm": "builder", "to": "scientist", "reason": "all touches under research/, outside builder write scope"}
- 2026-11-17T05:16:09+00:00 state_commit_deferred {"reason": "staged by someone else: tests/mfos/test_metrics.py, tools/mfos/mfos/evaluate.py, tools/mfos/mfos/metrics.py, tools/mfos/mfos/models.py"}
- 2026-11-17T05:24:24+00:00 run_finished {"run": "T0397-scientist-20261116T203207-5b71", "status": "completed", "cost": 6.87434, "subtype": "success", "report": "structured_output"}
- 2026-11-17T05:38:06+00:00 verified {"task": "T0397"}
- 2026-11-17T05:38:19+00:00 run_started {"run": "T0435-critic-20261116T213819-f37d", "task": "T0435", "role": "critic", "session": "d5e075a0-da7a-4610-b760-7ca81df08dd0"}
- 2026-11-17T05:38:54+00:00 run_finished {"run": "T0388-scientist-20261116T204635-8522", "status": "completed", "cost": 3.765979, "subtype": "success", "report": "structured_output"}
- 2026-11-17T05:41:35+00:00 task_added {"task": "T0437", "note": "founder approved 2026-11-17"}
- 2026-11-17T05:41:35+00:00 task_added {"task": "T0438", "note": "founder approved 2026-11-17"}
- 2026-11-17T05:41:35+00:00 task_added {"task": "T0439", "note": "founder approved 2026-11-17"}
- 2026-11-17T05:51:20+00:00 verified {"task": "T0388"}
- 2026-11-17T05:51:20+00:00 run_finished {"run": "T0435-critic-20261116T213819-f37d", "status": "completed", "cost": 2.287346, "subtype": "success", "report": "structured_output"}
- 2026-11-17T05:51:33+00:00 run_started {"run": "T0440-critic-20261116T215133-f3bf", "task": "T0440", "role": "critic", "session": "6a74a5a9-53ca-4edc-a0ef-d6c848c01ab4"}
- 2026-11-17T05:51:35+00:00 run_started {"run": "T0441-critic-20261116T215135-cb4c", "task": "T0441", "role": "critic", "session": "bdb6933a-d808-4b2c-a1b8-832ec7b358ea"}
