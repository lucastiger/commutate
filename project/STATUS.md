# ModuleForge status
_generated 2026-11-18T00:08:12+00:00 from repository state — do not edit_

## Founder inbox (3 open)
- **I0205** [external_action] [O008] Burst VM for E011's development L2 draws (band bound, joint operating characteristic, dev rows)
- **I0209** [external_action] [O004] O004: two F7 burst-VM runs before E004 registration, and a budget warning
- **I0248** [budget_increase] daily LLM budget reached

## Objectives
| id | status | verdict | evals | spent | title |
|---|---|---|---|---|---|
| O000 | passed | PASS | 1/2 | $0.50/$20 | Framework canary — the loop carries a known-answer hypothesis from plan to verdict |
| O001 | passed | PASS | 1/3 | $287.86/$315 | L1 PEEC ranks half-bridge layouts faithfully enough to drive layout search |
| O002 | active | - | 0/1 | $85.67/$120 | A fast L1 thermal model predicts each die's average junction temperature, the spread across paralleled dies and layout-to-layout differences well enough to drive search |
| O003 | needs_founder | - | 0/1 | $258.22/$265 | Reference wire-bonded half-bridge layouts leave >= 20 % loop-inductance headroom inside their own housing at <= +2 K Tj |
| O004 | active | - | 0/1 | $111.36/$148 | The L2 inductance reference agrees with an independent field solver on the inductance ratios of re-layouts of PowerSynth public sample designs |
| O005 | draft | - | 0/2 | $7.65/$60 | L1 picks near-best layouts within a fixed family and die count, the regime derivative re-layout searches |
| O006 | active | INCONCLUSIVE | 1/1 | $137.91/$140 | The thermal L2 reference matches converged analytic solutions and an independent FEM, and design pilots measure what O002-O004 must fix |
| O007 | passed | PASS | 1/1 | $92.55/$110 | The scikit-fem thermal reference matches converged analytic solutions and the in-house finite-volume L2 on generator layouts |
| O008 | active | - | 0/2 | $82.80/$140 | A search seeded at a degraded copy of a near-optimal layout recovers it, where inductance-blind heuristics do not, on every designer-derived development layout |
| O901 | passed | PASS | 1/2 | $9.19/$30 | Infrastructure canary v2 - a known answer through registered, sealed, recomputed and null-checked evidence |

## Usage (from run records)
| objective | runs | usd | output tokens | thinking | denials | limit hits |
|---|---|---|---|---|---|---|
| O002 | 37 | $85.67 | 1602356 | 817890 | 110 | 0 |
| O003 | 135 | $258.22 | 4105839 | 2002393 | 280 | 0 |
| O004 | 54 | $111.36 | 1760637 | 987261 | 142 | 0 |
| O005 | 4 | $7.65 | 185443 | 108670 | 29 | 0 |
| O006 | 69 | $137.91 | 2633380 | 1435121 | 137 | 0 |
| O007 | 50 | $92.55 | 1684141 | 838123 | 79 | 1 |
| O008 | 40 | $82.80 | 1452687 | 796803 | 108 | 0 |
| O901 | 3 | $5.05 | 101607 | 52842 | 14 | 0 |

## Tasks
cancelled: 47, done: 399, failed: 4, review: 1, running: 3, todo: 5

- T0382 `running` scientist/design_experiment: Design E011: draft spec and runner (selftest, smoke, development mode with the burst job manifest) (attempt 5)
- T0398 `review` scientist/design_experiment: E007 development rows: local dev run, F2 null check via mfos exp check, F3 coverage re-run on the dev structure (attempt 2)
- T0457 `running` scientist/design_experiment: E004 design part 2b: banded acceptance and its simulation, redraw record, 2R proxy pair, provenance, solve-stage review fixes, local FastHenry probe (attempt 1)
- T0459 `running` critic/review: Review T0398 (general) (attempt 1)

## Recent events
- 2026-11-17T21:32:17+00:00 run_finished {"run": "T0382-scientist-20261117T085511-4122", "status": "completed", "cost": 6.065576, "subtype": "success", "report": "structured_output"}
- 2026-11-17T21:42:56+00:00 inbox_resolved {"id": "I0247", "status": "approved", "note": "T0389 merge approved, reviews T0453, T0454, T0455 accept with caveats. E004 part 2, partial: solve stage, estimat
- 2026-11-17T21:46:00+00:00 task_failed_attempt {"task": "T0382", "signal": "dod_failed", "action": "diagnose"}
- 2026-11-17T21:46:00+00:00 investigation_spawned {"task": "T0458", "about": "T0382", "cls": "implementation"}
- 2026-11-17T21:46:05+00:00 merged {"task": "T0389"}
- 2026-11-17T21:46:06+00:00 registration_deferred {"task": "T0389", "experiment": "E004", "reason": "design task T0390 of E004 is still todo"}
- 2026-11-17T21:46:13+00:00 inbox_opened {"id": "I0248", "kind": "budget_increase", "subject": "daily LLM budget reached"}
- 2026-11-17T21:46:26+00:00 task_rebriefed {"task": "T0382", "note": "T0458 cancelled; experiment_drafts quirk; retry"}
- 2026-11-17T21:47:34+00:00 run_finished {"run": "T0398-scientist-20261117T133141-2750", "status": "completed", "cost": 0.395608, "subtype": "success", "report": "structured_output"}
- 2026-11-17T21:54:01+00:00 verified {"task": "T0398"}
- 2026-11-17T23:21:29+00:00 loop_stopped {"reason": "STOP file"}
- 2026-11-17T23:24:57+00:00 loop_started {"pid": 41772}
- 2026-11-18T00:00:31+00:00 run_started {"run": "T0382-scientist-20261117T160031-53cd", "task": "T0382", "role": "scientist", "session": "6e56b935-e89a-4c22-b7b3-b1bfdc12e6d7"}
- 2026-11-18T00:00:32+00:00 run_started {"run": "T0457-scientist-20261117T160032-2c24", "task": "T0457", "role": "scientist", "session": "13f462d5-81d1-4bd8-8cad-7beaa37ee672"}
- 2026-11-18T00:00:34+00:00 run_started {"run": "T0459-critic-20261117T160034-f27d", "task": "T0459", "role": "critic", "session": "d6c2249f-27d0-4bc2-aec1-0610a0fb46d5"}
