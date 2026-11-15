---
name: mf-planning
description: How to decompose an mfos objective into tasks - task types, sizing, definition-of-done patterns, risk levels, budgets, anti-patterns. Use when producing a plan.
user-invocable: false
---

# Planning reference

## Task types and owners
| type | agent | produces | typical DoD |
|---|---|---|---|
| implement | builder | code + unit tests | `uv run pytest tests/unit/test_x.py -q` |
| docs | builder | docs | `test -f docs/x.md` |
| research | scout | cited notes | `test -f project/memory/literature/x.md` |
| design_experiment | scientist | draft spec + runner | `uv run mfos exp check E002`, `uv run python experiments/runners/e002.py --smoke` |
| investigate | scientist | diagnosis notes + report | `test -f research/diagnoses/T00xx.md` |
| experiment | none (orchestrator) | registered result | (none — the runner and evaluator decide) |

## Sizing
One coherent deliverable; 20–120 agent-minutes; ≤ 15 files changed. Split by interface, not by layer.

## Risk (drives review depth and merge policy)
low: docs, refactors with tests, tooling · medium: new modules, generators, adapters ·
high: physics models, reference solvers, experiment runners that feed acceptance criteria ·
critical: anything the evaluator reads or that a public claim will rest on.

## Budgets (USD per task, before escalation)
research 1–3 · implement 2–6 · design_experiment 3–6 · investigate 3–5.

## Dependencies and `touches`
Depend on what you consume, not on what merely came earlier. `touches` lists the globs a task will
edit, so two tasks with overlapping `touches` never run concurrently.

## Anti-patterns (reject your own plan if it contains these)
Tasks without machine-checkable DoD · "investigate and fix" in one task · tasks that restate the
objective · speculative infrastructure no criterion needs · more than one open task per file ·
re-running an evaluation instead of designing a discriminating experiment.

## Pre-flight checks for every task brief (all three failed briefs of 2026-11-14 missed one)
1. **Write scope.** Every deliverable and `touches` glob lies inside the agent's `[role_write_scopes]` in
   `.mfos/policy.toml`: builder src/, tests/unit/, tests/regression/, benchmarks/, docs/, pyproject.toml, uv.lock;
   scientist research/, experiments/drafts/, experiments/runners/, tests/acceptance_drafts/, project/memory/; scout
   research/notes/, project/memory/literature/. No role writes tools/, .claude/, .mfos/, experiments/specs/,
   project/decisions/ or tests/acceptance/; a brief that needs them goes to the founder.
2. **Free experiment id.** Ids are global across objectives: list `experiments/specs/` and `experiments/drafts/`,
   and the ids the evidence plans of draft objectives reserve, before naming one (D0021 named O007's E009, D0022).
3. **No check that depends on a later step.** Every definition-of-done command must pass on main plus this task's
   own changes; nothing that needs a later approval, registration or merge (E010's registration dry run needed O003
   v6, which came after its design task).
