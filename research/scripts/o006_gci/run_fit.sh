#!/bin/sh
# Replacement (memory-feasible) pairs: solve gen #3 of each family at levels 0-2 (gen #1 is shared with the first pairs).
cd "$(dirname "$0")/../../.." || exit 1
unset VIRTUAL_ENV
J=research/scripts/o006_gci/pair_jobs.py
for lv in ${LEVELS:-0 1 2}; do for f in side_by_side interleaved u_shaped; do
  uv run python $J job $f B $lv fit 2>&1 | grep -v warning; done; done
