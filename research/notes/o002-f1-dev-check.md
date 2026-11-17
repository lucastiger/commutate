# O002 F1 development check: is level 1 enough to judge E007? (T0393)

Scientist, 2026-11-15. Data: `research/o002_f1/f1_dev_check.json`, written by `f1_dev_check.py --analyse` from stored
solves only (`research/o002_f1/cache/`, `research/o007_dev3/cache/`; later `research/o002_f1/burst_out/`).
Solver: `src/moduleforge/solvers/thermal_fem.py`, sha256 a216d5fe3209bcee..., frozen rule
`research/o007_dev3/frozen_config.json`. Coolant 338.15 K, h = 5000 W/(m² K).

**Verdict: `status: awaiting_level2`, `level1: pending`.** Every F1 rule that the data can already test passes for
level 1, and nothing fails. The verdict is still open because 6 level-2 solves are missing (0.5 P_ref on both
development layouts, and both loads on both partners). They are beyond the local memory rule (22.6-54.1 GB by E009's
figures), and they are in `research/o002_f1/burst_level2.sh`: 6.35 VM-hours, about $3.9 on n2d-custom-8-81920-ext.
After the copy-back, `--analyse` gives the final confirmed or refuted without any further solve.

## 1. Set-up (facts)
- **Layouts.** The development layouts come from E009's dev seed 20261101, and their fingerprints match E009
  (1f66b68a..., 6aaf383a...). One partner per stratum was chosen by a rule fixed before any solve: the first later
  layout in `generate_layouts(n, 20261101, family, dies)` whose dies all have the development die (5.0 x 5.0 mm, same
  thickness and attach). By rejection, stream index 2 in both strata: side_by_side_6_p bbbac5e8..., u_shaped_2_p
  2207858e... (index 1, a 4.5 mm die, was rejected). T0394's die_size_mm option does not exist yet.
- **Loads.** P_ref is C004's calibrated power per die: 32.232107 W (side_by_side, 12 dies) and 47.141886 W (u_shaped,
  4 dies). The other load is 0.5 P_ref. A partner uses its stratum's P_ref.
- **Reproduction check (passes).** I re-solved levels 0 and 1 at P_ref on both development layouts with the frozen
  bytes. They reproduce the cached tj_mean and tj_max of `research/o007_dev3/cache` with a difference of exactly
  0.0 K, against a 1e-6 K tolerance. So the cached level-2 solves (T0243, burst) serve P_ref on the development
  layouts.
- **Rules as implemented.**
  - Estimate: `mfos.metrics.gci_step_floor(f0, f1, f2, 0.01 K)`. This is gci_capped, except that a sequence whose two
    steps are both below 0.01 K gets 3 max|d|.
  - Level-1 error: |f1 - f2| + estimate.
  - Absolute die average: the level-1 error must be at most 1 % of that die's local rise. The local rise is the die
    average minus the mean baseplate-bottom temperature, both at level 1.
  - Spread (per switch) and same-stratum pair difference: the level-1 error must be at most 0.1 K. The pair difference
    uses the hottest die of each layout, ranked by its level-1 die average, and keeps that die fixed across levels.
  - Level-1 value against level-2 value: within 0.1 K.
  - Energy balance at most 1e-6; Tj max at P_ref at most 175 °C.
  - Interpretation (mine): for spreads and pair differences I gate the level-1 error |f1 - f2| + estimate, not the
    level-2 estimate alone. That is the stricter reading of "at the judged level". The level-2 estimate is also stored
    as `pass_L2`.

## 2. Outcome per load and quantity

| load | quantity (count) | rule | outcome on available data |
|---|---|---|---|
| P_ref | absolute die average, development layouts (16) | level-1 error <= 1 % of local rise | **pass 16/16**: max 0.72 % (0.212 K on a 29.6 K rise; largest error 0.274 K), level-2 estimates 0.073-0.152 K |
| P_ref | absolute die average, partners (16) | same | pending (no level 2); level-0→1 steps at most 0.86 % of rise |
| P_ref | spread, development layouts (4) | level-1 error <= 0.1 K | **pass 4/4**: max 0.026 K (u_shaped_2 LS) |
| P_ref | spread, partners (4) | same | pending; level-0→1 steps at most 0.037 K |
| P_ref | same-stratum pair difference (2) | level-1 error <= 0.1 K | pending; level-0→1 steps -0.055 K (side_by_side), -0.038 K (u_shaped) |
| P_ref | level 1 vs level 2 (10 = 8 spreads + 2 pairs) | within 0.1 K | **pass 4/4** testable (max 0.011 K), 6 pending |
| 0.5 P_ref | absolute die average (32) | 1 % of local rise | pending; level-0→1 steps at most 0.83 % of rise (rises 13.6-23.0 K) |
| 0.5 P_ref | spread (8) | 0.1 K | pending; level-0→1 steps at most 0.018 K |
| 0.5 P_ref | pair difference (2) | 0.1 K | pending; level-0→1 steps -0.025 K, -0.017 K |
| 0.5 P_ref | level 1 vs level 2 (10) | 0.1 K | pending |
| both | energy balance (18 stored solves) | <= 1e-6 | **pass**: max 3.4e-13 |
| P_ref | Tj max, every layout, levels 0-2 | <= 175 °C | **pass**: max 126.2 °C (side_by_side_6_p, level 1) |

**Cross-stratum difference** (side_by_side_6 minus u_shaped_2, hottest die averages; reported only, never gated):
- At P_ref: 2.082 / 1.957 / 1.911 K at levels 0/1/2. The level-2 estimate is 0.057 K, and the level-1 error is
  0.103 K, just above 0.1 K.
- At 0.5 P_ref: 1.138 / 1.080 K at levels 0/1.
- Fact: this one difference converges worse than the same-stratum steps. Inference: the discretisation error cancels
  less between layouts that differ in die count and family, as research/notes/o002-reference-convergence.md argued
  for 2R. E007's A1 uses same-stratum pairs only, so this does not count against level 1. It would matter if anyone
  compared strata with the reference at level 1.

**Sanity checks, all pass.** These separate "the experiment is broken" from "level 1 is insufficient":
- Fingerprints match, and the partners are distinct layouts with the same die.
- Picard converged on every solve (residual below 1e-4 K), and no CG solve hit its iteration cap.
- Every own solve used the frozen bytes.
- The mean baseplate-bottom temperature agrees two ways (exact integral of the Q1 field at z = 0, and
  T_c + Q_out/(hA)) to within 6e-14 K on all 16 own solves.
- DOF growth between levels is 7.33-7.67x (8 ± 15 %).
- Half-load scaling: the rise at 0.5 P_ref divided by the rise at P_ref is 0.489-0.493 for every die. It is below 0.5,
  which is the expected sign for k falling with T. It is a power-scaling check, not a convergence check.

## 3. Competing explanations (mf-diagnosis)
1. **H1: level 1 is enough** (the hypothesis under test). Prediction: the partner sequences and the 0.5 P_ref
   sequences behave like the P_ref development sequences.
   - Test: the 6 level-2 solves.
   - Evidence for H1 (inference, not a verdict): on the P_ref development sequences the level-1 error is 0.72-0.84
     |d1| for the die averages (ratio d2/d1 ≈ 0.33-0.37, order capped at 1) and 0.48-1.08 |d1| for the spreads.
     Applied to the pending sequences, that gives at most about 0.72 % of rise for absolute averages (0.84 x 0.86 %)
     and at most about 0.06 K for pair differences (1.08 x 0.055 K).
2. **H2: level 1 fails somewhere F1 has not yet looked.** The candidates are:
   - absolute die averages on the partners, or at 0.5 P_ref, where the rise roughly halves while the error also
     roughly halves;
   - a pair difference whose hottest die swaps between levels.
   - Test: the same level-2 solves.
   - What would prove H1 wrong: any pending level-1 error above 1 % of rise or above 0.1 K.
   - Fact: the hottest die swaps between levels. On u_shaped_2_p, dies 0 (HS) and 2 (LS) trade rank between levels 0
     and 1 at both loads:
     - at P_ref, die 2 minus die 0 goes from -0.032 K at level 0 to +0.032 K at level 1;
     - at 0.5 P_ref, it goes from -0.029 K to +0.0002 K, so level 1 is a near-tie.
     - The other three layouts keep their hottest die, with level-1 gaps of 0.08-0.46 K.
   - Consequences:
     - Fact: the gated pair sequence holds die 2, the level-1 hottest, fixed across levels, so it stays smooth.
     - Inference: if level 2 ranks die 0 hottest, A1's reference value moves by about the die-0/die-2 gap, about
       0.03 K, not by a discretisation jump.
     - Fact: the own-hottest variant (max of the die averages) has a level-0→1 step of only -0.006 K at P_ref,
       against -0.038 K for the fixed-index one.
     - Both are in the JSON (`hottest_die_by_L1`, `hottest_die_by_L2`, `own_hottest_max_variant`).
   - Recommendation: E007 should expect near-tied hottest dies in 2-die u_shaped layouts. A1's ranking at the judged
     level is well defined, but it is not grid-independent.
   - Fact: the largest absolute ratio is 0.72 %, with 28 % margin. This is the closest rule.
3. **H3: the check itself is broken**, for example a different solver, a wrong power or a stale cache. Test: the
   reproduction and sanity checks above. All pass, so H3 is rejected for the data in hand.

**Classification:** none yet; the experiment works and is waiting on data. My confidence that the burst will confirm
level 1 is about 0.8. That figure is an inference from the P_ref development sequences, the level-0→1 steps of the
pending sequences, and E010's 2R results. It is not evidence.

## 4. Level-2 burst (`research/o002_f1/burst_level2.sh`)
- **Running it.** `--dry-run` prints the plan and every command and runs none. Without the flag, the founder's
  machine runs `scripts/burst_gcp.sh --cmd "uv run python research/o002_f1/f1_dev_check.py --solve-level2 <6 keys>"
  research/o002_f1/burst_out n2d-custom-8-81920-ext us-central1-a`. It needs f1_dev_check.py committed on
  `$MF_REF` (main by default), and it refuses if thermal_fem on that ref is not a216d5fe....
- **Scheduling.** On the VM the jobs run largest first. A job starts only while the running jobs' E009 memory
  estimates (DOF x 4964 B x 1.15) fit within 0.85 x physical memory, so the side_by_side jobs run one at a time and
  two u_shaped jobs run together.
- **Estimates.**
  - Memory: 3 x 53-54 GB (side_by_side) and 3 x 22.6 GB (u_shaped). For comparison, the cached solves measured 29.5
    and 12.3 GB.
  - Wall: about 1.5 h and 0.64 h per job, at the measured level-2 rate of T0243's burst (585 µs per DOF).
  - Total: 5.85 h makespan plus 0.5 h set-up = 6.35 VM-hours, about $3.88 on-demand. The 0.612 $/h is the founder's
    figure for this machine in E010's spec.
  - A regular VM is recommended over Spot, because each solve saves its result only at the end.
- **After the copy-back:** `uv run python research/o002_f1/f1_dev_check.py --analyse`.

## 5. Recommended actions
1. Founder: run `bash research/o002_f1/burst_level2.sh` after this directory is on main. Expect about 6.4 h and $4.
2. Do not register E007 until `--analyse` reports `level1: confirmed`. If it reports `refuted`, F1's response
   applies: judge at level 2, or lower the load, under a new experiment id, which is a founder decision.
3. Planner: if E007's design ever compares across strata with the reference, note that the cross-stratum difference
   already has a 0.103 K level-1 error at P_ref.

## 6. Limits
- Two strata only (side_by_side 6, u_shaped 2), one partner each, and one die size (5.0 mm). The interleaved family
  and the other die counts are untested.
- The local-rise denominator uses the mean baseplate-bottom temperature, which is O002's A2 definition.
- The 0.01 K step floor did not fire on any complete sequence.

## 7. Verdict rule after T0419, and the result on the committed burst records
- **Rule.** `--analyse` now sets `level1 = 'pending'` and lists the failed checks in a top-level `broken` list if any
  sanity check fails (including the new `record_provenance`), `reproduction_check.passed` is false, the energy balance
  fails, or Tj at P_ref exceeds its limit. `refuted` and `confirmed` are possible only when `broken` is empty; the
  per-quantity rules are unchanged. `record_provenance` checks every stored record (cache/, burst_out/, and the
  o007_dev3 level-2 records at P_ref): power equal to p_ref x load factor (relative 1e-12), the layout's fingerprint,
  the key's level and load, the die count, solver hash `a216d5fe3209bcee`, and `frozen_config_sha256`. The o007_dev3
  level-2 records carry no solver hash (T0411 finding 3), so their provenance is dev_study.json's recorded
  `thermal_fem_sha256` plus `reproduction_check.passed`; the check's output says so. `own_solves_frozen_bytes` now
  covers every record in cache/ and burst_out/, whatever its `source` label.
- **Result (no solve; the 6 committed I0212 records plus the cached level 0-1 and o007_dev3 level-2 records).**
  status `complete`, level1 `confirmed`, `broken` = `[]`; 24 records pass `record_provenance`.
- **Worst level-1 error over tolerance** (error_L1 = |f1 - f2| + estimate, as a fraction of the tolerance):

  | quantity | P_ref | 0.5 P_ref |
  |---|---|---|
  | die average (1 % of local rise) | 0.717 (side_by_side_6, die 11; 0.212 K of 0.296 K) | 0.695 (side_by_side_6, die 11; 0.100 K of 0.144 K) |
  | per-switch spread (0.1 K) | 0.261 (side_by_side_6_p, HS) | 0.316 (side_by_side_6, LS) |
  | same-stratum pair difference (0.1 K) | 0.558 (side_by_side pair) | 0.250 (side_by_side pair) |
  | level-1 vs level-2 spread/pair (0.1 K) | 0.248 | 0.111 |

  The die-average cells give the worst ratio and, for that die, error_L1 out of its tolerance. The largest absolute
  die-average error_L1 is on another die, u_shaped_2_p die 3: 0.305 K (ratio 0.672) at P_ref and 0.143 K (ratio 0.647)
  at 0.5 P_ref. Attempt 1 of T0419 printed these two values against side_by_side_6 die 11; T0419 attempt 2 corrected
  that from f1_dev_check.json. The o007_dev3 level-2 records also carry no fingerprint and no `frozen_config_sha256`,
  so those fields are not checked on them. Their geometry is tied to this task's fingerprinted layouts through the
  reproduction check, which compares the level-0/1 solves of the same o007_dev3 cases with this task's cache records
  to within 1e-6 K. That link is an inference, not a direct field check, and `record_provenance` says so in its output.
