# O002 L1 thermal: design study of fast models against the level-1 reference (T0392)

Scientist, 2026-11-15. Research note on development geometry: design input for n4 and E007, **not evidence**.
Code `research/o002_l1/design_study.py`; numbers `research/o002_l1/design_study.json`; per-solve reference summaries
`research/o002_l1/cache/*.json` (no fields, reusable by n4); run log `research/o002_l1/run.log`.

## 1. Answer
- **Chosen: `fv_coarse_xcal`.** It is a coarse cell-centred finite-volume solve of the full layout problem, using the
  in-house FV solver (not the reference code). Its die-local rise is scaled by one factor per die size, calibrated
  against the reference. **meets_targets = true**:
  - median 0.315 s per evaluation (range 0.18-0.47 s);
  - A1-type 0.189 K at P_ref and 0.088 K at half P_ref (target 0.3 K);
  - A2-type 1.02 % and 1.01 % (target 1.8 %).
- **It misses the 0.6 x target on A4 (spreads).** The pooled A4-type ratio is 0.37 at P_ref (0.6 x 0.5 = 0.3 would be
  the matching target; the packet's meets_targets rule does not include A4). In the 2-die stratum the ratio is 0.81,
  above A4's own 0.5. **A4 is the criterion most likely to decide E007**; see risks.
- **f2_warning = false.** Both nulls fail A1 by 6x at P_ref: stratum mean 2.96 K, die position 3.03 K.
- **F4 preview.** Holding k at 300 K pushes the chosen model past A1 (0.55 K) and A2 (10 %) at P_ref, so k(T) is tested
  at this operating point.
- **F6 early flag.** The hottest node minus the die average of the reference reaches 4.2 K (side_by_side/6) and 5.6 K
  (u_shaped/2) at P_ref, beyond F6's 2 K founder-decision line. The hottest node is not converged at level 1 (D0020), so
  this is indicative only.

## 2. Design (facts)
**Layouts.** Two strata, one per die-count band. Each stratum holds C004's development layout (E009 dev seed 20261101)
plus the first 5 DRC-valid layouts of the recorded development seed **20261115** whose die size equals the dev layout's
(rejection on the generator's s, 40 draws per stratum):
- u_shaped/2 (2-3 band), 6 layouts;
- side_by_side/6 (4-6 band), 6 layouts.

Die size is 5.0 mm in both strata. That gives 12 layouts, 96 dies, 24 switches and 30 same-stratum pairs per load.
The dev fingerprints were asserted equal to E009's. Fingerprints and stream indices are in the JSON.

**Operating point.** T_c = 338.15 K, h = 5000 W/(m² K), k(T), equal uniform power per die.
- P_ref = 47.141886 W/die (u_shaped/2) and 32.232107 W/die (side_by_side/6). These are C004's calibration values (E009
  config.dev_regression_guard).
- Re-checked here at level 0: hottest-node rise 59.945 K and 60.160 K. Both are within 60 ± 0.25 K.
- Second load 0.5 P_ref.

**Reference.**
- Solver: `thermal_fem.solve_layout`, level 1, frozen GridRule built key for key from research/o007_dev3/frozen_config.json.
  The script asserts that this file equals E009 config.fem_rule.
- Code identity: thermal_fem.py sha256 a216d5fe3209bcee…, unchanged.
- 24 judged solves plus 2 calibration checks, one at a time.
  - Energy balance at most 4.3e-13 on every solve.
  - Peak RSS at most 4.1 GB.
  - 3164 CPU-s in total (0.88 CPU-h, budget 3).
- Mean baseplate-bottom temperature: the Q1 integral of the nodal field over z = 0 equals T_c + P_tot/(h A_bottom) to
  6.8e-12 K on every solve. So the die-local rise uses the analytic value.
- Independent check: my level-1 solve of side_by_side_6 at P_ref matches E009's cached level-1 values
  (research/o007_dev3/cache) to 8e-7 K, with the same DOF count.

**Statistics.** Point estimates (numpy linear p95), pooled over strata, as defined in the script docstring:
- A1-type uses the die the reference ranks hottest, with self-pairs excluded.
- A2-type divides by the die-local rise.
- A3-type is the per-switch spread of die averages.
- A4-type divides by the stratum-mean-spread null, per (stratum, switch), leave-one-layout-out.

The bracketed intervals below are a layout-clustered percentile bootstrap (B = 1000, within strata). They are
indicative only: this bootstrap under-covers a p95 bound (T0369), and with 6 layouts per stratum nothing here resolves
a p95 bound.

**Choice rule.** Written in the script before any candidate was scored against the reference: lowest
max over loads of max(a1/0.3, a2/0.018, a3/0.6, a4/0.3, t/1 s).

## 3. Candidates (facts; P_ref / half P_ref; median s per evaluation on one thread, 3 repeats after a warm-up)
| candidate | family | t [s] | A1-type p95 [K] | A2-type p95 | A3-type p95 [K] | A4-type ratio |
|---|---|---|---|---|---|---|
| fv_coarse | (a) coarse FV, no calibration | 0.315 | 0.206 / 0.096 | 3.59 % / 3.55 % | 0.217 / 0.101 | 0.53 / 0.52 |
| fv_coarse_boxcal | (a) + analytic box-stack factor | 0.315 | 0.201 / 0.096 | 2.61 % / 2.57 % | 0.164 / 0.076 | 0.40 / 0.40 |
| **fv_coarse_xcal** | (a) + factor from the other stratum's dev layout | 0.315 | **0.189 / 0.088** [0.11, 0.22] | **1.02 % / 1.01 %** [0.78, 1.05] | 0.150 / 0.070 | **0.37 / 0.36** [0.26, 0.55] |
| fem_coarse | (a) coarse thermal_fem GridRule | 1.133 | 0.226 / 0.104 | 3.23 % / 3.17 % | 0.334 / 0.159 | 0.81 / 0.82 |
| fem_coarse_xcal | as above + xcal factor | 1.133 | 0.215 / 0.098 | 1.80 % / 1.79 % | 0.347 / 0.165 | 0.84 / 0.85 |
| series_superposition | (b) per-housing Fourier superposition, k(T) passes | 0.037 | 1.389 / 0.637 | 6.56 % / 5.86 % | 1.089 / 0.425 | 2.65 / 2.20 |

Bracketed intervals are for P_ref. A4 per stratum at P_ref for fv_coarse_xcal: side_by_side/6 0.26, u_shaped/2 0.81.
A1 per stratum: 0.18 and 0.20 K.

Precomputation, reported separately:
- series mode factors: 0.2 ms per housing;
- box-stack calibration for fv_coarse_boxcal: 0.13 s per die size;
- xcal factor: one level-1 reference solve per calibration layout.

Model size: FV 36-82 k cells; coarse FEM 13-27 k DOF. Energy balance of every candidate solve is at most 4e-14.

Nulls, on the same reference values:

| null | load | A1-type [K] | A2-type | A3-type [K] | A4-type |
|---|---|---|---|---|---|
| stratum_mean | P_ref / half | 2.96 / 1.40 | 24.1 % / 24.0 % | 0.411 / 0.193 | 1 (definition) |
| die_position | P_ref / half | 3.03 / 1.45 | 4.6 % / 4.6 % | 0.411 / 0.193 | 1.00 / 1.00 |

**Why die_position's A4 is exactly 1 (checked, not a bug).** In every layout of both strata the hottest and coldest die
of each switch have the same die index: HS and LS argmax index 3 and argmin 0 in side_by_side/6; argmax 0 and argmin 1
in u_shaped/2. Then the max of the leave-one-out means equals the mean of the maxima, so its spread prediction is the
stratum-mean spread.

The die-position A2 is 3.6-3.7 % in u_shaped/2. That is close to A2's 3 %, as review T0372 expected for 2-die strata.

**What the candidates show (inference).**
1. **The coarse FV has one common-mode bias.** It over-predicts every die-local rise by about 2.6 %. The
   layout-dependent part is small: A1 is about 0.2 K, against a hottest-die SD of 1.0-1.1 K across layouts.
   - The calibration factor fitted on u_shaped/2 is 0.97387. The one fitted on side_by_side/6 is 0.97406. They agree to
     2e-4 across two families and 2 against 6 dies per switch.
   - That agreement is what lets an out-of-stratum calibration cut A2 from 3.6 % to 1.0 % without touching A1.
2. **The analytic box-stack factor is not enough.** It gives c = 0.9906, which removes only about a third of the bias.
   The box stack (every layer laterally uniform) has no die-attach-on-copper wedge at the die edge. That wedge is where
   the layout error sits (docs/thermal_model.md section 8: λ = 0.83 singularity). So that bias is a layout-mode
   discretisation error, not a stack error.
3. **The coarse FEM is slower and its bias depends on the stratum.**
   - Its factor differs between strata: 1.030 against 1.015.
   - Its spread error is twice the FV's, because Q1 under-resolves the edge singularity at h0 = 16 mm.
   - Its median time exceeds 1 s in this run. It was 0.85 s in the smoke run, so it is sensitive to machine load.
4. **The series superposition is fast but misses patterning.** It ignores the top-Cu patterning, the extent of the
   ceramic and backside Cu, and the overhang geometry. Its 1.4 K pair error is the cost of that.
   - It is not viable as the score.
   - It might serve as a pre-screen. Untested.
5. **k(T) is reproduced.** The median ratio of the rise at P_ref to the rise at half P_ref is 2.037 for the reference,
   the FV and the FEM alike. The super-linearity from k(T) is the same.

## 4. Method of the chosen candidate (for n4)
1. **Grid and geometry.** Cell-centred FV on a tensor grid that conforms to every layout line.
   - Regions and boundary conditions exactly as docs/thermal_model.md sections 2-4: patterned top Cu, die attach and die
     per die, backside inset, baseplate overhang, uniform h at the bottom, adiabatic elsewhere.
   - Face conductances by harmonic means (Patankar, *Numerical Heat Transfer and Fluid Flow*, 1980, ch. 4).
   - The prototype uses `solvers.thermal_fv.solve_steady` through `thermal_layout.solve_layout_level` with these
     level-0 constants: H0_MAX 4 mm, LAT_FRAC 16, EDGE_FRAC 2 (first edge cell 2 x the thinnest layer, growth 1.5),
     Z_CELLS 2.
   - The prototype sets these by temporarily patching module constants. **n4 must pass them as explicit grid
     parameters (no global state).**
2. **k(T).** Picard iteration (lagged k) with the cited `Layer.k_at` laws, to 1e-2 K (about 4 iterations).
   - Kirchhoff transform is not used. It linearises the problem exactly only for a single material with one k(T) law
     (Carslaw & Jaeger, *Conduction of Heat in Solids*, 2nd ed., 1959, sec. 1.7). Here seven materials have different
     laws.
3. **Die averages.** Area means of the reconstructed die-top surface field, as thermal_fv defines them. `tj_max` is the
   coarse surface maximum: reported, never gated.
4. **Calibration.** T_L1,i = T_bp + c(s) (T_FV,i − T_bp), with T_bp = T_c + ΣP/(h A_bottom) (exact by the energy
   balance) and s the die size.
   - c(s) is a frozen table with one entry per generator die size (4.0, 4.5, 5.0, 5.5 mm).
   - Each entry is the mean of (ref rise)/(FV rise) over the dies of development layouts only, at the level-1 reference
     and C004's P_ref, at least two layouts of different families per size.
   - Measured here: c(5.0 mm) = 0.9740 ± 0.0001.
   - The table must be frozen before E007's registration (F5). It is applied unchanged at every load and with
     constant_k.

**API** (`moduleforge.thermal`):
`evaluate(layout, power_W, *, h, T_c, constant_k=False) -> L1Result`.
- `power_W` is a scalar or one value per die in `layout.dies` order.
- `L1Result` fields:
  - `tj_mean` (K, absolute, `layout.dies` order);
  - `tj_max` (K, coarse, report only);
  - `T_bp`;
  - `die_local_rise`;
  - `energy_balance`;
  - `picard_iters`;
  - `n_cells`;
  - `wall_s`;
  - `calibration` (die size, c, table version).
- `evaluate` raises if the die size is not in the table, or if the layout has more than one die size.

**constant_k (F4).** It holds every layer at `Layer.k` = `k_at(T_REF = 300 K)`. That is the same convention as the
`constant_k` of both reference solvers, so the ablation can be cross-checked against a constant-k reference solve.
- Preview on these rows: A1-type 0.55 / 0.21 K, A2-type 10.0 % / 7.7 %, A4-type 2.1 / 1.5 at P_ref / half P_ref.
- Holding k at the coolant temperature (338 K) instead would shrink the ablation and make F4 harder to trigger. Untested.

## 5. Why it should hold on unseen strata (inference, with what would refute it)
- **No physics approximation.** The model solves the same continuum problem as the reference, with every layout
  feature, so its error is pure discretisation error.
- **The bias is local and common-mode.** The dominant part comes from the die edge and the thin layers, which are the
  same for every die of a given size on this stack. That is why the factor transfers across family and die count
  (2e-4 here).
- **The layout-dependent residual is small and resolved by construction.** It comes from trace edges near dies, which
  the conforming grid resolves at every stratum. At 0.15-0.2 K, it sits well under the 1.0-1.1 K layout-to-layout SD it
  must track.
- **The model shares no code with the reference** (FV against scikit-fem). Agreement is therefore not common-mode code
  error.
- **What would refute this:**
  - c(s) varying by more than about 0.005 between families at one die size (0.5 % of A2), or between interleaved and the
    other families;
  - layout-dependent error growing with die count 3-5, which is untested;
  - A1 of n4's frozen model above 0.3 K on a fresh development seed.

## 6. Risks
1. **A4 is the binding criterion (high).** The stratum-mean-spread null is weak in absolute terms: its p95 is 0.41 K
   pooled and 0.20 K in u_shaped/2 at P_ref. So A4 ≤ 0.5 needs an L1 spread error of about 0.2 K pooled and 0.1 K in
   2-die strata.
   - fv_coarse_xcal reaches 0.15 K pooled. In u_shaped/2 it gets 0.16 K, a ratio of 0.81.
   - The indicative pooled upper bound is 0.55.
   - The reference's own level-1-to-level-2 spread steps are up to about 0.05 K (E010), which is not negligible against
     a 0.2 K denominator.
   - n4 should try a finer lateral rule near dies, still well under 1 s. The probe gave EDGE_FRAC 1 at 0.24-0.56 s; its
     effect on spreads was not measured. Any such trial must run on a new development seed, not these rows.
2. **Die-size dependence of c (medium).** Only 5.0 mm was tested. The table needs all four sizes, with a
   cross-family check at each.
3. **Calibration uses reference data (medium).** This is legitimate if done on development seeds only and frozen before
   E007. A reviewer may prefer a physics-only correction, but the box-stack factor is not adequate (section 3, item 2).
4. **Narrow sample (medium).** This study had 2 of the 6 (family, band) cells, no interleaved family, no 3-5-die
   strata, and 6 layouts per stratum.
   - Both strata drew new layouts at the same stream indices (0, 1, 10, 13, 14 of seed 20261115). generate_layouts with
     a single (family, dies) combination consumes the stream identically, so the two strata share parameter draws
     (common random numbers).
   - E007 should use a distinct seed per stratum.
5. **Speed headroom (low).** The median is 0.32 s and the maximum 0.47 s on 12-die layouts. The coarse FEM's time
   varied by 30 % between runs with machine load.
6. **F6 (founder).** The hottest-node minus die-average gap is 4-6 K at P_ref on the reference. That is outside L1's
   scope, but it triggers F6's founder decision if E007 confirms it.

## 7. Facts, inferences and speculation
- **Facts:** every number in sections 2-3 and the F4 and F6 values, from design_study.json and the cache.
- **Inferences:** the causes of the bias (die-edge wedge, z resolution), the transfer to unseen strata, and the A4 risk.
- **Speculation:** a finer edge rule would close the A4 gap; the coolant-temperature constant_k would weaken F4.
