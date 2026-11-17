# ModuleForge status
_generated 2026-11-17T02:06:30+00:00 from repository state — do not edit_

## Founder inbox (2 open)
- **I0205** [external_action] [O008] Burst VM for E011's development L2 draws (band bound, joint operating characteristic, dev rows)
- **I0209** [external_action] [O004] O004: two F7 burst-VM runs before E004 registration, and a budget warning

## Objectives
| id | status | verdict | evals | spent | title |
|---|---|---|---|---|---|
| O000 | passed | PASS | 1/2 | $0.50/$20 | Framework canary — the loop carries a known-answer hypothesis from plan to verdict |
| O001 | passed | PASS | 1/3 | $287.86/$315 | L1 PEEC ranks half-bridge layouts faithfully enough to drive layout search |
| O002 | active | - | 0/1 | $50.26/$120 | A fast L1 thermal model predicts each die's average junction temperature, the spread across paralleled dies and layout-to-layout differences well enough to drive search |
| O003 | needs_founder | - | 0/1 | $258.22/$265 | Reference wire-bonded half-bridge layouts leave >= 20 % loop-inductance headroom inside their own housing at <= +2 K Tj |
| O004 | active | - | 0/1 | $69.57/$100 | The L2 inductance reference agrees with an independent field solver on the inductance ratios of re-layouts of PowerSynth public sample designs |
| O005 | draft | - | 0/2 | $7.65/$60 | L1 picks near-best layouts within a fixed family and die count, the regime derivative re-layout searches |
| O006 | active | INCONCLUSIVE | 1/1 | $137.91/$140 | The thermal L2 reference matches converged analytic solutions and an independent FEM, and design pilots measure what O002-O004 must fix |
| O007 | passed | PASS | 1/1 | $92.55/$110 | The scikit-fem thermal reference matches converged analytic solutions and the in-house finite-volume L2 on generator layouts |
| O008 | active | - | 0/2 | $52.43/$140 | A search seeded at a degraded copy of a near-optimal layout recovers it, where inductance-blind heuristics do not, on every designer-derived development layout |
| O901 | passed | PASS | 1/2 | $9.19/$30 | Infrastructure canary v2 - a known answer through registered, sealed, recomputed and null-checked evidence |

## Usage (from run records)
| objective | runs | usd | output tokens | thinking | denials | limit hits |
|---|---|---|---|---|---|---|
| O002 | 23 | $50.26 | 1066267 | 589953 | 71 | 0 |
| O003 | 135 | $258.22 | 4105839 | 2002393 | 280 | 0 |
| O004 | 36 | $69.57 | 1227257 | 758579 | 90 | 0 |
| O005 | 4 | $7.65 | 185443 | 108670 | 29 | 0 |
| O006 | 69 | $137.91 | 2633380 | 1435121 | 137 | 0 |
| O007 | 50 | $92.55 | 1684141 | 838123 | 79 | 1 |
| O008 | 31 | $52.43 | 1139532 | 668051 | 96 | 0 |
| O901 | 3 | $5.05 | 101607 | 52842 | 14 | 0 |

## Tasks
cancelled: 45, done: 366, failed: 4, review: 1, running: 3, todo: 10

- T0382 `running` scientist/design_experiment: Design E011: draft spec and runner (selftest, smoke, development mode with the burst job manifest) (attempt 1)
- T0387 `running` scientist/investigate: F7(b)-(d) l2_layout check on Case 4 development pairs: ladder, ratio estimates, F1 exclusion rate, VM job list (attempt 2)
- T0395 `review` builder/implement: L1 thermal model in src/moduleforge/thermal/ (n1's chosen design), tested against analytic limits, symmetry and power scaling, with a speed benchmark (attempt 2)
- T0424 `running` critic/review: Review T0395 (numerics) (attempt 1)

## Recent events
- 2026-11-17T01:17:04+00:00 run_finished {"run": "T0420-critic-20261116T170523-fb3c", "status": "completed", "cost": 2.109277, "subtype": "success", "report": "structured_output"}
- 2026-11-17T01:26:21+00:00 founder_decision_recorded {"objective": "O002", "summary": "E007: one-sided 97 % Woodruff bounds (level 0.94); 300 layouts, 20 per stratum"}
- 2026-11-17T01:28:20+00:00 inbox_opened {"id": "I0231", "kind": "protected_change", "subject": "T0396: merge needs founder approval"}
- 2026-11-17T01:28:29+00:00 run_started {"run": "T0429-critic-20261116T172829-54ef", "task": "T0429", "role": "critic", "session": "0b06a88d-e5e8-4436-adb7-ef2c4c1392bf"}
- 2026-11-17T01:28:31+00:00 run_started {"run": "T0423-critic-20261116T172831-33cc", "task": "T0423", "role": "critic", "session": "dfa3caa0-cae2-48f2-bb91-c024d5f5e08d"}
- 2026-11-17T01:34:10+00:00 run_finished {"run": "T0429-critic-20261116T172829-54ef", "status": "completed", "cost": 2.132347, "subtype": "success", "report": "structured_output"}
- 2026-11-17T01:41:04+00:00 founder_decision_recorded {"objective": "O004", "summary": "F1 caps relative: E_R / r <= 0.5 % (l2_layout), 1 % (FastHenry); decided before burst-1 results"}
- 2026-11-17T01:49:16+00:00 task_failed_attempt {"task": "T0387", "signal": "dod_failed", "action": "repair"}
- 2026-11-17T01:49:28+00:00 run_started {"run": "T0387-scientist-20261116T174928-dac5", "task": "T0387", "role": "scientist", "session": "787e3504-a026-4db1-8e0b-8affd84c21c8"}
- 2026-11-17T01:49:38+00:00 inbox_resolved {"id": "I0230", "status": "approved", "note": "T0385 merge approved (reviews T0427, T0428 accept with caveats). Caveats routed to T0389: deterministic multipole
- 2026-11-17T01:49:40+00:00 inbox_resolved {"id": "I0231", "status": "approved", "note": "T0396 merge approved (review T0420 accepts with caveats; routed to T0397/T0398). Founder decisions: one-sided 97 
- 2026-11-17T01:50:13+00:00 merged {"task": "T0385"}
- 2026-11-17T02:05:15+00:00 task_failed_attempt {"task": "T0396", "signal": "dod_failed", "action": "repair"}
- 2026-11-17T02:06:11+00:00 run_finished {"run": "T0423-critic-20261116T172831-33cc", "status": "completed", "cost": 1.805304, "subtype": "success", "report": "structured_output"}
- 2026-11-17T02:06:30+00:00 run_started {"run": "T0424-critic-20261116T180630-44d0", "task": "T0424", "role": "critic", "session": "7e3c1719-f002-4eaa-bbfe-e021fca01811"}
