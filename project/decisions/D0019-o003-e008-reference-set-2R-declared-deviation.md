# D0019 — O003's judged references stay D0010's public fallback; no screened public module is usable; E008's F3 deviation on 2D_Case_2R and 2D_Case_6 is declared
Date: 2026-11-12 · Status: accepted · Decider: founder (founder session, 2026-11-12) · Relates to: D0010, D0018; E008
draft

## Context
- No customer reference layout was shared by 2026-11-12 (I0140, answered 2026-11-11). Under D0010 and O003, the judged
  set is therefore the public fallback: PowerSynth 2D_Case_2R and 2D_Case_6, labelled "public benchmarks, low power,
  indicative".
- Both were loaded before E008's freeze. T0263 (on main 2026-11-11 01:01 UTC) reconstructed them, measured their rules
  and ran the twin and degradation at L1; both raised TwinError. T0314 (research, on main 2026-11-11 18:26 UTC) ran L0/L1
  variants on them; under variant R1 (no minimum gate-wire length) 2R's twin matches its power copper exactly and its
  degraded copy reaches an L1 ratio of 1.395 against the 1.388 target. 2D_Case_6 stays outside the twin space (switch
  blocks side by side with wires in opposite directions).
- E008 changed after that, in its runner and spec only:
  - T0316 (D0018 decisions 1 and 2, found on the development layout 2D_Case_4);
  - T0317 (D0018 fix-list item 1, prompted by 2R; and, from review T0318, solver failures in D's band solves make the
    run INVALID).
  No code under src/ (generator, twin, degradation, search, DRC) has changed since 2026-11-10 11:31 UTC (T0300), before
  either reference was loaded. Nothing beyond L0/L1 facts was known about either reference when these changes were made:
  no inductance solve, thermal solve or search has been run on them.
- To find an unseen judged set, the founder ran two fact-only screens in a claude.ai chat, outside the repository. Only
  yes/no facts and citations came back; no geometry reached the project. Both were received after D0018's fix list was
  committed (5fa0d7a5) and after T0317 merged.
  - NC State PREES (Prof. D. C. Hopkins). The reverse-engineered Cree/Wolfspeed CCS050M12CM2 model is a six-pack whose
    DC+ and DC- are shared by its three legs, and it has separate antiparallel diode dies. Its CAD file and licence were
    not found. No documents were found for the lab's 3.3 kV open-source test package or its APEC 2021 test modules.
  - A wider public search found one module passing every fact test: PowerSynth 2 sample design 2D_Case_5 (unseen by the
    project). A follow-up found that its two switch positions' dies differ by a quarter turn. E008's frozen twin needs
    identical dies (src/moduleforge/generate/derivative.py line 246); die rotation is outside the generator's space
    (line 31); reconstruction rule M1 chooses only 0° or 180°. So it would be excluded under F1(a), and representing it
    would need a generator change prompted by a screened candidate's facts. Every other module found failed a test or
    has no open full geometry.

## Decision
1. **Reference set unchanged.** O003's judged references remain D0010's public fallback, 2D_Case_2R and 2D_Case_6, with
   the label "public benchmarks, low power, indicative". O003 is not amended. 2D_Case_6 is expected to be excluded under
   F1(a) and is reported with its reason. 2R is then the only counted reference, so any verdict goes to the founder
   review first (O003; D0017).
2. **Declared F3 deviation.** O003 F3 requires the generator, twin, degradation rule and search to be frozen before any
   judged reference is loaded. For 2R and 2D_Case_6 this did not hold. The deviation is exactly the T0316 and T0317
   changes listed above, made with L0/L1 facts about the references and no inductance, thermal or search result. The
   change prompted by 2R removes a lower bound on gate-wire (and Kelvin-wire) length. It changes no power-copper,
   power-wire or die rule. E008's spec states this deviation, and every statement of the verdict carries it with the
   label.
3. **No further model change.** D0018's rule continues: until registration, the generator, twin, degradation rule, rules
   and search do not change, and the screen answers above are known. The remaining pre-registration work is the
   registered path: loading the judged references, their records, and the cost plan. Any further model change needs a
   new founder decision.
4. **No further look at the judged references before the freeze.** Until E008's code (including judged-reference
   loading) is frozen in its spec, 2R and 2D_Case_6 are only rebuilt from the frozen T0263 reconstruction script, to check
   their fingerprints and count mesh sizes. No twin, degradation, inductance, thermal or search run is made on them
   before registration.
5. **Scope_in reading restated** (D0018 fix-list item 1). O003 scope_in's enumerated design rules are the complete
   meaning of "design rules at least as strict as the reference's own".

## Consequences
- **Next step: the judged-reference loading task.** Then the full-fidelity development run on the VM, the founder
  decisions E008 lists before registration, any budget change, registration and the run. The run must start by about
  2026-11-22 to finish by 2026-11-24 (O003).
- **No snapping check is needed.** 2R is already on the 0.5, 0.25 and 0.125 mm grids (T0263: 0 snap records, s_ref = 0).
  O003's snapping check applies only to a reference that is not on the 0.5 mm grid.
- **The cost plan will be smaller.** It is re-run on the real reconstructions: 2R has 1.49 M l2_layout unknowns at
  0.25 mm, against the 4.11 M Case 4 proxy E008's estimate used.
- **The verdict is weak evidence.** It rests on a software tool's sample, on one counted reference, and on a declared
  deviation. INCONCLUSIVE is the likely outcome (D0010).
- **Kept as candidates for after day 60, under a new experiment id:** 2D_Case_5, 2D_Case_6, the open PowerSynth cases
  (2D_Case_3, Manual_2D_Case) and any NC State module whose files Prof. Hopkins can point to. A generator extension for
  quarter-turned dies and side-by-side switch blocks would be a new founder decision. Its facts, but not its geometry,
  are known for 2D_Case_5.

## Alternatives considered
- **NC State PREES modules as the judged set:** none passes the entry rules, or none has documents.
- **2D_Case_5 as a clean judged reference** (alone, with 2R, or with 2R as a fallback): not representable without a
  generator change prompted by its screened facts, and not feasible before 2026-11-24.
- **No E008 run before day 60:** the day-60 criterion counts as INCONCLUSIVE (D0011), with no measurement. Rejected: the
  registered path is needed for any later reference, and a measured, labelled number informs the thesis review.

## Erratum (2026-11-12, founder session, with the founder's permission)
Two times in Context were local Pacific time labelled UTC. T0263 reached main at 2026-11-11 09:01 UTC (not 01:01 UTC).
The last change under src/ (T0300) is 2026-11-10 19:31 UTC (not 11:31 UTC). T0263's run started at 2026-11-11
06:23 UTC, after T0300, so the statement that src/ has not changed since before either reference was loaded stands.
Nothing else changes.
