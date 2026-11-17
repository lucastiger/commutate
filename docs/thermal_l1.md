# L1 thermal model (`moduleforge.thermal`)

Status: built by T0395 (2026-11-16) from the design chosen in `research/notes/o002-l1-design.md` (T0392, `fv_coarse_xcal`),
with one change to the grid rule's lateral cap (section 5). After this task merges the package is frozen as E007's code under
test (F5). Every number below is on **development** layouts: design checks, not evidence.

## 1. Method
`evaluate(layout, power_W, *, h, T_c, constant_k=False) -> L1Result`

1. **Coarse conforming finite-volume solve of the full layout problem.** Regions and boundary conditions follow
   `docs/thermal_model.md` sections 2-4:
   - patterned top Cu, then die attach and die per die;
   - backside inset and baseplate overhang;
   - uniform `h` at the baseplate bottom, adiabatic elsewhere;
   - uniform flux over each die's top face.

   The grid is level 0 of `solvers.thermal_layout.build_layout_grid`, built with the explicit constants `GRID_RULE` (no
   global state):
   - lateral bulk cap `h0_max` **1.5 mm** (n1 used 4 mm);
   - `lat_frac` 16;
   - `edge_frac` 2: the first edge cell is 2 x the thinnest layer, growth 1.5;
   - `z_cells` 2.

   `solvers.thermal_fv.solve_steady` solves the system. Face conductances are the series of the two half-cells, a harmonic
   mean (Patankar, *Numerical Heat Transfer and Fluid Flow*, 1980, sec. 4.2.3, eq. 4.9). This is exact for 1D piecewise-
   constant k (composite wall, Incropera et al., *Fundamentals of Heat and Mass Transfer*, sec. 3.1.3).
   `solvers/thermal_fem.py`, the reference, is neither used nor modified, so L1 and the reference share no code.
2. **k(T).** Every layer takes k(T) from `geometry.stack` (`Layer.k_at`, `K_LAWS`). The temperature dependence is handled
   by lagged-k Picard iteration to 1e-2 K, about 4 iterations.
   - A Kirchhoff transform is not used. It is exact only for a single material with one law (Carslaw & Jaeger, *Conduction
     of Heat in Solids*, 2nd ed., 1959, sec. 1.7), and the stack has seven materials.
3. **Die averages.**
   - `tj_mean` is the area mean of the reconstructed die-top surface field (`thermal_fv` `surface_stats`).
   - `tj_max` is the coarse surface maximum. It is uncalibrated and reported only (F6).
4. **Calibration.**

       T_L1,i = T_bp + c(s) (T_FV,i - T_bp),   T_bp = T_c + sum(P) / (h A_bottom)

   - `T_bp` is the exact mean baseplate-bottom temperature. With uniform `h` all heat leaves through the bottom face, so
     the global energy balance fixes it.
   - `c(s)` is the frozen table `CALIBRATION`, one entry per generator die size (section 2).
   - It is applied unchanged at every load and with `constant_k`.
5. **`constant_k=True`** holds every layer at `Layer.k` (k at 300 K). This is the convention of both reference solvers
   (the F4 ablation).

**`L1Result` fields:**
- `tj_mean`: K, absolute, in `layout.dies` order;
- `tj_max`;
- `wall_s`;
- `meta`: method, grid rule, `tj_mean_fv` (the uncalibrated die means of the same solve);
- `T_bp`;
- `die_local_rise`;
- `energy_balance`;
- `picard_iters`;
- `n_cells`;
- `calibration`: die size, c, table version.

`power_W` is a scalar or one value per die. `evaluate(..., calibrate=False)` returns the raw coarse-FV values; it exists
for the table's derivation. `raw_fv(..., grid_rule=...)` is the same solve on another rule, for design checks only.
`evaluate` raises `ValueError` in three cases:
- the die size is not in the table;
- dies of different sizes are mixed;
- a die is not square.

## 2. Calibration table c(s) (`o002-l1-cal-v2`)
Derivation: `benchmarks/thermal_l1_calibration.py`. Per-solve reference summaries are in
`tests/regression/data/o002_l1_cal/`; the 5.0 mm entries come from T0392's cache in `o002_l1_dev/`.
`tests/regression/test_thermal_l1_dev.py` re-derives the table to 5e-6.

**Inputs per size.** For each generator die size s:
- **Layouts:** C004's two development strata (`side_by_side/6`, `u_shaped/2`), taking the first layout of E009's
  development seed 20261101 with `die_size_mm = s`. At 5.0 mm these are E009's development layouts themselves
  (fingerprints asserted).
- **P_ref:** C004's rule, as E009's `calibrate_power`. Level-0 reference solves start at 30 W with the update
  p ← 60 p / rise, until the hottest die rises 60 ± 0.25 K above the coolant.
- **Reference:** `thermal_fem.solve_layout` with the frozen E009 rule at level 1, at that P_ref.
  - Energy balance is at most 2.85e-13 over all cached solves.
  - Peak RSS is 4.2 GB; solves ran one at a time.
- **c(s):** the mean over the two layouts of the per-layout mean over dies of (reference rise) / (coarse-FV rise).

| s [mm] | P_ref side_by_side/6, u_shaped/2 [W/die] | c side_by_side/6 | c u_shaped/2 | **c(s)** | family spread | n1's 4 mm rule: c (spread) |
|---|---|---|---|---|---|---|
| 4.0 | 26.43, 38.75 | 0.98839 | 0.98250 | **0.98544** | 0.0059 | 0.97506 (0.0032) |
| 4.5 | 29.29, 42.89 | 0.98451 | 0.98118 | **0.98284** | 0.0033 | 0.97292 (0.0022) |
| 5.0 | 32.23, 47.14 (E009) | 0.98378 | 0.98218 | **0.98298** | 0.0016 | 0.97396 (0.0002) |
| 5.5 | 35.05, 51.42 | 0.98559 | 0.98244 | **0.98402** | 0.0032 | 0.97577 (0.0012) |

(The P_ref values for 4.0, 4.5 and 5.5 mm are in the `__Pref.json` files.)

**Transfer check (design note section 5).** The note says c(s) varying by more than about 0.005 between families at one
size would refute the transfer of the factor.
- n1's 4 mm rule meets this at every size (max 0.0032).
- The adopted 1.5 mm rule exceeds it at 4.0 mm (0.0059). At 4.5 and 5.5 mm it is at 0.0033 and 0.0032; at 5.0 mm,
  0.0016.
- With the finer rule, the coarse bias is smaller (about 1.7 % rather than 2.7 %) but slightly more family-dependent. In every
  size, side_by_side/6 has the larger c.

**Effect (inference).** Using the mean c, each family is off by at most half the spread: 0.3 % of the die-local rise, or
about 0.1 K at P_ref. That is a tenth of A2's 3 % budget. A stratum-constant factor error cancels in A1's same-stratum pair
differences and scales spreads by 0.3 %. This is a flagged deviation from the note's line, not a hidden one.

## 3. Limits
- **Scope.** Generator die sizes 4.0-5.5 mm on the 0.5 mm grid, one square size per layout, on the default DBC stack. Out
  of scope as for O002: steady state only, uniform `h`, no bond-wire heat paths, voids, TIM or electro-thermal coupling.
- **Calibration coverage.** Two families (side_by_side, u_shaped) at 2 and 6 dies per size. The interleaved family is
  covered only through the 5.0 mm validation rows (section 5), and 3-5-die strata are not covered at all.
- **Common-mode bias.** The coarse rule over-predicts the die-local rise by about 1.7 %; c removes it. The die-edge corner
  (attach meets Cu, singular exponent about 0.83, `thermal_model.md` section 8) is resolved only to the coarse rule's
  accuracy.
- **`tj_max`.** It is not converged on this grid and is not calibrated.
- **Speed.** The time grows with die count and layout complexity: 12-die layouts take 0.45-0.79 s per evaluation on this
  Mac, and machine load moves the median by about 15 %.

## 4. Tests and checks
**`tests/unit/thermal/test_l1.py`**
- 1D series limit `T_c + P (sum t_i/(k_i A) + 1/(h A))`: exact for the FV, rel 1e-6.
- Single-source N-layer Fourier series of `solvers.thermal_series` (Carslaw & Jaeger sec. 3.6) on a thin die, so that the
  FV and the series solve the same problem.
  - Coarse rule within 0.7 % (measured +0.34 %).
  - Fine rule within 0.2 % (measured −0.05 %), a convergence check.
- 1D Kirchhoff limit with k(T): all seven layers on their `K_LAWS`, against the exact per-layer integral of k dT = q t
  (brentq) at 20, 40 and 60 W, h = 5e4; coarse rule within 5e-4 of the rise (measured 1.6e-5 to 2.4e-4), fine rule 5e-5.
- `GRID_RULE` and `CALIBRATION` are pinned together: a grid-rule change needs a refit of c(s).
- Linearity in power at constant k: 1e-9.
- k(T):
  - every `K_LAWS` law falls above 300 K;
  - the rise is super-linear in power;
  - constant k at 300 K under-predicts.
- Mirror symmetry: 1e-3 K.
- Energy balance and exact `T_bp`.
- Calibration relation within one solve (1e-12) and across solves (1e-9 K, the solver's run-to-run difference).
- Determinism: 1e-9 K.
- Every generator die size evaluates. Unsupported or mixed sizes raise.

**`tests/regression/test_thermal_l1_dev.py`**
- The 12 T0392 development rows: A1-type p95 ≤ 0.3 K and A2-type p95 ≤ 0.018 at P_ref and 0.5 P_ref (0.6 x the A1/A2
  thresholds; never widened). A4-type per band is printed and sanity-bounded.
- c(s) is re-derived from the cached references.
- The fresh-seed 2-die rows of section 5: A1 ≤ 0.3 K, A2 ≤ 0.018, pooled A4-type ≤ 0.3. This is a regression guard, since
  these rows chose the rule.

**`benchmarks/thermal_l1_speed.py --check`** measures the median wall time per evaluation on one thread over the 12
development rows at both loads, against a 1.0 s limit (A5). Measured on this Mac:
- median 0.41-0.48 s (machine load moves it);
- maximum about 0.79 s under load (T0423/T0424).

## 5. Spread criterion (A4) per die-count band, and the founder's question
The founder asked (T0395 packet): does a finer coarse grid or a per-switch correction improve the 2-die stratum within
A5's 1 s?

**Statistics.**
- These are the design study's point estimates (numpy linear p95).
- A4-type = p95 of the per-(layout, switch) spread error / p95 of the leave-one-layout-out stratum-mean-spread null.
- Each stratum has 6 layouts, so 12 switch spreads, and a p95 over 12 values is close to their maximum. These numbers
  resolve no p95 bound (T0369).

**Development rows (T0392's 12 layouts, P_ref / 0.5 P_ref).**

| rule | A1-type [K] | A2-type | A3-type [K] | A4 2-3-die band (u_shaped/2) | A4 4-6-die band (side_by_side/6) | A4 pooled |
|---|---|---|---|---|---|---|
| n1, `h0_max` 4 mm | 0.189 / 0.088 | 1.02 % / 1.02 % | 0.151 / 0.070 | **0.81** / 0.81 | 0.26 / 0.28 | 0.37 / 0.36 |
| **adopted, 1.5 mm** | 0.200 / 0.093 | 0.67 % / 0.64 % | 0.099 / 0.050 | **0.23** / 0.23 | 0.23 / 0.24 | 0.24 / 0.26 |
| 1 mm | 0.139 / 0.064 | 0.55 % / 0.55 % | 0.100 / 0.051 | 0.25 / 0.24 | 0.23 / 0.24 | 0.24 / 0.26 |

**Fresh development seed.** Design note risk 1 forbids judging the change on the rows that suggested it, so the trial used
a new seed.
- **Seed:** 20261395, recorded; it is not a sealed seed.
- **Strata:** all three families at 2 dies per switch and 5.0 mm dies, 6 layouts each (18 layouts).
- **P_ref:** C004's rule on each stratum's first layout: 47.60, 51.01 and 47.79 W/die for side_by_side, interleaved and
  u_shaped.
- **Reference:** level 1 at P_ref.
- **Decision rule,** written in the script before any variant was scored on these rows:
  - adopt the variant with the lowest pooled 2-die A4-type;
  - the variant must beat n1's rule;
  - it must keep A1 ≤ 0.3 K and A2 ≤ 1.8 % on these and the development rows;
  - its median must be ≤ 0.6 s.

Fresh-seed results at P_ref. Times are the median and maximum per evaluation over the development rows, one thread; they
vary by about 15 % with machine load.

| rule | A1-type [K] | A2-type | A3-type [K] | A4 side_by_side/2 | A4 interleaved/2 | A4 u_shaped/2 | **A4 pooled** | time [s] |
|---|---|---|---|---|---|---|---|---|
| n1, 4 mm | 0.187 | 0.73 % | 0.189 | 0.77 | 0.14 | 0.51 | **0.69** | 0.32-0.38 / 0.49-0.59 |
| **1.5 mm** | 0.183 | 0.61 % | 0.058 | 0.25 | 0.19 | 0.29 | **0.21** | 0.39-0.41 / 0.55-0.62 |
| 1 mm | 0.107 | 0.52 % | 0.059 | 0.25 | 0.17 | 0.22 | **0.22** | 0.47-0.53 / 0.62-0.78 |
| n1 + per-switch correction | 0.187 | 0.73 % | 0.196 | 0.80 | 0.13 | 0.53 | 0.72 | as n1 |

The per-switch correction scales each switch's predicted spread by d = 1.009, a least-squares fit of the reference spread
against the model spread on the development rows.

**Answer.**
- **A finer coarse grid does improve the 2-die stratum, well within A5.**
  - The pooled fresh-seed 2-die A4-type ratio falls from 0.69 to 0.21.
  - On the development rows, u_shaped/2 falls from 0.81 to 0.23.
  - The median is about 0.4 s against the 1 s limit.
- **A per-switch correction does not help.**
  - The coarse model's spreads are not biased in scale (d = 1.009); its spread error is layout-specific.
  - Applying d makes A4 slightly worse in every stratum and for every rule.
- **Adopted:** `h0_max` 1.5 mm. The decision rule picked it over 1 mm (0.21 against 0.22, a difference well inside the
  noise of 12-value p95s). The 1 mm rule has the better A1 and A2, but it is slower.

**Inferred cause.** The 4 mm bulk cells are coarser than a die (4-5.5 mm) and than the trace gaps beside it. The
layout-specific heat spreading between paralleled dies of one switch, which sets their spread, lies at that scale. Edge
grading and z cells do not reach it (attempt 1's exploratory table: `edge_frac` 1 and `z_cells` 3 left u_shaped/2 at
0.76-0.81).

**Caveats.**
- The fresh-seed rows chose the rule, so they are no longer out of sample.
- Only 2-die strata at 5.0 mm were validated. The 3-5-die strata and the other die sizes have no A4 check.
- The adopted rule's c(s) family spread exceeds the design note's line at 4.0 mm (section 2).
- E007 decides on sealed seeds.
