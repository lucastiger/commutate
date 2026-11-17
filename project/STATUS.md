# ModuleForge status
_generated 2026-11-17T04:01:48+00:00 from repository state — do not edit_

## Founder inbox (2 open)
- **I0205** [external_action] [O008] Burst VM for E011's development L2 draws (band bound, joint operating characteristic, dev rows)
- **I0209** [external_action] [O004] O004: two F7 burst-VM runs before E004 registration, and a budget warning

## Objectives
| id | status | verdict | evals | spent | title |
|---|---|---|---|---|---|
| O000 | passed | PASS | 1/2 | $0.50/$20 | Framework canary — the loop carries a known-answer hypothesis from plan to verdict |
| O001 | passed | PASS | 1/3 | $287.86/$315 | L1 PEEC ranks half-bridge layouts faithfully enough to drive layout search |
| O002 | active | - | 0/1 | $53.77/$120 | A fast L1 thermal model predicts each die's average junction temperature, the spread across paralleled dies and layout-to-layout differences well enough to drive search |
| O003 | needs_founder | - | 0/1 | $258.22/$265 | Reference wire-bonded half-bridge layouts leave >= 20 % loop-inductance headroom inside their own housing at <= +2 K Tj |
| O004 | active | - | 0/1 | $71.86/$100 | The L2 inductance reference agrees with an independent field solver on the inductance ratios of re-layouts of PowerSynth public sample designs |
| O005 | draft | - | 0/2 | $7.65/$60 | L1 picks near-best layouts within a fixed family and die count, the regime derivative re-layout searches |
| O006 | active | INCONCLUSIVE | 1/1 | $137.91/$140 | The thermal L2 reference matches converged analytic solutions and an independent FEM, and design pilots measure what O002-O004 must fix |
| O007 | passed | PASS | 1/1 | $92.55/$110 | The scikit-fem thermal reference matches converged analytic solutions and the in-house finite-volume L2 on generator layouts |
| O008 | active | - | 0/2 | $59.67/$140 | A search seeded at a degraded copy of a near-optimal layout recovers it, where inductance-blind heuristics do not, on every designer-derived development layout |
| O901 | passed | PASS | 1/2 | $9.19/$30 | Infrastructure canary v2 - a known answer through registered, sealed, recomputed and null-checked evidence |

## Usage (from run records)
| objective | runs | usd | output tokens | thinking | denials | limit hits |
|---|---|---|---|---|---|---|
| O002 | 24 | $53.77 | 1117218 | 609089 | 81 | 0 |
| O003 | 135 | $258.22 | 4105839 | 2002393 | 280 | 0 |
| O004 | 36 | $71.85 | 1263841 | 775291 | 91 | 0 |
| O005 | 4 | $7.65 | 185443 | 108670 | 29 | 0 |
| O006 | 69 | $137.91 | 2633380 | 1435121 | 137 | 0 |
| O007 | 50 | $92.55 | 1684141 | 838123 | 79 | 1 |
| O008 | 34 | $59.67 | 1141503 | 668112 | 96 | 0 |
| O901 | 3 | $5.05 | 101607 | 52842 | 14 | 0 |

## Tasks
cancelled: 45, done: 368, failed: 4, review: 3, running: 3, todo: 11

- T0382 `review` scientist/design_experiment: Design E011: draft spec and runner (selftest, smoke, development mode with the burst job manifest) (attempt 1)
- T0387 `review` scientist/investigate: F7(b)-(d) l2_layout check on Case 4 development pairs: ladder, ratio estimates, F1 exclusion rate, VM job list (attempt 2)
- T0396 `review` scientist/design_experiment: E007 statistics: F3 coverage and power simulation, bound selection and fixed allocation; protected mfos.metrics additions drafted as a patch (attempt 2)
- T0430 `running` critic/review: Review T0382 (physics) (attempt 1)
- T0431 `running` critic/review: Review T0382 (numerics) (attempt 1)
- T0432 `running` critic/review: Review T0382 (statistics) (attempt 1)

## Recent events
- 2026-11-17T02:28:21+00:00 run_finished {"run": "T0424-critic-20261116T180630-44d0", "status": "completed", "cost": 2.372777, "subtype": "success", "report": "structured_output"}
- 2026-11-17T02:35:20+00:00 founder_decision_recorded {"objective": "O002", "summary": "T0395 c(s) accepted despite 0.0059 family spread at 4.0 mm; T0398 dev rows check transfer per stratum"}
- 2026-11-17T03:09:50+00:00 inbox_opened {"id": "I0232", "kind": "protected_change", "subject": "T0395: merge needs founder approval"}
- 2026-11-17T03:09:55+00:00 run_started {"run": "T0396-scientist-20261116T190955-cede", "task": "T0396", "role": "scientist", "session": "ca0b9fb8-e7fa-49e0-bc62-cd53be733675"}
- 2026-11-17T03:10:31+00:00 run_finished {"run": "T0382-scientist-20261116T160030-8287", "status": "completed", "cost": 7.238998, "subtype": "success", "report": "structured_output"}
- 2026-11-17T03:28:19+00:00 inbox_resolved {"id": "I0232", "status": "approved", "note": "T0395 merge approved (reviews T0423, T0424 accept with caveats). Founder accepts the 1.5 mm grid rule and c(s) de
- 2026-11-17T03:32:12+00:00 verified {"task": "T0382"}
- 2026-11-17T03:32:12+00:00 run_finished {"run": "T0387-scientist-20261116T174928-dac5", "status": "completed", "cost": 2.284848, "subtype": "success", "report": "structured_output"}
- 2026-11-17T03:43:06+00:00 verified {"task": "T0387"}
- 2026-11-17T03:43:13+00:00 merged {"task": "T0395"}
- 2026-11-17T03:43:24+00:00 run_started {"run": "T0430-critic-20261116T194324-4b9d", "task": "T0430", "role": "critic", "session": "d06465ed-4d4c-4ae3-bee4-618e05cb0d09"}
- 2026-11-17T03:43:26+00:00 run_started {"run": "T0431-critic-20261116T194326-6d60", "task": "T0431", "role": "critic", "session": "d4501822-0a07-40c7-82ec-826905757fbd"}
- 2026-11-17T03:48:17+00:00 run_finished {"run": "T0396-scientist-20261116T190955-cede", "status": "completed", "cost": 1.141333, "subtype": "success", "report": "structured_output"}
- 2026-11-17T04:01:36+00:00 verified {"task": "T0396"}
- 2026-11-17T04:01:48+00:00 run_started {"run": "T0432-critic-20261116T200148-ee9f", "task": "T0432", "role": "critic", "session": "f79b67f6-66d3-4817-a338-a8de5299cb4c"}
