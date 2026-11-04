# O007 development study 2 (T0228): pre-registered freeze of the graded scikit-fem rule

Author: scientist, T0228 attempt 1, 2026-11-04. Script: `research/scripts/o007_dev_study2.py` (reuses
`o007_dev_study.py` and `o007_probe.py` by import). Outputs: `research/o007_dev2/{dev_study.json, frozen_config.json,
plan.json, preregistration.json, cache/}`.
Labels: **[F]** fact (file or listed command), **[I]** inference, **[S]** speculation or extrapolation.

## 0. Pre-registration (written and committed before any solve of this study)

**What was run before this section.** Grid construction only: a scratch survey and `o007_dev_study2.py --plan`
(`plan.json`), giving DOF counts, cell-width ratios and die-centroid offsets. No temperature was computed in this task.
**Prior data, disclosed:** the T0225 probe already measured this rule on the N-layer DBC case at levels 0-2
(max |T - T_ref| 0.591 / 0.152 / 0.0386 K, CG max 132 / 191 / 259; `research/notes/o007-probe.md` sec. 7). T0207's
ungraded Q1 values on all other problems are also known. Nothing else under this rule has been solved.

### 0.1 Candidates

**Candidate 1, `a_q1h4_graded`** (exactly T0225 option (a), built through the production `GridRule`, T0227):
Q1 (2x2x2 Gauss), h0 4 mm, near_margin 2 mm, dz_max 1 mm, nz_min 1 (default_nz 1, `nz={}`), min_cells 2, zrefine,
`edge_grading = (1e-4, 2.5, 4e-3, 0.5)` (first offset, ratio, max offset, min-gap fraction). Mandatory lines as in
production and T0207: source centroids plus the frozen series maxima (box-stack); the manufactured case's frozen point
lines (layout mode); no extra lines on the generator layouts. In layout mode the grading's fixed set also holds every
layout geometry line (T0227/T0231). SNAP_FRACTION 1e-2. linear_rtol 1e-11, CG cap 400, AMG seed and Picard tolerance
1e-4 K as in production. Levels [0, 1, 2], r = 2 in x, y and z.

**No candidate 2.** The choice rule picks the cheapest eligible candidate. Any second rule aimed at the main kill
risk (the 3.5 % margin of the N-layer A2 at 0.0386 K, or Tj-max non-convergence on the dev dies) refines the grading,
so it costs more than candidate 1. It could only change the outcome if candidate 1 fails. In that case, a new
pre-registration with candidate 1's level-2 data in hand is the better design. A second candidate now would roughly
double the local compute and the founder burst.

[F] Level-0 / 1 / 2 DOF of candidate 1 (`plan.json`): Case 1a 135,531 / 1,025,661 / 7,973,721; Case 1b 160,173 /
1,221,025 / 9,529,569; Cases 2 and 3 99,275 / 750,141 / 5,827,289 each; N-layer 232,130 / 1,752,579 / 13,606,565;
manufactured 28,683 / 207,837 / 1,577,913; side_by_side_6 167,682 / 1,237,087 / 9,483,501; u_shaped_2 70,604 /
517,263 / 3,950,429. Minimum neighbour lateral cell-width ratio at L0: 1a 0.013, 1b 0.031, 2 0.010, 3 0.146, N-layer
0.066, manufactured 0.20, side_by_side_6 0.083, u_shaped_2 0.091. [I] The 1a and 2 values are the max-line sliver
signature of T0225 part 1, so CG headroom on those plates is a live risk.

### 0.2 Eligibility (T0207 note sec. 0.2, criteria 1-4, unchanged)

Measured at **level 2 on all six cases and both dev layouts**:
1. **Gates.** Energy balance <= 1e-6 (manufactured case: also |Q_out / 64.648 W - 1| <= 1e-6). Picard residual
   < 1e-4 K. Node-count growth 8 +/- 15 % per level. Every reported point is a node at every level, with stencils
   recorded. No linear-solve failure.
2. **CG headroom.** At most 300 CG iterations in every L0-L2 solve at every Picard step. This includes the
   dev-layout calibration solves. Counted by T0207's `cg_only` callback. `meta["cg_iterations"]` (T0222) is
   recorded alongside as a cross-check.
3. **Accuracy at level 2.** A1 analogue (max scaled error) <= 0.008. A2 analogue (max |T - T_ref|) <= 0.040 K.
   A4 (max `mfos.metrics.gci_capped`, floor 1e-3 K) <= 0.40 K on the cases and <= 0.25 K on the dev-layout dies
   (Tj_max per die).
4. **Memory.** Every E009 finest solve <= 217.6 GB (0.85 x 256 GB, n2-highmem-32). Each solve's peak is the measured
   peak where that exact solve ran. Otherwise it is DOF x the maximum measured whole-process Q1 bytes/DOF over solves
   with >= 1 M DOF (T0207, T0225 and this study). Fresh layouts count as 1.5 x the larger dev layout's DOF.

**Choice.** The cheapest eligible candidate by E009 finest-level peak memory, here candidate 1 if eligible.
`feasible` is true only if every criterion is **measured at level 2** on every case and layout and the reuse check of
0.5 passes. A level that the local memory rule does not allow leaves the candidate *unverified*, not eligible. Before
the founder's burst the expected state is `feasible: false`, with `levels_run` and `levels_missing` showing the gap.
A criterion missed with measured data rules the candidate out at once (`ruled_out`), whatever the missing levels.

### 0.3 Problems and records (as T0207)

- Cases 1a, 1b, 2, 3 and the N-layer DBC case in box-stack mode. The manufactured case in layout mode. All use O006's
  frozen references, checked first by `load_refs` (sha256 `befc5efa...`, `ca05847b...`).
- Dev seed 20261101 only: side_by_side with dies_per_switch 6 and u_shaped with 2. E006 fingerprints are asserted.
  No other seed, no fresh layouts, no data/holdout.
- Operating point: equal power per die, calibrated on level 0 to a hottest-die rise of 60 +/- 1 K above 65 C coolant,
  h = 5000 W/(m2 K), k(T).
- Per point and per die: the three level values, |T - T_ref|, scaled error, gci_capped, branch, p_obs, d1 and d2; the
  stencil per level; argmax_xyz per level and the move count; a constant-k column (k at the layer-mean T of the
  finest k(T) solve); node_count_ratio per case; cg_max_per_level for every case and layout. Also the F3 null
  (manufactured, constant k), DOF, wall time, peak RSS, and the final true relative residual per linear solve.
- **Diagnostic only (not eligibility): die-centroid node.** For each die, this is the level-0 grid node on the die's
  top face nearest its area centroid: the level-0 x line nearest the centroid x, the y line nearest the centroid y,
  and z at the die top. Higher levels bisect, so this node persists at every level. Its three-level gci_capped, branch
  and p_obs are recorded. [F] The grid survey shows the centroid is itself a level-0 node for 10 of 16 dies. For 6
  dies of side_by_side_6 the node is 0.219 mm off in y, because of the asymmetric grading tie-break of T0231. This
  separates Tj-max argmax movement from non-convergence (T0207 alternative 3). If the centroid sequence converges
  while Tj_max does not, the cause is the moving maximum.

### 0.4 Local memory rule and `--full`

Each solve runs in its own child process, one at a time. Before a solve, the estimate is DOF x the bytes/DOF of
criterion 4 x 1.15. A solve runs if the estimate is <= 5 GB, or <= 10 GB when `memory_pressure` shows >= 50 % free
and the swap proxy is under 4 GB (re-checked every 3 min, for up to 12 min). Otherwise it is skipped and left for the
burst. A watchdog kills the child at 10 GB RSS or 8 GB swap. Locally this allows every L0, every L1, and the
manufactured L2. The other level-2 solves are burst-only.
`--full` runs every solve under 0.85 x physical memory and then `--report`. Burst command (`plan.json`):
`scripts/burst_gcp.sh --cmd "uv run python research/scripts/o007_dev_study2.py --full" research/o007_dev2`.

### 0.5 Reuse of T0225 solves

The probe's `a_q1h4_graded` N-layer solves (L0, L1, local; L2, burst) enter this study's cache only if two
conditions hold. (i) At that level, the production graded grid equals the probe's emulated grid line for line:
`np.array_equal` on the x, y and z lines and on the material map. (ii) A fresh L0 solve under the production rule
reproduces the cached L0 values within 1e-9 K on all 12 points (bitwise expected). If (i) fails, the script stops. If
(ii) fails, `feasible` cannot be true. No other cached solve is reused.

### 0.6 E009 cost table

The table covers every E009 scikit-fem solve:
- 6 cases x L0-L2, and the manufactured constant-k null at L2.
- Per layout: 3 calibration L0 solves, L1, L2 and a constant-k L2. This applies to the 2 dev layouts and to 3 fresh
  layouts counted at 1.5 x side_by_side_6.
- The FV L2 cross-check, levels 1-3: measured on the T0204 burst (`research/o007_l2/full.json`), with fresh layouts at
  1.5 x the larger dev layout [S].

Columns: DOF or cells, peak GB, wall per solve, CPU-hours (= wall), and a recommended timeout of
max(30 min, 3 x wall). DOF counts come exactly from the grid. A solve not measured is extrapolated, labelled [S]:
memory as in criterion 4; wall time as s/DOF of the largest measured solve of the same problem, and of the largest
measured solve overall, whichever is greater, x 1.3 per level beyond it.

### 0.7 What would show this rule unfit for E009

- Any CG count above 300.
- A level-2 A1 above 0.008, A2 above 0.040 K, A4 above 0.40 K on a case, or Tj_max GCI above 0.25 K on a dev die,
  including divergent sequences (GCI +inf).
- A gate failure.

Where measured locally, any of these rules the candidate out before the burst. The reported dev A1/A2/A4 values
become E009's K1/K2 regression guard (section 5 after the data).

---
*Everything below was written after the data.*

Pre-registration commit: `5570ba2` (`research/o007_dev2/preregistration.json`, copied to `dev_study.json` as
`preregistration_commit`). **No post-data change** was made to the script, the candidate, the criteria or the cost
rule. Every number below comes from the code committed with section 0.

## 1. Outcome

**`feasible: false`, the expected pre-burst state. Candidate 1 is unverified, not ruled out.** Level 2 is measured on
the N-layer case (reused from T0225) and on the manufactured case. It is missing on Cases 1a, 1b, 2 and 3 and on both dev
layouts (`levels_missing` in `frozen_config.json`); all of these exceed the 10 GB local cap. No criterion is missed by
measured data:
- [F] Every gate holds.
- [F] CG max is 259 against the limit of 300.
- [F] Where level 2 exists, it meets the margins. N-layer: A2 0.0386 K, A1 0.00048, A4 0.142 K. Manufactured: A2
  0.0050 K, A4 0.019 K.

[I] **Three things decide the burst, in order of risk:**
1. **CG headroom at L2 on the Muzychka plates.** [F] CG max at L0 → L1: Case 1a 204 → 252, Case 1b 198 → 247, Case 3
   119 → 189, Case 2 81 → 116. [S] At a constant growth ratio, L2 lands at about 311, 308 and 300 for 1a, 1b and 3,
   against the limit of 300. The N-layer ratio fell from 1.45 to 1.36 between levels, so the outcome is genuinely open.
2. **Tj_max convergence on the dev dies (A4 <= 0.25 K).** Under `gci_capped`, an oscillatory die costs
   3 x max(|d1|, |d2|). [F] 14 of 16 dies have d1 > 0.083 K, so any oscillation at L2 on those dies misses the margin.
   A monotone or fast sequence passes if |d2| <= 0.20 K.
3. **Case 1a accuracy (A2 <= 0.040 K).** [F] The s2 mean is 0.442 → 0.116 K off (order 1.93). [S] The Richardson L2
   value is 0.030 K.

The N-layer A2, the binding item in T0207, is measured at 0.0386 K. It passes with 3.5 % margin.

## 2. What was run (commands, exit codes)

1. Before section 0 (grid only): a scratch survey in `$TMPDIR` (DOF, cell ratios, die-centroid offsets) and
   `uv run python research/scripts/o007_dev_study2.py --plan`, exit 0, which wrote `plan.json`.
2. Section 0 committed as `5570ba2`.
3. `uv run python research/scripts/o007_dev_study2.py`, exit 0, 10:42-10:54 local time
   (`research/o007_dev2/run_local.log`). It ran 30 child-process solves one at a time, including the reuse check and
   the 5 calibration solves. Largest peak 7.91 GB (manufactured constant-k L2). `memory_pressure` showed 60-70 % free
   and the swap proxy 0 GB. Six L2 solves were skipped by the memory gate: estimates of 19-46 GB, over the 10 GB cap.
4. `--report` (exit 0, deterministic: the DoD re-run reproduces `frozen_config.json` byte for byte);
   `uv run ruff check research/scripts/o007_dev_study2.py` (exit 0); the DoD commands of the packet (exit 0).

## 3. Checks [F]

- **References and inputs.** Reference hashes `befc5efa...` and `ca05847b...` matched. Dev fingerprints `1f66b68a...`
  and `6aaf383a...` equal E006.yaml. Only seed 20261101 was used. No fresh layout was used and the holdout data
  directory was not read.
- **Reuse (sec. 0.5).** The production graded grid equals the T0225 emulated grid in x, y and z lines and in the
  material map at L0, L1 and L2. The production L0 re-solve reproduces the cached L0 **bitwise** on all 12 points
  (max |dT| = 0).
- **Gates.** Energy balance <= 3.2e-12 on every solve. Manufactured |Q_out / 64.648 W - 1| <= 2.1e-9. Picard residual
  <= 4.4e-5 K. Final true relative residual <= 3.8e-11. Node-count growth 7.25-7.76, inside 6.8-9.2. Every reported
  point is a node at the same coordinates at every level run, with stencils recorded. The largest snap is 0.1 mm (Case
  1a/1b/3 maximum lines; recorded).
- **CG counters.** The T0222 `meta["cg_iterations"]` equals the `cg_only` count on every solve of this study
  (mismatch 0). The reused probe records predate T0222 and carry only `cg_only`.
- **Operating point.** Calibration converged in 2 solves (side_by_side_6: 32.23 W per die, hottest rise 60.16 K) and
  3 solves (u_shaped_2: 47.14 W, 59.95 K). The calibration CG max is 122 and 128.
- **F3 null.** The manufactured case at constant k (L2, layer-mean T) is off by 2.51 K, scaled 0.0249. It fails A1
  and A2, so the k(T) case discriminates, as in T0207.
- **Grids.** The smallest cell is 50 um laterally (grading first offset / 2) and 50 um in z. The minimum neighbour
  ratio at L0 is 0.010-0.20 (sec. 0.1).

## 4. Results (`dev_study.json` → `chosen`) [F]

| problem | levels | DOF finest | CG max per level | max abs err per level, K | worst point | A1 (finest) | A4 (gci_capped) |
|---|---|---|---|---|---|---|---|
| case1a | 0, 1 | 1,025,661 | 204 / 252 | 0.442 / 0.116 | s2 mean | 0.0021 | n/a |
| case1b | 0, 1 | 1,221,025 | 198 / 247 | 0.052 / 0.013 | s2 mean | 0.0019 | n/a |
| case2 | 0, 1 | 750,141 | 81 / 116 | 0.063 / 0.017 | s2 mean | 0.0025 | n/a |
| case3 | 0, 1 | 750,141 | 119 / 189 | 0.030 / 0.0075 | south mean | 0.0015 | n/a |
| nlayer_dbc | 0, 1, 2 (T0225) | 13,606,565 | 132 / 191 / 259 | 0.591 / 0.152 / 0.0386 | d1 mean | 0.00048 | 0.142 (d1 mean, monotone, p 1.95) |
| mms | 0, 1, 2 | 1,577,913 | 53 / 75 / 93 | 0.079 / 0.020 / 0.0050 | die area mean | 0.00005 | 0.019 |

Every N-layer point converges monotonically from below, with p_obs 1.70-1.96. Every point lies below its reference (FE low) except 7 of 12 Case 2 points
(at most +0.0035 K). The per-case max error shrinks by a factor of 3.6-4.0 per level. [S] Richardson L2 values of the per-case max error (order
from L0/L1): 1a 0.030 K, 1b 0.0035 K, 2 0.0048 K, 3 0.0019 K.

**Dev layouts (L0, L1; k(T); calibrated power).**

| layout | DOF L1 | CG max L0 / L1 | Tj_max d1 = L1 - L0, K (range over dies) | argmax moved | centroid-node d1, K | k(T) - const-k at L1, K |
|---|---|---|---|---|---|---|
| side_by_side_6 | 1,237,087 | 122 / 185 | +0.058 to +0.304 | 8 of 12 | +0.048 to +0.142 | +0.41 to +0.98 |
| u_shaped_2 | 517,263 | 128 / 179 | +0.258 to +0.396 | 4 of 4 | +0.109 to +0.181 | +1.49 to +1.63 |

[F] Every die rises from L0 to L1. On every die whose argmax stayed put (4 of 12 on side_by_side_6), Tj_max d1 equals
the centroid-node d1, or the argmax sits off-centre by a fixed offset. Where the argmax moved, Tj_max d1 is 1.5-3.0
times the centroid-node d1. Example: u_shaped_2 die 2 gives 0.396 K against 0.144 K. The moves are lateral shifts of
0.36-0.47 mm in x or y. [I] This is the T0207 pattern: part of the level-to-level change
is the maximum moving to a new node. With only two levels, nothing is known yet about convergence order. The
centroid-node GCI at L2 will separate the two effects, as pre-registered.

## 5. Regression guard for E009's spec (K1 > 0.05 scaled, K2 > 0.25 K) [F]

These are dev values of candidate 1 at the finest level run:
- **A1:** max scaled error 0.0025 (Case 2, L1). At L2: N-layer 0.00048, manufactured 0.00005.
- **A2:** max |T - T_ref| 0.116 K (Case 1a s2 mean, **L1**). At L2: N-layer 0.0386 K, manufactured 0.0050 K.
- **A4:** cases 0.142 K (N-layer, L2) and 0.019 K (manufactured). Layouts n/a (2 levels).

[I] No level-1 or level-2 value comes near K1 (factor 20) or K2. Case 1a at L1 sits at 46 % of K2. E009 reads level 2.
At **L0**, the N-layer (0.59 K) and Case 1a (0.44 K) would trip K2, so a run that reports a coarse level by mistake
would trip the kill criteria. These values update after the burst; E009's spec should quote the L2 values.

## 6. E009 cost table (`dev_study.json` → `chosen.e009_plan.rows`; method sec. 0.6)

The table has 54 rows, each with DOF or cells, peak GB, wall per solve, CPU-hours and a recommended timeout.

| part | finest peak | CPU-hours | basis |
|---|---|---|---|
| scikit-fem, 6 cases L0-L2 + manufactured null | 47.7 GB (Case 1b L2) [S] | 2.8 h | measured L0/L1 (macOS), N-layer L2 (Linux); rest [S] |
| scikit-fem, 2 dev layouts (3 cal L0, L1, L2, const-k L2) | 47.5 GB (side_by_side_6 L2) [S] | 1.7 h | [S] at L2 |
| scikit-fem, 3 fresh layouts at 1.5 x side_by_side_6 | **71.3 GB** (14.2 M DOF) [S] | 5.6 h | [S] |
| FV L2, dev layouts L1-L3 | 69.9 GB (side_by_side_6 L3) | 0.98 h | measured, T0204 burst (`o007_l2/full.json`) |
| FV L2, 3 fresh layouts L1-L3 | **104.8 GB** [S] | 2.6 h | 1.5 x side_by_side_6 [S] |
| **total** | max 104.8 GB <= 217.6 GB | **13.6 h** [S] | recommended overall timeout 41 h (3 x) |

[F] The extrapolated scikit-fem peaks use 5.01 kB/DOF. That is the largest measured Q1 rate at >= 1 M DOF, from the
manufactured constant-k L2 on macOS, so it is conservative. The Linux N-layer L2 measured 3.08 kB/DOF, which would put
the fresh-layout L2 near 44 GB. [S] Wall times use the largest measured s/DOF, from the N-layer L2 on the VM:
216 us/DOF. That rate includes Picard steps, so the 10.0 scikit-fem CPU-hours are an upper estimate. The FV level-3
solves set the E009 VM size: at 104.8 GB [S], an n2-highmem-16 (128 GB, 108.8 GB usable) has no margin, so plan
**n2-highmem-32** (256 GB).

## 7. The founder's burst (completes this study; it resumes from the committed cache)

`scripts/burst_gcp.sh --cmd "uv run python research/scripts/o007_dev_study2.py --full" research/o007_dev2`

- The bundle defaults to `main`. Run it after this branch is merged, or with `MF_REF=<this task branch>`.
- **Solves (8):** L2 of Cases 1a, 1b, 2 and 3, L2 of both dev layouts, and their constant-k L2 columns. The N-layer
  L2 is reused, not re-run.
- [S] Largest peak about 55 GB by the local estimate rule (Case 1b L2), or about 30 GB at the Linux rate. The default
  n2-highmem-32 works. The cheaper `e2-custom-10-81920` that T0225 used (80 GB) also fits; append it as the
  machine-type argument.
- [S] Wall time about 3.4 h at the conservative rate; allow 10 h.
- The mode ends with `--report`, which rewrites `dev_study.json` and `frozen_config.json` under the pre-registered
  rule. `feasible` becomes true only if every criterion holds at L2 everywhere.

**What would change the conclusion after the burst** (pre-registered in sec. 0.7):
- CG above 300 at L2 on any plate or layout, the risk named in section 1: candidate 1 is ruled out, and the founder
  decides between the T0218 headroom rule and a sliver-free line policy (T0225 part 1).
- An oscillatory or divergent Tj_max on a dev die: A4 is missed. The centroid-node branch then shows whether the
  cause is the moving argmax (centroid monotone) or non-convergence (centroid also non-monotone).
- Case 1a above 0.040 K at L2.

## 8. Facts, inferences, speculation; recommendations (no production change made)

- [F] Under the production graded rule, everything measured locally passes. The N-layer A2 is 0.0386 K at L2 (T0225,
  reproduced bitwise at L0). No gate failed and CG max is 259.
- [I] The open risk has moved from accuracy, the T0207 failure, to CG headroom at L2 on the 300 mm Muzychka plates.
  Those plates carry the maximum-line slivers (min ratio 0.010-0.031), the T0225 part-1 signature.
- [S] Constant-ratio CG extrapolation puts Cases 1a, 1b and 3 at 300-311 at L2.
- Recommendation 1 (planning): run the burst above before E009 is designed. Size E009's VM at 256 GB (FV level 3).
- Recommendation 2 (planning, only if the burst reads CG > 300 on the plates): the cheapest discriminating follow-up
  is T0225 part 1's centroid-only variant at L2 on Case 1a under this rule. If centroid-only stays <= 300, a
  line or snap policy fixes the headroom without a solver change. That is a builder task with review; it is not
  decided here.
