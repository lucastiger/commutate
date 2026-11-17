# ModuleForge status
_generated 2026-11-17T15:00:13+00:00 from repository state — do not edit_

## Founder inbox (9 open)
- **I0205** [external_action] [O008] Burst VM for E011's development L2 draws (band bound, joint operating characteristic, dev rows)
- **I0209** [external_action] [O004] O004: two F7 burst-VM runs before E004 registration, and a budget warning
- **I0235** [protected_change] T0437: merge needs founder approval
- **I0236** [protected_change] T0442: merge needs founder approval
- **I0237** [protected_change] T0438: merge needs founder approval
- **I0238** [protected_change] T0388: merge needs founder approval
- **I0239** [protected_change] T0419: merge needs founder approval
- **I0240** [protected_change] T0397: merge needs founder approval
- **I0241** [protected_change] T0443: merge needs founder approval

## Objectives
| id | status | verdict | evals | spent | title |
|---|---|---|---|---|---|
| O000 | passed | PASS | 1/2 | $0.50/$20 | Framework canary — the loop carries a known-answer hypothesis from plan to verdict |
| O001 | passed | PASS | 1/3 | $287.86/$315 | L1 PEEC ranks half-bridge layouts faithfully enough to drive layout search |
| O002 | active | - | 0/1 | $80.05/$120 | A fast L1 thermal model predicts each die's average junction temperature, the spread across paralleled dies and layout-to-layout differences well enough to drive search |
| O003 | needs_founder | - | 0/1 | $258.22/$265 | Reference wire-bonded half-bridge layouts leave >= 20 % loop-inductance headroom inside their own housing at <= +2 K Tj |
| O004 | active | - | 0/1 | $95.01/$100 | The L2 inductance reference agrees with an independent field solver on the inductance ratios of re-layouts of PowerSynth public sample designs |
| O005 | draft | - | 0/2 | $7.65/$60 | L1 picks near-best layouts within a fixed family and die count, the regime derivative re-layout searches |
| O006 | active | INCONCLUSIVE | 1/1 | $137.91/$140 | The thermal L2 reference matches converged analytic solutions and an independent FEM, and design pilots measure what O002-O004 must fix |
| O007 | passed | PASS | 1/1 | $92.55/$110 | The scikit-fem thermal reference matches converged analytic solutions and the in-house finite-volume L2 on generator layouts |
| O008 | active | - | 0/2 | $74.78/$140 | A search seeded at a degraded copy of a near-optimal layout recovers it, where inductance-blind heuristics do not, on every designer-derived development layout |
| O901 | passed | PASS | 1/2 | $9.19/$30 | Infrastructure canary v2 - a known answer through registered, sealed, recomputed and null-checked evidence |

## Usage (from run records)
| objective | runs | usd | output tokens | thinking | denials | limit hits |
|---|---|---|---|---|---|---|
| O002 | 34 | $80.05 | 1517932 | 785394 | 109 | 0 |
| O003 | 135 | $258.22 | 4105839 | 2002393 | 280 | 0 |
| O004 | 47 | $95.01 | 1602035 | 925454 | 135 | 0 |
| O005 | 4 | $7.65 | 185443 | 108670 | 29 | 0 |
| O006 | 69 | $137.91 | 2633380 | 1435121 | 137 | 0 |
| O007 | 50 | $92.55 | 1684141 | 838123 | 79 | 1 |
| O008 | 37 | $74.78 | 1325704 | 744500 | 107 | 0 |
| O901 | 3 | $5.05 | 101607 | 52842 | 14 | 0 |

## Tasks
cancelled: 46, done: 386, failed: 4, needs_founder: 7, todo: 8

- T0388 `needs_founder` scientist/design_experiment: E004 design, part 1: draft spec and registration stage (frozen references, sealed-seed pairs, F2/F4 checks on L1) (attempt 2)
- T0397 `needs_founder` scientist/design_experiment: E007 design: draft spec and runner (sealed seeds, per-stratum P_ref, level-1 judging with a level-2 subset, F2 nulls, F4/F6/F7 reports, code freeze, cost plan) (attempt 2)
- T0419 `needs_founder` scientist/implement: F1 development check: gate the level-1 verdict on the sanity block and per-record provenance (review T0411 findings 1-2) (attempt 2)
- T0437 `needs_founder` builder/implement: E011 source prerequisites: control.py seed-stream tag, proxy_descent step_mm, proxy pins, nulls.py review fixes, slow marks (attempt 1)
- T0438 `needs_founder` builder/implement: perturb.py fixes before E004's hash freezes (reviews T0416, T0387) (attempt 1)
- T0442 `needs_founder` builder/implement: FastHenry adapter fixes from reviews T0427/T0428 (retries, Zc.mat checks, version banner, self-test bound, MEM_MARGIN) (attempt 1)
- T0443 `needs_founder` builder/implement: Thermal L1 tests and doc fixes from reviews T0423/T0424 before E007's code freeze (attempt 1)

## Recent events
- 2026-11-17T10:40:59+00:00 run_started {"run": "T0443-builder-20261117T024059-8aa3", "task": "T0443", "role": "builder", "session": "9a453a00-6dd4-46d7-b32a-186be07f286f"}
- 2026-11-17T10:41:35+00:00 run_finished {"run": "T0397-scientist-20261117T015632-62c7", "status": "completed", "cost": 5.986665, "subtype": "success", "report": "structured_output"}
- 2026-11-17T10:54:18+00:00 verified {"task": "T0397"}
- 2026-11-17T10:54:19+00:00 run_finished {"run": "T0419-scientist-20261117T013814-97d5", "status": "completed", "cost": 0.838183, "subtype": "success", "report": "structured_output"}
- 2026-11-17T11:05:45+00:00 verified {"task": "T0419"}
- 2026-11-17T11:17:09+00:00 inbox_opened {"id": "I0239", "kind": "protected_change", "subject": "T0419: merge needs founder approval"}
- 2026-11-17T11:17:18+00:00 run_started {"run": "T0449-critic-20261117T031718-ec78", "task": "T0449", "role": "critic", "session": "b010e926-2265-4bda-8893-6fad7a517fce"}
- 2026-11-17T11:17:20+00:00 run_started {"run": "T0450-critic-20261117T031720-d7f2", "task": "T0450", "role": "critic", "session": "007d0c10-1641-47d3-8aaa-4fdd4c4e9f1e"}
- 2026-11-17T11:21:48+00:00 run_finished {"run": "T0449-critic-20261117T031718-ec78", "status": "completed", "cost": 2.086015, "subtype": "success", "report": "structured_output"}
- 2026-11-17T11:24:03+00:00 run_finished {"run": "T0450-critic-20261117T031720-d7f2", "status": "completed", "cost": 2.449089, "subtype": "success", "report": "structured_output"}
- 2026-11-17T12:06:37+00:00 inbox_opened {"id": "I0240", "kind": "protected_change", "subject": "T0397: merge needs founder approval"}
- 2026-11-17T12:11:40+00:00 run_finished {"run": "T0443-builder-20261117T024059-8aa3", "status": "completed", "cost": 0.419673, "subtype": "success", "report": "structured_output"}
- 2026-11-17T12:29:31+00:00 verified {"task": "T0443"}
- 2026-11-17T12:29:36+00:00 inbox_opened {"id": "I0241", "kind": "protected_change", "subject": "T0443: merge needs founder approval"}
- 2026-11-17T15:00:03+00:00 task_added {"task": "T0451", "note": "founder approved 2026-11-17"}
