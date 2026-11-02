# O006 A4: GCI of Tj differences, and whether the GCI is conservative at singular material corners (T0181)

Research note, **not evidence** (no `ExperimentRun`, no sealed data). Development seed 1181 only; seed 20261101 layouts
were not solved (the one T0170 value in section 1 is quoted from the packet / `benchmarks/results/thermal_l2_convergence.json`).
Code: `research/scripts/o006_gci/` -- `gci_study.py` (strip cases, estimators, `merge`), `pair_jobs.py` (pairs, one process
per layout x level; `run_pairs.sh`, `run_fit.sh`), `derive.py` (difference estimators), `summarize_pairs.py`. Raw output
`research/o006_gci/part_*.json` and `pairs_jobs.jsonl`, merged into `research/o006_gci/results.json`; full per-die tables in
`research/o006_gci/pair_tables.md`. Attempt 1 produced sections 1-3 and the strip runs; attempt 2 (this revision) re-checked
the section-4 numbers against the raw JSON, ran all pairs and wrote sections 4-7. Nothing in `src/`, thresholds or the
objective was changed.

Notation: f3, f2, f1 = values at levels 0, 1, 2 of the frozen T0170 rule (r = 2); d21 = f1 - f2.
* p_obs = ln(|d32|/|d21|)/ln 2 (monotone only); Richardson error estimate RE = |d21|/(2^p_obs - 1).
* Frozen O006 GCI (`thermal_layout.gci_three_grid`): 1.25|d21|/(2^min(p,2)-1) if p_obs in [1.5, 2.5], else 3|d21|/3 = |d21|.
* Candidate rule: as frozen inside [1.5, 2.5]; outside, 3|d21|/(2^p - 1) with p = clip(p_obs, 0.5, 2). **Assumption of
  this note:** for oscillatory triples (p_obs undefined) the candidate uses p = 0.5 (the packet does not define it).
* "True error" = |f(level 2) - f_ref|; f_ref = Richardson value from the finest triple of a much longer sequence, with
  uncertainty u_ref = max(candidate GCI of that triple, |f_ref - f_finest|). Verdict: conservative if GCI >= err + u_ref,
  non-conservative if GCI < err - u_ref, else undetermined.

## 1. Signal (fact, quoted)
T0170 benchmark, u_shaped_2 (seed 20261101), layout tj_max = 422.718 / 422.088 / 421.766 K: p_obs = 0.966, frozen GCI =
|d21| = 0.322 K; RE with p_obs = 0.338 K; candidate rule 3 x 0.322/(2^0.966 - 1) = 1.01 K. The frozen rule is below RE here.

## 2. Corner exponents (derived here, checked numerically)
Wedge of material 1 (angle pi/2, conductivity k1) on material 2 (angle pi, k2), adiabatic outer faces, T ~ r^lam
cos(lam(theta - theta_face)) in each wedge; continuity of T and k dT/dtheta at the interface gives
**k1 tan(lam pi/2) + k2 tan(lam pi) = 0** (same as the `thermal_layout` docstring). Limit k1 = k2: lam = 2/3 (the
homogeneous 270 deg re-entrant corner, pi/(3pi/2)) -- reproduced by the code (0.6667). Values at the 300 K conductivities
of `default_dbc_stack()`:

| corner (90 deg wedge on 180 deg wedge) | k1 / k2 (W/m K) | lam | 2 lam (point-value pollution order, uniform refinement; inference) |
|---|---|---|---|
| die attach on top Cu (graded by the rule) | 58 / 385 | 0.835 | 1.67 |
| solder on baseplate (backside-inset edge) | 58 / 385 | 0.835 | 1.67 |
| **top-Cu trace on ceramic; backside Cu under ceramic** (not graded) | 385 / 24 | **0.519** | **1.04** |

Inference: the strongest singularity in a layout is not the die-attach corner but every Cu-trace edge on the Al2O3 (and the
backside-Cu inset edge), which the frozen rule meshes with bulk cells only. That predicts p_obs drifting towards ~1 under
refinement, i.e. outside [1.5, 2.5] asymptotically even when the level 0-2 triple is inside.

## 3. Competing explanations and discriminating tests (all run)
* **H1** die-attach/Cu corner (lam 0.835) keeps levels 0-2 pre-asymptotic.
* **H2** ungraded Cu-on-ceramic / backside edges (lam 0.519) set the asymptotic order near 1.
* **H3** tj_max is a sampled maximum of the surface interpolant (non-smooth in h; the argmax moves), so its p_obs is erratic
  and its differences oscillate, independently of any corner.
* **H4** Picard / linear iteration error (tol 1e-4 K, 1e-12) contaminates d21.

Cases (2D x-z strips: two cells in y, adiabatic y walls, so the field is exactly y-invariant; frozen-rule lateral nodes via
`edge_graded_nodes`, frozen constants; levels 0..6, finest edge cell 1.6 um, 5.36 M cells; two 4.5 mm die strips, die0 2 mm
from the pad edge; q = 1.03 MW/m2, h = 5000, coolant 65 C):

**T1 (H1 vs H2): `strip2d` (all edges) vs `strip_dieonly` (every substrate layer spans the outline: only die-attach corners
remain), k(T), sliding-triple p_obs (levels 012, 123, ...):**

| value | strip2d p_obs | strip2d err(L2) K | strip_dieonly p_obs | dieonly err(L2) K |
|---|---|---|---|---|
| die0.tj_mean | 1.68 1.57 1.45 1.33 1.23 | 0.0513 | 1.87 1.87 1.86 1.85 | 0.0061 |
| die0.tj_centroid | 1.83 1.57 1.45 1.33 1.23 | 0.0452 | 2.97 1.82 1.81 1.80 | 0.0028 |
| die1.tj_mean | 1.76 1.66 1.56 1.43 1.32 | 0.0387 | 1.88 1.88 1.87 1.85 | 0.0065 |
| die0.tj_max | 1.57 2.00 1.42 1.30 1.37 | 0.0452 | 1.54 1.43 1.32 1.23 | 0.0073 |
| diff_tj_mean (die0-die1) | 1.19 1.17 1.13 1.09 1.07 | 0.0126 | 1.97 2.00 2.01 2.01 | 0.0004 |
| diff_tj_max | osc 3.43 1.15 0.44 1.40 | 0.0069 | osc 0.69 0.89 0.98 | 0.0038 |

Result: with only the die-attach corners, smooth functionals converge at a stable p = 1.85-1.87 and the level-2 error is
6-16x smaller; with the Cu-on-ceramic edges p_obs falls monotonically towards ~1.0-1.2 (as predicted by 2 lam = 1.04).
**H2 is supported, H1 is not the dominant mechanism** (the rule's die-edge grading handles the die-attach corner).
What would refute this: a die-only case whose p_obs also drifts below 1.5 (it does not, for mean/centroid).

**T2 (H4): constant k** (`strip2d_constk`, levels 0..5): same drift (die0.tj_mean 1.74 1.65 1.54 1.42) -> H4 rejected; the
tolerances are 3 orders below d21 anyway.

**T3 (H3): tj_max vs centroid/mean.** In `strip_dieonly` the centroid and mean are regular (p ~1.8) but die0.tj_max drifts
1.54 -> 1.23 and diff_tj_max is oscillatory then p < 1. **H3 is also real** for max-type values and their differences.

## 4. Item (2): are the estimators conservative at the singular corner? (strip2d, k(T); levels 0-2 vs a fine reference)
Case `strip2d` contains the die-attach-on-Cu corners (and the Cu-on-ceramic edges of section 2). Reference = Richardson
value from levels 5-6-7 (level 7: 21.4 M cells, finest edge cell 0.78 um); u_ref = max(candidate GCI(5,6,7), |f_ref - f7|).
Reference stability: 3-4-5 and 5-6-7 references differ by <= 0.0005 K for every per-die value (`part_strip2d_kT_L5`).

| value | true err(L2) +- u_ref K | p_obs 0-1-2 ... 5-6-7 | RE | frozen GCI | candidate GCI | frozen / candidate verdict |
|---|---|---|---|---|---|---|
| die0.tj_max | 0.0455 +- 0.0018 | 1.57 2.00 1.42 1.30 1.37 1.16 | 0.0567 | 0.0709 | 0.0709 | conservative / same |
| die0.tj_mean | 0.0514 +- 0.0022 | 1.68 1.57 1.45 1.33 1.23 1.16 | 0.0425 | 0.0532 | 0.0532 | undetermined / same |
| die0.tj_centroid | 0.0453 +- 0.0019 | 1.83 1.57 1.45 1.33 1.23 1.16 | 0.0324 | 0.0404 | 0.0404 | **non-conservative** / same |
| die1.tj_max | 0.0383 +- 0.0010 | 2.30 1.59 1.47 1.53 1.35 1.29 | 0.0188 | 0.0307 | 0.0307 | **non-conservative** / same |
| die1.tj_mean | 0.0389 +- 0.0013 | 1.76 1.66 1.56 1.43 1.32 1.18 | 0.0331 | 0.0413 | 0.0413 | conservative (by 0.001) / same |
| die1.tj_centroid | 0.0345 +- 0.0011 | 1.93 1.65 1.54 1.41 1.28 1.23 | 0.0247 | 0.0308 | 0.0308 | **non-conservative** / same |
| diff_tj_max | 0.0072 +- 0.0009 | osc 3.43 1.15 0.44 1.40 0.87 | n/a | 0.0377 | 0.2730 | conservative / conservative (38x) |
| diff_tj_mean | 0.0126 +- 0.0009 | 1.19 1.17 1.13 1.09 1.07 1.06 | 0.0118 | 0.0151 | 0.0354 | conservative / conservative |

Facts: the bare RE is non-conservative for 5 of 7 defined values. Both GCI rules are non-conservative for 3 of 6 per-die
values and **identical** there, because the level 0-2 p_obs (1.57-2.30) lies inside [1.5, 2.5] where the candidate does not
act; p_obs keeps falling with refinement (to 1.16-1.29 at 5-6-7, towards 2 lam = 1.04), i.e. levels 0-2 are pre-asymptotic
and overstate the order. The candidate rule changes only out-of-range/oscillatory triples, where it is conservative but up
to 38x the true error. Inference: since p_obs(5,6,7) is still above 1.04, f_ref under-extrapolates slightly; the true errors
are then larger than tabulated, so the non-conservative verdicts are robust and the marginal conservative ones are not.
Empirically err(L2) = 0.41-0.55 |d21| for the six per-die values.
Difference estimators against the truth (`part_derived.json`): GCI_A + GCI_B (frozen) 0.102 / 0.094 K vs true 0.0072 /
0.0126 K -> conservative; the difference of the components' signed Richardson corrections, 0.038 / 0.009 K, is
non-conservative for diff_tj_mean. Limitation: 2D strip (no 3D die vertices); the 3D `die3d` case was not run.

## 5. Item (1): same-stratum development pairs (seed 1181; family, 2 dies per switch, 4.5 mm dies; levels 0-2)
Selection (deterministic, outcome-blind): "first" = first equal-die-size pair in generation order of
`generate_layouts(16, 1181, family=f, dies_per_switch=2)` (gen #0, #1 in every family); "fit" = first such pair whose level-2
grids are both <= 8 M cells (gen #1, #3), declared when gen #0 level 2 looked infeasible (it later fitted). Fit selection is
biased towards layouts with fewer grid lines. Power per die = calibrated once per family on gen #0 at level 0 to an ~85 K
hottest rise (59.9 / 64.1 / 60.7 W), identical for all layouts of a family; h = 5000 W/m2K, coolant 65 C, k(T).
Solver health: energy balance <= 4e-14, linear residual <= 3e-12, Picard <= 6 iterations, all 27 solves.

Layout tj_max (K) at levels 0 / 1 / 2 and estimators of the level-2 value (per-die rows: `pair_tables.md`):

| family gen # | M cells L2 | levels 0 / 1 / 2 | abs d21 | p_obs | RE | frozen GCI | candidate GCI |
|---|---|---|---|---|---|---|---|
| side_by_side #0 | 9.96 | 424.048 / 423.583 / 423.397 | 0.186 | 1.33 | 0.123 | 0.186 | 0.370 |
| side_by_side #1 | 4.44 | 425.663 / 424.921 / 424.697 | 0.224 | 1.73 | 0.097 | 0.121 | 0.121 |
| side_by_side #3 | 4.55 | 424.622 / 423.893 / 423.614 | 0.278 | 1.39 | 0.172 | 0.278 | 0.515 |
| interleaved #0 | 10.11 | 423.023 / 422.529 / 422.324 | 0.205 | 1.27 | 0.146 | 0.205 | 0.439 |
| interleaved #1 | 4.54 | 427.090 / 426.211 / 425.911 | 0.301 | 1.55 | 0.156 | 0.196 | 0.196 |
| interleaved #3 | 4.69 | 423.718 / 422.926 / 422.599 | 0.327 | 1.28 | 0.230 | 0.327 | 0.691 |
| u_shaped #0 | 10.03 | 423.055 / 422.613 / 422.429 | 0.184 | 1.26 | 0.131 | 0.184 | 0.394 |
| u_shaped #1 | 4.44 | 427.046 / 426.355 / 426.112 | 0.243 | 1.51 | 0.132 | 0.165 | 0.165 |
| u_shaped #3 | 4.57 | 423.276 / 422.237 / 421.996 | 0.240 | 2.11 | 0.072 | 0.100 | 0.100 |

All 45 absolute values (9 layouts x {layout, 4 dies}): monotone; p_obs 1.14-2.23 (17 inside [1.5, 2.5], 28 below);
|d21| 0.091-0.327 K; RE 0.046-0.230 K; frozen GCI 0.057-0.327 K; candidate 0.057-0.691 K. None is near 0.025 K. No value
has p_obs < 1, so frozen GCI >= RE everywhere here (the T0170 p_obs = 0.966 case is on the sealed-seed layouts).

Pairwise differences of layout tj_max, D = tj_max(A) - tj_max(B) (K):

| pair | D levels 0 / 1 / 2 | p_obs | RE | frozen GCI | candidate GCI | GCI_A+GCI_B frozen / cand. |
|---|---|---|---|---|---|---|
| side_by_side first #0-#1 | -1.615 / -1.338 / -1.300 | 2.86 | 0.006 | 0.038 | 0.038 | 0.307 / 0.491 |
| interleaved first #0-#1 | -4.068 / -3.682 / -3.586 | 2.01 | 0.031 | 0.040 | 0.040 | 0.401 / 0.634 |
| u_shaped first #0-#1 | -3.991 / -3.742 / -3.682 | 2.07 | 0.018 | 0.025 | 0.025 | 0.349 / 0.559 |
| side_by_side fit #1-#3 | 1.041 / 1.028 / 1.083 | osc | n/a | 0.054 | 0.394 | 0.399 / 0.636 |
| interleaved fit #1-#3 | 3.372 / 3.285 / 3.311 | osc | n/a | 0.026 | 0.190 | 0.523 / 0.886 |
| u_shaped fit #1-#3 | 3.770 / 4.118 / 4.115 | osc | n/a | **0.003** | 0.022 | 0.265 / 0.265 |

All 30 differences (6 pairs x {layout, 4 same-slot dies}): 13 oscillatory (all in fit pairs); raw-sequence frozen GCI
0.003-0.082 K (9 of 30 <= 0.025 K), candidate 0.005-0.394 K (5 of 30 <= 0.025 K); GCI_A+GCI_B 0.14-0.63 K (frozen) and
0.14-1.19 K (candidate). Inference: the differences "converge" at p_obs 2.0-2.9 or oscillate although every component
converges at 1.14-2.23, i.e. the difference sequence reflects partial cancellation of two errors with different rates,
not an order of accuracy. The u_shaped fit pair shows the hazard: d32 = +0.348 K, d21 = -0.003 K gives a frozen GCI of
0.003 K while each component moved by 0.24 K at the same step. A GCI computed on the difference sequence alone is
therefore not a trustworthy bound; whether it is conservative cannot be decided here (no reference for full layouts).

## 6. Item (3): accuracy reachable within 16 GB
Facts (this host, shared with other worktrees): level 2 of the 16.8 M-grid / ~10 M-active-cell layouts peaked at 4.7-6.5
GB RSS (635-888 s); the 4.4-4.7 M-cell layouts at 3.2-5.7 GB (50-100 s); i.e. 0.65-1.25 kB per active cell. Level 3 is 8x
the cells (36-81 M), >= 23 GB even at the lowest measured rate: **level 2 is the finest level of the frozen rule that fits
in 16 GB** (inference: attempt 1's 4789 s for the same solve was host oversubscription, not a requirement).
* Absolute tj_max (per die or layout): frozen GCI 0.06-0.33 K, candidate 0.06-0.69 K. Transferring the strip ratio
  err(L2) ~ 0.4-0.55 |d21| (inference, 2D -> 3D not verified) gives true errors ~0.04-0.18 K. With asymptotic order ~1
  (section 2) each further level halves the error: 0.025 K needs about 2-3 more levels (64-512x cells). **Not reachable.**
* Differences between same-stratum layouts: estimator-dependent. Raw-sequence frozen GCI 0.003-0.082 K;
  the only estimator verified conservative (GCI_A+GCI_B, strip, 2 cases) gives 0.14-0.63 K. In the strip, true difference
  errors were about 3-7x smaller than per-die errors (0.007-0.013 K). So ~0.01-0.05 K difference accuracy is plausible
  (inference) but cannot be **demonstrated** at 0.025 K with an estimator shown to be conservative.

## 7. Conclusions and recommended actions (founder decision inputs; no threshold, rule or objective changed)
1. Root cause (confidence 0.7): the frozen grid rule's levels 0-2 are pre-asymptotic because the ungraded Cu-trace-on-Al2O3
   and backside-inset edges (lam = 0.519, point-value order ~1.04) dominate; the graded die-attach corner (lam = 0.835) is
   not the limiting singularity (T1). Consequently p_obs from levels 0-2 overstates the order and the Roache GCI with Fs
   1.25 is non-conservative for 3 of 6 per-die values with a validated reference. Secondary: tj_max sampling (H3).
2. The candidate rule (Fs 3, p = clip(p_obs, 0.5, 2) outside [1.5, 2.5]) is conservative where it acts but **does not
   repair** the in-range non-conservative cases and is up to 38x pessimistic on oscillatory differences. Not sufficient
   alone as the A4 correction.
3. A4 (<= 0.025 K for every reported value) is unreachable at 16 GB for absolute Tj under any rule examined (frozen,
   candidate, theory-order); for differences it is met only by the raw-sequence frozen GCI in 9 of 30 cases, an estimator
   not shown to be conservative. `affects_acceptance_criteria`: yes.
4. Options, each needing a founder decision and a new experiment id (none tested here beyond T1/T2/T3):
   (a) grade every trace and backside-inset edge like die edges, then re-test (die-only strip: p ~1.85 and 6-16x smaller
   level-2 error); (b) report die-mean or centroid Tj (smoother) alongside tj_max; (c) a theory-order GCI, p = min(p_obs,
   1.04), Fs 3 (post hoc; 5-7x the true error on the strip per-die values, by 2.85 |d21| / err; 0.26-0.93 K on the dev layouts, `pair_tables.md`);
   (d) for differences, bound by GCI_A + GCI_B or require a monotone difference sequence; (e) re-scope the A4 threshold to
   what level 2 can demonstrate (~0.3-0.7 K absolute under the candidate rule).
What would change these conclusions: a 3D layout reference (cropped domain at levels 3-4) showing level-2 errors inside the
frozen GCI; or a graded-edge rule whose p_obs still drifts below 1.5.
