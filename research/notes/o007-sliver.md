# O007 sliver discriminator (T0235): slivers or conditioning behind T0228's CG-only miss

Author: scientist, T0235 attempt 1, 2026-11-04. Founder I0124 (c), step 1. Script: `research/scripts/o007_sliver.py`.
Outputs: `research/o007_sliver/{survey.json, plan.json, preregistration.json, discriminator.json, cache/}`.
Labels: **[F]** fact (file or listed command), **[I]** inference, **[S]** speculation or extrapolation.

**This is a LABELLED DIAGNOSTIC.** It is not a candidate configuration. No temperature of any variant is compared with a
reference, and none enters any criterion, freeze or spec. There is no production code change
(`thermal_fem.py` is used unchanged; the survey's line-removal check wraps `_grading_lines` at run time in its own
process only).

## 0. Pre-registration (written and committed before any solve of this task)

**What was run before this section.** Grid construction only, with no temperature: `o007_sliver.py --survey` (L0 survey,
`survey.json`) and `--plan` (DOF and ratios per level, `plan.json`). Prior data, disclosed: T0228 measured candidate 1
(`max_lines` here) at L0/L1/L2 with CG max 204/252/316 (Case 1a) and 198/247/318 (Case 1b), and Case 2 at 81/116/162.
No variant of this task has been solved.

### 0.1 Survey (L0, candidate 1 exactly, production GridRule with edge_grading) [F] `survey.json`

These are intervals whose width is below 0.1 times a neighbour's width (x and y are identical by symmetry; x shown):

| case / variant | interval [mm] | width | neighbours | ratio | bounded by |
|---|---|---|---|---|---|
| 1a max_lines | [90.000, 90.029], [90.029, 90.057] | 28.6 um | 2148 / 28.6, 28.6 / 2134 um | **0.0133** | source centroid s1 / subdivision / frozen-max line s1 (57.2 um from the centroid, split into min_cells = 2) |
| 1a max_lines | [210.000, 210.104], [210.104, 210.208] | 103.9 um | 2148, 2097 um | 0.048 | source centroid s2 / frozen-max line s2 (207.7 um) |
| 1b max_lines | [90.000, 90.067], [90.067, 90.135] | 67.4 um | 2148, 2115 um | **0.0314** | source centroid s1 / frozen-max line s1 (134.8 um) |
| 1a, 1b both variants | [73.594, 74.766], [225.234, 226.406] | 1171.9 um | 12266 um | 0.0955 | outermost grading line (offset 3.906 mm outside the source edge) / subdivision; far-field cell |
| 1a, 1b both variants | [105.234, 106.406], [193.594, 194.766] | 1171.9 um | 14531 um | **0.0806** | the same between the two sources (87.2 mm gap, 6 cells) |
| 2 max_lines | [12.500, 12.518], [12.518, 12.536] | 17.8 um | 1719, 522 um | **0.0104** | centroids s1, s3 / frozen-max line s3 (35.7 um) |
| 2 max_lines | [37.500, 37.528] | 28.3 um | 1719 um | 0.0165 | centroids s2, s4 / subdivision |
| 2 max_lines (y) | [12.312, 12.406], [37.614, 37.729] | 94-114 um | ~1.6 mm | 0.058, 0.071 | frozen-max lines s2, s3 |

Explanation of the T0228 numbers:
- [F] **1a** min cell 28.6 um, ratio 0.013: this is the s1 centroid line plus the s1 frozen-maximum line 57.2 um away.
- [F] **1b** ratio 0.031: this is a maximum line too (s1, 134.8 um from the centroid). It is not the grading. The 1b
  **minimum cell** of 50 um *is* the grading: the 100 um first offset inside the source edge, split in two. Its
  neighbour ratio is 0.67, so it is not a sliver. The outer first offset (77.4 mm) snaps onto the source edge
  (`snaps`, 4 per axis, SNAP_FRACTION x 12.3 mm far-field cell = 123 um > 100 um).
- [F] **Case 2** has ratio 0.010 from a centroid/maximum pair, as in 1a, but CG max is only 81/116/162.
  [I] The same kind of sliver is therefore compatible with low CG counts, which is evidence against slivers being
  sufficient for high CG. It is not decisive: Case 2 is a different plate (50 mm, h = 400, k = 150; 1a is 300 mm,
  h = 10, k = 10).
- [F] **centroid_only** (frozen-maximum extra lines removed) leaves minimum ratio **0.0806** on both 1a and 1b. It
  comes from the junction between the outermost grading interval (2.34 mm, split into two 1.17 mm cells) and the
  12.3 / 14.5 mm far-field cells. That is a coarsening jump, not a pair of near-coincident lines. Case 2's
  centroid_only ratio is 0.273.
- [F] **Named-line removal check** (`survey.json` `named_line_removal_check`): removing the survey-named grading lines
  of centroid_only (73.594, 106.406, 193.594, 226.406 mm in x and y) *lowers* the minimum ratio to **0.0306** on both
  cases. The far-field interval absorbs the 3.9 mm offset band, and the next graded step (0.94 mm split in two) now
  faces it. No removal or merge of survey-named lines brings these grids to >= 0.1. Reaching 0.1 would need an added
  line or a changed far-field cell size, which goes beyond "removes or merges the survey-named lines".

### 0.2 Variants (fixed)

- **max_lines**: candidate 1 as frozen (`research/o007_dev2/frozen_config.json`). Values are copied from
  `research/o007_dev2/dev_study.json` and `plan.json`, not re-solved.
- **centroid_only**: candidate 1 with the frozen-maximum `extra_lines` removed (`box_problem(...)["extra"] = None`),
  built-in source centroid lines kept, everything else identical: Q1, h0 4 mm, near_margin 2 mm, dz_max 1 mm, nz_min 1,
  min_cells 2, zrefine, edge_grading (1e-4, 2.5, 4e-3, 0.5), SNAP_FRACTION 1e-2, linear_rtol 1e-11, CG cap 400, AMG
  seed, Picard tolerance 1e-4 K, levels 0, 1, 2. The grading lines are recomputed by the production rule; their
  fixed set no longer contains the maximum lines. DOF at L0/L1/L2: 1a 125,939 / 952,749 / 7,405,625;
  1b 148,837 / 1,134,225 / 8,850,625.
- **sliver_free: not registered.** It is allowed because centroid_only leaves 0.0806 < 0.1. But the check in 0.1
  shows that no geometry-only removal or merge of the survey-named lines reaches 0.1. It also shows that the
  residual low-ratio cells are not next to near-coincident lines.

### 0.3 Decisive variant

**case1a: centroid_only. case1b: centroid_only.** Rationale [I]: centroid_only removes exactly the near-coincident
centroid/maximum line pairs that set T0228's minimum ratios (0.013, 0.031). It is also the best that the proposed
repair (a sliver-free snap/max-line builder, I0124 (c) step 2) could achieve on these plates. So the decisive question
is whether that repair could bring CG to <= 300.

### 0.4 Verdict rule (as in the packet, applied by `--report`)

- `slivers` iff, on both case1a and case1b, the decisive variant's CG maximum over every Picard step is <= 300 at
  every level measured, with L2 measured (levels_run = [0, 1, 2]).
- `conditioning` iff any decisive-variant count exceeds 300 at any level, the 400 cap included. A solve that fails
  at the cap counts as measured, with its logged count (>= 400).
- `unmeasured` otherwise, i.e. while a decisive L2 is missing and no count exceeds 300.

CG is counted by T0207's `cg_only` callback (one call per pyamg CG iteration, outer accelerated solve only).
`meta["cg_iterations"]` (T0222) is recorded alongside it, with the equality check.

**Scope of the labels [I].** `conditioning` here means that the CG excess survives removal of the near-coincident
maximum lines. It does not separate three remaining causes:
- physical conditioning of the plate (weak Robin coupling h = 10 W/(m2 K) on a 300 mm plate);
- the 0.08 grading-to-far-field jump;
- the 12-14.5 mm by 1 mm far-field cell aspect ratio, which is the same at every level under zrefine.

`slivers` means that removing the maximum lines suffices on both plates.

### 0.5 Records per case and variant

levels_run, cg_max_per_level, DOF, min_ratio_lateral_l0 (min of the x and y ratios at L0, float), min ratios per level
(x and y for solved levels; lateral for every level from the grid), final and maximum true relative residual
||b - Ax|| / ||b||, wall time (solver and process), peak RSS, energy balance, Picard residual, and the
cg_only == meta check. Sanity gates (they separate a broken run from a hypothesis result): energy balance <= 1e-6 and
Picard residual < 1e-4 K on every ok solve; the true residual <= 10 x linear_rtol unless the solve failed;
cg_only == meta["cg_iterations"]; and the L0 grid of the solve equals the survey grid.

### 0.6 Runs and memory

L0 and L1 run locally under T0228's memory rule (`DS.Runner.gate`: estimate = DOF x `D2.bpd_max` x 1.15; run if
<= 5 GB, or <= 10 GB with memory_pressure >= 50 % free and swap < 4 GB, re-checked every 3 min for up to 12 min;
watchdog at 10 GB RSS or 8 GB swap). One child process runs at a time, level-major. L2 is burst-only:
`scripts/burst_gcp.sh --cmd "uv run python research/scripts/o007_sliver.py --full" research/o007_sliver`.
[S] L2 estimates (`plan.json`), from DOF x the measured T0228 L2 bytes/DOF and s/DOF of the same plate under max_lines
on e2-highmem-8: 1a about 22.9 GB and 28 min, 1b about 26.9 GB and 35 min. Wall time also scales with the CG count.
The expected state before the founder's burst is `unmeasured`.

### 0.7 What would make this diagnostic wrong or uninformative

- A gate failure, or cg_only != meta: the run is broken, not the hypothesis.
- L0/L1 counts of centroid_only exactly equal to max_lines: the variant had no effect on the grid where it matters.
  The survey already rules this out for the ratio, so this would point at the counter.
- Any centroid_only count > 300: `conditioning`. Then a snap/max-line builder cannot meet the 300 rule on these
  plates, and I0124 (c) step 2 should not be funded as specified.

---
*Everything below was written after the data.*

Pre-registration commit: `79502c0` (`research/o007_sliver/preregistration.json`, copied to `discriminator.json` as
`preregistration_commit`). **Post-data changes:** one only. `plan()` gained the field `full_gate_min_physical_GB`. It
is informational: it touches plan.json only and changes no solve, record or verdict. The variants, decisive variants,
verdict rule, gates and solver settings are as committed in section 0.

## 1. Result (local L0 and L1; L2 burst-only)

**Verdict: `unmeasured`**, the expected state before the burst. Every sanity gate of 0.5 holds (`discriminator.json`
`sanity`, `sanity_failed: []`). cg_only equals `meta["cg_iterations"]` on every solve. Energy balance is <= 1e-6 and
the Picard residual < 1e-4 K. The true relative residual is <= 3.5e-11 (<= 10 x rtol), and the L0 grid equals the
survey grid.

| case | variant | min ratio L0 | DOF L0 / L1 | CG max L0 / L1 / L2 | final true rel. residual L0 / L1 | wall L0 / L1 [s] |
|---|---|---|---|---|---|---|
| 1a | max_lines (T0228, copied) | 0.0133 | 135,531 / 1,025,661 | 204 / 252 / **316** | 1.1e-11 / 1.2e-11 | 5.0 / 43.5 |
| 1a | centroid_only | 0.0806 | 125,939 / 952,749 | **177 / 235** / - | 1.0e-11 / 1.1e-11 | 4.3 / 39.3 |
| 1b | max_lines (T0228, copied) | 0.0314 | 160,173 / 1,221,025 | 198 / 247 / **318** | 1.6e-11 / 3.8e-11 | 5.8 / 51.2 |
| 1b | centroid_only | 0.0806 | 148,837 / 1,134,225 | **188 / 240** / - | 1.5e-11 / 3.5e-11 | 5.3 / 47.4 |

[F] Local peak RSS was 0.85 / 2.70 GB (1a) and 0.97 / 3.20 GB (1b). Each L1 solve waited 3-9 min for
memory_pressure >= 50 % free, because the estimate (5.5 and 6.5 GB) was above the 5 GB soft limit.

## 2. Diagnosis (mf-diagnosis protocol; the pre-registered verdict is still open)

**Signal [F].** T0228 L2 CG 316 (1a) and 318 (1b) > 300. Every accuracy margin was met, and no solve hit the 400 cap.

**Explanations considered.**
1. *Slivers.* The near-coincident centroid/maximum line pairs (ratio 0.013, 0.031) degrade AMG-CG.
   Discriminating test: centroid_only (this task). It predicts a large drop that persists or grows with level.
2. *Conditioning of the plates*, broadly: the count is set by the operator, not by the maximum-line slivers. This
   covers weak Robin coupling (h = 10 W/(m2 K), k = 10 W/(m K), 300 x 300 x 10 mm), the 12-14.5 mm x 1 mm far-field
   cells, and the 0.08 grading-to-far-field jump. Discriminating test: the same centroid_only. It predicts a small
   drop that shrinks with level, while the counts keep growing by about 1.25-1.3 per level.
3. *Not separated here* (named in sec. 0.4): which of the parts of 2 dominates. A test needs a variant that changes
   the far-field cell size or the grading's outer end. That is outside this task's two-variant limit, so it was not
   run.

**Tests run [F].** centroid_only at L0 and L1 on both plates (four solves, about 2 min of compute). The drop relative
to max_lines:
- 1a: 27 (13 %) at L0, 17 (7 %) at L1;
- 1b: 10 (5 %) at L0, 7 (3 %) at L1.

Growth per level under centroid_only is 1.33 (1a) and 1.28 (1b). Under max_lines it was 1.24 / 1.25 (L0→L1) and
1.25 / 1.29 (L1→L2).

**Inference [I].** The sliver contribution is real but small, and it shrinks with refinement. Most of the count, and
all of its growth, survives removal of the maximum lines. Case 2 points the same way: its ratio-0.010 sliver came with
CG 81/116/162. This favours explanation 2 for the *size* of the count. It does not settle the pre-registered
question, because the L2 margin is narrow.

**Projection [S]** (not evidence; the verdict waits for the burst). centroid_only L2:
- 1a: about 312 at its own L0→L1 growth, or about 295 at max_lines' L1→L2 growth (316/252);
- 1b: about 306 or about 309.

Both plates sit within about +/-15 of the 300 limit, and 1b projects above it either way.

**Classification (provisional).** `model` class (the grid/solver configuration does not give the required CG
headroom on these plates; the code is not wrong), confidence **0.6**. `implementation` (a fixable sliver builder)
has 0.3; the remainder is that the burst shows both plates <= 300. This does not change the verdict rule. Only the
burst decides.

**What would prove this wrong.** `slivers` at L2 (both centroid_only counts <= 300) would show that maximum-line
removal is sufficient, whatever the small L0/L1 effect suggests. A count > 300 settles `conditioning` for the question
asked.

## 3. Recommended actions

1. Founder burst (L2 only; L0/L1 are cached and reused):
   `scripts/burst_gcp.sh --cmd "uv run python research/scripts/o007_sliver.py --full" research/o007_sliver`.
   [S] About 23 GB and 28 min (1a), about 27 GB and 35 min (1b), measured peak scaled by DOF. `--full`'s gate needs
   >= 60 GB physical memory (`plan.json` `full_gate_min_physical_GB`, from the conservative local bytes/DOF), so
   e2-highmem-8 (64 GB, as in T0228) suffices. Then commit `--report`.
2. If `conditioning`: do not fund the sliver-free snap/max-line builder (I0124 (c) step 2) as the repair. Even a
   perfect builder leaves these grids at centroid_only. The live options are a founder decision. They are outside
   this task's scope and are not recommended here: a rule change that addresses explanation 3 (far-field cell
   size or grading end, as a new pre-registered candidate) or a solver change. Neither changes the 300 rule.
3. If `slivers`: proceed with I0124 (c) step 2. The builder's acceptance should be centroid_only-level ratios
   (>= 0.08) with the maximum points still nodes.

## 4. Corrections before the L2 burst (founder session, 2026-11-05, review T0240) [post-data, labelled]
- [F] **Sec. 0.1 is wrong** where it says "No removal or merge of survey-named lines brings these grids to >= 0.1.
  Reaching 0.1 would need an added line". `named_removal_check` removed only lines labelled `grading_line` and tested
  no merge. Merging the two 1.17 mm cells of the outermost graded interval (2.34375 mm, split in two by
  `min_cells = 2`; subdivision lines at 74.766, 105.234, 194.766 and 225.234 mm) raises the minimum lateral ratio
  from 0.0806 to **0.161** on both plates (T0240).
- [F] **Founder-session diagnostic of that merge** (not pre-registered; it enters no verdict, criterion or spec):
  `research/scripts/o007_sliver_merged.py`, output `research/o007_sliver/founder_merged_variant.json`, local, L0 and
  L1. The centroid_only rows reproduce this task's counts exactly (177/235, 188/240), which checks the harness.

  | case | variant | min ratio L0 | CG max L0 / L1 |
  |---|---|---|---|
  | 1a | centroid_only | 0.0806 | 177 / 235 |
  | 1a | centroid_only + outer graded interval as one cell | 0.1613 | 174 / 231 |
  | 1b | centroid_only | 0.0806 | 188 / 240 |
  | 1b | centroid_only + outer graded interval as one cell | 0.1613 | 184 / 238 |

  [I] Raising the worst ratio from 0.081 to 0.161 cuts CG by 1-2 %, against 3-7 % for removing the maximum lines.
  Neither the slivers nor the 0.08 grading-to-far-field jump sets the count. This supports explanation 2's operator
  part (weak Robin coupling on the 300 mm plates) over its cell-size parts. Recommendation 2 is amended: a
  `conditioning` verdict does not by itself rule out a line policy that also fixes the outermost graded cell, but
  this diagnostic shows that such a policy changes the count by about 2 %, so it would not reach 300 either.
- [F] **Verdict code fix (before any L2 data):** `worker()` recorded any `RuntimeError`, a Picard failure included,
  as `cg_failed`, a measured level. Now only a failure whose CG log shows the 400 cap is `cg_failed`. Any other
  failure is `failed`, which `_variant` treats as a missing level, so it can no longer produce `slivers`.
- [F] The module docstring no longer points at a non-existent `SLIVER_FREE` constant.

## 5. After the burst: the verdict and a preconditioner diagnostic (founder session, 2026-11-05)
- [F] **Burst** (`e2-highmem-8`, 44 min, commit ab86689): **verdict `conditioning`**. centroid_only CG max at L0/L1/L2
  is 177/235/**305** (Case 1a) and 188/240/**314** (Case 1b), against max_lines 316 and 318. Removing the
  maximum lines takes 3.5 % and 1.3 % off at L2. Case 1a passes every sanity gate. Case 1b's L2 true relative
  residual, 1.05e-10, misses the 10 x rtol gate (1.0e-10) by 5 %, so 1b's L2 is a "broken run" under sec. 0.5. The
  verdict stands on Case 1a alone (305 > 300).
- [F] **Preconditioner diagnostic** (not pre-registered, not evidence; `research/scripts/o007_amg_sweeps.py`, output
  `research/o007_sliver/founder_amg_diagnostic.json`): candidate 1 exactly as frozen (max_lines), L0/L1, with the Q1
  AMG built three ways by `thermal_fem._sa_solver` (same seed). The default rows reproduce T0228's counts exactly.

  | AMG (order 1) | Case 1a CG L0 / L1 | Case 1b CG L0 / L1 | max dT vs default | solve wall vs default |
  |---|---|---|---|---|
  | pyamg default: 1 symmetric GS sweep, theta 0 (production) | 204 / 252 | 198 / 247 | - | - |
  | thermal_fv's: theta 0.05, filtered Jacobi, fwd/bwd GS | 238 / 295 | 234 / 297 | 7e-11 K | about equal |
  | **2 symmetric GS sweeps per level** | **145 / 180** | **141 / 177** | **5e-11 K** | **+7-10 %** |

  [I] The excess is the order-1 AMG's smoothing on these weakly cooled plates, not the grid. Two sweeps cut CG by
  28-29 % at equal temperatures (5e-11 K) for about 10 % more wall time. [S] At the observed L1-to-L2 growth
  (1.25-1.29), L2 would be about 225-232, inside the pre-registered 300 with margin, the rule unchanged. A solver
  setting is part of the frozen configuration, so this needs a pre-registered re-freeze of candidate 1 with the new
  smoother, re-measured at every level. Nothing here changes a verdict or a criterion.
