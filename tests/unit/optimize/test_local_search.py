"""Seeded local search (optimize/local.py, T0378) with injected cheap solvers on real derivative layouts.

Housing: the 70x40 half-bridge housing (``halfbridge_housing_spec``).  The synthetic score is the Manhattan distance of a
layout's parameter vector to a DRC-feasible target layout (a ``generate(reach=True)`` draw), so its global optimum, 0, is a
known feasible layout.  The 2R test uses 2D_Case_2R's spec (the only spec whose twin lies outside the sampler's support) built
the way E010's prepare does (as tests/unit/generate/test_reach.py does).
"""
import dataclasses
import importlib.util
import inspect
import json
import sys
from pathlib import Path

import numpy as np
import pytest
import yaml

from moduleforge.drc.rules import check
from moduleforge.generate import derivative as D
from moduleforge.generate import twin as W
from moduleforge.optimize import local as L
from moduleforge.optimize.local import LocalConfig, LocalSolvers, descend, local_search

ROOT = Path(__file__).resolve().parents[3]
NAMES = D.Params.NAMES


def pvec(lay):
    return D.params_of(lay).to_vector()


@pytest.fixture(scope="module")
def spec():
    return D.halfbridge_housing_spec(3, wires_per_die=1)


@pytest.fixture(scope="module")
def world(spec):
    """(target vector, seed layout): the seed is the target after six random valid joint moves of the search's own space."""
    tgt = D.generate(spec, 1, 11, reach=True)[0]
    tv = pvec(tgt)
    idx = L.movable_indices()
    sp = L._Space(spec)
    for rseed in range(3, 60):  # the first rng seed whose six moves give a seed 8 mm (Manhattan) from the target
        rng = np.random.default_rng(rseed)
        v, n = tv.copy(), 0
        for _ in range(300):
            w = L._joint(rng, v, idx, 2, 3, 2, 0.5)
            if sp.valid(w) is not None:
                v, n = w, n + 1
            if n >= 6:
                break
        if n == 6 and abs(np.abs(v - tv).sum() - 8.0) < 1e-9:
            return tv, sp.valid(v)
    raise AssertionError("no rng seed gives a seed layout 8 mm from the target")


def dist(tv):
    return lambda lay: float(np.abs(pvec(lay) - tv).sum())


class Solvers:
    """Counting injected solvers: l1 = 1 + distance (positive), l_sub = 1.1 l1 + a tiny layout-dependent term."""

    def __init__(self, tv, fail_after=None):
        self.tv, self.fail_after = tv, fail_after
        self.l1_calls, self.lsub_calls = [], []

    def l1(self, lay):
        if self.fail_after is not None and len(self.l1_calls) >= self.fail_after:
            raise RuntimeError("interrupted")
        self.l1_calls.append(lay.fingerprint())
        return 1.0 + dist(self.tv)(lay)

    def l_sub(self, lay):
        self.lsub_calls.append(lay.fingerprint())
        return 1.1 * (1.0 + dist(self.tv)(lay)) + 1e-3 * (int(lay.fingerprint()[:4], 16) / 65535)

    def bundle(self):
        return LocalSolvers(l1=self.l1, l_sub=self.l_sub)


CFG = LocalConfig(budget=2500, shortlist=4)


def test_reaches_known_feasible_optimum(spec, world):
    tv, seed_lay = world
    s = Solvers(tv)
    r = local_search(spec, seed_lay, 1, s.bundle(), CFG)
    assert dist(tv)(seed_lay) == pytest.approx(8.0)
    assert r.shortlist[0]["score"] == 1.0  # L1 = 1 + distance: distance 0
    assert np.allclose(r.best_params.to_vector(), tv)
    assert r.stats["manhattan_mm"] == pytest.approx(8.0)  # seed is 8 mm from the target in Manhattan distance
    assert r.stats["changed_params"] == int(np.sum(np.abs(pvec(seed_lay) - tv) > 1e-9))
    assert not check(r.best, spec.rules)


def test_determinism_and_different_seeds(spec, world):
    tv, seed_lay = world
    cfg = LocalConfig(budget=700, shortlist=4)
    a = local_search(spec, seed_lay, 5, Solvers(tv).bundle(), cfg)
    b = local_search(spec, seed_lay, 5, Solvers(tv).bundle(), cfg)
    c = local_search(spec, seed_lay, 6, Solvers(tv).bundle(), cfg)
    assert a.visited == b.visited and a.trajectory == b.trajectory and a.shortlist == b.shortlist
    assert a.best_fingerprint == b.best_fingerprint
    assert a.visited != c.visited  # joint samples differ, so the visited sets differ


def test_every_visited_layout_is_drc_clean_and_in_domain(spec, world):
    tv, seed_lay = world
    r = local_search(spec, seed_lay, 2, Solvers(tv).bundle(), LocalConfig(budget=600, shortlist=4))
    assert len(r.visited) == 600
    cx = D._Ctx(spec, reach=True)
    for fp, vec in r.visited:
        p = D.Params.from_vector(np.asarray(vec))
        ok, why = D.in_domain(spec, p, reach=True, ctx=cx)
        assert ok, why
        lay = D.build(spec, p)
        assert lay.fingerprint() == fp
        assert not check(lay, spec.rules)
    assert all(0 < y["rate"] <= 1 for y in r.stats["yield"].values())  # the move yield is recorded
    assert r.stats["yield"]["single"]["proposed"] > 0 and r.stats["yield"]["joint"]["proposed"] > 0


def test_budget_exact_and_l_sub_called_k_times_on_distinct_fingerprints(spec, world):
    tv, seed_lay = world
    for budget, k in ((137, 5), (300, 8)):
        s = Solvers(tv)
        r = local_search(spec, seed_lay, 4, s.bundle(), LocalConfig(budget=budget, shortlist=k))
        assert len(s.l1_calls) == budget == r.stats["l1_evals"] == len(set(s.l1_calls))
        assert r.stats["stopped_at_budget"] and r.stats["stop_reason"] == "budget"
        assert len(s.lsub_calls) == k == len(set(s.lsub_calls))
        assert set(s.lsub_calls) == {x["fingerprint"] for x in r.shortlist}
        # the shortlist is the K lowest-score visited layouts, and the best is the lowest L_sub
        scores = sorted(float(1.0 + np.abs(np.asarray(v) - tv).sum()) for _, v in r.visited)
        assert [x["score"] for x in r.shortlist] == scores[:k]
        assert r.best_fingerprint == min(r.shortlist, key=lambda x: x["l_sub"])["fingerprint"]


def test_record_fields(spec, world):
    tv, seed_lay = world
    r = local_search(spec, seed_lay, 4, Solvers(tv).bundle(), LocalConfig(budget=300, shortlist=8))
    st = r.stats
    assert st["l1_evals"] == 300 and st["moves"] == st["steps"] + st["perturbations"] == len(r.trajectory)
    assert st["last_improve_eval"] <= 300 and st["improving_last10"] == (st["last_improve_eval"] > 270)
    assert -1.0 <= st["spearman_l1_lsub"] <= 1.0
    assert st["l2_l1_min"] <= st["l2_l1_max"] and st["l1_s_per_eval"] > 0 and st["l1_fresh"] == 300
    assert st["cfg_hash"] == LocalConfig(budget=300, shortlist=8).hash()
    assert st["seed_in_domain"] is True


def test_signature_exposes_no_W_or_Wstar_input():
    ps = inspect.signature(local_search).parameters
    assert list(ps) == ["spec", "seed_layout", "seed", "solvers", "cfg", "workdir", "score"]
    assert not [n for n in ps if "twin" in n.lower() or "star" in n.lower() or n.lower() in ("w", "w_star", "wstar", "ref")]
    cfgf = {f.name for f in dataclasses.fields(LocalConfig)}
    assert not [n for n in cfgf | {f.name for f in dataclasses.fields(LocalSolvers)} if "twin" in n or "star" in n]


def test_config_is_frozen_with_a_stable_hash():
    import hashlib
    c = LocalConfig(budget=10, shortlist=3)
    with pytest.raises(dataclasses.FrozenInstanceError):
        c.budget = 11  # type: ignore[misc]
    want = hashlib.sha256(json.dumps(dataclasses.asdict(c), sort_keys=True).encode()).hexdigest()[:16]
    assert c.hash() == want == LocalConfig(budget=10, shortlist=3).hash()
    assert LocalConfig(budget=11, shortlist=3).hash() != c.hash()


def test_score_hook_receives_layout_and_solver_output(spec, world):
    tv, seed_lay = world
    seen = []

    def score(lay, out):
        seen.append((lay.fingerprint(), out["l1"]))
        return out["l1"] + 0.5 * (1 if lay.fingerprint() == seed_lay.fingerprint() else 0)

    s = Solvers(tv)
    r = local_search(spec, seed_lay, 1, s.bundle(), LocalConfig(budget=80, shortlist=3), score=score)
    assert len(seen) == 80 and seen[0] == (seed_lay.fingerprint(), 1.0 + 8.0)
    assert r.visited[0][0] == seed_lay.fingerprint()


def test_resume_from_checkpoint_gives_identical_result(spec, world, tmp_path):
    tv, seed_lay = world
    cfg = LocalConfig(budget=500, shortlist=4)
    ref = local_search(spec, seed_lay, 3, Solvers(tv).bundle(), cfg)
    wd = tmp_path / "run"
    s1 = Solvers(tv, fail_after=230)
    with pytest.raises(RuntimeError):
        local_search(spec, seed_lay, 3, s1.bundle(), cfg, wd)
    assert len(s1.l1_calls) == 230
    s2 = Solvers(tv)
    res = local_search(spec, seed_lay, 3, s2.bundle(), cfg, wd)
    assert len(s2.l1_calls) == 500 - 230 and len(s2.lsub_calls) == 4  # the 230 stored L1 solves are not repeated
    assert set(s2.l1_calls).isdisjoint(s1.l1_calls)
    for f in ("visited", "trajectory", "shortlist", "best_fingerprint"):
        assert getattr(res, f) == getattr(ref, f)
    s3 = Solvers(tv)
    again = local_search(spec, seed_lay, 3, s3.bundle(), cfg, wd)  # a full rerun solves nothing
    assert s3.l1_calls == [] and s3.lsub_calls == []
    assert again.visited == ref.visited and again.best_fingerprint == ref.best_fingerprint
    lines = (wd / "local_checkpoint.jsonl").read_text().splitlines()
    assert len(lines) == len({json.loads(x)["k"] for x in lines}) == 500 + 4  # append-only, one record per solve


def test_dies_fixed_never_moves_the_die_rows(spec, world):
    tv, seed_lay = world
    cfg = LocalConfig(budget=300, shortlist=3, dies_fixed=True)
    r = local_search(spec, seed_lay, 1, Solvers(tv).bundle(), cfg)
    rows = [i for i, n in enumerate(NAMES) if n.startswith("row_")]
    v0 = pvec(seed_lay)
    assert all(np.allclose(np.asarray(v)[rows], v0[rows]) for _, v in r.visited)
    assert not [i for i in L.movable_indices(True) if i in rows] and set(rows) <= set(L.movable_indices(False))


# ---------------------------------------------------------------------------------------------------------- descend
def brute_neighbours(spec, p, idx, step=0.5):
    """Independent enumeration of the +-step neighbours that are in the reach domain (in_domain includes build and DRC)."""
    cx = D._Ctx(spec, reach=True)
    out = []
    v = p.to_vector()
    for i in idx:
        s = L._step_of(i, step)
        for d in (-s, s):
            w = v.copy()
            w[i] += d
            q = D.Params.from_vector(w)
            if any(c[0] >= c[2] - 1e-9 or c[1] >= c[3] - 1e-9 for c in q.cols + q.slots):
                continue
            if D.in_domain(spec, q, reach=True, ctx=cx)[0]:
                out.append((NAMES[i], d, q))
    return out


def test_descend_stops_at_a_true_local_optimum(spec, world):
    tv, seed_lay = world
    f = dist(tv)
    res = descend(spec, D.params_of(seed_lay), f, movable=None, step_limit=100)
    assert res.kind == L.LOCAL_OPTIMUM and res.steps == len(res.trajectory) - 1
    scores = [t["score"] for t in res.trajectory]
    assert all(b < a for a, b in zip(scores, scores[1:], strict=False)) and scores[0] == 8.0
    for _, _, q in brute_neighbours(spec, res.params, L.movable_indices()):
        assert f(D.build(spec, q)) >= res.score  # no single DRC-valid move improves
    assert not check(res.layout, spec.rules)


def test_descend_stops_at_a_non_trivial_local_optimum(spec):
    """One movable parameter, minimised: the descent ends where the DRC / domain stops the next move."""
    lay = D.generate(spec, 1, 21, reach=True)[0]
    p = D.params_of(lay)
    i = NAMES.index("slot0_v0")

    def f(layout):
        return float(pvec(layout)[i])

    res = descend(spec, p, f, movable=[i], step_limit=100)
    assert res.kind == L.LOCAL_OPTIMUM
    for _, _, q in brute_neighbours(spec, res.params, [i]):
        assert f(D.build(spec, q)) >= res.score
    assert res.score <= f(lay)


def test_descend_step_limit_and_tie_order(spec, world):
    tv, seed_lay = world
    res = descend(spec, D.params_of(seed_lay), dist(tv), step_limit=2)
    assert res.kind == L.STEP_LIMIT and res.steps == 2 and len(res.trajectory) == 3
    # a tie: two parameters whose +-step both lower the score by the same amount; the first in NAMES order is taken
    p = D.params_of(seed_lay)
    v = p.to_vector()
    cand = brute_neighbours(spec, p, L.movable_indices())
    a_name, a_d, _ = cand[0]
    b = next(c for c in cand if c[0] != a_name)
    ia, ib = NAMES.index(a_name), NAMES.index(b[0])
    assert ia < ib

    def f(layout):
        w = pvec(layout)
        return (w[ia] - v[ia]) * np.sign(a_d) * -1.0 + (w[ib] - v[ib]) * np.sign(b[1]) * -1.0

    r1 = descend(spec, p, f, movable=[ia, ib], step_limit=1, reach=False)  # single steps only: a reach jump of a
    # movable parameter would win by its larger gain
    # moves ia by a_d and ib by b[1] each lower f by |step| (equal gains); the first (ia) wins the tie
    assert r1.trajectory[1]["move"] == a_name and r1.trajectory[1]["score"] == pytest.approx(-abs(a_d))


def test_descend_dies_fixed_and_validation(spec, world):
    tv, seed_lay = world
    rows = [i for i, n in enumerate(NAMES) if n.startswith("row_")]
    res = descend(spec, D.params_of(seed_lay), dist(tv), movable=rows + [NAMES.index("slot0_v0")], dies_fixed=True,
                  step_limit=20)
    assert all(not t["move"] or not t["move"].startswith("row_") for t in res.trajectory)
    with pytest.raises(ValueError):
        descend(spec, D.params_of(seed_lay), dist(tv), movable=[0])  # the integer flags never move


def test_spearman_closed_form():
    assert L.spearman([1, 2, 3, 4], [1, 3, 2, 4]) == pytest.approx(0.8)  # 1 - 6 * 2 / (4 * 15)
    assert L.spearman([1, 2, 3, 4], [4, 3, 2, 1]) == pytest.approx(-1.0)
    assert L.spearman([1, 2, 2, 4], [1, 2, 2, 4]) == pytest.approx(1.0)  # ties: average ranks
    assert np.isnan(L.spearman([1, 1, 1], [1, 2, 3])) and np.isnan(L.spearman([1, 2], [1, 2]))


# -------------------------------------------------------------------------------------------------- 2R: the domain
def _e010():
    name = "e010_run_for_local_test"
    if name in sys.modules:
        return sys.modules[name]
    sp = importlib.util.spec_from_file_location(name, ROOT / "experiments" / "runners" / "e010_run.py")
    m = importlib.util.module_from_spec(sp)
    sys.modules[name] = m
    sp.loader.exec_module(m)
    return m


def test_moves_stay_inside_in_domain_on_the_2R_spec():
    """2D_Case_2R, the only spec whose free region is not split (T0377): every layout the search visits is in the reach
    domain, seeded at the twin (which the sampler's own support need not contain: stats['seed_in_domain'] says)."""
    cfg = yaml.safe_load((ROOT / "experiments" / "specs" / "E010.yaml").read_text())["config"]
    entry = next(x for x in cfg["references"] if x["reference_id"] == "2D_Case_2R")
    rc = _e010().judged_reference(entry, cfg)
    spec2 = rc.spec
    tw, _, _ = W.twin(rc.reference, spec2, with_l1=False)
    tv = pvec(tw)

    def l1(lay):  # cheap deterministic stand-in with a gradient: distance to a shifted copy of the twin
        return 1.0 + float(np.abs(pvec(lay) - tv - 0.5).sum()) * 1e-3

    r = local_search(spec2, tw, 7, LocalSolvers(l1=l1, l_sub=lambda lay: 1.1 * l1(lay)),
                     LocalConfig(budget=250, shortlist=4))
    assert r.stats["l1_evals"] == 250 and isinstance(r.stats["seed_in_domain"], bool)
    cx = D._Ctx(spec2, reach=True)
    for _fp, vec in r.visited[1:]:  # every visited layout but the seed is in the domain, by construction
        p = D.Params.from_vector(np.asarray(vec))
        ok, why = D.in_domain(spec2, p, reach=True, ctx=cx)
        assert ok, why
        assert not check(D.build(spec2, p), spec2.rules)
    assert r.stats["yield"]["single"]["proposed"] > 0


# ------------------------------------------------------------------- T0379: scope and review T0414 fixes
def test_movable_set_is_the_frozen_objectives_and_no_foot_offset_moves(spec, world):
    assert L.movable_indices() == tuple(range(W.WALK_FIRST, W.WALK_END))
    assert [NAMES[i] for i in L.movable_indices()] == list(NAMES[4:40])
    assert not [i for i in L.movable_indices() if NAMES[i].startswith("foot_")]
    tv, seed_lay = world
    r = local_search(spec, seed_lay, 1, Solvers(tv).bundle(), LocalConfig(budget=400, shortlist=3))
    foot = [i for i, n in enumerate(NAMES) if n.startswith(("foot_", "sig_"))]
    v0 = pvec(seed_lay)
    assert all(np.array_equal(np.asarray(v)[foot], v0[foot]) for _, v in r.visited)


def test_descend_with_a_restricted_movable_set_changes_only_that_parameter(spec):
    """Reach jumps used to move other coordinates (column and slot u) whatever ``movable`` said."""
    lay = D.generate(spec, 1, 21, reach=True)[0]
    p = D.params_of(lay)
    v0 = p.to_vector()
    for name in ("slot0_u0", "slot0_u2" if False else "slot0_u1", "col_PHASE_u0"):
        i = NAMES.index(name)
        res = descend(spec, p, lambda lay_, i=i: -float(pvec(lay_)[i]), movable=[i], step_limit=40)  # pushes u up
        for t in res.trajectory:
            assert np.flatnonzero(np.abs(np.asarray(t["vec"]) - v0) > 1e-12).tolist() in ([], [i])
        res2 = descend(spec, p, lambda lay_, i=i: float(pvec(lay_)[i]), movable=[i], step_limit=40)  # pushes u down
        for t in res2.trajectory:
            assert set(np.flatnonzero(np.abs(np.asarray(t["vec"]) - v0) > 1e-12).tolist()) <= {i}
    # with the whole set a jump is still offered: the neighbourhood of the full set holds jumps, the restricted one none
    sp = L._Space(spec)
    i0 = NAMES.index("slot0_u0")
    only = list(sp.neighbours(v0, [i0], 0.5, p))
    assert all(np.flatnonzero(np.abs(v - v0) > 1e-12).tolist() == [i0] for _, _, v in only)
    full = list(sp.neighbours(v0, L.movable_indices(), 0.5, p))
    assert any(len(np.flatnonzero(np.abs(v - v0) > 1e-12)) > 0 and np.flatnonzero(np.abs(v - v0) > 1e-12)[0] != i0
               for _, _, v in full)  # the full set offers moves of other parameters (so the filter does something)


def test_store_keys_carry_the_solver_tag(spec, world, tmp_path):
    tv, seed_lay = world
    cfg = LocalConfig(budget=60, shortlist=3)
    wd = tmp_path / "w"
    a = Solvers(tv)
    local_search(spec, seed_lay, 1, LocalSolvers(a.l1, a.l_sub, tag="lsub0.5mm"), cfg, wd)
    same = Solvers(tv)
    local_search(spec, seed_lay, 1, LocalSolvers(same.l1, same.l_sub, tag="lsub0.5mm"), cfg, wd)
    assert same.l1_calls == [] and same.lsub_calls == []
    other = Solvers(tv)
    local_search(spec, seed_lay, 1, LocalSolvers(other.l1, other.l_sub, tag="lsub0.25mm"), cfg, wd)
    assert len(other.lsub_calls) == 3 and len(other.l1_calls) == 60  # a changed tag re-solves


def test_local_config_validates_budget_and_shortlist():
    for kw in ({"budget": 0}, {"budget": -3}, {"shortlist": 0}):
        with pytest.raises(ValueError):
            LocalConfig(**kw)
    assert LocalConfig(budget=1, shortlist=1).budget == 1


def test_descend_max_evals_and_min_gain(spec, world):
    tv, seed_lay = world
    n = []

    def f(lay):
        n.append(lay.fingerprint())
        return dist(tv)(lay)

    res = descend(spec, D.params_of(seed_lay), f, max_evals=30)
    assert res.kind == L.BUDGET and len(set(n)) == 30 == len(n)
    full = descend(spec, D.params_of(seed_lay), dist(tv), step_limit=100)
    gated = descend(spec, D.params_of(seed_lay), dist(tv), step_limit=100, min_gain=1.4)
    assert gated.steps < full.steps  # steps of 0.5 mm gain 0.5 < 1.4: only the larger jumps qualify
