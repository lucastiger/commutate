"""Thermal L2 core: steady finite-volume conduction on a non-uniform rectilinear grid, k(T) by Picard iteration.

D0006 primary L2 (steady part; transient is out of scope).  SI units (m, W, K), float64.  numpy/scipy/pyamg only.

Model
-----
Steady conduction  -div(k(T) grad T) = f  in the non-void cells of a tensor grid (lines ``x``, ``y``, ``z``,
non-uniform, strictly increasing).  Cell-centred finite volumes: one unknown T per non-void cell.

* Face conductance between neighbouring cells a, b is the series of the two half-cells,
  ``G = A / (d_a / (2 k_a) + d_b / (2 k_b))`` (d = cell size normal to the face, A = face area; Patankar,
  *Numerical Heat Transfer and Fluid Flow*, 1980, Sec. 4.2.3, Eq. 4.9).  This is exact for 1D piecewise-constant k
  with material interfaces on grid lines (series thermal resistance, Incropera et al., *Fundamentals of Heat and
  Mass Transfer*, Sec. 3.1.3 composite wall).
* Void cells (``cell_material < 0``) are excluded; every face between an active cell and a void cell is adiabatic
  unless a prescribed flux is given for it.
* k(T): ``k`` of each half-cell is evaluated at the temperature of its own cell.  Picard iteration, starting from
  ``T_init`` (default: the mean sink temperature): assemble with k(T_n), solve, repeat until
  ``max |T_{n+1} - T_n| < picard_tol`` (default 1e-4 K, the F2 criterion).  A material that is a plain number is
  temperature independent; if all are, exactly one solve is made.  ``meta['picard_iters']`` counts the solves.
* Linear solve: scipy.sparse CSR; ``scipy.sparse.linalg.cg`` preconditioned by one pyamg smoothed-aggregation V-cycle
  (symmetric strength threshold 0.05, strength-filtered Jacobi prolongation smoothing, symmetric Gauss-Seidel; the
  hierarchy is reused across Picard steps while it stays effective, rebuilt otherwise), relative residual
  ``||b - A u|| / ||b|| <= max(linear_tol, floor)`` (default ``linear_tol`` 1e-12) verified on the true residual, where
  ``floor = m eps || |A| |u| || / ||b||`` is the rounding bound of the computed residual (Higham 2002, Sec. 3.5; it
  exceeds 1e-12 only for stiff systems: high conductivity contrast or cell aspect ratio); ``RuntimeError`` if it is
  not reached (an unconverged field is never returned).  The unknown is ``u = T - T0`` with T0 the mean sink temperature,
  to avoid the 300 K offset in the residual.  Systems up to 2000 unknowns use a sparse direct solve.

Boundary and source data contract (this is what the manufactured reference n6 relies on)
-----------------------------------------------------------------------------------------
Axes are 0, 1, 2 = x, y, z; a *face* is identified by ``(axis, sign)`` of its **outward** normal as seen from the cell
(sign = -1 the low side, +1 the high side).  Exposed faces = faces of active cells on the box boundary or adjacent to a
void cell.

(a) Robin at z = 0 (the low-z face of every active cell with k index 0): heat leaves at ``h (T_face - T_inf)``.
    ``h`` [W/m2K] and ``T_inf`` [K] are each a scalar or a callable ``f(x, y)`` (1-D numpy arrays in, array out).
    The face value used is the mean over a tensor Gauss-Legendre rule (``n_gauss`` points per direction) of
    ``h`` and of ``h * T_inf`` (``T_inf_eff = <h T_inf> / <h>``).  Face conductance: the half-cell in series with
    1/h, ``G = A / (dz/(2k) + 1/h)``.  Every face-connected group of active cells must contain a Robin face (else the
    problem is singular); ``ValueError`` otherwise, e.g. for a die island floating above a void.
(b) Prescribed normal flux ``flux``, **heat flow into the domain in W/m2** (positive heats the cell), on any exposed
    face (default 0), additive to the Robin condition on z = 0, where it is applied at the face (combined face
    condition ``T_inf_eff = T_inf + q/h``, second order; elsewhere it enters the adjacent cell).  Either
    * a callable ``flux(x, y, z, axis, sign)`` applied to every exposed face, called per face orientation with 1-D
      arrays of face Gauss points, or
    * a dict ``{(axis, sign): spec}``; spec is a scalar, a callable ``f(x, y, z)`` (1-D arrays) or an array of the
      cell-grid shape ``(nx, ny, nz)`` giving the flux through that side of each cell (per-face array); the array
      must be zero on faces that are not exposed (ValueError otherwise).
    The face flux is the mean over ``n_gauss x n_gauss`` Gauss-Legendre points on the face, so a rectangular
    top-surface isoflux source conforming to grid lines is the special case ``{(2, +1): lambda x, y, z: q * inside}``.
(c) Volumetric source ``source`` [W/m3]: a scalar, an array of shape ``(nx, ny, nz)`` (uniform in each cell), or a
    callable ``f(x, y, z)`` (1-D arrays over the Gauss points) integrated per cell with the tensor Gauss-Legendre
    rule of ``n_gauss`` (>= 3) points per direction (exact for polynomials of degree 2*n_gauss-1 per direction).

Outputs (``ThermalResult``)
---------------------------
``T`` (nx, ny, nz) cell temperatures (NaN in void); ``surface`` the top-surface field: per (x, y) column, the highest
active cell's +z face temperature ``T_c + q dz / (2 k(T_c))`` with ``q`` the prescribed inflow on that face (O006 A1;
NaN for columns that are entirely void); ``surface(xq, yq)`` second-order bilinear interpolation of that field between
column centres (linear extrapolation in the outer half cells; a stencil node on a different surface level, such as a
die top next to copper, or in a void column is replaced by the value of the column that contains the query point);
``surface_stats(x0, x1, y0, y1)`` area mean (exact integral of that interpolant over the non-void part of the
rectangle) and maximum (attained at a corner of a bilinear piece); ``meta`` with ``n_cells``, ``picard_iters``,
``linear_residual`` (relative, last solve) and ``linear_residual_accepted`` (the threshold it met), ``linear_iters``,
``energy_balance`` = |Q_out / Q_in - 1| (Q_in = all volumetric power + signed prescribed flux, Q_out = Robin outflow;
|Q_out| if Q_in = 0), ``q_in``, ``q_out``, ``wall_time_s``.  The balance equals the residual sum of the linear system,
so it is limited by the linear tolerance.

References: Patankar (1980); Incropera et al. (see above); Abramowitz & Stegun 25.4.29 (Gauss-Legendre);
Bagnall, Muzychka & Wang, IEEE TCPMT 4(3):408 (2014) (Kirchhoff transform, used in the tests).
"""
from __future__ import annotations

import time
from collections.abc import Sequence
from dataclasses import dataclass, field

import numpy as np
import pyamg
import scipy.sparse as sp
import scipy.sparse.linalg as spla
from scipy.sparse.csgraph import connected_components

_DIRECT_MAX = 2000
_INNER_TOL = 1e-8  # relative linear tolerance of intermediate Picard solves
_SAME_LEVEL_TOL = 1e-9  # m, two surface heights closer than this are the same surface level
# AMG strength threshold: layer-conforming grids have cells of aspect ratio ~10-50 (10 um solder cells under 0.4 mm
# lateral cells).  The pyamg default theta = 0 aggregates across the weak lateral couplings and needs 50-130 CG
# iterations per 1e-8; theta = 0.05 with strength-filtered Jacobi prolongation smoothing needs 15-25 on the T0149
# benchmark systems (layered 0.3 M and 1.2 M cells, die-on-copper module 0.5 M, isotropic 0.26 M).
_AMG_THETA = 0.05
_CG_MAXITER = 300  # per CG pass
_CG_RESTARTS = 6  # CG passes (with a hierarchy rebuild if the previous one was weak) before giving up


@dataclass
class SurfaceField:
    """Top-surface temperature per column with second-order bilinear interpolation (module docstring)."""

    x: np.ndarray  # grid lines
    y: np.ndarray
    values: np.ndarray  # (nx, ny), NaN where the column is void
    height: np.ndarray  # (nx, ny) z of the surface, NaN where void

    def __post_init__(self):
        self.xc = 0.5 * (self.x[:-1] + self.x[1:])
        self.yc = 0.5 * (self.y[:-1] + self.y[1:])

    @staticmethod
    def _stencil(c, q, m):
        n = len(c)
        if n == 1:
            z = np.zeros(np.shape(q), dtype=int)
            return z, z, np.zeros(np.shape(q))
        i0 = np.clip(np.searchsorted(c, m, side="right") - 1, 0, n - 2)
        return i0, i0 + 1, (q - c[i0]) / (c[i0 + 1] - c[i0])

    def _eval(self, xq, yq, xm, ym):
        """Interpolant at (xq, yq) using the bilinear piece / containing column of the midpoint (xm, ym)."""
        nx, ny = self.values.shape
        ci = np.clip(np.searchsorted(self.x, xm, side="right") - 1, 0, nx - 1)
        cj = np.clip(np.searchsorted(self.y, ym, side="right") - 1, 0, ny - 1)
        i0, i1, tx = self._stencil(self.xc, xq, xm)
        j0, j1, ty = self._stencil(self.yc, yq, ym)
        own, own_z = self.values[ci, cj], self.height[ci, cj]

        def node(i, j):
            v = self.values[i, j]
            ok = np.isfinite(v) & (np.abs(self.height[i, j] - own_z) <= _SAME_LEVEL_TOL)
            return np.where(ok, v, own)

        return ((1 - tx) * (1 - ty) * node(i0, j0) + tx * (1 - ty) * node(i1, j0)
                + (1 - tx) * ty * node(i0, j1) + tx * ty * node(i1, j1))

    def _check(self, xq, yq):
        eps = 1e-12 * max(self.x[-1] - self.x[0], self.y[-1] - self.y[0])
        if (np.any(xq < self.x[0] - eps) or np.any(xq > self.x[-1] + eps)
                or np.any(yq < self.y[0] - eps) or np.any(yq > self.y[-1] + eps)):
            raise ValueError("query point outside the grid")

    def __call__(self, xq, yq):
        """Interpolated surface temperature at points (xq, yq) [m] (broadcast); NaN over void columns."""
        xq, yq = np.broadcast_arrays(np.asarray(xq, float), np.asarray(yq, float))
        self._check(xq, yq)
        out = self._eval(xq, yq, xq, yq)
        return float(out) if out.ndim == 0 else out

    def mean_max(self, x0, x1, y0, y1):
        """(area mean, maximum) of the interpolant over [x0,x1]x[y0,y1], restricted to non-void columns.

        A bilinear function's mean over a rectangle is the mean of its four corner values and its maximum is at a
        corner, so both are exact for the interpolant on the pieces cut by the grid lines and column centres."""
        if not (x1 > x0 and y1 > y0):
            raise ValueError("rectangle must have positive extent")
        self._check(np.array([x0, x1]), np.array([y0, y1]))

        def breaks(lines, centres, a, b):
            inner = np.concatenate([lines, centres])
            return np.unique(np.concatenate([[a, b], inner[(inner > a) & (inner < b)]]))

        bx, by = breaks(self.x, self.xc, x0, x1), breaks(self.y, self.yc, y0, y1)
        mx, my = 0.5 * (bx[:-1] + bx[1:]), 0.5 * (by[:-1] + by[1:])
        MX, MY = np.meshgrid(mx, my, indexing="ij")
        w = np.diff(bx)[:, None] * np.diff(by)[None, :]
        corners = []
        for xa in (bx[:-1], bx[1:]):
            for ya in (by[:-1], by[1:]):
                XA, YA = np.meshgrid(xa, ya, indexing="ij")
                corners.append(self._eval(XA, YA, MX, MY))
        corners = np.stack(corners)
        avg = corners.mean(axis=0)
        valid = np.isfinite(avg)
        if not valid.any():
            raise ValueError("rectangle contains no surface")
        return float((w[valid] * avg[valid]).sum() / w[valid].sum()), float(corners[:, valid].max())


@dataclass
class ThermalResult:
    x: np.ndarray
    y: np.ndarray
    z: np.ndarray
    T: np.ndarray
    surface: SurfaceField
    meta: dict = field(default_factory=dict)

    @property
    def energy_balance(self) -> float:
        return self.meta["energy_balance"]

    def surface_temperature(self, xq, yq):
        return self.surface(xq, yq)

    def surface_stats(self, x0, x1, y0, y1):
        return self.surface.mean_max(x0, x1, y0, y1)


def _lines(v, name):
    v = np.asarray(v, dtype=float)
    if v.ndim != 1 or v.size < 2 or np.any(np.diff(v) <= 0):
        raise ValueError(f"grid lines {name} must be 1-D, strictly increasing, with at least 2 entries")
    return v


def _material_k(materials, matid, T):
    """Conductivity of each active cell at temperature T (array over active cells)."""
    k = np.empty(matid.shape)
    for m, mat in enumerate(materials):
        sel = matid == m
        if not sel.any():
            continue
        if hasattr(mat, "k_at"):
            k[sel] = mat.k_at(T[sel])
        elif callable(mat):
            k[sel] = mat(T[sel])
        else:
            k[sel] = float(mat)
    if not np.all(k > 0) or not np.all(np.isfinite(k)):
        raise ValueError("conductivity must be positive and finite")
    return k


def _is_const(mat) -> bool:
    return not (hasattr(mat, "k_at") or callable(mat))


def _eval(fn, *coords):
    """Scalar or callable -> array broadcast to the shape of the coordinates."""
    shape = np.shape(coords[0])
    if callable(fn):
        return np.broadcast_to(np.asarray(fn(*coords), dtype=float), shape)
    return np.full(shape, float(fn))


def _residual_floor(A, u, nb):
    """Relative rounding bound of the computed residual ``b - A u``: ``|fl(A u) - A u| <= gamma_m |A| |u|`` with
    ``gamma_m ~ m eps``, m = the largest number of nonzeros in a row (Higham, *Accuracy and Stability of Numerical
    Algorithms*, 2nd ed., 2002, Sec. 3.5, Eq. 3.11).  A smaller residual cannot be verified in float64."""
    m = int(np.diff(A.indptr).max())
    return m * np.finfo(float).eps * float(np.linalg.norm(abs(A) @ np.abs(u))) / nb


class _Solver:
    """Cached linear solver: pyamg smoothed-aggregation preconditioned CG, hierarchy reused while effective."""

    def __init__(self):
        self.ml = None
        self.rebuild = True
        self.iters = 0
        self.fresh_iters = 0

    def solve(self, A, b, x0, tol):
        """Return ``(u, res, accepted)``: the solution, its true relative residual and the threshold it was held to,
        ``accepted = max(tol, rounding floor of the residual)``; the caller raises if ``res > accepted``."""
        nb = np.linalg.norm(b)
        if nb == 0.0:
            return np.zeros_like(b), 0.0, tol
        if A.shape[0] <= _DIRECT_MAX:
            u = spla.spsolve(A.tocsc(), b)
            res = np.linalg.norm(b - A @ u) / nb
            return u, res, tol if res <= tol else max(tol, _residual_floor(A, u, nb))
        u = x0.copy()
        accepted = tol
        for _ in range(_CG_RESTARTS):
            fresh = self.rebuild or self.ml is None
            if fresh:
                self.ml = pyamg.smoothed_aggregation_solver(
                    A, symmetry="symmetric", strength=("symmetric", {"theta": _AMG_THETA}),
                    smooth=("jacobi", {"filter_entries": True}), max_coarse=500, improve_candidates=None,
                    presmoother=("gauss_seidel", {"sweep": "forward"}),
                    postsmoother=("gauss_seidel", {"sweep": "backward"}))
                for lvl in self.ml.levels:  # pyamg keeps 1x1-block BSR operators; CSR kernels are faster, same maths
                    lvl.A = lvl.A.tocsr()
                    if hasattr(lvl, "P"):
                        lvl.P, lvl.R = lvl.P.tocsr(), lvl.R.tocsr()
                self.rebuild = False
            count = [0]

            def cb(_xk, count=count):
                count[0] += 1

            u, info = spla.cg(A, b, x0=u, rtol=tol, atol=0.0, maxiter=_CG_MAXITER,
                              M=self.ml.aspreconditioner(cycle="V"), callback=cb)
            self.iters += count[0]
            res = np.linalg.norm(b - A @ u) / nb
            if fresh:
                self.fresh_iters = count[0]
            if info != 0 or count[0] > 2 * self.fresh_iters + 10:
                self.rebuild = True  # stale or weak hierarchy: rebuild before the next solve
            if res <= tol:
                return u, res, tol
            accepted = max(tol, _residual_floor(A, u, nb))  # CG's recursive residual met tol, the true one stagnates
            if res <= accepted:
                return u, res, accepted
        return u, res, accepted


def solve_steady(x, y, z, cell_material, materials: Sequence, *, h, T_inf, flux=None, source=None,
                 T_init: float | None = None, picard_tol: float = 1e-4, max_picard: int = 100,
                 linear_tol: float = 1e-12, n_gauss: int = 3) -> ThermalResult:
    """Solve the steady problem described in the module docstring.

    ``cell_material`` is an int array (nx, ny, nz); ``-1`` (any negative) marks void.  ``materials[i]`` is a number
    (constant k), an object with ``k_at(T)`` (``geometry.stack.Layer``) or a callable ``k(T)`` (vectorised)."""
    t_start = time.perf_counter()
    if n_gauss < 3:
        raise ValueError("n_gauss must be at least 3")
    x, y, z = _lines(x, "x"), _lines(y, "y"), _lines(z, "z")
    nx, ny, nz = len(x) - 1, len(y) - 1, len(z) - 1
    shape = (nx, ny, nz)
    mat = np.asarray(cell_material)
    if mat.shape != shape:
        raise ValueError(f"cell_material has shape {mat.shape}, expected {shape}")
    mat = mat.astype(np.int64)
    if mat.max() >= len(materials):
        raise ValueError("cell_material refers to a material that is not in `materials`")
    act = mat >= 0
    n = int(act.sum())
    if n == 0:
        raise ValueError("no active cells")
    idx = np.full(shape, -1, dtype=np.int64)
    idx[act] = np.arange(n)
    hx, hy, hz = np.diff(x), np.diff(y), np.diff(z)
    xc, yc, zc = 0.5 * (x[:-1] + x[1:]), 0.5 * (y[:-1] + y[1:]), 0.5 * (z[:-1] + z[1:])
    gp, gw = np.polynomial.legendre.leggauss(n_gauss)
    gw = gw / 2.0  # weights of the mean over [-1, 1]

    Ia, Ja, Ka = np.nonzero(act)  # active cells in compact order (C order == idx order)
    matid = mat[act]
    size = (hx[Ia], hy[Ja], hz[Ka])
    centre = (xc[Ia], yc[Ja], zc[Ka])
    vol = size[0] * size[1] * size[2]

    # ---- Robin at z = 0 -------------------------------------------------------------------------------------------
    bot = act[:, :, 0]
    bi, bj = np.nonzero(bot)
    if bi.size == 0:
        raise ValueError("no active cell touches z = 0: the Robin boundary is empty and the problem is singular")
    rob_cell = idx[bi, bj, 0]
    h_f = np.zeros(bi.size)
    hT_f = np.zeros(bi.size)
    for a, wa in zip(gp, gw, strict=True):
        for b_, wb in zip(gp, gw, strict=True):
            xq, yq = xc[bi] + 0.5 * hx[bi] * a, yc[bj] + 0.5 * hy[bj] * b_
            hq, tq = _eval(h, xq, yq), _eval(T_inf, xq, yq)
            h_f += wa * wb * hq
            hT_f += wa * wb * hq * tq
    if np.any(h_f <= 0) or not np.all(np.isfinite(h_f)):
        raise ValueError("h must be positive and finite")
    tinf_f = hT_f / h_f
    rob_area = hx[bi] * hy[bj]
    T0 = float(tinf_f.mean())

    # ---- prescribed flux on exposed faces ---------------------------------------------------------------------------
    if isinstance(flux, dict):
        bad_keys = [key for key in flux if key not in {(a, s) for a in range(3) for s in (-1, 1)}]
        if bad_keys:
            raise ValueError(f"flux keys must be (axis, sign) with axis in 0, 1, 2 and sign in -1, +1; got {bad_keys}")
    elif flux is not None and not callable(flux):
        raise ValueError("flux must be None, a callable flux(x, y, z, axis, sign) or a dict {(axis, sign): spec}")
    pad = np.pad(act, 1, constant_values=False)
    F = np.zeros(n)  # W into each cell
    q_rob = np.zeros((nx, ny))  # W/m2 prescribed inflow on the z = 0 Robin face, folded into the face condition
    q_top = np.zeros(shape)  # W/m2 into the cell through its +z face
    for axis in range(3):
        for sign in (-1, 1):
            nb_act = pad[tuple(slice(2, None) if (a == axis and sign > 0) else slice(0, -2) if a == axis
                               else slice(1, -1) for a in range(3))]
            exposed = act & ~nb_act
            spec = flux
            if isinstance(flux, dict):
                spec = flux.get((axis, sign))
                if isinstance(spec, np.ndarray) and spec.ndim == 0:  # 0-d numpy scalar spec == plain scalar
                    spec = float(spec)
            if spec is None or not exposed.any():
                if isinstance(spec, np.ndarray) and np.any(spec != 0):
                    raise ValueError(f"flux array for face {(axis, sign)} is nonzero on non-exposed faces")
                continue
            ei, ej, ek = np.nonzero(exposed)
            ec = (xc[ei], yc[ej], zc[ek])
            ehalf = (0.5 * hx[ei], 0.5 * hy[ej], 0.5 * hz[ek])
            others = [a for a in range(3) if a != axis]
            area = np.ones(ei.size)
            for a in others:
                area = area * 2.0 * ehalf[a]
            face_coord = (x, y, z)[axis][(ei, ej, ek)[axis] + (1 if sign > 0 else 0)]
            if isinstance(spec, np.ndarray):
                if spec.shape != shape:
                    raise ValueError(f"flux array for face {(axis, sign)} must have shape {shape}")
                if np.any(spec[~exposed] != 0):
                    raise ValueError(f"flux array for face {(axis, sign)} is nonzero on non-exposed faces")
                qm = spec[exposed].astype(float)
            else:
                qm = np.zeros(ei.size)
                for a, wa in zip(gp, gw, strict=True):
                    for b_, wb in zip(gp, gw, strict=True):
                        pts = [None, None, None]
                        pts[axis] = face_coord
                        pts[others[0]] = ec[others[0]] + ehalf[others[0]] * a
                        pts[others[1]] = ec[others[1]] + ehalf[others[1]] * b_
                        if isinstance(flux, dict):
                            qq = _eval(spec, *pts)
                        else:
                            qq = np.broadcast_to(np.asarray(flux(*pts, axis, sign), float), ei.size)
                        qm += wa * wb * qq
            if axis == 2 and sign < 0:  # Robin face: combined face condition below, not a cell-centre source
                on_rob = ek == 0
                q_rob[ei[on_rob], ej[on_rob]] = qm[on_rob]
                ei, ej, ek, qm, area = ei[~on_rob], ej[~on_rob], ek[~on_rob], qm[~on_rob], area[~on_rob]
            np.add.at(F, idx[ei, ej, ek], qm * area)
            if axis == 2 and sign > 0:
                q_top[ei, ej, ek] = qm

    # Combined Robin-plus-flux face condition (review T0160).  Face balance  h (T_inf - T_f) + q = G_h (T_f - T_c)  with
    # G_h = 2k/dz the half-cell conductance gives heat into the cell  g (T_inf + q/h - T_c),  g = 1/(1/G_h + 1/h):
    # the flux acts at the face (second order), not at the cell centre (first order).  Gauss-averaged like h T_inf.
    q_rob_f = q_rob[bi, bj]
    tinf_eff = (hT_f + q_rob_f) / h_f
    q_rob_w = float((q_rob_f * rob_area).sum())

    # ---- volumetric source ------------------------------------------------------------------------------------------
    if source is None:
        Qv = np.zeros(n)
    elif callable(source):
        Qv = np.zeros(n)
        for a, wa in zip(gp, gw, strict=True):
            for b_, wb in zip(gp, gw, strict=True):
                for c_, wc in zip(gp, gw, strict=True):
                    pts = [centre[d] + 0.5 * size[d] * g for d, g in enumerate((a, b_, c_))]
                    Qv += wa * wb * wc * np.broadcast_to(np.asarray(source(*pts), float), n)
        Qv *= vol
    elif isinstance(source, np.ndarray):
        if source.shape != shape:
            raise ValueError(f"source array must have shape {shape}")
        Qv = source[act].astype(float) * vol
    else:
        Qv = float(source) * vol

    # ---- fixed connectivity -----------------------------------------------------------------------------------------
    pairs = []
    for axis in range(3):
        lo = tuple(slice(0, -1) if a == axis else slice(None) for a in range(3))
        hi = tuple(slice(1, None) if a == axis else slice(None) for a in range(3))
        both = act[lo] & act[hi]
        others = [a for a in range(3) if a != axis]
        h3 = (hx[:, None, None], hy[None, :, None], hz[None, None, :])
        area = h3[others[0]] * h3[others[1]]
        dd = np.diff((x, y, z)[axis])
        shp = [1, 1, 1]
        shp[axis] = -1
        d_lo = dd[:-1].reshape(shp)
        d_hi = dd[1:].reshape(shp)
        pairs.append((idx[lo][both], idx[hi][both], both, np.broadcast_to(area, both.shape)[both],
                      np.broadcast_to(d_lo, both.shape)[both], np.broadcast_to(d_hi, both.shape)[both],
                      lo, hi))

    # every face-connected component of active cells needs a Robin face, else the system is singular (review T0158)
    if n > 1:
        ia_all = np.concatenate([p[0] for p in pairs])
        ib_all = np.concatenate([p[1] for p in pairs])
        graph = sp.coo_matrix((np.ones(ia_all.size), (ia_all, ib_all)), shape=(n, n))
        n_comp, comp = connected_components(graph, directed=False)
        floating = np.setdiff1d(np.arange(n_comp), comp[rob_cell])
        if floating.size:
            raise ValueError(f"{floating.size} face-connected group(s) of active cells ({int(np.isin(comp, floating).sum())}"
                             " cells) have no conduction path to the Robin boundary at z = 0: the problem is singular")

    def assemble(k_a):
        kfull = np.ones(shape)
        kfull[act] = k_a
        rows, cols, vals = [], [], []
        diag = np.zeros(n)
        for ia, ib, both, area, d_lo, d_hi, lo, hi in pairs:
            ka, kb = kfull[lo][both], kfull[hi][both]
            G = area / (0.5 * d_lo / ka + 0.5 * d_hi / kb)
            rows += [ia, ib]
            cols += [ib, ia]
            vals += [-G, -G]
            diag += np.bincount(ia, G, n) + np.bincount(ib, G, n)
        g_rob = rob_area / (0.5 * hz[0] / k_a[rob_cell] + 1.0 / h_f)
        diag[rob_cell] += g_rob
        rows.append(np.arange(n))
        cols.append(np.arange(n))
        vals.append(diag)
        A = sp.csr_matrix((np.concatenate(vals), (np.concatenate(rows), np.concatenate(cols))), shape=(n, n))
        return A, g_rob

    # ---- Picard loop ------------------------------------------------------------------------------------------------
    nonlinear = any(not _is_const(m) for m in materials)
    Tc = np.full(n, T0 if T_init is None else float(T_init))
    solver = _Solver()
    u = Tc - T0
    iters = 0
    while True:
        iters += 1
        k_a = _material_k(materials, matid, Tc)
        A, g_rob = assemble(k_a)
        b = Qv + F
        b[rob_cell] += g_rob * (tinf_eff - T0)
        # inexact Picard: intermediate iterates need only ~1e-8 relative accuracy; the converged one is polished
        inner_tol = linear_tol if not nonlinear else max(linear_tol, _INNER_TOL)
        u, res, accepted = solver.solve(A, b, u, inner_tol)
        T_new = u + T0
        dT = float(np.max(np.abs(T_new - Tc)))
        T_prev, Tc = Tc, T_new
        if not nonlinear or dT < picard_tol:
            if res > linear_tol and inner_tol > linear_tol:
                u, res, accepted = solver.solve(A, b, u, linear_tol)
                Tc = u + T0
                dT = float(np.max(np.abs(Tc - T_prev)))  # re-check the Picard stop on the field actually returned
                if dT >= picard_tol and iters < max_picard:
                    continue
            break
        if iters >= max_picard:
            raise RuntimeError(f"Picard iteration did not converge in {max_picard} steps (last dT = {dT:.3g} K)")
    if nonlinear and not dT < picard_tol:
        raise RuntimeError(f"Picard iteration did not converge in {max_picard} steps (last dT = {dT:.3g} K)")
    if not res <= accepted:  # also catches NaN (review T0158/T0159: never return an unconverged field silently)
        raise RuntimeError(f"linear solve did not reach the relative residual {accepted:.1e} (got {res:.3g}); "
                           "loosen linear_tol or check the conductivity contrast and cell aspect ratios")

    # ---- outputs ----------------------------------------------------------------------------------------------------
    q_in = float(Qv.sum() + F.sum() + q_rob_w)
    q_out = float((g_rob * (Tc[rob_cell] - tinf_eff)).sum()) + q_rob_w  # Robin outflow h (T_f - T_inf)
    balance = abs(q_out / q_in - 1.0) if q_in != 0.0 else abs(q_out)

    Tfull = np.full(shape, np.nan)
    Tfull[act] = Tc
    k_final = _material_k(materials, matid, Tc)
    kfull = np.ones(shape)
    kfull[act] = k_final
    has = act.any(axis=2)
    kt = nz - 1 - np.argmax(act[:, :, ::-1], axis=2)
    ii, jj = np.meshgrid(np.arange(nx), np.arange(ny), indexing="ij")
    surf = Tfull[ii, jj, kt] + q_top[ii, jj, kt] * hz[kt] / (2.0 * kfull[ii, jj, kt])
    surf = np.where(has, surf, np.nan)
    height = np.where(has, z[kt + 1], np.nan)
    meta = {
        "n_cells": n, "picard_iters": iters, "linear_residual": float(res), "linear_residual_accepted": float(accepted),
        "linear_iters": solver.iters,
        "energy_balance": balance, "q_in": q_in, "q_out": q_out, "picard_dT": dT,
        "wall_time_s": time.perf_counter() - t_start,
    }
    return ThermalResult(x, y, z, Tfull, SurfaceField(x, y, surf, height), meta)


__all__ = ["SurfaceField", "ThermalResult", "solve_steady"]

