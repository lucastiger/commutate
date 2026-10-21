"""Canary v2 end to end with the fake CLI (audit 2026-10-19): O901 goes through plan approval, an implementation,
an experiment design with rows, recompute and a null, terminal registration, a minted sealed run, recomputation,
the null check, the PASS critic, and a proposed claim that becomes supported only when the founder approves it.
Two variants seed the defects the new rules exist for. The real canary runs on the real CLI after the merge."""
import json
import shutil
import time
from pathlib import Path

import pytest

from mfos import models as m
from mfos.cli import main as cli
from mfos.loop import Orchestrator
from mfos.store import Store

REPO = Path(__file__).resolve().parents[2]


def setup_o901(sandbox):
    d = sandbox / "project" / "objectives" / "O901"
    d.mkdir(parents=True)
    shutil.copy(REPO / "project" / "objectives" / "O901" / "objective.yaml", d / "objective.yaml")
    s = Store()
    s.git("add", "-A")
    s.git("commit", "-qm", "draft O901", as_founder=True)
    assert cli(["objective", "approve", "O901"]) == 0


def drive(until, max_ticks=150):
    """Tick the loop, approving plan approvals and experiment registrations the way the founder would."""
    for _ in range(max_ticks):
        Orchestrator(Store()).tick()
        s = Store()
        for item in s.inbox("open"):
            if item.kind in ("plan_approval", "experiment_registration"):
                assert cli(["approve", item.id, "--note", "reviewed"]) == 0
        if until(Store()):
            return Store()
        time.sleep(0.2)
    raise AssertionError("condition not reached; open inbox: " + str([i.subject for i in Store().inbox("open")]))


def evaluations(s, suffix=""):
    return sorted((s.objective_dir("O901") / "evaluations").glob(f"EV-O901-*{suffix}.json")) \
        if (s.objective_dir("O901") / "evaluations").exists() else []


def test_canary_v2_passes_through_the_new_evidence_path(sandbox):
    setup_o901(sandbox)
    s = drive(lambda s: s.objective_state("O901").status in ("passed", "needs_founder"))
    st = s.objective_state("O901")
    assert st.status == "passed", (st, [i.subject for i in s.inbox("open")])
    assert st.evidence_rules == 2 and st.frozen_hash == s.frozen_hash(s.objective("O901"))

    spec = s.spec("E901")
    assert spec.evidence_rules == 2 and spec.code_under_test == ["src/moduleforge/canary.py"]
    minted = [r for r in s.registry() if r["event"] == "minted" and r["experiment"] == "E901"]
    ev = m.Evaluation.model_validate_json(evaluations(s)[0].read_text())
    run_id = ev.results_used["E901"]
    assert minted[0]["run_id"] == run_id and minted[0]["commitment"]  # minted before the run, seed committed

    res = m.ExperimentResult.model_validate_json(
        (s.root / "experiments" / "results" / "E901" / run_id / "result.json").read_text())
    assert res.provenance.code.keys() == {"src/moduleforge/canary.py"}
    assert res.provenance.runner_hashes.keys() == {"experiments/runners/e901_canary.py"}
    a1 = ev.pass_checks[0]
    assert ev.verdict == "PASS" and a1.recomputed and a1.verdict == "satisfied"
    assert a1.null_value > 1e-3  # the null predictor does not meet A1: the criterion discriminates
    assert all(v == "ok" or v.startswith("n/a") for v in ev.checks["E901"].values()), ev.checks

    claim = next(s.read_yaml(p, m.Claim) for p in (s.project / "claims").glob("C*.yaml"))
    assert claim.status == "proposed" and claim.scope.startswith("Sampled: decades: 1, 2, 3; n_max:")
    item = next(i for i in s.inbox("open") if i.kind == "claim_approval")
    assert cli(["approve", item.id]) == 0
    assert Store().read_yaml(s.project / "claims" / f"{claim.id}.yaml", m.Claim).status == "supported"
    assert not [t for t in s.tasks("O901") if t.type == "investigate"]


@pytest.mark.parametrize("env, verdict, needle", [
    ("FAKE_E901_MISREPORT", "INVALID", "E901.max_rel_err: runner reported"),
    ("FAKE_E901_NULL_EQUALS_PRED", "INCONCLUSIVE", "non-discriminating"),
])
def test_canary_v2_seeded_defects_never_pass(sandbox, monkeypatch, env, verdict, needle):
    monkeypatch.setenv(env, "1")
    setup_o901(sandbox)
    s = drive(lambda s: bool(evaluations(s)))
    ev = m.Evaluation.model_validate_json(evaluations(s)[0].read_text())
    assert ev.verdict == verdict, ev.explanation
    assert needle in ev.explanation, ev.explanation
    assert s.objective_state("O901").status != "passed"
    assert not [p for p in (s.project / "claims").glob("C*.yaml")
                if s.read_yaml(p, m.Claim).objective == "O901"]
    if verdict == "INVALID":  # the defective run is consumed visibly, not silently replaced
        assert any(r["event"] == "consumed" for r in s.registry()), json.dumps(s.registry())
