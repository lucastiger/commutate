"""E006 runner: thermal L2 (finite volumes, k(T) by Picard) against frozen references and scikit-fem (O006 A1-A4).

Design: experiments/drafts/E006.yaml; rationale: research/notes/o006-e006-design.md.  SI units, kelvin, float64.

Modes
  (default)                    the registered run, through mfos.evidence.ExperimentRun (config from MFOS_SPEC_JSON)
  --refcheck [--out PATH]      F1's reference-only checks at full resolution, no L2 involved; writes
                               {checks: [{name, value, threshold, passed}], info: [...], all_passed} (default
                               research/e006/refcheck.json).  Never creates an evidence run.
  --smoke --rows-out PATH      pipeline check: every case and the two development layouts on a coarsened copy of the
                               frozen rule (smoke only: level-0 lateral and edge cells x4, one z cell per layer; the
                               ratio 2 between levels is kept), development seed only; writes only the rows.  Never
                               creates an evidence run and never touches the sealed seed.

Every reported value carries its three grid values (frozen rule levels 0, 1, 2, coarsest first) in f_lv0, f_lv1,
f_lv2; the evaluator recomputes every GCI from them (mfos.metrics).  gci / a4_branch columns are informational and use
the same function (mfos.metrics.gci_capped, floor 1e-3 K).  A diverging sequence gives +inf; it is never caught or
clipped.  References: GCI form and safety factors, Roache (1998) ch. 5 (via mfos.metrics); Muzychka, Culham &
Yovanovich, J. Electron. Packag. 125(2):178 (2003) and the N-layer series (experiments/runners/e006_series.py);
manufactured solution (experiments/runners/e006_mms.py; Salari & Knupp, SAND2000-1444).
"""
from __future__ import annotations

import argparse
import gc
import hashlib
import json
import math
import os
import resource
import sys
import time
from dataclasses import replace
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "experiments" / "runners"), str(ROOT / "tools" / "mfos"), str(ROOT / "src")]

import e006_mms as MMS  # noqa: E402
import e006_series as SER  # noqa: E402
import e006_skfem_q2 as Q2  # noqa: E402
import yaml  # noqa: E402
from mfos import metrics as MX  # noqa: E402
from shapely.geometry import box as sbox  # noqa: E402
from shapely.ops import unary_union  # noqa: E402

from moduleforge.generate.halfbridge import FAMILIES, generate_layouts  # noqa: E402
from moduleforge.geometry.layout import Die, Layout, Trace  # noqa: E402
from moduleforge.solvers import thermal_fem as FEM  # noqa: E402
from moduleforge.solvers import thermal_layout as TL  # noqa: E402
from moduleforge.solvers.thermal_fv import solve_steady  # noqa: E402

EID = "E006"
NAN = float("nan")


# ------------------------------------------------------------------------------------------------ config / helpers

def _gate_max(values) -> float:
    """Maximum for a sanity gate; +inf if any value is NaN or infinite, so the gate fails instead of Python's max()
    silently skipping a NaN that is not the first entry (review T0197 of T0196)."""
    vals = [float(v) for v in values]
    if not vals or not all(math.isfinite(v) for v in vals):
        return math.inf
    return max(vals)

def load_config() -> dict:
    env = os.environ.get("MFOS_SPEC_JSON")
    if env:
        return json.loads(env)["config"]
    for p in (ROOT / "experiments" / "specs" / "E006.yaml", ROOT / "experiments" / "drafts" / "E006.yaml"):
        if p.exists():
            return yaml.safe_load(p.read_text())["config"]
    raise FileNotFoundError("no E006 spec")


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def rss_gb() -> float:
    r = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return r / 1e9 if sys.platform == "darwin" else r / 1e6


def canon_sha(obj, allow_nan: bool = True) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":"), allow_nan=allow_nan).encode()).hexdigest()


def a4(f0: float, f1: float, f2: float, floor: float) -> dict:
    """A4 estimator (mfos.metrics.gci_capped) plus its branch, observed order and steps, as the rows report them."""
    d1, d2 = f1 - f0, f2 - f1
    e1 = 0.0 if abs(d1) < floor else d1
    e2 = 0.0 if abs(d2) < floor else d2
    if e1 == 0.0 and e2 == 0.0:
        br, rho = "exact", NAN
    elif e1 == 0.0:
        br, rho = "divergent", math.inf
    else:
        rho = e2 / e1
        br = ("divergent" if abs(rho) >= 1 else "oscillatory" if rho < 0 else "fast" if rho < 0.25 else "monotone")
    p_obs = math.log2(1.0 / rho) if (isinstance(rho, float) and 0 < rho < math.inf) else None
    g = MX.gci_capped(f0, f1, f2, floor)
    return {"gci": g, "a4_branch": br, "p_obs": p_obs, "d1": d1, "d2": d2,
            "non_asymptotic": p_obs is None or not (0.5 <= p_obs <= 2.0)}


def direction(f1: float, f2: float) -> str:
    return "from_above" if f2 < f1 else "from_below"


class Checks:
    def __init__(self):
        self.items: list[dict] = []
        self.info: list[dict] = []

    def add(self, name, passed, value=None, threshold=None, detail=""):
        self.items.append({"name": name, "passed": bool(passed), "value": value, "threshold": threshold,
                           "detail": detail})
        log(f"[{'PASS' if passed else 'FAIL'}] {name}: value={value} threshold={threshold} {detail}")

    def note(self, name, value=None, detail=""):
        self.info.append({"name": name, "value": value, "detail": detail})
        log(f"[INFO] {name}: {value} {detail}")


# ------------------------------------------------------------------------------------------------ references
def load_refs(cfg: dict, ck: Checks) -> tuple[dict, dict]:
    ser = json.loads((ROOT / cfg["series_ref_path"]).read_text())
    mms = json.loads((ROOT / cfg["mms_ref_path"]).read_text())
    s_sha = canon_sha(ser["payload"], allow_nan=False)
    m_sha = canon_sha(mms["payload"])
    ok = (s_sha == cfg["series_sha256"] == ser["sha256"]) and (m_sha == cfg["mms_sha256"] == mms["sha256_payload"])
    ck.add("reference_sha256", ok, detail=f"series {s_sha[:12]} (config {cfg['series_sha256'][:12]}), "
                                          f"mms {m_sha[:12]} (config {cfg['mms_sha256'][:12]}); checked before any solve")
    return ser["payload"], mms


def series_case(name: str, c: dict) -> SER.Case:
    """The frozen case rebuilt from the JSON's own parameters (not from a later stack.py)."""
    layers = tuple((la["name"], la["t_m"], la["k_W_mK"]) for la in c["layers_bottom_up"])
    srcs = tuple(SER.Source(s["name"], s["xc_m"], s["yc_m"], s["c_m"], s["d_m"], s["Q_W"]) for s in c["sources"])
    return SER.Case(name, c["a_m"], c["b_m"], layers, c["h_W_m2K"], c["Tf_K"], srcs,
                    kernel="nlayer" if len(layers) > 2 else "M03")


def series_checks(ser: dict, ck: Checks) -> None:
    """F1: series converged (doubling every knob, frozen values reproduced to < 1e-7 of the rise), the paper's printed
    Case 3 values at 50 terms, the N-layer series reducing to the two-layer one."""
    sc = SER.Checks()
    refs = {}
    for name in ser["cases"]:
        refs[name] = {"rows": [{"source": r["source"], "point": r["point"], "x": r["x_m"], "y": r["y_m"], "T": r["T_K"]}
                               for r in ser["rows"] if r["case"] == name]}
    frozen = {name: series_case(name, c) for name, c in ser["cases"].items()}
    built = {c.name: c for c in SER.all_cases()}
    same = all(frozen[n].layers == built[n].layers and frozen[n].sources == built[n].sources
               and frozen[n].h == built[n].h and frozen[n].Tf == built[n].Tf for n in frozen)
    ck.add("series_cases_match_frozen_parameters", same, detail="e006_series cases == series_values.json parameters")
    acc = SER.Acc(**{k: v for k, v in ser["accuracy"].items()})
    SER.check_convergence(sc, refs, acc)
    SER.check_paper(sc)
    SER.check_nlayer_equals_two_layer(sc, acc)
    conv = [i for i in sc.items if i[0].startswith("convergence_doubling_")]
    ck.add("series_converged", all(i[1] for i in conv), detail="; ".join(f"{i[0]}: {i[2]}" for i in conv))
    paper = [i for i in sc.items if i[3] and i[0].startswith("paper50_")]
    ck.add("case3_printed_values", bool(paper) and all(i[1] for i in paper), detail="; ".join(i[2] for i in paper))
    for i in sc.items:
        if not i[3]:
            ck.note(i[0], i[1], i[2])
    two = [i for i in sc.items if i[0] == "nlayer_equals_two_layer"]
    ck.add("nlayer_reduces_to_two_layer", bool(two) and two[0][1], detail=two[0][2] if two else "missing")


def mms_checks(mms: dict, cfg: dict, ck: Checks) -> None:
    src = (ROOT / "experiments" / "runners" / "e006_mms.py").read_bytes()
    same_runner = hashlib.sha256(src).hexdigest() == mms["provenance"]["runner_sha256"]
    ok, res, fs, bal, _ = MMS.selfcheck(verbose=False)
    kv = mms["payload"]["k_variation"]["ceramic"]
    ratio = kv["k_max"] / kv["k_min"] - 1.0
    ok_k = ratio >= cfg["mms_kvar_min"]
    ck.add("mms_numeric_check", ok and same_runner and ok_k, value=float(ratio), threshold=cfg["mms_kvar_min"],
           detail=f"e006_mms --selfcheck all gates {'pass' if ok else 'FAIL'} ("
                  + ", ".join(f"{k}={'ok' if v['passed'] else 'FAIL'}" for k, v in res.items())
                  + f"); generator sha256 matches the frozen file: {same_runner}; ceramic k_max/k_min - 1 = "
                    f"{ratio:.4f} >= {cfg['mms_kvar_min']} (k_max-normalised {(kv['k_max'] - kv['k_min']) / kv['k_max']:.4f})")


# ------------------------------------------------------------------------------------------------ scikit-fem F1 checks
def _f1_lines(case: SER.Case, k: dict, level: int, quarter: bool):
    """scikit-fem's own graded tensor lines for the F1 box solves (e006_skfem_q2.graded_lines; independent of the FV
    grid builder): lateral cells s0 * grow**k at every source edge up to hmax (hmax_far beyond margin_m of every edge,
    when set); z: every layer nz cells (default 1), the top layer graded toward the heated face when z_s0_m is set;
    level l bisects every level-0 cell l times (r = 2).  Returns x, y, z, layer interfaces, sources (x0, y0, x1, y1, P)
    in the solved domain (quarter = the centred-source quarter [a/2, a] x [b/2, b], mapped to [0, a/2] x [0, b/2])."""
    a, b = (case.a / 2, case.b / 2) if quarter else (case.a, case.b)
    if quarter:
        srcs = [(0.0, 0.0, s.c / 2, s.d / 2, s.Q / 4) for s in case.sources]
    else:
        srcs = [(s.x1, s.y1, s.x2, s.y2, s.Q) for s in case.sources]
    ex = sorted({v for s in srcs for v in (s[0], s[2])} - {0.0, a})
    ey = sorted({v for s in srcs for v in (s[1], s[3])} - {0.0, b})

    def axis(e, length):
        m = k.get("margin_m")
        pts = sorted({0.0, length, *e, *([v + d for v in e for d in (-m, m) if 0.0 < v + d < length] if m else [])})
        pts = np.array([v for i, v in enumerate(pts) if i == 0 or v - pts[i - 1] > 1e-12])
        mid = 0.5 * (pts[1:] + pts[:-1])
        far = np.array([min(abs(c - v) for v in e) > m for c in mid]) if m else np.zeros(mid.size, bool)
        return Q2.graded_lines(pts, e, k["s0_m"], k["grow"], np.where(far, k.get("hmax_far_m", 0.0), k["hmax_m"]),
                               level)

    zb = np.concatenate([[0.0], np.cumsum([t for _, t, _ in case.layers])])
    zs = [zb[:1]]
    for j, (name, _t, _) in enumerate(case.layers):
        if "z_s0_m" in k and j == len(case.layers) - 1:  # top layer graded toward the heated face
            seg = Q2.graded_lines(np.array([zb[j], zb[j + 1]]), [zb[j + 1]], k["z_s0_m"], k["grow"], k["z_hmax_m"],
                                  level)
        else:
            n = int(k["nz"].get(name, 1)) * 2**level
            seg = np.linspace(zb[j], zb[j + 1], n + 1)
        zs.append(seg[1:])
    return axis(ex, a), axis(ey, b), np.concatenate(zs), zb, srcs


def _bisects(coarse: list[np.ndarray], fine: list[np.ndarray]) -> bool:
    """Every coarse line is kept and every coarse cell is split into exactly two equal cells (ratio r = 2)."""
    return all(len(f) == 2 * len(c) - 1 and np.allclose(f[::2], c, rtol=0, atol=1e-12)
               and np.allclose(f[1::2], 0.5 * (c[:-1] + c[1:]), rtol=0, atol=1e-12)
               for c, f in zip(coarse, fine, strict=True))


def skfem_vs_series(case: SER.Case, ref_rows: list[dict], k: dict, quarter: bool, max_dofs: int,
                    rtol: float = Q2.LINEAR_RTOL, accept: float = 1e-9) -> dict:
    """scikit-fem Q2 box solve (e006_skfem_q2) at levels 0, 1, 2 of its own graded rule (r = 2, z refined too); per
    reported point the three values, the A4 GCI (mfos.metrics.gci_capped, floor 1e-3 K) and the finest value's error
    against the series.  Source means: exact Galerkin integral of the Q2 field over the source faces / area; points:
    the Q2 field evaluated at the point."""
    vals = {i: [] for i in range(len(ref_rows))}
    meta, lines = [], []
    srcidx = {s.name: i for i, s in enumerate(case.sources)}
    pts = []
    for row in ref_rows:
        x, y = row["x"], row["y"]
        if quarter:
            x, y = abs(x - case.a / 2), abs(y - case.b / 2)
        pts.append((x, y))
    for lv in (0, 1, 2):
        x, y, z, zb, srcs = _f1_lines(case, k, lv, quarter)
        lines.append([x, y, z])
        n_est = (2 * len(x) - 1) * (2 * len(y) - 1) * (2 * len(z) - 1)
        if n_est > max_dofs:
            raise MemoryError(f"scikit-fem Q2 level {lv}: {n_est} DOF > max {max_dofs} (memory rule)")
        r = Q2.solve_box_q2(x, y, z, zb, [kk for _, _, kk in case.layers], case.h, case.Tf, srcs, np.array(pts),
                            rtol=rtol, accept=accept)
        meta.append({"level": lv, "dofs": int(r.dofs), "elements": int(r.elements), "cg_iters": r.cg_iters,
                     "rel_residual": r.rel_residual, "wall_s": round(r.wall_s, 2),
                     "energy_balance": r.energy_balance, "rss_gb": round(rss_gb(), 2)})
        log(f"  scikit-fem Q2 {case.name} level {lv}: {r.dofs} DOF, {r.wall_s:.1f} s, balance {r.energy_balance:.1e}, "
            f"peak RSS {rss_gb():.2f} GB")
        for i, row in enumerate(ref_rows):
            vals[i].append(float(r.mean[srcidx[row["source"]]]) if row["point"] == "mean" else float(r.point[i]))
        del r
        gc.collect()
    out = []
    for i, row in enumerate(ref_rows):
        f = vals[i]
        br = a4(f[0], f[1], f[2], 1e-3)
        out.append({"source": row["source"], "point": row["point"], "T_ref": row["T"], "fe": f, "gci": br["gci"],
                    "branch": br["a4_branch"], "err": f[2] - row["T"]})
    return {"rows": out, "levels": meta, "max_err": max(abs(o["err"]) for o in out),
            "max_gci": max(o["gci"] for o in out), "max_energy_balance": max(m["energy_balance"] for m in meta),
            "ratio_ok": _bisects(lines[0], lines[1]) and _bisects(lines[1], lines[2]),
            "gci_bounds_err": all(o["gci"] >= abs(o["err"]) for o in out)}


def uniform_stack_case(ser: dict, cfg: dict) -> tuple[SER.Case, list[dict]]:
    """F1's N-layer check case: the frozen N-layer stack (layers, h, Tf of nlayer_dbc), laterally uniform, one
    centred die-sized source on a square box (quarter symmetry for scikit-fem), power set from the series alone so
    that the maximum rise is cfg target; reference values from e006_series (the code under F1 test)."""
    c = ser["cases"]["nlayer_dbc"]
    u = cfg["skfem_uniform"]
    base = series_case("nlayer_uniform", c)
    a = u["box_m"]
    s1 = SER.Source("die", a / 2, a / 2, u["die_m"], u["die_m"], 1.0)
    case1 = replace(base, a=a, b=a, sources=(s1,), kernel="nlayer")
    rise1 = SER.Field(case1).T_point(a / 2, a / 2) - case1.Tf
    P = round(u["target_rise_K"] / rise1, 1)
    case = replace(case1, sources=(replace(s1, Q=P),))
    fld = SER.Field(case)
    s = case.sources[0]
    xm, ym, Tm, _ = SER.maximize_on_source(fld, s)
    rows = [{"source": "die", "point": "centroid", "x": s.xc, "y": s.yc, "T": fld.T_point(s.xc, s.yc)},
            {"source": "die", "point": "mean", "x": s.xc, "y": s.yc, "T": float(fld.T([SER.Target.patch(s)])[0])},
            {"source": "die", "point": "max", "x": xm, "y": ym, "T": Tm}]
    return case, rows


def offcentre_stack_case(ser: dict, cfg: dict) -> tuple[SER.Case, list[dict], dict]:
    """F1's off-centre N-layer check case (review T0194 of T0165): the frozen N-layer stack (layers, h, Tf of
    nlayer_dbc), laterally uniform, on a non-square box with one rectangular die-sized source off-centre in x AND y,
    so the series' odd cosine modes (and the a != b, c != d terms) carry the answer.  Power set from the series alone
    so that the source's maximum rises cfg target.  Reported points: the source centroid, mean and maximum, and the
    centroid's mirror images about x = a/2 and y = b/2 (off-source points).  Also returns the series' odd-mode signal
    at the centroid, [T(x, y) - T(a - x, y)] / 2 (odd in x) and [T(x, y) - T(x, b - y)] / 2 (odd in y), which vanishes
    identically for a centred source, and the series' own doubling check on these points (every Acc knob doubled)."""
    c = ser["cases"]["nlayer_dbc"]
    u = cfg["skfem_offcentre"]
    base = series_case("nlayer_offcentre", c)
    (a, b), (cw, dw), (xc, yc) = u["box_m"], u["die_m"], u["centre_m"]
    s1 = SER.Source("die", xc, yc, cw, dw, 1.0)
    case1 = replace(base, a=a, b=b, sources=(s1,), kernel="nlayer")
    _, _, T1, _ = SER.maximize_on_source(SER.Field(case1), s1)
    P = round(u["target_rise_K"] / (T1 - case1.Tf), 1)
    case = replace(case1, sources=(replace(s1, Q=P),))
    s = case.sources[0]

    def points(fld, xm=None, ym=None):
        if xm is None:
            xm, ym, Tm, _ = SER.maximize_on_source(fld, s)
        else:
            Tm = fld.T_point(xm, ym)
        return [{"source": "die", "point": "centroid", "x": s.xc, "y": s.yc, "T": fld.T_point(s.xc, s.yc)},
                {"source": "die", "point": "mean", "x": s.xc, "y": s.yc, "T": float(fld.T([SER.Target.patch(s)])[0])},
                {"source": "die", "point": "max", "x": xm, "y": ym, "T": Tm},
                {"source": "die", "point": "centroid_xmirror", "x": a - s.xc, "y": s.yc,
                 "T": fld.T_point(a - s.xc, s.yc)},
                {"source": "die", "point": "centroid_ymirror", "x": s.xc, "y": b - s.yc,
                 "T": fld.T_point(s.xc, b - s.yc)}]

    fld = SER.Field(case)
    rows = points(fld)
    dbl = points(SER.Field(case, SER.Acc().doubled("all")), rows[2]["x"], rows[2]["y"])
    rise = rows[2]["T"] - case.Tf
    conv = max(abs(p["T"] - q["T"]) for p, q in zip(rows, dbl, strict=True)) / rise
    info = {"power_W": P, "rise_K": rise, "series_doubling_rel": conv,
            "odd_x_K": 0.5 * (rows[0]["T"] - rows[3]["T"]), "odd_y_K": 0.5 * (rows[0]["T"] - rows[4]["T"]),
            "max_offset_m": [rows[2]["x"] - s.xc, rows[2]["y"] - s.yc]}
    return case, rows, info


def skfem_checks(ser: dict, cfg: dict, ck: Checks) -> None:
    """F1's two scikit-fem agreement checks, each with scikit-fem's own A4 GCI <= 0.01 K, on the Q2 box solver
    (e006_skfem_q2: ElementHex2, exact Galerkin source means), preceded by that solver's own exactness self-test;
    Case 1a/1b as INFO only."""
    st = Q2.selftest()
    ok = (st["q2_point_eval_max_err"] <= 1e-9 and st["q2_1d_exact_max_err_K"] <= 1e-6
          and st["q2_1d_energy_balance"] <= cfg["energy_tol"])
    ck.add("skfem_q2_selftest", ok, value=st["q2_1d_exact_max_err_K"], threshold=1e-6,
           detail=f"point evaluation of a triquadratic field max err {st['q2_point_eval_max_err']:.1e} (<= 1e-9); "
                  f"two-layer 1D conduction exact to {st['q2_1d_exact_max_err_K']:.1e} K (<= 1e-6 K); energy balance "
                  f"{st['q2_1d_energy_balance']:.1e}")
    c2 = series_case("case2", ser["cases"]["case2"])
    r2 = [{"source": r["source"], "point": r["point"], "x": r["x_m"], "y": r["y_m"], "T": r["T_K"]}
          for r in ser["rows"] if r["case"] == "case2"]
    res = skfem_vs_series(c2, r2, cfg["skfem_case2"], False, cfg["skfem_max_dofs"])
    tab = "; ".join(f"{o['source']}.{o['point']} fe {o['fe'][0]:.5f}/{o['fe'][1]:.5f}/{o['fe'][2]:.5f} ref "
                    f"{o['T_ref']:.5f} err {o['err']:+.5f} gci {o['gci']:.5f} ({o['branch']})" for o in res["rows"])
    ck.add("case2_skfem_gci", res["max_gci"] <= cfg["skfem_f1_gci_K"], value=res["max_gci"],
           threshold=cfg["skfem_f1_gci_K"],
           detail=f"scikit-fem Q2 own A4 GCI (gci_capped, floor 1e-3 K), max over 12 values; ratio 2 between levels: "
                  f"{res['ratio_ok']}; GCI >= |err| on every value: {res['gci_bounds_err']}; levels {res['levels']}")
    ck.add("case2_vs_skfem", res["max_err"] <= cfg["skfem_f1_agree_K"], value=res["max_err"],
           threshold=cfg["skfem_f1_agree_K"], detail="max |T_fe(level 2) - T_series|; levels 0/1/2: " + tab)
    ck.add("case2_skfem_energy_and_ratio", res["max_energy_balance"] <= cfg["energy_tol"] and res["ratio_ok"],
           value=res["max_energy_balance"], threshold=cfg["energy_tol"],
           detail=f"max |Q_out/Q_in - 1| over the three solves; constant ratio 2: {res['ratio_ok']}")
    case, rows = uniform_stack_case(ser, cfg)
    u = cfg["skfem_uniform"]
    rise = max(r["T"] for r in rows) - case.Tf
    ck.add("nlayer_uniform_rise_in_band", 60.0 <= rise <= 110.0, value=rise, threshold=[60.0, 110.0],
           detail=f"centred {u['die_m'] * 1e3:.2f} mm die, {case.sources[0].Q} W on {u['box_m'] * 1e3:.1f} mm box")
    res = skfem_vs_series(case, rows, u, True, cfg["skfem_max_dofs"])
    ck.add("nlayer_uniform_skfem_gci", res["max_gci"] <= cfg["skfem_f1_gci_K"], value=res["max_gci"],
           threshold=cfg["skfem_f1_gci_K"],
           detail=f"quarter-symmetric scikit-fem Q2, own A4 GCI; ratio 2 between levels: {res['ratio_ok']}; GCI >= "
                  f"|err| on every value: {res['gci_bounds_err']}; levels {res['levels']}")
    ck.add("nlayer_uniform_vs_skfem", res["max_err"] <= cfg["skfem_f1_agree_K"], value=res["max_err"],
           threshold=cfg["skfem_f1_agree_K"], detail="; ".join(
               f"{o['point']} ref {o['T_ref']:.5f} fe {o['fe'][0]:.5f}/{o['fe'][1]:.5f}/{o['fe'][2]:.5f} err "
               f"{o['err']:+.5f} gci {o['gci']:.5f} ({o['branch']})" for o in res["rows"]))
    ck.add("nlayer_uniform_skfem_energy_and_ratio", res["max_energy_balance"] <= cfg["energy_tol"] and res["ratio_ok"],
           value=res["max_energy_balance"], threshold=cfg["energy_tol"],
           detail=f"max |Q_out/Q_in - 1| over the three solves; constant ratio 2: {res['ratio_ok']}")
    # off-centre source (review T0194): the odd modes of the N-layer kernel against a full-domain scikit-fem solve
    case, rows, info = offcentre_stack_case(ser, cfg)
    u = cfg["skfem_offcentre"]
    ck.add("nlayer_offcentre_rise_in_band", 60.0 <= info["rise_K"] <= 110.0, value=info["rise_K"],
           threshold=[60.0, 110.0],
           detail=f"{u['die_m'][0] * 1e3:.2f} x {u['die_m'][1] * 1e3:.2f} mm die centred at ({u['centre_m'][0] * 1e3:.2f}, "
                  f"{u['centre_m'][1] * 1e3:.2f}) mm, {info['power_W']} W on a {u['box_m'][0] * 1e3:.1f} x "
                  f"{u['box_m'][1] * 1e3:.1f} mm box; series odd-mode signal at the centroid: x {info['odd_x_K']:+.4f} K,"
                  f" y {info['odd_y_K']:+.4f} K (zero for a centred source); maximum offset from the centroid "
                  f"({info['max_offset_m'][0] * 1e3:+.3f}, {info['max_offset_m'][1] * 1e3:+.3f}) mm")
    ck.add("nlayer_offcentre_series_converged", info["series_doubling_rel"] < 1e-7, value=info["series_doubling_rel"],
           threshold=1e-7, detail="max |T(all Acc knobs doubled) - T(default)| / rise over the five points")
    res = skfem_vs_series(case, rows, u, False, cfg["skfem_max_dofs"])
    ck.add("nlayer_offcentre_skfem_gci", res["max_gci"] <= cfg["skfem_f1_gci_K"], value=res["max_gci"],
           threshold=cfg["skfem_f1_gci_K"],
           detail=f"full-domain scikit-fem Q2 (no symmetry), own A4 GCI; ratio 2 between levels: {res['ratio_ok']}; "
                  f"GCI >= |err| on every value: {res['gci_bounds_err']}; levels {res['levels']}")
    ck.add("nlayer_offcentre_vs_skfem", res["max_err"] <= cfg["skfem_f1_agree_K"], value=res["max_err"],
           threshold=cfg["skfem_f1_agree_K"], detail="; ".join(
               f"{o['point']} ref {o['T_ref']:.5f} fe {o['fe'][0]:.5f}/{o['fe'][1]:.5f}/{o['fe'][2]:.5f} err "
               f"{o['err']:+.5f} gci {o['gci']:.5f} ({o['branch']})" for o in res["rows"]))
    ck.add("nlayer_offcentre_skfem_energy_and_ratio",
           res["max_energy_balance"] <= cfg["energy_tol"] and res["ratio_ok"], value=res["max_energy_balance"],
           threshold=cfg["energy_tol"],
           detail=f"max |Q_out/Q_in - 1| over the three solves; constant ratio 2: {res['ratio_ok']}")
    for name in ("case1a", "case1b"):  # INFO only (F1): coarse scikit-fem Q2 on the 300 mm plates
        c = series_case(name, ser["cases"][name])
        rr = [{"source": r["source"], "point": r["point"], "x": r["x_m"], "y": r["y_m"], "T": r["T_K"]}
              for r in ser["rows"] if r["case"] == name]
        # INFO only: the weakly cooled 300 mm plates (h = 10 W/(m2 K)) are ill-conditioned; CG stops at 1e-8 and a
        # true relative residual <= 1e-6 is accepted (reported per level with the energy balance)
        res = skfem_vs_series(c, rr, cfg["skfem_case1"], False, cfg["skfem_max_dofs"], rtol=1e-8, accept=1e-6)
        ck.note(f"{name}_vs_skfem_info", res["max_err"], f"max |err| (K) of scikit-fem Q2 level 2; max GCI "
                f"{res['max_gci']:.4f} K; levels {res['levels']}")


def reference_checks(ser: dict, mms: dict, cfg: dict, ck: Checks, with_skfem: bool = True) -> None:
    series_checks(ser, ck)
    mms_checks(mms, cfg, ck)
    if with_skfem:
        skfem_checks(ser, cfg, ck)


# ------------------------------------------------------------------------------------------------ L2 on the cases
class Stats:
    def __init__(self):
        self.energy, self.picard, self.ratio_ok, self.ratio_detail, self.solves = [], [], True, [], []

    def solve(self, tag, res, kT: bool):
        m = res.meta
        self.energy.append((tag, float(m["energy_balance"])))
        if kT:
            self.picard.append((tag, float(m.get("picard_dT", NAN)), int(m["picard_iters"])))
        self.solves.append({"tag": tag, "n_cells": int(m["n_cells"]), "wall_s": round(float(m["wall_time_s"]), 2),
                            "rss_gb": round(rss_gb(), 2)})
        log(f"  solved {tag}: {m['n_cells']} cells, {m['wall_time_s']:.1f} s, balance {m['energy_balance']:.1e}, "
            f"peak RSS {rss_gb():.2f} GB")

    def lines(self, tag, levels_xyz: list):
        """Constant ratio: every level-l line is a level-(l+1) line and every level-l cell is split into exactly two."""
        ok = True
        for l0, l1 in zip(levels_xyz[:-1], levels_xyz[1:], strict=False):
            for a, b in zip(l0, l1, strict=True):
                ok &= len(b) == 2 * len(a) - 1 and np.allclose(b[::2], a, rtol=0, atol=1e-12)
                ok &= np.allclose(b[1::2], 0.5 * (a[:-1] + a[1:]), rtol=0, atol=1e-12)
        self.ratio_ok &= bool(ok)
        self.ratio_detail.append(f"{tag}:{'ok' if ok else 'FAIL'}")


def preflight(n_cells: int, cfg: dict, tag: str) -> None:
    """Refuse a solve whose estimated peak memory exceeds the machine's budget (an error result, never a verdict)."""
    est = n_cells * cfg["fv_bytes_per_cell"] / 1e9
    phys = FEM.physical_memory_bytes() / 1e9
    if est > cfg["memory_fraction"] * phys:
        raise MemoryError(f"{tag}: ~{n_cells / 1e6:.1f} M cells, estimated {est:.1f} GB > {cfg['memory_fraction']} x "
                          f"{phys:.1f} GB physical memory; run on a larger machine (scripts/burst_gcp.sh E006)")


def run_series_case(name, c, ref_rows, levels, cfg, st: Stats) -> list[dict]:
    layers = [(la["t_m"], la["k_W_mK"]) for la in c["layers_bottom_up"]]
    srcs = {s["name"]: (s["xc_m"] - s["c_m"] / 2, s["xc_m"] + s["c_m"] / 2, s["yc_m"] - s["d_m"] / 2,
                        s["yc_m"] + s["d_m"] / 2, s["Q_W"]) for s in c["sources"]}
    vals = {i: [] for i in range(len(ref_rows))}
    lines = []
    for lv in levels:
        x, y, z, _ = TL.build_box_grid(c["a_m"], c["b_m"], [t for t, _ in layers], [s[:4] for s in srcs.values()], lv)
        lines.append((x, y, z))
        preflight((len(x) - 1) * (len(y) - 1) * (len(z) - 1), cfg, f"{name} level {lv}")
        out = TL.solve_box_level(c["a_m"], c["b_m"], layers, list(srcs.values()), h=c["h_W_m2K"], T_c=c["Tf_K"],
                                 level=lv)
        res = out["result"]
        st.solve(f"{name}/L{lv}", res, kT=False)
        for i, r in enumerate(ref_rows):
            if r["point"] == "mean":
                x0, x1, y0, y1, _ = srcs[r["source"]]
                vals[i].append(float(res.surface_stats(x0, x1, y0, y1)[0]))
            else:
                vals[i].append(float(np.asarray(res.surface_temperature(r["x_m"], r["y_m"])).ravel()[0]))
        del out, res
        gc.collect()
    st.lines(name, lines)
    rows = []
    for i, r in enumerate(ref_rows):
        rows += case_rows(name, r["source"], f"{r['source']}.{r['point']}", vals[i], r["T_K"], c["scale_K"],
                          vals[i][-1], cfg, r["x_m"], r["y_m"])  # constant k: the null equals the L2 value
    return rows


def case_rows(case, source, point, f, T_ref, scale, dT_const, cfg, x=None, y=None) -> list[dict]:
    est = a4(*f, cfg["gci_floor_K"])
    err = f[2] - T_ref
    out = []
    for lv in range(3):
        fin = lv == 2
        out.append({"kind": "case", "case": case, "source": source, "point": point, "grid_level": lv,
                    "is_finest": fin, "T_l2": f[lv], "T_ref": T_ref, "case_scale": scale,
                    "f_lv0": f[0], "f_lv1": f[1], "f_lv2": f[2], **est,
                    "dT_const_k": dT_const if fin else None, "x_m": x, "y_m": y,
                    "err_K": f[lv] - T_ref,
                    "gci_over_err": (est["gci"] / abs(err) if abs(err) > 0 else math.inf) if fin else None})
    return out


def mms_layout() -> Layout:
    """The manufactured geometry as a Layout, so that the frozen rule's own grid builder makes its grids."""
    B = MMS.BOXES
    boxes = lambda j: [sbox(b[0], b[2], b[1], b[3]) for b in B[j]]  # noqa: E731
    top = boxes(4)
    traces = [Trace("A", top[0]), Trace("B", unary_union(top[1:]))]
    d = MMS.DIE
    die = Die(cx=0.5 * (d[0] + d[1]), cy=0.5 * (d[2] + d[3]), w=d[1] - d[0], h=d[3] - d[2], switch="HS", pads={})
    return Layout(family="mms", dies_per_switch=1, outline=boxes(3)[0], traces=traces, dies=[die], wires=[],
                  terminals={}, baseplate_outline=boxes(0)[0], backside_inset=B[1][0][0] - B[3][0][0])


def run_mms(mms: dict, levels, cfg, st: Stats, ck: Checks | None) -> list[dict]:
    case = MMS.build_case()
    lay = mms_layout()
    pts = mms["payload"]["reported_points"]
    zref = np.array(mms["payload"]["geometry"]["z_interfaces_m"])
    vals = {p["id"]: [] for p in pts}
    lines, geo_ok = [], True
    q_ref = -mms["balance"]["robin_W"]
    res = None
    for lv in levels:
        g = TL.build_layout_grid(lay, lv)
        lines.append((g.x, g.y, g.z))
        xc, yc, zc = (0.5 * (v[:-1] + v[1:]) for v in (g.x, g.y, g.z))
        X, Y, Z = np.meshgrid(xc, yc, zc, indexing="ij")
        mat = MMS.MMSCase.region_of(X, Y, Z)
        geo_ok &= bool(np.array_equal(mat, g.cell_material)) and all(np.min(np.abs(g.z - zz)) < 1e-12 for zz in zref)
        preflight(int((mat >= 0).sum()), cfg, f"mms level {lv}")
        del X, Y, Z
        res = solve_steady(g.x, g.y, g.z, mat, list(case.materials), h=case.h, T_inf=case.T_inf, flux=case.flux,
                           source=case.source)
        st.solve(f"mms/L{lv}", res, kT=True)
        # gated through st.energy (energy_balance sanity check, threshold energy_tol)
        st.energy.append((f"mms/L{lv}/vs_reference_integral", abs(res.meta["q_out"] / q_ref - 1.0)))
        for p in pts:
            if p["kind"] == "area_mean":
                x0, x1, y0, y1 = p["rect"]
                vals[p["id"]].append(float(res.surface_stats(x0, x1, y0, y1)[0]))
            else:
                vals[p["id"]].append(float(np.asarray(res.surface_temperature(p["x"], p["y"])).ravel()[0]))
        if lv != levels[-1]:
            del res
            gc.collect()
    st.lines("mms", lines)
    # F3 null: constant k per layer at the layer's volume-mean temperature of the finest k(T) solution
    T = res.T
    dv = np.einsum("i,j,k->ijk", np.diff(g.x), np.diff(g.y), np.diff(g.z))
    kc = []
    for j, la in enumerate(case.materials):
        m = mat == j
        kc.append(float(la.k_at(float(np.sum(T[m] * dv[m]) / np.sum(dv[m])))))
    del res, T
    gc.collect()
    rc = solve_steady(g.x, g.y, g.z, mat, kc, h=case.h, T_inf=case.T_inf, flux=case.flux, source=case.source)
    st.solve("mms/L2-constk", rc, kT=False)
    rows = []
    for p in pts:
        if p["kind"] == "area_mean":
            x0, x1, y0, y1 = p["rect"]
            nul = float(rc.surface_stats(x0, x1, y0, y1)[0])
        else:
            nul = float(np.asarray(rc.surface_temperature(p["x"], p["y"])).ravel()[0])
        rows += case_rows("mms", "die" if p["level"] == "die" else p["level"], p["id"], vals[p["id"]], p["T_K"],
                          mms["payload"]["case_scale_K"], nul, cfg, p.get("x"), p.get("y"))
    if ck is not None:
        ck.add("mms_geometry_matches_reference", geo_ok,
               detail="frozen-rule grid material map == reference region map at every level; grid z lines contain "
                      "the reference interfaces")
    del rc
    gc.collect()
    return rows


# ------------------------------------------------------------------------------------------------ generator layouts
def dev_layouts(cfg: dict) -> list[tuple[str, Layout]]:
    out = []
    for name, fam, dps in cfg["dev_layouts"]:
        out.append((name, generate_layouts(1, cfg["dev_seed"], family=fam, dies_per_switch=dps)[0]))
    return out


def fresh_layouts(seed: int) -> list[tuple[str, Layout]]:
    """The first DRC-valid layout of each generator family from ``seed`` (dies per switch as drawn)."""
    return [(f"fresh_{fam}", generate_layouts(1, seed, family=fam)[0]) for fam in FAMILIES]


CALIBRATION_MAX_ITERS = 10


def calibrate_power(lay: Layout, cfg: dict) -> tuple[float, float]:
    """Equal power per die from L2 level-0 solves so that the hottest die's Tj max rises target +/- tol above the
    coolant.  Proportional update p <- p * target / rise (a fixed-point iteration on P, exact if the rise were linear in
    P; k(T) makes it slightly nonlinear).  Returns (p, rise) with ``rise`` computed AT the returned ``p`` (the pair
    that operating_point and calibration_rise_K describe, and the power both solvers then use), unrounded.  If the
    tolerance is not met within CALIBRATION_MAX_ITERS solves it raises (an error result, never a verdict) instead of
    returning a power whose rise was never computed (reviews T0194/T0195 of T0165)."""
    Tc, h, tgt, tol = cfg["coolant_K"], cfg["h_W_m2K"], cfg["target_rise_K"], cfg["calibration_tol_K"]
    p = float(cfg["power_start_W"])
    hist = []
    for _ in range(CALIBRATION_MAX_ITERS):
        rise = float(TL.solve_layout_level(lay, level=0, power_W=p, h=h, T_c=Tc)["values"]["tj_max"] - Tc)
        hist.append(p)
        if abs(rise - tgt) <= tol:
            return p, rise  # rise was computed at exactly this p
        p *= tgt / rise
    raise RuntimeError(f"power calibration did not reach {tgt} +/- {tol} K in {CALIBRATION_MAX_ITERS} level-0 "
                       f"solves (powers tried {hist}); refusing to return a power whose rise was not computed")


def run_layout(name, lay, layout_set, cfg, skrule: dict, st: Stats, levels) -> list[dict]:
    Tc, h = cfg["coolant_K"], cfg["h_W_m2K"]
    P, cal = calibrate_power(lay, cfg)
    log(f"{name}: {len(lay.dies)} dies, {P:.3f} W per die, level-0 rise {cal:.3f} K")
    n = len(lay.dies)
    l2 = [[] for _ in range(n)]
    lines = []
    for lv in levels:
        g = TL.build_layout_grid(lay, lv)
        lines.append((g.x, g.y, g.z))
        preflight(int((g.cell_material >= 0).sum()), cfg, f"{name} L2 level {lv}")
        del g
        out = TL.solve_layout_level(lay, level=lv, power_W=P, h=h, T_c=Tc)
        st.solve(f"{name}/L{lv}", out["result"], kT=True)
        for i in range(n):
            l2[i].append(float(out["values"][f"die{i}.tj_max"]))
        del out
        gc.collect()
    st.lines(name, lines)
    rule = FEM.GridRule(h0=skrule["h0_m"], nz=dict(skrule["nz"]), zrefine=False, near_margin=skrule["near_margin_m"])
    rule_z = replace(rule, nz={k: 2 * v for k, v in skrule["nz"].items()})
    fe = [[] for _ in range(n)]
    fe_meta = []
    for lv in levels:
        r = FEM.solve_layout(lay, P, h, Tc, rule=rule, level=lv)
        fe_meta.append({"level": lv, "dofs": int(r.dofs), "wall_s": round(r.wall_s, 1), "eb": r.energy_balance,
                        "picard": r.picard_residual})
        st.energy.append((f"{name}/skfem/L{lv}", float(r.energy_balance)))
        st.picard.append((f"{name}/skfem/L{lv}", float(r.picard_residual), int(r.picard_iters)))
        for i in range(n):
            fe[i].append(float(r.tj_max[i]))
        del r
        gc.collect()
    # z-doubled level-1 solve: skfem_z1 enters A3's denominator and F5, so it passes the same F2 gates (energy balance,
    # Picard) as every other solve (review T0194 of T0165)
    rz = FEM.solve_layout(lay, P, h, Tc, rule=rule_z, level=levels[1])
    z1 = [float(v) for v in rz.tj_max]
    fe_meta.append({"level": f"{levels[1]}z2", "dofs": int(rz.dofs), "wall_s": round(rz.wall_s, 1),
                    "eb": rz.energy_balance, "picard": rz.picard_residual})
    st.energy.append((f"{name}/skfem/L{levels[1]}z2", float(rz.energy_balance)))
    st.picard.append((f"{name}/skfem/L{levels[1]}z2", float(rz.picard_residual), int(rz.picard_iters)))
    del rz
    gc.collect()
    log(f"{name}: scikit-fem {fe_meta}")
    rows = []
    for i, d in enumerate(lay.dies):
        e, s = a4(*l2[i], cfg["gci_floor_K"]), a4(*fe[i], cfg["gci_floor_K"])
        zt = float(MX.two_grid_term([fe[i][1]], [z1[i]])[0])
        ld, sd = direction(l2[i][1], l2[i][2]), direction(fe[i][1], fe[i][2])
        rows.append({
            "kind": "crosscheck", "is_finest": True, "layout": name, "layout_set": layout_set, "family": lay.family,
            "dies_per_switch": lay.dies_per_switch, "fingerprint": lay.fingerprint(), "die": i, "switch": d.switch,
            "power_w": P, "calibration_rise_K": cal, "tj_l2": l2[i][2], "f_lv0": l2[i][0], "f_lv1": l2[i][1],
            "f_lv2": l2[i][2], **e, "tj_skfem": fe[i][2], "skfem_lv0": fe[i][0], "skfem_lv1": fe[i][1],
            "skfem_lv2": fe[i][2], "skfem_gci": s["gci"], "skfem_a4_branch": s["a4_branch"], "skfem_p_obs": s["p_obs"],
            "skfem_z0": fe[i][1], "skfem_z1": z1[i], "skfem_z_term": zt,
            "skfem_estimate": s["gci"] + zt,
            "detectable_bias": e["gci"] + s["gci"] + zt - abs(l2[i][2] - fe[i][2]),
            "l2_direction": ld, "skfem_direction": sd, "same_side": ld == sd,
            "rise_lv0_K": l2[i][0] - Tc})
    return rows


# ------------------------------------------------------------------------------------------------ metrics
RECOMPUTE = [  # (metric, fn, pred, ref, params, where) exactly as the spec's recompute entries
    ("max_case_scaled_err", "max_scaled_abs_err", "T_l2", "T_ref", {"scale": "case_scale"},
     {"kind": "case", "is_finest": True}),
    ("max_abs_err_K", "max_abs_err", "T_l2", "T_ref", {}, {"kind": "case", "is_finest": True}),
    ("max_skfem_consistency", "max_gci_consistency", None, None,
     {"pred_levels": ["f_lv0", "f_lv1", "f_lv2"], "ref_levels": ["skfem_lv0", "skfem_lv1", "skfem_lv2"],
      "ref_zpair": ["skfem_z0", "skfem_z1"], "floor": 0.001}, {"kind": "crosscheck"}),
    ("max_conservative_gci_K", "max_gci_capped", None, None, {"levels": ["f_lv0", "f_lv1", "f_lv2"], "floor": 0.001},
     {"is_finest": True}),
]


def compute_metrics(rows: list[dict]) -> dict:
    out = {}
    for metric, fn, pred, ref, params, where in RECOMPUTE:
        sub = [r for r in rows if all(r.get(k) == v for k, v in where.items())]
        out[metric] = MX.compute(fn, sub, pred=pred, ref=ref, params=params)  # +inf passes through unchanged
    fin = [r for r in rows if r["kind"] == "case" and r["is_finest"]]
    out["null_dT_const_k_scaled_err"] = MX.max_scaled_abs_err([r["dT_const_k"] for r in fin],
                                                              [r["T_ref"] for r in fin], [r["case_scale"] for r in fin])
    out["null_dT_const_k_abs_err_K"] = MX.max_abs_err([r["dT_const_k"] for r in fin], [r["T_ref"] for r in fin])
    return out


def secondary(rows: list[dict]) -> dict:
    fin = [r for r in rows if r["is_finest"]]
    case = [r for r in fin if r["kind"] == "case"]
    return {"n_values": len(fin), "n_oscillatory": sum(r["a4_branch"] == "oscillatory" for r in fin),
            "n_divergent": sum(r["a4_branch"] == "divergent" for r in fin),
            "n_non_asymptotic": sum(bool(r["non_asymptotic"]) for r in fin),
            "min_gci_over_err_case": min((r["gci_over_err"] for r in case), default=NAN),
            "n_case_err_above_gci": sum(abs(r["err_K"]) > r["gci"] for r in case),
            "n_same_side_crosscheck": sum(bool(r.get("same_side")) for r in fin if r["kind"] == "crosscheck")}


# ------------------------------------------------------------------------------------------------ drivers
def all_rows(cfg, ser, mms, levels, st, ck, layouts, skrule) -> list[dict]:
    rows = []
    for name, c in ser["cases"].items():
        ref = [r for r in ser["rows"] if r["case"] == name]
        log(f"case {name}")
        rows += run_series_case(name, c, ref, levels, cfg, st)
    log("case mms")
    rows += run_mms(mms, levels, cfg, st, ck)
    for name, lay, lset in layouts:
        rows += run_layout(name, lay, lset, cfg, skrule, st, levels)
    return rows


def smoke(rows_out: str) -> int:
    cfg = load_config()
    ck = Checks()
    ser, mms = load_refs(cfg, ck)
    for k, v in cfg["smoke_rule"].items():  # coarsened copy of the frozen rule, smoke only (module docstring)
        setattr(TL, k, v)
    st = Stats()
    lays = [(n, lay, "dev") for n, lay in dev_layouts(cfg)]
    fps = {n: lay.fingerprint() for n, lay, _ in lays}
    ok_fp = all(fps[n] == f for n, f in cfg["dev_fingerprints"].items())
    fresh_dev = fresh_layouts(cfg["smoke_fresh_dev_seed"])  # the fresh-layout rule exercised on a dev seed (no solve)
    rows = all_rows(cfg, ser, mms, (0, 1, 2), st, ck, lays, cfg["smoke_skfem_rule"])
    met = compute_metrics(rows)
    doc = {"schema": "mfos.rows/1", "rows": rows,
           "meta": {"mode": "smoke (coarsened rule, dev seed; not evidence)", "smoke_rule": cfg["smoke_rule"],
                    "smoke_skfem_rule": cfg["smoke_skfem_rule"], "dev_fingerprints_match": ok_fp,
                    "fresh_rule_on_dev_seed": {n: (lay.family, lay.dies_per_switch, lay.fingerprint())
                                               for n, lay in fresh_dev},
                    "metrics": met, "secondary": secondary(rows), "max_energy_balance": max(e for _, e in st.energy),
                    "max_picard_dT": max(p for _, p, _ in st.picard), "constant_ratio": st.ratio_ok,
                    "checks": ck.items, "solves": st.solves}}
    Path(rows_out).parent.mkdir(parents=True, exist_ok=True)
    Path(rows_out).write_text(json.dumps(doc, indent=1, default=float) + "\n")
    log(f"wrote {rows_out}: {len(rows)} rows; metrics {met}")
    return 0 if ok_fp else 1


def refcheck(out: str) -> int:
    cfg = load_config()
    ck = Checks()
    t0 = time.time()
    ser, mms = load_refs(cfg, ck)
    reference_checks(ser, mms, cfg, ck)
    doc = {"experiment": EID, "mode": "refcheck (F1 reference-only checks, full resolution, no L2)",
           "checks": [{"name": c["name"], "value": c["value"], "threshold": c["threshold"], "passed": c["passed"],
                       "detail": c["detail"]} for c in ck.items],
           "info": ck.info, "all_passed": all(c["passed"] for c in ck.items),
           "wall_s": round(time.time() - t0, 1), "peak_rss_gb": round(rss_gb(), 2)}
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(json.dumps(doc, indent=1, default=str) + "\n")
    log(f"wrote {out}: all_passed={doc['all_passed']}")
    return 0 if doc["all_passed"] else 1


def full() -> int:
    from mfos.evidence import ExperimentRun

    with ExperimentRun(experiment_id=EID) as run:
        cfg = run.config
        if run.seed is None:
            raise RuntimeError("E006 needs the sealed seed (spec sealed_seed: true)")
        if run.seed == cfg["dev_seed"]:
            raise RuntimeError("the sealed seed equals the development seed")
        ck = Checks()
        ser, mms = load_refs(cfg, ck)  # before any solve
        if not ck.items[-1]["passed"]:
            raise RuntimeError("reference sha256 mismatch: refusing to solve")
        reference_checks(ser, mms, cfg, ck)  # F1, all before the first solver comparison
        st = Stats()
        dev = dev_layouts(cfg)
        fresh = fresh_layouts(run.seed)
        fps = {n: lay.fingerprint() for n, lay in dev + fresh}
        ok = all(fps[n] == f for n, f in cfg["dev_fingerprints"].items())
        fam = sorted(lay.family for _, lay in fresh) == sorted(FAMILIES)
        distinct = len(set(fps.values())) == 5
        ck.add("layout_fingerprints", ok and fam and distinct, detail=json.dumps(
            {n: {"fingerprint": fps[n], "family": lay.family, "dies_per_switch": lay.dies_per_switch}
             for n, lay in dev + fresh}))
        layouts = [(n, lay, "dev") for n, lay in dev] + [(n, lay, "fresh") for n, lay in fresh]
        rows = all_rows(cfg, ser, mms, (0, 1, 2), st, ck, layouts, cfg["skfem_rule"])
        run.rows(rows)
        met = compute_metrics(rows)
        for k in ("max_case_scaled_err", "max_abs_err_K", "max_skfem_consistency", "max_conservative_gci_K"):
            run.metric(k, met[k], level=0.0, n=len(rows), unit="" if k == "max_case_scaled_err" or
                       k == "max_skfem_consistency" else "K")
        for k in ("null_dT_const_k_scaled_err", "null_dT_const_k_abs_err_K"):
            run.metric(k, met[k], level=0.0)
        sec = secondary(rows)
        run.metric("n_oscillatory_values", sec["n_oscillatory"], level=0.0)
        run.metric("n_non_asymptotic_values", sec["n_non_asymptotic"], level=0.0)
        xc = [r for r in rows if r["kind"] == "crosscheck"]
        f5 = _gate_max(r["skfem_estimate"] for r in xc)
        eb = _gate_max(e for _, e in st.energy)
        pic = _gate_max(p for _, p, _ in st.picard)
        cal = _gate_max(abs(r["calibration_rise_K"] - cfg["target_rise_K"]) for r in xc)
        for c in ck.items:
            run.sanity(c["name"], c["passed"], value=c["value"] if isinstance(c["value"], (int, float)) else None,
                       threshold=c["threshold"] if isinstance(c["threshold"], (int, float)) else None,
                       detail=str(c["detail"])[:4000])
        run.sanity("constant_refinement_ratio", st.ratio_ok, detail="; ".join(st.ratio_detail))
        run.sanity("energy_balance", eb <= cfg["energy_tol"], value=eb, threshold=cfg["energy_tol"],
                   detail=f"max over {len(st.energy)} solves incl. mms against the integrated reference fluxes")
        run.sanity("picard_converged", pic < cfg["picard_tol_K"], value=pic, threshold=cfg["picard_tol_K"])
        run.sanity("operating_point", cal <= cfg["operating_point_tol_K"], value=cal,
                   threshold=cfg["operating_point_tol_K"], detail="max |level-0 hottest rise - 60 K| over layouts")
        run.sanity("skfem_gci_f5", f5 <= cfg["f5_max_K"], value=f5, threshold=cfg["f5_max_K"],
                   detail="max over every die of five layouts of gci_capped(skfem_lv0..2, 1e-3) + 2.5|z1 - z0|")
        sm = [f"{r['layout']}/die{r['die']}" for r in xc if r["same_side"]]
        run.domain(case=sorted({r["case"] for r in rows if r["kind"] == "case"}),
                   family=sorted({r["family"] for r in xc}), dies_per_switch=sorted({r["dies_per_switch"] for r in xc}),
                   layout_fingerprint=sorted(fps.values()), coolant_K=[cfg["coolant_K"]], h_W_m2K=[cfg["h_W_m2K"]],
                   target_rise_K=[cfg["target_rise_K"]])
        run.notes = (f"secondary {json.dumps(sec)}; same-side A3 pairs (weak for A3): {sm}; solves "
                     f"{json.dumps(st.solves)}; reference info {json.dumps(ck.info, default=str)[:3000]}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--refcheck", action="store_true")
    ap.add_argument("--out", default="research/e006/refcheck.json")
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--rows-out", default=None)
    a = ap.parse_args(argv)
    os.chdir(ROOT)
    if a.refcheck:
        return refcheck(a.out)
    if a.smoke:
        if not a.rows_out:
            ap.error("--smoke needs --rows-out PATH")
        return smoke(a.rows_out)
    return full()


if __name__ == "__main__":
    sys.exit(main())
