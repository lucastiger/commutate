# ModuleForge status
_generated 2026-11-14T17:56:16+00:00 from repository state — do not edit_

## Founder inbox (1 open)
- **I0185** [plan_approval] [O003] approve initial plan (1 tasks)

## Objectives
| id | status | verdict | evals | spent | title |
|---|---|---|---|---|---|
| O000 | passed | PASS | 1/2 | $0.50/$20 | Framework canary — the loop carries a known-answer hypothesis from plan to verdict |
| O001 | passed | PASS | 1/3 | $287.86/$315 | L1 PEEC ranks half-bridge layouts faithfully enough to drive layout search |
| O002 | draft | - | 0/1 | $11.44/$120 | A fast L1 thermal model predicts per-die Tj max, spread and layout-to-layout differences well enough to drive search |
| O003 | active | - | 0/1 | $233.49/$250 | Reference wire-bonded half-bridge layouts leave >= 20 % loop-inductance headroom inside their own housing at <= +2 K Tj |
| O004 | draft | - | 0/1 | $9.51/$100 | The L2 inductance reference is accurate on reconstructed public modules, so it can judge O003's headroom |
| O005 | draft | - | 0/2 | $7.65/$60 | L1 picks near-best layouts within a fixed family and die count, the regime derivative re-layout searches |
| O006 | active | INCONCLUSIVE | 1/1 | $137.91/$140 | The thermal L2 reference matches converged analytic solutions and an independent FEM, and design pilots measure what O002-O004 must fix |
| O007 | passed | PASS | 1/1 | $92.55/$110 | The scikit-fem thermal reference matches converged analytic solutions and the in-house finite-volume L2 on generator layouts |
| O901 | passed | PASS | 1/2 | $9.19/$30 | Infrastructure canary v2 - a known answer through registered, sealed, recomputed and null-checked evidence |

## Usage (from run records)
| objective | runs | usd | output tokens | thinking | denials | limit hits |
|---|---|---|---|---|---|---|
| O002 | 6 | $11.44 | 293351 | 180601 | 28 | 0 |
| O003 | 118 | $233.49 | 3728844 | 1837230 | 243 | 0 |
| O004 | 6 | $9.51 | 225161 | 160260 | 17 | 0 |
| O005 | 4 | $7.65 | 185443 | 108670 | 29 | 0 |
| O006 | 69 | $137.91 | 2633380 | 1435121 | 137 | 0 |
| O007 | 50 | $92.55 | 1684141 | 838123 | 79 | 1 |
| O901 | 3 | $5.05 | 101607 | 52842 | 14 | 0 |

## Tasks
cancelled: 39, done: 294, failed: 3, todo: 1


## Recent events
- 2026-11-14T17:55:12+00:00 experiment_registered {"id": "E008", "hash": "sha256:206af2d225679693ac78e904a898f0a9107db03912e431cdefb525a0268e3f6b", "by": "founder"}
- 2026-11-14T17:55:12+00:00 inbox_resolved {"id": "I0195", "status": "approved", "note": "Register E008 per D0020 (spec after T0332/T0334/T0336; local smoke on merged main: die-average columns and h_lo_v
- 2026-11-14T17:55:27+00:00 inbox_resolved {"id": "I0167", "status": "rejected", "note": "superseded by I0195 (D0020 item 5)", "by": "human"}
- 2026-11-14T17:55:30+00:00 inbox_resolved {"id": "I0169", "status": "rejected", "note": "superseded by I0195 (D0020 item 5)", "by": "human"}
- 2026-11-14T17:55:32+00:00 inbox_resolved {"id": "I0171", "status": "rejected", "note": "superseded by I0195 (D0020 item 5)", "by": "human"}
- 2026-11-14T17:55:35+00:00 inbox_resolved {"id": "I0175", "status": "rejected", "note": "superseded by I0195 (D0020 item 5)", "by": "human"}
- 2026-11-14T17:55:36+00:00 inbox_resolved {"id": "I0177", "status": "rejected", "note": "superseded by I0195 (D0020 item 5)", "by": "human"}
- 2026-11-14T17:55:38+00:00 inbox_resolved {"id": "I0179", "status": "rejected", "note": "superseded by I0195 (D0020 item 5)", "by": "human"}
- 2026-11-14T17:55:40+00:00 inbox_resolved {"id": "I0181", "status": "rejected", "note": "superseded by I0195 (D0020 item 5)", "by": "human"}
- 2026-11-14T17:55:42+00:00 inbox_resolved {"id": "I0187", "status": "rejected", "note": "superseded by I0195 (D0020 item 5)", "by": "human"}
- 2026-11-14T17:55:44+00:00 inbox_resolved {"id": "I0189", "status": "rejected", "note": "superseded by I0195 (D0020 item 5)", "by": "human"}
- 2026-11-14T17:55:46+00:00 inbox_resolved {"id": "I0191", "status": "rejected", "note": "superseded by I0195 (D0020 item 5)", "by": "human"}
- 2026-11-14T17:55:49+00:00 inbox_resolved {"id": "I0193", "status": "rejected", "note": "superseded by I0195 (D0020 item 5)", "by": "human"}
- 2026-11-14T17:55:53+00:00 inbox_resolved {"id": "I0165", "status": "rejected", "note": "superseded by I0195 (D0020 item 5)", "by": "human"}
- 2026-11-14T17:56:17+00:00 inbox_resolved {"id": "I0185", "status": "approved", "note": "Approve T0329 (run E008); founder runs it on the VM with research/o003/e008_dev/burst_full.sh", "by": "human"}
