# D0015 — O003 v3: O007/C004 is the thermal reference, the D0011 pause lifts with this revision, and eight design choices
Date: 2026-11-09 · Status: accepted · Decider: founder (founder session, 2026-11-09) · Follows: D0011, D0014 · Amends: O003 draft

## Context
- D0011 paused O003 until O006's pilots P1, P3 and P4 had reported. It also required one revision addressing draft reviews
  T0145 and T0146:
  - a planted-headroom search-power control;
  - a module-level denominator;
  - a band computable for locally processed customer layouts;
  - snapping bias in the band;
  - an empty-customer-set rule;
  - the operating point fixed per reference before any solve.
- The pilots have reported: research/notes/o006-p1-thermal-envelope.md, o006-p3-em-convergence.md (with its 2026-11-02
  addendum) and o006-p4-fasthenry-feasibility.md.
  - P4 found FastHenry not usable at module scale on the hardware agents may use.
- O006 did not pass (EV-O006-01, INCONCLUSIVE). D0014 moved the thermal reference to scikit-fem under O007.
  - O007 PASSED (EV-O007-01). Claim C004 is supported.
- C004 caveat 1: its 0.5 K bound does not carry over to new layouts. O003 must compute each layout's estimate from that
  layout's own three grids.
- C004's verified scope is the default Al2O3 DBC stack. The public fallback references (PowerSynth 2D_Case_2R and
  2D_Case_6) are AlN, and geometry/stack.py has no AlN law.
- thermal_fem.py on main changed after EV-O007-01 (commit 4a39469c). O007's decision_if_pass requires E008 to use the
  evaluated code.
- The O003 v3 draft addresses every D0011, T0145 and T0146 item and listed eight open choices (OD-1 to OD-8).
- This decision is taken before any O003 data exists. No customer layout is in the vault as of 2026-11-09.

## Decision
**Thermal reference.** O003 depends on O007 instead of O006 (D0014). Its thermal reference is C004's scikit-fem:
- src/moduleforge/solvers/thermal_fem.py;
- the GridRule of research/o007_dev3/frozen_config.json;
- levels 0-2.

**Pause.** The D0011 pause is lifted by this revision. O003 v3 goes to draft review, then to founder approval.
D0011's other rule stands: if there is no O003 verdict by 2026-11-27, it is INCONCLUSIVE.

**OD-1. Ratio-level band.**
- The band is w = 2 e_R + s_ref, where e_R is P3's estimator applied level by level to L_sub(best) / L_sub(reference).
- F1(c), w ≤ 0.05, is kept.
- Reason: with P3's measured values, the per-layout absolute estimates (about 2.5-3.7 %) would give w ≈ 0.10-0.15. F1(c)
  would then make the run INVALID with near certainty. Headroom is a ratio, and P3 recommends the ratio estimate.
- Pre-registration dev check: before E008 registration, e_R is measured on at least 4 pairs as different as real
  re-layouts (the twin against random DRC-valid candidates, on 2D_Case_4 and generator outlines). If any e_R > 0.02, the
  founder decides before registration.

**OD-2. L_term = 7 nH** for public references, and for customers who state no terminal inductance.
- Source: S3 (Chen 2013, Q3D, laminated DC terminals; research/notes/o003-public-benchmarks.md line 61).
- A PASS is reported with its sensitivity at 17.5 nH and at 0.
- Reason: it is a cited, fixed value set before data, and the smallest published terminal contribution, so a kill under it
  is robust.

**OD-3. Customer admissibility.** A customer layout is admissible only with that customer's NDA permission to run on a
VM. The permission is asked for in the same request as the layout.
- Reason: neither the 0.25 mm inductance level nor the thermal reference's level 2 fits this 16 GB machine at module scale.

**OD-4. Tj limit, two-sided interval form.** Both tests run on the same checked set, with no extra solves.
- The best candidate for h_lo is chosen by the conservative test: max_i (T_i(C) + GCI_i(C)) − max_j (T_j(R) − GCI_j(R)) ≤
  2 K.
- The best candidate for h_hi is chosen by the optimistic test: max_i (T_i(C) − GCI_i(C)) − max_j (T_j(R) + GCI_j(R)) ≤
  2 K.
- No GCI multiplier. C004 caveat 2 is disclosed with the verdict: 3 of 40 GCIs were 3-26 % short of the distance to the
  FV Richardson limit.
- Reason: the interval form is as rigorous as D0013's deduction and never looser. The optimistic kill-side test keeps
  thermal discretisation from pushing toward a kill.

**OD-5. The 60 K rule for every reference.**
- Reason: it is C004's verified load, and P1 puts it far from 175 °C. A customer's stated operating point lies outside
  what C004 sampled.

**OD-6. Thermal compute rule.**
- Thermal checks run in L_sub order over the 16-candidate inductance shortlist, in batches of 4. They stop after the first
  batch that holds a candidate meeting the conservative test, with at most 8 candidates per reference.
- Reason: it gives the same winner as a fixed top 8, at 10-18 thermal layouts (about 20-54 VM-h, $10-65) for two
  references. v2's rule could need up to 102 layouts (about 306 VM-h).

**OD-7. Validated thermal code.**
- E008 requires the thermal_fem.py bytes that EV-O007-01 evaluated (sha256 a216d5fe…). The founder reverts commit
  4a39469c.
- Every O003 extension stays out of thermal_fem.py. The AlN law goes in src/moduleforge/geometry/stack.py.
- Reason: O007's decision_if_pass requires code_must_match on that evaluation.

**OD-8. Agent budget.** budget.usd for O003 rises from 150 to 250.
- Reason: O001, O006 and O007 overran their agent budgets by 30-140 %, and O003's build is larger.

**AlN scope gap.** Before E008, two things are needed:
- an AlN k(T) law with a citation, in geometry/stack.py;
- the per-stack thermal spot check of O007's decision_if_pass and D0013 addendum 2, on at least one reference per stack
  type other than the default Al2O3 DBC. It is O007's A3 metric:
  - scikit-fem levels 0-2 against the in-house FV L2 at levels 1-3 of its frozen rule, at O003's operating point;
  - max_gci_consistency ≤ 1 on every die, with the FV estimate capped at 0.25 K.

  If the spot check fails, there is no O003 verdict (INVALID), followed by a diagnosis and a founder decision.

## Consequences
- **Build work before E008:**
  - reconstructions of 2D_Case_2R and 2D_Case_6, with their AlN thermal stacks;
  - the generalised generator, the twin and the degradation rule;
  - the search driver;
  - new protected mfos.metrics functions, headroom_median_lo and headroom_median_hi;
  - the e_R dev check;
  - the E008 design.
- **Founder actions:**
  - revert 4a39469c;
  - add E008 to policy burst_experiments;
  - apply the metrics patch;
  - ask any customer who shares a layout for VM permission in the same request.
- **Compute:**
  - thermal about 20-54 VM-h;
  - inductance about 26-150 CPU-h;
  - the spot check needs FV level 3 at about 70 GB;
  - cpu_hours 320 is unchanged.
- **Timeline:** with approval around 2026-11-12, E008 runs around 2026-11-21 to 2026-11-23, with essentially no slack.
  D0011 covers a miss.

## Alternatives considered
- **OD-1 A**, absolute-sum band 2 (e_ref + e_best): INVALID with near certainty under F1(c). Without F1(c), K1 cannot fire at
  the substrate level.
- **OD-1 C**, a FastHenry k2 burst: w would still be above 0.05 on absolute estimates.
- **OD-2**: 17.5 nH (an inference on S3's commercial module); 0 (contradicts D0011); a physical tab model (about 2-3
  agent-days, with invented geometry).
- **OD-4 A**: Tj(C) − Tj(R) + max GCI + max GCI. Looser by up to 0.11 K per layout on E009's layouts, and biased toward a
  kill when used for K1.
- **OD-6**: v2's rule (36-306 VM-h); fixed top 8 (same winner, always 18 layouts); fixed top 4 (weaker).
- **OD-7 b**: no code_must_match plus a bitwise reproduction check. This deviates from O007's decision text.
