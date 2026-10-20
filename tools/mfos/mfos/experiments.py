"""Run registered experiments reproducibly. No LLM is in this path.

Rules enforced here:
  * only `registered` specs whose content hash still matches may run;
  * runs happen in a clean detached checkout of main (so results cite a merged commit);
  * sealed-seed specs get a fresh unseen seed per run, recorded in the result;
  * a complete result for the same (spec_hash, commit, seed policy) is reused unless forced (legacy specs only);
  * the runner must write result.json through mfos.evidence.ExperimentRun.

Evidence rules v2 (specs registered after the 2026-10-19 audit, ``evidence_rules: 2``):
  * every run is minted first in experiments/registry.jsonl, with a commitment sha256(run_id:seed) for sealed
    specs; the seed itself stays in the git-ignored .mfos/sealed/ until the run records it in its result;
  * a burst VM runs a run minted on the main machine (`--run-id/--seed-file`) and never mints;
  * the registered spec must be committed in the checkout that runs (closes E003's gap: registered in the
    working tree 25 s before its run and committed afterwards);
  * `mfos exp run` records the sha256 of the runner files and of the spec's code_under_test in the result.
"""
from __future__ import annotations

import hashlib
import os
import secrets
import shlex
import shutil
import subprocess
import time
from pathlib import Path
from typing import Optional

from . import models as m
from .gitops import GitOps
from .store import Store, now


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def runner_files(root: Path, runner: str) -> dict[str, str]:
    """sha256 of every repository file the runner command names (the code that defines the experiment)."""
    return {tok: _file_sha256(root / tok) for tok in shlex.split(runner)
            if not tok.startswith("-") and (root / tok).is_file()}


EVIDENCE_RULES = 2  # evidence-rules version given to newly registered specs and newly approved objectives


def code_hashes(root: Path, patterns: list[str]) -> dict[str, str]:
    """sha256 of every repository file matched by ``patterns`` (paths or globs relative to ``root``), sorted."""
    out: dict[str, str] = {}
    for pat in patterns:
        hits = sorted(p for p in root.glob(pat) if p.is_file())
        if not hits:
            raise RuntimeError(f"code_under_test pattern `{pat}` matches no file in {root}")
        for p in hits:
            out[p.relative_to(root).as_posix()] = _file_sha256(p)
    return dict(sorted(out.items()))


def commitment(run_id: str, seed: int) -> str:
    return hashlib.sha256(f"{run_id}:{seed}".encode()).hexdigest()


def sealed_seed_path(store: Store, run_id: str) -> Path:
    return store.mfos / "sealed" / f"{run_id}.seed"


def new_run_id(eid: str) -> str:
    return f"{eid}-{time.strftime('%Y%m%dT%H%M%S')}-{secrets.token_hex(2)}"


def _registered(store: Store, eid: str) -> m.ExperimentSpec:
    spec = store.spec(eid)
    if spec.status != "registered" or spec.spec_hash != store.spec_hash(spec):
        raise RuntimeError(f"{eid} is not a registered, unmodified spec; refusing to run")
    return spec


def mint(store: Store, eid: str) -> tuple[str, Optional[Path]]:
    """Record a run id (and, for sealed specs, a commitment to a fresh seed) in the registry before the run exists.
    Returns (run_id, seed file or None). Burst scripts mint here, then pass both to the VM."""
    spec = _registered(store, eid)
    run_id = new_run_id(eid)
    seed_file = None
    commit = None
    if spec.sealed_seed:
        seed = secrets.randbelow(2**31 - 1)
        seed_file = sealed_seed_path(store, run_id)
        seed_file.parent.mkdir(parents=True, exist_ok=True)
        seed_file.write_text(str(seed))
        os.chmod(seed_file, 0o600)
        commit = commitment(run_id, seed)
    store.registry_append(event="minted", experiment=eid, run_id=run_id, spec_hash=spec.spec_hash, commitment=commit)
    store.event("experiment_minted", id=eid, run=run_id)
    return run_id, seed_file


def runner_changes(root: Path, spec: m.ExperimentSpec) -> list[str]:
    """Frozen runner files that are missing or differ in the checkout at ``root``."""
    return [rel for rel, want in spec.runner_files.items()
            if not (root / rel).is_file() or _file_sha256(root / rel) != want]


def register(store: Store, eid: str, by: str = "founder") -> m.ExperimentSpec:
    draft = store.spec_path(eid, draft=True)
    src = draft if draft.exists() else store.spec_path(eid)
    spec = store.read_yaml(src, m.ExperimentSpec)
    spec.runner_files = runner_files(store.root, spec.runner)
    if not spec.runner_files:
        raise RuntimeError(f"{eid}: cannot freeze the runner: `{spec.runner}` names no file in the repository")
    spec.evidence_rules = max(spec.evidence_rules, EVIDENCE_RULES)
    if spec.code_under_test:
        code_hashes(store.root, spec.code_under_test)  # every pattern must name at least one file now
    spec.status = "registered"
    spec.registered_by = by
    spec.registered_at = now()
    spec.spec_hash = store.spec_hash(spec)
    store.write_yaml(store.spec_path(eid), spec)
    if draft.exists():
        draft.unlink()
    store.event("experiment_registered", id=eid, hash=spec.spec_hash, by=by)
    return spec


def _cached(store: Store, spec: m.ExperimentSpec, commit: str) -> Optional[m.ExperimentResult]:
    if spec.sealed_seed:
        return None  # every sealed run must use a new seed
    for r in reversed(store.results(spec.id)):
        if r.status == "complete" and r.provenance.git_commit == commit and r.provenance.spec_hash == spec.spec_hash:
            return r
    return None


def run(store: Store, eid: str, *, ref: Optional[str] = None, force: bool = False,
        here: bool = False, run_id: Optional[str] = None, seed_file: Optional[Path] = None) -> m.ExperimentResult:
    spec = _registered(store, eid)
    v2 = spec.evidence_rules >= 2
    if run_id and spec.sealed_seed and not seed_file:
        raise RuntimeError(f"{eid}: a minted run of a sealed spec needs its --seed-file")
    git = GitOps(store)
    if here:
        cwd = store.root
    else:
        cwd = git.detached_worktree(f"exp-{eid}", ref or git.main)
    changed = runner_changes(cwd, spec)  # checked in the checkout that will actually run
    if v2 and not here and not changed:
        committed = cwd / "experiments" / "specs" / f"{eid}.yaml"
        ok = committed.exists() and store.read_yaml(committed, m.ExperimentSpec).spec_hash == spec.spec_hash
        if not ok:
            git.remove_worktree(cwd)
            raise RuntimeError(f"{eid}: the registered spec is not committed in {ref or git.main}; commit the "
                               "registration first (a run must cite a commit that contains its spec)")
    if changed:
        if not here:
            git.remove_worktree(cwd)
        raise RuntimeError(f"{eid}: runner file(s) {changed} changed since registration; refusing to run "
                           "(register a new experiment id for a new design)")
    commit = store.git("rev-parse", "HEAD", cwd=cwd)
    if not force and not here and not v2 and not run_id:
        hit = _cached(store, spec, commit)
        if hit:
            store.event("experiment_cached", id=eid, run=hit.run_id)
            git.remove_worktree(cwd)
            return hit
    seed: Optional[int] = None
    if run_id:  # minted elsewhere (burst VM): use exactly that id and seed, never touch the registry here
        if seed_file:
            seed = int(Path(seed_file).read_text().strip())
    elif v2 and not here:
        run_id, minted_seed_file = mint(store, eid)
        if minted_seed_file:
            seed = int(minted_seed_file.read_text().strip())
    else:
        run_id = new_run_id(eid)
    if spec.sealed_seed and seed is None:
        seed = secrets.randbelow(2**31 - 1)
    run_dir = store.root / "experiments" / "results" / eid / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    env = {**os.environ,
           "MFOS_EXPERIMENT_ID": eid, "MFOS_RUN_ID": run_id, "MFOS_RUN_DIR": str(run_dir),
           "MFOS_SPEC_HASH": spec.spec_hash or "", "MFOS_SPEC_JSON": spec.model_dump_json(),
           "MFOS_ARTIFACT_STORE": str(store.mfos / "artifacts"),
           "PYTHONPATH": os.pathsep.join(filter(None, [str(cwd / "tools" / "mfos"), str(cwd / "src"),
                                                       os.environ.get("PYTHONPATH", "")]))}
    if spec.sealed_seed:
        env["MFOS_SEED"] = str(seed)
    store.event("experiment_started", id=eid, run=run_id, commit=commit)
    t0 = time.time()
    with open(run_dir / "runner.log", "w") as log:
        try:
            proc = subprocess.run(spec.runner, shell=True, cwd=cwd, env=env, stdout=log, stderr=subprocess.STDOUT,
                                  timeout=spec.timeout_min * 60)
            code = proc.returncode
        except subprocess.TimeoutExpired:
            code = -9
    res_path = run_dir / "result.json"
    if res_path.exists():
        res = m.ExperimentResult.model_validate_json(res_path.read_text())
    else:
        res = m.ExperimentResult(experiment_id=eid, run_id=run_id, status="error",
                                 provenance=m.Provenance(git_commit=commit, git_dirty=False, spec_hash=spec.spec_hash),
                                 notes=f"runner exit code {code}; no result.json written")
        store.write_json(res_path, res)
    if code != 0 and res.status == "complete":
        res.status = "error"
        res.notes += f"\nrunner exited with code {code} after writing a result; downgraded to error"
        store.write_json(res_path, res)
    if v2:  # recorded by the wrapper, never by the runner
        res.provenance.runner_hashes = runner_files(cwd, spec.runner)
        try:
            res.provenance.code = code_hashes(cwd, spec.code_under_test)
        except RuntimeError as e:
            res.status = "error"
            res.notes += f"\n{e}"
        store.write_json(res_path, res)
    seconds = round(time.time() - t0, 1)
    store.event("experiment_finished", id=eid, run=run_id, status=res.status, seconds=seconds)
    # Last tracked write: once run.json exists the loop may evaluate the run and commit state (Store.results).
    store.write_json(run_dir / "run.json", {"exit_code": code, "seconds": seconds, "cwd_commit": commit})
    if not here:
        git.remove_worktree(cwd)
    return res


def validate_draft(store: Store, eid: str) -> list[str]:
    """Static checks the orchestrator runs on a scientist's draft before asking for registration."""
    problems: list[str] = []
    p = store.spec_path(eid, draft=True)
    if not p.exists():
        return [f"draft {p} missing"]
    try:
        spec = store.read_yaml(p, m.ExperimentSpec)
    except Exception as e:  # schema violation
        return [f"schema: {e}"]
    if not spec.metrics:
        problems.append("no metrics declared")
    if not spec.sanity_checks:
        problems.append("no sanity checks declared (every experiment needs at least one)")
    obj = store.objective(spec.objective)
    needed = {c.metric.split(".", 1)[1] for c in obj.acceptance.pass_all + obj.acceptance.fail_any
              if c.metric.startswith(eid + ".")}
    missing = needed - {x.name for x in spec.metrics}
    if missing:
        problems.append(f"metrics required by acceptance criteria not declared: {sorted(missing)}")
    runner_file = spec.runner.split()[-1] if spec.runner else ""
    if runner_file.endswith(".py") and not (store.root / runner_file).exists():
        problems.append(f"runner script {runner_file} not found")
    return problems


def artifacts_gc(store: Store, keep_days: int = 60) -> int:
    root = store.mfos / "artifacts"
    if not root.exists():
        return 0
    cutoff, n = time.time() - keep_days * 86400, 0
    for p in root.glob("*/*"):
        if p.stat().st_atime < cutoff:
            p.unlink()
            n += 1
    shutil.rmtree(root / "tmp", ignore_errors=True)
    return n
