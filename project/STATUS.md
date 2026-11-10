# ModuleForge status
_generated 2026-11-10T23:33:01+00:00 from repository state — do not edit_

## Founder inbox (1 open)
- **I0140** [question] [O003] Reference set on 2026-11-12 (D0010): customer layouts or public fallback

## Objectives
| id | status | verdict | evals | spent | title |
|---|---|---|---|---|---|
| O000 | passed | PASS | 1/2 | $0.50/$20 | Framework canary — the loop carries a known-answer hypothesis from plan to verdict |
| O001 | passed | PASS | 1/3 | $287.86/$315 | L1 PEEC ranks half-bridge layouts faithfully enough to drive layout search |
| O002 | draft | - | 0/1 | $11.44/$120 | A fast L1 thermal model predicts per-die Tj max, spread and layout-to-layout differences well enough to drive search |
| O003 | active | - | 0/1 | $124.71/$250 | Reference wire-bonded half-bridge layouts leave >= 20 % loop-inductance headroom inside their own housing at <= +2 K Tj |
| O004 | draft | - | 0/1 | $9.51/$100 | The L2 inductance reference is accurate on reconstructed public modules, so it can judge O003's headroom |
| O005 | draft | - | 0/2 | $7.65/$60 | L1 picks near-best layouts within a fixed family and die count, the regime derivative re-layout searches |
| O006 | active | INCONCLUSIVE | 1/1 | $137.91/$140 | The thermal L2 reference matches converged analytic solutions and an independent FEM, and design pilots measure what O002-O004 must fix |
| O007 | passed | PASS | 1/1 | $92.55/$110 | The scikit-fem thermal reference matches converged analytic solutions and the in-house finite-volume L2 on generator layouts |
| O901 | passed | PASS | 1/2 | $9.19/$30 | Infrastructure canary v2 - a known answer through registered, sealed, recomputed and null-checked evidence |

## Usage (from run records)
| objective | runs | usd | output tokens | thinking | denials | limit hits |
|---|---|---|---|---|---|---|
| O002 | 6 | $11.44 | 293351 | 180601 | 28 | 0 |
| O003 | 84 | $124.71 | 2115513 | 1105338 | 101 | 0 |
| O004 | 6 | $9.51 | 225161 | 160260 | 17 | 0 |
| O005 | 4 | $7.65 | 185443 | 108670 | 29 | 0 |
| O006 | 69 | $137.91 | 2633380 | 1435121 | 137 | 0 |
| O007 | 50 | $92.55 | 1684141 | 838123 | 79 | 1 |
| O901 | 3 | $5.05 | 101607 | 52842 | 14 | 0 |

## Tasks
cancelled: 39, done: 259, failed: 3, review: 1, running: 2, todo: 1

- T0262 `review` scientist/design_experiment: E008 design: draft spec and runner, sealed seeds, code-hash freeze, cost estimate, local dev rows (attempt 4)
- T0304 `running` critic/review: Review T0262 (physics) (attempt 1)
- T0305 `running` critic/review: Review T0262 (numerics) (attempt 1)

## Recent events
- 2026-11-10T22:48:19+00:00 capacity_backoff {"task": "T0262", "minutes": 5, "parsed_reset": false}
- 2026-11-10T22:53:32+00:00 run_started {"run": "T0262-scientist-20261110T145332-4045", "task": "T0262", "role": "scientist", "session": "130fac71-b3bf-4190-b4ce-2bd874527476"}
- 2026-11-10T22:54:46+00:00 run_finished {"run": "T0262-scientist-20261110T145332-4045", "status": "error", "cost": 0.0, "subtype": "success", "report": "missing"}
- 2026-11-10T22:54:46+00:00 capacity_backoff {"task": "T0262", "minutes": 5, "parsed_reset": false}
- 2026-11-10T22:59:59+00:00 run_started {"run": "T0262-scientist-20261110T145959-e041", "task": "T0262", "role": "scientist", "session": "ec33a4b5-9724-4f5f-a164-1eac752ec17e"}
- 2026-11-10T23:01:13+00:00 run_finished {"run": "T0262-scientist-20261110T145959-e041", "status": "error", "cost": 0.0, "subtype": "success", "report": "missing"}
- 2026-11-10T23:01:13+00:00 capacity_backoff {"task": "T0262", "minutes": 5, "parsed_reset": false}
- 2026-11-10T23:06:41+00:00 run_started {"run": "T0262-scientist-20261110T150641-c0b3", "task": "T0262", "role": "scientist", "session": "a5deb032-9e9f-455b-865c-97a8f84222eb"}
- 2026-11-10T23:20:10+00:00 loop_stopped {"reason": "STOP file"}
- 2026-11-10T23:20:15+00:00 loop_started {"pid": 41702}
- 2026-11-10T23:25:53+00:00 run_finished {"run": "T0262-scientist-20261110T150641-c0b3", "status": "completed", "cost": 4.069834, "subtype": "success", "report": "structured_output"}
- 2026-11-10T23:32:12+00:00 verified {"task": "T0262"}
- 2026-11-10T23:32:19+00:00 run_started {"run": "T0304-critic-20261110T153219-0ef7", "task": "T0304", "role": "critic", "session": "46e61b18-a61a-4cd7-858e-54bb18dbcbf5"}
- 2026-11-10T23:32:20+00:00 run_started {"run": "T0305-critic-20261110T153220-dc97", "task": "T0305", "role": "critic", "session": "4f282073-aaa3-412f-9792-ec0864dc90c3"}
- 2026-11-10T23:32:55+00:00 sleep_detected {"gap_s": 423, "runs_extended": 2}
