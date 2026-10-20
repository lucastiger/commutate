"""The recorded verdicts of the live repository must reproduce under the current evaluator, and every frozen hash
must still verify. Read-only: nothing here writes to the repository (evaluate(..., record=False))."""
import json
from pathlib import Path

import pytest

from mfos import evaluate
from mfos.store import Store

REPO = Path(__file__).resolve().parents[2]


@pytest.fixture
def live(monkeypatch):
    monkeypatch.delenv("MFOS_ROOT", raising=False)
    return Store(REPO)


@pytest.mark.parametrize("oid, ev_id", [("O000", "EV-O000-01"), ("O001", "EV-O001-01")])
def test_recorded_verdicts_reproduce(live, oid, ev_id):
    recorded = json.loads((live.objective_dir(oid) / "evaluations" / f"{ev_id}.json").read_text())
    ev = evaluate.evaluate(live, oid, record=False)
    assert ev.verdict == recorded["verdict"] == "PASS", ev.validity_problems
    assert ev.results_used == recorded["results_used"]
    for mine, theirs in zip(ev.pass_checks + ev.fail_checks, recorded["pass_checks"] + recorded["fail_checks"],
                            strict=True):
        assert (mine.id, mine.verdict, mine.value, mine.bound_used) == \
            (theirs["id"], theirs["verdict"], theirs["value"], theirs["bound_used"])


def test_every_frozen_hash_still_verifies(live):
    for oid in live.objective_ids():
        st = live.objective_state(oid)
        if st.criteria_hash:
            assert st.criteria_hash == live.criteria_hash(live.objective(oid)), oid
        if st.frozen_hash:
            assert st.frozen_hash == live.frozen_hash(live.objective(oid)), oid
    for p in sorted((live.root / "experiments" / "specs").glob("*.yaml")):
        spec = live.spec(p.stem)
        if spec.status == "registered":
            assert spec.spec_hash == live.spec_hash(spec), spec.id
