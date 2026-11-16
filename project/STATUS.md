# ModuleForge status
_generated 2026-11-16T00:42:08+00:00 from repository state — do not edit_

## Founder inbox (0 open)
- nothing needs you

## Objectives
| id | status | verdict | evals | spent | title |
|---|---|---|---|---|---|
| O000 | passed | PASS | 1/2 | $0.50/$20 | Framework canary — the loop carries a known-answer hypothesis from plan to verdict |
| O001 | passed | PASS | 1/3 | $287.86/$315 | L1 PEEC ranks half-bridge layouts faithfully enough to drive layout search |
| O002 | draft | - | 0/1 | $13.26/$120 | A fast L1 thermal model predicts each die's average junction temperature, the spread across paralleled dies and layout-to-layout differences well enough to drive search |
| O003 | needs_founder | - | 0/1 | $258.22/$265 | Reference wire-bonded half-bridge layouts leave >= 20 % loop-inductance headroom inside their own housing at <= +2 K Tj |
| O004 | draft | - | 0/1 | $23.71/$100 | The L2 inductance reference agrees with an independent field solver on the inductance ratios of re-layouts of PowerSynth public sample designs |
| O005 | draft | - | 0/2 | $7.65/$60 | L1 picks near-best layouts within a fixed family and die count, the regime derivative re-layout searches |
| O006 | active | INCONCLUSIVE | 1/1 | $137.91/$140 | The thermal L2 reference matches converged analytic solutions and an independent FEM, and design pilots measure what O002-O004 must fix |
| O007 | passed | PASS | 1/1 | $92.55/$110 | The scikit-fem thermal reference matches converged analytic solutions and the in-house finite-volume L2 on generator layouts |
| O008 | draft | - | 0/2 | $17.60/$140 | A search seeded at a degraded copy of a near-optimal layout recovers it, where inductance-blind heuristics do not, on every designer-derived development layout |
| O901 | passed | PASS | 1/2 | $9.19/$30 | Infrastructure canary v2 - a known answer through registered, sealed, recomputed and null-checked evidence |

## Usage (from run records)
| objective | runs | usd | output tokens | thinking | denials | limit hits |
|---|---|---|---|---|---|---|
| O002 | 8 | $13.26 | 332679 | 207945 | 32 | 0 |
| O003 | 135 | $258.22 | 4105839 | 2002393 | 280 | 0 |
| O004 | 14 | $23.71 | 549278 | 404912 | 35 | 0 |
| O005 | 4 | $7.65 | 185443 | 108670 | 29 | 0 |
| O006 | 69 | $137.91 | 2633380 | 1435121 | 137 | 0 |
| O007 | 50 | $92.55 | 1684141 | 838123 | 79 | 1 |
| O008 | 10 | $17.60 | 411688 | 300390 | 33 | 0 |
| O901 | 3 | $5.05 | 101607 | 52842 | 14 | 0 |

## Tasks
cancelled: 44, done: 321, failed: 4, running: 1

- T0369 `running` critic/review: Review OBJ-O002 (statistics) (attempt 1)

## Recent events
- 2026-11-16T00:06:06+00:00 run_finished {"run": "T0363-critic-20261115T155721-57be", "status": "completed", "cost": 2.260839, "subtype": "success", "report": "structured_output"}
- 2026-11-16T00:09:58+00:00 objective_draft_review {"objective": "O004", "ref": "a6fb177fef8ccf715f5b8d42c388109944d7f5ae", "tasks": ["T0365", "T0366"]}
- 2026-11-16T00:10:36+00:00 run_started {"run": "T0365-critic-20261115T161036-2811", "task": "T0365", "role": "critic", "session": "ff921fcd-1399-4288-88ef-7196a6a05f88"}
- 2026-11-16T00:10:37+00:00 run_started {"run": "T0366-critic-20261115T161037-9e05", "task": "T0366", "role": "critic", "session": "10d5e30e-584f-4dab-b2dc-d7a2f162b601"}
- 2026-11-16T00:17:26+00:00 run_finished {"run": "T0366-critic-20261115T161037-9e05", "status": "completed", "cost": 1.700482, "subtype": "success", "report": "structured_output"}
- 2026-11-16T00:17:27+00:00 run_finished {"run": "T0365-critic-20261115T161036-2811", "status": "completed", "cost": 1.782424, "subtype": "success", "report": "structured_output"}
- 2026-11-16T00:20:34+00:00 objective_draft_review {"objective": "O004", "ref": "5ea0dd66fab4b0f07d13e29c0982e1c433563c35", "tasks": ["T0367", "T0368"]}
- 2026-11-16T00:20:43+00:00 run_started {"run": "T0367-critic-20261115T162043-a8a7", "task": "T0367", "role": "critic", "session": "58181aef-1f80-45ce-b617-f737f4870951"}
- 2026-11-16T00:20:45+00:00 run_started {"run": "T0368-critic-20261115T162045-b43a", "task": "T0368", "role": "critic", "session": "e141db0a-663f-4bf8-8197-998999236aca"}
- 2026-11-16T00:28:50+00:00 run_finished {"run": "T0368-critic-20261115T162045-b43a", "status": "completed", "cost": 1.848675, "subtype": "success", "report": "structured_output"}
- 2026-11-16T00:28:50+00:00 run_finished {"run": "T0367-critic-20261115T162043-a8a7", "status": "completed", "cost": 1.801183, "subtype": "success", "report": "structured_output"}
- 2026-11-16T00:34:11+00:00 objective_draft_review {"objective": "O002", "ref": "7d9b7eb6657342c2fd3ce4e9950c02fab350472f", "tasks": ["T0369", "T0370"]}
- 2026-11-16T00:34:35+00:00 run_started {"run": "T0369-critic-20261115T163435-cb66", "task": "T0369", "role": "critic", "session": "537c3b7d-89b2-40af-93ad-6e00bdeb45e4"}
- 2026-11-16T00:34:36+00:00 run_started {"run": "T0370-critic-20261115T163436-82b8", "task": "T0370", "role": "critic", "session": "3e0168ba-3eca-477c-aeb4-c32d4cc099c4"}
- 2026-11-16T00:42:04+00:00 run_finished {"run": "T0370-critic-20261115T163436-82b8", "status": "completed", "cost": 1.819915, "subtype": "success", "report": "structured_output"}
