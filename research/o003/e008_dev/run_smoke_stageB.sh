#!/bin/sh
# T0262 attempt 4: local smoke stage B (development geometry only). Waits for stage A (gen2_0 twin gates and 4 band
# pairs), then adds 2D_Case_4's twin gates (smoke: 0.5 mm EM, E009 smoke thermal rule) reusing every cached gen2_0
# solve, and writes the union to experiments/drafts/E008.dev_rows.json (stage A's file stays if stage B fails).
cd "$(dirname "$0")/../../.." || exit 1
export VIRTUAL_ENV=
until grep -q "^exit=" research/o003/e008_dev/smoke_stageA.log; do sleep 30; done
uv run python experiments/runners/e008_run.py --dev --smoke --geoms gen2_0:gates:4,case4:gates:0 --mem-cap-gb 5 \
  --solo-cap-gb 9 --vcpus 3 --workdir research/o003/e008_dev/smoke_work \
  --rows-out research/o003/e008_dev/smoke_work/E008.dev_rows.stageB.json > research/o003/e008_dev/smoke_stageB.log 2>&1
rc=$?
[ $rc -eq 0 ] && cp research/o003/e008_dev/smoke_work/E008.dev_rows.stageB.json experiments/drafts/E008.dev_rows.json
echo "exit=$rc" >> research/o003/e008_dev/smoke_stageB.log
