# ModuleForge status
_generated 2026-11-12T05:34:51+00:00 from repository state — do not edit_

## Founder inbox (6 open)
- **I0165** [experiment_registration] register E008 (pre-registration)
- **I0167** [experiment_registration] register E008 (pre-registration)
- **I0169** [experiment_registration] register E008 (pre-registration)
- **I0171** [experiment_registration] register E008 (pre-registration)
- **I0175** [experiment_registration] register E008 (pre-registration)
- **I0176** [protected_change] T0317: merge needs founder approval

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
cancelled: 39, done: 276, failed: 3, needs_founder: 1

- T0317 `needs_founder` scientist/design_experiment: E008: drop the measured minimum gate-wire length from per-reference rules (founder fix list, D0018 item 1) (attempt 1)

## Recent events
- 2026-11-12T04:26:23+00:00 run_started {"run": "T0318-critic-20261111T202623-2491", "task": "T0318", "role": "critic", "session": "ab78161a-0b10-47d6-99ee-1eee2b048dc7"}
- 2026-11-12T04:26:57+00:00 sleep_detected {"gap_s": 694, "runs_extended": 1}
- 2026-11-12T04:38:22+00:00 run_finished {"run": "T0318-critic-20261111T202623-2491", "status": "completed", "cost": 2.45103, "subtype": "success", "report": "structured_output"}
- 2026-11-12T04:38:26+00:00 inbox_opened {"id": "I0174", "kind": "protected_change", "subject": "T0316: merge needs founder approval"}
- 2026-11-12T04:38:45+00:00 task_amended {"task": "T0317", "reason": "adds review T0318 follow-ups (solver failure != exclusion; selftest gaps) before T0317 starts"}
- 2026-11-12T04:39:26+00:00 inbox_resolved {"id": "I0174", "status": "approved", "note": "Merge T0316 (D0018 in E008: degraded copy as yardstick with a 1.5 mm floor, exclusion fallback). Review T0318 acc
- 2026-11-12T04:39:45+00:00 merged {"task": "T0316"}
- 2026-11-12T04:39:45+00:00 inbox_opened {"id": "I0175", "kind": "experiment_registration", "subject": "register E008 (pre-registration)"}
- 2026-11-12T04:39:49+00:00 run_started {"run": "T0317-scientist-20261111T203949-e320", "task": "T0317", "role": "scientist", "session": "1028ac29-25c8-472a-83cf-40fc4ad51543"}
- 2026-11-12T05:14:16+00:00 run_finished {"run": "T0317-scientist-20261111T203949-e320", "status": "completed", "cost": 3.779634, "subtype": "success", "report": "structured_output"}
- 2026-11-12T05:26:22+00:00 verified {"task": "T0317"}
- 2026-11-12T05:26:28+00:00 run_started {"run": "T0319-critic-20261111T212628-8b9c", "task": "T0319", "role": "critic", "session": "e4c54619-6661-4a1f-8871-59d4ec2a33fc"}
- 2026-11-12T05:27:03+00:00 sleep_detected {"gap_s": 768, "runs_extended": 1}
- 2026-11-12T05:34:44+00:00 run_finished {"run": "T0319-critic-20261111T212628-8b9c", "status": "completed", "cost": 2.333704, "subtype": "success", "report": "structured_output"}
- 2026-11-12T05:34:48+00:00 inbox_opened {"id": "I0176", "kind": "protected_change", "subject": "T0317: merge needs founder approval"}
