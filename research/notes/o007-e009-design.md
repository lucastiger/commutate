# E009 design: scikit-fem reference at the re-frozen graded Q1 rule (amg_gs_sweeps = 2) against O006's references and the L2 at levels 1-3 (T0244)

Author: scientist, T0244 attempt 1, 2026-11-06. Replaces T0238 (cancelled). The brief is T0229's, with T0244's changes.
Deliverables: `experiments/drafts/E009.yaml`, `experiments/runners/e009_run.py`, `research/e009/dev_rows.json` (smoke rows,
not evidence), this note. Labels: **[F]** fact (file, or a command listed in sec. 10), **[I]** inference, **[S]**
speculation or extrapolation.

## 0. Precondition (checked before any design work)

- [F] `research/o007_dev3/frozen_config.json` has `feasible: true` and `levels_missing: {}`.
- [F] `dev_study.json → chosen.summary` has `all_levels_measured: true`, `levels_complete: true` and
  `errors_at_level` = 2 for all six cases.
- [F] `chosen.e009_regression_guard.per_problem` has `at_L2: true` on all eight problems: Cases 1a, 1b, 2, 3, N-layer,
  manufactured, side_by_side_6 and u_shaped_2.
- [F] `protocol.ok`: `amg_gs_sweeps` was 2 on every solve, and nothing was reused.
- [F] The founder burst result is on main as commit `e803141b`.

The configuration is final, not provisional, so the design proceeds.
The file's sha256 is `0226b770…0e9a` (`config.fem_rule_file_sha256`).

## 1. What E009 measures, and the swapped roles

scikit-fem (production `src/moduleforge/solvers/thermal_fem.py`) is the solver under test. It is checked against:
- (a) O006's frozen references: series sha `befc5efa…`, manufactured sha `ca05847b…`;
- (b) the in-house FV L2 (`thermal_fv` / `thermal_layout`, its frozen rule unchanged) at levels 1, 2 and 3, on five
  generator layouts at O003's operating point.

Criteria A1-A4, K1 and K2 are the objective's, unchanged.

**Reused by import from E006, unchanged** (`import e006_run as E6`): `load_refs`, `series_checks`, `mms_checks`,
`Checks`, `Stats` (its `lines` bisection check), `dev_layouts`, `fresh_layouts`, `preflight` (FV memory), `a4`,
`direction`, `mms_layout`, `_gate_max` and `log`. Through them, `e006_series.py` and `e006_mms.py` are also reused.
E006's L2-specific drivers are not reused: `run_series_case`, `run_mms` and `calibrate_power` all call the FV. E009
has its own scikit-fem drivers. Their problem construction is the same as the dev studies' (T0207 `solve`, T0228/T0243
workers), so dev and registered values come from the same calls:
- **Box-stack mode.** The cases are built from the frozen JSON. Each layer is `BoxLayer(t, k, nz_min)`, and the
  mandatory `extra_lines` are the x and y of each source's frozen reference maximum (the centroid lines are built in).
- **Layout mode (manufactured case).** `mms_layout()` with `source`, `flux` and `T_inf`; Picard starts at `mms_Tc_K`
  = 340 K. The mandatory lines are the x, y and z of the eight non-mean points.
- **Generator layouts.** `solve_layout` with no extra lines. Tj max is the maximum nodal value on the die top face.

## 2. The one frozen configuration

- `config.fem_rule` is `frozen_config.json` copied verbatim. The YAML block was generated with `yaml.safe_dump` and
  checked by `yaml.safe_load(...) == json.load(...)`. Hand-copying would not be safe: PyYAML reads `1e-11` as a string.
- The runner builds one `GridRule` from it, key for key (`rule_from`): `h0`, `nz={}`, `default_nz=nz_min`, `zrefine`,
  `near_margin`, `min_cells`, `element_order`, `dz_max`,
  `edge_grading=(first_offset_m, ratio, max_offset_m, min_gap_fraction)` and `amg_gs_sweeps`.
- Every scikit-fem solve uses that rule, through `solve_box_stack`, `solve_layout` or, for the constant-k nulls,
  `layout_grid` plus `_solve_grid`. That covers every case, every layout level, every calibration solve and every
  constant-k column.
- There is no research-side grid or solver emulation, and no monkey-patching of thermal_fem.
- **Per-solve assertion.** `Solves.fem` raises if `result.meta['amg_gs_sweeps'] != fem_rule['amg_gs_sweeps']`. That is
  an error result, never a verdict. The smoke rule keeps `amg_gs_sweeps = 2`, so the assertion is exercised there too.
- **Gated check `fem_rule_frozen`, before any solve.** It requires all of the following:
  - `config.fem_rule` equals the file on disk;
  - `feasible` is true and no level is missing;
  - every production constant the file records equals thermal_fem's: `SNAP_FRACTION`, `LINEAR_RTOL`, `CG_MAXITER`,
    `AMG_SEED`, `PICARD_TOL_K`, `REFINEMENT_RATIO`, `LEVELS`, and `DATA_INTORDER` = 7.

  If it fails, the run refuses to solve. This guards against a later edit of thermal_fem's constants, which the
  `GridRule` alone would not reveal. `code_under_test` hashes `thermal_fem.py` as well.
- **Constant-k nulls (F3, and the layouts' `dT_const_k`).** These use `thermal_fem._solve_grid` on the production
  `layout_grid`, with k fixed per material at the volume-mean temperature of the finest k(T) solve. This is exactly
  T0207/T0228/T0243's method. [I] `_solve_grid` is a private name. A refactor of thermal_fem that renames it breaks the
  runner loudly (AttributeError), and never silently.

## 3. Rows

**Case rows** (`kind=case`, `is_finest: true`, one per reported value; 5 box cases × their points + 9 manufactured).
Each row has:
- `T_fem` (= `fem_lv2`), `T_ref`, `case_scale`, and `fem_lv0..fem_lv2`;
- the A4 record (`gci`, `a4_branch`, `p_obs`, `d1`, `d2`, `non_asymptotic` = p_obs outside [0.5, 2]);
- `err_lv0..2_K`, `scaled_err`, `gci_over_err` and `dT_const_k`;
- **`snap`** (`x_req`, `x_used`, `y_req`, `y_used`, `z_req`, `z_used`, `distance_m`), and `stencil_per_level` (index,
  on_line, coord, lo, hi per axis);
- per grid solve: `fem_cg_max_iterations_lvL`, `fem_linear_rel_residual_max_lvL`, `fem_cg_hit_maxiter_lvL` and
  `fem_dofs_lvL`.

Means are Galerkin source-face integrals (`tj_mean`). They have no snap and no stencil. For the constant-k series
cases, `dT_const_k = T_fem`, as in E006. The manufactured rows also carry `kconst_W_mK` and `layer_mean_T_K`.

**Crosscheck rows** (`kind=crosscheck`, `is_finest: true`, one per die of the five layouts). Each row has:
- `fem_lv0..2` and `l2_lv1..3`;
- both A4 records (`gci` / `l2_gci`, branches, p_obs, d1, d2);
- `fem_direction`, `l2_direction` and `same_side`;
- `f5_ok` (`l2_gci <= 0.25`), `a3_ratio`, `summed_gci_K` and `abs_diff_K`;
- `layout_set` (dev / fresh), `family`, `dies_per_switch` and `fingerprint`;
- `power_w`, `calibration_rise_K` and `calibration_history` (power, rise, CG data per solve);
- `tj_max_xyz_per_level` and `tj_max_node_moves`;
- `dT_const_k` and `a3_ratio_const_k`;
- the T0228 die-centroid-node diagnostic (`centroid_node_T_per_level`, `centroid_node_gci`);
- per grid solve, the scikit-fem CG maximum, residual, cap flag and DOF;
- the L2's `linear_iters`, `linear_residual` and cells per level (the FV reports these; it has no cap flag).

**Operating point.** Power is calibrated per layout on scikit-fem level 0 of the frozen rule, then used unchanged by
both solvers on every grid.
- Method: E006's proportional update from 30 W, tolerance `calibration_tol_K` = 0.25 K, at most 10 solves. A miss
  raises an error.
- The level-0 solve at exactly the returned power **is** `fem_lv0`; it is not solved twice.
- [F] On the dev layouts this returns the dev study's powers (32.232107 W and 47.141886 W). The calibration histories
  in `research/o007_dev3/cache/*calibration.json` show it:
  - side_by_side_6: 30 W gives 55.84 K, then 32.232107 W gives 60.160 K;
  - u_shaped_2: 30 W gives 37.48 K, 48.029515 W gives 61.130 K, then 47.141886 W gives 59.945 K.

  Every rejected iterate is ≥ 1.13 K off and every accepted one ≤ 0.16 K off. The dev study's 1 K tolerance and this
  0.25 K tolerance therefore stop at the same solve.
- The `operating_point` gate is ±1 K, as in the objective.

## 4. Metrics and recompute entries (exactly as the objective states)

| metric | fn | columns / params | where |
|---|---|---|---|
| max_case_scaled_err (A1, K1) | max_scaled_abs_err | pred T_fem, ref T_ref, scale case_scale | kind=case, is_finest |
| max_abs_err_K (A2, K2) | max_abs_err | pred T_fem, ref T_ref | kind=case, is_finest |
| max_l2_consistency (A3) | max_gci_consistency | pred_levels [fem_lv0..2], ref_levels [l2_lv1..3], floor 0.001, **ref_gci_cap 0.25** | kind=crosscheck, is_finest |
| max_conservative_gci_K (A4) | max_gci_capped | levels [fem_lv0..2], floor 0.001 | is_finest |

- **F5 is not a sanity check.** It acts only through `ref_gci_cap`: any die with L2 GCI > 0.25 K makes A3 +inf (not
  met, INCONCLUSIVE per `decision_if_inconclusive`), with no redraw (I0099, T0201). It is also reported as
  `max_l2_gci_K`, `n_f5_fail_dies` and per-row `f5_ok`.
- **Secondary metrics:** `a3_fresh`, `a3_dev`, `a4_fresh_K`, `a4_dev_K`, `a4_cases_K`, `max_a3_ratio_const_k`,
  `max_l2_gci_K`, `n_f5_fail_dies`, `n_oscillatory_values`, `n_non_asymptotic_values`, `n_same_side_dies` and
  `n_fem_solves_cg_over_300`.
- **Null baseline (F3):** the column `dT_const_k` applies to A1 and A2.

**Uncertainty.** Every metric is a deterministic maximum over the complete measured set. No sample is drawn within the
run, so a bootstrap CI would be meaningless. They are reported as point values at `level 0.0`, as the objective's
`uncertainty: {use: point}` and E006 do. The discretisation uncertainty of every value is the A4 GCI itself, which is a
criterion. [I] The three fresh layouts are one draw per family. E009 makes no population claim about "all layouts", and
A3 / A4 on the fresh subset are reported separately so the held-out part can be read on its own.

## 5. Sanity checks: "experiment broken" vs "hypothesis false"

Gated (any failure means INVALID). They are listed in the spec in the order the runner reports them:
- **Before any solve:** `reference_sha256`, `series_cases_match_frozen_parameters`, `series_converged`,
  `case3_printed_values`, `nlayer_reduces_to_two_layer`, `mms_numeric_check` (F1), and `fem_rule_frozen`. A hash or rule
  mismatch stops the run outright.
- **Before the layouts:** `layout_fingerprints` (F4).
- **After the solves:** `node_persistence`, `node_count_growth` (8 ± 15 %, scikit-fem nodes and L2 cells),
  `constant_refinement_ratio` (x, y, z, both solvers), `energy_balance` (also manufactured vs 64.648 W),
  `picard_converged` (both solvers), `operating_point`, and `linear_solver_headroom` (no scikit-fem solve hit the
  400-iteration cap).

**What each kind of outcome means:**
- *Experiment broken:* a failed gate.
- *Hypothesis false:* K1 / K2 tripped (model or implementation error), or A1 / A2 / A4 missed with every gate passing.
- *Cross-check unable to judge:* F5. A3 is not met, then diagnosis.
- *Disagreement:* A3 > 1 with F5 passing. One of the two solvers is wrong beyond its estimate, so diagnose before any
  use.

The CG-iteration count above 300 was an eligibility criterion of the dev study (I0124). In E009 it is reported
(`n_fem_solves_cg_over_300`), not gated. The gate is the cap (I0110), as the brief states.

## 6. Dev values recorded at freeze; regression guard (`config.dev_regression_guard`)

[F] **Measured** at level 2 of the frozen rule (T0243 `chosen.e009_regression_guard`; Cases 1a/1b/2/3, N-layer and both
dev layouts on the founder burst, Linux; manufactured case on macOS):

| | A1 (scaled) | A2 K | A4 K |
|---|---|---|---|
| max over cases | 6.80e-4 (Case 2) | 0.0386 (N-layer) | 0.142 (N-layer) |
| max over dev-layout dies | – | – | 0.124 (u_shaped_2) |

Per-problem values are in the spec.
- K1 (> 0.05) is 74 × the dev A1, and K2 (> 0.25 K) is 6.5 × the dev A2.
- CG max at L0-L2 was 227 (Case 1b L2) against the 400 cap.
- The runner reports this run's per-problem values next to these (`regression_guard`, informational).
- [I] The dev problems use the same code, the same grids and the same powers. Their E009 values should therefore
  reproduce the dev study to about 1e-10 K, as T0243 sec. 5 found between platforms. A larger change there would mean
  something other than the fresh layouts changed.

## 7. Cost table and burst VM (measured vs extrapolated)

Solves are sequential and in-process, as in E006. The runner holds one grid problem at a time. [I] pyamg/scipy CG is
essentially single-threaded, so CPU-hours ≈ wall-hours.

| block | basis | wall |
|---|---|---|
| scikit-fem, six cases L0-L2 + manufactured const-k | [F] measured: L2 on Linux (burst 1861 / 2309 / 969 / 1203 / 3041 s), manufactured L2 186 s + const-k 99 s (macOS), L0/L1 macOS | 2.7 h |
| scikit-fem, dev layouts L0-L2 + const-k L2 | [F] measured Linux: side_by_side_6 5554 + 1694 s, u_shaped_2 2236 + 674 s; L0/L1 (macOS) ≈ 0.06 h | 2.9 h |
| scikit-fem, 3 fresh layouts | [S] 1.5 × side_by_side_6 measured per level (L2 8331 s, const-k 2541 s, L1 194 s, calibration 3 × 20 s) | 9.3 h |
| FV L2 levels 1-3, dev layouts | [F] measured (T0204 burst, Linux): 22 + 209 + 1826 s and 16 + 146 + 1296 s | 1.0 h |
| FV L2 levels 1-3, 3 fresh layouts | [S] 1.5 × side_by_side_6 measured | 2.6 h |
| F1 reference checks | [F] measured in the smoke run (sec. 9; full resolution, unchanged by the grids) | < 0.1 h |
| **total** | | **≈ 18.5 h → `cpu_hours_est: 20`** |

- `timeout_min: 2700` (45 h). That is about 2.4 × the estimate. It equals the dev study's `recommended_total_timeout_h`.
- [I] I did not use T0243's own table for the fresh-layout walls. It extrapolates them from macOS s/DOF (3180 s for
  14.2 M DOF), but Linux measured 5554 s for side_by_side_6's 9.5 M DOF (dev-study note sec. 9 says the table's wall
  column is too low).
- **Memory.**
  - [F] Measured peaks: scikit-fem L2 10-42 GB (N-layer 41.8 GB); FV L3 69.9 GB (side_by_side_6).
  - [S] Extrapolated fresh peaks: scikit-fem 70.6 GB (14.2 M DOF × 4964 B/DOF, the preflight figure) and FV L3
    105 GB (1.5 × 58 M cells at the measured 1.2 kB/cell).
  - FV preflight: 87 M cells × 1500 B = 131 GB ≤ 0.85 × 256 GB.
  - scikit-fem preflight: 14.2 M DOF × 4964 × 1.15 = 81 GB.
  - Machine: **n2-highmem-32 (256 GB)**, per policy `burst_experiments`.
  - [I] An n2-highmem-16 (128 GB, ≈ 121 GB usable) would refuse a fresh FV level 3 above about 69 M cells under the
    1500 B/cell preflight. Do not use it.
- **No checkpoint/resume in the registered run.** An evidence run is one process with one sealed seed. Resuming across
  processes would need a provenance design that E006 did not have. A crash costs the VM time, not evidence.

## 8. Smoke mode (`--smoke --rows-out research/e009/dev_rows.json`; never evidence)

It runs every case, both dev layouts and three "fresh" layouts drawn from the **non-sealed dev seed 7** (E006's smoke
seed). The fresh rule is exercised end to end without touching the sealed seed. Both solvers run on coarsened copies of
their frozen rules:
- **scikit-fem** (`smoke_fem_overrides`): h0 16 mm, near_margin 1 mm, dz_max 4 mm, edge grading (2 mm, 2.5, 4 mm, 0.5).
  `amg_gs_sweeps` = 2, Q1, ratio 2 and levels 0-2 are all unchanged.
- **L2** (`smoke_l2_rule`): H0_MAX 16 mm, LAT_FRAC 16, EDGE_FRAC 64, Z_CELLS 1, still at levels 1-3.
- Memory cap 5 GB (this Mac's agent budget). [F] Grid sizes were computed before running: scikit-fem L2 ≤ 0.86 M DOF,
  FV L3 ≤ 0.85 M cells.

Smoke exits 0 when the integrity checks pass: reference hashes, `fem_rule_frozen`, fingerprints and the F1 checks. The
solver gates are recorded in `meta.checks`. On these coarse grids, `node_count_growth` and F5 may legitimately miss.
That is a property of the smoke grids, not of the frozen rule, and it is recorded in sec. 9. `mfos exp check E009 --rows`
uses these rows only for the null-discrimination test (F3).

## 9. Smoke result (pipeline check on coarsened rules, macOS; NOT evidence, NOT the frozen rule) [F]

`research/e009/dev_rows.json`: 106 rows (60 case values, 46 dies), 389.6 s, peak RSS 3.59 GB. Exit 0.

**Passed:**
- every integrity and F1 check: hashes, `fem_rule_frozen`, fingerprints (5 distinct, one fresh per family from seed 7),
  series convergence, Case 3 printed values, N-layer reduction, manufactured self-check;
- `node_persistence` (max snap 5.7e-5 m on the 16 mm smoke cells);
- `constant_refinement_ratio`, both solvers;
- `energy_balance`: max 2.1e-9, the manufactured case against 64.648 W; every solve's own balance ≤ 1e-11;
- `picard_converged`: max 4.5e-5 K;
- `operating_point`: max |rise − 60| = 0.21 K;
- `linear_solver_headroom`: CG max 220, no cap hit, max residual 3.2e-11;
- the per-solve `amg_gs_sweeps == 2` assertion, on all 46 scikit-fem solves (61 solves in all with the 15 FV solves).

**Missed, as expected of the coarsening.** These misses reflect the smoke grids, not the frozen rule:
- `node_count_growth` at the coarsest step only (6.71-6.79 < 6.80 on Cases 1a/2/3 and the manufactured case). [I] With
  few cells per axis the node ratio ((2n+1)/(n+1))³ sits below 8. The frozen rule measured 7.25-7.62 (T0243).
- A3, A4 and F5 are +inf. Several 16 mm sequences diverge on both solvers (8 divergent and 15 oscillatory values; 35 of
  46 dies above the F5 cap).

**Metrics on the smoke grids:** A1 6.3e-3, A2 0.355 K (Case 1a s2 mean on 16 mm cells), A3 +inf, A4 +inf.

**F3 null:** `dT_const_k` gives 2.524 K / scaled 0.0251 (dev study at frozen L2: 2.51 K / 0.0249). It fails A1 and A2,
so `mfos exp check E009 --rows` raises no null problem.

[I] The smoke run exercises every code path of the registered run: calibration, level loop, constant-k, FV levels 1-3,
F5 cap, metrics and recompute. It says nothing about the frozen rule's accuracy. That is the dev study's role (sec. 6).

## 10. Commands run (exit codes)

1. Grid-size exploration (grid construction only, no solve), from a throwaway script in `$TMPDIR`: candidate smoke
   rules, plus the frozen rule's DOF on seed-7 layouts (7.9-8.6 M at L2). Exit 0.
2. `uv run mfos exp check E009` (before the smoke): exit 0, with the expected problem "dev_rows not found".
3. `uv run python experiments/runners/e009_run.py --smoke --rows-out research/e009/dev_rows.json`: exit 0, 6.5 min,
   log in `research/e009/smoke.log`.
4. The DoD checks: frozen-config / spec equality, exit 0. `uv run mfos exp check E009 --rows research/e009/dev_rows.json`,
   exit 0. Spec key-string check, exit 0. Note exists, exit 0. `uv run ruff check experiments/runners research`, exit 0
   after the lint-only fix of sec. 11.3. `uv run mfos gate --fast`, exit 0 ("all gates passed").

## 11. Open points for the founder or reviewer (not decided here)

1. **Calibration tolerance 0.25 K** (E006's) rather than the dev studies' 1 K. [F] It gives the same powers on the dev
   layouts (sec. 3), and the gate stays at ±1 K.
2. **Private thermal_fem names** are used by the runner: `_solve_grid`, `_materials` and `_count_nodes`. They belong to
   the production module under test and are hashed by `code_under_test`; T0207-T0243 used them the same way.
3. **Lint-only edit outside E009.** `research/scripts/e002_runner_harness.py` (T0076) was split into one statement per
   line, with `# noqa: E402` on the imports that must follow its environment setup. This was needed because the DoD
   command `ruff check experiments/runners research` lints explicitly named paths despite `extend-exclude`. The
   statements and their order are unchanged.
4. The registered run needs policy `burst_experiments` to include E009 (objective scope_in). That is a founder action.
