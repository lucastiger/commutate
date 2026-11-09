"""Derivative re-layouts of a wire-bonded half-bridge inside a fixed reference housing (O003, T0258).

``ReferenceSpec`` holds everything a re-layout may NOT change: substrate and baseplate outline, stack, terminal pads,
the fixed keep-out copper (the reference's gate and Kelvin traces), the die (footprint, thickness, attach thickness,
source / gate / Kelvin pads), dies per switch, power wires per die with diameter and loop height, the signal-wire
diameter and loop height, and the ``DesignRules``.  ``spec_from_layout`` derives it from a reconstructed ``Layout``;
``halfbridge_housing_spec`` is the 70 x 40 mm generator housing.  ``generate(spec, n, seed)`` returns ``n`` layouts
that are DRC-clean under ``spec.rules`` (spacing per net pair, width classes, bondability, signal wires), deterministic in
``seed`` (one ``numpy`` Generator, no global state).  ``build(spec, params)`` is the deterministic parameters -> Layout
map and ``params_of(layout)`` its inverse on generated layouts; ``generate`` is a seeded rejection sampler over ``Params``.

Parameter space (all lateral values in mm on the DESIGN_GRID_MM = 0.5 mm grid, in a local frame u (along the die rows) / v
(across them); ``orient`` 0: u = x, v = y; 1: u = y, v = x)
----------------------------------------------------------------------------------------------------------------------
* four *slots* (copper bands across v) in a sequence fixed by three flags: the HS pair [DC+ die band, PHASE landing band] and
  the LS pair [PHASE die band, DC- landing band], each pair in either order, the pairs in either order -> 8 sequences; two
  adjacent PHASE slots either touch (one merged band: side-by-side) or are separate (joined by the PHASE column).
  Interleaved, U-shaped and side-by-side analogues, and the Case 4 sequence [PHASE, DC-, PHASE, DC+], are members.
* three *columns* (one per power net), each covering its terminal pad and every slot of the net (so the pad may sit at
  any position, even not at an end of the housing); the slots attach to the column's inner edge, on side lo or hi in u.
* two die *rows* (HS, LS): start u, v of the die edge, gap between dies; and the landing line v of the wires of each row.
Free ends of the slots, column extensions, die offsets, slot heights and gaps are drawn on the grid; copper widths and
gaps therefore vary freely.  Gate and Kelvin wires run straight from each die's pad to the nearest point of the fixed
copper of the die's own switch (``GATE_HS`` ...).  Not in the space: dies in more than one row per switch, die rotation,
copper islands that are not bands or columns (e.g. a PHASE ring around a die row, or copper beyond the 4 slots).

``params_of(layout)`` reads the vector from the layout's ``family`` string (``derivative:<topology>:<json vector>``), which
``build`` writes; ``build(spec, params_of(layout))`` reproduces the layout bit for bit (tested by fingerprint).

Assumptions: the fixed keep-out copper carries the nets GATE_HS / GATE_LS / KELVIN_HS / KELVIN_LS (``spec_from_layout`` can
rename a reference's own nets for that, e.g. Case 4's SIG_*); the maximum gate / Kelvin wire length is a rule of the spec
(for Case 4 an assumed 25 mm, see tests; the files give none).  Wire feet are at the source-pad centre moved 25 % of the pad
height towards the landing line, spread along u at <= 1 mm pitch.

Throughput, measured on 2D_Case_4 (2 dies per switch, 1 power wire per die, gate + Kelvin wire per die, max power wire 18 mm,
signal wires 25 mm; M-series Mac, one process, seed 1, 1000 candidates, three runs): 244-253 DRC-valid candidates / s, i.e.
20 000 candidates in about 80 s.  On Case 4 the fixed
gate / Kelvin copper and the 25 mm limit leave four of the eight pair sequences feasible (HS pair above the LS pair, either
order inside each pair; the merged-PHASE variants need a longer HS wire than 18 mm); the 70 x 40 housing yields five
sequence / merge variants (HS pair first only: the DC+ column would cross the DC- pad otherwise).  ``test_throughput_case4``
(slow) asserts >= 5 / s.
"""
from __future__ import annotations

import json
import math
from collections.abc import Mapping
from dataclasses import dataclass

import numpy as np
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import nearest_points, unary_union

from moduleforge.drc import check
from moduleforge.drc.rules import DesignRules
from moduleforge.geometry import (
    DC_MINUS,
    DC_PLUS,
    NETS,
    PHASE,
    SIGNAL_NET,
    SIGNAL_NETS,
    Die,
    Layout,
    SignalWire,
    Terminal,
    Trace,
    arc_wire,
    mm_to_m,
)
from moduleforge.geometry.stack import LayerStack

DESIGN_GRID_MM = 0.5
WIRE_PITCH_MM = 1.0  # nominal spacing of the power wires along u (reduced to fit the source pad)
SIGNAL_NETS_SET = frozenset(SIGNAL_NETS)
_MIT = {"join_style": "mitre", "mitre_limit": 10.0}


def _g_up(v: float) -> float:
    return math.ceil(v / DESIGN_GRID_MM - 1e-9) * DESIGN_GRID_MM


def _g_dn(v: float) -> float:
    return math.floor(v / DESIGN_GRID_MM + 1e-9) * DESIGN_GRID_MM


def _snap(v: float) -> float:
    return round(float(v) / DESIGN_GRID_MM) * DESIGN_GRID_MM


def _on_grid(v_m: float) -> bool:
    u = v_m * 1e3 / DESIGN_GRID_MM
    return abs(u - round(u)) < 1e-6


# --------------------------------------------------------------------------------------------------------------- spec
@dataclass(frozen=True, eq=False)
class DieSpec:
    """The (fixed) die: footprint w x h, thicknesses and pad rectangles (x0, y0, x1, y1) relative to the die centre."""

    w: float
    h: float
    thickness: float
    attach_thickness: float
    pads: dict[str, tuple[float, float, float, float]]


@dataclass(frozen=True, eq=False)
class ReferenceSpec:
    outline: Polygon
    baseplate_outline: Polygon
    stack: LayerStack
    terminals: dict[str, Terminal]
    keepouts: tuple[Trace, ...]  # fixed gate / Kelvin copper, copied unchanged into every layout
    die: DieSpec
    dies_per_switch: int
    wires_per_die: int
    wire_diameter: float
    loop_height: float
    rules: DesignRules
    signal_wire_diameter: float = 0.1e-3
    signal_loop_height: float = 0.5e-3
    backside_inset: float = 1.0e-3
    wire_sigma: float | None = None  # None: Layout default
    name: str = "reference"

    def __post_init__(self):
        if set(self.terminals) != set(NETS):
            raise ValueError("terminals must be exactly DC+, DC-, PHASE")
        if not (_on_grid(self.die.w) and _on_grid(self.die.h)):
            raise ValueError("die footprint must lie on the 0.5 mm design grid")
        if "source" not in self.die.pads:
            raise ValueError("die needs a source pad")
        for o in (0, 1):  # the k power wires must fit on the source pad along u, in either orientation
            _wire_pitch(self, o)


def _frame_size(o: int, w: float, h: float):
    return (w, h) if o == 0 else (h, w)


def _wire_pitch(spec: ReferenceSpec, orient: int) -> float:
    k = spec.wires_per_die
    if k == 1:
        return 0.0
    x0, y0, x1, y1 = spec.die.pads["source"]
    wu = _frame_size(orient, x1 - x0, y1 - y0)[0]
    margin = max(spec.rules.wire_start_margin, spec.wire_diameter / 2) + 5e-5
    pitch = min(mm_to_m(WIRE_PITCH_MM), (wu - 2 * margin) / (k - 1))
    need = max(spec.rules.min_wire_pitch, spec.rules.wire_pitch_diameters * spec.wire_diameter)
    if pitch < need - 1e-9:
        raise ValueError(f"{k} wires do not fit on the source pad at pitch >= {need:.3e} m (orient {orient})")
    return pitch


def spec_from_layout(layout: Layout, rules: DesignRules, keepout_nets: Mapping[str, str] | list | tuple | set,
                     *, extra_pads: Mapping[str, tuple] | None = None, signal_wire_diameter: float = 0.1e-3,
                     signal_loop_height: float = 0.5e-3, name: str | None = None) -> ReferenceSpec:
    """ReferenceSpec of a reconstructed ``layout``.

    ``keepout_nets``: nets of ``layout`` whose copper is the fixed gate / Kelvin copper (copied unchanged); a mapping
    ``{layout net: canonical net}`` also renames them to GATE_HS / GATE_LS / KELVIN_HS / KELVIN_LS (needed for the DRC's
    bondability rules and for signal wires); a plain collection keeps the names.  The power copper of ``layout`` is
    dropped (that is what is re-laid out).  ``extra_pads`` ({'gate'|'kelvin': (x0, y0, x1, y1)} relative to the die
    centre) adds die pads the layout does not have (assumed pad positions).  All dies must be identical.
    """
    ren = dict(keepout_nets) if isinstance(keepout_nets, Mapping) else {n: n for n in keepout_nets}
    if not layout.dies:
        raise ValueError("layout has no dies")
    d0 = layout.dies[0]
    rel = {k: (r[0] - d0.cx, r[1] - d0.cy, r[2] - d0.cx, r[3] - d0.cy) for k, r in d0.pads.items()}
    for d in layout.dies:
        same = (d.w, d.h, d.thickness, d.attach_thickness) == (d0.w, d0.h, d0.thickness, d0.attach_thickness)
        r2 = {k: (r[0] - d.cx, r[1] - d.cy, r[2] - d.cx, r[3] - d.cy) for k, r in d.pads.items()}
        if not same or set(r2) != set(rel) or any(np.abs(np.subtract(r2[k], rel[k])).max() > 1e-12 for k in rel):
            raise ValueError("dies of the layout are not identical")
    rel.update({k: tuple(v) for k, v in (extra_pads or {}).items()})
    if len(layout.wires) % len(layout.dies):
        raise ValueError("power wires are not evenly distributed over the dies")
    w0 = layout.wires[0]
    ko = []
    for t in layout.traces:
        if t.net in ren:
            ko.append(Trace(ren[t.net], t.polygon))
    missing = set(ren) - {t.net for t in layout.traces}
    if missing:
        raise ValueError(f"keepout nets not in the layout: {sorted(missing)}")
    sw = layout.signal_wires[0] if layout.signal_wires else None
    return ReferenceSpec(
        outline=layout.outline, baseplate_outline=layout.baseplate_outline, stack=layout.stack,
        terminals={k: Terminal(t.net, t.cx, t.cy, t.w, t.h) for k, t in layout.terminals.items()},
        keepouts=tuple(ko), die=DieSpec(d0.w, d0.h, d0.thickness, d0.attach_thickness, rel),
        dies_per_switch=layout.dies_per_switch, wires_per_die=len(layout.wires) // len(layout.dies),
        wire_diameter=w0.diameter, loop_height=w0.loop_height, rules=rules,
        signal_wire_diameter=sw.diameter if sw else signal_wire_diameter,
        signal_loop_height=sw.loop_height if sw else signal_loop_height,
        backside_inset=layout.backside_inset, wire_sigma=layout.wire_sigma, name=name or layout.family)


def halfbridge_housing_spec(dies_per_switch: int = 3, rules: DesignRules | None = None, wires_per_die: int = 3,
                            wire_diameter: float = 0.3e-3, loop_height: float = 1.0e-3) -> ReferenceSpec:
    """ReferenceSpec of the generator's 70 x 40 mm housing (``generate.halfbridge``): terminal pads, stack, 5 x 5 mm die
    with a 3.5 x 3.5 mm source pad and a gate pad, no fixed gate / Kelvin copper."""
    from moduleforge.generate import halfbridge as hb
    from moduleforge.geometry import default_dbc_stack
    s = 5.0
    hp = 0.35 * s
    pads = {"source": tuple(mm_to_m(v) for v in (-hp, -hp, hp, hp)),
            "gate": tuple(mm_to_m(v) for v in (0.36 * s, -0.47 * s, 0.47 * s, -0.36 * s))}
    terms = {n: Terminal(n, mm_to_m((p[0] + p[2]) / 2), mm_to_m((p[1] + p[3]) / 2), mm_to_m(p[2] - p[0]),
                         mm_to_m(p[3] - p[1])) for n, p in hb.PADS.items()}
    return ReferenceSpec(
        outline=box(0.0, 0.0, mm_to_m(hb.W_MM), mm_to_m(hb.H_MM)),
        baseplate_outline=box(mm_to_m(-8.0), mm_to_m(-8.0), mm_to_m(hb.W_MM + 8.0), mm_to_m(hb.H_MM + 8.0)),
        stack=default_dbc_stack(), terminals=terms, keepouts=(), die=DieSpec(mm_to_m(s), mm_to_m(s), *_die_t(), pads),
        dies_per_switch=dies_per_switch, wires_per_die=wires_per_die, wire_diameter=wire_diameter,
        loop_height=loop_height, rules=rules or DesignRules(), name="halfbridge_70x40")


def _die_t():
    return Die(0, 0, 1, 1, "HS", {}).thickness, Die(0, 0, 1, 1, "HS", {}).attach_thickness


# ------------------------------------------------------------------------------------------------------------ params
SLOT_ROLES = ("die", "land")
_NCOL, _NSLOT = 3, 4


@dataclass(frozen=True)
class Params:
    """Parameter vector of a layout (mm, local frame; see the module docstring)."""

    orient: int
    hs_first: int
    hs_die_first: int
    ls_die_first: int
    cols: tuple  # per power net in NETS order: (u0, v0, u1, v1)
    slots: tuple  # per slot in sequence order: (u0, v0, u1, v1)
    rows: tuple  # ((u0, v0, gap) HS, (u0, v0, gap) LS): start u of the first die, v of the die edge, gap between dies
    land: tuple  # (v of the HS wires' landing line, v of the LS wires' landing line)

    NAMES = (("orient", "hs_first", "hs_die_first", "ls_die_first")
             + tuple(f"col_{n}_{c}" for n in NETS for c in ("u0", "v0", "u1", "v1"))
             + tuple(f"slot{i}_{c}" for i in range(_NSLOT) for c in ("u0", "v0", "u1", "v1"))
             + tuple(f"row_{s}_{c}" for s in ("HS", "LS") for c in ("u0", "v0", "gap")) + ("land_HS", "land_LS"))

    def to_vector(self) -> np.ndarray:
        v = [self.orient, self.hs_first, self.hs_die_first, self.ls_die_first]
        v += [x for c in self.cols for x in c] + [x for s in self.slots for x in s]
        v += [x for r in self.rows for x in r] + list(self.land)
        return np.array(v, dtype=float)

    @classmethod
    def from_vector(cls, vec) -> Params:
        v = [float(x) for x in vec]
        if len(v) != len(cls.NAMES):
            raise ValueError(f"parameter vector must have {len(cls.NAMES)} entries")
        i = 4
        cols = tuple(tuple(v[i + 4 * k:i + 4 * k + 4]) for k in range(_NCOL))
        i += 4 * _NCOL
        slots = tuple(tuple(v[i + 4 * k:i + 4 * k + 4]) for k in range(_NSLOT))
        i += 4 * _NSLOT
        rows = (tuple(v[i:i + 3]), tuple(v[i + 3:i + 6]))
        return cls(int(v[0]), int(v[1]), int(v[2]), int(v[3]), cols, slots, rows, (v[i + 6], v[i + 7]))

    def sequence(self) -> list[tuple[str, str, str]]:
        return _sequence(self.hs_first, self.hs_die_first, self.ls_die_first)

    def topology(self) -> str:
        seq = self.sequence()
        merged = any(seq[i][0] == seq[i + 1][0] == PHASE and abs(self.slots[i + 1][1] - self.slots[i][3]) < 1e-9
                     for i in range(3))
        name = "-".join(f"{n}{'d' if r == 'die' else 'l'}" for n, r, _ in seq)
        return f"{'xy'[self.orient]}/{name}/{'merged' if merged else 'split'}"


def _sequence(hs_first, hs_die_first, ls_die_first):
    hs = [(DC_PLUS, "die", "HS"), (PHASE, "land", "HS")]
    ls = [(PHASE, "die", "LS"), (DC_MINUS, "land", "LS")]
    if not hs_die_first:
        hs = hs[::-1]
    if not ls_die_first:
        ls = ls[::-1]
    return hs + ls if hs_first else ls + hs


_PREFIX = "derivative:"


def _encode(p: Params) -> str:
    return f"{_PREFIX}{p.topology()}:{json.dumps(p.to_vector().tolist())}"


def params_of(layout: Layout) -> Params:
    """Parameter vector of a layout made by ``build`` / ``generate`` (read from its ``family`` string)."""
    if not layout.family.startswith(_PREFIX):
        raise ValueError("layout was not built by moduleforge.generate.derivative")
    return Params.from_vector(json.loads(layout.family.split(":", 2)[2]))


def topology_of(layout: Layout) -> str:
    return params_of(layout).topology()


class _Frame:
    """Local (u, v) <-> (x, y): orient 0 identity, orient 1 swaps the axes (an involution)."""

    def __init__(self, orient: int):
        self.o = orient

    def rect(self, u0, v0, u1, v1):
        return (u0, v0, u1, v1) if self.o == 0 else (v0, u0, v1, u1)

    lrect = rect

    def pt(self, u, v):
        return (u, v) if self.o == 0 else (v, u)

    def size(self, w, h):
        return _frame_size(self.o, w, h)


def _mm_rect(r):
    return tuple(mm_to_m(v) for v in r)


# ------------------------------------------------------------------------------------------------------------ builder
def build(spec: ReferenceSpec, p: Params) -> Layout:
    """Deterministic Layout of ``p`` inside ``spec`` (ValueError if the copper of a net is not one polygon, a signal wire
    cannot land, ...).  DRC cleanliness is not guaranteed for arbitrary ``p``; ``generate`` only returns clean ones."""
    fr = _Frame(p.orient)
    seq = p.sequence()
    rects: dict[str, list] = {n: [] for n in NETS}
    for (net, _, _), s in zip(seq, p.slots, strict=True):
        rects[net].append(box(*_mm_rect(fr.rect(*s))))
    for net, c in zip(NETS, p.cols, strict=True):
        rects[net].append(box(*_mm_rect(fr.rect(*c))))
    traces = []
    for net in NETS:
        poly = unary_union(rects[net])
        if not isinstance(poly, Polygon):
            raise ValueError(f"{net} copper is not a single polygon")
        traces.append(Trace(net, poly))
    traces += [Trace(t.net, t.polygon) for t in spec.keepouts]

    st = spec.stack
    z_top_cu = st.z_top("top_cu")
    dsp = spec.die
    dw, dh = dsp.w, dsp.h
    du, dv = (x * 1e3 for x in fr.size(dw, dh))
    k = spec.wires_per_die
    pitch = _wire_pitch(spec, p.orient) * 1e3
    dies, wires = [], []
    land = {"HS": p.land[0], "LS": p.land[1]}
    for sw, (u0, v0, gap), net in (("HS", p.rows[0], PHASE), ("LS", p.rows[1], DC_MINUS)):
        for i in range(spec.dies_per_switch):
            cx, cy = (mm_to_m(c) for c in fr.pt(u0 + i * (du + gap) + du / 2, v0 + dv / 2))
            pads = {n: (cx + r[0], cy + r[1], cx + r[2], cy + r[3]) for n, r in dsp.pads.items()}
            die = Die(cx, cy, dw, dh, sw, pads, dsp.thickness, dsp.attach_thickness)
            dies.append(die)
            pu0, pv0, pu1, pv1 = (c * 1e3 for c in fr.lrect(*pads["source"]))
            cv = (pv0 + pv1) / 2
            sgn = 1.0 if land[sw] > cv else -1.0
            z_start = z_top_cu + die.attach_thickness + die.thickness
            for j in range(k):
                u = (pu0 + pu1) / 2 + (j - (k - 1) / 2) * pitch
                s_xy = tuple(mm_to_m(c) for c in fr.pt(u, cv + sgn * 0.25 * (pv1 - pv0)))
                e_xy = tuple(mm_to_m(c) for c in fr.pt(u, land[sw]))
                wires.append(arc_wire(s_xy, e_xy, z_start, z_top_cu, spec.loop_height, spec.wire_diameter, net))
    sig = _signal_wires(spec, traces, dies, z_top_cu)
    kw = {} if spec.wire_sigma is None else {"wire_sigma": spec.wire_sigma}
    return Layout(family=_encode(p), dies_per_switch=spec.dies_per_switch, outline=spec.outline, traces=traces,
                  dies=dies, wires=wires, terminals=dict(spec.terminals), baseplate_outline=spec.baseplate_outline,
                  stack=st, backside_inset=spec.backside_inset, signal_wires=sig, **kw)


def _signal_wires(spec, traces, dies, z_top_cu):
    """Straight gate / Kelvin wires from every die pad to the nearest landable point of its switch's fixed copper."""
    margin = spec.rules.wire_landing_margin + 1e-7
    copper = {}
    for net in SIGNAL_NETS:
        polys = [t.polygon for t in traces if t.net == net]
        if polys:
            er = unary_union(polys).buffer(-margin, **_MIT)
            if er.is_empty:
                raise ValueError(f"{net} copper too narrow to land a wire")
            copper[net] = er
    out = []
    for i, d in enumerate(dies):
        for pad in ("gate", "kelvin"):
            net = SIGNAL_NET[(pad, d.switch)]
            if pad not in d.pads or net not in copper:
                continue
            x0, y0, x1, y1 = d.pads[pad]
            s = ((x0 + x1) / 2, (y0 + y1) / 2)
            q = nearest_points(copper[net], Point(s))[0]
            w = arc_wire(s, (q.x, q.y), z_top_cu + d.attach_thickness + d.thickness, z_top_cu,
                         spec.signal_loop_height, spec.signal_wire_diameter, net)
            out.append(SignalWire(i, pad, net, w.points, w.diameter, w.loop_height))
    return out


# ----------------------------------------------------------------------------------------------------------- sampler
class _Ctx:
    """Per-spec data of the sampler (mm)."""

    def __init__(self, spec: ReferenceSpec):
        r = spec.rules
        self.allowed = spec.outline.buffer(-(r.edge_margin - 1e-9), **_MIT)
        self.sp = {(a, b): _g_up(r.spacing_for(a, b) * 1e3) for a in NETS + tuple(SIGNAL_NETS) for b in NETS}
        self.dem = _g_up(r.die_edge_margin * 1e3)
        self.wmin = {n: _g_up(r.width_for(n) * 1e3) for n in NETS}
        ko = [(t.net, t.polygon) for t in spec.keepouts]
        self.free = {}
        for n in NETS:
            cut = [poly.buffer(r.spacing_for(n, kn) - 1e-9, **_MIT) for kn, poly in ko]
            self.free[n] = self.allowed.difference(unary_union(cut)) if cut else self.allowed
        self.pads = {n: (t.cx - t.w / 2, t.cy - t.h / 2, t.cx + t.w / 2, t.cy + t.h / 2)
                     for n, t in spec.terminals.items()}
        # bounds (mm, local frame of each orientation) of the fixed signal copper per net, and the shortest signal limit
        self.sig = {o: {} for o in (0, 1)}
        for kn, poly in ko:
            if kn in SIGNAL_NETS_SET:
                b = [c * 1e3 for c in poly.bounds]
                for o in (0, 1):
                    prev = self.sig[o].get(kn)
                    bb = _Frame(o).rect(*b)
                    self.sig[o][kn] = bb if prev is None else (min(prev[0], bb[0]), min(prev[1], bb[1]),
                                                               max(prev[2], bb[2]), max(prev[3], bb[3]))
        # per orientation: maximal v-intervals (mm, grid) whose strip is >= 40 % free of the keepouts' exclusion zones
        self.vwin = {}
        for o in (0, 1):
            fr = _Frame(o)
            ulo, vlo, uhi, vhi = fr.rect(*(c * 1e3 for c in self.allowed.bounds))
            vs = np.arange(_g_up(vlo), _g_dn(vhi) - 1e-9, DESIGN_GRID_MM)
            ok = []
            for v in vs:
                strip = box(*(c * 1e-3 for c in fr.rect(ulo, v, uhi, v + DESIGN_GRID_MM)))
                ok.append(self.free[PHASE].intersection(strip).area / strip.area >= 0.4)
            wins, i = [], 0
            while i < len(vs):
                if ok[i]:
                    j = i
                    while j + 1 < len(vs) and ok[j + 1]:
                        j += 1
                    wins.append((float(vs[i]), float(vs[j]) + DESIGN_GRID_MM))
                    i = j + 1
                else:
                    i += 1
            self.vwin[o] = wins
        lims = [x for x in (r.max_gate_wire_length, r.max_kelvin_wire_length) if x is not None]
        self.siglim = min(lims) * 1e3 if lims else None


def _pick_end(needed: float, limit: float, free_side: int, rng, extra_max: float):
    """Free end of a band: ``needed`` or further by a random grid amount, clipped at ``limit``; None if infeasible."""
    if (limit - needed) * free_side < -1e-9:
        return None
    end = needed + free_side * _snap(rng.uniform(0.0, extra_max))
    return end if (limit - end) * free_side >= -1e-9 else limit


def _sample(spec: ReferenceSpec, cx: _Ctx, rng: np.random.Generator) -> Params | None:
    orient = int(rng.integers(2))
    hs_first, hs_die_first, ls_die_first = (int(rng.integers(2)) for _ in range(3))
    fr = _Frame(orient)
    sig = cx.sig[orient]
    tgt = {}  # v of the fixed signal copper of each switch (None: unconstrained)
    for sw in ("HS", "LS"):
        vs = [(b[1] + b[3]) / 2 for n, b in sig.items() if n.endswith("_" + sw)]
        tgt[sw] = sum(vs) / len(vs) if vs else None
    if tgt["HS"] is not None and tgt["LS"] is not None and tgt["HS"] != tgt["LS"] and rng.random() < 0.6:
        hs_first = int(tgt["HS"] < tgt["LS"])  # the switch whose signal copper is at lower v goes first
    mid_v = None
    for sw, name in (("HS", "hs_die_first"), ("LS", "ls_die_first")):
        if tgt[sw] is not None and rng.random() < 0.5:
            # wires leave the die away from its signal copper: signal copper above -> landing slot below the die
            if mid_v is None:
                mid_v = sum(c * 1e3 for c in (cx.allowed.bounds[1 if orient == 0 else 0],
                                              cx.allowed.bounds[3 if orient == 0 else 2])) / 2
            above = tgt[sw] > mid_v
            if name == "hs_die_first":
                hs_die_first = int(not above)
            else:
                ls_die_first = int(not above)
    seq = _sequence(hs_first, hs_die_first, ls_die_first)
    du, dv = (x * 1e3 for x in fr.size(spec.die.w, spec.die.h))
    dem, k = cx.dem, spec.wires_per_die
    ulo, vlo, uhi, vhi = fr.lrect(*(_g_up(b) if i < 2 else _g_dn(b) for i, b in
                                    enumerate(c * 1e3 for c in cx.allowed.bounds)))
    # --- slot heights and v positions
    h_min = [dv + 2 * dem if role == "die" else max(cx.wmin[net], 2.0) for net, role, _ in seq]
    h_ext = [rng.uniform(0.0, 5.0 if role == "die" else 6.0) for _, role, _ in seq]
    merge = [seq[i][0] == seq[i + 1][0] and rng.random() < 0.5 for i in range(3)]
    g_min = [0.0 if merge[i] else cx.sp[(seq[i][0], seq[i + 1][0])] for i in range(3)]
    g_ext = [0.0 if merge[i] else rng.uniform(0.0, 12.0 if rng.random() < 0.6 else 2.5) for i in range(3)]
    reach = None if cx.siglim is None else cx.siglim - dv / 2  # sampling prior; the DRC enforces the real limits
    # window of each die slot's centre (absolute v) from the signal copper of its switch
    dwin = {}
    if reach is not None:
        for i, (_, role, sw) in enumerate(seq):
            bs = [bb for kn, bb in sig.items() if role == "die" and kn.endswith("_" + sw)]
            if bs:
                dwin[i] = (max(bb[1] for bb in bs) - reach, min(bb[3] for bb in bs) + reach)
    for alpha in (1.0, 0.5, 0.0):  # shrink the random extras until the stack fits where the signal copper is
        hts = [m + _snap(alpha * e) for m, e in zip(h_min, h_ext, strict=True)]
        gaps = [m + _snap(alpha * e) for m, e in zip(g_min, g_ext, strict=True)]
        ids = sorted(dwin)
        if len(ids) == 2:  # stretch / squeeze the gaps between the two die slots so that both windows can be met
            i, j = ids
            off = np.concatenate([[0.0], np.cumsum(np.array(hts[:3]) + np.array(gaps))])
            span = (off[j] + hts[j] / 2) - (off[i] + hts[i] / 2)
            smin, smax = dwin[j][0] - dwin[i][1], dwin[j][1] - dwin[i][0]
            free_g = [k for k in range(i, j) if not merge[k]]
            if span < smin and free_g:
                add = _g_up((smin - span) / len(free_g))
                for k in free_g:
                    gaps[k] += add
            elif span > smax:
                cut = span - smax
                for k in free_g:
                    take = _g_up(min(cut, gaps[k] - g_min[k]))
                    gaps[k] -= take
                    cut -= take
        total = sum(hts) + sum(gaps)
        fits = [w for w in cx.vwin[orient] if w[1] - w[0] >= total]
        if not fits:
            continue
        wlo, whi = fits[int(rng.integers(len(fits)))]
        lo_v, hi_v = wlo, whi - total
        off = 0.0
        for i in range(4):
            if i in dwin:
                c = off + hts[i] / 2
                lo_v, hi_v = max(lo_v, dwin[i][0] - c), min(hi_v, dwin[i][1] - c)
            off += hts[i] + (gaps[i] if i < 3 else 0.0)
        if hi_v >= lo_v:
            break
    else:
        return None
    v0 = max(_snap(rng.uniform(lo_v, hi_v)), _g_up(lo_v))
    sv = []
    for i in range(4):
        sv.append((v0, v0 + hts[i]))
        v0 += hts[i] + (gaps[i] if i < 3 else 0.0)
    # --- columns
    side, cols = {}, {}
    for net in NETS:
        pu0, pv0, pu1, pv1 = (c * 1e3 for c in fr.lrect(*cx.pads[net]))
        near = -1 if (pu0 + pu1) / 2 < (ulo + uhi) / 2 else 1
        side[net] = near if rng.random() < 0.85 else -near
        c0 = _g_dn(pu0) - _snap(rng.uniform(0.0, 1.5))
        c1 = _g_up(pu1) + _snap(rng.uniform(0.0, 1.5))
        if rng.random() < 0.5:  # widen towards the inside of the housing
            w = _snap(rng.uniform(0.0, 6.0))
            c0, c1 = (c0, c1 + w) if side[net] < 0 else (c0 - w, c1)
        mine = [sv[i] for i, s in enumerate(seq) if s[0] == net]
        a = min([pv0] + [x[0] for x in mine])
        b = max([pv1] + [x[1] for x in mine])
        if rng.random() < 0.3:
            a, b = a - _snap(rng.uniform(0.0, 3.0)), b + _snap(rng.uniform(0.0, 3.0))
        cols[net] = (c0, _g_dn(a), c1, _g_up(b))
    edge = {n: cols[n][2] if side[n] < 0 else cols[n][0] for n in NETS}  # attached (inner) edge of the net's bands

    def limit(net, va, vb):
        free_side = -side[net]
        lim = uhi if free_side > 0 else ulo
        for m in NETS:
            if m == net or side[m] != free_side:
                continue
            sp = cx.sp[(net, m)]
            if cols[m][1] - sp < vb and cols[m][3] + sp > va:
                lim = min(lim, cols[m][0] - sp) if free_side > 0 else max(lim, cols[m][2] + sp)
        return lim

    # --- die rows, landing lines, slot u extents
    ends = [None] * 4
    rows, land = {}, {}
    die_idx = {sw: next(i for i, s in enumerate(seq) if s[1] == "die" and s[2] == sw) for sw in ("HS", "LS")}
    land_idx = {sw: next(i for i, s in enumerate(seq) if s[1] == "land" and s[2] == sw) for sw in ("HS", "LS")}
    wu = {}
    for sw in ("HS", "LS"):
        i = die_idx[sw]
        net = seq[i][0]
        gap = max(_g_up(spec.rules.die_spacing * 1e3), dem) + _snap(rng.uniform(0.0, 2.0))
        ld = spec.dies_per_switch * du + (spec.dies_per_switch - 1) * gap
        x0 = dem + _snap(rng.uniform(0.0, 6.0))
        ae = edge[net]
        u0 = ae + x0 if side[net] < 0 else ae - x0 - ld
        needed = (u0 + ld + dem) if side[net] < 0 else (u0 - dem)
        end = _pick_end(needed, limit(net, *sv[i]), -side[net], rng, 8.0)
        if end is None:
            return None
        ends[i] = end
        dvs = sv[i][0] + dem + _snap(rng.uniform(0.0, hts[i] - dv - 2 * dem + 1e-9))
        rows[sw] = (u0, dvs, gap)
        # wire u extent (pad centre along u +- spread): conservative bound = die extent
        wu[sw] = (u0, u0 + ld)
    for sw in ("HS", "LS"):
        j = land_idx[sw]
        net = seq[j][0]
        lo, hi = wu[sw]
        needed = (hi + 0.5) if side[net] < 0 else (lo - 0.5)
        needed = _g_up(needed) if side[net] < 0 else _g_dn(needed)
        end = _pick_end(needed, limit(net, *sv[j]), -side[net], rng, 6.0)
        if end is None or (end - edge[net]) * (-side[net]) < 1.0:
            return None
        ends[j] = end
        # wire length within the rules (with slack for the arc) along v from the wire foot (source pad centre moved
        # 25 % of its height towards the landing line)
        sgn = 1.0 if j > die_idx[sw] else -1.0
        sx0, sy0, sx1, sy1 = fr.lrect(*spec.die.pads["source"])
        foot = rows[sw][1] + dv / 2 + 1e3 * ((sy0 + sy1) / 2 + sgn * 0.25 * (sy1 - sy0))
        wmin_, wmax_ = spec.rules.min_wire_length * 1e3 + 0.5, spec.rules.max_wire_length * 1e3 - 1.0
        lo_l, hi_l = (foot + wmin_, foot + wmax_) if sgn > 0 else (foot - wmax_, foot - wmin_)
        lo_l, hi_l = _g_up(max(lo_l, sv[j][0] + 0.5)), _g_dn(min(hi_l, sv[j][1] - 0.5))
        if hi_l < lo_l:
            return None
        land[sw] = lo_l + _snap(rng.uniform(0.0, hi_l - lo_l))
    slots = tuple((edge[seq[i][0]], sv[i][0], ends[i], sv[i][1]) if side[seq[i][0]] < 0
                  else (ends[i], sv[i][0], edge[seq[i][0]], sv[i][1]) for i in range(4))
    return Params(orient, hs_first, hs_die_first, ls_die_first, tuple(cols[n] for n in NETS), slots,
                  (rows["HS"], rows["LS"]), (land["HS"], land["LS"]))


def _quick_ok(spec: ReferenceSpec, cx: _Ctx, lay: Layout) -> bool:
    """Cheap necessary conditions (a subset of the DRC, tested before the expensive width checks): copper inside its
    free region, spacing between the power nets, signal-wire length limits, no plan-view crossing of signal and power wires."""
    tr = lay.traces
    for t in tr[:3]:
        if not cx.free[t.net].buffer(1e-9).contains(t.polygon):
            return False
    for i in range(3):
        for j in range(i + 1, 3):
            if tr[i].polygon.distance(tr[j].polygon) < spec.rules.spacing_for(tr[i].net, tr[j].net) - 1e-9:
                return False
    for w in lay.signal_wires:
        lim = spec.rules.max_gate_wire_length if w.pad == "gate" else spec.rules.max_kelvin_wire_length
        if lim is not None and w.length > lim:
            return False
    if lay.signal_wires:
        power = [LineString(w.points[:, :2]) for w in lay.wires]
        for sw in lay.signal_wires:
            ln = LineString(sw.points[:, :2])
            if any(ln.distance(q) < spec.rules.min_wire_pitch for q in power):
                return False
    return True


def generate(spec: ReferenceSpec, n: int, seed: int, max_failures: int = 20000) -> list[Layout]:
    """``n`` DRC-clean (under ``spec.rules``) layouts inside ``spec``, deterministic in ``seed``.

    Seeded rejection sampling over ``Params``; RuntimeError after ``max_failures`` consecutive rejected candidates."""
    rng = np.random.default_rng(seed)
    cx = _Ctx(spec)
    out: list[Layout] = []
    fails = 0
    while len(out) < n:
        lay = None
        p = _sample(spec, cx, rng)
        if p is not None:
            try:
                lay = build(spec, p)
            except ValueError:
                lay = None
        if lay is not None and _quick_ok(spec, cx, lay) and not check(lay, spec.rules):
            out.append(lay)
            fails = 0
        else:
            fails += 1
            if fails > max_failures:
                raise RuntimeError(f"no DRC-valid candidate in {max_failures} consecutive draws for {spec.name}")
    return out

