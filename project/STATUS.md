# ModuleForge status
_generated 2026-11-16T20:36:16+00:00 from repository state — do not edit_

## Founder inbox (3 open)
- **I0205** [external_action] [O008] Burst VM for E011's development L2 draws (band bound, joint operating characteristic, dev rows)
- **I0209** [external_action] [O004] O004: two F7 burst-VM runs before E004 registration, and a budget warning
- **I0226** [protected_change] T0379: merge needs founder approval

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
| O008 | active | - | 0/2 | $48.68/$140 | A search seeded at a degraded copy of a near-optimal layout recovers it, where inductance-blind heuristics do not, on every designer-derived development layout |
| O901 | passed | PASS | 1/2 | $9.19/$30 | Infrastructure canary v2 - a known answer through registered, sealed, recomputed and null-checked evidence |

## Usage (from run records)
| objective | runs | usd | output tokens | thinking | denials | limit hits |
|---|---|---|---|---|---|---|
| O002 | 20 | $46.34 | 1006543 | 563185 | 58 | 0 |
| O003 | 135 | $258.22 | 4105839 | 2002393 | 280 | 0 |
| O004 | 30 | $56.70 | 1041891 | 667106 | 79 | 0 |
| O005 | 4 | $7.65 | 185443 | 108670 | 29 | 0 |
| O006 | 69 | $137.91 | 2633380 | 1435121 | 137 | 0 |
| O007 | 50 | $92.55 | 1684141 | 838123 | 79 | 1 |
| O008 | 30 | $48.68 | 1070771 | 633627 | 86 | 0 |
| O901 | 3 | $5.05 | 101607 | 52842 | 14 | 0 |

## Tasks
cancelled: 45, done: 356, failed: 4, needs_founder: 1, review: 3, running: 3, todo: 14

- T0379 `needs_founder` builder/implement: Designer proxy rule, randomised degradation family and ablation (e) (attempt 1)
- T0380 `review` builder/implement: Inductance-blind nulls (a), (b), (d) and the random-screen ablation (c) (attempt 1)
- T0385 `running` builder/implement: FastHenry run adapter: pinned binary and self-test, multipole with up to 10 retries, Zc.mat parse, closed-form validation (attempt 1)
- T0395 `review` builder/implement: L1 thermal model in src/moduleforge/thermal/ (n1's chosen design), tested against analytic limits, symmetry and power scaling, with a speed benchmark (attempt 2)
- T0396 `review` scientist/design_experiment: E007 statistics: F3 coverage and power simulation, bound selection and fixed allocation; protected mfos.metrics additions drafted as a patch (attempt 1)
- T0425 `running` critic/review: Review T0380 (physics) (attempt 1)
- T0426 `running` critic/review: Review T0380 (numerics) (attempt 1)

## Recent events
- 2026-11-16T19:20:53+00:00 inbox_resolved {"id": "I0225", "status": "approved", "note": "T0384 merge approved (reviews T0417, T0418 accept with caveats; thin-stack FastHenry gap and nh=1 bias carried in
- 2026-11-16T19:22:59+00:00 merged {"task": "T0386"}
- 2026-11-16T19:23:09+00:00 run_started {"run": "T0421-critic-20261116T112309-016e", "task": "T0421", "role": "critic", "session": "5cec27db-0527-4762-bd42-3d1bb47315a9"}
- 2026-11-16T19:23:10+00:00 run_started {"run": "T0422-critic-20261116T112310-8ed1", "task": "T0422", "role": "critic", "session": "3479c732-1be2-412e-b26a-dca6eef8c22a"}
- 2026-11-16T19:23:45+00:00 sleep_detected {"gap_s": 1888, "runs_extended": 3}
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
