"""Seeded-failure suite (audit 2026-10-19, metric IV.3 "false-pass rate"): evidence that must never PASS.

Each scenario seeds one defect into an otherwise clean evidence-rules-v2 experiment and checks the verdict. Together
with the admissibility scenarios in test_evidence_integrity.py it is the regression net for the evaluator.
Scenarios here: 9 (2 controls, 7 seeded defects).
"""
import json
import textwrap

import pytest
import yaml

from mfos import evaluate, experiments
from mfos import metrics as mx
from mfos.cli import main as cli
from mfos.store import Store

RUNNER = '''\
"""E900: synthetic ranking experiment for the seeded-failure suite."""
import os

import numpy as np

from mfos import metrics as mx
from mfos.evidence import ExperimentRun

mode = os.environ.get("SEEDED_MODE", "good")
rng = np.random.default_rng(1)
# good: strata overlap, so knowing a row's stratum is not enough to rank it; strata_only: strata dominate
means, spread, noise = ((10, 12, 14), 0.25, 0.01) if mode == "good" else ((10, 20, 40), 0.01, 0.02)
rows = []
for fam, mu in zip("abc", means):
    for _ in range(20):
        ref = mu * (1 + spread * rng.uniform(-1, 1))
        rows.append({"family": fam, "ref": float(ref), "pred": float(ref * (1 + noise * rng.normal()))})
with ExperimentRun() as run:
    run.sanity("rows_written", passed=True)
    run.rows(rows)
    pred, ref = [r["pred"] for r in rows], [r["ref"] for r in rows]
    scheme = os.environ.get("SEEDED_CI_SCHEME", "plain")
    point, ci = mx.bootstrap_ci(lambda rr: mx.spearman([r["pred"] for r in rr], [r["ref"] for r in rr]), rows,
                                n_boot=200, seed=7, scheme=scheme, strata=["family"])
    if os.environ.get("SEEDED_MISREPORT") == "1":
        point += 0.05
    run.metric("spearman_rho", point, ci=ci, n=len(rows))
    if os.environ.get("SEEDED_DROP_WITHIN") != "1":
        run.metric("within_rho", mx.within_strata_spearman(pred, ref, [r["family"] for r in rows]), n=len(rows))
'''

OBJECTIVE = """\
id: O900
title: Seeded-failure harness
kind: hypothesis
priority: 1
risk: low
hypothesis:
  statement: pred ranks rows like ref, within families too
  decision_if_inconclusive: diagnose the design
evidence_plan: [E900]
acceptance:
  required_experiments: [E900]
  pass_all:
    - {id: A1, metric: E900.spearman_rho, comparator: ">=", threshold: 0.9, uncertainty: {use: ci}}
    - {id: A2, metric: E900.within_rho, comparator: ">=", threshold: 0.5, uncertainty: {use: point}}
  fail_any:
    - {id: K1, metric: E900.spearman_rho, comparator: "<", threshold: 0.5, uncertainty: {use: ci}}
  max_evaluations: 3
require_plan_approval: false
"""


def spec(**extra):
    d = {
        "id": "E900", "title": "seeded", "objective": "O900", "runner": "python3 experiments/runners/e900_seeded.py",
        "metrics": [{"name": "spearman_rho"}, {"name": "within_rho"}],
        "sanity_checks": [{"name": "rows_written"}],
        "rows": {"artifact": "rows.json"},
        "recompute": [
            {"metric": "spearman_rho", "fn": "spearman", "pred": "pred", "ref": "ref",
             "ci": {"scheme": "plain", "n_boot": 200, "seed": 7}},
            {"metric": "within_rho", "fn": "within_strata_spearman", "pred": "pred", "ref": "ref",
             "strata": ["family"]},
        ],
        "null_baselines": [{"name": "family_mean", "kind": "stratum_mean", "strata": ["family"],
                            "applies_to": ["spearman_rho"]}],
    }
    d.update(extra)
    return d


def setup(sandbox, monkeypatch, *, objective=OBJECTIVE, approve=True, register=True, **spec_extra):
    (sandbox / "experiments" / "runners" / "e900_seeded.py").write_text(RUNNER)
    d = sandbox / "project" / "objectives" / "O900"
    d.mkdir(parents=True, exist_ok=True)
    text = objective if _has_field() else objective.replace("  decision_if_inconclusive: diagnose the design\n", "")
    (d / "objective.yaml").write_text(text)
    (sandbox / "experiments" / "drafts" / "E900.yaml").write_text(yaml.safe_dump(spec(**spec_extra), sort_keys=False))
    s = Store()
    s.git("add", "-A")
    s.git("commit", "-qm", "E900 harness", as_founder=True)
    if register:
        experiments.register(Store(), "E900")
    if approve:
        assert cli(["objective", "approve", "O900"]) == 0
    s.git("add", "-A")
    s.git("commit", "-qm", "register E900", as_founder=True)
    return Store()


def _has_field():
    from mfos import models as m
    return "decision_if_inconclusive" in m.Hypothesis.model_fields


def run_and_evaluate():
    res = experiments.run(Store(), "E900", force=True)
    assert res.status == "complete", res.notes
    return res, evaluate.evaluate(Store(), "O900", record=False)


def verdict_of(ev, cid):
    return next(v for v in ev.pass_checks + ev.fail_checks if v.id == cid)


def test_control_clean_evidence_passes_with_a_null_that_fails(sandbox, monkeypatch):
    setup(sandbox, monkeypatch)
    _, ev = run_and_evaluate()
    assert ev.verdict == "PASS", ev.validity_problems
    a1 = verdict_of(ev, "A1")
    assert a1.recomputed and a1.runner_value == pytest.approx(a1.value, abs=1e-12)
    assert a1.null_value is not None and a1.null_bound < 0.9  # the family-mean predictor does not meet A1


def test_a_misreported_metric_is_invalid(sandbox, monkeypatch):
    setup(sandbox, monkeypatch)
    monkeypatch.setenv("SEEDED_MISREPORT", "1")
    _, ev = run_and_evaluate()
    assert ev.verdict == "INVALID"
    assert any("E900.spearman_rho: runner reported" in p for p in ev.validity_problems), ev.validity_problems


def test_a_criterion_a_null_also_meets_is_non_discriminating(sandbox, monkeypatch):
    """O001's A2/A3: a predictor that knew only each stratum's mean L2 scored rho = 0.975 and met them."""
    setup(sandbox, monkeypatch)
    monkeypatch.setenv("SEEDED_MODE", "strata_only")
    _, ev = run_and_evaluate()
    assert ev.verdict == "INCONCLUSIVE", ev.validity_problems
    a1 = verdict_of(ev, "A1")
    assert a1.verdict == "non_discriminating" and a1.null_bound >= 0.9
    assert "A1 (non-discriminating" in ev.explanation


def test_rows_edited_after_the_run_are_inadmissible(sandbox, monkeypatch):
    setup(sandbox, monkeypatch)
    res, ev = run_and_evaluate()
    assert ev.verdict == "PASS"
    rows_file = Store().root / "experiments" / "results" / "E900" / res.run_id / "rows.json"
    data = json.loads(rows_file.read_text())
    data["rows"][0]["pred"] *= 2
    rows_file.write_text(json.dumps(data))
    ev = evaluate.evaluate(Store(), "O900", record=False)
    assert ev.verdict == "INVALID" and any("artifacts" in p for p in ev.validity_problems)


def test_a_criterion_metric_without_recompute_or_exemption_is_invalid(sandbox, monkeypatch):
    setup(sandbox, monkeypatch, recompute=spec()["recompute"][:1])  # within_rho no longer recomputed
    _, ev = run_and_evaluate()
    assert ev.verdict == "INVALID"
    assert any("E900.within_rho (criterion A2): no recompute entry" in p for p in ev.validity_problems)


def test_an_exemption_with_a_reason_is_accepted(sandbox, monkeypatch):
    setup(sandbox, monkeypatch, recompute=spec()["recompute"][:1],
          recompute_exempt={"within_rho": "computed from per-layout ladders not in the rows (example)"})
    _, ev = run_and_evaluate()
    assert ev.verdict == "PASS", ev.validity_problems
    assert verdict_of(ev, "A2").recomputed is None


def test_the_evaluator_uses_its_own_ci_not_the_runners(sandbox, monkeypatch):
    setup(sandbox, monkeypatch)
    monkeypatch.setenv("SEEDED_CI_SCHEME", "stratified")  # the runner reports a different (narrower) interval
    res, ev = run_and_evaluate()
    rows = json.loads((Store().root / "experiments" / "results" / "E900" / res.run_id / "rows.json").read_text())["rows"]
    _, (lo, _) = mx.bootstrap_ci(lambda rr: mx.compute("spearman", rr, pred="pred", ref="ref"), rows, n_boot=200, seed=7)
    assert verdict_of(ev, "A1").bound_used == pytest.approx(lo, abs=1e-12)
    assert verdict_of(ev, "A1").bound_used != pytest.approx(res.metrics["spearman_rho"].ci[0], abs=1e-12)


def test_a_metric_the_runner_did_not_report_is_invalid(sandbox, monkeypatch):
    setup(sandbox, monkeypatch)
    monkeypatch.setenv("SEEDED_DROP_WITHIN", "1")
    _, ev = run_and_evaluate()
    assert ev.verdict == "INVALID"
    assert any("E900.within_rho: the runner did not report" in p for p in ev.validity_problems)


def test_registration_refuses_a_non_discriminating_design_unless_overridden_with_a_reason(sandbox, monkeypatch):
    # dev rows dominated by strata, as a dev-seed run of a badly designed sample would produce
    import numpy as np
    rng = np.random.default_rng(3)
    rows = []
    for fam, mu in zip("abc", (10, 20, 40), strict=True):
        for _ in range(10):
            ref = mu * (1 + 0.01 * rng.uniform(-1, 1))
            rows.append({"family": fam, "ref": ref, "pred": ref * (1 + 0.02 * rng.normal())})
    dev = sandbox / "experiments" / "drafts" / "E900_dev_rows.json"
    dev.parent.mkdir(parents=True, exist_ok=True)
    dev.write_text(json.dumps({"schema": "mfos.rows/1", "rows": rows}))
    setup(sandbox, monkeypatch, register=False, dev_rows="experiments/drafts/E900_dev_rows.json")
    assert cli(["exp", "check", "E900", "--rows", str(dev)]) == 1
    with pytest.raises(RuntimeError, match="also met by a declared null predictor"):
        experiments.register(Store(), "E900")
    assert cli(["exp", "register", "E900", "--override-null", "pilot: strata are the point"]) == 0
    override = [r for r in Store().registry() if r["event"] == "null_override"]
    assert override and override[0]["reason"] == "pilot: strata are the point" and override[0]["criteria"] == ["A1"]


def test_the_suite_header_counts_its_scenarios():
    import inspect
    import sys
    mod = sys.modules[__name__]
    n = len([f for name, f in inspect.getmembers(mod, inspect.isfunction)
             if name.startswith("test_") and name != "test_the_suite_header_counts_its_scenarios"])
    assert f"Scenarios here: {n} " in textwrap.dedent(mod.__doc__), n
