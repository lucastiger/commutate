"""Failures of the tooling are not failures of the work (audit 2026-10-19, C5/W1/W4/W6): the infrastructure class,
usage-limit scheduling with session resume, token and denial accounting, and the run archive."""
import datetime as dt
import json
import tarfile
import time

import pytest

from mfos import diagnose
from mfos import models as m
from mfos.agents import AgentRunner, RunRecord
from mfos.cli import main as cli
from mfos.loop import Orchestrator
from mfos.store import Store

LA = "America/Los_Angeles"


# ------------------------------------------------------------------------------------------------ classification
@pytest.mark.parametrize("signal", ["no_structured_output", "cli_error", "spec_missing", "integration_error",
                                    "runner_killed", "venv_provisioning"])
def test_tooling_signals_pause_without_spending_anything(signal):
    r = diagnose.respond(signal, attempts=3, max_attempts=3)
    assert (r.failure_class, r.action) == ("infrastructure", "pause")


def test_a_crashed_runner_goes_to_the_founder_not_to_a_rerun():
    r = diagnose.respond("experiment_crash")
    assert (r.failure_class, r.action) == ("experimental", "founder")
    assert diagnose.respond("dod_failed", 0, 3).action == "repair"  # the agent's own failures keep their route


@pytest.mark.parametrize("output, code, signal", [
    ('Traceback (most recent call last):\n  File "/wt/exp-E002/experiments/runners/e002_ranking.py", line 9\n'
     'KeyError: 1', None, "experiment_crash"),
    ('Traceback (most recent call last):\n  File "/wt/exp-E002/src/moduleforge/solvers/l2.py", line 3\nValueError',
     None, "experiment_crash"),
    ("RuntimeError: E002 is not a registered, unmodified spec; refusing to run", None, "spec_missing"),
    ("E004: the registered spec is not committed in main; commit the registration first", None, "spec_missing"),
    ("", -9, "runner_killed"),
    ("runner exit code -9; no result.json written", None, "experiment_error"),
])
def test_experiment_failure_classification(output, code, signal):
    assert diagnose.classify_experiment_failure(output, code) == signal


def test_cli_errors_are_recognized():
    assert diagnose.classify_agent_error("Invalid API key · Please run /login") == "cli_error"
    assert diagnose.classify_agent_error("error: unknown option '--permission-prompts'") == "cli_error"
    assert diagnose.classify_agent_error("Traceback (most recent call last): KeyError: 'x'") is None


# ------------------------------------------------------------------------------------------------ usage limits
NOW = dt.datetime(2026, 10, 19, 20, 0, tzinfo=dt.timezone.utc)  # 13:00 in Los Angeles


@pytest.mark.parametrize("when, expect", [
    ("11pm", (19, 23, 0)), ("11:30am", (20, 11, 30)), ("4am", (20, 4, 0)), ("5:30pm", (19, 17, 30)),
    ("12:20am", (20, 0, 20)), ("6pm", (19, 18, 0)), ("7:20pm", (19, 19, 20)), ("8:50pm", (19, 20, 50)),
    ("9:30pm", (19, 21, 30)), ("4:30pm", (19, 16, 30)),
])
def test_every_observed_reset_form_parses(when, expect):
    """The ten reset times in O001's 61 limit messages, all of the form `… · resets 11pm (America/Los_Angeles)`."""
    t = diagnose.parse_limit_reset(f"You've hit your session limit · resets {when} ({LA})", NOW)
    assert t is not None and str(t.tzinfo) == LA
    assert (t.day, t.hour, t.minute) == expect


def test_reset_parsing_edge_cases():
    late = dt.datetime(2026, 10, 20, 6, 50, tzinfo=dt.timezone.utc)  # 23:50 in Los Angeles: 12:20am is tomorrow
    t = diagnose.parse_limit_reset(f"resets 12:20am ({LA})", late)
    assert (t.month, t.day, t.hour, t.minute) == (10, 20, 0, 20)
    t = diagnose.parse_limit_reset("You've hit your weekly limit · resets Oct 23, 9am", NOW)
    assert (t.month, t.day, t.hour) == (10, 23, 9)
    assert diagnose.parse_limit_reset("5-hour limit reached ∙ resets 3pm", NOW) is not None
    assert diagnose.parse_limit_reset("Traceback: KeyError", NOW) is None
    assert diagnose.parse_limit_reset("resets 25pm (America/Los_Angeles)", NOW) is None
    assert diagnose.parse_limit_reset("resets 9pm (Nowhere/Invalid)", NOW) is None


def _limit_record(task, session="S-1"):
    return RunRecord(run_id=f"{task.id}-r", task_id=task.id, role=task.agent, session_id=session, cwd=".", started="",
                     status="error", is_error=True, subtype="success",
                     result_text=f"You've hit your session limit · resets 11pm ({LA})",
                     extra={"api_error_status": 429})


def test_a_usage_limit_waits_for_the_stated_reset_then_resumes_the_same_session(sandbox, monkeypatch):
    s = Store()
    o = Orchestrator(s)
    t = m.Task(id="T9600", objective="O000", title="build", type="implement", agent="builder", status="running",
               attempts=1)
    s.save_task(t)
    before = time.time()
    o._on_run_done(t, _limit_record(t))
    t = Store().task("T9600")
    assert (t.status, t.attempts, t.history[-1]["outcome"]) == ("todo", 0, "capacity_backoff")
    until = float((s.mfos / "backoff_until").read_text())
    reset = diagnose.parse_limit_reset(f"resets 11pm ({LA})")
    assert until == pytest.approx(reset.timestamp() + 120, abs=5) and until > before
    assert t.history[-1]["session"] == "S-1"

    started = []
    monkeypatch.setattr(o, "_start_agent", lambda task, resume=None: started.append(
        (task.id, resume, task.attempts, task.history[-1]["outcome"])))
    (s.mfos / "backoff_until").unlink()  # the reset has passed
    st = s.objective_state("O000")
    st.status = "active"
    s.save_objective_state("O000", st)
    o._dispatch()
    assert started == [("T9600", "S-1", 1, "capacity_resume")]  # the same attempt continues in the same session


def test_after_two_resumes_a_limited_task_starts_afresh(sandbox):
    o = Orchestrator(Store())
    hist = [{"outcome": "capacity_backoff", "session": "S"}, {"outcome": "capacity_resume"},
            {"outcome": "capacity_backoff", "session": "S"}, {"outcome": "capacity_resume"},
            {"outcome": "capacity_backoff", "session": "S"}]
    t = m.Task(id="T9601", objective="O000", title="x", type="implement", agent="builder", history=hist)
    assert o._resumable_session(t) is None
    assert o._resumable_session(t.model_copy(update={"history": hist[:3]})) == "S"
    network = [{"outcome": "capacity_backoff", "session": None}]  # a network error has no session worth resuming
    assert o._resumable_session(t.model_copy(update={"history": network})) is None


# ------------------------------------------------------------------------------------------------ pause semantics
def _review(tid, attempts=1):
    return m.Task(id=tid, objective="O000", title=f"review {tid}", type="review", agent="critic", status="running",
                  attempts=attempts, target="T0001", lens="physics")


def test_missing_reports_pause_once_per_cause_and_resume_on_approval(sandbox):
    s = Store()
    o = Orchestrator(s)
    for tid in ("T9700", "T9701"):
        t = _review(tid)
        s.save_task(t)
        o._on_run_done(t, RunRecord(run_id=f"{tid}-r", task_id=tid, role="critic", session_id="x", cwd=".",
                                    started="", status="completed", structured_output=None, result_text="All done."))
    s = Store()
    items = [i for i in s.inbox("open") if i.kind == "infrastructure"]
    assert len(items) == 1 and items[0].refs == ["T9700", "T9701"]
    for tid in ("T9700", "T9701"):
        t = s.task(tid)
        assert (t.status, t.attempts, t.history[-1]["outcome"]) == ("needs_founder", 0, "no_structured_output")
    assert not [t for t in s.tasks() if t.type == "investigate"]
    assert cli(["approve", items[0].id, "--note", "agent tools fixed"]) == 0
    assert {Store().task(tid).status for tid in ("T9700", "T9701")} == {"todo"}


def test_a_plan_out_of_attempts_goes_to_the_founder_without_a_diagnosis(sandbox):
    s = Store()
    o = Orchestrator(s)
    t = m.Task(id="T9702", objective="O000", title="plan", type="plan", agent="planner", status="running",
               attempts=3, max_attempts=3)
    s.save_task(t)
    o._fail(t, "agent_error", "planner returned invalid plan", "validation error")
    s = Store()
    assert s.task("T9702").status == "needs_founder"
    assert not [x for x in s.tasks() if x.type == "investigate"]
    assert any("T9702" in i.refs for i in s.inbox("open"))


def test_a_cli_error_is_an_infrastructure_pause(sandbox):
    s = Store()
    o = Orchestrator(s)
    t = m.Task(id="T9703", objective="O000", title="build", type="implement", agent="builder", status="running",
               attempts=1)
    s.save_task(t)
    o._on_run_done(t, RunRecord(run_id="T9703-r", task_id="T9703", role="builder", session_id="x", cwd=".", started="",
                                status="error", is_error=True, subtype="error_during_execution",
                                result_text="Invalid API key · Please run /login"))
    t = Store().task("T9703")
    assert (t.status, t.attempts) == ("needs_founder", 0)
    assert any(i.subject == "infrastructure: cli_error" for i in Store().inbox("open"))


# ------------------------------------------------------------------------------------------------ accounting, archive
def _finished_run(s, tid, packet_text="# packet\n", denials=2):
    runner = AgentRunner(s)
    cwd = s.root
    (cwd / ".mfos" / "packets").mkdir(parents=True, exist_ok=True)
    (cwd / ".mfos" / "packets" / f"{tid}-a1.md").write_text(packet_text)
    (cwd / ".mfos" / "packets" / f"{tid}-a1.dod.json").write_text("{}")
    rec = RunRecord(run_id=f"{tid}-critic-x", task_id=tid, role="critic", session_id="sess-1", cwd=str(cwd),
                    started="", pid=None, packet=f".mfos/packets/{tid}-a1.md", deadline=time.time() + 600)
    runner.save(rec)
    out = {"type": "result", "subtype": "success", "is_error": False, "result": "ok", "structured_output": {},
           "session_id": "sess-1", "total_cost_usd": 1.25, "num_turns": 4,
           "usage": {"input_tokens": 7, "cache_creation_input_tokens": 70, "cache_read_input_tokens": 700,
                     "output_tokens": 30, "output_tokens_details": {"thinking_tokens": 12}},
           "modelUsage": {"claude-opus-5-5": {}},
           "permission_denials": [{"tool_name": "Bash", "tool_use_id": str(i), "tool_input": {}} for i in range(denials)]}
    (runner.runs_dir / rec.run_id / "stdout.json").write_text(json.dumps(out))
    return runner, runner.poll(rec)


def test_usage_and_denials_are_recorded_and_reported(sandbox, capsys):
    s = Store()
    s.save_task(_review("T9800"))
    _, rec = _finished_run(s, "T9800", denials=3)
    assert rec.extra["usage"] == {"input": 7, "cache_creation": 70, "cache_read": 700, "output": 30, "thinking": 12}
    assert rec.extra["denials"] == 3 and rec.extra["denied_tools"] == {"Bash": 3}
    assert rec.extra["models"] == ["claude-opus-5-5"]
    capsys.readouterr()
    assert cli(["costs"]) == 0
    out = capsys.readouterr().out
    row = next(line for line in out.splitlines() if line.startswith("O000"))
    assert row.split()[1:3] == ["1", "1.25"] and row.split()[-2:] == ["3", "0"]


def test_packets_and_transcripts_are_archived_with_the_run(sandbox, tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "claude"))
    proj = tmp_path / "claude" / "projects" / "-x-mf-main"
    proj.mkdir(parents=True)
    (proj / "sess-1.jsonl").write_text('{"type": "user"}\n')
    s = Store()
    s.save_task(_review("T9801"))
    runner, rec = _finished_run(s, "T9801", packet_text="# the brief\n")
    rdir = runner.runs_dir / rec.run_id
    assert (rdir / "packet.md").read_text() == "# the brief\n"
    assert (rdir / "dod.json").exists() and (rdir / "transcript.jsonl").exists()
    assert cli(["archive", "--dest", str(tmp_path / "arch")]) == 0
    archive = next((tmp_path / "arch").glob("mfos-archive-*.tar.gz"))
    with tarfile.open(archive) as tar:
        assert f".mfos/runs/{rec.run_id}/packet.md" in tar.getnames()
    assert next((tmp_path / "arch").glob("*.sha256")).read_text().count(".mfos/runs/") >= 3


# ------------------------------------------------------------------------------------------------ founder stops
@pytest.mark.parametrize("held_as", ["needs_founder", "cancelled"])
@pytest.mark.parametrize("run_status", ["interrupted", "error", "completed"])
def test_a_run_that_ends_while_the_founder_holds_or_cancels_its_task_is_the_founders_stop(sandbox, held_as,
                                                                                          run_status):
    """2026-11-03: a hold followed by a stop used T0216's last attempt and spawned diagnosis T0218; a cancel of T0218
    was undone because the loop resumed the interrupted run."""
    s = Store()
    o = Orchestrator(s)
    o._start_agent = lambda *a, **k: pytest.fail("a founder-stopped task must not be resumed")
    t = m.Task(id="T9710", objective="O000", title="build", type="implement", agent="builder", status=held_as,
               attempts=3, max_attempts=3)
    s.save_task(t)
    o._on_run_done(t, RunRecord(run_id="T9710-r", task_id="T9710", role="builder", session_id="x", cwd=".",
                                started="2026-11-03T23:29:00+00:00", status=run_status,
                                is_error=run_status == "error", subtype="error_during_execution",
                                result_text="stopped"))
    t = Store().task("T9710")
    assert (t.status, t.attempts) == (held_as, 2)
    assert t.history[-1]["outcome"] == "founder_stopped"
    assert not [x for x in Store().tasks() if x.type == "investigate"]


def test_an_interrupted_run_of_a_running_task_is_still_resumed_once(sandbox):
    s = Store()
    o = Orchestrator(s)
    started = []
    o._start_agent = lambda t, resume=None: started.append(resume)
    t = m.Task(id="T9711", objective="O000", title="build", type="implement", agent="builder", status="running",
               attempts=1)
    s.save_task(t)
    o._on_run_done(t, RunRecord(run_id="T9711-r", task_id="T9711", role="builder", session_id="sess", cwd=".",
                                started="", status="interrupted"))
    assert started == ["sess"]


def test_a_review_parked_by_the_founder_or_infrastructure_blocks_the_merge(sandbox):
    """2026-11-03: T0206 reached merge while its review T0215 was parked (needs_founder) by a network outage."""
    s = Store()
    o = Orchestrator(s)
    t = m.Task(id="T9712", objective="O000", title="build", type="implement", agent="builder", status="review")
    s.save_task(t)
    parked = m.Task(id="T9713", objective="O000", title="Review T9712 (general)", type="review", agent="critic",
                    status="needs_founder", target="T9712")
    o.git.head = lambda path=None: "abc123"
    o._reviews_for = lambda target, ref=None: ([parked], [])
    o._merge = lambda task: pytest.fail("must not merge past a parked review")
    o._advance(t)
    assert Store().task("T9712").status == "review"
