import pytest

from moduleforge.geometry import default_amb_stack, default_dbc_stack


@pytest.mark.parametrize("make,ceramic,t,k", [(default_dbc_stack, "Al2O3", 0.38e-3, 24.0),
                                              (default_amb_stack, "Si3N4", 0.32e-3, 90.0)])
def test_z_bookkeeping_bottom_up(make, ceramic, t, k):
    s = make()
    assert [la.name for la in s.layers] == ["baseplate", "solder", "backside_cu", "ceramic", "top_cu"]
    assert s.z_bottom("baseplate") == 0.0  # z = 0 at baseplate bottom
    # each layer starts where the previous one ends; total = sum of thicknesses
    for a, b in zip(s.layers[:-1], s.layers[1:], strict=True):
        assert s.z_top(a.name) == pytest.approx(s.z_bottom(b.name), rel=1e-12)
    assert s.z_top("top_cu") == pytest.approx(s.total_thickness, rel=1e-12)
    assert s.z_top("top_cu") == pytest.approx(3.0e-3 + 0.1e-3 + 0.3e-3 + t + 0.3e-3, rel=1e-12)
    assert s.layer("ceramic").material == ceramic and s.layer("ceramic").thickness == t
    assert s.layer("ceramic").k == k and s.layer("ceramic").sigma == 0.0
    assert s.layer("top_cu").sigma == pytest.approx(5.8e7)


def test_conductive_planes():
    assert default_dbc_stack().conductive_plane_names == ("baseplate", "backside_cu")


# --- thermal materials: die attach, SiC die, cited k(T) laws (T0148) -----------------------------------------------
import dataclasses  # noqa: E402

import numpy as np  # noqa: E402

from moduleforge.generate.halfbridge import generate_layouts  # noqa: E402
from moduleforge.geometry import Die, Layer  # noqa: E402
from moduleforge.geometry.stack import (  # noqa: E402
    DIE_ATTACH_THICKNESS,
    DIE_THICKNESS,
    K_LAWS,
    K_T_MAX,
    K_T_MIN,
    T_REF,
)


def _all_thermal_layers(s):
    return [*s.layers, s.die_attach, s.die]


@pytest.mark.parametrize("make", [default_dbc_stack, default_amb_stack])
def test_default_stack_has_die_attach_and_sic_die(make):
    s = make()
    assert (s.die_attach.material, s.die_attach.thickness, s.die_attach.k) == ("SAC305", 50e-6, 58.0)
    assert (s.die.material, s.die.thickness, s.die.k) == ("4H-SiC", 180e-6, 370.0)
    assert s.die.sigma == 0.0
    # the die layers sit above the top Cu and are not substrate layers: the substrate z bookkeeping is unchanged
    assert len(s.layers) == 5 and s.total_thickness == s.z_top("top_cu")


def test_die_thickness_single_source_of_truth():
    s = default_dbc_stack()
    d = Die(0, 0, 1e-3, 1e-3, "HS", {})
    assert d.thickness == s.die.thickness == DIE_THICKNESS
    assert d.attach_thickness == s.die_attach.thickness == DIE_ATTACH_THICKNESS
    for lay in generate_layouts(6, seed=7):
        assert {x.thickness for x in lay.dies} == {lay.stack.die.thickness}
        assert {x.attach_thickness for x in lay.dies} == {lay.stack.die_attach.thickness}


@pytest.mark.parametrize("make", [default_dbc_stack, default_amb_stack])
def test_every_thermal_material_has_a_law_and_k_at_reference_is_layer_k(make):
    for la in _all_thermal_layers(make()):
        assert la.material in K_LAWS
        assert la.k_at(T_REF) == pytest.approx(la.k, rel=1e-14)
        T = np.linspace(290.0, 480.0, 20)
        k = la.k_at(T)
        assert k.shape == T.shape and np.all(np.diff(k) < 0), la.material  # phonon/electron k falls with T
        assert np.all(k > 0.4 * la.k)  # no law collapses within the required range (SiC is -50 % at 480 K)


def test_k_at_matches_independent_tabulated_ratios():
    # Incropera et al. Table A.1/A.2 ratios to 300 K: Cu 393/401 at 400 K; Al2O3 26.4/36 at 400 K (the law interpolates
    # the table log-linearly, so it passes through the tabulated points exactly)
    s = default_dbc_stack()
    cu, al = s.layer("top_cu"), s.layer("ceramic")
    assert cu.k_at(400.0) / cu.k == pytest.approx(393.0 / 401.0, rel=1e-4)
    assert al.k_at(400.0) / al.k == pytest.approx(26.4 / 36.0, rel=1e-12)
    # 480 K on the 400-600 K segment, against the hand-computed log-linear interpolation of 26.4 and 15.8
    a2 = np.log(15.8 / 26.4) / np.log(600.0 / 400.0)
    assert al.k_at(480.0) / al.k == pytest.approx((26.4 / 36.0) * (480.0 / 400.0) ** a2, rel=1e-12)
    # Wiedemann-Franz closed form for SAC305, evaluated by hand at 400 K: (400/300)/(1 + 4.2e-3*100)
    assert s.layer("solder").k_at(400.0) == pytest.approx(58.0 * (4 / 3) / 1.42, rel=1e-12)
    # 4H-SiC: 3.7 W/(cm K) (T/300)^-1.49 at 450 K
    assert s.die.k_at(450.0) == pytest.approx(370.0 * 1.5 ** -1.49, rel=1e-12)


def test_k_at_rejects_non_finite_temperatures():
    la = default_dbc_stack().layer("ceramic")
    for bad in (float("nan"), float("inf"), np.array([350.0, np.nan])):
        with pytest.raises(ValueError):
            la.k_at(bad)


def test_k_at_scales_a_vendor_value_and_accepts_arrays():
    la = Layer("ceramic", "Si3N4", 0.32e-3, 0.0, 70.0)  # vendor value stated at T_REF
    assert la.k_at(360.0) == pytest.approx(70.0 * 300.0 / 360.0, rel=1e-14)
    assert np.allclose(la.k_at(np.array([300.0, 450.0])), [70.0, 70.0 * 300.0 / 450.0], rtol=1e-14)


def test_k_at_range_and_unknown_material():
    la = default_dbc_stack().die
    assert K_T_MIN <= 290.0 and K_T_MAX >= 480.0
    for T in (K_T_MIN - 1.0, K_T_MAX + 1.0):
        with pytest.raises(ValueError):
            la.k_at(T)
    with pytest.raises(KeyError):
        dataclasses.replace(la, material="unobtainium").k_at(300.0)


def test_die_layer_thickness_must_be_positive():
    s = default_dbc_stack()
    with pytest.raises(ValueError):
        dataclasses.replace(s, die=dataclasses.replace(s.die, thickness=0.0))
    with pytest.raises(ValueError):
        dataclasses.replace(s, die_attach=dataclasses.replace(s.die_attach, thickness=-1e-6))
