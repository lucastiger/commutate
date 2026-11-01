# D0010 — Day 60 is judged on customer reference layouts if received by day 45; public benchmarks are the indicative fallback
Date: 2026-11-01 · Status: accepted · Decider: founder (founder session, 2026-11-01) · Amends: D0009

## Context
Draft reviews T0141 (statistics) and T0142 (physics) of O003 found that the public benchmark set cannot credibly test
A-T3 ("real derivative problems") by 2026-11-27: only two references can be reconstructed (PowerSynth 2D_Case_2R and
2D_Case_6, academic tool sample inputs; the Aalborg/Danfoss module has no published dimensions); with n = 2 and an
expected headroom near 18 %, the design is INCONCLUSIVE with probability 0.78–0.98; and a pass on tool sample inputs
would not show headroom on real commercial derivatives. A customer's own reference layout, the day-45 ask, would be a
credible test. This decision is taken before any O003 data exists.

## Decision
- **Reference set by rule, fixed now.** If one or more customers share a reference layout under NDA by 2026-11-12
  (day 45), O003's day-60 verdict is judged on those layouts. Otherwise it is judged on the public benchmarks
  (PowerSynth 2D_Case_2R and 2D_Case_6), and every statement of the verdict labels it "public benchmarks, low power,
  indicative".
- **INCONCLUSIVE at day 60** (headroom band between 10 % and 20 %) leads to a founder thesis review on 2026-11-27, not to
  continuing by default.
- D0009's other rules stand: the date stays 2026-11-27; the verdict is a founder decision on provisionally validated
  evidence; the kill fires if the upper end of the error band of the median headroom is below 10 %.
- **Customer data.** Customer layouts and anything derived from their geometry never enter this repository: they live
  in the private data vault (`project/customers/README.md`) and are referenced by ID and sha256. They are processed on this
  machine only; a cloud VM is used for them only if that customer's NDA permits it, recorded per customer.

## Consequences
O003 is revised to select its references by this rule and to keep customer geometry out of its rows. The charter's day-60
sentence is amended to match (`docs/reports/charter-2026-11-01.patch`).

## Alternatives considered
- (a) Public benchmarks only: keeps the charter wording, but a likely INCONCLUSIVE that tests tool sample inputs.
- (b) Customer layouts only: most credible, but nothing technical runs until a customer exists; without one the day-45
  kill fires anyway.
