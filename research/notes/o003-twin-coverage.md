# O003: twin and degradation coverage on 2D_Case_2R, 2D_Case_6 and 2D_Case_4 — which rule binds (L0/L1 only)
Date: 2026-11-11 · Task: T0314 (O003) · Author: scientist agent · Status: diagnosis and prototypes; no frozen code changed

Script: `research/scripts/o003_twin_coverage.py`. Output: `research/o003/twin_coverage/results.json` (deterministic: floats
rounded to 10 significant digits, no timings). Labels: **[F]** = fact, with the file, line or results.json key it comes from.
**[I]** = inference. Every number below is in results.json under `layouts.<name>.variants.<variant>` unless another
source is given.

**Headline.**
- **2D_Case_2R** fails on one rule, `min_signal_wire_length`. Without it (R1) the twin is exact on the power copper and
  D reaches the target: L1(D)/L1(W) = 1.395 ≥ 1.388. O003 does not require that rule. It comes from `measure_rules`,
  which E008 uses unmodified.
- **2D_Case_6** fails on structure, not on a rule. Every variant raises at twin.py's candidate filter.
- **2D_Case_4** fails on `min_width_power` = 5 mm, the reference's own minimum power-net width. O003 scope_in requires
  that rule. With it relaxed to 1 mm, move 1 alone reaches 1.421. That is twin.py's recorded 1.421, which was measured
  under the default 1 mm rule. Neither prototype degradation reaches the target under the required rules: 1.260 and
  1.240 at best.

## 1. Item 1: recorded outcomes and rule variants

Construction ([F] script `build_layouts`):
- 2R and Case 6: `spec_from_layout(PS.snapped(ref)[0], measure_rules(...)[0], KEEPOUT_NETS)`.
- Case 4: E008's own `dev_reference('case4', cfg)`. This is measure_rules plus the E008.yaml dev overrides: pitch at the
  defaults, `max_wire_length` 18 mm, assumed gate/Kelvin pads, and a 25 mm signal-wire limit
  (experiments/drafts/E008.yaml lines 297-327).

All three R0 outcomes match the recorded ones [F]:
- 2R: TwinError, `signal_wire_length`, 4.597 mm outside [5.344, 10.396] mm.
- Case 6: TwinError, "no (orientation, sequence)".
- Case 4: twin mode fit+signal_feet, then DegradeError at 1.232 after a 75-step walk.

| layout | variant | twin mode | error | symdiff per net DC+/DC-/PHASE (mm², fraction) | L1(W)/L1(ref) | degrade moves (skips: binding rules) | walk terminal | L1(D)/L1(W) vs 1.388 |
|---|---|---|---|---|---|---|---|---|
| 2R | R0 | – | TwinError `signal_wire_length` (LS gate wires 4.597 mm < 5.344) | – | – | not run | – | – |
| 2R | **R1** | fit | none | 0 / 0 / 0 (0.0) | 1.0000 (11.170 nH both) | spread[2,up]×1 mm, spread[3,up]×1 mm, 16 walk steps. Skipped: narrow/centre_landing (min_trace_width, min_spacing), spread[2,down], [1,down] (edge_margin, min_trace_width), [1,up], [3,down] (min_spacing, min_trace_width). Stopped: spread[2,up] (min_trace_width), [3,up] (edge_margin) | target_reached (start 1.044) | **1.395 ≥ 1.388** |
| 2R | R2 | skipped | no citable minimum (below) | | | | | |
| 6 | R0 / R1 | – | TwinError "no (orientation, sequence)" | – | – | not run | – | – |
| 4 | R0 (= R1: no lower bound set) | fit+signal_feet | DegradeError 1.232 | 0 / 0 / 0 (0.0) | 1.0017 | narrow_landing (bands 5.0 → 5.0 mm: already at the minimum), 75 walk steps. Skipped: centre_landing (changes nothing), all six spreads (min_spacing to GATE_HS/GATE_LS, 1.5 < 2.0 mm) | local_maximum (start 0.996) | **1.232 < 1.388** |

R3, one measured field relaxed to its effective DRC default ([F] `variants.R3:*`). Variants whose effective rules equal a
variant already run are reused (`same_effective_rules_as`).
- **2R:** 23 fields. Only `min_signal_wire_length` (which equals R1) removes the TwinError. Every other single
  relaxation still raises `signal_wire_length`. **Binding rule: min_signal_wire_length.**
- **Case 6:** 20 fields. Every one still raises at the candidate filter. **No rule binds**: the failure is structural
  (section 3).
- **Case 4** (DegradeError, terminal ratio L1(D)/L1(W)):

  | relaxed field | terminal ratio | notes |
  |---|---|---|
  | `min_width_power` 5 → 1 mm | **1.421, target reached** | moves 1-2 only, no walk |
  | `die_spacing` 6 → 1 | 1.293 | |
  | `die_edge_margin` 2 → 1 | 1.286 | |
  | `spacing_other` 2 → 1 | 1.248 | |
  | `spacing_signal_dcp` → 1 | 1.247 | |
  | `edge_margin`, `spacing_dcp_dcm`, `spacing_signal_phase` | 1.232 | |
  | the other relaxed fields | 1.232 unchanged | |
  | X: `max_wire_length` 18 mm → 1 m | 1.243 | outside R3: an E008 override, not a measured rule |

  **Binding rule: min_width_power.** No other single relaxation reaches the target.

**R2 skipped.** One web search and one fetch found no citable minimum gate-wire length for 0.30 mm Al wedge bonds. The
Tyndall design-rule PDF returned 404. `DesignRules.min_wire_length` = 1.5 mm (src/moduleforge/drc/rules.py line 31)
is one of the defaults the module docstring (lines 6-7) calls placeholders, so it is not a source.
- [I] Any physical minimum at or below 4.597 mm would make R2 behave like R1 on 2R. This rests on no citation.

**Lower bound vs O003 scope_in.**
- [F] The O003 bondability text (project/objectives/O003/objective.yaml lines 61-63) bounds the gate wire from above only:
  "each die's gate pad within the reference's longest gate-wire length of the fixed gate copper ... and no gate or
  Kelvin wire crossing a wire of another net in plan view".
- [F] The lower bound comes from `measure_rules` (src/moduleforge/drc/rules.py lines 475-478, 587:
  `min_signal_wire_length = sl_lo`, the reference's shortest signal wire). E008 uses it unmodified (`spec_of`, and the
  T0263 note §6).
- **Conclusion: O003 does not require the lower bound. It is a choice inherited by E008 through frozen measure_rules.**

**Mechanism of the 2R TwinError** (corrects T0263 §6, per T0313 finding 1):
- [F] The generator's gate wires run straight to the *nearest* landable point of their gate copper (derivative.py
  docstring lines 21-27; `_signal_wires`). So a twin gate wire is the shortest wire possible from its foot.
- [F] `checklist_facts.signal_wire_plan_excess_over_nearest_copper_mm`: 2R's reference wires land 1.13 to 1.91 mm
  (plan) beyond the nearest copper point. The twin's LS wires are 4.597 mm long against the reference's 5.34 and 5.41 mm.
- [F] The step-3 repair `_repair_signal` runs and fails. In a 0.5 mm gate pad, the foot margin is
  max(0.15, 0.15) + 0.05 = 0.2 mm, so `_foot_candidates` (twin.py lines 500-506) has a single position, (0, 0).
  Power-foot shifts do not lengthen a gate wire.

**T0263 point 0** (from T0313 finding 0, not re-fetched here): 2R's constraint.csv also sets voltage-dependent spacing
(≥ 3 mm at 5-10 kV, 5 mm at 15 kV). Neither the reconstruction (2.0 mm DC+/PHASE and PHASE/DC-) nor the measured rules
meet it.

## 2. Item 2: the DegradeError mechanism

**Case 4 at R0.**

Moves 1-3 ([F] `variants.R0.degrade`):
- Move 1 is applied but changes nothing: both landing bands are 5.0 mm, and the minimum is 5.0 mm.
- Move 2 changes nothing.
- All six spreads stop at their first step on `min_spacing`, between the slots and the GATE_HS / GATE_LS keep-outs
  (1.5 mm < 2.0 mm).

The walk ([F] `walk_terminal_blockers`) climbs from 0.996 to 1.232 in 75 steps. At the terminal state, 72 single-step
candidates exist:
- 36 are DRC-clean but do not raise L1.
- The other 36 are rejected by (41 rule hits; one candidate can hit two rules):
  - `min_trace_width` 10 (power width; 3 of them also `terminal_off_trace`);
  - `die_edge_margin` 8;
  - `min_spacing` 7 (DC+/DC- 5 mm; keep-out 2 mm);
  - `edge_margin` 5;
  - `wire_landing` 4;
  - `die_spacing` 2;
  - `wire_length` 2 (HS wires at the 18 mm cap).
- [I] Every power feature is at its rule minimum: columns and landing bands 5 mm wide, die slots exactly die + 2 × 2 mm,
  copper 5 mm from the edge.

Is each stopping rule required by O003 scope_in (objective.yaml lines 52-63)?
- **Required:** power-net width ≥ the reference's own minimum (line 58), per-pair and other-pair spacing (lines 55-58),
  die_spacing / die_edge_margin / edge_margin (lines 60-61).
- **Not in scope_in:**
  - `max_wire_length` 18 mm, an E008 dev override (E008.yaml line 323).
  - `wire_landing` (DRC default landing margin 0.3 mm) and `terminal_off_trace`. [I] These are structural, not
    strictness rules.
- R3 shows the target is reached only by relaxing the required power width. Lifting the non-required wire cap gives 1.243.

**Prototypes** (changes to the degradation rule only; D checked DRC-clean under R0, [F] `prototypes`):
- **P1:** continue from the frozen terminal state with single-parameter jumps of ±0.5 to ±5 mm plus rigid single-slot
  moves. Result: 1.260 after 25 steps, local maximum, DRC-clean.
- **P2:** the same candidate set from the walk's start. Result: 1.240 after 35 steps, local maximum.
- **Neither reaches 1.388. I found no degradation-rule change that does.** [I] Under the required 5 mm width the twin's
  bands cannot be narrowed. The keep-out strips (Case 4 SIG_* copper) block moving rows apart, so the remaining levers
  give about 26 %, against the 38.8 % L1 target. A hill-climb is not a proof that no D exists.

Caveats:
- The walk and the prototypes climb on L1, the same screen that decides when to stop.
- The 0.11 margin was derived on generator layouts. Case 4's twin L1 bias was 15.3 %, outside the 5-14 % band
  (twin.py lines 105-112).
- **Criteria change, flagged and not proposed:** accepting a planted headroom below F1(b)'s L_sub(D) ≥ 1.25 L_sub(twin),
  or a margin below 0.11.

**2R at R1:** D reaches 1.395 (above). Moves 1-2 are skipped on `min_trace_width` / `min_spacing`. The spreads stop on
`min_trace_width` / `edge_margin`. The walk finishes the job in 16 steps. [I] 2R ends 0.007 above the target, like the
stress set's median of 1.394 (twin.py line 93), so its L2 ratio decides F1(b), not L1.

## 3. Item 3: 2D_Case_6 against twin.py's candidate filter

[F] `layouts.2D_Case_6.candidate_filter_trace`; twin.py lines 584-603.

**Orientation 1.** `_rows_of` returns None (lines 208-210): in the local frame v = x, the die centres of each switch
differ by 6 mm (HS 14/20, LS 41/47), which exceeds 0.3 mm.

**Orientation 0.** Rows HS (12, 19, gap 2) and LS (39, 15, gap 2). Landing lines HS 15.5, LS 24.5. Anchor v in mm:
- HS die row centre 22.0;
- HS landing line 15.5 (the HS wires run down);
- LS die row centre 18.0;
- LS landing line 24.5 (the LS wires run up).

Lines 412-414 reject all 8 sequences:

| hs_first, hs_die_first, ls_die_first | anchors in slot order | first violation |
|---|---|---|
| 0,0,0 | 24.5, 18.0, 15.5, 22.0 | slots 0-1 |
| 0,0,1 | 18.0, 24.5, 15.5, 22.0 | slots 1-2 |
| 0,1,0 | 24.5, 18.0, 22.0, 15.5 | slots 0-1 |
| 0,1,1 | 18.0, 24.5, 22.0, 15.5 | slots 1-2 |
| 1,0,0 | 15.5, 22.0, 24.5, 18.0 | slots 2-3 |
| 1,0,1 | 15.5, 22.0, 18.0, 24.5 | slots 1-2 |
| 1,1,0 | 22.0, 15.5, 24.5, 18.0 | slots 0-1 |
| 1,1,1 | 22.0, 15.5, 18.0, 24.5 | slots 0-1 |

[I] The HS pair spans v 15.5-22.0 and the LS pair spans 18.0-24.5. The intervals overlap, so no total v-order of the
four slots exists. The cause is the side-by-side arrangement (HS block at x 12-22, LS block at x 39-49) with wires in
opposite directions. No rule is involved.

**Smallest extension** ([I], not implemented): a side-by-side topology.
- The two (die band, landing band) pairs each occupy their own u-range. Each pair is v-ordered internally and in either
  direction, and the pairs may overlap in v.
- Touched:
  - derivative.py: `Params` (one new int flag; `NAMES` and the vector length change), `_sequence`/`sequence`,
    `topology`, `_encode`/`params_of`, `_Ctx` and `_sample` (new branch), and possibly `build`'s column logic.
  - twin.py: `_fit` (per-pair order plus a u-disjointness test), `_best_split`/`_band_copper` (the PHASE band joining
    the HS landing slot to the LS die slot is u-adjacent, not v-adjacent), and `_shifted`/`SPREAD_ORDER` (spreads
    assume one v-order).
- Size: 2 source files (derivative.py 890 lines, twin.py 872 lines), about 9-11 functions, about 200-350 changed lines,
  and about 10-15 new tests in test_derivative.py / test_twin.py (33 and 39 tests today) plus a stress-test case.

**Freeze hashes it changes** ([F] E008.yaml lines 56-62):
- `derivative.py` a93effe5… and `twin.py` fd4ad327….
- `optimize/search.py` 55bbe01d… only if it is touched. It imports derivative ([F] grep).
- `rules.py`, `snap.py` and `stack.py` are unchanged.

**Search space:**
- [I] A new flag changes the Params vector and the sampler's draw sequence. So E008's sealed 20,000-candidate stream
  changes for every reference, and E008's dev rows (gen2_0, Case 4) must be re-run.
- [F] No registered spec depends on derivative/twin. `grep` finds only experiments/runners/e008_run.py,
  optimize/search.py and the generate tests. experiments/specs has E000-E003 (O000/O001), E006 (O006), E009 (O007)
  and E901 (the O901 canary), and no O005 spec. So no O001 or O005 evidence rests on this search space.

## 4. Item 4: screening checklist

Each question is answerable from a datasheet or a verbal description. The answer that excludes a layout from the twin
space is shown with each question, followed by 2R / Case 6 / Case 4.

| # | question | excluding answer | raise site | 2R | Case 6 | Case 4 |
|---|---|---|---|---|---|---|
| 1 | Are there exactly three power terminals (DC+, DC-, phase)? | no | derivative.py line 199 | yes [F] | yes [F] | yes [F] |
| 2 | Are all switch dies the same part, with the same orientation (gate pad on the same edge)? | no | derivative.py line 246; docstring "die rotation" | source: HS turned 180° [F T0263 §2]; uniform after M1 | source: LS turned 180°; uniform after M1 | yes (pads assumed) |
| 3 | Is the die outline a multiple of 0.5 mm? | no | derivative.py line 201 | yes 4×6 | yes | yes |
| 4 | Does every die carry the same number of power wires, all bonded on its source pad? | no | derivative.py line 249; twin.py line 242 | yes, 1 [F] | yes, 2 | yes, 1 |
| 5 | Are each switch's dies in a single straight row? | no | twin.py lines 208-210; docstring "more than one row" | yes | yes | yes |
| 6 | Do the two switches' die-plus-landing blocks sit side by side, with wires in opposite directions? | yes | twin.py lines 412-414 | no | **yes** | no |
| 7 | Do each switch's power wires all land on one strip of the other net, along one line? | no | `_feet_of` (mean landing line) | yes | yes [I] | yes |
| 8 | Is each power net one connected piece of copper? | no | derivative.py line 422; DRC net_split | yes [F islands = 1] | yes | yes |
| 9 | Does any power net form a closed ring (copper with a hole)? | yes | derivative.py docstring "PHASE ring" | no [F holes = 0]; open C-shape, represented exactly | no | no |
| 10 | Does any power net need more than one feed column, or more than two strips? | yes | build / `_fit` column test (twin.py lines 445-463) | no (symdiff 0) | unknown (fails earlier) | no (symdiff 0) |
| 11 | Does any gate (or Kelvin) wire land beyond the nearest edge of its gate copper (along the strip, or over the die)? | yes, under R0 | derivative `_signal_wires`; rules.py line 587 | **yes** (1.13-1.91 mm) | yes (0.76-0.78 mm) | none in source |
| 12 | Are there Kelvin-source wires? | supported, not excluding | spec / DRC bondability | no | no | yes (assumed pads) |
| 13 | Are there separate antiparallel diode dies? | yes | O003 out of scope | no | no | no |
| 14 | Does any power wire run die-to-die, or land on a die or terminal? | yes | DRC wire_net, wire_landing_keepout | no [I] | no [I] | no [I] |

[I] Questions 6 and 11 are the ones that decided these three layouts. Question 2 is hidden by M1 in the reconstructions.

## 5. Item 5: ranked changes

Coverage gain is weighed against cost.
1. **Drop `min_signal_wire_length` from E008's per-reference rules** (R1: `dataclasses.replace(rules,
   min_signal_wire_length=None)` in the reference loader).
   - Gain: 2R becomes representable, and its D reaches 1.395.
   - Cost: a few lines in the runner and spec. Candidates also lose the lower bound, which O003 never set.
   - **(i)** under a new freeze. If done inside measure_rules instead, rules.py's hash changes too.
2. **Case 4 DegradeError.** I found no degradation-rule change that reaches the target under the O003-required rules
   (P1 1.260, P2 1.240). The options are therefore decisions, not fixes:
   - (a) treat a DegradeError as exclusion of that reference rather than INVALID: **(iii)**. E008.yaml lines 381-382
     already list this as an open founder decision.
   - (b) a smaller planted headroom: **(ii)**, a criteria change, flagged and not proposed.
   - (c) [I] a D outside the twin's topology, e.g. another sequence. This is effectively a search, which F1(b)'s
     "degradation rule" does not describe: **(iii)**.
   - (d) lifting E008's 18 mm wire cap alone gives 1.243 and does not suffice.
3. **Generator side-by-side topology for Case 6** (section 3).
   - Gain: Case 6-type layouts; [I] the sensitivity to question 6 is likely common in PowerSynth layouts.
   - Cost: two frozen files, a changed search stream, and dev rows re-run.
   - **(i)**, a new freeze. Whether its D then reaches the target is unknown.
4. Leave Case 6 excluded under F1(a) as unrepresentable: **(iii)** (the reading in section 6).

**F3 status.** Every change above was found after 2R and Case 6 were seen. That is clean only if 2R, Case 6 and Case 4
become development layouts and the judged references stay unseen. Otherwise it is a declared deviation under F3. Per the
packet, I looked up no other module's geometry.

## 6. Item 6: what the specs say about a verdict on one counted reference

- [F] O003 decision_if_pass (objective.yaml line 34): "A PASS resting on a single counted reference goes to the founder
  review first, as INCONCLUSIVE does (D0017)". The A1 description (line 131) says the same.
- [F] K1 (line 134): "a kill resting on a single counted reference goes to the founder review like any kill
  (decision_if_fail)". The notes say the same (line 194, item 8).
- [F] F1 (line 139): a reference failing a twin gate "is excluded and reported, and E008 is INVALID only if no reference
  remains".
- [F] E008.yaml defines `n_counted_references` (line 831) and the `at_least_one_counted_reference` sanity check
  (line 855).
- [F] E008.yaml says a DegradeError means "implied: ... INVALID", with exclusion as an open founder decision (lines
  375-382).
- [F] Conflicting text on TwinError and DegradeError:
  - The sanity check `fail_fast_twin_and_D` (line 848) says "TwinError / DegradeError stop the run".
  - `prepare()` (e008_run.py line 620) says they "stop the reference".
- [I] So one counted reference can carry a verdict, but only through the founder review. Whether a TwinError or
  DegradeError on another reference stops the whole run or excludes that reference is ambiguous in E008 and must be
  decided before registration.

## Commands run (exit codes)
- `uv run python $TMPDIR/t0314/probe0.py {2D_Case_2R,2D_Case_6,case4}` → 0. Reproduced R0.
- `uv run python $TMPDIR/t0314/probe{1,2,3}.py` → 0. Scratch diagnostics; superseded by the script.
- `uv run ruff check research/scripts/o003_twin_coverage.py` → 0.
- `uv run python research/scripts/o003_twin_coverage.py --out research/o003/twin_coverage/results.json` → 0 (about 19 min).
- Second full run, `--out $TMPDIR/t0314/rerun.json` → 0. `cmp rerun.json results.json` → 0 (byte-identical).
- `uv run python experiments/runners/e008_run.py --verify-freeze` → 0.
- The thermal_fem.py sha256 prefix test (a216d5fe3209bcee) → 0.
- `uv run mfos gate --fast` → 0 ("all gates passed").
- `git status --short`: only the three new research/ paths. No src/, tests/, experiments/ or project/ file was changed.
  The definition of done's `git merge-base` command is blocked by the worktree guard hook, so I did not run it.
- Total compute: about 45 min. That is two full script runs of about 19 min each plus about 5 min of probes, above the
  packet's 30 min. The second run only checks determinism.
- WebSearch (heavy Al wire minimum length) → no value. WebFetch of the Tyndall PDF → HTTP 404.

## Errata (founder session, 2026-11-11, from review T0315)
Corrected in place after the merge, with no conclusion changed:
- R3 field counts (23 for 2R, 20 for Case 6; finding 1a).
- The Case 4 walk-terminal counts (72 candidates, 36 clean but not raising L1, 36 rejected; finding 0).
- The rules.py placeholder citation (finding 1b).
- E901 in the list of registered specs (finding 1c).

Open, for the founder (finding 2): whether O003 scope_in's opening clause, "design rules at least as strict as the
reference's own", makes the measured minimum gate-wire length a criterion. If it does, dropping it (section 5, change 1)
is a criteria change (ii), not (i).
