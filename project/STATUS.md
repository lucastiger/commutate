# ModuleForge status
_generated 2026-11-14T21:28:37+00:00 from repository state — do not edit_

## Founder inbox (0 open)
- nothing needs you

## Objectives
| id | status | verdict | evals | spent | title |
|---|---|---|---|---|---|
| O000 | passed | PASS | 1/2 | $0.50/$20 | Framework canary — the loop carries a known-answer hypothesis from plan to verdict |
| O001 | passed | PASS | 1/3 | $287.86/$315 | L1 PEEC ranks half-bridge layouts faithfully enough to drive layout search |
| O002 | draft | - | 0/1 | $11.44/$120 | A fast L1 thermal model predicts per-die Tj max, spread and layout-to-layout differences well enough to drive search |
| O003 | active | - | 0/1 | $236.29/$265 | Reference wire-bonded half-bridge layouts leave >= 20 % loop-inductance headroom inside their own housing at <= +2 K Tj |
| O004 | draft | - | 0/1 | $9.51/$100 | The L2 inductance reference is accurate on reconstructed public modules, so it can judge O003's headroom |
| O005 | draft | - | 0/2 | $7.65/$60 | L1 picks near-best layouts within a fixed family and die count, the regime derivative re-layout searches |
| O006 | active | INCONCLUSIVE | 1/1 | $137.91/$140 | The thermal L2 reference matches converged analytic solutions and an independent FEM, and design pilots measure what O002-O004 must fix |
| O007 | passed | PASS | 1/1 | $92.55/$110 | The scikit-fem thermal reference matches converged analytic solutions and the in-house finite-volume L2 on generator layouts |
| O901 | passed | PASS | 1/2 | $9.19/$30 | Infrastructure canary v2 - a known answer through registered, sealed, recomputed and null-checked evidence |

## Usage (from run records)
| objective | runs | usd | output tokens | thinking | denials | limit hits |
|---|---|---|---|---|---|---|
| O002 | 6 | $11.44 | 293351 | 180601 | 28 | 0 |
| O003 | 123 | $236.29 | 3788295 | 1862471 | 246 | 0 |
| O004 | 6 | $9.51 | 225161 | 160260 | 17 | 0 |
| O005 | 4 | $7.65 | 185443 | 108670 | 29 | 0 |
| O006 | 69 | $137.91 | 2633380 | 1435121 | 137 | 0 |
| O007 | 50 | $92.55 | 1684141 | 838123 | 79 | 1 |
| O901 | 3 | $5.05 | 101607 | 52842 | 14 | 0 |

## Tasks
cancelled: 41, done: 294, failed: 3, review: 1, running: 1, todo: 1

- T0338 `review` builder/implement: Generator: let the sampler place a slot stack across split free windows (2D_Case_2R's own topology is outside its support; D0021) (attempt 3)
- T0341 `running` critic/review: Review T0338 (general) (attempt 1)

## Recent events
- 2026-11-14T19:20:08+00:00 run_finished {"run": "T0338-builder-20261114T104144-f272", "status": "completed", "cost": 0.88713, "subtype": "success", "report": "structured_output"}
- 2026-11-14T19:20:08+00:00 task_failed_attempt {"task": "T0338", "signal": "scope_violation", "action": "repair"}
- 2026-11-14T19:20:13+00:00 run_started {"run": "T0338-builder-20261114T112013-351b", "task": "T0338", "role": "builder", "session": "c455b389-d4a3-49c0-97d0-db1f5a272932"}
- 2026-11-14T20:03:51+00:00 run_finished {"run": "T0338-builder-20261114T112013-351b", "status": "completed", "cost": 0.702341, "subtype": "success", "report": "structured_output"}
- 2026-11-14T20:03:51+00:00 task_failed_attempt {"task": "T0338", "signal": "scope_violation", "action": "diagnose"}
- 2026-11-14T20:03:51+00:00 investigation_spawned {"task": "T0340", "about": "T0338", "cls": "implementation"}
- 2026-11-14T20:03:58+00:00 run_started {"run": "T0340-scientist-20261114T120358-51be", "task": "T0340", "role": "scientist", "session": "d03be11c-47da-491d-ae2e-ddd44971e4a6"}
- 2026-11-14T20:05:15+00:00 run_interrupted {"run": "T0340-scientist-20261114T120358-51be", "cost": 0.35342}
- 2026-11-14T20:05:16+00:00 founder_stopped {"task": "T0340", "run": "T0340-scientist-20261114T120358-51be", "run_status": "interrupted", "task_status": "cancelled"}
- 2026-11-14T20:05:54+00:00 task_rescoped {"task": "T0338", "reason": "research deliverables moved to T0339 (builder write scope)"}
- 2026-11-14T20:14:59+00:00 run_started {"run": "T0338-builder-20261114T121459-a4c3", "task": "T0338", "role": "builder", "session": "281ba830-b511-4740-97fc-73a190722273"}
- 2026-11-14T20:56:05+00:00 run_finished {"run": "T0338-builder-20261114T121459-a4c3", "status": "completed", "cost": 0.86309, "subtype": "success", "report": "structured_output"}
- 2026-11-14T21:13:21+00:00 verified {"task": "T0338"}
- 2026-11-14T21:13:28+00:00 run_started {"run": "T0341-critic-20261114T131328-04c8", "task": "T0341", "role": "critic", "session": "16f84f99-0cb0-452e-a396-19e5fb493fed"}
- 2026-11-14T21:14:02+00:00 sleep_detected {"gap_s": 1079, "runs_extended": 1}
