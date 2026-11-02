# ModuleForge status
_generated 2026-11-02T03:48:29+00:00 from repository state — do not edit_

## Founder inbox (2 open)
- **I0066** [external_action] [O006] P3 burst VM run of the missing 0.25/0.125 mm l2_layout levels (T0154 diagnosis)
- **I0072** [decision] T0157: 2 review rounds rejected; your call

## Objectives
| id | status | verdict | evals | spent | title |
|---|---|---|---|---|---|
| O000 | passed | PASS | 1/2 | $0.50/$20 | Framework canary — the loop carries a known-answer hypothesis from plan to verdict |
| O001 | passed | PASS | 1/3 | $287.86/$315 | L1 PEEC ranks half-bridge layouts faithfully enough to drive layout search |
| O002 | draft | - | 0/1 | $11.44/$120 | A fast L1 thermal model predicts per-die Tj max, spread and layout-to-layout differences well enough to drive search |
| O003 | draft | - | 0/1 | $5.89/$150 | Reference wire-bonded half-bridge layouts leave >= 20 % loop-inductance headroom inside their own housing at <= +2 K Tj |
| O004 | draft | - | 0/1 | $9.51/$100 | The L2 inductance reference is accurate on reconstructed public modules, so it can judge O003's headroom |
| O005 | draft | - | 0/2 | $7.65/$60 | L1 picks near-best layouts within a fixed family and die count, the regime derivative re-layout searches |
| O006 | active | - | 0/1 | $60.73/$115 | The thermal L2 reference matches converged analytic solutions and an independent FEM, and design pilots measure what O002-O004 must fix |
| O901 | passed | PASS | 1/2 | $9.19/$30 | Infrastructure canary v2 - a known answer through registered, sealed, recomputed and null-checked evidence |

## Usage (from run records)
| objective | runs | usd | output tokens | thinking | denials | limit hits |
|---|---|---|---|---|---|---|
| O002 | 6 | $11.44 | 293351 | 180601 | 28 | 0 |
| O003 | 4 | $5.89 | 136620 | 96498 | 8 | 0 |
| O004 | 6 | $9.51 | 225161 | 160260 | 17 | 0 |
| O005 | 4 | $7.65 | 185443 | 108670 | 29 | 0 |
| O006 | 34 | $60.73 | 1318369 | 740859 | 51 | 0 |
| O901 | 3 | $5.05 | 101607 | 52842 | 14 | 0 |

## Tasks
cancelled: 30, done: 133, failed: 3, needs_founder: 1, running: 2, todo: 6

- T0155 `running` scientist/investigate: Pilot P4: FastHenry feasibility on 2D_Case_4 via a Layout-to-FastHenry exporter (research note, not evidence) (attempt 1)
- T0157 `needs_founder` scout/research: Verify every k(T) law and citation in geometry/stack.py against primary sources (attempt 2)
- T0163 `running` builder/implement: thermal_fv: second-order prescribed flux on the Robin face, Picard re-check of the returned field, tests (review T0160) (attempt 1)

## Recent events
- 2026-11-02T03:36:47+00:00 merged {"task": "T0153"}
- 2026-11-02T03:36:51+00:00 run_started {"run": "T0174-critic-20261101T193651-8590", "task": "T0174", "role": "critic", "session": "1bb919a0-7296-4f8f-ae9e-c0f7b673357c"}
- 2026-11-02T03:36:58+00:00 task_amended {"task": "T0165", "reason": "pin k(T) 30 % reading (T0173)"}
- 2026-11-02T03:36:58+00:00 task_amended {"task": "T0167", "reason": "k(T) sensitivity per T0157"}
- 2026-11-02T03:41:38+00:00 run_finished {"run": "T0174-critic-20261101T193651-8590", "status": "completed", "cost": 1.209264, "subtype": "success", "report": "structured_output"}
- 2026-11-02T03:41:40+00:00 task_failed_attempt {"task": "T0157", "signal": "review_rejected", "action": "repair"}
- 2026-11-02T03:41:43+00:00 run_started {"run": "T0157-scout-20261101T194143-6678", "task": "T0157", "role": "scout", "session": "94462071-f3c7-437f-abcd-51aa8e6f124c"}
- 2026-11-02T03:42:23+00:00 task_amended {"task": "T0167", "reason": "SiC range from T0157 final note (T0174)"}
- 2026-11-02T03:43:52+00:00 run_finished {"run": "T0157-scout-20261101T194143-6678", "status": "completed", "cost": 0.514512, "subtype": "success", "report": "structured_output"}
- 2026-11-02T03:44:38+00:00 verified {"task": "T0157"}
- 2026-11-02T03:44:43+00:00 run_started {"run": "T0175-critic-20261101T194443-b676", "task": "T0175", "role": "critic", "session": "ebd4f43b-7705-43af-bc53-5c9805c697e6"}
- 2026-11-02T03:48:22+00:00 run_finished {"run": "T0175-critic-20261101T194443-b676", "status": "completed", "cost": 1.030551, "subtype": "success", "report": "structured_output"}
- 2026-11-02T03:48:25+00:00 inbox_opened {"id": "I0072", "kind": "decision", "subject": "T0157: 2 review rounds rejected; your call"}
- 2026-11-02T03:48:25+00:00 review_round_cap {"task": "T0157", "rounds": 2}
- 2026-11-02T03:48:29+00:00 run_started {"run": "T0163-builder-20261101T194829-6df1", "task": "T0163", "role": "builder", "session": "5ae48dc6-7e12-429a-b196-d5632b8e8bc4"}
