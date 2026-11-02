"""Closed-form (Fourier-series) reference for the laterally uniform N-layer box stack (docs/thermal_model.md section 6).

Problem: rectangle ``[0,a]x[0,b]``, bottom-up layers ``(t_j, k_j)`` (constant k), adiabatic side walls, convective bottom
``k dT/dz = h (T - T_c)`` at z = 0, adiabatic top except under uniform-flux rectangular sources ``[x0,x1]x[y0,y1]``
with power ``P`` (flux ``q = P / area`` into the stack).  Separation of variables with ``cos(m pi x / a) cos(n pi y / b)``
modes (Carslaw & Jaeger, *Conduction of Heat in Solids*, 2nd ed., 1959, Sec. 3.6; Muzychka, Culham & Yovanovich,
J. Electron. Packag. 125(2):178-185, 2003, for the one- and two-layer case) and a per-mode layer transfer matrix on the
state ``(theta, k theta')``: for a layer of thickness ``t`` and ``lam^2 = (m pi/a)^2 + (n pi/b)^2``

    [theta; k theta']_top = [[cosh(lam t), sinh(lam t)/(k lam)], [k lam sinh(lam t), cosh(lam t)]] [theta; k theta']_bottom,

(``[[1, t/k], [0, 1]]`` for ``lam = 0``).  The bottom state is ``(1, h)`` (up to a factor); the top condition
``k theta' = F_mn`` (Fourier coefficient of the flux) fixes the factor.  Every matrix entry is positive, so the
ratio ``theta_top / F`` is free of cancellation; each layer matrix is divided by ``exp(lam t)`` (a common factor that
cancels in the ratio) to avoid overflow at large ``lam``.

Surface values (``mean`` over a rectangle, point value) are sums over ``m, n <= n_modes``; the tail decays like
``1/n_modes`` for point values and faster for means, so ``n_modes`` of a few hundred gives ~1e-4 K for the cases used here
(check by doubling ``n_modes``).
"""
from __future__ import annotations

import numpy as np


def _mode_gain(a: float, b: float, layers, h: float, n_modes: int):
    """(lam_x[m], lam_y[n], G[m,n]) with G = theta_top / F for unit Fourier flux coefficient."""
    m = np.arange(n_modes)
    ax, by = m * np.pi / a, m * np.pi / b
    lam = np.hypot(ax[:, None], by[None, :])
    # state (theta, k theta') = c * (1, h): accumulate L_N ... L_1 applied to (1, h)
    s1 = np.ones_like(lam)
    s2 = np.full_like(lam, float(h))
    for t, k in layers:
        x = lam * t
        e = np.exp(-2.0 * x)
        ch, sh = 0.5 * (1.0 + e), 0.5 * (1.0 - e)  # cosh, sinh divided by exp(x)
        with np.errstate(divide="ignore", invalid="ignore"):
            r12 = np.where(lam > 0, sh / (k * lam), t / k * np.exp(-x))
        r21 = k * lam * sh
        s1, s2 = ch * s1 + r12 * s2, r21 * s1 + ch * s2
        # keep the state O(1): the common scale cancels in s1 / s2
        sc = np.maximum(np.abs(s1), np.abs(s2))
        s1, s2 = s1 / sc, s2 / sc
    return ax, by, s1 / s2


def _cos_integrals(freq: np.ndarray, lo: float, hi: float) -> np.ndarray:
    """``int_lo^hi cos(freq x) dx`` (``hi - lo`` for freq = 0)."""
    out = np.full(freq.shape, hi - lo, dtype=float)
    nz = freq > 0
    out[nz] = (np.sin(freq[nz] * hi) - np.sin(freq[nz] * lo)) / freq[nz]
    return out


def _coeff(a, b, src, n_modes):
    """Fourier coefficients ``F[m,n]`` of the unit-power source (flux 1/area on the rectangle)."""
    x0, x1, y0, y1 = src
    m = np.arange(n_modes)
    ax, by = m * np.pi / a, m * np.pi / b
    ex = np.where(m == 0, 1.0, 2.0) / a
    ey = np.where(m == 0, 1.0, 2.0) / b
    ix, iy = _cos_integrals(ax, x0, x1), _cos_integrals(by, y0, y1)
    return (ex * ix)[:, None] * (ey * iy)[None, :] / ((x1 - x0) * (y1 - y0))


def box_series(a, b, layers, sources, *, h, T_c, n_modes: int = 400) -> dict:
    """Reference ``tj_mean`` / ``tj_centroid`` of every source rectangle, absolute K, summed over all sources.

    ``layers`` = [(t, k), ...] bottom-up, ``sources`` = [(x0, x1, y0, y1, P_W), ...].  Returns
    ``{'src{i}.tj_mean': ..., 'src{i}.tj_centroid': ...}`` (same keys as ``thermal_layout.solve_box_level``)."""
    ax, by, G = _mode_gain(a, b, layers, h, n_modes)
    F = sum(_coeff(a, b, s[:4], n_modes) * s[4] for s in sources)
    th = F * G  # surface-temperature coefficient of cos cos (rise over T_c)
    out = {}
    for i, (x0, x1, y0, y1, _P) in enumerate(sources):
        mx = _cos_integrals(ax, x0, x1) / (x1 - x0)
        my = _cos_integrals(by, y0, y1) / (y1 - y0)
        out[f"src{i}.tj_mean"] = T_c + float(mx @ th @ my)
        cx, cy = 0.5 * (x0 + x1), 0.5 * (y0 + y1)
        out[f"src{i}.tj_centroid"] = T_c + float(np.cos(ax * cx) @ th @ np.cos(by * cy))
    return out


__all__ = ["box_series"]
