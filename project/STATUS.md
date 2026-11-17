# ModuleForge status
_generated 2026-11-17T16:55:12+00:00 from repository state — do not edit_

## Founder inbox (2 open)
- **I0205** [external_action] [O008] Burst VM for E011's development L2 draws (band bound, joint operating characteristic, dev rows)
- **I0209** [external_action] [O004] O004: two F7 burst-VM runs before E004 registration, and a budget warning

## Objectives
| id | status | verdict | evals | spent | title |
|---|---|---|---|---|---|
| O000 | passed | PASS | 1/2 | $0.50/$20 | Framework canary — the loop carries a known-answer hypothesis from plan to verdict |
| O001 | passed | PASS | 1/3 | $287.86/$315 | L1 PEEC ranks half-bridge layouts faithfully enough to drive layout search |
| O002 | active | - | 0/1 | $80.05/$120 | A fast L1 thermal model predicts each die's average junction temperature, the spread across paralleled dies and layout-to-layout differences well enough to drive search |
| O003 | needs_founder | - | 0/1 | $258.22/$265 | Reference wire-bonded half-bridge layouts leave >= 20 % loop-inductance headroom inside their own housing at <= +2 K Tj |
| O004 | active | - | 0/1 | $95.01/$100 | The L2 inductance reference agrees with an independent field solver on the inductance ratios of re-layouts of PowerSynth public sample designs |
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
| O004 | 48 | $95.01 | 1602035 | 925454 | 135 | 0 |
| O005 | 4 | $7.65 | 185443 | 108670 | 29 | 0 |
| O006 | 69 | $137.91 | 2633380 | 1435121 | 137 | 0 |
| O007 | 50 | $92.55 | 1684141 | 838123 | 79 | 1 |
| O008 | 39 | $76.74 | 1358180 | 757831 | 108 | 0 |
| O901 | 3 | $5.05 | 101607 | 52842 | 14 | 0 |

## Tasks
cancelled: 46, done: 393, failed: 4, running: 3, todo: 5

- T0382 `running` scientist/design_experiment: Design E011: draft spec and runner (selftest, smoke, development mode with the burst job manifest) (attempt 4)
- T0398 `running` scientist/design_experiment: E007 development rows: local dev run, F2 null check via mfos exp check, F3 coverage re-run on the dev structure (attempt 1)
- T0451 `running` builder/implement: perturb.py hash coverage and redraw fixes (T0446), adapter test and docstring items (T0445), before E004's hash freezes (attempt 1)

## Recent events
- 2026-11-17T16:25:38+00:00 merged {"task": "T0397"}
- 2026-11-17T16:25:38+00:00 inbox_opened {"id": "I0243", "kind": "experiment_registration", "subject": "register E007 (pre-registration)"}
- 2026-11-17T16:31:18+00:00 merged {"task": "T0419"}
- 2026-11-17T16:36:52+00:00 merged {"task": "T0438"}
- 2026-11-17T16:42:32+00:00 merged {"task": "T0443"}
- 2026-11-17T16:42:39+00:00 run_started {"run": "T0451-builder-20261117T084239-1749", "task": "T0451", "role": "builder", "session": "bdd863ab-32cd-481d-ae5b-5d04a3448e4e"}
- 2026-11-17T16:42:40+00:00 run_started {"run": "T0398-scientist-20261117T084240-e4d3", "task": "T0398", "role": "scientist", "session": "42d0956f-582d-4e90-b39e-5de340d71007"}
- 2026-11-17T16:43:15+00:00 loop_stopped {"reason": "STOP file"}
- 2026-11-17T16:53:01+00:00 inbox_resolved {"id": "I0243", "status": "rejected", "note": "Premature: E007 design is incomplete. T0398 development rows and the final layouts per stratum from its power fig
- 2026-11-17T16:53:07+00:00 loop_started {"pid": 57452}
- 2026-11-17T16:53:08+00:00 run_finished {"run": "T0382-scientist-20261117T070728-ed30", "status": "completed", "cost": 1.955482, "subtype": "success", "report": "structured_output"}
- 2026-11-17T16:53:08+00:00 task_blocked {"task": "T0382"}
- 2026-11-17T16:53:08+00:00 inbox_opened {"id": "I0244", "kind": "decision", "subject": "T0382 blocked: the agent reports the task impossible or mis-specified"}
- 2026-11-17T16:54:59+00:00 inbox_resolved {"id": "I0244", "status": "answered", "note": "Resolved: agents cannot merge, so the founder merged main into the T0382 branch, which now has the T0437 code. At
- 2026-11-17T16:55:11+00:00 run_started {"run": "T0382-scientist-20261117T085511-4122", "task": "T0382", "role": "scientist", "session": "fefbfade-650f-476c-8445-b68ece0c022b"}
