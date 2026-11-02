"""Convergence and cost of the thermal L2 on the two A3 layouts (O006 A4, T0150).

Layouts (rule of O006 A3, dev seed 20261101): the first DRC-valid ``side_by_side`` layout with 6 dies per switch and the
first ``u_shaped`` layout with 2 dies per switch from ``generate_layouts(1, 20261101, family=..., dies_per_switch=...)``.
Conditions: coolant 65 C, h = 5000 W/(m2 K), k(T), equal power in every die.  The power is chosen once per layout by a
level-0 calibration so that the hottest Tj max rise over the coolant is 85 K (inside the required 60-110 K); the
calibration level and the rise at every level are recorded.  The grid rule is ``solvers.thermal_layout`` (frozen constants);
nothing is tuned here.

Each (layout, level) solve runs in a fresh subprocess so that wall time and peak RSS are per level.  A level that cannot
run (error, timeout) gets a status reason and null values, never an invented number; dies then have null Tj lists.

Output: ``benchmarks/results/thermal_l2_convergence.json`` =
``{mode, coolant_K, h_W_m2K, seed, layouts: [{name, fingerprint, power_per_die_W, target_rise_K, hottest_rise_K, levels:
[{level, n_cells, wall_s, peak_rss_mb, energy_balance, picard_iters, status}], dies: [{id, tj_max_K: [coarse, mid, fine],
gci_K, p_obs, tj_mean_K, gci_mean_K, tj_centroid_K, gci_centroid_K}], layout_values: {...}, max_gci_K}]}``.
``--smoke`` runs levels 0 and 1 only (level 2 is marked skipped) and writes to a temporary file, never to the results file.

Run: ``uv run python benchmarks/thermal_l2_convergence.py [--smoke] [--out PATH]``.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import resource
import subprocess
import sys
import tempfile
import time
from pathlib import Path

SEED = 20261101
T_COOLANT = 65.0 + 273.15
H = 5000.0
TARGET_RISE_K = 85.0  # inside the required 60-110 K
RISE_RANGE = (60.0, 110.0)
LAYOUTS = (("side_by_side_6", "side_by_side", 6), ("u_shaped_2", "u_shaped", 2))
LEVELS = (0, 1, 2)
CHILD_TIMEOUT_S = 3600
DEFAULT_OUT = Path(__file__).parent / "results" / "thermal_l2_convergence.json"


def get_layout(family: str, dies: int):
    from moduleforge.generate.halfbridge import generate_layouts

    return generate_layouts(1, SEED, family=family, dies_per_switch=dies)[0]


def _nan_to_none(v):
    if isinstance(v, float) and not math.isfinite(v):
        return None
    return v


def child(name: str, level: int, power: float) -> None:
    """Solve one level and print one JSON line (values, meta, peak RSS)."""
    from moduleforge.solvers import thermal_layout as tl

    fam, dies = next((f, d) for n, f, d in LAYOUTS if n == name)
    lay = get_layout(fam, dies)
    t0 = time.perf_counter()
    out = tl.solve_layout_level(lay, level=level, power_W=power, h=H, T_c=T_COOLANT)
    wall = time.perf_counter() - t0
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    rss_mb = rss / 1e6 if sys.platform == "darwin" else rss / 1e3  # bytes on macOS, KiB on Linux
    print("RESULT " + json.dumps({"values": out["values"], "meta": out["meta"], "wall_s": wall, "peak_rss_mb": rss_mb}))


def run_level(name: str, level: int, power: float) -> dict:
    cmd = [sys.executable, str(Path(__file__).resolve()), "--child", name, str(level), repr(power)]
    t0 = time.perf_counter()
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=CHILD_TIMEOUT_S, check=False)
    except subprocess.TimeoutExpired:
        return {"status": f"failed: timeout after {CHILD_TIMEOUT_S} s", "wall_s": time.perf_counter() - t0}
    lines = [ln for ln in proc.stdout.splitlines() if ln.startswith("RESULT ")]
    if proc.returncode != 0 or not lines:
        tail = (proc.stderr.strip().splitlines() or ["no output"])[-1][:300]
        return {"status": f"failed: exit {proc.returncode}: {tail}", "wall_s": time.perf_counter() - t0}
    return {"status": "ok", **json.loads(lines[0][len("RESULT "):])}


def calibrate_power(lay) -> tuple[float, float]:
    """Equal die power giving a hottest Tj max rise of TARGET_RISE_K at level 0 with k(T) (secant on the rise)."""
    from moduleforge.solvers import thermal_layout as tl

    p = 1.0
    for _ in range(8):
        rise = tl.solve_layout_level(lay, level=0, power_W=p, h=H, T_c=T_COOLANT)["values"]["tj_max"] - T_COOLANT
        if abs(rise - TARGET_RISE_K) < 2.0:
            break
        p *= TARGET_RISE_K / rise
    p = round(p, 1)
    rise = tl.solve_layout_level(lay, level=0, power_W=p, h=H, T_c=T_COOLANT)["values"]["tj_max"] - T_COOLANT
    if not RISE_RANGE[0] <= rise <= RISE_RANGE[1]:
        raise RuntimeError(f"calibrated rise {rise:.1f} K outside {RISE_RANGE}")
    return p, rise


def layout_record(name: str, family: str, dies: int, levels: tuple[int, ...], smoke: bool) -> dict:
    from moduleforge.solvers import thermal_layout as tl

    lay = get_layout(family, dies)
    power, cal_rise = calibrate_power(lay)
    runs = [run_level(name, lv, power) if lv in levels else {"status": "skipped: smoke mode"} for lv in LEVELS]
    rec = {
        "name": name, "fingerprint": lay.fingerprint(), "family": family, "dies_per_switch": dies,
        "n_dies": len(lay.dies), "power_per_die_W": power, "target_rise_K": TARGET_RISE_K,
        "calibration_level": 0, "calibration_rise_K": cal_rise, "r": float(tl.R),
        "levels": [{
            "level": lv, "n_cells": r.get("meta", {}).get("n_cells"), "wall_s": r.get("wall_s"),
            "peak_rss_mb": r.get("peak_rss_mb"), "energy_balance": r.get("meta", {}).get("energy_balance"),
            "picard_iters": r.get("meta", {}).get("picard_iters"), "status": r["status"]} for lv, r in zip(LEVELS, runs, strict=True)],
    }
    ok = all(r["status"] == "ok" for r in runs)
    names = list(runs[-1]["values"]) if runs[-1]["status"] == "ok" else []
    vals = {n: [runs[i]["values"][n] for i in range(3)] if ok else None for n in names}
    gci = {n: tl.gci_three_grid(*v) if v else None for n, v in vals.items()}

    def g(n):
        return (gci[n]["gci"], _nan_to_none(gci[n]["p_obs"])) if gci.get(n) else (None, None)

    dies_out = []
    for i in range(len(lay.dies)):
        d = {"id": i, "switch": lay.dies[i].switch}
        for key, label in (("tj_max", "tj_max_K"), ("tj_mean", "tj_mean_K"), ("tj_centroid", "tj_centroid_K")):
            d[label] = vals.get(f"die{i}.{key}")
        d["gci_K"], d["p_obs"] = g(f"die{i}.tj_max")
        d["gci_mean_K"], d["p_obs_mean"] = g(f"die{i}.tj_mean")
        d["gci_centroid_K"], d["p_obs_centroid"] = g(f"die{i}.tj_centroid")
        dies_out.append(d)
    rec["dies"] = dies_out
    rec["layout_values"] = {n: {"values": vals.get(n), "gci_K": g(n)[0], "p_obs": g(n)[1]}
                            for n in ("tj_max", "tj_mean", "spread_max", "spread_mean") if n in vals}
    gcis = [x["gci"] for x in gci.values() if x]
    rec["max_gci_K"] = max(gcis) if gcis else None
    rec["hottest_rise_K"] = [None if not ok else vals["tj_max"][i] - T_COOLANT for i in range(3)] if ok else None
    return rec


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--smoke", action="store_true", help="levels 0 and 1 only; writes to a temporary file")
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--child", nargs=3, metavar=("NAME", "LEVEL", "POWER"), help=argparse.SUPPRESS)
    a = ap.parse_args(argv)
    if a.child:
        child(a.child[0], int(a.child[1]), float(a.child[2]))
        return 0
    levels = (0, 1) if a.smoke else LEVELS
    recs = [layout_record(n, f, d, levels, a.smoke) for n, f, d in LAYOUTS]
    doc = {"mode": "smoke" if a.smoke else "full", "coolant_K": T_COOLANT, "h_W_m2K": H, "seed": SEED, "layouts": recs}
    out = a.out or (Path(tempfile.mkdtemp()) / "thermal_l2_convergence_smoke.json" if a.smoke else DEFAULT_OUT)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1) + "\n")
    print(f"wrote {out}")
    for r in recs:
        print(r["name"], "P/die", r["power_per_die_W"], "W; max GCI", r["max_gci_K"], "K;",
              [(lv["level"], lv["n_cells"], lv["status"]) for lv in r["levels"]])
    return 0 if all(lv["status"] in ("ok",) or lv["status"].startswith("skipped") for r in recs for lv in r["levels"]) else 1


if __name__ == "__main__":
    os.environ.setdefault("OMP_NUM_THREADS", "4")
    raise SystemExit(main())
