"""Layout -> FastHenry deck exporter (O004, D0002): the independent-solver side of the L2 cross-check.

Ported from ``research/scripts/o006_p4/fh_export.py`` (O006 pilot P4, T0155) and generalised from Case 4 to any ``Layout``.
Deliberate changes from P4 (none alters P4's Case 4 decks, tests/unit/test_fasthenry.py): the lattice origin is l2_layout's;
wire ends follow l2_layout's ``end_contact`` rule (P4 required every start on a die pad and joined every end to a trace);
``.equiv`` groups longer than ``MAX_LINE`` are split over several lines (P4 wrote one line per group, which FastHenry
refuses at 0.25 mm; P4's decks have no line over 900 characters); die footprints are checked against the lattice; the F6
variants ``die_model='distributed'`` and ``terminal_model='tab'``.
Writes a FastHenry 3.0wr input deck in SI metres (``.units m``; never ``.units mm``, which scales the reported impedance by
1000 in our build, D0002) from ``Layout.to_conductors()``, the conductor model that ``moduleforge.solvers.l2_layout``
consumes.  This module never runs FastHenry and freezes no refinement level (E004 freezes them); it only writes decks.

Deck frame: ``.units m``; ``.default sigma`` = top-Cu conductivity; ``.freq fmin=1e7 fmax=2e7`` with ``ndec`` chosen so the
sweep hits exactly 10 and 20 MHz; one ``.external`` between the DC+ and DC- terminal nodes, PHASE open (no third port).
Every line is at most ``MAX_LINE`` = 900 characters: FastHenry 3.0wr refuses input lines of about 1000 characters or more
(review T0408), so an ``.equiv`` group too long for one line (a die's footprint at 0.25 mm: 384 cells) is written as several
``.equiv`` lines that all start with the group's first node, which keeps the group one equivalence class (``equiv_lines``).
Checked with the provisioned FastHenry 3.0wr (sha256 eaa6d6fc...2d14, research/o006_p4/binary_check.json), T0384: the
0.25 mm decks (plane 2 mm) of Case 4, 2D_Case_2R and 2D_Case_6, default, tab and distributed, all read (``-f simple``,
exit 0), while the same Case 4 deck with each group rejoined onto one line (3852 characters) is refused (exit 1); P4's d0
deck with its groups split at 60 characters gives the unsplit deck's Zc.mat to every printed digit.

What is exported, and how it differs from l2_layout (every difference stated; "same" means the same modelling choice):
  traces    every top-Cu rectangle of ``to_conductors()`` is put on a cell-centred lattice of pitch ``cell_mm``.  The lattice
            ORIGIN is l2_layout's: the lower-left corner of the bounding box of the baseplate and the top-Cu rectangles
            (``l2_layout.layout_lattice``), so for equal pitch both tools use the same absolute cell edges.  A rectangle edge
            off the lattice raises ValueError, as l2_layout's ``cell_fill`` does.  One node per cell at the trace
            mid-thickness, an x-segment (w = cell, h = t) between x-neighbour cells of the same net, a y-segment between
            y-neighbours.  SAME lattice concept as l2_layout (cell-centred nodes, x- and y-branches).  DIFFERENT: thickness
            by FastHenry's ``nhinc`` filaments graded by ``rh`` (``nh_trace``; l2_layout: its own graded layers, 10 in top
            Cu) and ``nwinc`` width filaments per segment (``nw_trace``); FastHenry's kernel (exact rectangular-bar mutuals
            near, filament approximations far) and solve.  A cell holding two nets raises ValueError (as l2_layout).  Signal
            traces (SIG_*) are exported as floating meshes (eddy currents only), as in l2_layout.
  planes    backside Cu and baseplate as two floating ``gplane`` rectangles (their true outlines, mid-thickness z, thickness
            and sigma from the stack), ``seg1 x seg2`` from the SEPARATE pitch ``plane_cell_mm`` (E004's coarsest level may
            use <= 2 mm, F7(a)), ``nh_plane`` filaments graded by ``rh`` through the thickness.  DIFFERENT: l2_layout puts
            the planes on the same lateral grid as the traces; here the plane grid starts at the plane corner, not on the
            trace lattice, and its discretisation (edge segments, node layout) is FastHenry's own.  A non-rectangular plane
            raises ValueError.
  dies      DEFAULT ``die_model='short'``: ideal shorts, every trace node of the die's bottom net whose cell centre lies
            inside the die footprint and the start node of every wire that starts on the die's source pad are merged by one
            ``.equiv`` line, and so is any other wire end that lands on the die (``l2_layout.end_contact``'s rule: inside
            the footprint, at or above the die top).  The die footprint must lie on the lattice (ValueError otherwise,
            l2_layout's ``check_on_lattice``), and the net's cell nearest the die centre is added to the group (l2_layout's
            ``_nearest_cell``; already in the footprint for a die over its own net).  SAME as l2_layout's node merge.
            DIFFERENT: lattice segments with both ends in one die group are dropped (in FastHenry they would be
            self-loops); l2_layout keeps them as branches between merged nodes.
            VARIANT ``die_model='distributed'`` (O004's F6 diagnostic; NOT what E004's verdict uses): the footprint is no
            longer one node.  The die and its attach are a conductor block of the footprint and the stack thicknesses
            (``DieShort.z_top - DieShort.z_bottom`` = attach + die, from the Layout's stack), meshed as PEEC volume cells
            with cell-centred nodes, the convention the traces use: one block node per footprint cell at (cell centre,
            block mid-plane (z_bottom + z_top) / 2); lateral x/y segments (w = cell, h = block thickness, so their
            cross-section fills exactly [z_bottom, z_top]) between neighbouring block nodes; one vertical column of
            cross-section cell x cell per footprint cell from the drain-cell node of the trace (trace mid-thickness) up to
            the block node.  The block thus conducts in all three directions.  The footprint's trace cells are NOT merged
            and the lattice segments under the die are kept.  Each wire end on the die joins the block node of the footprint
            cell nearest to it (ties merged), instead of the whole footprint; the half block between the die top, where
            the wire starts, and the mid-plane is thereby an ideal short, as the half trace between the Cu surface and a
            trace node is for every wire foot.  All block nodes of a die are written before its segments (FastHenry reads
            the deck in one pass and refuses a segment naming a node not yet read).  The block's conductivity is ``die_sigma`` (default: the top-Cu
            sigma, i.e. a metal block; the stack's SiC die has sigma = 0 because the L2 models treat it as a short, so a
            semiconductor value would be an invention).  Model basis: PEEC volume-cell meshing of a conductor block (Ruehli,
            IEEE Trans. MTT 22 (1974) 216) with the partial inductance of the block carried by FastHenry's bar mutuals
            (Kamon, Tsuk, White, IEEE Trans. MTT 42 (1994) 1750).  The mesh is coarse by construction: each column
            overlaps the upper half of its trace cell and the lower half of the block, where the lateral segments also run
            (volume counted twice, a small error for a 0.18-0.23 mm block on a >= 0.25 mm lattice); the vertical path of
            the wire current is tb / 2 + t / 2 of column instead of tb + t / 2.  The diagnostic measures the size of the
            ideal-short assumption, not the die's own physics; with the default metal sigma it is a lower bound on the
            lateral resistance of a real die (review T0404: report a lower ``die_sigma`` as a sensitivity; ``die_sigma``
            must be finite and > 0).  The block, column and post segments carry no ``nwinc`` / ``nhinc``: one filament
            each at every level, so the variant refines only laterally, through ``cell_mm`` (review T0408).
            Solver limit (review T0409, not a deck error): FastHenry 3.0wr's multipole solver segfaulted on the Case 4
            distributed deck at cell 1 mm / plane 4 mm, the direct solver solved it; ``facts['solver_notes']`` says so
            for every distributed deck: use the direct solver, i.e. a level coarse enough for a dense solve.
  wires     each bond-wire polyline of the Layout (the same 7-point arc as l2_layout) is exported segment by segment, each
            polyline segment split into ``wire_sub`` collinear pieces.  DIFFERENT: FastHenry segments have rectangular
            cross-sections, so a round wire of diameter d is a square of side a = 0.8711 d with the same geometric mean
            distance (GMD of a disc 0.7788 r, of a square 0.44705 a: Grover, Inductance Calculations, 1946, tables of
            g.m.d.; a = 0.7788 / (2 x 0.44705) d), split into ``wire_n x wire_n`` filaments (``nwinc = nhinc = wire_n``;
            l2_layout: round filament bundle, centre disc + rings).  The wire cross-section thus refines with the traces.
            No landing clamp: the polyline ends sit exactly on the die top and the top-Cu surface, so the first / last
            pieces overlap the copper by up to a/2 (l2_layout keeps filament vertices >= LANDING_GAP x d above the copper).
  contacts  wire ends that do not land on a die (normally the feet) and the two port terminals join the lattice node of the
            NEAREST cell of their net (for a wire: its landing net, as l2_layout's ``contact_at``); when several cells tie
            (point on a cell edge or corner) all tied cells are merged with it by ``.equiv``.  The lattice segments between
            tied cells are KEPT, unlike the die-group segments: their two ends are one node, so each is a zero-voltage loop
            that carries only induced current (FastHenry solves such decks; P4 ran Case 4 with 8 of them).  The count is
            ``facts['n_shorted_segments']`` (it includes Ed segments between tied die-block nodes).  DIFFERENT: l2_layout
            uses bilinear current injection over the four surrounding cells (it reports that snapping moved L by up to
            +-5 % under sub-cell shifts; here the snap distance is <= cell / sqrt(2) and shrinks with refinement, so the
            effect is a discretisation error the refinement ladder must show).
            VARIANT ``terminal_model='tab'`` (F6): each port terminal is the top of a physical post of the terminal
            footprint (``Layout.terminals[net]`` w x h, or ``TabSpec.w/h``) and height ``TabSpec.height`` (default 2 mm:
            T0263's power_lead.part is 3 x 3 mm with a 2 mm post).  The post is one copper column of cross-section
            cell x cell per lattice cell of the terminal's net whose centre lies under the footprint, from that cell's
            node up to a post-top node at (cell centre, top-Cu surface + height); the post-top nodes are merged by one
            ``.equiv`` group (the lead top is one equipotential) and the ``.external`` node is the first of them.  The
            footprint must lie on the lattice (ValueError otherwise, the die-footprint rule).  The foot
            cells are not merged, so the current spreads through the trace copper into the post.  Same PEEC-block basis
            and mesh caveats as the die block; sigma = top-Cu sigma.  The post's own bulk is not meshed laterally.
            Solver limit (review T0405, not a deck error): with 2 mm posts and ``plane_cell_mm`` = 4, FastHenry 3.0wr's
            multipole solver warned 'DivideSegs' and segfaulted, while the direct solver and multipole at 2 mm solved the
            deck; ``facts['solver_notes']`` says so when the combination is exported.
  port      one ``.external`` between the DC+ and DC- terminal nodes; PHASE open (no third port).  SAME.
  materials Cu sigma and wire sigma from the stack / Layout (``.default sigma`` = top-Cu sigma).  SAME.
  not modelled (both): gate and Kelvin wires, power-lead posts (unless ``terminal_model='tab'``), the ceramic (non
            conductive), die attach as a conductor (unless ``die_model='distributed'``).
  not modelled (here only): L2's layer-resolved current redistribution inside the traces is FastHenry's ``nhinc`` ladder
            instead; no proximity-effect guarantee beyond what the chosen ``nh_*`` / ``rh`` resolve.

Refinement knobs (``FHLevel``): ``cell_mm`` (trace lattice pitch), ``plane_cell_mm`` (plane segmentation), ``nh_trace`` /
``nh_plane`` with ``rh`` (thickness filaments and their grading ratio, so the 3 / 5 / 9 ladder is ``nh_*`` = 3, 5, 9),
``nw_trace`` (width filaments per lattice segment), ``wire_n`` (filaments per wire side) and ``wire_sub`` (wire pieces per
polyline segment).  No level is frozen here.

    from moduleforge.solvers.fasthenry import FHLevel, export
    deck, facts = export(layout, FHLevel(cell_mm=0.5, plane_cell_mm=2.0, nh_trace=5, nh_plane=5, wire_n=3, wire_sub=2))
"""
from __future__ import annotations

import hashlib
import math
import numbers
import re
from dataclasses import asdict, dataclass

import numpy as np

from moduleforge.geometry import DC_MINUS, DC_PLUS

MM = 1e-3
FREQS_HZ = (1.0e7, 2.0e7)
SQUARE_PER_DIAMETER = 0.7788 / (2 * 0.44705)  # equal-GMD square side / disc diameter (Grover 1946), = 0.8711
DIE_MODELS = ("short", "distributed")
TERMINAL_MODELS = ("point", "tab")
# FastHenry 3.0wr reads input lines of about 1000 characters at most: review T0408 found single '.equiv' lines of <= 969
# characters accepted and >= 1209 refused ('line may be too long', 'What is the following line?', exit 1).  Every line this
# module writes is at most MAX_LINE characters: long '.equiv' groups are split (``equiv_lines``), anything else raises.
MAX_LINE = 900


@dataclass(frozen=True)
class FHLevel:
    """Refinement level.  ``nh_trace = nh_plane = 1`` (the defaults) is a SMOKE-TEST level only: one filament through the
    thickness is strongly biased on thin-ceramic stacks (+24 % against l2_layout on a generated layout, about +8 % on Case 4,
    review T0417); judge nothing at nh = 1, use the 3 / 5 / 9 ladder."""

    cell_mm: float = 1.0
    plane_cell_mm: float = 4.0
    nh_trace: int = 1
    nh_plane: int = 1
    rh: float = 2.0
    nw_trace: int = 1
    wire_n: int = 2
    wire_sub: int = 1

    def __post_init__(self):
        for k in ("cell_mm", "plane_cell_mm", "rh"):
            v = getattr(self, k)
            if isinstance(v, bool) or not isinstance(v, numbers.Real) or not math.isfinite(v) or v <= 0:
                raise ValueError(f"{k} must be a finite positive number, got {v!r}")
            object.__setattr__(self, k, float(v))  # plain float: the deck text does not depend on the caller's type
        for k in ("nh_trace", "nh_plane", "nw_trace", "wire_n", "wire_sub"):
            v = getattr(self, k)  # a float or bool would leak into the deck ('nhinc=3.0') or break range() (review T0409)
            if isinstance(v, bool) or not isinstance(v, numbers.Integral) or v < 1:
                raise ValueError(f"{k} must be a positive int (not a bool or float), got {v!r}")
            object.__setattr__(self, k, int(v))


@dataclass(frozen=True)
class TabSpec:
    """Terminal post of ``terminal_model='tab'``: footprint ``w`` x ``h`` [m] (None: the Layout's ``Terminal``) and ``height`` [m]."""

    w: float | None = None
    h: float | None = None
    height: float = 2.0e-3  # T0263: power_lead.part post height 2 mm


def _fmt(v: float) -> str:
    return f"{v:.10g}"


def lattice_origin(cm) -> tuple[float, float]:
    """Lower-left corner of the lattice: the one of ``l2_layout.layout_lattice`` (bbox of baseplate and top-Cu rectangles)."""
    bp = {p.name: p for p in cm.planes}["baseplate"]
    xmin, ymin, _, _ = bp.bounds
    for r in cm.rects:
        xmin, ymin = min(xmin, r.x0), min(ymin, r.y0)
    return float(xmin), float(ymin)


def _idx(v: float, o: float, c: float, what: str) -> int:
    k = (v - o) / c
    r = round(k)
    if abs(k - r) > 1e-6:
        raise ValueError(f"{what} at {v / MM:.6g} mm is not on the {c / MM:g} mm lattice")
    return int(r)


def lattice(cm, c: float, origin: tuple[float, float] | None = None):
    """{(ix, iy): (net, z_mid, thickness, sigma)} of the cell-centred top-Cu lattice of pitch c (metres)."""
    ox, oy = origin if origin is not None else lattice_origin(cm)
    cells: dict[tuple[int, int], tuple[str, float, float, float]] = {}
    for r in cm.rects:
        i0, i1 = _idx(r.x0, ox, c, "rect x0"), _idx(r.x1, ox, c, "rect x1")
        j0, j1 = _idx(r.y0, oy, c, "rect y0"), _idx(r.y1, oy, c, "rect y1")
        for i in range(i0, i1):
            for j in range(j0, j1):
                old = cells.get((i, j))
                if old is not None and old[0] != r.net:
                    raise ValueError(f"cell {(i, j)} holds two nets {old[0]} / {r.net}")
                cells[(i, j)] = (r.net, r.z + r.thickness / 2, r.thickness, r.sigma)
    return cells


def _centre(k, c, origin):
    return origin[0] + (k[0] + 0.5) * c, origin[1] + (k[1] + 0.5) * c


def _nearest(cells, c: float, origin, net: str, x: float, y: float, keys=None) -> list[tuple[int, int]]:
    keys = keys if keys is not None else [k for k, v in cells.items() if v[0] == net]
    if not keys:
        raise ValueError(f"no lattice cell of net {net}")
    xy = (np.array(keys, dtype=float) + 0.5) * c + np.array(origin)
    d = np.hypot(xy[:, 0] - x, xy[:, 1] - y)
    dmin = d.min()
    return [keys[i] for i in np.flatnonzero(d <= dmin + 1e-9 * c)]


def _tn(k):
    return f"Nt{k[0]}y{k[1]}"


def _dn(gi, k):
    return f"Nd{gi}i{k[0]}y{k[1]}"


def _on_die(shorts, p) -> int | None:
    """Index of the first die whose footprint holds the wire end p at or above its top surface (``l2_layout.end_contact``)."""
    for gi, d in enumerate(shorts):
        if abs(p[0] - d.x) <= d.w / 2 and abs(p[1] - d.y) <= d.h / 2 and p[2] >= d.z_top - 1e-9:
            return gi
    return None


def _shorted_segments(lines: list[str], equivs: list[list[str]]) -> int:
    """Number of segments whose two nodes lie in one ``.equiv`` class (zero-voltage loops; see the module docstring)."""
    parent: dict[str, str] = {}

    def find(a):
        parent.setdefault(a, a)
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for e in equivs:
        for n in e[1:]:
            parent[find(n)] = find(e[0])
    n = 0
    for ln in lines:
        if ln.startswith("E"):
            a, b = ln.split()[1:3]
            n += a in parent and b in parent and find(a) == find(b)
    return n


def _footprint_cells(cells, c, origin, net, cx, cy, w, h, what: str):
    """Cells of ``net`` under the footprint (centre cx, cy; size w x h).  ValueError unless the footprint's edges lie on the
    lattice (l2_layout's ``check_on_lattice`` for die footprints; the same rule here for tab footprints), so every cell is
    either fully inside or fully outside and the strict test on cell centres has no ties."""
    for v, o, edge in ((cx - w / 2, origin[0], "x0"), (cx + w / 2, origin[0], "x1"), (cy - h / 2, origin[1], "y0"),
                       (cy + h / 2, origin[1], "y1")):
        _idx(v, o, c, f"{what} footprint edge {edge}")
    return sorted(k for k, v in cells.items() if v[0] == net
                  and abs(_centre(k, c, origin)[0] - cx) < w / 2 and abs(_centre(k, c, origin)[1] - cy) < h / 2)


def equiv_lines(names: list[str], max_line: int = MAX_LINE) -> list[str]:
    """``.equiv`` lines merging ``names`` into one node, each at most ``max_line`` characters.  Every line starts with the
    group's first node, so the lines chain into one equivalence class (FastHenry 3.0wr's line limit, see MAX_LINE; review
    T0408 checked that a 400-name group split this way gives the impedance of the unsplit one)."""
    if len(names) < 2:
        return []
    head = ".equiv " + names[0]
    out: list[str] = []
    cur = head
    for n in names[1:]:
        if len(head) + 1 + len(n) > max_line:
            raise ValueError(f"node names {names[0]!r} / {n!r} do not fit on one {max_line}-character .equiv line")
        if len(cur) + 1 + len(n) > max_line:
            out.append(cur)
            cur = head
        cur += " " + n
    out.append(cur)
    return out


def export(layout, lev: FHLevel, freqs=FREQS_HZ, title: str = "", *, die_model: str = "short",
           terminal_model: str = "point", tab: TabSpec | None = None, die_sigma: float | None = None) -> tuple[str, dict]:
    """FastHenry deck (string) and its structural facts (counts, node names, sha256) for the Layout at level ``lev``.

    ``die_model`` in ``DIE_MODELS``, ``terminal_model`` in ``TERMINAL_MODELS`` (see the module docstring); ``tab`` only
    matters for ``terminal_model='tab'``; ``die_sigma`` only for ``die_model='distributed'``.  Deterministic: same input,
    same text.  ValueError for an off-lattice rectangle, die footprint or tab footprint, a cell holding two nets, a die
    whose net has no cell (``die_model='distributed'``: no cell under its footprint), a tab footprint without a cell, a
    wire end off the dies whose net has no cell, a non-rectangular plane, a ``die_sigma`` that is not a finite positive
    number, a multi-line ``title``, or a deck line longer than ``MAX_LINE`` (only a long ``title`` can cause that)."""
    if die_sigma is not None and (isinstance(die_sigma, bool) or not isinstance(die_sigma, numbers.Real)
                                  or not math.isfinite(die_sigma) or die_sigma <= 0):
        raise ValueError(f"die_sigma must be None or a finite positive conductivity [S/m], got {die_sigma!r}")
    if "\n" in title or "\r" in title:
        raise ValueError("title must be one line")
    if die_model not in DIE_MODELS:
        raise ValueError(f"die_model must be one of {DIE_MODELS}")
    if terminal_model not in TERMINAL_MODELS:
        raise ValueError(f"terminal_model must be one of {TERMINAL_MODELS}")
    cm = layout.to_conductors()
    c = lev.cell_mm * MM
    origin = lattice_origin(cm)
    cells = lattice(cm, c, origin)
    sigma_top = cm.rects[0].sigma
    distributed = die_model == "distributed"
    L = [f"* ModuleForge FastHenry deck {title}",
         f"* level {asdict(lev)} die_model={die_model} terminal_model={terminal_model}",
         ".units m", f".default sigma={_fmt(sigma_top)}"]
    # --- die groups (footprint cells of the bottom net)
    groups: list[set] = []
    for d in cm.shorts:
        g = set(_footprint_cells(cells, c, origin, d.bottom_net, d.x, d.y, d.w, d.h, f"die {d.die_index}"))
        if distributed:
            if not g:
                raise ValueError(f"die {d.die_index} footprint holds no cell of {d.bottom_net}: no block to mesh")
        elif any(v[0] == d.bottom_net for v in cells.values()):
            # l2_layout also adds the net's cell nearest the die centre (its _nearest_cell: first of ties in (i, j) order);
            # for a die over its own net that cell is already in the footprint
            g.add(sorted(_nearest(cells, c, origin, d.bottom_net, d.x, d.y))[0])
        else:
            raise ValueError(f"die {d.die_index}: no trace cell of its net {d.bottom_net}")
        groups.append(g)
    in_group = {k: gi for gi, g in enumerate(groups) for k in g}
    # --- trace nodes and segments
    for k, (_net, zm, _t, _s) in sorted(cells.items()):
        x, y = _centre(k, c, origin)
        L.append(f"{_tn(k)} x={_fmt(x)} y={_fmt(y)} z={_fmt(zm)}")
    nseg_trace = 0
    dropped = 0
    for (i, j), (net, _zm, t, s) in sorted(cells.items()):
        for di, dj, tag in ((1, 0, "x"), (0, 1, "y")):
            nb = (i + di, j + dj)
            if nb not in cells or cells[nb][0] != net:
                continue
            if not distributed and (i, j) in in_group and in_group.get(nb) == in_group[(i, j)]:
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
    wire_ends: list[tuple[tuple[np.ndarray, str], tuple[np.ndarray, str], str]] = []
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
        wire_ends.append(((pts[0], f"Nw{wi}p0"), (pts[-1], f"Nw{wi}p{len(pts) - 1}"), segs[0].net))
    # --- wire ends -> the die they land on (l2_layout.end_contact's rule), else a trace contact of the wire's net
    die_wires: dict[int, list[tuple[np.ndarray, str]]] = {gi: [] for gi in range(len(groups))}
    trace_ends: list[tuple[np.ndarray, str, str]] = []
    for start, end, net in wire_ends:
        for p, name in (start, end):
            gi = _on_die(cm.shorts, p)
            if gi is None:
                trace_ends.append((p, name, net))
            else:
                die_wires[gi].append((p, name))
    equivs: list[list[str]] = []
    n_block_nodes = n_block_segs = 0
    nfil_block = 0
    if not distributed:
        for gi, g in enumerate(groups):
            equivs.append([n for _, n in die_wires[gi]] + [_tn(k) for k in sorted(g)])
    else:
        sig_d = sigma_top if die_sigma is None else die_sigma
        for gi, (d, g) in enumerate(zip(cm.shorts, groups, strict=True)):
            tb = d.z_top - d.z_bottom
            zb = d.z_bottom + tb / 2  # block mid-plane: the lateral segments (h = tb) then fill exactly [z_bottom, z_top]
            ks = sorted(g)
            # every node of the block first: FastHenry reads the deck in one pass, a segment may only name nodes read before
            for k in ks:
                x, y = _centre(k, c, origin)
                L.append(f"{_dn(gi, k)} x={_fmt(x)} y={_fmt(y)} z={_fmt(zb)}")
                n_block_nodes += 1
            for k in ks:
                L.append(f"Ev{gi}i{k[0]}y{k[1]} {_tn(k)} {_dn(gi, k)} w={_fmt(c)} h={_fmt(c)} sigma={_fmt(sig_d)} "
                         f"wx=1 wy=0 wz=0")
                n_block_segs += 1
                nfil_block += 1
                for di, dj, tag in ((1, 0, "x"), (0, 1, "y")):
                    nb = (k[0] + di, k[1] + dj)
                    if nb in g:
                        L.append(f"Ed{tag}{gi}i{k[0]}y{k[1]} {_dn(gi, k)} {_dn(gi, nb)} w={_fmt(c)} h={_fmt(tb)} "
                                 f"sigma={_fmt(sig_d)}")
                        n_block_segs += 1
                        nfil_block += 1
            for p, name in die_wires[gi]:
                kn = _nearest(cells, c, origin, d.bottom_net, p[0], p[1], keys=ks)
                equivs.append([name] + [_dn(gi, k) for k in kn])
    contacts = {}
    for p, name, net in trace_ends:
        ks = _nearest(cells, c, origin, net, p[0], p[1])
        equivs.append([name] + [_tn(k) for k in ks])
        contacts[name] = ks
    port_nodes = {}
    tab_cells: dict[str, list] = {}
    for tag, net, p, term in (("P", DC_PLUS, cm.port.p_pos, layout.terminals[DC_PLUS]),
                              ("M", DC_MINUS, cm.port.p_neg, layout.terminals[DC_MINUS])):
        if terminal_model == "point":
            ks = _nearest(cells, c, origin, net, p[0], p[1])
            port_nodes[tag] = (_tn(ks[0]), ks)
            if len(ks) > 1:
                equivs.append([_tn(k) for k in ks])
        else:
            spec = tab or TabSpec()
            tw = spec.w if spec.w is not None else term.w
            th = spec.h if spec.h is not None else term.h
            ks = _footprint_cells(cells, c, origin, net, term.cx, term.cy, tw, th, f"terminal {net} tab")
            if not ks:
                raise ValueError(f"terminal {net} footprint holds no cell of the net")
            z_top = max(cells[k][1] + cells[k][2] / 2 for k in ks) + spec.height
            names = []
            for k in ks:
                x, y = _centre(k, c, origin)
                L.append(f"Nq{tag}i{k[0]}y{k[1]} x={_fmt(x)} y={_fmt(y)} z={_fmt(z_top)}")
                L.append(f"Eq{tag}i{k[0]}y{k[1]} {_tn(k)} Nq{tag}i{k[0]}y{k[1]} w={_fmt(c)} h={_fmt(c)} "
                         f"sigma={_fmt(cells[k][3])} wx=1 wy=0 wz=0")
                names.append(f"Nq{tag}i{k[0]}y{k[1]}")
                n_block_nodes += 1
                n_block_segs += 1
                nfil_block += 1
            equivs.append(names)
            port_nodes[tag] = (names[0], ks)
            tab_cells[tag] = ks
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
        L.extend(equiv_lines(e))
    L.append(f".external {port_nodes['P'][0]} {port_nodes['M'][0]}")
    if len(freqs) > 2:  # the .freq line holds a decade sweep between min and max: middle entries would be dropped (review T0418)
        raise ValueError(f"freqs must hold at most two frequencies (fmin, fmax), got {len(freqs)}")
    fmin, fmax = min(freqs), max(freqs)
    ndec = 1.0 / math.log10(fmax / fmin) if fmax > fmin else 1.0
    L.append(f".freq fmin={_fmt(fmin)} fmax={_fmt(fmax)} ndec={_fmt(ndec * (1 + 1e-9))}")
    L.append(".end")
    too_long = [ln[:40] for ln in L if len(ln) > MAX_LINE]
    if too_long:
        raise ValueError(f"{len(too_long)} deck line(s) longer than {MAX_LINE} characters (FastHenry 3.0wr refuses them), "
                         f"first: {too_long[0]!r}...")
    deck = "\n".join(L) + "\n"
    nfil = (nseg_trace * lev.nw_trace * lev.nh_trace + wire_segs * lev.wire_n ** 2
            + sum(p["segments"] for p in plane_info) * lev.nh_plane + nfil_block)
    nnodes = len(cells) + wire_nodes + n_block_nodes + sum((p["seg1"] + 1) * (p["seg2"] + 1) for p in plane_info)
    notes = []
    if terminal_model == "tab" and lev.plane_cell_mm > 2.0:
        notes.append("tab posts with plane_cell_mm > 2: FastHenry 3.0wr's multipole solver segfaulted on such a deck "
                     "(DivideSegs on a plane segment, review T0405); use plane_cell_mm <= 2 or the direct solver")
    if distributed:
        notes.append("die_model='distributed': FastHenry 3.0wr's multipole solver (-s iterative -m multi) segfaulted (rc -11, "
                     "after 'Forming sparse matrix preconditioner', no Zc.mat) on the Case 4 deck at cell 1 mm / plane 4 mm "
                     "with the default Cu die_sigma, while the direct solver solved it (review T0409); solve this variant "
                     "with the direct solver (-s ludecomp -m direct), i.e. at a level coarse enough for a dense solve "
                     "(~15-20k filaments on 16 GB, P4), and never parse Zc.mat from a crashed run (D0002)")
    area: dict[str, float] = {}
    for v in cells.values():
        area[v[0]] = area.get(v[0], 0.0) + c * c
    facts = {"level": asdict(lev), "die_model": die_model, "terminal_model": terminal_model, "origin_m": list(origin),
             "n_cells": len(cells), "trace_area_m2": area, "n_trace_segments": nseg_trace,
             "n_dropped_die_segments": dropped, "n_wire_nodes": wire_nodes, "n_wire_segments": wire_segs,
             "n_block_nodes": n_block_nodes, "n_block_segments": n_block_segs, "planes": plane_info,
             "n_filaments": nfil, "n_nodes": nnodes, "die_groups": [len(g) for g in groups], "port_nodes": port_nodes,
             "tab_cells": tab_cells, "contacts": contacts, "n_shorted_segments": _shorted_segments(L, equivs),
             "solver_notes": notes, "deck_sha256": hashlib.sha256(deck.encode()).hexdigest(),
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
