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
* Diagnostics: the energy-balance residual, the solver's discretisation error estimate (Richardson/GCI over three
  grids), and the Picard residual.

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
