# Does any commercial tool, service or academic tool already deliver automated or optimization-driven (re-)layout of wire-bonded multichip power modules with parasitic and thermal objectives, how close does each come, and what do customers use today? (A-T6)
Date: 2026-10-31 · Task: founder session (thesis review 2026-10-31) · Confidence: medium

Provenance: written by a general-purpose research agent launched from the founder session (scout subagents could
not run there: python3 3.10 made the guard fail closed). The founder session re-opened S2 (GPL v3, 29 June 2007) and
S3 (latest commits 12–16 Jun 2025, v2.2) and found them as stated; the other sources were not re-checked.

## Answer (≤ 5 sentences)
I found no commercial product or service that automatically synthesizes or re-lays out wire-bonded multichip power modules against parasitic and thermal objectives. The large vendors (Ansys/Synopsys, Siemens including Altair, Cadence, Keysight, COMSOL) sell extraction and thermal analysis plus general-purpose optimizers (Optimetrics/optiSLang, HEEDS, Optimality/Optimus) that tune parameters of a model the user has already built. Siemens comes closest: it markets a "multi-domain optimization solution for embedded and IGBT-style power modules" that it says cuts design time "from months to just a few weeks", but it has not published how the solution works. The closest match in function is academic and free: PowerSynth 2 (University of Arkansas, GPL-3.0, v2.2 released June 2025). Starting from a user's initial layout, it generates design-rule-clean Manhattan layouts optimized for loop inductance and maximum temperature, exports to Q3D, and its models agreed with hardware measurements to within 10–13%; it is not commercialized. Today a customer lays the module out by hand in CAD and iterates in Q3D/Icepak (or the Siemens or Cadence equivalents), sometimes with design-of-experiments scripting or in-house tools; no public source puts a number on how long a derivative re-layout takes.

## Sources
| id | citation | url | type (paper/doc/datasheet/news/filing/repo) | accessed |
|---|---|---|---|---|
| S1 | e3da/PowerSynth2-core repository and README (Univ. of Arkansas E3DA/MSCAD Labs) | https://github.com/e3da/PowerSynth2-core | repo | 2026-10-31 |
| S2 | PowerSynth2-core LICENSE.md | https://raw.githubusercontent.com/e3da/PowerSynth2-core/main/LICENSE.md | repo | 2026-10-31 |
| S3 | PowerSynth2-core commit history (main) | https://github.com/e3da/PowerSynth2-core/commits/main | repo | 2026-10-31 |
| S4 | e3da/PowerSynth2-gui repository | https://github.com/e3da/PowerSynth2-gui | repo | 2026-10-31 |
| S5 | M. Sanjabiasasi, H. A. Mantooth, Y. Peng, "PowerSynth 2: Automated Power Electronics Physical Design Synthesis With Custom and Heterogeneous Components," IEEE OJPEL 6:899–908, 2025, doi:10.1109/OJPEL.2025.3567148 (full text, NSF PAR) | https://par.nsf.gov/servlets/purl/10595462 | paper | 2026-10-31 |
| S6 | I. Al Razi, Q. Le, T. M. Evans, H. A. Mantooth, Y. Peng, "PowerSynth 2: Physical Design Automation for High-Density 3-D Multichip Power Modules," IEEE TPEL 38(4):4698–4713, Apr 2023, doi:10.1109/TPEL.2022.3227300 (accepted manuscript, NSF PAR) | https://par.nsf.gov/servlets/purl/10511312 | paper | 2026-10-31 |
| S7 | ERC Association, "Demonstration of Enhanced PowerSynth-Integrated Physical Design Flow" | https://erc-assoc.org/achievement/demonstration-enhanced-powersynth-integrated-physical-design-flow | news | 2026-10-31 |
| S8 | US Army Research Laboratory, ParaPower repository | https://github.com/USArmyResearchLab/ParaPower | repo | 2026-10-31 |
| S9 | P. Ning, F. Wang, K. Ngo, "Automatic Layout Design for Power Module," IEEE TPEL 28(1):481–487, 2013 (ORNL record) | https://www.ornl.gov/publication/automatic-layout-design-power-module | paper | 2026-10-31 |
| S10 | Y. Zhou, Y. Chen, H. Gao, C. Li, H. Luo, W. Li, X. He (Zhejiang Univ.), "A Layout Optimization Method to Reduce Commutation Inductance of Multi-Chip Power Module Based on Genetic Algorithm," WiPDA Asia 2021 | https://wipda-asia2021.aconf.org/presentation/93.html | paper | 2026-10-31 |
| S11 | S. Fukunaga, T. Funaki (Osaka Univ.), "Chip Layout Optimization of SiC Power Modules Based on Multiobjective Electro-Thermal Design Strategy," IEEJ JIA 11(1):157–162, 2022 | https://www.jstage.jst.go.jp/article/ieejjia/11/1/11_21006215/_article | paper | 2026-10-31 |
| S12 | V. Parque, A. Nakamura, T. Miyashita (Waseda Univ.), "A Study on the Inductance and Thermal Regression and Optimization for Automatic Layout Design of Power Modules," arXiv:2312.08523, 2023 | https://arxiv.org/html/2312.08523v1 | paper | 2026-10-31 |
| S13 | R. Rassmann, Y. Shen, X. Dong, U. Schuemann, R. Mallwitz, "Optimization of semiconductor bare die positions within multi-chip power modules," PCIM 2025 (TIB record) | https://www.tib.eu/en/search/id/vde:566541241 | paper | 2026-10-31 |
| S14 | L. Wan, N. Ripamonti, Y. F. Zhao, R. Soleimanzadeh, A. Schröder, "Design Space Exploration of SiC Power Module Package via Surrogate Model," Key Eng. Mater. 1054:115–120, 2026 | https://www.scientific.net/KEM.1054.115 | paper | 2026-10-31 |
| S15 | 2025 IEEE Design Methodologies Conference (DMC 2025), table of contents (Curran) | https://www.proceedings.com/content/085/085867webtoc.pdf | paper | 2026-10-31 |
| S16 | Ansys Q3D Extractor datasheet (© 2021) | https://ansys.synopsys.com/content/dam/amp/2022/may/asset-creation/q3d-extractor-datasheet/ansys-q3d-extractor-datasheet.pdf | datasheet | 2026-10-31 |
| S17 | Ansys webinar, "Optimizing Thermal Designs with Ansys optiSLang & AEDT Icepak" | https://ansys.synopsys.com/webinars/optimizing-thermal-designs-with-ansys-optislang-and-aedt-icepak | doc | 2026-10-31 |
| S18 | Econ Engineering (Ansys channel partner), "Multiphysics analysis of power electronic module," 2020 | https://econengineering.com/en/blog/multiphysics-analysis-of-power-electronic-module/ | news | 2026-10-31 |
| S19 | J. Victory (onsemi), "A Virtual Prototyping System for Silicon Carbide Power Modules," Ansys IDEAS Digital Forum 2023 | https://ansysevents.ansys.com/event/ideas-digital-forum-2023/planning/UGxhbm5pbmdfMTY0OTU3MQ== | doc | 2026-10-31 |
| S20 | "Synopsys Completes Acquisition of Ansys," 17 Jul 2025 (HPCwire reprint) | https://www.hpcwire.com/off-the-wire/synopsys-completes-acquisition-of-ansys/ | news | 2026-10-31 |
| S21 | Siemens on-demand webinar, "How to design a performance-optimized power module in a week" (J. Parry, R. Dudzinski) | https://webinars.sw.siemens.com/en-US/design-a-performance-optimized-power-module-in-a-week/ | doc | 2026-10-31 |
| S22 | Siemens on-demand webinar, "Multiphysics design optimization of a power module cooling solution" (T. Brodovsky) | https://webinars.sw.siemens.com/en-US/multiphysics-design-optimization-of-a-power-module-cooling-solution/ | doc | 2026-10-31 |
| S23 | J. Parry (Siemens DISW), "Multiphysics Optimization of a Power Module Cooling Solution," NAFEMS World Congress 2025, NWC25-0006833 | https://www.nafems.org/publications/resource_center/nwc25-0006833-rec/ | paper | 2026-10-31 |
| S24 | Siemens, "Power module design flow," technology overview | https://resources.sw.siemens.com/en-US/technology-overview-power-module-design-flow | doc | 2026-10-31 |
| S25 | W. Wessel, S. Liebetegger, F. Bauer, "Integration of S-parameters for power module verification into the engineer's design environment," SemiEngineering (sponsored), 7 Sep 2023 | https://semiengineering.com/integration-of-s-parameters-for-power-module-verification-into-the-engineers-design-environment | news | 2026-10-31 |
| S26 | NAFEMS news, "Siemens completes $10 billion acquisition of Altair Engineering" | https://www.nafems.org/about-us/media/news/industrynews1003/siemens-completes-10-billion-acquisition-of-altair-engineering/ | news | 2026-10-31 |
| S27 | Altair SimLab help, "Flux in SimLab: PEEC Tutorials" | https://help.altair.com/simlab/help/en_us/topics/solutions/SimLabTutoSummaries/FluxInSimLabExamplesMIPSE.htm | doc | 2026-10-31 |
| S28 | K. Alkama, C. Claus, L. Huang, "Parasitic extraction with Simcenter Flux," Siemens Simcenter blog, 11 Sep 2026 | https://blogs.sw.siemens.com/simcenter/parasitic-extraction-simcenter-flux/ | news | 2026-10-31 |
| S29 | C. Schwarz, S. Djordjevic (Noesis Solutions / Cadence), "Optimizing MOSFET Power Modules: A Multi-Domain Simulation Framework…," NAFEMS World Congress 2025, NWC25-0007262 | https://www.nafems.org/publications/resource_center/nwc25-0007262-pres/ | paper | 2026-10-31 |
| S30 | K. Rajendiran, "Accelerating Electric Vehicle Development Through Integrated Design Flow for Power Modules" (summary of a Cadence webinar), SemiWiki, 4 Dec 2024 | https://semiwiki.com/eda/cadence/350961-accelerating-electric-vehicle-development-through-integrated-design-flow-for-power-modules | news | 2026-10-31 |
| S31 | Cadence press release, Optimality Intelligent System Explorer, 8 Jun 2022 (Design-Reuse reprint) | https://us.design-reuse.com/news/52106/cadence-optimality-intelligent-system-explorer.html | news | 2026-10-31 |
| S32 | Keysight W3035E PathWave PEPro product page | https://www.keysight.com/us/en/product/W3035E/pathwave-pepro.html | doc | 2026-10-31 |
| S33 | D. Dingee, "Parasitic characterization comes to power design simulation," SemiEngineering (Keysight-sponsored), 9 Mar 2022 | https://semiengineering.com/parasitic-characterization-comes-to-power-design-simulation | news | 2026-10-31 |
| S34 | COMSOL Application Gallery 121521, "Thermal Analysis of a High-Power IGBT Module" | https://www.comsol.com/model/thermal-analysis-of-a-high-power-igbt-module-121521 | doc | 2026-10-31 |
| S35 | P. Beck, interview with P. Dietrich (Heraeus), Charged EVs, 31 Jul 2018 | https://chargedevs.com/features/heraeus-helps-companies-learn-to-use-cutting-edge-materials-to-improve-ev-electronics/ | news | 2026-10-31 |
| S36 | Fraunhofer IZM, Power Packaging research area page | https://www.izm.fraunhofer.de/en/abteilungen/system_integrationinterconnectiontechnologies/arbeitsgebiete/PowerPackaging.html | doc | 2026-10-31 |
| S37 | Silicon Austria Labs, Power Electronics Service Portfolio (2026) | https://silicon-austria-labs.com/wp-content/uploads/2026/08/POWER-ELECTRONICS-Service-Portfolio-5.pdf | doc | 2026-10-31 |
| S38 | SemiEngineering, "Startup Funding: Q3 2026" | https://semiengineering.com/startup-funding-q3-2026/ | news | 2026-10-31 |

## Findings
**PowerSynth 2: the closest functional match (academic, open source)**
- [S1] The core repository holds "the PowerSynth 2 layout engine, models, optimization algorithms, and the command line interface."
  - Versions: v2.0 added 3-D layout algorithms and electrical/thermal models; v2.1 improved the optimization algorithms; v2.2 added custom devices and power-converter design.
  - Origin and funding: built by the E3DA and MSCAD Labs at the University of Arkansas, co-directed by Y. Peng and H. A. Mantooth, and funded mainly by NSF (POETS ERC), ARL and ARPA-E.
  - Maturity: the README says v2.0 is a "minimal" codebase with many optional or experimental modules removed and not all features exposed.
  - Activity: 6 stars and 4 forks on 2026-10-31, and no GitHub release objects.
- [S2] The licence is GNU GPL v3 (29 June 2007). [S4] The GUI repository is also GPL-3.0, built on Qt 6.5/PySide6. It is "less thoroughly tested than the CLI", and the maintainers recommend the CLI.
- [S3] The latest commits are on 16 Jun 2025 ("v2.2 stable release…") and 13 Jun 2025 ("Update solver for numpy v2 format"). The one before those is 3 Sep 2024 (MOPSO moved to jMetalPy 1.7.0). No later commits were visible on 2026-10-31.
- [S5] (OJPEL 2025) How the layout engine works:
  - Data structures: hierarchical corner stitching plus horizontal and vertical constraint graphs.
  - Three generation modes: minimum-size, variable-size and fixed-size.
  - It handles "2D, 2.5D, and 3D Manhattan layouts". Round footprints are converted to squares "due to the Manhattan layout engine".
- [S5] Optimization and models:
  - Optimizers: MOPSO, NSGA-II and a randomization method.
  - Objectives for power modules: "Minimize the loop inductance and maximum temperature."
  - Electrical model: built-in PEEC plus FastHenry. Thermal model: an open-source reduced-order model (ParaPower, its reference [22]).
  - Device support: v2.1 handled only built-in devices (bare-die SiC MOSFETs and diodes); v2.2 adds user-defined components.
- [S5] Runtimes on dual Xeon Silver 4210 with one thread, 100 layouts by NSGA-II:
  - Single-layer half-bridge module: 70 s to generate and 300 s to evaluate.
  - Multi-layer half-bridge module: 100 s and 1700 s.
- [S5] Other details:
  - The introduction says that in industry "the best layout is usually manually chosen after hundreds of error-and-try iterations" (citing earlier work).
  - The paper is CC BY-NC-ND 4.0.
  - The first author is listed as "Independent Researcher, Sari, … Iran".
- [S6] (TPEL 2023) Inputs and the anchoring to an initial layout:
  - Input is a layer stack, design constraints and a hand-written hierarchical text "layout geometry script". Wire-bond groups are declared in that script and landing points are computed automatically.
  - "PowerSynth 2 layout optimization is dependent on the initial input layout."
  - Components can change relative location across hierarchy nodes, but not within the same node, chosen "as a result of tradeoff between runtime and design variation".
  - Outputs: APIs export to "ANSYS Q3D, SolidWorks, etc.", and the tool exports a distributed RLC parasitic netlist.
- [S6] Model accuracy and validation:
  - Loop-based electrical model: "56 times speedup with 6% accuracy compared to ANSYS Q3D" (2-D case).
  - ParaPower thermal model: "3500 times speedup" within 10% of ANSYS Fluent.
  - A fabricated 3-D wire-bonded SiC module agreed with predictions within 13% (electrical) and within 10% (thermal).
- [S6] Worked 3-D wire-bonded example:
  - Objectives: power-loop (DC+ to DC−) inductance and static maximum junction temperature. Floorplan area was swept over six sizes from 1056 to 2025 mm².
  - Randomization: 200 solutions per size, 100 s to generate and 2500 s to evaluate, on dual Xeon Silver 4210 with 384 GB.
  - NSGA-II: about 1 min per solution.
  - The minimum-size layout gave 3.26 nH at 1 MHz and Tj,max 381.68 K at 2.5 W per device.
  - After manual post-layout tuning the inductance was 2.77 nH. The gate loop "is not optimized".
- [S6] The authors' description of industry practice:
  - Commercial CAD tools "parameterize the design variables… However, they are limited by manually selected parameters… each iteration requires multiple FEA runs".
  - The industry flow is "based on manual and iterative steps".
  - "Most of the commercial modules from the power electronics industry are wire-bonded 2-D designs."
  - Listed as future work: "automatic netlist-to-layout synthesis, changing local relative location… handling non-Manhattan routing".
- [S7] The ERC page names industry liaisons "from Toyota, Wolfspeed, Deere, Caterpillar, and others", but does not say they use the tool.
  - Claims: "1000x speed-up and 100x memory reduction at 10-15% accuracy loss" versus finite-element flows, and 7.1% extraction error versus Q3D at 35× speed-up.
  - PowerSynth 1.4 won the ECCE 2021 student software demonstration. The page says nothing about commercialization.
- [S8] ParaPower ("Back of the Envelope Thermal Analysis", US ARL) is Apache-2.0, written in MATLAB, with 13 stars.

**Other academic layout optimizers**
- [S9] Ning/Wang/Ngo (TPEL 2013): automatic power-module layout design using a genetic algorithm.
- [S10] Zhejiang University (2021): goes from netlist and constraints to a fabrication-ready prototype.
  - Method: graph-based template generation plus genetic-algorithm sizing, with a built-in multi-port discrete circuit model.
  - Objectives: commutation inductance and *balancing branch inductances among paralleled chips*. Demonstrated on a 4-chip SiC module.
- [S5] (its reference [7]) describes the Zhejiang group's TPEL 2022 follow-up: integer-programming layout templates plus a genetic-algorithm Pareto front trading "loop inductance and branch mismatch".
- [S11] Osaka University (2022): NSGA-II over chip placement, using a finite-element multiphysics model of parasitic inductance and thermal resistance; samples were built and measured.
- [S12] Waseda University (2023): 36 design parameters, neural-network surrogates plus differential evolution.
  - Objectives: control-path inductance, main-path inductance and maximum substrate temperature.
  - It notes that "both (expert-based) iterative design and optimization frameworks are time and resource consuming".
- [S13] PCIM 2025 (Rassmann et al.): automates bare-die positioning with automated 3-D Ansys Q3D and Mechanical runs, aiming to cut manual workload.
- [S14] Key Engineering Materials 2026 (Wan et al.): half-bridge with 4 parallel SiC dies per switch and 17 design variables.
  - 4096 Sobol-sampled Ansys Q3D runs trained a surrogate, followed by gradient-based optimization.
  - Objectives: commutation-loop and gate-loop stray inductance, plus mutual-inductance balancing.
  - The abstract claims it "outperforms traditional expert-driven methods".
- [S15] DMC 2025 (Fayetteville, 17–19 Nov 2025) includes three relevant papers:
  - "LAREL: A Reliability-Aware Framework for Power Module Layout Optimization Under Dynamic Drive Cycle Stress" (Agogo-Mawuli, …, Ozpineci, Mantooth).
  - "Reinforcement Learning Based Optimization of Power Modules" (Coelho, Kruse, Rosskopf).
  - "High-Speed Electrothermal Simulations for Power Modules with PEEC and Thermal Resistance Networks" (Coelho, Zhang, Rosskopf).
- (inference) Coelho/Rosskopf are Fraunhofer IISB; their papers are indexed on publica.fraunhofer.de, which blocked my access, so I did not read the abstracts.

**EDA and simulation vendors: analysis plus general-purpose parametric optimization**
- [S16] Ansys Q3D: "The built-in Optimetrics module provides a way to parameterize the geometry… perform design of experiments and optimizations." It links to DesignXplorer and optiSLang, and offers two-way electrothermal coupling to Icepak.
- [S17] optiSLang with AEDT Icepak offers design of experiments, response surfaces, global/local optimization and metamodels. The page does not mention power modules or layout synthesis.
- [S18] Ansys partner Econ Engineering shows a Q3D, Simplorer and Icepak SiC module flow, and claims the tools can "design, analyse or optimise any kind of power module layout", without naming an optimization method.
- [S19] onsemi's in-house virtual prototyping tool:
  - The designer starts from a 2-D DXF of the DBC copper and does die selection and placement, connectivity and port definition by hand.
  - The tool auto-generates 3-D models through Ansys scripting and runs Icepak, Q3D and SPICE.
  - It was validated on onsemi SiC modules.
- [S20] Synopsys completed its acquisition of Ansys on 17 Jul 2025.
- [S21] Siemens webinar claims:
  - Developing a power module "can take many months… and requires intensive engineering effort."
  - The workflow "can be compressed from months into just a few days."
  - Dudzinski's bio: "a new multi-domain optimization solution for embedded and IGBT-style power modules" that will "reduce the time to design a power module from months to just a few weeks."
  - The page does not say what the solution does.
- [S22] Siemens cooling-optimization webinar:
  - EDA-driven layout is linked automatically to 3-D CFD and structural analysis, and stray inductance is evaluated by EM simulation.
  - HEEDS explores "hundreds or thousands" of variations, including SiC MOSFET placement exploration under layout constraints.
  - Multi-objective trade-off: inductance, temperature, pressure drop and warpage.
- [S23] Siemens NAFEMS 2025 talk: a full-bridge IGBT module workflow running from EDA design through electrothermal, thermal, thermomechanical, EM, optimization and reduced-order models. Goals: maximize heat transfer while minimizing pressure drop, inductance and warpage. No tools are named and no numbers are given.
- [S24] Siemens says typical flows leave schematic, layout and simulation unlinked, causing "engineering intensive design iterations", usually on multi-vendor software. It positions an integrated Xpedition flow for power modules.
- [S25] Siemens S-parameter flow (HyperLynx, then Xpedition AMS):
  - Example: three parallel Si IGBTs per switch, where U1 carries 76.46 A, about 14.5 A more than the other two devices.
  - No automated optimization loop is described.
- [S26] Siemens has completed its acquisition of Altair, at about USD 10 billion enterprise value (the page I opened shows no date).
- [S27] SimLab (Altair, now Siemens) offers PEEC tutorials:
  - A "Power Module" tutorial computing Z/S parameters.
  - MOSFET current sharing with a busbar (marked "in progress").
  - Half-bridge loop inductance from 1 Hz to 100 kHz.
  - No automated layout optimization.
- [S28] Simcenter Flux uses PEEC with surface-impedance boundary conditions. On a laminated busbar this cut solve time from 30 min to 2 min. No layout optimization is mentioned.
- [S29] Cadence and Noesis (NAFEMS 2025):
  - Tools: Allegro PKG Designer, Clarity 3D quasi-static solvers, PSpice, Celsius and Optimus.
  - Optimization variables: "MOSFET placement, wire bond diameter, and substrate layout".
  - Objectives: minimize parasitic inductance and thermal resistance. No numbers are given.
- [S30] Cadence's power-module flow (Allegro X, PSpice, Clarity, Celsius) makes no automatic-layout claim and gives no time-savings figures.
- [S31] Cadence Optimality (2022) is an AI-driven multidisciplinary optimizer. Claim: "on average 10X faster than traditional manual methods, with up to a 100X speedup realized on some designs", compared with manual brute-force parametric studies.
- [S32] Keysight PEPro extracts board-layout parasitics for power converters. The product page does not mention power modules or optimization.
- [S33] The Keysight-sponsored article focuses on PCBs: "Simulation often takes a back seat to respinning hardware prototypes until success."
- [S34] COMSOL's gallery has an electrothermal (Joule heating) IGBT-module analysis model. It does analysis only.

**Services and startups**
- [S35] Heraeus (2018): "We can offer simulation and design services." The interviewee adds that customers have been "doing simulations of their model for several decades."
- [S36] Fraunhofer IZM will "develop the design from scratch if necessary." [S37] Silicon Austria Labs lists module packaging and multi-domain coupled simulation services (titles only).
- [S38] None of the startups in the Q3 2026 SemiEngineering funding list is described as doing power-module layout or packaging EDA.

**Inferences**
- (inference) No vendor publicly documents a feature that re-synthesizes placement, traces and wire bonds under design rules from a reference layout plus new dies. Their optimization runs over parameters of a model the user has already built.
- (inference) Siemens' unnamed "multi-domain optimization solution" is the most likely commercial entrant into ModuleForge's value proposition. Its depth cannot be judged from public pages.
- (inference) What a customer uses today:
  - Manual CAD layout, iterated in Q3D/Icepak (or Clarity/Celsius, HyperLynx/Flotherm).
  - Optionally, Optimetrics, optiSLang, HEEDS or Optimus design-of-experiments studies.
  - In-house scripted flows ([S19], [S13]).
  - PowerSynth, at no cost.
- (inference) No primary source gives calendar time or iteration counts specifically for a *derivative* re-layout (die swap, second source or die-count change). The only figures are generic vendor claims ("many months") and qualitative academic statements.

## Relevance to ModuleForge
- **The algorithms are not novel.** PowerSynth already does what ModuleForge plans: a PEEC electrical model with a FastHenry cross-check, a reduced-order thermal model, NSGA-II/MOPSO search, Q3D export and a distributed parasitic netlist [S5, S6]. Fraunhofer IISB is working on PEEC with thermal resistance networks and RL/GA search [S15]. Differentiation has to come from the derivative workflow, not from optimizing per se.
- **Gaps in the sources that ModuleForge could exploit:**
  - Importing the customer's reference layout from CAD. PowerSynth needs a hand-written geometry script, and onsemi's tool starts from DXF with manual placement.
  - Non-Manhattan geometry, which PowerSynth lists as future work.
  - Die swaps and die-count changes inside a fixed housing.
  - Current sharing and gate-loop symmetry as primary objectives. PowerSynth's documented module objectives are loop inductance and maximum temperature, and its gate loop was not optimized [S6]. The Zhejiang work and Wan et al. do target branch balance [S10, S14].
  - Verification decks the customer can run themselves. PowerSynth already exports to Q3D, so this is not unique.
- **Licensing:** PowerSynth is GPL-3.0, so under the permissive-only policy its code cannot be reused. (inference) Running it unmodified as a separate external benchmark tool on public cases is a cheap head-to-head comparison. Its published 3-D case (3.26 nH min-size, 2.77 nH after tuning, ±13% versus hardware) is an external plausibility anchor. This is not legal advice.
- **Thermal reference candidate:** ParaPower is Apache-2.0 [S8] and could serve as the permissively licensed thermal reference that CLAUDE.md says is still to be chosen. Its MATLAB dependence is a practical cost (inference).
- **What the pitch is up against:** the status quo of manual layout plus Q3D/Icepak plus design-of-experiments studies, Siemens' integrated flow, and free PowerSynth. Customer interviews (A-T4, A-T5) should measure derivative re-layout time and iteration counts directly, because public sources do not.

## Thesis impact: strengthens — narrowly
As literally stated, A-T6 ("no incumbent or academic tool already delivers this commercially") survives. I found no commercial synthesis or re-layout product or service. The academic match (PowerSynth 2) is uncommercialized, Manhattan-only, anchored to a hand-authored initial layout, and shows weak adoption signals [S1–S7]. But the evidence weakens any claim that the *capability* is unique:
- Free academic tooling already does electro-thermal layout optimization from an initial layout.
- Siemens is openly marketing power-module optimization with a "months to weeks" pitch [S21].
- Module makers build their own Ansys-scripted tools [S19].

The moat therefore has to be derivative-specific fidelity and customer trust, not "nobody optimizes layouts".

## Open questions
- **Siemens:** what does the "multi-domain optimization solution for embedded and IGBT-style power modules" actually do? Does it move dies, traces and wire bonds under design rules, or only sweep parameters? Is it in use at Toshiba or other customers? (Watching the registration-gated webinar or asking for a demo would settle it.)
- **Real derivative re-layout duration and iteration count** at module makers and OEMs. This is the key quantity behind "removes iterations and weeks". Interview question for A-T4/A-T5.
- **Industry use of PowerSynth:** has anyone (the ERC page lists Wolfspeed, Toyota, Deere and Caterpillar as liaisons) adopted it, and is v2.x still maintained after June 2025?
- **Sources I could not open, so not cited:**
  - e3da.csce.uark.edu was unreachable (DNS failure), so I did not open the PowerSynth release page, the manuals, or the TPEL 2019/2021 PDFs. A search snippet attributes "four to six iterations in the industry" to TPEL 2021, but I could not verify it.
  - The Infineon "Customization by Short Flow" blog (snippet claims 5-month custom development) returned 403.
  - Fraunhofer publica abstracts were blocked by bot protection.
  - The full texts of the Zhejiang TPEL 2022, Mei et al. IET 2020 and Wan et al. KEM 2026 papers returned 403 or were not reachable.
- **Other gaps:**
  - Whether Fraunhofer IISB or the Zhejiang group offer their layout optimizers as contract services or via industrial partners.
  - Chinese EDA vendors were not checked beyond one search (e.g., Xpeedic returned nothing relevant).
  - Altair HyperStudy coupling and the COMSOL Optimization Module were not checked.
