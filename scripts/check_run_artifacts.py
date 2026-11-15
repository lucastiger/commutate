#!/usr/bin/env python3
"""Check that every artifact a run's result.json registers resolves the way the evaluator resolves it:
<run_dir>/<name>, else <store>/<sha256[:2]>/<sha256>, with a matching sha256 (tools/mfos/mfos/evaluate.py, check
"artifacts"). The burst launchers run it after the copy-back, so a run that would be INVALID for a missing artifact is
caught while the VM still exists (E010: work/evaluation_report.json registered under its bare name, the store copy left
on the VM; T0349).

Usage: scripts/check_run_artifacts.py <run_dir> [store]     store defaults to .mfos/artifacts
Exit 0 when every artifact resolves, 1 when one does not, 2 on bad usage. Standard library only, so the launchers can
run it with the system python3.
"""
import hashlib
import json
import sys
from pathlib import Path


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def main(argv: list[str]) -> int:
    if len(argv) not in (2, 3):
        print(__doc__.split("\n\n")[1], file=sys.stderr)
        return 2
    rd = Path(argv[1])
    store = Path(argv[2]) if len(argv) == 3 else Path(".mfos/artifacts")
    artifacts = json.loads((rd / "result.json").read_text()).get("artifacts", [])
    bad = []
    for a in artifacts:
        p = rd / a["name"]
        if not p.exists():
            p = store / a["sha256"][:2] / a["sha256"]
        if not p.exists():
            bad.append(f"{a['name']} missing from the run directory and the artifact store")
        elif sha256(p) != a["sha256"]:
            bad.append(f"{a['name']} sha256 changed")
    for b in bad:
        print(b, file=sys.stderr)
    print(f"{len(artifacts) - len(bad)} of {len(artifacts)} artifacts of {rd} resolve")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
