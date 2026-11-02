"""Thermal L2 on a ``Layout`` and on laterally uniform box stacks: conforming grid builder, frozen grid rule, three-grid GCI.

Builds docs/thermal_model.md (sections 2-6) on a non-uniform rectilinear grid and solves it with
``solvers.thermal_fv.solve_steady``.  SI units, float64, temperatures in kelvin.

Frozen grid rule (O006; O002 and O003 reuse it unchanged)
---------------------------------------------------------
Mandatory grid lines: every vertex coordinate of the baseplate outline, substrate outline, backside-Cu footprint, every
trace and every die footprint (x and y), and every layer interface in z (including the die-attach top and die top of each
die).  The **level-0 grid** is built from these lines as below; level ``l`` bisects every level-0 cell ``l`` times, so
**every spacing scales by exactly the constant ratio ``R = 2`` between consecutive levels** and every coarse line is a fine
line.  The three GCI levels are fixed: ``LEVEL0 = 0`` (levels 0, 1, 2); there is no per-case level or constant.

* z: ``Z_CELLS`` = 2 cells in every layer (substrate layers, die attach, die), no grading.  (Tried and rejected, see
  docs/thermal_model.md section 8: 4 cells everywhere, extra cells in layers thinner than 0.2 mm, geometric z grading;
  none changed a reported value by more than 0.02 K at twice the cell count.)
* lateral, bulk: ``n_i(0) = ceil(len_i / (m_i h0))`` cells per interval with ``h0 = min(LAT_FRAC * f_min, H0_MAX)``,
  ``f_min`` the smallest interval between consecutive feature lines (the smaller of the x and y values) (die, trace and
  box-source edges and box walls; the outline / baseplate / inset lines are not feature lines), ``LAT_FRAC = 1``,
  ``H0_MAX`` = 1 mm, and ``m_i = FAR_FACTOR = 4`` for intervals that lie wholly outside the substrate outline (the
  baseplate overhang; smooth far field) and 1 elsewhere.  The generator geometry lies on a 0.5 mm design grid, so ``h0`` is
  1 mm and the level 0 / 1 / 2 bulk cells are 1 / 0.5 / 0.25 mm.
* lateral, edges: at every die edge (and every box-source edge), both sides of the line carry **geometric cells**
  ``s_k = EDGE_FRAC * t_min * GROW**k`` (k = 0, 1, ...) until the size reaches the bulk size; ``t_min`` is the thinnest layer
  of the stack (the 50 um die attach), ``EDGE_FRAC`` = 2, ``GROW`` = 1.5.  Each end of an interval takes less than half of
  it, so the grid is mirror-symmetric.  The reason is the bimaterial corner where the die attach (k = 58) meets the copper
  (k = 385) at the die footprint edge: the temperature there behaves like ``r**lambda`` with ``lambda`` about 0.83
  (root of ``k1 tan(lambda pi/2) + k2 tan(lambda pi) = 0`` for the 90 deg attach and 180 deg copper wedges), which limits
  uniform meshes to order ``2 lambda`` about 1.7 and a large error constant; the edge cells cut the level-0 error of the die
  mean 2-4 times.

The constants are frozen at module level.  No other tuning is made per case.

Material assignment (docs/thermal_model.md section 2): a cell takes the material whose region contains the cell centre
(shapely ``contains_xy``; all region edges are grid lines so the test is exact); everything else is void.

Three-grid conservative GCI (O006 A4, D0012, D0013 and its addenda)
-------------------------------------------------------------------
For a value with coarse-to-fine values ``f0, f1, f2`` at levels ``l, l+1, l+2`` (ratio exactly 2), ``d1 = f1 - f0`` and
``d2 = f2 - f1``, each set to 0 when its magnitude is below ``GCI_FLOOR`` = 1e-3 K (ten times the Picard tolerance), and
``rho = d2 / d1``; ``gci_three_grid`` applies O006's A4 rule: 0 if ``d1 = d2 = 0``; ``+inf`` if ``|rho| >= 1`` or
``d1 = 0 < |d2|``; ``3 max(|d1|, |d2|)`` if ``-1 < rho < 0`` (oscillatory); ``1.25 max(|d2|, |d1|/4)`` if
``0 <= rho < 1/4``; ``1.25 |d2| / (2**p - 1)`` with ``p = min(log2(1/rho), 1)`` if ``1/4 <= rho < 1`` (safety factors 1.25
and 3 and the form from Roache, *Verification and Validation in Computational Science and Engineering*, 1998, ch. 5).  The
order is capped at 1 because the material corners make the observed order unreliable; the earlier rule (Fs = 1.25 / 3 by
the observed order, cap 2) was shown non-conservative (T0181).  The same rule is the evaluator's
``mfos.metrics.gci_capped`` with ``floor = 1e-3``.  ``meta['solver_tol']`` maps each reported value name to its GCI in K
(``inf`` when a sequence diverges or stagnates); ``meta['convergence']`` holds the three values, ``p_obs``, ``r``, cell
counts, energy balance and Picard iterations per level.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
import shapely
from shapely.ops import unary_union

from moduleforge.geometry.layout import Layout
from moduleforge.solvers.thermal_fv import ThermalResult, solve_steady

R = 2  # constant refinement ratio between consecutive levels (every spacing scales by exactly 1/R)
Z_CELLS = 2  # level-0 cells per layer thickness
EDGE_FRAC = 2.0  # level-0 first lateral cell at a die / source edge = EDGE_FRAC * thinnest layer thickness
GROW = 1.5  # growth ratio of the geometric edge cells
H0_MAX = 1.0e-3  # m, cap of the level-0 lateral cell size h0
LEVEL0 = 0  # the first of the three GCI levels (fixed by the rule)
LAT_FRAC = 1.0  # level-0 lateral cell = LAT_FRAC * smallest feature interval
FAR_FACTOR = 4  # level-0 lateral cells outside the substrate outline are this many times larger
MERGE_TOL = 1e-9  # m, grid lines closer than this are one line
GCI_FLOOR = 1.0e-3  # K, grid steps below this count as zero in the GCI: ten times the Picard tolerance (O006 A4, D0013)

MAT_NAMES = ("baseplate", "solder", "backside_cu", "ceramic", "top_cu", "die_attach", "die")


# ---------------------------------------------------------------------------------------------------- GCI
def gci_three_grid(f_coarse: float, f_mid: float, f_fine: float, r: float = R, *, floor: float = GCI_FLOOR) -> dict:
    """Order-capped grid convergence index of ``f_fine`` from three grids refined by exactly ``r = 2`` (O006 A4; D0012,
    D0013 and its addenda).  ``d1 = f_mid - f_coarse`` and ``d2 = f_fine - f_mid``, each set to 0 when its magnitude is
    below ``floor`` (K; default ``GCI_FLOOR`` = 1e-3 K, ten times the Picard tolerance, so iteration noise cannot pick the
    branch); ``rho = d2 / d1``:

      d1 = d2 = 0                    0                                   branch 'exact'
      |rho| >= 1, or d1 = 0 < |d2|   +inf                                'divergent'
      -1 < rho < 0                   3 max(|d1|, |d2|)                   'oscillatory'
      0 <= rho < 1/4                 1.25 max(|d2|, |d1|/4)              'fast'
      1/4 <= rho < 1                 1.25 |d2| / (2**p - 1), p = min(log2(1/rho), 1)   'monotone'

    Safety factors 1.25 and 3 (Roache's factor for the less reliable, here oscillatory, estimates) and the form
    ``|d2| / (r**p - 1)``: Roache (1998, *Verification and Validation in Computational Science and Engineering*, ch. 5).
    The cap ``p <= 1``, the branches and the floor are O006's A4 rule; the arithmetic is that of the evaluator's
    ``mfos.metrics.gci_capped`` (not imported here; the unit tests assert equality).  Returns ``gci``, ``p_obs``
    (``log2(1/rho)`` when ``rho > 0``, else NaN), ``monotone`` (``rho > 0``), ``Fs`` (3 for 'oscillatory', 1.25 for
    'fast' and 'monotone', NaN for 'exact' and 'divergent'), ``p`` (the order used: 2 for 'fast', the capped order for
    'monotone', NaN otherwise) and ``branch``."""
    if r != 2:
        raise ValueError(f"the frozen rule refines by exactly 2, got r = {r!r}")
    if floor < 0.0:
        raise ValueError("floor must be non-negative")
    d1, d2 = float(f_mid) - float(f_coarse), float(f_fine) - float(f_mid)
    d1 = 0.0 if abs(d1) < floor else d1
    d2 = 0.0 if abs(d2) < floor else d2
    nan = float("nan")
    if d1 == 0.0 and d2 == 0.0:
        return {"gci": 0.0, "p_obs": nan, "monotone": False, "Fs": nan, "p": nan, "branch": "exact"}
    if d1 == 0.0:
        return {"gci": math.inf, "p_obs": nan, "monotone": False, "Fs": nan, "p": nan, "branch": "divergent"}
    rho = d2 / d1
    p_obs = math.log2(1.0 / rho) if rho > 0.0 else nan
    if abs(rho) >= 1.0:
        return {"gci": math.inf, "p_obs": p_obs, "monotone": rho > 0.0, "Fs": nan, "p": nan, "branch": "divergent"}
    if rho < 0.0:
        return {"gci": 3.0 * max(abs(d1), abs(d2)), "p_obs": nan, "monotone": False, "Fs": 3.0, "p": nan,
                "branch": "oscillatory"}
    if rho < 0.25:
        return {"gci": 1.25 * max(abs(d2), abs(d1) / 4.0), "p_obs": p_obs, "monotone": rho > 0.0, "Fs": 1.25, "p": 2.0,
                "branch": "fast"}
    p = min(p_obs, 1.0)
    return {"gci": 1.25 * abs(d2) / (2.0 ** p - 1.0), "p_obs": p_obs, "monotone": True, "Fs": 1.25, "p": p,
            "branch": "monotone"}


# ---------------------------------------------------------------------------------------------------- grid rule
def _merge(vals) -> np.ndarray:
    v = np.sort(np.asarray(list(vals), dtype=float))
    out = [v[0]]
    for a in v[1:]:
        if a - out[-1] > MERGE_TOL:
            out.append(a)
    return np.array(out)


def edge_graded_nodes(lines: np.ndarray, edge_lines, h0: float, s_edge: float, grow: float, level: int,
                      far_mask=None, far_factor: float = 1.0) -> np.ndarray:
    """Level-``level`` nodes: each interval of ``lines`` gets, at each end that is an ``edge_lines`` line, geometric
    cells ``s_edge * grow**k`` until the size reaches ``h0`` (``far_factor * h0`` for far intervals), the rest uniform
    cells of size <= that; then every cell is bisected ``level`` times."""
    edge = np.array([np.min(np.abs(np.asarray(edge_lines) - v)) < MERGE_TOL if len(edge_lines) else False for v in lines])
    out = []
    for i in range(len(lines) - 1):
        a, b = lines[i], lines[i + 1]
        L = b - a
        hmax = h0 * (far_factor if (far_mask is not None and far_mask[i]) else 1.0)
        sizes_l, sizes_r = [], []
        for flag, acc in ((edge[i], sizes_l), (edge[i + 1], sizes_r)):
            if flag:
                s = s_edge
                while s < hmax and sum(acc) + s < 0.5 * L * (1.0 - 1e-9):  # each end takes < half: mirror-symmetric
                    acc.append(s)
                    s *= grow
        rem = L - sum(sizes_l) - sum(sizes_r)
        if rem <= 1e-12 * L:  # edge cells fill the interval: rescale
            sz = np.array(sizes_l + sizes_r[::-1])
            sz = sz / sz.sum() * L
        else:
            n_mid = max(1, int(np.ceil(rem / hmax - 1e-9)))
            sz = np.array(sizes_l + [rem / n_mid] * n_mid + sizes_r[::-1])
        nodes = a + np.concatenate([[0.0], np.cumsum(sz)])
        nodes[-1] = b
        if level:
            m = R**int(level)
            t = np.arange(m) / m
            nodes = np.concatenate([(nodes[:-1, None] + np.diff(nodes)[:, None] * t[None, :]).ravel(), [b]])
        out.append(nodes[:-1])
    return np.concatenate(out + [[lines[-1]]])


def _subdivide(lines: np.ndarray, counts: np.ndarray) -> np.ndarray:
    parts = [np.linspace(lines[i], lines[i + 1], int(c) + 1)[:-1] for i, c in enumerate(counts)]
    return np.concatenate(parts + [[lines[-1]]])


def feature_size(feature_x, feature_y) -> float:
    """Smallest interval between consecutive distinct feature lines, over both lateral axes."""
    return min(float(np.diff(_merge(f)).min()) for f in (feature_x, feature_y) if len(_merge(f)) > 1)


def level0_cell(f_min: float) -> float:
    """Level-0 lateral cell size ``h0 = min(LAT_FRAC * f_min, H0_MAX)``."""
    return min(LAT_FRAC * f_min, H0_MAX)


def lateral_counts(lines, f_min: float, far_mask, level: int) -> np.ndarray:
    """Cells per interval of the mandatory lines ``lines`` at ``level`` (module docstring rule)."""
    if level < 0 or int(level) != level:
        raise ValueError("level must be a non-negative integer")
    h0 = level0_cell(f_min)
    ln = np.diff(lines)
    m = np.where(far_mask, FAR_FACTOR, 1)
    n0 = np.maximum(1, np.ceil(ln / (m * h0) - 1e-9)).astype(int)
    return n0 * R**int(level)


def z_counts(n_intervals: int, level: int) -> np.ndarray:
    return np.full(n_intervals, Z_CELLS * R**int(level), dtype=int)


# ---------------------------------------------------------------------------------------------------- layout mode
def _coords(poly):
    xs, ys = [], []
    for g in getattr(poly, "geoms", [poly]):
        for ring in (g.exterior, *g.interiors):
            c = np.asarray(ring.coords)
            xs += list(c[:, 0])
            ys += list(c[:, 1])
    return xs, ys


@dataclass
class LayoutGrid:
    x: np.ndarray
    y: np.ndarray
    z: np.ndarray
    cell_material: np.ndarray  # (nx, ny, nz) int, -1 void; indices into MAT_NAMES
    materials: list
    level: int
    die_top_flux_index: list = field(default_factory=list)  # per die: (ix slice, iy slice, iz)

    @property
    def shape(self):
        return self.cell_material.shape


def _regions(layout: Layout):
    back = layout.outline.buffer(-layout.backside_inset, join_style="mitre")
    top = unary_union([t.polygon for t in layout.traces])
    return back, top


def build_layout_grid(layout: Layout, level: int) -> LayoutGrid:
    """Conforming grid and material map of docs/thermal_model.md section 2 at ``level`` of the frozen rule."""
    st = layout.stack
    back, top = _regions(layout)
    polys = [layout.baseplate_outline, layout.outline, back, top, *(t.polygon for t in layout.traces)]
    px, py = [], []
    for p in polys:
        a, b = _coords(p)
        px += a
        py += b
    fx, fy = [], []
    for p in (top, *(d.box for d in layout.dies)):
        a, b = _coords(p)
        fx += a
        fy += b
    xl, yl = _merge(px + fx), _merge(py + fy)
    ox0, oy0, ox1, oy1 = layout.outline.bounds
    far = lambda lines, lo, hi: (0.5 * (lines[:-1] + lines[1:]) < lo) | (0.5 * (lines[:-1] + lines[1:]) > hi)  # noqa: E731
    fmin = feature_size(fx, fy)
    h0, s_edge = level0_cell(fmin), EDGE_FRAC * min(la.thickness for la in (*st.layers, st.die_attach))
    dx = [v for d in layout.dies for v in (d.bounds[0], d.bounds[2])]
    dy = [v for d in layout.dies for v in (d.bounds[1], d.bounds[3])]
    x = edge_graded_nodes(xl, dx, h0, s_edge, GROW, level, far(xl, ox0, ox1), FAR_FACTOR)
    y = edge_graded_nodes(yl, dy, h0, s_edge, GROW, level, far(yl, oy0, oy1), FAR_FACTOR)

    zs = [0.0]
    for la in st.layers:
        zs.append(zs[-1] + la.thickness)
    zt = zs[-1]
    zlines = list(zs)
    for d in layout.dies:
        z0, z1 = layout.die_z_range(d)
        zlines += [zt + d.attach_thickness, z1]
    zl = _merge(zlines)
    z = _subdivide(zl, z_counts(len(zl) - 1, level))

    nx, ny, nz = len(x) - 1, len(y) - 1, len(z) - 1
    xc, yc, zc = 0.5 * (x[:-1] + x[1:]), 0.5 * (y[:-1] + y[1:]), 0.5 * (z[:-1] + z[1:])
    XC, YC = np.meshgrid(xc, yc, indexing="ij")
    inside = {
        "baseplate": shapely.contains_xy(layout.baseplate_outline, XC, YC),
        "backside": shapely.contains_xy(back, XC, YC),
        "outline": shapely.contains_xy(layout.outline, XC, YC),
        "top": shapely.contains_xy(top, XC, YC),
    }
    mat = np.full((nx, ny, nz), -1, dtype=np.int64)
    sub_foot = [inside["baseplate"], inside["backside"], inside["backside"], inside["outline"], inside["top"]]
    for m, la in enumerate(st.layers):
        k = np.nonzero((zc > st.z_bottom(la.name)) & (zc < st.z_top(la.name)))[0]
        mat[:, :, k] = np.where(sub_foot[m][:, :, None], m, -1)
    flux_index = []
    for d in layout.dies:
        x0, y0, x1, y1 = d.bounds
        ii = np.nonzero((xc > x0) & (xc < x1))[0]
        jj = np.nonzero((yc > y0) & (yc < y1))[0]
        za, zb = zt, zt + d.attach_thickness
        zc_hi = layout.die_z_range(d)[1]
        ka = np.nonzero((zc > za) & (zc < zb))[0]
        kd = np.nonzero((zc > zb) & (zc < zc_hi))[0]
        mat[np.ix_(ii, jj, ka)] = 5
        mat[np.ix_(ii, jj, kd)] = 6
        flux_index.append((ii, jj, int(kd[-1])))
    materials = [*st.layers, st.die_attach, st.die]
    return LayoutGrid(x, y, z, mat, materials, int(level), flux_index)


def _materials(grid_materials, constant_k: bool):
    if constant_k:
        return [la.k for la in grid_materials]
    return list(grid_materials)


def _die_values(res: ThermalResult, bounds) -> dict:
    x0, y0, x1, y1 = bounds
    mean, mx = res.surface_stats(x0, x1, y0, y1)
    return {"tj_max": mx, "tj_mean": mean, "tj_centroid": float(res.surface(0.5 * (x0 + x1), 0.5 * (y0 + y1)))}


def summarize_values(per_die: list[dict]) -> dict:
    """Flat name -> value map of the reported values (per die and layout level)."""
    out = {}
    for i, v in enumerate(per_die):
        for key, val in v.items():
            out[f"die{i}.{key}"] = val
    tmax = [v["tj_max"] for v in per_die]
    tmean = [v["tj_mean"] for v in per_die]
    out["tj_max"] = max(tmax)
    out["tj_mean"] = float(np.mean(tmean))
    out["spread_max"] = max(tmax) - min(tmax)
    out["spread_mean"] = max(tmean) - min(tmean)
    return out


def solve_layout_level(layout: Layout, *, level: int, power_W, h: float, T_c: float, constant_k: bool = False,
                       picard_tol: float = 1e-4) -> dict:
    """One level of the layout study: ``{'values', 'meta', 'result'}`` (``result`` is the ThermalResult)."""
    P = np.broadcast_to(np.asarray(power_W, float), (len(layout.dies),))
    g = build_layout_grid(layout, level)
    q = np.zeros(g.shape)
    for d, p, (ii, jj, kk) in zip(layout.dies, P, g.die_top_flux_index, strict=True):
        w, hh = d.w, d.h
        q[np.ix_(ii, jj, [kk])] = p / (w * hh)
    res = solve_steady(g.x, g.y, g.z, g.cell_material, _materials(g.materials, constant_k), h=h, T_inf=T_c,
                       flux={(2, 1): q}, picard_tol=picard_tol)
    vals = summarize_values([_die_values(res, d.bounds) for d in layout.dies])
    meta = {"level": int(level), "n_cells": res.meta["n_cells"], "energy_balance": res.meta["energy_balance"],
            "picard_iters": res.meta["picard_iters"], "wall_time_s": res.meta["wall_time_s"],
            "linear_residual": res.meta["linear_residual"], "q_in": res.meta["q_in"]}
    return {"values": vals, "meta": meta, "result": res}


def combine_levels(levels_meta: list[dict], levels_values: list[dict]) -> dict:
    """GCI of every value from three consecutive levels (coarse to fine): ``solver_tol`` and ``convergence``."""
    if len(levels_values) != 3:
        raise ValueError("three levels are required")
    names = list(levels_values[0])
    solver_tol, conv = {}, {}
    for n in names:
        f = [lv[n] for lv in levels_values]
        g = gci_three_grid(*f)
        solver_tol[n] = g["gci"]
        conv[n] = {"values": f, "p_obs": g["p_obs"], "monotone": g["monotone"], "Fs": g["Fs"], "p": g["p"]}
    return {
        "solver_tol": solver_tol,
        "convergence": conv,
        "r": float(R),
        "n_cells": [m["n_cells"] for m in levels_meta],
        "energy_balance": [m["energy_balance"] for m in levels_meta],
        "picard_iters": [m["picard_iters"] for m in levels_meta],
    }


def solve_layout(layout: Layout, *, power_W, h: float, T_c: float, constant_k: bool = False) -> dict:
    """Three consecutive levels ``LEVEL0..LEVEL0+2``.  Returns the finest-level values (``values``), the finest
    ThermalResult (``result``) and ``meta`` with ``solver_tol`` (GCI per value, K), ``convergence`` (module docstring),
    ``r``, ``n_cells``, ``energy_balance`` and ``picard_iters`` per level."""
    runs = []
    for lv in range(LEVEL0, LEVEL0 + 3):
        runs.append(solve_layout_level(layout, level=lv, power_W=power_W, h=h, T_c=T_c, constant_k=constant_k))
        if lv < LEVEL0 + 2:
            runs[-1].pop("result")
    meta = combine_levels([r_["meta"] for r_ in runs], [r_["values"] for r_ in runs])
    meta["levels"] = [r_["meta"]["level"] for r_ in runs]
    return {"values": runs[-1]["values"], "result": runs[-1]["result"], "meta": meta}


# ---------------------------------------------------------------------------------------------------- box-stack mode
def build_box_grid(a: float, b: float, thicknesses, sources, level: int):
    """Grid of the laterally uniform N-layer box ``[0,a]x[0,b]``; ``sources`` = [(x0, x1, y0, y1), ...]."""
    fx = [0.0, a] + [s[0] for s in sources] + [s[1] for s in sources]
    fy = [0.0, b] + [s[2] for s in sources] + [s[3] for s in sources]
    xl, yl = _merge(fx), _merge(fy)
    h0, s_edge = level0_cell(feature_size(fx, fy)), EDGE_FRAC * min(thicknesses)
    x = edge_graded_nodes(xl, [s[0] for s in sources] + [s[1] for s in sources], h0, s_edge, GROW, level)
    y = edge_graded_nodes(yl, [s[2] for s in sources] + [s[3] for s in sources], h0, s_edge, GROW, level)
    zl = np.concatenate([[0.0], np.cumsum(thicknesses)])
    z = _subdivide(zl, z_counts(len(zl) - 1, level))
    layer_of = np.searchsorted(zl, 0.5 * (z[:-1] + z[1:])) - 1
    mat = np.broadcast_to(layer_of, (len(x) - 1, len(y) - 1, len(z) - 1)).copy()
    return x, y, z, mat


def solve_box_level(a, b, layers, sources, *, h, T_c, level, picard_tol: float = 1e-4) -> dict:
    """``layers`` = [(thickness, k or Layer), ...] bottom-up; ``sources`` = [(x0, x1, y0, y1, P_W), ...] on the top face.

    Returns ``{'values', 'meta', 'result'}``; ``values`` has ``src{i}.tj_max / tj_mean / tj_centroid``."""
    thick = [t for t, _ in layers]
    kk = [k for _, k in layers]
    x, y, z, mat = build_box_grid(a, b, thick, [s[:4] for s in sources], level)
    xc, yc = 0.5 * (x[:-1] + x[1:]), 0.5 * (y[:-1] + y[1:])
    q = np.zeros(mat.shape)
    for x0, x1, y0, y1, P in sources:
        ii, jj = np.nonzero((xc > x0)[:, None] & (xc < x1)[:, None] & (yc > y0)[None, :] & (yc < y1)[None, :])
        q[ii, jj, -1] += P / ((x1 - x0) * (y1 - y0))
    res = solve_steady(x, y, z, mat, kk, h=h, T_inf=T_c, flux={(2, 1): q}, picard_tol=picard_tol)
    per = [_die_values(res, (s[0], s[2], s[1], s[3])) for s in sources]
    vals = {}
    for i, v in enumerate(per):
        for key, val in v.items():
            vals[f"src{i}.{key}"] = val
    vals["spread_max"] = max(v["tj_max"] for v in per) - min(v["tj_max"] for v in per)
    meta = {"level": int(level), "n_cells": res.meta["n_cells"], "energy_balance": res.meta["energy_balance"],
            "picard_iters": res.meta["picard_iters"], "wall_time_s": res.meta["wall_time_s"]}
    return {"values": vals, "meta": meta, "result": res}


def solve_box_stack(a, b, layers, sources, *, h, T_c) -> dict:
    """Box-stack mode at three consecutive levels, same output structure as ``solve_layout``."""
    runs = []
    for lv in range(LEVEL0, LEVEL0 + 3):
        runs.append(solve_box_level(a, b, layers, sources, h=h, T_c=T_c, level=lv))
    meta = combine_levels([r_["meta"] for r_ in runs], [r_["values"] for r_ in runs])
    meta["levels"] = [r_["meta"]["level"] for r_ in runs]
    return {"values": runs[-1]["values"], "result": runs[-1]["result"], "meta": meta}


__all__ = [
    "EDGE_FRAC", "FAR_FACTOR", "GROW", "H0_MAX", "LAT_FRAC", "LEVEL0", "MAT_NAMES", "R", "Z_CELLS", "LayoutGrid", "build_box_grid", "build_layout_grid",
    "combine_levels", "edge_graded_nodes", "feature_size", "gci_three_grid", "lateral_counts", "level0_cell", "solve_box_level", "solve_box_stack", "solve_layout",
    "solve_layout_level", "summarize_values", "z_counts",
]

