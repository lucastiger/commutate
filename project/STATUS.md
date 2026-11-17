# ModuleForge status
_generated 2026-11-17T21:31:41+00:00 from repository state — do not edit_

## Founder inbox (3 open)
- **I0205** [external_action] [O008] Burst VM for E011's development L2 draws (band bound, joint operating characteristic, dev rows)
- **I0209** [external_action] [O004] O004: two F7 burst-VM runs before E004 registration, and a budget warning
- **I0247** [protected_change] T0389: merge needs founder approval

## Objectives
| id | status | verdict | evals | spent | title |
|---|---|---|---|---|---|
| O000 | passed | PASS | 1/2 | $0.50/$20 | Framework canary — the loop carries a known-answer hypothesis from plan to verdict |
| O001 | passed | PASS | 1/3 | $287.86/$315 | L1 PEEC ranks half-bridge layouts faithfully enough to drive layout search |
| O002 | active | - | 0/1 | $85.27/$120 | A fast L1 thermal model predicts each die's average junction temperature, the spread across paralleled dies and layout-to-layout differences well enough to drive search |
| O003 | needs_founder | - | 0/1 | $258.22/$265 | Reference wire-bonded half-bridge layouts leave >= 20 % loop-inductance headroom inside their own housing at <= +2 K Tj |
| O004 | active | - | 0/1 | $111.36/$148 | The L2 inductance reference agrees with an independent field solver on the inductance ratios of re-layouts of PowerSynth public sample designs |
| O005 | draft | - | 0/2 | $7.65/$60 | L1 picks near-best layouts within a fixed family and die count, the regime derivative re-layout searches |
| O006 | active | INCONCLUSIVE | 1/1 | $137.91/$140 | The thermal L2 reference matches converged analytic solutions and an independent FEM, and design pilots measure what O002-O004 must fix |
| O007 | passed | PASS | 1/1 | $92.55/$110 | The scikit-fem thermal reference matches converged analytic solutions and the in-house finite-volume L2 on generator layouts |
| O008 | active | - | 0/2 | $76.74/$140 | A search seeded at a degraded copy of a near-optimal layout recovers it, where inductance-blind heuristics do not, on every designer-derived development layout |
| O901 | passed | PASS | 1/2 | $9.19/$30 | Infrastructure canary v2 - a known answer through registered, sealed, recomputed and null-checked evidence |

## Usage (from run records)
| objective | runs | usd | output tokens | thinking | denials | limit hits |
|---|---|---|---|---|---|---|
| O002 | 36 | $85.27 | 1597678 | 817600 | 110 | 0 |
| O003 | 135 | $258.22 | 4105839 | 2002393 | 280 | 0 |
| O004 | 53 | $111.36 | 1760637 | 987261 | 142 | 0 |
| O005 | 4 | $7.65 | 185443 | 108670 | 29 | 0 |
| O006 | 69 | $137.91 | 2633380 | 1435121 | 137 | 0 |
| O007 | 50 | $92.55 | 1684141 | 838123 | 79 | 1 |
| O008 | 39 | $76.74 | 1358180 | 757831 | 108 | 0 |
| O901 | 3 | $5.05 | 101607 | 52842 | 14 | 0 |

## Tasks
cancelled: 46, done: 398, failed: 4, needs_founder: 1, running: 2, todo: 6

- T0382 `running` scientist/design_experiment: Design E011: draft spec and runner (selftest, smoke, development mode with the burst job manifest) (attempt 4)
- T0389 `needs_founder` scientist/design_experiment: E004 design, part 2: solve stage, estimators, A1/A2/K1/K2 metrics, INVALID rules, and the FastHenry F7(a) job list (attempt 1)
- T0398 `running` scientist/design_experiment: E007 development rows: local dev run, F2 null check via mfos exp check, F3 coverage re-run on the dev structure (attempt 2)

## Recent events
- 2026-11-17T20:11:11+00:00 verified {"task": "T0389"}
- 2026-11-17T20:11:15+00:00 inbox_opened {"id": "I0246", "kind": "budget_increase", "subject": "[O004] budget exhausted ($102.85/$100.00)"}
- 2026-11-17T20:16:44+00:00 inbox_resolved {"id": "I0246", "status": "approved", "note": "usd=45", "by": "human"}
- 2026-11-17T20:17:08+00:00 run_started {"run": "T0453-critic-20261117T121708-3b1a", "task": "T0453", "role": "critic", "session": "e600b035-36b7-4dbd-9b66-f40e81f33e1e"}
- 2026-11-17T20:29:21+00:00 run_finished {"run": "T0453-critic-20261117T121708-3b1a", "status": "completed", "cost": 2.903289, "subtype": "success", "report": "structured_output"}
- 2026-11-17T20:29:35+00:00 run_started {"run": "T0454-critic-20261117T122935-02ee", "task": "T0454", "role": "critic", "session": "a0051ebe-6aba-4c41-93ff-0cd04b1bb342"}
- 2026-11-17T20:42:35+00:00 run_finished {"run": "T0454-critic-20261117T122935-02ee", "status": "completed", "cost": 2.888709, "subtype": "success", "report": "structured_output"}
- 2026-11-17T20:42:50+00:00 run_started {"run": "T0455-critic-20261117T124250-7589", "task": "T0455", "role": "critic", "session": "6cc75dbb-1eb1-4a3e-bb93-9e386055efd6"}
- 2026-11-17T20:50:55+00:00 run_finished {"run": "T0398-scientist-20261117T084240-e4d3", "status": "completed", "cost": 5.221086, "subtype": "success", "report": "structured_output"}
- 2026-11-17T20:58:34+00:00 task_failed_attempt {"task": "T0398", "signal": "dod_failed", "action": "repair"}
- 2026-11-17T20:58:34+00:00 run_finished {"run": "T0455-critic-20261117T124250-7589", "status": "completed", "cost": 2.712642, "subtype": "success", "report": "structured_output"}
- 2026-11-17T20:58:50+00:00 task_added {"task": "T0456", "note": "founder approved 2026-11-17 (Diagnose, then decide)"}
- 2026-11-17T21:00:49+00:00 task_added {"task": "T0457", "note": "founder approved 2026-11-17"}
- 2026-11-17T21:31:35+00:00 inbox_opened {"id": "I0247", "kind": "protected_change", "subject": "T0389: merge needs founder approval"}
- 2026-11-17T21:31:41+00:00 run_started {"run": "T0398-scientist-20261117T133141-2750", "task": "T0398", "role": "scientist", "session": "fcc9f3de-006d-4e4a-be6d-12aac8e8e0db"}
