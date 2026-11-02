# O006 / E006 analytic references: Muzychka 2003 flux-channel series and an N-layer Fourier series
Date: 2026-11-01, re-issued 2026-11-01 · Task: T0151 (scientist), re-issued as T0164 · Code: `experiments/runners/e006_series.py` ·
Values: `research/e006_refs/series_values.json` (sha256 of the canonical payload
`befc5efaf2d50e3c096b41521814e2949885279d702cf38b921a090b80667151`)

**Status (T0164): all gates pass; `--selfcheck` exits 0.** T0164 re-issues T0151 after the founder decision of
2026-11-02, which aligned the brief with the frozen O006 F1. The 50-term paper-reproduction gate (`GATED_PRINTED`) now
covers exactly F1's printed Case 3 values: 80.61 °C maximum at the centre and 78.87 °C source mean, to their printed
digits. Every other printed value, including the Case 1a/1b centroids, is still computed at 50 terms. It is printed by
`--selfcheck` with the tag INFO and is not gated (section 5.2). That `GATED_PRINTED` line, its comment and the
`check_paper` docstring are the only code changes from T0151's commit 9c01c7c. No reference value, parameter, material
constant or the Case 2 T_f changed. A fresh `--emit` reproduces the payload sha256 given above (section 5.1).

T0151's diagnosis still stands (sections 5.2 and 5.3). An independent scalar implementation of the printed equations
gives the runner's 50-term values to 1.7e-13 K. No equal truncation N from 1 to 200 reproduces the printed Case 1a s1,
Case 1a s2 or Case 1b s2 centroid. Neither Table 1 nor Table 2 fits a single N even within itself. Those printed
values therefore test the paper's summation convention, not the physics. As the packet instructs, no converged-value
tolerance against Tables 1-2 was added: the numbers have already been seen.

Labels used below: **[fact]** means checked by code in this task (the gate name is given); **[source]** is quoted or
transcribed from a cited paper; **[inference]** is reasoning not checked directly; **[speculation]** is marked as such.

## 1. Sources
| id | citation | what was used | read |
|---|---|---|---|
| M03 | Y. S. Muzychka, J. R. Culham, M. M. Yovanovich, "Thermal spreading resistance of eccentric heat sources on rectangular flux channels", *J. Electron. Packag.* 125(2):178–185 (2003), doi:10.1115/1.1568125, author copy at uwaterloo.ca/microelectronics-heat-transfer-laboratory (S44 of `project/memory/literature/thermal-l2-reference.md`) | eqs. (16)–(31), (37)–(41); Case 1/1b/2/3 parameters; Tables 1–4; Case 3 text | full text: text extracted from the author PDF (2026-11-01) |
| A95 | J. Albers, IEEE Trans. CPMT-A 18(1):31–38 (1995), doi:10.1109/95.370732 (S51) | exact recursion for N layers (the family of the kernel in 3.3) | abstract only |
| B14 | K. R. Bagnall, Y. S. Muzychka, E. N. Wang, IEEE TCPMT 4(5):817–830 (2014), doi:10.1109/TCPMT.2014.2299766 (S47) | N-layer, multi-source surface field | abstract only |
| C19 | A. Choudhury, D. J. Rogers, IEEE TPEL 34(2):1500–1508 (2019), doi:10.1109/TPEL.2018.2828439 (S52) | N-layer Fourier model of a power module | abstract only |
| M04 | Y. S. Muzychka, M. M. Yovanovich, J. R. Culham, *J. Thermophys. Heat Transf.* 18(1) (2004) (S45) | eq. (4): R_1D = Σ t_i/(k_i A) + 1/(hA) | via the memory note |
| ST | `moduleforge.geometry.stack` (the citations are in its docstring) | default DBC stack, die attach and die thicknesses and k at 300 K | repository |

I did not read A95, B14 or C19 in full. The N-layer kernel is therefore **derived here** (section 3.3) and checked
against an explicit boundary-value solve and against M03 eq. (30). Those papers are cited only as the established
family of methods; I do not claim the code follows their notation.

## 2. Problem and conventions
- Domain: a rectangular flux channel, 0 ≤ x ≤ a, 0 ≤ y ≤ b, with adiabatic sides. Uniform film coefficient h at
  the sink plane to fluid at T_f. Perfect contact between layers. Constant k per layer.
- Sources: uniform-flux rectangles c × d centred at (X_c, Y_c), power Q, flux q = Q/(cd). The origin is the lower-left
  corner of the plate, as in M03.
- Depth: the series use depth ζ measured downward from the source plane (M03's z). In ModuleForge coordinates
  (z up, z = 0 at the bottom of the baseplate) the source plane is z = total thickness.
- Units: SI and float64 throughout. T is in kelvin in the code and the JSON; °C appears only in comparisons with M03.
- Reported temperatures are surface temperatures (ζ = 0), the quantity the A1/A2 description compares with the L2
  reconstructed surface temperature.

## 3. Formulas
### 3.1 Mode form of the surface temperature (M03 eqs. 16, 20, 22, 24, 25, 37)
[source] M03 eq. (16) at ζ = 0, superposed over the sources (eq. 37):

  T(x,y) − T_f = Σ_i [ A_0ⁱ + Σ_m A_mⁱ cos λ_m x + Σ_n A_nⁱ cos δ_n y + Σ_m Σ_n A_mnⁱ cos λ_m x cos δ_n y ],

with λ_m = mπ/a, δ_n = nπ/b, β_mn = (λ_m² + δ_n²)^½ and the following coefficients:
- eq. (20): A_m = 2Q[sin((2X_c+c)λ_m/2) − sin((2X_c−c)λ_m/2)] / (a b c k₁ λ_m² φ(λ_m))
- eq. (22): the same in y with d, δ_n
- eq. (24): A_mn = 16Q cos(λ_m X_c) sin(λ_m c/2) cos(δ_n Y_c) sin(δ_n d/2) / (a b c d k₁ β_mn λ_m δ_n φ(β_mn))
- eq. (25)/(28)/(31): A_0 = (Q/ab)(Σ t_i/k_i + 1/h)

[inference, algebra] The same field written per mode is
θ = Σ_i q_i Σ_{m,n≥0} a_mⁱ b_nⁱ cos λ_m x cos δ_n y · Z(β_mn). Here a_m and b_n are the cosine coefficients of the
source indicator: a_0 = c/a, a_m = (2/a)(sin λ_m x₂ − sin λ_m x₁)/λ_m. Z(β) = θ/flux of one mode at the top
surface: Z(0) = Σ t/k + 1/h, and Z(β) = 1/(k₁ β φ(β)) otherwise. The code uses this form for the converged values
and the literal eqs. (20)–(25) for the 50-term reproduction, so the two are independent code paths.

### 3.2 Source mean (M03 eqs. 27, 41) and φ (eqs. 18, 30)
- [source] eq. (27)/(41) gives the mean over patch j: cos λ x is replaced by its patch mean,
  2 cos(λ X_cj) sin(λ c_j/2)/(λ c_j).
- [source] eq. (18), one layer: φ(ζ) = (ζ sinh ζt + (h/k) cosh ζt) / (ζ cosh ζt + (h/k) sinh ζt).
- [source] eq. (30), two layers, where layer 1 is the source layer:
  φ = [(α e^{4ζt₁} − e^{2ζt₁}) + ϱ(e^{2ζ(2t₁+t₂)} − α e^{2ζ(t₁+t₂)})] /
      [(α e^{4ζt₁} + e^{2ζt₁}) + ϱ(e^{2ζ(2t₁+t₂)} + α e^{2ζ(t₁+t₂)})],
  with ϱ = (ζ + h/k₂)/(ζ − h/k₂), α = (1 − κ)/(1 + κ) and κ = k₂/k₁.
- Code: both are evaluated in exactly equivalent overflow-free forms:
  - eq. (18) through tanh;
  - eq. (30) with numerator and denominator multiplied by (ζ − h/k₂) e^{−2ζ(2t₁+t₂)}, which also removes the
    removable pole of ϱ.
- [fact] `kernel_eq30_kappa1_equals_eq18`: eq. (30) with κ = 1 equals eq. (18) for the total thickness, to 0 relative
  difference.

### 3.3 N-layer kernel (derived here; recursion family of A95, B14 and C19)
Each Fourier mode obeys θ'' = β²θ in every layer. Write ρ for the normalised input impedance k_i β Z at the bottom of
layer i.
- (N3) Across layer i (k_i, t_i): ρ_top = (ρ_bottom + T_i)/(1 + ρ_bottom T_i), with T_i = tanh(β t_i).
- (N4) At an interface, Z is continuous, so ρ in the layer above is (k_above/k_i) · ρ_top.
- (N5) At the sink, Z = 1/h, so ρ_N = k_N β/h.
- Top layer: k₁ β Z = (1 + G e)/(1 − G e), with G = (ρ₁ − 1)/(ρ₁ + 1) and e = e^{−2βt₁}. The excess
  E = k₁ β Z − 1 = 2Ge/(1 − Ge) therefore has no cancellation.

[fact] Checks on this kernel:
- `kernel_recursion_equals_linear_system`: it equals an explicit 14 × 14 boundary-value solve for the 7-layer stack
  (max relative difference 1.7e-12 for β = 1 to 2e4 m⁻¹).
- `kernel_recursion_equals_eq30`: it equals M03 eq. (30) for two layers (1.0e-13).
- `kernel_beta0_limit_is_R1D`: as β → 0, Z tends to Σ t/k + 1/h.

### 3.4 Series acceleration (derived here)
**Split of the kernel.** Write Z(β) = 1/(k₁β) + R(β), with R = E/(k₁β).
- [fact, from the forms above] E decays like e^{−2βt₁}, where t₁ is the source-layer thickness. That decay is
  2α e^{−2βt₁} for eq. (30) and 2G e^{−2βt₁} for the N-layer kernel.
- The R-series is therefore summed directly. It is exponentially convergent and truncated at 2β t₁ ≥ 36 per
  direction, with at least 64 modes.

**Infinite-depth part.** This part sums 1/(k₁β), which converges only algebraically (O(1/N²) for the slowest point
values; see the raw-sum errors in 5.1). It is summed exactly through the Gaussian integral

  (S1) 1/β = (2/√π) ∫₀^∞ e^{−β²s²} ds.

That makes the double sum separable:

  (S2) Σ_{(m,n)≠(0,0)} q a_m b_n cos λ_m x cos δ_n y /(k₁β) = (q/k₁)(2/√π) ∫₀^∞ [F_x(x,s) F_y(y,s) − a₀b₀] ds.

**The 1D factors.** F_x(x,s) = Σ_{m≥0} a_m cos λ_m x e^{−λ_m² s²} is the source indicator smoothed by the heat kernel
at time s² with insulated ends.
- (S3) It is evaluated by images for s ≤ a/4:
  F_x = Σ_j ½[erf((x−x₁+2ja)/2s) − erf((x−x₂+2ja)/2s) + erf((x+x₂+2ja)/2s) − erf((x+x₁+2ja)/2s)],
  with j = −3…3.
- For s > a/4 it is evaluated by its cosine series (16 terms). The two forms are Poisson duals.
- [fact] `heat_kernel_images_equal_fourier`: the two forms agree to 6.5e-14.
- (S4) Patch means use the antiderivative of erf(u/2s), u erf(u/2s) + (2s/√π) e^{−u²/4s²}. Its |u| part is formed
  exactly from the patch width, so far images carry no ε|u|/Δp cancellation.
- The method of images is the textbook construction. The erf form for an insulated finite rod is in
  Carslaw & Jaeger, *Conduction of Heat in Solids*, 2nd ed. (1959), ch. II (not re-read for this task). The S3–S4
  identities are checked numerically, not taken on trust.

**Quadrature in s.**
- Composite 12-point Gauss–Legendre in u = ln s, with panels 0.5 wide.
- Range: s from 10⁻¹² min(a,b) to 3 max(a,b). The integrand at the upper end is about e^{−9π²} = e^{−89}.
- [0, s_lo] is taken as s_lo · f(s_lo).

**Doubling test (F1).** "Doubling the terms" means doubling each knob in turn and then all together:
- `modes`: the cut 36 → 72, i.e. twice the modes per direction (the minimum 64 → 128);
- `quad`: panel width halved, s_lo squared, s_hi doubled;
- `images`: J 3 → 6 and the cosine terms 16 → 32;
- `all`: all three at once.

The maximum is re-optimised in each doubled configuration, starting from the frozen maximiser.

### 3.5 Points, 1D solution and scale per case
For each source the code reports:
- the centroid T;
- the source mean T̄ (eq. 27/41);
- the maximum of the field over the closed source rectangle and its location. This is found by a 21 × 21 scan and
  then bounded L-BFGS-B from the three best scan points. [fact] `max_dominates_samples_and_scale_positive`: it is at
  least every scan sample, the centroid and the mean.

The 1D uniform-flux solution is T_1d = T_f + Q_total (Σ t/k + 1/h)/(ab). This is the sum of the A₀ terms, the mean
of the surface field over the whole face (M03's T̄_b; M04 eq. 4).
- [fact] `face_mean_equals_T1d`: holds to 1.2e-15.
- [fact] `paper_Tb_*`: matches the printed T̄_b = 53.06 °C of Tables 1–2.

The A1 scale of a case is max over its sources of (T_max,i − T_1d), following the A1 description in the objective.

## 4. Cases and parameters
| case | a × b [mm] | layers, top → bottom (t [mm], k [W/(m K)]) | h [W/(m² K)] | T_f [°C] | sources: name (X_c, Y_c; c × d [mm]; Q [W]) |
|---|---|---|---|---|---|
| case1a (M03 Case 1, Table 1) | 300 × 300 | (10, 10) | 10 | 25 | s1 (90, 90; 25 × 25; 10), s2 (210, 210; 25 × 25; 15) |
| case1b (M03 Table 2) | 300 × 300 | spreader (2, 350); plate (10, 10) | 10 | 25 | as case1a |
| case2 (M03 Tables 3–4) | 50 × 50 | (10, 150) | 400 | **25 (fixed here)** | s1 (12.5, 12.5; 10 × 10; 10), s2 (37.5, 12.5; 10 × 10; 25), s3 (12.5, 37.5; 10 × 10; 20), s4 (37.5, 37.5; 10 × 10; 15) |
| case3 (M03 text) | 100 × 100 | (10, 50) | 50 | 25 | five 20 × 20 mm, 5 W squares in a cross: centre (50, 50), west (30, 50), east (70, 50), south (50, 30), north (50, 70) |
| nlayer_dbc | 86 × 56 | die 4H-SiC (0.18, 370); die attach SAC305 (0.05, 58); top Cu (0.3, 385); Al2O3 (0.38, 24); backside Cu (0.3, 385); solder SAC305 (0.1, 58); baseplate Cu (3.0, 385) | 5000 | 65 | d1 (20, 18; 4.0 × 4.0; 76), d2 (31, 18; 5.5 × 5.5; 140), d3 (55, 36; 4.5 × 4.5; 104), d4 (79.5, 49; 5.0 × 4.0; 92) |

Notes on the parameters:
- **Case 1b layer order.** [source] M03: "a thin, t = 2 mm, highly conductive layer k = 350 W/mK, is added to the
  original substrate"; "adding a spreader has reduced the maximum source temperatures". So the spreader is layer 1,
  carrying the sources.
- **Case 2 T_f.** [source] M03 does not state T_f for Case 2. 25 °C is fixed here, as in Cases 1 and 3; the choice
  is documented in the code (`CASE2_TF_C`). [inference] With T_f = 25 °C the converged centroids are within 0.012 to
  0.024 K of Table 4 (5.2), so the tables are consistent with 25 °C, but they are not a gate.
- **N-layer stack.**
  - Thicknesses and k(300 K) come from `default_dbc_stack()` and its `die_attach`/`die` layers. The exact values the
    case uses are listed in 4.1. E006 should build its L2 case from that list, not by reading
    `moduleforge.geometry.stack` again.
  - Every layer spans the whole footprint (laterally uniform), and k is constant.
  - The footprint is the generator's baseplate box (−8…78 × −8…48 mm in `generate/halfbridge.py`).
  - h = 5000 W/(m² K) and 65 °C coolant are pilot P1's values.
  - The dies sit in four situations: a coupled pair (d1–d2, 6.25 mm gap), an isolated die (d3), and a rectangular die
    4 mm from two walls (d4).
- **Die powers.** They were set from this reference alone, before any solver comparison. The first choice
  (95/175/130/115 W) gave peak rises of 102–126 K, above the 60–110 K band; the problem is linear, so all powers were
  scaled by 0.8. [fact] `nlayer_rises_in_O002_band`: the peak rises above the coolant are 81.4, 100.6, 88.2 and
  91.5 K.

### 4.1 N-layer case (`nlayer_dbc`): exact layers and inputs for E006's L2 case
[fact] These values are the float64 values printed by `nlayer_layers()` and `case_nlayer()` in the runner (T0164,
2026-11-01). They are the same as the payload's `cases.nlayer_dbc` entry, which the sha256 above pins. Every layer
spans the whole 86 × 56 mm footprint (laterally uniform). k is constant (no k(T)).

| order (bottom → top) | layer name | thickness t [m] | t [mm] | k [W/(m K)] | material (per `geometry.stack`) |
|---|---|---|---|---|---|
| 1 (bottom, cooled face) | baseplate | 3.0e-3 | 3.00 | 385.0 | Cu |
| 2 | solder | 1.0e-4 | 0.10 | 58.0 | SAC305 |
| 3 | backside_cu | 3.0e-4 | 0.30 | 385.0 | Cu |
| 4 | ceramic | 3.8e-4 | 0.38 | 24.0 | Al2O3 |
| 5 | top_cu | 3.0e-4 | 0.30 | 385.0 | Cu |
| 6 | die_attach | 5.0e-5 | 0.05 | 58.0 | SAC305 |
| 7 (top, source plane) | die | 1.8e-4 | 0.18 | 370.0 | 4H-SiC |

Total thickness 4.31 mm. Other inputs:
- Footprint a × b = 0.086 × 0.056 m. The origin is the lower-left corner of the generator's baseplate box, which is
  (−8, −8) mm in `generate/halfbridge.py` coordinates.
- Uniform h = 5000 W/(m² K) on the bottom face (z = 0), coolant T_f = 65 °C = 338.15 K. The side walls are adiabatic.
- Uniform-flux sources on the top face (z = 4.31 mm), given as (x_c, y_c; c × d) in mm in the case frame, with power Q:
  - d1: (20.0, 18.0; 4.0 × 4.0), 76 W
  - d2: (31.0, 18.0; 5.5 × 5.5), 140 W
  - d3: (55.0, 36.0; 4.5 × 4.5), 104 W
  - d4: (79.5, 49.0; 5.0 × 4.0), 92 W
- T_1d = 357.67694155722853 K (84.526942 °C).

[inference] E006 has to model the whole die layer as a laterally uniform slab across the footprint, and the same for
the die-attach layer. This is the series' geometry, not the module's die islands, which are A3's job. If E006's L2
case uses die-sized islands for these two layers, it solves a different problem from this reference.

## 5. Gate results (`uv run python experiments/runners/e006_series.py --selfcheck`; exit 0 under T0164)
### 5.1 Gates (all pass; T0164 run: 22 of 22 gates pass, 77 s on the M5; the 16 paper50 comparisons other than Case 3 print as INFO)
| gate | result | threshold |
|---|---|---|
| convergence_doubling_{case1a, case1b, case2, case3, nlayer_dbc} | max relative change of every reported value (centroid, mean, max), relative to its rise: ≤ 1.1e-15 for all knobs; changes are at the level of one ulp of T in K | < 1e-7 |
| raw_partial_sums_converge_to_accelerated | the raw M03 sums at N = 100, 200, 400 and 800 approach the accelerated values monotonically. Worst at N = 800: 1.9e-6 of the rise, falling 3–8× per doubling (Case 1b and 2 centroids and means, Case 3 centre) | ≤ 1e-4, decreasing |
| nlayer_equals_two_layer | (i) Case 1b with its layers split into 5 sublayers through the N-layer kernel, against M03 eq. (30); (ii) the 7-layer stack collapsed to two conductivities (top 3 layers k = 370, bottom 4 k = 24) against eq. (30) with summed thicknesses. Max relative difference at centroid, mean and max points: 2.2e-16 | ≤ 1e-9 |
| full_top_source_equals_1D | a source covering the whole face gives Q R_1D/(ab) at corner, centre, edge and interior points and on a patch, for all 5 stacks: 3.3e-16 | ≤ 1e-9 |
| paper50_case3_centre_centroid | 50 terms: 80.6147 °C against the printed 80.61 | |Δ| ≤ 0.005 K |
| paper50_case3_cross_mean | 50 terms: 78.8712 °C against the printed 78.87 | |Δ| ≤ 0.005 K |
| paper_Tb_case1a / case1b | 53.0556 / 53.0571 °C against the printed 53.06 | |Δ| ≤ 0.005 K |
| kernel_* (4) and heat_kernel_images_equal_fourier | see section 3 | 1e-12 / 1e-10 / 1e-6 / 1e-13 |
| face_mean_equals_T1d | 1.2e-15 | ≤ 1e-9 |
| reciprocity_mean_rise | mean rise of patch j per watt in source i equals that of i per watt in j (Cases 1b, 2 and N-layer): 2.5e-15 | ≤ 1e-9 |
| case3_symmetry_and_centre_max | the four arm means are identical; the maximiser of the centre source is at (50, 50) mm to 0 m | 1e-10, 1e-7 m |
| max_dominates_samples_and_scale_positive | no violations | |
| nlayer_rises_in_O002_band | 81.4–100.6 K | 60–110 K |

### 5.2 Informational (INFO, not gated): the 50-term Case 1a/1b centroids
Under T0151 these four centroids were gated, and three of them failed. Under T0164, in line with frozen F1, they are
reported as INFO together with the other printed values (Case 1a/1b means, the Case 2 Table 4 values). The
diagnosis below is T0151's and is unchanged.
| quantity | printed (M03) | own 50 terms (m, n = 1…50) | Δ [K] | converged |
|---|---|---|---|---|
| Case 1a s1 centroid | 84.97 | 84.9386 | −0.031 | 85.4506 |
| Case 1a s2 centroid | 108.43 | 108.3842 | −0.046 | 109.1522 |
| Case 1b s2 centroid | 59.94 | 59.9475 | +0.0075 | 59.9743 |
| Case 1b s1 centroid (within 0.005 K; INFO) | 56.55 | 56.5480 | −0.002 | 56.5659 |

[fact] I scanned truncations to see whether any convention reproduces all six gated printed values (Case 3 centre and
mean, Case 1a and 1b centroids) to |Δ| ≤ 0.005 K. Both scans used a temporary script, not part of the deliverable.
- Square: single sums m ≤ N₁, double sums m, n ≤ N₂, with N₁ from 10 to 100 and N₂ from 5 to 100.
- Triangular: double sums with m + n ≤ N₂.
- **No convention does.** The best worst-case |Δ| is 0.0086 K (N₁ = 70–73, N₂ = 47–48). Under equal truncation
  N₁ = N₂ = N, Case 1b s2 comes within about 0.005 K only at N = 47–49, and there the Case 1a centroids are off by
  0.07–0.11 K.
- The Case 1a 50-term centroids are far from converged: the converged values are +0.48 and +0.72 K higher. They also
  move by 0.02 to 0.1 K when N changes by one (for example −0.031 at N = 50, −0.013 at 51, +0.066 at 53). They are
  truncation artefacts of a particular summation, and a correct implementation need not reproduce them to 0.01 K.

[inference] Why T0151's failure points to the gate rather than the code:
1. The same code reproduces Case 3 (both values), Case 1b s1 and T̄_b.
2. Its converged values are the limit of its own raw partial sums (5.1).
3. The compound kernel (eq. 30), which drives Case 1b, equals two independent derivations to 1e-13.
4. Independently, the converged Case 2 centroids agree with the scikit-fem scratch run S59 in
   `project/memory/literature/thermal-l2-reference.md` (T_f = 25 °C, 0.5 mm Q1 hexahedra) to ≤ 0.0012 K:
   97.3876 / 103.7958 / 101.2631 / 99.9204 against 97.388 / 103.797 / 101.264 / 99.921 °C. That run is not admissible
   evidence, but it is an independent method.

[speculation] Possible causes on the paper's side: Maple's summation details or a transcription or rounding slip in
the tables. The objective's own notes already record that "the paper's Case 2 table is not reproducible at 50 terms".

### 5.3 T0151 attempt 2 (2026-11-01): discriminating tests for the then-failing gates
Following mf-diagnosis, I tested two competing explanations for the three failures.
- **E1 (implementation):** the runner's 50-term path (`m03_truncated`) or its parameters are wrong.
- **E2 (reference/planning):** the printed Case 1a/1b centroids are not the output of the paper's printed equations
  under any single truncation, so no correct implementation can pass the gate.

I used a scratch script outside the repository, so it is not a deliverable. It imports the runner's case
definitions only.

1. **Parameter transcription (tests E1).** [source] I re-extracted the text of the author PDF of M03, pages 182–184,
   with a stdlib-only stream parser. These match the runner:
   - Case 1: a = b = 300 mm, t₁ = 10 mm, h = 10, k = 10, T_f = 25 °C, c = d = 25 mm. The sources are 10 W at
     X_c = Y_c = 90 mm and 15 W at X_c = Y_c = 210 mm. "A total of 50 terms were used in each of the single and
     double summations."
   - Case 1b: "a thin, t = 2 mm, highly conductive layer k = 350 W/mK, is added to the original substrate".
   - Case 2: Table 3.
   - Case 3: as stated in the text.
   - Equations: (18), (20), (22), (24), (25), (27), (28), (30), (31), (38) and (41) as printed.
   - Tables 1 and 2 list the centroid first and the mean second. The text gives "centroidal temperatures … 84.97 °C
     and 108.43 °C" and "56.55 and 59.94 °C".
2. **Independent re-implementation (tests E1).** [fact] I wrote fresh scalar loops of eqs. (18)/(30), (20), (22),
   (24), (25)/(31) and (38), with φ in its literal sinh/cosh/exp form rather than the runner's overflow-free form.
   At 50 terms they give these centroids:

   | centroid | °C |
   |---|---|
   | Case 1a s1 | 84.938624 |
   | Case 1a s2 | 108.384159 |
   | Case 1b s1 | 56.548006 |
   | Case 1b s2 | 59.947463 |
   | Case 3 centre | 80.614706 |

   The largest difference from the runner is 1.7e-13 K. E1 is therefore refuted for the 50-term path: the runner
   computes what the printed equations say.
3. **Which equal truncations m, n ≤ N (N = 1…200) reproduce each printed value to |Δ| ≤ 0.005 K (tests E2).** [fact]

   | printed value | N that reproduce it |
   |---|---|
   | Case 1a s1 centroid 84.97 | **none** |
   | Case 1a s1 mean 80.56 | 46–52 |
   | Case 1a s2 centroid 108.43 | **none** |
   | Case 1a s2 mean 101.81 | 53 only |
   | Case 1b s1 centroid 56.55 | 43–55 |
   | Case 1b s1 mean 56.05 | 57–200 |
   | Case 1b s2 centroid 59.94 | **none** |
   | Case 1b s2 mean 59.19 | 40–200 |
   | Case 3 centre 80.61 | 44–55, 58–200 and some smaller N |
   | Case 3 cross mean 78.87 | 24–200 |

   Within Table 1 the two means need disjoint N (46–52 against 53). Within Table 2 the s1 centroid and the s1 mean
   need disjoint N (≤ 55 against ≥ 57). So neither table is the output of the printed formulas under one truncation.
   Case 3 is, at N = 50, which is why its gate passes. This supports E2.
4. **One alternative reading of "centroid" (tests E2 further).** Eq. (41) superposes patch means. I tried this
   variant: the source's own contribution at its centroid point plus the other sources' contribution averaged over
   its patch, at 50 terms. [fact] It gives:

   | centroid | variant [°C] | printed [°C] | Δ [K] |
   |---|---|---|---|
   | Case 1a s1 | 84.9589 | 84.97 | −0.011 |
   | Case 1a s2 | 108.3977 | 108.43 | −0.032 |
   | Case 1b s1 | 56.5528 | 56.55 | +0.003 |
   | Case 1b s2 | 59.9507 | 59.94 | +0.011 |

   It fails three of the four. I tried no further variants. Searching many variants until one fits would itself be
   tuning, and a match found that way would be weak evidence.

[inference] T0151's classification: a **planning** failure, with confidence about 0.9. The T0151 packet required a
gate that a correct implementation cannot pass. T0164 resolves this by gating F1's Case 3 values only. The frozen objective's F1 requires only the Case 3 values, which pass. The
remaining uncertainty is that M03's Maple code may have used a convention I cannot recover from the paper, such as a
different truncation of the single sums or reduced floating-point precision. Even if it did, the 50-term Case 1a
centroids are 0.48 and 0.72 K below the converged values. They move by up to 0.1 K when N changes by one, so they
test the summation convention, not the physics. [fact] The converged values in `series_values.json` do not depend on
this gate. Re-emitting reproduced the committed payload exactly (sha256 `befc5efa…0667151`, 51 rows).

Informational comparisons, not gated (printed against converged, K):
- Case 1a means: +0.145 and +0.207.
- Case 1b means: −0.0012 and +0.0047.
- Case 2 Table 4: centroids −0.012 to −0.024; means +0.006 to +0.024.
- Case 3: centre +0.0019, cross mean +0.0031.

## 6. A1/A2 reference points per case (from the hashed JSON; T in °C here, K in the JSON)
T_1d is the 1D uniform-flux temperature. The scale is max_i (T_max,i − T_1d). "1 % of scale" is the A1 tolerance;
A2 is 0.05 K for every point.

**case1a**: T_f = 25.00 °C, T_1d = 53.055556 °C, scale = 56.102024 K (source s2), 1 % of scale = 0.5610 K; remainder modes 172 × 172

| source | point | x [mm] | y [mm] | T [°C] | rise T − T_f [K] |
|---|---|---|---|---|---|
| s1 | centroid | 90.0000 | 90.0000 | 85.450594 | 60.450594 |
| s1 | mean | 90.0000 | 90.0000 | 80.705153 | 55.705153 |
| s1 | max | 90.0572 | 90.0572 | 85.450866 | 60.450866 |
| s2 | centroid | 210.0000 | 210.0000 | 109.152175 | 84.152175 |
| s2 | mean | 210.0000 | 210.0000 | 102.017033 | 77.017033 |
| s2 | max | 210.2077 | 210.2077 | 109.157579 | 84.157579 |

**case1b**: T_f = 25.00 °C, T_1d = 53.057143 °C, scale = 6.920281 K (source s2), 1 % of scale = 0.0692 K; remainder modes 860 × 860

| source | point | x [mm] | y [mm] | T [°C] | rise T − T_f [K] |
|---|---|---|---|---|---|
| s1 | centroid | 90.0000 | 90.0000 | 56.565927 | 31.565927 |
| s1 | mean | 90.0000 | 90.0000 | 56.048841 | 31.048841 |
| s1 | max | 90.1348 | 90.1348 | 56.566108 | 31.566108 |
| s2 | centroid | 210.0000 | 210.0000 | 59.974347 | 34.974347 |
| s2 | mean | 210.0000 | 210.0000 | 59.194719 | 34.194719 |
| s2 | max | 210.4517 | 210.4517 | 59.977424 | 34.977424 |

**case2**: T_f = 25.00 °C, T_1d = 96.866667 °C, scale = 6.943202 K (source s2), 1 % of scale = 0.0694 K; remainder modes 64 × 64

| source | point | x [mm] | y [mm] | T [°C] | rise T − T_f [K] |
|---|---|---|---|---|---|
| s1 | centroid | 12.5000 | 12.5000 | 97.387642 | 72.387642 |
| s1 | mean | 12.5000 | 12.5000 | 96.856118 | 71.856118 |
| s1 | max | 13.5791 | 12.9677 | 97.425807 | 72.425807 |
| s2 | centroid | 37.5000 | 12.5000 | 103.795846 | 78.795846 |
| s2 | mean | 37.5000 | 12.5000 | 102.353099 | 77.353099 |
| s2 | max | 37.8928 | 12.3115 | 103.809868 | 78.809868 |
| s3 | centroid | 12.5000 | 37.5000 | 101.263066 | 76.263066 |
| s3 | mean | 12.5000 | 37.5000 | 100.123558 | 75.123558 |
| s3 | max | 12.5357 | 37.7288 | 101.266232 | 76.266232 |
| s4 | centroid | 37.5000 | 37.5000 | 99.920422 | 74.920422 |
| s4 | mean | 37.5000 | 37.5000 | 99.085659 | 74.085659 |
| s4 | max | 37.5566 | 37.1764 | 99.924918 | 74.924918 |

**case3**: T_f = 25.00 °C, T_1d = 75.500000 °C, scale = 5.111860 K (source centre), 1 % of scale = 0.0511 K; remainder modes 64 × 64

| source | point | x [mm] | y [mm] | T [°C] | rise T − T_f [K] |
|---|---|---|---|---|---|
| centre | centroid | 50.0000 | 50.0000 | 80.611860 | 55.611860 |
| centre | mean | 50.0000 | 50.0000 | 80.263217 | 55.263217 |
| centre | max | 50.0000 | 50.0000 | 80.611860 | 55.611860 |
| west | centroid | 30.0000 | 50.0000 | 78.944573 | 53.944573 |
| west | mean | 30.0000 | 50.0000 | 78.525523 | 53.525523 |
| west | max | 40.0000 | 50.0000 | 80.138167 | 55.138167 |
| east | centroid | 70.0000 | 50.0000 | 78.944573 | 53.944573 |
| east | mean | 70.0000 | 50.0000 | 78.525523 | 53.525523 |
| east | max | 60.0000 | 50.0000 | 80.138167 | 55.138167 |
| south | centroid | 50.0000 | 30.0000 | 78.944573 | 53.944573 |
| south | mean | 50.0000 | 30.0000 | 78.525523 | 53.525523 |
| south | max | 50.0000 | 40.0000 | 80.138167 | 55.138167 |
| north | centroid | 50.0000 | 70.0000 | 78.944573 | 53.944573 |
| north | mean | 50.0000 | 70.0000 | 78.525523 | 53.525523 |
| north | max | 50.0000 | 60.0000 | 80.138167 | 55.138167 |

**nlayer_dbc**: T_f = 65.00 °C, T_1d = 84.526942 °C, scale = 81.051535 K (source d2), 1 % of scale = 0.8105 K; remainder modes 2738 × 1783

| source | point | x [mm] | y [mm] | T [°C] | rise T − T_f [K] |
|---|---|---|---|---|---|
| d1 | centroid | 20.0000 | 18.0000 | 146.261860 | 81.261860 |
| d1 | mean | 20.0000 | 18.0000 | 135.920056 | 70.920056 |
| d1 | max | 20.1685 | 17.9825 | 146.365288 | 81.365288 |
| d2 | centroid | 31.0000 | 18.0000 | 165.548219 | 100.548219 |
| d2 | mean | 31.0000 | 18.0000 | 150.639001 | 85.639001 |
| d2 | max | 30.8952 | 17.9870 | 165.578477 | 100.578477 |
| d3 | centroid | 55.0000 | 36.0000 | 153.160567 | 88.160567 |
| d3 | mean | 55.0000 | 36.0000 | 140.102101 | 75.102101 |
| d3 | max | 55.0085 | 36.0107 | 153.161251 | 88.161251 |
| d4 | centroid | 79.5000 | 49.0000 | 156.446522 | 91.446522 |
| d4 | mean | 79.5000 | 49.0000 | 145.005419 | 80.005419 |
| d4 | max | 79.6291 | 49.0903 | 156.522169 | 91.522169 |

For a `mean` row, x and y are the source centroid; the value is the mean over the source rectangle.

## 7. Consequences for E006 and open items
- **Resolved (founder decision 2026-11-02, applied in T0164): the Case 1a/1b 50-term gate.** F1 in the frozen
  objective requires only "the paper's printed Case 3 values to their printed digits", and that passes. The T0151
  packet had added the Case 1a/1b centroids, and three of those four cannot be reproduced (5.2). Option (a) below was
  chosen: `GATED_PRINTED` now holds the two Case 3 values, and the Case 1a/1b comparisons are INFO. The options T0151
  put to the planner or founder were:
  - (a) Align the packet with F1: gate Case 3 and report Case 1a/1b as information. This is a one-line change to
    `GATED_PRINTED`, made under a new attempt.
  - (b) Replace it with a converged-value check, e.g. the converged Case 1b centroids within a stated tolerance of
    Table 2. The tolerance must be justified before anyone looks at the numbers again; I have already seen them.
  - (c) Keep it, and accept that the reference cannot pass.

  I recommend (a). The converged values do not depend on this gate, and `series_values.json` would be byte-identical
  under (a).

  [fact] Under (a), `--selfcheck` exits 0 and `series_values.json` is unchanged (same payload sha256), as T0151
  predicted. No converged-value tolerance against Tables 1-2 (option b) was added.
- **A1 and A2 tolerances.** Every case scale is above 5 K: 1 % gives 0.56 (case1a), 0.069 (case1b), 0.069 (case2),
  0.051 (case3) and 0.81 K (nlayer). A2's 0.05 K binds first in every case. Case 3 is the nearest to A1 binding
  (0.0511 K).
- **Maxima on source edges.** In Case 3 the maxima of the four arm sources lie on the edge they share with the centre
  source, at (40, 50) mm and the symmetric points. At a uniform-flux edge the surface field's second derivative is
  log-singular. [inference] The L2's bilinear interpolation of the reconstructed surface temperature at such a point
  converges more slowly than second order, so A4's observed-order rule is likely to fall back to F_s = 3 there.
- **Case 2 means and the F1 scikit-fem check (E006).** In the S59 scratch FE, the centroids agree with these
  references to 0.0012 K but the means differ by 0.008–0.021 K. The references' means are cross-checked here by raw
  sums (≤ 5e-7), reciprocity and the face mean. [inference] The FE's means were probably formed by nodal averaging on
  a 0.5 mm grid. E006's 0.02 K F1 agreement check should integrate the FE field exactly over each source, or the
  check may fail for reasons unrelated to either code.
- **Freezing.** F1 requires the references frozen before the first solver comparison. The JSON's payload hash is
  given in the header (`befc5efa…0667151`), and E006 freezes it. The N-layer layer values that E006's L2 case needs are
  in 4.1. Because the payload contains them (`layers_bottom_up`), any later change to `moduleforge.geometry.stack`
  constants would show up as a hash change on re-emit. Any change to a case, a parameter or the code's numerics changes the hash and needs a new
  experiment id after the first comparison.
- **Not done here (out of scope):** the comparison with the L2 or scikit-fem, the manufactured case, and k(T).
