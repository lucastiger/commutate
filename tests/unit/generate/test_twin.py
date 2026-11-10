"""Tests of the generator-space twin and the degradation rule (T0259, O003 F1(a) / F1(b)).

Dev screens only: the real twin gate F1(a1) runs at 0.25 mm in E008.  Case 4 is loaded by path (geometry facts only); its
gate / Kelvin pads and the 25 mm signal-wire limit are the ASSUMED ones of test_derivative.py.
"""
import dataclasses
import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest
from shapely.geometry import box

from moduleforge.drc import DesignRules, check
from moduleforge.generate import derivative as D
from moduleforge.generate import halfbridge as H
from moduleforge.generate import twin as W
from moduleforge.geometry import GATE_HS, GATE_LS, KELVIN_HS, KELVIN_LS, NETS

ROOT = Path(__file__).resolve().parents[3]
L1_DEV_SCREEN = 0.05  # dev screen on Case 4 (task T0259); the gate proper is E008 F1(a1)


def _load_case4():
    path = ROOT / "research" / "scripts" / "o006_case4_layout.py"
    sp = importlib.util.spec_from_file_location("o006_case4_layout_for_twin_test", path)
    mod = importlib.util.module_from_spec(sp)
    sys.modules[sp.name] = mod
    sp.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def case4():
    c4 = _load_case4()
    rules = DesignRules(max_wire_length=18e-3, max_gate_wire_length=25e-3, max_kelvin_wire_length=25e-3)
    rel = lambda r: tuple(v * 1e-3 for v in (r[0] - 2, r[1] - 3, r[2] - 2, r[3] - 3))  # noqa: E731
    spec = D.spec_from_layout(
        c4.build("base"), rules, {"SIG_HS_G": GATE_HS, "SIG_HS_KS": KELVIN_HS, "SIG_LS_G": GATE_LS, "SIG_LS_KS": KELVIN_LS},
        extra_pads={"gate": rel((0.5, 4.8, 1.5, 5.8)), "kelvin": rel((2.5, 4.8, 3.5, 5.8))})
    return c4.build("base"), spec


@pytest.fixture(scope="module")
def housing():
    return D.halfbridge_housing_spec(3)


@pytest.fixture(scope="module")
def housing_refs(housing):
    return D.generate(housing, 10, seed=2026)


@pytest.fixture(scope="module")
def hb_refs():
    """Layouts of the original 70 x 40 generator (not in the derivative parameter space by construction), all families."""
    out = []
    for fam in H.FAMILIES:
        out += H.generate_layouts(2, seed=5, family=fam)
    return out


def _spec_of(ref):
    return D.spec_from_layout(ref, DesignRules(), ())


def test_generated_layout_is_its_own_twin(housing, housing_refs):
    for ref in housing_refs:
        lay, p, rec = W.twin(ref, housing, with_l1=False)
        assert lay.fingerprint() == ref.fingerprint()
        assert rec["mode"] == "exact" and rec["symdiff_area_total_mm2"] == 0.0
        assert rec["max_die_displacement_mm"] == 0.0 and rec["max_wire_displacement_mm"] == 0.0
        assert p.to_vector().tolist() == D.params_of(ref).to_vector().tolist()


def test_exact_shortcut_is_guarded_by_the_fingerprint(housing, housing_refs):
    """A layout that carries a derivative family string but was modified is NOT its own twin; it goes to the fit."""
    ref = housing_refs[0]
    moved = dataclasses.replace(ref, dies=[dataclasses.replace(d, cx=d.cx + 0.5e-3) for d in ref.dies])
    lay, _, rec = W.twin(moved, housing, with_l1=False)
    assert rec["mode"] != "exact" and lay.fingerprint() != ref.fingerprint()


def test_fit_recovers_a_generated_layout_without_its_family_string(housing, housing_refs):
    """The geometric fit alone (stale family label) reproduces copper, dies and wires of generated layouts."""
    for ref in housing_refs[:6]:
        anon = dataclasses.replace(ref, family="anonymous")
        lay, _, rec = W.twin(anon, housing, with_l1=False)
        assert rec["mode"] in ("fit", "fit+signal_feet")
        assert rec["symdiff_area_total_mm2"] < 1e-6
        assert rec["max_die_displacement_mm"] < 1e-6
        assert rec["max_wire_displacement_mm"] < 0.13  # <= one 0.125 mm foot-grid step
        assert not check(lay, housing.rules)


def test_determinism(case4):
    ref, spec = case4
    a, pa, ra = W.twin(ref, spec, with_l1=False)
    b, pb, rb = W.twin(ref, spec, with_l1=False)
    assert a.fingerprint() == b.fingerprint() and pa.to_vector().tolist() == pb.to_vector().tolist() and ra == rb


def test_construction_uses_no_solver(case4, monkeypatch):
    import moduleforge.physics.peec as peec

    def boom(*a, **k):
        raise AssertionError("a solver was called")

    monkeypatch.setattr(peec, "loop_inductance", boom)
    ref, spec = case4
    W.twin(ref, spec, with_l1=False)


def test_case4_twin(case4):
    ref, spec = case4
    lay, p, rec = W.twin(ref, spec)
    assert check(lay, spec.rules) == []
    assert rec["topology"] == "x/PHASEd-DC-l-PHASEl-DC+d/split"  # the reference's own sequence
    # the copper is the reference copper (the 4 slots + 3 columns union is exact on this reference)
    assert rec["symdiff_area_total_mm2"] < 1e-9
    for n in NETS:
        c = rec["copper_area_mm2"][n]
        assert c["twin"] == pytest.approx(c["reference"], abs=1e-9)
    assert rec["reference_copper_mm2"] == pytest.approx(2260.0)  # 570 + 560 + 1130 mm^2 (the script's island areas)
    assert rec["max_die_displacement_mm"] == 0.0
    # wire feet: only the DRC repair against the assumed gate / Kelvin wires moves them (<= 0.25 mm here)
    assert rec["max_wire_displacement_mm"] <= 0.25 + 1e-9
    print(f"Case 4 twin: L1 ratio dev {rec['l1_ratio_abs_dev']:.4%}, wire displacement {rec['max_wire_displacement_mm']} mm")
    assert rec["l1_ratio_abs_dev"] <= L1_DEV_SCREEN  # dev screen only (E008 F1(a1) is at 0.25 mm)
    assert abs(1 - rec["l1_twin_H"] / rec["l1_reference_H"]) == pytest.approx(rec["l1_ratio_abs_dev"])


def test_housing_references_are_reported(hb_refs):
    """Original-generator references (all three families, 2..6 dies): DRC-clean twin, the L1 ratio sits in the record."""
    for ref in hb_refs:
        spec = _spec_of(ref)
        lay, _, rec = W.twin(ref, spec)
        assert check(lay, spec.rules) == []
        assert rec["symdiff_area_total_mm2"] < 1e-6 and rec["max_die_displacement_mm"] < 1e-6
        assert np.isfinite(rec["l1_ratio_abs_dev"])
        print(f"{ref.family} n={ref.dies_per_switch}: L1 dev {rec['l1_ratio_abs_dev']:.4%} wire disp "
              f"{rec['max_wire_displacement_mm']:.3f} mm")


def test_difference_record_is_exact_on_a_known_change(housing, housing_refs):
    """symdiff and displacements against an independently computed change: one die moved by 1 mm in x."""
    ref = housing_refs[0]
    moved = dataclasses.replace(ref, dies=[dataclasses.replace(ref.dies[0], cx=ref.dies[0].cx + 1e-3), *ref.dies[1:]])
    rec = W.difference_record(moved, ref)
    assert rec["symdiff_area_total_mm2"] == 0.0
    assert sorted(rec["die_centre_displacement_mm"][ref.dies[0].switch])[-1] == pytest.approx(1.0)
    assert sum(sum(v) for v in rec["die_centre_displacement_mm"].values()) == pytest.approx(1.0)
    t = ref.traces[0]
    x1, y1 = t.polygon.bounds[2], t.polygon.bounds[3]
    patch = box(x1 + 1e-3, y1 + 1e-3, x1 + 3e-3, y1 + 4e-3)  # a 2 x 3 mm island, disjoint from the trace
    bigger = dataclasses.replace(ref, traces=[dataclasses.replace(t, polygon=t.polygon.union(patch)), *ref.traces[1:]])
    rec2 = W.difference_record(bigger, ref)
    assert rec2["symdiff_area_total_mm2"] == pytest.approx(6.0)
    assert rec2["symdiff_area_mm2"][t.net] == pytest.approx(6.0)
    assert rec2["copper_area_mm2"][t.net]["reference"] == pytest.approx(rec2["copper_area_mm2"][t.net]["twin"] + 6.0)


# --------------------------------------------------------------------------------------------------------- degradation
def _ratio_target():
    return W.DEGRADE_RATIO * (1 + W.DEGRADE_MARGIN)


def test_degrade_on_ten_generator_housing_references(housing, housing_refs):
    for ref in housing_refs:
        tw, _, _ = W.twin(ref, housing, with_l1=False)
        d, rec = W.degrade(tw, housing)
        assert check(d, housing.rules) == []
        assert rec["l1_ratio"] >= _ratio_target()
        # only copper changes: dies, wires, terminals, keep-outs are identical, copper never grows
        assert [(x.cx, x.cy) for x in d.dies] == [(x.cx, x.cy) for x in tw.dies]
        assert all(np.array_equal(a.points, b.points) for a, b in zip(d.wires, tw.wires, strict=True))
        ta, tb = ({t.net: t.polygon for t in lay.traces} for lay in (d, tw))
        assert sum(ta[n].area for n in NETS) < sum(tb[n].area for n in NETS)
        assert rec["margin"] == W.DEGRADE_MARGIN and 1.25 * (1 + rec["margin"]) == pytest.approx(rec["target_l1_ratio"])


def test_degrade_on_case4(case4):
    ref, spec = case4
    tw, _, _ = W.twin(ref, spec, with_l1=False)
    d, rec = W.degrade(tw, spec)
    assert check(d, spec.rules) == [] and rec["l1_ratio"] >= _ratio_target()
    print(f"Case 4 degrade L1 ratio {rec['l1_ratio']:.3f} (target {_ratio_target():.3f})")


def test_degrade_is_deterministic_and_raises_when_the_ratio_is_missed(housing, housing_refs, monkeypatch):
    tw, _, _ = W.twin(housing_refs[0], housing, with_l1=False)
    a, _ = W.degrade(tw, housing, with_l1=False)
    b, _ = W.degrade(tw, housing, with_l1=False)
    assert a.fingerprint() == b.fingerprint() != tw.fingerprint()
    monkeypatch.setattr(W, "DEGRADE_MARGIN", 10.0)  # an unreachable target: the rule must report, not pass
    with pytest.raises(W.DegradeError):
        W.degrade(tw, housing)


def test_degrade_narrows_landing_slots_to_the_minimum_width(housing, housing_refs):
    tw, p, _ = W.twin(housing_refs[1], housing, with_l1=False)
    _, rec = W.degrade(tw, housing, with_l1=False)
    for v in rec["widths"].values():
        wmin = max(np.ceil(housing.rules.min_trace_width * 1e3 / 0.5) * 0.5, 1.0)
        assert wmin - 1e-9 <= v["after_mm"] <= wmin + 1.0  # at most two 0.5 mm steps above the minimum (landing margin)
        assert v["after_mm"] <= v["before_mm"]


# ------------------------------------------------------------------------- T0287: merged bands, exact DRC, degradation
def _transposed(spec):
    """The housing spec with x and y exchanged (orientation-y tests: build(spec_T, params with orient=1) is the transposed layout)."""
    from shapely.affinity import affine_transform

    from moduleforge.geometry import Terminal
    tr = lambda poly: affine_transform(poly, [0, 1, 1, 0, 0, 0])  # noqa: E731
    die = D.DieSpec(spec.die.h, spec.die.w, spec.die.thickness, spec.die.attach_thickness,
                    {k: (r[1], r[0], r[3], r[2]) for k, r in spec.die.pads.items()})
    terms = {k: Terminal(t.net, t.cy, t.cx, t.h, t.w) for k, t in spec.terminals.items()}
    return dataclasses.replace(spec, outline=tr(spec.outline), baseplate_outline=tr(spec.baseplate_outline), die=die,
                               terminals=terms)


def _overlapping_slots(p):
    """Total overlap area (mm^2) of any two slots of the parametrisation."""
    from shapely.geometry import box as bx
    r = [bx(*s) for s in p.slots]
    return sum(r[i].intersection(r[j]).area for i in range(4) for j in range(i + 1, 4))


@pytest.fixture(scope="module")
def merged_cases():
    """(spec, layout) of merged generator layouts, orientation x (housing) and y (transposed spec), 3 dies x 2 wires."""
    spec = D.halfbridge_housing_spec(3, wires_per_die=2)
    refs = [r for r in D.generate(spec, 30, seed=11) if D.topology_of(r).endswith("/merged")][:3]
    assert len(refs) == 3
    specy = _transposed(spec)
    out = [(spec, r) for r in refs]
    for r in refs:
        ly = D.build(specy, dataclasses.replace(D.params_of(r), orient=1))
        assert check(ly, specy.rules) == [] and D.topology_of(ly).startswith("y/") and D.topology_of(ly).endswith("/merged")
        out.append((specy, ly))
    return out


def test_merged_phase_band_is_split_and_labelled(merged_cases):
    """T0286 finding 0: fit-mode twins of merged generator layouts carry the label 'merged', no overlapping slots and
    the reference geometry; degrade() is effective on them (the slots are the geometry's, not overlapping ones)."""
    for spec, ref in merged_cases:
        anon = dataclasses.replace(ref, family="anonymous")
        lay, p, rec = W.twin(anon, spec, with_l1=False)
        assert rec["mode"] in ("fit", "fit+signal_feet")
        assert rec["topology"] == D.topology_of(ref) and rec["topology"].endswith("/merged")
        assert _overlapping_slots(p) == 0.0
        assert D.params_of(ref).sequence() == p.sequence() and p.orient == D.params_of(ref).orient
        assert rec["symdiff_area_total_mm2"] < 1e-6 and rec["max_die_displacement_mm"] < 1e-6
        assert rec["max_wire_displacement_mm"] < 0.13
        # the die slot and the landing slot of the PHASE band meet on the grid line where the generator put it
        seq, q = p.sequence(), D.params_of(ref)
        i = next(i for i in range(3) if seq[i][0] == seq[i + 1][0] == "PHASE")
        assert p.slots[i][3] == p.slots[i + 1][1] == q.slots[i][3] == q.slots[i + 1][1]
        d, drec = W.degrade(lay, spec)
        assert check(d, spec.rules) == [] and drec["l1_ratio"] >= _ratio_target()


def test_overlapping_unequal_intervals_are_split():
    """The probe lines of a merged band see different v-intervals (die part vs landing part): nested intervals split at
    the inner edge.  Checked on the T0286 example: a die slot ending at u = 60.5 beyond the landing slot's end."""
    spec = D.halfbridge_housing_spec(2, wires_per_die=2)
    ref = next(r for r in D.generate(spec, 60, seed=29) if D.topology_of(r).endswith("/merged"))
    _, p, rec = W.twin(dataclasses.replace(ref, family="anonymous"), spec, with_l1=False)
    assert rec["topology"].endswith("/merged") and _overlapping_slots(p) == 0.0


def test_exact_mode_checks_drc(housing, housing_refs):
    """T0286 finding 3: a layout that is its own twin but violates the spec's rules raises TwinError."""
    ref = housing_refs[0]
    strict = dataclasses.replace(housing, rules=DesignRules(min_trace_width=6e-3))
    assert check(ref, strict.rules)
    with pytest.raises(W.TwinError):
        W.twin(ref, strict, with_l1=False)


# the 54-layout population of T0286: n = 2, 3, 4 dies x 1, 2, 3 wires per die x 6 seeds
def _population():
    for n in (2, 3, 4):
        for k in (1, 2, 3):
            spec = D.halfbridge_housing_spec(n, wires_per_die=k)
            for ref in D.generate(spec, 6, seed=100 * n + k):
                yield spec, ref


def test_degradation_reaches_its_target_on_the_population_and_is_deterministic():
    """Every layout of the population reaches L1(D)/L1(W) >= 1.25 (1 + 0.11) and is DRC-clean; the ratio distribution
    is the one stated in the module docstring."""
    ratios, moves = [], {}
    for spec, ref in _population():
        tw, _, _ = W.twin(ref, spec, with_l1=False)
        d, rec = W.degrade(tw, spec)
        assert check(d, spec.rules) == []
        assert rec["l1_ratio"] >= _ratio_target() and rec["l1_ratio"] >= 1.25
        ratios.append(rec["l1_ratio"])
        moves[tuple(rec["moves"])] = moves.get(tuple(rec["moves"]), 0) + 1
    assert len(ratios) == 54
    lo, med, hi = min(ratios), float(np.median(ratios)), max(ratios)
    print(f"degradation L1 ratio over 54 layouts: min {lo:.3f}, median {med:.3f}, max {hi:.3f}; moves {moves}")
    assert lo >= _ratio_target()
    spec, ref = next(iter(_population()))
    a, ra = W.degrade(ref, spec)
    b, rb = W.degrade(ref, spec)
    assert a.fingerprint() == b.fingerprint() and ra == rb


def test_margin_covers_the_stated_l1_bias_spread():
    """L1 5-14 % below L2: the L1 ratio can exceed the L2 ratio by 0.95 / 0.86 - 1 = 10.5 %; the margin covers it."""
    assert W.DEGRADE_MARGIN >= 0.95 / 0.86 - 1 and W.DEGRADE_MARGIN >= 0.11
    assert _ratio_target() / (0.95 / 0.86) >= 1.25 - 1e-12


def test_centre_move_rescues_a_narrow_band_miss():
    """Landing bands that the narrowing alone leaves short of the target (the landing point is off the 0.5 mm grid): the
    second move centres the landing point in a minimum-width band.  Generator layout n = 3, k = 1, seed 931, index 6."""
    spec = D.halfbridge_housing_spec(3, wires_per_die=1)
    ref = D.generate(spec, 25, seed=931, max_failures=3000)[6]
    p1, _ = W._narrow_landing(D.params_of(ref), spec, centre=False)
    lay1 = D.build(spec, p1)
    assert W._l1(lay1) / W._l1(ref) < _ratio_target()  # narrowing alone misses
    d, rec = W.degrade(ref, spec)
    assert rec["moves"] == ["narrow_landing", "centre_landing"] and rec["l1_ratio"] >= _ratio_target()
    assert check(d, spec.rules) == []
    # the landing points moved by at most 0.25 mm, the dies and the wire feet not at all
    assert [(x.cx, x.cy) for x in d.dies] == [(x.cx, x.cy) for x in ref.dies]
    assert all(np.allclose(a.points[0], b.points[0]) for a, b in zip(d.wires, ref.wires, strict=True))
    assert all(np.linalg.norm(a.points[-1] - b.points[-1]) <= 0.25e-3 + 1e-9 for a, b in zip(d.wires, ref.wires, strict=True))


def test_spread_moves_are_used_when_narrowing_is_not_enough():
    """Stricter copper rule (2 mm minimum width): the landing bands have little to lose; a spread move completes."""
    spec = D.halfbridge_housing_spec(4, rules=DesignRules(min_trace_width=2e-3), wires_per_die=2)
    ref = D.generate(spec, 4, seed=942, max_failures=3000)[1]
    d, rec = W.degrade(ref, spec)
    assert any(m.startswith("spread") for m in rec["moves"]) and rec["l1_ratio"] >= _ratio_target()
    assert check(d, spec.rules) == []


def test_degrade_error_when_no_move_reaches_the_target():
    spec = D.halfbridge_housing_spec(4, rules=DesignRules(min_trace_width=2e-3), wires_per_die=1)
    ref = D.generate(spec, 4, seed=941, max_failures=3000)[2]
    with pytest.raises(W.DegradeError):
        W.degrade(ref, spec)
