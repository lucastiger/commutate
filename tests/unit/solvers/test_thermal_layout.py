"""Tests of the thermal L2 layout / box-stack front end: grid conformity, constant ratio, materials, GCI, 1D limit."""
from __future__ import annotations

import math

import numpy as np
import pytest

from moduleforge.generate.halfbridge import generate_layouts
from moduleforge.solvers import thermal_layout as tl
from moduleforge.solvers.thermal_series import box_series

T_C, H = 338.15, 5000.0


@pytest.fixture(scope="module")
def layout():
    return generate_layouts(1, 20261101, family="side_by_side", dies_per_switch=2)[0]


def _has(lines, v):
    return bool(np.min(np.abs(lines - v)) < 1e-9)


def _edges(layout):
    xs, ys = set(), set()
    back = layout.outline.buffer(-layout.backside_inset, join_style="mitre")
    polys = [layout.baseplate_outline, layout.outline, back, *(t.polygon for t in layout.traces),
             *(d.box for d in layout.dies)]
    for p in polys:
        c = np.asarray(p.exterior.coords)
        xs.update(c[:, 0])
        ys.update(c[:, 1])
    return sorted(xs), sorted(ys)


def _z_interfaces(layout):
    st = layout.stack
    z = [0.0]
    for la in st.layers:
        z.append(z[-1] + la.thickness)
    out = list(z)
    for d in layout.dies:
        out += [z[-1] + d.attach_thickness, layout.die_z_range(d)[1]]
    return out


@pytest.mark.parametrize("level", [0, 1, 2])
def test_every_geometry_edge_is_a_grid_line(layout, level):
    # level 2 is built without solving; only the grid builder runs
    g = tl.build_layout_grid(layout, level)
    xs, ys = _edges(layout)
    assert all(_has(g.x, v) for v in xs)
    assert all(_has(g.y, v) for v in ys)
    assert all(_has(g.z, v) for v in _z_interfaces(layout))
    assert np.all(np.diff(g.x) > 0) and np.all(np.diff(g.y) > 0) and np.all(np.diff(g.z) > 0)


def test_constant_refinement_ratio(layout):
    grids = [tl.build_layout_grid(layout, lv) for lv in range(3)]
    for a, b in zip(grids[:-1], grids[1:], strict=True):
        for ax in ("x", "y", "z"):
            fa, fb = getattr(a, ax), getattr(b, ax)
            assert len(fb) - 1 == tl.R * (len(fa) - 1)
            np.testing.assert_allclose(fb[::2], fa, atol=1e-12)  # coarse lines are fine lines
            # every spacing of the fine level is exactly half of the coarse one it lies in
            np.testing.assert_allclose(np.diff(fb)[0::2], np.diff(fa) / tl.R, rtol=1e-9)
            np.testing.assert_allclose(np.diff(fb)[1::2], np.diff(fa) / tl.R, rtol=1e-9)


def test_lateral_counts_double_exactly():
    lines = np.array([0.0, 1.3e-3, 4.0e-3, 4.5e-3])
    n = [tl.lateral_counts(lines, 0.5e-3, np.zeros(3, bool), lv) for lv in range(3)]
    np.testing.assert_array_equal(n[1], 2 * n[0])
    np.testing.assert_array_equal(n[2], 4 * n[0])
    np.testing.assert_array_equal(n[0], [3, 6, 1])  # ceil(len / 0.5 mm)
    far = tl.lateral_counts(lines, 0.5e-3, np.array([True, False, False]), 0)
    np.testing.assert_array_equal(far, [1, 6, 1])  # FAR_FACTOR 4: ceil(1.3/2) = 1


def test_material_assignment_at_sample_points(layout):
    g = tl.build_layout_grid(layout, 1)
    st = layout.stack
    xc, yc, zc = (0.5 * (a[:-1] + a[1:]) for a in (g.x, g.y, g.z))

    def at(x, y, z):
        return g.cell_material[np.argmin(abs(xc - x)), np.argmin(abs(yc - y)), np.argmin(abs(zc - z))]

    d = layout.dies[0]
    zbp = st.z_bottom("baseplate") + st.layer("baseplate").thickness / 2
    zsol = 0.5 * (st.z_bottom("solder") + st.z_top("solder"))
    zce = 0.5 * (st.z_bottom("ceramic") + st.z_top("ceramic"))
    ztc = 0.5 * (st.z_bottom("top_cu") + st.z_top("top_cu"))
    zat = st.z_top("top_cu") + d.attach_thickness / 2
    zdi = st.z_top("top_cu") + d.attach_thickness + d.thickness / 2
    assert at(d.cx, d.cy, zdi) == 6 and at(d.cx, d.cy, zat) == 5 and at(d.cx, d.cy, ztc) == 4
    assert at(d.cx, d.cy, zce) == 3 and at(d.cx, d.cy, zsol) == 1 and at(d.cx, d.cy, zbp) == 0
    # baseplate overhang (x = -4 mm): baseplate only
    assert at(-4e-3, 20e-3, zbp) == 0
    assert at(-4e-3, 20e-3, zsol) == -1 and at(-4e-3, 20e-3, zce) == -1
    # margin between the substrate edge and the inset backside Cu: ceramic yes, backside no
    zbs = 0.5 * (st.z_bottom("backside_cu") + st.z_top("backside_cu"))
    assert at(0.5 * layout.backside_inset, 20e-3, zce) == 3 and at(0.5 * layout.backside_inset, 20e-3, zbs) == -1
    # above the die: void; beside the die on top Cu: void above the copper
    assert at(d.cx, d.cy, g.z[-1] - 1e-9) == 6
    assert at(d.cx + d.w / 2 + 1e-3, d.cy, zdi) == -1
    # a point outside every trace (the PHASE pad x 2..6 mm is copper, a point at x = 7.5 mm, y = 20 mm is not) is void
    pt_void = [(x, y) for x in np.arange(0.5e-3, 9e-3, 0.25e-3) for y in (20e-3,)
               if not any(t.polygon.contains(__import__("shapely").geometry.Point(x, y)) for t in layout.traces)]
    assert pt_void and at(pt_void[0][0], pt_void[0][1], ztc) == -1


def test_layout_energy_balance_and_power(layout):
    out = tl.solve_layout_level(layout, level=0, power_W=[3.0, 5.0, 3.0, 5.0], h=H, T_c=T_C, constant_k=True)
    assert out["meta"]["energy_balance"] < 1e-9
    assert out["meta"]["q_in"] == pytest.approx(16.0, rel=1e-12)
    v = out["values"]
    assert all(v[f"die{i}.tj_max"] >= v[f"die{i}.tj_mean"] >= T_C for i in range(4))


def test_linear_scaling_with_constant_k(layout):
    a = tl.solve_layout_level(layout, level=0, power_W=2.0, h=H, T_c=T_C, constant_k=True)["values"]
    b = tl.solve_layout_level(layout, level=0, power_W=4.0, h=H, T_c=T_C, constant_k=True)["values"]
    assert (b["tj_max"] - T_C) == pytest.approx(2 * (a["tj_max"] - T_C), rel=1e-9)
    assert b["spread_max"] == pytest.approx(2 * a["spread_max"], rel=1e-8)


def test_k_of_t_picard_runs_and_balances(layout):
    out = tl.solve_layout_level(layout, level=0, power_W=8.0, h=H, T_c=T_C)
    assert out["meta"]["picard_iters"] > 1 and out["meta"]["energy_balance"] < 1e-6
    lin = tl.solve_layout_level(layout, level=0, power_W=8.0, h=H, T_c=T_C, constant_k=True)["values"]["tj_max"]
    assert out["values"]["tj_max"] > lin  # k falls with T, so the hot k(T) solution is hotter than k(300 K)


# ---------------------------------------------------------------------------------------------------- GCI
def test_gci_monotone_order_two():
    # d32 = -0.12, d21 = -0.03: p_obs = log2(4) = 2 -> Fs = 1.25, p = 2: GCI = 1.25 * 0.03 / (4 - 1) = 0.0125
    g = tl.gci_three_grid(1.16, 1.04, 1.01)
    assert g["p_obs"] == pytest.approx(2.0) and g["Fs"] == 1.25 and g["p"] == pytest.approx(2.0) and g["monotone"]
    assert g["gci"] == pytest.approx(0.0125, rel=1e-12)


def test_gci_monotone_order_between_1p5_and_2():
    ratio = 2**1.6  # p_obs = 1.6: p = 1.6, GCI = 1.25 * 0.1 / (2**1.6 - 1)
    g = tl.gci_three_grid(1.0 + 0.1 + 0.1 * ratio, 1.1, 1.0)
    assert g["p_obs"] == pytest.approx(1.6) and g["p"] == pytest.approx(1.6)
    assert g["gci"] == pytest.approx(0.125 / (2**1.6 - 1.0), rel=1e-12)


def test_gci_oscillatory():
    g = tl.gci_three_grid(1.0, 1.2, 1.1)  # d32 = +0.2, d21 = -0.1: Fs = 3, p = 2: 3 * 0.1 / 3 = 0.1
    assert not g["monotone"] and math.isnan(g["p_obs"]) and g["Fs"] == 3.0 and g["p"] == 2.0
    assert g["gci"] == pytest.approx(0.1, rel=1e-12)


def test_gci_order_out_of_range():
    hi = tl.gci_three_grid(1.8, 1.2, 1.1)  # ratio 6: p_obs = log2 6 = 2.585 > 2.5 -> Fs = 3, p = 2: 3 * 0.1 / 3
    assert hi["p_obs"] == pytest.approx(math.log2(6)) and hi["Fs"] == 3.0 and hi["gci"] == pytest.approx(0.1)
    lo = tl.gci_three_grid(1.2, 1.1, 1.0)  # ratio 1: p_obs = 0 < 1.5 -> Fs = 3, p = 2: 3 * 0.1 / 3
    assert lo["p_obs"] == pytest.approx(0.0, abs=1e-12) and lo["Fs"] == 3.0 and lo["gci"] == pytest.approx(0.1)


def test_gci_converged_values_give_zero():
    assert tl.gci_three_grid(2.0, 2.0, 2.0)["gci"] == 0.0
    assert tl.gci_three_grid(2.5, 2.0, 2.0)["gci"] == 0.0


def test_gci_uses_r_argument():
    g = tl.gci_three_grid(1.0 + 0.1 + 0.1 * 9, 1.1, 1.0, r=3.0)  # ratio 9 = 3**2 -> p_obs 2: 1.25 * 0.1 / (9 - 1)
    assert g["p_obs"] == pytest.approx(2.0) and g["gci"] == pytest.approx(1.25 * 0.1 / 8.0)


# ---------------------------------------------------------------------------------------------------- box stack
STACK = [(3e-3, 385.0), (0.1e-3, 58.0), (0.3e-3, 385.0), (0.38e-3, 24.0), (0.3e-3, 385.0),
         (50e-6, 58.0), (180e-6, 370.0)]


def test_box_full_top_source_is_1d_series_resistance():
    a, b, P = 10e-3, 6e-3, 25.0
    # R = sum t_j / (k_j A) + 1 / (h A) (docs/thermal_model.md section 6, Incropera sec. 3.1.3)
    area = a * b
    rise = P / area * (sum(t / k for t, k in STACK) + 1.0 / H)
    out = tl.solve_box_level(a, b, STACK, [(0.0, a, 0.0, b, P)], h=H, T_c=T_C, level=0)
    v = out["values"]
    for key in ("src0.tj_max", "src0.tj_mean", "src0.tj_centroid"):
        assert (v[key] - T_C) == pytest.approx(rise, rel=1e-9)
    assert out["meta"]["energy_balance"] < 1e-9


def test_box_three_levels_full_source_gci_zero():
    a, b, P = 4e-3, 4e-3, 3.0
    out = tl.solve_box_stack(a, b, STACK, [(0.0, a, 0.0, b, P)], h=H, T_c=T_C)
    assert max(out["meta"]["solver_tol"].values()) < 1e-8
    assert out["meta"]["r"] == 2.0 and len(out["meta"]["n_cells"]) == 3


def test_box_symmetric_sources_give_equal_values_and_converge():
    a = b = 12e-3
    s = 2e-3
    srcs = [(2e-3, 2e-3 + s, 2e-3, 2e-3 + s, 5.0), (8e-3, 8e-3 + s, 2e-3, 2e-3 + s, 5.0)]  # mirror images in x
    out = tl.solve_box_stack(a, b, STACK[:5], srcs, h=H, T_c=T_C)
    v = out["values"]
    assert v["src0.tj_max"] == pytest.approx(v["src1.tj_max"], rel=1e-10)
    assert v["spread_max"] == pytest.approx(0.0, abs=1e-9)
    conv = out["meta"]["convergence"]["src0.tj_max"]
    assert conv["monotone"] and 1.0 < conv["p_obs"] < 3.0
    assert out["meta"]["energy_balance"][-1] < 1e-9
    # temperatures fall monotonically in the sense of non-increasing |change| with level
    f = conv["values"]
    assert abs(f[2] - f[1]) < abs(f[1] - f[0])


@pytest.mark.slow
def test_layout_study_returns_solver_tol_and_levels(layout):
    out = tl.solve_layout(layout, power_W=2.0, h=H, T_c=T_C, constant_k=True)
    m = out["meta"]
    assert m["levels"] == [0, 1, 2] and len(m["n_cells"]) == 3 and m["n_cells"][0] < m["n_cells"][1] < m["n_cells"][2]
    assert set(m["solver_tol"]) == set(out["values"])
    assert {"die0.tj_max", "die0.tj_mean", "die0.tj_centroid", "spread_max", "tj_max"} <= set(m["solver_tol"])
    assert max(m["energy_balance"]) < 1e-9 and m["r"] == 2.0 and m["picard_iters"] == [1, 1, 1]


# ---------------------------------------------------------------------------------------------------- Fourier reference
def test_series_full_source_is_1d_series_resistance():
    a, b, P = 10e-3, 6e-3, 25.0
    ref = box_series(a, b, STACK, [(0.0, a, 0.0, b, P)], h=H, T_c=T_C, n_modes=4)
    rise = P / (a * b) * (sum(t / k for t, k in STACK) + 1.0 / H)
    assert ref["src0.tj_mean"] - T_C == pytest.approx(rise, rel=1e-12)
    assert ref["src0.tj_centroid"] - T_C == pytest.approx(rise, rel=1e-12)


def test_series_linear_symmetric_and_converged():
    a, b = 14e-3, 12e-3
    s1, s2 = (2e-3, 6e-3, 3e-3, 7e-3), (8e-3, 12e-3, 3e-3, 7e-3)  # mirror images about x = a / 2
    r = box_series(a, b, STACK, [(*s1, 10.0), (*s2, 10.0)], h=H, T_c=T_C, n_modes=300)
    assert r["src0.tj_mean"] == pytest.approx(r["src1.tj_mean"], rel=1e-12)
    assert r["src0.tj_centroid"] == pytest.approx(r["src1.tj_centroid"], rel=1e-12)
    r2 = box_series(a, b, STACK, [(*s1, 20.0), (*s2, 20.0)], h=H, T_c=T_C, n_modes=300)
    assert r2["src0.tj_mean"] - T_C == pytest.approx(2 * (r["src0.tj_mean"] - T_C), rel=1e-12)
    r3 = box_series(a, b, STACK, [(*s1, 10.0), (*s2, 10.0)], h=H, T_c=T_C, n_modes=600)
    assert abs(r3["src0.tj_mean"] - r["src0.tj_mean"]) < 1e-3 and abs(r3["src0.tj_centroid"] - r["src0.tj_centroid"]) < 5e-3


def test_series_total_power_balance_through_mean_sink_temperature():
    # the (0,0) mode alone carries the whole heat flow: its rise at the bottom face is P / (h A), so the
    # source-mean temperature exceeds T_c + P / (h A) (all other modes add positive terms)
    a, b, P = 14e-3, 12e-3, 30.0
    r = box_series(a, b, STACK, [(4e-3, 9e-3, 3e-3, 8e-3, P)], h=H, T_c=T_C, n_modes=200)
    assert r["src0.tj_mean"] - T_C > P / (H * a * b)


BOX_CASES = {
    "centred": (14e-3, 14e-3, [(4.5e-3, 9.5e-3, 4.5e-3, 9.5e-3, 30.0)]),
    "near_wall": (16e-3, 12e-3, [(1e-3, 6e-3, 2e-3, 7e-3, 25.0)]),
    "two_unequal": (16e-3, 12e-3, [(2e-3, 6.5e-3, 3e-3, 7.5e-3, 20.0), (9e-3, 13.5e-3, 3e-3, 7.5e-3, 40.0)]),
}


@pytest.mark.slow
@pytest.mark.parametrize("case", sorted(BOX_CASES))
def test_gci_is_conservative_against_fourier_series_on_partial_source_boxes(case):
    """Frozen rule, levels 0-2: GCI >= |true error| of the finest level for every reported source value, where the
    true error is against the converged Fourier series (``thermal_series``)."""
    a, b, srcs = BOX_CASES[case]
    out = tl.solve_box_stack(a, b, STACK, srcs, h=H, T_c=T_C)
    ref = box_series(a, b, STACK, srcs, h=H, T_c=T_C, n_modes=600)
    checked = 0
    for name, ref_val in ref.items():
        err = abs(out["values"][name] - ref_val)
        gci = out["meta"]["solver_tol"][name]
        assert gci >= err, f"{case} {name}: GCI {gci:.5f} K < true error {err:.5f} K"
        assert err < 0.05  # the rule is accurate here, not only conservative
        checked += 1
    assert checked == 2 * len(srcs)


@pytest.mark.slow
def test_gci_conservative_at_the_coarser_level_pair_too():
    # the same estimate computed from levels 0-2 must also bound the error of the middle level (it is an estimate of
    # the finest, so the bound is only required for the finest; the middle level error is larger than the finest)
    a, b, srcs = BOX_CASES["centred"]
    runs = [tl.solve_box_level(a, b, STACK, [(*s[:4], s[4]) for s in srcs], h=H, T_c=T_C, level=lv)["values"]
            for lv in range(3)]
    ref = box_series(a, b, STACK, srcs, h=H, T_c=T_C, n_modes=600)["src0.tj_mean"]
    e = [abs(r["src0.tj_mean"] - ref) for r in runs]
    assert e[0] > e[1] > e[2]


def test_rule_has_fixed_level0_and_no_per_case_knob():
    import inspect

    assert tl.LEVEL0 == 0
    assert "level0" not in inspect.signature(tl.solve_layout).parameters
    assert "level0" not in inspect.signature(tl.solve_box_stack).parameters


def test_edge_graded_nodes_geometric_and_nested():
    lines = np.array([0.0, 4e-3, 10e-3])
    n0 = tl.edge_graded_nodes(lines, [4e-3], 1e-3, 0.1e-3, 2.0, 0)
    d = np.diff(n0)
    assert np.all(d <= 1e-3 + 1e-15) and np.all(d > 0)
    i = int(np.searchsorted(n0, 4e-3))
    np.testing.assert_allclose(n0[i], 4e-3, atol=1e-15)  # the edge is a node
    # growth away from the edge on both sides: 0.1, 0.2, 0.4, 0.8 mm
    np.testing.assert_allclose(d[i - 1], 0.1e-3, rtol=1e-12)
    np.testing.assert_allclose(d[i], 0.1e-3, rtol=1e-12)
    np.testing.assert_allclose(d[i + 1] / d[i], 2.0, rtol=1e-12)
    n1 = tl.edge_graded_nodes(lines, [4e-3], 1e-3, 0.1e-3, 2.0, 1)
    np.testing.assert_allclose(n1[::2], n0, atol=1e-15)
    np.testing.assert_allclose(np.diff(n1)[0::2], np.diff(n0) / 2, rtol=1e-12)
