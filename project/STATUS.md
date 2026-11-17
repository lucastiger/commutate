# ModuleForge status
_generated 2026-11-17T15:07:28+00:00 from repository state — do not edit_

## Founder inbox (2 open)
- **I0205** [external_action] [O008] Burst VM for E011's development L2 draws (band bound, joint operating characteristic, dev rows)
- **I0209** [external_action] [O004] O004: two F7 burst-VM runs before E004 registration, and a budget warning

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
| O008 | 38 | $74.78 | 1325704 | 744500 | 107 | 0 |
| O901 | 3 | $5.05 | 101607 | 52842 | 14 | 0 |

## Tasks
cancelled: 46, done: 388, failed: 4, merge: 5, running: 1, todo: 7

- T0382 `running` scientist/design_experiment: Design E011: draft spec and runner (selftest, smoke, development mode with the burst job manifest) (attempt 3)
- T0388 `merge` scientist/design_experiment: E004 design, part 1: draft spec and registration stage (frozen references, sealed-seed pairs, F2/F4 checks on L1) (attempt 2)
- T0397 `merge` scientist/design_experiment: E007 design: draft spec and runner (sealed seeds, per-stratum P_ref, level-1 judging with a level-2 subset, F2 nulls, F4/F6/F7 reports, code freeze, cost plan) (attempt 2)
- T0419 `merge` scientist/implement: F1 development check: gate the level-1 verdict on the sanity block and per-record provenance (review T0411 findings 1-2) (attempt 2)
- T0438 `merge` builder/implement: perturb.py fixes before E004's hash freezes (reviews T0416, T0387) (attempt 1)
- T0443 `merge` builder/implement: Thermal L1 tests and doc fixes from reviews T0423/T0424 before E007's code freeze (attempt 1)

## Recent events
- 2026-11-17T12:06:37+00:00 inbox_opened {"id": "I0240", "kind": "protected_change", "subject": "T0397: merge needs founder approval"}
- 2026-11-17T12:11:40+00:00 run_finished {"run": "T0443-builder-20261117T024059-8aa3", "status": "completed", "cost": 0.419673, "subtype": "success", "report": "structured_output"}
- 2026-11-17T12:29:31+00:00 verified {"task": "T0443"}
- 2026-11-17T12:29:36+00:00 inbox_opened {"id": "I0241", "kind": "protected_change", "subject": "T0443: merge needs founder approval"}
- 2026-11-17T15:00:03+00:00 task_added {"task": "T0451", "note": "founder approved 2026-11-17"}
- 2026-11-17T15:01:26+00:00 inbox_resolved {"id": "I0235", "status": "approved", "note": "T0437 merge approved (review T0444 accept with caveats). Seed streams domain-tagged; proxy_descent step_mm; in-do
- 2026-11-17T15:01:34+00:00 inbox_resolved {"id": "I0236", "status": "approved", "note": "T0442 merge approved (review T0445 accept with caveats). No retry on external SIGKILL or repeated exits; 1x1 Zc.m
- 2026-11-17T15:01:37+00:00 merged {"task": "T0437"}
- 2026-11-17T15:04:07+00:00 inbox_resolved {"id": "I0237", "status": "approved", "note": "T0438 merge approved (review T0446 accept with caveats). perturb.py hash coverage, canonical long sides, whole-mm
- 2026-11-17T15:04:10+00:00 inbox_resolved {"id": "I0238", "status": "approved", "note": "T0388 merge approved (reviews T0440, T0441, T0447, T0448 accept with caveats). E004 part 1, partial: perturb fixe
- 2026-11-17T15:04:11+00:00 inbox_resolved {"id": "I0239", "status": "approved", "note": "T0419 merge approved (low risk; reassigned builder -> scientist for scope). F1 dev check gates level 1 on sanity 
- 2026-11-17T15:04:13+00:00 inbox_resolved {"id": "I0240", "status": "approved", "note": "T0397 merge approved (attempt 2 fixes T0436's blocker: the nulls apply to A1 and A4 only; reviews T0435, T0449, T
- 2026-11-17T15:04:15+00:00 inbox_resolved {"id": "I0241", "status": "approved", "note": "T0443 merge approved (low risk). k(T) Kirchhoff unit test, GRID_RULE/CALIBRATION pin test, docs/thermal_l1.md cor
- 2026-11-17T15:07:22+00:00 merged {"task": "T0442"}
- 2026-11-17T15:07:28+00:00 run_started {"run": "T0382-scientist-20261117T070728-ed30", "task": "T0382", "role": "scientist", "session": "6e83c6eb-e247-4434-bdc6-03b7a5e0fd19"}
