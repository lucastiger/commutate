# ModuleForge status
_generated 2026-11-10T02:56:54+00:00 from repository state — do not edit_

## Founder inbox (2 open)
- **I0140** [question] [O003] Reference set on 2026-11-12 (D0010): customer layouts or public fallback
- **I0156** [protected_change] T0285: merge needs founder approval

## Objectives
| id | status | verdict | evals | spent | title |
|---|---|---|---|---|---|
| O000 | passed | PASS | 1/2 | $0.50/$20 | Framework canary — the loop carries a known-answer hypothesis from plan to verdict |
| O001 | passed | PASS | 1/3 | $287.86/$315 | L1 PEEC ranks half-bridge layouts faithfully enough to drive layout search |
| O002 | draft | - | 0/1 | $11.44/$120 | A fast L1 thermal model predicts per-die Tj max, spread and layout-to-layout differences well enough to drive search |
| O003 | active | - | 0/1 | $79.45/$250 | Reference wire-bonded half-bridge layouts leave >= 20 % loop-inductance headroom inside their own housing at <= +2 K Tj |
| O004 | draft | - | 0/1 | $9.51/$100 | The L2 inductance reference is accurate on reconstructed public modules, so it can judge O003's headroom |
| O005 | draft | - | 0/2 | $7.65/$60 | L1 picks near-best layouts within a fixed family and die count, the regime derivative re-layout searches |
| O006 | active | INCONCLUSIVE | 1/1 | $137.91/$140 | The thermal L2 reference matches converged analytic solutions and an independent FEM, and design pilots measure what O002-O004 must fix |
| O007 | passed | PASS | 1/1 | $92.55/$110 | The scikit-fem thermal reference matches converged analytic solutions and the in-house finite-volume L2 on generator layouts |
| O901 | passed | PASS | 1/2 | $9.19/$30 | Infrastructure canary v2 - a known answer through registered, sealed, recomputed and null-checked evidence |

## Usage (from run records)
| objective | runs | usd | output tokens | thinking | denials | limit hits |
|---|---|---|---|---|---|---|
| O002 | 6 | $11.44 | 293351 | 180601 | 28 | 0 |
| O003 | 48 | $79.45 | 1557179 | 840879 | 78 | 0 |
| O004 | 6 | $9.51 | 225161 | 160260 | 17 | 0 |
| O005 | 4 | $7.65 | 185443 | 108670 | 29 | 0 |
| O006 | 69 | $137.91 | 2633380 | 1435121 | 137 | 0 |
| O007 | 50 | $92.55 | 1684141 | 838123 | 79 | 1 |
| O901 | 3 | $5.05 | 101607 | 52842 | 14 | 0 |

## Tasks
cancelled: 38, done: 244, failed: 3, needs_founder: 1, review: 1, running: 2, todo: 3

- T0285 `needs_founder` builder/implement: Search driver: one band-based e_R estimator, atomic checkpoint repair, bounded thermal records (review T0284) (attempt 1)
- T0287 `review` builder/implement: Twin/degrade: degradation always reaches 1.25 (1 + margin >= 0.11), merged-band split, exact-mode DRC (review T0286) (attempt 1)
- T0290 `running` builder/implement: Generator: DRC-consistent float tolerance in _quick_ok, tests that fail without the fixes (review T0288) (attempt 1)
- T0291 `running` critic/review: Review T0287 (general) (attempt 1)

## Recent events
- 2026-11-10T02:22:01+00:00 task_added {"task": "T0290", "reason": "review T0288 follow-up (_quick_ok tolerance, effective tests)"}
- 2026-11-10T02:22:01+00:00 task_amended {"task": "T0262", "reason": "waits for T0290; L1 screen throughput (T0288)"}
- 2026-11-10T02:27:52+00:00 inbox_opened {"id": "I0155", "kind": "protected_change", "subject": "T0282: merge needs founder approval"}
- 2026-11-10T02:28:32+00:00 sleep_detected {"gap_s": 429, "runs_extended": 2}
- 2026-11-10T02:29:44+00:00 inbox_resolved {"id": "I0155", "status": "approved", "note": "Merge T0282: foot-sampler float tolerance, scoped proofs, re-measured throughput; T0288 accepts with caveats; DRC
- 2026-11-10T02:30:00+00:00 merged {"task": "T0282"}
- 2026-11-10T02:30:05+00:00 run_started {"run": "T0290-builder-20261109T183005-35cf", "task": "T0290", "role": "builder", "session": "f16dffb8-15f3-476f-977f-5d855107ff6d"}
- 2026-11-10T02:32:00+00:00 run_finished {"run": "T0287-builder-20261109T173549-3fe8", "status": "completed", "cost": 1.244318, "subtype": "success", "report": "structured_output"}
- 2026-11-10T02:50:14+00:00 verified {"task": "T0287"}
- 2026-11-10T02:50:20+00:00 run_started {"run": "T0291-critic-20261109T185020-28d2", "task": "T0291", "role": "critic", "session": "a920280d-669d-40c0-a894-fd1b0910b94d"}
- 2026-11-10T02:50:55+00:00 sleep_detected {"gap_s": 1136, "runs_extended": 3}
- 2026-11-10T02:50:56+00:00 run_finished {"run": "T0289-critic-20261109T182048-9416", "status": "completed", "cost": 1.906882, "subtype": "success", "report": "structured_output"}
- 2026-11-10T02:51:28+00:00 task_added {"task": "T0292", "reason": "review T0289 follow-up (estimator import, near-tie window)"}
- 2026-11-10T02:51:28+00:00 task_amended {"task": "T0262", "reason": "waits for T0292 (driver, review T0289)"}
- 2026-11-10T02:56:49+00:00 inbox_opened {"id": "I0156", "kind": "protected_change", "subject": "T0285: merge needs founder approval"}
