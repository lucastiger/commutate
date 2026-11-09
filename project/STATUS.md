# ModuleForge status
_generated 2026-11-09T15:20:34+00:00 from repository state — do not edit_

## Founder inbox (2 open)
- **I0140** [question] [O003] Reference set on 2026-11-12 (D0010): customer layouts or public fallback
- **I0144** [protected_change] T0256: merge needs founder approval

## Objectives
| id | status | verdict | evals | spent | title |
|---|---|---|---|---|---|
| O000 | passed | PASS | 1/2 | $0.50/$20 | Framework canary — the loop carries a known-answer hypothesis from plan to verdict |
| O001 | passed | PASS | 1/3 | $287.86/$315 | L1 PEEC ranks half-bridge layouts faithfully enough to drive layout search |
| O002 | draft | - | 0/1 | $11.44/$120 | A fast L1 thermal model predicts per-die Tj max, spread and layout-to-layout differences well enough to drive search |
| O003 | active | - | 0/1 | $33.32/$250 | Reference wire-bonded half-bridge layouts leave >= 20 % loop-inductance headroom inside their own housing at <= +2 K Tj |
| O004 | draft | - | 0/1 | $9.51/$100 | The L2 inductance reference is accurate on reconstructed public modules, so it can judge O003's headroom |
| O005 | draft | - | 0/2 | $7.65/$60 | L1 picks near-best layouts within a fixed family and die count, the regime derivative re-layout searches |
| O006 | active | INCONCLUSIVE | 1/1 | $137.91/$140 | The thermal L2 reference matches converged analytic solutions and an independent FEM, and design pilots measure what O002-O004 must fix |
| O007 | passed | PASS | 1/1 | $92.55/$110 | The scikit-fem thermal reference matches converged analytic solutions and the in-house finite-volume L2 on generator layouts |
| O901 | passed | PASS | 1/2 | $9.19/$30 | Infrastructure canary v2 - a known answer through registered, sealed, recomputed and null-checked evidence |

## Usage (from run records)
| objective | runs | usd | output tokens | thinking | denials | limit hits |
|---|---|---|---|---|---|---|
| O002 | 6 | $11.44 | 293351 | 180601 | 28 | 0 |
| O003 | 17 | $33.32 | 670047 | 391736 | 30 | 0 |
| O004 | 6 | $9.51 | 225161 | 160260 | 17 | 0 |
| O005 | 4 | $7.65 | 185443 | 108670 | 29 | 0 |
| O006 | 69 | $137.91 | 2633380 | 1435121 | 137 | 0 |
| O007 | 50 | $92.55 | 1684141 | 838123 | 79 | 1 |
| O901 | 3 | $5.05 | 101607 | 52842 | 14 | 0 |

## Tasks
cancelled: 38, done: 219, failed: 3, merge: 1, needs_founder: 1, todo: 7

- T0256 `needs_founder` builder/implement: Per-net design rules, gate/Kelvin signal wires, bondability DRC and rule measurement (attempt 2)
- T0261 `merge` scientist/design_experiment: Draft headroom_min_lo / headroom_max_hi_ind (protected mfos.metrics) and the E008 row contract (attempt 1)

## Recent events
- 2026-11-09T08:24:43+00:00 run_finished {"run": "T0266-critic-20261109T001733-2e6f", "status": "completed", "cost": 2.304485, "subtype": "success", "report": "structured_output"}
- 2026-11-09T08:24:47+00:00 inbox_opened {"id": "I0143", "kind": "protected_change", "subject": "T0261: merge needs founder approval"}
- 2026-11-09T08:47:56+00:00 run_finished {"run": "T0256-builder-20261109T001733-7d0d", "status": "completed", "cost": 4.146169, "subtype": "success", "report": "structured_output"}
- 2026-11-09T08:55:56+00:00 verified {"task": "T0256"}
- 2026-11-09T08:56:01+00:00 run_started {"run": "T0267-critic-20261109T005601-e161", "task": "T0267", "role": "critic", "session": "fda4c413-fbaf-49f9-88db-8eb5fd6a8fc6"}
- 2026-11-09T08:56:35+00:00 sleep_detected {"gap_s": 520, "runs_extended": 1}
- 2026-11-09T09:02:53+00:00 run_finished {"run": "T0267-critic-20261109T005601-e161", "status": "completed", "cost": 2.114936, "subtype": "success", "report": "structured_output"}
- 2026-11-09T09:02:56+00:00 inbox_opened {"id": "I0144", "kind": "protected_change", "subject": "T0256: merge needs founder approval"}
- 2026-11-09T14:53:50+00:00 sleep_detected {"gap_s": 772, "runs_extended": 0}
- 2026-11-09T15:17:07+00:00 inbox_resolved {"id": "I0142", "status": "approved", "note": "Merge T0257 (AlN law, frozen snapping rule): T0264 accepts with caveats; all addressed in the follow-up builder t
- 2026-11-09T15:17:13+00:00 inbox_resolved {"id": "I0143", "status": "approved", "note": "Merge T0261 (research drafts only): T0266 accepts with caveats. The protected metrics patch is NOT applied until 
- 2026-11-09T15:17:14+00:00 sleep_detected {"gap_s": 1403, "runs_extended": 0}
- 2026-11-09T15:17:19+00:00 task_added {"task": "T0268"}
- 2026-11-09T15:17:19+00:00 task_added {"task": "T0269"}
- 2026-11-09T15:17:20+00:00 merged {"task": "T0257"}
