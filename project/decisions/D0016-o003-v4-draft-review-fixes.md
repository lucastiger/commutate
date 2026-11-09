# D0016 — O003 v4: fixes for draft reviews T0251/T0252 (Tj-blind kill, per-reference aggregation, twin as comparator)
Date: 2026-11-09 · Status: accepted · Decider: founder (founder session, 2026-11-09) · Follows: D0015 · Amends: O003 draft

## Context
O003 v3 (commit 0d892224, decisions D0015) went to draft review, and both reviews rejected it. This decision is taken
before any O003 data exists. The founder still approves the whole objective afterwards.

**T0251 (statistics):**
- **Blocker.** K1 can fire because the shortlist ignores Tj. When none of the at most 8 lowest-L_sub candidates passes the
  optimistic test, the rule set r = 1 and h_hi = a·s_ref ≤ 0.05, which is a kill. On the project's own generator, the
  lowest-inductance arrangement runs 2-10 K hotter across families: in 48 of 81 cross-family cases the lowest-L candidate
  with ≥ 20 % headroom is more than 2 K hotter.
- **Major.** With n = 1-2, the median is the mean. A PASS can include a reference in the null region, for example h_lo =
  0.40 and 0.01.
- **Major.** The generator-versus-reconstruction offset that the twin gate allows (up to about 0.05) is neither in w nor
  deducted.
- **Minor.** The declared twin null cannot meet A1, so it checks nothing.

**T0252 (physics):**
- **Blocker.** The same Tj-blind kill. A Fourier-series check gives about 2 K per mm of die compaction on the default stack
  and 4-6 K per mm on an AlN/1 mm stack.
- **Major.** The generator-versus-reconstruction thermal offset is not gated.
- **Major.** The single net-agnostic spacing rule lets DC+/phase/DC- gaps shrink to the reference's smallest gap, often a
  gate or Kelvin gap. Die spacing and edge margins are not tied to the reference.
- **Minor.** s_ref can be 0 while edges have moved by up to 0.125 mm.
- **Minor.** The best = reference case has two definitions of h.

## Decision
1. **No Tj-blind kill.** A reference for which no thermally checked candidate passes the optimistic Tj test has h_hi =
   +inf, reported with n_tj_rejected. A kill therefore requires, on every counted reference, a candidate that is
   Tj-feasible under the optimistic test.
   - The conservative side is unchanged: best = the reference, r = 1.
   - No Tj-aware screen or new control is added.
   - Reason: an inductance-ranked shortlist whose checked candidates are all too hot shows nothing about headroom at
     ≤ +2 K. This removes the kill path without adding build work.
2. **Per-reference aggregation.** A1 needs the minimum over references of h_lo ≥ 0.20 (metric headroom_min_lo). K1 fires
   only if the maximum over references of h_hi < 0.10 (metric headroom_max_hi). Anything else is INCONCLUSIVE. The
   thresholds are unchanged.
   - Reason: the band covers discretisation only, with no between-reference sampling term, so a verdict on "reference
     layouts" must hold for each one.
   - This equals D0009/D0010's median for n = 1, and is stricter in both directions for n = 2-3. Every PASS or kill here
     is also one under the median rule. Disagreeing references go to the D0010 thesis review.
3. **Twin as comparator.** r = L_sub(best) / L_sub(twin), and the Tj tests use the twin's per-die Tj and GCI. A thermal twin
   gate is added beside the inductance gate: |max Tj(twin) − max Tj(reconstruction)| ≤ G(twin) + G(reconstruction), each
   G the largest per-die gci_capped from its own three grids.
   - A reference failing either gate is excluded and reported.
   - The reconstruction-based ratio and Tj differences are secondary columns.
   - The twin's thermal solve is now required: one more thermal layout per reference.
   - Reason: generator and reconstruction representations differ systematically. Comparing like with like removes the
     offset from both the headroom and the feasible set.
4. **Spacing per power-net pair.** Minimum spacing for DC+/phase, phase/DC- and DC+/DC- comes from the reference's own
   minimum gap for that pair. Other pairs keep the reference's smallest gap. Die spacing, die-to-copper-edge and
   copper-to-substrate-edge margins are at least the reference's.
   - Build: per-net-pair spacing in DesignRules and the DRC, honoured by the generator.
   - Reason: headroom bought by narrowing high-voltage gaps is a rule artifact.
5. **Snapping check before registration.** For each off-grid reference, compare L_sub of the 0.5 mm-snapped reference
   with the 0.125 mm-snapped reference. If the difference exceeds s_ref, s_ref is replaced by it.
   - Both solves are at 0.125 mm cells, because l2_layout cannot mesh off-lattice geometry at 0.25 mm.
   - Reason: s_ref alone is not a bound (T0252).
   - Feasibility: a 0.125 mm solve needs about 35 GB at generator size and did not finish in 8.7 h at 2D_Case_4 size (P3
     addendum). If the check cannot be completed for a reference, this is reported to the founder before registration.
6. **best = reference.** When best is the reference (its twin), r = 1 and h_lo and h_hi follow the formula, apart from
   rule 1's h_hi = +inf.
   - Reason: one definition for the protected metric.
7. **L1-only null (reported, not gated).** The headroom of the best Tj-feasible candidate of a search without the
   16-candidate l2_layout re-rank. It uses the same top 16 by L1, thermal checks in L1 order under the same batch-and-stop
   rule, and reuses existing thermal results.
   - Expected at or below the full search's headroom.
   - Reason: it is an informative null in place of the formal twin null, without making a genuine headroom finding
     non_discriminating.

## Consequences
- **Thermal compute.** Per reference: the reconstruction, the twin and 4-8 candidates, which is 12-20 layouts for two
  references.
  - At 2-3 h each: 24-60 VM-h, $12-72 at $0.5-1.2/h.
  - At E009's n2-highmem-32 speed: about 4-17 VM-h.
  - The L1-only null adds at most 8 layouts per reference, usually few.
  - cpu_hours 320 still covers the worst case, narrowly.
- **Build additions:**
  - DesignRules/DRC per-net-pair spacing and the reference-derived die and edge margins;
  - the L1-only null in the search driver;
  - the twin-based, min/max metrics headroom_min_lo and headroom_max_hi (protected path);
  - the snapping check.
- **Outcomes.** A kill is now harder: it needs every reference in the null region with a Tj-feasible candidate. PASS is
  also harder: it needs every reference above 0.20. INCONCLUSIVE leads to the 2026-11-27 thesis review (D0010, D0011).

## Alternatives considered
- **A Tj-aware screen or a Tj-constrained planted control (T0251, T0252):** more search power under the Tj limit, but new
  build work on the critical path, and no L1 thermal model exists (O002).
- **Adding |1 − L(twin)/L(reference)| to w instead of the twin denominator (T0251):** it widens a band that F1(c) caps at
  0.05, and does nothing for the thermal offset.
- **Keeping the median and reporting per-reference values only (T0251):** it leaves PASS possible with one reference in
  the null region.
