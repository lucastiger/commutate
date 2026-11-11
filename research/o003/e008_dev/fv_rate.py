"""T0306 item 6: measured finite-volume (solvers.thermal_layout) wall time per cell on development geometry, for the
F6(e) cost basis of E008 (replaces the 1e-4 s/cell placeholder).  Development geometry only (gen2_0, 2D_Case_4).

Per geometry: P_ref from the frozen scikit-fem rule at level 0 (the runner's child_calibrate rule: hottest die 60 +/- 0.25 K
above the 65 C coolant, h = 5000 W/(m2 K)), then one thermal_layout solve at the requested FV level at P_ref, one thread
(OPENBLAS/OMP/MKL = 1, set by the caller).  An in-process watchdog stops the process if its peak RSS passes --cap-gb (house
rule: <= 5 GB for an agent; `ps` and `sysctl vm.swapusage` are denied in the sandbox, so the process watches itself).

Run: OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 MF_L2_FFT_WORKERS=1 \
     uv run python research/o003/e008_dev/fv_rate.py --geom gen2_0 --level 1 --out research/o003/e008_dev/fv_rate_gen2_0_L1.json
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import resource
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def rss_gb() -> float:
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * (1.0 if sys.platform == "darwin" else 1024.0) / 1e9


def watchdog(cap: float, out: Path):
    def run():
        while True:
            if rss_gb() > cap:
                out.write_text(json.dumps({"status": "stopped", "reason": f"peak RSS {rss_gb():.2f} GB > cap {cap} GB"}))
                os._exit(3)
            time.sleep(0.5)
    threading.Thread(target=run, daemon=True).start()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--geom", required=True)
    ap.add_argument("--level", type=int, default=1)
    ap.add_argument("--cap-gb", type=float, default=4.8)
    ap.add_argument("--out", required=True)
    ap.add_argument("--grid-only", action="store_true")
    ap.add_argument("--power", type=float, help="W per die: skip the calibration (FV peak memory measured alone)")
    ap.add_argument("--calibrate-only", action="store_true")
    a = ap.parse_args()
    out = Path(a.out)
    watchdog(a.cap_gb, out)
    sp = importlib.util.spec_from_file_location("e008_run", ROOT / "experiments/runners/e008_run.py")
    R = importlib.util.module_from_spec(sp)
    sys.modules["e008_run"] = R
    sp.loader.exec_module(R)
    import numpy as np
    from moduleforge.solvers import thermal_layout as TL
    cfg = R.load_spec()["config"]
    rc = R.dev_reference(a.geom, cfg)
    lay = rc.reference
    t0 = time.perf_counter()
    g = TL.build_layout_grid(lay, a.level)
    n_cells = int(np.prod(g.shape))
    rec = {"geom": rc.rid, "fingerprint": lay.fingerprint(), "level": a.level, "n_cells_grid": n_cells,
           "grid_build_s": time.perf_counter() - t0, "n_dies": len(lay.dies),
           "threads": {k: os.environ.get(k) for k in R.THREAD_VARS}, "host": os.uname().nodename,
           "peak_GB_after_grid": rss_gb()}
    del g
    if a.grid_only:
        out.write_text(json.dumps(rec | {"status": "ok"}, indent=1))
        return 0
    op = cfg["operating_point"]
    # P_ref by the runner's own calibration rule (frozen scikit-fem rule, level 0), so the FV solve runs at the operating
    # point E008 would use (Picard iteration count depends on the temperature range)
    job = {"fem_rule": cfg["fem_rule"], "power_start_W": op["power_start_W"], "max_iters": op["calibration_max_iters"],
           "h": op["h_W_m2K"], "T_c": op["coolant_K"], "target_K": op["target_rise_K"], "tol_K": op["calibration_tol_K"]}
    R.layout_of = lambda j, lay=lay: lay  # in process: the layout object itself
    if a.power is None:
        t0 = time.perf_counter()
        cal = R.child_calibrate(job)
        rec["calibration"] = {"P_ref_W": cal["P_ref_W"], "rise_K": cal["rise_K"], "history": cal["history"],
                              "wall_s": time.perf_counter() - t0, "peak_GB": rss_gb()}
        if a.calibrate_only:
            out.write_text(json.dumps(rec | {"status": "ok"}, indent=1, default=float))
            print(json.dumps(rec["calibration"], default=float))
            return 0
    else:
        cal = {"P_ref_W": a.power}
        rec["calibration"] = {"P_ref_W": a.power, "source": "--power (calibration run separately)"}
    t0, c0 = time.perf_counter(), time.process_time()
    r = TL.solve_layout_level(lay, level=a.level, power_W=cal["P_ref_W"], h=op["h_W_m2K"], T_c=op["coolant_K"])
    wall, cpu = time.perf_counter() - t0, time.process_time() - c0
    m = r["meta"]
    rec.update(status="ok", n_cells=int(m["n_cells"]), wall_s=wall, cpu_s=cpu, solver_wall_time_s=float(m["wall_time_s"]),
               picard_iters=int(m["picard_iters"]), energy_balance=float(m["energy_balance"]),
               linear_residual=float(m["linear_residual"]), s_per_cell=wall / int(m["n_cells"]),
               peak_GB=rss_gb(), bytes_per_cell_upper=rss_gb() * 1e9 / int(m["n_cells"]),
               tj_max_K=[float(r["values"][f"die{i}.tj_max"]) for i in range(len(lay.dies))])
    out.write_text(json.dumps(rec, indent=1, default=float))
    print(json.dumps({k: v for k, v in rec.items() if k not in ("calibration",)}, default=float))
    return 0


if __name__ == "__main__":
    sys.exit(main())
