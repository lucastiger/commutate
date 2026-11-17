"""Frozen perturbation rules on the 1 mm lattice for O004's re-layout pairs (T0386).

O004 judges inductance *ratios* r = L(re-layout) / L(reference) of pairs (reference, re-layout) of the reconstructed
PowerSynth sample designs.  2D_Case_6 has no twin, so the 0.5 mm parameter space of ``generate.derivative`` cannot be used;
the four moves here act directly on a reconstructed reference ``Layout``:

* ``die_row_shift``   (a) all dies of one switch (HS or LS) move by (dx, dy) mm.  Declared side effects: the dies' pads move
  with them; every power and signal wire on those dies keeps its direction: its start moves with its die, and its landing
  moves by the along-row part of the shift (``row_axis``), so a shift along the row moves the wires rigidly and a shift across
  it stretches or shrinks them towards their fixed landings (O006's die_shift); the host copper of each moved die is extended
  to the box of the die grown by the reference's own enclosure margin (min over the dies of the reference, whole mm, at least
  1 mm): copper is only added.
* ``trace_width``     (b) one long side of a power net's copper (an edge at least as long as the band is wide, measured to the
  opposite boundary) moves by ``delta`` mm along its normal (positive: outward, adds copper; negative: inward, removes it).
* ``terminal_copper`` (c) the window around a terminal pad (the pad grown by ``margin`` mm) grows by ``delta`` mm on one side
  (positive: the slab is added to the net's copper; negative: the slab of depth |delta| inside the window edge is removed).
* ``wire_landing``    (d) the landing point of every power wire of one switch moves by (dx, dy) mm on its landing copper
  (the start stays on the die pad).

Everything else of the reference is untouched (stack, outline, other nets, signal copper, terminals, the other switch).
Each move is a deterministic ``apply(reference, move_type, params) -> Layout`` with integer-mm parameters, so a reference
on l2_layout's 1 mm lattice stays on the 1.0, 0.5 and 0.25 mm lattices (``on_lattice``).

* ``compound`` (founder guidance I0217) two or three of the four moves, of distinct types, applied one after another in
  MOVE_TYPES order, each to the previous one's result (``_apply_compound``; params ``{"moves": [{"move_type", "params"},
  ...]}``).  It changes the union of what its components declare.  A compound is its own pair kind (``PAIR_KINDS``); the
  single moves keep their own pairs.  ``draw`` builds a compound as a chain of single draws: its size and move types are
  drawn first, then each component is drawn like a single move from its frozen range on the layout the earlier components
  left, and is redrawn until that intermediate layout is DRC-clean and changed.  Every intermediate is therefore a legal
  re-layout, and on tightly ruled references the rejection costs add instead of multiplying.

``draw(reference, allocation, seed)`` draws parameters for the requested number of pairs per pair kind from one ``numpy``
Generator over the frozen ranges below (no global state), compounds after the single moves.  It rejects a draw whose layout
is not DRC-clean under the reference's measured rules (``measured_rules``: ``drc.rules.measure_rules`` with
``min_signal_wire_length`` dropped, exactly the construction of ``e010_run.e008_rules`` / D0018 item 1), leaves the geometry
unchanged, or repeats the geometry of an earlier draw of any kind (``geometry_key``); after ``MAX_REDRAWS`` consecutive
rejections it raises ``RuntimeError``.  ``rules_sha256()``
hashes the rule sources (this module, the DRC, the wire constructor, the fingerprint and l2_layout's lattice rule) and the
ranges so that E004's spec can freeze them.  The ranges were developed on 2D_Case_4 and development seeds only (F2) and
never tuned on 2D_Case_2R / 2D_Case_6.

Known limit (T0386, development finding on 2D_Case_4 under its E008 dev rules, L1 at 20 MHz): no single DRC-clean move of
the four kinds reaches r <= 0.75 (exhaustive integer scans: die-row shift best r = 0.873, trace width 0.915, wire landing
0.963, terminal copper 0.981).  Compounds reach lower, but the lowest found is 0.7616 (LS die-row shift (-3, 2) mm, PHASE
T5 top edge +7 mm, HS landings (1, 9) mm; a clean chain).  The HS wires cannot shorten below 7 mm, because the 10 mm T5-T6
gap less the 3 mm DC+/PHASE spacing bounds the die shift plus the T5 widening.  O004's span [0.75, 0.98] is left to the
founder (I0217; tests/unit/test_perturb.py, strict xfail).
"""
from __future__ import annotations

import copy
import dataclasses
import hashlib
import inspect
import json
import math
from collections.abc import Mapping
from dataclasses import dataclass
from functools import partial

import numpy as np
import shapely
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union

from moduleforge.drc import check
from moduleforge.drc.rules import DesignRules, measure_rules
from moduleforge.geometry import DC_PLUS, NETS, PHASE, SIGNAL_NET, SIGNAL_PADS, Layout, SignalWire, Trace, arc_wire

MM = 1e-3
MOVE_TYPES = ("die_row_shift", "trace_width", "terminal_copper", "wire_landing")
COMPOUND = "compound"  # a re-layout applying two or three of the MOVE_TYPES together (founder guidance I0217)
PAIR_KINDS = MOVE_TYPES + (COMPOUND,)  # what ``draw``'s allocation counts: each single move type, and compounds
SWITCHES = ("HS", "LS")
SIDES = ("E", "W", "N", "S")

# ----------------------------------------------------------------------------------------------- frozen ranges (whole mm)
# Developed on 2D_Case_4 only (F2): each range covers, with slack, the whole span of DRC-clean values an exhaustive Case 4
# scan found (die shift dx -3..11, dy -7..2; landing dx -14..11, dy -1..2; trace delta -5..7; terminal margin and delta up
# to the scanned 12); the redraw rejects what a reference's rules do not allow.
DIE_SHIFT_MM = (-12, 12)  # dx and dy of the die row (inclusive); (0, 0) is not drawn
TRACE_DELTA_MM = (-10, 10)  # edge offset (inclusive); 0 is not drawn
TERMINAL_MARGIN_MM = (0, 10)  # window around the terminal pad (inclusive)
TERMINAL_DELTA_MM = (-10, 10)  # growth of one window side (inclusive); 0 is not drawn
LANDING_SHIFT_MM = (-15, 15)  # dx and dy of the landing points (inclusive); (0, 0) is not drawn
MAX_REDRAWS = 2000  # consecutive rejected draws of one pair before ``draw`` raises
LONG_SIDE_MIN_MM = 2  # edges shorter than this are never offered to ``trace_width``
DROPPED_MEASURED_RULES = ("min_signal_wire_length",)  # D0018 item 1, as e010_run.DROPPED_MEASURED_RULES
LATTICES_M = (1.0e-3, 0.5e-3, 0.25e-3)  # l2_layout's ladder for O004: every output must lie on all three
COMPOUND_SIZES = (2, 3)  # number of distinct move types in a compound (drawn uniformly), each from its own frozen range


def ranges() -> dict:
    """The frozen ranges and limits as they are now (what ``draw`` uses and ``rules_sha256`` hashes)."""
    return {"die_shift_mm": DIE_SHIFT_MM, "trace_delta_mm": TRACE_DELTA_MM, "terminal_margin_mm": TERMINAL_MARGIN_MM,
            "terminal_delta_mm": TERMINAL_DELTA_MM, "landing_shift_mm": LANDING_SHIFT_MM, "max_redraws": MAX_REDRAWS,
            "long_side_min_mm": LONG_SIDE_MIN_MM, "lattices_m": LATTICES_M, "compound_sizes": COMPOUND_SIZES}


@dataclass(frozen=True)
class Move:
    """One drawn pair: ``move_type`` is one of PAIR_KINDS; ``params`` are whole-mm integers / names (see the ``_apply_*``
    functions), for a compound ``{"moves": [{"move_type": ..., "params": ...}, ...]}`` (``_apply_compound``)."""

    move_type: str
    params: Mapping


# --------------------------------------------------------------------------------------------------------------- lattice
def on_lattice(layout: Layout, cell_m: float) -> bool:
    """True iff ``layout`` lies on l2_layout's lattice of cell size ``cell_m`` (m): ``layout_lattice`` finds a whole number of
    cells, every trace / plane edge is on a cell boundary (``cell_fill``) and every die footprint passes ``check_on_lattice``.
    ``l2_layout.CELL[0]`` is replaced during the call (the module has no other hook) and restored."""
    from moduleforge.solvers import l2_layout as L2
    cm = layout.to_conductors()
    saved = L2.CELL
    try:
        L2.CELL = (float(cell_m),) + tuple(saved[1:])
        try:
            lat = L2.layout_lattice(cm, 0)
            L2.cell_fill(cm, *lat)
            for d in cm.shorts:
                L2.check_on_lattice(d.x - d.w / 2, d.x + d.w / 2, d.y - d.h / 2, d.y + d.h / 2, *lat[:4],
                                    f"die {d.die_index} footprint")
        except ValueError:
            return False
    finally:
        L2.CELL = saved
    return True


# ------------------------------------------------------------------------------------------------------------------ rules
def require_whole_mm(layout: Layout) -> None:
    """ValueError unless every coordinate the moves round to whole mm (``_mm``) is already a whole number of mm: the trace
    vertices, the die boxes and the terminal boxes.  The moves work on integer-mm copies of these, so a reference off the 1 mm
    lattice would have its absolute coordinates rounded (and e.g. a long side at y = 20.5 mm read as y = 20 mm)."""
    bad = []
    for t in layout.traces:
        bad += [(f"trace {t.net}", c) for ring in (t.polygon.exterior, *t.polygon.interiors) for xy in ring.coords for c in xy]
    for k, d in enumerate(layout.dies):
        bad += [(f"die {k}", c) for c in d.bounds]
    for n, t in layout.terminals.items():
        bad += [(f"terminal {n}", c) for c in (t.cx - t.w / 2, t.cy - t.h / 2, t.cx + t.w / 2, t.cy + t.h / 2)]
    off = [(what, c / MM) for what, c in bad if abs(c / MM - round(c / MM)) > 1e-6]
    if off:
        raise ValueError(f"the reference is not on the whole-mm lattice the perturbation rules need: {off[0][0]} has a "
                         f"coordinate {off[0][1]!r} mm ({len(off)} such coordinates)")


def measured_rules(reference: Layout, overrides: Mapping | None = None) -> DesignRules:
    """The reference's measured design rules as E010 builds them (``e010_run.e008_rules``): ``measure_rules`` with the
    ``min_signal_wire_length`` lower bound dropped, then ``overrides`` (development references only; never for the judged
    ones).  ValueError if the reference itself is not DRC-clean under them (the rules cannot be derived: stop, do not
    substitute rules)."""
    require_whole_mm(reference)
    ov = dict(overrides or {})
    if set(ov) & set(DROPPED_MEASURED_RULES):
        raise ValueError(f"an override sets a dropped rule: {sorted(set(ov) & set(DROPPED_MEASURED_RULES))}")
    measured, _ = measure_rules(reference)
    rules = dataclasses.replace(measured, **{k: None for k in DROPPED_MEASURED_RULES}, **ov)
    bad = check(reference, rules)
    if bad:
        raise ValueError(f"the reference is not DRC-clean under its measured rules: {[v.rule for v in bad][:5]}")
    return rules


# --------------------------------------------------------------------------------------------------------------- helpers
def _mm(v: float) -> int:
    return int(round(v / MM))


def _int(v, name: str) -> int:
    if isinstance(v, bool) or int(v) != v:
        raise ValueError(f"{name} must be a whole number of mm, got {v!r}")
    return int(v)


def _box_mm(x0, y0, x1, y1) -> Polygon:
    return box(x0 * MM, y0 * MM, x1 * MM, y1 * MM)


def _rewire(w, start, end):
    p = w.points
    return arc_wire(start, end, float(p[0, 2]), float(p[-1, 2]), w.loop_height, w.diameter, w.net, npts=len(p))


def _source_owner(layout: Layout, xy, tol: float = 1e-9):
    for k, d in enumerate(layout.dies):
        p = d.pads.get("source")
        if p and p[0] - tol <= xy[0] <= p[2] + tol and p[1] - tol <= xy[1] <= p[3] + tol:
            return k
    return None


def _polygon(net: str, geom) -> Polygon:
    if isinstance(geom, Polygon) and not geom.is_empty:
        return geom
    raise ValueError(f"{net} copper is not a single polygon after the move")


def _tag(reference: Layout, move_type: str, params: Mapping) -> str:
    return f"{reference.family}|perturb:{move_type}:{json.dumps(dict(params), sort_keys=True)}"


def _canonical(poly: Polygon) -> Polygon:
    """``poly`` without collinear or repeated vertices, normalized (a union with copper already there changes nothing)."""
    return shapely.normalize(shapely.simplify(poly, 0.0))


def _set_net(layout: Layout, net: str, poly: Polygon) -> None:
    layout.traces = [Trace(t.net, _canonical(poly)) if t.net == net else t for t in layout.traces]


def _net_poly(layout: Layout, net: str) -> Polygon:
    polys = [t.polygon for t in layout.traces if t.net == net]
    if len(polys) != 1:
        raise ValueError(f"net {net} must have exactly one trace in the reference")
    return polys[0]


# ------------------------------------------------------------------------------------------------------ (a) die-row shift
def row_axis(reference: Layout, switch: str) -> str:
    """'x' or 'y': the axis along which the dies of ``switch`` are lined up (their centres spread along it; with one die, or
    no spread, the axis across the mean direction of the die's power wires).  ValueError if the dies are not on one line."""
    ds = [d for d in reference.dies if d.switch == switch]
    if not ds:
        raise ValueError(f"no {switch} die")
    sx = max(d.cx for d in ds) - min(d.cx for d in ds)
    sy = max(d.cy for d in ds) - min(d.cy for d in ds)
    if sx > 1e-9 and sy > 1e-9:
        raise ValueError(f"the {switch} dies are not on one row")
    if sx > 1e-9 or sy > 1e-9:
        return "x" if sx > 1e-9 else "y"
    idx = {k for k, d in enumerate(reference.dies) if d.switch == switch}
    v = [w.points[-1, :2] - w.points[0, :2] for w in reference.wires
         if _source_owner(reference, (float(w.points[0, 0]), float(w.points[0, 1]))) in idx]
    m = np.abs(np.asarray(v)).sum(axis=0) if v else np.array([0.0, 1.0])
    return "x" if m[1] >= m[0] else "y"


def _apply_die_row_shift(ref: Layout, p: Mapping) -> Layout:
    sw, dx, dy = p["switch"], _int(p["dx_mm"], "dx_mm"), _int(p["dy_mm"], "dy_mm")
    if sw not in SWITCHES:
        raise ValueError(f"switch must be one of {SWITCHES}")
    idx = [k for k, d in enumerate(ref.dies) if d.switch == sw]
    if not idx:
        raise ValueError(f"no {sw} die")
    along = row_axis(ref, sw)
    host_net = {"HS": DC_PLUS, "LS": PHASE}[sw]
    # reference enclosure of the row's dies in their host copper (whole mm, >= 1)
    host = _net_poly(ref, host_net)
    enc = min(host.exterior.distance(ref.dies[k].box) for k in idx)
    enc_mm = max(1, int(math.floor(enc / MM + 1e-6)))
    s, dxm, dym = set(idx), dx * MM, dy * MM
    # the along-row part of the shift moves the wire landings too (the wires move rigidly with the row); the across-row part
    # moves only the starts (the wires stretch or shrink towards their fixed landings)
    lxm, lym = (dxm, 0.0) if along == "x" else (0.0, dym)
    out = copy.deepcopy(ref)
    for k in idx:
        d = out.dies[k]
        d.cx, d.cy = d.cx + dxm, d.cy + dym
        d.pads = {n: (r[0] + dxm, r[1] + dym, r[2] + dxm, r[3] + dym) for n, r in d.pads.items()}
    for i, w in enumerate(ref.wires):
        if _source_owner(ref, (float(w.points[0, 0]), float(w.points[0, 1]))) in s:
            out.wires[i] = _rewire(w, (float(w.points[0, 0]) + dxm, float(w.points[0, 1]) + dym),
                                   (float(w.points[-1, 0]) + lxm, float(w.points[-1, 1]) + lym))
    for i, sg in enumerate(ref.signal_wires):
        if sg.die in s:
            q = sg.points
            nw = arc_wire((float(q[0, 0]) + dxm, float(q[0, 1]) + dym), (float(q[-1, 0]) + lxm, float(q[-1, 1]) + lym),
                          float(q[0, 2]), float(q[-1, 2]), sg.loop_height, sg.diameter, sg.net, npts=len(q))
            out.signal_wires[i] = SignalWire(sg.die, sg.pad, sg.net, nw.points, sg.diameter, sg.loop_height)
    grown = [host] + [_box_mm(*(_mm(c) - sgn * enc_mm for c, sgn in zip(out.dies[k].bounds, (1, 1, -1, -1), strict=True)))
                      for k in idx]
    _set_net(out, host_net, _polygon(host_net, unary_union(grown)))
    out.family = _tag(ref, "die_row_shift", p)
    return out


# ------------------------------------------------------------------------------------------------------- (b) trace width
def long_sides(poly: Polygon) -> list[tuple[str, int, int, int]]:
    """Axis-aligned exterior edges of ``poly`` at least ``LONG_SIDE_MIN_MM`` long and at least as long as the band is wide
    (distance to the opposite boundary along the inward normal at the edge midpoint), as (axis, c, a0, a1) in whole mm:
    'h' = horizontal edge at y = c from x = a0 to a1, 'v' = vertical at x = c from y = a0 to a1.  Sorted."""
    out = []
    poly = _canonical(poly)  # the edge set must not depend on collinear splits in the vertex list
    xy = [(_mm(x), _mm(y)) for x, y in poly.exterior.coords]
    for (x0, y0), (x1, y1) in zip(xy[:-1], xy[1:], strict=True):
        if (x0 != x1) == (y0 != y1):
            continue
        axis, c, a0, a1 = ("h", y0, min(x0, x1), max(x0, x1)) if y0 == y1 else ("v", x0, min(y0, y1), max(y0, y1))
        if a1 - a0 < LONG_SIDE_MIN_MM:
            continue
        n = _outward(poly, axis, c, a0, a1)
        mid = (a0 + a1) / 2
        o = (mid, c) if axis == "h" else (c, mid)
        d_in = (0, -n) if axis == "h" else (-n, 0)
        far = (o[0] + d_in[0] * 1e3, o[1] + d_in[1] * 1e3)  # ray inward, 1e3 mm long
        hit = LineString([(o[0] * MM + d_in[0] * 1e-6, o[1] * MM + d_in[1] * 1e-6), (far[0] * MM, far[1] * MM)]) \
            .intersection(poly.exterior)
        width = Point(o[0] * MM, o[1] * MM).distance(hit) / MM if not hit.is_empty else math.inf
        if a1 - a0 >= width - 1e-6:
            out.append((axis, c, a0, a1))
    return sorted(set(out))


def _outward(poly: Polygon, axis: str, c: int, a0: int, a1: int) -> int:
    mid = (a0 + a1) / 2
    for n in (1, -1):
        q = (mid * MM, (c + n * 1e-3) * MM) if axis == "h" else ((c + n * 1e-3) * MM, mid * MM)
        if not poly.contains(Point(q)):
            return n
    raise ValueError("edge has copper on both sides")


def _apply_trace_width(ref: Layout, p: Mapping) -> Layout:
    net, e, delta = p["net"], _int(p["edge"], "edge"), _int(p["delta_mm"], "delta_mm")
    if net not in NETS or delta == 0:
        raise ValueError("net must be a power net and delta_mm nonzero")
    poly = _net_poly(ref, net)
    sides = long_sides(poly)
    if not 0 <= e < len(sides):
        raise ValueError(f"edge index {e} outside 0..{len(sides) - 1}")
    axis, c, a0, a1 = sides[e]
    n = _outward(poly, axis, c, a0, a1)
    lo, hi = sorted((c, c + n * delta))
    strip = _box_mm(a0, lo, a1, hi) if axis == "h" else _box_mm(lo, a0, hi, a1)
    new = poly.union(strip) if delta > 0 else poly.difference(strip)
    out = copy.deepcopy(ref)
    _set_net(out, net, _polygon(net, new))
    out.family = _tag(ref, "trace_width", p)
    return out


# --------------------------------------------------------------------------------------------------- (c) terminal copper
def _apply_terminal_copper(ref: Layout, p: Mapping) -> Layout:
    net, side = p["net"], p["side"]
    m, delta = _int(p["margin_mm"], "margin_mm"), _int(p["delta_mm"], "delta_mm")
    if net not in NETS or side not in SIDES or delta == 0 or m < 0:
        raise ValueError("bad terminal_copper parameters")
    t = ref.terminals[net]
    x0, y0, x1, y1 = (_mm(c) for c in (t.cx - t.w / 2, t.cy - t.h / 2, t.cx + t.w / 2, t.cy + t.h / 2))
    x0, y0, x1, y1 = x0 - m, y0 - m, x1 + m, y1 + m  # the window
    a = abs(delta)
    slab = {"E": (x1, y0, x1 + a, y1) if delta > 0 else (x1 - a, y0, x1, y1),
            "W": (x0 - a, y0, x0, y1) if delta > 0 else (x0, y0, x0 + a, y1),
            "N": (x0, y1, x1, y1 + a) if delta > 0 else (x0, y1 - a, x1, y1),
            "S": (x0, y0 - a, x1, y0) if delta > 0 else (x0, y0, x1, y0 + a)}[side]
    poly = _net_poly(ref, net)
    new = poly.union(_box_mm(*slab)) if delta > 0 else poly.difference(_box_mm(*slab))
    out = copy.deepcopy(ref)
    _set_net(out, net, _polygon(net, new))
    out.family = _tag(ref, "terminal_copper", p)
    return out


# ----------------------------------------------------------------------------------------------------- (d) wire landing
def _apply_wire_landing(ref: Layout, p: Mapping) -> Layout:
    sw, dx, dy = p["switch"], _int(p["dx_mm"], "dx_mm"), _int(p["dy_mm"], "dy_mm")
    if sw not in SWITCHES:
        raise ValueError(f"switch must be one of {SWITCHES}")
    out = copy.deepcopy(ref)
    for i, w in enumerate(ref.wires):
        k = _source_owner(ref, (float(w.points[0, 0]), float(w.points[0, 1])))
        if k is not None and ref.dies[k].switch == sw:
            out.wires[i] = _rewire(w, (float(w.points[0, 0]), float(w.points[0, 1])),
                                   (float(w.points[-1, 0]) + dx * MM, float(w.points[-1, 1]) + dy * MM))
    out.family = _tag(ref, "wire_landing", p)
    return out


_APPLY = {"die_row_shift": _apply_die_row_shift, "trace_width": _apply_trace_width,
          "terminal_copper": _apply_terminal_copper, "wire_landing": _apply_wire_landing}


# ------------------------------------------------------------------------------------------------------- compound (I0217)
def components(move_type: str, params: Mapping) -> list[tuple[str, Mapping]]:
    """The single moves a pair applies, in order: ``[(move_type, params)]`` for a single move; for a compound its
    ``params["moves"]``, checked: COMPOUND_SIZES many, distinct move types, in MOVE_TYPES order (so one set of move types has
    one order)."""
    if move_type != COMPOUND:
        return [(move_type, params)]
    parts = params.get("moves") if isinstance(params, Mapping) else None
    if not isinstance(parts, list | tuple) or len(parts) not in COMPOUND_SIZES:
        raise ValueError(f"a compound applies {COMPOUND_SIZES} moves, given as params['moves']")
    out = []
    for q in parts:
        if not isinstance(q, Mapping) or q.get("move_type") not in MOVE_TYPES or not isinstance(q.get("params"), Mapping):
            raise ValueError(f"a compound component is {{'move_type': one of {MOVE_TYPES}, 'params': {{...}}}}, got {q!r}")
        out.append((q["move_type"], q["params"]))
    types = [t for t, _ in out]
    if types != [t for t in MOVE_TYPES if t in types] or len(set(types)) != len(types):
        raise ValueError(f"compound move types must be distinct and in MOVE_TYPES order, got {types}")
    return out


def _apply_compound(ref: Layout, p: Mapping) -> Layout:
    """The components applied one after another, each to the previous one's result (its parameters are read on that
    layout: e.g. a trace_width edge index counts the long sides of the copper as the earlier components left it)."""
    out = ref
    for mt, q in components(COMPOUND, p):
        out = _APPLY[mt](out, q)
    out.family = _tag(ref, COMPOUND, p)
    return out


def apply(reference: Layout, move_type: str, params: Mapping) -> Layout:
    """Deterministic re-layout of ``reference`` by one move or one compound (whole-mm ``params``).  The result is not
    DRC-checked (``draw`` only returns clean ones); ValueError for malformed parameters or a net whose copper stops being
    one polygon."""
    if move_type == COMPOUND:
        return _apply_compound(reference, params)
    if move_type not in _APPLY:
        raise ValueError(f"unknown move type {move_type!r}; expected one of {PAIR_KINDS}")
    return _APPLY[move_type](reference, params)


# ------------------------------------------------------------------------------------------------------------------ draw
def _nonzero(rng: np.random.Generator, lo: int, hi: int) -> int:
    while True:
        v = int(rng.integers(lo, hi + 1))
        if v:
            return v


def _draw_params(reference: Layout, move_type: str, rng: np.random.Generator) -> dict:
    if move_type in ("die_row_shift", "wire_landing"):
        lo, hi = DIE_SHIFT_MM if move_type == "die_row_shift" else LANDING_SHIFT_MM
        sw = SWITCHES[int(rng.integers(2))]
        while True:
            dx, dy = int(rng.integers(lo, hi + 1)), int(rng.integers(lo, hi + 1))
            if dx or dy:
                return {"switch": sw, "dx_mm": dx, "dy_mm": dy}
    if move_type == "trace_width":
        # the net is drawn first and only its long sides are evaluated: a net whose long sides cannot be read (an edge with
        # copper on both sides) or that has none makes this draw invalid (ValueError, redrawn by ``_draw_single``) instead
        # of making every trace_width draw on the layout fail
        net = NETS[int(rng.integers(len(NETS)))]
        n = len(long_sides(_net_poly(reference, net)))
        if not n:
            raise ValueError(f"net {net} has no long side")
        return {"net": net, "edge": int(rng.integers(n)), "delta_mm": _nonzero(rng, *TRACE_DELTA_MM)}
    net = NETS[int(rng.integers(len(NETS)))]
    if move_type == "terminal_copper":
        return {"net": net, "side": SIDES[int(rng.integers(4))], "margin_mm": int(rng.integers(TERMINAL_MARGIN_MM[0],
                                                                                              TERMINAL_MARGIN_MM[1] + 1)),
                "delta_mm": _nonzero(rng, *TERMINAL_DELTA_MM)}
    raise ValueError(move_type)


def geometry_key(layout: Layout) -> str:
    """Fingerprint of ``layout`` with its ``family`` label left out and every trace polygon canonical (``_canonical``): two
    layouts with the same key are the same geometry, however their polygons' vertex lists were built."""
    return dataclasses.replace(layout, family="", traces=[Trace(t.net, _canonical(t.polygon)) for t in layout.traces]
                               ).fingerprint()


def _draw_single(reference: Layout, kind: str, rng: np.random.Generator, rules: DesignRules, seen: set) -> tuple[dict, Layout]:
    """One single move of ``kind`` on ``reference``: parameters redrawn until the move applies, changes the geometry, is
    DRC-clean under ``rules`` and gives a geometry not in ``seen``; RuntimeError after MAX_REDRAWS consecutive rejections."""
    for _try in range(MAX_REDRAWS):
        try:
            params = _draw_params(reference, kind, rng)
            new = apply(reference, kind, params)
        except ValueError:
            continue
        if geometry_key(new) not in seen and not check(new, rules):
            return params, new
    raise RuntimeError(f"no new DRC-clean {kind} move in {MAX_REDRAWS} consecutive draws")


def _draw_compound(reference: Layout, rng: np.random.Generator, rules: DesignRules, seen: set) -> tuple[dict, Layout]:
    """One compound: its size from COMPOUND_SIZES and its distinct move types (in MOVE_TYPES order) drawn uniformly, then
    each component drawn as a single move (``_draw_single``, same frozen ranges and rejection limit) on the layout the
    earlier components left, so every intermediate layout is a DRC-clean re-layout and every component changes the
    geometry.  The whole compound is redrawn (up to MAX_REDRAWS times) while its geometry is in ``seen``."""
    for _try in range(MAX_REDRAWS):
        k = COMPOUND_SIZES[int(rng.integers(len(COMPOUND_SIZES)))]
        types = [MOVE_TYPES[i] for i in sorted(int(j) for j in rng.choice(len(MOVE_TYPES), size=k, replace=False))]
        cur, parts = reference, []
        for mt in types:
            q, cur = _draw_single(cur, mt, rng, rules, {geometry_key(cur)})
            parts.append({"move_type": mt, "params": q})
        if geometry_key(cur) not in seen:
            params = {"moves": parts}
            cur.family = _tag(reference, COMPOUND, params)
            return params, cur
    raise RuntimeError(f"no new DRC-clean {COMPOUND} move in {MAX_REDRAWS} consecutive draws")


def draw(reference: Layout, allocation: Mapping[str, int], seed: int, rules: DesignRules | None = None) -> list[Move]:
    """``allocation[kind]`` pairs per pair kind (a mapping from PAIR_KINDS: each single move type and ``COMPOUND``) as
    ``Move`` records, in PAIR_KINDS order then draw order.  One ``numpy`` Generator seeded by ``seed`` (no global state);
    every returned move is DRC-clean under ``rules`` (default ``measured_rules(reference)``), changes the geometry (each
    component of a compound changes it too) and gives a geometry distinct from the reference's and from every other returned
    move's, single or compound (``geometry_key``).  RuntimeError after ``MAX_REDRAWS`` consecutive rejected draws of a
    pair."""
    unknown = set(allocation) - set(PAIR_KINDS)
    if unknown:
        raise ValueError(f"unknown pair kinds {sorted(unknown)}; expected {PAIR_KINDS}")
    require_whole_mm(reference)
    rules = measured_rules(reference) if rules is None else rules
    rng = np.random.default_rng(seed)
    seen = {geometry_key(reference)}
    out: list[Move] = []
    for kind in PAIR_KINDS:
        for _ in range(_int(allocation.get(kind, 0), "allocation")):
            pick = _draw_compound if kind == COMPOUND else partial(_draw_single, kind=kind)
            params, new = pick(reference, rng=rng, rules=rules, seen=seen)
            seen.add(geometry_key(new))
            out.append(Move(kind, params))
    return out


def _rule_sources() -> list[tuple[str, str]]:
    """(name, source text) of everything that decides which layouts a seed yields: this module's whole source (moves, draw,
    helpers, constants), the DRC (``moduleforge.drc``: ``check``, ``measure_rules``, ``DesignRules``), the wire constructor
    ``geometry.layout.arc_wire`` and the fingerprint (``Layout.fingerprint``, the distinctness test), and l2_layout's lattice
    rule (``layout_lattice``, ``check_on_lattice``, ``cell_fill``, ``_snap_aligned``, ``rect_cover``, ``_overlap_1d``,
    ``ALIGN_TOL``)."""
    import sys

    import moduleforge.drc as drc_pkg
    import moduleforge.drc.rules as drc_rules
    from moduleforge.geometry import layout as geo
    from moduleforge.solvers import l2_layout as L2
    mods = [("generate.perturb", inspect.getsource(sys.modules[__name__])), ("drc", inspect.getsource(drc_pkg)),
            ("drc.rules", inspect.getsource(drc_rules))]
    fns = [("geometry.layout.arc_wire", inspect.getsource(geo.arc_wire)),
           ("geometry.layout.Layout.fingerprint", inspect.getsource(geo.Layout.fingerprint))]
    fns += [(f"solvers.l2_layout.{f.__name__}", inspect.getsource(f)) for f in
            (L2.layout_lattice, L2.check_on_lattice, L2.cell_fill, L2._snap_aligned, L2.rect_cover, L2._overlap_1d)]
    fns.append(("solvers.l2_layout.ALIGN_TOL", repr(L2.ALIGN_TOL)))
    # inputs the rng indexes or the DRC / draw read through the geometry package: NETS is indexed by the rng (its order
    # decides which net a draw picks), SIGNAL_NET / SIGNAL_PADS decide the signal wires' nets, and the Die.box,
    # BondWire.length and SignalWire.length properties are what the DRC measures
    fns += [("geometry.layout.NETS", repr(tuple(NETS))), ("geometry.layout.SIGNAL_PADS", repr(tuple(SIGNAL_PADS))),
            ("geometry.layout.SIGNAL_NET", json.dumps({f"{p}|{s}": n for (p, s), n in SIGNAL_NET.items()}, sort_keys=True)),
            ("geometry.layout.Die.box", inspect.getsource(geo.Die.box.fget)),
            ("geometry.layout.BondWire.length", inspect.getsource(geo.BondWire.length.fget)),
            ("geometry.layout.SignalWire.length", inspect.getsource(geo.SignalWire.length.fget))]
    return mods + fns


def rules_sha256() -> str:
    """SHA-256 over the rule sources (``_rule_sources``: the compound rule and its draw are part of this module's source)
    and the frozen ranges (``ranges()``, COMPOUND_SIZES included, and the name tuples, PAIR_KINDS included, as they are at
    call time), for E004's spec to freeze (F2)."""
    h = hashlib.sha256()
    for name, src in _rule_sources():
        h.update(f"{name}\n{len(src)}\n".encode())
        h.update(src.encode())
    h.update(json.dumps({"ranges": ranges(), "names": [PAIR_KINDS, SWITCHES, SIDES, DROPPED_MEASURED_RULES], "mm": MM},
                        sort_keys=True).encode())
    return h.hexdigest()
