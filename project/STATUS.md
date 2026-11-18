# ModuleForge status
_generated 2026-11-18T06:28:35+00:00 from repository state — do not edit_

## Founder inbox (3 open)
- **I0205** [external_action] [O008] Burst VM for E011's development L2 draws (band bound, joint operating characteristic, dev rows)
- **I0209** [external_action] [O004] O004: two F7 burst-VM runs before E004 registration, and a budget warning
- **I0255** [decision] E007 needs burst compute (~84.5 CPU-h)

## Objectives
| id | status | verdict | evals | spent | title |
|---|---|---|---|---|---|
| O000 | passed | PASS | 1/2 | $0.50/$20 | Framework canary — the loop carries a known-answer hypothesis from plan to verdict |
| O001 | passed | PASS | 1/3 | $287.86/$315 | L1 PEEC ranks half-bridge layouts faithfully enough to drive layout search |
| O002 | active | - | 0/1 | $99.38/$120 | A fast L1 thermal model predicts each die's average junction temperature, the spread across paralleled dies and layout-to-layout differences well enough to drive search |
| O003 | needs_founder | - | 0/1 | $258.22/$265 | Reference wire-bonded half-bridge layouts leave >= 20 % loop-inductance headroom inside their own housing at <= +2 K Tj |
| O004 | active | - | 0/1 | $126.95/$148 | The L2 inductance reference agrees with an independent field solver on the inductance ratios of re-layouts of PowerSynth public sample designs |
| O005 | draft | - | 0/2 | $7.65/$60 | L1 picks near-best layouts within a fixed family and die count, the regime derivative re-layout searches |
| O006 | active | INCONCLUSIVE | 1/1 | $137.91/$140 | The thermal L2 reference matches converged analytic solutions and an independent FEM, and design pilots measure what O002-O004 must fix |
| O007 | passed | PASS | 1/1 | $92.55/$110 | The scikit-fem thermal reference matches converged analytic solutions and the in-house finite-volume L2 on generator layouts |
| O008 | active | - | 0/2 | $91.48/$140 | A search seeded at a degraded copy of a near-optimal layout recovers it, where inductance-blind heuristics do not, on every designer-derived development layout |
| O901 | passed | PASS | 1/2 | $9.19/$30 | Infrastructure canary v2 - a known answer through registered, sealed, recomputed and null-checked evidence |

## Usage (from run records)
| objective | runs | usd | output tokens | thinking | denials | limit hits |
|---|---|---|---|---|---|---|
| O002 | 41 | $99.38 | 1794921 | 884897 | 131 | 0 |
| O003 | 135 | $258.22 | 4105839 | 2002393 | 280 | 0 |
| O004 | 57 | $126.95 | 2035204 | 1110965 | 147 | 0 |
| O005 | 4 | $7.65 | 185443 | 108670 | 29 | 0 |
| O006 | 69 | $137.91 | 2633380 | 1435121 | 137 | 0 |
| O007 | 50 | $92.55 | 1684141 | 838123 | 79 | 1 |
| O008 | 43 | $91.48 | 1532378 | 830907 | 120 | 0 |
| O901 | 3 | $5.05 | 101607 | 52842 | 14 | 0 |

## Tasks
cancelled: 47, done: 411, failed: 4, needs_founder: 1, running: 1, todo: 2

- T0390 `running` scientist/design_experiment: E004 design, part 3: reported diagnostics F3 (per conductor group, round vs square wire), F6 (die contact, terminal tabs), F8 (L1 beside l2_layout) (attempt 1)
- T0399 `needs_founder` none/experiment: Run E007: frozen L1 thermal model against the verified scikit-fem reference on fresh sealed layouts at P_ref and 0.5 P_ref (attempt 0)

## Recent events
- 2026-11-18T03:45:14+00:00 inbox_opened {"id": "I0254", "kind": "experiment_registration", "subject": "register E007 (pre-registration)"}
- 2026-11-18T04:44:19+00:00 experiment_registered {"id": "E007", "hash": "sha256:3b6d1b778d668cf5502c565592a478077a277c5b5b5dc06960d4a52a97087680", "by": "founder"}
- 2026-11-18T04:44:19+00:00 inbox_resolved {"id": "I0254", "status": "approved", "note": "Register E007: design complete (T0397, T0398, T0456, T0464), m = 32 per D0027, Woodruff 97 % bounds per D0025, le
- 2026-11-18T04:44:51+00:00 inbox_opened {"id": "I0255", "kind": "decision", "subject": "E007 needs burst compute (~84.5 CPU-h)"}
- 2026-11-18T04:44:51+00:00 burst_requested {"task": "T0399", "experiment": "E007", "cpu_hours": 84.5}
- 2026-11-18T04:52:35+00:00 experiment_minted {"id": "E007", "run": "E007-20261117T205235-8a84"}
- 2026-11-18T05:08:14+00:00 run_finished {"run": "T0457-scientist-20261117T171959-9768", "status": "completed", "cost": 6.061705, "subtype": "success", "report": "structured_output"}
- 2026-11-18T05:16:01+00:00 verified {"task": "T0457"}
- 2026-11-18T05:16:13+00:00 run_started {"run": "T0466-critic-20261117T211613-8302", "task": "T0466", "role": "critic", "session": "4777f8db-4dff-47c0-b9c8-1b3ee7c3af2d"}
- 2026-11-18T05:23:24+00:00 run_finished {"run": "T0466-critic-20261117T211613-8302", "status": "completed", "cost": 2.158309, "subtype": "success", "report": "structured_output"}
- 2026-11-18T05:29:02+00:00 inbox_opened {"id": "I0256", "kind": "protected_change", "subject": "T0457: merge needs founder approval"}
- 2026-11-18T06:28:09+00:00 inbox_resolved {"id": "I0256", "status": "approved", "note": "T0457 merge approved, review T0466 accepts with caveats, logged in O004 state. E004 part 2b: banded acceptance an
- 2026-11-18T06:28:26+00:00 merged {"task": "T0457"}
- 2026-11-18T06:28:27+00:00 registration_deferred {"task": "T0457", "experiment": "E004", "reason": "design task T0390 of E004 is still todo"}
- 2026-11-18T06:28:35+00:00 run_started {"run": "T0390-scientist-20261117T222835-1c59", "task": "T0390", "role": "scientist", "session": "2771237f-fdfa-4bc6-9f07-b025fc20d8f6"}
