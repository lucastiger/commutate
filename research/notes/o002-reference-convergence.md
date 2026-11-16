# O002 refresh: convergence of die-average Tj, pair differences and spreads on the thermal reference

Founder session, 2026-11-16, after O002's draft reviews T0369 (statistics) and T0370 (physics), which both found the
draft's 0.05 K bound on each die-average estimate unreachable. Measured from existing solves; no new solve.

**Data.** E010's stored thermal_fem solves on 2D_Case_2R (run E010-20261114T202413-80c1, `work/2D_Case_2R/solves/`):
18 layouts (the reconstruction, the twin and shortlisted candidates), 4 dies each, levels 0, 1 and 2 of the frozen grid
rule, one power per die for all layouts (59.5 W, C004's calibration). Same thermal_fem bytes as EV-O007-01. 2R is
development geometry under D0023. Script `research/o002_refresh/convergence_from_e010.py`, output
`research/o002_refresh/convergence_from_e010.json`.

**Estimator.** `mfos.metrics.gci_capped` of the finest (level 2) value. Pair difference: the die-average Tj of each
layout's hottest die (by its level-2 die average) minus the other layout's, over all 153 pairs. Spread: max - min of
die-average Tj over one switch's 2 dies, 36 switches.

| quantity (estimate at level 2) | median | p95 | max | +inf |
|---|---|---|---|---|
| absolute die-average Tj | 0.113 K | 0.143 K | 0.156 K | 0 of 72 |
| pair difference | 0.010 K | 0.040 K | 0.044 K | 8 of 153 |
| per-switch spread | 0.008 K | 0.030 K | 0.049 K | 2 of 36 |

| level step of pair differences | median | p95 | max |
|---|---|---|---|
| level 1 -> 2 | 0.007 K | 0.032 K | 0.036 K |
| level 0 -> 1 | 0.025 K | 0.117 K | 0.133 K |

The 8 divergent pair sequences all have both steps at or below 0.005 K (for example 0.0002 then -0.0013 K): tiny-step
cases that are converged, not diverging, where the ratio of two tiny steps is close to random.

Cost per solve: level 2 median 1,499 s (25 min), peak 14-16 GB, 4.3-4.8 M nodes; level 1 median 155 s.

## Reading
- Absolute die averages converge to about 0.11-0.16 K at level 2, so a 0.05 K bound on them is unreachable at any
  affordable level (both reviews).
- Differences between layouts and spreads within a switch converge about ten times better (at most 0.044 K and 0.049 K),
  because the discretisation error is largely common to layouts of the same stack and die.
- Judging at level 1 leaves at most about 0.05 K on a pair difference (the 0.036 K step plus the remainder beyond
  level 2), well inside a 0.1 K gate, at about a tenth of the level-2 cost.
- Limits: one PowerSynth geometry with 4 dies; generator layouts with 2-6 dies per switch may differ, so O002's F1 asks
  for the same check on two generator development layouts before E007's registration.
