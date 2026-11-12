# D0018 — E008's degraded copy is a yardstick, not a candidate; a reference without a valid degraded copy is excluded; the model-fix list before the reference screen
Date: 2026-11-12 · Status: accepted · Decider: founder (founder session, 2026-11-12) · Settles: E008 draft, founder
decision before registration "D below 1.25 L_sub(twin) ... or DegradeError"

## Context
O003's planted-headroom control F1(b) degrades the twin W into a copy D with L_sub(D) >= 1.25 L_sub(twin) and gives D
to the frozen search with a new seed. The control must get back to the twin's level. T0314 (research/notes/o003-twin-coverage.md,
review T0315) found that on 2D_Case_4, a development layout, degrade() raises DegradeError. The cause is O003's rule
that power-net copper be at least as wide as the reference's own narrowest power copper, 5 mm on Case 4. The twin's
landing bands are already at that width, so the main degradation move (narrowing them) cannot act. Two prototype
degradation rules reached L1 ratios of 1.260 and 1.240, against a target of 1.388. Relaxing this one rule alone gives
1.421. A well-designed judged module could hit the same wall. Under E008's current implied reading, that makes E008
INVALID.

The control search builds its candidates from the reference's own spec and rules (`search.run_control` → `_screen(spec,
...)`). D enters only as the yardstick: L_sub(D), D's band solves, and w_ctrl = 2 e_R(control best, D). What F1(b)
certifies is that the search reaches the twin's level (O003 notes, T0253), not that D is buildable. F1(b) requires
L_sub(D) >= 1.25 L_sub(twin); it does not require D to meet the candidate design rules.

## Decision
1. **D is a yardstick.** When E008's degradation rule builds D, it may make D's power-net copper (DC+, PHASE, DC-)
   narrower than the reference's own minimum power-net width, down to a floor that E008's spec states and freezes. The
   floor is at least the generator's default minimum width (1 mm). It must also be wide enough that D's band solves
   resolve the strip, so that narrowing does not inflate e_R and with it w_ctrl. The implementing task sets the floor
   from evidence on generator layouts and 2D_Case_4. Every other rule applies to D unchanged. The main and control
   searches keep every O003 scope_in rule for their candidates.
2. **Fallback: exclusion.** If, under (1), no D meets F1(b)'s definition for a reference, that reference is excluded
   and reported with the reason, as for a twin-gate failure. This covers two cases: degrade() raises DegradeError, or
   L_sub(D) / L_sub(twin) is below 1.25 at the conservative end of its band. E008 is INVALID only if no reference
   remains. A control that runs and misses h_plant - w_ctrl is still an experimental failure (INVALID), as O003's F1
   response says. This reads "no valid D can be made" as F1(b) not being runnable for that reference, not as F1(b)
   failing, the reading E008's draft already offered as its alternative. A DegradeError or TwinError stops that
   reference, not the run, which settles the conflicting wording in E008.yaml (`fail_fast_twin_and_D`).

## Consequences
- An E008 runner and spec change before registration; the frozen generator, twin, search and rules code is unchanged.
- The control's leniency is the risk to watch. Narrow strips in D could widen e_R(best, D), and with it w_ctrl, making
  the control easier to pass. The floor in (1) exists for this. The implementing task reports the cell count across
  D's narrowest strip at the band-solve and 0.25 mm cell sizes, and the evidence for its floor.
- The L1 screen's margin (0.11) was derived on generator layouts. On Case 4 with 1 mm strips, the L1 ratio was 1.421
  against an L2 ratio of 1.325 (T0291, twin.py docstring): still above 1.25, but the L1 bias lay outside the band the
  margin assumes. E008's L2 check of every D stays gated.
- With one or two judged references, exclusion rarely saves a verdict. Decision 1 is the main remedy.
- F3: this change was found on 2D_Case_4, a development layout. It is clean for a judged set nobody has seen (see the
  pending reference-set decision). If 2D_Case_2R and 2D_Case_6 stay judged, it is a declared deviation.

## Model-fix list, fixed before any candidate reference is screened (founder, 2026-11-12)
Confirmed by the founder before any fact screen of the candidate public modules (NC State PREES) was run or read, so
that the screen's answers can decide whether to adopt those modules but cannot steer what is built:
1. E008 drops the measured minimum gate-wire length (`min_signal_wire_length`) from its per-reference rules (T0314,
   variant R1). This reads O003 scope_in's enumerated rules as the complete meaning of "design rules at least as strict
   as the reference's own": its bondability rule bounds gate wires only from above (T0315 finding 2). The reference-set
   decision restates this reading.
2. Decisions 1 and 2 above.
3. The generator is not extended for 2D_Case_6's side-by-side switch blocks (T0314 section 3); such layouts stay
   outside the twin space and are excluded under F1(a).
Any further change to the generator, twin, degradation rule, rules or search before the freeze needs a new founder
decision that states whether the screen's answers were known.

## Not decided here
The reference set (D0010 amendment, candidate public modules).

## Alternatives considered
- (A) Keep the implied reading: any reference without a D makes E008 INVALID. Rejected: one well-designed module would
  void the experiment, although the control never builds from D.
- (D) A smaller planted headroom (for example 15 %): a criteria change to O003, and a weaker control. Rejected.
- A D outside the twin's topology: effectively a search, which F1(b)'s "degradation rule" does not describe. Rejected.
