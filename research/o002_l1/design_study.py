"""O002 L1 thermal design study (T0392): speed and accuracy of candidate fast models against the level-1 reference.

Research prototype, never production code (n4 builds ``moduleforge.thermal``). Development geometry only.

Data. C004's development layouts (E009 config.dev_layouts, dev seed 20261101: side_by_side_6, u_shaped_2) and, per
stratum (family, dies) of those two layouts, the first N_NEW DRC-valid layouts of the recorded development seed NEW_SEED
whose die size equals the development layout's (rejection on the generator's die size s). Strata: (u_shaped, 2) is in
the 2-3 band and (side_by_side, 6) in the 4-6 band; die size 5.0 mm in both (the dev layouts' size).

Operating point. T_c = 338.15 K, h = 5000 W/(m2 K), k(T), equal power per die. P_ref per stratum is C004's calibration
of its development layout (E009 config.dev_regression_guard.calibrated_power_W_per_die, hottest node 60 +/- 0.25 K above
the coolant at level 0); it is re-checked here by one level-0 solve per development layout. Second load 0.5 P_ref.

Reference. ``thermal_fem.solve_layout`` at the frozen GridRule of research/o007_dev3/frozen_config.json, level 1, built
key for key as E009's ``rule_from``; energy balance <= 1e-6 asserted on every solve; one solve at a time; per-solve
summaries cached in research/o002_l1/cache/ (no fields). Die-local rise = tj_mean - mean baseplate-bottom temperature;
that mean is T_c + P_total / (h A_bottom) for uniform h (energy balance), checked against the Q1 bilinear integral of the
nodal field over z = 0 on every solve.

Candidates (all single-thread; each evaluation timed end to end; one-off precomputation reported separately):
* fv_coarse: the in-house cell-centred FV solver (solvers.thermal_fv via thermal_layout.solve_layout_level) on a coarse
  rule (H0_MAX 4 mm, LAT_FRAC 16, EDGE_FRAC 2, Z_CELLS 2, level 0), k(T) by Picard to 1e-2 K. Uncalibrated.
* fv_coarse_boxcal: fv_coarse with the die-local rise scaled by c_box(die size) = (exact N-layer Fourier-series rise) /
  (same-rule FV rise) of one isolated die on the laterally uniform 7-layer box stack (constant k). No reference data.
* fv_coarse_xcal: fv_coarse with the die-local rise scaled by c_x = mean over dies of (ref rise) / (fv rise) on the
  OTHER stratum's development layout at its P_ref (an out-of-stratum transfer test of a reference-calibrated factor).
* fem_coarse: thermal_fem itself on a coarse GridRule (h0 16 mm, near margin 1 mm, dz_max 4 mm, edge grading 1 mm x 2.5
  to 4 mm, gs sweeps 2, level 0), Picard to 1e-2 K. Uncalibrated. fem_coarse_xcal: as fv_coarse_xcal.
* series_superposition: per-housing superposition of the exact N-layer box-stack Fourier series (thermal_series modes;
  Carslaw & Jaeger 1959 sec. 3.6; Muzychka, Culham & Yovanovich 2003) on the baseplate rectangle with every substrate
  layer laterally uniform (trace patterning, ceramic and backside extent ignored), plus the 1D die and attach drop
  P t / (k A); k(T) by three fixed-point passes on layer temperatures estimated from the 1D resistance fractions.

Statistics (point estimates, numpy linear percentiles), per load, pooled over strata:
* a1_pair_err_p95_K: p95 over same-stratum unordered layout pairs (self-pairs excluded) of |(T_a,h_a - T_b,h_b)_model -
  (T_a,h_a - T_b,h_b)_ref|, h_x the die the reference ranks hottest by tj_mean in layout x.
* a2_rel_err_p95: p95 over dies of |T_model - T_ref| / (T_ref - T_bp), T_bp = T_c + P_total / (h A_bottom).
* a3_spread_err_p95_K: p95 over (layout, switch) of |spread_model - spread_ref|, spread = max - min of tj_mean.
* a4_ratio_vs_stratum_mean: a3 / a3 of the stratum-mean-spread null (per (stratum, switch), leave-one-layout-out).
Nulls on the reference values: stratum_mean (every die of layout j predicted by the mean over the other layouts' dies;
spread by the LOLO mean spread of that switch) and die_position (LOLO mean at the same (switch, die index); die index =
order within the switch in layout.dies; its spread is max - min of the predicted dies). f2_warning: some null's a1 at
P_ref <= 0.5 K. Indicative 95 % intervals: layout-clustered percentile bootstrap within strata (B = 1000, seed 20261116),
known to under-cover a p95 bound (review T0369); reported, not used for any decision.

Choice rule (fixed before any candidate was scored against the reference): score = max over the two loads of
max(a1 / 0.3, a2 / 0.018, a3 / 0.6, a4 / 0.3, median_eval_s / 1.0) (0.6 x every A1-A5 threshold); the chosen candidate is
the lowest score; meets_targets = chosen has median <= 1 s and a1 <= 0.3 K and a2 <= 0.018 at both loads.

Run: ``uv run python research/o002_l1/design_study.py`` (resumes from the cache); ``--smoke`` checks the code paths only: 1 new
layout per stratum, E009's coarse smoke rule (config.smoke_fem_overrides) in place of the frozen rule, cache in $TMPDIR,
no P_ref assertion, output design_study_smoke.json.
"""
from __future__ import annotations

import os

for _v in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS",
           "NUMEXPR_NUM_THREADS"):
    os.environ[_v] = "1"

import argparse  # noqa: E402
import gc  # noqa: E402
import hashlib  # noqa: E402
import json  # noqa: E402
import resource  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402
from contextlib import contextmanager  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402
import yaml  # noqa: E402

from moduleforge.generate.halfbridge import generate_layouts  # noqa: E402
from moduleforge.solvers import thermal_fem as FEM  # noqa: E402
from moduleforge.solvers import thermal_layout as TL  # noqa: E402
from moduleforge.solvers import thermal_series as TS  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "research" / "o002_l1"
CACHE = OUT / "cache"
FROZEN = ROOT / "research" / "o007_dev3" / "frozen_config.json"
FEM_PATH = ROOT / "src" / "moduleforge" / "solvers" / "thermal_fem.py"
E009 = ROOT / "experiments" / "specs" / "E009.yaml"
SHA_PREFIX = "a216d5fe"
TC, H = 338.15, 5000.0
REF_LEVEL = 1
ENERGY_TOL = 1e-6
DEV_SEED = 20261101
NEW_SEED = 20261115  # recorded development seed for the new layouts (never a sealed seed)
N_NEW = 5
N_DRAW = 40
LOADS = {"P_ref": 1.0, "half_P_ref": 0.5}
FV_RULE = {"H0_MAX": 0.004, "LAT_FRAC": 16.0, "EDGE_FRAC": 2.0, "Z_CELLS": 2}
FEM_COARSE = FEM.GridRule(h0=0.016, nz={}, default_nz=1, zrefine=True, near_margin=0.001, min_cells=2, element_order=1,
                          dz_max=0.004, edge_grading=(0.001, 2.5, 0.004, 0.5), amg_gs_sweeps=2)
L1_PICARD_TOL = 1e-2
N_MODES = 240
TARGETS = {"a1": 0.3, "a2": 0.018, "a3": 0.6, "a4": 0.3, "t": 1.0}
BOOT_B, BOOT_SEED = 1000, 20261116


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def rss_gb() -> float:
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e9  # bytes on darwin


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def frozen_rule() -> tuple[FEM.GridRule, dict]:
    fr = json.loads(FROZEN.read_text())
    spec = yaml.safe_load(E009.read_text())["config"]
    assert spec["fem_rule"] == fr, "frozen_config.json differs from E009 config.fem_rule"
    eg = fr["edge_grading"]
    rule = FEM.GridRule(h0=float(fr["h0_m"]), nz={}, default_nz=int(fr["nz_min"]), zrefine=bool(fr["zrefine"]),
                        near_margin=float(fr["near_margin_m"]), min_cells=int(fr["min_cells"]),
                        element_order=int(fr["element_order"]), dz_max=float(fr["dz_max_m"]),
                        edge_grading=(float(eg["first_offset_m"]), float(eg["ratio"]), float(eg["max_offset_m"]),
                                      float(eg["min_gap_fraction"])),
                        amg_gs_sweeps=int(fr["amg_gs_sweeps"]))
    return rule, spec


# ------------------------------------------------------------------------------------------------ layouts
def die_size_mm(lay) -> float:
    s = {(round(d.w * 1e3, 6), round(d.h * 1e3, 6)) for d in lay.dies}
    assert len(s) == 1 and next(iter(s))[0] == next(iter(s))[1], s
    return next(iter(s))[0]


def build_layouts(spec: dict, n_new: int) -> list[dict]:
    out = []
    for name, fam, k in spec["dev_layouts"]:
        dev = generate_layouts(1, DEV_SEED, family=fam, dies_per_switch=k)[0]
        assert dev.fingerprint() == spec["dev_fingerprints"][name], name
        s = die_size_mm(dev)
        stratum = f"{fam}/{k}"
        out.append({"name": name, "layout": dev, "family": fam, "dies": k, "die_size_mm": s, "stratum": stratum,
                    "role": "dev", "seed": DEV_SEED, "index_in_stream": 0})
        pool = generate_layouts(N_DRAW, NEW_SEED, family=fam, dies_per_switch=k)
        seen = {dev.fingerprint()}
        taken = 0
        for i, lay in enumerate(pool):
            if taken >= n_new:
                break
            if die_size_mm(lay) != s or lay.fingerprint() in seen:
                continue
            seen.add(lay.fingerprint())
            out.append({"name": f"{fam}_{k}_n{taken}", "layout": lay, "family": fam, "dies": k, "die_size_mm": s,
                        "stratum": stratum, "role": "new", "seed": NEW_SEED, "index_in_stream": i})
            taken += 1
        assert taken == n_new, f"{stratum}: only {taken} layouts of die size {s} mm in {N_DRAW} draws"
    return out


def switch_groups(lay) -> dict[str, list[int]]:
    g: dict[str, list[int]] = {}
    for i, d in enumerate(lay.dies):
        g.setdefault(d.switch, []).append(i)
    return g


def bottom_area(lay) -> float:
    return float(lay.baseplate_outline.area)


def t_bp(lay, p_die: float) -> float:
    return TC + p_die * len(lay.dies) / (H * bottom_area(lay))


# ------------------------------------------------------------------------------------------------ reference
def bottom_mean_fem(res) -> float:
    """Area mean of the Q1 nodal field over z = 0 (trapezoid weights = exact bilinear integral on the tensor grid)."""
    nodes, T = res.nodes, res.T
    zmin = float(nodes[:, 2].min())
    m = np.abs(nodes[:, 2] - zmin) < 1e-12
    x, y, t = nodes[m, 0], nodes[m, 1], T[m]
    xs, ys = np.unique(np.round(x, 12)), np.unique(np.round(y, 12))
    assert xs.size * ys.size == t.size, "baseplate bottom is not a full tensor grid"

    def w(v):
        d = np.diff(v)
        ww = np.zeros(v.size)
        ww[:-1] += 0.5 * d
        ww[1:] += 0.5 * d
        return ww

    ix = np.searchsorted(xs, np.round(x, 12))
    iy = np.searchsorted(ys, np.round(y, 12))
    W = w(xs)[ix] * w(ys)[iy]
    return float(np.dot(W, t) / W.sum())


def ref_solve(row: dict, p_die: float, tag: str, rule: FEM.GridRule, level: int, sha: str, allow: bool) -> dict:
    lay = row["layout"]
    key = f"{lay.fingerprint()[:16]}__L{level}__{tag}"
    f = CACHE / f"{key}.json"
    if f.exists():
        d = json.loads(f.read_text())
        assert d["thermal_fem_sha256"] == sha and abs(d["power_W_per_die"] - p_die) < 1e-9, key
        return d
    log(f"reference {row['name']} {tag} L{level} P={p_die:.4f} W/die ({FEM.estimate_dofs(lay, rule, level)} DOF est.)")
    t0 = time.perf_counter()
    r = FEM.solve_layout(lay, p_die, H, TC, rule=rule, level=level)
    wall = time.perf_counter() - t0
    assert r.meta["amg_gs_sweeps"] == rule.amg_gs_sweeps
    if not r.energy_balance <= ENERGY_TOL:
        raise RuntimeError(f"{key}: energy balance {r.energy_balance:.3e} > {ENERGY_TOL}")
    bm = bottom_mean_fem(r)
    d = {"key": key, "name": row["name"], "fingerprint": lay.fingerprint(), "stratum": row["stratum"], "level": level,
         "load": tag, "power_W_per_die": p_die, "P_total_W": p_die * len(lay.dies), "h_W_m2K": H, "T_c_K": TC,
         "tj_mean_K": [float(v) for v in r.tj_mean], "tj_max_K": [float(v) for v in r.tj_max],
         "die_switch": [dd.switch for dd in lay.dies], "energy_balance": float(r.energy_balance),
         "picard_iters": int(r.picard_iters), "picard_residual_K": float(r.picard_residual), "dofs": int(r.dofs),
         "wall_s": wall, "peak_rss_GB_process": rss_gb(), "cg_max_iterations": int(r.meta["cg_max_iterations"]),
         "cg_hit_maxiter": bool(r.meta["cg_hit_maxiter"]), "bottom_mean_K_solve": bm,
         "bottom_mean_K_analytic": t_bp(lay, p_die), "thermal_fem_sha256": sha, "rule": "frozen E009 fem_rule"}
    CACHE.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(d, indent=1))
    del r
    gc.collect()
    log(f"  done {wall:.0f} s, eb {d['energy_balance']:.1e}, bottom mean solve-analytic "
        f"{bm - d['bottom_mean_K_analytic']:+.2e} K, peak RSS {d['peak_rss_GB_process']:.2f} GB")
    return d


# ------------------------------------------------------------------------------------------------ candidates
@contextmanager
def fv_rule(rule: dict):
    old = {k: getattr(TL, k) for k in rule}
    try:
        for k, v in rule.items():
            setattr(TL, k, v)
        yield
    finally:
        for k, v in old.items():
            setattr(TL, k, v)


def fv_eval(lay, p_die: float, *, h: float, T_c: float, constant_k: bool = False) -> dict:
    with fv_rule(FV_RULE):
        o = TL.solve_layout_level(lay, level=0, power_W=p_die, h=h, T_c=T_c, constant_k=constant_k,
                                  picard_tol=L1_PICARD_TOL)
        vals = [TL._die_values(o["result"], d.bounds) for d in lay.dies]
    return {"tj_mean": np.array([v["tj_mean"] for v in vals]), "tj_max": np.array([v["tj_max"] for v in vals]),
            "energy_balance": o["meta"]["energy_balance"], "n": o["meta"]["n_cells"]}


def fem_eval(lay, p_die: float, *, h: float, T_c: float, constant_k: bool = False) -> dict:
    r = FEM.solve_layout(lay, p_die, h, T_c, rule=FEM_COARSE, level=0, constant_k=constant_k, picard_tol=L1_PICARD_TOL)
    return {"tj_mean": np.asarray(r.tj_mean), "tj_max": np.asarray(r.tj_max), "energy_balance": r.energy_balance,
            "n": r.dofs}


class SeriesHousing:
    """Per-housing precomputation: baseplate rectangle and the separable mode factors; gains G recomputed per k set."""

    NAMES = ("baseplate", "solder", "backside_cu", "ceramic", "top_cu")

    def __init__(self, lay, n_modes: int = N_MODES):
        x0, y0, x1, y1 = lay.baseplate_outline.bounds
        self.x0, self.y0, self.a, self.b, self.n = x0, y0, x1 - x0, y1 - y0, n_modes
        self.layers = [lay.stack.layer(nm) for nm in self.NAMES]
        m = np.arange(n_modes)
        self.ax, self.by = m * np.pi / self.a, m * np.pi / self.b
        self.ex = np.where(m == 0, 1.0, 2.0) / self.a
        self.ey = np.where(m == 0, 1.0, 2.0) / self.b

    def gain(self, ks):
        return TS._mode_gain(self.a, self.b, [(la.thickness, k) for la, k in zip(self.layers, ks, strict=True)], H,
                             self.n)[2]

    def influence(self, lay, G) -> np.ndarray:
        """R[i, j]: mean rise over die i's footprint (top of top Cu) per watt in die j (uniform flux)."""
        ix, iy = [], []
        for d in lay.dies:
            bx0, by0, bx1, by1 = d.bounds
            ix.append(TS._cos_integrals(self.ax, bx0 - self.x0, bx1 - self.x0) / (bx1 - bx0))
            iy.append(TS._cos_integrals(self.by, by0 - self.y0, by1 - self.y0) / (by1 - by0))
        ix, iy = np.array(ix), np.array(iy)  # (n_die, n_modes): mean of cos over the die extent
        cx, cy = ix * self.ex, iy * self.ey  # Fourier coefficient of a unit-power source (per axis)
        X = ix[:, None, :] * cx[None, :, :]
        Y = iy[:, None, :] * cy[None, :, :]
        return np.einsum("ijm,mn,ijn->ij", X, G, Y)


def series_eval(lay, p_die: float, *, h: float, T_c: float, constant_k: bool = False, housing=None) -> dict:
    assert h == H, "the precomputed housing uses h = 5000"
    hs = housing or SeriesHousing(lay)
    P = np.full(len(lay.dies), float(p_die))
    st = lay.stack
    lays = hs.layers
    ks = [la.k for la in lays]
    k_att, k_die = st.die_attach.k, st.die.k
    tbp = T_c + P.sum() / (h * hs.a * hs.b)
    R1 = np.array([la.thickness / la.k for la in lays])
    T = None
    for _ in range(1 if constant_k else 3):
        G = hs.gain(ks)
        Tcu = T_c + hs.influence(lay, G) @ P
        A = np.array([d.w * d.h for d in lay.dies])
        d_att = P * np.array([d.attach_thickness for d in lay.dies]) / (k_att * A)
        d_die = P * np.array([d.thickness for d in lay.dies]) / (k_die * A)
        T = Tcu + d_att + d_die
        if constant_k:
            break
        # layer temperatures from the 1D resistance fractions between the baseplate bottom and the top Cu
        frac = (np.cumsum(R1) - 0.5 * R1) / R1.sum()
        tcu_m = float(Tcu.mean())
        ks = [float(la.k_at(np.array([tbp + f * (tcu_m - tbp)]))[0]) for la, f in zip(lays, frac, strict=True)]
        R1 = np.array([la.thickness / k for la, k in zip(lays, ks, strict=True)])
        k_att = float(st.die_attach.k_at(np.array([float((Tcu + 0.5 * d_att).mean())]))[0])
        k_die = float(st.die.k_at(np.array([float((Tcu + d_att + 0.5 * d_die).mean())]))[0])
    return {"tj_mean": T, "tj_max": None, "energy_balance": 0.0, "n": hs.n**2}


def box_calibration(die_mm: float, stack) -> dict:
    """c_box: exact series local rise / same-rule FV local rise of one centred die on the 7-layer box stack (constant k,
    1 W). Box 30 x 30 mm. Series checked by doubling n_modes."""
    a = b = 0.030
    s = die_mm * 1e-3
    names = SeriesHousing.NAMES
    layers = [(stack.layer(n).thickness, stack.layer(n).k) for n in names]
    layers += [(stack.die_attach.thickness, stack.die_attach.k), (stack.die.thickness, stack.die.k)]
    src = (0.5 * (a - s), 0.5 * (a + s), 0.5 * (b - s), 0.5 * (b + s), 1.0)
    base = TC + 1.0 / (H * a * b)
    ser = {n: TS.box_series(a, b, layers, [src], h=H, T_c=TC, n_modes=n)["src0.tj_mean"] for n in (400, 800)}
    with fv_rule(FV_RULE):
        fv = TL.solve_box_level(a, b, layers, [src], h=H, T_c=TC, level=0)["values"]["src0.tj_mean"]
    rs, rf = ser[800] - base, fv - base
    return {"c_box": rs / rf, "series_rise_K_per_W": rs, "fv_rise_K_per_W": rf,
            "series_n400_minus_n800_K": ser[400] - ser[800], "box_m": [a, b]}


# ------------------------------------------------------------------------------------------------ statistics
def p95(v) -> float:
    v = np.asarray(v, float)
    return float(np.percentile(v, 95)) if v.size else float("nan")


def stats_rows(rows: list[dict], pred: dict, load: str, idx=None) -> dict:
    """Per-load A1-A3 error vectors. rows: layout rows; pred[name][load] = predicted tj_mean array; idx: layout
    multiset (bootstrap), default all."""
    idx = list(range(len(rows))) if idx is None else idx
    a1, a2, a3 = [], [], []
    by_s: dict[str, list[int]] = {}
    for j in idx:
        by_s.setdefault(rows[j]["stratum"], []).append(j)
    for js in by_s.values():
        for u in range(len(js)):
            for v in range(u + 1, len(js)):
                ja, jb = js[u], js[v]
                if rows[ja]["name"] == rows[jb]["name"]:
                    continue  # self-pair (bootstrap duplicate)
                ra, rb = rows[ja]["ref"][load], rows[jb]["ref"][load]
                ha, hb = int(np.argmax(ra)), int(np.argmax(rb))
                ma, mb = pred[rows[ja]["name"]][load], pred[rows[jb]["name"]][load]
                a1.append(abs((ma[ha] - mb[hb]) - (ra[ha] - rb[hb])))
    for j in idx:
        r, m = rows[j]["ref"][load], pred[rows[j]["name"]][load]
        a2.extend(np.abs(m - r) / (r - rows[j]["tbp"][load]))
        for g in rows[j]["groups"].values():
            a3.append(abs((m[g].max() - m[g].min()) - (r[g].max() - r[g].min())))
    return {"a1": a1, "a2": a2, "a3": a3}


def null_preds(rows: list[dict]) -> tuple[dict, dict]:
    """stratum_mean and die_position predictions (LOLO within stratum) of tj_mean, and the stratum-mean spread."""
    sm, dp, sm_spread = {}, {}, {}
    for r in rows:
        others = [o for o in rows if o["stratum"] == r["stratum"] and o["name"] != r["name"]]
        sm[r["name"]], dp[r["name"]], sm_spread[r["name"]] = {}, {}, {}
        for load in LOADS:
            sm[r["name"]][load] = np.full(len(r["ref"][load]), np.mean([o["ref"][load].mean() for o in others]))
            dp[r["name"]][load] = np.mean([o["ref"][load] for o in others], axis=0)
            sm_spread[r["name"]][load] = {w: float(np.mean([o["ref"][load][o["groups"][w]].max()
                                                            - o["ref"][load][o["groups"][w]].min() for o in others]))
                                          for w in r["groups"]}
    return {"stratum_mean": sm, "die_position": dp}, sm_spread


def a3_null(rows: list[dict], sm_spread: dict, load: str, idx=None) -> list[float]:
    idx = list(range(len(rows))) if idx is None else idx
    out = []
    for j in idx:
        r = rows[j]["ref"][load]
        for w, g in rows[j]["groups"].items():
            out.append(abs(sm_spread[rows[j]["name"]][load][w] - (r[g].max() - r[g].min())))
    return out


def summarize(rows, pred, sm_spread, load, idx=None, spread_null: bool = False) -> dict:
    """spread_null: the model's spread is the stratum-mean spread (the stratum_mean null's A3/A4)."""
    e = stats_rows(rows, pred, load, idx)
    den = p95(a3_null(rows, sm_spread, load, idx))
    if spread_null:
        e["a3"] = a3_null(rows, sm_spread, load, idx)
    return {"a1_pair_err_p95_K": p95(e["a1"]), "a2_rel_err_p95": p95(e["a2"]), "a3_spread_err_p95_K": p95(e["a3"]),
            "a4_ratio_vs_stratum_mean": p95(e["a3"]) / den if den > 0 else float("nan"),
            "n_pairs": len(e["a1"]), "n_dies": len(e["a2"]), "n_switches": len(e["a3"])}


def bootstrap(rows, pred, sm_spread, load, spread_null: bool = False) -> dict:
    """Indicative layout-clustered percentile bootstrap (layouts resampled within strata; LOLO nulls held fixed)."""
    rng = np.random.default_rng(BOOT_SEED)
    by_s: dict[str, list[int]] = {}
    for j, r in enumerate(rows):
        by_s.setdefault(r["stratum"], []).append(j)
    keys = ("a1_pair_err_p95_K", "a2_rel_err_p95", "a3_spread_err_p95_K", "a4_ratio_vs_stratum_mean")
    acc = {k: [] for k in keys}
    for _ in range(BOOT_B):
        idx = [int(j) for js in by_s.values() for j in rng.choice(js, size=len(js), replace=True)]
        s = summarize(rows, pred, sm_spread, load, idx, spread_null)
        for k in keys:
            acc[k].append(s[k])
    return {k: [float(np.nanpercentile(v, 2.5)), float(np.nanpercentile(v, 97.5))] for k, v in acc.items()}


def per_stratum(rows, pred, sm_spread, load, spread_null: bool = False) -> dict:
    out = {}
    for s in sorted({r["stratum"] for r in rows}):
        idx = [j for j, r in enumerate(rows) if r["stratum"] == s]
        out[s] = summarize(rows, pred, sm_spread, load, idx, spread_null)
    return out


# ------------------------------------------------------------------------------------------------ main
def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true")
    args = ap.parse_args(argv)
    sha = sha256(FEM_PATH)
    assert sha.startswith(SHA_PREFIX), f"thermal_fem.py sha256 {sha} does not start with {SHA_PREFIX}"
    rule, spec = frozen_rule()
    global CACHE
    if args.smoke:
        ov = spec["smoke_fem_overrides"]
        eg = ov["edge_grading"]
        rule = FEM.GridRule(h0=ov["h0_m"], nz={}, default_nz=1, zrefine=True, near_margin=ov["near_margin_m"],
                            min_cells=2, element_order=1, dz_max=ov["dz_max_m"], edge_grading=(
                                eg["first_offset_m"], eg["ratio"], eg["max_offset_m"], eg["min_gap_fraction"]),
                            amg_gs_sweeps=2)
        CACHE = Path(os.environ.get("TMPDIR", "/tmp")) / "o002_l1_smoke_cache"
    p_ref = spec["dev_regression_guard"]["calibrated_power_W_per_die"]
    t_start = time.perf_counter()
    rows = build_layouts(spec, 1 if args.smoke else N_NEW)
    log(f"{len(rows)} layouts: " + ", ".join(f"{r['name']}({r['die_size_mm']} mm)" for r in rows))

    # P_ref re-check: level-0 hottest node of each dev layout at its calibrated power
    cal = {}
    for r in rows:
        if r["role"] != "dev":
            continue
        d0 = ref_solve(r, float(p_ref[r["name"]]), "P_ref_cal_check", rule, 0, sha, allow=True)
        cal[r["stratum"]] = {"dev_layout": r["name"], "P_ref_W_per_die": float(p_ref[r["name"]]),
                             "level0_hottest_node_rise_K": max(d0["tj_max_K"]) - TC, "energy_balance":
                             d0["energy_balance"], "source": "E009 config.dev_regression_guard.calibrated_power_W_per_die"}
        if not args.smoke:
            assert abs(cal[r["stratum"]]["level0_hottest_node_rise_K"] - 60.0) <= 0.25, cal[r["stratum"]]
    solves = []
    for r in rows:
        r["groups"] = {w: np.array(g) for w, g in switch_groups(r["layout"]).items()}
        r["P"] = {ld: f * cal[r["stratum"]]["P_ref_W_per_die"] for ld, f in LOADS.items()}
        r["tbp"] = {ld: t_bp(r["layout"], p) for ld, p in r["P"].items()}
        r["ref"], r["ref_max"] = {}, {}
        for ld, p in r["P"].items():
            d = ref_solve(r, p, ld, rule, REF_LEVEL, sha, allow=True)
            r["ref"][ld], r["ref_max"][ld] = np.array(d["tj_mean_K"]), np.array(d["tj_max_K"])
            solves.append(d)
    ref_cpu_s = sum(d["wall_s"] for d in solves)

    # ---- candidates: precomputation, then timed evaluations
    pre = {}
    t0 = time.perf_counter()
    housings = {r["name"]: SeriesHousing(r["layout"]) for r in rows}
    pre["series_superposition"] = {"wall_s_total": time.perf_counter() - t0, "what": "baseplate-rectangle mode factors"}
    t0 = time.perf_counter()
    boxcal = {s: box_calibration(s, rows[0]["layout"].stack) for s in sorted({r["die_size_mm"] for r in rows})}
    pre["fv_coarse_boxcal"] = {"wall_s_total": time.perf_counter() - t0, "c_box": boxcal}
    raw_fns = {"fv_coarse": fv_eval, "fem_coarse": fem_eval,
               "series_superposition": lambda lay, p, **kw: series_eval(lay, p, housing=housings[cur], **kw)}
    raw, tmax, times, ebs, sizes = {}, {}, {}, {}, {}
    for cname, fn in raw_fns.items():
        raw[cname], tmax[cname], times[cname], ebs[cname], sizes[cname] = {}, {}, [], [], []
        for r in rows:
            cur = r["name"]  # noqa: F841 (read by the series lambda)
            raw[cname][cur], tmax[cname][cur] = {}, {}
            for ld, p in r["P"].items():
                fn(r["layout"], p, h=H, T_c=TC)  # warm-up (imports, caches), not timed
                ts = []
                for _ in range(3):
                    tt = time.perf_counter()
                    o = fn(r["layout"], p, h=H, T_c=TC)
                    ts.append(time.perf_counter() - tt)
                times[cname].append(float(np.median(ts)))
                raw[cname][cur][ld], tmax[cname][cur][ld] = o["tj_mean"], o["tj_max"]
                ebs[cname].append(float(o["energy_balance"]))
                sizes[cname].append(int(o["n"]))
        log(f"{cname}: median {np.median(times[cname]):.3f} s, max eb {max(ebs[cname]):.1e}")

    def scaled(src: dict, c_of) -> dict:
        out = {}
        for r in rows:
            c = c_of(r)
            out[r["name"]] = {ld: r["tbp"][ld] + c * (src[r["name"]][ld] - r["tbp"][ld]) for ld in LOADS}
        return out

    def xcal_factor(src: dict, r: dict) -> float:
        dev = [o for o in rows if o["role"] == "dev" and o["stratum"] != r["stratum"]][0]
        return float(np.mean((dev["ref"]["P_ref"] - dev["tbp"]["P_ref"])
                             / (src[dev["name"]]["P_ref"] - dev["tbp"]["P_ref"])))

    preds = {"fv_coarse": raw["fv_coarse"],
             "fv_coarse_boxcal": scaled(raw["fv_coarse"], lambda r: boxcal[r["die_size_mm"]]["c_box"]),
             "fv_coarse_xcal": scaled(raw["fv_coarse"], lambda r: xcal_factor(raw["fv_coarse"], r)),
             "fem_coarse": raw["fem_coarse"],
             "fem_coarse_xcal": scaled(raw["fem_coarse"], lambda r: xcal_factor(raw["fem_coarse"], r)),
             "series_superposition": raw["series_superposition"]}
    base_of = {"fv_coarse": "fv_coarse", "fv_coarse_boxcal": "fv_coarse", "fv_coarse_xcal": "fv_coarse",
               "fem_coarse": "fem_coarse", "fem_coarse_xcal": "fem_coarse", "series_superposition": "series_superposition"}
    xcal = {c: {r["stratum"]: xcal_factor(raw[c], r) for r in rows} for c in ("fv_coarse", "fem_coarse")}

    nulls, sm_spread = null_preds(rows)
    out_c, out_ps, scores = {}, {}, {}
    for cname, pr in preds.items():
        med = float(np.median(times[base_of[cname]]))
        out_c[cname] = {}
        for ld in LOADS:
            s = summarize(rows, pr, sm_spread, ld)
            s["median_eval_s"] = med
            s["bootstrap95_indicative"] = bootstrap(rows, pr, sm_spread, ld)
            out_c[cname][ld] = s
        out_ps[cname] = {ld: per_stratum(rows, pr, sm_spread, ld) for ld in LOADS}
        scores[cname] = max(max(out_c[cname][ld]["a1_pair_err_p95_K"] / TARGETS["a1"],
                                out_c[cname][ld]["a2_rel_err_p95"] / TARGETS["a2"],
                                out_c[cname][ld]["a3_spread_err_p95_K"] / TARGETS["a3"],
                                out_c[cname][ld]["a4_ratio_vs_stratum_mean"] / TARGETS["a4"], med / TARGETS["t"])
                            for ld in LOADS)
    out_n = {}
    for nname, pr in nulls.items():
        sn = nname == "stratum_mean"
        out_n[nname] = {ld: summarize(rows, pr, sm_spread, ld, spread_null=sn) for ld in LOADS}
        for ld in LOADS:
            out_n[nname][ld]["per_stratum"] = per_stratum(rows, pr, sm_spread, ld, sn)
            out_n[nname][ld]["bootstrap95_indicative"] = bootstrap(rows, pr, sm_spread, ld, sn)
    chosen = min(scores, key=scores.get)
    ch = out_c[chosen]
    meets = bool(all(ch[ld]["median_eval_s"] <= TARGETS["t"] and ch[ld]["a1_pair_err_p95_K"] <= TARGETS["a1"]
                     and ch[ld]["a2_rel_err_p95"] <= TARGETS["a2"] for ld in LOADS))
    f2 = bool(any(out_n[n]["P_ref"]["a1_pair_err_p95_K"] <= 0.5 for n in out_n))

    # F4 preview: constant-k ablation of the chosen method's base solver (k = Layer.k = k_at(300 K))
    f4 = {}
    base = base_of[chosen]
    if base in ("fv_coarse", "fem_coarse"):
        ck = {}
        for r in rows:
            fn = fv_eval if base == "fv_coarse" else fem_eval
            ck[r["name"]] = {ld: fn(r["layout"], p, h=H, T_c=TC, constant_k=True)["tj_mean"] for ld, p in r["P"].items()}
        if chosen.endswith("boxcal"):
            ck = scaled(ck, lambda r: boxcal[r["die_size_mm"]]["c_box"])
        elif chosen.endswith("xcal"):
            ck = scaled(ck, lambda r: xcal_factor(raw[base], r))
        f4 = {ld: {k: v for k, v in summarize(rows, ck, sm_spread, ld).items() if not k.startswith("n_")}
              for ld in LOADS}
        f4["k_held_at"] = "Layer.k = k_at(T_REF = 300 K) for every layer (the reference's constant_k convention)"

    # sanity / diversity
    hot_sd = {s: {ld: float(np.std([r["ref"][ld].max() for r in rows if r["stratum"] == s], ddof=1)) for ld in LOADS}
              for s in sorted({r["stratum"] for r in rows})}
    bm_dev = max(abs(d["bottom_mean_K_solve"] - d["bottom_mean_K_analytic"]) for d in solves)
    linear = {}
    for cname in ("fv_coarse", "fem_coarse"):  # P_ref / half-P_ref rise ratio, ~2 minus the k(T) effect
        linear[cname] = float(np.median([np.mean((raw[cname][r["name"]]["P_ref"] - TC)
                                                 / (raw[cname][r["name"]]["half_P_ref"] - TC)) for r in rows]))
    linear["reference"] = float(np.median([np.mean((r["ref"]["P_ref"] - TC) / (r["ref"]["half_P_ref"] - TC))
                                           for r in rows]))
    hotgap = {s: {ld: float(max((r["ref_max"][ld] - r["ref"][ld]).max() for r in rows if r["stratum"] == s))
                  for ld in LOADS} for s in hot_sd}
    result = {
        "task": "T0392", "objective": "O002", "kind": "design study (development geometry only; not evidence)",
        "generated": time.strftime("%Y-%m-%dT%H:%M:%S"), "smoke": bool(args.smoke),
        "dev_seed": DEV_SEED, "new_layout_seed": NEW_SEED, "n_draw_per_stratum": N_DRAW,
        "operating_point": {"T_c_K": TC, "h_W_m2K": H, "kT": True, "loads": LOADS, "P_ref_calibration": cal},
        "reference": {"solver": "moduleforge.solvers.thermal_fem.solve_layout", "level": REF_LEVEL,
                      "rule": "research/o007_dev3/frozen_config.json (E009 fem_rule)", "thermal_fem_sha256": sha,
                      "frozen_config_sha256": sha256(FROZEN), "cpu_s_total": ref_cpu_s,
                      "peak_rss_GB_max": max(d["peak_rss_GB_process"] for d in solves),
                      "bottom_mean_solve_minus_analytic_max_K": bm_dev, "energy_tol": ENERGY_TOL},
        "layouts": [{"name": r["name"], "fingerprint": r["layout"].fingerprint(), "family": r["family"],
                     "dies": r["dies"], "die_size_mm": r["die_size_mm"], "stratum": r["stratum"], "role": r["role"],
                     "seed": r["seed"], "index_in_stream": r["index_in_stream"],
                     "power_W_per_die": r["P"]} for r in rows],
        "reference_solves": [{k: d[k] for k in ("name", "fingerprint", "stratum", "level", "load", "power_W_per_die",
                                                "energy_balance", "picard_iters", "dofs", "wall_s",
                                                "peak_rss_GB_process", "cg_max_iterations", "cg_hit_maxiter",
                                                "bottom_mean_K_solve", "bottom_mean_K_analytic")} for d in solves],
        "candidates": out_c, "candidates_per_stratum": out_ps,
        "candidate_info": {"precomputation": pre, "xcal_factor_by_stratum": xcal, "scores": scores,
                           "eval_times_s": times, "model_size": {k: [min(v), max(v)] for k, v in sizes.items()},
                           "energy_balance_max": {k: max(v) for k, v in ebs.items()},
                           "fv_rule": FV_RULE, "fem_coarse_rule": repr(FEM_COARSE), "picard_tol_K": L1_PICARD_TOL,
                           "series_n_modes": N_MODES},
        "nulls": out_n, "chosen": chosen, "meets_targets": meets, "f2_warning": f2, "targets": TARGETS,
        "f4_constant_k_preview": f4,
        "sanity": {"hottest_die_sd_K_by_stratum": hot_sd, "power_ratio_rise_median": linear,
                   "hottest_node_minus_die_average_max_K": hotgap},
        "wall_s_total": time.perf_counter() - t_start,
    }
    name = "design_study_smoke.json" if args.smoke else "design_study.json"
    (OUT / name).write_text(json.dumps(result, indent=1, default=float))
    log(f"wrote {name}: chosen {chosen} (score {scores[chosen]:.2f}), meets_targets {meets}, f2_warning {f2}")
    for cname in out_c:
        log(f"  {cname:22s} " + " | ".join(
            f"{ld}: a1 {out_c[cname][ld]['a1_pair_err_p95_K']:.3f} a2 {out_c[cname][ld]['a2_rel_err_p95']:.4f} "
            f"a3 {out_c[cname][ld]['a3_spread_err_p95_K']:.3f} a4 {out_c[cname][ld]['a4_ratio_vs_stratum_mean']:.2f}"
            for ld in LOADS) + f" | t {out_c[cname]['P_ref']['median_eval_s']:.3f} s")
    for nname in out_n:
        log(f"  null {nname:17s} " + " | ".join(
            f"{ld}: a1 {out_n[nname][ld]['a1_pair_err_p95_K']:.3f} a4 {out_n[nname][ld]['a4_ratio_vs_stratum_mean']:.2f}"
            for ld in LOADS))
    return 0


if __name__ == "__main__":
    sys.exit(main())
