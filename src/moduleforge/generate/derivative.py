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
* the *wire feet* of each row (T0273): ``feet`` = (fu0, fud, pitch, fv, land_du, land_dv) in mm.  Wire j of die i starts at
  u = (source-pad centre of die i) + fu0 + i * fud + (j - (k-1)/2) * pitch, v = pad centre + fv, and lands at (start u +
  land_du, landing line + land_dv).  ``sigfeet`` = (gate du, gate dv, Kelvin du, Kelvin dv): the gate / Kelvin feet relative to
  their pad centres (the wires still run straight to the nearest landable fixed copper).  The sampler draws absolute foot and
  landing positions on a 0.125 mm grid (the reference's own bond points are on it), inside the pad by the start margin; with
  probability 0.6 it places the power wires clear of the gate / Kelvin wires.  The space contains the Case 4 reference's own
  wires (test: start and end within 1e-6 m).
Free ends of the slots, column extensions, die offsets, slot heights and gaps are drawn on the grid; copper widths and
gaps therefore vary freely.  Gate and Kelvin wires run straight from each die's pad to the nearest point of the fixed
copper of the die's own switch (``GATE_HS`` ...).  Not in the space: dies in more than one row per switch, die rotation,
copper islands that are not bands or columns (e.g. a PHASE ring around a die row, or copper beyond the 4 slots).

``params_of(layout)`` reads the vector from the layout's ``family`` string (``derivative:<topology>:<json vector>``), which
``build`` writes; ``build(spec, params_of(layout))`` reproduces the layout bit for bit (tested by fingerprint).

Assumptions: the fixed keep-out copper carries the nets GATE_HS / GATE_LS / KELVIN_HS / KELVIN_LS (``spec_from_layout`` can
rename a reference's own nets for that, e.g. Case 4's SIG_*); the maximum gate / Kelvin wire length is a rule of the spec
(for Case 4 an assumed 25 mm, see tests; the files give none).

Limits shown on 2D_Case_4 (tests; its gate / Kelvin pads are assumed, the 25 mm limit is assumed):
* 2 and 3 power wires per die, default rules: DRC-valid candidates (the LS gate / Kelvin wires cross the source pad at x = 29 /
  31 mm; the feet are placed between / beside them at >= 0.625 mm).
* A 2 mm minimum wire pitch: for the LS dies over the signal strips' x range the closed form is a power foot at most
  (Kelvin_max - gate_min) / 2 = 1.35 mm from the nearer signal wire (the signal feet move only inside their 1 x 1 mm pads
  and the wires run straight to the copper); 3 wires need 4 mm of a 3.2 mm pad (ValueError at the spec).  SCOPE (T0281
  finding 2): that is proven only for orientation-x LS dies with centres x in about [25, 66] mm.  A numeric extension (feet on a
  0.25 mm grid, diagonal wires, 25 mm limit, y in [30, 80] mm; ``test_case4_2mm_pitch_bound_scope_ls_dies``) gives a
  foot-distance bound of at most 1.96 mm < 2 mm there (T0290: the earlier 1.81 mm was a coarse-grid artefact; the bound is now an
  endpoint-inclusive grid with a Lipschitz margin, the fine-grid supremum at the worst die centre (25, 30) mm is 1.820 mm).  Outside that range the wires are diagonal and the bound exceeds 2 mm
  (4.8 mm at x = 15, y = 30 mm), so for those placements, HS dies and orientation y the infeasibility rests on sampling only
  (RuntimeError after 3000 consecutive rejected draws in the test; 20000 in T0281's check).  Landing points of the gate /
  Kelvin wires are not parameters, so the generator cannot steer them away.  No rule is relaxed.
* Diversity under ``measure_rules(reference)`` (edge margin 5 mm, power width 5 mm, die spacing 6 mm, die edge margin 2 mm,
  spacings 3 / 3 / 5 mm and 2 mm to the signal copper; max power wire = the reference's longest, 16.151 mm; wire pitch the
  defaults 0.6 mm / 2 diameters because the measured 10 mm is the pitch between different dies; signal wires 25 mm): of the
  8 sequences x orientations (x merge variants, which exist for two sequences), orientation x has exactly 2 feasible
  sequences (proved by closed-form necessary conditions, ``orient0_windows`` in the tests, plus DRC-clean witnesses): the
  reference's own [PHASEd, DC-l, PHASEl, DC+d] and [PHASEd, DC-l, DC+d, PHASEl], both split.  Excluded in orientation x: LS
  pair [DC-l, PHASEd] (2 sequences) by max_kelvin_wire_length, short by 2.25 mm; HS pair at lower v than the LS pair (4
  sequences) by max_kelvin_wire_length, short by 24.9 mm.  Orientation y (all 8) is NOT proved infeasible: it is excluded
  by sampling only: of 12000 ``_sample`` draws (seed 1, after the T0282 float-tolerance fix) 182 orientation-y candidates
  were buildable, none passed the copper / spacing / signal-wire-limit pre-check, and the smallest signal-wire excess was
  17 mm.  That is evidence about the sampler's prior, not a bound on the parameter space.  The second sequence has 1.35 mm
  of slack.  The orientation-x search space is nearly the reference's own topology on Case 4 under its own rules; that is
  a property of the housing and the rules, not loosened here.  (Under the looser default 1 mm rules at least 3 topologies
  appear, ``test_at_least_three_topologies``.)

Float-tolerance audit (T0290, after review T0288; worded exactly after review T0294).  Comparisons that carry the DRC's tolerance
(1e-9 m = 1e-6 mm): ``_far_enough`` (feet clearance, CLEAR_TOL_MM), ``_quick_ok`` (signal-wire length, signal-to-power wire
distance, copper containment ``buffer(1e-9).contains``, net-to-net spacing), the ilo/ihi grid indices of ``_draw_feet`` and the
landing-point window ``land + ldv`` in ``_sample`` (ceil/floor with +-1e-9, like jlo/jhi, pmin/pmax), ``_g_up``/``_g_dn``/
``_on_grid``/``_pick_end``/the ValueError of ``_wire_pitch``.  Comparisons with NO tolerance, exact by construction because the
operands are multiples of the binary-exact grids 0.5 mm and 0.125 mm (sums and differences of such numbers of moderate size are
exact in float64): ``math.ceil(jc)`` / ``math.floor(jc)`` in ``_draw_feet``, ``hi_l < lo_l``, ``(end - edge) * (-side) < 1.0``,
``span < smin`` / ``span > smax`` in ``_sample``.  T0294 instrumented 26 000 evaluations and found no near-tie in them.
Defensive, no observed effect: the ``_quick_ok`` length / pitch tolerances (strict and tolerant versions never disagreed on 22 743
built candidates; the sampler places feet at pitch + 25 um, away from the tie) and the ilo/ihi and ``land + ldv`` tolerances (no
test fails when they are reverted).  Only the ``clear()`` / ``_far_enough`` tolerance changes sampled outcomes (k = 3, measured rules).

Keepout spacing (T0295, after review T0294 finding 0): ``drc.check`` compares trace-to-keepout spacing as a Euclidean distance, so
the sampler's free region (``_Ctx.free``) subtracts keepouts buffered with a ROUND join (16 segments per quarter circle) of radius
``(spacing - 1e-9 m) * cos(pi / 64)``; the polygonal arc then lies inside the true exclusion disc, so ``_quick_ok`` rejects no
placement the DRC accepts through this term (a diagonal placement at a keepout corner is kept).  The earlier mitre join had square
corners (1 of 525 DRC-clean Case 4 candidates under the measured rules was rejected).  The free region is slightly larger than with
the mitre join.  MEASURED (T0295, ``test_quick_ok_rejects_no_drc_clean_candidate_case4_measured``): Case 4, measured rules, k = 1, rng
seed 12345, 20 000 ``_sample`` draws: 2266 built, 260 DRC-clean, 0 of them rejected by ``_quick_ok`` (mitre join: 1 in T0294's run).  ``drc.check`` still filters every candidate in ``generate``.  Not changed: the outline edge margin (``allowed``).

Throughput, MEASURED on 2D_Case_4 (T0290; 2 dies per switch, gate + Kelvin wire per die, max power wire 18 mm, signal wires
25 mm; M-series Mac, one process; DRC-valid candidates per wall second of ``generate`` with seed 1 / seed 2, one run each, so a
single run has an unknown spread).  The machine was not idle: load average 3.3 / 3.6 / 3.9 (1 / 5 / 15 min) at the start and
3.6 / 3.7 / 3.9 at the end, other agents running.  These are measurements under that load, not bounds: rates move with the load
(T0288 measured lower values at a similar load).  Default rules, k = 1: 95.5 / 113.7 per s (150 layouts each); k = 3: 9.6 / 4.2 per
s (25 each).  Measured rules (``measure_rules``), k = 1: 44.1 / 31.8 per s (60 each); k = 3: 2.2 / 2.9 per s (8 each).  The
earlier figures (153 / 167, 46 / 44, 12 / 7, 3.1 / 4.2 per s, "conservative lower bounds") were single runs at a load of 5-6 and
were not bounds.  The E008 L1 screen needs 20 000 candidates per search; at the rates above that is roughly 3 min (default
rules, k = 1), 9-11 min (measured rules, k = 1), 1.9-2.5 h (measured rules, k = 3), to be re-measured under the load of the
run.  Without the float-tolerance fix the k = 3 yield on the measured rules was lower by a factor of about 2.7 (T0288: 11-12
against 30-34 DRC-valid per 60000 raw draws), not zero.  The
dominant cost is rejection: about 88 % of the raw draws are None (no feasible band / foot arrangement) and most of the rest
fail the pre-check or the DRC.  On Case 4 the fixed gate / Kelvin copper and the 25 mm limit leave four of the eight pair sequences
feasible under the default rules (HS pair above the LS pair, either order inside each pair; the merged-PHASE variants need a
longer HS wire than 18 mm); the 70 x 40 housing yields five sequence / merge variants (HS pair first only: the DC+ column
would cross the DC- pad otherwise).  ``test_throughput_case4`` (slow) asserts >= 5 / s.
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
from moduleforge.drc.rules import TOL as DRC_TOL
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
SIGNAL_NETS_SET = frozenset(SIGNAL_NETS)
_MIT = {"join_style": "mitre", "mitre_limit": 10.0}
# Keepout exclusion zones: round join (the DRC measures trace-to-keepout spacing as a Euclidean distance, so a mitre corner would
# exclude placements the DRC accepts, T0294 finding 0).  The arc is a polygon with 16 segments per quarter circle; its vertices lie
# on the circle (inscribed), and the radius is further multiplied by cos(pi / 64) = cos(half the angle of one segment) so that the
# polygon lies inside the true disc even if a buffer implementation circumscribed it (reduction <= 1.2e-3 of the radius, 6 um at 5 mm).
_ROUND_SEGS = 16
_ROUND_SHRINK = math.cos(math.pi / (4 * _ROUND_SEGS))
_RND = {"join_style": "round", "quad_segs": _ROUND_SEGS}


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
    pitch = (wu - 2 * margin) / (k - 1)  # the widest pitch that fits (the feet are parameters, ``Params.feet``)
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
N_COPPER_PARAMS = 4 + 4 * _NCOL + 4 * _NSLOT + 6 + 2  # entries of the vector before the wire feet
_FOOT_NAMES = ("fu0", "fud", "pitch", "fv", "land_du", "land_dv")
_SIG_NAMES = ("gate_du", "gate_dv", "kelvin_du", "kelvin_dv")


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
    feet: tuple  # per row (HS, LS): (fu0, fud, pitch, fv, land_du, land_dv), the power-wire feet and landings (mm)
    sigfeet: tuple  # per row (HS, LS): (gate du, gate dv, Kelvin du, Kelvin dv), gate / Kelvin feet from their pad centres

    NAMES = (("orient", "hs_first", "hs_die_first", "ls_die_first")
             + tuple(f"col_{n}_{c}" for n in NETS for c in ("u0", "v0", "u1", "v1"))
             + tuple(f"slot{i}_{c}" for i in range(_NSLOT) for c in ("u0", "v0", "u1", "v1"))
             + tuple(f"row_{s}_{c}" for s in ("HS", "LS") for c in ("u0", "v0", "gap")) + ("land_HS", "land_LS")
             + tuple(f"foot_{s}_{c}" for s in ("HS", "LS") for c in _FOOT_NAMES)
             + tuple(f"sig_{s}_{c}" for s in ("HS", "LS") for c in _SIG_NAMES))

    def to_vector(self) -> np.ndarray:
        v = [self.orient, self.hs_first, self.hs_die_first, self.ls_die_first]
        v += [x for c in self.cols for x in c] + [x for s in self.slots for x in s]
        v += [x for r in self.rows for x in r] + list(self.land)
        v += [x for r in self.feet for x in r] + [x for r in self.sigfeet for x in r]
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
        feet = (tuple(v[i + 8:i + 14]), tuple(v[i + 14:i + 20]))
        sigfeet = (tuple(v[i + 20:i + 24]), tuple(v[i + 24:i + 28]))
        return cls(int(v[0]), int(v[1]), int(v[2]), int(v[3]), cols, slots, rows, (v[i + 6], v[i + 7]), feet, sigfeet)

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
    dies, wires = [], []
    land = {"HS": p.land[0], "LS": p.land[1]}
    for sw, (u0, v0, gap), net in (("HS", p.rows[0], PHASE), ("LS", p.rows[1], DC_MINUS)):
        for i in range(spec.dies_per_switch):
            cx, cy = (mm_to_m(c) for c in fr.pt(u0 + i * (du + gap) + du / 2, v0 + dv / 2))
            pads = {n: (cx + r[0], cy + r[1], cx + r[2], cy + r[3]) for n, r in dsp.pads.items()}
            die = Die(cx, cy, dw, dh, sw, pads, dsp.thickness, dsp.attach_thickness)
            dies.append(die)
            pu0, pv0, pu1, pv1 = (c * 1e3 for c in fr.lrect(*pads["source"]))
            cu, cv = (pu0 + pu1) / 2, (pv0 + pv1) / 2
            fu0, fud, pit, fv, ldu, ldv = p.feet[0 if sw == "HS" else 1]
            z_start = z_top_cu + die.attach_thickness + die.thickness
            for j in range(k):
                u = cu + fu0 + i * fud + (j - (k - 1) / 2) * pit
                s_xy = tuple(mm_to_m(c) for c in fr.pt(u, cv + fv))
                e_xy = tuple(mm_to_m(c) for c in fr.pt(u + ldu, land[sw] + ldv))
                wires.append(arc_wire(s_xy, e_xy, z_start, z_top_cu, spec.loop_height, spec.wire_diameter, net))
    sig = _signal_wires(spec, traces, dies, z_top_cu, p, fr)
    kw = {} if spec.wire_sigma is None else {"wire_sigma": spec.wire_sigma}
    return Layout(family=_encode(p), dies_per_switch=spec.dies_per_switch, outline=spec.outline, traces=traces,
                  dies=dies, wires=wires, terminals=dict(spec.terminals), baseplate_outline=spec.baseplate_outline,
                  stack=st, backside_inset=spec.backside_inset, signal_wires=sig, **kw)


def _signal_wires(spec, traces, dies, z_top_cu, p, fr):
    """Straight gate / Kelvin wires from a foot in every die pad (pad centre + ``p.sigfeet``) to the nearest landable point
    of its switch's fixed copper."""
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
            off = p.sigfeet[0 if d.switch == "HS" else 1]
            du_, dv_ = off[0:2] if pad == "gate" else off[2:4]
            lu, lv = fr.pt((x0 + x1) / 2, (y0 + y1) / 2)  # local frame (an involution)
            s = fr.pt(lu + mm_to_m(du_), lv + mm_to_m(dv_))
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
            cut = [poly.buffer((r.spacing_for(n, kn) - 1e-9) * _ROUND_SHRINK, **_RND) for kn, poly in ko]
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
        self.vwin = {o: self._v_windows(o, self.free[PHASE]) for o in (0, 1)}
        # D0021: per orientation and net, the same windows of the net's own free region (a stack may straddle several), and
        # whether the single-window rule can place even the smallest possible stack (sum of the minimal slot heights and the
        # smallest gaps over all eight sequences, which no draw of ``_sample`` can undercut).  Where no window holds it the
        # single-window rule draws nothing at all (every draw returns None), so ``_sample`` places the stack across windows.
        self.bands = {o: {n: self._v_windows(o, self.free[n]) for n in NETS} for o in (0, 1)}
        self.split = {}
        for o in (0, 1):
            dv = _Frame(o).size(spec.die.w, spec.die.h)[1] * 1e3
            least = math.inf
            for combo in range(8):
                seq = _sequence(combo & 1, combo >> 1 & 1, combo >> 2 & 1)
                tot = sum(dv + 2 * self.dem if role == "die" else max(self.wmin[net], 2.0) for net, role, _ in seq)
                tot += sum(0.0 if seq[i][0] == seq[i + 1][0] else self.sp[(seq[i][0], seq[i + 1][0])] for i in range(3))
                least = min(least, tot)
            self.split[o] = not any(w[1] - w[0] >= least for w in self.vwin[o])

    def _v_windows(self, o: int, region) -> list:
        fr = _Frame(o)
        ulo, vlo, uhi, vhi = fr.rect(*(c * 1e3 for c in self.allowed.bounds))
        vs = np.arange(_g_up(vlo), _g_dn(vhi) - 1e-9, DESIGN_GRID_MM)
        ok = []
        for v in vs:
            strip = box(*(c * 1e-3 for c in fr.rect(ulo, v, uhi, v + DESIGN_GRID_MM)))
            ok.append(region.intersection(strip).area / strip.area >= 0.4)
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
        return wins

    def reach(self, net: str, o: int, va: float, vb: float, u_from: float, side: int, bound: float) -> float:
        """Furthest u (mm, grid) from ``u_from`` towards ``side`` (+1 / -1), at most ``bound``, such that the band
        ``va..vb`` (v, mm) stays inside the net's free region (keepouts and their spacing); ``bound`` if nothing is in the way."""
        fr = _Frame(o)
        a, b = (u_from, bound) if side > 0 else (bound, u_from)
        if b <= a:
            return bound
        strip = box(*(c * 1e-3 for c in fr.rect(a, va, b, vb)))
        blocked = strip.difference(self.free[net]).buffer(-1e-6, **_MIT)  # drops float slivers (1 um)
        if blocked.is_empty:
            return bound
        ub = [c * 1e3 for c in fr.rect(*blocked.bounds)]
        return _g_dn(ub[0]) if side > 0 else _g_up(ub[2])


CLEAR_TOL_MM = 1e-6  # absolute tolerance 1e-9 m of the clearance comparison (the DRC's own snapping scale is nm)
FOOT_GRID_MM = 0.125  # grid of the wire feet and landings (the reference's own bond points are on it)


def _far_enough(dist_mm: float, need_mm: float) -> bool:
    """``dist >= need`` with the absolute tolerance ``CLEAR_TOL_MM`` (1e-9 m), as ``drc.check`` compares (T0281 finding 0)."""
    return dist_mm >= need_mm - CLEAR_TOL_MM


def _draw_feet(spec: ReferenceSpec, rng: np.random.Generator, fr: _Frame, row: tuple, sgn: float):
    """Power-wire feet ``(fu0, fud, pitch, fv)`` and gate / Kelvin feet of one die row (mm); None if the k wires cannot fit.

    Feet are drawn on the 0.125 mm grid inside the source pad (``wire_start_margin`` + 0.05 mm from its edge).  With
    probability 0.6 the wires are placed clear (by the pitch rule + 25 um) of the plan-view lines of the die's gate and Kelvin
    wires, which run straight along v when the fixed signal copper lies along v (the case on Case 4); otherwise the draw is
    unconstrained and the DRC decides."""
    r = spec.rules
    u0 = row[0]
    du, dv = (x * 1e3 for x in fr.size(spec.die.w, spec.die.h))
    k, n = spec.wires_per_die, spec.dies_per_switch
    dm, ds = spec.wire_diameter * 1e3, spec.signal_wire_diameter * 1e3
    pu0, pv0, pu1, pv1 = (c * 1e3 for c in fr.lrect(*spec.die.pads["source"]))
    m = max(r.wire_start_margin * 1e3, dm / 2) + 0.05
    hu, hv = (pu1 - pu0) / 2 - m, (pv1 - pv0) / 2 - m
    if hu < 0 or hv < 0:
        return None
    pp = max(r.min_wire_pitch * 1e3, r.wire_pitch_diameters * dm) + 0.025
    ps = max(r.min_wire_pitch * 1e3, r.wire_pitch_diameters * max(dm, ds)) + 0.025
    # gate / Kelvin feet: offsets from the pad centres, spread apart with probability 0.5
    sig, sig_u = [0.0, 0.0, 0.0, 0.0], []  # sig_u: (offset from the die-0 source-pad centre along u) of each signal wire
    cen = {}
    for pad in ("gate", "kelvin"):
        if pad not in spec.die.pads:
            continue
        a0, b0, a1, b1 = (c * 1e3 for c in fr.lrect(*spec.die.pads[pad]))
        ms = max(r.wire_start_margin * 1e3, spec.signal_wire_diameter * 1e3 / 2) + 0.05
        cen[pad] = ((a0 + a1) / 2, (a1 - a0) / 2 - ms, (b1 - b0) / 2 - ms)
    if len(cen) == 2 and rng.random() < 0.5:
        lo_pad = min(cen, key=lambda t: cen[t][0])
        for pad in cen:
            ext = math.floor(cen[pad][1] / FOOT_GRID_MM + 1e-9) * FOOT_GRID_MM
            sig[2 * (pad == "kelvin")] = -ext if pad == lo_pad else ext
    for q, pad in enumerate(("gate", "kelvin")):
        if pad not in cen:
            continue
        _, hsu, hsv = cen[pad]
        if sig[2 * q] == 0.0:
            nu = int(math.floor(hsu / FOOT_GRID_MM + 1e-9)) if hsu > 0 else 0
            sig[2 * q] = FOOT_GRID_MM * int(rng.integers(-nu, nu + 1))
        nv = int(math.floor(hsv / FOOT_GRID_MM + 1e-9)) if hsv > 0 else 0
        sig[2 * q + 1] = FOOT_GRID_MM * int(rng.integers(-nv, nv + 1))
        sig_u.append(cen[pad][0] + sig[2 * q] - (pu0 + pu1) / 2)
    pmin = math.ceil(pp / FOOT_GRID_MM - 1e-9) * FOOT_GRID_MM
    pit = 0.0
    if k > 1:
        pmax = math.floor(2 * hu / (k - 1) / FOOT_GRID_MM + 1e-9) * FOOT_GRID_MM
        if pmax < pmin - 1e-9:
            return None
        pit = pmin + FOOT_GRID_MM * int(rng.integers(0, int(round((min(pmax, pmin + 2.0) - pmin) / FOOT_GRID_MM)) + 1))
    cu0 = u0 + du / 2 + (pu0 + pu1) / 2  # abs u of the die-0 source-pad centre
    fud = 0.0 if rng.random() < 0.7 else FOOT_GRID_MM * int(rng.integers(-8, 9))
    span = (k - 1) * pit

    def rel0_range(fd):  # range of the first wire's offset from the die-0 pad centre so that all feet stay inside
        return (max(-hu - i * fd for i in range(n)), min(hu - span - i * fd for i in range(n)))

    lo, hi = rel0_range(fud)
    if hi < lo - 1e-9:
        fud = 0.0
        lo, hi = rel0_range(fud)
    if hi < lo - 1e-9:
        return None
    ilo, ihi = math.ceil(_gdiv(cu0 + lo) - 1e-9), math.floor(_gdiv(cu0 + hi) + 1e-9)  # grid index tolerance as the neighbours
    if ihi < ilo:
        return None

    def clear(a0):
        return all(_far_enough(abs(a0 - cu0 + j * pit + i * fud - su), ps) for i in range(n) for j in range(k) for su in sig_u)

    a_abs = None
    if sig_u and rng.random() < 0.6:
        for _ in range(30):
            c = (int(rng.integers(ilo, ihi + 1)) * FOOT_GRID_MM)
            if clear(c):
                a_abs = c
                break
    if a_abs is None:
        a_abs = int(rng.integers(ilo, ihi + 1)) * FOOT_GRID_MM
    fu0 = a_abs - cu0 + span / 2
    pcv = row[1] + dv / 2 + (pv0 + pv1) / 2  # abs v of the source-pad centre
    jlo, jhi = math.ceil((pcv - hv) / FOOT_GRID_MM - 1e-9), math.floor((pcv + hv) / FOOT_GRID_MM + 1e-9)
    if jhi < jlo:
        return None
    jc = (pcv / FOOT_GRID_MM)
    if rng.random() < 0.5:  # towards the landing line (the legacy rule put the foot there, 25 % of the pad height out)
        jlo, jhi = (max(jlo, math.ceil(jc)), jhi) if sgn > 0 else (jlo, min(jhi, math.floor(jc)))
        if jhi < jlo:
            jlo = jhi = math.floor(jc) if sgn > 0 else math.ceil(jc)
    fv = int(rng.integers(jlo, jhi + 1)) * FOOT_GRID_MM - pcv
    return (fu0, fud, pit, fv), tuple(sig)


def _gdiv(x: float) -> float:
    return x / FOOT_GRID_MM


def _pick_end(needed: float, limit: float, free_side: int, rng, extra_max: float):
    """Free end of a band: ``needed`` or further by a random grid amount, clipped at ``limit``; None if infeasible."""
    if (limit - needed) * free_side < -1e-9:
        return None
    end = needed + free_side * _snap(rng.uniform(0.0, extra_max))
    return end if (limit - end) * free_side >= -1e-9 else limit


def _pick_start(ivs, lo: float, hi: float, rng, target: float | None):
    """A grid start in the union of intervals ``ivs`` within ``[lo, hi]``: the first feasible one at or after ``target``
    (jumping over an obstruction), or, without ``target``, uniform by length; None if there is none."""
    cl = []
    for a, b in ivs:
        a, b = _g_up(max(a, lo)), _g_dn(min(b, hi))
        if a <= b + 1e-9:
            cl.append((a, b))
    if not cl:
        return None
    if target is not None:
        for a, b in cl:
            if b >= target - 1e-9:
                return max(a, _g_up(target))
        return None
    w = np.array([b - a + DESIGN_GRID_MM for a, b in cl])
    a, b = cl[int(rng.choice(len(cl), p=w / w.sum()))]
    return a + DESIGN_GRID_MM * int(rng.integers(0, int(round((b - a) / DESIGN_GRID_MM)) + 1))


def _place_split(cx: _Ctx, orient: int, seq, h_min, h_ext, merge, g_min, g_ext, dwin, rng):
    """D0021: v extents ``((v0, v1) x 4, heights)`` of a four-slot stack whose slots may sit in different free windows of
    their own nets (the gap between them straddles the obstruction), or None.

    Slot ``i`` starts inside a window of its net's free region, with its centre inside ``dwin[i]`` if it is a die slot, and
    after the previous slot by at least the minimal gap (0 for a merged pair, which must then touch).  The random extras
    are shrunk (alpha 1, 0.5, 0) until a placement exists; a backward pass gives the latest start of every slot that still
    leaves room for the rest, a forward pass draws the starts (with probability 0.7 the first feasible start at or after the
    drawn gap, else uniformly in the feasible range)."""
    for alpha in (1.0, 0.5, 0.0):
        hts = [m + _snap(alpha * e) for m, e in zip(h_min, h_ext, strict=True)]
        gaps = [m + _snap(alpha * e) for m, e in zip(g_min, g_ext, strict=True)]
        feas = []
        for i, (net, _, _) in enumerate(seq):
            iv = [(a, b - hts[i]) for a, b in cx.bands[orient][net] if b - a >= hts[i]]
            if i in dwin:
                iv = [(max(a, dwin[i][0] - hts[i] / 2), min(b, dwin[i][1] - hts[i] / 2)) for a, b in iv]
            feas.append([(a, b) for a, b in iv if a <= b + 1e-9])
        late = [None] * 4
        end = math.inf
        for i in (3, 2, 1, 0):
            hi = max((_g_dn(min(b, end)) for a, b in feas[i] if _g_up(a) <= _g_dn(min(b, end))), default=None)
            if hi is None:
                break
            late[i] = hi
            end = late[i] - hts[i - 1] - g_min[i - 1] if i else 0.0
        else:
            starts, prev_end = [], None
            for i in range(4):
                if i == 0:
                    s0 = _pick_start(feas[0], -math.inf, late[0], rng, None)
                else:
                    lo = prev_end + g_min[i - 1]
                    target = lo if merge[i - 1] else (prev_end + gaps[i - 1] if rng.random() < 0.7 else None)
                    s0 = _pick_start(feas[i], lo, late[i], rng, target)
                    if s0 is None and target is not None:
                        s0 = _pick_start(feas[i], lo, late[i], rng, lo)
                    if s0 is not None and merge[i - 1] and s0 != prev_end:
                        return None
                if s0 is None:
                    return None
                starts.append(s0)
                prev_end = s0 + hts[i]
            return [(a, a + h) for a, h in zip(starts, hts, strict=True)], hts
    return None


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
    # window of each die slot's centre (absolute v) from the signal copper of its switch: the gate / Kelvin pad centre
    # (offset ``q`` from the die centre) within the wire-length limit, less 0.1 mm for the arc (sampling prior only;
    # the DRC enforces the real limits)
    dwin = {}
    qpad = {}
    for pad in ("gate", "kelvin"):
        if pad in spec.die.pads:
            _, b0, _, b1 = (c * 1e3 for c in fr.lrect(*spec.die.pads[pad]))
            qpad[pad] = (b0 + b1) / 2
    lim_of = {"gate": spec.rules.max_gate_wire_length, "kelvin": spec.rules.max_kelvin_wire_length}
    for i, (_, role, sw) in enumerate(seq):
        if role != "die":
            continue
        lo_w, hi_w, any_ = -math.inf, math.inf, False
        for kn, bb in sig.items():
            pad = "gate" if kn.startswith("GATE") else "kelvin"
            if kn.endswith("_" + sw) and pad in qpad and lim_of[pad] is not None:
                reach = lim_of[pad] * 1e3 - 0.1
                lo_w, hi_w, any_ = max(lo_w, bb[1] - reach - qpad[pad]), min(hi_w, bb[3] + reach - qpad[pad]), True
        if any_:
            dwin[i] = (lo_w, hi_w)
    split = cx.split[orient]
    if split:  # D0021: no single window holds even the smallest stack; place the slots across the windows
        placed = _place_split(cx, orient, seq, h_min, h_ext, merge, g_min, g_ext, dwin, rng)
        if placed is None:
            return None
        sv, hts = placed
    else:
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
        if split:  # the slot also stays inside the net's free region (keepouts and their spacing)
            lim = cx.reach(net, orient, va, vb, edge[net], free_side, lim)
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
    feet, sigfeet = {}, {}
    for sw in ("HS", "LS"):
        j = land_idx[sw]
        net = seq[j][0]
        lo, hi = wu[sw]
        needed = (hi + 1.0) if side[net] < 0 else (lo - 1.0)  # 0.5 mm plus room for the landing shift along u
        needed = _g_up(needed) if side[net] < 0 else _g_dn(needed)
        end = _pick_end(needed, limit(net, *sv[j]), -side[net], rng, 6.0)
        if end is None or (end - edge[net]) * (-side[net]) < 1.0:
            return None
        ends[j] = end
        sgn = 1.0 if j > die_idx[sw] else -1.0
        drawn = _draw_feet(spec, rng, fr, rows[sw], sgn)
        if drawn is None:
            return None
        (fu0, fud, pit, fv), sigfeet[sw] = drawn
        # wire length within the rules (with slack for the arc) along v from the wire foot
        sx0, sy0, sx1, sy1 = fr.lrect(*spec.die.pads["source"])
        foot = rows[sw][1] + dv / 2 + 1e3 * (sy0 + sy1) / 2 + fv
        wmin_, wmax_ = spec.rules.min_wire_length * 1e3 + 0.5, spec.rules.max_wire_length * 1e3 - 1.0
        lo_l, hi_l = (foot + wmin_, foot + wmax_) if sgn > 0 else (foot - wmax_, foot - wmin_)
        lo_l, hi_l = _g_up(max(lo_l, sv[j][0] + 0.5)), _g_dn(min(hi_l, sv[j][1] - 0.5))
        if hi_l < lo_l:
            return None
        land[sw] = lo_l + _snap(rng.uniform(0.0, hi_l - lo_l))
        ldv = 0.0 if rng.random() < 0.6 else FOOT_GRID_MM * int(rng.integers(-3, 4))
        if not (sv[j][0] + 0.5 - 1e-9 <= land[sw] + ldv <= sv[j][1] - 0.5 + 1e-9):
            ldv = 0.0
        ldu = 0.0 if rng.random() < 0.7 else FOOT_GRID_MM * int(rng.integers(-4, 5))
        feet[sw] = (fu0, fud, pit, fv, ldu, ldv)
    slots = tuple((edge[seq[i][0]], sv[i][0], ends[i], sv[i][1]) if side[seq[i][0]] < 0
                  else (ends[i], sv[i][0], edge[seq[i][0]], sv[i][1]) for i in range(4))
    return Params(orient, hs_first, hs_die_first, ls_die_first, tuple(cols[n] for n in NETS), slots,
                  (rows["HS"], rows["LS"]), (land["HS"], land["LS"]), (feet["HS"], feet["LS"]),
                  (sigfeet["HS"], sigfeet["LS"]))


def _quick_ok(spec: ReferenceSpec, cx: _Ctx, lay: Layout) -> bool:
    """Cheap necessary conditions (a subset of the DRC, tested before the expensive width checks): copper inside its
    free region, spacing between the power nets, signal-wire length limits, no plan-view crossing of signal and power wires.

    The rule-value comparisons below carry the DRC's own tolerance (``drc.rules.TOL`` = 1e-9 m) (T0288 finding 3); keepout
    spacing is tested against a round-joined free region (see the module docstring, T0295), so the float tolerance and the
    Euclidean keepout distance are covered.  Not proved for every housing: T0295 counted zero DRC-clean candidates rejected on the
    sampled specs only.  Signal-wire length ``<= limit + TOL``, signal-to-power wire
    distance ``>= min_wire_pitch - TOL`` (shapely gives 0.0006249999999999971 m for the grid-exact 0.02875 / 0.029375 m pair)."""
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
        if lim is not None and w.length > lim + DRC_TOL:  # the DRC's tolerance (T0288 finding 3)
            return False
    if lay.signal_wires:
        power = [LineString(w.points[:, :2]) for w in lay.wires]
        for sw in lay.signal_wires:
            ln = LineString(sw.points[:, :2])
            if any(ln.distance(q) < spec.rules.min_wire_pitch - DRC_TOL for q in power):  # as drc.check (T0288 finding 3)
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

