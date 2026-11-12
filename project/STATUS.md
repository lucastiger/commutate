# ModuleForge status
_generated 2026-11-12T16:46:36+00:00 from repository state — do not edit_

## Founder inbox (6 open)
- **I0165** [experiment_registration] register E008 (pre-registration)
- **I0167** [experiment_registration] register E008 (pre-registration)
- **I0169** [experiment_registration] register E008 (pre-registration)
- **I0171** [experiment_registration] register E008 (pre-registration)
- **I0175** [experiment_registration] register E008 (pre-registration)
- **I0177** [experiment_registration] register E008 (pre-registration)

## Objectives
| id | status | verdict | evals | spent | title |
|---|---|---|---|---|---|
| O000 | passed | PASS | 1/2 | $0.50/$20 | Framework canary — the loop carries a known-answer hypothesis from plan to verdict |
| O001 | passed | PASS | 1/3 | $287.86/$315 | L1 PEEC ranks half-bridge layouts faithfully enough to drive layout search |
| O002 | draft | - | 0/1 | $11.44/$120 | A fast L1 thermal model predicts per-die Tj max, spread and layout-to-layout differences well enough to drive search |
| O003 | active | - | 0/1 | $180.80/$250 | Reference wire-bonded half-bridge layouts leave >= 20 % loop-inductance headroom inside their own housing at <= +2 K Tj |
| O004 | draft | - | 0/1 | $9.51/$100 | The L2 inductance reference is accurate on reconstructed public modules, so it can judge O003's headroom |
| O005 | draft | - | 0/2 | $7.65/$60 | L1 picks near-best layouts within a fixed family and die count, the regime derivative re-layout searches |
| O006 | active | INCONCLUSIVE | 1/1 | $137.91/$140 | The thermal L2 reference matches converged analytic solutions and an independent FEM, and design pilots measure what O002-O004 must fix |
| O007 | passed | PASS | 1/1 | $92.55/$110 | The scikit-fem thermal reference matches converged analytic solutions and the in-house finite-volume L2 on generator layouts |
| O901 | passed | PASS | 1/2 | $9.19/$30 | Infrastructure canary v2 - a known answer through registered, sealed, recomputed and null-checked evidence |

## Usage (from run records)
| objective | runs | usd | output tokens | thinking | denials | limit hits |
|---|---|---|---|---|---|---|
| O002 | 6 | $11.44 | 293351 | 180601 | 28 | 0 |
| O003 | 100 | $180.80 | 2932630 | 1488713 | 156 | 0 |
| O004 | 6 | $9.51 | 225161 | 160260 | 17 | 0 |
| O005 | 4 | $7.65 | 185443 | 108670 | 29 | 0 |
| O006 | 69 | $137.91 | 2633380 | 1435121 | 137 | 0 |
| O007 | 50 | $92.55 | 1684141 | 838123 | 79 | 1 |
| O901 | 3 | $5.05 | 101607 | 52842 | 14 | 0 |

## Tasks
cancelled: 39, done: 277, failed: 3


## Recent events
- 2026-11-12T04:39:45+00:00 inbox_opened {"id": "I0175", "kind": "experiment_registration", "subject": "register E008 (pre-registration)"}
- 2026-11-12T04:39:49+00:00 run_started {"run": "T0317-scientist-20261111T203949-e320", "task": "T0317", "role": "scientist", "session": "1028ac29-25c8-472a-83cf-40fc4ad51543"}
- 2026-11-12T05:14:16+00:00 run_finished {"run": "T0317-scientist-20261111T203949-e320", "status": "completed", "cost": 3.779634, "subtype": "success", "report": "structured_output"}
- 2026-11-12T05:26:22+00:00 verified {"task": "T0317"}
- 2026-11-12T05:26:28+00:00 run_started {"run": "T0319-critic-20261111T212628-8b9c", "task": "T0319", "role": "critic", "session": "e4c54619-6661-4a1f-8871-59d4ec2a33fc"}
- 2026-11-12T05:27:03+00:00 sleep_detected {"gap_s": 768, "runs_extended": 1}
- 2026-11-12T05:34:44+00:00 run_finished {"run": "T0319-critic-20261111T212628-8b9c", "status": "completed", "cost": 2.333704, "subtype": "success", "report": "structured_output"}
- 2026-11-12T05:34:48+00:00 inbox_opened {"id": "I0176", "kind": "protected_change", "subject": "T0317: merge needs founder approval"}
- 2026-11-12T15:13:18+00:00 sleep_detected {"gap_s": 1392, "runs_extended": 0}
- 2026-11-12T15:23:27+00:00 inbox_resolved {"id": "I0176", "status": "approved", "note": "Merge T0317 (D0018 item 1: no minimum gate-wire length in E008's per-reference rules; solver failures in D's band
- 2026-11-12T15:24:06+00:00 merged {"task": "T0317"}
- 2026-11-12T15:24:06+00:00 inbox_opened {"id": "I0177", "kind": "experiment_registration", "subject": "register E008 (pre-registration)"}
- 2026-11-12T15:53:02+00:00 sleep_detected {"gap_s": 1394, "runs_extended": 0}
- 2026-11-12T16:28:20+00:00 sleep_detected {"gap_s": 1722, "runs_extended": 0}
- 2026-11-12T16:46:29+00:00 sleep_detected {"gap_s": 836, "runs_extended": 0}
