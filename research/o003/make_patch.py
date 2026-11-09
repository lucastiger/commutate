"""Generate research/o003/headroom_metrics.patch (T0261): a unified diff adding the O003 headroom metrics to the protected
tools/mfos/mfos/metrics.py (functions, METRICS dispatch, module docstring) and their tests to tests/mfos/test_metrics.py.
The code is copied verbatim from the marked blocks of headroom_metrics.py and test_headroom_metrics.py, so the patch and
the tested draft cannot drift apart. Run from the repository root: uv run python research/o003/make_patch.py"""
from __future__ import annotations

import difflib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
METRICS = "tools/mfos/mfos/metrics.py"
TESTS = "tests/mfos/test_metrics.py"


def _between(text: str, start: str, end: str) -> str:
    i, j = text.index(start) + len(start), text.index(end)
    return text[i:j]


def _replace_once(text: str, old: str, new: str) -> str:
    if text.count(old) != 1:
        raise SystemExit(f"anchor not found exactly once: {old[:60]!r}")
    return text.replace(old, new)


def patched_metrics(src: str) -> str:
    draft = (HERE / "headroom_metrics.py").read_text()
    block = _between(draft, "# >>> metrics.py\n", "# <<< metrics.py\n")
    entries = _between(draft, "    # >>> METRICS\n", "    # <<< METRICS\n")
    anchor = "# ------------------------------------------------------------------------------------------------ records adapter"
    out = _replace_once(src, anchor, block + "\n\n" + anchor)
    tail = "        rows, pred, ref, group=group, role=role, **(params or {})),\n}\n"
    out = _replace_once(out, tail, tail[:-2] + entries + "}\n")
    doc = "  optimism_ratio_by_group   per group (ref[reference] - ref[selected]) / (pred[reference] - pred[selected]), aggregated\n"
    add = ("  headroom_min_lo           O003 A1: min over counted references of h_lo = a (1 - r (1 + w)), twin rule first\n"
           "  headroom_max_hi_ind       O003 K1: max over counted references of h_hi = a (1 - r_ind (1 - w_ind)), levelling\n"
           "                            first (+inf if not levelled), then the twin rule, then near ties\n")
    return _replace_once(out, doc, doc + add)


def patched_tests(src: str) -> str:
    body = (HERE / "test_headroom_metrics.py").read_text().split("# >>> shared tests\n", 1)[1]
    out = _replace_once(src, "import json\n", "import importlib.util\nimport json\n")
    return out.rstrip("\n") + "\n\n" + body.rstrip("\n") + "\n"


def diff(path: str, new: str) -> str:
    old = (ROOT / path).read_text()
    return "".join(difflib.unified_diff(old.splitlines(keepends=True), new.splitlines(keepends=True),
                                        fromfile=f"a/{path}", tofile=f"b/{path}"))


def main() -> int:
    patch = diff(METRICS, patched_metrics((ROOT / METRICS).read_text()))
    patch += diff(TESTS, patched_tests((ROOT / TESTS).read_text()))
    (HERE / "headroom_metrics.patch").write_text(patch)
    print(f"wrote {HERE / 'headroom_metrics.patch'} ({len(patch.splitlines())} lines)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
