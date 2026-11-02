# D0012 — O006 A3/A4 restated: conservative 0.5 K bounds with an order-capped estimator (decided after data)
Date: 2026-11-02 · Status: accepted · Decider: founder (founder session, 2026-11-02) · Amends: O006 acceptance criteria

## Context
O006 was approved with A3 (L2 vs scikit-fem within 0.05 K, scikit-fem's own GCI at most 0.025 K) and A4 (every reported L2
value with a grid convergence index of at most 0.025 K; Fs = 1.25, p = min(p_obs, 2) inside p_obs in [1.5, 2.5], else
Fs = 3, p = 2). Before E006 was designed or registered, and before any evaluation was spent:
- T0170 refined the grid rule and found 0.025 K unreachable: about 460 M to 5 G cells would be needed, because the
  die-attach-on-copper corner (temperature ~ r^0.84) caps the observed order near 1.2-1.5 (benchmark on the A3 layouts:
  0.168 and 0.334 K).
- Reviews T0178/T0179 found the frozen estimator not conservative at low observed order (GCI = |f2 - f1| below p_obs 1.5,
  which understates the Richardson error when p_obs < 1).
- T0181 (development seeds only) measured absolute Tj max GCIs of 0.06-0.33 K on 9 layouts at the finest level that fits
  in 16 GB, and showed on three 2D corner cases against a 21 M-cell reference that the frozen rule and the proposed
  candidate rule both understate the true error at the singular corners (4-5 of 24 values), while GCI = 1.25 |f2 - f1|
  with the order capped at 1 bounded the true error in all 24 values (margin typically 2-3x). The founder session
  computed these verdicts from T0181's committed results (research/o006_gci/results.json); they are analysis, not evidence.

**This change is made after seeing data.** It is justified by (a) a defect in the estimator as originally specified,
shown on cases with a known true error, and (b) a threshold derivation that was stricter than any decision required:
0.025 K came from "half of O002's 0.05 K per-Tj allowance", but the decision that consumes O006 first is O003's +2 K Tj
limit at day 60. The thresholds below are derived from that decision, not from the measured values.

## Decision
- **A4:** every reported L2 value has GCI = 1.25 |f2 - f1| / (2^p - 1), p = min(p_obs, 1) for monotone sequences, and
  1.25 max(|f2 - f1|, |f1 - f0|) for oscillatory or non-monotone ones, of **at most 0.5 K**: a quarter of O003's +2 K budget.
- **A3:** for every die of the two A3 layouts, |Tj_L2 - Tj_skfem| is at most GCI_L2 + GCI_skfem (the two independent
  solvers agree within their combined conservative estimates), and **A3b:** scikit-fem's own GCI is at most 0.5 K.
- A1, A2, K1 and K2 (the analytic and manufactured references) are unchanged.
- Recomputation uses existing mfos.metrics functions (max_col, max_scaled_abs_err): no protected code changes.
- The objective is re-reviewed by critics and re-approved by the founder before T0165 (E006 design) is released.

## Consequences
- O006 can pass with the reference accuracy this Mac can actually deliver (about 0.1-0.5 K on absolute Tj).
- **O002 must be re-derived**: its draft A2 (0.5 K on pair differences) cannot be verified against a reference whose
  conservative difference bound is GCI_A + GCI_B = 0.14-0.63 K (T0181). O002 is still a draft, so nothing frozen changes.
- O003 uses the verified thermal L2 for its +2 K check with a 0.5 K reference bound.

## Alternatives considered
- (a) Keep A3/A4 as frozen: E006 would spend O006's single evaluation on a certain failure, and the fallback
  (scikit-fem) faces the same corner singularity.
- (b) A different discretisation near the corners (local refinement, singular enrichment) to reach 0.025 K: weeks of
  research on the critical path, for a precision no current decision needs.
- (c) Threshold 1.0 K with Fs = 3: passes more easily but leaves O003's +2 K check with a reference error of half its budget.
