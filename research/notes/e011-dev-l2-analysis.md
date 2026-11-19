# E011 development L2 analysis (O008), T0471

Author: the scientist agent, T0471, 2026-11-19. Sections are labelled **Fact** (read or computed from a file named
here), **Inference** (follows from facts by a stated argument) and **Speculation**. Development seeds and development
draws only (dev_seed 20261116). No sealed seed, no network, no VM, no new solve. Nothing under `data/holdout/` was read,
and no judged reference was opened.

**Bottom line (inference).** The burst confirms the provisional W* and the band bound. But on the development draws the
frozen design gives **A1 = 0.25** (2R passes 2 of 8 draws) and **A3 = 0** (blind compaction is not beaten on 2R).
The verdict on the dev rows would be INCONCLUSIVE. O008 F1 requires A3 met on development rows at registration, so
E011 cannot pass its own registration check as designed. Founder decision 1 below is blocking.

## 0. Sources and how every number is traced

- **Inputs (fact).**
  - `research/o008_e011_dev/dev_l2/`: the burst's results, 743 solved; the rows use 740 of them, the rest are the
    sensitivity proxies' 0.5 mm jobs counted separately.
  - `code_stamp.json` (sha256 256ff0e6…), `dev_solve_summary.json` (complete, converged; sha256 27abde60…).
  - `experiments/drafts/E011.dev_jobs.json`, the L1 manifest (sha256 17bd0a76…).
- **One command produced every number below (fact):**
  `uv run python experiments/runners/e011_run.py --dev-rows experiments/drafts/E011.dev_jobs.json --workdir research/o008_e011_dev/dev_l2`.
  It writes `research/o008_e011_dev/dev_l2/dev_rows.json`. That file has the keys `rows` (96), `per_layout`,
  `metrics`, `reported`, `recompute_check`, `band_bound`, `rank_stability`, `joint_oc`, `oc_lower_bounds`,
  `measured_sizing`, `measured_sizing_full_load` and `provenance`.
- **What the command checks (fact).**
  - The manifest's code stamp equals the burst's (tree 33dac5c7…).
  - Every result used has status ok and passes E010's convergence predicate (`em_failures`).
  - Each shortlist's best, re-derived by local_search's rule at 0.5 mm, equals the burst's selection, for all 34 groups.
  - It records a sha256 over the 740 result files it read (250fd827…).
- **Code checks (fact).** s and b are computed exactly as `run_layout` computes them:
  - s = L_sub(best)/L_sub(W*) − 1 at 0.25 mm;
  - b = 2 e_R by `mfos.metrics.ratio_band_estimate` over the five band levels.
  - The gated metrics come from e011_metrics and agree with mfos.metrics (`metrics.*.port`).
  - The spec's recompute entries, evaluated as mfos.evaluate does, give no discrepancy (`recompute_check` is `[]`).

## 1. W*, R_D and the redraw rate (task a1)

**Fact.**
- `choose_proxy` at 0.25 mm keeps the descent on both layouts, so the provisional W* holds.
  - L_sub(W*)/L_sub(W) is 0.9376 on 2R (L1: 0.9138) and 0.7176 on Case 4 (L1: 0.6533).
  - Across the five band levels the ratio moves by at most 7e-4.
- R_D = L_sub(D_j)/L_sub(W*) at 0.25 mm, per draw:

| layout | R_D, draws 0-7 | in [1.25, 1.60] | L1 ratio of D_j | (R_D−1)/(L1−1) |
|---|---|---|---|---|
| 2D_Case_2R | 1.290 1.209 1.281 1.296 1.406 1.285 1.288 1.310 | 7 of 8 | 1.309-1.538 | 0.68-0.79 |
| 2D_Case_4 | 1.286 1.288 1.288 1.279 1.305 1.290 1.300 1.285 | 8 of 8 | 1.390-1.421 | 0.70-0.74 |

- R_D at 0.5 mm differs from R_D at 0.25 mm by at most 0.0013.

**Inference.**
- Review item 7 holds: there is a systematic L2/L1 offset. L2 sees about 72 % of the planted L1 headroom (median
  ratio 0.72), so the L1 target 1.3875 maps to about 1.28 at L2. That is 0.03 above the window floor.
- The out-of-window rate is 1 of 16 (one-sided 95 % Clopper-Pearson upper bound 0.26), which implies about 0.07
  redraws per draw.
- A redraw aims at the same L1 target, so redrawing does not correct the offset. It only resamples the spread around
  1.28. Draws with a low L1 stop are the ones at risk: draw 1 stalled at L1 1.309.
- This is not an F6 risk at the current spread. Raising the L1 target would centre R_D in the window, but the target is
  a frozen value (founder decision 2).

## 2. Band b_j and the frozen bound (task a2)

**Fact.** b_j = 2 e_R per role. The bound (median b_j ≤ 0.01, max b_j ≤ 0.02) is gated on the search only.

| layout | search median / max | compact (d) median / max | widen (b) median / max |
|---|---|---|---|
| 2D_Case_2R | 0.0034 / 0.0061 | 0.0032 / 0.0068 | 0.0118 / 0.0171 |
| 2D_Case_4 | 0.0023 / 0.0027 | 0.0023 / 0.0048 | 0.0189 / 0.0250 |

- **The frozen bound holds for the search on both layouts.** It would also hold for compact. It would not hold for widen.
- No search draw lies within its band of the line (`within_band_of_line` 0 and 0). The conservative A1 equals the point
  A1 (0.25).
- `frozen.band_bound.development_value` is filled. That is the only change to `frozen`, so frozen_sha256 was refreshed
  (5f540d0a…). Every design value is unchanged.

**Inference.** Widen's large bands do not matter for A3: its s is 0.08-0.20, so s − b > 0.02 on every draw. The bound
does not need to change.

## 3. s_j, A1, A3, K1 on the dev draws (task a3)

**Fact (s_j at 0.25 mm, draws 0-7).**

| role | 2D_Case_2R | 2D_Case_4 |
|---|---|---|
| search | 0.022 0.044 0.025 0.050 0.042 −0.010 0.017 0.034 | 0.015 0.004 0.002 0.011 0.010 0.008 0.006 −0.001 |
| compact (d) | 0.034 0.056 0.030 0.059 0.072 0.012 0.014 0.100 | 0.023 0.032 0.011 0.027 0.017 0.025 0.015 0.014 |
| widen (b) | 0.117 0.091 0.086 0.090 0.161 0.078 0.081 0.182 | 0.178 0.203 0.128 0.095 0.112 0.123 0.157 0.148 |
| proxy alone (e) | 0.021 0.044 0.026 0.050 0.041 0.004 0.019 0.084 | 0.034 0.066 0.051 0.048 0.083 0.053 0.079 0.069 |
| random screen (c) | 0.102 0.073 0.081 0.095 0.092 0.094 0.099 0.054 | 0.016 0.042 0.064 0.052 0.068 0.035 0.043 0.038 |

- **Gated metrics:**
  - **A1 = 0.25.** 2R passes 2 of 8 draws; Case 4 passes 8 of 8. The Bonferroni CI is (0.022, 0.694).
  - **A2 = 0.**
  - **A3 = 0.** On 2R, compact has 6 resolved failures and 6 paired wins, below the 7 required. On Case 4, compact has
    exactly 4 resolved failures (at the line) and 8 paired wins. Widen is beaten on both layouts (8/8, 8/8).
  - **K1 = 0.0297** (2R median), so K1 does not fire. The Case 4 median is 0.0069.
  - Verdict on the dev rows: INCONCLUSIVE.
- `uv run mfos exp check E011 --rows research/o008_e011_dev/dev_l2/dev_rows.json` reports A1 not satisfied, A2
  satisfied and A3 not satisfied.
- F1(a): the seed null's s equals R_D − 1, which is at least 0.209, so it fails A1, as it must.
- Ablations: (c) has A1 0, K1 0.093. (e) has A1 0, K1 0.059. On 2R, the search's s is within about 0.01 of plain
  L1 descent (e) on most draws.
- L1 vs L2 on 2R (F4):
  - The L1 indicator (lowest-L1 layout / L1(W*)) had 5 of 8 draws at or below 1.02. L2 has 2 of 8.
  - Within each 2R shortlist, the Spearman correlation between L1 rank and L at 0.5 mm is −0.95 to 0.25 (median −0.35).
  - On Case 4 it is −0.14 to 0.99 (median 0.63).
- Improvement curve, L1 gain made in the last 10 % of the budget (manifest): 2R 0-0.9 %, Case 4 1.4-6.0 %.

**Inference.**
- Review item 6 is settled: **2R, not Case 4, is the A1 risk.** The old `expected_outcome.A1` text is withdrawn.
- On 2R the misses are an L1/L2 disagreement near the optimum, not a budget limit. 2R's search had almost stopped
  improving at L1, and its L1-best layouts are not the L2-best ones.
- Against compaction on 2R, the paired margin is missed on draws 2 and 6 (compact 0.030 vs search 0.025; 0.014 vs
  0.017). Compaction itself passes the 2 % line on draws 5 and 6 (0.012 and 0.014), so it has only 6 resolved
  failures.
- **Speculation.** A larger L2 shortlist, or an L2 re-ranking step on 2R, would address F4. Both are search-design
  changes for the founder (decision 1).

## 4. Ranking stability, 0.5 mm vs 0.25 mm (task a4, review item 3)

**Fact.**
- The burst solved only each shortlist's best at 0.25 mm. Every one of the 34 groups has exactly one member at both
  levels and none has two, so the within-shortlist ranking cannot be compared directly.
- Over every layout solved at both levels (51 on 2R, 50 on Case 4), q = L(0.25)/L(0.5) behaves as follows:
  - 2R: 0.9846-0.9870 (spread 0.25 %, sd 0.06 %);
  - Case 4: 0.9887-0.9936 (spread 0.49 %, sd 0.12 %).
- The 0.5 mm gaps from the best to the runner-up are 0-0.13 %.
- The four sensitivity proxies at 0.5 mm, as L/L(W*):

| proxy | 2R | Case 4 |
|---|---|---|
| threshold-free | 1.0001 | 1.0001 |
| reach=False (probe) | 0.990 | 0.973 |
| dies-fixed | 1.022 | 1.069 |
| other DC- reading | 1.0000 | 1.0000 |

**Inference.**
- The 0.25 mm best can differ from the 0.5 mm best in most groups. If it does, s changes by at most
  max(0, q-spread − gap): 0.25 points (2R) and 0.48 points (Case 4) (`selection_error_bound`).
- The direction is known. The registered rule takes the minimum L_sub over the same shortlist, so its s is never above
  the dev s for that shortlist. Every dev search s is therefore an upper bound (conservative) on the registered rule's
  s for that shortlist.
- This cannot rescue A1 on 2R. Of the six 2R misses, only draw 0 (s 0.0220) is within 0.25 points of the line.
- The reach=False and dies-fixed offsets (1-7 %) are 4 to 28 times the q spread, so their order relative to W* holds
  at 0.25 mm. Threshold-free (1.0001) and the other DC- reading (1.0000) lie within the q spread, so their order
  against W* is not resolved at either level.
- A direct measure would need the 113 (2R) + 118 (Case 4) non-best shortlist members at 0.25 mm. At the burst's
  measured walls (925 s and 3046 s) that is about 29 h + 100 h of solve time, about $30 on the 8-vCPU VM at 3-4 at
  once. **Not run.** The inference above makes it unnecessary for the registration decision.

## 5. Joint operating characteristic (task b, review item 1)

**Definitions, stated before computing.** The text is the same in `config.joint_operating_characteristic` and in
`e011_run.joint_oc`.

- **Estimand.** π = P(the registered run's verdict is PASS) over the sealed seed's randomness: degradation draws, and
  search and screen seeds. The verdict is judged as the evaluator judges it (s and b from L_sub at 0.25 mm), with W*,
  the code and the solver fixed. Also P(A1), P(A3), P(K1 not firing), P(INCONCLUSIVE) and P(FAIL).
- **It is not P(PASS) against continuum-exact inductance ratios.** O008 defines L_sub as l2_layout at 0.25 mm, and
  this method does not model discretisation error (b_j reports that per draw).
- **c.** s*_kj = (1+s_kj)/(1+c_k) − 1, with c_k = L_sub,run(W*_k)/L_sub,dev(W*_k) − 1. This is the relative
  difference between the registered run's single production solve of W*_k and the development solve. Every s on the
  layout shares it.
  - W* is deterministic (frozen descent, frozen code, confirmed in section 1), so c_k is zero up to the iterative
    solve's error.
  - c_k ~ U(−τ_k, τ_k), with τ_k = that solve's `solver_tol_rel_L_max` (2R 1.85e-5, Case 4 2.65e-5). It is drawn
    once per layout per replicate and applied to the search and both nulls.
  - The old draft drew c_k with σ = median b/3.92, which treated a fixed discretisation offset as a fresh draw that no
    registered run experiences. Review T0462's objection is right, and that construction is dropped.
- **Resampling.** Per layout, independently, B = 20000 replicates (seed 20261119) each resample 8 development draws
  with replacement. Each draw is resampled as its whole tuple (search, widen, compact), paired on D_j.
- **Checks.**
  - The vectorised metrics equal e011_metrics on the 200 replicates checked, with 0 mismatches.
  - Selftest: a planted 4-of-8 case reproduces P(A1 per layout) = 9/256 within 4 standard errors.
- **Uncertainty.** One-sided Clopper-Pearson lower bounds on each per-draw event rate, and the binomial tails they
  imply, singly and as a Bonferroni union bound on π.

**Fact (values).**
- P(PASS) = 0 (0 of 20000).
- P(A1) = 0.0003. Per layout: 2R 0.0003, with analytic A1-only 0.0004 at p = 0.25; Case 4 1.0.
- P(A3) = 0.226. P(compact beaten) is 0.36 on 2R (P(paired ≥ 7) = 0.36) and 0.63 on Case 4 (P(resolved ≥ 4) = 0.63).
  Widen is beaten with P 1.0 on both layouts.
- P(K1 not fired) = 1.0, P(INCONCLUSIVE) = 1.0, P(FAIL) = 0.
- Lower bounds: Case 4's 8 of 8 gives p_L = 0.69, so P(A1 on Case 4) ≥ 0.23 at 95 %. The Bonferroni bound on π is 0.

**Inference.**
- The plug-in figure is degenerate at 8/8 and 0/8, so "1.0" for Case 4 means "no dev draw failed", not "certain".
- The 2R side is not near the line. Even the one-sided 95 % upper bound on 2R's per-draw pass rate (2 of 8 → 0.59)
  gives P(A1 on 2R) of about 0.09.
- **With the frozen design, the registered run is expected to be INCONCLUSIVE.** This is a planning figure from 8 dev
  draws per layout, not evidence.
- **What would prove this wrong:** registered 2R draws passing 7 of 8 under the same frozen design. Given 2 of 8 here,
  that has probability below 0.1 % under the bootstrap.

## 6. Review items 4, 5, 8, 9 (task c)

**Fact (runner, `experiments/runners/e011_run.py`).**
- **(4)** In record mode, the R_D callback's window midpoint is used only for control flow. Draw records, attempt logs
  and rows now store `r_d`/`R_D` None with `r_d_provisional` true. `--dev-rows` fills the measured R_D at 0.25 and
  0.5 mm. The committed manifest predates the fix and still shows 1.425; the spec says so (`config.dev.r_d_placeholder`).
- **(5)** `changed_from_D` uses `ops.movable()`, as `changed_from_Wstar` does. `Solves` takes `freq_hz` from
  `config.levels.freq_hz` and `em_job` refuses to run without it. `full()`'s `er.domain` uses the spec value.
- **(9)** `tj_fallback_due` is evaluated in every mode.
  - Why it could not fire before: the old guard `and not provisional` skipped it whenever W* was provisional, which is
    always the case in dev mode, because `choose_proxy` needs L2 values.
  - It is now reachable: if it is due on the provisional W*, dev mode records the dies-fixed descent's band jobs for
    the burst (`tj_fallback_pending_l2`). The selftest plants 3 K and asserts this.
  - On the dev layouts it is not due: Tj(W*) − Tj(W) = −1.62 K (2R) and −2.02 K (Case 4).
- **(8) Not done; flagged.**
  - `research/o008_e011_dev/work` (stage checkpoints, `.wall` files) and `work_dev.log` do not exist on this machine.
    I checked this worktree, `main` and every other worktree under `~/mf/wt`, and searched the home directory.
  - They were never committed, so their sha256 cannot be recorded.
  - Recorded instead: the manifest (sha256 17bd0a76…; its `layouts.*.search_improvement.per_draw` holds every bracket
    end), `dev_summary.md` (44d24cc6…), and the dev_l2 results tree hash in `dev_rows.json`.
  - The brackets can be read but not re-derived.
- **Selftest additions:**
  - `dev_rows` on a fake manifest and burst (96 rows, planted s exact, R_D measured, recompute clean, P(PASS) 1);
  - the Tj fallback in dev mode;
  - the placeholder not recorded as a number;
  - the joint-OC analytic case;
  - `oc_lower_bounds`.

## 7. Registered-run size (task d, review item 2)

**Fact (measured on the burst; `measured_sizing.per_layout_level`).**

| | 2R 0.25 mm | Case 4 0.25 mm |
|---|---|---|
| wall, median | 925 s | 3046 s |
| wall vs E010 model | 0.66 | 0.53 |
| peak RSS, max | 6.4 GB | 16.5 GB |
| peak vs model | 1.00 | 1.05 |

- CPU/wall is 1.25-1.46 at 2 threads.
- The burst VM's shape is not recorded in the repository. The 2026-11-09 calibration (project/memory/lessons.md)
  measured 5700-5900 s for Case 4 at 0.25 mm with four at once on the 8-vCPU N2D. A full-load sensitivity therefore
  uses 5900 s.

**Model.**
- Solve counts from `registered_model`, per layout: P 10; D 8 plus redraws; S1 152 at 0.25 mm; S2 192.
- Phases and layouts run in sequence, as `run_all` runs them.
- Scheduling with E010.simulate at p90 walls and 1.1 × max peak. gen2_0 uses E010's model × 2R's measured ratios.
- Pricing: 0.612 $/h for 8 vCPU / 80 GB is the founder's figure. Extended memory at 0.0086 $/GB-h is E010's unchecked
  assumption. 16 vCPU is assumed to cost 2 × 0.612 $/h: check in the console.

| option | makespan h (measured; full load) | USD (measured; full load) | timeout_min |
|---|---|---|---|
| A: n2d-custom-8, 80 GB (current), 3 Case 4 at once | 105-122; 144-170 | 65-75; 89-104 | ~10800 |
| B: n2d-custom-8, 96 GB ext, 4 at once | 92-105; 121-140 | 69-79; 91-105 | ~9000 |
| C: n2d-custom-16, 160 GB, all 16 vCPUs | 53-63; 71-87 | 66-78; 87-107 | ~6000 |

- Ranges run from no redraws to every draw redrawn in all 4 waves. The measured out-of-window rate (1/16) sits in
  between: A 112 h / $69.
- Process CPU-hours: 495 (662 at full load). The old figures were cpu_hours_est 110 and timeout_min 7200.
- **Spec changes:**
  - `timeout_min` is now 10800, which covers option A in every scenario.
  - `cpu_hours_est` is now 495.
  - `registered_run_usd` and the options are in `cost_estimate`.
  - The choice is left open.
- A split into runs needs a layout-subset flag and a work-directory merge that the runner does not have, so it is not
  offered.

**Inference.** C is the fastest and costs about the same as A, because the bill scales with vCPU-hours. But it takes
the whole 16-vCPU free-trial cap, so it can only run when no other burst holds 8 vCPUs. B is the cheapest way to fit
under 150 h with only 8 vCPUs.

## 8. Founder decisions this prepares (task e)

1. **Register E011 as is, or redesign first (blocking).**
   - Evidence: dev rows A1 0.25 and A3 0 (sections 3 and 5); P(PASS) ≈ 0; O008 F1 requires A3 met on dev rows at
     registration.
   - **Recommendation: do not register as is.** A registered run would cost $65-107 and use one of O008's two
     evaluations on an expected INCONCLUSIVE.
   - Choose between:
     - (a) a pre-registration redesign aimed at 2R's L1/L2 disagreement: for example, L2 re-ranking of a larger
       shortlist, or a proxy rule whose W* is an L2 optimum and not only an L1 one. Each needs new dev rows and a new
       burst. The founder decides which frozen values change.
     - (b) take the dev evidence to the 11-27 thesis review as a finding against the hypothesis on 2R, without a
       registered run.
   - The objective lets the founder stop earlier. Whether (b) counts toward the plan's stop line is the founder's call.
2. **The L1 degradation target.** Keep 1.3875 (R_D ≈ 1.28 at L2, 1/16 out of window), or raise it so R_D centres in
   [1.25, 1.60], for example about 1.59 at the measured 0.72 slope (R_D about 1.425). The risk is small, so either is defensible.
   Recommendation: raise it if a redesign happens anyway; otherwise keep it.
3. **L1 search budget** (e011-dev-run.md section 4). Recommendation: keep 2000. 2R's misses are not budget-limited
   (under 1 % of L1 gain in the last 10 %). Case 4 still gains up to 6 % late but already passes 8 of 8.
4. **The no_moves rule** (review T0444, proposed). Recommendation: adopt it as written. It is conservative (a null that
   never moved is not a resolved failure), and it bound on none of the 32 null runs or 16 searches.
5. **Review item 8.** Recommendation: accept the manifest's recorded brackets for the budget decision, because they
   only feed decision 3, which does not depend on them at L2. If an audit trail is wanted, rerun `--dev`
   deterministically on the stamped code (about 2 h local, including local level-0 thermal solves) and commit the
   checkpoint hashes.
6. **Registered-run option and O008's VM budget.** If E011 is registered after a redesign: option C when no other burst
   runs, otherwise B. Set a VM cap of about $110 for the run. O008's VM spend would then be about $40 (dev burst) +
   $65-107, against the notes' $50-100 expectation.
   Recommendation: approve no registered-run VM money until decision 1 is made.

## 9. What would show this note wrong

- If `L2Table`, the selection re-derivation or the band computation did not match `run_layout`. The selftest checks
  them on fakes; all 34 real groups matched the burst's own selection.
- If the 0.25 mm results were not deterministic across VMs at more than the GMRES tolerance. Only a re-solve of W*
  would show that.
- If registered 2R draws behaved unlike the 8 dev draws, for example because the dev seed was atypical. Eight draws
  cannot exclude that (section 5's bounds).
