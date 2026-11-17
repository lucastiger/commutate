"""E007 (O002) metrics draft, T0396.

What is new here is the confidence bound F3 selects (``quantile_ci``, the block between the ``metrics.py`` markers; copied
verbatim into tools/mfos/mfos/metrics.py by make_patch.py). The point statistics are mfos.metrics' own, merged with
commit 2fea4a6e: quantile_abs_err (A3), quantile_rel_err (A2), quantile_abs_err_ratio (A4/K3), median_col (A5),
max_over_groups (max over load levels), pairwise_diff_error_quantile with self-pair exclusion (A1, params.unit) and
gci_step_floor / max_gci_step_floor (F1's 0.01 K step floor). Below the block: the runner-side helpers that turn die rows
into the layout and switch rows the metrics read (hottest die by the reference's die average, the own-hottest variant,
spreads, the stratum-mean-spread null per (stratum, switch), leave-one-layout-out). Row contract: e007_row_contract.md.

The bound (O002 F3; selection in f3_simulation.json). For a statistic that is the q-quantile of terms x_t (one term per
die, per switch or per same-stratum layout pair), each term belonging to one or two layouts (the independent units):
  F(t) = share of terms <= t; theta = np.quantile(x, q).
  Var F(theta) by the delete-one-layout jackknife (deleting a layout deletes every term that involves it, so pair terms,
  a U-statistic, are handled; Arvesen 1969, Ann. Math. Statist. 40:2076).
  Upper bound Q(q + c se), lower bound Q(q - c se) (Woodruff 1952, JASA 47:635-646; for clustered samples Francisco
  and Fuller 1991, Ann. Statist. 19:454-469), c the one-sided critical value, the order statistic rounded outward.
  Ratio of two quantiles on the same rows (A4): log-ratio by the Bahadur linearisation theta_hat - theta ~
  (q - F(theta)) / f(theta), with f estimated from Woodruff's interval (se_theta = (Q(q + c se) - Q(q - c se)) / 2c,
  Sitter and Wu 2001, Stat. Probab. Lett. 52:353-358), the two linearised terms combined per layout and the variance by
  the same jackknife (variant ``ratio='delta'``); or, the default F3 selected, the Bonferroni quotient of the two
  bounds at alpha / 2.
  Max over groups (load levels): upper bound max_g U_g at alpha (valid: the argmax group's bound covers it); lower
  bound max_g L_g at alpha / G (Bonferroni: a lower bound on the max fails if any group's lower bound fails).
  ``level`` keeps bootstrap_ci's meaning: (lo, hi) is a central ``level`` interval, each side a one-sided
  (1 + level) / 2 bound; F3 selected level 0.94 for E007 (one-sided 97 % bounds; f3_simulation.json).
"""
from __future__ import annotations

import itertools
import math
from typing import Any, Optional, Sequence

import numpy as np
from scipy import stats as _st

from mfos.metrics import Rows, _col, _groups, _p, compute, strata_keys

# >>> metrics.py
# ------------------------------------------------------------------------------------------------ quantile bounds (O002 F3)
QUANTILE_CI_FNS = ("quantile_abs_err", "quantile_rel_err", "pairwise_diff_error_quantile", "quantile_abs_err_ratio",
                   "max_over_groups")


def _unit_index(units: Sequence[Sequence[Any]]) -> tuple[np.ndarray, np.ndarray, int]:
    """Flattened (term, unit index) incidence of ``units`` (one tuple of unit labels per term) and the unit count."""
    labels = {u: k for k, u in enumerate(sorted({u for us in units for u in us}, key=str))}
    t_idx, k_idx = [], []
    for t, us in enumerate(units):
        for u in set(us):
            t_idx.append(t)
            k_idx.append(labels[u])
    return np.asarray(t_idx, dtype=int), np.asarray(k_idx, dtype=int), len(labels)


def _jackknife_cdf(x: np.ndarray, theta: float, inc: tuple[np.ndarray, np.ndarray, int]) -> Optional[np.ndarray]:
    """Delete-one-unit values of the share of terms <= theta; None when some unit is in every term."""
    t_idx, k_idx, n_units = inc
    ind = (x <= theta).astype(float)
    s = np.bincount(k_idx, weights=ind[t_idx], minlength=n_units)
    m = np.bincount(k_idx, minlength=n_units).astype(float)
    rest = x.size - m
    if np.any(rest <= 0.0):
        return None
    return (ind.sum() - s) / rest


def _jk_se(vals: np.ndarray) -> float:
    k = vals.size
    return float(math.sqrt((k - 1) / k * float(np.sum((vals - vals.mean()) ** 2))))


def _crit(alpha: float, n_units: int, crit: str) -> float:
    return float(_st.t.ppf(1.0 - alpha, n_units - 1) if crit == "t" else _st.norm.ppf(1.0 - alpha))


def woodruff_bound(values: Sequence[float], units: Sequence[Sequence[Any]], q: float, alpha: float, side: str,
                   crit: str = "t", rounding: str = "outward") -> float:
    """One-sided (1 - alpha) bound on the q-quantile of ``values`` (O002 F3): the order statistic at q +/- c se, se the
    delete-one-unit jackknife standard error of the share of terms <= np.quantile(values, q), c the t quantile with
    (units - 1) degrees of freedom (``crit='z'``: normal), rounded outward (``rounding='linear'``: np.quantile's
    interpolation). ``units``: one tuple of unit labels (layouts) per term, two for a pair term. +inf (upper) or -inf
    (lower) with fewer than 2 units, a unit in every term, or a shifted level outside [0, 1]."""
    if side not in ("upper", "lower"):
        raise ValueError(f"side must be upper or lower, not {side!r}")
    x = np.asarray(values, dtype=float)
    if x.size == 0 or x.size != len(units) or not np.all(np.isfinite(x)):
        raise ValueError("woodruff_bound needs one finite value per units entry")
    out = math.inf if side == "upper" else -math.inf
    inc = _unit_index(units)
    if inc[2] < 2:
        return out
    theta = float(np.quantile(x, q))
    fj = _jackknife_cdf(x, theta, inc)
    if fj is None:
        return out
    shift = _crit(alpha, inc[2], crit) * _jk_se(fj)
    lev = q + shift if side == "upper" else q - shift
    if not 0.0 <= lev <= 1.0:
        return out
    method = "linear" if rounding == "linear" else ("higher" if side == "upper" else "lower")
    return float(np.quantile(x, lev, method=method))


def woodruff_ratio_bound(num: Sequence[float], den: Sequence[float], units: Sequence[Sequence[Any]], q: float,
                         alpha: float, side: str, crit: str = "t", rounding: str = "outward",
                         ratio: str = "bonferroni") -> float:
    """One-sided (1 - alpha) bound on Q_q(num) / Q_q(den), both on the same terms (O002 A4/K3: L1's spread error over
    the stratum-mean-spread null's). The default is the one F3 selected (f3_simulation.json). ``ratio='delta'``: R exp(+/- c se), se of log R from the per-unit jackknife of the
    Bahadur-linearised log quantiles with Woodruff-implied densities; it falls back to the Bonferroni quotient when a
    quantile is 0 or a Woodruff level leaves [0, 1]. ``ratio='bonferroni'``: U_num / L_den (upper), L_num / U_den
    (lower), each at alpha / 2."""
    x1, x0 = np.asarray(num, dtype=float), np.asarray(den, dtype=float)
    if x1.size != x0.size:
        raise ValueError("num and den need the same terms")

    def bonferroni() -> float:
        if side == "upper":
            hi, lo = woodruff_bound(x1, units, q, alpha / 2, "upper", crit, rounding), \
                woodruff_bound(x0, units, q, alpha / 2, "lower", crit, rounding)
            return math.inf if lo <= 0.0 or not math.isfinite(hi) else hi / lo
        lo, hi = woodruff_bound(x1, units, q, alpha / 2, "lower", crit, rounding), \
            woodruff_bound(x0, units, q, alpha / 2, "upper", crit, rounding)
        return 0.0 if not math.isfinite(hi) or lo <= 0.0 else lo / hi

    if side not in ("upper", "lower"):
        raise ValueError(f"side must be upper or lower, not {side!r}")
    if ratio == "bonferroni":
        return bonferroni()
    inc = _unit_index(units)
    if inc[2] < 2:
        return math.inf if side == "upper" else 0.0
    c = _crit(alpha, inc[2], crit)
    lin = []
    for x in (x1, x0):
        theta = float(np.quantile(x, q))
        fj = _jackknife_cdf(x, theta, inc)
        if theta <= 0.0 or fj is None:
            return bonferroni()
        se_f = _jk_se(fj)
        if se_f == 0.0:
            lin.append(np.zeros_like(fj))
            continue
        if not (0.0 <= q - c * se_f and q + c * se_f <= 1.0):
            return bonferroni()
        se_theta = (float(np.quantile(x, q + c * se_f)) - float(np.quantile(x, q - c * se_f))) / (2.0 * c)
        lin.append(-fj * se_theta / (se_f * theta))  # d log(theta_hat) = -dF / (f theta), f = se_f / se_theta
    se = _jk_se(lin[0] - lin[1])
    r = float(np.quantile(x1, q) / np.quantile(x0, q))
    return float(r * math.exp(c * se if side == "upper" else -c * se))


def quantile_terms(fn: str, rows: Rows, *, pred: Optional[str], ref: Optional[str], strata: Sequence[str] = (),
                   params: Optional[dict[str, Any]] = None, cluster: str = "layout"
                   ) -> tuple[np.ndarray, Optional[np.ndarray], list[tuple[Any, ...]], float]:
    """The terms whose q-quantile metric ``fn`` returns, in the order and with the pair rule of that metric, with the
    ``cluster`` labels of the rows each term involves: (terms, null terms or None, units, q). The null terms are those of
    quantile_abs_err_ratio's denominator."""
    p = _p(params)
    q = float(p.get("q", 0.95))
    lab = [row[cluster] for row in rows]
    if fn == "pairwise_diff_error_quantile":
        pr, rf = _col(rows, pred), _col(rows, ref)
        u = [row[p["unit"]] for row in rows] if p.get("unit") else None
        terms, units = [], []
        for idx in _groups(strata_keys(rows, strata)).values():
            for i, j in itertools.combinations(idx.tolist(), 2):
                if u is None or u[i] != u[j]:
                    terms.append(abs((pr[i] - pr[j]) - (rf[i] - rf[j])))
                    units.append((lab[i], lab[j]))
        return np.asarray(terms, dtype=float), None, units, q
    units = [(v,) for v in lab]
    pr, rf = _col(rows, pred), _col(rows, ref)
    if fn == "quantile_abs_err":
        return np.abs(pr - rf), None, units, q
    if fn == "quantile_rel_err":
        return np.abs(pr - rf) / _col(rows, p["scale"]), None, units, q
    if fn == "quantile_abs_err_ratio":
        return np.abs(pr - rf), np.abs(_col(rows, p["null"]) - rf), units, q
    raise ValueError(f"quantile_ci does not support `{fn}`; supported: {QUANTILE_CI_FNS}")


def _quantile_bound(fn: str, rows: Rows, alpha: float, side: str, pred: Optional[str], ref: Optional[str],
                    strata: Sequence[str], params: Optional[dict[str, Any]], cluster: str, **variant: str) -> float:
    x, x0, units, q = quantile_terms(fn, rows, pred=pred, ref=ref, strata=strata, params=params, cluster=cluster)
    if x0 is not None:
        return woodruff_ratio_bound(x, x0, units, q, alpha, side, **variant)
    if x.size == 0:
        raise ValueError("no terms")
    return woodruff_bound(x, units, q, alpha, side, **{k: v for k, v in variant.items() if k != "ratio"})


def quantile_ci(fn: str, rows: Rows, *, pred: Optional[str] = None, ref: Optional[str] = None,
                strata: Sequence[str] = (), group: Optional[str] = None, role: Optional[str] = None,
                params: Optional[dict[str, Any]] = None, level: float = 0.95, cluster: Optional[str] = None,
                **variant: str) -> tuple[float, tuple[float, float]]:
    """(point, (lo, hi)) for a q-quantile metric (O002 F3, CISpec scheme 'woodruff'): point = compute(fn, ...) exactly
    as the evaluator computes it; lo and hi are one-sided (1 + level) / 2 bounds by woodruff_bound (or
    woodruff_ratio_bound for quantile_abs_err_ratio), with the rows' ``cluster`` column (the layout) as the independent
    units. For max_over_groups: hi = max over groups of each group's upper bound, lo = max over groups of each group's
    lower bound at alpha / (number of groups)."""
    if not cluster:
        raise ValueError("quantile_ci needs the cluster (unit) column")
    if fn not in QUANTILE_CI_FNS:
        raise ValueError(f"quantile_ci does not support `{fn}`; supported: {QUANTILE_CI_FNS}")
    point = compute(fn, rows, pred=pred, ref=ref, strata=strata, group=group, role=role, params=params)
    alpha = (1.0 - level) / 2.0
    if fn != "max_over_groups":
        return point, (_quantile_bound(fn, rows, alpha, "lower", pred, ref, strata, params, cluster, **variant),
                       _quantile_bound(fn, rows, alpha, "upper", pred, ref, strata, params, cluster, **variant))
    pp = _p(params)
    inner_fn, by, inner = pp["fn"], pp["by"], pp.get("inner")
    keys = sorted({row[by] for row in rows}, key=str)
    subs = [[row for row in rows if row[by] == k] for k in keys]
    hi = max(_quantile_bound(inner_fn, s, alpha, "upper", pred, ref, strata, inner, cluster, **variant) for s in subs)
    lo = max(_quantile_bound(inner_fn, s, alpha / len(keys), "lower", pred, ref, strata, inner, cluster, **variant)
             for s in subs)
    return point, (float(lo), float(hi))
# <<< metrics.py


# ------------------------------------------------------------------------------------------------ E007 runner helpers
STRATUM = ("family", "dies")


def _skey(row: dict[str, Any]) -> tuple[Any, ...]:
    return tuple(row[c] for c in STRATUM)


def layout_rows(die_rows: Rows, l1: str = "tj_l1_K", ref: str = "tj_ref_K") -> Rows:
    """One row per (layout, load) from the die rows (kind 'die'): the hottest die is the die the reference ranks hottest
    by its die average (A1; ties go to the first die in (switch, die_index) order), for L1 and the reference alike:
    tj_hot_ref_K, tj_hot_l1_K (L1 at the reference's hottest die), tj_ownhot_l1_K (L1's own hottest die, the variant
    reported beside A1; paired with tj_hot_ref_K, the reference's own hottest), hot_switch, hot_die_index."""
    groups: dict[tuple[Any, Any], list[dict[str, Any]]] = {}
    for r in die_rows:
        groups.setdefault((r["layout"], r["load"]), []).append(r)
    out = []
    for (lay, load), rs in groups.items():
        rs = sorted(rs, key=lambda r: (str(r["switch"]), int(r["die_index"])))
        hot = max(range(len(rs)), key=lambda i: (float(rs[i][ref]), -i))
        out.append({"kind": "layout", "layout": lay, "load": load, "family": rs[0]["family"], "dies": rs[0]["dies"],
                    "tj_hot_ref_K": float(rs[hot][ref]), "tj_hot_l1_K": float(rs[hot][l1]),
                    "tj_ownhot_l1_K": float(max(float(r[l1]) for r in rs)),
                    "hot_switch": rs[hot]["switch"], "hot_die_index": int(rs[hot]["die_index"])})
    return out


def switch_rows(die_rows: Rows, l1: str = "tj_l1_K", ref: str = "tj_ref_K") -> Rows:
    """One row per (layout, load, switch): spread = max - min of the die averages over the switch's paralleled dies
    (spread_ref_K, spread_l1_K) and the stratum-mean-spread null spread_null_K: the mean of spread_ref_K over the other
    layouts of the same (family, dies, load, switch), leave-one-layout-out (F2 null (d); A4's denominator)."""
    groups: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    for r in die_rows:
        groups.setdefault((r["layout"], r["load"], r["switch"]), []).append(r)
    out = []
    for (lay, load, sw), rs in groups.items():
        tr, tl = [float(r[ref]) for r in rs], [float(r[l1]) for r in rs]
        out.append({"kind": "switch", "layout": lay, "load": load, "switch": sw, "family": rs[0]["family"],
                    "dies": rs[0]["dies"], "spread_ref_K": max(tr) - min(tr), "spread_l1_K": max(tl) - min(tl)})
    cells: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    for r in out:
        cells.setdefault((*_skey(r), r["load"], r["switch"]), []).append(r)
    for rs in cells.values():
        if len(rs) < 2:
            raise ValueError("the leave-one-layout-out null needs at least 2 layouts per (stratum, load, switch)")
        tot = sum(r["spread_ref_K"] for r in rs)
        for r in rs:
            r["spread_null_K"] = (tot - r["spread_ref_K"]) / (len(rs) - 1)
    return out
