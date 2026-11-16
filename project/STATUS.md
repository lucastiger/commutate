# ModuleForge status
_generated 2026-11-16T21:29:22+00:00 from repository state — do not edit_

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
| O008 | active | - | 0/2 | $50.45/$140 | A search seeded at a degraded copy of a near-optimal layout recovers it, where inductance-blind heuristics do not, on every designer-derived development layout |
| O901 | passed | PASS | 1/2 | $9.19/$30 | Infrastructure canary v2 - a known answer through registered, sealed, recomputed and null-checked evidence |

## Usage (from run records)
| objective | runs | usd | output tokens | thinking | denials | limit hits |
|---|---|---|---|---|---|---|
| O002 | 20 | $46.34 | 1006543 | 563185 | 58 | 0 |
| O003 | 135 | $258.22 | 4105839 | 2002393 | 280 | 0 |
| O004 | 31 | $56.70 | 1041891 | 667106 | 79 | 0 |
| O005 | 4 | $7.65 | 185443 | 108670 | 29 | 0 |
| O006 | 69 | $137.91 | 2633380 | 1435121 | 137 | 0 |
| O007 | 50 | $92.55 | 1684141 | 838123 | 79 | 1 |
| O008 | 30 | $50.45 | 1103541 | 650648 | 90 | 0 |
| O901 | 3 | $5.05 | 101607 | 52842 | 14 | 0 |

## Tasks
cancelled: 45, done: 358, failed: 4, review: 3, running: 3, todo: 13

- T0380 `review` builder/implement: Inductance-blind nulls (a), (b), (d) and the random-screen ablation (c) (attempt 1)
- T0385 `running` builder/implement: FastHenry run adapter: pinned binary and self-test, multipole with up to 10 retries, Zc.mat parse, closed-form validation (attempt 1)
- T0387 `running` scientist/investigate: F7(b)-(d) l2_layout check on Case 4 development pairs: ladder, ratio estimates, F1 exclusion rate, VM job list (attempt 1)
- T0395 `review` builder/implement: L1 thermal model in src/moduleforge/thermal/ (n1's chosen design), tested against analytic limits, symmetry and power scaling, with a speed benchmark (attempt 2)
- T0396 `review` scientist/design_experiment: E007 statistics: F3 coverage and power simulation, bound selection and fixed allocation; protected mfos.metrics additions drafted as a patch (attempt 1)
- T0426 `running` critic/review: Review T0380 (numerics) (attempt 1)

## Recent events
- 2026-11-16T19:23:46+00:00 run_finished {"run": "T0380-builder-20261116T105143-b482", "status": "completed", "cost": 0.448279, "subtype": "success", "report": "structured_output"}
- 2026-11-16T19:35:26+00:00 verified {"task": "T0380"}
- 2026-11-16T20:04:37+00:00 merged {"task": "T0384"}
- 2026-11-16T20:04:46+00:00 run_started {"run": "T0425-critic-20261116T120446-03f8", "task": "T0425", "role": "critic", "session": "c0382d0b-a244-41de-b86c-837f656d025d"}
- 2026-11-16T20:05:21+00:00 sleep_detected {"gap_s": 2496, "runs_extended": 3}
- 2026-11-16T20:05:22+00:00 run_finished {"run": "T0422-critic-20261116T112310-8ed1", "status": "completed", "cost": 2.232622, "subtype": "success", "report": "structured_output"}
- 2026-11-16T20:05:22+00:00 run_finished {"run": "T0421-critic-20261116T112309-016e", "status": "completed", "cost": 1.713212, "subtype": "success", "report": "structured_output"}
- 2026-11-16T20:36:06+00:00 inbox_opened {"id": "I0226", "kind": "protected_change", "subject": "T0379: merge needs founder approval"}
- 2026-11-16T20:36:15+00:00 run_started {"run": "T0426-critic-20261116T123615-a06e", "task": "T0426", "role": "critic", "session": "64bd129e-ad9f-4bd3-b5df-7308292193b8"}
- 2026-11-16T20:36:16+00:00 run_started {"run": "T0385-builder-20261116T123616-1b28", "task": "T0385", "role": "builder", "session": "df0595ff-a821-4488-ada5-22683aa520b5"}
- 2026-11-16T20:36:51+00:00 sleep_detected {"gap_s": 1890, "runs_extended": 3}
- 2026-11-16T20:36:52+00:00 run_finished {"run": "T0425-critic-20261116T120446-03f8", "status": "completed", "cost": 1.769571, "subtype": "success", "report": "structured_output"}
- 2026-11-16T20:37:02+00:00 run_started {"run": "T0387-scientist-20261116T123702-806f", "task": "T0387", "role": "scientist", "session": "39796813-99fd-481c-969b-b4bd94d5344e"}
- 2026-11-16T20:37:05+00:00 inbox_resolved {"id": "I0226", "status": "approved", "note": "T0379 merge approved (reviews T0421, T0422 accept with caveats). Foot offsets excluded per O008 scope_in 'one par
- 2026-11-16T21:29:13+00:00 merged {"task": "T0379"}
