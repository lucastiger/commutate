# D0008 — O003 uses multi-fidelity search; O005 is shelved
Date: 2026-10-31 · Status: accepted · Decider: founder (founder session, 2026-10-31)

## Context
O005 (draft) was to decide whether O003 searches on L1 alone within a family and die count, or screens with L1 and
re-ranks the shortlisted candidates of each job with L2 (multi-fidelity). Two rounds of draft review rejected it
(`project/reviews/OBJ-O005/`, T0121–T0124). The second round's simulations, calibrated to E002's within-stratum L1
quality (residual about 1.4–1.5 %), found:
- the hypothesis is probably true: choosing by L1 loses about 0.8 % on average, and more than 2 % in about 16 % of
  strata, both inside O005's thresholds;
- but 15 strata cannot show it: P(PASS) about 0.2–0.4. Reaching 0.8 needs roughly 30–60 independent candidate sets,
  about 700–1,400 CPU-hours;
- K1 could not fire for any L1 consistent with E002, and the evaluator has no Clopper–Pearson path.
Both architectures share the same L1 screening step; they differ only in a few L2 solves per job. The day-60 gate
(2026-11-27) makes O004 and the customer evidence the critical path.

## Decision
- O003 uses **multi-fidelity search**: L1 screens candidates within the customer's family and die count; L2 (the code
  O004 validates) re-ranks the top candidates of each job, and the reported layout is the L2 best. O003 fixes the
  shortlist size in its design.
- **O005 is shelved**: it stays an unapproved draft, not deleted. Revisit it only if the per-job L2 cost becomes a
  constraint (for example on-premises customer compute).
- Charter assumption A-T1b is marked deferred.

## Consequences
O003's compute estimate includes L2 re-ranking per benchmark job (about 1–2 CPU-hours per candidate at E002's
reference level, times the shortlist size). No O005 compute (400 CPU-hours) is spent. The thermal constraint follows the
same pattern once O002 decides: L1 thermal screens, L2 thermal audits the finalists.

## Alternatives considered
- (a) Redesign O005 with an operating-characteristic study and 30–60 candidate sets: about 700–1,400 CPU-hours and a
  third review round, on the critical path to day 60.
- (b) Loosen O005's thresholds at 15 strata: cheaper, but accepts that a larger share of jobs may lose more than 2 %.
