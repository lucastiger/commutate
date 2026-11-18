"""Burst launchers (plan section 11, fixes 1 and 4, 2026-11-15): one parameterised launcher for phased registered runs,
and every launcher copies the VM's artifact store back and checks each registered artifact before the VM goes."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
CHECK = REPO / "scripts" / "check_run_artifacts.py"
PHASED = REPO / "scripts" / "burst_phased.sh"
E010_RUN = REPO / "experiments" / "results" / "E010" / "E010-20261114T202413-80c1"


def _check(run_dir: Path, store: Path) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(CHECK), str(run_dir), str(store)], capture_output=True, text=True)


def test_the_artifact_check_resolves_as_the_evaluator_does(tmp_path):
    import hashlib
    rd, store = tmp_path / "run", tmp_path / "store"
    (rd / "work").mkdir(parents=True)
    (rd / "rows.json").write_text("rows")
    (rd / "work" / "report.json").write_text("report")
    big = b"only in the store"
    digest = hashlib.sha256(big).hexdigest()
    (store / digest[:2]).mkdir(parents=True)
    (store / digest[:2] / digest).write_bytes(big)
    sha = {n: hashlib.sha256(t.encode()).hexdigest() for n, t in (("rows", "rows"), ("report", "report"))}
    arts = [{"name": "rows.json", "sha256": sha["rows"], "bytes": 4},
            {"name": "work/report.json", "sha256": sha["report"], "bytes": 6},
            {"name": "big.bin", "sha256": digest, "bytes": len(big)}]
    (rd / "result.json").write_text(json.dumps({"artifacts": arts}))
    r = _check(rd, store)
    assert r.returncode == 0 and "3 of 3 artifacts" in r.stdout, r.stderr
    (store / digest[:2] / digest).unlink()
    r = _check(rd, store)
    assert r.returncode == 1 and "big.bin missing from the run directory and the artifact store" in r.stderr
    (rd / "rows.json").write_text("edited")
    assert "rows.json sha256 changed" in _check(rd, store).stderr


@pytest.mark.skipif(not (E010_RUN / "result.json").exists(), reason="E010's run directory is not in this checkout")
def test_the_artifact_check_catches_e010s_report(tmp_path):
    """The defect as it happened: E010 registered work/evaluation_report.json under its bare name, and without the
    VM's store the report does not resolve, although the file is in the run directory (T0349)."""
    r = _check(E010_RUN, tmp_path / "empty_store")
    assert r.returncode == 1 and "evaluation_report.json missing" in r.stderr


def test_the_phased_launcher_is_one_executable_script_for_any_registered_experiment():
    assert os.access(PHASED, os.X_OK)
    for args in ([], ["E10"], ["E010", "--now"]):
        r = subprocess.run([str(PHASED), *args], capture_output=True, text=True, cwd=REPO)
        assert r.returncode == 2 and "usage: scripts/burst_phased.sh <EXPERIMENT_ID>" in r.stderr
    r = subprocess.run([str(PHASED), "E999", "--dry-run"], capture_output=True, text=True, cwd=REPO)
    assert r.returncode == 1 and "E999 is not registered" in r.stderr


@pytest.mark.skipif(not (REPO / "experiments" / "specs" / "E010.yaml").exists(), reason="E010 is not registered here")
def test_the_phased_dry_run_of_e010_reproduces_its_launch_and_fetches_the_store():
    r = subprocess.run([str(PHASED), "E010", "--dry-run"], capture_output=True, text=True, cwd=REPO, timeout=120)
    assert r.returncode == 0, r.stderr
    out = r.stdout
    assert "uv run mfos exp mint E010" in out
    assert "--machine-type n2d-custom-8-81920-ext" in out  # phase A from config.compute.vm.machine
    assert "--machine-type n2d-custom-8-499712-ext" in out  # phase B, the largest machine the spec names
    assert "E010_SOLO_RAM_GB=488" in out
    fetch, check, delete = (out.index(x) for x in (
        ":mf/.mfos/artifacts", "scripts/check_run_artifacts.py experiments/results/E010/",
        "gcloud compute instances delete"))
    assert fetch < check < delete  # the store is copied and every artifact checked before the VM is deleted


def test_the_single_vm_launcher_copies_the_store_back_and_checks_the_run():
    text = (REPO / "scripts" / "burst_gcp.sh").read_text()
    assert '"$NAME:mf/.mfos/artifacts"' in text
    assert 'python3 scripts/check_run_artifacts.py "$FETCH/$RUN_ID" .mfos/artifacts' in text


def test_the_single_vm_launcher_exports_mf_gcp_env_into_the_job_and_refuses_a_malformed_one():
    """2026-11-18: in experiment mode the launcher passed no environment, so E007's registered run would have run one
    solve at a time (E007_MAX_PROCS defaults to 1), about 85 VM-h instead of 36. MF_GCP_ENV now carries NAME=VALUE pairs
    into job.sh; a malformed one stops the launcher before anything has side effects (no gcloud call, no run minted)."""
    script = REPO / "scripts" / "burst_gcp.sh"
    text = script.read_text()
    assert 'ENV_LINE="export $JOB_ENV"' in text and '"$ENV_LINE" "$JOB" > "$WORK/job.sh"' in text
    for bad in ("E007_MAX_PROCS=8 oops", "lower=1", "E007_X=a b", "E007_X=$(id)", "E007_X='1'"):
        env = dict(os.environ, MF_GCP_ENV=bad, PATH="/usr/bin:/bin")
        r = subprocess.run(["bash", str(script), "--cmd", "true", "x"], capture_output=True, text=True, cwd=REPO, env=env)
        assert r.returncode == 2 and "MF_GCP_ENV:" in r.stderr, (bad, r.returncode, r.stderr)
