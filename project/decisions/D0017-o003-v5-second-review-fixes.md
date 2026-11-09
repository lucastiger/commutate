# D0017 — O003 v5: fixes for second-round reviews T0253/T0254 (inductance-only kill side, search levelling, bondability)
Date: 2026-11-09 · Status: accepted · Decider: founder (founder session, 2026-11-09) · Follows: D0016 · Amends: O003 draft

## Context
O003 v4 (commit 1a39aa3b, D0016) went to its second round of draft review, and both reviews accepted it with caveats. This
decision is taken before any O003 data exists. The founder still approves the whole objective afterwards.

**T0253 (statistics):**
- **Major 1.** The planted control only shows that the search reaches the twin. On the repository generator, random search
  had not levelled off at 20,000: the expected best of 5,000 is 1.45 % above the best of 20,000.
- **Major 2.** The h_hi = +inf rule blocks a kill even when the inductance-only best already lies in the null region.
- **Minors:**
  - the kill side takes its band from a single candidate;
  - the twin gate has no absolute cap;
  - a kill carries no L_term sensitivity.
- **Notes:**
  - the twin gates can shrink the counted set to one reference;
  - the "conservative" Tj test is not strictly conservative.

**T0254 (physics):**
- **Major 1.** K1 rests on a lower bound, the Tj-checked candidate, where the claim needs an upper bound.
- **Major 2.** No rule keeps dies wire-bondable to the fixed gate and Kelvin copper.
- **Minors:**
  - the twin and +inf rules conflict when the twin beats every checked candidate;
  - the twin-gate tolerances are discretisation-only;
  - trace width ignores nets;
  - a kill depends on the 7 nH L_term.
- **Note:** say what F1(b) actually certifies.

## Decision
1. **Kill side uses the inductance-only best.** h_hi = a (1 − r_ind (1 − w_ind)), where r_ind = L_sub(inductance-only best)
   / L_sub(twin) and w_ind = 2 e_R + s_ref for that pair. The inductance-only best is the lowest-L_sub candidate of the
   16-candidate shortlist, with no Tj limit. K1 fires if the maximum over counted references of h_hi < 0.10. The metric is
   now headroom_max_hi_ind.
   - This replaces D0016's optimistic-test h_hi and its +inf rule.
   - The Tj-checked candidates (conservative test) decide A1 only. The optimistic test is kept as a reported secondary
     column.
   - Reason: no Tj-feasible candidate of the search can beat it, so within the search's reach it is an upper bound on the
     Tj-constrained headroom. That is what a kill needs.
2. **Search levelling.** A reference counts toward K1 only if the lowest L1 among the first 5,000 candidates of its sealed
   sequence is at most (1 + w_ind) times the lowest L1 among all 20,000. Otherwise its h_hi = +inf, and it is INCONCLUSIVE
   for that reference.
   - A kill means "not found by this search (D0008 budget)". F1(b) certifies only that a new-seed inductance-only search
     reaches the twin's level.
   - Reason: random search may still be improving at 20,000 (T0253). This check is the cheapest one that does not add a
     search.
3. **Near ties.** e_R is computed for every shortlisted candidate whose L_sub is within (1 + w_ind) of the inductance-only
   best. The largest h_hi among them is used.
   - Reason: D0009 kills on the band's upper end, and a near-tie candidate with a wider band can have a higher one.
4. **Bondability.** Each die's gate pad must lie within the reference's longest gate-wire length of the fixed gate copper,
   and its Kelvin pad within the reference's longest Kelvin-wire length of the Kelvin copper. Both lengths are measured on
   the snapped reconstruction. No gate or Kelvin wire may cross a wire of another net in plan view.
   - Build: added to the DRC and the generator.
   - Reason: headroom from dies that cannot be gated is an artifact.
5. **Power-net trace width.** DC+, phase and DC- copper must be at least the reference's own minimum power-net width.
   Other nets keep the reference's smallest width.
   - Reason: necking power copper is a rule artifact, like the spacing case D0016 fixed.
6. **L_term sensitivity on kills.** Every kill is reported with h_hi at L_term = 0. A kill that disappears at L_term = 0 is
   labelled "dependent on the assumed terminal inductance".
   - Reason: a smaller terminal makes a kill harder, and 7 nH comes from another module (CPES).
7. **Twin gates.** The gates are unchanged. Before registration, the frozen twin of 2D_Case_4 is built and both gates are
   run on it as dev rows; if either fails, the founder decides. The reconstruction-based h_lo is reported beside every
   PASS as a stated limit.
   - Reason: this tests the discretisation-only tolerances before they can exclude references, and shows the gap to the
     real reference without an arbitrary cap.
8. **Counted references.** The verdict states the number of counted references (admissible, and passing both twin gates).
   A PASS on a single counted reference goes to the founder review before decision_if_pass applies. A kill already leads
   to a founder thesis review.
   - Checked against D0010: no contradiction. D0010 selects the reference set ("one or more" customer layouts) and leaves
     the day-60 verdict to the founder (D0009). This rule changes neither the set nor the verdict, only how a
     one-reference PASS is acted on.
9. **Wording.**
   - The twin rule is stated once, in A1, for A1 and K1, and is applied before any candidate-selection rule (the near-tie
     rule included).
   - The levelling condition is checked before the twin rule, because it decides whether a reference's search may support
     a kill at all. Otherwise a search that had not levelled off and could not beat the twin would support a kill.
   - The conservative Tj test is disclosed as not strictly conservative (≤ about 0.1 K).

## Consequences
- **Inductance compute.** Each near-tie candidate gets the four 0.5 mm band solves. Few are expected, since w_ind is
  small; the set is empty when s_ref = 0 and the twin is the inductance-only best.
- **Thermal compute** is unchanged from D0016.
- **Dev check** on 2D_Case_4: its reconstruction and twin, thermal and inductance. Roughly 10-20 VM-h [estimate].
- **Build additions:**
  - per-net-class width;
  - gate and Kelvin bondability in DesignRules, the DRC and the generator, which today draws no gate wires;
  - the levelling record in the search driver;
  - headroom_max_hi_ind, with unit tests of the rule order (protected path).
- **Outcomes.** A kill now needs, on every counted reference, a levelled search whose inductance-only best leaves less than
  10 %. It can fire where D0016's +inf rule blocked it, but not on a non-levelled search. INCONCLUSIVE stays the likely
  outcome (2026-11-27 thesis review, D0010 and D0011).

## Alternatives considered
- **Keep D0016's +inf rule and add a min with the inductance-only h_hi (T0253):** the inductance-only bound alone is
  simpler and is the actual upper bound.
- **A larger-budget search instead of a levelling check (T0253):** more compute and build on the critical path.
- **An absolute cap on the twin gate (T0253):** an arbitrary number. Reporting the reconstruction-based h_lo beside every
  PASS makes the gap visible instead.
- **A Tj-aware screen or control (T0251, T0252, T0254):** rejected in D0016 and still rejected. With the kill on the
  inductance-only best, it is no longer needed for the kill side.
