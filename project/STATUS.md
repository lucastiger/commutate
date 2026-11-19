# ModuleForge status
_generated 2026-11-19T09:19:41+00:00 from repository state — do not edit_

## Founder inbox (3 open)
- **I0205** [external_action] [O008] Burst VM for E011's development L2 draws (band bound, joint operating characteristic, dev rows)
- **I0209** [external_action] [O004] O004: two F7 burst-VM runs before E004 registration, and a budget warning
- **I0259** [claim_approval] [O002] approve the wording of claim C005

## Objectives
| id | status | verdict | evals | spent | title |
|---|---|---|---|---|---|
| O000 | passed | PASS | 1/2 | $0.50/$20 | Framework canary — the loop carries a known-answer hypothesis from plan to verdict |
| O001 | passed | PASS | 1/3 | $287.86/$315 | L1 PEEC ranks half-bridge layouts faithfully enough to drive layout search |
| O002 | passed | PASS | 1/1 | $103.71/$120 | A fast L1 thermal model predicts each die's average junction temperature, the spread across paralleled dies and layout-to-layout differences well enough to drive search |
| O003 | needs_founder | - | 0/1 | $258.22/$265 | Reference wire-bonded half-bridge layouts leave >= 20 % loop-inductance headroom inside their own housing at <= +2 K Tj |
| O004 | active | - | 0/1 | $139.22/$148 | The L2 inductance reference agrees with an independent field solver on the inductance ratios of re-layouts of PowerSynth public sample designs |
| O005 | draft | - | 0/2 | $7.65/$60 | L1 picks near-best layouts within a fixed family and die count, the regime derivative re-layout searches |
| O006 | active | INCONCLUSIVE | 1/1 | $137.91/$140 | The thermal L2 reference matches converged analytic solutions and an independent FEM, and design pilots measure what O002-O004 must fix |
| O007 | passed | PASS | 1/1 | $92.55/$110 | The scikit-fem thermal reference matches converged analytic solutions and the in-house finite-volume L2 on generator layouts |
| O008 | active | - | 0/2 | $91.48/$140 | A search seeded at a degraded copy of a near-optimal layout recovers it, where inductance-blind heuristics do not, on every designer-derived development layout |
| O901 | passed | PASS | 1/2 | $9.19/$30 | Infrastructure canary v2 - a known answer through registered, sealed, recomputed and null-checked evidence |

## Usage (from run records)
| objective | runs | usd | output tokens | thinking | denials | limit hits |
|---|---|---|---|---|---|---|
| O002 | 43 | $103.71 | 1856867 | 911798 | 143 | 0 |
| O003 | 135 | $258.22 | 4105839 | 2002393 | 280 | 0 |
| O004 | 60 | $139.22 | 2176735 | 1194906 | 158 | 0 |
| O005 | 4 | $7.65 | 185443 | 108670 | 29 | 0 |
| O006 | 69 | $137.91 | 2633380 | 1435121 | 137 | 0 |
| O007 | 50 | $92.55 | 1684141 | 838123 | 79 | 1 |
| O008 | 43 | $91.48 | 1532378 | 830907 | 120 | 0 |
| O901 | 3 | $5.05 | 101607 | 52842 | 14 | 0 |

## Tasks
cancelled: 47, done: 417, failed: 4, todo: 2


## Recent events
- 2026-11-18T15:01:37+00:00 inbox_resolved {"id": "I0257", "status": "approved", "note": "T0390 merge approved, reviews T0467 and T0468 accept with caveats, logged in O004 state. E004 part 3: F3, F6, F8 
- 2026-11-18T15:02:22+00:00 merged {"task": "T0390"}
- 2026-11-18T15:02:23+00:00 inbox_opened {"id": "I0258", "kind": "experiment_registration", "subject": "register E004 (pre-registration)"}
- 2026-11-18T15:03:28+00:00 inbox_resolved {"id": "I0258", "status": "rejected", "note": "Premature: E004 needs the founder decisions on the FastHenry ladder, the span lower end, the CPU budget and timeo
- 2026-11-18T15:19:49+00:00 founder_decision_recorded {"objective": "O004", "summary": "measure FastHenry k0/k1 on Case 4, then decide at the thesis review; E004 agent work paused"}
- 2026-11-19T08:31:03+00:00 evaluation {"objective": "O002", "id": "EV-O002-01", "verdict": "PASS"}
- 2026-11-19T08:31:19+00:00 run_started {"run": "T0469-critic-20261119T003119-af79", "task": "T0469", "role": "critic", "session": "52cddc6d-f0fb-4245-aac7-69750409fe98"}
- 2026-11-19T08:31:23+00:00 run_started {"run": "T0470-critic-20261119T003123-e023", "task": "T0470", "role": "critic", "session": "ac00b5d3-dfb0-4c6d-9762-c5ba0e7297dc"}
- 2026-11-19T08:36:10+00:00 run_finished {"run": "T0469-critic-20261119T003119-af79", "status": "completed", "cost": 1.789299, "subtype": "success", "report": "structured_output"}
- 2026-11-19T08:37:38+00:00 run_finished {"run": "T0470-critic-20261119T003123-e023", "status": "completed", "cost": 2.541435, "subtype": "success", "report": "structured_output"}
- 2026-11-19T08:37:42+00:00 claim_recorded {"id": "C005", "status": "proposed"}
- 2026-11-19T08:37:42+00:00 inbox_opened {"id": "I0259", "kind": "claim_approval", "subject": "[O002] approve the wording of claim C005"}
- 2026-11-19T08:37:44+00:00 objective_passed {"objective": "O002", "evaluation": "EV-O002-01"}
- 2026-11-19T08:39:27+00:00 founder_decision_recorded {"objective": "O002", "summary": "C005 approval after the 11-27 thesis review; final statement drafted with the reviews' limits"}
- 2026-11-19T09:19:15+00:00 session_note_recorded {"objective": "O004", "summary": "FastHenry Linux crash root-caused (matStats overflow); D0028 proposed; E004 binary pin must be per-platform"}
