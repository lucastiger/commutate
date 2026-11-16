# ModuleForge status
_generated 2026-11-16T04:45:21+00:00 from repository state — do not edit_

## Founder inbox (4 open)
- **I0205** [external_action] [O008] Burst VM for E011's development L2 draws (band bound, joint operating characteristic, dev rows)
- **I0209** [external_action] [O004] O004: two F7 burst-VM runs before E004 registration, and a budget warning
- **I0212** [external_action] [O002] Burst VM run of n2's level-2 development solves (F1 pre-registration check)
- **I0215** [protected_change] T0377: merge needs founder approval

## Objectives
| id | status | verdict | evals | spent | title |
|---|---|---|---|---|---|
| O000 | passed | PASS | 1/2 | $0.50/$20 | Framework canary — the loop carries a known-answer hypothesis from plan to verdict |
| O001 | passed | PASS | 1/3 | $287.86/$315 | L1 PEEC ranks half-bridge layouts faithfully enough to drive layout search |
| O002 | active | - | 0/1 | $21.73/$120 | A fast L1 thermal model predicts each die's average junction temperature, the spread across paralleled dies and layout-to-layout differences well enough to drive search |
| O003 | needs_founder | - | 0/1 | $258.22/$265 | Reference wire-bonded half-bridge layouts leave >= 20 % loop-inductance headroom inside their own housing at <= +2 K Tj |
| O004 | active | - | 0/1 | $29.12/$100 | The L2 inductance reference agrees with an independent field solver on the inductance ratios of re-layouts of PowerSynth public sample designs |
| O005 | draft | - | 0/2 | $7.65/$60 | L1 picks near-best layouts within a fixed family and die count, the regime derivative re-layout searches |
| O006 | active | INCONCLUSIVE | 1/1 | $137.91/$140 | The thermal L2 reference matches converged analytic solutions and an independent FEM, and design pilots measure what O002-O004 must fix |
| O007 | passed | PASS | 1/1 | $92.55/$110 | The scikit-fem thermal reference matches converged analytic solutions and the in-house finite-volume L2 on generator layouts |
| O008 | active | - | 0/2 | $36.11/$140 | A search seeded at a degraded copy of a near-optimal layout recovers it, where inductance-blind heuristics do not, on every designer-derived development layout |
| O901 | passed | PASS | 1/2 | $9.19/$30 | Infrastructure canary v2 - a known answer through registered, sealed, recomputed and null-checked evidence |

## Usage (from run records)
| objective | runs | usd | output tokens | thinking | denials | limit hits |
|---|---|---|---|---|---|---|
| O002 | 11 | $21.73 | 540809 | 352965 | 40 | 0 |
| O003 | 135 | $258.22 | 4105839 | 2002393 | 280 | 0 |
| O004 | 19 | $29.12 | 677928 | 474604 | 44 | 0 |
| O005 | 4 | $7.65 | 185443 | 108670 | 29 | 0 |
| O006 | 69 | $137.91 | 2633380 | 1435121 | 137 | 0 |
| O007 | 50 | $92.55 | 1684141 | 838123 | 79 | 1 |
| O008 | 19 | $36.11 | 814987 | 513086 | 60 | 0 |
| O901 | 3 | $5.05 | 101607 | 52842 | 14 | 0 |

## Tasks
cancelled: 44, done: 333, failed: 4, needs_founder: 1, review: 2, running: 3, todo: 19

- T0376 `review` scientist/investigate: Kill shot: do the probe's designer proxy and its null gap survive l2_layout? (attempt 1)
- T0377 `needs_founder` builder/implement: Reach: straddling slots, column outer edges to the edge margin, and the in_domain predicate (attempt 1)
- T0384 `review` builder/implement: FastHenry deck exporter in src: Layout -> SI-metre deck with refinable wire section, thickness and plane knobs, F6 model variants (attempt 1)
- T0386 `running` builder/implement: Frozen perturbation rules on the 1 mm lattice: die-row shift, power-trace width, terminal-near copper, wire landing (generate/perturb.py) (attempt 1)
- T0405 `running` critic/review: Review T0384 (numerics) (attempt 1)
- T0406 `running` critic/review: Review T0376 (general) (attempt 1)

## Recent events
- 2026-11-16T03:41:30+00:00 inbox_resolved {"id": "I0214", "status": "approved", "note": "T0381 merge approved (review T0400 accept with caveats); the session rebuilds the mfos.metrics fix on top", "by":
- 2026-11-16T03:41:47+00:00 run_finished {"run": "T0403-critic-20261115T193110-6839", "status": "completed", "cost": 2.238844, "subtype": "success", "report": "structured_output"}
- 2026-11-16T04:14:48+00:00 inbox_opened {"id": "I0215", "kind": "protected_change", "subject": "T0377: merge needs founder approval"}
- 2026-11-16T04:14:50+00:00 merged {"task": "T0381"}
- 2026-11-16T04:14:59+00:00 run_started {"run": "T0386-builder-20261115T201459-c16e", "task": "T0386", "role": "builder", "session": "329239a0-8171-4ea1-bf4e-79df621ad06b"}
- 2026-11-16T04:15:35+00:00 sleep_detected {"gap_s": 2028, "runs_extended": 3}
- 2026-11-16T04:15:36+00:00 run_finished {"run": "T0384-builder-20261115T193153-c4a4", "status": "completed", "cost": 0.788596, "subtype": "success", "report": "structured_output"}
- 2026-11-16T04:24:05+00:00 verified {"task": "T0384"}
- 2026-11-16T04:24:05+00:00 run_finished {"run": "T0376-scientist-20261115T175207-16b0", "status": "completed", "cost": 4.420349, "subtype": "success", "report": "structured_output"}
- 2026-11-16T04:33:09+00:00 verified {"task": "T0376"}
- 2026-11-16T04:33:27+00:00 run_started {"run": "T0404-critic-20261115T203327-bb2a", "task": "T0404", "role": "critic", "session": "5325d940-e7bc-49a6-8a67-7cfbd6255bfd"}
- 2026-11-16T04:33:30+00:00 run_started {"run": "T0405-critic-20261115T203330-a271", "task": "T0405", "role": "critic", "session": "85aa27e1-1f4b-43c8-842a-44a2bad39309"}
- 2026-11-16T04:34:06+00:00 sleep_detected {"gap_s": 1112, "runs_extended": 3}
- 2026-11-16T04:41:50+00:00 run_finished {"run": "T0404-critic-20261115T203327-bb2a", "status": "completed", "cost": 2.39727, "subtype": "success", "report": "structured_output"}
- 2026-11-16T04:42:12+00:00 run_started {"run": "T0406-critic-20261115T204212-b27a", "task": "T0406", "role": "critic", "session": "f4351c45-92a4-416b-a7c8-4042d86f92c3"}
