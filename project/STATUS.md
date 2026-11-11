# ModuleForge status
_generated 2026-11-11T18:25:02+00:00 from repository state — do not edit_

## Founder inbox (5 open)
- **I0165** [experiment_registration] register E008 (pre-registration)
- **I0167** [experiment_registration] register E008 (pre-registration)
- **I0169** [experiment_registration] register E008 (pre-registration)
- **I0171** [experiment_registration] register E008 (pre-registration)
- **I0173** [protected_change] T0314: merge needs founder approval

## Objectives
| id | status | verdict | evals | spent | title |
|---|---|---|---|---|---|
| O000 | passed | PASS | 1/2 | $0.50/$20 | Framework canary — the loop carries a known-answer hypothesis from plan to verdict |
| O001 | passed | PASS | 1/3 | $287.86/$315 | L1 PEEC ranks half-bridge layouts faithfully enough to drive layout search |
| O002 | draft | - | 0/1 | $11.44/$120 | A fast L1 thermal model predicts per-die Tj max, spread and layout-to-layout differences well enough to drive search |
| O003 | active | - | 0/1 | $166.79/$250 | Reference wire-bonded half-bridge layouts leave >= 20 % loop-inductance headroom inside their own housing at <= +2 K Tj |
| O004 | draft | - | 0/1 | $9.51/$100 | The L2 inductance reference is accurate on reconstructed public modules, so it can judge O003's headroom |
| O005 | draft | - | 0/2 | $7.65/$60 | L1 picks near-best layouts within a fixed family and die count, the regime derivative re-layout searches |
| O006 | active | INCONCLUSIVE | 1/1 | $137.91/$140 | The thermal L2 reference matches converged analytic solutions and an independent FEM, and design pilots measure what O002-O004 must fix |
| O007 | passed | PASS | 1/1 | $92.55/$110 | The scikit-fem thermal reference matches converged analytic solutions and the in-house finite-volume L2 on generator layouts |
| O901 | passed | PASS | 1/2 | $9.19/$30 | Infrastructure canary v2 - a known answer through registered, sealed, recomputed and null-checked evidence |

## Usage (from run records)
| objective | runs | usd | output tokens | thinking | denials | limit hits |
|---|---|---|---|---|---|---|
| O002 | 6 | $11.44 | 293351 | 180601 | 28 | 0 |
| O003 | 96 | $166.79 | 2738782 | 1402759 | 142 | 0 |
| O004 | 6 | $9.51 | 225161 | 160260 | 17 | 0 |
| O005 | 4 | $7.65 | 185443 | 108670 | 29 | 0 |
| O006 | 69 | $137.91 | 2633380 | 1435121 | 137 | 0 |
| O007 | 50 | $92.55 | 1684141 | 838123 | 79 | 1 |
| O901 | 3 | $5.05 | 101607 | 52842 | 14 | 0 |

## Tasks
cancelled: 39, done: 272, failed: 3, needs_founder: 1

- T0314 `needs_founder` scientist/research: Twin and degradation coverage on the development layouts 2D_Case_2R, 2D_Case_6 and 2D_Case_4: which rule binds and the smallest change (L0/L1 only) (attempt 1)

## Recent events
- 2026-11-11T06:55:03+00:00 run_started {"run": "T0313-critic-20261110T225503-2965", "task": "T0313", "role": "critic", "session": "3befbdf5-572d-45d9-89e6-6b7bf046a6b8"}
- 2026-11-11T06:55:37+00:00 sleep_detected {"gap_s": 364, "runs_extended": 1}
- 2026-11-11T07:02:29+00:00 run_finished {"run": "T0313-critic-20261110T225503-2965", "status": "completed", "cost": 2.034329, "subtype": "success", "report": "structured_output"}
- 2026-11-11T07:02:33+00:00 inbox_opened {"id": "I0172", "kind": "protected_change", "subject": "T0263: merge needs founder approval"}
- 2026-11-11T09:01:42+00:00 inbox_resolved {"id": "I0172", "status": "approved", "note": "Merge the frozen 2D_Case_2R and 2D_Case_6 reconstructions. Critic T0313 confirms both fail E008's twin check; E00
- 2026-11-11T09:01:50+00:00 merged {"task": "T0263"}
- 2026-11-11T15:54:52+00:00 inbox_resolved {"id": "I0140", "status": "answered", "note": "No admissible customer layout by 2026-11-12. Public reference set under review: NC State PREES (Prof. Hopkins) pu
- 2026-11-11T16:00:34+00:00 task_added {"task": "T0314", "reason": "founder go-ahead 2026-11-11: twin/degradation coverage diagnosis on the development layouts"}
- 2026-11-11T16:01:02+00:00 run_started {"run": "T0314-scientist-20261111T080102-d51f", "task": "T0314", "role": "scientist", "session": "5fa4f08b-650a-44d6-b895-517834a4945d"}
- 2026-11-11T17:21:38+00:00 run_finished {"run": "T0314-scientist-20261111T080102-d51f", "status": "completed", "cost": 3.99635, "subtype": "success", "report": "structured_output"}
- 2026-11-11T17:54:05+00:00 verified {"task": "T0314"}
- 2026-11-11T17:54:11+00:00 run_started {"run": "T0315-critic-20261111T095411-1156", "task": "T0315", "role": "critic", "session": "a7c7e73e-b67a-4947-8ba0-1b02a6d99ef6"}
- 2026-11-11T17:54:46+00:00 sleep_detected {"gap_s": 1991, "runs_extended": 1}
- 2026-11-11T18:24:53+00:00 run_finished {"run": "T0315-critic-20261111T095411-1156", "status": "completed", "cost": 2.191543, "subtype": "success", "report": "structured_output"}
- 2026-11-11T18:24:59+00:00 inbox_opened {"id": "I0173", "kind": "protected_change", "subject": "T0314: merge needs founder approval"}
