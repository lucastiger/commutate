# ModuleForge status
_generated 2026-11-17T09:38:14+00:00 from repository state — do not edit_

## Founder inbox (5 open)
- **I0205** [external_action] [O008] Burst VM for E011's development L2 draws (band bound, joint operating characteristic, dev rows)
- **I0209** [external_action] [O004] O004: two F7 burst-VM runs before E004 registration, and a budget warning
- **I0235** [protected_change] T0437: merge needs founder approval
- **I0236** [protected_change] T0442: merge needs founder approval
- **I0237** [protected_change] T0438: merge needs founder approval

## Objectives
| id | status | verdict | evals | spent | title |
|---|---|---|---|---|---|
| O000 | passed | PASS | 1/2 | $0.50/$20 | Framework canary — the loop carries a known-answer hypothesis from plan to verdict |
| O001 | passed | PASS | 1/3 | $287.86/$315 | L1 PEEC ranks half-bridge layouts faithfully enough to drive layout search |
| O002 | active | - | 0/1 | $65.61/$120 | A fast L1 thermal model predicts each die's average junction temperature, the spread across paralleled dies and layout-to-layout differences well enough to drive search |
| O003 | needs_founder | - | 0/1 | $258.22/$265 | Reference wire-bonded half-bridge layouts leave >= 20 % loop-inductance headroom inside their own housing at <= +2 K Tj |
| O004 | active | - | 0/1 | $87.48/$100 | The L2 inductance reference agrees with an independent field solver on the inductance ratios of re-layouts of PowerSynth public sample designs |
| O005 | draft | - | 0/2 | $7.65/$60 | L1 picks near-best layouts within a fixed family and die count, the regime derivative re-layout searches |
| O006 | active | INCONCLUSIVE | 1/1 | $137.91/$140 | The thermal L2 reference matches converged analytic solutions and an independent FEM, and design pilots measure what O002-O004 must fix |
| O007 | passed | PASS | 1/1 | $92.55/$110 | The scikit-fem thermal reference matches converged analytic solutions and the in-house finite-volume L2 on generator layouts |
| O008 | active | - | 0/2 | $74.78/$140 | A search seeded at a degraded copy of a near-optimal layout recovers it, where inductance-blind heuristics do not, on every designer-derived development layout |
| O901 | passed | PASS | 1/2 | $9.19/$30 | Infrastructure canary v2 - a known answer through registered, sealed, recomputed and null-checked evidence |

## Usage (from run records)
| objective | runs | usd | output tokens | thinking | denials | limit hits |
|---|---|---|---|---|---|---|
| O002 | 30 | $65.61 | 1320501 | 693417 | 94 | 0 |
| O003 | 135 | $258.22 | 4105839 | 2002393 | 280 | 0 |
| O004 | 45 | $87.48 | 1481524 | 875902 | 115 | 0 |
| O005 | 4 | $7.65 | 185443 | 108670 | 29 | 0 |
| O006 | 69 | $137.91 | 2633380 | 1435121 | 137 | 0 |
| O007 | 50 | $92.55 | 1684141 | 838123 | 79 | 1 |
| O008 | 37 | $74.78 | 1325704 | 744500 | 107 | 0 |
| O901 | 3 | $5.05 | 101607 | 52842 | 14 | 0 |

## Tasks
cancelled: 46, done: 381, failed: 4, needs_founder: 3, review: 1, running: 3, todo: 8

- T0388 `running` scientist/design_experiment: E004 design, part 1: draft spec and registration stage (frozen references, sealed-seed pairs, F2/F4 checks on L1) (attempt 2)
- T0397 `review` scientist/design_experiment: E007 design: draft spec and runner (sealed seeds, per-stratum P_ref, level-1 judging with a level-2 subset, F2 nulls, F4/F6/F7 reports, code freeze, cost plan) (attempt 1)
- T0419 `running` scientist/implement: F1 development check: gate the level-1 verdict on the sanity block and per-record provenance (review T0411 findings 1-2) (attempt 2)
- T0436 `running` critic/review: Review T0397 (numerics) (attempt 1)
- T0437 `needs_founder` builder/implement: E011 source prerequisites: control.py seed-stream tag, proxy_descent step_mm, proxy pins, nulls.py review fixes, slow marks (attempt 1)
- T0438 `needs_founder` builder/implement: perturb.py fixes before E004's hash freezes (reviews T0416, T0387) (attempt 1)
- T0442 `needs_founder` builder/implement: FastHenry adapter fixes from reviews T0427/T0428 (retries, Zc.mat checks, version banner, self-test bound, MEM_MARGIN) (attempt 1)

## Recent events
- 2026-11-17T08:09:04+00:00 run_finished {"run": "T0442-builder-20261116T230231-3c2d", "status": "completed", "cost": 0.455485, "subtype": "success", "report": "structured_output"}
- 2026-11-17T08:35:12+00:00 verified {"task": "T0442"}
- 2026-11-17T08:35:12+00:00 run_finished {"run": "T0438-builder-20261116T215742-1826", "status": "completed", "cost": 0.656029, "subtype": "success", "report": "structured_output"}
- 2026-11-17T08:54:55+00:00 verified {"task": "T0438"}
- 2026-11-17T08:55:08+00:00 run_started {"run": "T0445-critic-20261117T005508-575d", "task": "T0445", "role": "critic", "session": "32874ee8-e974-4e6c-8b4e-dbdd3c7a8f49"}
- 2026-11-17T08:55:10+00:00 run_started {"run": "T0446-critic-20261117T005510-b204", "task": "T0446", "role": "critic", "session": "d1dc9622-5aa8-4e4b-8c94-ed9a92479a2b"}
- 2026-11-17T08:55:46+00:00 run_finished {"run": "T0444-critic-20261117T000121-30a9", "status": "completed", "cost": 2.259334, "subtype": "success", "report": "structured_output"}
- 2026-11-17T09:04:48+00:00 inbox_opened {"id": "I0235", "kind": "protected_change", "subject": "T0437: merge needs founder approval"}
- 2026-11-17T09:05:00+00:00 run_started {"run": "T0388-scientist-20261117T010500-2448", "task": "T0388", "role": "scientist", "session": "a372e806-bf4d-4036-9908-f2bdcfb53e58"}
- 2026-11-17T09:12:47+00:00 run_finished {"run": "T0445-critic-20261117T005508-575d", "status": "completed", "cost": 1.764524, "subtype": "success", "report": "structured_output"}
- 2026-11-17T09:25:37+00:00 inbox_opened {"id": "I0236", "kind": "protected_change", "subject": "T0442: merge needs founder approval"}
- 2026-11-17T09:25:47+00:00 run_started {"run": "T0436-critic-20261117T012547-cb50", "task": "T0436", "role": "critic", "session": "eca5dcd8-50ca-4a88-9bca-c195cdce6cce"}
- 2026-11-17T09:26:24+00:00 run_finished {"run": "T0446-critic-20261117T005510-b204", "status": "completed", "cost": 2.425159, "subtype": "success", "report": "structured_output"}
- 2026-11-17T09:38:08+00:00 inbox_opened {"id": "I0237", "kind": "protected_change", "subject": "T0438: merge needs founder approval"}
- 2026-11-17T09:38:14+00:00 run_started {"run": "T0419-scientist-20261117T013814-97d5", "task": "T0419", "role": "scientist", "session": "d44d0181-6b67-44ef-9f58-95cbdaeae8dc"}
