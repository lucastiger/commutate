"""Tests of the L1 thermal model (moduleforge.thermal): analytic limits, linearity, k(T) super-linearity, mirror symmetry,
energy consistency, determinism, API."""
from __future__ import annotations

import dataclasses

import numpy as np
import pytest
from scipy.integrate import quad
from scipy.optimize import brentq
from shapely.affinity import scale
from shapely.geometry import box

from moduleforge.generate.halfbridge import generate_layouts
from moduleforge.geometry.layout import Die, Layout, Terminal, Trace
from moduleforge.geometry.stack import K_LAWS, T_REF
from moduleforge.solvers.thermal_series import box_series
from moduleforge.thermal import CALIBRATION, GRID_RULE, L1Result, evaluate, raw_fv

T_C, H = 338.15, 5000.0


@pytest.fixture(scope="module")
def lay():
    """Development layout u_shaped/2 (5.0 mm dies, in the calibration table)."""
    return generate_layouts(1, 20261101, family="u_shaped", dies_per_switch=2)[0]


def _column(side: float, die: float, inset: float = 0.0) -> Layout:
    """Laterally uniform column: baseplate = substrate = top Cu = ``side`` square, one centred ``die`` square die."""
    sq = box(0.0, 0.0, side, side)
    d = Die(cx=side / 2, cy=side / 2, w=die, h=die, switch="HS", pads={})
    return Layout(family="test", dies_per_switch=1, outline=sq, traces=[Trace("DC+", sq)], dies=[d], wires=[],
                  terminals={}, baseplate_outline=sq, backside_inset=inset)


def _layers(lo: Layout):
    st = lo.stack
    out = [(la.thickness, la.k) for la in st.layers]
    d = lo.dies[0]
    return out + [(d.attach_thickness, st.die_attach.k), (d.thickness, st.die.k)]


def test_1d_series_resistance_limit():
    """Die = substrate = baseplate = 5 mm square, adiabatic sides: exactly 1D.  T = T_c + P (sum t_i/(k_i A) + 1/(h A)).
    The FV scheme is exact for 1D piecewise-constant k (linear T per layer, harmonic-mean faces), so only solver
    tolerance remains: 1e-6 relative to the rise."""
    s = 5.0e-3
    lo = _column(s, s)
    P = 30.0
    A = s * s
    r_series = sum(t / (k * A) for t, k in _layers(lo)) + 1.0 / (H * A)
    out = evaluate(lo, P, h=H, T_c=T_C, constant_k=True, calibrate=False)
    assert out.tj_mean[0] - T_C == pytest.approx(P * r_series, rel=1e-6)


def test_single_source_nlayer_series_limit():
    """One 5 mm source on the laterally uniform 30 mm five-layer substrate stack (constant k) against the Fourier-series
    closed form of solvers.thermal_series (Carslaw & Jaeger 1959 sec. 3.6; series converged by doubling n_modes, 1e-3 K).

    The die (2 um) and attach (1 um) are made thin, so the FV problem is the closed form's: flux over the footprint on
    top of the Cu, plus the 1D drops P t / (k A) of the two thin layers (Incropera, composite wall).  The remaining
    difference is discretisation error.  Measured on this case: +0.34 % of the rise on the frozen coarse rule (1.5 mm
    lateral cap; +0.67 % with n1's 4 mm cap), -0.05 % on a fine rule (h0 0.5 mm, edge 0.5 x thinnest layer, 6 z cells per
    layer).  The coarse rule is held to 0.7 % (about twice its measured error) and the fine rule to 0.2 %, which checks that the
    FV converges to the closed form rather than merely landing near it.  (With the real 180 um die and 50 um attach the closed form's 1D
    die drop is itself a 2 % approximation: lateral spreading in the die, so that geometry is not used here.)"""
    a, s, P = 0.030, 5.0e-3, 20.0
    lo = _column(a, s)
    lo = dataclasses.replace(lo, dies=[dataclasses.replace(lo.dies[0], thickness=2e-6, attach_thickness=1e-6)])
    sub = _layers(lo)[:5]
    src = [(0.5 * (a - s), 0.5 * (a + s), 0.5 * (a - s), 0.5 * (a + s), P)]
    ser = {n: box_series(a, a, sub, src, h=H, T_c=T_C, n_modes=n)["src0.tj_mean"] for n in (300, 600)}
    assert abs(ser[300] - ser[600]) < 1e-3
    d = lo.dies[0]
    drop = P * (d.attach_thickness / (lo.stack.die_attach.k * s * s) + d.thickness / (lo.stack.die.k * s * s))
    exact = ser[600] - T_C + drop
    out = evaluate(lo, P, h=H, T_c=T_C, constant_k=True, calibrate=False)
    assert out.tj_mean[0] - T_C == pytest.approx(exact, rel=0.007)
    fine = raw_fv(lo, P, h=H, T_c=T_C, constant_k=True,
                  grid_rule={"h0_max": 0.5e-3, "lat_frac": 16.0, "edge_frac": 0.5, "z_cells": 6})
    assert fine["tj_mean"][0] - T_C == pytest.approx(exact, rel=0.002)
    assert out.T_bp - T_C == pytest.approx(P / (H * a * a), rel=1e-12)  # exact mean bottom temperature


def _kirchhoff_top_temperature(lo: Layout, P: float, h: float) -> float:
    """Exact 1D top-of-die temperature [K] with every layer on its K_LAWS law (adiabatic sides, flux q = P/A).

    Steady 1D conduction with k(T) conserves q, and the Kirchhoff transform makes each layer exact:
    integral_{T_below}^{T_above} k(T) dT = q t (Carslaw & Jaeger 1959 sec. 1.1 and 1.2; Incropera, composite wall).
    Each layer is solved for T_above by brentq on that integral (quad, 1e-13), starting from the exact bottom
    temperature T_c + q/h; the die is the seventh layer."""
    st, d = lo.stack, lo.dies[0]
    layers = [*st.layers, st.die_attach, st.die]
    thick = [la.thickness for la in st.layers] + [d.attach_thickness, d.thickness]
    q = P / (d.w * d.h)
    T = T_C + q / h
    for la, t in zip(layers, thick, strict=True):
        def resid(T1, la=la, t=t, T0=T):
            return quad(lambda x: la.k_at(x), T0, T1, epsabs=1e-12, epsrel=1e-13)[0] - q * t
        T = brentq(resid, T, min(T + 150.0, 523.0), xtol=1e-12)
    return T


@pytest.mark.parametrize("P", [20.0, 40.0, 60.0])
def test_1d_kirchhoff_limit_with_k_of_T(P):
    """k(T) path against the exact 1D Kirchhoff limit: a 5 mm column (die = substrate = baseplate, adiabatic sides,
    h = 5e4 to keep every layer inside the 273-523 K validity range), all seven layers on their K_LAWS.

    The FV is exact in 1D only for constant k per cell; with k(T) it carries a discretisation error that grows with
    the k variation across a cell, i.e. with the rise.  Measured on the frozen coarse rule (2 z cells per layer): 1.6e-5,
    3.8e-5 and 2.4e-4 of the rise at 20, 40 and 60 W (the error is second order in the temperature step per cell, so it
    grows faster than the power).  The tolerance is set from this scaling, about twice the worst measured value, 5e-4
    of the rise.  The convergence check refines to 8 z cells per layer (measured 8.6e-7, 5.1e-6, 1.4e-5); it must beat
    the coarse error at 60 W and hold 5e-5, so the FV converges to the Kirchhoff value rather than landing near it.
    The Picard tolerance (1e-2 K lagged increment) is far below both."""
    h = 5.0e4
    lo = _column(5.0e-3, 5.0e-3)
    exact = _kirchhoff_top_temperature(lo, P, h)
    rise = exact - T_C
    out = evaluate(lo, P, h=h, T_c=T_C, calibrate=False)
    err = abs(out.tj_mean[0] - exact) / rise
    assert err < 5e-4
    assert out.tj_mean[0] > exact  # lagged-k mid-cell sampling errs on the hot side here (measured sign)
    fine = raw_fv(lo, P, h=h, T_c=T_C,
                  grid_rule={"h0_max": 0.5e-3, "lat_frac": 16.0, "edge_frac": 0.5, "z_cells": 8})
    err_fine = abs(fine["tj_mean"][0] - exact) / rise
    assert err_fine < 5e-5
    if P == 60.0:
        assert err_fine < err / 5


def test_linearity_in_power_constant_k(lay):
    """constant_k makes the problem linear: 2x power gives 2x rise (1e-9 relative)."""
    p = 25.0
    a = evaluate(lay, p, h=H, T_c=T_C, constant_k=True)
    b = evaluate(lay, 2 * p, h=H, T_c=T_C, constant_k=True)
    np.testing.assert_allclose(b.tj_mean - T_C, 2 * (a.tj_mean - T_C), rtol=1e-9)


@pytest.mark.parametrize("material", sorted(K_LAWS))
def test_every_k_law_falls_above_300K(material):
    T = np.linspace(T_REF + 1.0, 520.0, 40)
    assert np.all(np.asarray(K_LAWS[material](T)) < K_LAWS[material](T_REF))


def test_superlinear_rise_with_k_of_T(lay):
    """All laws fall above 300 K, so heating lowers k and the rise grows faster than power; constant k at 300 K
    under-predicts the rise."""
    p = 30.0
    a = evaluate(lay, p, h=H, T_c=T_C)
    b = evaluate(lay, 2 * p, h=H, T_c=T_C)
    ratio = (b.tj_mean - T_C) / (a.tj_mean - T_C)
    assert np.all(ratio > 2.0 + 1e-3)
    assert np.all(ratio < 2.2)  # sanity: a few-percent effect, not a runaway
    ck = evaluate(lay, p, h=H, T_c=T_C, constant_k=True)
    assert np.all(ck.tj_mean < a.tj_mean)
    assert a.picard_iters > 1 and ck.picard_iters >= 1


def _mirror_x(lo: Layout) -> Layout:
    f = lambda g: scale(g, xfact=-1.0, yfact=1.0, origin=(0.0, 0.0))  # noqa: E731
    dies = [dataclasses.replace(d, cx=-d.cx, pads={k: (-v[2], v[1], -v[0], v[3]) for k, v in d.pads.items()})
            for d in lo.dies]
    terms = {k: Terminal(t.net, -t.cx, t.cy, t.w, t.h) for k, t in lo.terminals.items()}
    return dataclasses.replace(lo, outline=f(lo.outline), traces=[Trace(t.net, f(t.polygon)) for t in lo.traces],
                               dies=dies, wires=[], signal_wires=[], terminals=terms,
                               baseplate_outline=f(lo.baseplate_outline))


@pytest.mark.parametrize("family,k", [("u_shaped", 2), ("side_by_side", 2)])
def test_mirror_symmetry(family, k):
    """Mirroring the layout about x = 0 leaves each die's value unchanged (dies keep their list order).  The grid is
    mirror-symmetric by construction; the remaining difference is the iterative-solver tolerance, so 1e-3 K."""
    lo = generate_layouts(1, 20261101, family=family, dies_per_switch=k)[0]
    a = evaluate(lo, 40.0, h=H, T_c=T_C)
    b = evaluate(_mirror_x(lo), 40.0, h=H, T_c=T_C)
    np.testing.assert_allclose(b.tj_mean, a.tj_mean, atol=1e-3)
    np.testing.assert_allclose(b.tj_max, a.tj_max, atol=1e-3)


def test_energy_balance_and_flux_consistency(lay):
    """Heat out through the h-boundary equals the power in (reported solver balance), and the die-local rise is the
    calibrated coarse rise above the exact mean bottom temperature T_bp = T_c + P_tot/(h A).

    Within one solve the calibration relation is exact up to rounding (1e-12 relative).  Against a second, separate
    solve (``calibrate=False``) the iterative solver's run-to-run difference (summation order of threaded BLAS
    reductions; measured up to 6e-11 K, attempt 1) applies, so that comparison uses the determinism tolerance 1e-9 K."""
    p = 35.0
    o = evaluate(lay, p, h=H, T_c=T_C)
    assert o.energy_balance < 1e-8
    assert o.T_bp == pytest.approx(T_C + p * len(lay.dies) / (H * lay.baseplate_outline.area), rel=1e-14)
    np.testing.assert_allclose(o.tj_mean, o.T_bp + o.die_local_rise, rtol=0, atol=1e-12)
    c = o.calibration["c"]
    np.testing.assert_allclose(o.die_local_rise, c * (o.meta["tj_mean_fv"] - o.T_bp), rtol=1e-12)
    raw = evaluate(lay, p, h=H, T_c=T_C, calibrate=False)
    np.testing.assert_allclose(raw.tj_mean, o.meta["tj_mean_fv"], rtol=0, atol=1e-9)
    np.testing.assert_allclose(o.die_local_rise, c * (raw.tj_mean - raw.T_bp), rtol=0, atol=1e-9)
    assert c == CALIBRATION[5.0] and 0.9 < c < 1.0
    assert np.all(o.tj_max >= raw.tj_mean)  # coarse surface max is above the area mean


def test_repeat_evaluation_is_deterministic(lay):
    a = evaluate(lay, 33.0, h=H, T_c=T_C)
    b = evaluate(lay, 33.0, h=H, T_c=T_C)
    # same inputs, same process: equal up to floating-point summation order in the iterative solver (1e-9 K)
    np.testing.assert_allclose(a.tj_mean, b.tj_mean, rtol=0, atol=1e-9)
    np.testing.assert_allclose(a.tj_max, b.tj_max, rtol=0, atol=1e-9)
    assert a.picard_iters == b.picard_iters and a.n_cells == b.n_cells


def test_api_shapes_and_power_vector(lay):
    o = evaluate(lay, 30.0, h=H, T_c=T_C)
    assert isinstance(o, L1Result) and o.tj_mean.shape == (len(lay.dies),) and o.wall_s > 0
    same = evaluate(lay, np.full(len(lay.dies), 30.0), h=H, T_c=T_C)
    np.testing.assert_allclose(o.tj_mean, same.tj_mean, rtol=0, atol=1e-9)
    p = np.array([30.0, 0.0, 0.0, 0.0])[: len(lay.dies)]
    hot = evaluate(lay, p, h=H, T_c=T_C)
    assert np.argmax(hot.tj_mean) == 0
    q = np.full(len(lay.dies), 30.0)
    q[0] = 0.0
    assert evaluate(lay, q, h=H, T_c=T_C).tj_mean[0] < o.tj_mean[0]  # a die's own power raises its own value


@pytest.mark.parametrize("s_mm", [4.0, 4.5, 5.0, 5.5])
def test_every_generator_die_size_is_calibrated(s_mm):
    """The generator's die-size support (halfbridge.draw_die_size_mm: 4.0..5.5 mm on the 0.5 mm grid) is in the table,
    and a fixed-size development layout evaluates with its own factor."""
    assert set(CALIBRATION) == {4.0, 4.5, 5.0, 5.5}
    lo = generate_layouts(1, 20261101, family="u_shaped", dies_per_switch=2, die_size_mm=s_mm)[0]
    o = evaluate(lo, 20.0, h=H, T_c=T_C)
    assert o.calibration["c"] == CALIBRATION[s_mm] and o.calibration["die_size_mm"] == s_mm
    assert np.all(o.die_local_rise > 0)


def test_unsupported_die_size_raises():
    lo = _column(0.03, 3.0e-3)
    with pytest.raises(ValueError, match="no L1 calibration"):
        evaluate(lo, 10.0, h=H, T_c=T_C)
    mixed = generate_layouts(1, 20261101, family="u_shaped", dies_per_switch=2)[0]
    d0 = mixed.dies[0]
    mixed = dataclasses.replace(mixed, dies=[dataclasses.replace(d0, w=4.0e-3, h=4.0e-3), *mixed.dies[1:]])
    with pytest.raises(ValueError, match="one die size"):
        evaluate(mixed, 10.0, h=H, T_c=T_C)


def test_grid_rule_and_calibration_are_pinned_together():
    """CALIBRATION holds c(s) fitted on the coarse FV of exactly this GRID_RULE (CALIBRATION_VERSION o002-l1-cal-v2).
    Changing either without the other silently breaks the die-local rise by up to the coarse-grid bias (about 1.7 %)."""
    assert GRID_RULE == {"h0_max": 1.5e-3, "lat_frac": 16.0, "edge_frac": 2.0, "z_cells": 2}, (
        "GRID_RULE changed: a grid-rule change needs a refit of c(s) (benchmarks/thermal_l1_calibration.py), a new "
        "CALIBRATION_VERSION and updated CALIBRATION values; update this pin only together with them")
    assert CALIBRATION == {4.0: 0.98544, 4.5: 0.98284, 5.0: 0.98298, 5.5: 0.98402}, (
        "CALIBRATION changed: its values are valid only for the pinned GRID_RULE; a grid-rule change needs a refit of "
        "c(s), so refit and re-pin both together")
