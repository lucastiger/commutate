# E011 development L1 run (O008), T0382 attempt 4

Author: the scientist agent, T0382 attempt 4, 2026-11-17. Sections are labelled **Fact** (measured or read from a file
named here), **Inference** (follows from facts by a stated argument) and **Speculation**. The run used development
seeds only (dev_seed 20261116). No sealed seed was used, and no file under `data/holdout/` was read.

Sources: `experiments/drafts/E011.dev_jobs.json` (the manifest the runner wrote),
`research/o008_e011_dev/dev_summary.md` (all tables, written by `research/o008_e011_dev/summarize.py` from the
manifest and from the run's own code-stamped stage checkpoints in `research/o008_e011_dev/work/stages/`), and the run log
`research/o008_e011_dev/work_dev.log`.

## 1. What was run, on which code

**Fact.**
- The branch has T0437's code, because the founder merged main into it (8a8b8fc1). Before the run I read the sources:
  - `control.DEGRADE_TAG = 0x4D460D01` comes first in `control.degrade_entropy`;
  - `nulls.NO_MOVES = "no_moves"`;
  - `NullResult.stats` carries `seed_in_domain` and `n_neighbours_step0`.
- Runner changes, all made before the run. The code stamp hashes `e011_run.py`, so none could come after.
  1. `--dev-solve MANIFEST --dry-run` makes the same refusals, rebuilds and count assertions as a real `--dev-solve`, and solves nothing.
  2. `cached()` writes each stage's compute wall time beside its checkpoint.
  3. `vm_sizing` gives at-once counts under the prior and the learned memory figure. It also gives the burst makespan
     with wave 2, and a phase-sequential model of the registered run checked against `timeout_min`.
  4. The selftest gained a dry-run case and a sizing check.
- The spec's stamped blocks (`frozen`, `dev`) were edited before the run. `frozen.dc_minus_reading` now cites T0437's
  pins instead of attempt 1's draw-0 numbers.
- The first `--dev` start (09:01) died at 09:19 inside the manifest hook: `E010.simulate` raised "unschedulable: []".
  The cause was my sizing model, which built a phase group with no jobs in mid-run. I fixed it: empty phases are
  skipped, and a sizing error is recorded instead of raised. I exercised the fix on fakes through 18 hook calls. That
  directory has another code stamp; it is kept as `work.attempt4-aborted-sizingbug` and was not reused.
- The second start (run 1) ran from an empty work directory, 09:23 to 11:08 (local), exit 0. Its manifest failed the
  definition-of-done check `set(d['layouts'])`: `layouts` was a list of records, which are unhashable. I changed
  `write_manifest` to key `layouts` by layout name, with a `rows_l1` table (the L1 columns of every row), and added a
  selftest assertion for both. That changed the code stamp, so run 1 was moved aside (`work.attempt4-run1-listlayouts`)
  and not reused.
- The final run (run 2) started from an empty `research/o008_e011_dev/work` on the final runner code. It ran 11:12 to
  13:10 in one command, exit 0, and the manifest status reads `complete: L1 stages done, L2 pending (burst VM)`.
- **Reproducibility (fact).** Runs 1 and 2 give the same 611 (fingerprint, level) jobs with the same purposes and
  ranks. They also give identical per-layout records: proxy, sensitivity rows, draws, W*, Tj, degradation report,
  search curve, null steps, DC- comparison and streams. `dev_summary.md` differs only in the sizing lines, by at most
  0.4 h, because the measured L1 stage wall times differ (2R 0.81 h vs 1.05 h; run 2 shared the CPU with smoke and the
  gate).
- Code stamp: tree `33dac5c7b2fc7a5e…`, config `96d37c745505fde9…`. After the spec edits, `code_stamp(spec)`
  still equals the manifest's stamp (checked).

## 2. Per layout: frozen proxy, sensitivity rows, Tj

**Fact.** Every descent below ends at `local_optimum`, and the frozen W* is DRC-clean and inside `in_domain(reach=True)`.

| | 2D_Case_2R | 2D_Case_4 |
|---|---|---|
| frozen proxy (reach=True, min_gain 1e-12 H): steps, L1(W*)/L1(W) | 25, 0.9138 | 73, 0.6533 |
| threshold-free (min_gain 0) | 35, 0.9136 | 81, 0.6532 |
| probe proxy (reach=False, DRC only) | 27, 0.8979 | 120, 0.6280 |
| dies-fixed (Tj fallback candidate) | 17, 0.9302 | 63, 0.7014 |
| DC- read +1 | 23, 0.9149 (another layout) | 73, 0.6533 (same layout) |
| hottest-die Tj at thermal level 0: W, W* (K) | 398.10, 396.49 | 398.08, 396.05 |

- Both frozen-proxy values equal T0437's regression pins (2R 25 / 0.91379; Case 4 73 / 0.65327).
- The 2 K Tj fallback did not fire on either layout.
- W* is still provisional: locally it is the descent's end, and `choose_proxy` at 0.25 mm needs the burst.
- The DC- reading changes the proxy on 2R, not on Case 4. The search of draw 0 under the other reading reaches the same
  lowest L1 on both layouts (relative difference 0), with a different shortlist. The L2 comparison waits for the burst.

## 3. Degradations (F6 inputs)

**Fact.**
- 2R: 8 attempts. L1(D_j)/L1(W*) is 1.403, 1.309, 1.395, 1.434, 1.538, 1.421, 1.404, 1.392, so 7 of 8 reached the
  1.3875 L1 target. Draw 1 stalled at 1.309, and in the registered run it still costs an `r_d_at_l2` call.
- Case 4: 8 attempts, 1.390 to 1.421, 8 of 8 reached the target.
- No D_j lies outside `in_domain(reach=True)`. The searches and all 32 null runs were seeded in the domain.
- All 16 entropy lists start with DEGRADE_TAG.

**Limit.** Locally, every draw's attempt 0 is accepted provisionally, because R_D at L2 is a burst job. The L2 window
[1.25, 1.60] and the redraw rate are therefore not measured here. The nulls in section 5 ran on these draws, which hit
the L1 target that the frozen family uses to aim for the window (1.25 x 1.11). Whether they lie inside the L2 window
is pending.

## 4. The search's improvement curve (budget 2000 L1 evaluations)

**Fact.**
- All 16 searches stop at the budget (`stop_reason` budget, 2000 L1 evaluations).
- All 16 improved after evaluation 1800. The last improving evaluation is 1860 to 2000 on 2R and 1957 to 1998 on
  Case 4.
- The share of the final L1 gain made in the last 10 % and 25 % of the budget is computed by
  `e011_run.improvement_curve`. Every draw's value is a bracket (`exact` false): no shortlist member was evaluated by the
  cut. The upper end comes from the trajectory's running minimum; the lower end comes from the shortlist's highest L1.

| layout | last 10 %: median (max) upper end | last 25 %: median (max) upper end | lower ends |
|---|---|---|---|
| 2D_Case_2R | 0.001 (0.009) | 0.013 (0.030) | 0.000-0.005 |
| 2D_Case_4 | 0.028 (0.060) | 0.109 (0.162) | 0.002-0.013 |

**Inference.** The search is still improving when the budget ends on both layouts, but the late gains are small on 2R
(under 1 % of the final gain in the last 10 %). On Case 4 they are larger: up to about 6 % of the gain in the last
10 % and up to about 16 % in the last 25 %. Per-draw values are in `dev_summary.md`. The founder decides the budget;
it is unchanged.

**L1 indicator (not evidence; A1 is judged on L_sub at 0.25 mm).**
- **Fact.** L1(lowest-L1 layout of the search) / L1(W*), computed as L1(D_j)/L1(W*) x (1 - relative L1 gain):
  - 2R: 1.0059, 1.0453, 1.0233, 1.0552, 1.0080, 0.9965, 1.0112, 0.9987, so 5 of 8 are at or below 1.02.
  - Case 4: 1.0142, 0.9938, 0.9944, 1.0102, 1.0011, 1.0040, 1.0060, 1.0056, so 8 of 8.
- **Speculation.** If L2 tracks L1 within a shortlist (F4), 2R rather than Case 4 is the layout at risk for A1. That
  reverses the expectation in the spec (`expected_outcome.A1`). The burst's L2 rows decide; this note does not.

## 5. Nulls (b) widen and (d) compact (NULL_STEP_LIMIT 200)

**Fact.**
- All 32 runs (2 nulls x 8 draws x 2 layouts) end at `local_optimum`, with `seed_in_domain` true. None is capped and
  none is `no_moves`.
- Valid neighbours at step 0: 56 to 74.

| layout | widen steps | compact steps | changed params from D (widen / compact) |
|---|---|---|---|
| 2D_Case_2R | 14-26 | 21-36 | 7-12 / 9-15 |
| 2D_Case_4 | 30-58 | 53-73 | 11-18 / 15-21 |

**Inference.** At the frozen family's draws (L1 ratio 1.31 to 1.54), NULL_STEP_LIMIT = 200 is not approached. The
largest run is Case 4's compact at 73 steps. T0426 measured compact at 107 of 200 steps on Case 4 at R_D(L1) of
about 1.15 and asked whether runs at the registered range get capped. At the frozen family's L1 target, none does. The A3 margins against the in-domain
proxy need the burst's L2 rows.

## 6. Ablations

**Fact.**
- (c) random screen: `l1_evals` 2000 and `n_draws` 2000 on every draw of both layouts. Its budget counts sampler draws,
  and each draw cost exactly one L1 evaluation here.
- (e) proxy alone: 2R 28 to 42 steps (4 draws end at its budget, 4 at a local optimum); Case 4 29 to 35 steps (all at
  the budget). The budget is 2000 L1 evaluations and the step limit is 100000.

## 7. Burst job list and VM sizing (E011.dev_jobs.json)

**Fact (manifest).**
- 611 wave-1 jobs, one per (fingerprint, level): lat0.5 339; lat0.25, thk_c, thk_f and fil_f 68 each. Each job carries
  its level and every purpose (with its shortlist rank).
- 34 shortlist groups and 170 wave-2 jobs (the band of each group's best).
- `--dev-solve experiments/drafts/E011.dev_jobs.json --dry-run --workdir $TMPDIR/e011_dryrun` exits 0. It submits all
  611 (fingerprint, level) jobs exactly once, rebuilds and checks 339 fingerprints, rebuilds 34 groups, and would submit
  170 wave-2 jobs. Nothing was solved.

**Fact (measured memory).**
- `research/l2_thread_calib/summary.txt` gives 15.8 to 15.9 GB peak RSS for 2D_Case_4 at 0.25 mm (4.11 M unknowns,
  6268 to 6360 s pinned). That is 1.007 x E010's model (15.8 GB).
- The "about 25 GB each" figure is E010's scheduling prior (model x 1.6). The Scheduler uses it only until the first
  Case 4 0.25 mm solve finishes; after that it admits at model x 1.1 x 1.007 = 17.5 GB.
- This attempt's smoke measured gen2_0 at thk_c with 228,567 unknowns against a model of 281,064, so the model is 23 %
  high there. The spec's earlier "gen2_0 about 0.33 M at 0.25 mm" is wrong: it is about 1.8 M.

**Model output (E010 cost model + list scheduling; n2d-custom-8-81920, 66.3 GB usable, 8 vCPUs, 2 threads per solve).**
- Solves at once:
  - Case 4 at 0.25 mm: 2 under the prior, 3 after learning.
  - Every other (layout, level): 4, limited by vCPUs.
- Development burst: makespan 61.4 h (learned) to 71.5 h (prior), $38 to $44 including the 0.5 h overhead.
- Registered run, phases P, D, L1, S1 and S2 in order and layouts one after another, as `run_all` executes:

| memory | redraws | makespan h | USD | fits timeout_min = 120 h |
|---|---|---|---|---|
| learned | none | 170.2 | 104 | no |
| learned | every draw, all 4 waves | 198.0 | 121 | no |
| prior | none | 212.3 | 130 | no |
| prior | every draw, all 4 waves | 246.4 | 151 | no |

**Inference.**
- Case 4 alone takes about 109 h under the learned figure. 81 h of that is its 152 shortlist and end-point solves at
  0.25 mm, 3 at a time.
- T0382's earlier 91 to 136 h covered only those Case 4 solves. The full registered run (2R, Case 4 and gen2_0, with
  the band solves) exceeds 120 h in every scenario modelled.
- Possible responses, for the founder to choose: a longer timeout, a larger VM (more vCPUs and memory, so more Case 4
  0.25 mm solves at once), or running layouts in parallel or split. This design changes none of them.
- Uncertainty: the wall times are E010's model (alpha 1.44, calibrated on Case 4). gen2_0's model is 23 % high in
  unknowns. The L1 stage time on the VM assumes 1.8 x the Mac's (E010 cost basis).

## 8. Definition-of-done commands (this attempt; exit codes)

- `uv run python experiments/runners/e011_run.py --selftest` → 0 (SELFTEST PASS), run after each runner edit
- `E011_SMOKE_DIR=… uv run python experiments/runners/e011_run.py --smoke` → 0 twice: 618 s on the code before the
  last two runner edits, and 784 s on the final code. Both give the same metric values. The verdict preview is INVALID,
  as expected for smoke's single uncounted gen2_0 layout
- `uv run python experiments/runners/e011_run.py --dev --workdir research/o008_e011_dev/work` → 1 at 09:19 (the sizing
  bug above); 0 for run 1 (09:23 to 11:08); 0 for run 2 (11:12 to 13:10, final code)
- the manifest definition-of-done one-liner → 1 on run 1's manifest (unhashable layouts), 0 on run 2's
- `uv run python experiments/runners/e011_run.py --dev-solve experiments/drafts/E011.dev_jobs.json --dry-run …` → 0
- `uv run python experiments/runners/e011_run.py --freeze-report` → 0, `ok: true` after filling `frozen_sha256`
  (61c7abc9…) and `code_sha256` (control.py de00f8c9…, nulls.py da30f8e6…; the other three unchanged)
- `uv run mfos exp check E011` → 0; the definition-of-done spec-validation one-liner → 0
- `uv run ruff check experiments/runners/e011_run.py` → 0; `uv run mfos gate --fast` → 0 ("all gates passed"), on
  the code before the last two runner edits and again on the final code

## 9. What would show this note wrong

- If the burst's R_D values put most draws outside [1.25, 1.60], section 5's null steps were measured at
  unrepresentative draws.
- If `--dev-solve` (not the dry run) submits a different job count, the dry run's check is not the one that matters.
- If a measured Case 4 0.25 mm peak on the burst VM exceeds about 20.1 GB (admission is 1.1 x measured, and
  3 x 1.1 x 20.1 = 66.3 GB), only 2 run at once throughout, and the sizing moves toward the prior rows.
