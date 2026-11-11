# ModuleForge status
_generated 2026-11-11T01:46:58+00:00 from repository state — do not edit_

## Founder inbox (2 open)
- **I0140** [question] [O003] Reference set on 2026-11-12 (D0010): customer layouts or public fallback
- **I0165** [experiment_registration] register E008 (pre-registration)

## Objectives
| id | status | verdict | evals | spent | title |
|---|---|---|---|---|---|
| O000 | passed | PASS | 1/2 | $0.50/$20 | Framework canary — the loop carries a known-answer hypothesis from plan to verdict |
| O001 | passed | PASS | 1/3 | $287.86/$315 | L1 PEEC ranks half-bridge layouts faithfully enough to drive layout search |
| O002 | draft | - | 0/1 | $11.44/$120 | A fast L1 thermal model predicts per-die Tj max, spread and layout-to-layout differences well enough to drive search |
| O003 | active | - | 0/1 | $133.80/$250 | Reference wire-bonded half-bridge layouts leave >= 20 % loop-inductance headroom inside their own housing at <= +2 K Tj |
| O004 | draft | - | 0/1 | $9.51/$100 | The L2 inductance reference is accurate on reconstructed public modules, so it can judge O003's headroom |
| O005 | draft | - | 0/2 | $7.65/$60 | L1 picks near-best layouts within a fixed family and die count, the regime derivative re-layout searches |
| O006 | active | INCONCLUSIVE | 1/1 | $137.91/$140 | The thermal L2 reference matches converged analytic solutions and an independent FEM, and design pilots measure what O002-O004 must fix |
| O007 | passed | PASS | 1/1 | $92.55/$110 | The scikit-fem thermal reference matches converged analytic solutions and the in-house finite-volume L2 on generator layouts |
| O901 | passed | PASS | 1/2 | $9.19/$30 | Infrastructure canary v2 - a known answer through registered, sealed, recomputed and null-checked evidence |

## Usage (from run records)
| objective | runs | usd | output tokens | thinking | denials | limit hits |
|---|---|---|---|---|---|---|
| O002 | 6 | $11.44 | 293351 | 180601 | 28 | 0 |
| O003 | 86 | $133.80 | 2254606 | 1180948 | 111 | 0 |
| O004 | 6 | $9.51 | 225161 | 160260 | 17 | 0 |
| O005 | 4 | $7.65 | 185443 | 108670 | 29 | 0 |
| O006 | 69 | $137.91 | 2633380 | 1435121 | 137 | 0 |
| O007 | 50 | $92.55 | 1684141 | 838123 | 79 | 1 |
| O901 | 3 | $5.05 | 101607 | 52842 | 14 | 0 |

## Tasks
cancelled: 39, done: 262, failed: 3, running: 1, todo: 1

- T0306 `running` scientist/design_experiment: E008 runner: F6(e) per stack type, F6(c) on spot checks, rule strictness, selftest strength, dev-run reporting, FV cost basis (reviews T0304, T0305) (attempt 1)

## Recent events
- 2026-11-10T23:38:39+00:00 run_finished {"run": "T0304-critic-20261110T153219-0ef7", "status": "completed", "cost": 2.576348, "subtype": "success", "report": "structured_output"}
- 2026-11-10T23:41:03+00:00 task_added {"task": "T0306", "reason": "reviews T0304/T0305 follow-up (E008 runner, before T0263)"}
- 2026-11-10T23:41:03+00:00 task_amended {"task": "T0263", "reason": "waits for T0306 (E008 runner fixes from reviews T0304/T0305) so the gates are settled before F3"}
- 2026-11-11T00:06:20+00:00 inbox_opened {"id": "I0164", "kind": "protected_change", "subject": "T0262: merge needs founder approval"}
- 2026-11-11T00:06:56+00:00 sleep_detected {"gap_s": 1698, "runs_extended": 0}
- 2026-11-11T00:43:08+00:00 inbox_resolved {"id": "I0164", "status": "approved", "note": "Merge the E008 draft design. Both critics accept with caveats; their findings go to T0306 before T0263 loads the 
- 2026-11-11T01:09:51+00:00 merged {"task": "T0262"}
- 2026-11-11T01:09:51+00:00 inbox_opened {"id": "I0165", "kind": "experiment_registration", "subject": "register E008 (pre-registration)"}
- 2026-11-11T01:09:55+00:00 run_started {"run": "T0306-scientist-20261110T170955-0b12", "task": "T0306", "role": "scientist", "session": "83c289d4-7095-441c-948e-85c6c99fdd6c"}
- 2026-11-11T01:10:29+00:00 sleep_detected {"gap_s": 1622, "runs_extended": 1}
- 2026-11-11T01:25:33+00:00 run_finished {"run": "T0306-scientist-20261110T170955-0b12", "status": "error", "cost": 4.583078, "subtype": "success", "report": "missing"}
- 2026-11-11T01:25:33+00:00 capacity_backoff {"task": "T0306", "minutes": 5, "parsed_reset": false}
- 2026-11-11T01:30:58+00:00 run_started {"run": "T0306-scientist-20261110T173058-c746", "task": "T0306", "role": "scientist", "session": "a3244bc6-7e83-4f31-a637-12a619be0a76"}
- 2026-11-11T01:46:50+00:00 loop_stopped {"reason": "STOP file"}
- 2026-11-11T01:46:53+00:00 loop_started {"pid": 83444}
