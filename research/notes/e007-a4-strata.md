# E007: the per-stratum A4 misses (T0456, O002), 2026-11-17

Not evidence. These are development rows and design-time simulation only. Nothing gated was changed: the L1, its
calibration, the criteria, thresholds, bound and m are untouched. The only spec edits are `compute.bytes_per_dof['1']`
(3400 → 4400) and the new development seed 20261456, added to `seeds.forbidden`.

Files:
- `research/o002_e007/a4_strata/diag_rows.py`: per-switch-row anatomy, giving `diag_t0398.json` and `diag_combined9.json`.
- `diag_solves.py`: the L1-grid and reference-level tests, giving `diag_solves.json`.
- `run_extra.py`: the extra layouts. Rows go to `research/o002_e007/dev_rows_a4_strata.json`; the combined 9-layout rows
  and checkpoints go to `a4_strata/work/`.
- `sim_corrected.py`: the corrected simulation, giving `sim_corrected.json` (checkpoint `sim_corrected_checkpoint.json`).

## Two A4 nulls are not informative (review T0459 (2))
Of A4's three nulls, only isolated_die is informative.
- stratum_mean is A4's own denominator, so its A4 is exactly 1.
- die_position's spread is at most the stratum-mean spread by construction, so its A4 is about 1. Measured: 0.99999999999998
  (T0398) and 0.99999999999995 (the new rows).

isolated_die's A4 on the extra layouts (P_ref, point):

| stratum | new 6 layouts | all 9 layouts |
|---|---|---|
| interleaved/2 | 1.06 | 1.08 |
| side_by_side/2 | 1.99 | 2.07 |
| u_shaped/6 | 10.19 | 10.74 |

Pooled over the new rows it is 10.16. In interleaved/2 only, isolated_die's A4 is near 1 (1.06 / 1.08): there, knowing
the isolated-die spreading gives about as much as knowing the stratum-mean spread. In side_by_side/2 it is about 2
(1.99 / 2.07), so the isolated-die null is about twice as bad as the stratum mean there. (Corrected by T0464, review
T0463 (2); an earlier version said "near 1 in both 2-die strata".)

## 1. u_shaped/6 (A4 0.951 on T0398's 3 layouts): cause
Facts, from T0398's rows (`diag_t0398.json`):
- **The ratio is 0.0950 K / 0.0998 K.** The L1 numerator is small in absolute terms: A3-type 0.095 K, against A3's 1 K.
  The denominator is small too.
- **The reference spread is about 10 K in every row.** Values are 9.93–10.16 K, with sd 0.089 K over the 6 rows.
  - The hottest and coldest dies are die_index 2 and 5 in every row, in both the reference and L1.
  - So no single layout or die position dominates. One die pair sets every spread, and the three layouts are nearly
    identical in spread.
  - The stratum-mean null (leave-one-layout-out) is therefore almost exact: |error| ≤ 0.10 K.
- **L1's spread error is systematic.** It is −0.086 to −0.095 K in all 6 rows (−0.9 % of the spread). It is the
  difference of L1's die biases at positions 2 and 5. In HS the per-position bias is about [+0.18, −0.08, −0.12, −0.13,
  −0.10, −0.03] K, the same shape in every layout.
- **Recalibrating does not remove it.** Recalibrating to the stratum's implied factor (1.00027 × c(5.5 mm)) changes A4
  only from 0.951 to 0.924.
- **The calibration's form contributes, and the L1 grid rule does not explain it** (`diag_solves.json`, test (a)).
  The uncalibrated coarse FV spread is **+0.066 to +0.077 K** too high. The frozen c(5.5) = 0.98402 scales every rise,
  so it shrinks a 10 K spread by 1.6 % (−0.16 K) and gives the observed −0.09 K. c is fitted to the mean die rise on
  side_by_side/6 and u_shaped/2, and transfers to a 10 K inter-die spread only in part.
  - Refining the FV grid (h0 0.75 mm; 0.75 mm with lat_frac 32 and z_cells 4; 0.5 mm with lat_frac 32 and z_cells 4)
    lowers the raw error to +0.038 to +0.047 K.
  - Under the same refinement the calibrated error grows to −0.113 to −0.125 K, because c is fixed.
  - So a finer L1 grid alone would make the calibrated spread worse.
- **Reference discretization does not explain it** (test (b): level-0 reference solves on the same three layouts).
  - From level 0 to level 1 the reference spread changes by only +0.012 to +0.019 K.
  - With r = 2 and p = 2 (Richardson extrapolation, assumed asymptotic), the level-1 reference error on this spread is
    about 0.004–0.006 K. With p = 1 it is at most about 0.02 K.
  - Either way it is well below L1's 0.09 K.
- **Comparison with u_shaped/2** (calibrated family, 5.0 mm): A4 = 0.254, which is 0.151 / 0.595 K.
  - Its reference spreads are small (0.37–1.13 K) and vary a lot between layouts (sd 0.28 K), so the denominator is large.
  - L1's worst row is u_shaped_2_j01 HS at +0.186 K. Refining the L1 grid lowers it to +0.08 to +0.11 K, so there the
    grid rule matters.
  - The reference changes by up to 0.10 K from level 0 to level 1 (u_shaped_2_j02), so in 2-die strata the reference's
    own error may be a material share of L1's error.

Facts, from the 6 new u_shaped/6 layouts (seed 20261456, `diag_combined9.json`):
- L1's spread error is again −0.072 to −0.099 K in all 12 new rows.
- Two of the new layouts have reference spreads of 9.30–9.43 K (t456j02) and 11.05–11.08 K (t456j03). T0398's three
  layouts never sampled spreads that far apart.
- The null's error p95 rises from 0.10 K to 1.00 K (9 layouts), so **A4 drops to 0.092 (new 6) and 0.096 (all 9).**

Inference: u_shaped/6's 0.951 is mainly a small-denominator artefact. T0398's three layouts happened to have almost the
same spread (CV 0.9 %; the 9-layout CV is 4.2 %). That is T0398's speculation, now checked.
- The numerator is not noise: it is a stable −0.9 % spread bias, mostly the rise-proportional calibration applied to a
  large inter-die spread.
- A per-stratum A4 over ≤ 18 switch rows is a ratio of near-maxima. Here the denominator is set by the one or two most
  atypical layouts (t456j02/j03).
- At m = 20 a stratum whose layouts happen to be uniform in spread can again show A4 near 1. That cannot happen to the
  pooled A4, the criterion, whose denominator pools all 15 strata.

## 2. Extra development layouts (6 per stratum, seed 20261456, level 1, both loads)
What was run (facts):
- 36 level-1 solves; P_ref reused from T0398's calibration records, identical to 1e-12.
  - 1.15 CPU-h, one solve at a time, thread variables 1.
  - Peak RSS 4.75 GB (u_shaped/6). Cap 7.5 GB, allowed by the 10 GB rule: memory_pressure showed 51 % free at the start
    and no swap file in /private/var/vm.
  - `sysctl vm.swapusage` is blocked in this sandbox, so the runner's swap guard read 0. I checked swap by hand.
- Rows go to `dev_rows_a4_strata.json` (`meta.smoke = false`). The new layouts are named `*_t456jNN`.
- All 18 fingerprints are distinct, and none equals a T0398 layout or a P_ref layout.
- Every check passed except `allocation_fixed`. It fails by design: 3 strata × 6, not 15 × m.
- To run 3 strata, the registered pipeline is used with `all_strata`/`cells`/`BANDS` narrowed in-process. The freeze
  checks still run against the 15-stratum allocation.
- The 9-layout statistics recompute both leave-one-layout-out nulls over all 9 layouts.

Per stratum. A4 is at P_ref, 18 switch rows on 9 layouts (12 on the new 6). A2 is at the max over loads. Point values,
with the V4 upper bound where finite:

| stratum | A4 new 6 | A4 all 9 | A4 num / den (9), K | A4 upper (V4) | A2 all 9 (upper) | A3 all 9 (K) | A4 > 0.3? |
|---|---|---|---|---|---|---|---|
| interleaved/2 | 0.272 | **0.286** | 0.050 / 0.177 | +inf | 0.0085 (+inf) | 0.050 | no on points, by a small margin |
| side_by_side/2 | 0.243 | **0.223** | 0.052 / 0.234 | +inf | 0.0066 (+inf) | 0.052 | no |
| u_shaped/6 | 0.092 | **0.096** | 0.096 / 1.004 | +inf | 0.0059 (0.0075) | 0.096 | no |

- No per-stratum A4 upper bound is finite at 6 or 9 layouts. The only finite per-stratum bound is u_shaped/6's A2.
- At half P_ref (reported) A4 is 0.280, 0.221 and 0.104.

Bias by switch, mean of L1 minus reference die average, K, all 9 layouts:

| stratum | HS at P_ref | HS at 0.5 P_ref | LS at P_ref | LS at 0.5 P_ref |
|---|---|---|---|---|
| interleaved/2 | +0.085 | +0.035 | **+0.364** | +0.163 |
| side_by_side/2 | +0.216 | +0.095 | −0.103 | −0.052 |
| u_shaped/6 | −0.020 | −0.014 | +0.041 | +0.014 |

- On the new 6 alone, interleaved/2's LS bias is +0.371 K. This reproduces T0423/T0424/T0398's +0.3 to +0.5 K.
- The bias roughly halves at half load, so it is close to proportional to the rise.

Inferences:
- interleaved/2's L1 under-predicts the spread in all 18 rows (−0.019 to −0.055 K, about −15 to −20 %). That is
  systematic, and it holds the stratum near 0.3.
  - Refining the L1 grid barely changes its error (max |err| 0.048 → 0.046 K).
  - The reference spread falls from level 0 to level 1 by 0.04–0.08 K. If it keeps falling, a level-2 reference
    would shrink the apparent L1 error, by an estimated 0.015–0.03 K at p = 2 (unchecked: level 2 does not fit locally,
    T0398).
- side_by_side/2's L1 errors differ by switch: LS is −0.001 to +0.076 K and HS is −0.019 to +0.011 K. Refining the
  grid lowers its max error from 0.076 to 0.028 K.
- The three strata no longer trip D0025 decision 4's 0.3 line on point values. Each per-stratum A4 still has an
  unbounded upper bound, and interleaved/2 sits 0.014 below the line. Two of T0398's three trips (0.352, 0.340) look like
  3-layout noise; the third (0.951) was the small-denominator effect above.

## 3. Corrected per-cell power simulation (review T0420 item 2)
Model (`sim_corrected.py` docstring):
- Reference: rise = R_s + P_s[w,i] + sa·z_a + sv·z_v, where P_s is the stratum's die-position profile.
- L1 error: e = b_{s,w,load} (the HS/LS offset as a fixed effect) + Q_{s,w,i,load} (the die-position profile of the
  deviation around the (layout, switch) mean, fixed) + sc·z_c + sd·z_d.
- The random scales (sa, sv, sc, sd) are pooled per (family, band) cell by sums of squares over degrees of freedom.
  These are the measured reference variation, not n1's.
- The between-load correlation is measured. The fit uses T0398's rows with the three 9-layout strata substituted.
- Bound: V4 through `stats_sim_dev.run_cell`. 1000 reps per cell, truth from 1200 reps, seeds from 20261456.
  Monte Carlo SE is 0.007 at 0.95 and 0.016 at 0.5.

**Consistency check (declared in the script before it ran; gates the rest): PASS.** The measured pooled A4 at T0398's
structure (15 × 3) is 0.107.
- Normal errors: simulated median 0.108 (5–95 % range 0.082–0.140).
- t3 errors: simulated median 0.107 (range 0.078–0.150).

The adequacy limits below are reported, not gated, and are not hidden:
- **A3 is over-predicted.** Simulated median 0.127 K (normal) and 0.117 K (t3), against 0.091 K measured, which falls
  outside the 5–95 % range.
  - Likely cause (inference): each fixed profile estimated from 3 layouts carries noise of variance sd²/3, which
    inflates the die-level error. The numerator and the denominator are inflated together, so A4 still matches.
- **Per-stratum A4 at m = 9 matches in only one of the three strata:**

  | stratum | measured | simulated 5–95 % range (normal) | match |
  |---|---|---|---|
  | interleaved/2 | 0.286 | 0.14–0.42; P(A4 > 0.3) = 0.28 | yes |
  | side_by_side/2 | 0.223 | 0.05–0.13 | no |
  | u_shaped/6 | 0.096 | 0.12–0.25 | no |

- So the model is adequate for the pooled A4, not for per-stratum A4 or A3.

Power for the L1 as measured, at m = 20 / 24 / 32 / 40. Truth: A4 0.127, A1 0.22 K (normal) / 0.20 K (t3), A2 0.009,
A3 0.13 / 0.12 K.

| errors | joint power | A4 alone | min V4 coverage over all 7 statistics |
|---|---|---|---|
| normal | 1.000 / 1.000 / 1.000 / 1.000 | 1.000 at every m | 0.980 / 0.987 / 0.974 / 0.976 |
| t3 | 0.998 / 1.000 / 1.000 / 1.000 | 1.000 at every m | 0.971 / 0.979 / 0.981 / 0.973 |

Correction (T0464, review T0463 (1)): an earlier version of the normal row's "A4 alone" column showed
1.000 / 1.000 / 0.999 / 0.997, which is A4's V4 *coverage* at m = 20 / 24 / 32 / 40, not its power. A4 power is 1.000 at
every m under both error models (`a4_strata/sim_corrected.json` cells `power|*|m`, `power_each.A4`).

**Coverage at the registered m (review T0459 (1)).** This, not T0398's m = 3 figure (which is 1.0 by construction),
is the registration evidence.
- The lowest per-statistic coverage at any m is A1 under t3 at m = 20: 0.971, against V4's one-sided 97 %. That is
  within one Monte Carlo SE of nominal.
- The full tables per statistic and per m are in `sim_corrected.json` under `cells.*.coverage`.

**Kill side.** Model rescaled jointly so the truth is 1.2 × each kill threshold. Achieved: A1 1.80–1.82 K, A2 0.180,
A4 1.19–1.20. Scales: offsets ×22.5, layout-level ×4.5–4.9, die-level ×9.7–9.9. Probability that each kill fires,
m = 20 / 24 / 32 / 40:

| errors | K1 | K2 | K3 | min coverage |
|---|---|---|---|---|
| normal | 0.418 / 0.575 / 0.812 / 0.885 | 1.000 everywhere | 0.291 / 0.405 / 0.576 / 0.764 | ≥ 0.980 |
| t3 | 0.306 / 0.426 / 0.581 / 0.669 | 1.000 everywhere | 0.168 / 0.198 / 0.354 / 0.486 | ≥ 0.980 |

- At least one kill fires in every dataset, because K2 always fires.
- Comparison with T0398's n5-structure kill side, which uses a different generative model, so this is not a replication:
  - K3 at m = 20: 0.29 here, 0.38 there (normal).
  - K1 at m = 20: 0.42 here, 0.975 there (normal).
- Inference: with the measured structure (errors concentrated in fixed offsets and positions), K1 and K3 have low
  kill-side power at m = 20. A true ratio 1.2 × K3's line is killed with probability under 0.3 to 0.4. Raising m to 40
  roughly doubles K3's rate.

## 4. Memory
`config.compute.bytes_per_dof['1']`: 3400 → **4400**.
- Over T0398's 90 and this task's 36 level-1 solves, (peak RSS − 0.3 GB)/DOF is at most 4.33 kB.
- With 3400 the admission estimate (× 1.15 + 0.3 GB) was exceeded by up to 9 %. With 4400 every peak is ≤ 0.87 × the
  estimate.
- `--plan`'s level-1 memory rises by the same ratio. CPU-hours do not change.

## What would change these conclusions
- **u_shaped/6.** The diagnosis would be wrong if L1's −0.09 K spread bias moved with the layout, or if a level-2
  reference moved the spread by ≥ 0.05 K. The level-0 → level-1 change (≤ 0.02 K) makes both unlikely. A4 near 1 would
  return in any sample whose u_shaped/6 layouts happen to be uniform in spread.
- **interleaved/2.** A sealed 20-layout sample could put it above 0.3: the corrected model gives P ≈ 0.25–0.28 at 9
  layouts. A level-2 reference spread lower than level 1 by ≥ 0.02 K would lower it.
- **Power.** The power figures rest on a model that reproduces the pooled A4 but over-predicts A3 by about 30–40 % and
  misses two of three per-stratum A4s. If the real die-level structure has less fixed position error than fitted, A4
  power stays near 1 (truth 0.127 against 0.5). Kill-side rates are the model-dependent part.

## For the founder (facts, no recommendation on the stop rule's outcome)
- On 9 layouts per stratum, the three tripped strata are at A4 0.286, 0.223 and 0.096 (points), all ≤ 0.3, with
  unbounded per-stratum upper bounds.
- The HS/LS offset on interleaved (+0.36 K LS) persists.
- L1 under-predicts the spread systematically in interleaved/2 (about −17 %) and in u_shaped/6 (−0.9 %, mostly from the
  rise-proportional calibration).
