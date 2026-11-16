# ModuleForge status
_generated 2026-11-16T01:45:15+00:00 from repository state — do not edit_

## Founder inbox (7 open)
- **I0204** [decision] [O008] F7: E011's acceptance metrics in mfos.metrics (tools/ is protected)
- **I0205** [external_action] [O008] Burst VM for E011's development L2 draws (band bound, joint operating characteristic, dev rows)
- **I0206** [plan_approval] [O008] approve initial plan (8 tasks)
- **I0207** [question] [O004] O004: the 2D_Case_2R designer-proxy pair (owner, 1 mm lattice, denominator)
- **I0208** [external_action] [O004] O004: add the ratio-step rule to mfos.metrics (tools/ is protected)
- **I0209** [external_action] [O004] O004: two F7 burst-VM runs before E004 registration, and a budget warning
- **I0210** [plan_approval] [O004] approve initial plan (8 tasks)

## Objectives
| id | status | verdict | evals | spent | title |
|---|---|---|---|---|---|
| O000 | passed | PASS | 1/2 | $0.50/$20 | Framework canary — the loop carries a known-answer hypothesis from plan to verdict |
| O001 | passed | PASS | 1/3 | $287.86/$315 | L1 PEEC ranks half-bridge layouts faithfully enough to drive layout search |
| O002 | active | - | 0/1 | $19.10/$120 | A fast L1 thermal model predicts each die's average junction temperature, the spread across paralleled dies and layout-to-layout differences well enough to drive search |
| O003 | needs_founder | - | 0/1 | $258.22/$265 | Reference wire-bonded half-bridge layouts leave >= 20 % loop-inductance headroom inside their own housing at <= +2 K Tj |
| O004 | active | - | 0/1 | $25.93/$100 | The L2 inductance reference agrees with an independent field solver on the inductance ratios of re-layouts of PowerSynth public sample designs |
| O005 | draft | - | 0/2 | $7.65/$60 | L1 picks near-best layouts within a fixed family and die count, the regime derivative re-layout searches |
| O006 | active | INCONCLUSIVE | 1/1 | $137.91/$140 | The thermal L2 reference matches converged analytic solutions and an independent FEM, and design pilots measure what O002-O004 must fix |
| O007 | passed | PASS | 1/1 | $92.55/$110 | The scikit-fem thermal reference matches converged analytic solutions and the in-house finite-volume L2 on generator layouts |
| O008 | active | - | 0/2 | $19.63/$140 | A search seeded at a degraded copy of a near-optimal layout recovers it, where inductance-blind heuristics do not, on every designer-derived development layout |
| O901 | passed | PASS | 1/2 | $9.19/$30 | Infrastructure canary v2 - a known answer through registered, sealed, recomputed and null-checked evidence |

## Usage (from run records)
| objective | runs | usd | output tokens | thinking | denials | limit hits |
|---|---|---|---|---|---|---|
| O002 | 11 | $19.10 | 475972 | 309986 | 40 | 0 |
| O003 | 135 | $258.22 | 4105839 | 2002393 | 280 | 0 |
| O004 | 15 | $25.93 | 602089 | 439606 | 35 | 0 |
| O005 | 4 | $7.65 | 185443 | 108670 | 29 | 0 |
| O006 | 69 | $137.91 | 2633380 | 1435121 | 137 | 0 |
| O007 | 50 | $92.55 | 1684141 | 838123 | 79 | 1 |
| O008 | 11 | $19.63 | 457180 | 328060 | 33 | 0 |
| O901 | 3 | $5.05 | 101607 | 52842 | 14 | 0 |

## Tasks
cancelled: 44, done: 326, failed: 4, proposed: 16, running: 1

- T0373 `running` planner/plan: Plan O002 (periodic) (attempt 1)
- T0376 `proposed` scientist/investigate: Kill shot: do the probe's designer proxy and its null gap survive l2_layout? (attempt 0)
- T0377 `proposed` builder/implement: Reach: straddling slots, column outer edges to the edge margin, and the in_domain predicate (attempt 0)
- T0378 `proposed` builder/implement: Seeded local search over the derivative parameterisation (optimize/local.py) (attempt 0)
- T0379 `proposed` builder/implement: Designer proxy rule, randomised degradation family and ablation (e) (attempt 0)
- T0380 `proposed` builder/implement: Inductance-blind nulls (a), (b), (d) and the random-screen ablation (c) (attempt 0)
- T0381 `proposed` scientist/design_experiment: Draft E011's acceptance metric functions and analytic tests for the founder's mfos.metrics port (F7) (attempt 0)
- T0382 `proposed` scientist/design_experiment: Design E011: draft spec and runner (selftest, smoke, development mode with the burst job manifest) (attempt 0)
- T0383 `proposed` none/experiment: Run E011 (attempt 0)
- T0384 `proposed` builder/implement: FastHenry deck exporter in src: Layout -> SI-metre deck with refinable wire section, thickness and plane knobs, F6 model variants (attempt 0)
- T0385 `proposed` builder/implement: FastHenry run adapter: pinned binary and self-test, multipole with up to 10 retries, Zc.mat parse, closed-form validation (attempt 0)
- T0386 `proposed` builder/implement: Frozen perturbation rules on the 1 mm lattice: die-row shift, power-trace width, terminal-near copper, wire landing (generate/perturb.py) (attempt 0)
- T0387 `proposed` scientist/investigate: F7(b)-(d) l2_layout check on Case 4 development pairs: ladder, ratio estimates, F1 exclusion rate, VM job list (attempt 0)
- T0388 `proposed` scientist/design_experiment: E004 design, part 1: draft spec and registration stage (frozen references, sealed-seed pairs, F2/F4 checks on L1) (attempt 0)
- T0389 `proposed` scientist/design_experiment: E004 design, part 2: solve stage, estimators, A1/A2/K1/K2 metrics, INVALID rules, and the FastHenry F7(a) job list (attempt 0)
- T0390 `proposed` scientist/design_experiment: E004 design, part 3: reported diagnostics F3 (per conductor group, round vs square wire), F6 (die contact, terminal tabs), F8 (L1 beside l2_layout) (attempt 0)
- T0391 `proposed` none/experiment: Run E004 (registered) on the burst VM (attempt 0)

## Recent events
- 2026-11-16T01:35:45+00:00 objective_approved {"objective": "O002", "criteria_hash": "sha256:f7b92774c2cc4842f17ebdb0caa9d0fbe7d36d691df0b5320c830fc140ca332a"}
- 2026-11-16T01:35:54+00:00 run_started {"run": "T0374-planner-20261115T173554-610a", "task": "T0374", "role": "planner", "session": "cef995a5-7e7a-431a-ac20-3c0fb045bd73"}
- 2026-11-16T01:35:55+00:00 run_started {"run": "T0375-planner-20261115T173555-edb4", "task": "T0375", "role": "planner", "session": "f337f383-819a-438f-b7de-d40fe1483404"}
- 2026-11-16T01:35:56+00:00 run_started {"run": "T0373-planner-20261115T173556-8805", "task": "T0373", "role": "planner", "session": "9f84d004-acbb-453c-b014-82b3d666bb2f"}
- 2026-11-16T01:43:44+00:00 run_finished {"run": "T0375-planner-20261115T173555-edb4", "status": "completed", "cost": 2.023436, "subtype": "success", "report": "structured_output"}
- 2026-11-16T01:43:45+00:00 inbox_opened {"id": "I0204", "kind": "decision", "subject": "[O008] F7: E011's acceptance metrics in mfos.metrics (tools/ is protected)"}
- 2026-11-16T01:43:45+00:00 inbox_opened {"id": "I0205", "kind": "external_action", "subject": "[O008] Burst VM for E011's development L2 draws (band bound, joint operating characteristic, dev rows)"}
- 2026-11-16T01:43:45+00:00 inbox_opened {"id": "I0206", "kind": "plan_approval", "subject": "[O008] approve initial plan (8 tasks)"}
- 2026-11-16T01:43:45+00:00 plan_applied {"objective": "O008", "created": ["T0376", "T0377", "T0378", "T0379", "T0380", "T0381", "T0382", "T0383"], "dropped": 0}
- 2026-11-16T01:45:08+00:00 run_finished {"run": "T0374-planner-20261115T173554-610a", "status": "completed", "cost": 2.226232, "subtype": "success", "report": "structured_output"}
- 2026-11-16T01:45:09+00:00 inbox_opened {"id": "I0207", "kind": "question", "subject": "[O004] O004: the 2D_Case_2R designer-proxy pair (owner, 1 mm lattice, denominator)"}
- 2026-11-16T01:45:09+00:00 inbox_opened {"id": "I0208", "kind": "external_action", "subject": "[O004] O004: add the ratio-step rule to mfos.metrics (tools/ is protected)"}
- 2026-11-16T01:45:09+00:00 inbox_opened {"id": "I0209", "kind": "external_action", "subject": "[O004] O004: two F7 burst-VM runs before E004 registration, and a budget warning"}
- 2026-11-16T01:45:09+00:00 inbox_opened {"id": "I0210", "kind": "plan_approval", "subject": "[O004] approve initial plan (8 tasks)"}
- 2026-11-16T01:45:09+00:00 plan_applied {"objective": "O004", "created": ["T0384", "T0385", "T0386", "T0387", "T0388", "T0389", "T0390", "T0391"], "dropped": 0}
