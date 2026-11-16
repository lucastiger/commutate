"""Analytic tests for E011's acceptance metrics (O008 A1, A2, A3, K1; F7), draft for the founder's mfos.metrics port.

T0381. Tests the reference implementation in experiments/runners/e011_metrics.py (imported by path) and checks that
mfos.metrics, called through the evaluator's own path (``mfos.evaluate.metric_value`` on ``_where``-filtered rows with
the RecomputeSpecs below), gives the same numbers. Verdict logic is the objective's pass_all / fail_any as written in
project/objectives/O008/objective.yaml, judged with ``mfos.evaluate.judge``.
"""
from __future__ import annotations

import importlib.util
import math
from pathlib import Path

import numpy as np
import pytest
import yaml
from scipy import stats as st

from mfos import evaluate as ev
from mfos import models as m

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("e011_metrics_t0381", ROOT / "experiments" / "runners" / "e011_metrics.py")
em = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(em)

TOL = 0.02
# The recompute entries E011's spec should declare (column names as in e011_metrics' row schema).
RECOMPUTE = {
    "control_layout_pass_min": m.RecomputeSpec(
        metric="control_layout_pass_min", fn="control_layout_pass_min", pred="s", group="layout",
        where={"role": "search", "counted": True}, params={"tol": TOL}),
    "reach_outside_max": m.RecomputeSpec(metric="reach_outside_max", fn="max_col", pred="reach_outside"),
    "null_beaten_min": m.RecomputeSpec(
        metric="null_beaten_min", fn="null_beaten_min", pred="s", group="layout", role="role",
        where={"counted": True},
        params={"nulls": ["widen", "compact"], "search": "search", "draw": "draw", "b": "b", "capped": "capped",
                "tol": TOL, "k_resolved": 4, "k_paired": 7}),
    "control_shortfall_median_max": m.RecomputeSpec(
        metric="control_shortfall_median_max", fn="control_shortfall_median_max", pred="s", group="layout",
        where={"role": "search", "counted": True}),
}


# ------------------------------------------------------------------------------------------------ row builders
def _draws(s, b=0.004, capped=False, n=8):
    s = list(s) if isinstance(s, (list, tuple)) else [s] * n
    b = list(b) if isinstance(b, (list, tuple)) else [b] * len(s)
    c = list(capped) if isinstance(capped, (list, tuple)) else [capped] * len(s)
    return list(zip(s, b, c, strict=True))


def _layout(counted=True, in_domain=True, **roles):
    base = {"search": _draws(0.005), "seed": _draws(0.30), "widen": _draws(0.10, 0.005),
            "compact": _draws(0.08, 0.005), "random_screen": _draws(0.15), "proxy_alone": _draws(0.01)}
    base.update(roles)
    return {"counted": counted, "in_domain": in_domain, "roles": base}


def _rows(layouts):
    rows = []
    for lay, spec in layouts.items():
        for role, draws in spec["roles"].items():
            for j, (s, b, cap) in enumerate(draws):
                kind = ("seed" if role == "seed" else "no_candidate" if s is None
                        else ("budget" if role == "search" else "step_limit") if cap else "local_optimum")
                rows.append({"layout": lay, "counted": spec["counted"], "draw": j, "role": role, "s": s, "b": b,
                             "capped": cap, "terminal_kind": kind, "in_domain_W": spec["in_domain"],
                             "reach_outside": 0.0 if spec["in_domain"] else 1.0})
    return rows


def _two(**case4_roles):
    return _rows({"2D_Case_2R": _layout(), "2D_Case_4": _layout(**case4_roles),
                  "gen2_0": _layout(counted=False, search=_draws(0.5))})


def _mine(rows):
    return {"control_layout_pass_min": em.control_layout_pass_min(rows), "reach_outside_max": em.reach_outside_max(rows),
            "null_beaten_min": em.null_beaten_min(rows),
            "control_shortfall_median_max": em.control_shortfall_median_max(rows)}


def _theirs(rows):
    return {k: ev.metric_value(rc, ev._where(rows, rc.where), rc.pred).value for k, rc in RECOMPUTE.items()}


def _objective():
    return m.Objective.model_validate(yaml.safe_load((ROOT / "project/objectives/O008/objective.yaml").read_text()))


def _verdict(values):
    """mfos.evaluate.evaluate's combination, no validity problems: FAIL > PASS > INCONCLUSIVE, criteria from O008."""
    acc = _objective().acceptance
    mv = {f"E011.{k}": m.MetricValue(value=v) for k, v in values.items()}
    p = [ev.judge(c, mv.get(c.metric), as_fail=False).verdict for c in acc.pass_all]
    f = [ev.judge(c, mv.get(c.metric), as_fail=True).verdict for c in acc.fail_any]
    assert "missing" not in p + f, "a criterion's metric is not produced"
    v = "FAIL" if "satisfied" in f else "PASS" if all(x == "satisfied" for x in p) else "INCONCLUSIVE"
    assert em.verdict(values={f"E011.{k}": x for k, x in values.items()}, pass_all=acc.pass_all,
                      fail_any=acc.fail_any) == v
    return v


# ------------------------------------------------------------------------------------------------ A1
@pytest.mark.parametrize("k, expected, meets", [(8, 1.0, True), (7, 0.875, True), (6, 0.75, False)])
def test_a1_seven_and_six_of_eight(k, expected, meets):
    rows = _two(search=_draws([0.005] * k + [0.10] * (8 - k)))
    v = em.control_layout_pass_min(rows)
    assert v == expected and (v >= 0.875) is meets
    assert _theirs(rows)["control_layout_pass_min"] == v


def test_a1_is_min_over_counted_layouts_only():
    rows = _rows({"A": _layout(search=_draws([0.005] * 7 + [0.1])), "B": _layout(search=_draws([0.005] * 6 + [0.1] * 2)),
                  "gen2_0": _layout(counted=False, search=_draws(0.5))})
    assert em.control_layout_pass_min(rows) == 0.75  # B, not the uncounted gen2_0 at 0/8
    assert em.layout_pass_counts(rows) == {"A": 7, "B": 6}


def test_s_exactly_at_tol_passes_and_next_float_fails():
    above = math.nextafter(TOL, 1.0)
    rows = _two(search=_draws([TOL] * 7 + [above], b=0.0))
    assert em.layout_pass_counts(rows)["2D_Case_4"] == 7
    rows = _two(search=_draws([TOL] * 6 + [above] * 2, b=0.0))
    assert em.control_layout_pass_min(rows) == 0.75 == _theirs(rows)["control_layout_pass_min"]


def test_conservative_count_and_unresolved_count():
    # s = 0.02 exactly: point pass; conservative pass only with b = 0; within band iff b > 0 (strict <)
    s = [TOL, TOL, 0.015, 0.015, 0.025, 0.0, 0.0, 0.0]
    b = [0.0, 0.004, 0.004, 0.006, 0.006, 0.004, 0.004, 0.004]
    rows = _two(search=_draws(s, b))
    assert em.layout_pass_counts(rows)["2D_Case_4"] == 7
    assert em.layout_pass_counts(rows, conservative=True)["2D_Case_4"] == 5  # 0.02+0, 0.015+0.004, three zeros
    assert em.control_layout_pass_min_conservative(rows) == 5 / 8
    # |s - 0.02| < b: draw 1 (0 < .004), 2 (.005 < .004 no), 3 (.005 < .006), 4 (.005 < .006); draw 0 (0 < 0 no)
    assert em.unresolved_counts(rows)["2D_Case_4"] == 3
    assert set(em.unresolved_counts(rows)) == {"2D_Case_2R", "2D_Case_4", "gen2_0"}


# ------------------------------------------------------------------------------------------------ A3
@pytest.mark.parametrize("n_res, beaten", [(4, True), (3, False)])
def test_a3_four_of_eight_resolved(n_res, beaten):
    # unresolved draws: s - b = 0.02 exactly is not > tol; paired margin still clear on every draw
    s = [0.10] * n_res + [0.03] * (8 - n_res)
    b = [0.005] * n_res + [0.01] * (8 - n_res)
    rows = _two(compact=_draws(s, b), search=_draws(0.0, 0.004))
    t = em.null_beaten_table(rows)[("2D_Case_4", "compact")]
    assert (t["resolved"], t["paired"], t["beaten"]) == (n_res, 8, beaten)
    assert em.null_beaten_min(rows) == float(beaten) == _theirs(rows)["null_beaten_min"]


@pytest.mark.parametrize("n_capped, beaten", [(4, True), (5, False)])
def test_capped_null_is_not_a_resolved_failure(n_capped, beaten):
    rows = _two(widen=_draws(0.10, 0.005, capped=[True] * n_capped + [False] * (8 - n_capped)))
    t = em.null_beaten_table(rows)[("2D_Case_4", "widen")]
    assert t["resolved"] == 8 - n_capped and t["paired"] == 8  # capped draws still count as paired wins
    assert em.null_beaten_min(rows) == float(beaten) == _theirs(rows)["null_beaten_min"]


def test_a3_capped_requires_the_capped_param():
    """Without params.capped mfos.metrics counts capped runs as resolved failures, so E011's spec must set it."""
    rows = _two(widen=_draws(0.10, 0.005, capped=[True] * 5 + [False] * 3))
    rc = RECOMPUTE["null_beaten_min"]
    no_cap = rc.model_copy(update={"params": {k: v for k, v in rc.params.items() if k != "capped"}})
    assert ev.metric_value(no_cap, ev._where(rows, rc.where), rc.pred).value == 1.0  # wrong: capped counted
    assert _theirs(rows)["null_beaten_min"] == em.null_beaten_min(rows) == 0.0


def test_paired_margin_uses_both_bands():
    # dyadic values, exact in float64: diff 2^-4; each band 2^-5, either alone < diff, their sum == diff -> no win
    d, h = 2.0 ** -4, 2.0 ** -5
    s_null = [d] * 8
    b_null = [h, h] + [h - 2.0 ** -10] * 6
    rows = _two(search=_draws(0.0, h), compact=_draws(s_null, b_null))
    t = em.null_beaten_table(rows)[("2D_Case_4", "compact")]
    assert t["resolved"] == 8  # d - h = 2^-5 > 0.02
    assert t["paired"] == 6 and not t["beaten"]  # 6 of 8: a one-band margin would give 8
    assert em.null_beaten_min(rows) == 0.0 == _theirs(rows)["null_beaten_min"]
    b_null[1] = h - 2.0 ** -10  # 7 of 8
    rows = _two(search=_draws(0.0, h), compact=_draws(s_null, b_null))
    assert em.null_beaten_table(rows)[("2D_Case_4", "compact")]["paired"] == 7
    assert em.null_beaten_min(rows) == 1.0 == _theirs(rows)["null_beaten_min"]


# ------------------------------------------------------------------------------------------------ K1
@pytest.mark.parametrize("mid, expected, fires", [((0.04, 0.07), 0.055, True), ((0.03, 0.06), 0.045, False)])
def test_k1_median_of_even_count(mid, expected, fires):
    # lower middle and upper middle disagree with the mean of the two in both cases: discriminates the definition
    s = [0.0, 0.01, 0.02, mid[0], mid[1], 0.08, 0.09, 0.10]
    rows = _two(search=_draws(s))
    v = em.control_shortfall_median_max(rows)
    assert v == pytest.approx(expected, abs=1e-15) and (v > 0.05) is fires
    assert _theirs(rows)["control_shortfall_median_max"] == v
    assert _verdict({**_mine(rows)}) == ("FAIL" if fires else "INCONCLUSIVE")  # A1 3/8 not met either way


# ------------------------------------------------------------------------------------------------ verdicts
def test_null_recovers_on_one_layout_gives_inconclusive():
    """F7's case: compaction recovers W* on Case 4 (no resolved failure) and fails on 2R; the search passes 8/8."""
    rows = _two(compact=_draws(0.012, 0.004))  # 2R keeps the default failing compaction (0.08 +- 0.005)
    tab = em.null_beaten_table(rows)
    assert tab[("2D_Case_2R", "compact")]["beaten"] and not tab[("2D_Case_4", "compact")]["beaten"]
    vals = _mine(rows)
    assert vals == {"control_layout_pass_min": 1.0, "reach_outside_max": 0.0, "null_beaten_min": 0.0,
                    "control_shortfall_median_max": 0.005}
    assert _theirs(rows) == vals
    assert _verdict(vals) == "INCONCLUSIVE"


def test_all_met_gives_pass_and_reach_outside_gives_inconclusive():
    rows = _two()
    assert _theirs(rows) == _mine(rows)
    assert _verdict(_mine(rows)) == "PASS"
    out = _rows({"2D_Case_2R": _layout(in_domain=False), "2D_Case_4": _layout(),
                 "gen2_0": _layout(counted=False, in_domain=False)})
    assert em.reach_outside_max(out) == 1.0 == _theirs(out)["reach_outside_max"]
    assert _verdict(_mine(out)) == "INCONCLUSIVE"
    # A2 ranges over every development layout, counted or not
    only_dev = _rows({"2D_Case_2R": _layout(), "gen2_0": _layout(counted=False, in_domain=False)})
    assert em.reach_outside_max(only_dev) == 1.0 == _theirs(only_dev)["reach_outside_max"]


def test_seed_null_meeting_a1_is_detected():
    ok, v = em.seed_null_check(_two())
    assert ok and v == 0.0
    # defect: the seed's s taken against D_j instead of W* (0 by construction) -> the seed meets A1 -> INVALID (F1)
    bad = _rows({"2D_Case_2R": _layout(seed=_draws(0.0)), "2D_Case_4": _layout(seed=_draws(0.0))})
    ok, v = em.seed_null_check(bad)
    assert not ok and v == 1.0
    rc = RECOMPUTE["control_layout_pass_min"]
    seed_rc = rc.model_copy(update={"where": {"role": "seed", "counted": True}})
    assert ev.metric_value(seed_rc, ev._where(bad, seed_rc.where), "s").value == 1.0


# ------------------------------------------------------------------------------------------------ reported bounds
@pytest.mark.parametrize("n", [1, 8, 16])
def test_clopper_pearson_all_pass_closed_form(n):
    assert em.clopper_pearson_lower(n, n) == pytest.approx(0.05 ** (1.0 / n), rel=1e-12)


@pytest.mark.parametrize("k, n", [(1, 8), (7, 8), (15, 16), (10, 16)])
def test_clopper_pearson_defining_equation(k, n):
    p = em.clopper_pearson_lower(k, n)
    assert st.binom.sf(k - 1, n, p) == pytest.approx(0.05, rel=1e-9)  # P(X >= k | p_L) = alpha
    lo, hi = em.clopper_pearson_interval(k, n, 0.95)
    assert st.binom.sf(k - 1, n, lo) == pytest.approx(0.025, rel=1e-9)
    assert st.binom.cdf(k, n, hi) == pytest.approx(0.025, rel=1e-9)
    assert em.clopper_pearson_lower(0, n) == 0.0 and em.clopper_pearson_interval(n, n)[1] == 1.0


def test_pooled_bound_and_layout_intervals():
    rows = _two(search=_draws([0.005] * 7 + [0.1]))
    k, n, p = em.pooled_pass_lower_bound(rows)
    assert (k, n) == (15, 16) and p == pytest.approx(em.clopper_pearson_lower(15, 16))
    iv = em.layout_pass_intervals(rows)  # Bonferroni over 2 counted layouts: 97.5 % each
    assert set(iv) == {"2D_Case_2R", "2D_Case_4"}
    assert iv["2D_Case_4"][1:] == pytest.approx(em.clopper_pearson_interval(7, 8, 0.975))


@pytest.mark.parametrize("p, one, two", [(0.95, 0.94, 0.89), (0.90, 0.81, 0.66), (0.85, 0.66, 0.43),
                                         (0.70, 0.26, 0.07)])
def test_objective_operating_characteristic(p, one, two):
    """The figures in O008 A1's description: P(Bin(8, p) >= 7), per layout and squared for two layouts."""
    assert em.a1_operating_characteristic(p) == pytest.approx(p ** 8 + 8 * p ** 7 * (1 - p), rel=1e-12)
    assert round(em.a1_operating_characteristic(p), 2) == one
    assert round(em.a1_operating_characteristic(p, 2), 2) == two


# ------------------------------------------------------------------------------------------------ schema
@pytest.mark.parametrize("mutate, msg", [
    (lambda r: r[0].update(capped="false"), "capped must be a bool"),
    (lambda r: r[0].update(reach_outside=0.0, in_domain_W=False), "differ within layout|reach_outside"),
    (lambda r: r[0].pop("capped"), "missing columns"),
    (lambda r: r.append(dict(r[0])), "duplicate draw"),
    (lambda r: r[0].update(role="random"), "role must be"),
    (lambda r: r[0].update(b=-0.001), "b must be finite"),
    (lambda r: r[0].update(terminal_kind="step_limit", capped=False), "capped false"),
    (lambda r: r.pop(0), "search draws|differ from search"),
])
def test_schema_violations_raise(mutate, msg):
    rows = _two()
    mutate(rows)
    with pytest.raises(ValueError, match=msg):
        em.validate_rows(rows)


def test_no_candidate_draw_fails_without_voiding():
    rows = _two(search=_draws([None] + [0.005] * 7, [None] + [0.004] * 7))
    assert em.control_layout_pass_min(rows) == 0.875
    assert math.isfinite(em.control_shortfall_median_max(rows))


# ------------------------------------------------------------------------------------------------ agreement
def _random_rows(rng):
    pool = [0.0, TOL, math.nextafter(TOL, 1.0), math.nextafter(TOL, 0.0), 0.03, 0.05]
    layouts = {}
    for li in range(int(rng.integers(1, 4))):
        roles = {}
        for role in em.ROLES:
            s = [float(rng.choice(pool)) if rng.random() < 0.3 else float(rng.uniform(0.0, 0.12)) for _ in range(8)]
            b = [0.0 if rng.random() < 0.1 else float(rng.uniform(0.0, 0.02)) for _ in range(8)]
            cap = [bool(rng.random() < 0.3) for _ in range(8)]
            roles[role] = list(zip(s, b, cap, strict=True))
        layouts[f"L{li}"] = {"counted": li == 0 or bool(rng.random() < 0.7), "in_domain": bool(rng.random() < 0.8),
                             "roles": roles}
    if rng.random() < 0.5:  # skew some sets towards beaten nulls so both A3 outcomes occur
        for lay in layouts.values():
            lay["roles"]["search"] = [(x * 0.1, y * 0.2, c) for x, y, c in lay["roles"]["search"]]
    return _rows(layouts)


def test_agrees_with_mfos_metrics_on_random_rows():
    rng = np.random.default_rng(20261116)
    seen = {k: set() for k in RECOMPUTE}
    for _ in range(400):
        rows = _random_rows(rng)
        mine, theirs = _mine(rows), _theirs(rows)
        assert mine == theirs, (mine, theirs)
        for k, v in mine.items():
            seen[k].add(v)
    # the sample exercises both outcomes of every indicator and several A1 levels (diversity of the comparison)
    assert seen["null_beaten_min"] == {0.0, 1.0} and seen["reach_outside_max"] == {0.0, 1.0}
    assert len(seen["control_layout_pass_min"]) >= 5 and len(seen["control_shortfall_median_max"]) >= 100


@pytest.mark.xfail(strict=False, reason="T0381 report: mfos.metrics K1 lets one NaN draw mask another layout")
def test_k1_nan_draw_does_not_mask_another_layout():
    rows = _rows({"A": _layout(search=_draws([math.nan] + [0.005] * 7, [math.nan] + [0.004] * 7)),
                  "B": _layout(search=_draws(0.10))})
    assert em.control_shortfall_median_max(rows) == pytest.approx(0.10)  # A: median 0.005 (NaN as +inf); B: 0.10
    assert _theirs(rows)["control_shortfall_median_max"] == pytest.approx(0.10)


@pytest.mark.xfail(strict=False, reason="T0381 report: mfos.metrics counts a null's s = inf as a resolved failure")
def test_null_without_candidate_is_not_a_resolved_failure():
    # 5 draws with no candidate written as s = inf (finite b); 3 unresolved draws (0.03 - 0.01 < 0.02) that are paired
    # wins. As resolved failures the inf draws would make the null beaten (5 resolved, 8 paired)
    rows = _two(widen=_draws([math.inf] * 5 + [0.03] * 3, [0.004] * 5 + [0.01] * 3))
    t = em.null_beaten_table(rows)[("2D_Case_4", "widen")]
    assert (t["resolved"], t["paired"]) == (0, 3) and em.null_beaten_min(rows) == 0.0
    assert _theirs(rows)["null_beaten_min"] == 0.0


@pytest.mark.xfail(strict=False, reason="T0381 report: mfos.metrics averages over the draws present, not over 8")
def test_counted_layout_with_a_dropped_draw_is_rejected():
    # draw 7 dropped from every role on a counted layout (F6 would exclude the layout instead)
    rows = [r for r in _two(search=_draws([0.005] * 7 + [0.10])) if not (r["layout"] == "2D_Case_4" and r["draw"] == 7)]
    with pytest.raises(ValueError, match="7 search draws"):
        em.control_layout_pass_min(rows)
    with pytest.raises(ValueError):
        _theirs(rows)  # mfos.metrics returns A1 = 7/7 = 1.0 here
