"""Independent scikit-fem (trilinear or triquadratic hexahedra) thermal cross-check of a Layout (D0006 fallback, docs/thermal_model.md).

This module implements ``docs/thermal_model.md`` on its own: it builds its own conforming hexahedral mesh, materials and
boundary conditions straight from the ``Layout`` and its ``LayerStack`` and runs its own Picard loop. It must never import
the finite-volume solver or its layout/grid builder (task A3 independence); it only reads ``moduleforge.geometry``.

Method. Steady ``div(k(x,T) grad T) = 0`` in the solid Omega; uniform flux ``q_i = P_i / (w_i h_i)`` over each die top
face; Robin sink ``k dT/dz = h (T - T_c)`` on the whole baseplate bottom; everything else adiabatic (natural BC).
Galerkin with hexahedra of ``GridRule.element_order``: 1 = trilinear (scikit-fem ``ElementHex1``, 2x2x2 Gauss points,
the default) or 2 = triquadratic (``ElementHex2``, 27 nodes, 3x3x3 Gauss points). ``k`` is evaluated at the quadrature
points from the previous Picard iterate (lagged; Picard fixed point = the continuum solution). Linear systems are solved
by CG preconditioned with algebraic multigrid (pyamg, MIT), warm-started from the previous iterate: smoothed aggregation
for Q1 (as before); for Q2 a p-multigrid whose first coarse level is the Q1 space of the same mesh, with the constant
mode deflated (``_Solver``; smoothed aggregation on the Q2 matrix itself stalled at weak Robin coupling, T0205 review).

Why the quadrature is exact (axis-aligned boxes, constant ``k`` per element). The mesh cells and faces are axis-aligned
boxes, so the isoparametric map is affine and diagonal. In ``dT_i/dx_a dT_j/dx_a`` of two Q_p basis functions the
derivative along ``a`` has degree p-1 and the other two directions keep degree p, so the integrand has degree 2(p-1) in
direction ``a`` and 2p in the other two: 2 (p = 1) and 4 (p = 2), at most 2p. An n-point Gauss rule is exact to degree
2n-1: n = 2 gives 3 >= 2 for Q1 and n = 3 gives 5 >= 4 for Q2 (Abramowitz & Stegun 25.4.29; Ciarlet, 1978, sec. 4.1). The
Robin face mass is a product of two basis functions on a rectangle (degree 2p per direction, 4 for Q2) and the
source-face and sink-face integrals of one basis function are lower: the 3x3 face rule used there is exact too. With
``k`` varying inside an element the rule is a consistent quadrature (the lagged-k Picard scheme is defined by it). Every
face integral (scikit-fem ``FacetBasis``) is restricted to the dofs of its faces, which removes the 1e-15 round-off
values that the inverse-mapped face quadrature gives basis functions vanishing on the face (``_restrict``).

Manufactured data (optional, ``solve_layout`` / ``solve_box_stack``). ``source(x, y, z)`` [W/m3] is integrated over the
volume, ``flux(x, y, z, axis, sign)`` [W/m2] (heat into the domain, ``(axis, sign)`` the outward normal) over every
exterior and void-bounding face except the Robin face z = 0, and ``T_inf(x, y)`` [K] replaces the scalar coolant
temperature in ``h (T - T_inf)``. They are evaluated at 4x4x4 (volume) and 4x4 (face) Gauss points of every cell and
face (``DATA_INTORDER`` = 7, exact to degree 7 per direction; chunked like the stiffness). The weak form is
``int k grad T . grad v + int_sink h T v = int q v + int_faces g v + int_sink h T_inf v``; taking ``v = 1`` (in both
spaces) gives ``Q_out = int_sink h (T - T_inf) dS = Q_in`` exactly, with ``Q_in`` the *assembled* die, volume and face
loads, and ``energy_balance = |Q_out / Q_in - 1|`` is computed against that sum. It therefore checks the linear solve
and the bookkeeping of the loads, NOT the data quadrature, the face selection or the sign of the flux: for any data it is
zero up to the solver residual. Those are checked by comparing ``q_in_volume_W`` and ``q_in_boundary_W`` with
independently integrated values (tests/unit/solvers/test_thermal_fem_assembly.py) and ``q_out_W`` with O006's frozen
integral of the manufactured case.

Mesh (own rule). Grid lines (x, y, z) pass through every die, die-attach, top-Cu, backside-Cu (inset), ceramic and
baseplate edge and every layer interface, so every edge of every region is a mesh edge: the mesh conforms exactly and a
cell is wholly in one region. A cell belongs to a region when its centre does (void cells are dropped, their faces are
natural adiabatic boundaries). Refinement rule (``GridRule``): the interval between two neighbouring lines of length L
gets the smallest even number >= ``L / h0`` of cells in x and y (even, so that every interval midpoint, where a
symmetric die's surface maximum sits, is a node at every level), and each layer ``nz[layer]`` cells in z, at level 0;
level l has ``2**l`` times as many cells in every lateral interval (and in z too when ``zrefine`` is True, the default),
so the *refinement ratio is a constant r = 2* (cell sizes halve exactly) over the three levels 0, 1, 2 used for the grid
convergence index. With ``near_margin`` set, the lateral size is ``h0`` within that distance of a die (along the
axis), 2 ``h0`` out to three margins and 4 ``h0`` beyond (the same multipliers at every level). The benchmark (A3) uses ``zrefine=False``: z is held at counts whose error was measured separately
(a lateral-only study, the same pattern as the layout EM benchmark), because refining z too puts the finest level beyond
memory (see "Memory").

Outputs per die (section 5 of the definition): ``Tj_max`` = maximum nodal temperature over exactly the nodes of the die
top face (the dofs of its faces: vertices, and for Q2 also edge midpoints and face centres; the nodal FEM reads the
continuous surface field directly) and ``Tj_mean`` = area mean of T over the die top face (Galerkin integral), plus the
energy balance ``|Q_out / Q_in - 1|`` (exact up to the linear-solver tolerance for a Galerkin system whose stiffness rows
sum to zero, see above) and the Picard residual.

GCI: the order-capped rule of O006 A4 (D0012, D0013 and its addenda), shared with the finite-volume solver through
``thermal_layout.gci_three_grid`` (Roache 1998, ch. 5 for the safety factors 1.25 and 3, oscillatory, and the form
``|d2| / (2**p - 1)``; order capped at 1; grid steps below 1e-3 K count as zero; ``+inf`` for a divergent or stagnant
sequence). With f1, f2, f3 the finest, middle and coarsest values, the arguments of that function are (f3, f2, f1).

Memory, Q2 (T0205). The stiffness is assembled in element chunks (4000 elements for Q2, 20000 for Q1 per scikit-fem
basis, partial matrices summed by a binary tree), so the peak is the CSR matrix, the multigrid hierarchy and one chunk's
basis tables (about 23 kB per Q2 element), not all elements' tables. The bases are rebuilt at every Picard iteration (no
tables are kept between iterations). Measured on this Mac (whole-process peak RSS ``ru_maxrss``, k(T), 5 Picard
iterations, ``solve_layout`` on the generator layout side_by_side/6 of benchmarks/thermal_fem_convergence.py, T0205
attempt 2): Q2 8.1 kB/DOF at 57 k DOF (0.47 GB, 5 s), 4.5 kB at 416 k (1.9 GB, 45 s), 4.8 kB at 719 k (3.5 GB, 75 s);
attempt 1 measured 9.9 kB/DOF at 60 k on a three-layer box stack. ``BYTES_PER_DOF_BY_ORDER[2]`` = 10 kB is the upper bound
of those figures (the small-mesh figures are dominated by the fixed Python/numpy baseline). Q1 on the same 416 k DOF:
4.4 kB/DOF (1.8 GB, 34 s) chunked, against 7.6 kB/DOF (3.1 GB, 18 s) for the earlier version that kept one basis of all
elements: chunking costs Q1 about 1.8 times the wall time for 42 % less memory. Most of that time, growing as N^2 /
chunk, was whole-mesh work that scikit-fem repeats for every chunk's basis: the global split inside ``interpolate``
(avoided by ``_interpolate``) and the global DOF coordinates every basis computes unless built with
``disable_doflocs=True``, as all bases here are (2026-11-04, 1.7 M elements, per chunk: 0.38 s against 0.001 s and 0.48
s against 0.022 s; the values are unchanged). ``estimate_dofs`` counts the Q2 dofs
(vertices, edges, faces and cells of the active cells); at equal DOF a Q2 mesh has 8 times fewer cells.

Memory, Q1. D0006 estimated about 7.7 kB per DOF for scikit-fem + pyamg; ``max_dofs(budget_bytes)`` converts a budget into
the largest DOF count at that figure. On the 17.2 GB Apple-silicon laptop that built this, with 70 % of RAM (12.0 GB) as
the budget for one solve, that is 1.56 million DOF. Measured by ``benchmarks/thermal_fem_convergence.py`` (peak RSS of
the child process, whole-process including the Python and numpy baseline, two runs): 8-9 kB/DOF at 0.06-0.1 M DOF, about
7.5 kB/DOF at 0.25-0.4 M and 4.4-6.5 kB/DOF at 0.9-1.5 M (up to 6.5 GB), so the D0006 figure of 7.7 kB is a fair upper bound
and is what is used; the benchmark nevertheless skips a level whose estimate at 7.7 kB/DOF exceeds the budget (status ``skipped: memory``).
Grid convergence index of the benchmark layouts: see the module docstring of the benchmark and its JSON; on this machine the
finest affordable level (about 1.5 M DOF, lateral cells of 0.125 mm within 1.5 mm of a die) does NOT reach the A3
threshold of 0.025 K for every die (observed order 0.6-1.7, GCI 0.03-0.15 K), because the Tj error is dominated by
lateral spreading in the 0.3 mm copper films and near the die perimeters; the threshold needs a finer finest level than
this Mac can hold (burst VM per D0006).
"""
from __future__ import annotations

import math
import os
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

import numpy as np
import pyamg
import scipy.sparse as sp
import shapely
from pyamg.multilevel import MultilevelSolver
from pyamg.relaxation.smoothing import change_smoothers
from shapely.geometry import Polygon
from skfem import BilinearForm, CellBasis, ElementHex1, ElementHex2, FacetBasis, LinearForm, MeshHex
from skfem.assembly import Dofs
from skfem.helpers import dot, grad
from skfem.mapping import MappingIsoparametric

from moduleforge.geometry.layout import Layout
from moduleforge.geometry.stack import Layer
from moduleforge.solvers.thermal_layout import gci_three_grid

MM = 1.0e3  # the mesh is built in millimetres: k [W/(m K)] -> 1e-3 W/(mm K), h -> 1e-6 W/(mm2 K), areas in mm2
BYTES_PER_DOF = 7.7e3  # D0006 audit figure for scikit-fem + pyamg (Q1); the benchmark records the measured value
BYTES_PER_DOF_BY_ORDER = {1: BYTES_PER_DOF, 2: 10.0e3}  # whole-process peak RSS per DOF, see "Memory"
DATA_INTORDER = 7  # quadrature of manufactured data: 4x4x4 / 4x4 Gauss points (exact to degree 7 per direction)
PICARD_TOL_K = 1.0e-4  # stop when max |dT| of an iteration is below this [K]
LINEAR_RTOL = 1.0e-11  # relative residual of every AMG-CG solve
CG_MAXITER = 400  # iteration cap of every AMG-CG solve
REFINEMENT_RATIO = 2  # constant r of the three-level study
LEVELS = (0, 1, 2)
_HEX_CORNERS = ((0, 0, 0), (0, 1, 0), (1, 0, 0), (0, 0, 1), (1, 1, 0), (0, 1, 1), (1, 0, 1), (1, 1, 1))  # skfem order


def max_dofs(budget_bytes: float, bytes_per_dof: float | None = None, element_order: int = 1) -> int:
    """Largest DOF count whose estimated memory fits ``budget_bytes``: ``bytes_per_dof`` each, by default the figure of
    ``element_order`` (``BYTES_PER_DOF_BY_ORDER``; 7.7 kB for Q1)."""
    if bytes_per_dof is None:
        bytes_per_dof = BYTES_PER_DOF_BY_ORDER[element_order]
    return int(budget_bytes // bytes_per_dof)


def physical_memory_bytes() -> float:
    return float(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES"))


# ------------------------------------------------------------------------------------------------ result container
@dataclass
class ThermalResult:
    """Solution summary. Temperatures in K (absolute)."""

    tj_max: np.ndarray  # per die / source, max over the top face nodes
    tj_mean: np.ndarray  # per die / source, area mean over the top face
    energy_balance: float  # |Q_out / Q_in - 1|, Q_in = die powers + assembled volume source + boundary inflow
    picard_iters: int
    picard_residual: float  # last max |dT| [K]
    dofs: int
    wall_s: float
    T: np.ndarray = field(repr=False, default_factory=lambda: np.zeros(0))
    nodes: np.ndarray = field(repr=False, default_factory=lambda: np.zeros((0, 3)))
    meta: dict = field(default_factory=dict)
    field_eval: object = field(repr=False, default=None)  # for ``point_values``


@dataclass(frozen=True)
class GridRule:
    """Level-0 grid of the refinement rule: lateral size ``h0`` [m] and cells per layer in z (see module docstring)."""

    h0: float = 2.0e-3
    nz: dict = field(default_factory=lambda: {"baseplate": 2, "solder": 1, "backside_cu": 1, "ceramic": 1, "top_cu": 1,
                                              "die_attach": 1, "die": 2})
    default_nz: int = 1
    zrefine: bool = True  # z cell counts double with the level too (False: z held at the level-0 counts, lateral-only study)
    near_margin: float | None = None  # [m] if set: lateral size h0 within this distance of a die (along the axis), 2 h0
    # up to 3 x near_margin, 4 h0 beyond (smooth coarsening away from the dies, where the solution is smooth)
    min_cells: int = 2  # even minimum of level-0 lateral cells per interval
    element_order: int = 1  # 1: trilinear ElementHex1 (2x2x2 Gauss); 2: triquadratic ElementHex2 (3x3x3 Gauss)
    dz_max: float | None = None  # [m] absolute bound of the level-0 z cell size: every z interval of thickness t gets
    # max(nz_of(layer), ceil(t / dz_max)) cells at level 0 and 2**level times as many at level l (T0198). Needs zrefine.

    def __post_init__(self):
        if self.element_order not in (1, 2):
            raise ValueError("element_order must be 1 or 2")
        if self.dz_max is not None:
            if not self.dz_max > 0.0:
                raise ValueError("dz_max must be positive")
            if not self.zrefine:
                raise ValueError("dz_max needs zrefine=True (r = 2 in x, y and z)")

    def nz_of(self, name: str) -> int:
        return int(self.nz.get(name, self.default_nz))


# ------------------------------------------------------------------------------------------------ grid helpers
def _lines(coords: Sequence[float], tol: float = 1e-10) -> np.ndarray:
    c = np.unique(np.asarray(list(coords), dtype=float))
    keep = np.concatenate(([True], np.diff(c) > tol))
    return c[keep]


def _base_cells(length: float, h0: float, min_cells: int = 2) -> int:
    """Level-0 cells of an interval: the smallest even number >= length / h0 (even, so that the interval's midpoint is a
    node at every level; the surface maximum of a symmetric die sits there and must not alternate between node and
    mid-cell with the level)."""
    return max(min_cells, 2 * math.ceil(length / (2.0 * h0) - 1e-9))


def _size_multipliers(lines: np.ndarray, extents: Sequence[tuple[float, float]], margin: float | None) -> list[float]:
    """Cell-size multiplier of each interval: 1 within ``margin`` of a die extent, 2 within 3 margin, else 4 (all 1 if
    ``margin`` is None). The multiplier is the same at every refinement level, so the ratio stays constant."""
    if margin is None:
        return [1.0] * (lines.size - 1)
    mid = 0.5 * (lines[1:] + lines[:-1])
    d = np.full(mid.size, np.inf)
    for lo, hi in extents:
        d = np.minimum(d, np.maximum(0.0, np.maximum(lo - mid, mid - hi)))
    return [1.0 if v <= margin else 2.0 if v <= 3.0 * margin else 4.0 for v in d]


def _subdivide(lines: np.ndarray, h0: float, level: int, min_cells: int = 2,
               mult: Sequence[float] | None = None) -> np.ndarray:
    """Split every interval into an even number >= ``L / (h0 * mult)`` of equal cells at level 0 and ``2**level`` times as
    many at ``level`` (constant refinement ratio 2)."""
    out = [lines[:1]]
    mult = [1.0] * (lines.size - 1) if mult is None else mult
    for a, b, m in zip(lines[:-1], lines[1:], mult, strict=True):
        n = _base_cells(b - a, h0 * m, min_cells) * REFINEMENT_RATIO**level
        out.append(a + (b - a) * np.arange(1, n + 1) / n)
    return np.concatenate(out)


def _subdivide_n(lines: np.ndarray, n0: Sequence[int], level: int, zrefine: bool = True) -> np.ndarray:
    """Split interval i into ``n0[i] * 2**level`` equal cells (``2**0`` when ``zrefine`` is False)."""
    out = [lines[:1]]
    for a, b, n in zip(lines[:-1], lines[1:], n0, strict=True):
        m = int(n) * (REFINEMENT_RATIO**level if zrefine else 1)
        out.append(a + (b - a) * np.arange(1, m + 1) / m)
    return np.concatenate(out)


def _z_counts(zl0: np.ndarray, base_of_mid: Callable[[float], int], rule: GridRule) -> list[int]:
    """Level-0 cells of every z interval: ``base_of_mid(midpoint)`` (the layer's count), at least ``ceil(t / dz_max)`` when
    ``rule.dz_max`` is set (t the interval thickness), so the level-0 cell is at most ``dz_max`` thick."""
    out = []
    for a, b in zip(zl0[:-1], zl0[1:], strict=True):
        n = int(base_of_mid(0.5 * (a + b)))
        if rule.dz_max is not None:
            n = max(n, math.ceil((b - a) / rule.dz_max - 1e-9))
        out.append(n)
    return out


SNAP_FRACTION = 1.0e-2  # a mandatory line closer than this fraction of its level-0 cell size snaps onto a line


def _merge_lines(base: Sequence[float], extra: Sequence[float] | None, lo: float, hi: float, tol: float,
                 cell: Callable[[float], float] | None = None) -> tuple[np.ndarray, list[tuple[float, float]]]:
    """Level-0 lines: ``base`` (merged within ``tol``) plus the mandatory lines ``extra`` (inside [lo, hi]).

    Snapping (T0215, T0216). ``cell(v)`` is the level-0 cell size of the *geometry* interval that contains ``v``
    (``_lateral_cell``, ``_z_cell``). A mandatory line closer than ``SNAP_FRACTION * cell(v)`` (and at least ``tol``) to
    an existing line (geometry lines first, then mandatory lines taken in ascending order) is not added. It SNAPS onto
    the nearest such line, and ``(requested, used)`` is returned for it, with snap distance ``|used - requested|``. Every
    kept line is therefore at least ``SNAP_FRACTION * cell`` from every other line. The interval it creates gets the rule's count
    ``n`` (``min_cells`` = 2 laterally, the layer's ``nz`` in z: 1 or 2 by default), so each of its cells is at least
    ``SNAP_FRACTION / n`` of the surrounding level-0 cell. Every level halves both, so the ratio holds at every level.

    Why 1e-2 and a ratio. Two failures were measured (T0216, Q1 and Q2, layout and box-stack modes).
    (i) scikit-fem's face inverse map ``invF`` uses an absolute Newton tolerance, so it failed in any cell under about
    1 um, whatever the ratio. A kept line of 1e-3 h0 therefore solved at level 0 and crashed at level 1.
    ``_BoxMapping`` removes that failure.
    (ii) Q2 AMG-CG (``_Solver``) failed to converge on slivers about 5e-4 of the surrounding cell (offsets of 1e-3 cell)
    at levels 1-2. Offsets of 3e-3 and 1e-2 cell converged at levels 0-2. 1e-2 leaves a factor of 3 above that limit.
    A snapped point moves by at most 1e-2 of a level-0 cell: 20 um at h0 = 2 mm, 2.5 um in a 0.25 mm z cell. The move
    is recorded, not hidden, and a reported point is the node at ``used``."""
    ex = [] if extra is None else [float(v) for v in np.asarray(extra, dtype=float).ravel()]
    for v in ex:
        if v < lo - tol or v > hi + tol:
            raise ValueError(f"mandatory grid line {v} is outside the domain [{lo}, {hi}]")
    lines = list(_lines(base, tol))
    snaps: list[tuple[float, float]] = []
    for v in sorted(ex):
        arr = np.asarray(lines)
        j = int(np.argmin(np.abs(arr - v)))
        if abs(arr[j] - v) <= max(tol, 0.0 if cell is None else SNAP_FRACTION * cell(v)):
            if arr[j] != v:
                snaps.append((v, float(arr[j])))
        else:
            lines.append(v)
    return np.unique(np.asarray(lines, dtype=float)), snaps


def _interval_lookup(base: np.ndarray, widths: Sequence[float]) -> Callable[[float], float]:
    """``widths[i]`` of the interval ``[base[i], base[i+1]]`` that contains ``v`` (clipped to the end intervals)."""
    def cell(v: float) -> float:
        return float(widths[int(np.clip(np.searchsorted(base, v, side="right") - 1, 0, base.size - 2))])
    return cell


def _lateral_cell(base: np.ndarray, h0: float, min_cells: int, extents: Sequence[tuple[float, float]],
                  margin: float | None) -> Callable[[float], float]:
    """Level-0 lateral cell size ``L / n`` of each geometry interval (``_subdivide`` with its ``near_margin`` multipliers)."""
    L = np.diff(base)
    mult = _size_multipliers(base, extents, margin)
    return _interval_lookup(base, [li / _base_cells(li, h0 * m, min_cells) for li, m in zip(L, mult, strict=True)])


def _z_cell(base: np.ndarray, counts: Sequence[int]) -> Callable[[float], float]:
    """Level-0 z cell thickness ``t / n`` of each geometry z interval (``counts`` from ``_z_counts``)."""
    return _interval_lookup(base, list(np.diff(base) / np.asarray(counts, dtype=float)))


def _split_extra(extra_lines) -> tuple:
    """(xs, ys, zs) with every entry None or a flat float array (a scalar or any sequence is accepted, both modes)."""
    if extra_lines is None:
        return None, None, None
    if len(extra_lines) != 3:
        raise ValueError("extra_lines must be (xs, ys, zs)")
    return tuple(None if e is None else np.asarray(e, dtype=float).ravel() for e in extra_lines)


def _poly_coords(poly) -> tuple[list[float], list[float]]:
    xs, ys = [], []
    for g in getattr(poly, "geoms", [poly]):
        for r in (g.exterior, *g.interiors):
            for x, y in r.coords:
                xs.append(x)
                ys.append(y)
    return xs, ys


@dataclass
class _Grid:
    """Cell-wise material map on tensor lines; ``mat < 0`` is void."""

    x: np.ndarray
    y: np.ndarray
    z: np.ndarray
    mat: np.ndarray  # (nx, ny, nz) int
    kfun: list[Callable]  # kfun[m](T array) -> k array
    sources: list  # (x0, y0, x1, y1, z, P)
    h: float
    Tc: float
    names: list = field(default_factory=list)
    order: int = 1  # element order
    source: Callable | None = None  # manufactured volume source(x, y, z) [W/m3]
    flux: Callable | None = None  # manufactured inflow flux(x, y, z, axis, sign) [W/m2] on every boundary face but z = 0
    T_inf: Callable | None = None  # Robin ambient T_inf(x, y) [K] (replaces the scalar coolant temperature in h (T - T_inf))
    snaps: dict = field(default_factory=dict)  # per axis: (requested, used) of every snapped mandatory line


class _BoxMapping(MappingIsoparametric):
    """scikit-fem's trilinear mapping with an inverse that also works in thin cells (T0216).

    ``MappingIsoparametric.invF`` stops when the per-element 1-norm of the Newton step in *reference* units falls below
    an absolute 1e-12. In a cell of width ``w`` the step cannot fall below round-off, about ``eps |x| / w``, with the
    coordinate ``|x|`` in mm. For a cell under about 1 um at module coordinates of tens of mm the test therefore never
    passes ('Newton iteration didn't converge'). The cause is the absolute width, not the ratio to the neighbouring cell,
    which is why a sliver that solves at level 0 fails at level 1 (T0216 attempt-1 review). Our cells are axis-aligned
    boxes, so the map is affine and one Newton step is exact up to round-off. The inverse first runs scikit-fem's own
    iteration, so a mesh it handles gets bit-identical points (Q1/Q2 results unchanged). If that iteration fails, this
    accepts the Newton iterate once its residual in *physical* units is round-off, ``|x - F(X)| <= 64 eps max|x|``
    (64 bounds the summed rounding of the eight-corner map). That leaves the point within 64 eps max|x| of its exact
    position (about 1e-13 mm)."""

    NEWTON_ITERS = 8  # the affine box map converges in 1-2 steps; more steps only jitter at round-off

    def invF(self, x, tind=None, newton_max_iters=NEWTON_ITERS, newton_tol=1e-12):
        try:
            return super().invF(x, tind=tind, newton_max_iters=newton_max_iters, newton_tol=newton_tol)
        except Exception:  # noqa: BLE001 - scikit-fem raises a bare Exception on non-convergence
            pass
        tol = 64.0 * np.finfo(float).eps * max(1.0, float(np.max(np.abs(x))))
        X = np.zeros(x.shape) + 0.5
        for _ in range(newton_max_iters):
            dX = np.einsum("ijkl,jkl->ikl", self.invDF(X, tind), x - self.F(X, tind))
            X = np.clip(X + dX, 0.0, 1.0)
            if np.max(np.abs(x - self.F(X, tind)), initial=0.0) <= tol:
                return X
        raise ValueError("inverse map of the hexahedral mesh did not converge to round-off (degenerate cell?)")


def _build_mesh(g: _Grid):
    """Skfem MeshHex of the non-void cells; returns (mesh, element material, element -> cell ijk)."""
    nx, ny, nz = g.mat.shape
    ci, cj, ck = np.nonzero(g.mat >= 0)
    emat = g.mat[ci, cj, ck].astype(np.int64)
    sy, sz = ny + 1, nz + 1
    corner_ids = np.empty((8, ci.size), dtype=np.int64)
    for c, (dx, dy, dz) in enumerate(_HEX_CORNERS):
        corner_ids[c] = ((ci + dx) * sy + (cj + dy)) * sz + (ck + dz)
    used, inv = np.unique(corner_ids.ravel(), return_inverse=True)
    t = inv.reshape(8, ci.size)
    ii, rem = np.divmod(used, sy * sz)
    jj, kk = np.divmod(rem, sz)
    p = np.vstack((g.x[ii], g.y[jj], g.z[kk]))
    mesh = MeshHex(p * MM, t, validate=False)  # internal length unit: mm
    dof_of = -np.ones((nx + 1) * sy * sz, dtype=np.int64)  # structured node id -> dof (basis dof = node index of Q1)
    dof_of[used] = np.arange(used.size)
    return mesh, emat, dof_of


def _gci(f: Sequence[float], r: float = REFINEMENT_RATIO) -> tuple[float, float]:
    """(GCI, p_obs) of values (finest, middle, coarsest) at ratio ``r = 2`` by O006's A4 rule
    (``thermal_layout.gci_three_grid``); ``p_obs`` is NaN when the convergence is not monotone."""
    f1, f2, f3 = (float(v) for v in f)
    g = gci_three_grid(f3, f2, f1, r)
    return g["gci"], g["p_obs"]


def gci(values: Sequence[float], r: float = REFINEMENT_RATIO) -> tuple[float, float]:
    """Public wrapper of the per-value Roache GCI: ``(gci, p_obs)`` for ``values = (finest, middle, coarsest)``."""
    return _gci(values, r)


# ------------------------------------------------------------------------------------------------ assembly helpers
def _element(order: int):
    return ElementHex1() if order == 1 else ElementHex2()


def _interpolate(cb: CellBasis, w: np.ndarray) -> np.ndarray:
    """``np.asarray(cb.interpolate(w))`` for a scalar element, at the cost of ``cb``'s own elements.

    scikit-fem 12.0's ``interpolate`` first splits ``w`` by ``np.unique`` over the whole ``Dofs.element_dofs``. With the
    global ``Dofs`` shared by every chunk's basis that is O(N) per chunk, O(N^2 / chunk) per k(T) assembly: 13.6 M Q1
    DOFs spent more than 100 min in one Picard step's assembly (O007 probe burst, 2026-11-04). The loop below is
    scikit-fem's ``linear_combination`` term for term, so the values are bit-identical."""
    if w.shape[0] != cb.N:
        raise ValueError("Input array has wrong size.")
    out = 0.0 * np.einsum("...,...j->...j", w[cb.element_dofs[0]], cb.basis[0][0].get(0))
    for i in range(cb.Nbfun):
        out += np.einsum("...,...j->...j", w[cb.element_dofs[i]], cb.basis[i][0].get(0))
    return out


def _sum_chunks(parts) -> sp.csr_matrix | None:
    """Sum an iterable of sparse matrices by a binary-counter tree (cost O(nnz log n_chunks), not O(n_chunks nnz); at most
    about two partial sums of the final size are alive at once)."""
    stack: list[tuple[int, sp.csr_matrix]] = []
    for m in parts:
        stack.append((0, m.tocsr()))
        while len(stack) > 1 and stack[-1][0] == stack[-2][0]:
            (lv, a), (_, b) = stack.pop(), stack.pop()
            stack.append((lv + 1, (a + b).tocsr()))
    out = None
    for _, m in stack:
        out = m if out is None else (out + m).tocsr()
    return out


@BilinearForm
def _stiff_form(u, v, w):
    return w["k"] * dot(grad(u), grad(v))


@BilinearForm
def _mass_form(u, v, w):
    return u * v


@LinearForm
def _one_form(v, w):
    return 1.0 * v


@LinearForm
def _load_form(v, w):
    return w["f"] * v


def _chunks(n: int, size: int):
    for s in range(0, n, size):
        yield np.arange(s, min(n, s + size))


def _face_mask(dofs, facets: np.ndarray, nd: int) -> np.ndarray:
    """True for the dofs that live on ``facets`` (their vertices, and for Q2 also their edge and face midpoints)."""
    m = np.zeros(nd, dtype=bool)
    if facets.size:
        m[dofs.get_facet_dofs(facets).flatten()] = True
    return m


def _complement(idx: np.ndarray, nd: int) -> np.ndarray:
    m = np.ones(nd, dtype=bool)
    m[idx] = False
    return m


def _restrict(M: sp.csr_matrix, mask: np.ndarray) -> sp.csr_matrix:
    """``M`` with the rows and columns outside ``mask`` zeroed.

    A face integral assembled with ``FacetBasis`` maps the face quadrature points back to the reference cell by an inverse
    (Newton) map, so they sit about 1e-16 off the reference face: basis functions that vanish on the face then come out at
    about 1e-15 instead of 0 (measured: 25 to 550 such dofs per die face). They are exactly zero in the continuum. Every
    face integral is therefore restricted to the face's own dofs, so the loads, the Robin mass and the node set of
    ``tj_max`` are exactly those of the face (T0205 review: off-face nodes had entered ``tj_max``)."""
    D = sp.diags(mask.astype(float))
    out = (D @ M @ D).tocsr()
    out.eliminate_zeros()
    return out


def _boundary_faces(mesh) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Boundary facets of the mesh (cells next to void included) with their outward normal ``axis`` (0, 1, 2), ``sign``
    (+1/-1) and centre ``mp`` (3, n) [mm]; the faces are axis-aligned rectangles."""
    bf = mesh.boundary_facets()
    P = mesh.p[:, mesh.facets[:, bf]]  # (3, 4, nf)
    mp = P.mean(axis=1)
    axis = (P.max(axis=1) - P.min(axis=1)).argmin(axis=0)
    cols = np.arange(bf.size)
    ctr = mesh.p[:, mesh.t[:, mesh.f2t[0, bf]]].mean(axis=1)
    sign = np.where(mp[axis, cols] > ctr[axis, cols], 1, -1)
    return bf, axis, sign, mp


def _q1_to_q2(mesh, dofs) -> sp.csr_matrix:
    """Prolongation (N_Q2 x N_vertices) of the trilinear (Q1) space into the triquadratic (Q2) one on the same mesh: a
    vertex dof copies its vertex, an edge-midpoint dof is the mean of the edge's 2 vertices, a face-centre dof the mean of
    the face's 4 and a cell-centre dof the mean of the cell's 8. Exact, because a trilinear function on an axis-aligned box
    is linear along an edge, bilinear on a face and trilinear in the cell (Q1 is a subspace of Q2)."""
    nv = mesh.p.shape[1]
    rows, cols, vals = [dofs.nodal_dofs[0]], [np.arange(nv)], [np.ones(nv)]
    for dd, conn in ((dofs.edge_dofs, mesh.edges), (dofs.facet_dofs, mesh.facets), (dofs.interior_dofs, mesh.t)):
        m = conn.shape[0]
        rows.append(np.repeat(dd[0], m))
        cols.append(conn.T.ravel())
        vals.append(np.full(dd.shape[1] * m, 1.0 / m))
    return sp.csr_matrix((np.concatenate(vals), (np.concatenate(rows), np.concatenate(cols))), shape=(int(dofs.N), nv))


AMG_SEED = 20261103  # explicit seed for pyamg's hierarchy construction (see _sa_solver)


def _sa_solver(A: sp.csr_matrix, **kw):
    """pyamg smoothed aggregation with a fixed seed. pyamg estimates the spectral radius it uses to smooth the
    prolongator from an unseeded random start vector (pyamg.util.linalg.approximate_spectral_radius,
    np.random.rand), so without a seed the hierarchy, and with it the CG convergence of every solve, changes from run
    to run (2026-11-03: residual-check failures in 1 of 25 runs of the same solve, and flaky tests). The global numpy
    random state is restored afterwards, so callers' random streams are unaffected."""
    state = np.random.get_state()
    np.random.seed(AMG_SEED)
    try:
        return pyamg.smoothed_aggregation_solver(A, **kw)
    finally:
        np.random.set_state(state)


class _Solver:
    """CG preconditioned by algebraic multigrid (pyamg, MIT), stopping at the relative residual ``LINEAR_RTOL``; raises
    unless the true relative residual of the returned solution is below 1e-8.

    Order 1: smoothed-aggregation AMG on the matrix as is, with the constant-mode deflation below (added 2026-11-03: without
    it the order-1 solve at h = 5 W/(m2 K) sat at its round-off floor, near the 1e-8 check, and failed on Linux CI; with it
    the toy layout reaches 2.4e-11 at h = 5, while h <= 1 W/(m2 K) still fails the check, far below any operating point).

    Order 2: smoothed aggregation applied to the Q2 matrix directly builds far too few coarse unknowns (every Q2 dof is
    strongly coupled to up to 125 dofs of its neighbouring cells, so the aggregates are huge: operator complexity 1.005 on
    the toy layout), and CG stalls when the Robin coupling is weak (h = 50 W/(m2 K), T0205 review). The first coarse level
    is therefore the Q1 space of the same mesh (p-multigrid; Ronquist & Patera, J. Sci. Comput. 2(4):389, 1987):
    prolongation ``P`` = ``_q1_to_q2`` (exact), Galerkin coarse matrix ``P^T A P``, smoothed aggregation below it, and
    symmetric Gauss-Seidel smoothing on every level (a symmetric V-cycle, so a valid CG preconditioner). In addition the
    near-null constant mode is deflated: ``x = c 1 + y`` with ``c = 1^T b / 1^T A 1`` (the A-orthogonal projection of the
    solution on the constants, i.e. the global energy balance), and CG solves ``A y = b - c A 1``. Without it the
    attainable relative residual of the rise, about eps |A| |x| / |b|, is 1.5e-10 for a uniform 48 K rise over 0.6 K of
    variation (h = 50), above ``LINEAR_RTOL``; with it the floor scales with the variation of the rise, not its mean."""

    def __init__(self, A: sp.csr_matrix, P: sp.csr_matrix | None = None):
        self.A = A
        self.P = P
        self.one = np.ones(A.shape[0])
        self.a1 = A @ self.one
        self.c_den = float(self.one @ self.a1)
        if P is None:
            self.ml = _sa_solver(A, max_coarse=500)
            return
        Ac = (P.T @ (A @ P)).tocsr()
        coarse = _sa_solver(Ac, max_coarse=500)
        top = MultilevelSolver.Level()
        top.A, top.P, top.R = A, P, P.T.tocsr()
        self.ml = MultilevelSolver([top, *coarse.levels], coarse_solver="pinv")
        gs = ("gauss_seidel", {"sweep": "symmetric"})
        change_smoothers(self.ml, presmoother=gs, postsmoother=gs)

    def solve(self, b: np.ndarray, x0: np.ndarray) -> np.ndarray:
        c = float(self.one @ b) / self.c_den
        hist: list = []  # pyamg's own residual history (read only: it does not change the iterates)
        y, info = self.ml.solve(b - c * self.a1, x0=x0 - c, tol=LINEAR_RTOL, maxiter=CG_MAXITER, accel="cg",
                                residuals=hist, return_info=True)
        x = c + y
        nb = np.linalg.norm(b)
        rel = float(np.linalg.norm(b - self.A @ x) / nb) if nb > 0.0 else float(np.linalg.norm(b - self.A @ x))
        # info is 0 on convergence to LINEAR_RTOL and the iteration count otherwise; hist[0] is the starting residual
        iters = len(hist) - 1
        self.stats = {"iterations": int(iters), "rel_residual": rel,
                      "hit_maxiter": bool(iters >= CG_MAXITER or info != 0)}
        if np.linalg.norm(b - self.A @ x) > 1e-8 * nb:
            raise RuntimeError("AMG-CG did not converge to a relative residual of 1e-8")
        return x


@dataclass
class _FieldEval:
    """What ``point_values`` needs to evaluate the FE field at a point."""

    mesh: object
    elem: object
    dofs: object
    eidx: np.ndarray  # (nx, ny, nz) element id of every tensor cell, -1 for void
    lines: tuple  # (x, y, z) tensor lines [m]


def _solve_grid(g: _Grid, constant_k: bool, k_const_T: float | None = None, picard_tol: float = PICARD_TOL_K,
                max_picard: int = 60, chunk: int | None = None) -> ThermalResult:
    """Assemble and solve the grid problem (module docstring). ``g.order`` selects Q1 or Q2; ``chunk`` is the number of
    elements (facets: a tenth of it) per scikit-fem basis during assembly."""
    t0 = time.perf_counter()
    order = g.order
    mesh, emat, _ = _build_mesh(g)
    bmap = _BoxMapping(mesh, mesh.elem(), mesh.bndelem)  # every face basis: inverse map robust in thin cells
    elem = _element(order)
    dofs = Dofs(mesh, elem)
    nd = int(dofs.N)
    ne = emat.size
    chunk = chunk or (4000 if order == 2 else 20000)
    fchunk = max(200, chunk // 10)
    iq = 4 if order == 2 else 2  # stiffness quadrature (exact for constant k per element, see module docstring)
    hh = g.h / MM**2  # W/(mm2 K)

    # ---- boundary classification ----
    bf, axis, sign, mp = _boundary_faces(mesh)
    ztol = 1e-9 * float(mesh.p[2].max())
    robin = (axis == 2) & (sign < 0) & (np.abs(mp[2]) < ztol)
    robin_idx = bf[robin]
    # Robin mass, int of each basis function over the sink face, and the T_inf load
    mass_parts, ones_b = [], np.zeros(nd)
    f_robin = np.zeros(nd)
    for s in _chunks(robin_idx.size, fchunk):
        fb = FacetBasis(mesh, elem, mapping=bmap, facets=robin_idx[s], intorder=4, dofs=dofs, disable_doflocs=True)
        mass_parts.append(_mass_form.assemble(fb))
        ones_b += _one_form.assemble(fb)
        if g.T_inf is not None:
            fd = FacetBasis(mesh, elem, mapping=bmap, facets=robin_idx[s], intorder=DATA_INTORDER, dofs=dofs, disable_doflocs=True)
            X = fd.global_coordinates() / MM
            ti = np.broadcast_to(np.asarray(g.T_inf(X[0], X[1]), dtype=float), X[0].shape)
            f_robin += _load_form.assemble(fd, f=hh * (ti - g.Tc))
    on_sink = _face_mask(dofs, robin_idx, nd)
    Mb = hh * _restrict(_sum_chunks(mass_parts), on_sink)
    ones_b[~on_sink] = 0.0
    f_robin[~on_sink] = 0.0
    del mass_parts

    # ---- die sources: uniform flux over each top face (faces on the mesh boundary, no active cell above) ----
    f_die = np.zeros(nd)
    src_vecs, src_nodes = [], []
    P_tot = 0.0
    nzc = g.mat.shape[2]
    xc, yc = 0.5 * (g.x[1:] + g.x[:-1]), 0.5 * (g.y[1:] + g.y[:-1])
    zt_tol = 1e-9 * g.z[-1]
    top = (axis == 2) & (sign > 0)
    for (x0, y0, x1, y1, zt, P) in g.sources:
        kp = int(np.argmin(np.abs(g.z - zt)))
        if abs(g.z[kp] - zt) > zt_tol:
            raise ValueError("a heat source plane is not a z grid line")
        sx = np.nonzero((xc > x0) & (xc < x1))[0]
        sy_ = np.nonzero((yc > y0) & (yc < y1))[0]
        si, sj = np.meshgrid(sx, sy_, indexing="ij")
        si, sj = si.ravel(), sj.ravel()
        if si.size == 0 or kp == 0 or (g.mat[si, sj, kp - 1] < 0).any():
            raise ValueError("a heat source is not fully supported by active cells below its plane")
        if kp < nzc and (g.mat[si, sj, kp] >= 0).any():
            raise ValueError("a heat source face is not on the mesh boundary (active cells above it)")
        sel = (top & (np.abs(mp[2] - zt * MM) < zt_tol * MM) & (mp[0] > x0 * MM) & (mp[0] < x1 * MM)
               & (mp[1] > y0 * MM) & (mp[1] < y1 * MM))
        vec = np.zeros(nd)
        for s in _chunks(int(sel.sum()), fchunk):
            fb = FacetBasis(mesh, elem, mapping=bmap, facets=bf[sel][s], intorder=4, dofs=dofs, disable_doflocs=True)
            vec += _one_form.assemble(fb)
        face_dofs = np.unique(dofs.get_facet_dofs(bf[sel]).flatten())  # every node of the face (Q2: + edge/face midpoints)
        vec[_complement(face_dofs, nd)] = 0.0
        area = float(vec.sum())
        if abs(area - (x1 - x0) * (y1 - y0) * MM**2) > 1e-6 * area:
            raise ValueError("a heat source is not fully covered by mesh faces (area mismatch)")
        f_die += (P / area) * vec  # W/mm2 times mm2
        src_vecs.append(vec / area)
        src_nodes.append(face_dofs)
        P_tot += P

    # ---- manufactured data: volume source and inflow flux on every boundary face except the Robin face ----
    f_vol = np.zeros(nd)
    if g.source is not None:
        for idx in _chunks(ne, max(100, chunk // 4)):
            cb = CellBasis(mesh, elem, intorder=DATA_INTORDER, elements=idx, dofs=dofs, disable_doflocs=True)
            X = cb.global_coordinates() / MM
            q = np.broadcast_to(np.asarray(g.source(X[0], X[1], X[2]), dtype=float), X[0].shape)
            f_vol += _load_form.assemble(cb, f=q / MM**3)
            del cb, X, q
    f_flux = np.zeros(nd)
    if g.flux is not None:
        for ax in range(3):
            for sg in (-1, 1):
                sel = bf[(axis == ax) & (sign == sg) & ~robin]
                part = np.zeros(nd)
                for s in _chunks(sel.size, fchunk):
                    fb = FacetBasis(mesh, elem, mapping=bmap, facets=sel[s], intorder=DATA_INTORDER, dofs=dofs, disable_doflocs=True)
                    X = fb.global_coordinates() / MM
                    q = np.broadcast_to(np.asarray(g.flux(X[0], X[1], X[2], ax, sg), dtype=float), X[0].shape)
                    part += _load_form.assemble(fb, f=q / MM**2)
                part[~_face_mask(dofs, sel, nd)] = 0.0
                f_flux += part
    rhs = f_die + f_vol + f_flux + f_robin  # solve for the rise theta = T - Tc, whose Robin right-hand side vanishes
    q_die, q_vol, q_bnd = P_tot, float(f_vol.sum()), float(f_flux.sum())
    del bf, axis, sign, mp

    prolong = _q1_to_q2(mesh, dofs) if order == 2 else None  # first coarse level of the Q2 multigrid (see _Solver)
    theta = np.zeros(nd)
    picard = 0
    resid = float("inf")
    kmax = len(g.kfun)
    cg_stats: list[dict] = []  # one entry per linear solve (every Picard step)
    while True:
        A = None  # free the previous system before the next is built (one CSR matrix alive at the peak)
        T_prev = g.Tc + theta

        def stiffness_parts(T_prev=T_prev):
            for idx in _chunks(ne, chunk):
                cb = CellBasis(mesh, elem, intorder=iq, elements=idx, dofs=dofs, disable_doflocs=True)
                nq = cb.X.shape[1]
                if constant_k:
                    Tq = np.full((idx.size, nq), k_const_T if k_const_T is not None else g.Tc)
                else:
                    Tq = _interpolate(cb, T_prev)  # absolute T at this chunk's quadrature points
                kq = np.empty((idx.size, nq))
                em = emat[idx]
                for m in range(kmax):
                    sel = em == m
                    if sel.any():
                        kq[sel] = g.kfun[m](Tq[sel])
                yield _stiff_form.assemble(cb, k=kq / MM)
                del cb, Tq, kq

        A = (_sum_chunks(stiffness_parts()) + Mb).tocsr()
        lin = _Solver(A, prolong)
        new = lin.solve(rhs, theta)
        cg_stats.append(lin.stats)
        picard += 1
        resid = float(np.max(np.abs(new - theta)))
        theta = new
        if constant_k or resid < picard_tol:
            break
        if picard >= max_picard:
            raise RuntimeError(f"Picard did not converge in {max_picard} iterations (last |dT| = {resid:.3e} K)")
    Tn = g.Tc + theta
    # Q_out = int h (T - T_inf) dS over the sink face; the T_inf part is the assembled load (its integral is f_robin.sum())
    q_out = float(hh * np.dot(ones_b, theta) - f_robin.sum())
    q_in = q_die + q_vol + q_bnd
    eb = abs(q_out / q_in - 1.0) if q_in != 0.0 else abs(q_out)
    nodes_m = _doflocs(mesh, dofs).T / MM
    arg = [int(n[np.argmax(Tn[n])]) for n in src_nodes]  # the top-face DOF of maximum T (first one on a tie)
    tj_max = np.array([Tn[a] for a in arg])
    tj_xyz = [[float(c) for c in nodes_m[a]] for a in arg]
    tj_mean = np.array([float(np.dot(v, Tn)) for v in src_vecs])
    wall = time.perf_counter() - t0
    ci, cj, ck = np.nonzero(g.mat >= 0)
    eidx = -np.ones(g.mat.shape, dtype=np.int64)
    eidx[ci, cj, ck] = np.arange(ne)
    cg_its = [int(st["iterations"]) for st in cg_stats]
    meta = {"cg_iterations": cg_its, "cg_max_iterations": max(cg_its),
            "linear_rel_residual_max": max(float(st["rel_residual"]) for st in cg_stats),
            "cg_hit_maxiter": any(bool(st["hit_maxiter"]) for st in cg_stats),
            "n_elements": int(ne), "element_order": order, "n_vertices": int(mesh.p.shape[1]), "q_out_W": q_out,
            "P_total_W": P_tot, "q_in_die_W": q_die, "q_in_volume_W": q_vol, "q_in_boundary_W": q_bnd,
            "q_in_W": q_in, "data_intorder": DATA_INTORDER, "n_dofs": int(nd), "tj_max_xyz": tj_xyz,
            "lines": {"x": g.x.copy(), "y": g.y.copy(), "z": g.z.copy()},
            "n_lines": {"x": int(g.x.size), "y": int(g.y.size), "z": int(g.z.size)},
            "snapped_lines": {ax: [(float(a), float(b)) for a, b in v] for ax, v in g.snaps.items()},
            "max_snap_m": max([abs(b - a) for v in g.snaps.values() for a, b in v], default=0.0)}
    return ThermalResult(tj_max, tj_mean, eb, picard, resid, nd, wall, T=Tn, nodes=nodes_m, meta=meta,
                         field_eval=_FieldEval(mesh, elem, dofs, eidx, (g.x, g.y, g.z)))


def _doflocs(mesh, dofs) -> np.ndarray:
    """Dof coordinates (3, N) [mm]: vertices, edge midpoints, face centres, cell centres (affine cells)."""
    loc = np.zeros((3, int(dofs.N)))
    loc[:, dofs.nodal_dofs[0]] = mesh.p
    if dofs.edge_dofs.shape[0]:
        loc[:, dofs.edge_dofs[0]] = mesh.p[:, mesh.edges].mean(axis=1)
    if dofs.facet_dofs.shape[0]:
        loc[:, dofs.facet_dofs[0]] = mesh.p[:, mesh.facets].mean(axis=1)
    if dofs.interior_dofs.shape[0]:
        loc[:, dofs.interior_dofs[0]] = mesh.p[:, mesh.t].mean(axis=1)
    return loc


def point_values(res: ThermalResult, pts: np.ndarray) -> np.ndarray:
    """Absolute temperature [K] of the FE field at points ``pts`` (n, 3) [m]: the tensor cell containing each point (an
    active one when the point is on a shared line or on a boundary), reference coordinates by the mesh mapping's inverse."""
    fe = res.field_eval
    if fe is None:
        raise ValueError("the result carries no field evaluator")
    mapping = _BoxMapping(fe.mesh, fe.mesh.elem(), fe.mesh.bndelem)
    out = np.empty(len(pts))
    for n, p in enumerate(np.asarray(pts, dtype=float).reshape(-1, 3)):
        cand = []
        for lines, v in zip(fe.lines, p, strict=True):
            tol = 1e-9 * abs(lines[-1])
            i = int(np.clip(np.searchsorted(lines, v, side="right") - 1, 0, lines.size - 2))
            if v < lines[0] - tol or v > lines[-1] + tol:
                raise ValueError(f"point {p} outside the mesh")
            cand.append([j for j in (i - 1, i) if 0 <= j < lines.size - 1 and lines[j] - tol <= v <= lines[j + 1] + tol])
        e = next((int(fe.eidx[i, j, k]) for i in cand[0] for j in cand[1] for k in cand[2] if fe.eidx[i, j, k] >= 0), -1)
        if e < 0:
            raise ValueError(f"point {p} is not in an active cell")
        X = mapping.invF((p * MM)[:, None, None], tind=np.array([e]))
        cb = CellBasis(fe.mesh, fe.elem, elements=np.array([e]), quadrature=(X[:, 0, :], np.array([1.0])), dofs=fe.dofs, disable_doflocs=True)
        out[n] = float(_interpolate(cb, res.T).ravel()[0])
    return out


NODE_TOL_M = 1.0e-9  # a point is a DOF location when every coordinate is within this of it


def _top_z(res: ThermalResult) -> float:
    return float(res.field_eval.lines[2][-1]) if res.field_eval is not None else float(res.nodes[:, 2].max())


def node_value(res: ThermalResult, x: float, y: float, z: float | None = None) -> float:
    """Temperature [K] at the DOF location (x, y, z) [m] (``z`` defaults to the top face). Q2 DOFs include edge, face and
    cell mid-nodes. The point must coincide with a DOF to within ``NODE_TOL_M`` in every coordinate, else ValueError: there
    is no interpolation, so a reported value is always a nodal value of the discrete solution."""
    z = _top_z(res) if z is None else float(z)
    d = np.abs(res.nodes - np.array([x, y, z], dtype=float))
    hit = np.nonzero((d <= NODE_TOL_M).all(axis=1))[0]
    if hit.size == 0:
        raise ValueError(f"point ({x}, {y}, {z}) is not a DOF location of the mesh (tolerance {NODE_TOL_M} m)")
    return float(res.T[hit[np.argmin(d[hit].sum(axis=1))]])


def node_stencil(res: ThermalResult, x: float, y: float, z: float | None = None) -> tuple[dict, dict, dict]:
    """Per axis (x, y, z) the grid-line stencil of a point: ``{"index", "on_line", "coord", "lo", "hi"}``. If the point is
    on a grid line (within ``NODE_TOL_M``): ``index`` is the line's index, ``coord`` its coordinate, ``lo`` / ``hi`` the
    neighbouring line coordinates (None at the domain ends). If it lies between lines (a Q2 mid-node): ``index`` None,
    ``on_line`` False, ``lo`` / ``hi`` the enclosing lines. ValueError outside the mesh. A runner compares these between
    levels to report that the point is a node."""
    fe = res.field_eval
    if fe is None:
        raise ValueError("the result carries no field evaluator")
    z = _top_z(res) if z is None else float(z)
    out = []
    for lines, v in zip(fe.lines, (float(x), float(y), z), strict=True):
        if v < lines[0] - NODE_TOL_M or v > lines[-1] + NODE_TOL_M:
            raise ValueError(f"coordinate {v} is outside the mesh")
        i = int(np.argmin(np.abs(lines - v)))
        if abs(lines[i] - v) <= NODE_TOL_M:
            out.append({"index": i, "on_line": True, "coord": float(lines[i]),
                        "lo": float(lines[i - 1]) if i > 0 else None,
                        "hi": float(lines[i + 1]) if i < lines.size - 1 else None})
        else:
            j = int(np.searchsorted(lines, v) - 1)
            out.append({"index": None, "on_line": False, "coord": v, "lo": float(lines[j]), "hi": float(lines[j + 1])})
    return out[0], out[1], out[2]


# ------------------------------------------------------------------------------------------------ layout mode
def _k_of(layer: Layer) -> Callable:
    return lambda T: layer.k_at(T)


def layout_grid(layout: Layout, power_W: Sequence[float] | float, h: float, T_c: float,
                rule: GridRule | None = None, level: int = 0, extra_lines: tuple | None = None) -> _Grid:
    """Conforming tensor grid, material map and sources for ``layout`` (docs/thermal_model.md, sections 2-4)."""
    rule = rule or GridRule()
    st = layout.stack
    P = np.broadcast_to(np.asarray(power_W, dtype=float), (len(layout.dies),)).copy()
    back = layout.outline.buffer(-layout.backside_inset, join_style="mitre")
    traces = shapely.union_all([t.polygon for t in layout.traces])
    # containment checks (invalid input -> raise, section 2)
    if not layout.outline.buffer(1e-9).contains(back):
        raise ValueError("backside Cu is not inside the substrate outline")
    if not layout.baseplate_outline.buffer(1e-9).contains(layout.outline):
        raise ValueError("outline is not inside the baseplate outline")
    if not layout.outline.buffer(1e-9).contains(traces):
        raise ValueError("traces are not inside the outline")
    for d in layout.dies:
        if not traces.buffer(1e-9).contains(d.box):
            raise ValueError("a die footprint is not supported by the top-Cu traces")
    # z lines: substrate layers then die attach and die (per die thickness may differ -> union of lines)
    zb = [0.0]
    zcounts = []
    names = []
    for la in st.layers:
        zb.append(zb[-1] + la.thickness)
        zcounts.append(rule.nz_of(la.name))
        names.append(la.name)
    z_top_cu = zb[-1]
    att = sorted({d.attach_thickness for d in layout.dies})
    dth = sorted({d.thickness for d in layout.dies})
    extra = []  # (z_lo, z_hi, n) intervals above top Cu
    for a in att:
        extra.append((z_top_cu, z_top_cu + a, rule.nz_of("die_attach")))
    for a in att:
        for t in dth:
            extra.append((z_top_cu + a, z_top_cu + a + t, rule.nz_of("die")))
    zl_pts = sorted({round(v, 15) for v in zb} | {round(e[0], 15) for e in extra} | {round(e[1], 15) for e in extra})
    exs, eys, ezs = _split_extra(extra_lines)
    # cells per z interval at level 0
    bands = [(zb[i], zb[i + 1], zcounts[i]) for i in range(len(zcounts))] + extra

    def base_n(mid: float) -> int:
        for lo, hi, nn in bands:
            if lo - 1e-12 <= mid <= hi + 1e-12:
                return nn
        return 1

    zbase = np.asarray(zl_pts, dtype=float)
    zl0, zsnap = _merge_lines(zbase, ezs, zbase[0], zbase[-1], 1e-12, _z_cell(zbase, _z_counts(zbase, base_n, rule)))
    nzi = _z_counts(zl0, base_n, rule)
    zl = _subdivide_n(zl0, nzi, level, rule.zrefine)
    # x, y lines
    xs, ys = [], []
    for poly in (layout.baseplate_outline, layout.outline, back, traces):
        px, py = _poly_coords(poly)
        xs += px
        ys += py
    for d in layout.dies:
        x0, y0, x1, y1 = d.bounds
        xs += [x0, x1]
        ys += [y0, y1]
    bx, by = layout.baseplate_outline.bounds[0::2], layout.baseplate_outline.bounds[1::2]
    ext_x, ext_y = [(d.bounds[0], d.bounds[2]) for d in layout.dies], [(d.bounds[1], d.bounds[3]) for d in layout.dies]
    xb, yb = _lines(xs), _lines(ys)
    xl0, xsnap = _merge_lines(xb, exs, bx[0], bx[1], 1e-10, _lateral_cell(xb, rule.h0, rule.min_cells, ext_x, rule.near_margin))
    yl0, ysnap = _merge_lines(yb, eys, by[0], by[1], 1e-10, _lateral_cell(yb, rule.h0, rule.min_cells, ext_y, rule.near_margin))
    mx = _size_multipliers(xl0, ext_x, rule.near_margin)
    my = _size_multipliers(yl0, ext_y, rule.near_margin)
    xl = _subdivide(xl0, rule.h0, level, rule.min_cells, mx)
    yl = _subdivide(yl0, rule.h0, level, rule.min_cells, my)
    xc, yc, zc = 0.5 * (xl[1:] + xl[:-1]), 0.5 * (yl[1:] + yl[:-1]), 0.5 * (zl[1:] + zl[:-1])
    X, Y = np.meshgrid(xc, yc, indexing="ij")

    def inside(poly):
        return shapely.contains_xy(poly, X.ravel(), Y.ravel()).reshape(X.shape)

    in_base, in_out, in_back, in_tr = (inside(layout.baseplate_outline), inside(layout.outline), inside(back),
                                       inside(traces))
    materials = [st.layer(n) for n in ("baseplate", "solder", "backside_cu", "ceramic", "top_cu")] + [st.die_attach,
                                                                                                    st.die]
    mat = -np.ones((xc.size, yc.size, zc.size), dtype=np.int32)
    for k, z in enumerate(zc):
        if z < zb[1]:
            mat[:, :, k][in_base] = 0
        elif z < zb[2]:
            mat[:, :, k][in_back] = 1
        elif z < zb[3]:
            mat[:, :, k][in_back] = 2
        elif z < zb[4]:
            mat[:, :, k][in_out] = 3
        elif z < zb[5]:
            mat[:, :, k][in_tr] = 4
        else:
            for d in layout.dies:
                x0, y0, x1, y1 = d.bounds
                msk = (X > x0) & (X < x1) & (Y > y0) & (Y < y1)
                za = z_top_cu + d.attach_thickness
                if z < za:
                    mat[:, :, k][msk] = 5
                elif z < za + d.thickness:
                    mat[:, :, k][msk] = 6
    sources = []
    for d, p in zip(layout.dies, P, strict=True):
        x0, y0, x1, y1 = d.bounds
        sources.append((x0, y0, x1, y1, z_top_cu + d.attach_thickness + d.thickness, float(p)))
    return _Grid(xl, yl, zl, mat, [_k_of(m) for m in materials], sources, float(h), float(T_c),
                 ["baseplate", "solder", "backside_cu", "ceramic", "top_cu", "die_attach", "die"],
                 order=rule.element_order, snaps={"x": xsnap, "y": ysnap, "z": zsnap})


def estimate_dofs(layout: Layout, rule: GridRule | None = None, level: int = 0) -> int:
    """DOF count of the level-``level`` mesh from the grid counts alone (no matrices built; used to skip levels): the
    nodes for ``rule.element_order`` 1, nodes + edges + faces + cells for 2."""
    g = layout_grid(layout, 1.0, 1.0, 300.0, rule, level)
    return _count_nodes(g.mat) if g.order == 1 else _count_nodes_q2(g.mat)


def _count_nodes(mat: np.ndarray) -> int:
    act = mat >= 0
    pad = np.zeros((act.shape[0] + 1, act.shape[1] + 1, act.shape[2] + 1), dtype=bool)
    for dx in (0, 1):
        for dy in (0, 1):
            for dz in (0, 1):
                pad[dx:dx + act.shape[0], dy:dy + act.shape[1], dz:dz + act.shape[2]] |= act
    return int(pad.sum())


def _count_nodes_q2(mat: np.ndarray) -> int:
    """Q2 DOFs = points of the doubled lattice (2n+1 per axis) that lie in the closure of an active cell. A lattice
    point touches the cells on either side along every axis it is on a line of, so the test is separable per axis."""
    act = mat >= 0
    for ax in range(3):
        n = act.shape[ax]
        pad = np.concatenate([np.zeros_like(np.take(act, [0], axis=ax)), act, np.zeros_like(np.take(act, [0], axis=ax))], axis=ax)
        out_shape = list(act.shape)
        out_shape[ax] = 2 * n + 1
        out = np.zeros(out_shape, dtype=bool)
        sl = [slice(None)] * 3
        sl[ax] = slice(1, 2 * n + 1, 2)  # odd points: the cell itself
        out[tuple(sl)] = act
        lo, hi = [slice(None)] * 3, [slice(None)] * 3
        lo[ax], hi[ax] = slice(0, n + 1), slice(1, n + 2)
        sl[ax] = slice(0, 2 * n + 1, 2)  # even points: either neighbour
        out[tuple(sl)] = pad[tuple(lo)] | pad[tuple(hi)]
        act = out
    return int(act.sum())


def solve_layout(layout: Layout, power_W: Sequence[float] | float, h: float, T_c: float, *, rule: GridRule | None = None,
                 level: int = 0, constant_k: bool = False, picard_tol: float = PICARD_TOL_K,
                 source: Callable | None = None, flux: Callable | None = None,
                 T_inf: Callable | None = None, extra_lines: tuple | None = None) -> ThermalResult:
    """Layout mode: solve docs/thermal_model.md on the level-``level`` conforming mesh (``rule.element_order`` 1 or 2).

    Optional manufactured data (SI; defaults None = the production problem, unchanged): ``source(x, y, z)`` [W/m3] over
    the volume; ``flux(x, y, z, axis, sign)`` [W/m2], heat INTO the domain, on every exterior and void-bounding face
    except the Robin face z = 0, ``(axis, sign)`` the outward normal; ``T_inf(x, y)`` [K] replacing the scalar ``T_c`` in
    ``h (T - T_inf)`` (``T_c`` stays the reference of the solved rise and the start of the Picard iteration). The callables
    take arrays of any shape. They are integrated with 4-point Gauss rules per direction (``DATA_INTORDER`` = 7: exact to
    degree 7 per direction on the axis-aligned cells and faces). ``meta`` splits ``Q_in`` into ``q_in_die_W``,
    ``q_in_volume_W`` and ``q_in_boundary_W`` (sum ``q_in_W``) next to ``q_out_W``; ``energy_balance`` is
    ``|q_out_W / q_in_W - 1|`` with the assembled ``Q_in``.

    ``extra_lines=(xs, ys, zs)`` [m] are mandatory grid lines, merged into the level-0 line set before subdivision, so a
    point on them is a node at every level (``node_value``); they must lie inside the baseplate box and the z extent. Each
    entry is None, a scalar or a sequence (the same in box-stack mode). A line closer than ``SNAP_FRACTION`` (1e-2) of the
    level-0 cell size of the geometry interval that contains it (lateral ``L / n``, z ``t / n``) to an existing line
    snaps onto it (``_merge_lines``): ``meta["snapped_lines"][axis]`` lists ``(requested, used)`` and ``meta["max_snap_m"]`` the largest
    distance, so a reported point (``node_value`` at the ``used`` coordinate) never moved by more than that.
    ``rule.dz_max`` bounds the z cell size in absolute terms (``GridRule``).

    ``power_W`` is one value per die (``layout.dies`` order) or a scalar for all. ``constant_k`` uses ``k = Layer.k``
    (``k_at(T_REF)``). Returns per-die ``tj_max`` / ``tj_mean`` (absolute K, same order as ``layout.dies``)."""
    g = layout_grid(layout, power_W, h, T_c, rule, level, extra_lines)
    if constant_k:
        g.kfun = [(lambda T, la=la: np.full_like(T, la.k)) for la in _materials(layout)]
    g.source, g.flux, g.T_inf = source, flux, T_inf
    r = _solve_grid(g, constant_k=constant_k, picard_tol=picard_tol)
    r.meta.update(level=level, cells=g.mat.shape)
    return r


def _materials(layout: Layout) -> list[Layer]:
    st = layout.stack
    return [st.layer(n) for n in ("baseplate", "solder", "backside_cu", "ceramic", "top_cu")] + [st.die_attach, st.die]


def convergence_study(layout: Layout, power_W: Sequence[float] | float, h: float, T_c: float, *,
                      rule: GridRule | None = None, levels: Sequence[int] = LEVELS) -> dict:
    """Solve three levels and return per-die Tj max, GCI and observed order (levels finest last in ``levels``)."""
    res = [solve_layout(layout, power_W, h, T_c, rule=rule, level=lv) for lv in levels]
    out = []
    for i in range(len(layout.dies)):
        vals = [res[2].tj_max[i], res[1].tj_max[i], res[0].tj_max[i]]  # finest, middle, coarsest
        c, p = _gci(vals)
        out.append({"tj_max_K": [float(r.tj_max[i]) for r in res], "gci_K": c, "p_obs": p})
    return {"levels": res, "dies": out}


# ------------------------------------------------------------------------------------------------ box-stack mode
@dataclass(frozen=True)
class BoxLayer:
    """One laterally uniform layer: thickness ``t`` [m] and conductivity ``k`` (a number or a callable ``k(T[K])``)."""

    t: float
    k: float | Callable
    n: int = 1  # cells in z at level 0 (times 2**level)
    name: str = ""


def box_stack_grid(a: float, b: float, layers: Sequence[BoxLayer], h: float, T_c: float,
                   sources: Sequence[tuple[float, float, float, float, float]], *, h0: float | None = None, level: int = 0,
                   constant_k: bool = False, element_order: int = 1, source: Callable | None = None,
                   flux: Callable | None = None, T_inf: Callable | None = None, rule: GridRule | None = None,
                   extra_lines: tuple | None = None) -> _Grid:
    """Conforming tensor grid of ``solve_box_stack`` (arguments there)."""
    if rule is None:
        if h0 is None:
            raise ValueError("give a GridRule (rule=) or h0")
        rule = GridRule(h0=h0, element_order=element_order)
    else:
        if h0 is not None and h0 != rule.h0:
            raise ValueError("h0 and rule.h0 disagree")
        if element_order != 1 and element_order != rule.element_order:
            raise ValueError("element_order and rule.element_order disagree")
    exs, eys, ezs = _split_extra(extra_lines)
    cx = [0.5 * (s[0] + s[2]) for s in sources]  # a source's centroid lines are always mandatory
    cy = [0.5 * (s[1] + s[3]) for s in sources]
    ext_x, ext_y = [(s[0], s[2]) for s in sources], [(s[1], s[3]) for s in sources]
    xb = _lines([0.0, a] + [s[0] for s in sources] + [s[2] for s in sources])
    yb = _lines([0.0, b] + [s[1] for s in sources] + [s[3] for s in sources])
    xl0, xsnap = _merge_lines(xb, np.concatenate([cx, [] if exs is None else exs]), 0.0, a, 1e-10,
                              _lateral_cell(xb, rule.h0, rule.min_cells, ext_x, rule.near_margin))
    yl0, ysnap = _merge_lines(yb, np.concatenate([cy, [] if eys is None else eys]), 0.0, b, 1e-10,
                              _lateral_cell(yb, rule.h0, rule.min_cells, ext_y, rule.near_margin))
    mx = _size_multipliers(xl0, ext_x, rule.near_margin)
    my = _size_multipliers(yl0, ext_y, rule.near_margin)
    xl, yl = _subdivide(xl0, rule.h0, level, rule.min_cells, mx), _subdivide(yl0, rule.h0, level, rule.min_cells, my)
    zb = np.concatenate(([0.0], np.cumsum([la.t for la in layers])))

    def base_n(m: float) -> int:
        return layers[min(int(np.searchsorted(zb, m) - 1), len(layers) - 1)].n

    zl0, zsnap = _merge_lines(zb, ezs, 0.0, float(zb[-1]), 1e-12, _z_cell(zb, _z_counts(zb, base_n, rule)))
    nzi = _z_counts(zl0, base_n, rule)
    zl = _subdivide_n(zl0, nzi, level, rule.zrefine)
    mat = np.empty((xl.size - 1, yl.size - 1, zl.size - 1), dtype=np.int32)
    zc = 0.5 * (zl[1:] + zl[:-1])
    for i in range(len(layers)):
        mat[:, :, (zc > zb[i]) & (zc < zb[i + 1])] = i

    def kf(la: BoxLayer):
        if callable(la.k):
            return (lambda T, la=la: np.full_like(T, la.k(T_c))) if constant_k else (lambda T, la=la: la.k(T))
        return lambda T, la=la: np.full_like(T, float(la.k))

    srcs = [(s[0], s[1], s[2], s[3], float(zb[-1]), float(s[4])) for s in sources]
    return _Grid(xl, yl, zl, mat, [kf(la) for la in layers], srcs, float(h), float(T_c), order=rule.element_order,
                 source=source, flux=flux, T_inf=T_inf, snaps={"x": xsnap, "y": ysnap, "z": zsnap})


def solve_box_stack(a: float, b: float, layers: Sequence[BoxLayer], h: float, T_c: float,
                    sources: Sequence[tuple[float, float, float, float, float]], *, h0: float | None = None, level: int = 0,
                    constant_k: bool = False, picard_tol: float = PICARD_TOL_K, element_order: int = 1,
                    source: Callable | None = None, flux: Callable | None = None,
                    T_inf: Callable | None = None, rule: GridRule | None = None,
                    extra_lines: tuple | None = None) -> ThermalResult:
    """Laterally uniform flux-channel mode (section 6): rectangle [0,a]x[0,b], bottom-up ``layers`` spanning it all,
    adiabatic sides, convective bottom (``h``, ``T_c``), sources ``(x0, y0, x1, y1, P)`` on the top face.

    Grid: the same ``GridRule`` and line builder as layout mode. Pass ``rule`` (``h0``, ``near_margin``, ``min_cells``,
    ``dz_max``, ``element_order``, ``zrefine``) or the legacy ``h0`` / ``element_order`` keywords (a rule with those two
    and the defaults otherwise). The level-0 z cells of a layer are its ``BoxLayer.n``, raised to ``ceil(t / dz_max)``
    when ``rule.dz_max`` is set (``rule.nz`` is not used here). Lateral lines are 0, a, b, the source edges, every
    source's centroid lines (always mandatory, so the legacy ``h0=`` grid now includes them) and ``extra_lines=(xs, ys, zs)`` [m]
    (scalar or sequence per axis, snapped as in ``solve_layout``), merged before subdivision. A
    ``constant_k`` with a callable ``k`` evaluates it at ``T_c``. ``meta`` carries the top-surface grid (``xs``, ``ys``,
    ``T_top[nx+1, ny+1]``, vertex values) for ``top_value`` (not for reported values: use ``node_value``).

    ``source``, ``flux`` and ``T_inf`` are the manufactured data of ``solve_layout`` (the flux applies to every face but
    the bottom, the top and sides included)."""
    g = box_stack_grid(a, b, layers, h, T_c, sources, h0=h0, level=level, constant_k=constant_k,
                       element_order=element_order, source=source, flux=flux, T_inf=T_inf, rule=rule,
                       extra_lines=extra_lines)
    r = _solve_grid(g, constant_k=constant_k, k_const_T=T_c, picard_tol=picard_tol)
    xl, yl, ztop = g.x, g.y, g.z[-1]
    nv = r.meta["n_vertices"]  # vertex dofs come first in both elements (dof i = mesh node i)
    nodes, Tv = r.nodes[:nv], r.T[:nv]
    top = np.isclose(nodes[:, 2], ztop)
    ix = np.searchsorted(xl, nodes[top, 0] - 1e-14)
    iy = np.searchsorted(yl, nodes[top, 1] - 1e-14)
    grid = np.full((xl.size, yl.size), np.nan)
    grid[ix, iy] = Tv[top]
    r.meta.update(xs=xl, ys=yl, T_top=grid, level=level)
    return r


def top_value(res: ThermalResult, x: float, y: float) -> float:
    """Bilinear lookup of the top-surface temperature of a box-stack result at (x, y). NOT FOR REPORTED VALUES: it
    interpolates between vertices (and ignores Q2 mid-nodes); report ``node_value`` at a mandatory grid line instead."""
    xs, ys, T = res.meta["xs"], res.meta["ys"], res.meta["T_top"]
    i = int(np.clip(np.searchsorted(xs, x) - 1, 0, xs.size - 2))
    j = int(np.clip(np.searchsorted(ys, y) - 1, 0, ys.size - 2))
    u = (x - xs[i]) / (xs[i + 1] - xs[i])
    v = (y - ys[j]) / (ys[j + 1] - ys[j])
    return float((1 - u) * (1 - v) * T[i, j] + u * (1 - v) * T[i + 1, j] + (1 - u) * v * T[i, j + 1]
                 + u * v * T[i + 1, j + 1])


def layout_polygons_for_tests(layout: Layout) -> Polygon:
    """Union of top-Cu trace polygons (helper for tests of mesh conformity)."""
    return shapely.union_all([t.polygon for t in layout.traces])
