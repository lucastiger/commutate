"""Inductance-blind nulls (a), (b), (d) and the random-screen ablation (c) (optimize/nulls.py, T0380) on the 70x40
half-bridge housing, with geometric scores only and injected counting solvers for (c)."""
import inspect

import numpy as np
import pytest

from moduleforge.drc.rules import check
from moduleforge.generate import derivative as D
from moduleforge.generate import twin as T
from moduleforge.optimize import local as L
from moduleforge.optimize import nulls as N
from moduleforge.optimize.local import LocalConfig, LocalSolvers


@pytest.fixture(scope="module")
def spec():
    return D.halfbridge_housing_spec(3, wires_per_die=1)


@pytest.fixture(scope="module")
def d(spec):
    return D.generate(spec, 1, 5, reach=True)[0]


@pytest.fixture(scope="module")
def widen(spec, d):
    return N.null_widen(spec, d, step_limit=60)


@pytest.fixture(scope="module")
def compact(spec, d):
    return N.null_compact(spec, d, step_limit=60)


def _raise(*_a, **_k):
    raise AssertionError("an inductance solver was called")


def _fp(lay):
    return D.params_of(lay).to_vector()


def test_blind_nulls_never_call_an_inductance_solver(spec, d, monkeypatch):
    bad = LocalSolvers(l1=_raise, l_sub=_raise)
    monkeypatch.setattr(T, "_l1", _raise)
    for fn in (N.null_seed, N.null_widen, N.null_compact):
        kw = {"step_limit": 3} if fn is not N.null_seed else {}
        fn(spec, d, solvers=bad, **kw)
        assert "solvers" in inspect.signature(fn).parameters


def test_seed_is_unchanged(spec, d):
    r = N.null_seed(spec, d)
    assert r.layout is d and r.steps == 0 and r.changed_params == 0 and r.manhattan_mm == 0.0


@pytest.mark.parametrize("which", ["widen", "compact"])
def test_outputs_drc_clean_in_domain_and_record_distance(spec, d, widen, compact, which):
    r = {"widen": widen, "compact": compact}[which]
    assert not check(r.layout, spec.rules)
    assert D.in_domain(spec, r.params, reach=True)[0]
    diff = np.abs(_fp(r.layout) - _fp(d))
    assert r.steps > 0 and r.changed_params == int(np.sum(diff > 1e-9)) > 0
    assert r.manhattan_mm == pytest.approx(float(diff.sum())) and r.manhattan_mm > 0
    assert r.terminal in (L.LOCAL_OPTIMUM, L.STEP_LIMIT)


def test_widen_increases_power_copper_monotonically(d, widen):
    a = widen.score_trajectory
    assert len(a) == widen.steps + 1
    assert all(y > x for x, y in zip(a, a[1:], strict=False))
    assert a[0] == pytest.approx(N.power_copper_mm2(d)) and a[-1] == pytest.approx(N.power_copper_mm2(widen.layout))


@pytest.mark.slow
def test_widen_ends_where_no_single_widening_move_is_feasible(spec, d):
    r = N.null_widen(spec, d, step_limit=400)
    assert r.terminal == L.LOCAL_OPTIMUM and r.steps < 400
    a_end = N.power_copper_mm2(r.layout)
    sp = L._Space(spec)
    n_valid = 0
    for kind, _, v in sp.neighbours(r.params.to_vector(), L.movable_indices(), 0.5, r.params):
        cl = sp.valid(v, kind)
        if cl is not None:
            n_valid += 1
            assert N.power_copper_mm2(cl) <= a_end + 1e-9  # no feasible move adds copper
    assert n_valid > 0  # the end is a DRC limit, not an empty neighbourhood


def test_compact_score_monotone_non_decreasing_and_constraints_hold(d, compact):
    s = compact.score_trajectory
    assert len(s) == compact.steps + 1
    assert all(y >= x - 1e-9 for x, y in zip(s, s[1:], strict=False))
    assert s[-1] > s[0]
    assert s[0] == pytest.approx(N.compact_score(d))
    # copper not reduced, wires not lengthened, relative to D_j
    assert N.power_copper_mm2(compact.layout) >= N.power_copper_mm2(d) - 1e-9
    assert N.power_wire_mm(compact.layout) <= N.power_wire_mm(d) + 1e-9


@pytest.mark.slow
def test_compact_local_optimum_has_no_feasible_improving_move(spec, d):
    r = N.null_compact(spec, d, step_limit=400)
    assert r.terminal == L.LOCAL_OPTIMUM
    a0, w0, s0 = N.power_copper_mm2(r.layout), N.power_wire_mm(r.layout), N.compact_score(r.layout)
    sp = L._Space(spec)
    for kind, _, v in sp.neighbours(r.params.to_vector(), L.movable_indices(), 0.5, r.params):
        cl = sp.valid(v, kind)
        if cl is not None and N.power_copper_mm2(cl) >= a0 - 1e-9 and N.power_wire_mm(cl) <= w0 + 1e-9:
            assert N.compact_score(cl) <= s0 + 1e-9


@pytest.mark.slow
def test_determinism(spec, d, widen, compact):
    w2, c2 = N.null_widen(spec, d, step_limit=60), N.null_compact(spec, d, step_limit=60)
    assert w2.layout.fingerprint() == widen.layout.fingerprint() and w2.score_trajectory == widen.score_trajectory
    assert c2.layout.fingerprint() == compact.layout.fingerprint() and c2.score_trajectory == compact.score_trajectory


def test_repeat_runs_are_identical_fast(spec, d):
    """Fast variant of ``test_determinism`` (capped at 3 steps)."""
    for fn in (N.null_widen, N.null_compact):
        a, b = fn(spec, d, step_limit=3), fn(spec, d, step_limit=3)
        assert a.layout.fingerprint() == b.layout.fingerprint() and a.score_trajectory == b.score_trajectory


def test_capped_run_reports_step_limit(spec, d):
    for fn in (N.null_widen, N.null_compact):
        r = fn(spec, d, step_limit=2)
        assert r.terminal == L.STEP_LIMIT and r.steps == 2


# A real layout outside the reach domain: it builds and is DRC-clean, but none of its single-parameter neighbours is in the
# domain (found by perturbing four parameters of ``d`` at random; checked below).
OUT_OF_DOMAIN_VEC = [0.0, 1.0, 1.0, 1.0, 64.0, 4.5, 69.0, 17.0, 58.5, 23.0, 68.5, 35.5, 2.0, 12.5, 6.5, 26.0, 14.0, 4.5, 64.0,
                     12.0, 6.0, 13.5, 37.0, 16.5, 6.5, 14.5, 32.0, 26.0, 8.5, 31.5, 66.0, 35.5, 16.0, 6.0, 1.5, 12.0, 19.5, 1.0,
                     17.5, 34.75, 0.375, -0.125, 0.0, -0.5, 0.0, 0.125, 0.25, 0.0, 0.0, -1.25, 0.0, 0.125, 0.0, 0.0, 0.0, 0.0,
                     0.0, 0.0, 0.0, 0.0]


def test_stats_record_seed_in_domain_and_first_neighbourhood(spec, d):
    sp = L._Space(spec)
    p = D.params_of(d)
    n = sum(sp.valid(v, k) is not None for k, _, v in sp.neighbours(p.to_vector(), L.movable_indices(), 0.5, p))
    assert n > 0
    for fn in (N.null_widen, N.null_compact):
        r = fn(spec, d, step_limit=1)
        assert r.stats["seed_in_domain"] is True and r.stats["n_neighbours_step0"] == n
        assert r.terminal == L.STEP_LIMIT or r.steps == 0
    # dies fixed: the die-row moves drop out of the neighbourhood
    rf = N.null_widen(spec, d, step_limit=1, dies_fixed=True)
    assert 0 < rf.stats["n_neighbours_step0"] < n


@pytest.mark.parametrize("fn", [N.null_widen, N.null_compact])
def test_out_of_domain_dj_with_no_neighbours_is_no_moves_not_local_optimum(spec, fn):
    p = D.Params.from_vector(np.array(OUT_OF_DOMAIN_VEC))
    dj = D.build(spec, p)
    assert not check(dj, spec.rules) and not D.in_domain(spec, p, reach=True)[0]
    r = fn(spec, dj, step_limit=5)
    assert r.terminal == N.NO_MOVES and r.terminal != L.LOCAL_OPTIMUM
    assert r.steps == 0 and r.layout.fingerprint() == dj.fingerprint() and r.changed_params == 0
    assert r.stats == {"seed_in_domain": False, "n_neighbours_step0": 0}


def test_dies_fixed_is_passed_to_descend(spec, d):
    row0 = [i for i, n in enumerate(D.Params.NAMES) if n.startswith("row_")]
    for fn in (N.null_widen, N.null_compact):
        free, fixed = fn(spec, d, step_limit=12), fn(spec, d, step_limit=12, dies_fixed=True)
        assert _fp(fixed.layout)[row0].tobytes() == _fp(d)[row0].tobytes()
        assert fn.__defaults__ is not None and inspect.signature(fn).parameters["dies_fixed"].default is False
        assert free.layout.fingerprint() != fixed.layout.fingerprint() or _fp(free.layout)[row0].tobytes() == _fp(d)[row0].tobytes()


@pytest.mark.slow
def test_a_limit_equal_to_the_optimum_step_count_is_local_optimum_not_step_limit(spec, d):
    """Review T0426: a run whose local optimum is reached on exactly step ``step_limit`` is not 'step_limit'."""
    full = N.null_widen(spec, d, step_limit=400)
    assert full.terminal == L.LOCAL_OPTIMUM and 0 < full.steps < 400
    at = N.null_widen(spec, d, step_limit=full.steps)
    assert at.terminal == L.LOCAL_OPTIMUM and at.steps == full.steps
    assert at.layout.fingerprint() == full.layout.fingerprint() and at.score_trajectory == full.score_trajectory
    below = N.null_widen(spec, d, step_limit=full.steps - 1)
    assert below.terminal == L.STEP_LIMIT and below.steps == full.steps - 1


@pytest.mark.parametrize("fn", [N.null_widen, N.null_compact])
def test_limit_equal_to_the_optimum_step_count_fast_variant(spec, d, monkeypatch, fn):
    """Fast variant of the two exact-limit tests: copper and wire measures saturate (copper capped 25 mm^2 above D_j's, wire
    floored 3 mm below it), so the local optimum is a few steps away."""
    a_cap, w_floor = N.power_copper_mm2(d) + 25.0, N.power_wire_mm(d) - 3.0
    real_a, real_w = N.power_copper_mm2, N.power_wire_mm
    monkeypatch.setattr(N, "power_copper_mm2", lambda lay: min(real_a(lay), a_cap))
    monkeypatch.setattr(N, "power_wire_mm", lambda lay: max(real_w(lay), w_floor))
    full = fn(spec, d, step_limit=400)
    assert full.terminal == L.LOCAL_OPTIMUM and 0 < full.steps < 12
    at = fn(spec, d, step_limit=full.steps)
    assert at.terminal == L.LOCAL_OPTIMUM and at.steps == full.steps
    assert at.layout.fingerprint() == full.layout.fingerprint() and at.score_trajectory == full.score_trajectory
    below = fn(spec, d, step_limit=full.steps - 1)
    assert below.terminal == L.STEP_LIMIT and below.steps == full.steps - 1


@pytest.mark.slow
def test_compact_limit_equal_to_the_optimum_step_count_is_local_optimum(spec, d):
    full = N.null_compact(spec, d, step_limit=400)
    assert full.terminal == L.LOCAL_OPTIMUM and 0 < full.steps < 400
    at = N.null_compact(spec, d, step_limit=full.steps)
    assert at.terminal == L.LOCAL_OPTIMUM and at.steps == full.steps
    assert at.layout.fingerprint() == full.layout.fingerprint() and at.score_trajectory == full.score_trajectory
    below = N.null_compact(spec, d, step_limit=full.steps - 1)
    assert below.terminal == L.STEP_LIMIT and below.steps == full.steps - 1


def test_compact_rejects_a_move_that_gains_score_but_loses_copper(spec, d, monkeypatch):
    """Synthetic candidate: the power-copper and wire measures are made to pay 200 mm of wire (and cost 3 mm^2 of copper)
    per mm that ``land_LS`` moves from its start, so the steepest A-W move reduces copper; ``null_compact`` must not take
    it, while an unconstrained A-W descent does."""
    i = D.Params.NAMES.index("land_LS")
    u0 = _fp(d)[i]
    real_a, real_w = N.power_copper_mm2, N.power_wire_mm

    def moved(lay):
        return abs(float(_fp(lay)[i]) - u0)

    monkeypatch.setattr(N, "power_copper_mm2", lambda lay: real_a(lay) - 3.0 * moved(lay))
    monkeypatch.setattr(N, "power_wire_mm", lambda lay: real_w(lay) - 200.0 * moved(lay))
    a0, w0 = N.power_copper_mm2(d), N.power_wire_mm(d)
    free = L.descend(spec, D.params_of(d), lambda lay: -N.compact_score(lay), step_limit=1)
    assert free.steps == 1 and free.trajectory[1]["move"] == "land_LS"
    assert N.power_copper_mm2(free.layout) < a0 - 1.0  # the unconstrained steepest move loses copper (and shortens wire)
    assert N.power_wire_mm(free.layout) < w0 - 50.0
    r = N.null_compact(spec, d, step_limit=1)
    assert r.layout.fingerprint() != free.layout.fingerprint()
    assert moved(r.layout) == 0.0  # land_LS never moved
    assert N.power_copper_mm2(r.layout) >= a0 - 1e-9 and N.power_wire_mm(r.layout) <= w0 + 1e-9
    assert r.steps == 1 and r.score_trajectory[1] > r.score_trajectory[0]  # but it still found a constrained gain


class Counting:
    def __init__(self):
        self.l1_calls, self.lsub_calls = [], []

    def l1(self, lay):
        self.l1_calls.append(lay.fingerprint())
        return 1.0 + float(np.abs(_fp(lay)).sum()) * 1e-3

    def l_sub(self, lay):
        self.lsub_calls.append(lay.fingerprint())
        return 1.1 * (1.0 + float(np.abs(_fp(lay)).sum()) * 1e-3) + 1e-4 * (int(lay.fingerprint()[:4], 16) / 65535)


def test_random_screen_budget_shortlist_and_selection(spec, d):
    c = Counting()
    cfg = LocalConfig(budget=40, shortlist=5)
    r = N.ablation_random_screen(spec, d, 7, LocalSolvers(c.l1, c.l_sub), cfg, chunk=20)
    assert len(c.l1_calls) <= 40 and len(set(c.l1_calls)) == len(c.l1_calls) == r.stats["l1_evals"]
    assert len(c.lsub_calls) == 5 == len(set(c.lsub_calls)) == r.stats["l_sub_evals"]
    # shortlist = the 5 lowest L1 of the stream, best = lowest l_sub
    stream = {x.fingerprint(): c.l1(x) for x in N.candidate_stream(spec, 40, 7, lambda s, m, k: D.generate(s, m, k, reach=True), 20)}
    assert set(c.lsub_calls) == set(sorted(stream, key=stream.get)[:5])
    assert r.layout.fingerprint() == min(r.stats["shortlist"], key=lambda t: t["l_sub"])["fingerprint"]
    assert not check(r.layout, spec.rules) and D.in_domain(spec, r.params, reach=True)[0]
    assert r.steps == 0 and r.manhattan_mm == pytest.approx(float(np.abs(_fp(r.layout) - _fp(d)).sum()))
    c2 = Counting()
    r2 = N.ablation_random_screen(spec, d, 7, LocalSolvers(c2.l1, c2.l_sub), cfg, chunk=20)
    assert r2.layout.fingerprint() == r.layout.fingerprint()
