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


def test_compact_local_optimum_has_no_feasible_improving_move(spec, d):
    r = N.null_compact(spec, d, step_limit=400)
    assert r.terminal == L.LOCAL_OPTIMUM
    a0, w0, s0 = N.power_copper_mm2(r.layout), N.power_wire_mm(r.layout), N.compact_score(r.layout)
    sp = L._Space(spec)
    for kind, _, v in sp.neighbours(r.params.to_vector(), L.movable_indices(), 0.5, r.params):
        cl = sp.valid(v, kind)
        if cl is not None and N.power_copper_mm2(cl) >= a0 - 1e-9 and N.power_wire_mm(cl) <= w0 + 1e-9:
            assert N.compact_score(cl) <= s0 + 1e-9


def test_determinism(spec, d, widen, compact):
    w2, c2 = N.null_widen(spec, d, step_limit=60), N.null_compact(spec, d, step_limit=60)
    assert w2.layout.fingerprint() == widen.layout.fingerprint() and w2.score_trajectory == widen.score_trajectory
    assert c2.layout.fingerprint() == compact.layout.fingerprint() and c2.score_trajectory == compact.score_trajectory


def test_capped_run_reports_step_limit(spec, d):
    for fn in (N.null_widen, N.null_compact):
        r = fn(spec, d, step_limit=2)
        assert r.terminal == L.STEP_LIMIT and r.steps == 2


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
