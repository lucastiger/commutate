# E004 design, part 1: registration stage (T0388)

RESEARCH NOTE, NOT EVIDENCE. Development work only: 2D_Case_4, development seeds, L1 only (O004 F2). No draw, no
`long_sides` and no L1 or l2_layout solve was run on 2D_Case_2R or 2D_Case_6. Their reconstructions were only rebuilt
by the frozen T0263 script, to check their fingerprints. Deliverables: `experiments/drafts/E004.yaml` and
`experiments/runners/e004_run.py`. Simulation output: `research/o004_e004/span_sim_case4.json`.

## 1. What the registration stage does (facts: the code)
The order is fixed in `e004_run.stage_registration`:
1. **Seed provenance.** Registered mode uses only `MFOS_SEED`. Smoke and development modes use `DEV_SEED = 20261117`
   and never read the sealed seed.
2. **Freeze (F2).** The reconstruction script's sha256 is checked first; nothing is imported from it before that. Then
   every file hash in `config.freeze.files`, `perturb.rules_sha256()`, `rules_supplement_sha256()`,
   `l2_layout.source_sha256()`, the numpy and shapely versions, the pinned commit (it must be an ancestor of HEAD), and
   `config.span` against O004's own text.
3. **References.** Both judged reconstructions are rebuilt by `snapped()` and their fingerprints checked. No tracked file
   may carry one of the script's `FORBIDDEN_NAMES` (D0007, F5).
4. **Before any draw.** Every reference coordinate that perturb rounds must be whole mm: trace vertices, die bounds and
   terminal boxes (T0416 item 3). Each reference must also be on the 1.0, 0.5 and 0.25 mm lattices.
5. **Draws.** `perturb.draw` runs per reference slot k with `SeedSequence(s, spawn_key=(k,))`. If a draw raises, the
   stage refuses and names the net (T0387).
6. **F4 checks**, on L0 geometry and L1:
   - at least 2 references;
   - at least 6 pairs per reference;
   - each single move type on each reference (compounds not counted, I0217);
   - every layout on the three lattices;
   - every re-layout DRC-clean and distinct, re-checked apart from the draw;
   - the pooled L1 span at both frequencies;
   - the proxy pair built.
   The coverage rule (|1 - r_L1| >= 6 % at both frequencies) is reported per move type, not checked.

In registered mode the first failed check raises `RegistrationRefused` before any solve. In smoke mode every check is
recorded and the run exits 0. The solve stage is a stub (T0389). In smoke mode its five declared checks are reported as
not run (`passed: false`), so the run is not marked invalid for missing checks.

**The span's lower end has one source.** `objective_span()` parses O004 scope_in's sentence "must span at least [0.75,
0.98] with at least 3 below 0.90" into `SPAN`, and `SPAN_LOWER_END` is defined from it. The spec's `config.span` repeats
the value so that registration freezes it. The runner refuses if the spec and the objective differ, so an amendment
cannot change the design silently. The lower end stays 0.75 in the code.

**Allocation (pre-registered before the simulation was run).** One pair of each of the four single types and two
compounds per reference. Rationale: I0217 says single moves keep per-type coverage and compounds are allowed toward the
span.

## 2. Checks that the checks can fail (facts, run 2026-11-16)
- **Smoke** (`--smoke --stage registration`, 1.8 s, exit 0). 2D_Case_4 stands in for both slots.
  - Pass: freeze, fingerprints, no GPL files, whole mm, draws, the F4 counts, lattices, DRC/distinct.
  - Fail: `l1_span` (pooled min 0.9454; 0 pairs below 0.90) and `proxy_pair_built` (pending).
  - The five solve checks are not run.
- **gen2_0** (development). `whole_mm_failures` flags all three nets' traces and dies 0, 2 and 3, and `on_lattice` at
  1 mm is False. `draw_pairs(gen2_0, {trace_width: 1})` refuses with "nets with a both-sided long side: DC+, PHASE",
  which matches T0387's finding.

## 3. Span simulation on 2D_Case_4 (founder request, T0387 report)
### Method (facts)
- **Command:** `uv run python experiments/runners/e004_run.py --dev-span-sim 200`, checkpointed, 1.3 s per seed.
- **Draws:** 2D_Case_4 with E008's development overrides, the frozen allocation, and seeds `DEV_SEED + 1000 + k` for
  k = 0..199 (never E004's sealed seed). Each seed draws both slots through the registration path
  (`reference_seed(seed, 0)` and `reference_seed(seed, 1)`).
- **Samples:** each slot's draw (6 pairs) is a single-reference sample, n = 400. The two slots pooled (12 pairs) stand in
  for O004's pooled check over two references, n = 200, without the proxy pair.
- **The check:** upper end 0.98, at least 3 pairs below 0.90, both frequencies.
- **Failures:** 0 of 400 draws failed.
- **Cost:** L1 only, peak memory well under 1 GB.

### Fraction of draws meeting the span check (Wilson 95 %)
| lower end | single reference (n = 400) | pooled two slots (n = 200) |
|---|---|---|
| 0.75 | 0 [0, 0.0095] | 0 [0, 0.019] |
| 0.78 | 0 [0, 0.0095] | 0 [0, 0.019] |
| 0.80 | 0 [0, 0.0095] | 0 [0, 0.019] |
| 0.85 | 0 [0, 0.0095] | 0.005 [0.0009, 0.028] |

### Which constraint binds (facts)
- **Upper end:** max >= 0.98 holds in every draw.
- **At least 3 below 0.90** is the main block. No single draw has it (counts per draw: 0: 315, 1: 78, 2: 7). Only 2 of
  200 pooled draws do.
- **Lower end:** min <= lo is met at 0.75 / 0.78 / 0.80 / 0.85 by 0 / 0 / 1 / 5 of 400 single draws.
- **Lowest L1 ratio per draw** (20 MHz, single reference): min 0.7987; quantiles 5 % 0.873, 25 % 0.903, 50 % 0.930,
  75 % 0.957, 95 % 0.986.
- **Per pair kind** (20 MHz):

  | kind | n | min | median | share r < 0.90 | share \|1 - r\| >= 6 % |
  |---|---|---|---|---|---|
  | compound | 800 | 0.799 | 0.986 | 0.06 | 0.30 |
  | die_row_shift | 400 | 0.873 | 0.962 | 0.11 | 0.35 |
  | trace_width | 400 | 0.915 | 0.996 | 0 | 0.08 |
  | wire_landing | 400 | 0.963 | 1.009 | 0 | 0.14 |
  | terminal_copper | 400 | 0.981 | 1.000 | 0 | 0.05 |

### Inferences (not results; they rest on Case 4 standing in for the judged references)
- **Why "3 below 0.90" almost never holds.** Under this allocation only 3 of the 6 pairs per reference can reach below
  0.90: the die-row shift and the two compounds. All three must do it, with chance about 0.11 x 0.06^2 ≈ 4e-4. Pooled
  over two references, 3 of 6 candidates must do it.
- **Lowering the lower end does not rescue the check.** Even at 0.85 the pooled pass fraction is at most about 3 %, so
  a sealed registered draw would almost surely be refused by F4. A refused sealed run stays on the record.
- **The coverage rule will rarely cover most types.** With one single pair per type per reference (2 pooled), the chance
  that a type is covered is about:

  | type | chance covered |
  |---|---|
  | terminal_copper | 1 - 0.955^2 ≈ 9 % |
  | trace_width | ≈ 16 % |
  | wire_landing | ≈ 26 % |
  | die_row_shift | ≈ 57 % |

- **2D_Case_2R and 2D_Case_6 may differ from Case 4.** Their rules, gaps and wire lengths differ, so these fractions
  carry over only as an order of magnitude. Measuring them on 2R or Case 6 is forbidden by F2.
- **The decision is the founder's.** Changing the allocation, the span, or the draw (for example a pre-registered
  rejection on r_L1, which is not the tool under test) is a design change. None is made here. The three options:
  1. more compound slots, or a frozen rule that draws compounds conditioned on r_L1 < 0.90 within the sealed stream;
  2. the span checked per draw on its lower end and its n_below separately, with a narrower lower end;
  3. the n_below count lowered.
  Options 1 and 2 keep F2 intact, since L1 is not under test and the rule is frozen before the draw.

## 4. What is not done, and why (facts)
- **perturb.py fixes (T0416 items 1, 2 and 4, and T0387's `long_sides` fix).** These are `src/` and `tests/unit/`
  changes. T0388's write scope is research/, experiments/drafts/, experiments/runners/, tests/acceptance_drafts/ and
  project/memory/, so I made none of them. The stopgaps:
  - Item 1: `rules_supplement_sha256()` hashes NETS, SIGNAL_NET, SIGNAL_PADS and the sources of `Die.bounds`/`Die.box`,
    `BondWire.length` and `SignalWire.length`. It is frozen beside `rules_sha256()`.
  - Item 2: the frozen rule text in the spec states the representation dependence. The packet allows this instead of
    a code change.
  - Item 3: the runner asserts whole-mm coordinates and the lattices, and refuses rather than redrawing.
  - Item 4 (a vacuous test) and the T0387 fix (evaluating long sides only for the drawn net) need a builder task.
  - Each of these fixes changes `perturb.rules_sha256()` and perturb.py's file hash, so the spec's freeze block must be
    refrozen after they land.
- **Proxy pair.** `optimize.control.proxy_descent` exists (T0379), but it passes `step_mm=0.5` to `local.descend` and
  has no step parameter. I0207 asks for that parameter in O008's code. `proxy_pair_status()` reports pending with this
  reason, and registered mode refuses.

## 5. F7 (facts from research/notes/o004-f7-l2-pilot.md)
- F7(b) passed.
- F7(c): 0 of 2 complete pairs were excluded and 11 pairs are pending a VM run. The trigger has not fired and is
  undecided.
- F7(a), the FastHenry burst, has not been run.

None of this fires F7's response trigger, so E004's design was not blocked on it. Registration still waits on the
assembled F7 results.

## What would prove this wrong
- `uv run python experiments/runners/e004_run.py --smoke --stage registration` passing a check on a layout that
  violates it. The gen2_0 run above is the counter-test for the whole-mm, lattice and draw-refusal checks.
- A judged-reference draw that differs from a replay with the same seed: `perturb.draw` is deterministic given the seed
  and the frozen sources.

## 6. Attempt 2 (2026-11-17): review findings T0440 / T0441 and D0024
Sections 1-5 describe attempt 1. Where they disagree with this section, this section holds.

### Why attempt 2 (facts)
- Attempt 1's DoD commands exited 0. The orchestrator's full gate (`uv run pytest -q tests`) then timed out at 2700 s.
- No test imports `e004_run.py` or reads `E004.yaml` (grep over `tests/`). The founder raised the full-gate timeout to
  5400 s on main (commit e0c174e3, "T0388 full-gate timeout beside builders").
- Inference: the timeout was load on the machine, not this task's files. Nothing in attempt 2 adds a test.
- Reviews T0440 (physics) and T0441 (numerics) accepted attempt 1 with caveats. D0024 (main, 9a54cdb0) now records the
  founder decisions that the spec cited from task briefs.

### What changed, finding by finding (facts: the code)
| finding | change |
|---|---|
| T0440/T0441 major: the freeze missed `kernels.py`, `conductors.py`, `units.py`, `l2_dd.py` and the `__init__` files | `config.freeze.files` now holds every moduleforge file the stage loads (27; `--print-freeze` lists them). `freeze_hashes_match` fails if a loaded file is unlisted. A new end-of-stage check, `freeze_covers_loaded_sources`, catches lazy imports. scipy is pinned. |
| T0440/T0441 minor: `seed_provenance` cannot fail | Registered mode draws from `run.seed`, the seed ExperimentRun records. The check replays every slot's draw from the seed read independently (`MFOS_SEED`, or `DEV_SEED` in smoke) and compares moves and geometry. |
| T0440/T0441 minor: the reference lattice check ran after the draws | `references_on_lattice` is a new check, gated with `references_whole_mm` before any draw. A `measured_rules` ValueError on a judged reference becomes `RegistrationRefused` with its cause. |
| T0440 minor: compound intermediates were not re-checked | `pair_records` re-applies each compound step by step. It records each step's DRC result and whether the step changed the geometry, and checks that the stepwise result equals `perturb.apply`'s. `layouts_drc_clean_distinct` fails on any of these. The spec now says this is the same `drc.check` re-run, not an independent DRC (T0441). |
| T0441 minor: KeyError once the proxy pair is built in smoke | The proxy record is keyed by its slot id. |
| T0441 minor: r_L1 is resolved only to about ±0.005 at hmax 4 mm | `config.l1` fixes `hmax_m` 4 mm (the gate's mesh) and `hmax_check_m` 2 mm (reported). `l1_mesh_report` flags every value near a span or coverage threshold, or crossing one between the two meshes. |
| T0440 minor: the F1 rule cited a decision not on record | The spec cites D0024 items 1-5 (`config.decisions`, `f1_rule`, `stand_in`, `development_geometry`, the stagewise rule, the proxy). |
| T0441 note: scipy not pinned | `config.freeze.packages` adds scipy 1.18.1. |
| T0440/T0441 note: the pinned commit was missing from the review snapshot | The pin moved to 42db7eb5, a main commit and an ancestor of HEAD that survives a squash merge. The stage also checks that every frozen file's blob at the pinned commit carries the frozen hash. |

The hashes frozen in attempt 1 are unchanged; no file under `src/` changed between aea69183 and 42db7eb5.

### Counter-tests: the checks can fail (facts, run 2026-11-17)
`uv run python research/o004_e004/check_registration_checks.py` gives 15/15 as expected, on development geometry only.
- **Freeze.** Each of these fails the freeze: dropping `kernels.py`; altering the hash of `conductors.py` (it fails both live and at the pinned commit); pinning T0386's commit, whose blobs differ; a wrong scipy version. Attempt 1's commit, whose src blobs are identical, passes.
- **Seed.** A replay from `DEV_SEED + 1` is flagged on both slots.
- **Stagewise DRC.** Rules with a 1 m minimum width flag every pair, and every compound intermediate as well as every final layout.
- **gen2_0.** It is off the 1 mm lattice and fails the whole-mm check: the three nets' traces and dies 0, 2 and 3.
- **Proxy.** A built proxy record in smoke counts toward its slot with no KeyError.
- **Mesh report.** A synthetic ratio that crosses 0.90 between the two meshes is flagged; one far from every threshold is not.

### Smoke (`--smoke --stage registration`, development seed, 2D_Case_4 in both slots; facts)
- Exit 0, run status `complete`, all 20 declared checks reported, 7.4 s (L1 at 2 mm is now added).
- Passed: every check except `l1_span` and `proxy_pair_built`. Those two fail for the reasons in section 2.
- The five solve checks are not run.
- `l1_mesh`: largest ratio shift 4.7e-3 between 4 and 2 mm. The span verdict is the same at both meshes. One pair is
  flagged near the 0.98 upper end (0.9757 at 4 mm, 0.9732 at 2 mm).

### Still open (unchanged by attempt 2)
- **T0438** (perturb.py fixes) is in review. When it lands, refreeze with `--print-freeze`.
- **T0437** (`proxy_descent` step_mm) needs the founder.
- **The span and the allocation** are open in D0024.
- **F7(a)/(c)** are unassembled. The trigger has not fired and is undecided.
- **T0389** is the solve stage.
- **O004's pre-registration development distribution at l2_layout 0.5 mm** is T0387's F7(d) on its 11 Case 4 pairs
  (`research/o004_f7`, `distribution_L1_vs_0p5mm`). It does not cover the frozen allocation's own draws. Whether that
  suffices is the founder's reading (raised by T0441).
