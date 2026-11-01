# D0011 — No O003 verdict by day 60 counts as INCONCLUSIVE; O003 waits for O006's pilots
Date: 2026-11-01 · Status: accepted · Decider: founder (founder session, 2026-11-01) · Amends: D0010

## Context
Draft reviews T0145 (statistics) and T0146 (physics) rejected O003's second draft with two blockers that cannot be fixed
without measured inputs: (1) the 20 % / 10 % lines concern the module-level loop customers buy, while the reference can
model only the substrate-level loop, with no terminal tab, lead or bus-bar model; (2) there is no search-power control,
so a search that returns its input would fire the day-60 kill while every check stays green. The error band also needs
O006's pilots (P3 L2 convergence, P4 FastHenry feasibility) and P1 (thermal operating envelope). O006 must pass and its
pilots report (about 1–2 weeks) before O003 can be finalised, so an O003 verdict by 2026-11-27 is uncertain. This
decision is taken before any O003 data exists.

## Decision
- O003 is paused as a draft until O006's pilots P1, P3 and P4 have reported; it is then revised once, addressing
  T0145/T0146 (a planted-headroom search-power control, a terminal model or the customer's own terminal inductance for a
  module-level denominator, a band computable for locally processed customer layouts, snapping bias in the band, a
  rule for an empty customer set, and the operating point fixed per reference before any solve).
- If O003 has not produced a verdict by 2026-11-27, the day-60 criterion counts as **INCONCLUSIVE**: under D0010 the
  founder holds a thesis review on 2026-11-27, and continuing requires an explicit, recorded reason.
- D0009's and D0010's other rules stand.

## Consequences
The critical path is now: customer layouts by 2026-11-12 (day 45), O006 approval and pilots, the O003 revision. The
day-45 gate is unchanged.

## Alternatives considered
- (a) No verdict counts as a kill: the strictest reading, but it treats a tooling delay as a negative result.
- (b) Decide at the day-45 review: defers a choice that is better fixed before data.
