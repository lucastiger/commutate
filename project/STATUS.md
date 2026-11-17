# ModuleForge status
_generated 2026-11-17T01:28:31+00:00 from repository state — do not edit_

## Founder inbox (4 open)
- **I0205** [external_action] [O008] Burst VM for E011's development L2 draws (band bound, joint operating characteristic, dev rows)
- **I0209** [external_action] [O004] O004: two F7 burst-VM runs before E004 registration, and a budget warning
- **I0230** [protected_change] T0385: merge needs founder approval
- **I0231** [protected_change] T0396: merge needs founder approval

## Objectives
| id | status | verdict | evals | spent | title |
|---|---|---|---|---|---|
| O000 | passed | PASS | 1/2 | $0.50/$20 | Framework canary — the loop carries a known-answer hypothesis from plan to verdict |
| O001 | passed | PASS | 1/3 | $287.86/$315 | L1 PEEC ranks half-bridge layouts faithfully enough to drive layout search |
| O002 | active | - | 0/1 | $48.45/$120 | A fast L1 thermal model predicts each die's average junction temperature, the spread across paralleled dies and layout-to-layout differences well enough to drive search |
| O003 | needs_founder | - | 0/1 | $258.22/$265 | Reference wire-bonded half-bridge layouts leave >= 20 % loop-inductance headroom inside their own housing at <= +2 K Tj |
| O004 | active | - | 0/1 | $67.44/$100 | The L2 inductance reference agrees with an independent field solver on the inductance ratios of re-layouts of PowerSynth public sample designs |
| O005 | draft | - | 0/2 | $7.65/$60 | L1 picks near-best layouts within a fixed family and die count, the regime derivative re-layout searches |
| O006 | active | INCONCLUSIVE | 1/1 | $137.91/$140 | The thermal L2 reference matches converged analytic solutions and an independent FEM, and design pilots measure what O002-O004 must fix |
| O007 | passed | PASS | 1/1 | $92.55/$110 | The scikit-fem thermal reference matches converged analytic solutions and the in-house finite-volume L2 on generator layouts |
| O008 | active | - | 0/2 | $52.43/$140 | A search seeded at a degraded copy of a near-optimal layout recovers it, where inductance-blind heuristics do not, on every designer-derived development layout |
| O901 | passed | PASS | 1/2 | $9.19/$30 | Infrastructure canary v2 - a known answer through registered, sealed, recomputed and null-checked evidence |

## Usage (from run records)
| objective | runs | usd | output tokens | thinking | denials | limit hits |
|---|---|---|---|---|---|---|
| O002 | 22 | $48.45 | 1040553 | 580611 | 66 | 0 |
| O003 | 135 | $258.22 | 4105839 | 2002393 | 280 | 0 |
| O004 | 35 | $67.44 | 1200161 | 743817 | 85 | 0 |
| O005 | 4 | $7.65 | 185443 | 108670 | 29 | 0 |
| O006 | 69 | $137.91 | 2633380 | 1435121 | 137 | 0 |
| O007 | 50 | $92.55 | 1684141 | 838123 | 79 | 1 |
| O008 | 31 | $52.43 | 1139532 | 668051 | 96 | 0 |
| O901 | 3 | $5.05 | 101607 | 52842 | 14 | 0 |

## Tasks
cancelled: 45, done: 363, failed: 4, needs_founder: 2, review: 2, running: 3, todo: 10

- T0382 `running` scientist/design_experiment: Design E011: draft spec and runner (selftest, smoke, development mode with the burst job manifest) (attempt 1)
- T0385 `needs_founder` builder/implement: FastHenry run adapter: pinned binary and self-test, multipole with up to 10 retries, Zc.mat parse, closed-form validation (attempt 1)
- T0387 `review` scientist/investigate: F7(b)-(d) l2_layout check on Case 4 development pairs: ladder, ratio estimates, F1 exclusion rate, VM job list (attempt 1)
- T0395 `review` builder/implement: L1 thermal model in src/moduleforge/thermal/ (n1's chosen design), tested against analytic limits, symmetry and power scaling, with a speed benchmark (attempt 2)
- T0396 `needs_founder` scientist/design_experiment: E007 statistics: F3 coverage and power simulation, bound selection and fixed allocation; protected mfos.metrics additions drafted as a patch (attempt 1)
- T0423 `running` critic/review: Review T0395 (physics) (attempt 1)
- T0429 `running` critic/review: Review T0387 (general) (attempt 1)

## Recent events
- 2026-11-17T00:00:30+00:00 run_started {"run": "T0428-critic-20261116T160030-ca1a", "task": "T0428", "role": "critic", "session": "f574f800-7638-4347-a287-660d27b3593f"}
- 2026-11-17T00:00:30+00:00 run_started {"run": "T0382-scientist-20261116T160030-8287", "task": "T0382", "role": "scientist", "session": "0980b0a0-f516-4599-b117-dccd2695249b"}
- 2026-11-17T00:02:19+00:00 inbox_resolved {"id": "I0229", "status": "approved", "note": "Acknowledged after the 00:00 UTC reset; cap not raised.", "by": "human"}
- 2026-11-17T00:06:09+00:00 run_finished {"run": "T0427-critic-20261116T160028-9dd1", "status": "completed", "cost": 1.414486, "subtype": "success", "report": "structured_output"}
- 2026-11-17T00:06:20+00:00 run_started {"run": "T0387-scientist-20261116T160620-eb98", "task": "T0387", "role": "scientist", "session": "39796813-99fd-481c-969b-b4bd94d5344e"}
- 2026-11-17T00:09:55+00:00 run_finished {"run": "T0428-critic-20261116T160030-ca1a", "status": "completed", "cost": 1.977187, "subtype": "success", "report": "structured_output"}
- 2026-11-17T01:05:12+00:00 inbox_opened {"id": "I0230", "kind": "protected_change", "subject": "T0385: merge needs founder approval"}
- 2026-11-17T01:05:23+00:00 run_started {"run": "T0420-critic-20261116T170523-fb3c", "task": "T0420", "role": "critic", "session": "acf93c3c-b7de-40be-af8e-a1d554014587"}
- 2026-11-17T01:05:59+00:00 run_finished {"run": "T0387-scientist-20261116T160620-eb98", "status": "completed", "cost": 2.766734, "subtype": "success", "report": "structured_output"}
- 2026-11-17T01:17:04+00:00 verified {"task": "T0387"}
- 2026-11-17T01:17:04+00:00 run_finished {"run": "T0420-critic-20261116T170523-fb3c", "status": "completed", "cost": 2.109277, "subtype": "success", "report": "structured_output"}
- 2026-11-17T01:26:21+00:00 founder_decision_recorded {"objective": "O002", "summary": "E007: one-sided 97 % Woodruff bounds (level 0.94); 300 layouts, 20 per stratum"}
- 2026-11-17T01:28:20+00:00 inbox_opened {"id": "I0231", "kind": "protected_change", "subject": "T0396: merge needs founder approval"}
- 2026-11-17T01:28:29+00:00 run_started {"run": "T0429-critic-20261116T172829-54ef", "task": "T0429", "role": "critic", "session": "0b06a88d-e5e8-4436-adb7-ef2c4c1392bf"}
- 2026-11-17T01:28:31+00:00 run_started {"run": "T0423-critic-20261116T172831-33cc", "task": "T0423", "role": "critic", "session": "dfa3caa0-cae2-48f2-bb91-c024d5f5e08d"}
