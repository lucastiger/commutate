#!/usr/bin/env bash
# T0393 (O002 F1 development check): the level-2 thermal_fem solves that exceed the local memory rule, for the
# founder's burst VM. Agents never start a VM or run gcloud; the founder runs this script.
#
#   bash research/o002_f1/burst_level2.sh --dry-run   print the plan (VM-hours, memory, $) and every command; run none
#   bash research/o002_f1/burst_level2.sh             do it (needs gcloud; this directory committed on $MF_REF)
#
# Conventions (scripts/burst.sh, scripts/burst_gcp.sh --cmd): one ephemeral VM, the code only as a git bundle of a
# committed ref, results copied back, the VM deleted on every exit path (burst_gcp.sh's trap). Not a registered run, so
# no mint and no seed. The jobs are the missing level-2 keys of f1_dev_check.py --plan (computed here, read-only); on
# the VM, f1_dev_check.py --solve-level2 runs them largest first, a job starting only while the running jobs' E009
# memory estimates (DOF x 4964 B x 1.15) fit 0.85 x physical memory; every finished solve is one JSON file in
# research/o002_f1/burst_out/, and a rerun with MF_GCP_RESUME=1 skips finished ones. Machine: N2D custom, 8 vCPU,
# memory from MF_F1_RAM_GB (default 78 GB visible = n2d-custom-8-81920-ext, E010's machine; founder's 0.612 $/h).
# The thermal solves run on one core each, so the machine is sized by memory. Regular VM (MF_GCP_SPOT=0) by default:
# a level-2 solve is 0.6-1.6 h and checkpoints only at its end, so Spot rarely pays (docs/INFRASTRUCTURE.md).
# After the copy-back: uv run python research/o002_f1/f1_dev_check.py --analyse (no solve) updates the JSON.
set -euo pipefail
{
DRY=0
case "${1:-}" in
  --dry-run) DRY=1 ;;
  "") ;;
  *) echo "usage: bash research/o002_f1/burst_level2.sh [--dry-run]" >&2; exit 2 ;;
esac
cd "$(git rev-parse --show-toplevel)"
REF="${MF_REF:-main}"
ZONE="${MF_GCP_ZONE:-us-central1-a}"
RAM_GB="${MF_F1_RAM_GB:-78}"
FETCH=research/o002_f1/burst_out
show() { printf '+'; printf ' %q' "$@"; printf '\n'; }

PLAN="$(uv run python research/o002_f1/f1_dev_check.py --plan --ram-gb "$RAM_GB" 2> /dev/null)"
read -r MACHINE KEYS NJOBS FITS VMH USD PEAK USABLE MAKESPAN <<< "$(printf '%s' "$PLAN" | python3 -c '
import json, sys
p = json.load(sys.stdin)
print(p["machine"], ",".join(p["keys"]) or "-", len(p["keys"]), int(p["fits"]), "%.2f" % p["vm_hours"], "%.2f" % p["usd"],
      "%.1f" % p["peak_job_GB_E009"], "%.1f" % p["usable_GB"], "%.2f" % p["makespan_h"])')"
printf '%s' "$PLAN" | python3 -c '
import json, sys
p = json.load(sys.stdin)
print("# level-2 jobs (E009 memory estimate, wall at the measured level-2 rate):")
for j in p["jobs"]:
    print("#   %-32s %6.2f M DOF  %6.1f GB  %5.2f h  start %.2f h" % (j["key"], j["est_dofs"] / 1e6, j["est_GB_E009"],
                                                                  j["est_wall_h"], j["start_h"]))'
echo "# machine $MACHINE ($RAM_GB GB, $USABLE GB usable at 0.85): $NJOBS jobs, largest $PEAK GB, fits: $FITS"
echo "# expected: makespan $MAKESPAN h + 0.5 h set-up = $VMH VM-hours, \$$USD (on-demand)"
if [ "$NJOBS" = 0 ]; then echo "# nothing to do: every level-2 solve is stored"; exit 0; fi
[ "$FITS" = 1 ] || { echo "the largest job does not fit $USABLE GB: set MF_F1_RAM_GB higher" >&2; exit 1; }
MAXH="$(python3 -c "import math; print(math.ceil(1.5 * $VMH) + 1)")"   # burst_gcp.sh deadline with 50 % slack

JOB="uv run python research/o002_f1/f1_dev_check.py --solve-level2 $KEYS"
CMD=(env MF_REF="$REF" MF_GCP_PROVISION=0 MF_GCP_MAX_HOURS="$MAXH" MF_GCP_SPOT="${MF_GCP_SPOT:-0}"
     scripts/burst_gcp.sh --cmd "$JOB" "$FETCH" "$MACHINE" "$ZONE")
# preflight (read-only): the script and the frozen solver bytes on the ref the VM gets
show git cat-file -e "$REF:research/o002_f1/f1_dev_check.py"
show git show "$REF:src/moduleforge/solvers/thermal_fem.py" '|' shasum -a 256
if [ "$DRY" = 0 ]; then
  git cat-file -e "$REF:research/o002_f1/f1_dev_check.py" 2> /dev/null \
    || { echo "research/o002_f1/f1_dev_check.py is not committed on $REF" >&2; exit 1; }
  SHA="$(git show "$REF:src/moduleforge/solvers/thermal_fem.py" | shasum -a 256 | cut -c1-16)"
  [ "$SHA" = a216d5fe3209bcee ] || { echo "thermal_fem.py on $REF is $SHA, not the frozen a216d5fe..." >&2; exit 1; }
fi
show scripts/burst_gcp.sh --check "$MACHINE" "$ZONE"
show "${CMD[@]}"
show uv run python research/o002_f1/f1_dev_check.py --analyse
if [ "$DRY" = 1 ]; then echo "# dry run: nothing started"; exit 0; fi
scripts/burst_gcp.sh --check "$MACHINE" "$ZONE"
"${CMD[@]}"
uv run python research/o002_f1/f1_dev_check.py --analyse
exit 0
}
