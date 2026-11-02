"""E006 manufactured reference (T0153): symbolic 3D manufactured temperature field with k(T) on the default DBC stack
with patterned top copper (two islands, one L-shaped with a re-entrant corner), die attach and SiC die on one island.

Independence: this module never imports the moduleforge solver package (or any FEM package). It imports
``moduleforge.geometry.stack`` only for thicknesses, k(300 K) and the cited k(T) laws, which it re-implements
symbolically and cross-checks numerically against ``Layer.k_at``.

Usage
  uv run python experiments/runners/e006_mms.py --selfcheck            gated self-checks; exit 1 on any failure
  uv run python experiments/runners/e006_mms.py --emit research/e006_refs/mms_values.json
        self-checks, then the F3 constant-k estimate (own finite-volume solve), then writes the frozen values + sha256

Construction (full derivation: research/notes/o006-manufactured-solution.md)
  Layers j = 0..6 (baseplate, solder, backside_cu, ceramic, top_cu, die_attach, die) between interfaces z_0..z_7.
  Each interface i carries two smooth plane functions, shared by the two layers that meet there:
      Theta_i(x, y)  temperature [K],      G_i(x, y) = k dT/dz  [W/m^2]  (heat flowing down, toward -z, if > 0).
  In layer j, with s = (z - z_j) / t_j, T* is the cubic Hermite interpolant in z (endpoint values and slopes):
      T_j = Theta_j h00(s) + Theta_{j+1} h01(s) + t_j [G_j / k_j(Theta_j) h10(s) + G_{j+1} / k_j(Theta_{j+1}) h11(s)]
  with h00 = 2s^3 - 3s^2 + 1, h01 = -2s^3 + 3s^2, h10 = s^3 - 2s^2 + s, h11 = s^3 - s^2 (endpoint conditions checked by
  substitution). So T_j(z_j) = Theta_j and k_j(T_j) dT_j/dz (z_j) = G_j on both sides of every interface: T* and the
  normal flux are continuous at every material interface for every (x, y) by construction (verified numerically).
  Each layer's formula is defined on the whole plane; patterning only decides which faces are void-bounding.
  Source per region: q''' = -div(k_j(T_j) grad T_j) (sympy, exact differentiation).
  Prescribed inflow on every exterior / void-bounding face: k(T*) dT*/dn (n outward); on horizontal faces this is
  +G_i (top faces) or -G_i (bottom faces).  Robin at z = 0: uniform h, T_inf(x, y) = Theta_0 - G_0 / h.

Solver contract this targets (D0006 FV solver, task n2/n3 docstring): (a) Robin at z = 0 with scalar h and callable
T_inf(x, y); (b) prescribed normal flux as a callable flux(x, y, z, axis, sign), heat INTO the domain in W/m^2,
additive to Robin on z = 0 (so this module returns 0 there), faces identified by the outward normal (axis, sign);
(c) volumetric source callable source(x, y, z) [W/m^3]. Materials: the stack's Layer objects (k_at). All inside the
contract; nothing is extended.

Sources: cubic Hermite basis: de Boor, A Practical Guide to Splines (1978), ch. IV; Kirchhoff transform identity
div(k(T) grad T) = Laplacian(phi(T)), phi' = k: Carslaw & Jaeger, Conduction of Heat in Solids, 2nd ed. (1959),
sec. 1.8, and Bagnall, Muzychka & Wang, IEEE TCPMT 4(3):408 (2014); MMS: Salari & Knupp, SAND2000-1444 (2000);
sixth-order central second difference: Fornberg, Math. Comp. 51(184):699-706 (1988), Table 1; Gauss-Legendre:
Abramowitz & Stegun 25.4.29; finite volumes (F3 estimate only): Patankar (1980) sec. 4.2.3.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import time
from functools import lru_cache
from pathlib import Path

import numpy as np
import sympy as sp
from scipy.optimize import minimize

from moduleforge.geometry.stack import K_T_MAX, K_T_MIN, default_dbc_stack


def mm_to_m(v):
    """Millimetre -> metre (mf-conventions named helper)."""
    return np.asarray(v, dtype=float) * 1e-3


# ----------------------------------------------------------------------------------------------------------------
# Geometry: default DBC stack (geometry.stack) + die attach + die; rectilinear footprints in mm (0.5 mm design grid)
# ----------------------------------------------------------------------------------------------------------------
NAMES = ("baseplate", "solder", "backside_cu", "ceramic", "top_cu", "die_attach", "die")
STACK = default_dbc_stack()
LAYERS = tuple(STACK.layer(n) for n in NAMES[:5]) + (STACK.die_attach, STACK.die)
_zb = [STACK.z_bottom(n) for n in NAMES[:5]] + [STACK.z_top("top_cu")]
_zb.append(_zb[-1] + STACK.die_attach.thickness)
_zb.append(_zb[-1] + STACK.die.thickness)
Z = np.array(_zb)  # 8 interfaces, m

BOXES_MM = {  # region j -> list of (x0, x1, y0, y1) in mm
    0: [(0.0, 30.0, 0.0, 24.0)],  # baseplate (3 mm overhang beyond the ceramic)
    1: [(4.0, 26.0, 4.0, 20.0)],  # solder = backside-Cu footprint
    2: [(4.0, 26.0, 4.0, 20.0)],  # backside Cu: ceramic outline inset by 1 mm
    3: [(3.0, 27.0, 3.0, 21.0)],  # ceramic = substrate outline
    4: [(4.5, 16.5, 4.5, 19.5),  # top-Cu island A (carries the die)
        (18.0, 25.5, 4.5, 10.0), (21.5, 25.5, 10.0, 19.5)],  # island B, L-shaped (re-entrant corner at 21.5, 10)
    5: [(8.0, 13.0, 8.5, 13.5)],  # die attach = die footprint
    6: [(8.0, 13.0, 8.5, 13.5)],  # 4H-SiC die, 5 mm x 5 mm
}
BOXES = {j: [tuple(mm_to_m(b)) for b in bl] for j, bl in BOXES_MM.items()}
DIE = BOXES[6][0]

# ----------------------------------------------------------------------------------------------------------------
# Manufactured field parameters (frozen design; chosen before any solver comparison, see the note)
# ----------------------------------------------------------------------------------------------------------------
XD, YD = float(mm_to_m(10.5)), float(mm_to_m(11.0))  # die centre: main bump centre and tilt origin
SX, SY = float(mm_to_m(6.5)), float(mm_to_m(5.5))  # main bump widths (anisotropic)
X2, Y2, S2 = float(mm_to_m(23.0)), float(mm_to_m(13.5)), float(mm_to_m(4.0))  # secondary bump on island B
TILT_X, TILT_Y = 1000.0, 600.0  # K/m lateral tilt: tau = -TILT_X (x - XD) - TILT_Y (y - YD)
G_FAR = np.array([0.03, 0.12, 0.15, 0.15, 0.15, 0.15, 0.15, 0.15]) * 1e6  # W/m^2, G_i far from both bumps
G_PEAK = np.array([0.20, 1.20, 1.30, 1.40, 1.60, 2.00, 2.10, 2.20]) * 1e6  # W/m^2, amplitude on the main bump
G_B2 = np.array([0.02, 0.10, 0.12, 0.15, 0.20, 0.25, 0.25, 0.25]) * 1e6  # W/m^2, amplitude on the secondary bump
THETA0_FAR, THETA0_PEAK, THETA0_B2 = 322.0, 25.0, 3.0  # K: Theta_0 far value and bump excesses at z = 0
H = 5000.0  # W/(m^2 K), uniform Robin coefficient at z = 0 (O002's value)

FD_SEED = 61530  # FD-check sample points
IFACE_SEED = 61531  # interface-continuity sample points
N_FD_PER_REGION = 200  # 7 regions -> 1400 >= 1000 points
TOL_FD, TOL_IFACE, TOL_BAL, KVAR_MIN = 1e-6, 1e-10, 1e-10, 0.30
RANGE_MIN, RANGE_MAX = 60.0, 110.0  # K, O002-like field range
AL2O3_BRANCH = 400.0  # K: the cited Al2O3 law changes exponent here; the ceramic must stay below (smoothness)


def _column(theta0: float, G: np.ndarray) -> np.ndarray:
    """Interface temperatures of a 1-D column with interface fluxes G (design rule for Theta amplitudes).

    Layer drop d solves d = t_j * mean(G_j, G_{j+1}) / k_j(Theta_j + d/2) (fixed point). Only a design rule: any
    smooth Theta is admissible, a consistent one keeps the source small and the field physically flavoured."""
    th = [theta0]
    for j in range(7):
        t, gm, d = Z[j + 1] - Z[j], 0.5 * (G[j] + G[j + 1]), 0.0
        for _ in range(60):
            d = t * gm / LAYERS[j].k_at(th[-1] + 0.5 * d)
        th.append(th[-1] + d)
    return np.array(th)


_far = _column(THETA0_FAR, G_FAR)
A_TH = _far  # Theta_i far value (before tilt)
B_TH = _column(THETA0_FAR + THETA0_PEAK, G_FAR + G_PEAK) - _far  # main-bump amplitude per interface
C_TH = _column(THETA0_FAR + THETA0_B2, G_FAR + G_B2) - _far  # secondary-bump amplitude per interface


# ----------------------------------------------------------------------------------------------------------------
# Symbolic k(T) laws (transcribed from geometry.stack, cited there; checked against Layer.k_at in the self-check)
# ----------------------------------------------------------------------------------------------------------------
def k_sym(layer, T):
    """k(T) of ``layer`` as a sympy expression: Layer.k * f(T) / f(300 K), with f(300 K) = 1 for every law."""
    k0, m = float(layer.k), layer.material
    if m == "Cu":  # Incropera et al. Table A.1 slope
        f = 1 - 1.995e-4 * (T - 300)
    elif m == "SAC305":  # Wiedemann-Franz with tin TCR 4.2e-3 /K
        f = (T / 300) / (1 + 4.2e-3 * (T - 300))
    elif m == "Al2O3":  # Incropera Table A.2, log-linear 300-400 K segment (valid branch: T <= 400 K)
        f = (T / 300) ** (math.log(26.4 / 36.0) / math.log(400.0 / 300.0))
    elif m == "4H-SiC":  # (T/300)^-1.49, TCAD form after Levinshtein et al. (2001)
        f = (T / 300) ** -1.49
    else:
        raise KeyError(m)
    return k0 * f


# ----------------------------------------------------------------------------------------------------------------
# Symbolic field and lambdified callables
# ----------------------------------------------------------------------------------------------------------------
class MMSCase:
    """The manufactured case: exact field, source, face fluxes and Robin data as numpy callables (SI units)."""

    def __init__(self):
        x, y, z = sp.symbols("x y z", real=True)
        self.sym = (x, y, z)
        B = sp.exp(-((x - XD) ** 2 / (2 * SX ** 2) + (y - YD) ** 2 / (2 * SY ** 2)))
        B2 = sp.exp(-((x - X2) ** 2 + (y - Y2) ** 2) / (2 * S2 ** 2))
        tau = -TILT_X * (x - XD) - TILT_Y * (y - YD)
        self.theta_sym = [float(A_TH[i]) + float(B_TH[i]) * B + float(C_TH[i]) * B2 + tau for i in range(8)]
        self.G_sym = [float(G_FAR[i]) + float(G_PEAK[i]) * B + float(G_B2[i]) * B2 for i in range(8)]
        self.T_sym, self.F_sym, self.terms_sym = [], [], []
        for j in range(7):
            t = float(Z[j + 1] - Z[j])
            s = (z - float(Z[j])) / t
            h00, h01 = 2 * s ** 3 - 3 * s ** 2 + 1, -2 * s ** 3 + 3 * s ** 2
            h10, h11 = s ** 3 - 2 * s ** 2 + s, s ** 3 - s ** 2
            lo, hi = self.theta_sym[j], self.theta_sym[j + 1]
            Tj = (lo * h00 + hi * h01 + t * (self.G_sym[j] / k_sym(LAYERS[j], lo) * h10
                                             + self.G_sym[j + 1] / k_sym(LAYERS[j], hi) * h11))
            kT = k_sym(LAYERS[j], Tj)
            F = [kT * sp.diff(Tj, v) for v in (x, y, z)]  # k grad T  (heat flux vector is -F)
            self.T_sym.append(Tj)
            self.F_sym.append(F)
            self.terms_sym.append([sp.diff(F[a], v) for a, v in enumerate((x, y, z))])  # d/dx_a (k dT/dx_a)
        lam = lambda e: sp.lambdify((x, y, z), e, modules="numpy", cse=True)  # noqa: E731
        lam2 = lambda e: sp.lambdify((x, y), e, modules="numpy", cse=True)  # noqa: E731
        self._T = [lam(e) for e in self.T_sym]
        self._F = [lam(e) for e in self.F_sym]
        self._terms = [lam(e) for e in self.terms_sym]
        self._theta = [lam2(e) for e in self.theta_sym]
        self._G = [lam2(e) for e in self.G_sym]
        self.h = H
        self.materials = LAYERS  # region index j -> Layer (k_at); top-Cu islands share index 4

    # --- per-layer evaluation helpers -------------------------------------------------------------------------
    @staticmethod
    def layer_of_z(z):
        """Layer index of interior points (z strictly inside a layer); clipped to 0..6."""
        return np.clip(np.searchsorted(Z, np.asarray(z, float), side="right") - 1, 0, 6)

    @staticmethod
    def _bc(v, shape):
        return np.broadcast_to(np.asarray(v, dtype=float), shape)

    def _eval(self, fns, j, x, y, z, comp=None):
        x, y, z = (np.asarray(v, dtype=float) for v in np.broadcast_arrays(x, y, z))
        j = np.broadcast_to(np.asarray(j), x.shape)
        out = np.empty(x.shape)
        for jj in np.unique(j):
            m = j == jj
            r = fns[int(jj)](x[m], y[m], z[m])
            if comp is not None:
                r = r[comp]
            out[m] = self._bc(r, out[m].shape)
        return out

    def T_layer(self, j, x, y, z):
        return self._eval(self._T, j, x, y, z)

    def F_layer(self, j, x, y, z, axis):
        """k(T*) dT*/dx_axis evaluated with layer j's formula."""
        return self._eval(self._F, j, x, y, z, comp=axis)

    def terms_layer(self, j, x, y, z):
        return np.stack([self._eval(self._terms, j, x, y, z, comp=a) for a in range(3)])

    def theta(self, i, x, y):
        x, y = np.broadcast_arrays(np.asarray(x, float), np.asarray(y, float))
        return self._bc(self._theta[i](x, y), x.shape).copy()

    def G(self, i, x, y):
        x, y = np.broadcast_arrays(np.asarray(x, float), np.asarray(y, float))
        return self._bc(self._G[i](x, y), x.shape).copy()

    # --- public callables (the solver contract) ---------------------------------------------------------------
    def T_exact(self, x, y, z):
        """T*(x, y, z) [K]; at an interface both layers agree (the upper layer's formula is used)."""
        return self.T_layer(self.layer_of_z(z), x, y, z)

    def source(self, x, y, z):
        """q''' = -div(k(T*) grad T*) [W/m^3] at interior points; the region is the layer containing z."""
        return -self.terms_layer(self.layer_of_z(z), x, y, z).sum(axis=0)

    def flux(self, x, y, z, axis, sign):
        """Prescribed inflow k(T*) dT*/dn [W/m^2] (n outward) on a face with outward normal (axis, sign).

        Horizontal faces (axis 2) lie on an interface plane z_i: sign +1 is the top face of layer i-1, sign -1 the
        bottom face of layer i. z = 0 with sign -1 returns 0 (the Robin condition carries that face)."""
        x, y, z = (np.asarray(v, dtype=float) for v in np.broadcast_arrays(x, y, z))
        out = np.zeros(x.shape)
        if axis == 2:
            i = np.argmin(np.abs(z[..., None] - Z), axis=-1)
            if np.any(np.abs(z - Z[i]) > 1e-9):
                raise ValueError("horizontal face off an interface plane")
            j = i - 1 if sign > 0 else i
            robin = (sign < 0) & (i == 0)
            if np.any((j < 0) | (j > 6)):
                raise ValueError("horizontal face outside the stack")
            m = ~robin
            if m.any():
                out[m] = sign * self.F_layer(j[m], x[m], y[m], z[m], 2)
            return out
        return sign * self.F_layer(self.layer_of_z(z), x, y, z, axis)

    def T_inf(self, x, y):
        """Robin ambient temperature at z = 0 [K], with uniform h: h (T* - T_inf) = k dT*/dz = G_0."""
        return self.theta(0, x, y) - self.G(0, x, y) / self.h

    def surface_exact(self, x, y, level):
        """T* on a top surface: level 'die' (z_7), 'cu' (z_5), 'ceramic' (z_4, gaps), 'baseplate' (z_1, overhang)."""
        return self.theta({"die": 7, "cu": 5, "ceramic": 4, "baseplate": 1}[level], x, y)

    @staticmethod
    def region_of(x, y, z):
        """Region index (0..6) of points or -1 for void (cell centres; footprints are closed boxes)."""
        x, y, z = (np.asarray(v, dtype=float) for v in np.broadcast_arrays(x, y, z))
        j = MMSCase.layer_of_z(z)
        out = np.full(x.shape, -1, dtype=int)
        for jj in range(7):
            m = j == jj
            ins = np.zeros(m.sum(), dtype=bool)
            for (x0, x1, y0, y1) in BOXES[jj]:
                ins |= (x[m] >= x0) & (x[m] <= x1) & (y[m] >= y0) & (y[m] <= y1)
            sub = np.full(m.sum(), -1)
            sub[ins] = jj
            out[m] = sub
        return out


@lru_cache(maxsize=1)
def build_case() -> MMSCase:
    return MMSCase()


# ----------------------------------------------------------------------------------------------------------------
# Breakpoint grid, faces and cubature
# ----------------------------------------------------------------------------------------------------------------
XB = np.unique(np.concatenate([[b[0], b[1]] for bl in BOXES.values() for b in bl]))
YB = np.unique(np.concatenate([[b[2], b[3]] for bl in BOXES.values() for b in bl]))


def _occ(j, xc, yc):
    X, Y = np.meshgrid(xc, yc, indexing="ij")
    m = np.zeros(X.shape, dtype=bool)
    for (x0, x1, y0, y1) in BOXES[j]:
        m |= (X > x0) & (X < x1) & (Y > y0) & (Y < y1)
    return m


OCC = [_occ(j, 0.5 * (XB[:-1] + XB[1:]), 0.5 * (YB[:-1] + YB[1:])) for j in range(7)]


def _gl(a, b, n):
    xi, w = np.polynomial.legendre.leggauss(n)
    return 0.5 * (b - a) * xi + 0.5 * (a + b), 0.5 * (b - a) * w


def patches(j):
    """Boundary patches of region j: (kind, axis, sign, coord, (a1, b1), (a2, b2)); kind exposed|interface|robin.

    axis 2: coord = z, ranges (x, y); axis 0: coord = x, ranges (y, z); axis 1: coord = y, ranges (x, z)."""
    out, o = [], OCC[j]
    nxb, nyb = o.shape
    for p in range(nxb):
        for q in range(nyb):
            if not o[p, q]:
                continue
            xr, yr = (XB[p], XB[p + 1]), (YB[q], YB[q + 1])
            top = "exposed" if j == 6 or not OCC[j + 1][p, q] else "interface"
            bot = "robin" if j == 0 else ("exposed" if not OCC[j - 1][p, q] else "interface")
            out.append((top, 2, +1, Z[j + 1], xr, yr))
            out.append((bot, 2, -1, Z[j], xr, yr))
    zr = (Z[j], Z[j + 1])
    for p in range(nxb + 1):  # faces normal to x at XB[p]
        for q in range(nyb):
            lo = o[p - 1, q] if p > 0 else False
            hi = o[p, q] if p < nxb else False
            if lo != hi:
                out.append(("exposed", 0, +1 if lo else -1, XB[p], (YB[q], YB[q + 1]), zr))
    for q in range(nyb + 1):
        for p in range(nxb):
            lo = o[p, q - 1] if q > 0 else False
            hi = o[p, q] if q < nyb else False
            if lo != hi:
                out.append(("exposed", 1, +1 if lo else -1, YB[q], (XB[p], XB[p + 1]), zr))
    return out


def _patch_points(axis, c, r1, r2, n):
    u, wu = _gl(*r1, n)
    v, wv = _gl(*r2, n)
    U, V = np.meshgrid(u, v, indexing="ij")
    W = np.outer(wu, wv).ravel()
    U, V, C = U.ravel(), V.ravel(), np.full(U.size, c)
    pts = {2: (U, V, C), 0: (C, U, V), 1: (U, C, V)}[axis]
    return pts, W


def patch_integral(case, j, patch, n):
    kind, axis, sign, c, r1, r2 = patch
    (px, py, pz), W = _patch_points(axis, c, r1, r2, n)
    if kind == "robin":  # outflow h (T* - T_inf) leaves the domain: inflow is its negative
        f = -case.h * (case.T_exact(px, py, pz) - case.T_inf(px, py))
    elif kind == "exposed":  # through the public contract callable
        f = case.flux(px, py, pz, axis, sign)
    else:  # interface: inflow into region j from its neighbour, with region j's own formula
        f = sign * case.F_layer(j, px, py, pz, axis)
    return float(W @ f)


def volume_integral(case, j, n, fn="source"):
    """Integral over region j of the source (fn='source') or of T* (fn='T') by tensor Gauss-Legendre per cell."""
    tot = 0.0
    zz, wz = _gl(Z[j], Z[j + 1], n)
    for p, q in zip(*np.nonzero(OCC[j]), strict=True):
        xx, wx = _gl(XB[p], XB[p + 1], n)
        yy, wy = _gl(YB[q], YB[q + 1], n)
        X, Y, ZZ = np.meshgrid(xx, yy, zz, indexing="ij")
        Wt = np.einsum("i,j,k->ijk", wx, wy, wz).ravel()
        if fn == "source":
            f = -case.terms_layer(j, X.ravel(), Y.ravel(), ZZ.ravel()).sum(axis=0)
        else:
            f = case.T_layer(j, X.ravel(), Y.ravel(), ZZ.ravel())
        tot += float(Wt @ f)
    return tot


def region_volume(j):
    return float(sum((XB[p + 1] - XB[p]) * (YB[q + 1] - YB[q]) for p, q in zip(*np.nonzero(OCC[j]), strict=True))
                 * (Z[j + 1] - Z[j]))


# ----------------------------------------------------------------------------------------------------------------
# Field extremes and reported points
# ----------------------------------------------------------------------------------------------------------------
def _extreme(fun, bounds_list, sense, n=7):
    """Global extreme of fun(x) (x a point) over a union of boxes: dense sample, then bounded L-BFGS-B polish."""
    best = None
    for bnds in bounds_list:
        axes = [np.linspace(a, b, n) for a, b in bnds]
        G = np.stack(np.meshgrid(*axes, indexing="ij"), -1).reshape(-1, len(bnds))
        v = sense * fun(G.T)
        k = int(np.argmin(v))
        scale = np.array([b - a for a, b in bnds])
        lo = np.array([a for a, _ in bnds])
        res = minimize(lambda u, lo=lo, scale=scale: float(sense * fun(((lo + u * scale)[:, None]))[0]), (G[k] - lo) / scale,
                       method="L-BFGS-B", bounds=[(0.0, 1.0)] * len(bnds), options={"ftol": 1e-15, "gtol": 1e-12})
        cand = [(float(v[k]), G[k]), (float(res.fun), lo + res.x * scale)]
        for val, pt in cand:
            if best is None or val < best[0]:
                best = (val, pt)
    return sense * best[0], best[1]


def region_extremes(case, j):
    cells = [[(XB[p], XB[p + 1]), (YB[q], YB[q + 1]), (Z[j], Z[j + 1])] for p, q in zip(*np.nonzero(OCC[j]), strict=True)]
    f = lambda P: case.T_layer(j, P[0], P[1], P[2])  # noqa: E731
    tmin, pmin = _extreme(f, cells, +1)
    tmax, pmax = _extreme(f, cells, -1)
    return tmin, pmin, tmax, pmax


POINTS = [  # (id, kind, level, x_mm, y_mm): every point >= 1 mm from any surface-level change
    ("die_centroid", "point", "die", 10.5, 11.0),
    ("cuA_1", "point", "cu", 6.0, 17.0),
    ("cuA_2", "point", "cu", 15.0, 6.0),
    ("cuB_arm1", "point", "cu", 20.0, 7.25),
    ("cuB_arm2", "point", "cu", 23.5, 15.0),
    ("gap_ceramic", "point", "ceramic", 19.0, 15.0),
    ("overhang_baseplate", "point", "baseplate", 1.5, 12.0),
]
LEVEL_Z = {"die": 7, "cu": 5, "ceramic": 4, "baseplate": 1}


def reported_points(case):
    out = []
    for pid, kind, lev, xm, ym in POINTS:
        x, y = float(mm_to_m(xm)), float(mm_to_m(ym))
        out.append(dict(id=pid, kind=kind, level=lev, x=x, y=y, z=float(Z[LEVEL_Z[lev]]),
                        T_K=float(case.surface_exact(x, y, lev)[()])))
    x0, x1, y0, y1 = DIE
    xx, wx = _gl(x0, x1, 32)
    yy, wy = _gl(y0, y1, 32)
    X, Y = np.meshgrid(xx, yy, indexing="ij")
    mean = float(np.outer(wx, wy).ravel() @ case.theta(7, X.ravel(), Y.ravel())) / ((x1 - x0) * (y1 - y0))
    out.append(dict(id="die_mean", kind="area_mean", level="die", x=None, y=None, z=float(Z[7]),
                    rect=[x0, x1, y0, y1], T_K=mean))
    tmax, pmax = _extreme(lambda P: case.theta(7, P[0], P[1]), [[(x0, x1), (y0, y1)]], -1, n=21)
    out.append(dict(id="die_max", kind="max", level="die", x=float(pmax[0]), y=float(pmax[1]), z=float(Z[7]),
                    rect=[x0, x1, y0, y1], T_K=float(tmax)))
    return out


# ----------------------------------------------------------------------------------------------------------------
# Self-checks
# ----------------------------------------------------------------------------------------------------------------
FD6 = np.array([1 / 90, -3 / 20, 3 / 2, -49 / 18, 3 / 2, -3 / 20, 1 / 90])  # Fornberg (1988), 2nd derivative


def _phi(layer, Tc, T, n=16):
    """Kirchhoff potential phi(T) - phi(Tc) = int_Tc^T k(s) ds with the stack's numeric k_at (independent of sympy)."""
    xi, w = np.polynomial.legendre.leggauss(n)
    s = Tc[..., None] + (T - Tc)[..., None] * (1 + xi) / 2
    return (layer.k_at(s) * w).sum(-1) * (T - Tc) / 2


def check_klaws(case):
    worst = 0.0
    Ts = sp.Symbol("T")
    for la in LAYERS:
        hi = AL2O3_BRANCH if la.material == "Al2O3" else 520.0
        T = np.linspace(280.0, hi, 241)
        ks = sp.lambdify(Ts, k_sym(la, Ts), "numpy")(T)
        worst = max(worst, float(np.max(np.abs(ks / la.k_at(T) - 1))))
    return worst


def check_fd(case, seed=FD_SEED, n_per=N_FD_PER_REGION):
    """-div(k grad T*) by 6th-order central differences of the Kirchhoff potential of T* vs the symbolic source."""
    rng = np.random.default_rng(seed)
    worst, n_tot, per_region = 0.0, 0, {}
    hxy = float(mm_to_m(0.25))
    for j in range(7):
        boxes = BOXES[j]
        areas = np.array([(b[1] - b[0]) * (b[3] - b[2]) for b in boxes])
        bi = rng.choice(len(boxes), size=n_per, p=areas / areas.sum())
        bx = np.array(boxes)[bi]
        px = bx[:, 0] + rng.random(n_per) * (bx[:, 1] - bx[:, 0])
        py = bx[:, 2] + rng.random(n_per) * (bx[:, 3] - bx[:, 2])
        t = Z[j + 1] - Z[j]
        hz = t / 16
        pz = Z[j] + 3.5 * hz + rng.random(n_per) * (t - 7 * hz)
        Tc = case.T_layer(j, px, py, pz)
        d2 = []
        for a, h in ((0, hxy), (1, hxy), (2, hz)):
            acc = np.zeros(n_per)
            for m, c in zip(range(-3, 4), FD6, strict=True):
                P = [px, py, pz]
                P[a] = P[a] + m * h
                if m != 0:
                    acc += c * _phi(LAYERS[j], Tc, case.T_layer(j, *P))
            d2.append(acc / h ** 2)
        q_fd = -np.sum(d2, axis=0)
        terms = case.terms_layer(j, px, py, pz)
        q_sym = -terms.sum(axis=0)
        rel = np.abs(q_fd - q_sym) / np.abs(terms).sum(axis=0)
        per_region[NAMES[j]] = float(rel.max())
        worst = max(worst, float(rel.max()))
        n_tot += n_per
    return worst, n_tot, per_region


def check_interfaces(case, seed=IFACE_SEED, n=500):
    rng = np.random.default_rng(seed)
    wT = wF = 0.0
    Gscale = float(np.max(G_FAR + G_PEAK + G_B2))
    for i in range(1, 7):
        both = OCC[i - 1] & OCC[i]
        cells = np.argwhere(both)
        c = cells[rng.integers(0, len(cells), n)]
        px = XB[c[:, 0]] + rng.random(n) * (XB[c[:, 0] + 1] - XB[c[:, 0]])
        py = YB[c[:, 1]] + rng.random(n) * (YB[c[:, 1] + 1] - YB[c[:, 1]])
        pz = np.full(n, Z[i])
        dT = np.abs(case.T_layer(i - 1, px, py, pz) - case.T_layer(i, px, py, pz))
        dF = np.abs(case.F_layer(i - 1, px, py, pz, 2) - case.F_layer(i, px, py, pz, 2))
        wT = max(wT, float(dT.max() / np.abs(case.T_layer(i, px, py, pz)).max()))
        wF = max(wF, float(dF.max() / Gscale))
    return wT, wF


def balances(case, n):
    """Global balance (source + exposed inflow + Robin = 0) and per-region balances (with interface terms)."""
    S = [volume_integral(case, j, n) for j in range(7)]
    exposed, robin, per = 0.0, 0.0, []
    for j in range(7):
        vals = {"exposed": 0.0, "interface": 0.0, "robin": 0.0}
        absum = abs(S[j])
        for pt in patches(j):
            v = patch_integral(case, j, pt, n)
            vals[pt[0]] += v
            absum += abs(v)
        exposed += vals["exposed"]
        robin += vals["robin"]
        per.append(dict(region=NAMES[j], source_W=S[j], exposed_W=vals["exposed"], interface_W=vals["interface"],
                        robin_W=vals["robin"], rel=abs(S[j] + sum(vals.values())) / absum))
    total = sum(S) + exposed + robin
    return dict(source_W=sum(S), exposed_inflow_W=exposed, robin_W=robin, global_rel=abs(total) / abs(robin),
                per_region=per)


def field_stats(case):
    ext = {}
    for j in range(7):
        tmin, pmin, tmax, pmax = region_extremes(case, j)
        kmin, kmax = sorted([float(LAYERS[j].k_at(tmin)), float(LAYERS[j].k_at(tmax))])
        ext[NAMES[j]] = dict(T_min=tmin, at_min=[float(v) for v in pmin], T_max=tmax, at_max=[float(v) for v in pmax],
                             k_min=kmin, k_max=kmax, kvar_over_min=kmax / kmin - 1, kvar_over_max=1 - kmin / kmax)
    tmin = min(e["T_min"] for e in ext.values())
    tmax = max(e["T_max"] for e in ext.values())
    # Robin ambient range over the baseplate bottom
    bp = BOXES[0][0]
    ti_min, _ = _extreme(lambda P: case.T_inf(P[0], P[1]), [[bp[:2], bp[2:]]], +1, n=31)
    ti_max, _ = _extreme(lambda P: case.T_inf(P[0], P[1]), [[bp[:2], bp[2:]]], -1, n=31)
    return dict(regions=ext, T_min=tmin, T_max=tmax, range_K=tmax - tmin, T_inf_min=ti_min, T_inf_max=ti_max)


def selfcheck(verbose=True):
    t0 = time.perf_counter()
    case = build_case()
    t_build = time.perf_counter() - t0
    res, ok = {}, True

    def gate(name, passed, detail):
        nonlocal ok
        ok &= bool(passed)
        res[name] = dict(passed=bool(passed), detail=detail)
        if verbose:
            print(f"[{'PASS' if passed else 'FAIL'}] {name}: {detail}")

    kl = check_klaws(case)
    gate("klaw_transcription", kl <= 1e-12, f"max |k_sym / Layer.k_at - 1| = {kl:.2e} (<= 1e-12)")
    fs = field_stats(case)
    cer = fs["regions"]["ceramic"]
    gate("field_range", RANGE_MIN <= fs["range_K"] <= RANGE_MAX,
         f"T* in [{fs['T_min']:.3f}, {fs['T_max']:.3f}] K, range {fs['range_K']:.3f} K (60-110)")
    gate("k_law_validity", fs["T_min"] >= K_T_MIN and fs["T_max"] <= K_T_MAX
         and K_T_MIN <= fs["T_inf_min"] and fs["T_inf_max"] <= K_T_MAX,
         f"T* and T_inf ({fs['T_inf_min']:.2f}-{fs['T_inf_max']:.2f} K) inside {K_T_MIN}-{K_T_MAX} K")
    gate("ceramic_single_branch", cer["T_max"] < AL2O3_BRANCH - 1.0,
         f"ceramic T* max {cer['T_max']:.3f} K < {AL2O3_BRANCH - 1:.0f} K (one smooth branch of the Al2O3 law)")
    kv = {n: e["kvar_over_min"] for n, e in fs["regions"].items()}
    best = max(kv, key=kv.get)
    gate("k_variation", kv[best] >= KVAR_MIN,
         f"max_layer (k_max/k_min - 1) = {kv[best]:.4f} in {best} (>= {KVAR_MIN}); (k_max-k_min)/k_max = "
         f"{fs['regions'][best]['kvar_over_max']:.4f}; all: " + ", ".join(f"{n} {v:.3f}" for n, v in kv.items()))
    fd, nfd, fdreg = check_fd(case)
    gate("source_vs_fd", fd <= TOL_FD and nfd >= 1000,
         f"{nfd} seeded points (seed {FD_SEED}), max |q_sym - q_fd| / sum_a |d_a(k d_a T)| = {fd:.2e} (<= {TOL_FD})")
    wT, wF = check_interfaces(case)
    gate("interface_continuity", wT <= TOL_IFACE and wF <= TOL_IFACE,
         f"max rel jump: T {wT:.2e}, k dT/dz {wF:.2e} (<= {TOL_IFACE}) over 6 interfaces x 500 points")
    b1, b2 = balances(case, 12), balances(case, 18)
    conv = abs(b1["robin_W"] - b2["robin_W"]) / abs(b2["robin_W"])
    worst_reg = max(r["rel"] for r in b2["per_region"])
    gate("global_balance", b2["global_rel"] <= TOL_BAL and b1["global_rel"] <= TOL_BAL,
         f"|int q dV + int inflow dA - int h(T-T_inf) dA| / Q_out = {b2['global_rel']:.2e} (n=18), "
         f"{b1['global_rel']:.2e} (n=12); Q_out = {-b2['robin_W']:.4f} W, source {b2['source_W']:.4f} W, "
         f"face inflow {b2['exposed_inflow_W']:.4f} W")
    gate("region_balance", worst_reg <= TOL_BAL, f"max per-region relative imbalance {worst_reg:.2e} (n=18)")
    gate("cubature_converged", conv <= 1e-12, f"Q_out change n=12 -> 18: {conv:.2e} (<= 1e-12)")
    if verbose:
        print(f"(build {t_build:.1f} s, total {time.perf_counter() - t0:.1f} s) selfcheck {'PASS' if ok else 'FAIL'}")
    return ok, res, fs, b2, fdreg


# ----------------------------------------------------------------------------------------------------------------
# F3 estimate: own cell-centred finite-volume solve (Patankar 1980) of the manufactured problem, k(T) and constant k
# ----------------------------------------------------------------------------------------------------------------
def _refine(lines, hmax):
    out = [lines[0]]
    for a, b in zip(lines[:-1], lines[1:], strict=True):
        n = max(1, int(math.ceil((b - a) / hmax - 1e-9)))
        out.extend(list(a + (b - a) * np.arange(1, n + 1) / n))
    return np.array(out)


def fv_solve(case, hxy, nz, k_const=None, picard_tol=1e-6, max_picard=60):
    """Steady FV solve with the manufactured data; returns (surface sampler, meta). k_const: per-layer k or None."""
    import pyamg
    import scipy.sparse as sps

    xl, yl = _refine(XB, hxy), _refine(YB, hxy)
    zl = np.concatenate([[Z[0]]] + [Z[j] + (Z[j + 1] - Z[j]) * np.arange(1, nz[j] + 1) / nz[j] for j in range(7)])
    zl[np.cumsum(nz)] = Z[1:]
    xc, yc, zc = 0.5 * (xl[1:] + xl[:-1]), 0.5 * (yl[1:] + yl[:-1]), 0.5 * (zl[1:] + zl[:-1])
    dx, dy, dz = np.diff(xl), np.diff(yl), np.diff(zl)
    NX, NY, NZ = len(xc), len(yc), len(zc)
    Xc, Yc, Zc = np.meshgrid(xc, yc, zc, indexing="ij")
    mat = case.region_of(Xc, Yc, Zc)
    act = mat >= 0
    n = int(act.sum())
    idx = np.full(act.shape, -1)
    idx[act] = np.arange(n)
    gp, gw = np.polynomial.legendre.leggauss(3)
    gw = gw / 2
    I, J, K = np.nonzero(act)  # noqa: E741
    b = np.zeros(n)
    # volumetric source, 3x3x3 Gauss per cell
    for a in range(3):
        for c in range(3):
            for e in range(3):
                px = xc[I] + 0.5 * dx[I] * gp[a]
                py = yc[J] + 0.5 * dy[J] * gp[c]
                pz = zc[K] + 0.5 * dz[K] * gp[e]
                b += gw[a] * gw[c] * gw[e] * case.source(px, py, pz) * dx[I] * dy[J] * dz[K]
    d = (dx, dy, dz)
    lines = (xl, yl, zl)
    cells = (I, J, K)
    pairs, q_top = [], np.zeros((NX, NY))
    robin_cells = robin_A = robin_Tinf = None
    for ax in range(3):
        o1, o2 = [t for t in range(3) if t != ax]
        for sign in (-1, +1):
            nb = [I.copy(), J.copy(), K.copy()]
            nb[ax] = nb[ax] + sign
            N_ax = act.shape[ax]
            inside = (nb[ax] >= 0) & (nb[ax] < N_ax)
            nb_act = np.zeros(n, dtype=bool)
            nb_act[inside] = act[nb[0][inside], nb[1][inside], nb[2][inside]]
            area = d[o1][cells[o1]] * d[o2][cells[o2]]
            if sign > 0:  # interior pairs once
                sel = nb_act
                pairs.append((ax, np.nonzero(sel)[0], idx[nb[0][sel], nb[1][sel], nb[2][sel]], area[sel]))
            exp_ = ~nb_act
            if ax == 2 and sign < 0:
                rob = exp_ & (K == 0)
                exp_ = exp_ & (K != 0)
            sel = np.nonzero(exp_)[0]
            face = lines[ax][cells[ax][sel] + (1 if sign > 0 else 0)]
            Q = np.zeros(sel.size)
            for a in range(3):
                for c in range(3):
                    P = [None, None, None]
                    P[ax] = face
                    P[o1] = 0.5 * (lines[o1][cells[o1][sel]] + lines[o1][cells[o1][sel] + 1]) + 0.5 * d[o1][cells[o1][sel]] * gp[a]
                    P[o2] = 0.5 * (lines[o2][cells[o2][sel]] + lines[o2][cells[o2][sel] + 1]) + 0.5 * d[o2][cells[o2][sel]] * gp[c]
                    Q += gw[a] * gw[c] * case.flux(P[0], P[1], P[2], ax, sign)
            b[sel] += Q * area[sel]
            if ax == 2 and sign > 0:
                top = sel[(K[sel] == NZ - 1) | ~act[I[sel], J[sel], np.minimum(K[sel] + 1, NZ - 1)]]
                qmap = dict(zip(sel.tolist(), Q.tolist(), strict=True))
                for cidx in top:
                    q_top[I[cidx], J[cidx]] = qmap[cidx]
            if ax == 2 and sign < 0:
                robin_cells = np.nonzero(rob)[0]
                robin_A = area[robin_cells]
                Ti = np.zeros(robin_cells.size)
                for a in range(3):
                    for c in range(3):
                        Ti += gw[a] * gw[c] * case.T_inf(xc[I[robin_cells]] + 0.5 * dx[I[robin_cells]] * gp[a],
                                                         yc[J[robin_cells]] + 0.5 * dy[J[robin_cells]] * gp[c])
                robin_Tinf = Ti
    lay = mat[act]

    def kcell(T):
        k = np.empty(n)
        for j in range(7):
            m = lay == j
            k[m] = k_const[j] if k_const is not None else LAYERS[j].k_at(T[m])
        return k

    T = np.full(n, float(np.mean(robin_Tinf)))
    it = 0
    for it in range(1, max_picard + 1):  # noqa: B007 (it is reported after the loop)
        k = kcell(T)
        rows, cols, vals = [], [], []
        diag = np.zeros(n)
        for ax, a_, b_, A in pairs:
            g = A / (d[ax][cells[ax][a_]] / (2 * k[a_]) + d[ax][cells[ax][b_]] / (2 * k[b_]))
            rows += [a_, b_]
            cols += [b_, a_]
            vals += [-g, -g]
            np.add.at(diag, a_, g)
            np.add.at(diag, b_, g)
        gR = robin_A / (dz[0] / (2 * k[robin_cells]) + 1 / case.h)
        np.add.at(diag, robin_cells, gR)
        rhs = b.copy()
        np.add.at(rhs, robin_cells, gR * robin_Tinf)
        M = sps.coo_matrix((np.concatenate(vals + [diag]), (np.concatenate(rows + [np.arange(n)]),
                            np.concatenate(cols + [np.arange(n)]))), shape=(n, n)).tocsr()
        ml = pyamg.smoothed_aggregation_solver(M, symmetry="symmetric")
        Tn = ml.solve(rhs, x0=T, tol=1e-13, accel="cg", maxiter=1000)
        dT = float(np.max(np.abs(Tn - T)))
        T = Tn
        if k_const is not None or dT < picard_tol:
            break
    k = kcell(T)
    Tg = np.full(act.shape, np.nan)
    Tg[act] = T
    kg = np.full(act.shape, np.nan)
    kg[act] = k
    ktop = NZ - 1 - np.argmax(act[:, :, ::-1], axis=2)
    ii, jj = np.meshgrid(np.arange(NX), np.arange(NY), indexing="ij")
    Ts = Tg[ii, jj, ktop] + q_top * dz[ktop] / (2 * kg[ii, jj, ktop])
    ztop = zl[ktop + 1]

    def sample(x, y):
        i0 = int(np.clip(np.searchsorted(xc, x) - 1, 0, NX - 2))
        j0 = int(np.clip(np.searchsorted(yc, y) - 1, 0, NY - 2))
        zz = ztop[i0:i0 + 2, j0:j0 + 2]
        if np.ptp(zz) > 1e-12:
            raise ValueError("bilinear stencil crosses a surface-level change")
        u = (x - xc[i0]) / (xc[i0 + 1] - xc[i0])
        v = (y - yc[j0]) / (yc[j0 + 1] - yc[j0])
        s = Ts[i0:i0 + 2, j0:j0 + 2]
        return float((1 - u) * (1 - v) * s[0, 0] + u * (1 - v) * s[1, 0] + (1 - u) * v * s[0, 1] + u * v * s[1, 1])

    x0, x1, y0, y1 = DIE
    die_cols = np.outer((xc > x0) & (xc < x1), (yc > y0) & (yc < y1))
    Aij = np.outer(dx, dy)
    die_mean = float((Ts * Aij)[die_cols].sum() / Aij[die_cols].sum())
    q_out = float(np.sum(gR * (T[robin_cells] - robin_Tinf)))
    q_in = float(b.sum())
    return sample, dict(n_cells=n, picard_iters=it, die_mean=die_mean, die_max_cells=float(np.nanmax(Ts[die_cols])),
                        energy_balance=abs(q_out / q_in - 1))


def f3_estimate(case, pts, verbose=True):
    """Shift of the reported points when every layer has constant k at its volume-mean T* (F3's dT_const_k)."""
    tbar = [volume_integral(case, j, 8, fn="T") / region_volume(j) for j in range(7)]
    kbar = [float(LAYERS[j].k_at(tbar[j])) for j in range(7)]
    levels = [(float(mm_to_m(0.5)), [6, 2, 2, 4, 2, 2, 3]), (float(mm_to_m(0.25)), [12, 4, 4, 8, 4, 4, 6])]
    out = []
    for hxy, nz in levels:
        t0 = time.perf_counter()
        sk, mk = fv_solve(case, hxy, nz)
        sc, mc = fv_solve(case, hxy, nz, k_const=kbar)
        rows = []
        for p in pts:
            if p["kind"] == "point" or p["kind"] == "max":
                v_k, v_c = sk(p["x"], p["y"]), sc(p["x"], p["y"])
            else:
                v_k, v_c = mk["die_mean"], mc["die_mean"]
            rows.append(dict(id=p["id"], T_ref=p["T_K"], T_fv_kT=v_k, T_fv_constk=v_c, err_kT=v_k - p["T_K"],
                             dT_const_k=v_c - p["T_K"], constk_minus_kT=v_c - v_k))
        lev = dict(hxy_m=hxy, nz=nz, n_cells=mk["n_cells"], picard_iters=mk["picard_iters"],
                   energy_balance_kT=mk["energy_balance"], energy_balance_constk=mc["energy_balance"],
                   wall_s=time.perf_counter() - t0, rows=rows)
        out.append(lev)
        if verbose:
            print(f"F3 FV level hxy={hxy * 1e3:.2f} mm: {mk['n_cells']} cells, {mk['picard_iters']} Picard, "
                  f"balance {mk['energy_balance']:.1e}; max |T_fv(kT)-T*| = "
                  f"{max(abs(r['err_kT']) for r in rows):.4f} K; max |dT_const_k| = "
                  f"{max(abs(r['dT_const_k']) for r in rows):.4f} K; max |T_constk - T_kT| = "
                  f"{max(abs(r['constk_minus_kT']) for r in rows):.4f} K ({lev['wall_s']:.0f} s)")
    return dict(layer_mean_T=dict(zip(NAMES, tbar, strict=True)), layer_k_const=dict(zip(NAMES, kbar, strict=True)), levels=out)


# ----------------------------------------------------------------------------------------------------------------
def _canon(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def emit(path: Path):
    ok, res, fs, bal, fdreg = selfcheck()
    if not ok:
        print("self-check failed: nothing emitted")
        return 1
    case = build_case()
    pts = reported_points(case)
    f3 = f3_estimate(case, pts)
    fine = f3["levels"][-1]["rows"]
    scale = fs["range_K"]
    worst_c = max(abs(r["constk_minus_kT"]) for r in fine)
    worst_d = max(abs(r["dT_const_k"]) for r in fine)
    payload = dict(
        case="E006-manufactured", task="T0153", units="SI (m, K, W)",
        geometry=dict(z_interfaces_m=Z.tolist(), regions=[dict(index=j, name=NAMES[j], material=LAYERS[j].material,
                      k_300K=LAYERS[j].k, boxes_m=[list(b) for b in BOXES[j]]) for j in range(7)],
                      note="region j occupies z_j..z_{j+1} over the union of its boxes; everything else is void"),
        field=dict(construction="per-layer cubic Hermite in z with shared interface data Theta_i, G_i",
                   XD=XD, YD=YD, SX=SX, SY=SY, X2=X2, Y2=Y2, S2=S2, TILT_X=TILT_X, TILT_Y=TILT_Y,
                   G_FAR=G_FAR.tolist(), G_PEAK=G_PEAK.tolist(), G_B2=G_B2.tolist(),
                   THETA_A=A_TH.tolist(), THETA_B=B_TH.tolist(), THETA_C=C_TH.tolist()),
        bc=dict(robin_z0=dict(h=H, T_inf="Theta_0(x, y) - G_0(x, y) / h"),
                flux="inflow k dT*/dn (W/m^2, positive heats the cell) on every exterior and void-bounding face; "
                     "0 on z = 0 (Robin)", source="q''' = -div(k(T*) grad T*) per region"),
        field_range=dict(T_min=fs["T_min"], T_max=fs["T_max"], range_K=scale),
        case_scale_K=scale,
        k_variation={n: dict(k_min=e["k_min"], k_max=e["k_max"], kvar_over_min=e["kvar_over_min"],
                             T_min=e["T_min"], T_max=e["T_max"]) for n, e in fs["regions"].items()},
        reported_points=pts,
    )
    sha = hashlib.sha256(_canon(payload).encode()).hexdigest()
    src = Path(__file__).read_bytes()
    doc = dict(sha256_payload=sha, payload=payload,
               provenance=dict(runner="experiments/runners/e006_mms.py", runner_sha256=hashlib.sha256(src).hexdigest(),
                               sympy=sp.__version__, numpy=np.__version__,
                               generated=time.strftime("%Y-%m-%dT%H:%M:%S%z")),
               selfcheck=res, fd_per_region=fdreg, balance=bal, T_inf_range=[fs["T_inf_min"], fs["T_inf_max"]],
               f3_estimate=dict(f3, summary=dict(
                   max_abs_constk_minus_kT_K=worst_c, max_abs_dT_const_k_K=worst_d,
                   a1_threshold_K=0.01 * scale, a2_threshold_K=0.05,
                   expected_to_fail_A1=worst_c > 0.01 * scale, expected_to_fail_A2=worst_c > 0.05)))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=1) + "\n")
    print(f"wrote {path} sha256_payload {sha}")
    print(f"F3: max |T_constk - T_kT| = {worst_c:.3f} K vs A1 {0.01 * scale:.3f} K, A2 0.05 K")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--selfcheck", action="store_true")
    ap.add_argument("--emit", type=Path)
    a = ap.parse_args()
    if a.emit:
        sys.exit(emit(a.emit))
    if a.selfcheck:
        sys.exit(0 if selfcheck()[0] else 1)
    ap.print_help()
    sys.exit(2)
