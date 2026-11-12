#!/usr/bin/env bash
# T0322: launch procedure for E008's REGISTERED run, for the founder (agents never launch VMs). Pattern of burst_dev.sh,
# but the phase A -> phase B resize needs one VM that is stopped, resized and restarted with its disk, which
# scripts/burst_gcp.sh cannot do (it deletes its VM on every exit path and never resumes a registered run). So the
# lifecycle is plain gcloud here; burst_gcp.sh is used unchanged for the quota check only, and its rules are kept:
#   - the run is minted ONCE on this machine (uv run mfos exp mint E008) before any VM exists; the VM gets the run id and
#     the sealed seed file only, and runs `mfos exp run E008 --force --run-id <id> --seed-file ~/mf.seed`;
#   - the code reaches the VM only as a git bundle of main (the registration must be committed there);
#   - a regular VM (never Spot) for a registered run; nothing from an earlier run or cache is ever uploaded.
# Phases (founder constraint: one 8-vCPU N2D VM at a time):
#   A  on config.compute.vm's machine (n2d-custom-8-81920-ext): every solve whose estimate fits phase A's usable memory.
#      The runner stops by itself when only larger jobs remain (exit 75, <run>/work/phase_b_needed.json; no result).
#   B  the SAME VM is stopped, resized to the machine --plan names for the largest phase-B job (today 2D_Case_2R's F6(e)
#      FV level 3, 410.7 GB -> n2d-custom-8-499712-ext) and restarted; the SAME minted run is started again and resumes
#      from its own workdir on the same disk (every finished solve is a result file there), running each big job alone.
# Then the run directory is copied back to experiments/results/E008/<run id> and the VM is deleted.
# Re-running this script resumes from its state file (it never mints twice). Commands, expected output and failure modes:
# research/notes/e008-design.md section 11.
#   research/o003/e008_dev/burst_full.sh --dry-run    print every command in order, run none
#   research/o003/e008_dev/burst_full.sh              do it (needs gcloud, the registered spec on main)
# Environment: MF_GCP_ZONE (us-central1-a), MF_GCP_ZONES (zones to try for the create, default MF_GCP_ZONE then the
# region's others), MF_GCP_DISK_GB (40), MF_E008_STATE (~/.cache/mf-burst/e008_full), MF_E008_POLL_S (300),
# MF_E008_MAX_HOURS_A (30) / MF_E008_MAX_HOURS_B (20): VM self-stop backstop per phase (a stop keeps the disk).
set -euo pipefail
{
DRY=0
case "${1:-}" in
  --dry-run) DRY=1 ;;
  "") ;;
  *) echo "usage: research/o003/e008_dev/burst_full.sh [--dry-run]" >&2; exit 2 ;;
esac
cd "$(git rev-parse --show-toplevel)"
EID=E008
REF=main
ZONE="${MF_GCP_ZONE:-us-central1-a}"
REGION="${ZONE%-*}"
DISK_GB="${MF_GCP_DISK_GB:-40}"
POLL_S="${MF_E008_POLL_S:-300}"
MAXH_A="${MF_E008_MAX_HOURS_A:-30}"
MAXH_B="${MF_E008_MAX_HOURS_B:-20}"
STATE_DIR="${MF_E008_STATE:-$HOME/.cache/mf-burst/e008_full}"
STATE="$STATE_DIR/state.env"
SPEC=experiments/specs/E008.yaml
RUNNER=experiments/runners/e008_run.py

say() { printf '%s\n' "$*"; }
show() { printf '+'; printf ' %q' "$@"; printf '\n'; }
run() { show "$@"; if [ "$DRY" = 0 ]; then "$@"; fi; }   # every side-effecting command goes through run()
save() { if [ "$DRY" = 0 ]; then mkdir -p "$STATE_DIR"; printf '%s=%q\n' "$1" "$2" >> "$STATE"; fi; eval "$1=\"\$2\""; }
step_done() { [ "$DRY" = 0 ] && grep -qx "STEP_$1=1" "$STATE" 2> /dev/null; }
mark() { save "STEP_$1" 1; }

# ---- machine types: phase A from the spec's config.compute.vm, phase B from --plan (file reads only in --dry-run)
if [ ! -f "$SPEC" ]; then
  if [ "$DRY" = 1 ]; then say "# NOTE: $SPEC does not exist yet (E008 is not registered); --dry-run reads the draft"; SPEC=experiments/drafts/E008.yaml
  else say "E008 is not registered ($SPEC missing): register and commit it on $REF first" >&2; exit 1; fi
fi
TYPE_A="$(grep -m1 -oE 'machine: n2d-custom-8-[0-9]+-ext' "$SPEC" | cut -d' ' -f2)"
if [ "$DRY" = 1 ]; then
  say "# phase-B machine: the largest phase-B machine named in the spec's cost_estimate (filled by --plan); live: --plan below"
  TYPE_B="$(grep -oE 'n2d-custom-8-[0-9]+-ext' "$SPEC" | sort -t- -k4,4n | tail -1)"
fi
show uv run python "$RUNNER" --plan --plan-out "$STATE_DIR/plan.json"
if [ "$DRY" = 0 ]; then
  mkdir -p "$STATE_DIR"
  uv run python "$RUNNER" --plan --plan-out "$STATE_DIR/plan.json" > /dev/null
  # the largest phase-B machine over the expected and the all-counted scenarios (both cases)
  TYPE_B="$(python3 -c 'import json, sys
p = json.load(open(sys.argv[1]))
rows = [b for grp in ("cases", "if_all_counted") for c in p[grp].values() for b in c["phase_b_big_memory_jobs"]]
print(max(rows, key=lambda b: b["ram_GB"])["machine"] if rows else "")' "$STATE_DIR/plan.json")"
fi
RAM_B_GB="$(echo "${TYPE_B:-x-x-x-0-x}" | cut -d- -f4)"; RAM_B_GB=$((RAM_B_GB / 1024))
say "# phase A machine: $TYPE_A; phase B machine: ${TYPE_B:-none} (${RAM_B_GB} GB); zone $ZONE"
[ -n "$TYPE_A" ] || { say "no phase-A machine in $SPEC" >&2; exit 1; }

# ---- state (resume): RUN_ID, SEED_FILE, NAME, ZONE and finished steps
if [ "$DRY" = 0 ] && [ -f "$STATE" ]; then
  # shellcheck disable=SC1090
  . "$STATE"; say "# resuming from $STATE (run ${RUN_ID:-not minted yet})"
fi

# ---- 0. preflight (read-only): registration committed on main, clean code, gcloud project and N2D quota
show git cat-file -e "$REF:$SPEC"
show git status --porcelain --untracked-files=no -- src experiments/runners tools pyproject.toml uv.lock
if [ "$DRY" = 0 ]; then
  git cat-file -e "$REF:$SPEC" 2> /dev/null || { say "$EID's registration is not committed on $REF" >&2; exit 1; }
  [ -z "$(git status --porcelain --untracked-files=no -- src experiments/runners tools pyproject.toml uv.lock)" ] \
    || { say "uncommitted code changes: the run must use the commit on $REF" >&2; exit 1; }
fi
run scripts/burst_gcp.sh --check n2d-standard-8 "$ZONE"   # quota N2D_CPUS >= 8 in the region (custom types share it)

# ---- 1. mint the run once, here (never on the VM, never twice)
if [ -z "${RUN_ID:-}" ]; then
  show uv run mfos exp mint "$EID"
  if [ "$DRY" = 0 ]; then
    MINT="$(uv run mfos exp mint "$EID")"
    save RUN_ID "$(printf '%s' "$MINT" | python3 -c 'import json,sys; print(json.load(sys.stdin)["run_id"])')"
    save SEED_FILE "$(printf '%s' "$MINT" | python3 -c 'import json,sys; print(json.load(sys.stdin)["seed_file"] or "")')"
    [ -n "$SEED_FILE" ] || { say "E008 is sealed but mint returned no seed file" >&2; exit 1; }
    say "minted $RUN_ID"
  else
    RUN_ID="<RUN_ID printed by mint>"; SEED_FILE="<seed_file printed by mint>"
  fi
fi
RUNDIR="mf/experiments/results/$EID/$RUN_ID"            # on the VM, relative to ~
WORKDIR="$RUNDIR/work"                                   # the runner's default workdir (<run_dir>/work)
JOB="uv run mfos exp run $EID --force --run-id $RUN_ID --seed-file ~/mf.seed"

# ---- 2. one regular VM on phase A's machine (zones of the region in order; the disk stays in that zone)
if [ -z "${NAME:-}" ]; then
  save NAME "mf-e008-$(date +%s)"
  ZONES="${MF_GCP_ZONES:-$ZONE}"
  if [ "$DRY" = 0 ] && [ -z "${MF_GCP_ZONES:-}" ]; then
    ZONES="$ZONE $(gcloud compute zones list --filter="region:$REGION AND status:UP" --format='value(name)' | grep -vx "$ZONE" | tr '\n' ' ')"
  fi
  CREATED=0
  for z in $ZONES; do
    show gcloud compute instances create "$NAME" --zone "$z" --machine-type "$TYPE_A" --image-family ubuntu-2404-lts-amd64 \
      --image-project ubuntu-os-cloud --boot-disk-size "${DISK_GB}GB" --boot-disk-type pd-balanced --quiet
    if [ "$DRY" = 1 ]; then CREATED=1; ZONE="$z"; break; fi
    if err="$(gcloud compute instances create "$NAME" --zone "$z" --machine-type "$TYPE_A" --image-family ubuntu-2404-lts-amd64 \
        --image-project ubuntu-os-cloud --boot-disk-size "${DISK_GB}GB" --boot-disk-type pd-balanced --quiet 2>&1 > /dev/null)"; then
      CREATED=1; save ZONE "$z"; break
    fi
    if echo "$err" | grep -qE "ZONE_RESOURCE_POOL_EXHAUSTED|resource_availability|does not have enough resources|STOCKOUT"; then
      say "$TYPE_A is unavailable in $z; trying the next zone" >&2; continue
    fi
    say "$err" >&2; exit 1
  done
  [ "$CREATED" = 1 ] || { say "$TYPE_A is unavailable in: $ZONES. Nothing was started; rerun later (the run stays minted)" >&2; NAME=""; exit 1; }
fi
SSH=(gcloud compute ssh "$NAME" --zone "$ZONE" --quiet --command)
SCP=(gcloud compute scp --zone "$ZONE" --quiet)

# ---- 3. set-up (idempotent, as burst_gcp.sh; no FastHenry/ngspice build) and the sealed seed
REMOTE='set -euo pipefail
if [ ! -e ~/mf.ready ]; then
export DEBIAN_FRONTEND=noninteractive
sudo apt-get -o DPkg::Lock::Timeout=300 update -qq
sudo apt-get -o DPkg::Lock::Timeout=300 install -y -qq git build-essential curl > /dev/null
curl -LsSf https://astral.sh/uv/install.sh | sh > /dev/null
export PATH="$HOME/.local/bin:$PATH"
rm -rf ~/mf && git clone -q ~/mf.bundle ~/mf && cd ~/mf && git checkout -q '"$REF"'
uv sync -q --all-groups
touch ~/mf.ready
fi
echo "host: $(hostname), $(nproc) vCPU, $(free -g | awk "/Mem:/ {print \$2}") GB"'
if ! step_done setup; then
  show git bundle create "$STATE_DIR/mf.bundle" "$REF"
  if [ "$DRY" = 0 ]; then git bundle create -q "$STATE_DIR/mf.bundle" "$REF"; fi
  if [ "$DRY" = 0 ]; then
    for _ in $(seq 1 60); do "${SSH[@]}" true > /dev/null 2>&1 && break; sleep 5; done
  fi
  # the checkpoint cleaner used after an unplanned stop (no here-document: macOS bash 3.2 mis-parses them in a brace group)
  if [ "$DRY" = 0 ]; then printf '%s\n' 'import json, pathlib, sys' 'for f in pathlib.Path(sys.argv[1]).rglob("*.json"):' \
    '    try:' '        json.loads(f.read_text())' '    except ValueError:' '        f.unlink()' \
    '        print(f"dropped unreadable {f}")' > "$STATE_DIR/drop_bad.py"; fi
  run "${SCP[@]}" "$STATE_DIR/drop_bad.py" "$NAME:drop_bad.py"
  run "${SCP[@]}" "$STATE_DIR/mf.bundle" "$NAME:mf.bundle"
  run "${SSH[@]}" "$REMOTE"
  run "${SCP[@]}" "$SEED_FILE" "$NAME:mf.seed"
  run "${SSH[@]}" "chmod 600 ~/mf.seed"
  mark setup
fi

# ---- phase helpers: start (idempotent: not if finished or running), wait, read the runner's exit code
start_phase() {  # $1: A|B  $2: extra environment ("" or E008_SOLO_RAM_GB=<GB>)  $3: backstop hours
  local p="$1" envs="$2" h="$3"
  # Not started again if it finished (rc file) or was started in this boot (boot marker): a rerun of this script
  # while the job runs changes nothing. After an unplanned stop (new boot) it restarts and the run resumes; a result
  # file cut mid-write is unreadable, so drop_bad.py removes it and that one solve is recomputed.
  run "${SSH[@]}" "set -u; [ -e ~/phase$p.rc ] && exit 0; B=\$(cat /proc/sys/kernel/random/boot_id); \
[ \"\$(cat ~/phase$p.boot 2> /dev/null)\" = \"\$B\" ] && exit 0; echo \$B > ~/phase$p.boot; \
mkdir -p ~/$WORKDIR && python3 ~/drop_bad.py ~/$WORKDIR; sudo shutdown -h +$((h * 60)) > /dev/null 2>&1; \
nohup bash -c 'export PATH=\$HOME/.local/bin:\$PATH; cd ~/mf && $envs $JOB > ~/phase$p.log 2>&1; echo \$? > ~/phase$p.rc' \
> /dev/null 2>&1 < /dev/null & echo started phase $p"
}
wait_phase() {  # $1: A|B; returns when ~/phase<p>.rc exists; exits 3 if the VM stops under the job
  local p="$1" rc="" st n=0
  show "${SSH[@]}" "cat ~/phase$p.rc"
  say "# (every $POLL_S s until it exists; also: gcloud compute instances describe $NAME --zone $ZONE --format='value(status)')"
  [ "$DRY" = 1 ] && return 0
  while [ -z "$rc" ]; do
    sleep "$POLL_S"; n=$((n + 1))
    rc="$("${SSH[@]}" "cat ~/phase$p.rc 2> /dev/null" 2> /dev/null | tr -d '[:space:]' || true)"
    if [ -z "$rc" ]; then
      st="$(gcloud compute instances describe "$NAME" --zone "$ZONE" --format='value(status)' 2> /dev/null || echo unknown)"
      case "$st" in
        TERMINATED|STOPPED|SUSPENDED)
          say "VM $NAME is $st during phase $p (host event or the ${MAXH_A}/${MAXH_B} h backstop). The disk and the run's" >&2
          say "workdir are kept: rerun this script; it starts the VM and the same run resumes (design note section 11)." >&2
          exit 3 ;;
      esac
      [ $((n % 6)) = 0 ] && "${SSH[@]}" "tail -2 ~/$RUNDIR/runner.log 2> /dev/null" 2> /dev/null || true
    fi
  done
  say "phase $p finished (mfos exit $rc)"
}
runner_exit() {  # the runner's own exit code, recorded by the mfos wrapper in run.json
  "${SSH[@]}" "python3 -c 'import json; print(json.load(open(\"$RUNDIR/run.json\"))[\"exit_code\"])'" 2> /dev/null | tr -d '[:space:]'
}
ensure_running() {  # after an unplanned stop (rerun of this script): start the VM again, same type, same disk
  [ "$DRY" = 1 ] && return 0
  local st
  st="$(gcloud compute instances describe "$NAME" --zone "$ZONE" --format='value(status)')"
  if [ "$st" != RUNNING ]; then run gcloud compute instances start "$NAME" --zone "$ZONE"; fi
  for _ in $(seq 1 60); do "${SSH[@]}" true > /dev/null 2>&1 && break; sleep 5; done
}

# ---- 4. phase A
if ! step_done phaseA; then
  ensure_running
  start_phase A "" "$MAXH_A"
  wait_phase A
  mark phaseA
fi
# read once while the VM still runs and kept in the state file: a rerun after a stop never needs ssh for it
if [ "$DRY" = 1 ]; then RC_A=75; elif [ -z "${RC_A:-}" ]; then save RC_A "$(runner_exit)"; fi
[ -n "$RC_A" ] || { say "could not read the runner's exit code of phase A (VM unreachable?): rerun this script" >&2; exit 7; }
say "# phase A runner exit: $RC_A (0: finished, no phase B needed; 75: phase B needed; else: failed)"

# ---- 5. phase B: stop, resize to --plan's machine, start, the same run resumes from its workdir
if [ "$RC_A" = 75 ]; then
  if ! step_done phaseB; then
    show "${SSH[@]}" "cat ~/$WORKDIR/phase_b_needed.json"
    if [ "$DRY" = 0 ] && ! step_done resized; then
      NEED="$("${SSH[@]}" "cat ~/$WORKDIR/phase_b_needed.json")"; say "$NEED"
      NEED_RAM="$(printf '%s' "$NEED" | python3 -c 'import json,sys; print(int(json.load(sys.stdin)["ram_GB_by_plan_rule"]))')"
      if [ -z "${TYPE_B:-}" ] || [ "$NEED_RAM" -gt "$RAM_B_GB" ]; then
        run gcloud compute instances stop "$NAME" --zone "$ZONE"
        say "phase B needs $NEED_RAM GB, more than --plan's ${RAM_B_GB} GB: VM stopped (disk kept). The founder decides." >&2
        exit 4
      fi
      run "${SSH[@]}" "cp ~/$RUNDIR/runner.log ~/$RUNDIR/runner.phaseA.log"
    fi
    if ! step_done resized; then
      run gcloud compute instances stop "$NAME" --zone "$ZONE"
      run gcloud compute instances set-machine-type "$NAME" --zone "$ZONE" --machine-type "$TYPE_B"
      mark resized
    fi
    if [ "$DRY" = 1 ]; then
      run gcloud compute instances start "$NAME" --zone "$ZONE"
    else
      STARTED=0
      for i in $(seq 1 "${MF_E008_START_TRIES:-12}"); do
        if out="$(gcloud compute instances start "$NAME" --zone "$ZONE" 2>&1)"; then STARTED=1; break; fi
        say "start $i failed: $(echo "$out" | tail -1)" >&2
        echo "$out" | grep -qE "ZONE_RESOURCE_POOL_EXHAUSTED|resource_availability|does not have enough resources|STOCKOUT" || break
        sleep 600
      done
      [ "$STARTED" = 1 ] || { say "$TYPE_B could not start in $ZONE: VM left stopped (disk kept, only disk billed). Rerun later; see design note section 11." >&2; exit 5; }
      ensure_running
    fi
    start_phase B "E008_SOLO_RAM_GB=$RAM_B_GB" "$MAXH_B"
    wait_phase B
    mark phaseB
  fi
  if [ "$DRY" = 1 ]; then RC_B=0; elif [ -z "${RC_B:-}" ]; then save RC_B "$(runner_exit)"; fi
  [ -n "$RC_B" ] || { say "could not read the runner's exit code of phase B (VM unreachable?): rerun this script" >&2; exit 7; }
  say "# phase B runner exit: $RC_B (0: the run is complete)"
  RC_FINAL="$RC_B"
else
  RC_FINAL="$RC_A"
fi

# ---- 6. copy the run directory back, then delete the VM (only once the copy is verified)
[ "$DRY" = 1 ] || mkdir -p "experiments/results/$EID"
run "${SCP[@]}" --recurse "$NAME:$RUNDIR" "experiments/results/$EID/"
if [ "$DRY" = 0 ]; then
  for f in result.json run.json; do
    [ -f "experiments/results/$EID/$RUN_ID/$f" ] || { say "copy-back incomplete ($f missing): the VM is kept; rerun this script" >&2; exit 6; }
  done
fi
if [ "$RC_FINAL" = 0 ]; then
  run gcloud compute instances delete "$NAME" --zone "$ZONE" --quiet
  if [ "$DRY" = 0 ]; then mv "$STATE" "$STATE.done-$(date +%s)"; fi
  say "copied experiments/results/$EID/$RUN_ID back and deleted $NAME; the orchestrator evaluates the run on its next tick"
else
  run gcloud compute instances stop "$NAME" --zone "$ZONE"
  say "the run ended with runner exit $RC_FINAL; its result is copied back; the VM is STOPPED (not deleted) for inspection:" >&2
  say "  gcloud compute instances delete $NAME --zone $ZONE   once nothing more is needed from it" >&2
  [ "$DRY" = 1 ] || exit 1
fi
exit 0
}
