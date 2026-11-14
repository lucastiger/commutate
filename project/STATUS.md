# ModuleForge status
_generated 2026-11-14T01:20:40+00:00 from repository state — do not edit_

## Founder inbox (11 open)
- **I0165** [experiment_registration] register E008 (pre-registration)
- **I0167** [experiment_registration] register E008 (pre-registration)
- **I0169** [experiment_registration] register E008 (pre-registration)
- **I0171** [experiment_registration] register E008 (pre-registration)
- **I0175** [experiment_registration] register E008 (pre-registration)
- **I0177** [experiment_registration] register E008 (pre-registration)
- **I0179** [experiment_registration] register E008 (pre-registration)
- **I0181** [experiment_registration] register E008 (pre-registration)
- **I0185** [plan_approval] [O003] approve initial plan (1 tasks)
- **I0187** [experiment_registration] register E008 (pre-registration)
- **I0189** [experiment_registration] register E008 (pre-registration)

## Objectives
| id | status | verdict | evals | spent | title |
|---|---|---|---|---|---|
| O000 | passed | PASS | 1/2 | $0.50/$20 | Framework canary — the loop carries a known-answer hypothesis from plan to verdict |
| O001 | passed | PASS | 1/3 | $287.86/$315 | L1 PEEC ranks half-bridge layouts faithfully enough to drive layout search |
| O002 | draft | - | 0/1 | $11.44/$120 | A fast L1 thermal model predicts per-die Tj max, spread and layout-to-layout differences well enough to drive search |
| O003 | active | - | 0/1 | $218.99/$250 | Reference wire-bonded half-bridge layouts leave >= 20 % loop-inductance headroom inside their own housing at <= +2 K Tj |
| O004 | draft | - | 0/1 | $9.51/$100 | The L2 inductance reference is accurate on reconstructed public modules, so it can judge O003's headroom |
| O005 | draft | - | 0/2 | $7.65/$60 | L1 picks near-best layouts within a fixed family and die count, the regime derivative re-layout searches |
| O006 | active | INCONCLUSIVE | 1/1 | $137.91/$140 | The thermal L2 reference matches converged analytic solutions and an independent FEM, and design pilots measure what O002-O004 must fix |
| O007 | passed | PASS | 1/1 | $92.55/$110 | The scikit-fem thermal reference matches converged analytic solutions and the in-house finite-volume L2 on generator layouts |
| O901 | passed | PASS | 1/2 | $9.19/$30 | Infrastructure canary v2 - a known answer through registered, sealed, recomputed and null-checked evidence |

## Usage (from run records)
| objective | runs | usd | output tokens | thinking | denials | limit hits |
|---|---|---|---|---|---|---|
| O002 | 6 | $11.44 | 293351 | 180601 | 28 | 0 |
| O003 | 112 | $218.99 | 3510317 | 1745371 | 209 | 0 |
| O004 | 6 | $9.51 | 225161 | 160260 | 17 | 0 |
| O005 | 4 | $7.65 | 185443 | 108670 | 29 | 0 |
| O006 | 69 | $137.91 | 2633380 | 1435121 | 137 | 0 |
| O007 | 50 | $92.55 | 1684141 | 838123 | 79 | 1 |
| O901 | 3 | $5.05 | 101607 | 52842 | 14 | 0 |

## Tasks
cancelled: 39, done: 288, failed: 3, proposed: 1

- T0329 `proposed` none/experiment: Run E008: module-level loop-inductance headroom at <= +2 K Tj on D0019's public reference set (2D_Case_2R, 2D_Case_6) (attempt 0)

## Recent events
- 2026-11-13T19:08:07+00:00 founder_decision_noted {"decision": "E008 registration readings (founder, 2026-11-13, D0020): band check = Case 4's 4 pairs + gen2_0's search estimate (I0184 option 1); row-contract i
- 2026-11-13T19:08:07+00:00 inbox_resolved {"id": "I0183", "status": "approved", "note": "Done 2026-11-13: burst_tj_osc.sh ran (15/15 solves ok, V0 reproduces the dev run). Result H3: the hot spot moves 
- 2026-11-13T19:08:08+00:00 inbox_resolved {"id": "I0184", "status": "approved", "note": "Option 1 (founder, D0020): Case 4's 4 pairs (max e_R 0.01785) plus gen2_0's search estimate (~0.019) are the band
- 2026-11-13T19:09:02+00:00 task_added {"task": "T0330", "reason": "founder 2026-11-13 (D0020): declared expected outcome, reported die-average Tj, registration readings"}
- 2026-11-13T19:09:29+00:00 run_started {"run": "T0330-scientist-20261113T110929-62a1", "task": "T0330", "role": "scientist", "session": "dfb7ee55-98a1-483a-9f49-c369deb78256"}
- 2026-11-13T19:48:17+00:00 run_finished {"run": "T0330-scientist-20261113T110929-62a1", "status": "completed", "cost": 4.308172, "subtype": "success", "report": "structured_output"}
- 2026-11-13T20:05:01+00:00 verified {"task": "T0330"}
- 2026-11-13T20:05:10+00:00 run_started {"run": "T0331-critic-20261113T120510-5f57", "task": "T0331", "role": "critic", "session": "4bfb8b2e-ec62-45cc-b249-9796366a339d"}
- 2026-11-13T20:05:45+00:00 sleep_detected {"gap_s": 1049, "runs_extended": 1}
- 2026-11-13T20:27:22+00:00 run_finished {"run": "T0331-critic-20261113T120510-5f57", "status": "completed", "cost": 2.016545, "subtype": "success", "report": "structured_output"}
- 2026-11-13T20:27:27+00:00 inbox_opened {"id": "I0188", "kind": "protected_change", "subject": "T0330: merge needs founder approval"}
- 2026-11-13T20:53:08+00:00 inbox_resolved {"id": "I0188", "status": "approved", "note": "Merge T0330 (D0020 follow-up: expected outcome declared, reported die-average Tj, registration readings settled).
- 2026-11-13T20:53:30+00:00 merged {"task": "T0330"}
- 2026-11-13T20:53:30+00:00 inbox_opened {"id": "I0189", "kind": "experiment_registration", "subject": "register E008 (pre-registration)"}
- 2026-11-14T01:16:47+00:00 sleep_detected {"gap_s": 7240, "runs_extended": 0}
