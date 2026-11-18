# D0027 — O002, E007: the per-stratum A4 check passes on 9 development layouts and is a diagnostic; the sample is 32 layouts per stratum (480), for kill-side power
Date: 2026-11-18 · Status: accepted (drafted by the founder session; accepted as drafted) · Decider: founder · Amends: D0025 items 2 and 4 · Relates to: O002 (F3, A4, K1-K3), T0398, T0456, T0459, T0464

## Context
- D0025 item 4 had the development rows check the c(s) transfer per stratum, and stop if any stratum missed A4 <= 0.3.
  On T0398's rows (3 layouts per stratum), A4 was above 0.3 in three strata: interleaved/2 0.352, side_by_side/2 0.340
  and u_shaped/6 0.951. Pooled A4 was 0.107, against a threshold of 0.5.
- T0456 diagnosed the three strata and added 6 development layouts to each (seed 20261456).
  - u_shaped/6's 0.951 was a small-denominator artefact. The three layouts had nearly identical reference spreads, so
    the leave-one-out null's error was tiny. L1's spread error there is a real but small systematic -0.9 %.
  - On 9 layouts (18 switch rows), A4 is 0.286 (interleaved/2), 0.223 (side_by_side/2) and 0.096 (u_shaped/6). No
    per-stratum A4 upper bound is finite at these sizes.
  - The interleaved low-side bias (+0.36 K at P_ref) is real. A future L1 version could target it.
- D0025 item 2 left m (layouts per stratum) provisional at 20, pending power for the L1 as measured. T0456's corrected
  simulation passed its gating consistency check: simulated median A4 0.108 / 0.107 against 0.107 measured. Its results:
  - Pass power is about 1.0 at every m from 20 to 40, with minimum V4 coverage of 0.971 or better.
  - Kill side, at 1.2 x each kill threshold (normal / t3 errors):

    | m | P(K1 fires) | P(K3 fires) |
    |---|---|---|
    | 20 | 0.418 / 0.306 | 0.291 / 0.168 |
    | 32 | 0.812 / 0.581 | 0.576 / 0.354 |
    | 40 | 0.885 / 0.669 | 0.764 / 0.486 |

    K2 fires with probability 1.0 at every m. The model over-predicts A3 by 30-40 %, so the kill-side rates are approximate.

## Decision
1. **The per-stratum A4 check counts as passed on the 9 development layouts.** The per-stratum A4 is a reported
   diagnostic, not a gate: at 6-18 switch rows it is a ratio of near-maxima, and its denominator is set by the most
   atypical layouts. The pooled A4 (threshold 0.5) is the criterion. E007 may proceed toward its freeze with the L1 and
   c(s) as frozen (D0025 item 4).
2. **E007 uses m = 32 layouts per (family, dies) stratum, 480 layouts in all** (amends D0025 item 2). The reason is the
   kill side. At m = 20 a moderately bad L1 would most likely end INCONCLUSIVE instead of FAIL; at m = 32 K1 fires with
   probability 0.81 (normal) / 0.58 (t3) at 1.2 x the kill threshold. The cost is about 14 more CPU-hours of level-1
   reference solves and about $9 more VM, within O002's 100 CPU-hours counted as process CPU time (D0025 item 3). T0464
   checks this against the regenerated plan.

## Consequences
- T0464 sets the allocation to 32 per stratum and 480 layouts, names T0456's corrected simulation as the power and
  coverage evidence at m = 32, regenerates the cost plan, and lists the level-2 timing burst needed before registration.
- E007's spec cites D0025 and D0027.
