# ModuleForge status
_generated 2026-11-18T15:03:59+00:00 from repository state — do not edit_

## Founder inbox (3 open)
- **I0205** [external_action] [O008] Burst VM for E011's development L2 draws (band bound, joint operating characteristic, dev rows)
- **I0209** [external_action] [O004] O004: two F7 burst-VM runs before E004 registration, and a budget warning
- **I0255** [decision] E007 needs burst compute (~84.5 CPU-h)

## Objectives
| id | status | verdict | evals | spent | title |
|---|---|---|---|---|---|
| O000 | passed | PASS | 1/2 | $0.50/$20 | Framework canary — the loop carries a known-answer hypothesis from plan to verdict |
| O001 | passed | PASS | 1/3 | $287.86/$315 | L1 PEEC ranks half-bridge layouts faithfully enough to drive layout search |
| O002 | active | - | 0/1 | $99.38/$120 | A fast L1 thermal model predicts each die's average junction temperature, the spread across paralleled dies and layout-to-layout differences well enough to drive search |
| O003 | needs_founder | - | 0/1 | $258.22/$265 | Reference wire-bonded half-bridge layouts leave >= 20 % loop-inductance headroom inside their own housing at <= +2 K Tj |
| O004 | active | - | 0/1 | $139.22/$148 | The L2 inductance reference agrees with an independent field solver on the inductance ratios of re-layouts of PowerSynth public sample designs |
| O005 | draft | - | 0/2 | $7.65/$60 | L1 picks near-best layouts within a fixed family and die count, the regime derivative re-layout searches |
| O006 | active | INCONCLUSIVE | 1/1 | $137.91/$140 | The thermal L2 reference matches converged analytic solutions and an independent FEM, and design pilots measure what O002-O004 must fix |
| O007 | passed | PASS | 1/1 | $92.55/$110 | The scikit-fem thermal reference matches converged analytic solutions and the in-house finite-volume L2 on generator layouts |
| O008 | active | - | 0/2 | $91.48/$140 | A search seeded at a degraded copy of a near-optimal layout recovers it, where inductance-blind heuristics do not, on every designer-derived development layout |
| O901 | passed | PASS | 1/2 | $9.19/$30 | Infrastructure canary v2 - a known answer through registered, sealed, recomputed and null-checked evidence |

## Usage (from run records)
| objective | runs | usd | output tokens | thinking | denials | limit hits |
|---|---|---|---|---|---|---|
| O002 | 41 | $99.38 | 1794921 | 884897 | 131 | 0 |
| O003 | 135 | $258.22 | 4105839 | 2002393 | 280 | 0 |
| O004 | 60 | $139.22 | 2176735 | 1194906 | 158 | 0 |
| O005 | 4 | $7.65 | 185443 | 108670 | 29 | 0 |
| O006 | 69 | $137.91 | 2633380 | 1435121 | 137 | 0 |
| O007 | 50 | $92.55 | 1684141 | 838123 | 79 | 1 |
| O008 | 43 | $91.48 | 1532378 | 830907 | 120 | 0 |
| O901 | 3 | $5.05 | 101607 | 52842 | 14 | 0 |

## Tasks
cancelled: 47, done: 414, failed: 4, needs_founder: 1, todo: 2

- T0399 `needs_founder` none/experiment: Run E007: frozen L1 thermal model against the verified scikit-fem reference on fresh sealed layouts at P_ref and 0.5 P_ref (attempt 0)

## Recent events
- 2026-11-18T06:28:35+00:00 run_started {"run": "T0390-scientist-20261117T222835-1c59", "task": "T0390", "role": "scientist", "session": "2771237f-fdfa-4bc6-9f07-b025fc20d8f6"}
- 2026-11-18T08:43:14+00:00 run_finished {"run": "T0390-scientist-20261117T222835-1c59", "status": "error", "cost": 4.035547, "subtype": "error_max_budget_usd", "report": "transcript"}
- 2026-11-18T08:43:14+00:00 task_failed_attempt {"task": "T0390", "signal": "agent_error", "action": "repair"}
- 2026-11-18T08:43:22+00:00 run_started {"run": "T0390-scientist-20261118T004322-d913", "task": "T0390", "role": "scientist", "session": "5fcfe529-dbde-4739-8c19-7f02af3f2501"}
- 2026-11-18T09:54:41+00:00 run_finished {"run": "T0390-scientist-20261118T004322-d913", "status": "completed", "cost": 2.797189, "subtype": "success", "report": "structured_output"}
- 2026-11-18T10:18:07+00:00 verified {"task": "T0390"}
- 2026-11-18T10:18:18+00:00 run_started {"run": "T0467-critic-20261118T021818-450b", "task": "T0467", "role": "critic", "session": "fef46b8c-f715-4d56-8db2-4bb66b243f3f"}
- 2026-11-18T10:18:20+00:00 run_started {"run": "T0468-critic-20261118T021820-5d1e", "task": "T0468", "role": "critic", "session": "79bb6cb7-211a-47b3-b045-16a8a36dc6e3"}
- 2026-11-18T10:51:57+00:00 run_finished {"run": "T0467-critic-20261118T021818-450b", "status": "completed", "cost": 2.82753, "subtype": "success", "report": "structured_output"}
- 2026-11-18T10:53:27+00:00 run_finished {"run": "T0468-critic-20261118T021820-5d1e", "status": "completed", "cost": 2.607875, "subtype": "success", "report": "structured_output"}
- 2026-11-18T11:23:29+00:00 inbox_opened {"id": "I0257", "kind": "protected_change", "subject": "T0390: merge needs founder approval"}
- 2026-11-18T15:01:37+00:00 inbox_resolved {"id": "I0257", "status": "approved", "note": "T0390 merge approved, reviews T0467 and T0468 accept with caveats, logged in O004 state. E004 part 3: F3, F6, F8 
- 2026-11-18T15:02:22+00:00 merged {"task": "T0390"}
- 2026-11-18T15:02:23+00:00 inbox_opened {"id": "I0258", "kind": "experiment_registration", "subject": "register E004 (pre-registration)"}
- 2026-11-18T15:03:28+00:00 inbox_resolved {"id": "I0258", "status": "rejected", "note": "Premature: E004 needs the founder decisions on the FastHenry ladder, the span lower end, the CPU budget and timeo
