"""E009 runner: scikit-fem thermal reference (production thermal_fem, frozen graded Q1 rule, amg_gs_sweeps = 2) against
O006's frozen references and against the in-house finite-volume L2 at its levels 1-3 on five generator layouts (O007).

Design: experiments/drafts/E009.yaml; rationale: research/notes/o007-e009-design.md.  SI units, kelvin, float64.

Roles (swapped against E006): scikit-fem is under test, the L2 (solvers.thermal_fv / thermal_layout at its own frozen
rule, levels 1, 2, 3) is the cross-check.  Every scikit-fem solve goes through production
``moduleforge.solvers.thermal_fem`` with ONE ``GridRule`` built from ``config.fem_rule`` (research/o007_dev3/
frozen_config.json, verbatim), edge grading and ``amg_gs_sweeps`` included; there is no research-side grid or solver
emulation.  After every scikit-fem solve the runner asserts ``result.meta['amg_gs_sweeps'] == fem_rule['amg_gs_sweeps']``
(an error, never a verdict, if not).  The constant-k nulls use the same production grid (``thermal_fem.layout_grid``) and
assembly (``thermal_fem._solve_grid``) with k fixed per material at that material's volume-mean temperature of the finest
k(T) solve (as T0207/T0228/T0243 and E006).

E006's machinery is reused by import, unchanged: load_refs, series_checks, mms_checks (F1), Checks, Stats (constant-ratio
line check), dev_layouts, fresh_layouts, preflight (FV memory), a4, direction, mms_layout, _gate_max.

Modes
  (default)                    the registered run, through mfos.evidence.ExperimentRun (config from MFOS_SPEC_JSON),
                               sealed seed required
  --smoke --rows-out PATH      pipeline check on coarsened copies of BOTH frozen rules (config smoke_fem_overrides,
                               smoke_l2_rule; the ratio 2 between levels, the edge grading path and amg_gs_sweeps are
                               kept), every case, the two dev layouts and three 'fresh' layouts drawn from the non-sealed
                               dev seed config.smoke_fresh_dev_seed; writes only the rows.  Never creates an evidence run
                               and never touches the sealed seed.

Rows (every row carries the three grid values of each solver, coarsest first, so the evaluator recomputes every metric):
  kind=case        one per reported point of a reference case (is_finest true): T_fem (= fem_lv2), T_ref, case_scale,
                   fem_lv0..fem_lv2, the A4 estimate (gci, a4_branch, p_obs, d1, d2, non_asymptotic), dT_const_k, the
                   snap of the point (requested, used, distance), its node stencil per level, and per grid solve
                   cg_max_iterations / linear_rel_residual_max (thermal_fem meta, T0222).
  kind=crosscheck  one per die of the five layouts (is_finest true): fem_lv0..2, l2_lv1..3, both GCIs, branches and
                   convergence directions (same_side flag), F5 (l2_gci <= f5_max_K, NOT gated), the Tj-max node per
                   level and its move count, power_w, calibration rise, dT_const_k and its A3 ratio, CG / residual data.
References: GCI form and safety factors, Roache (1998) ch. 5 (via mfos.metrics, D0012/D0013); Muzychka, Culham &
Yovanovich, J. Electron. Packag. 125(2):178 (2003) and the N-layer series (e006_series.py); manufactured solution
(e006_mms.py; Salari & Knupp, SAND2000-1444).
"""
from __future__ import annotations

import argparse
import gc
import hashlib
import json
import math
import os
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "experiments" / "runners"), str(ROOT / "tools" / "mfos"), str(ROOT / "src")]

import e006_mms as MMS  # noqa: E402
import e006_run as E6  # noqa: E402  (E006 machinery, unchanged, read-only use)
import yaml  # noqa: E402
from mfos import metrics as MX  # noqa: E402

from moduleforge.generate.halfbridge import FAMILIES  # noqa: E402
from moduleforge.solvers import thermal_fem as FEM  # noqa: E402
from moduleforge.solvers import thermal_layout as TL  # noqa: E402

EID = "E009"
NAN = float("nan")
FROZEN_CONFIG_PATH = "research/o007_dev3/frozen_config.json"
Checks, Stats, log, rss_gb, a4, direction, _gate_max = E6.Checks, E6.Stats, E6.log, E6.rss_gb, E6.a4, E6.direction, \
    E6._gate_max


# ------------------------------------------------------------------------------------------------ config / rule
def load_config() -> dict:
    env = os.environ.get("MFOS_SPEC_JSON")
    if env:
        return json.loads(env)["config"]
    for p in (ROOT / "experiments" / "specs" / f"{EID}.yaml", ROOT / "experiments" / "drafts" / f"{EID}.yaml"):
        if p.exists():
            return yaml.safe_load(p.read_text())["config"]
    raise FileNotFoundError(f"no {EID} spec")


def rule_from(fr: dict) -> FEM.GridRule:
    """The one scikit-fem GridRule of E009, built key for key from the frozen configuration."""
    eg = fr["edge_grading"]
    return FEM.GridRule(h0=float(fr["h0_m"]), nz={}, default_nz=int(fr["nz_min"]), zrefine=bool(fr["zrefine"]),
                        near_margin=float(fr["near_margin_m"]), min_cells=int(fr["min_cells"]),
                        element_order=int(fr["element_order"]), dz_max=float(fr["dz_max_m"]),
                        edge_grading=(float(eg["first_offset_m"]), float(eg["ratio"]), float(eg["max_offset_m"]),
                                      float(eg["min_gap_fraction"])),
                        amg_gs_sweeps=int(fr["amg_gs_sweeps"]))


def smoke_fem_rule(cfg: dict) -> dict:
    """Smoke only: the frozen rule with the keys of config.smoke_fem_overrides replaced (coarser, same code paths)."""
    fr = json.loads(json.dumps(cfg["fem_rule"]))
    for k, v in cfg["smoke_fem_overrides"].items():
        fr[k] = v
    return fr


def rule_checks(cfg: dict, ck: Checks) -> None:
    """fem_rule_frozen: config.fem_rule equals the frozen file, is feasible, and every production constant it records
    equals thermal_fem's (snap fraction, CG rtol/cap, AMG seed, Picard tolerance, ratio, levels, data quadrature)."""
    fr = cfg["fem_rule"]
    disk = json.loads((ROOT / FROZEN_CONFIG_PATH).read_text())
    prod = {"snap_fraction": FEM.SNAP_FRACTION, "linear_rtol": FEM.LINEAR_RTOL, "cg_maxiter": FEM.CG_MAXITER,
            "amg_seed": FEM.AMG_SEED, "picard_tol_K": FEM.PICARD_TOL_K, "refinement_ratio": FEM.REFINEMENT_RATIO,
            "levels": list(FEM.LEVELS)}
    bad = [k for k, v in prod.items() if fr[k] != v]
    ok = (fr == disk and fr["feasible"] is True and not fr["levels_missing"] and not bad
          and FEM.DATA_INTORDER == 7 and fr["element_order"] == 1 and fr["amg_gs_sweeps"] == 2
          and fr["picard_tol_K"] == cfg["picard_tol_K"])
    ck.add("fem_rule_frozen", ok, detail=f"config.fem_rule == {FROZEN_CONFIG_PATH}: {fr == disk}; feasible "
           f"{fr['feasible']}; production constants differing: {bad}; DATA_INTORDER {FEM.DATA_INTORDER}; rule "
           f"{rule_from(fr)}")


# ------------------------------------------------------------------------------------------------ solve bookkeeping
class Solves:
    """Every solve of the run (both solvers), with the per-solve data the sanity checks and the rows use."""

    def __init__(self, cfg: dict, smoke: bool):
        self.cfg, self.smoke, self.items = cfg, smoke, []
        self.phys_gb = FEM.physical_memory_bytes() / 1e9
        self.cap_gb = cfg["memory_fraction"] * self.phys_gb
        if smoke:
            self.cap_gb = min(self.cap_gb, float(cfg["smoke_memory_cap_GB"]))

    def fem_preflight(self, dofs: int, tag: str) -> None:
        est = dofs * self.cfg["fem_bytes_per_dof"] * self.cfg["fem_memory_margin"] / 1e9
        if est > self.cap_gb:
            raise MemoryError(f"{tag}: {dofs / 1e6:.2f} M DOF, estimated {est:.1f} GB > {self.cap_gb:.1f} GB "
                              f"({'smoke cap' if self.smoke else 'memory_fraction x physical'}); run on the burst VM "
                              f"({self.cfg['burst_machine']})")

    def fem(self, tag: str, r, level, kT: bool, expect_sweeps: int) -> dict:
        m = r.meta
        if m.get("amg_gs_sweeps") != expect_sweeps:
            raise RuntimeError(f"{tag}: result meta amg_gs_sweeps {m.get('amg_gs_sweeps')!r} != fem_rule "
                               f"{expect_sweeps}: refusing to continue")
        rec = {"tag": tag, "solver": "fem", "level": level, "kT": kT, "dofs": int(r.dofs),
               "wall_s": round(float(r.wall_s), 2), "energy_balance": float(r.energy_balance),
               "picard_iters": int(r.picard_iters), "picard_residual_K": float(r.picard_residual),
               "cg_iterations": [int(v) for v in m["cg_iterations"]], "cg_max_iterations": int(m["cg_max_iterations"]),
               "linear_rel_residual_max": float(m["linear_rel_residual_max"]), "cg_hit_maxiter": bool(m["cg_hit_maxiter"]),
               "amg_gs_sweeps": m["amg_gs_sweeps"], "max_snap_m": float(m["max_snap_m"]), "n_lines": m["n_lines"],
               "peak_rss_gb": round(rss_gb(), 3)}
        self.items.append(rec)
        log(f"  fem {tag}: {rec['dofs']} DOF, {rec['wall_s']:.1f} s, Picard {rec['picard_iters']}, CG max "
            f"{rec['cg_max_iterations']}, res {rec['linear_rel_residual_max']:.1e}, eb {rec['energy_balance']:.1e}, "
            f"peak RSS {rec['peak_rss_gb']:.2f} GB")
        return rec

    def fv(self, tag: str, res, level: int) -> dict:
        m = res.meta
        rec = {"tag": tag, "solver": "fv", "level": level, "kT": True, "n_cells": int(m["n_cells"]),
               "wall_s": round(float(m["wall_time_s"]), 2), "energy_balance": float(m["energy_balance"]),
               "picard_iters": int(m["picard_iters"]), "picard_residual_K": float(m.get("picard_dT", NAN)),
               "linear_iters": m.get("linear_iters"), "linear_residual": float(m.get("linear_residual", NAN)),
               "peak_rss_gb": round(rss_gb(), 3)}
        self.items.append(rec)
        log(f"  fv {tag}: {rec['n_cells']} cells, {rec['wall_s']:.1f} s, Picard {rec['picard_iters']}, eb "
            f"{rec['energy_balance']:.1e}, peak RSS {rec['peak_rss_gb']:.2f} GB")
        return rec


def _used(r, ax: str, v: float | None) -> float | None:
    """The coordinate the production grid uses for a requested mandatory line (after snapping)."""
    if v is None:
        return None
    for a, b in r.meta["snapped_lines"].get(ax, []):
        if abs(a - v) <= 1e-12:
            return float(b)
    return float(v)


def _stencil(r, x, y, z=None) -> list:
    return [{k: s[k] for k in ("index", "on_line", "coord", "lo", "hi")} for s in FEM.node_stencil(r, x, y, z)]


def _layer_means(r, g, n_mat: int) -> list:
    """Volume-mean temperature per material (element mean of its 8 vertex values x element volume), as T0207."""
    ci, cj, ck = np.nonzero(g.mat >= 0)
    em = g.mat[ci, cj, ck]
    vol = np.diff(g.x)[ci] * np.diff(g.y)[cj] * np.diff(g.z)[ck]
    Te = r.T[r.field_eval.mesh.t].mean(axis=0)
    return [float(np.sum(Te[em == m] * vol[em == m]) / np.sum(vol[em == m])) if np.any(em == m) else None
            for m in range(n_mat)]


def _const_k_solve(g, kconst: list):
    g.kfun = [(lambda T, k=k: np.full_like(T, k)) for k in kconst]
    return FEM._solve_grid(g, constant_k=True)


def _growth(counts: list[int]) -> list[float]:
    return [b / a for a, b in zip(counts[:-1], counts[1:], strict=False)]


# ------------------------------------------------------------------------------------------------ reference cases
class Ctx:
    def __init__(self, cfg: dict, fr: dict, smoke: bool):
        self.cfg, self.fr, self.rule, self.smoke = cfg, fr, rule_from(fr), smoke
        self.levels = tuple(int(v) for v in fr["levels"])
        self.l2_levels = tuple(int(v) for v in cfg["l2_levels"])
        self.sv = Solves(cfg, smoke)
        self.st = Stats()  # E006's constant-ratio line check (st.lines) for both solvers
        self.growth: list[tuple[str, list[float]]] = []
        self.node_ok, self.node_detail = True, []
        self.mms_ref_eb: list[tuple[str, float]] = []
        self.op: list[tuple[str, float]] = []


def _case_row(ctx: Ctx, case: str, source: str, point: str, f: list, T_ref: float, scale: float, dT_const: float,
              snap: dict | None, stencils: list | None, solves: list[dict]) -> dict:
    est = a4(*f, ctx.cfg["gci_floor_K"])
    err = f[2] - T_ref
    row = {"kind": "case", "case": case, "source": source, "point": point, "is_finest": True, "grid_level": 2,
           "T_fem": f[2], "T_ref": T_ref, "case_scale": scale, "fem_lv0": f[0], "fem_lv1": f[1], "fem_lv2": f[2],
           **est, "err_K": err, "scaled_err": abs(err) / scale,
           "err_lv0_K": f[0] - T_ref, "err_lv1_K": f[1] - T_ref, "err_lv2_K": f[2] - T_ref,
           "gci_over_err": est["gci"] / abs(err) if abs(err) > 0 else math.inf, "dT_const_k": dT_const,
           "snap": snap, "stencil_per_level": stencils}
    for lv, s in zip(ctx.levels, solves, strict=True):
        row[f"fem_cg_max_iterations_lv{lv}"] = s["cg_max_iterations"]
        row[f"fem_linear_rel_residual_max_lv{lv}"] = s["linear_rel_residual_max"]
        row[f"fem_cg_hit_maxiter_lv{lv}"] = s["cg_hit_maxiter"]
        row[f"fem_dofs_lv{lv}"] = s["dofs"]
    return row


def _point_record(r, x_req, y_req, z_req=None) -> dict:
    xu, yu, zu = _used(r, "x", x_req), _used(r, "y", y_req), _used(r, "z", z_req)
    dist = max(abs(xu - x_req), abs(yu - y_req), 0.0 if z_req is None else abs(zu - z_req))
    return {"T": FEM.node_value(r, xu, yu, zu), "snap": {"x_req": x_req, "x_used": xu, "y_req": y_req, "y_used": yu,
            "z_req": z_req, "z_used": zu, "distance_m": dist}, "stencil": _stencil(r, xu, yu, zu)}


def _persist(ctx: Ctx, tag: str, recs: list[dict]) -> None:
    """node_persistence: same used coordinates and same stencil coordinates (on a grid line) on every level."""
    s0 = recs[0]["snap"]
    ok = all(r["snap"] == s0 for r in recs)
    ok &= all(all(a["on_line"] for a in r["stencil"]) for r in recs)
    ok &= all([a["coord"] for a in r["stencil"]] == [a["coord"] for a in recs[0]["stencil"]] for r in recs)
    ctx.node_ok &= bool(ok)
    if not ok:
        ctx.node_detail.append(f"{tag}: FAIL")


def run_box_case(ctx: Ctx, name: str, c: dict, ref_rows: list[dict]) -> list[dict]:
    srcs = [(s["xc_m"] - s["c_m"] / 2, s["yc_m"] - s["d_m"] / 2, s["xc_m"] + s["c_m"] / 2, s["yc_m"] + s["d_m"] / 2,
             s["Q_W"]) for s in c["sources"]]
    names = [s["name"] for s in c["sources"]]
    layers = [FEM.BoxLayer(la["t_m"], la["k_W_mK"], int(ctx.fr["nz_min"]), la["name"]) for la in c["layers_bottom_up"]]
    mx = [r for r in ref_rows if r["point"] == "max"]
    extra = ([r["x_m"] for r in mx], [r["y_m"] for r in mx], None)  # frozen reference maxima: mandatory lines
    per = {i: [] for i in range(len(ref_rows))}
    solves, lines, dofs = [], [], []
    for lv in ctx.levels:
        g = FEM.box_stack_grid(c["a_m"], c["b_m"], layers, c["h_W_m2K"], c["Tf_K"], srcs, rule=ctx.rule, level=lv,
                               extra_lines=extra)
        ctx.sv.fem_preflight(FEM._count_nodes(g.mat), f"{name} L{lv}")
        del g
        r = FEM.solve_box_stack(c["a_m"], c["b_m"], layers, c["h_W_m2K"], c["Tf_K"], srcs, rule=ctx.rule, level=lv,
                                extra_lines=extra)
        solves.append(ctx.sv.fem(f"{name}/L{lv}", r, lv, kT=True, expect_sweeps=ctx.rule.amg_gs_sweeps))
        lines.append(tuple(np.asarray(r.meta["lines"][a]) for a in ("x", "y", "z")))
        dofs.append(int(r.dofs))
        for i, row in enumerate(ref_rows):
            if row["point"] == "mean":  # Galerkin area mean over the source face
                per[i].append({"T": float(r.tj_mean[names.index(row["source"])]), "snap": None, "stencil": None})
            else:
                per[i].append(_point_record(r, row["x_m"], row["y_m"]))
        del r
        gc.collect()
    ctx.st.lines(f"fem/{name}", lines)
    ctx.growth.append((f"fem/{name}", _growth(dofs)))
    out = []
    for i, row in enumerate(ref_rows):
        recs = per[i]
        if recs[0]["snap"] is not None:
            _persist(ctx, f"{name}/{row['source']}.{row['point']}", recs)
        f = [p["T"] for p in recs]
        out.append(_case_row(ctx, name, row["source"], f"{row['source']}.{row['point']}", f, row["T_K"], c["scale_K"],
                             f[-1], recs[0]["snap"], [p["stencil"] for p in recs], solves))
    return out  # constant k: the null (dT_const_k) equals the scikit-fem value, as E006


def run_mms(ctx: Ctx, mms: dict) -> list[dict]:
    case, lay = MMS.build_case(), E6.mms_layout()
    pts = mms["payload"]["reported_points"]
    ex_pts = [p for p in pts if p["kind"] != "area_mean"]
    extra = ([p["x"] for p in ex_pts], [p["y"] for p in ex_pts], [p["z"] for p in ex_pts])
    q_ref = -float(mms["balance"]["robin_W"])
    Tc = float(ctx.cfg["mms_Tc_K"])
    per = {p["id"]: [] for p in pts}
    solves, lines, dofs = [], [], []
    tm = g = None
    for lv in ctx.levels:
        g = FEM.layout_grid(lay, 0.0, case.h, Tc, ctx.rule, lv, extra)
        ctx.sv.fem_preflight(FEM._count_nodes(g.mat), f"mms L{lv}")
        r = FEM.solve_layout(lay, 0.0, case.h, Tc, rule=ctx.rule, level=lv, source=case.source, flux=case.flux,
                             T_inf=case.T_inf, extra_lines=extra)
        solves.append(ctx.sv.fem(f"mms/L{lv}", r, lv, kT=True, expect_sweeps=ctx.rule.amg_gs_sweeps))
        ctx.mms_ref_eb.append((f"mms/L{lv}/vs_reference_integral", abs(float(r.meta["q_out_W"]) / q_ref - 1.0)))
        lines.append(tuple(np.asarray(r.meta["lines"][a]) for a in ("x", "y", "z")))
        dofs.append(int(r.dofs))
        for p in pts:
            if p["kind"] == "area_mean":
                per[p["id"]].append({"T": float(r.tj_mean[0]), "snap": None, "stencil": None})
            else:
                per[p["id"]].append(_point_record(r, p["x"], p["y"], p["z"]))
        if lv == ctx.levels[-1]:
            tm = _layer_means(r, g, len(FEM._materials(lay)))
        del r
        gc.collect()
    ctx.st.lines("fem/mms", lines)
    ctx.growth.append(("fem/mms", _growth(dofs)))
    # F3 null: constant k per material at its volume-mean temperature of the finest k(T) solve
    mats = FEM._materials(lay)
    kconst = [float(la.k_at(t)) if t is not None else float(la.k) for la, t in zip(mats, tm, strict=True)]
    gn = FEM.layout_grid(lay, 0.0, case.h, Tc, ctx.rule, ctx.levels[-1], extra)
    gn.source, gn.flux, gn.T_inf = case.source, case.flux, case.T_inf
    rc = _const_k_solve(gn, kconst)
    ctx.sv.fem(f"mms/L{ctx.levels[-1]}/constk", rc, ctx.levels[-1], kT=False, expect_sweeps=ctx.rule.amg_gs_sweeps)
    ctx.mms_ref_eb.append(("mms/constk/vs_reference_integral", abs(float(rc.meta["q_out_W"]) / q_ref - 1.0)))
    out = []
    for p in pts:
        recs = per[p["id"]]
        if p["kind"] == "area_mean":
            nul = float(rc.tj_mean[0])
        else:
            _persist(ctx, f"mms/{p['id']}", recs)
            s = recs[0]["snap"]
            nul = FEM.node_value(rc, s["x_used"], s["y_used"], s["z_used"])
        row = _case_row(ctx, "mms", "die" if p["level"] == "die" else p["level"], p["id"], [q["T"] for q in recs],
                        p["T_K"], mms["payload"]["case_scale_K"], nul, recs[0]["snap"], [q["stencil"] for q in recs],
                        solves)
        row["kconst_W_mK"] = kconst
        row["layer_mean_T_K"] = tm
        out.append(row)
    del rc, gn, g
    gc.collect()
    return out


# ------------------------------------------------------------------------------------------------ generator layouts
def calibrate_power(ctx: Ctx, name: str, lay) -> tuple[float, float, object, list[dict]]:
    """Equal power per die from scikit-fem level-0 solves of the frozen rule so that the hottest die's Tj max rises
    target +/- calibration_tol above the coolant (proportional update p <- p target / rise, as E006's calibrate_power).
    Returns (p, rise, result at p, calibration history); the level-0 result at exactly p is fem_lv0.  Raises (an error,
    never a verdict) if the tolerance is not met in calibration_max_iters solves."""
    cfg = ctx.cfg
    Tc, h, tgt, tol = cfg["coolant_K"], cfg["h_W_m2K"], cfg["target_rise_K"], cfg["calibration_tol_K"]
    lv0 = ctx.levels[0]
    ctx.sv.fem_preflight(FEM.estimate_dofs(lay, ctx.rule, lv0), f"{name} calibration L{lv0}")
    p, hist = float(cfg["power_start_W"]), []
    for it in range(int(cfg["calibration_max_iters"])):
        r = FEM.solve_layout(lay, p, h, Tc, rule=ctx.rule, level=lv0)
        rec = ctx.sv.fem(f"{name}/cal{it}", r, lv0, kT=True, expect_sweeps=ctx.rule.amg_gs_sweeps)
        rise = float(np.max(r.tj_max) - Tc)
        hist.append({"power_W": p, "rise_K": rise, "cg_max_iterations": rec["cg_max_iterations"],
                     "linear_rel_residual_max": rec["linear_rel_residual_max"], "cg_hit_maxiter": rec["cg_hit_maxiter"]})
        if abs(rise - tgt) <= tol:
            return p, rise, r, hist
        p *= tgt / rise
        del r
        gc.collect()
    raise RuntimeError(f"{name}: power calibration did not reach {tgt} +/- {tol} K in {len(hist)} level-0 solves "
                       f"({hist}); refusing to return a power whose rise was not computed")


def run_layout(ctx: Ctx, name: str, lay, layout_set: str) -> list[dict]:
    cfg = ctx.cfg
    Tc, h = cfg["coolant_K"], cfg["h_W_m2K"]
    n = len(lay.dies)
    P, cal, r0, hist = calibrate_power(ctx, name, lay)
    ctx.op.append((name, abs(cal - cfg["target_rise_K"])))
    log(f"{name}: {n} dies, {P:.6f} W per die, scikit-fem level-0 rise {cal:.4f} K ({len(hist)} solves)")
    # die-centroid node diagnostic (T0228): level-0 line nearest each die centroid; a node at every level (bisection)
    l0 = r0.meta["lines"]
    cen = []
    for d in lay.dies:
        b = d.bounds
        cx, cy = 0.5 * (b[0] + b[2]), 0.5 * (b[1] + b[3])
        cen.append((float(l0["x"][np.argmin(np.abs(l0["x"] - cx))]), float(l0["y"][np.argmin(np.abs(l0["y"] - cy))])))
    fe, xyz, cnode = [[] for _ in range(n)], [[] for _ in range(n)], [[] for _ in range(n)]
    solves, lines, dofs = [], [], []
    tm = None
    for lv in ctx.levels:
        if lv == ctx.levels[0]:
            r, rec = r0, ctx.sv.items[-1]  # the calibration solve at exactly P is the level-0 solve
        else:
            ctx.sv.fem_preflight(FEM.estimate_dofs(lay, ctx.rule, lv), f"{name} fem L{lv}")
            r = FEM.solve_layout(lay, P, h, Tc, rule=ctx.rule, level=lv)
            rec = ctx.sv.fem(f"{name}/fem/L{lv}", r, lv, kT=True, expect_sweeps=ctx.rule.amg_gs_sweeps)
        solves.append(rec)
        lines.append(tuple(np.asarray(r.meta["lines"][a]) for a in ("x", "y", "z")))
        dofs.append(int(r.dofs))
        for i in range(n):
            fe[i].append(float(r.tj_max[i]))
            xyz[i].append([float(v) for v in r.meta["tj_max_xyz"][i]])
            cnode[i].append(FEM.node_value(r, cen[i][0], cen[i][1], r.meta["tj_max_xyz"][i][2]))
        if lv == ctx.levels[-1]:
            tm = _layer_means(r, FEM.layout_grid(lay, P, h, Tc, ctx.rule, lv), len(FEM._materials(lay)))
        del r
        r0 = None
        gc.collect()
    ctx.st.lines(f"fem/{name}", lines)
    ctx.growth.append((f"fem/{name}", _growth(dofs)))
    # constant-k column: k per material at its volume-mean temperature of the finest k(T) solve, same grid
    mats = FEM._materials(lay)
    kconst = [float(la.k_at(t)) if t is not None else float(la.k) for la, t in zip(mats, tm, strict=True)]
    rc = _const_k_solve(FEM.layout_grid(lay, P, h, Tc, ctx.rule, ctx.levels[-1]), kconst)
    crec = ctx.sv.fem(f"{name}/fem/L{ctx.levels[-1]}/constk", rc, ctx.levels[-1], kT=False,
                      expect_sweeps=ctx.rule.amg_gs_sweeps)
    tconst = [float(v) for v in rc.tj_max]
    del rc
    gc.collect()
    # the cross-check: the L2 at levels 1-3 of its own frozen rule, same power
    l2, l2rec, l2lines = [[] for _ in range(n)], [], []
    for lv in ctx.l2_levels:
        gfv = TL.build_layout_grid(lay, lv)
        l2lines.append((gfv.x, gfv.y, gfv.z))
        E6.preflight(int((gfv.cell_material >= 0).sum()), cfg, f"{name} L2 level {lv}")
        del gfv
        out = TL.solve_layout_level(lay, level=lv, power_W=P, h=h, T_c=Tc)
        l2rec.append(ctx.sv.fv(f"{name}/l2/L{lv}", out["result"], lv))
        for i in range(n):
            l2[i].append(float(out["values"][f"die{i}.tj_max"]))
        del out
        gc.collect()
    ctx.st.lines(f"l2/{name}", l2lines)
    ctx.growth.append((f"l2/{name}", _growth([s["n_cells"] for s in l2rec])))
    rows, floor, cap = [], cfg["gci_floor_K"], cfg["f5_max_K"]
    for i, d in enumerate(lay.dies):
        e, s = a4(*fe[i], floor), a4(*l2[i], floor)
        fd, ld = direction(fe[i][1], fe[i][2]), direction(l2[i][1], l2[i][2])
        tot = e["gci"] + s["gci"]
        diff = abs(fe[i][2] - l2[i][2])
        ratio = (math.inf if s["gci"] > cap or math.isinf(tot) or (tot == 0.0 and diff > 0)
                 else (diff / tot if tot > 0 else 0.0))
        cdiff = abs(tconst[i] - l2[i][2])
        cratio = math.inf if math.isinf(tot) or (tot == 0.0 and cdiff > 0) else (cdiff / tot if tot > 0 else 0.0)
        moves = sum(1 for a, b in zip(xyz[i][:-1], xyz[i][1:], strict=False)
                    if max(abs(u - v) for u, v in zip(a, b, strict=True)) > 1e-9)
        row = {"kind": "crosscheck", "is_finest": True, "layout": name, "layout_set": layout_set,
               "family": lay.family, "dies_per_switch": lay.dies_per_switch, "fingerprint": lay.fingerprint(),
               "die": i, "switch": d.switch, "power_w": P, "calibration_rise_K": cal, "calibration_history": hist,
               "rise_lv0_K": fe[i][0] - Tc, "tj_fem": fe[i][2], "fem_lv0": fe[i][0], "fem_lv1": fe[i][1],
               "fem_lv2": fe[i][2], **e, "tj_l2": l2[i][2], "l2_lv1": l2[i][0], "l2_lv2": l2[i][1], "l2_lv3": l2[i][2],
               "l2_gci": s["gci"], "l2_a4_branch": s["a4_branch"], "l2_p_obs": s["p_obs"], "l2_d1": s["d1"],
               "l2_d2": s["d2"], "l2_non_asymptotic": s["non_asymptotic"], "f5_ok": bool(s["gci"] <= cap),
               "fem_direction": fd, "l2_direction": ld, "same_side": fd == ld, "abs_diff_K": diff,
               "a3_ratio": ratio, "summed_gci_K": tot, "dT_const_k": tconst[i], "a3_ratio_const_k": cratio,
               "kconst_W_mK": kconst, "layer_mean_T_K": tm,
               "tj_max_xyz_per_level": xyz[i], "tj_max_node_moves": moves,
               "centroid_node_xy": list(cen[i]), "centroid_node_T_per_level": cnode[i],
               "centroid_node_gci": MX.gci_capped(*cnode[i], floor),
               "fem_constk_cg_max_iterations": crec["cg_max_iterations"],
               "fem_constk_linear_rel_residual_max": crec["linear_rel_residual_max"]}
        for lv, sr in zip(ctx.levels, solves, strict=True):
            row[f"fem_cg_max_iterations_lv{lv}"] = sr["cg_max_iterations"]
            row[f"fem_linear_rel_residual_max_lv{lv}"] = sr["linear_rel_residual_max"]
            row[f"fem_cg_hit_maxiter_lv{lv}"] = sr["cg_hit_maxiter"]
            row[f"fem_dofs_lv{lv}"] = sr["dofs"]
        for lv, sr in zip(ctx.l2_levels, l2rec, strict=True):
            row[f"l2_linear_iters_lv{lv}"] = sr["linear_iters"]
            row[f"l2_linear_residual_lv{lv}"] = sr["linear_residual"]
            row[f"l2_cells_lv{lv}"] = sr["n_cells"]
        rows.append(row)
    return rows


# ------------------------------------------------------------------------------------------------ metrics
RECOMPUTE = [  # (metric, fn, pred, ref, params, where) exactly as the spec's recompute entries
    ("max_case_scaled_err", "max_scaled_abs_err", "T_fem", "T_ref", {"scale": "case_scale"},
     {"kind": "case", "is_finest": True}),
    ("max_abs_err_K", "max_abs_err", "T_fem", "T_ref", {}, {"kind": "case", "is_finest": True}),
    ("max_l2_consistency", "max_gci_consistency", None, None,
     {"pred_levels": ["fem_lv0", "fem_lv1", "fem_lv2"], "ref_levels": ["l2_lv1", "l2_lv2", "l2_lv3"], "floor": 0.001,
      "ref_gci_cap": 0.25}, {"kind": "crosscheck", "is_finest": True}),
    ("max_conservative_gci_K", "max_gci_capped", None, None,
     {"levels": ["fem_lv0", "fem_lv1", "fem_lv2"], "floor": 0.001}, {"is_finest": True}),
]
A3_PARAMS = RECOMPUTE[2][4]
A4_PARAMS = RECOMPUTE[3][4]


def _sel(rows, **where):
    return [r for r in rows if all(r.get(k) == v for k, v in where.items())]


def compute_metrics(rows: list[dict]) -> dict:
    out = {}
    for metric, fn, pred, ref, params, where in RECOMPUTE:
        out[metric] = MX.compute(fn, _sel(rows, **where), pred=pred, ref=ref, params=params)  # +inf passes through
    fin = _sel(rows, kind="case", is_finest=True)
    out["null_dT_const_k_scaled_err"] = MX.max_scaled_abs_err([r["dT_const_k"] for r in fin], [r["T_ref"] for r in fin],
                                                              [r["case_scale"] for r in fin])
    out["null_dT_const_k_abs_err_K"] = MX.max_abs_err([r["dT_const_k"] for r in fin], [r["T_ref"] for r in fin])
    return out


def secondary(rows: list[dict], solves: list[dict], cfg: dict) -> dict:
    fin = _sel(rows, is_finest=True)
    case, xc = _sel(fin, kind="case"), _sel(fin, kind="crosscheck")
    out = {"n_values": len(fin), "n_case_values": len(case), "n_crosscheck_values": len(xc),
           "n_oscillatory": sum(r["a4_branch"] == "oscillatory" for r in fin),
           "n_divergent": sum(r["a4_branch"] == "divergent" for r in fin),
           "n_non_asymptotic": sum(bool(r["non_asymptotic"]) for r in fin),
           "n_same_side": sum(bool(r["same_side"]) for r in xc),
           "n_case_err_above_gci": sum(abs(r["err_K"]) > r["gci"] for r in case),
           "max_case_snap_m": max((r["snap"]["distance_m"] for r in case if r["snap"]), default=0.0),
           "max_l2_gci_K": _gate_max(r["l2_gci"] for r in xc) if xc else NAN,
           "n_f5_fail": sum(not r["f5_ok"] for r in xc),
           "f5_fail_dies": [f"{r['layout']}/die{r['die']}" for r in xc if not r["f5_ok"]],
           "max_a3_ratio_const_k": _gate_max(r["a3_ratio_const_k"] for r in xc) if xc else NAN,
           "n_tj_max_node_moved": sum(r["tj_max_node_moves"] > 0 for r in xc),
           "max_cg_iterations_fem": max((s["cg_max_iterations"] for s in solves if s["solver"] == "fem"), default=0),
           "n_fem_solves_cg_over_flag": sum(s["cg_max_iterations"] > cfg["cg_flag"] for s in solves
                                            if s["solver"] == "fem"),
           "max_linear_rel_residual_fem": max((s["linear_rel_residual_max"] for s in solves if s["solver"] == "fem"),
                                              default=NAN)}
    for sub in ("fresh", "dev"):
        rr = _sel(xc, layout_set=sub)
        out[f"a3_{sub}"] = MX.compute("max_gci_consistency", rr, params=A3_PARAMS) if rr else NAN
        out[f"a4_{sub}_K"] = MX.compute("max_gci_capped", rr, params=A4_PARAMS) if rr else NAN
    out["a4_cases_K"] = MX.compute("max_gci_capped", case, params=A4_PARAMS) if case else NAN
    return out


def regression_guard(rows: list[dict], cfg: dict) -> dict:
    """Informational: this run's dev-problem values next to the dev study's at freeze (K1/K2 act as the guard)."""
    g = cfg["dev_regression_guard"]
    out = {}
    for prob, ref in g["per_problem"].items():
        rr = [r for r in rows if r.get("case") == prob] or [r for r in rows if r.get("layout") == prob]
        if not rr:
            continue
        now = {"A4_gci_K": _gate_max(r["gci"] for r in rr)}
        if rr[0]["kind"] == "case":
            now["A1_scaled_err"] = max(r["scaled_err"] for r in rr)
            now["A2_abs_err_K"] = max(abs(r["err_K"]) for r in rr)
        out[prob] = {"dev_study": ref, "this_run": now,
                     "max_abs_change": max(abs(now[k] - ref[k]) for k in now if k in ref)}
    return out


# ------------------------------------------------------------------------------------------------ checks
def gated_checks(ctx: Ctx, ck: Checks, rows: list[dict]) -> None:
    """The gated sanity checks after the solves (all but the reference and fingerprint checks, made earlier)."""
    cfg, sv = ctx.cfg, ctx.sv.items
    ck.add("node_persistence", ctx.node_ok and bool(rows), detail="every reported case point (not the Galerkin means) "
           "is a DOF at the same used coordinates and on the same grid lines at all three levels (stencils in the "
           f"rows); failures: {ctx.node_detail}")
    lo, hi = cfg["node_growth_factor"] * (1 - cfg["node_growth_tol"]), cfg["node_growth_factor"] * (1 + cfg["node_growth_tol"])
    allg = [v for _, gs in ctx.growth for v in gs]
    ok_g = bool(allg) and all(lo <= v <= hi for v in allg)
    ck.add("node_count_growth", ok_g, value=min(allg) if allg else None, threshold=lo,
           detail=f"node (scikit-fem DOF) and cell (L2) count ratio per level in [{lo:.2f}, {hi:.2f}]: "
                  + "; ".join(f"{t}: {[round(v, 3) for v in gs]}" for t, gs in ctx.growth))
    ck.add("constant_refinement_ratio", ctx.st.ratio_ok, detail="every level-l line kept and every level-l cell bisected "
           "in x, y and z, both solvers: " + "; ".join(ctx.st.ratio_detail))
    eb = [(s["tag"], s["energy_balance"]) for s in sv] + ctx.mms_ref_eb
    ebm = _gate_max(v for _, v in eb)
    ck.add("energy_balance", ebm <= cfg["energy_tol"], value=ebm, threshold=cfg["energy_tol"],
           detail=f"max |Q_out/Q_in - 1| over {len(sv)} solves (both solvers, constant-k included) and the manufactured "
                  f"case against the integrated reference outflow (64.648 W): "
                  f"{max(eb, key=lambda t: t[1] if math.isfinite(t[1]) else math.inf)}")
    pk = [(s["tag"], s["picard_residual_K"]) for s in sv if s["kT"]]
    pm = _gate_max(v for _, v in pk)
    ck.add("picard_converged", pm < cfg["picard_tol_K"], value=pm, threshold=cfg["picard_tol_K"],
           detail=f"last Picard max|dT| over {len(pk)} k(T) solves (both solvers)")
    opm = _gate_max(v for _, v in ctx.op)
    ck.add("operating_point", opm <= cfg["operating_point_tol_K"], value=opm, threshold=cfg["operating_point_tol_K"],
           detail="max over layouts of |scikit-fem level-0 hottest-die rise - 60 K| at the recorded equal power: "
                  + json.dumps({n: round(v, 4) for n, v in ctx.op}))
    fem = [s for s in sv if s["solver"] == "fem"]
    hit = [s["tag"] for s in fem if s["cg_hit_maxiter"]]
    ck.add("linear_solver_headroom", not hit and bool(fem), value=float(max(s["cg_max_iterations"] for s in fem)),
           threshold=float(ctx.fr["cg_maxiter"]),
           detail=f"no scikit-fem solve (every level, calibration and constant-k solve) hit the CG cap "
                  f"{ctx.fr['cg_maxiter']} (thermal_fem meta cg_hit_maxiter, T0222/I0110); hits: {hit}; solves above "
                  f"{cfg['cg_flag']}: {[s['tag'] for s in fem if s['cg_max_iterations'] > cfg['cg_flag']]}; max linear "
                  f"relative residual {max(s['linear_rel_residual_max'] for s in fem):.2e}")


def fingerprint_check(cfg: dict, ck: Checks, dev: list, fresh: list) -> None:
    fps = {n: lay.fingerprint() for n, lay in dev + fresh}
    ok = all(fps.get(n) == f for n, f in cfg["dev_fingerprints"].items())
    fam = sorted(lay.family for _, lay in fresh) == sorted(FAMILIES)
    distinct = len(set(fps.values())) == len(dev) + len(fresh) == 5
    ck.add("layout_fingerprints", ok and fam and distinct, detail=json.dumps(
        {n: {"fingerprint": fps[n], "family": lay.family, "dies_per_switch": lay.dies_per_switch, "dies": len(lay.dies)}
         for n, lay in dev + fresh}))


# ------------------------------------------------------------------------------------------------ drivers
def all_rows(ctx: Ctx, ser: dict, mms: dict, layouts: list) -> list[dict]:
    rows = []
    for name, c in ser["cases"].items():
        log(f"case {name}")
        rows += run_box_case(ctx, name, c, [r for r in ser["rows"] if r["case"] == name])
    log("case mms")
    rows += run_mms(ctx, mms)
    for name, lay, lset in layouts:
        log(f"layout {name} ({lset})")
        rows += run_layout(ctx, name, lay, lset)
    return rows


def _f1(cfg: dict, ck: Checks) -> tuple[dict, dict]:
    ser, mms = E6.load_refs(cfg, ck)  # reference_sha256, before any solve
    if not ck.items[-1]["passed"]:
        raise RuntimeError("reference sha256 mismatch: refusing to solve")
    E6.series_checks(ser, ck)  # series_cases_match_frozen_parameters, series_converged, case3_printed_values, N-layer
    E6.mms_checks(mms, cfg, ck)  # mms_numeric_check
    rule_checks(cfg, ck)
    if not ck.items[-1]["passed"]:
        raise RuntimeError("fem_rule is not the frozen configuration: refusing to solve")
    return ser, mms


def smoke(rows_out: str) -> int:
    t0 = time.time()
    cfg = load_config()
    ck = Checks()
    ser, mms = _f1(cfg, ck)
    fr = smoke_fem_rule(cfg)
    for k, v in cfg["smoke_l2_rule"].items():  # coarsened copy of the L2's frozen rule, smoke only
        setattr(TL, k, v)
    ctx = Ctx(cfg, fr, smoke=True)
    dev = E6.dev_layouts(cfg)
    fresh = E6.fresh_layouts(int(cfg["smoke_fresh_dev_seed"]))  # non-sealed dev seed: the 'fresh' rule exercised
    fingerprint_check(cfg, ck, dev, fresh)
    layouts = [(n, lay, "dev") for n, lay in dev] + [(n, lay, "fresh") for n, lay in fresh]
    rows = all_rows(ctx, ser, mms, layouts)
    gated_checks(ctx, ck, rows)
    met = compute_metrics(rows)
    sec = secondary(rows, ctx.sv.items, cfg)
    doc = {"schema": "mfos.rows/1", "rows": rows,
           "meta": {"mode": "smoke (coarsened copies of both frozen rules, dev seeds only; NOT evidence)",
                    "smoke_fem_rule": fr, "smoke_l2_rule": cfg["smoke_l2_rule"],
                    "smoke_fresh_dev_seed": cfg["smoke_fresh_dev_seed"], "metrics": met, "secondary": sec,
                    "regression_guard_vs_dev_study (smoke grids: not comparable)": regression_guard(rows, cfg),
                    "checks": ck.items, "info": ck.info, "solves": ctx.sv.items,
                    "wall_s": round(time.time() - t0, 1), "peak_rss_gb": round(rss_gb(), 3), "platform": sys.platform,
                    "fem_rule_sha256": hashlib.sha256((ROOT / FROZEN_CONFIG_PATH).read_bytes()).hexdigest()}}
    Path(rows_out).parent.mkdir(parents=True, exist_ok=True)
    Path(rows_out).write_text(json.dumps(doc, indent=1, default=float) + "\n")
    log(f"wrote {rows_out}: {len(rows)} rows; metrics {met}; secondary {json.dumps(sec, default=str)}")
    integrity = [c for c in ck.items if c["name"] in ("reference_sha256", "fem_rule_frozen", "layout_fingerprints",
                                                       "series_converged", "case3_printed_values",
                                                       "nlayer_reduces_to_two_layer", "mms_numeric_check")]
    return 0 if all(c["passed"] for c in integrity) else 1


def full() -> int:
    from mfos.evidence import ExperimentRun

    with ExperimentRun(experiment_id=EID) as run:
        cfg = run.config
        if run.seed is None:
            raise RuntimeError("E009 needs the sealed seed (spec sealed_seed: true)")
        if run.seed in (cfg["dev_seed"], cfg["smoke_fresh_dev_seed"]):
            raise RuntimeError("the sealed seed equals a development seed")
        ck = Checks()
        ser, mms = _f1(cfg, ck)  # F1 and the frozen-rule check, all before the first solve
        ctx = Ctx(cfg, cfg["fem_rule"], smoke=False)
        dev = E6.dev_layouts(cfg)
        fresh = E6.fresh_layouts(run.seed)
        fingerprint_check(cfg, ck, dev, fresh)
        layouts = [(n, lay, "dev") for n, lay in dev] + [(n, lay, "fresh") for n, lay in fresh]
        rows = all_rows(ctx, ser, mms, layouts)
        run.rows(rows)
        gated_checks(ctx, ck, rows)
        met = compute_metrics(rows)
        units = {"max_case_scaled_err": "", "max_abs_err_K": "K", "max_l2_consistency": "",
                 "max_conservative_gci_K": "K", "null_dT_const_k_scaled_err": "", "null_dT_const_k_abs_err_K": "K"}
        for k, u in units.items():  # deterministic maxima over the full measured set: point values, level 0.0
            run.metric(k, met[k], level=0.0, n=len(rows), unit=u)
        sec = secondary(rows, ctx.sv.items, cfg)
        for k in ("a3_fresh", "a3_dev", "max_a3_ratio_const_k"):
            run.metric(k, sec[k], level=0.0)
        for k in ("a4_fresh_K", "a4_dev_K", "a4_cases_K", "max_l2_gci_K"):
            run.metric(k, sec[k], level=0.0, unit="K")
        for k, name in (("n_f5_fail", "n_f5_fail_dies"), ("n_oscillatory", "n_oscillatory_values"),
                        ("n_non_asymptotic", "n_non_asymptotic_values"), ("n_same_side", "n_same_side_dies"),
                        ("n_fem_solves_cg_over_flag", "n_fem_solves_cg_over_300")):
            run.metric(name, sec[k], level=0.0)
        for c in ck.items:
            run.sanity(c["name"], c["passed"], value=c["value"] if isinstance(c["value"], (int, float)) else None,
                       threshold=c["threshold"] if isinstance(c["threshold"], (int, float)) else None,
                       detail=str(c["detail"])[:4000])
        xc = _sel(rows, kind="crosscheck")
        run.domain(case=sorted({r["case"] for r in rows if r["kind"] == "case"}),
                   family=sorted({r["family"] for r in xc}), dies_per_switch=sorted({r["dies_per_switch"] for r in xc}),
                   layout_fingerprint=sorted({r["fingerprint"] for r in xc}), coolant_K=[cfg["coolant_K"]],
                   h_W_m2K=[cfg["h_W_m2K"]], target_rise_K=[cfg["target_rise_K"]])
        run.notes = (f"secondary {json.dumps(sec, default=str)}; regression guard vs dev study "
                     f"{json.dumps(regression_guard(rows, cfg), default=str)[:3000]}; solves "
                     f"{json.dumps(ctx.sv.items, default=str)[:20000]}; reference info "
                     f"{json.dumps(ck.info, default=str)[:3000]}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--rows-out", default=None)
    a = ap.parse_args(argv)
    os.chdir(ROOT)
    if a.smoke:
        if not a.rows_out:
            ap.error("--smoke needs --rows-out PATH")
        return smoke(a.rows_out)
    return full()


if __name__ == "__main__":
    sys.exit(main())
