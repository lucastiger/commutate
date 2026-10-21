"""Claims cannot state more than was sampled, verdicts bring their pre-registered decision to the founder, and the
acts that define evidence need the founder at a terminal (audit 2026-10-19, C4 and W5)."""
import time
from pathlib import Path

import pytest

from mfos import human
from mfos import models as m
from mfos.cli import main as cli
from mfos.loop import Orchestrator
from mfos.store import Store

from test_hooks import run_guard

REPO = Path(__file__).resolve().parents[2]


def drive(oid="O000", max_ticks=80):
    s = Store()
    o = Orchestrator(s)
    for _ in range(max_ticks):
        o.tick()
        if s.objective_state(oid).status in ("passed", "failed", "needs_founder"):
            break
        time.sleep(0.3)
    return Store()


def declare_domain(sandbox):
    runner = sandbox / "experiments" / "runners" / "e000_canary.py"
    text = runner.read_text()
    marker = '        run.metric("max_rel_err", max(errs), n=len(ns))\n'
    assert marker in text
    runner.write_text(text.replace(marker, marker + "        run.domain(n=ns, implementation=['float64 fsum'])\n"))
    Store().git("commit", "-qam", "E000 declares its sampled domain", as_founder=True)


def test_a_pass_proposes_a_claim_scoped_by_what_was_sampled(sandbox):
    declare_domain(sandbox)
    assert cli(["exp", "register", "E000"]) == 0
    assert cli(["objective", "approve", "O000"]) == 0
    s = drive()
    assert s.objective_state("O000").status == "passed"
    claim = s.read_yaml(s.project / "claims" / "C001.yaml", m.Claim)
    assert claim.status == "proposed"
    assert claim.domain == {"implementation": ["float64 fsum"], "n": [1000, 10000, 100000, 1000000]}
    assert claim.scope.startswith("Sampled: implementation: float64 fsum; n: 1000, 10000, 100000, 1000000.")
    item = next(i for i in s.inbox("open") if i.kind == "claim_approval")
    assert item.refs[0] == "C001"
    assert cli(["approve", item.id]) == 0  # the founder at a terminal (patched TTY)
    s = Store()
    claim = s.read_yaml(s.project / "claims" / "C001.yaml", m.Claim)
    assert (claim.status, claim.approved_by) == ("supported", "founder")
    assert "Approve claim C001" in s.git("log", "-1", "--format=%s")


def test_a_claim_without_a_declared_domain_needs_an_explicit_scope(sandbox, monkeypatch):
    assert cli(["exp", "register", "E000"]) == 0
    assert cli(["objective", "approve", "O000"]) == 0
    s = drive()
    claim = s.read_yaml(s.project / "claims" / "C001.yaml", m.Claim)
    assert claim.status == "proposed" and claim.scope.startswith("UNSPECIFIED")
    monkeypatch.setattr(human, "interactive", lambda: False)
    assert cli(["claim", "approve", "C001", "--scope", "n in {1e3, 1e4, 1e5, 1e6}"]) == 2  # no terminal: refused
    monkeypatch.setattr(human, "interactive", lambda: True)
    assert cli(["claim", "approve", "C001"]) == 1  # no domain and no --scope
    assert cli(["claim", "approve", "C001", "--scope", "n in {1e3, 1e4, 1e5, 1e6}, float64"]) == 0
    claim = Store().read_yaml(Store().project / "claims" / "C001.yaml", m.Claim)
    assert claim.status == "supported" and claim.scope == "n in {1e3, 1e4, 1e5, 1e6}, float64"


def test_annotations_append_and_never_rewrite(sandbox):
    s = Store()
    c = m.Claim(id="C001", statement="L1 ranks layouts", scope="DBC; 70x40 mm", status="supported", objective="O000",
                evaluation="EV-O000-01")
    s.write_yaml(s.project / "claims" / "C001.yaml", c)
    assert cli(["claim", "annotate", "C001", "--decision", "D0006", "--note", "scope restricted after audit",
                "--restrict", "DBC only", "--restrict", "pooled ranking only"]) == 0
    c2 = Store().read_yaml(s.project / "claims" / "C001.yaml", m.Claim)
    assert (c2.statement, c2.scope, c2.status) == (c.statement, c.scope, c.status)
    assert c2.scope_restrictions == ["DBC only", "pooled ranking only"]
    assert c2.annotations[0].decision == "D0006" and c2.annotations[0].by == "founder"


def test_the_live_claims_still_load():
    s = Store(REPO)
    for cid in ("C001", "C002"):
        assert s.read_yaml(s.project / "claims" / f"{cid}.yaml", m.Claim).status == "supported"


def test_a_fail_verdict_brings_the_pre_registered_decision_to_the_founder(sandbox, monkeypatch):
    monkeypatch.setenv("FAKE_SUBTLE_BUG_ONCE", "1")
    assert cli(["exp", "register", "E000"]) == 0
    assert cli(["objective", "approve", "O000"]) == 0
    s = drive(max_ticks=140)
    items = [i for i in s.inbox(None) if i.subject.startswith("[O000] FAIL (EV-O000-01)")]
    assert items and "Fix mfos configuration" in items[0].summary  # O000's decision_if_fail, quoted


def test_an_inconclusive_verdict_quotes_decision_if_inconclusive(sandbox, monkeypatch):
    from test_seeded_failures import setup
    from mfos import experiments
    setup(sandbox, monkeypatch)
    monkeypatch.setenv("SEEDED_MODE", "strata_only")
    experiments.run(Store(), "E900", force=True)
    s = Store()
    st = s.objective_state("O900")
    Orchestrator(s)._maybe_evaluate("O900", s.objective("O900"), st)
    item = next(i for i in Store().inbox("open") if i.subject.startswith("[O900] INCONCLUSIVE"))
    assert "diagnose the design" in item.summary


def test_founder_acts_refuse_without_a_terminal_and_other_resolutions_are_attributed(sandbox, monkeypatch):
    monkeypatch.setattr(human, "interactive", lambda: False)
    assert cli(["exp", "register", "E000"]) == 2
    assert not Store().spec_path("E000").exists()
    assert cli(["objective", "approve", "O000"]) == 2
    assert Store().objective_state("O000").status == "draft"
    s = Store()
    reg = s.add_inbox(kind="experiment_registration", subject="register E000", summary="x", refs=["E000"])
    assert cli(["approve", reg.id]) == 2 and Store().inbox("open")
    q = s.add_inbox(kind="question", subject="which stack?", summary="x", refs=[])
    assert cli(["answer", q.id, "DBC first"]) == 0
    assert Store().read_yaml(s.project / "inbox" / f"{q.id}.yaml", m.InboxItem).resolved_by == "session"
    monkeypatch.setattr(human, "interactive", lambda: True)
    monkeypatch.setattr(human, "ask", lambda prompt: "WRONG")
    assert cli(["objective", "approve", "O000"]) == 2  # typed the wrong id


@pytest.mark.parametrize("command, decision", [
    ("uv run mfos objective approve O004", "deny"),
    ("uv run mfos approve I0001 --note ok", "deny"),
    ("uv run mfos exp register E004", "deny"),
    ("cd x && uv run python -m mfos.cli claim approve C003", "deny"),
    ("uv run mfos evaluate O004", "deny"),
    ("uv run mfos loop --once", "deny"),
    ("uv run mfos gate --fast", "allow"),
    ("uv run mfos exp check E004", "allow"),
    ("uv run mfos evaluate O004 --dry-run", "allow"),
    ("uv run mfos inbox", "allow"),
    ("uv run mfos task list --status running", "allow"),
    ("uv run mfos objective show O004 | head", "allow"),
])
def test_agents_cannot_run_founder_commands(command, decision):
    assert run_guard("builder", "Bash", {"command": command}) == decision
    assert run_guard("", "Bash", {"command": command}) == "allow"  # the founder's own session is not guarded
