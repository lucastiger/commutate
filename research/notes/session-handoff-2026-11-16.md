# Founder-session handoff, 2026-11-16

Supersedes `research/notes/session-handoff-2026-11-15.md`, whose next steps are done or moved here. The repository is
the source of truth for everything cited. Times are UTC unless marked.

## Where things stand
- **O003**: paused (needs_founder). D0023 (accepted 2026-11-15): E010 is void, O003 has no verdict, no successor under
  O003; by D0011 it counts as INCONCLUSIVE at the 11-27 day-60 review. T0349's design rule is in
  `project/memory/lessons.md`.
- **O008, O004, O002: approved by the founder at 01:35 on 11-16**, ahead of the 11-27 thesis review. Each has a planner
  running (T0375 O008, T0374 O004, T0373 O002, $4 each) and `require_plan_approval: true`, so each plan arrives as an
  inbox item for the founder before any build work runs.
  - **O008** (reach plus a seeded search; planted-headroom control on a designer proxy W*, die rows free everywhere;
    criteria A1 7 of 8 per layout, A2 reach, A3 blind nulls beaten per layout, K1 median shortfall per layout; E011;
    core only, no feature extensions). Five draft-review rounds (T0351-T0360), the last two accept with caveats. Basis:
    `research/notes/o008-control-probe.md` (L1 probe on 2R and Case 4, including a die-fixed re-run).
  - **O004** (l2_layout at 0.25 mm against FastHenry on PowerSynth 2D_Case_2R and 2D_Case_6; Case 4 development only per
    O006 F4; ratio test primary; E004). Four rounds (T0361-T0368), the last accept with caveats. Burst pilots (F7) are
    the founder's to launch before registration.
  - **O002** (fast L1 thermal model against the scikit-fem reference of C004; die-average Tj gated, hottest node
    reported, so decision 5 of the thesis review is now effectively made; E007; reference judged at level 1). Two rounds
    (T0369-T0372), the last accept with caveats. Basis: `research/notes/o002-reference-convergence.md`.
  - The founder accepted every proposed number in the three drafts.
- **Coverage census**: `research/notes/coverage-census.md` (14 commercial modules, free sources): 0 confirmed
  representable, at most 5; separate diode dies block 6, multi-pad terminals 4; the two planned extensions block no
  known commercial module. A plan risk-table early sign.
- **mfos**: merged on main: the four plan-section-11 fixes (16d263fc) and the state-commit fix (17df701b: a tick no
  longer commits anything it did not stage). The audit job flags bot commit 6b4986f3 (content equal to the approved
  7c861f72) until it leaves the 2-day window, about 11-17 21:32 UTC; no action. The loop runs as pid 26177 from a zsh
  terminal (tty ttys002), not tmux.

## Next steps, in order
1. **Review each plan_approval item** when it arrives: check every task against skill mf-planning's pre-flight checks
   (role write scope; free experiment id; no definition of done that depends on a later step; no task writing tools/).
   Give the founder the exact `uv run mfos approve <id>` or `uv run mfos reject <id> --note "..."` command.
2. **Founder-session tooling before any registration** (tools/ is protected; ask the founder first): the mfos.metrics
   functions the three objectives name: O008 F7 (per-layout pass fraction, null-beaten indicator, per-layout median
   shortfall); O004 (the ratio-step rule: steps below 0.1 % converged, 3 max|d|); O002 (quantile-of-relative and
   absolute error, median, ratio-to-null, per-level max, self-pair exclusion, the coverage-checked bound F3 selects,
   and its 0.01 K step floor), each with analytic tests.
3. **Thesis review 11-27**: briefing in `research/notes/thesis-review-2026-11-27-briefing.md`. Update it first: O008,
   O004 and O002 are approved, so decisions 5 (yardstick) and 9 (budgets) are largely taken, and 4 and 6 now concern
   the work already started. The founder runs `/thesis-review` on the day; the session then drafts decision records for
   decisions 1, 2, 4, 5 and 6.
4. **Customer track** (founder): send the emails in `research/notes/outreach-drafts.md` (PREES; design-partner
   prospects); calls follow the call guide there; record each call in `project/customers/`; send the session the
   fact-only answers. Capability brief: `research/notes/capability-brief-draft.md` (C002 and C004 only).
5. **Optional**: an l2_layout check of W against W* on 2R and Case 4 (does the L1 probe's 10 % and 37 % hold at L2?),
   in a session, no VM, only if the founder asks.

## Standing instructions from the founder
- Everything in the 11-15 note's standing instructions still applies (gated commands are the founder's; protected
  paths; VMs and data; leakage rule; watchers every 10-15 s reporting each change, re-armed on expiry).
- Emails with common sense: short, asking for a call; at most three questions (skill founder-session).
- For anything the founder must do: exact commands, and say explicitly whether to run them now or later (skill
  founder-session).
- Commit commands for the founder: chain with `&&` and name the paths after `--` on `git commit`
  (`git add P && git commit -m "..." -- P`), so a commit never picks up what the loop has just staged and nothing runs
  after a failure (index-lock race on 11-16, stray commit 49db98ef holding only project/STATUS.md).
- Commits by the session only when asked; `git merge` is denied to the session, so merges are the founder's.

## Lessons from this session
- A state tick used to commit the whole index; fixed, but a founder commit can still pick up the loop's staged state
  unless it names its paths.
- Draft reviews inform approval and do not gate it (mfos objective approve). Each round costs about $3.50; stop when
  both reviews accept with caveats and fold their findings in without another round.
- A planted-headroom control must target a near-optimal layout (a designer proxy), not the twin: blind compaction
  recovers twins (o008-control-probe).
- Ratio and difference sequences need a step-size floor: gci_capped returns +inf for converged sequences with tiny
  steps (O004, O002 reviews).
