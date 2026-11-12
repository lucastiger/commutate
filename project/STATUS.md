# ModuleForge status
_generated 2026-11-12T04:38:29+00:00 from repository state — do not edit_

## Founder inbox (5 open)
- **I0165** [experiment_registration] register E008 (pre-registration)
- **I0167** [experiment_registration] register E008 (pre-registration)
- **I0169** [experiment_registration] register E008 (pre-registration)
- **I0171** [experiment_registration] register E008 (pre-registration)
- **I0174** [protected_change] T0316: merge needs founder approval

## Objectives
| id | status | verdict | evals | spent | title |
|---|---|---|---|---|---|
| O000 | passed | PASS | 1/2 | $0.50/$20 | Framework canary — the loop carries a known-answer hypothesis from plan to verdict |
| O001 | passed | PASS | 1/3 | $287.86/$315 | L1 PEEC ranks half-bridge layouts faithfully enough to drive layout search |
| O002 | draft | - | 0/1 | $11.44/$120 | A fast L1 thermal model predicts per-die Tj max, spread and layout-to-layout differences well enough to drive search |
| O003 | active | - | 0/1 | $174.69/$250 | Reference wire-bonded half-bridge layouts leave >= 20 % loop-inductance headroom inside their own housing at <= +2 K Tj |
| O004 | draft | - | 0/1 | $9.51/$100 | The L2 inductance reference is accurate on reconstructed public modules, so it can judge O003's headroom |
| O005 | draft | - | 0/2 | $7.65/$60 | L1 picks near-best layouts within a fixed family and die count, the regime derivative re-layout searches |
| O006 | active | INCONCLUSIVE | 1/1 | $137.91/$140 | The thermal L2 reference matches converged analytic solutions and an independent FEM, and design pilots measure what O002-O004 must fix |
| O007 | passed | PASS | 1/1 | $92.55/$110 | The scikit-fem thermal reference matches converged analytic solutions and the in-house finite-volume L2 on generator layouts |
| O901 | passed | PASS | 1/2 | $9.19/$30 | Infrastructure canary v2 - a known answer through registered, sealed, recomputed and null-checked evidence |

## Usage (from run records)
| objective | runs | usd | output tokens | thinking | denials | limit hits |
|---|---|---|---|---|---|---|
| O002 | 6 | $11.44 | 293351 | 180601 | 28 | 0 |
| O003 | 98 | $174.69 | 2867459 | 1461684 | 155 | 0 |
| O004 | 6 | $9.51 | 225161 | 160260 | 17 | 0 |
| O005 | 4 | $7.65 | 185443 | 108670 | 29 | 0 |
| O006 | 69 | $137.91 | 2633380 | 1435121 | 137 | 0 |
| O007 | 50 | $92.55 | 1684141 | 838123 | 79 | 1 |
| O901 | 3 | $5.05 | 101607 | 52842 | 14 | 0 |

## Tasks
cancelled: 39, done: 274, failed: 3, needs_founder: 1, todo: 1

- T0316 `needs_founder` scientist/design_experiment: E008: degraded copy as a yardstick under a frozen power-width floor; exclusion when no valid D exists (founder decision D0018) (attempt 1)

## Recent events
- 2026-11-12T01:42:48+00:00 sleep_detected {"gap_s": 6806, "runs_extended": 0}
- 2026-11-12T02:21:32+00:00 sleep_detected {"gap_s": 1882, "runs_extended": 0}
- 2026-11-12T02:27:41+00:00 sleep_detected {"gap_s": 369, "runs_extended": 0}
- 2026-11-12T02:44:41+00:00 sleep_detected {"gap_s": 980, "runs_extended": 0}
- 2026-11-12T02:50:30+00:00 sleep_detected {"gap_s": 349, "runs_extended": 0}
- 2026-11-12T03:19:00+00:00 task_added {"task": "T0316", "reason": "founder decision 2026-11-12 (D0018): degraded copy as yardstick, exclusion fallback"}
- 2026-11-12T03:19:24+00:00 run_started {"run": "T0316-scientist-20261111T191924-cf93", "task": "T0316", "role": "scientist", "session": "0c028ff9-af16-4a5d-a62e-a75de873bc51"}
- 2026-11-12T03:22:50+00:00 founder_decision_noted {"subject": "O003/E008 model-fix list fixed before any reference screen", "note": "Founder confirmed in session: (1) drop E008 min_signal_wire_length (scope_in 
- 2026-11-12T03:23:18+00:00 task_added {"task": "T0317", "reason": "founder fix list 2026-11-12 (D0018 item 1): drop the measured gate-wire minimum"}
- 2026-11-12T04:15:24+00:00 run_finished {"run": "T0316-scientist-20261111T191924-cf93", "status": "completed", "cost": 5.447153, "subtype": "success", "report": "structured_output"}
- 2026-11-12T04:26:17+00:00 verified {"task": "T0316"}
- 2026-11-12T04:26:23+00:00 run_started {"run": "T0318-critic-20261111T202623-2491", "task": "T0318", "role": "critic", "session": "ab78161a-0b10-47d6-99ee-1eee2b048dc7"}
- 2026-11-12T04:26:57+00:00 sleep_detected {"gap_s": 694, "runs_extended": 1}
- 2026-11-12T04:38:22+00:00 run_finished {"run": "T0318-critic-20261111T202623-2491", "status": "completed", "cost": 2.45103, "subtype": "success", "report": "structured_output"}
- 2026-11-12T04:38:26+00:00 inbox_opened {"id": "I0174", "kind": "protected_change", "subject": "T0316: merge needs founder approval"}
