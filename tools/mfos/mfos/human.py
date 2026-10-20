"""Terminal confirmation for the actions that define evidence (audit 2026-10-19, W5).

Approving an objective, registering an experiment, approving or annotating a claim, and approving criteria changes,
budget increases or protected changes need the founder at a terminal: stdin and stdout are TTYs and the founder types
the id back. A Claude Code shell has no TTY, so an AI session cannot do these by itself; it can prepare them and tell
the founder the command. This is a recording and friction mechanism, not a sandbox: a determined process can fake a
terminal. The guard hook additionally blocks these commands outright for agent roles.

Tests replace ``interactive`` and ``ask`` in-process; there is deliberately no environment-variable escape hatch.
"""
from __future__ import annotations

import sys

# inbox kinds whose resolution is a human act
GATED_KINDS = {"objective_approval", "experiment_registration", "criteria_change", "claim_approval",
               "budget_increase", "protected_change"}


def interactive() -> bool:
    try:
        return sys.stdin.isatty() and sys.stdout.isatty()
    except (AttributeError, ValueError):
        return False


def ask(prompt: str) -> str:
    return input(prompt)


def confirm(command: str, expect: str) -> bool:
    """True only if a person at a terminal typed ``expect``. Prints why not otherwise."""
    if not interactive():
        print(f"This action must be confirmed by the founder in a terminal: run `uv run mfos {command}` yourself.",
              file=sys.stderr)
        return False
    typed = ask(f"Type {expect} to confirm `mfos {command}`: ").strip()
    if typed != expect:
        print("Not confirmed; nothing changed.", file=sys.stderr)
        return False
    return True


def resolver() -> str:
    """Who resolved a non-gated item: "human" at a terminal, otherwise "session"."""
    return "human" if interactive() else "session"
