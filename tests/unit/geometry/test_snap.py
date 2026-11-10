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


# --- T0268: review T0264 fixes, hand-computed expectations (lengths in mm unless wrapped by MM) -----------------------
from shapely.geometry import LineString  # noqa: E402

from moduleforge.geometry.layout import Die, Terminal, arc_wire  # noqa: E402
from moduleforge.geometry.snap import CHECKED_RULES, _move_into  # noqa: E402


def _chamfered(xl, xr, yb=20.0, yt=30.0):
    """Rectangle (mm) with a 2 mm 45-degree chamfer at the top right: non-rectilinear, so it is staircased."""
    return Polygon([(xl * MM, yb * MM), (xr * MM, yb * MM), (xr * MM, (yt - 2) * MM), ((xr - 2) * MM, yt * MM),
                    (xl * MM, yt * MM)])


def _bounds_mm(poly):
    return tuple(round(b / MM, 9) for b in poly.bounds)


@pytest.mark.parametrize("xl,xl_snapped", [(20.3, 20.5), (20.2, 20.0)])
def test_staircase_threshold_is_one_half(xl, xl_snapped):
    # left column cells are covered by (20.5 - xl) / 0.5 = 0.4 (out) or 0.6 (in): a 0.3 or a 0.7 threshold gets one wrong
    r = _snap_trace(_chamfered(xl, 30.0), 0.5 * MM)
    assert _bounds_mm(r.layout.traces[0].polygon)[0] == xl_snapped
    assert any(q.kind == "staircase" for q in r.records)


@pytest.mark.parametrize("xr,xr_snapped", [(30.2, 30.0), (30.3, 30.5)])
def test_staircase_threshold_right_edge(xr, xr_snapped):
    # right column [30, 30.5] is covered (xr - 30) / 0.5 = 0.4 (out) or 0.6 (in)
    r = _snap_trace(_chamfered(20.0, xr), 0.5 * MM)
    assert _bounds_mm(r.layout.traces[0].polygon)[2] == xr_snapped


def test_staircase_ties_round_outward_and_differ_from_vertex_snapping():
    # every edge exactly half-way between lines: cells are exactly half covered, hence in -> left/bottom go DOWN, right/top UP
    g = 0.5 * MM
    r = _snap_trace(_chamfered(20.25, 30.25, 20.25, 30.25), g)
    assert _bounds_mm(r.layout.traces[0].polygon) == (20.0, 20.0, 30.5, 30.5)
    assert snap_value(20.25 * MM, g) == pytest.approx(20.5 * MM)  # the vertex / rectangle rule goes up instead
    # a rectilinear polygon with the same left edge takes the vertex rule
    rect = _snap_trace(Polygon([(20.25 * MM, 20 * MM), (30 * MM, 20 * MM), (30 * MM, 30 * MM), (20.25 * MM, 30 * MM)]), g)
    assert _bounds_mm(rect.layout.traces[0].polygon)[0] == 20.5


@pytest.mark.parametrize("off,corner_in", [(0.145, True), (0.15, False), (0.1, True), (0.2, False)])
def test_staircase_convex_corner_cell_rule(off, corner_in):
    # both corner edges are `off` mm inside the cell's lower-left corner (20, 20): the edges cover f = (0.5 - off) / 0.5 of the
    # cell each, the corner cell f * f = 0.5041 (off .145) / 0.49 (.15) / 0.64 (.1) / 0.36 (.2); in iff f * f >= 1/2
    poly = _chamfered(20.0 + off, 30.0, 20.0 + off, 30.0)
    new = _snap_trace(poly, 0.5 * MM).layout.traces[0].polygon
    from shapely.geometry import Point
    corner, nb_x, nb_y = Point(20.25 * MM, 20.25 * MM), Point(20.75 * MM, 20.25 * MM), Point(20.25 * MM, 20.75 * MM)
    assert new.contains(nb_x) and new.contains(nb_y)  # f * 1 = 0.7 .. 0.9 -> in
    assert new.contains(corner) == corner_in


def _wire_fixture(trace_y0=3.3, trace_x=(26.0, 36.0), wires=(((19.0, 4.35), (31.0, 4.35)), ((19.0, 3.7), (31.0, 3.7))),
                  terminals=None):
    """HS die 17.3-20.7 x 3-7 mm on DC+ copper, source pad 17.4-20.6 (reaches past the snapped footprint), PHASE copper
    to its right; straight-in-plane wires (start -> end, mm) with 1 mm sine loop. Grid 0.5 mm."""
    mm = lambda *v: tuple(x * MM for x in v)  # noqa: E731
    die = Die(19.0 * MM, 5.0 * MM, 3.4 * MM, 4.0 * MM, "HS", {"source": mm(17.4, 3.5, 20.6, 6.5)})
    ws = [arc_wire(mm(*a), mm(*b), 0.0, 0.0, 1.0 * MM, 0.3 * MM, "PHASE") for a, b in wires]
    return Layout(
        "t", 1, box(*mm(0, 0, 40, 20)),
        [Trace("DC+", box(*mm(14, 0, 24, 10))), Trace("PHASE", box(*mm(trace_x[0], trace_y0, trace_x[1], 10)))],
        [die], ws, terminals or {}, box(*mm(0, 0, 40, 20)))


def test_wire_end_relocation_and_pad_clip():
    lay = _wire_fixture()
    # PHASE copper lower edge 3.3 -> 3.5; landing region eroded by 0.3 mm starts at y = 3.8; wire 1 ends at y = 3.7 -> 3.8
    r = snap_layout(lay, 0.5 * MM)
    w0, w1 = r.layout.wires
    assert np.allclose(w0.points, lay.wires[0].points, atol=1e-15)  # wire 0 ends at y = 4.35 >= 3.8: untouched
    assert np.allclose(w1.points[0], lay.wires[1].points[0], atol=1e-15)
    assert w1.points[-1, 0] == pytest.approx(31.0 * MM, abs=1e-12) and w1.points[-1, 1] == pytest.approx(3.8 * MM, abs=1e-12)
    # interior points follow linearly in index (7 points), z untouched
    dy = np.arange(7) / 6 * 0.1 * MM
    assert np.allclose(w1.points[:, 1] - lay.wires[1].points[:, 1], dy, atol=1e-12)
    assert np.array_equal(w1.points[:, 2], lay.wires[1].points[:, 2])
    assert np.allclose(w1.points[:, 0], lay.wires[1].points[:, 0], atol=1e-15)
    rec = [q for q in r.records if q.kind == "wire"]
    assert [q.element for q in rec] == ["wire[1] end"] and rec[0].displacement == pytest.approx(0.1 * MM, abs=1e-12)
    # the relocated end is on the landing copper, inside the 0.3 mm margin, so the landing rule is clean
    assert not [v for v in check(r.layout) if v.rule in ("wire_landing", "wire_start")]
    # die 17.3-20.7 -> 17.5-20.5 (shrinks); its source pad 17.4-20.6 is clipped to 17.5-20.5
    clip = [q for q in r.records if q.kind == "clip"]
    assert len(clip) == 1 and clip[0].element == "die[0] pad source"
    assert np.allclose(clip[0].after, np.array([17.5, 3.5, 20.5, 6.5]) * MM, atol=1e-12)
    assert clip[0].displacement == pytest.approx(0.1 * MM, abs=1e-12)
    assert np.allclose(r.layout.dies[0].pads["source"], np.array([17.5, 3.5, 20.5, 6.5]) * MM, atol=1e-12)


def test_move_into_nearest_point_of_region():
    region = box(0, 0, 2 * MM, 2 * MM)
    assert _move_into(region, 1 * MM, 1 * MM) == (1 * MM, 1 * MM)  # inside: unchanged
    assert _move_into(region, 3 * MM, 1 * MM) == pytest.approx((2 * MM, 1 * MM))  # face
    assert _move_into(region, 3 * MM, 3 * MM) == pytest.approx((2 * MM, 2 * MM))  # corner
    assert _move_into(region, 1 * MM, -0.5 * MM) == pytest.approx((1 * MM, 0.0))


def test_terminal_snapping_value_and_record():
    tm = Terminal("PHASE", 29.0 * MM - 0.1 * MM, 5.0 * MM, 3.8 * MM, 6.0 * MM)  # x 27.0-30.8 -> 27.0-31.0; y 2-8 on grid
    lay = _wire_fixture(trace_y0=3.0, wires=(((19.0, 5.0), (31.1, 5.0)),), terminals={"PHASE": tm})
    r = snap_layout(lay, 0.5 * MM)
    t = r.layout.terminals["PHASE"]
    assert (t.cx, t.cy, t.w, t.h) == pytest.approx((29.0 * MM, 5.0 * MM, 4.0 * MM, 6.0 * MM), abs=1e-12)
    rec = [q for q in r.records if q.element == "terminal PHASE"]
    assert len(rec) == 1 and rec[0].displacement == pytest.approx(0.2 * MM, abs=1e-12)
    assert np.allclose(rec[0].after, np.array([27.0, 2.0, 31.0, 8.0]) * MM, atol=1e-12)


def test_collapsing_hole_raises_value_error_naming_the_feature():
    # a 0.15 mm square hole whose edges both snap to 24.0: ring with < 3 distinct points (shapely raises GEOSException)
    big = box(20 * MM, 20 * MM, 30 * MM, 30 * MM)
    hole = box(24.05 * MM, 24.05 * MM, 24.2 * MM, 24.2 * MM)
    with pytest.raises(ValueError, match=r"trace\[0\] DC\+"):
        _snap_trace(Polygon(big.exterior.coords, [hole.exterior.coords]), 0.5 * MM)
    # a hole that survives (0.3 -> 0.5 wide) is fine
    ok = box(24.1 * MM, 24.1 * MM, 24.6 * MM, 24.6 * MM)  # -> 24.0..24.5
    r = _snap_trace(Polygon(big.exterior.coords, [ok.exterior.coords]), 0.5 * MM)
    assert len(r.layout.traces[0].polygon.interiors) == 1
    assert r.layout.traces[0].polygon.area == pytest.approx((100 - 0.25) * MM * MM, rel=1e-9)


def test_recheck_reports_snapping_induced_net_split():
    # two 10 mm squares joined by a 0.1 mm wide diagonal neck: each diagonal cell is 0.0707 / 0.25 = 28 % covered -> dropped
    neck = LineString([(29 * MM, 29 * MM), (35 * MM, 35 * MM)]).buffer(0.05 * MM, cap_style="flat")
    poly = box(20 * MM, 20 * MM, 30 * MM, 30 * MM).union(box(34 * MM, 34 * MM, 44 * MM, 44 * MM)).union(neck)
    assert poly.geom_type == "Polygon"
    lay = _fixture(poly)
    lay.dies, lay.wires, lay.terminals = [], [], {}
    assert not [v for v in check(lay) if v.rule == "net_split"]
    r = snap_layout(lay, 0.5 * MM)
    sp = [v for v in r.violations if v.rule == "net_split"]
    assert len(sp) == 1 and "DC+" in sp[0].message and "2 islands" in sp[0].message


def test_recheck_reports_wire_pitch_length_and_landing_keepout():
    assert {"net_split", "wire_pitch", "wire_length", "wire_landing_keepout"} <= set(CHECKED_RULES)
    # pitch: wire 1's end moves 0.1 mm toward wire 0 (y 3.7 -> 3.8) and the clearance falls from 0.65 to 0.55 mm < 0.6 mm
    lay = _wire_fixture()
    assert not [v for v in check(lay) if v.rule == "wire_pitch"]
    r = snap_layout(lay, 0.5 * MM)
    pv = [v for v in r.violations if v.rule == "wire_pitch"]
    assert len(pv) == 1 and "wires 0/1" in pv[0].message and "5.500e-04" in pv[0].message
    # length: that move lengthens wire 1 by ~4e-7 m; a limit 1e-8 m above its original length is exceeded only after snapping
    rules = DesignRules(max_wire_length=lay.wires[1].length + 1e-8)
    assert not [v for v in check(lay, rules) if v.rule == "wire_length"]
    lv = [v for v in snap_layout(lay, 0.5 * MM, rules).violations if v.rule == "wire_length"]
    assert len(lv) == 1 and lv[0].message.startswith("wire 1 ")
    # keepout: terminal pad right edge 30.8 -> 31.0 reaches the landing point 31.1: clearance 0.3 -> 0.1 mm < 0.3 mm
    tm = Terminal("PHASE", 28.9 * MM, 5.0 * MM, 3.8 * MM, 6.0 * MM)
    lay = _wire_fixture(trace_y0=3.0, wires=(((19.0, 5.0), (31.1, 5.0)),), terminals={"PHASE": tm})
    assert not [v for v in check(lay) if v.rule == "wire_landing_keepout"]
    kv = [v for v in snap_layout(lay, 0.5 * MM).violations if v.rule == "wire_landing_keepout"]
    assert len(kv) == 1 and kv[0].message.startswith("wire 0 ")


# --- T0274: full re-check with induced / pre-existing labels; staircase raises on filled holes and split outlines -------
def test_full_recheck_labels_wire_start_induced_by_clipped_source_pad():
    # die 17.3-20.74 snaps to 17.5-20.5; source pad 20.3-20.74 is clipped to 20.3-20.5 (0.2 mm < 2 x 0.15 mm margin), so
    # _erode falls back to the whole pad and the start point (20.5, 4.35), 0.09 mm from the pad edge before, is 0 mm after
    mm = lambda *v: tuple(x * MM for x in v)  # noqa: E731
    die = Die(19.02 * MM, 5.0 * MM, 3.44 * MM, 4.0 * MM, "HS", {"source": mm(20.3, 3.5, 20.74, 6.5)})
    w = arc_wire(mm(20.5, 4.35), mm(31.0, 4.35), 0.0, 0.0, 1.0 * MM, 0.3 * MM, "PHASE")
    lay = Layout("t", 1, box(*mm(0, 0, 40, 20)),
                 [Trace("DC+", box(*mm(14, 0, 24, 10))), Trace("PHASE", box(*mm(26, 3, 36, 10)))],
                 [die], [w], {}, box(*mm(0, 0, 40, 20)))
    assert not [v for v in check(lay) if v.rule == "wire_start"]
    r = snap_layout(lay, 0.5 * MM)
    ws = [v for v in r.violations if v.rule == "wire_start"]
    assert len(ws) == 1 and ws[0].origin == "induced" and "margin" in ws[0].message


def test_full_recheck_labels_terminal_off_trace_induced_by_staircase_notch():
    # off = 0.2 mm: the corner cell [20, 20.5]^2 has coverage 0.6 * 0.6 = 0.36 < 1/2 and is dropped; the terminal (20.2-21.2)
    # snaps to 20-21 and now covers the notch
    lay = _fixture(_chamfered(20.2, 30.0, 20.2, 30.0))
    lay.dies, lay.wires = [], []
    lay.terminals = {"DC+": Terminal("DC+", 20.7 * MM, 20.7 * MM, 1.0 * MM, 1.0 * MM)}
    assert not [v for v in check(lay) if v.rule == "terminal_off_trace"]
    r = snap_layout(lay, 0.5 * MM)
    tv = [v for v in r.violations if v.rule == "terminal_off_trace"]
    assert len(tv) == 1 and tv[0].origin == "induced"


def test_full_recheck_labels_pre_existing_violation():
    # two traces 0.5 mm apart on the grid: min_spacing (1 mm) is violated before and after snapping, nothing moves
    lay = _case4()
    lay = dataclasses.replace(lay, traces=[Trace("DC-", box(20 * MM, 45 * MM, 40 * MM, 49.5 * MM)),
                                           Trace("PHASE", box(20 * MM, 50 * MM, 40 * MM, 60 * MM))])
    lay.dies, lay.wires, lay.terminals = [], [], {}
    assert [v for v in check(lay) if v.rule == "min_spacing"]
    r = snap_layout(lay, 0.5 * MM)
    ms = [v for v in r.violations if v.rule == "min_spacing"]
    assert len(ms) == 1 and ms[0].origin == "pre-existing"
    assert all(v.origin == "pre-existing" for v in r.violations)


def test_staircase_filling_a_hole_raises_naming_the_feature():
    big = _chamfered(20.0, 30.0)
    hole = box(24.05 * MM, 24.05 * MM, 24.2 * MM, 24.2 * MM)
    poly = Polygon(big.exterior.coords, [hole.exterior.coords])
    with pytest.raises(ValueError, match=r"trace\[0\] DC\+.*hole"):
        _snap_trace(poly, 0.5 * MM)
    ok = Polygon(big.exterior.coords, [box(24 * MM, 24 * MM, 25 * MM, 25 * MM).exterior.coords])
    assert len(_snap_trace(ok, 0.5 * MM).layout.traces[0].polygon.interiors) == 1


def test_staircased_outline_splitting_into_parts_raises_naming_the_outline():
    neck = LineString([(29 * MM, 29 * MM), (35 * MM, 35 * MM)]).buffer(0.05 * MM, cap_style="flat")
    poly = box(20 * MM, 20 * MM, 30 * MM, 30 * MM).union(box(34 * MM, 34 * MM, 44 * MM, 44 * MM)).union(neck)
    assert poly.geom_type == "Polygon"
    lay = dataclasses.replace(_case4(), outline=poly)
    with pytest.raises(ValueError, match=r"outline.*splits"):
        snap_layout(lay, 0.5 * MM)


def test_staircase_filling_a_hole_raises_even_when_the_trace_splits():
    # two blocks joined by a 0.1 mm 45-degree neck (dropped: the trace splits) and a 0.15 mm hole in one block
    neck = LineString([(29 * MM, 29 * MM), (35 * MM, 35 * MM)]).buffer(0.05 * MM, cap_style="flat")
    two = box(20 * MM, 20 * MM, 30 * MM, 30 * MM).union(box(34 * MM, 34 * MM, 44 * MM, 44 * MM)).union(neck)
    assert two.geom_type == "Polygon"
    poly = Polygon(two.exterior.coords, [box(24.05 * MM, 24.05 * MM, 24.2 * MM, 24.2 * MM).exterior.coords])
    with pytest.raises(ValueError, match=r"trace\[0\] DC\+: hole 0 is filled"):
        _snap_trace(poly, 0.5 * MM)
    r = _snap_trace(two, 0.5 * MM)  # without the hole the split is reported, not raised
    assert [v.origin for v in r.violations if v.rule == "net_split"] == ["induced"]


def test_pre_existing_violation_matched_with_its_numbers_changed():
    # gap 0.4 mm (49.6-50.0) -> 0.5 mm after snapping (49.6 -> 49.5): still < 1 mm, same violation with a new spacing value
    lay = _case4()
    lay = dataclasses.replace(lay, traces=[Trace("DC-", box(20 * MM, 45 * MM, 40 * MM, 49.6 * MM)),
                                           Trace("PHASE", box(20 * MM, 50 * MM, 40 * MM, 60 * MM))])
    lay.dies, lay.wires, lay.terminals = [], [], {}
    before = [v for v in check(lay) if v.rule == "min_spacing"]
    r = snap_layout(lay, 0.5 * MM)
    ms = [v for v in r.violations if v.rule == "min_spacing"]
    assert len(before) == 1 and len(ms) == 1 and ms[0].message != before[0].message
    assert ms[0].origin == "pre-existing"
