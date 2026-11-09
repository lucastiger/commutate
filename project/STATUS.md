# ModuleForge status
_generated 2026-11-09T15:43:52+00:00 from repository state — do not edit_

## Founder inbox (1 open)
- **I0140** [question] [O003] Reference set on 2026-11-12 (D0010): customer layouts or public fallback

## Objectives
| id | status | verdict | evals | spent | title |
|---|---|---|---|---|---|
| O000 | passed | PASS | 1/2 | $0.50/$20 | Framework canary — the loop carries a known-answer hypothesis from plan to verdict |
| O001 | passed | PASS | 1/3 | $287.86/$315 | L1 PEEC ranks half-bridge layouts faithfully enough to drive layout search |
| O002 | draft | - | 0/1 | $11.44/$120 | A fast L1 thermal model predicts per-die Tj max, spread and layout-to-layout differences well enough to drive search |
| O003 | active | - | 0/1 | $34.35/$250 | Reference wire-bonded half-bridge layouts leave >= 20 % loop-inductance headroom inside their own housing at <= +2 K Tj |
| O004 | draft | - | 0/1 | $9.51/$100 | The L2 inductance reference is accurate on reconstructed public modules, so it can judge O003's headroom |
| O005 | draft | - | 0/2 | $7.65/$60 | L1 picks near-best layouts within a fixed family and die count, the regime derivative re-layout searches |
| O006 | active | INCONCLUSIVE | 1/1 | $137.91/$140 | The thermal L2 reference matches converged analytic solutions and an independent FEM, and design pilots measure what O002-O004 must fix |
| O007 | passed | PASS | 1/1 | $92.55/$110 | The scikit-fem thermal reference matches converged analytic solutions and the in-house finite-volume L2 on generator layouts |
| O901 | passed | PASS | 1/2 | $9.19/$30 | Infrastructure canary v2 - a known answer through registered, sealed, recomputed and null-checked evidence |

## Usage (from run records)
| objective | runs | usd | output tokens | thinking | denials | limit hits |
|---|---|---|---|---|---|---|
| O002 | 6 | $11.44 | 293351 | 180601 | 28 | 0 |
| O003 | 20 | $34.35 | 715817 | 412154 | 31 | 0 |
| O004 | 6 | $9.51 | 225161 | 160260 | 17 | 0 |
| O005 | 4 | $7.65 | 185443 | 108670 | 29 | 0 |
| O006 | 69 | $137.91 | 2633380 | 1435121 | 137 | 0 |
| O007 | 50 | $92.55 | 1684141 | 838123 | 79 | 1 |
| O901 | 3 | $5.05 | 101607 | 52842 | 14 | 0 |

## Tasks
cancelled: 38, done: 221, failed: 3, running: 2, todo: 6

- T0258 `running` builder/implement: Generalised derivative-layout generator inside a reference's housing (attempt 1)
- T0268 `running` builder/implement: Snapping rule and AlN law fixes from review T0264 (before E008's design) (attempt 1)

## Recent events
- 2026-11-09T15:17:13+00:00 inbox_resolved {"id": "I0143", "status": "approved", "note": "Merge T0261 (research drafts only): T0266 accepts with caveats. The protected metrics patch is NOT applied until 
- 2026-11-09T15:17:14+00:00 sleep_detected {"gap_s": 1403, "runs_extended": 0}
- 2026-11-09T15:17:19+00:00 task_added {"task": "T0268"}
- 2026-11-09T15:17:19+00:00 task_added {"task": "T0269"}
- 2026-11-09T15:17:20+00:00 merged {"task": "T0257"}
- 2026-11-09T15:20:40+00:00 merged {"task": "T0261"}
- 2026-11-09T15:20:44+00:00 run_started {"run": "T0268-builder-20261109T072044-ab09", "task": "T0268", "role": "builder", "session": "3f2597bf-abac-48c6-91a9-d468911b9adc"}
- 2026-11-09T15:20:44+00:00 run_started {"run": "T0269-builder-20261109T072044-7412", "task": "T0269", "role": "builder", "session": "a9eb87f4-2d35-45df-b37a-bb4b40646287"}
- 2026-11-09T15:21:25+00:00 inbox_resolved {"id": "I0144", "status": "approved", "note": "Merge T0256 attempt 2: per-switch gate/Kelvin nets fix T0265's blocker; T0267 accepts with caveats (signal-to-pow
- 2026-11-09T15:21:30+00:00 task_added {"task": "T0270"}
- 2026-11-09T15:25:53+00:00 merged {"task": "T0256"}
- 2026-11-09T15:41:58+00:00 run_finished {"run": "T0269-builder-20261109T072044-7412", "status": "completed", "cost": 1.028206, "subtype": "success", "report": "structured_output"}
- 2026-11-09T15:41:58+00:00 task_failed_attempt {"task": "T0269", "signal": "scope_violation", "action": "repair"}
- 2026-11-09T15:42:01+00:00 run_started {"run": "T0258-builder-20261109T074201-4b0e", "task": "T0258", "role": "builder", "session": "49b9a6e6-8950-448d-b559-00725c32dfc0"}
- 2026-11-09T15:43:46+00:00 task_amended {"task": "T0269", "reason": "role builder -> scientist: deliverables are in research/o003 (scope_violation)"}
