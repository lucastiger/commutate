# E011 design, T0382 attempt 2 (scientist, 2026-11-16)

## Facts
- The founder's ordering (2026-11-17, item 1) puts source fixes in `src/moduleforge/optimize/control.py`,
  `src/moduleforge/optimize/nulls.py`, `tests/unit/optimize/test_control.py` and `tests/unit/optimize/test_nulls.py`
  first. The task's `touches` lists them, but the scientist role's write scope (`.mfos/policy.toml`
  `role_write_scopes.scientist = research/**, experiments/drafts/**, experiments/runners/**,
  tests/acceptance_drafts/**, project/memory/**`) and the packet's Boundaries section exclude `src/` and
  `tests/unit/`, and `.claude/hooks/guard.py` denies Edit/Write outside the scope. None of these fixes is made here.
  Current state, checked by reading the sources: `control.draw_degradations` still seeds attempt `a` of draw `j` with
  `SeedSequence([sealed_seed, layout_index, j, a])` (no domain tag); `nulls.py` has no `no_moves` terminal, no
  `seed_in_domain` in its stats and no `dies_fixed` argument; `test_nulls.py` has no `slow` marks.
- Because the seed-tag fix changes every degradation draw, the development L1 run (`--dev`) was **not** rerun: rows
  from today's control.py would not come from the code that will be frozen (founder item 3).
- Attempt 1's checkpoints were moved to `research/o008_e011_dev/work.attempt1-stale` (gitignored). The runner now
  refuses them: `--dev --workdir research/o008_e011_dev/work.attempt1-stale` raises `StaleCheckpoint` (exit 1) before
  any stage runs.
- `experiments/drafts/E011.dev_jobs.json` is still attempt 1's partial schema-1 manifest. It is now marked
  `stale: true` with a reason, and `--dev-solve` refuses it (exit 1: schema 1, status not complete, no code stamp).

## Runner changes (experiments/runners/e011_run.py), all exercised by `--selftest`
1. `dev_solve` keys jobs by (fingerprint, level). It asserts that the jobs submitted equal `totals.jobs_wave1`, the
   manifest's job count, and the number of distinct outputs. It rebuilds each layout once per fingerprint, with the
   fingerprint checked.
2. `Solves.run` records every purpose and shortlist rank of a deduplicated job. The manifest (schema
   `e011.dev_jobs/2`) carries `purposes` per job. `dev_solve` rebuilds the shortlist groups from all purposes and
   picks each best by (L at screen_level, L1 rank). Group count, rank contiguity (0..n-1) and the wave-2 count are
   asserted.
3. `em_ok` and `dev_solve` use E010's predicate (`e010_run.band_solve_failures`): a missing convergence record, a
   GMRES flag other than 0, a non-finite `L_H` or `solver_tol_rel_L_max`, or a failed record is not converged.
   `dev_solve` exits 3 unless every job has a converged result.
4. Work directories carry `code_stamp.json`: a sha256 over `src/moduleforge/**/*.py`, e010_run.py and e011_run.py,
   plus the stage-setting config blocks. A different stamp, or checkpoints with no stamp, are refused. The manifest
   carries the stamp, and `dev_solve` refuses a mismatch.
5. `seed_streams_distinct` is now computed from the run's own sub-seeds and recorded degradation entropy lists (review
   T0432). It also reports whether control.py's entropy lists are domain-tagged; today they are not.
6. The improvement curve (founder item 4): per draw, the share of the final L1 gain made in the last 10 % and 25 % of
   the budget, with per-layout medians. It is exact when the last improvement came before the cut or when a
   shortlist member had been evaluated by the cut; otherwise it is a bracket (see `improvement_curve`'s docstring).
   Hand-checked in `_unit_checks`.
7. `em_ok` skips E010's Scheduler `<out>.job.json` files. Under the stricter predicate the first smoke run counted
   them as unconverged results; the fake scheduler writes none. A selftest guard was added.

Selftest case `_manifest_check`: a dev-mode run on fakes (2 layouts x 8 draws), then `write_manifest`, then
`dev_solve`. It produces 388 wave-1 jobs at all five levels, 34 shortlist groups and 170 wave-2 jobs, and every
(fingerprint, level) has a result. It also checks the refusals and the predicate. Mutation check: re-inserting
attempt 1's fingerprint-only keying makes the selftest fail (dev_solve raises "116 jobs built ... totals.jobs_wave1
388"). So does keeping only the first purpose (the alt_short_d0 groups disappear, and dev_solve exits 3).

## Inferences
- Once the source fixes land, the remaining work is mechanical: rerun `--dev` (2D_Case_2R, then 2D_Case_4, resuming
  across 2-hour commands; the stamp guarantees one code version), then `--freeze-report`, then fill code_sha256 and
  frozen_sha256. The VM sizing comes from the regenerated manifest's `jobs_by_level` and `est_peak_GB`. From E010's cost
  model on the layout areas (computed here, not measured on solves): Case 4 at lat0.25 has 4.11 M unknowns, 1.60 h,
  15.8 GB by model and 25.3 GB with the level prior 1.6. That is 2 at once in the 66.3 GB usable on
  n2d-custom-8-81920, not the 4 the spec's registered-run cost line assumed. Consequence (inference): about 136 h of
  makespan for Case 4's roughly 170 registered 0.25 mm solves, above timeout_min = 120 h, and about $105 for the
  registered run. At 3 at once (measured memory at the model x 1.1) it is about 91 h and about $80. Recorded in the
  spec as cost_estimate.sizing_check_attempt2 for the founder.
- `mfos gate --fast` timed out (900 s, unit tests) while a smoke run shared the CPU. Run alone it passed. The
  unmarked long tests in test_nulls.py (T0426 item 4, a pending source fix) leave little margin.
- The reach=True proxy pin (2R: 25 steps, L1 ratio 0.9138 before the seed change) is unaffected by the degradation
  seed change. The proxy descent is deterministic and does not use the degradation streams. This is an inference
  from reading control.proxy_descent's call path, not a measurement.

## Not done (needs the founder)
Either extend this task's write scope to the four source and test files, or split them into a builder task. Then
rerun T0382's steps 3-5.
