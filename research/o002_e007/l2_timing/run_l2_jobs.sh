#!/usr/bin/env bash
# T0464: E007's pre-registration level-2 burst (D0025 decision 3; review T0463 (5)). Runs the two level-2 reference
# solves ONE AT A TIME (24-25 GB each with margin), each in its own child process of the frozen runner, and writes their
# records (cpu_s, wall_s, peak_rss_GB, DOF, tj_mean, ...) into research/o002_e007/l2_timing/. Burst only (> 10 GB):
#   scripts/burst_gcp.sh --cmd "bash research/o002_e007/l2_timing/run_l2_jobs.sh" research/o002_e007/l2_timing n2d-custom-8-81920-ext
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
for j in job.json job_interleaved_2_j01.json; do
  echo "== $j $(date -u +%FT%TZ)"
  uv run python experiments/runners/e007_run.py --child "research/o002_e007/l2_timing/$j"
done
ls -l research/o002_e007/l2_timing/
