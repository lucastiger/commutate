#!/bin/bash
# Founder-session calibration for E008's run plan (2026-11-09; research, NOT evidence).
# Question: P3's 0.25 mm Case 4 solves on the burst VM (research/o006_p3/solves/*__lat0.25.json) logged ~62,000-64,000
# CPU-s for ~7,000 s wall each, two solves sharing an n2-highmem-32: ~9 busy cores per solve, against 1.5 on the Mac at
# 0.5 mm. Linux numpy uses OpenBLAS, whose threads (one per vCPU, per process) busy-wait; l2_layout makes many small
# BLAS calls. If that is the waste, pinning every thread pool to 1 leaves L unchanged and lets several solves share one
# 8-vCPU VM. This script measures it with P3's own --child mode (same geometry, same levels, src/ untouched):
#   A  one 0.5 mm solve alone, default threads, then pinned (minutes each)
#   B  four pinned 0.25 mm solves at once: P3's three geometries, base twice
#   C  the same four with two threads each (8 threads on 8 vCPU: does the second hyperthread of each core help?)
# On the Mac (Accelerate, which does not spin) the pinned 0.5 mm base solve gave L equal to P3's to 8e-15 with the same
# GMRES iterations: 419 s wall / 408 CPU-s pinned, 252 s / 372 CPU-s with default threads, under the same load.
# Results: research/l2_thread_calib/*.json (P3's record format) and summary.txt (against P3's records). Re-runnable: a
# solve whose record exists is skipped (MF_GCP_SPOT=auto relaunches resume from the cache).
#   scripts/burst_gcp.sh --cmd "bash research/scripts/l2_thread_calib.sh" research/l2_thread_calib n2d-custom-8-81920-ext
set -u
cd "$(dirname "$0")/../.."
O=research/l2_thread_calib
R=research/scripts/o006_p3_em_convergence.py
PIN=(env OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 MF_L2_FFT_WORKERS=1 MF_L2_THREADS=1)
TWO=(env OPENBLAS_NUM_THREADS=2 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 MF_L2_FFT_WORKERS=2 MF_L2_THREADS=1)
mkdir -p "$O"
{ nproc; free -g; lscpu | grep -E "Model name|Thread|Core|Socket"; uv run python -c "import numpy; numpy.show_config()"; } \
  > "$O/host.txt" 2>&1

run() {  # tag geom level threads (default | 1 | 2)
  local f="$O/$1.json"
  [ -s "$f" ] && return 0
  case "$4" in
    1) "${PIN[@]}" uv run python "$R" --child "$2" "$3" "$f" > "$O/$1.log" 2>&1 ;;
    2) "${TWO[@]}" uv run python "$R" --child "$2" "$3" "$f" > "$O/$1.log" 2>&1 ;;
    *) uv run python "$R" --child "$2" "$3" "$f" > "$O/$1.log" 2>&1 ;;
  esac
}

run A_default_base_lat0.5 case4_base lat0.5 default
run A_pinned_base_lat0.5 case4_base lat0.5 1
for g in base die_shift trace_width; do run "B_pinned_${g}_lat0.25" "case4_$g" lat0.25 1 & done
run B_pinned_base2_lat0.25 case4_base lat0.25 1 &
wait
for g in base die_shift trace_width; do run "C_two_${g}_lat0.25" "case4_$g" lat0.25 2 & done
run C_two_base2_lat0.25 case4_base lat0.25 2 &
wait

uv run python - "$O" > "$O/summary.txt" 2>&1 <<'EOF'
import json, sys
from pathlib import Path
o, p3 = Path(sys.argv[1]), Path("research/o006_p3/solves")
for f in sorted(o.glob("*.json")):
    r = json.loads(f.read_text())
    geom, level = r["geom"], r["level"]
    ref = json.loads((p3 / f"{geom}__{level}.json").read_text())
    dl = max(abs(r["L_H"][k] / ref["L_H"][k] - 1) for k in r["L_H"])
    print(f"{f.stem:28s} wall {r['wall_s']:7.0f} s  cpu {r['cpu_s']:7.0f} s  cores {r['cpu_s'] / r['wall_s']:4.1f}  "
          f"rss {r['peak_mem_mb'] / 1e3:5.1f} GB  iters {r['gmres_iters']}  |L/L_P3 - 1| {dl:.1e} "
          f"(P3: wall {ref['wall_s']:.0f} s, cpu {ref['cpu_s']:.0f} s, iters {ref['gmres_iters']})")
EOF
cat "$O/summary.txt"
