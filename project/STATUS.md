# ModuleForge status
_generated 2026-11-11T06:55:42+00:00 from repository state — do not edit_

## Founder inbox (5 open)
- **I0140** [question] [O003] Reference set on 2026-11-12 (D0010): customer layouts or public fallback
- **I0165** [experiment_registration] register E008 (pre-registration)
- **I0167** [experiment_registration] register E008 (pre-registration)
- **I0169** [experiment_registration] register E008 (pre-registration)
- **I0171** [experiment_registration] register E008 (pre-registration)

## Objectives
| id | status | verdict | evals | spent | title |
|---|---|---|---|---|---|
| O000 | passed | PASS | 1/2 | $0.50/$20 | Framework canary — the loop carries a known-answer hypothesis from plan to verdict |
| O001 | passed | PASS | 1/3 | $287.86/$315 | L1 PEEC ranks half-bridge layouts faithfully enough to drive layout search |
| O002 | draft | - | 0/1 | $11.44/$120 | A fast L1 thermal model predicts per-die Tj max, spread and layout-to-layout differences well enough to drive search |
| O003 | active | - | 0/1 | $158.57/$250 | Reference wire-bonded half-bridge layouts leave >= 20 % loop-inductance headroom inside their own housing at <= +2 K Tj |
| O004 | draft | - | 0/1 | $9.51/$100 | The L2 inductance reference is accurate on reconstructed public modules, so it can judge O003's headroom |
| O005 | draft | - | 0/2 | $7.65/$60 | L1 picks near-best layouts within a fixed family and die count, the regime derivative re-layout searches |
| O006 | active | INCONCLUSIVE | 1/1 | $137.91/$140 | The thermal L2 reference matches converged analytic solutions and an independent FEM, and design pilots measure what O002-O004 must fix |
| O007 | passed | PASS | 1/1 | $92.55/$110 | The scikit-fem thermal reference matches converged analytic solutions and the in-house finite-volume L2 on generator layouts |
| O901 | passed | PASS | 1/2 | $9.19/$30 | Infrastructure canary v2 - a known answer through registered, sealed, recomputed and null-checked evidence |

## Usage (from run records)
| objective | runs | usd | output tokens | thinking | denials | limit hits |
|---|---|---|---|---|---|---|
| O002 | 6 | $11.44 | 293351 | 180601 | 28 | 0 |
| O003 | 94 | $158.57 | 2611153 | 1336767 | 135 | 0 |
| O004 | 6 | $9.51 | 225161 | 160260 | 17 | 0 |
| O005 | 4 | $7.65 | 185443 | 108670 | 29 | 0 |
| O006 | 69 | $137.91 | 2633380 | 1435121 | 137 | 0 |
| O007 | 50 | $92.55 | 1684141 | 838123 | 79 | 1 |
| O901 | 3 | $5.05 | 101607 | 52842 | 14 | 0 |

## Tasks
cancelled: 39, done: 269, failed: 3, review: 1, running: 1

- T0263 `review` scientist/research: Frozen reconstructions of PowerSynth 2D_Case_2R and 2D_Case_6 (D0010 public fallback), snapped, with measured rules (attempt 1)
- T0313 `running` critic/review: Review T0263 (general) (attempt 1)

## Recent events
- 2026-11-11T04:33:23+00:00 run_started {"run": "T0311-scientist-20261110T203323-e8b3", "task": "T0311", "role": "scientist", "session": "5ec62158-c0d6-4052-aea1-b79464859e29"}
- 2026-11-11T04:57:48+00:00 run_finished {"run": "T0311-scientist-20261110T203323-e8b3", "status": "completed", "cost": 2.019112, "subtype": "success", "report": "structured_output"}
- 2026-11-11T05:08:46+00:00 verified {"task": "T0311"}
- 2026-11-11T05:08:52+00:00 run_started {"run": "T0312-critic-20261110T210852-0ba9", "task": "T0312", "role": "critic", "session": "ba45f8e8-f8a8-4c10-a3da-11890d3cbb46"}
- 2026-11-11T05:09:26+00:00 sleep_detected {"gap_s": 718, "runs_extended": 1}
- 2026-11-11T05:15:56+00:00 run_finished {"run": "T0312-critic-20261110T210852-0ba9", "status": "completed", "cost": 2.578585, "subtype": "success", "report": "structured_output"}
- 2026-11-11T05:16:00+00:00 inbox_opened {"id": "I0170", "kind": "protected_change", "subject": "T0311: merge needs founder approval"}
- 2026-11-11T06:23:00+00:00 inbox_resolved {"id": "I0170", "status": "approved", "note": "Merge the stack-type rounding fix (review T0310). Critic T0312 accepts with caveats; test-only items go to the fu
- 2026-11-11T06:23:08+00:00 merged {"task": "T0311"}
- 2026-11-11T06:23:08+00:00 inbox_opened {"id": "I0171", "kind": "experiment_registration", "subject": "register E008 (pre-registration)"}
- 2026-11-11T06:23:12+00:00 run_started {"run": "T0263-scientist-20261110T222312-321c", "task": "T0263", "role": "scientist", "session": "15fc6073-a969-4362-9054-0f93db2ec6ac"}
- 2026-11-11T06:49:35+00:00 run_finished {"run": "T0263-scientist-20261110T222312-321c", "status": "completed", "cost": 3.70223, "subtype": "success", "report": "structured_output"}
- 2026-11-11T06:54:58+00:00 verified {"task": "T0263"}
- 2026-11-11T06:55:03+00:00 run_started {"run": "T0313-critic-20261110T225503-2965", "task": "T0313", "role": "critic", "session": "3befbdf5-572d-45d9-89e6-6b7bf046a6b8"}
- 2026-11-11T06:55:37+00:00 sleep_detected {"gap_s": 364, "runs_extended": 1}
