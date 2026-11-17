"""Speed benchmark of the L1 thermal model (A5): median wall time per evaluation on one thread over the development
layouts (the 12 layouts of the T0392 design study) at P_ref and 0.5 P_ref.

``--check`` exits 1 if the median exceeds 1.0 s.  Run with one BLAS/OpenMP thread:
``OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 uv run python benchmarks/thermal_l1_speed.py --check``.
"""
from __future__ import annotations

import os

for _v in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

import argparse  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402
import yaml  # noqa: E402

from moduleforge.generate.halfbridge import generate_layouts  # noqa: E402
from moduleforge.thermal import evaluate  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
LIMIT_S = 1.0
H, TC = 5000.0, 338.15
DEV_SEED, NEW_SEED, N_NEW, N_DRAW = 20261101, 20261115, 5, 40
REPEATS = 3


def dev_layouts():
    spec = yaml.safe_load((ROOT / "experiments" / "specs" / "E009.yaml").read_text())["config"]
    p_ref = spec["dev_regression_guard"]["calibrated_power_W_per_die"]
    out = []
    for name, fam, k in spec["dev_layouts"]:
        dev = generate_layouts(1, DEV_SEED, family=fam, dies_per_switch=k)[0]
        lays, seen = [(name, dev)], {dev.fingerprint()}
        for lay in generate_layouts(N_DRAW, NEW_SEED, family=fam, dies_per_switch=k):
            if len(lays) > N_NEW:
                break
            if lay.dies[0].w == dev.dies[0].w and lay.fingerprint() not in seen:
                seen.add(lay.fingerprint())
                lays.append((f"{fam}_{k}_n{len(lays) - 1}", lay))
        out += [(nm, lay, p_ref[name]) for nm, lay in lays]
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="exit 1 if the median evaluation exceeds 1 s")
    args = ap.parse_args(argv)
    rows = dev_layouts()
    times = []
    evaluate(rows[0][1], rows[0][2], h=H, T_c=TC)  # warm-up (imports, caches), not timed
    for nm, lay, p_ref in rows:
        for ld, f in (("P_ref", 1.0), ("0.5 P_ref", 0.5)):
            ts = []
            for _ in range(REPEATS):
                t0 = time.perf_counter()
                evaluate(lay, f * p_ref, h=H, T_c=TC)
                ts.append(time.perf_counter() - t0)
            times.append(float(np.median(ts)))
            print(f"{nm:20s} {len(lay.dies):2d} dies {ld:10s} {times[-1]:.3f} s", flush=True)
    med = float(np.median(times))
    print(f"median {med:.3f} s, max {max(times):.3f} s over {len(times)} evaluations (limit {LIMIT_S} s, one thread)")
    if args.check and med > LIMIT_S:
        print("FAIL: median above limit")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
