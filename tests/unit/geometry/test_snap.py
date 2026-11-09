"""Tests of geometry.snap (T0257): identity on grid layouts, idempotence, half-step bound, staircase, nets, lattice."""
import dataclasses
import importlib.util
from pathlib import Path

import numpy as np
import pytest
from shapely.geometry import Polygon, box

from moduleforge.drc.rules import DesignRules, check
from moduleforge.generate.halfbridge import generate_layouts
from moduleforge.geometry.layout import Layout, Trace
from moduleforge.geometry.snap import GRIDS, snap_layout, snap_value
from moduleforge.solvers import l2_layout as L2

MM = 1e-3
ROOT = Path(__file__).resolve().parents[3]


def _case4(variant="base"):
    spec = importlib.util.spec_from_file_location("o006_case4", ROOT / "research/scripts/o006_case4_layout.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m.build(variant)


def _fp_equal(a: Layout, b: Layout) -> bool:
    return a.fingerprint() == b.fingerprint()


@pytest.mark.parametrize("grid", GRIDS)
def test_identity_on_generator_layouts(grid):
    for lay in generate_layouts(6, seed=11):
        r = snap_layout(lay, grid)
        assert _fp_equal(r.layout, lay) and r.records == [] and r.violations == []


def test_tie_rule_and_values():
    g = 0.5 * MM
    assert snap_value(0.25 * MM, g) == pytest.approx(0.5 * MM)  # exact half -> higher line
    assert snap_value(-0.25 * MM, g) == 0.0  # also toward +inf
    assert snap_value(0.2499 * MM, g) == 0.0
    assert snap_value(1.2501 * MM, g) == pytest.approx(1.5 * MM)
    assert snap_value(1.25 * MM + 1e-15, g) == snap_value(1.25 * MM - 1e-15, g)  # float noise does not flip a tie


def _offgrid_case4():
    """Case 4 shifted by an off-grid amount so every edge needs snapping (identity does not apply)."""
    lay = _case4()
    s = (0.13 * MM, -0.31 * MM)
    from shapely.affinity import translate
    t = lambda p: translate(p, *s)  # noqa: E731
    out = dataclasses.replace(
        lay, outline=t(lay.outline), baseplate_outline=t(lay.baseplate_outline),
        traces=[Trace(x.net, t(x.polygon)) for x in lay.traces])
    for d in out.dies:
        d.cx += s[0]; d.cy += s[1]  # noqa: E702
        d.pads = {k: (p[0] + s[0], p[1] + s[1], p[2] + s[0], p[3] + s[1]) for k, p in d.pads.items()}
    for w in out.wires:
        w.points = w.points + np.array([s[0], s[1], 0.0])
    for tm in out.terminals.values():
        tm.cx += s[0]; tm.cy += s[1]  # noqa: E702
    return out


@pytest.mark.parametrize("grid", GRIDS)
def test_idempotent_and_half_step_bound_and_nets_kept(grid):
    lay = _offgrid_case4()
    r = snap_layout(lay, grid, DesignRules(min_spacing=0.5 * MM, die_edge_margin=0.5 * MM))
    assert r.records, "an off-grid layout must produce snaps"
    edge = [q for q in r.records if q.kind == "edge"]
    assert edge and all(q.displacement <= grid / 2 + 1e-12 for q in edge)
    r2 = snap_layout(r.layout, grid)
    assert _fp_equal(r2.layout, r.layout) and r2.records == []
    assert [t.net for t in r.layout.traces] == [t.net for t in lay.traces]
    for i, a in enumerate(r.layout.traces):
        for b in r.layout.traces[i + 1:]:
            if a.net != b.net:
                assert a.polygon.distance(b.polygon) > 0
    assert not [v for v in r.violations if v.rule == "net_merged"]
    # every snapped x/y coordinate of the copper is a multiple of the grid
    for t in r.layout.traces:
        c = np.asarray(t.polygon.exterior.coords) / grid
        assert np.allclose(c, np.round(c), atol=1e-9)


def test_case4_is_on_the_grid_and_dies_snap_identically_everywhere():
    for v in ("base", "die_shift", "trace_width"):
        lay = _case4(v)
        assert _fp_equal(snap_layout(lay, 0.5 * MM).layout, lay)
    # same die rectangle in two different layouts -> same snapped footprint
    a, b = _offgrid_case4(), _offgrid_case4()
    b.traces = b.traces[::-1]
    da = snap_layout(a, 0.25 * MM).layout.dies
    db = snap_layout(b, 0.25 * MM).layout.dies
    assert [(d.cx, d.cy, d.w, d.h) for d in da] == [(d.cx, d.cy, d.w, d.h) for d in db]


def test_wire_ends_move_only_as_needed():
    lay = _case4()
    # shrink nothing: wire ends already on their pads must not move at a coarser grid than 0.25? (feet at +0.125 offsets)
    r = snap_layout(lay, 0.5 * MM)
    for w0, w1 in zip(lay.wires, r.layout.wires, strict=True):
        assert np.allclose(w0.points, w1.points, atol=1e-12)
    # an off-grid pad: the end moves by no more than the copper edge moved plus the landing margin
    off = _offgrid_case4()
    rr = snap_layout(off, 0.5 * MM)
    for q in rr.records:
        if q.kind == "wire":
            assert q.displacement <= 0.5 * MM + 0.3 * MM + 1e-9
    for w in rr.layout.wires:
        end = w.points[-1]
        assert any(t.net == w.net and t.polygon.contains(box(end[0], end[1], end[0], end[1]).centroid)
                   for t in rr.layout.traces)


def _fixture(poly):
    lay = _case4()
    return dataclasses.replace(lay, traces=[Trace("DC+", poly)])


def _snap_trace(poly, g):
    lay = _fixture(poly)
    lay.dies, lay.wires, lay.terminals = [], [], {}
    return snap_layout(lay, g)


@pytest.mark.parametrize("g", GRIDS)
def test_staircase_area_error_diagonal_and_triangle(g):
    # triangle 10 x 10 mm: exact area 50 mm^2; each cut cell contributes <= g^2/2, and symmetric errors mostly cancel
    tri = Polygon([(20 * MM, 20 * MM), (30 * MM, 20 * MM), (20 * MM, 30 * MM)])
    # parallelogram strip along the 45-degree diagonal (width 3 mm in x)
    dia = Polygon([(20 * MM, 20 * MM), (23 * MM, 20 * MM), (33 * MM, 30 * MM), (30 * MM, 30 * MM)])
    for poly in (tri, dia):
        r = _snap_trace(poly, g)
        new = r.layout.traces[0].polygon
        # independent bound: every cell cut by the boundary (partial coverage) contributes at most g^2 / 2
        i = np.arange(int(18 * MM / g), int(35 * MM / g))
        cells = [box(a * g, b * g, (a + 1) * g, (b + 1) * g) for a in i for b in i]
        n_cut = sum(1 for c in cells if c.intersects(poly.boundary) and 1e-9 < c.intersection(poly).area / c.area < 1 - 1e-9)
        assert n_cut > 0 and abs(new.area - poly.area) <= 0.5 * g * g * n_cut * (1 + 1e-9)
        # exact 45-degree ties all round up (documented rule): the error sits at the bound's scale, it does not cancel
        assert any(q.kind == "staircase" for q in r.records)
        c = np.asarray(new.exterior.coords) / g
        assert np.allclose(c, np.round(c), atol=1e-9)
        # staircase boundary stays within one cell diagonal of the original
        assert max(q.displacement for q in r.records if q.kind == "staircase") <= g * 2 ** 0.5 + 1e-12
    # error shrinks with the grid on the triangle
    errs = [abs(_snap_trace(tri, gg).layout.traces[0].polygon.area - tri.area) for gg in GRIDS]
    assert errs[2] <= errs[0] + 1e-18


def test_merging_nets_are_reported_not_repaired():
    lay = _case4()
    a = box(20 * MM, 45 * MM, 40 * MM, 49.8 * MM)
    b = box(20 * MM, 50.2 * MM, 40 * MM, 60 * MM)  # 0.4 mm gap, snaps to touching at 0.5 mm? 49.8->50, 50.2->50
    lay = dataclasses.replace(lay, traces=[Trace("DC-", a), Trace("PHASE", b)])
    lay.dies, lay.wires = [], []
    r = snap_layout(lay, 0.5 * MM)
    assert any(v.rule == "net_merged" for v in r.violations)
    assert any(v.rule == "min_spacing" for v in r.violations)
    assert r.layout.traces[0].net == "DC-" and r.layout.traces[1].net == "PHASE"


def test_die_enclosure_recheck_reports():
    lay = _case4()
    rules = DesignRules()
    assert not [v for v in check(lay, rules) if v.rule == "die_edge_margin"]
    off = _offgrid_case4()
    r = snap_layout(off, 0.5 * MM, DesignRules(die_edge_margin=2.5 * MM))
    assert any(v.rule == "die_edge_margin" for v in r.violations)  # reported, layout not altered to fix it


@pytest.mark.parametrize("grid,cells", [(0.5 * MM, (0.5 * MM,)), (0.25 * MM, (0.5 * MM, 0.25 * MM))])
def test_snapped_layout_exact_on_l2_lattice(grid, cells):
    lay = snap_layout(_offgrid_case4(), grid).layout
    cm = lay.to_conductors()
    saved = L2.CELL
    try:
        for cell in cells:
            L2.CELL = (cell,) + tuple(saved[1:])
            lat = L2.layout_lattice(cm, 0)
            fill = L2.cell_fill(cm, *lat)
            for d in cm.shorts:
                L2.check_on_lattice(d.x - d.w / 2, d.x + d.w / 2, d.y - d.h / 2, d.y + d.h / 2, *lat[:4], "die")
            assert max(abs(r - e) / e for r, e in fill["area"].values()) < 1e-12
    finally:
        L2.CELL = saved
