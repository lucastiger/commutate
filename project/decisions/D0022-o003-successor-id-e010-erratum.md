# D0022 — Erratum to D0021: O003's successor experiment is E010, not E009
Date: 2026-11-14 · Status: accepted · Decider: founder (founder session, 2026-11-14) · Amends: D0021 (id only); T0339, T0342

## Context
D0021 named O003's successor experiment "E009". E009 is O007's registered, completed scikit-fem thermal experiment
(experiments/specs/E009.yaml, experiments/runners/e009_run.py, run E009-20261107T162152-a3cf). Claim C004 cites it, and
O003 requires C004. Both T0339 attempts stopped rather than overwrite it, and diagnosis T0342 traced the failure to the
id. E010 is used nowhere in experiments/, project/ or research/. E004, E005 and E007 are reserved by the evidence
plans of O004, O005 and O002.

## Decision
1. Wherever D0021 says E009 for O003's successor, read E010. Its experiment files, runner, development directory,
   notes, launcher and burst state directory use E010 / e010 names. O003 v6 (D0021 item 5) names E010.
2. Nothing else in D0021 changes. O007's E009 and everything that cites it stay untouched.
3. T0339 is rewritten to E010 and retried.
