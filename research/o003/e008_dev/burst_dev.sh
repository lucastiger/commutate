#!/usr/bin/env bash
# T0262: E008 full-fidelity DEV run (development geometry only: generator housing gen2_0 with the full frozen search,
# 2D_Case_4 twin gates and band-check pairs; never a judged reference). For the founder; agents never launch VMs.
# 0.25 mm production cells, the frozen thermal rule at levels 0-2, two threads per solve (research/l2_thread_calib),
# concurrency by the --plan memory estimates within 0.85 x RAM. Resumable: every solve is a result file under the
# work directory, which burst_gcp.sh caches and re-uploads after a Spot preemption (MF_GCP_SPOT=auto).
# Expected: about 10-12 VM-hours on n2d-custom-8-81920-ext (inference from the --plan cost model; research/notes/e008-design.md).
# Largest jobs: gen2_0 candidates' thermal level 2 (6.2-7.0 M DOFs, ~40 GB) and Case 4 lat0.25 (15.9 GB); the scheduler keeps
# the sum of estimates within 0.85 x RAM.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
MF_GCP_SPOT=auto MF_GCP_PROVISION=0 MF_GCP_RESUME=1 scripts/burst_gcp.sh --cmd \
  "uv run python experiments/runners/e008_run.py --dev --geoms gen2_0,case4:gates:4 --band-pairs 4 \
   --workdir research/o003/e008_dev/full_work --rows-out research/o003/e008_dev/full_work/E008.dev_rows.json" \
  research/o003/e008_dev/full_work n2d-custom-8-81920-ext us-central1-a
# then: cp research/o003/e008_dev/full_work/E008.dev_rows.json experiments/drafts/E008.dev_rows.json (replaces the
# local smoke rows) and re-run: uv run python experiments/runners/e008_run.py --plan --plan-out research/o003/e008_dev/plan.json
