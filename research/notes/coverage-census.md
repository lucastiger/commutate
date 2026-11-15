# Coverage census of wire-bonded SiC half-bridge modules (fact-only screening answers)
Date: 2026-11-15 · Task: scout census (plan section 2) · Confidence: low (see section 1, limits)

**Declaration: fact-only screening answers; no geometry entered the repository.** Every cell below is a yes/no, a count, a part number or a datasheet figure. No copper dimensions, coordinates, drawings, images or layout files were copied. Pin counts are *external* pins from datasheet pin tables.

## Answer (≤ 5 sentences)
Public free sources identify 14 commercial half-bridge SiC modules (one short of the 15 asked for), plus 4 PowerSynth rows and 1 six-pack listed separately. Datasheets answer only Q2 (partly), Q6, Q9 and Q14 (partly); Q1, Q3-Q5, Q7-Q8 and Q10-Q13 are unknown for all 14 commercial modules. From datasheets alone, 9 of 14 commercial modules carry an excluding feature (separate diode dies: 6; several power pins per net: 4 [I]), 0 are confirmed representable today and 5 are undetermined. The top missing features by modules blocked are diode dies (6) and terminal layout (4), not quarter-turned dies or side-by-side blocks. A defensible 80 % coverage number needs vendor or designer answers (section 5).

## 1. Method
- Date of all access: **2026-11-15**. Free public sources only: vendor datasheets (text extracted locally from the public PDF), vendor product pages, one trade-press article, distributor listings. No account, form, paywall or contact. A paywalled TechInsights teardown of NXH006P120MNF2 exists (S8c); not used.
- Search: web search per vendor (Wolfspeed, Infineon, onsemi, STMicroelectronics, ROHM, Mitsubishi Electric, Fuji Electric, Semikron Danfoss, Microchip, Vincotech), then reading the datasheet text of each candidate myself. Sub-agent summaries were used only to find URLs; a statement is cited to a datasheet only where I read it in the extracted text. Secondary sources are labelled.
- Selection: modules named half-bridge/phase-leg, SiC MOSFET, with an openly downloadable datasheet or product page, spread over vendors. Selected by *datasheet accessibility*, not at random (sampling bias: see thesis_impact).
- **Wire-bonding is not stated by any source for any commercial module.** All 14 are included on the [I] that screw/press-fit power modules of this type are wire-bonded; XM3 (M4) is the least certain.
- Not counted: ST (no half-bridge found: ACEPACK 2 SiC parts are 3-level or four-packs; SH70M12W3AG is a molded SMD half-bridge whose page I did not open; web-search snippets only, S15), Fuji (the 2MSI parts are Si-IGBT + SiC-SBD hybrids; the one all-SiC article module is described as having "no bonding Al wire", S16; no usable all-SiC half-bridge datasheet found).
- Development layouts (2D_Case_2R, 2D_Case_6, 2D_Case_4): copied from `research/notes/o003-twin-coverage.md` section 4 (T14), not re-derived. PowerSynth 2D_Case_5 and the PREES/CCS050M12CM2 model: only facts in D0019 Context (D19). I did not open NC State PREES/Hopkins material or any PowerSynth file, nor `data/`, `project/customers/`, or any customer file.
- Tooling note: the fetch tool could not read PDFs, so I downloaded public datasheets to the session scratchpad (outside the repository) and extracted text with `pypdf` run with `python -I`. Nothing was added to the repository except this file.
- Limits: datasheet text does not carry die arrays, copper topology or wire counts; those sit in drawings, which the rules exclude. Hence the many "?".

### Counts
- Counted commercial half-bridge modules: **14** (shortfall of 1 against the 15 target; not padded).
- Counted PowerSynth public rows: 1 unseen (2D_Case_5, facts from D19).
- Development layouts: 3 (2D_Case_2R, 2D_Case_6, 2D_Case_4).
- Separate (not half-bridge): 1 six-pack (CCS050M12CM2, facts from D19).

## 2. Modules and answers
Legend: `?` = unknown (source does not say). Q-numbers are the "sent #" of Part A. [I] = inference, reasoning in the notes below the table.

### 2a. Identification
| ID | Vendor | Part | Class | Substrate as stated | Source |
|---|---|---|---|---|---|
| M1 | Wolfspeed | CAS300M12BM2 (62 mm) | 1200 V, 300 A; LStray 11.1 nH | AlN insulator, Cu baseplate (DBC/AMB ?) | S1 |
| M2 | Wolfspeed | CAS120M12BM2 (62 mm) | 1200 V, 120 A; LStray 12.9 nH | AlN insulator, Cu baseplate | S2 |
| M3 | Wolfspeed | CAS325M12HM2 | 1200 V, 325 A; 5.5 nH (press) | AlSiC baseplate, Si3N4 AMB (press, secondary) | S3 |
| M4 | Wolfspeed | CAB400M12XM3 (XM3) | 1200 V, 400 A; 6.7 nH | Si3N4 insulator, Cu baseplate | S4 |
| M5 | Infineon | FF6MR12KM1 (62 mm) | 1200 V, ID nom 250 A (preliminary data); 20 nH | Internal isolation Al2O3, Cu baseplate | S5 |
| M6 | Infineon | FF45MR12W1M1_B11 (EasyDUAL 1B) | 1200 V, ID nom 25 A; 18 nH | Internal isolation Al2O3 | S6 |
| M7 | onsemi | NXH010P120MNF1 (F1) | 1200 V, 10 mΩ | DBC (ceramic material not stated) | S7 |
| M8 | onsemi | NXH006P120MNF2 (F2) | 1200 V, 6 mΩ | Ceramic "HPS", 0.38 mm | S8 |
| M9 | ROHM | BSM180D12P3C007 (C type) | 1200 V, 180 A; Ls 25.0 nH | ? | S9 |
| M10 | ROHM | BSM300D12P2E001 (E type) | 1200 V, 300 A; Ls 13 nH | ? | S10 |
| M11 | Mitsubishi Electric | FMF800DXZA-24B | 1200 V, 800 A; Ls (P-N) 10.0 nH | Cu base plate; ceramic ? | S11 |
| M12 | Semikron Danfoss | SKM500MB120SC (SEMITRANS 3) | 1200 V (current ?) | DBC on insulated Cu baseplate (ceramic ?) | S12 |
| M13 | Microchip | MSCSM120AM02CT6LIAG (SP6LI phase leg) | 1200 V, 2.1 mΩ typ; ~3 nH (slides) | ? | S13 |
| M14 | Vincotech | 10-EY122PA008ME01-LU38F06T (flowDUAL E2 SiC) | 1200 V, 8 mΩ; equivalent to FF6MR12W2M1H_B70 | AlN | S14 |

### 2b. Answers Q1-Q14 (non-`?` cells carry the source key)
| ID | Q1 | Q2 | Q3-Q5 | Q6 | Q7 | Q8 | Q9 | Q10-Q13 | Q14 |
|---|---|---|---|---|---|---|---|---|---|
| M1 | ? | 3 power terminals (V+, Mid, V-) plus G1, K1, G2, K2 [S1]; pads ? | ? | ? | ? | ? | **yes**, Schottky diodes (datasheet "Schottky Diode", "Diode per position"); count ? [S1] | ? | Kelvin-source terminals K1, K2 exist [S1]; wire landing ? |
| M2 | ? | same labels V+, Mid, V-, G1, K1, G2, K2 [S2] | ? | ? | ? | ? | **yes**, Schottky [S2]; count ? | ? | K1, K2 terminals [S2]; landing ? |
| M3 | ? | ? | ? | C2M 25 mΩ 1.2 kV MOSFET [S3, press]; die size ? | 7 per switch [I-a]; arrangement ? | ? | **yes**, Z-Rec Schottky; 6 per switch [I-a] [S3] | ? | ? |
| M4 | ? | "offset terminal layout"; nets and counts ? [S4] | ? | ? | ? | ? | no separate diode stated; datasheet lists only "Body Diode" [S4] [I-b] | ? | Kelvin-**drain** pin (high side) [S4]; Kelvin source ? |
| M5 | ? | ? | ? | ? | ? | ? | no separate diode stated; datasheet lists only "Body Diode" [S5] [I-b] | ? | ? |
| M6 | ? | ? (NTC integrated, PressFIT) | ? | ? | ? | ? | no separate diode stated; "Body Diode" only [S6] [I-b] | ? | ? |
| M7 | ? | 3 nets; pins: DC+ 4, DC- 4, PHASE 4 (12 power pins) [S7]; pads ? | ? | ? | ? | ? | no separate diode stated; "Body Diode" curve only [S7] [I-b] | ? | Kelvin-emitter pins S1, S2 [S7]; landing ? |
| M8 | ? | pins: DC+ 8, DC- 8, PHASE 10 (26 power pins) [S8]; pads ? | ? | ? | ? | ? | not stated (no diode section found) | ? | 2 Kelvin pins + 2 gate pins per switch [S8]; landing ? |
| M9 | ? | Main terminals M6 screw [S9]; count and nets ? | ? | "SiC-UMOSFET" (trench); no die size | ? | ? | **yes**, SiC-SBD ("SBD (1/2 module)" thermal row) [S9]; count ? | ? | ? |
| M10 | ? | Main terminals M6 screw [S10]; count ? | ? | "SiC-DMOSFET"; no die size | ? | ? | **yes**, SiC-SBD [S10]; count ? | ? | ? |
| M11 | ? | Terminal list includes aP, aN, bP, bN (two P and two N terminals) [S11] [I-c]; pads ? | ? | SiC MOSFET; no die part/size | ? | ? | **yes**, SiC-SBD (Di1, Di2); count in chip drawing, not read [S11] | ? | ? |
| M12 | ? | ? | ? | 2nd-gen SiC MOSFET [S12]; die ? | ? | ? | no separate diode stated; "Integrated body diode" [S12] [I-b] | ? | ? |
| M13 | ? | ? | ? | ? | ? | ? | ? (distributor table has a "SiC parallel diode" 300 A column; meaning unclear) [S13] | ? | ? |
| M14 | ? | pins: DC+ 8, DC- 8, Ph1 10 (26 power pins) [S14]; pads ? | ? | ? | ? | ? | ? ("Diode forward voltage" row; separate or body not stated) | ? | Source pins S11 ×2, S12 ×2, gate ×2 per switch [S14]; "Kelvin" not stated |

Inference notes
- [I-a] M3: the article gives seven MOSFETs and six diodes for the module; per switch is inferred from 25 mΩ / 7 ≈ 3.6 mΩ against the datasheet module Rds(on) 3.6 mΩ (search summary, not read). Unverified.
- [I-b] "No separate diode stated" is absence in the datasheet text I read, not proof of absence. Treated as "no" only for scoring and flagged.
- [I-c] The Mitsubishi datasheet text lists aP, aN, bN, bP; I read this as two paired half-bridge terminal sets (the 2015 article says two 400 A half-bridges are externally paralleled, S11b). Not exactly three power terminals if so.

### 2c. Six-pack (separate, not counted)
| ID | Part | Facts (D0019 only) |
|---|---|---|
| X1 | Wolfspeed CCS050M12CM2 (treated as a PREES-related module, see Rules unsure) | Six-pack; DC+ and DC- shared by its three legs; separate antiparallel diode dies [D19]. Nothing else recorded; I did not open the Wolfspeed datasheet. |

### 2d. PowerSynth rows
Development layouts ("development layout"; copied from T14 §4, mapped to sent numbers):
| Sent Q | 2D_Case_2R | 2D_Case_6 | 2D_Case_4 |
|---|---|---|---|
| 1 substrates | not recorded | not recorded | not recorded |
| 2 power terminals | exactly three: yes [T14 Q1] | yes | yes |
| 3 one piece per net | yes (islands = 1) [T14 Q8] | yes | yes |
| 4 ring | no (open C-shape) [T14 Q9] | no | no |
| 5 branching | no [T14 Q10] | unknown (fails earlier) | no |
| 6 die / grid | outline 4×6, on 0.5 mm grid [T14 Q3]; die part not recorded | on grid | on grid |
| 7 array | single row per switch [T14 Q5] | single row | single row |
| 8 orientation | source: HS turned 180°; uniform after M1 [T14 Q2] | source: LS turned 180°; uniform after M1 | uniform (pads assumed) |
| 9 diode dies | no [T14 Q13] | no | no |
| 10 wires per die | same, 1 [T14 Q4] | same, 2 | same, 1 |
| 11 landing line | yes [T14 Q7] | yes [I] | yes |
| 12 side-by-side blocks | no [T14 Q6] | **yes** | no |
| 13 die/terminal wires | no [I] [T14 Q14] | no [I] | no [I] |
| 14 Kelvin / gate landing | no Kelvin; gate landing beyond nearest edge **yes** (1.13-1.91 mm) [T14 Q11, Q12] | no Kelvin; beyond nearest edge **yes** (0.76-0.78 mm) | Kelvin yes (assumed pads); no gate landing in source |

PowerSynth 2D_Case_5 (public, unseen; facts from D19 only): passes every fact test of the D0019 screen (tests not listed in D19); its two switch positions' dies differ by a quarter turn [D19]. Nothing else known.

### 2e. Sources
| key | citation | URL | type | accessed |
|---|---|---|---|---|
| S1 | Wolfspeed CAS300M12BM2 data sheet, Rev. 3 (Jan 2024) | https://assets.wolfspeed.com/uploads/2024/01/Wolfspeed_CAS300M12BM2_data_sheet.pdf | datasheet | 2026-11-15 |
| S2 | Wolfspeed CAS120M12BM2 data sheet, Rev. 3 (Jan 2024) | https://assets.wolfspeed.com/uploads/2024/01/Wolfspeed_CAS120M12BM2_data_sheet.pdf | datasheet | 2026-11-15 |
| S3 | eeNews Europe, 1200 V 325 A SiC module (HM2); product page https://www.wolfspeed.com/cas325m12hm2 redirects to another family | https://www.eenewseurope.com/en/1200v-325a-silicon-carbide-module-in-a-new-low-inductance-format/ | news (secondary) | 2026-11-15 (via search summary, page not read by me) |
| S4 | Wolfspeed CAB400M12XM3 data sheet, Rev. 2 (Jun 2024); product page https://wolfspeed.com/cab400m12xm3 | https://assets.wolfspeed.com/uploads/2024/01/Wolfspeed_CAB400M12XM3_data_sheet.pdf | datasheet | 2026-11-15 |
| S5 | Infineon FF6MR12KM1 datasheet V2.0 (2020-04-29, preliminary), distributor copy | https://static.chipdip.ru/lib/183/DOC011183478.pdf | datasheet | 2026-11-15 |
| S6 | Infineon FF45MR12W1M1_B11 datasheet V2.2 (2020-03-27), distributor copy | https://static.chipdip.ru/lib/702/DOC011702924.pdf | datasheet | 2026-11-15 |
| S7 | onsemi NXH010P120MNF1 datasheet | https://www.onsemi.com/pdf/datasheet/nxh010p120mnf1-d.pdf | datasheet | 2026-11-15 |
| S8 | onsemi NXH006P120MNF2 datasheet | https://www.onsemi.com/pdf/datasheet/nxh006p120mnf2-d.pdf | datasheet | 2026-11-15 |
| S8c | TechInsights package analysis PKG-2201-801 (paywalled, contents list only) | https://techinsights.com/ko/node/36737 | report listing | 2026-11-15 |
| S9 | ROHM BSM180D12P3C007 datasheet, Rev.003 (19 Mar 2025) | https://fscdn.rohm.com/en/products/databook/datasheet/discrete/sic/power_module/bsm180d12p3c007-e.pdf | datasheet | 2026-11-15 |
| S10 | ROHM BSM300D12P2E001 datasheet | https://fscdn.rohm.com/en/products/databook/datasheet/discrete/sic/power_module/bsm300d12p2e001-e.pdf | datasheet | 2026-11-15 |
| S11 | Mitsubishi FMF800DXZA-24B datasheet (the -24B family sibling; FMF800DX-24A not found) | https://www.MitsubishiElectric.co.jp/semiconductors/powerdevices/datasheets/sic/fmf800dxza-24b_e.pdf | datasheet | 2026-11-15 |
| S11b | eepower, 800 A 1200 V full-SiC module (2015) | https://eepower.com/technical-articles/new-800a1200v-full-sic-module/ | article | 2026-11-15 (via agent summary) |
| S12 | Semikron Danfoss SKM500MB120SC datasheet, Rev. 1.0 (14.08.2020) | https://assets.danfoss.com/documents/latest/516899/AI498340515663en-000102.pdf | datasheet | 2026-11-15 |
| S13 | DigiKey MSCSM120AM02CT6LIAG listing; Microchip slides on DigiKey forum | https://www.digikey.fi/en/products/detail/microchip-technology/MSCSM120AM02CT6LIAG/12350304 ; https://forum.digikey.com/t/value-proposition-of-cfae-hotspot-3-of-4-msic-power-packaging-modules-slides-from-microchip/39293 | distributor/slides | 2026-11-15 (agent) |
| S14 | Vincotech 10-EY122PA008ME01-LU38F06T datasheet, rev 3 (17 Apr 2026) | https://stvincotechftpassets.blob.core.windows.net/assets/10-EY122PA008ME01-LU38F06T-D3-14.pdf | datasheet | 2026-11-15 |
| S15 | ST ACEPACK search results (not opened): https://www.st.com/en/power-transistors/sh70m12w3ag.html | | product page | not read |
| S16 | Charged Devices, Fuji all-SiC package article | https://chargedevs.com/newswire/fuji-increases-power-density-with-sic-and-new-packaging-technologies | article | 2026-11-15 (agent) |
| T14 | `research/notes/o003-twin-coverage.md` section 4 | repository | internal | 2026-11-15 |
| D19 | `project/decisions/D0019-o003-e008-reference-set-2R-declared-deviation.md`, Context | repository | internal | 2026-11-15 |

## 3. Scoring (Part B key)
"Excluded" = at least one known excluding answer. "Undetermined" = no known excluding answer, but most questions unknown. Nothing is scored "representable today" without answers to the unknown questions.

| ID | Score | Excluded by (feature) |
|---|---|---|
| M1 CAS300M12BM2 | excluded | diode dies (Q9) |
| M2 CAS120M12BM2 | excluded | diode dies (Q9) |
| M3 CAS325M12HM2 | excluded | diode dies (Q9, secondary source; [I-a]) |
| M4 CAB400M12XM3 | undetermined | none known; wire-bonding unconfirmed |
| M5 FF6MR12KM1 | undetermined | none known |
| M6 FF45MR12W1M1_B11 | undetermined | none known |
| M7 NXH010P120MNF1 | excluded | terminal layout: 12 power pins, not three terminals (Q2) [I-d] |
| M8 NXH006P120MNF2 | excluded | terminal layout: 26 power pins (Q2) [I-d] |
| M9 BSM180D12P3C007 | excluded | diode dies (Q9) |
| M10 BSM300D12P2E001 | excluded | diode dies (Q9) |
| M11 FMF800DXZA-24B | excluded | diode dies (Q9); terminal layout (Q2) [I-c] |
| M12 SKM500MB120SC | undetermined | none known |
| M13 MSCSM120AM02CT6LIAG | undetermined | none known (Q9 unknown) |
| M14 flowDUAL E2 SiC | excluded | terminal layout: 26 power pins (Q2) [I-d] |
| 2D_Case_2R (dev layout) | excluded | signal-wire landing (Q14, under rule R0); representable under variant R1 [T14 §5] |
| 2D_Case_6 (dev layout) | excluded | side-by-side blocks (Q12); signal-wire landing (Q14) |
| 2D_Case_4 (dev layout) | representable today (key) | none; its degradation failure (DegradeError, T14 §5) is a separate issue |
| 2D_Case_5 (D19 facts) | excluded | quarter-turned dies (Q8) |

[I-d] The key excludes "not exactly three power terminals". External pins of one net may be tied to a single substrate pad, so this exclusion is conditional. If pins ≠ pads, M7, M8, M14 move to undetermined and M11 stays excluded by diode dies.

Totals, commercial (14): excluded 9, undetermined 5, confirmed representable 0.

## 4. Coverage table and ranking
| Excluding feature | Blocks | Which (known today) |
|---|---|---|
| Diode dies (Q9) | 6 | M1, M2, M3, M9, M10, M11 |
| Terminal layout (Q2) [I-d] | 4 | M7, M8, M11, M14 |
| Signal-wire landing (Q14) | 2 | 2D_Case_2R, 2D_Case_6 (dev layouts) |
| Side-by-side switch blocks (Q12) | 1 | 2D_Case_6 (dev layout) |
| Quarter-turned dies (Q8) | 1 | 2D_Case_5 |
| Multi-substrate, rings, extra strips, dies in several rows, die library, wire count, landing line, die-to-die wires | 0 known | cannot be counted: answers unknown for all commercial modules |

Ranking by modules unlocked (module leaves "excluded" to at least "undetermined" when only this feature blocks it):
1. Diode dies: unlocks 5 outright (M1, M2, M3, M9, M10); M11 still needs terminal layout.
2. Terminal layout: unlocks 3 outright (M7, M8, M14); M11 still needs diode dies. Together with 1 they unlock all 9 excluded commercial modules.
3. Signal-wire landing (rule): 1 outright (2R), 0 more (6 needs side-by-side as well).
4. Side-by-side blocks: 0 outright (Case 6 also needs landing); 1 jointly with 3.
5. Quarter-turned dies: 1 (2D_Case_5), the only module blocked by it; none of the commercial modules is known to need it.

Fraction representable today:
- Commercial only (14): confirmed 0/14 = 0 %. Upper bound if every unknown passes: 5/14 = 36 %.
- With the four PowerSynth rows (18): confirmed 1/18 = 6 % (2D_Case_4 only); upper bound 6/18 = 33 %.
- Without the PowerSynth rows: as commercial only.
- The 80 % target cannot be met by adding quarter-turns and side-by-side blocks alone; on current evidence it needs diode dies and multi-pin terminals, plus whatever the unknowns hide.

## 5. Questions only the vendor or designer can answer
Common to all 14 commercial modules: Q1 (substrate count), Q3 (each net one piece or islands), Q4 (rings), Q5 (branching), Q7 (die array rows × dies per row), Q8 (die orientation), Q10 (wires per die and bond pad), Q11 (landing line), Q12 (side-by-side blocks), Q13 (die-to-die/terminal wires), Q14 gate-landing item, and wire-bonded confirmation.

Per module, in addition:
- M1, M2, M9, M10, M11: die count of the separate diodes (Q9); Q6 die part and size.
- M3: confirm 7 MOSFETs and 6 diodes per switch (not per module); Q6 die size.
- M4: wire-bonded or not; Q2 terminals per net; Kelvin-source wires (only Kelvin drain stated).
- M5, M6, M12, M13: Q2 terminal counts per net, Q6 die size, Q9 (separate diodes, M13 definitively).
- M7, M8, M14: do the 4/4/4, 8/8/10, 8/8/10 power pins land on one pad per net, or several?
- M8: ceramic material behind "HPS", and tile count.
- M11: whether the aP/bP and aN/bN pairs are separate half-bridges in one housing, and chip counts from the chip-location figure.
- M13: construction facts (substrate, wire-bonded).

## 6. thesis_impact
**Weakens, with low confidence.** On datasheet facts alone, 9 of 14 sampled commercial modules (64 %) carry a feature that the generator family excludes, and the two commonest are separate antiparallel diode dies (6 of 14) and multi-pin terminals (4 of 14, conditional on pins mapping to several pads). Neither is in the near-term build list (quarter-turned dies, side-by-side blocks); diode dies are outside O003 scope and appear only in the February-March list (plan section 13). Quarter-turns and side-by-side blocks are known to unlock only 2 rows (both PowerSynth). So the census does suggest that few real modules fit the family after those two extensions alone, though 0 confirmed fits is partly because most questions are unanswerable from free sources, not because they fail. The sample is selected by datasheet availability, includes mostly 62 mm and Easy-class modules, and none of the 14 is confirmed wire-bonded. The census cannot support the 80 % target statement in either direction until section 5 is answered. A representation that handles diode dies and several terminal pads, or a reference-native route (plan section 13), looks more relevant than the two planned extensions.

## Rules I was unsure how to apply
1. CCS050M12CM2: the PREES model is of this commercial part. I treated it as a PREES module and used D0019 only.
2. Q2 pins vs pads: the key's "three power terminals" is about substrate pads; I scored external pins and flagged the sensitivity ([I-d]).
3. Wire-bonding: not stated by any source; scored on inference.
4. The census has 14 commercial modules (below the 15 target); with four PowerSynth rows it has 18 rows. I did not pad.
5. I downloaded public PDFs and installed `pypdf` in the session scratchpad to read them, which the brief did not explicitly mention. Nothing was written inside the repository besides this file.
