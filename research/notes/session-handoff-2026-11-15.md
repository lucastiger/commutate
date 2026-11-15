# Founder-session handoff, 2026-11-15

The previous founder session ran 2026-11-12 to 2026-11-15. This note is what the next session needs; the repository is
the source of truth for everything it cites.

## Where things stand
- **O003**: active, no verdict. E008 could not search 2D_Case_2R as registered (D0021). Its successor E010 (D0022; E009
  is O007's experiment) was registered and run on the founder's VM (run E010-20261114T202413-80c1, complete, 6.2 VM-h).
  The evidence is INVALID: the planted-headroom control F1(b) failed on 2R (h_ctrl 0.161 against h_plant 0.220 - w_ctrl
  0.013), and the artifact evaluation_report.json was not in the local artifact store (the launcher copies only the run
  directory). The evaluation was not counted: `evaluations` is empty, so O003's single evaluation is unused. Replans
  3/3 used; spent $258.22 of the $264.99 cap.
- **Diagnosis T0349** (experimental, 0.85): the frozen search cannot reach the 2R designer's layout. The twin lies outside
  the sampler's reach (slots attach to the column's inner edge), and the best random draws sit 3-6 % above it. Review
  T0350: accept with caveats. Merge item **I0203** is open.
- **mfos**: five loop fixes merged on main (721e9ed6) and live since the loop restart on 2026-11-14 17:32 (pid 12013).
  1. `register()` refuses an id that is already registered.
  2. `--no-replan` on a diagnosis merge is honoured.
  3. A scientist can report `blocked`, and the report goes to the founder.
  4. A hold set during verify is kept.
  5. Cancelled or held agents are stopped.

  `.git/info/exclude` lists demo/, research/o003/e008_dev/full_work/ and research/o003/e008_dev/tj_osc/vm_work/, so the
  loop can restart.
- **The plan**: "Commutate Plan and Timeline", a Claude Docs doc owned by the founder
  (https://claude.ai/artifact/FEGt6mrR4zoLEXmvNg9cYk). v1 = a paid derivative re-layout sprint, shipping about
  2027-02-26. The validation objective O009 reaches a verdict about 2027-01-29, and broad coverage (at least 80 % of a
  census of SiC half-bridge modules) comes by 2027-03-26.
- **Day-60 review** 2026-11-27. **Day-90 line** 2026-12-27; the plan aims for a signed LOI by 12-18.

## Next steps, in order
1. **Founder approves I0203.** Use `--no-replan`; O003's replans are used up anyway.
2. **Session drafts D0023.** E010 is void with no verdict: the frozen D0008 search does not reach the 2R designer's level,
   so E010's h = 0 is not evidence of no headroom. It also records T0349's design rule: rehearse every planted-headroom
   control on a development reference whose twin the sampler cannot draw. The founder accepts it, then the session
   pauses O003 (`uv run mfos objective pause O003`) and adds the design rule to project/memory/lessons.md.
3. **Get the founder's explicit go-ahead for the coverage census** (plan section 2). Decide which objective owns it,
   because O003 has no budget. Recommended: draft O008 first, with the census as its first task.
4. **Prepare the thesis review (11-27):**
   - A-T3 becomes "untested, instrument insufficient";
   - amend O003's rule on the order of work (coverage and the search before current-mismatch work);
   - choose the thermal yardstick (recommended: die-average Tj gated, hottest node reported);
   - the v1 definition and its ship gate;
   - the coverage target;
   - budgets.
5. **Draft O008** (search seeded at the twin, reach, quarter-turned dies, side-by-side blocks, planted controls on
   development geometry, where 2R and 2D_Case_6 are now development layouts) and refresh the O002 and O004 drafts.
   Plan sections 3-5.
6. **Make the four tooling fixes in a founder session** (plan section 11; agents cannot write tools/):
   - runners register run-directory artifact paths, and the launcher fetches the artifact store;
   - one diagnosis per failure (E010 spawned T0348 and T0349);
   - the guard hook reads `from mfos import models` as the `mfos import` command;
   - one parameterised burst launcher.

## Rules learned in this session (check before creating any task)
- Builder scope is src/, tests/unit/, tests/regression/, docs/ only; research/ files belong to scientist tasks.
- Experiment ids are global: list experiments/specs/ and drafts/ before naming one.
- No definition-of-done check may depend on a later step (E010's dry run needed O003 v6 first).
- `mfos objective approve` sets needs_replan; clear it in the same command when no replan is wanted (done for O003 v6).
- The loop refuses to start with untracked files in the checkout (`unexpected_changes`); restart it only when no task is
  in verify.

## Housekeeping
- The E008 VM mf-e008-1794679144 (us-central1-a) was stopped, not deleted, on 2026-11-14. Delete it if that has not been
  done.
- ~/.cache/mf-burst/e008_full/state.env holds the failed E008 run (RC_A=1); E010's state is archived as state.env.done-*.
