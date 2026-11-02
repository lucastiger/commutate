#!/bin/sh
# Sequential pair jobs, cheapest first (one process per layout x level). Research only.
cd "$(dirname "$0")/../../.." || exit 1
unset VIRTUAL_ENV
J=research/scripts/o006_gci/pair_jobs.py
for lv in 0 1; do for f in side_by_side interleaved u_shaped; do for t in A B; do
  uv run python $J job $f $t $lv 2>&1 | grep -v warning; done; done; done
for f in side_by_side interleaved u_shaped; do uv run python $J job $f B 2 2>&1 | grep -v warning; done
for f in side_by_side interleaved u_shaped; do uv run python $J job $f A 2 2>&1 | grep -v warning; date; done
uv run python $J assemble 2>&1 | grep -v warning
