# E007 development rows (T0398, O002), 2026-11-17

Not evidence. Development geometry only. Rows: `experiments/drafts/E007.dev_rows.json`, written by `e007_run.py --dev`.
Simulation: `research/o002_e007/stats_sim_dev.py` → `f3_dev_simulation.json`. Work directory with checkpoints:
`research/o002_e007/dev_work/`.

## What was run (facts)
- Seed 20261398 (`config.dev.dev_seed`, already in `config.seeds.forbidden`). 15 (family, dies) strata × 3 layouts = 45
  layouts. Die sizes come from `config.dev.die_size_mm`: every family at 4.0/4.5/5.0/5.5 mm, and interleaved/3 at 4.0 mm.
  P_ref comes from each stratum's level-0 calibration on its seed-20261101 development layout. Judged at level 1, both loads,
  90 reference solves. `meta.smoke = false`. No sealed seed. No F7 and no level-2 subset (both are off in `config.dev`).
- One solve at a time (`--max-procs 1`), with thread variables set to 1. Cap 7 GB, which is allowed by the 10 GB rule:
  memory_pressure showed 72 % free and the swap files totalled ≤ 3 GB.
  `sysctl vm.swapusage` is blocked in this sandbox, so the runner's swap guard read 0. I watched the swap-file count by
  hand instead; it stayed at 3.
- Measured cost: the 90 level-1 solves took 2.96 CPU-h (CPU/wall 0.994); the 15 calibrations took 0.13 CPU-h. Peak RSS was
  5.44 GB (interleaved/6). Level 1 ran at 0.136 ms/DOF median (max 0.262) and up to 4.3 kB/DOF. Simulations took about
  0.5 CPU-h. Total is under the 6 CPU-h local limit.
- Pass 1's L1 phase (A5) ran while my simulation was using another core, so it broke "nothing else running".
  Pass 2 re-timed it alone, after the judged solves had checkpointed. A5 = 0.537 s in pass 1 and 0.440 s in pass 2; the
  rows carry pass 2. L1 outputs agree across the passes to 2e-10 K. Pass 1 is kept as `dev_work/l1_phase_pass1.json`.
- Every sanity check passed: freeze, seeds, allocation, distinct/unseen, operating point, energy balance, Picard, CG
  headroom, Tj rating, baseplate mean, rows contract, single-thread timing, recompute consistency, f2_null_discrimination.

## Results (facts; points, V4 bounds in the rows' meta)
A1 0.230 K [V4 upper +inf at 3 layouts/stratum]. A2 0.0081 (upper 0.010). A3 0.091 K (upper 0.186).
A4 0.107 (upper +inf). A5 0.440 s (95 % order-statistic interval 0.400–0.477, recorded at level 0.95).
Own-hottest A1 0.230 K. Sample diversity: the minimum over strata of the sd of the hottest-die average is 0.053 K.

**F2 (packet step 2): passes.** All values are points at P_ref (A1) and P_ref (A4).

| null | A1 (K) | A4 | A2 | A3 (K) | lowest per-stratum A1 (K) |
|---|---|---|---|---|---|
| die_position | 5.69 | 1.00 | 0.083 | 0.85 | 0.150 |
| stratum_mean (per stratum and switch) | 5.50 | 1.00 | 0.187 | 0.85 | 0.164 |
| isolated_die | 3.82 | 11.42 | 0.431 | 9.72 | 0.063 |

Per-stratum A1/A2 for every null are in `meta.f2_nulls[*].per_stratum_P_ref`. `mfos exp check` shows A1 not_satisfied for
every null. A4 is "undetermined" at the bound, because the ratio's upper bound is +inf with 3 layouts per stratum.
The die-position null's A4 equals the stratum-mean null's (0.99999999999998). That is consistent with the scope limit:
the die-position spread is at most the mean spread. Some strata have a small null A1 (down to 0.06 K). F2 is judged
on the pooled statistic, as specified.

**D0025 decision 4 check: trips. Stop. The founder decides before E007 freezes.**

| stratum | size | c(s) | implied c | bias HS / LS P_ref (K) | A1 (K) | A2 max | A2 recal. | A4 | A5 (s) |
|---|---|---|---|---|---|---|---|---|---|
| interleaved/2 | 4.5 | 0.9828 | 0.9783 | +0.08 / +0.35 | 0.019 | 0.0081 | 0.0038 | **0.352** | 0.37 |
| interleaved/3 | 4.0 | 0.9854 | 0.9787 | +0.11 / +0.47 | 0.049 | 0.0116 | 0.0058 | 0.093 | 0.36 |
| interleaved/4 | 5.5 | 0.9840 | 0.9827 | −0.05 / +0.15 | 0.081 | 0.0048 | 0.0039 | 0.163 | 0.49 |
| interleaved/5 | 5.0 | 0.9830 | 0.9802 | +0.01 / +0.20 | 0.004 | 0.0063 | 0.0043 | 0.291 | 0.54 |
| interleaved/6 | 4.5 | 0.9828 | 0.9781 | +0.06 / +0.29 | 0.021 | 0.0098 | 0.0049 | 0.054 | 0.63 |
| side_by_side/2 | 4.0 | 0.9854 | 0.9844 | +0.23 / −0.13 | 0.250 | 0.0063 | 0.0053 | **0.340** | 0.28 |
| side_by_side/3 | 4.5 | 0.9828 | 0.9824 | +0.19 / −0.15 | 0.189 | 0.0059 | 0.0060 | 0.079 | 0.37 |
| side_by_side/4 | 5.0 | 0.9830 | 0.9838 | −0.02 / −0.05 | 0.110 | 0.0051 | 0.0043 | 0.133 | 0.43 |
| side_by_side/5 | 5.5 | 0.9840 | 0.9857 | −0.03 / −0.10 | 0.145 | 0.0066 | 0.0052 | 0.106 | 0.49 |
| side_by_side/6 | 4.0 | 0.9854 | 0.9855 | +0.10 / −0.11 | 0.200 | 0.0055 | 0.0056 | 0.202 | 0.50 |
| u_shaped/2 | 5.0 | 0.9830 | 0.9826 | −0.01 / +0.05 | 0.041 | 0.0030 | 0.0026 | 0.254 | 0.35 |
| u_shaped/3 | 5.5 | 0.9840 | 0.9841 | −0.04 / +0.03 | 0.123 | 0.0025 | 0.0024 | 0.140 | 0.38 |
| u_shaped/4 | 4.0 | 0.9854 | 0.9817 | +0.07 / +0.25 | 0.149 | 0.0074 | 0.0036 | 0.087 | 0.39 |
| u_shaped/5 | 4.5 | 0.9828 | 0.9827 | −0.00 / −0.01 | 0.242 | 0.0056 | 0.0054 | 0.132 | 0.55 |
| u_shaped/6 | 5.5 | 0.9840 | 0.9843 | −0.02 / +0.00 | 0.069 | 0.0062 | 0.0064 | **0.951** | 0.59 |

- The 1.8 % A2 guard holds in every stratum (max 1.16 %). A4 ≤ 0.3 fails in interleaved/2, side_by_side/2 and u_shaped/6.
- Implied-c family spread is 0.0064 at 4.0 mm (T0395 measured 0.0059), then 0.0046 / 0.0036 / 0.0031 at 4.5 / 5.0 / 5.5 mm.
  Interleaved is the lowest at every size: L1 over-predicts its rise. Effect on A2: with each stratum's implied factor,
  A2 at 4.0 mm on interleaved/3 drops from 1.16 % to 0.58 %. Across strata the A2 share from calibration is ≤ 0.6
  percentage points.
- LS dies on interleaved strata are biased +0.29 to +0.47 K at 4.0–4.5 mm, against HS +0.06 to +0.11 K. This reproduces
  T0423/T0424.

Inferences:
- Each per-stratum A4 is a ratio of p95s over 6 switch rows (3 layouts × 2 switches), which is in effect a ratio of maxima.
  It is very noisy.
- Speculation, not checked: u_shaped/6's 0.951 may be noise in a small denominator (the stratum-mean null's spread
  error over 6 rows). It was not diagnosed here and is worth inspecting before m is chosen.
- The interleaved LS bias is systematic. A per-family c would remove most of it, but that is a model change (a new L1
  version), not something for here.

## F3 on the dev structure (packet step 3). Bound V4; 1000 reps per cell; Monte Carlo SE 0.007 at 0.95
Coverage, as the minimum over the scenarios n1, alt, edge, kill, dev and dev_cells at m = 3:

| | A1 | A2 | A3 | A4 | K1 | K2 | K3 |
|---|---|---|---|---|---|---|---|
| normal | 1.000 | 0.985 | 0.983 | 1.000 | 0.998 | 0.974 | 1.000 |
| t3 | 1.000 | 0.983 | 0.989 | 1.000 | 0.997 | 0.971 | 1.000 |

## Power at m = 20 / 24 / 32 / 40 (T0434 (1)); joint (A4 alone)
| scenario | normal | t3 |
|---|---|---|
| n1 values (A4 0.366) | 0.971 / 0.990 / 0.999 / 1.000 (same) | 0.516 / 0.618 / 0.819 / 0.914 (same) |
| dev as measured (A1 0.230, A2 0.0081, A4 0.107) | 1.000 at every m | 0.992 / 0.999 / 1.000 / 1.000 (A4 1.000) |

n5's alt (0.6 × thresholds) gives power_joint 0.898 (t3) and 1.0 (normal) at m = 20. In n1 the joint power is A4's
power: every other criterion's power is 1.0. Cross-check: n1/t3/20 gives 0.516 here against 0.531 in T0434's
independent run, within one Monte Carlo SE.

**Kill side (T0434 (2))**, scenario at 1.2 × each kill threshold (A1 1.8 K, A2 0.18, A4 1.2), m = 20 / 24 / 32 / 40:
- P(K1 fires): normal 0.975 / 0.997 / 0.998 / 1.000; t3 0.446 / 0.570 / 0.696 / 0.815.
- P(K2 fires): 1.000 everywhere.
- P(K3 fires): normal 0.381 / 0.477 / 0.638 / 0.844; t3 0.093 / 0.167 / 0.188 / 0.333.

Inference: K3, and K1 under t3, have low kill-side power. A true ratio 1.2 × K3's line is usually not killed at m = 20.
The likely outcome is INCONCLUSIVE.

**dev_cells (T0420 (2)): the model fails its own adequacy check, so its power is not reported as a finding.**
- It uses per-(family, band) error scales measured on the dev rows. Its truth gives A3 0.357 K and A4 1.13; the dev rows
  measure 0.091 K and 0.107.
- Cause (inference): I measured die-level error sd around the layout mean. That folds the systematic HS/LS offset and
  die-position errors into iid per-die noise, which inflates spreads. The reference's die variation was also taken from
  n1.
- V4 still covers under this pessimistic model (≥ 0.970 at every m). Its power (0 at every m) is an artifact of the
  model and says nothing about L1.
- A corrected version needs: deviations around the (layout, switch) mean, switch offsets as fixed effects, and measured
  reference variation. Recommended as a follow-up.

## Other packet items
- A5 (step 4): `meta.l1_eval_s_p50` = 0.440 s, on the founder's Mac (arm64), single thread, alone.
- Level-2 timing (T0420 (1)): no level-2 solve fits the local 10 GB limit. The smallest development layout
  (side_by_side/2, 4.0 mm) is 3.48 M DOF, est. 20.2 GB; E009 measured 12.3 GB for a 2-die level-2 solve. The job is
  ready at `research/o002_e007/l2_timing/job.json`. Burst command:
  `scripts/burst_gcp.sh --cmd "uv run python experiments/runners/e007_run.py --child research/o002_e007/l2_timing/job.json" research/o002_e007/l2_timing n2d-custom-8-81920-ext`.
  The record will carry cpu_s, wall_s and peak_rss_GB.
- cpu_hours_est (step 5): `--plan` gives the same CPU-hours (56.7 expected / 61.1 upper), so the spec's 57.0 is kept.
  The measured level-1 rate on the Mac (0.136 ms/DOF median) is below the plan's 0.195, but the registered host is the
  VM. The measured peak memory per DOF (4.3 kB) is above the plan's 3.4 kB for level 1. Recommendation: raise
  `compute.bytes_per_dof['1']` before registration. Not changed here.
- Review T0449/T0450 fixes in the runner and spec:
  1. A5 interval computed and recorded at 0.95.
  2. Units come from the spec, so F4 A1/A3 are in K.
  3. F4 thresholds come from the objective, with the point-estimate rule stated.
  4. `--plan` prints the runner flags its packing needs, plus a one-at-a-time alternative (57.2 VM-h, $35.00).
  5. The A5 host is fixed as option A's VM; the L1 phase records its host.
  6. `config.scope_limits` covers F6 (subset only), die-position A4 and A5's host.
- The L1-phase cache key now hashes only what L1 depends on, not prose in the config.

Nothing gated was changed: criteria, thresholds, bound, allocation and m = 20 are untouched. Spec additions:
- `dev_rows`
- seed 20261399 (this simulation's seed) added to `seeds.forbidden`
- `scope_limits`
- `dev.result`
- one founder-decision item
