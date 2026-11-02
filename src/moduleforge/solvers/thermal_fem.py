"""Independent scikit-fem (trilinear hexahedra) thermal cross-check of a Layout (D0006 fallback, docs/thermal_model.md).

This module implements ``docs/thermal_model.md`` on its own: it builds its own conforming hexahedral mesh, materials and
boundary conditions straight from the ``Layout`` and its ``LayerStack`` and runs its own Picard loop. It must never import
the finite-volume solver or its layout/grid builder (task A3 independence); it only reads ``moduleforge.geometry``.

Method. Steady ``div(k(x,T) grad T) = 0`` in the solid Omega; uniform flux ``q_i = P_i / (w_i h_i)`` over each die top
face; Robin sink ``k dT/dz = h (T - T_c)`` on the whole baseplate bottom; everything else adiabatic (natural BC).
Galerkin with trilinear hexahedra (scikit-fem ``ElementHex1``), 2x2x2 Gauss points, ``k`` evaluated at the quadrature
points from the previous Picard iterate (lagged; Picard fixed point = the continuum solution). Linear systems are solved
by CG preconditioned with smoothed-aggregation AMG (pyamg, MIT), warm-started from the previous iterate.

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

Outputs per die (section 5 of the definition): ``Tj_max`` = maximum nodal temperature on the die top face (the nodal
FEM reads the continuous surface field directly) and ``Tj_mean`` = area mean of T over the die top face (Galerkin
integral), plus the energy balance ``|Q_out / sum P - 1|`` (exact up to the linear-solver tolerance for a Galerkin
system whose stiffness rows sum to zero) and the Picard residual.

GCI: the order-capped rule of O006 A4 (D0012, D0013 and its addenda), shared with the finite-volume solver through
``thermal_layout.gci_three_grid`` (Roache 1998, ch. 5 for the safety factors 1.25 and 3, oscillatory, and the form
``|d2| / (2**p - 1)``; order capped at 1; grid steps below 1e-3 K count as zero; ``+inf`` for a divergent or stagnant
sequence). With f1, f2, f3 the finest, middle and coarsest values, the arguments of that function are (f3, f2, f1).

Memory. D0006 estimated about 7.7 kB per DOF for scikit-fem + pyamg; ``max_dofs(budget_bytes)`` converts a budget into
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
from shapely.geometry import Polygon
from skfem import Basis, BilinearForm, ElementHex1, MeshHex
from skfem.helpers import dot, grad

from moduleforge.geometry.layout import Layout
from moduleforge.geometry.stack import Layer
from moduleforge.solvers.thermal_layout import gci_three_grid

MM = 1.0e3  # the mesh is built in millimetres: k [W/(m K)] -> 1e-3 W/(mm K), h -> 1e-6 W/(mm2 K), areas in mm2
BYTES_PER_DOF = 7.7e3  # D0006 audit figure for scikit-fem + pyamg; the benchmark records the measured value
PICARD_TOL_K = 1.0e-4  # stop when max |dT| of an iteration is below this [K]
LINEAR_RTOL = 1.0e-11  # relative residual of every AMG-CG solve
REFINEMENT_RATIO = 2  # constant r of the three-level study
LEVELS = (0, 1, 2)
_HEX_CORNERS = ((0, 0, 0), (0, 1, 0), (1, 0, 0), (0, 0, 1), (1, 1, 0), (0, 1, 1), (1, 0, 1), (1, 1, 1))  # skfem order


def max_dofs(budget_bytes: float, bytes_per_dof: float = BYTES_PER_DOF) -> int:
    """Largest DOF count whose estimated memory (``bytes_per_dof`` each) fits ``budget_bytes``."""
    return int(budget_bytes // bytes_per_dof)


def physical_memory_bytes() -> float:
    return float(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES"))


# ------------------------------------------------------------------------------------------------ result container
@dataclass
class ThermalResult:
    """Solution summary. Temperatures in K (absolute)."""

    tj_max: np.ndarray  # per die / source, max over the top face nodes
    tj_mean: np.ndarray  # per die / source, area mean over the top face
    energy_balance: float  # |Q_out / sum(P) - 1|
    picard_iters: int
    picard_residual: float  # last max |dT| [K]
    dofs: int
    wall_s: float
    T: np.ndarray = field(repr=False, default_factory=lambda: np.zeros(0))
    nodes: np.ndarray = field(repr=False, default_factory=lambda: np.zeros((0, 3)))
    meta: dict = field(default_factory=dict)


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


# 2D Q1 mass matrix of a rectangle a x b, corners ordered (0,0), (1,0), (0,1), (1,1): (a b / 36) * _MASS_Q1
_MASS_Q1 = np.array([[4, 2, 2, 1], [2, 4, 1, 2], [2, 1, 4, 2], [1, 2, 2, 4]], dtype=float)


def _face_nodes(g: _Grid, dof_of: np.ndarray, ii, jj, kplane: int):
    """dofs (4, nfaces) of the corners (0,0),(1,0),(0,1),(1,1) of the x-y faces of cells (ii, jj) on node plane
    ``kplane`` and the face areas a*b in mm2 (the faces are exact rectangles; assembled directly, no inverse map)."""
    sy, sz = g.y.size, g.z.size
    ids = np.stack([((ii + dx) * sy + (jj + dy)) * sz + kplane for dy in (0, 1) for dx in (0, 1)])
    dofs = dof_of[ids]
    if (dofs < 0).any():
        raise RuntimeError("face node missing from the mesh")
    area = (np.diff(g.x)[ii] * np.diff(g.y)[jj]) * MM**2
    return dofs, area


def _gci(f: Sequence[float], r: float = REFINEMENT_RATIO) -> tuple[float, float]:
    """(GCI, p_obs) of values (finest, middle, coarsest) at ratio ``r = 2`` by O006's A4 rule
    (``thermal_layout.gci_three_grid``); ``p_obs`` is NaN when the convergence is not monotone."""
    f1, f2, f3 = (float(v) for v in f)
    g = gci_three_grid(f3, f2, f1, r)
    return g["gci"], g["p_obs"]


def gci(values: Sequence[float], r: float = REFINEMENT_RATIO) -> tuple[float, float]:
    """Public wrapper of the per-value Roache GCI: ``(gci, p_obs)`` for ``values = (finest, middle, coarsest)``."""
    return _gci(values, r)


# ------------------------------------------------------------------------------------------------ core solver
def _amg_cg(A: sp.csr_matrix, b: np.ndarray, x0: np.ndarray, ml) -> np.ndarray:
    x = ml.solve(b, x0=x0, tol=LINEAR_RTOL, maxiter=400, accel="cg")
    if np.linalg.norm(b - A @ x) > 1e-8 * np.linalg.norm(b):
        raise RuntimeError("AMG-CG did not converge to a relative residual of 1e-8")
    return x


def _solve_grid(g: _Grid, constant_k: bool, k_const_T: float | None = None, picard_tol: float = PICARD_TOL_K,
                max_picard: int = 60) -> ThermalResult:
    t0 = time.perf_counter()
    mesh, emat, dof_of = _build_mesh(g)
    basis = Basis(mesh, ElementHex1(), intorder=2)
    nd = basis.N
    ne = emat.size
    nqp = basis.X.shape[1]

    @BilinearForm
    def stiff(u, v, w):
        return w["k"] * dot(grad(u), grad(v))

    nd = int(nd)
    # Robin bottom: the whole z = 0 face of the active cells at k = 0 (the baseplate); mass matrix by direct assembly
    bi, bj = np.nonzero(g.mat[:, :, 0] >= 0)
    dofs, area = _face_nodes(g, dof_of, bi, bj, 0)
    ii = np.repeat(dofs[:, None, :], 4, axis=1).ravel()
    jj = np.repeat(dofs[None, :, :], 4, axis=0).ravel()
    vals = (area[None, None, :] / 36.0 * _MASS_Q1[:, :, None]).ravel()
    Mb = (g.h / MM**2) * sp.coo_matrix((vals, (ii, jj)), shape=(nd, nd)).tocsr()
    ones_b = np.bincount(dofs.ravel(), weights=np.tile(area / 4.0, 4), minlength=nd)  # integral of each hat over the face
    # heat input: uniform flux over each source's top face (cells whose top face lies on z = zt and has no active
    # cell above it, i.e. the face is on the mesh boundary)
    f = np.zeros(nd)
    src_vecs, src_nodes = [], []
    P_tot = 0.0
    nzc = g.mat.shape[2]
    xc, yc = 0.5 * (g.x[1:] + g.x[:-1]), 0.5 * (g.y[1:] + g.y[:-1])
    ztol = 1e-9 * g.z[-1]
    for (x0, y0, x1, y1, zt, P) in g.sources:
        kp = int(np.argmin(np.abs(g.z - zt)))
        if abs(g.z[kp] - zt) > ztol:
            raise ValueError("a heat source plane is not a z grid line")
        sx = np.nonzero((xc > x0) & (xc < x1))[0]
        sy_ = np.nonzero((yc > y0) & (yc < y1))[0]
        si, sj = np.meshgrid(sx, sy_, indexing="ij")
        si, sj = si.ravel(), sj.ravel()
        if si.size == 0 or kp == 0 or (g.mat[si, sj, kp - 1] < 0).any():
            raise ValueError("a heat source is not fully supported by active cells below its plane")
        if kp < nzc and (g.mat[si, sj, kp] >= 0).any():
            raise ValueError("a heat source face is not on the mesh boundary (active cells above it)")
        dofs, area = _face_nodes(g, dof_of, si, sj, kp)
        if abs(area.sum() - (x1 - x0) * (y1 - y0) * MM**2) > 1e-6 * area.sum():
            raise ValueError("a heat source is not fully covered by mesh faces (area mismatch)")
        vec = np.bincount(dofs.ravel(), weights=np.tile(area / 4.0, 4), minlength=nd)
        f += (P / area.sum()) * vec  # W/mm2 times mm2
        src_vecs.append(vec / area.sum())
        src_nodes.append(np.nonzero(vec)[0])
        P_tot += P
    rhs = f  # solve for the rise theta = T - Tc, whose Robin right-hand side vanishes

    theta = np.zeros(nd)
    picard = 0
    resid = float("inf")
    ml = None
    A = None
    kmax = len(g.kfun)
    while True:
        T_prev = g.Tc + theta
        if constant_k:
            Tq = np.full((ne, nqp), k_const_T if k_const_T is not None else g.Tc)
        else:
            Tq = np.asarray(basis.interpolate(T_prev))  # (ne, nqp) absolute T at quadrature points
        kq = np.empty((ne, nqp))
        for m in range(kmax):
            sel = emat == m
            if sel.any():
                kq[sel] = g.kfun[m](Tq[sel])
        A = (stiff.assemble(basis, k=kq / MM) + Mb).tocsr()
        ml = pyamg.smoothed_aggregation_solver(A, max_coarse=500)
        new = _amg_cg(A, rhs, theta, ml)
        picard += 1
        resid = float(np.max(np.abs(new - theta)))
        theta = new
        if constant_k or resid < picard_tol:
            break
        if picard >= max_picard:
            raise RuntimeError(f"Picard did not converge in {max_picard} iterations (last |dT| = {resid:.3e} K)")
    Tn = g.Tc + theta
    q_out = float(g.h / MM**2 * np.dot(ones_b, theta))
    eb = abs(q_out / P_tot - 1.0)
    tj_max = np.array([Tn[n].max() for n in src_nodes])
    tj_mean = np.array([float(np.dot(v, Tn)) for v in src_vecs])
    wall = time.perf_counter() - t0
    return ThermalResult(tj_max, tj_mean, eb, picard, resid, nd, wall, T=Tn, nodes=mesh.p.T / MM,
                         meta={"n_elements": int(ne), "q_out_W": q_out, "P_total_W": P_tot})


# ------------------------------------------------------------------------------------------------ layout mode
def _k_of(layer: Layer) -> Callable:
    return lambda T: layer.k_at(T)


def layout_grid(layout: Layout, power_W: Sequence[float] | float, h: float, T_c: float,
                rule: GridRule | None = None, level: int = 0) -> _Grid:
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
    zl0 = _lines(zl_pts, 1e-12)
    # cells per z interval at level 0
    nzi = []
    for a, b in zip(zl0[:-1], zl0[1:], strict=True):
        mid = 0.5 * (a + b)
        n = 1
        for lo, hi, nn in [(zb[i], zb[i + 1], zcounts[i]) for i in range(len(zcounts))] + extra:
            if lo - 1e-12 <= mid <= hi + 1e-12:
                n = nn
                break
        nzi.append(n)
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
    xl0, yl0 = _lines(xs), _lines(ys)
    mx = _size_multipliers(xl0, [(d.bounds[0], d.bounds[2]) for d in layout.dies], rule.near_margin)
    my = _size_multipliers(yl0, [(d.bounds[1], d.bounds[3]) for d in layout.dies], rule.near_margin)
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
                 ["baseplate", "solder", "backside_cu", "ceramic", "top_cu", "die_attach", "die"])


def estimate_dofs(layout: Layout, rule: GridRule | None = None, level: int = 0) -> int:
    """Node count of the level-``level`` mesh from the grid counts alone (no matrices built; used to skip levels)."""
    g = layout_grid(layout, 1.0, 1.0, 300.0, rule, level)
    return _count_nodes(g.mat)


def _count_nodes(mat: np.ndarray) -> int:
    act = mat >= 0
    pad = np.zeros((act.shape[0] + 1, act.shape[1] + 1, act.shape[2] + 1), dtype=bool)
    for dx in (0, 1):
        for dy in (0, 1):
            for dz in (0, 1):
                pad[dx:dx + act.shape[0], dy:dy + act.shape[1], dz:dz + act.shape[2]] |= act
    return int(pad.sum())


def solve_layout(layout: Layout, power_W: Sequence[float] | float, h: float, T_c: float, *, rule: GridRule | None = None,
                 level: int = 0, constant_k: bool = False, picard_tol: float = PICARD_TOL_K) -> ThermalResult:
    """Layout mode: solve docs/thermal_model.md on the level-``level`` conforming mesh.

    ``power_W`` is one value per die (``layout.dies`` order) or a scalar for all. ``constant_k`` uses ``k = Layer.k``
    (``k_at(T_REF)``). Returns per-die ``tj_max`` / ``tj_mean`` (absolute K, same order as ``layout.dies``)."""
    g = layout_grid(layout, power_W, h, T_c, rule, level)
    if constant_k:
        g.kfun = [(lambda T, la=la: np.full_like(T, la.k)) for la in _materials(layout)]
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


def solve_box_stack(a: float, b: float, layers: Sequence[BoxLayer], h: float, T_c: float,
                    sources: Sequence[tuple[float, float, float, float, float]], *, h0: float, level: int = 0,
                    constant_k: bool = False, picard_tol: float = PICARD_TOL_K) -> ThermalResult:
    """Laterally uniform flux-channel mode (section 6): rectangle [0,a]x[0,b], bottom-up ``layers`` spanning it all,
    adiabatic sides, convective bottom (``h``, ``T_c``), sources ``(x0, y0, x1, y1, P)`` on the top face.

    ``h0`` is the level-0 lateral cell size (intervals between 0, a, b and the source edges get ``ceil(L/h0)`` cells,
    times ``2**level``). ``constant_k`` with a callable ``k`` evaluates it at ``T_c``. ``meta`` carries the top-surface
    grid (``xs``, ``ys``, ``T_top[nx+1, ny+1]``) for point lookups with ``top_value``."""
    xl0 = _lines([0.0, a] + [s[0] for s in sources] + [s[2] for s in sources])
    yl0 = _lines([0.0, b] + [s[1] for s in sources] + [s[3] for s in sources])
    xl, yl = _subdivide(xl0, h0, level), _subdivide(yl0, h0, level)
    zb = np.concatenate(([0.0], np.cumsum([la.t for la in layers])))
    zl = _subdivide_n(zb, [la.n for la in layers], level)
    mat = np.empty((xl.size - 1, yl.size - 1, zl.size - 1), dtype=np.int32)
    zc = 0.5 * (zl[1:] + zl[:-1])
    for i in range(len(layers)):
        mat[:, :, (zc > zb[i]) & (zc < zb[i + 1])] = i

    def kf(la: BoxLayer):
        if callable(la.k):
            return (lambda T, la=la: np.full_like(T, la.k(T_c))) if constant_k else (lambda T, la=la: la.k(T))
        return lambda T, la=la: np.full_like(T, float(la.k))

    srcs = [(s[0], s[1], s[2], s[3], float(zb[-1]), float(s[4])) for s in sources]
    g = _Grid(xl, yl, zl, mat, [kf(la) for la in layers], srcs, float(h), float(T_c))
    r = _solve_grid(g, constant_k=constant_k, k_const_T=T_c, picard_tol=picard_tol)
    top = np.isclose(r.nodes[:, 2], zb[-1])
    ix = np.searchsorted(xl, r.nodes[top, 0] - 1e-14)
    iy = np.searchsorted(yl, r.nodes[top, 1] - 1e-14)
    grid = np.full((xl.size, yl.size), np.nan)
    grid[ix, iy] = r.T[top]
    r.meta.update(xs=xl, ys=yl, T_top=grid, level=level)
    return r


def top_value(res: ThermalResult, x: float, y: float) -> float:
    """Bilinear lookup of the top-surface temperature of a box-stack result at (x, y)."""
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
