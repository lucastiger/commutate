# E004 design part 2b (T0457): banded acceptance, redraw record, 2R proxy pair, provenance, solve-stage fixes, local FastHenry probe

Status: research and design note, not evidence. Development geometry only (2D_Case_4, the Case 4 twin, development
seeds; O004 F2). Founder decisions are cited as "founder decision, O004 state log, 2026-11-17T15:58:20 UTC" (banded
acceptance; D0024's open item, decided in principle) and D0024 items 1-5.

## 1. What changed (facts, checkable in the diff)
- `experiments/runners/e004_run.py`
  - Banded acceptance (`bands`, `band_fill`, `initial_slots`, `config.banded_acceptance`): the first draw is unchanged
    (perturb.draw with `reference_seed`). While a band has a deficit, the next redrawable slot in cyclic order is redrawn
    with `perturb.draw(ref, {kind: 1}, redraw_seed(s, slot, pos, n))`. The slot keeps its kind, so every move type keeps
    its pair on each reference. The new pair is accepted only if its geometry is new and it lies in a band that has a
    deficit. A slot can be redrawn only if no band needs it and it is not the only single pair covering its type
    (6 % rule). Limits: 100 per slot and 600 in total, fixed before the simulation ran. Registration refuses
    (`banded_acceptance_filled`) when a band cannot be filled within them. The bands are "< 0.90 (at least 3)" and
    ">= 0.98 (at least 1)", with a pair counting only if it is in the band at both frequencies. The lower end is NOT a
    band: `l1_span` still requires min r <= 0.75.
  - Redraw record (`DrawObserver`, `redraw_class`, `move_type_restrictions`): every rejection inside perturb.draw is
    recorded with move type, reference, class, exception type and message. The observer wraps perturb's
    `_draw_params`, `apply` and `check` and restores them afterwards. The `observer_transparent` self-test, and the
    smoke's seed_provenance replay without the observer, show that it does not change the draws. A reference defect
    ('exactly one trace in the reference', 'no HS/LS die', 'not on one row') or an unclassified exception fails
    `redraws_classified`, which refuses the registration (reviews T0446, T0452).
  - The 2R proxy pair (`build_proxy`, D0024 item 3): E010's `judged_reference(2D_Case_2R)` (in smoke, E010's
    `dev_reference('case4')`), then `twin.twin`, then `control.proxy_descent(step_mm=1, step_limit=400)`. The ratio is
    taken against the frozen reconstruction. The T0444 lattice record goes to `proxy_on_lattice`, which refuses if any
    visited layout or the end point is off the lattice.
  - seed_provenance: in registered mode, `run.seed` is checked against the registry's minted commitment
    (`mfos.experiments.commitment`). Every slot's draw seed, its first draw and the whole banded redraw sequence are
    then replayed, without the observer, from the seed read again.
  - Solve stage: references are compared with the registration record's fingerprints; K1's argmax pair and its
    `excluded_f1` flag go into criteria; zero-failure bounds are given only for strata whose counted pairs all meet A1
    (otherwise `conditional`, null); coverage after exclusion uses the 6 % rule; the covered range uses counted pairs
    only; the discretisation band goes into `solve.json` as a band, not as a `ci=`; `fh_terms(at=...)` is asserted in
    FH_LADDER; `fh_level`'s unused parameter is gone; the L1 mesh flag uses max(|r4-r2|, |r4-r1| + gci_capped(r4,r2,r1));
    timeouts are asserted to fit `timeout_min` at plan time; a memory-killed FastHenry run is retried once, alone, at the
    full budget; `fh_thickness_share_of_cap` is added per pair row.
  - `--selftest`: 20 hand-built cases, including the monotone ladder, the F1 cap at E_R/r = 0.49999 % / 0.50001 %, a
    missing FastHenry finest value with K1 firing elsewhere, the K1-saves-from-INVALID branch and its converse, K1 on an
    excluded pair, conditional bounds, and stage_solve with a built proxy record and stubbed solvers.
- `research/o004_f7/fh_local_probe.py`: full local multipole solves of the Case 4 k0 decks, one at a time.

## 2. Results
### 2.1 Smoke registration (development seed, Case 4 in both slots; command `--smoke --stage registration`, exit 0)
- Every registration check passed. The banded rule filled after 79 redraws (mean 6.6 and max 8 per slot). The replay
  re-derived all 12 slot draws and all 79 redraws exactly.
- Internal redraws: only drc, not_one_polygon ('<net> copper is not a single polygon after the move') and duplicate.
  No reference defect and no unclassified exception occurred, and no move type is restricted on Case 4.
- The Case 4 twin's proxy took 38 one-mm steps to a local optimum. Its r_L1 is 0.663, against 2D_Case_4's base. All 39
  visited layouts and the end point are on the 1 mm lattice, and the end point is also on the 0.5 and 0.25 mm
  lattices. No step was a non-integer jump.
  - Fact: `land_HS` and `land_LS` (the wire-landing parameters) are off whole mm already at the twin start, and
    `perturb.on_lattice` does not test wire landings.
  - Inference: D0024 item 3's "on the 1 mm lattice by construction" holds for l2_layout's lattice (traces, planes,
    dies), not for every generator parameter. This needs the founder's reading; no builder change is indicated by Case 4.
- `l1_span` passed in smoke only because the Case 4 proxy (0.663) is pooled.
  - Inference: this does not carry over to 2R. Its in-domain proxy pin is 0.914 at 0.5 mm steps
    (tests/unit/optimize/test_control.py), so on 2R the proxy is not expected to reach the lower end.
- The 2R proxy's lattice check runs only at registration (F2 forbids L1 on 2R before then). On a failure, registration
  refuses with the builder-change message.

### 2.2 Development simulation of the banded rule (`--dev-band-sim 200`, research/o004_f7/band_sim_case4.json)
Setup: rules_sha256 2dbd9977...; 2D_Case_4 in both slots; seeds DEV_SEED+1000+k for k < 200 (the T0388 span-sim seeds);
no proxy pair. Intervals are Wilson 95 %.
- Bands filled within the limits in 200 of 200 draws [0.981, 1.000]. Internal reference-defect or unclassified
  redraws: 0.
- Pass fraction of the full registration check (bands filled and O004's span at both frequencies) by lower end:

| lower end | pass | Wilson 95 % |
|---|---|---|
| 0.75 | 0/200 | [0, 0.019] |
| 0.76 | 0/200 | [0, 0.019] |
| 0.78 | 0/200 | [0, 0.019] |
| 0.80 | 1/200 | [0.001, 0.028] |
| 0.82 | 5/200 | [0.011, 0.057] |
| 0.85 | 19/200 | [0.062, 0.144] |

- Each draw's lowest r_L1 at 20 MHz after the rule: min 0.7987, 5 % 0.839, quartiles 0.8645 / 0.8752 / 0.8822, 95 %
  0.8896, max 0.8953. Before the rule (first draw): median 0.9078, max 0.9857.
- Redraws per slot: mean 7.6, max 47. Mean by kind: die_row_shift 4.1, compound 7.8, others about 8-9. Redraws per draw:
  median 72.5, mean 91.7, 95 % 232, max 424, against the limit of 600. Fill fraction if the total limit were 25 / 50 /
  100 / 200: 0.10 / 0.30 / 0.63 / 0.93.
- Coverage under the 6 % rule, pooled over the two slots, after the rule (first draw): die_row_shift 0.96 (0.575);
  trace_width 0.155 (0.155); terminal_copper 0.09 (0.09); wire_landing 0.255 (0.255). Covered on each slot: 0.625 /
  0.01 / 0 / 0.02.
- Inference: the rule fills the two bands, but the lower end stays binding. It stops as soon as the bands are full and
  never searches downward, so no lower end at or below 0.78 passes in 200 draws; 0.85 passes about 1 in 10. A pass on
  the judged references needs either a lower end the bands can reach, or the lower end as a third band (section 3).
  Coverage of trace_width, terminal_copper and wire_landing stays low because the rule never redraws for coverage.
  That is reported, not checked.

### 2.3 Local FastHenry k0 solves (research/o004_f7/fh_local_probe.json; pinned binary eaa6d6fc...)
| deck | filaments | wall s (projected) | peak MB (projection x 1.3 margin) | peak / raw 31.1 kB per filament |
|---|---|---|---|---|
| case4_base k0 nh5 | 71,796 | 1115 (760), 1.47x | 3039 (2972) | 1.33 |
| dev03_trace_width k0 nh5 | 71,176 | 1372 (751), 1.83x | 3580 (2947) | 1.58 |

- Caveat: the band simulation ran on the same Mac at the same time, so some of the time factor may be CPU contention.
  Memory is not affected by that.
- Fact: both peaks exceed the projection. At cap = projection, as in T0389's job list, both runs would have been killed.
  The spec now sets cap = projection x 1.5, adds one retry alone at the full budget (memory_cap_policy), and takes the
  time factor 1.83 as the Case 4 calibration.
- Regenerated job list (research/o004_f7/vm_jobs_fasthenry.json):
  - F7(a) burst on e2-highmem-16, memory-packed at 108 GB with at most 6 jobs at once: 101.9 CPU-h, makespan 38.1 h,
    upper envelope 79.1 h (exponent 1.40 +- 0.30, a factor 2.1 at the k2 decks), USD 28-58. Launch with
    MF_GCP_MAX_HOURS=99.
  - E004 cost plan: 139.1 CPU-h (spec cpu_hours_est), makespan 16.8 h, suggested MF_GCP_MAX_HOURS=42.
  - The largest judged FastHenry timeout, doubled for its retry, is 341,381 s against timeout_min 360,000 s. It fits,
    with little margin.
  - gen2_0 g3's stale probe status is now 'timeout' (review T0455).
  - Per-pair thickness share of the 1 % cap: pending until the burst results exist (`thickness_share`).

## 3. Open items and caveats
- Inference: with the banded rule the registered sample is conditioned on L1 bands, so the zero-failure bounds describe
  the band-conditioned population (stated in `config.banded_acceptance.statistics_note`).
- Ambiguity for the founder: the founder's text names two bands. The lower end could be read as a third band ("at least
  1 at or below the lower end"). I implemented the text literally; the simulation reports, per lower end, the fraction
  that passes the full registration check after the two-band fill.
- Refreeze before registration: the proxy context imports experiments/runners/e010_run.py and reads E010.yaml. Their
  sha256 are recorded in the proxy record, and they are to be added to config.freeze at the refreeze.
- F3/F6 diagnostics and the F7(a) results (nh_lateral, the thin-stack gap) are still open.

---

# Attempt 2 (T0457-a2, 2026-11-17, founder session rebrief)

Status: research and design note, not evidence. Development geometry only (2D_Case_4 and its derivatives, development
seeds; O004 F2). Founder decisions: banded acceptance, founder decision in the O004 state log, 2026-11-17T15:58:20 UTC
(D0024's open item, decided in principle); D0024 items 1-5. The frozen rule (`bands`, `band_fill` without `band_list`)
is unchanged, and 0.75 stays the span's lower end in the code.

## A2.1 What attempt 2 changed (facts, checkable in the diff)
- `experiments/runners/e004_run.py`
  - `in_band` also knows `'<='` and `'cover'` (a single pair of a move type with |1 - r_L1| >= 6 % at both
    frequencies). Only the research variants use them. `band_fill(..., band_list=None)`: registration never passes
    `band_list`, so the frozen bands are used as before. New self-test `research_band_ops` (21/21 pass).
  - `BAND_VARIANTS`, `variant_bands`, `dev_band_variants`, `summarize_band_variants`, and the CLI
    `--dev-band-variants N --shard I/M|pool [--summarize-only]`. `_Memo` caches `draw_pairs` and the L1-only
    `pair_records` across the four variants of one seed, and the frozen functions are restored afterwards. Check: with
    the memo and `observe=False`, development seeds k = 0 and 1 reproduce attempt 1's frozen-rule results exactly (same
    final r_L1 and the same 90 / 104 redraws). Pool mode claims seeds with O_EXCL files
    (`research/o004_f7/band_variants_claims/`). Seeds computed twice are compared, and they must agree exactly.
  - `dev_fh_plan`:
    - Local factors are keyed per probe entry, so a repeat of a deck does not overwrite the first solve.
    - Level families: 'k' (k0/k1/k2/k1w) and 'g' (the gen2_0 diagnostic levels). A local timeout gives a lower bound
      on its deck's factor.
    - An exponent refit is attempted. There is no slope, because the k-level points span only 71-74k filaments.
    - New `memory_calibration` and `level_risk` records (the factorial and the direct k1 multiplier, section A2.4).
    - The E004 cost plan has an upper envelope, and its MF_GCP_MAX_HOURS is derived from that envelope.
    - Every job carries `timeout_covers_upper_envelope`.
- `research/o004_f7/fh_local_probe.py`:
  - `job@tag` repeats a deck under its own key.
  - The 1/5/15-min load averages before and after each solve are recorded.
  - Ratios are taken against the raw (uncalibrated) projection.
  - `CUSTOM` level-factorial decks, which are not in the job list. Their timeout is 8x the raw projection, with a
    minimum of 900 s.
- `experiments/drafts/E004.yaml`: `memory_cap_policy` now cites all four k0 measurements. `cpu_hours_est` is taken from
  the regenerated plan (section A2.5).

## A2.2 Process incident (fact)
- Attempt 1's probe process outlived attempt 1. It was still solving `case4_base__fh_g1` when attempt 2 started, and it
  wrote its timeout record at 17:47:51.
- Attempt 2 started its own g1 solve at 17:23 without knowing this. `ps`, `pgrep` and `top` are blocked in this sandbox,
  so the old process could be neither seen nor stopped.
- From 17:25 to 17:48 three of the agent's compute processes ran at once: two FastHenry solves of at most 0.9 GB each,
  and the 0.15 GB simulation. The total stayed far below 5 GB, but the count broke the two-process rule.
- Attempt 1's record is kept as `case4_base__fh_g1@attempt1`. Both g1 solves are timeouts at 3600 s.

## A2.3 Span-decision variants of the banded rule (research only; the frozen rule is unchanged)
### Setup
- Simulation: `--dev-band-variants 200`. Files: research/o004_f7/band_variants_case4.shard0of2.json and .pool81526.json,
  with the summary in band_variants_case4_summary.json.
- Same 200 development seeds as attempt 1 (DEV_SEED + 1000 + k), 2D_Case_4 in both slots, rules_sha256 2dbd9977..., no
  proxy pair.
- The frozen limits apply: 100 redraws per slot and 600 in total.
- (a) is the frozen rule plus the band "at least 1 pair <= X at both frequencies".
- (b) is (a) at X = 0.85 plus, for each move type, the band "at least 1 single pair of that type with |1 - r_L1| >= 6 %
  at both frequencies", pooled over the two slots.
- Intervals are Wilson 95 %.
- The fill fraction under a smaller total limit L is read off the run exactly: a draw fills under L iff it filled with at
  most L redraws, because the rule's sequence does not depend on the limit until it stops.

### Consistency checks (facts)
- All 200 first draws equal attempt 1's.
- In every (a) variant and every seed, the single-move final pairs equal the frozen rule's final pairs. This is
  expected: (a) runs as the frozen rule until the frozen bands are full, and afterwards only a pair <= X, which on Case 4
  is always a compound, can be accepted.
- No variant used fewer redraws than the frozen rule.
- No seed was computed twice.

| rule | filled (limit 600) | Wilson 95 % | redraws/slot mean | max | fill @100 | @200 | @600 |
|---|---|---|---|---|---|---|---|
| frozen (attempt 1) | 200/200 | [0.981, 1.000] | 7.6 | 47 | 0.625 | 0.930 | 1.000 |
| (a) X = 0.85 | 77/200 | [0.320, 0.454] | 38.7 | 100 | 0.080 | 0.175 | 0.385 |
| (b) X = 0.85 + coverage | 89/200 | [0.378, 0.514] | 35.1 | 100 | 0.075 | 0.190 | 0.445 |
| (a) X = 0.82 | 16/200 | [0.050, 0.126] | 47.5 | 100 | 0.025 | 0.045 | 0.080 |
| (a) X = 0.80 | 2/200 | [0.003, 0.036] | 49.6 | 100 | 0.005 | 0.005 | 0.010 |

Pass fraction of the full check: the bands filled within the limits AND O004's span check at both frequencies with the
given lower end.

| rule | 0.75 | 0.76 | 0.78 | 0.80 | 0.82 | 0.85 |
|---|---|---|---|---|---|---|
| frozen | 0/200 | 0/200 | 0/200 | 1/200 [0.001, 0.028] | 5/200 [0.011, 0.057] | 19/200 [0.062, 0.144] |
| (a) 0.85 | 0/200 | 0/200 | 0/200 | 2/200 [0.003, 0.036] | 14/200 [0.042, 0.114] | 77/200 [0.320, 0.454] |
| (b) | 0/200 | 0/200 | 0/200 | 2/200 [0.003, 0.036] | 17/200 [0.054, 0.132] | 89/200 [0.378, 0.514] |
| (a) 0.82 | 0/200 | 0/200 | 0/200 | 2/200 [0.003, 0.036] | 16/200 [0.050, 0.126] | 16/200 [0.050, 0.126] |
| (a) 0.80 | 0/200 | 0/200 | 0/200 | 2/200 [0.003, 0.036] | 2/200 [0.003, 0.036] | 2/200 [0.003, 0.036] |

(0/200 has the Wilson interval [0, 0.019].)

Lowest r_L1 at 20 MHz per draw, after the rule:

| rule | min | 5 % | 25 % | median | 75 % | 95 % | max |
|---|---|---|---|---|---|---|---|
| frozen | 0.7987 | 0.8393 | 0.8645 | 0.8752 | 0.8822 | 0.8896 | 0.8953 |
| (a) 0.85 | 0.7929 | 0.8192 | 0.8426 | 0.8643 | 0.8790 | 0.8886 | 0.8953 |
| (b) | 0.7929 | 0.8160 | 0.8419 | 0.8582 | 0.8755 | 0.8882 | 0.8943 |
| (a) 0.82 | 0.7929 | 0.8161 | 0.8607 | 0.8732 | 0.8822 | 0.8895 | 0.8953 |
| (a) 0.80 | 0.7929 | 0.8389 | 0.8638 | 0.8750 | 0.8822 | 0.8896 | 0.8953 |

Coverage under the 6 % rule after the rule, shown as pooled / on each slot:

| rule | die_row_shift | trace_width | terminal_copper | wire_landing |
|---|---|---|---|---|
| frozen and all (a) | 0.960 / 0.625 | 0.155 / 0.010 | 0.090 / 0.000 | 0.255 / 0.020 |
| (b) | 1.000 / 0.725 | 1.000 / 0.010 | 1.000 / 0.000 | 1.000 / 0.020 |

Total redraws per draw and refusal reasons:
- Medians: frozen 72.5, (a) 0.85 600, (b) 522, (a) 0.82 600, (a) 0.80 600.
- Means: frozen 91.7, (a) 0.85 463.9, (b) 421.2, (a) 0.82 570.1, (a) 0.80 594.8.
- Refusals:
  - (a) 0.85: 122 at the total limit, 1 with no redrawable slot.
  - (b): 31 at the total limit, 80 with no redrawable slot.
  - (a) 0.82: 183 at the total limit, 1 with no redrawable slot.
  - (a) 0.80: 197 at the total limit, 1 with no redrawable slot.
- Under (b) the coverage bands always filled; every refusal was the <= 0.85 band.
- Every pair in the extra band, in every variant, was a compound: 78, 90, 16 and 2 pairs.
- Redraws per slot by kind, mean/max:
  - (a) 0.85: compound 32.4/100, die_row_shift 14.2/98, terminal_copper 53.9/100, trace_width 51.4/99,
    wire_landing 47.7/100.
  - (b): compound 39.1/100, die_row_shift 12.7/100, terminal_copper 43.4/100, trace_width 38.9/100,
    wire_landing 37.3/100.

### Inferences (not tested further)
- On 2D_Case_4 only compound moves reach r_L1 <= 0.85. Attempt 1's redraw log gives 0.28 % of compound redraws at
  <= 0.85, 0.07 % at <= 0.82 and 0.01 % at <= 0.80, and no single move ever went below 0.873.
- The cyclic rule spends about 2/3 of its redraws on single-move slots that can never fill a low band. The limits
  therefore bind:
  - At most 4 x 100 compound redraws are possible per draw, and the 600 total in cyclic order allows about 200 of them.
  - Even with the extra band, no lower end at or below 0.78 passes in 200 draws. The lowest pair seen on the 200
    seeds under any of the five rules is 0.7929 (the rules share their redraw streams, so these are not independent).
- (b) fills more often than (a), 89 against 77: an interval-overlapping difference, so not established.
  - Plausible mechanism: pairs held by the coverage bands become non-redrawable, which moves the cyclic redraws toward
    the compound slots.
  - (b) also ends far more often with "no slot can be redrawn" (80 against 1). The per-slot limit of 100 on the compound
    slots is reached.
- What this means for the span decision. On Case 4 neither a band at X nor a coverage band makes a lower end of 0.80 or
  below reachable within the frozen limits. Even 0.85 fills in only 39-45 % of draws.
- Speculation, not simulated: a rule that redraws only the slots of kinds that can reach the band in deficit (compounds
  for a low band) would fill X = 0.85 much more often for the same total. The judged references' compound reach is
  unknown before registration (F2 forbids L1 span work on 2R / Case 6 beyond the registered draw).

## A2.4 Local FastHenry measurements (research/o004_f7/fh_local_probe.json; pinned binary eaa6d6fc...; one solve at a time)
This section supersedes section 2.3's "time factor 1.83 as the Case 4 calibration" reading, and its count of probed decks.

| entry | level | filaments | status | wall s | raw projection s | factor | peak MB / projection | 1-min load before |
|---|---|---|---|---|---|---|---|---|
| case4_base k0 nh5 (a1) | k0 | 71,796 | ok | 1115 | 760 | 1.47 | 1.02 | not recorded |
| dev03_trace_width k0 nh5 (a1) | k0 | 71,176 | ok | 1372 | 751 | 1.83 | 1.21 | not recorded |
| case4_base k0 nh5 @solo | k0 | 71,796 | ok | 764 | 760 | 1.005 | 0.91 | 4.4 |
| standin_compound k0 nh5 | k0 | 74,346 | ok | 1131 | 798 | 1.42 | 1.20 | 3.7 |
| case4_base g1 (a1) | g1 | 34,192 | timeout | 3600 | 269 | >= 13.4 | 0.45 (at timeout) | not recorded |
| case4_base g1 | g1 | 34,192 | timeout | 3600 | 269 | >= 13.4 | 0.61 (at timeout) | 4.0 |
| fhx B: k0 lateral, nh 1, wire 2/1 | custom | 14,436 | ok | 127 | 80 | 1.57 | 0.54 | 4.1 |
| fhx B + wire_sub 2 | custom | 14,532 | ok | 171 | 81 | 2.11 | 0.54 | 4.0 |
| fhx B + cell 0.5 mm | custom | 34,096 | ok | 1688 | 268 | 6.30 | 0.64 | 4.9 |
| fhx k1 lateral (cell 0.5, plane 1, wire 4/2), nh 1 | custom | 58,648 | timeout | 4581 | 573 | >= 8.0 | 0.36 (at timeout) | 4.0 |

### Facts
- On every slow deck the log tail shows the preconditioner built in 24-42 s. The time went into the phase after it, and
  the solve was CPU-bound (cpu_s within 1 % of wall_s): not swap, not I/O.
- The Mac was shared with another agent throughout, with a 1-min load of 3.7-4.9.
- The k0 measurements were 0.91-1.21 x the memory projection, under cap_factor 1.5 (24 % headroom over the largest).

### Inferences
- The k0 time rule (t_ref (F / f_ref)^1.4) is accurate when the machine is not overloaded: 1.005 on the solo repeat of
  the same deck. Attempt 1's 1.47-1.83 is mostly contention. The plan keeps the largest k0 factor, 1.83, as a
  conservative calibration.
- The g-level misses are not specific to gen2_0. Case 4's own g1 deck misses by at least 13.4x, twice.
- In the factorial against base B (1.57x), wire_sub 2 alone gives 1.34x B, and the 0.5 mm cell alone gives 4.0x B. That
  4.0x sits exactly on the 4x threshold I set before the run (6.2972 against 6.2980), so the binary reading is not used.
  Both features together (g1) give at least 8.5x B, more than the product of the two. k1's own lateral level gives at
  least 5.1x B.
- So the 0.5 mm trace cell, not gen2_0's thin stack and not wire_sub alone, drives the miss. The k1 decks (cell 0.5 mm)
  and k2 decks (0.25 mm) of E004 and F7(a) should be expected at 5x or more their k0-calibrated projection.
- Speculation, untested: slow iterative convergence at the finer cells. A VM run that logs FastHenry's iteration counts
  on one k1 deck would discriminate.

### How the plan uses this (`projection.level_risk`)
- Central projections: k1 decks x m1 = 5.08, a lower bound because the k1-lateral deck timed out; k2 decks x m1.
- Upper envelope: k2 decks x m1^2 = 25.8, a geometric extrapolation per halving of the cell, an assumption. On top of
  that comes the exponent envelope ((F / f_ref)^0.3, a factor of 2.1 at 1.2 M filaments).
- The exponent could not be refitted: the k-level local points span only 71-74k filaments.

## A2.5 Regenerated job list (research/o004_f7/vm_jobs_fasthenry.json, `--dev-fh-plan`)
### F7(a)
- Machine e2-highmem-16, memory-packed at 108 GB with at most 6 jobs at once (never by CPU count), 24 jobs.
- 502.5 CPU-h. Makespan: 193.7 h central, 2042 h upper envelope.
- USD 141 central, USD 1491 upper.
- MF_GCP_MAX_HOURS = ceil(1.25 x the upper makespan) = 2553 h.
- The three Case 4 k2 decks (1.16-1.21 M filaments, 47-49 GB projected) dominate. Their timeouts (10 x the calibrated
  projection) do not cover their upper envelope (`timeout_covers_upper_envelope: false`).
### E004 cost plan
- 15 layouts, 518.2 CPU-h (`cpu_hours_est` set to this). Makespan 64.7 h central (14 jobs at once), 436.2 h upper.
- USD 47 central, USD 319 upper.
- MF_GCP_MAX_HOURS 546.
- `timeouts_fit` is **false**: the 2D_Case_2R k2 deck's timeout of 867,288 s, doubled for its retry, is 1,734,576 s,
  against timeout_min 360,000 s. The registered solve stage would refuse before any solve, as item 10 intends.
### Thickness share (T0454 item 6)
- Thickness-term share of the 1 % cap per pair: still pending.
- It needs the F7(a) k1 nh 3/5/9 results. No k1 deck fits the local 3 GB rule at nh >= 3 (the smallest, case4_base
  k1_nh3, is 7.1 GB projected).

## A2.6 Definition of done (run 2026-11-17 ~20:55 PST, after the last edit)
`--selftest` 0 (21/21) · `--smoke --stage registration` 0 (all 18 checks pass, proxy built, 133 s) · `mfos exp check
E004` 0 · job-list assert 0 · `ruff check experiments/runners/e004_run.py` 0 · `mfos gate --fast` 0.

## A2.7 For the founder (recommendations; no frozen rule, objective or spec timeout was changed)
1. **Span decision.** On Case 4, neither variant makes a lower end <= 0.80 reachable within the frozen limits, and 0.85
   fills in 39-45 % of draws. If a lower band is wanted, the redraw rule probably has to target the compound slots
   (not simulated).
2. **Burst 2.** Do not launch F7(a) as planned. The k1 / k2 decks are expected to run at least 5x slower than projected,
   and the Case 4 k2 decks could take weeks.
   - Suggested first VM step: one full k1 solve, case4_base k1_nh3 (174k filaments, 7.1 GB), with iteration logging.
   - Then decide whether to drop or replace the Case 4 k2 decks.
   - Then recalibrate.
3. **E004 timeouts.** Before registration, decide on the timeout rule (10 x projection), timeout_min (100 h) or the
   ladder. Under the measured k1 factor, the registered stage's timeouts, set from the raw projection, would also cut
   off k1 / k2 solves, at 8x or more the rule against a timeout of 10x.
4. **Refreeze items** are unchanged from section 3: the e010 runner and spec, then F3 / F6.
