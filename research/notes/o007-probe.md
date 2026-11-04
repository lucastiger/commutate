# O007 feasibility probe (T0225): N-layer source-edge resolution, Q2 CG discriminator, E009 cost per option

Author: scientist, T0225 attempt 1, 2026-11-03. Script: `research/scripts/o007_probe.py` (reuses
`research/scripts/o007_dev_study.py` by import). Outputs: `research/o007_probe/{probe.json, plan.json, cache/}`.
Labels: **[F]** fact (file or listed command), **[I]** inference, **[S]** speculation or extrapolation.

## 0. Pre-registration (written and committed before any solve of this probe)

Before writing this section I ran only grid construction (DOF counts, cell-size ratios; `--plan` and a scratch
survey of five grading variants, N-layer / Case 1a / dev-layout level-0 DOF). No temperature was computed in this task.
References: O006 frozen files, series sha256 `befc5efa...`, manufactured `ca05847b...` (checked by `load_refs` first).
Layouts (cost only, no solve): dev seed 20261101, side_by_side x6 and u_shaped x2, fingerprints as in E006.yaml.

### 0.1 Configurations (four in total; production thermal_fem unchanged: CG cap 400, LINEAR_RTOL 1e-11, SNAP_FRACTION 1e-2)

| id | part | order | h0 | near_margin | dz_max | mandatory lines | grading | problems, levels |
|---|---|---|---|---|---|---|---|---|
| `p1_q2h4_maxlines` | 1 | Q2 | 4 mm | 2 mm | 5 mm | centroids + frozen reference-maximum lines (production) | none | Case 1a, Case 2; L0, L1 |
| `p1_q2h4_centroid` | 1 | Q2 | 4 mm | 2 mm | 5 mm | centroids only | none | Case 1a, Case 2; L0, L1 |
| `a_q1h4_graded` (option a) | 2 | Q1 | 4 mm | 2 mm | 1 mm | production | geometric, 0.2 | N-layer; L0, L1, L2 |
| `b_q2h1` (option b) | 2 | Q2 | 1 mm | 0.5 mm | 5 mm | production | none | N-layer; L0, L1, L2 |

nz_min 1 cell per layer, min_cells 2, Picard tolerance as production. Level-0 DOF counted [F]: N-layer
`a_q1h4_graded` 232,130 / 1,752,579 / 13,606,565 (L0/L1/L2); `b_q2h1` 142,155 / 1,087,877 / 8,508,105. Part 1:
Case 1a 29,645 / 210,681 (max lines) and 23,805 / 168,921 (centroid only); Case 2 10,125 / 71,289 and 4,205 / 29,241.
Minimum neighbour lateral cell-width ratio at L0: Case 1a 0.0092 (max lines) vs 0.197 (centroid only); Case 2 0.0071
vs 0.333; `b_q2h1` 0.0076 (production max lines 8.5-17.5 um from centroids, not snapped at h0 = 1 mm);
`a_q1h4_graded` 0.066.

### 0.2 Grading offsets of option (a) (fixed by the geometry, never by a solution)

Offsets from every source edge, both sides, in x and in y: first offset 0.1 mm, growth ratio 2.5, up to about h0:
**0.1, 0.25, 0.625, 1.5625, 3.906 mm**. Basis: 0.1 mm lies between the die attach (0.05 mm) and die (0.18 mm)
thicknesses; each interval gets the rule's 2 cells, so the first cells are 0.05 mm at L0. The outermost offset is about
3 x the DBC spreading length sqrt(k_Cu t_Cu t_cer / k_cer) = sqrt(385 x 0.3e-3 x 0.38e-3 / 24) = 1.35 mm (fin
estimate, derived here). Inward offsets are kept only below (half-width - 0.5 x step). A candidate line is dropped if
it is closer than 0.5 x its own offset step to a fixed line (domain ends, source edges, centroids, maximum lines) or to
an already accepted line (finest first), so overlapping gradings create no slivers. Why Q1 for (a): the same grading
with Q2 (h0 4 mm) costs 0.45-0.82 M DOF at L0 on the N-layer case (3.6-6.6 M at L1, over the 10 GB local cap) in the
grid-only survey; Q1 keeps L0 and L1 measurable locally and L2 within the burst VM. Option (b) "small near_margin"
is 0.5 mm.

### 0.3 Measurements

Per solve: DOF, peak RSS (child process), wall time, CG iterations per Picard step (`cg_only` counter of T0207), final
relative residual ||b - Ax|| / ||b||, energy balance, snapped lines, minimum neighbour cell-width ratio (x, y, z,
lateral). N-layer (part 2): the 12 frozen O006 A1 points (centroid, source mean, reference maximum of d1-d4); per level
|T - T_ref|, the max scaled error (|err| / 81.05 K, O006 A1 scale), DOF, peak RSS, CG max. With three levels:
`mfos.metrics.gci_capped` (floor 1e-3 K), branch and observed order. Levels a local rule does not allow are recorded
as skipped with the estimate; every extrapolation is labelled [S].

Local memory rule: one solve at a time in a child process, at most 5 GB, or at most 10 GB when memory_pressure shows
>= 50 % free and swap (proxy) < 4 GB; watchdog kill at 10 GB RSS or 8 GB swap. Estimate before a solve: DOF x the max
measured whole-process bytes/DOF of the same element order at >= 1 M DOF (dev_study.json and this probe) x 1.15.

### 0.4 Readings and decision rule (thresholds fixed here)

**Part 1 reading (per case, CG max over Picard steps and levels 0-1).** with-max > 300 and centroid-only <= 300:
*slivers*, fixable by the line or snap policy. Both > 300: *conditioning* on the weak-Robin plates, needs a
preconditioner change. Both <= 300: *not discriminating at levels 0-1*. Centroid-only > 300 >= with-max: neither.
Statement for option (b): headroom recoverable without a solver change = "yes" if at least one case reads slivers and
none reads conditioning; "no" if any case reads conditioning; otherwise "undetermined at levels 0-1".

**Part 3 cost.** Exact DOF from the grid of every E009 scikit-fem solve under each part-2 rule: 6 cases (1a, 1b, 2,
3, N-layer, manufactured) x levels 0-2, the 2 dev layouts x levels 0-2 with the same die-edge grading, and 3 fresh
layouts at 1.5 x the larger dev layout's DOF per level. Peak = DOF x bytes/DOF (rule above, without the 1.15).
Fits the burst VM iff the largest peak <= 0.85 x 256 GB = 217.6 GB. CPU-hours [S]: s/DOF of the largest measured
N-layer probe solve of that configuration x DOF, x 1.3 per level beyond it.

**Part 4 go/no-go per option (the packet's default rule, with these interpretations):**
- **go**: N-layer max |T - T_ref| over the 12 points <= **0.040 K** at a measured level, CG max <= **300** on every
  probe solve of that option's configuration (its part-2 solves), and the E009 cost fits the burst VM.
- **provisional_go**: the same, with the level-2 error Richardson-extrapolated [S] when level 2 is not measured:
  observed order p = log2(E1 / E0... finest pair) = log2(E_{L-1} / E_L) of the A2 metric E (max over points of
  |T - T_ref|, reference known) at the two finest measured levels, required in **[0.5, 2]**, and E_2 = E_1 x 2^-p
  <= 0.040 K.
- **no_go**: otherwise. A no_go reached with level 2 unmeasured is labelled "unverified at level 2" in the basis.
- No stricter rule is added. Part 1 is reported separately for option (b) as the packet asks; it does not enter the
  rule, because the rule's CG clause covers the option's own probe solves.

What would make this probe wrong: a reference error (hash-checked), a point-definition mismatch for the mean (same
`tj_mean` as T0207), or a grid-rule bug in the emulated grading (checked by the energy balance and node-count growth).

---
*Everything below was written after the data.* Pre-registration commit: `c2cf616` (recorded in `probe.json` as
`preregistration_commit`).

## 1. Outcome

| | option (a) `a_q1h4_graded` | option (b) `b_q2h1` |
|---|---|---|
| levels run (local) | 0, 1 (L2 13.6 M DOF, est. 65.7 GB: skipped) | 0, 1 (L2 8.5 M DOF, est. 45.4 GB: skipped) |
| DOF | 232,130 / 1,752,579 | 142,155 / 1,087,877 |
| N-layer max \|T - T_ref\|, K | 0.591 / **0.152** (d1 mean) | 0.263 / **0.057** (d3 mean) |
| max scaled error (A1 scale 81.05 K) | 0.0073 / 0.0019 | 0.0032 / 0.0007 |
| observed order of A2 (L0 to L1) | 1.96 (per point 1.78-1.96, all errors negative) | 2.21 (means 2.15-2.26; centroids/maxima 3.6-4.0) |
| Richardson L2 error [S] | 0.039 K | 0.012 K (p outside [0.5, 2]) |
| CG max per level | 132 / 191 | 296 / **400 = cap** |
| final relative residual | 1.1e-11 / 1.2e-11 | 1.2e-11 / 7.7e-11 |
| peak RSS | 1.34 / 4.13 GB | 1.13 / 5.05 GB |
| min neighbour lateral cell ratio | 0.066 | 0.0076 (max-line slivers, 4.3 um cells) |
| E009 finest peak (part 3) | 66.5 GB (fresh layout L2, 15.8 M DOF) | 114.4 GB (Case 1b L2, 24.7 M DOF) |
| E009 CPU-hours [S] | 5.0 h | 5.9 h |
| fits n2-highmem-32 (217.6 GB) | yes | yes |
| **go_no_go** | **provisional_go** | **no_go** (CG cap; also p > 2) |

[F] Option (a) meets the provisional rule by a small margin: E_2 [S] = 0.152 x 2^-1.96 = 0.0392 K against 0.040 K.
E_2 <= 0.040 K needs p >= 1.93, and E_2 <= 0.05 K (A2 itself) needs p >= 1.61. [I] So the verdict hangs on the order
staying near the Q1 nominal 2 from L1 to L2. The per-point orders (1.78-1.96, one sign) suggest the asymptotic range;
T0207's ungraded Q1 showed about 1.2 here. Neither fact proves the order holds at L2.

[F] Option (b) is the more accurate per DOF (0.057 K at 1.09 M DOF), but its L1 solve reached the 400-iteration cap.
Its grid carries the production maximum lines 8.5-17.5 um from the centroid lines. At h0 = 1 mm they are not snapped
(1e-2 of a 0.5-1 mm cell), so they leave 4.3 um cells, a neighbour ratio of 0.0076. That is the same sliver signature
that part 1 isolates.

## 2. Part 1: CG discriminator (Q2, q2_h4 settings, levels 0-1) [F]

| case | variant | CG max L0 / L1 | final rel. residual (max) | min lateral cell ratio | DOF L1 |
|---|---|---|---|---|---|
| 1a | with maximum lines | 249 / **359** | 1.7e-11 | 0.0092 | 210,681 |
| 1a | centroid only | 28 / 32 | 8.4e-12 | 0.197 | 168,921 |
| 2 | with maximum lines | 190 / 288 | 4.3e-11 | 0.0071 | 71,289 |
| 2 | centroid only | 15 / 17 | 4.5e-12 | 0.333 | 29,241 |

The with-maximum-lines values reproduce T0207 to the iteration (249, 190, 359, 288). Readings by the section-0 rule:
Case 1a is *slivers*. Case 2 is *not discriminating at levels 0-1*, since both variants stay at or below 300. [I] Case 2
still shows the same 17-fold drop. The centroid-only grids are also 20-60 % smaller. Grid size alone cannot explain an
11- to 17-fold change in iterations, though, while the sliver ratio changes by 20-50 times. **Statement for option (b):
the CG headroom can be recovered without a solver (preconditioner) change. The fix is a line or snap policy for the
maximum lines.** That policy (SNAP_FRACTION and the mandatory-line rule) lives in `thermal_fem`'s grid builder. Changing
it is still a `src/` change, with its own review. Not measured: CG at L2 with centroid-only lines, and option (b) with a
sliver-free line policy. That would have been a fifth configuration.

## 3. Checks [F]
Reference hashes matched (`load_refs`, series `befc5efa...`, manufactured `ca05847b...`). Energy balance <= 6e-13 on
every probe solve. Node-count growth from L0 to L1: 7.55 for (a) and 7.65 for (b), inside 8 +/- 15 %. Every point
evaluated is a node; snaps are recorded (max snap 17.5 um for (a), 4.5 um for (b)). Peak memory stayed below 5.1 GB.
memory_pressure showed 55-69 % free and the swap proxy 0 GB. Layouts were used only for grid counts (dev seed 20261101,
fingerprints checked). No fresh or sealed seed was used, and the holdout data directory was not read.

## 4. Commands run (exit codes)
1. `uv run python research/scripts/o007_probe.py --plan` (grid only, before section 0): 0.
2. Commit of section 0 (`c2cf616`), then `uv run python research/scripts/o007_probe.py`: 0. Log in
   `research/o007_probe/run_local.log`.
3. **Change after the data (bookkeeping only).** On the first launch, both centroid-only L0 solves failed. The script
   asked for the maximum points, whose lines that variant omits by design (`node_value` ValueError). The worker now
   skips those points in that variant only. The failed cache records were deleted and the run repeated (exit 0). No
   configuration, line or threshold changed. When the fix was made, no centroid-only CG count had yet been measured.
4. `uv run python research/scripts/o007_probe.py --report`: 0. `uv run ruff check research/scripts/o007_probe.py`: 0.
5. Typo in section 0.4: the stray "log2(E1 / E0... finest pair)". The definition after it, log2(E_{L-1} / E_L) at the
   two finest measured levels, is the one the code applies.

## 5. Not covered by this probe
- Level 2 of either option (burst; command below). CG on the Muzychka plates under the part-2 rules: those were costed
  but not solved. Under (b), Case 1a and 1b would also carry maximum-line slivers. Under (a), Q1 Case 1a reached 286
  ungraded in T0207.
- Dev-layout Tj convergence under grading (T0207: Q1 ungraded had divergent Tj-max on 10 of 16 dies), A4 (needs three
  levels), and the FV L2 cross-check cost.

## 6. Memo for the founder's path decision
- [F] Under the pre-registered rule: **option (a) provisional_go, option (b) no_go.** Both options' E009 cost fits the
  burst VM: 66.5 GB and 114.4 GB peaks, about 5-6 CPU-hours [S].
- [F] Grading the source edges in the tensor grid (emulated with mandatory lines, Q1) cut the N-layer error at L1 from
  T0207's ungraded Q1 values to 0.152 K, and raised the observed order to about 2. Its L2 is extrapolated to 0.039 K [S],
  just inside the 0.040 K margin.
- [F] Q2 at h0 = 1 mm is about 3 times as accurate at L1 (0.057 K). Its blocker is CG on slivers from the
  maximum-line policy, not accuracy. [F] Part 1 shows slivers cause the Q2 CG loss on Case 1a: removing the maximum
  lines takes 359 iterations to 32.
- [I] Two paths are open. (1) Build option (a)'s grading into the grid rule (builder task), and confirm L2 on the burst
  first. (2) Fix the maximum-line or snap policy (builder task, no preconditioner change), then re-probe option (b) with
  that policy. [S] Option (b) with a sliver-free policy would likely meet A2 at L2 with margin (extrapolated 0.012 K).
- **What would change this conclusion.** A measured L2 for (a) above 0.040 K, or an observed L1-to-L2 order below 1.93,
  makes (a) no_go. A CG count above 300 at L2 on the N-layer case or the Muzychka plates under (a)'s rule. For (b), a
  sliver-free line policy that still needs more than 300 iterations would point to conditioning instead.
- Burst to measure L2 of both options (resumes from the cache; about 57 GB and 45 GB peaks):
  `scripts/burst_gcp.sh --cmd "uv run python research/scripts/o007_probe.py --full" research/o007_probe`
