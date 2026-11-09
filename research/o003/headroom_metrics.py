"""Draft (T0261) of two protected mfos.metrics functions for O003 / E008: headroom_min_lo (A1) and headroom_max_hi_ind (K1).

Research draft, not evidence. The founder applies it to tools/mfos/mfos/metrics.py with research/o003/headroom_metrics.patch
(generated from this file by research/o003/make_patch.py: the block between the ``>>> metrics.py`` and ``<<< metrics.py``
markers and the dispatch entries between ``>>> METRICS`` and ``<<< METRICS`` are copied verbatim). The rule text implemented
is O003's acceptance A1 and K1 (objective v5, D0016, D0017); the row contract is research/o003/e008_row_contract.md.

Facts this file relies on (cited): the order-capped GCI is mfos.metrics.gci_capped (O006 A4, D0012, D0013); the band
estimator terms are O006 pilot P3's (research/scripts/o006_p3_em_convergence.py: two-level ``3 |f2 - f1| / (r - 1)`` at
r = 2 and ``middle_term``), with Roache's safety factors (Verification and Validation in Computational Science and
Engineering, Hermosa 1998, ch. 5).
"""
from __future__ import annotations

import math
from typing import Any, Optional, Sequence

from mfos import metrics as _mx
from mfos.metrics import Rows, gci_capped, null_column

__all__ = [
    "HR_BAND", "HR_TJ", "HR_SHORTLIST", "HR_BATCH", "HR_MAX_CHECKED", "HR_PARAMS", "HEADROOM_METRICS",
    "ratio_middle_term", "ratio_band_estimate", "snapping_bias", "tj_bounds", "tj_conservative_ok", "tj_optimistic_ok",
    "twin_gate_inductance", "twin_gate_thermal", "headroom_lo", "headroom_hi", "headroom_per_reference",
    "headroom_min_lo", "headroom_max_hi_ind", "compute", "gci_capped", "null_column",
]


# >>> metrics.py
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
# <<< metrics.py


# Dispatch entries for mfos.metrics.METRICS (copied verbatim into its dict literal by make_patch.py).
HEADROOM_METRICS = {
    # >>> METRICS
    "headroom_min_lo": lambda rows, pred=None, params=None, **_: headroom_min_lo(rows, pred or "L_sub_H", params),
    "headroom_max_hi_ind": lambda rows, pred=None, params=None, **_: headroom_max_hi_ind(rows, pred or "L_sub_H",
                                                                                          params),
    # <<< METRICS
}


def compute(fn: str, rows: Rows, *, pred: Optional[str] = None, ref: Optional[str] = None, strata: Sequence[str] = (),
            group: Optional[str] = None, role: Optional[str] = None, params: Optional[dict[str, Any]] = None) -> float:
    """mfos.metrics.compute with the two draft metrics added (what compute does once the patch is applied)."""
    if fn in HEADROOM_METRICS:
        return float(HEADROOM_METRICS[fn](rows, pred=pred, ref=ref, strata=list(strata), group=group, role=role,
                                          params=params))
    return _mx.compute(fn, rows, pred=pred, ref=ref, strata=strata, group=group, role=role, params=params)
