"""Hand-computed cases for E007's metrics (T0396). Above the marker: the runner helpers of e007_metrics.py and the
mfos.metrics functions merged with 2fea4a6e as E007 uses them (self-pair exclusion, per-level max, ratio, step floor).
Below the marker: the bound F3 selects; that body is appended verbatim to tests/mfos/test_metrics.py by make_patch.py,
where ``mx`` is mfos.metrics."""
import math
import sys
from pathlib import Path

import numpy as np
import pytest
from scipy import stats as st

sys.path.insert(0, str(Path(__file__).resolve().parent))
import e007_metrics as em  # noqa: E402
from mfos import metrics as M  # noqa: E402

mx = em
HERE = Path(__file__).resolve().parent


def _die(lay, sw, i, ref, l1, load="P_ref", fam="u_shaped", dies=2):
    return {"kind": "die", "layout": lay, "family": fam, "dies": dies, "switch": sw, "die_index": i, "load": load,
            "tj_ref_K": ref, "tj_l1_K": l1}


def test_self_pair_excluded_in_pairwise_statistic():
    # layout a drawn twice (as a cluster bootstrap would) and b: with unit=layout only (a, b) pairs count, error
    # |(10 - 20) - (9.5 - 20.1)| = 0.6 each; without it the zero-error self-pair (a, a) is the minimum
    rows = [{"layout": "a", "family": "f", "dies": 2, "p": 10.0, "r": 9.5}] * 2 + \
           [{"layout": "b", "family": "f", "dies": 2, "p": 20.0, "r": 20.1}]
    kw = dict(pred="p", ref="r", strata=["family", "dies"])
    assert M.compute("pairwise_diff_error_quantile", rows, params={"q": 0.0, "unit": "layout"}, **kw) == \
        pytest.approx(0.6, abs=1e-12)
    assert M.compute("pairwise_diff_error_quantile", rows, params={"q": 0.0}, **kw) == 0.0


def test_hottest_die_is_the_reference_hottest_and_own_hottest_variant():
    # layout x: reference ranks HS1 hottest (101.0); L1 is 100.2 there but ranks LS0 hottest (101.5)
    # layout y: reference hottest LS1 (100.0, L1 100.4); L1's own hottest is also LS1
    rows = [_die("x", "HS", 0, 100.0, 99.0), _die("x", "HS", 1, 101.0, 100.2), _die("x", "LS", 0, 100.5, 101.5),
            _die("x", "LS", 1, 99.0, 99.0), _die("y", "HS", 0, 99.0, 99.1), _die("y", "HS", 1, 98.0, 98.0),
            _die("y", "LS", 0, 99.5, 99.4), _die("y", "LS", 1, 100.0, 100.4)]
    lay = {r["layout"]: r for r in em.layout_rows(rows)}
    assert (lay["x"]["hot_switch"], lay["x"]["hot_die_index"]) == ("HS", 1)
    assert lay["x"]["tj_hot_ref_K"] == 101.0 and lay["x"]["tj_hot_l1_K"] == 100.2 and lay["x"]["tj_ownhot_l1_K"] == 101.5
    assert (lay["y"]["hot_switch"], lay["y"]["hot_die_index"]) == ("LS", 1) and lay["y"]["tj_ownhot_l1_K"] == 100.4
    lr = list(lay.values())
    kw = dict(ref="tj_hot_ref_K", strata=["family", "dies"], params={"q": 1.0, "unit": "layout"})
    # A1: |(100.2 - 100.4) - (101 - 100)| = 1.2; own-hottest: |(101.5 - 100.4) - (101 - 100)| = 0.1
    assert M.compute("pairwise_diff_error_quantile", lr, pred="tj_hot_l1_K", **kw) == pytest.approx(1.2, abs=1e-12)
    assert M.compute("pairwise_diff_error_quantile", lr, pred="tj_ownhot_l1_K", **kw) == pytest.approx(0.1, abs=1e-12)
    # a tie in the reference goes to the first die in (switch, die_index) order
    tie = em.layout_rows([_die("z", "LS", 0, 100.0, 1.0), _die("z", "HS", 1, 100.0, 2.0), _die("z", "HS", 0, 99.0, 3.0)])
    assert (tie[0]["hot_switch"], tie[0]["hot_die_index"], tie[0]["tj_hot_l1_K"]) == ("HS", 1, 2.0)


def test_switch_spreads_and_leave_one_layout_out_null():
    # HS spreads (ref) 1, 2, 4 K over layouts a, b, c; L1 spreads 1.5, 2, 3
    rows = []
    for lay, (r0, r1), (p0, p1) in (("a", (100, 101), (100, 101.5)), ("b", (100, 102), (100, 102)),
                                    ("c", (100, 104), (100, 103))):
        rows += [_die(lay, "HS", 0, r0, p0), _die(lay, "HS", 1, r1, p1)]
    sw = {r["layout"]: r for r in em.switch_rows(rows)}
    assert [sw[k]["spread_ref_K"] for k in "abc"] == [1.0, 2.0, 4.0]
    assert [sw[k]["spread_l1_K"] for k in "abc"] == [1.5, 2.0, 3.0]
    assert [sw[k]["spread_null_K"] for k in "abc"] == [3.0, 2.5, 1.5]  # (2+4)/2, (1+4)/2, (1+2)/2
    with pytest.raises(ValueError):
        em.switch_rows(rows[:2])


def test_per_level_max_and_ratio_by_hand():
    rows = [{"load": "P", "p": 1.2, "r": 1.0, "n": 1.0}, {"load": "P", "p": 2.5, "r": 2.0, "n": 3.0},
            {"load": "H", "p": 0.9, "r": 1.0, "n": 1.1}, {"load": "H", "p": 2.7, "r": 2.0, "n": 2.0}]
    # per level max |p - r|: P 0.5, H 0.7 -> 0.7
    got = M.compute("max_over_groups", rows, pred="p", ref="r",
                    params={"fn": "quantile_abs_err", "by": "load", "inner": {"q": 1.0}})
    assert got == pytest.approx(0.7, abs=1e-12)
    # ratio on P: max |p - r| = 0.5 over max |n - r| = 1.0
    assert M.compute("quantile_abs_err_ratio", rows[:2], pred="p", ref="r", params={"null": "n", "q": 1.0}) == \
        pytest.approx(0.5, abs=1e-12)


def test_step_floor_and_unchanged_gci_capped():
    f = (300.000, 300.004, 300.007)  # steps 0.004, 0.003 K, both below 0.01 K: converged, 3 x 0.004
    assert M.gci_step_floor(*f, step_floor=0.01) == pytest.approx(0.012, abs=1e-12)
    g = (300.0, 300.2, 300.25)  # steps above the floor: gci_capped's value
    assert M.gci_step_floor(*g, step_floor=0.01) == M.gci_capped(*g)
    h = (300.0, 300.005, 300.02)  # one step below, one above: gci_capped
    assert M.gci_step_floor(*h, step_floor=0.01) == M.gci_capped(*h)


def test_patch_carries_the_tested_block_verbatim():
    src = (HERE / "e007_metrics.py").read_text()
    block = src.split("# >>> metrics.py\n", 1)[1].split("# <<< metrics.py\n", 1)[0]
    added = "".join(ln[1:] + "\n" for ln in (HERE / "e007_metrics.patch").read_text().splitlines()
                    if ln[:1] in ("+", " ") and not ln.startswith("+++"))  # the new side of every hunk
    assert block in added
    body = Path(__file__).read_text().split("# >>> shared tests\n", 1)[1]
    assert body in added


# >>> shared tests


# ------------------------------------------------------------------------------------------------ O002 F3 bound
def test_woodruff_bound_one_unit_per_term_by_hand():
    # terms 1, 2, 3, 4, one layout each; q 0.5: theta 2.5, share <= theta 1/2; jackknife shares 1/3, 1/3, 2/3, 2/3:
    # var = 3/4 x 4 (1/6)^2 = 1/12. With c = 1 (z, alpha = 1 - Phi(1)) the levels are 0.5 +/- 1/sqrt(12)
    alpha = float(1.0 - st.norm.cdf(1.0))
    se = 1.0 / math.sqrt(12.0)
    units = [("a",), ("b",), ("c",), ("d",)]
    up = mx.woodruff_bound([1, 2, 3, 4], units, 0.5, alpha, "upper", crit="z", rounding="linear")
    lo = mx.woodruff_bound([1, 2, 3, 4], units, 0.5, alpha, "lower", crit="z", rounding="linear")
    assert up == pytest.approx(1 + 3 * (0.5 + se), abs=1e-12) and lo == pytest.approx(1 + 3 * (0.5 - se), abs=1e-12)
    # t with 3 degrees of freedom, alpha 0.1, rounded outward: level 0.5 + 1.6377 / sqrt(12) = 0.973 -> 4; 0.027 -> 1
    assert mx.woodruff_bound([1, 2, 3, 4], units, 0.5, 0.1, "upper") == 4.0
    assert mx.woodruff_bound([1, 2, 3, 4], units, 0.5, 0.1, "lower") == 1.0
    # a level outside [0, 1], or fewer than 2 units: no finite bound
    assert mx.woodruff_bound([1, 2, 3, 4], units, 0.95, 0.05, "upper") == math.inf
    assert mx.woodruff_bound([1, 2], [("a",), ("a",)], 0.5, 0.05, "lower") == -math.inf


def test_woodruff_bound_on_pair_terms_deletes_every_pair_of_a_layout():
    # one die-average row per layout a, b, c (errors 0, 1, 3 K): pair terms ab 1, ac 3, bc 2; q 0.5 -> theta 2.
    # Deleting a leaves bc (share <= 2: 1), deleting b leaves ac (0), deleting c leaves ab (1): mean 2/3,
    # var = 2/3 x (1/9 + 4/9 + 1/9) = 4/9, se = 2/3. c = 0.5: levels 0.5 +/- 1/3 over sorted terms 1, 2, 3
    rows = [{"layout": k, "family": "f", "dies": 3, "r": 50.0, "p": 50.0 + e} for k, e in (("a", 0.0), ("b", 1.0),
                                                                                         ("c", 3.0))]
    alpha = float(1.0 - st.norm.cdf(0.5))
    pt, (lo, hi) = mx.quantile_ci("pairwise_diff_error_quantile", rows, pred="p", ref="r", strata=["family", "dies"],
                                  params={"q": 0.5, "unit": "layout"}, level=1.0 - 2.0 * alpha, cluster="layout",
                                  crit="z", rounding="linear")
    assert pt == mx.compute("pairwise_diff_error_quantile", rows, pred="p", ref="r", strata=["family", "dies"],
                            params={"q": 0.5, "unit": "layout"}) == pytest.approx(2.0, abs=1e-12)
    assert hi == pytest.approx(1 + 2 * (0.5 + 1 / 3), abs=1e-12) and lo == pytest.approx(1 + 2 * (0.5 - 1 / 3), abs=1e-12)


def test_quantile_ci_max_over_groups_uses_bonferroni_for_the_lower_bound():
    rng = np.random.default_rng(3)
    rows = [{"layout": f"L{j}", "load": ld, "p": float(rng.normal()), "r": 0.0} for j in range(30)
            for ld in ("P", "H") for _ in range(2)]
    params = {"fn": "quantile_abs_err", "by": "load", "inner": {"q": 0.9}}
    pt, (lo, hi) = mx.quantile_ci("max_over_groups", rows, pred="p", ref="r", params=params, level=0.9, cluster="layout")
    assert pt == mx.compute("max_over_groups", rows, pred="p", ref="r", params=params)
    per = {ld: [r for r in rows if r["load"] == ld] for ld in ("H", "P")}
    terms = {ld: (np.abs([r["p"] for r in rs]), [(r["layout"],) for r in rs]) for ld, rs in per.items()}
    assert hi == max(mx.woodruff_bound(x, u, 0.9, 0.05, "upper") for x, u in terms.values())
    assert lo == max(mx.woodruff_bound(x, u, 0.9, 0.025, "lower") for x, u in terms.values())
    assert lo <= pt <= hi


def test_woodruff_ratio_bound_exact_cases():
    rng = np.random.default_rng(5)
    x = np.abs(rng.normal(size=60))
    units = [(f"L{k // 2}",) for k in range(60)]
    # identical numerator and denominator terms: ratio 1 and zero linearised variance; 2 x the terms: ratio 2
    for side in ("upper", "lower"):
        assert mx.woodruff_ratio_bound(x, x, units, 0.95, 0.05, side, ratio="delta") == pytest.approx(1.0, abs=1e-12)
        assert mx.woodruff_ratio_bound(2 * x, x, units, 0.95, 0.05, side, ratio="delta") == \
            pytest.approx(2.0, abs=1e-12)
    y = np.abs(rng.normal(size=60)) * 2.0
    b_hi = mx.woodruff_bound(x, units, 0.9, 0.025, "upper") / mx.woodruff_bound(y, units, 0.9, 0.025, "lower")
    b_lo = mx.woodruff_bound(x, units, 0.9, 0.025, "lower") / mx.woodruff_bound(y, units, 0.9, 0.025, "upper")
    assert mx.woodruff_ratio_bound(x, y, units, 0.9, 0.05, "upper") == pytest.approx(b_hi, rel=1e-12)  # the default
    assert mx.woodruff_ratio_bound(x, y, units, 0.9, 0.05, "lower") == pytest.approx(b_lo, rel=1e-12)
    r = float(np.quantile(x, 0.9) / np.quantile(y, 0.9))
    lo_d = mx.woodruff_ratio_bound(x, y, units, 0.9, 0.05, "lower", ratio="delta")
    assert b_lo < lo_d < r < mx.woodruff_ratio_bound(x, y, units, 0.9, 0.05, "upper", ratio="delta") < b_hi


def test_quantile_ci_ratio_and_failures():
    rows = [{"layout": f"L{k // 2}", "p": 1.0 + 0.1 * k, "r": 1.0, "n": 1.0 + 0.3 * k} for k in range(40)]
    pt, (lo, hi) = mx.quantile_ci("quantile_abs_err_ratio", rows, pred="p", ref="r", params={"null": "n", "q": 0.9},
                                  level=0.9, cluster="layout")
    assert pt == pytest.approx(1.0 / 3.0, rel=1e-12) and lo <= pt <= hi  # every error is 1/3 of the null's
    with pytest.raises(ValueError):
        mx.quantile_ci("quantile_abs_err", rows, pred="p", ref="r", level=0.9)  # no cluster column
    with pytest.raises(ValueError):
        mx.quantile_ci("mape", rows, pred="p", ref="r", level=0.9, cluster="layout")
