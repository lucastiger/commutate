# ModuleForge status
_generated 2026-11-10T04:17:49+00:00 from repository state — do not edit_

## Founder inbox (1 open)
- **I0140** [question] [O003] Reference set on 2026-11-12 (D0010): customer layouts or public fallback

## Objectives
| id | status | verdict | evals | spent | title |
|---|---|---|---|---|---|
| O000 | passed | PASS | 1/2 | $0.50/$20 | Framework canary — the loop carries a known-answer hypothesis from plan to verdict |
| O001 | passed | PASS | 1/3 | $287.86/$315 | L1 PEEC ranks half-bridge layouts faithfully enough to drive layout search |
| O002 | draft | - | 0/1 | $11.44/$120 | A fast L1 thermal model predicts per-die Tj max, spread and layout-to-layout differences well enough to drive search |
| O003 | active | - | 0/1 | $84.40/$250 | Reference wire-bonded half-bridge layouts leave >= 20 % loop-inductance headroom inside their own housing at <= +2 K Tj |
| O004 | draft | - | 0/1 | $9.51/$100 | The L2 inductance reference is accurate on reconstructed public modules, so it can judge O003's headroom |
| O005 | draft | - | 0/2 | $7.65/$60 | L1 picks near-best layouts within a fixed family and die count, the regime derivative re-layout searches |
| O006 | active | INCONCLUSIVE | 1/1 | $137.91/$140 | The thermal L2 reference matches converged analytic solutions and an independent FEM, and design pilots measure what O002-O004 must fix |
| O007 | passed | PASS | 1/1 | $92.55/$110 | The scikit-fem thermal reference matches converged analytic solutions and the in-house finite-volume L2 on generator layouts |
| O901 | passed | PASS | 1/2 | $9.19/$30 | Infrastructure canary v2 - a known answer through registered, sealed, recomputed and null-checked evidence |

## Usage (from run records)
| objective | runs | usd | output tokens | thinking | denials | limit hits |
|---|---|---|---|---|---|---|
| O002 | 6 | $11.44 | 293351 | 180601 | 28 | 0 |
| O003 | 51 | $84.40 | 1656823 | 884555 | 88 | 0 |
| O004 | 6 | $9.51 | 225161 | 160260 | 17 | 0 |
| O005 | 4 | $7.65 | 185443 | 108670 | 29 | 0 |
| O006 | 69 | $137.91 | 2633380 | 1435121 | 137 | 0 |
| O007 | 50 | $92.55 | 1684141 | 838123 | 79 | 1 |
| O901 | 3 | $5.05 | 101607 | 52842 | 14 | 0 |

## Tasks
cancelled: 38, done: 248, failed: 3, merge: 1, running: 2, todo: 3

- T0290 `merge` builder/implement: Generator: DRC-consistent float tolerance in _quick_ok, tests that fail without the fixes (review T0288) (attempt 1)
- T0292 `running` builder/implement: Search driver: import the evaluator's band estimator, union near-tie window, thermal record checks (review T0289) (attempt 1)
- T0293 `running` builder/implement: Twin/degrade: L1-raising fallback walk for minimum-width bands, exact merged-band split (review T0291) (attempt 1)

## Recent events
- 2026-11-10T03:17:09+00:00 inbox_opened {"id": "I0157", "kind": "protected_change", "subject": "T0287: merge needs founder approval"}
- 2026-11-10T03:17:46+00:00 sleep_detected {"gap_s": 384, "runs_extended": 1}
- 2026-11-10T03:22:14+00:00 run_finished {"run": "T0290-builder-20261109T183005-35cf", "status": "completed", "cost": 0.755394, "subtype": "success", "report": "structured_output"}
- 2026-11-10T03:33:42+00:00 inbox_resolved {"id": "I0156", "status": "approved", "note": "Merge T0285: one band-based e_R, atomic checkpoint repair, whitelisted thermal records; T0289 accepts with minor 
- 2026-11-10T03:33:44+00:00 inbox_resolved {"id": "I0157", "status": "approved", "note": "Merge T0287: degradation target 1.25 x 1.11 reached on the 54-layout population and Case 4, merged-band split, ex
- 2026-11-10T03:36:04+00:00 verified {"task": "T0290"}
- 2026-11-10T03:36:07+00:00 merged {"task": "T0285"}
- 2026-11-10T03:40:34+00:00 merged {"task": "T0287"}
- 2026-11-10T03:40:38+00:00 run_started {"run": "T0294-critic-20261109T194038-25f5", "task": "T0294", "role": "critic", "session": "fedf5bc2-92fc-4b89-bcfa-0a5cf84f09ba"}
- 2026-11-10T03:40:39+00:00 run_started {"run": "T0292-builder-20261109T194039-7abc", "task": "T0292", "role": "builder", "session": "ef8584f7-bf10-4ed9-9c17-d805584149cc"}
- 2026-11-10T03:40:39+00:00 run_started {"run": "T0293-builder-20261109T194039-aeaf", "task": "T0293", "role": "builder", "session": "f5ae19c9-d926-4006-ae6e-59f025cf074f"}
- 2026-11-10T03:41:13+00:00 sleep_detected {"gap_s": 1141, "runs_extended": 3}
- 2026-11-10T04:08:39+00:00 run_finished {"run": "T0294-critic-20261109T194038-25f5", "status": "completed", "cost": 1.894022, "subtype": "success", "report": "structured_output"}
- 2026-11-10T04:09:16+00:00 task_added {"task": "T0295", "reason": "review T0294 follow-up (keepout corners)"}
- 2026-11-10T04:09:16+00:00 task_amended {"task": "T0262", "reason": "waits for T0295 (keepout corners, review T0294)"}
