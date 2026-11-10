# ModuleForge status
_generated 2026-11-10T17:14:45+00:00 from repository state — do not edit_

## Founder inbox (1 open)
- **I0140** [question] [O003] Reference set on 2026-11-12 (D0010): customer layouts or public fallback

## Objectives
| id | status | verdict | evals | spent | title |
|---|---|---|---|---|---|
| O000 | passed | PASS | 1/2 | $0.50/$20 | Framework canary — the loop carries a known-answer hypothesis from plan to verdict |
| O001 | passed | PASS | 1/3 | $287.86/$315 | L1 PEEC ranks half-bridge layouts faithfully enough to drive layout search |
| O002 | draft | - | 0/1 | $11.44/$120 | A fast L1 thermal model predicts per-die Tj max, spread and layout-to-layout differences well enough to drive search |
| O003 | active | - | 0/1 | $100.49/$250 | Reference wire-bonded half-bridge layouts leave >= 20 % loop-inductance headroom inside their own housing at <= +2 K Tj |
| O004 | draft | - | 0/1 | $9.51/$100 | The L2 inductance reference is accurate on reconstructed public modules, so it can judge O003's headroom |
| O005 | draft | - | 0/2 | $7.65/$60 | L1 picks near-best layouts within a fixed family and die count, the regime derivative re-layout searches |
| O006 | active | INCONCLUSIVE | 1/1 | $137.91/$140 | The thermal L2 reference matches converged analytic solutions and an independent FEM, and design pilots measure what O002-O004 must fix |
| O007 | passed | PASS | 1/1 | $92.55/$110 | The scikit-fem thermal reference matches converged analytic solutions and the in-house finite-volume L2 on generator layouts |
| O901 | passed | PASS | 1/2 | $9.19/$30 | Infrastructure canary v2 - a known answer through registered, sealed, recomputed and null-checked evidence |

## Usage (from run records)
| objective | runs | usd | output tokens | thinking | denials | limit hits |
|---|---|---|---|---|---|---|
| O002 | 6 | $11.44 | 293351 | 180601 | 28 | 0 |
| O003 | 60 | $100.49 | 1814219 | 941923 | 93 | 0 |
| O004 | 6 | $9.51 | 225161 | 160260 | 17 | 0 |
| O005 | 4 | $7.65 | 185443 | 108670 | 29 | 0 |
| O006 | 69 | $137.91 | 2633380 | 1435121 | 137 | 0 |
| O007 | 50 | $92.55 | 1684141 | 838123 | 79 | 1 |
| O901 | 3 | $5.05 | 101607 | 52842 | 14 | 0 |

## Tasks
cancelled: 38, done: 256, failed: 3, review: 1, running: 1, todo: 2

- T0300 `review` builder/implement: Twin: band-copper column removal keeps T-junction necks; split tests that prove the minimum (review T0299) (attempt 1)
- T0301 `running` critic/review: Review T0300 (general) (attempt 1)

## Recent events
- 2026-11-10T14:14:27+00:00 run_finished {"run": "T0298-builder-20261110T052743-dea1", "status": "completed", "cost": 0.548323, "subtype": "success", "report": "structured_output"}
- 2026-11-10T14:34:31+00:00 verified {"task": "T0298"}
- 2026-11-10T14:34:36+00:00 run_started {"run": "T0299-critic-20261110T063436-bbdf", "task": "T0299", "role": "critic", "session": "5c74bcf3-2022-4ffb-8a90-fbeba6e0e079"}
- 2026-11-10T14:35:10+00:00 sleep_detected {"gap_s": 1244, "runs_extended": 1}
- 2026-11-10T14:54:30+00:00 run_finished {"run": "T0299-critic-20261110T063436-bbdf", "status": "completed", "cost": 1.601313, "subtype": "success", "report": "structured_output"}
- 2026-11-10T14:54:36+00:00 inbox_opened {"id": "I0162", "kind": "protected_change", "subject": "T0298: merge needs founder approval"}
- 2026-11-10T14:55:58+00:00 task_added {"task": "T0300", "reason": "review T0299 follow-up (T-junction necks, split tests)"}
- 2026-11-10T14:55:58+00:00 task_amended {"task": "T0262", "reason": "waits for T0300 (T-junction necks, review T0299); reports twin-vs-reconstruction copper"}
- 2026-11-10T14:55:58+00:00 task_amended {"task": "T0263", "reason": "twin-space check reports twin copper symdiff, midpoint splits and walk use (review T0299)"}
- 2026-11-10T15:19:40+00:00 inbox_resolved {"id": "I0162", "status": "approved", "note": "Merge T0298: best split scored on the band's own copper (column-adjacent L-bands), disjoint move/skip record; T02
- 2026-11-10T15:20:21+00:00 merged {"task": "T0298"}
- 2026-11-10T15:20:25+00:00 run_started {"run": "T0300-builder-20261110T072025-dabc", "task": "T0300", "role": "builder", "session": "d5d7713a-516e-4b03-ab75-5c47ad62f636"}
- 2026-11-10T16:49:45+00:00 run_finished {"run": "T0300-builder-20261110T072025-dabc", "status": "completed", "cost": 0.556406, "subtype": "success", "report": "structured_output"}
- 2026-11-10T17:14:37+00:00 verified {"task": "T0300"}
- 2026-11-10T17:14:45+00:00 run_started {"run": "T0301-critic-20261110T091445-3349", "task": "T0301", "role": "critic", "session": "07c88e2d-c7a7-4ff3-b51e-89a46bd18cde"}
