# O007 development study 3 (T0243): pre-registered re-freeze of candidate 1 with two AMG smoothing sweeps

Author: scientist, T0243 attempt 1, 2026-11-05. Founder path (A), I0128, step 2; replaces T0237 (cancelled).
Script: `research/scripts/o007_dev_study3.py`. It reuses `o007_dev_study2.py` (T0228) by import, and through it
`o007_dev_study.py` (T0207) and `o007_probe.py` (T0225). Outputs: `research/o007_dev3/{dev_study.json,
frozen_config.json, plan.json, preregistration.json, cache/}`. No production code is changed.
Labels: **[F]** fact (file or listed command), **[I]** inference, **[S]** speculation or extrapolation.

## 0. Pre-registration (written and committed before any solve of this study)

**What was run before this section (grid construction only).** I wrote the script and ran
`uv run python research/scripts/o007_dev_study3.py --plan`, which exited 0 and wrote `plan.json`. That run produced
DOF counts and cell ratios, and compared every grid with T0228's grid. No temperature has been computed in this task.

[F] `plan.json`: at every level 0-2 of all eight problems, the grid under this study's rule equals T0228's grid line for
line (`np.array_equal` on the x, y, z lines and the material map; 24 of 24). `amg_gs_sweeps` reaches the grid object
only as the solver option. The DOF counts are therefore T0228's: Case 1a 135,531 / 1,025,661 / 7,973,721; Case 1b
160,173 / 1,221,025 / 9,529,569; Cases 2 and 3 99,275 / 750,141 / 5,827,289; N-layer 232,130 / 1,752,579 / 13,606,565;
manufactured 28,683 / 207,837 / 1,577,913; side_by_side_6 167,682 / 1,237,087 / 9,483,501; u_shaped_2 70,604 / 517,263 /
3,950,429.

### 0.0 Prior data, disclosed (all of it is known to me before any solve)

**T0228, candidate 1 with pyamg's default smoother** (`research/o007_dev2/dev_study.json`; L2 from the founder burst):

| problem | CG max L0 / L1 / L2 | max abs err L0 / L1 / L2, K | A1 at L2 | A4 at L2, K | Picard |
|---|---|---|---|---|---|
| case1a | 204 / 252 / **316** | 0.442 / 0.116 / 0.0296 | 5.3e-4 | 0.108 | 2 |
| case1b | 198 / 247 / **318** | 0.052 / 0.013 / 0.0034 | 4.9e-4 | 0.012 | 2 |
| case2 | 81 / 116 / 162 | 0.063 / 0.017 / 0.0047 | 6.8e-4 | 0.016 | 2 |
| case3 | 119 / 189 / 249 | 0.030 / 0.0075 / 0.0019 | 3.7e-4 | 0.0070 | 2 |
| nlayer_dbc | 132 / 191 / 259 (T0225 solves, reused in T0228) | 0.591 / 0.152 / 0.0386 | 4.8e-4 | 0.142 | 2 |
| mms | 53 / 75 / 93 | 0.079 / 0.020 / 0.0050 | 5e-5 | 0.019 | 6 / 5 / 5 |
| side_by_side_6 | 122 / 185 / 253 (calibration 122) | n/a | n/a | 0.095 (centroid node 0.079) | 5 |
| u_shaped_2 | 128 / 179 / 250 (calibration 128) | n/a | n/a | 0.124 (centroid node 0.092) | 5 |

T0228 summary: A1 6.8e-4, A2 0.0386 K, A4 0.142 K on the cases and 0.124 K on the layouts. Constant-k nulls had CG max
253. Verdict: ruled out by CG > 300 on Cases 1a and 1b only. Calibrated powers were 32.232 W (side_by_side_6) and
47.142 W (u_shaped_2) per die.

**T0235 (sliver discriminator, founder burst).** With the maximum lines removed (centroid_only), CG max at L0 / L1 / L2
was 177 / 235 / **305** on Case 1a and 188 / 240 / **314** on Case 1b. Case 1b's L2 missed that study's 10 x rtol
residual gate. The verdict was `conditioning`.

**Founder diagnostic** (`research/o007_sliver/founder_amg_diagnostic.json`; not pre-registered). It ran candidate 1
with 2 symmetric Gauss-Seidel sweeps per AMG level at L0 / L1. CG max was **145 / 180** (Case 1a) and **141 / 177**
(Case 1b), against 204 / 252 and 198 / 247 by default. |dT| vs default was <= 5e-11 K, and solve wall time was
+7-10 %. The T0242 benchmark (`benchmarks/o007_amg_sweeps.json`) reproduces 145 and 141 at L0 through the production
option. **[S] The founder's projection is about 225-232 at L2**, from the L1-to-L2 growth of 1.25-1.29 seen in
T0228. It is speculation: no two-sweep solve has been run above L1.

### 0.1 Candidate (one, not tuned)

**`a_q1h4_graded_gs2`**: T0228's candidate 1, `a_q1h4_graded`, unchanged in every respect, plus
`GridRule.amg_gs_sweeps = 2`, the founder's value. Candidate 1 is: Q1, h0 4 mm, near_margin 2 mm, dz_max 1 mm, nz_min 1,
min_cells 2, zrefine, edge_grading (1e-4, 2.5, 4e-3, 0.5), T0228's mandatory lines, SNAP_FRACTION 1e-2, linear_rtol
1e-11, CG cap 400, AMG seed 20261103, Picard 1e-4 K, levels [0, 1, 2], r = 2.

The script asserts at import that its `GridRule` equals `dataclasses.replace(T0228 rule, amg_gs_sweeps=2)`.
`frozen_config.json` is `research/o007_dev2/frozen_config.json` copied key for key. Only `candidate_id`, `feasible`,
`levels_missing` and `rationale` may differ, and `amg_gs_sweeps: 2` is added. Every copied value is checked against
the candidate and the production constants before writing. There is no second candidate and no tuning of the sweep
count.

### 0.2 Eligibility (T0228 note sec. 0.2, criteria 1-4, unchanged)

Every criterion is measured **at level 2 on all six cases and both dev layouts**:
1. **Gates.** Energy balance <= 1e-6; the manufactured case also needs |Q_out / 64.648 W - 1| <= 1e-6. Picard
   residual < 1e-4 K. Node-count growth 8 +/- 15 % per level. Every reported point is a node at every level, with
   stencils recorded. No linear-solve failure.
2. **CG headroom.** At most 300 CG iterations in every L0-L2 solve at every Picard step: the level runs, the
   dev-layout calibration solves and the constant-k nulls (`_gate_constant_k`, T0232). The 300 rule is kept (I0124).
   Iterations are counted by T0207's `cg_only` callback. The production `meta["cg_iterations"]` and
   `cg_max_iterations` (T0222) are recorded alongside as a cross-check.
3. **Accuracy at level 2.** A1 <= 0.008. A2 <= 0.040 K. A4 (`mfos.metrics.gci_capped`, floor 1e-3 K) <= 0.40 K on the
   cases and <= 0.25 K on the dev-layout dies (Tj_max per die).
4. **Memory.** Every E009 finest solve <= 217.6 GB. The peak is the measured peak where that exact solve ran.
   Otherwise it is DOF x the maximum measured whole-process Q1 bytes/DOF over solves with >= 1 M DOF (T0207, T0225
   and this study). Fresh layouts count as 1.5 x the larger dev layout's DOF.

`feasible` is true only if every criterion is measured at L2 on all eight problems and holds, and the protocol
conditions of 0.3 hold. A criterion missed with measured data rules the candidate out at once (`ruled_out`). Before
the founder's burst the expected state is `feasible: false` with `levels_missing`, and that is a valid completion.

### 0.3 Protocol: production solver, every level re-measured, no reuse

- Every solve goes through production `thermal_fem` with a `GridRule` that carries `amg_gs_sweeps = 2`. This covers
  the box-stack and layout modes, the calibration solves and the constant-k nulls, whose grids come from the same
  rule. `_sa_solver` is not patched. The only wrappers are T0207/T0228's measurement wrappers: a counting `callback`
  on the outer CG call, and capture of the returned result. Neither changes an iterate.
- The worker reads `amg_gs_sweeps` from the production result's `meta`. If it is not 2, the solve is recorded as
  `failed_amg_gs_sweeps`, with exit code 5.
- **No reuse.** The solver changed, so every level of every problem is solved again into `research/o007_dev3/cache/`.
  No T0225, T0228, T0235 or founder-diagnostic solve feeds any value. `reused_levels` is `[]` in every record.
- **Protocol conditions** are validity conditions, not eligibility criteria. Each one can only make `feasible`
  stricter. (a) Every record has `amg_gs_sweeps == 2`. (b) No reused level. (c) The `cg_only` count equals
  `meta["cg_iterations"]` on every solve (T0228 found mismatch 0). If any fails, `feasible` is false and the
  experiment is broken. That says nothing about the rule.

### 0.4 Problems and records (as T0228 sec. 0.3)

The problems are Cases 1a, 1b, 2, 3 and the N-layer DBC case in box-stack mode, and the manufactured case in layout
mode. All use O006's frozen references, checked by sha256 first. The dev layouts are seed 20261101 only, with their E006
fingerprints asserted: side_by_side with 6 dies per switch and u_shaped with 2. There are no fresh layouts and no
holdout data. Operating point: calibrated on L0 to a hottest-die rise of 60 +/- 1 K above 65 C coolant,
h = 5000 W/(m2 K), k(T).

Every record of T0228 is kept: per-point and per-die values, errors, gci_capped, branch, p_obs, d1, d2, stencils,
argmax_xyz and moves, the constant-k column, the F3 null, node-count ratio, DOF, wall time, peak RSS, the final true
relative residual, and the **die-centroid-node diagnostic GCI**.

In addition, every case and layout record carries:
- `amg_gs_sweeps` from the production meta of all its solves;
- `reused_levels`;
- `cg_max_iterations_per_level` and `linear_rel_residual_max_per_level`;
- a `solves` list giving `cg_max_iterations` and `linear_rel_residual_max` (T0222) for every solve.

### 0.5 Consistency diagnostic (not a criterion, not a gate)

For each problem, level and reported value that T0228 also measured, the diagnostic records |T_new - T_T0228| with
both Picard counts. It also records both CG maxima, the calibrated powers and, on the same platform, the wall ratio.
Reported values are case points, die Tj_max, die Tj_mean, die-centroid-node T, and constant-k nulls where both exist.
A value is **flagged if |dT| > 1e-6 K while the Picard counts agree**. [I] Expectation: the smoother changes only the
preconditioner. At the same rtol (1e-11) both solutions are the same discrete solution to about 1e-10 K, as the
founder diagnostic measured (5e-11 K). A flag would point to a change other than the smoother. It would be reported
and investigated, and it changes no verdict. T0228's N-layer L0-L2 are T0225 solves and are compared as T0228 holds them.

### 0.6 Runs, memory, burst

Local runs follow T0228's memory rule, one child process at a time. The pre-solve estimate is DOF x the criterion-4
bytes/DOF x 1.15. A solve runs if the estimate is <= 5 GB, or <= 10 GB when `memory_pressure` shows >= 50 % free and
swap is < 4 GB (re-checked every 3 min, for up to 12 min). Otherwise it is skipped and left for the burst. A watchdog
stops the child at 10 GB RSS or 8 GB swap. [F] `plan.json`: every L0 and L1 and the manufactured L2 are local
candidates. Four need the memory_pressure condition (Case 1b L1, N-layer L1, side_by_side_6 L1, manufactured L2),
and seven L2 solves are burst-only (estimates 19-66 GB).

`--full` runs every solve under 0.85 x physical memory, then `--report`. The burst command is:
`scripts/burst_gcp.sh --cmd "uv run python research/scripts/o007_dev_study3.py --full" research/o007_dev3`.
After the local run, `plan.json` lists every solve the burst must run. Each memory estimate is T0228's measured peak
for the same solve and the criterion-4 rule. [I] A Gauss-Seidel smoother stores no extra operator. Each wall estimate
[S] is T0228's measured wall for the same solve x the two-sweep wall ratio measured locally (the maximum over the L1
solves).

### 0.7 E009 cost table and regression guard

The E009 cost table uses T0228's method (sec. 0.6 there, `e009_table`), with this study's measurements. The dev A1, A2
and A4 values at L2 are recorded in `dev_study.json` → `chosen.e009_regression_guard` for E009's K1 (> 0.05 scaled) and
K2 (> 0.25 K) guard. Every change made after data is labelled as such in this note.

### 0.8 What would prove the hypothesis wrong, and what would show the experiment broken

The hypothesis under test, from the T0235 verdict and the founder diagnostic: T0228's CG excess was the order-1 AMG's
smoothing, and with 2 sweeps candidate 1 meets every criterion, the 300 rule included. Two competing explanations:
- **E1: the smoother sets the count.** The roughly 28 % L0/L1 reduction persists, and L2 lands near 225-232 [S].
- **E2: the weak-Robin conditioning grows faster than the extra smoothing helps.** The reduction erodes with
  refinement, and L2 on Cases 1a/1b approaches or exceeds 300.

The discriminating test is the per-level CG ratio new / T0228. Under E1 it stays near 0.72 at L0, L1 and L2. Under E2
it rises toward 1 with level. L0/L1 are measured locally; L2 needs the burst.

**Rule unfit (hypothesis refuted)** if any of these is measured: CG > 300 on any L0-L2 solve; A1 > 0.008; A2 > 0.040 K;
A4 > 0.40 K on a case, or Tj_max GCI > 0.25 K on a dev die (divergent sequences included); a gate failure.
**Experiment broken, no conclusion about the rule** if: a protocol condition of 0.3 fails; the reference hash or a
fingerprint fails; or the consistency diagnostic flags values. A flag is not a gate, but it would make me distrust
the run until explained.

---
*Everything below was written after the data.*

Pre-registration commit: `1cd23ad8` (`research/o007_dev3/preregistration.json`, copied to `dev_study.json` as
`preregistration_commit`). The local run's log starts at 18:22:29, after the commit, and its first line checks that
`1cd23ad8` is an ancestor of HEAD.

**Post-data changes, labelled.** There is one. `plan.json` → `burst_totals` gained `min_physical_GB_for_full_gate`, the
largest criterion-4 estimate of a burst solve divided by 0.85. It changes the plan output only, not the analysis, a
criterion, a record or `frozen_config.json` (see sec. 7). Nothing else in the script, the candidate, the criteria or
the cost rule changed after the first solve.

## 1. Outcome

**`feasible: false`, the expected pre-burst state. The candidate is unverified, not ruled out.**
- L2 is measured on the manufactured case. It is missing on Cases 1a, 1b, 2 and 3, the N-layer case and both dev
  layouts (`levels_missing`). All seven exceed the 10 GB local cap.
- No criterion is missed by measured data, and every protocol condition of 0.3 holds.
- [F] CG max over every solve of this study, calibration and constant-k included, is **180** (Case 1a L1). It was 252
  in T0228 at the same level.
- [F] At every level measured, the CG count is **0.68-0.72 x T0228's** on all eight problems, at the same discrete
  solution to <= 3.6e-11 K.

## 2. What was run (commands, exit codes)

1. Before section 0 (grid only): `uv run python research/scripts/o007_dev_study3.py --plan`, exit 0.
2. Section 0, the script and `plan.json` committed as `1cd23ad8`. Then `preregistration.json` was written.
3. `uv run python research/scripts/o007_dev_study3.py`, exit 0, 18:22-18:40 (`research/o007_dev3/run_local.log`).
   - 23 child-process solves, one at a time: 11 L0 (5 of them calibration solves), 8 L1, the manufactured L2, and 3
     constant-k nulls (manufactured L2, both layouts at L1, the finest level run locally).
   - Case 1b L1 waited 3 min for memory_pressure >= 50 % free.
   - Largest peak 7.83 GB (manufactured constant-k L2, run under the memory_pressure condition, swap 0). Every other
     solve was <= 4.91 GB.
   - Seven L2 solves skipped by the memory gate (estimates 19-66 GB).
4. `--report` (inside step 3, and again after the post-data plan change), exit 0.
5. The packet's DoD commands: frozen-config check, dev-study check, determinism re-run of `--report` (byte-identical
   `frozen_config.json`), plan check, note exists. All exit 0. `uv run ruff check research/scripts/o007_dev_study3.py`
   exit 0. `uv run mfos gate --fast` exit 0 ("all gates passed").

## 3. Checks [F]

- **Inputs.** Reference hashes `befc5efa...` / `ca05847b...` matched. Dev fingerprints `1f66b68a...` and
  `6aaf383a...` equal E006.yaml. Seed 20261101 only, no fresh layouts, no holdout data.
- **Protocol (sec. 0.3).** `amg_gs_sweeps` is 2 in the production meta of every solve. `reused_levels` is `[]` in every
  record. The `cg_only` count equals `meta["cg_iterations"]` on every solve (mismatch 0). `protocol.ok` is true.
- **Gates.**
  - Energy balance <= 3.4e-12 on every solve (largest 3.31e-12, Case 2 L1).
  - Manufactured |Q_out / 64.648 W - 1| <= 2.1e-9.
  - Picard residual <= 4.8e-5 K (4.71e-5 K on the u_shaped_2 L0 calibration solve cal1, review T0247).
  - Largest true relative residual 3.8e-11 (Case 1b L1); every `linear_rel_residual_max` <= 3.8e-11.
  - Node-count growth 7.25-7.62 per level.
  - No solve hit the 400 cap.
- **Operating point.** Calibration reproduces T0228's: 32.232107 W per die, hottest-die rise 60.16 K, in 2 solves
  (side_by_side_6); 47.141886 W, 59.95 K, in 3 solves (u_shaped_2). The powers differ from T0228's by < 4e-12 W.
  Calibration CG max is 87 and 92.
- **F3 null.** The manufactured case at constant k (L2) is off by 2.51 K, scaled 0.0249. It fails A1 and A2, so the k(T)
  case still discriminates.

## 4. Results (`dev_study.json` → `chosen`) [F]

| problem | CG max L0 / L1 / L2, this study | T0228 | ratio new / T0228 per level | max abs err at finest, K | A1 (finest) |
|---|---|---|---|---|---|
| case1a | 145 / 180 / - | 204 / 252 / 316 | 0.711 / 0.714 | 0.116 (L1) | 0.0021 |
| case1b | 141 / 177 / - | 198 / 247 / 318 | 0.712 / 0.717 | 0.0134 (L1) | 0.0019 |
| case2 | 58 / 83 / - | 81 / 116 / 162 | 0.716 / 0.716 | 0.0174 (L1) | 0.0025 |
| case3 | 85 / 135 / - | 119 / 189 / 249 | 0.714 / 0.714 | 0.0075 (L1) | 0.0015 |
| nlayer_dbc | 94 / 136 / - | 132 / 191 / 259 | 0.712 / 0.712 | 0.152 (L1) | 0.0019 |
| mms | 37 / 51 / **66** | 53 / 75 / 93 | 0.698 / 0.680 / **0.710** | 0.0050 (L2) | 5.0e-5 (A4 0.0187 K) |
| side_by_side_6 | 87 / 132 / - (cal 87, const-k L1 132) | 122 / 185 / 253 | 0.713 / 0.714 | n/a | n/a |
| u_shaped_2 | 92 / 128 / - (cal 92, const-k L1 128) | 128 / 179 / 250 | 0.719 / 0.715 | n/a | n/a |

The error values equal T0228's (sec. 5), so T0228's accuracy findings carry over unchanged.
- Case 1a's s2 mean is 0.116 K off at L1.
- On the dev layouts, Tj_max rises from L0 to L1 on every die. d1 is +0.058 to +0.304 K on side_by_side_6 and
  +0.258 to +0.395 K on u_shaped_2. The argmax moved on 8 of 12 and 4 of 4 dies.
- The die-centroid-node d1 is +0.048 to +0.142 K and +0.109 to +0.181 K. The centroid node is the same node at every
  level on every die.
- With two levels, no GCI exists yet on the layouts.

**Two-sweep wall time (local, same platform, L1).** The ratio of process wall to T0228's is 1.166 (1a), 1.135 (1b),
1.089 (2), 1.114 (3), 1.084 (manufactured), 1.147 (side_by_side_6) and 1.170 (u_shaped_2). [I] The N-layer ratio of
0.353 is not comparable: T0228's N-layer L1 is a T0225 probe record from another worker. The plan uses the maximum,
1.170.

## 5. Consistency diagnostic (sec. 0.5; not a criterion) [F]

266 values compared at every level and variant that both studies measured. These are case points, die Tj_max, Tj_mean
and centroid-node T, and the constant-k nulls.
- **Max |T_new - T_T0228| is 3.6e-11 K** (manufactured). Per problem the maximum is 3.0e-12 to 3.6e-11 K.
- The Picard counts agree everywhere. **0 values are flagged** at 1e-6 K.
- [I] The smoother changed the iteration count and nothing else. Both runs reach the same discrete solution within the
  linear tolerance, as the founder diagnostic found.
- [I] Prediction stated before any L2 data: the burst's L2 values will equal T0228's L2 values to about 1e-10 K. That
  means A1 6.8e-4, A2 0.0386 K, A4 0.142 K on the cases and 0.124 K on the layouts, all inside the margins. A
  difference above 1e-6 K at L2 with equal Picard counts would contradict this and needs explaining before any verdict
  is trusted.

## 6. Diagnosis of T0228's CG-only miss (mf-diagnosis), as far as local data go

- **E1, smoother-limited (supported).** The new/T0228 CG ratio is constant at 0.711-0.719 on L0 and L1 of every box and
  layout problem. On the manufactured case, the only L2 measured, it is 0.698 / 0.680 / 0.710. [I] E2 predicts a ratio
  that climbs with level toward 1. The manufactured case shows no such climb (ratios 0.698 / 0.680 / 0.710; its L2 ratio is 0.012 above L0, review T0247),
  and the plates show none from L0 to L1 (+0.003 to +0.005).
- **E2, conditioning outgrows the smoother (not excluded).** The weakly cooled 300 mm plates, Cases 1a/1b, have not
  been measured at L2. A ratio near 1 there would need a sharp break between L1 and L2 that no measured problem shows.
- [S] Projection at the measured L1 ratio: Case 1a 0.714 x 316 = **226**, Case 1b 0.717 x 318 = **228**, Case 3 178,
  N-layer 184, side_by_side_6 181, u_shaped_2 179. This agrees with the founder's 225-232. Case 1b, the worst case,
  needs a ratio of 0.943 to exceed 300.
- **What would prove this wrong:** any L2 count above 300, or an L2 ratio above about 0.8 on the plates.
- **Class:** implementation, meaning the linear-solver configuration, not the grid or the physics. Confidence 0.65
  until the plates' L2 is measured.

## 7. The founder's burst (completes this study; it resumes from the committed cache)

`scripts/burst_gcp.sh --cmd "uv run python research/scripts/o007_dev_study3.py --full" research/o007_dev3`

- Run it after this branch is merged (the bundle defaults to `main`), or with `MF_REF=<this task branch>`.
- **9 solves** (`plan.json` → `burst_solves`): L2 of Cases 1a, 1b, 2 and 3, the N-layer case and both dev layouts, and
  the two layout constant-k L2 nulls. Unlike T0228, the **N-layer L2 is run**, because nothing is reused.
- **Machine (post-data finding, plan only).** `--full` skips any solve whose estimate (DOF x 4964 B/DOF x 1.15) exceeds
  0.85 x physical memory. The N-layer L2 estimate is 77.7 GB, so the machine needs **>= 91.4 GB**
  (`min_physical_GB_for_full_gate`). The script's default **n2-highmem-32 (256 GB)** works, and so does an
  n2-highmem-16 (128 GB). **The e2-highmem-8 (64 GB) that T0228's burst used would skip the N-layer L2**, leaving
  `feasible: false`. Do not reuse that machine type.
- [F] T0228 measured peaks of 10-30 GB for the same solves on Linux. The N-layer L2 measured 41.9 GB in T0225.
- [S] Wall time is T0228's measured burst wall per solve x 1.170: 13-100 min each, 6.1 h in sequence on an e2-class
  core. Recommended timeout 19 h (3 x).
- The run ends with `--report`. `feasible` becomes true only if every criterion of 0.2 holds at L2 on all eight
  problems and the protocol conditions hold.

## 8. E009 regression guard (K1 > 0.05 scaled, K2 > 0.25 K) [F]

`dev_study.json` → `chosen.e009_regression_guard` holds the guard values:
- **At L2 (manufactured only, so far):** A1 5.0e-5, A2 0.0050 K, A4 0.019 K.
- **At L1:** A1 max 0.0025 (Case 2). A2 max 0.152 K (N-layer), with Case 1a at 0.116 K.
- [I] By sec. 5 the L2 values should reproduce T0228's L2: A1 6.8e-4, A2 0.0386 K, A4 0.142 K on the cases and 0.124 K
  on the layouts. That is a factor of 6.5 below K2 and 74 below K1.
- E009's spec should quote this study's L2 values after the burst, not the L1 or prediction values above.

## 9. E009 cost table (`chosen.e009_plan`, T0228's method)

- [F] The method gives a scikit-fem finest peak of 70.6 GB [S] (fresh layouts at 1.5 x side_by_side_6; 4964 B/DOF from
  the manufactured constant-k L2 on macOS) and an FV L2 peak of 104.8 GB [S]. Both fit in 217.6 GB, so plan
  **n2-highmem-32** for E009.
- [I] **The table's wall column is too low.** Its [S] L2 walls come from macOS s/DOF x 1.3 per level, since this study
  has no L2 measurement yet (Case 1a L2 513 s). T0228's burst measured 1808 s for that same solve on Linux, 3.5 x more.
  The 6.2 CPU-hours total (2.6 scikit-fem) is therefore an underestimate. For the burst itself, use the
  T0228-measured basis of sec. 7.
- I did not change the table's pre-registered rule. After the burst it uses measured values for every dev solve.

## 10. Facts, inferences, speculation; recommendations (no production change made)

- [F] Under the production option `amg_gs_sweeps = 2`, candidate 1's grids are identical to T0228's. Its solutions agree
  to <= 3.6e-11 K. Its CG counts are 68-72 % of T0228's at every level measured, and CG max is 180. Every gate and
  protocol condition holds.
- [I] The only criterion T0228 missed, CG <= 300 at L2 on Cases 1a/1b, is very likely met. Every other criterion should
  reproduce T0228's passing values.
- [S] L2 CG of about 226 / 228 on Cases 1a / 1b.
- **Recommendation 1 (founder):** run the burst of sec. 7 on n2-highmem-32 (the default) or n2-highmem-16, not
  e2-highmem-8.
- **Recommendation 2 (planning):** if `feasible` becomes true, E009's frozen configuration is
  `research/o007_dev3/frozen_config.json`. If an L2 count exceeds 300, the candidate is ruled out under the
  pre-registered rule. Any further smoother change then needs a new pre-registration, and no re-tuning on these
  cases.

## Burst result (founder session, 2026-11-06; `e2-custom-12-98304`, 330 min, commit bdb57af)
- [F] `--full` measured every L2 solve with `amg_gs_sweeps = 2`; nothing reused. **`feasible: true`: candidate
  a_q1h4_graded_gs2 is eligible on every pre-registered criterion at level 2**, with the 300 rule unchanged.
- [F] CG max at L0 / L1 / L2: Case 1a 145 / 180 / **224** (T0228: 316), Case 1b 141 / 177 / **227** (318), Case 2
  58 / 83 / 115, Case 3 85 / 135 / 176, N-layer 94 / 136 / 184, manufactured 37 / 51 / 66, side_by_side_6 87 / 132 / 181,
  u_shaped_2 92 / 128 / 181; constant-k nulls at L2 180 and 181. The maximum is 227, and every gate holds on every case
  and layout.
- [F] Margins at L2 are unchanged from T0228 to about 1e-11 K, as the smoother changes the iterates only: A1 6.8e-4,
  A2 0.0386 K (N-layer, limit 0.040), A4 cases 0.142 K, A4 layouts 0.124 K. Energy balance <= 7.8e-12. Peaks 10-42 GB.
