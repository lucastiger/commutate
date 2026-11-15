# ModuleForge status
_generated 2026-11-15T22:15:08+00:00 from repository state — do not edit_

## Founder inbox (0 open)
- nothing needs you

## Objectives
| id | status | verdict | evals | spent | title |
|---|---|---|---|---|---|
| O000 | passed | PASS | 1/2 | $0.50/$20 | Framework canary — the loop carries a known-answer hypothesis from plan to verdict |
| O001 | passed | PASS | 1/3 | $287.86/$315 | L1 PEEC ranks half-bridge layouts faithfully enough to drive layout search |
| O002 | draft | - | 0/1 | $11.44/$120 | A fast L1 thermal model predicts per-die Tj max, spread and layout-to-layout differences well enough to drive search |
| O003 | needs_founder | - | 0/1 | $258.22/$265 | Reference wire-bonded half-bridge layouts leave >= 20 % loop-inductance headroom inside their own housing at <= +2 K Tj |
| O004 | draft | - | 0/1 | $9.51/$100 | The L2 inductance reference is accurate on reconstructed public modules, so it can judge O003's headroom |
| O005 | draft | - | 0/2 | $7.65/$60 | L1 picks near-best layouts within a fixed family and die count, the regime derivative re-layout searches |
| O006 | active | INCONCLUSIVE | 1/1 | $137.91/$140 | The thermal L2 reference matches converged analytic solutions and an independent FEM, and design pilots measure what O002-O004 must fix |
| O007 | passed | PASS | 1/1 | $92.55/$110 | The scikit-fem thermal reference matches converged analytic solutions and the in-house finite-volume L2 on generator layouts |
| O008 | draft | - | 0/2 | $6.93/$140 | A search seeded at a degraded copy of the reference, in a parameterisation that contains the reference's twin, recovers planted loop-inductance headroom on held-out degradations of the development layouts |
| O901 | passed | PASS | 1/2 | $9.19/$30 | Infrastructure canary v2 - a known answer through registered, sealed, recomputed and null-checked evidence |

## Usage (from run records)
| objective | runs | usd | output tokens | thinking | denials | limit hits |
|---|---|---|---|---|---|---|
| O002 | 6 | $11.44 | 293351 | 180601 | 28 | 0 |
| O003 | 135 | $258.22 | 4105839 | 2002393 | 280 | 0 |
| O004 | 6 | $9.51 | 225161 | 160260 | 17 | 0 |
| O005 | 4 | $7.65 | 185443 | 108670 | 29 | 0 |
| O006 | 69 | $137.91 | 2633380 | 1435121 | 137 | 0 |
| O007 | 50 | $92.55 | 1684141 | 838123 | 79 | 1 |
| O008 | 4 | $6.93 | 148814 | 105629 | 6 | 0 |
| O901 | 3 | $5.05 | 101607 | 52842 | 14 | 0 |

## Tasks
cancelled: 44, done: 306, failed: 4


## Recent events
- 2026-11-15T20:03:03+00:00 inbox_resolved {"id": "I0203", "status": "approved", "note": "Merge T0349 (diagnosis of EV-O003-01: E010 void; the frozen search cannot reach the 2R designer's level). Review 
- 2026-11-15T20:09:06+00:00 merged {"task": "T0349"}
- 2026-11-15T20:09:44+00:00 sleep_detected {"gap_s": 380, "runs_extended": 0}
- 2026-11-15T21:34:29+00:00 loop_started {"pid": 97506}
- 2026-11-15T21:36:47+00:00 objective_draft_review {"objective": "O008", "ref": "0df043d9a6a8ae1c054ed2b88da3bbca3742398a", "tasks": ["T0351", "T0352"]}
- 2026-11-15T21:37:10+00:00 run_started {"run": "T0351-critic-20261115T133710-bab2", "task": "T0351", "role": "critic", "session": "86f2b7ba-93d2-4146-9ccf-f8049a3669c9"}
- 2026-11-15T21:37:11+00:00 run_started {"run": "T0352-critic-20261115T133711-be38", "task": "T0352", "role": "critic", "session": "1e87a00a-b27f-4df0-ab04-8215fd3f4d19"}
- 2026-11-15T21:43:23+00:00 run_finished {"run": "T0351-critic-20261115T133710-bab2", "status": "completed", "cost": 1.486634, "subtype": "success", "report": "structured_output"}
- 2026-11-15T21:46:31+00:00 run_finished {"run": "T0352-critic-20261115T133711-be38", "status": "completed", "cost": 1.945286, "subtype": "success", "report": "structured_output"}
- 2026-11-15T22:06:09+00:00 loop_started {"pid": 26177}
- 2026-11-15T22:06:16+00:00 objective_draft_review {"objective": "O008", "ref": "38b97be630e1882e3df9f76cd9a163bb2a67b148", "tasks": ["T0353", "T0354"]}
- 2026-11-15T22:06:56+00:00 run_started {"run": "T0353-critic-20261115T140656-e293", "task": "T0353", "role": "critic", "session": "c06debc0-d131-4b08-888e-3ee3eec64092"}
- 2026-11-15T22:06:57+00:00 run_started {"run": "T0354-critic-20261115T140657-07cf", "task": "T0354", "role": "critic", "session": "b35f2ba3-5a0d-44fe-aeca-7f8cd950463f"}
- 2026-11-15T22:13:47+00:00 run_finished {"run": "T0353-critic-20261115T140656-e293", "status": "completed", "cost": 1.578319, "subtype": "success", "report": "structured_output"}
- 2026-11-15T22:15:04+00:00 run_finished {"run": "T0354-critic-20261115T140657-07cf", "status": "completed", "cost": 1.917719, "subtype": "success", "report": "structured_output"}
