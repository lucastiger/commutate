# O006 / E006 manufactured reference: 3D field with k(T) on the default DBC stack with patterned top copper
Date: 2026-11-01 · Task: T0153 · Confidence: high for the construction and the self-checks; medium for the F3
estimate (own coarse FV, see section 6)

Runner: `experiments/runners/e006_mms.py` (does not import the solver package or any FEM package). Frozen values:
`research/e006_refs/mms_values.json` (`sha256_payload` covers geometry, field parameters, BC conventions, field range,
k variation and the reported points; self-check results and the F3 estimate are diagnostics outside the hash).

## 1. Answer
You can build the case entirely inside the FV solver's contract (n2/n3 docstring): a per-cell volumetric source as a
callable, a prescribed inflow callable `flux(x, y, z, axis, sign)` on every exterior and void-bounding face, and Robin
at z = 0 with a scalar `h` and a callable `T_inf(x, y)`. Nothing had to be extended. The materials are the stack's own
`Layer` objects with their cited k(T) laws. The field ranges over 294.74–395.49 K (range 100.75 K, so the A1 scale is
100.75 K). In the ceramic, k varies by 32.3 % (k_max/k_min − 1). All gated self-checks pass. A constant-k solve at the
layer-mean temperatures moves the reported points by up to 2.51 K. That is 2.5× A1's 1.007 K and 50× A2's 0.05 K, so
F3's null `dT_const_k` should fail both.

## 2. Geometry (facts, from the runner; SI in the code, mm here)
The stack is `default_dbc_stack()` plus `die_attach` (SAC305, 50 µm) and `die` (4H-SiC, 180 µm). The interfaces are
z = 0, 3.00, 3.10, 3.40, 3.78, 4.08, 4.13, 4.31 mm.

| j | region | material, k(300 K) | footprint (mm) |
|---|---|---|---|
| 0 | baseplate | Cu, 385 | [0, 30] × [0, 24] (3 mm overhang past the ceramic) |
| 1 | solder | SAC305, 58 | [4, 26] × [4, 20] (= backside-Cu footprint) |
| 2 | backside Cu | Cu, 385 | [4, 26] × [4, 20] (ceramic outline inset by 1 mm) |
| 3 | ceramic | Al2O3, 24 | [3, 27] × [3, 21] |
| 4 | top Cu | Cu, 385 | island A [4.5, 16.5] × [4.5, 19.5]; island B, L-shaped: [18, 25.5] × [4.5, 10] ∪ [21.5, 25.5] × [10, 19.5] |
| 5 | die attach | SAC305, 58 | die footprint [8, 13] × [8.5, 13.5] |
| 6 | die | 4H-SiC, 370 | [8, 13] × [8.5, 13.5] |

Everything else is void (docs/thermal_model.md §2). That includes the 1.5 mm gap between the islands, the notch of
the L (whose re-entrant corner is at (21.5, 10)), the 1.5 mm ceramic margin around the copper, the backside-Cu margin
below the ceramic and the baseplate overhang top. `MMSCase.region_of(x, y, z)` gives the region index of cell
centres, and `MMSCase.materials[j]` gives the Layer.

## 3. Derivation
**Interface data.** Each interface i = 0..7 carries two smooth plane functions. Both layers that meet there use them:
- Θ_i(x, y) = a_i + b_i B + c_i B₂ + τ
- G_i(x, y) = g_i + e_i B + f_i B₂, with G = k ∂T/∂z

The terms are:
- B is an anisotropic Gaussian centred on the die (σx = 6.5 mm, σy = 5.5 mm).
- B₂ is a 4 mm Gaussian on island B at (23, 13.5).
- τ = −1000 K/m (x − 10.5 mm) − 600 K/m (y − 11 mm) is a lateral tilt.
- g, e, f are frozen constants (runner header). For example, the peak heat flux at the die top is
  g₇ + e₇ = 2.35 MW/m².
- a, b, c come from a deterministic 1-D column rule (`_column`: each layer's drop solves
  d = t·Ḡ/k(Θ + d/2)) applied to the far, main-bump and secondary-bump columns. The rule is only a design rule: any
  smooth Θ is admissible, and a consistent one keeps the source moderate.

**Field.** In layer j, with s = (z − z_j)/t_j, T* is the cubic Hermite interpolant in z (de Boor 1978, ch. IV):

T_j = Θ_j h00(s) + Θ_{j+1} h01(s) + t_j [G_j / k_j(Θ_j) · h10(s) + G_{j+1} / k_j(Θ_{j+1}) · h11(s)]

Here h00 = 2s³ − 3s² + 1, h01 = −2s³ + 3s², h10 = s³ − 2s² + s and h11 = s³ − s². Substitution gives T_j(z_j) = Θ_j and
∂zT_j(z_j) = G_j / k_j(Θ_j), so k_j(T_j) ∂zT_j = G_j at the interface. The same holds at z_{j+1}. So **T\* and the
normal flux are continuous at every material interface, for every (x, y), by construction**. Other ways of building
it were rejected:
- A z-independent lateral term would have forced zero heat flow across the interfaces when the k laws differ.
- Chained Kirchhoff inverses would have needed Lambert W for SAC305.

Each layer's formula is analytic on the whole plane. Patterning therefore only decides which faces are void-bounding,
and lateral faces need no constraint because there are no lateral material–material interfaces.

**Source.** q''' = −div(k_j(T_j) ∇T_j), from exact sympy differentiation of the flux components F = k ∇T
(`terms_sym`, lambdified with CSE). By the Kirchhoff identity div(k ∇T) = Δφ(T) with φ' = k (Carslaw & Jaeger 1959,
§1.8; Bagnall, Muzychka & Wang 2014), this is also −Δφ_j(T*). The FD check uses that independent form.

**Faces.** The inflow (heat into the domain, W/m²) is k(T*) ∂T*/∂n with n outward, so it is +F·n. It is applied on:
- top faces: +G_i (die top G₇, copper top outside the die G₅, ceramic in the gaps G₄, baseplate overhang top G₁);
- bottom faces: −G_i (ceramic underside in the margin, −G₃);
- side faces: ±k ∂T*/∂x or ±k ∂T*/∂y.

The callable resolves the region of a horizontal face from z plus the sign (+1 means the layer below the plane) and
returns 0 on z = 0, because the contract makes the flux additive to Robin there.

**Robin.** h = 5000 W/(m² K), uniform (O002's value). The outflow k ∂T*/∂z at z = 0 is G₀, so
T_inf(x, y) = Θ₀ − G₀/h. Its range is 288.7–332.5 K, inside the k-law validity range, so a Picard iteration started
at the mean sink temperature does not trip `k_at`.

**Smoothness constraint (inference).** The cited Al2O3 law changes exponent at 400 K, so k is C⁰ but not C¹ there.
A field that crossed 400 K in the ceramic would give a lateral flux discontinuity on the isotherm, which a pointwise
source cannot represent. The design keeps the ceramic below 399 K (max 390.27 K, gated). Consequence: the MMS does
not exercise the upper Al2O3 branch. The k(T) layouts of A3 do (O002 Tj up to 448 K).

## 4. Self-checks (`--selfcheck`, exit 1 on any failure; run 2026-11-01, all PASS)

| gate | result | threshold |
|---|---|---|
| sympy k laws vs `Layer.k_at` (280–520 K; ceramic to 400 K) | 2.1e-14 | ≤ 1e-12 |
| field range | 100.749 K | 60–110 K |
| T* and T_inf inside 273.15–523.15 K | yes | — |
| ceramic below the Al2O3 branch point | 390.27 K | < 399 K |
| k variation, ceramic (k_max/k_min − 1) | 0.3227 (k 18.07–23.91 W/(m K), T 301.1–390.3 K) | ≥ 0.30 |
| source vs independent FD, 1400 seeded points (seed 61530), 200 per region | max 1.0e-8 | ≤ 1e-6 |
| interface continuity, 6 interfaces × 500 points: T / k ∂T/∂z | 5.8e-16 / 4.2e-13 | ≤ 1e-10 |
| global balance ∫q dV + ∫inflow dA − ∫h(T − T_inf) dA, over Q_out | 3.3e-12 | ≤ 1e-10 |
| per-region balance (with interface terms) | max 7.9e-13 | ≤ 1e-10 |
| cubature convergence (Gauss–Legendre n = 12 → 18, Q_out) | 0 | ≤ 1e-12 |

How the checks are built:
- **FD check.** It uses only the lambdified T* (no symbolic derivatives) and the stack's numeric `k_at`. φ(T) − φ(T_c)
  comes from 16-point Gauss–Legendre, and the second derivatives from 6th-order central differences
  (Fornberg 1988): h = 0.25 mm laterally and t_j/16 in z, with points kept 3.5 h_z inside each layer. The error is
  normalised by Σ_a |∂_a(k ∂_aT)| at the point, so near-zero sources do not inflate it.
- **Balances.** They use the public `source`, `flux` and `T_inf` callables on an exact decomposition of every
  region's boundary into rectangles. This checks the contract mapping (signs, face ownership), not only the internal
  expressions.
- **Kinds of k variation.** In the ceramic, k_max/k_min − 1 = 0.323 and (k_max − k_min)/k_max = 0.244. The objective
  does not define "varies by 30 %". I gate on the min-normalised ratio. The max-normalised one cannot reach 30 % in
  the ceramic: with the cited law below 400 K, a 30 % max-normalised change needs a ceramic span of about 112 K, which
  is more than the whole 60–110 K field range. **Ambiguity flagged for the founder/critic.**
- **Energy budget.** Q_out = 64.65 W. Face inflow is 364.76 W, of which 230.9 W is on the top-Cu faces and 51.8 W on
  the die. The volumetric source is net −300.11 W (−207.2 W in the baseplate). So the case is far from physical:
  heat enters on most void faces, and the bulk acts as a sink. This is by design for code verification
  (Salari & Knupp 2000): every operator term, every face type and the Robin T_inf(x, y) are exercised. It also means
  a solver that ignored void-face fluxes would be off by hundreds of watts.

## 5. Reported points (the top surface: die top z₇, Cu top z₅, ceramic in gaps z₄, baseplate overhang z₁)
Every point is at least 1 mm from any change of surface level, so a correct bilinear surface interpolation is second
order there. The die mean and maximum are taken over the whole die top, edges included.

| id | surface | x, y (mm) | T* (K) |
|---|---|---|---|
| die_centroid | die | 10.5, 11.0 | 395.1205 |
| die_mean | die (area mean, 32×32 Gauss–Legendre) | [8, 13] × [8.5, 13.5] | 391.2212 |
| die_max | die (interior max, L-BFGS-B polish) | 9.900, 10.738 | 395.4864 |
| cuA_1 | Cu island A | 6.0, 17.0 | 355.0735 |
| cuA_2 | Cu island A | 15.0, 6.0 | 358.5267 |
| cuB_arm1 | Cu island B | 20.0, 7.25 | 337.8707 |
| cuB_arm2 | Cu island B | 23.5, 15.0 | 323.5993 |
| gap_ceramic | ceramic in the L notch | 19.0, 15.0 | 339.5083 |
| overhang_baseplate | baseplate overhang | 1.5, 12.0 | 342.4950 |

Case scale (A1) = field range = 100.749 K, so 1 % = 1.007 K.

## 6. F3 estimate (diagnostic, not evidence)
`--emit` solves the manufactured problem with an **own** cell-centred FV solver. It uses Patankar half-cell
conductances, 3-point Gauss data integration, Picard iteration on k(T) to 1e-6 K and the same surface reconstruction
T_c + q dz/2k. It runs on two grids:
- lateral ≤ 0.5 mm, 21 z-cells: 32 k active cells;
- lateral ≤ 0.25 mm, 42 z-cells: 259 k active cells.

| quantity (max over the 9 points) | 0.5 mm | 0.25 mm |
|---|---|---|
| \|T_fv(k(T)) − T*\| (consistency of the data) | 0.1436 K | 0.0359 K (ratio 4.0, second order) |
| \|T_fv(const k) − T_fv(k(T))\| (the k(T) effect, discretisation cancels) | 2.512 K | 2.514 K |
| \|T_fv(const k) − T*\| (F3's dT_const_k as E006 will compute it) | 2.614 K | 2.540 K |
| energy balance \|Q_out/Q_in − 1\| | 1e-13 | 2e-14 |

The constant k is k_j at each region's volume-mean T* (325.3, 332.6, 333.6, 339.7, 355.4, 388.7 and 390.4 K, bottom
up). The largest shifts are at the die: die_max −2.51 K, die_centroid −2.48 K, die_mean −2.26 K. The other points move
by 0.02–0.75 K.
- **Expected.** E006's `dT_const_k` should fail A1 (2.5 K > 1.007 K) and A2 (> 0.05 K) by wide margins, so F3's
  discrimination requirement holds. The E006 dev rows will confirm it with the production solver.
- **Inference.** The shift is set almost entirely by the ceramic's lateral k contrast under the die (local about
  381 K against the 339.7 K layer mean). It barely depends on the grid (2.512 against 2.514 K).

**What this does and does not show.** The own FV converges to T* at second order. That is end-to-end evidence that
the data (source, face inflows, Robin) are mutually consistent and sign-correct under my reading of the contract. It
is not evidence about the production solver, and it shares my interpretation of the contract's conventions. Those
conventions are written in the module docstring and in the JSON `bc` block so that E006 can audit them.

**Discretisation warning for E006 (inference).** My FV error at 0.25 mm is 0.036 K, close to A2's 0.05 K. A
production grid rule coarser than about 0.3 mm laterally would likely fail A2 on this case through discretisation
alone, not through a model error. The GCI (A4) would show it.

## 7. Using the case in E006
`from e006_mms import build_case` (with experiments/runners on the path), then `case = build_case()`. Then:
- solver inputs: `case.source`, `case.flux`, `case.h`, `case.T_inf`, `case.materials[j]`, `case.region_of(xc, yc, zc)`;
- grid lines must include every box edge (`XB`, `YB`) and `Z`;
- reference values: `reported_points(case)` or the frozen JSON;
- checks: `case.T_exact` and `case.surface_exact` for diagnostics, and the energy balance against
  ∫q dV + Σ inflow = 64.648 W.

Any change to the field, geometry or points after the first solver comparison voids the run (F1). Make it under a new
experiment id.

## 8. Open questions
- Which "30 %" definition did the objective intend (section 4)?
- The upper Al2O3 branch (> 400 K) is not covered by this case.
- Should E006 also compare interior cell values? The solver API gives the top surface only, and these points are on
  that surface.
