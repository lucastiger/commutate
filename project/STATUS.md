# ModuleForge status
_generated 2026-11-10T22:48:23+00:00 from repository state — do not edit_

## Founder inbox (1 open)
- **I0140** [question] [O003] Reference set on 2026-11-12 (D0010): customer layouts or public fallback

## Objectives
| id | status | verdict | evals | spent | title |
|---|---|---|---|---|---|
| O000 | passed | PASS | 1/2 | $0.50/$20 | Framework canary — the loop carries a known-answer hypothesis from plan to verdict |
| O001 | passed | PASS | 1/3 | $287.86/$315 | L1 PEEC ranks half-bridge layouts faithfully enough to drive layout search |
| O002 | draft | - | 0/1 | $11.44/$120 | A fast L1 thermal model predicts per-die Tj max, spread and layout-to-layout differences well enough to drive search |
| O003 | active | - | 0/1 | $120.64/$250 | Reference wire-bonded half-bridge layouts leave >= 20 % loop-inductance headroom inside their own housing at <= +2 K Tj |
| O004 | draft | - | 0/1 | $9.51/$100 | The L2 inductance reference is accurate on reconstructed public modules, so it can judge O003's headroom |
| O005 | draft | - | 0/2 | $7.65/$60 | L1 picks near-best layouts within a fixed family and die count, the regime derivative re-layout searches |
| O006 | active | INCONCLUSIVE | 1/1 | $137.91/$140 | The thermal L2 reference matches converged analytic solutions and an independent FEM, and design pilots measure what O002-O004 must fix |
| O007 | passed | PASS | 1/1 | $92.55/$110 | The scikit-fem thermal reference matches converged analytic solutions and the in-house finite-volume L2 on generator layouts |
| O901 | passed | PASS | 1/2 | $9.19/$30 | Infrastructure canary v2 - a known answer through registered, sealed, recomputed and null-checked evidence |

## Usage (from run records)
| objective | runs | usd | output tokens | thinking | denials | limit hits |
|---|---|---|---|---|---|---|
| O002 | 6 | $11.44 | 293351 | 180601 | 28 | 0 |
| O003 | 79 | $120.64 | 2046881 | 1066298 | 101 | 0 |
| O004 | 6 | $9.51 | 225161 | 160260 | 17 | 0 |
| O005 | 4 | $7.65 | 185443 | 108670 | 29 | 0 |
| O006 | 69 | $137.91 | 2633380 | 1435121 | 137 | 0 |
| O007 | 50 | $92.55 | 1684141 | 838123 | 79 | 1 |
| O901 | 3 | $5.05 | 101607 | 52842 | 14 | 0 |

## Tasks
cancelled: 39, done: 259, failed: 3, todo: 2


## Recent events
- 2026-11-10T22:21:17+00:00 run_started {"run": "T0262-scientist-20261110T142117-deca", "task": "T0262", "role": "scientist", "session": "12f1a011-b8df-46f6-b08e-24308602e407"}
- 2026-11-10T22:22:30+00:00 run_finished {"run": "T0262-scientist-20261110T142117-deca", "status": "error", "cost": 0.0, "subtype": "success", "report": "missing"}
- 2026-11-10T22:22:30+00:00 capacity_backoff {"task": "T0262", "minutes": 5, "parsed_reset": false}
- 2026-11-10T22:27:43+00:00 run_started {"run": "T0262-scientist-20261110T142743-933b", "task": "T0262", "role": "scientist", "session": "d9b55e11-9d2d-4263-bd8d-0f41ebd7a663"}
- 2026-11-10T22:28:56+00:00 run_finished {"run": "T0262-scientist-20261110T142743-933b", "status": "error", "cost": 0.0, "subtype": "success", "report": "missing"}
- 2026-11-10T22:28:56+00:00 capacity_backoff {"task": "T0262", "minutes": 5, "parsed_reset": false}
- 2026-11-10T22:34:10+00:00 run_started {"run": "T0262-scientist-20261110T143410-b0b9", "task": "T0262", "role": "scientist", "session": "d64e2336-5072-4628-95b0-7e2bfba5d3f9"}
- 2026-11-10T22:35:23+00:00 run_finished {"run": "T0262-scientist-20261110T143410-b0b9", "status": "error", "cost": 0.0, "subtype": "success", "report": "missing"}
- 2026-11-10T22:35:23+00:00 capacity_backoff {"task": "T0262", "minutes": 5, "parsed_reset": false}
- 2026-11-10T22:40:36+00:00 run_started {"run": "T0262-scientist-20261110T144036-d854", "task": "T0262", "role": "scientist", "session": "879fffb0-476a-4c0a-bbd6-09dc65cf554e"}
- 2026-11-10T22:41:50+00:00 run_finished {"run": "T0262-scientist-20261110T144036-d854", "status": "error", "cost": 0.0, "subtype": "success", "report": "missing"}
- 2026-11-10T22:41:50+00:00 capacity_backoff {"task": "T0262", "minutes": 5, "parsed_reset": false}
- 2026-11-10T22:47:03+00:00 run_started {"run": "T0262-scientist-20261110T144703-3e6e", "task": "T0262", "role": "scientist", "session": "b7970228-1481-4577-ad0c-5642b007f1be"}
- 2026-11-10T22:48:19+00:00 run_finished {"run": "T0262-scientist-20261110T144703-3e6e", "status": "error", "cost": 0.0, "subtype": "success", "report": "missing"}
- 2026-11-10T22:48:19+00:00 capacity_backoff {"task": "T0262", "minutes": 5, "parsed_reset": false}
