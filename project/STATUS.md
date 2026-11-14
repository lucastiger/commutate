# ModuleForge status
_generated 2026-11-14T17:55:37+00:00 from repository state — do not edit_

## Founder inbox (8 open)
- **I0165** [experiment_registration] register E008 (pre-registration)
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
| O003 | active | - | 0/1 | $233.49/$250 | Reference wire-bonded half-bridge layouts leave >= 20 % loop-inductance headroom inside their own housing at <= +2 K Tj |
| O004 | draft | - | 0/1 | $9.51/$100 | The L2 inductance reference is accurate on reconstructed public modules, so it can judge O003's headroom |
| O005 | draft | - | 0/2 | $7.65/$60 | L1 picks near-best layouts within a fixed family and die count, the regime derivative re-layout searches |
| O006 | active | INCONCLUSIVE | 1/1 | $137.91/$140 | The thermal L2 reference matches converged analytic solutions and an independent FEM, and design pilots measure what O002-O004 must fix |
| O007 | passed | PASS | 1/1 | $92.55/$110 | The scikit-fem thermal reference matches converged analytic solutions and the in-house finite-volume L2 on generator layouts |
| O901 | passed | PASS | 1/2 | $9.19/$30 | Infrastructure canary v2 - a known answer through registered, sealed, recomputed and null-checked evidence |

## Usage (from run records)
| objective | runs | usd | output tokens | thinking | denials | limit hits |
|---|---|---|---|---|---|---|
| O002 | 6 | $11.44 | 293351 | 180601 | 28 | 0 |
| O003 | 118 | $233.49 | 3728844 | 1837230 | 243 | 0 |
| O004 | 6 | $9.51 | 225161 | 160260 | 17 | 0 |
| O005 | 4 | $7.65 | 185443 | 108670 | 29 | 0 |
| O006 | 69 | $137.91 | 2633380 | 1435121 | 137 | 0 |
| O007 | 50 | $92.55 | 1684141 | 838123 | 79 | 1 |
| O901 | 3 | $5.05 | 101607 | 52842 | 14 | 0 |

## Tasks
cancelled: 39, done: 294, failed: 3, proposed: 1

- T0329 `proposed` none/experiment: Run E008: module-level loop-inductance headroom at <= +2 K Tj on D0019's public reference set (2D_Case_2R, 2D_Case_6) (attempt 0)

## Recent events
- 2026-11-14T07:57:03+00:00 run_started {"run": "T0337-critic-20261113T235703-b76c", "task": "T0337", "role": "critic", "session": "15cab19d-5042-4768-9f17-cd024dee794c"}
- 2026-11-14T07:57:38+00:00 sleep_detected {"gap_s": 773, "runs_extended": 1}
- 2026-11-14T08:08:05+00:00 run_finished {"run": "T0337-critic-20261113T235703-b76c", "status": "completed", "cost": 1.32739, "subtype": "success", "report": "structured_output"}
- 2026-11-14T08:08:09+00:00 inbox_opened {"id": "I0194", "kind": "protected_change", "subject": "T0336: merge needs founder approval"}
- 2026-11-14T17:49:58+00:00 inbox_resolved {"id": "I0194", "status": "approved", "note": "Merge T0336 (code_under_test completed with the run's full src import closure). Review T0337 accept.", "by": "hum
- 2026-11-14T17:50:34+00:00 merged {"task": "T0336"}
- 2026-11-14T17:50:34+00:00 inbox_opened {"id": "I0195", "kind": "experiment_registration", "subject": "register E008 (pre-registration)"}
- 2026-11-14T17:55:12+00:00 experiment_registered {"id": "E008", "hash": "sha256:206af2d225679693ac78e904a898f0a9107db03912e431cdefb525a0268e3f6b", "by": "founder"}
- 2026-11-14T17:55:12+00:00 inbox_resolved {"id": "I0195", "status": "approved", "note": "Register E008 per D0020 (spec after T0332/T0334/T0336; local smoke on merged main: die-average columns and h_lo_v
- 2026-11-14T17:55:27+00:00 inbox_resolved {"id": "I0167", "status": "rejected", "note": "superseded by I0195 (D0020 item 5)", "by": "human"}
- 2026-11-14T17:55:30+00:00 inbox_resolved {"id": "I0169", "status": "rejected", "note": "superseded by I0195 (D0020 item 5)", "by": "human"}
- 2026-11-14T17:55:32+00:00 inbox_resolved {"id": "I0171", "status": "rejected", "note": "superseded by I0195 (D0020 item 5)", "by": "human"}
- 2026-11-14T17:55:35+00:00 inbox_resolved {"id": "I0175", "status": "rejected", "note": "superseded by I0195 (D0020 item 5)", "by": "human"}
- 2026-11-14T17:55:36+00:00 inbox_resolved {"id": "I0177", "status": "rejected", "note": "superseded by I0195 (D0020 item 5)", "by": "human"}
- 2026-11-14T17:55:38+00:00 inbox_resolved {"id": "I0179", "status": "rejected", "note": "superseded by I0195 (D0020 item 5)", "by": "human"}
