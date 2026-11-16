# ModuleForge status
_generated 2026-11-16T00:03:38+00:00 from repository state — do not edit_

## Founder inbox (0 open)
- nothing needs you

## Objectives
| id | status | verdict | evals | spent | title |
|---|---|---|---|---|---|
| O000 | passed | PASS | 1/2 | $0.50/$20 | Framework canary — the loop carries a known-answer hypothesis from plan to verdict |
| O001 | passed | PASS | 1/3 | $287.86/$315 | L1 PEEC ranks half-bridge layouts faithfully enough to drive layout search |
| O002 | draft | - | 0/1 | $11.44/$120 | A fast L1 thermal model predicts per-die Tj max, spread and layout-to-layout differences well enough to drive search |
| O003 | needs_founder | - | 0/1 | $258.22/$265 | Reference wire-bonded half-bridge layouts leave >= 20 % loop-inductance headroom inside their own housing at <= +2 K Tj |
| O004 | draft | - | 0/1 | $14.31/$100 | The L2 inductance reference agrees with an independent field solver on the inductance ratios of re-layouts of PowerSynth public sample designs |
| O005 | draft | - | 0/2 | $7.65/$60 | L1 picks near-best layouts within a fixed family and die count, the regime derivative re-layout searches |
| O006 | active | INCONCLUSIVE | 1/1 | $137.91/$140 | The thermal L2 reference matches converged analytic solutions and an independent FEM, and design pilots measure what O002-O004 must fix |
| O007 | passed | PASS | 1/1 | $92.55/$110 | The scikit-fem thermal reference matches converged analytic solutions and the in-house finite-volume L2 on generator layouts |
| O008 | draft | - | 0/2 | $17.60/$140 | A search seeded at a degraded copy of a near-optimal layout recovers it, where inductance-blind heuristics do not, on every designer-derived development layout |
| O901 | passed | PASS | 1/2 | $9.19/$30 | Infrastructure canary v2 - a known answer through registered, sealed, recomputed and null-checked evidence |

## Usage (from run records)
| objective | runs | usd | output tokens | thinking | denials | limit hits |
|---|---|---|---|---|---|---|
| O002 | 6 | $11.44 | 293351 | 180601 | 28 | 0 |
| O003 | 135 | $258.22 | 4105839 | 2002393 | 280 | 0 |
| O004 | 10 | $14.31 | 337284 | 242677 | 23 | 0 |
| O005 | 4 | $7.65 | 185443 | 108670 | 29 | 0 |
| O006 | 69 | $137.91 | 2633380 | 1435121 | 137 | 0 |
| O007 | 50 | $92.55 | 1684141 | 838123 | 79 | 1 |
| O008 | 10 | $17.60 | 411688 | 300390 | 33 | 0 |
| O901 | 3 | $5.05 | 101607 | 52842 | 14 | 0 |

## Tasks
cancelled: 44, done: 315, failed: 4, running: 1

- T0363 `running` critic/review: Review OBJ-O004 (statistics) (attempt 1)

## Recent events
- 2026-11-15T23:10:59+00:00 run_finished {"run": "T0358-critic-20261115T150329-1f20", "status": "completed", "cost": 1.718796, "subtype": "success", "report": "structured_output"}
- 2026-11-15T23:25:48+00:00 objective_draft_review {"objective": "O008", "ref": "d76fd2592eaf1e34be1776531f167910991a9bfb", "tasks": ["T0359", "T0360"]}
- 2026-11-15T23:26:29+00:00 run_started {"run": "T0359-critic-20261115T152629-08ec", "task": "T0359", "role": "critic", "session": "49daf6e5-94b7-4c94-a3a3-8e0939329547"}
- 2026-11-15T23:26:31+00:00 run_started {"run": "T0360-critic-20261115T152631-b179", "task": "T0360", "role": "critic", "session": "f2cacb45-e086-4143-b032-3e6e89a55e22"}
- 2026-11-15T23:35:13+00:00 run_finished {"run": "T0359-critic-20261115T152629-08ec", "status": "completed", "cost": 1.688795, "subtype": "success", "report": "structured_output"}
- 2026-11-15T23:37:46+00:00 run_finished {"run": "T0360-critic-20261115T152631-b179", "status": "completed", "cost": 2.255259, "subtype": "success", "report": "structured_output"}
- 2026-11-15T23:45:47+00:00 objective_draft_review {"objective": "O004", "ref": "e8d8166e5b74b81e6dc4244ca4e00e6004bc1be1", "tasks": ["T0361", "T0362"]}
- 2026-11-15T23:46:00+00:00 run_started {"run": "T0361-critic-20261115T154600-b36b", "task": "T0361", "role": "critic", "session": "5520eee3-70f0-4023-9e2d-5086209827d3"}
- 2026-11-15T23:46:02+00:00 run_started {"run": "T0362-critic-20261115T154602-37db", "task": "T0362", "role": "critic", "session": "ab758341-35f4-47eb-846f-33a4f7f99e3a"}
- 2026-11-15T23:50:58+00:00 run_finished {"run": "T0361-critic-20261115T154600-b36b", "status": "completed", "cost": 1.181625, "subtype": "success", "report": "structured_output"}
- 2026-11-15T23:54:44+00:00 run_finished {"run": "T0362-critic-20261115T154602-37db", "status": "completed", "cost": 2.053218, "subtype": "success", "report": "structured_output"}
- 2026-11-15T23:57:13+00:00 objective_draft_review {"objective": "O004", "ref": "75df0debba88c60a3f9b32bb97070b3f46f139b9", "tasks": ["T0363", "T0364"]}
- 2026-11-15T23:57:21+00:00 run_started {"run": "T0363-critic-20261115T155721-57be", "task": "T0363", "role": "critic", "session": "a73af082-1b68-4e03-8169-4e2bb99f7f2c"}
- 2026-11-15T23:57:23+00:00 run_started {"run": "T0364-critic-20261115T155723-85d0", "task": "T0364", "role": "critic", "session": "335cca40-9b39-4fed-818f-e097bce27258"}
- 2026-11-16T00:03:34+00:00 run_finished {"run": "T0364-critic-20261115T155723-85d0", "status": "completed", "cost": 1.571962, "subtype": "success", "report": "structured_output"}
