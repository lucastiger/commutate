# Diagnosis: E011's development miss on 2D_Case_2R (T0475, O008)

Author: the scientist agent, T0475, 2026-11-20. Protocol: skill mf-diagnosis. Labels: **Fact** (read from or computed
from a committed file named here), **Inference** (follows from the facts by a stated argument), **Speculation**.

Scope: development geometry (2D_Case_2R), development seed 20261116 and its committed draws only. I used no sealed
seed and read nothing under `data/holdout/`. I opened no NC State PREES module, no 2D_Case_5 and no customer geometry.
I edited no file under `src/`, `experiments/specs/`, the objective or `experiments/drafts/E011.yaml`. I ran no
0.25 mm solve, no VM job and nothing over the network. Local l2_layout solves at 0.5 mm: 50 solves, 1.33 CPU-hours
(the cap is 6).

## 0. Bottom line

- **Root cause.** The search stops short of moves that both L1 and L2 rate as improving. It does not stop at an L1
  optimum that L2 disagrees with.
- **Two mechanisms trap it** (facts in §3):
  - **(a) Rugged screen.** The frozen 4 mm L1 mesh makes L1 rugged at the search's 0.5 mm step along die-row
    coordinates. The search ends in dents 0.1–0.4 % deep, and the dents disappear at 2 mm and 1 mm mesh.
  - **(b) Coupled DRC move.** The PHASE column's lower edge can move only together with the high-side die row and
    slot 2's free end (rule `slot2_free_end`). The move set offers that 3-parameter move with a probability of order
    1e-6 per proposal.
- **An amplifier.** L2 prices the low-side die row's u position at about 0.7 %/mm. L1 prices it at 0.15–0.19 %/mm.
  So a die-row offset the search leaves (6–6.5 mm on draws 4 and 7) costs 3.4–4.2 points at L2 while L1 shows under
  1 %. This is why the L1 indicator passes 5 of 8 draws and L2 passes 2.
- **What the counterfactuals show.** From every one of the six failed end points, one or two structured moves that the
  frozen L1 also rates as improving bring L2 at 0.5 mm down by 2.6 to 5.6 points, to 0.987–0.998 of W*.
- **Class: model** (the search method's assumptions about the L1 landscape and the move set, plus L1's die-row
  sensitivity). Confidence 0.75. It is not implementation (no bug found), not experimental, not selection (H3
  refuted), and not within-shortlist misranking.
- **Finding for the founder.** With the frozen 4 mm screen, the 2 % line on 2R lies at the screen's resolution along
  the low-side die row. It is not shown to lie below what an L1-guided search can resolve with a smoother screen
  (§6).
- **Recommended redesign (option A, §7).** Structured moves (die-row line moves, DRC-coupled moves) and the L1 screen
  at hmax 2 mm everywhere E011 uses L1. Validate it on a fresh development seed, with a local 0.5 mm go/no-go on 2R
  before any VM.

## 1. Signal (confirmed)

**Fact** (`research/o008_e011_dev/dev_l2/dev_rows.json`, rows of 2D_Case_2R; rebuilt in `t1_assembled.json`).

- **Search s at 0.25 mm, draws 0–7:** 0.022 0.044 0.025 0.050 0.042 −0.010 0.017 0.034.
  - Pass (s ≤ 0.02): draws 5 and 6, so 2 of 8.
  - Without draw 1 (R_D 1.209, outside [1.25, 1.60]): 2 of 7.
- **Compaction s:** 0.034 0.056 0.030 0.059 0.072 0.012 0.014 0.100.
  - Resolved failures: 6 of 8 (5 of 7 without draw 1).
  - Paired wins of the search: 6 of 8 (5 of 7), missed on draws 2 and 6. So A3 = 0 either way.
- **Checks I re-ran:**
  - All 168 2R layouts solved at 0.5 mm were rebuilt from their manifest vectors, and every fingerprint matched.
  - L1(W*)/L1(W) reproduces 0.91379.
  - A local 0.5 mm solve of W* equals the burst's to 7e-15 relative: 144 GMRES iterations, same solver source sha256
    `ed0288b6…` (`t4_l2_local.json`, case A0).
  - A local solve of draw 7's end point gives the burst's ratio, 1.0338 (case A1).
  - The code under test is byte-identical to the burst's stamp: the five sha256 values in `dev_l2/code_stamp.json`.

## 2. Explanations considered

| id | explanation | discriminating test |
|---|---|---|
| H1 | fidelity: the search ends at an L1 optimum that L2 ranks below W* (C002-type misordering) | is the end point an L1 optimum? Do L1 and L2 disagree on the direction back to W*? (T3, T4) |
| H1′ | within-shortlist misranking | L2 span of each shortlist (T1) |
| H2 | basin or reach: move set, step, budget, DRC wall | L1 neighbourhood and path from the end point to W*; validity along the path (T3) |
| H2a | (added) a DRC-coupled move the move set cannot make | which single moves are invalid, and why; the joint move (T3c) |
| H2b | (added) L1 discretisation ruggedness at the 0.5 mm step | L1 scans at hmax 4 / 2 / 1 mm (T5, T7) |
| H2c | (added) budget alone | improving moves left at the end; ablation (e)'s terminal kind (T1, T3) |
| H3 | selection: W* is the lower of two and carries a shared error | size of the choice; determinism of the W* solve; W*'s residual in the L1→L2 fit (T2, T4) |
| H4 | the degradation moves parameters whose effect L1 does not see | per-parameter L1 vs L2 sensitivity at W*; the L1/L2 residual against parameter offsets (T2, T6) |

## 3. Tests and results

Every script is in `research/o008_e011_diag/` and writes the JSON named. All but T4 and T6 are L1-only or use
committed data. L1 is the frozen `twin._l1` (hmax 4 mm, 20 MHz). Validity means the search's constraint: it builds, is
DRC-clean under 2R's measured rules, and lies in `in_domain(reach=True)`.

### 3.1 T1: what the search returns, per draw (`t1_assemble.py` → `t1_assembled.json`)

**Fact.** Ratios are to W*. L2 is l2_layout at 0.5 mm from the burst. s is at 0.25 mm.

| draw | s | L1(b) | L2(b) | ablation (e) L1 / L2 | shortlist L2 span | row_LS_u0 − W* (mm) | compaction row_LS_u0 |
|---|---|---|---|---|---|---|---|
| 0 | 0.022 | 1.0078 | 1.0220 | 1.0102 / 1.0208 | 0.0008 | +3.5 | +4.0 (= D) |
| 1* | 0.044 | 1.0453 | 1.0446 | 1.0455 / 1.0442 | 0.0002 | +3.0 | +3.0 (= D) |
| 2 | 0.025 | 1.0233 | 1.0250 | 1.0257 / 1.0260 | 0.0003 | 0 | 0 |
| 3 | 0.050 | 1.0554 | 1.0492 | 1.0557 / 1.0493 | 0.0001 | 0 | 0 |
| 4 | 0.042 | 1.0080 | 1.0416 | 1.0194 / 1.0406 | 0.0001 | +6.5 | +7.5 (= D) |
| 5 | −0.010 | 0.9965 | 0.9900 | 1.0013 / 1.0041 | 0.0013 | −1.0 | +1.5 (= D) |
| 6 | 0.017 | 1.0112 | 1.0166 | 1.0106 / 1.0185 | 0.0009 | +2.0 | +2.0 (= D) |
| 7 | 0.034 | 0.9987 | 1.0338 | 1.0558 / 1.0832 | 0.0000 | +6.0 | +7.0 (= D) |

\* R_D outside the window.

- The search changes 12–22 parameters from W*. It restores only 7–13 of the 19–27 parameters the degradation planted.
  It restores the landing lines on every draw.
- Compaction never moves a die row: on every draw it leaves them at D_j's values.
- On draws 2 and 6, the search's die rows and col_PHASE_u0 equal compaction's.

**Inference.**
- The misses fall into two kinds:
  - L2 ≈ L1: draws 1, 2, 3. The search misses at L1 too, and plain L1 descent (ablation e) ends within 0.3 points of
    it.
  - L2 ≫ L1: draws 4, 7 and, in part, 0. L1 says recovered; L2 says 2–4 points above. These are the draws with a
    large residual low-side die-row offset.
- Within-shortlist re-ranking moves s by at most the span, 0.01–0.13 points (T0474 confirmed). **H1′ is refuted as a
  cause.**
- A3's paired-win misses on draws 2 and 6 have the same cause as A1's misses: there the search fixes nothing
  compaction does not, because neither restores the die rows or the coupled block.

### 3.2 T2: L1 → L2 fidelity over all 168 2R layouts (`t2_fidelity.py` → `t2_fidelity.json`)

**Fact.**
- Fit log(L2 ratio) = a·log(L1 ratio) + c: a = 0.711, c = 0.0131, residual sd 0.0164. Under this fit W* sits 1.31 %
  below the line.
- The residual correlates with the low-side die row's u offset from W* (row_LS_u0) at r = 0.90. slot1_u0 comes next
  at 0.62, because the two co-vary on draws 0 and 4. All other parameters are at |r| ≤ 0.28.
- Adding row_LS_u0 to the fit:
  - +0.48 %/mm; residual sd falls to 0.0069; R² 0.988; the intercept falls to 0.0012.
  - On one point per scored group (n = 55): 0.44 %/mm.
  - Leaving out one draw at a time: 0.41–0.49 %/mm.
  - slot1_u0 beside it: 0.03–0.09 %/mm.

**Inference.**
- L1 misses a die-row-position term of about 0.45 %/mm on top of the 0.7 scale factor. It is stable under clustering
  and under leaving out draws.
- W*'s apparent L2 advantage is this term: the residual's intercept is about 0.1 % once the term is included.

### 3.3 T3: the L1 landscape between the end point and W* (`t3_l1_paths.py`, `t3b_dierow_scans.py`)

**Fact (T3a, local optimality).**
- Improving valid single 0.5 mm moves from the returned layout: 11, 2, 1, 9, 7, 6, 2, 2 (draws 0–7), out of 36–43
  valid neighbours.
- The largest gain from one is 0.19 points (draw 0). On draws 1 and 2 the gains are under 0.01 points.

**Fact (T3b, path to W*).**
- On all 8 draws a greedy path reaches W* through valid layouts only. Its moves are unit steps toward W* or one
  parameter set to W*'s value.
- The L1 barrier along it is 0 (draws 0, 1, 3, 6), 0.0013–0.0035 (2, 5, 7) or 0.0073 (4). **There is no DRC wall.**

**Fact (T3c, coupled block; `t3_l1_paths.json` and the block check in §8).**
- On draws 2 and 3 the path's big gains come from col_PHASE_u0 −0.5 mm steps, each worth −1.7 to −2.0 L1 points.
- Each such step is valid only together with row_HS_u0 −0.5 and slot2_u1 −0.5.
- From b₂ and b₃, col_PHASE_u0 −0.5 alone, or with either partner alone, fails `in_domain` with `slot2_free_end`. The
  triple is valid: L1 1.0233 → 1.0082 (b₂) and 1.0554 → 1.0383 (b₃).
- The search's joint move draws k ∈ {2, 3, 4} parameters uniformly from the 36 movable ones, signs ±, and 1–4 steps
  each (`local._joint`). So P(this triple, all −, equal steps) ≤ (1/3)·(1/7140)·(1/8)·(4/64) ≈ 4e-7 per proposal.
  Proposals of four parameters that contain the triple add about 1e-6.
- About 480 joint proposals per search (12 per iteration, 33–40 iterations) give P ≲ 1e-3 per search. Draws 1, 2 and 3
  all hold the planted slot2_u1 offset (+3, +3, +4 mm).

**Fact (T3d, die-row scans from the end point at 4 mm).**
- The first 0.5 mm step toward W*'s die-row value raises L1 on every scanned draw with a die-row offset:
  - draw 7 row_LS_u0: 0.9987 → 1.0007;
  - draw 4 row_LS_u0: 1.0080 → 1.0093;
  - draw 1 row_HS_u0: 1.0453 → 1.0473;
  - draw 6 row_LS_u0: 1.0112 → 1.0126.
- The longer moves fall: to 0.9895, 0.9987, 1.0282 and 1.0082 at or near W*'s value.

### 3.4 T5 and T7: is the ruggedness numerical? (`t5_l1_mesh.py`, `t7_l1_cost_roughness.py`)

**Fact.** The same scans at hmax 4 / 2 / 1 mm (`physics.peec.loop_inductance`; at 4 mm it equals `twin._l1`, asserted):

| scan | first step at 4 mm | first step at 1 mm | RMS of quadratic residual, 4 / 2 / 1 mm | sign changes of the slope, 4 / 2 / 1 mm |
|---|---|---|---|---|
| W*, row_LS_u0 0 → +6 | — | — | 0.081 / 0.028 / 0.012 % | 5 / 0 / 0 |
| draw 7, row_LS_u0 | +0.0020 | −0.0012 | 0.077 / 0.037 / 0.022 % | 5 / 3 / 1 |
| draw 4, row_LS_u0 | +0.0013 | −0.0020 | 0.094 / 0.029 / 0.003 % | 2 / 0 / 0 |
| draw 1, row_HS_u0 | +0.0020 | −0.0017 | 0.081 / 0.021 / 0.008 % | 2 / 0 / 0 |
| draw 6, row_LS_u0 | +0.0014 | −0.0006 | 0.071 / 0.031 / 0.011 % | 3 / 3 / 1 |

- The L1 cost of the die-row offset itself does not depend on the mesh: W* with row_LS_u0 +6 mm reads 1.0108 / 1.0110
  / 1.0113 at 4 / 2 / 1 mm.
- Measured time per L1 evaluation on the twin (T7):
  - 2R: 14 / 42 / 387 ms;
  - Case 4: 29 / 131 / 3540 ms.

**Inference.**
- The dents are discretisation noise of the 4 mm screen. The trace mesh conforms to the die-footprint edges, so it
  changes when a die row moves.
- The search's end points sit at the bottom of dents along die-row coordinates. Its 0.5 mm single steps cannot leave
  them, because the dent depth (0.1–0.2 %) exceeds L1's true slope per step (about 0.1 %).
- At 2 mm the noise is 3–4 times smaller, at 3 times the cost. At 1 mm it nearly vanishes, but Case 4 then costs 3.5 s
  per evaluation.

### 3.5 T4: counterfactual L2 solves at 0.5 mm (`t4_l2_local.py` → `t4_l2_local.json`)

**Fact.** Local l2_layout at lat0.5 runs through E010's child, in the burst's job format. Ratios are to the local W*
solve. Every case is valid.

| case | what | L1 4 mm | L1 1 mm | L2 0.5 mm |
|---|---|---|---|---|
| A1 | draw 7's end point b₇ (burst: 1.0338) | 0.9987 | 1.0038 | 1.0338 |
| B1 | W* with row_LS_u0 +6 mm | 1.0108 | 1.0113 | **1.0431** |
| B2 | W* with row_LS_u0 +3 mm | 1.0057 | 1.0044 | 1.0188 |
| B3 | b₇ with row_LS_u0 at W*'s value | 0.9895 | 0.9930 | **0.9912** |
| B4 | b₄ with slot1_u0 and row_LS_u0 at W*'s | 0.9877 | 0.9847 | **0.9865** |
| B4b | b₄ with slot1_u0 at W*'s only | 1.0080 | 1.0073 | 1.0412 |
| B5 | W* with slot1_u0 +3 mm | 1.0000 | 1.0000 | 1.0040 |
| C1 | b₂ with the triple −0.5 mm | 1.0082 | 1.0092 | 1.0112 |
| C2 | b₂ with the triple −1.0 mm | 0.9932 | 0.9938 | **0.9979** |
| C3 | b₃ with the triple −0.5 mm | 1.0383 | 1.0384 | 1.0342 |
| C4 | b₃ with the triple −2.0 mm | 0.9916 | 0.9893 | **0.9929** |
| D1 | b₁ with row_HS_u0, row_LS_u0 and row_LS_gap at W*'s | 1.0271 | 1.0293 | 1.0185 |
| D2 | D1, then col_PHASE_u0 and slot2_u1 −1 mm | 0.9923 | 0.9931 | **0.9919** |
| E0 | b₀ with slot1_u0 and row_LS_u0 at W*'s | 1.0059 | 1.0063 | **0.9963** |

**Inference.**
- On every failed draw (0, 1, 2, 3, 4, 7), one or two structured moves from the returned layout lower L2 at 0.5 mm by
  2.6 to 5.6 points, to 0.987–0.998 of W*:
  - die-row line moves: draws 0, 4 and 7 (E0, B4, B3);
  - the die rows plus the coupled pair: draw 1 (D2);
  - the coupled triple: draws 2 and 3 (C2, C4).
- The frozen 4 mm L1 also rates each of these moves as improving. **L1 and L2 agree on the direction**, so H1 as
  stated (an L1 optimum misordered by L2) is not what stops the search.
- L2 prices row_LS_u0 at about 0.63–0.72 %/mm (B2, B1); L1 prices it at 0.15–0.19 %/mm. That is a factor of about 4,
  or about 5.5 after the global 0.71 slope. slot1_u0 is not the cause (B4b: no change; B5: 0.13 %/mm).

### 3.6 T6: one-at-a-time sensitivity at W* (`t6_sensitivity.py` → `t6_sensitivity.json`)

**Fact.**
- 35 valid one-at-a-time moves at W* over 27 parameters, each the largest valid move of at most 2 mm.
- L2 against L1, as log ratios through the origin: slope 0.716 (1 mm L1) and 0.712 (4 mm L1); residual sd 0.24 %;
  Pearson 0.98.
- The largest residuals are on die-row and landing parameters:

| move | L1 4 mm / 1 mm | L2 |
|---|---|---|
| row_LS_u0 +2 mm | 1.0049 / 1.0025 | 1.0115 (+0.96 % over the fit) |
| row_HS_u0 −2 mm | 1.0071 / 1.0069 | 0.9989 (−0.61 %) |
| row_LS_u0 −2 mm | 0.9978 / 1.0023 | 0.9963 (−0.53 %) |
| land_LS −2 mm | 1.0405 / 1.0419 | 1.0247 (−0.50 %) |

- Column and slot moves follow the 0.71 slope within 0.36 %. slot1_u0 +2 mm reads L1 1.0000 and L2 1.0018.

**Inference.**
- L1's L2-relevant error is concentrated on the die-row coordinates. It is a scale factor on everything else.
- At W* itself L1 and L2 disagree on the sign along row_HS_u0 and, at 1 mm, row_LS_u0: L2 would move both rows −2 mm
  for a 0.1–0.4 % gain. So W* is an L1 optimum but not an L2 optimum along the die rows.
- That does not explain the misses, which are 2–5 points in the other direction (T4). It does bound how far below W*
  an L2-aware search could go on these coordinates (about 0.4 %).
- **H4 holds in this narrow form:** the parameters whose L2 effect L1 misjudges are the die rows, which the degradation
  moves (+7.5 and +7 mm row_LS_u0 on draws 4 and 7).

### 3.7 H3 (selection)

**Fact.**
- L2(W)/L2(W*) = 1.0666 at 0.25 mm (`dev_rows.json`, per_layout).
- The W* solve is deterministic across machines to 7e-15 (A0). Its GMRES tolerance is 1.85e-5.
- The search's band b on 2R is 0.0004–0.0061.
- W*'s −1.31 % residual in T2's plain fit falls to about −0.12 % once row_LS_u0 is in the fit.

**Inference.**
- A choice between two values 6.7 % apart carries no winner's curse at any error level seen here.
- The shared W* error is bounded by b (at most 0.6 points) and is far smaller than the 0.2–3 point misses.
- **H3 is refuted as a material cause.** It cannot move any 2R draw across the line except draw 0, whose s is 0.022.

## 4. Per-draw attribution and counts

| draw | s | kind | mechanism (test) |
|---|---|---|---|
| 0 | 0.022 | L2 ≫ L1, small | low-side die row +3.5 mm left in a dent, plus budget (T2, T3a, E0) |
| 1* | 0.044 | L2 ≈ L1 | die rows in dents (D1), plus the coupled block, partly (D2) |
| 2 | 0.025 | L2 ≈ L1 | coupled block (C1, C2) |
| 3 | 0.050 | L2 ≈ L1 | coupled block (C3, C4) |
| 4 | 0.042 | L2 ≫ L1 | low-side die row +6.5 mm, in a dent, priced 4× higher at L2 (B4) |
| 7 | 0.034 | L2 ≫ L1 | low-side die row +6 mm, likewise (B3) |
| 5, 6 | pass | — | the residual die-row offset is −1 mm and +2 mm |

Counts:
- All 8 draws: 6 misses. 2 are coupled-block (2, 3), 3 are die-row/fidelity (0, 4, 7) and 1 is mixed (1).
- Without draw 1: 5 misses of 7, with 2 coupled-block and 3 die-row.

## 5. Ranking, class and confidence

1. **H2, reach, through H2a (coupled DRC move) and H2b (rugged 4 mm screen). Rank 1.**
   - It explains all six misses' immediate cause: a valid improving structured move exists from every failed end point
     (T3, T4), and the search's move set does not take it.
   - **H2c (budget alone) is a minor factor.** On draws 1, 2, 5 and 6, plain descent ends at a local optimum at the
     same L1 levels. The improving single moves left on draws 0, 3 and 4 are worth at most 0.19 points.
2. **H4 / H1 as an amplifier. Rank 2.**
   - L1 under-weights the low-side die row's position about 4-fold (T2, B1, B2).
   - This turns the die-row offsets the trapped search leaves into misses of 2–4 points that L1 does not show, and
     makes the L1 indicator overstate the search (5 of 8 against 2 of 8).
   - The degradation does plant such offsets: +7.5 and +7 mm on draws 4 and 7.
   - It does not misdirect the search: L1's gradient has the right sign along that coordinate (T5).
3. **H1′, within-shortlist misranking. Refuted** (span ≤ 0.13 points).
4. **H3, selection. Refuted** as material (§3.7).

**Class: model**, confidence 0.75. It is the search method's assumption that a 0.5 mm single-step descent with random
joint moves suffices on the frozen L1, plus L1's die-row sensitivity. The signature is a systematic error tied to a
physical variable (die-row position) that survives verified code and a validated reference (local and burst agree
bit for bit).

It is not implementation: the search does what its docstring says, and the five code hashes match the stamp. It is not
experimental: the control answered its question. It is not planning or business.

**Speculation.** L1 treats each die footprint as one equipotential node and the die as an ideal short (model
docstring, `physics/peec/model.py`). L2 resolves the current under and around the footprint at 0.5 mm. That is one
candidate for the missing die-position term. I did not test it.

## 6. Finding for the founder: is the 2 % line resolvable on 2R?

**Inference, from T2, T4, T5 and T7.**
- L2 prices a low-side die-row offset at about 0.7 %/mm. A residual offset of 2.8 mm therefore uses the whole 2 %
  tolerance, while the frozen 4 mm L1 shows it as about 0.5 %.
- The 4 mm screen's noise is 0.07–0.09 % RMS, with dents up to 0.4 %. That equals L1's signal for a die-row error of
  0.5–2 mm, which L2 prices at 0.35–1.4 points.
- **So with the frozen screen, the 2 % line on 2R lies at the screen's resolution along this coordinate, and the frozen
  search does not resolve it.**
- At 2 mm the noise is 0.02–0.04 %, so L1 resolves the coordinate's sign. There the line is not shown to lie below
  what an L1-guided search can resolve, but the margin is thin.
- I do not design around this. The redesign below keeps the 2 % line, the 7 of 8 and A3. If its development rows show
  the L1 indicator at 7 of 8 or more but L2 below 7 of 8, with residual die-row offsets above about 2.5 mm, the line is
  below L1-guided search's resolution on 2R. Per decision_if_fail, that should stop the work.

## 7. Redesign proposal (one to choose; none carried out)

Each option is a search change. decision_if_inconclusive's "degradation family or proxy rule, not the search" applies
only when A1 is met, and here A1 fails.

I considered a degradation-family change and rejected it, for example one that plants smaller die-row offsets. It
would make 2R easier without making the search better, which is designing around the finding. scope_in also requires
the same parameter set throughout.

Every option needs:
- a new experiment id;
- a new development seed: these 16 draws are now tuning data;
- new development rows.

No option changes the objective's thresholds.

### Option A (recommended): structured moves and a 2 mm screen

- **What changes (search).**
  1. **Line moves** for the six die-row parameters: n = 2, 4, 8 and 16 grid steps each way, offered every iteration
     (48 more candidates). When the search is stuck, every movable parameter is line-searched before the random
     perturbation.
  2. **Coupled moves.** A ±0.5 mm single move that `in_domain` rejects for a slot free-end or die-row rule is retried
     with the parameters that rule binds moved by the same step (the T3c triple is one instance).
  3. **The L1 screen at hmax 2 mm** in every E011 use of L1: proxy descent, degradation, search, ablations (c) and (e).
     W* therefore stays an optimum of the search's own screen, as scope_in requires.
- **Frozen values that change. Each is a founder decision; I change none.**
  - `frozen.search`, `search_cfg_hash` and `code_sha256` of local.py (the move set; the budget of 2000 L1 evaluations
    stays, or the founder resets it after the L1 stage's improvement curve);
  - `frozen.proxy.rule`: `twin._l1` becomes the 2 mm screen, so W* is re-derived and `choose_proxy` reruns at 0.25 mm;
  - `frozen.degradation`: the L1 target 1.3875 must be re-aimed under the new screen (decision 2 of the analysis note
    again);
  - `frozen.ablation_c` and `frozen.ablation_e` (same screen);
  - the dev seed.
- **Development rows and compute.**
  1. **L1 stage, local and checkpointed.** The last one took 1.98 h at 4 mm (`e011-dev-run.md` §1). At 2 mm, 3–4.5×
     the evaluation cost gives about 6–9 h. No VM.
  2. **Go/no-go, local, no VM.** Solve all 2R shortlists and end points at 0.5 mm: about 160 solves at about 80 CPU-s,
     so about 3.6 CPU-h, about 2 h wall at 2 at once, peak 1.8 GB each.
     - s at 0.5 mm tracks s at 0.25 mm within about 0.25 points (q spread, analysis note §4).
     - Stop here, before any VM, if 2R passes fewer than 7 of 8 draws at 0.5 mm, or if a search best's paired margin
       over compaction falls short on more than one draw.
  3. **Development burst** of the same structure as the last: about 611 jobs plus wave 2. The last cost $40 and took
     61–72 h on n2d-custom-8, or about 35 h on 16 vCPUs at about the same cost.
- **What would show it failed on the development rows (any one):**
  - 2R passes fewer than 7 of 8 at 0.25 mm;
  - Case 4 passes fewer than 7 of 8;
  - A3 = 0 on either layout;
  - K1 fires.
  - The diagnostic split: if the L1 indicator is at 7 of 8 or more but L2 below 7 of 8, with residual row_LS_u0 offsets
    above about 2.5 mm, the fidelity limit of §6 binds.

### Option A′: structured moves only, frozen 4 mm screen

- **What changes:** items 1 and 2 of option A only.
- **Frozen values:** `frozen.search`, `search_cfg_hash`, local.py's hash and the dev seed.
  - W* stays (no new proxy solves).
  - The degradation family and its target stay.
- **Compute:** L1 stage about 2–3 h local; the same go/no-go and burst as A.
- **Risk (inference).** A line move picks the lowest L1 point on its line. At 4 mm that point carries about 0.1–0.4 %
  of noise. At L1's 0.15–0.19 %/mm that is ±0.5–2 mm of die-row error, so up to about 1.4 points at L2: most of the
  tolerance.
  - The counterfactuals say A′ would have fixed the observed misses: B3, B4 and C2 are improving at 4 mm.
  - But the resolution floor makes a pass at 7 of 8 fragile.
- **Failure criteria:** as for A.

### Option B: a multi-fidelity search (L2-guided refinement)

- **What changes:** after the frozen L1 search, a fixed-budget L2 refinement at 0.5 mm. It is a coordinate descent over
  the die rows and the coupled moves with l2_layout at lat0.5, N₂ = 40 solves per draw, followed by the 0.25 mm
  shortlist as now. It removes the amplifier, not just the traps.
- **Frozen values:** `frozen.search` plus a new `frozen.refine` block.
- **Objective text.** The hypothesis describes the search as "L1 screen; l2_layout at 0.25 mm on a fixed shortlist".
  An L2-guided step changes that description, which only the founder can amend: `affects_acceptance_criteria`, though
  no threshold changes.
- **Compute (measured walls, `dev_rows.json` measured_sizing):**
  - 2R lat0.5 median 196 s, so 40 × 196 s ≈ 2.2 solve-h per draw;
  - Case 4 lat0.5 median 541 s, so ≈ 6.0 solve-h per draw;
  - development rows about 66 solve-h extra, about 17 h at 4 at once on n2d-custom-8, about $10–12 above the $40
    burst;
  - the registered run about the same again.
  - 2R's refinement can run locally (about 1 CPU-min per solve here). Case 4's would need about 4.5 GB per solve and
    about 3 min each.
- **Failure criteria:** as for A. Signature: if refinement passes 2R and Case 4 fails, the cost moves to Case 4.

**Recommendation: option A.**
- It removes both mechanisms that trap the search (T3, T5).
- It lowers the screen noise that would otherwise put a floor of up to about 1.4 points under the result (§6).
- It costs about $40 of VM, the same as the last development round, and leaves the objective's text alone.
- It has a local 0.5 mm go/no-go on 2R that can stop it before any VM spend.
- B is the stronger fix for the amplifier, but it needs an objective-text amendment. Keep it as the fallback the
  founder may prefer, if he wants the die-row blind spot priced at L2 inside the search.

## 8. Commands run (exit codes)

All from the worktree root, `uv run --quiet python research/o008_e011_diag/<script>`:

| command | exit |
|---|---|
| `t1_assemble.py` | 0 |
| `t2_fidelity.py` | 0 |
| `t3_l1_paths.py` (94 s) | 0 |
| `t3b_dierow_scans.py` | 0 |
| `t5_l1_mesh.py` | 0 |
| `t7_l1_cost_roughness.py` | 0 |
| `t4_l2_local.py --plan` | 0 |
| `t4_l2_local.py --only A0_Wstar --jobs 1` | 0 |
| `t4_l2_local.py --jobs 2` (twice: 11 cases, then 3 more) | 0 |
| `t6_sensitivity.py --plan` | 0 |
| `t6_sensitivity.py --jobs 2` | 0 |

Two ad-hoc probes in `$TMPDIR`, not kept: the parameter list and timing, and the coupled-block check of §3.3. Their
results are reproduced by `t3_l1_paths.py` / `t4_l2_local.py` case C1 and by the validity column of
`t4_l2_local.json`.

## 9. What would show this diagnosis wrong

- **A redesigned search that takes these structured moves still misses at L2 on fresh development draws.** If it
  reaches W*'s L1 level and the misses track something other than die-row offsets, a third mechanism exists that these
  8 draws did not show. The counterfactuals are single moves from the end points, not full searches. A search that
  makes them may meet new traps.
- **0.5 mm against 0.25 mm.** If 0.25 mm solves of the six counterfactuals (E0, D2, C2, C4, B4, B3) and of W* do not
  reproduce their 0.5 mm ratios within about 0.3 points. The q spread on 2R is 0.25 %.
  - Job list: those 7 fingerprints in `t4_l2_local.json` at lat0.25, plus the four other band levels if a band is
    wanted.
  - Cost: 7 × 925 s (measured median) ≈ 1.8 solve-h, under 1 h wall at 4 at once on n2d-custom-8, about $1. 2R at
    0.25 mm peaks at 6.4 GB, so it could also run locally under the 10 GB single-process rule, but this packet allows no
    0.25 mm solves.
  - Not run.
- **The die-row term is specific to these geometries.** If T2's row_LS_u0 term vanished on a fresh development seed,
  the amplifier would be an accident of these 8 draws. The mechanism ranking, H2 first, would not change.
- **Eight draws.** Draws 2 and 3 share a planted slot2_u1 offset. A different seed may plant other coupled blocks that
  option A's coupled-move rule does not cover. The go/no-go is meant to catch that cheaply.

## Sources

- **Committed inputs:**
  - `experiments/drafts/E011.dev_jobs.json` (parameter vectors and purposes);
  - `research/o008_e011_dev/dev_l2/` (`dev_rows.json`, `solves/`, `code_stamp.json`);
  - `research/notes/e011-dev-l2-analysis.md`;
  - `research/notes/e011-dev-run.md`;
  - `research/notes/o008-control-probe.md`.
- **Outputs of this task:** `research/o008_e011_diag/*.json` and `research/o008_e011_diag/l2/solves/*.json`, with
  layouts in `l2/lay/`.
- **Code read, not changed:**
  - `src/moduleforge/optimize/local.py` (move set, `_joint`);
  - `src/moduleforge/optimize/control.py` (degradation);
  - `src/moduleforge/optimize/nulls.py`;
  - `src/moduleforge/physics/peec/model.py` (L1's mesh and die model);
  - `experiments/runners/e011_run.py` and `experiments/runners/e010_run.py` (the child solve).
