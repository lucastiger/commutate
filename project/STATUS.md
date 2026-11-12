# ModuleForge status
_generated 2026-11-12T21:33:00+00:00 from repository state — do not edit_

## Founder inbox (7 open)
- **I0165** [experiment_registration] register E008 (pre-registration)
- **I0167** [experiment_registration] register E008 (pre-registration)
- **I0169** [experiment_registration] register E008 (pre-registration)
- **I0171** [experiment_registration] register E008 (pre-registration)
- **I0175** [experiment_registration] register E008 (pre-registration)
- **I0177** [experiment_registration] register E008 (pre-registration)
- **I0179** [experiment_registration] register E008 (pre-registration)

## Objectives
| id | status | verdict | evals | spent | title |
|---|---|---|---|---|---|
| O000 | passed | PASS | 1/2 | $0.50/$20 | Framework canary — the loop carries a known-answer hypothesis from plan to verdict |
| O001 | passed | PASS | 1/3 | $287.86/$315 | L1 PEEC ranks half-bridge layouts faithfully enough to drive layout search |
| O002 | draft | - | 0/1 | $11.44/$120 | A fast L1 thermal model predicts per-die Tj max, spread and layout-to-layout differences well enough to drive search |
| O003 | active | - | 0/1 | $194.49/$250 | Reference wire-bonded half-bridge layouts leave >= 20 % loop-inductance headroom inside their own housing at <= +2 K Tj |
| O004 | draft | - | 0/1 | $9.51/$100 | The L2 inductance reference is accurate on reconstructed public modules, so it can judge O003's headroom |
| O005 | draft | - | 0/2 | $7.65/$60 | L1 picks near-best layouts within a fixed family and die count, the regime derivative re-layout searches |
| O006 | active | INCONCLUSIVE | 1/1 | $137.91/$140 | The thermal L2 reference matches converged analytic solutions and an independent FEM, and design pilots measure what O002-O004 must fix |
| O007 | passed | PASS | 1/1 | $92.55/$110 | The scikit-fem thermal reference matches converged analytic solutions and the in-house finite-volume L2 on generator layouts |
| O901 | passed | PASS | 1/2 | $9.19/$30 | Infrastructure canary v2 - a known answer through registered, sealed, recomputed and null-checked evidence |

## Usage (from run records)
| objective | runs | usd | output tokens | thinking | denials | limit hits |
|---|---|---|---|---|---|---|
| O002 | 6 | $11.44 | 293351 | 180601 | 28 | 0 |
| O003 | 103 | $194.49 | 3135471 | 1573949 | 171 | 0 |
| O004 | 6 | $9.51 | 225161 | 160260 | 17 | 0 |
| O005 | 4 | $7.65 | 185443 | 108670 | 29 | 0 |
| O006 | 69 | $137.91 | 2633380 | 1435121 | 137 | 0 |
| O007 | 50 | $92.55 | 1684141 | 838123 | 79 | 1 |
| O901 | 3 | $5.05 | 101607 | 52842 | 14 | 0 |

## Tasks
cancelled: 39, done: 279, failed: 3, todo: 1


## Recent events
- 2026-11-12T19:30:13+00:00 founder_decision_noted {"decision": "D0019 (draft, to be committed): O003 judged references stay D0010 public fallback 2D_Case_2R + 2D_Case_6; F3 deviation declared (T0316, T0317 afte
- 2026-11-12T19:30:19+00:00 run_started {"run": "T0320-scientist-20261112T113019-c937", "task": "T0320", "role": "scientist", "session": "7b289e87-f086-4eac-9071-ac94e0f2bd92"}
- 2026-11-12T20:10:50+00:00 run_finished {"run": "T0320-scientist-20261112T113019-c937", "status": "completed", "cost": 6.328291, "subtype": "success", "report": "structured_output"}
- 2026-11-12T20:24:57+00:00 verified {"task": "T0320"}
- 2026-11-12T20:25:03+00:00 run_started {"run": "T0321-critic-20261112T122503-f7af", "task": "T0321", "role": "critic", "session": "f2206079-4dd3-4a18-980c-2d7dd8a52431"}
- 2026-11-12T20:25:38+00:00 sleep_detected {"gap_s": 889, "runs_extended": 1}
- 2026-11-12T20:39:05+00:00 run_finished {"run": "T0321-critic-20261112T122503-f7af", "status": "completed", "cost": 2.185204, "subtype": "success", "report": "structured_output"}
- 2026-11-12T20:39:09+00:00 inbox_opened {"id": "I0178", "kind": "protected_change", "subject": "T0320: merge needs founder approval"}
- 2026-11-12T20:46:28+00:00 inbox_resolved {"id": "I0178", "status": "approved", "note": "Merge T0320 (D0019: judged-reference loader, registered path full(), --check-references, real-size cost plan, dec
- 2026-11-12T20:46:37+00:00 merged {"task": "T0320"}
- 2026-11-12T20:46:37+00:00 inbox_opened {"id": "I0179", "kind": "experiment_registration", "subject": "register E008 (pre-registration)"}
- 2026-11-12T21:06:03+00:00 task_added {"task": "T0322", "reason": "founder 2026-11-12: T0321 fixes, report-only for an excluded reference's stack type, launch procedure"}
- 2026-11-12T21:06:25+00:00 run_started {"run": "T0322-scientist-20261112T130625-cd1f", "task": "T0322", "role": "scientist", "session": "135d4e61-3315-485d-a9f8-d2b9baf300c7"}
- 2026-11-12T21:32:58+00:00 run_finished {"run": "T0322-scientist-20261112T130625-cd1f", "status": "error", "cost": 5.174583, "subtype": "success", "report": "missing"}
- 2026-11-12T21:32:58+00:00 capacity_backoff {"task": "T0322", "minutes": 5, "parsed_reset": false}
