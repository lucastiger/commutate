"""E011 acceptance metrics (O008 A1, A2, A3, K1) over per-draw rows: reference implementations for mfos.metrics (F7).

T0381. Written independently of the functions the founder session added to ``mfos.metrics`` (I0204); the agreement
test in ``tests/acceptance_drafts/test_e011_metrics.py`` runs both on the same synthetic rows. Pure functions over a
list of row dicts, no I/O, no randomness.

Row schema (``mfos.rows/1``; one row per layout x role x draw; the runner, n5, emits exactly these columns)
---------------------------------------------------------------------------------------------------------
``layout``        str    development layout id, e.g. ``2D_Case_2R``, ``2D_Case_4``, ``gen2_0``
``counted``       bool   the layout is in O008's counted set; ``False`` for gen2_0 (reported, not counted) and for a
                         layout F6 excludes. Constant within a layout
``draw``          int    draw index j; pairs the degraded copy D_j across roles within a layout. A counted layout
                         has exactly 8 draws per role present, with the same draw ids for every role
``role``          str    one of ``search`` (the seeded search), ``seed`` (null a: D_j returned unchanged), ``widen``
                         (null b), ``compact`` (null d), ``random_screen`` (ablation c), ``proxy_alone`` (ablation e)
``s``             float  shortfall s_j = L_sub(best_j) / L_sub(W*) - 1, L_sub at 0.25 mm from this role's own solve
                         (dimensionless). ``None`` or NaN when the run returned no candidate: that draw counts as
                         failed (shortfall +inf), it does not void the run
``b``             float  band b_j = 2 e_R(best_j, W*) by the D0008 band rule (dimensionless, >= 0); finite whenever
                         ``s`` is finite
``capped``        bool   the run stopped at its frozen step limit (or budget) rather than at its own local optimum.
                         A capped null draw is never a resolved failure (A3)
``terminal_kind`` str    reported beside ``capped``: ``local_optimum``, ``step_limit``, ``budget``, ``seed`` or
                         ``no_candidate``; ``step_limit`` and ``budget`` require ``capped`` true
``in_domain_W``   bool   in_domain(params_of(W)) for the layout's twin W, from the parameterisation's and the
                         sampler's own construction. Constant within a layout
``reach_outside`` float  1.0 - in_domain_W, so A2 is ``max_col`` over this column; must equal 1 - in_domain_W

Definitions (tol = 0.02, 8 draws; "counted" layouts are those with ``counted`` true)
-----------------------------------------------------------------------------
A1 control_layout_pass_min       min over counted layouts of (#search draws with s_j <= tol) / 8
A2 reach_outside_max             max over all development layouts (counted or not) of 1 - in_domain(W)
A3 null_beaten_min               min over counted layouts and the gating nulls (widen, compact) of beaten, where a
                                 null is beaten on a layout iff (i) #draws with null s_j - b_j > tol and the null run
                                 not capped >= 4 and (ii) #draws with s_j(null) - s_j(search) > b_j(search) + b_j(null)
                                 >= 7, paired on the draw id; 1.0 if every (layout, null) is beaten, else 0.0
K1 control_shortfall_median_max  max over counted layouts of the median of the search's s_j (even count: mean of the
                                 two middle values)
Reported, not gated: the conservative A1 count (s_j + b_j <= tol), the per-layout count of draws within their band of
the line (|s_j - tol| < b_j), the pooled one-sided Clopper-Pearson lower bound on the pass probability, the
Bonferroni-simultaneous per-layout Clopper-Pearson intervals (a CI for A1), and the F1 seed-null check.

All comparisons are on the recorded float64 values, with the strictness the objective states: ``<=`` for a pass,
``>`` for a resolved failure and for a paired win. A row-level bootstrap is not meaningful for these count metrics
(it breaks the one-row-per-draw structure that the validation enforces), so their ``recompute`` entries carry no
``ci``; the criteria use ``uncertainty: point`` and the intervals above are reported beside them.
"""
from __future__ import annotations

import math
from typing import Any, Optional, Sequence

import numpy as np
from scipy import stats as _st

Rows = list[dict[str, Any]]

TOL = 0.02  # O008: a draw passes when s_j <= 2 %
N_DRAWS = 8  # O008: 8 draws per layout
MIN_PASS = 7  # A1: 7 of 8 (0.875)
MIN_RESOLVED = 4  # A3: resolved failures on at least 4 of 8 draws
MIN_PAIRED = 7  # A3: paired wins on at least 7 of 8 draws
ROLES = ("search", "seed", "widen", "compact", "random_screen", "proxy_alone")
GATING_NULLS = ("widen", "compact")
TERMINAL_KINDS = ("local_optimum", "step_limit", "budget", "seed", "no_candidate")
COLUMNS = ("layout", "counted", "draw", "role", "s", "b", "capped", "terminal_kind", "in_domain_W", "reach_outside")


# ------------------------------------------------------------------------------------------------ validation
def _is_bool(v: Any) -> bool:
    return isinstance(v, (bool, np.bool_))


def _shortfall(v: Any, where: str) -> float:
    """s as float64; None or NaN (no candidate) -> +inf, so the draw fails every pass test."""
    if v is None:
        return math.inf
    if _is_bool(v) or not isinstance(v, (int, float, np.integer, np.floating)):
        raise ValueError(f"{where}: s must be a number or None, got {v!r}")
    x = float(v)
    if math.isnan(x):
        return math.inf
    if x == -math.inf:
        raise ValueError(f"{where}: s is -inf")
    return x


def _band(v: Any, s: float, where: str) -> float:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        if math.isfinite(s):
            raise ValueError(f"{where}: b is missing for a finite s")
        return math.nan
    if _is_bool(v) or not isinstance(v, (int, float, np.integer, np.floating)):
        raise ValueError(f"{where}: b must be a number, got {v!r}")
    x = float(v)
    if not math.isfinite(x) or x < 0.0:
        raise ValueError(f"{where}: b must be finite and >= 0, got {x!r}")
    return x


def _table(rows: Rows, n_draws: int = N_DRAWS) -> dict[str, dict[str, Any]]:
    """Validate the rows and index them: layout -> {counted, in_domain_W, roles: role -> draw -> (s, b, capped)}."""
    if not isinstance(rows, list) or not rows:
        raise ValueError("rows must be a non-empty list of dicts")
    out: dict[str, dict[str, Any]] = {}
    for i, r in enumerate(rows):
        where = f"row {i}"
        missing = [c for c in COLUMNS if c not in r]
        if missing:
            raise ValueError(f"{where}: missing columns {missing}")
        lay, role, draw = r["layout"], r["role"], r["draw"]
        where = f"row {i} ({lay}, {role}, draw {draw})"
        if not isinstance(lay, str) or not lay:
            raise ValueError(f"{where}: layout must be a non-empty string")
        if role not in ROLES:
            raise ValueError(f"{where}: role must be one of {ROLES}")
        if _is_bool(draw) or not isinstance(draw, (int, np.integer)):
            raise ValueError(f"{where}: draw must be an integer")
        for c in ("counted", "capped", "in_domain_W"):
            if not _is_bool(r[c]):
                raise ValueError(f"{where}: {c} must be a bool, got {r[c]!r}")
        if r["terminal_kind"] not in TERMINAL_KINDS:
            raise ValueError(f"{where}: terminal_kind must be one of {TERMINAL_KINDS}")
        if r["terminal_kind"] in ("step_limit", "budget") and not r["capped"]:
            raise ValueError(f"{where}: terminal_kind {r['terminal_kind']} with capped false")
        if r["terminal_kind"] == "local_optimum" and r["capped"]:
            raise ValueError(f"{where}: terminal_kind local_optimum with capped true")
        ro = r["reach_outside"]
        if _is_bool(ro) or not isinstance(ro, (int, float, np.integer, np.floating)) \
                or float(ro) != 1.0 - float(bool(r["in_domain_W"])):
            raise ValueError(f"{where}: reach_outside must equal 1 - in_domain_W, got {ro!r}")
        s = _shortfall(r["s"], where)
        b = _band(r["b"], s, where)
        t = out.setdefault(lay, {"counted": bool(r["counted"]), "in_domain_W": bool(r["in_domain_W"]), "roles": {}})
        if t["counted"] != bool(r["counted"]) or t["in_domain_W"] != bool(r["in_domain_W"]):
            raise ValueError(f"{where}: counted / in_domain_W differ within layout {lay}")
        d = t["roles"].setdefault(role, {})
        if int(draw) in d:
            raise ValueError(f"{where}: duplicate draw")
        d[int(draw)] = (s, b, bool(r["capped"]))
    for lay, t in out.items():
        if not t["counted"]:
            continue
        if "search" not in t["roles"]:
            raise ValueError(f"counted layout {lay} has no search rows")
        ids = set(t["roles"]["search"])
        if len(ids) != n_draws:
            raise ValueError(f"counted layout {lay}: {len(ids)} search draws, expected {n_draws}")
        for role, d in t["roles"].items():
            if set(d) != ids:
                raise ValueError(f"counted layout {lay}: draws of {role} {sorted(d)} differ from search {sorted(ids)}")
    if not any(t["counted"] for t in out.values()):
        raise ValueError("no counted layout")
    return out


def validate_rows(rows: Rows, n_draws: int = N_DRAWS) -> None:
    """Raise ValueError when the rows do not follow the schema in the module docstring."""
    _table(rows, n_draws)


def _counted(t: dict[str, dict[str, Any]], role: str) -> dict[str, dict[int, tuple[float, float, bool]]]:
    out = {}
    for lay, v in sorted(t.items()):
        if v["counted"]:
            if role not in v["roles"]:
                raise ValueError(f"counted layout {lay} has no {role} rows")
            out[lay] = v["roles"][role]
    return out


# ------------------------------------------------------------------------------------------------ gated metrics
def layout_pass_counts(rows: Rows, role: str = "search", tol: float = TOL, n_draws: int = N_DRAWS,
                       conservative: bool = False) -> dict[str, int]:
    """Per counted layout, the number of ``role`` draws with s_j <= tol (``conservative``: s_j + b_j <= tol)."""
    out = {}
    for lay, d in _counted(_table(rows, n_draws), role).items():
        out[lay] = sum(1 for s, b, _ in d.values()
                       if math.isfinite(s) and ((s + b) if conservative else s) <= tol)
    return out


def control_layout_pass_min(rows: Rows, role: str = "search", tol: float = TOL, n_draws: int = N_DRAWS) -> float:
    """O008 A1: min over counted layouts of the fraction of the layout's n_draws draws with s_j <= tol."""
    return min(k / n_draws for k in layout_pass_counts(rows, role, tol, n_draws).values())


def reach_outside_max(rows: Rows, n_draws: int = N_DRAWS) -> float:
    """O008 A2: max over all development layouts (counted or not) of 1 - in_domain(W)."""
    return max(1.0 - float(v["in_domain_W"]) for v in _table(rows, n_draws).values())


def null_beaten_table(rows: Rows, nulls: Sequence[str] = GATING_NULLS, tol: float = TOL, n_draws: int = N_DRAWS,
                      min_resolved: int = MIN_RESOLVED, min_paired: int = MIN_PAIRED) -> dict[tuple[str, str], dict]:
    """Per (counted layout, null): resolved-failure count, paired-win count and the beaten indicator (A3).

    Resolved failure on draw j: the null's run is not capped and s_j(null) - b_j(null) > tol.
    Paired win on draw j: s_j(null) - s_j(search) > b_j(search) + b_j(null), both finite (a draw where either run
    returned no candidate is not a win). Capped null draws may still be paired wins: the objective excludes them from
    the resolved-failure count only.
    """
    t = _table(rows, n_draws)
    search = _counted(t, "search")
    out = {}
    for null in nulls:
        if null not in ROLES:
            raise ValueError(f"unknown null role {null!r}")
        for lay, nd in _counted(t, null).items():
            sd = search[lay]
            resolved = sum(1 for s, b, cap in nd.values() if not cap and math.isfinite(s) and s - b > tol)
            paired = 0
            for j, (sn, bn, _) in nd.items():
                ss, bs, _ = sd[j]
                if math.isfinite(sn) and math.isfinite(ss) and sn - ss > bs + bn:
                    paired += 1
            out[(lay, null)] = {"resolved": resolved, "paired": paired,
                                "beaten": resolved >= min_resolved and paired >= min_paired}
    return out


def null_beaten_min(rows: Rows, nulls: Sequence[str] = GATING_NULLS, tol: float = TOL, n_draws: int = N_DRAWS,
                    min_resolved: int = MIN_RESOLVED, min_paired: int = MIN_PAIRED) -> float:
    """O008 A3: 1.0 if every gating null is beaten on every counted layout, else 0.0."""
    if not nulls:
        raise ValueError("no gating null given")
    tab = null_beaten_table(rows, nulls, tol, n_draws, min_resolved, min_paired)
    return float(min(v["beaten"] for v in tab.values()))


def control_shortfall_median_max(rows: Rows, role: str = "search", n_draws: int = N_DRAWS) -> float:
    """O008 K1: max over counted layouts of the median of s_j (no-candidate draws as +inf)."""
    return max(float(np.median(np.array([s for s, _, _ in d.values()], dtype=np.float64)))
               for d in _counted(_table(rows, n_draws), role).values())


# ------------------------------------------------------------------------------------------------ reported helpers
def control_layout_pass_min_conservative(rows: Rows, role: str = "search", tol: float = TOL,
                                         n_draws: int = N_DRAWS) -> float:
    """A1 with the band applied conservatively: min over counted layouts of #(s_j + b_j <= tol) / n_draws."""
    return min(k / n_draws for k in layout_pass_counts(rows, role, tol, n_draws, conservative=True).values())


def unresolved_counts(rows: Rows, role: str = "search", tol: float = TOL,
                      n_draws: int = N_DRAWS) -> dict[str, int]:
    """Per layout (counted or not), the number of ``role`` draws within their band of the line: |s_j - tol| < b_j."""
    out = {}
    for lay, v in sorted(_table(rows, n_draws).items()):
        if role in v["roles"]:
            out[lay] = sum(1 for s, b, _ in v["roles"][role].values() if math.isfinite(s) and abs(s - tol) < b)
    return out


def clopper_pearson_lower(k: int, n: int, level: float = 0.95) -> float:
    """Exact one-sided lower confidence bound on a binomial p from k successes in n trials.

    p_L solves P(X >= k | n, p_L) = 1 - level, i.e. p_L = Beta^{-1}(1 - level; k, n - k + 1), and p_L = 0 for k = 0
    (Clopper & Pearson 1934, Biometrika 26:404-413; one-sided form as in Brown, Cai & DasGupta 2001, Stat. Sci.
    16:101-133). For k = n, p_L = (1 - level)^(1/n).
    """
    if not (0 <= k <= n) or n < 1 or not (0.0 < level < 1.0):
        raise ValueError(f"need 0 <= k <= n, n >= 1, 0 < level < 1; got k={k}, n={n}, level={level}")
    return 0.0 if k == 0 else float(_st.beta.ppf(1.0 - level, k, n - k + 1))


def clopper_pearson_interval(k: int, n: int, level: float = 0.95) -> tuple[float, float]:
    """Exact two-sided interval: (Beta^{-1}(a/2; k, n-k+1), Beta^{-1}(1-a/2; k+1, n-k)), a = 1 - level (ibid.)."""
    if not (0 <= k <= n) or n < 1 or not (0.0 < level < 1.0):
        raise ValueError(f"need 0 <= k <= n, n >= 1, 0 < level < 1; got k={k}, n={n}, level={level}")
    a = 1.0 - level
    lo = 0.0 if k == 0 else float(_st.beta.ppf(a / 2.0, k, n - k + 1))
    hi = 1.0 if k == n else float(_st.beta.ppf(1.0 - a / 2.0, k + 1, n - k))
    return lo, hi


def pooled_pass_lower_bound(rows: Rows, role: str = "search", tol: float = TOL, n_draws: int = N_DRAWS,
                            level: float = 0.95, conservative: bool = False) -> tuple[int, int, float]:
    """(k, n, p_L): passes pooled over the counted layouts and the one-sided Clopper-Pearson lower bound.

    Reported, not gated: draws within a layout share W* (and its single L_sub solve), so they are not independent
    trials over references; this is a count summary, not a reliability bound.
    """
    counts = layout_pass_counts(rows, role, tol, n_draws, conservative)
    k, n = sum(counts.values()), n_draws * len(counts)
    return k, n, clopper_pearson_lower(k, n, level)


def layout_pass_intervals(rows: Rows, role: str = "search", tol: float = TOL, n_draws: int = N_DRAWS,
                          level: float = 0.95) -> dict[str, tuple[int, float, float]]:
    """Per counted layout (k, lo, hi): two-sided Clopper-Pearson intervals at Bonferroni level 1 - (1 - level) / m.

    With m counted layouts the intervals hold jointly with probability >= level, so (min lo, min hi) is a
    conservative ``level`` interval for min over layouts of the per-draw pass probability: the CI reported beside A1.
    Same caveat as the pooled bound: it assumes independent draws given the layout's W*.
    """
    counts = layout_pass_counts(rows, role, tol, n_draws)
    lev = 1.0 - (1.0 - level) / len(counts)
    return {lay: (k, *clopper_pearson_interval(k, n_draws, lev)) for lay, k in counts.items()}


def a1_operating_characteristic(p: float, n_layouts: int = 1, n_draws: int = N_DRAWS, min_pass: int = MIN_PASS) -> float:
    """P(A1 met) with independent draws of per-draw pass probability p: P(Bin(n_draws, p) >= min_pass)^n_layouts."""
    return float(_st.binom.sf(min_pass - 1, n_draws, p)) ** n_layouts


def seed_null_check(rows: Rows, threshold: float = MIN_PASS / N_DRAWS, tol: float = TOL,
                    n_draws: int = N_DRAWS) -> tuple[bool, float]:
    """F1 gated sanity check: (passed, A1 of the seed null). The seed null meeting A1 means INVALID.

    The seed null returns D_j, whose shortfall is R_D - 1 >= 0.25 by construction, so it can meet A1 only through a
    defect in the computation (e.g. s taken against D_j rather than W*).
    """
    v = control_layout_pass_min(rows, role="seed", tol=tol, n_draws=n_draws)
    return v < threshold, v


def verdict(values: dict[str, Optional[float]], pass_all: Sequence[Any], fail_any: Sequence[Any]) -> str:
    """The evaluator's verdict on point values (mfos.evaluate.evaluate, no validity problems): FAIL if any fail
    criterion holds, else PASS if every pass criterion holds, else INCONCLUSIVE. ``values`` maps criterion metric
    names (``E011.x``) to point values; criteria need ``metric``, ``comparator`` and ``threshold``.
    """
    import operator
    ops = {">=": operator.ge, ">": operator.gt, "<=": operator.le, "<": operator.lt}
    if any(values.get(c.metric) is None for c in [*pass_all, *fail_any]):
        return "INVALID"
    if any(ops[c.comparator](values[c.metric], c.threshold) for c in fail_any):
        return "FAIL"
    if all(ops[c.comparator](values[c.metric], c.threshold) for c in pass_all):
        return "PASS"
    return "INCONCLUSIVE"
