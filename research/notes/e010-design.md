# E010 design (T0339): E008 with the repaired sampler and the SearchInfeasible exclusion (D0021; id E010 by D0022)

[F] = fact checked here, [I] = inference.

**What E010 is [F].** E010 is the registered experiments/specs/E008.yaml with three changes, D0021 items 2-4:
- (a) the T0338 sampler;
- (b) SearchInfeasible;
- (c) new freeze hashes.

research/o003/e010_dev/make_spec.py derives the draft from the registered spec itself, not from e008_dev/make_spec.py.
E008's registered content came from that script plus the T0320-T0336 update scripts, so the script alone would not
reproduce it. make_spec.py then walks both specs key by key and writes every difference, with its reason, to
research/o003/e010_dev/spec_diff.md. It stops on any difference that has no reason.

The differences are:
- the id and paths;
- derivative.py's freeze hash, the only frozen file that changed (the script asserts this);
- failure_consequences.SearchInfeasible;
- one clause in the at_least_one_counted_reference description;
- the deviation statement, which now names D0021 and no longer says "src/ unchanged since T0300";
- f3_declared_deviation.d0021, which also states review T0341's finding;
- changed_after;
- the 2R screen rate and its basis;
- the --plan cost lines.

Everything else is unchanged: criteria, metrics, recompute entries, nulls, stop rules, F3 order, budgets, bands, D0019's
references, D0020's Tj rule, twin.py, the search driver, the cost-model rates and the sealed-seed policy.

**(b) in the runner [F] (experiments/runners/e010_run.py).**
- A screen job whose child recorded derivative.generate's RuntimeError ("no DRC-valid candidate in ... consecutive draws")
  raises `SearchInfeasible` in `Scheduler.done`.
- The scheduler does not treat it as fatal.
- `Run.drive`, the code path shared by the registered and dev runs, catches it per driver and calls
  `Run.search_infeasible`. That excludes the reference (reason SearchInfeasible, stage screen), drops both of its drivers
  and its queued jobs, and re-runs spot_assignment.
- The pending count is taken after the pass, so a reference excluded later in the same pass does not leave a phantom
  pending driver. The selftest's resume case found that bug.
- evaluate() reports the exclusion under `excluded`. at_least_one_counted_reference makes the run INVALID only if no
  reference remains.
- Any other failed screen or solve still stops the run.

Selftest `search_infeasible_failures` runs the real screen child on a synthetic housing whose 30 mm power-width rule cannot
draw. It covers three cases: main and control infeasible, control only, and fake1 as the only reference. It also checks a
resume and a planted "ValueError" screen, which must still stop the run.

The test compares a run with fake1 against a run without it. It requires these to be byte-identical:
- every row;
- every metric except n_excluded_references (1 vs 0);
- every whole per-reference check of fake0 and fake2;
- every aggregate check's name, passed, value and threshold. The exception is fail_fast_twin_and_D, whose value is the
  exclusion count and must be 1 vs 0.

Aggregate check details may name the exclusion. 0 failures.

**--check-references (D0021 item 4) [F].** For each reference the check rebuilds it, verifies the fingerprint and builds
the spec. It then fits the twin's geometry (with_l1=False) and measures the sampler's draw rate with
`draw_feasibility`: 300 000 draws for the main screen and 300 000 for the control screen. Both screens use the reference's
own spec. research/o003/e010_dev/feasibility_2r.py calls the same function with the same constants and asserts that its
counts equal check_references.json.

Results:
- **2D_Case_2R:** 2026 DRC-clean in 600 000 draws, p = 3.38e-3, about 14 ms per candidate on this Mac, P(abort) <= 1.1e-22.
- **2D_Case_6:** TwinError, as expected, so no screen runs.

Mesh counts are not recomputed: D0021 item 4 allows no l2_layout, thermal or FV code on 2R or 6. plan_references keeps
E008's T0320 counts, and the check confirms the fingerprint behind them. `--mesh-counts` recomputes them, after
registration only.

--plan's 2R screen rate = 0.45 s + 13.84 ms x 5.55 = 0.527 s per candidate. 5.55 is the largest measured Mac -> VM factor.
Applying it to pure-Python sampling is an inference [I].

**Cost [F, research/o003/e010_dev/plan.json].**

| Plan | E010 billed vCPU-hours | E010 VM-hours | E010 cost | E008 billed vCPU-hours |
|---|---|---|---|---|
| Expected | 102.1 | 12.76 | $22.70 | 98.7 |
| Upper | 150.5 | 18.81 | $26.40 | 147.1 |
| If 2D_Case_6 were counted (expected / upper) | 152.0 / 257.4 | | | |

The +3.4 vCPU-hours is the longer 2R screen, which is on the critical path. **The 320 vCPU-hour cap holds in every case.**
D0021 item 6 quoted $22.44 / $26.14, which E008's plan gave; E010's plan is $0.26 higher.

**Dev rows [F].** experiments/drafts/E010.dev_rows.json was rebuilt with
`e010_run.py --dev --geoms gen2_0::0,case4:gates:4 --band-pairs 4 --replay-only`.
- It ran on a worktree copy of the dev run's full_work: 333 files, sha256 list equal to the source (log
  research/o003/e010_dev/replay_T0339.log).
- solves_started 0, and the rows equal E008's 59 dev rows.
- The e010_dev copies of gen2_0_prep.py, case4_prep.py and refresh_rule_strictness.py then re-stamped runner_sha256, as
  T0324 did. The meta differs from E008's only in those provenance records.

**Support on 2R (review T0341) [F].** See research/notes/e010-generator.md. Every DRC-clean 2R candidate has the twin's
configuration, so a 2R result is a within-topology search. On gen2_0, 56 of 200 candidates share the twin's topology.

**What would prove this wrong.** Any of these on the registered run:
- a 2R screen raising SearchInfeasible, which is predicted at P <= 1e-22;
- a dev stream mismatch;
- rows of a counted reference that depend on whether another reference was excluded.

**Not done.** No L1, l2_layout, EM, thermal, FV, degrade() or search ran on 2R or 6. Nothing under the E008 run's solves/
was read, and no gcloud call was made. src/, tools/, the specs, e008_run.py, the E009 files and the frozen script were not
changed.
