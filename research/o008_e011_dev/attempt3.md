# T0382 attempt 3: blocked on taking main into the branch (2026-11-17)

Author: scientist agent, T0382 attempt 3. Facts, inferences and requests are labelled.

## Why the development run was not started

**Facts**
- The packet's first instruction for attempt 3 reads "merge current main into this branch first". Steps 1-5 (the dev
  L1 run "on the code that will be frozen", `--freeze-report`, the complete manifest and the notes) all depend on it.
- This branch (`task/T0382-design-e011-draft-spec-and-runner-selfte`, HEAD 5cd9749d) does not contain T0437:
  `git log --oneline HEAD | grep -c T0437` gives 0, and `git branch --contains f080880c` lists `main` and T0388's
  branch, not this one. `git log --oneline main ^HEAD` lists 65 commits.
- The `src/` files main changed since this branch took it in: `optimize/control.py`, `optimize/nulls.py` (T0437),
  `solvers/fasthenry.py`, `solvers/fasthenry_run.py` (T0442), `solvers/thermal_layout.py` and `thermal/__init__.py`.
  D0026 (project/decisions) is also on main only.
- Agents may not merge. mf-git says: "Never: push, merge, rebase … If you need something from main that is not in
  your branch, report `blocked` and say what." The guard hook refused even a read-only `git merge-base` in this
  attempt ("history rewriting/merging is the orchestrator's job"). In `tools/mfos/mfos/loop.py`, `_merge_conflict`
  says "agents may not merge (policy: git merge is denied to them)". The orchestrator's `gitops.update_from_main`
  runs only at merge time (loop.py, `_merge`), not when an attempt starts.

**Inference: why I did not work around it.** I could have run the runner against an exported copy of main's tree.
That would break the rule quoted above. It would also leave this worktree's files disagreeing with the hashes:
`--freeze-report` and the code stamp would describe main's `src/`, while this branch's `src/` is still the
pre-T0437 code. Without T0437, a development run on this branch would use untagged degradation streams. D0026 item 3
and the packet ("no development row or pin from before T0437 carries over") rule those rows out in advance.

**Request (founder or orchestrator).** In `/Users/lukeskywalker/mf/wt/T0382`, run `git merge --no-edit main`, which is
what `gitops.update_from_main` does. Main changed none of the files this task writes (`git log main ^HEAD --
experiments/runners experiments/drafts/E011.yaml experiments/drafts/E011.dev_jobs.json research/o008_e011_dev` is
empty), so no conflict is expected. Then retry T0382. The next attempt starts at the packet's attempt-3 step 1, the
`--dev` run.

## Done in scope this attempt (all independent of T0437's code)

1. **Review T0444: `no_moves`.**
   - `e011_metrics.py`: `TERMINAL_KINDS` gains `no_moves`. A new `CAPPED_KINDS = (step_limit, budget, no_moves)`, and
     the validator refuses any of them with `capped` false. The column docs and the A3 docstring say so.
   - `e011_run.terminal`: a null's `no_moves` (nulls.NO_MOVES) and the search's `stop_reason == 'no_moves'` both map to
     `(no_moves, capped=True)`. Before this they mapped to `(local_optimum, False)`, which made a null that never moved
     count as a resolved failure.
   - The selftest's unit checks gained the following:
     - the terminal mapping for both, plus a null `local_optimum`;
     - a planted table with 5 no_moves and 3 local_optimum widen draws, all at s = 0.2 and b = 0.001, against a
       search at s = 0. The expected result is resolved 3, paired 8, not beaten.
     - the validator refusing `no_moves` with `capped` false.
   - The spec gets `frozen.nulls.no_moves_rule`, worded as proposed for the founder to confirm, and the A3 metric
     description names step_limit and no_moves as capped.
2. **Null rows** (packet step 4(b)). Rows for widen and compact now carry `seed_in_domain` and `n_neighbours_step0`
   from `NullResult.stats`, and so does `null_steps`. On this branch's pre-T0437 nulls.py both read `None`. On main they
   are filled. The runner raises if any null run's `seed_in_domain` is False (T0425: never scored).
3. **Spec text.**
   - It cites D0026 item 1 for the parameter set and item 2 for the proxy rule.
   - `seeds.rule` names the T0437 entropy list `[control.DEGRADE_TAG = 0x4D460D01, seed, layout_index, j, a]`
     (`control.degrade_entropy`).
   - `prerequisites_pending` now states that the fixes are on main (f080880c) and not yet in this branch.
4. **Compatibility check by reading main's code (not run).**
   - T0437's API changes are additive: `proxy_descent(step_mm=0.5)`, `null_widen` / `null_compact(dies_fixed=False)`,
     and the new `stats` keys.
   - Main's `draw_degradations` records `"entropy": ent` in each attempt log (main control.py line 213).
   - The runner's `seed_streams_distinct` reads it, so `control_entropy_domain_tagged` should read True after the merge.
     This is an inference until the dev run shows it.

## Not done (needs main in the branch)
- The `--dev` run for 2D_Case_2R and 2D_Case_4.
- `--freeze-report`, `code_sha256` and `frozen_sha256`.
- `E011.dev_jobs.json` with status complete. The file is still attempt 1's stale schema-1 manifest, and `dev_solve`
  refuses it.
- research/notes/e011-dev-run.md. Not written, because it is meant to hold the dev run's facts.
- The improvement curves, the null step and terminal tables at R_D in [1.25, 1.60], the proxy terminal values, the
  ablation l1_evals, and the VM sizing from measured unknowns.
