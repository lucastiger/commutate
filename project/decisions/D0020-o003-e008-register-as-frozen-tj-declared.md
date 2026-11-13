# D0020 — E008 is registered with O003's frozen Tj definition; A1 is declared expected-unreachable on 2D_Case_2R; the remaining registration readings are settled
Date: 2026-11-13 · Status: accepted · Decider: founder (founder session, 2026-11-13) · Relates to: D0013, D0018, D0019; E008, T0324, T0325

## Context
- The full-fidelity development run of E008 (founder's VM, 2026-11-13; rows rebuilt by T0324) found, on the development
  layout 2D_Case_4, that the frozen thermal rule gives every die of the reference and the twin a non-monotone Tj max over
  levels 0-2, so `mfos.metrics.gci_capped` is +inf on every die. On gen2_0 (generator housing, default stack) the
  conservative +2 K test was reachable.
- T0325 diagnosed it on development geometry only (research/diagnoses/T0325.md) and its level-2 launcher ran on the
  founder's VM (2026-11-13; 15 of 15 solves ok; V0 reproduces the dev run). Result: in-plane hot-spot migration (T0325's
  H3). The hottest node is the die centre at levels 0 and 1 and moves one level-2 cell at level 2 (+0.15 K), so the
  second step is about twice the first (rho about -1.6 to -2.9) and the rule returns +inf. The die-centre node and the
  die-top mean converge. The stack does not matter: without the 1 um solder layer the values change by at most 0.012 K,
  and V4, which is 2D_Case_2R's recorded stack recipe on Case 4's geometry, is +inf on every die.
- Inference (2D_Case_2R is not solved before the freeze, D0019 item 4): 2R carries the same 4 x 6 mm die footprint and
  that stack, so its twin and its candidates are expected to get +inf on every die. Then no candidate meets the
  conservative +2 K test, best = twin and h_lo = -a s_ref: A1 is expected to be unreachable on 2R. gen2_0's dev search
  did not level off (first-5,000 L1 minimum 9.3 % above the 20,000 minimum, window 3.75 %); if 2R's does not either, K1
  is unavailable for it.
- O003 defines Tj as the maximum nodal value on the die top face, with the three-level `gci_capped` estimate (D0013).
  Changing that definition would be an objective amendment made after development results.

## Decision
1. **Register as frozen.** E008 keeps O003's Tj definition and every gated criterion. Its spec states, before
   registration, the expected outcome: on 2D_Case_2R, A1 is expected to be unreachable (T0325, by inference); the expected
   verdict is INCONCLUSIVE unless 2R's search levels off and K1 fires; 2R's inductance-only headroom (h_hi_ind and its
   columns) is measured and reported either way.
2. **Reported, not gated: die-average Tj.** E008 adds, per die and level, the area-weighted mean temperature of the die top
   face (the virtual junction temperature that datasheet thermal resistances refer to), its `gci_capped` estimate, and per
   reference the conservative-test analogue on that quantity for the thermally checked candidates. It decides nothing.
3. **Band check (I0184 option 1).** 2D_Case_4's 4 twin-versus-random pairs (e_R 0.00956, 0.01254, 0.00635, 0.01785; max
   0.01785 < 0.02) together with gen2_0's search estimate (e_R about 0.019 for its A1 best) are the pre-registration band
   check. gen2_0's 4 random pairs were not solved (the VM run crashed before them). The closeness to 0.02 is recorded as a
   risk to F1(c).
4. **Readings confirmed as implemented:**
   - row-contract interpretations 1-9 (research/o003/e008_row_contract.md section 5); under item 1, 2R's thermal twin gate
     F1(a2) is expected to pass only because both G are +inf;
   - judged references use `measure_rules` less `min_signal_wire_length`, with no override (D0019 item 5);
   - the 320 cpu_hours cap is read as billed vCPU-hours (expected 97.0, upper 145.4);
   - an all-inadmissible non-default stack type is reported, not gated (F6(e));
   - the stack-type rounding rule as implemented (integer nanometres, 9 significant digits);
   - `quick_ok_draws` stays a fixed 2,000 draws (false-rejection bound: gen2_0 3.0 %, 2D_Case_4 8.7 %).
5. Registration: the founder approves the register-E008 inbox item filed after the spec records this decision; the earlier
   register items are superseded.

## Consequences
- E008 can still deliver its central measurement on 2R: the reference solver's inductance headroom, with the
  reconstruction-based and L_term = 0 columns, plus the die-average thermal comparison as a reported fact.
- A formal PASS of O003 on D0019's set is not expected from E008. A thermal measure that converges for centre hot spots
  (die-average Tj, a fourth level, or die-interior grading) is a candidate for a later objective or experiment, decided
  after day 60.

## Alternatives considered
- Amend O003 to judge the +2 K limit on die-average Tj before registration: gives E008 a chance to PASS, but changes the
  hypothesis after development results, needs an objective amendment and a protected metrics change, costs 2-4 days and
  $10-15, and squeezes the 2026-11-22 start.
- Skip E008 before day 60 (D0011: INCONCLUSIVE with no measurement).
