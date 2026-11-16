"""O008's control (optimize/control.py, T0379): the designer proxy rule, the randomised degradation family, ablation (e).

Development geometry only (2D_Case_2R and 2D_Case_4 under D0023, built as E010's prepare does) and the 70x40 half-bridge
housing.  No L2 anywhere: the solvers are L1 (``twin._l1``) or synthetic.
"""
import importlib.util
import inspect
import json
import pickle
import sys
from pathlib import Path

import numpy as np
import pytest
import yaml

from moduleforge.drc.rules import check
from moduleforge.generate import derivative as D
from moduleforge.generate import twin as W
from moduleforge.optimize import control as C
from moduleforge.optimize import local as L

ROOT = Path(__file__).resolve().parents[3]
NAMES = D.Params.NAMES
ROWS = [i for i, n in enumerate(NAMES) if n.startswith("row_")]
CTX_2R = ROOT / "experiments/results/E010/E010-20261114T202413-80c1/work/2D_Case_2R/ctx.pkl"
PROBE = ROOT / "research/o008_probe/probe_2R_proxy.json"
l1 = W._l1


def pvec(lay):
    return D.params_of(lay).to_vector()


def _e010():
    name = "e010_run_for_control_test"
    if name in sys.modules:
        return sys.modules[name]
    sp = importlib.util.spec_from_file_location(name, ROOT / "experiments" / "runners" / "e010_run.py")
    m = importlib.util.module_from_spec(sp)
    sys.modules[name] = m
    sp.loader.exec_module(m)
    return m


@pytest.fixture(scope="module")
def cfg10():
    return yaml.safe_load((ROOT / "experiments" / "specs" / "E010.yaml").read_text())["config"]


@pytest.fixture(scope="module")
def twoR(cfg10):
    entry = next(x for x in cfg10["references"] if x["reference_id"] == "2D_Case_2R")
    rc = _e010().judged_reference(entry, cfg10)
    tw, _, _ = W.twin(rc.reference, rc.spec, with_l1=False)
    return rc.spec, tw


@pytest.fixture(scope="module")
def case4(cfg10):
    rc = _e010().dev_reference("case4", cfg10)
    tw, _, _ = W.twin(rc.reference, rc.spec, with_l1=False)
    return rc.spec, tw


@pytest.fixture(scope="module")
def spec():
    return D.halfbridge_housing_spec(3, wires_per_die=1)


@pytest.fixture(scope="module")
def wstar(spec):
    """A housing layout used as W*: a generated reach-domain layout."""
    return D.generate(spec, 1, 11, reach=True)[0]


class Boom(Exception):
    pass


def raising_l_sub(_lay):
    raise Boom("l_sub must not be called")


# CHEAP degradation settings for the unit tests
FAST = C.DegradeConfig(target_ratio=1.05, max_proposals=60)


# ------------------------------------------------------------------------------------------------------ no L2
def test_degradation_and_proxy_never_call_l2(spec, wstar, monkeypatch):
    """The functions take no L2 callable (signatures), the l_sub that would be injected raises, and the l2_layout solver
    entry points raise too: nothing reaches them."""
    for fn in (C.proxy_descent, C.degrade_draw, C.proxy_alone):
        assert not [n for n in inspect.signature(fn).parameters if "sub" in n.lower() or "l2" in n.lower()], fn
    assert "l_sub" in inspect.signature(C.choose_proxy).parameters  # the only place a shortlist solver enters
    assert "r_d_at_l2" in inspect.signature(C.draw_degradations).parameters
    from moduleforge.solvers import l2_layout
    for name in dir(l2_layout):
        if name.startswith(("solve", "l2", "run")) and callable(getattr(l2_layout, name)):
            monkeypatch.setattr(l2_layout, name, lambda *a, _n=name, **k: (_ for _ in ()).throw(Boom(_n)))
    solvers = L.LocalSolvers(l1=l1, l_sub=raising_l_sub)
    r = C.proxy_descent(spec, D.params_of(wstar), solvers.l1, step_limit=3)
    assert r.steps >= 0
    dg = C.degrade_draw(spec, wstar, np.random.default_rng(1), solvers.l1, FAST)
    assert dg.proposals >= 1
    a = C.proxy_alone(spec, dg.layout, solvers.l1, budget=40)
    assert a.kind in (L.BUDGET, L.LOCAL_OPTIMUM)
    assert not any("l2_layout" in m for m in sys.modules if m.startswith("moduleforge.optimize.control"))
    assert not hasattr(C, "l2_layout")


# ------------------------------------------------------------------------------------------------- degradation
def test_degrade_draw_is_deterministic_per_seed(spec, wstar):
    a = C.degrade_draw(spec, wstar, np.random.default_rng(np.random.SeedSequence([5, 0, 0, 0])), l1, FAST)
    b = C.degrade_draw(spec, wstar, np.random.default_rng(np.random.SeedSequence([5, 0, 0, 0])), l1, FAST)
    c = C.degrade_draw(spec, wstar, np.random.default_rng(np.random.SeedSequence([5, 0, 0, 1])), l1, FAST)
    assert a.layout.fingerprint() == b.layout.fingerprint() and a.path == b.path and a.l1_ratio == b.l1_ratio
    assert a.layout.fingerprint() != c.layout.fingerprint()


def test_degrade_draw_outputs_are_drc_clean_in_domain_and_stop_at_the_target(spec, wstar):
    cx = D._Ctx(spec, reach=True)
    cfg = C.DegradeConfig(target_ratio=1.10, max_proposals=300)
    dg = C.degrade_draw(spec, wstar, np.random.default_rng(3), l1, cfg)
    assert dg.stop == "target" and dg.l1_ratio >= 1.10 and dg.accepted == len(dg.path) >= 1
    ratios = [l1(D.build(spec, D.Params.from_vector(np.asarray(v)))) / l1(wstar) for v in dg.path]
    assert all(b > a for a, b in zip(ratios, ratios[1:], strict=False))  # an ascent
    assert ratios[-1] == pytest.approx(dg.l1_ratio, rel=1e-12)
    assert all(r < 1.10 for r in ratios[:-1])  # stopped at the first state at or above the target
    for v in dg.path:  # every accepted state
        p = D.Params.from_vector(np.asarray(v))
        ok, why = D.in_domain(spec, p, reach=True, ctx=cx)
        assert ok, why
        assert not check(D.build(spec, p), spec.rules)
    # moves only over the search's set
    other = [i for i in range(len(NAMES)) if i not in L.movable_indices()]
    assert np.array_equal(pvec(dg.layout)[other], pvec(wstar)[other])
    assert dg.changed == int(np.sum(np.abs(pvec(dg.layout) - pvec(wstar)) > 1e-9))
    assert dg.manhattan_mm == pytest.approx(float(np.abs(pvec(dg.layout) - pvec(wstar)).sum()))
    # a stricter proposal budget ends at "proposals"
    short = C.degrade_draw(spec, wstar, np.random.default_rng(3), l1, C.DegradeConfig(target_ratio=50.0, max_proposals=7))
    assert short.stop == "proposals" and short.proposals == 7


def test_degrade_dies_fixed_leaves_row_parameters_bit_identical(spec, wstar):
    cfg = C.DegradeConfig(target_ratio=1.10, max_proposals=200, dies_fixed=True)
    for s in range(3):
        dg = C.degrade_draw(spec, wstar, np.random.default_rng(s), l1, cfg)
        assert dg.accepted >= 1
        assert pvec(dg.layout)[ROWS].tobytes() == pvec(wstar)[ROWS].tobytes()
    free = C.DegradeConfig(target_ratio=1.5, max_proposals=400)
    moved = any(pvec(C.degrade_draw(spec, wstar, np.random.default_rng(s), l1, free).layout)[ROWS].tobytes()
                != pvec(wstar)[ROWS].tobytes() for s in range(4))
    assert moved  # with the die rows free the same draws do move them (the fixed result is not a vacuous pass)


def test_proxy_descent_dies_fixed_leaves_row_parameters_bit_identical(spec, wstar):
    def score(lay):  # a synthetic score that wants the die rows to move: sum of the row coordinates
        return float(pvec(lay)[ROWS].sum())

    free = C.proxy_descent(spec, D.params_of(wstar), score, step_limit=8, min_gain=0.0)
    fixed = C.proxy_descent(spec, D.params_of(wstar), score, step_limit=8, dies_fixed=True, min_gain=0.0)
    assert pvec(free.layout)[ROWS].tobytes() != pvec(wstar)[ROWS].tobytes()
    assert pvec(fixed.layout)[ROWS].tobytes() == pvec(wstar)[ROWS].tobytes()
    assert all(not (t["move"] or "").startswith("row_") for t in fixed.trajectory)
    assert all(np.asarray(t["vec"])[ROWS].tobytes() == pvec(wstar)[ROWS].tobytes() for t in fixed.trajectory)


def test_proxy_descent_is_clean_in_domain_and_monotone(spec, wstar):
    cx = D._Ctx(spec, reach=True)
    r = C.proxy_descent(spec, D.params_of(wstar), l1, step_limit=6)
    assert r.kind in (L.LOCAL_OPTIMUM, L.STEP_LIMIT) and r.steps == len(r.trajectory) - 1 <= 6
    sc = [t["score"] for t in r.trajectory]
    assert all(b < a for a, b in zip(sc, sc[1:], strict=False)) and r.l1 == sc[-1] and r.l1_start == sc[0]
    assert r.l1_ratio == pytest.approx(r.l1 / r.l1_start)
    for t in r.trajectory[1:]:
        p = D.Params.from_vector(np.asarray(t["vec"]))
        assert D.in_domain(spec, p, reach=True, ctx=cx)[0]
        assert not check(D.build(spec, p), spec.rules)
        assert t["move"] in NAMES or ">" in t["move"]  # a single parameter or a reach jump
    d = np.abs(np.asarray(r.trajectory[-1]["vec"]) - pvec(wstar))
    assert np.all(d[:4] == 0) and np.all(d[40:] == 0)  # flags, feet and signal offsets never move


# -------------------------------------------------------------------------------------------- the redraw logic
def _scripted(values):
    calls = []

    def r_d(lay):
        calls.append(lay.fingerprint())
        return values[len(calls) - 1]

    return r_d, calls


def test_redraw_accepts_in_window_only_and_records_attempts(spec, wstar):
    # the window [1.25, 1.60] is closed; values in draw 0: 1.24, 1.61, 1.25 -> accepted at attempt 2; draw 1: 1.60 first try
    # draw 2: 1.0 1.0 1.0 1.0 (limit 3 -> 4 attempts) -> not accepted
    vals = [1.24, 1.61, 1.25, 1.60, 1.0, 1.7, 1.2, 1.9]
    f, calls = _scripted(vals)
    out = C.draw_degradations(spec, wstar, 77, 2, 3, f, redraw_limit=3, l1=l1, cfg=FAST)
    assert len(calls) == 8 and [o.attempts for o in out] == [3, 1, 4]
    assert [o.accepted for o in out] == [True, True, False]
    assert out[0].r_d == 1.25 and out[1].r_d == 1.60 and out[2].r_d is None and out[2].layout is None
    assert [a["r_d"] for a in out[0].attempt_log] == [1.24, 1.61, 1.25]
    assert [a["in_window"] for a in out[2].attempt_log] == [False] * 4
    assert out[0].layout.fingerprint() == calls[2] and out[1].layout.fingerprint() == calls[3]
    # sub-seeds are SeedSequence([seed, layout_index, draw, attempt]), per attempt
    for o in out:
        for a in o.attempt_log:
            assert a["entropy"] == [77, 2, o.draw, a["attempt"]]
    rng = np.random.default_rng(np.random.SeedSequence([77, 2, 0, 2]))
    again = C.degrade_draw(spec, wstar, rng, l1, FAST)
    assert again.layout.fingerprint() == out[0].layout.fingerprint()
    assert len({c for c in calls}) > 1  # different attempts give different layouts


def test_redraw_limit_zero_and_never_exceeds_the_limit(spec, wstar):
    f, calls = _scripted([9.0] * 20)
    out = C.draw_degradations(spec, wstar, 1, 0, 2, f, redraw_limit=0, l1=l1, cfg=FAST)
    assert len(calls) == 2 and [o.attempts for o in out] == [1, 1] and not any(o.accepted for o in out)
    f, calls = _scripted([9.0] * 20)
    C.draw_degradations(spec, wstar, 1, 0, 2, f, redraw_limit=4, l1=l1, cfg=FAST)
    assert len(calls) == 2 * 5
    with pytest.raises(ValueError):
        C.draw_degradations(spec, wstar, 1, 0, 1, f, redraw_limit=-1, l1=l1, cfg=FAST)


def test_draw_degradations_is_deterministic_and_seed_sensitive(spec, wstar):
    def run(seed, idx):
        f, _ = _scripted([1.4] * 10)
        return [o.layout.fingerprint() for o in C.draw_degradations(spec, wstar, seed, idx, 3, f, 1, l1, FAST)]

    assert run(5, 0) == run(5, 0)
    assert run(5, 0) != run(6, 0) and run(5, 0) != run(5, 1)
    assert len(set(run(5, 0))) == 3  # the draws differ


# ---------------------------------------------------------------------------------------------------- choose_proxy
class FakeDesc:
    def __init__(self, layout, ratio=0.9, steps=7, kind=L.LOCAL_OPTIMUM):
        self.layout, self.l1_ratio, self.steps, self.kind = layout, ratio, steps, kind


def test_choose_proxy_returns_W_unless_the_descent_is_strictly_lower(spec, wstar):
    Wl = wstar
    other = D.generate(spec, 2, 12, reach=True)[1]
    vals = {Wl.fingerprint(): 10.0, other.fingerprint(): 10.0}
    for lw, ld, want in ((10.0, 10.0, "W"), (10.0, 12.0, "W"), (10.0, 9.0, "descent")):
        vals[Wl.fingerprint()], vals[other.fingerprint()] = lw, ld
        ch = C.choose_proxy(Wl, FakeDesc(other, 0.8, 11, L.STEP_LIMIT), lambda lay: vals[lay.fingerprint()])
        assert ch.chosen == want
        assert ch.layout is (other if want == "descent" else Wl)
        assert ch.steps == 11 and ch.terminal == L.STEP_LIMIT
        assert ch.l_sub_ratio == pytest.approx(ld / lw if want == "descent" else 1.0)
        assert ch.l1_ratio == (0.8 if want == "descent" else 1.0)
        assert (ch.l_sub_W, ch.l_sub_descent) == (lw, ld)


# ------------------------------------------------------------------------------------------------ proxy_alone
def test_proxy_alone_spends_at_most_the_l1_budget(spec, wstar):
    start = C.degrade_draw(spec, wstar, np.random.default_rng(2), l1, C.DegradeConfig(target_ratio=1.15, max_proposals=300))
    seen = set()

    def f(lay):
        seen.add(lay.fingerprint())
        return l1(lay)

    r = C.proxy_alone(spec, start.layout, f, budget=60)
    assert r.kind == L.BUDGET and len(seen) == 60
    assert r.l1 <= l1(start.layout) and r.steps >= 1
    assert not check(r.layout, spec.rules)
    big = C.proxy_alone(spec, start.layout, l1, budget=180)
    assert big.l1 <= r.l1 and big.steps >= r.steps  # the same path, a longer prefix: more budget never ends higher
    with pytest.raises(ValueError):
        C.proxy_alone(spec, start.layout, l1, budget=0)


# --------------------------------------------------------------------------------------- column sides (T0402/T0403)
def _sides_report(spec, vecs):
    """For each vector: the sides twin._net_side reads, the side tuples the replay certifies, and whether the reading is
    among them.  -> (n, n_read_infeasible, n_ambiguous, examples)"""
    cx = D._Ctx(spec, reach=True)
    bad, amb, ex = 0, 0, []
    for v in vecs:
        p = D.Params.from_vector(np.asarray(v))
        read, feas = C.read_sides(p), C.feasible_sides(spec, p, cx)
        assert feas, "an in-domain layout must have a certifying side tuple"
        if read not in feas:
            bad += 1
            ex.append(("read-not-feasible", read, feas))
        if len(feas) > 1:
            amb += 1
            ex.append(("ambiguous", read, feas))
    return len(vecs), bad, amb, ex


def _check_sides(spec, tw, label, steps=6):
    desc = C.proxy_descent(spec, D.params_of(tw), l1, step_limit=steps)
    vecs = [t["vec"] for t in desc.trajectory]
    dg = C.degrade_draw(spec, desc.layout, np.random.default_rng(11), l1, C.DegradeConfig(target_ratio=1.3875, max_proposals=120))
    vecs += dg.path
    n, bad, amb, ex = _sides_report(spec, vecs)
    print(f"[sides] {label}: {n} states, reading not certified in {bad}, ambiguous {amb}: {ex[:3]}")
    # the starting twin: the sides the walk's jumps assume must be the ones under which the twin is in the domain
    assert C.read_sides(D.params_of(tw)) in C.feasible_sides(spec, D.params_of(tw)), f"{label}: twin side reading"
    assert bad == 0, f"{label}: twin._net_side misreads a column side in {bad} of {n} states: {ex[:3]}"
    return n, amb


def test_column_sides_2R(twoR):
    _check_sides(twoR[0], twoR[1], "2D_Case_2R")


def test_column_sides_case4(case4):
    _check_sides(case4[0], case4[1], "2D_Case_4")


def test_degradations_stay_in_the_reach_domain_on_the_development_layouts(spec, wstar, twoR, case4):
    for sp_, lay, n in ((spec, wstar, 3), (twoR[0], twoR[1], 2), (case4[0], case4[1], 2)):
        cx = D._Ctx(sp_, reach=True)
        recs = C.draw_degradations(sp_, lay, 20261116, 0, n, lambda _l: 1.4, 0, l1,
                                   C.DegradeConfig(target_ratio=1.15, max_proposals=150))
        for r in recs:
            assert r.accepted
            ok, why = D.in_domain(sp_, D.params_of(r.layout), reach=True, ctx=cx)
            assert ok, why
            assert not check(r.layout, sp_.rules)


# -------------------------------------------------------------------------------------------- regression anchor
@pytest.mark.slow
def test_proxy_descent_reproduces_the_probe_on_2R_twin():
    """With reach off and the probe's movable set, proxy_descent on 2R's twin gives the probe's L1(W*)/L1(W) and 27 steps
    (research/o008_probe/probe_2R_proxy.json: its saved context, the twin E010 built)."""
    ref = json.loads(PROBE.read_text())
    ctx = pickle.loads(CTX_2R.read_bytes())
    spec_, tw = ctx["spec"], ctx["twin"]
    assert l1(tw) * 1e9 == pytest.approx(ref["l1_W_nH"], rel=1e-12)
    r = C.proxy_descent(spec_, D.params_of(tw), l1, step_limit=ref["max_steps"] * 4, reach=False)
    assert r.steps == ref["proxy"]["steps"] == 27 and not ref["proxy"]["hit_step_cap"] and r.kind == L.LOCAL_OPTIMUM
    assert r.l1_ratio == pytest.approx(ref["proxy"]["l1_proxy_over_twin"], abs=1e-9)
    assert r.l1_ratio == pytest.approx(0.898, abs=5e-4)
    assert r.l1 * 1e9 == pytest.approx(ref["l1_proxy_nH"], abs=1e-9)
    assert not check(r.layout, spec_.rules)
