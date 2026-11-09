"""Tests of the derivative-layout generator (T0258) on the 70 x 40 mm generator housing and on PowerSynth 2D_Case_4.

Case 4 is loaded by path from research/scripts/o006_case4_layout.py (geometry facts only).  Its gate and Kelvin wires are
not in the reference: the SIG_* traces are the keep-outs (renamed to GATE_* / KELVIN_*), the die gate / Kelvin pads are an
ASSUMED 1 x 1 mm pair in the strip above the source pad, and the maximum signal-wire length is an ASSUMED 25 mm.
"""
import dataclasses
import importlib.util
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np
import pytest

from moduleforge.drc import DesignRules, check
from moduleforge.generate import derivative as D
from moduleforge.geometry import GATE_HS, GATE_LS, KELVIN_HS, KELVIN_LS, NETS
from moduleforge.physics.peec import loop_inductance
from moduleforge.solvers import l2_layout as L2
from moduleforge.solvers import thermal_fem as F

ROOT = Path(__file__).resolve().parents[3]
MAX_SIGNAL_WIRE_MM = 25.0  # assumed (Case 4 files give none)


def _load_case4():
    path = ROOT / "research" / "scripts" / "o006_case4_layout.py"
    sp = importlib.util.spec_from_file_location("o006_case4_layout_for_test", path)
    mod = importlib.util.module_from_spec(sp)
    sys.modules[sp.name] = mod
    sp.loader.exec_module(mod)
    return mod


def case4_spec():
    c4 = _load_case4()
    # max_wire_length 18 mm (assumed): the reference's own power wires are 12 mm (LS) and 16 mm (HS) long
    rules = DesignRules(max_wire_length=18e-3, max_gate_wire_length=MAX_SIGNAL_WIRE_MM * 1e-3,
                        max_kelvin_wire_length=MAX_SIGNAL_WIRE_MM * 1e-3)
    rel = lambda r: tuple(v * 1e-3 for v in (r[0] - 2, r[1] - 3, r[2] - 2, r[3] - 3))  # noqa: E731 (die 4 x 6 mm)
    return D.spec_from_layout(
        c4.build("base"), rules,
        {"SIG_HS_G": GATE_HS, "SIG_HS_KS": KELVIN_HS, "SIG_LS_G": GATE_LS, "SIG_LS_KS": KELVIN_LS},
        extra_pads={"gate": rel((0.5, 4.8, 1.5, 5.8)), "kelvin": rel((2.5, 4.8, 3.5, 5.8))})


@pytest.fixture(scope="module")
def c4():
    return case4_spec()


@pytest.fixture(scope="module")
def hb():
    return D.halfbridge_housing_spec(3)


@pytest.fixture(scope="module")
def c4_layouts(c4):
    return D.generate(c4, 200, seed=7)


@pytest.fixture(scope="module")
def hb_layouts(hb):
    return D.generate(hb, 60, seed=3)


def test_determinism(c4, hb):
    for spec in (c4, hb):
        a = [x.fingerprint() for x in D.generate(spec, 12, seed=11)]
        assert a == [x.fingerprint() for x in D.generate(spec, 12, seed=11)]
        assert a != [x.fingerprint() for x in D.generate(spec, 12, seed=12)]
    # the first layout depends on the seed only, not on how many are requested
    assert D.generate(hb, 1, seed=5)[0].fingerprint() == D.generate(hb, 4, seed=5)[0].fingerprint()


def test_drc_clean_under_spec_rules(c4, hb, c4_layouts, hb_layouts):
    assert len(c4_layouts) == 200 and len(hb_layouts) == 60
    for spec, lays in ((c4, c4_layouts), (hb, hb_layouts)):
        for lay in lays:
            assert check(lay, spec.rules) == []
    # the Case 4 candidates carry signal wires from every gate and Kelvin pad, within the assumed limit
    for lay in c4_layouts[:20]:
        assert len(lay.signal_wires) == 2 * len(lay.dies)
        assert max(w.length for w in lay.signal_wires) <= MAX_SIGNAL_WIRE_MM * 1e-3 + 1e-9


def test_per_pair_spacing_and_width_rules_are_enforced(c4):
    """Stricter per-pair spacing / width classes of the spec are honoured by the generated copper."""
    rules = DesignRules(spacing_dcp_phase=2.5e-3, spacing_phase_dcm=2.0e-3, spacing_dcp_dcm=3.0e-3, min_width_power=2.0e-3,
                        max_wire_length=18e-3, max_gate_wire_length=25e-3, max_kelvin_wire_length=25e-3)
    spec = D.ReferenceSpec(**{**c4.__dict__, "rules": rules})
    for lay in D.generate(spec, 15, seed=2):
        assert check(lay, rules) == []
        p = {t.net: t.polygon for t in lay.traces}
        assert p["DC+"].distance(p["PHASE"]) >= 2.5e-3 - 1e-9
        assert p["PHASE"].distance(p["DC-"]) >= 2.0e-3 - 1e-9
        assert p["DC+"].distance(p["DC-"]) >= 3.0e-3 - 1e-9


def _on_lattice(lay, refinement):
    cm = lay.to_conductors()
    lat = L2.layout_lattice(cm, refinement)
    fill = L2.cell_fill(cm, *lat)  # ValueError if a feature is off the lattice or two nets share a cell
    for d in cm.shorts:
        L2.check_on_lattice(d.x - d.w / 2, d.x + d.w / 2, d.y - d.h / 2, d.y + d.h / 2, *lat[:4], "die")
    return max(abs(rep - ex) / ex for rep, ex in fill["area"].values())


def test_on_l2_lattice_at_0p5_and_0p25_mm(c4_layouts, hb_layouts):
    for lay in c4_layouts[:25] + hb_layouts[:25]:
        for refinement in (0, 1):  # CELL = 0.5 mm, 0.25 mm
            assert _on_lattice(lay, refinement) < 1e-12


def test_every_lateral_parameter_on_the_design_grid(c4_layouts):
    for lay in c4_layouts[:30]:
        vec = D.params_of(lay).to_vector()[4:]  # everything after the four topology flags is lateral, in mm
        assert np.all(np.abs(vec / 0.5 - np.round(vec / 0.5)) < 1e-9)


def test_thermal_layout_grid_level0_accepts_every_candidate(c4_layouts, hb_layouts):
    for lay in c4_layouts[:15] + hb_layouts[:15]:
        F.layout_grid(lay, 10.0, 5000.0, 300.0, F.GridRule(), 0)


def test_l1_finite_positive_on_case4_candidates(c4_layouts):
    for lay in c4_layouts[:6]:
        L = loop_inductance(lay, 20e6).L_H[0]
        assert np.isfinite(L) and L > 0.0
        assert L < 1e-6  # nH-scale loop, not a unit error


def test_at_least_three_topologies_among_200_case4(c4_layouts):
    tops = Counter(D.topology_of(x) for x in c4_layouts)
    assert len(tops) >= 3, tops


def test_housing_covers_all_sequences_and_merged_variants(hb_layouts):
    seqs = {D.params_of(x).sequence().__repr__() for x in hb_layouts}
    assert len(seqs) >= 4
    assert any(D.topology_of(x).endswith("merged") for x in hb_layouts)
    assert any(D.topology_of(x).endswith("split") for x in hb_layouts)


def test_params_round_trip_exact(c4_layouts, hb_layouts, c4, hb):
    for spec, lays in ((c4, c4_layouts), (hb, hb_layouts)):
        for lay in lays:
            p = D.params_of(lay)
            assert D.Params.from_vector(p.to_vector()) == p
            again = D.build(spec, p)
            assert D.params_of(again) == p  # params -> Layout -> params
            assert again.fingerprint() == lay.fingerprint()  # and the builder reproduces the layout bit for bit
            assert D.params_of(again).to_vector().tolist() == p.to_vector().tolist()


def test_fixed_items_byte_identical_to_the_spec(c4, c4_layouts, hb, hb_layouts):
    for spec, lays in ((c4, c4_layouts), (hb, hb_layouts)):
        for lay in lays:
            assert lay.outline.equals_exact(spec.outline, 0) and lay.baseplate_outline.equals_exact(
                spec.baseplate_outline, 0)
            assert lay.stack == spec.stack and lay.backside_inset == spec.backside_inset
            assert lay.terminals == spec.terminals
            fixed = [t for t in lay.traces if t.net not in NETS]
            assert len(fixed) == len(spec.keepouts)
            for t, k in zip(fixed, spec.keepouts, strict=True):
                assert t.net == k.net and t.polygon.equals_exact(k.polygon, 0)
            n = spec.dies_per_switch
            assert lay.dies_per_switch == n and len(lay.dies) == 2 * n
            assert [d.switch for d in lay.dies] == ["HS"] * n + ["LS"] * n
            for d in lay.dies:
                assert (d.w, d.h, d.thickness, d.attach_thickness) == (spec.die.w, spec.die.h, spec.die.thickness,
                                                                       spec.die.attach_thickness)
                for name, r in spec.die.pads.items():
                    got = tuple(np.array(d.pads[name]) - np.array([d.cx, d.cy, d.cx, d.cy]))
                    assert np.allclose(got, r, atol=1e-12, rtol=0)
                assert set(d.pads) == set(spec.die.pads)
            assert len(lay.wires) == n * 2 * spec.wires_per_die
            assert {w.diameter for w in lay.wires} == {spec.wire_diameter}
            assert {w.loop_height for w in lay.wires} == {spec.loop_height}
            assert {w.diameter for w in lay.signal_wires} <= {spec.signal_wire_diameter}


def test_case4_spec_is_the_reference_dies_and_housing(c4):
    assert c4.dies_per_switch == 2 and c4.wires_per_die == 1
    assert (c4.die.w, c4.die.h) == (4e-3, 6e-3) and c4.die.thickness == pytest.approx(0.18e-3)
    assert c4.wire_diameter == pytest.approx(0.3e-3) and c4.loop_height == pytest.approx(1.0e-3)
    assert {k.net for k in c4.keepouts} == {GATE_HS, GATE_LS, KELVIN_HS, KELVIN_LS}
    assert c4.outline.bounds == pytest.approx((5e-3, 5e-3, 75e-3, 105e-3))


def test_case4_reference_is_in_the_parameter_space(c4):
    """The reference's own copper, dies and wires as a Params vector: the twin construction needs this."""
    ref = D.Params(
        orient=0, hs_first=0, hs_die_first=0, ls_die_first=1,
        cols=((10, 55, 20, 80), (10, 10, 20, 50), (55, 30, 65, 98)),  # DC+ (T10), DC- (T9), PHASE (T11)
        slots=((25, 30, 55, 40), (20, 45, 52, 50), (25, 55, 55, 60), (20, 70, 52, 80)),  # T3, T4, T5, T6
        rows=((28, 72, 6), (28, 32, 6)), land=(57.0, 47.0))
    lay = D.build(c4, ref)
    c4m = _load_case4()
    base = c4m.build("base")
    for net in NETS:
        a = next(t.polygon for t in lay.traces if t.net == net)
        b = next(t.polygon for t in base.traces if t.net == net)
        assert a.symmetric_difference(b).area < 1e-12
    assert sorted((round(d.cx, 6), round(d.cy, 6), d.switch) for d in lay.dies) == sorted(
        (round(d.cx, 6), round(d.cy, 6), d.switch) for d in base.dies)
    assert check(lay, c4.rules) == []


def test_halfbridge_housing_matches_generator_constants(hb):
    from moduleforge.generate import halfbridge as H
    assert hb.outline.bounds == pytest.approx((0, 0, 70e-3, 40e-3))
    for net, pad in H.PADS.items():
        t = hb.terminals[net]
        assert (t.cx, t.cy, t.w, t.h) == pytest.approx(
            tuple(v * 1e-3 for v in ((pad[0] + pad[2]) / 2, (pad[1] + pad[3]) / 2, pad[2] - pad[0], pad[3] - pad[1])))


def test_spec_validation():
    with pytest.raises(ValueError):
        D.ReferenceSpec(**{**D.halfbridge_housing_spec(2).__dict__, "wires_per_die": 12})  # does not fit the source pad
    base = D.halfbridge_housing_spec(2)
    off = D.DieSpec(5.1e-3, 5e-3, base.die.thickness, base.die.attach_thickness, base.die.pads)
    with pytest.raises(ValueError):
        D.ReferenceSpec(**{**base.__dict__, "die": off})  # footprint off the 0.5 mm grid
    with pytest.raises(ValueError):
        D.params_of(dataclasses.replace(D.generate(base, 1, 0)[0], family="side_by_side"))


@pytest.mark.slow
def test_throughput_case4(c4):
    t0 = time.perf_counter()
    lays = D.generate(c4, 200, seed=99)
    rate = len(lays) / (time.perf_counter() - t0)
    print(f"2D_Case_4: {rate:.1f} DRC-valid candidates / s")
    assert rate >= 5.0
