# O003 public fallback references (D0010): frozen reconstructions of PowerSynth 2D_Case_2R and 2D_Case_6
Date: 2026-11-10 · Task: T0263 (O003; shared with O004) · Author: scientist agent · Status: reconstructions frozen; TWIN-SPACE CHECK negative

**Headline (TWIN-SPACE CHECK): both references raise `TwinError` in E008's own `prepare()`.** Under F1(a), each reference
is therefore excluded, and E008 would be **INVALID**. The founder decides before registration (§6).

Script: `research/scripts/o003_powersynth_references.py`.
- `--check`: exits 0 iff every check passes.
- `--write`: writes `research/o003/references/<ref>.json`.

Pattern: `research/scripts/o006_case4_layout.py` (D0007). No PowerSynth file is copied, committed or imported. The script
holds hand-transcribed numbers only.

Labels in this note: **[F]** fact read from a source file or measured by the frozen code; **[I]** inference;
**[M]** modelling choice (numbered as in the script's docstring).

## 1. Sources
- **[F]** Repository: e3da/PowerSynth2-pkg (GPL-3.0), commit `a1de7ced949c0fd0105d166767b1de8705eb65ab`. This is the pin
  used for Case 4.
- **[F]** Directories read: `work/Sample_Designs/2D_Case_2R` and `work/Sample_Designs/2D_Case_6`.
- **[F]** Downloaded 2026-11-10 from raw.githubusercontent.com into `$TMPDIR/ps_t0263`, outside the repository.
- **[F]** Files read per case (11): `README.txt`, `layout_geometry_script.txt`, `layer_stack.csv`, `bond_wires_setup.txt`,
  `constraint.csv`, `macro_script.txt`, `Trace_Ori.txt`, `Part_Lib/{MOSFET,power_lead,signal_lead}.part`,
  `Wire_Lib/bond_wire_info.wire`. Their sha256 values are in `SOURCES_SHA256` and in each JSON under `source.sha256`.
- **[F]** `--check --sources $TMPDIR/ps_t0263` re-hashed all 22 files: every hash matched.
- **[F]** The figures (`Figs/*.png`) were downloaded but not used. The macro variants and `output.log` were not read.
- **[F]** Publications named by the READMEs:
  - 2D_Case_2R: T. Evans et al., IEEE TPEL 34(6), 2019, pp. 5063-5078.
  - 2D_Case_6: Q. Le, I. Al Razi, Y. Peng, H. A. Mantooth, IEEE ECCE 2021, pp. 1358-1365.

## 2. Facts transcribed (mm; PowerSynth (x, y, w, h) = lower-left corner and size, baseplate frame)
The full tables are in the script docstring and in `REFS`. Summary:

| | 2D_Case_2R | 2D_Case_6 |
|---|---|---|
| baseplate / substrate | 55x60x1.0 Cu / 45x50 at (5,5) | 60x40x1.0 Cu / 50x30 at (5,5) |
| stack | Cu 0.2 / AlN 0.835 / Cu 0.2; die 0.18 | Cu 0.2 / AlN 0.64 / Cu 0.2; die 0.18 |
| DC+ | T10 (7,37,26,8), lead L5 (9,38) | T4 (7,18,26,8) ∪ T5 (27,26,6,8), L2 (28,29) |
| PHASE | T2 (7,15,30,8) ∪ T3 (37,15,10,32) ∪ T4 (7,47,40,4) (C-ring), L2 (41,31) | T1 (7,6,21,11) ∪ T2 (28,14,6,3) ∪ T3 (34,14,19,8), L1 (23,8) |
| DC- | T1 (7,7,40,6), L1 (9,8) | T6 (34,23,19,11), L3 (35,29) |
| gate copper | T5 (7,25,26,4) GATE_LS, T6 (7,31,26,4) GATE_HS | T9 (7,27,19,3) GATE_HS, T7 (29,10,24,3) GATE_LS |
| other signal copper | none | T8 (29,6,24,3), T10 (7,31,19,3): no wire, no lead |
| dies (CPM2-1200-0025B, 4x6) | LS D1 (13,16), D2 (22,16); HS D3 (19,38), D4 (27,38) | HS D1 (12,19), D2 (18,19); LS D3 (39,15), D4 (45,15) |
| power wires | 1 per die, Ø 0.30, 0.25 mm points | 2 per die "2 0.5", Ø 0.30, 1x1 mm points |
| gate wires | 4, Ø 0.30 (Wire1) | 4, Ø 0.30 (Wire1) |
| Kelvin | none (README) | none (README) |
| diode dies | **none** (layout script defines only power_lead, signal_lead, MOS) | **none** (same) |
| macro inductance measure | L5 -> L1 (DC+ -> DC-) | L2 -> L3 (DC+ -> DC-), "1000 #kHz" |
| constraint.csv spacing | 0.5 everywhere | 1.0 everywhere |

- **[F]** Copper areas, transcribed and checked by `--check`:
  - 2D_Case_2R: DC- 240, PHASE 720, DC+ 208, each gate 104 mm².
  - 2D_Case_6: PHASE 401, DC+ 256, DC- 209, GATE_LS 72, GATE_HS 57, SIG_T8 72, SIG_T10 57 mm².
- **[I]** Net assignment. Drain islands and macro Source/Sink give it directly. For 2D_Case_2R the constraint.csv voltage
  column also agrees: T10 15000, T2 7500, T1 0. In both cases the macro measure is the ModuleForge commutation-loop port
  (DC+ to DC-, PHASE open).
- **[F]** PowerSynth places its gate bond points without regard to the part's gate pad:
  - Every gate bond point lies in the source-pad area.
  - For one switch per case they sit on the die edge opposite the part's gate pad:
    - 2D_Case_2R HS D3/D4: B14/B16 at die-relative y 1-1.25.
    - 2D_Case_6 LS D3/D4: B11/B14 at y 1-2.
  - In those dies the source wire leaves toward the part's gate-pad edge.
- **[I]** That switch was drawn as if its dies were turned by 180°.

## 3. Modelling choices
- **M1 die orientation (identical dies).** spec_from_layout requires identical dies, so one uniform orientation is used per
  reference.
  - Rule, fixed before any rule measurement, twin or L1: choose between 0° and 180° about the die centre. Take the one with
    the larger smallest plan distance between a gate wire and a power wire.
  - Recorded scores:
    - 2D_Case_2R: 0° → 0.749 mm, 180° → 0.570 mm. Chosen: **0°** (part as drawn).
    - 2D_Case_6: 0° → 0.015 mm, 180° → 0.802 mm. Chosen: **180°**.
  - Why 0° fails for 2D_Case_6: the LS power wires would pass over the LS gate pads, and the measured pitch rule would fall
    to 0.015 mm.
  - Pads at 180°: source (0.165, 1.15, 3.5, 4.5) and gate (2.47, 0.5, 0.5, 0.5), die-relative.
  - The die footprint, the die short and the power-wire feet do not depend on M1. So L_loop and the thermal inputs do not
    depend on it either. Only the gate pads and gate wires do.
  - Consequence for 2D_Case_2R at 0°: the HS gate wires cross over their die and are 10.40 mm long.
- **M2 gate wires.** Gate wires are SignalWires from the gate-pad centre to the centre of PowerSynth's landing point.
  - Diameter 0.30 mm (Wire1, as in the source).
  - No Kelvin wires.
  - Gate wires are not conductors in `to_conductors()`.
- **M3 power-wire feet.**
  - Feet sit at the bond-point centres.
  - 2D_Case_6: two wires 0.5 mm apart, centred on the 1 x 1 point, offset across the wire direction.
  - **[I]** The source gives "2 0.5". The exact placement inside the point is not given.
- **M4 wire shape.** `arc_wire` with loop height 1.0 mm for every wire. The JEDEC 4-point height is not in the files read,
  so this is the Case 4 assumption. Wire conductivity: Al.
- **M5 solder layer.** The stack's solder layer is SAC305, 1 µm. PowerSynth has none, but LayerStack requires one. This
  matches the E008 dev substitution for Case 4.
- **M6 die attach.**
  - Die attach: SAC305, 50 µm (DIE_ATTACH_THICKNESS). It is non-zero, and thermal_fem accepts it (§5).
  - Die: 4H-SiC, 0.18 mm. This is a fact and equals the default.
  - The die top, and so the wire start, is 50 µm higher than with a zero attach.
- **M7 backside copper.** backside_inset = 0: the bottom metal covers the full substrate outline.
- **M8 terminals.** Terminals are the 3 x 3 lead footprints. Leads, posts and signal leads are not modelled.
- **M9 conductivities.**
  - Cu 385 W/(m K).
  - AlN 170 W/(m K) at 300 K, with the AlN k(T) law in `geometry/stack.py` (K_LAWS; its docstring gives 170-180 W/(m K)
    for sintered AlN).
  - PowerSynth's material table was not read.
- **M10 keep-outs and L_term.**
  - Keep-out nets:
    - 2D_Case_2R: GATE_LS, GATE_HS.
    - 2D_Case_6: SIG_T8, GATE_LS, GATE_HS, SIG_T10. SIG_* is not Kelvin: the README says there is none, and SIG_* falls
      in spacing class `other`.
  - L_term = 7 nH: E008 `config.L_term.public_H` (S3 of `research/notes/o003-public-benchmarks.md`).

## 4. Snapping, hashes, measured rules
- **[F]** Snap record counts (snap_layout, DEFAULT_RULES), at 0.5, 0.25 and 0.125 mm:
  - 2D_Case_2R: 0 / 0 / 0.
  - 2D_Case_6: 0 / 0 / 0.
- **[F]** Both references are already on all three grids, so **s_ref = 0** for both. The snapped fingerprints equal the
  built ones at every grid.
- **[F]** The reconstruction is the built layout.
  - Reason: snap_layout re-derives die w/h from the snapped edges, which adds 1-ulp float noise below RECORD_TOL. That
    noise fails spec_from_layout's exact die-identity test.
  - The script checks that the fingerprints are equal.
- **[F]** 2D_Case_6 under DEFAULT_RULES has 4 pre-existing `wire_pitch` violations: the source's 0.5 mm pair pitch is below
  the 0.6 mm default. None are induced by snapping.
- **[F]** Reconstruction hashes (Layout.fingerprint):
  - 2D_Case_2R `66cb1e191c9f88396125cfd87227865d209ea6cf4c5f4306082c5ccee2ad696a`
  - 2D_Case_6 `71e07ae149b42bcd5efa243edc51730c208556e66fdf8c9d3356dc54ce574cb7`
- **[F]** E008 stack types (`_stack_type`): `other:13fbac2ad296` (2R) and `other:d34d9682c1b0` (Case 6). So each needs its
  own spot check under F6(e).

**[F]** Measured rules (measure_rules on the reconstruction; mm, rounded; full values in the JSON):

| rule | 2D_Case_2R | 2D_Case_6 |
|---|---|---|
| spacing DC+/PHASE, PHASE/DC-, DC+/DC- | 2.0, 2.0, 24.0 | 1.0, 1.0, 1.0 |
| spacing signal–DC+ / –PHASE / –DC- / –own source / HS–LS | 2.0 / 2.0 / 18.0 / 4.0 / 2.0 | 1.0 / 1.0 / 8.0 / 9.43 / 14.32 |
| spacing_other (→ min_spacing) | – (min_spacing 2.0) | 1.0 |
| min width power / other | 4.0 / 4.0 | 3.0 / 3.0 |
| die_spacing, die_edge_margin, edge_margin | 4.0, 1.0, 2.0 | 2.0, 1.0, 1.0 |
| min_wire_pitch (diameters) | 0.749 (2.50; gate–power pair) | 0.500 (1.67; power pair) |
| signal wire Ø range; length range | 0.30; 5.344–10.396 | 0.30; 4.123–8.330 |
| max_gate_wire_length | 10.396 | 8.330 |
| unmeasured (defaults) | wire length 1.5–15, Ø 0.1–0.5, landing margin 0.3, start margin 0.15, die–terminal 1.0 | same |

- **[F]** Each reconstruction is DRC-clean under its own measured rules (`--check`).
- **[I]** In 2D_Case_2R, `min_wire_pitch` comes from the HS gate-wire/power-wire pair. It is an M1/M2 consequence, not a
  power-wire pitch of the source, which has one wire per die.

## 5. Mesh-only numbers (no solve)
- **[F]** l2_layout at 0.25 mm. Lattice plus Grid plus wire filaments, as in `build_layout_system` up to the Grid.
  Unknowns = n_g + nfil:

| | lattice | grid unknowns | filaments | **unknowns** |
|---|---|---|---|---|
| 2D_Case_2R | 220 x 240 | 1,491,040 | 100 | **1,491,140** |
| 2D_Case_6 | 240 x 160 | 1,094,880 | 200 | **1,095,080** |

- **[I]** Both are smaller than Case 4's 4.11 M unknowns, which E008's `--plan` used as a proxy for both references.
  E008.yaml also lists `on_grid: false` as a proxy for both; the fact is `on_grid: true`. `--plan` should be re-run on
  these reconstructions, as E008.yaml already says.
- **[F]** Lattice exactness: relative area error ≤ 1.1e-15 at both 0.5 and 0.25 mm, and the die footprints are on the
  lattice.
- **[F]** `thermal_fem.layout_grid` level 0, under the frozen rule `research/o007_dev3/frozen_config.json`, accepts both.
  `estimate_dofs` level 0: 77,966 (2R) and 81,714 (Case 6).

## 6. TWIN-SPACE CHECK (founder session 2026-11-09; review T0299)
- **[F]** Method: E008's own `prepare()`, loaded from `experiments/runners/e008_run.py` after `--verify-freeze` exited 0.
  - Spec: `spec_from_layout(reconstruction, measure_rules(reconstruction)[0], keepout_nets)`, with no overrides.
  - `n_quick = 0`, so no generator sample is drawn.
  - L1 only. No l2_layout or thermal solve, and no search.
  - Run time 65 s for both references.

| | 2D_Case_2R | 2D_Case_6 |
|---|---|---|
| twin mode | fit (reached the fitted twin's DRC test) | – |
| error raised | `TwinError: the fitted twin is not DRC-clean under spec.rules: signal_wire_length` on signal wires 2 and 3 (4.597 mm outside [5.344, 10.396] mm, at the LS gate pads (14.28, 21.25) and (23.28, 21.25) mm) | `TwinError: no (orientation, sequence) of the generator space matches the reference geometry` |
| difference record, L1(W)/L1(ref), copper symmetric difference per net, midpoint splits | not produced: `prepare()` stops at the TwinError (§ "Twin" in the JSON) | not produced |
| degrade(), walk, L1(D)/L1(twin) | not run (no twin) | not run |

**Mechanism, 2D_Case_2R** ([F] from the error, [I] for the explanation):
- measure_rules sets `min_signal_wire_length` to the reference's shortest gate wire, 5.344 mm (D1).
- The fitted twin puts the LS gate wires 4.597 mm long, about 0.75 mm shorter.
- The reference has signal wires, so the twin's gate-foot repair (step 3) does not apply, and any violation raises.
- [I] The failure comes from two things together:
  - the packet's requirement that gate wires be modelled as signal wires;
  - the lower length bound that measure_rules derives from them.
- It does not come from the power copper: the fit got as far as the DRC test.
- Whether the outcome depends on M1 was not tested. M1 moves every die's gate pad, LS included. M1 was fixed by its
  geometric rule before the twin ran, and it was not revisited after seeing the result.

**Mechanism, 2D_Case_6** ([I], from the geometry):
- Along y, the anchors are interleaved:
  - HS landing line 15.5;
  - LS die row 15–21;
  - HS die row 19–25;
  - LS landing line 24.5.
- The two switch blocks sit side by side in x, and their wires run in opposite directions.
- Probable cause: the generator's 16 (orientation, sequence) slot orders do not admit this anchor order, so no pair is
  kept. This was not checked line by line against twin.py's candidate filter.
- The anchors come from the dies and the power-wire ends. These are facts plus M3, and M3 only spreads the feet across x.
  So M1, M2 and M4 cannot change this outcome.

**Consequence.** Every reference raises. Under F1(a) both are excluded, and E008 as drafted would be INVALID before any VM
spend. The packet requires that this decision go to the founder before registration.

Options the founder may weigh (speculation, not tested here):
- For 2R: model gate pads without gate wires, as Case 4 does through `extra_pads`. Then `min_signal_wire_length` stays
  None.
- Change how `measure_rules` and the twin treat signal-wire length. That is frozen code, so it needs a new freeze.
- For Case 6: extend the generator space. That is frozen too.

None of these was run.

## 7. What was not done, and what would prove this wrong
- No inductance or thermal solve and no search was run on these references. The generator ran only inside twin()'s fit;
  no sample was drawn.
- If PowerSynth's coordinates were not in the baseplate frame, every trace would shift by 5 mm.
  - [I] They are in the baseplate frame: every trace lies inside the (5, 5) substrate, and the source lists the substrate
    at (5, 5).
  - Even a shift would not change any relative geometry, rule or twin outcome. It would only move the lattice origin.
- M1 would be wrong if the real modules use dies with a mirrored or other pad layout. It affects only the gate wires, and
  the 2D_Case_6 TwinError does not depend on it.

## 8. Commands run (exit codes)
- `uv run python experiments/runners/e008_run.py --verify-freeze` → 0. All six freeze hashes, the grid rule, the
  thermal_fem hash and the metric parameters were OK.
- `uv run python research/scripts/o003_powersynth_references.py --write` → 0. Twin results as in §6.
- `uv run python research/scripts/o003_powersynth_references.py --check --sources $TMPDIR/ps_t0263` → 0.
- `uv run python research/scripts/o003_powersynth_references.py --check` → 0.
- `uv run ruff check research/scripts/o003_powersynth_references.py` → 0.
