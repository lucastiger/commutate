# Thermal model of a Layout (L2 reference definition)

Status: definition, T0148 · Governs: the in-house finite-volume solver (D0006, task n3) and the independent
scikit-fem cross-check (task n5). Both implement **this document independently**; neither implements the other.
Anything the two must agree on is written here; anything left to a solver (grid, linear solver, reconstruction of
surface values) must not change the continuum problem below. SI units and float64 throughout; temperatures in kelvin.

## 1. Inputs

* A `Layout` (`moduleforge.geometry.layout`) with its `LayerStack` (`moduleforge.geometry.stack`). Coordinates:
  x–y is the substrate plane; `z = 0` is the **bottom of the baseplate**; `stack.z_bottom(name)` / `stack.z_top(name)`
  give the substrate layer interfaces (baseplate, solder, backside_cu, ceramic, top_cu, bottom-up).
* Scalars supplied by the experiment, never defaulted by the model: the heat-transfer coefficient `h` [W/(m² K)]
  (uniform), the coolant temperature `T_c` [K], and the power `P_i` [W] of each die `i` (total dissipated in the die).
* Materials: `Layer.material` and `Layer.k` (conductivity at `T_REF` = 300 K). `Layer.k_at(T)` is the temperature law
  (cited in `stack.py`; valid 273.15–523.15 K, a `ValueError` outside). Materials are isotropic. For a constant-k run
  `k = Layer.k` is used (`k_at(T_REF)`).

## 2. Regions (the solid domain Ω)

Ω is the union of the following sets; each is an exact rectilinear set built from the layout's float coordinates
(no snapping, no fillets, no meniscus). Every point of Ω belongs to exactly one region; interfaces between regions
are **perfect contact** (continuous temperature and normal flux, no interface resistance).

| # | region | x–y footprint | z range | material (from `LayerStack`) |
|---|---|---|---|---|
| 1 | baseplate | `baseplate_outline` (includes the overhang outside the substrate outline) | `z_bottom(baseplate)`…`z_top(baseplate)` | `layer("baseplate")` (Cu) |
| 2 | solder | the backside-Cu footprint (below) | `z_bottom(solder)`…`z_top(solder)` | `layer("solder")` (SAC305) |
| 3 | backside Cu | `outline.buffer(-backside_inset, join_style="mitre")` | `z_bottom(backside_cu)`…`z_top(backside_cu)` | `layer("backside_cu")` (Cu) |
| 4 | ceramic | `outline` (the full substrate) | `z_bottom(ceramic)`…`z_top(ceramic)` | `layer("ceramic")` (Al2O3 or Si3N4) |
| 5 | top-Cu traces | union of all `Trace.polygon` (all nets alike; the net label is irrelevant thermally) | `z_bottom(top_cu)`…`z_top(top_cu)` | `layer("top_cu")` (Cu) |
| 6 | die attach, one per die | the die footprint `Die.bounds` = `box(cx ± w/2, cy ± h/2)` | `z_top(top_cu)` … `+ Die.attach_thickness` | `stack.die_attach` (SAC305) |
| 7 | die, one per die | the die footprint `Die.bounds` | die-attach top … `+ Die.thickness` | `stack.die` (4H-SiC) |

Notes:

* **Gaps are void.** Everything in the bounding box that is not in a region above — the gaps between traces (the
  ceramic's top face there), the ceramic outside the traces, the baseplate overhang's top face, the space beside and
  above the dies, the margin between the backside-Cu inset and the substrate edge (below the ceramic, above the
  baseplate and solder) — is void. Void is not meshed and carries **adiabatic faces** (section 4). Air, gel, housing,
  terminals, bond wires, die metallisation/pads and solder fillets are **not modelled** (conservative: they only
  add paths for heat).
* **One source of truth for thickness.** The per-die thicknesses `Die.thickness` and `Die.attach_thickness` are the
  geometry used here (and by the EM model for the die-short height). They default to `stack.die.thickness` and
  `stack.die_attach.thickness` (constants `DIE_THICKNESS` = 180 µm, `DIE_ATTACH_THICKNESS` = 50 µm in `stack.py`), and
  the generator never overrides them; the materials come from `stack.die` and `stack.die_attach`. A layout whose
  dies disagree with the stack's thicknesses is allowed, and the dies' values rule.
* **Containment (invalid input otherwise → the solver raises):** the backside-Cu footprint lies in the ceramic
  footprint, `outline` lies in `baseplate_outline`, every trace lies in `outline`, and every die footprint lies in
  the trace union (the attach is fully supported). Die footprints are disjoint.
* `Die.pads` (source and gate rectangles) do not enter the thermal model.

## 3. Governing equation and heat input

Steady state, no volumetric source:

    div( k(x, T) grad T ) = 0   in Ω,   k(x, T) = k_region(T)   (piecewise constant in x)

* **k(T):** `k_region(T) = Layer.k_at(T)` of the region's layer (section 2), solved by Picard iteration (lagging k at
  the previous iterate) to convergence; with constant k the problem is linear. The Picard fixed point is the
  continuum solution being defined.
* **Heat input:** a uniform flux `q_i = P_i / (w_i h_i)` [W/m²] over the **entire top face of die `i`** (the plane
  `z = z_top(die i)` over `Die.bounds`; not just the source pad), directed into the die: `-k ∂T/∂n = -q_i` with `n`
  the outward normal (+z). The total heat injected is `Σ P_i`. No heat is generated in the die volume.

## 4. Boundary conditions

* **Baseplate bottom** (`z = 0`, footprint `baseplate_outline`, the whole face): convective sink, uniform `h`, to the
  coolant: `-k ∂T/∂n = k ∂T/∂z = h (T − T_c)` with outward normal `n = −z` (z points up from the baseplate bottom),
  i.e. the heat flux leaving is `h (T − T_c)`; with heat entering at the top, `∂T/∂z > 0` there.
* **Every other face is adiabatic**: `∂T/∂n = 0`. That is the baseplate side faces and its top face outside the
  solder footprint, the side faces of solder, backside Cu and ceramic, the ceramic's top face in the gaps, the side
  and top faces of the top Cu, the side faces of the die attach and die, and the die top face (apart from the flux of
  section 3 there, which replaces the adiabatic condition on it). The faces facing a void are adiabatic as well.
* **Energy balance** (a required self-check, tolerance fixed by the experiment, not here):
  `∫ h (T − T_c) dA over the baseplate bottom = Σ P_i`.

## 5. Outputs (all in kelvin, as absolute temperatures; rises are `T − T_c`)

For die `i`, with `S_i` the die top face (`z = z_top(die i)`, `Die.bounds`):

* `Tj_max_i = max_{x in S_i} T(x)` — the maximum of the **continuous die-top surface temperature**, over the
  face including its edges (not a cell-centre or die-centroid value; a cell-centred scheme must reconstruct the
  surface field, and the nodal FEM reads it directly; both converge to this maximum).
* `Tj_mean_i = (1/|S_i|) ∫_{S_i} T dA` — the **area mean** over the die top face.
* Layout-level: `Tj max = max_i Tj_max_i` ("Tj max" of the module); `Tj mean = (1/N) Σ_i Tj_mean_i`; the **inter-die
  spread** `spread = max_i Tj_max_i − min_i Tj_max_i` (and likewise `spread_mean` for the means). Dies of both switches are
  included; a restriction to a switch must be stated by the experiment.
* Diagnostics: the energy-balance residual, the solver's discretisation error estimate (order-capped GCI over three
  grids, section 6), and the Picard residual.

## 6. Laterally uniform box-stack ("flux-channel") mode

The analytic reference cases use a simplified problem that is a special case of the same equations; both solvers
must provide it, with the same code path as the layout mode but a different geometry description:

* A rectangle `[0, a] × [0, b]` and a bottom-up list of layers `(t_j, k_j(T))`, **every layer spanning the full
  rectangle** (no patterning, no overhang, no void) with perfect interfaces.
* **Adiabatic side walls** (`x = 0, a` and `y = 0, b`) and an adiabatic top face except under the sources.
* Convective bottom: uniform `h`, coolant `T_c`, over the whole bottom face (`h → ∞` is not used; it is a finite `h`).
* Sources: rectangles `[x0, x1] × [y0, y1]` on the top face of the top layer with uniform flux `q = P/area` each,
  superposable (linear case).

Uses: (a) the single- and two-layer rectangular flux channels of Muzychka, Culham & Yovanovich (J. Electron.
Packag. 125(2):178–185, 2003: separation of variables, adiabatic sides, uniform-flux sources, convective sink) and
the 1D series resistance `R = Σ t_j/(k_j A) + 1/(h A)` when the source covers the whole top face; (b) the N-layer
Fourier series for the default stack: the seven layers of section 2 stacked as laterally uniform layers — baseplate,
solder, backside Cu, ceramic, top Cu, die attach, die — with die-sized sources of power `P_i` on the die layer's top
face; (c) manufactured solutions, for which a body-force term is added by the experiment, outside this definition.
The box-stack mode is a verification device only: the production problem is always sections 2–5.

## 7. What is deliberately outside this definition

Transient conduction; convection inside the cold plate (a uniform `h` stands for it); radiation; contact or
interface resistances; temperature-dependent `h`; anisotropy (e.g. of the DBC); heat generation in the substrate
(conduction losses in the copper); bond-wire and terminal conduction; solder voids and fillets.

## 8. Grid rule and grid-convergence evidence (T0150, revised by T0170)

The rule is frozen in `solvers/thermal_layout.py` (module docstring): mandatory grid lines at every geometry edge and layer
interface; level-0 bulk lateral cells `h0 = min(LAT_FRAC f_min, 1 mm)` (1 mm on the generator's 0.5 mm design grid; 4x
larger over the baseplate overhang), 2 z-cells per layer, **geometric edge cells at every die edge** (first cell
`2 t_min` = 100 um, growth 1.5, up to the bulk size); level `l` bisects every level-0 cell `l` times; the three GCI
levels are always 0, 1, 2 (`LEVEL0 = 0`, no per-case knob). GCI: O006's A4 rule (D0012; D0013 and its addenda 1 and
2), a conservative order-capped three-grid index. With `d1 = f1 - f0`, `d2 = f2 - f1` (levels 0, 1, 2), each set to 0 when
its magnitude is below 1e-3 K (ten times the 1e-4 K Picard tolerance, so iteration noise cannot pick the branch), and
`rho = d2/d1`: `d1 = d2 = 0` gives 0; `|rho| >= 1` or `d1 = 0 < |d2|` (divergent or stagnant) gives `+inf`;
`-1 < rho < 0` (oscillatory) gives `3 max(|d1|, |d2|)`; `0 <= rho < 1/4` (observed order above 2) gives
`1.25 max(|d2|, |d1|/4)`; `1/4 <= rho < 1` gives `1.25 |d2| / (2^p - 1)` with `p = min(log2(1/rho), 1)`. The safety factors
1.25 and 3 and the form are Roache (1998, ch. 5); the order cap, the branches and the floor are O006's. `meta['solver_tol']`
and the scikit-fem cross-check report exactly this value (`gci_three_grid`; tested equal to `mfos.metrics.gci_capped` with
`floor = 1e-3`). The earlier `Fs` = 1.25 / 3 rule with order cap 2 is superseded (non-conservative, T0181), as is the first
A4 text without the floor and with factor 1.25 on oscillatory sequences (D0013 addendum 2). The committed benchmark JSONs
keep the values recorded under the rule of their time.

**Why the edge cells.** Uniform meshes converged at `p_obs` about 1.1-1.7 on the layouts. The die-attach (k = 58) /
copper (k = 385) wedge at the die footprint edge has a singular exponent `lambda` = 0.83 (root of
`k1 tan(lambda pi/2) + k2 tan(lambda pi) = 0`; attach wedge 90 deg, copper wedge 180 deg), so `T ~ r^lambda` and a quasi-uniform
mesh converges at about `2 lambda` = 1.7 with a large constant. Edge cells cut the level-0 error of the die mean from about 2 K to
about 0.5 K. Removing patterned copper or the overhang from the layout (material map edited, same grids) did not change the
convergence ratios, which localises the slow part at the dies, not at the substrate.

**Tried and not adopted** (dev layout `side_by_side`, 2 dies per switch, seed 7, never the A3 seed; max GCI over the die
values, level 2 cells in brackets): frozen T0150 rule 0.29 K (1.8 M); z-cells 4 everywhere 0.28 K (3.6 M); 6 z-cells in layers
under 0.2 mm 0.29 K (2.6 M); lateral geometric grading 1.5 / 2 / 3 of every interval 0.21 / 0.18 / 0.15 K (1.8 M) but tj_max
worse at grade 3 (0.29 K); far factor 1 0.28 K; grading toward trace edges as well (12 M cells for the u-shaped layout,
unaffordable). Extra z-cells and z grading changed no value by more than 0.02 K.
Adopted rule on seed 7: 0.127 K (4.6 M cells); `u_shaped` 2 dies, seed 5: 0.179 K (4.5 M); `side_by_side` 6 dies, seed 11 (50 W per
die, 126 K rise): 0.405 K (7.2 M).

**GCI is conservative on analytic cases.** `solvers/thermal_series.py` is an independent N-layer Fourier-series solution of
section 6 (transfer matrix per mode, Carslaw and Jaeger 1959, Muzychka et al. 2003); `tests/unit/solvers/test_thermal_layout.py`
compares, on three partial-source boxes on the seven-layer stack (centred die, die near a wall, two unequal dies), the true
error of the finest level with the GCI of levels 0-2 for every source mean and centroid, and requires GCI >= |error| in each
(errors 0.001-0.0045 K, GCI 0.0017-0.0095 K, the GCI exceeding the error by 1.1-5x). On the frozen T0150 rule
the same kind of check on a 30 x 30 mm box with a 6 mm die was also conservative (centroid error 0.31 K, GCI 0.76 K) but
useless, since h0 = 6 mm put one cell across the die; `H0_MAX` removes that. For the layouts the "truth" is unknown; the Richardson extrapolation at `p_obs` about 1.5 puts the
level-2 error at about half of the level 1-2 change, so GCI (>= that change times 0.6-1) is conservative there too.

**A3 layouts, rule as final** (`benchmarks/results/thermal_l2_convergence.json`, run once after the rule was fixed):

| layout | cells L0 / L1 / L2 | peak RSS L2 | max GCI over all reported values |
|---|---|---|---|
| side_by_side, 6 dies per switch | 113 k / 0.91 M / 7.26 M | 6.4 GB | 0.168 K (tj_mean of one die); tj_max 0.092 |
| u_shaped, 2 dies per switch | 70 k / 0.56 M / 4.48 M | 6.2 GB | 0.334 K (tj_max of one die); spread_max 0.118 |

The T0150 rule gave 0.448 and 0.668 K. **The A4 limit of 0.025 K is not reached** and, with the observed order of 1.2-1.5 at
the finest levels, is not reachable at an affordable size: a factor 7-13 in the level 1-2 change needs 2-3.5 more bisections,
i.e. 460 M-5 G cells (70-700 GB of RAM), against 4.5-7.3 M cells here. The 6-die A3 layout needs 7.3 M cells at level 2 (6.4 GB RSS,
88 s on this Mac); a 16 GB machine is enough, the 5 M-cell budget is exceeded. The remaining slow component was not localised
further (die-edge cells, z-refinement and substrate features were excluded; the u-shaped tj_max still converges at
`p_obs` about 1); a different discretisation near the die corners (local mesh refinement with hanging nodes, or a
higher-order scheme) is the open option, not a finer global rule.

## 9. scikit-fem reference: element order and manufactured data (T0205)

`solvers/thermal_fem.py` implements sections 2-6 with hexahedral Galerkin elements of a chosen order,
`GridRule.element_order` (default 1; `solve_box_stack(element_order=...)` for the box mode).

* **Order 1**: trilinear `ElementHex1`, 2x2x2 Gauss points. Results are those of the earlier trilinear-only version
  (same `tj_max`/`tj_mean` to 1e-12 K on the 416 k-DOF smoke level of `benchmarks/thermal_fem_convergence.py`).
* **Order 2**: triquadratic `ElementHex2` (27 nodes), 3x3x3 Gauss points, on the same conforming mesh (same lines, same
  void rule). On axis-aligned boxes the map is affine and diagonal, so for constant `k` per element the stiffness
  integrand has degree 2(p-1) along the differentiated direction and 2p along the other two, at most 4 for Q2, and the
  Robin face mass has degree 4 per direction; a 3-point Gauss rule is exact to degree 5, so both are integrated exactly
  (Q1: degree 2 against the 2-point rule's 3). With `k(T)` the rule is the definition of the lagged-`k` Picard scheme.
  The stiffness is assembled in element chunks and summed by a binary tree, so the peak memory is the CSR matrix, the AMG
  hierarchy and one chunk of basis tables. Picard (stop at `max |dT| < 1e-4 K`), AMG-preconditioned CG (relative residual
  1e-11, true residual checked at 1e-8) and the solve for `theta = T - T_c` are unchanged.
* **Linear solver for Q2**: smoothed aggregation applied to the Q2 matrix directly coarsens far too aggressively (each Q2
  dof couples strongly to 125 others; operator complexity 1.005) and stalled at `h = 50 W/(m2 K)`. The Q2 preconditioner
  is a p-multigrid V-cycle: symmetric Gauss-Seidel on Q2, the exact Q1-to-Q2 interpolation on the same mesh as the first
  prolongation, smoothed aggregation on the Galerkin Q1 matrix below it (Ronquist & Patera, J. Sci. Comput. 2(4):389,
  1987). The constant mode is deflated (`x = c 1 + y`, `c = 1^T b / 1^T A 1`), because for a weak sink the rise is a
  large uniform part plus a small variation and the attainable residual eps |A| |x| / |b| would otherwise exceed 1e-11
  (1.5e-10 for a 48 K rise with 0.6 K of variation). Order 1 keeps plain smoothed aggregation.
* **Surface quantities** are assembled with scikit-fem facet bases (exact tensor rules): the Robin face mass, the uniform
  die flux `P_i/A_i`, and `tj_mean` = the exact Galerkin integral of `T` over the die top face divided by its area.
  `tj_max` is the maximum over exactly the nodes of that face (the dofs of its faces; for Q2 these include the edge
  midpoints and the face centres), and `point_values(result, pts)` evaluates the FE field at arbitrary points. Every face
  integral is restricted to the dofs of its faces: the facet quadrature points are mapped back to the reference cell by an
  inverse (Newton) map and land about 1e-16 off the face, which gives basis functions that vanish on the face values of
  about 1e-15 (25 to 550 such nodes per die face). Without the restriction those nodes entered `tj_max` (a 0.02 K bias on
  an unpowered die next to a 60 W die; T0205 review).
* **Manufactured data** (optional, for the O006 reference cases; defaults `None` leave the problem of section 3-4
  unchanged): `source(x, y, z)` [W/m3] over the volume; `flux(x, y, z, axis, sign)` [W/m2], heat into the domain, on every
  exterior and void-bounding face except the Robin face `z = 0` (the callable is also asked for die top faces, additive to
  the die flux); `T_inf(x, y)` [K] in place of the scalar coolant temperature in `h (T - T_inf)` (`T_c` stays the reference
  of the solved rise). Quadrature of the data: 4x4x4 Gauss points per cell and 4x4 per face (exact to degree 7 per
  direction). `meta` records `q_in_die_W`, `q_in_volume_W`, `q_in_boundary_W`, their sum `q_in_W`, and `q_out_W`
  = `int h (T - T_inf) dS`; `energy_balance` is `|q_out_W / q_in_W - 1|` against the *assembled* `Q_in` (exact up to the
  linear-solver residual, since constants lie in both spaces). It is a check of the linear solve and of the load
  bookkeeping only: it is zero for any data, so it cannot detect a wrong data quadrature, face selection or flux sign.
  Those are checked against independently integrated `Q_in` (tests) and O006's frozen `Q_out`. The interface and the sign
  convention follow `MMSCase` of `experiments/runners/e006_mms.py`.
* **Memory per DOF** (measured, whole-process peak RSS, k(T), `solve_layout` on the side_by_side/6 generator layout of
  the benchmark): Q2 8.1 kB at 57 k DOF, 4.5 kB at 416 k (1.9 GB, 45 s), 4.8 kB at 719 k (3.5 GB, 75 s); attempt 1 measured
  9.9 kB at 60 k on a box stack. Q1 at 416 k: 4.4 kB chunked (34 s) against 7.6 kB (18 s) for the earlier version that kept
  one basis of all elements (chunking trades 1.8 times the wall time for 42 % less memory). `BYTES_PER_DOF_BY_ORDER` =
  {1: 7.7 kB (D0006 bound), 2: 10 kB (upper bound of the Q2 figures)}; `max_dofs(budget, element_order=)` and
  `estimate_dofs` (the Q2 count includes edge, face and cell dofs) account for the order.
* **Verification** (`tests/unit/solvers/test_thermal_fem_assembly.py`): the two-layer series-resistance column and a
  manufactured quadratic field are reproduced by Q2 to the solver tolerance; for `k = k0 (1 + beta (T - T0))` against
  the Kirchhoff closed form the RMS error of the field converges at order 2 (Q1) and 3 (Q2), the through-thickness mean at
  2 and 4 (end-node values are exact in 1D for both orders); a two-region case with matched interface flux closes the
  energy balance against the exactly integrated source and flux to 1e-9; O006's manufactured case closes the balance to
  1e-6 and agrees with the frozen `Q_out` integral to 1e-6, with the error at the frozen points falling from level 0 to 1 at
  observed order >= 1.5 (measured 3.6 for Q1, 4.2 for Q2; the nodal maximum of the die is not the field maximum, so the
  die maximum is evaluated at the frozen location). Regression tests: `tj_max` equals the maximum over the face nodes
  selected by their coordinates on a layout where the node layer below an unpowered die is hotter than its face; at
  `h` = 500, 50 and 5 W/(m2 K) both orders converge and the spreading part of the die rise, `T - T_c - P/(h A_b)`,
  changes linearly in `h` (small-Biot limit); the Q1-to-Q2 prolongation reproduces trilinear fields exactly.

## 10. scikit-fem reference: grid rule with an absolute dz bound, mandatory lines and node-only values (T0206)

Implemented in `src/moduleforge/solvers/thermal_fem.py` (O007; from diagnosis T0198 and `project/memory/lessons.md`).

**Absolute through-thickness bound.** `GridRule.dz_max` [m] (default None: the per-layer counts of section 8's rule, unchanged).
When set, every z interval of thickness `t` (each stack layer, the die attach, the die; an interval cut by a mandatory z line is
bounded per piece) gets `max(nz_of(layer), ceil(t / dz_max))` cells at level 0 and `2**level` times as many at level `l`, so the
level-0 cell is at most `dz_max` thick and a count set by the bound is not capped by a fixed count per layer. All three
directions are refined, with the constant ratio `r = 2` (every line of level `l` is a line of level `l+1` and every cell
bisects), so `zrefine=False` together with `dz_max` is rejected. The rule is the same in layout mode (`solve_layout`) and in
box-stack mode (`solve_box_stack`); the latter takes the same `GridRule` (`h0`, `near_margin`, `min_cells`, `dz_max`,
`element_order`) through the same line builder and `_solve_grid` (`rule=`; the legacy `h0=` / `element_order=` keywords still
work). In box-stack mode a layer's level-0 count is `BoxLayer.n` (`GridRule.nz` is not used). The DOF count grows by about 8
per level (tested 8 +/- 15 % for Q1 and Q2).

**Mandatory grid lines.** `extra_lines=(xs, ys, zs)` [m] (any entry may be None) are merged into the level-0 line set before
subdivision, so a point on them is a node at every level; lines outside the domain are rejected. Level-0 lateral intervals
have an even cell count, so a line is a node at all levels also under Q2 (where, in addition, interval midpoints are mid-edge
DOFs). Box-stack mode always adds each source's centroid lines. The runner (E009) passes the frozen references' maximum
locations and the manufactured case's frozen points: they are fixed by the references, never by a solver result.

**Node-only point values.** `node_value(res, x, y, z=None)` [K] returns T at the DOF at that point (`z` defaults to the top
face; Q2 includes edge, face and cell mid-nodes) within 1e-9 m and raises `ValueError` otherwise: no interpolation.
`node_stencil(res, x, y, z=None)` returns, per axis, the index of the grid line through the point with the neighbouring line
coordinates (`index` None and the enclosing lines for a Q2 mid-node), so a runner can show per level that the point is a
node. `top_value` (bilinear, vertices only) is not for reported values.

**Per-die outputs.** `tj_max[i]` is the maximum over the DOF locations of die `i`'s top face and `meta['tj_max_xyz'][i]` its
coordinates [m] (the first such DOF on an exact tie); `tj_mean[i]` stays the Galerkin area integral. `meta` also records
`n_dofs`, `n_elements`, `element_order`, `level` (set by the solve functions), the per-axis line arrays `meta['lines']` and
the counts `meta['n_lines']`, so a runner can check bisection and DOF growth.
