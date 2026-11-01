# What public wire-bonded half-bridge/six-pack module layouts can serve as reference layouts for O003 re-layout headroom studies?
Date: 2026-10-31 · Task: founder session (thesis review 2026-10-31) · Confidence: medium

Provenance: written by a general-purpose research agent launched from the founder session (scout subagents could
not run there: python3 3.10 made the guard fail closed). The founder session re-opened S5 (the Sample_Designs
directory list matches) and could not re-open S1 (TLS certificate rejected); the other sources were not re-checked.

## Answer (≤ 5 sentences)
No public benchmark suite exists for wire-bonded module re-layout. The usable public material is a small number of academic layouts with partial geometry and published simulated or measured loop inductance, plus one machine-readable layout set, the PowerSynth Sample_Designs, which is licensed GPL-3.0. Shortlist, ranked by how easy each is to reconstruct: (1) PowerSynth `2D_Case_2R`/`2D_Case_6` (machine-readable layer stacks and layout scripts, tied to the Evans TPEL 2019 test vehicles) [S4–S6]; (2) the UTK conventional vs P-cell/N-cell IGBT phase-leg pair, with the same dies, a table of dimensions, Q3D results and impedance-analyzer measurements [S1, S2]; (3) the CPES 1200 V/60 A and 120 A SiC phase-leg modules, including a Q3D comparison against a commercial 100 A module's internal layout [S3]; (4) the Aalborg/Danfoss SiC half-bridge with 4 dies per switch, for current sharing [S8–S10]; (5) the reverse-engineered Cree CCS050M12CM2 six-pack 3D CAD model, which the authors describe as "open source", but where it is hosted is unknown [S14]. None of these is a fixed-housing derivative with complete geometry plus measured current sharing and Tj. The published numbers also show that the headroom figure depends strongly on which loop is the denominator and on whether inductance is extracted at DC or AC, so O003 needs a pre-registered reconstruction protocol before day 60.

## Sources
| id | citation | url | type (paper/doc/datasheet/news/filing/repo) | accessed |
|---|---|---|---|---|
| S1 | S. Li, L. M. Tolbert, F. Wang, F. Z. Peng, "Reduction of Stray Inductance in Power Electronic Modules Using Basic Switching Cells," IEEE ECCE 2010 (author copy) | https://web.eecs.utk.edu/~tolbert/publications/ecce2010_shengnan_final_paper.pdf | paper | 2026-10-31 |
| S2 | S. Li, "Packaging Design of IGBT Power Module Using Novel Switching Cells," PhD dissertation, Univ. of Tennessee, Dec. 2011 (record: trace.tennessee.edu/utk_graddiss/1205) | https://trace.tennessee.edu/bitstreams/b62b0332-f663-4ff7-880d-47586b39a8a5/download | paper | 2026-10-31 |
| S3 | Z. Chen, "Electrical Integration of SiC Power Devices for High-Power-Density Applications," PhD dissertation, Virginia Tech, 2013 (hdl 10919/23923) | https://vtechworks.lib.vt.edu/bitstreams/09c2e354-f30f-475f-938f-6260792d669c/download | paper | 2026-10-31 |
| S4 | T. Evans et al., "PowerSynth: A Power Module Layout Generation Tool," IEEE TPEL 34(6), 2019, DOI 10.1109/TPEL.2018.2870346 (author copy via Wayback; the e3da.csce.uark.edu host returned NXDOMAIN on 2026-10-31) | https://web.archive.org/web/20250319022709id_/https://e3da.csce.uark.edu/pub/doc/2019/T.Evans-IEEE.TPEL-2019.pdf | paper | 2026-10-31 |
| S5 | e3da/PowerSynth2-pkg, `work/Sample_Designs` (tree; `2D_Case_2R` README, `layer_stack.csv`, `layout_geometry_script.txt`; `2D_Case_4`, `2D_Case_6`, `3D_Case_2` READMEs; org repo list), GPL-3.0 | https://github.com/e3da/PowerSynth2-pkg | repo | 2026-10-31 |
| S6 | e3da/PowerSynth2-core README (GPL-3.0; cites PowerSynth 2 TPEL 2023, DMC 2023, OJPEL 2025) | https://github.com/e3da/PowerSynth2-core | repo | 2026-10-31 |
| S7 | I. Al Razi et al., IEEE TPEL 36(8), Aug. 2021 (PowerSynth 2.5-D multichip module design-automation paper; author copy via Wayback; full title not captured in the text extraction) | https://web.archive.org/web/20250319034738id_/https://e3da.csce.uark.edu/pub/doc/2021/I.Al.Razi-IEEE.TPEL-2021.pdf | paper | 2026-10-31 |
| S8 | H. Li, S. Munk-Nielsen, X. Wang, R. Maheshwari, S. Beczkowski, C. Uhrenfeldt, T. Franke, "Influences of Device and Circuit Mismatches on Paralleling Silicon Carbide MOSFETs," IEEE TPEL 31(1):621–634, 2016 (VBN pre-print) | https://vbn.aau.dk/ws/files/209523346/Influences_of_Device_and_Circuit_Mismatches_on_Paralleling_Silicon_Carbide_MOSFETs.pdf | paper | 2026-10-31 |
| S9 | S. Beczkowski, A. B. Jørgensen, H. Li, C. Uhrenfeldt, X. Dai, S. Munk-Nielsen, "Switching current imbalance mitigation in power modules with parallel connected SiC MOSFETs," EPE'17 ECCE Europe (accepted manuscript) | https://vbn.aau.dk/ws/files/305861887/EPE17_current_imbalance_mitigation_sicmosfet.pdf | paper | 2026-10-31 |
| S10 | P. P. Kubulus et al., "Dynamic Current Sharing Optimization of Asymmetric SiC Power Module," IEEE ECCE 2023 (accepted manuscript) | https://vbn.aau.dk/ws/files/626504363/Dynamic_Current_Sharing_Optimization_of_Asymmetric_SiC_Power_Module.pdf | paper | 2026-10-31 |
| S11 | H. Li, S. Munk-Nielsen, S. Beczkowski, X. Wang, "A Novel DBC Layout for Current Imbalance Mitigation in SiC MOSFET Multichip Power Modules," IEEE TPEL 31(12):8042–8045, 2016 (record/abstract only) | https://vbn.aau.dk/da/publications/a-novel-dbc-layout-for-current-imbalance-mitigation-in-sic-mosfet-3/ | paper | 2026-10-31 |
| S12 | M. Wang, F. Luo, L. Xu, "A double-end sourced multi-chip improved wire-bonded SiC MOSFET power module design," APEC 2016 (record/abstract only) | https://researchconnect.stonybrook.edu/en/publications/a-double-end-sourced-multi-chip-improved-wire-bonded-sic-mosfet-p/ | paper | 2026-10-31 |
| S13 | M. Wang, F. Luo, L. Xu, "An improved wire-bonded power module with double-end sourced structure," ECCE 2016 (record/abstract only) | https://researchconnect.stonybrook.edu/en/publications/an-improved-wire-bonded-power-module-with-double-end-sourced-stru/ | paper | 2026-10-31 |
| S14 | A. J. Morgan, Y. Xu, D. C. Hopkins, I. Husain, W. Yu, "Decomposition and electro-physical model creation of the CREE 1200V, 50A 3-Ph SiC module," APEC 2016, DOI 10.1109/APEC.2016.7468163 (record/abstract only) | https://researchconnect.suny.edu/en/publications/decomposition-and-electro-physical-model-creation-of-the-cree-120/ | paper | 2026-10-31 |
| S15 | M. G. Spitaleri et al., "Layout Impact on Current Sharing in SiC Power Modules: Modeling and Experimental Validation," ECCE 2025 (record only, no file) | https://www.iris.unict.it/handle/20.500.11769/715112 | paper | 2026-10-31 |
| S16 | J. Yang et al., "Design and current balancing optimization of a 1700V/1000A multi-chip SiC power module," ICPE-ECCE Asia 2023 (record only) | https://wrap.warwick.ac.uk/181797 | paper | 2026-10-31 |
| S17 | V. Parque, A. Nakamura, T. Miyashita, "A Study on the Inductance and Thermal Regression and Optimization for Automatic Layout Design of Power Modules," arXiv:2312.08523 (ICSJ 2023), CC BY-SA 4.0 | https://arxiv.org/abs/2312.08523 | paper | 2026-10-31 |

## Findings
**UTK P-cell/N-cell pair (IGBT, 1 die per switch)**
- [S1] Conceptual phase-leg modules in Q3D, Table I:
  - DBC size: 37.0×38.0 mm (conventional) vs 37.5×38.5 mm (proposed).
  - DBC: 8 mil Cu, 25 mil alumina.
  - Dies: IGBT 5×5 mm, diode 5.85×5.85 mm.
  - Bond wires: "8 mil×5".
- [S1] Q3D loop inductance, "DC excitation source … skin effect is neglected" (Table II), conventional → proposed:
  - Loop1: 53.06 nH → 39.91 nH.
  - Loop2: 50.67 nH → 35.18 nH.
  - S1 emitter–D2 cathode: 20.19 nH → 4.23 nH.
  - The point inductances include terminal leads l1 = l4 = 15.3 nH (conventional) and 15.0 nH (proposed).
- [S1] Saber double-pulse simulation at 300 V, 30 A: turn-off overshoot 246 V (conventional) vs 200 V (proposed).
- [S2] Prototypes used an ABB 1200 V/75 A IGBT. Table 3.3, Q3D DC/AC values:
  - Conventional: Loop1 38.3/18.0 nH, Loop2 38.3/18.5 nH.
  - Proposed: Loop1 11.7/7.2 nH, Loop2 14.4/8.6 nH.
- [S2] Table 5.1, simulated vs measured. Measurement: Agilent 4294A, "from 1 MHz to 10 MHz", on dummy modules with Al wires bonded in place of the dice.
  - Conventional: Loop1 20.5/25 nH, Loop2 20.3/21 nH.
  - Proposed: Loop1 7.2/6.5 nH, Loop2 8.6/6.0 nH.
- [S2] Chapter 6 adds a two-chip-parallel variant (two IGBTs and two diodes per cell). The P/N-cell layout lowers loop inductance, but "the mismatch of the paralleled branches was larger", and it "takes more substrate area".

**CPES SiC phase-leg modules (Virginia Tech, Chen dissertation)**
- [S3] 1200 V/60 A module bill of materials (Table 5-1):
  - Cree SiC MOSFET 1200 V/20 A, die 4.08×4.08 mm².
  - Cree SBD 1200 V/10 A, die 2.26×2.26 mm².
  - Al wire 10 mil, "3 wires in parallel for each die".
  - Curamik AlN DBC, Cu/AlN/Cu 8/25/8 mils.
  - Ni terminals 5 mils; AlSiC-9 baseplate 4 mm; Sn5-Pb95 solder.
  - (inference) 60 A from 20 A dies implies 3 MOSFETs per switch.
- [S3] Even laminated DC terminals "still introduce around 7 nH extra inductance in the switching loop" (Q3D), "almost 50% of the total parasitic inductance inside the module". Decoupling capacitors were embedded for this reason.
- [S3] 120 A module construction: two identical DBCs; 1200 V/20 A SBDs (3.08×3.08 mm²); 31 mil Ni-plated Cu terminals.
- [S3] It was compared with a commercial 1200 V/100 A SiC phase-leg module. The dissertation publishes that module's internal layout figure, and the commercial module uses "CPW2-1200-S010B * 5 in parallel in each switch position" (inferred from its datasheet).
- [S3] Q3D comparison results:
  - "Substrate-associated loop inductance … drop from 9.7 nH to only 4.8 nH".
  - DC bus bars: 37% lower.
  - CPES total: 15.8 nH, "42% less than that of the commercial module".
- [S3] Double-pulse ringing estimates, including the tester boards: 60 nH (commercial) vs 40.1 nH (CPES). Of the 19.9 nH difference, 11.3 nH is from the internal layout and 8.6 nH from the boards. Turn-off over-voltage was 680 V for both at 5 A/ns.
- (inference) Implied commercial module-internal total: 15.8/0.58 ≈ 27.2 nH.
  - The substrate-only gain (4.9 nH) is therefore ≈18% of the module-internal loop.
  - It is ≈8% of the measured double-pulse loop (60 nH).
  - Both are below O003's 20% threshold if terminals and bus bars are fixed by the housing.

**PowerSynth (University of Arkansas; GPL-3.0)**
- [S4] Electrical test vehicle (passive, no dies):
  - DBC 40×50 mm, Cu 200 µm, AlN 635 µm.
  - "a pair of 300 μm diameter aluminum wire bonds … to each location" of a device, "a single device per switching".
  - Measured with an LCR meter; compared against FastHenry.
- [S4] A thermal test vehicle with 2 devices per switch was measured with an IR camera (±2 °C) and a thermocouple (±2.2 °C). PowerSynth error vs simulation: average 3.2%, maximum 8.0%.
- [S4] Optimization example:
  - 4 devices per switch, 8 devices at 50 W each, 100 kHz, baseplate backside at 300 K.
  - Substrate area varied from 45×50 to 80×80 mm.
  - 170 non-dominated layouts "span a difference in inductance and temperature of 7 nH and 15 °C".
  - The measured inductance tables were not recoverable in the text extraction.
- [S5] Sample cases include `2D_Case_2R`, `2D_Case_3`…`2D_Case_8`, `3D_Case_2/3/4/6`, Buck/Boost and Manual cases. Each has `layout_geometry_script.txt`, `layer_stack.csv`, `macro_script.txt` and, for most, `bond_wires_setup.txt`.
- [S5] `2D_Case_2R`:
  - README: SiC half-bridge, wire-bonded gate and power loops, single-sided cooling, no Kelvin source; "used in" Evans TPEL 2019.
  - Layer stack: baseplate 55×60×1 mm Cu; Cu 45×50×0.2 mm; AlN 45×50×0.835 mm; top Cu 0.2 mm.
  - The AlN thickness differs from the 635 µm stated in S4.
  - The layout script holds four MOSFETs (D1–D4); (inference) 2 per switch.
- [S5] `2D_Case_6` is wire-bonded, single-sided cooling, and was "used in" Le et al., ECCE 2021 (loop-based inductance extraction). `2D_Case_4` is wire-bonded with a Kelvin source, with no publication named.
- [S6] All e3da repositories are GPL-3.0. PowerSynth2-pkg was last pushed 2026-04-20.
- [S7] Fabricated 2.5-D full-bridge module (PowerSynth flow), validated by double-pulse test:
  - 92 mm × 60 mm, rated 76 A.
  - A synthesized case reports 7.12 nH vs 10.2 nH for commercial modules.
  - Loop inductance including the decoupling capacitor: 7.986 nH.

**Aalborg current sharing (SiC, 4 dies per switch)**
- [S8] Danfoss test half-bridge "consisted with 8 SiC MOSFETs dies and 4 of them are in parallel". The layout minimizes drain-loop (Ld) mismatch, but the common-source inductance (Ls) differs per die.
- [S8] Measured on a PCB replica of the layout:
  - Without an auxiliary source wire: "largest current unbalance … more than 15A while the on state current is only around 10A"; the Q1 overshoot is ">200%" while the total current overshoot is ~30%.
  - With an auxiliary source bond wire: peak drain overshoot "reduced from 22A to 18A".
  - Gate drive +25/−5 V. Geometry is shown only in figures, with no dimensions.
- [S9] An "industry standard DBC layout" (Dynex co-authors) with numerically extracted parasitics. The mitigation is tuning individual source bond wires.
- [S10] A "highly asymmetric half-bridge module layout … four parallel dies" modelled in Q3D, with gate and source resistances tuned by a genetic algorithm.
- [S11] Abstract only, no numbers.

**Other candidates**
- [S12, S13] Double-end-sourced wire-bonded 1200 V/60 A half-bridge with 3 devices in parallel: power-loop inductance "7.2 nH" and improved current sharing. Full text not open.
- [S14] Cree CCS050M12CM2 (1200 V/50 A, 25 mΩ six-pack): reverse-engineered "into a full 3D CAD model", with Q3D parasitics and baseplate thermal maps. "The complete model is made open source and freely distributed". Where it is hosted was not found.
- [S15] Per-die current was measured by cutting the module's source copper trace; no full text is available and all rights are reserved.
- [S16] 18 paralleled chips per switch (1700 V/1000 A), with no numbers.
- [S17] 36 layout parameters, CC BY-SA 4.0, but no geometry or values are released.

**Licences, access and negative results**
- [S8–S10] VBN terms: "download and print one copy … for the purpose of private study"; "may not further distribute … or use it for any profit-making activity".
- [S1, S4] Author copies carry IEEE copyright notices.
- (inference) Numeric dimensions are facts and can be re-modelled. Figures and PDFs must not be redistributed. GPL-3.0 sample files conflict with the "permissive licenses only" rule if they are vendored; this needs a founder decision.
- (inference) Negative result: searches found no open DBC-level module CAD project. For Tesla, ST and EconoDUAL modules, searches surfaced only paid teardown reports, which were not opened, and no open per-die geometry.

## Relevance to ModuleForge
- Each shortlisted case can be rebuilt in L0 and solved with L1/L2 PEEC. Published values are only reconstruction checks, not headroom evidence:
  - S2 Table 5.1 measurements.
  - S3 Q3D breakdown.
  - S4 LCR and IR data.
  - S8 per-die waveforms.
- Two specification lessons for O003 benchmarks:
  - DC and AC extraction differ by about 2× (S2: 38.3 vs 18.0 nH), so the extraction frequency must be fixed.
  - The denominator must be fixed: substrate-only, module-internal, or the loop including the PCB. S3 shows that terminals and bus bars dominate.
- (inference) The S1, S2 and S3 comparisons pit an optimized layout against a "conventional" baseline. Headroom against real commercial derivatives is probably smaller.
- (inference) Fixed-housing derivatives should keep terminals and bus bars frozen, and only S3 lets us estimate what is left once they are.

## Thesis impact: unclear — why
Loop-inductance branch, leaning weaker:
- The only public comparison against a commercial module implies about 18% module-internal headroom from substrate re-layout alone (inference from S3), just under the 20% threshold.
- Against conventional baselines with fixed leads, Q3D gives 25–31% (S1).

Current-mismatch branch, leaning plausible:
- Conventional 4-die layouts show very large dynamic imbalance (Q1 overshoot >200%, S8), so ≥50% mismatch headroom looks plausible (inference).
- However, no public dataset gives full geometry together with per-die measurements.

The kill criterion itself is under-specified until the benchmark set, baseline, loop definition and frequency are pre-registered.

## Open questions
- Where is the "open source" CCS050M12CM2 model (S14) hosted? Only the founder may contact the authors.
- Founder decision: may GPL-3.0 PowerSynth sample designs (S5) be used as external benchmark inputs under the permissive-licence policy?
- The measured inductance tables of S4 and S7 are not in the extractable text; they need a manual read.
- Fraunhofer IISB's DMC 2025 work benchmarking RL vs genetic algorithms on half-bridge layouts came up in search, but its record page was access-denied, so it is not cited. Were its test cases released?
- Are paid teardowns (System Plus, LTEC) affordable and usable for a fixed-housing commercial reference? Not opened.
- Datasheet module stray inductance could serve as an anchor. The Wolfspeed CAS300M12BM2 sheet states only the condition ("Between DC- and DC+, f = 10 MHz"); the value was not machine-readable.
- Does "public benchmarks" in the kill criterion allow reconstructed academic layouts, and with which tolerance on unknown dimensions?
