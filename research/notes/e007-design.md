# E007 design: frozen L1 thermal model against the C004 reference on sealed generator layouts (T0397, O002)

Scientist, 2026-11-16 (attempt 1), revised 2026-11-17 (attempt 2, after reviews T0435 accept-with-caveats and T0436
reject). Covers `experiments/drafts/E007.yaml` and `experiments/runners/e007_run.py`. A design, **not evidence**.
Labels: **[F]** fact (checked here, or cited), **[I]** inference, **[S]** speculation. Decision record: **D0025**
(bound, sample, CPU-hour convention, frozen L1 calibration).

## 0. What changed in attempt 2 (by finding)
| finding | change | how it is checked |
|---|---|---|
| T0436 blocker: every null applied to A2 and A3, so A3 would be `non_discriminating` and E007 could never PASS | `null_baselines.applies_to` = [A1, A4] for all three nulls; rationale in `config.nulls.applies` | selftest: spec check; the evaluator's own `evaluate.null_check` on the fake m = 20 rows flags nothing and applies the nulls to A1 and A4 only (6 null lines); on the same rows the stratum-mean null's A3 upper bound is 0.413 K, so attempt 1's design **would** have been non-discriminating there |
| T0436 major: selftest never ran the real reference path; `node_count_growth` bypassed under FAKE; baseplate check trivially true | selftest runs one **real** level-0 P_ref calibration through a real child process; bypass removed | see section 5 |
| T0436/T0435 minor: seed check covered 2 of 6 streams | every stream seed recorded in `sub_seeds` and checked; all six streams must be present | mutations: a forbidden `timing_order`, `l2_subset` or `die_size` seed is caught |
| T0435: F7 draws not intersected with seen layouts | judged **and** F7-draw fingerprints checked against C004, T0393 and P_ref sets | mutation: a seen F7 draw is caught |
| T0435: F7 half-load L1 evaluations outside the L1 phase; rating check skipped F7 | F7 selection and half-load evaluations run inside the L1 phase (parent re-derives the selection and refuses a mismatch); `energy_balance` covers all 1,248 (selftest) L1 evaluations; `tj_max_within_rating` covers judged and F7 layouts | selftest |
| T0435/T0436: A5 wording | "after every P_ref calibration solve has finished and before any judged reference solve, with none running" | text |
| T0435: plan figures stale | `config.compute.plan_summary` regenerated from `--plan` | section 6 |
| T0435: freeze missed imported modules | `moduleforge/__init__`, `generate/__init__`, `geometry/__init__`, `conductors`, `units`, `solvers/__init__` hashed; `geometry/*.py` in `code_under_test` | `--verify-freeze` |
| T0436 minor: per-stratum A2 bound uninformative | each stratum's point, bound, maximum and an `upper_informative` flag, and counts | reported |
| T0435 notes: die-position A4 ≈ stratum-mean's; F6 estimate only on the subset; T0436 note: two power figures | stated in the spec (`config.nulls.applies`, F6 report scope, `config.bound.statement`) | text |
| D0025 (new on main) | cited for bound, sample, convention, L1 freeze; `ci` set on the recompute entries; `--dev` reports D0025 decision 4's per-stratum check | selftest |

## 1. What E007 measures
- **Reference.** [F] `solvers.thermal_fem` sha256 a216d5fe3209bcee... (`code_must_match` with O007's EV-O007-01) on
  the frozen GridRule `research/o007_dev3/frozen_config.json`, checked key for key, by file sha256 and against
  thermal_fem's production constants before any solve.
- **Judged level.** [F] Level 1: F1's development check (T0393) is `status: complete, level1: confirmed`
  (`research/o002_f1/f1_dev_check.json`, commit 87f639df), and D0025's context records the founder's level-2 burst
  (I0212) confirming it. The packet's stop condition does not apply.
- **Model under test.** [F] `moduleforge.thermal` (fv_coarse_xcal) as merged by T0395: GRID_RULE h0_max 1.5 mm,
  CALIBRATION 0.98544/0.98284/0.98298/0.98402 (4.0-5.5 mm), version o002-l1-cal-v2, frozen by value and by sha256
  together with every module it and the generator import. T0395's fresh-seed rows (seed 20261395) chose the grid:
  development rows, never judged evidence. T0395 changed `thermal_layout.py` (keyword overrides, defaults unchanged),
  so re-runs of E006, E008, E009 and E010 record a new hash for it with no change in behaviour.
- **Operating point.** [F] T_c = 338.15 K, h = 5000 W/(m² K). P_ref per stratum by C004's rule (level-0 calibration of
  the hottest node to 60 ± 0.25 K) on `generate_layouts(1, 20261101, family, dies, die_size_mm = the stratum's sealed
  size)[0]`, written to `pref.json` before any judged solve; never judged. Second load 0.5 P_ref.

## 2. Sample and frozen rules
- **Allocation.** [F] 300 layouts, 20 per (family, dies) stratum, 15 strata (f3_simulation.json), every (family, band)
  cell drawn. **m is provisional** (D0025 decision 2): the final m comes from T0398's power for the as-measured L1 at
  m = 20, 24, 32, 40. Only simulated m values are admissible.
- **Seed streams.** [F] `SeedSequence([seed, stream, *index])` for: die size per stratum (`draw_die_size_mm`), layouts
  per stratum, F7 pool strata, F7 draws per pool, the level-2 subset, the L1 timing order. All are recorded in
  `plan_frozen.json` and checked against `config.seeds.forbidden` (E009/C004 20261101; T0392 20261115/16; F3
  20261117/18; T0395 20261395; T0398 20261398; E009's sealed 831496695 and smoke 7; the AMG seed 20261103).
- **Level-2 subset** (F1): per cell one stratum, then 2 of its judged layouts; levels 0 and 2 at both loads (48
  solves); gates with `gci_step_floor(v0, v1, v2, 0.01 K)` and level-1 error = |v1 - v2| + estimate.
- **F7.** Two pools per cell, 40 sealed draws each; the optimised layout is the lowest L1 hottest-die average at P_ref;
  solved at level 1 at both loads; A1-type errors against the stratum's judged layouts, reported.

## 3. Rows, metrics, bounds, nulls
- **Rows** follow `research/o002_e007/e007_row_contract.md` (die, layout, switch kinds via the n5 helpers; no
  geometry). Judged pair rows are not written (the contract forms pairs inside `pairwise_diff_error_quantile`).
- **Recompute** entries for A1-A5 (K1-K3 share the A1, A2, A4 names) and the own-hottest A1, each with
  `ci: {scheme: woodruff, level: 0.94, cluster: layout}` except A5 (point). [F] On main the merged
  `mfos.metrics.quantile_ci` (da2118fc) equals the verbatim `e007_metrics.quantile_ci` on every entry of the selftest
  rows (exact tuple equality).
- **[F] This branch's base predates da2118fc**, so `uv run mfos exp check E007` **in this worktree** reports a schema
  error on `scheme: woodruff`. `experiments.validate_draft` run with main's committed tooling (`git archive da2118fc
  tools/` to a temp directory, `PYTHONPATH` to it) returns no problems. After the merge the check passes on main.
- **Nulls (F2).** (c) die position and (d) stratum mean / stratum-mean spread, per (stratum, switch) and
  leave-one-layout-out; (a) isolated die (`solvers.thermal_series.box_series`, die alone, constant k at 363.15 K,
  uniform substrate, plus the 1D die and attach resistance on the exact mean baseplate temperature).
  - `applies_to` = A1 and A4 for each. [F] O002 F2 requires each null to fail A1 and the spread nulls to fail A4; the
    hypothesis says A3 and A5 are each met by a layout-ignorant predictor, and A3's description that a stratum-mean
    spread may meet A3 alone. [F] Development data: stratum_mean and die_position A3-type 0.411 / 0.193 K
    (`research/notes/o002-l1-design.md`), under A3's 1 K.
  - [I] All three nulls predict spreads, so all three are applied to A4 (the stricter reading; a founder decision).
  - Gated `f2_null_discrimination`: on the judged rows at P_ref every null's **point** fails A1 (> 0.5 K) and A4
    (> 0.5), applies_to is exactly A1/A4, and no null meets either at its bound. A failure is a design error
    (INVALID). Whether to gate it or only report it is listed for the founder.
  - A2 and A3 of every null are reported (A2 also per stratum).
- **Per-stratum rule** (F3): A2 per stratum and A4 per band with the V4 bound; reported with an informativeness flag.
  [I] With 20 layouts a p95 bound at one-sided 97 % sits near the stratum maximum or at +inf for clustered errors; on
  the fake rows 12/15 were informative, 0/15 infinite. Real rows may differ.
- **Reported, not gated:** own-hottest A1; per-load A1-A3; per-band A4; F4 constant-k at both loads; F6 hottest node
  of every die and largest gap per stratum, its estimate on the subset only; F7; sample diversity (SD of the hottest
  die per stratum); D0025's per-stratum L1 check.

## 4. Sanity checks: the experiment is broken vs the hypothesis is false
- **The experiment is broken:** freeze, sealed_seeds_fresh, allocation_fixed, layouts_distinct_and_unseen,
  subset_frozen_before_solves, operating_point, energy_balance, picard_converged, linear_solver_headroom,
  baseplate_mean_consistent, rows_contract, f2_null_discrimination (design), recompute_consistency,
  l1_timing_single_thread.
- **The reference is not good enough** (F1, INVALID): f1_abs_die_average, f1_pair_difference, f1_spread,
  f1_level1_vs_level2, node_count_growth, tj_max_within_rating.
- **What would prove L1 wrong:** A1's or A4's upper bound above 0.5 with the F1 gates passing; K1-K3 kill on lower
  bounds.

## 5. Verification run here (commands, exit codes, outcomes)
- `uv run python experiments/runners/e007_run.py --selftest`: exit 0, 78 s, 0 failures. [F] Fake physics on the
  registered m = 20 (686 fake reference jobs, resume with 0 new solves, refusal of a foreign work directory), every
  sanity check passing including unbypassed node_count_growth, finite V4 bounds on every entry, the evaluator's null
  check, and mutations: wrong hottest die, 1 K hottest-die error, a null meeting A1, applies_to beyond A1/A4,
  forbidden stream seeds, a seen F7 draw. **Real physics:**
  - L1 on a judged u_shaped/2 layout: 0.39 s, energy balance 6.7e-16;
  - DOF growth of the 12 subset layouts (estimator): 7.33-7.66 per level, inside 8 ± 15 %;
  - one level-0 P_ref calibration of side_by_side/2's development layout (4.0 mm) through a real child process: P_ref
    38.979 W, rise 59.967 K after 3 solves, 25 s; energy balance ≤ 5.2e-14; Q1 bottom mean 344.624961037 K equal to
    T_c + Q_out/(hA) to the printed 9 decimals; Picard 3.6e-5 K; CG at most 96 iterations; DOF estimator exact
    (63,882); peak RSS 0.57 GB under the admission estimate 0.66 GB.
- The same selftest with main's tooling on `PYTHONPATH` (da2118fc): exit 0; `mfos.metrics.quantile_ci` used; the
  evaluator's `null_check` in bounds mode: A1-A5 satisfied on fake rows, every null `not_satisfied` on A1 and A4.
- `--verify-freeze` exit 0 (17 file hashes, GridRule, constants, L1 rule and table, allocation). `--plan` exit 0.
  `ruff` clean. Definition-of-done string check and thermal_fem hash check exit 0.
- **Not exercised:** a level-1 or level-2 real solve (3-5 GB and 28-45 GB); multi-process admission; the
  skip-over-cap branch. **The fake physics is not evidence that the nulls fail on real data:** that is
  `mfos exp check E007 --rows <T0398 dev rows>`, before registration.

## 6. Cost (`--plan`, development-seed proxies; process CPU time, D0025 decision 3)
- [F] 717 reference solves (600 judged, 24 F7, 48 subset, 45 calibration) and 1,693 L1 evaluations (0.3 CPU-h).
- [F] 56.7 CPU-h expected (61.1 if every die is 5.5 mm), within O002's 100, above policy `local_cpu_hours_max` 6, so
  burst per policy. Option A: 25.4 VM-h, $15.54 (upper 29.1 h, $17.79). Option B: 22.2 CPU-h locally (one solve
  at a time, about 22 h wall), then 22.6 VM-h, $13.84 (upper 26.3 h, $16.11).
- [F] Over the 5 GB local cap: level 1 of side_by_side/6, interleaved/6 and u_shaped/6 (5.0-5.5 GB), every level-2
  subset solve (28-45 GB expected, 48-77 min each), and in the upper case F7's 4-6 band.
- [I] CPU time = wall time assumed (one effective thread); level 2 is about 26 of the 57 CPU-h. D0025's "about 52
  CPU-hours" predates this plan; T0398 measures one level-2 solve.

## 7. Founder decisions before registration (also `config.founder_decisions_before_registration`)
1. m: 20 provisional (D0025 decision 2), final from T0398's power figures.
2. Registration waits for T0398's dev rows: `dev_rows` set; `mfos exp check E007 --rows ...` shows every null failing
   A1 and A4; D0025 decision 4's per-stratum check (1.8 % A2 guard, A4 ≤ 0.3) passes or the founder decides.
3. Null `applies_to`: A1 and A4 for all three (narrower or wider readings listed in the spec).
4. `f2_null_discrimination` gated on judged rows or report-only.
5. Compute location: option A (policy) or option B (split run, one work directory).
6. Null (a)'s 363.15 K and uniform-substrate simplification; F7's 40 draws and pool rule; A5's warm-up and ordering;
   pair rows per the contract; F6's estimate on the subset only; the yardstick assumes the 11-27 decision 5.

## 8. Running it (host settings)
`E007_MEM_CAP_GB` (admission cap, default 5 GB), `E007_MAX_PROCS` (admitted by memory, default 1), `E007_WORKDIR`
(checkpoint and resume), `E007_SKIP_OVER_CAP=1` (option B: solve what fits, stop listing the rest). Swap above
8 GB stops the run with checkpoints kept. Every reference solve is its own subprocess with an atomic checkpoint; a
stale checkpoint (other layout, power, level or code hash) is an error, never reused.
