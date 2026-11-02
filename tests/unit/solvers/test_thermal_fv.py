"""Tests of the steady thermal FV core against closed forms, symmetry, conservation and observed order."""
from __future__ import annotations

import numpy as np
import pytest

from moduleforge.geometry.stack import Layer, default_dbc_stack
from moduleforge.solvers import thermal_fv
from moduleforge.solvers.thermal_fv import SurfaceField, solve_steady


def test_multilayer_slab_series_resistance():
    # Incropera et al., Sec. 3.1.3: T_top - T_inf = q'' (1/h + sum t_i / k_i) for 1-D flow through a composite wall.
    t = np.array([3e-3, 0.1e-3, 0.3e-3, 0.38e-3, 0.3e-3])
    k = np.array([385.0, 58.0, 385.0, 24.0, 385.0])
    h, Tinf, q = 5000.0, 300.0, 2.0e5
    z = np.concatenate([[0.0], np.cumsum(t)])
    zl = np.concatenate([np.linspace(z[i], z[i + 1], n + 1)[:-1] for i, n in enumerate([4, 2, 2, 3, 2])] + [[z[-1]]])
    nzc = len(zl) - 1
    layer_of = np.searchsorted(z, 0.5 * (zl[:-1] + zl[1:])) - 1
    mat = np.broadcast_to(layer_of, (3, 2, nzc)).copy()
    x, y = np.array([0.0, 1e-3, 3e-3, 4e-3]), np.array([0.0, 2e-3, 3e-3])
    res = solve_steady(x, y, zl, mat, list(k), h=h, T_inf=Tinf, flux={(2, 1): q})
    exact_top = Tinf + q * (1 / h + np.sum(t / k))
    assert abs(res.surface(2e-3, 1e-3) - exact_top) / (exact_top - Tinf) < 1e-10
    zc = 0.5 * (zl[:-1] + zl[1:])
    # piecewise-linear exact profile at cell centres
    r_below = np.array([1 / h + np.sum(t[:m] / k[:m]) + (zc[c] - z[m]) / k[m] for c, m in enumerate(layer_of)])
    assert np.max(np.abs(res.T[0, 0, :] - (Tinf + q * r_below))) / (exact_top - Tinf) < 1e-10
    assert res.meta["picard_iters"] == 1


def _smooth_problem(N, mirror=False):
    """Manufactured 3-D field with adiabatic sides, Robin bottom, flux top; returns max-norm cell error."""
    Lx, Ly, Lz, k, h = 3e-3, 2e-3, 1e-3, 20.0, 800.0

    def grid(L, n, amp):
        s = np.linspace(0, 1, n + 1)
        return L * (s + amp * np.sin(2 * np.pi * s) / (2 * np.pi))  # smooth, monotone (amp < 1)

    x, y, z = grid(Lx, N, 0.4), grid(Ly, N, -0.3), grid(Lz, N, 0.35)

    def T(x, y, z):
        return 300.0 + 8.0 * np.cos(np.pi * x / Lx) * np.cos(2 * np.pi * y / Ly) * (1.0 + 0.5 * np.sin(2 * z / Lz) + z / Lz)

    def dTdz(x, y, z):
        return 8.0 * np.cos(np.pi * x / Lx) * np.cos(2 * np.pi * y / Ly) * (np.cos(2 * z / Lz) / Lz + 1 / Lz)

    def lap(x, y, z):
        g = 1.0 + 0.5 * np.sin(2 * z / Lz) + z / Lz
        gzz = -2.0 * np.sin(2 * z / Lz) / Lz**2
        cx = np.cos(np.pi * x / Lx) * np.cos(2 * np.pi * y / Ly)
        return 8.0 * cx * (-(np.pi / Lx) ** 2 - (2 * np.pi / Ly) ** 2) * g + 8.0 * cx * gzz

    mat = np.zeros((N, N, N), dtype=int)
    res = solve_steady(x, y, z, mat, [k], h=h, source=lambda x, y, z: -k * lap(x, y, z),
                       T_inf=lambda x, y: T(x, y, 0 * x) - k * dTdz(x, y, 0 * x) / h,
                       flux={(2, 1): lambda x, y, z: k * dTdz(x, y, z)})
    xc, yc, zc = (0.5 * (a[:-1] + a[1:]) for a in (x, y, z))
    exact = T(xc[:, None, None], yc[None, :, None], zc[None, None, :])
    return np.max(np.abs(res.T - exact)), res


def test_observed_order_smooth_3d_nonuniform():
    errs = [_smooth_problem(N)[0] for N in (16, 32, 64)]
    orders = [np.log2(errs[i] / errs[i + 1]) for i in range(2)]
    assert all(1.8 <= p <= 2.2 for p in orders), (errs, orders)


def test_energy_balance_heterogeneous_with_voids_and_k_of_T():
    rng = np.random.default_rng(7)
    x = np.cumsum(np.r_[0, rng.uniform(0.5e-3, 2e-3, 14)])
    y = np.cumsum(np.r_[0, rng.uniform(0.5e-3, 2e-3, 12)])
    stack = default_dbc_stack()
    z = np.array([0, 1e-3, 3e-3, 3.1e-3, 3.4e-3, 3.78e-3, 4.08e-3, 4.13e-3, 4.31e-3])
    layer_idx = [0, 0, 1, 2, 3, 4, 5, 6]  # baseplate, baseplate, solder, cu, ceramic, cu, die_attach, die
    layers = [stack.layer("baseplate"), stack.layer("solder"), stack.layer("backside_cu"), stack.layer("ceramic"),
              stack.layer("top_cu"), stack.die_attach, stack.die]
    mat = np.broadcast_to(np.array(layer_idx), (14, 12, 8)).copy()
    mat[:4, :, 6:] = -1  # void above part of the top copper
    mat[:, :, 6:][np.s_[8:, :, :]] = -1
    res = solve_steady(x, y, z, mat, layers, h=5000.0, T_inf=300.0,
                       flux={(2, 1): lambda x, y, z: 1e6 * ((x > 5e-3) & (x < 9e-3)), (0, -1): 1e3},
                       source=lambda x, y, z: 2e8 * (z > 4.13e-3))
    assert res.meta["energy_balance"] <= 1e-9
    assert res.meta["picard_iters"] > 1
    assert res.meta["picard_dT"] < 1e-4
    assert res.meta["linear_residual"] <= 1e-11
    assert np.isnan(res.T[:4, :, 6:]).all()


def test_mirror_symmetry():
    xm = np.array([0, 1, 2.5, 3, 5, 6, 7.5, 8, 9])  # mm, exact in binary; the mirror line is x = 4.5 mm
    x = np.unique(np.concatenate([xm, 9.0 - xm])) * 1e-3
    y = np.array([0, 1.5, 2, 4, 5.5, 6]) * 1e-3
    z = np.array([0, 1, 1.5, 2.5, 3]) * 1e-3
    nx = len(x) - 1
    mat = np.zeros((nx, len(y) - 1, len(z) - 1), dtype=int)
    mat[:, :, 2:] = 1
    mid = 4.5e-3
    res = solve_steady(x, y, z, mat, [50.0, Layer("a", "Cu", 1e-3, 1.0, 385.0)], h=3000.0, T_inf=310.0,
                       flux={(2, 1): lambda x, y, z: 1e6 * (np.abs(x - mid) > 2e-3) * (np.abs(x - mid) < 4e-3)})
    assert res.meta["picard_iters"] > 1
    assert np.max(np.abs(res.T - res.T[::-1, :, :])) < 1e-9
    assert res.T.max() - res.T.min() > 1.0  # nontrivial field


def test_kirchhoff_transform_1d_sic_slab():
    # Kirchhoff theta = int k dT.  For 4H-SiC k = k0 (T/300)^-1.49 (geometry.stack), theta(T) =
    # -k0*300/0.49 * (T/300)^-0.49; steady 1-D flux q makes theta linear in z (Bagnall et al., IEEE TCPMT 4(3), 2014).
    sic = Layer("die", "4H-SiC", 2e-3, 0.0, 370.0)
    k0, h, Tinf, q, L = 370.0, 1e5, 300.0, 1.0e7, 2e-3
    Tb = Tinf + q / h  # bottom face temperature (Robin)

    def theta(T):
        return -k0 * 300.0 / 0.49 * (T / 300.0) ** -0.49

    def inv(th):
        return 300.0 * (-th * 0.49 / (k0 * 300.0)) ** (-1 / 0.49)

    exact_top = inv(theta(Tb) + q * L)
    errs = []
    for nz in (25, 50, 100):
        z = np.linspace(0, L, nz + 1)
        res = solve_steady([0, 1e-3], [0, 1e-3], z, np.zeros((1, 1, nz), int), [sic], h=h, T_inf=Tinf, flux={(2, 1): q})
        errs.append(abs(res.surface(5e-4, 5e-4) - exact_top))
        assert res.meta["picard_iters"] > 1
    # tolerance = Picard stop (1e-4 K, error of a contraction <= a few times that) + O(h^2) discretisation error
    assert errs[2] < 3e-4 + 0.3 * errs[0] * (25 / 100) ** 2 + 1e-12
    assert errs[2] < 1e-3
    assert errs[1] < errs[0]
    assert exact_top - Tinf > 50.0  # non-trivial: k varies by > 10 % over the slab


def test_void_faces_adiabatic():
    # column 1 is void: column 2 is hydraulically cut off from the heated column 0 and stays at T_inf exactly
    x, y, z = np.array([0, 1, 2, 3]) * 1e-3, np.array([0, 1]) * 1e-3, np.array([0, 0.5, 1.0]) * 1e-3
    mat = np.zeros((3, 1, 2), int)
    mat[1] = -1
    res = solve_steady(x, y, z, mat, [100.0], h=1000.0, T_inf=300.0, source=lambda x, y, z: 1e8 * (x < 1e-3))
    assert np.allclose(res.T[2], 300.0, atol=1e-12)
    assert np.isnan(res.T[1]).all()
    assert res.T[0].min() > 300.0
    assert res.meta["energy_balance"] < 1e-12

    # prescribed flux on a void-bounding face: top cell void; flux through the +z face of cell 1 is 1-D exact
    mat = np.array([0, 0, -1]).reshape(1, 1, 3)
    zz = np.array([0, 1, 2, 3]) * 1e-3
    q, k, h = 1e5, 40.0, 2000.0
    res = solve_steady([0, 1e-3], [0, 1e-3], zz, mat, [k], h=h, T_inf=300.0, flux={(2, 1): q})
    assert abs(res.surface(5e-4, 5e-4) - (300.0 + q * (1 / h + 2e-3 / k))) < 1e-9
    # no flux specified: that face is adiabatic, so the field is uniform at T_inf
    res = solve_steady([0, 1e-3], [0, 1e-3], zz, mat, [k], h=h, T_inf=300.0)
    assert np.allclose(res.T[0, 0, :2], 300.0, atol=1e-12)


def test_volumetric_gauss_integration_and_energy():
    # integral of a degree-5 polynomial over the box is exact with 3-point Gauss-Legendre per direction
    x, y, z = np.array([0, 1, 3]) * 1e-3, np.array([0, 2, 3]) * 1e-3, np.array([0, 1, 2]) * 1e-3
    f = lambda x, y, z: 1e9 * (x / 1e-3) ** 5 + 2e9 * (y / 1e-3) ** 3 * (z / 1e-3) ** 2  # noqa: E731
    res = solve_steady(x, y, z, np.zeros((2, 2, 2), int), [10.0], h=1e3, T_inf=300.0, source=f)
    ex = 1e9 * (3.0**6 / 6.0) * 3.0 * 2.0 + 2e9 * (3.0**4 / 4.0) * (2.0**3 / 3.0) * 3.0
    exact = ex * 1e-9  # mm^3 -> m^3
    assert abs(res.meta["q_in"] - exact) / exact < 1e-12
    assert res.meta["energy_balance"] <= 1e-9


def test_surface_field_bilinear_interpolation_and_stats():
    x, y = np.array([0.0, 1.0, 3.0, 4.0]), np.array([0.0, 2.0, 3.0])
    xc, yc = 0.5 * (x[:-1] + x[1:]), 0.5 * (y[:-1] + y[1:])
    f = lambda X, Y: 2.0 + 3.0 * X - 1.5 * Y + 0.7 * X * Y  # noqa: E731  bilinear
    sf = SurfaceField(x, y, f(xc[:, None], yc[None, :]), np.zeros((3, 2)))
    px, py = np.array([0.0, 0.2, 1.7, 2.9, 4.0]), np.array([0.0, 1.1, 2.2, 3.0, 0.4])
    assert np.allclose(sf(px, py), f(px, py), atol=1e-12)  # exact, including linear extrapolation in edge half cells
    x0, x1, y0, y1 = 0.3, 3.6, 0.2, 2.7
    mean, mx = sf.mean_max(x0, x1, y0, y1)
    ex_mean = (2.0 * (x1 - x0) * (y1 - y0) + 1.5 * (x1**2 - x0**2) * (y1 - y0) - 0.75 * (x1 - x0) * (y1**2 - y0**2)
               + 0.7 * 0.25 * (x1**2 - x0**2) * (y1**2 - y0**2)) / ((x1 - x0) * (y1 - y0))
    assert abs(mean - ex_mean) < 1e-12
    assert abs(mx - max(f(a, b) for a in (x0, x1) for b in (y0, y1))) < 1e-12
    with pytest.raises(ValueError):
        sf(5.0, 1.0)


def test_surface_levels_and_void_columns():
    # die top (higher level) next to copper top, plus a void column: stencil nodes on another level are replaced
    sf = SurfaceField(np.array([0.0, 1.0, 2.0, 3.0]), np.array([0.0, 1.0]), np.array([[10.0], [20.0], [np.nan]]),
                      np.array([[1.0], [2.0], [np.nan]]))
    assert sf(0.9, 0.5) == pytest.approx(10.0)  # does not blend with the column at another level
    assert sf(1.5, 0.5) == pytest.approx(20.0)
    assert np.isnan(sf(2.5, 0.5))
    mean, mx = sf.mean_max(0.0, 3.0, 0.0, 1.0)
    assert mean == pytest.approx(15.0) and mx == pytest.approx(20.0)  # void part excluded


def test_input_validation():
    z = np.array([0, 1e-3])
    one = np.zeros((1, 1, 1), int)
    with pytest.raises(ValueError, match="h must be positive"):
        solve_steady([0, 1e-3], [0, 1e-3], z, one, [10.0], h=0.0, T_inf=300.0)
    with pytest.raises(ValueError, match="n_gauss"):
        solve_steady([0, 1e-3], [0, 1e-3], z, one, [10.0], h=10.0, T_inf=300.0, n_gauss=2)
    for key in [(2, 0), (3, 1), ("z", 1)]:  # a typo in a flux key must not silently mean zero flux
        with pytest.raises(ValueError, match="flux keys"):
            solve_steady([0, 1e-3], [0, 1e-3], z, one, [10.0], h=10.0, T_inf=300.0, flux={key: 1e3})
    with pytest.raises(ValueError, match="flux array .* shape"):
        solve_steady([0, 1e-3], [0, 1e-3], z, one, [10.0], h=10.0, T_inf=300.0, flux={(0, -1): np.ones((2, 1, 1))})
    bad = np.ones((2, 1, 2))
    with pytest.raises(ValueError, match="non-exposed"):  # nonzero flux array on a non-exposed (interior) face
        solve_steady([0, 1e-3, 2e-3], [0, 1e-3], [0, 1e-3, 2e-3], np.zeros((2, 1, 2), int), [10.0], h=10.0,
                     T_inf=300.0, flux={(2, 1): bad})


def test_floating_island_raises():
    # a cell separated from the Robin face by a void layer has no conduction path to the sink: singular system
    with pytest.raises(ValueError, match="no conduction path"):
        solve_steady([0, 1e-3], [0, 1e-3], [0, 1e-3, 2e-3, 3e-3], np.array([0, -1, 0]).reshape(1, 1, 3), [10.0],
                     h=1e3, T_inf=300.0, source=1e6)
    n = 14  # same on the iterative path: the top two layers float above a void layer
    lines = np.linspace(0, 1e-3, n + 1)
    mat = np.zeros((n, n, n), int)
    mat[:, :, n - 3] = -1
    with pytest.raises(ValueError, match="no conduction path"):
        solve_steady(lines, lines, lines, mat, [10.0], h=1e3, T_inf=300.0, flux={(2, 1): 1e5})


def test_unreached_linear_tolerance_raises(monkeypatch):
    # starve CG (one iteration per pass) on the iterative path: the unconverged field must not be returned
    monkeypatch.setattr(thermal_fv, "_CG_MAXITER", 1)
    n = 14  # 2744 cells > _DIRECT_MAX
    lines = np.linspace(0, 1e-3, n + 1)
    with pytest.raises(RuntimeError, match="linear solve"):
        solve_steady(lines, lines, lines, np.zeros((n, n, n), int), [10.0], h=1e3, T_inf=300.0, source=1e9)


def test_stiff_system_accepted_at_the_rounding_floor_and_conserves_energy():
    # k contrast 1e7 and cell aspect ratios up to 100: the true residual stagnates at the float64 rounding level of
    # b - A u, above 1e-12.  The solver must accept it there (not raise) and the field must still conserve energy.
    rng = np.random.default_rng(3)
    n = 24
    xy = np.cumsum(np.r_[0, rng.uniform(0.2, 1.0, n)]) * 1e-4
    z = np.cumsum(np.r_[0, rng.uniform(0.01, 0.2, n)]) * 1e-4
    mat = rng.integers(0, 3, (n, n, n))
    res = solve_steady(xy, xy, z, mat, [1e4, 1e-3, 1.0], h=5e3, T_inf=300.0, flux={(2, 1): 1e5})
    m = res.meta
    assert m["linear_residual"] <= m["linear_residual_accepted"]
    assert m["linear_residual_accepted"] < 1e-7
    assert m["energy_balance"] <= 1e-9
    assert np.all(res.T >= 300.0 - 1e-6)  # maximum principle: heat only enters, the sink is at 300 K


def _exposed(act, axis, sign):
    pad = np.pad(act, 1, constant_values=False)
    sl = [slice(1, -1)] * 3
    sl[axis] = slice(2, None) if sign > 0 else slice(0, -2)
    return act & ~pad[tuple(sl)]


@pytest.mark.parametrize("ncell", [(9, 7, 6), (16, 14, 12)])  # direct and AMG-CG paths
@pytest.mark.parametrize("form", ["callable", "arrays"])
def test_piecewise_linear_field_exact_with_lateral_and_void_fluxes(ncell, form):
    # T = T0 + b x + c y + g(z), g piecewise linear with k1 g'_1 = k2 g'_2 at the layer interface z_i (flux
    # continuity).  Within each layer T is linear, so the two-point flux with half-cells in series is exact and the FV
    # cell values equal T at the cell centres, given exact boundary data: prescribed inflow k dT/dn on every exposed
    # face (box sides, top, the faces of an open pocket and of an enclosed void) and a Robin bottom with
    # T_inf = T(x, y, 0) - k1 g'_1 / h.  Any error in the sign, area or orientation of a face flux breaks exactness.
    nx, ny, nz = ncell
    rng = np.random.default_rng(11)
    x = np.cumsum(np.r_[0.0, rng.uniform(0.4e-3, 1.6e-3, nx)])
    y = np.cumsum(np.r_[0.0, rng.uniform(0.4e-3, 1.6e-3, ny)])
    nz0 = nz // 2
    zi, zt = 1.0e-3, 1.6e-3
    s = np.linspace(0, 1, nz0 + 1) ** 1.3
    z = np.concatenate([zi * s, zi + (zt - zi) * (np.linspace(0, 1, nz - nz0 + 1) ** 0.8)[1:]])
    k1, k2, h, T0, b, c, d1 = 50.0, 200.0, 2000.0, 320.0, 2000.0, -1500.0, 4000.0
    d2 = k1 * d1 / k2

    def g(zz):
        return np.where(zz <= zi, d1 * zz, d1 * zi + d2 * (zz - zi))

    def T(xx, yy, zz):
        return T0 + b * xx + c * yy + g(zz)

    def kz(zz):
        return np.where(zz < zi, k1, k2)

    mat = np.zeros((nx, ny, nz), int)
    mat[:, :, nz0:] = 1
    mat[nx // 3:nx // 3 + 3, ny // 3:ny // 3 + 2, nz0:] = -1  # pocket through the top layer, floor at z_i
    mat[nx - 3, ny - 3, 1] = -1  # enclosed void cell in the bottom layer
    act = mat >= 0
    grad = (b, c, None)

    def flux_fn(xx, yy, zz, axis, sign):
        if axis == 2:  # = k2 d2 on either side of the interface; none on z = 0 (additive to the Robin flux there)
            return np.where(zz > 0.0, sign * k1 * d1, 0.0)
        return sign * kz(zz) * grad[axis]

    if form == "callable":
        flux = flux_fn
    else:
        kc = np.where(mat == 1, k2, k1)
        flux = {}
        for axis in range(3):
            for sign in (-1, 1):
                val = sign * (k1 * d1 if axis == 2 else kc * grad[axis])
                flux[(axis, sign)] = np.where(_exposed(act, axis, sign), val, 0.0)
        flux[(2, -1)][:, :, 0] = 0.0
    res = solve_steady(x, y, z, mat, [k1, k2], h=h, T_inf=lambda xx, yy: T(xx, yy, 0 * xx) - k1 * d1 / h, flux=flux)
    xc, yc, zc = (0.5 * (a[:-1] + a[1:]) for a in (x, y, z))
    exact = T(xc[:, None, None], yc[None, :, None], zc[None, None, :])
    assert np.max(np.abs(res.T[act] - exact[act])) < 1e-9
    assert np.isnan(res.T[~act]).all()
    # reconstructed top surface (box top and pocket floor) is exact for a linear field
    surf_exact = T(xc[:, None], yc[None, :], res.surface.height)
    assert np.max(np.abs(res.surface.values - surf_exact)) < 1e-9
    assert np.any(res.surface.height == zi) and np.any(res.surface.height == zt)
    # inflow is the sum of the exact face fluxes; it leaves through the bottom
    assert res.meta["energy_balance"] <= 1e-9
    assert abs(res.meta["q_out"] - k1 * d1 * (x[-1] - x[0]) * (y[-1] - y[0])) < 1e-9 * res.meta["q_out"]


@pytest.mark.slow
def test_million_cells_under_60_s():
    stack = default_dbc_stack()
    layers = [stack.layer(n) for n in ("baseplate", "solder", "backside_cu", "ceramic", "top_cu")]
    n_per = [20, 10, 10, 10, 10]
    zl = [0.0]
    for la, n in zip(layers, n_per, strict=True):
        zl.extend(zl[-1] + la.thickness * np.arange(1, n + 1) / n)
    z = np.array(zl)
    nz = len(z) - 1
    nxy = 140
    x, y = np.linspace(0, 60e-3, nxy + 1), np.linspace(0, 50e-3, nxy + 1)
    mat = np.repeat(np.repeat(np.array(sum(([i] * n for i, n in enumerate(n_per)), []))[None, None, :], nxy, 0),
                    nxy, 1)
    assert mat.size >= 1_000_000
    q = lambda x, y, z: 2e6 * (np.abs(x - 30e-3) < 5e-3) * (np.abs(y - 25e-3) < 5e-3)  # noqa: E731
    res = solve_steady(x, y, z, mat, layers, h=5000.0, T_inf=300.0, flux={(2, 1): q})
    assert nz == 60 and res.meta["n_cells"] >= 1_000_000
    assert res.meta["wall_time_s"] < 60.0
    assert res.meta["energy_balance"] <= 1e-9
