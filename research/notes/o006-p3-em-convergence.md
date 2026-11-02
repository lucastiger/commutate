# O006 pilot P3: l2_layout discretisation on PowerSynth 2D_Case_4 and two perturbations
Date: 2026-11-01 · Task: T0154 (scientist, investigate) · Objective: O006 (pilot P3, input to D0009's day-60 band) ·
Confidence: medium on the measured numbers, low on the absolute band (only two lateral levels ran)

**This is a research note, not evidence.** O006 F4: 2D_Case_4 and its two perturbations are pilot geometry, excluded from
O003's and O004's judged sets. Nothing here was produced through `mfos.evidence.ExperimentRun`.

Files: `research/scripts/o006_case4_layout.py` (geometry, `--check`), `research/scripts/o006_p3_em_convergence.py`
(levels, solves, estimators, `--assemble`), `research/o006_p3/results.json` (machine-readable results),
`research/o006_p3/tables.md` (generated tables; all numbers below are copied from it), `research/o006_p3/solves/*.json`
(one record per solve, with provenance).

## Answer (≤ 5 sentences)
Only the 1.0 mm (supplementary) and 0.5 mm lateral levels fit on this 16 GB Mac. The 0.25 mm level needs about 16 GB and
the 0.125 mm level 21–85 GB (projected), and agents may not launch burst VMs. So the observed order of the requested
0.5 / 0.25 / 0.125 mm ladder is **not observed**, and every lateral term below is a two-level (1.0 / 0.5 mm) estimate.
At 0.5 mm, L(base) = 22.961 nH at 10 MHz and 22.817 nH at 20 MHz. The frozen absolute discretisation estimate is
1.75 nH (7.6 %) at 10 MHz and 1.81 nH (7.9 %) at 20 MHz. It is dominated by the lateral term, 3 × the −2.15 % change from
1.0 to 0.5 mm. The thickness term is 0.02 nH (observed order about 4). The filament term is 0.22–0.27 nH, but a post hoc
diagnostic shows it is an artefact of refining the wire annuli radially only: with 12 filaments per ring, L is within
0.008 % of production, and the estimate drops to 1.54 nH (6.7 %). The pair ratios cancel most of the error. The frozen
ratio estimates are 1.7–1.8e-3 for the 1 mm die shift (an effect of 1 − R = 1.36 %) and 0.9–1.1e-3 for the 2 mm
trace-width change (1 − R = 3.09 %); post hoc they are 1.5e-3 and 0.5–0.8e-3. These ratio estimates are D0009's relevant
input, but they rest on two lateral levels including the coarse 1.0 mm one, and they should be confirmed at
0.25 / 0.125 mm on a burst VM before 2026-11-27.

## 1. Provenance and geometry (D0007)
- Source: e3da/PowerSynth2-pkg, commit `a1de7ced949c0fd0105d166767b1de8705eb65ab` (2025-06-17, "v2.2 stable release"),
  `work/Sample_Designs/2D_Case_4`, GPL-3.0. Twelve files were downloaded to a temporary directory outside the repository
  and read there. Their sha256 values are in `results.json` (`sources_sha256`) and in `o006_case4_layout.SOURCES_SHA256`.
  `--check --sources DIR` re-hashes them, and did so on 2026-11-01 (exit 0). No GPL file was committed, copied or imported.
  The layout script contains only numbers transcribed by hand.
- Facts used: the layer stack (baseplate Cu 80 × 110 × 1.0 mm; bottom Cu 70 × 100 × 0.2; AlN 0.835; top Cu 0.2; device
  layer 0.18), the trace rectangles, the die and lead positions, the bond points and the wire table. All are listed with
  their source file in the script's docstring.
- Inferences:
  - (a) Coordinates are absolute in the baseplate frame. The axes of `Figs/initial_layout_I1.png` span the 70 × 100 mm
    substrate at (5, 5).
  - (b) Net roles. Island T6 ∪ T10 carries the D3/D4 drains and lead L3, so it is DC+. Island T3 ∪ T11 ∪ T5 carries the
    D1/D2 drains and receives the D3/D4 source wires, so it is PHASE. Island T4 ∪ T9 receives the D1/D2 source wires, so it
    is DC−.
  - (c) The ModuleForge port is the commutation loop L3 → D3/D4 → BW5/BW6 → PHASE → D1/D2 → BW3/BW4 → L2. PowerSynth's
    own macro measure (L4 → L2, 1 MHz) is a different loop. Case 4 has no published value.
- Modelling choices M1–M7 (script docstring), stated rather than taken from the source:
  - Gate wires and Kelvin-source wires are omitted. The ideal-short die would join them to the power path.
  - Signal traces are kept as floating copper.
  - Loop height is assumed to be 1.0 mm. The JEDEC 4-point height is not in the files read.
  - A 1 µm solder layer is added because `LayerStack` requires one; it is not a conductor in the model.
  - Die attach is 0, backside inset is 0, and leads are not modelled.
- Perturbations, frozen in the script before the first solve. Both keep the 1 mm spacing and enclosure rules of
  `constraint.csv` and stay on the 1.0 / 0.5 / 0.25 / 0.125 mm lattices.
  - `die_shift`: high-side dies D3 and D4, with their source-wire starts, move −1.0 mm in y. BW5/BW6 shorten from 16.15
    to 15.16 mm.
  - `trace_width`: the DC− trace T4 widens from 5 to 7 mm (lower edge y 45 → 43 mm; +64 mm² of copper).
- `--check` verifies:
  - three distinct fingerprints;
  - inter-net spacing and die enclosure;
  - every wire starts on a die source pad and lands on the correct commutation-loop net;
  - terminals sit on their traces;
  - each perturbation changes exactly what it documents;
  - the transcribed island areas;
  - the geometry is on all four lattices, with represented area within 1.03e-15 of the copper area;
  - no PowerSynth file name appears under `research/`.

## 2. Levels: exactly what is refined, and by what ratio
Every solve is `solvers.l2_layout.loop_inductance(layout, [10 MHz, 20 MHz], refinement=0)` in a fresh process. The
refinement-0 entries of the module constants `CELL`, `LAYERS_TOP/BACK/BASE`, `WIRE_EDGES` (and `WIRE_PHI` for one diagnostic)
are overridden in that process. This is the mechanism of `research/scripts/l2_layout_lateral_diag.py`; `src/` is unchanged.
All solves report tool_version 0.3.0 and source_sha256 `ed0288b6…58a8e`. Thickness layers are graded to the skin depth at
F_MESH = 100 MHz at every level (first layer = min(0.5 δ, uniform)), so both frequencies come from one mesh.

| level | lateral cell | layers top/back/base | wire annulus edges (× r) | filaments/wire | refines |
|---|---|---|---|---|---|
| lat1.0 | 1.0 mm | 10/6/6 | E0 | 25 | supplementary (all Case 4 features lie on 1 mm) |
| lat0.5 | 0.5 mm | 10/6/6 | E0 | 25 | production refinement 0 |
| lat0.25 | 0.25 mm | 10/6/6 | E0 | 25 | production refinement 1 (K_STAR, O003's level): **not run** |
| lat0.125 | 0.125 mm | 10/6/6 | E0 | 25 | production refinement 2: **not run** |
| thk_c | 0.5 mm | 5/3/3 | E0 | 25 | layer counts × 1/2 |
| thk_f | 0.5 mm | 20/12/12 | E0 | 25 | layer counts × 2 |
| fil_f | 0.5 mm | 10/6/6 | E1 | 55 | every annulus bisected radially (radial width ratio 2), 6 per ring |
| fil_f_phi12 | 0.5 mm | 10/6/6 | E1 | 109 | E1 with 12 per ring: **post hoc diagnostic** (added after fil_f was seen; not in the estimators) |

E0 = (0, .35, .6, .8, .93, 1) (production); E1 = (0, .175, .35, .475, .6, .7, .8, .865, .93, .965, 1).

- Lateral refinement ratio: 2.
- Thickness: the layer count changes by 2 per step. Because of the grading rule this is not a uniform halving of every
  layer.
- Filaments: the radial annulus width changes by 2 per step.

## 3. Estimators
Fixed in the runner's docstring before the first solve. Roache's GCI with the safety factors of Roache, *Verification and
Validation in Computational Science and Engineering* (1998), ch. 5: Fs = 1.25 with three grids, 3 with two.

- **Three levels**, constant ratio r = 2, f1 the finest level, e21 = f2 − f1, e32 = f3 − f2. The sequence is monotone iff
  e21·e32 > 0 and |e21| < |e32|.
  - If monotone: p_obs = ln(e32/e21)/ln r, the extrapolated value is f1 + (f1 − f2)/(r^p − 1), and
    GCI = 1.25 |e21|/(r^p − 1).
  - Otherwise: GCI = 3 max(|e21|, |e32|), and there is no extrapolation.
- **Two levels**: GCI = 3 |f2 − f1|/(r − 1). This is Fs = 3 with an assumed order 1.
- **Thickness term**: production (10/6/6) is the middle of the three thickness levels, so the term estimates the error of
  the middle value.
  - If monotone: 1.25 |e21| r^p/(r^p − 1).
  - Otherwise: 3 max(|e21|, |e32|).
- **Filament term**: 3 |L(E1) − L(E0)|.
- **Total**: abs_est = GCI_lateral + thickness term + filament term. This is a linear sum, which is conservative.
- **Pair ratio** R = L_pert/L_base per level: the same formulas, applied to R.

**Deviations, made after the 0.5 mm results were known (stated so a reader can discount them):**
1. The frozen rule took the lateral term from the requested ladder. With only one requested level run, it falls back to
   the two-level formula on the finest two consecutive levels of the nested ladder 1.0 / 0.5 / 0.25 / 0.125 mm, i.e.
   1.0 / 0.5 mm. The formula is unchanged; only the levels it uses changed.
2. `L_extrap_H` should be null for two levels. It is instead filled with a two-level Richardson value at an **assumed**
   order p = 0.72, labelled as assumed (`L_extrap_kind`). The order is the median observed lateral order of l2_layout on the
   six earlier aligned generator ladders at 0.5 / 0.25 / 0.125 mm and 20 MHz (`research/l2_layout_vm`, `l2_layout_vm2`,
   `l2_layout_diag`): 0.685, 0.713, 0.716, 0.729, 0.789, 0.803. Those data predate this task and are not Case 4.
   Extrapolations at p = 1 and p = 2 are reported beside it. `p_obs` stays null.
3. The level `fil_f_phi12` was added (§5.3).

## 4. Results (from `research/o006_p3/tables.md`)
L in nH at 10 / 20 MHz. Wall times on this Mac; those of thk_f and later were inflated by swapping. Solver health:
- every GMRES flag is 0;
- 120–229 iterations;
- max solver_tol relative to L is 3.2e-5, negligible against every term below.

| level | case4_base | case4_die_shift | case4_trace_width |
|---|---|---|---|
| lat1.0 | 23.4659 / 23.3234 (57 s, 1.8 GB) | 23.1595 / 23.0201 | 22.7400 / 22.5998 |
| lat0.5 | 22.9609 / 22.8174 (206 s, 3.9 GB, 1.02 M unknowns) | 22.6497 / 22.5093 | 22.2523 / 22.1110 |
| thk_c | 23.2346 / 23.0108 | 22.9223 / 22.7020 | 22.5132 / 22.2960 |
| thk_f | 22.9444 / 22.8020 (856 s, 8.1 GB) | 22.6331 / 22.4939 | 22.2357 / 22.0955 |
| fil_f | 23.0336 / 22.9065 | 22.7198 / 22.5952 | 22.3250 / 22.2001 |
| fil_f_phi12 (post hoc) | 22.9592 / 22.8188 (850 s, 4.5 GB) | 22.6480 / 22.5105 | 22.2506 / 22.1124 |

Absolute estimate for case4_base:
- **10 MHz**:
  - lateral two-level 1.515 nH (the 1.0 → 0.5 mm change is −0.505 nH, −2.15 %);
  - thickness term 0.022 nH (p_thk = 4.05);
  - filament term 0.218 nH (fil_f − lat0.5 = +0.073 nH, +0.32 %);
  - **abs_est = 1.755 nH (7.6 % of L(0.5 mm))**.
- **20 MHz**:
  - lateral 1.518 nH;
  - thickness 0.021 nH (p_thk = 3.65);
  - filament 0.267 nH (+0.39 %);
  - **abs_est = 1.806 nH (7.9 %)**.
- L_extrap (assumed p = 0.72): 22.18 nH at 10 MHz and 22.04 nH at 20 MHz. At p = 1: 22.46 / 22.31 nH. At p = 2:
  22.79 / 22.65 nH.
- The perturbed geometries give the same picture:
  - lateral term 1.46–1.53 nH;
  - abs_est 1.70–1.81 nH (7.6–8.1 %);
  - post hoc 1.49–1.56 nH.
- Post hoc alternative, with the filament term taken from fil_f_phi12 (3 × |−0.0017| / |+0.0014| nH):
  abs_est = 1.542 nH (6.7 %) at 10 MHz and 1.543 nH (6.8 %) at 20 MHz. Field: `abs_est_posthoc_phi12_H`.

Pair ratios L_pert/L_base:

| pert | f | lat1.0 | lat0.5 | thk_c | thk_f | fil_f | lateral GCI | thk term | fil term | ratio_est (frozen) |
|---|---|---|---|---|---|---|---|---|---|---|
| die_shift | 10 MHz | 0.986943 | 0.986445 | 0.986560 | 0.986433 | 0.986376 | 1.50e-3 | 1.7e-5 (monotone) | 2.07e-4 | **1.72e-3** |
| die_shift | 20 MHz | 0.986996 | 0.986498 | 0.986580 | 0.986486 | 0.986411 | 1.49e-3 | 1.8e-5 (monotone) | 2.62e-4 | **1.77e-3** |
| trace_width | 10 MHz | 0.969067 | 0.969138 | 0.968950 | 0.969111 | 0.969236 | 2.1e-4 | 5.65e-4 (oscillatory) | 2.95e-4 | **1.07e-3** |
| trace_width | 20 MHz | 0.968974 | 0.969040 | 0.968935 | 0.969014 | 0.969163 | 2.0e-4 | 3.16e-4 (oscillatory) | 3.68e-4 | **0.88e-3** |

## 5. Competing explanations and discriminating tests (skill mf-diagnosis)
**5.1 Which discretisation parameter dominates the error on Case 4?**
- H1, lateral cell: predicts that the 1.0 → 0.5 mm change is much larger than the thickness and filament changes.
- H2, thickness layers: predicts a large thk_f − lat0.5 change.
- H3, wire filaments: predicts a large fil_f − lat0.5 change. This is plausible here because each die has a single
  0.3 mm wire, so the wires carry a large share of L.

Test: all three were run at 0.5 mm.
- Lateral: −2.15 % for one halving.
- Thickness: −0.07 % for doubling 10/6/6 (the step 5/3/3 → 10/6/6 was −1.19 %). The convergence is monotone with order
  about 4, so production 10/6/6 is resolved to about 0.1 %.
- Filaments: +0.32 % / +0.39 %.

**H1 holds** (fact, at the levels run). What would prove it wrong: a 0.25 mm change comparable to or smaller than the
filament change. The prior ladders predict −1.3 % for 0.5 → 0.25 mm (an inference: −2.15 % × 2^−0.72).

**5.2 Is the 0.5 mm level in the asymptotic range?**
- Ha: yes, with the order seen on generator layouts (0.69–0.80).
- Hb: no. At 1.0 mm the 2 mm trace gaps are only two cells and the PFFT near zone (18 cells) spans 18 mm, so the 1.0 mm
  level may be pre-asymptotic and the two-level estimate could be wrong in either direction.

Test: only a third level (0.25 mm) discriminates between them. It was not run. **Unresolved.** If the true order were
below 0.42, the two-level Fs = 3 estimate would not bound the remaining error: 3|Δ| < |Δ|/(2^p − 1) when p < 0.415.

**5.3 Why does filament refinement raise L by 0.3–0.4 %?**
The earlier generator study added one annulus and found +0.017 % (`research/l2_layout_vm/solve_s7_d2_r1_wires_finer.json`).
- Fa: the 25-filament wire under-resolves the 19 µm skin depth of Al at 20 MHz. This is a genuine discretisation error.
  The skin depth δ = (π f µ0 σ)^−1/2 with σ = 3.5e7 S/m is 19 µm (Ramo, Whinnery & Van Duzer, *Fields and Waves*, eq. 4.5).
- Fb: radial-only bisection with WIRE_PHI fixed at 6 makes each outer ring six thin rods with angular gaps (equivalent
  radius 0.105 r in the outermost ring). The path does not converge to the solid wire, and the shift is partly an artefact
  of representing sectors as round rods.

Discriminating test: `fil_f_phi12`, the same annuli with 12 filaments per ring, which roughly keeps the sector aspect ratio.
- Under Fa, fil_f_phi12 stays near fil_f.
- Under Fb, it moves back toward lat0.5.

Result: L(fil_f_phi12) − L(lat0.5), base / die_shift / trace_width:
- 10 MHz: −0.0017 / −0.0017 / −0.0017 nH (−0.007 %).
- 20 MHz: +0.0014 / +0.0012 / +0.0014 nH.

The fil_f shifts were +0.07–0.09 nH. **Fb holds** (fact, at 0.5 mm): radial-only bisection with 6 filaments per ring is
not a convergent path. On the aspect-keeping path, the production 25-filament wire is converged to ≤ 0.01 % (inference
from two points on that path). The frozen filament term (3 × |fil_f − lat0.5|) stays the reported `abs_est`. It
overstates the filament error by about 40× and is kept only because it was fixed before the result was seen. What would
prove Fb wrong: a further aspect-keeping step (for example E1 with 24 per ring) that moves L by more than 0.05 %.

**5.4 Do discretisation errors cancel in pair ratios?**
- Ra: the error is a smooth, geometry-insensitive multiplicative bias, so ratios cancel.
- Rb: the perturbation moves features relative to the grid, or redistributes current where the grid error is largest, so
  ratios do not cancel.

Test: the ratio change across levels compared with the L change.
- trace_width:
  - Lateral: the ratio moves +7e-5 (1.0 → 0.5 mm) while L moves −2.15 %. Cancellation is about 300×, consistent with Ra.
  - Thickness: the ratio oscillates (thk_c → lat0.5 → thk_f: +1.9e-4 then −2.7e-5 at 10 MHz), so the frozen rule applies
    3 × max, which gives 5.7e-4 / 3.2e-4.
- die_shift: the ratio moves −5.0e-4, about 40× cancellation. That is still 3.7 % of the effect itself (1 − R = 1.36 %).
- Frozen ratio_est as a share of the effect:
  - die_shift: 1.7–1.8e-3, about 13 % of 1 − R;
  - trace_width: 0.9–1.1e-3, about 3 %.
- So cancellation is strong but perturbation-dependent. The die shift shortens the wires and moves the die footprints,
  where the current density gradients are largest, so it cancels less (an inference). On L itself the relative estimate
  is 7.6 %, so working in ratios gains a factor of about 40–90 here.

## 6. Not run: levels beyond this Mac, with estimated cost
- **Measured on Case 4**: 0.5 mm uses 1.02 M unknowns and 3.9 GB in 206 s; 0.5 mm with 20/12/12 layers uses 2.04 M unknowns
  and 8.1 GB. Case 4 has about twice the unknowns of a generator layout because its 80 × 110 mm baseplate is larger than
  the generator's 86 × 56 mm.
- **0.25 mm** (3 solves): 4.08 M unknowns each.
  - Memory: 15.6–16.3 GB from Case 4's own bytes per unknown, or 6.9–26 GB across the generator-ratio methods
    (`cost_projection_not_run` in results.json).
  - Wall: 10–90 min each.
  - It does not fit beside the agents on this 16 GB Mac, which was already swapping during the 8 GB thk_f solves.
- **0.125 mm** (3 solves): 16.3 M unknowns each, 21–85 GB, 0.8–8.2 h each.
- Agents may not launch burst VMs: docs/INFRASTRUCTURE.md §8 has the founder run `scripts/burst*.sh` with the founder's
  cloud credentials, which this task was not given. These levels are therefore marked `not_run`.
- **Estimated cost**:
  - One n2-highmem-32 (256 GB) runs the three 0.25 mm solves together, then the three 0.125 mm solves two or three at a
    time. That is about 3–17 VM-hours.
  - At the documented Hetzner CCX53 rate (128 GB, €0.855/h; INFRASTRUCTURE §8), one 0.125 mm solve at a time comes to
    about €3–25.
  - The GCP price was not looked up.
- **Command for the founder** (the branch must be merged first, or `MF_REF` set to it):
  `scripts/burst_gcp.sh --cmd "uv run python research/scripts/o006_p3_em_convergence.py --run lat0.25 lat0.125 --jobs 3 && uv run python research/scripts/o006_p3_em_convergence.py --assemble" research/o006_p3`.

## 7. Conclusions, with what is fact and what is inference
- Fact:
  - On Case 4 at 0.5 mm, l2_layout's L moves by −2.15 % per lateral halving from 1.0 mm.
  - The production thickness layers are converged to about 0.1 %.
  - Radial filament bisection moves L by +0.3–0.4 %.
  - The pair ratios move by ≤ 5e-4 between 1.0 and 0.5 mm.
- Inference:
  - The absolute band at 0.5 mm is about 8 % (6.7 % post hoc). At 0.25 mm (O003's level) it would be about 4–5 %, if the
    0.5 → 0.25 change is −1.3 % as the prior order predicts and the 0.5 mm thickness and filament terms carry over:
    3 × 1.3 % + 0.1 % + (1 % frozen or 0.02 % post hoc).
  - Headroom is a ratio, so D0009's band should use the pair-ratio estimate. That estimate is O(1e-3) for small
    perturbations, but O003's re-layouts are larger than these perturbations, and ratio errors may grow with the size of
    the change.
- Speculation: the Case 4 lateral order is near the generator value (0.7). Nothing here tests that.
- Classification (mf-diagnosis): **experimental** limitation, not an implementation fault. No failure of l2_layout was seen:
  solver health is clean and every sequence is smooth. The requested ladder cannot be completed with the resources an agent
  may use. Confidence 0.6.

## 8. Recommended actions
1. Founder: run the 0.25 / 0.125 mm levels on a burst VM (command in §6) before O003's run. That gives the observed order
   for Case 4 and an observed-order Richardson estimate, and resolves 5.2.
2. O003 / D0009: use the pair-ratio estimate (headroom = 1 − L_opt/L_ref) as the discretisation part of the band. Measure
   it on perturbations as large as the actual re-layouts, not only on 1 mm moves.
3. Filament refinement: Fb holds (5.3). Future convergence studies, including E-specs for O004, should refine WIRE_PHI
   together with the radial edges. Radial-only bisection gives a spurious +0.3–0.4 % on single-wire loops. Production
   WIRE_EDGES/WIRE_PHI need no change on this evidence: they are within 0.01 % of the aspect-keeping refinement.
4. P4 (FastHenry feasibility) can reuse `o006_case4_layout.build()` as the shared geometry.

## What would change these conclusions
- An observed 0.25 mm change much smaller than 1.3 %: the band shrinks, and the order is higher than assumed.
- One much larger than 1.3 %, or a 0.125 mm sequence that oscillates: the band grows, and Hb holds.
- A further aspect-keeping filament step that moves L by more than 0.05 %: Fb is wrong, and the filament term must be
  re-estimated.
- A different reading of the PowerSynth coordinates or loop height. This changes L(Case 4), but the convergence behaviour
  should change little (an inference).
