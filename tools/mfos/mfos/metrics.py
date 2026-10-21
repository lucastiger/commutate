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
  topk_recall               share of the predicted best k_frac that lie in the reference best within_frac
  within_strata_spearman    Spearman of log values centred on their stratum means
  discordance_by_gap        per gap bin: (pairs, discordant pairs), gap = |ref_i - ref_j| / min(ref_i, ref_j)
  group_selection_regret    per group ref[argmin pred] / min ref - 1, aggregated (mean or max)
  stratum_mean_offset_spread  max - min over strata of mean(pred / ref - 1)
  pairwise_diff_error_quantile  q-quantile over within-stratum pairs of |(pred_i - pred_j) - (ref_i - ref_j)|
  headroom_by_group         per group 1 - value[selected] / value[reference], aggregated
  optimism_ratio_by_group   per group (ref[reference] - ref[selected]) / (pred[reference] - pred[selected]), aggregated
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


# ------------------------------------------------------------------------------------------------ records adapter
def strata_keys(rows: Rows, columns: Sequence[str]) -> list[str]:
    return [":".join(str(row[c]) for c in columns) for row in rows]


def _col(rows: Rows, name: Optional[str]) -> np.ndarray:
    if not name:
        raise ValueError("this metric needs a column name")
    return np.asarray([row[name] for row in rows], dtype=float)


# name -> f(rows, pred, ref, strata, group, role, params) -> float
METRICS: dict[str, Callable[..., float]] = {
    "spearman": lambda rows, pred, ref, **_: spearman(_col(rows, pred), _col(rows, ref)),
    "kendall_tau": lambda rows, pred, ref, **_: kendall_tau(_col(rows, pred), _col(rows, ref)),
    "mape": lambda rows, pred, ref, **_: mape(_col(rows, pred), _col(rows, ref)),
    "mean_signed_rel_err": lambda rows, pred, ref, **_: mean_signed_rel_err(_col(rows, pred), _col(rows, ref)),
    "max_rel_err": lambda rows, pred, ref, **_: max_rel_err(_col(rows, pred), _col(rows, ref)),
    "max_abs_err": lambda rows, pred, ref, **_: max_abs_err(_col(rows, pred), _col(rows, ref)),
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
