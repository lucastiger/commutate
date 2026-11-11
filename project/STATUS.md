# ModuleForge status
_generated 2026-11-11T05:16:03+00:00 from repository state — do not edit_

## Founder inbox (5 open)
- **I0140** [question] [O003] Reference set on 2026-11-12 (D0010): customer layouts or public fallback
- **I0165** [experiment_registration] register E008 (pre-registration)
- **I0167** [experiment_registration] register E008 (pre-registration)
- **I0169** [experiment_registration] register E008 (pre-registration)
- **I0170** [protected_change] T0311: merge needs founder approval

## Objectives
| id | status | verdict | evals | spent | title |
|---|---|---|---|---|---|
| O000 | passed | PASS | 1/2 | $0.50/$20 | Framework canary — the loop carries a known-answer hypothesis from plan to verdict |
| O001 | passed | PASS | 1/3 | $287.86/$315 | L1 PEEC ranks half-bridge layouts faithfully enough to drive layout search |
| O002 | draft | - | 0/1 | $11.44/$120 | A fast L1 thermal model predicts per-die Tj max, spread and layout-to-layout differences well enough to drive search |
| O003 | active | - | 0/1 | $154.86/$250 | Reference wire-bonded half-bridge layouts leave >= 20 % loop-inductance headroom inside their own housing at <= +2 K Tj |
| O004 | draft | - | 0/1 | $9.51/$100 | The L2 inductance reference is accurate on reconstructed public modules, so it can judge O003's headroom |
| O005 | draft | - | 0/2 | $7.65/$60 | L1 picks near-best layouts within a fixed family and die count, the regime derivative re-layout searches |
| O006 | active | INCONCLUSIVE | 1/1 | $137.91/$140 | The thermal L2 reference matches converged analytic solutions and an independent FEM, and design pilots measure what O002-O004 must fix |
| O007 | passed | PASS | 1/1 | $92.55/$110 | The scikit-fem thermal reference matches converged analytic solutions and the in-house finite-volume L2 on generator layouts |
| O901 | passed | PASS | 1/2 | $9.19/$30 | Infrastructure canary v2 - a known answer through registered, sealed, recomputed and null-checked evidence |

## Usage (from run records)
| objective | runs | usd | output tokens | thinking | denials | limit hits |
|---|---|---|---|---|---|---|
| O002 | 6 | $11.44 | 293351 | 180601 | 28 | 0 |
| O003 | 92 | $154.86 | 2537664 | 1301370 | 135 | 0 |
| O004 | 6 | $9.51 | 225161 | 160260 | 17 | 0 |
| O005 | 4 | $7.65 | 185443 | 108670 | 29 | 0 |
| O006 | 69 | $137.91 | 2633380 | 1435121 | 137 | 0 |
| O007 | 50 | $92.55 | 1684141 | 838123 | 79 | 1 |
| O901 | 3 | $5.05 | 101607 | 52842 | 14 | 0 |

## Tasks
cancelled: 39, done: 268, failed: 3, needs_founder: 1, todo: 1

- T0311 `needs_founder` scientist/design_experiment: E008 runner: stack-type signature rounding, selftest gaps, F6(e) reading for the founder (review T0310) (attempt 1)

## Recent events
- 2026-11-11T04:20:02+00:00 sleep_detected {"gap_s": 714, "runs_extended": 1}
- 2026-11-11T04:27:04+00:00 run_finished {"run": "T0310-critic-20261110T201928-8048", "status": "completed", "cost": 2.192312, "subtype": "success", "report": "structured_output"}
- 2026-11-11T04:27:08+00:00 inbox_opened {"id": "I0168", "kind": "protected_change", "subject": "T0309: merge needs founder approval"}
- 2026-11-11T04:27:42+00:00 task_added {"task": "T0311", "reason": "review T0310 follow-up (stack-type rounding, before T0263)"}
- 2026-11-11T04:27:42+00:00 task_amended {"task": "T0263", "reason": "waits for T0311 (stack-type signature rounding from review T0310) so F6(e) is settled before F3"}
- 2026-11-11T04:33:00+00:00 inbox_resolved {"id": "I0168", "status": "approved", "note": "Merge the E008 runner fixes from reviews T0307/T0308. Critic T0310 accepts with caveats; its findings go to T0311
- 2026-11-11T04:33:19+00:00 merged {"task": "T0309"}
- 2026-11-11T04:33:19+00:00 inbox_opened {"id": "I0169", "kind": "experiment_registration", "subject": "register E008 (pre-registration)"}
- 2026-11-11T04:33:23+00:00 run_started {"run": "T0311-scientist-20261110T203323-e8b3", "task": "T0311", "role": "scientist", "session": "5ec62158-c0d6-4052-aea1-b79464859e29"}
- 2026-11-11T04:57:48+00:00 run_finished {"run": "T0311-scientist-20261110T203323-e8b3", "status": "completed", "cost": 2.019112, "subtype": "success", "report": "structured_output"}
- 2026-11-11T05:08:46+00:00 verified {"task": "T0311"}
- 2026-11-11T05:08:52+00:00 run_started {"run": "T0312-critic-20261110T210852-0ba9", "task": "T0312", "role": "critic", "session": "ba45f8e8-f8a8-4c10-a3da-11890d3cbb46"}
- 2026-11-11T05:09:26+00:00 sleep_detected {"gap_s": 718, "runs_extended": 1}
- 2026-11-11T05:15:56+00:00 run_finished {"run": "T0312-critic-20261110T210852-0ba9", "status": "completed", "cost": 2.578585, "subtype": "success", "report": "structured_output"}
- 2026-11-11T05:16:00+00:00 inbox_opened {"id": "I0170", "kind": "protected_change", "subject": "T0311: merge needs founder approval"}
