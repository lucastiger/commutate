# Which permissively licensed solvers can serve as ModuleForge's L2 thermal reference, and which should be chosen?
Date: 2026-10-31 · Task: founder session (thesis review 2026-10-31) · Confidence: medium

Provenance: written by a general-purpose research agent launched from the founder session (scout subagents could
not run there: python3 3.10 made the guard fail closed). The founder session re-opened S16 (ParMETIS: "freely used for
educational and research purposes by non-profit institutions and US government agencies only") and S1 (scikit-fem:
"licensed under the 3-clause BSD license") and found them as stated; the other sources were not re-checked. Numbers
marked [S59] come from the agent's scratch runs outside the repository: they inform the decision and are not
admissible evidence.

## Answer (≤ 5 sentences)
First choice: an in-house finite-volume conduction solver on a non-uniform rectilinear grid with grid lines on every layer interface, die edge and top-copper edge (ModuleForge layouts are rectilinear by construction), built only on numpy/scipy (BSD-3) and pyamg (MIT), with a convective (h) or fixed-temperature sink boundary, Picard iteration for k(T) and implicit time stepping. It has no licence friction, and the existing prototype already solves 3.0 M unknowns in 7.0 s at 2.5 GB peak on the M5. Fallback and code-to-code cross-check: scikit-fem (BSD-3-Clause, pure Python, installs on Apple Silicon) with trilinear hexahedra on the same tensor grid plus pyamg. In a scratch run it reproduced the four-source centroid temperatures of Muzychka et al. (2003) to within 0.023 K, but it used about 7.7 kB per DOF, so roughly 1–2 M DOF is its ceiling on the laptop. Whichever is used must be verified against the 1D series resistance, the Muzychka–Culham–Yovanovich (2003) multi-source tables, the N-layer series of Bagnall–Muzychka–Wang (2014), which give the full surface field and so the per-die maximum and the inter-die spread, the Kirchhoff transform and manufactured solutions for k(T) and transient, an energy balance and a three-grid convergence study. FEniCSx is not recommended: DOLFINx, UFL and FFCx are LGPL-3.0-or-later, and its conda-forge build pulls in ParMETIS (non-profit use only, evaluation-only for companies) and GPL UMFPACK/SPQR through PETSc; MFEM, SfePy and deal.II are permissive but cost more to integrate, FiPy is memory-hungry, and Elmer, OpenFOAM and gmsh are GPL and usable only as separate executables under a founder decision.

## Sources
| id | citation | url | type (paper/doc/datasheet/news/filing/repo/licence) | accessed |
|---|---|---|---|---|
| S1 | scikit-fem README (licensing paragraph, benchmark table, changelog) | https://raw.githubusercontent.com/kinnala/scikit-fem/master/README.md | repo | 2026-10-31 |
| S2 | scikit-fem GitHub repository page (BSD-3-Clause; JOSS 5(52):2369, Gustafsson & McBain 2020, doi:10.21105/joss.02369, Crossref-checked) | https://github.com/kinnala/scikit-fem | repo | 2026-10-31 |
| S3 | scikit-fem docs, list of examples | https://scikit-fem.readthedocs.io/en/latest/listofexamples.html | doc | 2026-10-31 |
| S4 | scikit-fem docs, API (init_tensor, with_subdomains, with_boundaries) | https://scikit-fem.readthedocs.io/en/latest/api.html | doc | 2026-10-31 |
| S5 | PyPI JSON metadata: scikit-fem, pyamg, meshio, scipy, mfem, sfepy, FiPy, gmsh, pygmsh, netgen-mesher, ngsolve, fenics-ufl/-ffcx/-basix/-dolfinx, petsc, petsc4py, mpi4py | https://pypi.org/pypi/{name}/json | doc | 2026-10-31 |
| S6 | DOLFINx README (licence, installation) | https://github.com/FEniCS/dolfinx | repo | 2026-10-31 |
| S7 | DOLFINx COPYING.LESSER | https://raw.githubusercontent.com/FEniCS/dolfinx/main/COPYING.LESSER | licence | 2026-10-31 |
| S8 | DOLFINx releases | https://github.com/FEniCS/dolfinx/releases | repo | 2026-10-31 |
| S9 | UFL README, licence | https://github.com/FEniCS/ufl | repo | 2026-10-31 |
| S10 | FFCx README, licence | https://github.com/FEniCS/ffcx | repo | 2026-10-31 |
| S11 | Basix README, licence | https://github.com/FEniCS/basix | repo | 2026-10-31 |
| S12 | PETSc licence page | https://petsc.org/release/install/license/ | licence | 2026-10-31 |
| S13 | conda-forge package metadata (anaconda.org API): fenics-dolfinx, fenics-libdolfinx, fenics-ffcx, fenics-ufl, fenics-basix, petsc, parmetis, metis, libumfpack, libspqr, libcholmod, libklu, mumps-mpi, hypre, superlu_dist, scalapack, sfepy, mfem, dealii, openfoam, fipy, gmsh, scikit-fem, pyamg | https://api.anaconda.org/package/conda-forge/{name} | doc | 2026-10-31 |
| S14 | conda-forge petsc-feedstock recipe.yaml (host requirements) | https://github.com/conda-forge/petsc-feedstock/blob/main/recipe/recipe.yaml | repo | 2026-10-31 |
| S15 | conda-forge fenics-dolfinx-feedstock recipe.yaml | https://github.com/conda-forge/fenics-dolfinx-feedstock/blob/main/recipe/recipe.yaml | repo | 2026-10-31 |
| S16 | ParMETIS LICENSE | https://github.com/KarypisLab/ParMETIS/blob/main/LICENSE | licence | 2026-10-31 |
| S17 | J. S. Dokken, FEniCSx tutorial (index page) | https://jsdokken.com/dolfinx-tutorial/ | doc | 2026-10-31 |
| S18 | MFEM LICENSE | https://raw.githubusercontent.com/mfem/mfem/master/LICENSE | licence | 2026-10-31 |
| S19 | PyMFEM README | https://github.com/mfem/PyMFEM | repo | 2026-10-31 |
| S20 | PyMFEM INSTALL.md | https://raw.githubusercontent.com/mfem/PyMFEM/master/INSTALL.md | doc | 2026-10-31 |
| S21 | PyMFEM on PyPI (mfem 4.10.0.1, wheel list) | https://pypi.org/project/mfem/ | doc | 2026-10-31 |
| S22 | MFEM examples page (ex16, ex27) | https://mfem.org/examples/ | doc | 2026-10-31 |
| S23 | hypre COPYRIGHT | https://raw.githubusercontent.com/hypre-space/hypre/master/COPYRIGHT | licence | 2026-10-31 |
| S24 | SfePy LICENSE | https://raw.githubusercontent.com/sfepy/sfepy/master/LICENSE | licence | 2026-10-31 |
| S25 | SfePy installation docs | https://sfepy.org/doc-devel/installation.html | doc | 2026-10-31 |
| S26 | SfePy user's guide (solver list) | https://sfepy.org/doc-devel/users_guide.html | doc | 2026-10-31 |
| S27 | FiPy LICENSE.rst | https://raw.githubusercontent.com/usnistgov/fipy/master/LICENSE.rst | licence | 2026-10-31 |
| S28 | FiPy USAGE | https://pages.nist.gov/fipy/en/stable/USAGE.html | doc | 2026-10-31 |
| S29 | FiPy EFFICIENCY | https://pages.nist.gov/fipy/en/stable/EFFICIENCY.html | doc | 2026-10-31 |
| S30 | deal.II LICENSE.md at tag v9.8.0 | https://raw.githubusercontent.com/dealii/dealii/v9.8.0/LICENSE.md | licence | 2026-10-31 |
| S31 | deal.II releases (GitHub API) and README | https://api.github.com/repos/dealii/dealii/releases ; https://raw.githubusercontent.com/dealii/dealii/master/README.md | repo | 2026-10-31 |
| S32 | deal.II readme (supported platforms) | https://www.dealii.org/current/readme.html | doc | 2026-10-31 |
| S33 | Elmer LICENSE.md (devel branch) | https://github.com/ElmerCSC/elmerfem/blob/devel/LICENSE.md | licence | 2026-10-31 |
| S34 | Elmer licence policy | https://github.com/ElmerCSC/elmerfem/blob/devel/license_texts/ElmerLicensePolicy.md | licence | 2026-10-31 |
| S35 | Elmer HeatSolve.F90 and HeatSolveVec.F90 licence headers | https://github.com/ElmerCSC/elmerfem/tree/devel/fem/src/modules | repo | 2026-10-31 |
| S36 | Elmer repository page and releases API | https://github.com/ElmerCSC/elmerfem ; https://api.github.com/repos/ElmerCSC/elmerfem/releases | repo | 2026-10-31 |
| S37 | OpenFOAM licensing page | https://www.openfoam.com/documentation/licencing | licence | 2026-10-31 |
| S38 | OpenFOAM download page | https://www.openfoam.com/download | doc | 2026-10-31 |
| S39 | Gmsh LICENSE.txt | https://gmsh.info/LICENSE.txt | licence | 2026-10-31 |
| S40 | Homebrew formulae API (gmsh; no formula for deal.ii, dealii, elmer, openfoam) | https://formulae.brew.sh/api/formula/gmsh.json | doc | 2026-10-31 |
| S41 | PyAMG LICENSE.txt | https://raw.githubusercontent.com/pyamg/pyamg/main/LICENSE.txt | licence | 2026-10-31 |
| S42 | Bell, Olson, Schroder, Southworth, "PyAMG: Algebraic Multigrid Solvers in Python", JOSS 8(87):5495 (2023) | https://joss.theoj.org/papers/10.21105/joss.05495 | paper | 2026-10-31 |
| S43 | GitHub API repo metadata (pushed_at, stars, licence) for FEniCS/dolfinx, kinnala/scikit-fem, mfem/mfem, mfem/PyMFEM, sfepy/sfepy, usnistgov/fipy, dealii/dealii, ElmerCSC/elmerfem, pyamg/pyamg, OpenFOAM/OpenFOAM-dev | https://api.github.com/repos/{owner}/{repo} | repo | 2026-10-31 |
| S44 | Muzychka, Culham, Yovanovich, "Thermal spreading resistance of eccentric heat sources on rectangular flux channels", J. Electron. Packag. 125(2):178–185 (2003), doi:10.1115/1.1568125 (full text read) | https://uwaterloo.ca/microelectronics-heat-transfer-laboratory/sites/default/files/uploads/documents/spreading_resistance_3-mhtl03-1.pdf | paper | 2026-10-31 |
| S45 | Muzychka, Yovanovich, Culham, "Thermal spreading resistance in compound and orthotropic systems", J. Thermophys. Heat Transf. 18(1) (2004) (full text read) | https://uwaterloo.ca/microelectronics-heat-transfer-laboratory/sites/default/files/uploads/documents/spreading_resistance_3-mhtl04-27.pdf | paper | 2026-10-31 |
| S46 | Muzychka, Bagnall, Wang, "Thermal spreading resistance and heat source temperature in compound orthotropic systems with interfacial resistance", IEEE TCPMT 3(11):1826–1841 (2013), doi:10.1109/TCPMT.2013.2269273 (abstract via OpenAlex, metadata via Crossref) | https://api.openalex.org/works/https://doi.org/10.1109/TCPMT.2013.2269273 | paper | 2026-10-31 |
| S47 | Bagnall, Muzychka, Wang, "Analytical solution for temperature rise in complex multilayer structures with discrete heat sources", IEEE TCPMT 4(5):817–830 (2014), doi:10.1109/TCPMT.2014.2299766 (abstract only) | https://api.openalex.org/works/https://doi.org/10.1109/TCPMT.2014.2299766 | paper | 2026-10-31 |
| S48 | Bagnall, Muzychka, Wang, "Application of the Kirchhoff transform to thermal spreading problems with convection boundary conditions", IEEE TCPMT 4(3):408–420 (2014), doi:10.1109/TCPMT.2013.2292584 (abstract only) | https://api.openalex.org/works/https://doi.org/10.1109/TCPMT.2013.2292584 | paper | 2026-10-31 |
| S49 | Ellison, "Maximum thermal spreading resistance for rectangular sources and plates with nonunity aspect ratios", IEEE Trans. Compon. Packag. Technol. 26(2):439–454 (2003), doi:10.1109/TCAPT.2003.815088 (abstract only) | https://api.openalex.org/works/https://doi.org/10.1109/TCAPT.2003.815088 | paper | 2026-10-31 |
| S50 | Simons, "Simple formulas for estimating thermal spreading resistance", Electronics Cooling, May 2004 (Lee et al. 1995 model) | https://www.electronics-cooling.com/2004/05/simple-formulas-for-estimating-thermal-spreading-resistance/ | news | 2026-10-31 |
| S51 | Albers, "An exact recursion relation solution for the steady-state surface temperature of a general multilayer structure", IEEE Trans. CPMT-A 18(1):31–38 (1995), doi:10.1109/95.370732 (abstract via Semantic Scholar; CC0 Zenodo record) | https://zenodo.org/record/1262907 | paper | 2026-10-31 |
| S52 | Choudhury & Rogers, "Steady-state thermal modeling of a power module: an N-layer Fourier approach", IEEE TPEL 34(2):1500–1508 (2019), doi:10.1109/TPEL.2018.2828439 (abstract only) | https://api.openalex.org/works/https://doi.org/10.1109/TPEL.2018.2828439 | paper | 2026-10-31 |
| S53 | Choudhury & Rogers, "Transient thermal modeling of a power module: an N-layer Fourier approach", IEEE TPEL 35(10):10580–10591 (2020), doi:10.1109/TPEL.2020.2983248 (abstract only) | https://api.openalex.org/works/https://doi.org/10.1109/TPEL.2020.2983248 | paper | 2026-10-31 |
| S54 | Choudhury, "Thermal modelling of power semiconductor modules in power electronic applications", DPhil thesis, Univ. Oxford (2021), doi:10.5287/ora-rbwk0qqxk (record page) | https://ora.ox.ac.uk/objects/uuid:d7bb820b-8a3b-4c12-a8cc-5c8d635b6b74 | paper | 2026-10-31 |
| S55 | Salari & Knupp, "Code verification by the method of manufactured solutions", SAND2000-1444 (2000), doi:10.2172/759450 (record page) | https://www.osti.gov/biblio/759450 | doc | 2026-10-31 |
| S56 | ModuleForge `docs/INFRASTRUCTURE.md` §7.1 and `benchmarks/infra/thermal_bench.py` (internal) | repository | doc | 2026-10-31 |
| S57 | ModuleForge `src/moduleforge/geometry/layout.py`, `conductors.py`, `stack.py` (internal) | repository | repo | 2026-10-31 |
| S58 | ModuleForge `scripts/check_licenses.py` (internal) | repository | repo | 2026-10-31 |
| S59 | Scratch runs in the research session on Apple M5, 16 GB: `thermal_bench.py` re-run, scikit-fem check against S44 Case 2, inspection of mfem-4.10.0.1-cp312-macosx_14_0_arm64 wheel. Not admissible evidence; scratch files deleted after the session | local | doc | 2026-10-31 |

## Findings
**Project context**
- [S58] The licence gate fails (BLOCKED) on any distribution whose metadata contains "GPL" without "LGPL"/"LESSER", or contains "AFFERO". It reports (REVIEW) LGPL licences and empty licence metadata.
- [S57] Top-copper traces are "Rectilinear top-Cu polygon[s]", and `decompose_polygon` raises "polygon is not rectilinear". Conductors are "Axis-aligned top-Cu rectangle[s]". The stack, bottom-up, is baseplate, solder, backside_cu, ceramic, top_cu, with cited default conductivities (Cu ~385, Al2O3 24, Si3N4 90, SAC305 58 W/(m K)).
- (inference) A non-uniform tensor grid with a line at every layer interface and every rectangle edge represents this geometry exactly. That avoids staircase error and any unstructured mesher, gmsh included.
- [S56] The existing prototype uses 7-point finite differences with harmonic-mean conductivity, a cold-plate boundary with h = 5000 W/(m² K), and 400 W in four 5 × 5 mm dies on a 60 × 50 mm stack. The grid is uniform. It is solved by pyamg smoothed aggregation plus CG to tol 1e-8. Documented results on a 1-vCPU Xeon: 2.3 / 11.6 / 26 s at 0.29 / 1.44 / 3.0 M unknowns, and 2.1 GB at 3 M. The document's line "FEniCSx of similar size behaves comparably" is not marked as measured. Its local rule: "never run a 3D thermal mesh above ~5M unknowns locally".
- [S59] Re-run on the M5 (numpy 2.5.4, scipy 1.18.1, pyamg 5.4.1):
  - AMG setup plus solve: 0.7 / 3.1 / 7.0 s, with 19 / 16 / 16 iterations.
  - Q_out/Q_in = 1.0000; peak RSS 2,526 MB (≈ 0.84 kB per unknown).
  - Tmax − Tcool = 70.72 / 75.13 / 72.60 K. This does not converge monotonically, because the uniform grid resolves neither the 0.05–0.1 mm layers nor the die edges.
- (inference) The prototype is a good cost proxy but not a converged reference; the grid must follow the layers and edges. At ~0.84 kB per unknown, 1e7 unknowns would need ≈ 8–9 GB. That fits in 16 GB but breaks the 5 M local rule, so those runs belong on burst VMs.

**scikit-fem**
- Licence and release:
  - [S1] README: "The contents of `skfem/` and the PyPI package `scikit-fem` are licensed under the 3-clause BSD license". Some examples may carry other licences.
  - [S5] Version 12.0.2 (2026-06-05), a py3-none-any wheel, Python ≥ 3.10, minimal dependencies numpy and scipy. The PyPI classifier is "OSI Approved :: BSD License", so it passes the gate (inference from S58).
  - [S43] Repository last pushed 2026-10-31; 672 stars.
- [S1] README benchmark (Laplace, linear tetrahedra, MacBook Pro M2): assembly took 12.58563 s at 1,030,301 DOFs. The direct solver `scipy.sparse.linalg.spsolve` took 62.69 s at 64,000 DOFs and shows "nan" from 125,000 DOFs. 3D problems therefore need AMG-preconditioned CG.
- [S3, S4] Relevant examples and API:
  - ex9 is a 3D Poisson problem solved by PCG "with PyAMG or pyamgcl". ex17 is steady conduction with generation and a Robin condition. ex19 is the transient heat equation.
  - Newton's method appears only in non-thermal examples such as ex10, so a k(T) loop would be our own code.
  - `MeshHex1.init_tensor(x, y, z)` and `MeshTet1.init_tensor` build tensor-product meshes; `with_subdomains` and `with_boundaries` tag regions.
- [S59] Scratch check against S44 Case 2 (Q1 hexahedra, pyamg SA-CG, Tf = 25 °C assumed because Case 2 does not state it):
  - Grid h = 0.5 mm, aligned with the source edges: 214,221 DOFs.
  - Centroid temperatures 97.388 / 103.797 / 101.264 / 99.921 °C against the published 97.40 / 103.82 / 101.28 / 99.94 °C. Differences are −0.012 to −0.023 K, ≤ 0.03 % of the ~72–79 K rise.
  - Mean temperatures 96.848 / 102.332 / 100.107 / 99.073 °C against 96.85 / 102.33 / 100.10 / 99.07 °C (|Δ| ≤ 0.007 K).
  - Energy balance 1.000000; 13 CG iterations.
- [S59] scikit-fem memory:
  - With default quadrature: 3.72 GB at 214 k DOFs. The 1.66 M DOF run reached a 33 GB footprint (swapping) and was killed.
  - With `intorder=3`: 1.58 GB at 214 k DOFs and 5.45 GB at 707 k DOFs (≈ 7.7 kB per DOF, about 9 times the FD prototype). Assembly took 1.3 s and 4.3 s.
  - (inference) Without chunked assembly the local ceiling is about 1.5–2 M DOFs.

**FEniCSx (DOLFINx, UFL, FFCx, Basix, PETSc)**
- Licences:
  - [S6, S7] DOLFINx is LGPL "version 3 or later"; COPYING.LESSER is LGPL "Version 3, 29 June 2007".
  - [S5, S9, S10] UFL (2026.2.0, 2026-09-30) and FFCx (0.11.0, 2026-06-09) declare License-Expression LGPL-3.0-or-later, so the gate would REVIEW them.
  - [S5, S11] Basix is MIT, with wheels including macosx_11_0_arm64.
  - [S12] PETSc is 2-clause BSD; the licence "DOES NOT apply to any software that may be obtained via the –download-package option".
- Packaging:
  - [S8, S13] DOLFINx v0.11.0 was tagged 09 Jun; conda-forge 0.11.0 (first upload 2026-06-10) is LGPL-3.0-or-later on linux-64, linux-aarch64, osx-64, osx-arm64 and win-64.
  - [S5, S6] fenics-dolfinx is not on PyPI (JSON 404). Beta wheels of main are on Test PyPI (Python 3.12+, macOS 15+) and are "built without PETSc".
- Dependencies of the conda-forge build:
  - [S15] conda-forge fenics-libdolfinx run-requires parmetis on non-Windows and links petsc, parmetis, kahip, superlu_dist and scotch.
  - [S14] conda-forge PETSc links hypre, metis, parmetis, ptscotch, mumps-mpi, superlu_dist and SuiteSparse (libcholmod, libklu, libspqr, libumfpack).
  - [S13] conda-forge licences: parmetis "LicenseRef-ParMETIS"; libumfpack GPL-2.0-or-later; libspqr GPL-2.0-or-later; libcholmod "LGPL-2.1-or-later AND GPL-2.0-or-later AND Apache-2.0"; mumps-mpi CECILL-C; hypre and metis Apache-2.0.
- [S16] ParMETIS licence: "It can be freely used for educational and research purposes by non-profit institutions and US government agencies only. Other organizations are allowed to use ParMETIS only for evaluation purposes, and any further uses will require prior approval."
- (inference) A stock conda-forge FEniCSx install puts evaluation-only ParMETIS and GPL SuiteSparse code into the process. A clean stack needs a custom PETSc/DOLFINx build, and the LGPL core still needs founder review.
- [S17] The tutorial covers the transient heat equation (including "A known analytical solution"), nonlinear Poisson with custom Newton solvers, Robin conditions and material subdomains. It targets DOLFINx 0.11.0.post0. [S43] Repository pushed 2026-10-30.

**MFEM / PyMFEM**
- [S18] BSD 3-Clause, "Copyright (c) 2010-2026, Lawrence Livermore National Security, LLC".
- [S5, S21] mfem 4.10.0.1 (2026-10-27) declares License-Expression BSD-3-Clause, with wheels for macosx_14_0_arm64 and manylinux x86_64 on cp311–cp314. [S19] The README still says the binary install is "available only on linux platforms (Py38-312)", which is out of date.
- [S20] The default pip install is "a *serial* version"; `--with-parallel` "turns on building `metis` and `hypre`" from source.
- [S59] The arm64 wheel contains only `mfem/external/ser/lib/libmfem*.dylib`; `mfem/_par` holds SWIG `.i` sources and no compiled modules. (inference) There is no hypre BoomerAMG in the wheel, so the serial build has no AMG for 1e6+ DOF.
- [S23] hypre is "licensed under the Apache License, Version 2.0 … or the MIT license … at your option", relicensed from LGPL-2.1. [S13] METIS is Apache-2.0. (inference) A parallel MFEM + hypre + METIS stack is fully permissive but needs an MPI source build; this was not tested on macOS.
- [S22] ex16 "solves a simple 2D/3D time dependent nonlinear heat conduction problem" with du/dt = ∇·(κ + αu)∇u, implicit and explicit time integration and a Picard step. ex27 has a Robin condition. [S13] conda-forge has mfem 4.8 (osx-arm64). [S43] Repository pushed 2026-11-01.

**SfePy**
- [S24] BSD 3-clause text, "Copyright (c) 2007 - 2014 SfePy Developers".
- [S5, S25] 2026.3 (2026-09-29) is a source distribution only on PyPI; building needs a C compiler, Cython and CMake. [S13] conda-forge has 2026.3 for osx-arm64. [S25] The docs list only "Intel-based macOS".
- [S26] Solvers include `ls.pyamg`, `ls.pyamg_krylov`, `ls.petsc`, `ls.mumps`, `nls.newton`, `nls.petsc`, `ts.simple` and `ts.adaptive`, so nonlinear transient conduction is supported natively.
- (inference, S13 and S25) The optional scikit-umfpack would bring in GPL-2.0-or-later UMFPACK and should be avoided.

**FiPy**
- [S27] NIST terms: "not subject to copyright protection in the United States", "may be subject to foreign copyright", with permission "to use, copy, modify, create derivative works, and distribute" provided the notice is kept. [S13] conda-forge labels it "NIST-PD".
- [S5] 4.0.3 (2026-06-18) is a pure-Python wheel with no licence field or classifier. (inference, S58) The gate would report "REVIEW … unknown".
- [S28] Supported solver suites: "petsc", "pyamgx", "scipy", "trilinos". It provides Gmsh2D/Gmsh3D wrappers and warns that accuracy "can be compromised with highly non-orthogonal" meshes.
- [S29] It is "around 17 times slower than the FORTRAN code" (about 9 times with `--inline`) on a 2D benchmark of up to 102,400 cells, and "each cell requires approximately 1.4 kilobytes of memory" (a "very rough guide"). (inference) That is roughly 14 GB at 1e7 cells.

**deal.II**
- [S30] The v9.8.0 LICENSE.md says it is licensed "under the terms of the Apache License 2.0 with LLVM Exception, and separately under … the GNU Lesser General Public License v2.1 or later … (dual licensed)". Files under bundled/, examples/ and tests/ may differ.
- [S31] v9.8.0 was published 2026-08-09. It is a C++/CMake source build or a Docker image.
- [S32] It is tested with "Clang (… both Intel- and ARM-based Apple Mac systems via Xcode)". [S40] There is no Homebrew formula. [S13] conda-forge has only 9.3.2, for linux-64 and osx-64.
- (inference) The licence option is permissive, but there is no Python workflow, so integration is costly.

**Elmer**
- [S33] The suite is "GPL … either version 2 … or … any later version".
- [S34] Per the policy, LGPL covers "the ElmerSolver main library (libelmersolver, codewise /fem/src/*.F90), as well as the libraries matc and fhutiter". "ElmerGUI, ElmerGrid, and most of the existing physical modules" are GPL. The policy text gives the versions as GPL "v. 2.1" and LGPL "v. 2.0", which looks reversed relative to the file headers.
- [S35] The HeatSolve.F90 and HeatSolveVec.F90 headers are LGPL "version 2.1 … or … any later version".
- [S36] Latest release is release-26.2.1 (2026-04-29). There is no conda-forge package [S13] and no Homebrew formula [S40]. macOS means compiling from source; Linux has a PPA and Docker.

**OpenFOAM**
- [S37] "OpenFOAM is distributed under the GPL v3 licence."
- [S38] v2606 was released 26/06/2026. Linux has packages; macOS uses Docker. [S13] conda-forge has openfoam 2412, linux-64 only, GPL-3.0-only.

**Meshing**
- [S39] Gmsh is GPL v2 or later, with an exception that permits combining it with Netgen, METIS, OpenCASCADE and ParaView.
- [S5] PyPI licence metadata:
  - gmsh 4.15.2: "GPLv2+", so BLOCKED by the gate (inference from S58).
  - pygmsh 7.1.17: GPLv3+, also BLOCKED.
  - netgen-mesher / ngsolve 6.2.2608: LGPL-2.1-only, so REVIEW.
  - meshio 5.3.5: MIT.
- [S40] Homebrew gmsh 4.15.2 has arm64 macOS bottles, so it could run as a separate executable.

**pyamg**
- [S41] "The MIT License (MIT)", "Copyright (c) 2008-2015 PyAMG Developers".
- [S5] 5.4.1 (2026-10-30) has macosx_11_0_arm64 wheels. [S42] JOSS 8(87):5495 (2023). [S43] Repository pushed 2026-10-31.

**Analytic and semi-analytic verification benchmarks**
- [S45] Eq. (4): R_1D = Σᵢ tᵢ/(kᵢ A) + 1/(hA), with R_T = R_1D + R_s. This is exact for a uniform heat flux covering the whole top face and tests the layer conductivities and the sink boundary.
- [S44] Muzychka, Culham and Yovanovich (2003):
  - Method: separation of variables for isotropic and compound (two-layer) rectangular flux channels, with adiabatic edges (eqs. 11–12), uniform flux inside each source and convection at the sink (eq. 9).
  - Multiple sources: "any number of discrete heat sources … using superposition" (eq. 37). It gives the surface field, the centroid temperature T̂ and the mean temperature T̄; 50 terms were used in each sum.
  - Case 1a: 300 × 300 × 10 mm plate, k = 10, h = 10, Tf = 25 °C; sources of 10 W and 15 W, each 25 × 25 mm. Centroid temperatures 84.97 / 108.43 °C, against 85.95 / 109.92 °C from Culham's least-squares generalized-Fourier method (≈ 1.6 % of the rise).
  - Case 1b: adds a 2 mm, k = 350 layer. Centroid temperatures 56.55 / 59.94 °C.
  - Case 2: 50 × 50 × 10 mm, k = 150, h = 400; four 10 × 10 mm sources of 10 / 25 / 20 / 15 W (Table 3). Results are in Table 4.
  - Case 3: five 5 W sources forming a cross. Maximum at the centre 80.61 °C; mean source temperature 78.87 °C.
- [S45] The 2004 review is "mainly concerned with … systems with one or two layers". It gives the orthotropic transformation k_eff = √(k_r k_z), t_eff = t/γ.
- [S46] Muzychka, Bagnall and Wang (2013): compound orthotropic systems with interfacial resistance and an arbitrarily placed source. Superposition gives multiple sources, and the paper reports "source mean and centroid temperatures" and an influence-coefficient method for many sources.
- [S47] Bagnall, Muzychka and Wang (2014): a closed-form temperature distribution for "rectangular isoflux heat sources, any number of layers of arbitrary thermal conductivity, and perfect interfacial contact or finite interfacial conductance", with convective conditions in the source and sink planes. Only the abstract was read; the full text is paywalled.
- [S48] Kirchhoff transform with convection at the sink, "accurate to within 1%". Earlier use was "restricted to temperature and heat flux boundary conditions".
- [S49] Ellison (2003): an "exact three-dimensional (3-D) solution" for a single plate, giving "maximum and source-averaged thermal spreading resistances" via a Biot number.
- [S50] The Lee et al. (1995) formulas, as reported by Simons (2004), approximate Tmax at the source centre. Against the exact TAMS series they err by −1.2 % to +3.9 % on R_tot and −2.1 % to +4.8 % on R_sp (10 × 10 mm source, 2.5 mm plate, k 25–400, h_eff 250–1000). That is screening accuracy, not verification accuracy.
- [S51] Albers (1995): an exact recursion "for any number of layers" giving the surface temperature, "identical with those presented by Kokkas and the TXYZ thermal code" for three layers.
- [S52, S53, S54] Choudhury and Rogers, N-layer Fourier models of power modules with an arbitrary number of sources:
  - Steady state: ≈ 0.27 % temperature error against FEM at die centres; agreement within 3.5 % against a commercial SiC module.
  - Transient: < 2 % against FEM; < 6 % against a thermal camera.
  - Thesis: ≈ 1.00 % maximum error (steady) and ≈ 15 % in the sub-transient region.
- [S55] The method of manufactured solutions "can identify any coding mistake that affects the order-of-accuracy".
- (inference) How the benchmarks cover Tj max and multiple sources:
  - S44, S46, S47, S51 and S52 give the full surface field, so the per-die maximum and the inter-die spread can be found by searching that field.
  - S44 and S46 tabulate centroid and mean temperatures; S49 gives the maximum for a single centred source. With several dies, the maximum may not sit at a die centroid.
  - Multiple sources are handled in S44, S46, S47, S52 and S53.
  - All of them assume laterally uniform layers across the whole footprint, adiabatic sides and a uniform h. Patterned copper, substrates smaller than the baseplate and k(T) in multilayer stacks therefore need MMS plus a code-to-code comparison (FV against FEM) and grid convergence.
  - The Kirchhoff transform (S48) only linearises single-material problems.
- The "Feng" multilayer series reference named in the brief could not be identified; S52 and S53 are the closest power-module N-layer equivalents.

## Relevance to ModuleForge
- Thermal L2 can follow the D0003 pattern. The main solver is the in-house FV on a grid that follows every layer and edge. scikit-fem acts as a third-party-assembled, independently discretized cross-check on a subset of cases, the role FastHenry has for EM.
- Both new dependencies (pyamg MIT, scikit-fem BSD-3) should pass `check_licenses.py`. Avoid installing gmsh or pygmsh into the environment; the gate would block them. A founder decision record is still needed to fix the choice before O002 is drafted, as the thesis review asks.
- INFRASTRUCTURE.md says L1 thermal will be a spectral/layered Green's-function model, which is the same mathematics as S44–S53. Those benchmarks verify L2 (and L1) on laterally uniform stacks. O002's L1-vs-L2 comparison must therefore focus on what the series cannot represent: patterned top copper, solder and ceramic footprints, k(T), and the spread across paralleled dies.
- L2 should report the per-die surface maximum taken from the field, not the centroid. A cell-centred FV needs a surface reconstruction for this; the nodal FEM cross-check gets it directly.
- An E001-style experiment for L2 is needed: analytic cases from S44/S45/S47, MMS for k(T) and transient, an energy balance, and Richardson three-grid error bounds reported as an honest `solver_tol`.

## Thesis impact: strengthens — weakly
A permissive, verifiable L2 thermal reference is feasible on the laptop. That removes the blocker the 2026-10-31 thesis review named for A-T2. Published N-layer Fourier models, the likely L1 family, match FEM at die centres to ≈ 0.27–1 % in steady state and < 2 % in transient (S52–S54). None of these sources tests patterned copper or inter-die Tj spread, which is what A-T2 actually claims.

## Open questions
- What error budget for L2 Tj max and Tj spread (K or %) will O002 pre-register, and on which outputs: per-die maximum, mean, spread?
- What is in scope for L2: bond wires, die metallization, solder voids or fillets, a TIM or cold plate versus a uniform h, and whether h is non-uniform?
- Which vendor or literature k(T) data will be used for SiC, Si, Si3N4/Al2O3, Cu and solder?
- Is an in-house primary L2 acceptable to the founder (as with D0003), or is a third-party code required for credibility against customers' Icepak (L3)?
- Full text of S47 (paywalled) is needed to implement the N-layer series; only the abstracts of S46–S49 and S52–S53 were read.
- Which "Feng" reference did the brief mean?
- PyMFEM's parallel hypre build on Apple Silicon is untested.
- How fine must the grid be in-plane and through-thickness for Tj-max convergence with 0.05–0.1 mm solder layers, and what transient time step is needed for Zth campaigns?
