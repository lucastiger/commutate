# ModuleForge status
_generated 2026-11-16T17:38:30+00:00 from repository state — do not edit_

## Founder inbox (4 open)
- **I0205** [external_action] [O008] Burst VM for E011's development L2 draws (band bound, joint operating characteristic, dev rows)
- **I0209** [external_action] [O004] O004: two F7 burst-VM runs before E004 registration, and a budget warning
- **I0223** [plan_approval] [O002] approve initial plan (1 tasks)
- **I0224** [protected_change] T0386: merge needs founder approval

## Objectives
| id | status | verdict | evals | spent | title |
|---|---|---|---|---|---|
| O000 | passed | PASS | 1/2 | $0.50/$20 | Framework canary — the loop carries a known-answer hypothesis from plan to verdict |
| O001 | passed | PASS | 1/3 | $287.86/$315 | L1 PEEC ranks half-bridge layouts faithfully enough to drive layout search |
| O002 | active | - | 0/1 | $41.75/$120 | A fast L1 thermal model predicts each die's average junction temperature, the spread across paralleled dies and layout-to-layout differences well enough to drive search |
| O003 | needs_founder | - | 0/1 | $258.22/$265 | Reference wire-bonded half-bridge layouts leave >= 20 % loop-inductance headroom inside their own housing at <= +2 K Tj |
| O004 | active | - | 0/1 | $53.79/$100 | The L2 inductance reference agrees with an independent field solver on the inductance ratios of re-layouts of PowerSynth public sample designs |
| O005 | draft | - | 0/2 | $7.65/$60 | L1 picks near-best layouts within a fixed family and die count, the regime derivative re-layout searches |
| O006 | active | INCONCLUSIVE | 1/1 | $137.91/$140 | The thermal L2 reference matches converged analytic solutions and an independent FEM, and design pilots measure what O002-O004 must fix |
| O007 | passed | PASS | 1/1 | $92.55/$110 | The scikit-fem thermal reference matches converged analytic solutions and the in-house finite-volume L2 on generator layouts |
| O008 | active | - | 0/2 | $43.15/$140 | A search seeded at a degraded copy of a near-optimal layout recovers it, where inductance-blind heuristics do not, on every designer-derived development layout |
| O901 | passed | PASS | 1/2 | $9.19/$30 | Infrastructure canary v2 - a known answer through registered, sealed, recomputed and null-checked evidence |

## Usage (from run records)
| objective | runs | usd | output tokens | thinking | denials | limit hits |
|---|---|---|---|---|---|---|
| O002 | 20 | $41.75 | 924612 | 524203 | 58 | 0 |
| O003 | 135 | $258.22 | 4105839 | 2002393 | 280 | 0 |
| O004 | 29 | $53.79 | 1037870 | 667043 | 79 | 0 |
| O005 | 4 | $7.65 | 185443 | 108670 | 29 | 0 |
| O006 | 69 | $137.91 | 2633380 | 1435121 | 137 | 0 |
| O007 | 50 | $92.55 | 1684141 | 838123 | 79 | 1 |
| O008 | 25 | $43.15 | 953271 | 584314 | 76 | 0 |
| O901 | 3 | $5.05 | 101607 | 52842 | 14 | 0 |

## Tasks
cancelled: 45, done: 351, failed: 4, needs_founder: 1, proposed: 1, review: 2, running: 3, todo: 13

- T0379 `running` builder/implement: Designer proxy rule, randomised degradation family and ablation (e) (attempt 1)
- T0384 `review` builder/implement: FastHenry deck exporter in src: Layout -> SI-metre deck with refinable wire section, thickness and plane knobs, F6 model variants (attempt 3)
- T0386 `needs_founder` builder/implement: Frozen perturbation rules on the 1 mm lattice: die-row shift, power-trace width, terminal-near copper, wire landing (generate/perturb.py) (attempt 3)
- T0395 `running` builder/implement: L1 thermal model in src/moduleforge/thermal/ (n1's chosen design), tested against analytic limits, symmetry and power scaling, with a speed benchmark (attempt 2)
- T0396 `review` scientist/design_experiment: E007 statistics: F3 coverage and power simulation, bound selection and fixed allocation; protected mfos.metrics additions drafted as a patch (attempt 1)
- T0417 `running` critic/review: Review T0384 (physics) (attempt 1)
- T0419 `proposed` builder/implement: F1 development check: gate the level-1 verdict on the sanity block and per-record provenance (review T0411 findings 1-2) (attempt 0)

## Recent events
- 2026-11-16T16:25:15+00:00 run_finished {"run": "T0418-critic-20261116T081637-d3db", "status": "completed", "cost": 2.191171, "subtype": "success", "report": "structured_output"}
- 2026-11-16T16:25:27+00:00 run_started {"run": "T0396-scientist-20261116T082527-88e2", "task": "T0396", "role": "scientist", "session": "13bf75d0-f5d8-4d88-b403-935856986e88"}
- 2026-11-16T16:58:41+00:00 run_finished {"run": "T0395-builder-20261116T082437-92ea", "status": "completed", "cost": 0.850593, "subtype": "success", "report": "structured_output"}
- 2026-11-16T17:17:05+00:00 task_failed_attempt {"task": "T0395", "signal": "dod_failed", "action": "repair"}
- 2026-11-16T17:17:13+00:00 run_started {"run": "T0395-builder-20261116T091713-10cb", "task": "T0395", "role": "builder", "session": "141e31cb-1492-4ed8-9a01-b52e54e36fd6"}
- 2026-11-16T17:17:49+00:00 sleep_detected {"gap_s": 1149, "runs_extended": 3}
- 2026-11-16T17:28:25+00:00 run_finished {"run": "T0396-scientist-20261116T082527-88e2", "status": "completed", "cost": 6.091297, "subtype": "success", "report": "structured_output"}
- 2026-11-16T17:32:37+00:00 inbox_resolved {"id": "I0222", "status": "approved", "note": "T0378 merge approved (reviews T0414, T0415 accept with caveats; foot-offset removal and review fixes carried into
- 2026-11-16T17:32:39+00:00 replan_declined {"objective": "O002", "reason": "T0392/T0393 results covered by the approved plan; T0412 stopped"}
- 2026-11-16T17:33:04+00:00 note {"objective": "O002", "text": "correction: T0412 completed at 16:16 before the 17:32 replan_declined; T0412 restored to done; T0419/I0223 await the founder"}
- 2026-11-16T17:37:00+00:00 inbox_resolved {"id": "I0212", "status": "approved", "note": "Done 2026-11-16: founder ran research/o002_f1/burst_level2.sh (n2d-custom-8-81920-ext, 137 min, about $1.40, VM d
- 2026-11-16T17:37:30+00:00 verified {"task": "T0396"}
- 2026-11-16T17:37:35+00:00 merged {"task": "T0378"}
- 2026-11-16T17:37:44+00:00 run_started {"run": "T0379-builder-20261116T093744-60f2", "task": "T0379", "role": "builder", "session": "5a8d8e79-b99e-480d-b07f-f9d8872a0093"}
- 2026-11-16T17:38:19+00:00 sleep_detected {"gap_s": 600, "runs_extended": 3}
