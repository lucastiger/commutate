"""T0306 item 6: Mac -> GCP VM factor of the finite-volume solver (solvers.thermal_layout / thermal_fv), measured on
identical solves.  The founder's O007 burst (commit 8d4467c5, e2-highmem-16, research/o007_l2/full.json) solved the two
O007/E006 development generator layouts (side_by_side_6, u_shaped_2; dev seed 20261101, generator geometry only) at
levels 1-3; this script re-solves their level 1 on this Mac with the same code (thermal_fv.py / thermal_layout.py are
unchanged since 2026-11-02, before both runs), the same layout (fingerprint asserted by the O007 loader), the same power
per die and one thread, and writes the per-layout wall ratio VM / Mac.  It also states the VM's own level 1 -> 3 wall
exponent from full.json.  Peak memory ~1.8 GB.

Run: OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
     uv run python research/o003/e008_dev/fv_vm_factor.py --out research/o003/e008_dev/fv_vm_factor.json
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import math
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    sp = importlib.util.spec_from_file_location("o007_l2_preview", ROOT / "research/scripts/o007_l2_preview.py")
    P = importlib.util.module_from_spec(sp)
    sys.modules["o007_l2_preview"] = P
    sp.loader.exec_module(P)
    full = json.loads((ROOT / "research/o007_l2/full.json").read_text())
    prev = json.loads((ROOT / "research/o007_l2/preview.json").read_text())
    out = {"task": "T0306", "vm": "e2-highmem-16 (founder burst 2026-11-04, commit 8d4467c5; full.json physical "
           f"{full['memory']['physical_gb']:.1f} GB)", "mac": os.uname().nodename,
           "threads": {k: os.environ.get(k) for k in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS")},
           "layouts": {}}
    for name, v in full["layouts"].items():
        vm = v["solves"]
        P_w = float(v["power_W_per_die_proxy"])
        mac = P.child({"layout": name, "level": 1, "kind": "solve", "power_W": P_w, "cap_gb": 4.8})
        if mac["n_cells"] != vm["1"]["n_cells"]:
            raise RuntimeError(f"{name}: {mac['n_cells']} cells here, {vm['1']['n_cells']} on the VM")
        tj_vm = full["layouts"][name].get("dies")
        n = [vm[k]["n_cells"] for k in ("1", "2", "3")]
        t = [vm[k]["solve_wall_s"] for k in ("1", "2", "3")]
        out["layouts"][name] = {
            "power_W_per_die": P_w, "n_cells_L1": mac["n_cells"], "picard_iters_mac": mac["picard_iters"],
            "mac_wall_s_L1": mac["solve_wall_s"], "mac_wall_s_L1_preview_T0204": prev["detail"][name]["level1_solve"]["solve_wall_s"],
            "vm_wall_s_L1": t[0], "vm_over_mac": t[0] / mac["solve_wall_s"],
            "vm_over_mac_preview": t[0] / prev["detail"][name]["level1_solve"]["solve_wall_s"],
            "vm_cells": n, "vm_wall_s": t, "vm_s_per_cell": [b / c for b, c in zip(t, n, strict=True)],
            "vm_beta_steps": [math.log(t[i + 1] / t[i]) / math.log(n[i + 1] / n[i]) for i in range(2)],
            "vm_beta_L1_L3": math.log(t[2] / t[0]) / math.log(n[2] / n[0]),
            "mac_s_per_cell_L1": mac["solve_wall_s"] / mac["n_cells"], "tj_max_K_mac": mac["tj_max_K"],
            "vm_dies_record_present": tj_vm is not None}
        print(name, json.dumps({k: out["layouts"][name][k] for k in ("mac_wall_s_L1", "vm_wall_s_L1", "vm_over_mac",
                                                                     "vm_over_mac_preview", "vm_beta_L1_L3")}))
    f = [x["vm_over_mac"] for x in out["layouts"].values()]
    out["summary"] = {"vm_over_mac": f, "mean": sum(f) / len(f), "min": min(f), "max": max(f),
                      "vm_beta_L1_L3": [x["vm_beta_L1_L3"] for x in out["layouts"].values()],
                      "vm_beta_steps_all": [b for x in out["layouts"].values() for b in x["vm_beta_steps"]]}
    Path(a.out).write_text(json.dumps(out, indent=1))
    print(json.dumps(out["summary"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
