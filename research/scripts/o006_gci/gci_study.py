"""T0181 research study (not evidence): GCI of Tj-max differences and estimator conservativeness at the die-attach corner.

Parts (each writes ``research/o006_gci/<part>.json``; ``merge`` writes ``research/o006_gci/results.json``):

* ``pairs``   -- three same-stratum pairs (same family, dies per switch = 2, same die size) of development layouts from
  ``generate_layouts(16, DEV_SEED, family=f, dies_per_switch=2)`` (DEV_SEED != 20261101); first pair in generation order
  with equal die size.  Frozen T0170 grid rule, levels 0-2, k(T), h = 5000 W/m2K, coolant 65 C, equal die power
  calibrated once on layout A at level 0 to an 85 K hottest rise and used unchanged for B.
* ``strip2d`` -- y-invariant strip (two y cells, adiabatic y walls => exact 2D x-z problem) of the default DBC stack with two
  die strips on one top-Cu pad: contains the bimaterial die-attach-on-copper edge.  Lateral grid = the frozen rule's
  ``edge_graded_nodes`` with the frozen constants; levels 0..6 (finest edge cell 100 um / 64).
* ``die3d``   -- one 4.5 mm die on a pad, full 3D, frozen-rule grid, levels 0..3.

Estimators for a coarse-to-fine triple (f3, f2, f1), r = 2: p_obs, Richardson error estimate |f2-f1|/(r**p_obs - 1),
frozen O006 GCI (``thermal_layout.gci_three_grid``), candidate GCI (Fs = 3, p = clip(p_obs, 0.5, 2) outside [1.5, 2.5];
same as frozen inside; for oscillatory triples p = 0.5, an assumption of this note, the packet does not define it).

Run: ``uv run python research/scripts/o006_gci/gci_study.py {pairs|strip2d|die3d|merge} [--max-level N]``.
"""
from __future__ import annotations

import argparse
import json
import math
import resource
import sys
import time
from pathlib import Path

import numpy as np
from scipy.optimize import brentq

from moduleforge.geometry.stack import default_dbc_stack
from moduleforge.solvers import thermal_layout as tl
from moduleforge.solvers.thermal_fv import solve_steady

OUT = Path(__file__).resolve().parents[3] / "research" / "o006_gci"
DEV_SEED = 1181  # development seed (task number); never 20261101
FORBIDDEN_SEED = 20261101
T_C = 65.0 + 273.15
H = 5000.0
TARGET_RISE = 85.0
FAMILIES = ("side_by_side", "interleaved", "u_shaped")
MM = 1e-3
CELL_CAP = 8_000_000  # cells; measured 0.9 kB/cell (3D, T0170 benchmark) to 1.6 kB/cell (strip, level 5): <= 13 GB of 16 GB


def rss_gb() -> float:
    r = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return r / 1e9 if sys.platform == "darwin" else r / 1e6


# ------------------------------------------------------------------------------------------------ estimators
def estimators(f3: float, f2: float, f1: float, r: float = 2.0) -> dict:
    d32, d21 = f2 - f3, f1 - f2
    fr = tl.gci_three_grid(f3, f2, f1, r)
    mono = d32 * d21 > 0
    p_abs = math.log(abs(d32) / abs(d21)) / math.log(r) if d21 != 0 and d32 != 0 else float("nan")
    p_obs = p_abs if mono else float("nan")
    re = abs(d21) / (r**p_obs - 1.0) if mono and p_obs > 0 else float("nan")
    f_re = f1 + d21 / (r**p_obs - 1.0) if mono and p_obs > 0 else float("nan")
    if d21 == 0:
        cand = 0.0
    elif mono and 1.5 <= p_obs <= 2.5:
        cand = 1.25 * abs(d21) / (r ** min(p_obs, 2.0) - 1.0)
    else:
        p = float(np.clip(p_obs, 0.5, 2.0)) if mono else 0.5
        cand = 3.0 * abs(d21) / (r**p - 1.0)
    return {"values": [f3, f2, f1], "monotone": bool(mono), "p_obs": p_obs, "p_abs": p_abs, "richardson_err": re,
            "richardson_value": f_re, "gci_frozen": fr["gci"], "gci_candidate": cand, "abs_d21": abs(d21)}


def corner_exponent(k_attach: float, k_cu: float) -> float:
    """Root in (0.5, 1) of k1 tan(lam pi/2) + k2 tan(lam pi) = 0 (90 deg attach wedge on 180 deg Cu, Neumann faces;
    derived in research/notes/o006-gci-differences.md section 2)."""
    f = lambda lam: k_attach * math.tan(lam * math.pi / 2) + k_cu * math.tan(lam * math.pi)  # noqa: E731
    return brentq(f, 0.5 + 1e-9, 1.0 - 1e-9)


# ------------------------------------------------------------------------------------------------ part 1: pairs
def find_pairs():
    from moduleforge.generate.halfbridge import generate_layouts

    assert DEV_SEED != FORBIDDEN_SEED
    pairs = []
    for fam in FAMILIES:
        lays = generate_layouts(16, DEV_SEED, family=fam, dies_per_switch=2)
        seen = {}
        for i, lay in enumerate(lays):
            s = round(lay.dies[0].w / MM, 3)
            if s in seen:
                pairs.append((fam, s, (seen[s], lays[seen[s]]), (i, lay)))
                break
            seen[s] = i
        else:
            raise RuntimeError(f"no equal-die-size pair for {fam}")
    return pairs


def calibrate(lay) -> float:
    p = 50.0
    for _ in range(8):
        rise = tl.solve_layout_level(lay, level=0, power_W=p, h=H, T_c=T_C)["values"]["tj_max"] - T_C
        if abs(rise - TARGET_RISE) < 1.0:
            break
        p *= TARGET_RISE / rise
    return round(p, 1)


def run_pairs(max_level: int) -> dict:
    out = []
    for fam, s, (ia, la), (ib, lb) in find_pairs():
        P = calibrate(la)
        rec = {"family": fam, "dies_per_switch": 2, "die_size_mm": s, "power_per_die_W": P, "layouts": []}
        vals = {}
        for tag, idx, lay in (("A", ia, la), ("B", ib, lb)):
            lv = []
            for level in range(max_level + 1):
                t0 = time.perf_counter()
                r = tl.solve_layout_level(lay, level=level, power_W=P, h=H, T_c=T_C)
                lv.append({"level": level, "n_cells": r["meta"]["n_cells"], "wall_s": time.perf_counter() - t0,
                           "peak_rss_gb_so_far": rss_gb(), "energy_balance": r["meta"]["energy_balance"],
                           "picard_iters": r["meta"]["picard_iters"], "values": r["values"]})
                del r
                print(fam, tag, level, lv[-1]["n_cells"], round(lv[-1]["wall_s"], 1), round(rss_gb(), 2), flush=True)
            vals[tag] = lv
            per_die = []
            for d in range(len(lay.dies)):
                f = [x["values"][f"die{d}.tj_max"] for x in lv]
                per_die.append({"die": d, "switch": lay.dies[d].switch, "tj_max_K": f,
                                **(estimators(*f[-3:]) if len(f) >= 3 else {})})
            ft = [x["values"]["tj_max"] for x in lv]
            rec["layouts"].append({"tag": tag, "index_in_generation": idx, "fingerprint": lay.fingerprint(),
                                   "levels": [{k: v for k, v in x.items() if k != "values"} for x in lv],
                                   "per_die": per_die, "tj_max": {"tj_max_K": ft, **(estimators(*ft[-3:]) if len(ft) >= 3 else {})}})
        dif = [a["values"]["tj_max"] - b["values"]["tj_max"] for a, b in zip(vals["A"], vals["B"], strict=True)]
        rec["diff_tj_max_A_minus_B"] = {"values_K": dif, **(estimators(*dif[-3:]) if len(dif) >= 3 else {})}
        out.append(rec)
    return {"dev_seed": DEV_SEED, "pairs": out}


# ------------------------------------------------------------------------------------------------ cropped cases
def stack_z(st):
    zl = np.concatenate([[0.0], np.cumsum([la.thickness for la in st.layers])])
    zt = zl[-1]
    za, zd = zt + st.die_attach.thickness, zt + st.die_attach.thickness + st.die.thickness
    return np.concatenate([zl, [za, zd]])


def cropped_grid(xspec, yspec, dies, level, st):
    """xspec/yspec: dict(lines, feature, edge, far_lo, far_hi) in m; ``dies`` = [(x0, x1, y0, y1)].  Frozen-rule nodes."""
    zl = stack_z(st)
    s_edge = tl.EDGE_FRAC * min(la.thickness for la in (*st.layers, st.die_attach))
    fmin = min(float(np.diff(tl._merge(sp["feature"])).min()) for sp in (xspec, yspec) if len(sp["feature"]) > 1)
    h0 = tl.level0_cell(fmin)
    ax = []
    for sp in (xspec, yspec):
        if sp.get("uniform"):
            ax.append(np.asarray(sp["uniform"]))
            continue
        ln = tl._merge(sp["lines"])
        mid = 0.5 * (ln[:-1] + ln[1:])
        far = (mid < sp["far_lo"]) | (mid > sp["far_hi"])
        ax.append(tl.edge_graded_nodes(ln, sp["edge"], h0, s_edge, tl.GROW, level, far, tl.FAR_FACTOR))
    x, y = ax
    z = tl._subdivide(zl, tl.z_counts(len(zl) - 1, level))
    return x, y, z, zl


def solve_cropped(xspec, yspec, regions, dies, level, q_flux, constant_k=False):
    """regions: per substrate layer (x0, x1, y0, y1) footprint; dies: [(x0, x1, y0, y1)] attach+die footprints."""
    st = default_dbc_stack()
    x, y, z, zl = cropped_grid(xspec, yspec, dies, level, st)
    if (len(x) - 1) * (len(y) - 1) * (len(z) - 1) > CELL_CAP:
        raise MemoryError(f"level {level}: grid exceeds CELL_CAP = {CELL_CAP} cells (16 GB host)")
    xc, yc, zc = 0.5 * (x[:-1] + x[1:]), 0.5 * (y[:-1] + y[1:]), 0.5 * (z[:-1] + z[1:])
    mat = np.full((len(xc), len(yc), len(zc)), -1, dtype=np.int64)

    def foot(b):
        return ((xc > b[0]) & (xc < b[1]))[:, None] & ((yc > b[2]) & (yc < b[3]))[None, :]

    for m, b in enumerate(regions):
        k = np.nonzero((zc > zl[m]) & (zc < zl[m + 1]))[0]
        mat[:, :, k] = np.where(foot(b)[:, :, None], m, -1)
    ka = np.nonzero((zc > zl[5]) & (zc < zl[6]))[0]
    kd = np.nonzero((zc > zl[6]) & (zc < zl[7]))[0]
    q = np.zeros(mat.shape)
    for b in dies:
        f = foot(b)
        for kk, mid in ((ka, 5), (kd, 6)):
            sl = mat[:, :, kk]
            sl[f] = mid
            mat[:, :, kk] = sl
        q[:, :, kd[-1]][f] = q_flux
    mats = [*st.layers, st.die_attach, st.die]
    if constant_k:
        mats = [la.k for la in mats]
    t0 = time.perf_counter()
    res = solve_steady(x, y, z, mat, mats, h=H, T_inf=T_C, flux={(2, 1): q})
    vals = {}
    for i, b in enumerate(dies):
        mean, mx = res.surface_stats(b[0], b[1], b[2], b[3])
        vals[f"die{i}.tj_max"] = mx
        vals[f"die{i}.tj_mean"] = mean
        vals[f"die{i}.tj_centroid"] = float(res.surface(0.5 * (b[0] + b[1]), 0.5 * (b[2] + b[3])))
    if len(dies) == 2:
        vals["diff_tj_max"] = vals["die0.tj_max"] - vals["die1.tj_max"]
        vals["diff_tj_mean"] = vals["die0.tj_mean"] - vals["die1.tj_mean"]
    meta = {"level": level, "n_cells": int(res.meta["n_cells"]), "energy_balance": res.meta["energy_balance"],
            "picard_iters": res.meta["picard_iters"], "wall_s": time.perf_counter() - t0, "peak_rss_gb_so_far": rss_gb(),
            "min_dx_m": float(np.diff(x).min())}
    return vals, meta


def strip_geometry():
    m = MM
    dies = [(3.5 * m, 8.0 * m, 0.0, 1.0 * m), (11.0 * m, 15.5 * m, 0.0, 1.0 * m)]  # die0 near the pad edge
    pad, outline, back, base = (1.5 * m, 19.0 * m), (0.0, 22.0 * m), (1.0 * m, 21.0 * m), (-8.0 * m, 30.0 * m)
    xs = {"lines": [base[0], base[1], *outline, *back, *pad, *(v for d in dies for v in d[:2])],
          "feature": [*pad, *(v for d in dies for v in d[:2])], "edge": [v for d in dies for v in d[:2]],
          "far_lo": outline[0], "far_hi": outline[1]}
    ys = {"uniform": [0.0, 0.5 * m, 1.0 * m], "feature": []}
    yy = (0.0, 1.0 * m)
    regions = [(*base, *yy), (*back, *yy), (*back, *yy), (*outline, *yy), (*pad, *yy)]
    return xs, ys, regions, dies


def strip_dieonly_geometry():
    """Discriminating variant: every substrate layer spans the outline (no Cu-on-ceramic or solder-on-baseplate re-entrant
    edges); the only re-entrant material corners left are the die-attach-on-Cu edges."""
    xs, ys, _, dies = strip_geometry()
    m = MM
    outline, yy = (0.0, 22.0 * m), (0.0, 1.0 * m)
    xs = {"lines": [*outline, *(v for d in dies for v in d[:2])], "feature": [*outline, *(v for d in dies for v in d[:2])],
          "edge": [v for d in dies for v in d[:2]], "far_lo": outline[0], "far_hi": outline[1]}
    return xs, ys, [(*outline, *yy)] * 5, dies


def die3d_geometry():
    m = MM
    d = (-2.25 * m, 2.25 * m)
    pad, back, outline, base = (-5.25 * m, 5.25 * m), (-6.25 * m, 6.25 * m), (-7.25 * m, 7.25 * m), (-11.25 * m, 11.25 * m)
    sp = {"lines": [*base, *outline, *back, *pad, *d], "feature": [*pad, *d], "edge": list(d),
          "far_lo": outline[0], "far_hi": outline[1]}
    regions = [(*base, *base), (*back, *back), (*back, *back), (*outline, *outline), (*pad, *pad)]
    return sp, dict(sp), regions, [(*d, *d)]


def run_cropped(kind: str, max_level: int, q_flux: float, constant_k: bool) -> dict:
    xs, ys, regions, dies = {"strip2d": strip_geometry, "strip_dieonly": strip_dieonly_geometry,
                             "die3d": die3d_geometry}[kind]()
    levels = []
    for lv in range(max_level + 1):
        vals, meta = solve_cropped(xs, ys, regions, dies, lv, q_flux, constant_k)
        levels.append({"meta": meta, "values": vals})
        print(kind, "constk" if constant_k else "kT", lv, meta["n_cells"], round(meta["wall_s"], 1),
              round(meta["peak_rss_gb_so_far"], 2), {k: round(v, 5) for k, v in vals.items()}, flush=True)
    names = list(levels[0]["values"])
    seq = {}
    for n in names:
        f = [lv_["values"][n] for lv_ in levels]
        triples = [{"levels": [i, i + 1, i + 2], **estimators(*f[i:i + 3])} for i in range(len(f) - 2)]
        rec = {"values_K": f, "triples": triples}
        if len(f) >= 4:  # reference: Richardson from the finest triple, uncertainty = its candidate GCI (conservative)
            fin = triples[-1]
            ref = fin["richardson_value"] if math.isfinite(fin["richardson_value"]) else f[-1]
            ref_unc = max(fin["gci_candidate"], abs(ref - f[-1]))
            e2 = abs(f[2] - ref)
            t0 = triples[0]
            rec["reference"] = {"value_K": ref, "uncertainty_K": ref_unc, "from_levels": fin["levels"]}
            rec["true_err_level2_K"] = e2
            for est in ("gci_frozen", "gci_candidate", "richardson_err"):
                g = t0[est]
                verdict = ("conservative" if g >= e2 + ref_unc else "non-conservative" if g < e2 - ref_unc
                           else "undetermined") if math.isfinite(g) else "undefined"
                rec[f"{est}_L012_vs_true"] = {"estimate_K": g, "ratio_est_over_true": g / e2 if e2 > 0 else None,
                                              "verdict": verdict}
        seq[n] = rec
    st = default_dbc_stack()
    return {"kind": kind, "q_flux_W_m2": q_flux, "constant_k": constant_k, "levels": [lv_["meta"] for lv_ in levels],
            "values": seq, "corner_exponent_lambda": corner_exponent(st.die_attach.k, st.layers[4].k),
            "corner_exponent_homogeneous_check": corner_exponent(1.0, 1.0),
            "corner_exponent_cu_quadrant_on_ceramic": corner_exponent(st.layers[4].k, st.layers[3].k),
            "corner_exponent_solder_quadrant_on_baseplate": corner_exponent(st.layers[1].k, st.layers[0].k)}


def _clean(o):
    if isinstance(o, float) and not math.isfinite(o):
        return None
    if isinstance(o, dict):
        return {k: _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    if isinstance(o, np.generic):
        return _clean(o.item())
    return o


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("part", choices=["pairs", "strip2d", "strip_dieonly", "die3d", "merge"])
    ap.add_argument("--max-level", type=int, default=None)
    ap.add_argument("--constant-k", action="store_true")
    ap.add_argument("--q", type=float, default=2.0e6, help="die-top heat flux, W/m2")
    ap.add_argument("--tag", default="")
    a = ap.parse_args(argv)
    OUT.mkdir(parents=True, exist_ok=True)
    if a.part == "merge":
        doc = {"note": "research/notes/o006-gci-differences.md", "status": "research, not evidence"}
        for f in sorted(OUT.glob("part_*.json")):
            doc[f.stem[5:]] = json.loads(f.read_text())
        (OUT / "results.json").write_text(json.dumps(_clean(doc), indent=1) + "\n")
        return 0
    if a.part == "pairs":
        doc = run_pairs(2 if a.max_level is None else a.max_level)
    else:
        ml = a.max_level if a.max_level is not None else (3 if a.part == "die3d" else 6)
        doc = run_cropped(a.part, ml, a.q, a.constant_k)
    name = f"part_{a.part}{a.tag}.json"
    (OUT / name).write_text(json.dumps(_clean(doc), indent=1) + "\n")
    print("wrote", OUT / name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
