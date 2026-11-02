"""E006 analytic thermal references: Muzychka 2003 flux-channel series and an N-layer Fourier series (F1 gates).

Own implementation of the steady surface temperature of a rectangular flux channel (lateral size a x b, adiabatic
sides, uniform film coefficient h to a fluid at T_f on the sink plane) heated by uniform-flux rectangular sources on
the top face. No solver code is used: the module imports only numpy, scipy.special/optimize and, for the material
constants of the N-layer case, ``moduleforge.geometry.stack``.

References (equation numbers refer to these papers; see research/notes/o006-reference-series.md):
  [M03] Y. S. Muzychka, J. R. Culham, M. M. Yovanovich, "Thermal spreading resistance of eccentric heat sources on
        rectangular flux channels", J. Electron. Packag. 125(2):178-185 (2003), doi:10.1115/1.1568125.
        Eq. (16) general solution, (18) single-layer phi, (20)/(22)/(24) Fourier coefficients A_m, A_n, A_mn,
        (25) A_0, (27) source-mean temperature, (28)/(31) 1D excess, (30) compound (two-layer) phi,
        (37)-(41) superposition of N sources; Tables 1-4 and the Case 3 text give the printed values.
  [A95] J. Albers, "An exact recursion relation solution for the steady-state surface temperature of a general
        multilayer structure", IEEE Trans. CPMT-A 18(1):31-38 (1995), doi:10.1109/95.370732 (abstract read).
  [B14] K. R. Bagnall, Y. S. Muzychka, E. N. Wang, IEEE TCPMT 4(5):817-830 (2014), doi:10.1109/TCPMT.2014.2299766.
  [C19] A. Choudhury, D. J. Rogers, IEEE TPEL 34(2):1500-1508 (2019), doi:10.1109/TPEL.2018.2828439.
  The N-layer kernel below is derived in the notes (layer-by-layer input impedance of each Fourier mode, the
  recursion family of [A95]/[B14]/[C19]); it is checked against an explicit boundary-value linear system and against
  [M03] eq. (30).

Series acceleration (notes, section 4). Every mode (lambda_m, delta_n), beta = sqrt(lambda^2 + delta^2), of the
surface temperature carries the kernel Z(beta) = theta/flux. Split Z = 1/(k_top beta) + R(beta): R decays like
exp(-2 beta t_top) and is summed directly (exponential convergence); the infinite-depth part is summed exactly
through 1/beta = (2/sqrt(pi)) int_0^inf exp(-beta^2 s^2) ds, which makes the double sum separable into two 1D
heat-kernel sums, each evaluated by erf images (small s) or its cosine series (large s; Poisson summation).

CLI:  --selfcheck  run F1's gates (exit 1 on any failure)
      --emit PATH  write every reference value with a sha256 (research/e006_refs/series_values.json)
SI units and kelvin internally; degrees Celsius only for comparison with the paper's printed values.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import time
from dataclasses import dataclass, replace

import numpy as np
from scipy.optimize import minimize
from scipy.special import erf, erfc

from moduleforge.geometry.stack import default_dbc_stack
from moduleforge.geometry.units import m_to_mm, mm_to_m

KELVIN_OFFSET = 273.15
SQRT_PI = math.sqrt(math.pi)


def c_to_k(t_c):
    """Degrees Celsius to kelvin."""
    return t_c + KELVIN_OFFSET


def k_to_c(t_k):
    """Kelvin to degrees Celsius."""
    return t_k - KELVIN_OFFSET


# ----------------------------------------------------------------------------------------------------------------------
# Geometry and cases
# ----------------------------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Source:
    """Uniform-flux rectangular source on the top face: centroid (xc, yc), size c (x) by d (y) [m], power Q [W]."""

    name: str
    xc: float
    yc: float
    c: float
    d: float
    Q: float

    @property
    def x1(self) -> float:
        return self.xc - self.c / 2

    @property
    def x2(self) -> float:
        return self.xc + self.c / 2

    @property
    def y1(self) -> float:
        return self.yc - self.d / 2

    @property
    def y2(self) -> float:
        return self.yc + self.d / 2

    @property
    def q(self) -> float:
        return self.Q / (self.c * self.d)


@dataclass(frozen=True)
class Case:
    """Flux channel a x b [m]; ``layers`` bottom-up as (name, thickness [m], k [W/(m K)]); sink h [W/(m^2 K)] to a
    fluid at Tf [K]. ``kernel``: 'M03' uses [M03] eq. (18) (one layer) or eq. (30) (two layers); 'nlayer' uses the
    N-layer recursion."""

    name: str
    a: float
    b: float
    layers: tuple[tuple[str, float, float], ...]
    h: float
    Tf: float
    sources: tuple[Source, ...]
    kernel: str = "M03"
    note: str = ""

    @property
    def top_down(self) -> tuple[tuple[str, float, float], ...]:
        return tuple(reversed(self.layers))

    @property
    def k_top(self) -> float:
        return self.top_down[0][2]

    @property
    def t_top(self) -> float:
        return self.top_down[0][1]

    @property
    def r1d_area(self) -> float:
        """Area-specific 1D resistance sum(t_i/k_i) + 1/h [m^2 K/W] ([M03] eq. (28)/(31); Muzychka 2004 eq. (4))."""
        return sum(t / k for _, t, k in self.layers) + 1.0 / self.h

    @property
    def Q_total(self) -> float:
        return sum(s.Q for s in self.sources)

    @property
    def T_1d(self) -> float:
        """1D uniform-flux surface temperature: the whole power spread uniformly over the top face (= A_0 summed over
        the sources, [M03] eq. (25)/(28)/(31); the paper's mean base temperature T_b of Tables 1-2)."""
        return self.Tf + self.Q_total * self.r1d_area / (self.a * self.b)


def _mm(x: float) -> float:
    return mm_to_m(x)


def case_1a() -> Case:
    """[M03] Case 1 (Table 1): 300 x 300 x 10 mm plate, k = 10, h = 10, Tf = 25 C, two 25 x 25 mm sources."""
    return Case(
        "case1a", _mm(300.0), _mm(300.0), (("plate", _mm(10.0), 10.0),), 10.0, c_to_k(25.0),
        (Source("s1", _mm(90.0), _mm(90.0), _mm(25.0), _mm(25.0), 10.0),
         Source("s2", _mm(210.0), _mm(210.0), _mm(25.0), _mm(25.0), 15.0)),
        note="M03 Case 1 / Table 1")


def case_1b() -> Case:
    """[M03] Case 1b (Table 2): Case 1a plus a 2 mm, k = 350 spreader on top (sources on the spreader)."""
    c = case_1a()
    return replace(c, name="case1b", layers=(("plate", _mm(10.0), 10.0), ("spreader", _mm(2.0), 350.0)),
                   note="M03 Case 1b / Table 2: layer 1 (top) = 2 mm k=350 spreader, layer 2 = 10 mm k=10 plate")


CASE2_TF_C = 25.0  # [M03] Case 2 does not state Tf; fixed here to 25 C (the value of Cases 1 and 3), see notes.


def case_2() -> Case:
    """[M03] Case 2 (Tables 3-4): 50 x 50 x 10 mm baseplate, k = 150, h = 400, four 10 x 10 mm sources; Tf fixed."""
    srcs = (("s1", 10.0, 12.5, 12.5), ("s2", 25.0, 37.5, 12.5), ("s3", 20.0, 12.5, 37.5), ("s4", 15.0, 37.5, 37.5))
    return Case(
        "case2", _mm(50.0), _mm(50.0), (("baseplate", _mm(10.0), 150.0),), 400.0, c_to_k(CASE2_TF_C),
        tuple(Source(n, _mm(x), _mm(y), _mm(10.0), _mm(10.0), q) for n, q, x, y in srcs),
        note="M03 Case 2 / Tables 3-4; Tf not stated in the paper, fixed to 25 C")


def case_3() -> Case:
    """[M03] Case 3: 100 x 100 x 10 mm plate, k = 50, h = 50, Tf = 25 C, five 20 x 20 mm 5 W sources in a cross."""
    pos = (("centre", 50.0, 50.0), ("west", 30.0, 50.0), ("east", 70.0, 50.0), ("south", 50.0, 30.0),
           ("north", 50.0, 70.0))
    return Case(
        "case3", _mm(100.0), _mm(100.0), (("plate", _mm(10.0), 50.0),), 50.0, c_to_k(25.0),
        tuple(Source(n, _mm(x), _mm(y), _mm(20.0), _mm(20.0), 5.0) for n, x, y in pos),
        note="M03 Case 3: cross-shaped iso-flux source = five 20 x 20 mm squares")


# N-layer case: laterally uniform default DBC stack + die attach + SiC die (constant k = Layer.k at 300 K), on the
# generator's baseplate box (moduleforge.generate.halfbridge: -8..78 x -8..48 mm, i.e. 86 x 56 mm), coolant 65 C and
# h = 5000 W/(m^2 K) as in O006 pilot P1. Die-sized sources (4.0-5.5 mm), powers chosen so that the per-die maximum
# rises above the coolant lie in the O002 band of 60-110 K (a first choice of 95/175/130/115 W gave 102-126 K; all
# powers were scaled by 0.8, the problem being linear; set from this reference alone, before any solver comparison); one die near a corner and one near an edge exercise the
# adiabatic walls, one is rectangular. Coordinates are relative to the baseplate box's lower-left corner.
NLAYER_A_MM, NLAYER_B_MM = 86.0, 56.0
NLAYER_H = 5000.0
NLAYER_TF_C = 65.0
NLAYER_SOURCES_MM = (  # name, xc, yc, c, d [mm], Q [W]
    ("d1", 20.0, 18.0, 4.0, 4.0, 76.0),
    ("d2", 31.0, 18.0, 5.5, 5.5, 140.0),
    ("d3", 55.0, 36.0, 4.5, 4.5, 104.0),
    ("d4", 79.5, 49.0, 5.0, 4.0, 92.0),
)


def nlayer_layers() -> tuple[tuple[str, float, float], ...]:
    """Bottom-up (name, t, k) of the default DBC stack plus die attach and die, k = Layer.k (300 K) from
    moduleforge.geometry.stack (citations there)."""
    st = default_dbc_stack()
    out = [(la.name, la.thickness, la.k) for la in st.layers]
    out.append((st.die_attach.name, st.die_attach.thickness, st.die_attach.k))
    out.append((st.die.name, st.die.thickness, st.die.k))
    return tuple(out)


def case_nlayer() -> Case:
    return Case(
        "nlayer_dbc", _mm(NLAYER_A_MM), _mm(NLAYER_B_MM), nlayer_layers(), NLAYER_H, c_to_k(NLAYER_TF_C),
        tuple(Source(n, _mm(x), _mm(y), _mm(c), _mm(d), q) for n, x, y, c, d, q in NLAYER_SOURCES_MM),
        kernel="nlayer",
        note="laterally uniform default DBC stack + SAC305 die attach + 4H-SiC die, constant k; 86 x 56 mm")


def all_cases() -> list[Case]:
    return [case_1a(), case_1b(), case_2(), case_3(), case_nlayer()]


# ----------------------------------------------------------------------------------------------------------------------
# Mode kernels. All return the dimensionless excess  E(beta) = k_top * beta * Z(beta) - 1,  where Z = theta/flux of the
# mode at the top surface. Z = 1/(k_top beta) for an infinitely deep top layer, so E -> 0 like exp(-2 beta t_top).
# ----------------------------------------------------------------------------------------------------------------------
def phi_single(z, t, k, h):
    """[M03] eq. (18): phi = (z sinh(zt) + h/k cosh(zt)) / (z cosh(zt) + h/k sinh(zt)) (tanh form, no overflow)."""
    z = np.asarray(z, dtype=float)
    th = np.tanh(z * t)
    H = h / k
    return (z * th + H) / (z + H * th)


def excess_single(z, t, k, h):
    """1/phi - 1 for [M03] eq. (18): 1/phi - 1 = (z - H)(1 - T)/(z T + H), T = tanh(zt) = (1 - e)/(1 + e),
    e = exp(-2 z t), i.e. the cancellation-free form 2 (z - H) e / ((z + H) - (z - H) e)."""
    z = np.asarray(z, dtype=float)
    H = h / k
    e = np.exp(-2.0 * z * t)
    return 2.0 * (z - H) * e / ((z + H) - (z - H) * e)


def _compound_num_den(z, t1, k1, t2, k2, h):
    """Numerator and denominator of [M03] eq. (30), both multiplied by (z - h/k2) exp(-2 z (2 t1 + t2)).

    eq. (30): phi = [(alpha e^{4zt1} - e^{2zt1}) + rho (e^{2z(2t1+t2)} - alpha e^{2z(t1+t2)})]
                  / [(alpha e^{4zt1} + e^{2zt1}) + rho (e^{2z(2t1+t2)} + alpha e^{2z(t1+t2)})],
    rho = (z + h/k2)/(z - h/k2), alpha = (1 - kappa)/(1 + kappa), kappa = k2/k1. The scaling removes the overflow
    and the removable pole of rho at z = h/k2; it is an exact algebraic identity."""
    z = np.asarray(z, dtype=float)
    H = h / k2
    kap = k2 / k1
    alpha = (1.0 - kap) / (1.0 + kap)
    E1 = np.exp(-2.0 * z * t1)
    E2 = np.exp(-2.0 * z * t2)
    E12 = np.exp(-2.0 * z * (t1 + t2))
    num = (z - H) * (alpha * E2 - E12) + (z + H) * (1.0 - alpha * E1)
    den = (z - H) * (alpha * E2 + E12) + (z + H) * (1.0 + alpha * E1)
    return num, den, (z, H, alpha, E1, E12)


def phi_compound(z, t1, k1, t2, k2, h):
    """[M03] eq. (30) (two layers: 1 = top/source layer, 2 = bottom layer with h on its lower face)."""
    num, den, _ = _compound_num_den(z, t1, k1, t2, k2, h)
    return num / den


def excess_compound(z, t1, k1, t2, k2, h):
    """1/phi - 1 for [M03] eq. (30): (den - num)/num = 2 [(z - H) E12 + (z + H) alpha E1] / num (no cancellation)."""
    num, _, (z, H, alpha, E1, E12) = _compound_num_den(z, t1, k1, t2, k2, h)
    return 2.0 * ((z - H) * E12 + (z + H) * alpha * E1) / num


def excess_nlayer(beta, layers_top_down, h):
    """N-layer excess E = k_1 beta Z - 1 by the input-impedance recursion (notes eq. N3-N5).

    For a mode exp-dependence cos(lambda x) cos(delta y), each layer i (k_i, t_i) obeys theta'' = beta^2 theta in z.
    With the normalised impedance at the *bottom* of layer i, rho_i = k_i beta Z_i,bottom, the normalised impedance at
    its top is (rho_i + T_i) / (1 + rho_i T_i), T_i = tanh(beta t_i); across an interface (perfect contact) Z is
    continuous, so rho_{i-1,bottom} = (k_{i-1}/k_i) rho_{i,top}. At the sink, Z = 1/h, so rho_N = k_N beta / h.
    For the top layer the normalised impedance is written (1 + G e)/(1 - G e), G = (rho_1 - 1)/(rho_1 + 1),
    e = exp(-2 beta t_1), so E = 2 G e / (1 - G e) without cancellation."""
    beta = np.asarray(beta, dtype=float)
    lay = list(layers_top_down)
    k_n = lay[-1][2]
    rho = k_n * beta / h  # bottom of the lowest layer
    for i in range(len(lay) - 1, 0, -1):
        t_i, k_i = lay[i][1], lay[i][2]
        T = np.tanh(beta * t_i)
        top = (rho + T) / (1.0 + rho * T)
        rho = (lay[i - 1][2] / k_i) * top  # continuity of Z: rho_{i-1} = k_{i-1} beta Z = (k_{i-1}/k_i) top
    t1 = lay[0][1]
    G = (rho - 1.0) / (rho + 1.0)
    e = np.exp(-2.0 * beta * t1)
    return 2.0 * G * e / (1.0 - G * e)


def z_nlayer_linear_system(beta: float, layers_top_down, h) -> float:
    """Independent check of the recursion: solve the 2N x 2N boundary-value system for one mode explicitly.

    Layer i occupies z_i < z < z_{i+1} (z downward from the source plane), theta_i = A_i cosh(beta (z - z_i)) +
    B_i sinh(beta (z - z_i)). Conditions: -k_1 theta_1'(0) = 1 (unit flux in); theta and k theta' continuous at each
    interface; -k_N theta_N'(t) = h theta_N(t). Returns Z = theta_1(0) = A_1 [K m^2/W]."""
    lay = list(layers_top_down)
    n = len(lay)
    M = np.zeros((2 * n, 2 * n))
    rhs = np.zeros(2 * n)
    M[0, 1] = -lay[0][2] * beta  # -k1 * beta * B_1 = 1
    rhs[0] = 1.0
    row = 1
    for i in range(n - 1):
        t, k = lay[i][1], lay[i][2]
        kn = lay[i + 1][2]
        ch, sh = math.cosh(beta * t), math.sinh(beta * t)
        M[row, 2 * i], M[row, 2 * i + 1], M[row, 2 * i + 2] = ch, sh, -1.0  # temperature continuity
        row += 1
        M[row, 2 * i] = k * beta * sh  # flux continuity: k theta' at the bottom of i = k_n theta' at top of i+1
        M[row, 2 * i + 1] = k * beta * ch
        M[row, 2 * i + 3] = -kn * beta
        row += 1
    t, k = lay[-1][1], lay[-1][2]
    ch, sh = math.cosh(beta * t), math.sinh(beta * t)
    M[row, 2 * n - 2] = k * beta * sh + h * ch  # k theta' + h theta = 0 at the sink
    M[row, 2 * n - 1] = k * beta * ch + h * sh
    sol = np.linalg.solve(M, rhs)
    return float(sol[0])


def mode_excess(case: Case, beta):
    """E(beta) = k_top beta Z(beta) - 1 for the case's kernel."""
    td = case.top_down
    if case.kernel == "nlayer":
        return excess_nlayer(beta, td, case.h)
    if len(td) == 1:
        return excess_single(beta, td[0][1], td[0][2], case.h)
    if len(td) == 2:
        return excess_compound(beta, td[0][1], td[0][2], td[1][1], td[1][2], case.h)
    raise ValueError("kernel 'M03' supports one or two layers")


# ----------------------------------------------------------------------------------------------------------------------
# Targets: a point (x, y) or the mean over a rectangular patch [x1, x2] x [y1, y2]. 1D factors per direction.
# ----------------------------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Target:
    kind: str  # "point" or "patch"
    x1: float
    x2: float
    y1: float
    y2: float

    @staticmethod
    def point(x: float, y: float) -> Target:
        return Target("point", x, x, y, y)

    @staticmethod
    def patch(src: Source) -> Target:
        return Target("patch", src.x1, src.x2, src.y1, src.y2)


def _cos_factor(lam: np.ndarray, p1: np.ndarray, p2: np.ndarray, is_patch: np.ndarray) -> np.ndarray:
    """Value of cos(lam x) at a point (p1 = p2), or its mean over [p1, p2]; shape (P, M)."""
    lam = lam[None, :]
    p1 = p1[:, None]
    p2 = p2[:, None]
    with np.errstate(invalid="ignore", divide="ignore"):
        mean = (np.sin(lam * p2) - np.sin(lam * p1)) / (lam * (p2 - p1))
    mean = np.where(lam == 0.0, 1.0, mean)
    return np.where(is_patch[:, None], mean, np.cos(lam * p1))


def _src_coeff(lam: np.ndarray, length: float, lo: float, hi: float) -> np.ndarray:
    """Cosine coefficients a_m of the indicator of [lo, hi] on [0, length] (Neumann): a_0 = (hi-lo)/length,
    a_m = (2/length) (sin(lam hi) - sin(lam lo))/lam."""
    out = np.empty_like(lam)
    out[0] = (hi - lo) / length
    lm = lam[1:]
    out[1:] = (2.0 / length) * (np.sin(lm * hi) - np.sin(lm * lo)) / lm
    return out


# ----------------------------------------------------------------------------------------------------------------------
# Accuracy configuration (all "terms" knobs; ``doubled`` doubles every one of them)
# ----------------------------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Acc:
    cut: float = 36.0  # remainder modes up to beta with 2 beta t_top >= cut (exp(-36) = 2.3e-16), per direction
    min_modes: int = 64
    panel_w: float = 0.5  # width of the Gauss-Legendre panels in u = ln s
    gl_nodes: int = 12
    s_lo_rel: float = 1e-12  # lower end of the s-integral relative to min(a, b); [0, s_lo] taken as s_lo f(s_lo)
    s_hi_rel: float = 3.0  # upper end relative to max(a, b): integrand ~ exp(-(pi s / max(a,b))^2) = exp(-89)
    n_images: int = 3  # erf images j = -J..J (used for s <= switch * length)
    n_fourier: int = 16  # cosine terms of the 1D heat kernel (used for s > switch * length)
    switch: float = 0.25

    def doubled(self, what: str = "all") -> Acc:
        d = {}
        if what in ("all", "modes"):
            d.update(cut=2 * self.cut, min_modes=2 * self.min_modes)
        if what in ("all", "quad"):
            d.update(panel_w=self.panel_w / 2, s_lo_rel=self.s_lo_rel ** 2, s_hi_rel=2 * self.s_hi_rel)
        if what in ("all", "images"):
            d.update(n_images=2 * self.n_images, n_fourier=2 * self.n_fourier)
        return replace(self, **d)


def mode_counts(case: Case, acc: Acc) -> tuple[int, int]:
    beta_cut = acc.cut / (2.0 * case.t_top)
    mx = max(acc.min_modes, math.ceil(beta_cut * case.a / math.pi))
    my = max(acc.min_modes, math.ceil(beta_cut * case.b / math.pi))
    return mx, my


def _s_nodes(case: Case, acc: Acc) -> tuple[np.ndarray, np.ndarray, float]:
    """Composite Gauss-Legendre nodes and weights in s for int_{s_lo}^{s_hi} f(s) ds via u = ln s."""
    s_lo = acc.s_lo_rel * min(case.a, case.b)
    s_hi = acc.s_hi_rel * max(case.a, case.b)
    u0, u1 = math.log(s_lo), math.log(s_hi)
    npan = math.ceil((u1 - u0) / acc.panel_w)
    edges = np.linspace(u0, u1, npan + 1)
    xg, wg = np.polynomial.legendre.leggauss(acc.gl_nodes)
    mid = 0.5 * (edges[1:] + edges[:-1])
    half = 0.5 * (edges[1:] - edges[:-1])
    u = (mid[:, None] + half[:, None] * xg[None, :]).ravel()
    w = (half[:, None] * wg[None, :]).ravel()
    s = np.exp(u)
    return s, w * s, s_lo  # ds = s du


# ----------------------------------------------------------------------------------------------------------------------
# Infinite-depth part: theta_inf = (q / k_top) (2/sqrt(pi)) int_0^inf [Fx Fy - a0 b0] ds  (notes eq. S1-S4)
# ----------------------------------------------------------------------------------------------------------------------
def _erf_prim_rest(u: np.ndarray, s: np.ndarray) -> np.ndarray:
    """P(u) - |u| for the antiderivative P(u) = u erf(u/(2s)) + (2s/sqrt(pi)) exp(-u^2/(4 s^2)) of erf(u/(2s)):
    -|u| erfc(|u|/(2s)) + (2s/sqrt(pi)) exp(-u^2/(4 s^2)), small for |u| >> s (no cancellation)."""
    au = np.abs(u)
    return -au * erfc(au / (2.0 * s)) + (2.0 * s / SQRT_PI) * np.exp(-(u * u) / (4.0 * s * s))


def _erf_mean(u1: np.ndarray, u2: np.ndarray, dp: np.ndarray, s: np.ndarray) -> np.ndarray:
    """(P(u2) - P(u1)) / dp with u2 - u1 = dp: |u2| - |u1| is formed exactly as +dp, -dp or u1 + u2 (straddling 0),
    so far images (|u| >> dp) carry no cancellation error eps |u| / dp."""
    dabs = np.where(u1 >= 0.0, dp, np.where(u2 <= 0.0, -dp, u1 + u2))
    return (dabs + _erf_prim_rest(u2, s) - _erf_prim_rest(u1, s)) / dp


def heat1d_images(p1, p2, is_patch, lo, hi, length, s, n_images):
    """F(x, s) - a0 by images: the indicator of [lo, hi] on [0, length] with Neumann ends, smoothed by the heat kernel
    at time s^2; point value (p1 = p2) or mean over [p1, p2]. Arrays: p1, p2, is_patch (P,), s (S,) -> (P, S)."""
    p1 = p1[:, None, None]
    p2 = p2[:, None, None]
    pat = is_patch[:, None, None]
    ss = s[None, :, None]
    j = np.arange(-n_images, n_images + 1, dtype=float)[None, None, :] * (2.0 * length)
    # edges of the source and of its mirror image about x = 0, with sign +1/2 for the lower edge and -1/2 the upper
    terms = ((-lo, 0.5), (-hi, -0.5), (hi, 0.5), (lo, -0.5))
    dp = np.where(pat, p2 - p1, 1.0)
    out = 0.0
    for shift, sign in terms:
        u1 = p1 + shift + j
        u2 = p2 + shift + j
        val_pt = erf(u1 / (2.0 * ss))
        val_pa = _erf_mean(u1, u2, dp, ss)
        out = out + sign * np.where(pat, val_pa, val_pt).sum(axis=2)
    return out - (hi - lo) / length


def heat1d_fourier(p1, p2, is_patch, lo, hi, length, s, n_terms):
    """F(x, s) - a0 by its cosine series sum_{m>=1} a_m cos(lam_m x) exp(-lam_m^2 s^2) (Poisson dual of the images)."""
    lam = np.arange(n_terms + 1, dtype=float) * math.pi / length
    a = _src_coeff(lam, length, lo, hi)[1:]
    cf = _cos_factor(lam, p1, p2, is_patch)[:, 1:]  # (P, M)
    g = np.exp(-(lam[1:, None] ** 2) * (s[None, :] ** 2))  # (M, S)
    return (cf * a[None, :]) @ g


def heat1d(p1, p2, is_patch, lo, hi, length, s, acc: Acc):
    out = np.empty((p1.size, s.size))
    small = s <= acc.switch * length
    if small.any():
        out[:, small] = heat1d_images(p1, p2, is_patch, lo, hi, length, s[small], acc.n_images)
    if (~small).any():
        out[:, ~small] = heat1d_fourier(p1, p2, is_patch, lo, hi, length, s[~small], acc.n_fourier)
    return out


def theta_inf(case: Case, src: Source, targets: list[Target], acc: Acc) -> np.ndarray:
    """Infinite-depth surface excess of one source at the targets, without its (0,0) mode [K]."""
    s, w, s_lo = _s_nodes(case, acc)
    s_all = np.concatenate([[s_lo], s])
    w_all = np.concatenate([[s_lo], w])  # [0, s_lo] by the rectangle rule f(s_lo) s_lo
    x1 = np.array([t.x1 for t in targets])
    x2 = np.array([t.x2 for t in targets])
    y1 = np.array([t.y1 for t in targets])
    y2 = np.array([t.y2 for t in targets])
    pat = np.array([t.kind == "patch" for t in targets])
    fx = heat1d(x1, x2, pat, src.x1, src.x2, case.a, s_all, acc)
    fy = heat1d(y1, y2, pat, src.y1, src.y2, case.b, s_all, acc)
    a0 = src.c / case.a
    b0 = src.d / case.b
    integrand = fx * fy + a0 * fy + b0 * fx  # = Fx Fy - a0 b0 with Fx - a0 = fx, Fy - b0 = fy
    return (src.q / case.k_top) * (2.0 / SQRT_PI) * (integrand @ w_all)


# ----------------------------------------------------------------------------------------------------------------------
# Remainder part (exponentially convergent double cosine series) and the assembled field
# ----------------------------------------------------------------------------------------------------------------------
class Field:
    """Converged surface temperature of a case: T = Tf + sum_i [Q_i R1D/(ab) + theta_inf,i + theta_R,i]."""

    def __init__(self, case: Case, acc: Acc | None = None):
        self.case = case
        self.acc = acc or Acc()
        mx, my = mode_counts(case, self.acc)
        self.lam = np.arange(mx + 1, dtype=float) * math.pi / case.a
        self.dlt = np.arange(my + 1, dtype=float) * math.pi / case.b
        beta = np.sqrt(self.lam[:, None] ** 2 + self.dlt[None, :] ** 2)
        beta[0, 0] = 1.0
        W = mode_excess(case, beta) / (case.k_top * beta)  # R(beta) = E / (k_top beta)
        W[0, 0] = 0.0
        self.W = W
        self.coef = []  # per source: (q a_m, b_n)
        for src in case.sources:
            self.coef.append((src.q * _src_coeff(self.lam, case.a, src.x1, src.x2),
                              _src_coeff(self.dlt, case.b, src.y1, src.y2)))
        # combined matrix G_mn = W_mn sum_i q_i a_m^i b_n^i, for fast evaluation of the total field at many points
        C = sum(np.outer(qa, bb) for qa, bb in self.coef)
        self.G = self.W * C

    def _factors(self, targets: list[Target]):
        x1 = np.array([t.x1 for t in targets])
        x2 = np.array([t.x2 for t in targets])
        y1 = np.array([t.y1 for t in targets])
        y2 = np.array([t.y2 for t in targets])
        pat = np.array([t.kind == "patch" for t in targets])
        return _cos_factor(self.lam, x1, x2, pat), _cos_factor(self.dlt, y1, y2, pat)

    def rise(self, targets: list[Target], sources: list[int] | None = None, chunk: int = 256) -> np.ndarray:
        """T - Tf [K] at the targets, from all sources or from the listed source indices."""
        case = self.case
        idx = list(range(len(case.sources))) if sources is None else list(sources)
        out = np.zeros(len(targets))
        for i in idx:
            src = case.sources[i]
            out += src.Q * case.r1d_area / (case.a * case.b)
            out += theta_inf(case, src, targets, self.acc)
        if sources is None:
            G = self.G
        else:
            G = self.W * sum(np.outer(self.coef[i][0], self.coef[i][1]) for i in idx)
        for k0 in range(0, len(targets), chunk):
            cx, cy = self._factors(targets[k0:k0 + chunk])
            out[k0:k0 + chunk] += np.einsum("pm,pm->p", cx, cy @ G.T)
        return out

    def T(self, targets: list[Target], sources=None) -> np.ndarray:
        return self.case.Tf + self.rise(targets, sources)

    def T_point(self, x: float, y: float) -> float:
        return float(self.T([Target.point(x, y)])[0])


# ----------------------------------------------------------------------------------------------------------------------
# Paper reproduction: [M03] partial sums truncated at m, n = 1..N (N = 50 in the paper), coded from eqs. (20)-(27)/(41)
# independently of the accelerated path above.
# ----------------------------------------------------------------------------------------------------------------------
def m03_phi(case: Case, z):
    td = case.top_down
    if len(td) == 1:
        return phi_single(z, td[0][1], td[0][2], case.h)
    return phi_compound(z, td[0][1], td[0][2], td[1][1], td[1][2], case.h)


def m03_truncated(case: Case, targets: list[Target], n_terms: int = 50) -> np.ndarray:
    """T [K] from [M03] eqs. (16), (20), (22), (24), (25), (27), (37), (41) with m, n = 1..n_terms."""
    a, b, k1 = case.a, case.b, case.k_top
    m = np.arange(1, n_terms + 1, dtype=float)
    lam = m * math.pi / a
    dl = m * math.pi / b
    bet = np.sqrt(lam[:, None] ** 2 + dl[None, :] ** 2)
    phl, phd, phb = m03_phi(case, lam), m03_phi(case, dl), m03_phi(case, bet)
    out = np.full(len(targets), case.Tf)
    for src in case.sources:
        Q, Xc, Yc, c, d = src.Q, src.xc, src.yc, src.c, src.d
        A0 = Q / (a * b) * case.r1d_area  # eq. (25)/(28)/(31)
        Am = 2 * Q * (np.sin((2 * Xc + c) / 2 * lam) - np.sin((2 * Xc - c) / 2 * lam)) / (a * b * c * k1 * lam ** 2
                                                                                         * phl)  # eq. (20)
        An = 2 * Q * (np.sin((2 * Yc + d) / 2 * dl) - np.sin((2 * Yc - d) / 2 * dl)) / (a * b * d * k1 * dl ** 2
                                                                                        * phd)  # eq. (22)
        Amn = (16 * Q * np.outer(np.cos(lam * Xc) * np.sin(lam * c / 2), np.cos(dl * Yc) * np.sin(dl * d / 2))
               / (a * b * c * d * k1 * bet * np.outer(lam, dl) * phb))  # eq. (24)
        for p, t in enumerate(targets):
            if t.kind == "point":  # eq. (16) at z = 0
                fx, fy = np.cos(lam * t.x1), np.cos(dl * t.y1)
                out[p] += A0 + Am @ fx + An @ fy + fx @ Amn @ fy
            else:  # eq. (27)/(41): mean over patch j of centroid (Xcj, Ycj), size cj x dj
                cj, dj = t.x2 - t.x1, t.y2 - t.y1
                xcj, ycj = 0.5 * (t.x1 + t.x2), 0.5 * (t.y1 + t.y2)
                gx = np.cos(lam * xcj) * np.sin(lam * cj / 2) / (lam * cj)
                gy = np.cos(dl * ycj) * np.sin(dl * dj / 2) / (dl * dj)
                out[p] += A0 + 2 * Am @ gx + 2 * An @ gy + 4 * gx @ Amn @ gy
    return out


# Printed values of [M03] (degrees C): Case 1a Table 1, Case 1b Table 2, Case 2 Table 4, Case 3 text.
PRINTED_C = {
    ("case1a", "s1", "centroid"): 84.97, ("case1a", "s1", "mean"): 80.56,
    ("case1a", "s2", "centroid"): 108.43, ("case1a", "s2", "mean"): 101.81,
    ("case1b", "s1", "centroid"): 56.55, ("case1b", "s1", "mean"): 56.05,
    ("case1b", "s2", "centroid"): 59.94, ("case1b", "s2", "mean"): 59.19,
    ("case2", "s1", "centroid"): 97.40, ("case2", "s1", "mean"): 96.85,
    ("case2", "s2", "centroid"): 103.82, ("case2", "s2", "mean"): 102.33,
    ("case2", "s3", "centroid"): 101.28, ("case2", "s3", "mean"): 100.10,
    ("case2", "s4", "centroid"): 99.94, ("case2", "s4", "mean"): 99.07,
    ("case3", "centre", "centroid"): 80.61, ("case3", "cross", "mean"): 78.87,
}
PRINTED_TB_C = {"case1a": 53.06, "case1b": 53.06}  # mean base temperature T_b, Tables 1-2
# Gated: exactly O006 F1's printed Case 3 values. Every other printed value (incl. Case 1a/1b centroids) is INFO: no
# single 50-term cut-off reproduces Tables 1-2 (T0151 attempt 2; note section 5.3).
GATED_PRINTED = (("case3", "centre", "centroid"), ("case3", "cross", "mean"))


def m03_printed_targets(case: Case, src_name: str, kind: str) -> list[Target]:
    if src_name == "cross":
        return [Target.patch(s) for s in case.sources]  # equal areas: the area-weighted mean is the plain mean
    src = next(s for s in case.sources if s.name == src_name)
    return [Target.point(src.xc, src.yc)] if kind == "centroid" else [Target.patch(src)]


def m03_value_c(case: Case, src_name: str, kind: str, n_terms: int | None) -> float:
    """[M03] quantity in degrees C: truncated at n_terms (paper: 50) or, for None, the converged (accelerated) value."""
    tg = m03_printed_targets(case, src_name, kind)
    vals = m03_truncated(case, tg, n_terms) if n_terms is not None else Field(case).T(tg)
    return float(k_to_c(np.mean(vals)))


# ----------------------------------------------------------------------------------------------------------------------
# Reported values per source: centroid, mean, maximum over the source (and its location)
# ----------------------------------------------------------------------------------------------------------------------
def maximize_on_source(fld: Field, src: Source, n_grid: int = 21, start: tuple[float, float] | None = None):
    """Maximum of T over the closed source rectangle: grid scan, then bounded L-BFGS-B from the best three grid
    points (or only from ``start``, then grid_max is T at ``start``). Returns (x, y, T, grid_max)."""
    if start is None:
        xs = np.linspace(src.x1, src.x2, n_grid)
        ys = np.linspace(src.y1, src.y2, n_grid)
        X, Y = np.meshgrid(xs, ys, indexing="ij")
        pts = [Target.point(x, y) for x, y in zip(X.ravel(), Y.ravel(), strict=True)]
        Tg = fld.T(pts)
        grid_max = float(Tg.max())
        order = np.argsort(-Tg)
        starts = [(X.ravel()[i], Y.ravel()[i]) for i in order[:3]]
    else:  # re-optimisation from a known maximiser (convergence checks): no grid scan
        starts = [start]
        grid_max = fld.T_point(*start)
    scale = max(grid_max - fld.case.Tf, 1e-30)

    def f(v):
        x = src.x1 + v[0] * src.c
        y = src.y1 + v[1] * src.d
        return -(fld.T_point(x, y) - fld.case.Tf) / scale

    best = None
    for x0, y0 in starts:
        v0 = np.array([(x0 - src.x1) / src.c, (y0 - src.y1) / src.d])
        r = minimize(f, v0, method="L-BFGS-B", bounds=[(0.0, 1.0), (0.0, 1.0)],
                     options={"ftol": 1e-16, "gtol": 1e-13, "eps": 1e-8, "maxiter": 400})
        val = -r.fun
        if best is None or val > best[0]:
            best = (val, r.x)
    v = best[1]
    x, y = src.x1 + v[0] * src.c, src.y1 + v[1] * src.d
    Tm = fld.T_point(x, y)
    return x, y, Tm, grid_max


def reference_values(case: Case, acc: Acc | None = None, max_starts: dict | None = None) -> dict:
    """All reported values of a case: rows (source, point type, x, y, T [K]) plus the case scale."""
    fld = Field(case, acc)
    rows = []
    for src in case.sources:
        Tc = float(fld.T([Target.point(src.xc, src.yc)])[0])
        Tmean = float(fld.T([Target.patch(src)])[0])
        st = None if max_starts is None else max_starts[src.name]
        xm, ym, Tmax, gmax = maximize_on_source(fld, src, start=st)
        rows.append({"source": src.name, "point": "centroid", "x": src.xc, "y": src.yc, "T": Tc})
        rows.append({"source": src.name, "point": "mean", "x": src.xc, "y": src.yc, "T": Tmean})
        rows.append({"source": src.name, "point": "max", "x": xm, "y": ym, "T": Tmax, "grid_max": gmax})
    spread = {r["source"]: r["T"] - case.T_1d for r in rows if r["point"] == "max"}
    scale_src = max(spread, key=spread.get)
    return {"case": case.name, "rows": rows, "T_1d": case.T_1d, "scale": spread[scale_src],
            "scale_source": scale_src, "spreading_rise_at_max": spread, "modes": mode_counts(case, fld.acc)}


# ----------------------------------------------------------------------------------------------------------------------
# F1 self-checks
# ----------------------------------------------------------------------------------------------------------------------
class Checks:
    def __init__(self):
        self.items = []

    def add(self, name: str, ok: bool, detail: str, gate: bool = True):
        self.items.append((name, bool(ok), detail, gate))
        tag = ("PASS" if ok else "FAIL") if gate else "INFO"
        print(f"[{tag}] {name}: {detail}", flush=True)

    @property
    def failed(self) -> list[str]:
        return [n for n, ok, _, g in self.items if g and not ok]


def check_kernels(ck: Checks):
    """Mode kernels: eq. (30) at kappa = 1 equals eq. (18); recursion equals eq. (30) for two layers and the explicit
    linear system for the 7-layer stack; recursion with layers sharing k equals eq. (30)."""
    betas = np.geomspace(1.0, 3e5, 400)
    h = 5000.0
    # (a) eq. (30) with k2 = k1 reduces to eq. (18) of the total thickness
    e30 = excess_compound(betas, 1e-3, 100.0, 4e-3, 100.0, h)
    e18 = excess_single(betas, 5e-3, 100.0, h)
    err = float(np.max(np.abs((1 + e30) / (1 + e18) - 1)))
    ck.add("kernel_eq30_kappa1_equals_eq18", err <= 1e-12, f"max rel diff of 1/phi = {err:.2e} (<= 1e-12)")
    # (b) N-layer recursion vs eq. (30) on two layers, several conductivity ratios
    worst = 0.0
    for (t1, k1, t2, k2, hh) in ((2e-3, 350.0, 10e-3, 10.0, 10.0), (0.53e-3, 370.0, 3.78e-3, 24.0, 5000.0),
                                 (1e-3, 10.0, 5e-3, 400.0, 1e4)):
        en = excess_nlayer(betas, (("l1", t1, k1), ("l2", t2, k2)), hh)
        ec = excess_compound(betas, t1, k1, t2, k2, hh)
        worst = max(worst, float(np.max(np.abs((1 + en) / (1 + ec) - 1))))
    ck.add("kernel_recursion_equals_eq30", worst <= 1e-12, f"max rel diff of Z = {worst:.2e} (<= 1e-12)")
    # (c) recursion vs explicit 2N x 2N boundary-value system, 7-layer default stack
    td = tuple(reversed(nlayer_layers()))
    worst = 0.0
    for bt in np.geomspace(1.0, 2e4, 60):
        zr = (1.0 + float(excess_nlayer(np.array([bt]), td, h)[0])) / (td[0][2] * bt)
        zl = z_nlayer_linear_system(float(bt), td, h)
        worst = max(worst, abs(zr / zl - 1))
    ck.add("kernel_recursion_equals_linear_system", worst <= 1e-10,
           f"7-layer stack, beta 1..2e4 1/m: max rel diff {worst:.2e} (<= 1e-10)")
    # (d) beta -> 0 limit: Z -> R1D (sum t/k + 1/h)
    r1d = sum(t / k for _, t, k in td) + 1 / h
    bt = 1e-6
    z0 = (1.0 + float(excess_nlayer(np.array([bt]), td, h)[0])) / (td[0][2] * bt)
    ck.add("kernel_beta0_limit_is_R1D", abs(z0 / r1d - 1) <= 1e-6, f"Z(1e-6)/R1D - 1 = {z0 / r1d - 1:.2e} (<= 1e-6)")


def check_poisson(ck: Checks):
    """Images and cosine series of the 1D heat kernel agree (Poisson summation) around the switch point."""
    rng = np.random.default_rng(20261101)
    L, lo, hi = 0.05, 0.012, 0.021
    p = rng.uniform(0, L, 40)
    p2 = np.minimum(p + rng.uniform(0, 0.01, 40), L)
    pat = np.arange(40) % 2 == 1
    p1 = p.copy()
    p2 = np.where(pat, p2, p1)
    s = np.array([0.1, 0.25, 0.4]) * L
    fi = heat1d_images(p1, p2, pat, lo, hi, L, s, 12)
    ff = heat1d_fourier(p1, p2, pat, lo, hi, L, s, 200)
    err = float(np.max(np.abs(fi - ff)))
    ck.add("heat_kernel_images_equal_fourier", err <= 1e-13, f"max |images - cosine series| = {err:.2e} (<= 1e-13)")


def check_full_top(ck: Checks):
    """A source covering the whole top face gives T = Tf + Q R1D/(ab) everywhere ([M03] eq. (28)/(31); 1D series)."""
    worst = 0.0
    for case in all_cases():
        src = Source("full", case.a / 2, case.b / 2, case.a, case.b, 100.0)
        c2 = replace(case, sources=(src,))
        fld = Field(c2)
        tg = [Target.point(0.0, 0.0), Target.point(case.a / 2, case.b / 2), Target.point(0.3 * case.a, 0.9 * case.b),
              Target.point(case.a, 0.17 * case.b), Target.patch(Source("p", 0.4 * case.a, 0.3 * case.b,
                                                                       0.1 * case.a, 0.2 * case.b, 0.0))]
        r = fld.rise(tg)
        ref = 100.0 * case.r1d_area / (case.a * case.b)
        worst = max(worst, float(np.max(np.abs(r / ref - 1))))
    ck.add("full_top_source_equals_1D", worst <= 1e-9, f"max rel diff over 5 stacks x 5 targets = {worst:.2e} (<= 1e-9)")


def check_face_mean(ck: Checks):
    """The mean of the surface field over the whole top face equals the 1D temperature T_1d (all non-zero modes and
    the infinite-depth part integrate to zero)."""
    worst = 0.0
    for case in all_cases():
        fld = Field(case)
        face = Target("patch", 0.0, case.a, 0.0, case.b)
        r = float(fld.rise([face])[0])
        worst = max(worst, abs(r / (case.T_1d - case.Tf) - 1))
    ck.add("face_mean_equals_T1d", worst <= 1e-9, f"max rel diff = {worst:.2e} (<= 1e-9)")


def check_reciprocity(ck: Checks):
    """Green reciprocity of uniform-flux patches: mean rise of patch j per watt in source i = that of i per watt in j."""
    worst = 0.0
    for case in (case_1b(), case_2(), case_nlayer()):
        fld = Field(case)
        n = len(case.sources)
        R = np.zeros((n, n))
        for i in range(n):
            tg = [Target.patch(s) for s in case.sources]
            R[:, i] = fld.rise(tg, sources=[i]) / case.sources[i].Q
        worst = max(worst, float(np.max(np.abs(R - R.T) / np.abs(R))))
    ck.add("reciprocity_mean_rise", worst <= 1e-9, f"max |R_ij - R_ji|/R_ij = {worst:.2e} (<= 1e-9)")


def check_acceleration_consistency(ck: Checks):
    """The accelerated value is the limit of the raw partial sums: error of the [M03] truncated series at N = 100, 200,
    400, 800 decreases and is below 1e-4 of the rise at N = 800 (Case 1b and Case 2 centroids and means, Case 3
    centre; single-layer and compound kernels)."""
    worst_last = 0.0
    monotone = True
    lines = []
    for case, names in ((case_1b(), ("s1", "s2")), (case_2(), ("s1", "s2", "s3", "s4")), (case_3(), ("centre",))):
        fld = Field(case)
        for nm in names:
            for kind in ("centroid", "mean"):
                tg = m03_printed_targets(case, nm, kind)
                ref = float(fld.T(tg)[0])
                rise = ref - case.Tf
                errs = [abs(float(m03_truncated(case, tg, n)[0]) - ref) / rise for n in (100, 200, 400, 800)]
                monotone &= all(e2 < e1 for e1, e2 in zip(errs, errs[1:], strict=False)) or errs[-1] < 1e-10
                worst_last = max(worst_last, errs[-1])
                lines.append(f"{case.name}/{nm}/{kind}: " + ",".join(f"{e:.1e}" for e in errs))
    ck.add("raw_partial_sums_converge_to_accelerated", monotone and worst_last <= 1e-4,
           f"rel err at N=100,200,400,800: {'; '.join(lines)}; worst at N=800 {worst_last:.1e} (<= 1e-4, decreasing)")


def check_paper(ck: Checks):
    """[M03] truncated at the paper's 50 terms reproduces the printed values to their printed digits (gated: only F1's
    Case 3 centre maximum and source mean); every other printed value and the converged values are reported (INFO)."""
    cases = {c.name: c for c in (case_1a(), case_1b(), case_2(), case_3())}
    for key, printed in PRINTED_C.items():
        cname, sname, kind = key
        v50 = m03_value_c(cases[cname], sname, kind, 50)
        vinf = m03_value_c(cases[cname], sname, kind, None)
        ok = abs(v50 - printed) <= 0.005 + 1e-9
        gate = key in GATED_PRINTED
        ck.add(f"paper50_{cname}_{sname}_{kind}", ok,
               f"50 terms {v50:.4f} C vs printed {printed:.2f} C (|d| <= 0.005); converged {vinf:.4f} C "
               f"(converged - printed {vinf - printed:+.4f} K)", gate=gate)
    for cname, tb in PRINTED_TB_C.items():
        v = k_to_c(cases[cname].T_1d)
        ck.add(f"paper_Tb_{cname}", abs(v - tb) <= 0.005 + 1e-9, f"T_1d {v:.4f} C vs printed T_b {tb:.2f} C")


def check_nlayer_equals_two_layer(ck: Checks, acc: Acc):
    """N-layer series with layers sharing two conductivities equals the [M03] eq. (30) two-layer series (rel 1e-9 of
    the rise), at every reported point type (centroid, mean, max location of the two-layer field)."""
    worst = 0.0
    details = []
    c1b = case_1b()
    split_1b = (("plate_a", _mm(3.0), 10.0), ("plate_b", _mm(3.0), 10.0), ("plate_c", _mm(4.0), 10.0),
                ("spr_a", _mm(0.8), 350.0), ("spr_b", _mm(1.2), 350.0))
    nl = nlayer_layers()  # 7 layers; top three (top_cu, die_attach, die) -> k = 370, bottom four -> k = 24
    t_top3 = sum(t for _, t, _ in nl[4:])
    t_bot4 = sum(t for _, t, _ in nl[:4])
    cn = case_nlayer()
    two_n = replace(cn, name="nl_two", kernel="M03", layers=(("bottom", t_bot4, 24.0), ("top", t_top3, 370.0)))
    split_n = replace(cn, name="nl_split", kernel="nlayer",
                      layers=tuple((nm, t, 24.0) for nm, t, _ in nl[:4]) + tuple((nm, t, 370.0) for nm, t, _ in nl[4:]))
    for two, nlay in ((c1b, replace(c1b, name="case1b_split", kernel="nlayer", layers=split_1b)), (two_n, split_n)):
        f2 = Field(two, acc)
        fn = Field(nlay, acc)
        tg = []
        for src in two.sources:
            x, y, _, _ = maximize_on_source(f2, src, n_grid=11)
            tg += [Target.point(src.xc, src.yc), Target.patch(src), Target.point(x, y)]
        r2 = f2.rise(tg)
        rn = fn.rise(tg)
        e = float(np.max(np.abs(rn / r2 - 1)))
        worst = max(worst, e)
        details.append(f"{nlay.name}: {e:.1e}")
    ck.add("nlayer_equals_two_layer", worst <= 1e-9, f"max rel diff {'; '.join(details)} (<= 1e-9)")


def check_convergence(ck: Checks, refs: dict, acc: Acc) -> dict:
    """Doubling every terms knob (remainder modes, s-quadrature panels and range, images and heat-kernel cosine
    terms), separately and together, changes every reported value by < 1e-7 relative to its rise above Tf."""
    out = {}
    for case in all_cases():
        ref = refs[case.name]
        worst_case = 0.0
        for what in ("modes", "quad", "images", "all"):
            acc2 = acc.doubled(what)
            fld2 = Field(case, acc2)
            worst = 0.0
            for r in ref["rows"]:
                src = next(s for s in case.sources if s.name == r["source"])
                if r["point"] == "centroid":
                    v = fld2.T_point(r["x"], r["y"])
                elif r["point"] == "mean":
                    v = float(fld2.T([Target.patch(src)])[0])
                else:
                    _, _, v, _ = maximize_on_source(fld2, src, start=(r["x"], r["y"]))
                worst = max(worst, abs(v - r["T"]) / (r["T"] - case.Tf))
            worst_case = max(worst_case, worst)
            out[(case.name, what)] = worst
        ck.add(f"convergence_doubling_{case.name}", worst_case < 1e-7,
               "max rel change " + ", ".join(f"{w}={out[(case.name, w)]:.1e}" for w in ("modes", "quad", "images",
                                                                                        "all")) + " (< 1e-7)")
    return out


def check_reference_sanity(ck: Checks, refs: dict):
    """Max >= grid samples and >= centroid and mean; Case 3 symmetric with the maximum at the centre; N-layer max
    rises inside the 60-110 K design band; every case scale positive."""
    bad = []
    for name, ref in refs.items():
        by = {}
        for r in ref["rows"]:
            by.setdefault(r["source"], {})[r["point"]] = r
        for s, d in by.items():
            tm = d["max"]["T"]
            if tm < d["max"]["grid_max"] - 1e-12 * abs(tm) or tm < d["centroid"]["T"] or tm < d["mean"]["T"]:
                bad.append(f"{name}/{s}")
        if ref["scale"] <= 0:
            bad.append(f"{name}/scale")
    ck.add("max_dominates_samples_and_scale_positive", not bad, f"violations: {bad or 'none'}")
    c3 = {r["source"] + "/" + r["point"]: r for r in refs["case3"]["rows"]}
    arms = [c3[f"{a}/mean"]["T"] for a in ("west", "east", "south", "north")]
    sym = (max(arms) - min(arms)) / (arms[0] - c_to_k(25.0))
    loc = math.hypot(c3["centre/max"]["x"] - _mm(50.0), c3["centre/max"]["y"] - _mm(50.0))
    ck.add("case3_symmetry_and_centre_max", sym <= 1e-10 and loc <= 1e-7,
           f"arm means spread rel {sym:.1e} (<= 1e-10); centre max at {loc:.1e} m from (50, 50) mm (<= 1e-7 m)")
    cn = case_nlayer()
    rises = [r["T"] - cn.Tf for r in refs["nlayer_dbc"]["rows"] if r["point"] == "max"]
    ck.add("nlayer_rises_in_O002_band", all(60.0 <= x <= 110.0 for x in rises),
           "max rises above coolant " + ", ".join(f"{x:.2f}" for x in rises) + " K (60-110 K)")


# ----------------------------------------------------------------------------------------------------------------------
# Emission
# ----------------------------------------------------------------------------------------------------------------------
def build_payload(refs: dict, acc: Acc) -> dict:
    cases = {c.name: c for c in all_cases()}
    rows = []
    scales = {}
    for name, ref in refs.items():
        case = cases[name]
        for r in ref["rows"]:
            rows.append({"case": name, "source": r["source"], "point": r["point"], "x_m": r["x"], "y_m": r["y"],
                         "T_K": r["T"], "rise_K": r["T"] - case.Tf})
        scales[name] = {"scale_K": ref["scale"], "scale_source": ref["scale_source"], "T_1d_K": ref["T_1d"],
                        "Tf_K": case.Tf, "h_W_m2K": case.h, "a_m": case.a, "b_m": case.b,
                        "layers_bottom_up": [{"name": n, "t_m": t, "k_W_mK": k} for n, t, k in case.layers],
                        "sources": [{"name": s.name, "xc_m": s.xc, "yc_m": s.yc, "c_m": s.c, "d_m": s.d, "Q_W": s.Q}
                                    for s in case.sources],
                        "spreading_rise_at_max_K": ref["spreading_rise_at_max"], "remainder_modes": ref["modes"],
                        "note": case.note}
    return {"schema": "e006_series_values/1", "units": "SI; temperatures in K; x, y from the plate's lower-left corner",
            "generator": "experiments/runners/e006_series.py", "accuracy": acc.__dict__, "cases": scales,
            "rows": rows}


def canonical_sha256(payload: dict) -> str:
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return hashlib.sha256(blob).hexdigest()


def compute_refs(acc: Acc) -> dict:
    refs = {}
    for case in all_cases():
        t0 = time.time()
        refs[case.name] = reference_values(case, acc)
        print(f"  {case.name}: scale {refs[case.name]['scale']:.4f} K ({refs[case.name]['scale_source']}), "
              f"modes {refs[case.name]['modes']}, {time.time() - t0:.1f} s", flush=True)
    return refs


def print_table(refs: dict):
    cases = {c.name: c for c in all_cases()}
    for name, ref in refs.items():
        case = cases[name]
        print(f"{name}: Tf = {k_to_c(case.Tf):.2f} C, T_1d = {k_to_c(ref['T_1d']):.6f} C, scale = {ref['scale']:.6f} K")
        for r in ref["rows"]:
            print(f"  {r['source']:7s} {r['point']:8s} x={m_to_mm(r['x']):9.4f} mm y={m_to_mm(r['y']):9.4f} mm "
                  f"T={k_to_c(r['T']):.7f} C rise={r['T'] - case.Tf:.7f} K")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--selfcheck", action="store_true", help="run F1's gates; exit 1 on any failure")
    ap.add_argument("--emit", metavar="PATH", help="write every reference value with its sha256 to PATH (JSON)")
    args = ap.parse_args(argv)
    if not (args.selfcheck or args.emit):
        ap.error("give --selfcheck and/or --emit PATH")
    acc = Acc()
    t0 = time.time()
    print("computing reference values ...", flush=True)
    refs = compute_refs(acc)
    print_table(refs)
    rc = 0
    if args.selfcheck:
        ck = Checks()
        check_kernels(ck)
        check_poisson(ck)
        check_full_top(ck)
        check_face_mean(ck)
        check_reciprocity(ck)
        check_paper(ck)
        check_acceleration_consistency(ck)
        check_nlayer_equals_two_layer(ck, acc)
        check_reference_sanity(ck, refs)
        check_convergence(ck, refs, acc)
        n_gate = sum(1 for *_, g in ck.items if g)
        print(f"selfcheck: {n_gate - len(ck.failed)}/{n_gate} gates passed; failed: {ck.failed or 'none'}; "
              f"{time.time() - t0:.0f} s", flush=True)
        rc = 1 if ck.failed else 0
    if args.emit:
        payload = build_payload(refs, acc)
        digest = canonical_sha256(payload)
        doc = {"sha256": digest, "sha256_of": "canonical JSON (sorted keys, compact) of 'payload'", "payload": payload}
        with open(args.emit, "w") as fh:
            json.dump(doc, fh, indent=1, sort_keys=True)
            fh.write("\n")
        print(f"wrote {args.emit} sha256(payload) = {digest}", flush=True)
    return rc


if __name__ == "__main__":
    sys.exit(main())
