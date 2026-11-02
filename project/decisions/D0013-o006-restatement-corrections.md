# D0013 — O006 restatement corrected after re-reviews T0184/T0185 (estimator defined, load pinned, O003 carries the difference)
Date: 2026-11-02 · Status: accepted · Decider: founder (founder session, 2026-11-02) · Amends: O006 (on top of D0012)

## Context
D0012 restated O006's A3/A4 after T0170/T0181. Both re-reviews of the restated objective rejected it (T0184 statistics,
T0185 physics; project/reviews/OBJ-O006/). Their common findings, checked by the founder session:
- Hypothesis (b) still said "agrees within 0.05 K" while A3 tests agreement within the summed GCIs (up to 1.0 K), so
  every criterion could pass with the statement false. The null, why_it_matters and decision_if_pass were still keyed to
  O002's precision, which D0012 itself says O006 does not verify.
- A4's estimator was undefined for monotone sequences with growing or equal steps. Applied literally, it gave a negative
  GCI (which passes) or a division by zero. A lucky-grid sequence (observed order far above 2) got a near-zero GCI. The
  grid index order was implied only.
- "0.5 K is a quarter of O003's +2 K" was wrong: O003 judges a two-layout difference, which inherits up to
  GCI_ref + GCI_best = 1.0 K, half its budget.
- A3/A4 named no load, although the discretisation error scales with the rise.
- A4 covered only the two development layouts the estimator and threshold were chosen on (two of three families).
- The evaluator took the maximum of a GCI column the runner computed, so a wrong cap or index swap would pass the
  recomputation.
- A failure of the scikit-fem cross-check (A3b) mapped to adopting scikit-fem.
- F1's 0.02 K scikit-fem agreement checks did not budget scikit-fem's own error.
One T0184 finding is void: T0181's results (research/o006_gci/results.json) are committed. They were merged after the
reviewed commit.

## Decision
Founder answers of 2026-11-02 in the founder session; text in docs/reports/o006-criteria-change-D0013.patch.
- **Threshold:** A4 stays at **0.5 K per value**. O003 inherits up to 1.0 K on its two-layout difference and deducts it:
  a candidate meets O003's Tj limit only if ΔTj + GCI_ref + GCI_best ≤ 2 K. This goes into O003's revision; O003 is
  paused (D0011).
- **Load:** every generator layout in A3 and A4 runs at **O003's operating point**. That is 65 °C coolant,
  h = 5000 W/(m² K) and k(T), with equal power per die. The power is fixed per layout from an L2 level-0 solve so the
  hottest die rises 60 K (±1 K), then used unchanged by both solvers and on every grid. O003 fixed this point
  before T0181's data. Other loads (O002's 45 W) carry their own per-run GCI.
- **Estimator (A4, also used by A3 and F5):** f0, f1, f2 are levels 0 (coarsest), 1 and 2 (finest), d1 = f1 − f0,
  d2 = f2 − f1, rho = d2/d1. The branches:
  - d1 = d2 = 0: GCI = 0.
  - |rho| ≥ 1, or d1 = 0 < |d2| (divergent or stagnant): GCI = +inf, so A4 is not met (INCONCLUSIVE, not INVALID).
  - −1 < rho < 0 (oscillatory) or 0 ≤ rho < 1/4 (p_obs > 2): GCI = 1.25 max(|d1|, |d2|).
  - 1/4 ≤ rho < 1: GCI = 1.25 |d2| / (2^p − 1), with p = min(p_obs, 1).
- **Recomputation:** new mfos.metrics functions `gci_capped`, `max_gci_capped` (A4) and `max_gci_consistency` (A3)
  recompute every GCI from the three grid values in the rows (docs/reports/metrics-o006-D0013.patch, protected path,
  applied by the founder). The rows carry the three grid values of every reported value.
- **Coverage:** A4 adds three fresh layouts, the first DRC-valid layout of each generator family from E006's sealed
  seed. They run in L2 only, at the same operating point. A3 stays on its two rule-fixed layouts, because scikit-fem is
  the expensive part.
- **Cross-check failures:** A3b moves to sanity check F5 (scikit-fem's own GCI ≤ 0.5 K on every A3 die). If it fails,
  the run is INVALID and the cross-check is refined under a new experiment id, on this Mac first. An A3-only failure
  (A1, A2 and A4 met) is INCONCLUSIVE and leads to a diagnosis of which solver is wrong and a founder decision, not an
  automatic switch.
- **F1:** in both scikit-fem agreement checks, scikit-fem's own GCI must be ≤ 0.01 K. This tightens F1; no tolerance is
  loosened.
- The objective is reviewed once more (`mfos objective review O006`) and re-approved before T0165 is released. T0165's
  brief is amended to match.

## Consequences
- O006's pass now means three things, and nothing stronger. The L2 is accurate to 1 % and 0.05 K where the exact answer
  is known (corner-free fields). It agrees with an independent FEM within their summed conservative bounds on two
  layouts. Every reported value at O003's operating point, on five layouts covering all three families, has a
  conservative GCI ≤ 0.5 K.
- O003's revision must state its Tj check with the deducted GCIs; O002 is re-derived against this precision (D0012).
- E006 gets larger: three more L2 layouts at three levels each. That is minutes per solve on this Mac, within the
  memory rule.
- The solver-side GCI helpers (thermal_layout.gci_three_grid, thermal_fem._gci) still implement the superseded rule and
  feed meta['solver_tol']. They are aligned in a later cleanup task; E006's evidence uses the mfos.metrics function.

## Alternatives considered
- 0.25 K per value (a quarter of O003's budget on the difference): the benchmark u_shaped_2 GCI is about 0.42 K at an
  85 K rise and about 0.30 K at 60 K. A likely A4 failure leads to a fallback with the same corner singularities.
- A paired-difference criterion: T0181 found difference sequences unreliable (partial cancellation of two errors with
  different rates), so it would need research first.
- Loads of 85 K or 110 K: these are stricter than the decision O006 feeds. At 110 K, u_shaped_2 is about 0.55 K.
- Keeping A3b as a criterion: a non-converged cross-check would decide against the solver under test.

## Addendum (2026-11-02, after re-reviews T0187/T0188)
Both re-reviews of the D0013 text rejected it (project/reviews/OBJ-O006/T0187.json, T0188.json). Their common blocker
was a jump in the lucky-grid branch. For a fixed coarse step d1, the GCI fell from 1.25|d1| to 0.3125|d1| at rho = 1/4,
so faster convergence got a bound four times larger. On the development data at 60 K that jump, not the discretisation
error, decided A4: side_by_side_6 die 11 came out at 0.49 K and T0181's u_shaped #B dies at 0.93 K.

Founder answers of 2026-11-02 (texts: docs/reports/o006-criteria-change-D0013-addendum.patch and
docs/reports/metrics-o006-D0013-addendum.patch):
- **Estimator:** for 0 ≤ rho < 1/4, GCI = 1.25 max(|d2|, |d1|/4), which credits order 2 from the coarser step. It is
  continuous in rho on [0, 1) and never below the order-1-capped form T0181 found conservative. On 52 development Tj max
  sequences (T0170 benchmark and T0181 pairs, scaled to a 60 K rise) the maximum is 0.306 K, against 0.932 K with the
  jump; the order-1 cap alone also gives 0.306 K.
- **A3 coverage:** A3 also runs on A4's three fresh sealed-seed layouts, so it predicts on unseen geometry in all three
  families. A scikit-fem finest-level solve takes about 2 minutes and 6.5 GB on this Mac.
- **scikit-fem z error:** scikit-fem's estimate adds 1.25 |dTj_z|, the change in each die's Tj max when every layer's
  through-thickness cell count is doubled on its level-1 lateral grid. Its benchmark refines only laterally; the
  measured z sensitivity is about 0.02 K. The evaluator adds it (mfos.metrics max_gci_consistency, ref_extra).
- **Review:** one more critic round before re-approval.

Changes made by the founder session with these answers, which follow from the re-reviews:
- dies_per_switch is written explicitly. The 30 % k variation is defined as k_max/k_min − 1 ≥ 0.30 within one layer
  (T0173). The 0.5 K is stated as a discretisation bound on generator geometry, where accuracy is checked by the
  cross-check.
- meta['solver_tol'] (thermal_layout.gci_three_grid) must compute A4's estimator before E006 registration. That way
  code_must_match carries the verified estimator to O003. Done by a builder task before T0165.
- An A2 miss confined to the manufactured case, below K2 and within that case's own GCI, goes to a founder decision on
  refinement, not straight to the fallback (T0188: a smooth-case discretisation shortfall is not a model error).
- No kill criterion on A3 (T0187 suggested one). A gross disagreement cannot tell which solver is wrong, so it stays
  INCONCLUSIVE and goes to diagnosis.
