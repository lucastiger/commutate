# O008 kill shot: do the probe's designer proxy and its null gap survive l2_layout? (T0376)

Scientist agent, 2026-11-15. Investigate task. Development geometry (2D_Case_2R and 2D_Case_4 under D0023) and
development seeds (20261115 + j) only. No sealed seed, no judged reference, no production code change.
Labels: **[fact]** = read from a file or measured by a command in §7; **[inference]** = follows from facts by the stated
argument; **[speculation]** = plausible, untested.

## Pre-declared readings (from the task packet, fixed before any L2 solve)
- **KILL-A** fires on a layout if L_sub(W*) >= L_sub(W): the proxy rule returns W, and on 2R blind compaction recovered
  W at L1 (research/notes/o008-control-probe.md).
- **KILL-B** fires on a layout if a solved compaction or widen endpoint has L2 s = L_sub(x) / L_sub(W*) - 1 <= 0.02.
- Otherwise: "kill shot did not fire".

**This check is indicative and is not evidence for any O008 criterion.** It runs in the probe's parameter domain
without reach, on unsealed development draws. Every L2 value here uses 0.5 mm cells, coarser than E011's 0.25 mm, and
2R was run at 0.5 mm too, not at the 0.25 mm the packet's rule picks (§2.1).

## Result in one paragraph
**The kill shot did not fire on either layout at 0.5 mm cells** [fact]. KILL-A: W* stays below W at L2 on both layouts,
by 7.2 % on 2R (L1: 10.2 %) and 30.1 % on Case 4 (L1: 37.2 %). KILL-B: no solved null endpoint is within 2 % of
L_sub(W*). On Case 4 the closest null is +9.4 %. **On 2R it is +2.29 % (compact0, L1 +5.95 %), 0.29 percentage points
above the line.** That is less than the largest 0.5 → 0.25 mm shift of a layout ratio that E010 measured on 2R (0.35 %),
and less than E010's band estimate e_R on 2R ratios (median 0.42 %, max 1.18 %). **So 2R's KILL-B is not decided at
E011's resolution** [inference].

## 1. Step 1: deterministic regeneration (facts)
- `probe.py` was imported unchanged, with a clean argv so that `DIES_FIXED` is False (die rows free). Its `descend`
  (proxy, 200 steps) and, per draw j = 0..4, `ascent` (seed 20261115 + j) and `descend` (guided / compact / widen) were
  re-run with `keep=True`. The script skips the probe's `frozen_degrade` call; it consumes no random numbers, so the
  draws are unaffected.
- 2R used E010's committed `ctx.pkl`. Case 4 was rebuilt with `e010_run.dev_reference('case4', cfg)` from the registered
  E010 spec config, followed by `twin.twin`, as `e010_run.prepare` does. The ctx is saved at
  `research/o008_probe/l2_work/ctx_Case4.pkl`.
- **Every regenerated quantity equals the probe JSON exactly**, 54 per layout: L1(W), L1(W*), W*/W, proxy steps, and
  per draw seed, R_D, coordinates changed, Manhattan distance, and s and steps for each of the 3 modes. Max relative
  difference 0 on both layouts, so the 1e-9 tolerance is met with no slack used. Rebuilding Case 4 from E010's config
  therefore gives the same twin, to the last bit of L1, as E008's ctx that the probe used.
- All 17 layouts per reference were checked: W, W*, D_0..4, and the 15 endpoints. Each one rebuilt from its saved
  parameter vector reproduces its fingerprint and is DRC-clean under `spec.rules`.
- Parameter vectors are in `research/o008_probe/l2_work/regen_{2R,Case4}.json` (`layouts.<id>.params`, with
  `Params.NAMES`).

## 2. Step 2: l2_layout solves (facts)
### 2.1 Level, and one deviation
- `em_unknowns` / `em_cost` on the baseplate box:
  - 2R: 1.54 M unknowns, 6.42 GB at 0.25 mm (0.39 M, 2.21 GB at 0.5 mm).
  - Case 4: 4.11 M unknowns, 15.8 GB at 0.25 mm (1.03 M, 4.55 GB at 0.5 mm).
  - The packet's rule (finest cell whose estimate fits 8 GB) therefore gives **0.25 mm for 2R and 0.5 mm for Case 4**.
- **Deviation: 2R was solved at 0.5 mm.** A 6.4 GB process exceeds this machine's 5 GB budget. It may start only if
  `memory_pressure` reports >= 50 % free and swap in use is < 4 GB.
  - `sysctl vm.swapusage` is denied in the agent sandbox, so swap in use was bounded above by the total swapfile size.
  - That bound was 7.5 to 8.6 GB from 18:22 to 18:48, re-checked every 180 s (`l2_work/solve_1.log`), and never below
    6.4 GB afterwards (`l2_work/gate_log.jsonl`).
  - The 0.25 mm solve could not be started, so 2R ran at 0.5 mm, which the packet allows ("else 0.5 mm"). The reason
    is recorded in `l2_work/levels.json`.
  - **Both layouts are therefore at 0.5 mm, one level coarser than E011's 0.25 mm.**
- Threads: 2 per solve (`e010_run.thread_count`: the calibration shows two-thread solves faster), with OPENBLAS / OMP /
  MKL_NUM_THREADS and MF_L2_FFT_WORKERS = 2 and MF_L2_THREADS = 1 (`e010_run.child_env`).
- Each solve ran alone in a fresh process through `e010_run.child_em` (E010's frozen `lat0.5` level, 20 MHz).

### 2.2 Sanity checks (separate "the check is broken" from "the proxy is wrong")
| check | result |
|---|---|
| regeneration equals probe (1e-9 rel) | pass, max rel 0 (both layouts) |
| every layout rebuilds to its fingerprint and is DRC-clean | pass (34 layouts) |
| 2R W at 0.5 mm reproduces E010's committed VM solve of the same twin (`f95383…__emlat0.5`, Linux, other machine) | 14.0997275 nH both, rel 1.2e-14 |
| every GMRES solve converged (flag 0) | pass |
| largest a-posteriori solver_tol | 3.1e-5 (far below every gap read here) |

### 2.3 Memory events
The watchdog stopped four solve attempts because the swapfile total passed 8 GB: Case 4 W* after 286 s, then compact0
and guided0 at once (18:27), and later compact2. A 3.9 GB solve was running next to other work on the machine. The
attempts are kept in `l2_work/failed_attempts.jsonl` and their wall time counts toward the budget. Every mandatory layout
was re-solved later. No result comes from a stopped attempt.

## 3. Step 3: results per layout (facts; from `research/o008_probe/l2_check.json`, report written 20:08)
L1 s = L1(x) / L1(W*) - 1 (probe); L2 s = L_sub(x) / L_sub(W*) - 1; all L2 at 0.5 mm cells. Every guided, compact and widen endpoint of both layouts was solved (10 null endpoints per layout); total solve wall 4,158 s of the 3 h budget, killed attempts included.

| | 2D_Case_2R | 2D_Case_4 |
|---|---|---|
| cell (mm) | 0.5 | 0.5 |
| L_sub(W) (nH) | 14.0997 | 22.8528 |
| L_sub(W*) (nH) | 13.0909 | 15.9657 |
| L_sub(W*) / L_sub(W) | 0.9285 | 0.6986 |
| L1(W*) / L1(W) | 0.8979 | 0.6280 |
| best compaction endpoint (lowest L1 s) | compact1 | compact0 |
|   its L1 s / L2 s | +3.07 % / +3.64 % | +14.01 % / +9.36 % |
|   guided endpoint of that draw, L1 s / L2 s | -3.68 % / -1.01 % | +1.22 % / +1.09 % |
| lowest L2 s of solved null endpoints | +2.29 % | +9.36 % |
| null endpoints solved / unsolved | 10 / 0 | 10 / 0 |
| KILL-A / KILL-B | False / False | False / False |
| reading | kill shot did not fire | kill shot did not fire |

| layout | endpoint | kind | L1 s | L2 s | L2 s - L1 s | L2/L1 |
|---|---|---|---|---|---|---|
| 2D_Case_2R | W | twin | - | +7.71 % | - | 1.2623 |
| 2D_Case_2R | Wstar | proxy | - | +0.00 % | - | 1.3053 |
| 2D_Case_2R | guided0 | guided | -0.41 % | -0.73 % | -0.32 % | 1.3011 |
| 2D_Case_2R | compact0 | compact | +5.95 % | +2.29 % | -3.66 % | 1.2602 |
| 2D_Case_2R | widen0 | widen | +14.16 % | +7.54 % | -6.62 % | 1.2296 |
| 2D_Case_2R | guided1 | guided | -3.68 % | -1.01 % | +2.67 % | 1.3415 |
| 2D_Case_2R | compact1 | compact | +3.07 % | +3.64 % | +0.57 % | 1.3126 |
| 2D_Case_2R | widen1 | widen | +8.39 % | +7.40 % | -0.99 % | 1.2934 |
| 2D_Case_2R | guided2 | guided | +0.69 % | +2.95 % | +2.26 % | 1.3346 |
| 2D_Case_2R | compact2 | compact | +6.71 % | +6.19 % | -0.52 % | 1.2990 |
| 2D_Case_2R | widen2 | widen | +19.18 % | +14.82 % | -4.36 % | 1.2575 |
| 2D_Case_2R | guided3 | guided | +0.77 % | +0.94 % | +0.17 % | 1.3075 |
| 2D_Case_2R | compact3 | compact | +4.85 % | +2.97 % | -1.87 % | 1.2820 |
| 2D_Case_2R | widen3 | widen | +15.29 % | +9.32 % | -5.97 % | 1.2377 |
| 2D_Case_2R | guided4 | guided | +0.69 % | +0.76 % | +0.07 % | 1.3062 |
| 2D_Case_2R | compact4 | compact | +8.84 % | +5.44 % | -3.41 % | 1.2644 |
| 2D_Case_2R | widen4 | widen | +24.18 % | +15.58 % | -8.60 % | 1.2149 |
| 2D_Case_4 | W | twin | - | +43.14 % | - | 1.1805 |
| 2D_Case_4 | Wstar | proxy | - | +0.00 % | - | 1.3133 |
| 2D_Case_4 | guided0 | guided | +1.22 % | +1.09 % | -0.13 % | 1.3116 |
| 2D_Case_4 | compact0 | compact | +14.01 % | +9.36 % | -4.65 % | 1.2597 |
| 2D_Case_4 | widen0 (= compact0) | widen | +14.01 % | +9.36 % | -4.65 % | 1.2597 |
| 2D_Case_4 | guided1 | guided | +2.26 % | +0.87 % | -1.39 % | 1.2955 |
| 2D_Case_4 | compact1 | compact | +17.51 % | +12.08 % | -5.43 % | 1.2526 |
| 2D_Case_4 | widen1 | widen | +18.51 % | +12.81 % | -5.69 % | 1.2503 |
| 2D_Case_4 | guided2 | guided | +3.36 % | +2.83 % | -0.53 % | 1.3066 |
| 2D_Case_4 | compact2 (= widen2) | compact | +15.25 % | +10.44 % | -4.82 % | 1.2585 |
| 2D_Case_4 | widen2 | widen | +15.25 % | +10.44 % | -4.82 % | 1.2585 |
| 2D_Case_4 | guided3 | guided | +3.56 % | +2.73 % | -0.83 % | 1.3028 |
| 2D_Case_4 | compact3 | compact | +18.74 % | +13.35 % | -5.39 % | 1.2537 |
| 2D_Case_4 | widen3 | widen | +20.98 % | +14.80 % | -6.18 % | 1.2463 |
| 2D_Case_4 | guided4 | guided | +1.84 % | +1.71 % | -0.14 % | 1.3116 |
| 2D_Case_4 | compact4 | compact | +18.07 % | +12.68 % | -5.39 % | 1.2534 |
| 2D_Case_4 | widen4 (= compact4) | widen | +18.07 % | +12.68 % | -5.39 % | 1.2534 |

| layout | layout id | cell (mm) | unknowns | wall (s) | cpu (s) | peak RSS (GB) | threads |
|---|---|---|---|---|---|---|---|
| 2D_Case_2R | W | 0.5 | 369140 | 64 | 77 | 2.23 | 2 |
| 2D_Case_2R | Wstar | 0.5 | 377560 | 84 | 102 | 2.41 | 2 |
| 2D_Case_2R | compact0 | 0.5 | 380220 | 71 | 85 | 2.26 | 2 |
| 2D_Case_2R | compact1 | 0.5 | 380220 | 89 | 106 | 2.37 | 2 |
| 2D_Case_2R | compact2 | 0.5 | 380220 | 75 | 90 | 1.81 | 2 |
| 2D_Case_2R | compact3 | 0.5 | 380220 | 73 | 88 | 2.11 | 2 |
| 2D_Case_2R | compact4 | 0.5 | 378240 | 72 | 86 | 1.76 | 2 |
| 2D_Case_2R | guided0 | 0.5 | 372610 | 71 | 86 | 2.13 | 2 |
| 2D_Case_2R | guided1 | 0.5 | 373440 | 102 | 123 | 2.35 | 2 |
| 2D_Case_2R | guided2 | 0.5 | 374460 | 69 | 83 | 2.41 | 2 |
| 2D_Case_2R | guided3 | 0.5 | 374550 | 69 | 83 | 2.27 | 2 |
| 2D_Case_2R | guided4 | 0.5 | 374550 | 68 | 82 | 2.29 | 2 |
| 2D_Case_2R | widen0 | 0.5 | 380220 | 77 | 91 | 2.47 | 2 |
| 2D_Case_2R | widen1 | 0.5 | 380220 | 80 | 96 | 2.11 | 2 |
| 2D_Case_2R | widen2 | 0.5 | 380220 | 94 | 113 | 2.47 | 2 |
| 2D_Case_2R | widen3 | 0.5 | 380220 | 90 | 107 | 2.22 | 2 |
| 2D_Case_2R | widen4 | 0.5 | 378240 | 100 | 118 | 2.24 | 2 |
| 2D_Case_4 | W | 0.5 | 1020260 | 306 | 370 | 3.68 | 2 |
| 2D_Case_4 | Wstar | 0.5 | 1077980 | 257 | 310 | 3.80 | 2 |
| 2D_Case_4 | compact0 | 0.5 | 1081750 | 175 | 215 | 3.93 | 2 |
| 2D_Case_4 | compact1 | 0.5 | 1081740 | 228 | 280 | 3.92 | 2 |
| 2D_Case_4 | compact3 | 0.5 | 1080350 | 182 | 228 | 4.36 | 2 |
| 2D_Case_4 | compact4 | 0.5 | 1080500 | 180 | 220 | 4.55 | 2 |
| 2D_Case_4 | guided0 | 0.5 | 1069230 | 144 | 178 | 3.90 | 2 |
| 2D_Case_4 | guided1 | 0.5 | 1072490 | 156 | 194 | 3.91 | 2 |
| 2D_Case_4 | guided2 | 0.5 | 1069570 | 153 | 191 | 3.93 | 2 |
| 2D_Case_4 | guided3 | 0.5 | 1069090 | 155 | 194 | 3.88 | 2 |
| 2D_Case_4 | guided4 | 0.5 | 1070920 | 202 | 247 | 3.86 | 2 |
| 2D_Case_4 | widen1 | 0.5 | 1081740 | 169 | 210 | 4.47 | 2 |
| 2D_Case_4 | widen2 | 0.5 | 1076580 | 183 | 228 | 3.89 | 2 |
| 2D_Case_4 | widen3 | 0.5 | 1080350 | 231 | 279 | 3.89 | 2 |

## 4. Readings and interpretation
**KILL-A did not fire on either layout** [fact]. The margins, 7.2 % (2R) and 30.1 % (Case 4), are 6 to 25 times the
largest 2R ratio band in E010 (1.18 %). They would survive the 0.5 → 0.25 mm change unless Case 4 or 2R shifted by far
more than anything measured on 2R [inference]. L1 overstates the proxy's gain, by 3.0 points on 2R and 7.1 points on
Case 4, but the sign and most of the size survive at L2. The probe's "finding for the thesis review" (10 % and 37 %
below the twin at L1) becomes about 7 % and 30 % at 0.5 mm L2 [fact]. It is still not evidence (D0023, unsealed, no
thermal check).

**KILL-B did not fire at 0.5 mm, but on 2R it is not resolved** [fact / inference]:
- On 2R the solved compaction endpoints sit at L2 s +2.29 % to +6.19 %, against L1 s +3.1 % to +8.8 %.
- L1 overstates the null gap on most 2R compaction endpoints, and it orders them differently from L2. The packet's
  mandatory "lowest L1 s" endpoint (compact1, L1 +3.07 %) is not the lowest at L2: compact0 is (+2.29 %, L1 +5.95 %).
  A null chosen by L1 is therefore not the strongest null.
- 0.29 points above the line is within the discretisation scale of a 2R ratio: E010's 0.25 vs 0.5 mm lateral shift is
  up to 0.35 %, and its five-level e_R reaches 1.18 %. At E011's 0.25 mm the 2R reading could go either way
  [inference].
- On Case 4 the nearest null is 9.4 % (L1: 14 %). It would need a 7-point ratio shift to fire, so KILL-B is far from
  firing there [inference]. Case 4's 0.5 → 0.25 mm shift is not measured here (15.8 GB), so the 2R scale is borrowed
  [inference].

**What the guided stand-in does at L2** [fact]:
- 2R: L2 s -1.0 % to +2.95 %, with 4 of 5 within 2 % (L1: 5 of 5).
- Case 4: +0.9 % to +2.8 %, with 3 of 5 within 2 % (L1: 2 of 5). Every one of these runs was at the 60-step cap.

**For O008 (inference):** on 2R, the L2 gap between the seeded search (stand-in) and blind compaction is thin. The best
compaction endpoint is 2.29 % above W*, and the guided endpoints reach -1.0 % to +2.95 %. Criterion A3 ("nulls beaten
by a resolved margin on every layout") is at risk on 2R once E011 draws its own degraded copies and reads them with a
band of e_R ~0.4–1.2 %. Case 4 discriminates clearly.

**L2/L1 ratio** (table above): L1's bias differs between layouts of one reference [fact]. That is why L1 s does not
order the endpoints the way L2 s does on 2R. E011's L1 screen and its fixed shortlist need that spread in mind
[inference].

## 5. Competing explanations considered (mf-diagnosis)
| explanation | discriminating test | outcome |
|---|---|---|
| H1: the probe's W* gain is an L1 artefact (L1 bias exploited by the descent) | L_sub(W*) vs L_sub(W) | rejected at 0.5 mm on both: gain 7 % / 30 % at L2 |
| H2: the probe's null gap is an L1 artefact | L2 s of null endpoints vs 0.02 | Case 4: rejected (9.4 %). 2R: partly supported: the gap shrinks from 3.1-8.8 % to 2.3-6.2 % and its closest member is within resolution of the line |
| H3 (experimental): the regenerated layouts are not the probe's | 54 quantities per layout vs probe JSON | rejected (max rel 0) |
| H4 (experimental): the L2 numbers are wrong on this machine | W at 0.5 mm vs E010's committed VM solve | rejected (1.2e-14) |
| H5 (experimental): 0.5 mm cells are too coarse to decide KILL-B on 2R | 0.25 mm solves of 2R W*, compact0, compact3, compact1 | **not run** (memory rule, §2.1); E010's 2R band says the 0.29-point margin is inside the 0.5 → 0.25 mm scale |

**What would prove this note wrong:**
- A 0.25 mm solve with L_sub(compact0) / L_sub(W*) - 1 <= 0.02 on 2R. KILL-B then fires on 2R at E011's level.
- L_sub(W*) >= L_sub(W) at 0.25 mm on either layout. That needs a ratio shift 20 times the largest measured, so it is
  unlikely [inference].

## 6. Recommended actions (no production code; scope unchanged)
1. Before the search, proxy and null modules are built, solve 2R at 0.25 mm. The decisive four are W*, compact0, compact3
   and compact1; add W and guided1 if there is room. That is 4 to 6 solves at about 6.4 GB and about 15 min each on the
   VM (E010: 815-955 s at 0.25 mm on 2R). Run them on this Mac only when swap is < 4 GB, else on an e2-highmem VM. The
   script resumes; add `--level-2r lat0.25` and point it at a fresh work directory. A KILL-B there (compact0 <= 2 %)
   would mean blind compaction recovers W* on 2R. A3 would then fail on 2R, and E011's design should be reconsidered
   before it is built.
2. Choose O008's nulls, and judge them, by L2, not L1. On 2R the L1-lowest compaction endpoint was not the L2-lowest
   (§4). A null selected by L1 understates the null.
3. Plan the search budget around Case 4. Every guided run there hit the 60-step cap, and at L2 only 3 of 5 reach 2 %.
4. Lesson recorded in `project/memory/lessons.md`: swap and process monitoring in the agent sandbox.

## 7. Reproduction (commands, in order; exit codes)
- `uv run python research/o008_probe/l2_check.py regen 2R` → 0 (502 s); `… regen Case4` → 0 (1106 s), run concurrently
  (two light L1 processes).
- `uv run python research/o008_probe/l2_check.py solve --case4-first --max-wait-s 1200` → 3 (memory gate for 2R
  0.25 mm stayed closed; Case 4 W solved; three attempts stopped by the swap watchdog). Log: `l2_work/solve_1.log`.
- `uv run python research/o008_probe/l2_check.py solve --case4-first --level-2r lat0.5 --max-wait-s 2400 --override-reason
  "…"` → 0 (log `l2_work/solve_2.log`).
- `uv run python research/o008_probe/l2_check.py report` → 0, writes `research/o008_probe/l2_check.json` and
  `l2_work/tables.md`.
- Files: `research/o008_probe/l2_check.py`, `l2_check.json`, `l2_work/` (regen, per-solve records, logs, gate log).
