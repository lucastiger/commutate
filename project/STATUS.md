# ModuleForge status
_generated 2026-11-13T19:08:12+00:00 from repository state — do not edit_

## Founder inbox (10 open)
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

## Objectives
| id | status | verdict | evals | spent | title |
|---|---|---|---|---|---|
| O000 | passed | PASS | 1/2 | $0.50/$20 | Framework canary — the loop carries a known-answer hypothesis from plan to verdict |
| O001 | passed | PASS | 1/3 | $287.86/$315 | L1 PEEC ranks half-bridge layouts faithfully enough to drive layout search |
| O002 | draft | - | 0/1 | $11.44/$120 | A fast L1 thermal model predicts per-die Tj max, spread and layout-to-layout differences well enough to drive search |
| O003 | active | - | 0/1 | $212.66/$250 | Reference wire-bonded half-bridge layouts leave >= 20 % loop-inductance headroom inside their own housing at <= +2 K Tj |
| O004 | draft | - | 0/1 | $9.51/$100 | The L2 inductance reference is accurate on reconstructed public modules, so it can judge O003's headroom |
| O005 | draft | - | 0/2 | $7.65/$60 | L1 picks near-best layouts within a fixed family and die count, the regime derivative re-layout searches |
| O006 | active | INCONCLUSIVE | 1/1 | $137.91/$140 | The thermal L2 reference matches converged analytic solutions and an independent FEM, and design pilots measure what O002-O004 must fix |
| O007 | passed | PASS | 1/1 | $92.55/$110 | The scikit-fem thermal reference matches converged analytic solutions and the in-house finite-volume L2 on generator layouts |
| O901 | passed | PASS | 1/2 | $9.19/$30 | Infrastructure canary v2 - a known answer through registered, sealed, recomputed and null-checked evidence |

## Usage (from run records)
| objective | runs | usd | output tokens | thinking | denials | limit hits |
|---|---|---|---|---|---|---|
| O002 | 6 | $11.44 | 293351 | 180601 | 28 | 0 |
| O003 | 110 | $212.66 | 3413882 | 1707357 | 202 | 0 |
| O004 | 6 | $9.51 | 225161 | 160260 | 17 | 0 |
| O005 | 4 | $7.65 | 185443 | 108670 | 29 | 0 |
| O006 | 69 | $137.91 | 2633380 | 1435121 | 137 | 0 |
| O007 | 50 | $92.55 | 1684141 | 838123 | 79 | 1 |
| O901 | 3 | $5.05 | 101607 | 52842 | 14 | 0 |

## Tasks
cancelled: 39, done: 286, failed: 3, proposed: 1

- T0329 `proposed` none/experiment: Run E008: module-level loop-inductance headroom at <= +2 K Tj on D0019's public reference set (2D_Case_2R, 2D_Case_6) (attempt 0)

## Recent events
- 2026-11-13T18:06:51+00:00 run_finished {"run": "T0328-planner-20261113T100341-e9c1", "status": "completed", "cost": 1.08921, "subtype": "success", "report": "structured_output"}
- 2026-11-13T18:06:52+00:00 inbox_opened {"id": "I0183", "kind": "external_action", "subject": "[O003] [O003] Run T0325's level-2 launcher (burst_tj_osc.sh) and decide Tj attainability before registeri
- 2026-11-13T18:06:52+00:00 inbox_opened {"id": "I0184", "kind": "decision", "subject": "[O003] [O003] E008 pre-registration: band check with gen2_0's pairs unsolved, the non-levelled dev search, and w
- 2026-11-13T18:06:52+00:00 inbox_opened {"id": "I0185", "kind": "plan_approval", "subject": "[O003] approve initial plan (1 tasks)"}
- 2026-11-13T18:06:52+00:00 plan_applied {"objective": "O003", "created": ["T0329"], "dropped": 0}
- 2026-11-13T18:14:06+00:00 run_finished {"run": "T0327-critic-20261113T095910-e39b", "status": "completed", "cost": 2.387313, "subtype": "success", "report": "structured_output"}
- 2026-11-13T18:20:08+00:00 inbox_opened {"id": "I0186", "kind": "protected_change", "subject": "T0324: merge needs founder approval"}
- 2026-11-13T18:20:45+00:00 sleep_detected {"gap_s": 400, "runs_extended": 0}
- 2026-11-13T18:36:34+00:00 inbox_resolved {"id": "I0186", "status": "approved", "note": "Merge T0324 (dev-run crash fix, dev rows replayed, T0323 fixes).", "by": "human"}
- 2026-11-13T18:37:07+00:00 merged {"task": "T0324"}
- 2026-11-13T18:37:07+00:00 inbox_opened {"id": "I0187", "kind": "experiment_registration", "subject": "register E008 (pre-registration)"}
- 2026-11-13T19:08:07+00:00 founder_decision_noted {"decision": "E008 Tj attainability (founder, 2026-11-13, D0020): register E008 with the frozen Tj definition. T0325's level-2 VM run found H3 (hot spot moves o
- 2026-11-13T19:08:07+00:00 founder_decision_noted {"decision": "E008 registration readings (founder, 2026-11-13, D0020): band check = Case 4's 4 pairs + gen2_0's search estimate (I0184 option 1); row-contract i
- 2026-11-13T19:08:07+00:00 inbox_resolved {"id": "I0183", "status": "approved", "note": "Done 2026-11-13: burst_tj_osc.sh ran (15/15 solves ok, V0 reproduces the dev run). Result H3: the hot spot moves 
- 2026-11-13T19:08:08+00:00 inbox_resolved {"id": "I0184", "status": "approved", "note": "Option 1 (founder, D0020): Case 4's 4 pairs (max e_R 0.01785) plus gen2_0's search estimate (~0.019) are the band
