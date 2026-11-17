"""Verdict hardening of f1_dev_check.analyse (T0419, review T0411 findings 1-2).  Synthetic level-2 records live in
tmp_path only: L2 = L1 + 0.35 (L1 - L0) of the cached level-0/1 records (so the level-2 step is 0.35 of the level-1
step: a converging sequence).  Nothing is solved."""
from __future__ import annotations

import copy
import importlib.util
import json
import shutil
from pathlib import Path

import numpy as np
import pytest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("f1_dev_check", HERE / "f1_dev_check.py")
F = importlib.util.module_from_spec(spec)
spec.loader.exec_module(F)

SYN_KEYS = [k for k in F.all_keys(levels=(2,)) if not (k.endswith("__P_ref__L2") and not k.split("__")[0].endswith("_p"))]


@pytest.fixture
def env(tmp_path, monkeypatch):
    cache, burst = tmp_path / "cache", tmp_path / "burst_out"
    shutil.copytree(F.CACHE, cache)
    burst.mkdir()
    monkeypatch.setattr(F, "CACHE", cache)
    monkeypatch.setattr(F, "BURST_OUT", burst)
    monkeypatch.setattr(F, "OUT", tmp_path / "out.json")
    return cache, burst


def write_synthetic(cache: Path, burst: Path) -> None:
    for k in SYN_KEYS:
        name, load, _ = F.parse_key(k)
        r0 = json.loads((cache / f"{F.key_of(name, load, 0)}.json").read_text())
        r1 = json.loads((cache / f"{F.key_of(name, load, 1)}.json").read_text())
        r2 = copy.deepcopy(r1)
        r2.update(key=k, level=2, dofs=8 * r1["dofs"])
        for f in ("tj_mean", "tj_max"):
            a, b = np.array(r0[f]), np.array(r1[f])
            r2[f] = (b + 0.35 * (b - a)).tolist()
        (burst / f"{k}.json").write_text(json.dumps(r2))


def edit(burst: Path, key: str, fn) -> None:
    p = burst / f"{key}.json"
    r = json.loads(p.read_text())
    fn(r)
    p.write_text(json.dumps(r))


def test_clean_synthetic_set_confirms(env):
    write_synthetic(*env)
    res = F.analyse()
    assert res["status"] == "complete"
    assert res["broken"] == []
    assert res["level1"] == "confirmed"
    assert res["checks"]["sanity"]["record_provenance"]["passed"] is True


def test_real_perturbation_refutes(env):
    write_synthetic(*env)
    edit(env[1], "u_shaped_2_p__P_ref__L2", lambda r: r["tj_mean"].__setitem__(0, r["tj_mean"][0] + 0.3))
    res = F.analyse()
    assert res["broken"] == []
    assert res["level1"] == "refuted"


def test_wrong_solver_hash_is_pending(env):
    write_synthetic(*env)
    edit(env[1], SYN_KEYS[0], lambda r: r.update(thermal_fem_sha256="deadbeef" * 8))
    res = F.analyse()
    assert res["level1"] == "pending"
    assert "sanity.own_solves_frozen_bytes" in res["broken"]
    assert "sanity.record_provenance" in res["broken"]
    assert SYN_KEYS[0] in res["checks"]["sanity"]["record_provenance"]["failing_keys"]


def test_power_off_one_percent_is_pending(env):
    write_synthetic(*env)
    edit(env[1], SYN_KEYS[1], lambda r: r.update(power_W=r["power_W"] * 1.01))
    res = F.analyse()
    assert res["level1"] == "pending"
    assert res["checks"]["sanity"]["record_provenance"]["failing_keys"] == [SYN_KEYS[1]]


def test_cache_record_power_off_is_pending(env):
    write_synthetic(*env)
    p = env[0] / "u_shaped_2__half_P_ref__L1.json"
    r = json.loads(p.read_text())
    r["power_W"] *= 1 + 1e-9
    p.write_text(json.dumps(r))
    res = F.analyse()
    assert res["level1"] == "pending"
    assert "u_shaped_2__half_P_ref__L1" in res["checks"]["sanity"]["record_provenance"]["failing_keys"]


def test_fingerprint_mismatch_is_pending(env):
    write_synthetic(*env)
    edit(env[1], SYN_KEYS[2], lambda r: r.update(fingerprint="0" * 64))
    res = F.analyse()
    assert res["level1"] == "pending"
    assert "sanity.record_provenance" in res["broken"]


def test_frozen_config_hash_mismatch_is_pending(env):
    write_synthetic(*env)
    edit(env[1], SYN_KEYS[3], lambda r: r.update(frozen_config_sha256="0" * 64))
    res = F.analyse()
    assert res["level1"] == "pending"
    assert "sanity.record_provenance" in res["broken"]


def test_forced_reproduction_failure_is_pending(env):
    write_synthetic(*env)
    p = env[0] / "u_shaped_2__P_ref__L1.json"
    r = json.loads(p.read_text())
    r["tj_mean"][0] += 1e-3
    p.write_text(json.dumps(r))
    res = F.analyse()
    assert res["reproduction_check"]["passed"] is False
    assert res["level1"] == "pending"
    assert "reproduction_check" in res["broken"]


def test_repository_data_without_burst_awaits_level2(env):
    res = F.analyse()
    assert res["status"] == "awaiting_level2"
    assert res["level1"] == "pending"
    assert res["broken"] == []
    prov = res["checks"]["sanity"]["record_provenance"]
    assert prov["passed"] is True and prov["n_o007_dev3"] == 2
