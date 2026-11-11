# ModuleForge status
_generated 2026-11-11T03:40:59+00:00 from repository state — do not edit_

## Founder inbox (3 open)
- **I0140** [question] [O003] Reference set on 2026-11-12 (D0010): customer layouts or public fallback
- **I0165** [experiment_registration] register E008 (pre-registration)
- **I0167** [experiment_registration] register E008 (pre-registration)

## Objectives
| id | status | verdict | evals | spent | title |
|---|---|---|---|---|---|
| O000 | passed | PASS | 1/2 | $0.50/$20 | Framework canary — the loop carries a known-answer hypothesis from plan to verdict |
| O001 | passed | PASS | 1/3 | $287.86/$315 | L1 PEEC ranks half-bridge layouts faithfully enough to drive layout search |
| O002 | draft | - | 0/1 | $11.44/$120 | A fast L1 thermal model predicts per-die Tj max, spread and layout-to-layout differences well enough to drive search |
| O003 | active | - | 0/1 | $144.16/$250 | Reference wire-bonded half-bridge layouts leave >= 20 % loop-inductance headroom inside their own housing at <= +2 K Tj |
| O004 | draft | - | 0/1 | $9.51/$100 | The L2 inductance reference is accurate on reconstructed public modules, so it can judge O003's headroom |
| O005 | draft | - | 0/2 | $7.65/$60 | L1 picks near-best layouts within a fixed family and die count, the regime derivative re-layout searches |
| O006 | active | INCONCLUSIVE | 1/1 | $137.91/$140 | The thermal L2 reference matches converged analytic solutions and an independent FEM, and design pilots measure what O002-O004 must fix |
| O007 | passed | PASS | 1/1 | $92.55/$110 | The scikit-fem thermal reference matches converged analytic solutions and the in-house finite-volume L2 on generator layouts |
| O901 | passed | PASS | 1/2 | $9.19/$30 | Infrastructure canary v2 - a known answer through registered, sealed, recomputed and null-checked evidence |

## Usage (from run records)
| objective | runs | usd | output tokens | thinking | denials | limit hits |
|---|---|---|---|---|---|---|
| O002 | 6 | $11.44 | 293351 | 180601 | 28 | 0 |
| O003 | 89 | $144.16 | 2400149 | 1249456 | 127 | 0 |
| O004 | 6 | $9.51 | 225161 | 160260 | 17 | 0 |
| O005 | 4 | $7.65 | 185443 | 108670 | 29 | 0 |
| O006 | 69 | $137.91 | 2633380 | 1435121 | 137 | 0 |
| O007 | 50 | $92.55 | 1684141 | 838123 | 79 | 1 |
| O901 | 3 | $5.05 | 101607 | 52842 | 14 | 0 |

## Tasks
cancelled: 39, done: 265, failed: 3, running: 1, todo: 1

- T0309 `running` scientist/design_experiment: E008 runner: admissible spot-check references, per-die thickness in stack type, NaN-safe F6(c) with FV Picard record, thermal-report selftest (reviews T0307, T0308) (attempt 1)

## Recent events
- 2026-11-11T02:07:22+00:00 run_finished {"run": "T0306-scientist-20261110T173058-c746", "status": "completed", "cost": 5.763118, "subtype": "success", "report": "structured_output"}
- 2026-11-11T02:18:59+00:00 verified {"task": "T0306"}
- 2026-11-11T02:19:06+00:00 run_started {"run": "T0307-critic-20261110T181906-2794", "task": "T0307", "role": "critic", "session": "66b158eb-59f7-46fd-8270-d330d489ac32"}
- 2026-11-11T02:19:07+00:00 run_started {"run": "T0308-critic-20261110T181907-65bc", "task": "T0308", "role": "critic", "session": "10028901-0f5c-4944-a53a-f51d62af7450"}
- 2026-11-11T02:19:42+00:00 sleep_detected {"gap_s": 742, "runs_extended": 2}
- 2026-11-11T02:32:05+00:00 run_finished {"run": "T0307-critic-20261110T181906-2794", "status": "completed", "cost": 2.330334, "subtype": "success", "report": "structured_output"}
- 2026-11-11T02:32:44+00:00 run_finished {"run": "T0308-critic-20261110T181907-65bc", "status": "completed", "cost": 2.272415, "subtype": "success", "report": "structured_output"}
- 2026-11-11T02:33:49+00:00 task_added {"task": "T0309", "reason": "reviews T0307/T0308 follow-up (E008 runner, before T0263)"}
- 2026-11-11T02:33:49+00:00 task_amended {"task": "T0263", "reason": "waits for T0309 (E008 runner fixes from reviews T0307/T0308) so the gates are settled before F3"}
- 2026-11-11T02:59:26+00:00 inbox_opened {"id": "I0166", "kind": "protected_change", "subject": "T0306: merge needs founder approval"}
- 2026-11-11T03:00:02+00:00 sleep_detected {"gap_s": 1639, "runs_extended": 0}
- 2026-11-11T03:40:21+00:00 inbox_resolved {"id": "I0166", "status": "approved", "note": "Merge the E008 runner fixes from reviews T0304/T0305. Both critics accept with caveats; their findings go to T030
- 2026-11-11T03:40:55+00:00 merged {"task": "T0306"}
- 2026-11-11T03:40:55+00:00 inbox_opened {"id": "I0167", "kind": "experiment_registration", "subject": "register E008 (pre-registration)"}
- 2026-11-11T03:40:59+00:00 run_started {"run": "T0309-scientist-20261110T194059-505a", "task": "T0309", "role": "scientist", "session": "e5ac8c3e-b8e9-4d1a-ae59-361f8019f629"}
