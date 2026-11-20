# Day-60 thesis review, 2026-11-27: decision briefing

Prepared by the founder session, 2026-11-15, for the founder (handoff note step 4; plan section 1). It lists the
decisions the review must take, with the evidence on record, options and a recommendation. Recommendations are
proposals; the founder decides. On the day, `/thesis-review` writes the full report
(`docs/reports/thesis-review-2026-11-27.md`); this briefing is the agenda for it.

## Where things stand (all on record)
- **O003 has no verdict.** E010 is void: the frozen search cannot reach the 2D_Case_2R designer's level, so its
  h = 0 is not evidence of no headroom (D0023, diagnosis T0349, review T0350). By D0011, no verdict by 11-27 counts as
  INCONCLUSIVE, which triggers this review; continuing requires an explicit, recorded reason.
- **What works:** the fast inductance model ranks layouts (C002, narrowly); the thermal reference is verified (C004);
  the burst pipeline ran E010 in 6.2 VM-hours.
- **What does not exist yet:** a search that reaches the reference designer (O008, drafted and in its second draft
  review), a fast thermal model (O002), an independent inductance check on real modules (O004), any validation on
  fresh modules (O009).
- **Coverage census** (`research/notes/coverage-census.md`): 0 of 14 commercial modules confirmed representable today,
  at most 5 of 14 even if every unknown answer is favourable. The planned extensions (quarter-turned dies,
  side-by-side blocks) block no known commercial module; separate diode dies block 6 and multi-pad terminals 4.
- **A hint, not evidence:** an L1-only development probe (`research/notes/o008-control-probe.md`) found that a local
  search seeded at the twin, under each reference's own measured rules, reaches layouts 10 % (2D_Case_2R) and 37 %
  (2D_Case_4) below the twins at L1. O008's T0376 checked it with l2_layout at 0.5 mm (2026-11-16): the optimised
  layouts sit 7 % (2R, L2 ratio 0.929) and 30 % (Case 4, 0.699) below the twins. The references are development
  geometry already seen, the cells are coarser than a judged run's, and Tj was not checked, so this still cannot
  count for A-T3; it is the strongest technical signal so far that headroom exists. One limit since (2026-11-16,
  reviews T0421/T0422): the probe's 2R optimum widens the low-side die-row gap past the search domain's cap (minimum
  gap + 2 mm), so the search cannot reach it. O008's proxy, frozen inside the search's domain, is shallower: L1 ratio
  0.914 on 2R (probe 0.898) and 0.653 on Case 4 (probe 0.628). Headroom the search can find is bounded by that domain.
- **Customers:** `project/customers/` holds only its README. No customer conversation is on record, and the charter
  counts customer evidence only when it is recorded there. Outreach drafts are ready
  (`research/notes/outreach-drafts.md`).
- **Spend:** $814.83 across objectives (STATUS.md), plus session work that mfos does not record.

## Decisions

### 1. The day-45 criterion, which is unrecorded
- **Evidence.** The charter's day-45 kill line is "no customer willing to share a reference layout under NDA"
  (2026-11-12). I0140 (answered 11-11) says "No admissible customer layout by 2026-11-12". No decision record covers
  day 45: D0010 chose only the reference set for day 60. On the record, the criterion was met and not reviewed.
- **Options.** (a) Record a decision now, labelled post hoc, stating why work continued past day 45 and what binds it
  instead. (b) Treat day 45 as fired and stop.
- **Recommendation.** (a), labelled post hoc, with the day-90 line (a paid or LOI-backed sprint by 12-27, target LOI
  12-18) stated as the binding commercial test. A skeptical reading of (a) is that the kill lines are being moved;
  the decision should say so and accept it.

### 2. Day 60: continue or stop, and the recorded reason
- **Case for continuing.** The failure is diagnosed and specific: the search instrument lacks reach (T0349), not the
  physics or the thesis; the fix is scoped (O008) and testable on development geometry by 12-28, and the L1 probe
  suggests a seeded search finds what the random screen could not; the product is defined (plan, "First product"),
  and the commercial test is 30 days away.
- **Case against** (as a skeptical investor would put it). After 60 days there is no headroom evidence on any module,
  no customer conversation on record, the generator family represents at most about a third of sampled commercial
  modules, and each fix so far has exposed a deeper gap.
- **Recommendation.** Continue, with the reason recorded as: "the day-60 test could not be run with the instrument
  built (D0023); the inductance thesis is untested, not refuted; continuation is bound by the day-90 commercial line
  and by O008's stop line (one redesign, then stop inductance-search work)".

### 3. A-T3's status
- **Proposal.** "Untested, instrument insufficient (E010 void, D0023)". Not "weakened": no measurement of headroom
  exists, for or against.

### 4. The order of work (amends O003's pre-registered rule)
- **Evidence.** O003's decision_if_inconclusive says "test the current-mismatch branch of A-T3 before any further
  loop-inductance work". A current-mismatch headroom test needs the same search instrument that failed in E010, and no
  current-sharing model exists yet.
- **Recommendation.** Amend: coverage and the seeded search first (O008), current sharing reported, not gated, in O008
  and O009 (plan section 8). Record it as a decision, because O003 is frozen; the reason is the one above.

### 5. The thermal yardstick for the +2 K limit
- **Evidence.** The hottest node moves between grid levels, so O003's rule (hottest node with a three-grid estimate)
  returns an infinite estimate on real dies (D0020, T0325). The die-average temperature converges and is already
  computed.
- **Options.** (a) Die-average Tj gated, hottest node reported. (b) Hottest node gated with a different estimator,
  which needs new numerics work first. (c) Both gated.
- **Recommendation.** (a). It is the quantity datasheet thermal resistances refer to, and O002's refresh is written
  in it.

### 6. The representation route: decide earlier than 01-20 (added by the session)
- **Evidence.** The census: the two extensions the plan builds first unlock no known commercial module, and every
  extension costs about a week (T0314). The reference-native route (the search edits the imported reference's own
  copper, dies and wires, so there is no twin to construct) would cover diode dies and multi-pad terminals without new
  families. The 12-28 freeze locks whatever route O009 validates in January.
- **Options.** (a) Keep the plan: compare the routes 01-04 to 01-15 and decide 01-20, after the freeze, so O009
  validates the parametric route only. (b) Switch to reference-native now, unproven. (c) Run the route comparison in
  early December on development geometry, beside O008's core, and decide before the freeze.
- **Recommendation.** (c). It costs the comparison (plan estimate $20-30 agent) three weeks earlier and avoids freezing
  and validating a route that may be replaced.

### 7. The first product (v1) and its ship gate
- **Proposal.** Accept the plan's "First product" table: a paid re-layout sprint on a partner's module, shipping about
  02-26; gate: O008, O002 and O004 pass, O009 has a verdict, the partner's module passes the coverage screen, and die
  swap passes its control. If decision 6 picks reference-native, "passes the coverage screen" becomes "imports
  cleanly".

### 8. The coverage target
- **Proposal.** At least 80 % of census modules representable by the end of March, a committed partner's module first.
  Measure it on the census refreshed with the call answers, since most layout questions are unanswered today.

### 9. Budgets
- **Proposal.** As the plan's table, about $550-770 agent through January, set per objective: O008 $140-220 (its
  revised draft's control, 24 sealed degradations, may need $50-100 of VM against the plan's $10-25), O002 $108 left of
  $120, O004 $90 left of $100 plus $15-30 VM, O009 $80-120 plus $20-45 VM. O003's remaining $6.77 is not spent.

## Updates since the briefing was written (added by the founder session, 2026-11-19)
- **O002 passed its experiment.** E007 (480 sealed layouts, 32 per stratum, D0025/D0027) met A1-A5 with margin: A1 0.236 K
  (bound 0.263 against 0.5), A2 0.82 % (3 %), A3 0.090 K (1 K), A4 0.116 (0.5), A5 0.60 s (1 s); every null fails A1 by
  about 4 K. EV-O002-01 is PASS, and reviews T0469 and T0470 accept it with caveats. **Decision 5 now has evidence behind
  it:** each die's hottest node lies 2-5.9 K above its average in every stratum (O002 F6's trigger), so a +2 K die-average
  budget does not bound the hot spot. Claim C005 assumes decision 5 and waits for it; its final wording, with the reviews'
  limits, is drafted in `research/notes/claim-drafts/C005-statement.txt`. Two limits matter for the product: A1 holds
  pooled, not per stratum (interleaved/2 at P_ref: p95 0.503 K), and spread prediction is weak in two-die strata (A4
  0.42-0.47 per stratum).
- **O004 hit a cost wall** (decide here). FastHenry's finest level is far slower than planned: a 0.5 mm trace cell runs
  at least 5x its projection, each finest Case 4 deck about 100 h. The F7(a) burst would be about 194 h and $141 (up to
  about 2,000 h on the upper envelope), and E004 about 542 CPU-h against O004's 260; O004's agent budget is nearly spent
  ($139 of $148). F7(c) passed: burst 1 excluded none of 13 development pairs. The span cannot reach a lower end of 0.80 or
  below on Case 4; the frozen banded rule supports about 0.89. A FastHenry measurement burst (k0 and k1 on three Case 4
  layouts) has measured k1 (below). Options: a coarser FastHenry ladder (finest level 0.5 mm), a cropped
  domain, FastHenry at its two coarser levels with a wider estimate, or descoping E004's FastHenry comparison.
  - *Measurement burst, 2026-11-19 and 20* (`research/o004_f7/fh_solves`, about $6 of VM). The first run crashed every
    deck on Linux. The cause was a FastHenry bug, also behind D0002's intermittent crash, fixed by D0028 (one source fix,
    identical results). The rerun solved all six decks: k0 (1 mm trace cell) and k1 (0.5 mm) on three Case 4 layouts,
    each deck alone with the VM's memory (e2-highmem-8).

    | layout | L at k0, 10 MHz | L at k1, 10 MHz | ratio to case4_base, k0 | ratio, k1 | k1 run time, peak memory |
    |---|---|---|---|---|---|
    | case4_base | 24.302 nH | 22.949 nH | 1 | 1 | 6.3 h, 37.6 GB |
    | dev03_trace_width | 25.741 nH | 24.320 nH | 1.0592 | 1.0597 | 1.6 h, 21.3 GB |
    | standin_compound | 19.783 nH | 18.694 nH | 0.8141 | 0.8146 | 3.1 h, 24.4 GB |

    - Facts: from k0 to k1 each inductance falls 5.5-5.8 %, but each ratio moves by +0.0005 (at 20 MHz: dev03 +0.0005,
      standin +0.0011), 50-100 times less. k1 needs 21-38 GB against 11.7 GB projected, and 1.6-6.3 h; k0 needs 4.3-4.7
      GB and 1.0-1.6 h. Against the job list's projections, k1 took 0.1-0.5 times the projected time (13.7-14.5 h,
      which included the 5x factor above) and 2.3-4.2 times the raw memory estimate (about 9 GB). FastHenry uses one core
      (CPU time equals wall time), so memory, not vCPUs, limits how many decks share a VM.
    - Inference: a ladder whose finest level is 0.5 mm is affordable, and on these layouts its ratio error looks small.
      This supports the "coarser FastHenry ladder" option above. Limits: three layouts, all Case 4; two levels only, so the
      k1-to-k2 step is unmeasured and a two-level estimate assumes the step keeps shrinking; F7(a)'s thickness ladder
      (nh 3/5/9) was not run.
    - E004's FastHenry memory model and its binary pin (per platform since D0028) both change before registration.
- **O008's E011 as designed is expected to be INCONCLUSIVE** (decide here; development analysis T0471, three reviews
  accept with caveats). W* and the band bound hold at 0.25 mm (W*/W 0.938 on 2R, 0.718 on Case 4). On the development
  draws:
  - A1 = 0.25: 2R passes 2 of 8 draws, Case 4 passes 8 of 8.
  - A3 = 0: blind compaction is not beaten on 2R.
  - P(PASS) is about 0, with a 95 % upper bound of about 0.11.
  - O008 F1 requires A3 met on development rows, so E011 fails its own registration check.

  The choice: redesign before registration, or take this evidence here as a finding against the hypothesis on 2R. The
  statistics review's caveat bears on it. 2R's misses (0.2-3 points above the 2 % line) are larger than the spread inside
  any 2R shortlist (at most 0.12 points), so re-ranking the existing shortlists at L2 cannot fix 2R; a redesign would
  have to change where the search ends. If E011 is registered, the run is $65-107 of VM (53-170 h). The analysis
  recommends keeping the 2000-evaluation search budget (2R's misses are not budget-limited) and adopting the no_moves
  rule (`research/notes/e011-dev-l2-analysis.md` section 8).
- **Compute constraint.** The burst project is on the Google Cloud free trial: 16 vCPUs in all at once, not raisable without
  upgrading, which the founder will not do. Bursts run in sequence; the free-trial credit bounds the total VM spend.
- **Agent spend as of 2026-11-19** (STATUS.md): O002 $103.71 of $120, O004 $139.22 of $148, O008 $102.61 of $140 (after
  T0471); plus VM: E007 about $22, E011 development about $40, O004 bursts about $12 plus the FastHenry measurement burst
  (about $6).

## What gets recorded after the review
- The charter (founder-owned): A-T3's status; the day-45 and day-60 outcomes; any change of order of work or route.
- Decision records, drafted by the session and accepted by the founder: decisions 1, 2, 4, 5 and 6.
- `docs/reports/thesis-review-2026-11-27.md`, written by `/thesis-review`.
