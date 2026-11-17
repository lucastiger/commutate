"""Check e007_metrics.patch on a scratch copy (T0396): extract HEAD's tools/mfos and tests/mfos into a temporary
directory, apply the patch there, and run the patched tests/mfos/test_metrics.py against the patched package (extra
arguments go to pytest; --baseline skips the patch). Tests that read repository files by relative path fail in the
scratch copy with or without the patch. Nothing in the repository is modified.
Run from the repository root: uv run python research/o002_e007/check_patch.py"""
from __future__ import annotations

import io
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PATCH = Path(__file__).resolve().parent / "e007_metrics.patch"


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="e007patch_"))
    try:
        tar = subprocess.run(["git", "archive", "HEAD", "tools/mfos", "tests/mfos"], cwd=ROOT, check=True,
                             capture_output=True).stdout
        tarfile.open(fileobj=io.BytesIO(tar)).extractall(tmp, filter="data")
        subprocess.run(["git", "init", "-q"], cwd=tmp, check=True)
        if "--baseline" not in sys.argv:  # --baseline: the same run without the patch, for comparison
            subprocess.run(["git", "apply", str(PATCH)], cwd=tmp, check=True)
        chk = tmp / "chk"
        chk.mkdir()
        shutil.copy(tmp / "tests" / "mfos" / "test_metrics.py", chk / "test_patched_metrics.py")
        env = {**os.environ, "PYTHONPATH": str(tmp / "tools" / "mfos")}
        probe = subprocess.run([sys.executable, "-c", "import mfos.metrics as m; print(m.__file__)"], env=env,
                               capture_output=True, text=True, check=True).stdout.strip()
        print(f"patched package: {probe}")
        if not probe.startswith(str(tmp)):
            print("the patched package was not the one imported")
            return 1
        r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", f"--rootdir={chk}",
                            str(chk / "test_patched_metrics.py"), *[a for a in sys.argv[1:] if a != "--baseline"]],
                           env=env, capture_output=True, text=True)
        print(r.stdout[-1500:], r.stderr[-800:])
        return r.returncode
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
