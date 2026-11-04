# O007 development study (T0207): scikit-fem configuration for E009, and the E009 memory and cost plan

Author: scientist, T0207 attempt 1, 2026-11-03. Script: `research/scripts/o007_dev_study.py`. Outputs:
`research/o007_dev/{dev_study.json, frozen_config.json, plan.json, cache/}`.
Labels: **[F]** fact (read from a file or produced by a listed command), **[I]** inference, **[S]** speculation.

## 0. Pre-registration (written before any solve of this study)

Before writing this section I ran only grid-construction code: level-0 grid shapes and DOF counts from
`thermal_fem.box_stack_grid` / `layout_grid` with `_count_nodes(_q2)`. These are costs, not solution values. No
temperature of any case or layout had been computed in this task when this section was written.

**[F] Cost facts behind the candidate list (level-0 DOF; level 2 has about 64 times as many, since r = 2 in x, y and z).**
Q2 grids of the two dev layouts are limited by their geometry lines, not by h0. Every geometry interval gets at least
two cells, so Q2 at level 2 has about 2.5 to 4.5 M DOF for any h0 from 2 to 8 mm. Q1 on the same lines has about
0.6 to 1.5 M DOF. The 300 mm Muzychka plates (Cases 1a and 1b) are the costly reference cases. Q2 with
h0 = 2 mm and dz_max = 2 mm gives 13 to 16 M DOF at level 2. Q2 with h0 = 4 mm and dz_max = 5 mm gives 1.9 to 2.7 M.

### 0.1 Candidates (four; near_margin 2 mm, nz_min 1 cell per layer, min_cells 2, the production defaults otherwise)

| id | element order | h0 | near_margin | dz_max | rationale |
|---|---|---|---|---|---|
| `q1_h4` | 1 (Q1, 2x2x2 Gauss) | 4 mm | 2 mm | 1.0 mm | cheapest; every level-2 grid is about 1.3 M DOF or less |
| `q1_h2` | 1 | 2 mm | 2 mm | 0.5 mm | Q1 refined laterally by 2 and in z by 2 |
| `q2_h4` | 2 (Q2, 3x3x3 Gauss) | 4 mm | 2 mm | 5.0 mm | cheapest Q2 |
| `q2_h4z2` | 2 | 4 mm | 2 mm | 2.0 mm | Q2 with z refined (10 mm plates: 5 instead of 2 level-0 cells) |

The mandatory-line policy is the same for all four. Box-stack mode uses the lines through every source centroid
(built in) and through the frozen series maximum of every source (`extra_lines`). Layout mode (manufactured case)
uses the x and y lines through every frozen point and maximum (`extra_lines`). Snapping follows the production
`SNAP_FRACTION` (1e-2 of the level-0 cell). Every snap is recorded. The other fixed settings are `linear_rtol`
1e-11 and the CG cap of 400 (production, unchanged), Picard tolerance 1e-4 K, and levels [0, 1, 2].

### 0.2 Selection criterion

A candidate is **eligible** only if, on every reference case and both dev layouts, every check below holds at
levels 0-2:

1. **Gates.** Energy balance at most 1e-6 (manufactured case: also |Q_out / 64.648 W - 1| <= 1e-6). Picard residual
   below 1e-4 K. Node-count growth 8 +/- 15 % from each level to the next. Every reported point is a node on every
   level (the `node_value` lookup succeeds; stencils are recorded). No linear-solve failure.
2. **CG headroom** (founder note, T0218). No level-0 to level-2 solve, at any Picard step, needs more than 300 CG
   iterations.
3. **Accuracy at level 2, with margin.** The A1 analogue (max scaled error) is at most **0.008** (80 % of 0.01). The
   A2 analogue (max |T - T_ref|) is at most **0.040 K** (80 % of 0.05). A4 (max GCI from `mfos.metrics.gci_capped`,
   floor 1e-3 K) is at most **0.40 K** on the reference cases and at most **0.25 K** on the dies of the dev layouts.
   The dev layouts get 50 % of the threshold because E009's three fresh layouts are unseen. The reference cases
   are deterministic, so E009 repeats their values up to platform round-off, and 80 % is enough margin there.
4. **Memory.** Every E009 finest solve fits the burst VM: n2-highmem-32, 256 GB, 0.85 x 256 = 217 GB per solve,
   solves run one after another. The estimate is DOF x measured peak bytes/DOF. Fresh layouts are allowed 1.5 x the
   larger dev layout's DOF count.

**Choice.** Among eligible candidates, take the smallest estimated E009 finest-level peak memory (max over E009's
solves). A candidate counts as eligible only when criterion 3 is **measured** at level 2. A level 2 that the local
memory rule does not allow leaves the candidate *unverified*, not eligible. If no candidate is verified eligible, the
outcome is `feasible: false`. `chosen` then holds the cheapest candidate that the data did not rule out, labelled
provisional, plus the `--full` burst command that would complete it.

**Local memory rule (this run).** The packet allows up to 0.85 x physical memory. The agent rules are stricter: at
most 5 GB per process, or up to 10 GB when `memory_pressure` shows at least 50 % free and swap is under 4 GB. The
stricter rule applies. The sandbox denies `sysctl vm.swapusage`, so swap use is read as the total size of
`/private/var/vm/swapfile*` (a proxy). Each solve runs in its own child process. A watchdog kills it at 10 GB RSS or
8 GB swap. Peak memory before a solve is estimated from DOF x the largest measured bytes/DOF of the same element
order x 1.15 (the module's bound of 7.7 / 10 kB per DOF until a measurement exists).

**Also recorded, but not part of eligibility.** The F3 null: the manufactured case at constant k, evaluated at the
layer-mean temperature, must fail A1 and A2. If it does not, that is a design problem of E009, not of a candidate.
Also: per-die Tj-max node coordinates per level and how often they move, divergent and oscillatory sequences, a
constant-k column on the layouts, DOFs, wall time, peak RSS, CG iterations and final residuals per solve.

## 1. Outcome in one paragraph

**No candidate is feasible (`feasible: false`).** Every candidate is ruled out by measured data, before any
extrapolation:

- **[F] Q1 fails on accuracy.** `q1_h4` at level 2 misses A2 by a factor of 28: max |T - T_ref| = 1.389 K, at the
  N-layer d3 source mean. Its A4 on the cases is 3.67 K. Both dev layouts have divergent Tj-max sequences (GCI +inf).
  `q1_h2` misses A2 at level 2 on the N-layer case: 0.680 K.
- **[F] Q2 fails on CG headroom.** It is far more accurate where it ran: Case 1a at level 2 has |err| = 0.0115 K and
  GCI 0.042 K. But both Q2 candidates exceed 300 CG iterations at level 1 on Case 1a (359 and 352). At level 2 they
  reach the cap of 400 on Cases 1a and 2. That makes them ineligible under the founder's T0218 rule. At level 1 the
  N-layer source mean is still 0.48 K off.
- **[I] The binding physics is the N-layer DBC case.** The die-sized flux patches sit on a 0.18 mm die over a
  0.05 mm attach, 0.3 mm Cu and 0.38 mm ceramic. The source-edge singularity in those thin layers needs lateral cells
  well below the layer thicknesses. Any grid that resolves it, refined by r = 2 in x, y and z over three levels, puts
  the 300 mm Muzychka plates at tens of millions of DOF.

`chosen` in the JSON files is `q1_h4`. It is shown **for the record only, as the cheapest candidate with complete
three-level data, and is not a recommendation.** The pre-registration did not specify what to list when every
candidate is ruled out, so this display choice was made after seeing the data.

## 2. What was run (commands, exit codes)

1. Grid-only cost survey (scratch, `$TMPDIR`), then the pre-registration, committed as `df40ac9`, before any solve.
2. `uv run python research/scripts/o007_dev_study.py --plan`: exit 0 (`plan.json`, DOF counts, no solve).
3. `uv run python research/scripts/o007_dev_study.py`: first launch exit 1. The cache scan read the calibration file
   as a solve, which was a bookkeeping bug with no effect on any solve. After the fix, exit 0 (log
   `research/o007_dev/run_local.log`). 17:5x to 18:4x local time, one solve at a time, each in its own child
   process. Largest peak 5.64 GB; `memory_pressure` showed 73-77 % free, swap proxy 0 GB.
4. `uv run python research/scripts/o007_dev_study.py --report`: exit 0. `uv run ruff check …`: exit 0.

**[F] Instrumentation correction (found during the run, before any accuracy result was read).** At first the CG
count was taken from pyamg's `residuals` list. That list came back with 2-3 entries for real solves, so it was
dropped. A per-iteration `callback` replaced it. That count was then 2n + 1: the AMG preconditioner's matvec calls
`ml.solve(maxiter=1)` on the same object, so its calls were counted too. The logger now counts only the outer
`accel="cg"` call and tags each entry `counter: "cg_only"`. Untagged entries from solves already done are converted by
(n - 1) / 2. Discriminating check: the `q1_h4/case2/L1` solve was re-run with the fixed logger. The conversion
predicted 154 iterations and the re-run counted 154. The final residual was bit-identical (1.1093e-11), so the
instrumentation does not change the solve. The production `_Solver` and its limits are untouched.

## 3. Checks that hold for every candidate [F]

- References: series sha256 `befc5efa…` and manufactured `ca05847b…` (canonical payloads) equal the frozen values.
  The dev layouts' fingerprints equal `experiments/specs/E006.yaml` (`1f66b68a…`, `6aaf383a…`). Only dev seed
  20261101 was used. No fresh layout and no `data/holdout` were used.
- Energy balance is at most 2.4e-11 on every solve. Manufactured Q_out matches 64.648 W to within 1e-6 (gated).
  Picard residual is below 1e-4 K.
- Node-count growth from level to level is 7.04 to 7.77, inside 8 +/- 15 % (6.8 to 9.2). Every reported point is a
  node at the same snapped coordinate on every level run. Stencils are recorded per level in `dev_study.json`.
- **F3 null.** The manufactured case at constant k (each layer at its own layer-mean temperature, finest level run)
  is off by 2.51 K, scaled 0.025. It fails A1 and A2 for all four candidates, so the k(T) case discriminates.
- Operating point: the hottest die rises 59.95-60.16 K at level 0. Equal power per die is 31.8-32.2 W
  (side_by_side_6) and 46.8-47.3 W (u_shaped_2). The constant-k column (k at layer-mean T) runs 0.5 to 1.65 K cooler
  than k(T).

## 4. Results per candidate (level-2 values where run; [F] from `dev_study.json`)

| | q1_h4 | q1_h2 | q2_h4 | q2_h4z2 |
|---|---|---|---|---|
| levels run (cases / layouts) | 0-2 everywhere | 0-2 except 1a, 1b, 3 (L2 > 10 GB) | 0-2 on 1a, 2, 3; else 0-1 | 0-2 on 2, 3; else 0-1 |
| A1 max scaled err (margin 0.008) | **0.0171** (N-layer, L2) | 0.0084 (N-layer, L2) | 0.0060 (N-layer, **L1**) | 0.0059 (N-layer, L1) |
| A2 max abs err, K (margin 0.040) | **1.389** (N-layer d3 mean) | **0.680** (N-layer d2 mean) | 0.482 (N-layer, L1); 1a 0.0115, 2 0.0059 at L2 | 0.482 (N-layer, L1) |
| A4 cases, K (margin 0.40) | **3.67** (N-layer) | **2.00** (N-layer) | 0.042 (1a, 2, 3 only) | 0.014 (2, 3 only) |
| A4 dev layouts, K (margin 0.25) | **+inf** (4 divergent, 6 oscillatory of 16 dies) | **+inf** on side_by_side_6 (8 divergent); u_shaped_2 0.354 | n/a (2 levels) | n/a (2 levels) |
| max CG iterations, L0-L2 (limit 300) | 286 (Case 1a L2) | 225 | **400 = cap** (1a and 2, L2); 359 at 1a L1 | **400 = cap** (2, L2); 352 at 1a L1 |
| Tj-max node moved between levels | 14 of 16 dies | 14 of 16 | 12 of 16 (L0 to L1) | 12 of 16 |
| verdict | ineligible (margins) | ineligible (margins) | ineligible (CG) | ineligible (CG) |

Other per-case details: Case 1b, Case 3 and the manufactured case meet A1, A2 and A4 for every candidate. The
manufactured case's worst error is 0.0085 K (Q1) and 0.00005 K (Q2, L1). Case 1a's s2 mean is 0.130 K off for
`q1_h4` and 0.0115 K for `q2_h4`. Case 2's s2 mean is 0.047 K off for `q1_h4` and 0.006 K for `q2_h4`. **[I]** The
errors come from discretisation, not from a bias. On every failing point the three-level sequence moves
monotonically toward the reference: N-layer d3 mean for `q1_h4` is 402.03 / 408.92 / 411.86 K against 413.25 K. The
GCI there (3.67 K) brackets the true error (1.39 K). Observed order is about 1.2, below Q1's nominal 2, which fits an
edge singularity.

**[S] Extrapolation, labelled as such.** The Q2 N-layer error goes 2.20 K (L0) to 0.48 K (L1), a ratio of 0.22. If
that ratio held, level 2 would be about 0.1 K off, still above 0.04 K and beyond the 0.05 K of A2. Not measured: the
Q2 N-layer level 2 has 3.06 M DOF, about 12-14 GB.

## 5. Regression guard for E009's spec (K1/K2)

No configuration is frozen. Here are the dev values for the record. `q1_h4` at level 2 gives A1 = 0.0171 and
A2 = 1.389 K. `q1_h2` gives at least 0.0084 and 0.680 K (incomplete). Both Q2 candidates give at least 0.0060 and
0.482 K (level 1, incomplete). **[I] Consequence for the objective:** with any of these four configurations, E009
would trip **K2** (> 0.25 K, read as "a model or implementation error"). The N-layer source mean causes it, and the
cause is a discretisation shortfall, not a model error. The founder should know this before E009 is designed around
the current A2 / K2 pair and grid budget.

## 6. Memory and cost (E009 plan per candidate; JSON `candidates.<id>.e009_plan`)

[F] Measured Q2 whole-process peak memory per DOF:

| DOF | Q2 bytes/DOF |
|---|---|
| 0.2-0.6 M | 4.0-6.0 kB |
| 1.28 M | 4.3 kB |
| 1.58 M | 3.9 kB |
| 2.08 M | 3.0 kB |

All are below the module's 10 kB bound. Q1 at 1.35 M DOF: 4.2 kB/DOF.

The E009 table is extrapolated where a solve was not run, with DOF counted exactly from the grid. It covers 6 cases
x 3 levels, the manufactured null, and 5 layouts x (3 calibration L0 + L1 + L2 + constant-k). The three fresh
layouts are taken at 1.5 x the larger dev layout's DOF.

| candidate | finest-level peak | wall = CPU hours | recommended timeout | burst needed? |
|---|---|---|---|---|
| q1_h4 | 4.7 GB (measured) | 0.4 h | 2 h | no |
| q1_h2 | 30.5 GB (Case 1b L2, 7.2 M DOF) | 0.9 h | 3 h | yes |
| q2_h4 | 14.4 GB (fresh-layout allowance, 4.8 M DOF) | 1.3 h | 4 h | yes |
| q2_h4z2 | 18.3 GB | 3.7 h | 12 h | yes |

The burst runs fit an n2-highmem-32 (256 GB, 217 GB usable) with a large margin. Not costed here: the
finite-volume L2 cross-check (levels 1-3 of its rule). The wall extrapolation assumes 1.3x per level for CG growth.
Q2 Case 2 went 288 → 400 (cap) iterations, so the growth is at least that.

Completing the incomplete levels (not needed for the verdict, since every candidate is already ruled out) is a
founder-run dev burst: `scripts/burst_gcp.sh --cmd "uv run python research/scripts/o007_dev_study.py --full" research/o007_dev`
(it resumes from `research/o007_dev/cache/`).

## 7. What would change this conclusion

- A reference error. That is unlikely: the hashes match, and Cases 1b and 3 and the manufactured case agree to
  0.0003-0.008 K through the same code. A wrong N-layer reference would also have to explain the monotone convergence
  toward it.
- A point-definition mismatch for "mean". The production `tj_mean` is the Galerkin face mean, and the reference is
  the area mean over the source. The monotone approach to the reference argues against a mismatch.
- A cheaper rule that resolves source edges (for example a geometric grading toward die edges, finer than
  `near_margin`'s x1/x2/x4). That would need a change to `thermal_fem` and a new pre-registered study.

## 8. Recommendations (no production change made here)

1. **Founder decision (planning).** On the four pre-registered configurations, O007's A2/K2 is not reachable on the
   N-layer source means with r = 2 in x, y and z over three levels, at a cost E009 can afford. The options need a
   new pre-registration:
   - (a) a grid rule with edge grading near sources (builder task on `thermal_fem`, with a review), then a new dev
     study;
   - (b) Q2 with a finer h0 near sources only, costed on the burst VM;
   - (c) revisit the objective's resolution budget for the N-layer case.

   None of these is decided here.
2. **Implementation (AMG-CG headroom, T0218).** Q2 reaches the 400-iteration cap at level 2 on Case 1a and Case 2,
   the weak-Robin 10 mm plates, and those solves pass only through the 1e-8 final check. Q2 is ineligible until a
   solver task (preconditioner, cap, or snap policy) restores the headroom, with its own review.
3. **Q1 on layouts.** Tj-max sequences are divergent or oscillatory on 10 of 16 dies (`q1_h4`), and the argmax node
   moves on 14 of 16. The T0198/T0202 concern is confirmed for Q1 at these grids.
