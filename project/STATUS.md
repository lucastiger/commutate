# ModuleForge status
_generated 2026-11-09T22:45:54+00:00 from repository state — do not edit_

## Founder inbox (4 open)
- **I0140** [question] [O003] Reference set on 2026-11-12 (D0010): customer layouts or public fallback
- **I0151** [protected_change] T0274: merge needs founder approval
- **I0152** [protected_change] T0276: merge needs founder approval
- **I0153** [protected_change] T0279: merge needs founder approval

## Objectives
| id | status | verdict | evals | spent | title |
|---|---|---|---|---|---|
| O000 | passed | PASS | 1/2 | $0.50/$20 | Framework canary — the loop carries a known-answer hypothesis from plan to verdict |
| O001 | passed | PASS | 1/3 | $287.86/$315 | L1 PEEC ranks half-bridge layouts faithfully enough to drive layout search |
| O002 | draft | - | 0/1 | $11.44/$120 | A fast L1 thermal model predicts per-die Tj max, spread and layout-to-layout differences well enough to drive search |
| O003 | active | - | 0/1 | $68.50/$250 | Reference wire-bonded half-bridge layouts leave >= 20 % loop-inductance headroom inside their own housing at <= +2 K Tj |
| O004 | draft | - | 0/1 | $9.51/$100 | The L2 inductance reference is accurate on reconstructed public modules, so it can judge O003's headroom |
| O005 | draft | - | 0/2 | $7.65/$60 | L1 picks near-best layouts within a fixed family and die count, the regime derivative re-layout searches |
| O006 | active | INCONCLUSIVE | 1/1 | $137.91/$140 | The thermal L2 reference matches converged analytic solutions and an independent FEM, and design pilots measure what O002-O004 must fix |
| O007 | passed | PASS | 1/1 | $92.55/$110 | The scikit-fem thermal reference matches converged analytic solutions and the in-house finite-volume L2 on generator layouts |
| O901 | passed | PASS | 1/2 | $9.19/$30 | Infrastructure canary v2 - a known answer through registered, sealed, recomputed and null-checked evidence |

## Usage (from run records)
| objective | runs | usd | output tokens | thinking | denials | limit hits |
|---|---|---|---|---|---|---|
| O002 | 6 | $11.44 | 293351 | 180601 | 28 | 0 |
| O003 | 40 | $68.50 | 1321265 | 732420 | 66 | 0 |
| O004 | 6 | $9.51 | 225161 | 160260 | 17 | 0 |
| O005 | 4 | $7.65 | 185443 | 108670 | 29 | 0 |
| O006 | 69 | $137.91 | 2633380 | 1435121 | 137 | 0 |
| O007 | 50 | $92.55 | 1684141 | 838123 | 79 | 1 |
| O901 | 3 | $5.05 | 101607 | 52842 | 14 | 0 |

## Tasks
cancelled: 38, done: 236, failed: 3, needs_founder: 3, running: 2, todo: 3

- T0259 `running` builder/implement: Twin construction and degradation rule (F1(a), F1(b)) (attempt 1)
- T0274 `needs_founder` builder/implement: Snapping: full DRC re-check with induced/pre-existing labels, docstring fixes (review T0272) (attempt 2)
- T0276 `needs_founder` scientist/design_experiment: Headroom metrics: fail-closed parameter values and two untested branches (review T0275) (attempt 1)
- T0279 `needs_founder` builder/implement: Search driver: exact L1-only null, w_ctrl without s_ref, e_R for A1 best and near ties, full thermal checkpoint (review T0278) (attempt 1)
- T0282 `running` builder/implement: Generator: foot-sampler float tolerance, topology-count proof scope, throughput (review T0281) (attempt 1)

## Recent events
- 2026-11-09T21:49:57+00:00 sleep_detected {"gap_s": 1182, "runs_extended": 2}
- 2026-11-09T21:49:59+00:00 run_finished {"run": "T0279-builder-20261109T125534-34cd", "status": "completed", "cost": 0.68255, "subtype": "success", "report": "structured_output"}
- 2026-11-09T22:00:40+00:00 verified {"task": "T0279"}
- 2026-11-09T22:00:40+00:00 run_finished {"run": "T0283-critic-20261109T132940-0900", "status": "completed", "cost": 2.321661, "subtype": "success", "report": "structured_output"}
- 2026-11-09T22:04:30+00:00 inbox_opened {"id": "I0152", "kind": "protected_change", "subject": "T0276: merge needs founder approval"}
- 2026-11-09T22:04:35+00:00 run_started {"run": "T0284-critic-20261109T140435-5320", "task": "T0284", "role": "critic", "session": "70a2c165-1131-4a41-affe-6155dd64a875"}
- 2026-11-09T22:05:08+00:00 sleep_detected {"gap_s": 911, "runs_extended": 1}
- 2026-11-09T22:11:23+00:00 run_finished {"run": "T0284-critic-20261109T140435-5320", "status": "completed", "cost": 2.383736, "subtype": "success", "report": "structured_output"}
- 2026-11-09T22:15:04+00:00 inbox_opened {"id": "I0153", "kind": "protected_change", "subject": "T0279: merge needs founder approval"}
- 2026-11-09T22:41:41+00:00 inbox_resolved {"id": "I0150", "status": "approved", "note": "Merge T0273: searchable wire feet and multi-wire dies with gate/Kelvin copper; T0281 accepts with caveats; the sa
- 2026-11-09T22:42:55+00:00 task_added {"task": "T0285", "reason": "review T0284 follow-up (driver e_R consistency, checkpoint)"}
- 2026-11-09T22:42:55+00:00 task_amended {"task": "T0262", "reason": "waits for T0285; spec checks from T0283/T0284"}
- 2026-11-09T22:45:50+00:00 merged {"task": "T0273"}
- 2026-11-09T22:45:54+00:00 run_started {"run": "T0259-builder-20261109T144554-9b86", "task": "T0259", "role": "builder", "session": "e721df1d-7eba-4ec6-91c0-69fcf576492a"}
- 2026-11-09T22:45:54+00:00 run_started {"run": "T0282-builder-20261109T144554-a09a", "task": "T0282", "role": "builder", "session": "c9f9250f-ea94-4e39-a24c-d1e04d1c344e"}
