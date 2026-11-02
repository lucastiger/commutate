# ModuleForge status
_generated 2026-11-02T19:31:43+00:00 from repository state — do not edit_

## Founder inbox (1 open)
- **I0095** [decision] E006 needs burst compute (~3 CPU-h)

## Objectives
| id | status | verdict | evals | spent | title |
|---|---|---|---|---|---|
| O000 | passed | PASS | 1/2 | $0.50/$20 | Framework canary — the loop carries a known-answer hypothesis from plan to verdict |
| O001 | passed | PASS | 1/3 | $287.86/$315 | L1 PEEC ranks half-bridge layouts faithfully enough to drive layout search |
| O002 | draft | - | 0/1 | $11.44/$120 | A fast L1 thermal model predicts per-die Tj max, spread and layout-to-layout differences well enough to drive search |
| O003 | draft | - | 0/1 | $5.89/$150 | Reference wire-bonded half-bridge layouts leave >= 20 % loop-inductance headroom inside their own housing at <= +2 K Tj |
| O004 | draft | - | 0/1 | $9.51/$100 | The L2 inductance reference is accurate on reconstructed public modules, so it can judge O003's headroom |
| O005 | draft | - | 0/2 | $7.65/$60 | L1 picks near-best layouts within a fixed family and die count, the regime derivative re-layout searches |
| O006 | active | - | 0/1 | $131.12/$140 | The thermal L2 reference matches converged analytic solutions and an independent FEM, and design pilots measure what O002-O004 must fix |
| O901 | passed | PASS | 1/2 | $9.19/$30 | Infrastructure canary v2 - a known answer through registered, sealed, recomputed and null-checked evidence |

## Usage (from run records)
| objective | runs | usd | output tokens | thinking | denials | limit hits |
|---|---|---|---|---|---|---|
| O002 | 6 | $11.44 | 293351 | 180601 | 28 | 0 |
| O003 | 4 | $5.89 | 136620 | 96498 | 8 | 0 |
| O004 | 6 | $9.51 | 225161 | 160260 | 17 | 0 |
| O005 | 4 | $7.65 | 185443 | 108670 | 29 | 0 |
| O006 | 66 | $131.12 | 2501448 | 1365604 | 124 | 0 |
| O901 | 3 | $5.05 | 101607 | 52842 | 14 | 0 |

## Tasks
cancelled: 30, done: 163, failed: 3, needs_founder: 1

- T0166 `needs_founder` none/experiment: Run E006: thermal L2 against frozen references, scikit-fem cross-check and GCI (attempt 0)

## Recent events
- 2026-11-02T18:40:39+00:00 run_started {"run": "T0196-scientist-20261102T104039-19d7", "task": "T0196", "role": "scientist", "session": "46daa03b-08ae-48aa-b8e5-71eebf2a9c4f"}
- 2026-11-02T18:42:54+00:00 inbox_resolved {"id": "I0092", "status": "approved", "note": "Stale: cap already 120 (b1233a2); raised by the pre-restart loop", "by": "human"}
- 2026-11-02T19:01:47+00:00 run_finished {"run": "T0196-scientist-20261102T104039-19d7", "status": "completed", "cost": 3.36292, "subtype": "success", "report": "structured_output"}
- 2026-11-02T19:03:55+00:00 verified {"task": "T0196"}
- 2026-11-02T19:03:58+00:00 run_started {"run": "T0197-critic-20261102T110358-0958", "task": "T0197", "role": "critic", "session": "3e74a854-2db3-4e8a-b75c-34fdbd8b62ca"}
- 2026-11-02T19:11:34+00:00 run_finished {"run": "T0197-critic-20261102T110358-0958", "status": "completed", "cost": 2.534383, "subtype": "success", "report": "structured_output"}
- 2026-11-02T19:11:37+00:00 inbox_opened {"id": "I0093", "kind": "protected_change", "subject": "T0196: merge needs founder approval"}
- 2026-11-02T19:28:09+00:00 inbox_resolved {"id": "I0093", "status": "approved", "note": "T0196: E006 pre-registration fixes (review T0197 accept with caveats); NaN-safe gate patch follows before registr
- 2026-11-02T19:28:43+00:00 merged {"task": "T0196"}
- 2026-11-02T19:28:43+00:00 inbox_opened {"id": "I0094", "kind": "experiment_registration", "subject": "register E006 (pre-registration)"}
- 2026-11-02T19:30:43+00:00 inbox_resolved {"id": "I0090", "status": "rejected", "note": "Superseded by I0094: register after T0196 and the NaN-gate fix", "by": "human"}
- 2026-11-02T19:31:17+00:00 experiment_registered {"id": "E006", "hash": "sha256:6ea7ce80d70572248e8704bbc71743459c4fa44cec07ff2a1cdeb59547b08fcf", "by": "founder"}
- 2026-11-02T19:31:17+00:00 inbox_resolved {"id": "I0094", "status": "approved", "note": "Register E006: design T0165 + fixes T0196 (reviews T0194, T0195, T0197) + NaN-safe gates", "by": "human"}
- 2026-11-02T19:31:43+00:00 inbox_opened {"id": "I0095", "kind": "decision", "subject": "E006 needs burst compute (~3 CPU-h)"}
- 2026-11-02T19:31:43+00:00 burst_requested {"task": "T0166", "experiment": "E006", "cpu_hours": 3.0}
