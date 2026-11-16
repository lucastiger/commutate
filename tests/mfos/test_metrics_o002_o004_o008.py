"""mfos.metrics functions for the criteria of O002, O004 and O008 (approved 2026-11-16), checked against hand-computed
cases, the existing functions they extend, and E010's measured tiny-step pair sequences."""
import math

import numpy as np
import pytest

from mfos import metrics as mx


# ------------------------------------------------------------------------------------------------ step floor
def test_a_sequence_with_both_steps_below_the_floor_counts_as_converged():
    # E010 2R pair differences (research/notes/o002-reference-convergence.md): steps 0.0002 then -0.0013 K;
    # gci_capped calls this divergent (|rho| >= 1), the floor rule gives 3 max|d|
    f = (1.0, 1.0002, 0.9989)
    assert mx.gci_capped(*f) == math.inf
    assert mx.gci_step_floor(*f, step_floor=0.01) == pytest.approx(3 * 0.0013, abs=1e-12)
    assert mx.gci_step_floor(*f, step_floor=0.0) == math.inf  # no floor: gci_capped's verdict


def test_above_the_floor_the_rule_is_gci_capped_and_never_below_three_times_the_step():
    f = (10.0, 10.4, 10.5)  # rho = 0.25, monotone convergence
    assert mx.gci_step_floor(*f, step_floor=0.01) == pytest.approx(mx.gci_capped(*f), abs=1e-15)
    g = (2.0, 2.0006, 2.0009)  # both steps below 1e-3: 3 max|d|, while gci_capped's own floor would give 0
    assert mx.gci_step_floor(*g, step_floor=1e-3) == pytest.approx(3 * 0.0006, abs=1e-15)
    assert mx.gci_capped(*g, floor=1e-3) == 0.0
    h = (5.0, 5.00001, 5.2)  # one tiny step and one large: not converged, gci_capped decides (+inf)
    assert mx.gci_step_floor(*h, step_floor=1e-3) == math.inf
    with pytest.raises(ValueError):
        mx.gci_step_floor(*f, step_floor=-1.0)


def test_a_relative_floor_scales_with_the_value():
    # O004: ratio steps below 0.1 % of the ratio; P3's trace-width ratio sequence (steps 7.1e-5, 2.5e-4)
    r = (0.969067, 0.969138, 0.969390)
    assert mx.gci_capped(*r) == math.inf
    assert mx.gci_step_floor(*r, step_floor=1e-3, relative=True) == pytest.approx(3 * (0.969390 - 0.969138), rel=1e-9)
    assert mx.gci_step_floor(*r, step_floor=1e-5, relative=True) == math.inf  # floor 9.7e-6: both steps above
    rows = [{"a": r[0], "b": r[1], "c": r[2]}, {"a": 10.0, "b": 10.4, "c": 10.5}]
    got = mx.compute("max_gci_step_floor", rows, params={"levels": ["a", "b", "c"], "step_floor": 1e-3,
                                                         "relative": True})
    assert got == pytest.approx(max(3 * (0.969390 - 0.969138), mx.gci_capped(10.0, 10.4, 10.5)), rel=1e-9)


# ------------------------------------------------------------------------------------------------ O008
def _draws(layout, shortfalls, role="search", b=0.005, capped=False):
    return [{"layout": layout, "draw": j, "role": role, "s": s, "b": b, "capped": capped}
            for j, s in enumerate(shortfalls)]


def test_o008_a1_takes_the_worst_layout_and_k1_the_worst_median():
    rows = _draws("2R", [0.0, 0.01, 0.03, -0.01]) + _draws("Case4", [0.0, 0.0, 0.02, 0.025])
    # 2R passes 3 of 4 (0.03 fails); Case4 passes 3 of 4 (0.02 sits on the line and passes, 0.025 fails)
    assert mx.control_layout_pass_min(rows, tol=0.02) == pytest.approx(0.75)
    assert mx.control_layout_pass_min(_draws("x", [0.02, 0.0200001]), tol=0.02) == pytest.approx(0.5)
    assert mx.compute("control_layout_pass_min", rows, pred="s", group="layout", params={"tol": 0.02}) == \
        mx.control_layout_pass_min(rows, tol=0.02)
    # medians: 2R (0.0 + 0.01) / 2 = 0.005; Case4 (0.0 + 0.02) / 2 = 0.01
    assert mx.control_shortfall_median_max(rows) == pytest.approx(0.01)


def _o008_rows(null_s, null_b=0.004, capped=False, n=8):
    rows = _draws("2R", [0.0] * n, b=0.005)
    rows += _draws("2R", [null_s] * n, role="compact", b=null_b, capped=capped)
    rows += _draws("2R", [0.20] * n, role="widen", b=0.004)
    return rows


def test_o008_a3_a_null_is_beaten_only_if_it_fails_resolvably_and_loses_the_paired_comparison():
    nulls = ["compact", "widen"]
    # compaction at +6 %: resolved (0.06 - 0.004 > 0.02) on 8 of 8, paired (0.06 > 0.005 + 0.004) on 8 of 8
    assert mx.null_beaten_min(_o008_rows(0.06), nulls=nulls) == 1.0
    # compaction at +2.3 %: within its band of the line (0.023 - 0.004 = 0.019 <= 0.02), never resolved
    assert mx.null_beaten_min(_o008_rows(0.023), nulls=nulls) == 0.0
    # a null that stopped at its step limit never counts as a resolved failure
    assert mx.null_beaten_min(_o008_rows(0.06, capped=True), nulls=nulls, capped="capped") == 0.0
    assert mx.null_beaten_min(_o008_rows(0.06, capped=True), nulls=nulls) == 1.0  # flag ignored when not named
    # the paired leg alone can fail: a null that fails resolvably but the search is no better by both bands
    rows = _draws("2R", [0.05] * 8, b=0.01) + _draws("2R", [0.06] * 8, role="compact", b=0.01) + \
        _draws("2R", [0.20] * 8, role="widen", b=0.004)
    assert mx.null_beaten_min(rows, nulls=nulls) == 0.0  # 0.06 - 0.05 = 0.01 is not > 0.01 + 0.01
    got = mx.compute("null_beaten_min", _o008_rows(0.06), pred="s", group="layout", role="role",
                     params={"nulls": nulls, "draw": "draw", "b": "b", "tol": 0.02, "k_resolved": 4, "k_paired": 7})
    assert got == 1.0


def test_o008_a3_takes_the_minimum_over_layouts_and_refuses_unpaired_rows():
    nulls = ["compact", "widen"]
    good = _o008_rows(0.06)
    bad = [{**r, "layout": "Case4"} for r in _o008_rows(0.0)]  # on Case4 compaction recovers the target
    assert mx.null_beaten_min(good + bad, nulls=nulls) == 0.0
    with pytest.raises(ValueError, match="has no 'widen' row"):
        mx.null_beaten_min([r for r in good if not (r["role"] == "widen" and r["draw"] == 3)], nulls=nulls)
    with pytest.raises(ValueError, match="duplicate row"):
        mx.null_beaten_min(good + good[:1], nulls=nulls)
    with pytest.raises(ValueError):
        mx.null_beaten_min(good, nulls=[])


# ------------------------------------------------------------------------------------------------ O004
def test_o004_a1_counts_an_excluded_pair_as_not_met():
    pred, ref = [0.90, 0.80], [0.91, 0.79]
    assert mx.max_rel_err_or_inf(pred, ref, [False, False]) == pytest.approx(mx.max_rel_err(pred, ref))
    assert mx.max_rel_err_or_inf(pred, ref, [False, True]) == math.inf
    rows = [{"r_l2": 0.90, "r_fh": 0.91, "excl": 0}, {"r_l2": 0.80, "r_fh": 0.79, "excl": 0}]
    assert mx.compute("max_rel_err_or_inf", rows, pred="r_l2", ref="r_fh", params={"excluded": "excl"}) == \
        pytest.approx(abs(0.80 / 0.79 - 1))


def test_o004_a2_is_a_capped_consistency_check():
    # |22.0 - 22.5| / (0.4 + 0.6) = 0.5; caps of 5 % of L are not exceeded
    assert mx.max_consistency_capped([22.0], [22.5], [0.4], [0.6], cap_rel=0.05) == pytest.approx(0.5)
    # a wide FastHenry estimate (11 % of L, as P4's two-level one) is unresolved, never easier to meet
    assert mx.max_consistency_capped([22.0], [22.5], [0.4], [2.5], cap_rel=0.05) == math.inf
    assert mx.max_consistency_capped([22.0], [22.5], [0.4], [math.inf], cap_rel=0.05) == math.inf
    assert mx.max_consistency_capped([22.0], [22.0], [0.0], [0.0], cap_rel=0.05) == 0.0
    assert mx.max_consistency_capped([22.0], [22.1], [0.0], [0.0], cap_rel=0.05) == math.inf
    rows = [{"l2": 22.0, "fh": 22.5, "e2": 0.4, "ef": 0.6}]
    assert mx.compute("max_consistency_capped", rows, pred="l2", ref="fh",
                      params={"e_pred": "e2", "e_ref": "ef", "cap_rel": 0.05}) == pytest.approx(0.5)


# ------------------------------------------------------------------------------------------------ O002
def test_o002_quantiles_ratio_and_median_match_numpy():
    rng = np.random.default_rng(7)
    ref = rng.normal(60.0, 5.0, 200)
    pred = ref + rng.normal(0.0, 0.3, 200)
    null = np.full(200, ref.mean())
    scale = rng.uniform(25.0, 47.0, 200)
    assert mx.quantile_abs_err(pred, ref) == pytest.approx(np.quantile(np.abs(pred - ref), 0.95), rel=1e-12)
    assert mx.quantile_rel_err(pred, ref, scale, q=0.9) == \
        pytest.approx(np.quantile(np.abs(pred - ref) / scale, 0.9), rel=1e-12)
    assert mx.quantile_abs_err_ratio(pred, null, ref) == pytest.approx(
        np.quantile(np.abs(pred - ref), 0.95) / np.quantile(np.abs(null - ref), 0.95), rel=1e-12)
    assert mx.quantile_abs_err_ratio(ref, ref, ref) == 0.0
    assert mx.quantile_abs_err_ratio(pred, ref, ref) == math.inf
    assert mx.median_col([3.0, 1.0, 2.0, 10.0]) == pytest.approx(2.5)
    with pytest.raises(ValueError):
        mx.quantile_rel_err(pred, ref, np.zeros(200))


def test_o002_pairwise_error_skips_pairs_of_the_same_layout():
    # two copies of layout "a" (as a cluster bootstrap draws them) would add a zero-error self-pair
    pred, ref, strata = [1.0, 1.0, 2.5], [1.0, 1.0, 2.0], ["s", "s", "s"]
    with_self = mx.pairwise_diff_error_quantile(pred, ref, strata, q=0.0)
    assert with_self == 0.0  # the self-pair (a, a) has zero error
    no_self = mx.pairwise_diff_error_quantile(pred, ref, strata, q=0.0, units=["a", "a", "b"])
    assert no_self == pytest.approx(0.5)  # only the (a, b) pairs: |(1 - 2.5) - (1 - 2)| = 0.5
    rows = [{"p": p, "r": r, "st": s, "lay": u} for p, r, s, u in zip(pred, ref, strata, ["a", "a", "b"], strict=True)]
    assert mx.compute("pairwise_diff_error_quantile", rows, pred="p", ref="r", strata=["st"],
                      params={"q": 0.0, "unit": "lay"}) == pytest.approx(0.5)
    assert mx.compute("pairwise_diff_error_quantile", rows, pred="p", ref="r", strata=["st"],
                      params={"q": 0.0}) == 0.0  # unchanged without "unit"


def test_o002_max_over_load_levels():
    rows = [{"load": "P_ref", "p": 1.0, "r": 1.2}, {"load": "P_ref", "p": 2.0, "r": 2.0},
            {"load": "half", "p": 1.0, "r": 1.05}, {"load": "half", "p": 3.0, "r": 3.0}]
    got = mx.compute("max_over_groups", rows, pred="p", ref="r",
                     params={"fn": "quantile_abs_err", "by": "load", "inner": {"q": 1.0}})
    assert got == pytest.approx(0.2)  # P_ref's max error 0.2 against half's 0.05
    with pytest.raises(ValueError):
        mx.compute("max_over_groups", rows, pred="p", ref="r", params={"fn": "max_over_groups", "by": "load"})


def test_every_new_function_is_registered():
    for name in ("max_gci_step_floor", "control_layout_pass_min", "control_shortfall_median_max", "null_beaten_min",
                 "max_rel_err_or_inf", "max_consistency_capped", "quantile_abs_err", "quantile_rel_err",
                 "quantile_abs_err_ratio", "median_col", "max_over_groups"):
        assert name in mx.METRICS
