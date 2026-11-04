"""Grid rule of the scikit-fem thermal reference (T0206, from diagnosis T0198): absolute dz bound with r = 2 in x, y and z,
mandatory grid lines, node-only point values and the Tj-max node coordinates (docs/thermal_model.md, "Grid rule")."""
from __future__ import annotations

import math

import numpy as np
import pytest
from shapely.geometry import box

from moduleforge.generate.halfbridge import generate_layouts
from moduleforge.geometry.layout import Die, Layout, Trace
from moduleforge.geometry.stack import default_dbc_stack
from moduleforge.solvers import thermal_fem as F

TC = 338.15
H = 5000.0


def _toy_layout() -> Layout:
    """Two dies on one rectangular trace, mirror-symmetric about x = 10 mm (the layout of test_thermal_fem.py)."""
    outline = box(0.0, 0.0, 20e-3, 10e-3)
    d1 = Die(6e-3, 5e-3, 4e-3, 4e-3, "HS", {})
    d2 = Die(14e-3, 5e-3, 4e-3, 4e-3, "LS", {})
    return Layout("toy", 1, outline, [Trace("DC+", box(2e-3, 2e-3, 18e-3, 8e-3))], [d1, d2], [], {},
                  box(-3e-3, -3e-3, 23e-3, 13e-3), default_dbc_stack())


def _gen_layout() -> Layout:
    return generate_layouts(1, 20261103)[0]


# a box stack of realistic size: 24 x 16 mm substrate-like footprint, Cu / ceramic / Cu / die attach / die, two sources
def _stack() -> list:
    return [F.BoxLayer(3.0e-3, 390.0, 2, "base"), F.BoxLayer(0.3e-3, 390.0, 1, "cu"), F.BoxLayer(0.38e-3, 25.0, 1, "al2o3"),
            F.BoxLayer(0.3e-3, 390.0, 1, "cu"), F.BoxLayer(0.1e-3, 60.0, 1, "attach"), F.BoxLayer(0.18e-3, 120.0, 2, "die")]


A_BOX, B_BOX = 24e-3, 16e-3
SRC2 = [(5e-3, 4e-3, 11e-3, 12e-3, 30.0), (14e-3, 5e-3, 19e-3, 11e-3, 20.0)]


def _dz(g) -> np.ndarray:
    return np.diff(g.z)


# ------------------------------------------------------------------------------------------------ (a) dz bound
@pytest.mark.parametrize("dz_max", [2.5e-4, 1.0e-3])
def test_dz_bound_and_halving_default_stack(dz_max):
    """Level-0 dz <= dz_max in every layer (incl. die attach and die); halves exactly per level; every interval's count is
    max(nz, ceil(t / dz_max)) times 2**level."""
    lay = _toy_layout()
    rule = F.GridRule(h0=5e-3, dz_max=dz_max)
    st = lay.stack
    zb = np.concatenate(([0.0], np.cumsum([la.thickness for la in st.layers])))
    d = lay.dies[0]
    bands = [(zb[i], zb[i + 1], rule.nz_of(la.name)) for i, la in enumerate(st.layers)]
    bands += [(zb[-1], zb[-1] + d.attach_thickness, rule.nz_of("die_attach")),
              (zb[-1] + d.attach_thickness, zb[-1] + d.attach_thickness + d.thickness, rule.nz_of("die"))]
    prev = None
    for lv in (0, 1, 2):
        g = F.layout_grid(lay, 1.0, H, TC, rule, lv)
        dz = _dz(g)
        assert dz.max() <= dz_max / 2**lv * (1 + 1e-9)
        for lo, hi, nz in bands:
            sel = (g.z[:-1] >= lo - 1e-12) & (g.z[1:] <= hi + 1e-12)
            expect = max(nz, math.ceil((hi - lo) / dz_max - 1e-9)) * 2**lv  # independent count of the cells of this layer
            assert sel.sum() == expect
            np.testing.assert_allclose(dz[sel], (hi - lo) / expect, rtol=1e-9)
        if prev is not None:
            assert dz.size == 2 * prev.size  # every z cell halves exactly
        prev = dz


def test_dz_bound_single_plate_10mm():
    """A 10 mm single plate: ceil(10 mm / dz_max) cells, dz <= dz_max, halving; dz_max=None keeps the layer's count."""
    for dz_max, ncell in [(1.0e-3, 10), (3.0e-3, 4), (4.0e-3, 3)]:
        rule = F.GridRule(h0=5e-3, dz_max=dz_max)
        for lv in (0, 1, 2):
            g = F.box_stack_grid(20e-3, 20e-3, [F.BoxLayer(10e-3, 100.0, 1)], H, TC, [], rule=rule, level=lv)
            assert g.z.size - 1 == ncell * 2**lv
            assert _dz(g).max() <= dz_max / 2**lv * (1 + 1e-9)
            np.testing.assert_allclose(_dz(g), 10e-3 / (ncell * 2**lv), rtol=1e-9)
    g = F.box_stack_grid(20e-3, 20e-3, [F.BoxLayer(10e-3, 100.0, 3)], H, TC, [], rule=F.GridRule(h0=5e-3), level=1)
    assert g.z.size - 1 == 6  # no dz_max: the per-layer count, doubled per level
    # a layer count above the bound is kept (max, not min)
    g = F.box_stack_grid(20e-3, 20e-3, [F.BoxLayer(10e-3, 100.0, 40)], H, TC, [], rule=F.GridRule(h0=5e-3, dz_max=1e-3))
    assert g.z.size - 1 == 40


def test_dz_max_validation():
    with pytest.raises(ValueError):
        F.GridRule(dz_max=1e-3, zrefine=False)
    with pytest.raises(ValueError):
        F.GridRule(dz_max=0.0)
    assert F.GridRule().dz_max is None
    assert F.GridRule(dz_max=2.5e-4, element_order=2).zrefine


# ------------------------------------------------------------------------------------------------ r = 2 bisection
def _check_bisection(grids):
    for g0, g1 in zip(grids[:-1], grids[1:], strict=True):
        for a0, a1 in ((g0.x, g1.x), (g0.y, g1.y), (g0.z, g1.z)):
            # every line of level l is a line of level l+1 ...
            idx = np.searchsorted(a1, a0)
            np.testing.assert_allclose(a1[idx], a0, rtol=0, atol=1e-13)
            # ... and every cell bisects: exactly one new line strictly inside each cell, at its midpoint
            assert a1.size == 2 * a0.size - 1
            np.testing.assert_allclose(a1[idx[:-1] + 1], 0.5 * (a0[1:] + a0[:-1]), rtol=0, atol=1e-13)
            assert np.all(np.diff(idx) == 2)


@pytest.mark.parametrize("which", ["layout", "generator", "box", "box_near"])
def test_every_line_is_a_finer_line_and_every_cell_bisects(which):
    """Levels 0 -> 1 -> 2: lines nest and cells bisect in x, y and z (constant refinement ratio r = 2), with dz_max set,
    with near_margin grading, with mandatory lines and the mandatory source centroid lines."""
    rule = F.GridRule(h0=2.5e-3, dz_max=2.5e-4)
    ex = ([3.3e-3], [4.1e-3], [1.234e-4])
    if which == "layout":
        grids = [F.layout_grid(_toy_layout(), 1.0, H, TC, rule, lv, extra_lines=ex) for lv in (0, 1, 2)]
    elif which == "generator":
        grids = [F.layout_grid(_gen_layout(), 1.0, H, TC, F.GridRule(h0=4e-3, dz_max=5e-4), lv) for lv in (0, 1)]
    elif which == "box":
        grids = [F.box_stack_grid(A_BOX, B_BOX, _stack(), H, TC, SRC2, rule=rule, level=lv, extra_lines=ex) for lv in (0, 1, 2)]
    else:
        r = F.GridRule(h0=1.5e-3, dz_max=5e-4, near_margin=1.5e-3)
        grids = [F.box_stack_grid(A_BOX, B_BOX, _stack(), H, TC, SRC2, rule=r, level=lv) for lv in (0, 1, 2)]
    _check_bisection(grids)


# ------------------------------------------------------------------------------------------------ DOF growth
def _count(g) -> int:
    return F._count_nodes(g.mat) if g.order == 1 else F._count_nodes_q2(g.mat)


@pytest.mark.parametrize("order", [1, 2])
def test_dof_growth_is_8_per_level_generator_layout(order):
    """DOFs grow by 8 +/- 15 % per level (r = 2 in three directions) on a default-stack generator layout; the count is the
    lattice count that test_thermal_fem_assembly.py proves equal to the assembled N."""
    lay = _gen_layout()
    rule = F.GridRule(h0=1.5e-3, dz_max=2.5e-4, element_order=order)
    n = [F.estimate_dofs(lay, rule, lv) for lv in (0, 1, 2)]
    for a, b in zip(n[:-1], n[1:], strict=True):
        assert 8 * 0.85 <= b / a <= 8 * 1.15, n


@pytest.mark.parametrize("order", [1, 2])
def test_dof_growth_is_8_per_level_box_stack(order):
    rule = F.GridRule(h0=1.0e-3, dz_max=2.5e-4, element_order=order)
    n = [_count(F.box_stack_grid(A_BOX, B_BOX, _stack(), H, TC, SRC2, rule=rule, level=lv)) for lv in (0, 1, 2)]
    for a, b in zip(n[:-1], n[1:], strict=True):
        assert 8 * 0.85 <= b / a <= 8 * 1.15, n


@pytest.mark.parametrize("order", [1, 2])
def test_meta_records_dofs_lines_and_order(order):
    """meta: n_dofs (equal to the DOF count and to the grid's lattice count), n_elements (= non-void cells), element order,
    level, line arrays and counts; DOFs grow ~8x between two levels of the solved box stack."""
    rule = F.GridRule(h0=4e-3, dz_max=1.0e-3, element_order=order)
    res = [F.solve_box_stack(A_BOX, B_BOX, _stack(), H, TC, SRC2, rule=rule, level=lv, constant_k=True) for lv in (0, 1)]
    for lv, r in enumerate(res):
        g = F.box_stack_grid(A_BOX, B_BOX, _stack(), H, TC, SRC2, rule=rule, level=lv)
        m = r.meta
        assert m["n_dofs"] == r.dofs == _count(g)
        assert m["n_elements"] == (g.mat.size)  # a box stack has no void cells
        assert m["element_order"] == order and m["level"] == lv
        for ax, arr in zip("xyz", (g.x, g.y, g.z), strict=True):
            np.testing.assert_array_equal(m["lines"][ax], arr)
            assert m["n_lines"][ax] == arr.size
    assert m["n_elements"] == 8 * res[0].meta["n_elements"]  # exact bisection: 8 children per cell
    assert 6.5 <= res[1].dofs / res[0].dofs <= 9.5


# ------------------------------------------------------------------------------------------------ mandatory lines
@pytest.mark.parametrize("order", [1, 2])
def test_mandatory_lines_node_value_at_every_level_box(order):
    """Lines at coordinates that no geometry fixes are lines (hence nodes) at every level; node_value returns the nodal value
    there (checked against the independently built vertex table of the top face for Q1 and the nearest-DOF search) and
    raises off-node. The source centroid is mandatory without being asked."""
    xe, ye, ze = 7.3e-3, 5.1e-3, 1.7e-3
    rule = F.GridRule(h0=4e-3, dz_max=1.0e-3, element_order=order)
    levels = (0, 1, 2) if order == 1 else (0, 1)
    for lv in levels:
        r = F.solve_box_stack(A_BOX, B_BOX, _stack(), H, TC, SRC2, rule=rule, level=lv, constant_k=True,
                              extra_lines=([xe], [ye], [ze]))
        lines = r.meta["lines"]
        for ax, v in zip("xyz", (xe, ye, ze), strict=True):
            assert np.min(np.abs(lines[ax] - v)) < 1e-12
        for s in SRC2:  # centroids
            assert np.min(np.abs(lines["x"] - 0.5 * (s[0] + s[2]))) < 1e-12
            assert np.min(np.abs(lines["y"] - 0.5 * (s[1] + s[3]))) < 1e-12
        v = F.node_value(r, xe, ye)  # z defaults to the top face
        d = np.linalg.norm(r.nodes - np.array([xe, ye, sum(la.t for la in _stack())]), axis=1)
        assert v == r.T[np.argmin(d)] and d.min() < 1e-12
        vz = F.node_value(r, xe, ye, ze)  # an interior mandatory z plane
        assert vz == r.T[np.argmin(np.linalg.norm(r.nodes - np.array([xe, ye, ze]), axis=1))]
        if order == 1:  # the independent vertex table of the top face (meta T_top)
            i = int(np.argmin(np.abs(r.meta["xs"] - xe)))
            j = int(np.argmin(np.abs(r.meta["ys"] - ye)))
            assert v == pytest.approx(r.meta["T_top"][i, j], abs=1e-12)
        cx = 0.5 * (SRC2[0][0] + SRC2[0][2])
        assert F.node_value(r, cx, 0.5 * (SRC2[0][1] + SRC2[0][3])) > TC  # a source centroid is a node too
        st = F.node_stencil(r, xe, ye, ze)
        for s, ax, v0 in zip(st, "xyz", (xe, ye, ze), strict=True):
            assert s["on_line"] and lines[ax][s["index"]] == pytest.approx(v0, abs=1e-12) and s["coord"] == lines[ax][s["index"]]
            assert s["lo"] == lines[ax][s["index"] - 1] and s["hi"] == lines[ax][s["index"] + 1]
        # off-node: a third of the way across a cell is not a DOF of Q1 nor of Q2 (nodes at 0, 1/2, 1)
        x_off = xe + (lines["x"][np.searchsorted(lines["x"], xe + 1e-12)] - xe) / 3.0
        with pytest.raises(ValueError):
            F.node_value(r, x_off, ye)
        with pytest.raises(ValueError):
            F.node_value(r, xe, ye, ze + 1e-6)
        with pytest.raises(ValueError):
            F.node_value(r, 0.5 * (xe + 2 * xe), ye)
        s_off = F.node_stencil(r, x_off, ye)
        assert not s_off[0]["on_line"] and s_off[0]["lo"] < x_off < s_off[0]["hi"] and s_off[0]["index"] is None
        with pytest.raises(ValueError):
            F.node_stencil(r, -1.0, ye)
    if order == 1:  # Q1: the cell midpoint is not a node
        r = F.solve_box_stack(A_BOX, B_BOX, _stack(), H, TC, SRC2, rule=rule, level=0, constant_k=True)
        xm = 0.5 * (r.meta["xs"][1] + r.meta["xs"][2])
        with pytest.raises(ValueError):
            F.node_value(r, xm, r.meta["ys"][1])
    else:  # Q2: the cell midpoint is a (mid-edge) node
        r = F.solve_box_stack(A_BOX, B_BOX, _stack(), H, TC, SRC2, rule=rule, level=0, constant_k=True)
        xm = 0.5 * (r.meta["xs"][1] + r.meta["xs"][2])
        assert math.isfinite(F.node_value(r, xm, r.meta["ys"][1]))


def test_mandatory_lines_layout_mode_and_tolerance():
    """Layout mode: a point inside a die top face, on mandatory lines, is a node at levels 0, 1, 2; a coordinate within
    1e-9 m of a node is accepted, 1e-8 m off is rejected; lines outside the domain are rejected."""
    lay = _toy_layout()
    pt = (5.3e-3, 4.7e-3)
    zt = lay.stack.z_top("top_cu") + lay.dies[0].attach_thickness + lay.dies[0].thickness
    rule = F.GridRule(h0=2e-3, dz_max=2.5e-4)
    for lv in (0, 1):
        r = F.solve_layout(lay, 20.0, H, TC, rule=rule, level=lv, constant_k=True, extra_lines=([pt[0]], [pt[1]], None))
        v = F.node_value(r, *pt)
        i = np.argmin(np.linalg.norm(r.nodes - np.array([pt[0], pt[1], zt]), axis=1))
        assert v == r.T[i] and abs(r.nodes[i, 2] - zt) < 1e-12 and r.T[i] > TC
        assert F.node_value(r, pt[0] + 0.9e-9, pt[1] - 0.9e-9, zt) == v
        with pytest.raises(ValueError):
            F.node_value(r, pt[0] + 1e-8, pt[1])
    with pytest.raises(ValueError):
        F.layout_grid(lay, 1.0, H, TC, rule, 0, extra_lines=([1.0], [0.0], None))
    with pytest.raises(ValueError):
        F.box_stack_grid(A_BOX, B_BOX, _stack(), H, TC, [], rule=rule, extra_lines=([0.0], [0.0], [1.0]))


# ------------------------------------------------------------------------------------------------ Tj max node
@pytest.mark.parametrize("order", [1, 2])
def test_tj_max_xyz_on_die_top_face_and_is_the_max_node(order):
    """tj_max_xyz[i] lies on die i's top face (z, and inside its x/y footprint) and is the DOF of maximum T among the
    nodes selected independently from the node coordinates; the value is tj_max[i]."""
    lay = _toy_layout()
    r = F.solve_layout(lay, [60.0, 10.0], H, TC, rule=F.GridRule(h0=1e-3, dz_max=2.5e-4, element_order=order), level=0)
    assert len(r.meta["tj_max_xyz"]) == 2
    for i, d in enumerate(lay.dies):
        x0, y0, x1, y1 = d.bounds
        zt = lay.stack.z_top("top_cu") + d.attach_thickness + d.thickness
        n = r.nodes
        face = (np.abs(n[:, 2] - zt) < 1e-12) & (n[:, 0] >= x0 - 1e-12) & (n[:, 0] <= x1 + 1e-12) \
            & (n[:, 1] >= y0 - 1e-12) & (n[:, 1] <= y1 + 1e-12)
        k = np.nonzero(face)[0][np.argmax(r.T[face])]
        xyz = r.meta["tj_max_xyz"][i]
        assert abs(xyz[2] - zt) < 1e-12 and x0 <= xyz[0] <= x1 and y0 <= xyz[1] <= y1
        np.testing.assert_allclose(xyz, n[k], atol=1e-12)
        assert r.tj_max[i] == r.T[k]
        assert F.node_value(r, xyz[0], xyz[1], xyz[2]) == r.tj_max[i]
    # the hot die's maximum is near its centre line in y (the die is y-symmetric about 5 mm)
    assert abs(r.meta["tj_max_xyz"][0][1] - 5e-3) < 1e-3


@pytest.mark.parametrize("order", [1, 2])
def test_tj_max_xyz_box_stack(order):
    a, b = 0.02, 0.01
    layers = [F.BoxLayer(1e-3, 150.0, 2), F.BoxLayer(0.3e-3, 30.0, 1)]
    r = F.solve_box_stack(a, b, layers, 2000.0, 300.0, [(7e-3, 2e-3, 13e-3, 8e-3, 20.0)], constant_k=True,
                          rule=F.GridRule(h0=1e-3, dz_max=2.5e-4, element_order=order), level=1)
    xyz = r.meta["tj_max_xyz"][0]
    assert xyz[2] == pytest.approx(1.3e-3, abs=1e-12)
    assert xyz[0] == pytest.approx(10e-3, abs=1e-9) and xyz[1] == pytest.approx(5e-3, abs=1e-9)  # centred source: its centroid


# ------------------------------------------------------------------------------------------------ symmetry
@pytest.mark.parametrize("order", [1, 2])
def test_centred_single_source_box_stack_mirror_symmetric(order):
    """A centred source on a box stack gives a field with T(x, y, z) = T(a - x, y, z) = T(x, b - y, z) to 1e-9 K at every
    DOF (Q1 and Q2, k(T) Picard, dz_max grid, mandatory lines)."""
    a, b = 20e-3, 12e-3
    src = [(7e-3, 4e-3, 13e-3, 8e-3, 40.0)]
    # mandatory lines placed symmetrically, so that the grid itself is mirror-symmetric
    sym = F.solve_box_stack(a, b, _stack(), H, TC, src, rule=F.GridRule(h0=3e-3, dz_max=5e-4, element_order=order), level=1,
                            extra_lines=([4.3e-3, a - 4.3e-3], [2.9e-3, b - 2.9e-3], None))
    q = np.round(sym.nodes / 1e-10).astype(np.int64)
    key = {tuple(row): i for i, row in enumerate(q)}
    for axis, L in ((0, a), (1, b)):
        qm = q.copy()
        qm[:, axis] = np.round(L / 1e-10).astype(np.int64) - q[:, axis]
        idx = np.array([key[tuple(row)] for row in qm])
        assert np.max(np.abs(sym.T - sym.T[idx])) < 1e-9
    assert sym.tj_max[0] > TC + 1.0


# ------------------------------------------------------------------------------------------------ unchanged default
def test_default_rule_unchanged_counts_and_legacy_signature():
    """dz_max=None: z cells are the per-layer counts times 2**level (the earlier rule); the legacy box-stack call
    (h0, element_order keywords) equals the rule call; no extra lines add no lines (beyond a box stack's centroids: the legacy ``h0=`` box-stack grid now
    includes every source's centroid lines, T0215 note; the test checks that explicitly below)."""
    lay = _toy_layout()
    rule = F.GridRule(h0=2e-3)
    for lv in (0, 1, 2):
        g = F.layout_grid(lay, 1.0, H, TC, rule, lv)
        assert g.z.size - 1 == (2 + 1 + 1 + 1 + 1 + 1 + 2) * 2**lv  # baseplate, solder, bs-Cu, ceramic, top-Cu, attach, die
        g2 = F.layout_grid(lay, 1.0, H, TC, rule, lv, extra_lines=([], [], []))
        for u, v in ((g.x, g2.x), (g.y, g2.y), (g.z, g2.z)):
            np.testing.assert_array_equal(u, v)
    layers = [F.BoxLayer(1e-3, 100.0, 2), F.BoxLayer(0.5e-3, 50.0, 1)]
    a, b, src = 0.01, 0.01, [(0.0, 0.0, 0.01, 0.01, 10.0)]
    r1 = F.solve_box_stack(a, b, layers, 1000.0, 300.0, src, h0=0.005, element_order=2, level=1, constant_k=True)
    r2 = F.solve_box_stack(a, b, layers, 1000.0, 300.0, src, rule=F.GridRule(h0=0.005, element_order=2), level=1,
                           constant_k=True)
    for ax in "xyz":
        np.testing.assert_array_equal(r1.meta["lines"][ax], r2.meta["lines"][ax])  # the same grid
    assert np.min(np.abs(r1.meta["lines"]["x"] - 0.005)) < 1e-12  # the legacy grid has the source centroid line x = a / 2
    np.testing.assert_allclose(r1.T, r2.T, rtol=0, atol=1e-9)
    with pytest.raises(ValueError):
        F.solve_box_stack(a, b, layers, 1000.0, 300.0, src, level=0)  # neither h0 nor a rule
    with pytest.raises(ValueError):
        F.solve_box_stack(a, b, layers, 1000.0, 300.0, src, h0=0.005, rule=F.GridRule(h0=0.004))


# ------------------------------------------------------------------------------------------------ snapping (T0215)
# values of the pre-T0216 code (git HEAD of T0206) on grids without near-coincident lines: the change must not move them
_PINNED = {
    ("layout", 1): ([409.3695498235362, 387.9296200355076], [402.93731534702255, 384.62940987494596]),
    ("layout", 2): ([409.40963472949034, 388.0002973140944], [404.5359297103216, 385.6077243402118]),
    ("box", 1): ([377.3747379321397, 375.99713690098713], [374.47348709395874, 373.3398746240375]),
    ("box", 2): ([377.3621280688686, 376.0135333254722], [374.8045130715334, 373.70663407223515]),
}


@pytest.mark.parametrize("order", [1, 2])
@pytest.mark.parametrize("mode", ["layout", "box"])
def test_results_unchanged_without_near_coincident_lines(mode, order):
    if mode == "layout":
        r = F.solve_layout(_toy_layout(), [40.0, 20.0], H, TC, rule=F.GridRule(h0=2e-3, dz_max=5e-4, element_order=order),
                           extra_lines=([4.5e-3], [3.7e-3], [1.234e-4]))
    else:
        r = F.solve_box_stack(A_BOX, B_BOX, _stack(), H, TC, SRC2, rule=F.GridRule(h0=4e-3, dz_max=1e-3, element_order=order),
                              extra_lines=([7.3e-3], [5.1e-3], [1.7e-3]))
    tj, tm = _PINNED[(mode, order)]
    np.testing.assert_allclose(r.tj_max, tj, rtol=0, atol=1e-8)
    np.testing.assert_allclose(r.tj_mean, tm, rtol=0, atol=1e-8)
    assert r.meta["snapped_lines"] == {"x": [], "y": [], "z": []} and r.meta["max_snap_m"] == 0.0


@pytest.mark.parametrize("order", [1, 2])
@pytest.mark.parametrize("mode", ["layout", "box"])
@pytest.mark.parametrize("dy", [1e-9, 1e-7, 1e-6])
def test_near_coincident_mandatory_line_snaps_and_solves(mode, dy, order):
    """A mandatory line dy from an existing edge (die edge y = 3 mm / source edge y = 4 mm) snaps onto it: no sliver
    cell, the solve works, the snap is recorded, and the nodal value at the snapped coordinate equals the value of a run
    that asked for the edge exactly (so a reported point moved by exactly the recorded distance, dy)."""
    if mode == "layout":
        edge, xe, ze = 3e-3, 4.5e-3, _toy_layout().stack.z_top("top_cu") + 1e-9  # z: just above the top-Cu / attach plane
        rule = F.GridRule(h0=3e-3, dz_max=5e-4, element_order=order)

        def run(ey, ez):
            return F.solve_layout(_toy_layout(), 30.0, H, TC, rule=rule, constant_k=True, extra_lines=([xe], [ey], [ez]))
    else:
        edge, xe, ze = 4e-3, 7.3e-3, 3.0e-3 + 1e-7  # z: just above the base / cu interface
        rule = F.GridRule(h0=4e-3, dz_max=1e-3, element_order=order)

        def run(ey, ez):
            return F.solve_box_stack(A_BOX, B_BOX, _stack(), H, TC, SRC2, rule=rule, constant_k=True,
                                     extra_lines=([xe], [ey], [ez]))
    zedge = round(ze - (1e-9 if mode == "layout" else 1e-7), 12)
    r = run(edge + dy, ze)
    ref = run(edge, zedge)
    y = r.meta["lines"]["y"]
    assert np.min(np.abs(y - edge)) < 1e-14 and np.sum(np.abs(y - edge) < 1e-5) == 1  # one line near the edge, on it
    assert np.sum(np.abs(r.meta["lines"]["z"] - zedge) < 1e-5) == 1
    for ax in "yz":
        np.testing.assert_array_equal(r.meta["lines"][ax], ref.meta["lines"][ax])
    sy = r.meta["snapped_lines"]["y"]
    assert len(sy) == 1 and sy[0][0] == edge + dy and abs(sy[0][1] - edge) < 1e-14
    sz = r.meta["snapped_lines"]["z"]
    assert len(sz) == 1 and abs(sz[0][1] - zedge) < 1e-12 and abs(sz[0][0] - ze) < 1e-14
    assert r.meta["max_snap_m"] == pytest.approx(max(dy, abs(ze - zedge)), rel=1e-3, abs=1e-12)
    assert ref.meta["snapped_lines"]["y"] == []
    zt = r.meta["lines"]["z"][-1]
    xs = r.meta["lines"]["x"]
    assert np.min(np.abs(xs - xe)) < 1e-14
    np.testing.assert_allclose(r.tj_max, ref.tj_max, rtol=0, atol=1e-9)
    # the point is reported at the snapped coordinate, a node; the requested one is a recorded dy away
    assert F.node_value(r, xe, sy[0][1], zt) == pytest.approx(F.node_value(ref, xe, edge, zt), abs=1e-9)
    if dy > 2e-9:
        with pytest.raises(ValueError):
            F.node_value(r, xe, edge + dy, zt)


@pytest.mark.parametrize("mode", ["layout", "box"])
def test_far_mandatory_line_is_kept_and_close_ones_merge(mode):
    """The snap distance is SNAP_FRACTION of the level-0 cell of the geometry interval holding the line: just outside it the
    line is kept, just inside it snaps; two mandatory lines 1e-7 apart give one line."""
    if mode == "layout":
        # y = 3 mm die edge; geometry interval [3, 7] mm (die), L = 4 mm, h0 = 2 mm -> 2 cells of 2 mm
        h0, edge, w = 2e-3, 3e-3, 2e-3
        mk = lambda ey: F.layout_grid(_toy_layout(), 1.0, H, TC, F.GridRule(h0=h0), 0, extra_lines=([4.5e-3], ey, None))  # noqa: E731
    else:
        # y = 4 mm source edge; geometry interval [4, 5] mm (the two sources' lower edges), L = 1 mm -> 2 cells of 0.5 mm
        h0, edge, w = 2e-3, 4e-3, 0.5e-3
        mk = lambda ey: F.box_stack_grid(A_BOX, B_BOX, _stack(), H, TC, SRC2, rule=F.GridRule(h0=h0), extra_lines=([7.3e-3], ey, None))  # noqa: E731
    g = mk([edge + 1.5 * F.SNAP_FRACTION * w])
    assert np.min(np.abs(g.y - (edge + 1.5 * F.SNAP_FRACTION * w))) < 1e-14 and g.snaps["y"] == []  # kept
    assert np.min(np.diff(g.y)) == pytest.approx(0.75 * F.SNAP_FRACTION * w, rel=1e-6)  # 2 cells: >= SNAP_FRACTION / 2 of w
    g = mk([edge + 0.5 * F.SNAP_FRACTION * w])
    assert np.sum(np.abs(g.y - edge) < 1e-5) == 1 and len(g.snaps["y"]) == 1
    assert g.snaps["y"][0][1] == pytest.approx(edge, abs=1e-15)
    g = mk([edge + 0.4 * w, edge + 0.4 * w + 1e-7])
    assert np.sum(np.abs(g.y - (edge + 0.4 * w)) < 1e-5) == 1 and len(g.snaps["y"]) == 1
    assert abs(g.snaps["y"][0][0] - g.snaps["y"][0][1] - 1e-7) < 1e-12  # the later line snapped onto the earlier one


def test_box_mapping_inverse_is_exact_in_thin_cells():
    """The face inverse map: scikit-fem's own iteration fails in a 1e-7 m cell (absolute tolerance, the cause of the
    level-1 crashes); _BoxMapping returns the reference coordinates of points mapped forward from known ones, to round-off."""
    from skfem import MeshHex
    from skfem.mapping import MappingIsoparametric

    x = np.array([10.0, 30.0, 30.0 + 1e-4, 31.0])  # mm, as in the solver: cell 1 is 1e-4 mm = 1e-7 m wide
    m = MeshHex.init_tensor(x, np.array([0.0, 2.0]), np.array([0.0, 1.0]))
    e = int(np.argmin(np.ptp(m.p[0, m.t], axis=0)))  # the thin cell
    rng = np.random.default_rng(20261103)
    Xref = rng.random((3, 1, 9))
    Xref[0, 0, :3] = 0.0  # points on a face, as FacetBasis passes them
    pts = MappingIsoparametric(m, m.elem(), m.bndelem).F(Xref, tind=np.array([e]))  # the forward (affine) map
    assert np.ptp(pts[0]) < 1.1e-4  # the points do lie in the thin cell
    with pytest.raises(Exception, match="Newton"):
        MappingIsoparametric(m, m.elem(), m.bndelem).invF(pts, tind=np.array([e]))
    got = F._BoxMapping(m, m.elem(), m.bndelem).invF(pts, tind=np.array([e]))
    # reference-space error of a point known to eps |x| = 7e-15 mm in a 1e-4 mm cell: <= ~1e-10
    np.testing.assert_allclose(got, Xref, rtol=0, atol=1e-9)
    # a regular cell: the same points as scikit-fem's own inverse (bit-identical path)
    e2 = int(np.argmax(np.ptp(m.p[0, m.t], axis=0)))
    p2 = MappingIsoparametric(m, m.elem(), m.bndelem).F(Xref, tind=np.array([e2]))
    np.testing.assert_array_equal(F._BoxMapping(m, m.elem(), m.bndelem).invF(p2, tind=np.array([e2])),
                                  MappingIsoparametric(m, m.elem(), m.bndelem).invF(p2, tind=np.array([e2])))


@pytest.mark.parametrize("order", [1, 2])
def test_thin_layer_cells_solve_to_the_1d_closed_form(order):
    """A 0.4 um layer (cells of 0.4 um at level 0, 0.2 um at level 1) under a source covering the whole top: the exact
    solution is 1D and linear in each layer, T_top = Tc + q (1/h + sum t_i / k_i), q = P / (a b) (series thermal
    resistances; Incropera, Fundamentals of Heat and Mass Transfer, 6th ed., eq. 3.19), which Q1 and Q2 reproduce exactly.
    The face inverse map failed here before _BoxMapping."""
    a = b = 8e-3
    layers = [F.BoxLayer(1e-3, 100.0, 1), F.BoxLayer(4e-7, 5.0, 1)]
    P, h = 10.0, 2000.0
    q = P / (a * b)
    exact = TC + q * (1.0 / h + 1e-3 / 100.0 + 4e-7 / 5.0)
    for lv in (0, 1):
        r = F.solve_box_stack(a, b, layers, h, TC, [(0.0, 0.0, a, b, P)], rule=F.GridRule(h0=8e-3, element_order=order),
                              level=lv, constant_k=True)
        assert np.min(np.diff(r.meta["lines"]["z"])) == pytest.approx(4e-7 / 2**lv, rel=1e-6)
        np.testing.assert_allclose(r.tj_max, exact, rtol=0, atol=1e-7)
        np.testing.assert_allclose(r.tj_mean, exact, rtol=0, atol=1e-7)
        assert r.energy_balance < 1e-9


# a small box with a 1 mm source gap (x cells of 0.5 mm) and a 0.1 mm attach layer (one z cell): kept lines just outside
# the snap distance there give the thinnest cells the rule allows (x: 3.75 um, z: 1.5 um at level 0; halved per level)
_BAND_LAYERS = [F.BoxLayer(2e-3, 390.0, 1, "base"), F.BoxLayer(0.1e-3, 60.0, 1, "attach"), F.BoxLayer(0.18e-3, 120.0, 1, "die")]
_BAND_SRC = [(4e-3, 4e-3, 8e-3, 12e-3, 20.0), (9e-3, 4e-3, 12e-3, 12e-3, 15.0)]


@pytest.mark.parametrize("order", [1, 2])
def test_kept_line_just_outside_snap_distance_solves_above_level_0_box(order):
    """Lines at 1.5 x and 0.5 x the snap distance from a source edge (x, gap [8, 9] mm: cell 0.5 mm), a source edge (y,
    interval [4, 12] mm: cell 4 mm), below the base / attach interface (z, base cell 2 mm) and below the attach / die
    interface (z, attach cell 0.1 mm): the 1.5 x lines are kept (z cells of the layer count, 1: 1.5 um), the 0.5 x ones snap, and every grid solves at levels 0-2 (Q1) and 0-1 (Q2) with the energy balanced. The attempt-1 rule
    crashed at level 1 on such lines."""
    f = F.SNAP_FRACTION
    z_ba, z_ad = 2e-3, 2.1e-3
    rule = F.GridRule(h0=4e-3, element_order=order)
    kept = ([8e-3 + 1.5 * f * 0.5e-3], [4e-3 + 1.5 * f * 4e-3], [z_ba - 1.5 * f * 2e-3, z_ad - 1.5 * f * 0.1e-3])
    snapped = ([8e-3 + 0.5 * f * 0.5e-3], [4e-3 + 0.5 * f * 4e-3], [z_ad - 0.5 * f * 0.1e-3])
    prev = None
    for lv in range(3 if order == 1 else 2):
        r = F.solve_box_stack(16e-3, 16e-3, _BAND_LAYERS, H, TC, _BAND_SRC, rule=rule, level=lv, extra_lines=kept)
        assert r.meta["max_snap_m"] == 0.0
        for ax, vals in zip("xyz", kept, strict=True):
            for v in vals:
                assert np.min(np.abs(r.meta["lines"][ax] - v)) < 1e-15
        assert np.min(np.diff(r.meta["lines"]["z"])) == pytest.approx(1.5 * f * 0.1e-3 / 2**lv, rel=1e-6)
        assert np.min(np.diff(r.meta["lines"]["x"])) == pytest.approx(0.75 * f * 0.5e-3 / 2**lv, rel=1e-6)
        assert r.energy_balance < 1e-8 and np.all(r.tj_max > TC + 1.0)
        if prev is not None:
            assert np.all(np.abs(r.tj_max - prev) < 0.5)  # a converging sequence, not a broken solve
        prev = r.tj_max
        rs = F.solve_box_stack(16e-3, 16e-3, _BAND_LAYERS, H, TC, _BAND_SRC, rule=rule, level=lv, extra_lines=snapped)
        got = {ax: [u for _, u in rs.meta["snapped_lines"][ax]] for ax in "xyz"}
        assert got["x"] == [pytest.approx(8e-3, abs=1e-15)] and got["y"] == [pytest.approx(4e-3, abs=1e-15)]
        assert got["z"] == [pytest.approx(z_ad, abs=1e-15)] and rs.energy_balance < 1e-8
        assert rs.meta["max_snap_m"] == pytest.approx(0.5 * f * 4e-3, rel=1e-9)  # the largest requested move (y)
        assert np.isfinite(F.node_value(rs, 8e-3, 4e-3, z_ad))  # the snapped point is a node


def test_kept_line_just_outside_snap_distance_solves_above_level_0_layout():
    """Layout mode: lines 1.5 x the snap distance from the die edge y = 3 mm (cell 4 mm at h0 = 8 mm) and from the top-Cu
    / die-attach plane (one attach cell) are kept and solve at levels 0 and 1 (Q1) and 0 (Q2)."""
    lay = _toy_layout()
    f, zt = F.SNAP_FRACTION, lay.stack.z_top("top_cu")
    att = lay.dies[0].attach_thickness
    ex = ([4.5e-3], [3e-3 + 1.5 * f * 4e-3], [zt + 1.5 * f * att])
    for order, levels in ((1, (0, 1)), (2, (0,))):
        for lv in levels:
            r = F.solve_layout(lay, [40.0, 20.0], H, TC, rule=F.GridRule(h0=8e-3, element_order=order), level=lv,
                               extra_lines=ex)
            assert r.meta["max_snap_m"] == 0.0 and r.energy_balance < 1e-8 and np.all(r.tj_max > TC + 1.0)
            assert np.min(np.abs(r.meta["lines"]["z"] - ex[2][0])) < 1e-15
            assert np.min(np.abs(r.meta["lines"]["y"] - ex[1][0])) < 1e-15


def test_extra_lines_same_inputs_in_both_modes():
    """extra_lines entries may be None, a scalar, a list, a tuple or an array in layout and box-stack mode alike; scalar
    and one-element list give the identical grid."""
    forms = [(5e-3, 6.1e-3, 1.5e-4), ([5e-3], [6.1e-3], [1.5e-4]), ((5e-3,), (6.1e-3,), (1.5e-4,)),
             (np.array(5e-3), np.array([6.1e-3]), np.float64(1.5e-4))]
    rule = F.GridRule(h0=2e-3, dz_max=5e-4)
    for build in (lambda e: F.layout_grid(_toy_layout(), 1.0, H, TC, rule, 0, extra_lines=e),
                  lambda e: F.box_stack_grid(A_BOX, B_BOX, _stack(), H, TC, SRC2, rule=rule, extra_lines=e)):
        ref = build(forms[1])
        for f in forms:
            g = build(f)
            for u, v in ((g.x, ref.x), (g.y, ref.y), (g.z, ref.z)):
                np.testing.assert_array_equal(u, v)
        assert np.min(np.abs(ref.x - 5e-3)) < 1e-14 and np.min(np.abs(ref.y - 6.1e-3)) < 1e-14
        build((5e-3, None, None))  # None entries
        with pytest.raises(ValueError):
            build(([1.0], [0.0]))
