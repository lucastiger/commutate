"""Tests of the FastHenry deck exporter (T0384).  FastHenry is NOT run here (the next task does that): these are structure,
geometry and bookkeeping checks against independent computations (shapely perimeters, conductor-model areas, closed-form
counts) and a node-for-node comparison with the research exporter the module was ported from."""
from __future__ import annotations

import dataclasses
import importlib.util
import math
import sys
from pathlib import Path

import numpy as np
import pytest
from shapely.geometry import box

from moduleforge.geometry import DC_MINUS, DC_PLUS
from moduleforge.solvers import fasthenry as FH
from moduleforge.solvers import l2_layout as L2

ROOT = Path(__file__).resolve().parents[2]
MM = 1e-3


def _load(name: str, rel: str):
    sp = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(sp)
    sys.modules[name] = mod
    sp.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def case4():
    return _load("o006_case4_layout_for_fh_test", "research/scripts/o006_case4_layout.py")


@pytest.fixture(scope="module")
def base(case4):
    return case4.build("base")


@pytest.fixture(scope="module")
def refs():
    """The frozen T0263 reconstructions of the judged references (read-only import of the research script)."""
    m = _load("o003_powersynth_references_for_fh_test", "research/scripts/o003_powersynth_references.py")
    return {r: m.build(r) for r in ("2D_Case_2R", "2D_Case_6")}


@pytest.fixture(scope="module")
def gen_layout():
    from moduleforge.generate.halfbridge import generate_layouts
    return generate_layouts(1, seed=7, dies_per_switch=2)[0]


def parse(deck: str):
    nodes, segs, planes, equiv, ext, units, freq, default = {}, {}, [], [], [], [], None, None
    for line in deck.splitlines():
        s = line.strip()
        if not s or s.startswith("*") or s.startswith("+"):
            continue
        low = s.lower()
        if low.startswith(".units"):
            units.append(low.split()[1])
        elif low.startswith(".default"):
            default = s
        elif low.startswith(".equiv"):
            equiv.append(s.split()[1:])
        elif low.startswith(".external"):
            ext.append(s.split()[1:])
        elif low.startswith(".freq"):
            freq = dict(kv.split("=") for kv in s.split()[1:])
        elif low.startswith("n"):
            kv = dict(t.split("=") for t in s.split()[1:])
            nodes[s.split()[0]] = tuple(float(kv[a]) for a in "xyz")
        elif low.startswith("e"):
            p = s.split()
            segs[p[0]] = (p[1], p[2], dict(t.split("=") for t in p[3:]))
        elif low.startswith("g"):
            planes.append(dict(t.split("=") for t in s.split()[1:]))
    return nodes, segs, planes, equiv, ext, units, freq, default


def noncomment(deck: str):
    return [ln for ln in deck.splitlines() if not ln.startswith("*")]


READER_MAX_LINE = 900  # FastHenry 3.0wr refuses lines of ~1000+ characters (review T0408: 969 read, 1209 refused); margin


def read_errors(deck: str) -> list[str]:
    """What FastHenry 3.0wr's one-pass, case-insensitive reader would refuse: a line longer than READER_MAX_LINE characters,
    a segment, ``.equiv`` or ``.external`` naming a node not defined on an EARLIER line, and a node or element name defined
    twice.  Independent of the exporter's code."""
    defined: set[str] = set()
    elements: set[str] = set()
    bad = []
    for no, ln in enumerate(deck.splitlines(), 1):
        if len(ln) > READER_MAX_LINE:
            bad.append(f"line {no} too long: {len(ln)} > {READER_MAX_LINE} characters")
        s = ln.strip().lower()
        if not s or s.startswith("*"):
            continue
        tok = s.split()
        refs: list[str] = []
        if tok[0] == "+":  # gplane node: '+ name (x,y,z)'
            name = tok[1].split("(")[0]
            bad += [f"duplicate node {name}"] if name in defined else []
            defined.add(name)
        elif tok[0].startswith("n"):
            bad += [f"duplicate node {tok[0]}"] if tok[0] in defined else []
            defined.add(tok[0])
        elif tok[0].startswith(("e", "g")):
            bad += [f"duplicate element {tok[0]}"] if tok[0] in elements else []
            elements.add(tok[0])
            refs = tok[1:3] if tok[0].startswith("e") else []
        elif tok[0] in (".equiv", ".external"):
            refs = tok[1:]
        bad += [f"{n} used before definition in: {ln}" for n in refs if n not in defined]
    return bad


def equiv_classes(equiv: list[list[str]]) -> dict[str, frozenset]:
    """{node: its equivalence class} from parsed ``.equiv`` lines (union-find: lines sharing a node are one class)."""
    parent: dict[str, str] = {}

    def find(a):
        parent.setdefault(a, a)
        while parent[a] != a:
            a = parent[a]
        return a

    for e in equiv:
        for n in e[1:]:
            ra, rb = find(e[0]), find(n)
            if ra != rb:
                parent[rb] = ra
    out: dict[str, set] = {}
    for n in parent:
        out.setdefault(find(n), set()).add(n)
    return {n: frozenset(s) for s in out.values() for n in s}


# ----------------------------------------------------------------------------------------------------------- header
def test_header_units_sigma_freq_and_single_port(base):
    deck, _ = FH.export(base, FH.FHLevel(), title="t")
    nodes, segs, planes, equiv, ext, units, freq, default = parse(deck)
    assert units == ["m"] and ".units mm" not in deck.lower()
    assert default.startswith(".default sigma=")
    assert float(default.split("=")[1]) == base.to_conductors().rects[0].sigma
    assert (float(freq["fmin"]), float(freq["fmax"])) == (1e7, 2e7)
    ndec = float(freq["ndec"])
    assert math.isclose(float(freq["fmin"]) * 10 ** (1 / ndec), 2e7, rel_tol=1e-8)
    assert len(ext) == 1 and len(ext[0]) == 2 and all(n in nodes for n in ext[0])
    assert deck.rstrip().endswith(".end")
    # port nodes sit on DC+ / DC- terminal cells (point model: the nearest cell centre, within cell / sqrt(2))
    cm = base.to_conductors()
    for n, p in zip(ext[0], (cm.port.p_pos, cm.port.p_neg), strict=True):
        assert math.hypot(nodes[n][0] - p[0], nodes[n][1] - p[1]) <= 0.5 * math.sqrt(2) * MM + 1e-12
    # everything is in metres: all nodes inside the baseplate box
    bx = cm.planes[1].bounds
    for x, y, z in nodes.values():
        assert bx[0] - 1e-9 <= x <= bx[2] + 1e-9 and bx[1] - 1e-9 <= y <= bx[3] + 1e-9 and 0 <= z < 0.01


def test_deck_is_deterministic(base):
    a = FH.export(base, FH.FHLevel(cell_mm=0.5), title="x")[0]
    b = FH.export(base, FH.FHLevel(cell_mm=0.5), title="x")[0]
    assert a == b


def test_origin_is_the_l2_layout_lattice_origin(base, gen_layout):
    for lay, cell_idx in ((base, 0), (gen_layout, 0)):
        cm = lay.to_conductors()
        xmin, ymin = L2.layout_lattice(cm, cell_idx)[:2]
        assert FH.lattice_origin(cm) == (xmin, ymin)
    cm = gen_layout.to_conductors()
    assert FH.lattice_origin(cm)[0] < 0  # the generator's baseplate starts at -8 mm: a non-zero origin is exercised
    _, f = FH.export(gen_layout, FH.FHLevel(cell_mm=0.5))
    assert f["origin_m"] == list(FH.lattice_origin(cm))


# --------------------------------------------------------------------------------------------------- area and counts
def _check_area(lay, cell_mm):
    cm = lay.to_conductors()
    deck, f = FH.export(lay, FH.FHLevel(cell_mm=cell_mm))
    for net in {r.net for r in cm.rects}:
        assert f["trace_area_m2"][net] == pytest.approx(cm.copper_area(net), rel=1e-12)
    n_trace_nodes = sum(1 for k in parse(deck)[0] if k.startswith("Nt"))
    assert n_trace_nodes * (cell_mm * MM) ** 2 == pytest.approx(cm.copper_area(), rel=1e-12)
    return deck, f


@pytest.mark.parametrize("cell_mm", [1.0, 0.5, 0.25])
def test_trace_area_per_net_equals_conductor_model_case4(base, cell_mm):
    _check_area(base, cell_mm)


@pytest.mark.parametrize("cell_mm", [0.5, 0.25])
def test_trace_area_per_net_equals_conductor_model_generated(gen_layout, cell_mm):
    _check_area(gen_layout, cell_mm)


def test_segment_counts_scale_per_halving_against_shapely_perimeters(base):
    """A net of N cells with total boundary P (in cells, no two nets touching) has (4N - P) / 2 = 2N - P/2 lattice
    neighbour pairs: segment counts follow the independent shapely area / perimeter, not the exporter's own loop."""
    polys = [t.polygon for t in base.traces]
    prev = None
    for cell_mm in (1.0, 0.5, 0.25):
        c = cell_mm * MM
        n = sum(p.area for p in polys) / c ** 2
        per = sum(p.exterior.length + sum(r.length for r in p.interiors) for p in polys) / c
        _, f = FH.export(base, FH.FHLevel(cell_mm=cell_mm))
        assert f["n_cells"] == round(n)
        assert f["n_trace_segments"] + f["n_dropped_die_segments"] == round(2 * n - per / 2)
        assert f["n_dropped_die_segments"] > 0
        if prev is not None:  # halving the pitch: cells x4 exactly, segments between 4x and 4x + a perimeter term
            assert f["n_cells"] == 4 * prev["n_cells"]
            r = (f["n_trace_segments"] + f["n_dropped_die_segments"]) / (prev["n_trace_segments"] + prev["n_dropped_die_segments"])
            assert 4.0 < r < 4.3
        prev = f


def test_plane_pitch_is_separate_from_trace_pitch(base):
    _, f4 = FH.export(base, FH.FHLevel(cell_mm=1.0, plane_cell_mm=4.0))
    _, f2 = FH.export(base, FH.FHLevel(cell_mm=1.0, plane_cell_mm=2.0))
    assert f2["n_cells"] == f4["n_cells"]
    cm = base.to_conductors()
    for pl in cm.planes:  # each of seg1 / seg2 against the plane's own extent / pitch (shapely-free: Plane.bounds)
        x0, y0, x1, y1 = pl.bounds
        for f, pitch in ((f4, 4.0), (f2, 2.0)):
            info = [p for p in f["planes"] if p["name"] == pl.name][0]
            assert info["seg1"] == max(1, round((x1 - x0) / (pitch * MM)))
            assert info["seg2"] == max(1, round((y1 - y0) / (pitch * MM)))
    bp = [p for p in f2["planes"] if p["name"] == "baseplate"][0]
    assert bp["seg1"] == 40 and bp["seg2"] == 55  # 80 x 110 mm at 2 mm


def test_thickness_ladder_and_width_filaments_in_deck(base):
    for nh in (3, 5, 9):
        deck, f = FH.export(base, FH.FHLevel(nh_trace=nh, nh_plane=nh, rh=1.5, nw_trace=2))
        _, segs, planes, *_ = parse(deck)
        tr = [kv for k, (_, _, kv) in segs.items() if k[1] in "xy" and k[0] == "E" and not k.startswith("Ew")]
        assert tr and all(kv["nhinc"] == str(nh) and kv["nwinc"] == "2" and kv["rh"] == "1.5" for kv in tr)
        assert all(p["nhinc"] == str(nh) and p["rh"] == "1.5" for p in planes)
    _, f1 = FH.export(base, FH.FHLevel(nh_trace=1, nh_plane=1))
    _, f3 = FH.export(base, FH.FHLevel(nh_trace=3, nh_plane=3))
    wire_f = f1["n_wire_segments"] * 4
    assert (f3["n_filaments"] - wire_f) == 3 * (f1["n_filaments"] - wire_f)


# ------------------------------------------------------------------------------------------------------------ wires
@pytest.mark.parametrize("wire_n,wire_sub", [(1, 1), (2, 1), (3, 2)])
def test_wire_square_side_and_filaments(base, wire_n, wire_sub):
    deck, f = FH.export(base, FH.FHLevel(wire_n=wire_n, wire_sub=wire_sub))
    nodes, segs, *_ = parse(deck)
    d = base.wires[0].diameter
    ws = [(a, b, kv) for k, (a, b, kv) in segs.items() if k.startswith("Ew")]
    assert len(ws) == sum(len(w.points) - 1 for w in base.wires) * wire_sub == f["n_wire_segments"]
    assert FH.SQUARE_PER_DIAMETER == pytest.approx(0.8711, abs=1e-4)  # exact ratio 0.78/0.894 = 0.87104; the packet rounds it to 0.8711
    for _, _, kv in ws:
        assert float(kv["w"]) == pytest.approx(0.8711 * d, rel=1e-4) and kv["w"] == kv["h"]
        assert kv["nwinc"] == kv["nhinc"] == str(wire_n)  # wire_n^2 filaments
    # equal-GMD check: GMD of the square (0.44705 a) equals that of the disc (0.7788 r)
    assert 0.44705 * float(ws[0][2]["w"]) == pytest.approx(0.7788 * d / 2, rel=1e-4)
    # total wire length preserved by the splitting
    Lw = sum(math.dist(nodes[a], nodes[b]) for a, b, _ in ws)
    assert Lw == pytest.approx(sum(w.length for w in base.wires), rel=1e-9)


# ------------------------------------------------------------------------------------------------------------- dies
def _expected_die_cells(lay, nodes, d):
    """Trace nodes whose centre lies inside the die footprint and on the die's bottom-net copper (shapely, independent)."""
    from shapely.ops import unary_union
    net_poly = unary_union([t.polygon for t in lay.traces if t.net == d.bottom_net])
    fp = box(d.x - d.w / 2, d.y - d.h / 2, d.x + d.w / 2, d.y + d.h / 2)
    return {n for n, (x, y, _) in nodes.items() if n.startswith("Nt") and fp.contains(box(x, y, x, y).centroid)
            and net_poly.contains(box(x, y, x, y).centroid)}


def test_die_equiv_groups_hold_every_footprint_cell(base):
    """Every footprint cell of the bottom net and the die's wire start form ONE equivalence class, also at 0.25 mm where
    the group (384 cells) is split over several .equiv lines."""
    for cell_mm in (1.0, 0.5, 0.25):
        deck, f = FH.export(base, FH.FHLevel(cell_mm=cell_mm))
        nodes, _, _, equiv, *_ = parse(deck)
        cls = equiv_classes(equiv)
        cm = base.to_conductors()
        assert len(f["die_groups"]) == 4
        for d in cm.shorts:
            expect = _expected_die_cells(base, nodes, d)
            assert len(expect) == round(4 * 6 / cell_mm ** 2)
            groups = {cls[n] for n in expect if n in cls}
            assert len(groups) == 1 and expect <= next(iter(groups))
            group = next(iter(groups))
            assert {n for n in group if n.startswith("Nt")} == expect  # nothing outside the footprint
            wires_in = {n for n in group if n.startswith("Nw")}
            assert len(wires_in) == 1  # one source-wire start per die in Case 4
        n_lines = sum(1 for ln in deck.splitlines() if ln.startswith(".equiv"))
        assert (n_lines > len(set(cls.values()))) == (cell_mm == 0.25)  # split only where a group exceeds the line limit


def test_distributed_die_keeps_the_footprint_apart(base):
    deck, f = FH.export(base, FH.FHLevel(), die_model="distributed")
    nodes, segs, _, equiv, *_ = parse(deck)
    cm = base.to_conductors()
    assert f["n_dropped_die_segments"] == 0
    assert sum(1 for k in segs if k.startswith("Ev")) == 4 * 24
    cols = [(k, v) for k, v in segs.items() if k.startswith("Ev")]
    d0 = cm.shorts[0]
    tb = d0.z_top - d0.z_bottom
    z_trace_mid = cm.rects[0].z + cm.rects[0].thickness / 2
    for _, (a, b, kv) in cols:  # column: trace mid-thickness -> block mid-plane, same (x, y)
        assert a.startswith("Nt") and b.startswith("Nd") and float(kv["w"]) == float(kv["h"]) == MM
        assert nodes[a][2] == pytest.approx(z_trace_mid, rel=1e-12)
        assert nodes[b][2] == pytest.approx((d0.z_bottom + d0.z_top) / 2, rel=1e-12)
        assert nodes[a][:2] == nodes[b][:2]
    lat_s = [(a, b, kv) for k, (a, b, kv) in segs.items() if k.startswith("Ed")]
    lat = [kv for _, _, kv in lat_s]
    assert lat and all(float(kv["h"]) == pytest.approx(tb, rel=1e-9) for kv in lat)
    for a, b, kv in lat_s:  # FastHenry centres h on the node line: the lateral block fills exactly [z_bottom, z_top]
        z, h = nodes[a][2], float(kv["h"])
        assert nodes[b][2] == z and z - h / 2 == pytest.approx(d0.z_bottom, rel=1e-12)
        assert z + h / 2 == pytest.approx(d0.z_top, rel=1e-12)
        assert math.dist(nodes[a], nodes[b]) == pytest.approx(MM, rel=1e-12)
    # 4 x 6 footprint: x-neighbours 3 x 6 + y-neighbours 4 x 5 = 38 lateral segments per die
    assert len(lat) == 4 * 38
    # wire starts join die-top nodes (the trace footprint cells are not merged with them)
    starts = [e for e in equiv if e[0].startswith("Nw") and e[0].endswith("p0")]
    assert len(starts) == 4 and all(n.startswith("Nd") for e in starts for n in e[1:])
    # a die-sigma override changes only the block conductivity
    deck2, _ = FH.export(base, FH.FHLevel(), die_model="distributed", die_sigma=1.0e4)
    assert deck2.count("sigma=10000") == len(cols) + len(lat)


def test_tab_terminal_variant(base):
    deck, f = FH.export(base, FH.FHLevel(), terminal_model="tab")
    nodes, segs, _, equiv, ext, *_ = parse(deck)
    cm = base.to_conductors()
    z_cu = cm.rects[0].z + cm.rects[0].thickness
    assert set(f["tab_cells"]) == {"P", "M"} and all(len(v) == 9 for v in f["tab_cells"].values())  # 3 x 3 mm / 1 mm
    posts = {k: v for k, v in segs.items() if k.startswith("Eq")}
    assert len(posts) == 18
    for _, b, kv in posts.values():
        assert nodes[b][2] == pytest.approx(z_cu + 2e-3, rel=1e-12) and float(kv["w"]) == MM
    # one post top per terminal, merged; the .external node is one of them
    tops = [e for e in equiv if all(n.startswith("Nq") for n in e)]
    assert len(tops) == 2 and all(len(e) == 9 for e in tops)
    assert ext[0][0] in tops[0] + tops[1] and ext[0][1] in tops[0] + tops[1] and ext[0][0] != ext[0][1]
    # the foot joins every footprint cell without merging them
    assert not any(sum(n.startswith("Nt") for n in e) > 1 for e in equiv if not e[0].startswith("Nq")
                   and not e[0].startswith("Nw"))
    # override footprint and height
    deck2, f2 = FH.export(base, FH.FHLevel(cell_mm=0.5), terminal_model="tab", tab=FH.TabSpec(w=2e-3, h=2e-3, height=3e-3))
    assert all(len(v) == 16 for v in f2["tab_cells"].values())
    nodes2 = parse(deck2)[0]
    assert max(z for _, _, z in nodes2.values() if z > z_cu) == pytest.approx(z_cu + 3e-3, rel=1e-12)


def test_f6_variants_are_well_formed_together(base):
    deck, f = FH.export(base, FH.FHLevel(cell_mm=0.5, plane_cell_mm=2.0, nh_trace=3, wire_n=3),
                        die_model="distributed", terminal_model="tab")
    nodes, segs, planes, equiv, ext, units, *_ = parse(deck)
    assert units == ["m"] and len(ext) == 1 and len(planes) == 2
    assert read_errors(deck) == []
    assert f["n_block_nodes"] > 0 and f["die_model"] == "distributed" and f["terminal_model"] == "tab"
    assert FH.export(base, FH.FHLevel(), die_model="distributed")[1]["deck_sha256"] != FH.export(base, FH.FHLevel())[1]["deck_sha256"]
    with pytest.raises(ValueError):
        FH.export(base, FH.FHLevel(), die_model="bogus")
    with pytest.raises(ValueError):
        FH.export(base, FH.FHLevel(), terminal_model="bogus")


@pytest.mark.parametrize("die_model", FH.DIE_MODELS)
@pytest.mark.parametrize("terminal_model", FH.TERMINAL_MODELS)
def test_every_node_is_defined_before_use(base, gen_layout, die_model, terminal_model):
    """FastHenry reads the deck in one pass (attempt 1's distributed die named +x / +y neighbours before their node lines,
    review T0404/T0405): every variant, two levels, Case 4 and a generated layout."""
    for lay, lev in ((base, FH.FHLevel()), (base, FH.FHLevel(cell_mm=0.5, plane_cell_mm=2.0, nh_trace=3, wire_n=3)),
                     (gen_layout, FH.FHLevel(cell_mm=0.5, plane_cell_mm=2.0))):
        deck, _ = FH.export(lay, lev, die_model=die_model, terminal_model=terminal_model)
        assert read_errors(deck) == []


def test_read_errors_catches_a_forward_reference(base):
    """Negative control of the order check: the attempt-1 layout (a block node written after a segment naming it) fails."""
    deck, _ = FH.export(base, FH.FHLevel(), die_model="distributed")
    lines = deck.splitlines()
    i = next(k for k, ln in enumerate(lines) if ln.startswith("Nd0i"))
    moved = lines[:i] + lines[i + 1:-1] + [lines[i], lines[-1]]
    errs = read_errors("\n".join(moved))
    assert errs and all(lines[i].split()[0].lower() in e for e in errs)
    assert read_errors(deck + lines[i] + "\n") == [f"duplicate node {lines[i].split()[0].lower()}"]


@pytest.mark.parametrize("cell_mm", [1.0, 0.5, 0.25])
def test_shorted_segments_count_the_tied_contact_cells(base, cell_mm):
    """Segments kept between tied contact cells (docstring 'contacts'): a point on a cell edge ties 2 cells (1 segment), on a
    corner 4 cells (4 segments).  Closed form from the contact coordinates, Case 4 (no contact near a net edge)."""
    cm = base.to_conductors()
    c = cell_mm * MM
    ox, oy = FH.lattice_origin(cm)
    pts = [cm.port.p_pos, cm.port.p_neg]
    by_w: dict[int, list] = {}
    for s in cm.wires:
        by_w.setdefault(s.wire_index, []).append(s)
    pts += [sg[-1].p1 for sg in by_w.values()]  # feet; Case 4 starts are on dies (short model: no lattice segment)

    def tie(v, o):
        u = (v - o) / c
        return abs(u - math.floor(u)) < 1e-9 or abs(u - math.floor(u) - 1) < 1e-9  # on a cell edge

    expect = sum({(False, False): 0, (True, False): 1, (False, True): 1, (True, True): 4}[(tie(p[0], ox), tie(p[1], oy))]
                 for p in pts)
    _, f = FH.export(base, FH.FHLevel(cell_mm=cell_mm))
    assert f["n_shorted_segments"] == expect
    assert expect == (0 if cell_mm == 1.0 else 8)  # the ports at (13.5, 36.5 / 64.5) mm sit on corners below 1 mm


def _with_extra_wires(lay, extra):
    cm = lay.to_conductors()
    cm2 = dataclasses.replace(cm, wires=(*cm.wires, *extra))

    class Fake:
        terminals = lay.terminals

        def to_conductors(self):
            return cm2

    return Fake()


def test_wire_ends_follow_l2_layout_end_contact(base):
    """A wire END on a die joins that die (l2_layout.end_contact), not a trace cell; a wire START off the dies joins its
    net's nearest trace cell.  Extra wires on Case 4: die 0 pad -> die 1 top (stitch), and DC- trace -> DC- trace."""
    cm = base.to_conductors()
    d0, d1 = cm.shorts[0], cm.shorts[1]
    w0 = next(s for s in cm.wires if s.wire_index == 0)
    nw = 1 + max(s.wire_index for s in cm.wires)
    a, b = (d0.x + 0.6e-3, d0.y + 0.3e-3, d0.z_top), (d1.x - 0.6e-3, d1.y + 0.3e-3, d1.z_top)
    top = (a[0] / 2 + b[0] / 2, a[1], d0.z_top + 1e-3)
    foot = [s for s in cm.wires if s.wire_index == 0][-1].p1  # wire 0's foot on the DC- trace
    t0, t1 = (foot[0] + 3.0e-3, foot[1], foot[2]), (foot[0] + 6.0e-3, foot[1], foot[2])
    extra = [dataclasses.replace(w0, wire_index=nw, p0=a, p1=top), dataclasses.replace(w0, wire_index=nw, p0=top, p1=b),
             dataclasses.replace(w0, wire_index=nw + 1, p0=t0, p1=(t0[0] + 1.5e-3, t0[1], t0[2] + 1e-3)),
             dataclasses.replace(w0, wire_index=nw + 1, p0=(t0[0] + 1.5e-3, t0[1], t0[2] + 1e-3), p1=t1)]
    lay = _with_extra_wires(base, extra)
    # short dies: the stitch's start is in die 0's group, its end in die 1's group
    deck, f = FH.export(lay, FH.FHLevel())
    nodes, _, _, equiv, *_ = parse(deck)
    assert read_errors(deck) == []
    grp = {n: frozenset(e) for e in equiv for n in e}
    s_name, e_name = f"Nw{nw}p0", f"Nw{nw}p2"
    for name, d in ((s_name, d0), (e_name, d1)):
        cells = {n for n in grp[name] if n.startswith("Nt")}
        assert len(cells) == 24 and all(abs(nodes[n][0] - d.x) < d.w / 2 and abs(nodes[n][1] - d.y) < d.h / 2 for n in cells)
    assert e_name not in f["contacts"] and grp[s_name] != grp[e_name]
    # trace-to-trace wire: both ends are trace contacts of the wire's net, at the nearest cell centre
    for k, p in ((0, t0), (2, t1)):
        ks = f["contacts"][f"Nw{nw + 1}p{k}"]
        assert len(ks) == 1
        x, y = (ks[0][0] + 0.5) * MM + f["origin_m"][0], (ks[0][1] + 0.5) * MM + f["origin_m"][1]
        assert math.hypot(x - p[0], y - p[1]) <= 0.5 * math.sqrt(2) * MM
    # distributed dies: the stitch's end joins die 1's block node nearest to it
    deck, f = FH.export(lay, FH.FHLevel(), die_model="distributed")
    nodes, _, _, equiv, *_ = parse(deck)
    assert read_errors(deck) == []
    e = next(e for e in equiv if e[0] == e_name)
    assert len(e) == 2 and e[1].startswith("Nd1i")
    assert math.hypot(nodes[e[1]][0] - b[0], nodes[e[1]][1] - b[1]) <= 0.5 * math.sqrt(2) * MM


def test_tab_solver_note(base):
    assert FH.export(base, FH.FHLevel(plane_cell_mm=4.0), terminal_model="tab")[1]["solver_notes"]
    assert FH.export(base, FH.FHLevel(plane_cell_mm=2.0), terminal_model="tab")[1]["solver_notes"] == []
    assert FH.export(base, FH.FHLevel(plane_cell_mm=4.0))[1]["solver_notes"] == []


def test_distributed_die_solver_note(base):
    """Review T0409: the distributed-die deck crashed FastHenry's multipole solver; every such deck says to use the direct one."""
    for lev in (FH.FHLevel(), FH.FHLevel(cell_mm=0.5, plane_cell_mm=2.0)):
        notes = FH.export(base, lev, die_model="distributed")[1]["solver_notes"]
        assert len(notes) == 1 and "multipole" in notes[0] and "direct solver" in notes[0]
    assert FH.export(base, FH.FHLevel(plane_cell_mm=2.0))[1]["solver_notes"] == []


# ------------------------------------------------------------------------------------------- FastHenry's line limit
@pytest.mark.parametrize("terminal_model", FH.TERMINAL_MODELS)
@pytest.mark.parametrize("which", ["case4", "2D_Case_2R", "2D_Case_6", "generated"])
def test_every_line_fits_the_reader_at_quarter_mm(base, refs, gen_layout, which, terminal_model):
    """Review T0408 (blocker): at 0.25 mm a die group written on one .equiv line is 3474-4026 characters and FastHenry
    3.0wr refuses the deck.  Default dies, point and tab terminals, on Case 4, the two judged references and a generated
    layout: every line <= 900 characters, the deck reads in one pass, and the split groups are still one class each."""
    lay = {"case4": base, "generated": gen_layout, **refs}[which]
    deck, f = FH.export(lay, FH.FHLevel(cell_mm=0.25, plane_cell_mm=2.0), terminal_model=terminal_model)
    assert max(len(ln) for ln in deck.splitlines()) <= 900
    assert read_errors(deck) == []
    nodes, _, _, equiv, ext, *_ = parse(deck)
    cls = equiv_classes(equiv)
    # non-vacuous: at least one class would not fit on one line, so the splitting is exercised
    assert max(len(".equiv " + " ".join(sorted(c))) for c in set(cls.values())) > 900
    lines_per_head: dict[str, int] = {}
    for e in equiv:
        lines_per_head[e[0]] = lines_per_head.get(e[0], 0) + 1
        assert all(cls[n] == cls[e[0]] for n in e)
    assert max(lines_per_head.values()) > 1
    cm = lay.to_conductors()
    for d in cm.shorts:  # every die: all footprint cells in one class with its source-wire start(s)
        expect = _expected_die_cells(lay, nodes, d)
        assert len(expect) == round(d.w * d.h / (0.25 * MM) ** 2)
        groups = {cls[n] for n in expect}
        assert len(groups) == 1
        assert {n for n in next(iter(groups)) if n.startswith("Nt")} == expect
        assert any(n.startswith("Nw") for n in next(iter(groups)))
    if terminal_model == "tab":  # each post top (3 x 3 mm in the references: 144 cells) is one class with its .external node
        for node, net in zip(ext[0], (DC_PLUS, DC_MINUS), strict=True):
            tops, term = cls[node], lay.terminals[net]
            assert all(n.startswith("Nq") for n in tops) and len(tops) == round(term.w * term.h / (0.25 * MM) ** 2)
            assert len({nodes[n][2] for n in tops}) == 1
        if which != "generated":
            assert all(len(cls[n]) == 144 for n in ext[0])


@pytest.mark.parametrize("which", ["case4", "2D_Case_2R", "2D_Case_6"])
def test_distributed_deck_fits_the_reader_at_quarter_mm(base, refs, which):
    lay = {"case4": base, **refs}[which]
    for tm in FH.TERMINAL_MODELS:
        deck, _ = FH.export(lay, FH.FHLevel(cell_mm=0.25, plane_cell_mm=2.0), die_model="distributed", terminal_model=tm)
        assert read_errors(deck) == []


def test_read_errors_catches_a_long_line(base):
    """Negative control of the length check: rejoining a split die group onto one line (P4's form) is refused."""
    deck, _ = FH.export(base, FH.FHLevel(cell_mm=0.25))
    lines = deck.splitlines()
    eq = [k for k, ln in enumerate(lines) if ln.startswith(".equiv")]
    head = lines[eq[0]].split()[1]
    same = [k for k in eq if lines[k].split()[1] == head]
    assert len(same) > 1
    joined = lines[same[0]] + "".join(" " + " ".join(lines[k].split()[2:]) for k in same[1:])
    assert len(joined) > 900
    bad = [ln for k, ln in enumerate(lines) if k not in same[1:]]
    bad[same[0]] = joined
    errs = read_errors("\n".join(bad) + "\n")
    assert len(errs) == 1 and "too long" in errs[0]


@pytest.mark.parametrize("max_line", [30, 60, 900])
def test_equiv_lines_chain_into_one_group(max_line):
    names = [f"Nt{i}y{j}" for i in range(20) for j in range(20)]
    out = FH.equiv_lines(names, max_line=max_line)
    assert all(len(ln) <= max_line and ln.split()[:2] == [".equiv", names[0]] and len(ln.split()) >= 3 for ln in out)
    rest = [n for ln in out for n in ln.split()[2:]]
    assert rest == names[1:]  # every other name exactly once, in order
    for a, b in zip(out[:-1], out[1:], strict=True):  # greedy packing: the next line's first name did not fit on this one
        assert len(a) + 1 + len(b.split()[2]) > max_line
    assert FH.equiv_lines(names[:1]) == [] and FH.equiv_lines(names[:2]) == [f".equiv {names[0]} {names[1]}"]
    with pytest.raises(ValueError):
        FH.equiv_lines(["N" * 10, "M" * 30], max_line=30)


def test_long_title_is_refused(base):
    with pytest.raises(ValueError, match="longer than"):
        FH.export(base, FH.FHLevel(), title="x" * 1000)
    with pytest.raises(ValueError, match="one line"):
        FH.export(base, FH.FHLevel(), title="a\n.units mm")


# --------------------------------------------------------------------------------------------------------- refusals
def test_off_lattice_is_refused(base):
    with pytest.raises(ValueError, match="lattice"):
        FH.export(base, FH.FHLevel(cell_mm=0.3))
    with pytest.raises(ValueError, match="lattice"):
        FH.export(base, FH.FHLevel(cell_mm=2.0))  # T9 etc. are on a 1 mm grid, not all 2 mm aligned


def test_cell_with_two_nets_is_refused(base):
    cm = base.to_conductors()
    r0 = cm.rects[0]
    other = next(r for r in cm.rects if r.net != r0.net)
    bad = dataclasses.replace(r0, net=other.net)  # same rectangle, other net: every cell of it holds two nets
    cm2 = dataclasses.replace(cm, rects=(*cm.rects, bad))

    class Fake:
        terminals = base.terminals

        def to_conductors(self):
            return cm2

    with pytest.raises(ValueError, match="two nets"):
        FH.export(Fake(), FH.FHLevel())


def test_level_validation():
    for kw in ({"nh_trace": 0}, {"wire_n": 0}, {"cell_mm": 0.0}, {"rh": -1.0}):
        with pytest.raises(ValueError):
            FH.FHLevel(**kw)
    # review T0409: counts must be ints, not bools or integral floats (nhinc=3.0 in the deck; range(2.0) TypeError)
    for k in ("nh_trace", "nh_plane", "nw_trace", "wire_n", "wire_sub"):
        for v in (True, 3.0, 2.5, "3", None, -1):
            with pytest.raises(ValueError, match=k):
                FH.FHLevel(**{k: v})
    for k in ("cell_mm", "plane_cell_mm", "rh"):
        for v in (True, float("nan"), float("inf"), "1", -0.5):
            with pytest.raises(ValueError, match=k):
                FH.FHLevel(**{k: v})
    assert FH.FHLevel(cell_mm=1, nh_trace=9).nh_trace == 9  # an int pitch is fine
    # numpy scalars from a sweep are accepted and stored as plain int / float: same level, same deck text
    assert FH.FHLevel(nh_trace=np.int64(5), cell_mm=np.float64(0.5)) == FH.FHLevel(nh_trace=5, cell_mm=0.5)
    assert repr(FH.FHLevel(nh_trace=np.int64(5), cell_mm=1)) == repr(FH.FHLevel(nh_trace=5, cell_mm=1.0))


def test_die_sigma_validation(base):
    """Review T0408: a zero, negative or non-finite die conductivity is refused (the stack's SiC die has sigma = 0)."""
    for v in (0.0, -5.8e7, float("nan"), float("inf"), True, "5.8e7"):
        with pytest.raises(ValueError, match="die_sigma"):
            FH.export(base, FH.FHLevel(), die_model="distributed", die_sigma=v)
    deck, _ = FH.export(base, FH.FHLevel(), die_model="distributed", die_sigma=1e6)
    assert "sigma=1000000 " in deck


def _shift_die(lay, dx):
    cm = lay.to_conductors()
    cm2 = dataclasses.replace(cm, shorts=(dataclasses.replace(cm.shorts[0], x=cm.shorts[0].x + dx), *cm.shorts[1:]))

    class Fake:
        terminals = lay.terminals

        def to_conductors(self):
            return cm2

    return Fake()


@pytest.mark.parametrize("die_model", FH.DIE_MODELS)
def test_off_lattice_die_footprint_is_refused(base, die_model):
    """Review T0409: a die shifted half a cell was accepted; l2_layout's check_on_lattice refuses it, so does the exporter."""
    with pytest.raises(ValueError, match="die 0 footprint.*lattice"):
        FH.export(_shift_die(base, 0.5e-3), FH.FHLevel(cell_mm=1.0), die_model=die_model)
    d = _shift_die(base, 0.5e-3).to_conductors().shorts[0]
    ox, oy = FH.lattice_origin(base.to_conductors())
    with pytest.raises(ValueError, match="lattice"):  # l2_layout refuses the same footprint
        L2.check_on_lattice(d.x - d.w / 2, d.x + d.w / 2, d.y - d.h / 2, d.y + d.h / 2, ox, oy, 1e-3, 1e-3, "die 0")
    # a whole-cell shift stays on the lattice and is accepted
    _, f = FH.export(_shift_die(base, 1.0e-3), FH.FHLevel(cell_mm=1.0), die_model=die_model)
    assert f["die_groups"][0] == 24


def test_off_lattice_tab_footprint_is_refused(base):
    with pytest.raises(ValueError, match="tab footprint.*lattice"):
        FH.export(base, FH.FHLevel(cell_mm=1.0), terminal_model="tab", tab=FH.TabSpec(w=2.5e-3, h=3e-3))
    with pytest.raises(ValueError, match="tab footprint.*lattice"):
        FH.export(base, FH.FHLevel(cell_mm=0.5), terminal_model="tab", tab=FH.TabSpec(w=2.4e-3, h=2.4e-3))
    _, f = FH.export(base, FH.FHLevel(cell_mm=0.5), terminal_model="tab", tab=FH.TabSpec(w=2.0e-3, h=3.0e-3))
    assert all(len(v) == 24 for v in f["tab_cells"].values())


# ---------------------------------------------------------------------------------------------------- faithful port
def test_faithful_port_matches_the_research_exporter_node_for_node(case4):
    """Case 4 base at P4's k0 knobs: the deck equals research/scripts/o006_p4/fh_export.py's, line for line.  The only
    differences are the two ``*`` header comment lines (title / level text), which carry no model content.  Behaviour
    changed on purpose by this task, none of which changes these decks: (1) the lattice origin is l2_layout's (identical
    here: the Case 4 baseplate corner is (0, 0)); (2) wire ends follow l2_layout's end_contact rule (P4: every start had
    to lie on a die pad, every end joined a trace; here a wire end on a die joins the die and a start off the dies joins
    a trace; in Case 4 all starts are on die pads and all feet on traces); (3) the F6 variants (not the default)."""
    old = _load("o006_p4_fh_export_for_test", "research/scripts/o006_p4/fh_export.py")
    cases = [(case4.build("base"), dict(cell_mm=1.0, plane_cell_mm=4.0, nh_trace=1, nh_plane=1, rh=2.0, nw_trace=1,
                                        wire_n=2, wire_sub=1)),
             (case4.build("die_shift"), dict(cell_mm=1.0, plane_cell_mm=4.0, nh_trace=3, nh_plane=3, wire_n=2, wire_sub=2)),
             (case4.build("trace_width"), dict(cell_mm=0.5, plane_cell_mm=2.0, nh_trace=3, nh_plane=3, wire_n=3, wire_sub=1))]
    for lay, kw in cases:
        dn, fn = FH.export(lay, FH.FHLevel(**kw), title="t")
        do, fo = old.export(lay, old.FHLevel(**kw), title="t")
        assert noncomment(dn) == noncomment(do)
        for k in ("n_cells", "n_trace_segments", "n_dropped_die_segments", "n_wire_segments", "n_filaments", "n_nodes",
                  "die_groups"):
            assert fn[k] == fo[k]


def test_parse_zc():
    z = FH.parse_zc("Row 1:  Impedance matrix for frequency = 1e+07 1 x 1\n  0.0123456 +1.4e+00j\n"
                    "Impedance matrix for frequency = 2e+07 1 x 1\n  0.02 -3.5e-01j\n")
    assert z == {1e7: complex(0.0123456, 1.4), 2e7: complex(0.02, -0.35)}


def test_nets_constants_used():
    assert DC_PLUS != DC_MINUS and np.isfinite(FH.FREQS_HZ).all()
