# ModuleForge status
_generated 2026-11-16T20:04:46+00:00 from repository state — do not edit_

## Founder inbox (2 open)
- **I0205** [external_action] [O008] Burst VM for E011's development L2 draws (band bound, joint operating characteristic, dev rows)
- **I0209** [external_action] [O004] O004: two F7 burst-VM runs before E004 registration, and a budget warning

## Objectives
| id | status | verdict | evals | spent | title |
|---|---|---|---|---|---|
| O000 | passed | PASS | 1/2 | $0.50/$20 | Framework canary — the loop carries a known-answer hypothesis from plan to verdict |
| O001 | passed | PASS | 1/3 | $287.86/$315 | L1 PEEC ranks half-bridge layouts faithfully enough to drive layout search |
| O002 | active | - | 0/1 | $46.34/$120 | A fast L1 thermal model predicts each die's average junction temperature, the spread across paralleled dies and layout-to-layout differences well enough to drive search |
| O003 | needs_founder | - | 0/1 | $258.22/$265 | Reference wire-bonded half-bridge layouts leave >= 20 % loop-inductance headroom inside their own housing at <= +2 K Tj |
| O004 | active | - | 0/1 | $56.70/$100 | The L2 inductance reference agrees with an independent field solver on the inductance ratios of re-layouts of PowerSynth public sample designs |
| O005 | draft | - | 0/2 | $7.65/$60 | L1 picks near-best layouts within a fixed family and die count, the regime derivative re-layout searches |
| O006 | active | INCONCLUSIVE | 1/1 | $137.91/$140 | The thermal L2 reference matches converged analytic solutions and an independent FEM, and design pilots measure what O002-O004 must fix |
| O007 | passed | PASS | 1/1 | $92.55/$110 | The scikit-fem thermal reference matches converged analytic solutions and the in-house finite-volume L2 on generator layouts |
| O008 | active | - | 0/2 | $44.73/$140 | A search seeded at a degraded copy of a near-optimal layout recovers it, where inductance-blind heuristics do not, on every designer-derived development layout |
| O901 | passed | PASS | 1/2 | $9.19/$30 | Infrastructure canary v2 - a known answer through registered, sealed, recomputed and null-checked evidence |

## Usage (from run records)
| objective | runs | usd | output tokens | thinking | denials | limit hits |
|---|---|---|---|---|---|---|
| O002 | 20 | $46.34 | 1006543 | 563185 | 58 | 0 |
| O003 | 135 | $258.22 | 4105839 | 2002393 | 280 | 0 |
| O004 | 29 | $56.70 | 1041891 | 667106 | 79 | 0 |
| O005 | 4 | $7.65 | 185443 | 108670 | 29 | 0 |
| O006 | 69 | $137.91 | 2633380 | 1435121 | 137 | 0 |
| O007 | 50 | $92.55 | 1684141 | 838123 | 79 | 1 |
| O008 | 29 | $44.74 | 1005053 | 596927 | 76 | 0 |
| O901 | 3 | $5.05 | 101607 | 52842 | 14 | 0 |

## Tasks
cancelled: 45, done: 354, failed: 4, review: 4, running: 3, todo: 16

- T0379 `review` builder/implement: Designer proxy rule, randomised degradation family and ablation (e) (attempt 1)
- T0380 `review` builder/implement: Inductance-blind nulls (a), (b), (d) and the random-screen ablation (c) (attempt 1)
- T0395 `review` builder/implement: L1 thermal model in src/moduleforge/thermal/ (n1's chosen design), tested against analytic limits, symmetry and power scaling, with a speed benchmark (attempt 2)
- T0396 `review` scientist/design_experiment: E007 statistics: F3 coverage and power simulation, bound selection and fixed allocation; protected mfos.metrics additions drafted as a patch (attempt 1)
- T0421 `running` critic/review: Review T0379 (physics) (attempt 1)
- T0422 `running` critic/review: Review T0379 (numerics) (attempt 1)
- T0425 `running` critic/review: Review T0380 (physics) (attempt 1)

## Recent events
- 2026-11-16T18:51:43+00:00 run_started {"run": "T0380-builder-20261116T105143-b482", "task": "T0380", "role": "builder", "session": "f54cd5ba-1e7d-4928-9532-d1639391ef3b"}
- 2026-11-16T18:52:18+00:00 sleep_detected {"gap_s": 2049, "runs_extended": 3}
- 2026-11-16T18:52:19+00:00 run_finished {"run": "T0379-builder-20261116T093744-60f2", "status": "completed", "cost": 1.136298, "subtype": "success", "report": "structured_output"}
- 2026-11-16T19:01:16+00:00 verified {"task": "T0379"}
- 2026-11-16T19:01:16+00:00 run_finished {"run": "T0395-builder-20261116T091713-10cb", "status": "completed", "cost": 4.592129, "subtype": "success", "report": "structured_output"}
- 2026-11-16T19:15:18+00:00 verified {"task": "T0395"}
- 2026-11-16T19:20:53+00:00 inbox_resolved {"id": "I0225", "status": "approved", "note": "T0384 merge approved (reviews T0417, T0418 accept with caveats; thin-stack FastHenry gap and nh=1 bias carried in
- 2026-11-16T19:22:59+00:00 merged {"task": "T0386"}
- 2026-11-16T19:23:09+00:00 run_started {"run": "T0421-critic-20261116T112309-016e", "task": "T0421", "role": "critic", "session": "5cec27db-0527-4762-bd42-3d1bb47315a9"}
- 2026-11-16T19:23:10+00:00 run_started {"run": "T0422-critic-20261116T112310-8ed1", "task": "T0422", "role": "critic", "session": "3479c732-1be2-412e-b26a-dca6eef8c22a"}
- 2026-11-16T19:23:45+00:00 sleep_detected {"gap_s": 1888, "runs_extended": 3}
- 2026-11-16T19:23:46+00:00 run_finished {"run": "T0380-builder-20261116T105143-b482", "status": "completed", "cost": 0.448279, "subtype": "success", "report": "structured_output"}
- 2026-11-16T19:35:26+00:00 verified {"task": "T0380"}
- 2026-11-16T20:04:37+00:00 merged {"task": "T0384"}
- 2026-11-16T20:04:46+00:00 run_started {"run": "T0425-critic-20261116T120446-03f8", "task": "T0425", "role": "critic", "session": "c0382d0b-a244-41de-b86c-837f656d025d"}
