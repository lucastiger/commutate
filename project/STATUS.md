# ModuleForge status
_generated 2026-11-02T05:08:05+00:00 from repository state — do not edit_

## Founder inbox (3 open)
- **I0066** [external_action] [O006] P3 burst VM run of the missing 0.25/0.125 mm l2_layout levels (T0154 diagnosis)
- **I0074** [protected_change] T0157: merge needs founder approval
- **I0075** [protected_change] T0164: merge needs founder approval

## Objectives
| id | status | verdict | evals | spent | title |
|---|---|---|---|---|---|
| O000 | passed | PASS | 1/2 | $0.50/$20 | Framework canary — the loop carries a known-answer hypothesis from plan to verdict |
| O001 | passed | PASS | 1/3 | $287.86/$315 | L1 PEEC ranks half-bridge layouts faithfully enough to drive layout search |
| O002 | draft | - | 0/1 | $11.44/$120 | A fast L1 thermal model predicts per-die Tj max, spread and layout-to-layout differences well enough to drive search |
| O003 | draft | - | 0/1 | $5.89/$150 | Reference wire-bonded half-bridge layouts leave >= 20 % loop-inductance headroom inside their own housing at <= +2 K Tj |
| O004 | draft | - | 0/1 | $9.51/$100 | The L2 inductance reference is accurate on reconstructed public modules, so it can judge O003's headroom |
| O005 | draft | - | 0/2 | $7.65/$60 | L1 picks near-best layouts within a fixed family and die count, the regime derivative re-layout searches |
| O006 | active | - | 0/1 | $71.02/$115 | The thermal L2 reference matches converged analytic solutions and an independent FEM, and design pilots measure what O002-O004 must fix |
| O901 | passed | PASS | 1/2 | $9.19/$30 | Infrastructure canary v2 - a known answer through registered, sealed, recomputed and null-checked evidence |

## Usage (from run records)
| objective | runs | usd | output tokens | thinking | denials | limit hits |
|---|---|---|---|---|---|---|
| O002 | 6 | $11.44 | 293351 | 180601 | 28 | 0 |
| O003 | 4 | $5.89 | 136620 | 96498 | 8 | 0 |
| O004 | 6 | $9.51 | 225161 | 160260 | 17 | 0 |
| O005 | 4 | $7.65 | 185443 | 108670 | 29 | 0 |
| O006 | 40 | $71.02 | 1564799 | 852594 | 55 | 0 |
| O901 | 3 | $5.05 | 101607 | 52842 | 14 | 0 |

## Tasks
cancelled: 30, done: 136, failed: 3, merge: 1, needs_founder: 2, review: 1, running: 1, todo: 5

- T0155 `merge` scientist/investigate: Pilot P4: FastHenry feasibility on 2D_Case_4 via a Layout-to-FastHenry exporter (research note, not evidence) (attempt 1)
- T0157 `needs_founder` scout/research: Secondary-source screen of every k(T) law and 300 K value in geometry/stack.py (primary check deferred) (attempt 3)
- T0164 `needs_founder` scientist/research: E006 analytic references (re-issue of T0151): paper-reproduction gate matching frozen F1 (Case 3 only), payload hash pinned (attempt 1)
- T0170 `review` builder/implement: Thermal grid rule: refine thin layers and edges, fix level0, prove GCI is conservative (A4; reviews T0168/T0169) (attempt 1)
- T0178 `running` critic/review: Review T0170 (physics) (attempt 1)

## Recent events
- 2026-11-02T04:02:47+00:00 run_finished {"run": "T0157-scout-20261101T200059-95a3", "status": "completed", "cost": 0.318994, "subtype": "success", "report": "structured_output"}
- 2026-11-02T04:03:28+00:00 verified {"task": "T0157"}
- 2026-11-02T04:03:33+00:00 run_started {"run": "T0177-critic-20261101T200333-2bd6", "task": "T0177", "role": "critic", "session": "8271ffd2-1c55-4ab1-8363-cc4ad544bb7c"}
- 2026-11-02T04:08:50+00:00 run_finished {"run": "T0177-critic-20261101T200333-2bd6", "status": "completed", "cost": 1.323057, "subtype": "success", "report": "structured_output"}
- 2026-11-02T04:09:37+00:00 inbox_opened {"id": "I0074", "kind": "protected_change", "subject": "T0157: merge needs founder approval"}
- 2026-11-02T04:09:41+00:00 run_started {"run": "T0164-scientist-20261101T200941-306f", "task": "T0164", "role": "scientist", "session": "948820b8-8023-4c11-b4fc-11ed3b22783c"}
- 2026-11-02T04:17:05+00:00 run_finished {"run": "T0164-scientist-20261101T200941-306f", "status": "completed", "cost": 1.118278, "subtype": "success", "report": "structured_output"}
- 2026-11-02T04:19:22+00:00 verified {"task": "T0164"}
- 2026-11-02T04:19:25+00:00 inbox_opened {"id": "I0075", "kind": "protected_change", "subject": "T0164: merge needs founder approval"}
- 2026-11-02T04:19:27+00:00 run_started {"run": "T0170-builder-20261101T201927-4128", "task": "T0170", "role": "builder", "session": "e32359d2-3c30-4bec-960e-df6c235ef8d3"}
- 2026-11-02T05:01:27+00:00 run_finished {"run": "T0170-builder-20261101T201927-4128", "status": "completed", "cost": 1.639743, "subtype": "success", "report": "structured_output"}
- 2026-11-02T05:03:54+00:00 verified {"task": "T0170"}
- 2026-11-02T05:03:58+00:00 run_started {"run": "T0178-critic-20261101T210358-a9cd", "task": "T0178", "role": "critic", "session": "8f64c3f5-74d2-4a1b-8573-392a9c8e44df"}
- 2026-11-02T05:07:01+00:00 run_finished {"run": "T0155-scientist-20261101T192217-0866", "status": "completed", "cost": 4.372007, "subtype": "success", "report": "structured_output"}
- 2026-11-02T05:07:40+00:00 verified {"task": "T0155"}
