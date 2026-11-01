# Customer outreach playbook — exact steps to the day-45 gate (2026-11-12)

Written 2026-11-01 (day 34) from a founder session. It turns `docs/reports/customer-interview-guide-2026-10-31.md`
into exact steps: whom to contact, the messages to send word for word, the call script, and how to record each call.
Agents never contact anyone. The founder sends every message and holds every call.

## 0. What the next 11 days must produce

| Due | Output | Charter link |
|---|---|---|
| 2026-11-12 (day 45) | At least one prospective customer who says yes to sharing a past reference layout under NDA, with a concrete next step (NDA routed, named contact, date). Who counts as a customer is decision 3 below | day-45 kill criterion, A-T4 |
| every call | Iteration counts, cycle times and achieved vs. target numbers for a real derivative, quoted verbatim | A-T3 |
| every call | What a layout you did not draw must pass before they build it, and in what format | A-T4 |
| every call | Who owns the budget, what outside help they have paid for before, and whether a derivative is coming in the next 90 days | A-T5 (day 90: paid or LOI-backed sprint by 2026-12-27) |
| every call | What they use today: vendor tools, consultancies, in-house scripts, PowerSynth | A-T6 |

Evidence counts only when written to `project/customers/` in the README format and tagged (charter, Kill criteria).
Target: 10 or more conversations held and recorded by 2026-11-11.

**Decide these yourself before the first call. They are your decisions; this document does not make them.**
1. **Who signs an NDA.** Your company, if one is formed, or you personally. Most companies send their own NDA. Have a
   standard mutual NDA ready for those that do not; Common Paper and Bonterms both publish free ones. If you are
   under 18, a contract you sign may not be enforceable against you, so the other side may want an adult or a company
   to sign. Settle this before you ask anyone for a layout.
2. **What you offer for a shared layout.** One option: the first re-layout on a past design is free, in exchange for
   the data and an honest review in their own tools; paid fixed-price sprints come after. Fix a price anchor for when
   someone asks, framed against their cost of one build-and-test iteration.
3. **Who counts as a "customer" for day 45.** A university lab or a consultancy sharing a layout is useful, but it
   is not obviously a customer. Decide before 2026-11-12, and write the answer into the thesis review, not after you
   see who said yes.
4. **Where customer data goes.** Keep it out of this repository (`project/customers/README.md`). **Do not give
   customer files to Claude or any other AI service unless the NDA allows third-party processing.** Most NDAs forbid
   it by default. Promise only what you already do: separate storage, access by you alone, no other use, deletion on
   request. On-prem execution is planned (`docs/ARCHITECTURE.md`, customer-confidential mode), not built.
5. **Recording.** Ask before every recording. California (Penal Code 632) and several other jurisdictions require the
   consent of everyone on the call.

## 1. Day-by-day plan

US daylight saving time ended today, so Pacific time is UTC−8. Central Europe is UTC+1, nine hours ahead: a 17:00 CET
slot is 08:00 PT. Japan is UTC+9, seventeen hours ahead: 17:00 PT is 10:00 JST the next day.

| Day | Do |
|---|---|
| Sun 11-01 | Set up the tracker (§6), signature and calendar link. Decide items 1–5 above. Read the abstracts and write the personal first lines for batch 1 (§3). |
| Mon 11-02 | Send batch 1: every batch-1 row in §3.1 and §3.2, about 20 contacts (script A, B or C). Send warm-intro asks (script D) to everyone you know who might know a power-electronics engineer. Send 10 LinkedIn connection requests (script E); once you run out of personalized notes, send without a note and use script B after they accept. Register for the IEEE SFBAC-PELS talk (§3.3). |
| Tue 11-03 | Send batch 2: the batch-2 rows, about 20 contacts. 10 more LinkedIn requests. |
| Wed 11-04 | Send batch 3: the batch-3 rows plus LinkedIn and job-posting leads from §3.4, about 15 contacts (script B). First calls. 18:00: attend the IEEE SFBAC-PELS talk in San Jose. |
| Thu 11-05 | Bump batch 1 (script F1). Calls. Send recap and data-request emails (script H) within 24 h of each call. |
| Fri 11-06 | Bump batch 2. Calls. Ask every person you spoke to for two referrals, and email those referrals the same day. |
| Mon 11-09 | Bump batch 3. Last bump to batch 1 (script F2). Calls. Follow up on every NDA in progress. |
| Tue 11-10 – Wed 11-11 | Calls. Chase each NDA to a named person and a date. Commit every note. Many US companies observe Veterans Day (11-11); expect fewer replies that day. |
| Thu 11-12 | Commit the last notes. Run `/thesis-review` and judge the day-45 criterion on what is in `project/customers/`. |

Volume: about 60 personal emails and 20 LinkedIn requests. **Plan on roughly one in eight cold messages becoming a
call.** That rate is an assumption, not data. Measure your own after batch 1 and add contacts if it is lower. Warm
introductions convert much better, so ask for them early and often. Do not cold-call: book calls by email or
LinkedIn, and use the phone only when someone gives you a number and a time.

## 2. Introducing yourself and what you may claim

Say plainly who you are and what stage you are at: solo founder, no customers yet, early software. Engineers check.
Anything that looks inflated ends the conversation and the referrals with it. Send from an address on your own domain
if you have one.

**True today (2026-11-01), so you may say it:**
- A fast inductance model (L1, PEEC) ranks generated wire-bonded half-bridge layouts by commutation-loop inductance in
  agreement with an exact in-house reference solver: Spearman 0.996 on 90 layouts at 20 MHz, about 22 ms per layout
  (claim C002). Scope: one DBC stack, generated layouts, layouts differing by about 5 % or more.
- Free academic tools (PowerSynth 2) and vendor optimizers exist. You know them, and you differ from them on the
  derivative workflow (§5.8).

**Not true yet, so do not say or imply it:**
- Any inductance or current-sharing improvement on a real or commercial module. A-T3 is untested; the one public
  comparison suggests about 18 % substrate-only headroom (`research/notes/o003-public-benchmarks.md`).
- Thermal modeling, current-sharing or gate-loop optimization, import of real CAD layouts, or Q3D/Icepak deck export.
  None of these is built.
- Customers, pilots, partners or a team.

## 3. Whom to contact

Compiled on 2026-11-01 by two research agents and spot-checked in the founder session. Every named person below has
public work on this topic. The founder session checked each name against the PCIM 2026 conference contents **[P26]**,
the PCIM 2025 programme **[P25]**, or the URL in the row. Rows marked † come from a source the agents listed that the
founder session did not re-open. Most job titles are unknown, so ask in the call.

- [P26] https://pcim.mesago.com/content/dam/messefrankfurt-mesago/pcim/2027/documents/pdf/en/Inhaltsverzeichnis.pdf
  (the PCIM Europe 2026 programme, despite "2027" in the path)
- [P25] https://download.mesago.de/PCIM/2025/Konferenz/PCIM_2025_Conference_Program.pdf

**Addresses.** Use only published addresses: the corresponding-author line of a paper, a faculty page, or a company
contact page. Otherwise use LinkedIn (script E) or ask a mutual contact. Do not guess addresses. Before writing the
personal line, read at least the abstract; search the title on vde-verlag.de for PCIM papers.

### 3.1 Where a yes to the layout ask is most likely
Large module makers and tier-1s give the best A-T3 and A-T4 facts. Their legal departments, however, rarely approve
sharing a layout with a new solo vendor within 11 days. A day-45 yes is more likely to come from three places: a small
independent module maker, a startup with a new module programme, or an engineer who can share an old or discontinued
design. Put these first in every batch. For organizations with no named contact, find the engineer by the LinkedIn
search in §3.4. Use a custom-module inquiry form only if you say in the first line that you are not buying modules.

| Organization | Why | Evidence | Batch |
|---|---|---|---|
| SwissSEM Technologies (Lenzburg, CH) | A small independent module maker that re-laid out a 62 mm module substrate. Contact Sven Matthias (§3.2). | [P25] PP002 | 1 |
| Powerex (Youngwood PA) | Custom modules are its business. A Dec 2025 posting asks for module layouts, Q3D and FEA | https://jobs.solidprofessor.com/job/251446/design-engineer/ † ; https://www.pwrx.com/pwrx/docs/Custom_Module_Brochure.pdf † | 1 |
| SemiQ (Lake Forest CA) | A small SiC module maker that releases package derivatives often | https://www.semiconductor-today.com/news_items/2026/feb/semiq-180226.shtml † | 1 |
| Sensitron (Hauppauge NY) | Custom hi-rel SiC bridge modules and chip-and-wire hybrids | https://sensitron.com/mobile/Hi_brochure/Capabilities.pdf † | 1 |
| SSDI (La Mirada CA) | Standard, custom and sub-contract modules (2026 catalog) | https://ssdi-power.com/wp-content/uploads/2026/06/SSDI_New_Products2026_1-03W.pdf † | 1 |
| Heron Power (Scotts Valley CA, near you) | A funded SiC solid-state-transformer startup hiring power-electronics engineers | https://simplify.jobs/c/Heron-Power † | 1 |
| Solitron Devices (FL) | Sells SiC half-bridge modules "standard and custom" | https://eepower.com/new-industry-products/solitron-devices-announces-1200v-silicon-carbide-half-bridge-power-module/ † | 2 |
| Apex Microtechnology (Tucson) | SiC half-bridge and three-phase modules (MSA303, Mar 2026) | https://www.apexanalog.com/press/product_news_msa303.html † | 2 |
| CISSOID (BE) | SiC intelligent power modules offered for customization | https://www.electropages.com/2025/05/unique-intelligent-modular-sic-inverter-platform-now-available † | 2 |
| Marel Power Solutions (Plymouth MI) | A startup and DOE SiC Packaging Prize Phase 1 winner (Dec 2024) | https://www.semiconductor-today.com/news_items/2024/dec/doe-sicpackagingprize-051224.shtml † | 2 |
| Texas Instruments high-power modules (Santa Clara, local) | A new 5–300 kW module programme hiring packaging engineers | aggregator posting, ~Oct 2026 † | 2 |
| Alpha & Omega Semiconductor (Sunnyvale, local) | AlphaModule SiC module family, launched 2024 | AOS press release, 2024 † | 3 |

### 3.2 Named people
**Industry: use script A.**

| Name | Organization | Work to cite | Source | Batch |
|---|---|---|---|---|
| Sven Matthias | SwissSEM Technologies, CH | "Automation-Optimized Design for 62mm Power Modules Enabling Enhanced Performance", PCIM 2025, PP002 | [P25] | 1 |
| Michael Frisch | Vincotech, DE (application-specific modules are its business) | "Smart Paralleling of SiC-MOSFET in Power Modules", PCIM 2026, PP091 | [P26] | 1 |
| James Victory | onsemi (modeling and simulation) | "A Virtual Prototyping System for Silicon Carbide Power Modules", Ansys IDEAS 2023. His flow goes from DBC DXF to Q3D/Icepak/SPICE, the same decks ModuleForge would deliver | `research/notes/a-t6-competitive-landscape.md` S19 | 1 |
| Brice McPherson | Wolfspeed, power-module business unit, product development engineer | Optimizing the Kelvin-source connection for paralleled devices in an overmolded module (Wolfspeed article, 2025-04-17) | https://www.wolfspeed.com/knowledge-center/article/breaking-the-mold-redefining-whats-possible-through-product-engineering/ | 1 |
| Habib Mustain | Heraeus Electronics, Power Electronics Segment Manager Americas | Low-inductance module design on multilayer ceramic substrates. He sees many customers' layouts: ask for introductions | https://aaee.uark.edu/?p=1226 | 1 |
| Taegyun Lee | STMicroelectronics, DE | "Intelligent Methodology for Efficient Power Module Design by SPICE-based Virtual Prototyping", PCIM 2025 | [P25] | 1 |
| Dhruvil Patani | Volkswagen, DE | "Optimizing Chip Area in Power Module Design: Comparison of Traditional and AI Surrogate Models for Thermal Resistance Calculation", PCIM 2025, PP130. An OEM sizing die area is the die-count case | [P25] | 1 |
| Naeem Bharmal, Omar Nezamuddin | BorgWarner, US | "Next Generation SiC Inverter with Low Power Loop Inductance and Variable Gate Drive Strength", PCIM 2026, OP096 | [P26] | 1 |
| Michael Fügl | Infineon, DE | "Inductance-optimized Power Module Concept: Balance di/dt Symmetry and Losses by Leadframe Overlap", PCIM 2026, OP097 | [P26] | 2 |
| Christian Schweikert | Infineon, DE | "Quantifying the Impact of a Reduced Stray Inductance to the SiC MOSFET Module-/Inverter Current" (OP109) and "Minimizing Thermal Imbalances in Paralleled SiC MOSFETs" (PP298), PCIM 2026 | [P26] | 2 |
| Jonathan Hackel | Robert Bosch, DE | "Influence of Inductances and Asymmetries on Short-Circuit Behavior for SiC-Based Traction Inverters", PCIM 2025, PP254 | [P25] | 2 |
| Elena Mengotti | ABB, CH | "Investigation of Aging Effects and Current Sharing in a SiC MOSFET Module with Baseplate", PCIM 2026, PP281 | [P26] | 2 |
| Slavo Kicin | Hitachi Energy, CH | "Next Generation 3.3kV LV LinPak Si Power Module with 3AC Design for Traction Applications", PCIM 2026, OP049 | [P26] | 2 |
| Martin Schulz | Littelfuse, DE | "Power Semiconductor Assembly to Boost Power-Density in Commercial Vehicle Drivetrain Designs", PCIM 2026 | [P26] | 2 |
| Alain Calmels | Microchip Technology, FR (Microchip builds custom modules) | "Highly Integrated, Robust Power Solution for Aerospace Motor Drive Applications up to 80 kVA", PCIM 2026 | [P26] | 2 |
| Achim Endruschat | Vitesco Technologies, DE | "… Power Chip Embedding" (traction module), PCIM 2026 | [P26] | 3 |
| Lorenzo Colombini | HPE, IT | "Thermal Modeling of SiC Power Module: A CFD-Based Approach for Junction-to-Fluid Resistance Estimate", PCIM 2025, PP201 | [P25] | 3 |

**Building tools in this space: use script A, batch 2.** These calls are discovery and A-T6 evidence more than sales.
Ask what their tool does, whether it is internal only, and whether it handles derivatives in a fixed housing. Tag the
answers `[A-T6]`. Share no more than the 60-second description in §5.6.

| Name | Organization | Work to cite | Source |
|---|---|---|---|
| Yanfeng Shen, Xiaoting Dong | Semikron Danfoss, DE | "Accelerating SiC Power Module Design via AI Enabled Web Based Virtual Prototyping", PCIM 2026, OP039. With HAW Kiel: "… Multi-Objective Optimization Using PEEC Method", PCIM 2026 | [P26] |
| Lu Wan | Hitachi Energy Research, Baden-Dättwil, CH | "Design Space Exploration of SiC Power Module Package via Surrogate Model", Key Eng. Mater. 1054:115–120, May 2026. A Q3D-trained surrogate optimizes commutation- and gate-loop inductance and mutual-inductance balance for 4 dies per switch | https://www.scientific.net/KEM.1054.115 (affiliation per the paper PDF) |
| Wilfried Wessel | Siemens EDA | "Optimising a Power Module for Electrical and Thermal Performance and Symmetry Using EDA Tools", PCIM 2024 | https://vde-verlag.de/proceedings-en/566262080.html † |

**Academics: use script C, and ask them for introductions.**

| Name | Organization | Work to cite | Batch |
|---|---|---|---|
| H. Alan Mantooth, Yarui Peng | University of Arkansas | PowerSynth 2 (IEEE OJPEL 2025; TPEL 2023). Add the O003 request in §7 | 1 |
| Stig Munk-Nielsen, Szymon Beczkowski | Aalborg University | Current imbalance in 4-die SiC modules (TPEL 2016; EPE 2017). Add the §7 request | 1 |
| Douglas C. Hopkins | NC State (PREES) | Reverse-engineered Cree CCS050M12CM2 model (APEC 2016). Add the §7 request | 1 |
| Rando Raßmann, Ulf Schümann | HAW Kiel (University of Applied Sciences Kiel) | "Optimization of Semiconductor Bare Die Placement in Multi-Chip Power Modules", PCIM 2025, PP131, plus the 2026 PEEC paper with Semikron Danfoss. They are tool builders and a route into Semikron Danfoss | 2 |
| Ivana Kovacevic-Badstuebner | ETH Zurich | PEEC evaluation of internal switching oscillations in SiC multichip modules, PCIM 2026, PP148 (co-authors from Infineon and Ingeteam) | 2 |
| Fei (Fred) Wang, Leon Tolbert | University of Tennessee (UTK) | Basic-switching-cell layouts for lower stray inductance (ECCE 2010) | 2 |
| Christina DiMarino | Virginia Tech, CPES | Medium-voltage SiC module packaging | 2 |
| Fang Luo | Stony Brook | Double-end-sourced wire-bonded SiC module (APEC/ECCE 2016) | 3 |
| Burak Ozpineci | ORNL | LAREL, reliability-aware module layout optimization (DMC 2025) | 3 |
| Rodrigo Coelho, Andreas Rosskopf | Fraunhofer IISB | Reinforcement-learning module optimization; PEEC plus thermal-network simulation (DMC 2025). Tool builders | 3 |

Academic sources: the citations in `research/notes/a-t6-competitive-landscape.md` and `research/notes/o003-public-benchmarks.md`,
and [P25]/[P26] for Raßmann and Kovacevic-Badstuebner.

### 3.3 In person, in the Bay Area
- **Wed 2026-11-04, 18:00:** the IEEE SFBAC-PELS chapter talk at Murata Electronics, 1732 N First St #500, San Jose.
  Free; registration required (https://r6.ieee.org/scv-pels/events/). The topic is magnetics, not modules. Go to meet
  local power-electronics engineers and the chapter officers. What to say: "I'm building software for re-laying out
  power modules when the dies change. Do you know anyone who lays out SiC or IGBT modules?"
- **Alan Tepe, Archer Aviation (San Jose):** inventor on US 12,351,325 B2, "Systems, methods, and mechanical designs
  for inverters for eVTOL aircraft" (assigned to Archer, granted 2025-07-08). His current title is unconfirmed. Ask
  whether Archer lays out its own substrates.
- **Local teams with no named contact yet** (find people with §3.4): Tesla power-semiconductor and module packaging
  (Palo Alto); onsemi module development (San Jose); TI high-power modules (Santa Clara); Alpha & Omega (Sunnyvale);
  Power Integrations automotive module packaging (San Jose); Joby power electronics (San Carlos); Lucid inverter
  (Newark); Kyocera substrates (Milpitas); SimuTech Group, which absorbed Ozen Engineering (Sunnyvale), an Ansys
  partner that knows the local Q3D/Icepak users. All †.

### 3.4 Finding more names (batch 3 onward)
- **LinkedIn people search:** `"power module" AND (packaging OR layout OR design) AND (SiC OR IGBT)`. Also search the
  titles "power module design engineer", "power module packaging engineer" and "package development engineer",
  filtered by the companies above. For second-degree contacts, ask the mutual contact for an introduction (script D).
- **Job postings:** an opening for a power-module design or packaging engineer tells you the team exists. LinkedIn
  often shows the hiring manager. Powerex, Microchip, Tesla, TI, Delta Electronics Americas (RTP) and GE Aerospace
  all posted such roles in 2025–26 †.
- **Conference author lists:** in [P26] and [P25], the sessions "WBG Application and Package", "Design Methods and
  Tools for Power Electronics" and the packaging sessions. Also IEEE DMC 2026 (Aalborg, 18–20 Nov, https://attend.ieee.org/dmc-2026 †).
- **Consortium member lists** (company names only): CPES https://cpes.vt.edu/about/members · ECPE
  https://www.ecpe.org/network/network-members/industrial-members/ · WEMPEC https://wempec.wisc.edu/about-us/current-members/ †
- **Every call:** ask for two names (§5.7).

### 3.5 Events after day 45 (toward day 90)
3D-PEIM 2026, 16–19 Nov, ASU SkySong, Tempe AZ (dates confirmed at https://www.3d-peim.org/) · IEEE DMC 2026,
18–20 Nov, Aalborg † · APEC 2027, 7–11 Mar, New Orleans † · SEMI-THERM 43, 15–18 Mar 2027, San Jose † · PCIM Europe
2027, 11–13 May, Nuremberg †. WiPDA 2026 has already taken place (26–28 Oct).

### 3.6 Competitive signals found while compiling this list `[A-T6]`
These are not in `research/notes/a-t6-competitive-landscape.md`:
- Semikron Danfoss: AI-enabled web-based virtual prototyping, and PEEC-based multi-objective optimization of module
  layouts with HAW Kiel (PCIM 2026).
- HAW Kiel and Danfoss Silicon Power: a funded automated layout-design project running to Oct 2026 †.
- Hitachi Energy Research: Q3D-trained surrogate optimization of loop inductance and mutual-inductance balance (2026).
- Siemens EDA: symmetry optimization of modules (PCIM 2024) †.

Several of your best contacts are building tools of their own. Ask about them in the calls, and consider a scout task
to update the A-T6 note.

## 4. Messages, word for word

Replace everything in `{braces}`. Keep the personal first line specific: name one detail from their work. A generic
compliment reads as a mass mailing.

### A. Cold email to someone whose paper, talk or article you read
**Subject:** Your {venue year} {paper/talk} on {topic}: a question about derivative re-layouts

> Hi {First name},
>
> I read your {venue year} {paper/talk} "{title}". {One specific sentence, e.g. "The per-die currents you measured
> with and without the auxiliary source wire are the clearest data I have found on how layout drives sharing."}
>
> I'm building ModuleForge, software for one specific job: re-laying out a wire-bonded SiC/IGBT module when the die
> generation, die supplier or die count changes inside an existing housing. It targets loop inductance, current
> sharing and gate-loop symmetry, and the results are checked in the customer's own Q3D/Icepak flow.
>
> Before I build further I want to understand how these derivatives really go: how many iterations, what limits the
> result, and what it would take to trust a layout you did not draw. Would you have 30 minutes for a video call this
> week or next? {Day date, time TZ} or {day date, time TZ} work for me, or any time that suits you.
>
> Thank you,
> {Your name}
> Founder, ModuleForge · {phone} · {link}

### B. Cold email with no publication to cite (LinkedIn profile, job posting, product line)
**Subject:** How {Company} handles module re-layouts when the dies change

> Hi {First name},
>
> I came across your work on {product line / "SiC module packaging" / the {role} opening on your team} at {Company}.
> I'm building ModuleForge, software for one job: re-laying out a wire-bonded SiC/IGBT module when the die
> generation, supplier or die count changes inside an existing housing. It targets loop inductance, current sharing
> and gate-loop symmetry, checked in your own Q3D/Icepak flow.
>
> I'm early, and I'm trying to learn how derivative re-layouts actually go before building further. Would you have
> 30 minutes this week or next to tell me about the last one you worked on? {Two slots with time zone}. If someone
> else on your team owns this work, a pointer would help just as much.
>
> Thank you,
> {signature}

### C. Professor or researcher (their view, plus an introduction to industry partners)
**Subject:** Industry practice in module re-layout, and possibly an introduction

> Dear Prof. {Last name},
>
> I have been reading your group's work on {topic}, in particular "{title}" ({venue year}).
>
> I'm building ModuleForge, software for re-laying out wire-bonded SiC/IGBT modules when the dies change inside an
> existing housing. It targets loop inductance, current sharing and gate-loop symmetry, verified in the customer's
> own Q3D/Icepak flow. Right now I'm trying to learn how industry teams actually handle these derivative re-layouts.
>
> Two requests, either of which would help a great deal:
> 1. 20–30 minutes of your view on how your industry partners do this today, and where it hurts.
> 2. If one of your industry partners or former students now lays out modules, would you be willing to forward the
>    short note below?
>
> {Forwardable paragraph from D}
>
> With thanks,
> {signature}

{If the person is on the O003 list in §7, add one line asking for the benchmark data named there.}

### D. Warm-introduction request (to anyone you know)
**Subject:** Quick intro request: power module engineers

> Hi {Name},
>
> I'm working on ModuleForge, software that re-lays out power modules (the semiconductor packages inside EV
> inverters, industrial drives and solar inverters) when the chips inside them change. I need to talk to the
> engineers who design those modules. Do you know one? It could be someone at a chip or module maker (Infineon,
> onsemi, Wolfspeed, Microchip and so on), an EV or aerospace company that designs its own inverters, or a
> power-electronics professor.
>
> If anyone comes to mind, could you forward the paragraph below? I'll take it from there.
>
> > {Your name} is building ModuleForge, software that re-lays out wire-bonded SiC/IGBT power modules when the die
> > generation, supplier or die count changes inside an existing housing. It aims at lower loop inductance, better
> > current sharing and symmetric gate loops, verified in the customer's own Q3D/Icepak flow. {First name} would
> > like 30 minutes with an engineer who has done such a derivative re-layout, to learn how it goes today.
> > {email}
>
> Thank you!
> {Your name}

### E. LinkedIn connection note (under 200 characters; free accounts get only a few notes a month)
> Hi {First name}, I'm building software to re-lay out SiC/IGBT modules when dies change in a fixed housing. Could
> I ask about your last derivative layout in a 20-min call?

Once they accept, send script B as a LinkedIn message, shortened to its second paragraph and the ask.

### F. Follow-ups (reply in the same thread, never a new email)
**F1, 3 business days later:**
> Hi {First name}, bringing this back to the top of your inbox. Even 15 minutes would help, and if someone else owns
> derivative layouts at {Company}, a name would be just as useful. Thanks, {Your name}

**F2, 2 business days after F1 (short, because of the deadline). This is the last one:**
> Hi {First name}, last note from me on this. If the timing is wrong, no problem at all. If you can spare one line:
> roughly how many layout-and-build iterations does a die-change derivative take at {Company}? That alone would
> help. Thanks, {Your name}

A one-line answer to F2 is A-T3 evidence. Record it as a short note in `project/customers/`.

### G. Calendar invite
**Title:** ModuleForge × {Company}: 30 min on derivative module re-layouts
> Thanks for making time. Agenda: (1) your last derivative re-layout: what changed, how many iterations, what
> limited it (15 min); (2) how a layout is verified and signed off before it is built (5 min); (3) what I'm building,
> and whether a test on a past design makes sense (10 min). I won't share anything that identifies you or {Company}
> without asking first.

### H. Recap and next step (within 24 hours of every call)
> Hi {First name},
>
> Thank you again for the time today. What I took away, in your words:
> - {verbatim point 1}
> - {verbatim point 2}
> - {verbatim point 3}
>
> {If they agreed to share a layout:} As we discussed, to re-lay out {the past design} I would need the items below.
> An older or discontinued product is ideal.
> 1. The substrate layout as DXF, STEP or the Q3D project, whichever is easiest.
> 2. The layer stack: copper and ceramic thicknesses and materials, baseplate, die attach.
> 3. Your design rules: copper spacing and isolation distances, edge margins, wire-bond rules (wire diameter, maximum
>    loop length, pad sizes, bond-head clearance).
> 4. What is fixed: housing outline, terminal and pin positions, and anything else that cannot move.
> 5. The old and new die data: size, pad positions, and losses at your operating point.
> 6. The thermal boundary: cooling and baseplate or heatsink conditions.
> 7. Anything you measured or extracted on the reference (loop inductance, per-die currents, Tj), if you can share it.
>
> I'm happy to sign {Company}'s NDA. Who should I send my details to? {Or: I've attached a standard mutual NDA in
> case that is easier.}
>
> {If not:} You mentioned {referral}. Would you be willing to introduce us? The paragraph below is ready to forward.
>
> Best,
> {Your name}

## 5. The call (30 minutes)

Rules for the whole call:
- Ask about **what happened last time**, not what they would do in the future. "How many iterations did your last
  one take?" produces evidence. "Would a tool like this help?" does not.
- **Get numbers and quote them verbatim.** When you hear "a few weeks", ask "Roughly how many: three, eight?"
- Say nothing about the product until block 6. If they ask early, say "Happy to tell you at the end; first I'd
  love to hear how you do it today."
- Let silence work. Do not fill a pause or suggest answers.
- Separate facts from your interpretation in the notes.
- At the end of each block, check that you have the items under "Leave with".

### 5.1 Opening (2 min), word for word
> Thanks for making time, {First name}. Quick context: I'm {Your name}, and I'm building ModuleForge, software for
> re-laying out wire-bonded modules when the dies change inside an existing housing. I'm early, and the most useful
> thing for me is to hear how this really goes for you. I'll mostly ask about the last derivative you worked on, and
> at the end I'll tell you what I'm building and ask one or two things. Is 30 minutes still OK? Do you mind if I take
> notes? {Optional: Would it be OK to record, just for my own notes? Completely fine if not.} I won't share anything
> that identifies you or {Company} without asking you first.

### 5.2 Context (3 min)
- "What's your role, and roughly how many module layouts have you personally worked on in the last two years?"
- "What kinds of modules: half-bridge, six-pack, full-bridge? SiC or IGBT? How many dies in parallel per switch?
  DBC or AMB? Wire-bonded, or clips and sintered top-side?"
- "How often does a derivative come up: a new die generation, a second-source die, or a different die count in an
  existing housing? How many a year on your team?"

Leave with: role, module types, die counts per switch, number of derivatives per year. `[A-T5]` (frequency)

### 5.3 The last derivative, in detail (10 min) `[A-T3]`
- "Think of the most recent time a module had to be re-laid out because the die changed. What exactly changed: the
  generation, the supplier, the count, the die size, the pad positions?"
- "What had to stay fixed: the housing, baseplate, terminals, pin positions, substrate outline, the stack?"
- "Walk me through it, from the day you got the new die to release. What were the steps?"
- "How many layout versions did you make before the one that shipped? How many of those did you build hardware
  for?" Keep simulation versions and hardware builds as separate counts.
- "How long did one hardware iteration take, from layout to substrate order to assembly to test? What was the long
  pole?" Quote it.
- "How many people worked on it, in what roles?"
- "Was there a target: a loop-inductance number, a current-sharing spec, a Tj limit? What did you end up with
  compared with the reference design?" Get the numbers, for example "loop inductance went from 12 to 9 nH".
- "What limited the result? If you had had two more weeks, what would you have changed?" This probes for
  performance left on the table.
- **Current sharing:** "With {N} dies in parallel, how unequal were the currents, static and during switching? How
  did you find out, simulation or measurement? Did you derate the module because of it?" This tests A-T3's
  50 %-mismatch branch, which public data cannot settle.
- **Gate loop:** "Did you check gate-loop symmetry across the paralleled dies? Any oscillation problems?"
- **Thermal:** "How close to the Tj limit did you end up? Did one hot die set the rating?"
- **Manufacturing rules:** "Which rules bit you: wire-bond length or angle, bond-head clearance, copper spacing for
  isolation, solder or sinter keep-outs, the supplier's substrate rules?"
- "What did the derivative cost all in: engineer time, prototypes, test, and the cost of being late?"

Probes for any answer: "Can you give me the number?" · "Was that typical, or was that one unusual?" · "What
happened next?" · "Why?"

Leave with: what changed and what was fixed; simulation versions and hardware builds; weeks per hardware iteration;
target vs. achieved numbers; the limiting factor; how bad current sharing was; cost.

### 5.4 Verification and trust (5 min) `[A-T4]`
- "Before a layout gets built, what checks does it have to pass, and who signs it off?" (DRC, Q3D, Icepak,
  mechanical, reliability, supplier rules, design review)
- "Suppose someone handed you a layout you didn't draw, together with Q3D and Icepak projects you could run
  yourself. What would you need to see before you would build it?"
- "In what format would it have to arrive: DXF, STEP, an AEDT project, your CAD (AutoCAD, SolidWorks, Allegro,
  Xpedition)?"
- "What would make you reject it outright?"
- "Can design data leave your building at all? Would a tool have to run on your own machines?"

Leave with: sign-off chain, the acceptance conditions, rejection reasons verbatim, required format, data
constraints.

### 5.5 Alternatives and money (5 min) `[A-T6]` `[A-T5]`
- "Have you tried to automate any of this: Optimetrics or optiSLang, HEEDS, PowerSynth, in-house scripts? What
  happened?" `[A-T6]`
- "Have you ever paid outside help for layout or simulation: consultants, Fraunhofer, the substrate supplier,
  Ansys or Siemens services? For what, and roughly what did it cost?" Past spending is the best price evidence you
  will get. `[A-T5]`
- "Who owns the budget for a derivative? Who would sign a purchase order for outside layout work, and how long does
  that take?" `[A-T5]`
- "Is a derivative coming up in the next three months?" `[A-T5]` (timing for day 90)

Leave with: the alternatives they have tried and why those stopped; past outside spend; the budget owner and PO
path; the next derivative and its date.

### 5.6 What you are building, and the ask (5 min) `[day-45 gate]` `[A-T4]`
Describe the product in about 60 seconds, word for word:
> Here's what I'm building. The goal: you give it the reference layout, the housing and stack, your design rules
> and the new dies, and it returns manufacturable re-layouts (die placement, copper, wire bonds) scored for
> commutation-loop inductance, current sharing between paralleled dies, gate-loop symmetry and junction
> temperature. It also gives you Q3D and Icepak projects, so you check the result in your own tools. Where it is
> today: the fast inductance model is built and agrees with an exact reference solver on generated half-bridge
> layouts. Thermal, and running it on a real customer design, are not done yet. That is why I'm asking for a past
> design.

Then ask, word for word:
> The most useful next step for me would be to try this on a real past design. Could you share one older reference
> layout (the substrate layout, stack, design rules and die data) under an NDA? I would do the re-layout, and you
> would check it in your own tools. An old or discontinued product is ideal.

- **If yes:** "What would your legal team need? Do you have your own NDA, or should I send one? Who should I send
  it to, and by when?" Write down the person and the date.
- **If no:** "What would have to be true for that to be possible?" Then offer a smaller step: "Could you share just
  the stack and design rules, with a sanitized or dummy layout?"
- **If they hesitate over money or priority:** "If the re-layout on your past design beat what you shipped and checked
  out in your tools, what would have to happen for you to pay for a sprint on your next derivative before the end
  of the year?" `[A-T5]`

### 5.7 Close (1 min)
- "Who else should I talk to, inside or outside {Company}? Would you be willing to introduce me?"
- "Can I follow up on {the NDA / the data} on {date}?"

### 5.8 Questions they will ask you, and honest answers
- **"How is this different from PowerSynth / optiSLang / HEEDS / Siemens?"** PowerSynth optimizes a layout you write
  by hand in its own script format, for loop inductance and maximum temperature, Manhattan geometry only.
  optiSLang and HEEDS sweep parameters of a model you have already built. ModuleForge starts from your existing
  layout and housing, and aims at current sharing and gate-loop symmetry as well as loop inductance and Tj. It is
  early, which is why I want to test it on a real past design. (Source: `research/notes/a-t6-competitive-landscape.md`.)
- **"What results do you have?"** The inductance ranking result in §2, with its scope. No results on a real
  module yet.
- **"Who are you, and who is on the team?"** The plain truth (§2).
- **"Where would our data go?"** Only what you decided in §0 item 4.
- **"What does it cost?"** Your anchor from §0 item 2. Then ask: "What did your last outside layout or simulation
  work cost?"
- **"Can we see a demo?"** "Not on a real design yet. Doing that on one of yours is the point of the pilot."
- **"Can it handle {feature}?"** If it is not built, say so: "Not yet. Is it a must-have for you?" Then write it
  down as a requirement, tagged `[A-T4]`.

### 5.9 Reading the result honestly
- **Strong signal:** they agree to share a layout and name the next step (NDA routing, a person, a date). They
  introduce you to their manager or budget owner. They name a derivative coming up, with a budget.
- **Medium signal:** a second meeting with more people. They send the stack and design rules but not the layout.
- **Not evidence:** "interesting", "keep me posted", "send me a deck", compliments. Record these as they were said
  and do not count them.

## 6. Tracking and recording

**Tracker** (a spreadsheet outside the repository: it holds names and addresses). Columns: name · organization ·
role · segment · source and hook · channel · date sent · F1 date · F2 date · status (sent / replied / booked / held /
declined / no reply) · call date · note file · layout-under-NDA answer · referrals.

**Note per conversation**: write it within two hours of the call, as `project/customers/YYYY-MM-DD-<company-or-alias>.md`.
Use an alias if the company should not be named in the repository. Template:

```markdown
# <Company or alias> — <YYYY-MM-DD>
Who: <role, team, years in role>; found via <cold email / intro by … / LinkedIn>
Context: <segment; module types; SiC/IGBT; dies per switch; DBC/AMB; derivatives per year> [A-T5]
Last derivative: <what changed; what stayed fixed>
Iterations and cycle times (verbatim): "<…>" [A-T3]
Target vs. achieved: <loop L, current sharing, Tj, with numbers> [A-T3]
What limited the result: <…> [A-T3]
Tools and sign-off: <…> [A-T4]
Accepting an outside layout: conditions "<…>"; rejection reasons "<…>"; format <…> [A-T4]
Data handling: <can data leave; on-prem needed> [A-T4]
Alternatives tried: <…> [A-T6]
Budget owner, PO path, past outside spend: <…> [A-T5]
Upcoming derivative (next 90 days): <…> [A-T5]
Reference layout under NDA: exact words "<…>"; next step <…>; who <…>; by <date> [day-45 gate] [A-T4]
Objections: <…>
Referrals: <…>
Follow-ups: <…>
My read (interpretation, kept apart from the facts above): <…>
```

Commit each note yourself, as the founder (`project/customers/` is excluded from the loop's state commits):
`git add project/customers/<file>.md && git commit -m "customers: <date> <alias> [A-T3][A-T4]"`.
Never commit customer files, drawings or data. Reference them by an ID kept in your private data vault. Things said
under NDA belong in the vault, not in the note.

If you held conversations before the laptop theft whose notes were lost, reconstruct each now in the same format,
marked `Reconstructed on 2026-11-0x from memory`.

## 7. Also ask, when you contact these authors (benchmark data for O003, day 60)

The founder alone may contact authors (`research/notes/o003-public-benchmarks.md`, Open questions).
- Morgan, Xu, Hopkins, Husain and Yu (NC State, APEC 2016): where is the "open source" 3D CAD model of the
  reverse-engineered Cree CCS050M12CM2 six-pack hosted?
- The PowerSynth authors (University of Arkansas): the measured inductance tables of the Evans TPEL 2019 test
  vehicles and the Al Razi TPEL 2021 module, which were not readable in the extracted text.
- The Aalborg authors (Li, Munk-Nielsen, Beczkowski): layout dimensions of the 4-die Danfoss test half-bridge used
  for the current-sharing measurements.
