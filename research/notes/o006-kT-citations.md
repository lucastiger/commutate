# Secondary-source screen of the k(T) laws and 300 K values in geometry/stack.py (primary check deferred)
Date: 2026-11-01 · Task: T0157 (O006), attempt 3 (founder re-scope I0072) · Confidence: low-medium. This is a screen, not a verification.

## Provenance (read first)
- Opened in this session: `src/moduleforge/geometry/stack.py` (Read tool, full docstring and laws) and the arXiv abstract page 1712.00830 (WebFetch; the tool returns a model summary of the page, not the page image).
- Carried over from attempts 1-2 and NOT re-opened now: search-engine summaries and OCR scan text (S1, S3-S13). Each is labelled with how it was seen. Attempt 2 could not read any PDF (binary returned) or the Ioffe page (TLS error, not bypassed).
- No primary document was opened by any attempt. Statements tagged (review) come from reviews T0174/T0175 and are not confirmed by me. Statements tagged (inference) are my arithmetic or reasoning.

## Answer (≤ 5 sentences)
No k(T) law or 300 K value in stack.py has been checked against an opened primary; Cu 401/393/379 and Al2O3 36.0/26.4/15.8 match scanned Incropera copies, and everything else is secondary, bibliographic-only or not found. The SiC exponent -1.49 originates in Burgemeister et al. 1979 (6H-SiC, normal to c, about 30 % lower parallel to c, per review), so it is a 6H in-plane law applied to a 4H die heated along c. The code's SAC305 alpha = 4.2e-3 /K at a 300 K reference is consistent with the tin coefficient of 4.6-4.7e-3 /K quoted for 0-100 C once the reference temperatures are matched, so no correction is proposed. The Si3N4 exponent -1.0 has no opened source, and the one weak hint (some grades lose up to 45 % over 0-400 C) says -1.0 may be too steep, not too shallow. For P1, sweep SiC k(300 K) 270-390 W/(m K) with exponent -1.25 to -1.50, SAC305 alpha 4.0-5.0e-3 /K, and Si3N4 exponent -0.65 to -1.0 (reasoning below).

## Sources
| id | citation | url | how seen | accessed |
|---|---|---|---|---|
| S0 | `src/moduleforge/geometry/stack.py` (docstring, `K_LAWS`, default layers) | repo | opened, this session | 2026-11-01 |
| S1 | Scanned appendix copies of Incropera & DeWitt property tables (OCR, no column headers) | https://es.scribd.com/document/398809124/App-AThermophysical-Properties-of-Matter-pdf ; https://www.scribd.com/document/548223971/Table-A-2 | secondary scan, OCR text read in attempt 1 | 2026-11-01 |
| S2 | Burgemeister, von Muench, Pettenpaul, "Thermal conductivity and electrical properties of 6H silicon carbide", J. Appl. Phys. 50(9), 5790-5794 (1979), DOI 10.1063/1.326720 | https://scilit.com/publications/e8055c143caf231b8e8a91a70c738915 | bibliographic record only. Exponent, 3.87 W/(cm K) and the c-axis ~30 % are from the review | 2026-11-01 |
| S3 | Ioffe NSM SiC thermal page: 3.6 / 3.7 / 4.9 W/(cm K) at 300 K for 3C / 4H / 6H (Goldberg et al. 2001); T fit 611/(T-115) W/(cm K), 100-2300 K (Nilsson et al. 1997) | https://www.ioffe.ru/SVA/NSM/Semicond/SiC/thermal.html | search summary (page failed TLS); the fit is for 6H per review T0175 | 2026-11-01 |
| S4 | "Thermal conductivity of 4H-SiC single crystals", DOI 10.1063/1.4790134: n-type ~280 W/(m K), T^-1.26; V-doped semi-insulating ~347 W/(m K), T^-1.256; normal to c | https://scispace.com/papers/thermal-conductivity-of-4h-sic-single-crystals-1px5ne0guc | abstract via search summary | 2026-11-01 |
| S5 | Qian, Jiang, Yang, Materials Today Physics 3, 70-75 (2017), arXiv 1712.00830: femtosecond TDTR, 250-450 K, k_r and k_z measured together on n-type 4H, SI 4H, SI 6H; ordering SI 4H > n-type 4H > SI 6H | https://arxiv.org/abs/1712.00830 | abstract page, opened this session via WebFetch summary; no numbers in the abstract, full text not read | 2026-11-01 |
| S6 | Slack, J. Phys. Chem. Solids 34(2), 321-335 (1973), DOI 10.1016/0022-3697(73)90092-9 | https://scilit.net/publications/1030314b23f5bd72f70c209e8643ff7d | bibliographic record only | 2026-11-01 |
| S7 | Hirosaki, Ogata, Kocer, Kitagawa, Nakamura, Phys. Rev. B 65, 134110 (2002): Green-Kubo MD, ideal crystals, 300 K ~105 / 225 (alpha a/c), 170 / 450 (beta a/c) W/(m K); "dependence on temperature was calculated" | https://data.zhenzhi.com/details/1/865259830 | abstract via aggregator | 2026-11-01 |
| S8 | Tatsumi, Togo, Tanaka (2016), arXiv 1612.08480; Zhou & Feng APL (2023) | https://arxiv.org/pdf/1612.08480 | search snippets: MD absolute values >2x experiment | 2026-11-01 |
| S9 | Sn-3.5Ag directionally solidified, J. Mater. Sci.: Mater. Electron. (2011): resistivity and W-F k, 293-476 K, both roughly linear in T | https://link.springer.com/article/10.1007/s10854-011-0350-9 | abstract via search snippet | 2026-11-01 |
| S10 | Metall. Mater. Trans. B (2014), DOI 10.1007/s11663-014-0109-9: k(T) of Sn-10 wt% X binaries | https://avesis.gelisim.edu.tr/yayin/e73f7b2c-41a7-4146-be09-fc2a35eecc40/ | abstract only | 2026-11-01 |
| S11 | US patent application 11411150: SAC305 k drops ~13 % from 25 to 150 C; resistivity rises ~27 % from 25 to 85 C; method not stated | https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/11411150 | search-engine summary of an unreadable scan | 2026-11-01 |
| S12 | Tin temperature coefficient of resistivity 0.0047 /K and 0.0046 /K (both quoted for 0-100 C) | https://machinemfg.com/metal-resistivity-and-temperature-coefficient-table ; https://www.goodfellow.com/usa/tin-spooled-wire-1000186095 | secondary web tables, search snippets | 2026-11-01 |
| S13 | Kyocera SN241O ~54 W/(m K); Syalons Si3N4 19-28; Fraunhofer IKTS 2022 "up to 100" | https://kyocera-solutions.de/fileadmin/user_upload/Download/werkstoffdatenblaetter/siliziumnitrid/Kyocera_Fineceramics_Europe_SN241O.pdf ; https://www.ikts.fraunhofer.de/content/dam/ikts/downloads/annual_reports/2022/15_Highly_thermally_conductive_silicon_nitride_ceramics_for_power_electronics.pdf | datasheet / report search snippets | 2026-11-01 |
| S14 | Springer chapter, doi 10.1007/978-1-4613-3156-8_6: some Si3N4 grades lose up to 45 % of k between 0 and 400 C | https://link.springer.com/chapter/10.1007/978-1-4613-3156-8_6 | search snippet | 2026-11-01 |

## Source-class table (every law and every 300 K value in stack.py)
Classes: **P** primary opened · **S** secondary or scan · **B** bibliographic record only · **N** not found. Nothing is class P.

| Item in stack.py | Code value | Class | Evidence |
|---|---|---|---|
| Cu k(T) law | f = 1 - 1.995e-4 (T-300) | S | Incropera Table A.1 rows 401 / 393 / 379 at 300 / 400 / 600 K in scan [S1]; slope is arithmetic: (393-401)/100/401 |
| Cu k(300 K) | 385 | N | Code says "CRC, ~385 typical for DBC copper". CRC not opened; only the 401 pure-Cu value is in [S1]. 385 is a design choice (inference) |
| Al2O3 k(T) law | log-linear through 36.0 / 26.4 / 15.8 | S | [S1] OCR row for aluminium oxide, no temperature headers, so the column mapping is inferred from layout. Exponents recomputed: -1.0787 and -1.2661, as in code |
| Al2O3 k(300 K) | 24 | N | "Rogers/curamik and CeramTec datasheets" not opened. (96 % grade; the table is 36 for polycrystalline) |
| Al2O3 below 300 K | first segment extended | N | No data; assumption |
| Si3N4 k(T) law | (T/300)^-1.0, "Slack 1973; Hirosaki 2002" | B (Slack), S (Hirosaki abstract) | [S6] record only. [S7] is an ideal-crystal MD abstract; I could not read whether it reports k ~ 1/T. Claim unverified. Treat -1.0 as an assumption |
| Si3N4 k(300 K) | 90 | S (weak) | Only IKTS "up to 100" [S13] supports it; Kyocera SN241O is ~54 [S13]. Vendor and grade dependent |
| SAC305 k(T) law | (T/300)/(1+4.2e-3 (T-300)) | N (SAC305); S for tin | No SAC305 k(T) found. Tin TCR [S12]; Sn-3.5Ag [S9]; Sn binaries [S10] (abstracts) |
| SAC305 k(300 K) | 58 | N | "Lead-free solder handbooks" not opened. W-F check L rho: 2.44e-8 x 300 / 13e-8 = 56.3 W/(m K) is internal arithmetic, not a source |
| Sintered-Ag k | 100-250 W/(m K), docstring only | N | No source opened and `K_LAWS` has no sintered-Ag law (stack.py docstring [S0]); would need a new `Layer.material` |
| 4H-SiC k(T) law | (T/300)^-1.49 | B | Origin is Burgemeister 1979 [S2], 6H, normal to c (review). Record only; exponent not read. Code docstring says "TCAD material files"; no TCAD file found |
| 4H-SiC k(300 K) | 370 | S | Ioffe 3.7 W/(cm K) for 4H [S3], credited to Goldberg 2001, summary only; direction not stated in what I saw. Levinshtein 2001 book not opened |
| SiC "c-axis 330-490" (docstring) | text claim | N | Unverified. Per review these figures are in-plane, do not call them c-axis |

## Findings

### Error fixes required by reviews T0174 / T0175
1. **SAC305 alpha (T0175).** The code's alpha = 4.2e-3 /K is a coefficient about 300 K: rho(T) = rho(300)[1 + alpha (T-300)]. Table values of 4.6-4.7e-3 /K for 0-100 C [S12] are referenced to the cold end of the range. (inference) Re-referencing: if rho = rho_0[1 + a0 (T-273.15)], then alpha_300 = a0 / (1 + a0 x 26.85). For a0 = 4.6e-3 this is 4.09e-3 and for 4.7e-3 it is 4.17e-3 /K, so 4.2e-3 /K at 300 K is consistent with the tabulated tin coefficients (assuming the 0-100 C values are referenced to 0 C, which the snippets do not state). The attempt-2 proposal to move to 4.7e-3 /K at a 300 K reference mixed reference temperatures and is withdrawn. Not a discrepancy.
   - The residual weak datum is S11: k down ~13 % from 25 to 150 C. At a 300 K reference this implies alpha ~ 5.0e-3 /K ((inference): 1.41/(1+123 alpha) = 0.87 x 1.5166 gives alpha = 5.0e-3), and the quoted resistivity rise (+27 % over 25-85 C) implies ~4.5e-3 /K. S11 is a patent summary of an alloy with no method given, so it bounds the sweep (below) and is not a correction.
2. **Si3N4 hint sign (T0175).** S14 says some grades lose up to 45 % between 0 and 400 C, i.e. k(673 K)/k(273 K) = 0.55. (inference) A power law with that ratio has exponent ln 0.55 / ln(673.15/273.15) = -0.66, while -1.0 would give a ratio of 0.41 (a 59 % loss). So for those grades -1.0 is too steep, not too shallow. The attempt-2 sentence that -1.0 "may be too shallow" had the wrong sign. The hint is a snippet about "some grades" and is weak.
3. **Burgemeister 1979 (T0174/T0175).** The -1.49 exponent comes from Burgemeister, von Muench & Pettenpaul, J. Appl. Phys. 50, 5790 (1979) [S2]: 6H-SiC, heat flow normal to c, k ~ T^-1.49 (review states 300-500 K, purest sample, 3.87 W/(cm K) at room temperature), with k parallel to c about 30 % lower (review). I confirmed the title and the 6H subject only; the numbers are the reviewers'. The code applies it to a 4H die heated along c.
4. **Ioffe fit is 6H, not 4H (T0175).** The 611/(T-115) W/(cm K) fit in [S3] is a 6H fit (review). It gives 3.30 W/(cm K) at 300 K (611/185), which matches neither the 4H (3.7) nor the 6H (4.9) table value on that page, so I cannot reconcile it. Between 300 and 480 K it implies an effective exponent ln(185/365)/ln(1.6) = -1.45 (inference, 6H, direction not stated). Attempt 2's use of it as a 4H curve is withdrawn.

### Other points
- Cu and Al2O3: numbers match the scans [S1]; the Cu 400-600 K slope is 12 % shallower than the 300-400 K slope and changes k by <0.2 % over 400-480 K (code docstring arithmetic, [S0]). Pure-Cu data do not describe DBC/baseplate copper (inference).
- Slack 1973 wording: the docstring "The 1/T trend is the phonon-Umklapp law of Slack" overstates. Secondary summaries only say Umklapp-limited k ~ 1/T holds above the Debye temperature in fairly perfect crystals [S6, bibliographic]. Suggested wording: "1/T is the high-temperature Umklapp limit for pure crystals; real sintered ceramics deviate (Al2O3 table exponents -1.08 to -1.27)".
- Do not adopt the attempt-1 SiC values (-1.26, ~280 W/(m K)): they are normal to c [S4], the wrong direction for a vertical die.
- Qian et al. [S5] measured k_r and k_z on 4H together, 250-450 K. It is the right kind of source for cross-plane 4H, but the abstract has no numbers and I have not read the full text.

## P1 sensitivity ranges (exploratory design input, not evidence)
Every range is an inference from the secondary sources above and should be replaced when primaries are read.

| Quantity | Nominal (code) | Sweep range | Reasoning |
|---|---|---|---|
| 4H-SiC through-thickness (c-axis) k(300 K) | 370 W/(m K) | 270-390 W/(m K) | Upper end: Ioffe 3.7 [S3] and Burgemeister's 6H normal-to-c 3.87 W/(cm K) (review) are ~370-390, and no source I saw gives a higher 4H value in the needed direction. Lower end: n-type 4H normal to c is ~280 [S4], and 0.7 x 387 = 271 is the 6H "30 % lower along c" case (review). The S5 abstract ranks n-type 4H below semi-insulating 4H, and power dies are n-type (inference), so the lower half of the range is the relevant one. Direction dependence in 4H is not sourced, so the range is wide on purpose |
| 4H-SiC exponent | -1.49 | -1.25 to -1.50 | -1.26 / -1.256 for 4H normal to c [S4]; -1.49 from 6H normal to c (S2, review); 6H fit implies -1.45 [S3]. The c-axis 4H exponent is unknown. f(480 K) = 1.6^n: n=-1.25 gives 0.556, n=-1.50 gives 0.494 (12 % apart) |
| SAC305 alpha (300 K reference) | 4.2e-3 /K | 4.0e-3 to 5.0e-3 /K | Lower: re-referenced tin tables give 4.09-4.17e-3. Upper: S11 patent k-drop implies 5.0e-3. f(480 K) = 1.6/(1+180 alpha): 0.930 at 4.0e-3, 0.911 at 4.2e-3, 0.842 at 5.0e-3 |
| SAC305 k(300 K) | 58 | not swept here | No source; W-F arithmetic gives 56. Suggest 50-60 only if P1 shows sensitivity (inference) |
| Si3N4 exponent | -1.0 | -0.65 to -1.0 | Lower magnitude: -0.66 from the S14 "up to 45 % loss over 0-400 C" hint. Upper: -1.0 pure-lattice Umklapp limit (assumed, S6 record only). f(480 K) = 0.737 at -0.65 and 0.625 at -1.0 |
| Si3N4 k(300 K) | 90 | 55-100 W/(m K) (inference) | Kyocera ~54 and IKTS "up to 100" [S13]; vendor/grade dependent |
| Sintered Ag k | none in code | 100-250 W/(m K) (docstring) | No source; needs a k(T) law before use |

## Relevance to ModuleForge
E006 compares the solver with references that use the same k(T) laws, so these findings do not change E006 pass/fail. They matter for pilot P1, where the SiC, Si3N4 and SAC305 slopes are uncertain by up to ~10-12 % in k at 480 K; report P1 results over the ranges above.

## Thesis impact: none
Layer-level property uncertainty of order 10 % does not bear on the layout-compiler thesis by itself.

## Open questions
Primaries the founder should obtain (agents cannot open paywalled material):
- Incropera et al., Tables A.1 and A.2 (page images with column headers): confirms Cu 401/393/379 and the Al2O3 column mapping.
- Slack, J. Phys. Chem. Solids 34, 321 (1973): what it says about Al2O3 and Si3N4 and about 1/T.
- Hirosaki et al., Phys. Rev. B 65, 134110 (2002): does it report k ~ 1/T for beta-Si3N4, and over what range?
- Burgemeister et al., J. Appl. Phys. 50, 5790 (1979): confirm the -1.49 exponent, the 3.87 W/(cm K) value, the temperature range, and the parallel-to-c reduction.
- The cross-plane 4H-SiC TDTR paper: Qian et al., Mater. Today Phys. 3, 70 (2017) full text for k_z(T), 250-450 K, or another cross-plane 4H source.
Secondary leads (not required): a measured SAC305 k(T) (Metall. Mater. Trans. B 2014; J. Mater. Sci. SAC305 paper); measured k(T) of AMB Si3N4 substrates, 300-480 K; a sintered-Ag k(T) source; a Sentaurus/Silvaco SiC listing, or drop the TCAD wording in stack.py.
