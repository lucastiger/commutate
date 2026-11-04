#!/usr/bin/env bash
# Google Compute Engine counterpart of scripts/burst.sh: run ONE registered experiment, or one repository command,
# on an ephemeral VM, copy the results back, delete the VM. The VM is deleted on every exit path (trap). The code
# reaches the VM only as a git bundle, so no GitHub credentials ever do. Results keep full provenance.
#
# Usage:
#   scripts/burst_gcp.sh --check [machine-type] [zone]          verify gcloud auth, project, API and CPU quota
#   scripts/burst_gcp.sh E001 [machine-type] [zone]             mfos exp run E001 --force; copy experiments/results/E001
#   scripts/burst_gcp.sh --cmd "<command>" <path> [machine-type] [zone]
#                                                               run <command> in the repo; copy <path> back to the same
#                                                               relative path here (for benchmarks and spikes)
# Defaults: n2-highmem-32 (32 vCPU, 256 GB) in us-central1-a. MF_REF=<ref> bundles another committed ref (default main).
# MF_GCP_SPOT=1 uses one Spot VM (cheaper, can be preempted: never for a registered run). MF_GCP_SPOT=auto (--cmd only)
# relaunches after a preemption, rotating through MF_GCP_ZONES and resuming from the cache, and finishes on a regular VM
# after MF_GCP_SPOT_TRIES Spot attempts (default 2). With --cmd the output directory is cached on this machine every
# MF_GCP_SYNC_POLLS x 30 s (default 4, ~2-3 min); MF_GCP_RESUME=1 uploads that cache on the first VM too.
# MF_GCP_PROVISION=0 skips the FastHenry/ngspice build for jobs that do not need them (faster relaunches).
# MF_GCP_DISK_GB sets the boot disk (default 20 GB). Size the machine by memory: the thermal solvers run on one core.
# Setup (once): docs/INFRASTRUCTURE.md, "Burst compute on Google Cloud".
set -euo pipefail
MODE=exp
case "${1:-}" in
  --check) MODE=check; shift ;;
  --cmd) MODE=cmd; CMD="${2:?--cmd needs a command}"; FETCH="${3:?--cmd needs a path to copy back}"; shift 3 ;;
  ""|-*) echo "usage: scripts/burst_gcp.sh --check | <EXPERIMENT_ID> | --cmd \"<command>\" <path>  [machine-type] [zone]" >&2; exit 2 ;;
  *) EID="$1"; shift ;;
esac
TYPE="${1:-n2-highmem-32}"; ZONE="${2:-us-central1-a}"; REGION="${ZONE%-*}"; REF="${MF_REF:-main}"
# Checked before anything has side effects (a registered run is minted below, and minting cannot be undone).
SPOT_MODE="${MF_GCP_SPOT:-0}"
case "$SPOT_MODE" in 0|1|auto) ;; *) echo "MF_GCP_SPOT must be 0, 1 or auto" >&2; exit 2 ;; esac
if [ "$MODE" = exp ] && [ "$SPOT_MODE" = auto ]; then echo "MF_GCP_SPOT=auto is for --cmd runs only" >&2; exit 2; fi
command -v gcloud > /dev/null || { echo "gcloud is not installed: brew install --cask google-cloud-sdk" >&2; exit 1; }
PROJECT="$(gcloud config get-value project 2> /dev/null || true)"
[ -n "$PROJECT" ] || { echo "no gcloud project set: gcloud config set project <PROJECT_ID>" >&2; exit 1; }
cd "$(git rev-parse --show-toplevel)"

if [ "$MODE" = check ]; then
  echo "account: $(gcloud auth list --filter=status:ACTIVE --format='value(account)')"
  echo "project: $PROJECT"
  gcloud services list --enabled --filter=name:compute.googleapis.com --format='value(name)' | grep -q compute \
    || { echo "Compute Engine API is not enabled: gcloud services enable compute.googleapis.com" >&2; exit 1; }
  VCPU="$(gcloud compute machine-types describe "$TYPE" --zone "$ZONE" --format='value(guestCpus)')"
  echo "machine type: $TYPE in $ZONE ($VCPU vCPU, $(gcloud compute machine-types describe "$TYPE" --zone "$ZONE" --format='value(memoryMb)') MB)"
  gcloud compute regions describe "$REGION" --format=json | python3 -c "
import json, sys
q = {x['metric']: (x['limit'], x['usage']) for x in json.load(sys.stdin)['quotas']}
fam = '$TYPE'.split('-')[0].upper() + '_CPUS'
need = int('$VCPU')
ok = True
for m in ('CPUS', fam):
    if m in q:
        lim, use = q[m]
        print(f'quota {m} in $REGION: {use:.0f} used of {lim:.0f}')
        ok &= lim - use >= need
print('enough quota for one VM' if ok else f'NOT enough quota for {need} vCPU: request an increase (IAM & Admin > Quotas)')
sys.exit(0 if ok else 1)"
  exit 0
fi

if [ "$MODE" = exp ]; then
  test -f "experiments/specs/$EID.yaml" || { echo "$EID is not registered (experiments/specs/$EID.yaml missing)" >&2; exit 1; }
  if [ -n "$(git status --porcelain --untracked-files=no -- src experiments/runners tools pyproject.toml uv.lock)" ]; then
    echo "uncommitted code changes: the experiment must run on a commit that is on main" >&2; exit 1
  fi
  git cat-file -e "$REF:experiments/specs/$EID.yaml" 2> /dev/null \
    || { echo "$EID's registration is not committed on $REF: commit it first (the run must cite a commit with its spec)" >&2; exit 1; }
  # Mint the run here, before any VM exists: its id and seed commitment go into experiments/registry.jsonl on this
  # machine, and the VM runs exactly that run. Evaluator 2.0.0 uses the first minted run, so a run cannot be
  # repeated quietly until a result looks good.
  MINT="$(uv run mfos exp mint "$EID")"
  RUN_ID="$(printf '%s' "$MINT" | python3 -c 'import json,sys; print(json.load(sys.stdin)["run_id"])')"
  SEED_FILE="$(printf '%s' "$MINT" | python3 -c 'import json,sys; print(json.load(sys.stdin)["seed_file"] or "")')"
  echo "minted $RUN_ID"
  TAG="$(echo "$EID" | tr '[:upper:]' '[:lower:]')"
else
  TAG=cmd
fi
WORK="$(mktemp -d)"
git bundle create -q "$WORK/mf.bundle" "$REF"
# MF_GCP_SPOT: 0 regular VM (default) | 1 one Spot VM | auto: Spot, relaunched automatically after a preemption (rotating
# through MF_GCP_ZONES and resuming from the cache below), then a regular VM after MF_GCP_SPOT_TRIES Spot attempts (default
# 2). 2026-11-03: N2 Spot cost 60 % of regular and three Spot VMs were preempted after 6-27 min, so Spot only pays off
# with automatic resume and a bounded number of attempts. auto is for --cmd runs: a registered run is never resumed
# (MF_GCP_SPOT is validated at the top, before a run is minted).
SPOT_TRIES="${MF_GCP_SPOT_TRIES:-2}"
SYNC_POLLS="${MF_GCP_SYNC_POLLS:-4}"
MAXH="${MF_GCP_MAX_HOURS:-6}"
# A set-up VM uses about 4 GB of its boot disk (2026-11-04: 3.7 GB with the uv cache); 200 GB cost $0.027/h for nothing.
DISK_GB="${MF_GCP_DISK_GB:-20}"
DEADLINE=$((SECONDS + MAXH * 3600))
# A zone can run out of a machine type (ZONE_RESOURCE_POOL_EXHAUSTED for n2-highmem-32 in us-central1-a, 2026-10-06).
# The CPU quota is regional, so the default list is the region's zones; MF_GCP_ZONES may list zones of several regions.
ZONELIST="${MF_GCP_ZONES:-$ZONE $(gcloud compute zones list --filter="region:$REGION AND status:UP" --format='value(name)' | grep -vx "$ZONE" | tr '\n' ' ')}"
read -r -a ZONEARR <<< "$ZONELIST"
PROVISION="scripts/provision_compute.sh"   # FastHenry and ngspice; MF_GCP_PROVISION=0 when the job needs neither
if [ "${MF_GCP_PROVISION:-1}" = 0 ]; then PROVISION=""; fi
REMOTE='set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
sudo apt-get update -qq && sudo apt-get install -y -qq git build-essential curl > /dev/null
curl -LsSf https://astral.sh/uv/install.sh | sh > /dev/null
export PATH="$HOME/.local/bin:$PATH"
git clone -q ~/mf.bundle ~/mf && cd ~/mf && git checkout -q '"$REF"'
'"$PROVISION"'
uv sync -q --all-groups
echo "host: $(hostname), $(nproc) vCPU, $(free -g | awk "/Mem:/ {print \$2}") GB"'
if [ "$MODE" = exp ]; then
  JOB="uv run mfos exp run $EID --force --run-id $RUN_ID"; FETCH="experiments/results/$EID"
  if [ -n "$SEED_FILE" ]; then JOB="$JOB --seed-file ~/mf.seed"; fi
else
  JOB="$CMD"
fi
printf 'set -uo pipefail\nexport PATH="$HOME/.local/bin:$PATH"\ncd ~/mf\n%s\n' "$JOB" > "$WORK/job.sh"
# Spot resume (--cmd runs only; a registered experiment is never seeded with earlier results): while the job runs, its
# output directory, checkpoints included, is copied every SYNC_POLLS x 30 s to a cache on this machine; a relaunch (or a
# rerun with MF_GCP_RESUME=1) uploads that cache before the job starts, so a script that resumes from its checkpoints
# skips finished work.
CACHE=""
if [ "$MODE" = cmd ]; then
  CACHE="${MF_GCP_CACHE:-$HOME/.cache/mf-burst}/$(printf '%s' "$FETCH" | tr '/' '_')"
  mkdir -p "$CACHE"
fi

NAME=""
ACCOUNT=""   # one line per VM: attempt, kind, zone, minutes, outcome
T_VM=0
account() {  # $1: outcome of the current VM
  ACCOUNT="$ACCOUNT
  attempt $ATTEMPT: $KIND $TYPE in $ZONE, $(((SECONDS - T_VM + 59) / 60)) min, $1"
}
vm_state() {  # prints the VM's status ("" if it no longer exists); fails only if gcloud itself fails (e.g. network)
  gcloud compute instances list --filter="name=$NAME" --format='value(status)' 2> /dev/null
}
vm_lost() {  # true only if a successful listing shows the VM gone or stopping (a network failure is not a loss)
  local state
  state="$(vm_state)" || return 1
  case "$state" in RUNNING|PROVISIONING|STAGING|REPAIRING) return 1 ;; esac
  return 0
}
cleanup() {
  if [ -z "$NAME" ]; then return 0; fi
  if [ -z "$(vm_state || echo unknown)" ]; then echo "$NAME is already gone"; return 0; fi
  echo "deleting $NAME"
  gcloud compute instances delete "$NAME" --zone "$ZONE" --quiet > /dev/null 2>&1 || echo "DELETE FAILED: remove $NAME by hand" >&2
}
trap cleanup EXIT

create_vm() {  # $1: 1 for Spot; $2: attempt number (rotates the first zone tried). Sets NAME and ZONE; 1 if no capacity.
  local spot_args=() n=${#ZONEARR[@]} i z err
  if [ "$1" = 1 ]; then spot_args=(--provisioning-model=SPOT --instance-termination-action=DELETE); fi
  # The PID keeps two bursts started in the same second apart (2026-11-04: the L2 preview's VM name collided with the
  # probe's and its create failed).
  NAME="mf-burst-$TAG-$(date +%s)-$$-a$2"
  for ((i = 0; i < n; i++)); do
    z="${ZONEARR[$(((i + $2 - 1) % n))]}"
    if err="$(gcloud compute instances create "$NAME" --zone "$z" --machine-type "$TYPE" \
        --image-family ubuntu-2404-lts-amd64 --image-project ubuntu-os-cloud \
        --boot-disk-size "${DISK_GB}GB" --boot-disk-type pd-balanced ${spot_args[@]+"${spot_args[@]}"} --quiet 2>&1 > /dev/null)"; then
      ZONE="$z"; return 0
    fi
    if echo "$err" | grep -qE "ZONE_RESOURCE_POOL_EXHAUSTED|resource_availability|does not have enough resources|STOCKOUT"; then
      echo "$TYPE is unavailable in $z; trying the next zone" >&2; continue
    fi
    echo "$err" >&2; NAME=""; exit 1
  done
  NAME=""; return 1
}

setup_vm() {
  local _
  for _ in $(seq 1 60); do
    if gcloud compute ssh "$NAME" --zone "$ZONE" --quiet --command true > /dev/null 2>&1; then break; fi
    sleep 5
  done
  gcloud compute scp --zone "$ZONE" --quiet "$WORK/mf.bundle" "$NAME:mf.bundle" > /dev/null || return 1
  gcloud compute ssh "$NAME" --zone "$ZONE" --quiet --command "$REMOTE" || return 1
}

start_job() {  # $1: 1 to upload the cache before the job starts
  if [ "$MODE" = exp ] && [ -n "$SEED_FILE" ]; then
    gcloud compute scp --zone "$ZONE" --quiet "$SEED_FILE" "$NAME:mf.seed" > /dev/null || return 1
  fi
  if [ "$1" = 1 ] && [ -n "$CACHE" ] && [ -d "$CACHE/fetched" ]; then
    # A checkpoint copied while the job was writing it is unreadable: drop it, so the job recomputes that step instead
    # of failing on it.
    python3 - "$CACHE/fetched" <<'PY'
import json, pathlib, sys
for f in pathlib.Path(sys.argv[1]).rglob("*.json"):
    try:
        json.loads(f.read_text())
    except ValueError:
        f.unlink()
        print(f"dropped unreadable checkpoint {f}")
PY
    gcloud compute ssh "$NAME" --zone "$ZONE" --quiet --command "mkdir -p ~/mf/$FETCH" > /dev/null || return 1
    gcloud compute scp --zone "$ZONE" --quiet --recurse "$CACHE/fetched" "$NAME:mf-resume" > /dev/null || return 1
    gcloud compute ssh "$NAME" --zone "$ZONE" --quiet --command "cp -R ~/mf-resume/. ~/mf/$FETCH/ && rm -rf ~/mf-resume" > /dev/null || return 1
    echo "resumed from $CACHE/fetched ($(find "$CACHE/fetched" -type f | wc -l | tr -d ' ') files)"
  fi
  gcloud compute scp --zone "$ZONE" --quiet "$WORK/job.sh" "$NAME:job.sh" > /dev/null || return 1
  # The VM's own shutdown is a backstop 20 minutes after this script's deadline, so that on a timeout the script can
  # still copy job.log and partial results back before it deletes the VM (2026-11-03: both fired at 4 h exactly).
  gcloud compute ssh "$NAME" --zone "$ZONE" --quiet --command "sudo shutdown -h +$(((DEADLINE - SECONDS) / 60 + 20)) > /dev/null 2>&1; nohup bash -c 'bash ~/job.sh > ~/job.log 2>&1; echo \$? > ~/job.rc' > /dev/null 2>&1 < /dev/null &" || return 1
  echo "job started on $NAME: $JOB"
}

poll_job() {  # sets RC: the job's exit code, 125 if the VM was preempted or deleted, or "" at the deadline
  local polls=0 gone=0
  RC=""
  while [ -z "$RC" ] && [ $SECONDS -lt $DEADLINE ]; do
    sleep 30
    polls=$((polls + 1))
    RC="$(gcloud compute ssh "$NAME" --zone "$ZONE" --quiet --command 'cat ~/job.rc 2> /dev/null' 2> /dev/null | tr -d '[:space:]' || true)"
    if [ -n "$CACHE" ] && [ $((polls % SYNC_POLLS)) -eq 0 ]; then
      rm -rf "$CACHE/sync.tmp"
      if gcloud compute scp --zone "$ZONE" --quiet --recurse "$NAME:mf/$FETCH" "$CACHE/sync.tmp" > /dev/null 2>&1; then
        rm -rf "$CACHE/fetched" && mv "$CACHE/sync.tmp" "$CACHE/fetched"
      fi
    fi
    # Only a successful listing that shows the VM missing or not running counts; a failed gcloud call (network) never
    # does, so a connection blip cannot end the wait or delete a healthy VM. Two consecutive such polls end the wait.
    if [ -z "$RC" ]; then
      if vm_lost; then gone=$((gone + 1)); else gone=0; fi
      if [ "$gone" -ge 2 ]; then echo "VM $NAME is gone or stopping (spot preemption or deletion): stopping the wait" >&2; RC=125; fi
    fi
  done
}

ATTEMPT=0
RC=""
while :; do
  ATTEMPT=$((ATTEMPT + 1))
  SPOT_NOW=0
  if [ "$SPOT_MODE" = 1 ]; then SPOT_NOW=1; fi
  if [ "$SPOT_MODE" = auto ] && [ "$ATTEMPT" -le "$SPOT_TRIES" ]; then SPOT_NOW=1; fi
  KIND=regular
  if [ "$SPOT_NOW" = 1 ]; then KIND=spot; fi
  if ! create_vm "$SPOT_NOW" "$ATTEMPT"; then
    if [ "$SPOT_MODE" = auto ] && [ "$SPOT_NOW" = 1 ]; then
      echo "no $KIND capacity for $TYPE in: $ZONELIST" >&2; RC=125
    else
      echo "$TYPE is unavailable in every zone of: $ZONELIST (retry later or pass another type/zone)" >&2; exit 1
    fi
  else
    T_VM=$SECONDS
    echo "$NAME ($TYPE, $ZONE, $KIND, attempt $ATTEMPT)"
    UPLOAD=0
    if [ "$ATTEMPT" -gt 1 ] || [ "${MF_GCP_RESUME:-0}" = 1 ]; then UPLOAD=1; fi
    if setup_vm && start_job "$UPLOAD"; then
      poll_job
    elif vm_lost; then
      echo "$NAME was lost during setup (spot preemption?)" >&2; RC=125
    else
      account "setup failed"
      echo "setup of $NAME failed while the VM is still up: not a preemption, stopping" >&2; exit 1
    fi
  fi
  # Relaunch only in auto mode, after a preemption, while time and Spot attempts (plus the one regular VM) remain.
  if [ "$RC" = 125 ] && [ "$SPOT_MODE" = auto ] && [ $SECONDS -lt $DEADLINE ] && [ "$ATTEMPT" -le "$SPOT_TRIES" ]; then
    if [ -n "$NAME" ]; then account preempted; fi
    cleanup; NAME=""; RC=""
    NEXT=regular
    if [ $((ATTEMPT + 1)) -le "$SPOT_TRIES" ]; then NEXT=spot; fi
    echo "relaunching as attempt $((ATTEMPT + 1)) ($NEXT), resuming from the cache" >&2
    continue
  fi
  break
done
if [ -z "$RC" ]; then echo "job did not finish within ${MAXH} h" >&2; RC=124; fi
if [ -n "$NAME" ]; then
  gcloud compute scp --zone "$ZONE" --quiet "$NAME:job.log" "$WORK/job.log" > /dev/null 2>&1 || true
fi
echo "--- job exit $RC; last lines of its log:"; tail -15 "$WORK/job.log" 2> /dev/null || true
mkdir -p "$(dirname "$FETCH")"
if [ -n "$NAME" ] && gcloud compute scp --zone "$ZONE" --quiet --recurse "$NAME:mf/$FETCH" "$WORK/fetched" > /dev/null 2>&1; then
  mkdir -p "$FETCH"; cp -R "$WORK/fetched/." "$FETCH/"
  echo "copied $FETCH back"
  # A finished job's cache is spent: clear it so a later MF_GCP_RESUME=1 run cannot be seeded with stale results.
  if [ -n "$CACHE" ] && [ "$RC" = 0 ]; then rm -rf "$CACHE"; fi
  if [ "$MODE" = exp ]; then echo "the orchestrator picks the results up on its next tick"; fi
else
  echo "nothing to copy back at $FETCH" >&2
  if [ -n "$CACHE" ] && [ -d "$CACHE/fetched" ]; then
    echo "partial results are cached in $CACHE/fetched: rerun with MF_GCP_RESUME=1 to continue" >&2
  fi
fi
if [ -n "$NAME" ]; then account "exit $RC"; fi
echo "--- VM time (the deleting step adds about a minute each):$ACCOUNT"
exit "$RC"
