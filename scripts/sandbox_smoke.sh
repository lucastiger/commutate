#!/usr/bin/env bash
# Smoke test of the agent sandbox with this machine's real Claude Code CLI (audit 2026-10-19, W2). Costs <= $0.50.
# Run it after merging the sandbox change and after every Claude Code update. Prints PASS (exit 0) or FAIL (exit 1).
# See scripts/sandbox_smoke.py for what it checks. MFOS_CLAUDE_BIN overrides the CLI, as for the orchestrator.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
exec uv run python scripts/sandbox_smoke.py "$@"
