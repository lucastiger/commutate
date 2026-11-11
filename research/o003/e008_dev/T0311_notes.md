# T0311 — E008 runner: stack-type rounding, selftest gaps, F6(e) reading (review T0310)

Scope: development path only (generator layouts, 2D_Case_4, fake-solver selftest). No judged reference, customer data,
2D_Case_2R or 2D_Case_6 was loaded. `src/moduleforge/solvers/thermal_fem.py` unchanged (sha256 a216d5fe3209bcee...).
No tolerance, gate, frozen value or cost model changed. Runner after this task: sha256 6d01aa5c0434...8342.

## Changes (facts)

1. **Stack-type signature rounding (T0310 finding 3).** `_stack_signature` now writes every thickness (substrate,
   die-attach and die layers, and every per-die thickness and attach thickness) as integer nanometres
   (`_sig_nm`: `int(round(t / 1e-9))`, Python round-half-even) and every conductivity to 9 significant digits
   (`_sig_k`: `format(k, ".8e")`). Constants `SIG_THICKNESS_QUANTUM_M = 1e-9`, `SIG_K_SIGNIFICANT_DIGITS = 9`.
   A NaN/inf thickness raises (no type; the reference stops). The rule is in the spec (F6e_stack_type_spot_check
   description and a founder_decisions_before_registration entry).
   - Selftest `stack_rounding_failures`: the default stack with every layer thickness and k and the die/attach thickness
     x (1 + 1e-15), 2D_Case_4's stored die thickness 0.00017999999999999998 m, and a single die x (1 + 1e-15) (the
     reviewer's probe, which gave `other:408ebae3a1b4` before) are all `Al2O3_default_dbc`; +1 um on each of the
     substrate/attach/die layers in turn, k x (1 + 1e-6) on each layer, die +1 um, attach +1 um, and one of four dies
     +1 um are all non-default.
   - Real dev references (L0 only, peak RSS 106 MB): gen2_0 is `Al2O3_default_dbc` with dies [[180000, 50000]] nm;
     2D_Case_4 stays non-default (die attach 0 nm, PowerSynth stack) as `other:a9ad6bbb1af1` (was `other:61c8dd23d7d1`;
     the hash changes because the signature's encoding changed, not the classification).
2. **Selftest gaps (T0310 findings 0-2).**
   - f0: `ST_REFS` gains fake6, a second admissible AMB reference after fake2. The expected spot reference stays fake2,
     and fake6 must have no finite-volume (FV) solves and 0 FV solves in its F6(c) details.
   - f1: fake2's level-1 FV record is written without `picard_dT_K` (`fv_pc_missing`). `F6c_picard:fake2` must fail with
     value NaN. fake2's other Picard values are <= 5e-5 K, so only the missing key can cause the failure.
   - f2: `fv_tj_nan` puts a NaN Tj on die 1 of a spot reference's FV level-2 solve. That is not the first die, and the
     plant is on the last checked type in sorted order, so a plain `max()` drops it. The per-type check must fail with
     value NaN, the aggregate must fail with value NaN, and `stack_type_a3` must be NaN. The plant runs in two scenarios:
     `stack_types`, which keeps all the other plants, and a new `stack_types_nan`, where the NaN is the only fault. In
     `stack_types_nan` nothing else can fail the aggregate.
   - **Defect found while planting f2 (fact):** before this change a NaN Tj did not fail F6(e) cleanly.
     `mfos.metrics.max_gci_consistency` raises `ValueError("non-finite value in a metric column")` (`_finite_rows`), so
     `evaluate` stopped and wrote no F6(e) check. This failed closed (a crash, so no verdict), but it did not match the
     spec's "a NaN or infinite A3 fails". New helper `_a3_die` returns NaN for a die with any non-finite Tj and otherwise
     calls the unchanged metric. Mutant N6 removes the guard; the selftest then raises the same ValueError.
3. **Spec (T0310 finding 4).** founder_decisions_before_registration now lists the F6(e) reading: a non-default type
   whose references are all inadmissible is reported, not gated. It also lists the alternative (fail F6e) and says the
   runner implements the first. A second entry states the rounding rule as decided here, which the founder may change.

## Evidence that the new checks bite (facts)

`uv run python research/o003/e008_dev/t0311_mutations.py --out research/o003/e008_dev/t0311_mutations.json`:
the unmutated runner passes (rc 0), and all 18 mutants are caught (rc 1). N1-N10 are new: last admissible reference;
missing Picard counted as 0; plain max over dies; plain max for the aggregate value; NaN-unsafe aggregate pass
(caught only by `stack_types_nan`); no non-finite guard; exact-float thickness; exact-float k; 10 um quantum;
5-digit k. M1-M8 are T0309's mutants re-run on this runner; M2's pattern follows the renamed key `die_thickness_attach_nm`.

## Inferences and caveats

- Rounding cannot merge two thicknesses more than 1 nm apart, or two k values more than 1e-8 apart in relative terms.
  Two values within float noise of a half-nm boundary could still round apart (inference: physical layer
  thicknesses are not specified to 0.5 nm, so this is not expected).
- `E008.dev_rows.json` carries runner stamp ae96dda0 (the T0309 runner). This task changes no row-producing code
  (assemble_rows, the row fields), only the signature, the F6(e) evaluation and the selftest. The dev rows remain what
  that runner produced, and the stamp no longer equals the current runner hash.
- T0310 finding 2 also named the per-row `energy_balance_max` field. The packet's item 2 did not ask for a plant
  there, so none was added; that field still uses `_worst` (unchanged).
- The registered path (`full()`, judged-reference loading) is untouched; it is added after T0263 and re-reviewed.
