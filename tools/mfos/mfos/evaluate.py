"""Deterministic acceptance evaluation. No LLM is involved in any verdict.

Three-valued logic with uncertainty:
  * A pass criterion is SATISFIED only if the conservative end of the CI clears it
    (lower bound for >=/>, upper bound for <=/<).
  * A fail criterion is SATISFIED only if the result is definitely on the failing side
    (e.g. "rho < 0.80" requires the CI *upper* bound < 0.80).
  * Anything else is UNDETERMINED.

Overall verdict:
  INVALID       evidence is not admissible (dirty tree, spec drift, failed sanity check,
                missing result, missing required uncertainty). This is an *experimental*
                failure and says nothing about the hypothesis.
  FAIL          any fail criterion satisfied.
  PASS          every pass criterion satisfied.
  INCONCLUSIVE  otherwise.

Evidence rules v2 (evaluator 2.0.0; specs registered with ``evidence_rules: 2``) add admissibility checks computed
from git and the run registry, never from a runner's say-so: the run's commit is on main and contains the registered
spec; the lockfile, runner files and code under test at that commit match what the run recorded; artifacts exist with
their recorded hashes; the run was minted in experiments/registry.jsonl (with a verified seed commitment for sealed
specs); required objectives have passed; and code that must match another objective's validated code does. The first
complete registered run not consumed by an earlier evaluation is used; every other run is listed. Specs registered
before v2 are judged exactly as by evaluator 1.0.0.
"""
from __future__ import annotations

import hashlib
import json
import operator
import subprocess
from pathlib import Path
from typing import Callable, Optional

import yaml

from . import models as m
from .store import Store, file_sha256, now

EVALUATOR_VERSION = "2.0.0"

_OPS: dict[str, Callable[[float, float], bool]] = {
    ">=": operator.ge, ">": operator.gt, "<=": operator.le, "<": operator.lt,
}

# Admissibility checks that are about the run itself: a failure consumes the run (the next evaluation uses the next
# minted run, and the skip stays visible in the registry). `requires_passed` is about the world, not the run.
RUN_CHECKS = ("on_main", "spec_in_commit", "lockfile", "runner_files", "code_under_test", "artifacts", "registry",
              "code_must_match")


def _metric(results: dict[str, m.ExperimentResult], ref: str) -> Optional[m.MetricValue]:
    eid, _, name = ref.partition(".")
    res = results.get(eid)
    return res.metrics.get(name) if res else None


def judge(c: m.Criterion, mv: Optional[m.MetricValue], *, as_fail: bool) -> m.CriterionVerdict:
    base = dict(id=c.id, metric=c.metric, comparator=c.comparator, threshold=c.threshold)
    if mv is None:
        return m.CriterionVerdict(**base, verdict="missing")
    op = _OPS[c.comparator]
    if c.uncertainty.use == "point":
        ok = op(mv.value, c.threshold)
        return m.CriterionVerdict(**base, value=mv.value, bound_used=mv.value,
                                  verdict="satisfied" if ok else "not_satisfied")
    if mv.ci is None:
        return m.CriterionVerdict(**base, value=mv.value, verdict="missing")
    lo, hi = mv.ci
    greater = c.comparator in (">=", ">")
    # pass criteria use the pessimistic bound; fail criteria require certainty of failure
    if not as_fail:
        bound = lo if greater else hi
        sat = op(bound, c.threshold)
        other = hi if greater else lo
        verdict = "satisfied" if sat else ("not_satisfied" if not op(other, c.threshold) else "undetermined")
    else:
        bound = hi if not greater else lo  # e.g. "< t" -> need hi < t ; "> t" -> need lo > t
        sat = op(bound, c.threshold)
        verdict = "satisfied" if sat else "undetermined"
    return m.CriterionVerdict(**base, value=mv.value, bound_used=bound, verdict=verdict)


# ------------------------------------------------------------------------------------------------ git helpers
def _git_bytes(store: Store, *args: str) -> Optional[bytes]:
    r = subprocess.run(["git", *args], cwd=store.root, capture_output=True)
    return r.stdout if r.returncode == 0 else None


def _sha_at(store: Store, commit: str, path: str) -> Optional[str]:
    data = _git_bytes(store, "show", f"{commit}:{path}")
    return hashlib.sha256(data).hexdigest() if data is not None else None


def _main(store: Store) -> str:
    return store.policy.get("git", {}).get("main_branch", "main")


def run_dir(store: Store, res: m.ExperimentResult) -> Path:
    return store.root / "experiments" / "results" / res.experiment_id / res.run_id


def _evaluation(store: Store, oid: str, ev_id: str) -> Optional[m.Evaluation]:
    p = store.objective_dir(oid) / "evaluations" / f"{ev_id}.json"
    return m.Evaluation.model_validate_json(p.read_text()) if p.exists() else None


def _result(store: Store, eid: str, run_id: str) -> Optional[m.ExperimentResult]:
    p = store.root / "experiments" / "results" / eid / run_id / "result.json"
    if not p.exists():
        return None
    try:
        return m.ExperimentResult.model_validate_json(p.read_text())
    except Exception:
        return None


def validated_code(store: Store, oid: str) -> dict[str, str]:
    """Code hashes recorded in the results used by ``oid``'s last PASS evaluation (empty if it never passed)."""
    for ev_id in reversed(store.objective_state(oid).evaluations):
        ev = _evaluation(store, oid, ev_id)
        if ev is None or ev.verdict != "PASS":
            continue
        out: dict[str, str] = {}
        for eid, rid in ev.results_used.items():
            r = _result(store, eid, rid)
            if r is not None:
                out.update(r.provenance.code)
        return out
    return {}


# ------------------------------------------------------------------------------------------------ admissibility
def admissibility(store: Store, spec: m.ExperimentSpec, res: m.ExperimentResult) -> dict[str, str]:
    """Rules-v2 checks of one result, by name: "ok", "n/a: <why>", or the reason it fails."""
    from .experiments import commitment
    c: dict[str, str] = {}
    commit = res.provenance.git_commit
    main = _main(store)
    anc = subprocess.run(["git", "merge-base", "--is-ancestor", commit, main], cwd=store.root,
                         capture_output=True).returncode == 0
    c["on_main"] = "ok" if anc else f"commit {commit[:10]} is not an ancestor of {main}"

    raw = _git_bytes(store, "show", f"{commit}:experiments/specs/{spec.id}.yaml")
    if raw is None:
        c["spec_in_commit"] = f"spec absent from run commit {commit[:10]}"
    else:
        try:
            at = m.ExperimentSpec.model_validate(yaml.safe_load(raw) or {})
            c["spec_in_commit"] = "ok" if at.spec_hash == spec.spec_hash else \
                f"the spec in run commit {commit[:10]} has hash {at.spec_hash}, not the registered {spec.spec_hash}"
        except Exception as e:  # unparseable or a different schema
            c["spec_in_commit"] = f"the spec in run commit {commit[:10]} does not validate: {e}"

    lock_at = _sha_at(store, commit, "uv.lock")
    c["lockfile"] = "ok" if lock_at == res.provenance.lock_hash else \
        f"uv.lock at {commit[:10]} hashes to {lock_at}, the result records {res.provenance.lock_hash}"

    if not spec.runner_files:
        c["runner_files"] = "n/a: spec registered before runner freezing"
    else:
        bad = [f for f, h in spec.runner_files.items() if _sha_at(store, commit, f) != h]
        bad += [f"{f} (recorded at run time)" for f, h in res.provenance.runner_hashes.items()
                if spec.runner_files.get(f) != h]
        if spec.evidence_rules >= 2 and not res.provenance.runner_hashes:
            bad.append("no runner hashes recorded at run time")
        c["runner_files"] = "ok" if not bad else "runner files differ from the registration: " + ", ".join(bad)

    if not spec.code_under_test:
        c["code_under_test"] = "n/a: the spec declares no code_under_test"
    elif not res.provenance.code:
        c["code_under_test"] = "the result records no code hashes"
    else:
        bad = [f for f, h in res.provenance.code.items() if _sha_at(store, commit, f) != h]
        c["code_under_test"] = "ok" if not bad else \
            f"code at run commit {commit[:10]} differs from the recorded hashes: " + ", ".join(bad)

    rd = run_dir(store, res)
    bad = []
    for a in res.artifacts:
        p = rd / a.name
        if not p.exists():
            bad.append(f"{a.name} missing from the run directory")
        elif file_sha256(p) != a.sha256:
            bad.append(f"{a.name} sha256 changed")
    c["artifacts"] = "ok" if not bad else "; ".join(bad)

    if spec.evidence_rules < 2:
        c["registry"] = "n/a: legacy spec (registered before the run registry)"
    else:
        minted = [r for r in store.registry() if r.get("event") == "minted" and r.get("run_id") == res.run_id
                  and r.get("experiment") == spec.id]
        if not minted:
            c["registry"] = f"run {res.run_id} was not minted in experiments/registry.jsonl"
        elif minted[0].get("spec_hash") != spec.spec_hash:
            c["registry"] = f"run {res.run_id} was minted for spec hash {minted[0].get('spec_hash')}"
        elif spec.sealed_seed and (res.seed is None or minted[0].get("commitment") != commitment(res.run_id, res.seed)):
            c["registry"] = f"the seed recorded by {res.run_id} does not match its minted commitment"
        else:
            c["registry"] = "ok"

    if not spec.code_must_match:
        c["code_must_match"] = "n/a: the spec declares no code_must_match"
    else:
        bad = []
        for cm in spec.code_must_match:
            mine, theirs = res.provenance.code.get(cm.path), validated_code(store, cm.objective).get(cm.path)
            if mine is None or theirs is None or mine != theirs:
                bad.append(f"{cm.path}: this run {mine and mine[:12]}, validated by {cm.objective} "
                           f"{theirs and theirs[:12]}")
        c["code_must_match"] = "ok" if not bad else "; ".join(bad)

    unmet = [o for o in spec.requires_passed if store.objective_state(o).status != "passed"]
    c["requires_passed"] = ("ok" if not unmet else "waiting for " + ", ".join(f"{o} to pass" for o in unmet)) \
        if spec.requires_passed else "n/a: the spec requires no objective"
    return c


def failed(checks: dict[str, str], names=None) -> dict[str, str]:
    return {k: v for k, v in checks.items() if v != "ok" and not v.startswith("n/a") and (names is None or k in names)}


# ------------------------------------------------------------------------------------------------ run selection
def consumed_runs(store: Store, oid: str) -> set[str]:
    """Runs an earlier evaluation of ``oid`` used or listed, plus runs it rejected as inadmissible."""
    out: set[str] = set()
    for ev_id in store.objective_state(oid).evaluations:
        ev = _evaluation(store, oid, ev_id)
        if ev is not None:
            out |= set(ev.results_used.values())
            for runs in ev.unused_runs.values():
                out |= set(runs)
    for r in store.registry():
        if r.get("event") in ("consumed", "abandoned") and r.get("objective", oid) == oid:
            out.add(r.get("run_id", ""))
    return out


def _pick(store: Store, oid: str, spec: m.ExperimentSpec) -> tuple[Optional[m.ExperimentResult], list[str], str]:
    """(selected result or None, other runs to list, why none). v2: the first run minted for this spec hash that is
    not consumed; waits while that run has no finished result, so a later run can never overtake an earlier one."""
    done = {r.run_id: r for r in store.results(spec.id)}  # results with run.json (finalized)
    if spec.evidence_rules < 2:
        complete = [r for r in done.values() if r.status == "complete"]
        complete.sort(key=lambda r: r.run_id)
        return (complete[-1] if complete else None), [], "no complete result"
    used = consumed_runs(store, oid)
    minted = [r["run_id"] for r in store.registry() if r.get("event") == "minted" and r.get("experiment") == spec.id
              and r.get("spec_hash") == spec.spec_hash]
    chosen: Optional[m.ExperimentResult] = None
    why = "no complete registered result"
    for rid in minted:
        if rid in used:
            continue
        r = done.get(rid)
        if r is None:
            why = f"waiting for minted run {rid} to finish (or `mfos exp abandon {rid}`)"
            break
        if r.status == "complete":
            chosen = r
            break
    others = sorted(rid for rid, r in done.items()
                    if r.status == "complete" and rid not in used and (chosen is None or rid != chosen.run_id))
    return chosen, others, why


def selected_runs(store: Store, obj: m.Objective) -> Optional[dict[str, str]]:
    """{experiment: run id} that an evaluation would use now, or None while any required experiment has none."""
    out = {}
    for eid in obj.acceptance.required_experiments:
        if not store.spec_path(eid).exists():
            return None
        r, _, _ = _pick(store, obj.id, store.spec(eid))
        if r is None:
            return None
        out[eid] = r.run_id
    return out


def select_results(store: Store, obj: m.Objective) -> tuple[dict[str, m.ExperimentResult], list[str]]:
    chosen, problems, _, _ = _select(store, obj)
    return chosen, problems


def _select(store: Store, obj: m.Objective):
    chosen: dict[str, m.ExperimentResult] = {}
    problems: list[str] = []
    unused: dict[str, list[str]] = {}
    checks: dict[str, dict[str, str]] = {}
    for eid in obj.acceptance.required_experiments:
        spec_file = store.spec_path(eid)
        if not spec_file.exists():
            problems.append(f"{eid}: no registered spec")
            continue
        spec = store.spec(eid)
        if spec.status != "registered" or spec.spec_hash != store.spec_hash(spec):
            problems.append(f"{eid}: spec not registered or modified after registration")
            continue
        r, others, why = _pick(store, obj.id, spec)
        if others:
            unused[eid] = others
        if r is None:
            problems.append(f"{eid}: {why}")
            continue
        if r.provenance.git_dirty:
            problems.append(f"{eid}/{r.run_id}: produced from a dirty working tree")
        if r.provenance.spec_hash != spec.spec_hash:
            problems.append(f"{eid}/{r.run_id}: result spec_hash does not match registered spec")
        bad = [s.name for s in r.sanity if not s.passed]
        if bad:
            problems.append(f"{eid}/{r.run_id}: sanity checks failed: {', '.join(bad)}")
        missing = [x.name for x in spec.sanity_checks if x.name not in {s.name for s in r.sanity}]
        if missing:
            problems.append(f"{eid}/{r.run_id}: sanity checks not reported: {', '.join(missing)}")
        if spec.evidence_rules >= 2:
            checks[eid] = admissibility(store, spec, r)
            for name, why_bad in failed(checks[eid]).items():
                problems.append(f"{eid}/{r.run_id}: {name}: {why_bad}")
        chosen[eid] = r
    return chosen, problems, unused, checks


# ------------------------------------------------------------------------------------------------ evaluation
def evaluate(store: Store, oid: str, record: bool = True) -> m.Evaluation:
    obj = store.objective(oid)
    st = store.objective_state(oid)
    results, problems, unused, checks = _select(store, obj)
    if st.criteria_hash and st.criteria_hash != store.criteria_hash(obj):
        problems.append("acceptance criteria changed after approval (criteria_hash mismatch)")
    if st.frozen_hash and st.frozen_hash != store.frozen_hash(obj):
        problems.append("hypothesis, scope or evidence plan changed after approval (frozen_hash mismatch)")
    if len(st.evaluations) >= obj.acceptance.max_evaluations:
        problems.append(f"evaluation budget exhausted ({obj.acceptance.max_evaluations}); founder must decide")

    pass_checks = [judge(c, _metric(results, c.metric), as_fail=False) for c in obj.acceptance.pass_all]
    fail_checks = [judge(c, _metric(results, c.metric), as_fail=True) for c in obj.acceptance.fail_any]
    missing = [v.id for v in pass_checks + fail_checks if v.verdict == "missing"]
    if missing:
        problems.append("metrics missing or lacking required uncertainty: " + ", ".join(missing))

    if problems:
        verdict, why = "INVALID", "Evidence not admissible: " + "; ".join(problems)
    elif any(v.verdict == "satisfied" for v in fail_checks):
        hit = [v.id for v in fail_checks if v.verdict == "satisfied"]
        verdict, why = "FAIL", f"Kill criteria definitely met: {', '.join(hit)}"
    elif all(v.verdict == "satisfied" for v in pass_checks):
        verdict, why = "PASS", "All pass criteria met at the conservative bound"
    else:
        open_ = [v.id for v in pass_checks if v.verdict != "satisfied"]
        verdict, why = "INCONCLUSIVE", f"Pass criteria not established: {', '.join(open_)}"

    eid = f"EV-{oid}-{len(st.evaluations) + 1:02d}"
    ev = m.Evaluation(
        id=eid, objective=oid, timestamp=now(), criteria_hash=st.criteria_hash,
        evaluator_version=EVALUATOR_VERSION,
        results_used={k: v.run_id for k, v in results.items()},
        validity_problems=problems, pass_checks=pass_checks, fail_checks=fail_checks,
        verdict=verdict, explanation=why, unused_runs=unused, checks=checks,
    )
    if record and verdict != "INVALID":
        store.write_json(store.objective_dir(oid) / "evaluations" / f"{eid}.json", ev)
        st.evaluations.append(eid)
        st.last_verdict = verdict
        store.save_objective_state(oid, st)
        store.event("evaluation", objective=oid, id=eid, verdict=verdict)
    elif record:
        store.write_json(store.objective_dir(oid) / "evaluations" / f"{eid}-invalid.json", ev)
        store.event("evaluation_invalid", objective=oid, problems=problems)
        # A run that fails a check about itself is consumed, visibly: the next evaluation uses the next minted run.
        for x, res in results.items():
            bad = failed(checks.get(x, {}), RUN_CHECKS)
            if bad:
                store.registry_append(event="consumed", objective=oid, experiment=x, run_id=res.run_id,
                                      evaluation=f"{eid}-invalid", reason="; ".join(f"{k}: {v}" for k, v in bad.items()))
    return ev


# ------------------------------------------------------------------------------------------------ audit
def audit_evidence(store: Store, oid: str) -> list[tuple[str, str, str, str]]:
    """Apply the v2 checks to the runs used by ``oid``'s recorded evaluations, whatever rules they were judged by.
    Read-only. Returns rows (evaluation, experiment/run, check, outcome)."""
    rows = []
    for ev_id in store.objective_state(oid).evaluations:
        ev = _evaluation(store, oid, ev_id)
        if ev is None:
            continue
        for eid, rid in ev.results_used.items():
            res = _result(store, eid, rid)
            if res is None or not store.spec_path(eid).exists():
                rows.append((ev_id, f"{eid}/{rid}", "result", "missing"))
                continue
            for name, outcome in admissibility(store, store.spec(eid), res).items():
                rows.append((ev_id, f"{eid}/{rid}", name, outcome))
    return rows


def audit_json(store: Store, oid: str) -> str:
    return json.dumps([dict(zip(("evaluation", "run", "check", "outcome"), r, strict=True)) for r in audit_evidence(store, oid)],
                      indent=2)
