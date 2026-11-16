"""Inductance-blind nulls (a), (b), (d) and the random-screen ablation (c) of O008 (item 3b of the objective notes; T0380).

Every null starts at a degraded copy ``D_j`` (a layout that builds and is DRC-clean under ``spec.rules``) and returns a
``NullResult``.  (a), (b) and (d) contain no inductance model: their scores are geometric (power copper area, power-wire
length), and they take no solver.  (c) is the D0008 random screen alone and uses ``l1`` and ``l_sub`` as the search does.

(a) ``null_seed``     returns ``D_j`` unchanged.
(b) ``null_widen``    widen every power band toward its DRC limit: ``local.descend`` on the score ``-A`` with ``A`` the area
                      of the union of the power-net copper (mm^2), as the probe's ``widen`` mode (research/o008_probe).
(d) ``null_compact``  more power copper and shorter power wires: the probe's ``compact`` score ``A - W`` (mm^2 of copper
                      minus mm of power wire, 1 mm^2 against 1 mm), keeping only moves that do not reduce ``A`` and do not
                      lengthen ``W`` (review T0354).  The constraint is relative to the current layout, so the descent is
                      run one ``descend`` step at a time with the constraint anchored at the current layout.
(c) ``ablation_random_screen``  ``search.candidate_stream`` over ``derivative.generate(reach=True)`` (the reach sampler,
                      n1), ``cfg.budget`` draws screened by L1, the ``cfg.shortlist`` lowest-L1 distinct layouts to
                      ``l_sub``, the lowest ``l_sub`` returned.  No local move.

(b) and (d) move exactly the parameters ``local.movable_indices()`` returns (``descend``'s default) and every layout they
visit is DRC-clean and in ``in_domain(reach=True)``.  Each runs to its own local optimum within ``NULL_STEP_LIMIT`` steps and
records its terminal kind (``local_optimum`` or ``step_limit``); a run capped at the limit is not a resolved failure of
the null (A3, review T0359).  Every null records ``steps``, ``changed_params`` and ``manhattan_mm`` from ``D_j`` (over the
whole parameter vector, in mm).
"""
from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import partial

import numpy as np
from shapely.ops import unary_union

from moduleforge.generate import derivative as D
from moduleforge.geometry.layout import NETS, Layout

from .local import LOCAL_OPTIMUM, STEP_LIMIT, LocalConfig, LocalSolvers, descend
from .search import candidate_stream

NULL_STEP_LIMIT = 200  # frozen: generous (the probe's proxy descent used 200; its nulls 60 and several hit that cap)
_TOL = 1e-9


@dataclass
class NullResult:
    name: str  # seed | widen | compact | random_screen
    layout: Layout
    params: D.Params
    steps: int
    terminal: str  # LOCAL_OPTIMUM, STEP_LIMIT, or "none" for (a) and (c), which do not descend
    changed_params: int
    manhattan_mm: float
    score_trajectory: list[float] = field(default_factory=list)  # blind score (higher is better) at step 0, 1, ...
    stats: dict = field(default_factory=dict)


def power_copper_mm2(lay: Layout) -> float:
    """Area (mm^2) of the union of the copper traces of each power net, summed over the nets (the probe's copper_mm2)."""
    return sum(unary_union([t.polygon for t in lay.traces if t.net == n]).area for n in NETS) * 1e6


def power_wire_mm(lay: Layout) -> float:
    """Total length (mm) of the power-net wires."""
    return sum(w.length for w in lay.wires if w.net in NETS) * 1e3


def compact_score(lay: Layout) -> float:
    """The probe's compact score: power copper area (mm^2) minus power-wire length (mm); higher is better."""
    return power_copper_mm2(lay) - power_wire_mm(lay)


def _result(name, start: Layout, lay: Layout, steps, terminal, traj, stats=None) -> NullResult:
    v0, v1 = D.params_of(start).to_vector(), D.params_of(lay).to_vector()
    diff = np.abs(v1 - v0)
    return NullResult(name, lay, D.params_of(lay), int(steps), terminal, int(np.sum(diff > _TOL)), float(np.sum(diff)),
                      list(traj), dict(stats or {}))


def null_seed(spec: D.ReferenceSpec, d: Layout, solvers: LocalSolvers | None = None) -> NullResult:
    """(a) ``D_j`` unchanged.  ``solvers`` is never called."""
    return _result("seed", d, d, 0, "none", [])


def null_widen(spec: D.ReferenceSpec, d: Layout, step_limit: int = NULL_STEP_LIMIT,
               solvers: LocalSolvers | None = None) -> NullResult:
    """(b) steepest widening of the power copper from ``d`` to a local optimum of the area, or ``step_limit`` steps.
    ``solvers`` is never called."""
    r = descend(spec, D.params_of(d), lambda lay: -power_copper_mm2(lay), step_limit=step_limit)
    return _result("widen", d, r.layout, r.steps, r.kind, [-t["score"] for t in r.trajectory])


def null_compact(spec: D.ReferenceSpec, d: Layout, step_limit: int = NULL_STEP_LIMIT,
                 solvers: LocalSolvers | None = None) -> NullResult:
    """(d) steepest ascent of ``compact_score`` over the moves that neither reduce the power copper nor lengthen the power
    wires, to a local optimum or ``step_limit`` steps.  ``solvers`` is never called."""
    p, lay = D.params_of(d), d
    traj = [compact_score(lay)]
    steps, kind = 0, LOCAL_OPTIMUM
    while True:
        if steps >= step_limit:
            kind = STEP_LIMIT
            break
        a0, w0 = power_copper_mm2(lay), power_wire_mm(lay)

        def score(cl: Layout, a0=a0, w0=w0) -> float:
            a, w = power_copper_mm2(cl), power_wire_mm(cl)
            return math.inf if (a < a0 - _TOL or w > w0 + _TOL) else -(a - w)

        r = descend(spec, p, score, step_limit=1)
        if r.steps == 0:
            break
        p, lay, steps = r.params, r.layout, steps + 1
        traj.append(compact_score(lay))
    return _result("compact", d, lay, steps, kind, traj)


def ablation_random_screen(spec: D.ReferenceSpec, d: Layout, seed: int, solvers: LocalSolvers,
                           cfg: LocalConfig = LocalConfig(), chunk: int = 250,
                           generate: Callable | None = None) -> NullResult:
    """(c) the random screen alone: ``cfg.budget`` draws of the reach sampler (``candidate_stream``, sub-seeds from
    ``seed``), L1 on each distinct layout (a repeated fingerprint is solved once), ``cfg.shortlist`` lowest-L1 distinct
    layouts (ties by draw index) to ``solvers.l_sub``, the lowest ``l_sub`` (ties by L1 rank) returned.  ``d`` is used
    only for the recorded distance.  ``stats``: l1_evals, l_sub_evals, n_draws, shortlist (fingerprint, l1, l_sub)."""
    gen = generate if generate is not None else partial(D.generate, reach=True)
    l1s: dict[str, float] = {}
    first: dict[str, tuple[int, Layout]] = {}
    for i, lay in enumerate(candidate_stream(spec, cfg.budget, seed, gen, chunk)):
        fp = lay.fingerprint()
        if fp not in l1s:
            l1s[fp] = float(solvers.l1(lay))
            first[fp] = (i, lay)
    order = sorted(l1s, key=lambda f: (l1s[f], first[f][0]))[:cfg.shortlist]
    short = [{"fingerprint": f, "l1": l1s[f], "l_sub": float(solvers.l_sub(first[f][1]))} for f in order]
    bi = min(range(len(short)), key=lambda i: (short[i]["l_sub"], i))
    best = first[short[bi]["fingerprint"]][1]
    stats = {"l1_evals": len(l1s), "l_sub_evals": len(short), "n_draws": cfg.budget, "shortlist": short,
             "budget": cfg.budget}
    return _result("random_screen", d, best, 0, "none", [], stats)


__all__ = ["NULL_STEP_LIMIT", "NullResult", "ablation_random_screen", "compact_score", "null_compact", "null_seed",
           "null_widen", "power_copper_mm2", "power_wire_mm"]
