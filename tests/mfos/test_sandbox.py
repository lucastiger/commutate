"""Agents' shells run in Claude Code's OS sandbox with a provisioned venv (audit 2026-10-19, W2): per-run settings,
environment, provisioning failures as infrastructure, and the real-CLI smoke script (here with a fake CLI)."""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from mfos import models as m
from mfos.agents import AgentRunner
from mfos.loop import Orchestrator
from mfos.store import Store

REPO = Path(__file__).resolve().parents[2]


def _start(sandbox, tmp_path, monkeypatch, settings_file=None):
    log = tmp_path / "argv.jsonl"
    monkeypatch.setenv("FAKE_ARGV_LOG", str(log))
    s = Store()
    t = m.Task(id="T9900", objective="O000", title="scout", type="research", agent="scout")
    rec = AgentRunner(s).start(task=t, role="scout", cwd=sandbox, packet_rel=".mfos/packets/T9900-a1.md", schema={},
                               budget_usd=1.0, max_turns=2, settings_file=settings_file)
    for _ in range(100):
        if log.exists():
            break
        time.sleep(0.1)
    call = json.loads(log.read_text().splitlines()[-1])
    argv = call["argv"]
    path = Path(argv[argv.index("--settings") + 1]) if "--settings" in argv else None
    return rec, call, path


def test_a_worktree_run_gets_only_the_sandbox_block(sandbox, tmp_path, monkeypatch):
    rec, call, path = _start(sandbox, tmp_path, monkeypatch)
    assert path == Store().mfos / "runs" / rec.run_id / "settings.json"
    settings = json.loads(path.read_text())
    assert list(settings) == ["sandbox"]  # the project's own settings supply permissions and hooks
    sb = settings["sandbox"]
    assert sb["enabled"] and sb["autoAllowBashIfSandboxed"] and sb["failIfUnavailable"]
    assert sb["allowUnsandboxedCommands"] is False
    assert sb["filesystem"]["allowWrite"] and "uv" in sb["filesystem"]["allowWrite"][0]
    assert call["env"]["UV_OFFLINE"] == "1" and call["env"]["UV_FROZEN"] == "1"


def test_a_review_run_gets_the_orchestrator_settings_plus_the_sandbox(sandbox, tmp_path, monkeypatch):
    _, _, path = _start(sandbox, tmp_path, monkeypatch, settings_file=Store().root / ".claude" / "settings.json")
    settings = json.loads(path.read_text())
    assert {"permissions", "hooks", "sandbox"} <= set(settings)
    original = json.loads((Store().root / ".claude" / "settings.json").read_text())
    assert settings["permissions"] == original["permissions"]  # every deny rule kept


def test_with_the_sandbox_disabled_nothing_changes(sandbox, tmp_path, monkeypatch):
    pol = sandbox / ".mfos" / "policy.toml"
    text = pol.read_text()
    head, tail = text.split("[sandbox]", 1)
    assert tail.lstrip(" #").split("\n", 1)[1].startswith("enabled = true")
    pol.write_text(head + "[sandbox]" + tail.replace("enabled = true", "enabled = false", 1))
    _, call, path = _start(sandbox, tmp_path, monkeypatch)
    assert path is None and call["env"]["UV_OFFLINE"] is None


def test_a_venv_that_cannot_be_built_is_an_infrastructure_pause(sandbox):
    (sandbox / "uv.lock").write_text("not a lockfile\n")
    s = Store()
    s.git("add", "-A")
    s.git("commit", "-qm", "a broken lockfile", as_founder=True)
    o = Orchestrator(s)
    t = m.Task(id="T9901", objective="O000", title="build", type="implement", agent="builder", status="todo")
    s.save_task(t)
    o._start_agent(t)
    s = Store()
    t = s.task("T9901")
    assert (t.status, t.attempts, t.runs) == ("needs_founder", 0, [])
    assert any(i.subject == "infrastructure: venv_provisioning" for i in s.inbox("open"))


FAKE = '''import json, sys
args = sys.argv[1:]
assert "--settings" in args and json.load(open(args[args.index("--settings") + 1]))["sandbox"]["enabled"]
rep = {"pytest_ok": True, "tmp_ok": True, "home_write_ok": False, "network_ok": NETWORK, "notes": "fake"}
print(json.dumps({"type": "result", "is_error": False, "structured_output": rep, "permission_denials": [],
                  "total_cost_usd": 0.01}))
'''


def _smoke(sandbox, tmp_path, network):
    fake = tmp_path / "fake_cli.py"
    fake.write_text(FAKE.replace("NETWORK", str(network)))
    env = {**os.environ, "MFOS_CLAUDE_BIN": f"{sys.executable} {fake}", "MFOS_ROOT": str(sandbox)}
    return subprocess.run([sys.executable, str(REPO / "scripts" / "sandbox_smoke.py")], cwd=sandbox, env=env,
                          capture_output=True, text=True, timeout=300)


def test_the_smoke_script_passes_a_confined_working_critic(sandbox, tmp_path):
    r = _smoke(sandbox, tmp_path, network=False)
    assert r.returncode == 0 and r.stdout.strip().endswith("PASS"), r.stdout + r.stderr


def test_the_smoke_script_fails_when_the_network_is_open(sandbox, tmp_path):
    r = _smoke(sandbox, tmp_path, network=True)
    assert r.returncode == 1 and "FAIL network blocked" in r.stdout, r.stdout + r.stderr
