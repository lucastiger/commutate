# ModuleForge status
_generated 2026-11-09T07:20:27+00:00 from repository state — do not edit_

## Founder inbox (4 open)
- **I0138** [external_action] [O003] Burst compute for E008 and its pre-registration checks
- **I0139** [external_action] [O003] Protected-path changes before E008 registration
- **I0140** [question] [O003] Reference set on 2026-11-12 (D0010): customer layouts or public fallback
- **I0141** [plan_approval] [O003] approve initial plan (8 tasks)

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
| O003 | 9 | $15.21 | 302482 | 210476 | 11 | 0 |
| O004 | 6 | $9.51 | 225161 | 160260 | 17 | 0 |
| O005 | 4 | $7.65 | 185443 | 108670 | 29 | 0 |
| O006 | 69 | $137.91 | 2633380 | 1435121 | 137 | 0 |
| O007 | 50 | $92.55 | 1684141 | 838123 | 79 | 1 |
| O901 | 3 | $5.05 | 101607 | 52842 | 14 | 0 |

## Tasks
cancelled: 38, done: 214, failed: 3, proposed: 8

- T0256 `proposed` builder/implement: Per-net design rules, gate/Kelvin signal wires, bondability DRC and rule measurement (attempt 0)
- T0257 `proposed` builder/implement: AlN k(T) law in stack.py and the frozen grid-snapping rule (attempt 0)
- T0258 `proposed` builder/implement: Generalised derivative-layout generator inside a reference's housing (attempt 0)
- T0259 `proposed` builder/implement: Twin construction and degradation rule (F1(a), F1(b)) (attempt 0)
- T0260 `proposed` builder/implement: Search driver per D0008/F3 with L1-only null, near ties, levelling record and control mode (attempt 0)
- T0261 `proposed` scientist/design_experiment: Draft headroom_min_lo / headroom_max_hi_ind (protected mfos.metrics) and the E008 row contract (attempt 0)
- T0262 `proposed` scientist/design_experiment: E008 design: draft spec and runner, sealed seeds, code-hash freeze, cost estimate, local dev rows (attempt 0)
- T0263 `proposed` scientist/research: Frozen reconstructions of PowerSynth 2D_Case_2R and 2D_Case_6 (D0010 public fallback), snapped, with measured rules (attempt 0)

## Recent events
- 2026-11-09T06:44:24+00:00 run_finished {"run": "T0251-critic-20261108T223758-4a63", "status": "completed", "cost": 1.602902, "subtype": "success", "report": "structured_output"}
- 2026-11-09T06:44:25+00:00 run_finished {"run": "T0252-critic-20261108T223759-1306", "status": "completed", "cost": 1.704452, "subtype": "success", "report": "structured_output"}
- 2026-11-09T06:51:32+00:00 objective_draft_review {"objective": "O003", "ref": "1a39aa3b2e4087b915b158833aebce9c3090a0a0", "tasks": ["T0253", "T0254"]}
- 2026-11-09T06:52:05+00:00 run_started {"run": "T0253-critic-20261108T225205-629b", "task": "T0253", "role": "critic", "session": "7288e5c9-0d4a-4659-a3af-657790b87f0b"}
- 2026-11-09T06:52:06+00:00 run_started {"run": "T0254-critic-20261108T225206-fdf2", "task": "T0254", "role": "critic", "session": "d41207f3-3413-45d8-8a70-0ae3d6d3a414"}
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
