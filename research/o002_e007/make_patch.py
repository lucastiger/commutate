"""Generate research/o002_e007/e007_metrics.patch (T0396): O002 F3's confidence bound for the protected tools/mfos.

- tools/mfos/mfos/metrics.py: the block between the ``metrics.py`` markers of e007_metrics.py (verbatim), inserted
  before null_column; bootstrap_ci refuses scheme 'woodruff' (not a bootstrap); the module docstring lists quantile_ci.
- tools/mfos/mfos/models.py: CISpec.scheme gains 'woodruff' (``cluster`` names the unit column).
- tools/mfos/mfos/evaluate.py: metric_value routes scheme 'woodruff' to mfos.metrics.quantile_ci (bootstrap_ci receives
  only an opaque statistic; the bound needs the metric's terms and their layouts).
- tests/mfos/test_metrics.py: the shared tests of test_e007_metrics.py (verbatim) and one evaluator-routing test.
Run from the repository root: uv run python research/o002_e007/make_patch.py"""
from __future__ import annotations

import difflib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent


def _between(text: str, start: str, end: str) -> str:
    i, j = text.index(start) + len(start), text.index(end)
    return text[i:j]


def _once(text: str, old: str, new: str) -> str:
    if text.count(old) != 1:
        raise SystemExit(f"anchor not found exactly once: {old[:70]!r}")
    return text.replace(old, new)


def patched_metrics(src: str) -> str:
    block = _between((HERE / "e007_metrics.py").read_text(), "# >>> metrics.py\n", "# <<< metrics.py\n")
    out = _once(src, "def null_column(", block + "\n\ndef null_column(")
    out = _once(out, '    else:\n        raise ValueError(f"unknown bootstrap scheme `{scheme}`")\n',
                '    elif scheme == "woodruff":\n'
                '        raise ValueError("scheme `woodruff` is not a bootstrap: the evaluator calls quantile_ci, which '
                'needs the metric\'s terms")\n'
                '    else:\n        raise ValueError(f"unknown bootstrap scheme `{scheme}`")\n')
    doc = "  max_over_groups           max over the values of one column of another metric computed per value\n"
    add = ("Bounds (CISpec scheme 'woodruff', O002 F3): quantile_ci gives one-sided (1 + level) / 2 bounds on the q-quantile\n"
           "metrics above by woodruff_bound / woodruff_ratio_bound, layouts as the independent units.\n")
    return _once(out, doc, doc + add)


def patched_models(src: str) -> str:
    out = _once(src, '    scheme: Literal["plain", "stratified", "cluster"] = "plain"\n',
                '    scheme: Literal["plain", "stratified", "cluster", "woodruff"] = "plain"  # woodruff: O002 F3\n')
    return _once(out, '    cluster: Optional[str] = None  # column, for scheme "cluster"\n',
                 '    cluster: Optional[str] = None  # column, for schemes "cluster" and "woodruff" (the unit)\n')


def patched_evaluate(src: str) -> str:
    old = ("    point, ci = mx.bootstrap_ci(stat, rows, n_boot=rc.ci.n_boot, level=rc.ci.level, seed=rc.ci.seed,\n"
           "                                scheme=rc.ci.scheme, strata=rc.ci.strata, cluster=rc.ci.cluster)\n")
    new = ("    if rc.ci.scheme == \"woodruff\":  # O002 F3: needs the metric's terms, not an opaque statistic\n"
           "        point, ci = mx.quantile_ci(rc.fn, rows, pred=pred, ref=rc.ref, strata=rc.strata, group=rc.group,\n"
           "                                   role=rc.role, params=rc.params, level=rc.ci.level, cluster=rc.ci.cluster)\n"
           "    else:\n"
           "        point, ci = mx.bootstrap_ci(stat, rows, n_boot=rc.ci.n_boot, level=rc.ci.level, seed=rc.ci.seed,\n"
           "                                    scheme=rc.ci.scheme, strata=rc.ci.strata, cluster=rc.ci.cluster)\n")
    return _once(src, old, new)


ROUTING_TEST = '''

def test_evaluator_routes_scheme_woodruff_to_quantile_ci():
    from mfos import evaluate as ev
    from mfos import models as mm
    rows = [{"layout": f"L{k // 2}", "p": 0.01 * k, "r": 0.0} for k in range(160)]
    rc = mm.RecomputeSpec(metric="x", fn="quantile_abs_err", pred="p", ref="r", params={"q": 0.95},
                          ci=mm.CISpec(scheme="woodruff", level=0.9, cluster="layout"))
    mv = ev.metric_value(rc, rows, "p")
    pt, ci = mx.quantile_ci("quantile_abs_err", rows, pred="p", ref="r", params={"q": 0.95}, level=0.9,
                            cluster="layout")
    assert mv.value == pt and tuple(mv.ci) == ci and mv.level == 0.9 and ci[0] <= pt <= ci[1]
    with pytest.raises(ValueError, match="woodruff"):
        mx.bootstrap_ci(lambda rr: 0.0, rows, scheme="woodruff")
'''


def patched_tests(src: str) -> str:
    body = (HERE / "test_e007_metrics.py").read_text().split("# >>> shared tests\n", 1)[1]
    return src.rstrip("\n") + "\n\n" + body.rstrip("\n") + "\n" + ROUTING_TEST


def diff(path: str, new: str) -> str:
    old = (ROOT / path).read_text()
    return "".join(difflib.unified_diff(old.splitlines(keepends=True), new.splitlines(keepends=True),
                                        fromfile=f"a/{path}", tofile=f"b/{path}"))


def main() -> int:
    jobs = (("tools/mfos/mfos/metrics.py", patched_metrics), ("tools/mfos/mfos/models.py", patched_models),
            ("tools/mfos/mfos/evaluate.py", patched_evaluate), ("tests/mfos/test_metrics.py", patched_tests))
    patch = "".join(diff(p, f((ROOT / p).read_text())) for p, f in jobs)
    (HERE / "e007_metrics.patch").write_text(patch)
    print(f"wrote {HERE / 'e007_metrics.patch'} ({len(patch.splitlines())} lines)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
