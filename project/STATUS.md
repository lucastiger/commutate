# ModuleForge status
_generated 2026-11-16T02:59:50+00:00 from repository state — do not edit_

## Founder inbox (3 open)
- **I0205** [external_action] [O008] Burst VM for E011's development L2 draws (band bound, joint operating characteristic, dev rows)
- **I0209** [external_action] [O004] O004: two F7 burst-VM runs before E004 registration, and a budget warning
- **I0212** [external_action] [O002] Burst VM run of n2's level-2 development solves (F1 pre-registration check)

## Objectives
| id | status | verdict | evals | spent | title |
|---|---|---|---|---|---|
| O000 | passed | PASS | 1/2 | $0.50/$20 | Framework canary — the loop carries a known-answer hypothesis from plan to verdict |
| O001 | passed | PASS | 1/3 | $287.86/$315 | L1 PEEC ranks half-bridge layouts faithfully enough to drive layout search |
| O002 | active | - | 0/1 | $21.73/$120 | A fast L1 thermal model predicts each die's average junction temperature, the spread across paralleled dies and layout-to-layout differences well enough to drive search |
| O003 | needs_founder | - | 0/1 | $258.22/$265 | Reference wire-bonded half-bridge layouts leave >= 20 % loop-inductance headroom inside their own housing at <= +2 K Tj |
| O004 | active | - | 0/1 | $25.93/$100 | The L2 inductance reference agrees with an independent field solver on the inductance ratios of re-layouts of PowerSynth public sample designs |
| O005 | draft | - | 0/2 | $7.65/$60 | L1 picks near-best layouts within a fixed family and die count, the regime derivative re-layout searches |
| O006 | active | INCONCLUSIVE | 1/1 | $137.91/$140 | The thermal L2 reference matches converged analytic solutions and an independent FEM, and design pilots measure what O002-O004 must fix |
| O007 | passed | PASS | 1/1 | $92.55/$110 | The scikit-fem thermal reference matches converged analytic solutions and the in-house finite-volume L2 on generator layouts |
| O008 | active | - | 0/2 | $25.75/$140 | A search seeded at a degraded copy of a near-optimal layout recovers it, where inductance-blind heuristics do not, on every designer-derived development layout |
| O901 | passed | PASS | 1/2 | $9.19/$30 | Infrastructure canary v2 - a known answer through registered, sealed, recomputed and null-checked evidence |

## Usage (from run records)
| objective | runs | usd | output tokens | thinking | denials | limit hits |
|---|---|---|---|---|---|---|
| O002 | 11 | $21.73 | 540809 | 352965 | 40 | 0 |
| O003 | 135 | $258.22 | 4105839 | 2002393 | 280 | 0 |
| O004 | 15 | $25.93 | 602089 | 439606 | 35 | 0 |
| O005 | 4 | $7.65 | 185443 | 108670 | 29 | 0 |
| O006 | 69 | $137.91 | 2633380 | 1435121 | 137 | 0 |
| O007 | 50 | $92.55 | 1684141 | 838123 | 79 | 1 |
| O008 | 17 | $25.75 | 631547 | 416686 | 41 | 0 |
| O901 | 3 | $5.05 | 101607 | 52842 | 14 | 0 |

## Tasks
cancelled: 44, done: 328, failed: 4, review: 2, running: 3, todo: 22

- T0376 `running` scientist/investigate: Kill shot: do the probe's designer proxy and its null gap survive l2_layout? (attempt 1)
- T0377 `review` builder/implement: Reach: straddling slots, column outer edges to the edge margin, and the in_domain predicate (attempt 1)
- T0381 `review` scientist/design_experiment: Draft E011's acceptance metric functions and analytic tests for the founder's mfos.metrics port (F7) (attempt 1)
- T0401 `running` critic/review: Review T0381 (numerics) (attempt 1)
- T0402 `running` critic/review: Review T0377 (physics) (attempt 1)

## Recent events
- 2026-11-16T01:51:50+00:00 inbox_resolved {"id": "I0211", "status": "approved", "note": "Patch route approved, limited to the bound F3 selects; the other functions are in mfos.metrics", "by": "human"}
- 2026-11-16T01:52:02+00:00 inbox_resolved {"id": "I0207", "status": "answered", "note": "(b)+(c): O004 runs the proxy descent in 1 mm steps (on the lattice by construction), and the pair's ratio is agai
- 2026-11-16T01:52:07+00:00 run_started {"run": "T0376-scientist-20261115T175207-16b0", "task": "T0376", "role": "scientist", "session": "a860343e-3462-4896-9eb6-56849e82c0b8"}
- 2026-11-16T01:52:07+00:00 run_started {"run": "T0377-builder-20261115T175207-24d7", "task": "T0377", "role": "builder", "session": "e8993f2b-1ff4-4a65-84b2-7d51ec15599c"}
- 2026-11-16T01:52:08+00:00 run_started {"run": "T0381-scientist-20261115T175208-7f35", "task": "T0381", "role": "scientist", "session": "c77411e8-bdc9-465a-a3d7-4d32ed3d8bb8"}
- 2026-11-16T02:31:32+00:00 run_finished {"run": "T0381-scientist-20261115T175208-7f35", "status": "completed", "cost": 1.904972, "subtype": "success", "report": "structured_output"}
- 2026-11-16T02:39:37+00:00 verified {"task": "T0381"}
- 2026-11-16T02:39:50+00:00 run_started {"run": "T0400-critic-20261115T183950-b68f", "task": "T0400", "role": "critic", "session": "2a7400de-afe6-4dda-a592-63158f3f7498"}
- 2026-11-16T02:40:26+00:00 sleep_detected {"gap_s": 535, "runs_extended": 3}
- 2026-11-16T02:43:25+00:00 run_finished {"run": "T0377-builder-20261115T175207-24d7", "status": "completed", "cost": 2.505912, "subtype": "success", "report": "structured_output"}
- 2026-11-16T02:54:54+00:00 verified {"task": "T0377"}
- 2026-11-16T02:55:09+00:00 run_started {"run": "T0401-critic-20261115T185509-05d8", "task": "T0401", "role": "critic", "session": "ec117b28-8bf1-48c6-9236-7b8740b2a52f"}
- 2026-11-16T02:55:46+00:00 sleep_detected {"gap_s": 742, "runs_extended": 3}
- 2026-11-16T02:55:47+00:00 run_finished {"run": "T0400-critic-20261115T183950-b68f", "status": "completed", "cost": 1.711575, "subtype": "success", "report": "structured_output"}
- 2026-11-16T02:55:59+00:00 run_started {"run": "T0402-critic-20261115T185559-039a", "task": "T0402", "role": "critic", "session": "3fefd00c-eea1-42b3-9166-e2836fc9bca8"}
