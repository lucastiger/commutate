"""Tests of the scikit-fem thermal cross-check (``moduleforge.solvers.thermal_fem``, docs/thermal_model.md)."""
from __future__ import annotations

import math

import numpy as np
import pytest
import shapely
from shapely.geometry import box

from moduleforge.generate.halfbridge import generate_layouts
from moduleforge.geometry.layout import Die, Layout, Trace
from moduleforge.geometry.stack import default_dbc_stack
from moduleforge.solvers import thermal_fem as F

TC = 338.15


def test_1d_slab_series_resistance():
    """Source over the whole top face: T_top = T_c + P (sum t/(k A) + 1/(h A)) (exact for linear elements)."""
    a, b, h, P = 0.02, 0.01, 1000.0, 100.0
    A = a * b
    layers = [F.BoxLayer(1e-3, 100.0, 2), F.BoxLayer(2e-3, 50.0, 2), F.BoxLayer(0.5e-3, 10.0, 1)]
    r = F.solve_box_stack(a, b, layers, h, 300.0, [(0, 0, a, b, P)], h0=0.01, constant_k=True)
    exact = 300.0 + P * (1e-3 / (100 * A) + 2e-3 / (50 * A) + 0.5e-3 / (10 * A) + 1 / (h * A))
    assert r.tj_max[0] == pytest.approx(exact, rel=1e-10)
    assert r.tj_mean[0] == pytest.approx(exact, rel=1e-10)
    assert r.energy_balance < 1e-9


def test_kirchhoff_1d_k_of_T():
    """1D k(T) = k0 (1 + beta (T - T0)): Kirchhoff theta = T + beta/2 (T-T0)^2 is linear in z (Carslaw & Jaeger)."""
    k0, beta, T0, t, A, h, Tc, P = 100.0, 2.0e-3, 300.0, 5e-3, 1e-4, 2.0e4, 300.0, 50.0
    q = P / A
    Tb = Tc + q / h  # bottom temperature from the convective condition (flux q leaves)
    # k0 (T - T0 + beta/2 (T-T0)^2) is linear in z: flux q = [Phi(Ttop) - Phi(Tb)] / t
    phi_b = k0 * ((Tb - T0) + 0.5 * beta * (Tb - T0) ** 2)
    phi_t = phi_b + q * t
    x = (-1 + math.sqrt(1 + 2 * beta * phi_t / k0)) / beta  # solve (T-T0) + beta/2 (T-T0)^2 = phi_t / k0
    exact = T0 + x
    layer = F.BoxLayer(t, lambda T: k0 * (1.0 + beta * (np.asarray(T) - T0)), 8)
    r = F.solve_box_stack(0.01, 0.01, [layer], h, Tc, [(0, 0, 0.01, 0.01, P)], h0=0.01)
    assert r.tj_max[0] == pytest.approx(exact, abs=2e-3)
    assert r.picard_iters > 2
    const = F.solve_box_stack(0.01, 0.01, [layer], h, Tc, [(0, 0, 0.01, 0.01, P)], h0=0.01, constant_k=True)
    assert abs(const.tj_max[0] - exact) > 0.05  # constant k (at T_c) is a different answer: the test discriminates


def test_box_two_sources_symmetry_and_balance():
    """Two equal sources placed mirror-symmetrically give equal Tj; the energy balance closes."""
    a, b = 0.02, 0.01
    layers = [F.BoxLayer(1e-3, 150.0, 2), F.BoxLayer(0.3e-3, 30.0, 1)]
    src = [(2e-3, 3e-3, 6e-3, 7e-3, 20.0), (a - 6e-3, 3e-3, a - 2e-3, 7e-3, 20.0)]
    r = F.solve_box_stack(a, b, layers, 2000.0, 300.0, src, h0=1e-3, constant_k=True)
    assert r.tj_max[0] == pytest.approx(r.tj_max[1], rel=1e-12)
    assert r.tj_mean[0] == pytest.approx(r.tj_mean[1], rel=1e-12)
    assert r.energy_balance < 1e-9
    assert r.tj_max[0] > r.tj_mean[0] > 300.0


def test_gci_formula():
    """Roache GCI on a sequence with known order: f(h) = f0 + C h^2 gives p_obs = 2 and GCI = 1.25 |f2-f1|/(r^2-1)."""
    f = [1.0 + 3.0 * h**2 for h in (0.25, 0.5, 1.0)]  # finest, middle, coarsest (r = 2)
    c, p = F.gci(f)
    assert p == pytest.approx(2.0, abs=1e-12)
    assert c == pytest.approx(1.25 * abs(f[1] - f[0]) / 3.0, rel=1e-12)
    assert c >= 3.0 * 0.25**2  # the GCI bounds the true error of the finest value (C h^2 = 0.1875)
    # oscillatory: Fs = 3, p = 2
    c2, p2 = F.gci([1.0, 1.2, 1.1])
    assert math.isnan(p2)
    assert c2 == pytest.approx(3.0 * 0.2 / 3.0, rel=1e-12)
    # p_obs outside [1.5, 2.5]: Fs = 3, p = 2
    f1 = [1.0 + h**1.0 for h in (0.25, 0.5, 1.0)]
    c3, p3 = F.gci(f1)
    assert p3 == pytest.approx(1.0, abs=1e-12)
    assert c3 == pytest.approx(3.0 * 0.25 / 3.0, rel=1e-12)
    # p_obs = 3 -> Fs = 3, p = 2 as well
    c4, p4 = F.gci([1.0 + h**3 for h in (0.25, 0.5, 1.0)])
    assert p4 == pytest.approx(3.0, abs=1e-12)
    assert c4 == pytest.approx(3.0 * (0.5**3 - 0.25**3) / 3.0, rel=1e-12)


# ------------------------------------------------------------------------------------------------ layout mode
def _toy_layout(mirror: bool = False) -> Layout:
    """Two dies on one rectangular trace, mirror-symmetric about x = 10 mm; small and on a 1 mm grid."""
    outline = box(0.0, 0.0, 20e-3, 10e-3)
    trace = box(2e-3, 2e-3, 18e-3, 8e-3)
    d1 = Die(6e-3, 5e-3, 4e-3, 4e-3, "HS", {})
    d2 = Die(14e-3, 5e-3, 4e-3, 4e-3, "LS", {})
    return Layout("toy", 1, outline, [Trace("DC+", trace)], [d1, d2], [], {}, box(-3e-3, -3e-3, 23e-3, 13e-3),
                  default_dbc_stack())


COARSE = F.GridRule(h0=2.0e-3)


def test_layout_energy_balance_and_mirror_symmetry():
    lay = _toy_layout()
    r = F.solve_layout(lay, 20.0, 5000.0, TC, rule=COARSE, level=0)
    assert r.energy_balance < 1e-8
    assert r.picard_residual < 1e-4
    assert r.tj_max[0] == pytest.approx(r.tj_max[1], abs=1e-9)  # mirror about x = 10 mm
    assert r.tj_mean[0] == pytest.approx(r.tj_mean[1], abs=1e-9)
    assert r.tj_max[0] >= r.tj_mean[0] > TC + 1.0
    # unequal power breaks the symmetry in the right direction
    r2 = F.solve_layout(lay, [30.0, 10.0], 5000.0, TC, rule=COARSE, level=0)
    assert r2.tj_max[0] > r2.tj_max[1]
    assert r2.energy_balance < 1e-8


def test_layout_total_rise_bounded_by_1d_estimates():
    """Tj rise lies between 1D conduction through the full die-area column (lower) and a column of the whole
    substrate-area for the convective part (sanity bounds from series resistance)."""
    lay = _toy_layout()
    P, h = 20.0, 5000.0
    r = F.solve_layout(lay, P, h, TC, rule=COARSE, level=0, constant_k=True)
    st = lay.stack
    A_die = 4e-3 * 4e-3
    below = sum(la.thickness / la.k for la in st.layers) + st.die_attach.thickness / st.die_attach.k + \
        st.die.thickness / st.die.k
    upper = P * below / A_die + 2 * P / (h * 26e-3 * 16e-3)  # no lateral spreading in the stack; both dies' heat via baseplate
    lower = 2 * P / (h * 26e-3 * 16e-3)  # convective sink alone
    rise = r.tj_max.max() - TC
    assert lower < rise < upper


def test_mesh_conformity_die_and_copper_edges():
    """Every die, die-attach, copper, backside-Cu and baseplate edge is a mesh line, and the cell volumes of each
    region add up exactly to the area of the region times its thickness."""
    layouts = generate_layouts(3, 20261101)
    st = layouts[0].stack
    for lay in layouts[:2]:
        g = F.layout_grid(lay, 10.0, 5000.0, TC, COARSE, 0)
        xs, ys = g.x, g.y
        back = lay.outline.buffer(-lay.backside_inset, join_style="mitre")
        edges_x, edges_y = [], []
        for poly in [lay.baseplate_outline, lay.outline, back] + [t.polygon for t in lay.traces]:
            for rng in (poly.exterior, *poly.interiors):
                edges_x += [c[0] for c in rng.coords]
                edges_y += [c[1] for c in rng.coords]
        for d in lay.dies:
            edges_x += [d.bounds[0], d.bounds[2]]
            edges_y += [d.bounds[1], d.bounds[3]]
        assert all(np.min(np.abs(xs - e)) < 1e-12 for e in edges_x)
        assert all(np.min(np.abs(ys - e)) < 1e-12 for e in edges_y)
        # z lines at every interface and die top
        zt = [st.z_top(n) for n in ("baseplate", "solder", "backside_cu", "ceramic", "top_cu")]
        for d in lay.dies:
            zb = st.z_top("top_cu") + d.attach_thickness
            zt += [zb, zb + d.thickness]
        assert all(np.min(np.abs(g.z - z)) < 1e-12 for z in zt)
        # region volumes from the cell map equal polygon area x thickness (cells conform: no partial cells)
        dx, dy, dz = np.diff(g.x), np.diff(g.y), np.diff(g.z)
        vol = dx[:, None, None] * dy[None, :, None] * dz[None, None, :]
        traces = F.layout_polygons_for_tests(lay)
        expect = {
            0: lay.baseplate_outline.area * st.layer("baseplate").thickness,
            1: back.area * st.layer("solder").thickness,
            2: back.area * st.layer("backside_cu").thickness,
            3: lay.outline.area * st.layer("ceramic").thickness,
            4: traces.area * st.layer("top_cu").thickness,
            5: sum(d.box.area * d.attach_thickness for d in lay.dies),
            6: sum(d.box.area * d.thickness for d in lay.dies),
        }
        for m, v in expect.items():
            assert vol[g.mat == m].sum() == pytest.approx(v, rel=1e-9), m
        # void: nothing meshed outside the trace union in the top-Cu slab
        k_top = np.nonzero(np.abs(0.5 * (g.z[1:] + g.z[:-1]) - 0.5 * (zt[3] + zt[4])) < 1e-9)[0][0]
        X, Y = np.meshgrid(0.5 * (xs[1:] + xs[:-1]), 0.5 * (ys[1:] + ys[:-1]), indexing="ij")
        gap = ~shapely.contains_xy(traces, X.ravel(), Y.ravel()).reshape(X.shape)
        assert np.all(g.mat[:, :, k_top][gap] < 0)


def test_refinement_ratio_is_constant():
    """Cells per interval double exactly from level to level (r = 2) in x, y and z."""
    lay = _toy_layout()
    g0, g1, g2 = (F.layout_grid(lay, 1.0, 1.0, TC, COARSE, lv) for lv in (0, 1, 2))
    for ax in ("x", "y", "z"):
        n = [getattr(g, ax).size - 1 for g in (g0, g1, g2)]
        assert n[1] == 2 * n[0] and n[2] == 2 * n[1]


def test_lateral_only_refinement_keeps_z_fixed():
    lay = _toy_layout()
    rule = F.GridRule(h0=2.0e-3, zrefine=False)
    g0, g1, g2 = (F.layout_grid(lay, 1.0, 1.0, TC, rule, lv) for lv in (0, 1, 2))
    assert g0.z.size == g1.z.size == g2.z.size
    assert g1.x.size - 1 == 2 * (g0.x.size - 1) and g2.y.size - 1 == 4 * (g0.y.size - 1)


def test_near_die_size_multipliers_keep_ratio_and_conformity():
    lay = _toy_layout()
    rule = F.GridRule(h0=1.0e-3, zrefine=False, near_margin=1.0e-3)
    gs = [F.layout_grid(lay, 1.0, 1.0, TC, rule, lv) for lv in (0, 1, 2)]
    for ax in ("x", "y"):
        n = [getattr(g, ax).size - 1 for g in gs]
        assert n[1] == 2 * n[0] and n[2] == 2 * n[1]
    uniform = F.layout_grid(lay, 1.0, 1.0, TC, F.GridRule(h0=1.0e-3, zrefine=False), 0)
    assert gs[0].x.size < uniform.x.size  # coarsened away from the dies
    # every die edge is still a grid line and the die cells are at the finest size
    for d in lay.dies:
        for e in (d.bounds[0], d.bounds[2]):
            assert np.min(np.abs(gs[0].x - e)) < 1e-12
        inside = gs[0].x[(gs[0].x >= d.bounds[0] - 1e-12) & (gs[0].x <= d.bounds[2] + 1e-12)]
        assert np.diff(inside).max() <= 1.0e-3 + 1e-12


def test_layout_k_of_T_changes_result_and_converges():
    lay = _toy_layout()
    rk = F.solve_layout(lay, 40.0, 5000.0, TC, rule=COARSE, level=0)
    rc = F.solve_layout(lay, 40.0, 5000.0, TC, rule=COARSE, level=0, constant_k=True)
    assert rk.picard_iters >= 3
    assert abs(rk.tj_max[0] - rc.tj_max[0]) > 0.1
    assert rk.energy_balance < 1e-8


def test_dof_numbering_matches_nodes_and_volume():
    """The direct facet assembly assumes basis dof i == mesh node i; the active-cell volumes add up to the mesh volume."""
    from skfem import Basis, ElementHex1

    g = F.layout_grid(_toy_layout(), 1.0, 1.0, TC, COARSE, 0)
    mesh, emat, dof_of = F._build_mesh(g)
    basis = Basis(mesh, ElementHex1(), intorder=2)
    assert np.allclose(basis.doflocs, mesh.p)
    vol = np.diff(g.x)[:, None, None] * np.diff(g.y)[None, :, None] * np.diff(g.z)[None, None, :]
    from skfem import LinearForm

    @LinearForm
    def f(v, w):
        return v

    assert f.assemble(basis).sum() == pytest.approx(vol[g.mat >= 0].sum() * F.MM**3, rel=1e-12)
    assert emat.size == int((g.mat >= 0).sum())
