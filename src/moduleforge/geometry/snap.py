"""Grid snapping of a Layout: the frozen rule of O003 scope_in (parameter grids of 0.5, 0.25 and 0.125 mm).

Rule (all lengths SI, grid ``g`` in m; the grid lines are the integer multiples of ``g`` in the layout frame):

* **Nearest grid line.** Every copper, outline (substrate and baseplate), terminal-pad and die-footprint edge moves to the
  nearest line, independently per axis: ``u = v / g``, ``k = floor(u + 1/2 + TIE_TOL)``, ``v' = k g``.
* **Ties** (``u`` exactly half-way between two lines, within ``TIE_TOL`` = 1e-9 cells of float noise) resolve to the
  *higher* line (round half toward +infinity) for every *vertex or rectangle edge* snap, both axes: rectilinear copper and
  outline vertices, terminal pads and die footprints. A coordinate within ``TIE_TOL`` cells of a line is on it. Hence the
  map is idempotent and a layout that is already on the grid is returned unchanged. **Staircased copper has a different tie
  rule**: an exactly half-covered cell is *in*, so a left or bottom edge exactly half-way between two lines goes to the
  LOWER line and a right or top edge to the UPPER line, i.e. ties round *outward* (the code is kept as implemented in T0257,
  because the cell-coverage rule is symmetric in the four directions, whereas "toward +infinity" would bias the copper
  toward +x/+y).
* **Rectilinear copper** (all edges axis-parallel, within 1 nm) snaps vertex by vertex, which moves each edge to the nearest
  line. **Non-rectilinear copper** is staircased: a grid cell belongs to the copper iff at least half of its area lies in the
  original polygon (a cell at exactly half is in). The area error is at most half a cell per boundary cell. Consequences of
  the cell rule: a convex rectilinear corner of a staircased polygon keeps its corner cell only if the covered area
  fraction there, the product of the two edges' covered fractions of the cell, is at least 1/2 (two edges 0.6 of a cell
  inside give 0.36, so the cell is dropped and the corner has a one-cell notch); and every cell cut exactly diagonally (45
  degree edges) is a tie and is in, so narrow 45 degree strips gain area.
* **Die footprints** snap edge by edge as a pure function of the die's own rectangle, so the same die at the same place gets
  the same footprint in the reference and in every candidate. Pads on a die (``Die.pads``) are not on the grid by design
  (they are ~0.7 x die size); a pad is only clipped to the snapped footprint when it would leave it.
* **Wire end points** keep their position unless the pad they sit on (landing copper of their net, or the die source pad at
  the start) no longer contains them, eroded by the same margin ``drc.check`` uses; then they move to the nearest point of
  that region. The points between follow linearly in index; z is untouched.
* **Record.** ``SnapRecord(element, before, after, displacement)`` for every coordinate or wire end point that moved by more than
  ``RECORD_TOL``. For edge snaps ``displacement`` is the largest per-axis move (<= g/2); for a staircased polygon it is the
  Hausdorff distance between the old and new boundary and ``kind == 'staircase'`` (can exceed g/2).
* **Re-check.** The full ``drc.check`` runs on the snapped layout under the caller's ``DesignRules`` and on the input;
  plus an explicit ``net_merged`` test (two nets' copper touching). Every violation of the snapped layout is returned as a
  ``SnapViolation`` labelled ``origin == 'induced'`` (no violation of the same rule and message, numbers aside, before
  snapping) or ``'pre-existing'`` (present before). Nothing is repaired. A feature (outline, trace, hole, terminal or die)
  that collapses to zero size or becomes invalid raises ValueError naming it. On the staircase path a hole that is filled
  raises ValueError naming the feature, and so does an outline or baseplate outline that splits into several parts (a
  trace that splits is reported as a ``net_split`` violation).
"""
from __future__ import annotations

import copy
import math
import re
from collections import Counter
from dataclasses import dataclass, replace

import numpy as np
import shapely
import shapely.errors
from shapely.geometry import MultiPolygon, Point, Polygon, box
from shapely.ops import nearest_points

from moduleforge.drc.rules import DEFAULT_RULES, DesignRules, Violation, check

from .layout import Layout, Terminal, Trace

GRIDS = (0.5e-3, 0.25e-3, 0.125e-3)  # m, the parameter grids of scope_in
TIE_TOL = 1e-9  # cells
RECORD_TOL = 1e-12  # m (1 pm): moves below this are float noise, not snaps
RECT_TOL = 1e-9  # m: an edge is axis-parallel when its other-axis extent is below this
CHECKED_RULES = ("min_spacing", "die_edge_margin", "die_off_trace", "die_wrong_net",
                 "net_split", "wire_pitch", "wire_length", "wire_landing_keepout")  # legacy subset; all rules are reported now
_NUM = re.compile(r"[-+]?\d+\.\d+e[-+]?\d+")


@dataclass(frozen=True)
class SnapViolation(Violation):
    origin: str = "induced"  # 'induced' (absent before snapping) | 'pre-existing' (present before)


@dataclass(frozen=True)
class SnapRecord:
    element: str
    before: tuple
    after: tuple
    displacement: float  # m
    kind: str = "edge"  # 'edge' | 'staircase' | 'clip' | 'wire'


@dataclass
class SnapResult:
    layout: Layout
    records: list[SnapRecord]
    violations: list[Violation]


def snap_value(v: float, g: float) -> float:
    """``v`` moved to the nearest multiple of ``g`` (ties to the higher line, see module docstring)."""
    return math.floor(v / g + 0.5 + TIE_TOL) * g


def _check_grid(g: float) -> None:
    if not any(abs(g - s) < 1e-12 for s in GRIDS):
        raise ValueError(f"grid must be one of {[s * 1e3 for s in GRIDS]} mm, got {g * 1e3} mm")


def _is_rectilinear(poly: Polygon) -> bool:
    for ring in (poly.exterior, *poly.interiors):
        c = np.asarray(ring.coords)
        d = np.abs(np.diff(c, axis=0))
        if np.any((d[:, 0] > RECT_TOL) & (d[:, 1] > RECT_TOL)):
            return False
    return True


def _snap_rect_polygon(poly: Polygon, g: float, name: str, rec: list[SnapRecord]) -> Polygon:
    def ring(r):
        out = []
        for x, y in r.coords:
            sx, sy = snap_value(x, g), snap_value(y, g)
            d = max(abs(sx - x), abs(sy - y))
            if d > RECORD_TOL and not any(q.element == name and q.before == (x, y) for q in rec):
                rec.append(SnapRecord(name, (x, y), (sx, sy), d))
            out.append((sx, sy))
        return out

    try:
        res = Polygon(ring(poly.exterior), [ring(i) for i in poly.interiors])
        res = shapely.remove_repeated_points(res)
    except (shapely.errors.GEOSException, ValueError) as e:  # a ring with < 3 distinct points: a feature collapsed
        raise ValueError(f"{name} (outline or a hole) collapses when snapped to {g * 1e3} mm: {e}") from e
    if res.is_empty or res.area <= 0 or not res.is_valid:
        raise ValueError(f"{name} collapses or becomes invalid when snapped to {g * 1e3} mm")
    return res


def _staircase(poly: Polygon, g: float, name: str, rec: list[SnapRecord], single_part: bool = False):
    """Cells with >= half their area inside ``poly``, merged into rectangles per row run."""
    x0, y0, x1, y1 = poly.bounds
    i0, i1 = math.floor(x0 / g), math.ceil(x1 / g)
    j0, j1 = math.floor(y0 / g), math.ceil(y1 / g)
    shapely.prepare(poly)
    rects = []
    for j in range(j0, j1):
        ii = np.arange(i0, i1)
        cells = shapely.box(ii * g, j * g, (ii + 1) * g, (j + 1) * g)
        frac = np.zeros(len(ii))
        inter = shapely.intersects(poly, cells)
        inner = shapely.contains_properly(poly, cells)
        frac[inner] = 1.0
        part = inter & ~inner
        if part.any():
            frac[part] = shapely.area(shapely.intersection(poly, cells[part])) / (g * g)
        inside = frac >= 0.5 - TIE_TOL
        k = 0
        while k < len(ii):
            if inside[k]:
                m = k
                while m + 1 < len(ii) and inside[m + 1]:
                    m += 1
                rects.append(box(ii[k] * g, j * g, (ii[m] + 1) * g, (j + 1) * g))
                k = m + 1
            else:
                k += 1
    if not rects:
        raise ValueError(f"{name} vanishes when staircased on {g * 1e3} mm")
    res = shapely.union_all(rects)
    for h, ring in enumerate(poly.interiors):  # filled: no part of the hole is left without copper
        if Polygon(ring).difference(res).area <= TIE_TOL * g * g:
            raise ValueError(f"{name}: hole {h} is filled when staircased on {g * 1e3} mm")
    if single_part and res.geom_type != "Polygon":
        raise ValueError(f"{name} splits into {len(res.geoms)} parts when staircased on {g * 1e3} mm")
    hd = shapely.hausdorff_distance(poly.boundary, res.boundary)
    rec.append(SnapRecord(name, (poly.area,), (res.area,), float(hd), "staircase"))
    return res


def _snap_polygon(poly, g: float, name: str, rec: list[SnapRecord], single_part: bool = False):
    if isinstance(poly, MultiPolygon):
        raise ValueError(f"{name} is a multi-part polygon")
    if _is_rectilinear(poly):
        return _snap_rect_polygon(poly, g, name, rec)
    return _staircase(poly, g, name, rec, single_part)


def _snap_rect(r, g: float, name: str, rec: list[SnapRecord]):
    """(x0, y0, x1, y1) with every edge moved to its nearest line; ValueError if a side collapses."""
    new = tuple(snap_value(v, g) for v in r)
    if new[2] <= new[0] or new[3] <= new[1]:
        raise ValueError(f"{name} collapses when snapped to {g * 1e3} mm")
    d = max(abs(a - b) for a, b in zip(new, r, strict=True))
    if d > RECORD_TOL:
        rec.append(SnapRecord(name, tuple(r), new, d))
    return new


def _move_into(region, x: float, y: float):
    p = Point(x, y)
    if region.buffer(1e-12).contains(p):
        return x, y
    q = nearest_points(region, p)[0]
    return float(q.x), float(q.y)


def _erode(poly, margin: float):
    e = poly.buffer(-margin, join_style="mitre", mitre_limit=10.0)
    return e if not e.is_empty else poly


def snap_layout(layout: Layout, grid: float, rules: DesignRules = DEFAULT_RULES) -> SnapResult:
    """Snap ``layout`` to ``grid`` [m] (0.5, 0.25 or 0.125 mm). The input is not modified."""
    _check_grid(grid)
    g = grid
    rec: list[SnapRecord] = []
    out = copy.deepcopy(layout)

    out.outline = _snap_polygon(layout.outline, g, "outline", rec, True)
    out.baseplate_outline = _snap_polygon(layout.baseplate_outline, g, "baseplate_outline", rec, True)
    out.traces = [Trace(t.net, _snap_polygon(t.polygon, g, f"trace[{i}] {t.net}", rec))
                  for i, t in enumerate(layout.traces)]

    for n, t in layout.terminals.items():
        x0, y0, x1, y1 = _snap_rect((t.cx - t.w / 2, t.cy - t.h / 2, t.cx + t.w / 2, t.cy + t.h / 2), g,
                                    f"terminal {n}", rec)
        out.terminals[n] = Terminal(t.net, (x0 + x1) / 2, (y0 + y1) / 2, x1 - x0, y1 - y0)

    for i, d in enumerate(layout.dies):
        x0, y0, x1, y1 = _snap_rect(d.bounds, g, f"die[{i}] {d.switch}", rec)
        nd = out.dies[i]
        nd.cx, nd.cy, nd.w, nd.h = (x0 + x1) / 2, (y0 + y1) / 2, x1 - x0, y1 - y0
        for name, p in d.pads.items():
            c = (max(p[0], x0), max(p[1], y0), min(p[2], x1), min(p[3], y1))
            if c != tuple(p):
                if c[2] <= c[0] or c[3] <= c[1]:
                    raise ValueError(f"die[{i}] pad {name} lies outside the snapped footprint")
                rec.append(SnapRecord(f"die[{i}] pad {name}", tuple(p), c, max(abs(a - b) for a, b in zip(c, p, strict=True)),
                                      "clip"))
                nd.pads[name] = c

    # wire end points: stay where they are while still on their pad, else the nearest point of it
    for k, w in enumerate(layout.wires):
        pts = np.array(w.points, dtype=float)
        ends = []
        for idx in (0, -1):
            x, y = pts[idx, 0], pts[idx, 1]
            if idx == 0:
                owner = [i for i, d in enumerate(layout.dies)
                         if "source" in d.pads and box(*d.pads["source"]).buffer(1e-9).contains(Point(x, y))]
                region = (_erode(box(*out.dies[owner[0]].pads["source"]), max(rules.wire_start_margin, w.diameter / 2))
                          if owner else None)
            else:
                cu = shapely.union_all([t.polygon for t in out.traces if t.net == w.net])
                region = _erode(cu, rules.wire_landing_margin) if not cu.is_empty else None
            ends.append((x, y) if region is None else _move_into(region, x, y))
        d0 = np.array(ends[0]) - pts[0, :2]
        d1 = np.array(ends[1]) - pts[-1, :2]
        if max(np.abs(d0).max(), np.abs(d1).max()) > RECORD_TOL:
            t = np.linspace(0.0, 1.0, len(pts))[:, None]
            out.wires[k].points = pts.copy()
            out.wires[k].points[:, :2] += (1 - t) * d0 + t * d1
            for idx, dd, e in ((0, d0, ends[0]), (-1, d1, ends[1])):
                if np.abs(dd).max() > RECORD_TOL:
                    rec.append(SnapRecord(f"wire[{k}] {'start' if idx == 0 else 'end'}",
                                          (float(pts[idx, 0]), float(pts[idx, 1])), e, float(np.hypot(*dd)), "wire"))

    before = Counter(_key(v) for v in _full_check(layout, rules))
    viol = []
    for v in _full_check(out, rules):
        k = _key(v)
        pre = before[k] > 0
        if pre:
            before[k] -= 1
        viol.append(SnapViolation(v.rule, v.message, v.where, "pre-existing" if pre else "induced"))
    return SnapResult(replace(out), rec, viol)


def _key(v: Violation) -> tuple[str, str]:
    return v.rule, _NUM.sub("#", v.message)


def _full_check(lay: Layout, rules: DesignRules) -> list[Violation]:
    """``drc.check`` plus ``net_merged`` (two nets' copper touching)."""
    viol = list(check(lay, rules))
    for i in range(len(lay.traces)):
        for j in range(i + 1, len(lay.traces)):
            a, b = lay.traces[i], lay.traces[j]
            if a.net != b.net and a.polygon.distance(b.polygon) <= 0.0:
                pt = a.polygon.representative_point()
                viol.append(Violation("net_merged", f"traces {i} ({a.net}) and {j} ({b.net}) touch", (float(pt.x), float(pt.y))))
    return viol
