# O006 pilot P4 — FastHenry feasibility on PowerSynth 2D_Case_4 (T0155)

**Research note, not evidence (O006 F4).** Input (b) of D0009's day-60 error band. Author: scientist agent, 2026-11-01.
Facts are marked [F] (measured or read here, reproducible by the listed command), inferences [I], speculation [S].

Artifacts: `research/scripts/o006_p4/fh_export.py` (exporter, `--selftest`), `research/scripts/o006_p4/run_fh.py`
(runner and summariser), `research/o006_p4/runs.jsonl` (one line per FastHenry run), `research/o006_p4/results.json`,
`research/o006_p4/binary_check.json`, `research/o006_p4/d0_solver_diag.json`.

## 0. Answer

**FastHenry is NOT usable at module scale for D0009 on the hardware agents may use** (`usable: false`). Per D0009,
band component (b) is therefore **l2_layout's discretisation estimate doubled**. The verdict follows the criterion fixed
before the ladder ran (§2). U1 (levels completed) and U2 (multipole = direct within 1e-3) pass. **U3 fails**: FastHenry's
own discretisation estimate is 2.44-3.09 nH (11-14 % of L) against l2_layout's 1.70-1.81 nH from P3, because only two
lateral levels fit in 6 GB. The third level (0.25 mm traces, 413k filaments) projects to ~10 GB and ~2.4 h per run.

What FastHenry did measure [F] (two-level extrapolation plus a thickness correction; uncertainties are the stated estimates, not
statistical CIs):

| geometry | f | L_FH extrap (nH) | L_l2 extrap, P3 (nH) | FH - l2 (nH) | rel. | combined estimate (rel.) |
|---|---|---|---|---|---|---|
| base | 10 MHz | 22.36 +- 3.09 | 22.18 +- 1.75 | +0.18 | +0.8 % | +-21.8 % |
| base | 20 MHz | 22.26 +- 3.09 | 22.04 +- 1.81 | +0.22 | +1.0 % | +-22.2 % |
| die_shift | 10 MHz | 22.07 +- 3.07 | 21.86 +- 1.76 | +0.21 | +0.9 % | +-22.1 % |
| die_shift | 20 MHz | 21.97 +- 3.07 | 21.72 +- 1.81 | +0.25 | +1.2 % | +-22.5 % |
| trace_width | 10 MHz | 21.99 +- 2.45 | 21.50 +- 1.70 | +0.49 | +2.3 % | +-19.3 % |
| trace_width | 20 MHz | 21.90 +- 2.44 | 21.36 +- 1.76 | +0.54 | +2.5 % | +-19.7 % |

Pair ratios R = L_pert / L_base [F]: die_shift FH 0.98719 +- 0.00063 vs l2 0.98567 +- 0.00172 (diff +0.0015, inside the
combined 0.0024); trace_width FH 0.9824 +- 0.0223 vs l2 0.9692 +- 0.0011 (diff +0.013; FastHenry's ratio is not converged:
0.9630 at k0 and 0.9696 at k1; the post-hoc check in §3.4 traces this to the 4 mm plane cell at k0). Same picture at 20 MHz (`ratio_diff` in results.json).

[I] The two references agree within 0.8-2.5 % on L, far inside either's error estimate. That is consistent, but it is not a
check of l2_layout at the precision D0009 needs: FastHenry's band is ~1.7 x l2_layout's. **A founder-run burst VM could
change the verdict** (§4): with k2 and the same estimators, FastHenry's estimate would fall to roughly 0.8 nH if the
lateral order is ~1 [S].

## 1. Set-up

* **Geometry** [F]: P3's reconstruction `research/scripts/o006_case4_layout.py` (`build("base")`, `"die_shift"`,
  `"trace_width"`), imported unchanged; the exporter reads only `Layout.to_conductors()`, the model l2_layout solves.
* **Tool** [F]: FastHenry 3.0wr (banner "Version 3.0wr (29Sep96, mod 031424)"), the provisioned binary
  `~/.local/bin/fasthenry` built outside the uv environment by `scripts/provision_compute.sh` (D0002). Its D0002 self-test
  (10 x 1 x 1 mm Cu bar, 1 kHz, `.units m`) gives 5.704256 nH, the value D0002 recorded (5.704 nH; closed form 5.695 nH)
  (`run_fh.py --binary-check`). **Discrepancy** [F]: the binary's sha256 is `eaa6d6fc…2d14`, not the `15bfbcd1…7365`
  D0002 recorded for its 2026-09-30 build; the file is dated 2026-10-31, so it was rebuilt (D0002 pins the tarball, which
  the script verifies, not the binary). [I] A rebuild with another compiler version changes the binary hash; the
  self-test agreeing to 7 digits makes a different solver unlikely, but the founder should know the binary changed.
* **Machine** [F]: this MacBook (16 GB, shared with agents). Agents may not launch burst VMs (docs/INFRASTRUCTURE.md §10:
  `scripts/burst_gcp.sh` runs with the founder's cloud credentials; P3 recorded the same rule). Every run here is local;
  runs that did not fit are listed as `not_run` with the reason. Runs went two to three at a time (single-threaded
  FastHenry, 10 cores), so wall times carry contention of the order of +-25 % [I].
* **Memory and time** [F]: `peak_mem_mb` is the child's `ru_maxrss` from `os.wait4` (`/usr/bin/time -l` is blocked by the
  sandbox, sysctl). The planned `ps` watchdog cannot see processes inside the agent sandbox, so it never fired; runs were
  instead screened before starting (direct: dense-memory estimate 8F^2 + 16M^2 bytes; multipole: linear projection from
  the largest completed run) against a 6 GB cap, plus a wall-clock timeout.
* **Port** [F]: one `.external` between the DC+ (L3, (13.5, 64.5) mm) and DC- (L2, (13.5, 36.5) mm) terminal-centre
  nodes, phase open; L = Im Z11 / (2 pi f) at 10 and 20 MHz from a single `.freq` sweep (fmin 1e7, fmax 2e7,
  ndec = 1/log10 2).

### 1.1 Modelling differences, FastHenry deck vs l2_layout (all stated in `fh_export.py`'s docstring)

| item | l2_layout (P3) | FastHenry deck (P4) |
|---|---|---|
| traces | cell-centred lattice, x/y branches, 10 graded thickness layers (top Cu) | same lattice concept; thickness by `nhinc` filaments, `rh = 2` grading; FastHenry kernel (exact bar formulas near, filament far) |
| planes | backside Cu and baseplate on the **same** lateral grid as the traces, 6 graded layers each | two floating `gplane`s, own pitch (`plane_cell`), `nhinc`/`rh` |
| dies | ideal short: footprint cells of the drain net + wire start merged | same (`.equiv`); lattice segments inside one footprint dropped (they would be self-loops) |
| wires | round filament bundle (disc + rings), 7-point sine arc, landing clamp >= 0.5 d above Cu | same 7-point arc; square section of equal GMD (a = 0.8711 d, Grover 1946), `wire_n^2` filaments; polyline split into `wire_sub` pieces; no landing clamp (end pieces overlap the Cu by <= a/2) |
| contacts (wire feet, port) | bilinear injection over the 4 surrounding cells | node merge with the nearest cell(s) of the net (ties merged); snap distance <= cell/sqrt 2 |
| signal traces | floating copper | floating meshes |
| solve | GMRES with a rigorous a-posteriori bound | dense LU (`-s ludecomp`) or GMRES with multipole matvec (`-s iterative -m multi -t 1e-4 -o 4`) |

[I] The trace lattice concept is shared, so FastHenry is independent of l2_layout in kernel, plane and wire treatment,
contacts and solver, but not in the decision to mesh copper on a cell-centred grid; extrapolation to zero cell size is
what removes that shared choice.

## 2. Plan, estimators and usability criterion (fixed before the first ladder run)

Written into `run_fh.py` (comment block above `summarise`) before the first k0 run; the only change after a Case 4
solve was the multipole expansion order (§3.1), made on the d0 solver check and before any ladder run.

* **Lateral ladder** (multipole): k0 / k1 / k2 = trace cell 1.0 / 0.5 / 0.25 mm (the 1 mm lattice is the coarsest on which
  every Case 4 edge lies), plane cell 4 / 2 / 1 mm, wire pieces per polyline segment 1 / 2 / 4; refinement ratio 2 in
  all three; fixed `nh_trace = nh_plane = 3`, `rh = 2`, `wire_n = 2`, `nw_trace = 1`.
* **Thickness study** at k0's lateral mesh: nh = 3 (k0), 5, 9 (nh - 1 doubles), plus nh = 1 for information.
* **Solver check** (base geometry, thin decks nh = 1): d0 (cell 1, plane 4 mm, 8.3k filaments), d1 (cell 1, plane
  2 mm, 14.4k), d2 (cell 0.5, plane 2 mm, 34k), each with direct LU and multipole where memory allows.
* **Estimators** (P3's formulas, so the two references are treated alike): three lateral levels monotone ->
  observed order p, Richardson value and GCI = 1.25 |e21| / (2^p - 1) (Roache 1998, *Verification and Validation in
  Computational Science and Engineering*, ch. 5); non-monotone -> finest value, 3 max|e|; two levels -> Richardson with
  assumed p = 1 and GCI = 3 |f2 - f1|. Thickness: correction D = L(nh9) - L(nh3) at k0 added to the lateral value
  (separability assumed [I]); term = 1.25 |t9 - t5| / (2^pt - 1) if monotone-contracting, else 3 max of the two changes.
  `L_extrap = f_ext + D`, `abs_est = GCI + term` (linear sum). Pair ratio R = L_pert / L_base per level, same formulas.
  l2_layout reference values: P3's `L_extrap_H` (assumed-order p = 0.72, two levels) and `abs_est_H`; pair ratios
  P3's `extrap_assumed_p` and `ratio_est`.
* **Usable at module scale** iff for every geometry and both frequencies: (U1) at least two lateral levels and all
  three thickness runs complete (a crash that recurs on the one retry counts as not completed); (U2) multipole within
  1e-3 (relative) of direct LU on every deck solved both ways; (U3) FastHenry's own estimate `abs_est_FH` is at most
  l2_layout's `abs_est_H` from P3. [I] Rationale for U3: band component (b) is only informative if FastHenry's own
  discretisation error is smaller than the error it is meant to check; otherwise D0009's fallback (doubling l2_layout's
  estimate) carries no less information.
* Resources: 6 GB peak-memory cap per run (two or three runs share the 16 GB machine with agents), 90 min timeout.

## 3. Results

### 3.1 Solver check: direct vs multipole (base, thin decks nh = 1) [F]

| deck | filaments | direct LU | multipole order 2 (default) | multipole order 4 |
|---|---|---|---|---|
| d0 (cell 1, plane 4 mm) | 8 344 | 25.7702 nH, 48 s, 0.94 GB | 25.5681 (-7.8e-3), 16 s, 0.11 GB | 25.7616 (-3.3e-4), 69 s, 0.16 GB |
| d1 (cell 1, plane 2 mm) | 14 364 | 25.5402 nH, 218 s, 2.56 GB | 25.5299 (-4.0e-4), 281 s, 0.24 GB | 25.5367 (-1.4e-4), 439 s, 0.31 GB |
| d2 (cell 0.5, plane 2 mm) | 34 048 | not run: estimated 13.9 GB dense | (run lost: the job was stopped at its time limit) | - |

Values at 10 MHz; 20 MHz agrees to <= 3e-6 relative (nh = 1 decks have no skin effect through the thickness).
Diagnosis of the d0 order-2 error (`d0_solver_diag.json`) [F]: tolerance 1e-6 instead of 1e-4 changed nothing, so it is not
the GMRES tolerance. Order 4 and order 6 agree to 2e-5, and GMRES with the direct matvec (`-m direct`) reproduces the LU value
to all printed digits. **FastHenry's default multipole order (2) is too low at module scale.** Every ladder run used
`-o 4`. That was the only setting changed after a Case 4 solve, and it was decided on this check before any ladder run.
[I] Direct LU stops at ~15-20k filaments on 16 GB (8F^2 + 16M^2 bytes). It cannot run any thickness-resolved Case 4 deck
(k0 alone has 25k filaments), so at module scale it serves only as a solver check on thin decks.

### 3.2 Ladder and thickness runs (multipole, order 4, tol 1e-4) [F]

L at 10 MHz in nH (20 MHz in results.json); wall time; peak RSS; F = filaments.

| run | F (base) | base | die_shift | trace_width | wall (s) | peak (GB) |
|---|---|---|---|---|---|---|
| k0 (1.0 / 4 mm, nh 3) | 25 056 | 24.6308 | 24.3284 | 23.7193 (2nd attempt) | 44-172 | 0.56-0.78 |
| k1 (0.5 / 2 mm, nh 3) | 102 192 | 23.6509 | 23.3557 | 22.9310 | 1203-1246 | 2.43-2.87 |
| k2 (0.25 / 1 mm, nh 3) | 412 584 | not run | not run | not run | ~8 800 projected | ~9.6-9.8 projected |
| k0_nh1 | 8 416 | 25.7866 | 25.4727 | crash x2 | 60-74 | 0.17 |
| k0_nh5 | 41 696 | 24.4241 (2nd attempt) | 24.1218 | 23.6213 | 100-110 | 1.10-1.15 |
| k0_nh9 | 74 976 | 24.3155 | 24.0141 | 23.5669 | 268-292 | 1.79-2.41 |

* Lateral k0 -> k1: -4.0 % (base), -4.0 % (die_shift), -3.3 % (trace_width). l2_layout's 1.0 -> 0.5 mm step in P3 was
  -2.15 %. The two-level GCI (Fs = 3, p = 1) is 2.37-2.95 nH and dominates FastHenry's estimate.
* Thickness nh 3 -> 5 -> 9: -0.21, -0.11 nH (base, 10 MHz), monotone with p = 0.85-1.16. Correction D = -0.15 to
  -0.39 nH, term 0.07-0.15 nH. nh 1 -> 3 lowers L by 4.5 %: thickness filaments are a first-order knob in FastHenry, as
  layers are in l2_layout (P3's thk_c -> lat0.5 was -1.2 %).
* k2 projection: memory linear in F from k1 (23.7 kB per filament). Time from the k0 -> k1 scaling (x7.2 for x4.1 filaments,
  exponent 1.40). A 6 GB cap leaves it out locally; an n2-highmem-32 burst VM would hold all three geometries in parallel
  in ~2.5-3 h [I].
* Wall times were measured with two or three FastHenry runs sharing the machine; treat them as +-25 % [I].

### 3.3 Crashes [F]

All crashes are SIGSEGV (signal 11) 1-4 s into the run, while FastHenry forms the sparse preconditioner. That is D0002's
known intermittent crash. No run crashed after the preconditioner was formed (k1: 3 of 3 completed). Across order-4
multipole attempts: 4 crashes in 20 attempts in the plan runs, plus 4 in 12 in a repeat test of the k0_nh1 deck
(`crash_repeat.json`: trace_width 1/6, base 3/6). Total 8 / 32 = 25 % (Wilson 95 % CI 13-42 %). The crash is not tied to
a geometry: the same deck crashes and succeeds. Direct LU: 0 of 2 attempts crashed; order 2: 0 of 2. [I] Crashes are early
and cheap, so retrying works (a retried run either crashes within seconds or completes); with the root cause unknown,
D0002's rule stands: never parse Zc.mat of a crashed run (the runner does not).

### 3.4 Post-hoc diagnostic (after the results; not used in any estimate)

Added after the results (`k0_p2`: k0 with k1's 2 mm plane pitch; base and trace_width only) to test one explanation of
FastHenry's unconverged trace_width ratio: the 4 mm plane cell at k0 cannot resolve the 2 mm move of the DC- trace edge.
[F] Base L 24.4357 nH (k0: 24.6308, so the plane pitch alone gives -0.195 nH of the -0.980 nH k0 -> k1 change; 920 s,
1.8 GB). trace_width 23.6996 nH (762 s, 1.7 GB). **Ratio 0.96988** (k0 0.96299, k1 0.96956, l2_layout 0.9692 +- 0.0011).
[I] The plane pitch causes all of the k0 -> k1 change in the trace_width ratio, so the extrapolated FH ratio (0.9824) is
an artefact of the k0 plane mesh fed through the p = 1 two-level formula, and probably the thickness correction for that
ratio too. With planes at <= 2 mm FastHenry's trace_width ratio sits within ~0.0005 of l2_layout's. Any further ladder
should start at plane pitch <= 2 mm. This diagnostic does not change the pre-stated verdict and is not in results.json's
estimates.

## 4. What would change the conclusion

* **A burst run of k2** (founder: `scripts/burst_gcp.sh --cmd "uv run python research/scripts/o006_p4/run_fh.py --plan
  ladder --mem-cap-mb 60000 --timeout-s 20000" research/o006_p4`, ~3 h on n2-highmem-32, then `--summarise`). If the
  three-level estimate is <= l2_layout's 1.75 nH, U3 passes and FastHenry becomes usable under the same criterion. If k1 -> k2
  shrinks by much less than half of k0 -> k1, the verdict stands. [S] Expected: usable for L; the trace_width ratio probably
  still needs a finer plane mesh.
* **The binary.** If the rebuilt binary (sha256 `eaa6d6fc…`, ≠ D0002's `15bfbcd1…`) turned out to behave differently from
  the pinned build on larger decks, every number here would need re-running on a binary with the recorded hash. The 7-digit
  self-test match argues against a difference [I].
* **Separability of the thickness correction.** D was measured at k0 only. The trace_width ratio moved by +0.0062 with
  nh 3 -> 9 at k0, the same size as its lateral change, so for ratios the correction may not separate [I].
* **The criterion.** U3 compares FastHenry's estimate with l2_layout's. If the founder holds that band (b) should be the
  measured FH - l2 difference whatever FastHenry's own uncertainty, the measured differences (+0.8 to +2.5 %) would enter
  instead. Doubling l2_layout's estimate (2 x 7.9-8.2 %) is the more conservative of the two.

## 5. Commands run

`uv run python research/scripts/o006_p4/fh_export.py --selftest` (exit 0) · `run_fh.py --binary-check` (exit 0) ·
`run_fh.py --plan solver --only-geometry case4_base` (stopped by the job time limit during the optional order-2 d2 run) ·
`run_fh.py --plan main` (all three geometries, exit 0) · `run_fh.py --plan solver_o4 --only-geometry case4_base` (exit 0)
· the d0 tolerance/order diagnostic and the crash-repeat loop (inline Python calling `run_fh.run_deck`; results in
`d0_solver_diag.json`, `crash_repeat.json`) · `run_fh.py --plan posthoc` · `run_fh.py --summarise` (exit 0).
