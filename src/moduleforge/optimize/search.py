"""Deterministic, resumable multi-fidelity search driver for O003 (D0008, frozen budget F3, founder 2026-11-09).

All solvers are injected (``Solvers``); the driver only orders, budgets and records. It never computes the headroom h
(that belongs to ``mfos.metrics``). Layouts are touched only through ``fingerprint()``.

Procedure (``run_search``):
 1. From a sealed seed, stream ``generate`` until ``n_candidates`` DRC-valid layouts exist (chunks of ``chunk`` with
    sub-seeds derived from ``SeedSequence([seed, chunk_index])``; only L1 and the shortlist are kept in memory).
    L1 for all; levelling record = lowest L1 among the first ``n_first`` and among all.
 2. Shortlist = ``shortlist`` lowest L1 (ties by generation index); ``l_sub`` on each. Inductance-only best =
    lowest L_sub.
 3. Thermal checks in ascending L_sub, batches of ``batch``; stop after the first batch holding a candidate that meets
    the conservative test ``max_i(T_i(C)+GCI_i(C)) - max_j(T_j(W)-GCI_j(W)) <= tj_margin`` (level-2 Tj); at most
    ``max_checks``. Twin and reconstruction are always solved thermally.
 4. L1-only null: shortlist in ascending L1 with the same rule, reusing cached thermal results, at most ``max_checks``
    new solves.
 5. Band solves: reference, twin, A1 best, inductance-only best, and every shortlisted candidate with
    L_sub <= (1 + w_ind) * L_sub(inductance-only best), w_ind = 2 e_R(best_ind, twin) + s_ref.

Every solve is stored in an append-only JSONL checkpoint keyed ``<fingerprint>:<kind>``; a rerun on the same
directory re-solves nothing that is stored.
"""
from __future__ import annotations

import json
import math
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np


@dataclass(frozen=True)
class SearchConfig:
    n_candidates: int = 20_000
    n_first: int = 5_000
    shortlist: int = 16
    batch: int = 4
    max_checks: int = 8
    tj_margin: float = 2.0  # K
    chunk: int = 250  # candidates per generate() call (memory only; changes the stream, so part of the frozen config)


@dataclass
class Solvers:
    """Injected solvers. ``thermal(layout, P)`` returns a mapping ``{"tj": (3, n_die) per-die Tj max at levels 0-2,
    "gci": (n_die,) per-die GCI}`` (or an object with those attributes). ``e_R(pair)`` takes ``(candidate, twin)``."""

    l1: Callable[[Any], float]
    l_sub: Callable[[Any], float]
    band: Callable[[Any], Sequence[float]]
    thermal: Callable[[Any, float], Any]
    e_R: Callable[[tuple], float]


@dataclass
class SearchResult:
    rows: dict[str, list[dict]]
    levelling: dict
    inductance_best: str | None
    a1_best: str | None
    null_best: str | None
    near_ties: list[str] = field(default_factory=list)
    w_ind: float | None = None
    thermal_checked: list[str] = field(default_factory=list)
    null_new_checks: int = 0


class Store:
    """Append-only JSONL checkpoint of solve results."""

    def __init__(self, path: Path | None):
        self.path = path
        self.data: dict[str, Any] = {}
        if path is not None:
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.exists():
                for line in path.read_text().splitlines():
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:  # torn last line after an interrupted write
                        continue
                    self.data[rec["k"]] = rec["v"]
        self.solves = 0  # number of fresh solves in this session

    def get(self, key: str, fn: Callable[[], Any]):
        if key in self.data:
            return self.data[key]
        v = _jsonable(fn())
        self.solves += 1
        self.data[key] = v
        if self.path is not None:
            with self.path.open("a") as f:
                f.write(json.dumps({"k": key, "v": v}) + "\n")
                f.flush()
        return v

    def has(self, key: str) -> bool:
        return key in self.data


def _jsonable(v):
    if isinstance(v, dict):
        return {k: _jsonable(x) for k, x in v.items()}
    if isinstance(v, np.ndarray):
        return v.tolist()
    if isinstance(v, (list, tuple)):
        return [_jsonable(x) for x in v]
    if isinstance(v, np.generic):
        return v.item()
    return v


def candidate_stream(spec, n: int, seed: int, generate: Callable | None = None, chunk: int = 250) -> Iterator:
    """Yield ``n`` layouts from ``generate(spec, m, seed_k)``, chunk by chunk, with ``seed_k`` derived from ``seed``."""
    if generate is None:
        from moduleforge.generate.derivative import generate
    done, k = 0, 0
    while done < n:
        m = min(chunk, n - done)
        sk = int(np.random.SeedSequence([seed, k]).generate_state(1)[0])
        for lay in generate(spec, m, sk):
            yield lay
        done += m
        k += 1


def _thermal_fields(res) -> tuple[list[list[float]], list[float]]:
    if isinstance(res, dict):
        tj, gci = res["tj"], res["gci"]
    else:
        tj, gci = res.tj, res.gci
    return [list(map(float, r)) for r in tj], [float(g) for g in gci]


def conservative_margin(cand: dict, twin: dict) -> float:
    """max_i(T_i(C)+GCI_i(C)) - max_j(T_j(W)-GCI_j(W)) with level-2 Tj; +inf if undefined (inf GCI of C, or a twin
    whose every die has infinite GCI)."""
    tc, gc = np.asarray(cand["tj"][-1], float), np.asarray(cand["gci"], float)
    tw, gw = np.asarray(twin["tj"][-1], float), np.asarray(twin["gci"], float)
    with np.errstate(invalid="ignore"):
        up = np.max(tc + gc)
        lo = np.max(tw - gw)
    if np.isnan(up) or np.isnan(lo) or np.isposinf(up) or np.isneginf(lo):
        return math.inf
    return float(up - lo)


class _Run:
    def __init__(self, solvers: Solvers, store: Store, P: float | None):
        self.s, self.store, self.P = solvers, store, P
        self.rows: dict[str, list[dict]] = {"candidates": [], "tj": [], "band": [], "lsub": [], "e_R": [],
                                            "checks": []}
        self.fp_of: dict[int, str] = {}

    def fp(self, lay) -> str:
        k = id(lay)
        if k not in self.fp_of:
            self.fp_of[k] = lay.fingerprint()
        return self.fp_of[k]

    def l_sub(self, lay) -> float:
        return float(self.store.get(f"{self.fp(lay)}:lsub", lambda: self.s.l_sub(lay)))

    def band(self, lay, role: str) -> list[float]:
        b = self.store.get(f"{self.fp(lay)}:band", lambda: list(self.s.band(lay)))
        self.rows["band"].append({"fingerprint": self.fp(lay), "role": role, "band": b})
        return b

    def thermal(self, lay, role: str) -> dict:
        key = f"{self.fp(lay)}:thermal"
        fresh = not self.store.has(key)

        def solve():
            tj, gci = _thermal_fields(self.s.thermal(lay, self.P))
            return {"tj": tj, "gci": gci}
        res = self.store.get(key, solve)
        if not any(r["fingerprint"] == self.fp(lay) and r["die"] == 0 for r in self.rows["tj"]):
            for i, g in enumerate(res["gci"]):
                self.rows["tj"].append({"fingerprint": self.fp(lay), "role": role, "die": i,
                                        "tj0": res["tj"][0][i], "tj1": res["tj"][1][i], "tj2": res["tj"][2][i],
                                        "gci": g})
        res = dict(res)
        res["fresh"] = fresh
        return res

    def e_R(self, cand, other, role: str) -> float:
        v = float(self.store.get(f"{self.fp(cand)}|{self.fp(other)}:eR", lambda: self.s.e_R((cand, other))))
        self.rows["e_R"].append({"candidate": self.fp(cand), "other": self.fp(other), "role": role, "e_R": v})
        return v


def _screen(run: _Run, spec, seed: int, cfg: SearchConfig, generate):
    """Steps 1-2. Returns (levelling dict, shortlist [(index, layout, l1)] by ascending L1, L_sub by index)."""
    keep: list[tuple[float, int, Any]] = []  # (l1, index, layout), at most cfg.shortlist, sorted
    best_first = math.inf
    best_all = math.inf
    n = 0
    for idx, lay in enumerate(candidate_stream(spec, cfg.n_candidates, seed, generate, cfg.chunk)):
        f = run.fp(lay)
        v = float(run.store.get(f"{f}:l1", lambda lay=lay: run.s.l1(lay)))
        n += 1
        best_all = min(best_all, v)
        if idx < cfg.n_first:
            best_first = min(best_first, v)
        keep.append((v, idx, lay))
        keep.sort(key=lambda t: (t[0], t[1]))
        del keep[cfg.shortlist:]
        run.fp_of = {id(t[2]): run.fp_of[id(t[2])] for t in keep}  # drop fingerprints of discarded layouts
    lev = {"n_candidates": n, "l1_min_first": best_first, "l1_min_all": best_all, "n_first": min(cfg.n_first, n)}
    shortlist = [(i, lay, v) for v, i, lay in keep]
    for rank, (i, lay, v) in enumerate(shortlist):
        run.rows["candidates"].append({"fingerprint": run.fp(lay), "index": i, "l1_rank": rank, "l1": v,
                                       "l_sub": run.l_sub(lay)})
    return lev, shortlist


def _levelled(lev: dict, w_ind: float) -> bool:
    return lev["l1_min_first"] <= (1.0 + w_ind) * lev["l1_min_all"]


def run_search(spec, reference, twin, seed: int, solvers: Solvers, P: float, s_ref: float, workdir: str | Path | None,
               cfg: SearchConfig = SearchConfig(), generate: Callable | None = None) -> SearchResult:
    """Full A1/K1 search for one reference (module docstring). ``twin`` is W, ``reference`` the reconstruction."""
    store = Store(Path(workdir) / "checkpoint.jsonl" if workdir is not None else None)
    run = _Run(solvers, store, P)
    lev, short = _screen(run, spec, seed, cfg, generate)
    lsub = {i: run.l_sub(lay) for i, lay, _ in short}
    lsub_ref, lsub_twin = run.l_sub(reference), run.l_sub(twin)
    run.rows["lsub"] += [{"fingerprint": run.fp(reference), "role": "reference", "l_sub": lsub_ref},
                         {"fingerprint": run.fp(twin), "role": "twin", "l_sub": lsub_twin}]
    tw = run.thermal(twin, "twin")
    run.thermal(reference, "reference")

    asc = sorted(short, key=lambda t: (lsub[t[0]], t[0]))  # ascending L_sub, ties by generation index
    ind_best = asc[0]
    checked: dict[int, float] = {}  # index -> margin

    def check(t, role):
        i, lay, _ = t
        res = run.thermal(lay, role)
        m = conservative_margin(res, tw)
        checked[i] = m
        run.rows["checks"].append({"fingerprint": run.fp(lay), "role": role, "margin": m,
                                   "passes": bool(m <= cfg.tj_margin)})
        return m <= cfg.tj_margin, res["fresh"]

    # A1: ascending L_sub, batches
    a1_best = None
    order: list[str] = []
    for b0 in range(0, min(len(asc), cfg.max_checks), cfg.batch):
        batch = asc[b0:min(b0 + cfg.batch, cfg.max_checks)]
        for t in batch:
            ok, _ = check(t, "a1")
            order.append(run.fp(t[1]))
            if ok and a1_best is None:
                a1_best = t
        if a1_best is not None:
            break

    # null: ascending L1, cached results reused, at most max_checks new solves
    null_best, new = None, 0
    for b0 in range(0, len(short), cfg.batch):
        for t in short[b0:b0 + cfg.batch]:
            cached = t[0] in checked
            if not cached and new >= cfg.max_checks:
                continue
            if cached:
                ok = checked[t[0]] <= cfg.tj_margin
            else:
                ok, fresh = check(t, "null")
                new += 1
                order.append(run.fp(t[1]))
            if ok and null_best is None:
                null_best = t
        if null_best is not None or new >= cfg.max_checks:
            break

    # bands
    run.band(reference, "reference")
    run.band(twin, "twin")
    if a1_best is not None:
        run.band(a1_best[1], "a1_best")
    run.band(ind_best[1], "inductance_best")
    e_ind = run.e_R(ind_best[1], twin, "inductance_best")
    w_ind = 2.0 * e_ind + s_ref
    ties = []
    for t in asc:
        if t[0] != ind_best[0] and lsub[t[0]] <= (1.0 + w_ind) * lsub[ind_best[0]]:
            run.band(t[1], "near_tie")
            ties.append(run.fp(t[1]))
    lev["w_ind"] = w_ind
    lev["levelled"] = _levelled(lev, w_ind)
    return SearchResult(rows=run.rows, levelling=lev, inductance_best=run.fp(ind_best[1]),
                        a1_best=run.fp(a1_best[1]) if a1_best else None,
                        null_best=run.fp(null_best[1]) if null_best else None, near_ties=ties, w_ind=w_ind,
                        thermal_checked=order, null_new_checks=new)


def run_control(spec, d, seed: int, solvers: Solvers, s_ref: float, workdir: str | Path | None,
                cfg: SearchConfig = SearchConfig(), generate: Callable | None = None) -> SearchResult:
    """Control mode (F1(b)): reference = D, a new sealed ``seed``, same budget, inductance only; no thermal solves."""
    store = Store(Path(workdir) / "checkpoint.jsonl" if workdir is not None else None)
    run = _Run(solvers, store, None)
    lev, short = _screen(run, spec, seed, cfg, generate)
    lsub = {i: run.l_sub(lay) for i, lay, _ in short}
    run.rows["lsub"].append({"fingerprint": run.fp(d), "role": "degraded", "l_sub": run.l_sub(d)})
    best = min(short, key=lambda t: (lsub[t[0]], t[0]))
    run.band(d, "degraded")
    run.band(best[1], "control_best")
    e = run.e_R(best[1], d, "control_best")
    w = 2.0 * e + s_ref
    lev["w_ind"] = w
    lev["levelled"] = _levelled(lev, w)
    return SearchResult(rows=run.rows, levelling=lev, inductance_best=run.fp(best[1]), a1_best=None, null_best=None,
                        w_ind=w)
