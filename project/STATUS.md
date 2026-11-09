# ModuleForge status
_generated 2026-11-09T08:02:37+00:00 from repository state — do not edit_

## Founder inbox (2 open)
- **I0140** [question] [O003] Reference set on 2026-11-12 (D0010): customer layouts or public fallback
- **I0142** [protected_change] T0257: merge needs founder approval

## Objectives
| id | status | verdict | evals | spent | title |
|---|---|---|---|---|---|
| O000 | passed | PASS | 1/2 | $0.50/$20 | Framework canary — the loop carries a known-answer hypothesis from plan to verdict |
| O001 | passed | PASS | 1/3 | $287.86/$315 | L1 PEEC ranks half-bridge layouts faithfully enough to drive layout search |
| O002 | draft | - | 0/1 | $11.44/$120 | A fast L1 thermal model predicts per-die Tj max, spread and layout-to-layout differences well enough to drive search |
| O003 | active | - | 0/1 | $18.79/$250 | Reference wire-bonded half-bridge layouts leave >= 20 % loop-inductance headroom inside their own housing at <= +2 K Tj |
| O004 | draft | - | 0/1 | $9.51/$100 | The L2 inductance reference is accurate on reconstructed public modules, so it can judge O003's headroom |
| O005 | draft | - | 0/2 | $7.65/$60 | L1 picks near-best layouts within a fixed family and die count, the regime derivative re-layout searches |
| O006 | active | INCONCLUSIVE | 1/1 | $137.91/$140 | The thermal L2 reference matches converged analytic solutions and an independent FEM, and design pilots measure what O002-O004 must fix |
| O007 | passed | PASS | 1/1 | $92.55/$110 | The scikit-fem thermal reference matches converged analytic solutions and the in-house finite-volume L2 on generator layouts |
| O901 | passed | PASS | 1/2 | $9.19/$30 | Infrastructure canary v2 - a known answer through registered, sealed, recomputed and null-checked evidence |

## Usage (from run records)
| objective | runs | usd | output tokens | thinking | denials | limit hits |
|---|---|---|---|---|---|---|
| O002 | 6 | $11.44 | 293351 | 180601 | 28 | 0 |
| O003 | 14 | $18.79 | 412893 | 258074 | 14 | 0 |
| O004 | 6 | $9.51 | 225161 | 160260 | 17 | 0 |
| O005 | 4 | $7.65 | 185443 | 108670 | 29 | 0 |
| O006 | 69 | $137.91 | 2633380 | 1435121 | 137 | 0 |
| O007 | 50 | $92.55 | 1684141 | 838123 | 79 | 1 |
| O901 | 3 | $5.05 | 101607 | 52842 | 14 | 0 |

## Tasks
cancelled: 38, done: 215, failed: 3, needs_founder: 1, review: 1, running: 2, todo: 5

- T0256 `review` builder/implement: Per-net design rules, gate/Kelvin signal wires, bondability DRC and rule measurement (attempt 1)
- T0257 `needs_founder` builder/implement: AlN k(T) law in stack.py and the frozen grid-snapping rule (attempt 1)
- T0261 `running` scientist/design_experiment: Draft headroom_min_lo / headroom_max_hi_ind (protected mfos.metrics) and the E008 row contract (attempt 1)
- T0265 `running` critic/review: Review T0256 (general) (attempt 1)

## Recent events
- 2026-11-09T07:28:33+00:00 inbox_resolved {"id": "I0141", "status": "approved", "note": "Plan approved (T0256-T0263): build chain on generator housings and 2D_Case_4 per F3; public reconstructions after
- 2026-11-09T07:28:39+00:00 inbox_resolved {"id": "I0138", "status": "approved", "note": "E008 added to burst_experiments; VM time reserved for the full-fidelity dev rows once the E008 design merges.", "
- 2026-11-09T07:28:46+00:00 inbox_resolved {"id": "I0139", "status": "approved", "note": "thermal_fem.py confirmed at a216d5fe (EV-O007-01 bytes, revert dd9727cc); metrics patch to be applied on T0261's 
- 2026-11-09T07:28:46+00:00 run_started {"run": "T0256-builder-20261108T232846-aecb", "task": "T0256", "role": "builder", "session": "4d03165a-cd3e-44be-8f98-60f8bbcf2f02"}
- 2026-11-09T07:28:46+00:00 run_started {"run": "T0257-builder-20261108T232846-46d1", "task": "T0257", "role": "builder", "session": "a3123393-042c-41fe-b0b7-78edbd27c4bf"}
- 2026-11-09T07:40:58+00:00 run_finished {"run": "T0257-builder-20261108T232846-46d1", "status": "completed", "cost": 0.668016, "subtype": "success", "report": "structured_output"}
- 2026-11-09T07:46:03+00:00 verified {"task": "T0257"}
- 2026-11-09T07:46:10+00:00 run_started {"run": "T0264-critic-20261108T234610-ec0e", "task": "T0264", "role": "critic", "session": "21868d9f-58be-46e4-8007-1ce89871029b"}
- 2026-11-09T07:46:43+00:00 sleep_detected {"gap_s": 347, "runs_extended": 2}
- 2026-11-09T07:52:24+00:00 run_finished {"run": "T0264-critic-20261108T234610-ec0e", "status": "completed", "cost": 1.756902, "subtype": "success", "report": "structured_output"}
- 2026-11-09T07:52:29+00:00 inbox_opened {"id": "I0142", "kind": "protected_change", "subject": "T0257: merge needs founder approval"}
- 2026-11-09T07:52:34+00:00 run_started {"run": "T0261-scientist-20261108T235234-8ffb", "task": "T0261", "role": "scientist", "session": "854ae221-ae2f-4388-9e26-2600ca558dc0"}
- 2026-11-09T07:55:01+00:00 run_finished {"run": "T0256-builder-20261108T232846-aecb", "status": "completed", "cost": 1.15678, "subtype": "success", "report": "structured_output"}
- 2026-11-09T08:02:32+00:00 verified {"task": "T0256"}
- 2026-11-09T08:02:37+00:00 run_started {"run": "T0265-critic-20261109T000237-c0eb", "task": "T0265", "role": "critic", "session": "06f33d6f-2800-49e5-a626-1bd2206de9f0"}
