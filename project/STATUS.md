# ModuleForge status
_generated 2026-11-15T10:36:13+00:00 from repository state — do not edit_

## Founder inbox (0 open)
- nothing needs you

## Objectives
| id | status | verdict | evals | spent | title |
|---|---|---|---|---|---|
| O000 | passed | PASS | 1/2 | $0.50/$20 | Framework canary — the loop carries a known-answer hypothesis from plan to verdict |
| O001 | passed | PASS | 1/3 | $287.86/$315 | L1 PEEC ranks half-bridge layouts faithfully enough to drive layout search |
| O002 | draft | - | 0/1 | $11.44/$120 | A fast L1 thermal model predicts per-die Tj max, spread and layout-to-layout differences well enough to drive search |
| O003 | active | - | 0/1 | $252.88/$265 | Reference wire-bonded half-bridge layouts leave >= 20 % loop-inductance headroom inside their own housing at <= +2 K Tj |
| O004 | draft | - | 0/1 | $9.51/$100 | The L2 inductance reference is accurate on reconstructed public modules, so it can judge O003's headroom |
| O005 | draft | - | 0/2 | $7.65/$60 | L1 picks near-best layouts within a fixed family and die count, the regime derivative re-layout searches |
| O006 | active | INCONCLUSIVE | 1/1 | $137.91/$140 | The thermal L2 reference matches converged analytic solutions and an independent FEM, and design pilots measure what O002-O004 must fix |
| O007 | passed | PASS | 1/1 | $92.55/$110 | The scikit-fem thermal reference matches converged analytic solutions and the in-house finite-volume L2 on generator layouts |
| O901 | passed | PASS | 1/2 | $9.19/$30 | Infrastructure canary v2 - a known answer through registered, sealed, recomputed and null-checked evidence |

## Usage (from run records)
| objective | runs | usd | output tokens | thinking | denials | limit hits |
|---|---|---|---|---|---|---|
| O002 | 6 | $11.44 | 293351 | 180601 | 28 | 0 |
| O003 | 134 | $252.88 | 4013058 | 1954277 | 274 | 0 |
| O004 | 6 | $9.51 | 225161 | 160260 | 17 | 0 |
| O005 | 4 | $7.65 | 185443 | 108670 | 29 | 0 |
| O006 | 69 | $137.91 | 2633380 | 1435121 | 137 | 0 |
| O007 | 50 | $92.55 | 1684141 | 838123 | 79 | 1 |
| O901 | 3 | $5.05 | 101607 | 52842 | 14 | 0 |

## Tasks
cancelled: 44, done: 300, failed: 4, running: 1

- T0349 `running` scientist/investigate: Diagnose failure of EV-O003-01 (attempt 1)

## Recent events
- 2026-11-15T04:16:27+00:00 experiment_registered {"id": "E010", "hash": "sha256:0f9a4d0ffd5b3e31cf03a93f7dbea42c121bad0a3b6c163ff33bfb5377e2eae8", "by": "founder"}
- 2026-11-15T04:16:27+00:00 inbox_resolved {"id": "I0201", "status": "approved", "note": "Register E010 per D0021/D0022 (E008 + repaired sampler + SearchInfeasible exclusion + new freeze hashes); O003 v6
- 2026-11-15T04:16:50+00:00 task_added {"task": "T0347", "reason": "founder 2026-11-14: run registered E010 (D0021/D0022)"}
- 2026-11-15T04:17:16+00:00 inbox_opened {"id": "I0202", "kind": "decision", "subject": "E010 needs burst compute (~102.1 CPU-h)"}
- 2026-11-15T04:17:16+00:00 burst_requested {"task": "T0347", "experiment": "E010", "cpu_hours": 102.1}
- 2026-11-15T04:24:13+00:00 experiment_minted {"id": "E010", "run": "E010-20261114T202413-80c1"}
- 2026-11-15T10:35:22+00:00 task_failed_attempt {"task": "T0347", "signal": "sanity_failed", "action": "fix_experiment"}
- 2026-11-15T10:35:22+00:00 investigation_spawned {"task": "T0348", "about": "T0347", "cls": "experimental"}
- 2026-11-15T10:35:24+00:00 evaluation_invalid {"objective": "O003", "problems": ["E010/E010-20261114T202413-80c1: sanity checks failed: F1b_control, F1b_control:2D_Case_2R", "E010/E010-20261114T202413-80c1:
- 2026-11-15T10:35:24+00:00 investigation_spawned {"task": "T0349", "about": "EV-O003-01", "cls": "experimental"}
- 2026-11-15T10:35:27+00:00 run_started {"run": "T0348-scientist-20261115T023527-8a7a", "task": "T0348", "role": "scientist", "session": "dbd44023-b7c0-4b0e-a8b3-6e16ee41c982"}
- 2026-11-15T10:35:28+00:00 run_started {"run": "T0349-scientist-20261115T023528-c5fc", "task": "T0349", "role": "scientist", "session": "4f720fe6-06db-4a31-a50a-f085b5679a00"}
- 2026-11-15T10:36:08+00:00 run_stopped_for_founder {"run": "T0348-scientist-20261115T023527-8a7a", "task": "T0348", "task_status": "cancelled"}
- 2026-11-15T10:36:08+00:00 run_finished {"run": "T0348-scientist-20261115T023527-8a7a", "status": "error", "cost": 0.403363, "subtype": "error_during_execution", "report": "missing"}
- 2026-11-15T10:36:08+00:00 founder_stopped {"task": "T0348", "run": "T0348-scientist-20261115T023527-8a7a", "run_status": "error", "task_status": "cancelled"}
