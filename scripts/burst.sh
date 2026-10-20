#!/usr/bin/env bash
# Run ONE registered experiment on an ephemeral Hetzner Cloud VM, copy its results back, delete the VM.
# The VM is deleted on every exit path (trap). Results keep full provenance (commit, spec hash, host).
#
# Usage:   scripts/burst.sh E002 [server-type] [location]      e.g. scripts/burst.sh E002 ccx53 fsn1
# Setup (once):
#   brew install hcloud
#   hcloud context create moduleforge          # paste a project API token (Read & Write)
#   hcloud ssh-key create --name mf --public-key-from-file ~/.ssh/id_ed25519.pub
set -euo pipefail
EID="${1:?usage: scripts/burst.sh <EXPERIMENT_ID> [server-type] [location]}"
TYPE="${2:-ccx33}"; LOC="${3:-fsn1}"
NAME="mf-burst-$(echo "$EID" | tr '[:upper:]' '[:lower:]')-$(date +%s)"
cd "$(git rev-parse --show-toplevel)"
test -f "experiments/specs/$EID.yaml" || { echo "$EID is not registered (experiments/specs/$EID.yaml missing)" >&2; exit 1; }
if [ -n "$(git status --porcelain --untracked-files=no -- src experiments/runners tools pyproject.toml uv.lock)" ]; then
  echo "uncommitted code changes: the experiment must run on a commit that is on main" >&2; exit 1
fi
git cat-file -e "main:experiments/specs/$EID.yaml" 2> /dev/null \
  || { echo "$EID's registration is not committed on main: commit it first (the run must cite a commit with its spec)" >&2; exit 1; }
# Mint the run here, before any VM exists: its id and seed commitment go into experiments/registry.jsonl on this
# machine, and the VM runs exactly that run (mfos exp run --run-id/--seed-file). Evaluator 2.0.0 uses the first
# minted run, so a run cannot be repeated quietly until a result looks good.
MINT="$(uv run mfos exp mint "$EID")"
RUN_ID="$(printf '%s' "$MINT" | python3 -c 'import json,sys; print(json.load(sys.stdin)["run_id"])')"
SEED_FILE="$(printf '%s' "$MINT" | python3 -c 'import json,sys; print(json.load(sys.stdin)["seed_file"] or "")')"
echo "minted $RUN_ID"
BUNDLE="$(mktemp -d)/mf.bundle"
git bundle create -q "$BUNDLE" main        # no GitHub credentials ever reach the VM
OPTS=(-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=5 -o LogLevel=ERROR)
hcloud server create --name "$NAME" --type "$TYPE" --image ubuntu-24.04 --location "$LOC" --ssh-key mf > /dev/null
trap 'echo "deleting $NAME"; hcloud server delete "$NAME" > /dev/null' EXIT
IP="$(hcloud server ip "$NAME")"
echo "$NAME ($TYPE) at $IP"
for _ in $(seq 1 60); do ssh "${OPTS[@]}" "root@$IP" true 2> /dev/null && break; sleep 5; done
scp -q "${OPTS[@]}" "$BUNDLE" "root@$IP:/root/mf.bundle"
if [ -n "$SEED_FILE" ]; then scp -q "${OPTS[@]}" "$SEED_FILE" "root@$IP:/root/mf.seed"; fi
ssh "${OPTS[@]}" "root@$IP" bash -s "$EID" "$RUN_ID" "${SEED_FILE:+/root/mf.seed}" << 'REMOTE'
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq && apt-get install -y -qq git build-essential > /dev/null
curl -LsSf https://astral.sh/uv/install.sh | sh > /dev/null
export PATH="$HOME/.local/bin:$PATH"
git clone -q /root/mf.bundle /root/mf && cd /root/mf
scripts/provision_compute.sh
uv sync -q --all-groups
uv run mfos exp run "$1" --force --run-id "$2" ${3:+--seed-file "$3"}
REMOTE
mkdir -p "experiments/results/$EID"
scp -q -r "${OPTS[@]}" "root@$IP:/root/mf/experiments/results/$EID/*" "experiments/results/$EID/"
echo "results copied to experiments/results/$EID/; the orchestrator picks them up on its next tick"
