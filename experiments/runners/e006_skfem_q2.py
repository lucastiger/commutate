"""scikit-fem triquadratic (Q2) box-stack solver for E006's F1 reference checks (research code, not production).

Purpose. F1 asks for an independent scikit-fem run on Muzychka 2003 Case 2 and on the laterally uniform default stack,
with scikit-fem's own grid convergence index (O006 A4 estimator, mfos.metrics.gci_capped, floor 1e-3 K) at most 0.01 K,
"refined until it is".  The trilinear (Q1) path of ``moduleforge.solvers.thermal_fem`` reached 0.0155 K and 0.044 K at
the largest meshes this Mac holds (T0165 attempt 1: 1.8 M DOF, about 6 GB).  The A4 estimator caps the order at 1, so
its value is about 1.25 |d2| (the finest step) and only a smaller finest step lowers it.  Raising the polynomial degree
does that at a fixed memory: this module solves the same boundary-value problem with scikit-fem's ``ElementHex2``
(27-node Lagrange hexahedra) on the same kind of graded tensor mesh, three levels obtained by bisecting every level-0
cell (constant ratio r = 2).

Problem (docs/thermal_model.md section 6, box-stack mode; Muzychka, Culham & Yovanovich, J. Electron. Packag. 125(2):178,
2003, eqs. 1-4).  Constant-k layers spanning [0, a] x [0, b], stacked bottom-up; uniform flux q_i = P_i / (c_i d_i) on
each source rectangle of the top face; Robin sink k dT/dn = -h (T - Tf) on the whole bottom face; every other face
adiabatic.  Unknown theta = T - Tf.  Galerkin: K theta = f with
    K_ij = sum_e k_e int_e grad(phi_i) . grad(phi_j) dV + h int_bottom phi_i phi_j dS,   f_i = sum_s q_s int_s phi_i dS.
Units inside: millimetres (k [W/(m K)] -> 1e-3 W/(mm K), h -> 1e-6 W/(mm2 K)), as in thermal_fem.

Quadrature: Gauss with 3 points per direction (``intorder=4``), exact for every Q2 stiffness and face-mass integrand on
the axis-aligned boxes used here (degree <= 4 per direction).  Source means are the exact Galerkin integral of the
field over the source faces divided by the area (never a nodal average); point values evaluate the Q2 field at the
point (element found on the tensor lines, reference coordinates by the mesh mapping's inverse).

Energy balance: with v = 1 in the Galerkin equation (constants are in the space), h int_bottom theta dS = sum P exactly,
up to the linear-solver residual; |Q_out / Q_in - 1| is reported per solve.

Memory: the stiffness matrix is assembled in element chunks (``chunk`` elements per scikit-fem basis), so the peak is
the CSR matrix, the AMG hierarchy and one chunk's basis tables (about 23 kB per Q2 element), not all elements' tables.
The linear system is solved by CG preconditioned with smoothed-aggregation AMG (pyamg, MIT), relative residual 1e-11.
"""
from __future__ import annotations

import math
import time
from collections.abc import Sequence
from dataclasses import dataclass, field

import numpy as np
import pyamg
import scipy.sparse as sp
from skfem import BilinearForm, CellBasis, ElementHex2, FacetBasis, LinearForm, MeshHex
from skfem.assembly import Dofs
from skfem.helpers import dot, grad

MM = 1.0e3
LINEAR_RTOL = 1.0e-11


def graded_lines(lines, edges, s0: float, grow: float, hmax, level: int) -> np.ndarray:
    """Graded tensor lines (independent of the FV grid builder): each interval of ``lines`` gets geometric cells
    s0 * grow**k from every end that is in ``edges`` (each end < half the interval when both are), then uniform cells
    <= hmax (a number, or one value per interval); level l bisects every level-0 cell l times (constant ratio 2)."""
    out = [np.asarray(lines[:1], dtype=float)]
    hm = np.broadcast_to(np.asarray(hmax, dtype=float), (len(lines) - 1,))
    ed = [any(abs(v - e) < 1e-12 for e in edges) for v in lines]
    for i in range(len(lines) - 1):
        a, b = float(lines[i]), float(lines[i + 1])
        L, hmx = b - a, float(hm[i])
        cap = 0.5 * L if (ed[i] and ed[i + 1]) else L
        sides = []
        for flag in (ed[i], ed[i + 1]):
            acc, c = [], s0
            while flag and c < hmx and sum(acc) + c < cap * (1 - 1e-9):
                acc.append(c)
                c *= grow
            sides.append(acc)
        rem = L - sum(sides[0]) - sum(sides[1])
        n = max(1, math.ceil(rem / hmx - 1e-9)) if rem > 1e-12 * L else 0
        sz = np.array(sides[0] + [rem / n] * n + sides[1][::-1]) if n else np.array(sides[0] + sides[1][::-1])
        sz *= L / sz.sum()
        sz = np.repeat(sz / 2**level, 2**level)
        seg = a + np.cumsum(sz)
        seg[-1] = b
        out.append(seg)
    return np.concatenate(out)


@dataclass
class BoxQ2Result:
    """One Q2 solve.  Temperatures absolute [K]."""

    mean: np.ndarray  # per source: exact area mean of T over the source face
    point: np.ndarray  # per requested point: T of the Q2 field
    energy_balance: float  # |Q_out / Q_in - 1|
    dofs: int
    elements: int
    cg_iters: int
    rel_residual: float
    wall_s: float
    meta: dict = field(default_factory=dict)


def _locate(x: np.ndarray, y: np.ndarray, z: np.ndarray, pt: Sequence[float]) -> tuple[int, int, int]:
    """Tensor cell (i, j, k) containing ``pt`` [mm] (the lower cell on a shared line; any neighbour gives the same value
    of the continuous field)."""
    out = []
    for lines, v in ((x, pt[0]), (y, pt[1]), (z, pt[2])):
        i = int(np.clip(np.searchsorted(lines, v, side="right") - 1, 0, lines.size - 2))
        if not (lines[i] - 1e-9 <= v <= lines[i + 1] + 1e-9):
            raise ValueError(f"point {pt} outside the mesh")
        out.append(i)
    return tuple(out)


def _element_index(mesh: MeshHex, x, y, z) -> np.ndarray:
    """Map tensor cell (i, j, k) -> mesh element id (built from element-centre coordinates; no assumption about the
    ordering inside MeshHex.init_tensor)."""
    pc = mesh.p[:, mesh.t].mean(axis=1)
    xc, yc, zc = 0.5 * (x[1:] + x[:-1]), 0.5 * (y[1:] + y[:-1]), 0.5 * (z[1:] + z[:-1])
    ii = np.searchsorted(xc, pc[0] - 1e-9 * max(1.0, abs(x[-1])))
    jj = np.searchsorted(yc, pc[1] - 1e-9 * max(1.0, abs(y[-1])))
    kk = np.searchsorted(zc, pc[2] - 1e-9 * max(1.0, abs(z[-1])))
    idx = -np.ones((xc.size, yc.size, zc.size), dtype=np.int64)
    idx[ii, jj, kk] = np.arange(mesh.t.shape[1])
    if (idx < 0).any():
        raise RuntimeError("tensor cell -> element map incomplete")
    return idx


def point_values(mesh, elem, dofs, eidx, x, y, z, u: np.ndarray, pts: np.ndarray) -> np.ndarray:
    """Values of the FE function ``u`` at points ``pts`` (n, 3) [mm]: one-point 'quadrature' at each point's reference
    coordinates inside its element (scikit-fem's interpolate at that point)."""
    mapping = mesh._mapping()
    vals = np.empty(len(pts))
    for n, p in enumerate(pts):
        e = int(eidx[_locate(x, y, z, p)])
        X = mapping.invF(np.asarray(p, dtype=float)[:, None, None], tind=np.array([e]))  # (3, 1, 1) reference coords
        cb = CellBasis(mesh, elem, elements=np.array([e]), quadrature=(X[:, 0, :], np.array([1.0])), dofs=dofs)
        vals[n] = float(np.asarray(cb.interpolate(u).value).ravel()[0])
    return vals


def linear_solve(A: sp.csr_matrix, f: np.ndarray, rtol: float = LINEAR_RTOL,
                 accept: float = 1e-9) -> tuple[np.ndarray, int, float]:
    """Solve the SPD system by CG preconditioned with smoothed-aggregation AMG on the symmetrically diagonal-scaled
    matrix D^-1/2 A D^-1/2 (same solution; the scaling removes the k contrast and the mm-unit Robin scale from the
    aggregation).  CG stops at relative residual ``rtol``; raises unless the true relative residual |f - A x| / |f| <=
    ``accept`` (gated F1 solves: 1e-11 and 1e-9; the INFO-only Case 1a/1b solves pass looser values, reported)."""
    d = 1.0 / np.sqrt(A.diagonal())
    Dm = sp.diags(d)
    As = (Dm @ A @ Dm).tocsr()
    ml = pyamg.smoothed_aggregation_solver(As, symmetry="hermitian", max_coarse=500)
    resid: list[float] = []
    y = ml.solve(d * f, tol=rtol, maxiter=3000, accel="cg", residuals=resid)
    x = d * y
    rel = float(np.linalg.norm(f - A @ x) / np.linalg.norm(f))
    if rel > accept:
        raise RuntimeError(f"AMG-CG relative residual {rel:.2e} > {accept:.0e} after {len(resid) - 1} iterations")
    return x, len(resid) - 1, rel


def solve_box_q2(x: np.ndarray, y: np.ndarray, z: np.ndarray, layer_z: Sequence[float], layer_k: Sequence[float],
                 h: float, Tf: float, sources: Sequence[tuple[float, float, float, float, float]],
                 points: np.ndarray, chunk: int = 4000, rtol: float = LINEAR_RTOL,
                 accept: float = 1e-9) -> BoxQ2Result:
    """Solve the box stack on tensor lines ``x, y, z`` [m] with Q2 hexahedra.

    ``layer_z``: interface heights bottom-up [m] (0 first, top last; every one must be a z line); ``layer_k`` [W/(m K)];
    ``sources``: (x0, y0, x1, y1, P [W]) on the top face (edges must be x/y lines); ``points``: (n, 2) top-face points [m].
    """
    t0 = time.perf_counter()
    xm, ym, zm = (np.asarray(v, dtype=float) * MM for v in (x, y, z))
    lz = np.asarray(layer_z, dtype=float) * MM
    for v in lz:
        if np.min(np.abs(zm - v)) > 1e-9:
            raise ValueError("a layer interface is not a z line")
    mesh = MeshHex.init_tensor(xm, ym, zm)
    elem = ElementHex2()
    dofs = Dofs(mesh, elem)
    N = int(dofs.N)
    ne = int(mesh.t.shape[1])
    zc = mesh.p[2, mesh.t].mean(axis=0)
    lay = np.clip(np.searchsorted(lz, zc) - 1, 0, len(layer_k) - 1)
    kel = np.asarray(layer_k, dtype=float)[lay] / MM  # W/(mm K)

    @BilinearForm
    def stiff(u, v, w):
        return w["kk"] * dot(grad(u), grad(v))

    A = sp.csr_matrix((N, N))
    for s in range(0, ne, chunk):
        idx = np.arange(s, min(ne, s + chunk))
        cb = CellBasis(mesh, elem, intorder=4, elements=idx, dofs=dofs)
        kk = np.repeat(kel[idx][:, None], cb.X.shape[1], axis=1)
        A = A + stiff.assemble(cb, kk=kk).tocsr()
        del cb, kk

    hh = h / MM**2  # W/(mm2 K)
    ztop = float(zm[-1])
    bottom = mesh.facets_satisfying(lambda X: np.isclose(X[2], 0.0), boundaries_only=True)
    fb = FacetBasis(mesh, elem, facets=bottom, intorder=4, dofs=dofs)
    A = (A + hh * BilinearForm(lambda u, v, w: u * v).assemble(fb)).tocsr()
    ones_b = LinearForm(lambda v, w: 1.0 * v).assemble(fb)  # int_bottom phi_i dS [mm2]
    del fb

    f = np.zeros(N)
    svecs, areas, P_tot = [], [], 0.0
    for (x0, y0, x1, y1, P) in sources:
        X0, Y0, X1, Y1 = (v * MM for v in (x0, y0, x1, y1))

        def on_src(X, X0=X0, Y0=Y0, X1=X1, Y1=Y1):
            return (np.isclose(X[2], ztop) & (X[0] > X0 - 1e-9) & (X[0] < X1 + 1e-9) & (X[1] > Y0 - 1e-9)
                    & (X[1] < Y1 + 1e-9))

        fac = mesh.facets_satisfying(on_src, boundaries_only=True)
        sb = FacetBasis(mesh, elem, facets=fac, intorder=4, dofs=dofs)
        vec = LinearForm(lambda v, w: 1.0 * v).assemble(sb)
        area = float(vec.sum())
        if abs(area - (X1 - X0) * (Y1 - Y0)) > 1e-9 * area:
            raise ValueError("a source is not covered exactly by mesh faces (edges must be mesh lines)")
        f += (P / area) * vec
        svecs.append(vec / area)
        areas.append(area)
        P_tot += P
        del sb

    theta, iters, rel = linear_solve(A, f, rtol, accept)
    q_out = hh * float(ones_b @ theta)
    eb = abs(q_out / P_tot - 1.0)
    means = np.array([Tf + float(v @ theta) for v in svecs])
    eidx = _element_index(mesh, xm, ym, zm)
    pts = np.column_stack([np.asarray(points, dtype=float).reshape(-1, 2) * MM, np.full(len(points), ztop)])
    pv = Tf + point_values(mesh, elem, dofs, eidx, xm, ym, zm, theta, pts) if len(points) else np.zeros(0)
    return BoxQ2Result(means, pv, eb, N, ne, iters, rel, time.perf_counter() - t0,
                       meta={"q_out_W": q_out, "P_total_W": P_tot, "nx": xm.size - 1, "ny": ym.size - 1,
                             "nz": zm.size - 1})


def selftest() -> dict:
    """Checks of this module on small problems (run before the F1 solves; cheap):
    (1) point evaluation reproduces a triquadratic function exactly from its nodal interpolant;
    (2) a 1D conduction problem (uniform flux over the whole top, Robin bottom, two layers) is reproduced exactly:
        T_top = Tf + q (1/h + sum t_i / k_i) (Q2 contains the piecewise-linear exact solution)."""
    x = np.array([0.0, 0.3, 1.0, 2.0]) * 1e-3
    y = np.array([0.0, 0.5, 1.5]) * 1e-3
    z = np.array([0.0, 0.2, 0.25, 0.6]) * 1e-3
    xm, ym, zm = x * MM, y * MM, z * MM
    mesh = MeshHex.init_tensor(xm, ym, zm)
    elem = ElementHex2()
    basis = CellBasis(mesh, elem, intorder=2)
    dofs = basis.dofs

    def fq(P):
        return 1.0 + P[0] ** 2 - 0.7 * P[1] * P[2] + 0.3 * P[2] ** 2 * P[0] + P[0] * P[1] * P[2] ** 2

    u = fq(basis.doflocs)
    rng = np.random.default_rng(20261102)
    pts = np.column_stack([rng.uniform(0, xm[-1], 7), rng.uniform(0, ym[-1], 7), rng.uniform(0, zm[-1], 7)])
    eidx = _element_index(mesh, xm, ym, zm)
    got = point_values(mesh, elem, dofs, eidx, xm, ym, zm, u, pts)
    err_interp = float(np.max(np.abs(got - fq(pts.T))))
    # 1D two-layer problem
    a = 2e-3
    zl = np.array([0.0, 0.4e-3, 0.6e-3])
    ks, h, Tf, P = (150.0, 24.0), 2000.0, 300.0, 3.0
    r = solve_box_q2(np.linspace(0, a, 3), np.linspace(0, a, 3), np.array([0.0, 0.2e-3, 0.4e-3, 0.5e-3, 0.6e-3]),
                     zl, ks, h, Tf, [(0.0, 0.0, a, a, P)], np.array([[0.3e-3, 1.1e-3]]))
    q = P / a**2
    exact = Tf + q * (1 / h + 0.4e-3 / ks[0] + 0.2e-3 / ks[1])
    err_1d = float(max(abs(r.point[0] - exact), abs(r.mean[0] - exact)))
    return {"q2_point_eval_max_err": err_interp, "q2_1d_exact_max_err_K": err_1d, "q2_1d_energy_balance": r.energy_balance}
