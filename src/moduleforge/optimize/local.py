"""Seeded local search over the derivative parameterisation (O008, item 2 of the objective notes; T0378).

Two public pieces, both over ``derivative.Params`` (mm, local frame) under ``spec.rules`` (the reference's own measured
design rules, a hard constraint):

``descend(spec, params, score, movable, step_mm, step_limit, dies_fixed)``
    The shared primitive: steepest single-parameter descent.  At each step every candidate of the neighbourhood is built and
    must be DRC-clean and satisfy ``in_domain(spec, ., reach=True)``; the lowest-score one that is strictly lower than the
    current score is taken, ties going to the first candidate in ``Params.NAMES`` order (then the reach jumps).  It stops at
    a local optimum (no valid neighbour is strictly lower) or after ``step_limit`` steps and returns the terminal kind
    (``LOCAL_OPTIMUM`` / ``STEP_LIMIT`` / ``BUDGET``; at the limit the neighbourhood is not examined once more), the step count and the
    trajectory.  The proxy rule and the nulls reuse it with other scores.

``local_search(spec, seed_layout, seed, solvers, cfg, workdir, score)``
    The seeded search.  Its inputs are the spec, the layout it is seeded at and an integer seed; no argument can carry W,
    W* or their values.  Each iteration screens (L1, through the injected ``score``) the DRC-valid single-parameter
    neighbourhood of the current layout plus ``cfg.n_joint`` seeded joint moves (2..``joint_k_max`` parameters, 1..
    ``joint_steps_max`` grid steps each) and takes the best strictly improving one; when none improves it perturbs (a seeded
    larger joint move from the lowest-score visited layout, accepted whatever its score).  The budget is counted in L1
    evaluations: one per distinct layout fingerprint visited (a fingerprint already in the checkpoint still counts, so a
    resumed run walks the identical path), and the search spends it exactly unless it runs out of valid moves.  At the end
    the ``cfg.shortlist`` lowest-score distinct visited layouts go to ``solvers.l_sub``; the best is the lowest L_sub.
    All randomness is ``numpy.random.default_rng(SeedSequence([seed, kind, counter]))``; there is no global state.  Every
    solve is appended to a JSONL ``Store`` (``search.Store``), so a rerun on the same workdir re-solves nothing.

Movable parameters (``movable_indices``): the columns, slots, die rows and landing lines (``Params.NAMES[4:40]``, 0.5 mm
steps, ``twin.WALK_FIRST:WALK_END``), the frozen objective's set.  The power-wire foot offsets (``foot_*_land_*``) do not
move (founder decision 2026-11-16).  ``dies_fixed`` removes the die rows (``row_*``).  The integer flags never move.  Besides
the +-step changes the neighbourhood holds the reach jumps of ``twin._walk_candidates(reach=True)`` (a slot end to the column
edge or the outline limit, a column edge to the limit or back to its pad); a jump is offered only if every parameter it
changes is movable.

Domain.  Every layout the search moves to (every candidate of ``descend``) satisfies ``in_domain(spec, ., reach=True)``, so
the search's moves are kept inside the domain: a candidate outside it is never evaluated, never counted in the budget and
never visited.  The seed layout itself is only required to build and be DRC-clean (a degraded copy made by a walk can lie
outside the domain: ``in_domain`` is a superset test of the sampler's support, with no upper bound on the stack gaps, and the
twin's walk can leave it); ``stats['seed_in_domain']`` says whether it did.  If it did not and no neighbour is in the domain,
the search ends with ``stop_reason == 'no_moves'``.  The yield of the moves (valid / proposed, per kind) is in
``stats['yield']``.

Cost: the dominant cost of a proposal is ``in_domain`` (a build, ``_quick_ok`` and a DRC check), of a visited layout the L1
solve; ``stats['l1_s_per_eval']`` is the measured wall time per fresh L1 evaluation.
Measured (T0378, 2026-11-16, 2D_Case_4's development spec and twin, ``twin._l1``, one process): 0.013-0.016 s per L1
evaluation (800 evaluations: 12.7 s of L1 in 15.9 s wall).  Yield of the moves there (valid / proposed, 800 evaluations):
single +-step 68 %, reach jumps 52 %, joint moves 22 % (perturbations on the 70x40 housing with a synthetic score: 6 %).
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import math
import time
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from moduleforge.generate import derivative as D
from moduleforge.generate import twin as T
from moduleforge.geometry.layout import Layout

from .search import Store

LOCAL_OPTIMUM, STEP_LIMIT, BUDGET = "local_optimum", "step_limit", "budget"  # terminal kinds of descend
NAMES = D.Params.NAMES


def movable_indices(dies_fixed: bool = False) -> tuple[int, ...]:
    """The parameters the hypothesis names, as indices into ``Params.NAMES`` in that order (die rows dropped if
    ``dies_fixed``)."""
    idx = range(T.WALK_FIRST, T.WALK_END)
    return tuple(i for i in idx if not (dies_fixed and NAMES[i].startswith("row_")))


def _norm_movable(movable: Iterable[int | str] | None, dies_fixed: bool) -> tuple[int, ...]:
    if movable is None:
        return movable_indices(dies_fixed)
    idx = {NAMES.index(m) if isinstance(m, str) else int(m) for m in movable}
    bad = [i for i in idx if not 4 <= i < len(NAMES)]
    if bad:
        raise ValueError(f"parameter indices {bad} are not movable (the four flags never move)")
    return tuple(i for i in sorted(idx) if not (dies_fixed and NAMES[i].startswith("row_")))


def _step_of(i: int, step_mm: float) -> float:
    return step_mm


def _rects_ok(p: D.Params) -> bool:
    return not any(c[0] >= c[2] - 1e-9 or c[1] >= c[3] - 1e-9 for c in p.cols + p.slots)


class _Space:
    """DRC-valid, in-domain candidates of one spec: validity cache and yield counters."""

    def __init__(self, spec: D.ReferenceSpec, reach: bool = True):
        self.spec = spec
        self.reach = reach
        self.ctx = D._Ctx(spec, reach=True) if reach else None
        self.cache: dict[bytes, Layout | None] = {}
        self.tally: dict[str, list[int]] = {}  # kind -> [proposed, valid]

    def valid(self, vec: np.ndarray, kind: str = "other") -> Layout | None:
        t = self.tally.setdefault(kind, [0, 0])
        t[0] += 1
        key = vec.tobytes()
        if key not in self.cache:
            lay = None
            try:
                p = D.Params.from_vector(vec)
                if self.reach:
                    if _rects_ok(p) and D.in_domain(self.spec, p, reach=True, ctx=self.ctx)[0]:
                        lay = D.build(self.spec, p)
                elif _rects_ok(p):  # reach off: a layout that builds and is DRC-clean under spec.rules (the probe's rule)
                    cand = D.build(self.spec, p)
                    lay = cand if not _drc(cand, self.spec) else None
            except ValueError:
                lay = None
            self.cache[key] = lay
        lay = self.cache[key]
        t[1] += lay is not None
        return lay

    def neighbours(self, vec: np.ndarray, idx: Sequence[int], step_mm: float, p: D.Params):
        """(kind, tag, vector) of the single-parameter neighbourhood in order: -step, +step per parameter in NAMES order,
        then the reach jumps."""
        for i in idx:
            s = _step_of(i, step_mm)
            for d in (-s, s):
                v = vec.copy()
                v[i] += d
                yield "single", NAMES[i], v
        if not self.reach:
            return
        names, movable = set(NAMES), set(idx)
        for tag, _, q in T._walk_candidates(p, self.spec, reach=True):
            if tag not in names:
                w = q.to_vector()
                if all(j in movable for j in np.flatnonzero(np.abs(w - vec) > 1e-12)):
                    yield "jump", tag, w


@dataclass
class DescentResult:
    kind: str  # LOCAL_OPTIMUM, STEP_LIMIT or BUDGET
    steps: int
    trajectory: list[dict]  # step 0 is the start; each later entry: step, move, delta, score, fingerprint
    params: D.Params
    layout: Layout
    score: float


def descend(spec: D.ReferenceSpec, params: D.Params, score: Callable[[Layout], float],
            movable: Iterable[int | str] | None = None, step_mm: float = 0.5, step_limit: int = 200,
            dies_fixed: bool = False, reach: bool = True, max_evals: int | None = None,
            min_gain: float = 0.0) -> DescentResult:
    """Steepest single-parameter descent of ``score`` (lower is better) from ``params`` (module docstring).  ``params``
    must build and be DRC-clean under ``spec.rules`` (ValueError otherwise); every candidate must also be in the reach domain.
    ``movable``: parameter indices or names (None: ``movable_indices``); ``dies_fixed`` drops the die rows.  ``reach=False``
    (the probe's rule, for regression anchors): no reach jumps and no domain test, only build + DRC under ``spec.rules``.
    ``max_evals``: a budget of distinct score evaluations (the start counts); when the next evaluation would exceed it the
    step in progress takes the best improving candidate evaluated so far and the descent ends with kind ``BUDGET``.  ``min_gain``: a candidate must be lower than the
    current score by more than this (default 0: strictly lower)."""
    idx = _norm_movable(movable, dies_fixed)
    sp = _Space(spec, reach)
    lay = D.build(spec, params)
    if _drc(lay, spec):
        raise ValueError("the start layout is not DRC-clean under spec.rules")
    memo: dict[str, float] = {}

    class _Out(Exception):
        pass

    def sc(layout: Layout) -> float:
        fp = layout.fingerprint()
        if fp not in memo:
            if max_evals is not None and len(memo) >= max_evals:
                raise _Out
            memo[fp] = float(score(layout))
        return memo[fp]

    cur = sc(lay)
    traj = [{"step": 0, "move": None, "delta": 0.0, "score": cur, "fingerprint": lay.fingerprint(),
             "vec": params.to_vector().tolist()}]
    p = params
    steps = 0
    while steps < step_limit:
        vec = p.to_vector()
        best, out_of_budget = None, False
        try:
            for kind, tag, v in sp.neighbours(vec, idx, step_mm, p):
                cl = sp.valid(v, kind)
                if cl is None:
                    continue
                s = sc(cl)
                if s < cur - min_gain and (best is None or s < best[0]):
                    best = (s, tag, v, cl)
        except _Out:
            out_of_budget = True  # the best improving candidate evaluated so far is still taken, then the descent ends
        if best is None:
            return DescentResult(BUDGET if out_of_budget else LOCAL_OPTIMUM, steps, traj, p, lay, cur)
        cur, tag, v, lay = best
        delta = float(np.sum(v - vec))
        p = D.Params.from_vector(v)
        steps += 1
        traj.append({"step": steps, "move": tag, "delta": delta, "score": cur, "fingerprint": lay.fingerprint(),
                     "vec": v.tolist()})
        if out_of_budget:
            return DescentResult(BUDGET, steps, traj, p, lay, cur)
    return DescentResult(STEP_LIMIT, steps, traj, p, lay, cur)


def _drc(lay: Layout, spec: D.ReferenceSpec):
    from moduleforge.drc.rules import check
    return check(lay, spec.rules)


# ----------------------------------------------------------------------------------------------------- the search
@dataclass(frozen=True)
class LocalConfig:
    budget: int = 2000  # L1 evaluations (distinct layouts)
    shortlist: int = 8  # K layouts sent to l_sub
    step_mm: float = 0.5
    n_joint: int = 12  # joint moves proposed per iteration
    joint_k_max: int = 4  # a joint move changes 2..joint_k_max parameters
    joint_steps_max: int = 4  # each by 1..joint_steps_max grid steps
    perturb_k_max: int = 6  # a perturbation changes 3..perturb_k_max parameters
    perturb_steps_max: int = 8
    perturb_tries: int = 200  # proposals per perturbation before the search gives up (stop_reason 'no_moves')
    max_iters: int = 100_000  # guard against an endless walk over already visited layouts
    dies_fixed: bool = False

    def __post_init__(self):
        if self.budget < 1 or self.shortlist < 1:
            raise ValueError(f"budget and shortlist must be >= 1 (got budget={self.budget}, shortlist={self.shortlist})")

    def hash(self) -> str:
        """Stable hash of the config (sha256 of its sorted JSON, first 16 hex digits)."""
        s = json.dumps(dataclasses.asdict(self), sort_keys=True)
        return hashlib.sha256(s.encode()).hexdigest()[:16]


@dataclass
class LocalSolvers:
    """Injected solvers.  ``l1(layout)``: the screen (seconds-scale at most); ``l_sub(layout)``: the shortlist solver
    (``l2_layout`` at 0.25 mm in the runner).  Neither may see anything but the layout."""

    l1: Callable[[Layout], float]
    l_sub: Callable[[Layout], float]
    tag: str = ""  # identifies the solver configuration (e.g. "lsub0.25mm"); part of every checkpoint key


def default_score(layout: Layout, out: dict[str, float]) -> float:
    """Default screen score: L1 of the commutation loop.  Hook signature ``score(layout, solver_outputs) -> float`` (lower
    is better); thermal and current-sharing terms can be added later from other solver outputs."""
    return out["l1"]


@dataclass
class LocalResult:
    best: Layout
    best_params: D.Params
    best_fingerprint: str
    shortlist: list[dict]  # rank, fingerprint, score, l1, l_sub (by ascending score)
    stats: dict
    trajectory: list[dict]
    visited: list[tuple[str, list[float]]]  # (fingerprint, parameter vector) in visit order


class _Budget(Exception):
    pass


def _rank(a: np.ndarray) -> np.ndarray:
    order = np.argsort(a, kind="stable")
    r = np.empty(len(a))
    srt = a[order]
    i = 0
    while i < len(a):
        j = i
        while j + 1 < len(a) and srt[j + 1] == srt[i]:
            j += 1
        r[order[i:j + 1]] = 0.5 * (i + j) + 1.0
        i = j + 1
    return r


def spearman(a: Sequence[float], b: Sequence[float]) -> float:
    """Spearman rank correlation (Pearson on average ranks); NaN for fewer than 3 points or a constant column."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    if len(a) < 3:
        return math.nan
    ra, rb = _rank(a) - _rank(a).mean(), _rank(b) - _rank(b).mean()
    den = math.sqrt(float(ra @ ra) * float(rb @ rb))
    return float(ra @ rb / den) if den > 0 else math.nan


def _joint(rng: np.random.Generator, vec: np.ndarray, idx: Sequence[int], k_lo: int, k_hi: int, steps_max: int,
           step_mm: float) -> np.ndarray:
    k = int(rng.integers(k_lo, min(k_hi, len(idx)) + 1))
    chosen = sorted(rng.choice(len(idx), size=k, replace=False).tolist())
    v = vec.copy()
    for c in chosen:
        i = idx[c]
        v[i] += float(rng.choice([-1.0, 1.0])) * int(rng.integers(1, steps_max + 1)) * _step_of(i, step_mm)
    return v


def local_search(spec: D.ReferenceSpec, seed_layout: Layout, seed: int, solvers: LocalSolvers,
                 cfg: LocalConfig = LocalConfig(), workdir: str | Path | None = None,
                 score: Callable[[Layout, dict[str, float]], float] = default_score) -> LocalResult:
    """Seeded local search (module docstring).  ``seed_layout`` must come from ``derivative.build`` / ``generate`` and be
    DRC-clean under ``spec.rules``."""
    store = Store(Path(workdir) / "local_checkpoint.jsonl" if workdir is not None else None)
    idx = movable_indices(cfg.dies_fixed)
    sp = _Space(spec)
    p0 = D.params_of(seed_layout)
    v0 = p0.to_vector()
    if _drc(seed_layout, spec):
        raise ValueError("the seed layout is not DRC-clean under spec.rules")
    seed_in_domain = D.in_domain(spec, p0, reach=True, ctx=sp.ctx)[0]

    visited: dict[str, dict] = {}  # fingerprint -> {score, l1, vec, order}
    st = {"n": 0, "best": math.inf, "last_improve": 0, "fresh": 0, "secs": 0.0}

    def evaluate(lay: Layout, vec: np.ndarray) -> float:
        fp = lay.fingerprint()
        rec = visited.get(fp)
        if rec is not None:
            return rec["score"]
        if st["n"] >= cfg.budget:
            raise _Budget
        def solve():
            t = time.perf_counter()
            v = float(solvers.l1(lay))
            st["fresh"] += 1
            st["secs"] += time.perf_counter() - t
            return v
        l1 = float(store.get(f"local:{solvers.tag}:{fp}:l1", solve))
        s = float(score(lay, {"l1": l1}))
        st["n"] += 1
        visited[fp] = {"score": s, "l1": l1, "vec": vec.tolist(), "order": st["n"]}
        if s < st["best"]:
            st["best"], st["last_improve"] = s, st["n"]
        return s

    traj: list[dict] = []
    counts = {"steps": 0, "perturbations": 0, "moves": 0}
    cur_vec = v0
    stop = "budget"
    try:
        cur = evaluate(seed_layout, v0)
        for it in range(1, cfg.max_iters + 1):
            rng = np.random.default_rng(np.random.SeedSequence([seed, 1, it]))
            cands = list(sp.neighbours(cur_vec, idx, cfg.step_mm, D.Params.from_vector(cur_vec)))
            cands += [("joint", "joint", _joint(rng, cur_vec, idx, 2, cfg.joint_k_max, cfg.joint_steps_max, cfg.step_mm))
                      for _ in range(cfg.n_joint)]
            best = None
            for kind, tag, v in cands:
                cl = sp.valid(v, kind)
                if cl is None:
                    continue
                s = evaluate(cl, v)
                if s < cur and (best is None or s < best[0]):
                    best = (s, kind, tag, v, cl)
            if best is not None:
                cur, kind, tag, cur_vec, _ = best
                counts["steps"] += 1
                counts["moves"] += 1
                traj.append({"it": it, "kind": kind, "move": tag, "score": cur, "n_l1": st["n"]})
                continue
            # stuck: perturb the lowest-score visited layout (first in visit order on ties), accept whatever the score
            base = min(visited.values(), key=lambda r: (r["score"], r["order"]))
            bvec = np.asarray(base["vec"])
            prng = np.random.default_rng(np.random.SeedSequence([seed, 2, counts["perturbations"]]))
            for _ in range(cfg.perturb_tries):
                v = _joint(prng, bvec, idx, 3, cfg.perturb_k_max, cfg.perturb_steps_max, cfg.step_mm)
                cl = sp.valid(v, "perturb")
                if cl is not None:
                    break
            else:
                stop = "no_moves"
                break
            cur_vec = v
            cur = evaluate(cl, v)
            counts["perturbations"] += 1
            counts["moves"] += 1
            traj.append({"it": it, "kind": "perturb", "move": "perturb", "score": cur, "n_l1": st["n"]})
        else:
            stop = "max_iters"
    except _Budget:
        stop = "budget"

    order = sorted(visited.items(), key=lambda kv: (kv[1]["score"], kv[1]["order"]))[:cfg.shortlist]
    short = []
    for rank, (fp, rec) in enumerate(order):
        lay = D.build(spec, D.Params.from_vector(np.asarray(rec["vec"])))
        ls = float(store.get(f"local:{solvers.tag}:{fp}:lsub", lambda lay=lay: float(solvers.l_sub(lay))))
        short.append({"rank": rank, "fingerprint": fp, "score": rec["score"], "l1": rec["l1"], "l_sub": ls,
                      "vec": rec["vec"]})
    bi = min(range(len(short)), key=lambda i: (short[i]["l_sub"], i))
    bvec = np.asarray(short[bi]["vec"])
    bp = D.Params.from_vector(bvec)
    best_lay = D.build(spec, bp)
    diff = np.abs(bvec - v0)
    ratio = [r["l_sub"] / r["l1"] for r in short if r["l1"] > 0]
    n_l1 = st["n"]
    stats = {
        **counts, "l1_evals": n_l1, "budget": cfg.budget, "stopped_at_budget": n_l1 >= cfg.budget,
        "stop_reason": stop, "last_improve_eval": st["last_improve"],
        "improving_last10": bool(st["last_improve"] > 0.9 * cfg.budget),
        "changed_params": int(np.sum(diff > 1e-9)), "manhattan_mm": float(np.sum(diff)),
        "seed_in_domain": bool(seed_in_domain), "n_visited": len(visited), "shortlist_k": len(short),
        "spearman_l1_lsub": spearman([r["l1"] for r in short], [r["l_sub"] for r in short]),
        "l2_l1_min": min(ratio, default=math.nan), "l2_l1_max": max(ratio, default=math.nan),
        "l1_fresh": st["fresh"], "l1_seconds": st["secs"],
        "l1_s_per_eval": st["secs"] / st["fresh"] if st["fresh"] else math.nan,
        "yield": {k: {"proposed": a, "valid": b, "rate": b / a if a else math.nan} for k, (a, b) in sp.tally.items()},
        "cfg_hash": cfg.hash(),
    }
    return LocalResult(best_lay, bp, short[bi]["fingerprint"], short, stats, traj,
                       [(fp, r["vec"]) for fp, r in visited.items()])


__all__ = ["BUDGET", "LOCAL_OPTIMUM", "STEP_LIMIT", "DescentResult", "LocalConfig", "LocalResult", "LocalSolvers",
                      "default_score", "descend", "local_search", "movable_indices", "spearman"]
