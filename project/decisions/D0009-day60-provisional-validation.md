# D0009 — Day-60 gate keeps its date and is judged on provisionally validated evidence
Date: 2026-11-01 · Status: accepted · Decider: founder (founder session, 2026-11-01)

## Context
The charter's day-60 kill criterion (2026-11-27) reads: "O003 shows < 10% headroom on public benchmarks (the
pre-registered set reconstructed from research/notes/o003-public-benchmarks.md, with housing and terminals fixed and the
loop and extraction frequency fixed in O003)". Headroom is judged by the L2 inductance reference. Three draft-review
rounds of O004, the objective that validates that reference on reconstructed public modules (project/reviews/OBJ-O004,
T0125–T0134), showed that its precision gates and FastHenry's feasibility at module scale must first be measured.
O006 runs those pilots. A sealed O004 verdict, and then O003, cannot both finish by 2026-11-27.

## Decision
- The day-60 date stays 2026-11-27; it is not moved.
- O003 runs on the public benchmark set with l2_layout and reports each reference's headroom with an explicit error
  band combining (a) l2_layout's discretisation estimate and (b) the L2–FastHenry agreement measured on module-scale
  geometry in O006's pilot P4 (or, if FastHenry proves unusable there, l2_layout's discretisation estimate doubled).
  This is **provisional validation**; it is stated as such wherever the verdict is cited.
- The day-60 kill fires if the upper end of the error band of the median headroom across the benchmark references is
  below 10 %.
- The verdict is recorded as a founder decision on 2026-11-27 (it is not an mfos evaluation, because O004 will not have
  passed). If O004 later passes or fails, the founder revisits the verdict and records the outcome.

## Consequences
O003 must be drafted, reviewed and approved early enough to run before 2026-11-27, in parallel with O006 and O004. Its
experiment declares l2_layout as code_under_test without code_must_match on O004 (O004 is not yet passed); O004's
later code_must_match ties future O003 work to the validated code.

## Alternatives considered
- (a) Move the day-60 date until O004 finishes: honest about the evidence, but it moves a criterion set in advance.
- (b) Decide at day 45: defers a decision whose inputs (O006 pilot timing) are already known.
