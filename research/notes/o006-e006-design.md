# O006 / E006 design: thermal L2 against frozen references and scikit-fem (T0165)
Date: 2026-11-02 · Task: T0165 · Status: draft spec `experiments/drafts/E006.yaml`, runner `experiments/runners/e006_run.py`.
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
- **Operating point [F]**: 65 °C coolant, h = 5000 W/(m² K), k(T). Equal power per die is found by secant on L2
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
- Eccentric sources are covered by Case 2 (the same Field summation), reciprocity and the two-layer reduction.

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
- F2: `constant_refinement_ratio`, `energy_balance` (every L2 and scikit-fem solve; the MMS also against the
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
