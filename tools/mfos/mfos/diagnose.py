"""Failure classification and response policy.

The deterministic layer classifies *signals*; an independent scientist run (fresh
context) then confirms or overturns the class with evidence and a discriminating
test. The response depends on the class, not on how the failure felt:

  implementation  code is wrong                 -> repair (fresh builder), then escalate model, then diagnose
  experimental    experiment/reference invalid  -> fix the experiment; hypothesis untouched; evidence voided
  model           physics/math assumption wrong -> diagnose + critic audit -> planner replans within objective
  planning        wrong objective/decomposition -> founder decision memo
  business        thesis weakening              -> founder decision memo (never auto-acted on)
  infrastructure  tooling, not the work         -> pause: the attempt is given back, no diagnosis is spawned,
                                                   one de-duplicated inbox item per cause (audit 2026-10-19: 7 of
                                                   O001's 8 spawned diagnoses had tooling causes)

Usage and network limits are not failures at all: the loop backs off until the stated reset (parse_limit_reset)
and resumes the interrupted session.
"""
from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass
from typing import Optional
from zoneinfo import ZoneInfo

SIGNAL_CLASS = {
    "dod_failed": "implementation",
    "gate_failed": "implementation",
    "scope_violation": "implementation",
    "agent_error": "implementation",
    "review_rejected": "implementation",
    "experiment_error": "implementation",
    "evidence_invalid": "experimental",
    "sanity_failed": "experimental",
    "verdict_inconclusive": "experimental",
    "verdict_fail": "model",
    "claim_conflict": "model",
    "attempts_exhausted": "planning",
    "replans_exhausted": "planning",
    "budget_exhausted": "planning",
    "evaluations_exhausted": "planning",
    "thesis_signal": "business",
    # tooling, not the work (never spends an attempt, never spawns a diagnosis)
    "no_structured_output": "infrastructure",
    "cli_error": "infrastructure",
    "spec_missing": "infrastructure",
    "integration_error": "infrastructure",
    "runner_killed": "infrastructure",
    "venv_provisioning": "infrastructure",
    # a registered runner crashed in repository code: a frozen runner bug needs a new experiment id
    "experiment_crash": "experimental",
}

# Claude Code CLI messages that mean the tool or its configuration failed, not the agent's work.
CLI_ERROR_SIGNS = ("invalid api key", "please run /login", "not logged in", "unknown option", "unknown argument",
                   "invalid permission mode", "failed to parse settings", "invalid settings", "sandbox is required",
                   "sandbox is unavailable", "sandbox dependencies", "no conversation found")


def classify_agent_error(text: str) -> Optional[str]:
    """``cli_error`` if an agent run's output shows the CLI or its configuration failed, else None."""
    low = text.lower()
    return "cli_error" if any(k in low for k in CLI_ERROR_SIGNS) else None


_TRACE_FRAME = re.compile(r'File "([^"]+)", line \d+')


def classify_experiment_failure(output: str, exit_code: Optional[int] = None) -> str:
    """Signal for an experiment that produced no complete result, from its runner log / result notes.

    experiment_crash  a traceback whose frames include repository code (experiments/runners/ or src/)
    spec_missing      the experiment was not registered, or its registration was not committed
    runner_killed     killed or timed out with no traceback (infrastructure)
    experiment_error  anything else (the existing repair route)
    """
    low = output.lower()
    if "is not a registered" in low or "registered spec is not committed" in low or "not registered" in low:
        return "spec_missing"
    frames = _TRACE_FRAME.findall(output)
    if any("experiments/runners/" in f or "/src/" in f or f.startswith("src/") for f in frames):
        return "experiment_crash"
    if exit_code in (-9, 137, 143) or "timed out" in low or "timeoutexpired" in low or (exit_code and not frames):
        return "runner_killed"
    return "experiment_error"


_RESET = re.compile(r"resets\s+(?:(?P<mon>[A-Z][a-z]{2})\s+(?P<day>\d{1,2}),?\s*)?(?P<h>\d{1,2})(?::(?P<m>\d{2}))?"
                    r"\s*(?P<ap>am|pm)(?:\s*\((?P<tz>[^)]+)\))?", re.I)
_MONTHS = {m: i for i, m in enumerate(("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov",
                                       "dec"), start=1)}


def parse_limit_reset(text: str, now: Optional[dt.datetime] = None) -> Optional[dt.datetime]:
    """The reset time a Claude Code usage-limit message states, as an aware datetime, or None.

    Forms seen in O001's run records and tests: "You've hit your session limit · resets 11pm (America/Los_Angeles)",
    "… resets 11:30am (America/Los_Angeles)", "… weekly limit · resets Oct 3, 9am", "5-hour limit reached ∙ resets 3pm".
    Without a zone the machine's local zone is assumed; without a date, the next such time after ``now``.
    """
    mt = _RESET.search(text or "")
    if not mt:
        return None
    now = now or dt.datetime.now(dt.timezone.utc)
    try:
        tz = ZoneInfo(mt["tz"].strip()) if mt["tz"] else now.astimezone().tzinfo
    except Exception:
        return None
    local = now.astimezone(tz)
    h12, minute = int(mt["h"]), int(mt["m"] or 0)
    if not 1 <= h12 <= 12 or minute > 59:
        return None
    hour = h12 % 12 + (12 if mt["ap"].lower() == "pm" else 0)
    if mt["mon"]:
        month = _MONTHS.get(mt["mon"].lower())
        if month is None:
            return None
        cand = local.replace(month=month, day=int(mt["day"]), hour=hour, minute=minute, second=0, microsecond=0)
        if cand < local - dt.timedelta(days=1):
            cand = cand.replace(year=cand.year + 1)
        return cand
    cand = local.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if cand <= local:
        cand += dt.timedelta(days=1)
    return cand


@dataclass
class Response:
    failure_class: str
    action: str  # repair | diagnose | fix_experiment | replan | founder
    needs_review: bool
    note: str


def respond(signal: str, attempts: int = 0, max_attempts: int = 3) -> Response:
    cls = SIGNAL_CLASS.get(signal, "planning")
    if cls == "infrastructure":
        return Response(cls, "pause", False,
                        "tooling failure, not the work: no attempt used, no diagnosis; fix the cause, then approve "
                        "the inbox item to retry")
    if signal == "experiment_crash":
        return Response(cls, "founder", False,
                        "the registered runner crashed in repository code; a frozen runner bug needs a new "
                        "experiment id (never re-run automatically)")
    if cls == "implementation":
        if attempts < max_attempts:
            return Response(cls, "repair", False, "retry in a fresh session with the failure output")
        return Response(cls, "diagnose", False, "repairs exhausted; scientist diagnoses before replanning")
    if cls == "experimental":
        return Response(cls, "fix_experiment", True,
                        "evidence voided; scientist repairs the experiment design; critic reviews the new design")
    if cls == "model":
        return Response(cls, "diagnose", True,
                        "independent diagnosis with alternatives and a discriminating test, plus critic audit")
    return Response(cls, "founder", False, "requires a founder decision")
