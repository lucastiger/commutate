"""Deterministic, resumable multi-fidelity search driver for O003 (D0008, frozen budget F3, founder 2026-11-09).

All solvers are injected (``Solvers``); the driver only orders, budgets and records. It never computes the headroom h
(that belongs to ``mfos.metrics``). Layouts are touched only through ``fingerprint()``.

Procedure (``run_search``):
 1. From a sealed seed, stream ``generate`` until ``n_candidates`` DRC-valid layouts exist (chunks of ``chunk`` with
    sub-seeds derived from ``SeedSequence([seed, chunk_index])``; only L1 and the shortlist are kept in memory).
    L1 for all; levelling record = lowest L1 among the first ``n_first`` and among all.
 2. Shortlist = ``shortlist`` lowest L1 (ties by generation index), de-duplicated by fingerprint (the first in L1 order is kept and the next
    unique layout is taken); ``l_sub`` on each. Inductance-only best = lowest L_sub.
 3. Thermal checks in ascending L_sub, batches of ``batch``; stop after the first batch holding a candidate that meets
    the conservative test ``max_i(T_i(C)+GCI_i(C)) - max_j(T_j(W)-GCI_j(W)) <= tj_margin`` (level-2 Tj); at most
    ``max_checks``. Twin and reconstruction are always solved thermally. GCI_i is computed here by
    ``mfos.metrics.gci_capped`` (floor 1e-3 K) from the returned per-level Tj values, never taken from the callable.
 4. L1-only null (F1): the first ``max_checks`` shortlist positions in ascending L1, batches of ``batch``, cached
    thermal results reused, stop after the first batch holding a passing candidate, return the first passing
    candidate in L1 order (None if positions 1..max_checks all fail). Never passes over an unchecked candidate.
 5. Band solves: reference, twin, A1 best, inductance-only best, and every shortlisted candidate with
    L_sub <= (1 + w_ind) * L_sub(inductance-only best), w_ind = 2 e_R(best_ind, twin) + s_ref. Every e_R (that one,
    the A1 best's, every near tie's, and the control best's) is ``band_e_R`` of the stored band solves (P3's estimator
    on the ratio); each recorded e_R row has ``"estimator": "band_e_R"``.
 6. Pool statistics: the twin's L1 and the median L1 (and median L1 headroom vs the twin) of the DRC-valid pool.

Every solve is stored in an append-only JSONL checkpoint keyed ``<namespace>:<fingerprint>:<kind>`` (namespace
``main`` for the search, ``control`` for control mode); a rerun on the same directory re-solves nothing that is stored.
The thermal record of each solve is a whitelist (``THERMAL_REQUIRED``: per level per-die Tj max and its node
coordinates, node counts, fingerprint, energy balance, Picard convergence, plus the driver's own gci); nodal fields and
meshes are never stored. A torn trailing line is repaired by truncating in place.

Band vector order (``Solvers.band``), as in research/o003/headroom_metrics.py: [L(0.25 mm cells, production), then at
0.5 mm cells: production layers 10/6/6 and wires, layers 5/3/3, layers 20/12/12, wire annuli bisected with 12
filaments per ring].
"""
from __future__ import annotations

import json
import math
import os
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from mfos.metrics import gci_capped

GCI_FLOOR_K = 1e-3  # scope_in: gci_capped floor, ten times the Picard tolerance
MAX_RECORD_ARRAY = 10_000  # elements; larger arrays (nodal fields, meshes) are never written to the checkpoint
E_R_ESTIMATOR = "band_e_R"  # the one e_R estimator of the driver; every recorded e_R row names it
# Fields a thermal solve must return per thermally checked layout (all kept in the checkpoint, nothing else is):
# tj (3, n_die) per-die Tj max at levels 0-2, tj_max_node (node coordinates of those maxima), nodes (node count per
# level), fingerprint (layout fingerprint), energy_balance, picard (convergence).
THERMAL_REQUIRED = ("tj", "tj_max_node", "nodes", "fingerprint", "energy_balance", "picard")


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
    """Injected solvers. ``thermal(layout, P)`` returns a mapping or an attribute object (namedtuple, dataclass,
    ``SimpleNamespace``) with the fields ``THERMAL_REQUIRED``; ``tj`` is the (3, n_die) per-die Tj max at levels 0-2.
    Only those fields (and an optional ``gci``, kept as ``gci_reported`` and never used) are stored; a missing required
    field raises ``ValueError`` and an array above ``MAX_RECORD_ARRAY`` elements raises ``ValueError``. ``band(layout)``
    returns the five band levels; every e_R of the driver is ``band_e_R`` of stored band solves (there is no injected
    e_R)."""

    l1: Callable[[Any], float]
    l_sub: Callable[[Any], float]
    band: Callable[[Any], Sequence[float]]
    thermal: Callable[[Any, float], Any]


@dataclass
class SearchResult:
    rows: dict[str, list[dict]]
    levelling: dict
    inductance_best: str | None
    a1_best: str | None
    null_best: str | None
    near_ties: list[str] = field(default_factory=list)
    w_ind: float | None = None
    w_ctrl: float | None = None  # control mode only: 2 e_R(control best, D), no s_ref term (F1(b))
    w_a1: float | None = None  # 2 e_R(A1 best, twin) + s_ref from the band solves
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
                raw = path.read_bytes()
                if raw and not raw.endswith(b"\n"):
                    # torn trailing line after an interrupted write: keep it if it is a complete record (append the
                    # missing newline), else truncate in place to the last newline. Never a full rewrite, so a kill
                    # during the repair can lose at most the torn record.
                    cut = raw.rfind(b"\n") + 1
                    try:
                        json.loads(raw[cut:])
                        with path.open("ab") as f:
                            f.write(b"\n")
                        raw += b"\n"
                    except json.JSONDecodeError:
                        os.truncate(path, cut)
                        raw = raw[:cut]
                for line in raw.decode().splitlines():
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
    """Plain-JSON copy of ``v``: dicts, lists/tuples, numpy arrays and scalars, str/bool/int/float/None. Anything else
    (arbitrary objects, meshes, field evaluators) raises ``TypeError``; an array or list above ``MAX_RECORD_ARRAY``
    elements raises ``ValueError``, so nodal fields cannot reach the checkpoint."""
    if isinstance(v, np.ndarray):
        if v.size > MAX_RECORD_ARRAY:
            raise ValueError(f"array of {v.size} elements exceeds the checkpoint limit {MAX_RECORD_ARRAY}: "
                             "nodal fields and meshes are never stored")
        return v.tolist()
    if isinstance(v, Mapping):
        return {str(k): _jsonable(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        if len(v) > MAX_RECORD_ARRAY:
            raise ValueError(f"sequence of {len(v)} elements exceeds the checkpoint limit {MAX_RECORD_ARRAY}")
        return [_jsonable(x) for x in v]
    if isinstance(v, np.generic):
        return v.item()
    if v is None or isinstance(v, (str, bool, int, float)):
        return v
    raise TypeError(f"cannot store {type(v).__name__} in the checkpoint")


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


def _field(res, name):
    if isinstance(res, Mapping):
        return res.get(name, _MISSING)
    return getattr(res, name, _MISSING)


_MISSING = object()


def _thermal_record(res) -> dict:
    """Bounded jsonable thermal record of one solve: exactly ``THERMAL_REQUIRED`` (each must be present) plus ``gci``
    computed here by ``gci_capped`` (floor 1e-3 K) per die. A ``gci`` returned by the callable is kept as
    ``gci_reported`` and never used. ``res`` may be a mapping or an attribute object (namedtuple included); every other
    field of it (nodal temperatures, node arrays, evaluators) is dropped, never serialised."""
    missing = [k for k in THERMAL_REQUIRED if _field(res, k) is _MISSING]
    if missing:
        raise ValueError(f"thermal result lacks required field(s): {', '.join(missing)}")
    rec = {k: _jsonable(_field(res, k)) for k in THERMAL_REQUIRED}
    tj = [[float(x) for x in r] for r in rec["tj"]]
    if len(tj) != 3:
        raise ValueError("thermal result needs per-die Tj at three levels")
    reported = _field(res, "gci")
    if reported is not _MISSING:
        rec["gci_reported"] = _jsonable(reported)
    rec["tj"] = tj
    rec["gci"] = [gci_capped(tj[0][i], tj[1][i], tj[2][i], floor=GCI_FLOOR_K) for i in range(len(tj[0]))]
    return rec


def band_e_R(x: Sequence[float], c: Sequence[float]) -> float:
    """e_R of the ratio R = L(x) / L(c) from five band levels each (order in the module docstring): O006 pilot P3's
    estimator applied to the ratio, level by level (O003 A1):
    ``3 |R(0.25) - R(0.5)| + thickness term(R(5/3/3), R(10/6/6), R(20/12/12)) + 3 |R(12 per ring) - R(production)|``.
    3 |.| is Roache's two-level GCI 3 |f2 - f1| / (r - 1) at r = 2; the thickness term for a monotone sequence is
    1.25 |e21| rp / (rp - 1), rp = e32 / e21, and 3 max(|e21|, |e32|) when the sequence oscillates or diverges
    (Roache, Verification and Validation in Computational Science and Engineering, 1998, ch. 5)."""
    xs, cs = [float(v) for v in x], [float(v) for v in c]
    if len(xs) != 5 or len(cs) != 5:
        raise ValueError("band_e_R needs five levels per layout")
    if not all(math.isfinite(v) and v > 0.0 for v in xs + cs):
        raise ValueError("band_e_R needs finite positive inductances")
    r025, r05, r_c, r_f, r_w = (a / b for a, b in zip(xs, cs, strict=True))
    e21, e32 = r05 - r_f, r_c - r05  # middle (production) value against fine and coarse thickness
    if e21 * e32 > 0.0 and abs(e21) < abs(e32):
        rp = e32 / e21
        thick = 1.25 * abs(e21) * rp / (rp - 1.0)
    else:
        thick = 3.0 * max(abs(e21), abs(e32))
    return 3.0 * abs(r025 - r05) + thick + 3.0 * abs(r_w - r05)


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
    def __init__(self, solvers: Solvers, store: Store, P: float | None, ns: str = "main"):
        self.s, self.store, self.P, self.ns = solvers, store, P, ns
        self.rows: dict[str, list[dict]] = {"candidates": [], "tj": [], "band": [], "lsub": [], "e_R": [],
                                            "checks": [], "thermal": []}
        self.fp_of: dict[int, str] = {}

    def fp(self, lay) -> str:
        k = id(lay)
        if k not in self.fp_of:
            self.fp_of[k] = lay.fingerprint()
        return self.fp_of[k]

    def key(self, lay, kind: str) -> str:
        return f"{self.ns}:{self.fp(lay)}:{kind}"

    def l1(self, lay) -> float:
        return float(self.store.get(self.key(lay, "l1"), lambda: self.s.l1(lay)))

    def l_sub(self, lay) -> float:
        return float(self.store.get(self.key(lay, "lsub"), lambda: self.s.l_sub(lay)))

    def band(self, lay, role: str) -> list[float]:
        b = self.store.get(self.key(lay, "band"), lambda: list(self.s.band(lay)))
        self.rows["band"].append({"fingerprint": self.fp(lay), "role": role, "band": b})
        return b

    def thermal(self, lay, role: str) -> dict:
        key = self.key(lay, "thermal")
        fresh = not self.store.has(key)

        def solve():
            return _thermal_record(self.s.thermal(lay, self.P))
        res = self.store.get(key, solve)
        if not any(r["fingerprint"] == self.fp(lay) for r in self.rows["thermal"]):
            self.rows["thermal"].append({"fingerprint": self.fp(lay), "role": role, "record": res})
        if not any(r["fingerprint"] == self.fp(lay) and r["die"] == 0 for r in self.rows["tj"]):
            for i, g in enumerate(res["gci"]):
                self.rows["tj"].append({"fingerprint": self.fp(lay), "role": role, "die": i,
                                        "tj0": res["tj"][0][i], "tj1": res["tj"][1][i], "tj2": res["tj"][2][i],
                                        "gci": g})
        res = dict(res)
        res["fresh"] = fresh
        return res

    def e_R_from_bands(self, cand, other, role: str) -> float:
        """e_R of (cand, other) from the band solves already stored for both (no new solve)."""
        v = band_e_R(self.store.data[self.key(cand, "band")], self.store.data[self.key(other, "band")])
        self.rows["e_R"].append({"candidate": self.fp(cand), "other": self.fp(other), "role": role, "e_R": v,
                                 "source": "band", "estimator": E_R_ESTIMATOR})
        return v


def _screen(run: _Run, spec, seed: int, cfg: SearchConfig, generate):
    """Steps 1-2. Returns (levelling dict, shortlist [(index, layout, l1)] by ascending L1, L_sub by index)."""
    keep: list[tuple[float, int, Any]] = []  # (l1, index, layout), at most cfg.shortlist unique fingerprints, sorted
    best_first = math.inf
    best_all = math.inf
    pool: list[float] = []
    for idx, lay in enumerate(candidate_stream(spec, cfg.n_candidates, seed, generate, cfg.chunk)):
        f = run.fp(lay)
        v = run.l1(lay)
        pool.append(v)
        best_all = min(best_all, v)
        if idx < cfg.n_first:
            best_first = min(best_first, v)
        if all(run.fp(t[2]) != f for t in keep):  # a repeated fingerprint never takes a second slot
            keep.append((v, idx, lay))
            keep.sort(key=lambda t: (t[0], t[1]))
            del keep[cfg.shortlist:]
        run.fp_of = {id(t[2]): run.fp_of[id(t[2])] for t in keep}  # drop fingerprints of discarded layouts
    n = len(pool)
    lev = {"n_candidates": n, "l1_min_first": best_first, "l1_min_all": best_all, "n_first": min(cfg.n_first, n),
           "l1_pool_median": float(np.median(pool)) if pool else math.nan}
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
    l1_twin = run.l1(twin)
    lev["l1_twin"] = l1_twin
    lev["l1_pool_median_headroom"] = 1.0 - lev["l1_pool_median"] / l1_twin

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

    # null (F1): the first max_checks positions in ascending L1, batches, cached results reused; the first passing
    # candidate in L1 order. No position is skipped, none beyond max_checks is looked at.
    null_best, new = None, 0
    reach = short[:cfg.max_checks]
    for b0 in range(0, len(reach), cfg.batch):
        for t in reach[b0:b0 + cfg.batch]:
            if t[0] in checked:
                ok = checked[t[0]] <= cfg.tj_margin
            else:
                ok, _ = check(t, "null")
                new += 1
                order.append(run.fp(t[1]))
            if ok and null_best is None:
                null_best = t
        if null_best is not None:
            break

    # bands
    run.band(reference, "reference")
    run.band(twin, "twin")
    if a1_best is not None:
        run.band(a1_best[1], "a1_best")
    run.band(ind_best[1], "inductance_best")
    e_ind = run.e_R_from_bands(ind_best[1], twin, "inductance_best")
    w_ind = 2.0 * e_ind + s_ref
    ties = []
    tie_layouts = []
    for t in asc:
        if run.fp(t[1]) != run.fp(ind_best[1]) and lsub[t[0]] <= (1.0 + w_ind) * lsub[ind_best[0]]:
            run.band(t[1], "near_tie")
            ties.append(run.fp(t[1]))
            tie_layouts.append(t[1])
    w_a1 = None
    if a1_best is not None:
        w_a1 = 2.0 * run.e_R_from_bands(a1_best[1], twin, "a1_best") + s_ref
    for lay in tie_layouts:
        run.e_R_from_bands(lay, twin, "near_tie")
    lev["w_ind"] = w_ind
    lev["levelled"] = _levelled(lev, w_ind)
    return SearchResult(rows=run.rows, levelling=lev, inductance_best=run.fp(ind_best[1]),
                        a1_best=run.fp(a1_best[1]) if a1_best else None,
                        null_best=run.fp(null_best[1]) if null_best else None, near_ties=ties, w_ind=w_ind,
                        w_a1=w_a1, thermal_checked=order, null_new_checks=new)


def run_control(spec, d, seed: int, solvers: Solvers, s_ref: float, workdir: str | Path | None,
                cfg: SearchConfig = SearchConfig(), generate: Callable | None = None) -> SearchResult:
    """Control mode (F1(b)): reference = D, a new sealed ``seed``, same budget, inductance only; no thermal solves.
    ``w_ctrl = 2 e_R(control best, D)`` with no ``s_ref`` term (D is a generator-space degradation of the twin and has
    no snapping bias); ``s_ref`` is accepted for signature compatibility and unused. K1's levelling flag is not
    computed here. Checkpoint keys are in the ``control`` namespace."""
    store = Store(Path(workdir) / "checkpoint.jsonl" if workdir is not None else None)
    run = _Run(solvers, store, None, ns="control")
    lev, short = _screen(run, spec, seed, cfg, generate)
    lsub = {i: run.l_sub(lay) for i, lay, _ in short}
    run.rows["lsub"].append({"fingerprint": run.fp(d), "role": "degraded", "l_sub": run.l_sub(d)})
    best = min(short, key=lambda t: (lsub[t[0]], t[0]))
    run.band(d, "degraded")
    run.band(best[1], "control_best")
    e = run.e_R_from_bands(best[1], d, "control_best")
    w_ctrl = 2.0 * e
    lev["w_ctrl"] = w_ctrl
    return SearchResult(rows=run.rows, levelling=lev, inductance_best=run.fp(best[1]), a1_best=None, null_best=None,
                        w_ctrl=w_ctrl)
