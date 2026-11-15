# Founder-session handoff, 2026-11-15

The previous founder session ran 2026-11-12 to 2026-11-15. This note is what the next session needs; the repository is
the source of truth for everything it cites. Times are Pacific unless marked UTC.

## Where things stand
- **O003** (objective v6, re-approved 2026-11-14; its criteria now name E010): active, no verdict.
  - E008 could not search 2D_Case_2R as registered (D0021). Its successor E010 (D0022; E009 is O007's experiment) was
    registered and run on the founder's VM: run E010-20261114T202413-80c1, complete, 6.2 VM-h.
  - The evidence is INVALID. The planted-headroom control F1(b) failed on 2R: h_ctrl 0.161 against h_plant 0.220 minus
    w_ctrl 0.013. The artifact evaluation_report.json was also missing from the local artifact store; the runner
    registered a bare name and the store copy stayed on the VM.
  - The evaluation was not counted (`project/objectives/O003/evaluations/EV-O003-01-invalid.json`; `evaluations` is
    empty), so O003's single evaluation is unused.
  - Replans 3/3 used; $258.22 spent of the $264.99 cap.
- **Diagnosis T0349** (experimental, confidence 0.85): the frozen search cannot reach the 2R designer's layout. The twin
  lies outside the sampler's reach (slots attach to the column's inner edge), and the best random draws sit 3-6 % above
  it. Review T0350: accept with caveats (`project/reviews/T0349/T0350.json`). The founder approved its merge (I0203) at
  12:03 on 2026-11-15; it merged at 12:09 (99330585). The note is `research/diagnoses/T0349.md`.
- **Records:**
  - D0021 and D0022 in `project/decisions/`;
  - the registered spec `experiments/specs/E010.yaml` and the reviews `project/reviews/T0338/T0341.json` and
    `project/reviews/T0339/T0346.json`;
  - the E010 run in `experiments/results/E010/`; nobody needs to read its solve files.
- **mfos**: five loop fixes are merged on main (721e9ed6), live since the loop restart on 2026-11-14 17:32 (pid 12013).
  1. `register()` refuses an id that is already registered.
  2. `--no-replan` on a diagnosis merge is honoured; confirmed in production, since T0349's merge left needs_replan
     false.
  3. A scientist can report `blocked`, and the report goes to the founder.
  4. A hold set during verify is kept.
  5. The agent of a cancelled or held task is stopped; confirmed in production on T0348.

  `.git/info/exclude` lists demo/, research/o003/e008_dev/full_work/ and research/o003/e008_dev/tj_osc/vm_work/, so the
  loop can restart. demo/ is the founder's local demo (http://127.0.0.1:8751/) and is not in the repository.
- **The plan**: "Commutate Plan and Timeline". The living copy is a Claude Docs doc the founder owns
  (https://claude.ai/artifact/FEGt6mrR4zoLEXmvNg9cYk). A snapshot is in `project/plan/commutate-plan-and-timeline.md`,
  with the timeline image beside it (committed by the loop's state commit fb2a1639).
  - v1 is a paid derivative re-layout sprint, shipping about 2027-02-26.
  - The validation objective O009 reaches a verdict about 2027-01-29.
  - Broad coverage (at least 80 % of a census of SiC half-bridge modules) is due about 2027-03-26.
  - Its decisions table lists 14 dated founder decisions.
- **Dates**: day-60 review 2026-11-27; day-90 line 2026-12-27; the plan aims for a signed LOI by 12-18.

## Next steps, in order
1. **Check that no O003 planner task has appeared.** There was none at handoff, and needs_replan was false after
   T0349's merge. If one appears, cancel it; the loop now stops its agent.
2. **Session drafts D0023.** E010 is void with no verdict: the frozen D0008 search does not reach the 2R designer's
   level, so E010's h = 0 is not evidence of no headroom. It also records T0349's design rule: rehearse every
   planted-headroom control on a development reference whose twin the sampler cannot draw. The founder accepts it.
   Then the session pauses O003 (`uv run mfos objective pause O003`, which only sets needs_founder) and adds the design
   rule to project/memory/lessons.md.
3. **Get the founder's explicit go-ahead for the coverage census** (plan section 2), unless they gave it when starting
   the session. Decide which objective owns it, because O003 has no budget. Recommended: draft O008 first, with the
   census as its first task.
4. **Prepare the thesis review (11-27):**
   - A-T3 becomes "untested, instrument insufficient";
   - amend O003's rule on the order of work (coverage and the search before current-mismatch work);
   - choose the thermal yardstick (recommended: die-average Tj gated, hottest node reported);
   - the v1 definition and its ship gate;
   - the coverage target;
   - budgets.
5. **Draft O008** (search seeded at the twin, reach, quarter-turned dies, side-by-side blocks, planted controls on
   development geometry, where 2R and 2D_Case_6 become development layouts) and refresh the O002 and O004 drafts.
   Plan sections 3-5.
6. **Make the four tooling fixes in a founder session** (plan section 11; agents cannot write tools/):
   - runners register run-directory artifact paths, and the launcher fetches the artifact store;
   - one diagnosis per failure (E010 spawned T0348 and T0349);
   - the guard hook reads `from mfos import models` as the `mfos import` command;
   - one parameterised burst launcher.

## Standing instructions from the founder
- **Gated commands are the founder's.** Never run `mfos objective approve`, `mfos exp register` or
  `mfos claim approve|annotate`, and never approve or reject gated inbox kinds. Give the exact command instead, with its
  expected output. Resolve non-gated items only when the founder decided in the session, with `--no-replan`.
- **Protected paths change only with founder permission:** `.mfos/**`, `tools/mfos/**`, `.github/**`, `.claude/**`,
  `project/decisions/**`, `project/objectives/*/objective.yaml`, `experiments/specs/**`, `tests/acceptance/**`.
  Decision records and registered specs are never edited; add an erratum or a new record.
- **VMs and data:**
  - Agents never run gcloud or start VMs; the founder launches them, so keep VM cost low.
  - Never read data/holdout/.
  - Customer files never go to Claude or any AI service unless the NDA allows third-party processing.
- **Leakage rule:** nobody opens NC State PREES, 2D_Case_5 or customer geometry until O008's code is frozen with hashes
  recorded. Fact-only screening answers are allowed and are declared when used.
- **Watchers**: the founder wants every state change reported promptly. Use Monitor polls every 10-15 s that post a line
  on each change, re-armed on every expiry, including while waiting for an answer, and read the state that changed.
- **Commits** only when asked, ending with the Co-Authored-By line. No pushes and no gh. The shell is zsh, where
  unmatched globs error. Do not recommend NODE_EXTRA_CA_CERTS.

## Rules learned in this session (check before creating any task)
- Builder scope is src/, tests/unit/, tests/regression/, docs/ only; research/ files belong to scientist tasks. No agent
  role may write tools/.
- Experiment ids are global: list experiments/specs/ and drafts/ before naming one (register now refuses a taken id).
- No definition-of-done check may depend on a later step (E010's dry run needed O003 v6 first).
- `mfos objective approve` sets needs_replan; clear it in the same command when no replan is wanted (done for O003 v6).
- A hold or cancel is now kept by the loop, but set holds before a task reaches verify when you can.
- The loop refuses to start with untracked files in the checkout (`unexpected_changes`); restart it only when no task is
  in verify.

## Housekeeping
- The E008 VM mf-e008-1794679144 (us-central1-a) was stopped, not deleted, on 2026-11-14. The founder was asked to
  delete it; confirm.
- ~/.cache/mf-burst/e008_full/state.env holds the failed E008 run (RC_A=1); E010's state is archived as state.env.done-*.
- Cancelled diagnosis worktrees (wt/T0340, wt/T0345, wt/T0348) remain; the loop manages task worktrees.
