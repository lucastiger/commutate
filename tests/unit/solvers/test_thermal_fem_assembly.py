"""Element order Q1/Q2 and manufactured data of ``moduleforge.solvers.thermal_fem`` (T0205).

Every test compares with a closed form or an independently integrated quantity, never with the solver itself.

References for the closed forms
  * series resistance of a laterally uniform column: T_top = T_c + q (1/h + sum t_i/k_i) (Fourier's law, Incropera et al.,
    Fundamentals of Heat and Mass Transfer, 7th ed., sec. 3.1);
  * Kirchhoff transform for k = k0 (1 + beta (T - T0)): phi(T) = int k dT = k0 [(T-T0) + beta (T-T0)^2 / 2] is linear in z
    in a 1D column (Carslaw & Jaeger, Conduction of Heat in Solids, 2nd ed., 1959, sec. 1.8);
  * method of manufactured solutions: Salari & Knupp, SAND2000-1444 (2000); a Q2 space contains every polynomial of degree
    <= 2 in each variable, so a quadratic field is its own Galerkin solution (Ciarlet, The Finite Element Method for
    Elliptic Problems, 1978, ch. 3-4) when the data are integrated exactly.
"""
from __future__ import annotations

import importlib.util
import json
import math
from pathlib import Path

import numpy as np
import pytest
import sympy as sp
from shapely.geometry import box

from moduleforge.geometry.layout import Die, Layout, Trace
from moduleforge.geometry.stack import default_dbc_stack
from moduleforge.solvers import thermal_fem as F

ROOT = Path(__file__).resolve().parents[3]


def _orders(errs: list[float]) -> list[float]:
    return [math.log2(errs[i] / errs[i + 1]) for i in range(len(errs) - 1)]


def _toy_layout() -> Layout:
    """Two dies on one trace on a 1 mm grid (as in test_thermal_fem)."""
    d1, d2 = Die(6e-3, 5e-3, 4e-3, 4e-3, "HS", {}), Die(14e-3, 5e-3, 4e-3, 4e-3, "LS", {})
    return Layout("toy", 1, box(0.0, 0.0, 20e-3, 10e-3), [Trace("DC+", box(2e-3, 2e-3, 18e-3, 8e-3))], [d1, d2], [], {},
                  box(-3e-3, -3e-3, 23e-3, 13e-3), default_dbc_stack())


# ---------------------------------------------------------------------------------------------------------- options
def test_grid_rule_element_order_and_memory_accounting():
    assert F.GridRule().element_order == 1
    assert F.GridRule(element_order=2).element_order == 2
    with pytest.raises(ValueError):
        F.GridRule(element_order=3)
    with pytest.raises(ValueError):
        F.solve_box_stack(1e-3, 1e-3, [F.BoxLayer(1e-3, 100.0)], 1000.0, 300.0, [], h0=1e-3, element_order=0)
    assert F.max_dofs(7.7e9) == 1_000_000  # unchanged default (Q1)
    assert F.max_dofs(1e9, element_order=2) == int(1e9 // F.BYTES_PER_DOF_BY_ORDER[2])
    assert F.BYTES_PER_DOF_BY_ORDER[2] > F.BYTES_PER_DOF_BY_ORDER[1] > 0  # Q2 stores 3.4x the couplings per row
    assert F.max_dofs(1e9, 5e3, element_order=2) == 200_000  # an explicit figure wins


def test_estimate_dofs_matches_the_assembled_system_for_both_orders():
    """The lattice count of the Q2 dofs (vertices + edges + faces + cells of the active cells) equals the solved N, on a
    layout with void cells (patterned copper, die islands)."""
    lay = _toy_layout()
    for order in (1, 2):
        rule = F.GridRule(h0=2.0e-3, element_order=order)
        r = F.solve_layout(lay, 20.0, 5000.0, 338.15, rule=rule, level=0, constant_k=True)
        assert F.estimate_dofs(lay, rule, 0) == r.dofs
    assert F.estimate_dofs(lay, F.GridRule(h0=2.0e-3, element_order=2), 0) > 5 * F.estimate_dofs(lay, F.GridRule(h0=2.0e-3), 0)


@pytest.mark.parametrize("order", [1, 2])
def test_tj_max_is_the_maximum_over_exactly_the_die_face_nodes(order):
    """Regression (T0205 review): ``tj_max`` is the maximum over the nodes of the die top face only. Unequal powers (60 W,
    0 W): heat from the hot die reaches the unpowered die through the copper, so the node layer just below that die's
    face is hotter than the face itself; any off-face node in the set would raise its ``tj_max``. The face nodes are
    selected here independently, from the node coordinates."""
    lay = _toy_layout()
    r = F.solve_layout(lay, [60.0, 0.0], 5000.0, 338.15, rule=F.GridRule(h0=1e-3, element_order=order), level=0)
    n = r.nodes
    for i, d in enumerate(lay.dies):
        x0, y0, x1, y1 = d.bounds
        zt = lay.stack.z_top("top_cu") + d.attach_thickness + d.thickness
        inside = (n[:, 0] >= x0 - 1e-12) & (n[:, 0] <= x1 + 1e-12) & (n[:, 1] >= y0 - 1e-12) & (n[:, 1] <= y1 + 1e-12)
        face = inside & (np.abs(n[:, 2] - zt) < 1e-12)
        assert face.sum() == (4 * order + 1) ** 2  # 4 x 4 cells on the 4 mm die at h0 = 1 mm
        assert r.tj_max[i] == r.T[face].max()
        z_below = np.unique(n[inside & (n[:, 2] < zt - 1e-12), 2])[-1]
        below = inside & (np.abs(n[:, 2] - z_below) < 1e-12)
        if i == 1:  # the unpowered die: the test discriminates (the layer below its face is hotter than the face)
            assert r.T[below].max() > r.tj_max[i] + 5e-3
    assert r.energy_balance <= 1e-9


@pytest.mark.parametrize("order", [1, 2])
def test_weak_robin_coupling_converges_with_the_small_biot_limit(order):
    """Regression (T0205 review: Q2 AMG-CG stalled at h = 50 W/(m2 K)). For h -> 0 the rise is
    T - T_c = P / (h A_b) + psi(x) + O(h), with psi the h-independent solution of the problem whose sink is spread
    uniformly over the bottom. Derivation: integrating the equation gives h int_bottom (T - T_c) = P (the uniform part);
    the rest is a regular expansion in h (Hinch, Perturbation Methods, 1991, ch. 1) whose leading term is the Neumann
    problem for psi with zero bottom mean. So psi = T_mean - T_c - P / (h A_b) over each die must change linearly in h:
    by a factor of 10 less from h = 50 to 5 than from 500 to 50."""
    lay = _toy_layout()
    P, Tc, A_b = [0.6, 0.4], 338.15, lay.baseplate_outline.area
    psi = {}
    for h in (500.0, 50.0, 5.0):
        r = F.solve_layout(lay, P, h, Tc, rule=F.GridRule(h0=1e-3, element_order=order), level=0, constant_k=True)
        assert r.energy_balance <= 1e-9
        psi[h] = r.tj_mean - Tc - sum(P) / (h * A_b)
    assert np.all(psi[5.0] > 0.25) and np.all(psi[5.0] < 0.6)  # a spreading rise of a few tenths of a K
    d1, d2 = np.abs(psi[500.0] - psi[50.0]), np.abs(psi[50.0] - psi[5.0])
    assert np.all(d2 < 1e-3)
    assert np.all((d1 / d2 > 8.0) & (d1 / d2 < 12.0))  # O(h)


def test_q1_to_q2_prolongation_is_exact_for_trilinear_fields():
    """The first coarse level of the Q2 multigrid interpolates Q1 into Q2 exactly: a trilinear function's vertex values
    map to its values at every Q2 node (vertices, edge midpoints, face centres, cell centres) on a mesh with void cells."""
    from skfem.assembly import Dofs
    g = F.layout_grid(_toy_layout(), 1.0, 5000.0, 300.0, F.GridRule(h0=2e-3, element_order=2), 0)
    mesh, _, _ = F._build_mesh(g)
    dofs = Dofs(mesh, F._element(2))
    P = F._q1_to_q2(mesh, dofs)
    X = F._doflocs(mesh, dofs)

    def f(p):
        return 1.0 + 0.3 * p[0] - 2.0 * p[1] + 0.5 * p[2] + 0.7 * p[0] * p[1] - 0.4 * p[1] * p[2] + 0.2 * p[0] * p[1] * p[2]

    assert np.abs(P @ f(mesh.p) - f(X)).max() < 1e-11 * np.abs(f(X)).max()
    assert np.allclose(P.sum(axis=1), 1.0)  # constants are reproduced (the deflated near-null mode)


# ---------------------------------------------------------------------------------------------------------- 1. series
@pytest.mark.parametrize("order", [1, 2])
@pytest.mark.parametrize("by_flux", [False, True])
def test_two_layer_column_series_resistance(order, by_flux):
    """Full-face uniform flux q = P/A on a two-layer column, Robin bottom: T_top = T_c + q (1/h + t1/k1 + t2/k2).
    The piecewise-linear exact solution is in both spaces; the flux enters either as the die source or as the manufactured
    ``flux`` callable on the top face. Means over the top face are the exact Galerkin integral."""
    a = b = 4e-3
    t1, t2, k1, k2, h, Tc, P = 0.4e-3, 0.2e-3, 150.0, 24.0, 2000.0, 300.0, 3.0
    q = P / (a * b)
    exact_top = Tc + q * (1 / h + t1 / k1 + t2 / k2)
    layers = [F.BoxLayer(t1, k1, 2), F.BoxLayer(t2, k2, 1)]
    if by_flux:
        def flux(x, y, z, axis, sign):
            return np.where((axis == 2) & (sign > 0), q, 0.0) * np.ones_like(x)
        r = F.solve_box_stack(a, b, layers, h, Tc, [], h0=a / 2, element_order=order, flux=flux)
        top = r.T[np.isclose(r.nodes[:, 2], t1 + t2)]
        assert np.abs(top - exact_top).max() < 1e-6
        assert r.meta["q_in_boundary_W"] == pytest.approx(P, rel=1e-12) and r.meta["q_in_die_W"] == 0.0
    else:
        r = F.solve_box_stack(a, b, layers, h, Tc, [(0, 0, a, b, P)], h0=a / 2, element_order=order)
        assert abs(r.tj_max[0] - exact_top) < 1e-6
        assert abs(r.tj_mean[0] - exact_top) < 1e-6
        assert r.meta["q_in_die_W"] == P and r.meta["q_in_boundary_W"] == 0.0
    assert r.energy_balance <= 1e-9
    assert r.meta["q_out_W"] == pytest.approx(P, rel=1e-9)


@pytest.mark.parametrize("order", [1, 2])
def test_source_mean_is_the_exact_galerkin_integral(order):
    """A partial source (not the whole top) gives a non-uniform T on its face. ``tj_mean`` must equal the area mean of the
    FE field, integrated here independently: 3x3 Gauss per cell of the point values (exact for a biquadratic per cell)."""
    a, b = 6e-3, 4e-3
    src = (1e-3, 1e-3, 4e-3, 3e-3, 5.0)
    layers = [F.BoxLayer(0.5e-3, 100.0, 2), F.BoxLayer(0.3e-3, 40.0, 1)]
    r = F.solve_box_stack(a, b, layers, 3000.0, 300.0, [src], h0=1e-3, element_order=order, constant_k=True)
    xs, ys = r.meta["xs"], r.meta["ys"]
    xs = xs[(xs >= src[0] - 1e-12) & (xs <= src[2] + 1e-12)]
    ys = ys[(ys >= src[1] - 1e-12) & (ys <= src[3] + 1e-12)]
    g, w = np.polynomial.legendre.leggauss(3)
    ztop = 0.8e-3
    tot = 0.0
    for x0, x1 in zip(xs[:-1], xs[1:], strict=True):
        for y0, y1 in zip(ys[:-1], ys[1:], strict=True):
            X, Y = np.meshgrid(0.5 * (x1 - x0) * (g + 1) + x0, 0.5 * (y1 - y0) * (g + 1) + y0, indexing="ij")
            v = F.point_values(r, np.column_stack([X.ravel(), Y.ravel(), np.full(9, ztop)]))
            tot += 0.25 * (x1 - x0) * (y1 - y0) * float(np.outer(w, w).ravel() @ v)
    mean = tot / ((src[2] - src[0]) * (src[3] - src[1]))
    assert r.tj_mean[0] == pytest.approx(mean, abs=1e-9)
    assert r.tj_max[0] > r.tj_mean[0] + 0.05  # the field is not constant on the face: the test discriminates
    assert r.energy_balance <= 1e-9


# ---------------------------------------------------------------------------------------------------------- 2. k(T)
def test_kirchhoff_column_convergence_orders():
    """1D column, k = k0 (1 + beta (T - T0)), uniform inflow q on top, Robin bottom. Kirchhoff: phi(T) = phi(T_b) + q z, so
    T(z) = T0 + (-1 + sqrt(1 + 2 beta phi/k0)) / beta, T_b = T_c + q/h. Both the lagged-k Picard scheme at Gauss points and
    the end-node values are (super)convergent in 1D, so the discretisation error is measured by the RMS error of the FE
    field at 81 points along the column (Q1: order 2, Q2: order 3) and by the through-thickness mean (a linear functional:
    order 2 for Q1, 4 for Q2 on the observed levels)."""
    k0, beta, T0, t, A, h, Tc, P = 100.0, 6.0e-3, 300.0, 5e-3, 1e-4, 2.0e4, 300.0, 300.0
    q = P / A
    phi_b = k0 * ((Tc + q / h - T0) + 0.5 * beta * (Tc + q / h - T0) ** 2)

    def exact(z):
        return T0 + (-1 + np.sqrt(1 + 2 * beta * (phi_b + q * z) / k0)) / beta

    xg, wg = np.polynomial.legendre.leggauss(30)
    mean_exact = float(np.sum(0.5 * t * wg * exact(0.5 * t * (xg + 1))) / t)
    zs = np.linspace(0.013, 0.987, 81) * t
    g3, w3 = np.polynomial.legendre.leggauss(3)
    out = {}
    for order in (1, 2):
        rms, mean_err = [], []
        for lv in range(4):  # three bisections
            layer = F.BoxLayer(t, lambda T: k0 * (1.0 + beta * (np.asarray(T) - T0)), 1)
            r = F.solve_box_stack(0.01, 0.01, [layer], h, Tc, [(0, 0, 0.01, 0.01, P)], h0=0.01, level=lv,
                                  element_order=order, picard_tol=1e-11)
            assert r.picard_iters > 3 and r.energy_balance < 1e-9
            e = F.point_values(r, np.column_stack([np.full(zs.size, 3e-3), np.full(zs.size, 4e-3), zs])) - exact(zs)
            rms.append(math.sqrt(float(np.mean(e**2))))
            tot, zl = 0.0, np.linspace(0.0, t, 2**lv + 1)
            for z0, z1 in zip(zl[:-1], zl[1:], strict=True):
                v = F.point_values(r, np.column_stack([np.full(3, 3e-3), np.full(3, 4e-3), 0.5 * (z1 - z0) * (g3 + 1) + z0]))
                tot += 0.5 * (z1 - z0) * float(w3 @ v)
            mean_err.append(abs(tot / t - mean_exact))
        out[order] = (_orders(rms), _orders(mean_err), rms)
    assert all(abs(p - 2.0) < 0.1 for p in out[1][0]) and all(abs(p - 2.0) < 0.1 for p in out[1][1])
    assert all(p > 2.85 for p in out[2][0]) and out[2][0][-1] > 2.95  # approaching 3 from below
    assert all(p >= 3.0 for p in out[2][1])
    assert out[2][2][-1] < 1e-2 * out[1][2][-1]  # and Q2 is far more accurate at the same level (200x measured)


# ---------------------------------------------------------------------------------------------------------- 3. quadratic
_C = dict(xx=1.2e6, yy=-0.8e6, zz=2.0e6, xy=1.5e6, xz=-2.2e6, yz=1.1e6, x=-3e3, y=2e3, z=-5e3)  # K/m^2 and K/m


def _u(x, y, z):
    c = _C
    return (330.0 + c["xx"] * x**2 + c["yy"] * y**2 + c["zz"] * z**2 + c["xy"] * x * y + c["xz"] * x * z + c["yz"] * y * z
            + c["x"] * x + c["y"] * y + c["z"] * z)


def _grad_u(x, y, z):
    c = _C
    return (2 * c["xx"] * x + c["xy"] * y + c["xz"] * z + c["x"], 2 * c["yy"] * y + c["xy"] * x + c["yz"] * z + c["y"],
            2 * c["zz"] * z + c["xz"] * x + c["yz"] * y + c["z"])


def _quadratic_case(order: int, level: int):
    a = b = 4e-3
    t, k, h = 2e-3, 100.0, 5000.0
    q = -k * 2 * (_C["xx"] + _C["yy"] + _C["zz"])  # -div(k grad u), constant

    def flux(x, y, z, axis, sign):  # heat into the domain = k grad u . n_out
        return sign * k * _grad_u(x, y, z)[axis]

    def T_inf(x, y):  # outflow at z = 0 is k du/dz = h (u - T_inf)
        z0 = np.zeros_like(x)
        return _u(x, y, z0) - k * _grad_u(x, y, z0)[2] / h

    r = F.solve_box_stack(a, b, [F.BoxLayer(t, k, 1)], h, 330.0, [], h0=a / 2, level=level, element_order=order,
                          source=lambda x, y, z: np.full_like(x, q), flux=flux, T_inf=T_inf, constant_k=True)
    return r, (a, b, t)


def test_quadratic_field_q2_exact_at_every_node_and_q1_second_order():
    """u quadratic in x, y, z with constant k: the matching source, inflow flux k grad u . n and T_inf(x, y) make u the
    exact solution. Q2 contains u, so every node is reproduced to the linear-solver level; Q1 converges at order 2 at a
    fixed node (the top-face centre, a node at every level)."""
    for lv in range(3):
        r, (a, b, t) = _quadratic_case(2, lv)
        assert np.abs(r.T - _u(r.nodes[:, 0], r.nodes[:, 1], r.nodes[:, 2])).max() < 1e-8
        assert r.energy_balance <= 1e-9
        # assembled loads against closed forms (not a tautology, unlike the energy balance): Q_vol = q a b t, and by the
        # divergence theorem the inflow over every face but z = 0 is -Q_vol + int_{z=0} k du/dz dA
        k, q = 100.0, -100.0 * 2 * (_C["xx"] + _C["yy"] + _C["zz"])
        q_bot = k * (_C["xz"] * a**2 * b / 2 + _C["yz"] * a * b**2 / 2 + _C["z"] * a * b)
        assert r.meta["q_in_volume_W"] == pytest.approx(q * a * b * t, rel=1e-12)
        assert r.meta["q_in_boundary_W"] == pytest.approx(-q * a * b * t + q_bot, rel=1e-10)
    errs = []
    for lv in range(4):
        r, (a, b, t) = _quadratic_case(1, lv)
        i = int(np.argmin(np.linalg.norm(r.nodes - np.array([a / 2, b / 2, t]), axis=1)))
        assert np.allclose(r.nodes[i], [a / 2, b / 2, t])
        errs.append(abs(r.T[i] - _u(*r.nodes[i])))
        assert r.energy_balance <= 1e-9
    assert errs[0] > 0.1 and errs[-1] > 1e-3  # a real discretisation error that the data and the Q1 space do not remove
    assert all(abs(p - 2.0) < 0.05 for p in _orders(errs))


# ---------------------------------------------------------------------------------------------------------- 4. interface
def _two_region_case():
    """Polynomial field p in the lower layer (k1) and p + c(x, y) (z - z_i) above (k2), c = (k1/k2 - 1) dp/dz at z_i:
    T and k dT/dz are continuous across z_i. Source -k_j Laplace T_j and face fluxes k_j dT_j/dn are exact polynomials."""
    x, y, z = sp.symbols("x y z")
    a = b = 4e-3
    t1, t2, k1, k2, h = 1.0e-3, 1.0e-3, 150.0, 24.0, 4000.0
    X, Y, Zs = x / a, y / b, z / (t1 + t2)
    p = (330 + 8 * X + 5 * Y + 12 * Zs + 6 * X**2 - 4 * Y * Zs + 7 * X**3 * Y + 5 * Zs**4 - 3 * X**2 * Zs**2 + 2 * Y**3)
    c = (k1 / k2 - 1) * sp.diff(p, z).subs(z, t1)
    T = [p, p + c * (z - t1)]
    k = [k1, k2]
    src = [-k[j] * sum(sp.diff(T[j], v, 2) for v in (x, y, z)) for j in range(2)]
    fl = [[k[j] * sp.diff(T[j], v) for v in (x, y, z)] for j in range(2)]
    lam = lambda e: sp.lambdify((x, y, z), e, "numpy")  # noqa: E731
    Tf = [lam(e) for e in T]
    srcf = [lam(e) for e in src]
    flf = [[lam(e) for e in row] for row in fl]
    zi = t1

    def layer(zz):
        return zz > zi

    def source(xx, yy, zz):
        m = layer(zz)
        return np.where(m, srcf[1](xx, yy, zz), srcf[0](xx, yy, zz)) * np.ones_like(xx)

    def flux(xx, yy, zz, axis, sign):
        if axis == 2:  # only the top face is a boundary face besides the Robin bottom
            assert sign > 0 and np.allclose(zz, t1 + t2)
            return sign * flf[1][2](xx, yy, zz) * np.ones_like(xx)
        m = layer(zz)
        return sign * np.where(m, flf[1][axis](xx, yy, zz), flf[0][axis](xx, yy, zz)) * np.ones_like(xx)

    def T_inf(xx, yy):
        z0 = np.zeros_like(xx)
        return Tf[0](xx, yy, z0) - flf[0][2](xx, yy, z0) / h

    def T_exact(xx, yy, zz):
        return np.where(layer(zz), Tf[1](xx, yy, zz), Tf[0](xx, yy, zz))

    # exact integrals of the data (sympy, exact rational arithmetic on the polynomials)
    vol = sum(sp.integrate(src[j], (x, 0, a), (y, 0, b), (z, [0, t1][j], [t1, t1 + t2][j])) for j in range(2))
    bnd = 0
    for j in range(2):
        zr = ([0, t1], [t1, t1 + t2])[j]
        bnd += sp.integrate(-fl[j][0].subs(x, 0), (y, 0, b), (z, *zr)) + sp.integrate(fl[j][0].subs(x, a), (y, 0, b), (z, *zr))
        bnd += sp.integrate(-fl[j][1].subs(y, 0), (x, 0, a), (z, *zr)) + sp.integrate(fl[j][1].subs(y, b), (x, 0, a), (z, *zr))
    bnd += sp.integrate(fl[1][2].subs(z, t1 + t2), (x, 0, a), (y, 0, b))
    layers = [F.BoxLayer(t1, k1, 1), F.BoxLayer(t2, k2, 1)]
    return dict(a=a, b=b, h=h, layers=layers, source=source, flux=flux, T_inf=T_inf, T_exact=T_exact,
                Q_vol=float(vol), Q_bnd=float(bnd))


def test_two_region_interface_energy_balance_and_convergence():
    """Two conductivities (150 and 24 W/(m K)) with matched T and normal flux at the interface. (a) The assembled Q_in
    equals the exactly integrated source and boundary inflow, and Q_out closes it to 1e-9; (b) the nodal RMS error
    converges at the element order (Q1: 2, Q2: >= 3 since the field is a quartic polynomial that Q2 cannot represent)."""
    case = _two_region_case()
    assert abs(case["Q_vol"]) > 0.1 and abs(case["Q_bnd"]) > 0.1  # both contribute
    rms = {1: [], 2: []}
    for order in (1, 2):
        for lv in range(3):
            r = F.solve_box_stack(case["a"], case["b"], case["layers"], case["h"], 330.0, [], h0=case["a"] / 2, level=lv,
                                  element_order=order, constant_k=True, source=case["source"], flux=case["flux"],
                                  T_inf=case["T_inf"])
            Q = case["Q_vol"] + case["Q_bnd"]
            assert r.meta["q_in_volume_W"] == pytest.approx(case["Q_vol"], rel=1e-9)
            assert r.meta["q_in_boundary_W"] == pytest.approx(case["Q_bnd"], rel=1e-9)
            assert abs(r.meta["q_out_W"] / Q - 1.0) <= 1e-9
            assert r.energy_balance <= 1e-9
            e = r.T - case["T_exact"](r.nodes[:, 0], r.nodes[:, 1], r.nodes[:, 2])
            rms[order].append(math.sqrt(float(np.mean(e**2))))
    assert all(abs(p - 2.0) < 0.35 for p in _orders(rms[1]))
    assert all(p > 2.7 for p in _orders(rms[2]))
    assert rms[2][-1] < 0.05 * rms[1][-1]


# ---------------------------------------------------------------------------------------------------------- 5. O006 MMS
def _o006():
    """e006_run (for ``mms_layout``) and e006_mms (``build_case``) imported by path; research code, never modified."""
    path = ROOT / "experiments" / "runners" / "e006_run.py"
    spec = importlib.util.spec_from_file_location("e006_run_for_t0205", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _mms_levels(order: int, levels=(0, 1)):
    R = _o006()
    case = R.MMS.build_case()
    ref = json.loads((ROOT / "research" / "e006_refs" / "mms_values.json").read_text())
    pts = ref["payload"]["reported_points"]
    q_ref = -ref["balance"]["robin_W"]
    lay = R.mms_layout()
    rule = F.GridRule(h0=2.0e-3, element_order=order)
    out = []
    for lv in levels:
        r = F.solve_layout(lay, 0.0, case.h, 340.0, rule=rule, level=lv, source=case.source, flux=case.flux,
                           T_inf=case.T_inf, picard_tol=1e-6)
        err = {}
        for p in pts:
            if p["kind"] == "area_mean":
                v = r.tj_mean[0]  # exact Galerkin mean over the die top
            else:  # 'point' and the true maximum's location 'max'
                v = F.point_values(r, np.array([[p["x"], p["y"], p["z"]]]))[0]
            err[p["id"]] = v - p["T_K"]
        out.append((r, err, q_ref))
    return out


def _check_mms(order: int, levels):
    res = _mms_levels(order, levels)
    for r, _, q_ref in res:
        assert r.energy_balance <= 1e-6  # Q_in assembled from the source, face fluxes and the Robin data
        assert abs(r.meta["q_out_W"] / q_ref - 1.0) <= 1e-6  # and equal to the frozen, independently integrated Q_out
        assert r.meta["q_in_volume_W"] != 0.0 and r.meta["q_in_boundary_W"] != 0.0 and r.meta["q_in_die_W"] == 0.0
        assert r.picard_residual < 1e-6
    linf = [max(abs(v) for v in e.values()) for _, e, _ in res]
    assert all(p >= 1.5 for p in _orders(linf)), linf
    assert linf[-1] < 0.1 * (3.0 if order == 1 else 1.0)  # K, against a 60-110 K field range
    return res


def test_o006_manufactured_case_q1_coarse_levels():
    """O006's 3D manufactured solution (default stack, patterned top copper, k(T) varying by >= 30 % in the ceramic) through
    the production mesh and assembly code. The error at the frozen points (Linf over the nine) falls from level 0 to 1 at
    an observed order >= 1.5."""
    _check_mms(1, (0, 1))


def test_o006_manufactured_case_q2_coarse_levels():
    res = _check_mms(2, (0, 1))
    q1 = _mms_levels(1, (1,))[0][1]  # Q2 at level 0 (same dof count as Q1 at level 1) is at least as accurate
    assert max(abs(v) for v in res[0][1].values()) < max(abs(v) for v in q1.values())
