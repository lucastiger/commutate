"""Source-edge grading of the scikit-fem thermal reference (T0227, port of the T0225 probe's option (a)): offsets, gaps,
nesting over levels, geometry-only lines, a 1-D analytic slab, energy balance and mirror symmetry."""
from __future__ import annotations

import numpy as np
import pytest
from shapely.geometry import box

from moduleforge.geometry.layout import Die, Layout, Trace
from moduleforge.geometry.stack import default_dbc_stack
from moduleforge.solvers import thermal_fem as F

GRADING = (1e-4, 2.5, 4e-3, 0.5)
TC, H = 338.15, 5000.0
A, B = 24e-3, 16e-3
SRC = [(5e-3, 4e-3, 11e-3, 12e-3, 30.0), (14e-3, 5e-3, 19e-3, 11e-3, 20.0)]


def _rule(grading=GRADING, **kw) -> F.GridRule:
    return F.GridRule(h0=4e-3, nz={}, default_nz=1, zrefine=True, near_margin=2e-3, dz_max=1e-3, edge_grading=grading, **kw)


def _stack(k=lambda T: 150.0 - 0.1 * (T - 300.0)) -> list:
    return [F.BoxLayer(2.0e-3, 390.0, 1, "base"), F.BoxLayer(0.38e-3, 25.0, 1, "cer"), F.BoxLayer(0.3e-3, k, 1, "cu"),
            F.BoxLayer(0.1e-3, 60.0, 1, "att"), F.BoxLayer(0.18e-3, 120.0, 1, "die")]


def _toy_layout() -> Layout:
    outline = box(0.0, 0.0, 20e-3, 10e-3)
    d1 = Die(6e-3, 5e-3, 4e-3, 4e-3, "HS", {})
    d2 = Die(14e-3, 5e-3, 4e-3, 4e-3, "LS", {})
    return Layout("toy", 1, outline, [Trace("DC+", box(2e-3, 2e-3, 18e-3, 8e-3))], [d1, d2], [], {},
                  box(-3e-3, -3e-3, 23e-3, 13e-3), default_dbc_stack())


def _box_grid(rule, level=0, srcs=SRC, **kw):
    return F.box_stack_grid(A, B, _stack(), H, TC, srcs, rule=rule, level=level, **kw)


def test_offsets_match_spec():
    offs, steps = F._grading_offsets(GRADING)
    assert np.allclose(offs, [0.1e-3, 0.25e-3, 0.625e-3, 1.5625e-3, 3.90625e-3], rtol=1e-12, atol=0)
    assert np.allclose(steps, [0.1e-3, 0.15e-3, 0.375e-3, 0.9375e-3, 2.34375e-3], rtol=1e-12, atol=0)


def test_default_is_unchanged():
    g0 = _box_grid(F.GridRule(h0=4e-3, nz={}, default_nz=1, near_margin=2e-3, dz_max=1e-3))
    g1 = _box_grid(_rule())
    assert g0.grading == {"x": [], "y": []}
    assert g1.x.size > g0.x.size and g1.y.size > g0.y.size
    assert F.GridRule().edge_grading is None
    with pytest.raises(ValueError):
        F.GridRule(edge_grading=(1e-4, 1.0, 4e-3, 0.5))


def _check_gaps(lines, extents, lo, hi, fixed):
    gap = GRADING[3]
    _, steps = F._grading_offsets(GRADING)
    offs, _ = F._grading_offsets(GRADING)
    fixed = list(fixed) + [lo, hi] + [v for e in extents for v in e]
    for i, v in enumerate(lines):
        assert lo < v < hi
        # the step of this line: the finest step it can belong to is that of the nearest offset from some edge
        s = min(steps[int(np.argmin(np.abs(np.array(offs) - abs(v - e))))] for ex in extents for e in ex)
        others = fixed + [w for j, w in enumerate(lines) if j != i]
        assert min(abs(v - w) for w in others) >= gap * min(steps) - 1e-15
        assert min(abs(v - w) for w in fixed) >= gap * s - 1e-15


def test_gaps_and_domain_box_and_layout():
    g = _box_grid(_rule())
    ext_x, ext_y = [(s[0], s[2]) for s in SRC], [(s[1], s[3]) for s in SRC]
    cx, cy = [0.5 * (s[0] + s[2]) for s in SRC], [0.5 * (s[1] + s[3]) for s in SRC]
    _check_gaps(g.grading["x"], ext_x, 0.0, A, cx)
    _check_gaps(g.grading["y"], ext_y, 0.0, B, cy)
    # pairwise: any two grading lines are at least min_gap * (the finer step) apart, i.e. >= 0.5 * 0.1 mm
    for v in (g.grading["x"], g.grading["y"]):
        assert np.all(np.diff(v) >= GRADING[3] * GRADING[0] - 1e-15)
    lay = _toy_layout()
    gl = F.layout_grid(lay, 1.0, H, TC, _rule(), 0)
    bx, by = lay.baseplate_outline.bounds[0::2], lay.baseplate_outline.bounds[1::2]
    for v, lo, hi in ((gl.grading["x"], *bx), (gl.grading["y"], *by)):
        assert len(v) > 0 and min(v) > lo and max(v) < hi
        assert np.all(np.diff(v) >= GRADING[3] * GRADING[0] - 1e-15)
    # no sliver next to any outline line of the layout
    xs = np.unique(np.concatenate([np.array(p.exterior.coords)[:, 0] for p in (lay.outline, lay.baseplate_outline)]
                                  + [np.array(t.polygon.exterior.coords)[:, 0] for t in lay.traces]))
    for v in gl.grading["x"]:
        assert np.min(np.abs(xs - v)) >= GRADING[3] * GRADING[0] - 1e-15


@pytest.mark.parametrize("mode", ["box", "layout"])
def test_level0_lines_are_nodes_at_levels_1_2(mode):
    def grid(lv):
        if mode == "box":
            return _box_grid(_rule(), lv)
        return F.layout_grid(_toy_layout(), 1.0, H, TC, _rule(), lv)
    g0, g1, g2 = grid(0), grid(1), grid(2)
    for ax in "xyz":
        l0 = getattr(g0, ax)
        for gl in (g1, g2):
            fine = getattr(gl, ax)
            assert all(np.min(np.abs(fine - v)) < 1e-14 for v in l0)
    # lateral level-0 cells are bisected exactly
    assert (g1.x.size - 1) == 2 * (g0.x.size - 1) and (g2.y.size - 1) == 4 * (g0.y.size - 1)


def test_grading_depends_only_on_geometry():
    r = _rule()
    grids = [F.box_stack_grid(A, B, _stack(), h, TC, [(s[0], s[1], s[2], s[3], p * s[4]) for s in SRC], rule=r)
             for h, p in ((H, 1.0), (2 * H, 3.0))]
    for ax in "xy":
        assert np.array_equal(grids[0].grading[ax], grids[1].grading[ax])
        assert np.array_equal(getattr(grids[0], ax), getattr(grids[1], ax))
    lay = _toy_layout()
    ga, gb = (F.layout_grid(lay, p, h, TC, r, 0) for h, p in ((H, 1.0), (3 * H, 7.0)))
    for ax in "xy":
        assert np.array_equal(getattr(ga, ax), getattr(gb, ax))


def test_two_layer_slab_series_resistance():
    """Constant k, uniform flux q over the whole top face, Robin bottom: T_top = T_c + q/h + q sum(t_i/k_i), exact for Q1."""
    layers = [F.BoxLayer(1.0e-3, 200.0, 1, "a"), F.BoxLayer(0.4e-3, 30.0, 1, "b")]
    a, b, P = 10e-3, 8e-3, 12.0
    q = P / (a * b)
    exact = TC + q / H + q * sum(la.t / la.k for la in layers)
    r = F.GridRule(h0=4e-3, nz={}, default_nz=1, near_margin=2e-3, dz_max=0.5e-3, edge_grading=GRADING)
    res = F.solve_box_stack(a, b, layers, H, TC, [(0.0, 0.0, a, b, P)], rule=r)
    assert res.meta["grading_lines"]["x"] > 0 and res.meta["grading_lines"]["y"] > 0  # inward lines of the full face
    assert np.max(np.abs(res.tj_max / exact - 1.0)) < 1e-9
    assert abs(res.tj_mean[0] / exact - 1.0) < 1e-9
    # two abutting sources that together cover the face: the 1-D result again, on a grid graded around x = a/2 too
    srcs = [(0.0, 0.0, a / 2, b, P / 2), (a / 2, 0.0, a, b, P / 2)]
    res2 = F.solve_box_stack(a, b, layers, H, TC, srcs, rule=r)
    assert res2.meta["grading_lines"]["x"] > 0
    assert np.max(np.abs(res2.tj_max / exact - 1.0)) < 1e-9


def test_energy_balance_graded_box_stack():
    res = F.solve_box_stack(A, B, _stack(), H, TC, SRC, rule=_rule())
    assert res.energy_balance <= 1e-6
    assert res.meta["grading_lines"]["x"] > 0 and res.meta["edge_grading"] == list(GRADING)


def test_mirror_symmetry():
    a, b = 20e-3, 12e-3
    src = [(7e-3, 4e-3, 13e-3, 8e-3, 25.0)]  # centred about (a/2, b/2)
    r = _rule()
    g = F.box_stack_grid(a, b, _stack(), H, TC, src, rule=r)
    for ax, L in (("x", a), ("y", b)):
        v = np.array(g.grading[ax])
        assert np.allclose(np.sort(L - v), v, rtol=0, atol=1e-12)
        ln = getattr(g, ax)
        assert np.allclose(np.sort(L - ln), ln, rtol=0, atol=1e-12)
    res = F.solve_box_stack(a, b, _stack(), H, TC, src, rule=r)
    pts = res.nodes
    T = res.T
    key = {tuple(np.round(p, 12)): t for p, t in zip(pts, T, strict=True)}
    worst = 0.0
    for p, t in zip(pts, T, strict=True):
        for m in ((a - p[0], p[1], p[2]), (p[0], b - p[1], p[2])):
            worst = max(worst, abs(key[tuple(np.round(m, 12))] - t))
    assert worst < 1e-9
