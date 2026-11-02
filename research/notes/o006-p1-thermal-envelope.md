# O006 pilot P1: thermal envelope, O002 load levels and O003 operating point (research note, not evidence)
Task T0167 (O006) · scientist · 2026-11-01 · Exploratory design input (O006 F4: pilots are never evidence).

Amendment before the production run (2026-11-01): the fixed level was changed from 1 to 0 because a
2-layout smoke run cost 250-315 CPU-s per layout at level 1 single-threaded (about 9 CPU-hours for the sample against
the brief's ~3). The smoke run is not part of the results. Nothing else changed.

## 1. Pre-registered rules (written before any solve; recorded by sha256 in `research/o006_p1/raw/prereg.json`)
Solver: `moduleforge.solvers.thermal_layout`, frozen grid rule, **level 0** for every P1/P2 number (one fixed level;
the grid of each layout is built once and reused for all its solves; a check shows the reuse reproduces
`solve_layout_level` exactly). Coolant T_c = 338.15 K, uniform h = 5000 W/(m² K), equal power P per die, uniform over the
die top. k(T): the coded laws of `geometry/stack.py` (nominal); constant k: every layer at its 300 K `Layer.k`.

Sample (dev seeds only; none appears in O003/O004, which name no numeric seed, and E006's A3 seed 20261101 is avoided):
15 strata (family x dies 2-6); stratum s draws from `generate_layouts(n, 916701 + s, family, dies)`.
- P1 balanced set: in each stratum, for each die size 4.0/4.5/5.0/5.5 mm (the generator's 0.5 mm grid), the first 2
  layouts of that size in the stream: 2 x 4 x 15 = 120 layouts, 30 per die size, every stratum equally in every bin.
- P2 core: P2 note, section 1 (10 layouts per stratum at its drawn die size; the first 2 overlap the balanced set).
- Level-bias set: the first P2-core layout of strata 0, 2, 4, 5, 6, 8, 9, 10, 12, 14 (all families, dies 2-6), solved
  at levels 1 and 2 as well.

Per layout of the balanced set: constant-k, one linear solve at 1 W/die gives every die's rise per watt, so the
constant-k limit is P_lim,ck = 110 K / max rise-per-W. With k(T), P_lim is found by secant iteration on the hottest-die
Tj max to |Tj max - 448.15 K| <= 0.02 K; one more k(T) solve at 0.55 P_lim; the k(T) rise of the hottest die is fitted
per layout as aP + bP² (least squares through the origin over all its k(T) solves) to give P60 (60 K rise).
k(T) sensitivity (T0157 final note, review T0174): the P1 envelope is recomputed by secant from the nominal limit with
(i) 4H-SiC through-die k = 270 W/(m K) (T/300)^-1.50 (low end) and (ii) 390 (T/300)^-1.25 (high end), the c-axis range of
T0157; (iii) SAC305 alpha = 4.0e-3 /K and (iv) 5.0e-3 /K (T0157 slope range), applied to both SAC305 layers (substrate
solder and die attach). Each one at a time; laws are varied in the pilot script only.

Envelope statistic per die size (n layouts): the highest power keeping Tj max <= 175 °C on >= 95 % of layouts is the
order statistic P_(k+1) of the sorted per-layout limits with k = floor(0.05 n) (n = 30: the second smallest); 95 %
interval by bootstrap over layouts (B = 2000, seed 916799), reported with the caveat that extreme-quantile bootstrap at
n = 30 is rough.

Load levels for O002 (frozen rule): the two levels are the powers at which the hottest layouts (the 95 % envelope) rise
60 K and 110 K, common to all strata in integer watts:
- P_hi = floor(min over die sizes of the k(T) envelope power), so Tj max <= 175 °C on >= 95 % of layouts of every size;
- P_lo = floor(min over die sizes of the same order statistic of P60), so the hottest-die rise is <= 60 K on >= 95 %.
The distribution of rises at both levels is reported (fraction in 60-110 K, by die size and die count).
O003 operating point: O003 fixes the power per reference so that its hottest die rises 60 K; P1 reports P60 by die size
and die count, the Tj headroom to 175 °C there, and P_lo as the single common value for generator development layouts.
Level bias: on the level-bias set, level-0 minus level-2 per-die Tj max at P_lo and P_hi (k(T)), with the three-level
GCI, and the implied bias of the envelope power.

## 2. What was run (facts)
- Pre-registration is checkable: the sha256 in `raw/prereg.json` (written 2026-11-02T07:11:01Z, before the first P1
  solve) is that of the first 45 lines of this note and the first 49 lines of the P2 note, joined by newlines with no
  trailing newline. Check with `python3 -c "import hashlib;L=open('research/notes/o006-p1-thermal-envelope.md').read()
  .split(chr(10));print(hashlib.sha256(chr(10).join(L[:45]).encode()).hexdigest())"` (expect 33f0bbc9...; with the P2
  note and `L[:49]` expect b08f7648...). Both matched on 2026-11-02, so sections 1 (and the level amendment above them)
  were not edited after the solves.
- Script `research/scripts/o006_p1/thermal_envelope.py` (phases check, p1, levels, p2, bias, report); raw per-layout
  records in `research/o006_p1/raw/`, summary in `research/o006_p1/results.json`, log in `research/o006_p1/run.log`.
- Seeds (all dev, all recorded in results.json): 916700 (die size per stratum), 916701-916715 (generator stream of
  stratum 0-14), 916799 (bootstrap). 240 distinct DRC-valid layouts, each re-generated from (seed, stream index) and
  checked against its stored `Layout.fingerprint()`. 120 in the balanced P1 set (30 per die size, 2 per stratum and die
  size, 60 of 60 (family, dies, die size) cells filled), 150 in the P2 core (30 overlap), 10 in the level-bias set.
- Sanity checks (all passed): grid reuse vs `solve_layout_level` max |dTj| 1.4e-10 K (k(T)) and 0 (constant k); the
  variant code with the coded values (370, -1.49; alpha 4.2e-3) reproduces the coded laws to 1.9e-10 K; constant-k
  linearity error 6e-14; energy balance <= 1.5e-13 on all 2216 P1/P2 solves; Picard <= 6 iterations; P_lim(k(T)) <
  P_lim(constant k) on 120/120 layouts (every coded law decreases with T, so this sign is required); each variant moves
  every one of the 120 limits in the expected direction (SiC low and SAC 5.0e-3 down, SiC high and SAC 4.0e-3 up, 120/120);
  the per-layout quadratic fit used for P60 and for the balanced-set rises agrees with direct solves at 25 and 45 W within
  0.077 K (60 comparisons on the 30 overlap layouts).
- Compute: see section 6.

## 3. Results: envelope (facts; level 0, k(T) nominal unless stated)
Highest power per die keeping Tj max <= 175 °C on >= 95 % of layouts (order statistic, n = 30 per die size; 95 %
bootstrap interval in brackets; min and median of the per-layout limits):

| die size | k(T) nominal | constant k (300 K values) | min / median per layout, k(T) |
|---|---|---|---|
| 4.0 mm | **45.6 W** [44.0, 48.6] | 51.0 W [49.3, 54.5] | 44.0 / 53.3 W |
| 4.5 mm | **51.5 W** [50.5, 55.3] | 57.8 W [56.3, 61.6] | 50.5 / 59.3 W |
| 5.0 mm | **56.6 W** [55.9, 57.8] | 63.2 W [62.1, 64.6] | 55.9 / 65.4 W |
| 5.5 mm | **60.2 W** [58.0, 64.2] | 67.2 W [64.3, 71.4] | 58.0 / 69.5 W |

- k(T) lowers the envelope by 10.4-11.7 % against constant k at 300 K values (part of this is only that the coolant is
  at 338 K, where every coded k is already lower than at 300 K).
- Die count matters more than die size (k(T), all sizes pooled, n = 24 per die count): 65.6 W (2 dies), 56.2 (3),
  52.0 (4), 48.6 (5), 45.6 (6). Pooled over all 120 layouts: 50.3 W.
- O002's current top level of 60 W per die keeps Tj max <= 175 °C on 27 % (4.0 mm), 50 % (4.5), 73 % (5.0) and 97 %
  (5.5) of layouts (per-layout limit >= 60 W, exact from the secant). O002's F1 sanity check (>= 90 % at 60 W) would
  fail on this generator space for every die size but 5.5 mm.

### k(T) sensitivity (T0157 final note ranges; review T0174)
Envelope (W) with each law varied one at a time; shift against nominal in brackets:

| die size | nominal | SiC c-axis low: 270 (T/300)^-1.50 | SiC c-axis high: 390 (T/300)^-1.25 | SAC305 alpha 4.0e-3 | SAC305 alpha 5.0e-3 |
|---|---|---|---|---|---|
| 4.0 | 45.64 | 45.08 (-0.56) | 45.88 (+0.24) | 45.67 (+0.03) | 45.53 (-0.11) |
| 4.5 | 51.47 | 50.89 (-0.58) | 51.71 (+0.24) | 51.50 (+0.03) | 51.34 (-0.13) |
| 5.0 | 56.55 | 55.95 (-0.60) | 56.81 (+0.26) | 56.58 (+0.03) | 56.42 (-0.13) |
| 5.5 | 60.22 | 59.66 (-0.56) | 60.46 (+0.24) | 60.25 (+0.03) | 60.09 (-0.13) |

- The 180 um SiC die and the 50 um / 100 um SAC305 layers are a small part of the die-to-coolant resistance, so the
  T0157 ranges move the envelope by at most -1.2 % / +0.5 % (SiC) and -0.3 % / +0.1 % (SAC305). The sampling interval of
  the envelope itself (n = 30) is 2-5 W wide, about ten times the law uncertainty.
- Si3N4 is not in the default DBC stack (Al2O3 ceramic), so T0157's Si3N4 range does not apply to this pilot. T0157
  lists no other correction that is not already a range above (its SAC305 alpha check found no discrepancy).
- Combined corners were not solved. (inference) Adding the one-at-a-time shifts, the pessimistic corner (SiC low and
  SAC305 5.0e-3) gives 44.97 W at 4.0 mm and the optimistic corner 45.91 W.

## 4. Results: O002 load levels and O003 operating point
Frozen rule (section 1): P_hi = floor(45.64) = **45 W per die**; P_lo = floor(min over sizes of the P60 order statistic
= 25.74 W at 4.0 mm) = **25 W per die**. P60 order statistics by size: 25.7 / 29.1 / 31.9 / 34.0 W.

Hottest-die rise on the balanced set (n = 120; per-layout fit, checked within 0.077 K against direct solves):

| level | median | 5th pct | 95th pct | max | in 60-110 K | <= 110 K | median by dies 2/3/4/5/6 |
|---|---|---|---|---|---|---|---|
| 25 W | 41.0 K | 30.0 | 52.6 | 60.4 | 1 % | 100 % | 32 / 38 / 42 / 46 / 46 K |
| 45 W | 75.7 K | 55.2 | 97.8 | 112.7 | 88 % | 99 % | 59 / 71 / 77 / 86 / 85 K |

Does the recommendation change under the T0157 ranges? (fact, one at a time) The minimum envelope stays >= 45.08 W in
every variant, so P_hi = 45 W is unchanged. (inference) P60 was not recomputed per variant; the variants move the
110 K limit by at most 1.2 %, the margin of P_lo is 0.74 W (2.9 %) and the law effects are smaller at a 60 K rise than at
110 K, so P_lo = 25 W is unchanged. Under the additive pessimistic corner the 4.0 mm envelope would be 44.97 W, and the
rule would give 44 W instead of 45 W (a 0.03 W difference, inside the sampling interval [44.0, 48.6] W).

Interpretation (inference):
- 45 W is the most a common power per die can be on this generator space with 175 °C on >= 95 % of 4.0 mm layouts. At
  45 W, 88 % of layouts rise 60-110 K, so 45 W is a good single top level for O002.
- The frozen rule's low level (25 W) puts the hottest layouts at 60 K, but most layouts at 30-53 K, below the 60-110 K
  band. With one power for all strata, two levels cannot both sit inside 60-110 K: at a fixed power the hottest-die rise
  varies by a factor of 1.77 across layouts (p95/p05 at 45 W), about the band's own ratio of 110/60 = 1.83. If O002 wants
  both levels in the band, it needs a power per stratum (the die size is already fixed per stratum), for example the
  stratum's P60 and P_lim medians. That is a founder decision; this pilot does not choose it.
- O002 now uses 30 and 60 W. 60 W is outside the envelope for most layouts (section 3); 30 W is about the P60 of the
  smaller dies.

O003 operating point. O003 sets the power per reference so that the hottest die rises 60 K (Tj max = 125 °C, 50 K
below 175 °C). On generator layouts this power (P60, k(T)) is 24.8-54.6 W per die: medians 39 / 33 / 30 / 29 / 27 W
(4.0 mm, 2-6 dies) to 52 / 44 / 39 / 37 / 36 W (5.5 mm), and 0.57 of the layout's own 175 °C limit (median). The
operating point therefore never touches the envelope, and O003's +2 K Tj budget is far from 175 °C. For generator
development layouts with one common value, use P_lo = 25 W (hottest-die rise <= 60 K on >= 95 % of layouts of every
size). Full table: `o003_operating_point.P60_W_by_die_size_and_dies` in results.json.

## 5. Level bias (facts; 10 layouts, the pre-registered set)
All 10 pre-registered level-bias layouts were solved at levels 1 and 2 (finest) at 25 W and 45 W, k(T): all three
families, 2-6 dies per switch, die sizes 4.0 (3 layouts), 4.5 (2), 5.0 (2) and 5.5 mm (3); 80 dies. Level-2 grids have
4.5-12.4 M cells. Level 0 (used) minus level 2 (finest), per-die Tj max:

| load | per-die bias, min / mean / max | SD across layouts of the Tj max bias | layout spread bias (max - min over all dies), mean / SD / max | L1 - L2 max abs | three-level GCI max |
|---|---|---|---|---|---|
| 25 W | +0.14 / +0.30 / +0.49 K | 0.10 K | +0.06 / 0.03 / 0.12 K | 0.13 K | 0.13 K |
| 45 W | +0.25 / +0.56 / +0.92 K | 0.19 K | +0.12 / 0.05 / 0.22 K | 0.25 K | 0.25 K |

- The sign is the same on all 80 dies at both loads: level 0 reads hot. The implied envelope-power bias at 45 W (Tj max
  bias divided by the layout's slope dTj/dP from its fit) is -0.23 to -0.57 W, so every level-0 envelope is conservative
  by 0.5-1.3 %.
- (fact) The Tj max bias is largest on the smallest dies: 0.69-0.92 K at 4.0 mm, 0.38-0.56 K at 5.5 mm (45 W). (inference)
  The level-0 cell is too coarse to resolve the spreading under a small die; this is the size that sets P_hi.
- (inference) At the finest level the 4.0 mm envelope would be about 45.64 + 0.28 to 0.57 = 45.9 to 46.2 W, so the
  frozen rule could give P_hi = 46 W instead of 45 W. The order statistic is set by side_by_side_6_s916705_i000
  (45.64 W), which is not in the bias set, so this is an estimate from the other three 4.0 mm layouts, not a solve. Either value is inside the envelope's sampling interval [44.0, 48.6] W.
- For P2 only the part of the bias that changes between layouts or dies matters: SD across layouts 0.10 K (25 W) and
  0.19 K (45 W); die-to-die range of the bias within one layout up to 0.17 K (25 W) and 0.34 K (45 W). These are against
  within-stratum SDs of layout Tj max of 0.66-1.83 K (25 W) and 1.26-3.60 K (45 W), and null p95 errors of >= 0.97 K, so
  the level cannot change a P2 conclusion about Tj max or pair differences. It is not small for the switch-spread null
  (P2 note, section 4). It would matter for O002's 0.5 K pair threshold, which O002 judges on its own L2 at the GCI
  levels.

## 6. Compute and sample sizes
8840 CPU-s (2.46 CPU-h) recorded over 2256 solves of finished work: 120 P1 layouts x about 15 solves, 150 P2 layouts x 2,
10 bias layouts x 4 (2766 CPU-s for the bias set). Not counted, because no process records it: the 2-layout level-1 smoke
run; in attempt 1, two parallel level-2 processes that stalled in swap; in attempt 2, seven parallel level-2 processes
that I started by mistake (about 6 GB each on a machine already under memory pressure), which the sandbox did not let me
stop and which ended after about 11 minutes with no output (killed by the OS, inference). The 7 layouts were then solved
in one sequential process (about 45 min wall, ending 10:19 UTC on 2026-11-02 by the file times; the first layout took
about 23 min in heavy swap while other sessions' jobs used the same machine). The cached
results do not depend on these failed runs: every layout record is written only when its solve completes.
Sample sizes: envelope n = 30 per die size (120 in total), n = 24 per die count; P2 n = 10 layouts per stratum x 15
strata; level bias n = 10 layouts (80 dies).

## 7. Summary, and what would prove this wrong
- Envelope at 175 °C with k(T), level 0: 45.6 / 51.5 / 56.6 / 60.2 W per die for 4.0 / 4.5 / 5.0 / 5.5 mm (constant k:
  51.0 / 57.8 / 63.2 / 67.2 W). The T0157 law ranges move it by -1.2 % to +0.5 %; the level-0 grid makes it 0.5-1.3 %
  conservative (10-layout bias set).
- O002 load levels by the frozen rule: 25 W and 45 W per die, unchanged under every one-at-a-time T0157 range (45 W could
  become 44 W only under the additive pessimistic corner, and 46 W at the finest level; both inside the sampling
  interval). O002's 60 W is outside the envelope for 4.0-5.0 mm dies. At 25 W most rises fall below 60 K (section 4).
- O003: power per reference at a 60 K hottest-die rise, 25-55 W on generator layouts. Common development value 25 W.
- Falsifiers: an independent FEM or level-2 sweep that puts the 4.0 mm envelope below 45 W; a fresh seed set whose
  second-smallest 4.0 mm limit falls below 45 W (the bootstrap interval reaches 44.0 W); primary c-axis 4H-SiC data
  outside 270-390 W/(m K).

## 8. Recommended follow-up
- Founder decision for O002: common 25/45 W (frozen rule) or per-stratum powers that keep both levels in 60-110 K.
- If P_hi must be known to 1 W, solve the order-statistic layouts of the 4.0 mm bin at level 2 (2 layouts, about 10-20
  CPU-min each, one process at a time: level 2 needs about 6 GB).
