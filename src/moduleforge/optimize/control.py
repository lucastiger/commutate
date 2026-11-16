"""O008's control: the designer proxy rule, the randomised degradation family and ablation (e) (T0379; item 3a of the
objective notes).  Built on ``local.descend`` and ``local.movable_indices`` (the frozen objective's one parameter set,
``Params.NAMES[twin.WALK_FIRST:twin.WALK_END]``: columns, slots, die rows, landing lines).

Nothing here takes an L2 callable: the proxy rule and the degradation see ``l1`` only; ``draw_degradations`` calls the
injected ``r_d_at_l2`` only to accept or reject a whole draw (F6).

``proxy_descent`` / ``choose_proxy``
    The designer proxy W*: the steepest single-parameter L1 descent from the twin W in 0.5 mm steps, DRC-clean and inside
    ``in_domain(reach=True)``, to a local optimum or the step limit.  ``dies_fixed=True`` is the Tj fallback.  ``choose_proxy``
    takes the lower L_sub of W and the descent's result (W on a tie or a higher L_sub, F3) and records the ratios.
``degrade_draw`` / ``draw_degradations``
    A stochastic L1 ascent from W* by joint moves of 2-4 parameters of the search's set, 0.5-2 mm each (the probe,
    research/o008_probe/probe.py ``ascent``), every accepted state DRC-clean and in ``in_domain(reach=True)``, stopping at the
    frozen L1 target 1.25 x 1.11 (``twin.DEGRADE_RATIO``, ``twin.DEGRADE_MARGIN``).  A draw's sub-seed is
    ``SeedSequence([sealed_seed, layout_index, draw, attempt])``; the draw is accepted if ``r_d_at_l2`` of it lies in
    [1.25, 1.60], else redrawn with the next attempt, at most ``redraw_limit`` redraws.
``proxy_alone``
    Ablation (e): the proxy rule from a degraded D_j with the search's L1 budget and no L2 shortlist.

Column sides: ``twin._net_side`` reads a column's side from the slots' mid-u against the column's, so for a slot that
straddles its column it can differ from the sides under which ``derivative.in_domain`` finds the layout feasible (it tries
both for every net).  ``feasible_sides`` exposes that set so a caller (and the tests) can check the reading.
"""
from __future__ import annotations

import itertools
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

import numpy as np

from moduleforge.generate import derivative as D
from moduleforge.generate import twin as T
from moduleforge.geometry.layout import Layout

from . import local as L

R_D_WINDOW = (1.25, 1.60)  # accepted L_sub(D) / L_sub(W*) (the objective's window)
FROZEN_L1_TARGET = T.DEGRADE_RATIO * (1.0 + T.DEGRADE_MARGIN)  # 1.25 x 1.11 = 1.3875, the L1 stop of a degradation
MIN_GAIN_H = 1e-12  # the probe's step tolerance: score(new) > score(cur) + 1e-12 with score = -L1 in H


# ----------------------------------------------------------------------------------------------------- the proxy rule
@dataclass
class ProxyDescent:
    layout: Layout
    params: D.Params
    l1_start: float
    l1: float  # of ``layout``
    steps: int
    kind: str  # local.LOCAL_OPTIMUM / STEP_LIMIT / BUDGET
    trajectory: list[dict]

    @property
    def l1_ratio(self) -> float:
        return self.l1 / self.l1_start


def proxy_descent(spec: D.ReferenceSpec, W_params: D.Params, l1: Callable[[Layout], float], step_limit: int,
                  dies_fixed: bool = False, reach: bool = True, max_evals: int | None = None,
                  movable: Sequence[int] | None = None, min_gain: float = MIN_GAIN_H) -> ProxyDescent:
    """Steepest single-parameter L1 descent from ``W_params`` in 0.5 mm steps, DRC-clean and in the reach domain, to a local
    optimum or ``step_limit`` steps, over ``local.movable_indices(dies_fixed)`` (die rows included unless ``dies_fixed``,
    in which case the ``row_*`` entries of the result are bit-identical to ``W_params``'s).  ``reach=False`` is the probe's
    rule (build + DRC only, no reach jumps), for regression anchors; ``max_evals`` a budget of distinct L1 evaluations.
    ``min_gain``: a step must lower L1 by more than this (H); the probe's tolerance 1e-12 H (0.001 nH, ~1e-4 relative)."""
    res = L.descend(spec, W_params, l1, movable=movable, step_mm=0.5, step_limit=step_limit, dies_fixed=dies_fixed,
                    reach=reach, max_evals=max_evals, min_gain=min_gain)
    return ProxyDescent(res.layout, res.params, res.trajectory[0]["score"], res.score, res.steps, res.kind, res.trajectory)


@dataclass
class ProxyChoice:
    layout: Layout  # W*
    chosen: str  # "W" or "descent"
    l1_ratio: float  # L1(W*) / L1(W)
    l_sub_ratio: float  # L_sub(W*) / L_sub(W)
    l_sub_W: float
    l_sub_descent: float
    steps: int
    terminal: str  # the descent's terminal kind


def choose_proxy(W: Layout, W_desc: ProxyDescent, l_sub: Callable[[Layout], float]) -> ProxyChoice:
    """W*: the one of ``W`` and the descent's layout with the lower L_sub; ``W`` unless the descent's is strictly lower (F3)."""
    ls_w = float(l_sub(W))
    ls_d = float(l_sub(W_desc.layout))
    pick_d = ls_d < ls_w
    return ProxyChoice(W_desc.layout if pick_d else W, "descent" if pick_d else "W",
                       W_desc.l1_ratio if pick_d else 1.0, ls_d / ls_w if pick_d else 1.0, ls_w, ls_d,
                       W_desc.steps, W_desc.kind)


def proxy_alone(spec: D.ReferenceSpec, D_layout: Layout, l1: Callable[[Layout], float], budget: int,
                dies_fixed: bool = False, step_limit: int = 100_000) -> ProxyDescent:
    """Ablation (e): the proxy rule from ``D_layout`` with the search's L1 budget (distinct L1 evaluations, the start
    included) and no L2 shortlist; the result is the descent's final layout."""
    if budget < 1:
        raise ValueError("budget must be >= 1")
    return proxy_descent(spec, D.params_of(D_layout), l1, step_limit, dies_fixed=dies_fixed, max_evals=budget)


# -------------------------------------------------------------------------------------------------------- degradation
@dataclass(frozen=True)
class DegradeConfig:
    target_ratio: float = FROZEN_L1_TARGET  # stop at L1(D) / L1(W*) >= this
    max_proposals: int = 400
    k_lo: int = 2  # a joint move changes k_lo..k_hi parameters
    k_hi: int = 4
    mags_mm: tuple[float, ...] = (0.5, 1.0, 1.5, 2.0)
    dies_fixed: bool = False

    def __post_init__(self):
        if not (1 <= self.k_lo <= self.k_hi) or self.max_proposals < 1 or not self.mags_mm:
            raise ValueError("invalid DegradeConfig")


@dataclass
class Degradation:
    layout: Layout
    params: D.Params
    l1_ratio: float  # L1(D) / L1(W*)
    proposals: int
    accepted: int
    changed: int  # parameters that differ from W*'s
    manhattan_mm: float
    stop: str  # "target" or "proposals"
    path: list[list[float]] = field(default_factory=list)  # parameter vector after each accepted move


def degrade_draw(spec: D.ReferenceSpec, Wstar_layout: Layout, rng: np.random.Generator, l1: Callable[[Layout], float],
                 cfg: DegradeConfig = DegradeConfig()) -> Degradation:
    """One degradation of W*: stochastic L1 ascent by joint moves over ``local.movable_indices``; a move is accepted if the
    result builds, is DRC-clean, lies in ``in_domain(reach=True)`` and has a higher L1; stops at ``cfg.target_ratio`` or
    after ``cfg.max_proposals`` proposals.  Takes no L2 callable."""
    idx = np.array(L.movable_indices(cfg.dies_fixed))
    sp = L._Space(spec)
    p = D.params_of(Wstar_layout)
    v0 = p.to_vector()
    l_w = float(l1(Wstar_layout))
    cur_v, cur_lay, cur = v0, Wstar_layout, l_w
    n_prop = n_acc = 0
    path: list[list[float]] = []
    stop = "proposals"
    for _ in range(cfg.max_proposals):
        if cur / l_w >= cfg.target_ratio:
            stop = "target"
            break
        n_prop += 1
        v = cur_v.copy()
        k = int(rng.integers(cfg.k_lo, cfg.k_hi + 1))
        for i in rng.choice(idx, size=min(k, len(idx)), replace=False):
            v[i] += float(rng.choice([-1.0, 1.0]) * rng.choice(cfg.mags_mm))
        cl = sp.valid(v, "degrade")
        if cl is None:
            continue
        li = float(l1(cl))
        if li > cur:
            cur_v, cur_lay, cur = v, cl, li
            n_acc += 1
            path.append(v.tolist())
    else:
        if cur / l_w >= cfg.target_ratio:
            stop = "target"
    diff = np.abs(cur_v - v0)
    return Degradation(cur_lay, D.Params.from_vector(cur_v), cur / l_w, n_prop, n_acc, int(np.sum(diff > 1e-9)),
                       float(np.sum(diff)), stop, path)


@dataclass
class DrawRecord:
    draw: int
    layout: Layout | None  # the accepted D_j, None if the redraw limit was exhausted
    accepted: bool
    attempts: int
    r_d: float | None  # achieved R_D of the accepted attempt (None if none was accepted)
    attempt_log: list[dict]  # per attempt: attempt, seed entropy list, l1_ratio, r_d, in_window


def draw_degradations(spec: D.ReferenceSpec, Wstar: Layout, sealed_seed: int, layout_index: int, n_draws: int,
                      r_d_at_l2: Callable[[Layout], float], redraw_limit: int, l1: Callable[[Layout], float],
                      cfg: DegradeConfig = DegradeConfig(), window: tuple[float, float] = R_D_WINDOW) -> list[DrawRecord]:
    """``n_draws`` degradations D_j of ``Wstar``.  Attempt ``a`` of draw ``j`` uses
    ``default_rng(SeedSequence([sealed_seed, layout_index, j, a]))``; ``r_d_at_l2(D)`` (= L_sub(D) / L_sub(W*), injected) is
    called once per attempt, only to accept (``window[0] <= r_d <= window[1]``) or reject the whole draw; a rejected draw is
    redrawn with the next attempt, at most ``redraw_limit`` redraws (``redraw_limit + 1`` attempts).  Every attempt and the
    achieved R_D are recorded (F6); a draw that exhausts the limit is returned with ``accepted=False``."""
    if redraw_limit < 0:
        raise ValueError("redraw_limit must be >= 0")
    out = []
    for j in range(n_draws):
        log: list[dict] = []
        rec = DrawRecord(j, None, False, 0, None, log)
        for a in range(redraw_limit + 1):
            ent = [int(sealed_seed), int(layout_index), j, a]
            rng = np.random.default_rng(np.random.SeedSequence(ent))
            dg = degrade_draw(spec, Wstar, rng, l1, cfg)
            r = float(r_d_at_l2(dg.layout))
            ok = window[0] <= r <= window[1]
            log.append({"attempt": a, "entropy": ent, "l1_ratio": dg.l1_ratio, "r_d": r, "in_window": ok,
                        "changed": dg.changed, "manhattan_mm": dg.manhattan_mm, "stop": dg.stop})
            rec.attempts = a + 1
            if ok:
                rec.layout, rec.accepted, rec.r_d = dg.layout, True, r
                break
        out.append(rec)
    return out


# ------------------------------------------------------------------------------------------------------- column sides
def read_sides(p: D.Params) -> tuple[int, int, int]:
    """The column sides ``twin._net_side`` reads (per net in ``Params.cols`` order)."""
    return tuple(T._net_side(p, q) for q in range(3))  # type: ignore[return-value]


def feasible_sides(spec: D.ReferenceSpec, p: D.Params, ctx: D._Ctx | None = None) -> list[tuple[int, int, int]]:
    """Side tuples (-1 / +1 per net) under which the sampler's replay accepts the side-dependent part of ``p`` (reach
    domain): the sides ``derivative.in_domain`` can certify.  More than one tuple means the reading is ambiguous."""
    cx = ctx if ctx is not None else D._Ctx(spec, reach=True)
    seq = p.sequence()
    sv = [(s[1], s[3]) for s in p.slots]
    hts = [b - a for a, b in sv]
    return [s for s in itertools.product((-1, 1), repeat=3) if D._replay(spec, cx, p, s, seq, sv, hts) is None]


__all__ = ["DegradeConfig", "Degradation", "DrawRecord", "FROZEN_L1_TARGET", "ProxyChoice", "ProxyDescent", "R_D_WINDOW",
           "choose_proxy", "degrade_draw", "draw_degradations", "feasible_sides", "proxy_alone", "proxy_descent",
           "read_sides"]
