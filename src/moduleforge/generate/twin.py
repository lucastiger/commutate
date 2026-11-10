"""Generator-space twin of a reference layout and the frozen degradation rule (O003, F1(a), F1(b); T0259).

``twin(reference, spec)`` expresses a reference layout in the parameter space of ``generate.derivative`` by a deterministic
*geometric* construction.  No solver output enters it (the L1 values in the record are computed afterwards and only reported).

Construction (all lengths mm in the local frame u / v of the orientation, see ``derivative``)
--------------------------------------------------------------------------------------------
0. Exact case.  If the reference was built by ``derivative.build`` and ``build(spec, params_of(reference))`` reproduces its
   fingerprint, the twin IS the reference (record ``mode == "exact"``).  This is the inverse map, not a fit; a modified layout
   whose family string is stale fails the fingerprint test and goes to the fit.  The exact case also runs
   ``check(layout, spec.rules)`` and raises ``TwinError`` on violations (T0286 finding 3).
1. Candidates: the 16 pairs (orientation, sequence), enumerated in the order orient 0 / 1, then ``hs_first``, ``hs_die_first``,
   ``ls_die_first`` = 0 / 1 (lexicographic, the first index wins a tie).  A pair is kept when the v-order of the four anchor
   points (HS die row, HS landing line, LS die row, LS landing line) is the order of its slots.
2. For a kept pair the parameters are read off the reference geometry, with no search:
   * die rows: start u, die-edge v and gap from the die rectangles of each switch (mean gap if not regular);
   * wire feet: ``fu0, fud, pitch, fv, land_du`` and the landing line / ``land_dv`` from the power-wire end points, as
     least-squares-free averages over the row (means of the per-wire offsets from the source-pad centres);
   * gate / Kelvin feet: the mean offsets of the reference's signal wires from their pad centres, zero when it has none;
   * slots: the v-interval of the net's copper along the vertical line through the row's first die centre (die slot) or the
     mean wire landing u of the row (landing slot; ``_feet_of`` returns it), and the full horizontal chord of the copper at
     the slot's mid-v.  Two adjacent slots of one net whose probe intervals overlap (a merged PHASE band; the die part and
     the landing part generally have different u extents, so the intervals are nested, not equal) are split: if one interval
     is nested in the other with a common edge, at the inner edge; if they are equal or overlap partly, at the grid line
     between what each slot needs, inside the overlap.  The topology label ('merged' when the two slots touch) and the
     slots are then those of the generator (T0286 finding 0);
   * columns: the bounding box of (copper minus the slot rectangles) joined with the terminal pad, if it lies in the copper;
     otherwise the pad rectangle.
   Copper coordinates and die-row starts / gaps are snapped to the 0.5 mm design grid and the wire feet to the 0.125 mm grid
   (the generator's grids).  The candidate with the smallest symmetric-difference area of the power copper wins; ties keep the
   first in the enumeration order.
3. If the fitted twin is not DRC-clean and the spec has gate / Kelvin pads (the reference had none or other wires), the gate
   and Kelvin feet are moved, and if that is not enough the power-wire feet of the switch along u: per switch (HS, then LS), for
   a power-foot shift of 0, +0.125, -0.125, +0.25 ... up to 1.5 mm (smallest first), coordinate descent (two passes) over the
   gate and Kelvin foot positions on the 0.125 mm grid inside the pad, each taking the position with the fewest violations at
   its switch (ties: nearest to the fitted offset, then smaller du, then smaller dv); the first shift that clears the switch
   is taken.  Any other violation, or no clean shift, raises ``TwinError``.  The shifts appear in the wire displacements of the
   record.

The record states every geometric difference: copper area per net, symmetric-difference area per net and in total, die-centre
displacements (dies matched per switch by minimum total distance) and power-wire foot / landing displacements.

Degradation (F1(b)) -- an ordered list of geometric moves
-----------------------------------------------------------
``degrade(twin_layout, spec)`` applies deterministic geometric moves in the generator space, in a fixed order, each one
keeping the layout buildable and DRC-clean (a move whose result is not is skipped, a spread step that is not is the end of
that move), and stops at the first state with ``L1(D) / L1(twin) >= DEGRADE_RATIO * (1 + DEGRADE_MARGIN)`` (L1 at 20 MHz).  No
search and no solver in the choice of a move; L1 only decides when to stop.  Dies, die count, wires per die, wire feet,
terminals and all other slots stay; the columns are extended to cover moved slots.  The order:

1. ``narrow_landing``: every *landing slot* (the copper band on which the power wires of a die row land) is narrowed to the
   design-rule minimum width of its net (``rules.width_for(net)`` rounded up to the 0.5 mm grid, at least 1 mm; wider in 0.5 mm
   steps only if the landing point would otherwise be closer than the landing margin + 0.05 mm to a band edge).  The
   commutation current runs along these bands between the landing points and the DC- / PHASE columns; a partial inductance
   of a strip over the image planes scales with 1 / width.
2. ``centre_landing``: as 1, but each wire landing point may move along v by up to w0 (nearest first, on the 0.125 mm foot
   grid, ties: positive) so that the band reaches the minimum width w0.  A landing point off the 0.5 mm grid otherwise forces
   a band 0.5 mm wider (T0286: bands 2.0 mm wide could only reach 1.5 mm).  Landing points move by at most 0.25 mm in practice.
3. ``spread``: slots ``j..3`` (or ``0..j-1``) with the die rows and landing lines they carry are moved by 0.5, 1.0, ... mm in
   v (up to 20 mm) in the order (j, direction) = (2, up), (2, down), (1, up), (3, up), (1, down), (3, down): the pairs move
   apart (j = 2) or the landing band moves away from its die row (j = 1, 3: longer wires).  Each step must be DRC-clean
   (outline, spacing, ``max_wire_length``); the first step that meets the target ends the rule, otherwise the largest
   feasible step is kept and the next move follows.
``DegradeError`` is raised when no move reaches the target (or the first move is not even buildable).  Without L1
(``with_l1=False``) only the first feasible move among 1 and 2 is applied, since nothing says when to stop.  The record lists the moves.

DEGRADE_MARGIN = 0.11.  C002 / E002 found L1 biased low by 5-14 % relative to the converged L2 with family- and die-count
dependent structure.  D and its twin share the family, housing, die count and wires, so the bias largely cancels in the
ratio; what does not is bounded by the spread of the bias: the L1 ratio can overstate the L2 ratio by at most
0.95 / 0.86 - 1 = 10.5 % (twin biased 5 % low, D biased 14 % low), so the margin is at least 0.105; 0.11 gives
1.25 * 1.11 / 1.105 = 1.2556 >= 1.25.  E008 checks L_sub at 0.25 mm cells itself; this is a screen.

Exploration of the alternatives (T0286 finding 4; generator housing layouts, L1 at 20 MHz, ratios relative to the state after
move 1 unless stated; scratch runs of T0287):
* Moving only die rows or slots apart in v (move 3 alone, any j, up to the largest DRC-feasible shift of 0.5-8 mm) raises
  the ratio by 0-9 %, typically 3-5 %: far less than the 20-40 % that the narrowing gives, which is why it is a late move.
* Narrowing the die slots to the die plus the die-edge margin: +0.1-2 %.  Trimming the free ends of the slots to the dies /
  landing points: 0.0 % (copper beyond the current path does not matter).  Both were dropped.
* Landing-point centring (move 2): rescues the cases where move 1 leaves 1.18-1.34 (bands that stay 0.5 mm wider than the
  minimum); in a sample of 225 housing layouts (n = 2..4, k = 1..3, 25 seeds each, default 1 mm rules) move 1 alone reached
  the target on 223, moves 1 + 2 on all 225.
* With the stricter 2 mm minimum width (72 layouts) the bands of the twin are often already at the rule minimum (nothing to
  narrow) and 45 of 72 end in ``DegradeError`` after all moves, at ratios 1.0-1.38.  This is the rule's limit, not a bug:
  a judged reference whose landing bands are already at the minimum width has no room for the F1(b) screen.
Population of T0286 (n = 2, 3, 4 dies x 1, 2, 3 wires per die x 6 seeds = 54 housing layouts; ``test_degradation_reaches_its_target_...``):
all reach the target; L1(D) / L1(twin): min 1.415, median 1.887, max 3.328 (move 1 alone on all of them).  2D_Case_4: 1.421
against the target 1.388.
"""
from __future__ import annotations

import dataclasses
import itertools
import math

import numpy as np
from scipy.optimize import linear_sum_assignment
from shapely.geometry import LineString, Point, box
from shapely.ops import unary_union

from moduleforge.drc import check
from moduleforge.generate import derivative as D
from moduleforge.geometry import NETS, Layout

MM = 1e-3
FOOT_GRID = D.FOOT_GRID_MM
GRID = D.DESIGN_GRID_MM
L1_FREQ_HZ = 20e6


class TwinError(ValueError):
    """The reference cannot be expressed as a DRC-clean layout of the generator space."""


def _snap(v: float, g: float = GRID) -> float:
    return round(float(v) / g) * g


def _l1(layout: Layout) -> float:
    from moduleforge.physics.peec import loop_inductance
    return float(loop_inductance(layout, [L1_FREQ_HZ]).L_H[0])


# ---------------------------------------------------------------------------------------------------------- geometry
def _loc(fr: D._Frame, x: float, y: float):
    return fr.pt(x, y)  # the frame is an involution


def _v_interval(poly, u: float, v: float):
    """(v0, v1) of the connected piece of ``poly`` along the line u = const (mm) that contains v; None if v is outside."""
    ln = poly.intersection(LineString([(u * MM, -1.0), (u * MM, 1.0)]))
    parts = [ln] if ln.geom_type == "LineString" else list(getattr(ln, "geoms", []))
    for p in parts:
        if p.geom_type == "LineString" and p.bounds[1] / MM - 1e-6 <= v <= p.bounds[3] / MM + 1e-6:
            return p.bounds[1] / MM, p.bounds[3] / MM
    return None


def _chord(poly, v: float, u: float):
    """(u0, u1) of the piece of ``poly`` along the line v = const (mm) that contains u."""
    ln = poly.intersection(LineString([(-1.0, v * MM), (1.0, v * MM)]))
    parts = [ln] if ln.geom_type == "LineString" else list(getattr(ln, "geoms", []))
    for p in parts:
        if p.geom_type == "LineString" and p.bounds[0] / MM - 1e-6 <= u <= p.bounds[2] / MM + 1e-6:
            return p.bounds[0] / MM, p.bounds[2] / MM
    return None


def _flip(poly, o: int):
    """``poly`` in the local frame of orientation ``o`` (axes swapped for o == 1)."""
    if o == 0:
        return poly
    from shapely.affinity import affine_transform
    return affine_transform(poly, [0, 1, 1, 0, 0, 0])


def _rows_of(ref: Layout, spec: D.ReferenceSpec, o: int):
    """Die rows per switch in the local frame: (u0, v0, gap), die centres sorted along u; None if the dies are not in a row."""
    fr = D._Frame(o)
    du, dv = (x / MM for x in fr.size(spec.die.w, spec.die.h))
    out = {}
    for sw in ("HS", "LS"):
        ds = [d for d in ref.dies if d.switch == sw]
        c = sorted((_loc(fr, d.cx / MM, d.cy / MM) for d in ds))
        if len(c) != spec.dies_per_switch or max(p[1] for p in c) - min(p[1] for p in c) > 0.3:
            return None
        gaps = [c[i + 1][0] - c[i][0] - du for i in range(len(c) - 1)]
        gap = float(np.mean(gaps)) if gaps else 1.0
        out[sw] = (_snap(c[0][0] - du / 2), _snap(float(np.mean([p[1] for p in c])) - dv / 2), _snap(gap))
    return out


def _match(a: np.ndarray, b: np.ndarray):
    """Minimum-total-distance assignment of the rows of ``a`` to the rows of ``b``; returns (index pairs, distances)."""
    cost = np.linalg.norm(a[:, None, :] - b[None, :, :], axis=2)
    i, j = linear_sum_assignment(cost)
    return list(zip(i.tolist(), j.tolist(), strict=True)), cost[i, j]


def _feet_of(ref: Layout, spec: D.ReferenceSpec, o: int, rows):
    """Wire feet per switch (fu0, fud, pitch, fv, land_du, land_dv), the landing lines and the mean wire landing u, from the
    reference wires."""
    fr = D._Frame(o)
    k = spec.wires_per_die
    sx = spec.die.pads["source"]
    pu = 0.5 * (D._Frame(o).lrect(*sx)[0] + D._Frame(o).lrect(*sx)[2]) / MM
    pv = 0.5 * (D._Frame(o).lrect(*sx)[1] + D._Frame(o).lrect(*sx)[3]) / MM
    du, dv = (x / MM for x in fr.size(spec.die.w, spec.die.h))
    feet, land, landu = {}, {}, {}
    for sw in ("HS", "LS"):
        ds = sorted((d for d in ref.dies if d.switch == sw), key=lambda d: _loc(fr, d.cx, d.cy))
        ws = []
        for d in ds:
            cu, cv = _loc(fr, d.cx / MM, d.cy / MM)
            mine = [w for w in ref.wires
                    if box(*d.pads["source"]).buffer(1e-9).contains(Point(w.points[0, 0], w.points[0, 1]))]
            if len(mine) != k:
                raise TwinError(f"die at ({d.cx / MM:.2f}, {d.cy / MM:.2f}) mm has {len(mine)} wires, spec says {k}")
            mine = sorted(mine, key=lambda w: _loc(fr, w.points[0, 0], w.points[0, 1]))
            ws.append((cu + pu, cv + pv, [(_loc(fr, w.points[0, 0] / MM, w.points[0, 1] / MM),
                                           _loc(fr, w.points[-1, 0] / MM, w.points[-1, 1] / MM)) for w in mine]))
        pit = float(np.mean([w[2][j + 1][0][0] - w[2][j][0][0] for w in ws for j in range(k - 1)])) if k > 1 else 0.0
        rel0 = [w[2][0][0][0] + (k - 1) / 2 * pit - w[0] for w in ws]  # mean-wire u offset from the pad centre, per die
        fud = float(np.mean(np.diff(rel0))) if len(ws) > 1 else 0.0
        fv = float(np.mean([s[0][1] - w[1] for w in ws for s in w[2]]))
        ldu = float(np.mean([s[1][0] - s[0][0] for w in ws for s in w[2]]))
        lv = float(np.mean([s[1][1] for w in ws for s in w[2]]))
        u0, v0, _ = rows[sw]
        cu0, cv0 = u0 + du / 2 + pu, v0 + dv / 2 + pv  # source-pad centre of die 0 of the (snapped) twin row
        # absolute foot positions on the 0.125 mm grid (the generator's own grid), not offsets from the pad centre
        feet[sw] = (_snap(cu0 + rel0[0], FOOT_GRID) - cu0, _snap(fud, FOOT_GRID), _snap(pit, FOOT_GRID),
                    _snap(cv0 + fv, FOOT_GRID) - cv0, _snap(ldu, FOOT_GRID), 0.0)
        land[sw] = _snap(lv, FOOT_GRID)
        landu[sw] = float(np.mean([s[1][0] for w in ws for s in w[2]]))  # mean wire landing u (the landing-slot probe)
    return feet, land, landu


def _sigfeet_of(ref: Layout, spec: D.ReferenceSpec, o: int):
    """Mean offsets of the reference's gate / Kelvin wire feet from their pad centres per switch (zero if it has none)."""
    fr = D._Frame(o)
    out = {}
    for sw in ("HS", "LS"):
        v = [0.0, 0.0, 0.0, 0.0]
        for q, pad in enumerate(("gate", "kelvin")):
            offs = []
            for w in ref.signal_wires:
                d = ref.dies[w.die]
                if d.switch != sw or w.pad != pad or pad not in d.pads:
                    continue
                x0, y0, x1, y1 = d.pads[pad]
                a = _loc(fr, w.points[0, 0] / MM - (x0 + x1) / 2 / MM, w.points[0, 1] / MM - (y0 + y1) / 2 / MM)
                offs.append(a)
            if offs:
                v[2 * q], v[2 * q + 1] = (_snap(x, FOOT_GRID) for x in np.mean(offs, axis=0))
        out[sw] = tuple(v)
    return out


def _fit(ref: Layout, spec: D.ReferenceSpec, o: int, hs_first: int, hdf: int, ldf: int, rows, feet, land, sig, landu):
    """Params for one (orientation, sequence) candidate, or None if the sequence does not match the geometry."""
    fr = D._Frame(o)
    seq = D._sequence(hs_first, hdf, ldf)
    du, dv = (x / MM for x in fr.size(spec.die.w, spec.die.h))
    polys = {n: _flip(next(t.polygon for t in ref.traces if t.net == n), o) for n in NETS}
    anchor = []  # per slot: (probe u, probe v, v-needed range)
    for _, role, sw in seq:
        u0, v0, _ = rows[sw]
        if role == "die":
            anchor.append((u0 + du / 2, v0 + dv / 2, (v0, v0 + dv)))
        else:
            anchor.append((landu[sw], land[sw], (land[sw], land[sw])))
    vs = [a[1] for a in anchor]
    if any(vs[i] > vs[i + 1] + 1e-9 for i in range(3)):
        return None
    ivs = []
    for (net, _, _), (pu, pv, _) in zip(seq, anchor, strict=True):
        iv = _v_interval(polys[net], pu, pv)
        if iv is None:  # the probe line misses the copper of the net: this (orientation, sequence) does not fit
            return None
        ivs.append(list(iv))
    # split overlapping intervals of one net (a merged band whose die and landing parts are seen by the two probes with
    # different extents): the boundary is the inner edge of the nested interval, or, if both are equal (or only partly
    # overlap), the grid line between what each slot needs, inside the overlap
    for i in range(3):
        (a0, a1), (b0, b1) = ivs[i], ivs[i + 1]
        if seq[i][0] != seq[i + 1][0] or min(a1, b1) - max(a0, b0) <= 1e-9:
            continue
        if abs(a0 - b0) <= 1e-9 and a1 < b1 - 1e-9:  # lower slot [a0, a1] inside the upper slot's interval
            ivs[i + 1][0] = a1
        elif abs(a1 - b1) <= 1e-9 and b0 > a0 + 1e-9:  # upper slot [b0, b1] inside the lower slot's interval
            ivs[i][1] = b0
        else:
            lo, hi = max(a0, b0), min(a1, b1)
            s_ = _snap(0.5 * (anchor[i][2][1] + anchor[i + 1][2][0]))
            if not lo < s_ < hi:
                s_ = 0.5 * (lo + hi)
            ivs[i][1] = ivs[i + 1][0] = s_
            ivs[i][0], ivs[i + 1][1] = min(a0, b0), max(a1, b1)
    slots, rects = [], {n: [] for n in NETS}
    for (net, _, _), (a, b) in zip(seq, ivs, strict=True):
        a, b = _snap(a), _snap(b)
        ch = _chord(polys[net], 0.5 * (a + b), anchor[len(slots)][0])
        if ch is None:
            return None
        r = (_snap(ch[0]), a, _snap(ch[1]), b)
        slots.append(r)
        rects[net].append(box(*(c * MM for c in r)))
    cols = []
    for net in NETS:
        t = ref.terminals[net]
        pad = box(*(c * MM for c in fr.rect(*((t.cx - t.w / 2) / MM, (t.cy - t.h / 2) / MM,
                                                (t.cx + t.w / 2) / MM, (t.cy + t.h / 2) / MM))))
        rest = polys[net].difference(unary_union(rects[net]).buffer(1e-9))
        cand = []
        if not rest.is_empty:
            comps = [g for g in getattr(rest, "geoms", [rest]) if g.area > 1e-12]
            near = min(comps, key=lambda g: g.distance(pad)) if comps else None
            cand += [unary_union(comps + [pad]).bounds] + ([unary_union([near, pad]).bounds] if near else [])
        cand.append(pad.bounds)
        for b in cand:
            bb = tuple(_snap(c / MM) for c in b)
            if polys[net].buffer(1e-9).contains(box(*(c * MM for c in bb))) and bb[0] < bb[2] and bb[1] < bb[3]:
                cols.append(bb)
                break
        else:
            return None
    return D.Params(o, hs_first, hdf, ldf, tuple(cols), tuple(slots), (rows["HS"], rows["LS"]),
                    (land["HS"], land["LS"]), (feet["HS"], feet["LS"]), (sig["HS"], sig["LS"]))


# ---------------------------------------------------------------------------------------------------------- record
def _power_union(lay: Layout):
    return {t.net: t.polygon for t in lay.traces if t.net in NETS}


def difference_record(ref: Layout, tw: Layout) -> dict:
    """Every geometric difference between twin and reference (SI in mm / mm^2)."""
    a, b = _power_union(ref), _power_union(tw)
    rec = {"copper_area_mm2": {n: {"reference": a[n].area / MM**2, "twin": b[n].area / MM**2} for n in NETS},
           "symdiff_area_mm2": {n: a[n].symmetric_difference(b[n]).area / MM**2 for n in NETS}}
    rec["symdiff_area_total_mm2"] = float(sum(rec["symdiff_area_mm2"].values()))
    rec["reference_copper_mm2"] = float(sum(p.area for p in a.values()) / MM**2)
    dd = {}
    for sw in ("HS", "LS"):
        ra = np.array([(d.cx, d.cy) for d in ref.dies if d.switch == sw]) / MM
        rb = np.array([(d.cx, d.cy) for d in tw.dies if d.switch == sw]) / MM
        pairs, dist = _match(ra, rb)
        dd[sw] = [float(x) for x in dist]
    rec["die_centre_displacement_mm"] = dd
    ws = {}
    for end, name in ((0, "foot"), (-1, "landing")):
        ra = np.array([w.points[end, :2] for w in ref.wires]) / MM
        rb = np.array([w.points[end, :2] for w in tw.wires]) / MM
        _, dist = _match(ra, rb)
        ws[name] = [float(x) for x in dist]
    rec["wire_displacement_mm"] = ws
    rec["max_die_displacement_mm"] = float(max(max(v) for v in dd.values()))
    rec["max_wire_displacement_mm"] = float(max(max(v) for v in ws.values()))
    return rec


# ---------------------------------------------------------------------------------------------------------- twin
def _foot_candidates(spec, pad: str):
    """Foot offsets (du, dv) of a gate / Kelvin pad on the 0.125 mm grid inside the pad (the sampler's margin)."""
    r = spec.rules
    x0, y0, x1, y1 = (c / MM for c in spec.die.pads[pad])
    m = max(r.wire_start_margin / MM, spec.signal_wire_diameter / MM / 2) + 0.05
    nu, nv = int(((x1 - x0) / 2 - m) / FOOT_GRID + 1e-9), int(((y1 - y0) / 2 - m) / FOOT_GRID + 1e-9)
    return [(i * FOOT_GRID, j * FOOT_GRID) for i in range(-nu, nu + 1) for j in range(-nv, nv + 1)]


def _n_violations(spec, p: D.Params, sw: int):
    """(layout, number of DRC violations nearest to a die of switch ``sw``; 10**6 if the build fails)."""
    try:
        lay = D.build(spec, p)
    except ValueError:
        return None, 10**6
    names = ("HS", "LS")[sw]
    mine = np.array([(d.cx, d.cy) for d in lay.dies if d.switch == names])
    other = np.array([(d.cx, d.cy) for d in lay.dies if d.switch != names])
    n = 0
    for v in check(lay, spec.rules):
        w = np.asarray(v.where if v.where is not None else (0.0, 0.0), float)[:2]
        n += int(np.linalg.norm(mine - w, axis=1).min() <= np.linalg.norm(other - w, axis=1).min())
    return lay, n


def _repair_signal(spec, p: D.Params, max_shift_mm: float = 1.5):
    """DRC repair for a spec with gate / Kelvin pads (module docstring, step 3).  Per switch (HS, then LS; violations are
    attributed to the switch whose die is nearest), for a power-foot shift along u of 0, +0.125, -0.125, +0.25 ... mm (the
    smallest first), coordinate descent over the gate and the Kelvin foot: each takes, among its grid positions, the one
    with the fewest violations (ties: nearest to the fitted offset, then smaller du, then smaller dv); two passes.  The
    first shift that clears the switch is taken."""
    pads = [pad for pad in ("gate", "kelvin") if pad in spec.die.pads]
    if not pads:
        return None
    cands = {pad: _foot_candidates(spec, pad) for pad in pads}
    n_steps = int(max_shift_mm / FOOT_GRID + 1e-9)
    shifts = [0.0] + [sgn * i * FOOT_GRID for i in range(1, n_steps + 1) for sgn in (1, -1)]
    cur = p
    for sw in (0, 1):
        for sh in shifts:
            feet = list(cur.feet)
            feet[sw] = (feet[sw][0] + sh,) + tuple(feet[sw][1:])
            trial = dataclasses.replace(cur, feet=tuple(feet))
            sig = [list(x) for x in trial.sigfeet]
            for _ in range(2):
                for pad in pads:
                    q = 0 if pad == "gate" else 2
                    fit = (sig[sw][q], sig[sw][q + 1])
                    best = None
                    for c in sorted(cands[pad], key=lambda c: (math.hypot(c[0] - fit[0], c[1] - fit[1]), c[0], c[1])):
                        sig[sw][q], sig[sw][q + 1] = c
                        _, n = _n_violations(spec, dataclasses.replace(trial, sigfeet=tuple(tuple(x) for x in sig)), sw)
                        if best is None or n < best[0]:
                            best = (n, c)
                    sig[sw][q], sig[sw][q + 1] = best[1]
            trial = dataclasses.replace(trial, sigfeet=tuple(tuple(x) for x in sig))
            if _n_violations(spec, trial, sw)[1] == 0:
                cur = trial
                break
        else:
            return None
    lay, _ = _n_violations(spec, cur, 0)
    return (lay, cur) if lay is not None and not check(lay, spec.rules) else None


def twin(reference: Layout, spec: D.ReferenceSpec, with_l1: bool = True) -> tuple[Layout, D.Params, dict]:
    """Generator-space twin W of ``reference`` inside ``spec`` -> (layout, params, record); see the module docstring."""
    exact = None
    try:
        p0 = D.params_of(reference)
        lay = D.build(spec, p0)
        if lay.fingerprint() == reference.fingerprint():
            exact = (lay, p0)
    except ValueError:
        pass  # not a derivative layout, or not one of this spec: the fit
    if exact is not None:
        lay, p0 = exact
        viol = check(lay, spec.rules)  # the shortcut honours the TwinError contract: DRC-clean under spec.rules
        if viol:
            raise TwinError("the reference is its own twin but is not DRC-clean under spec.rules: "
                            + "; ".join(str(v) for v in viol[:5]))
        rec = {"mode": "exact", "topology": p0.topology(), **difference_record(reference, lay)}
        return _finish(reference, lay, p0, rec, with_l1)
    best = None
    for o in (0, 1):
        rows = _rows_of(reference, spec, o)
        if rows is None:
            continue
        feet, land, landu = _feet_of(reference, spec, o, rows)
        sig = _sigfeet_of(reference, spec, o)
        for hf, hdf, ldf in itertools.product((0, 1), repeat=3):
            p = _fit(reference, spec, o, hf, hdf, ldf, rows, feet, land, sig, landu)
            if p is None:
                continue
            try:
                lay = D.build(spec, p)
            except ValueError:
                continue
            sd = sum(a.symmetric_difference(b).area for a, b in zip(
                _power_union(reference).values(), _power_union(lay).values(), strict=True))
            if best is None or sd < best[0] - 1e-18:  # strict: the first candidate in the enumeration order wins ties
                best = (sd, p, lay)
    if best is None:
        raise TwinError("no (orientation, sequence) of the generator space matches the reference geometry")
    _, p, lay = best
    viol = check(lay, spec.rules)
    mode = "fit"
    if viol:
        fixed = _repair_signal(spec, p)
        if fixed is None:
            raise TwinError("the fitted twin is not DRC-clean under spec.rules: "
                            + "; ".join(str(v) for v in viol[:5]))
        lay, p = fixed
        mode = "fit+signal_feet"
    rec = {"mode": mode, "topology": p.topology(), **difference_record(reference, lay)}
    return _finish(reference, lay, p, rec, with_l1)


def _finish(reference, lay, p, rec, with_l1):
    if with_l1:
        l_ref, l_tw = _l1(reference), _l1(lay)
        rec["l1_reference_H"], rec["l1_twin_H"] = l_ref, l_tw
        rec["l1_ratio_abs_dev"] = abs(1.0 - l_tw / l_ref)
    return lay, p, rec


# ------------------------------------------------------------------------------------------------------- degradation
DEGRADE_RATIO = 1.25  # F1(b): L_sub(D) >= 1.25 L_sub(twin)
DEGRADE_MARGIN = 0.11  # covers the L1-versus-L2 disagreement of the ratio (module docstring)


class DegradeError(ValueError):
    """No move of the degradation order gives a DRC-clean layout with the required L1 ratio."""


def _replace_slots(p: D.Params, slots, rows=None, land=None, feet=None) -> D.Params:
    """``p`` with new slots (and optionally rows / landing lines / feet); the columns are extended to cover every slot."""
    seq = p.sequence()
    cols = []
    for net, c in zip(NETS, p.cols, strict=True):
        mine = [slots[i] for i, s in enumerate(seq) if s[0] == net]
        cols.append((c[0], min([c[1]] + [m[1] for m in mine]), c[2], max([c[3]] + [m[3] for m in mine])))
    return dataclasses.replace(p, slots=tuple(tuple(s) for s in slots), cols=tuple(cols),
                               **{k: v for k, v in (("rows", rows), ("land", land), ("feet", feet)) if v is not None})


def _narrow_landing(p: D.Params, spec: D.ReferenceSpec, centre: bool):
    """Move 1 (``centre`` False) / move 2 (True): every landing slot to its net's minimum width, see the module docstring."""
    r = spec.rules
    margin = r.wire_landing_margin * 1e3 + 0.05
    slots, widths, feet = [list(s) for s in p.slots], {}, [list(f) for f in p.feet]
    for i, (net, role, sw) in enumerate(p.sequence()):
        if role != "land":
            continue
        k = 0 if sw == "HS" else 1
        w0 = max(D._g_up(r.width_for(net) * 1e3), 1.0)
        v_end = p.land[k] + p.feet[k][5]
        shifts = [0.0]
        if centre:  # landing points on the 0.125 mm foot grid, nearest shift first (ties: the positive one)
            shifts = [0.0] + [s * j * FOOT_GRID for j in range(1, int(w0 / FOOT_GRID) + 1) for s in (1, -1)]
        pick = None
        for dv in shifts:
            ve = v_end + dv
            # the narrowest band of width w0, w0 + 0.5, ... on the grid that holds the landing point by ``margin`` on both
            # sides (lowest edge a = floor_grid(ve - w / 2) + {0, -0.5, +0.5} that fits)
            pick = next(((w, a) for w in (w0 + D.DESIGN_GRID_MM * q for q in range(12))
                         for a in (D._g_dn(ve - w / 2) + D.DESIGN_GRID_MM * j for j in (0, -1, 1))
                         if ve - a >= margin and a + w - ve >= margin), None)
            if pick is not None and (pick[0] <= w0 + 1e-9 or not centre):
                feet[k][5] = p.feet[k][5] + dv
                break
        w, a = pick
        old = slots[i]
        widths[f"{sw}_landing_{net}"] = {"before_mm": old[3] - old[1], "after_mm": w, "landing_shift_mm": feet[k][5] - p.feet[k][5]}
        slots[i] = [old[0], a, old[2], a + w]
    return _replace_slots(p, slots, feet=tuple(tuple(f) for f in feet)), widths


def _try(spec, p):
    """(layout, None) if ``p`` builds and is DRC-clean, else (None, reason)."""
    try:
        lay = D.build(spec, p)
    except ValueError as e:
        return None, f"cannot be built: {e}"
    viol = check(lay, spec.rules)
    return (lay, None) if not viol else (None, "not DRC-clean: " + "; ".join(str(v) for v in viol[:3]))


def _shifted(p: D.Params, j: int, dv: float, down: bool) -> D.Params:
    """Slots ``j..3`` (``down`` False) or ``0..j-1`` (True) and the die rows / landing lines they carry, moved by +dv / -dv
    in v (mm); the columns are extended.  Wire feet and landing offsets stay, so wires move with their rows / bands."""
    slots, rows, land = [list(s) for s in p.slots], [list(r) for r in p.rows], list(p.land)
    d = -dv if down else dv
    for i, (_, role, sw) in enumerate(p.sequence()):
        if (i < j) != down:
            continue
        slots[i][1] += d
        slots[i][3] += d
        if role == "die":
            rows[0 if sw == "HS" else 1][1] += d
        else:
            land[0 if sw == "HS" else 1] += d
    return _replace_slots(p, slots, rows=tuple(tuple(r) for r in rows), land=tuple(land))


# the (first moved slot, direction) of the spread moves, in the order tried (module docstring)
SPREAD_ORDER = ((2, False), (2, True), (1, False), (3, False), (1, True), (3, True))
SPREAD_STEP_MM = D.DESIGN_GRID_MM
SPREAD_MAX_MM = 20.0


def _moves():
    """The ordered move families (name, strength steps, map (state, step) -> params).  A family with several steps is applied
    with growing strength until the target is met or the next step is infeasible; the largest feasible step is kept."""
    fam = [("narrow_landing", 1, lambda p, spec, q: _narrow_landing(p, spec, centre=False)[0]),
           ("centre_landing", 1, lambda p, spec, q: _narrow_landing(p, spec, centre=True)[0])]
    for j, down in SPREAD_ORDER:
        fam.append((f"spread[{j},{'down' if down else 'up'}]", int(SPREAD_MAX_MM / SPREAD_STEP_MM),
                    lambda p, spec, q, j=j, down=down: _shifted(p, j, q * SPREAD_STEP_MM, down)))
    return fam


def degrade(twin_layout: Layout, spec: D.ReferenceSpec, with_l1: bool = True) -> tuple[Layout, dict]:
    """The frozen degradation rule of F1(b) applied to a twin built by ``derivative.build`` -> (D, record)."""
    target = DEGRADE_RATIO * (1.0 + DEGRADE_MARGIN)
    p0 = D.params_of(twin_layout)
    l_tw = _l1(twin_layout) if with_l1 else None
    rec = {"rule": "ordered geometric moves, see the module docstring", "target_l1_ratio": target,
           "margin": DEGRADE_MARGIN, "moves": [], "l1_checked": with_l1}
    p, lay, ratio, why1 = p0, None, None, None
    for name, steps, make in _moves():
        kept = None
        for q in range(1, steps + 1):
            cand = make(p, spec, q)
            cl, why = _try(spec, cand)
            if cl is None:
                why1 = why1 or f"{name}: {why}"
                break
            kept = (cand, cl, q)
            if not with_l1:
                break
            ratio = _l1(cl) / l_tw
            if ratio >= target:
                break
        if kept is not None:
            p, lay, q = kept
            rec["moves"].append(name if steps == 1 else f"{name}x{q * SPREAD_STEP_MM:g}mm")
        if not with_l1 and lay is not None:
            break  # without L1 only the first (narrowing) move is applied, see the docstring
        if ratio is not None and ratio >= target:
            break
    if lay is None:
        raise DegradeError(f"no move gives a buildable, DRC-clean layout ({why1})")
    rec["widths"] = _narrow_landing(p0, spec, centre="centre_landing" in rec["moves"])[1]
    if with_l1:
        rec["l1_twin_H"], rec["l1_degraded_H"], rec["l1_ratio"] = l_tw, _l1(lay), _l1(lay) / l_tw
        if rec["l1_ratio"] < target:
            raise DegradeError(f"L1 ratio {rec['l1_ratio']:.3f} < {target:.3f} after {rec['moves']}")
    return lay, rec
