"""Generator-space twin of a reference layout and the frozen degradation rule (O003, F1(a), F1(b); T0259).

``twin(reference, spec)`` expresses a reference layout in the parameter space of ``generate.derivative`` by a deterministic
*geometric* construction.  No solver output enters it (the L1 values in the record are computed afterwards and only reported).

Construction (all lengths mm in the local frame u / v of the orientation, see ``derivative``)
--------------------------------------------------------------------------------------------
0. Exact case.  If the reference was built by ``derivative.build`` and ``build(spec, params_of(reference))`` reproduces its
   fingerprint, the twin IS the reference (record ``mode == "exact"``).  This is the inverse map, not a fit; a modified layout
   whose family string is stale fails the fingerprint test and goes to the fit.
1. Candidates: the 16 pairs (orientation, sequence), enumerated in the order orient 0 / 1, then ``hs_first``, ``hs_die_first``,
   ``ls_die_first`` = 0 / 1 (lexicographic, the first index wins a tie).  A pair is kept when the v-order of the four anchor
   points (HS die row, HS landing line, LS die row, LS landing line) is the order of its slots.
2. For a kept pair the parameters are read off the reference geometry, with no search:
   * die rows: start u, die-edge v and gap from the die rectangles of each switch (mean gap if not regular);
   * wire feet: ``fu0, fud, pitch, fv, land_du`` and the landing line / ``land_dv`` from the power-wire end points, as
     least-squares-free averages over the row (means of the per-wire offsets from the source-pad centres);
   * gate / Kelvin feet: the mean offsets of the reference's signal wires from their pad centres, zero when it has none;
   * slots: the v-interval of the net's copper along the vertical line through the row's first die centre (die slot) or the
     mean wire landing u (landing slot), and the full horizontal chord of the copper at the slot's mid-v.  Two slots of one
     net that fall in the same interval (a merged PHASE band) are split on the grid between what each needs;
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

Degradation (F1(b))
-------------------
``degrade(twin_layout, spec)`` is one fixed geometric move in the generator space, with no search and no solver in the
choice: every *landing slot* (the copper band on which the power wires of a die row land, one per switch) is narrowed to the
design-rule minimum width of its net (``rules.width_for(net)`` rounded up to the 0.5 mm grid, at least 1 mm; wider in 0.5 mm
steps only if the landing point would otherwise be closer than the landing margin + 0.05 mm to a band edge) around the
wire landing line, and the columns are extended so that they still reach the narrowed bands.  Dies, wire feet, wire landing
points, terminals and every other slot stay as they are.  The commutation current runs along these bands between the landing
points and the DC- / PHASE columns; a partial inductance of a strip over the substrate's image planes scales with 1 / width,
so narrowing lengthens the effective path.  Moving the die rows along u and widening the slot gaps were tried first: both move
L1 by less than 20 % in the interleaved and U-shaped families (research notes in the task report), the narrowing by 40 %+.

The acceptance is checked here by L1 at 20 MHz: ``L1(D) / L1(twin) >= DEGRADE_RATIO * (1 + DEGRADE_MARGIN)`` with
DEGRADE_RATIO = 1.25 (F1(b): L_sub(D) >= 1.25 L_sub(twin) by l2_layout, checked in E008) and DEGRADE_MARGIN = 0.10.  Why 0.10:
C002 / E002 found L1 biased low by 5-14 % relative to the converged L2 with family- and die-count-dependent structure; D and
its twin share the family, housing, die count and wires, so the bias largely cancels in the ratio and the part that does not is
bounded by the spread of the bias, 14 % - 5 % = 9 points; 0.10 covers it.  ``degrade`` raises ``DegradeError`` if the ratio
or the DRC fails (it does not try another move).  E008 checks the L_sub ratio at 0.25 mm cells itself.
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
    """Wire feet per switch (fu0, fud, pitch, fv, land_du, land_dv) and the landing lines, from the reference wires."""
    fr = D._Frame(o)
    k = spec.wires_per_die
    sx = spec.die.pads["source"]
    pu = 0.5 * (D._Frame(o).lrect(*sx)[0] + D._Frame(o).lrect(*sx)[2]) / MM
    pv = 0.5 * (D._Frame(o).lrect(*sx)[1] + D._Frame(o).lrect(*sx)[3]) / MM
    du, dv = (x / MM for x in fr.size(spec.die.w, spec.die.h))
    feet, land = {}, {}
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
    return feet, land


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


def _fit(ref: Layout, spec: D.ReferenceSpec, o: int, hs_first: int, hdf: int, ldf: int, rows, feet, land, sig):
    """Params for one (orientation, sequence) candidate, or None if the sequence does not match the geometry."""
    fr = D._Frame(o)
    seq = D._sequence(hs_first, hdf, ldf)
    du, dv = (x / MM for x in fr.size(spec.die.w, spec.die.h))
    polys = {n: _flip(next(t.polygon for t in ref.traces if t.net == n), o) for n in NETS}
    anchor = []  # per slot: (probe u, probe v, v-needed range)
    for _, role, sw in seq:
        u0, v0, gap = rows[sw]
        ld = spec.dies_per_switch * du + (spec.dies_per_switch - 1) * gap
        if role == "die":
            anchor.append((u0 + du / 2, v0 + dv / 2, (v0, v0 + dv)))
        else:
            anchor.append((u0 + ld / 2, land[sw], (land[sw], land[sw])))
    vs = [a[1] for a in anchor]
    if any(vs[i] > vs[i + 1] + 1e-9 for i in range(3)):
        return None
    ivs = []
    for (net, _, _), (pu, pv, _) in zip(seq, anchor, strict=True):
        iv = _v_interval(polys[net], pu, pv)
        if iv is None:  # the probe line misses the copper of the net: this (orientation, sequence) does not fit
            return None
        ivs.append(list(iv))
    # split merged intervals of one net between what each slot needs
    for i in range(3):
        if seq[i][0] == seq[i + 1][0] and ivs[i] == ivs[i + 1]:
            lo_need_top, hi_need_bot = anchor[i][2][1], anchor[i + 1][2][0]
            s = _snap(0.5 * (lo_need_top + hi_need_bot))
            if not ivs[i][0] < s < ivs[i][1]:
                s = 0.5 * (ivs[i][0] + ivs[i][1])
            ivs[i][1] = ivs[i + 1][0] = s
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
    try:
        p0 = D.params_of(reference)
        lay = D.build(spec, p0)
        if lay.fingerprint() == reference.fingerprint():
            rec = {"mode": "exact", "topology": p0.topology(), **difference_record(reference, lay)}
            return _finish(reference, lay, p0, rec, with_l1)
    except ValueError:
        pass
    best = None
    for o in (0, 1):
        rows = _rows_of(reference, spec, o)
        if rows is None:
            continue
        feet, land = _feet_of(reference, spec, o, rows)
        sig = _sigfeet_of(reference, spec, o)
        for hf, hdf, ldf in itertools.product((0, 1), repeat=3):
            p = _fit(reference, spec, o, hf, hdf, ldf, rows, feet, land, sig)
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
DEGRADE_MARGIN = 0.10  # covers the L1-versus-L2 disagreement of the ratio (module docstring)


class DegradeError(ValueError):
    """The degradation rule does not give a DRC-clean layout with the required L1 ratio."""


def degrade(twin_layout: Layout, spec: D.ReferenceSpec, with_l1: bool = True) -> tuple[Layout, dict]:
    """The frozen degradation rule of F1(b) applied to a twin built by ``derivative.build`` -> (D, record)."""
    p = D.params_of(twin_layout)
    seq = p.sequence()
    r = spec.rules
    margin = r.wire_landing_margin * 1e3 + 0.05
    slots, widths = list(p.slots), {}
    for i, (net, role, sw) in enumerate(seq):
        if role != "land":
            continue
        k = 0 if sw == "HS" else 1
        w0 = max(D._g_up(r.width_for(net) * 1e3), 1.0)
        v_end = p.land[k] + p.feet[k][5]
        # the narrowest band of width w0, w0 + 0.5, ... on the grid that holds the landing point by ``margin`` on both sides
        # (position: the lowest edge a = floor_grid(v_end - w / 2) + {0, -0.5, +0.5, ...} that fits)
        w, a = next((w, a) for w in (w0 + D.DESIGN_GRID_MM * i for i in range(12))
                    for a in (D._g_dn(v_end - w / 2) + D.DESIGN_GRID_MM * j for j in (0, -1, 1))
                    if v_end - a >= margin and a + w - v_end >= margin)
        old = slots[i]
        widths[f"{sw}_landing_{net}"] = {"before_mm": old[3] - old[1], "after_mm": w}
        slots[i] = (old[0], a, old[2], a + w)
    cols = []
    for net, c in zip(NETS, p.cols, strict=True):
        mine = [slots[i] for i, s in enumerate(seq) if s[0] == net]
        cols.append((c[0], min([c[1]] + [m[1] for m in mine]), c[2], max([c[3]] + [m[3] for m in mine])))
    pd = dataclasses.replace(p, slots=tuple(slots), cols=tuple(cols))
    try:
        lay = D.build(spec, pd)
    except ValueError as e:
        raise DegradeError(f"degraded layout cannot be built: {e}") from e
    viol = check(lay, r)
    if viol:
        raise DegradeError("degraded layout is not DRC-clean: " + "; ".join(str(v) for v in viol[:5]))
    rec = {"rule": "narrow every landing slot to the minimum width of its net", "widths": widths,
           "target_l1_ratio": DEGRADE_RATIO * (1.0 + DEGRADE_MARGIN), "margin": DEGRADE_MARGIN}
    if with_l1:
        rec["l1_twin_H"], rec["l1_degraded_H"] = _l1(twin_layout), _l1(lay)
        rec["l1_ratio"] = rec["l1_degraded_H"] / rec["l1_twin_H"]
        if rec["l1_ratio"] < rec["target_l1_ratio"]:
            raise DegradeError(f"L1 ratio {rec['l1_ratio']:.3f} < {rec['target_l1_ratio']:.3f}")
    return lay, rec
