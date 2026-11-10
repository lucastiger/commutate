# ModuleForge status
_generated 2026-11-10T19:06:39+00:00 from repository state — do not edit_

## Founder inbox (2 open)
- **I0140** [question] [O003] Reference set on 2026-11-12 (D0010): customer layouts or public fallback
- **I0163** [protected_change] T0300: merge needs founder approval

## Objectives
| id | status | verdict | evals | spent | title |
|---|---|---|---|---|---|
| O000 | passed | PASS | 1/2 | $0.50/$20 | Framework canary — the loop carries a known-answer hypothesis from plan to verdict |
| O001 | passed | PASS | 1/3 | $287.86/$315 | L1 PEEC ranks half-bridge layouts faithfully enough to drive layout search |
| O002 | draft | - | 0/1 | $11.44/$120 | A fast L1 thermal model predicts per-die Tj max, spread and layout-to-layout differences well enough to drive search |
| O003 | active | - | 0/1 | $107.48/$250 | Reference wire-bonded half-bridge layouts leave >= 20 % loop-inductance headroom inside their own housing at <= +2 K Tj |
| O004 | draft | - | 0/1 | $9.51/$100 | The L2 inductance reference is accurate on reconstructed public modules, so it can judge O003's headroom |
| O005 | draft | - | 0/2 | $7.65/$60 | L1 picks near-best layouts within a fixed family and die count, the regime derivative re-layout searches |
| O006 | active | INCONCLUSIVE | 1/1 | $137.91/$140 | The thermal L2 reference matches converged analytic solutions and an independent FEM, and design pilots measure what O002-O004 must fix |
| O007 | passed | PASS | 1/1 | $92.55/$110 | The scikit-fem thermal reference matches converged analytic solutions and the in-house finite-volume L2 on generator layouts |
| O901 | passed | PASS | 1/2 | $9.19/$30 | Infrastructure canary v2 - a known answer through registered, sealed, recomputed and null-checked evidence |

## Usage (from run records)
| objective | runs | usd | output tokens | thinking | denials | limit hits |
|---|---|---|---|---|---|---|
| O002 | 6 | $11.44 | 293351 | 180601 | 28 | 0 |
| O003 | 63 | $107.48 | 1929712 | 1013139 | 100 | 0 |
| O004 | 6 | $9.51 | 225161 | 160260 | 17 | 0 |
| O005 | 4 | $7.65 | 185443 | 108670 | 29 | 0 |
| O006 | 69 | $137.91 | 2633380 | 1435121 | 137 | 0 |
| O007 | 50 | $92.55 | 1684141 | 838123 | 79 | 1 |
| O901 | 3 | $5.05 | 101607 | 52842 | 14 | 0 |

## Tasks
cancelled: 38, done: 258, failed: 3, needs_founder: 1, todo: 2

- T0300 `needs_founder` builder/implement: Twin: band-copper column removal keeps T-junction necks; split tests that prove the minimum (review T0299) (attempt 2)

## Recent events
- 2026-11-10T17:14:45+00:00 run_started {"run": "T0301-critic-20261110T091445-3349", "task": "T0301", "role": "critic", "session": "07c88e2d-c7a7-4ff3-b51e-89a46bd18cde"}
- 2026-11-10T17:15:19+00:00 sleep_detected {"gap_s": 1535, "runs_extended": 1}
- 2026-11-10T17:33:31+00:00 run_finished {"run": "T0301-critic-20261110T091445-3349", "status": "error", "cost": 1.163615, "subtype": "success", "report": "missing"}
- 2026-11-10T17:33:31+00:00 task_failed_attempt {"task": "T0301", "signal": "agent_error", "action": "repair"}
- 2026-11-10T17:33:37+00:00 run_started {"run": "T0301-critic-20261110T093337-66dc", "task": "T0301", "role": "critic", "session": "4fcbb6e6-e00f-4152-815e-bf3054edfe35"}
- 2026-11-10T17:46:43+00:00 run_finished {"run": "T0301-critic-20261110T093337-66dc", "status": "completed", "cost": 1.315408, "subtype": "success", "report": "structured_output"}
- 2026-11-10T17:46:45+00:00 task_failed_attempt {"task": "T0300", "signal": "review_rejected", "action": "repair"}
- 2026-11-10T17:46:47+00:00 run_started {"run": "T0300-builder-20261110T094647-e3b4", "task": "T0300", "role": "builder", "session": "d530ca17-c96d-484f-9abf-2afa7e20deba"}
- 2026-11-10T18:32:33+00:00 run_finished {"run": "T0300-builder-20261110T094647-e3b4", "status": "completed", "cost": 2.782074, "subtype": "success", "report": "structured_output"}
- 2026-11-10T18:51:03+00:00 verified {"task": "T0300"}
- 2026-11-10T18:51:08+00:00 run_started {"run": "T0302-critic-20261110T105108-aa59", "task": "T0302", "role": "critic", "session": "875b0bbb-be74-484e-8e26-dc4f12d89b99"}
- 2026-11-10T18:51:42+00:00 sleep_detected {"gap_s": 1150, "runs_extended": 1}
- 2026-11-10T19:05:04+00:00 run_finished {"run": "T0302-critic-20261110T105108-aa59", "status": "completed", "cost": 1.720518, "subtype": "success", "report": "structured_output"}
- 2026-11-10T19:05:09+00:00 inbox_opened {"id": "I0163", "kind": "protected_change", "subject": "T0300: merge needs founder approval"}
- 2026-11-10T19:06:08+00:00 task_amended {"task": "T0262", "reason": "spec lists the twin's documented limitations (review T0302); no further split follow-up"}
