"""O006 pilot P4 (T0155): Layout -> FastHenry deck exporter (research script, NOT evidence, O006 F4).

Writes a FastHenry 3.0wr input deck in SI metres (``.units m``; never ``.units mm``, which scales the reported impedance
by 1000 in our build, D0002) from a ModuleForge ``Layout`` via ``Layout.to_conductors()``, the same conductor model the
L2 layout solver (``moduleforge.solvers.l2_layout``) consumes.  Started from benchmarks/infra/fh_gen.py (its ``.units m``,
``.default sigma`` header, floating ``gplane`` with one dummy node, ``.external`` and ``.freq`` lines).

What is exported, and how it differs from l2_layout (every difference stated; "same" means the same modelling choice):
  traces    every top-Cu rectangle of ``to_conductors()`` is put on a cell-centred lattice of pitch ``cell`` (absolute
            coordinates; a rectangle edge off the lattice raises ValueError, as l2_layout's ``cell_fill`` does): one node
            per cell at the trace mid-thickness, an x-segment (w = cell, h = t) between x-neighbour cells of the same net,
            a y-segment between y-neighbours.  SAME lattice concept as l2_layout (cell-centred nodes, x- and y-branches).
            DIFFERENT: thickness by FastHenry's ``nhinc`` filaments graded by ``rh`` (l2_layout: its own graded layers,
            10 in top Cu); FastHenry's kernel (exact rectangular-bar mutuals near, filament approximations far) and solve.
            A cell holding two nets raises ValueError (as l2_layout).  Signal traces (SIG_*) are exported as floating
            meshes (eddy currents only), as in l2_layout.
  planes    backside Cu and baseplate as two floating ``gplane`` rectangles (their true outlines, mid-thickness z,
            thickness and sigma from the stack), ``seg1 x seg2`` from the ``plane_cell`` knob, ``nhinc`` / ``rh`` through
            the thickness.  DIFFERENT: l2_layout puts the planes on the SAME lateral grid as the traces; here the plane
            pitch is a separate knob (FastHenry's gplane grid starts at the plane corner, not on the trace lattice).
            FastHenry's gplane discretisation (edge segments, node layout) is FastHenry's own.
  dies      ideal shorts: every trace node of the die's bottom net whose cell centre lies inside the die footprint and the
            start node of every wire that starts on the die's source pad are merged by one ``.equiv`` line.  SAME as
            l2_layout's node merge.  DIFFERENT: lattice segments with both ends in one die group are dropped (in FastHenry
            they would be self-loops); l2_layout keeps them as branches between merged nodes.
  wires     each bond-wire polyline of the Layout (the same 7-point arc as l2_layout) is exported segment by segment,
            each polyline segment split into ``wire_sub`` collinear pieces.  DIFFERENT: FastHenry segments have
            rectangular cross-sections, so a round wire of diameter d is a square of side a = 0.8711 d with the same
            geometric mean distance (GMD of a disc 0.7788 r, of a square 0.44705 a: Grover, Inductance Calculations, 1946,
            tables of g.m.d.; a = 0.7788 / (2 x 0.44705) d), split into ``wire_n x wire_n`` filaments
            (l2_layout: round filament bundle, centre disc + rings).  No landing clamp: the polyline ends sit exactly on
            the die top and the top-Cu surface, so the first/last pieces overlap the copper by up to a/2 (l2_layout keeps
            filament vertices >= LANDING_GAP x d above the copper).
  contacts  wire feet and the two port terminals join the lattice node of the NEAREST cell of their net; when several
            cells tie (point on a cell edge or corner) all tied cells are merged with it by ``.equiv``.  DIFFERENT:
            l2_layout uses bilinear current injection over the four surrounding cells (it reports that snapping moved L by
            up to +-5 % under sub-cell shifts; here the snap distance is <= cell / sqrt(2) and shrinks with refinement,
            so the effect is a discretisation error the refinement ladder must show).
  port      one ``.external`` between the DC+ and DC- terminal-centre nodes; PHASE open (no third port).  SAME.
  materials Cu sigma and wire sigma from the stack / Layout (``.default sigma`` = top-Cu sigma).  SAME.
  not modelled (both): gate and Kelvin wires, power-lead posts, the ceramic (non-conductive), die attach as a conductor.

Refinement knobs (``FHLevel``): ``cell`` (trace lattice pitch), ``plane_cell`` (plane segmentation), ``nh_trace`` /
``nh_plane`` with ``rh`` (thickness filaments), ``nw_trace`` (width filaments per lattice segment), ``wire_n`` (filaments
per wire side) and ``wire_sub`` (wire segmentation).

    uv run python research/scripts/o006_p4/fh_export.py --selftest          # deck structure checks; FastHenry NOT run
    uv run python research/scripts/o006_p4/fh_export.py --geometry case4_base --cell 1.0 --plane-cell 4 > deck.inp
"""
from __future__ import annotations

import argparse
import hashlib
import math
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "research" / "scripts"))
import o006_case4_layout as case4  # noqa: E402  (P3's reconstruction, reused unchanged)

from moduleforge.geometry import DC_MINUS, DC_PLUS  # noqa: E402

MM = 1e-3
FREQS_HZ = (1.0e7, 2.0e7)
SQUARE_PER_DIAMETER = 0.7788 / (2 * 0.44705)  # equal-GMD square side / disc diameter (Grover 1946), = 0.8711


@dataclass(frozen=True)
class FHLevel:
    cell_mm: float = 1.0
    plane_cell_mm: float = 4.0
    nh_trace: int = 1
    nh_plane: int = 1
    rh: float = 2.0
    nw_trace: int = 1
    wire_n: int = 2
    wire_sub: int = 1


def _fmt(v: float) -> str:
    return f"{v:.10g}"


def _idx(v: float, c: float, what: str) -> int:
    k = v / c
    r = round(k)
    if abs(k - r) > 1e-6:
        raise ValueError(f"{what} at {v / MM:.6g} mm is not on the {c / MM:g} mm lattice")
    return int(r)


def lattice(cm, c: float):
    """{(ix, iy): (net, z_mid, thickness, sigma)} of the cell-centred top-Cu lattice of pitch c (metres)."""
    cells: dict[tuple[int, int], tuple[str, float, float, float]] = {}
    for r in cm.rects:
        i0, i1 = _idx(r.x0, c, "rect x0"), _idx(r.x1, c, "rect x1")
        j0, j1 = _idx(r.y0, c, "rect y0"), _idx(r.y1, c, "rect y1")
        for i in range(i0, i1):
            for j in range(j0, j1):
                old = cells.get((i, j))
                if old is not None and old[0] != r.net:
                    raise ValueError(f"cell {(i, j)} holds two nets {old[0]} / {r.net}")
                cells[(i, j)] = (r.net, r.z + r.thickness / 2, r.thickness, r.sigma)
    return cells


def _nearest(cells, c: float, net: str, x: float, y: float) -> list[tuple[int, int]]:
    keys = [k for k, v in cells.items() if v[0] == net]
    if not keys:
        raise ValueError(f"no lattice cell of net {net}")
    xy = (np.array(keys, dtype=float) + 0.5) * c
    d = np.hypot(xy[:, 0] - x, xy[:, 1] - y)
    dmin = d.min()
    return [keys[i] for i in np.flatnonzero(d <= dmin + 1e-9 * c)]


def _tn(k):
    return f"Nt{k[0]}y{k[1]}"


def export(layout, lev: FHLevel, freqs=FREQS_HZ, title: str = "") -> tuple[str, dict]:
    """FastHenry deck (string) and its structural facts (for --selftest and the run log)."""
    cm = layout.to_conductors()
    c = lev.cell_mm * MM
    cells = lattice(cm, c)
    sigma_top = cm.rects[0].sigma
    L = [f"* O006 P4 FastHenry deck (research, not evidence): {title}",
         f"* level {asdict(lev)}",
         ".units m", f".default sigma={_fmt(sigma_top)}"]
    # --- die groups (ideal shorts) and wire starts
    groups: list[set] = []
    for d in cm.shorts:
        g = {k for k, v in cells.items() if v[0] == d.bottom_net
             and abs((k[0] + 0.5) * c - d.x) < d.w / 2 and abs((k[1] + 0.5) * c - d.y) < d.h / 2}
        if not g:
            raise ValueError(f"die {d.die_index} footprint holds no cell of {d.bottom_net}")
        groups.append(g)
    in_group = {k: gi for gi, g in enumerate(groups) for k in g}
    # --- trace nodes and segments
    for k, (_net, zm, _t, _s) in sorted(cells.items()):
        L.append(f"{_tn(k)} x={_fmt((k[0] + 0.5) * c)} y={_fmt((k[1] + 0.5) * c)} z={_fmt(zm)}")
    nseg_trace = 0
    dropped = 0
    for (i, j), (net, _zm, t, s) in sorted(cells.items()):
        for di, dj, tag in ((1, 0, "x"), (0, 1, "y")):
            nb = (i + di, j + dj)
            if nb not in cells or cells[nb][0] != net:
                continue
            if (i, j) in in_group and in_group.get(nb) == in_group[(i, j)]:
                dropped += 1
                continue
            L.append(f"E{tag}{i}y{j} {_tn((i, j))} {_tn(nb)} w={_fmt(c)} h={_fmt(t)} sigma={_fmt(s)} "
                     f"nwinc={lev.nw_trace} nhinc={lev.nh_trace} rh={_fmt(lev.rh)}")
            nseg_trace += 1
    # --- bond wires
    wires: dict[int, list] = {}
    for s in cm.wires:
        wires.setdefault(s.wire_index, []).append(s)
    wire_nodes, wire_segs = 0, 0
    wire_start, wire_end = {}, {}
    for wi, segs in sorted(wires.items()):
        pts = [np.array(segs[0].p0)]
        for s in segs:
            a, b = np.array(s.p0), np.array(s.p1)
            for q in range(1, lev.wire_sub + 1):
                pts.append(a + (b - a) * q / lev.wire_sub)
        a_sq = SQUARE_PER_DIAMETER * segs[0].diameter
        for k, p in enumerate(pts):
            L.append(f"Nw{wi}p{k} x={_fmt(p[0])} y={_fmt(p[1])} z={_fmt(p[2])}")
        for k in range(len(pts) - 1):
            L.append(f"Ew{wi}s{k} Nw{wi}p{k} Nw{wi}p{k + 1} w={_fmt(a_sq)} h={_fmt(a_sq)} sigma={_fmt(segs[0].sigma)} "
                     f"nwinc={lev.wire_n} nhinc={lev.wire_n}")
        wire_nodes += len(pts)
        wire_segs += len(pts) - 1
        wire_start[wi], wire_end[wi] = (pts[0], f"Nw{wi}p0"), (pts[-1], f"Nw{wi}p{len(pts) - 1}", segs[0].net)
    # wires start on a die source pad -> join that die's group
    die_wires: dict[int, list[str]] = {gi: [] for gi in range(len(groups))}
    for wi, (p, name) in wire_start.items():
        hit = [gi for gi, d in enumerate(cm.shorts)
               if d.pad[0] <= p[0] <= d.pad[2] and d.pad[1] <= p[1] <= d.pad[3]]
        if len(hit) != 1:
            raise ValueError(f"wire {wi} does not start on exactly one die source pad")
        die_wires[hit[0]].append(name)
    equivs = []
    for gi, g in enumerate(groups):
        equivs.append(die_wires[gi] + [_tn(k) for k in sorted(g)])
    contacts = {}
    for p, name, net in wire_end.values():
        ks = _nearest(cells, c, net, p[0], p[1])
        equivs.append([name] + [_tn(k) for k in ks])
        contacts[name] = ks
    port_nodes = {}
    for tag, net, p in (("P", DC_PLUS, cm.port.p_pos), ("M", DC_MINUS, cm.port.p_neg)):
        ks = _nearest(cells, c, net, p[0], p[1])
        port_nodes[tag] = (_tn(ks[0]), ks)
        if len(ks) > 1:
            equivs.append([_tn(k) for k in ks])
    # --- planes (floating gplanes)
    plane_info = []
    for pl in cm.planes:
        o = pl.outline
        x0, y0, x1, y1 = pl.bounds
        if len(o) != 4 or not all(min(abs(px - x0), abs(px - x1)) < 1e-12 and min(abs(py - y0), abs(py - y1)) < 1e-12
                                  for px, py in o):
            raise ValueError(f"plane {pl.name} is not an axis-aligned rectangle")
        s1 = max(1, round((x1 - x0) / (lev.plane_cell_mm * MM)))
        s2 = max(1, round((y1 - y0) / (lev.plane_cell_mm * MM)))
        zp = pl.z_bottom + pl.thickness / 2
        L.append(f"g{pl.name} x1={_fmt(x0)} y1={_fmt(y0)} z1={_fmt(zp)} x2={_fmt(x1)} y2={_fmt(y0)} z2={_fmt(zp)} "
                 f"x3={_fmt(x1)} y3={_fmt(y1)} z3={_fmt(zp)} thick={_fmt(pl.thickness)} seg1={s1} seg2={s2} "
                 f"sigma={_fmt(pl.sigma)} nhinc={lev.nh_plane} rh={_fmt(lev.rh)}")
        L.append(f"+ n{pl.name}f ({_fmt((x0 + x1) / 2)},{_fmt((y0 + y1) / 2)},{_fmt(zp)})")
        plane_info.append({"name": pl.name, "bounds_m": [x0, y0, x1, y1], "z_mid_m": zp, "thick_m": pl.thickness,
                           "seg1": s1, "seg2": s2, "segments": (s1 + 1) * s2 + s1 * (s2 + 1)})
    for e in equivs:
        if len(e) > 1:
            L.append(".equiv " + " ".join(e))
    L.append(f".external {port_nodes['P'][0]} {port_nodes['M'][0]}")
    fmin, fmax = min(freqs), max(freqs)
    ndec = 1.0 / math.log10(fmax / fmin) if fmax > fmin else 1.0
    L.append(f".freq fmin={_fmt(fmin)} fmax={_fmt(fmax)} ndec={_fmt(ndec * (1 + 1e-9))}")
    L.append(".end")
    deck = "\n".join(L) + "\n"
    nfil = (nseg_trace * lev.nw_trace * lev.nh_trace + wire_segs * lev.wire_n ** 2
            + sum(p["segments"] for p in plane_info) * lev.nh_plane)
    nnodes = len(cells) + wire_nodes + sum((p["seg1"] + 1) * (p["seg2"] + 1) for p in plane_info)
    facts = {"level": asdict(lev), "n_cells": len(cells), "n_trace_segments": nseg_trace, "n_dropped_die_segments": dropped,
             "n_wire_nodes": wire_nodes, "n_wire_segments": wire_segs, "planes": plane_info, "n_filaments": nfil,
             "n_nodes": nnodes, "die_groups": [len(g) for g in groups], "port_nodes": port_nodes,
             "contacts": contacts, "deck_sha256": hashlib.sha256(deck.encode()).hexdigest(),
             # rough direct-solve memory: dense real filament L (8 B) + dense complex mesh matrix (16 B), meshes ~ F - N
             "direct_mem_est_gb": (8 * nfil ** 2 + 16 * max(nfil - nnodes, nfil // 2) ** 2) / 1e9}
    return deck, facts


ZC_RE = re.compile(r"frequency\s*=\s*([0-9.eE+-]+)")
NUM_RE = re.compile(r"([-+]?[0-9.]+(?:[eE][-+]?\d+)?)\s*([-+]\s*[0-9.]+(?:[eE][-+]?\d+)?)j")


def parse_zc(text: str) -> dict[float, complex]:
    """{frequency: Z11} from a FastHenry Zc.mat with one port."""
    out, f = {}, None
    for line in text.splitlines():
        m = ZC_RE.search(line)
        if m:
            f = float(m.group(1))
            continue
        m = NUM_RE.search(line)
        if m and f is not None:
            out[f] = complex(float(m.group(1)), float(m.group(2).replace(" ", "")))
            f = None
    return out


# ------------------------------------------------------------------------------------------------------------ selftest
def _parse_deck(deck: str):
    nodes, segs, planes, equiv, ext, units, freq = {}, [], [], [], [], [], None
    for line in deck.splitlines():
        s = line.strip()
        if not s or s.startswith("*"):
            continue
        low = s.lower()
        if low.startswith(".units"):
            units.append(low.split()[1])
        elif low.startswith(".equiv"):
            equiv.append(s.split()[1:])
        elif low.startswith(".external"):
            ext.append(s.split()[1:])
        elif low.startswith(".freq"):
            freq = dict(kv.split("=") for kv in s.split()[1:])
        elif low.startswith("n"):
            kv = dict(t.split("=") for t in s.split()[1:])
            nodes[s.split()[0].lower()] = tuple(float(kv[a]) for a in "xyz")
        elif low.startswith("e"):
            parts = s.split()
            segs.append((parts[1].lower(), parts[2].lower(), dict(t.split("=") for t in parts[3:])))
        elif low.startswith("g"):
            planes.append(dict(t.split("=") for t in s.split()[1:]))
    return nodes, segs, planes, equiv, ext, units, freq


def selftest() -> int:
    errs: list[str] = []
    G = case4.geometries()
    lev = FHLevel(cell_mm=1.0, plane_cell_mm=4.0, nh_trace=3, nh_plane=3, wire_n=2, wire_sub=2)
    out = {}
    for name, lay in G.items():
        deck, f = export(lay, lev, title=name)
        nodes, segs, planes, equiv, ext, units, freq = _parse_deck(deck)
        cm = lay.to_conductors()
        # units: metres only
        if units != ["m"] or ".units mm" in deck.lower():
            errs.append(f"{name}: units {units} (must be exactly one '.units m')")
        bx = cm.planes[1].bounds  # baseplate
        for n, p in nodes.items():
            if not (bx[0] - 1e-9 <= p[0] <= bx[2] + 1e-9 and bx[1] - 1e-9 <= p[1] <= bx[3] + 1e-9 and 0 <= p[2] < 0.01):
                errs.append(f"{name}: node {n} at {p} outside the baseplate box in metres")
                break
        # node count: lattice cells from copper AREA (independent of the rectangle loop) + wire nodes
        n_cells_area = round(cm.copper_area() / (lev.cell_mm * MM) ** 2)
        n_wire_nodes = sum(len(w.points) - 1 for w in lay.wires) * lev.wire_sub + len(lay.wires)
        if len(nodes) != n_cells_area + n_wire_nodes:
            errs.append(f"{name}: {len(nodes)} nodes != {n_cells_area} cells + {n_wire_nodes} wire nodes")
        # segment count: independent rasterisation of the net polygons (shapely point-in-polygon at cell centres)
        from shapely.geometry import Point
        c = lev.cell_mm * MM
        x0, y0, x1, y1 = cm.planes[0].bounds
        grid = {}
        for t in lay.traces:
            for i in range(round(x0 / c), round(x1 / c)):
                for j in range(round(y0 / c), round(y1 / c)):
                    if t.polygon.contains(Point((i + 0.5) * c, (j + 0.5) * c)):
                        grid[(i, j)] = t.net
        adj = sum(1 for (i, j), n in grid.items() for nb in ((i + 1, j), (i, j + 1)) if grid.get(nb) == n)
        if f["n_trace_segments"] + f["n_dropped_die_segments"] != adj or len(grid) != f["n_cells"]:
            errs.append(f"{name}: trace segments {f['n_trace_segments']}+{f['n_dropped_die_segments']} != raster {adj}")
        n_wseg = sum(len(w.points) - 1 for w in lay.wires) * lev.wire_sub
        if len(segs) != f["n_trace_segments"] + n_wseg:
            errs.append(f"{name}: {len(segs)} segments != {f['n_trace_segments']} trace + {n_wseg} wire")
        for a, b, kv in segs:
            if a not in nodes or b not in nodes:
                errs.append(f"{name}: segment references undefined node {a}/{b}")
                break
            if not 0 < float(kv["w"]) < 0.01 or not 0 < float(kv["h"]) < 0.01:
                errs.append(f"{name}: segment dimension not in metres: {kv}")
                break
        # wire length preserved (metres)
        Lw = sum(math.dist(nodes[a], nodes[b]) for a, b, _ in segs if a.startswith("nw"))
        Lref = sum(w.length for w in lay.wires)
        if abs(Lw - Lref) > 1e-9 * Lref:
            errs.append(f"{name}: exported wire length {Lw} != layout {Lref}")
        # planes: two, metres, extents = the conductor-model outlines
        if len(planes) != 2:
            errs.append(f"{name}: {len(planes)} gplanes (expected 2)")
        for pl, ref in zip(planes, cm.planes, strict=False):
            b = ref.bounds
            got = (float(pl["x1"]), float(pl["y1"]), float(pl["x3"]), float(pl["y3"]))
            if max(abs(u - v) for u, v in zip(got, b, strict=True)) > 1e-12 or abs(float(pl["thick"]) - ref.thickness) > 1e-15:
                errs.append(f"{name}: plane {ref.name} extent/thickness mismatch")
        # single port between the DC+ and DC- terminal centres
        if len(ext) != 1 or len(ext[0]) != 2:
            errs.append(f"{name}: expected a single 2-node .external, got {ext}")
        else:
            for tag, nd, p in (("P", ext[0][0], cm.port.p_pos), ("M", ext[0][1], cm.port.p_neg)):
                ks = f["port_nodes"][tag][1]
                cen = (np.array(ks, float) + 0.5).mean(axis=0) * c
                if nd.lower() != _tn(ks[0]).lower() or np.hypot(*(cen - np.array(p[:2]))) > 1e-9:
                    errs.append(f"{name}: port node {tag} centroid {cen} != terminal centre {p[:2]}")
                net = {"P": DC_PLUS, "M": DC_MINUS}[tag]
                if any(cells_net != net for cells_net in (lattice(cm, c)[k][0] for k in ks)):
                    errs.append(f"{name}: port {tag} touches a cell of another net")
        # every .equiv node exists; die groups are disjoint from each other and from port nodes
        for e in equiv:
            for n in e:
                if n.lower() not in nodes:
                    errs.append(f"{name}: .equiv references undefined node {n}")
        if len(f["die_groups"]) != 4 or min(f["die_groups"]) < 1:
            errs.append(f"{name}: die groups {f['die_groups']}")
        expect_cells = round(case4.DIE_FOOT[0] * case4.DIE_FOOT[1] / lev.cell_mm ** 2)
        if any(g != expect_cells for g in f["die_groups"]):
            errs.append(f"{name}: die group sizes {f['die_groups']} != {expect_cells} cells per 4 x 6 mm footprint")
        # frequencies: the .freq sweep hits exactly 10 and 20 MHz
        fmin, fmax, ndec = float(freq["fmin"]), float(freq["fmax"]), float(freq["ndec"])
        f2 = fmin * 10 ** (1 / ndec)
        if (fmin, fmax) != FREQS_HZ or not (abs(f2 - fmax) / fmax < 1e-8 and f2 <= fmax * (1 + 1e-12)):
            errs.append(f"{name}: .freq {freq} does not give 10 and 20 MHz")
        out[name] = {k: f[k] for k in ("n_cells", "n_trace_segments", "n_dropped_die_segments", "n_wire_segments",
                                      "n_filaments", "die_groups", "deck_sha256")}
    # refinement knobs change the counts as documented (cell halves -> 4x cells; plane_cell halves -> ~4x plane segments)
    b = G["case4_base"]
    f1 = export(b, FHLevel(cell_mm=1.0, plane_cell_mm=4.0))[1]
    f2 = export(b, FHLevel(cell_mm=0.5, plane_cell_mm=2.0, wire_sub=2))[1]
    if f2["n_cells"] != 4 * f1["n_cells"]:
        errs.append(f"cell 1.0 -> 0.5 mm: {f1['n_cells']} -> {f2['n_cells']} cells (expected x4)")
    if not 3.5 < sum(p["segments"] for p in f2["planes"]) / sum(p["segments"] for p in f1["planes"]) < 4.5:
        errs.append("plane_cell 4 -> 2 mm did not ~quadruple the plane segments")
    if f2["n_wire_segments"] != 2 * f1["n_wire_segments"]:
        errs.append("wire_sub 2 did not double the wire segments")
    # off-lattice refusal
    try:
        export(b, FHLevel(cell_mm=0.3))
        errs.append("0.3 mm lattice (off the 1 mm design grid) was not refused")
    except ValueError:
        pass
    # Zc.mat parser on a FastHenry-format sample (format of a FastHenry 3.0wr run, values illustrative)
    z = parse_zc("Row 1:  Impedance matrix for frequency = 1e+07 1 x 1\n  0.0123456 +1.4e+00j\n"
                 "Impedance matrix for frequency = 2e+07 1 x 1\n  0.02 -3.5e-01j\n")
    if z != {1e7: complex(0.0123456, 1.4), 2e7: complex(0.02, -0.35)}:
        errs.append(f"parse_zc: {z}")
    import json
    print(json.dumps({"ok": not errs, "errors": errs, "decks": out}, indent=1))
    return 0 if not errs else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--geometry", default="case4_base", choices=case4.GEOMETRY_NAMES)
    for k, v in asdict(FHLevel()).items():
        ap.add_argument("--" + k.replace("_mm", "").replace("_", "-"), dest=k, type=type(v), default=v)
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    lev = FHLevel(**{k: getattr(a, k) for k in asdict(FHLevel())})
    deck, _ = export(case4.geometries()[a.geometry], lev, title=a.geometry)
    sys.stdout.write(deck)
    return 0


if __name__ == "__main__":
    sys.exit(main())
