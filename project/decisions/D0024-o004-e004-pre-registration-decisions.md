# D0024 — O004 before E004's registration: F1's caps are relative to the ratio; the 0.7616 compound stands in for "r <= 0.75"; the 2R proxy pair at 1 mm against the reconstruction; compounds under the stagewise rule; development geometry under F2. The span and allocation stay open
Date: 2026-11-17 · Status: accepted (drafted by the founder session; accepted as drafted) · Decider: founder · Relates to: O004 (F1, F2, F4, F7), I0207, I0217, D0002; T0386, T0387, T0388, T0429, T0433, T0440, T0441

## Context
- These decisions were taken in founder sessions on 2026-11-16 and 2026-11-17 and recorded in O004's state log and in
  task briefs. Blinded reviewers do not see the state log, and review T0440 could not find them, so they are recorded
  here for E004's spec to cite.
- Facts they rest on:
  - T0386 and T0387 (span_reach.json): the frozen rules, compounds included, reach no 2D_Case_4 pair with r <= 0.75 at
    L1. The lowest found is a three-move compound at r = 0.7616 at 20 MHz (0.7613 at 10 MHz), and only from T0386's
    pinned start. Single moves bottom out at 0.873 (a die-row shift). On gen2_0 the lowest is 0.888.
  - T0387: L1 overstates large effects. The 0.7616 pair is 0.807 at l2_layout 0.5 mm, and l2_layout 0.5 mm minus L1
    ranges from -0.017 to +0.046 over the 11 Case 4 development pairs.
  - T0388 (research/o004_e004/span_sim_case4.json, recounted by T0440 and T0441): with the frozen allocation (one
    pair of each single move type plus 2 compounds per reference), no draw meets F4's span. That is 0 of 400
    single-reference draws and 0 of 200 pooled, at any lower end from 0.75 to 0.85, and 1 of 200 pooled at 0.85. The
    binding term is "at least 3 below 0.90". Per draw, the count below 0.90 is 0 in 315 draws, 1 in 78 and 2 in 7.

## Decision
1. **F1's caps are relative to the ratio** (2026-11-17 01:41 UTC; review T0429 finding 6). A counted pair needs
   E_R / r <= 0.5 % for l2_layout and E_R / r <= 1 % for FastHenry. E_R is the gci_step_floor estimate of the
   three-level ratio sequence, in ratio units, and r is the finest ratio. This reads O004's "at most 0.5 % / 1 %" the
   way A1 (|r_L2 / r_FH - 1|) and the step floor ("0.1 % of a ratio") are written; no threshold changes. It was decided
   before any F7(c) burst result existed.
2. **The stand-in for "the pair with r <= 0.75"** (2026-11-16, on T0386's partial result). Wherever F7(a)/(c) or a
   brief names that pair, the lowest compound found is used instead, labelled "lowest reachable, r = 0.7616, stands in
   for r <= 0.75". It is the lowest found by a start-dependent search, not a proven floor (T0429).
3. **The 2D_Case_2R designer-proxy pair** (I0207, answered (b)+(c)). O004 runs O008's proxy descent in 1 mm steps, so
   the result is on the 1 mm lattice by construction, and takes the pair's ratio against the frozen 2R
   reconstruction, as O004 defines r. E004's spec carries a declared scope note: this is not exactly O008's 0.5 mm rule.
4. **Compound re-layouts** (I0217). Compounds of two or three of the four frozen move types are allowed, to widen
   the span. Single moves keep per-type coverage. If r <= 0.75 is still unreachable, that is reported and the span is
   not changed on that account.
   - The stagewise rule (2026-11-16 17:55 UTC): every step of a compound is DRC-clean, not only the final layout, and
     E004's frozen rule text states it.
5. **Development geometry under F2** (2026-11-16 17:55 UTC correction). Span-reach, rule-range and pilot work use
   2D_Case_4, gen2_0 and development seeds only. Nothing is drawn, and no inductance is computed, on 2D_Case_2R or
   2D_Case_6 before registration, except F7(b)'s l2_layout 0.25 mm solve of 2D_Case_6's reconstruction, which F7 names.

## Open, not decided here
- **The span's lower end and the allocation.** As drafted, F4 would refuse a sealed registration almost surely, and a
  refused sealed run stays on the record. Lowering the lower end alone does not help. The options are:
  - (a) a frozen acceptance rule inside the sealed stream that fills L1-ratio bands. L1 is not the tool under test, and
    every pair stays drawn from the sealed seed (F2).
  - (b) more compound slots.
  - (c) relaxing "at least 3 below 0.90".

  The founder decides after burst 1's F7(c) results (I0209), because F1 exclusions of the large-effect pairs bear on
  the same choice. The decision is recorded as an amendment of this record before registration.

## Consequences
- E004's spec cites D0024 for items 1-5. Its registration check keeps O004's span text until the open item is decided.
- T0387's pilot_l2.py, written before item 1, used the absolute reading. It is corrected before burst 1's results are
  assembled.
