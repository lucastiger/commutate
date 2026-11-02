"""mfos.metrics: the evaluator's own metric implementations, checked against scipy, hand-computed cases, mfos.stats,
and regression anchors recomputed from O001/E002's committed artifacts (audit 2026-10-19)."""
import json
import math
from pathlib import Path

import numpy as np
import pytest
from scipy import stats as st

from mfos import metrics as mx
from mfos import stats as legacy

REPO = Path(__file__).resolve().parents[2]
E002 = REPO / "experiments" / "results" / "E002" / "E002-20261016T054426-b69a"


def test_spearman_matches_scipy_and_the_legacy_definition():
    rng = np.random.default_rng(1)
    x = rng.normal(size=50)
    y = x + rng.normal(size=50)
    y[:5] = y[0]  # ties
    assert mx.spearman(x, y) == pytest.approx(st.spearmanr(x, y).statistic, abs=1e-12)
    assert mx.spearman(x, y) == pytest.approx(legacy.spearman(x, y), abs=1e-14)
    assert mx.spearman([1, 2, 3], [5, 5, 5]) == 0.0  # constant ranks: 0, as mfos.stats
    with pytest.raises(ValueError):
        mx.spearman([1, 2], [1, 2])


def test_simple_metrics_by_hand():
    assert mx.mape([1.1, 0.9], [1.0, 1.0]) == pytest.approx(0.1)
    assert mx.mean_signed_rel_err([1.1, 0.8], [1.0, 1.0]) == pytest.approx(-0.05)
    assert mx.max_rel_err([1.1, 0.8], [1.0, 1.0]) == pytest.approx(0.2)
    assert mx.max_abs_err([1.5, 0.8], [1.0, 1.0]) == pytest.approx(0.5)
    assert mx.kendall_tau([1, 2, 3, 4], [1, 3, 2, 4]) == pytest.approx(st.kendalltau([1, 2, 3, 4], [1, 3, 2, 4]).statistic)
    assert mx.kendall_tau([1, 2, 3], [7, 7, 7]) == 0.0
    ref = np.arange(1.0, 101.0)
    assert mx.topk_recall(ref, ref) == 1.0 == legacy.topk_recall(ref, ref)
    assert mx.topk_recall(ref[::-1].copy(), ref) == 0.0


def test_stratum_and_pair_metrics_by_hand():
    pred, ref = [1.0, 2.0, 10.0, 12.0], [1.0, 2.2, 11.0, 10.5]
    strata = ["a", "a", "b", "b"]
    # pairs: (0,1) gap 1.2 concordant; (2,3) gap 0.0476 discordant; cross pairs all large gaps, concordant
    assert mx.discordance_by_gap(pred, ref, (0.0, 0.05, math.inf)) == [(1, 1), (5, 0)]
    assert mx.discordance_rate(pred, ref, 0.0, 0.05) == 1.0
    # group a: argmin pred = 0 -> ref 1.0 = min, regret 0; group b: argmin pred = 2 -> 11.0 vs min 10.5
    assert mx.group_selection_regret(pred, ref, strata, agg="max") == pytest.approx(11.0 / 10.5 - 1)
    assert mx.group_selection_regret(pred, ref, strata) == pytest.approx((11.0 / 10.5 - 1) / 2)
    e = np.array(pred) / np.array(ref) - 1
    assert mx.stratum_mean_offset_spread(pred, ref, strata) == pytest.approx(e[2:].mean() - e[:2].mean())
    # within pairs: a: |(1-2)-(1-2.2)| = 0.2; b: |(10-12)-(11-10.5)| = 2.5
    assert mx.pairwise_diff_error_quantile(pred, ref, strata, q=1.0) == pytest.approx(2.5)
    assert mx.pairwise_diff_error_quantile(pred, ref, strata, q=0.0) == pytest.approx(0.2)


def test_selection_metrics_by_group_and_role():
    rows = [
        {"group": "P1", "role": "reference", "L1": 10.0, "L2": 11.0},
        {"group": "P1", "role": "selected", "L1": 7.0, "L2": 8.8},
        {"group": "P2", "role": "reference", "L1": 20.0, "L2": 22.0},
        {"group": "P2", "role": "selected", "L1": 16.0, "L2": 19.8},
    ]
    assert mx.headroom_by_group(rows, "L2", agg="min") == pytest.approx(1 - 19.8 / 22.0)
    assert mx.headroom_by_group(rows, "L2", agg="max") == pytest.approx(1 - 8.8 / 11.0)
    assert mx.optimism_ratio_by_group(rows, "L1", "L2", agg="min") == pytest.approx((22.0 - 19.8) / (20.0 - 16.0))
    assert mx.compute("headroom_by_group", rows, ref="L2", group="group", role="role",
                      params={"agg": "median"}) == pytest.approx(np.median([1 - 8.8 / 11, 1 - 19.8 / 22]))


def test_plain_bootstrap_reproduces_mfos_stats_exactly():
    rng = np.random.default_rng(0)
    x = rng.normal(size=60)
    y = x + 0.3 * rng.normal(size=60)
    rows = [{"p": a, "r": b} for a, b in zip(x, y, strict=True)]
    new = mx.bootstrap_ci(lambda rr: mx.compute("spearman", rr, pred="p", ref="r"), rows, n_boot=300, seed=3)
    old = legacy.bootstrap_ci(legacy.spearman, x, y, n_boot=300, seed=3)
    assert new[0] == pytest.approx(old[0], abs=1e-14)
    assert new[1] == pytest.approx(old[1], abs=1e-12)


def test_stratified_and_cluster_bootstraps_keep_their_structure():
    rows = [{"s": s, "v": float(i)} for i, s in enumerate("aaabbbbbcc")]
    seen = []

    def stat(rr):
        seen.append(sorted(r["s"] for r in rr))
        return float(np.mean([r["v"] for r in rr]))
    mx.bootstrap_ci(stat, rows, n_boot=20, seed=1, scheme="stratified", strata=["s"])
    assert all(x == sorted("aaabbbbbcc") for x in seen[1:])  # every resample keeps the stratum sizes
    seen.clear()
    mx.bootstrap_ci(stat, rows, n_boot=20, seed=1, scheme="cluster", cluster="s")
    assert all(set(x) <= set("abc") for x in seen)
    with pytest.raises(ValueError):
        mx.bootstrap_ci(stat, rows, scheme="stratified")


def test_null_columns():
    rows = [{"s": "a", "ref": 1.0, "n": 9.0}, {"s": "a", "ref": 3.0, "n": 8.0}, {"s": "b", "ref": 10.0, "n": 7.0}]
    assert mx.null_column(rows, "stratum_mean", "ref", ["s"]) == [2.0, 2.0, 10.0]
    assert mx.null_column(rows, "column", "ref", column="n") == [9.0, 8.0, 7.0]


# ------------------------------------------------------------------------------------------------ E002 anchors
@pytest.fixture(scope="module")
def e002_rows():
    rows = json.loads((E002 / "e002_rows.json").read_text())["rows"]
    ref = json.loads((E002 / "e002_reference.json").read_text())["per_layout"]
    assert [r["i"] for r in rows] == [p["i"] for p in ref]
    return [{"pred": r["L1_H"]["20000000.0"], "ref": p["L2_inf"], "family": r["family"], "dies": r["dies"]}
            for r, p in zip(rows, ref, strict=True)]


def test_e002_regression_anchors(e002_rows):
    """The values the audit recomputed independently from E002's committed artifacts (scipy) and that E002 reported."""
    rows = e002_rows
    pred = [r["pred"] for r in rows]
    ref = [r["ref"] for r in rows]
    strata = mx.strata_keys(rows, ["family", "dies"])
    assert mx.spearman(pred, ref) == pytest.approx(0.995851340, abs=1e-9)
    assert mx.mape(pred, ref) == pytest.approx(0.097161254, abs=1e-9)
    assert mx.topk_recall(pred, ref, 0.1, 0.2) == 1.0
    assert mx.within_strata_spearman(pred, ref, strata) == pytest.approx(0.976968350, abs=1e-9)
    null = mx.null_column(rows, "stratum_mean", "ref", ["family", "dies"])
    assert mx.spearman(null, ref) == pytest.approx(0.974771821, abs=1e-9)  # why O001's A2/A3 did not discriminate
    assert mx.discordance_by_gap(pred, ref) == [(160, 60), (233, 29), (370, 0), (3242, 0)]
    assert mx.group_selection_regret(pred, ref, strata) == pytest.approx(0.001319751, abs=1e-9)
    assert mx.group_selection_regret(pred, ref, strata, agg="max") == pytest.approx(0.010934818, abs=1e-9)
    point, ci = mx.bootstrap_ci(lambda rr: mx.compute("spearman", rr, pred="pred", ref="ref"), rows,
                                n_boot=2000, seed=20261008)
    recorded = json.loads((E002 / "result.json").read_text())["metrics"]["spearman_rho_Lloop"]
    assert point == pytest.approx(recorded["value"], abs=1e-12)
    assert ci == pytest.approx(tuple(recorded["ci"]), abs=1e-12)
    assert ci == pytest.approx((0.9897220464162575, 0.9975624829898619), abs=1e-12)


def test_o006_recompute_metrics_by_hand():
    """I0064 (2026-11-02): A1/K1, A3 and A4 of O006 need these to be recomputed from E006's rows."""
    assert mx.max_scaled_abs_err([1.1, 2.0], [1.0, 2.3], [5.0, 10.0]) == pytest.approx(0.03)  # max(0.1/5, 0.3/10)
    assert mx.max_abs_err_gated([1.0, 2.04], [1.02, 2.0], [0.01, 0.02], 0.025) == pytest.approx(0.04)
    assert mx.max_abs_err_gated([1.0, 2.04], [1.02, 2.0], [0.01, 0.03], 0.025) == math.inf  # gate missed: not met
    assert mx.max_col([0.004, 0.019, 0.011]) == pytest.approx(0.019)
    rows = [{"p": 1.1, "r": 1.0, "s": 5.0, "g": 0.01}, {"p": 2.0, "r": 2.3, "s": 10.0, "g": 0.02}]
    assert mx.compute("max_scaled_abs_err", rows, pred="p", ref="r", params={"scale": "s"}) == pytest.approx(0.03)
    assert mx.compute("max_abs_err_gated", rows, pred="p", ref="r",
                      params={"gate": "g", "gate_max": 0.025}) == pytest.approx(0.3)
    assert mx.compute("max_col", rows, pred="g") == pytest.approx(0.02)


@pytest.mark.parametrize("call", [
    lambda: mx.max_scaled_abs_err([], [], []),
    lambda: mx.max_scaled_abs_err([1.0], [math.nan], [1.0]),
    lambda: mx.max_scaled_abs_err([1.0], [1.0], [0.0]),
    lambda: mx.max_abs_err_gated([1.0], [1.0], [math.nan], 0.025),
    lambda: mx.max_col([]),
    lambda: mx.max_col([0.01, math.inf]),
])
def test_o006_recompute_metrics_fail_closed(call):
    with pytest.raises(ValueError):
        call()
