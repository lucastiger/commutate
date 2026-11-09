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

from moduleforge.drc import DesignRules, check, measure_rules
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
    """Checks only that generate()'s DRC filter is applied: ``check`` is the same function the generator filters with, so
    this is NOT independent evidence of manufacturability (the DRC's own tests, tests/unit/drc, carry that)."""
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
        vec = D.params_of(lay).to_vector()
        lateral = vec[4:D.N_COPPER_PARAMS]  # copper, dies, landing lines: lateral values in mm after the four topology flags
        assert np.all(np.abs(lateral / 0.5 - np.round(lateral / 0.5)) < 1e-9)
        # wire feet and landings (T0273) are on the finer 0.125 mm grid, as absolute positions
        for w in lay.wires:
            pts = np.array([w.points[0, :2], w.points[-1, :2]]) * 1e3
            assert np.all(np.abs(pts / 0.125 - np.round(pts / 0.125)) < 1e-6)


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


def test_housing_feasible_set_is_exactly_five_sequence_variants():
    """70 x 40 housing, default rules: the generator yields exactly five (orientation, sequence, merge) variants, all with
    the HS pair at lower v and u = x.  (400 draws, seed 4; the other 11 are excluded by the terminal pads: with the LS pair
    first the DC+ column would have to cross the DC- pad, see the module docstring.)"""
    hb = D.halfbridge_housing_spec(3)
    got = Counter()
    for lay in D.generate(hb, 400, seed=4):
        seq = tuple(f"{n}{'d' if r == 'die' else 'l'}" for n, r, _ in D.params_of(lay).sequence())
        o, _, merge = D.topology_of(lay).split("/")
        got[(o, seq, merge)] += 1
    assert set(got) == {
        ("x", ("PHASEl", "DC+d", "PHASEd", "DC-l"), "split"), ("x", ("DC+d", "PHASEl", "DC-l", "PHASEd"), "split"),
        ("x", ("PHASEl", "DC+d", "DC-l", "PHASEd"), "split"), ("x", ("DC+d", "PHASEl", "PHASEd", "DC-l"), "split"),
        ("x", ("DC+d", "PHASEl", "PHASEd", "DC-l"), "merged")}, got


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


KEEPOUT_NETS = {"SIG_HS_G": GATE_HS, "SIG_HS_KS": KELVIN_HS, "SIG_LS_G": GATE_LS, "SIG_LS_KS": KELVIN_LS}


def case4_reference_params():
    """The Case 4 reference as a Params vector.  Wire feet (mm): the reference's bond points are at x = 29.125 / 40.125
    (die 1 / die 2) and y = 73.125 (HS) / 35.125 (LS), landing at x = same, y = 57.125 (HS) / 47.125 (LS).  Source pad
    centre of the die at (cx, cy): (cx + 0.085, cy - 0.4); die centres x = 30 / 40, y = 75 (HS) / 35 (LS)."""
    return D.Params(
        orient=0, hs_first=0, hs_die_first=0, ls_die_first=1,
        cols=((10, 55, 20, 80), (10, 10, 20, 50), (55, 30, 65, 98)),  # DC+ (T10), DC- (T9), PHASE (T11)
        slots=((25, 30, 55, 40), (20, 45, 52, 50), (25, 55, 55, 60), (20, 70, 52, 80)),  # T3, T4, T5, T6
        rows=((28, 72, 6), (28, 32, 6)), land=(57.0, 47.0),
        # (fu0, fud, pitch, fv, land_du, land_dv) per row: fu0 = 29.125 - 30.085, fud = (40.125 - 40.085) - fu0 = 1.0
        feet=((29.125 - 30.085, 1.0, 0.0, 73.125 - 74.6, 0.0, 0.125), (29.125 - 30.085, 1.0, 0.0, 35.125 - 34.6, 0.0, 0.125)),
        sigfeet=((0.0, 0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 0.0)))


def case4_reference_spec(c4):
    """The reference as the reconstruction has it: no gate / Kelvin pads on the dies, hence no signal wires (M1 / M2)."""
    return D.spec_from_layout(_load_case4().build("base"), c4.rules, KEEPOUT_NETS)


def test_case4_reference_is_in_the_parameter_space(c4):
    """The reference's own copper, dies and power wires (start and end within 1e-6 m) are a Params vector: the twin
    construction needs this (T0271 findings 2 and 4)."""
    lay = D.build(case4_reference_spec(c4), case4_reference_params())
    base = _load_case4().build("base")
    for net in NETS:
        a = next(t.polygon for t in lay.traces if t.net == net)
        b = next(t.polygon for t in base.traces if t.net == net)
        assert a.symmetric_difference(b).area < 1e-12
    assert sorted((round(d.cx, 6), round(d.cy, 6), d.switch) for d in lay.dies) == sorted(
        (round(d.cx, 6), round(d.cy, 6), d.switch) for d in base.dies)
    assert len(lay.wires) == len(base.wires) == 4
    key = lambda w: (round(w.points[0, 0], 6), round(w.points[0, 1], 6))  # noqa: E731
    for a, b in zip(sorted(lay.wires, key=key), sorted(base.wires, key=key), strict=True):
        assert np.abs(a.points[0] - b.points[0]).max() < 1e-6 and np.abs(a.points[-1] - b.points[-1]).max() < 1e-6
        assert a.net == b.net and a.diameter == b.diameter and a.loop_height == b.loop_height
        assert a.length == pytest.approx(b.length, abs=1e-6)  # the reference's wire lengths 12.2 mm (LS) / 16.15 mm (HS)
    assert check(lay, c4.rules) == []


def test_old_fixed_foot_rule_misses_the_reference_wires(c4):
    """Why the feet are parameters: the former rule (pad centre, 25 % shift) put the Case 4 wires 0.96 mm / 0.35-0.6 mm off."""
    ref = case4_reference_params()
    h = 4.5  # source pad height, mm; the old rule moved the foot 25 % of it towards the landing line (HS: down, LS: up)
    centred = dataclasses.replace(ref, feet=((0.0, 0.0, 0.0, -0.25 * h, 0.0, 0.0), (0.0, 0.0, 0.0, 0.25 * h, 0.0, 0.0)))
    lay, base = D.build(case4_reference_spec(c4), centred), _load_case4().build("base")
    off = max(np.abs(a.points[0, :2] - b.points[0, :2]).max() for a, b in zip(
        sorted(lay.wires, key=lambda w: (w.points[0, 0], w.points[0, 1])),
        sorted(base.wires, key=lambda w: (w.points[0, 0], w.points[0, 1])), strict=True))
    assert off > 0.9e-3


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


# ------------------------------------------------------------------------------------- multi-wire dies (T0271 finding 0)
@pytest.mark.parametrize("k", [2, 3])
def test_case4_multi_wire_dies_default_rules(c4, k):
    """2 and 3 power wires per die with the fixed gate / Kelvin copper: DRC-valid, no RuntimeError.  Needs the feet to be
    parameters: the gate / Kelvin wires of the LS dies run straight over the source pad at x = 29 / 31 mm, which left the
    old centred feet 0.415 / 0.585 mm from them (< 0.6 mm)."""
    spec = dataclasses.replace(c4, wires_per_die=k)
    lays = D.generate(spec, 12, seed=20 + k)
    for lay in lays:
        assert check(lay, spec.rules) == []
        assert len(lay.wires) == 4 * k and len(lay.signal_wires) == 8
    # the k wires of a die are spread over the pad at the pitch of the parameter, >= the 0.6 mm rule
    for lay in lays:
        p = D.params_of(lay)
        for row in p.feet:
            assert row[2] >= 0.6 - 1e-9
    assert len({D.params_of(x).feet for x in lays}) > 1  # the feet are searched, not fixed


def _pad_v_and_u(spec, pad):
    x0, y0, x1, y1 = spec.die.pads[pad]
    return (x0 * 1e3, x1 * 1e3), (y0 * 1e3, y1 * 1e3)  # relative to the die centre, mm


def test_case4_min_wire_pitch_2mm_is_geometrically_infeasible(c4):
    """With a 2 mm minimum wire pitch Case 4 (assumed gate / Kelvin pads) admits no layout; the numbers:

    The LS dies' gate and Kelvin wires start in their 1 x 1 mm pads (feet >= 0.15 mm inside the edge) and run straight along
    y over the source pad to the copper below the die.  A power wire foot lies in the source pad, whose y range is inside the
    signal wires' y range, so its distance to the nearer signal wire is at most |u_foot - u_signal|.  The two signal wires
    are at most (kelvin_max - gate_min) apart in x, so the best foot is midway: (kelvin_max - gate_min) / 2 = 1.35 mm < 2 mm.
    Hence 1 or 2 wires per die cannot meet the pitch (3 wires do not even fit the 3.2 mm of pad: 4 mm needed)."""
    rules = dataclasses.replace(c4.rules, min_wire_pitch=2e-3)
    ms = max(rules.wire_start_margin, c4.signal_wire_diameter / 2) * 1e3  # 0.15 mm
    (g0, g1), (gv0, _) = _pad_v_and_u(c4, "gate")
    (k0, k1), _ = _pad_v_and_u(c4, "kelvin")
    (s0, s1), (sv0, sv1) = _pad_v_and_u(c4, "source")
    # the LS signal copper lies entirely below the source pad (so the signal wires cross the pad's whole y range)
    ls_top = max(t.polygon.bounds[3] for t in c4.keepouts if t.net in (GATE_LS, KELVIN_LS)) * 1e3
    ls_pad_bottom = 35.0 + sv0  # Case 4 LS dies are centred at y = 35 mm: source pad from y = 32.35 mm
    assert ls_top < ls_pad_bottom  # 28 mm < 32.35 mm
    assert gv0 + ms > sv1 - ms  # the signal feet are above the power feet's whole range
    best = ((k1 - ms) - (g0 + ms)) / 2
    assert best == pytest.approx(1.35, abs=1e-9) and best < rules.min_wire_pitch * 1e3
    # the generator agrees: RuntimeError (every draw rejected), in 3000 draws
    for k in (1, 2):
        with pytest.raises(RuntimeError):
            D.generate(dataclasses.replace(c4, wires_per_die=k, rules=rules), 1, seed=1, max_failures=3000)
    # 3 wires need 2 x 2 mm between the outer feet; the pad offers (3.5 - 2 x 0.15) mm = 3.2 mm
    need, have = 2 * 2.0, (s1 - s0) - 2 * (max(rules.wire_start_margin, c4.wire_diameter / 2) * 1e3)
    assert need > have
    with pytest.raises(ValueError, match="do not fit"):
        dataclasses.replace(c4, wires_per_die=3, rules=rules)


# ------------------------------------------------------------ diversity under the reference's own rules (T0271 finding 1)
def case4_measured_spec(c4):
    """Case 4 under ``measure_rules(reference)``.  Measured values used as they are: edge margin 5 mm, power width 5 mm,
    die spacing 6 mm, die edge margin 2 mm, spacing DC+/PHASE 3 mm, PHASE/DC- 3 mm, DC+/DC- 5 mm, other (signal copper) 2 mm.
    Replaced where measure_rules has no meaningful value: (a) ``max_wire_length``: measure_rules does not measure it (default
    15 mm, which the reference's own 16.15 mm wires violate), set to the reference's longest power wire; (b) wire pitch: the
    measured 10 mm / 33 diameters is the distance between wires of different dies, there is no second wire on a die: the
    defaults 0.6 mm / 2 diameters are kept; (c) gate / Kelvin wire limits: 25 mm as everywhere else (the files give none)."""
    base = _load_case4().build("base")
    measured, rec = measure_rules(base)
    assert rec["min_wire_pitch"] == pytest.approx(10e-3) and rec["n_signal_wires"] == 0
    longest = max(w.length for w in base.wires)
    assert longest == pytest.approx(16.151e-3, abs=1e-6)
    default = DesignRules()
    rules = dataclasses.replace(
        measured, max_wire_length=np.ceil(longest * 1e9) / 1e9, min_wire_pitch=default.min_wire_pitch,
        wire_pitch_diameters=default.wire_pitch_diameters, max_gate_wire_length=MAX_SIGNAL_WIRE_MM * 1e-3,
        max_kelvin_wire_length=MAX_SIGNAL_WIRE_MM * 1e-3)
    assert check(base, dataclasses.replace(rules, max_gate_wire_length=None, max_kelvin_wire_length=None)) == []
    pads = {k: v for k, v in c4.die.pads.items() if k in ("gate", "kelvin")}
    return D.spec_from_layout(base, rules, KEEPOUT_NETS, extra_pads=pads)


def _sequence_name(p):
    return tuple(f"{n}{'d' if r == 'die' else 'l'}" for n, r, _ in p.sequence())


def orient0_windows(spec):
    """Necessary conditions on the die positions (mm; orientation 0, bands across y) per band sequence.

    Every band must reach the wires' x range (28..44 mm), where the fixed signal copper strips lie (GATE_LS y <= 28, KELVIN_LS
    y <= 18, GATE_HS y >= 82, KELVIN_HS y >= 93), so all bands lie between ``zone_lo`` = GATE_LS top + spacing and
    ``zone_hi`` = GATE_HS bottom - spacing.  A die's gate / Kelvin wire is at least the distance from its foot (>= the start
    margin inside the pad) to the landable copper (wire_landing_margin inside the strip).  y_LS / y_HS: lower edge of the dies."""
    r = spec.rules
    mm = 1e3
    dv, dem, lm, ms = spec.die.h * mm, r.die_edge_margin * mm, r.wire_landing_margin * mm, \
        max(r.wire_start_margin, spec.signal_wire_diameter / 2) * mm
    cu = {t.net: t.polygon.bounds for t in spec.keepouts}
    (_, _), (kv0, kv1) = _pad_v_and_u(spec, "kelvin")
    pad_lo, pad_hi = kv0 + dv / 2 + ms, kv1 + dv / 2 - ms  # foot range above the die's lower edge (gate pad = Kelvin pad row)
    lim = {"gate": r.max_gate_wire_length * mm, "kelvin": r.max_kelvin_wire_length * mm}
    y_ls_max = min(lim[p] + (cu[n][3] * mm - lm) - pad_lo for p, n in (("gate", GATE_LS), ("kelvin", KELVIN_LS)))
    y_hs_min = max((cu[n][1] * mm + lm) - lim[p] - pad_hi for p, n in (("gate", GATE_HS), ("kelvin", KELVIN_HS)))
    zone_lo = cu[GATE_LS][3] * mm + r.spacing_for("PHASE", GATE_LS) * mm
    zone_hi = cu[GATE_HS][1] * mm - r.spacing_for("PHASE", GATE_HS) * mm
    w = r.width_for("PHASE") * mm
    sp_pd, sp_pc = r.spacing_for("PHASE", "DC-") * mm, r.spacing_for("PHASE", "DC+") * mm
    return {"y_ls_max": y_ls_max, "y_hs_min": y_hs_min, "zone_lo": zone_lo, "zone_hi": zone_hi,
            "y_ls_min": {1: zone_lo + dem, 0: zone_lo + w + sp_pd + dem},  # by ls_die_first: [PHASEd, DC-l] / [DC-l, PHASEd]
            "y_hs_max": {0: zone_hi - dem - dv, 1: zone_hi - w - sp_pc - dem - dv}}  # by hs_die_first: [PHASEl, DC+d] / [DC+d, PHASEl]


def test_case4_topology_diversity_under_measured_rules(c4):
    """Case 4 under the reference's own rules: 2 of the 8 band sequences (x 2 orientations x merge variants) are feasible.

    Feasible (found by the generator and DRC-clean; split only, orientation x): the reference's own
    [PHASEd, DC-l, PHASEl, DC+d] and [PHASEd, DC-l, DC+d, PHASEl] (PHASE landing band above the HS die band).  Excluded:
    * LS pair [DC-l, PHASEd] (2 sequences): the DC- landing band (>= 5 mm, 3 mm from PHASE, 2 mm above the GATE_LS strip)
      pushes the LS dies to y >= 40 mm, but the Kelvin wire (25 mm to KELVIN_LS) needs y <= 37.75: short by 2.25 mm
      (max_kelvin_wire_length).
    * HS pair first (4 sequences): the HS dies must be at y >= 62.65 mm (Kelvin wire to KELVIN_HS) and the LS dies at
      y <= 37.75 mm, so the HS pair cannot be below the LS pair: short by 24.9 mm (max_kelvin_wire_length).
    * orientation y (u = y, all 8): not excluded by a closed form here; sampled, see the last test.
    The window of the second sequence is narrow: HS dies y in [62.65, 64.0] mm, 1.35 mm of slack (it is at the PHASE
    landing band's upper edge: spacing to GATE_HS).  Rules are not loosened to create diversity."""
    spec = case4_measured_spec(c4)
    r = spec.rules
    for name, want in (("edge_margin", 5e-3), ("min_width_power", 5e-3), ("die_spacing", 6e-3), ("die_edge_margin", 2e-3),
                       ("spacing_dcp_phase", 3e-3), ("spacing_phase_dcm", 3e-3), ("spacing_dcp_dcm", 5e-3),
                       ("spacing_other", 2e-3)):
        assert getattr(r, name) == pytest.approx(want, abs=2e-6), name
    w = orient0_windows(spec)
    assert (w["y_ls_max"], w["y_hs_min"], w["zone_lo"], w["zone_hi"]) == pytest.approx((37.75, 62.65, 30.0, 80.0), abs=1e-3)  # measured widths are bisected to 1 um

    lays = D.generate(spec, 250, seed=5)
    found = Counter((D.topology_of(x).split("/")[0], _sequence_name(D.params_of(x)), D.topology_of(x).split("/")[2])
                    for x in lays)
    s1 = ("x", ("PHASEd", "DC-l", "PHASEl", "DC+d"), "split")
    s2 = ("x", ("PHASEd", "DC-l", "DC+d", "PHASEl"), "split")
    assert set(found) == {s1, s2}, found
    for lay in lays:
        assert check(lay, r) == []

    # analytic bounds for every orientation-0 sequence: feasible iff both die windows are non-empty and the pairs are in y order
    feasible, margins = set(), {}
    for hs_first in (0, 1):
        for hs_die_first in (0, 1):
            for ls_die_first in (0, 1):
                seq = _sequence_name(D.Params(0, hs_first, hs_die_first, ls_die_first, (), (), (), (), (), ()))
                ls_slack = w["y_ls_max"] - w["y_ls_min"][ls_die_first]
                hs_slack = w["y_hs_max"][hs_die_first] - w["y_hs_min"]
                order_slack = (w["y_ls_max"] - w["y_hs_min"]) if hs_first else float("inf")  # HS dies below LS dies
                margins[seq] = (ls_slack, hs_slack, order_slack)
                if min(ls_slack, hs_slack, order_slack) >= 0:
                    feasible.add(seq)
    assert feasible == {s1[1], s2[1]}
    assert margins[s1[1]][:2] == pytest.approx((5.75, 9.35), abs=1e-3)
    assert margins[s2[1]][:2] == pytest.approx((5.75, 1.35), abs=1e-3)
    for seq, (ls_slack, _hs_slack, order_slack) in margins.items():
        if seq[0] == "DC-l":  # LS pair [DC-l, PHASEd]
            assert ls_slack == pytest.approx(-2.25, abs=1e-3)
        if seq[0] in ("PHASEl", "DC+d"):  # HS pair first
            assert order_slack == pytest.approx(-24.9, abs=1e-3)


def test_case4_orientation_y_has_no_candidate_under_measured_rules(c4):
    """Orientation y (dies in rows along y) is excluded by sampling, not by a closed form: of the orientation-y candidates
    drawn, none has copper that is both inside its free region and spaced by the rules, and the best has a gate / Kelvin
    wire more than 5 mm over the 25 mm limit (14.9 mm in a 60 000-draw scratch run)."""
    spec = case4_measured_spec(c4)
    cx = D._Ctx(spec)
    rng = np.random.default_rng(1)
    n = clean = 0
    best = np.inf
    for _ in range(12000):
        p = D._sample(spec, cx, rng)
        if p is None or p.orient != 1:
            continue
        try:
            lay = D.build(spec, p)
        except ValueError:
            continue
        n += 1
        clean += D._quick_ok(spec, cx, lay)
        best = min(best, max(w.length for w in lay.signal_wires) - MAX_SIGNAL_WIRE_MM * 1e-3)
    assert n >= 50 and clean == 0
    assert best > 5e-3, best


def test_fingerprints_identical_across_processes():
    """Same seed, same fingerprints in two separate interpreters (2 wires per die, so the foot draws are exercised)."""
    import subprocess
    code = (
        "import sys; sys.path.insert(0, %r); import dataclasses, test_derivative as T; from moduleforge.generate import "
        "derivative as D; s = dataclasses.replace(T.case4_spec(), wires_per_die=2); "
        "print(*[x.fingerprint() for x in D.generate(s, 3, seed=11)])" % str(Path(__file__).parent))
    outs = [subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True).stdout.split()
            for _ in range(2)]
    assert len(outs[0]) == 3 and outs[0] == outs[1]
    here = [x.fingerprint() for x in D.generate(dataclasses.replace(case4_spec(), wires_per_die=2), 3, seed=11)]
    assert outs[0] == here
