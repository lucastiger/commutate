# ModuleForge status
_generated 2026-11-17T00:06:20+00:00 from repository state — do not edit_

## Founder inbox (2 open)
- **I0205** [external_action] [O008] Burst VM for E011's development L2 draws (band bound, joint operating characteristic, dev rows)
- **I0209** [external_action] [O004] O004: two F7 burst-VM runs before E004 registration, and a budget warning

## Objectives
| id | status | verdict | evals | spent | title |
|---|---|---|---|---|---|
| O000 | passed | PASS | 1/2 | $0.50/$20 | Framework canary — the loop carries a known-answer hypothesis from plan to verdict |
| O001 | passed | PASS | 1/3 | $287.86/$315 | L1 PEEC ranks half-bridge layouts faithfully enough to drive layout search |
| O002 | active | - | 0/1 | $46.34/$120 | A fast L1 thermal model predicts each die's average junction temperature, the spread across paralleled dies and layout-to-layout differences well enough to drive search |
| O003 | needs_founder | - | 0/1 | $258.22/$265 | Reference wire-bonded half-bridge layouts leave >= 20 % loop-inductance headroom inside their own housing at <= +2 K Tj |
| O004 | active | - | 0/1 | $62.69/$100 | The L2 inductance reference agrees with an independent field solver on the inductance ratios of re-layouts of PowerSynth public sample designs |
| O005 | draft | - | 0/2 | $7.65/$60 | L1 picks near-best layouts within a fixed family and die count, the regime derivative re-layout searches |
| O006 | active | INCONCLUSIVE | 1/1 | $137.91/$140 | The thermal L2 reference matches converged analytic solutions and an independent FEM, and design pilots measure what O002-O004 must fix |
| O007 | passed | PASS | 1/1 | $92.55/$110 | The scikit-fem thermal reference matches converged analytic solutions and the in-house finite-volume L2 on generator layouts |
| O008 | active | - | 0/2 | $52.43/$140 | A search seeded at a degraded copy of a near-optimal layout recovers it, where inductance-blind heuristics do not, on every designer-derived development layout |
| O901 | passed | PASS | 1/2 | $9.19/$30 | Infrastructure canary v2 - a known answer through registered, sealed, recomputed and null-checked evidence |

## Usage (from run records)
| objective | runs | usd | output tokens | thinking | denials | limit hits |
|---|---|---|---|---|---|---|
| O002 | 20 | $46.34 | 1006543 | 563185 | 58 | 0 |
| O003 | 135 | $258.22 | 4105839 | 2002393 | 280 | 0 |
| O004 | 34 | $62.69 | 1127180 | 706310 | 82 | 0 |
| O005 | 4 | $7.65 | 185443 | 108670 | 29 | 0 |
| O006 | 69 | $137.91 | 2633380 | 1435121 | 137 | 0 |
| O007 | 50 | $92.55 | 1684141 | 838123 | 79 | 1 |
| O008 | 31 | $52.43 | 1139532 | 668051 | 96 | 0 |
| O901 | 3 | $5.05 | 101607 | 52842 | 14 | 0 |

## Tasks
cancelled: 45, done: 361, failed: 4, review: 3, running: 3, todo: 12

- T0382 `running` scientist/design_experiment: Design E011: draft spec and runner (selftest, smoke, development mode with the burst job manifest) (attempt 1)
- T0385 `review` builder/implement: FastHenry run adapter: pinned binary and self-test, multipole with up to 10 retries, Zc.mat parse, closed-form validation (attempt 1)
- T0387 `running` scientist/investigate: F7(b)-(d) l2_layout check on Case 4 development pairs: ladder, ratio estimates, F1 exclusion rate, VM job list (attempt 1)
- T0395 `review` builder/implement: L1 thermal model in src/moduleforge/thermal/ (n1's chosen design), tested against analytic limits, symmetry and power scaling, with a speed benchmark (attempt 2)
- T0396 `review` scientist/design_experiment: E007 statistics: F3 coverage and power simulation, bound selection and fixed allocation; protected mfos.metrics additions drafted as a patch (attempt 1)
- T0428 `running` critic/review: Review T0385 (numerics) (attempt 1)

## Recent events
- 2026-11-16T23:12:24+00:00 run_finished {"run": "T0387-scientist-20261116T123702-806f", "status": "error", "cost": 3.090616, "subtype": "success", "report": "missing"}
- 2026-11-16T23:12:24+00:00 capacity_backoff {"task": "T0387", "minutes": 5, "parsed_reset": false}
- 2026-11-16T23:12:24+00:00 run_finished {"run": "T0426-critic-20261116T123615-a06e", "status": "completed", "cost": 1.979046, "subtype": "success", "report": "structured_output"}
- 2026-11-16T23:45:50+00:00 inbox_opened {"id": "I0227", "kind": "protected_change", "subject": "T0380: merge needs founder approval"}
- 2026-11-16T23:45:58+00:00 inbox_opened {"id": "I0228", "kind": "budget_increase", "subject": "daily LLM budget reached"}
- 2026-11-16T23:49:31+00:00 inbox_resolved {"id": "I0227", "status": "approved", "note": "T0380 merge approved (reviews T0425, T0426 accept with caveats). Caveats routed to T0382: out-of-domain seed repo
- 2026-11-16T23:49:37+00:00 inbox_resolved {"id": "I0228", "status": "approved", "note": "Acknowledged; cap not raised. The day resets at 00:00 UTC.", "by": "human"}
- 2026-11-16T23:50:14+00:00 merged {"task": "T0380"}
- 2026-11-16T23:50:21+00:00 inbox_opened {"id": "I0229", "kind": "budget_increase", "subject": "daily LLM budget reached"}
- 2026-11-17T00:00:28+00:00 run_started {"run": "T0427-critic-20261116T160028-9dd1", "task": "T0427", "role": "critic", "session": "c4c88cda-f19d-4353-9be8-b18e76bd8e79"}
- 2026-11-17T00:00:30+00:00 run_started {"run": "T0428-critic-20261116T160030-ca1a", "task": "T0428", "role": "critic", "session": "f574f800-7638-4347-a287-660d27b3593f"}
- 2026-11-17T00:00:30+00:00 run_started {"run": "T0382-scientist-20261116T160030-8287", "task": "T0382", "role": "scientist", "session": "0980b0a0-f516-4599-b117-dccd2695249b"}
- 2026-11-17T00:02:19+00:00 inbox_resolved {"id": "I0229", "status": "approved", "note": "Acknowledged after the 00:00 UTC reset; cap not raised.", "by": "human"}
- 2026-11-17T00:06:09+00:00 run_finished {"run": "T0427-critic-20261116T160028-9dd1", "status": "completed", "cost": 1.414486, "subtype": "success", "report": "structured_output"}
- 2026-11-17T00:06:20+00:00 run_started {"run": "T0387-scientist-20261116T160620-eb98", "task": "T0387", "role": "scientist", "session": "39796813-99fd-481c-969b-b4bd94d5344e"}
