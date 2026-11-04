"""AMG-CG statistics in ThermalResult.meta (T0222): instrumentation only, the iterates are unchanged."""

from __future__ import annotations

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

KEYS = ("cg_iterations", "cg_max_iterations", "linear_rel_residual_max", "cg_hit_maxiter")


@pytest.mark.parametrize("order", [1, 2])
def test_instrumented_solve_is_bit_identical_to_plain_multilevel_solve(order, monkeypatch):
    seen = []
    orig = F._Solver.solve

    def spy(self, b, x0):
        x = orig(self, b, x0)
        seen.append((self, b.copy(), x0.copy(), x))
        return x

    monkeypatch.setattr(F._Solver, "solve", spy)
    F.solve_box_stack(16e-3, 16e-3, _BAND_LAYERS, H, TC, _BAND_SRC, rule=F.GridRule(h0=8e-3, element_order=order))
    assert seen
    for sol, b, x0, x in seen:
        c = float(sol.one @ b) / sol.c_den
        plain = c + sol.ml.solve(b - c * sol.a1, x0=x0 - c, tol=F.LINEAR_RTOL, maxiter=400, accel="cg")
        assert np.array_equal(x, plain)
    assert max(s[0].stats["iterations"] for s in seen) >= 1  # a warm start at the solution can take 0 iterations


@pytest.mark.parametrize("mode", ["box", "layout"])
def test_meta_keys_and_values_on_plain_grid(mode):
    if mode == "box":
        r = F.solve_box_stack(16e-3, 16e-3, _BAND_LAYERS, H, TC, _BAND_SRC, rule=F.GridRule(h0=8e-3))
    else:
        r = F.solve_layout(_toy_layout(), [40.0, 20.0], H, TC, rule=F.GridRule(h0=8e-3))
    for k in KEYS:
        assert k in r.meta
    its = r.meta["cg_iterations"]
    assert isinstance(its, list) and all(isinstance(i, int) for i in its)
    assert len(its) == r.picard_iters
    assert isinstance(r.meta["cg_max_iterations"], int) and r.meta["cg_max_iterations"] == max(its)
    assert 1 <= r.meta["cg_max_iterations"] <= F.CG_MAXITER
    assert isinstance(r.meta["linear_rel_residual_max"], float) and 0.0 <= r.meta["linear_rel_residual_max"] <= 1e-8
    assert r.meta["cg_hit_maxiter"] is False


def test_counter_sees_the_sliver_effect():
    f, z_ba, z_ad = F.SNAP_FRACTION, 2e-3, 2.1e-3
    rule = F.GridRule(h0=4e-3, element_order=1)
    kept = ([8e-3 + 1.5 * f * 0.5e-3], [4e-3 + 1.5 * f * 4e-3], [z_ba - 1.5 * f * 2e-3, z_ad - 1.5 * f * 0.1e-3])
    snapped = ([8e-3 + 0.5 * f * 0.5e-3], [4e-3 + 0.5 * f * 4e-3], [z_ad - 0.5 * f * 0.1e-3])
    for lv in (0, 1):
        rk = F.solve_box_stack(16e-3, 16e-3, _BAND_LAYERS, H, TC, _BAND_SRC, rule=rule, level=lv, extra_lines=kept)
        rs = F.solve_box_stack(16e-3, 16e-3, _BAND_LAYERS, H, TC, _BAND_SRC, rule=rule, level=lv, extra_lines=snapped)
        assert rk.meta["cg_max_iterations"] > rs.meta["cg_max_iterations"]
