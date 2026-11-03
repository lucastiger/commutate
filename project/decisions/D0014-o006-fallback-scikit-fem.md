# D0014 — O006 INCONCLUSIVE: the pre-registered fallback, scikit-fem as the thermal reference (O007)
Date: 2026-11-02 · Status: accepted · Decider: founder (I0096, founder session) · Follows: O006, D0006, D0012, D0013

## Context
- O006's single evaluation, EV-O006-01 (run E006-20261102T145940-2815, burst VM), is **INCONCLUSIVE**:
  - A1 = 0.0206 (limit 0.01), A2 = 0.143 K (limit 0.05 K), A4 = +inf (limit 0.5 K): not met;
  - A3 = 0.719 (limit 1.0): met;
  - K1 and K2 not fired;
  - no validity problems, and every metric was recomputed from the rows and matched the runner.
- An earlier run, E006-20261102T113312-b41e, was complete with every sanity check passed, but `mfos` wrote its +inf as
  null and could not read the result back. It was abandoned on the record, the defect was fixed (commit bb0725f), and
  the run was repeated under a new mint. A1-A3 matched across the two runs; A4 could not be read in the first.
- Diagnosis T0198 (reviews T0199 statistics, T0200 accept with caveats) found no implementation defect in the in-house
  L2:
  - A1/A2 miss only on the 10 mm Muzychka plates (Cases 1a and 2), because the frozen grid rule puts a fixed 2 cells in
    every layer. Quadrupling the through-thickness cells brings Case 2 to 0.010 K, and the solver converges to the
    reference at second order with a limiting bias of about 0.0002 K;
  - A4 = +inf comes from a three-grid GCI applied to bilinear interpolants at fixed off-lattice points, whose stencil
    position changes between levels non-smoothly; the field itself converges monotonically there.
- O006's pre-registered decision for INCONCLUSIVE, when neither special route applies (A3 is met, A1 and A2 are both
  missed), is "same as fail": switch the thermal reference to D0006's fallback, scikit-fem, and verify it under a new
  experiment id.

## Decision
- **Follow the pre-registered decision.** scikit-fem becomes the candidate thermal reference and is verified under a
  new objective, **O007**, and experiment **E009** (draft: docs/reports/o007-objective-draft.yaml).
- O007 keeps O006's criteria A1, A2, A4, K1 and K2 unchanged. A3 swaps the roles: the in-house L2, at its frozen rule
  exactly as evaluated, is the independent cross-check.
- O007's design avoids the two diagnosed measurement defects from the start, before any O007 data exist:
  - through-thickness cells bounded in absolute size;
  - reported point values only at nodes that persist across the three grids.
- O006 is not re-evaluated. Its evaluation stands as recorded.

## Alternatives considered
- **(b) Re-verify the in-house L2 with a corrected grid rule** (T0198 path b). The diagnosis makes it technically
  attractive. But it would replace a pre-registered decision with a rescue chosen after seeing the data. Kept as O007's
  decision_if_fail option, where it must be recorded as a post-data choice.

## Consequences
- O003 depends on O007 instead of O006, and O002's reference text points to O007. Both are drafts and are revised at
  their next draft review.
- O003's day-60 test (2026-11-27) needs O007 to pass first. If no thermal verdict exists by then, D0011 applies (no
  verdict is INCONCLUSIVE, which leads to a thesis review).
- The in-house L2 stays useful as a fast, cross-checked secondary solver, never as the judge, unless a later objective
  verifies it.
