"""Manufacturing design rules (DRC) for wire-bonded DBC/AMB half-bridge layouts.

Default values are *typical* DBC/AMB design-guide numbers (Rogers/curamik and Heraeus/Kyocera substrate
design guidelines for 0.3 mm Cu: min. trace width ~1 mm, min. Cu-Cu isolation spacing ~1 mm, Cu-to-ceramic-edge
margin ~1 mm; die-to-Cu-edge margin ~1 mm; Al wire bonding pitch >= ~2 wire diameters; heavy Al bond wire
diameters ~100-500 um as in Heraeus / Hesse Bondtec heavy-Al-wire product ranges). They are placeholders
to be replaced with the customer's vendor rules; all lengths are SI (m).
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from shapely.geometry import LineString, Point, box
from shapely.ops import unary_union

from moduleforge.geometry import DC_MINUS, DC_PLUS, NETS, PHASE, SIGNAL_NET, SIGNAL_PADS, Layout
from moduleforge.geometry.units import mm_to_m

TOL = 1e-9  # geometric comparison tolerance, 1 nm
WIDTH_TOL = 1e-7  # min_trace_width tolerance, 0.1 um: well above GEOS buffer precision (~1e-9 m at mm scale)


@dataclass(frozen=True)
class DesignRules:
    min_trace_width: float = mm_to_m(1.0)
    min_spacing: float = mm_to_m(1.0)
    edge_margin: float = mm_to_m(1.0)
    die_edge_margin: float = mm_to_m(1.0)
    die_spacing: float = mm_to_m(1.0)
    min_wire_length: float = mm_to_m(1.5)
    max_wire_length: float = mm_to_m(15.0)
    min_wire_pitch: float = mm_to_m(0.6)  # 2 x 0.3 mm wire diameter
    wire_landing_margin: float = mm_to_m(0.3)
    wire_pitch_diameters: float = 2.0  # pitch >= this many wire diameters (module docstring: ~2)
    min_wire_diameter: float = mm_to_m(0.1)  # placeholder, heavy Al wire (see module docstring)
    max_wire_diameter: float = mm_to_m(0.5)  # placeholder, heavy Al wire (see module docstring)
    # placeholder: same-net die-to-terminal-pad clearance, equal to the die-to-Cu-edge margin (1 mm)
    die_terminal_clearance: float = mm_to_m(1.0)
    # placeholder: a bond foot must sit >= half a typical 0.3 mm heavy-Al wire diameter inside the pad edge
    # so the wedge footprint does not overhang the metallisation
    wire_start_margin: float = mm_to_m(0.15)
    # Optional per-net-pair spacing; ``None`` = use ``min_spacing`` (the default, so behaviour is unchanged).
    # ``spacing_other`` applies to every net pair that is not one of the three power pairs (including two
    # separate pieces of copper of the same net).
    spacing_dcp_phase: float | None = None
    spacing_phase_dcm: float | None = None
    spacing_dcp_dcm: float | None = None
    spacing_other: float | None = None
    # Optional minimum width per net class; ``None`` = use ``min_trace_width``.
    min_width_power: float | None = None  # nets DC+, PHASE, DC-
    min_width_other: float | None = None  # every other net (gate, Kelvin, ...)
    # Optional bondability limits; ``None`` = not enforced. When set, every die that has a gate (Kelvin) pad must
    # have that pad within this plan distance of the fixed copper of its own switch's gate (Kelvin) net
    # (``SIGNAL_NET``), and no gate (Kelvin) wire may be longer.
    max_gate_wire_length: float | None = None
    max_kelvin_wire_length: float | None = None

    def spacing_for(self, net_a: str, net_b: str) -> float:
        """Minimum copper spacing required between nets ``net_a`` and ``net_b``."""
        pair = frozenset((net_a, net_b))
        v = {
            frozenset((DC_PLUS, PHASE)): self.spacing_dcp_phase,
            frozenset((PHASE, DC_MINUS)): self.spacing_phase_dcm,
            frozenset((DC_PLUS, DC_MINUS)): self.spacing_dcp_dcm,
        }.get(pair, self.spacing_other)
        return self.min_spacing if v is None else v

    def width_for(self, net: str) -> float:
        """Minimum trace width required for copper of net ``net``."""
        v = self.min_width_power if net in NETS else self.min_width_other
        return self.min_trace_width if v is None else v


DEFAULT_RULES = DesignRules()


@dataclass(frozen=True)
class Violation:
    rule: str
    message: str
    where: tuple[float, float] | None = None


def _pt(g):
    c = g.representative_point()
    return (float(c.x), float(c.y))


def _topology(g) -> tuple[int, int]:
    """(number of polygon pieces, total number of holes) of a shapely geometry."""
    polys = [p for p in getattr(g, "geoms", [g]) if p.geom_type == "Polygon" and not p.is_empty]
    return len(polys), sum(len(p.interiors) for p in polys)


def _width_problem(poly, width: float):
    """(``'thin'`` | ``'neck'`` | None, where) for polygon ``poly`` against minimum width ``width``.

    ``thin``: the morphological opening with a square of side ``width`` loses area. ``neck``: eroding by half
    the width splits the trace into more pieces than it has, or closes a hole into the outside (a neck closing
    a copper loop turns the ring into a C: one piece, fewer holes).
    """
    mit = {"join_style": "mitre", "mitre_limit": 10.0}
    r = width / 2 - WIDTH_TOL
    opened = poly.buffer(-r, **mit).buffer(r, **mit)
    thin = poly.difference(opened)
    if thin.area > 1e-12:
        return "thin", _pt(thin)
    eroded = poly.buffer(-r, **mit)
    if (_topology(eroded)[0] > _topology(poly)[0]) or (_topology(eroded)[1] < _topology(poly)[1]):
        return "neck", _pt(poly)
    return None, None


def _edge_ok(layout: Layout, poly, margin: float) -> bool:
    mit = {"join_style": "mitre", "mitre_limit": 10.0}
    return layout.outline.buffer(-(margin - TOL), **mit).contains(poly)


def _die_edge_ok(trace_poly, die_box, margin: float) -> bool:
    mit = {"join_style": "mitre", "mitre_limit": 10.0}
    return trace_poly.buffer(-(margin - TOL), **mit).contains(die_box)


def check(layout: Layout, rules: DesignRules = DEFAULT_RULES) -> list[Violation]:
    """Return all rule violations (empty list = DRC clean)."""
    v: list[Violation] = []
    mit = {"join_style": "mitre", "mitre_limit": 10.0}

    # min_trace_width (per net class): morphological opening with a square element of side min width
    for i, t in enumerate(layout.traces):
        kind, where = _width_problem(t.polygon, rules.width_for(t.net))
        if kind == "thin":
            v.append(Violation("min_trace_width", f"trace {i} ({t.net}) narrower than min width", where))
        elif kind == "neck":
            v.append(Violation("min_trace_width", f"trace {i} ({t.net}) has a neck narrower than min width", where))

    # net_split: each net's copper must be a single connected island
    for net in sorted({t.net for t in layout.traces}):
        merged = unary_union([t.polygon for t in layout.traces if t.net == net])
        if len(getattr(merged, "geoms", [merged])) > 1:
            v.append(Violation("net_split", f"net {net} copper is split into {len(merged.geoms)} islands",
                               _pt(merged)))

    # min_spacing
    for i in range(len(layout.traces)):
        for j in range(i + 1, len(layout.traces)):
            a, b = layout.traces[i], layout.traces[j]
            d = a.polygon.distance(b.polygon)
            need = rules.spacing_for(a.net, b.net)
            if d < need - TOL:
                v.append(Violation("min_spacing", f"traces {i}/{j} ({a.net}/{b.net}) spacing {d:.3e} m < {need:.3e} m",
                                   _pt(a.polygon)))

    # edge margin
    for i, t in enumerate(layout.traces):
        if not _edge_ok(layout, t.polygon, rules.edge_margin):
            v.append(Violation("edge_margin", f"trace {i} ({t.net}) closer to substrate edge than margin",
                               _pt(t.polygon)))

    # die placement, net and margin
    want = {"HS": "DC+", "LS": "PHASE"}
    for i, d in enumerate(layout.dies):
        if d.switch not in want:
            v.append(Violation("die_bad_switch", f"die {i} has unknown switch {d.switch!r} (expected HS or LS)",
                               (d.cx, d.cy)))
        host = [t for t in layout.traces if t.polygon.contains(Point(d.cx, d.cy))]
        if not host:
            v.append(Violation("die_off_trace", f"die {i} not on any trace", (d.cx, d.cy)))
            continue
        if d.switch in want and host[0].net != want[d.switch]:
            v.append(Violation("die_wrong_net", f"die {i} ({d.switch}) on {host[0].net}", (d.cx, d.cy)))
        if not _die_edge_ok(host[0].polygon, d.box, rules.die_edge_margin):
            v.append(Violation("die_edge_margin", f"die {i} closer to trace edge than margin", (d.cx, d.cy)))
    for i in range(len(layout.dies)):
        for j in range(i + 1, len(layout.dies)):
            dist = layout.dies[i].box.distance(layout.dies[j].box)
            if dist < rules.die_spacing - TOL:
                v.append(Violation("die_spacing", f"dies {i}/{j} spacing {dist:.3e} m",
                                   (layout.dies[i].cx, layout.dies[i].cy)))

    # die / terminal keep-outs and switch presence
    pads = {net: box(tm.cx - tm.w / 2, tm.cy - tm.h / 2, tm.cx + tm.w / 2, tm.cy + tm.h / 2)
            for net, tm in layout.terminals.items()}
    for i, d in enumerate(layout.dies):
        for net, pad in pads.items():
            if d.box.buffer(-TOL).intersects(pad):
                v.append(Violation("die_on_terminal", f"die {i} overlaps terminal {net}", (d.cx, d.cy)))
            elif d.box.distance(pad) < rules.die_terminal_clearance - TOL:
                v.append(Violation("die_on_terminal", f"die {i} closer than clearance to terminal {net}",
                                   (d.cx, d.cy)))
    for sw in ("HS", "LS"):
        if not any(d.switch == sw for d in layout.dies):
            v.append(Violation("missing_switch", f"layout has no {sw} die"))

    # wires
    def on_source(d, x, y):
        p = d.pads.get("source")
        if p is None:
            return False
        return p[0] - TOL <= x <= p[2] + TOL and p[1] - TOL <= y <= p[3] + TOL

    for i, d in enumerate(layout.dies):
        if "source" not in d.pads:
            v.append(Violation("die_no_source_pad", f"die {i} ({d.switch}) has no source pad", (d.cx, d.cy)))

    expect = {"HS": "PHASE", "LS": "DC-"}
    bonded: set[int] = set()
    lines = []
    for i, w in enumerate(layout.wires):
        xy = (float(w.points[0, 0]), float(w.points[0, 1]))
        if not (rules.min_wire_length - TOL <= w.length <= rules.max_wire_length + TOL):
            v.append(Violation("wire_length", f"wire {i} length {w.length:.3e} m", xy))
        if not (rules.min_wire_diameter - TOL <= w.diameter <= rules.max_wire_diameter + TOL):
            v.append(Violation("wire_diameter", f"wire {i} diameter {w.diameter:.3e} m", xy))
        end = Point(w.points[-1, 0], w.points[-1, 1])
        ok = any(
            t.net == w.net and t.polygon.buffer(-(rules.wire_landing_margin - TOL), **mit).contains(end)
            for t in layout.traces
        )
        if not ok:
            v.append(Violation("wire_landing", f"wire {i} does not land on {w.net} Cu", (end.x, end.y)))
        if any(end.distance(g) < rules.wire_landing_margin - TOL
               for g in [d.box for d in layout.dies] + list(pads.values())):
            v.append(Violation("wire_landing_keepout", f"wire {i} lands too close to a die or terminal pad",
                               (end.x, end.y)))
        owners = [k for k, d in enumerate(layout.dies) if on_source(d, *xy)]
        if not owners:
            v.append(Violation("wire_start", f"wire {i} does not start on a die source pad", xy))
        else:
            bonded.update(owners)
            margin = max(rules.wire_start_margin, w.diameter / 2)  # bond foot must not overhang the pad
            if not any(box(*layout.dies[k].pads["source"]).buffer(-(margin - TOL), **mit)
                       .intersects(Point(xy)) for k in owners):
                v.append(Violation("wire_start", f"wire {i} starts closer than margin to its source-pad edge", xy))
            want_net = expect.get(layout.dies[owners[0]].switch)
            under = [t.net for t in layout.traces if t.polygon.buffer(TOL).contains(end)]
            if want_net is not None and (w.net != want_net or (under and want_net not in under)):
                v.append(Violation("wire_net", f"wire {i} from a {layout.dies[owners[0]].switch} die must land "
                                   f"on {want_net}; labelled {w.net}, copper under landing {under}", (end.x, end.y)))
        lines.append(LineString(w.points[:, :2]))
    for k, d in enumerate(layout.dies):
        if k not in bonded:
            v.append(Violation("die_unbonded", f"die {k} ({d.switch}) has no wire on its source pad", (d.cx, d.cy)))
    for i in range(len(lines)):
        for j in range(i + 1, len(lines)):
            d = lines[i].distance(lines[j])
            need = max(rules.min_wire_pitch,
                       rules.wire_pitch_diameters * max(layout.wires[i].diameter, layout.wires[j].diameter))
            if d < need - TOL:
                v.append(Violation("wire_pitch", f"wires {i}/{j} pitch {d:.3e} m < {need:.3e} m",
                                   (float(layout.wires[i].points[0, 0]), float(layout.wires[i].points[0, 1]))))

    v.extend(_check_signal(layout, rules, lines))

    # terminals must sit on their net's copper
    for net, tm in layout.terminals.items():
        pad = box(tm.cx - tm.w / 2, tm.cy - tm.h / 2, tm.cx + tm.w / 2, tm.cy + tm.h / 2).buffer(-TOL)
        if not any(t.net == net and t.polygon.contains(pad) for t in layout.traces):
            v.append(Violation("terminal_off_trace", f"terminal {net} not on {net} Cu", (tm.cx, tm.cy)))
    return v


def _on_pad(d, name: str, x: float, y: float) -> bool:
    p = d.pads.get(name)
    return p is not None and p[0] - TOL <= x <= p[2] + TOL and p[1] - TOL <= y <= p[3] + TOL


def _signal_limit(rules: DesignRules, pad: str) -> float | None:
    return rules.max_gate_wire_length if pad == "gate" else rules.max_kelvin_wire_length


def _check_signal(layout: Layout, rules: DesignRules, power_lines: list) -> list[Violation]:
    """Bondability of the gate / Kelvin pads and the geometry of the gate / Kelvin wires.

    Gate and Kelvin nets are per switch position (``SIGNAL_NET``): a pad of an HS die is checked against, and its
    wire must land on, HS gate (Kelvin) copper only, never the LS one, and vice versa.
    """
    v: list[Violation] = []
    mit = {"join_style": "mitre", "mitre_limit": 10.0}
    # bondability: each die's pad within the limit of the fixed copper of its own switch's net; a die without that
    # pad is not checked (the pad set belongs to the fixed die), a die with it but no copper of its net is flagged
    for pad in SIGNAL_PADS:
        limit = _signal_limit(rules, pad)
        if limit is None:
            continue
        for i, d in enumerate(layout.dies):
            net = SIGNAL_NET.get((pad, d.switch))
            if pad not in d.pads or net is None:  # an unknown switch is reported as die_bad_switch
                continue
            cu = [t.polygon for t in layout.traces if t.net == net]
            if not cu:
                v.append(Violation("signal_bondability", f"die {i} ({d.switch}) has a {pad} pad but the layout has "
                                   f"no {net} copper", (d.cx, d.cy)))
                continue
            dist = box(*d.pads[pad]).distance(unary_union(cu))
            if dist > limit + TOL:
                v.append(Violation("signal_bondability", f"die {i} ({d.switch}) {pad} pad is {dist:.3e} m from "
                                   f"{net} copper (> {limit:.3e} m)", (d.cx, d.cy)))
    lines = []
    for k, w in enumerate(layout.signal_wires):
        xy = (float(w.points[0, 0]), float(w.points[0, 1]))
        end = Point(w.points[-1, 0], w.points[-1, 1])
        lines.append(LineString(w.points[:, :2]))
        want = SIGNAL_NET.get((w.pad, layout.dies[w.die].switch)) if 0 <= w.die < len(layout.dies) else None
        if want is None or w.net != want:
            v.append(Violation("signal_wire_net", f"signal wire {k}: die {w.die}, pad {w.pad!r}, net {w.net!r}; "
                               f"expected a die index in range, a pad in {SIGNAL_PADS} and net {want!r}", xy))
            continue
        d = layout.dies[w.die]
        if not _on_pad(d, w.pad, *xy):
            v.append(Violation("signal_wire_start", f"signal wire {k} does not start on its die {w.die} {w.pad} pad",
                               xy))
        else:
            margin = max(rules.wire_start_margin, w.diameter / 2)  # bond foot must not overhang the pad
            if not box(*d.pads[w.pad]).buffer(-(margin - TOL), **mit).intersects(Point(xy)):
                v.append(Violation("signal_wire_start", f"signal wire {k} starts closer than margin to its "
                                   f"{w.pad}-pad edge", xy))
        if not any(t.net == w.net and t.polygon.buffer(-(rules.wire_landing_margin - TOL), **mit).contains(end)
                   for t in layout.traces):
            v.append(Violation("signal_wire_landing", f"signal wire {k} does not land on {w.net} Cu", (end.x, end.y)))
        limit = _signal_limit(rules, w.pad)
        if limit is not None and w.length > limit + TOL:
            v.append(Violation("signal_wire_length", f"signal wire {k} length {w.length:.3e} m > {limit:.3e} m", xy))
    # plan-view crossings with a wire of another net; pitch applies to every pair involving a signal wire
    nets = [w.net for w in layout.wires] + [w.net for w in layout.signal_wires]
    diams = [w.diameter for w in layout.wires] + [w.diameter for w in layout.signal_wires]
    all_lines = list(power_lines) + lines
    n_pow = len(power_lines)
    for i in range(n_pow, len(all_lines)):
        for j in range(i):
            a, b = all_lines[j], all_lines[i]
            where = (float(b.coords[0][0]), float(b.coords[0][1]))
            gap = a.distance(b)
            if nets[i] != nets[j] and gap == 0.0:
                v.append(Violation("signal_wire_cross", f"signal wire {i - n_pow} ({nets[i]}) crosses "
                                   f"{'signal wire ' + str(j - n_pow) if j >= n_pow else 'wire ' + str(j)} "
                                   f"({nets[j]})", where))
                continue
            need = max(rules.min_wire_pitch, rules.wire_pitch_diameters * max(diams[i], diams[j]))
            if gap < need - TOL:
                v.append(Violation("wire_pitch", f"signal wire {i - n_pow} / "
                                   f"{'signal wire ' + str(j - n_pow) if j >= n_pow else 'wire ' + str(j)} "
                                   f"pitch {gap:.3e} m < {need:.3e} m", where))
    return v


def _floor_nm(v: float) -> float:
    return math.floor(v * 1e9) / 1e9


def _ceil_nm(v: float) -> float:
    return math.ceil(v * 1e9) / 1e9


def _bisect_max(ok, hi: float, tol: float) -> float:
    """Largest ``x`` in [0, hi] (to within ``tol``, returned from the passing side) with ``ok(x)``.

    ``ok`` is assumed to hold at 0 and, if it holds at ``hi``, ``hi`` is returned. The returned value itself
    satisfies ``ok`` (checked, stepping down by ``tol`` if bisection hit a non-monotone spot).
    """
    if ok(hi):
        return hi
    lo = 0.0
    while hi - lo > tol:
        mid = 0.5 * (lo + hi)
        if ok(mid):
            lo = mid
        else:
            hi = mid
    while lo > 0.0 and not ok(lo):
        lo = max(0.0, lo - tol)
    return lo


_POWER_PAIRS = {
    frozenset((DC_PLUS, PHASE)): "dcp_phase",
    frozenset((PHASE, DC_MINUS)): "phase_dcm",
    frozenset((DC_PLUS, DC_MINUS)): "dcp_dcm",
}


def measure_rules(layout: Layout) -> tuple[DesignRules, dict]:
    """Measure the design rules a (snapped) layout itself satisfies: ``(rules, record)``.

    ``check(layout, rules)`` is empty for the returned rules whenever ``check(layout)`` under the default rules
    is: every value is the layout's own tightest feature, rounded to the safe side by at most 1 nm (widths by at
    most 1 um, the bisection resolution). Values the layout has no feature for (e.g. ``spacing_other`` when there
    are only the three power nets, or the gate length without gate copper) stay ``None`` / default in ``rules``
    and ``None`` in ``record``.

    * spacing of each power-net pair (min distance between the copper of the two nets), and one value, the
      smallest, over every other trace pair (including two separate pieces of the same net);
      ``min_spacing`` (the fall-back value) is set to ``spacing_other`` if there is one, else to the smallest
      power-pair gap.
    * minimum width of power copper and of other copper: bisection to 1 um on the DRC's own opening/neck test
      (``min_trace_width`` falls back like ``min_spacing``).
    * ``min_wire_pitch``: the smallest plan-view centre-line distance over all wire pairs (power and signal);
      ``wire_pitch_diameters``: the smallest ratio of that distance to the larger diameter of the pair. Both are
      checked (the DRC takes the larger requirement), so where the tightest pitch is between thin wires, thicker
      wires keep the layout's own pitch-to-diameter ratio instead of inheriting the thin wires' pitch.
    * ``die_spacing``, ``die_edge_margin`` and ``edge_margin`` (the last two by bisection to 1 nm on the DRC's
      own containment test).
    * ``max_gate_wire_length`` / ``max_kelvin_wire_length``: the longest signal wire of that kind, or the largest
      distance from such a die pad to the copper of its own switch's net when that is larger (a pad without a
      wire). With every pad bonded this is the longest wire, since a wire is at least as long as its pad's plan
      distance to the copper it lands on. The limit is left ``None`` (``record['signal_unmeasured']`` says why)
      when a die has the pad but the layout has no copper of its net: the layout could not meet any limit.
    """
    tr = layout.traces
    gaps: dict[str, float] = {}
    other_gap = None
    for i in range(len(tr)):
        for j in range(i + 1, len(tr)):
            d = tr[i].polygon.distance(tr[j].polygon)
            key = _POWER_PAIRS.get(frozenset((tr[i].net, tr[j].net)))
            if key is None:
                other_gap = d if other_gap is None else min(other_gap, d)
            else:
                gaps[key] = min(gaps.get(key, d), d)

    def class_width(select):
        polys = [t.polygon for t in tr if select(t.net)]
        if not polys:
            return None
        hi = min(min(p.bounds[2] - p.bounds[0], p.bounds[3] - p.bounds[1]) for p in polys) + 1e-6
        return _bisect_max(lambda w: all(_width_problem(p, w)[0] is None for p in polys), hi, 1e-6)

    w_power = class_width(lambda n: n in NETS)
    w_other = class_width(lambda n: n not in NETS)

    all_wires = list(layout.wires) + list(layout.signal_wires)
    lines = [LineString(w.points[:, :2]) for w in all_wires]
    pairs = [(lines[i].distance(lines[j]), max(all_wires[i].diameter, all_wires[j].diameter))
             for i in range(len(lines)) for j in range(i)]
    pitch = min((g for g, _ in pairs), default=None)
    pitch_ratio = min((g / dm for g, dm in pairs), default=None)

    dsp = min((layout.dies[i].box.distance(layout.dies[j].box)
               for i in range(len(layout.dies)) for j in range(i + 1, len(layout.dies))), default=None)

    die_margins = []
    for d in layout.dies:
        host = [t for t in tr if t.polygon.contains(Point(d.cx, d.cy))]
        if host:
            hi = host[0].polygon.boundary.distance(d.box)
            die_margins.append(_bisect_max(lambda m, h=host[0].polygon, b=d.box: _die_edge_ok(h, b, m), hi, 1e-9))
    edge_margins = [_bisect_max(lambda m, p=t.polygon: _edge_ok(layout, p, m),
                                layout.outline.boundary.distance(t.polygon), 1e-9) for t in tr]

    lengths: dict[str, float | None] = {}
    pad_dist: dict[str, float | None] = {}
    unmeasured: dict[str, str] = {}
    for pad in SIGNAL_PADS:
        ws = [w.length for w in layout.signal_wires if w.pad == pad]
        lengths[pad] = max(ws) if ws else None
        dists, missing = [], []
        for i, d in enumerate(layout.dies):
            net = SIGNAL_NET.get((pad, d.switch))
            if pad not in d.pads or net is None:
                continue
            cu = [t.polygon for t in tr if t.net == net]
            if cu:
                dists.append(box(*d.pads[pad]).distance(unary_union(cu)))
            else:
                missing.append(f"die {i} ({d.switch}) has a {pad} pad but there is no {net} copper")
        pad_dist[pad] = max(dists) if dists else None
        if missing:
            unmeasured[pad] = "; ".join(missing)

    def fl(v):
        return None if v is None else _floor_nm(v)

    def rule_len(pad):
        c = [x for x in (lengths[pad], pad_dist[pad]) if x is not None]
        return _ceil_nm(max(c)) if c and pad not in unmeasured else None

    sp = {k: fl(v) for k, v in gaps.items()}
    sp_other = fl(other_gap)
    base = DesignRules()
    min_sp = sp_other if sp_other is not None else (min(sp.values()) if sp else base.min_spacing)
    wp, wo = fl(w_power), fl(w_other)
    min_w = wo if wo is not None else (wp if wp is not None else base.min_trace_width)
    rules = DesignRules(
        min_trace_width=min_w,
        min_spacing=min_sp,
        edge_margin=_floor_nm(min(edge_margins)) if edge_margins else base.edge_margin,
        die_edge_margin=_floor_nm(min(die_margins)) if die_margins else base.die_edge_margin,
        die_spacing=fl(dsp) if dsp is not None else base.die_spacing,
        min_wire_pitch=fl(pitch) if pitch is not None else base.min_wire_pitch,
        wire_pitch_diameters=fl(pitch_ratio) if pitch_ratio is not None else base.wire_pitch_diameters,
        spacing_dcp_phase=sp.get("dcp_phase"),
        spacing_phase_dcm=sp.get("phase_dcm"),
        spacing_dcp_dcm=sp.get("dcp_dcm"),
        spacing_other=sp_other,
        min_width_power=wp,
        min_width_other=wo,
        max_gate_wire_length=rule_len("gate"),
        max_kelvin_wire_length=rule_len("kelvin"),
    )
    record = {
        "gap_dcp_phase": gaps.get("dcp_phase"),
        "gap_phase_dcm": gaps.get("phase_dcm"),
        "gap_dcp_dcm": gaps.get("dcp_dcm"),
        "gap_other_min": other_gap,
        "min_width_power": w_power,
        "min_width_other": w_other,
        "min_wire_pitch": pitch,
        "min_wire_pitch_diameters": pitch_ratio,
        "die_spacing": dsp,
        "die_edge_margin": min(die_margins) if die_margins else None,
        "edge_margin": min(edge_margins) if edge_margins else None,
        "longest_gate_wire": lengths["gate"],
        "longest_kelvin_wire": lengths["kelvin"],
        "max_gate_pad_to_copper": pad_dist["gate"],
        "max_kelvin_pad_to_copper": pad_dist["kelvin"],
        "signal_unmeasured": unmeasured,
        "n_traces": len(tr),
        "n_dies": len(layout.dies),
        "n_wires": len(layout.wires),
        "n_signal_wires": len(layout.signal_wires),
    }
    return rules, record
