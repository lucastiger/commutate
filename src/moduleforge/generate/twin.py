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
     the slot's mid-v.  Two adjacent slots of one net whose probe intervals overlap (a merged PHASE band) are split: if one
     interval is nested in the other with a common edge, at the inner edge; if both probes see the same interval (or the
     intervals overlap partly), by ``_best_split``: among the 0.5 mm grid lines strictly inside the union at which each slot
     still holds what it carries (its die row with ``rules.die_edge_margin``, its landing line with
     ``rules.wire_landing_margin``), the one that minimises the symmetric difference of the PHASE copper with the two slot
     rectangles (each with the chord at its own mid-v); ties: nearest the midpoint between the two needs, then lower.
     When the two slots have different u-extents (an L-shaped band) the minimum is unique and is the generator's boundary.
     When they have the same u-extent (a rectangular band, the usual DBC pad that carries one switch's dies and receives
     the other's wires) every boundary gives the same copper, so the copper does not determine it; the midpoint rule then
     chooses one between the needs (T0286 finding 0, T0291 finding 0, T0293 review).  Copper, label and L1 of the twin do
     not depend on that choice; the degradation does (move 1 narrows the landing slot, so a smaller landing slot leaves
     less to remove).  The topology label is 'merged' when the two slots touch;
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

Degradation (F1(b)) -- an ordered list of geometric moves and a fallback walk
------------------------------------------------------------------------------
``degrade(twin_layout, spec)`` applies deterministic geometric moves in the generator space, in a fixed order, each one
keeping the layout buildable and DRC-clean (a move whose result is not is skipped, a spread step that is not is the end of
that move), and stops at the first state with ``L1(D) / L1(twin) >= DEGRADE_RATIO * (1 + DEGRADE_MARGIN)`` (L1 at 20 MHz).
No search and no solver in the choice of a move; L1 only decides when to stop (and, in the walk, which change is kept).
Die count, the die footprint, wires per die, the wire feet relative to their die and the terminals stay.  The die positions
do *not* all stay: the spread moves (3) shift whole die rows (with the slots they sit in) in v by up to 20 mm, and the walk
(4) changes a row's start u, die-edge v or die gap in 0.5 mm steps; the wires move with their dies.  Landing points move
with their landing line (spread, walk) and by the landing shift of move 2.  The columns are extended to cover moved slots
(the walk also changes them directly).  The order:

1. ``narrow_landing``: every *landing slot* (the copper band on which the power wires of a die row land) is narrowed to the
   design-rule minimum width of its net (``rules.width_for(net)`` rounded up to the 0.5 mm grid, at least 1 mm; wider in 0.5 mm
   steps only if the landing point would otherwise be closer than the landing margin + 0.05 mm to a band edge).  The
   commutation current runs along these bands between the landing points and the DC- / PHASE columns; a partial inductance
   of a strip over the image planes scales with 1 / width.  If no band width up to the minimum + 5.5 mm holds the landing
   point by the margin, the move raises ``DegradeError`` (inside ``degrade``: it is recorded in ``skipped``).
2. ``centre_landing``: as 1, but each wire landing point may move along v by up to w0 (nearest first, on the 0.125 mm foot
   grid, ties: positive) so that the band reaches the minimum width w0.  A landing point off the 0.5 mm grid otherwise forces
   a band 0.5 mm wider (T0286: bands 2.0 mm wide could only reach 1.5 mm).  Landing points move by at most 0.25 mm in practice.
   A band for which no shift admits width w0 is skipped (it and its landing point stay, the reason is in ``widths``); a move
   that changes nothing is not applied.
3. ``spread``: slots ``j..3`` (or ``0..j-1``) with the die rows and landing lines they carry are moved by 0.5, 1.0, ... mm in
   v (up to 20 mm) in the order (j, direction) = (2, up), (2, down), (1, up), (3, up), (1, down), (3, down): the pairs move
   apart (j = 2) or the landing band moves away from its die row (j = 1, 3: longer wires).  Each step must be DRC-clean
   (outline, spacing, ``max_wire_length``); the first step that meets the target ends the rule, otherwise the largest
   feasible step is kept and the next move follows.
4. ``walk`` (T0293; T0291 caveat 1).  If the target is still missed, a deterministic walk over the generator's own
   parameters: the column, slot (u0, v0, u1, v1), die-row (start u, die-edge v, gap) and landing-line parameters, in the
   order of ``Params.NAMES``, each changed by -0.5 mm and +0.5 mm (the design grid).  At each step the DRC-valid
   single-parameter change (it builds, ``check`` is clean) that raises L1 *most* is applied (ties: the first in that order;
   the change must raise L1 strictly), until the target is met.  The walk starts from the state after moves 1-3 (from the
   twin itself if no move applied).  When no valid single-parameter change raises L1 further (a local maximum), or after
   ``WALK_MAX_STEPS`` steps, ``DegradeError`` is raised.  ``record['walk']`` (also on the exception) holds the ratio at the
   walk's start (after moves 1-3), every step with its ratio, the terminal kind (``target_reached``, ``local_maximum``,
   ``step_limit``), the terminal ratio and a message, which is also in the exception's message.  A hill-climb stops at
   local maxima, so this is an honest limit, not a proof that no layout exists.  Every step is listed in
   ``record['moves']`` as ``walk[<parameter><+/->0.5mm]``.  Computational cost: about 70 candidates per step, one L1 each
   (some 25 ms).  Caveat (T0293 review): the walk climbs on the L1 screen that also decides when it stops, so it may
   favour changes on which L1 is biased, and it stops just above the target (median 1.394 against 1.3875 on the 2 mm
   stress set); the 0.11 margin was derived from generator layouts, not walk outputs.  On one walk case the ratio was
   stable under L1 mesh refinement (1.394 / 1.390 / 1.392 at hmax 4 / 2 / 1 mm; ``test_walk_ratio_is_stable_...``), but
   only E008's L2 ratio is evidence that a walk-produced D meets 1.25.

``DegradeError`` is raised when no move or walk step reaches the target.  Without L1 (``with_l1=False``) nothing says when to
stop and the walk is not run: the first feasible move of the order 1, 2, 3 (spread moves at their first step, 0.5 mm) is
applied, and the others are not (a move that is infeasible is skipped for the next one; if none is feasible
``DegradeError``).  The record lists the moves, the ones skipped and why, and the landing-band widths of each landing move
actually applied, measured on the state it was applied to (``widths_by_move``; ``widths`` is the last of them, empty when
none was applied); see ``degrade``.

DEGRADE_MARGIN = 0.11.  C002 / E002 found L1 biased low by 5-14 % relative to the converged L2 with family- and die-count
dependent structure.  D and its twin share the family, housing, die count and wires, so the bias largely cancels in the
ratio; what does not is bounded by the spread of the bias.  With L1 = L2 (1 - b), L2 ratio = L1 ratio (1 - b_W) / (1 - b_D), so
the L1 ratio overstates the L2 ratio most when the twin is biased 14 % low and D 5 % low: by at most 0.95 / 0.86 - 1 = 10.5 %,
so the margin is at least 0.105; 0.11 gives 1.25 * 1.11 / 1.105 = 1.2556 >= 1.25.  Caveats (T0291 finding 2): the 5-14 % band
was measured on generator layouts at L1's 4 mm mesh, not on degraded layouts with 1 mm bands; on 2D_Case_4 the twin's L1 bias was
15.3 % (outside the band) and D's 9.2 %, the L1 ratio 1.421 against an L2 ratio of 1.325 (still >= 1.25).  E008 checks L_sub at
0.25 mm cells itself and should record the L2 ratio of every D; this is a screen.

Exploration of the alternatives (T0286 finding 4; generator housing layouts, L1 at 20 MHz, ratios relative to the state after
move 1 unless stated; scratch runs of T0287):
* Moving only die rows or slots apart in v (move 3 alone, any j, up to the largest DRC-feasible shift of 0.5-8 mm) raises
  the ratio by 0-9 %, typically 3-5 %: far less than the 20-40 % that the narrowing gives, which is why it is a late move.
* Narrowing the die slots to the die plus the die-edge margin: +0.1-2 %.  Trimming the free ends of the slots to the dies /
  landing points: 0.0 % (copper beyond the current path does not matter).  Both were dropped.
* Landing-point centring (move 2): rescues the cases where move 1 leaves 1.18-1.34 (bands that stay 0.5 mm wider than the
  minimum); in a sample of 225 housing layouts (n = 2..4, k = 1..3, 25 seeds each, default 1 mm rules) move 1 alone reached
  the target on 223, moves 1 + 2 on all 225.
* With the stricter 2 mm minimum width (72 layouts: n = 2, 3, 4 x k = 1, 2, 3 x 8 layouts, seed 1000 n + 10 k + 7) the bands of
  the twin are often already at the rule minimum.  Moves 1-3 alone left 45 of 72 in ``DegradeError`` (ratios 1.0-1.38).  With
  the walk, 63 of 72 reach the target (ratios min 1.3875, median 1.3943, max 2.0866) and all are DRC-clean; 9 end at a local
  maximum of the hill-climb (terminal kind ``local_maximum``) at ratios 1.206-1.372 after 48-64 walk steps from 1.003-1.225
  after moves 1-3 (``tests/regression/test_degrade_walk_stress.py`` lists them with their start and terminal ratios).  A
  judged reference at such a rule can still raise ``DegradeError``; its record says where the walk stopped.  On the 54
  default-rule layouts and Case 4 the walk is never needed (zero failures).
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


SPLIT_TIE_M2 = 1e-12  # symmetric differences within 1e-6 mm^2 tie (genuine ones differ by >= 0.25 mm^2: 0.5 mm grid)
SPLIT_EPS_MM = 1e-6  # a landing line on the boundary is not inside its slot


def _best_split(poly, seq, ivs, i: int, anchor, rules) -> float:
    """Boundary v (mm) of the merged band formed by slots ``i`` and ``i + 1`` of one net, when the probe intervals do not
    say where it is (both probes see the same v-interval, or the intervals overlap partly; T0291 finding 0, T0293 review).

    Candidates: the 0.5 mm grid lines strictly inside the union ``(lo, hi)`` of the two intervals at which each slot still
    holds what it carries (``_split_window``): the lower slot's need (its die row's upper edge, or its landing line) plus
    its margin (``rules.die_edge_margin`` for a die slot, ``rules.wire_landing_margin`` for a landing slot) at or below the
    boundary, the upper slot's need less its margin at or above it.  If no grid line meets the margins, the window between
    the needs themselves (a landing line strictly inside its slot); if that is empty too, every grid line in ``(lo, hi)``.
    Among the candidates, the boundary that minimises the symmetric difference between the reference copper ``poly`` and
    the union of the two slot rectangles (each with the horizontal chord of the copper at its own mid-v).  Ties (within
    ``SPLIT_TIE_M2``; a rectangular band, whose copper is the same for every boundary, ties everywhere): the boundary
    nearest to the midpoint of the two needs, then the lower one.  Where the band is not rectangular (different u-extents of the two slots) the minimum is unique and is
    the generator's boundary; where it is rectangular the copper does not determine the boundary and the midpoint rule
    chooses it (the generator's own boundary is then recovered only when it lies nearest the midpoint)."""
    lo, hi = ivs[i][0], ivs[i + 1][1]
    n_lo, n_hi = anchor[i][2][1], anchor[i + 1][2][0]
    mid = 0.5 * (n_lo + n_hi)
    grid = []
    s_ = math.floor(lo / GRID + 1e-9) * GRID + GRID
    while s_ < hi - 1e-9:
        grid.append(s_)
        s_ += GRID
    for a, b in _split_window(seq, i, n_lo, n_hi, rules):
        cands = [x for x in grid if a - 1e-9 <= x <= b + 1e-9]
        if cands:
            break
    scored = []
    for x in cands:
        rects = []
        for (a, b), pr in (((lo, x), anchor[i][0]), ((x, hi), anchor[i + 1][0])):
            ch = _chord(poly, 0.5 * (a + b), pr)
            if ch is None:
                break
            rects.append(box(_snap(ch[0]) * MM, _snap(a) * MM, _snap(ch[1]) * MM, _snap(b) * MM))
        else:
            scored.append((poly.symmetric_difference(unary_union(rects)).area, x))
    if not scored:  # no candidate gives two slot rectangles: the grid line nearest the midpoint of the needs
        return min(grid or [_snap(mid)], key=lambda x: (abs(x - mid), x))
    sd_min = min(sd for sd, _ in scored)
    return min((x for sd, x in scored if sd <= sd_min + SPLIT_TIE_M2), key=lambda x: (abs(x - mid), x))


def _split_window(seq, i: int, n_lo: float, n_hi: float, rules):
    """The closed windows (a, b) of the boundary for ``_best_split``, in the order tried: between the needs with the
    margins of the two slots' roles; between the needs themselves (a die row may end on the boundary, a landing line must
    lie strictly inside its slot, by ``SPLIT_EPS_MM``); unbounded."""
    m = {"die": rules.die_edge_margin / MM, "land": rules.wire_landing_margin / MM}
    e = {"die": 0.0, "land": SPLIT_EPS_MM}
    lo_role, hi_role = seq[i][1], seq[i + 1][1]
    return ((n_lo + m[lo_role], n_hi - m[hi_role]), (n_lo + e[lo_role], n_hi - e[hi_role]), (-math.inf, math.inf))


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
    # split overlapping intervals of one net (a merged band): if the probes see nested intervals with a common edge, the
    # boundary is the inner edge of the nested one; if they see the same interval (or the intervals overlap partly), the
    # grid line chosen by ``_best_split`` (minimum symmetric difference among the boundaries at which each slot holds its
    # die row / landing line with its margin; ties: nearest the midpoint of the needs, then lower)
    for i in range(3):
        (a0, a1), (b0, b1) = ivs[i], ivs[i + 1]
        if seq[i][0] != seq[i + 1][0] or min(a1, b1) - max(a0, b0) <= 1e-9:
            continue
        if abs(a0 - b0) <= 1e-9 and a1 < b1 - 1e-9:  # lower slot [a0, a1] inside the upper slot's interval
            ivs[i + 1][0] = a1
        elif abs(a1 - b1) <= 1e-9 and b0 > a0 + 1e-9:  # upper slot [b0, b1] inside the lower slot's interval
            ivs[i][1] = b0
        else:  # equal (or partly overlapping) intervals
            ivs[i][0], ivs[i + 1][1] = min(a0, b0), max(a1, b1)
            ivs[i][1] = ivs[i + 1][0] = _best_split(polys[seq[i][0]], seq, ivs, i, anchor, spec.rules)
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
            cand = next(((w, a) for w in (w0 + D.DESIGN_GRID_MM * q for q in range(12))
                         for a in (D._g_dn(ve - w / 2) + D.DESIGN_GRID_MM * j for j in (0, -1, 1))
                         if ve - a >= margin and a + w - ve >= margin), None)
            if cand is not None and (cand[0] <= w0 + 1e-9 or not centre):
                pick, shift = cand, dv
                break
        old = slots[i]
        if pick is None:
            if not centre:
                raise DegradeError(f"no band width up to {w0 + 5.5:g} mm holds the {sw} landing point by the landing "
                                   f"margin {r.wire_landing_margin * 1e3:g} mm (minimum width {w0:g} mm)")
            # T0291 finding 1: no landing shift admits the minimum width -> skip this band (it stays as it is, centred
            # on nothing; the landing point is never moved off the band) and say why
            widths[f"{sw}_landing_{net}"] = {
                "before_mm": old[3] - old[1], "after_mm": old[3] - old[1], "landing_shift_mm": 0.0,
                "skipped": f"no landing shift within +-{w0:g} mm admits a band of width {w0:g} mm with the landing "
                           f"margin {r.wire_landing_margin * 1e3:g} mm"}
            continue
        w, a = pick
        feet[k][5] = p.feet[k][5] + shift
        widths[f"{sw}_landing_{net}"] = {"before_mm": old[3] - old[1], "after_mm": w,
                                         "landing_shift_mm": feet[k][5] - p.feet[k][5]}
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


LANDING_MOVES = ("narrow_landing", "centre_landing")


def _moves():
    """The ordered move families (name, strength steps, map (state, step) -> params).  A family with several steps is applied
    with growing strength until the target is met or the next step is infeasible; the largest feasible step is kept."""
    fam = [("narrow_landing", 1, lambda p, spec, q: _narrow_landing(p, spec, centre=False)[0]),
           ("centre_landing", 1, lambda p, spec, q: _narrow_landing(p, spec, centre=True)[0])]
    for j, down in SPREAD_ORDER:
        fam.append((f"spread[{j},{'down' if down else 'up'}]", int(SPREAD_MAX_MM / SPREAD_STEP_MM),
                    lambda p, spec, q, j=j, down=down: _shifted(p, j, q * SPREAD_STEP_MM, down)))
    return fam


WALK_STEP_MM = D.DESIGN_GRID_MM
WALK_MAX_STEPS = 400
WALK_TARGET, WALK_LOCAL_MAX, WALK_STEP_LIMIT = "target_reached", "local_maximum", "step_limit"  # terminal kinds
# Params.NAMES[WALK_FIRST:WALK_END]: the column, slot, die-row and landing-line parameters (the walk's parameters)
WALK_FIRST, WALK_END = 4, D.N_COPPER_PARAMS  # after the four ints: 12 column + 16 slot + 6 row + 2 landing entries


def _walk_candidates(p: D.Params):
    """The single-parameter changes of the walk, in their fixed order: for every copper parameter of ``p`` in the order of
    ``Params.NAMES`` (columns, slots, die rows, landing lines), first -0.5 mm, then +0.5 mm (``WALK_STEP_MM``) ->
    (name, delta, params).  Changes that make a rectangle empty or inverted are not offered."""
    vec = p.to_vector()
    for i in range(WALK_FIRST, WALK_END):
        for d in (-WALK_STEP_MM, WALK_STEP_MM):
            v = vec.copy()
            v[i] += d
            q = D.Params.from_vector(v)
            if any(c[0] >= c[2] - 1e-9 or c[1] >= c[3] - 1e-9 for c in q.cols + q.slots):
                continue
            yield D.Params.NAMES[i], d, q


def _walk(spec, p: D.Params, lay: Layout, l_tw: float, target: float):
    """The fallback walk of ``degrade``: at each step apply, among the DRC-valid single-parameter changes of
    ``_walk_candidates`` that raise L1, the one with the highest L1 (ties: the first in the candidate order); stop when
    L1(D) / L1(W) >= ``target``, when no valid change raises L1 (terminal state), or after ``WALK_MAX_STEPS`` steps.
    -> (params, layout, ratio, steps, terminal kind, terminal-state string); the kind is ``WALK_TARGET``,
    ``WALK_LOCAL_MAX`` or ``WALK_STEP_LIMIT``."""
    cur = _l1(lay)
    steps = []
    for _ in range(WALK_MAX_STEPS):
        if cur / l_tw >= target:
            return p, lay, cur / l_tw, steps, WALK_TARGET, "target reached"
        best, n_valid = None, 0
        for name, d, q in _walk_candidates(p):
            cl, _ = _try(spec, q)
            if cl is None:
                continue
            n_valid += 1
            li = _l1(cl)
            if li > cur * (1.0 + 1e-12) and (best is None or li > best[0]):  # strict: the first of equal values wins
                best = (li, name, d, q, cl)
        if best is None:
            return p, lay, cur / l_tw, steps, WALK_LOCAL_MAX, (
                f"local maximum: none of the {n_valid} DRC-valid single-parameter changes raises L1 further "
                f"(ratio {cur / l_tw:.4f} after {len(steps)} walk steps)")
        cur, name, d, p, lay = best
        steps.append({"parameter": name, "delta_mm": d, "l1_ratio": cur / l_tw})
    if cur / l_tw >= target:
        return p, lay, cur / l_tw, steps, WALK_TARGET, "target reached"
    return p, lay, cur / l_tw, steps, WALK_STEP_LIMIT, f"stopped after {WALK_MAX_STEPS} steps at ratio {cur / l_tw:.4f}"


def degrade(twin_layout: Layout, spec: D.ReferenceSpec, with_l1: bool = True) -> tuple[Layout, dict]:
    """The frozen degradation rule of F1(b) applied to a twin built by ``derivative.build`` -> (D, record).

    Moves 1-3, then (with L1 only, if the target is still missed) the walk, see the module docstring.  The record has
    ``moves`` (every move applied, the walk steps as ``walk[parameter+-0.5mm]``), ``widths_by_move`` (for each landing move
    that was applied: per landing band ``before_mm`` -- the width in the state the move was applied to --, ``after_mm`` and
    ``landing_shift_mm``; a band that move 2 skipped carries ``skipped`` and is unchanged), ``widths`` (the entry of the
    last landing move applied -- move 2 if applied, else move 1 --, empty if neither was; later spread / walk moves are not
    in it), ``skipped`` (moves not applied and why) and ``walk`` (None if the walk did not run, else its start ratio, steps,
    terminal kind, terminal ratio and message).  ``DegradeError`` carries the record in its ``record`` attribute.

    ``with_l1=False``: no L1 is computed, so nothing says when to stop; the walk is not run.  The moves are tried in the
    order 1, 2, 3 (each spread move at its first 0.5 mm step only); a move that raises ``DegradeError``, changes nothing,
    does not build or is not DRC-clean is listed in ``skipped`` and the next is tried; the first feasible one is applied
    and the rule ends there (one move).  If none is feasible, ``DegradeError``.  The result is then not known to meet any
    ratio (``l1_checked`` False, no ``l1_ratio``)."""
    target = DEGRADE_RATIO * (1.0 + DEGRADE_MARGIN)
    p0 = D.params_of(twin_layout)
    l_tw = _l1(twin_layout) if with_l1 else None
    rec = {"rule": "ordered geometric moves and a fallback walk, see the module docstring", "target_l1_ratio": target,
           "margin": DEGRADE_MARGIN, "moves": [], "skipped": [], "walk": None, "l1_checked": with_l1,
           "widths_by_move": {}, "widths": {}}

    def fail(msg):
        err = DegradeError(msg)
        err.record = rec
        return err

    p, lay, ratio = p0, None, None
    for name, steps, make in _moves():
        kept = None
        for q in range(1, steps + 1):
            try:
                cand = make(p, spec, q)
            except DegradeError as e:
                rec["skipped"].append(f"{name}: {e}")
                break
            if cand.to_vector().tolist() == p.to_vector().tolist():
                rec["skipped"].append(f"{name}: changes nothing")
                break
            cl, why = _try(spec, cand)
            if cl is None:
                rec["skipped"].append(f"{name}: {why}")
                break
            kept = (cand, cl, q)
            if not with_l1:
                break
            ratio = _l1(cl) / l_tw
            if ratio >= target:
                break
        if kept is not None:
            if name in LANDING_MOVES:  # the widths of this move, on the state it was applied to (T0291 finding 3c)
                rec["widths_by_move"][name] = _narrow_landing(p, spec, centre=name == "centre_landing")[1]
            p, lay, q = kept
            rec["moves"].append(name if steps == 1 else f"{name}x{q * SPREAD_STEP_MM:g}mm")
        if not with_l1 and lay is not None:
            break  # without L1 the first feasible move of the order is applied (one step), see the docstring
        if ratio is not None and ratio >= target:
            break
    if with_l1 and (ratio is None or ratio < target):
        if lay is None:  # no move was applicable: the walk starts from the twin itself
            lay, why = _try(spec, p0)
            if lay is None:
                raise fail(f"the twin is not a DRC-clean start for the walk ({why})")
        start = _l1(lay) / l_tw
        p, lay, ratio, steps, kind, terminal = _walk(spec, p, lay, l_tw, target)
        rec["walk"] = {"start_l1_ratio": start, "steps": steps, "terminal": kind, "terminal_state": terminal,
                       "l1_ratio": ratio}
        rec["moves"] += [f"walk[{x['parameter']}{x['delta_mm']:+g}mm]" for x in steps]
    if lay is None:
        raise fail(f"no move gives a buildable, DRC-clean layout ({'; '.join(rec['skipped'])})")
    applied = [m for m in LANDING_MOVES if m in rec["widths_by_move"]]
    rec["widths"] = rec["widths_by_move"][applied[-1]] if applied else {}
    if with_l1:
        rec["l1_twin_H"], rec["l1_degraded_H"], rec["l1_ratio"] = l_tw, _l1(lay), _l1(lay) / l_tw
        if rec["l1_ratio"] < target:
            raise fail(f"L1 ratio {rec['l1_ratio']:.3f} < {target:.3f} after {rec['moves']}; walk terminal state: "
                       f"{rec['walk']['terminal_state'] if rec['walk'] else 'not run'}")
    return lay, rec
