"""T0198 test 2 (diagnosis only, not evidence): is the non-monotone A4 sequence of the 'max' points (and the oscillatory
MMS points) produced by the bilinear surface-interpolation stencil rather than by the FV solution?

No L2 solve. For each point and frozen-rule level 0-2 it builds the frozen grid (TL.build_box_grid / build_layout_grid),
takes the production SurfaceField stencil (same searchsorted rule, same same-height fallback), fills the stencil's
column-centre values with the EXACT reference field (series Field for nlayer_dbc, manufactured T* for mms) and reports
  e_int(L) = interpolant of exact values at the point - exact value at the point   (pure interpolation error)
next to E006's observed error e_obs(L) = f_L - T_ref (rows.json of run E006-20261102T145940-2815, path as argv[1]).
The residual e_obs - e_int is the FV solution's own error at the column centres, carried by the interpolant. A4's
estimator (TL.gci_three_grid, identical to the evaluator's gci_capped and unit-tested as such) is applied to the observed
and to the interpolation-corrected sequence f_L - e_int(L).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / "experiments" / "runners"), str(ROOT / "src"), str(ROOT / "tools" / "mfos")]
import e006_mms as MMS  # noqa: E402
import e006_run as RUN  # noqa: E402
import e006_series as SER  # noqa: E402

from moduleforge.solvers import thermal_layout as TL  # noqa: E402
from moduleforge.solvers.thermal_fv import _SAME_LEVEL_TOL  # noqa: E402

RUN_ROWS = Path(sys.argv[1]) if len(sys.argv) > 1 else None


def gci(f):
    return TL.gci_three_grid(*f, floor=1e-3)["gci"]


def stencil(c, q):
    n = len(c)
    i0 = int(np.clip(np.searchsorted(c, q, side="right") - 1, 0, n - 2))
    return i0, i0 + 1, float((q - c[i0]) / (c[i0 + 1] - c[i0]))


def interp_exact(x, y, height, exact_at, xq, yq):
    """Production stencil (SurfaceField._eval) with exact column values; height[i,j] = surface z (NaN void)."""
    xc, yc = 0.5 * (x[:-1] + x[1:]), 0.5 * (y[:-1] + y[1:])
    ci = int(np.clip(np.searchsorted(x, xq, side="right") - 1, 0, len(xc) - 1))
    cj = int(np.clip(np.searchsorted(y, yq, side="right") - 1, 0, len(yc) - 1))
    i0, i1, tx = stencil(xc, xq)
    j0, j1, ty = stencil(yc, yq)
    own_z = height[ci, cj]
    own = exact_at(xc[ci], yc[cj], own_z)
    fell_back = []

    def node(i, j):
        z = height[i, j]
        if np.isfinite(z) and abs(z - own_z) <= _SAME_LEVEL_TOL:
            return exact_at(xc[i], yc[j], z)
        fell_back.append((i, j))
        return own

    v = ((1 - tx) * (1 - ty) * node(i0, j0) + tx * (1 - ty) * node(i1, j0)
         + (1 - tx) * ty * node(i0, j1) + tx * ty * node(i1, j1))
    hx, hy = xc[i1] - xc[i0], yc[j1] - yc[j0]
    return v, own_z, {"tx": round(tx, 4), "ty": round(ty, 4), "hx_mm": round(hx * 1e3, 4),
                      "hy_mm": round(hy * 1e3, 4), "fallback_nodes": len(fell_back)}


def main():
    rows = json.load(open(RUN_ROWS))["rows"] if RUN_ROWS else []
    obs = {(r["case"], r["point"]): r for r in rows if r.get("kind") == "case" and r["is_finest"]}
    out = []
    # ---- nlayer_dbc (laterally uniform box; every column has the same surface height)
    ser = json.load(open(ROOT / "research/e006_refs/series_values.json"))["payload"]
    c = ser["cases"]["nlayer_dbc"]
    fld = SER.Field(SER.case_nlayer())
    thick = [la["t_m"] for la in c["layers_bottom_up"]]
    srcs = [(s["xc_m"] - s["c_m"] / 2, s["xc_m"] + s["c_m"] / 2, s["yc_m"] - s["d_m"] / 2, s["yc_m"] + s["d_m"] / 2)
            for s in c["sources"]]

    def ex_n(xx, yy, zz):
        return float(fld.T([SER.Target.point(float(xx), float(yy))])[0])

    pts_n = [r for r in ser["rows"] if r["case"] == "nlayer_dbc" and r["point"] in ("max", "centroid")]
    grids_n = []
    for lv in range(3):
        gx, gy = TL.build_box_grid(c["a_m"], c["b_m"], thick, srcs, lv)[:2]
        grids_n.append((gx, gy, np.zeros((len(gx) - 1, len(gy) - 1))))
    # ---- mms (layout grid; surface height per column from the frozen grid's material map)
    mcase = MMS.build_case()
    mref = json.load(open(ROOT / "research/e006_refs/mms_values.json"))["payload"]["reported_points"]
    lay = RUN.mms_layout()
    grids_m = []
    for lv in range(3):
        g = TL.build_layout_grid(lay, lv)
        has = g.cell_material >= 0
        kt = has.shape[2] - 1 - np.argmax(has[:, :, ::-1], axis=2)
        height = np.where(has.any(axis=2), g.z[kt + 1], np.nan)
        grids_m.append((g.x, g.y, height))

    def ex_m(xx, yy, zz):
        return float(np.asarray(mcase.T_exact(np.array([xx]), np.array([yy]), np.array([zz - 1e-12]))).ravel()[0])  # just below the surface

    jobs = [("nlayer_dbc", f"{r['source']}.{r['point']}", r["x_m"], r["y_m"], r["T_K"], grids_n, ex_n) for r in pts_n]
    jobs += [("mms", p["id"], p["x"], p["y"], p["T_K"], grids_m, ex_m) for p in mref if p["kind"] in ("point", "max")]
    for case_name, pid, xq, yq, Tref, grids, exact in jobs:
        e_int, info, ref_check = [], [], None
        for gx, gy, h in grids:
            v, z_own, inf = interp_exact(gx, gy, h, exact, xq, yq)
            t_pt = exact(xq, yq, z_own)
            ref_check = t_pt - Tref  # exact field at the point vs the frozen reference value
            e_int.append(v - t_pt)
            info.append(inf)
        o = obs.get((case_name, pid))
        rec = {"case": case_name, "point": pid, "x_mm": xq * 1e3, "y_mm": yq * 1e3, "ref_check_K": ref_check,
               "e_int": e_int, "stencil": info}
        if o:
            f = [o["f_lv0"], o["f_lv1"], o["f_lv2"]]
            e_obs = [v - Tref for v in f]
            fc = [f[i] - e_int[i] for i in range(3)]
            rec.update({"e_obs": e_obs, "e_resid": [e_obs[i] - e_int[i] for i in range(3)],
                        "gci_obs": gci(f), "gci_corrected": gci(fc)})
        out.append(rec)

        def fmt(v):
            return " ".join(f"{a:+.4f}" for a in v)

        line = f"{case_name:10s} {pid:20s} refchk {ref_check:+.1e} | e_int {fmt(e_int)}"
        if o:
            line += (f" | e_obs {fmt(rec['e_obs'])} | resid {fmt(rec['e_resid'])} | GCI obs {rec['gci_obs']:.4f}"
                     f" -> corr {rec['gci_corrected']:.4f}")
        line += " | " + "; ".join(f"t=({s['tx']},{s['ty']}) h=({s['hx_mm']},{s['hy_mm']}) fb={s['fallback_nodes']}"
                                  for s in info)
        print(line, flush=True)
    Path(ROOT / "research/diagnoses/T0198/t2_interp_stencil.json").write_text(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    main()
