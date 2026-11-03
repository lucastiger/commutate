"""T0198 test 1 (diagnosis only, not evidence): a series case (default Case 2, Muzychka 2003 single 10 mm plate) on the frozen box
grid rule. Usage: t1_case2_refinement.py {small|all|zsplit} [case].

Reproduces E006's level 0-2 values for Case 2, then separates lateral from through-thickness (z) refinement:
  (a) frozen levels 0, 1, 2           (must reproduce rows.json to ~1e-9 K: determinism / provenance)
  (b) lateral level 2, z of level 3   (z doubled)
  (c) lateral level 2, z of level 4   (z quadrupled)
  (d) lateral level 3, z of level 2   (lateral doubled)
  (e) full level 3                    (both doubled)
For each source mean / centroid it reports T - T_ref, and also the cell-sum mean (FV-consistent mean of the
reconstructed surface values of cells inside the source) next to the interpolant mean used by E006.
Memory: prints peak RSS after each solve; skips a solve whose estimate (2000 B/cell, measured) > 4.5 GB.
"""
from __future__ import annotations

import json
import resource
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / "experiments" / "runners"), str(ROOT / "src")]
from moduleforge.solvers import thermal_layout as TL  # noqa: E402
from moduleforge.solvers.thermal_fv import solve_steady  # noqa: E402

MAX_GB = 4.5


def rss_gb():
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e9  # macOS: bytes


def main(variants, case="case2"):
    ser = json.load(open(ROOT / "research/e006_refs/series_values.json"))["payload"]
    c = ser["cases"][case]
    refs = [r for r in ser["rows"] if r["case"] == case]
    layers = [(la["t_m"], la["k_W_mK"]) for la in c["layers_bottom_up"]]
    srcs = [(s["xc_m"] - s["c_m"] / 2, s["xc_m"] + s["c_m"] / 2, s["yc_m"] - s["d_m"] / 2, s["yc_m"] + s["d_m"] / 2,
             s["Q_W"], s["name"]) for s in c["sources"]]
    thick = [t for t, _ in layers]
    out = []
    for name, lat, zl in variants:
        x, y, _, _ = TL.build_box_grid(c["a_m"], c["b_m"], thick, [s[:4] for s in srcs], lat)
        _, _, z, _ = TL.build_box_grid(c["a_m"], c["b_m"], thick, [s[:4] for s in srcs], zl)
        zlines = np.concatenate([[0.0], np.cumsum(thick)])
        zc = 0.5 * (z[:-1] + z[1:])
        layer_of = np.searchsorted(zlines, zc) - 1
        mat = np.broadcast_to(layer_of, (len(x) - 1, len(y) - 1, len(z) - 1)).copy()
        n = mat.size
        if n * 2000 / 1e9 > MAX_GB:  # measured ~1.9 kB/cell at 333 k cells
            print(f"skip {name}: {n} cells, est {n * 2000 / 1e9:.1f} GB > {MAX_GB}")
            continue
        xc, yc = 0.5 * (x[:-1] + x[1:]), 0.5 * (y[:-1] + y[1:])
        q = np.zeros(mat.shape)
        for x0, x1, y0, y1, P, _ in srcs:  # same flux assignment as TL.solve_box_level
            ii, jj = np.nonzero((xc > x0)[:, None] & (xc < x1)[:, None] & (yc > y0)[None, :] & (yc < y1)[None, :])
            q[ii, jj, -1] += P / ((x1 - x0) * (y1 - y0))
        t0 = time.time()
        res = solve_steady(x, y, z, mat, [k for _, k in layers], h=c["h_W_m2K"], T_inf=c["Tf_K"], flux={(2, 1): q},
                           picard_tol=1e-4)
        sf = res.surface
        rec = {"variant": name, "lat_level": lat, "z_level": zl, "n_cells": int(n), "nz": len(z) - 1,
               "hx_bulk_mm": float(np.max(np.diff(x)) * 1e3), "dz_mm": float(np.max(np.diff(z)) * 1e3),
               "energy_balance": float(res.meta["energy_balance"]), "wall_s": round(time.time() - t0, 2), "pts": {}}
        for r in refs:
            s = next(s for s in srcs if s[5] == r["source"])
            if r["point"] == "mean":
                v = float(res.surface_stats(s[0], s[1], s[2], s[3])[0])  # E006's interpolant mean
                inside = ((sf.xc > s[0]) & (sf.xc < s[1]))[:, None] & ((sf.yc > s[2]) & (sf.yc < s[3]))[None, :]
                w = np.diff(x)[:, None] * np.diff(y)[None, :]
                cell_mean = float((sf.values * w)[inside].sum() / w[inside].sum())
                rec["pts"][f"{r['source']}.mean"] = {"err": v - r["T_K"], "cellsum_err": cell_mean - r["T_K"]}
            else:
                v = float(np.asarray(res.surface_temperature(r["x_m"], r["y_m"])).ravel()[0])
                rec["pts"][f"{r['source']}.{r['point']}"] = {"err": v - r["T_K"]}
        rec["rss_gb"] = round(rss_gb(), 2)
        out.append(rec)
        e = rec["pts"]
        print(f"{name:10s} cells={n:9d} nz={rec['nz']:3d} dz={rec['dz_mm']:.3f}mm hx={rec['hx_bulk_mm']:.3f}mm "
              f"wall={rec['wall_s']:6.1f}s rss={rec['rss_gb']:.2f}GB bal={rec['energy_balance']:.1e} | "
              + " ".join(f"{k} {v['err']:+.4f}" for k, v in e.items()), flush=True)
        del res, sf, q, mat
    return out


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    case = sys.argv[2] if len(sys.argv) > 2 else "case2"
    V = {"small": [("L0", 0, 0), ("L1", 1, 1), ("L2", 2, 2)],
         "all": [("L0", 0, 0), ("L1", 1, 1), ("L2", 2, 2), ("L2z3", 2, 3), ("L2z4", 2, 4), ("L1z3", 1, 3),
                 ("L3z2", 3, 2), ("L3", 3, 3)],
         "nlsplit": [("L0", 0, 0), ("L0z1", 0, 1), ("L0z2", 0, 2), ("L1z0", 1, 0)],
         "zsplit": [("L0", 0, 0), ("L0z1", 0, 1), ("L0z2", 0, 2), ("L0z3", 0, 3), ("L1", 1, 1), ("L1z0", 1, 0)]}[which]
    res = main(V, case)
    Path(ROOT / f"research/diagnoses/T0198/t1_{case}_{which}.json").write_text(json.dumps(res, indent=1))
