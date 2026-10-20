"""Evidence rules v2 (evaluator 2.0.0, audit 2026-10-19): admissibility is decided from git and the run registry,
never from what a runner reports. Each seeded failure below must make the evaluation INVALID and name its check."""
import hashlib
import json
import os
import time

import pytest
import yaml

from mfos import evaluate, experiments
from mfos import models as m
from mfos.cli import main as cli
from mfos.loop import Orchestrator
from mfos.store import Store

CANARY = "import math\n\n\ndef harmonic(n: int) -> float:\n    return math.fsum(1.0 / k for k in range(1, n + 1))\n"
CODE = "src/moduleforge/canary.py"
RUNNER = "experiments/runners/e000_canary.py"


def commit_all(s, msg):
    s.git("add", "-A")
    s.git("commit", "-qm", msg, as_founder=True)


def prepare(sandbox, **spec_fields):
    """The canary implemented, E000 registered under rules v2 (with extra spec fields), O000 approved, all committed."""
    (sandbox / CODE).write_text(CANARY)
    draft = sandbox / "experiments" / "drafts" / "E000.yaml"
    spec = yaml.safe_load(draft.read_text())
    spec.update(spec_fields)
    draft.write_text(yaml.safe_dump(spec, sort_keys=False))
    s = Store()
    assert experiments.register(s, "E000").evidence_rules == 2
    assert cli(["objective", "approve", "O000"]) == 0
    commit_all(s, "register E000; implement the canary")
    return Store()


def result_file(s, run_id):
    return s.root / "experiments" / "results" / "E000" / run_id / "result.json"


def edit_result(s, run_id, fn):
    p = result_file(s, run_id)
    d = json.loads(p.read_text())
    fn(d)
    p.write_text(json.dumps(d))


def evaluation():
    return evaluate.evaluate(Store(), "O000", record=False)


def assert_invalid(ev, check):
    assert ev.verdict == "INVALID", ev
    assert any(f": {check}: " in p or p.endswith(f": {check}") or f"{check} " in p for p in ev.validity_problems), \
        ev.validity_problems


def test_clean_v2_evidence_passes_and_records_its_checks(sandbox):
    s = prepare(sandbox, code_under_test=[CODE])
    res = experiments.run(s, "E000", force=True)
    assert res.status == "complete"
    assert res.provenance.runner_hashes == {RUNNER: hashlib.sha256((sandbox / RUNNER).read_bytes()).hexdigest()}
    assert res.provenance.code == {CODE: hashlib.sha256(CANARY.encode()).hexdigest()}
    minted = [r for r in Store().registry() if r["event"] == "minted"]
    assert [r["run_id"] for r in minted] == [res.run_id]
    ev = evaluation()
    assert ev.verdict == "PASS", ev.validity_problems
    assert ev.evaluator_version == "2.0.0"
    assert ev.checks["E000"]["on_main"] == "ok" and ev.checks["E000"]["code_under_test"] == "ok"
    assert all(v == "ok" or v.startswith("n/a") for v in ev.checks["E000"].values()), ev.checks


@pytest.mark.parametrize("check, tamper", [
    ("lockfile", lambda d: d["provenance"].update(lock_hash="0" * 64)),
    ("runner_files", lambda d: d["provenance"].update(runner_hashes={RUNNER: "0" * 64})),
    ("code_under_test", lambda d: d["provenance"].update(code={CODE: "0" * 64})),
    ("artifacts", lambda d: d.update(artifacts=[{"name": "rows.json", "sha256": "0" * 64, "bytes": 1}])),
])
def test_tampered_provenance_is_inadmissible(sandbox, check, tamper):
    s = prepare(sandbox, code_under_test=[CODE])
    res = experiments.run(s, "E000", force=True)
    edit_result(s, res.run_id, tamper)
    assert_invalid(evaluation(), check)


def test_an_artifact_edited_after_the_run_is_inadmissible(sandbox):
    s = prepare(sandbox)
    res = experiments.run(s, "E000", force=True)
    rows = result_file(s, res.run_id).parent / "rows.json"
    rows.write_text('{"rows": [1]}')
    digest = hashlib.sha256(b'{"rows": [1]}').hexdigest()
    edit_result(s, res.run_id, lambda d: d.update(artifacts=[{"name": "rows.json", "sha256": digest, "bytes": 13}]))
    assert evaluation().verdict == "PASS"
    rows.write_text('{"rows": [2]}')
    ev = evaluation()
    assert_invalid(ev, "artifacts")
    assert "sha256 changed" in ev.checks["E000"]["artifacts"]


def test_a_result_from_a_commit_not_on_main_is_inadmissible(sandbox):
    s = prepare(sandbox)
    s.git("checkout", "-qb", "side")
    (sandbox / "side.txt").write_text("not on main\n")
    commit_all(s, "a commit that never reaches main")
    s.git("checkout", "-q", "main")
    experiments.run(s, "E000", ref="side", force=True)
    assert_invalid(evaluation(), "on_main")


def test_a_result_whose_commit_lacks_the_registered_spec_is_inadmissible(sandbox):
    """E003 (2026-10-11) ran on commit 4c8cf3e, which did not contain experiments/specs/E003.yaml."""
    s = prepare(sandbox)
    res = experiments.run(s, "E000", force=True)
    first = s.git("rev-list", "--max-parents=0", "HEAD")
    edit_result(s, res.run_id, lambda d: d["provenance"].update(git_commit=first))
    ev = evaluation()
    assert_invalid(ev, "spec_in_commit")
    assert "spec absent from run commit" in ev.checks["E000"]["spec_in_commit"]


def test_run_refuses_while_the_registration_is_uncommitted(sandbox):
    (sandbox / CODE).write_text(CANARY)
    commit_all(Store(), "canary")
    experiments.register(Store(), "E000")  # registered in the working tree only
    with pytest.raises(RuntimeError, match="not committed"):
        experiments.run(Store(), "E000", force=True)


def test_an_unregistered_run_is_inadmissible(sandbox):
    s = prepare(sandbox)
    experiments.run(s, "E000", force=True, run_id="E000-20990101T000000-beef")  # never minted
    ev = evaluation()
    assert ev.verdict == "INVALID"
    assert any("no complete registered result" in p for p in ev.validity_problems), ev.validity_problems


def test_a_seed_that_does_not_match_its_commitment_is_inadmissible(sandbox):
    s = prepare(sandbox, sealed_seed=True)
    res = experiments.run(s, "E000", force=True)
    seed_file = experiments.sealed_seed_path(s, res.run_id)
    assert seed_file.exists() and (os.stat(seed_file).st_mode & 0o777) == 0o600
    minted = next(r for r in s.registry() if r["run_id"] == res.run_id)
    assert minted["commitment"] == experiments.commitment(res.run_id, res.seed)
    assert evaluation().verdict == "PASS"
    edit_result(s, res.run_id, lambda d: d.update(seed=res.seed + 1))
    assert_invalid(evaluation(), "registry")


def test_requires_passed_blocks_dispatch_and_evaluation(sandbox):
    s = prepare(sandbox, requires_passed=["O777"])
    experiments.run(s, "E000", force=True)
    assert_invalid(evaluation(), "requires_passed")
    t = m.Task(id="T9500", objective="O000", title="run E000", type="experiment", agent="none", experiment="E000")
    assert "waiting for O777 to pass" in Orchestrator(Store())._blockers(t, [])


def test_code_must_match_binds_a_judge_to_the_validated_code(sandbox):
    """O001: A1 validated solvers.l2 while E002 was judged by solvers.l2_layout. code_must_match makes that a check."""
    s = prepare(sandbox, code_under_test=[CODE], code_must_match=[{"path": CODE, "objective": "O777"}])
    res = experiments.run(s, "E000", force=True)
    assert_invalid(evaluation(), "code_must_match")  # O777 never validated anything
    # O777 passed on evidence whose code is this very file: now the binding holds
    st = m.ObjectiveState(status="passed", evaluations=["EV-O777-01"])
    s.save_objective_state("O777", st)
    ev777 = m.Evaluation(id="EV-O777-01", objective="O777", timestamp="t", criteria_hash=None, evaluator_version="2.0.0",
                         results_used={"E000": res.run_id}, validity_problems=[], pass_checks=[], fail_checks=[],
                         verdict="PASS", explanation="")
    s.write_json(s.objective_dir("O777") / "evaluations" / "EV-O777-01.json", ev777)
    assert evaluation().checks["E000"]["code_must_match"] == "ok"


def test_editing_the_hypothesis_after_approval_is_detected(sandbox):
    s = prepare(sandbox)
    experiments.run(s, "E000", force=True)
    p = s.objective_dir("O000") / "objective.yaml"
    p.write_text(p.read_text().replace("moduleforge.canary.harmonic(n) returns", "moduleforge.canary.harmonic(n) gives"))
    assert cli(["doctor", "--ci"]) == 1
    ev = evaluation()
    assert ev.verdict == "INVALID" and any("frozen_hash" in x for x in ev.validity_problems)


def test_the_first_minted_run_counts_and_later_ones_are_listed(sandbox):
    s = prepare(sandbox)
    first = experiments.run(s, "E000", force=True)
    second = experiments.run(Store(), "E000", force=True)
    ev = evaluate.evaluate(Store(), "O000")
    assert ev.verdict == "PASS"
    assert ev.results_used == {"E000": first.run_id}
    assert ev.unused_runs == {"E000": [second.run_id]}


def test_an_inadmissible_first_run_is_consumed_visibly(sandbox):
    s = prepare(sandbox)
    first = experiments.run(s, "E000", force=True)
    second = experiments.run(Store(), "E000", force=True)
    edit_result(s, first.run_id, lambda d: d["provenance"].update(lock_hash="0" * 64))
    ev = evaluate.evaluate(Store(), "O000")
    assert ev.verdict == "INVALID" and ev.results_used == {"E000": first.run_id}
    consumed = [r for r in Store().registry() if r["event"] == "consumed"]
    assert [r["run_id"] for r in consumed] == [first.run_id] and "lockfile" in consumed[0]["reason"]
    ev = evaluate.evaluate(Store(), "O000")
    assert ev.verdict == "PASS" and ev.results_used == {"E000": second.run_id}


def test_a_later_run_never_overtakes_an_earlier_minted_one(sandbox):
    s = prepare(sandbox)
    pending, _ = experiments.mint(s, "E000")  # minted (e.g. for a burst VM) but no result yet
    later = experiments.run(Store(), "E000", force=True)
    assert evaluate.selected_runs(Store(), Store().objective("O000")) is None
    ev = evaluation()
    assert ev.verdict == "INVALID" and any(f"waiting for minted run {pending}" in p for p in ev.validity_problems)
    assert cli(["exp", "abandon", "E000", "--run-id", pending, "--reason", "the VM died"]) == 0
    assert evaluate.selected_runs(Store(), Store().objective("O000")) == {"E000": later.run_id}
    assert evaluation().verdict == "PASS"


def test_the_burst_path_runs_a_run_minted_elsewhere_without_touching_the_registry(sandbox):
    s = prepare(sandbox, sealed_seed=True)
    run_id, seed_file = experiments.mint(s, "E000")
    seed = int(seed_file.read_text())
    n = len(Store().registry())
    res = experiments.run(Store(), "E000", force=True, run_id=run_id, seed_file=seed_file)
    assert res.run_id == run_id and res.seed == seed
    assert len(Store().registry()) == n
    assert evaluation().verdict == "PASS"


def test_a_legacy_spec_is_judged_exactly_as_before(sandbox):
    """Specs registered before evidence rules v2 (E000-E003) keep evaluator 1.0.0 behaviour: no registry, latest run."""
    (sandbox / CODE).write_text(CANARY)
    s = Store()
    spec = experiments.register(s, "E000")
    spec.evidence_rules = 1
    spec.spec_hash = s.spec_hash(spec)
    s.write_yaml(s.spec_path("E000"), spec)
    assert cli(["objective", "approve", "O000"]) == 0
    commit_all(s, "legacy registration")
    experiments.run(Store(), "E000", force=True)
    time.sleep(1.1)  # legacy run ids order by their second-resolution timestamp
    last = experiments.run(Store(), "E000", force=True)
    assert not Store().registry_path.exists()
    ev = evaluation()
    assert ev.verdict == "PASS" and ev.results_used == {"E000": last.run_id}
    assert ev.checks == {} and ev.unused_runs == {}
