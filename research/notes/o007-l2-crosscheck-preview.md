# O007 cross-check preview: L2 at levels 1-3 on the two dev layouts (T0204)

Diagnostic, not evidence (no ExperimentRun). It informs E009's VM sizing and gives an early read on F5. F5 requires the
in-house L2's own A4 GCI (`mfos.metrics.gci_capped`, floor 1e-3 K, levels 1-3, r = 2) ≤ 0.25 K on every die.
Script: `research/scripts/o007_l2_preview.py`. Output: `research/o007_l2/preview.json`. Only the dev layouts were used
(dev seed 20261101: `side_by_side_6`, `u_shaped_2`; both fingerprints asserted equal to `experiments/specs/E006.yaml`). Only
their E006 rows were used, selected through an explicit allow-list. E006's fresh (held-out) rows are never read by the script.

## Exact burst command (founder)

```bash
scripts/burst_gcp.sh --cmd "uv run python research/scripts/o007_l2_preview.py --full --out research/o007_l2/full.json" research/o007_l2
```

- **Recommended VM RAM: 256 GB.** That is the script's default machine, `n2-highmem-32`, so no machine-type argument is needed.
  A `n2-highmem-16` (128 GB, append `n2-highmem-16` to the command) passes the preflight but leaves no margin at the
  locally measured memory rate (see below).
- `burst_gcp.sh` ships `MF_REF` (default `main`). This script must therefore be on `main` before the run, or the run must
  be started with `MF_REF=<this task's branch>`. Agents cannot merge.
- Every solve runs in its own child process and is checkpointed to `research/o007_l2/full_ckpt/<layout>_L<l>.json`.
  `research/o007_l2` is copied back, so an interrupted run resumes when the same command is run again. Exit code 3 means
  the preflight refused a solve.
- Expected wall time on E006's VM type is about 1.0-1.5 h (inference, below).

## Facts (measured or read; reproducible with the dry run)

**Cell counts** (active cells, `thermal_layout.build_layout_grid`). All levels 0-3 were built, level 3 in a child
process with a peak RSS of 0.92 / 0.63 GB. Each level has exactly 8× the cells of the previous one, and E006's recorded
counts for levels 0-2 match.

| layout | dies | L1 | L2 | L3 | mem est. at 1500 B/cell (L1 / L2 / L3) |
|---|---|---|---|---|---|
| side_by_side_6 | 12 | 907,424 | 7,259,392 | 58,075,136 | 1.36 / 10.9 / **87.1 GB** |
| u_shaped_2 | 4 | 560,528 | 4,484,224 | 35,873,792 | 0.84 / 6.73 / **53.8 GB** |

**Level-1 solves on this Mac**, at E006's power: 31.842 W per die (side_by_side_6) and 46.168 W per die (u_shaped_2).
- side_by_side_6: 4.7-5.5 s; peak RSS 1.55-1.74 GB over three runs (macOS RSS varies about 10 %).
- u_shaped_2: 3.0-3.2 s; peak RSS 1.11 GB.
- Memory above the post-build baseline is **1.78 kB/cell** for both layouts. That is *above* E006's planning figure of
  1500 B/cell.
- Energy balance ≤ 1e-14. Final Picard step 7e-6 K and 1.9e-5 K (5 iterations).
- Per-die Tj max reproduces E006's `f_lv1` within 2e-10 K. `git diff bb0725f` (E006's commit) over `solvers/thermal_*`,
  `geometry/` and `generate/` is empty.
- The full-mode smoke run (levels 0-2, cap 2 GB) reproduced E006's `f_lv0` and `f_lv1` within 1e-10 K, refused level 2
  through the preflight (exit 3) and resumed from its checkpoints.

**E006's own VM record** (result.json, burst VM, Linux) for the dev layouts:
- L2 wall times: 2.07 / 17.8 / 180 s (side_by_side_6) and 1.42 / 11.9 / 120 s (u_shaped_2). Each level costs 8.4-10.1× the previous one.
- Peak RSS on its largest solve (case 1b, 23.2 M cells) was 24.9 GB. That is ≤ 1.07 kB/cell, since `ru_maxrss` is cumulative.

**E006 levels 0-2 on the dev dies** (`f_lv0..f_lv2`, run E006-20261102T145940-2815):
- All 16 dies converge monotonically from above. 13 are in the `monotone` branch and 3 in `fast`.
- p_obs is 1.48-2.30 on side_by_side_6. On u_shaped_2 it is 1.67-1.71 for dies 0-1 and **0.96-0.97 for dies 2-3**.
- GCI_02 is at most 0.303 K, on u_shaped_2 die 3.

## Prediction of the levels 1-3 GCI (inference)

**Primary assumption:** the observed step ratio ρ = d2/d1 holds for one more level, so d3 = ρ·d2. Under this rule the
predicted GCI_13 is ρ × GCI_02 in the monotone and fast branches. Every die stays in its branch.

| layout / die | branch, p_obs (0-2) | GCI_02 K | **pred GCI_13 K** | **F5 margin K** | order 1 (ρ'=0.5) | two-term h¹+h² | sign flip of d3 | break-even ρ' (p*) |
|---|---|---|---|---|---|---|---|---|
| sbs6 die 0 | monotone 1.48 | 0.146 | 0.052 | **0.198** | 0.073 | 0.059 | 0.351 ✗ | 0.71 (0.50) |
| sbs6 dies 1-5 | monotone 1.57-1.77 | 0.126-0.150 | 0.042-0.047 | 0.203-0.208 | 0.063-0.075 | 0.047-0.052 | 0.303-0.360 ✗ | 0.70-0.73 |
| sbs6 dies 6-11 | monotone/fast 1.95-2.30 | 0.087-0.122 | 0.021-0.029 | 0.221-0.229 | 0.042-0.056 | 0.021-0.030 | 0.200-0.268 (2 of 6 ✗) | 0.75-0.79 |
| u2 die 0 | monotone 1.71 | 0.167 | 0.051 | 0.199 | 0.084 | 0.057 | 0.402 ✗ | 0.69 (0.55) |
| u2 die 1 | monotone 1.67 | 0.179 | 0.056 | 0.194 | 0.090 | 0.063 | 0.431 ✗ | 0.67 (0.57) |
| **u2 die 2** | monotone **0.96** | 0.295 | **0.151** | **0.099** | 0.140 | 0.145 | 0.670 ✗ | **0.60 (0.74)** |
| **u2 die 3** | monotone **0.97** | 0.303 | **0.155** | **0.095** | 0.145 | 0.150 | 0.696 ✗ | **0.59 (0.75)** |

Exact per-die values are in `preview.json` under `layouts.<name>.dies[*]`, as `scenarios_gci_13_K` and `break_even_rho`.
The break-even ρ' is the largest same-sign ratio d3/d2 that still gives GCI_13 ≤ 0.25 K.

**Predicted F5 margin:**
- side_by_side_6: at least 0.198 K (largest predicted GCI_13 = 0.052 K).
- u_shaped_2: at least **0.095 K** (die 3, predicted 0.155 K).
- The binding dies are u_shaped_2 dies 2 and 3.

**Sensitivity:**
- *Order and step ratio.* Same-sign scenarios all pass:
  - order 2 or order 1 for the next step;
  - two-term fits f* + a·h^p1 + b·h² with p1 = 1 or p1 = 1.66, the corner order 2λ that `thermal_layout`'s docstring states;
  - |d3| below the 1e-3 K floor.
  The worst of them is u2 die 3 at 0.155 K. F5 fails on the binding dies only if their step ratio *rises* from 0.51 to
  above 0.59-0.60 (p_obs falls below about 0.75). On the other dies it fails only if ρ' rises above 0.67-0.79.
- *Power.* E009 calibrates power on scikit-fem level 0, not on L2 level 0. E006's own scikit-fem level 0 (a different
  rule from E009's) gave hottest rises of 59.38 / 58.67 K at E006's power. Scaling the GCI linearly with power raises
  the predictions by 1.1 % and 2.3 %: at most 0.158 K, margin 0.092 K. This is approximate, because E009's scikit-fem
  rule is not frozen yet.
- *Branch.* The prediction is fragile here. If d3 changes sign on a die, the A4 rule uses 3·max(|d2|, |d3|) with d2 = E006's level 1→2 step (0.08-0.23 K). F5 then fails
  on **8 of 12** side_by_side_6 dies and **all 4** u_shaped_2 dies. No sign change was seen at levels 0-2 on any dev die.

## Memory and RAM sizing (inference)

- The preflight copies `e006_run.preflight`: active cells × 1500 B must not exceed 0.85 × physical memory. Level 3 of
  side_by_side_6 therefore needs ≥ 102.5 GB physical.
- At the locally measured 1.78 kB/cell, its level-3 peak would be about 104 GB. At E006's Linux-measured ≤ 1.07 kB/cell
  it would be about 62 GB. u_shaped_2 level 3 would be 38-64 GB.
- Sizing at the larger rate, with 0.85 headroom, needs 121.8 GB physical. Assuming the guest reports 95 % of nominal
  RAM, 128 GB gives 121.6 GB, just short. Hence 256 GB.
- 128 GB (n2-highmem-16) is plausible if the Linux rate holds (inference from one cumulative E006 figure), but it has no
  margin. Solves are strictly sequential: the parent holds only the level-0 count.
- None of the level-2 or level-3 solves fits this Mac's 5 GB agent budget. side_by_side_6 L2 is estimated at 10.9 GB at
  1500 B/cell. No local level-2 or level-3 solve was attempted.

**Wall time (inference):** at E006's level-to-level growth (×10.1), level 3 takes about 1820 s (side_by_side_6) and
1210 s (u_shaped_2). At 1.5× that growth it takes 2730 s and 1820 s. Levels 1-2 add about 330 s. Total about 0.9-1.4 h on
E006's VM type. pyamg and scipy CG are largely single-threaded, so extra vCPUs buy little.

## Competing explanations for the F5 outcome, and what discriminates them (speculation until the full run)

1. **Asymptotic monotone convergence.** Levels 1-3 keep ρ near its levels 0-2 value, and F5 passes with a margin of at
   least about 0.09 K.
   *Prediction:* the full run's levels 1-3 ρ is close to the levels 0-2 ρ for every die.
2. **u_shaped_2 dies 2-3 are pre-asymptotic, with a lower-order term dominating.** These two dies have p_obs ≈ 0.96,
   unlike the other 14 dies (1.5-2.3). A slower-decaying error term (for example a non-edge-graded feature line near
   them) could hold ρ at 0.5 or push it higher.
   *Discriminating test:* the full run's ρ for those two dies. A value above 0.6 fails F5 and this preview with it.
3. **The Tj-max location moves between levels**, and the sign of d3 flips.
   *Discriminating test:* the sign of d3 per die in `full.json` (`direction`, `branch` = oscillatory).
   This is the explanation that would most clearly prove the primary prediction wrong.

No local test can separate these: each needs a level-3 solve, which needs more than 5 GB. Cheap tests that were run, and
whose outcomes support the inputs of the prediction rather than the prediction itself:
- the level-1 reproduction (2e-10 K);
- the bisection identity at levels 0-3;
- equality between the GCI copy in `thermal_layout` and `mfos.metrics`, asserted in the script;
- recomputation of each E006 `gci` from `f_lv0..2`, asserted to 1e-12.

**What would prove this preview wrong:** any dev die in `full.json` with `gci_capped_K` > 0.25 K, or with branch
`oscillatory` or `divergent`.

## Caveats

- The packet lists `experiments/results/E006/E006-20261102T145940-2815/runner.log`, but that file is not present. Solve
  statistics were taken from the dev-layout tags in `result.json`.
- While locating those statistics I printed the solve-stat lines (cells and wall time only, no temperatures) of all
  E006 solves, including the three fresh layouts. They were not used anywhere. The script reads only the dev tags.
- Three of the five A3 layouts are fresh sealed-seed layouts that are not previewed here, by design. F5's outcome on
  them is unknown. The 0.095 K margin applies to the dev layouts only.
- The full mode uses E006's power as a proxy. E009 recalibrates its power, so the GCI values that F5 judges will differ
  by about the power ratio (about 1-2 % on this evidence).
