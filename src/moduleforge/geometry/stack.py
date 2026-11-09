"""Layer stack of a DBC/AMB power-module substrate.

Conventions (mf-conventions): SI units, float64, z = 0 at the *bottom of the baseplate*, layers are
listed bottom-up. The default values below are *typical* datasheet/design-guide values, intended as
cited defaults, and must be replaced by vendor data for a real customer module:

* Copper electrical conductivity 5.8e7 S/m: International Annealed Copper Standard (IEC 60028).
* Copper thermal conductivity ~385 W/(m K): CRC Handbook of Chemistry and Physics (401 W/mK for pure Cu
  at 300 K; ~385 typical for DBC/baseplate copper).
* Al2O3 (96 %) DBC ceramic: 0.38 mm thick, k ~ 24 W/(m K); Rogers/curamik and CeramTec DBC datasheets.
* Si3N4 AMB ceramic: 0.32 mm thick, k ~ 90 W/(m K); Rogers/curamik and Kyocera Si3N4 AMB datasheets.
* Substrate Cu: 0.30 mm on both faces (standard DBC/AMB copper thickness).
* Baseplate: 3 mm Cu (typical module baseplate).
* SAC305 solder: 0.1 mm, sigma ~ 7.7e6 S/m (rho ~ 13 uOhm cm), k ~ 58 W/(m K); Lead-free solder handbooks.
* Aluminium bond wire: pure Al rho = 2.65e-8 Ohm m -> 3.77e7 S/m (CRC); alloy bond wire is lower, 3.5e7 used.
* Die attach: 50 um SAC305 solder (same material and k(T) law as the substrate solder; sintered Ag, k ~ 100-250
  W/(m K) depending on porosity, is the usual SiC alternative and would be a different ``Layer.material``).
* Die: 180 um 4H-SiC, k = 370 W/(m K) at 300 K (Levinshtein, Rumyantsev, Shur, *Properties of Advanced
  Semiconductor Materials*, Wiley 2001, SiC chapter: 3.7 W/(cm K) for 4H-SiC at 300 K).

**Thermal conductivity k(T).** ``Layer.k`` is the value at ``T_REF`` = 300 K. ``Layer.k_at(T)`` returns
``Layer.k * f_material(T) / f_material(T_REF)``, with the material laws ``f`` below (``K_LAWS``), so a vendor value
stored in ``Layer.k`` keeps the cited temperature *dependence*. Every law is valid over ``K_T_MIN``..``K_T_MAX``
(273.15-523.15 K, which contains the required 290-480 K); outside that range ``k_at`` raises ValueError.

* Cu: linear, f = 1 - 1.995e-4 (T - 300 K). Incropera, DeWitt, Bergman, Lavine, *Fundamentals of Heat and Mass
  Transfer*, 6th/7th ed., Table A.1 (pure copper: 401 W/(m K) at 300 K, 393 at 400 K, 379 at 600 K); the slope is
  (393 - 401)/100/401 and the table's 400-600 K slope, (379 - 393)/200/401, is 12 % shallower, which changes k by
  < 0.2 % over 400-480 K.
* Al2O3: log-linear (piecewise power-law) interpolation of Incropera et al. Table A.2 (polycrystalline aluminium
  oxide: 36.0, 26.4, 15.8 W/(m K) at 300, 400, 600 K), so the law passes through the tabulated points: exponent
  ln(26.4/36)/ln(4/3) = -1.078 on 300-400 K (also used below 300 K) and ln(15.8/26.4)/ln(1.5) = -1.266 on 400-600 K.
  The 1/T trend is the phonon-Umklapp law of Slack, J. Phys. Chem. Solids 34, 321 (1973). The 96 % DBC grade follows
  the same relative law (its absolute value of 24 W/(m K) is the datasheet value in ``Layer.k``). (Review T0156: an
  earlier single exponent -1.15 rested on a misquoted 26 at 400 K and missed the table by 2 % there.)
* Si3N4: f = (T/300)^-1.0, the Umklapp-limited law of Slack (1973) for a dense, pure lattice; Hirosaki et al., Phys.
  Rev. B 65, 134110 (2002), find k ~ 1/T for high-conductivity beta-Si3N4. Medium confidence for commercial AMB grades.
* AlN: f = (T/300)^-1.0, the Umklapp-limited law of Slack, Tanzilli, Pohl, Vandersande, J. Phys. Chem. Solids 48, 641
  (1987), who measure k ~ 1/T above ~200 K for AlN single crystals (k(300 K) = 319 W/(m K) for the purest crystal, so
  k(400 K) = 239 and k(480 K) = 199 W/(m K) under the law). Sintered substrate AlN (typically 170-180 W/(m K), the value
  stored in ``Layer.k``) is limited by oxygen and grain-boundary scattering, whose share is temperature-independent, so its
  true slope is probably shallower than 1/T: the law then overstates the fall of k with T. Medium-low confidence for
  commercial grades (no sintered-AlN table was consulted); conservative for Tj (a hotter die sees a lower k).
* SAC305 (substrate solder and die attach): Wiedemann-Franz electronic conduction, k ~ L T sigma(T) with
  rho(T) = rho(300 K) [1 + alpha (T - 300 K)] and alpha = 4.2e-3 /K (CRC, temperature coefficient of resistivity of
  tin, 4.2-4.7e-3 /K), so f = (T/300) / (1 + 4.2e-3 (T - 300)). L = 2.44e-8 W Ohm/K^2 and rho = 13 uOhm cm reproduce
  k(300 K) = 56 W/(m K), within 4 % of the 58 stored in ``Layer.k``, so the law is a consistent shape for the
  datasheet value. Medium-low confidence in the slope (-8.9 % between 300 and 480 K): no primary SAC305 k(T) data
  were consulted.
* 4H-SiC: f = (T/300)^-1.49. The 3.7 (T/300)^-1.49 W/(cm K) form is the one used in TCAD material files (Silvaco
  Atlas / Synopsys Sentaurus SiC models after Levinshtein et al. 2001); the c-axis conductivity of real wafers
  varies 330-490 W/(m K) with doping and polytype.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

import numpy as np

SIGMA_CU = 5.8e7  # S/m, IACS
SIGMA_AL_WIRE = 3.5e7  # S/m, Al bond wire (CRC pure Al 3.77e7, alloy lower)
SIGMA_SOLDER = 7.7e6  # S/m, SAC305

LAYER_ORDER = ("baseplate", "solder", "backside_cu", "ceramic", "top_cu")

# Single source of the nominal die and die-attach thickness: the default stack's ``die`` / ``die_attach`` layers and
# the defaults of ``Die.thickness`` / ``Die.attach_thickness`` (geometry/layout.py) all read these.
DIE_THICKNESS = 180e-6  # m, typical SiC/IGBT die
DIE_ATTACH_THICKNESS = 50e-6  # m, typical solder/sinter die attach

T_REF = 300.0  # K, the reference temperature at which ``Layer.k`` is stated
K_T_MIN = 273.15  # K, validity range of every k(T) law (see module docstring)
K_T_MAX = 523.15  # K

AL2O3_TABLE = ((300.0, 36.0), (400.0, 26.4), (600.0, 15.8))  # K, W/(m K); Incropera et al. Table A.2


def _al2o3_law(T):
    """Log-linear interpolation of AL2O3_TABLE, normalised to 1 at 300 K (first segment extended below 300 K)."""
    T = np.asarray(T, dtype=float)
    (t0, k0), (t1, k1), (t2, k2) = AL2O3_TABLE
    a1 = np.log(k1 / k0) / np.log(t1 / t0)
    a2 = np.log(k2 / k1) / np.log(t2 / t1)
    return np.where(T <= t1, (T / t0) ** a1, (k1 / k0) * (T / t1) ** a2)


# Relative k(T) laws f_material(T) (module docstring has the citations); only the ratio f(T)/f(T_REF) is used.
K_LAWS: dict[str, Callable[[float], float]] = {
    "Cu": lambda T: 1.0 - 1.995e-4 * (T - 300.0),
    "Al2O3": _al2o3_law,
    "Si3N4": lambda T: (T / 300.0) ** -1.0,
    "AlN": lambda T: (T / 300.0) ** -1.0,
    "SAC305": lambda T: (T / 300.0) / (1.0 + 4.2e-3 * (T - 300.0)),
    "4H-SiC": lambda T: (T / 300.0) ** -1.49,
}


@dataclass(frozen=True)
class Layer:
    """One layer: thickness [m], electrical conductivity sigma [S/m], thermal conductivity k [W/(m K)].

    ``k`` is the conductivity at ``T_REF`` (300 K); ``k_at(T)`` applies the cited temperature law of the material."""

    name: str
    material: str
    thickness: float
    sigma: float
    k: float

    def k_at(self, T):
        """Thermal conductivity [W/(m K)] at temperature ``T`` [K] (scalar or array), valid 273.15-523.15 K.

        ``k * f(T) / f(T_REF)`` with the material law ``K_LAWS[material]`` (citations in the module docstring);
        KeyError for a material without a law, ValueError outside the validity range or for a non-finite T (a
        diverged Picard iterate must not pass silently, review T0156)."""
        T = np.asarray(T, dtype=float)
        if not np.all(np.isfinite(T)):
            raise ValueError("k(T) needs finite temperatures, got NaN or inf")
        if np.any(T < K_T_MIN) or np.any(T > K_T_MAX):
            raise ValueError(f"k(T) laws are valid for {K_T_MIN}-{K_T_MAX} K, got {T.min()}..{T.max()} K")
        f = K_LAWS[self.material]
        out = self.k * f(T) / f(T_REF)
        return float(out) if out.ndim == 0 else out


@dataclass(frozen=True)
class LayerStack:
    """Bottom-up layer stack; z = 0 at the bottom of the first (baseplate) layer.

    ``layers`` is the substrate stack (``LAYER_ORDER``). ``die_attach`` and ``die`` are the two layers above the
    top Cu (die-attach footprint, then die): they are *not* part of ``layers`` or ``total_thickness``, since they
    exist only under each die footprint. ``Die.thickness`` / ``Die.attach_thickness`` are the per-die thicknesses
    of the geometry and default to the thicknesses of these two layers (``DIE_THICKNESS``, ``DIE_ATTACH_THICKNESS``)."""

    layers: tuple[Layer, ...]
    kind: str = "custom"
    die_attach: Layer = field(
        default_factory=lambda: Layer("die_attach", "SAC305", DIE_ATTACH_THICKNESS, SIGMA_SOLDER, 58.0))
    die: Layer = field(default_factory=lambda: Layer("die", "4H-SiC", DIE_THICKNESS, 0.0, 370.0))

    def __post_init__(self):
        names = tuple(la.name for la in self.layers)
        if names != LAYER_ORDER:
            raise ValueError(f"layers must be {LAYER_ORDER} bottom-up, got {names}")
        if any(la.thickness <= 0 for la in self.layers):
            raise ValueError("layer thicknesses must be positive")
        if self.die_attach.thickness <= 0 or self.die.thickness <= 0:
            raise ValueError("layer thicknesses must be positive")

    def layer(self, name: str) -> Layer:
        for la in self.layers:
            if la.name == name:
                return la
        raise KeyError(name)

    def z_bottom(self, name: str) -> float:
        z = 0.0
        for la in self.layers:
            if la.name == name:
                return z
            z += la.thickness
        raise KeyError(name)

    def z_top(self, name: str) -> float:
        return self.z_bottom(name) + self.layer(name).thickness

    @property
    def total_thickness(self) -> float:
        return sum(la.thickness for la in self.layers)

    @property
    def conductive_plane_names(self) -> tuple[str, ...]:
        """Extended conductive planes that carry image currents (backside Cu and baseplate)."""
        return ("baseplate", "backside_cu")


def _stack(kind: str, ceramic: Layer) -> LayerStack:
    return LayerStack(
        (
            Layer("baseplate", "Cu", 3.0e-3, SIGMA_CU, 385.0),
            Layer("solder", "SAC305", 0.1e-3, SIGMA_SOLDER, 58.0),
            Layer("backside_cu", "Cu", 0.3e-3, SIGMA_CU, 385.0),
            ceramic,
            Layer("top_cu", "Cu", 0.3e-3, SIGMA_CU, 385.0),
        ),
        kind=kind,
    )


def default_dbc_stack() -> LayerStack:
    """Al2O3 DBC: 0.38 mm ceramic, k = 24 W/mK (see module docstring for sources)."""
    return _stack("DBC", Layer("ceramic", "Al2O3", 0.38e-3, 0.0, 24.0))


def default_amb_stack() -> LayerStack:
    """Si3N4 AMB: 0.32 mm ceramic, k = 90 W/mK (see module docstring for sources)."""
    return _stack("AMB", Layer("ceramic", "Si3N4", 0.32e-3, 0.0, 90.0))
