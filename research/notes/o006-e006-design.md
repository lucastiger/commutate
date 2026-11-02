# O006 / E006 design: thermal L2 against frozen references and scikit-fem (T0165)
Date: 2026-11-02 · Task: T0165 · Status: draft spec `experiments/drafts/E006.yaml`, runner `experiments/runners/e006_run.py`.
Update T0196 (pre-registration fixes after reviews T0194/T0195): see section 8. The F5 feasibility check on the two
development layouts gives a maximum scikit-fem estimate of 0.200 K against the 0.25 K limit (`research/e006/f5_dev_check.json`).
An off-centre source was added to F1's N-layer check, and the refcheck still passes (19 gated checks).

Bottom line (attempt 2): the F1 reference pre-check now passes (`research/e006/refcheck.json`, all_passed = true). Attempt 1
failed only on scikit-fem's own GCI; with triquadratic (Q2) scikit-fem elements it is 0.0046 K (Case 2) and 0.0006 K (uniform
stack), against the 0.01 K threshold, which was not loosened. The registered run still does not fit this Mac (section 7).

Labels used below: **[F]** fact (measured or read from code), **[I]** inference, **[S]** speculation.

## 1. What is measured and how it maps to O006
| metric (spec) | criterion | recompute (evaluator, mfos.metrics) | rows |
|---|---|---|---|
| `max_case_scaled_err` | A1 (<= 0.01), K1 (> 0.05) | `max_scaled_abs_err`, pred `T_l2`, ref `T_ref`, scale `case_scale` | `kind=case, is_finest=true` |
| `max_abs_err_K` | A2 (<= 0.05 K), K2 (> 0.25 K) | `max_abs_err` | same |
| `max_skfem_consistency` | A3 (<= 1) | `max_gci_consistency`, `pred_levels` f_lv0..2, `ref_levels` skfem_lv0..2, `ref_zpair` [skfem_z0, skfem_z1], floor 1e-3 | `kind=crosscheck` |
| `max_conservative_gci_K` | A4 (<= 0.5 K) | `max_gci_capped`, levels f_lv0..2, floor 1e-3 | `is_finest=true` (cases and dies) |

All four are point values written with `level=0.0` and no CI. They are deterministic and nothing is sampled. The runner computes them with
`mfos.metrics.compute` on the same `where` filters. A diverging sequence gives `+inf`, and the runner never catches, clips or replaces it.
F5 is the gated sanity check `skfem_gci_f5`: `gci_capped(skfem_lv0..2, 1e-3) + two_grid_term(z0, z1) <= 0.25 K` on
every die of the five layouts. F3 is the null `constant_k_at_layer_mean` (column `dT_const_k`), which applies to A1 and A2.
The `gci` / `a4_branch` / `p_obs` / `d1` / `d2` columns are informational. They come from `mfos.metrics.gci_capped`, and the
evaluator recomputes the GCIs from f_lv0..2.

## 2. Points, cases, grids
- **Series cases [F]**: Cases 1a, 1b, 2 and 3, and nlayer_dbc are rebuilt from `series_values.json`'s own parameters
  (layers, h, Tf, sources), not from stack.py. A gate checks that the generator's cases equal the JSON. The points are the
  51 frozen rows: per source the centroid, the source mean (`surface_stats` area mean) and the frozen reference maximum location
  (bilinear `surface_temperature` of the reconstructed T_c + q dz/2k). Case scale = the JSON `scale_K`.
- **Manufactured case [F]**: the nine frozen points (die centroid, die mean, die max at the reference maximiser, four
  Cu points, the gap ceramic point and the overhang baseplate point). The scale is the field range, 100.749 K. The geometry is built as a `Layout`, so
  `thermal_layout.build_layout_grid` (the frozen rule) produces the grids. A gate checks that the grid's material map
  equals `MMSCase.region_of` and that the z lines contain the JSON interfaces at every level.
- **Grids [F]**: frozen rule levels 0, 1 and 2 only. `constant_refinement_ratio` checks that every level-(l+1) grid bisects
  every level-l cell. There are no hand-built or tuned L2 grids.
- **Layouts [F]**: dev: `generate_layouts(1, 20261101, family, dies_per_switch)` for side_by_side/6 and u_shaped/2,
  with fingerprints frozen in config (1f66b68a…, 6aaf383a…, identical to the T0150/T0152 benchmarks). Fresh: the first
  layout of each family in `FAMILIES` from the run's sealed seed (`generate_layouts(1, seed, family=f)[0]`; the generator
  returns only DRC-valid layouts; dies per switch as drawn). These give one cross-check row per die, with `layout_set=fresh`, `family`,
  `dies_per_switch`. The dev rows never use the sealed seed. On dev seed 7, the fresh rule drew side_by_side/5,
  interleaved/5 and u_shaped/5 (smoke metadata; not solved).
- **Operating point [F]**: 65 °C coolant, h = 5000 W/(m² K), k(T). Equal power per die is found by proportional updates (p <- p x 60 K / rise; T0196: not a secant) on L2
  level-0 solves until the hottest die rises 60 ± 0.25 K, and the gate allows ±1 K. That power is then used unchanged by both
  solvers on every grid and recorded as `power_w`. Smoke (coarse rule): side_by_side_6 31.20 W, u_shaped_2 45.57 W. The
  registered run recomputes these on the frozen rule.
- **scikit-fem cross-check [F]**: the benchmark rule (h0 = 0.5 mm, near margin 1.5 mm, benchmark nz, `zrefine=False`)
  at levels 0, 1 and 2. `skfem_z0` = the level-1 value, `skfem_z1` = level 1 with every nz doubled (one extra solve per layout).
  `detectable_bias`, `l2_direction` and `skfem_direction` are reported, and `same_side` flags same-side pairs (weak for A3).

## 3. Reference pre-check (`--refcheck`, F1, no L2): result
`research/e006/refcheck.json` holds **all_passed = true** (attempt 2). [F]
| check | value | threshold | pass |
|---|---|---|---|
| reference_sha256 (series befc5efa…, mms ca05847b…) | match | equal | yes |
| series_converged (doubling all knobs on the frozen rows) | <= 1.1e-15 rel | < 1e-7 | yes |
| case3_printed_values (50 terms) | 80.6147 / 78.8712 °C | 80.61 / 78.87 ± 0.005 | yes |
| nlayer_reduces_to_two_layer | 2.2e-16 | 1e-9 | yes |
| mms_numeric_check (all T0153 self-checks, generator sha256, k ratio) | 0.3227 | >= 0.30 | yes |
| skfem_q2_selftest (Q2 point evaluation; exact two-layer 1D solution) | 4.9e-15; 2.5e-11 K | 1e-9; 1e-6 K | yes |
| **case2_skfem_gci** (scikit-fem's own A4 GCI, 12 values) | **0.0046 K** | 0.01 K | yes |
| case2_vs_skfem, max abs error | 0.0011 K | 0.02 K | yes |
| case2_skfem_energy_and_ratio | 1.7e-12, r = 2 | 1e-6 | yes |
| nlayer_uniform_rise_in_band | 84.96 K | 60–110 K | yes |
| **nlayer_uniform_skfem_gci** (3 values) | **0.00058 K** | 0.01 K | yes |
| nlayer_uniform_vs_skfem | 0.00010 K | 0.02 K | yes |
| nlayer_uniform_skfem_energy_and_ratio | 5.0e-12, r = 2 | 1e-6 | yes |
INFO, not gated (same Q2 solver, coarse mesh; CG stopped at 1e-8 because the h = 10 W/(m² K) plates are ill-conditioned,
true residual <= 1e-6 accepted and reported): Case 1a max |err| 0.0084 K (scikit-fem GCI 0.44 K, from a coarse level 0);
Case 1b 0.00009 K (GCI 0.0014 K).

**What changed from attempt 1, and why it now works.**
- **[F]** Attempt 1 used scikit-fem trilinear hexahedra (Q1, the path of `thermal_fem._solve_grid`) on four graded meshes. Its error
  against the series was already 0.003–0.017 K, but its own GCI stayed at 0.0155 K and 0.044 K at the largest meshes that fit
  (1.8 M and 0.74 M DOF, about 6–7 GB; table below).
- **[F]** The A4 estimator caps the order at 1, so for p_obs >= 1 it equals 1.25 |d2| (`mfos.metrics.gci_capped`). The only way to
  lower it is a smaller finest step. More Q1 refinement would need 8x the DOF per level, more than 10 GB.
- **[F]** Attempt 2 keeps scikit-fem and the gate, and raises the polynomial degree: `ElementHex2` (27-node Lagrange hexahedra),
  in `experiments/runners/e006_skfem_q2.py`. It uses the same kind of graded tensor mesh (level l bisects every level-0 cell l
  times, r = 2; z refined too) and chunked assembly. CG is preconditioned with smoothed-aggregation AMG on the diagonally scaled
  matrix, with relative residual 1e-11 (accepted at <= 1e-9). Source means are the exact Galerkin integral of the Q2 field over
  the source faces; point values evaluate the Q2 field at the point.
- **[F]** Self-test, run first in every refcheck: a triquadratic field is evaluated exactly at random points (4.9e-15), and the
  two-layer 1D problem is reproduced to 2.5e-11 K.
- **[F]** Result: at 0.59 M / 0.51 M DOF and 4.8 GB peak, the finest steps are below 0.004 K. On every one of the 15 values,
  GCI >= |T_fe − T_series| (the estimator bounds the known error); GCI/|err| ranges from 4 to over 100.
- **[F] Disclosure (tuning).** For Case 2, one earlier Q2 mesh (s0 1 mm, hmax 4 mm, levels 0–1 only; 0.17 M DOF at level 1,
  max error 0.0017 K) was run to measure memory. At about 5 kB/DOF its level 2 (1.33 M DOF) would need about 7 GB. The
  registered mesh is therefore coarser (s0 2 mm, hmax 5 mm), a change for memory that makes the check harder, not easier. The
  uniform-stack Q2 mesh is the first and only one tried.
- **[I] Interpretation:** F1's purpose is to validate the frozen references with an independent method. The references now
  agree with an independent, self-converged FE solution to 0.0011 K (Case 2) and 0.0001 K (N-layer, uniform stack), 20x and
  200x inside 0.02 K.
- **[I] Scope of F1:** F1 does not verify `thermal_fem`'s Q1 path. That path is the A3 cross-check, and its own convergence is gated by F5
  on the layouts. Attempt 1's Q1 values (errors 0.003–0.011 K at the finest meshes) are consistent with the Q2 values, so the two
  scikit-fem discretisations agree within their errors.

Attempt 1, Q1 meshes (each a full refcheck run; peak RSS at most 6.9 GB; 40–55 s each) [F]:
| attempt (scikit-fem Q1 mesh) | Case 2 max err / GCI | uniform stack max err / GCI |
|---|---|---|
| uniform h0 1 mm, nz 4 / uniform 0.25 mm | 0.0166 / 0.0486 | 0.0045 / 0.0156 |
| graded edges, hmax 2 mm / hmax 1 mm | 0.0045 / 0.0223 | 0.0085 / 0.0316 |
| hmax 1 mm, z_hmax 5 mm / near-zone 0.25 mm | 0.0048 / 0.0216 | 0.0052 / 0.0192 |
| z_hmax 2.5 mm (1.8 M DOF) / near-zone 0.125 mm, die nz 4 | 0.0033 / 0.0155 | 0.0114 / 0.0440 |

The F1 uniform-stack check uses the frozen N-layer stack (layers, h and Tf of nlayer_dbc), laterally uniform, with one centred
5.5 mm die on a 16.5 mm box. The power, 68.8 W, is set from the series alone for an 85 K rise. Scikit-fem solves the symmetric quarter. Reasons [F]:
- The 86 × 56 mm four-source case needs several million DOF to reach a 0.01 K GCI.
- Eccentric sources are covered by Case 2 (the same Field summation), reciprocity and the two-layer reduction. Since
  T0196 they are also covered by a full-domain off-centre N-layer check against scikit-fem (section 8.5).

## 4. Secondary values (smoke dev rows only: coarsened rule, not the frozen rule, not evidence) [F]
GCI / |T_L2 − T_ref| ranges over 2.3–3.6 at every reference point, and no error exceeds its GCI. Per case (max |err|, max GCI,
min GCI/err): 1a 0.414 / 1.218 / 2.94; 1b 0.0064 / 0.027 / 2.92; Case 2 0.436 / 1.055 / 2.34; Case 3 0.036 / 0.102 / 2.86;
N-layer 0.083 / 0.701 / 2.62; manufactured 0.049 / inf / 3.62.
- Oscillatory values: 2 (both manufactured). Divergent values: 1 (manufactured, so A4 = inf on the smoke grid).
- p_obs outside [0.5, 2]: 31 of 76. Mostly p_obs 2.0–4.3 on the corner-free series cases, plus the manufactured die
  centroid, die max and overhang, which are undefined.
- Directions: no same-side pairs among the 16 dev dies.

The registered run reports these columns on the frozen rule, and the note will be updated from its rows.

## 5. F1–F3 coverage
- F1: every item is a gated check before the first L2 solve. These are the sha256 values, series convergence, the Case 3 printed
  values, the two-layer reduction, the Q2 solver's self-test, Case 2 and the uniform stack against scikit-fem Q2 with its own GCI,
  energy balance and constant ratio, and the MMS self-checks with the generator hash and the k ratio. The full run repeats them
  before the first solve (`reference_checks`).
- F2: `constant_refinement_ratio`, `energy_balance` (every L2 and scikit-fem solve, since T0196 including the z-doubled level-1 solve; the MMS also against the
  integrated reference 64.648 W), `picard_converged` (< 1e-4 K, both solvers), and per-row branch, d1, d2 and p_obs, plus the counts.
- F3: `dT_const_k` uses constant k at each layer's volume-mean temperature of the finest k(T) L2 solution, solved on the
  finest grid. It equals T_l2 on the constant-k cases. Dev rows: the null gives A1 0.063 and A2 2.56 K, both failing (manufactured
  shift 2.56 K). `mfos exp check E006 --rows research/e006/dev_rows.json` exits 0.
- **Energy-balance risk from attempt 1, now checked [F]:** the smoke's max energy-balance value is 7.4e-6, from the coarsened
  smoke grid. The manufactured-case gate compares Q_out with the frozen reference's integrated outflow (64.648 W). The
  manufactured source and boundary fluxes depend on position only, so by discrete conservation this gate measures the solver's
  input quadrature, not its temperature accuracy. T0165 attempt 2 therefore checked it blind before registration, on the frozen
  rule (script prints only the balances; no temperature was printed or inspected):
  - |Q_out/Q_ref − 1| = 1.5e-7, 1.8e-9 and 3.1e-11 at levels 0, 1 and 2 (14.6 k, 117 k and 933 k cells; 18 s at level 2);
  - solver balance at most 1.3e-14; Picard max|dT| at most 3.7e-6 K.
  All are within 1e-6, so the frozen-rule run will not be INVALID on this gate. **[I]**
- **Founder amendment (T0173)** is recorded in the spec config. The 30 % rule reads k_max/k_min − 1 >= 0.30 within one layer.
  Measured: 0.3227 in the Al2O3 ceramic, a margin of +0.0227. The k_max-normalised value is 0.244 (reported only).

## 6. Spec fields
- `code_under_test`: thermal_fv.py, thermal_layout.py, stack.py (provenance), thermal_fem.py, e006_series.py, e006_mms.py and
  e006_skfem_q2.py (the F1 scikit-fem Q2 solver, new in attempt 2).
- New config (attempt 2): `skfem_f1_element`, Q2 meshes `skfem_case2` (s0 2 mm, grow 2, hmax 5 mm; top layer z-graded at
  2 mm / 5 mm), `skfem_uniform` (s0 0.25 mm, grow 2, hmax 1 mm, baseplate nz 2, other layers 1), `skfem_case1` (INFO),
  `skfem_max_dofs` 700 000 (Q2 DOF; refused above). New gated checks: `skfem_q2_selftest`, `case2_skfem_energy_and_ratio`,
  `nlayer_uniform_skfem_energy_and_ratio`.
- `code_must_match: []`. O006 depends on no passed objective. O003 will reference this evaluation's hashes.
- `sealed_seed: true`. The full run refuses a missing seed or the dev seed.

## 7. Runtime and memory plan (measured on this Mac) [F]
- FV memory: Case 1a level 1 has 1.45 M cells at 2.13 GB, and the N-layer case level 1 has 2.36 M cells at 2.85 GB. That is about 1.1–1.5 kB per cell at the margin.
- Frozen-rule level-2 cells: 1a 11.6 M, 1b 23.2 M, N-layer 18.9 M, Case 3 1.28 M, Case 2 0.33 M.
- **[I] Projected peaks: about 17, 30 and 21 GB.** No single process fits 10 GB. These cases have no axis mirror symmetry, so the domain cannot be cropped.
  The rule is frozen, so coarser levels are not allowed. Chunked assembly would need a production change.
- **The registered run therefore needs a larger machine:** `scripts/burst_gcp.sh E006 n2-highmem-16` (128 GB; not Spot for a
  registered run). Alternatively the founder can decide on the cases.
- The runner refuses any solve whose estimated memory exceeds 0.85 × physical RAM, so it errors instead of swapping.
- Layout levels 2: about 6.4 GB (L2) and 6.5 GB (scikit-fem) per solve, run one at a time.
- Estimated wall time is 1–2 h on a VM (series and MMS levels about 10 min; 5 layouts × (about 2 min L2 + about 3 min scikit-fem);
  F1 checks about 2 min). The spec sets `timeout_min: 300` and `cpu_hours_est: 3`, against an objective cap of 80 CPU-h.
- Smoke: 60 s and 2.9 GB peak.
- Refcheck (attempt 2, measured): 202 s wall time and 4.93 GB peak RSS, one process. The gated part (self-test, Case 2 and the uniform stack) takes
  about 75 s. The INFO-only Case 1b level 2 takes 110 s (CG on the ill-conditioned 300 mm plate).

## 8. T0196 pre-registration fixes (reviews T0194 and T0195 of T0165)
No gate, threshold, estimator or frozen grid rule was changed. E006 is still a draft.

### 8.1 z-doubled scikit-fem solve gated (T0194, major) [F]
`run_layout` now appends the z-doubled level-1 solve's energy balance and Picard residual to `st.energy` / `st.picard`
(tag `<layout>/skfem/L1z2`), so `energy_balance` and `picard_converged` cover it like every other solve. Its value
`skfem_z1` enters A3's denominator and F5. The spec's two descriptions now name this solve. In smoke, both z-doubled
solves have balance <= 2e-14 and Picard <= 4e-5 K. In the F5 dev check (8.3) the figures are 1.6e-14 and 1.8e-5 K.

### 8.2 calibrate_power pairing (T0194/T0195, minor) [F]
`calibrate_power` returns as soon as a level-0 rise is within 0.25 K of 60 K, and it returns that rise together with
the power it was computed at. If the tolerance is not met in 10 solves it raises a `RuntimeError` (an error result,
never a verdict), so it can no longer return a power whose rise was never computed. `operating_point` and
`calibration_rise_K` therefore describe the power both solvers use. The docstring and section 2 now call the update
proportional (p <- p x 60 / rise), which it is, not a secant. Smoke powers and rises are unchanged (31.204 W / 60.089 K,
45.566 W / 59.950 K), and every smoke metric equals the T0165 dev rows.

### 8.3 Dead code removed (T0195) [F]
Removed `q_ok` in `run_mms`. The manufactured-case balance against the reference outflow was already gated through
`st.energy`, and still is. Also removed the no-op `cfg` rebuild in `smoke()`.

### 8.4 F5 feasibility on development geometry (`research/e006/f5_dev_check.json`) [F]
- **What was run.** `experiments/runners/e006_f5_dev.py` ran on the two development A3 layouts only (dev seed 20261101:
  side_by_side_6 and u_shaped_2, fingerprints asserted), never the sealed seed. It used scikit-fem's frozen E006 rule
  (`skfem_rule`: h0 0.5 mm, near margin 1.5 mm, nz as in config, z held), levels 0-2 plus the z-doubled level-1 solve,
  exactly as `run_layout` builds them. The operating point was O003's: 65 °C coolant, h = 5000 W/(m² K), k(T), and
  equal power from `e006_run.calibrate_power`: 31.842 W per die (side_by_side_6) and 46.168 W (u_shaped_2).
- **Estimate.** For each die, `mfos.metrics.gci_capped(skfem_lv0..2, floor 1e-3 K) + mfos.metrics.two_grid_term(lv1, z1)`.
- **Blindness.** No L2 Tj value, no L2-vs-scikit-fem difference and no A3/A4 value was computed, printed or written.
  The only L2 computation was the level-0 calibration inside `calibrate_power`, which is how scope_in defines the
  operating point. The child process keeps the power and discards the rise.
- **Result.** Maximum estimate **0.2001 K**, at u_shaped_2 die 3 (GCI 0.1414 K + z term 0.0587 K), against the
  **0.25 K** limit: met, margin 0.050 K.
  - Maximum GCI 0.141 K and maximum z term 0.059 K.
  - side_by_side_6 dies: 0.088-0.132 K. u_shaped_2 dies: 0.148-0.200 K.
  - All 16 sequences are in the monotone branch, with p_obs between 0.75 and 1.73.
  - F2 on these 10 solves: energy balance <= 1.2e-13, Picard <= 2.3e-5 K.
- **Agreement with T0195's projection [I].** T0195 projected about 0.2 K by rescaling the 85 K benchmark to 60 K. The
  measured value agrees.
- **Memory [F].** Each solve ran in its own subprocess, one at a time. The level-2 peaks were 7.46 GB (side_by_side_6,
  1.48 M DOF) and 6.10 GB (u_shaped_2). The z-doubled solves peaked at 5.83 GB (0.72 M DOF) and 3.97 GB. Wall time was
  about 4 min in total. Before every solve estimated above 5 GB, the script checked that memory_pressure showed >= 50 %
  free (it showed 70-74 %) and that the swap files totalled < 4 GB (they totalled 0 GB).
  - The side_by_side_6 level-2 peak is 0.46 GB above the packet's "about 7 GB". It stayed inside the agent rule's 10 GB
    single-process allowance, whose preconditions were met.
  - `sysctl vm.swapusage` is blocked by the sandbox. The total size of `/private/var/vm/swapfile*` was used instead; it
    bounds the swap in use from above.
- **What this does not show [I/S].**
  - The three fresh sealed-seed layouts are unmeasured. On dev seed 7 the fresh rule drew 5 dies per switch. With a 20 %
    margin on the development layouts, F5 could still fail on a fresh layout [S]. That would make the registered run
    INVALID, never a verdict on the L2.
  - u_shaped_2 is the binding layout, with a 2-dies-per-switch geometry. Its die GCIs are about twice those of
    side_by_side_6.

### 8.5 Off-centre source in F1's N-layer check (T0194, minor) [F]
- **Case.** The frozen N-layer stack (nlayer_dbc layers, h and Tf), laterally uniform, on a 12 x 10 mm box. One
  5 x 4 mm source is centred at (4.0, 3.5) mm, off-centre in both x and y and with a != b and c != d. scikit-fem Q2
  solves the full domain, with no symmetry used.
- **Reported points (5).** The centroid, the source mean, the source maximum, and the centroid's mirror images about
  x = a/2 and y = b/2.
- **Power.** 35.9 W, set from the series alone for an 85 K maximum rise. The measured rise is 85.08 K.
- **Odd modes carry the answer.** The series' odd-mode signal at the centroid, [T(x,y) - T(a-x,y)]/2, is +9.30 K in x
  and +7.66 K in y. It is identically zero for the centred source of the uniform check. An odd-mode error larger than
  about 0.2 % of that signal would therefore exceed the 0.02 K agreement limit [I].
- **Mesh.** It was fixed before any solve, by DOF count alone: the uniform check's family (grow 2) with s0 and hmax
  doubled (0.5 mm / 2 mm). That is the finest member that keeps level 2 at the passing uniform check's 514 865 Q2 DOF.
  s0 0.25 mm / hmax 1 mm would need 1.22 M DOF, above `skfem_max_dofs` (700 000). It is the first and only mesh tried.
- **Results (refcheck, gated).**
  - `nlayer_offcentre_rise_in_band`: 85.08 K.
  - `nlayer_offcentre_series_converged`: doubling every series knob changed nothing (0.0). As T0194 noted for the frozen
    cases, this gate on its own is weak. The independent check is scikit-fem.
  - `nlayer_offcentre_skfem_gci`: **0.0081 K** (<= 0.01 K). This is the smallest margin of the F1 scikit-fem checks
    and is set by the maximum point.
  - `nlayer_offcentre_vs_skfem`: **0.00035 K** (<= 0.02 K).
  - `nlayer_offcentre_skfem_energy_and_ratio`: 1.2e-12, r = 2.
- **Bound check.** GCI >= |err| holds on 4 of the 5 values. The exception is the x-mirror point: both of its steps are
  below the 1e-3 K floor, so its GCI is 0, and its error is 1e-5 K. This is an artefact of the floor and is not gated.
- **Cost.** Peak RSS 4.81 GB. The refcheck took 198 s and its 19 gated checks all pass.
- **Interpretation [I].** The N-layer kernel's eccentric and odd-mode terms now agree with an independent full-domain
  FE solution to 3.5e-4 K. Before this, two reviewers' own series codes were the only direct confirmation.

### 8.6 Commands run in T0196 (exit codes)
- `e006_f5_dev.py`: 0.
- `--refcheck`: 0.
- `--smoke --rows-out research/e006/dev_rows.json`: 0.
- `mfos exp check E006 --rows research/e006/dev_rows.json`: 0.
- `ruff check .`: 0.
- Both JSON assertions of the DoD: 0.
- `mfos gate --fast`: 0.
