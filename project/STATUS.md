# ModuleForge status
_generated 2026-11-02T00:25:35+00:00 from repository state — do not edit_

## Founder inbox (0 open)
- nothing needs you

## Objectives
| id | status | verdict | evals | spent | title |
|---|---|---|---|---|---|
| O000 | passed | PASS | 1/2 | $0.50/$20 | Framework canary — the loop carries a known-answer hypothesis from plan to verdict |
| O001 | passed | PASS | 1/3 | $287.86/$315 | L1 PEEC ranks half-bridge layouts faithfully enough to drive layout search |
| O002 | draft | - | 0/1 | $11.44/$120 | A fast L1 thermal model predicts per-die Tj max, spread and layout-to-layout differences well enough to drive search |
| O003 | draft | - | 0/1 | $5.89/$150 | Reference wire-bonded half-bridge layouts leave >= 20 % loop-inductance headroom inside their own housing at <= +2 K Tj |
| O004 | draft | - | 0/1 | $9.51/$100 | The L2 inductance reference is accurate on reconstructed public modules, so it can judge O003's headroom |
| O005 | draft | - | 0/2 | $7.65/$60 | L1 picks near-best layouts within a fixed family and die count, the regime derivative re-layout searches |
| O006 | active | - | 0/1 | $20.70/$90 | The thermal L2 reference matches converged analytic solutions and an independent FEM, and design pilots measure what O002-O004 must fix |
| O901 | passed | PASS | 1/2 | $9.19/$30 | Infrastructure canary v2 - a known answer through registered, sealed, recomputed and null-checked evidence |

## Usage (from run records)
| objective | runs | usd | output tokens | thinking | denials | limit hits |
|---|---|---|---|---|---|---|
| O002 | 6 | $11.44 | 293351 | 180601 | 28 | 0 |
| O003 | 4 | $5.89 | 136620 | 96498 | 8 | 0 |
| O004 | 6 | $9.51 | 225161 | 160260 | 17 | 0 |
| O005 | 4 | $7.65 | 185443 | 108670 | 29 | 0 |
| O006 | 14 | $20.70 | 517348 | 321966 | 22 | 0 |
| O901 | 3 | $5.05 | 101607 | 52842 | 14 | 0 |

## Tasks
cancelled: 29, done: 119, failed: 3, running: 2, todo: 6

- T0149 `running` builder/implement: Thermal L2 core: steady finite-volume conduction on a non-uniform rectilinear grid with k(T) Picard (solvers/thermal_fv.py) (attempt 2)
- T0154 `running` scientist/investigate: Pilot P3: l2_layout discretisation on PowerSynth 2D_Case_4 and two perturbations (research note, not evidence) (attempt 1)

## Recent events
- 2026-11-01T22:55:04+00:00 run_started {"run": "T0156-critic-20261101T145504-e069", "task": "T0156", "role": "critic", "session": "ef1f4388-6257-458c-9818-b4d463a9f0cc"}
- 2026-11-01T23:00:40+00:00 run_finished {"run": "T0156-critic-20261101T145504-e069", "status": "completed", "cost": 1.913495, "subtype": "success", "report": "structured_output"}
- 2026-11-01T23:00:44+00:00 inbox_opened {"id": "I0061", "kind": "protected_change", "subject": "T0148: merge needs founder approval"}
- 2026-11-01T23:06:30+00:00 inbox_resolved {"id": "I0061", "status": "approved", "note": "Approved with founder-session fixes 0e649fa for review T0156 (BC sign, Al2O3 table law, SAC305 slope, NaN guard).
- 2026-11-01T23:06:43+00:00 task_added {"task": "T0157"}
- 2026-11-01T23:06:46+00:00 merged {"task": "T0148"}
- 2026-11-01T23:06:48+00:00 run_started {"run": "T0149-builder-20261101T150648-59a5", "task": "T0149", "role": "builder", "session": "cfdd279b-60d9-4f48-ae4e-4f21dc9d906f"}
- 2026-11-01T23:48:38+00:00 run_finished {"run": "T0149-builder-20261101T150648-59a5", "status": "completed", "cost": 1.114816, "subtype": "success", "report": "structured_output"}
- 2026-11-01T23:50:34+00:00 verified {"task": "T0149"}
- 2026-11-01T23:50:39+00:00 run_started {"run": "T0158-critic-20261101T155039-10fb", "task": "T0158", "role": "critic", "session": "8bc7e921-cb22-49db-8682-be4d16e4f13f"}
- 2026-11-01T23:59:05+00:00 run_finished {"run": "T0158-critic-20261101T155039-10fb", "status": "completed", "cost": 1.732983, "subtype": "success", "report": "structured_output"}
- 2026-11-01T23:59:09+00:00 run_started {"run": "T0159-critic-20261101T155909-04e5", "task": "T0159", "role": "critic", "session": "bb25986f-ebcd-4566-b365-c7206fdc0cbc"}
- 2026-11-02T00:10:27+00:00 run_finished {"run": "T0159-critic-20261101T155909-04e5", "status": "completed", "cost": 1.86505, "subtype": "success", "report": "structured_output"}
- 2026-11-02T00:25:33+00:00 task_failed_attempt {"task": "T0149", "signal": "gate_failed", "action": "repair"}
- 2026-11-02T00:25:35+00:00 run_started {"run": "T0149-builder-20261101T162535-8e18", "task": "T0149", "role": "builder", "session": "52e3ed90-fcc9-41a3-b0c4-c8fadc196c7c"}
