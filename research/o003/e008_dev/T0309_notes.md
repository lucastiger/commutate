# T0309: E008 runner follow-up to reviews T0307 and T0308

Scope: experiments/runners/e008_run.py, experiments/drafts/E008.yaml (sanity-check text only),
experiments/drafts/E008.dev_rows.json (provenance stamp only), research/o003/e008_dev/. No frozen value, tolerance, gate,
cost model or founder decision changed. thermal_fem.py was not touched (sha256 a216d5fe3209bcee...). Dev geometry only
(generator layouts, 2D_Case_4). The registered path (full()) is unchanged and still out of scope.

## Changes (facts)
1. Spot-check reference: `Run.drive` takes the first *admissible* reference of each non-default stack type. A type with
   no admissible reference goes into `Run.spot_none`. It gets no spot check and no per-type check. `evaluate` reports it
   under `rep["F6e"][type]` with `reference: None` and a status, and lists it in the aggregate check's detail
   (`no_admissible_reference`). It is not failed. The spec's F6e_stack_type_spot_check text says this.
2. Stack type: the signature now includes the sorted set of per-die (Die.thickness, Die.attach_thickness). It is built
   from the reference layout's dies and the derivative spec's DieSpec, which every twin and candidate is built with.
   Default = default_dbc_stack() with dies of the geometry defaults.
3. F6(c): `child_fv` records `picard_dT_K` from `r["result"].meta["picard_dT"]`. evaluate folds it into F6c_picard. A
   record without it counts as NaN. The energy-balance, Picard and A3 maxima use `_worst` (NaN if any value is NaN), and
   every check uses `_within` (finite and <= tol). So a NaN or infinite value fails.
4. Selftest: a literal hand case for `thermal_report_from_rows` (TR_ROWS/TR_HAND; the derivation is in the comment above
   them). It covers the twin's per-die GCIs 0.15625/0.625 K, width 0.3125 K, a divergent die (+inf, n_gci_inf 1), node
   growth 9.5 (flagged) and a hot candidate with margin_vs_twin 10.3125 K and passes_vs_twin False. Two falsified report
   versions must fail this check inside the selftest. In offgrid_tj, every planted hot candidate must have passes_vs_twin
   False and margin > 2 K, and the twin's width must equal the hand value 0.125 K. The stack_types scenario now has six
   references with types from the real `_stack_type` and real `Die` objects (ST_REFS):
   - the first AMB reference is inadmissible, so the spot check falls on the second;
   - an AMB reference that differs only in die thickness gets its own spot check;
   - the default stack with only thicker per-die attach is a non-default type;
   - a type with only an inadmissible reference gets no check and is not failed.
   It also plants FV energy balance 1e-3, a NaN energy balance at level 2 (not first, so a plain max() drops it) and an
   FV Picard residual of 5e-4 K at level 3.
5. The rule_strictness guard skips `die_spacing` (NOT_NET_SPACING). The refresh script re-stamped runner_sha256 to
   ae96dda0... after the last runner edit. It keeps the T0306 stamp under `previous` and records `report_unchanged: true`
   for both dev references.

## Evidence
- `research/o003/e008_dev/t0309_mutations.json`: the unmutated runner's selftest returns 0. Each of eight mutants
  returns 1:
  - M1: spot reference ignores admissibility
  - M2: per-die thickness dropped from the signature
  - M3: plain max drops NaN
  - M4: FV Picard not folded
  - M5: `_within` lets NaN pass
  - M6: report marks every layout attainable
  - M7: T0308's falsified report
  - M8: guard matches die_spacing again
- Real dev layouts (L0 only): gen2_0 is `Al2O3_default_dbc` with dies [[0.00018, 5e-05]]. 2D_Case_4 is `other:61c8dd23d7d1`
  with dies [[0.00017999999999999998, 0.0]].

## Open points (inference / for the founder or a later task)
- Exact float equality. 2D_Case_4's die thickness is stored as 0.00017999999999999998 m, not 0.00018 m. A reference on
  the default DBC stack whose thicknesses differ from the defaults only by rounding would therefore be a non-default
  type and need an FV spot check. This errs toward more checks, never fewer. At Case 4 size, though, one spot check is the
  ~416 GB phase-B job. Quantising thicknesses (e.g. to 1 nm) in the signature would be a design change for a new
  draft. It was not made here.
- 2D_Case_4's dies have attach_thickness 0 (the PowerSynth stack carries the solder as a substrate layer). That is a fact
  about the reconstruction, not a runner issue.
- The spot-check reference is the first admissible reference. It may still be excluded later by the twin gates F1(a),
  which are known only after evaluate. Its spot check then still runs and is gated. That is conservative, but it costs
  the FV solves.
- Run.drive still builds drivers (and searches) for inadmissible references if the loader passes them. The full() loader
  (after T0263) should pass only admissible references, or drive should skip them. Neither was changed here.
