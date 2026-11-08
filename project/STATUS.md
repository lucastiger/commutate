# ModuleForge status
_generated 2026-11-08T07:12:26+00:00 from repository state — do not edit_

## Founder inbox (0 open)
- nothing needs you

## Objectives
| id | status | verdict | evals | spent | title |
|---|---|---|---|---|---|
| O000 | passed | PASS | 1/2 | $0.50/$20 | Framework canary — the loop carries a known-answer hypothesis from plan to verdict |
| O001 | passed | PASS | 1/3 | $287.86/$315 | L1 PEEC ranks half-bridge layouts faithfully enough to drive layout search |
| O002 | draft | - | 0/1 | $11.44/$120 | A fast L1 thermal model predicts per-die Tj max, spread and layout-to-layout differences well enough to drive search |
| O003 | draft | - | 0/1 | $5.89/$150 | Reference wire-bonded half-bridge layouts leave >= 20 % loop-inductance headroom inside their own housing at <= +2 K Tj |
| O004 | draft | - | 0/1 | $9.51/$100 | The L2 inductance reference is accurate on reconstructed public modules, so it can judge O003's headroom |
| O005 | draft | - | 0/2 | $7.65/$60 | L1 picks near-best layouts within a fixed family and die count, the regime derivative re-layout searches |
| O006 | active | INCONCLUSIVE | 1/1 | $137.91/$140 | The thermal L2 reference matches converged analytic solutions and an independent FEM, and design pilots measure what O002-O004 must fix |
| O007 | evaluating | PASS | 1/1 | $90.68/$110 | The scikit-fem thermal reference matches converged analytic solutions and the in-house finite-volume L2 on generator layouts |
| O901 | passed | PASS | 1/2 | $9.19/$30 | Infrastructure canary v2 - a known answer through registered, sealed, recomputed and null-checked evidence |

## Usage (from run records)
| objective | runs | usd | output tokens | thinking | denials | limit hits |
|---|---|---|---|---|---|---|
| O002 | 6 | $11.44 | 293351 | 180601 | 28 | 0 |
| O003 | 4 | $5.89 | 136620 | 96498 | 8 | 0 |
| O004 | 6 | $9.51 | 225161 | 160260 | 17 | 0 |
| O005 | 4 | $7.65 | 185443 | 108670 | 29 | 0 |
| O006 | 69 | $137.91 | 2633380 | 1435121 | 137 | 0 |
| O007 | 49 | $90.68 | 1655473 | 821709 | 74 | 0 |
| O901 | 3 | $5.05 | 101607 | 52842 | 14 | 0 |

## Tasks
cancelled: 38, done: 208, failed: 3, running: 1

- T0250 `running` critic/review: Review EV-O007-01 (general) (attempt 1)

## Recent events
- 2026-11-06T16:06:44+00:00 inbox_opened {"id": "I0134", "kind": "protected_change", "subject": "T0244: merge needs founder approval"}
- 2026-11-06T16:07:37+00:00 sleep_detected {"gap_s": 691, "runs_extended": 0}
- 2026-11-06T20:20:43+00:00 inbox_resolved {"id": "I0134", "status": "approved", "note": "Merge T0244 (E009 design): T0248 and T0249 accept with caveats. full() checked against the ExperimentRun API by r
- 2026-11-06T20:21:04+00:00 merged {"task": "T0244"}
- 2026-11-06T20:21:04+00:00 inbox_opened {"id": "I0135", "kind": "experiment_registration", "subject": "register E009 (pre-registration)"}
- 2026-11-06T20:57:52+00:00 experiment_registered {"id": "E009", "hash": "sha256:7d703f10e909b5281d177919c4d9fe7098e6cd670f1c26f938f3bb872d333c94", "by": "founder"}
- 2026-11-06T20:57:52+00:00 inbox_resolved {"id": "I0135", "status": "approved", "note": "Register E009: spec matches O007 (A1-A4, K1/K2, F1-F5 via ref_gci_cap per I0099); full() exercised end to end in 
- 2026-11-06T20:58:22+00:00 inbox_opened {"id": "I0136", "kind": "decision", "subject": "E009 needs burst compute (~20 CPU-h)"}
- 2026-11-06T20:58:22+00:00 burst_requested {"task": "T0245", "experiment": "E009", "cpu_hours": 20.0}
- 2026-11-07T01:50:34+00:00 sleep_detected {"gap_s": 10927, "runs_extended": 0}
- 2026-11-07T03:52:56+00:00 sleep_detected {"gap_s": 7343, "runs_extended": 0}
- 2026-11-08T00:21:52+00:00 experiment_minted {"id": "E009", "run": "E009-20261107T162152-a3cf"}
- 2026-11-08T00:22:04+00:00 inbox_resolved {"id": "I0136", "status": "approved", "note": "E009 launched on n2d-custom-8-155648-ext (free trial, 8 vCPU; 152 GiB clears the spec's 131 GB preflight bound), 
- 2026-11-08T07:12:21+00:00 evaluation {"objective": "O007", "id": "EV-O007-01", "verdict": "PASS"}
- 2026-11-08T07:12:26+00:00 run_started {"run": "T0250-critic-20261107T231226-0cd8", "task": "T0250", "role": "critic", "session": "88b907f8-7fbd-40ce-8f7b-6c2fe200bed2"}
