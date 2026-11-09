# ModuleForge status
_generated 2026-11-09T07:28:46+00:00 from repository state — do not edit_

## Founder inbox (1 open)
- **I0140** [question] [O003] Reference set on 2026-11-12 (D0010): customer layouts or public fallback

## Objectives
| id | status | verdict | evals | spent | title |
|---|---|---|---|---|---|
| O000 | passed | PASS | 1/2 | $0.50/$20 | Framework canary — the loop carries a known-answer hypothesis from plan to verdict |
| O001 | passed | PASS | 1/3 | $287.86/$315 | L1 PEEC ranks half-bridge layouts faithfully enough to drive layout search |
| O002 | draft | - | 0/1 | $11.44/$120 | A fast L1 thermal model predicts per-die Tj max, spread and layout-to-layout differences well enough to drive search |
| O003 | active | - | 0/1 | $15.21/$250 | Reference wire-bonded half-bridge layouts leave >= 20 % loop-inductance headroom inside their own housing at <= +2 K Tj |
| O004 | draft | - | 0/1 | $9.51/$100 | The L2 inductance reference is accurate on reconstructed public modules, so it can judge O003's headroom |
| O005 | draft | - | 0/2 | $7.65/$60 | L1 picks near-best layouts within a fixed family and die count, the regime derivative re-layout searches |
| O006 | active | INCONCLUSIVE | 1/1 | $137.91/$140 | The thermal L2 reference matches converged analytic solutions and an independent FEM, and design pilots measure what O002-O004 must fix |
| O007 | passed | PASS | 1/1 | $92.55/$110 | The scikit-fem thermal reference matches converged analytic solutions and the in-house finite-volume L2 on generator layouts |
| O901 | passed | PASS | 1/2 | $9.19/$30 | Infrastructure canary v2 - a known answer through registered, sealed, recomputed and null-checked evidence |

## Usage (from run records)
| objective | runs | usd | output tokens | thinking | denials | limit hits |
|---|---|---|---|---|---|---|
| O002 | 6 | $11.44 | 293351 | 180601 | 28 | 0 |
| O003 | 11 | $15.21 | 302482 | 210476 | 11 | 0 |
| O004 | 6 | $9.51 | 225161 | 160260 | 17 | 0 |
| O005 | 4 | $7.65 | 185443 | 108670 | 29 | 0 |
| O006 | 69 | $137.91 | 2633380 | 1435121 | 137 | 0 |
| O007 | 50 | $92.55 | 1684141 | 838123 | 79 | 1 |
| O901 | 3 | $5.05 | 101607 | 52842 | 14 | 0 |

## Tasks
cancelled: 38, done: 214, failed: 3, running: 2, todo: 6

- T0256 `running` builder/implement: Per-net design rules, gate/Kelvin signal wires, bondability DRC and rule measurement (attempt 1)
- T0257 `running` builder/implement: AlN k(T) law in stack.py and the frozen grid-snapping rule (attempt 1)

## Recent events
- 2026-11-09T06:59:06+00:00 run_finished {"run": "T0254-critic-20261108T225206-fdf2", "status": "completed", "cost": 1.733284, "subtype": "success", "report": "structured_output"}
- 2026-11-09T07:05:02+00:00 run_finished {"run": "T0253-critic-20261108T225205-629b", "status": "completed", "cost": 2.001104, "subtype": "success", "report": "structured_output"}
- 2026-11-09T07:11:55+00:00 objective_approved {"objective": "O003", "criteria_hash": "sha256:887a2ecefbcf0b10619e92df91ce193a6d5a3e685430ef9a456e398c22e71a62"}
- 2026-11-09T07:12:09+00:00 run_started {"run": "T0255-planner-20261108T231209-3cdb", "task": "T0255", "role": "planner", "session": "7bb31f2f-6013-4687-9422-e9c4c4adc22a"}
- 2026-11-09T07:20:23+00:00 run_finished {"run": "T0255-planner-20261108T231209-3cdb", "status": "completed", "cost": 2.278426, "subtype": "success", "report": "structured_output"}
- 2026-11-09T07:20:24+00:00 inbox_opened {"id": "I0138", "kind": "external_action", "subject": "[O003] Burst compute for E008 and its pre-registration checks"}
- 2026-11-09T07:20:24+00:00 inbox_opened {"id": "I0139", "kind": "external_action", "subject": "[O003] Protected-path changes before E008 registration"}
- 2026-11-09T07:20:24+00:00 inbox_opened {"id": "I0140", "kind": "question", "subject": "[O003] Reference set on 2026-11-12 (D0010): customer layouts or public fallback"}
- 2026-11-09T07:20:24+00:00 inbox_opened {"id": "I0141", "kind": "plan_approval", "subject": "[O003] approve initial plan (8 tasks)"}
- 2026-11-09T07:20:24+00:00 plan_applied {"objective": "O003", "created": ["T0256", "T0257", "T0258", "T0259", "T0260", "T0261", "T0262", "T0263"], "dropped": 0}
- 2026-11-09T07:28:33+00:00 inbox_resolved {"id": "I0141", "status": "approved", "note": "Plan approved (T0256-T0263): build chain on generator housings and 2D_Case_4 per F3; public reconstructions after
- 2026-11-09T07:28:39+00:00 inbox_resolved {"id": "I0138", "status": "approved", "note": "E008 added to burst_experiments; VM time reserved for the full-fidelity dev rows once the E008 design merges.", "
- 2026-11-09T07:28:46+00:00 inbox_resolved {"id": "I0139", "status": "approved", "note": "thermal_fem.py confirmed at a216d5fe (EV-O007-01 bytes, revert dd9727cc); metrics patch to be applied on T0261's 
- 2026-11-09T07:28:46+00:00 run_started {"run": "T0256-builder-20261108T232846-aecb", "task": "T0256", "role": "builder", "session": "4d03165a-cd3e-44be-8f98-60f8bbcf2f02"}
- 2026-11-09T07:28:46+00:00 run_started {"run": "T0257-builder-20261108T232846-46d1", "task": "T0257", "role": "builder", "session": "a3123393-042c-41fe-b0b7-78edbd27c4bf"}
