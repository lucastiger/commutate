# ModuleForge status
_generated 2026-11-17T20:11:20+00:00 from repository state — do not edit_

## Founder inbox (3 open)
- **I0205** [external_action] [O008] Burst VM for E011's development L2 draws (band bound, joint operating characteristic, dev rows)
- **I0209** [external_action] [O004] O004: two F7 burst-VM runs before E004 registration, and a budget warning
- **I0246** [budget_increase] [O004] budget exhausted ($102.85/$100.00)

## Objectives
| id | status | verdict | evals | spent | title |
|---|---|---|---|---|---|
| O000 | passed | PASS | 1/2 | $0.50/$20 | Framework canary — the loop carries a known-answer hypothesis from plan to verdict |
| O001 | passed | PASS | 1/3 | $287.86/$315 | L1 PEEC ranks half-bridge layouts faithfully enough to drive layout search |
| O002 | active | - | 0/1 | $80.05/$120 | A fast L1 thermal model predicts each die's average junction temperature, the spread across paralleled dies and layout-to-layout differences well enough to drive search |
| O003 | needs_founder | - | 0/1 | $258.22/$265 | Reference wire-bonded half-bridge layouts leave >= 20 % loop-inductance headroom inside their own housing at <= +2 K Tj |
| O004 | needs_founder | - | 0/1 | $102.85/$100 | The L2 inductance reference agrees with an independent field solver on the inductance ratios of re-layouts of PowerSynth public sample designs |
| O005 | draft | - | 0/2 | $7.65/$60 | L1 picks near-best layouts within a fixed family and die count, the regime derivative re-layout searches |
| O006 | active | INCONCLUSIVE | 1/1 | $137.91/$140 | The thermal L2 reference matches converged analytic solutions and an independent FEM, and design pilots measure what O002-O004 must fix |
| O007 | passed | PASS | 1/1 | $92.55/$110 | The scikit-fem thermal reference matches converged analytic solutions and the in-house finite-volume L2 on generator layouts |
| O008 | active | - | 0/2 | $76.74/$140 | A search seeded at a degraded copy of a near-optimal layout recovers it, where inductance-blind heuristics do not, on every designer-derived development layout |
| O901 | passed | PASS | 1/2 | $9.19/$30 | Infrastructure canary v2 - a known answer through registered, sealed, recomputed and null-checked evidence |

## Usage (from run records)
| objective | runs | usd | output tokens | thinking | denials | limit hits |
|---|---|---|---|---|---|---|
| O002 | 35 | $80.05 | 1517932 | 785394 | 109 | 0 |
| O003 | 135 | $258.22 | 4105839 | 2002393 | 280 | 0 |
| O004 | 50 | $102.85 | 1744973 | 986819 | 142 | 0 |
| O005 | 4 | $7.65 | 185443 | 108670 | 29 | 0 |
| O006 | 69 | $137.91 | 2633380 | 1435121 | 137 | 0 |
| O007 | 50 | $92.55 | 1684141 | 838123 | 79 | 1 |
| O008 | 39 | $76.74 | 1358180 | 757831 | 108 | 0 |
| O901 | 3 | $5.05 | 101607 | 52842 | 14 | 0 |

## Tasks
cancelled: 46, done: 395, failed: 4, review: 1, running: 2, todo: 7

- T0382 `running` scientist/design_experiment: Design E011: draft spec and runner (selftest, smoke, development mode with the burst job manifest) (attempt 4)
- T0389 `review` scientist/design_experiment: E004 design, part 2: solve stage, estimators, A1/A2/K1/K2 metrics, INVALID rules, and the FastHenry F7(a) job list (attempt 1)
- T0398 `running` scientist/design_experiment: E007 development rows: local dev run, F2 null check via mfos exp check, F3 coverage re-run on the dev structure (attempt 1)

## Recent events
- 2026-11-17T16:53:08+00:00 task_blocked {"task": "T0382"}
- 2026-11-17T16:53:08+00:00 inbox_opened {"id": "I0244", "kind": "decision", "subject": "T0382 blocked: the agent reports the task impossible or mis-specified"}
- 2026-11-17T16:54:59+00:00 inbox_resolved {"id": "I0244", "status": "answered", "note": "Resolved: agents cannot merge, so the founder merged main into the T0382 branch, which now has the T0437 code. At
- 2026-11-17T16:55:11+00:00 run_started {"run": "T0382-scientist-20261117T085511-4122", "task": "T0382", "role": "scientist", "session": "fefbfade-650f-476c-8445-b68ece0c022b"}
- 2026-11-17T17:14:45+00:00 run_finished {"run": "T0451-builder-20261117T084239-1749", "status": "completed", "cost": 0.463409, "subtype": "success", "report": "structured_output"}
- 2026-11-17T17:31:27+00:00 verified {"task": "T0451"}
- 2026-11-17T17:31:39+00:00 run_started {"run": "T0452-critic-20261117T093139-9a28", "task": "T0452", "role": "critic", "session": "76055eba-cb1b-44fe-a264-d8870c0b0724"}
- 2026-11-17T17:52:25+00:00 run_finished {"run": "T0452-critic-20261117T093139-9a28", "status": "completed", "cost": 2.064137, "subtype": "success", "report": "structured_output"}
- 2026-11-17T17:52:32+00:00 inbox_opened {"id": "I0245", "kind": "protected_change", "subject": "T0451: merge needs founder approval"}
- 2026-11-17T18:30:34+00:00 inbox_resolved {"id": "I0245", "status": "approved", "note": "T0451 merge approved, review T0452 accepts with caveats. Rules hash now covers Die.bounds and _ring_ints, LongSid
- 2026-11-17T18:30:57+00:00 merged {"task": "T0451"}
- 2026-11-17T18:31:08+00:00 run_started {"run": "T0389-scientist-20261117T103108-f20b", "task": "T0389", "role": "scientist", "session": "6cb45661-9e39-42a3-951d-89ca80ed7ac2"}
- 2026-11-17T19:51:45+00:00 run_finished {"run": "T0389-scientist-20261117T103108-f20b", "status": "completed", "cost": 5.312969, "subtype": "success", "report": "structured_output"}
- 2026-11-17T20:11:11+00:00 verified {"task": "T0389"}
- 2026-11-17T20:11:15+00:00 inbox_opened {"id": "I0246", "kind": "budget_increase", "subject": "[O004] budget exhausted ($102.85/$100.00)"}
