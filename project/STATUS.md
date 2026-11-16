# ModuleForge status
_generated 2026-11-16T13:36:01+00:00 from repository state — do not edit_

## Founder inbox (10 open)
- **I0205** [external_action] [O008] Burst VM for E011's development L2 draws (band bound, joint operating characteristic, dev rows)
- **I0209** [external_action] [O004] O004: two F7 burst-VM runs before E004 registration, and a budget warning
- **I0212** [external_action] [O002] Burst VM run of n2's level-2 development solves (F1 pre-registration check)
- **I0215** [protected_change] T0377: merge needs founder approval
- **I0216** [protected_change] T0376: merge needs founder approval
- **I0217** [decision] T0386 blocked: the agent reports the task impossible or mis-specified
- **I0218** [decision] T0384: 2 review rounds rejected; your call
- **I0219** [protected_change] T0392: merge needs founder approval
- **I0220** [protected_change] T0394: merge needs founder approval
- **I0221** [protected_change] T0393: merge needs founder approval

## Objectives
| id | status | verdict | evals | spent | title |
|---|---|---|---|---|---|
| O000 | passed | PASS | 1/2 | $0.50/$20 | Framework canary — the loop carries a known-answer hypothesis from plan to verdict |
| O001 | passed | PASS | 1/3 | $287.86/$315 | L1 PEEC ranks half-bridge layouts faithfully enough to drive layout search |
| O002 | active | - | 0/1 | $33.79/$120 | A fast L1 thermal model predicts each die's average junction temperature, the spread across paralleled dies and layout-to-layout differences well enough to drive search |
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
| O002 | 16 | $33.79 | 746698 | 435011 | 51 | 0 |
| O003 | 135 | $258.22 | 4105839 | 2002393 | 280 | 0 |
| O004 | 24 | $42.95 | 941817 | 611635 | 61 | 0 |
| O005 | 4 | $7.65 | 185443 | 108670 | 29 | 0 |
| O006 | 69 | $137.91 | 2633380 | 1435121 | 137 | 0 |
| O007 | 50 | $92.55 | 1684141 | 838123 | 79 | 1 |
| O008 | 19 | $38.15 | 846743 | 525848 | 68 | 0 |
| O901 | 3 | $5.05 | 101607 | 52842 | 14 | 0 |

## Tasks
cancelled: 44, done: 340, failed: 4, needs_founder: 7, todo: 16

- T0376 `needs_founder` scientist/investigate: Kill shot: do the probe's designer proxy and its null gap survive l2_layout? (attempt 1)
- T0377 `needs_founder` builder/implement: Reach: straddling slots, column outer edges to the edge margin, and the in_domain predicate (attempt 1)
- T0384 `needs_founder` builder/implement: FastHenry deck exporter in src: Layout -> SI-metre deck with refinable wire section, thickness and plane knobs, F6 model variants (attempt 2)
- T0386 `needs_founder` builder/implement: Frozen perturbation rules on the 1 mm lattice: die-row shift, power-trace width, terminal-near copper, wire landing (generate/perturb.py) (attempt 2)
- T0392 `needs_founder` scientist/investigate: L1 thermal design study on development layouts: speed and accuracy of candidate fast models against the level-1 reference, plus early F2 null check (attempt 1)
- T0393 `needs_founder` scientist/investigate: F1 pre-registration check: three-level convergence of die averages, spreads and pair differences on C004's development layouts at P_ref and 0.5 P_ref (attempt 1)
- T0394 `needs_founder` builder/implement: Generator option: one fixed die size per stratum (die_size_mm), random stream and default output unchanged (attempt 1)

## Recent events
- 2026-11-16T06:31:04+00:00 run_finished {"run": "T0392-scientist-20261115T210153-32f5", "status": "completed", "cost": 3.390652, "subtype": "success", "report": "structured_output"}
- 2026-11-16T06:39:32+00:00 verified {"task": "T0392"}
- 2026-11-16T06:39:43+00:00 run_started {"run": "T0410-critic-20261115T223943-35d0", "task": "T0410", "role": "critic", "session": "c34daeee-9641-462f-b359-7dac05f0508a"}
- 2026-11-16T06:40:19+00:00 sleep_detected {"gap_s": 556, "runs_extended": 3}
- 2026-11-16T06:46:30+00:00 run_finished {"run": "T0410-critic-20261115T223943-35d0", "status": "completed", "cost": 2.134583, "subtype": "success", "report": "structured_output"}
- 2026-11-16T06:46:36+00:00 inbox_opened {"id": "I0219", "kind": "protected_change", "subject": "T0392: merge needs founder approval"}
- 2026-11-16T06:48:08+00:00 run_finished {"run": "T0393-scientist-20261115T215858-56d2", "status": "completed", "cost": 4.016277, "subtype": "success", "report": "structured_output"}
- 2026-11-16T06:54:21+00:00 verified {"task": "T0393"}
- 2026-11-16T06:54:21+00:00 run_finished {"run": "T0394-builder-20261115T221542-879d", "status": "completed", "cost": 0.337095, "subtype": "success", "report": "structured_output"}
- 2026-11-16T07:09:43+00:00 verified {"task": "T0394"}
- 2026-11-16T07:09:48+00:00 inbox_opened {"id": "I0220", "kind": "protected_change", "subject": "T0394: merge needs founder approval"}
- 2026-11-16T07:09:55+00:00 run_started {"run": "T0411-critic-20261115T230955-ace3", "task": "T0411", "role": "critic", "session": "20071fe9-29f4-4bb0-88d9-8c0558374fd4"}
- 2026-11-16T07:10:29+00:00 sleep_detected {"gap_s": 1342, "runs_extended": 1}
- 2026-11-16T07:15:58+00:00 run_finished {"run": "T0411-critic-20261115T230955-ace3", "status": "completed", "cost": 2.181931, "subtype": "success", "report": "structured_output"}
- 2026-11-16T07:16:03+00:00 inbox_opened {"id": "I0221", "kind": "protected_change", "subject": "T0393: merge needs founder approval"}
