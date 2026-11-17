# O004 F7(b)-(d): l2_layout pilot on 2D_Case_4 development pairs (T0387)

RESEARCH ONLY, NOT EVIDENCE. Development geometry (2D_Case_4, gen2_0) and development seeds only (O004 F2). Nothing was
drawn and no L1 or FastHenry value was computed on 2D_Case_2R or 2D_Case_6. The one exception is F7(b): the l2_layout
0.25 mm solve of 2D_Case_6's frozen reconstruction (plus its mesh count used to size that solve), completed locally.
Code: `research/o004_f7/pilot_l2.py`; outputs: `dev_pairs.json`, `f7c_local.json`, `vm_jobs_l2.json`, `span_reach.json`,
solve records in `research/o004_f7/solves/`. `uv run python research/o004_f7/pilot_l2.py --check` re-validates them
against each other and against the layouts' fingerprints, without solving.

## Answer
- **F7(b) passes as a feasibility check:** the Case 6 0.25 mm l2_layout solve completed locally (595 s, 4.75 GB).
- **Exclusion rate so far: 0 of 2 pairs with a complete F1 ladder.** Both are O006 P3's pairs. Only P3's trace_width is a
  frozen-rule geometry; P3's die_shift is not. All 11 drawn development pairs are still pending, because their 0.25 mm
  level cannot run on this Mac.
- **F7's response trigger has not fired on the data so far, but it is undecided.** Every drawn pair, the stand-in included,
  still lacks its 0.25 mm and thk_f levels.
- **Chance of no exclusion among the 13 judged pairs:** 1.0 at the observed rate (0/2). That figure is uninformative: with
  n = 2 the one-sided 95 % upper bound on the rate is 77.6 %, which implies a chance as low as 3.5e-9.
- **The stand-in is marginal.** Stand-in: lowest reachable, r = 0.7616, stands in for r <= 0.75. Its frozen filament term
  alone is 0.0018 / 0.0023 (10 / 20 MHz), against F1's cap of 0.005. If its missing 0.25 mm step contracts like P3's
  die_shift (rho = 0.56), its estimate is about 0.0034. At rho = 0.8 it would be about 0.0060, and it would be excluded
  (inference, below).
- **L1 overstates the larger effects by up to 4.6 ratio points.** The stand-in is r = 0.7616 at L1 but 0.8074 at l2_layout
  0.5 mm.
- **Span reach (founder question).** [0.75, 0.98] with at least 3 pairs below 0.90 cannot be reached on either development
  layout. Case 4's lowest reachable lower end is 0.7616 (20 MHz) / 0.7613 (10 MHz). gen2_0's is 0.8880 by `apply`, and
  0.9445 by what `perturb.draw` can actually draw, because `draw` raises for trace_width on gen2_0.

## Facts
### F7(c) development pairs (`dev_pairs.json`)
- Draw: `perturb.draw(case4, {each single type: 2, compound: 2}, seed=20261116)`. The rules are
  `measured_rules(case4, E008 dev overrides)`, as in `tests/unit/test_perturb.py`.
- Added to the draw: the stand-in, T0386's pinned `LOWEST_COMPOUND` (LS die-row shift (-3, 2) mm, PHASE edge 3 +7 mm, HS
  landings (1, 9) mm). It is labelled "lowest reachable, r = 0.7616, stands in for r <= 0.75" (founder decision (i)); no
  lower pair was searched for.
- All 11 layouts are DRC-clean, distinct, and on the 1.0 / 0.5 / 0.25 mm lattices.
- Every pair kind is present, and 2 pairs lie below 0.90 at L1.
- r >= 0.98 is present (dev02 0.9999, dev04 0.9811, dev05 0.9990, dev08 0.9830).

| pair | kind | r L1 10 / 20 MHz | r l2 1.0 mm (20) | r l2 0.5 mm (20) | l2(0.5) - L1 (20) |
|---|---|---|---|---|---|
| dev00 | die_row_shift HS (8, -6) | 0.8879 / 0.8882 | 0.9019 | 0.9009 | +0.0127 |
| dev01 | die_row_shift HS (-1, -5) | 0.9278 / 0.9281 | 0.9293 | 0.9275 | -0.0006 |
| dev02 | trace_width PHASE e5 -2 | 0.9999 / 0.9999 | 1.0016 | 1.0016 | +0.0018 |
| dev03 | trace_width PHASE e4 -4 | 1.0774 / 1.0776 | 1.0609 | 1.0609 | -0.0167 |
| dev04 | terminal_copper PHASE S m8 +6 | 0.9812 / 0.9811 | 0.9865 | 0.9863 | +0.0052 |
| dev05 | terminal_copper PHASE E m8 -7 | 0.9990 / 0.9990 | 1.0016 | 1.0013 | +0.0023 |
| dev06 | wire_landing HS (4, 1) | 0.9757 / 0.9756 | 0.9791 | 0.9794 | +0.0038 |
| dev07 | wire_landing LS (3, 2) | 1.0438 / 1.0437 | 1.0322 | 1.0330 | -0.0107 |
| dev08 | compound | 0.9831 / 0.9830 | 0.9883 | 0.9886 | +0.0056 |
| dev09 | compound | 0.9493 / 0.9495 | 0.9553 | 0.9543 | +0.0049 |
| stand-in | compound (3 types) | 0.7613 / 0.7616 | 0.8082 | 0.8074 | +0.0457 |

(F7(d): the 1.0 / 0.5 mm values are from `f7c_local.json`, `distribution_L1_vs_0p5mm`.)

### Local l2_layout solves (this Mac, 2 threads each, one at a time)
- **lat1.0** (14 solves; CELL[0] = 1.0 mm at refinement 0, as in E010's `child_em`): 71-138 s, 1.3-2.0 GB, 0.25 M unknowns.
- **lat0.5** (12 solves): 220-390 s, 3.7-5.4 GB, 1.01-1.04 M unknowns.
- **thk_c** (2 solves): 124 s, 2.8 GB.
- **fil_f** (2 solves): 298-339 s, 5.9 GB.
- Solver health: every GMRES flag is 0, and the relative tolerance on L is at most 3.5e-5.
- Reproduction of P3: this task's base lat1.0 / lat0.5 and P3-pair lat1.0 solves give P3's L to at most 1.4e-14
  (`p3_reuse_check`). So P3's base lat0.25 and thk_f solves are reused. P3's lat0.25 files carry the current fingerprints.
  P3's Mac files carry an older `Layout.fingerprint` value for the same geometry, an encoding change shown by the identical L.
- **0.25 mm was not run locally on Case 4.** One Case 4 0.25 mm solve peaks at 15.8-15.9 GB per process (measured:
  `research/notes/l2-thread-calibration.md`, and the P3 VM files). That is above this Mac's 10 GB single-process cap.
  The packet's "about 8 GB each" is not what was measured, and l2_layout has no memory knob short of editing `src/`.
  - The three P3 thk_f solves were 8.1 GB each. The swap condition for the 10 GB exception cannot be verified in the
    sandbox (`sysctl vm.swapusage` is denied, and the swapfile bound is 4.3 GB). So thk_f also goes to the VM.

### F7(c) ladder of the base and the stand-in (`f7c_local.json`)
- Base L at 20 MHz, in nH:

  | lat1.0 | lat0.5 | lat0.25 (P3 VM) | thk_c | thk_f (P3) | fil_f |
  |---|---|---|---|---|---|
  | 23.3234 | 22.8174 | 22.6365 | 23.0108 | 22.8020 | 22.9065 |

- Stand-in ratio at 20 MHz:

  | lat1.0 | lat0.5 | thk_c | fil_f | lat0.25 | thk_f |
  |---|---|---|---|---|---|
  | 0.80820 | 0.80736 | 0.80815 | 0.80660 | pending (VM) | pending (VM) |

- Stand-in estimate terms:
  - F1's E_R is +inf (pending). By O004 F1, a missing level makes the estimate +inf.
  - Filament term 3 |R(fil_f) - R(0.5)|: 0.00180 at 10 MHz and 0.00228 at 20 MHz.
  - Lateral step 1.0 -> 0.5 mm: -0.106 % (relative), just above the 0.1 % step floor. So `gci_step_floor` will fall back
    to `gci_capped` unless the 0.25 mm step changes that.
- **P3 precedent pairs (complete ladders):**
  - **die_shift:** E_R = 0.00172 / 0.00177 (10 / 20 MHz), counted. Lateral rho = 0.56, monotone. It is not the geometry
    of the frozen die_row_shift HS (0, -1): the frozen rule also extends the host copper (fact: `same_geometry` false).
  - **trace_width:** E_R = 0.00162 / 0.00144, counted. Steps of 0.007 % and 0.026 % are both below the floor, so the
    lateral term is 3 max|d|. It is the frozen trace_width DC- edge 0 +2 mm geometry (`same_geometry` true).

### F7(b): 2D_Case_6 reconstruction, l2_layout 0.25 mm
**Completed locally.** The solve ran here because the reconstruction has 1.095 M unknowns at 0.25 mm (its mesh count),
inside the 5 GB budget, where the 16 GB VM sizing assumed it would not fit.
- Unpatched refinement 1 (0.25 mm). L = 7.0539 / 7.0019 nH at 10 / 20 MHz.
- 595 s wall, 703 s CPU, peak 4.75 GB.
- GMRES flags 0 / 0 (166 / 176 iterations), relative tolerance on L 2.3e-5.
- Fingerprint 71e07ae1…cb7 (`solves/case6_recon__lat0.25.json`).
F7(b) passes as a feasibility check: the solve completes. No FastHenry, no 2R, and no other level was run on Case 6.

### Span reach on the development layouts (`span_reach.json`; founder correction 2026-11-16 17:55 UTC)
- **Method: T0386's structured search.**
  - Exhaustive integer scans of each single move's frozen range, keeping only DRC-clean, changed layouts.
  - Coordinate descent at 20 MHz over all ten 2- and 3-type stagewise compounds, from the best singles. Each coordinate
    step is a full scan of one component's frozen range: up to 3 sweeps for the minimum, 1 for the maximum.
  - A joint stage for each 3-type compound: top-15 x top-15 head chains, a full scan of the third component on the best
    8, then descent.
  - On Case 4 the pinned T0386 compound was also a start, and it was recomputed. Without it, descent reached 0.7895, so the
    0.7616 minimum may rest on that start.
- **2D_Case_4** (on the 1 mm lattice):
  - Lowest 0.7616 / 0.7613 (20 / 10 MHz); highest 1.3407 / 1.3400.
  - Singles' minimum: die_row_shift 0.8732, trace_width 0.9147, wire_landing 0.9628, terminal_copper 0.9811.
  - 14 distinct single die-row shifts lie below 0.90, so "3 below 0.90" is reachable. [0.75, 0.98] is not: the lowest
    reachable lower end is 0.7616.
- **gen2_0** (E010 dev seed 20261110). Fact: it is not on the 1 mm lattice (on the 0.5 / 0.25 mm lattices only), so
  O004's lattice rule would refuse layouts drawn from it.
  - Fact: `perturb.long_sides` raises "edge has copper on both sides" for DC+ and PHASE, and `_draw_params` evaluates
    every net. So `perturb.draw` raises for every trace_width draw on gen2_0, and for any compound with a trace_width
    component (reproduced: `draw(gen2_0, {trace_width: 1})` raises ValueError).
  - By `apply` (DC- only for trace_width): lowest 0.8880 (die-row + trace-width + terminal compound), highest 1.1590.
    Below 0.90 is reached only by compounds containing trace_width.
  - By what `draw` can draw: lowest 0.9445 (die-row + terminal + landing). No pair below 0.90.
  - Singles' minimum: die_row_shift 0.9847 (only 14 of 1248 clean), trace_width 0.9295, terminal_copper 0.9745,
    wire_landing 0.9856.
  - Verdict: [0.75, 0.98] is not reachable. The lowest reachable lower end is 0.8880 by `apply`, or 0.9445 by `draw`.

### VM manifest (`vm_jobs_l2.json`; the founder launches it, agents never start VMs)
- **Jobs:** 42 in all.
  - 11 lat0.25: the 10 drawn pairs and the stand-in. The base's 0.25 mm level is reused from P3.
  - 11 thk_f, 10 thk_c and 10 fil_f, so that every drawn pair gets the full F1 estimate.
  - No Case 6 job: F7(b) finished locally.
- **Projections:**
  - lat0.25: 16.0-16.2 GB and about 5,900-6,000 s each (two threads, on the n2d calibration).
  - thk_f: 8.1 GB, about 2,300 s.
  - thk_c / fil_f: under 6 GB, about 930 s.
  - Four at a time on one n2d-custom-8-81920-ext: makespan about 7.7 h, about $3.4 at an approximate $0.40/h.
- **Command:**
  `MF_REF=task/T0387-f7-b-d-l2-layout-check-on-case-4-develop MF_GCP_PROVISION=0 MF_GCP_SPOT=auto scripts/burst_gcp.sh
  --cmd "uv sync --all-groups && uv run python research/o004_f7/pilot_l2.py --run-vm --parallel 4 --threads 2"
  research/o004_f7/solves n2d-custom-8-81920-ext us-central1-a`, then `--assemble` and `--check` locally.
  - MF_REF needs this branch committed first. The solves resume per file.

## Inferences (not results)
- **Projected exclusions** (`f7c_local.json` `projection_inference`).
  - Method: the missing 0.25 mm ratio step is taken as rho x the measured 1.0 -> 0.5 mm step, plus P3's thickness term.
    The filament term is the measured one where it exists, else P3's 3.7e-4, which may understate it: the stand-in's
    measured term is 6x larger.
  - At rho = 0.56 (P3 die_shift) no pair is excluded.
  - At rho = 0.8, dev01 (die-row shift, r_L1 0.928, E about 0.0076) and the stand-in (about 0.0060) are excluded.
  - That would fire the F7 trigger (an excluded pair with r <= 0.90, and more than one in all). At that rate (2/11), the
    chance of no exclusion among 13 judged pairs is (9/11)^13 = 0.074.
  - At rho = 0.56 the rate is 0/11. The one-sided 95 % bound on it is 23.8 %, so the chance of no exclusion is at least
    0.029.
- **Where the risk sits.** The pairs at risk are die-row shifts across the row and the large compound. That matches P3:
  moves that change the wire length cancel the least.
- **The filament term is the biggest single piece of the stand-in's estimate.** P3 §5.3 showed that the frozen
  filament term (radial-only annulus bisection) overstates the filament error about 40x. Under F1 it can therefore push
  a large-effect pair toward exclusion through a term known to be an artefact. That is a criteria matter for the founder,
  not a fix made here.
- **L1 exaggerates |1 - r| for large moves** (the stand-in by 0.046, dev03 by 0.017, dev00 by 0.013).
  - O004's registration span and the 6 % coverage rule are both judged at L1. So the range FastHenry and l2_layout
    actually judge will be narrower than the registered L1 span: about 0.81 at the low end on Case 4.

## What would prove this wrong
- Any VM 0.25 mm solve whose base or pair L differs from the 1.0 / 0.5 mm trend by more than P3's step pattern. Rerun
  `--assemble`; the exclusion rate is then a fact, and the projection above is void.
- A Case 4 compound below 0.7616 found by a stronger search: span_reach is a lower bound on reach, not a proof of
  unreachability.

## Process deviations (stated so a reader can discount them)
- For about 10 min, three light processes ran at once (one solve queue and two L1 span searches, under 5 GB in total).
  The sandbox denies the process listing that would have let me stop one.
- Two fil_f solves (5.9 GB) and one lat0.5 solve (5.4 GB) exceeded the 5 GB total budget. memory_pressure was at least 60 %
  free, but swap below 4 GB could not be verified. No swap growth past the 8 GB stop was observed (swapfiles at 4.3 GB).
- The joint search stage was added after Case 4's descent had been seen (0.7895 > T0386's 0.7616) and before gen2_0
  was searched. It is research search power, not an evaluation.

## Attempt 2 (2026-11-16, after the orchestrator merged main): status of the results above
- **The results above are unchanged.** Main's merge (70f426fc, then HEAD d2cb5b20) touched no code these results depend
  on: `generate/perturb`, `geometry`, `drc`, `physics/peec`, `solvers/l2_layout` and `mfos.metrics` are all untouched.
  `uv run python research/o004_f7/pilot_l2.py --check` exits 0 on HEAD. That check rebuilds every layout to its
  recorded fingerprint, checks `perturb.rules_sha256` and recomputes every E_R.
- **The definition-of-done failure was the fast gate's 900 s timeout, not this branch.** On the same HEAD the fast unit
  suite took 984 s in one run and passed `uv run mfos gate --fast` (exit 0) in 746 s twenty minutes later, at similar
  load. Diagnosis: `research/diagnoses/T0387.md`. Raw output: `research/o004_f7/gate_unit_timing_attempt2.txt` and
  `gate_fast_attempt2.txt`.
- **No new solves.** The thk_f level (8.1 GB) needs the 10 GB single-process exception, and its swap condition still
  cannot be verified. `/System/Volumes/VM` holds five 1.07 GB swapfiles (an upper bound of 5.4 GB, above the 4 GB
  limit), one of them created at 17:37 today. `sysctl vm.swapusage` is denied. memory_pressure showed 58 % free. So
  thk_f and every Case 4 0.25 mm solve (15.8 GB measured: `research/o006_p3/solves/case4_base__lat0.25.json`
  `peak_mem_mb`) stay in `vm_jobs_l2.json`.
- **The exclusion rate is still 0 of 2 complete pairs, with 11 pending.** The F7 trigger has not fired and is undecided
  until the VM jobs are assembled.

## Burst 1 and the final F7(c) result (founder session, 2026-11-17)
- **Runs.** The founder ran the 42 jobs of `vm_jobs_l2.json` on n2d-custom-8-81920-ext (`burst_gcp.sh`, Spot, from main
  after T0387's merge f2a64fd0). The first burst stopped at the script's default 6 h limit (`MF_GCP_MAX_HOURS`) with 32 jobs done; a
  resumed burst (`MF_GCP_RESUME=1`) ran the last 10 and exited 0. All 42 solves converged (GMRES flags 0). Each 0.25 mm
  solve peaked at 15.8-16.1 GB and took 1.2-1.6 h on 2 threads, as projected.
- **F1 reading.** The status uses the founder's relative reading, E_R / r <= 0.5 % (D0024 item 1, decided before any of
  these results existed), not the absolute E_R <= 0.005 this note's earlier sections used. In this pilot a pair whose
  missing level is still a VM job is 'pending', not 'excluded'.
- **Result (`f7c_local.json`, `pilot_l2.py --check` OK).** All 13 pairs have complete ladders (the 11 frozen-rule
  development pairs and P3's two precedent pairs). None is excluded. Largest E_R / r: the stand-in compound (r_L1 0.7616,
  r at 0.25 mm 0.8070), 0.289 % at 10 MHz and 0.349 % at 20 MHz. Next: dev03 trace_width 0.347 % / 0.290 %, dev07
  wire_landing 0.284 % / 0.298 %, dev01 die_row_shift 0.232 % / 0.260 %. Every other pair is below 0.22 %. Under the
  absolute reading every pair is also counted.
- **F7(c)'s trigger does not fire.** No development pair with r <= 0.90 is excluded, and none is excluded at all. The
  observed rate is 0 of 13; its one-sided 95 % upper bound is 20.6 %, at which the chance of no exclusion among E004's 13
  judged pairs would be 0.05.
- **Inference, not a result.** The large-effect pairs converged faster than the rho = 0.8 projection assumed; the
  stand-in, the pair most at risk, sits at 0.70 of the cap. The judged references are other layouts, so this is a
  development rate, not a bound for them.
- **Reproducibility after T0438.** T0438 changed `perturb.rules_sha256()` and renumbers Case 4's trace_width edges, and
  `measured_rules` now refuses gen2_0 (off the 1 mm lattice). The development pairs are fixed geometries, identified by
  the fingerprints in `dev_pairs.json` and every solve file; `--check` verifies those instead of a rebuild once the rules
  hash differs. `span_reach.json`'s gen2_0 results can no longer be regenerated with the current rules.
