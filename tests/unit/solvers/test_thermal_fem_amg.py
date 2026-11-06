"""GridRule.amg_gs_sweeps (T0242): opt-in order-1 AMG smoother option; the default leaves every solve bitwise unchanged."""

from __future__ import annotations

import dataclasses

import numpy as np
import pytest

from shapely.geometry import box

from moduleforge.geometry.layout import Die, Layout, Trace
from moduleforge.geometry.stack import default_dbc_stack
from moduleforge.solvers import thermal_fem as F

TC = 338.15
H = 5000.0
_BAND_LAYERS = [F.BoxLayer(2e-3, 390.0, 1, "base"), F.BoxLayer(0.1e-3, 60.0, 1, "attach"),
                F.BoxLayer(0.18e-3, 120.0, 1, "die")]
_BAND_SRC = [(4e-3, 4e-3, 8e-3, 12e-3, 20.0), (9e-3, 4e-3, 12e-3, 12e-3, 15.0)]


def _toy_layout() -> Layout:
    outline = box(0.0, 0.0, 20e-3, 10e-3)
    d1 = Die(6e-3, 5e-3, 4e-3, 4e-3, "HS", {})
    d2 = Die(14e-3, 5e-3, 4e-3, 4e-3, "LS", {})
    return Layout("toy", 1, outline, [Trace("DC+", box(2e-3, 2e-3, 18e-3, 8e-3))], [d1, d2], [], {},
                  box(-3e-3, -3e-3, 23e-3, 13e-3), default_dbc_stack())

# Captured from the code before the option existed (git HEAD of thermal_fem.py, 2026-11-05): sha256 of T.tobytes() was
# identical before and after the edit on the capture machine; sums are compared to 1e-12 relative for portability.
_BOX = {"cg": [21, 0], "sum": 197788.3785537942, "max": 371.83441217826044, "min": 363.8444980116085}
_LAY = {"cg": [38, 34, 29, 25, 19], "sum": 804041.5712268387, "max": 410.1531509774512, "min": 363.6413634235871}


def _check(r, ref):
    assert r.meta["cg_iterations"] == ref["cg"]
    assert r.meta["amg_gs_sweeps"] is None
    assert float(r.T.sum()) == pytest.approx(ref["sum"], rel=1e-12)
    assert float(r.T.max()) == pytest.approx(ref["max"], rel=1e-12)
    assert float(r.T.min()) == pytest.approx(ref["min"], rel=1e-12)


def test_default_box_stack_unchanged():
    _check(F.solve_box_stack(16e-3, 16e-3, _BAND_LAYERS, H, TC, _BAND_SRC, rule=F.GridRule(h0=8e-3)), _BOX)


def test_default_layout_unchanged():
    _check(F.solve_layout(_toy_layout(), [40.0, 20.0], H, TC, rule=F.GridRule(h0=8e-3)), _LAY)


def test_default_hierarchy_is_pyamgs_own(monkeypatch):
    rule = F.GridRule(h0=8e-3)
    assert rule.amg_gs_sweeps is None
    assert dataclasses.replace(rule, amg_gs_sweeps=None) == rule
    seen = []  # the default builds the hierarchy with pyamg's own smoothers: no smoother argument is passed (T0246)
    orig = F._sa_solver
    monkeypatch.setattr(F, "_sa_solver", lambda A, **kw: seen.append(kw) or orig(A, **kw))
    F.solve_box_stack(16e-3, 16e-3, _BAND_LAYERS, 50.0, TC, _BAND_SRC, rule=rule)
    assert seen and all(kw == {"max_coarse": 500} for kw in seen)


def _solve(mode, rule, level):
    if mode == "box":
        return F.solve_box_stack(16e-3, 16e-3, _BAND_LAYERS, 50.0, TC, _BAND_SRC, rule=rule, level=level)
    return F.solve_layout(_toy_layout(), [2.0, 1.0], 50.0, TC, rule=rule, level=level)


@pytest.mark.parametrize("mode", ["box", "layout"])
def test_one_sweep_matches_the_default_at_level_1(mode):
    """amg_gs_sweeps = 1 is pyamg's default smoothing: same CG counts and temperatures (to 1e-12 K, for portability;
    bitwise on the capture machine) as None, so the option's plumbing changes nothing but the sweep count (T0246)."""
    r0, r1 = _solve(mode, F.GridRule(h0=8e-3), 1), _solve(mode, F.GridRule(h0=8e-3, amg_gs_sweeps=1), 1)
    assert r1.meta["cg_iterations"] == r0.meta["cg_iterations"]
    assert float(np.abs(r1.T - r0.T).max()) <= 1e-12


@pytest.mark.parametrize("mode", ["box", "layout"])
def test_two_sweeps_cut_cg_at_level_1(mode):
    """At level 1 too, two sweeps need fewer CG iterations than the default (measured 26 -> 18 box, 52 -> 37 layout)
    at equal temperatures (|dT| <= 1e-8 K; measured <= 1.6e-10 K) (T0246)."""
    r0, r2 = _solve(mode, F.GridRule(h0=8e-3), 1), _solve(mode, F.GridRule(h0=8e-3, amg_gs_sweeps=2), 1)
    assert max(r2.meta["cg_iterations"]) <= 0.85 * max(r0.meta["cg_iterations"])
    assert float(np.abs(r2.T - r0.T).max()) <= 1e-8


@pytest.mark.parametrize("mode", ["box", "layout"])
def test_two_sweeps_same_temperatures_weak_cooling(mode):
    h = 50.0  # weakly cooled, h <= 50 W/(m2 K)
    base = F.GridRule(h0=8e-3)
    two = dataclasses.replace(base, amg_gs_sweeps=2)
    if mode == "box":
        r0 = F.solve_box_stack(16e-3, 16e-3, _BAND_LAYERS, h, TC, _BAND_SRC, rule=base)
        r2 = F.solve_box_stack(16e-3, 16e-3, _BAND_LAYERS, h, TC, _BAND_SRC, rule=two)
    else:
        r0 = F.solve_layout(_toy_layout(), [2.0, 1.0], h, TC, rule=base)
        r2 = F.solve_layout(_toy_layout(), [2.0, 1.0], h, TC, rule=two)
    assert r2.meta["amg_gs_sweeps"] == 2 and r0.meta["amg_gs_sweeps"] is None
    assert r2.energy_balance <= 1e-6
    assert float(np.abs(r2.T - r0.T).max()) <= 1e-8
    assert r2.meta["cg_hit_maxiter"] is False


def test_two_sweeps_build_a_different_hierarchy(monkeypatch):
    seen = []
    orig = F._sa_solver
    monkeypatch.setattr(F, "_sa_solver", lambda A, **kw: seen.append(kw) or orig(A, **kw))
    F.solve_box_stack(16e-3, 16e-3, _BAND_LAYERS, 50.0, TC, _BAND_SRC, rule=F.GridRule(h0=8e-3, amg_gs_sweeps=3))
    gs = ("gauss_seidel", {"sweep": "symmetric", "iterations": 3})
    assert seen and all(kw == {"max_coarse": 500, "presmoother": gs, "postsmoother": gs} for kw in seen)


@pytest.mark.parametrize("bad", [0, 9, -1, 2.0, True, "2"])
def test_invalid_sweeps_rejected(bad):
    with pytest.raises(ValueError):
        F.GridRule(amg_gs_sweeps=bad)


def test_order2_with_option_rejected():
    with pytest.raises(ValueError):
        F.GridRule(element_order=2, amg_gs_sweeps=2)
    assert F.GridRule(element_order=2).amg_gs_sweeps is None
    for n in (1, 8):
        assert F.GridRule(amg_gs_sweeps=n).amg_gs_sweeps == n
