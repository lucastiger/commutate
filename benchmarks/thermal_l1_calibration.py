"""Derivation of the L1 calibration table c(s) and the T0395 fresh-seed spread (A4-type) check.  Development data only.

This script produces the data behind ``moduleforge.thermal.CALIBRATION`` and the A4 section of docs/thermal_l1.md.  It is
not evidence (E007 is).  Every reference solve is cached as a per-solve summary (no fields) in
tests/regression/data/o002_l1_cal/, so a re-run resumes and the regression test can re-derive the table without solving.

Reference. ``thermal_fem.solve_layout`` at the frozen GridRule (research/o007_dev3/frozen_config.json, asserted equal to
E009 config.fem_rule), level 1, k(T), T_c = 338.15 K, h = 5000 W/(m2 K), equal power per die; energy balance <= 1e-6 asserted;
one solve at a time (peak about 4 GB).  P_ref per layout is C004's calibration rule exactly as E009's ``calibrate_power``:
level-0 solves of the frozen rule from 30 W, proportional update p <- 60 p / rise until the hottest die's Tj max rises
60 +/- 0.25 K above the coolant (at most 10 solves).

Calibration rows (``cal``).  For each generator die size s in {4.0, 4.5, 5.0, 5.5} mm and each of C004's two development
strata (E009 config.dev_layouts: side_by_side/6, u_shaped/2), the first layout of E009's development seed 20261101 with the
die size fixed to s (``generate_layouts(1, 20261101, family, dies, die_size_mm=s)``).  At s = 5.0 mm these are E009's
development layouts themselves (fingerprints asserted) and their P_ref and level-1 values are the T0392 cache
(tests/regression/data/o002_l1_dev/); no new solve.  c(s) = mean over the two layouts of the mean over dies of
(reference rise) / (coarse-FV rise), rise = Tj_mean - T_bp, T_bp = T_c + P_total / (h A_bottom) (design note section 4:
"at least two layouts of different families per size").

Validation rows (``val``).  The founder's A4 question (T0395 packet): does a finer coarse grid or a per-switch correction
improve the 2-die stratum within A5's 1 s?  The design note (risk 1) requires such a trial on a new development seed, not
the T0392 rows.  Recorded development seed VAL_SEED = 20261395 (not a date; never a sealed seed): for each family, the
first 6 DRC-valid 2-die layouts with 5.0 mm dies (``die_size_mm=5.0``), P_ref by C004's rule on the first layout of the
stratum, level-1 reference at P_ref on all six.

Decision rule (written before any variant was scored on the validation rows).  Variants of the coarse lateral cap
``h0_max``: 4 mm (n1's frozen rule), 1.5 mm and 1 mm (the two settings attempt 1 found best on the T0392 rows); every
variant gets its own c(s) from the calibration rows.  Adopt the variant with the lowest pooled 2-die A4-type ratio on the
validation rows at P_ref among those that (i) beat n1's rule there, (ii) keep A1-type <= 0.3 K and A2-type <= 1.8 % on the
validation rows and on the T0392 development rows at both loads, (iii) have a median evaluation <= 0.6 s on one thread
over the T0392 rows (A5 headroom for machine load).  If none qualifies, keep n1's rule.  The per-switch correction (a
spread scale d fitted on the T0392 rows, applied to the validation rows) is scored for the report only.

Statistics are the design study's point estimates (numpy linear p95): A1-type over same-stratum layout pairs of the
reference-hottest die; A2-type over dies, relative to the reference die-local rise; A3-type over (layout, switch) of the
spread (max - min of die means); A4-type = A3-type p95 / p95 of the leave-one-layout-out stratum-mean-spread null.

Run (one thread): ``uv run python benchmarks/thermal_l1_calibration.py solve cal`` / ``solve val`` (reference solves,
resumable), ``report --json benchmarks/results/thermal_l1_calibration.json`` (variants, c(s), A1/A2/A4, timing; no
reference solve).

Outcome (T0395, 2026-11-16; numbers in docs/thermal_l1.md and benchmarks/results/thermal_l1_calibration.json): the rule
selected h0_max 1.5 mm (validation 2-die A4-type 0.21 against n1's 0.69; 1 mm gave 0.22); it is ``moduleforge.thermal.GRID_RULE``
and its c(s) is ``CALIBRATION``.
"""
from __future__ import annotations

import os

for _v in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[_v] = "1"

import argparse  # noqa: E402
import gc  # noqa: E402
import hashlib  # noqa: E402
import json  # noqa: E402
import resource  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402
import yaml  # noqa: E402

from moduleforge.generate.halfbridge import FAMILIES, generate_layouts  # noqa: E402
from moduleforge.thermal import GRID_RULE, raw_fv  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CAL_DIR = ROOT / "tests" / "regression" / "data" / "o002_l1_cal"
DEV_DIR = ROOT / "tests" / "regression" / "data" / "o002_l1_dev"
FROZEN = ROOT / "research" / "o007_dev3" / "frozen_config.json"
E009 = ROOT / "experiments" / "specs" / "E009.yaml"
FEM_PATH = ROOT / "src" / "moduleforge" / "solvers" / "thermal_fem.py"
TC, H = 338.15, 5000.0
DEV_SEED, NEW_SEED, N_NEW, N_DRAW = 20261101, 20261115, 5, 40
VAL_SEED, N_VAL = 20261395, 6
SIZES = (4.0, 4.5, 5.0, 5.5)
ENERGY_TOL = 1e-6
TARGET_RISE, CAL_TOL, CAL_MAX, P_START = 60.0, 0.25, 10, 30.0
N1_RULE = {"h0_max": 4.0e-3, "lat_frac": 16.0, "edge_frac": 2.0, "z_cells": 2}  # n1's coarse rule (T0392 section 4)
VARIANTS = {"h0_max 4 mm (n1)": N1_RULE, "h0_max 1.5 mm": {**N1_RULE, "h0_max": 1.5e-3},
            "h0_max 1 mm": {**N1_RULE, "h0_max": 1.0e-3}}
LOADS = {"P_ref": 1.0, "half_P_ref": 0.5}


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def e009() -> dict:
    return yaml.safe_load(E009.read_text())["config"]


def size_mm(lay) -> float:
    return round(lay.dies[0].w * 1e3, 6)


# ------------------------------------------------------------------------------------------------ rows
def cal_rows() -> list[dict]:
    """Calibration layouts: per size, the first seed-20261101 layout of each E009 development stratum at that size."""
    spec = e009()
    rows = []
    for s in SIZES:
        for name, fam, k in spec["dev_layouts"]:
            lay = generate_layouts(1, DEV_SEED, family=fam, dies_per_switch=k, die_size_mm=s)[0]
            if s == 5.0:
                assert lay.fingerprint() == spec["dev_fingerprints"][name], name
            rows.append({"name": f"{fam}_{k}_s{s}", "dev_name": name, "layout": lay, "size": s,
                         "stratum": f"{fam}/{k}", "p_e009": spec["dev_regression_guard"]["calibrated_power_W_per_die"][name]
                         if s == 5.0 else None})
    return rows


def dev_rows() -> list[dict]:
    """The 12 T0392 development rows (as tests/regression/test_thermal_l1_dev.py builds them), with cached references."""
    spec = e009()
    p_ref = spec["dev_regression_guard"]["calibrated_power_W_per_die"]
    rows = []
    for name, fam, k in spec["dev_layouts"]:
        dev = generate_layouts(1, DEV_SEED, family=fam, dies_per_switch=k)[0]
        lays, seen = [dev], {dev.fingerprint()}
        for lay in generate_layouts(N_DRAW, NEW_SEED, family=fam, dies_per_switch=k):
            if len(lays) > N_NEW:
                break
            if size_mm(lay) == size_mm(dev) and lay.fingerprint() not in seen:
                seen.add(lay.fingerprint())
                lays.append(lay)
        for lay in lays:
            ref = {ld: np.array(json.loads((DEV_DIR / f"{lay.fingerprint()[:16]}__L1__{ld}.json").read_text())["tj_mean_K"])
                   for ld in LOADS}
            rows.append({"layout": lay, "stratum": f"{fam}/{k}", "P": {ld: f * p_ref[name] for ld, f in LOADS.items()},
                         "ref": ref})
    return rows


def val_layouts() -> list[tuple[str, list]]:
    return [(f"{fam}/2", generate_layouts(N_VAL, VAL_SEED, family=fam, dies_per_switch=2, die_size_mm=5.0))
            for fam in FAMILIES]


# ------------------------------------------------------------------------------------------------ reference
def frozen_rule():
    from moduleforge.solvers import thermal_fem as FEM

    fr = json.loads(FROZEN.read_text())
    assert e009()["fem_rule"] == fr, "frozen_config.json differs from E009 config.fem_rule"
    eg = fr["edge_grading"]
    return FEM.GridRule(h0=float(fr["h0_m"]), nz={}, default_nz=int(fr["nz_min"]), zrefine=bool(fr["zrefine"]),
                        near_margin=float(fr["near_margin_m"]), min_cells=int(fr["min_cells"]),
                        element_order=int(fr["element_order"]), dz_max=float(fr["dz_max_m"]),
                        edge_grading=(float(eg["first_offset_m"]), float(eg["ratio"]), float(eg["max_offset_m"]),
                                      float(eg["min_gap_fraction"])),
                        amg_gs_sweeps=int(fr["amg_gs_sweeps"]))


def _sha() -> str:
    return hashlib.sha256(FEM_PATH.read_bytes()).hexdigest()


def ref_solve(lay, p_die: float, level: int, tag: str, label: str) -> dict:
    """Cached per-solve summary of the frozen-rule reference at ``level`` (computed if absent)."""
    from moduleforge.solvers import thermal_fem as FEM

    f = CAL_DIR / f"{lay.fingerprint()[:16]}__L{level}__{tag}.json"
    if f.exists():
        d = json.loads(f.read_text())
        assert d["fingerprint"] == lay.fingerprint() and abs(d["power_W_per_die"] - p_die) < 1e-9, f.name
        return d
    log(f"reference {label} L{level} {tag} P = {p_die:.6f} W/die")
    t0 = time.perf_counter()
    r = FEM.solve_layout(lay, p_die, H, TC, rule=frozen_rule(), level=level)
    wall = time.perf_counter() - t0
    if not r.energy_balance <= ENERGY_TOL:
        raise RuntimeError(f"{f.name}: energy balance {r.energy_balance:.3e} > {ENERGY_TOL}")
    d = {"fingerprint": lay.fingerprint(), "label": label, "level": level, "load": tag, "power_W_per_die": p_die,
         "die_size_mm": size_mm(lay), "h_W_m2K": H, "T_c_K": TC, "tj_mean_K": [float(v) for v in r.tj_mean],
         "tj_max_K": [float(v) for v in r.tj_max], "die_switch": [d.switch for d in lay.dies],
         "energy_balance": float(r.energy_balance), "picard_iters": int(r.picard_iters), "dofs": int(r.dofs),
         "cg_hit_maxiter": bool(r.meta["cg_hit_maxiter"]), "wall_s": wall,
         "peak_rss_GB_process": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e9,
         "thermal_fem_sha256": _sha(), "rule": "frozen E009 fem_rule"}
    CAL_DIR.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(d, indent=1))
    del r
    gc.collect()
    log(f"  done {wall:.0f} s, energy balance {d['energy_balance']:.1e}, peak RSS {d['peak_rss_GB_process']:.2f} GB")
    return d


def p_ref(lay, label: str) -> float:
    """C004's rule (E009 ``calibrate_power``): level-0 solves, p <- 60 p / rise until |rise - 60| <= 0.25 K."""
    f = CAL_DIR / f"{lay.fingerprint()[:16]}__Pref.json"
    if f.exists():
        return float(json.loads(f.read_text())["P_ref_W_per_die"])
    p, hist = P_START, []
    for it in range(CAL_MAX):
        d = ref_solve(lay, p, 0, f"cal{it}", label)
        rise = max(d["tj_max_K"]) - TC
        hist.append({"power_W": p, "rise_K": rise})
        if abs(rise - TARGET_RISE) <= CAL_TOL:
            f.write_text(json.dumps({"fingerprint": lay.fingerprint(), "label": label, "P_ref_W_per_die": p,
                                     "rise_K": rise, "history": hist, "rule": "C004 / E009 calibrate_power"}, indent=1))
            return p
        p *= TARGET_RISE / rise
    raise RuntimeError(f"{label}: power calibration did not converge: {hist}")


def solve(which: str) -> None:
    if which == "cal":
        for r in cal_rows():
            if r["size"] == 5.0:
                continue  # E009's development layouts: T0392 cache
            p = p_ref(r["layout"], r["name"])
            ref_solve(r["layout"], p, 1, "P_ref", r["name"])
    else:
        for stratum, lays in val_layouts():
            p = p_ref(lays[0], f"val {stratum} #0")
            for i, lay in enumerate(lays):
                ref_solve(lay, p, 1, "P_ref", f"val {stratum} #{i}")


# ------------------------------------------------------------------------------------------------ analysis
def cal_reference(r: dict) -> tuple[float, np.ndarray]:
    lay = r["layout"]
    if r["size"] == 5.0:
        d = json.loads((DEV_DIR / f"{lay.fingerprint()[:16]}__L1__P_ref.json").read_text())
        assert abs(d["power_W_per_die"] - r["p_e009"]) < 1e-9
        return r["p_e009"], np.array(d["tj_mean_K"])
    p = float(json.loads((CAL_DIR / f"{lay.fingerprint()[:16]}__Pref.json").read_text())["P_ref_W_per_die"])
    return p, np.array(json.loads((CAL_DIR / f"{lay.fingerprint()[:16]}__L1__P_ref.json").read_text())["tj_mean_K"])


def t_bp(lay, p_die: float) -> float:
    return TC + p_die * len(lay.dies) / (H * float(lay.baseplate_outline.area))


def fit_table(rule: dict) -> dict:
    """c(s) and its per-family values for the coarse rule ``rule``."""
    out = {}
    for r in cal_rows():
        p, ref = cal_reference(r)
        fv = raw_fv(r["layout"], p, h=H, T_c=TC, grid_rule=rule)["tj_mean"]
        tb = t_bp(r["layout"], p)
        out.setdefault(r["size"], {})[r["stratum"]] = float(np.mean((ref - tb) / (fv - tb)))
    return {s: {"c": float(np.mean(list(v.values()))), "per_family": v,
                "family_spread": float(max(v.values()) - min(v.values()))} for s, v in out.items()}


def _p95(v) -> float:
    return float(np.percentile(np.asarray(v, float), 95))


def groups(lay) -> dict:
    g = {}
    for i, d in enumerate(lay.dies):
        g.setdefault(d.switch, []).append(i)
    return {k: np.array(v) for k, v in g.items()}


def stats(rows: list[dict], ld: str, spread_scale: float = 1.0) -> dict:
    """A1/A2/A3/A4-type point estimates; per stratum and pooled.  ``spread_scale`` multiplies predicted spreads."""
    out = {"a1": [], "a2": [], "num": {}, "den": {}}
    for s in sorted({r["stratum"] for r in rows}):
        rs = [r for r in rows if r["stratum"] == s]
        for i in range(len(rs)):
            for j in range(i + 1, len(rs)):
                a, b = rs[i], rs[j]
                ha, hb = int(np.argmax(a["ref"][ld])), int(np.argmax(b["ref"][ld]))
                out["a1"].append(abs((a["pred"][ld][ha] - b["pred"][ld][hb]) - (a["ref"][ld][ha] - b["ref"][ld][hb])))
        for r in rs:
            tb = t_bp(r["layout"], r["P"][ld])
            out["a2"] += list(np.abs(r["pred"][ld] - r["ref"][ld]) / (r["ref"][ld] - tb))
            for w, g in groups(r["layout"]).items():
                sp_ref = np.ptp(r["ref"][ld][g])
                out["num"].setdefault(s, []).append(abs(spread_scale * np.ptp(r["pred"][ld][g]) - sp_ref))
                null = np.mean([np.ptp(o["ref"][ld][groups(o["layout"])[w]]) for o in rs if o is not r])
                out["den"].setdefault(s, []).append(abs(null - sp_ref))
    num_all = [v for s in out["num"] for v in out["num"][s]]
    den_all = [v for s in out["den"] for v in out["den"][s]]
    return {"a1_p95_K": _p95(out["a1"]) if out["a1"] else float("nan"), "a2_p95": _p95(out["a2"]),
            "a3_p95_K": _p95(num_all), "a4_pooled": _p95(num_all) / _p95(den_all),
            "a4_by_stratum": {s: {"ratio": _p95(out["num"][s]) / _p95(out["den"][s]), "model_K": _p95(out["num"][s]),
                                  "null_K": _p95(out["den"][s])} for s in out["num"]}}


def predict(rows: list[dict], rule: dict, table: dict, timing: list | None = None) -> None:
    for r in rows:
        r["pred"] = {}
        c = table[size_mm(r["layout"])]["c"]
        for ld, p in r["P"].items():
            t0 = time.perf_counter()
            fv = raw_fv(r["layout"], p, h=H, T_c=TC, grid_rule=rule)["tj_mean"]
            tb = t_bp(r["layout"], p)
            r["pred"][ld] = tb + c * (fv - tb)
            if timing is not None:
                timing.append(time.perf_counter() - t0)


def val_rows() -> list[dict]:
    rows = []
    for stratum, lays in val_layouts():
        p = float(json.loads((CAL_DIR / f"{lays[0].fingerprint()[:16]}__Pref.json").read_text())["P_ref_W_per_die"])
        for lay in lays:
            d = json.loads((CAL_DIR / f"{lay.fingerprint()[:16]}__L1__P_ref.json").read_text())
            assert abs(d["power_W_per_die"] - p) < 1e-9
            rows.append({"layout": lay, "stratum": stratum, "P": {"P_ref": p}, "ref": {"P_ref": np.array(d["tj_mean_K"])}})
    return rows


def spread_scale_fit(rows: list[dict]) -> float:
    """Per-switch correction: least-squares d in spread_ref ~ d spread_model over (layout, switch, load) of ``rows``."""
    m, r_ = [], []
    for r in rows:
        for ld in r["pred"]:
            for g in groups(r["layout"]).values():
                m.append(np.ptp(r["pred"][ld][g]))
                r_.append(np.ptp(r["ref"][ld][g]))
    m, r_ = np.array(m), np.array(r_)
    return float(m @ r_ / (m @ m))


def report(out_json: Path | None) -> int:
    dev, val = dev_rows(), val_rows()
    res = {"grid_rule_frozen": dict(GRID_RULE), "variants": {}}
    for name, rule in VARIANTS.items():
        table = fit_table(rule)
        raw_fv(dev[0]["layout"], 30.0, h=H, T_c=TC, grid_rule=rule)  # warm-up
        times: list[float] = []
        predict(dev, rule, table, times)
        predict(val, rule, table)
        d = spread_scale_fit(dev)
        v = {"rule": rule, "table": {str(s): t for s, t in table.items()},
             "dev": {ld: stats(dev, ld) for ld in LOADS}, "val": stats(val, "P_ref"),
             "val_spread_corrected": {"d": d, **stats(val, "P_ref", spread_scale=d)},
             "t_median_s": float(np.median(times)), "t_max_s": float(np.max(times))}
        res["variants"][name] = v
        log(f"{name}: c = {', '.join(f'{s}: {t['c']:.5f} (spread {t['family_spread']:.4f})' for s, t in table.items())}")
        for ld in LOADS:
            st = v["dev"][ld]
            log(f"  dev {ld:10s} A1 {st['a1_p95_K']:.3f} K  A2 {100 * st['a2_p95']:.2f} %  A3 {st['a3_p95_K']:.3f} K  "
                f"A4 pooled {st['a4_pooled']:.2f}  " + "  ".join(f"{s} {x['ratio']:.2f}" for s, x in st["a4_by_stratum"].items()))
        st = v["val"]
        log(f"  val P_ref     A1 {st['a1_p95_K']:.3f} K  A2 {100 * st['a2_p95']:.2f} %  A3 {st['a3_p95_K']:.3f} K  "
            f"A4 pooled {st['a4_pooled']:.2f}  " + "  ".join(f"{s} {x['ratio']:.2f} ({x['model_K']:.3f}/{x['null_K']:.3f} K)"
                                                           for s, x in st["a4_by_stratum"].items()))
        sc = v["val_spread_corrected"]
        log(f"  val per-switch spread scale d = {d:.4f} (fit on dev): A4 pooled {sc['a4_pooled']:.2f}  "
            + "  ".join(f"{s} {x['ratio']:.2f}" for s, x in sc["a4_by_stratum"].items()))
        log(f"  time median {v['t_median_s']:.3f} s, max {v['t_max_s']:.3f} s (dev rows, one thread)")
    if out_json is not None:
        out_json.write_text(json.dumps(res, indent=1))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("solve")
    s.add_argument("which", choices=("cal", "val"))
    r = sub.add_parser("report")
    r.add_argument("--json", type=Path, default=None)
    a = ap.parse_args(argv)
    if a.cmd == "solve":
        assert _sha().startswith("a216d5fe3209bcee"), "thermal_fem.py changed"
        solve(a.which)
        return 0
    return report(a.json)


if __name__ == "__main__":
    sys.exit(main())
