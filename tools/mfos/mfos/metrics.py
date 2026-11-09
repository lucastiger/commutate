"""The evaluator's own implementation of acceptance metrics (evidence rules v2, audit 2026-10-19).

Runners compute their metrics for their own use; the evaluator recomputes every declared metric from the run's
rows artifact with this module and judges on its own numbers. One tested implementation, separate from
``mfos.stats`` (which registered runners import and which therefore never changes).

Rows are flat records: ``{"schema": "mfos.rows/1", "rows": [{"pred": ..., "ref": ..., "family": ..., ...}]}``.
Column names are declared per metric in the experiment spec (``recompute``).

Definitions (each function's docstring repeats its own):
  spearman                  Pearson correlation of average ranks; 0 when either rank vector is constant
  kendall_tau               Kendall tau-b
  mape                      mean |pred - ref| / |ref|
  mean_signed_rel_err       mean (pred / ref - 1)
  max_rel_err               max |pred / ref - 1|
  max_abs_err               max |pred - ref|
  max_gci_capped            max of the order-capped three-grid GCI (O006 A4; +inf if a sequence diverges)
  max_gci_consistency       max |p2 - r2| / (GCI(p) + GCI(r) [+ two-grid terms]) over two solvers' sequences (O006 A3)
  topk_recall               share of the predicted best k_frac that lie in the reference best within_frac
  within_strata_spearman    Spearman of log values centred on their stratum means
  discordance_by_gap        per gap bin: (pairs, discordant pairs), gap = |ref_i - ref_j| / min(ref_i, ref_j)
  group_selection_regret    per group ref[argmin pred] / min ref - 1, aggregated (mean or max)
  stratum_mean_offset_spread  max - min over strata of mean(pred / ref - 1)
  pairwise_diff_error_quantile  q-quantile over within-stratum pairs of |(pred_i - pred_j) - (ref_i - ref_j)|
  headroom_by_group         per group 1 - value[selected] / value[reference], aggregated
  optimism_ratio_by_group   per group (ref[reference] - ref[selected]) / (pred[reference] - pred[selected]), aggregated
  headroom_min_lo           O003 A1: min over counted references of h_lo = a (1 - r (1 + w)), twin rule first
  headroom_max_hi_ind       O003 K1: max over counted references of h_hi = a (1 - r_ind (1 - w_ind)), levelling
                            first (+inf if not levelled), then the twin rule, then near ties
"""
from __future__ import annotations

import itertools
import math
from typing import Any, Callable, Optional, Sequence

import numpy as np
from scipy import stats as _st

Rows = list[dict[str, Any]]
AGG: dict[str, Callable[[np.ndarray], float]] = {
    "mean": lambda a: float(np.mean(a)), "median": lambda a: float(np.median(a)),
    "min": lambda a: float(np.min(a)), "max": lambda a: float(np.max(a)),
}


# ------------------------------------------------------------------------------------------------ array metrics
def _arr(x: Sequence[float]) -> np.ndarray:
    return np.asarray(x, dtype=float)


def spearman(pred: Sequence[float], ref: Sequence[float]) -> float:
    """Pearson correlation of average ranks (ties share their mean rank); 0 when either rank vector is constant.
    Same definition as mfos.stats.spearman."""
    p, r = _arr(pred), _arr(ref)
    if len(p) != len(r) or len(p) < 3:
        raise ValueError("spearman needs two equal-length samples of size >= 3")
    rp, rr = _st.rankdata(p, method="average"), _st.rankdata(r, method="average")
    rp, rr = rp - rp.mean(), rr - rr.mean()
    denom = math.sqrt(float((rp**2).sum()) * float((rr**2).sum()))
    return float((rp * rr).sum() / denom) if denom > 0 else 0.0


def kendall_tau(pred: Sequence[float], ref: Sequence[float]) -> float:
    """Kendall tau-b; 0 when either sample is constant."""
    t = _st.kendalltau(_arr(pred), _arr(ref)).statistic
    return 0.0 if t is None or math.isnan(t) else float(t)


def mape(pred: Sequence[float], ref: Sequence[float]) -> float:
    """mean |pred - ref| / |ref|."""
    p, r = _arr(pred), _arr(ref)
    if np.any(r == 0):
        raise ValueError("mape undefined for zero reference values")
    return float(np.mean(np.abs(p - r) / np.abs(r)))


def mean_signed_rel_err(pred: Sequence[float], ref: Sequence[float]) -> float:
    """mean (pred / ref - 1)."""
    return float(np.mean(_arr(pred) / _arr(ref) - 1.0))


def max_rel_err(pred: Sequence[float], ref: Sequence[float]) -> float:
    """max |pred / ref - 1|."""
    return float(np.max(np.abs(_arr(pred) / _arr(ref) - 1.0)))


def max_abs_err(pred: Sequence[float], ref: Sequence[float]) -> float:
    """max |pred - ref|."""
    return float(np.max(np.abs(_arr(pred) - _arr(ref))))


def _finite_rows(*cols: np.ndarray) -> None:
    """Fail closed: no rows, or a NaN/inf anywhere, raises (the recomputation fails, so the evidence is INVALID rather
    than a value that could pass a criterion or fire a kill)."""
    if not cols[0].size:
        raise ValueError("no rows")
    if not all(np.all(np.isfinite(c)) for c in cols):
        raise ValueError("non-finite value in a metric column")


def max_scaled_abs_err(pred: Sequence[float], ref: Sequence[float], scale: Sequence[float]) -> float:
    """max over rows of |pred - ref| / scale, each row in units of its own scale (O006 A1/K1: the case scale)."""
    p, r, s = _arr(pred), _arr(ref), _arr(scale)
    _finite_rows(p, r, s)
    if np.any(s <= 0):
        raise ValueError("scale must be positive")
    return float(np.max(np.abs(p - r) / s))


def max_abs_err_gated(pred: Sequence[float], ref: Sequence[float], gate: Sequence[float], gate_max: float) -> float:
    """max |pred - ref| if every row's gate value is at most gate_max, otherwise +inf: a criterion on it is then not met
    (O006 A3: the scikit-fem cross-check counts only when scikit-fem's own convergence index is within its bound)."""
    p, r, g = _arr(pred), _arr(ref), _arr(gate)
    _finite_rows(p, r, g)
    if np.any(g > gate_max):
        return math.inf
    return float(np.max(np.abs(p - r)))


def max_col(values: Sequence[float]) -> float:
    """max of one column (O006 A4: the largest grid convergence index)."""
    v = _arr(values)
    _finite_rows(v)
    return float(np.max(v))


def gci_capped(f0: float, f1: float, f2: float, floor: float = 0.0) -> float:
    """Order-capped grid convergence index of the finest value f2 from three grids refined by r = 2 (O006 A4, D0012 and
    D0013). f0, f1, f2 are the values at levels 0 (coarsest), 1 and 2 (finest); d1 = f1 - f0, d2 = f2 - f1, each set to
    0 when its magnitude is below ``floor`` (O006: 1e-3 K, ten times the Picard tolerance, so iteration noise cannot pick
    the branch); rho = d2 / d1:

      d1 = d2 = 0                          0 (grid-independent)
      |rho| >= 1, or d1 = 0 < |d2|         +inf: divergent or stagnant, a criterion on it is not met
      -1 < rho < 0                         3 max(|d1|, |d2|): oscillatory, with Roache's factor for less reliable
                                           estimates (1.25 can understate a two-term error by up to 1.6x, T0191)
      0 <= rho < 1/4                       1.25 max(|d2|, |d1| / 4): observed order above 2 (a possibly lucky grid) is
                                           credited with order 2 from the coarser step; equal to the next branch at 1/4
      1/4 <= rho < 1                       1.25 |d2| / (2^p - 1), p = min(p_obs, 1), p_obs = log2(1 / rho)

    On [0, 1) the value is continuous in rho and never below the order-1-capped form 1.25 |d2| / (2^min(p_obs, 1) - 1)
    that T0181 found conservative at the singular corners. The safety factors 1.25 and 3 and the form |d2| / (r^p - 1)
    are Roache's (Verification and Validation in Computational Science and Engineering, Hermosa 1998, ch. 5); the
    order cap at 1, the branches and the floor are O006's rule (D0013 and its addenda)."""
    if floor < 0.0:
        raise ValueError("floor must be non-negative")
    d1, d2 = float(f1) - float(f0), float(f2) - float(f1)
    d1 = 0.0 if abs(d1) < floor else d1
    d2 = 0.0 if abs(d2) < floor else d2
    if d1 == 0.0 and d2 == 0.0:
        return 0.0
    if d1 == 0.0:
        return math.inf
    rho = d2 / d1
    if abs(rho) >= 1.0:
        return math.inf
    if rho < 0.0:
        return 3.0 * max(abs(d1), abs(d2))
    if rho < 0.25:
        return 1.25 * max(abs(d2), abs(d1) / 4.0)
    p = min(math.log2(1.0 / rho), 1.0)
    return 1.25 * abs(d2) / (2.0 ** p - 1.0)


def max_gci_capped(f0: Sequence[float], f1: Sequence[float], f2: Sequence[float], floor: float = 0.0) -> float:
    """max over rows of gci_capped(f0, f1, f2, floor) (O006 A4: every reported value's GCI recomputed from its three grid
    values); +inf when any row's sequence diverges."""
    a, b, c = _arr(f0), _arr(f1), _arr(f2)
    _finite_rows(a, b, c)
    return float(max(gci_capped(x, y, z, floor) for x, y, z in zip(a, b, c, strict=True)))


def two_grid_term(base: Sequence[float], doubled: Sequence[float]) -> np.ndarray:
    """1.25 x 2 |doubled - base| per row: the error of the undoubled grid for one doubling of one direction, assuming
    first order (error = |difference| / (2^1 - 1) x 2^1) with Roache's 1.25 (O006 A3: scikit-fem's through-thickness
    term, D0013 addendum 2)."""
    a, b = _arr(base), _arr(doubled)
    _finite_rows(a, b)
    return 2.5 * np.abs(b - a)


def max_gci_consistency(p0: Sequence[float], p1: Sequence[float], p2: Sequence[float],
                        r0: Sequence[float], r1: Sequence[float], r2: Sequence[float], floor: float = 0.0,
                        p_extra: Optional[Sequence[float]] = None, r_extra: Optional[Sequence[float]] = None,
                        ref_gci_cap: Optional[float] = None) -> float:
    """max over rows of |p2 - r2| / (gci_capped(p0, p1, p2) + p_extra + gci_capped(r0, r1, r2) + r_extra) (O006 A3: two
    independent solvers' finest values agree within their summed conservative estimates when this is at most 1). The
    optional extra terms are non-negative per-row errors a three-grid sequence leaves out, formed by two_grid_term from
    grid values in the rows (O006: scikit-fem's through-thickness term). A divergent sequence on either side gives
    +inf, as does a zero summed estimate with unequal values; a zero summed estimate with equal values gives 0. With
    ``ref_gci_cap``, a reference (cross-check) GCI above the cap on any row also gives +inf: the cross-check is not
    converged enough to judge, so the criterion is not met (O007 F5, I0099), rather than the run being INVALID."""
    n = len(_arr(p0))
    pe = _arr(p_extra) if p_extra is not None else np.zeros(n)
    re_ = _arr(r_extra) if r_extra is not None else np.zeros(n)
    cols = [_arr(x) for x in (p0, p1, p2, r0, r1, r2)]
    _finite_rows(*cols, pe, re_)
    if np.any(pe < 0) or np.any(re_ < 0):
        raise ValueError("extra error terms must be non-negative")
    if ref_gci_cap is not None and ref_gci_cap < 0:
        raise ValueError("ref_gci_cap must be non-negative")
    worst = 0.0
    for a0, a1, a2, b0, b1, b2, ea, eb in zip(*cols, pe, re_, strict=True):
        g_ref = gci_capped(b0, b1, b2, floor)
        if ref_gci_cap is not None and g_ref > ref_gci_cap:
            return math.inf
        g = gci_capped(a0, a1, a2, floor) + ea + g_ref + eb
        diff = abs(a2 - b2)
        if math.isinf(g) or (g == 0.0 and diff > 0.0):
            return math.inf
        worst = max(worst, diff / g if g > 0.0 else 0.0)
    return float(worst)


def topk_recall(pred: Sequence[float], ref: Sequence[float], k_frac: float = 0.1, within_frac: float = 0.2,
                lower_is_better: bool = True) -> float:
    """Share of the predicted best ``k_frac`` that lie inside the reference best ``within_frac``.
    Same definition as mfos.stats.topk_recall (k = max(1, round(k_frac n)), stable argsort)."""
    p, r = _arr(pred), _arr(ref)
    sgn = 1.0 if lower_is_better else -1.0
    k = max(1, int(round(k_frac * len(p))))
    w = max(1, int(round(within_frac * len(r))))
    top_pred = set(np.argsort(sgn * p)[:k].tolist())
    top_ref = set(np.argsort(sgn * r)[:w].tolist())
    return len(top_pred & top_ref) / k


def _groups(keys: Sequence[Any]) -> dict[Any, np.ndarray]:
    out: dict[Any, list[int]] = {}
    for i, k in enumerate(keys):
        out.setdefault(k, []).append(i)
    return {k: np.asarray(v) for k, v in out.items()}


def within_strata_spearman(pred: Sequence[float], ref: Sequence[float], strata: Sequence[Any]) -> float:
    """Spearman of log values centred on their stratum means: ranking power left once each stratum's level is known."""
    lp, lr = np.log(_arr(pred)), np.log(_arr(ref))
    for idx in _groups(strata).values():
        lp[idx] -= lp[idx].mean()
        lr[idx] -= lr[idx].mean()
    return spearman(lp, lr)


def discordance_by_gap(pred: Sequence[float], ref: Sequence[float],
                       edges: Sequence[float] = (0.0, 0.02, 0.05, 0.10, math.inf)) -> list[tuple[int, int]]:
    """For each bin [edges[i], edges[i+1]) of gap = |ref_i - ref_j| / min(ref_i, ref_j): (pairs, discordant pairs)."""
    p, r = _arr(pred), _arr(ref)
    out = [[0, 0] for _ in range(len(edges) - 1)]
    for i, j in itertools.combinations(range(len(p)), 2):
        gap = abs(r[i] - r[j]) / min(r[i], r[j])
        for b in range(len(edges) - 1):
            if edges[b] <= gap < edges[b + 1]:
                out[b][0] += 1
                out[b][1] += int(np.sign(p[i] - p[j]) != np.sign(r[i] - r[j]))
                break
    return [(a, b) for a, b in out]


def discordance_rate(pred: Sequence[float], ref: Sequence[float], lo: float = 0.0, hi: float = 0.02) -> float:
    """Discordant share of pairs whose gap lies in [lo, hi) (0 when there are none)."""
    (n, d), = discordance_by_gap(pred, ref, (lo, hi))
    return d / n if n else 0.0


def group_selection_regret(pred: Sequence[float], ref: Sequence[float], groups: Sequence[Any],
                           agg: str = "mean") -> float:
    """Per group, ref[argmin pred] / min(ref) - 1 (what choosing by pred loses), aggregated over groups."""
    p, r = _arr(pred), _arr(ref)
    vals = [r[idx][np.argmin(p[idx])] / r[idx].min() - 1.0 for idx in _groups(groups).values()]
    return AGG[agg](np.asarray(vals))


def stratum_mean_offset_spread(pred: Sequence[float], ref: Sequence[float], strata: Sequence[Any]) -> float:
    """max - min over strata of the stratum mean of pred / ref - 1."""
    e = _arr(pred) / _arr(ref) - 1.0
    means = [e[idx].mean() for idx in _groups(strata).values()]
    return float(max(means) - min(means))


def pairwise_diff_error_quantile(pred: Sequence[float], ref: Sequence[float], strata: Sequence[Any],
                                 q: float = 0.95) -> float:
    """q-quantile, over all pairs inside each stratum, of |(pred_i - pred_j) - (ref_i - ref_j)|."""
    p, r = _arr(pred), _arr(ref)
    errs = [abs((p[i] - p[j]) - (r[i] - r[j])) for idx in _groups(strata).values()
            for i, j in itertools.combinations(idx.tolist(), 2)]
    if not errs:
        raise ValueError("no within-stratum pairs")
    return float(np.quantile(errs, q))


def _by_role(rows: Rows, group: str, role: str) -> dict[Any, dict[str, dict[str, Any]]]:
    out: dict[Any, dict[str, dict[str, Any]]] = {}
    for row in rows:
        out.setdefault(row[group], {})[row[role]] = row
    return out


def headroom_by_group(rows: Rows, value: str, group: str = "group", role: str = "role", ref_role: str = "reference",
                      sel_role: str = "selected", agg: str = "median") -> float:
    """Per group 1 - value[selected] / value[reference] (e.g. L2 loop inductance), aggregated over groups."""
    vals = [1.0 - g[sel_role][value] / g[ref_role][value] for g in _by_role(rows, group, role).values()]
    return AGG[agg](np.asarray(vals, dtype=float))


def optimism_ratio_by_group(rows: Rows, pred: str, ref: str, group: str = "group", role: str = "role",
                            ref_role: str = "reference", sel_role: str = "selected", agg: str = "min") -> float:
    """Per group (ref[reference] - ref[selected]) / (pred[reference] - pred[selected]): the share of the improvement
    predicted by ``pred`` (e.g. L1) that the reference model (e.g. L2) confirms, aggregated over groups."""
    vals = []
    for g in _by_role(rows, group, role).values():
        a, b = g[ref_role], g[sel_role]
        vals.append((a[ref] - b[ref]) / (a[pred] - b[pred]))
    return AGG[agg](np.asarray(vals, dtype=float))


# ------------------------------------------------------------------------------------------------ O003 headroom (E008)
# O003 acceptance A1 and K1 (objective v5; D0016, D0017). Row contract: research/o003/e008_row_contract.md. Rows of kind
# "reference", "layout" and "die" (rows of other kinds are ignored); every inductance in H, every temperature in K.
HR_BAND = ("L_sub_c05_H", "L_sub_thk_c_H", "L_sub_thk_f_H", "L_sub_wire_f_H")  # the four 0.5 mm-cell band solves
HR_TJ = ("Tj_l0_K", "Tj_l1_K", "Tj_l2_K")  # per-die Tj max at thermal levels 0 (coarsest), 1, 2
HR_SHORTLIST, HR_BATCH, HR_MAX_CHECKED = 16, 4, 8  # O003 F3: D0008 shortlist; thermal checks in batches of 4, at most 8
HR_PARAMS = frozenset({"L_term_H", "comparator", "floor", "tj_limit_K"})


def _hr_num(v: Any, name: str) -> float:
    if v is None or isinstance(v, bool):
        raise ValueError(f"{name}: missing")
    x = float(v)
    if not math.isfinite(x):
        raise ValueError(f"{name}: {v!r} is not finite")
    return x


def _hr_pos(v: Any, name: str) -> float:
    x = _hr_num(v, name)
    if x <= 0.0:
        raise ValueError(f"{name}: {v!r} is not positive")
    return x


def _hr_check_params(p: dict[str, Any]) -> None:
    """Fail closed on parameter values (T0275 finding 2): floor (K) must be finite and >= 0, tj_limit_K (K) finite and
    > 0. A nan limit makes every Tj comparison false, so no candidate is eligible and A1 fails silently; gci_capped reads
    a nan floor as 0 and an infinite one zeroes every GCI, and it rejects a negative floor only once a die is bounded.
    Checked here, before any row is read, so both metrics refuse the spec. Absent keys take the defaults (floor 1e-3,
    tj_limit_K 2.0)."""
    if "floor" in p and _hr_num(p["floor"], "floor") < 0.0:
        raise ValueError(f"floor: {p['floor']!r} is negative")
    if "tj_limit_K" in p:
        _hr_pos(p["tj_limit_K"], "tj_limit_K")


def _hr_key(row: dict[str, Any], col: str) -> str:
    if row.get(col) is None:
        raise ValueError(f"a {row.get('kind')} row has no {col}")
    return str(row[col])


def ratio_middle_term(fc: float, fm: float, ff: float) -> float:
    """O006 P3's thickness term: the error of the middle value fm of three levels (fc coarse, fm the production count,
    ff fine), refined by a constant ratio r (research/scripts/o006_p3_em_convergence.py, middle_term). With e21 = fm - ff
    and e32 = fc - fm the sequence is monotone iff e21 e32 > 0 and |e21| < |e32|; then r^p_obs = e32 / e21 and the term is
    1.25 |e21| r^p / (r^p - 1), which does not depend on r; otherwise it is 3 max(|e21|, |e32|) (Roache 1998, ch. 5)."""
    e21, e32 = float(fm) - float(ff), float(fc) - float(fm)
    if e21 * e32 > 0.0 and abs(e21) < abs(e32):
        rp = e32 / e21
        return 1.25 * abs(e21) * rp / (rp - 1.0)
    return 3.0 * max(abs(e21), abs(e32))


def ratio_band_estimate(x: Sequence[float], c: Sequence[float]) -> float:
    """e_R of the ratio R = L(x) / L(c), level by level from the same solves (O006 P3 recommendation 2; O003 A1). x and c
    hold five inductances each, in the order: 0.25 mm cells (production); then at 0.5 mm cells production layers 10/6/6
    and wires, layers 5/3/3, layers 20/12/12, wire annuli bisected with 12 filaments per ring (HR_BAND). Linear sum
    (conservative): e_R = 3 |R(0.25) - R(0.5)| + ratio_middle_term(R(5/3/3), R(0.5), R(20/12/12)) + 3 |R(wire) - R(0.5)|.
    3 |..| is Roache's two-level GCI 3 |f2 - f1| / (r - 1) at r = 2 (P3's lateral and filament terms)."""
    xs, cs = [float(v) for v in x], [float(v) for v in c]
    if len(xs) != 5 or len(cs) != 5:
        raise ValueError("ratio_band_estimate needs five levels per layout")
    if not all(math.isfinite(v) and v > 0.0 for v in xs + cs):
        raise ValueError("ratio_band_estimate needs finite positive inductances")
    r025, r05, r_thk_c, r_thk_f, r_wire = (a / b for a, b in zip(xs, cs, strict=True))
    return 3.0 * abs(r025 - r05) + ratio_middle_term(r_thk_c, r05, r_thk_f) + 3.0 * abs(r_wire - r05)


def snapping_bias(on_grid: bool, l_snap025: Any = None, l_snap05: Any = None, l_chk0125: Any = None,
                  l_chk05: Any = None) -> float:
    """s_ref of O003 A1. 0 when the reference is already on the 0.5 mm grid. Otherwise 2 |L(reference snapped to 0.25 mm)
    / L(reference snapped to 0.5 mm) - 1|, both solved at 0.25 mm cells, replaced by the pre-registration snapping check's
    relative difference |L(snapped to 0.125 mm) / L(snapped to 0.5 mm) - 1| (both at 0.125 mm cells) when that is larger.
    A check that could not be completed is passed as None for both values (O003 notes: reported to the founder before
    registration); one value without the other raises."""
    if not isinstance(on_grid, bool):
        raise ValueError("on_grid must be true or false")
    if on_grid:
        return 0.0
    s = 2.0 * abs(_hr_pos(l_snap025, "L_snap025_H") / _hr_pos(l_snap05, "L_snap05_H") - 1.0)
    if l_chk0125 is not None or l_chk05 is not None:
        s = max(s, abs(_hr_pos(l_chk0125, "L_snapchk0125_H") / _hr_pos(l_chk05, "L_snapchk05_H") - 1.0))
    return s


def tj_bounds(dies: Sequence[Sequence[float]], floor: float = 1e-3,
              n_dies: Optional[int] = None) -> tuple[float, float, float, float, int]:
    """One layout's Tj interval quantities (O003 scope_in, the Tj limit; C004 caveat 1; D0013). ``dies`` holds, per die,
    the Tj max (K) at thermal levels 0, 1, 2 of that layout's own three grids. T_i is the level-2 value and GCI_i =
    gci_capped(level 0, 1, 2, floor). Returns (max_i T_i, max_i GCI_i, upper, lower, n_inf): upper = max_i (T_i + GCI_i),
    +inf if any GCI_i is +inf; lower = max over the dies with finite GCI of (T_i - GCI_i), -inf if there is none (a die
    whose GCI is +inf bounds nothing and drops out of a lower bound); n_inf counts the dies with GCI_i = +inf.
    ``n_dies``, when given, is the die count the layout must carry (scope_in fixes the die count, so every thermally
    checked layout carries the twin's); any other count raises, because a layout missing its hottest die would be judged on
    the dies that remain."""
    if not dies:
        raise ValueError("a thermally checked layout needs at least one die")
    if n_dies is not None and len(dies) != n_dies:
        raise ValueError(f"a thermally checked layout has {len(dies)} dies, the twin has {n_dies}")
    t_max = g_max = upper = lower = -math.inf
    n_inf = 0
    for d in dies:
        f0, f1, f2 = (_hr_num(v, "Tj") for v in d)
        g = gci_capped(f0, f1, f2, floor)
        t_max, g_max, upper = max(t_max, f2), max(g_max, g), max(upper, f2 + g)
        if math.isinf(g):
            n_inf += 1
        else:
            lower = max(lower, f2 - g)
    return t_max, g_max, upper, lower, n_inf


def tj_conservative_ok(cand: Sequence[float], twin: Sequence[float], limit_k: float = 2.0) -> bool:
    """O003's conservative Tj test (decides A1), on tj_bounds tuples: max_i (T_i(C) + GCI_i(C)) - max_j (T_j(W) -
    GCI_j(W)) <= limit_k. A +inf GCI on C fails it; a +inf GCI on W drops that die out of W's lower bound."""
    return cand[2] - twin[3] <= limit_k


def tj_optimistic_ok(cand: Sequence[float], twin: Sequence[float], limit_k: float = 2.0) -> bool:
    """O003's optimistic Tj test (secondary column only), on tj_bounds tuples: max_i (T_i(C) - GCI_i(C)) - max_j (T_j(W)
    + GCI_j(W)) <= limit_k. A +inf GCI on W makes every candidate pass it."""
    return cand[3] - twin[2] <= limit_k


def twin_gate_inductance(twin5: Sequence[float], recon5: Sequence[float], s_ref: float) -> bool:
    """O003 F1(a1): |1 - L_sub(W) / L_sub(reference)| <= 2 e_R(W, reference) + s_ref, from the five levels of each."""
    return abs(1.0 - float(twin5[0]) / float(recon5[0])) <= 2.0 * ratio_band_estimate(twin5, recon5) + s_ref


def twin_gate_thermal(twin: Sequence[float], recon: Sequence[float]) -> bool:
    """O003 F1(a2), on tj_bounds tuples: |max_i T_i(W) - max_j T_j(reference)| <= G(W) + G(reference), each G the largest
    per-die gci_capped of that layout's own three grids. Taken literally, a +inf G passes the gate."""
    return abs(twin[0] - recon[0]) <= twin[1] + recon[1]


def headroom_lo(a: float, r: float, w: float) -> float:
    """O003 A1: h_lo = a (1 - r (1 + w)), the lower end of the module-level headroom band."""
    return a * (1.0 - r * (1.0 + w))


def headroom_hi(a: float, r: float, w: float) -> float:
    """O003 K1: h_hi = a (1 - r (1 - w)), the upper end of the module-level headroom band."""
    return a * (1.0 - r * (1.0 - w))


def _hr_tables(rows: Rows) -> dict[str, dict[str, Any]]:
    refs: dict[str, dict[str, Any]] = {}
    for row in rows:
        kind = row.get("kind")
        if kind not in ("reference", "layout", "die"):
            continue
        rid = _hr_key(row, "reference_id")
        t = refs.setdefault(rid, {"ref": None, "layouts": {}, "dies": {}})
        if kind == "reference":
            if t["ref"] is not None:
                raise ValueError(f"reference {rid}: more than one reference row")
            t["ref"] = row
        elif kind == "layout":
            lid = _hr_key(row, "layout_id")
            if lid in t["layouts"]:
                raise ValueError(f"reference {rid}: layout {lid} appears twice")
            t["layouts"][lid] = row
        else:
            dies = t["dies"].setdefault(_hr_key(row, "layout_id"), {})
            did = _hr_key(row, "die_id")
            if did in dies:
                raise ValueError(f"reference {rid}: die {did} of layout {row['layout_id']} appears twice")
            dies[did] = tuple(row.get(c) for c in HR_TJ)
    for rid, t in refs.items():
        if t["ref"] is None:
            raise ValueError(f"reference {rid}: layout or die rows but no reference row")
    return refs


def _hr_reference(t: dict[str, Any], pred: str, params: dict[str, Any], lo: bool, hi: bool) -> dict[str, Any]:
    """Every per-reference quantity of A1 (lo) and K1 (hi) for one reference, in the rule order of O003 v5."""
    ref = t["ref"]
    rid = str(ref["reference_id"])
    admissible = ref.get("admissible")
    if not isinstance(admissible, bool):
        raise ValueError(f"reference {rid}: admissible must be true or false")
    out: dict[str, Any] = {"reference_id": rid, "admissible": admissible, "counted": False}
    if not admissible:
        return out
    roles: dict[str, list[dict[str, Any]]] = {}
    for lay in t["layouts"].values():
        roles.setdefault(str(lay.get("role")), []).append(lay)
    if len(roles.get("twin", [])) != 1 or len(roles.get("reconstruction", [])) != 1:
        raise ValueError(f"reference {rid}: needs exactly one twin and one reconstruction layout row")
    twin, recon = roles["twin"][0], roles["reconstruction"][0]
    cands = roles.get("candidate", [])
    if len(cands) != HR_SHORTLIST:
        raise ValueError(f"reference {rid}: {len(cands)} candidate rows, the shortlist has {HR_SHORTLIST}")
    floor = float(params.get("floor", 1e-3))
    limit = float(params.get("tj_limit_K", 2.0))

    def lsub(lay: dict[str, Any]) -> float:
        return _hr_pos(lay.get(pred), f"{rid}/{lay['layout_id']} {pred}")

    def five(lay: dict[str, Any]) -> tuple[float, ...]:
        return (lsub(lay),) + tuple(_hr_pos(lay.get(c), f"{rid}/{lay['layout_id']} {c}") for c in HR_BAND)

    def has_dies(lay: dict[str, Any]) -> bool:
        return bool(t["dies"].get(str(lay["layout_id"])))

    n_dies = len(t["dies"].get(str(twin["layout_id"]), ()))  # scope_in fixes the die count: the twin's

    def bounds(lay: dict[str, Any]) -> tuple[float, float, float, float, int]:
        if not has_dies(lay):
            raise ValueError(f"reference {rid}: no die rows for thermally checked layout {lay['layout_id']}")
        return tj_bounds(list(t["dies"][str(lay["layout_id"])].values()), floor, n_dies)

    on_grid = ref.get("on_grid")
    snap_cols = ("L_snap025_H", "L_snap05_H", "L_snapchk0125_H", "L_snapchk05_H")
    if on_grid is False and any(c not in ref for c in snap_cols):
        raise ValueError(f"reference {rid}: an off-grid reference row must carry {', '.join(snap_cols)} (null allowed "
                         "only for the snapping check)")
    s_ref = snapping_bias(on_grid, *(ref.get(c) for c in snap_cols))
    tw_b, rec_b = bounds(twin), bounds(recon)
    gate_a1 = twin_gate_inductance(five(twin), five(recon), s_ref)
    gate_a2 = twin_gate_thermal(tw_b, rec_b)
    out.update(s_ref=s_ref, gate_a1=gate_a1, gate_a2=gate_a2, counted=gate_a1 and gate_a2, L_sub_twin_H=lsub(twin),
               L_sub_recon_H=lsub(recon), tj_twin=tw_b, tj_recon=rec_b)
    if not out["counted"]:
        return out
    comparator = params.get("comparator", "twin")
    if comparator not in ("twin", "reconstruction"):
        raise ValueError(f"comparator must be twin or reconstruction, not {comparator!r}")
    comp = twin if comparator == "twin" else recon
    l_term = _hr_num(params["L_term_H"] if "L_term_H" in params else ref.get("L_term_H"), f"{rid} L_term_H")
    if l_term < 0.0:
        raise ValueError(f"reference {rid}: L_term_H must be non-negative")
    lc = lsub(comp)
    a = lc / (lc + l_term)
    order = sorted(cands, key=lambda c: (lsub(c), str(c["layout_id"])))  # ascending L_sub, ties by layout_id
    out.update(comparator=comparator, L_term_H=l_term, a=a)

    if lo:
        # F3: thermal checks in ascending L_sub order, batches of 4, stop after the first batch holding a candidate that
        # meets the conservative test, at most 8. Candidates are always tested against the twin W, whatever the
        # comparator, so the feasible set cannot move (scope_in, T0252).
        checked: list[tuple[dict[str, Any], tuple[float, float, float, float, int]]] = []
        eligible: list[dict[str, Any]] = []
        f3_complete = True
        for start in range(0, HR_MAX_CHECKED, HR_BATCH):
            batch = order[start:start + HR_BATCH]
            if not all(has_dies(c) for c in batch):
                if lc <= lsub(order[0]):  # the comparator beats every shortlisted candidate: the twin rule decides
                    f3_complete = False
                    break
                raise ValueError(f"reference {rid}: a candidate F3 checks has no die rows")
            for c in batch:
                cb = bounds(c)
                checked.append((c, cb))
                if tj_conservative_ok(cb, tw_b, limit):
                    eligible.append(c)
            if eligible:
                break
        # twin rule first: best is the comparator when no candidate is eligible or none is below it
        best = eligible[0] if eligible else None
        if best is None or lc <= lsub(best):
            out.update(best_id=None, r=1.0, e_R=0.0, w=s_ref, h_lo=headroom_lo(a, 1.0, s_ref))
        else:
            e = ratio_band_estimate(five(best), five(comp))
            r = lsub(best) / lc
            out.update(best_id=str(best["layout_id"]), r=r, e_R=e, w=2.0 * e + s_ref,
                       h_lo=headroom_lo(a, r, 2.0 * e + s_ref))
        out.update(f3_complete=f3_complete, n_thermal_checked=len(checked), n_tj_rejected=len(checked) - len(eligible),
                   checked_ids=[str(c["layout_id"]) for c, _ in checked],
                   n_tj_inf=tw_b[4] + rec_b[4] + sum(cb[4] for _, cb in checked))
        if hi:  # secondary: the h_hi of the lowest-L_sub checked candidate that passes the optimistic test
            opt = next((c for c, cb in checked if tj_optimistic_ok(cb, tw_b, limit)), None)
            if opt is None or lc <= lsub(opt):
                out.update(opt_id=None, h_opt_hi=headroom_hi(a, 1.0, s_ref))
            else:
                try:
                    eo = ratio_band_estimate(five(opt), five(comp))
                    h_opt: Optional[float] = headroom_hi(a, lsub(opt) / lc, 2.0 * eo + s_ref)
                except ValueError:  # no band solves on that candidate: the secondary column is not available
                    h_opt = None
                out.update(opt_id=str(opt["layout_id"]), h_opt_hi=h_opt)

    if hi:
        ind = order[0]
        # levelling first: it decides whether this reference's search may support a kill at all (D0017 item 9); it is a
        # property of the search, so its w_ind is always the twin pair's
        w_lev = 2.0 * ratio_band_estimate(five(ind), five(twin)) + s_ref
        l1_first = _hr_pos(ref.get("L1_min_first5000_H"), f"{rid} L1_min_first5000_H")
        l1_all = _hr_pos(ref.get("L1_min_all_H"), f"{rid} L1_min_all_H")
        if l1_first < l1_all:
            raise ValueError(f"reference {rid}: the lowest L1 of the first 5,000 is below the lowest of all 20,000")
        levelled = l1_first <= (1.0 + w_lev) * l1_all
        out.update(ind_id=str(ind["layout_id"]), w_levelling=w_lev, levelled=levelled)
        if not levelled:
            out.update(near_tie_h_hi={}, w_ind=None, r_ind=None, h_hi=math.inf)
        elif lc <= lsub(ind):  # twin rule, before the near-tie rule
            out.update(near_tie_h_hi={}, w_ind=s_ref, r_ind=1.0, h_hi=headroom_hi(a, 1.0, s_ref))
        else:
            w_ind = 2.0 * ratio_band_estimate(five(ind), five(comp)) + s_ref
            ties: dict[str, float] = {}
            for c in order:
                if lsub(c) <= (1.0 + w_ind) * lsub(ind):
                    wc = 2.0 * ratio_band_estimate(five(c), five(comp)) + s_ref
                    ties[str(c["layout_id"])] = headroom_hi(a, lsub(c) / lc, wc)
            out.update(near_tie_h_hi=ties, w_ind=w_ind, r_ind=lsub(ind) / lc, h_hi=max(ties.values()))
    return out


def headroom_per_reference(rows: Rows, pred: str = "L_sub_H", params: Optional[dict[str, Any]] = None,
                           lo: bool = True, hi: bool = True) -> dict[str, dict[str, Any]]:
    """Every per-reference quantity of O003 A1 and K1 (reported columns; the two metrics below take their min / max).
    ``pred`` names the 0.25 mm-cell L_sub column (the null of F1 substitutes it); ``params`` may hold L_term_H (H, the
    sensitivity at 0 and 17.5 nH), comparator ("twin", or "reconstruction" for the secondary values), floor (K, default
    1e-3) and tj_limit_K (default 2.0). Unknown keys raise, so a mistyped parameter cannot silently change a metric; so
    do a floor that is not finite or is negative and a tj_limit_K that is not finite or not positive."""
    p = dict(params or {})
    unknown = sorted(set(p) - HR_PARAMS)
    if unknown:
        raise ValueError(f"unknown headroom params {unknown}; known: {sorted(HR_PARAMS)}")
    _hr_check_params(p)
    tables = _hr_tables(rows)
    if not tables:
        raise ValueError("no reference rows")
    return {rid: _hr_reference(t, pred, p, lo, hi) for rid, t in sorted(tables.items())}


def headroom_min_lo(rows: Rows, pred: str = "L_sub_H", params: Optional[dict[str, Any]] = None) -> float:
    """O003 A1: minimum over counted references (admissible, passing twin gates F1(a1) and (a2)) of h_lo = a (1 - r (1 +
    w)). Per reference: a = L_sub(twin) / (L_sub(twin) + L_term); best = the lowest-L_sub candidate meeting the
    conservative Tj test among those thermally checked under F3 (ascending L_sub, batches of 4, at most 8); twin rule
    first: if no candidate is eligible or the twin's L_sub is at most best's, r = 1, e_R = 0 and h_lo = -a s_ref;
    otherwise r = L_sub(best) / L_sub(twin) and w = 2 e_R + s_ref with e_R = ratio_band_estimate(best, twin). No counted
    reference raises (E008 INVALID, F1(a))."""
    per = headroom_per_reference(rows, pred, params, lo=True, hi=False)
    vals = [v["h_lo"] for v in per.values() if v["counted"]]
    if not vals:
        raise ValueError("no counted reference (O003 F1(a): E008 is INVALID)")
    return float(min(vals))


def headroom_max_hi_ind(rows: Rows, pred: str = "L_sub_H", params: Optional[dict[str, Any]] = None) -> float:
    """O003 K1: maximum over counted references of h_hi = a (1 - r_ind (1 - w_ind)), from the inductance-only best (the
    lowest-L_sub candidate of the 16-candidate shortlist, no Tj limit). Rule order per reference (D0017): (1) levelling:
    unless the lowest L1 of the first 5,000 candidates is at most (1 + w_ind) times the lowest of all 20,000, h_hi = +inf;
    (2) twin rule: if the twin's L_sub is at most every shortlisted candidate's, h_hi = a s_ref; (3) near ties: h_hi is
    the largest h_hi over the shortlisted candidates whose L_sub is at most (1 + w_ind) L_sub(inductance-only best), each
    with its own e_R. No counted reference raises (E008 INVALID, F1(a))."""
    per = headroom_per_reference(rows, pred, params, lo=False, hi=True)
    vals = [v["h_hi"] for v in per.values() if v["counted"]]
    if not vals:
        raise ValueError("no counted reference (O003 F1(a): E008 is INVALID)")
    return float(max(vals))


# ------------------------------------------------------------------------------------------------ records adapter
def strata_keys(rows: Rows, columns: Sequence[str]) -> list[str]:
    return [":".join(str(row[c]) for c in columns) for row in rows]


def _col(rows: Rows, name: Optional[str]) -> np.ndarray:
    if not name:
        raise ValueError("this metric needs a column name")
    return np.asarray([row[name] for row in rows], dtype=float)


def _two_grid(rows: Rows, params: Optional[dict[str, Any]], key: str) -> Optional[np.ndarray]:
    names = (params or {}).get(key)
    if names is None:
        return None
    if not isinstance(names, (list, tuple)) or len(names) != 2:
        raise ValueError(f"params.{key} must name two columns, the base grid first")
    return two_grid_term(_col(rows, names[0]), _col(rows, names[1]))


def _levels(rows: Rows, params: Optional[dict[str, Any]], key: str) -> list[np.ndarray]:
    names = (params or {}).get(key)
    if not isinstance(names, (list, tuple)) or len(names) != 3:
        raise ValueError(f"params.{key} must name three columns, coarsest level first")
    return [_col(rows, n) for n in names]


# name -> f(rows, pred, ref, strata, group, role, params) -> float
METRICS: dict[str, Callable[..., float]] = {
    "spearman": lambda rows, pred, ref, **_: spearman(_col(rows, pred), _col(rows, ref)),
    "kendall_tau": lambda rows, pred, ref, **_: kendall_tau(_col(rows, pred), _col(rows, ref)),
    "mape": lambda rows, pred, ref, **_: mape(_col(rows, pred), _col(rows, ref)),
    "mean_signed_rel_err": lambda rows, pred, ref, **_: mean_signed_rel_err(_col(rows, pred), _col(rows, ref)),
    "max_rel_err": lambda rows, pred, ref, **_: max_rel_err(_col(rows, pred), _col(rows, ref)),
    "max_abs_err": lambda rows, pred, ref, **_: max_abs_err(_col(rows, pred), _col(rows, ref)),
    "max_scaled_abs_err": lambda rows, pred, ref, params=None, **_: max_scaled_abs_err(
        _col(rows, pred), _col(rows, ref), _col(rows, (params or {}).get("scale"))),
    "max_abs_err_gated": lambda rows, pred, ref, params=None, **_: max_abs_err_gated(
        _col(rows, pred), _col(rows, ref), _col(rows, (params or {}).get("gate")), float((params or {})["gate_max"])),
    "max_col": lambda rows, pred, **_: max_col(_col(rows, pred)),  # the column is named by ``pred``
    "max_gci_capped": lambda rows, params=None, **_: max_gci_capped(*_levels(rows, params, "levels"),
                                                                    floor=float((params or {}).get("floor", 0.0))),
    "max_gci_consistency": lambda rows, params=None, **_: max_gci_consistency(
        *_levels(rows, params, "pred_levels"), *_levels(rows, params, "ref_levels"),
        floor=float((params or {}).get("floor", 0.0)),
        p_extra=_two_grid(rows, params, "pred_zpair"), r_extra=_two_grid(rows, params, "ref_zpair"),
        ref_gci_cap=None if (params or {}).get("ref_gci_cap") is None else float(params["ref_gci_cap"])),
    "topk_recall": lambda rows, pred, ref, params=None, **_: topk_recall(_col(rows, pred), _col(rows, ref),
                                                                          **(params or {})),
    "within_strata_spearman": lambda rows, pred, ref, strata, **_: within_strata_spearman(
        _col(rows, pred), _col(rows, ref), strata_keys(rows, strata)),
    "discordance_rate": lambda rows, pred, ref, params=None, **_: discordance_rate(
        _col(rows, pred), _col(rows, ref), **(params or {})),
    "group_selection_regret": lambda rows, pred, ref, group, params=None, **_: group_selection_regret(
        _col(rows, pred), _col(rows, ref), [row[group] for row in rows], **(params or {})),
    "stratum_mean_offset_spread": lambda rows, pred, ref, strata, **_: stratum_mean_offset_spread(
        _col(rows, pred), _col(rows, ref), strata_keys(rows, strata)),
    "pairwise_diff_error_quantile": lambda rows, pred, ref, strata, params=None, **_: pairwise_diff_error_quantile(
        _col(rows, pred), _col(rows, ref), strata_keys(rows, strata), **(params or {})),
    "headroom_by_group": lambda rows, pred, ref, group, role, params=None, **_: headroom_by_group(
        rows, ref, group=group, role=role, **(params or {})),
    "optimism_ratio_by_group": lambda rows, pred, ref, group, role, params=None, **_: optimism_ratio_by_group(
        rows, pred, ref, group=group, role=role, **(params or {})),
    "headroom_min_lo": lambda rows, pred=None, params=None, **_: headroom_min_lo(rows, pred or "L_sub_H", params),
    "headroom_max_hi_ind": lambda rows, pred=None, params=None, **_: headroom_max_hi_ind(rows, pred or "L_sub_H",
                                                                                          params),
}


def compute(fn: str, rows: Rows, *, pred: Optional[str] = None, ref: Optional[str] = None,
            strata: Sequence[str] = (), group: Optional[str] = None, role: Optional[str] = None,
            params: Optional[dict[str, Any]] = None) -> float:
    if fn not in METRICS:
        raise KeyError(f"unknown metric function `{fn}`; known: {sorted(METRICS)}")
    return float(METRICS[fn](rows, pred=pred, ref=ref, strata=list(strata), group=group, role=role, params=params))


# ------------------------------------------------------------------------------------------------ uncertainty
def bootstrap_ci(stat: Callable[[Rows], float], rows: Rows, *, n_boot: int = 2000, level: float = 0.95, seed: int = 0,
                 scheme: str = "plain", strata: Sequence[str] = (), cluster: Optional[str] = None
                 ) -> tuple[float, tuple[float, float]]:
    """Percentile bootstrap of ``stat`` over rows. Returns (point, (lo, hi)).

    plain       resample n rows with replacement: ``default_rng(seed).integers(0, n, n)`` per draw, exactly as
                mfos.stats.bootstrap_ci, so the two agree for the same seed
    stratified  resample within each stratum (columns ``strata``), keeping stratum sizes
    cluster     resample whole clusters (column ``cluster``) with replacement
    """
    rng = np.random.default_rng(seed)
    n = len(rows)
    point = float(stat(rows))
    boots = np.empty(n_boot)
    if scheme == "plain":
        for i in range(n_boot):
            idx = rng.integers(0, n, n)
            boots[i] = stat([rows[j] for j in idx])
    elif scheme == "stratified":
        if not strata:
            raise ValueError("a stratified bootstrap needs strata columns")
        groups = list(_groups(strata_keys(rows, strata)).values())
        for i in range(n_boot):
            idx = np.concatenate([rng.choice(g, len(g)) for g in groups])
            boots[i] = stat([rows[j] for j in idx])
    elif scheme == "cluster":
        if not cluster:
            raise ValueError("a cluster bootstrap needs a cluster column")
        groups = list(_groups([row[cluster] for row in rows]).values())
        for i in range(n_boot):
            pick = rng.integers(0, len(groups), len(groups))
            idx = np.concatenate([groups[k] for k in pick])
            boots[i] = stat([rows[j] for j in idx])
    else:
        raise ValueError(f"unknown bootstrap scheme `{scheme}`")
    alpha = (1.0 - level) / 2.0
    lo, hi = np.quantile(boots, [alpha, 1.0 - alpha])
    return point, (float(lo), float(hi))


def null_column(rows: Rows, kind: str, ref: Optional[str], strata: Sequence[str] = (),
                column: Optional[str] = None) -> list[float]:
    """The null predictor's values: the stratum mean of ``ref`` ("stratum_mean"), or a named column ("column")."""
    if kind == "column":
        return [float(row[column]) for row in rows]  # type: ignore[index]
    if kind == "stratum_mean":
        keys = strata_keys(rows, strata)
        vals = _col(rows, ref)
        means = {k: float(vals[idx].mean()) for k, idx in _groups(keys).items()}
        return [means[k] for k in keys]
    raise ValueError(f"unknown null kind `{kind}`")
