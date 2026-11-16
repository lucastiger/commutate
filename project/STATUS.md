# ModuleForge status
_generated 2026-11-16T16:25:27+00:00 from repository state — do not edit_

## Founder inbox (6 open)
- **I0205** [external_action] [O008] Burst VM for E011's development L2 draws (band bound, joint operating characteristic, dev rows)
- **I0209** [external_action] [O004] O004: two F7 burst-VM runs before E004 registration, and a budget warning
- **I0212** [external_action] [O002] Burst VM run of n2's level-2 development solves (F1 pre-registration check)
- **I0222** [protected_change] T0378: merge needs founder approval
- **I0223** [plan_approval] [O002] approve initial plan (1 tasks)
- **I0224** [protected_change] T0386: merge needs founder approval

## Objectives
| id | status | verdict | evals | spent | title |
|---|---|---|---|---|---|
| O000 | passed | PASS | 1/2 | $0.50/$20 | Framework canary — the loop carries a known-answer hypothesis from plan to verdict |
| O001 | passed | PASS | 1/3 | $287.86/$315 | L1 PEEC ranks half-bridge layouts faithfully enough to drive layout search |
| O002 | active | - | 0/1 | $34.81/$120 | A fast L1 thermal model predicts each die's average junction temperature, the spread across paralleled dies and layout-to-layout differences well enough to drive search |
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
| O002 | 19 | $34.81 | 764563 | 446345 | 51 | 0 |
| O003 | 135 | $258.22 | 4105839 | 2002393 | 280 | 0 |
| O004 | 29 | $53.79 | 1037870 | 667043 | 79 | 0 |
| O005 | 4 | $7.65 | 185443 | 108670 | 29 | 0 |
| O006 | 69 | $137.91 | 2633380 | 1435121 | 137 | 0 |
| O007 | 50 | $92.55 | 1684141 | 838123 | 79 | 1 |
| O008 | 24 | $43.15 | 953271 | 584314 | 76 | 0 |
| O901 | 3 | $5.05 | 101607 | 52842 | 14 | 0 |

## Tasks
cancelled: 45, done: 350, failed: 4, needs_founder: 2, proposed: 1, review: 1, running: 3, todo: 13

- T0378 `needs_founder` builder/implement: Seeded local search over the derivative parameterisation (optimize/local.py) (attempt 1)
- T0384 `review` builder/implement: FastHenry deck exporter in src: Layout -> SI-metre deck with refinable wire section, thickness and plane knobs, F6 model variants (attempt 3)
- T0386 `needs_founder` builder/implement: Frozen perturbation rules on the 1 mm lattice: die-row shift, power-trace width, terminal-near copper, wire landing (generate/perturb.py) (attempt 3)
- T0395 `running` builder/implement: L1 thermal model in src/moduleforge/thermal/ (n1's chosen design), tested against analytic limits, symmetry and power scaling, with a speed benchmark (attempt 1)
- T0396 `running` scientist/design_experiment: E007 statistics: F3 coverage and power simulation, bound selection and fixed allocation; protected mfos.metrics additions drafted as a patch (attempt 1)
- T0417 `running` critic/review: Review T0384 (physics) (attempt 1)
- T0419 `proposed` builder/implement: F1 development check: gate the level-1 verdict on the sanity block and per-record provenance (review T0411 findings 1-2) (attempt 0)

## Recent events
- 2026-11-16T16:10:24+00:00 sleep_detected {"gap_s": 1703, "runs_extended": 3}
- 2026-11-16T16:10:25+00:00 run_finished {"run": "T0384-builder-20261116T063048-5eee", "status": "completed", "cost": 3.25279, "subtype": "success", "report": "structured_output"}
- 2026-11-16T16:16:25+00:00 verified {"task": "T0384"}
- 2026-11-16T16:16:25+00:00 run_finished {"run": "T0412-planner-20261116T080949-4d80", "status": "completed", "cost": 1.015579, "subtype": "success", "report": "structured_output"}
- 2026-11-16T16:16:26+00:00 inbox_opened {"id": "I0223", "kind": "plan_approval", "subject": "[O002] approve initial plan (1 tasks)"}
- 2026-11-16T16:16:26+00:00 plan_applied {"objective": "O002", "created": ["T0419"], "dropped": 0}
- 2026-11-16T16:16:35+00:00 run_started {"run": "T0417-critic-20261116T081635-d96d", "task": "T0417", "role": "critic", "session": "270f99dc-9974-48af-b8cc-1ed1511dc78f"}
- 2026-11-16T16:16:37+00:00 run_started {"run": "T0418-critic-20261116T081637-d3db", "task": "T0418", "role": "critic", "session": "9228fa32-9171-4cc9-af2f-686c3df3c698"}
- 2026-11-16T16:17:13+00:00 sleep_detected {"gap_s": 408, "runs_extended": 3}
- 2026-11-16T16:17:14+00:00 run_finished {"run": "T0416-critic-20261116T080949-bbcc", "status": "completed", "cost": 2.0926, "subtype": "success", "report": "structured_output"}
- 2026-11-16T16:24:29+00:00 inbox_opened {"id": "I0224", "kind": "protected_change", "subject": "T0386: merge needs founder approval"}
- 2026-11-16T16:24:37+00:00 run_started {"run": "T0395-builder-20261116T082437-92ea", "task": "T0395", "role": "builder", "session": "4c03f443-5d88-4ade-bff5-dc4b2d82e2bc"}
- 2026-11-16T16:25:14+00:00 sleep_detected {"gap_s": 481, "runs_extended": 3}
- 2026-11-16T16:25:15+00:00 run_finished {"run": "T0418-critic-20261116T081637-d3db", "status": "completed", "cost": 2.191171, "subtype": "success", "report": "structured_output"}
- 2026-11-16T16:25:27+00:00 run_started {"run": "T0396-scientist-20261116T082527-88e2", "task": "T0396", "role": "scientist", "session": "13bf75d0-f5d8-4d88-b403-935856986e88"}
