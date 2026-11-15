# D0023 — E010 is void: the frozen D0008 search does not reach the 2D_Case_2R designer's level; O003 has no verdict and is paused; planted-headroom controls are rehearsed on a development reference whose twin the sampler cannot draw
Date: 2026-11-15 · Status: accepted · Decider: founder (founder session, 2026-11-15; accepted as drafted) · Relates to: D0008, D0010, D0011, D0019, D0020, D0021, D0022; E010, T0347, T0349, T0350, I0203; run E010-20261114T202413-80c1, EV-O003-01

## Context
- Run E010-20261114T202413-80c1 (founder's VM, 6.2 VM-h) finished with status complete. 2D_Case_6 was excluded at
  prepare by TwinError, as the spec expected; 2D_Case_2R was the only counted reference. The main search on 2R
  returned h_lo = h_hi = 0 and had levelled off, so K1 would have fired had the run been admissible.
- EV-O003-01 is INVALID for two independent reasons (`project/objectives/O003/evaluations/EV-O003-01-invalid.json`):
  1. The planted-headroom control F1(b) failed on 2R: h_ctrl 0.161 against h_plant 0.220 minus w_ctrl 0.013
     (required 0.207). The control's best candidate is 1.0755 L_sub(W); a pass needed 1.0172 L_sub(W) or less.
  2. `evaluation_report.json` was written under `<run>/work/` but registered as a bare name, and the artifact-store
     copy stayed on the VM, so the evaluator could not resolve it.

  INVALID evaluations are not counted: O003's single evaluation is unused (`evaluations: []`).
- Diagnosis T0349 (failure class experimental, confidence 0.85; review T0350 accept_with_caveats; merged 99330585
  under I0203 with no replan):
  - The driver and the check are computed correctly (recomputed to 1e-12 from the raw checkpoints). Not a solver
    artefact in W, not L1 misranking as the main cause, not the phase A/B split.
  - The frozen sampler builds every slot from its column's inner edge and caps the PHASE column's outer edge at
    45.5 mm, so the twin W lies outside its support: W is outside the drawn range on 11 of 36 coordinates of the
    40,000 run candidates (T0350's count; T0349 quoted 13 from a 200-draw sample), and the nearest candidate is
    83 mm away (Manhattan).
  - The best L1 draws sit 3.05 % (main) and 6.2 % (control) above W. Per T0350, the demonstrated cause is the thin
    lower tail of the random prior under the fixed 20,000-draw budget; the support restriction narrows the margin
    but is not shown to be sufficient on its own.
  - Why the design missed it: the only full F1(b) rehearsal was on gen2_0, whose twin lies inside the sampler's
    support by construction (T0349 §2.3).
- O003's frozen text covers this case. F1 detection: "If the reference is near-optimal, (b) may fail and E008 is
  INVALID; a kill is possible only where the D0008 search matches the reference designer." F1 response:
  "experimental failure (INVALID) when (b) ... fails ...: fix the generator or the search under a new experiment id;
  at day 60 D0011 applies (no verdict counts as INCONCLUSIVE)."
- O003 has used 3 of 3 replans and $258.22 of its $264.99 cap. Any change that lets F1(b) pass on 2R touches frozen
  F3 elements (generator code hash, the D0008 budget or the search procedure), now after 2R's E010 results were read.

## Decision
1. **E010 is void for O003's question, and O003 has no verdict.** The run stays on record and EV-O003-01 stays
   INVALID and uncounted. E010's h = 0 on 2D_Case_2R reads "not found by the frozen D0008 search", never as evidence
   that 2R has no headroom. No claim is proposed from E010, for or against A-T3. E010's spec, runner and results are
   not changed.
2. **No successor experiment under O003** (T0349 §5, option (a)). Reaching the reference designer's level (a
   parameterisation that contains the twin, a search seeded at it) is new work under a new objective, not a rerun of
   O003.
3. **O003 is paused** (`uv run mfos objective pause O003`, which sets its status to needs_founder) so the loop
   dispatches no further O003 work; its remaining $6.77 is not spent. Under D0011, no verdict by 2026-11-27 counts as
   INCONCLUSIVE, and the founder's thesis review on 2026-11-27 (D0010) takes it up. O003's decision_if_inconclusive
   ("test the current-mismatch branch of A-T3 before any further loop-inductance work") stands unless that review
   amends it with a recorded reason; this record does not amend it.
4. **Design rule for every planted-headroom (F1(b)-type) control.** Before registration, the control is rehearsed on
   at least one development reference whose twin the sampler cannot draw. The registration package reports, per
   reference: whether the twin lies inside the sampler's support (the coordinate-range test against the drawn pool
   and the attached-form test of T0349 §2.2), and the L1 lower tail of the candidate pool relative to the twin
   (minimum excess, and counts within 2, 3, 5, 7, 10 and 15 %). The rule goes into `project/memory/lessons.md`.
5. **The artifact defect is fixed in tooling, not in E010.** Runners register run-directory paths and the burst
   launcher fetches the artifact store, each with a test (plan section 11, fix 1). E008's runner has the same
   pattern; neither registered runner is edited.

## Consequences
- The day-60 kill does not fire: an instrument that cannot reach the reference designer is not a negative result
  (D0011 rejected "no verdict counts as a kill" for the same reason). A-T3 stays untested; the thesis review is asked
  to record it as "untested, instrument insufficient".
- 2D_Case_2R's E010 values (L_sub, Tj, the candidate pools) have been read, so 2R cannot serve as a judged reference
  for a generator or search developed after them. 2D_Case_6's twin failed at prepare; both are available as
  development geometry.
- No further O003 spend. The work the finding calls for is in the plan's section 3 (working id O008), drafted
  separately for founder approval.

## Alternatives considered
- (b) A successor experiment under O003 with a new id, a sampler whose support contains the twin and/or a search
  seeded at W, declared as an F3 deviation: not chosen. Unlike D0021's deviation, it would come after 2R's results
  were read; replans are exhausted and $6.77 is left.
- (c) Judge O003 on a reference set loaded only after a generator freeze: that is the plan's route (sections 3, 6
  and 7) under new objectives, not under O003.
- Read E010 as a kill because K1 is satisfied: rejected. F1(b) is a gated sanity check and failed, and O003's own
  text allows a kill only where the D0008 search matches the reference designer.
