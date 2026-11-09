# l2_layout thread pinning and concurrency on an 8-vCPU VM (input to E008's run plan)
Date: 2026-11-09 · Founder session (not an mfos task) · Script: `research/scripts/l2_thread_calib.sh` (commit 433a0b78) ·
Data: `research/l2_thread_calib/` · Confidence: high on the measured numbers, medium on the E008 projection

**This is a research note, not evidence.** It uses O006 pilot P3's own `--child` mode (Case 4 and its two perturbations,
P3's levels, `src/` untouched); nothing here went through `mfos.evidence.ExperimentRun`.

## Answer (≤ 5 sentences)
P3's 0.25 mm Case 4 solves on the n2-highmem-32 logged 61,658-64,021 CPU-s for 6,941-7,202 s wall, about 9 busy cores per
solve, because Linux numpy's OpenBLAS starts a busy-waiting thread per vCPU in every process. Pinned to one thread, the
same solves give L equal to P3's to <= 6.3e-14 with identical GMRES iteration counts, and use one core each. Four pinned
0.25 mm solves at once on an 8-vCPU, 80 GB N2D took 6,268-6,519 s each (peak 15.8-15.9 GB), slightly faster than P3's
two-at-a-time solves on 32 vCPUs, at a tenth of the CPU. With two threads each (phase C) the four solves took 5,678-5,862 s, 9-10 % less wall at 1.5 cores each, with L again
equal to P3's to <= 6.2e-14: about $0.24 per 0.25 mm solve at the regular N2D price ($0.27 pinned), against about $2.10
for P3's configuration (n2-highmem-32 at $2.10/h, two solves per ~2 h).

## 1. Setup
- VM: `n2d-custom-8-81920-ext` (AMD EPYC 7B13, 4 cores x 2 threads, 78 GB usable), Spot, us-central1-a, 2026-11-09,
  launched by the founder with `scripts/burst_gcp.sh --cmd "bash research/scripts/l2_thread_calib.sh" ...`.
- Pinned: `OPENBLAS_NUM_THREADS = OMP_NUM_THREADS = MKL_NUM_THREADS = 1`, `MF_L2_FFT_WORKERS = 1`, `MF_L2_THREADS = 1`.
  Two threads (phase C): the same with 2, `MF_L2_THREADS = 1` (serial assembly is l2_layout's default; see the comment
  above `NTHREADS` in `src/moduleforge/solvers/l2_layout.py`).
- Phases: A, one 0.5 mm base solve alone with default threads, then pinned; B, four pinned 0.25 mm solves at once (P3's
  three geometries, base twice); C, the same four with two threads each.
- Mac reference (founder session, same `--child` mode, loaded machine, Apple Accelerate BLAS, which does not spin):
  0.5 mm base pinned 419 s wall / 408 CPU-s; default threads 252 s / 372 CPU-s; L equal to P3's to 8e-15.

## 2. Results (from `research/l2_thread_calib/summary.txt`)
| run | wall s | CPU s | cores | peak GB | GMRES iters | max abs(L / L_P3 - 1) | P3 wall / CPU s |
|---|---|---|---|---|---|---|---|
| A default, 0.5 mm base | 647 | 2015 | 3.1 | 4.1 | 171 / 186 | 2.5e-14 | 206 / 317 (Mac) |
| A pinned, 0.5 mm base | 846 | 847 | 1.0 | 4.1 | 171 / 186 | 2.7e-14 | |
| B pinned, 0.25 mm base | 6310 | 6310 | 1.0 | 15.8 | 257 / 274 | 5.1e-14 | 7202 / 64021 |
| B pinned, 0.25 mm base (repeat) | 6360 | 6359 | 1.0 | 15.8 | 257 / 274 | 5.1e-14 | 7202 / 64021 |
| B pinned, 0.25 mm die_shift | 6268 | 6268 | 1.0 | 15.9 | 255 / 270 | 6.3e-14 | 7076 / 62771 |
| B pinned, 0.25 mm trace_width | 6519 | 6519 | 1.0 | 15.8 | 267 / 283 | 5.0e-14 | 6941 / 61658 |
| C two threads, 0.25 mm base | 5733 | 8511 | 1.5 | 15.8 | 257 / 274 | 5.7e-14 | 7202 / 64021 |
| C two threads, 0.25 mm base (repeat) | 5730 | 8499 | 1.5 | 15.8 | 257 / 274 | 5.7e-14 | 7202 / 64021 |
| C two threads, 0.25 mm die_shift | 5678 | 8409 | 1.5 | 15.9 | 255 / 270 | 6.2e-14 | 7076 / 62771 |
| C two threads, 0.25 mm trace_width | 5862 | 8676 | 1.5 | 15.9 | 267 / 283 | 5.1e-14 | 6941 / 61658 |

## 3. Findings
- **Fact: pinning does not change the answer.** Every pinned solve reproduces P3's L to <= 6.3e-14 relative (P3's solver
  tolerance is 3.2e-5 of L) with the same GMRES iteration counts.
- **Fact: the threads in P3's VM runs were waste.** Pinned, a 0.25 mm solve needs about 6,300 CPU-s; P3 logged about
  63,000. On this VM, default threads made one 0.5 mm solve 1.3x faster than pinned at 2.4x the CPU.
- **Fact: four pinned solves share 4 physical cores without a large penalty.** Pinned 0.25 / 0.5 mm wall ratio is
  6,310 / 846 = 7.5 (the 0.5 mm solve ran alone), against 6.5 for CPU on the Mac's generator layouts (T0075), so sharing
  memory bandwidth costs at most about 15 %.
- **Fact: a cloud core is about 2x slower than this Mac's core** on l2_layout (846 s against 419 s, 0.5 mm, pinned). The
  0.25 mm level still cannot run on the Mac: one solve peaks at 15.9 GB on a 16 GB machine.
- **Fact: a second thread per solve helps a little.** With two threads each (8 threads on 8 vCPU), the four 0.25 mm
  solves took 0.899-0.909 of their phase-B wall time at 1.48 cores each (35 % more CPU), with the same L and iterations.
  On a VM billed by the hour that is about 10 % cheaper per solve, so E008's run plan uses four solves at once with
  two threads each (`OPENBLAS_NUM_THREADS = OMP_NUM_THREADS = MKL_NUM_THREADS = MF_L2_FFT_WORKERS = 2`, `MF_L2_THREADS = 1`).

## 4. Consequence for E008 (inference; T0262 owns the plan)
- Per reference about 36 solves at 0.25 mm (reconstruction, its 0.25 mm snapping variant, twin, 16-candidate shortlist,
  degraded copy D, the control's 16-candidate shortlist) and band solves (0.5 mm, 5/3/3 and 20/12/12 layers, 12-per-ring
  wires) on about 7 layouts. From P3's CPU-s, one layout's four band solves cost about 1.1 fine solves.
- Two public references: about 72 + 16 = 88 fine-solve equivalents. At 4 at once, two threads each, 5,700-5,900 s each:
  about 35-36 h. Thermal (O007: 0.35-0.85 h per layout, 10-42 GB at level 2; about 12 layouts per reference) and the AlN
  spot check add an estimated 5-12 h when interleaved. Total about 40-48 h on one regular 8-vCPU, 80 GB N2D, about
  $24-29 at $0.612/h.
- At P3's configuration the same work would have needed about 1,500 CPU-hours (O003's budget: 320).
- The registered run goes on a regular VM: a preempted registered run is not resumed (`scripts/burst_gcp.sh`).

## 5. What would change these conclusions
- References much larger than Case 4 (80 x 110 mm baseplate): memory and time scale with the unknowns (about 4.1 M at
  0.25 mm here); at more than about 19 GB per solve, only three fit in 80 GB.
- A different VM CPU platform: N2D custom shapes run on AMD Milan or Rome; Rome would be slower per core.
- Thermal solves larger than O007's measured 10-42 GB at level 2 would reduce how many EM solves can run beside them.
