"""mfos — the ModuleForge operating system CLI.

Founder commands:  status, inbox, approve, reject, answer, objective, loop, stop, start, costs, report
Agent/CI commands: gate, exp check, doctor
Level-1 trigger:   task start (start one task; the running loop finishes it)
Migration helpers: packet (render a task packet to paste into Claude Code), run (one task, synchronously,
                   only while no loop runs)
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import shutil
import sys
import time
from pathlib import Path

import yaml

from . import evaluate, experiments, gates, human, models as m, packets, report
from .store import Store, now


def _store() -> Store:
    return Store()


# ------------------------------------------------------------------ objectives
def cmd_objective(a: argparse.Namespace) -> int:
    s = _store()
    if a.action == "new":
        d = s.objective_dir(a.id)
        if d.exists():
            print(f"{a.id} already exists", file=sys.stderr)
            return 1
        d.mkdir(parents=True)
        tpl = (s.root / "templates" / "objective.yaml").read_text().replace("OXXX", a.id)
        (d / "objective.yaml").write_text(tpl)
        s.save_objective_state(a.id, m.ObjectiveState(status="draft"))
        print(f"created {d/'objective.yaml'} — edit it, then: mfos objective approve {a.id}")
        return 0
    if a.action == "approve":
        s.objective(a.id)  # validates schema before asking anyone to confirm
        _print_draft_reviews(s, a.id)
        if not human.confirm(f"objective approve {a.id}", a.id):
            return 2
        return _approve_objective(s, a.id)
    if a.action == "show":
        print(yaml.safe_dump(s.objective(a.id).model_dump(mode="json"), sort_keys=False))
        print(yaml.safe_dump(s.objective_state(a.id).model_dump(mode="json"), sort_keys=False))
        return 0
    return _objective_other(s, a)


def _print_draft_reviews(s: Store, oid: str) -> None:
    """The objective-draft reviews inform the approval; they do not gate it."""
    d = s.project / "reviews" / f"OBJ-{oid}"
    reviews = sorted(d.glob("*.json")) if d.exists() else []
    if not reviews:
        print(f"No draft review of {oid} on record (`uv run mfos objective review {oid}` runs one).")
    for p in reviews:
        rv = m.Review.model_validate_json(p.read_text())
        print(f"draft review {p.stem}: {rv.verdict}")
        for f in rv.findings:
            if f.severity in ("blocker", "major"):
                print(f"  [{f.severity}, {f.impact}] {f.title}")


def _approve_objective(s: Store, oid: str) -> int:
    """Freeze an objective (a founder act: callers confirm at a terminal first)."""
    obj = s.objective(oid)  # validates schema
    st = s.objective_state(oid)
    st.status, st.approved_by, st.approved_at = "active", "founder", now()
    st.criteria_hash = s.criteria_hash(obj)
    st.frozen_hash = s.frozen_hash(obj)
    st.evidence_rules = max(st.evidence_rules, experiments.EVIDENCE_RULES)
    st.needs_replan = True
    s.save_objective_state(oid, st)
    s.event("objective_approved", actor="founder", objective=oid, criteria_hash=st.criteria_hash)
    d = s.objective_dir(oid).relative_to(s.root)
    s.git("add", "--", str(d / "objective.yaml"), str(d / "state.yaml"), check=False)
    s.git("commit", "-q", "-m", f"Approve {oid}: freeze hypothesis and acceptance criteria",
          "-m", f"criteria_hash: {st.criteria_hash}", check=False, as_founder=True)
    print(f"{oid} approved and frozen ({st.criteria_hash[:19]}…)")
    return 0


def _objective_other(s: Store, a: argparse.Namespace) -> int:
    if a.action == "pause":
        st = s.objective_state(a.id)
        st.status = "needs_founder"
        s.save_objective_state(a.id, st)
        return 0
    if a.action == "review":  # founder: adversarial review of a draft before approval (audit 2026-10-19)
        from .loop import Orchestrator
        try:
            made = Orchestrator(s).review_objective_draft(a.id)
        except ValueError as e:
            print(e, file=sys.stderr)
            return 1
        print(f"{a.id}: draft review tasks {', '.join(made)}; the loop dispatches them; results in "
              f"project/reviews/OBJ-{a.id}/")
        return 0
    if a.action == "rereview":  # founder: the blinded review of a PASS ran on a stale or wrong snapshot
        from .loop import Orchestrator
        try:
            ev_id, ref, n = Orchestrator(s).rereview_evaluation(a.id)
        except ValueError as e:
            print(e, file=sys.stderr)
            return 1
        print(f"{a.id}: {n} critics re-review {ev_id} at {ref[:10]}; the loop dispatches them")
        return 0
    if a.action == "resume":
        st = s.objective_state(a.id)
        st.status = "active"
        s.save_objective_state(a.id, st)
        return 0
    return 1


# ------------------------------------------------------------------ inbox
def _resolve(s: Store, iid: str, status: str, note: str, replan: bool = True) -> int:
    p = s.project / "inbox" / f"{iid}.yaml"
    item = s.read_yaml(p, m.InboxItem)
    if item.status != "open":
        print(f"{iid} is already {item.status}")
        return 1
    gated = item.kind in human.GATED_KINDS and status in ("approved", "rejected")
    if gated and not human.confirm(f"{'approve' if status == 'approved' else 'reject'} {iid}", iid):
        return 2
    item.status, item.response, item.resolved_at = status, note, now()
    item.resolved_by = "human" if gated else human.resolver()
    approved = status == "approved"
    if item.kind == "objective_approval" and approved:
        _approve_objective(s, item.refs[0])
    elif item.kind == "claim_approval" and approved:
        rc = _approve_claim(s, item.refs[0], statement=None, scope=None)
        if rc:
            return rc
    elif item.kind == "plan_approval":
        oid, tids = item.refs[0], item.refs[1:]
        for tid in tids:
            t = s.task(tid)
            if t.status == "proposed":
                t.status = "todo" if approved else "cancelled"
                s.save_task(t)
        if not approved:
            st = s.objective_state(oid)
            st.needs_replan = True
            st.log.append(f"founder rejected plan: {note}")
            s.save_objective_state(oid, st)
    elif item.kind == "experiment_registration" and approved:
        experiments.register(s, item.refs[0], by="founder")
    elif item.kind == "protected_change" and approved:
        t = s.task(item.refs[0])
        t.protected_approved = True
        t.approval = iid
        t.status = "merge"
        s.save_task(t)
    elif item.kind == "infrastructure" and status in ("approved", "answered"):
        for ref in item.refs:  # the cause is fixed: every task it parked goes back to todo
            if s.task_path(ref).exists():
                t = s.task(ref)
                if t.status == "needs_founder":
                    t.status = "todo"
                    t.history.append({"outcome": "infrastructure_resolved", "summary": f"{iid}: {note}", "at": now()})
                    s.save_task(t)
    elif item.kind == "budget_increase" and approved:
        for ref in item.refs:
            if ref.startswith("O"):
                st = s.objective_state(ref)
                extra = float(note.split("=", 1)[1]) if note.startswith("usd=") else 25.0
                st.budget_override_usd = st.spent_usd + extra
                st.status = "active"
                s.save_objective_state(ref, st)
        (s.mfos / "budget_notice").unlink(missing_ok=True)
    elif item.kind in ("decision", "question", "thesis_change", "criteria_change", "model_escalation"):
        for ref in item.refs:
            if ref.startswith("O") and (s.objective_dir(ref) / "objective.yaml").exists():
                st = s.objective_state(ref)
                st.log.append(f"founder {status} {iid}: {note}" + ("" if replan else " (no replan)"))
                # --no-replan: the founder resolves the decision and declines a replan. Without it, past the replan
                # limit every answered decision re-parked the objective with a new "replan limit reached" item, so it
                # could not be reactivated through the inbox at all (O001, 2026-10-07).
                st.needs_replan = replan
                if st.status == "needs_founder" and (approved or not replan):
                    st.status = "active"
                s.save_objective_state(ref, st)
    s.save_inbox(item)
    s.event("inbox_resolved", actor="founder", id=iid, status=status, note=note, by=item.resolved_by)
    print(f"{iid} {status}")
    return 0


# ------------------------------------------------------------------ claims
def _claim_path(s: Store, cid: str) -> Path:
    return s.project / "claims" / f"{cid}.yaml"


def _commit_founder(s: Store, path: Path, message: str) -> None:
    s.git("add", "--", str(path.relative_to(s.root)), check=False)
    s.git("commit", "-q", "-m", message, check=False, as_founder=True)


def _approve_claim(s: Store, cid: str, statement: str | None, scope: str | None) -> int:
    c = s.read_yaml(_claim_path(s, cid), m.Claim)
    if c.status != "proposed":
        print(f"{cid} is {c.status}, not proposed", file=sys.stderr)
        return 1
    if scope is None and c.scope.startswith("UNSPECIFIED"):
        print(f"{cid}: the runners declared no domain; approve with --scope stating what was sampled", file=sys.stderr)
        return 1
    if statement:
        c.statement = statement
    if scope:
        c.scope = scope
    c.status, c.approved_by, c.approved_at = "supported", "founder", now()
    s.write_yaml(_claim_path(s, cid), c)
    for item in s.inbox("open"):
        if item.kind == "claim_approval" and cid in item.refs:
            item.status, item.response, item.resolved_at, item.resolved_by = "approved", "claim approved", now(), "human"
            s.save_inbox(item)
    s.event("claim_approved", actor="founder", id=cid)
    _commit_founder(s, _claim_path(s, cid), f"Approve claim {cid}")
    print(f"{cid} supported")
    return 0


def cmd_claim(a: argparse.Namespace) -> int:
    s = _store()
    if a.action == "list":
        for p in sorted((s.project / "claims").glob("C*.yaml")):
            c = s.read_yaml(p, m.Claim)
            extra = f" (+{len(c.scope_restrictions)} restrictions)" if c.scope_restrictions else ""
            print(f"{c.id} {c.status:10s} {c.objective} {c.evaluation}{extra}")
        return 0
    if not a.id:
        print("claim id required", file=sys.stderr)
        return 1
    if a.action == "show":
        print(yaml.safe_dump(s.read_yaml(_claim_path(s, a.id), m.Claim).model_dump(mode="json"), sort_keys=False,
                             allow_unicode=True, width=110))
        return 0
    if a.action == "approve":
        if not human.confirm(f"claim approve {a.id}", a.id):
            return 2
        statement = Path(a.statement_file).read_text().strip() if a.statement_file else None
        return _approve_claim(s, a.id, statement, a.scope)
    if a.action == "annotate":
        if not a.note:
            print("claim annotate needs --note", file=sys.stderr)
            return 1
        if not human.confirm(f"claim annotate {a.id}", a.id):
            return 2
        c = s.read_yaml(_claim_path(s, a.id), m.Claim)
        c.annotations.append(m.Annotation(at=now(), by="founder", note=a.note, decision=a.decision))
        c.scope_restrictions += a.restrict or []
        s.write_yaml(_claim_path(s, a.id), c)
        s.event("claim_annotated", actor="founder", id=a.id, decision=a.decision, restrictions=len(a.restrict or []))
        _commit_founder(s, _claim_path(s, a.id), f"Annotate claim {a.id}" + (f" ({a.decision})" if a.decision else ""))
        print(f"{a.id} annotated")
        return 0
    return 1


def cmd_inbox(a: argparse.Namespace) -> int:
    s = _store()
    if a.action in (None, "list"):
        for i in s.inbox("open"):
            print(f"{i.id}  [{i.kind}]  {i.subject}")
        return 0
    if a.action == "show":
        print(yaml.safe_dump(s.read_yaml(s.project / "inbox" / f"{a.id}.yaml", m.InboxItem).model_dump(), sort_keys=False))
        return 0
    return 1


def cmd_approve(a: argparse.Namespace) -> int:
    return _resolve(_store(), a.id, "approved", a.note or "", replan=not a.no_replan)


def cmd_reject(a: argparse.Namespace) -> int:
    return _resolve(_store(), a.id, "rejected", a.note, replan=not a.no_replan)


def cmd_answer(a: argparse.Namespace) -> int:
    return _resolve(_store(), a.id, "answered", a.text, replan=not a.no_replan)


# ------------------------------------------------------------------ tasks
def cmd_task(a: argparse.Namespace) -> int:
    s = _store()
    if a.action == "add":
        if not (a.objective and a.title and a.type):
            print("task add needs --objective, --type, --title", file=sys.stderr)
            return 1
        tid = s.new_task_id()
        t = m.Task(id=tid, objective=a.objective, title=a.title, type=a.type, agent=a.agent or "scientist",
                   description=a.description or "", status="todo", risk=a.risk or "medium",
                   created_by="founder", created_at=now(),
                   deliverables=[f"research/diagnoses/{tid}.md"] if a.type == "investigate" else [])
        s.save_task(t)
        s.event("task_added", actor="founder", task=tid)
        print(tid)
        return 0
    if a.action == "list":
        for t in s.tasks(a.objective):
            if a.status and t.status != a.status:
                continue
            print(f"{t.id} {t.status:13s} {t.agent:9s} {t.type:18s} {t.title}")
        return 0
    t = s.task(a.id)
    if a.action == "show":
        print(yaml.safe_dump(t.model_dump(mode="json"), sort_keys=False))
    elif a.action == "start":
        from .loop import Orchestrator
        why = Orchestrator(s).start_task(t.id)
        if why:
            print(f"{t.id} not started: " + "; ".join(why), file=sys.stderr)
            return 1
        print(f"{t.id} started; the loop verifies, reviews and merges it")
    elif a.action == "retry":
        t.status, t.max_attempts = "todo", max(t.max_attempts, t.attempts + 1)
        s.save_task(t)
    elif a.action == "cancel":
        t.status = "cancelled"
        s.save_task(t)
    return 0


def cmd_packet(a: argparse.Namespace) -> int:
    """Phase-1/2 migration helper: render the packet and the one-line prompt to paste into Claude Code."""
    s = _store()
    t = s.task(a.id)
    rel = packets.work_packet(s, t, s.root, f"{t.id}-manual")
    print(f"Packet written to {rel}\n\nPaste into Claude Code (or run `claude --agent {t.agent}`):\n")
    print(f"Read `{rel}` and complete task {t.id} exactly as specified. When done, run every definition-of-done "
          "command, fix failures, and report the commands and exit codes.")
    return 0


def cmd_run(a: argparse.Namespace) -> int:
    """Run the orchestrator until one task leaves the pipeline (Phase 3 helper; only while no loop runs)."""
    from .loop import Orchestrator, acquire_loop_lock
    s = _store()
    lock = acquire_loop_lock(s)  # held until return
    if lock is None:
        print(f"the orchestrator loop is running; use `mfos task start {a.id}` and the loop finishes the task",
              file=sys.stderr)
        return 1
    o = Orchestrator(s)
    t = s.task(a.id)
    if t.status in ("todo", "proposed"):
        t.status = "todo"
        s.save_task(t)
        if t.agent == "none":
            o._start_experiment(t)
        else:
            o._start_agent(t)
    while True:
        o._poll_runs()
        o._poll_experiments()
        o._advance(s.task(a.id))
        for x in s.tasks():  # reviews spawned for this task
            if x.type == "review" and x.target == a.id and x.status == "todo":
                o._start_agent(x)
            elif x.type == "review" and x.target == a.id:
                o._advance(x)
        cur = s.task(a.id)
        if cur.status in ("done", "failed", "cancelled", "needs_founder") or \
                (cur.status == "todo" and cur.attempts >= cur.max_attempts):
            print(f"{cur.id}: {cur.status}")
            return 0 if cur.status == "done" else 2
        if cur.status == "todo":
            o._start_agent(cur)
        time.sleep(a.poll)


# ------------------------------------------------------------------ experiments / evaluation
def cmd_exp(a: argparse.Namespace) -> int:
    s = _store()
    if a.action == "register":
        if not human.confirm(f"exp register {a.id}", a.id):
            return 2
        try:
            spec = experiments.register(s, a.id, by="founder", override_null=a.override_null)
        except RuntimeError as e:
            print(e, file=sys.stderr)
            return 1
        # Leave the same auditable trail as an inbox approval (checked by scripts/audit_main.py).
        override = f" Null-discrimination override: {a.override_null}" if a.override_null else ""
        item = s.add_inbox(kind="experiment_registration", subject=f"register {a.id} (direct, via CLI)",
                           summary=f"Registered directly by the founder. spec_hash={spec.spec_hash}.{override}",
                           refs=[a.id])
        item.status, item.response, item.resolved_at = "approved", "registered via mfos exp register", now()
        s.save_inbox(item)
        print(f"registered {a.id} {spec.spec_hash}")
    elif a.action == "mint":
        run_id, seed_file = experiments.mint(s, a.id)
        print(json.dumps({"run_id": run_id, "seed_file": str(seed_file) if seed_file else None}))
    elif a.action == "abandon":  # a minted run that will never produce a result (e.g. a VM that died)
        if not a.run_id or not a.reason:
            print("exp abandon needs --run-id and --reason", file=sys.stderr)
            return 1
        s.registry_append(event="abandoned", experiment=a.id, run_id=a.run_id, reason=a.reason, by="founder")
        s.event("experiment_run_abandoned", actor="founder", id=a.id, run=a.run_id, reason=a.reason)
        print(f"{a.run_id} abandoned")
    elif a.action == "run":
        res = experiments.run(s, a.id, force=a.force, here=a.here, run_id=a.run_id,
                              seed_file=Path(a.seed_file).expanduser() if a.seed_file else None)
        print(json.dumps({"run": res.run_id, "status": res.status,
                          "metrics": {k: v.model_dump() for k, v in res.metrics.items()}}, indent=2))
        return 0 if res.status == "complete" else 3
    elif a.action == "check":
        probs = experiments.validate_draft(s, a.id)
        for p in probs:
            print("PROBLEM:", p)
        if a.rows:  # recompute every criterion on dev rows and test it against the declared nulls
            draft = s.spec_path(a.id, draft=True)
            spec = s.read_yaml(draft if draft.exists() else s.spec_path(a.id), m.ExperimentSpec)
            lines, bad = evaluate.null_check(s, spec, evaluate.load_rows(Path(a.rows)))
            print("\n".join(lines))
            for c in bad:
                print(f"PROBLEM: criterion {c} is also met by a declared null predictor on these rows")
            probs = probs + bad
        return 1 if probs else 0
    return 0


def cmd_evaluate(a: argparse.Namespace) -> int:
    ev = evaluate.evaluate(_store(), a.id, record=not a.dry_run)
    print(ev.model_dump_json(indent=2))
    return 0


def cmd_audit_evidence(a: argparse.Namespace) -> int:
    """Evidence rules v2 applied to the runs behind an objective's recorded evaluations. Writes nothing."""
    s = _store()
    rows = evaluate.audit_evidence(s, a.id)
    if a.json:
        print(evaluate.audit_json(s, a.id))
        return 0
    failures = 0
    for ev_id, run, check, outcome in rows:
        mark = "ok " if outcome == "ok" else ("n/a" if outcome.startswith("n/a") else "FAIL")
        failures += mark == "FAIL"
        print(f"{ev_id:12s} {run:34s} {check:17s} {mark:4s} {'' if outcome == 'ok' else outcome}")
    print(f"audit-evidence {a.id}: {len(rows)} checks, {failures} failed")
    return 0


# ------------------------------------------------------------------ ops
def cmd_gate(a: argparse.Namespace) -> int:
    s = _store()
    res = gates.run_gate(s, Path.cwd(), "full" if a.full else "fast")
    ok, text = gates.summarize(res)
    print(text or "all gates passed")
    return 0 if ok else 1


def cmd_loop(a: argparse.Namespace) -> int:
    from .loop import Orchestrator, acquire_loop_lock
    o = Orchestrator()
    if a.once:
        lock = acquire_loop_lock(o.s)  # held until return
        if lock is None:
            print("the orchestrator loop is running; it already ticks", file=sys.stderr)
            return 1
        print(json.dumps(o.tick()))
        return 0
    o.run_forever(poll_s=a.poll, max_cycles=a.cycles)
    return 0


def cmd_stop(a: argparse.Namespace) -> int:
    s = _store()
    (s.mfos / "STOP").write_text(now())
    print("stop requested; running agents finish, nothing new starts")
    return 0


def cmd_start(a: argparse.Namespace) -> int:
    s = _store()
    (s.mfos / "STOP").unlink(missing_ok=True)
    (s.project / "STOP").unlink(missing_ok=True)
    return 0


def cmd_status(a: argparse.Namespace) -> int:
    print(report.write_status(_store()))
    return 0


def cmd_report(a: argparse.Namespace) -> int:
    print(report.evidence_package(_store(), a.id))
    return 0


def cmd_costs(a: argparse.Namespace) -> int:
    """Per objective, from the run records (the source of truth): runs, USD, tokens, denials, usage-limit hits."""
    s = _store()
    rows = report.usage_by_objective(s)
    print(f"{'objective':10s} {'runs':>5s} {'usd':>8s} {'input':>9s} {'cache_rd':>11s} {'cache_wr':>10s} "
          f"{'output':>9s} {'thinking':>9s} {'denials':>7s} {'limits':>6s}")
    for oid, r in sorted(rows.items()):
        print(f"{oid:10s} {r['runs']:5d} {r['usd']:8.2f} {r['input']:9d} {r['cache_read']:11d} "
              f"{r['cache_creation']:10d} {r['output']:9d} {r['thinking']:9d} {r['denials']:7d} {r['limits']:6d}")
    for oid in s.objective_ids():
        st = s.objective_state(oid)
        recorded = rows.get(oid, {}).get("usd", 0.0)
        if abs(st.spent_usd - recorded) > 1.0:
            print(f"NOTE {oid}: state ledger ${st.spent_usd:.2f} differs from the run records ${recorded:.2f}")
    from .agents import AgentRunner
    today = dt.datetime.now(dt.timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
    print(f"today: ${AgentRunner(s).spent_since(today):.2f}")
    return 0


def cmd_archive(a: argparse.Namespace) -> int:
    """Offline copy of the run records (packets, transcripts) and the event log, with a sha256 manifest."""
    import hashlib
    import tarfile
    s = _store()
    dest = Path(a.dest).expanduser()
    dest.mkdir(parents=True, exist_ok=True)
    out = dest / f"mfos-archive-{time.strftime('%Y%m%dT%H%M%S')}.tar.gz"
    sources = [p for p in (s.mfos / "runs", s.project / "events.jsonl") if p.exists()]
    manifest = []
    for src in sources:
        for f in sorted([src] if src.is_file() else src.rglob("*")):
            if f.is_file():
                manifest.append(f"{hashlib.sha256(f.read_bytes()).hexdigest()}  {f.relative_to(s.root)}")
    man = dest / (out.name + ".sha256")
    man.write_text("\n".join(manifest) + "\n")
    with tarfile.open(out, "w:gz") as tar:
        for src in sources:
            tar.add(src, arcname=str(src.relative_to(s.root)))
    print(f"{out} ({len(manifest)} files; manifest {man.name})")
    return 0


def cmd_doctor(a: argparse.Namespace) -> int:
    s = _store()
    problems: list[str] = []
    for oid in s.objective_ids():
        try:
            obj = s.objective(oid)
        except Exception as e:
            problems.append(f"{oid}: invalid objective.yaml: {e}")
            continue
        st = s.objective_state(oid)
        if st.criteria_hash and st.criteria_hash != s.criteria_hash(obj):
            problems.append(f"{oid}: acceptance criteria edited after approval — re-approve or revert")
        if st.frozen_hash and st.frozen_hash != s.frozen_hash(obj):
            problems.append(f"{oid}: hypothesis, scope or evidence plan edited after approval — re-approve or revert")
    for p in sorted((s.root / "experiments" / "specs").glob("*.yaml")):
        spec = s.read_yaml(p, m.ExperimentSpec)
        if spec.status == "registered" and spec.spec_hash != s.spec_hash(spec):
            problems.append(f"{spec.id}: registered spec modified after registration")
        elif spec.status == "registered" and experiments.runner_changes(s.root, spec):
            problems.append(f"{spec.id}: runner changed after registration: {experiments.runner_changes(s.root, spec)}")
    try:
        s.tasks()  # every task file is schema-validated on load
    except Exception as e:
        problems.append(f"invalid task file: {e}")
    if not a.ci:
        from .loop import Orchestrator
        stray = Orchestrator(s).unexpected_changes()
        if stray:
            problems.append("orchestrator checkout has non-state changes: " + ", ".join(stray[:10]))
    free_gb = shutil.disk_usage(s.root).free / 1e9
    if free_gb < 20 and not a.ci:
        problems.append(f"only {free_gb:.0f} GB free disk: prune artifacts and caches (docs/INFRASTRUCTURE.md §9)")
    for p in sorted((s.root / ".claude" / "agents").glob("*.md")):
        tools = next((x for x in p.read_text().splitlines() if x.startswith("tools:")), None)
        if tools is not None and "StructuredOutput" not in tools.split(":", 1)[1].replace(",", " ").split():
            problems.append(f"{p.relative_to(s.root)}: tools: allow-list omits StructuredOutput, "
                            "so the agent never sees the --json-schema report format")
    if not a.ci:  # minted runs that never produced a result, for a week: abandon them visibly or run them
        week = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=7)
        closed = {r.get("run_id") for r in s.registry() if r.get("event") in ("abandoned", "consumed")}
        for r in s.registry():
            if r.get("event") != "minted" or r.get("run_id") in closed:
                continue
            done = (s.root / "experiments" / "results" / r["experiment"] / r["run_id"] / "run.json").exists()
            if not done and dt.datetime.fromisoformat(r["at"]) < week:
                problems.append(f"minted run {r['run_id']} has no result after 7 days "
                                f"(`mfos exp abandon {r['experiment']} --run-id {r['run_id']} --reason ...`)")
    claude_md = s.root / "CLAUDE.md"
    if claude_md.exists() and len(claude_md.read_text().splitlines()) > 200:
        problems.append("CLAUDE.md exceeds 200 lines; move procedures into skills")
    if not a.ci:
        for tool in ("git", s.policy.get("claude_bin", "claude")):
            if shutil.which(tool) is None:
                problems.append(f"{tool} not found on PATH")
    for p in problems:
        print("PROBLEM:", p)
    print("doctor: ok" if not problems else f"doctor: {len(problems)} problem(s)")
    return 1 if problems else 0


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="mfos", description="ModuleForge operating system")
    sub = p.add_subparsers(dest="cmd", required=True)

    def cmd(name: str, fn, help_: str = "") -> argparse.ArgumentParser:
        sp = sub.add_parser(name, help=help_)
        sp.set_defaults(fn=fn)
        return sp

    o = cmd("objective", cmd_objective, "create, approve (freeze), show, pause, resume an objective")
    o.add_argument("action", choices=["new", "approve", "show", "pause", "resume", "rereview", "review"])
    o.add_argument("id")

    i = cmd("inbox", cmd_inbox, "list or show founder decisions")
    i.add_argument("action", nargs="?", choices=["list", "show"])
    i.add_argument("id", nargs="?")
    ap = cmd("approve", cmd_approve, "approve an inbox item")
    ap.add_argument("id")
    ap.add_argument("--note")
    rj = cmd("reject", cmd_reject, "reject an inbox item")
    rj.add_argument("id")
    rj.add_argument("--note", required=True)
    an = cmd("answer", cmd_answer, "answer an inbox question")
    an.add_argument("id")
    an.add_argument("text")
    for p_ in (ap, rj, an):
        p_.add_argument("--no-replan", action="store_true",
                        help="resolve a decision without asking the planner to replan the objective")

    c = cmd("claim", cmd_claim, "list, show, approve (proposed -> supported) or annotate claims")
    c.add_argument("action", choices=["list", "show", "approve", "annotate"])
    c.add_argument("id", nargs="?")
    c.add_argument("--statement-file", help="approve: the final claim statement, if it differs from the draft")
    c.add_argument("--scope", help="approve: the scope, required when the runners declared no domain")
    c.add_argument("--note", help="annotate: what changed and why")
    c.add_argument("--restrict", action="append", help="annotate: a scope restriction (repeatable)")
    c.add_argument("--decision", help="annotate: the decision record, e.g. D0006")

    t = cmd("task", cmd_task, "add, list, show, start, retry, cancel tasks")
    t.add_argument("action", choices=["add", "list", "show", "start", "retry", "cancel"])
    t.add_argument("id", nargs="?")
    t.add_argument("--objective")
    t.add_argument("--status")
    t.add_argument("--type", choices=["implement", "investigate", "research", "docs", "design_experiment"])
    t.add_argument("--agent", choices=["builder", "scientist", "scout"])
    t.add_argument("--title")
    t.add_argument("--description")
    t.add_argument("--risk", choices=["low", "medium", "high", "critical"])
    pk = cmd("packet", cmd_packet, "render a task packet for manual use in Claude Code")
    pk.add_argument("id")
    rn = cmd("run", cmd_run, "run one task through the pipeline, synchronously")
    rn.add_argument("id")
    rn.add_argument("--poll", type=int, default=10)

    e = cmd("exp", cmd_exp, "register, run, or check experiments")
    e.add_argument("action", choices=["register", "run", "check", "mint", "abandon"])
    e.add_argument("id")
    e.add_argument("--force", action="store_true")
    e.add_argument("--here", action="store_true", help="dev only: run in this checkout")
    e.add_argument("--run-id", help="run: a run minted elsewhere (burst VM); abandon: the run to abandon")
    e.add_argument("--seed-file", help="run: the sealed seed of a minted run")
    e.add_argument("--reason", help="abandon: why the minted run will never produce a result")
    e.add_argument("--rows", help="check: dev-seed rows to recompute the criteria and nulls on")
    e.add_argument("--override-null", help="register: recorded reason to register despite a non-discriminating criterion")
    ev = cmd("evaluate", cmd_evaluate, "evaluate an objective's acceptance criteria")
    ev.add_argument("id")
    ev.add_argument("--dry-run", action="store_true")
    au = cmd("audit-evidence", cmd_audit_evidence, "apply evidence rules v2 to an objective's recorded evaluations")
    au.add_argument("id")
    au.add_argument("--json", action="store_true")

    g = cmd("gate", cmd_gate, "run quality gates")
    g.add_argument("--fast", action="store_true")
    g.add_argument("--full", action="store_true")
    lp = cmd("loop", cmd_loop, "run the orchestrator")
    lp.add_argument("--once", action="store_true")
    lp.add_argument("--cycles", type=int)
    lp.add_argument("--poll", type=int, default=30)
    cmd("stop", cmd_stop, "stop dispatching new work")
    cmd("start", cmd_start, "clear a stop request")
    cmd("status", cmd_status, "write and print STATUS.md")
    rp = cmd("report", cmd_report, "write an objective's evidence package")
    rp.add_argument("id")
    cmd("costs", cmd_costs, "spend, tokens, denials and usage-limit hits by objective")
    ar = cmd("archive", cmd_archive, "offline copy of run records, transcripts and events")
    ar.add_argument("--dest", default="~/mf-archive")
    dr = cmd("doctor", cmd_doctor, "check repository integrity")
    dr.add_argument("--ci", action="store_true")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    return int(args.fn(args) or 0)


if __name__ == "__main__":
    sys.exit(main())
