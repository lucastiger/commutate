# ModuleForge status
_generated 2026-11-18T03:46:10+00:00 from repository state — do not edit_

## Founder inbox (3 open)
- **I0205** [external_action] [O008] Burst VM for E011's development L2 draws (band bound, joint operating characteristic, dev rows)
- **I0209** [external_action] [O004] O004: two F7 burst-VM runs before E004 registration, and a budget warning
- **I0254** [experiment_registration] register E007 (pre-registration)

## Objectives
| id | status | verdict | evals | spent | title |
|---|---|---|---|---|---|
| O000 | passed | PASS | 1/2 | $0.50/$20 | Framework canary — the loop carries a known-answer hypothesis from plan to verdict |
| O001 | passed | PASS | 1/3 | $287.86/$315 | L1 PEEC ranks half-bridge layouts faithfully enough to drive layout search |
| O002 | active | - | 0/1 | $99.38/$120 | A fast L1 thermal model predicts each die's average junction temperature, the spread across paralleled dies and layout-to-layout differences well enough to drive search |
| O003 | needs_founder | - | 0/1 | $258.22/$265 | Reference wire-bonded half-bridge layouts leave >= 20 % loop-inductance headroom inside their own housing at <= +2 K Tj |
| O004 | active | - | 0/1 | $118.73/$148 | The L2 inductance reference agrees with an independent field solver on the inductance ratios of re-layouts of PowerSynth public sample designs |
| O005 | draft | - | 0/2 | $7.65/$60 | L1 picks near-best layouts within a fixed family and die count, the regime derivative re-layout searches |
| O006 | active | INCONCLUSIVE | 1/1 | $137.91/$140 | The thermal L2 reference matches converged analytic solutions and an independent FEM, and design pilots measure what O002-O004 must fix |
| O007 | passed | PASS | 1/1 | $92.55/$110 | The scikit-fem thermal reference matches converged analytic solutions and the in-house finite-volume L2 on generator layouts |
| O008 | active | - | 0/2 | $91.48/$140 | A search seeded at a degraded copy of a near-optimal layout recovers it, where inductance-blind heuristics do not, on every designer-derived development layout |
| O901 | passed | PASS | 1/2 | $9.19/$30 | Infrastructure canary v2 - a known answer through registered, sealed, recomputed and null-checked evidence |

## Usage (from run records)
| objective | runs | usd | output tokens | thinking | denials | limit hits |
|---|---|---|---|---|---|---|
| O002 | 41 | $99.38 | 1794921 | 884897 | 131 | 0 |
| O003 | 135 | $258.22 | 4105839 | 2002393 | 280 | 0 |
| O004 | 55 | $118.73 | 1881647 | 1038213 | 142 | 0 |
| O005 | 4 | $7.65 | 185443 | 108670 | 29 | 0 |
| O006 | 69 | $137.91 | 2633380 | 1435121 | 137 | 0 |
| O007 | 50 | $92.55 | 1684141 | 838123 | 79 | 1 |
| O008 | 43 | $91.48 | 1532378 | 830907 | 120 | 0 |
| O901 | 3 | $5.05 | 101607 | 52842 | 14 | 0 |

## Tasks
cancelled: 47, done: 409, failed: 4, running: 1, todo: 4

- T0457 `running` scientist/design_experiment: E004 design part 2b: banded acceptance and its simulation, redraw record, 2R proxy pair, provenance, solve-stage review fixes, local FastHenry probe (attempt 2)

## Recent events
- 2026-11-18T02:33:12+00:00 task_added {"task": "T0464", "note": "founder decision 2026-11-18"}
- 2026-11-18T02:36:32+00:00 run_finished {"run": "T0463-critic-20261117T182940-d3e0", "status": "completed", "cost": 1.828217, "subtype": "success", "report": "structured_output"}
- 2026-11-18T02:44:01+00:00 inbox_opened {"id": "I0252", "kind": "protected_change", "subject": "T0456: merge needs founder approval"}
- 2026-11-18T02:54:03+00:00 inbox_resolved {"id": "I0252", "status": "approved", "note": "T0456 merge approved, review T0463 accepts with caveats, routed to T0464. On 9 layouts all three strata meet A4 a
- 2026-11-18T02:54:24+00:00 merged {"task": "T0456"}
- 2026-11-18T02:54:26+00:00 registration_deferred {"task": "T0456", "experiment": "E007", "reason": "design task T0464 of E007 is still todo"}
- 2026-11-18T02:54:36+00:00 run_started {"run": "T0464-scientist-20261117T185436-0c97", "task": "T0464", "role": "scientist", "session": "e8a9a16f-8452-401c-8c0e-11fb73c6bc2b"}
- 2026-11-18T03:24:26+00:00 run_finished {"run": "T0464-scientist-20261117T185436-0c97", "status": "completed", "cost": 2.515331, "subtype": "success", "report": "structured_output"}
- 2026-11-18T03:34:48+00:00 verified {"task": "T0464"}
- 2026-11-18T03:35:03+00:00 run_started {"run": "T0465-critic-20261117T193503-66c1", "task": "T0465", "role": "critic", "session": "f95309b9-e3d1-4784-8426-24d524d66885"}
- 2026-11-18T03:40:31+00:00 run_finished {"run": "T0465-critic-20261117T193503-66c1", "status": "completed", "cost": 2.193401, "subtype": "success", "report": "structured_output"}
- 2026-11-18T03:40:38+00:00 inbox_opened {"id": "I0253", "kind": "protected_change", "subject": "T0464: merge needs founder approval"}
- 2026-11-18T03:45:08+00:00 inbox_resolved {"id": "I0253", "status": "approved", "note": "T0464 merge approved, review T0465 accepts with caveats. E007 finalised at m = 32, 480 layouts, cost 74 to 79 CPU
- 2026-11-18T03:45:13+00:00 merged {"task": "T0464"}
- 2026-11-18T03:45:14+00:00 inbox_opened {"id": "I0254", "kind": "experiment_registration", "subject": "register E007 (pre-registration)"}
