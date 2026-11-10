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
    assert rec["l1_ratio"] == pytest.approx(1.421, abs=1e-3) and rec["walk"] is None  # locked (T0291 finding 4)
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
    # T0291 finding 4: the distribution stated in the module docstring is locked (move 1 alone on all 54, no walk)
    assert (lo, med, hi) == pytest.approx((1.415, 1.887, 3.328), abs=1e-3)
    assert moves == {("narrow_landing",): 54}
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


# ----------------------------------------------------------------------------------------------- T0293
def test_equal_interval_merged_bands_recover_the_generators_slots(monkeypatch):
    """T0291 finding 0: merged PHASE bands where both probes see the same v-interval are split on the 0.5 mm grid at the
    boundary that minimises the symmetric difference, which is the generator's slot boundary (n = 4, k = 3, seed 7043 had
    5.25 and 7.0 mm^2 of PHASE copper off with the midpoint)."""
    from shapely.geometry import Polygon
    calls = []  # (boundary chosen, boundary with the scored copper emptied: the midpoint fallback)
    orig, band = W._best_split, W._band_copper

    def spy(*a, **k):
        x = orig(*a, **k)
        W._band_copper = lambda *b, **kk: Polygon()
        try:
            calls.append((x, orig(*a, **k)))
        finally:
            W._band_copper = band
        return x
    monkeypatch.setattr(W, "_best_split", spy)
    n_merged = 0
    for n, k in ((4, 3), (3, 2), (2, 1)):
        spec = D.halfbridge_housing_spec(n, wires_per_die=k)
        for ref in D.generate(spec, 10, seed=7000 + 10 * n + k):
            if not D.topology_of(ref).endswith("/merged"):
                continue
            n_merged += 1
            lay, p, rec = W.twin(dataclasses.replace(ref, family="anonymous"), spec, with_l1=False)
            assert rec["symdiff_area_total_mm2"] < 1e-6, (n, k)
            # the slots' v-extents are the generator's (their u-extents are the chords of the copper, which may run on into
            # a column: same copper, so the symmetric difference above is zero)
            assert [(s[1], s[3]) for s in p.slots] == [(s[1], s[3]) for s in D.params_of(ref).slots]
            assert _overlapping_slots(p) == 0.0
    assert n_merged >= 5 and calls, "the equal-interval branch was never exercised"
    # T0299 finding 2: on some of these the midpoint fallback gives another boundary, so the minimum decides
    assert any(abs(x - m) > 1e-9 for x, m in calls), calls


_SEQ_DIE_LAND = [("PHASE", "die", "LS"), ("PHASE", "land", "HS")]
_SEQ_LAND_DIE = [("PHASE", "land", "HS"), ("PHASE", "die", "LS")]


def test_best_split_is_the_minimum_symmetric_difference_boundary():
    """_best_split on a hand-made L-shaped band: two stacked rectangles of different u extent; the split must be at the
    step in the outline (v = 3), not at the midpoint of the needs (die row up to 1, landing line at 5: midpoint 3.0 here
    too, so a second band with the step at v = 4 checks that the copper, not the midpoint, decides).  The landing line is
    at 6 mm (midpoint of the needs 3.5): none of the steps 2, 3, 4 is the midpoint (T0299 finding 2)."""
    from shapely.geometry import box as bx
    rules = DesignRules()
    anchor = [(2.0, 0.5, (0.0, 1.0)), (2.0, 6.0, (6.0, 6.0))]
    for step in (3.0, 4.0, 2.0):
        poly = bx(0, 0, 10e-3, step * 1e-3).union(bx(0, step * 1e-3, 6e-3, 7e-3))
        assert W._best_split(poly, _SEQ_DIE_LAND, [[0.0, 7.0], [0.0, 7.0]], 0, anchor, rules) == pytest.approx(step)


def test_best_split_ties_on_a_rectangular_band_go_to_the_midpoint_of_the_needs():
    """T0293 review (blocker): a rectangular merged band has the same copper for every boundary.  The tie must not go to
    the lowest grid line (which put the landing line outside its own slot) but, among the boundaries at which each slot
    holds its need with its margin, to the one nearest the midpoint of the needs (then the lower)."""
    from shapely.geometry import box as bx
    rules = DesignRules()  # die edge margin 1.0 mm, landing margin 0.3 mm
    poly = bx(0, 16.5e-3, 50e-3, 30.5e-3)  # the review's example: v from 16.5 to 30.5 mm, landing line 17.5 mm
    ivs = [[16.5, 30.5], [16.5, 30.5]]
    for row_v0, want in ((21.5, 19.5), (22.0, 19.5), (20.0, 18.5), (18.5, 18.0)):
        # landing slot below (need: the landing line), LS die slot above (need: the die row from row_v0)
        anchor = [(20.0, 17.5, (17.5, 17.5)), (10.0, row_v0 + 3.0, (row_v0, row_v0 + 6.0))]
        s = W._best_split(poly, _SEQ_LAND_DIE, ivs, 0, anchor, rules)
        assert s == pytest.approx(want), row_v0
        assert 17.5 + rules.wire_landing_margin * 1e3 <= s + 1e-9  # the landing line is inside its slot by the margin
        if 18.0 <= row_v0 - rules.die_edge_margin * 1e3:  # a grid line exists that meets both margins
            assert s <= row_v0 - rules.die_edge_margin * 1e3 + 1e-9
    # the needs leave no grid line with the margins: between the needs themselves (17.5 < s <= 18.0; s = 17.5 would put
    # the landing line on the boundary)
    anchor = [(20.0, 17.5, (17.5, 17.5)), (10.0, 21.0, (18.0, 24.0))]
    assert W._best_split(poly, _SEQ_LAND_DIE, ivs, 0, anchor, rules) == pytest.approx(18.0)
    # mirrored order (die slot below, landing slot above): the same rule
    anchor = [(10.0, 20.0, (17.0, 23.0)), (20.0, 28.0, (28.0, 28.0))]
    assert W._best_split(poly, _SEQ_DIE_LAND, ivs, 0, anchor, rules) == pytest.approx(25.5)


def _rectangular_merged(spec, ref):
    """``ref`` with the two touching PHASE slots given the same u-extent (the wider one's, else the narrower one's), so
    that the merged band is a rectangle; (slot index, params, layout) or None if neither variant is DRC-clean."""
    p = D.params_of(ref)
    seq = p.sequence()
    i = next(i for i in range(3) if seq[i][0] == seq[i + 1][0] == "PHASE" and p.slots[i + 1][1] == p.slots[i][3])
    a, b = p.slots[i], p.slots[i + 1]
    for u0, u1 in ((min(a[0], b[0]), max(a[2], b[2])), (max(a[0], b[0]), min(a[2], b[2]))):
        sl = list(p.slots)
        sl[i], sl[i + 1] = (u0, a[1], u1, a[3]), (u0, b[1], u1, b[3])
        q = dataclasses.replace(p, slots=tuple(sl))
        try:
            lay = D.build(spec, q)
        except ValueError:
            continue
        if not check(lay, spec.rules):
            return i, q, lay
    return None


def test_rectangular_merged_bands_keep_each_slots_contents():
    """T0293 review (blocker): rectangular merged PHASE bands (both slots with the same u-extent; the generator's sampler
    never draws them, so they are made from merged generator layouts).  The fit-mode twin has the reference copper, the
    label 'merged', no overlapping slots, each slot holds its die row / landing line with the rule margins, the boundary
    is the grid line nearest the midpoint of the needs (independently computed here), and degradation from the twin
    reaches the target.  Seeds 500 + 10 n + k, the first two merged layouts per (n, k) that have a DRC-clean variant."""
    n_cases = n_same = 0
    for n in (2, 3, 4):
        for k in (1, 2, 3):
            spec = D.halfbridge_housing_spec(n, wires_per_die=k)
            rules = spec.rules
            dv = spec.die.h * 1e3  # orientation x: v = y
            got = 0
            for ref in D.generate(spec, 40, seed=500 + 10 * n + k):
                if got == 2 or not D.topology_of(ref).endswith("/merged"):
                    continue
                made = _rectangular_merged(spec, ref)
                if made is None:
                    continue
                got += 1
                i, q, lay = made
                tw, p, rec = W.twin(dataclasses.replace(lay, family="anonymous"), spec, with_l1=False)
                assert rec["mode"] in ("fit", "fit+signal_feet") and rec["topology"] == D.topology_of(lay)
                assert rec["symdiff_area_total_mm2"] < 1e-6 and _overlapping_slots(p) == 0.0
                assert p.sequence() == q.sequence()
                needs, margins = [], []
                for j in (i, i + 1):
                    _, role, sw = p.sequence()[j]
                    s = p.slots[j]
                    if role == "land":
                        v = p.land[0 if sw == "HS" else 1]
                        m = rules.wire_landing_margin * 1e3
                        assert s[1] + m - 1e-9 <= v <= s[3] - m + 1e-9  # the landing line inside its own slot
                        needs.append((v, v))
                    else:
                        v0 = p.rows[0 if sw == "HS" else 1][1]
                        m = rules.die_edge_margin * 1e3
                        assert s[1] + m - 1e-9 <= v0 and v0 + dv <= s[3] - m + 1e-9  # the die row inside its own slot
                        needs.append((v0, v0 + dv))
                    margins.append(m)
                lo_ok, hi_ok = needs[0][1] + margins[0], needs[1][0] - margins[1]
                grid = [x * 0.5 for x in range(int(np.ceil(lo_ok / 0.5 - 1e-9)), int(np.floor(hi_ok / 0.5 + 1e-9)) + 1)]
                mid = 0.5 * (needs[0][1] + needs[1][0])
                assert p.slots[i][3] == min(grid, key=lambda x: (abs(x - mid), x))
                n_same += p.slots[i][3] == q.slots[i][3]
                _, drec = W.degrade(tw, spec)
                assert drec["l1_ratio"] >= _ratio_target()
                n_cases += 1
    print(f"rectangular merged bands: {n_cases}, generator boundary recovered in {n_same}")
    assert n_cases >= 15


def _spec_with_landing_margin(spec, m):
    return dataclasses.replace(spec, rules=dataclasses.replace(spec.rules, wire_landing_margin=m))


def test_centre_landing_skips_a_band_that_no_shift_admits_and_records_why():
    """T0291 finding 1: with a 0.5 mm landing margin no shift of the landing point gives a minimum-width band; the move
    must not leave the band off the wires' landing point."""
    spec = D.halfbridge_housing_spec(3, wires_per_die=2)
    ref = D.generate(spec, 6, seed=5)[0]
    spec_m = _spec_with_landing_margin(spec, 0.5e-3)
    p, widths = W._narrow_landing(D.params_of(ref), spec_m, centre=True)
    assert widths and all("skipped" in v and v["landing_shift_mm"] == 0.0 for v in widths.values())
    q = D.params_of(ref)
    assert p.feet == q.feet and p.slots == q.slots  # nothing moved, so every wire still lands on its band
    # the unchanged move is not applied by degrade() and is listed in `skipped`
    _, rec = W.degrade(ref, spec_m, with_l1=False)
    assert "centre_landing" not in rec["moves"]


def test_narrow_landing_raises_degrade_error_not_type_error_when_no_width_fits():
    spec = D.halfbridge_housing_spec(3, wires_per_die=2)
    ref = D.generate(spec, 2, seed=5)[0]
    with pytest.raises(W.DegradeError):
        W._narrow_landing(D.params_of(ref), _spec_with_landing_margin(spec, 8e-3), centre=False)


def test_widths_report_only_the_landing_move_that_was_applied():
    """T0291 finding 3(c): rec['widths'] is empty when neither landing move was applied."""
    spec = D.halfbridge_housing_spec(3, wires_per_die=2)
    ref = D.generate(spec, 2, seed=5)[0]
    _, rec = W.degrade(ref, spec, with_l1=False)
    assert rec["moves"] == ["narrow_landing"] and set(rec["widths"]) and rec["skipped"] == []
    # a spread-only result (no landing move applied) reports no widths: the 2 mm rule leaves this layout's bands at the minimum
    spec2 = D.halfbridge_housing_spec(4, rules=DesignRules(min_trace_width=2e-3), wires_per_die=2)
    ref2 = D.generate(spec2, 4, seed=942, max_failures=3000)[1]
    _, rec2 = W.degrade(ref2, spec2)
    landing = {"narrow_landing", "centre_landing"} & set(rec2["moves"])
    assert (rec2["widths"] == {}) == (not landing)
    assert set(rec2["widths_by_move"]) == landing
    # both landing moves applied (n = 3, k = 1, seed 931, index 6): move 2's widths start where move 1 left the bands, and
    # the widths reported are those of D's landing slots
    spec3 = D.halfbridge_housing_spec(3, wires_per_die=1)
    ref3 = D.generate(spec3, 25, seed=931, max_failures=3000)[6]
    d3, rec3 = W.degrade(ref3, spec3)
    wb = rec3["widths_by_move"]
    assert set(wb) == {"narrow_landing", "centre_landing"} and rec3["widths"] == wb["centre_landing"]
    for key, v in wb["centre_landing"].items():
        assert v["before_mm"] == wb["narrow_landing"][key]["after_mm"]
    p3 = D.params_of(d3)
    for i, (net, role, sw) in enumerate(p3.sequence()):
        if role == "land":
            assert p3.slots[i][3] - p3.slots[i][1] == rec3["widths"][f"{sw}_landing_{net}"]["after_mm"]


def test_walk_steps_are_on_the_grid_valid_and_listed():
    """The walk of T0293 (2 mm rule, n = 2, k = 1, seed 2017 index 7): every step is a +-0.5 mm change of one parameter,
    the record lists every move, the walk raised L1 at every step and the result is DRC-clean and deterministic."""
    spec = D.halfbridge_housing_spec(2, rules=DesignRules(min_trace_width=2e-3), wires_per_die=1)
    ref = D.generate(spec, 8, seed=2017, max_failures=3000)[7]
    d, rec = W.degrade(ref, spec)
    assert check(d, spec.rules) == [] and rec["l1_ratio"] >= _ratio_target()
    steps = rec["walk"]["steps"]
    assert steps and all(abs(abs(s["delta_mm"]) - 0.5) < 1e-12 and s["parameter"] in D.Params.NAMES for s in steps)
    ratios = [s["l1_ratio"] for s in steps]
    assert ratios == sorted(ratios) and len(set(ratios)) == len(ratios)
    assert rec["moves"][-len(steps):] == [f"walk[{s['parameter']}{s['delta_mm']:+g}mm]" for s in steps]
    assert rec["walk"]["terminal_state"] == "target reached" and rec["walk"]["terminal"] == W.WALK_TARGET
    assert rec["walk"]["l1_ratio"] == rec["l1_ratio"] == ratios[-1]
    assert rec["walk"]["start_l1_ratio"] < _ratio_target() <= rec["l1_ratio"]
    d2, rec2 = W.degrade(ref, spec)
    assert d2.fingerprint() == d.fingerprint() and rec2 == rec


def test_degrade_error_carries_the_walk_terminal_state():
    """(2, 1, 1) of the 2 mm stress set: the walk ends at a local maximum; the terminal ratio is locked (as in
    tests/regression/test_degrade_walk_stress.py) and the record says where the walk started and stopped."""
    spec = D.halfbridge_housing_spec(2, rules=DesignRules(min_trace_width=2e-3), wires_per_die=1)
    ref = D.generate(spec, 8, seed=2017, max_failures=3000)[1]
    with pytest.raises(W.DegradeError) as ei:
        W.degrade(ref, spec)
    wk = ei.value.record["walk"]
    assert wk["terminal"] == W.WALK_LOCAL_MAX and wk["terminal_state"].startswith("local maximum")
    assert wk["terminal_state"] in str(ei.value)
    assert wk["l1_ratio"] == pytest.approx(1.3382, abs=1e-3) and wk["l1_ratio"] < _ratio_target()
    assert wk["steps"] and wk["l1_ratio"] == wk["steps"][-1]["l1_ratio"] and wk["start_l1_ratio"] < wk["l1_ratio"]


def test_walk_ratio_is_stable_under_l1_mesh_refinement():
    """T0293 review: the walk climbs on the L1 screen that judges it.  On the walk case of
    test_walk_steps_are_on_the_grid_valid_and_listed the ratio stays within 0.5 % under refinement of the L1 mesh (4, 2,
    1 mm: 1.3940, 1.3903, 1.3919).  A screen-robustness check only; E008's L2 ratio is the evidence."""
    from moduleforge.physics.peec import loop_inductance
    spec = D.halfbridge_housing_spec(2, rules=DesignRules(min_trace_width=2e-3), wires_per_die=1)
    ref = D.generate(spec, 8, seed=2017, max_failures=3000)[7]
    d, rec = W.degrade(ref, spec)
    assert rec["walk"]["terminal"] == W.WALK_TARGET and rec["walk"]["steps"]
    ratios = [loop_inductance(d, [20e6], hmax=h).L_H[0] / loop_inductance(ref, [20e6], hmax=h).L_H[0]
              for h in (4e-3, 2e-3, 1e-3)]
    assert ratios[0] == pytest.approx(rec["l1_ratio"], rel=1e-12)
    assert ratios == pytest.approx([1.3940, 1.3903, 1.3919], abs=1e-3)
    assert max(ratios) / min(ratios) - 1 < 0.005


def _l_band(*extra):
    """L-shaped PHASE band: die slot u 0-40 x v 10-13, landing slot u 0-30 x v 13-20 (true boundary 13 mm), plus the
    extra boxes ((u0, u1, v0, v1) in mm)."""
    from shapely.geometry import box as bx
    p = bx(0, 10e-3, 40e-3, 13e-3).union(bx(0, 13e-3, 30e-3, 20e-3))
    for u0, u1, v0, v1 in extra:
        p = p.union(bx(u0 * 1e-3, v0 * 1e-3, u1 * 1e-3, v1 * 1e-3))
    return p


# die row needs 10-11.5 (probe u 20), landing line at 18 (probe u 15): the midpoint of the needs is 14.75 (grid 14.5),
# not the boundary 13, so a result of 13 is decided by the copper, not by the tie rule
_L_ANCHOR = [(20.0, 11.0, (10.0, 11.5)), (15.0, 18.0, (18.0, 18.0))]
_L_MIDPOINT_PICK = 14.5


def _l_split(poly):
    return W._best_split(poly, _SEQ_DIE_LAND, [[10.0, 20.0], [10.0, 20.0]], 0, _L_ANCHOR, DesignRules())


def _t0293_rule(poly, lo, hi, probes):
    """The T0293 scoring (whole net copper, nothing removed), to show which cases a test discriminates."""
    return poly


def _t0298_rule(poly, lo, hi, probes):
    """The T0298 rule: every u-range where the copper crosses v = lo - 0.25 or hi + 0.25 mm removed over [lo, hi]."""
    from shapely.geometry import LineString
    from shapely.geometry import box as bx
    from shapely.ops import unary_union
    strip = poly.intersection(bx(-1e6, lo * 1e-3, 1e6, hi * 1e-3))
    cols = []
    for v in (lo - 0.25, hi + 0.25):
        ln = poly.intersection(LineString([(-1.0, v * 1e-3), (1.0, v * 1e-3)]))
        for g in ([ln] if ln.geom_type == "LineString" else list(getattr(ln, "geoms", []))):
            if g.geom_type == "LineString" and g.bounds[2] - g.bounds[0] > 1e-9:
                cols.append(bx(g.bounds[0], lo * 1e-3, g.bounds[2], hi * 1e-3))
    return strip.difference(unary_union(cols)) if cols else strip


def _l_split_under(monkeypatch, rule, poly):
    with monkeypatch.context() as m:
        m.setattr(W, "_band_copper", rule)
        return _l_split(poly)


def test_best_split_ignores_attached_column_copper_outside_the_band(monkeypatch):  # T0297 finding 0
    """The L-band with a column at u 40.. spanning v 0-30: for widths of 10 mm and more (>= the 10 mm gap beside the
    narrower slot) the T0293 scoring pulled the minimum off the step.  Widths narrower than, equal to and wider than the
    gap all recover 13 (needs' midpoint 14.75); for 12 mm and wider the T0293 scoring does not, so the case discriminates."""
    for w in (0, 5, 8, 10, 12, 15, 25):
        poly = _l_band((40, 40 + w, 0, 30)) if w else _l_band()
        assert _l_split(poly) == pytest.approx(13.0), w
        if w >= 12:
            assert _l_split_under(monkeypatch, _t0293_rule, poly) != pytest.approx(13.0), w


# (u0, u1, v0, v1) of necks on which the T0298 rule loses the step (it notches both slots and every candidate ties):
# interior necks from below and from above, and L-junctions flush with a slot's end (T0300 review, major)
_NECKS = [(20, 25, 0, 10), (25, 35, 0, 10), (10, 30, 0, 10), (22, 23, 0, 10),  # from below, inside the u-range
          (30, 40, 0, 10), (28, 40, 0, 10),  # from below, flush with the die slot's end (beside the landing slot)
          (20, 25, 20, 30), (10, 30, 20, 30), (22, 23, 20, 30),  # from above, inside the landing slot's u-range
          (25, 30, 20, 30)]  # from above, flush with the landing slot's end


@pytest.mark.parametrize("neck", _NECKS)
def test_best_split_keeps_t_junction_necks_from_below_and_above(monkeypatch, neck):  # T0299 finding 0
    """A column joining the band's lower or upper edge at any u (a T-junction neck inside the slots' u-range, or an
    L-junction flush with a slot's end) is outside the band's v-range and does not change the band copper: the step at
    13 is recovered.  On every one of these cases the T0298 rule gives the tie rule's 14.5 instead."""
    assert _l_split(_l_band(neck)) == pytest.approx(13.0)
    assert _l_split_under(monkeypatch, _t0298_rule, _l_band(neck)) == pytest.approx(_L_MIDPOINT_PICK)


def test_best_split_neck_and_side_columns_together():
    assert _l_split(_l_band((20, 25, 0, 10), (40, 52, 0, 30), (-8, 0, 0, 30))) == pytest.approx(13.0)
    assert _l_split(_l_band((30, 40, 0, 10), (40, 55, 0, 30), (25, 30, 20, 30))) == pytest.approx(13.0)


@pytest.mark.parametrize("extra", [
    ((40, 52, 0, 30), (52, 53, 15, 15.5)),  # a 1 x 0.5 mm nub on the column's far side
    ((40, 52, 0, 30), (40, 54, 10, 20)),  # the column 2 mm wider inside the band than at the probe lines
    ((40, 52, 0, 30), (55, 58, 12, 18)),  # a disconnected island of the net beyond the column, inside the band
    ((40, 52, 0, 30), (55, 58, 10, 20)),  # the same island spanning the band's whole v-range
])
def test_best_split_side_column_with_copper_beyond_it(monkeypatch, extra):  # T0300 review, blocker
    """A side column 12 mm wide (wider than the 10 mm gap) with strip copper beyond it: still the step, where the
    T0293 scoring is pulled off it."""
    assert _l_split(_l_band(*extra)) == pytest.approx(13.0)
    assert _l_split_under(monkeypatch, _t0293_rule, _l_band(*extra)) != pytest.approx(13.0)


@pytest.mark.parametrize("col", [(40, 45, 10, 20), (40, 52, 10, 20), (40, 55, 10, 20), (40, 65, 10, 20),
                                 (40, 65, 10, 18), (40, 65, 12, 20), (35, 60, 11, 19), (40, 55, 0, 15)])
def test_best_split_side_column_inside_the_band_v_range(monkeypatch, col):  # T0299 finding 1
    """Side columns that cross neither end of the band (inside its v-range, full or partial height), or cross one end
    and stop inside the band: the part beside the landing slot is not connected to the slots' common u-range along its
    own horizontal line and is not scored, so every width gives the step.  Wide ones pull the T0293 scoring off it."""
    assert _l_split(_l_band(col)) == pytest.approx(13.0)
    if col[1] - col[0] >= 15:
        assert _l_split_under(monkeypatch, _t0293_rule, _l_band(col)) != pytest.approx(13.0)


def test_best_split_column_that_fills_the_step_ties():
    """Stated restriction (``_best_split`` docstring): a column at u 30-45 touches the landing slot's end and covers the
    die slot's end, so the copper of the band is the rectangle u 0-45 x v 10-20 and has no step; every candidate ties
    and the tie rule picks the grid line nearest the needs' midpoint (14.5).  A column at u 35-50 leaves a 5 mm step and
    gives 13."""
    assert _l_split(_l_band((30, 45, 0, 30))) == pytest.approx(_L_MIDPOINT_PICK)
    assert _l_split(_l_band((35, 50, 0, 30))) == pytest.approx(13.0)


def test_band_copper_is_the_slots_copper():
    """``_band_copper`` directly: the L-band with a column 15 mm wide attached to the die slot (u 40-55, v 0-30), a neck
    from below (u 20-25) and a nub: the kept copper is the L-band plus the column's part beside the die slot (v 10-13)."""
    from shapely.geometry import box as bx
    poly = _l_band((40, 55, 0, 30), (20, 25, 0, 10), (55, 56, 15, 16))
    got = W._band_copper(poly, 10.0, 20.0, [a[:2] for a in _L_ANCHOR])
    want = bx(0, 10e-3, 55e-3, 13e-3).union(bx(0, 13e-3, 30e-3, 20e-3))
    assert got.symmetric_difference(want).area < 1e-15
    assert got.area == pytest.approx(55 * 3e-6 + 30 * 7e-6, rel=1e-12)


def test_best_split_is_decided_by_the_scored_copper_not_the_midpoint(monkeypatch):  # T0299 finding 2
    """Mutation check: with the scored copper replaced by an empty polygon every candidate ties and the midpoint rule
    decides (14.5 for the needs here); the real copper gives 13, so the tests above prove the minimum."""
    from shapely.geometry import Polygon
    poly = _l_band((20, 25, 0, 10), (40, 52, 0, 30))
    assert _l_split(poly) == pytest.approx(13.0)
    assert _l_split_under(monkeypatch, lambda *a, **k: Polygon(), poly) == pytest.approx(_L_MIDPOINT_PICK)


def test_degrade_records_a_stopped_spread_family_apart_from_skipped(monkeypatch):
    """T0297 finding 1: a spread family whose step q >= 2 fails is applied up to q-1 and recorded in ``stopped``; it is
    not in ``skipped``, so moves and skipped are disjoint by family name.  The 2 mm rule layout of
    test_widths_report_only_the_landing_move_that_was_applied needs spread moves; step 2 (1.0 mm) is made to fail."""
    spec = D.halfbridge_housing_spec(4, rules=DesignRules(min_trace_width=2e-3), wires_per_die=2)
    ref = D.generate(spec, 4, seed=942, max_failures=3000)[1]
    last = []
    orig_shift, orig_try = W._shifted, W._try
    monkeypatch.setattr(W, "_shifted", lambda p, j, dv, down: (last.append(dv), orig_shift(p, j, dv, down))[1])
    monkeypatch.setattr(W, "_try", lambda sp, c: (None, "forced") if last and last[-1] == 2 * W.SPREAD_STEP_MM
                        else orig_try(sp, c))
    try:
        _, rec = W.degrade(ref, spec)
    except W.DegradeError as e:
        rec = e.record
    spread = [m for m in rec["moves"] if m.startswith("spread")]
    assert spread and rec["stopped"], rec["moves"]
    for st in rec["stopped"]:
        fam = st.split(":")[0]
        assert st == f"{fam}: stopped at step 1 (forced)"
        assert f"{fam}x{W.SPREAD_STEP_MM:g}mm" in rec["moves"]
        assert not any(sk.split(":")[0] == fam for sk in rec["skipped"])
    fams = {m.split("x")[0] for m in spread}
    assert not fams & {sk.split(":")[0] for sk in rec["skipped"]}
