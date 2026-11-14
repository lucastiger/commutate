# D0021 — E008 cannot search 2D_Case_2R as registered; O003 moves to a successor experiment E009 with a repaired generator sampler (declared F3 deviation)
Date: 2026-11-14 · Status: accepted · Decider: founder (founder session, 2026-11-14) · Relates to: D0018, D0019, D0020; E008, T0329; run E008-20261114T095904-2c22

## Context
- The first registered E008 run (founder's VM mf-e008-1794679144, 2026-11-14, phase A) ended with runner exit 1 after
  1011 s; result status `error`, no metrics (committed c6aa4334). 2D_Case_6 was excluded by TwinError as the spec expects
  (F1(a)). On 2D_Case_2R the main and control screens raised "no DRC-valid candidate in 20000 consecutive draws"
  (derivative.py:888); the scheduler re-raised it and aborted the run.
- Founder-session diagnosis (generator/DRC only, unsealed seeds, after E008's registration; no L1, L2, EM, thermal or
  search; no solve values read): 0 DRC-clean in 312 000 draws. The 2R reference and its twin are DRC-clean and
  `build(spec, params_of(twin))` is DRC-clean, but `derivative._sample` places the four slots in ONE free vertical
  window; on 2R (orientation 0) the windows are (7, 23) and (39, 53) mm and the twin's stack spans 7..51 mm across an
  obstruction. The reference's own topology is outside the sampler's support. Class implementation, confidence ~85 %.
- E008's config.freeze (F3) pins src/moduleforge/generate/derivative.py (a93effe5...); "a change voids the run". The
  registered E008 cannot produce a verdict. O003's evaluation (max 1) is unused (error runs are not selected, INVALID
  evaluations are not counted).
- O003 names E008 in evidence_plan, required_experiments and the A1/K1 metric names (frozen fields), and its failure
  mode F3 requires the generator to be developed only on the generator's own layouts and 2D_Case_4 and frozen before any
  judged reference is loaded.

## Decision
1. **E008 is closed as not runnable.** Its run E008-20261114T095904-2c22 stays on record (status error). T0329 is
   cancelled and I0196 answered with this decision. E008's spec is not changed.
2. **Successor E009 = E008 with three changes only:** (a) the generator sampler can place a slot stack across more than
   one free window (gaps straddling an obstruction, slots narrower than the band where the free region requires it);
   (b) a reference whose main or control search cannot draw a DRC-valid candidate within the draw limit is excluded and
   reported (reason SearchInfeasible), like a TwinError, instead of aborting the run; E009 is INVALID only if no
   reference remains; (c) new freeze hashes. Unchanged: O003's thresholds, comparators and max_evaluations; D0019's
   reference set; D0020's Tj rule and readings; the twin construction (twin.py), degradation rule, search driver,
   budgets, bands, cost model. 2D_Case_6 is still expected to be excluded (TwinError; twin.py unchanged).
3. **Dev streams unchanged.** The sampler change must leave the sealed candidate stream of every development
   reference byte-identical (fingerprints), so E008's development rows and checks carry over to E009 with no re-solve.
   If that proves impossible, the work stops and the founder decides.
4. **Declared deviation from O003 F3.** The generator is changed after 2D_Case_2R was loaded. Limits:
   - the fix is developed on the generator's own layouts, 2D_Case_4 and synthetic housings with a split free region;
   - before E009 is registered, 2D_Case_2R and 2D_Case_6 may be used only for generator/DRC feasibility: reference
     reconstruction by the frozen T0263 script, spec_from_layout, twin() geometry fit, derivative sampling/build and
     drc.check (acceptance test: the 2R twin's parameters lie in the sampler's support, and generate() draws DRC-valid
     2R candidates). No L1, l2_layout, EM, thermal, FV, degrade() or search run on them;
   - no one reads the EM solve values of run E008-20261114T095904-2c22, or any L_sub or Tj of 2R or 6, before E009 is
     registered; E009 reuses no E008 run data (fresh mint, fresh solves).
5. **O003 v6.** evidence_plan, required_experiments and the A1/K1 metric names change from E008 to E009, and F3's text
   names E009's spec; nothing else changes. The founder re-approves O003 before E009 is registered.
6. **Budget.** O003 has $16.51 left; the fix, the E009 design and their reviews are estimated at about $13. The founder
   requests a $15 margin above the current $250 cap for one rework cycle (budget_increase item, approved at a terminal
   with note usd=31.5, giving a cap of about $265). VM run: as planned for E008 (expected $22.44, upper $26.14).
7. **Order.** The generator fix (one task) first; then the E009 design (depends on it); then O003 v6 and its
   re-approval; then E009's registration and the VM run. Founder choices in session, 2026-11-14: successor experiment;
   DRC-only 2R/6 feasibility check allowed (item 4); +$15 budget; this record accepted as drafted.

## Consequences
- The O003 verdict moves from E008 to E009; the deadline (run by about 2026-11-24) still holds.
- The sampler support grows for every housing whose free region is split; the dev-stream identity check (item 3) shows
  it does not move any development result.

## Alternatives considered
- Rerun E008 with more draws or another seed: rejected (0 of 312 000; the twin is outside the support).
- Stop and review O003 before more spend: not chosen by the founder (2026-11-14).
- Fix the sampler without any 2R check before registration: cleaner under F3 but risks a second failed VM run.
