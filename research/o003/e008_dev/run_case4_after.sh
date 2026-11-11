#!/bin/sh
# T0262: waits for the first local smoke chain (gen2_0 gates, then the cost probe) and then runs 2D_Case_4's twin gates.
cd "$(dirname "$0")/../../.." || exit 1
while ! grep -qE '^\{|Traceback' research/o003/e008_dev/probe.log 2>/dev/null; do sleep 30; done
cp experiments/drafts/E008.dev_rows.json research/o003/e008_dev/dev_rows_gen2.json 2>/dev/null
uv run python experiments/runners/e008_run.py --dev --smoke --geoms case4:gates --band-pairs 2 --mem-cap-gb 5 \
  --solo-cap-gb 9 --vcpus 2 --workdir experiments/drafts/E008_dev_work \
  --rows-out research/o003/e008_dev/dev_rows_case4.json > research/o003/e008_dev/dev_case4.log 2>&1
