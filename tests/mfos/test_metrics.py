"""mfos.metrics: the evaluator's own metric implementations, checked against scipy, hand-computed cases, mfos.stats,
and regression anchors recomputed from O001/E002's committed artifacts (audit 2026-10-19)."""
import importlib.util
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


def test_o006_gci_capped_branches_by_hand():
    """D0013 (re-reviews T0184/T0185): every three-grid sequence has a defined, non-negative GCI."""
    assert mx.gci_capped(410.0, 410.0, 410.0) == 0.0
    assert mx.gci_capped(410.0, 410.25, 410.75) == math.inf  # growing steps (the literal D0012 formula gave a negative GCI)
    assert mx.gci_capped(410.0, 410.5, 411.0) == math.inf  # stagnant: p_obs = 0 (D0012 divided by zero)
    assert mx.gci_capped(410.0, 410.0, 410.5) == math.inf  # d1 = 0 < |d2|
    assert mx.gci_capped(410.0, 410.5, 410.0) == math.inf  # oscillating with equal amplitude: rho = -1
    assert mx.gci_capped(410.0, 410.3, 410.31) == pytest.approx(1.25 * 0.3 / 4)  # lucky grid, p_obs 4.9: order 2 from d1
    assert mx.gci_capped(410.0, 410.4, 410.2) == pytest.approx(3.0 * 0.4)  # oscillatory: Roache's Fs = 3
    assert mx.gci_capped(410.0, 410.4, 410.5) == pytest.approx(1.25 * 0.1)  # rho 1/4: p_obs 2, capped at 1
    assert mx.gci_capped(410.0, 410.4, 410.6) == pytest.approx(1.25 * 0.2)  # rho 1/2: p_obs 1, 2^1 - 1 = 1
    assert mx.gci_capped(410.0, 410.4, 410.7) == pytest.approx(1.25 * 0.3 / (4.0 / 3.0 - 1.0))  # rho 3/4, p_obs < 1
    # T0181 section 1, u_shaped_2 (seed 20261101), levels 0/1/2 = 422.718 / 422.088 / 421.766 K: p_obs 0.966
    rho = (421.766 - 422.088) / (422.088 - 422.718)
    assert mx.gci_capped(422.718, 422.088, 421.766) == pytest.approx(1.25 * 0.322 / (2.0 ** math.log2(1 / rho) - 1.0))
    assert mx.gci_capped(422.718, 422.088, 421.766) == pytest.approx(1.25 * 0.322 / (0.630 / 0.322 - 1.0), abs=1e-9)  # 0.4208 K
    # reversing the level order is a different (here divergent) sequence: the convention is coarsest first
    assert mx.gci_capped(421.766, 422.088, 422.718) == math.inf


def test_o006_gci_recompute_functions_by_hand():
    rows = [{"a0": 410.0, "a1": 410.4, "a2": 410.6, "b0": 410.9, "b1": 410.7, "b2": 410.65},
            {"a0": 300.0, "a1": 300.0, "a2": 300.0, "b0": 300.0, "b1": 300.0, "b2": 300.0}]
    assert mx.max_gci_capped([410.0, 300.0], [410.4, 300.0], [410.6, 300.0]) == pytest.approx(0.25)
    assert mx.compute("max_gci_capped", rows, params={"levels": ["a0", "a1", "a2"]}) == pytest.approx(0.25)
    g_b = 1.25 * 0.05  # rho 1/4 for b: p capped at 1
    assert mx.compute("max_gci_consistency", rows, params={"pred_levels": ["a0", "a1", "a2"],
                                                           "ref_levels": ["b0", "b1", "b2"]}) == pytest.approx(
        0.05 / (0.25 + g_b))
    diverging = rows + [{"a0": 1.0, "a1": 1.1, "a2": 1.3, "b0": 1.0, "b1": 1.0, "b2": 1.0}]
    assert mx.compute("max_gci_capped", diverging, params={"levels": ["a0", "a1", "a2"]}) == math.inf
    assert mx.compute("max_gci_consistency", diverging, params={"pred_levels": ["a0", "a1", "a2"],
                                                                "ref_levels": ["b0", "b1", "b2"]}) == math.inf
    exact_but_unequal = [{"a0": 1.0, "a1": 1.0, "a2": 1.0, "b0": 2.0, "b1": 2.0, "b2": 2.0}]
    assert mx.compute("max_gci_consistency", exact_but_unequal, params={"pred_levels": ["a0", "a1", "a2"],
                                                                        "ref_levels": ["b0", "b1", "b2"]}) == math.inf


@pytest.mark.parametrize("call", [
    lambda: mx.max_gci_capped([], [], []),
    lambda: mx.max_gci_capped([1.0], [math.nan], [1.0]),
    lambda: mx.max_gci_consistency([1.0], [1.0], [1.0], [1.0], [math.inf], [1.0]),
    lambda: mx.compute("max_gci_capped", [{"a": 1.0}], params={"levels": ["a", "a"]}),
    lambda: mx.compute("max_gci_capped", [{"a": 1.0}], params=None),
])
def test_o006_gci_recompute_fail_closed(call):
    with pytest.raises(ValueError):
        call()


def test_o006_gci_capped_continuous_and_never_below_order1_cap():
    """D0013 addendum (re-reviews T0187/T0188): no jump at rho = 1/4, and never below the order-1-capped form T0181
    found conservative; the side_by_side_6 die-11 case (rho 0.210) no longer sits at the 0.5 K threshold."""
    d1 = 0.4
    below = mx.gci_capped(410.0, 410.0 + d1, 410.0 + d1 + d1 * (0.25 - 1e-12))
    at = mx.gci_capped(410.0, 410.0 + d1, 410.0 + d1 + d1 * 0.25)
    assert below == pytest.approx(at, rel=1e-9) == pytest.approx(1.25 * d1 / 4)
    for rho in np.linspace(0.0, 0.999, 200):
        for d in (0.05, 0.4, -0.3):
            f0, f1 = 400.0, 400.0 + d
            f2 = f1 + rho * d
            d2, r = f2 - f1, (f2 - f1) / (f1 - f0)  # the rounded differences gci_capped sees
            p = min(math.log2(1 / r), 1.0) if r > 0 else 1.0
            assert mx.gci_capped(f0, f1, f2) >= 1.25 * abs(d2) / (2.0 ** p - 1.0) * (1 - 1e-12)
    assert mx.gci_capped(410.0, 410.396, 410.396 + 0.210 * 0.396) == pytest.approx(1.25 * 0.396 / 4)  # 0.124 K, not 0.495


def test_o006_gci_noise_floor_and_oscillatory_factor():
    """D0013 addendum 2 (reviews T0190/T0191): iteration noise below the floor cannot pick the branch, and the
    oscillatory branch carries Roache's factor 3 (1.25 understated a two-term error by up to 1.6x)."""
    for noise in (-4e-5, 4e-5):  # below the 1e-4 K Picard tolerance
        assert mx.gci_capped(410.0, 410.4, 410.4 + noise, floor=1e-3) == pytest.approx(1.25 * 0.4 / 4)
    assert mx.gci_capped(410.0, 410.4, 410.4 - 4e-5) == pytest.approx(3.0 * 0.4)  # without the floor the sign decides
    assert mx.gci_capped(410.0, 410.0005, 410.0009, floor=1e-3) == 0.0  # both steps below the floor
    assert mx.gci_capped(410.0, 410.0005, 410.0105, floor=1e-3) == math.inf  # d1 floored to 0 < |d2|: divergent
    with pytest.raises(ValueError):
        mx.gci_capped(410.0, 410.4, 410.5, floor=-1.0)
    # two-term error e(h) = h + t h^2 sampled at h = 4, 2, 1 (T0191's scan): the oscillatory branch now bounds it
    for t in np.linspace(-5.0, 5.0, 2001):
        e = [h + t * h * h for h in (4.0, 2.0, 1.0)]
        g = mx.gci_capped(*e)
        if math.isfinite(g) and (e[2] - e[1]) * (e[1] - e[0]) < 0:
            assert g >= abs(e[2]), t


def test_o006_gci_consistency_two_grid_terms():
    rows = [{"a0": 410.0, "a1": 410.4, "a2": 410.6, "b0": 410.9, "b1": 410.7, "b2": 410.65, "z0": 410.65, "z1": 410.66}]
    params = {"pred_levels": ["a0", "a1", "a2"], "ref_levels": ["b0", "b1", "b2"], "floor": 1e-3}
    base = mx.compute("max_gci_consistency", rows, params=params)
    with_z = mx.compute("max_gci_consistency", rows, params={**params, "ref_zpair": ["z0", "z1"]})
    assert mx.two_grid_term([410.65], [410.66]) == pytest.approx([0.025])
    assert with_z == pytest.approx(0.05 / (0.25 + 1.25 * 0.05 + 0.025)) and with_z < base
    with pytest.raises(ValueError):
        mx.compute("max_gci_consistency", rows, params={**params, "ref_zpair": ["z0"]})
    with pytest.raises(ValueError):
        mx.compute("max_gci_consistency", [{**rows[0], "z1": math.nan}], params={**params, "ref_zpair": ["z0", "z1"]})




def test_o007_f5_reference_gci_cap_makes_a3_not_met():
    """I0099 (O007 F5): a cross-check whose own GCI exceeds the cap on any row makes A3 +inf (not met), never INVALID."""
    rows = [{"a0": 410.0, "a1": 410.4, "a2": 410.6, "b0": 410.9, "b1": 410.7, "b2": 410.65},
            {"a0": 400.0, "a1": 400.2, "a2": 400.3, "b0": 399.0, "b1": 399.8, "b2": 400.1}]
    params = {"pred_levels": ["a0", "a1", "a2"], "ref_levels": ["b0", "b1", "b2"], "floor": 1e-3}
    g_ref = [mx.gci_capped(r["b0"], r["b1"], r["b2"], 1e-3) for r in rows]
    assert max(g_ref) == pytest.approx(1.25 * 0.3)  # second row: rho 0.375, p_obs 1.42 capped at 1
    uncapped = mx.compute("max_gci_consistency", rows, params=params)
    assert math.isfinite(uncapped)
    assert mx.compute("max_gci_consistency", rows, params={**params, "ref_gci_cap": max(g_ref) + 1e-9}) == uncapped
    assert mx.compute("max_gci_consistency", rows, params={**params, "ref_gci_cap": max(g_ref) - 1e-9}) == math.inf
    assert mx.compute("max_gci_consistency", rows, params={**params, "ref_gci_cap": None}) == uncapped
    with pytest.raises(ValueError):
        mx.compute("max_gci_consistency", rows, params={**params, "ref_gci_cap": -0.1})



# ------------------------------------------------------------------------------------------------ O003 headroom
NH = 1e-9


def _o3_layout(rid, lid, role, l_nh, band=(0.0, 0.0, 0.0, 0.0)):
    """band = (dl, dc, df, dw) in nH: L(0.5 mm) = L + dl, L(5/3/3) = L(0.5) + dc, L(20/12/12) = L(0.5) + df,
    L(wire) = L(0.5) + dw; None leaves the band columns empty."""
    row = {"kind": "layout", "reference_id": rid, "layout_id": lid, "role": role, "L_sub_H": l_nh * NH}
    if band is not None:
        dl, dc, df, dw = band
        c05 = l_nh + dl
        row.update(L_sub_c05_H=c05 * NH, L_sub_thk_c_H=(c05 + dc) * NH, L_sub_thk_f_H=(c05 + df) * NH,
                   L_sub_wire_f_H=(c05 + dw) * NH)
    return row


def _o3_dies(rid, lid, dies):
    return [{"kind": "die", "reference_id": rid, "layout_id": lid, "die_id": f"d{i}", "Tj_l0_K": d[0],
             "Tj_l1_K": d[1], "Tj_l2_K": d[2]} for i, d in enumerate(dies)]


ZB = (0.0, 0.0, 0.0, 0.0)  # a zero band: every 0.5 mm column equals the 0.25 mm one


def _o3_case(rid="R1", *, twin=10.0, recon=None, cands=(), l_term=7.0, admissible=True, s_ref=None, l1=(10.0, 10.0),
             tw_dies=((350.0,) * 3,) * 2, rec_dies=None, cand_t=350.0, cand_dies=None, no_dies=(), twin_band=ZB,
             recon_band=ZB):
    """One reference: twin and reconstruction (zero band unless given), ``cands`` = [(L_nH, band)] padded to the 16-candidate
    shortlist with candidates at 1.2 x twin + k x 0.01 nH; candidate dies at cand_t unless cand_dies[k] gives them;
    s_ref = None puts the reference on the 0.5 mm grid, else off-grid with L(0.25 snap) / L(0.5 snap) = 1 + s_ref / 2."""
    ref = {"kind": "reference", "reference_id": rid, "admissible": admissible, "L_term_H": l_term * NH,
           "on_grid": s_ref is None, "L1_min_first5000_H": l1[0] * NH, "L1_min_all_H": l1[1] * NH}
    if s_ref is not None:
        ref.update(L_snap025_H=(1.0 + s_ref / 2) * 10 * NH, L_snap05_H=10 * NH, L_snapchk0125_H=None,
                   L_snapchk05_H=None)
    rows = [ref]
    if not admissible:
        return rows
    rows += [_o3_layout(rid, "twin", "twin", twin, twin_band),
             _o3_layout(rid, "recon", "reconstruction", recon or twin, recon_band)]
    rows += _o3_dies(rid, "twin", tw_dies) + _o3_dies(rid, "recon", rec_dies or tw_dies)
    full = list(cands) + [(1.2 * twin + 0.01 * k, (0.0, 0.0, 0.0, 0.0)) for k in range(16 - len(cands))]
    for k, (lk, band) in enumerate(full):
        lid = f"c{k:02d}"
        rows.append(_o3_layout(rid, lid, "candidate", lk, band))
        if k not in no_dies:
            rows += _o3_dies(rid, lid, (cand_dies or {}).get(k, ((cand_t,) * 3,) * 2))
    return rows


def test_o003_ratio_band_estimate_by_hand_and_against_p3():
    one = [1.0] * 5
    # monotone thickness: e21 = 0.001, e32 = 0.004, r^p = 4 -> 1.25 x 0.001 x 4 / 3
    assert mx.ratio_band_estimate([0.8, 0.8, 0.804, 0.799, 0.8], one) == pytest.approx(1.25 * 0.001 * 4 / 3)
    # oscillatory thickness 3 max(|e21|, |e32|) = 0.006; lateral 3 x 0.002; wire 3 x 0.001
    assert mx.ratio_band_estimate([0.802, 0.8, 0.802, 0.801, 0.801], one) == pytest.approx(0.006 + 0.006 + 0.003)
    assert mx.ratio_band_estimate([8.0, 8.0, 8.0, 8.0, 8.0], [10.0] * 5) == 0.0  # ratios equal at every level
    spec = importlib.util.spec_from_file_location("o006_p3", REPO / "research" / "scripts" / "o006_p3_em_convergence.py")
    p3 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(p3)
    rng = np.random.default_rng(20261109)
    for fc, fm, ff in 1.0 + 1e-3 * rng.normal(size=(500, 3)):
        assert mx.ratio_middle_term(fc, fm, ff) == pytest.approx(p3.middle_term(fc, fm, ff, 2.0)[1], rel=1e-9)
    with pytest.raises(ValueError):
        mx.ratio_band_estimate([1.0] * 4, one)


def test_o003_snapping_bias_and_tj_bounds_by_hand():
    assert mx.snapping_bias(True, None, None) == 0.0
    assert mx.snapping_bias(False, 10.1, 10.0) == pytest.approx(0.02)
    assert mx.snapping_bias(False, 10.1, 10.0, 10.3, 10.0) == pytest.approx(0.03)  # the snapping check is larger
    assert mx.snapping_bias(False, 10.1, 10.0, 10.05, 10.0) == pytest.approx(0.02)
    with pytest.raises(ValueError):
        mx.snapping_bias(False, 10.1, 10.0, 10.3, None)
    # die 0: rho 1/2 -> GCI 1.25 x 0.25 = 0.3125; die 1: divergent (rho = 1) -> +inf, drops out of the lower bound
    t = mx.tj_bounds([(350.0, 350.5, 350.75), (351.0, 352.0, 353.0)])
    assert t == (353.0, math.inf, math.inf, pytest.approx(350.75 - 0.3125), 1)
    assert mx.tj_bounds([(351.0, 352.0, 353.0)])[3] == -math.inf  # nothing bounds W from below


def test_o003_twin_case_gives_minus_and_plus_a_sref():
    rows = _o3_case(s_ref=0.02, cands=[(12.0, (0.0, 0.0, 0.0, 0.0))])
    a = 10.0 / 17.0
    assert mx.headroom_min_lo(rows) == pytest.approx(-a * 0.02)
    assert mx.headroom_max_hi_ind(rows) == pytest.approx(a * 0.02)
    per = mx.headroom_per_reference(rows)["R1"]
    assert per["best_id"] is None and per["r"] == 1.0 and per["e_R"] == 0.0 and per["near_tie_h_hi"] == {}


def test_o003_no_eligible_candidate():
    # every checked candidate is 10 K hotter than the twin: 8 checked (two batches), none eligible -> twin rule for A1;
    # K1 ignores Tj: inductance-only best 8 nH, e_R 0, w_ind 0.02, h_hi = a (1 - 0.8 x 0.98)
    rows = _o3_case(s_ref=0.02, cands=[(8.0, (0.0, 0.0, 0.0, 0.0))], cand_t=360.0)
    a = 10.0 / 17.0
    per = mx.headroom_per_reference(rows)["R1"]
    assert per["n_thermal_checked"] == 8 and per["n_tj_rejected"] == 8 and per["best_id"] is None
    assert mx.headroom_min_lo(rows) == pytest.approx(-a * 0.02)
    assert mx.headroom_max_hi_ind(rows) == pytest.approx(a * (1 - 0.8 * 0.98))


def test_o003_non_levelled_is_inf_and_checked_before_the_twin_rule():
    a = 10.0 / 17.0
    twin_wins = dict(s_ref=0.02, cands=[(12.0, (0.0, 0.0, 0.0, 0.0))])
    assert mx.headroom_max_hi_ind(_o3_case(**twin_wins, l1=(10.5, 10.0))) == math.inf  # 10.5 > 1.02 x 10.0
    assert mx.headroom_max_hi_ind(_o3_case(**twin_wins, l1=(10.19, 10.0))) == pytest.approx(a * 0.02)  # levelled
    assert mx.headroom_min_lo(_o3_case(**twin_wins, l1=(10.5, 10.0))) == pytest.approx(-a * 0.02)  # A1 unaffected
    with pytest.raises(ValueError):  # first-5,000 minimum below the all-20,000 minimum is inconsistent data
        mx.headroom_max_hi_ind(_o3_case(**twin_wins, l1=(9.9, 10.0)))


def test_o003_near_tie_takes_the_largest_h_hi():
    # w_ind = 0 + 0.02: near ties up to 8.16 nH. c01 at 8.1 nH has L(0.5) = 8.15 nH: e_R = 3 x 0.005 = 0.015, w = 0.05,
    # h_hi = a (1 - 0.81 x 0.95) = a 0.2305 > c00's a (1 - 0.8 x 0.98) = a 0.216; c02 at 8.2 nH is outside despite its
    # wide band
    rows = _o3_case(s_ref=0.02, cands=[(8.0, (0.0, 0.0, 0.0, 0.0)), (8.1, (0.05, 0.0, 0.0, 0.0)),
                                       (8.2, (1.0, 0.0, 0.0, 0.0))])
    a = 10.0 / 17.0
    per = mx.headroom_per_reference(rows)["R1"]
    assert sorted(per["near_tie_h_hi"]) == ["c00", "c01"]
    assert per["near_tie_h_hi"]["c00"] == pytest.approx(a * 0.216)
    assert mx.headroom_max_hi_ind(rows) == pytest.approx(a * (1 - 0.81 * 0.95))
    assert mx.headroom_min_lo(rows) == pytest.approx(a * (1 - 0.8 * 1.02))  # A1 best is c00 (meets the Tj test)


def test_o003_inf_gci_on_candidate_fails_and_on_twin_drops_out():
    a, s = 10.0 / 17.0, 0.02
    best = [(8.0, (0.0, 0.0, 0.0, 0.0))]
    # on C: die (350, 350.5, 351) has rho = 1 -> +inf -> fails; with (350, 350.5, 350.75) it passes (351.06 - 350 <= 2)
    flat = (350.0, 350.0, 350.0)
    bad = _o3_case(s_ref=s, cands=best, cand_dies={0: [(350.0, 350.5, 351.0), flat]})
    good = _o3_case(s_ref=s, cands=best, cand_dies={0: [(350.0, 350.5, 350.75), flat]})
    assert mx.headroom_min_lo(bad) == pytest.approx(-a * s)
    assert mx.headroom_per_reference(bad)["R1"]["n_tj_inf"] == 1
    assert mx.headroom_min_lo(good) == pytest.approx(a * (1 - 0.8 * (1 + s)))
    # on W: die B (383, 383.5, 384) diverges and drops out, so W's lower bound is die A's 380 K and a 383 K candidate
    # fails (3 K > 2 K); were B counted at 384 K it would pass. The optimistic test passes (W's upper bound is +inf).
    tw = [(380.0, 380.0, 380.0), (383.0, 383.5, 384.0)]
    rows = _o3_case(s_ref=s, cands=best, tw_dies=tw, rec_dies=[(380.0,) * 3] * 2, cand_dies={0: [(383.0,) * 3] * 2})
    per = mx.headroom_per_reference(rows)["R1"]
    assert per["gate_a2"] and per["best_id"] is None and per["h_lo"] == pytest.approx(-a * s)
    assert per["opt_id"] == "c00" and per["h_opt_hi"] == pytest.approx(a * (1 - 0.8 * (1 - s)))


def test_o003_f3_batches_and_extra_thermal_rows():
    a = 10.0 / 17.0
    cands = [(8.0 + 0.1 * k, (0.0, 0.0, 0.0, 0.0)) for k in range(6)]
    hot = {k: [(360.0,) * 3] * 2 for k in range(4)}
    rows = _o3_case(cands=cands, cand_dies=hot)  # batch 1 all fail; c04 (8.4 nH) in batch 2 is best
    per = mx.headroom_per_reference(rows)["R1"]
    assert per["best_id"] == "c04" and per["n_thermal_checked"] == 8
    assert per["h_lo"] == pytest.approx(a * (1 - 0.84))
    # c02 passes in batch 1: stop after it; batch 2 needs no thermal rows; best is the lowest eligible, c02
    rows = _o3_case(cands=cands, cand_dies={0: [(360.0,) * 3] * 2, 1: [(360.0,) * 3] * 2}, no_dies=range(4, 16))
    assert mx.headroom_per_reference(rows)["R1"]["best_id"] == "c02"
    with pytest.raises(ValueError):  # a candidate F3 must check has no thermal rows
        mx.headroom_min_lo(_o3_case(cands=cands, no_dies=(1,)))


def test_o003_counted_references_and_twin_gates():
    a = 10.0 / 17.0
    r1 = _o3_case("R1", s_ref=0.02, cands=[(7.0, (0.0, 0.0, 0.0, 0.0))])  # h_lo = a (1 - 0.7 x 1.02)
    excluded = _o3_case("R0", admissible=False)
    a1_fail = _o3_case("R2", s_ref=0.02, recon=10.5, cands=[(9.5, (0.0, 0.0, 0.0, 0.0))])  # |1 - 10/10.5| > 0.02
    a1_pass = _o3_case("R2", s_ref=0.02, recon=10.15, cands=[(9.5, (0.0, 0.0, 0.0, 0.0))])  # 0.0148 <= 0.02
    a2_fail = _o3_case("R3", cands=[(9.5, (0.0, 0.0, 0.0, 0.0))], rec_dies=[(353.0,) * 3] * 2)  # 3 K > G sum 0
    single = r1 + excluded + a1_fail + a2_fail
    per = mx.headroom_per_reference(single)
    assert [k for k, v in per.items() if v["counted"]] == ["R1"]
    assert not per["R2"]["gate_a1"] and per["R2"]["gate_a2"] and not per["R3"]["gate_a2"]
    assert mx.headroom_min_lo(single) == pytest.approx(a * (1 - 0.7 * 1.02))
    assert mx.headroom_max_hi_ind(single) == pytest.approx(a * (1 - 0.7 * 0.98))
    both = r1 + a1_pass
    assert mx.headroom_min_lo(both) == pytest.approx(a * (1 - 0.95 * 1.02))  # R2 counted and lower
    with pytest.raises(ValueError):  # no counted reference: INVALID
        mx.headroom_min_lo(excluded + a1_fail + a2_fail)


@pytest.mark.parametrize("l_sub, l_term, pass_from, kill_below", [(10.0, 0.0, 0.216, 0.082), (10.0, 7.0, 0.353, 0.153),
                                                                    (20.0, 7.0, 0.284, 0.117)])
def test_o003_verdict_region_examples_of_the_notes(l_sub, l_term, pass_from, kill_below):
    """O003 notes: a = 1, w = 0.02: PASS from 0.216, kill below 0.082; 10 nH + 7 nH: 0.353 / 0.153; 20 nH: 0.284 / 0.117."""
    w = 0.02
    a = l_sub / (l_sub + l_term)
    h_pass, h_kill = 1 - (1 - 0.20 / a) / (1 + w), 1 - (1 - 0.10 / a) / (1 - w)
    assert round(h_pass, 3) == pass_from and round(h_kill, 3) == kill_below

    def rows(h_sub):
        return _o3_case(twin=l_sub, l_term=l_term, s_ref=w, l1=(l_sub, l_sub),
                        cands=[(l_sub * (1 - h_sub), (0.0, 0.0, 0.0, 0.0))])
    assert mx.headroom_min_lo(rows(h_pass + 1e-6)) >= 0.20 > mx.headroom_min_lo(rows(h_pass - 1e-6))
    assert mx.headroom_max_hi_ind(rows(h_kill - 1e-6)) < 0.10 <= mx.headroom_max_hi_ind(rows(h_kill + 1e-6))


def test_o003_sensitivity_and_reconstruction_based_secondary():
    rows = _o3_case(s_ref=0.02, recon=10.1, cands=[(8.0, (0.0, 0.0, 0.0, 0.0))])
    assert mx.headroom_min_lo(rows, params={"L_term_H": 0.0}) == pytest.approx(1 - 0.8 * 1.02)
    assert mx.headroom_min_lo(rows, params={"L_term_H": 17.5e-9}) == pytest.approx(10 / 27.5 * (1 - 0.8 * 1.02))
    assert mx.headroom_max_hi_ind(rows, params={"L_term_H": 0.0}) == pytest.approx(1 - 0.8 * 0.98)
    ar = 10.1 / 17.1
    assert mx.headroom_min_lo(rows, params={"comparator": "reconstruction"}) == pytest.approx(
        ar * (1 - 8.0 / 10.1 * 1.02))
    assert mx.headroom_max_hi_ind(rows, params={"comparator": "reconstruction"}) == pytest.approx(
        ar * (1 - 8.0 / 10.1 * 0.98))
    with pytest.raises(ValueError):
        mx.headroom_min_lo(rows, params={"L_term": 0.0})  # mistyped key


def test_o003_dispatch_and_declared_null():
    rows = _o3_case(s_ref=0.02, cands=[(8.0, (0.0, 0.0, 0.0, 0.0))])
    for r in rows:  # the null column of the row contract: the twin's L_sub on candidate rows, the row's own elsewhere
        r["L_sub_null_H"] = 10.0 * NH if r.get("role") == "candidate" else r.get("L_sub_H", 10.0 * NH)
    a = 10.0 / 17.0
    assert mx.compute("headroom_min_lo", rows, pred="L_sub_H") == pytest.approx(a * (1 - 0.8 * 1.02))
    assert mx.compute("headroom_max_hi_ind", rows, params={"L_term_H": 0.0}) == pytest.approx(1 - 0.8 * 0.98)
    nrows = [{**r, "__null__": v} for r, v in zip(rows, mx.null_column(rows, "column", None, column="L_sub_null_H"),
                                                  strict=True)]
    assert mx.compute("headroom_min_lo", nrows, pred="__null__") == pytest.approx(-a * 0.02)  # fails A1 by construction




# ------------------------------------------------------------------------------------------------ nonzero band terms (T0269)
# Every case below has e_R > 0 somewhere the formula uses it, so a dropped, doubled or mis-wired band term changes a value.
FULL_BAND = (0.05, 0.04, -0.01, 0.02)  # L(0.5) = L + 0.05, L(5/3/3) = L(0.5) + 0.04, L(20/12/12) = L(0.5) - 0.01, wire + 0.02
# Hand value of e_R(candidate 8.0 nH with FULL_BAND, twin 10 nH with a zero band): R = 0.8 / 0.805 / 0.809 / 0.804 / 0.807;
# lateral 3 x 0.005; thickness e21 = 0.805 - 0.804 = 0.001, e32 = 0.809 - 0.805 = 0.004, r^p = 4: 1.25 x 0.001 x 4 / 3;
# wire 3 x 0.002.
E_FULL = 0.015 + 0.005 / 3 + 0.006
A_TWIN = 10.0 / 17.0


def test_o003_a1_best_with_nonzero_band_uses_two_e_r_plus_s_ref():
    rows = _o3_case(s_ref=0.02, cands=[(8.0, FULL_BAND)])
    per = mx.headroom_per_reference(rows)["R1"]
    assert per["best_id"] == "c00" and per["e_R"] == pytest.approx(E_FULL, rel=1e-9)
    w = 2 * E_FULL + 0.02
    assert per["w"] == pytest.approx(w, rel=1e-9)
    assert mx.headroom_min_lo(rows) == pytest.approx(A_TWIN * (1 - 0.8 * (1 + w)), rel=1e-9)
    # the same layout is K1's inductance-only best, levelled (L1 equal), alone in its near-tie band (to 8.0 x (1 + w) < 12)
    assert mx.headroom_max_hi_ind(rows) == pytest.approx(A_TWIN * (1 - 0.8 * (1 - w)), rel=1e-9)
    assert mx.headroom_per_reference(rows)["R1"]["near_tie_h_hi"].keys() == {"c00"}


def test_o003_a1_each_band_term_enters_alone():
    # one nonzero term at a time (the others are zero), so each term of e_R is pinned by itself
    for band, e in [((0.05, 0, 0, 0), 0.015), ((0, 0.04, 0, 0), 3 * 0.004),
                    ((0, 0, 0, 0.02), 0.006)]:
        per = mx.headroom_per_reference(_o3_case(s_ref=0.02, cands=[(8.0, band)]))["R1"]
        assert per["e_R"] == pytest.approx(e, rel=1e-9), band


def test_o003_levelling_threshold_uses_two_e_r_of_the_ind_twin_pair():
    # w_lev = 2 E_FULL + s_ref = 0.065333: levelled iff L1_first <= 1.065333 L1_all
    a = A_TWIN
    w = 2 * E_FULL + 0.02
    kw = dict(s_ref=0.02, cands=[(8.0, FULL_BAND)])
    assert mx.headroom_max_hi_ind(_o3_case(**kw, l1=(10.64, 10.0))) == pytest.approx(a * (1 - 0.8 * (1 - w)), rel=1e-9)
    assert mx.headroom_max_hi_ind(_o3_case(**kw, l1=(10.67, 10.0))) == math.inf
    assert mx.headroom_per_reference(_o3_case(**kw, l1=(10.64, 10.0)))["R1"]["w_levelling"] == pytest.approx(w, rel=1e-9)


def test_o003_twin_gate_inductance_counts_two_e_r():
    # twin 10 nH vs reconstruction 10.2 nH: |1 - L(W)/L(ref)| = 0.019608. W's 0.5 mm value is 10 + dl, so
    # e_R = 3 |10 / 10.2 - (10 + dl) / 10.2|, and the gate needs 2 e_R >= 0.019608 (s_ref = 0, on the grid)
    def per(dl):
        rows = _o3_case(twin=10.0, recon=10.2, cands=[(9.0, ZB)], twin_band=(dl, 0, 0, 0), recon_band=ZB)
        return mx.headroom_per_reference(rows)["R1"]
    ok = per(0.034)  # e_R = 3 x 0.034 / 10.2 = 0.01, 2 e_R = 0.02 >= 0.019608 passes (a single e_R = 0.01 would fail)
    assert ok["gate_a1"] and ok["counted"]
    bad = per(0.03)  # e_R = 0.008824, 2 e_R = 0.017647 < 0.019608 fails (the 0.5 mm columns alone: 0.016667 would pass)
    assert not bad["gate_a1"] and not bad["counted"]
    with pytest.raises(ValueError, match="no counted reference"):
        mx.headroom_min_lo(_o3_case(twin=10.0, recon=10.2, cands=[(9.0, ZB)], twin_band=(0.03, 0, 0, 0)))
    with pytest.raises(ValueError, match="no counted reference"):
        mx.headroom_max_hi_ind(_o3_case(twin=10.0, recon=10.2, cands=[(9.0, ZB)], twin_band=(0.03, 0, 0, 0)))


def test_o003_twin_gate_inductance_adds_s_ref_to_two_e_r():
    # e_R = 0.008824, 2 e_R = 0.017647; s_ref = 0.002 lifts the threshold to 0.019647 >= 0.019608
    rows = _o3_case(twin=10.0, recon=10.2, s_ref=0.002, cands=[(9.0, ZB)], twin_band=(0.03, 0, 0, 0))
    assert mx.headroom_per_reference(rows)["R1"]["gate_a1"]
    rows = _o3_case(twin=10.0, recon=10.2, s_ref=0.0019, cands=[(9.0, ZB)], twin_band=(0.03, 0, 0, 0))
    assert not mx.headroom_per_reference(rows)["R1"]["gate_a1"]


def test_o003_twin_gate_thermal_adds_the_two_gci_values():
    # W: die A (350, 350.5, 350.75), GCI 1.25 x 0.25 / (2 - 1) = 0.3125; die B flat. Reconstruction: die A (T - 2, T - 0.5, T),
    # d1 = 1.5, d2 = 0.5, rho = 1/3, p capped at 1: GCI 1.25 x 0.5 = 0.625. G sum 0.9375; max 0.625.
    w_dies = [(350.0, 350.5, 350.75), (350.0, 350.0, 350.0)]

    def per(t_ref):
        rec = [(t_ref - 2.0, t_ref - 0.5, t_ref), (340.0, 340.0, 340.0)]
        return mx.headroom_per_reference(_o3_case(cands=[(9.0, ZB)], tw_dies=w_dies, rec_dies=rec))["R1"]
    ok = per(351.6)  # |350.75 - 351.6| = 0.85 <= 0.9375, but > max(G) = 0.625
    assert ok["gate_a2"] and ok["counted"] and ok["tj_twin"][1] == pytest.approx(0.3125)
    assert ok["tj_recon"][1] == pytest.approx(0.625)
    bad = per(351.7)  # 0.95 > 0.9375
    assert not bad["gate_a2"]
    assert per(349.9)["gate_a2"] and not per(349.7)["gate_a2"]  # symmetric: 0.85 passes, 1.05 fails


RECON_BAND = (-0.1, 0.0, 0.0, 0.0)  # reconstruction 10 nH whose 0.5 mm columns are 9.9 nH
# e_R(c00, reconstruction) = 3 (8.05 / 9.9 - 0.8) = 0.039394 (all four 0.5 mm levels equal, so only the lateral term);
# e_R(c00, twin) = 0.015
E_REC = 3 * (8.05 / 9.9 - 0.8)


def _recon_case(**kw):
    return _o3_case(s_ref=0.02, recon_band=RECON_BAND, cands=[(8.0, (0.05, 0.0, 0.0, 0.0))], **kw)


def test_o003_reconstruction_secondary_uses_the_reconstruction_pair_but_the_twins_tj_and_levelling():
    rec = {"comparator": "reconstruction"}
    # twin dies flat at 350 K (G = 0); reconstruction die (349.5, 350.0, 350.25): GCI 0.3125, |350.25 - 350| passes F1(a2).
    # Candidate c00 flat at 351.99 K: 1.99 K above W's lower bound (eligible against W), 2.0525 K above the
    # reconstruction's (350.25 - 0.3125 = 349.9375) so it would fail were the Tj test run against the reconstruction.
    rec_dies = [(349.5, 350.0, 350.25), (340.0, 340.0, 340.0)]
    hot = {0: [(351.99,) * 3] * 2}
    rows = _recon_case(rec_dies=rec_dies, cand_dies=hot)
    per = mx.headroom_per_reference(rows, params=rec)["R1"]
    assert per["counted"] and per["best_id"] == "c00" and per["e_R"] == pytest.approx(E_REC, rel=1e-9)
    w = 2 * E_REC + 0.02
    a = 10.0 / 17.0  # the reconstruction is 10 nH too
    assert mx.headroom_min_lo(rows, params=rec) == pytest.approx(a * (1 - 0.8 * (1 + w)), rel=1e-9)
    # against the twin's pair e_R would be 0.015: a different number
    assert mx.headroom_min_lo(rows) == pytest.approx(a * (1 - 0.8 * (1 + 2 * 0.015 + 0.02)), rel=1e-9)
    # K1 with the reconstruction as comparator: w_ind = 2 E_REC + s_ref
    assert mx.headroom_max_hi_ind(rows, params=rec) == pytest.approx(a * (1 - 0.8 * (1 - w)), rel=1e-9)
    # levelling keeps the twin pair: w_lev = 2 x 0.015 + 0.02 = 0.05 (the reconstruction pair would give 2 E_REC + 0.02 =
    # 0.0988). 10.4 <= 10.5 is levelled, 10.7 is not under the twin pair although the other pair would level it.
    assert mx.headroom_max_hi_ind(_recon_case(rec_dies=rec_dies, l1=(10.4, 10.0)), params=rec) == pytest.approx(
        a * (1 - 0.8 * (1 - w)), rel=1e-9)
    nl = mx.headroom_per_reference(_recon_case(rec_dies=rec_dies, l1=(10.7, 10.0)), params=rec)["R1"]
    assert nl["w_levelling"] == pytest.approx(0.05, rel=1e-9) and nl["h_hi"] == math.inf


def test_o003_tj_limit_and_floor_params_change_the_eligible_set():
    a, s = A_TWIN, 0.02
    best = [(8.0, ZB)]
    flat = lambda t: {0: [(t,) * 3] * 2}  # noqa: E731
    pos = a * (1 - 0.8 * (1 + s))
    # W flat at 350 K. Candidate 1.5 K above: eligible at the default 2 K, not at 1 K; 2.5 K above: only at 3 K
    assert mx.headroom_min_lo(_o3_case(s_ref=s, cands=best, cand_dies=flat(351.5))) == pytest.approx(pos)
    assert mx.headroom_min_lo(_o3_case(s_ref=s, cands=best, cand_dies=flat(351.5)),
                              params={"tj_limit_K": 1.0}) == pytest.approx(-a * s)
    assert mx.headroom_min_lo(_o3_case(s_ref=s, cands=best, cand_dies=flat(352.0))) == pytest.approx(pos)  # exactly 2 K
    assert mx.headroom_min_lo(_o3_case(s_ref=s, cands=best, cand_dies=flat(352.5))) == pytest.approx(-a * s)
    assert mx.headroom_min_lo(_o3_case(s_ref=s, cands=best, cand_dies=flat(352.5)),
                              params={"tj_limit_K": 3.0}) == pytest.approx(pos)
    # floor: die (350, 350.0004, 350.001) has d1 = 0.0004, d2 = 0.0006, both below the default floor 1e-3 K -> GCI 0;
    # with floor 0, rho = 1.5 -> +inf and the candidate fails
    small = {0: [(350.0, 350.0004, 350.001)] * 2}
    assert mx.headroom_min_lo(_o3_case(s_ref=s, cands=best, cand_dies=small)) == pytest.approx(pos)
    assert mx.headroom_min_lo(_o3_case(s_ref=s, cands=best, cand_dies=small),
                              params={"floor": 0.0}) == pytest.approx(-a * s)


def test_o003_boundaries_at_equality():
    a = A_TWIN
    # on the grid with a zero band, w_lev = 0 and L1_first = L1_all is exactly at the levelling threshold: levelled
    on_grid = _o3_case(cands=[(8.0, ZB)], l1=(10.0, 10.0))
    assert mx.headroom_max_hi_ind(on_grid) == pytest.approx(a * (1 - 0.8))
    # the twin's L_sub equals the lowest candidate's: the twin rule decides (h_hi = a s_ref) although the candidate has a
    # nonzero band that the near-tie rule would turn into a(2 e_R + s_ref)
    rows = _o3_case(s_ref=0.02, cands=[(10.0, (0.05, 0, 0, 0))])
    assert mx.headroom_max_hi_ind(rows) == pytest.approx(a * 0.02)
    assert mx.headroom_min_lo(rows) == pytest.approx(-a * 0.02)


def test_o003_near_tie_band_comes_from_the_inductance_only_bests_e_r():
    # c00 (8.0 nH, e_R = 0.015) gives w_ind = 0.05 and near ties up to 8.4 nH. c01 at 8.35 nH has a wide band (L(0.5) =
    # 9.35, e_R = 3 x 0.1 = 0.3, w = 0.62) and h_hi = a (1 - 0.835 x 0.38); with w_ind = s_ref alone (8.16) or e_R not
    # doubled (8.28) it would not be a near tie
    rows = _o3_case(s_ref=0.02, cands=[(8.0, (0.05, 0, 0, 0)), (8.35, (1.0, 0, 0, 0))])
    per = mx.headroom_per_reference(rows)["R1"]
    assert sorted(per["near_tie_h_hi"]) == ["c00", "c01"] and per["w_ind"] == pytest.approx(0.05, rel=1e-9)
    assert mx.headroom_max_hi_ind(rows) == pytest.approx(A_TWIN * (1 - 0.835 * 0.38), rel=1e-9)


def test_o003_equal_l_sub_ties_break_by_layout_id_ascending():
    # c00 and c01 both 8.0 nH, both eligible; c00 has a zero band, c01 a nonzero one: the A1 best is c00 (e_R = 0)
    rows = _o3_case(s_ref=0.02, cands=[(8.0, ZB), (8.0, (0.05, 0, 0, 0))])
    per = mx.headroom_per_reference(rows)["R1"]
    assert per["best_id"] == "c00" and per["ind_id"] == "c00" and per["e_R"] == 0.0
    assert mx.headroom_min_lo(rows) == pytest.approx(A_TWIN * (1 - 0.8 * 1.02))
    # K1: both are near ties of each other; the one with the wider band has the larger h_hi (w = 0.05)
    assert mx.headroom_max_hi_ind(rows) == pytest.approx(A_TWIN * (1 - 0.8 * 0.95))


def test_o003_die_count_must_be_the_twins_for_every_thermally_checked_layout():
    assert mx.tj_bounds([(350.0,) * 3] * 2, n_dies=2)[0] == 350.0
    with pytest.raises(ValueError, match="dies"):
        mx.tj_bounds([(350.0,) * 3], n_dies=2)
    one = (350.0,) * 3
    cands = [(8.0, ZB)]
    three = {k: [one] * 3 for k in range(4)}  # the four candidates of F3's first batch
    assert mx.headroom_min_lo(_o3_case(s_ref=0.02, cands=cands, tw_dies=(one,) * 3, cand_dies=three)) > 0  # 3 everywhere
    # the reconstruction with a die missing: both metrics refuse (both run the twin gates)
    for metric in (mx.headroom_min_lo, mx.headroom_max_hi_ind):
        with pytest.raises(ValueError, match="dies"):
            metric(_o3_case(s_ref=0.02, cands=cands, rec_dies=[one]))
        with pytest.raises(ValueError, match="dies"):
            metric(_o3_case(s_ref=0.02, cands=cands, rec_dies=[one] * 3))
    # a candidate F3 checks, with a die missing (it could otherwise pass on its remaining, cooler dies)
    with pytest.raises(ValueError, match="dies"):
        mx.headroom_min_lo(_o3_case(s_ref=0.02, cands=cands, cand_dies={0: [one]}))
    # a candidate F3 does not check (c10 is beyond the 8 checked) is not looked at, and K1 never reads candidate dies
    assert mx.headroom_min_lo(_o3_case(s_ref=0.02, cands=cands, cand_dies={10: [one]})) > 0
    assert mx.headroom_max_hi_ind(_o3_case(s_ref=0.02, cands=cands, cand_dies={0: [one]})) > 0


def test_o003_null_column_contract_for_extra_row_kinds():
    """Degraded and control_best layout rows, L1-only null rows and a runner-added kind carry L_sub_null_H and change
    nothing: the metrics ignore them (row contract section 3)."""
    rows = _o3_case(s_ref=0.02, cands=[(8.0, ZB)])
    extra = [{"kind": "layout", "reference_id": "R1", "layout_id": "deg0", "role": "degraded", "L_sub_H": 11e-9},
             {"kind": "layout", "reference_id": "R1", "layout_id": "ctl0", "role": "control_best", "L_sub_H": 6e-9},
             {"kind": "layout", "reference_id": "R1", "layout_id": "l1n0", "role": "l1_null_best", "L_sub_H": 7e-9},
             {"kind": "die", "reference_id": "R1", "layout_id": "l1n0", "die_id": "d0", "Tj_l0_K": 340.0,
              "Tj_l1_K": 340.0, "Tj_l2_K": 340.0},
             {"kind": "runner_note", "text": "no reference"}]
    base_min, base_max = mx.headroom_min_lo(rows), mx.headroom_max_hi_ind(rows)
    allrows = rows + extra
    for r in allrows:
        r["L_sub_null_H"] = 10.0 * NH if r.get("role") == "candidate" else r.get("L_sub_H", 10.0 * NH)
    assert mx.headroom_min_lo(allrows) == base_min and mx.headroom_max_hi_ind(allrows) == base_max
    nulls = mx.null_column(allrows, "column", None, column="L_sub_null_H")  # every row of every kind has a value
    assert len(nulls) == len(allrows)
    nrows = [{**r, "__null__": v} for r, v in zip(allrows, nulls, strict=True)]
    a = A_TWIN
    assert mx.headroom_min_lo(nrows, pred="__null__") == pytest.approx(-a * 0.02)
    del allrows[-1]["L_sub_null_H"]  # a row without it: the recompute entry would fail, closed
    with pytest.raises(KeyError):
        mx.null_column(allrows, "column", None, column="L_sub_null_H")


# ------------------------------------------------------------------------------------------------ T0269 attempt 2 gaps
# Each case below kills a mutant that survived every test above (check_mutants.py, section "attempt 2").


def test_o003_k1_is_the_max_and_a1_the_min_over_counted_references():
    # R1: c00 at 7 nH; R2: c00 at 9.5 nH (reconstruction 10.15 nH passes F1(a1)); both counted, zero bands, s_ref 0.02
    a = A_TWIN
    r1 = _o3_case("R1", s_ref=0.02, cands=[(7.0, ZB)])
    r2 = _o3_case("R2", s_ref=0.02, recon=10.15, cands=[(9.5, ZB)])
    assert mx.headroom_max_hi_ind(r1 + r2) == pytest.approx(a * (1 - 0.7 * 0.98))  # R1's, the larger
    assert mx.headroom_min_lo(r1 + r2) == pytest.approx(a * (1 - 0.95 * 1.02))  # R2's, the smaller
    # one counted reference that is not levelled (10.5 > 1.02 x 10) makes K1 +inf, whatever the others give
    r3 = _o3_case("R3", s_ref=0.02, cands=[(9.5, ZB)], l1=(10.5, 10.0))
    assert mx.headroom_max_hi_ind(r1 + r2 + r3) == math.inf


def test_o003_twin_rule_needs_no_candidate_dies_also_under_the_declared_null():
    a, s = A_TWIN, 0.02
    # every shortlisted candidate (12 nH and up) is above the twin's 10 nH: the twin rule decides A1 and F3 stops before
    # any thermal check, with no candidate die rows at all or with die rows on only part of the first batch
    for no_dies in (range(16), range(1, 16)):
        per = mx.headroom_per_reference(_o3_case(s_ref=s, no_dies=no_dies))["R1"]
        assert per["h_lo"] == pytest.approx(-a * s) and not per["f3_complete"] and per["n_thermal_checked"] == 0
    # equality counts (L(W) <= L(c)): the lowest candidate at exactly 10 nH, no candidate die rows
    assert mx.headroom_min_lo(_o3_case(s_ref=s, cands=[(10.0, ZB)], no_dies=range(16))) == pytest.approx(-a * s)
    # a candidate below the twin: the die rows F3 needs are missing, so it raises (fail closed)
    with pytest.raises(ValueError, match="no die rows"):
        mx.headroom_min_lo(_o3_case(s_ref=s, cands=[(9.99, ZB)], no_dies=range(16)))
    # the declared null (row contract section 3): F3 really checked c12..c15 (the four lowest, 8.0..8.3 nH; c12 eligible),
    # so only they have die rows. Under the null every candidate takes the twin's 10 nH, F3's order falls back to
    # layout_id (c00..c03, without die rows), and the twin rule (10 <= 10) decides without them: h_lo = -a s_ref
    cands = [(12.0 + 0.01 * k, ZB) for k in range(12)] + [(8.0 + 0.1 * k, ZB) for k in range(4)]
    rows = _o3_case(s_ref=s, cands=cands, no_dies=range(12))
    assert mx.headroom_per_reference(rows)["R1"]["best_id"] == "c12"
    for r in rows:
        r["L_sub_null_H"] = 10.0 * NH if r.get("role") == "candidate" else r.get("L_sub_H", 10.0 * NH)
    nrows = [{**r, "__null__": v} for r, v in zip(rows, mx.null_column(rows, "column", None, column="L_sub_null_H"),
                                                  strict=True)]
    assert mx.compute("headroom_min_lo", nrows, pred="__null__") == pytest.approx(-a * s)


def test_o003_reconstruction_secondary_switches_the_twin_rule_and_the_near_tie_band():
    rec, s = {"comparator": "reconstruction"}, 0.02
    # twin rule: twin 10 nH, reconstruction 10.1 nH (F1(a1): 0.0099 <= 0.02), c00 at 10.05 nH between them, zero bands.
    # Against the twin the twin rule decides (10 <= 10.05); against the reconstruction it does not (10.1 > 10.05).
    rows = _o3_case(s_ref=s, recon=10.1, cands=[(10.05, ZB)])
    a, ar, rr = A_TWIN, 10.1 / 17.1, 10.05 / 10.1
    assert mx.headroom_min_lo(rows) == pytest.approx(-a * s)
    assert mx.headroom_max_hi_ind(rows) == pytest.approx(a * s)
    assert mx.headroom_min_lo(rows, params=rec) == pytest.approx(ar * (1 - rr * (1 + s)))
    assert mx.headroom_max_hi_ind(rows, params=rec) == pytest.approx(ar * (1 - rr * (1 - s)))
    # near-tie band: w_ind = 2 e_R(ind, comparator) + s_ref. With RECON_BAND, e_R(c00, reconstruction) = E_REC and the
    # band reaches 8.0 (1 + 2 E_REC + 0.02) = 8.79 nH; against the twin (e_R 0.015) only 8.4 nH. c01 at 8.6 nH has
    # L(0.5) = 9.6 nH: e_R(c01, reconstruction) = 3 |0.86 - 9.6 / 9.9| (lateral term only) and the largest h_hi.
    rows = _o3_case(s_ref=s, recon_band=RECON_BAND, cands=[(8.0, (0.05, 0, 0, 0)), (8.6, (1.0, 0, 0, 0))])
    w1 = 2 * 3 * abs(0.86 - 9.6 / 9.9) + s
    per_rec = mx.headroom_per_reference(rows, params=rec)["R1"]
    assert per_rec["w_ind"] == pytest.approx(2 * E_REC + s, rel=1e-9) and sorted(per_rec["near_tie_h_hi"]) == ["c00", "c01"]
    assert mx.headroom_max_hi_ind(rows, params=rec) == pytest.approx(A_TWIN * (1 - 0.86 * (1 - w1)), rel=1e-9)
    assert sorted(mx.headroom_per_reference(rows)["R1"]["near_tie_h_hi"]) == ["c00"]


def test_o003_near_tie_set_takes_every_candidate_inside_the_band():
    # w_ind = 2 x 0.015 + 0.02 = 0.05: band to 8.4 nH. c00 8.0 (e_R 0.015), c01 8.1 (zero band), c02 8.3 (L(0.5) = 9.3,
    # e_R = 3 x 0.1 = 0.3, w = 0.62): three near ties, the third has the largest h_hi = a (1 - 0.83 x 0.38)
    rows = _o3_case(s_ref=0.02, cands=[(8.0, (0.05, 0, 0, 0)), (8.1, ZB), (8.3, (1.0, 0, 0, 0))])
    per = mx.headroom_per_reference(rows)["R1"]
    assert sorted(per["near_tie_h_hi"]) == ["c00", "c01", "c02"]
    assert per["near_tie_h_hi"]["c01"] == pytest.approx(A_TWIN * (1 - 0.81 * 0.98))
    assert mx.headroom_max_hi_ind(rows) == pytest.approx(A_TWIN * (1 - 0.83 * 0.38), rel=1e-9)


def test_o003_optimistic_secondary_with_a_band_and_without_band_solves():
    w = 2 * E_FULL + 0.02
    per = mx.headroom_per_reference(_o3_case(s_ref=0.02, cands=[(8.0, FULL_BAND)]))["R1"]
    assert per["opt_id"] == "c00" and per["h_opt_hi"] == pytest.approx(A_TWIN * (1 - 0.8 * (1 - w)), rel=1e-9)
    # c00 (8.0 nH) is 10 K hotter than W: fails both tests. c01 (8.2 nH, no band solves) has dies (351, 352, 352.5), GCI
    # 1.25 x 0.5 = 0.625: conservative 353.125 - 350 > 2 K fails, optimistic 351.875 - 350 <= 2 K passes, so c01 is the
    # optimistic pick and its column is None (not available). c02 (8.4 nH) is the A1 best. c01 lies outside K1's near-tie
    # band (8.0 x 1.02 = 8.16 nH), so it needs no band solves there.
    rows = _o3_case(s_ref=0.02, cands=[(8.0, ZB), (8.2, None), (8.4, ZB)],
                    cand_dies={0: [(360.0,) * 3] * 2, 1: [(351.0, 352.0, 352.5)] * 2})
    per = mx.headroom_per_reference(rows)["R1"]
    assert per["best_id"] == "c02" and per["opt_id"] == "c01" and per["h_opt_hi"] is None
    assert per["h_lo"] == pytest.approx(A_TWIN * (1 - 0.84 * 1.02))
    assert per["h_hi"] == pytest.approx(A_TWIN * (1 - 0.8 * 0.98))


def test_o003_ratio_middle_term_at_equal_differences():
    # |e21| = |e32| (exact in binary): r^p = 1, not contracting, so 3 max(|e21|, |e32|) = 0.75, as P3's middle_term
    spec = importlib.util.spec_from_file_location("o006_p3", REPO / "research" / "scripts" / "o006_p3_em_convergence.py")
    p3 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(p3)
    assert mx.ratio_middle_term(1.5, 1.25, 1.0) == 0.75 == p3.middle_term(1.5, 1.25, 1.0, 2.0)[1]


@pytest.mark.parametrize("metric", ["headroom_min_lo", "headroom_max_hi_ind"])
def test_o003_unknown_comparator_raises(metric):
    with pytest.raises(ValueError, match="comparator must be twin or reconstruction"):
        getattr(mx, metric)(_good_rows(), params={"comparator": "Reconstruction"})


def _drop_dies(rows, lid, keep=1):
    ds = [r for r in rows if r["kind"] == "die" and r["layout_id"] == lid]
    for r in ds[keep:]:
        rows.remove(r)


def _add_die(rows, lid, die_id="dx"):
    d = next(r for r in rows if r["kind"] == "die" and r["layout_id"] == lid)
    rows.append({**d, "die_id": die_id or d["die_id"]})


# Mutations of a good case that each metric must refuse. Each metric gets its own test, calling only that metric.
_COMMON = {
    "second_twin_layout_id": lambda rows: rows.append(dict(rows[1])),
    "second_reference_row": lambda rows: rows.append(dict(rows[0])),
    "no_reconstruction": lambda rows: [r.update(role="candidate") for r in rows if r.get("layout_id") == "recon"],
    "c00_band_column_missing": lambda rows: [r.pop("L_sub_c05_H") for r in rows
                                             if r.get("layout_id") == "c00" and r["kind"] == "layout"],
    "admissible_not_bool": lambda rows: rows[0].update(admissible="yes"),
    "fifteen_candidates": lambda rows: [rows.remove(r) for r in [r for r in rows if r.get("layout_id") == "c15"
                                                                 and r["kind"] == "layout"]],
    "L_term_nan": lambda rows: rows[0].update(L_term_H=math.nan),
    "L_term_negative": lambda rows: rows[0].update(L_term_H=-1e-9),
    "twin_band_column_missing": lambda rows: [r.pop("L_sub_thk_f_H") for r in rows if r.get("layout_id") == "twin"
                                              and r["kind"] == "layout"],
    "recon_die_missing": lambda rows: _drop_dies(rows, "recon"),
    "recon_die_added": lambda rows: _add_die(rows, "recon"),
    "twin_die_rows_absent": lambda rows: _drop_dies(rows, "twin", keep=0),
    "off_grid_without_snap_columns": lambda rows: rows[0].pop("L_snap025_H"),
    "unknown_layout_without_reference_row": lambda rows: rows.__setitem__(slice(0, 1), []),
    "off_grid_snap_check_key_missing": lambda rows: rows[0].pop("L_snapchk05_H"),
    "recon_die_duplicated": lambda rows: _add_die(rows, "recon", die_id=None),
    "L_term_bool": lambda rows: rows[0].update(L_term_H=True),
    "on_grid_string": lambda rows: rows[0].update(on_grid="false"),
}
_ONLY_A1 = {
    "best_candidate_die_missing": lambda rows: _drop_dies(rows, "c00"),
    "checked_candidate_without_dies": lambda rows: _drop_dies(rows, "c01", keep=0),
    "checked_candidate_tj_nan": lambda rows: [r.update(Tj_l1_K=math.nan) for r in rows
                                              if r["kind"] == "die" and r["layout_id"] == "c00"],
    "best_candidate_die_duplicated": lambda rows: _add_die(rows, "c00", die_id=None),
}
_ONLY_K1 = {
    "L1_all_missing": lambda rows: rows[0].pop("L1_min_all_H"),
    "L1_first_below_all": lambda rows: rows[0].update(L1_min_first5000_H=9.9e-9),
    "L1_first_missing": lambda rows: rows[0].update(L1_min_first5000_H=None),
    "L1_all_zero": lambda rows: rows[0].update(L1_min_all_H=0.0),
}
# The guard each mutation must trip (the message it raises), so a case cannot pass on an unrelated ValueError.
_MATCH = {
    "second_twin_layout_id": "layout twin appears twice", "second_reference_row": "more than one reference row",
    "no_reconstruction": "exactly one twin and one reconstruction", "c00_band_column_missing": "c00 L_sub_c05_H: missing",
    "admissible_not_bool": "admissible must be true or false", "fifteen_candidates": "15 candidate rows",
    "L_term_nan": "L_term_H: nan is not finite", "L_term_negative": "L_term_H must be non-negative",
    "twin_band_column_missing": "twin L_sub_thk_f_H: missing", "recon_die_missing": "has 1 dies, the twin has 2",
    "recon_die_added": "has 3 dies, the twin has 2", "twin_die_rows_absent": "no die rows for thermally checked layout twin",
    "off_grid_without_snap_columns": "off-grid reference row must carry",
    "unknown_layout_without_reference_row": "no reference row",
    "off_grid_snap_check_key_missing": "off-grid reference row must carry",
    "recon_die_duplicated": "die d0 of layout recon appears twice", "L_term_bool": "L_term_H: missing",
    "on_grid_string": "on_grid must be true or false",
    "best_candidate_die_missing": "has 1 dies, the twin has 2", "checked_candidate_without_dies": "candidate F3 checks has no",
    "checked_candidate_tj_nan": "Tj: nan is not finite", "best_candidate_die_duplicated": "die d0 of layout c00 appears twice",
    "L1_all_missing": "L1_min_all_H: missing", "L1_first_below_all": "first 5,000 is below the lowest of all",
    "L1_first_missing": "L1_min_first5000_H: missing", "L1_all_zero": "L1_min_all_H: 0.0 is not positive",
}


def _good_rows():
    return _o3_case(s_ref=0.02, cands=[(8.0, (0.05, 0.0, 0.0, 0.0))])


def test_o003_fail_closed_inputs_are_a_good_case_to_begin_with():
    rows = _good_rows()
    assert mx.headroom_min_lo(rows) > 0 and mx.headroom_max_hi_ind(rows) > 0
    assert set(_MATCH) == set(_COMMON) | set(_ONLY_A1) | set(_ONLY_K1)  # every mutation names its guard


@pytest.mark.parametrize("name", sorted(_COMMON) + sorted(_ONLY_A1))
def test_o003_fail_closed_headroom_min_lo(name):
    rows = _good_rows()
    ({**_COMMON, **_ONLY_A1})[name](rows)
    with pytest.raises(ValueError, match=_MATCH[name]):
        mx.headroom_min_lo(rows)


@pytest.mark.parametrize("name", sorted(_COMMON) + sorted(_ONLY_K1))
def test_o003_fail_closed_headroom_max_hi_ind(name):
    rows = _good_rows()
    ({**_COMMON, **_ONLY_K1})[name](rows)
    with pytest.raises(ValueError, match=_MATCH[name]):
        mx.headroom_max_hi_ind(rows)


# ------------------------------------------------------------------------------------------------ T0275 gaps (T0276)
# Parameter values fail closed (T0275 finding 2), and the two probe mutants that survived T0269's tests (findings 0, 1).
# Each value below names its key in the message. Before T0276, tj_limit_K = nan gave A1 = -a s_ref (every Tj comparison
# false) and floor = inf zeroed every GCI, so a divergent candidate became eligible; neither raised.
_BAD_PARAMS = {
    "floor_nan": ({"floor": math.nan}, "floor: nan is not finite"),
    "floor_inf": ({"floor": math.inf}, "floor: inf is not finite"),
    "floor_minus_inf": ({"floor": -math.inf}, "floor: -inf is not finite"),
    "floor_negative": ({"floor": -1e-3}, "floor: -0.001 is negative"),
    "floor_none": ({"floor": None}, "floor: missing"),
    "tj_limit_nan": ({"tj_limit_K": math.nan}, "tj_limit_K: nan is not finite"),
    "tj_limit_inf": ({"tj_limit_K": math.inf}, "tj_limit_K: inf is not finite"),
    "tj_limit_minus_inf": ({"tj_limit_K": -math.inf}, "tj_limit_K: -inf is not finite"),
    "tj_limit_negative": ({"tj_limit_K": -1.0}, "tj_limit_K: -1.0 is not positive"),
    "tj_limit_zero": ({"tj_limit_K": 0.0}, "tj_limit_K: 0.0 is not positive"),
    "tj_limit_none": ({"tj_limit_K": None}, "tj_limit_K: missing"),
}


@pytest.mark.parametrize("metric", ["headroom_min_lo", "headroom_max_hi_ind"])
@pytest.mark.parametrize("name", sorted(_BAD_PARAMS))
def test_o003_fail_closed_parameter_values(metric, name):
    params, match = _BAD_PARAMS[name]
    with pytest.raises(ValueError, match=match):
        getattr(mx, metric)(_good_rows(), params=params)
    with pytest.raises(ValueError, match=match):  # checked before any row is read: not "no counted reference"
        getattr(mx, metric)(_o3_case(admissible=False), params=params)
    with pytest.raises(ValueError, match=match):  # also through the dispatch, with the other parameter valid
        mx.compute(metric, _good_rows(), params={"floor": 1e-3, "tj_limit_K": 2.0, **params})


def test_o003_valid_parameter_values_at_their_bounds_are_accepted():
    rows = _good_rows()
    explicit = {"floor": 1e-3, "tj_limit_K": 2.0}  # the defaults, stated explicitly as the row contract asks
    assert mx.headroom_min_lo(rows, params=explicit) == mx.headroom_min_lo(rows)
    assert mx.headroom_max_hi_ind(rows, params=explicit) == mx.headroom_max_hi_ind(rows)
    # floor 0 is allowed (>= 0); tj_limit_K only needs to be positive: the zero-band case has c00 at W's 350 K, so a
    # 1e-9 K limit keeps it eligible
    assert mx.headroom_min_lo(rows, params={"floor": 0.0, "tj_limit_K": 1e-9}) == mx.headroom_min_lo(rows)


def test_o003_f3_missing_die_rows_in_batch_two_raise_when_a_candidate_is_below_the_comparator():
    # T0275 finding 0. c00..c03 (8.0..8.3 nH) are 10 K hotter than W, so batch 1 has no eligible candidate; c04..c15
    # (the padding, 12.00 nH and up) have no die rows; L(W) = 10 nH lies between order[0] = c00 and batch 2's first, c04.
    # F3 must check batch 2, so the missing rows raise. The shortcut (no die rows needed) applies only when L(comparator)
    # is at most the lowest shortlisted L_sub, order[0], not the first of the current batch.
    a, s = A_TWIN, 0.02
    cands = [(8.0 + 0.1 * k, ZB) for k in range(4)]
    hot = {k: [(360.0,) * 3] * 2 for k in range(4)}
    rows = _o3_case(s_ref=s, cands=cands, cand_dies=hot, no_dies=range(4, 16))
    with pytest.raises(ValueError, match="candidate F3 checks has no die rows"):
        mx.headroom_min_lo(rows)
    with pytest.raises(ValueError, match="candidate F3 checks has no die rows"):
        mx.headroom_per_reference(rows)
    # K1 runs no thermal check and needs no candidate die rows: inductance-only best c00, w_ind = s_ref, c01 (8.1 nH) a
    # near tie with the smaller h_hi
    assert mx.headroom_max_hi_ind(rows) == pytest.approx(a * (1 - 0.8 * 0.98))
    # control: the same case with batch 2's die rows present (350 K, as W). F3 checks both batches; c04 (12.00 nH) is
    # eligible but above W, so the twin rule decides
    per = mx.headroom_per_reference(_o3_case(s_ref=s, cands=cands, cand_dies=hot, no_dies=range(8, 16)))["R1"]
    assert per["f3_complete"] and per["checked_ids"] == [f"c{k:02d}" for k in range(8)]
    assert per["best_id"] is None and per["h_lo"] == pytest.approx(-a * s)


def test_o003_optimistic_secondary_applies_the_twin_rule_to_its_own_pick():
    # T0275 finding 1. c00 (8.0 nH) is 10 K hotter than W and fails both Tj tests. c01 (12.00 nH, the padding) passes both
    # and is the optimistic pick, with L_sub above L(W) = 10 nH: the twin rule gives h_opt_hi = a s_ref and no opt_id.
    # Without the rule it would be a (1 - 1.2 x 0.98) < 0.
    a, s = A_TWIN, 0.02
    hot0 = {0: [(360.0,) * 3] * 2}
    per = mx.headroom_per_reference(_o3_case(s_ref=s, cands=[(8.0, ZB)], cand_dies=hot0))["R1"]
    assert per["checked_ids"] == ["c00", "c01", "c02", "c03"] and per["best_id"] is None
    assert per["h_lo"] == pytest.approx(-a * s)
    assert per["opt_id"] is None and per["h_opt_hi"] == pytest.approx(a * s)
    # equality counts (L(W) <= L(opt)): c01 at exactly 10 nH with FULL_BAND (e_R(c01, twin) = E_FULL, as at 8 nH, since
    # the band offsets are absolute and W is 10 nH). The twin rule gives a s_ref; past it the band would give
    # a (1 - 1 x (1 - (2 E_FULL + s_ref))) = a (2 E_FULL + s_ref)
    per = mx.headroom_per_reference(_o3_case(s_ref=s, cands=[(8.0, ZB), (10.0, FULL_BAND)], cand_dies=hot0))["R1"]
    assert per["opt_id"] is None and per["h_opt_hi"] == pytest.approx(a * s)
    assert mx.ratio_band_estimate([10.0, 10.05, 10.09, 10.04, 10.07], [10.0] * 5) == pytest.approx(E_FULL, rel=1e-9)
    # the rule compares against the comparator (row contract section 5, item 9): twin 10 nH, reconstruction 10.1 nH
    # (F1(a1): 0.0099 <= 0.02), optimistic pick c01 at 10.05 nH between them, zero bands. Against the twin the rule decides
    # (a s_ref); against the reconstruction it does not: ar (1 - (10.05 / 10.1) x (1 - s_ref)) with ar = 10.1 / 17.1
    rows = _o3_case(s_ref=s, recon=10.1, cands=[(8.0, ZB), (10.05, ZB)], cand_dies=hot0)
    per = mx.headroom_per_reference(rows)["R1"]
    assert per["opt_id"] is None and per["h_opt_hi"] == pytest.approx(a * s)
    per = mx.headroom_per_reference(rows, params={"comparator": "reconstruction"})["R1"]
    ar = 10.1 / 17.1
    assert per["opt_id"] == "c01" and per["h_opt_hi"] == pytest.approx(ar * (1 - 10.05 / 10.1 * (1 - s)))
