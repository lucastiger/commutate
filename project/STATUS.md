# ModuleForge status
_generated 2026-11-14T07:57:44+00:00 from repository state — do not edit_

## Founder inbox (13 open)
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
- **I0191** [experiment_registration] register E008 (pre-registration)
- **I0193** [experiment_registration] register E008 (pre-registration)

## Objectives
| id | status | verdict | evals | spent | title |
|---|---|---|---|---|---|
| O000 | passed | PASS | 1/2 | $0.50/$20 | Framework canary — the loop carries a known-answer hypothesis from plan to verdict |
| O001 | passed | PASS | 1/3 | $287.86/$315 | L1 PEEC ranks half-bridge layouts faithfully enough to drive layout search |
| O002 | draft | - | 0/1 | $11.44/$120 | A fast L1 thermal model predicts per-die Tj max, spread and layout-to-layout differences well enough to drive search |
| O003 | active | - | 0/1 | $232.16/$250 | Reference wire-bonded half-bridge layouts leave >= 20 % loop-inductance headroom inside their own housing at <= +2 K Tj |
| O004 | draft | - | 0/1 | $9.51/$100 | The L2 inductance reference is accurate on reconstructed public modules, so it can judge O003's headroom |
| O005 | draft | - | 0/2 | $7.65/$60 | L1 picks near-best layouts within a fixed family and die count, the regime derivative re-layout searches |
| O006 | active | INCONCLUSIVE | 1/1 | $137.91/$140 | The thermal L2 reference matches converged analytic solutions and an independent FEM, and design pilots measure what O002-O004 must fix |
| O007 | passed | PASS | 1/1 | $92.55/$110 | The scikit-fem thermal reference matches converged analytic solutions and the in-house finite-volume L2 on generator layouts |
| O901 | passed | PASS | 1/2 | $9.19/$30 | Infrastructure canary v2 - a known answer through registered, sealed, recomputed and null-checked evidence |

## Usage (from run records)
| objective | runs | usd | output tokens | thinking | denials | limit hits |
|---|---|---|---|---|---|---|
| O002 | 6 | $11.44 | 293351 | 180601 | 28 | 0 |
| O003 | 118 | $232.16 | 3706065 | 1829878 | 232 | 0 |
| O004 | 6 | $9.51 | 225161 | 160260 | 17 | 0 |
| O005 | 4 | $7.65 | 185443 | 108670 | 29 | 0 |
| O006 | 69 | $137.91 | 2633380 | 1435121 | 137 | 0 |
| O007 | 50 | $92.55 | 1684141 | 838123 | 79 | 1 |
| O901 | 3 | $5.05 | 101607 | 52842 | 14 | 0 |

## Tasks
cancelled: 39, done: 292, failed: 3, proposed: 1, review: 1, running: 1

- T0329 `proposed` none/experiment: Run E008: module-level loop-inductance headroom at <= +2 K Tj on D0019's public reference set (2D_Case_2R, 2D_Case_6) (attempt 0)
- T0336 `review` scientist/design_experiment: E008: complete code_under_test with every src file the run imports (review T0335 finding 1) (attempt 1)
- T0337 `running` critic/review: Review T0336 (general) (attempt 1)

## Recent events
- 2026-11-14T06:06:30+00:00 run_finished {"run": "T0334-scientist-20261113T213207-4d37", "status": "completed", "cost": 3.07692, "subtype": "success", "report": "structured_output"}
- 2026-11-14T06:20:54+00:00 verified {"task": "T0334"}
- 2026-11-14T06:21:00+00:00 run_started {"run": "T0335-critic-20261113T222100-0e45", "task": "T0335", "role": "critic", "session": "9c473e6f-c148-433e-881c-5305d837faa8"}
- 2026-11-14T06:21:34+00:00 sleep_detected {"gap_s": 906, "runs_extended": 1}
- 2026-11-14T06:35:42+00:00 run_finished {"run": "T0335-critic-20261113T222100-0e45", "status": "completed", "cost": 2.056197, "subtype": "success", "report": "structured_output"}
- 2026-11-14T06:35:47+00:00 inbox_opened {"id": "I0192", "kind": "protected_change", "subject": "T0334: merge needs founder approval"}
- 2026-11-14T07:16:08+00:00 task_added {"task": "T0336", "reason": "founder 2026-11-13: complete E008 code_under_test before registration (T0335 finding 1)"}
- 2026-11-14T07:21:38+00:00 inbox_resolved {"id": "I0192", "status": "approved", "note": "Merge T0334 (registration blockers: gate-only dev rows get their own kinds; L1 code_under_test path). Review T033
- 2026-11-14T07:21:41+00:00 merged {"task": "T0334"}
- 2026-11-14T07:21:41+00:00 inbox_opened {"id": "I0193", "kind": "experiment_registration", "subject": "register E008 (pre-registration)"}
- 2026-11-14T07:21:45+00:00 run_started {"run": "T0336-scientist-20261113T232145-70ce", "task": "T0336", "role": "scientist", "session": "da153571-b0c1-4fb3-899b-f2e193803be4"}
- 2026-11-14T07:44:46+00:00 run_finished {"run": "T0336-scientist-20261113T232145-70ce", "status": "completed", "cost": 1.470621, "subtype": "success", "report": "structured_output"}
- 2026-11-14T07:56:56+00:00 verified {"task": "T0336"}
- 2026-11-14T07:57:03+00:00 run_started {"run": "T0337-critic-20261113T235703-b76c", "task": "T0337", "role": "critic", "session": "15cab19d-5042-4768-9f17-cd024dee794c"}
- 2026-11-14T07:57:38+00:00 sleep_detected {"gap_s": 773, "runs_extended": 1}
