"""Reviews converge and pay for themselves (audit 2026-10-19, W2/W3): materiality, a round cap with a founder brief,
the verifier's report in evaluation reviews, adversarial review of objective drafts, the full gate before high-risk
merges."""
import time

from mfos import models as m
from mfos.agents import RunRecord
from mfos.cli import main as cli
from mfos.loop import Orchestrator
from mfos.store import Store


def _review_task(s, rid="T9950", target="T9000"):
    t = m.Task(id=rid, objective="O000", title=f"Review {target}", type="review", agent="critic", status="running",
               target=target, lens="general", description="0" * 40)
    s.save_task(t)
    return t


def _finish_review(o, t, review):
    o._on_review(t, RunRecord(run_id="r", task_id=t.id, role="critic", session_id="x", cwd=".", started=""),
                 review.model_dump())
    return m.Review.model_validate_json((o.s.project / "reviews" / t.target / f"{t.id}.json").read_text())


def test_a_reject_needs_an_evidence_or_correctness_blocker(sandbox):
    s = Store()
    o = Orchestrator(s)
    second_order = m.Review(verdict="reject", independent_checks_performed=["re-ran the estimator"],
                            findings=[m.Finding(severity="blocker", title="the bound could be tighter", detail="x",
                                                impact="scope")])
    stored = _finish_review(o, _review_task(s, "T9950"), second_order)
    assert stored.verdict == "accept_with_caveats" and "downgraded by policy" in stored.caveats[-1]
    assert stored.findings[0].title == "the bound could be tighter"  # the critic's findings stay as written
    real = m.Review(verdict="reject", independent_checks_performed=["ran the tests"],
                    findings=[m.Finding(severity="blocker", title="wrong sign", detail="x", impact="correctness")])
    assert _finish_review(o, _review_task(s, "T9951"), real).verdict == "reject"


def _task_with_rejecting_review(s, o, prior_rejections):
    t = m.Task(id="T9000", objective="O000", title="Change", type="implement", agent="builder", status="review",
               risk="medium", attempts=1,
               history=[{"outcome": "review_rejected", "summary": "x"}] * prior_rejections)
    s.save_task(t)
    path = o.git.task_worktree(t)
    s.save_task(t)
    head = o.git.head(path)
    s.save_task(m.Task(id="T9960", objective="O000", title="Review T9000", type="review", agent="critic",
                       status="done", target="T9000", lens="general", description=head))
    p = s.project / "reviews" / "T9000" / "T9960.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(m.Review(verdict="reject", findings=[
        m.Finding(severity="blocker", title="units off by 1e3", detail="x", impact="correctness",
                  suggested_check="compare with Grover")]).model_dump_json())
    return s.task("T9000")


def test_the_first_rejection_goes_back_for_repair(sandbox):
    s = Store()
    o = Orchestrator(s)
    o._advance(_task_with_rejecting_review(s, o, prior_rejections=0))
    t = Store().task("T9000")
    assert t.status == "todo" and t.history[-1]["outcome"] == "review_rejected"


def test_the_second_rejected_round_goes_to_the_founder_with_a_brief(sandbox):
    s = Store()
    o = Orchestrator(s)
    o._advance(_task_with_rejecting_review(s, o, prior_rejections=1))
    s = Store()
    t = s.task("T9000")
    assert t.status == "needs_founder" and t.history[-1]["outcome"] == "review_round_cap"
    item = next(i for i in s.inbox("open") if i.subject.startswith("T9000: 2 review rounds rejected"))
    assert "[blocker, impact correctness] units off by 1e3 (check: compare with Grover)" in item.summary
    assert not [x for x in s.tasks() if x.type == "investigate"]


def test_evaluation_reviews_start_from_the_verifiers_report(sandbox):
    s = Store()
    o = Orchestrator(s)
    ev = m.Evaluation(id="EV-O000-01", objective="O000", timestamp="t", criteria_hash=None, evaluator_version="2.0.0",
                      results_used={"E000": "E000-r1"}, validity_problems=[], verdict="PASS", explanation="",
                      fail_checks=[], checks={"E000": {"on_main": "ok", "registry": "ok"}},
                      pass_checks=[m.CriterionVerdict(id="A1", metric="E000.max_rel_err", comparator="<=",
                                                      threshold=1e-9, value=1e-12, bound_used=1e-12,
                                                      verdict="satisfied", recomputed=True, runner_value=1e-12,
                                                      null_value=0.4)])
    s.write_json(s.objective_dir("O000") / "evaluations" / "EV-O000-01.json", ev)
    rt = m.Task(id="T9970", objective="O000", title="Review EV", type="review", agent="critic", target="EV-O000-01")
    _, material = o._review_material(rt, s.root)
    assert material.startswith("### Verified by code (evaluator 2.0.0)")
    assert "E000: on_main ok; registry ok" in material and "null 0.4 -> satisfied" in material


DRAFT = """id: O777
title: draft under review
hypothesis: {statement: L1 picks the best of six layouts within each stratum}
evidence_plan: [E777]
acceptance:
  required_experiments: [E777]
  pass_all: [{id: A1, metric: E777.regret, comparator: "<=", threshold: 0.02, uncertainty: {use: point}}]
notes: see D0006
"""


def test_an_objective_draft_is_reviewed_before_approval(sandbox, capsys):
    s = Store()
    d = s.objective_dir("O777")
    d.mkdir(parents=True)
    (d / "objective.yaml").write_text(DRAFT)
    assert cli(["objective", "review", "O777"]) == 1  # not committed yet
    s.git("add", "-A")
    s.git("commit", "-qm", "draft O777", as_founder=True)
    assert cli(["objective", "review", "O777"]) == 0
    tasks = [t for t in Store().tasks("O777") if t.type == "review"]
    assert sorted(t.lens for t in tasks) == ["physics", "statistics"]
    assert all(t.target == "OBJ-O777" for t in tasks)
    o = Orchestrator(Store())
    assert o._blockers(tasks[0], []) == []  # a draft objective's own reviews may run
    claim, material = o._review_material(tasks[0], Store().root)
    assert "predictor that ignores the decision-relevant information" in claim and "E777.regret" in material
    for _ in range(40):  # the loop dispatches them (fake critic) and records the reviews
        o.tick()
        if len(list((Store().project / "reviews" / "OBJ-O777").glob("*.json"))) == 2:
            break
        time.sleep(0.3)
    capsys.readouterr()
    assert cli(["objective", "approve", "O777"]) == 0
    out = capsys.readouterr().out
    assert out.count("draft review T") == 2 and "accept" in out


def test_high_risk_merges_pass_the_full_gate_first(sandbox):
    pol = sandbox / ".mfos" / "policy.toml"
    pol.write_text(pol.read_text().replace("full = []", 'full = ["python3 -c \\"import sys; sys.exit(3)\\""]'))
    s = Store()
    o = Orchestrator(s)
    for tid, risk in (("T9980", "high"), ("T9981", "low")):
        t = m.Task(id=tid, objective="O000", title=f"{risk} change", type="implement", agent="builder",
                   status="merge", risk=risk, attempts=1)
        s.save_task(t)
        path = o.git.task_worktree(t)
        (path / f"{tid}.txt").write_text("x\n")
        o.git.commit_all(path, f"[{tid}] change")
        s.save_task(t)
        o._merge(s.task(tid))
    high, low = Store().task("T9980"), Store().task("T9981")
    assert high.history[-1]["outcome"] == "gate_failed" and "full gate fails before merge" in high.history[-1]["summary"]
    assert low.status == "done"  # low risk: the fast checks at verify suffice
