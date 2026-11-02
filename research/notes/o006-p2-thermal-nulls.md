# O006 pilot P2: thermal null predictors per O002 stratum (research note, not evidence)
Task T0167 (O006) · scientist · 2026-11-01 · Exploratory design input for O002/E007 (O006 F4: pilots are never evidence).

Amendment before the production run (2026-11-01): the fixed level was changed from 1 to 0 because a
2-layout smoke run cost 250-315 CPU-s per layout at level 1 single-threaded (about 9 CPU-hours for the sample against
the brief's ~3). The smoke run is not part of the results. Nothing else changed.

## 1. Pre-registered definitions (written before any P2 number was computed)
This section was written, and its sha256 recorded by `thermal_envelope.py p1` in `research/o006_p1/raw/prereg.json`,
before the P1 solves started and before any P2 solve. It was not edited afterwards. Results are in section 2.

Data. P1's sample (`research/scripts/o006_p1/thermal_envelope.py`), thermal L2 `solvers.thermal_layout` at frozen-rule
level 0 (one fixed level), k(T) with the coded laws of `geometry/stack.py`, coolant 65 °C, uniform h = 5000 W/(m² K),
equal power per die, uniform over each die's top area. Strata are O002's: s = (family, dies per switch), 15 strata.
One die size d_s per stratum, drawn before any solve: `rng(916700).permutation([4.0, 4.5, 5.0, 5.5] x 4)[:15]` in stratum
order (side_by_side 2..6, interleaved 2..6, u_shaped 2..6). The P2 core of stratum s is the first K = 10 DRC-valid
layouts with die size d_s in the generator stream of dev seed 916701 + s (s = 0..14). Loads: the two load levels P_lo,
P_hi chosen by P1's frozen rule (P1 note, section 1). Every P2 value is a direct L2 solve at those loads (no interpolation).

Target. T[j, i] = per-die Tj max (maximum of the die-top surface temperature, `ThermalResult.surface_stats`) of die i in
layout j of the stratum, at one load level; i runs over the 2n dies, labelled (switch, index along x).

Predictors of T[j, i] (all three per stratum and per load level):
1. **Stratum mean (SM)**: the mean of T over all K layouts and all dies of the stratum, in-sample (the evaluation set's own
   mean, as O002's null (d) is computed on the evaluation rows).
2. **Die-size cell mean (CM)**: O002 null (b), a dev-trained lookup on (family, dies, die size, load) returning the cell
   mean. Trained leave-one-layout-out: for layout j, the mean over the other K - 1 layouts and all their dies.
   Because O002 fixes one die size per stratum, the (family, dies, die size) cell is the stratum, so CM differs from SM
   only in being trained out-of-sample. This degeneracy is a property of O002's design and is reported, not hidden.
3. **Die-position lookup (DP)**: O002 null (c), a dev-trained lookup on (family, dies, die size, load, switch, die index),
   leave-one-layout-out: for die (switch w, index i) of layout j, the mean of T over the other K - 1 layouts at the same
   (w, i).

Reported per stratum, predictor and load level:
- p95_abs_err_K: the 95th percentile (numpy linear interpolation) of |T - prediction| over all K x 2n dies; with a 95 %
  layout-clustered bootstrap interval (B = 2000, seed 916799; layouts resampled with replacement, per-die errors held as
  computed on the full sample).
- n_layouts and n_dies.
- For DP also the p95 of |T - prediction| / (T - mean baseplate-bottom temperature) (O002 A3's normalisation; the mean
  baseplate-bottom temperature is exactly T_c + Q/(h A_baseplate) by the energy balance).
Within-stratum spread, per stratum and load level: SD and range (max - min) of the layout-level Tj max (hottest die of
each layout) over the K layouts; SD of per-die T over all dies; the pairwise layout differences |Tj max,a - Tj max,b| over
all K(K-1)/2 pairs (median, p95, max), which is also the error of the stratum-mean predictor of a pair difference (O002 A2
null, predicted difference 0); and the per-switch spread (max - min of T over one switch's paralleled dies): mean and SD,
with the p95 error of the stratum-mean-spread predictor (O002 A4/A5 null).

Not done: no predictor is tuned; no stratum, layout or die is dropped after solving; no other predictor is added to the
nulls list after seeing results (any extra analysis is labelled exploratory).

## 2. Results (facts; level 0, k(T), P_lo = 25 W and P_hi = 45 W per die from P1's frozen rule)
Section 1 is checkable: the sha256 of the first 49 lines of this file (joined by newlines, no trailing newline) equals
the P2 hash in `research/o006_p1/raw/prereg.json` (b08f7648...), recorded before the first solve (P1 note, section 2).
n_layouts = 10 per stratum, n_dies = 20-120 per stratum (2n x 10), 15 strata, 2 load levels: 90 entries in
`results.json["nulls"]` (stratum x predictor x load). All are direct solves (no interpolation). Bootstrap intervals are
in results.json; with K = 10 layouts they are wide (for example side_by_side/2 at 45 W, stratum mean 3.59 K [2.85, 5.04]).

p95 absolute error of per-die Tj max, K (stratum mean SM / die-size cell mean CM / die-position lookup DP), with the DP
error relative to the local rise (O002 A3 normalisation), the within-stratum spread of layout Tj max (SD, range), the
pairwise |dTj max| p95 over 45 layout pairs, and the per-switch spread (mean; p95 error of the stratum-mean spread).
Every cell gives the 25 W value, then "/", then the 45 W value; cells with two numbers per load separate them by a comma:

| stratum (die mm) | load | SM | CM | DP | DP rel | Tj max SD, range | pair p95 | switch spread: mean, null p95 err |
|---|---|---|---|---|---|---|---|---|
| side_by_side/2 (4.5) | 25 / 45 W | 1.89 / 3.59 | 1.97 / 3.73 | 0.97 / 1.85 | 3.2 / 3.4 % | 0.72, 2.28 / 1.38, 4.38 | 2.01 / 3.85 | 0.37, 0.52 / 0.70, 1.01 |
| side_by_side/3 (5.5) | 25 / 45 W | 2.75 / 5.12 | 2.79 / 5.21 | 1.35 / 2.54 | 5.3 / 5.4 % | 0.94, 3.03 / 1.78, 5.73 | 2.55 / 4.83 | 2.46, 0.16 / 4.58, 0.31 |
| side_by_side/4 (5.0) | 25 / 45 W | 4.09 / 7.63 | 4.21 / 7.84 | 1.63 / 3.11 | 5.5 / 5.7 % | 1.05, 3.42 / 2.01, 6.61 | 2.59 / 4.99 | 4.09, 0.31 / 7.65, 0.61 |
| side_by_side/5 (4.5) | 25 / 45 W | 5.97 / 11.42 | 6.15 / 11.82 | 2.45 / 4.64 | 6.4 / 6.5 % | 1.27, 3.81 / 2.45, 7.35 | 3.21 / 6.12 | 6.43, 0.60 / 12.11, 1.25 |
| side_by_side/6 (5.5) | 25 / 45 W | 5.75 / 10.79 | 5.89 / 11.05 | 2.45 / 4.62 | 8.6 / 8.8 % | 1.61, 4.73 / 3.05, 8.93 | 4.12 / 7.80 | 6.37, 0.70 / 11.86, 1.34 |
| interleaved/2 (4.0) | 25 / 45 W | 1.65 / 3.18 | 1.75 / 3.36 | 1.13 / 2.16 | 3.4 / 3.5 % | 0.66, 2.07 / 1.27, 3.97 | 1.82 / 3.50 | 0.10, 0.12 / 0.19, 0.24 |
| interleaved/3 (4.5) | 25 / 45 W | 2.68 / 5.10 | 2.71 / 5.16 | 1.08 / 2.06 | 3.5 / 3.6 % | 0.76, 1.87 / 1.45, 3.59 | 1.83 / 3.52 | 2.51, 0.21 / 4.75, 0.43 |
| interleaved/4 (5.0) | 25 / 45 W | 3.34 / 6.30 | 3.47 / 6.54 | 1.41 / 2.70 | 5.6 / 5.6 % | 0.79, 2.48 / 1.50, 4.70 | 1.95 / 3.73 | 3.44, 0.36 / 6.45, 0.68 |
| interleaved/5 (5.5) | 25 / 45 W | 3.78 / 7.09 | 3.95 / 7.39 | 1.85 / 3.48 | 6.9 / 7.0 % | 0.92, 2.77 / 1.74, 5.22 | 2.46 / 4.64 | 4.64, 0.41 / 8.63, 0.77 |
| interleaved/6 (5.5) | 25 / 45 W | 4.32 / 8.07 | 4.42 / 8.27 | 1.60 / 3.01 | 6.9 / 7.1 % | 1.08, 2.89 / 2.05, 5.45 | 2.73 / 5.15 | 5.42, 0.54 / 10.09, 1.03 |
| u_shaped/2 (4.0) | 25 / 45 W | 1.28 / 2.48 | 1.41 / 2.69 | 1.51 / 2.90 | 4.4 / 4.5 % | 0.87, 2.65 / 1.68, 5.12 | 2.40 / 4.63 | 0.27, 0.23 / 0.51, 0.44 |
| u_shaped/3 (4.0) | 25 / 45 W | 3.10 / 5.91 | 3.27 / 6.30 | 2.13 / 4.10 | 6.2 / 6.5 % | 1.14, 3.78 / 2.21, 7.33 | 3.19 / 6.21 | 3.22, 0.29 / 6.15, 0.59 |
| u_shaped/4 (5.0) | 25 / 45 W | 3.05 / 5.79 | 3.18 / 6.03 | 1.36 / 2.58 | 4.5 / 4.7 % | 0.66, 2.25 / 1.26, 4.35 | 1.63 / 3.20 | 4.13, 0.14 / 7.74, 0.28 |
| u_shaped/5 (4.5) | 25 / 45 W | 4.88 / 9.26 | 5.06 / 9.62 | 2.59 / 4.98 | 7.0 / 7.1 % | 1.51, 4.49 / 2.94, 8.74 | 3.87 / 7.56 | 6.31, 0.36 / 11.90, 0.72 |
| u_shaped/6 (4.0) | 25 / 45 W | 5.93 / 11.35 | 6.17 / 11.80 | 2.66 / 5.18 | 6.5 / 6.7 % | 1.83, 4.86 / 3.60, 9.47 | 4.51 / 8.83 | 8.25, 0.51 / 15.73, 1.04 |

Summary over the 15 strata (min / median / max of the per-stratum p95):
- 25 W: SM 1.28 / 3.34 / 5.97 K; CM 1.41 / 3.47 / 6.17 K; DP 0.97 / 1.60 / 2.66 K; DP relative 3.2 / 5.6 / 8.6 %.
- 45 W: SM 2.48 / 6.30 / 11.42 K; CM 2.69 / 6.54 / 11.82 K; DP 1.85 / 3.01 / 5.18 K; DP relative 3.4 / 5.7 / 8.8 %.
- Pooled over all strata, the stratum-mean-spread predictor's p95 error of the per-switch spread (300 switch values) is
  0.50 K at 25 W and 1.02 K at 45 W (exploratory: computed after section 1 was frozen, as the A5 denominator).

## 3. What this means for O002 (inference)
- Errors scale almost linearly with power (45/25 = 1.8; the p95 ratios are 1.8-1.95, slightly more because of k(T)).
  At O002's present 60 W they would be about 1.35 x the 45 W values, but 60 W is outside the 175 °C envelope (P1 note).
- CM equals SM up to leave-one-layout-out training noise: its p95 is 1-9 % above SM in every stratum. Under one die size
  per stratum, O002's null (b) is redundant with null (d); keeping both adds nothing.
- DP (null (c)) is the strongest null. Its local relative error has a median of 5.6-5.7 %, matching review T0132's
  "about 5.6 %", and it is at least 3.2 % in every stratum. So O002 A3 (3 %) is failed by every null in every stratum at its
  point estimate, but only narrowly in side_by_side/2, interleaved/2 and interleaved/3 (3.2-3.6 %; no interval was
  computed for the relative error, so these three may not fail A3 on a fresh sample).
- A2 (pair differences, 0.5 K): the stratum-mean pair null (predicted difference 0) has p95 1.6-4.5 K at 25 W and
  3.2-8.8 K at 45 W, 3-18 times the threshold. A2 discriminates well.
- A4 (switch spread error, 1 K): the stratum-mean-spread null has a p95 error below 1 K in 11 of 15 strata at 45 W and in
  all strata at 25 W. A4 alone does not reject this null in most strata. A5 (L1 at most half the null's error) is what
  carries this test: pooled, L1 would need a spread error p95 of about 0.5 K at 45 W (0.25 K at 25 W). O002 should check
  this against its L1 accuracy targets.
- Within-stratum spread is small at the low level: the SD of layout Tj max is 0.66-1.83 K at 25 W. The level bias that
  varies from layout to layout (P1 note, section 5) has to stay well below this, or the reference itself adds spread.
- With K = 10 layouts per stratum the per-stratum p95 is uncertain by about +-30 % (bootstrap). O002's planned >= 10
  layouts per stratum gives null p95 values no better known than that.

## 4. Limitations
Level 0 grid. On P1's 10-layout bias set (P1 note, section 5), level 0 minus level 2 is +0.14 to +0.92 K per die, the
same sign everywhere. Its layout-to-layout SD (0.10 K at 25 W, 0.19 K at 45 W) is far below every Tj max and pair
number above. It is not negligible for the switch-spread null: the level-0 excess of the layout spread (max - min over
all dies, a proxy for the per-switch spread, which was not computed at level 2) is +0.12 K mean, SD 0.05 K, max 0.22 K
at 45 W, and the within-layout die-to-die range of the bias reaches 0.34 K, while the stratum-mean-spread null's p95
error at 45 W is only 0.24-0.44 K in interleaved/2, u_shaped/4, side_by_side/3, interleaved/3 and u_shaped/2. In those
strata the spread-null numbers are uncertain at the 0.1-0.2 K level from the grid alone (inference). One die size per stratum, drawn once; a different draw changes
which strata are hottest. Uniform h and uniform die heating, as in O002. LOLO training on 9 layouts is noisier than a
large dev-trained lookup, so DP errors here are an upper estimate of a well-trained lookup (CM vs SM shows a 1-9 %
inflation; DP, with 9 samples per die position, is inflated more). Research note, not evidence.
