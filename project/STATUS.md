# ModuleForge status
_generated 2026-11-18T02:20:48+00:00 from repository state — do not edit_

## Founder inbox (3 open)
- **I0205** [external_action] [O008] Burst VM for E011's development L2 draws (band bound, joint operating characteristic, dev rows)
- **I0209** [external_action] [O004] O004: two F7 burst-VM runs before E004 registration, and a budget warning
- **I0250** [protected_change] T0382: merge needs founder approval

## Objectives
| id | status | verdict | evals | spent | title |
|---|---|---|---|---|---|
| O000 | passed | PASS | 1/2 | $0.50/$20 | Framework canary — the loop carries a known-answer hypothesis from plan to verdict |
| O001 | passed | PASS | 1/3 | $287.86/$315 | L1 PEEC ranks half-bridge layouts faithfully enough to drive layout search |
| O002 | active | - | 0/1 | $88.05/$120 | A fast L1 thermal model predicts each die's average junction temperature, the spread across paralleled dies and layout-to-layout differences well enough to drive search |
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
| O002 | 38 | $88.05 | 1629405 | 826307 | 118 | 0 |
| O003 | 135 | $258.22 | 4105839 | 2002393 | 280 | 0 |
| O004 | 55 | $118.73 | 1881647 | 1038213 | 142 | 0 |
| O005 | 4 | $7.65 | 185443 | 108670 | 29 | 0 |
| O006 | 69 | $137.91 | 2633380 | 1435121 | 137 | 0 |
| O007 | 50 | $92.55 | 1684141 | 838123 | 79 | 1 |
| O008 | 43 | $91.48 | 1532378 | 830907 | 120 | 0 |
| O901 | 3 | $5.05 | 101607 | 52842 | 14 | 0 |

## Tasks
cancelled: 47, done: 404, failed: 4, needs_founder: 1, running: 2, todo: 4

- T0382 `needs_founder` scientist/design_experiment: Design E011: draft spec and runner (selftest, smoke, development mode with the burst job manifest) (attempt 5)
- T0456 `running` scientist/design_experiment: E007: diagnose the per-stratum A4 misses (u_shaped/6 0.95), extra development layouts in 3 strata, corrected power simulation (attempt 1)
- T0457 `running` scientist/design_experiment: E004 design part 2b: banded acceptance and its simulation, redraw record, 2R proxy pair, provenance, solve-stage review fixes, local FastHenry probe (attempt 2)

## Recent events
- 2026-11-18T00:23:22+00:00 merged {"task": "T0398"}
- 2026-11-18T00:23:24+00:00 registration_deferred {"task": "T0398", "experiment": "E007", "reason": "design task T0456 of E007 is still todo"}
- 2026-11-18T00:23:35+00:00 run_started {"run": "T0456-scientist-20261117T162335-b347", "task": "T0456", "role": "scientist", "session": "d976bc9f-5c90-49df-a63a-4bbb33114849"}
- 2026-11-18T00:30:58+00:00 run_finished {"run": "T0382-scientist-20261117T160031-53cd", "status": "completed", "cost": 0.968663, "subtype": "success", "report": "structured_output"}
- 2026-11-18T00:52:39+00:00 verified {"task": "T0382"}
- 2026-11-18T00:52:39+00:00 run_finished {"run": "T0457-scientist-20261117T160032-2c24", "status": "error", "cost": 7.374897, "subtype": "error_max_turns", "report": "missing"}
- 2026-11-18T00:52:39+00:00 task_failed_attempt {"task": "T0457", "signal": "agent_error", "action": "repair"}
- 2026-11-18T00:53:01+00:00 run_started {"run": "T0460-critic-20261117T165301-7328", "task": "T0460", "role": "critic", "session": "46ff50b6-29ff-4d13-b5c8-e23afccf26be"}
- 2026-11-18T00:53:05+00:00 run_started {"run": "T0461-critic-20261117T165305-7d2e", "task": "T0461", "role": "critic", "session": "80ce883a-18c0-4a10-8933-217f769259c3"}
- 2026-11-18T01:08:24+00:00 run_finished {"run": "T0461-critic-20261117T165305-7d2e", "status": "completed", "cost": 2.672621, "subtype": "success", "report": "structured_output"}
- 2026-11-18T01:08:39+00:00 run_started {"run": "T0462-critic-20261117T170839-8c52", "task": "T0462", "role": "critic", "session": "c0135254-c5a8-475a-b158-98d80b621595"}
- 2026-11-18T01:19:40+00:00 run_finished {"run": "T0460-critic-20261117T165301-7328", "status": "completed", "cost": 2.539493, "subtype": "success", "report": "structured_output"}
- 2026-11-18T01:19:59+00:00 run_started {"run": "T0457-scientist-20261117T171959-9768", "task": "T0457", "role": "scientist", "session": "8988e2af-cc93-45bf-973f-e1b828fbf571"}
- 2026-11-18T01:23:06+00:00 run_finished {"run": "T0462-critic-20261117T170839-8c52", "status": "completed", "cost": 2.497534, "subtype": "success", "report": "structured_output"}
- 2026-11-18T02:19:54+00:00 inbox_opened {"id": "I0250", "kind": "protected_change", "subject": "T0382: merge needs founder approval"}
