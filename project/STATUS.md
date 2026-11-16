# ModuleForge status
_generated 2026-11-16T06:16:30+00:00 from repository state — do not edit_

## Founder inbox (7 open)
- **I0205** [external_action] [O008] Burst VM for E011's development L2 draws (band bound, joint operating characteristic, dev rows)
- **I0209** [external_action] [O004] O004: two F7 burst-VM runs before E004 registration, and a budget warning
- **I0212** [external_action] [O002] Burst VM run of n2's level-2 development solves (F1 pre-registration check)
- **I0215** [protected_change] T0377: merge needs founder approval
- **I0216** [protected_change] T0376: merge needs founder approval
- **I0217** [decision] T0386 blocked: the agent reports the task impossible or mis-specified
- **I0218** [decision] T0384: 2 review rounds rejected; your call

## Objectives
| id | status | verdict | evals | spent | title |
|---|---|---|---|---|---|
| O000 | passed | PASS | 1/2 | $0.50/$20 | Framework canary — the loop carries a known-answer hypothesis from plan to verdict |
| O001 | passed | PASS | 1/3 | $287.86/$315 | L1 PEEC ranks half-bridge layouts faithfully enough to drive layout search |
| O002 | active | - | 0/1 | $21.73/$120 | A fast L1 thermal model predicts each die's average junction temperature, the spread across paralleled dies and layout-to-layout differences well enough to drive search |
| O003 | needs_founder | - | 0/1 | $258.22/$265 | Reference wire-bonded half-bridge layouts leave >= 20 % loop-inductance headroom inside their own housing at <= +2 K Tj |
| O004 | active | - | 0/1 | $42.95/$100 | The L2 inductance reference agrees with an independent field solver on the inductance ratios of re-layouts of PowerSynth public sample designs |
| O005 | draft | - | 0/2 | $7.65/$60 | L1 picks near-best layouts within a fixed family and die count, the regime derivative re-layout searches |
| O006 | active | INCONCLUSIVE | 1/1 | $137.91/$140 | The thermal L2 reference matches converged analytic solutions and an independent FEM, and design pilots measure what O002-O004 must fix |
| O007 | passed | PASS | 1/1 | $92.55/$110 | The scikit-fem thermal reference matches converged analytic solutions and the in-house finite-volume L2 on generator layouts |
| O008 | active | - | 0/2 | $38.15/$140 | A search seeded at a degraded copy of a near-optimal layout recovers it, where inductance-blind heuristics do not, on every designer-derived development layout |
| O901 | passed | PASS | 1/2 | $9.19/$30 | Infrastructure canary v2 - a known answer through registered, sealed, recomputed and null-checked evidence |

## Usage (from run records)
| objective | runs | usd | output tokens | thinking | denials | limit hits |
|---|---|---|---|---|---|---|
| O002 | 14 | $21.73 | 540809 | 352965 | 40 | 0 |
| O003 | 135 | $258.22 | 4105839 | 2002393 | 280 | 0 |
| O004 | 24 | $42.95 | 941817 | 611635 | 61 | 0 |
| O005 | 4 | $7.65 | 185443 | 108670 | 29 | 0 |
| O006 | 69 | $137.91 | 2633380 | 1435121 | 137 | 0 |
| O007 | 50 | $92.55 | 1684141 | 838123 | 79 | 1 |
| O008 | 19 | $38.15 | 846743 | 525848 | 68 | 0 |
| O901 | 3 | $5.05 | 101607 | 52842 | 14 | 0 |

## Tasks
cancelled: 44, done: 338, failed: 4, needs_founder: 4, running: 3, todo: 16

- T0376 `needs_founder` scientist/investigate: Kill shot: do the probe's designer proxy and its null gap survive l2_layout? (attempt 1)
- T0377 `needs_founder` builder/implement: Reach: straddling slots, column outer edges to the edge margin, and the in_domain predicate (attempt 1)
- T0384 `needs_founder` builder/implement: FastHenry deck exporter in src: Layout -> SI-metre deck with refinable wire section, thickness and plane knobs, F6 model variants (attempt 2)
- T0386 `needs_founder` builder/implement: Frozen perturbation rules on the 1 mm lattice: die-row shift, power-trace width, terminal-near copper, wire landing (generate/perturb.py) (attempt 2)
- T0392 `running` scientist/investigate: L1 thermal design study on development layouts: speed and accuracy of candidate fast models against the level-1 reference, plus early F2 null check (attempt 1)
- T0393 `running` scientist/investigate: F1 pre-registration check: three-level convergence of die averages, spreads and pair differences on C004's development layouts at P_ref and 0.5 P_ref (attempt 1)
- T0394 `running` builder/implement: Generator option: one fixed die size per stratum (die_size_mm), random stream and default output unchanged (attempt 1)

## Recent events
- 2026-11-16T05:09:30+00:00 run_started {"run": "T0386-builder-20261115T210930-574e", "task": "T0386", "role": "builder", "session": "7988fdfc-bc12-44d2-a173-5c4663dfe8e6"}
- 2026-11-16T05:37:51+00:00 run_finished {"run": "T0384-builder-20261115T210237-57d0", "status": "completed", "cost": 1.790552, "subtype": "success", "report": "structured_output"}
- 2026-11-16T05:47:09+00:00 verified {"task": "T0384"}
- 2026-11-16T05:47:09+00:00 run_finished {"run": "T0386-builder-20261115T210930-574e", "status": "completed", "cost": 2.824165, "subtype": "success", "report": "structured_output"}
- 2026-11-16T05:47:10+00:00 task_blocked {"task": "T0386"}
- 2026-11-16T05:47:10+00:00 inbox_opened {"id": "I0217", "kind": "decision", "subject": "T0386 blocked: the agent reports the task impossible or mis-specified"}
- 2026-11-16T05:47:22+00:00 run_started {"run": "T0408-critic-20261115T214722-e0be", "task": "T0408", "role": "critic", "session": "fab4775f-1c41-4a57-b07b-712bc1fc407d"}
- 2026-11-16T05:47:24+00:00 run_started {"run": "T0409-critic-20261115T214724-9459", "task": "T0409", "role": "critic", "session": "46d9a332-6089-4f16-9db9-2e45e2f77de1"}
- 2026-11-16T05:48:00+00:00 sleep_detected {"gap_s": 611, "runs_extended": 3}
- 2026-11-16T05:58:47+00:00 run_finished {"run": "T0408-critic-20261115T214722-e0be", "status": "completed", "cost": 2.185453, "subtype": "success", "report": "structured_output"}
- 2026-11-16T05:58:58+00:00 run_started {"run": "T0393-scientist-20261115T215858-56d2", "task": "T0393", "role": "scientist", "session": "eb1fcf97-5388-4708-b8ec-84bd43392b24"}
- 2026-11-16T06:15:28+00:00 run_finished {"run": "T0409-critic-20261115T214724-9459", "status": "completed", "cost": 1.890915, "subtype": "success", "report": "structured_output"}
- 2026-11-16T06:15:32+00:00 inbox_opened {"id": "I0218", "kind": "decision", "subject": "T0384: 2 review rounds rejected; your call"}
- 2026-11-16T06:15:32+00:00 review_round_cap {"task": "T0384", "rounds": 2}
- 2026-11-16T06:15:42+00:00 run_started {"run": "T0394-builder-20261115T221542-879d", "task": "T0394", "role": "builder", "session": "14222536-deed-4038-88a5-013298833475"}
