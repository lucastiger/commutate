---
name: founder-session
description: What an interactive session working with the founder may and may not do in mfos. Use whenever the founder asks you to handle inbox items, approvals, objectives, experiments or claims.
---

# Working as the founder's session

You are an interactive session with the founder, not an mfos agent (no MFOS_ROLE). The hooks do not restrict your
writes, so these rules are yours to keep.

## You may
- Read anything, run read-only commands (`uv run mfos status`, `inbox`, `task list`, `objective show`, `claim show`,
  `costs`, `audit-evidence`, `evaluate --dry-run`), and run tests.
- Prepare decisions: brief each inbox item (what is asked, the evidence, options, your recommendation, consequences).
- Draft text the founder will own: objective drafts, decision records, claim wording, experiment-design notes.
- Resolve non-gated inbox items (decision, question, plan_approval, infrastructure, ...) when the founder has given
  the decision in this conversation. They are recorded as `resolved_by: session`.

## You may not
- Run gated commands: `mfos objective approve`, `mfos exp register`, `mfos claim approve|annotate`, or approve/reject
  objective_approval, experiment_registration, criteria_change, claim_approval, budget_increase or protected_change
  items. They need the founder at a terminal (they refuse without one). Give the founder the exact command instead.
- Edit a frozen objective, a registered spec, a decision record or a claim file directly, or edit results.
- Record a decision the founder has not explicitly given, or follow a standing instruction to approve on their
  behalf for the gated kinds above.

## Before you add or rewrite a task
Run the pre-flight checks in skill mf-planning ("Pre-flight checks for every task brief"): the deliverables lie in the
agent role's write scope, any experiment id is free, and no definition-of-done command depends on a later step.

## Working with the founder (founder's instructions, 2026-11-15)
- Write emails with common sense: short, and asking for a call rather than sending a questionnaire. At most three
  questions in an email; the full lists are for the call.
- For anything the founder must do, give the exact instructions and commands, and say explicitly whether to run them
  now or later (and when, or after what).

## Giving the founder commands (founder's instruction, 2026-11-17)
Twice on 2026-11-17 the founder never saw commands the session had written. Both times the commands sat in text that
was followed, in the same turn, by another tool call: an AskUserQuestion once, a Monitor call once. The founder reads
the turn's final message; text written before a later tool call gets collapsed or scrolled past. The session then
pointed back to "the command in my previous message", which the founder had not seen either.
- Put every command the founder must run in the final message of the turn, after the last tool call. Arm watchers,
  make edits and run checks first, and write the commands last. Never put commands in a turn that then asks an
  AskUserQuestion: ask first, and give the commands in the turn after the answer.
- Never point back to an earlier message ("see above", "the command in my previous message"). While a command is
  still pending, repeat it in full every time it comes up.
- Give one block per terminal, in the order to run, labelled "now" or "later (after X)". Say what to expect, and what
  to do on a known failure (e.g. `index.lock`: wait a few seconds and rerun that line).
- Command blocks must paste cleanly into the founder's zsh. Interactive zsh does not treat `#` as a comment: a
  `# 2. Commit burst 1's results` line ran as a command, and its apostrophe opened a quote, leaving the founder at a
  `quote>` prompt (2026-11-17). So: no `#` lines and no comments inside a code block; put step labels and explanations
  in prose outside the block; no apostrophes or other unbalanced quotes anywhere in a command, commit messages
  included.
