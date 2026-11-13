#!/usr/bin/env bash
# T0325: 2D_Case_4 Tj oscillation diagnosis, levels 0-2 of stack variants V0-V4 on Case 4's twin (DEVELOPMENT GEOMETRY ONLY:
# 2D_Case_4, never a judged reference; tj_osc.py refuses any layout whose fingerprint does not start f4862196 / d0dd6090).
# For the founder; agents never launch VMs. Notes: research/diagnoses/T0325.md.
#
# What runs on the VM (scripts/burst_gcp.sh --cmd, unchanged; it bundles committed MAIN, so the T0325 branch must be merged
# first, and every layout is rebuilt from that commit by the runner's dev path, never from a saved ctx.pkl):
#   tj_osc.py run      --variants V0,V1,V2,V3,V4 --which twin --levels 0,1,2 --threads 2 (one subprocess and one result file
#                      per solve; an existing ok result is never re-solved, so a Spot preemption resumes from the cache)
#   tj_osc.py summary  per-die Tj per level, steps, gci_capped and tj_bounds per variant (mfos.metrics, floor 1e-3 K)
# Concurrency: largest first, sum of memory estimates <= 0.85 x RAM (estimate 0.5 GB + 4 kB/node, ~25 % above the dev run's
# measured 9.27 GB at 2.75 M nodes), at most 4 solves at once (--max-procs 4: 8 vCPU / 2 threads).
# Expected (inference from the 2026-11-13 dev run's walls, research/diagnoses/T0325.md): 15 solves, the five level-2 solves
# 2.2-2.8 M nodes, 9-12 GB, ~17-20 min each, all five within two rounds of four; about 1 VM-hour including set-up,
# about $0.6 at the founder's 0.612 $/h figure for this machine (less on Spot). Copied back: research/o003/e008_dev/tj_osc/vm_work
# (solves/*.json per solve, jobs.json, summary.json, run.log).
#
# Usage: bash research/o003/e008_dev/tj_osc/burst_tj_osc.sh [--dry-run]
#   --dry-run  prints every command and runs none (no gcloud, no VM, no solve)
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
DRY=0
case "${1:-}" in
  --dry-run) DRY=1 ;;
  "") ;;
  *) echo "usage: $0 [--dry-run]" >&2; exit 2 ;;
esac
TJ=research/o003/e008_dev/tj_osc/tj_osc.py
WD=research/o003/e008_dev/tj_osc/vm_work
MACHINE=n2d-custom-8-81920-ext
ZONE=us-central1-a
INNER="mkdir -p $WD && uv run python $TJ run --variants V0,V1,V2,V3,V4 --which twin --levels 0,1,2 --threads 2 --max-procs 4"
INNER="$INNER --workdir $WD 2>&1 | tee -a $WD/run.log; uv run python $TJ summary --workdir $WD 2>&1 | tee $WD/summary.txt"
ENVS=(MF_GCP_SPOT=auto MF_GCP_PROVISION=0 MF_GCP_RESUME=1)

if [ "$DRY" = 1 ]; then
  echo "# dry run: nothing below is executed"
  echo "# 1. precondition: the launcher's driver is committed on main (burst_gcp.sh bundles main)"
  echo "git cat-file -e main:$TJ"
  echo "# 2. VM run (Spot auto, resumable; copies $WD back)"
  echo "${ENVS[*]} scripts/burst_gcp.sh --cmd '$INNER' $WD $MACHINE $ZONE"
  echo "# 3. on this machine, after the copy-back (no solve; prints the table again from the result files)"
  echo "uv run python $TJ summary --workdir $WD"
  exit 0
fi

git cat-file -e "main:$TJ" 2> /dev/null || { echo "$TJ is not committed on main: merge T0325 first (burst_gcp.sh bundles main)" >&2; exit 1; }
env "${ENVS[@]}" scripts/burst_gcp.sh --cmd "$INNER" "$WD" "$MACHINE" "$ZONE"
uv run python "$TJ" summary --workdir "$WD"
