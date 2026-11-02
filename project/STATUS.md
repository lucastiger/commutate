# ModuleForge status
_generated 2026-11-02T19:11:31+00:00 from repository state — do not edit_

## Founder inbox (1 open)
- **I0090** [experiment_registration] register E006 (pre-registration)

## Objectives
| id | status | verdict | evals | spent | title |
|---|---|---|---|---|---|
| O000 | passed | PASS | 1/2 | $0.50/$20 | Framework canary — the loop carries a known-answer hypothesis from plan to verdict |
| O001 | passed | PASS | 1/3 | $287.86/$315 | L1 PEEC ranks half-bridge layouts faithfully enough to drive layout search |
| O002 | draft | - | 0/1 | $11.44/$120 | A fast L1 thermal model predicts per-die Tj max, spread and layout-to-layout differences well enough to drive search |
| O003 | draft | - | 0/1 | $5.89/$150 | Reference wire-bonded half-bridge layouts leave >= 20 % loop-inductance headroom inside their own housing at <= +2 K Tj |
| O004 | draft | - | 0/1 | $9.51/$100 | The L2 inductance reference is accurate on reconstructed public modules, so it can judge O003's headroom |
| O005 | draft | - | 0/2 | $7.65/$60 | L1 picks near-best layouts within a fixed family and die count, the regime derivative re-layout searches |
| O006 | active | - | 0/1 | $128.59/$140 | The thermal L2 reference matches converged analytic solutions and an independent FEM, and design pilots measure what O002-O004 must fix |
| O901 | passed | PASS | 1/2 | $9.19/$30 | Infrastructure canary v2 - a known answer through registered, sealed, recomputed and null-checked evidence |

## Usage (from run records)
| objective | runs | usd | output tokens | thinking | denials | limit hits |
|---|---|---|---|---|---|---|
| O002 | 6 | $11.44 | 293351 | 180601 | 28 | 0 |
| O003 | 4 | $5.89 | 136620 | 96498 | 8 | 0 |
| O004 | 6 | $9.51 | 225161 | 160260 | 17 | 0 |
| O005 | 4 | $7.65 | 185443 | 108670 | 29 | 0 |
| O006 | 66 | $128.59 | 2466052 | 1349402 | 112 | 0 |
| O901 | 3 | $5.05 | 101607 | 52842 | 14 | 0 |

## Tasks
cancelled: 30, done: 161, failed: 3, review: 1, running: 1, todo: 1

- T0196 `review` scientist/design_experiment: E006 pre-registration fixes (reviews T0194/T0195): gate the z-doubled scikit-fem solve, calibrate_power pairing, F5 dev feasibility (attempt 1)
- T0197 `running` critic/review: Review T0196 (general) (attempt 1)

## Recent events
- 2026-11-02T17:33:12+00:00 task_added {"task": "T0196", "objective": "O006", "reason": "E006 pre-registration fixes"}
- 2026-11-02T17:42:14+00:00 inbox_opened {"id": "I0089", "kind": "protected_change", "subject": "T0165: merge needs founder approval"}
- 2026-11-02T17:42:48+00:00 sleep_detected {"gap_s": 612, "runs_extended": 0}
- 2026-11-02T18:33:53+00:00 inbox_resolved {"id": "I0089", "status": "approved", "note": "T0165: E006 design merged (reviews T0194/T0195 accept with caveats; fixes in T0196 before registration)", "by": "
- 2026-11-02T18:34:18+00:00 merged {"task": "T0165"}
- 2026-11-02T18:34:18+00:00 inbox_opened {"id": "I0090", "kind": "experiment_registration", "subject": "register E006 (pre-registration)"}
- 2026-11-02T18:34:20+00:00 inbox_opened {"id": "I0091", "kind": "budget_increase", "subject": "daily LLM budget reached"}
- 2026-11-02T18:40:13+00:00 inbox_resolved {"id": "I0091", "status": "approved", "note": "Daily cap raised to 120 in policy", "by": "human"}
- 2026-11-02T18:40:34+00:00 inbox_opened {"id": "I0092", "kind": "budget_increase", "subject": "daily LLM budget reached"}
- 2026-11-02T18:40:36+00:00 loop_started {"pid": 85666}
- 2026-11-02T18:40:39+00:00 run_started {"run": "T0196-scientist-20261102T104039-19d7", "task": "T0196", "role": "scientist", "session": "46daa03b-08ae-48aa-b8e5-71eebf2a9c4f"}
- 2026-11-02T18:42:54+00:00 inbox_resolved {"id": "I0092", "status": "approved", "note": "Stale: cap already 120 (b1233a2); raised by the pre-restart loop", "by": "human"}
- 2026-11-02T19:01:47+00:00 run_finished {"run": "T0196-scientist-20261102T104039-19d7", "status": "completed", "cost": 3.36292, "subtype": "success", "report": "structured_output"}
- 2026-11-02T19:03:55+00:00 verified {"task": "T0196"}
- 2026-11-02T19:03:58+00:00 run_started {"run": "T0197-critic-20261102T110358-0958", "task": "T0197", "role": "critic", "session": "3e74a854-2db3-4e8a-b75c-34fdbd8b62ca"}
