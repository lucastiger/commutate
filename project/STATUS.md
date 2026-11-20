# ModuleForge status
_generated 2026-11-20T23:23:19+00:00 from repository state — do not edit_

## Founder inbox (2 open)
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
| O008 | active | - | 0/2 | $102.61/$140 | A search seeded at a degraded copy of a near-optimal layout recovers it, where inductance-blind heuristics do not, on every designer-derived development layout |
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
| O008 | 47 | $102.61 | 1731186 | 929899 | 136 | 0 |
| O901 | 3 | $5.05 | 101607 | 52842 | 14 | 0 |

## Tasks
cancelled: 47, done: 421, failed: 4, todo: 2


## Recent events
- 2026-11-19T16:23:40+00:00 inbox_opened {"id": "I0260", "kind": "protected_change", "subject": "T0471: merge needs founder approval"}
- 2026-11-19T16:29:23+00:00 session_note_recorded {"objective": "O008", "about": "T0471 review items"}
- 2026-11-19T16:35:39+00:00 inbox_resolved {"id": "I0260", "status": "approved", "note": "Merge T0471 (E011 development L2 analysis). Reviews T0472-T0474 accept with caveats, logged in O008 state. This i
- 2026-11-19T16:57:30+00:00 session_note_recorded {"objective": "O004", "about": "FastHenry burst limit 60 h"}
- 2026-11-19T17:12:01+00:00 merged {"task": "T0471"}
- 2026-11-19T17:12:02+00:00 inbox_opened {"id": "I0261", "kind": "experiment_registration", "subject": "register E011 (pre-registration)"}
- 2026-11-19T17:26:00+00:00 inbox_resolved {"id": "I0261", "status": "rejected", "note": "Not registering now. T0471 finds E011 as designed expected INCONCLUSIVE (dev rows A1 0.25, A3 0, P(PASS) about 0)
- 2026-11-19T18:06:54+00:00 session_note_recorded {"objective": "O004", "about": "FastHenry k0 Linux equals Mac"}
- 2026-11-20T00:25:35+00:00 session_note_recorded {"objective": "O004", "about": "FastHenry case4 k1 result"}
- 2026-11-20T03:40:19+00:00 note {"objective": "O004", "about": "fh_measurement_burst"}
- 2026-11-20T05:13:01+00:00 note {"objective": "O004", "about": "fh_measurement_burst"}
- 2026-11-20T06:44:54+00:00 note {"objective": "O004", "about": "fh_measurement_burst_done"}
- 2026-11-20T19:55:41+00:00 loop_started {"pid": 47147}
- 2026-11-20T20:44:12+00:00 loop_started {"pid": 56711}
- 2026-11-20T23:22:58+00:00 sleep_detected {"gap_s": 941, "slept_s": 897, "runs_extended": 0}
