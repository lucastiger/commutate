# D0025 — O002 before E007's registration: one-sided 97 % Woodruff bounds; 20 layouts per stratum, provisional until power for the measured L1 is known; CPU-hours count process time; T0395's grid rule and c(s) accepted, with a development-row check
Date: 2026-11-17 · Status: accepted (drafted by the founder session; accepted as drafted) · Decider: founder · Relates to: O002 (F1, F3, F5, budget), I0211, I0212, I0223; T0392, T0393, T0395, T0396, T0397, T0398, T0419, T0420, T0423, T0424, T0434

## Context
- These decisions were taken in founder sessions on 2026-11-16 and 2026-11-17 and recorded in O002's state log, which
  blinded reviewers do not see. They are recorded here for E007's spec to cite.
- F1 (judging level): the founder's level-2 burst (I0212, records committed in 87f639df) confirmed level-1 judging.
  T0419 (I0223) makes the sanity and provenance checks part of the verdict.
- F3 (T0396, f3_simulation.json; reviews T0420 and T0434):
  - The nominal one-sided 95 % Woodruff bound (V3) under-covers in some cells: kill|t3|20 0.932 and alt|normal|24
    0.941, about 3 Monte Carlo SE below 0.95. V4, the same bound at one-sided 97 %, covers 0.965 to 1.0 in every cell.
  - The selection rule was amended, and V4 added, after round 1 was seen. Round 2 used fresh seeds, and T0434's own
    fresh-seed rerun reproduced V4's coverage.
  - Joint power at 0.6 x each threshold, under t3, is 0.748 at m = 16, 0.898 at m = 20 and 0.958 at m = 24.
  - For the L1 as measured on development rows (A4 = 0.366, 0.73 x A4's threshold), joint power at m = 20 is 0.531
    under t3 and 0.967 under normal errors. A4 alone drives the shortfall. That scenario was simulated only at m = 20.
- T0395's L1 (reviews T0423, T0424): the 1.5 mm grid rule replaced n1's 4 mm cap because it improves A4. With it, c(s)
  varies between the two calibration families by 0.0059 at 4.0 mm, above the design note's 0.005 transfer line; the
  other sizes are at most 0.0033. On an uncalibrated interleaved/3 layout at 4.0 mm, A2-type was at most 1.55 %
  against the 3 % threshold. Per-die bias was larger on LS dies (0.35-0.43 K) than on HS dies (about 0.1 K).

## Decision
1. **The bound** (2026-11-17 01:26 UTC). E007 judges A1-A4 and K1-K3 with CISpec(scheme='woodruff', level=0.94,
   cluster='layout').
   - That is one-sided 97 % bounds, and the K1/K2 lower bounds under max-over-loads are at 98.5 % per load.
   - It is more conservative than O002's "upper 95 % bound" for both passes and kills; the cost is a somewhat higher
     chance of INCONCLUSIVE.
   - The bound is mfos.metrics.quantile_ci (patch route I0211, merged da2118fc).
   - The registration record discloses the amended selection rule and keeps round 1's numbers
     (f3_simulation_r1_noselection.json).
2. **The sample** (2026-11-17 01:26 UTC, made provisional at 04:25 UTC). m = 20 layouts per (family, dies) stratum,
   300 in all, with f3_simulation.json's fixed allocation, stays in the files. The final m is chosen before
   registration from T0398's power figures for the as-measured L1, at m = 20, 24, 32 and 40 under normal and t3
   errors. The choice is recorded as an amendment of this record.
3. **CPU-hours** (2026-11-17 04:25 UTC). O002's cpu_hours budget counts the CPU time the solver processes use, as run
   records measure it, not burst-VM vCPU-hours; VM time is costed in dollars. E007's plan is about 52 CPU-hours on
   this convention. T0398 confirms it by measuring level-2 cpu/wall on one solve.
4. **The L1's calibration** (2026-11-17 02:35 UTC). T0395's 1.5 mm grid rule and its c(s) table are accepted although
   the 4.0 mm family spread exceeds the transfer line.
   - The development rows (T0398) are the check: every family at every die size, interleaved and the 3-5-die strata
     included. Per stratum they report the implied factor beside c(s), the per-die bias for HS and LS dies, A2-type
     against the model's 1.8 % guard, and A4 against 0.3.
   - If any stratum misses the guard or A4 <= 0.3, the founder decides before E007 freezes.

## Consequences
- E007's spec cites D0025 for its bound, sample, cost convention and the frozen L1.
- Registration waits for T0398's development rows, the final m, and `mfos exp check E007` on those rows (F2's
  null-discrimination requirement).
