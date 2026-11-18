# ModuleForge status
_generated 2026-11-18T02:33:41+00:00 from repository state — do not edit_

## Founder inbox (2 open)
- **I0205** [external_action] [O008] Burst VM for E011's development L2 draws (band bound, joint operating characteristic, dev rows)
- **I0209** [external_action] [O004] O004: two F7 burst-VM runs before E004 registration, and a budget warning

## Objectives
| id | status | verdict | evals | spent | title |
|---|---|---|---|---|---|
| O000 | passed | PASS | 1/2 | $0.50/$20 | Framework canary — the loop carries a known-answer hypothesis from plan to verdict |
| O001 | passed | PASS | 1/3 | $287.86/$315 | L1 PEEC ranks half-bridge layouts faithfully enough to drive layout search |
| O002 | active | - | 0/1 | $92.84/$120 | A fast L1 thermal model predicts each die's average junction temperature, the spread across paralleled dies and layout-to-layout differences well enough to drive search |
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
| O002 | 39 | $92.84 | 1703518 | 853294 | 118 | 0 |
| O003 | 135 | $258.22 | 4105839 | 2002393 | 280 | 0 |
| O004 | 55 | $118.73 | 1881647 | 1038213 | 142 | 0 |
| O005 | 4 | $7.65 | 185443 | 108670 | 29 | 0 |
| O006 | 69 | $137.91 | 2633380 | 1435121 | 137 | 0 |
| O007 | 50 | $92.55 | 1684141 | 838123 | 79 | 1 |
| O008 | 43 | $91.48 | 1532378 | 830907 | 120 | 0 |
| O901 | 3 | $5.05 | 101607 | 52842 | 14 | 0 |

## Tasks
cancelled: 47, done: 405, failed: 4, review: 1, running: 2, todo: 5

- T0456 `review` scientist/design_experiment: E007: diagnose the per-stratum A4 misses (u_shaped/6 0.95), extra development layouts in 3 strata, corrected power simulation (attempt 1)
- T0457 `running` scientist/design_experiment: E004 design part 2b: banded acceptance and its simulation, redraw record, 2R proxy pair, provenance, solve-stage review fixes, local FastHenry probe (attempt 2)
- T0463 `running` critic/review: Review T0456 (general) (attempt 1)

## Recent events
- 2026-11-18T01:08:24+00:00 run_finished {"run": "T0461-critic-20261117T165305-7d2e", "status": "completed", "cost": 2.672621, "subtype": "success", "report": "structured_output"}
- 2026-11-18T01:08:39+00:00 run_started {"run": "T0462-critic-20261117T170839-8c52", "task": "T0462", "role": "critic", "session": "c0135254-c5a8-475a-b158-98d80b621595"}
- 2026-11-18T01:19:40+00:00 run_finished {"run": "T0460-critic-20261117T165301-7328", "status": "completed", "cost": 2.539493, "subtype": "success", "report": "structured_output"}
- 2026-11-18T01:19:59+00:00 run_started {"run": "T0457-scientist-20261117T171959-9768", "task": "T0457", "role": "scientist", "session": "8988e2af-cc93-45bf-973f-e1b828fbf571"}
- 2026-11-18T01:23:06+00:00 run_finished {"run": "T0462-critic-20261117T170839-8c52", "status": "completed", "cost": 2.497534, "subtype": "success", "report": "structured_output"}
- 2026-11-18T02:19:54+00:00 inbox_opened {"id": "I0250", "kind": "protected_change", "subject": "T0382: merge needs founder approval"}
- 2026-11-18T02:21:23+00:00 run_finished {"run": "T0456-scientist-20261117T162335-b347", "status": "completed", "cost": 4.794641, "subtype": "success", "report": "structured_output"}
- 2026-11-18T02:26:43+00:00 inbox_resolved {"id": "I0250", "status": "approved", "note": "T0382 merge approved, reviews T0460, T0461, T0462 accept with caveats, logged in O008 state for the pre-registrat
- 2026-11-18T02:29:23+00:00 verified {"task": "T0456"}
- 2026-11-18T02:29:27+00:00 merged {"task": "T0382"}
- 2026-11-18T02:29:29+00:00 inbox_opened {"id": "I0251", "kind": "experiment_registration", "subject": "register E011 (pre-registration)"}
- 2026-11-18T02:29:40+00:00 run_started {"run": "T0463-critic-20261117T182940-d3e0", "task": "T0463", "role": "critic", "session": "9e7dcb8d-48d0-4f14-af53-c3281206fcdb"}
- 2026-11-18T02:32:48+00:00 inbox_resolved {"id": "I0251", "status": "rejected", "note": "Premature: E011 needs its development burst (I0205), the development L2 analysis, and founder decisions on the se
- 2026-11-18T02:33:12+00:00 founder_decision_recorded {"objective": "O002", "summary": "E007: per-stratum A4 check passed on 9 layouts; m = 32 (480 layouts)"}
- 2026-11-18T02:33:12+00:00 task_added {"task": "T0464", "note": "founder decision 2026-11-18"}
