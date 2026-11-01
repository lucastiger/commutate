# D0006 — L2 thermal reference: in-house finite-volume conduction solver; scikit-fem FEM as cross-check
Date: <date of founder decision> · Status: proposed (draft by the founder session, 2026-10-31) · Decider: founder

<!-- Draft. Decision records are a protected path: if you accept it, copy this file to
     project/decisions/D0006-thermal-l2-reference.md, set Date and Status, edit as you see fit, and commit it. -->

## Context
O002 (A-T2: a fast L1 thermal model is faithful enough for Tj max and spread) needs an L2 thermal reference before it
can be drafted (thesis review `docs/reports/thesis-review-2026-10-31.md`, proposal 4). The audit
`project/memory/literature/thermal-l2-reference.md` compared scikit-fem, FEniCSx, MFEM/PyMFEM, SfePy, FiPy, deal.II,
Elmer, OpenFOAM and an in-house solver against the permissive-licence policy (`scripts/check_licenses.py`), Apple
Silicon installability, k(T) and transient support, and verifiability:
- FEniCSx: DOLFINx/UFL/FFCx are LGPL-3.0-or-later, and the conda-forge build links ParMETIS (non-profit use only,
  evaluation-only for companies) and GPL SuiteSparse through PETSc.
- Elmer, OpenFOAM, gmsh: GPL; usable only as separate executables under a decision record.
- MFEM (BSD-3), SfePy (BSD-3), deal.II (Apache-2.0 with LLVM exception): permissive, but higher integration cost; the
  PyMFEM arm64 wheel is serial without AMG.
- scikit-fem (BSD-3) with pyamg (MIT): installs as wheels; reproduced the four-source centroid temperatures of
  Muzychka, Culham & Yovanovich (2003) Case 2 to within 0.023 K in a scratch run (not admissible evidence), at about
  7.7 kB per DOF.
- ModuleForge layouts are rectilinear by construction (`geometry/layout.py`, `conductors.py`), so a non-uniform
  rectilinear grid with lines on every layer interface and every copper and die edge represents them exactly; the
  existing FD prototype (`benchmarks/infra/thermal_bench.py`, pyamg) solves 3 M unknowns in about 7 s at 2.5 GB on the
  M5, but on a uniform grid that is not converged.

## Decision
- **Primary L2:** an in-house finite-volume steady and transient conduction solver in `moduleforge.solvers`, on a
  non-uniform rectilinear grid conforming to every layer interface and every top-copper and die edge; numpy/scipy and
  pyamg only; convective (h) or fixed-temperature sink; Picard iteration for k(T); implicit time stepping. It reports
  per-die surface maximum, mean and the inter-die spread, an energy balance, and an honest discretization error bound
  from a three-grid Richardson study as `meta['solver_tol']` (the D0003 pattern).
- **Cross-check:** scikit-fem with trilinear hexahedra on the same tensor grid and pyamg, on a subset of cases, as an
  independently discretized comparison (the role FastHenry has for the EM L2).
- **Verification before any L1 comparison** (an E001-style experiment): the 1D series resistance; Muzychka, Culham &
  Yovanovich (2003) single and multi-source tables; the N-layer series of Bagnall, Muzychka & Wang (2014) for the
  surface field (per-die maximum and spread); the Kirchhoff transform (Bagnall et al. 2014) and manufactured solutions
  for k(T) and transient; energy balance; three-grid convergence.
- **Dependencies:** add `pyamg` (MIT) and `scikit-fem` (BSD-3) to the project; never install gmsh or pygmsh into the
  environment (GPL; the licence gate blocks them).
- Runs above about 5 M unknowns go to burst VMs (`docs/INFRASTRUCTURE.md`).

## Alternatives considered
- (a) FEniCSx as primary: mature, but LGPL core and ParMETIS/GPL transitive dependencies in the standard build; a
  clean build is a maintenance burden.
- (b) scikit-fem as primary: permissive and verified on one case, but about 9 times the memory per unknown of the FV
  prototype, so roughly 1–2 M DOF on the laptop.
- (c) PyMFEM: permissive, but the macOS wheel has no AMG; a parallel hypre build is untested on Apple Silicon.
- (d) Elmer or OpenFOAM as separate executables: GPL and source builds on macOS.

## Consequences
O002 can be drafted with this L2 as its reference and a verification experiment as its first required experiment
(the E001 pattern), with `code_must_match` tying O002's comparison to the verified L2 code. Open questions for the
O002 draft, from the audit: the pre-registered error budget for Tj max and spread; the L2 scope (bond wires, solder
fillets, TIM or uniform h); the k(T) data sources.
