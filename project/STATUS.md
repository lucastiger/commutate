# ModuleForge status
_generated 2026-11-17T08:55:10+00:00 from repository state — do not edit_

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
| O004 | active | - | 0/1 | $83.29/$100 | The L2 inductance reference agrees with an independent field solver on the inductance ratios of re-layouts of PowerSynth public sample designs |
| O005 | draft | - | 0/2 | $7.65/$60 | L1 picks near-best layouts within a fixed family and die count, the regime derivative re-layout searches |
| O006 | active | INCONCLUSIVE | 1/1 | $137.91/$140 | The thermal L2 reference matches converged analytic solutions and an independent FEM, and design pilots measure what O002-O004 must fix |
| O007 | passed | PASS | 1/1 | $92.55/$110 | The scikit-fem thermal reference matches converged analytic solutions and the in-house finite-volume L2 on generator layouts |
| O008 | active | - | 0/2 | $72.52/$140 | A search seeded at a degraded copy of a near-optimal layout recovers it, where inductance-blind heuristics do not, on every designer-derived development layout |
| O901 | passed | PASS | 1/2 | $9.19/$30 | Infrastructure canary v2 - a known answer through registered, sealed, recomputed and null-checked evidence |

## Usage (from run records)
| objective | runs | usd | output tokens | thinking | denials | limit hits |
|---|---|---|---|---|---|---|
| O002 | 28 | $65.61 | 1320501 | 693417 | 94 | 0 |
| O003 | 135 | $258.22 | 4105839 | 2002393 | 280 | 0 |
| O004 | 44 | $83.29 | 1443571 | 855381 | 109 | 0 |
| O005 | 4 | $7.65 | 185443 | 108670 | 29 | 0 |
| O006 | 69 | $137.91 | 2633380 | 1435121 | 137 | 0 |
| O007 | 50 | $92.55 | 1684141 | 838123 | 79 | 1 |
| O008 | 37 | $72.52 | 1293492 | 728482 | 101 | 0 |
| O901 | 3 | $5.05 | 101607 | 52842 | 14 | 0 |

## Tasks
cancelled: 46, done: 378, failed: 4, review: 4, running: 3, todo: 11

- T0397 `review` scientist/design_experiment: E007 design: draft spec and runner (sealed seeds, per-stratum P_ref, level-1 judging with a level-2 subset, F2 nulls, F4/F6/F7 reports, code freeze, cost plan) (attempt 1)
- T0437 `review` builder/implement: E011 source prerequisites: control.py seed-stream tag, proxy_descent step_mm, proxy pins, nulls.py review fixes, slow marks (attempt 1)
- T0438 `review` builder/implement: perturb.py fixes before E004's hash freezes (reviews T0416, T0387) (attempt 1)
- T0442 `review` builder/implement: FastHenry adapter fixes from reviews T0427/T0428 (retries, Zc.mat checks, version banner, self-test bound, MEM_MARGIN) (attempt 1)
- T0444 `running` critic/review: Review T0437 (general) (attempt 1)
- T0445 `running` critic/review: Review T0442 (general) (attempt 1)
- T0446 `running` critic/review: Review T0438 (general) (attempt 1)

## Recent events
- 2026-11-17T06:30:54+00:00 task_added {"task": "T0442", "note": "founder approved 2026-11-17"}
- 2026-11-17T06:30:54+00:00 task_added {"task": "T0443", "note": "founder approved 2026-11-17"}
- 2026-11-17T07:02:15+00:00 task_failed_attempt {"task": "T0388", "signal": "gate_failed", "action": "repair"}
- 2026-11-17T07:02:31+00:00 run_started {"run": "T0442-builder-20261116T230231-3c2d", "task": "T0442", "role": "builder", "session": "20fc06e0-6198-4d9b-9dc3-977099eae492"}
- 2026-11-17T07:11:09+00:00 run_finished {"run": "T0437-builder-20261116T215657-38fd", "status": "completed", "cost": 0.897086, "subtype": "success", "report": "structured_output"}
- 2026-11-17T08:00:55+00:00 verified {"task": "T0437"}
- 2026-11-17T08:01:21+00:00 run_started {"run": "T0444-critic-20261117T000121-30a9", "task": "T0444", "role": "critic", "session": "3d285425-c613-4de4-9722-9b221d1727e5"}
- 2026-11-17T08:02:01+00:00 loop_stopped {"reason": "STOP file"}
- 2026-11-17T08:09:03+00:00 loop_started {"pid": 56165}
- 2026-11-17T08:09:04+00:00 run_finished {"run": "T0442-builder-20261116T230231-3c2d", "status": "completed", "cost": 0.455485, "subtype": "success", "report": "structured_output"}
- 2026-11-17T08:35:12+00:00 verified {"task": "T0442"}
- 2026-11-17T08:35:12+00:00 run_finished {"run": "T0438-builder-20261116T215742-1826", "status": "completed", "cost": 0.656029, "subtype": "success", "report": "structured_output"}
- 2026-11-17T08:54:55+00:00 verified {"task": "T0438"}
- 2026-11-17T08:55:08+00:00 run_started {"run": "T0445-critic-20261117T005508-575d", "task": "T0445", "role": "critic", "session": "32874ee8-e974-4e6c-8b4e-dbdd3c7a8f49"}
- 2026-11-17T08:55:10+00:00 run_started {"run": "T0446-critic-20261117T005510-b204", "task": "T0446", "role": "critic", "session": "d1dc9622-5aa8-4e4b-8c94-ed9a92479a2b"}
