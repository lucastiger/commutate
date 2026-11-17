"""L1 thermal model: coarse conforming finite-volume solve of the full layout problem with a frozen per-die-size
calibration of the die-local rise (design ``fv_coarse_xcal`` of research/notes/o002-l1-design.md, T0392).

Steady state, uniform ``h`` at the baseplate bottom, uniform flux over each die's top face, temperature-dependent
conductivity (``geometry.stack.K_LAWS`` through ``Layer.k_at``) by Picard iteration.  SI units, float64.  Method,
citations and limits: docs/thermal_l1.md.  Frozen as E007's code_under_test (F5): do not change the numbers below
without a new registration.

    T_L1,i = T_bp + c(s) (T_FV,i - T_bp),   T_bp = T_c + sum(P) / (h A_bottom)

``T_bp`` (mean baseplate-bottom temperature) is exact by the energy balance for uniform ``h`` (a global heat balance:
all power leaves through the bottom face).  ``c(s)`` is the frozen table ``CALIBRATION`` (die size s in mm).

Closed forms and methods used: face conductance as the series of two half-cells (harmonic mean; Patankar, *Numerical
Heat Transfer and Fluid Flow*, 1980, Sec. 4.2.3, Eq. 4.9) in ``solvers.thermal_fv``; lagged-k (Picard) iteration for
k(T) (a Kirchhoff transform, Carslaw & Jaeger, *Conduction of Heat in Solids*, 2nd ed., 1959, Sec. 1.7, linearises only a
single-material body and is not used); ``T_bp`` from the global energy balance (all heat leaves through ``h``).
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

import numpy as np

from moduleforge.geometry.layout import Layout
from moduleforge.solvers import thermal_layout as _TL
from moduleforge.solvers.thermal_fv import solve_steady

# Frozen coarse grid rule: level 0 of the layout rule of solvers.thermal_layout with explicit constants (no global state).
# n1's rule (T0392 section 4) had the lateral bulk cap h0_max = 4 mm; T0395 lowered it to 1.5 mm by the decision rule written
# in benchmarks/thermal_l1_calibration.py before scoring: on a fresh development seed (20261395, three 2-die strata) the
# spread (A4-type) ratio fell from 0.69 to 0.21 at a median 0.39 s per evaluation (docs/thermal_l1.md).
GRID_RULE = {"h0_max": 1.5e-3, "lat_frac": 16.0, "edge_frac": 2.0, "z_cells": 2}
PICARD_TOL_K = 1e-2  # K, lagged-k Picard tolerance (about 4 iterations)

CALIBRATION_VERSION = "o002-l1-cal-v2"
# c(s), s = die size [mm], one entry per generator die size (halfbridge.draw_die_size_mm: 4.0, 4.5, 5.0, 5.5 mm).  Each is
# the mean over C004's two development strata (side_by_side/6, u_shaped/2; dev seed 20261101 with the die size fixed to s)
# of the mean over dies of (level-1 reference rise) / (coarse-FV rise on GRID_RULE) at the layout's P_ref (C004's rule).
# Derivation: benchmarks/thermal_l1_calibration.py; cached references tests/regression/data/o002_l1_cal/ and o002_l1_dev/;
# re-derived by tests/regression/test_thermal_l1_dev.py.  Per family (side_by_side/6, u_shaped/2): 4.0 mm 0.98839 / 0.98250,
# 4.5 mm 0.98451 / 0.98118, 5.0 mm 0.98378 / 0.98218, 5.5 mm 0.98559 / 0.98244.
CALIBRATION: dict[float, float] = {4.0: 0.98544, 4.5: 0.98284, 5.0: 0.98298, 5.5: 0.98402}


@dataclass
class L1Result:
    tj_mean: np.ndarray  # K, absolute, layout.dies order (calibrated)
    tj_max: np.ndarray  # K, coarse surface maximum per die (uncalibrated; reported, never gated)
    wall_s: float
    meta: dict = field(default_factory=dict)
    T_bp: float = float("nan")
    die_local_rise: np.ndarray = field(default_factory=lambda: np.zeros(0))
    energy_balance: float = float("nan")
    picard_iters: int = 0
    n_cells: int = 0
    calibration: dict = field(default_factory=dict)


def die_size_mm(layout: Layout) -> float:
    sizes = {(round(d.w * 1e3, 6), round(d.h * 1e3, 6)) for d in layout.dies}
    if len(sizes) != 1:
        raise ValueError(f"L1 needs one die size per layout, got {sorted(sizes)}")
    w, hh = next(iter(sizes))
    if w != hh:
        raise ValueError(f"L1 calibration is for square dies, got {w} x {hh} mm")
    return w


def calibration_factor(s_mm: float) -> float:
    for k, c in CALIBRATION.items():
        if abs(k - s_mm) < 1e-6:
            return c
    raise ValueError(f"no L1 calibration for die size {s_mm} mm (table: {sorted(CALIBRATION)})")


def raw_fv(layout: Layout, power_W, *, h: float, T_c: float, constant_k: bool = False,
           grid_rule: dict | None = None) -> dict:
    """Uncalibrated coarse-FV solve: ``{'tj_mean', 'tj_max', 'result'}`` (K, ``layout.dies`` order) on ``grid_rule``
    (default the frozen ``GRID_RULE``; other rules are for the table's derivation and design checks only)."""
    n = len(layout.dies)
    P = np.array(np.broadcast_to(np.asarray(power_W, dtype=float), (n,)))
    g = _TL.build_layout_grid(layout, 0, **(GRID_RULE if grid_rule is None else grid_rule))
    q = np.zeros(g.shape)
    for d, p, (ii, jj, kk) in zip(layout.dies, P, g.die_top_flux_index, strict=True):
        q[np.ix_(ii, jj, [kk])] = p / (d.w * d.h)
    res = solve_steady(g.x, g.y, g.z, g.cell_material, _TL._materials(g.materials, constant_k), h=h, T_inf=T_c,
                       flux={(2, 1): q}, picard_tol=PICARD_TOL_K)
    vals = [_TL._die_values(res, d.bounds) for d in layout.dies]
    return {"tj_mean": np.array([v["tj_mean"] for v in vals]), "tj_max": np.array([v["tj_max"] for v in vals]),
            "result": res}


def evaluate(layout: Layout, power_W, *, h: float, T_c: float, constant_k: bool = False,
             calibrate: bool = True) -> L1Result:
    """Per-die mean (and coarse max) junction temperature [K] of ``layout`` at ``power_W`` (W; scalar or one value
    per die in ``layout.dies`` order), uniform ``h`` [W/(m2 K)] at the baseplate bottom, coolant ``T_c`` [K].

    ``constant_k=True`` holds every layer at ``Layer.k`` (= k at 300 K, the F4 ablation); the calibration factor is
    applied unchanged.  ``calibrate=False`` returns the raw coarse-FV values (for the table's derivation only).
    ``meta['tj_mean_fv']`` holds the uncalibrated coarse-FV die means of the same solve."""
    t0 = time.perf_counter()
    n = len(layout.dies)
    P = np.array(np.broadcast_to(np.asarray(power_W, dtype=float), (n,)))
    s_mm = die_size_mm(layout)
    c = calibration_factor(s_mm) if calibrate else 1.0
    fv = raw_fv(layout, P, h=h, T_c=T_c, constant_k=constant_k)
    res = fv["result"]
    t_bp = T_c + float(P.sum()) / (h * float(layout.baseplate_outline.area))
    rise = c * (fv["tj_mean"] - t_bp)
    return L1Result(
        tj_mean=t_bp + rise, tj_max=fv["tj_max"], wall_s=time.perf_counter() - t0,
        meta={"method": "fv_coarse_xcal", "grid_rule": dict(GRID_RULE), "picard_tol_K": PICARD_TOL_K,
              "constant_k": bool(constant_k), "calibrate": bool(calibrate), "tj_max_is_calibrated": False,
              "tj_mean_fv": fv["tj_mean"]},
        T_bp=t_bp, die_local_rise=rise, energy_balance=float(res.meta["energy_balance"]),
        picard_iters=int(res.meta["picard_iters"]), n_cells=int(res.meta["n_cells"]),
        calibration={"die_size_mm": s_mm, "c": c, "table_version": CALIBRATION_VERSION})


__all__ = ["CALIBRATION", "CALIBRATION_VERSION", "GRID_RULE", "L1Result", "calibration_factor", "evaluate", "raw_fv"]
