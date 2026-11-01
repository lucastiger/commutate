# Thesis review — 2026-10-31 (day 33)

Day count from the bootstrap commit `67f8b68` (2026-09-28). Kill dates: day 45 = 2026-11-12, day 60 = 2026-11-27,
day 90 = 2026-12-27. Sources read: `project/charter.md`, `project/claims/C001–C003.yaml`,
`project/objectives/*/evaluations/*.json` (no objective has an `EVIDENCE.md`; the evaluation JSONs and claim files
are the evidence of record), `project/customers/` (README only), `project/memory/literature/INDEX.md` (empty),
`research/notes/`. All recommendations below are proposals; the founder decides. The charter is a protected path and
was not edited.

## 1. Assumptions

| id | assumption | proposed status | evidence |
|---|---|---|---|
| A-T1 | A fast L1 EM model ranks layouts faithfully enough to drive search | **supported, narrowly** | `project/claims/C002.yaml` (supported, EV-O001-01); `project/objectives/O001/evaluations/EV-O001-01.json` (A1–A6 satisfied: Spearman 0.996, lower bound 0.990; MAPE 9.7 %; top-decile recall 1.0; median 22 ms/eval); `research/notes/o001-e002-within-stratum-exploratory.md` (post hoc, not confirmatory) |
| A-T2 | A fast L1 thermal model is faithful enough for Tj max and spread | untested | none. No thermal code exists (`src/moduleforge/` has no `thermal`), and the L2 thermal reference is still unchosen (CLAUDE.md glossary) |
| A-T3 | Real derivative problems have ≥ 20 % L or ≥ 50 % current-mismatch headroom at ≤ +2 K Tj | untested | none |
| A-T4 | Customers accept software layouts verified in their own Q3D/Icepak flow | untested | none: `project/customers/` holds only `README.md`; no interview note has ever been committed (`git log -- project/customers` shows only the bootstrap) |
| A-T5 | Paid derivative-layout sprints can start within 90 days | untested | none (same as A-T4) |
| A-T6 | No incumbent or academic tool already delivers this commercially | **untested in the repository** (charter says "partially tested") | none: `project/memory/literature/INDEX.md` is empty and no scout note exists. If the "partially" rests on work outside the repository, it should be written down as a scout note |

Why A-T1 is "narrowly" supported (all from the caveats in `project/claims/C002.yaml`):
- The pooled ranking metrics are dominated by family and die-count strata: a stratum-mean-only predictor reaches
  Spearman 0.972 (`research/notes/o001-e002-within-stratum-exploratory.md`). Derivative re-layout ranks layouts
  *within* a family and die count. The within-stratum Spearman 0.977 [0.940, 0.983] is post hoc on already-seen
  sealed data and is hypothesis-generating only.
- Below about 5 % inductance difference L1 misorders 23–38 % of pairs; below 2 % it is close to chance. Derivative
  layouts that differ only slightly are exactly that regime.
- One DBC stack (Al2O3 0.38 mm, Cu 0.3 mm), one 70 × 40 mm housing, 20 MHz only, the generator's three families.
  AMB untested. L1 is 5–14 % low with die-count-dependent bias, overstating the benefit of adding dies by about
  2–3.5 points, and it does not converge on mesh refinement.

C001 (O000) and C003 (O901) are infrastructure canaries. They show the evidence pipeline works end to end (sealed
seeds, recomputation, null check, provenance audit, critics); they bear on no thesis assumption.

## 2. The strongest case against continuing (a skeptical investor)

"Thirty-three days in, you have spent about $300 of model usage and $80–100 of cloud compute, and produced one
narrow technical result plus two self-tests of your own process. The result shows a fast inductance model agrees
with your own in-house reference on synthetic layouts from your own generator, on one stack, in one housing — and its
strongest metric is matched almost exactly by a predictor that only knows the family and die count. The regime that
matters for derivatives, small differences between near-equivalent layouts, is where it is weakest. Thermal, which
your value proposition promises to bound, does not exist yet and has no reference solver. Most importantly, there is
no recorded customer conversation. Your own kill criterion requires a customer willing to share a reference layout
under NDA by November 12, twelve days from now, and nothing in the repository says you have spoken to anyone. The
competitive assumption has no written evidence either: Ansys, Siemens and Cadence ship parasitic extraction and
thermal tools, module makers have in-house scripts, and academic layout-synthesis work for power modules exists. You
have been building the engine and the operating system around it while the two assumptions that decide whether
there is a business (A-T4, A-T5) remain untouched. Infrastructure work also cost real time: the canary had to be
re-run, and a laptop theft destroyed unpushed work. Why would the next 57 days look different?"

## 3. What changed since the last review

There is no earlier review in `docs/reports/`; this is the first. Since the charter was written:
- **O001 passed** (EV-O001-01, 2026-10-16) → C002 supported with substantial caveats. L2 became an in-house
  exact-kernel PEEC with FastHenry optional (D0003, D0004); compute budget raised to 400 CPU-h (D0005).
- **O000 and O901 passed** (C001, C003): the evidence pipeline v2 (provenance, recomputation, null discrimination,
  sandboxed agents) works end to end.
- **Environment recovered** onto a new laptop after a theft (2026-10-31). T0116's first attempt and the local run
  records were lost and rebuilt; nothing in the evidence of record was affected.
- Nothing changed for A-T2 to A-T6.

## 4. Recommended changes (proposals)

1. **Re-prioritize toward the day-45 gate now.** Before any new compute objective, hold customer conversations and
   record them in `project/customers/` with `[A-T4]`/`[A-T5]` tags. If interviews already happened and their notes
   lived only on the stolen laptop, reconstruct them from memory now and mark them as reconstructed.
2. **Commission the A-T6 scout research** (a `research` task for the scout: commercial tools, in-house practice,
   academic power-module layout synthesis, with citations). Change the charter status from "partially tested" to
   "untested" until a note exists.
3. **Next technical objective: a within-stratum ranking test, before or alongside O002.** Pre-register a
   within-(family, dies) ranking criterion on fresh sealed seeds, including near-equivalent pairs (< 5 % ΔL), as
   `research/notes/o001-e002-within-stratum-exploratory.md` proposes. This is the regime derivative re-layout needs,
   and it is cheap relative to thermal.
4. **O002 (thermal L1): first choose the thermal L2 reference** (a permissively licensed solver, recorded as a
   decision) before drafting the objective. Without it O002 cannot be pre-registered.
5. **O003 (headroom): prepare a public benchmark set now.** The day-60 kill criterion is defined "on public
   benchmarks", and no such set is identified anywhere in the repository.
6. **Charter wording:** (a) narrow A-T1 to its supported scope ("…on the default DBC stack, for layouts whose loop
   inductance differs by ≥ 5 %"), with the within-stratum question as a new assumption or folded into O003;
   (b) set A-T1 to "supported (narrow, C002)", A-T6 to "untested"; (c) state where customer evidence must live for
   the day-45 and day-90 criteria to be judged.
7. **Infrastructure canaries are complete.** Propose no further canary objectives unless the pipeline changes.

## 5. Addendum (same day): research commissioned by this review

Three research notes were written on 2026-10-31 by general-purpose research agents from the founder session (scout
subagents could not run there), each spot-checked on its decisive sources:
- **A-T6** — `research/notes/a-t6-competitive-landscape.md`: no commercial product or service re-synthesizes
  power-module layouts; vendors sell analysis plus parametric optimizers, and Siemens markets a power-module
  optimization solution ("months to just a few weeks") whose method is unpublished. The academic PowerSynth 2
  (GPL-3.0, v2.2 June 2025) already optimizes wire-bonded layouts for loop inductance and Tj max from a hand-written
  initial layout, with Q3D export. Proposed status: supported as stated, capability not unique. The moat must be
  the derivative workflow (reference import, fixed housing, die swaps, current sharing and gate-loop objectives,
  customer-runnable decks), not "nobody optimizes layouts".
- **A-T3 / day-60 gate** — `research/notes/o003-public-benchmarks.md`: no public re-layout benchmark exists; the
  best reconstructable references are the PowerSynth sample designs (GPL-3.0), the UTK P/N-cell pair, the CPES SiC
  phase legs against a commercial module, and the Aalborg/Danfoss 4-die module. **The only public comparison with a
  commercial module implies about 18 % module-internal loop-inductance headroom from substrate re-layout with the
  terminals fixed (an inference from the CPES Q3D numbers), just below A-T3's 20 %.** Headroom depends strongly on
  the loop definition and on DC versus AC extraction, so the day-60 criterion needs a pre-registered definition.
  This weakens the loop-inductance branch of A-T3 and leaves the current-mismatch branch plausible but unmeasured.
- **A-T2 blocker** — `project/memory/literature/thermal-l2-reference.md`: a permissive, verifiable thermal L2 is
  feasible: an in-house finite-volume solver on a layer- and edge-conforming rectilinear grid (scipy, pyamg), with
  scikit-fem (BSD-3) as cross-check; FEniCSx is LGPL with ParMETIS and GPL transitive dependencies. Draft decision:
  `docs/reports/D0006-draft-thermal-l2-reference.md`.

Founder decisions these raise: whether GPL-3.0 PowerSynth sample designs may be used as external benchmark inputs
(and PowerSynth itself as an unmodified external comparison tool); the O003 loop definition and extraction frequency;
and the charter wording in `docs/reports/charter-2026-10-31.patch`.
