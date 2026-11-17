"""Tests of the frozen O004 perturbation rules (generate/perturb.py, T0386), the four single moves and the compound
re-layouts of founder guidance I0217.

Development references only: 2D_Case_4 (research/scripts/o006_case4_layout.py; ranges were developed on it) and, geometry
only (no inductance of any kind is computed on them), 2D_Case_2R / 2D_Case_6 (research/scripts/o003_powersynth_references.py).
"""
from __future__ import annotations

import dataclasses
import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest
from shapely.geometry import Polygon, box

from moduleforge.drc import check
from moduleforge.generate import perturb as P
from moduleforge.geometry import DC_MINUS, DC_PLUS, NETS, PHASE, SIGNAL_NET, Trace

ROOT = Path(__file__).resolve().parents[2]
CELLS = (1.0e-3, 0.5e-3, 0.25e-3)
assert CELLS == P.LATTICES_M
# E008.yaml dev.case4.rule_overrides (dev only): pitch rules at the DesignRules defaults (the measured 10 mm is the pitch
# between different dies) and 18 mm power wires; 2D_Case_2R / 2D_Case_6 use the plain measured rules.
CASE4_OVERRIDES = {"min_wire_pitch": 0.6e-3, "wire_pitch_diameters": 2.0, "max_wire_length": 0.018}


def _load(name: str, rel: str):
    sp = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(sp)
    sys.modules[sp.name] = mod
    sp.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def c4mod():
    return _load("o006_case4_layout_for_perturb_test", "research/scripts/o006_case4_layout.py")


@pytest.fixture(scope="module")
def case4(c4mod):
    ref = c4mod.build("base")
    return ref, P.measured_rules(ref, CASE4_OVERRIDES)


@pytest.fixture(scope="module")
def o3mod():
    return _load("o003_references_for_perturb_test", "research/scripts/o003_powersynth_references.py")


@pytest.fixture(scope="module", params=["2D_Case_2R", "2D_Case_6"])
def geo_ref(request, o3mod):
    ref = o3mod.snapped(request.param)[0]
    return request.param, ref, P.measured_rules(ref)


def _poly_equal(a, b) -> bool:
    return a.symmetric_difference(b).area < 1e-12


def _nets(lay):
    return {t.net: t.polygon for t in lay.traces}


def _wire_ends(lay):
    return [(w.points[0, :2], w.points[-1, :2]) for w in lay.wires]


def _same_but(ref, new, *, traces=(), dies=False, wires=False, signal=False):
    """Everything not named is identical: stack, outline, terminals, dies, wires, signal wires, other nets' copper."""
    assert new.stack == ref.stack and new.dies_per_switch == ref.dies_per_switch
    assert _poly_equal(new.outline, ref.outline) and _poly_equal(new.baseplate_outline, ref.baseplate_outline)
    assert new.terminals == ref.terminals and new.backside_inset == ref.backside_inset
    assert [t.net for t in new.traces] == [t.net for t in ref.traces]
    for a, b in zip(ref.traces, new.traces, strict=True):
        if a.net not in traces:
            assert _poly_equal(a.polygon, b.polygon), a.net
    if not dies:
        assert [(d.cx, d.cy, d.pads) for d in ref.dies] == [(d.cx, d.cy, d.pads) for d in new.dies]
    if not wires:
        assert all(np.array_equal(a.points, b.points) for a, b in zip(ref.wires, new.wires, strict=True))
    if not signal:
        assert all(np.array_equal(a.points, b.points) for a, b in zip(ref.signal_wires, new.signal_wires, strict=True))


# ---------------------------------------------------------------------------------------------------------- lattice helper
def test_on_lattice_levels_and_misalignment(case4):
    ref, _ = case4
    assert all(P.on_lattice(ref, c) for c in CELLS)
    # an added PHASE rectangle whose top edge is 0.5 mm / 0.1 mm off the 1 mm lattice
    for shift, expect in ((0.5e-3, (False, True, True)), (0.1e-3, (False, False, False)), (0.25e-3, (False, False, True))):
        tr = [Trace(t.net, t.polygon.union(box(65e-3, 60e-3, 67e-3, 63e-3 + shift))) if t.net == PHASE else t
              for t in ref.traces]
        assert tuple(P.on_lattice(dataclasses.replace(ref, traces=tr), c) for c in CELLS) == expect, shift


# ------------------------------------------------------------------------------------------------------------------ rules
def test_measured_rules_follow_e008_construction(case4):
    ref, rules = case4
    from moduleforge.drc.rules import measure_rules
    measured, _ = measure_rules(ref)
    assert rules.min_signal_wire_length is None  # D0018 item 1
    assert rules.min_spacing == measured.min_spacing and rules.die_edge_margin == measured.die_edge_margin
    assert rules.max_wire_length == 0.018  # the dev override
    assert check(ref, rules) == []


def test_measured_rules_raise_if_reference_violates_them(c4mod):
    # Case 4 under its raw measured rules is not DRC-clean (16.15 mm wires against the default 15 mm): no substitute rules
    with pytest.raises(ValueError, match="not DRC-clean"):
        P.measured_rules(c4mod.build("base"))
    with pytest.raises(ValueError, match="dropped"):
        P.measured_rules(c4mod.build("base"), {"min_signal_wire_length": 1e-3})


def test_rules_sha256_is_stable_and_covers_ranges_and_sources(monkeypatch):
    h = P.rules_sha256()
    assert len(h) == 64 and h == P.rules_sha256()
    names = [n for n, _ in P._rule_sources()]
    for need in ("generate.perturb", "drc", "drc.rules", "geometry.layout.arc_wire", "geometry.layout.Layout.fingerprint",
                 "solvers.l2_layout.layout_lattice", "solvers.l2_layout.check_on_lattice", "solvers.l2_layout.cell_fill"):
        assert need in names
    src = dict(P._rule_sources())
    # the whole module is hashed, helpers and constants included (review of attempt 1: _mm, _polygon, MM were not)
    for frag in ("MM = 1e-3", "def _mm(", "def _box_mm(", "def _polygon(", "def _net_poly(", "def _set_net(", "def _int("):
        assert frag in src["generate.perturb"], frag
    assert "def check(" in src["drc.rules"] and "def measure_rules(" in src["drc.rules"]
    for frag in ("def _apply_compound(", "def _draw_compound(", "def components("):  # compounds are hashed (I0217)
        assert frag in src["generate.perturb"], frag
    for attr, val in (("DIE_SHIFT_MM", (-13, 12)), ("TERMINAL_MARGIN_MM", (0, 9)), ("MAX_REDRAWS", 7),
                      ("COMPOUND_SIZES", (2,)), ("PAIR_KINDS", P.MOVE_TYPES)):
        with monkeypatch.context() as m:
            m.setattr(P, attr, val)
            assert P.rules_sha256() != h, attr
    real = P._rule_sources()
    monkeypatch.setattr(P, "_rule_sources", lambda: [(n, s + " " if n == "drc.rules" else s) for n, s in real])
    assert P.rules_sha256() != h  # a change in the DRC source changes the hash


def test_ranges_are_whole_mm_and_wide():
    r = P.ranges()
    for k in ("die_shift_mm", "trace_delta_mm", "terminal_margin_mm", "terminal_delta_mm", "landing_shift_mm"):
        lo, hi = r[k]
        assert isinstance(lo, int) and isinstance(hi, int) and lo <= hi, k
    assert r["die_shift_mm"][0] < 0 < r["die_shift_mm"][1] and r["landing_shift_mm"][0] < 0 < r["landing_shift_mm"][1]
    assert r["compound_sizes"] == (2, 3)  # two or three of the four move types (I0217)
    assert P.PAIR_KINDS == P.MOVE_TYPES + (P.COMPOUND,)


# ----------------------------------------------------------------------------------------------------------- determinism
def test_draw_is_deterministic_in_the_seed_and_uses_no_global_state(case4):
    ref, rules = case4
    alloc = {m: 3 for m in P.PAIR_KINDS}
    a = P.draw(ref, alloc, seed=11, rules=rules)
    np.random.seed(0)
    state = np.random.get_state()[1].copy()
    b = P.draw(ref, alloc, seed=11, rules=rules)
    assert np.array_equal(np.random.get_state()[1], state)  # the global numpy state is untouched
    assert a == b and len(a) == 15
    assert [m.move_type for m in a] == [m for m in P.PAIR_KINDS for _ in range(3)]
    # adding compounds after the singles leaves the single draws of a seed as they were
    assert P.draw(ref, {m: 3 for m in P.MOVE_TYPES}, seed=11, rules=rules) == a[:12]
    c = P.draw(ref, alloc, seed=12, rules=rules)
    assert a != c
    fp = ref.fingerprint()
    x = [P.apply(ref, m.move_type, m.params).fingerprint() for m in a]
    y = [P.apply(ref, m.move_type, m.params).fingerprint() for m in a]
    assert x == y and ref.fingerprint() == fp  # apply is deterministic and does not modify the reference


def test_draw_returns_distinct_geometries(case4):
    ref, rules = case4
    mvs = P.draw(ref, {m: 8 for m in P.PAIR_KINDS}, seed=5, rules=rules)
    keys = [P.geometry_key(P.apply(ref, m.move_type, m.params)) for m in mvs]
    assert len(set(keys)) == len(keys) and P.geometry_key(ref) not in keys  # compounds included (I0217)
    assert sum(m.move_type == P.COMPOUND for m in mvs) == 8
    # the key ignores only the label: two parameter sets with the same geometry share it (a W slab of 1 or 2 mm next to the
    # DC+ pad at x 12 mm lies inside the copper column x 10..20 mm, so both leave the copper as it was)
    a = P.apply(ref, "terminal_copper", {"net": DC_PLUS, "side": "W", "margin_mm": 0, "delta_mm": 1})
    b = P.apply(ref, "terminal_copper", {"net": DC_PLUS, "side": "W", "margin_mm": 0, "delta_mm": 2})
    assert a.family != b.family and P.geometry_key(a) == P.geometry_key(b) == P.geometry_key(ref)


def test_apply_returns_no_shared_mutable_state(case4):
    ref, _ = case4
    moves = [("die_row_shift", {"switch": "HS", "dx_mm": 2, "dy_mm": -1}),
             ("trace_width", {"net": DC_MINUS, "edge": 0, "delta_mm": 1}),
             ("terminal_copper", {"net": PHASE, "side": "S", "margin_mm": 1, "delta_mm": 2}),
             ("wire_landing", {"switch": "LS", "dx_mm": 1, "dy_mm": 0})]
    moves.append((P.COMPOUND, {"moves": [{"move_type": mt, "params": prm} for mt, prm in moves[1:]]}))
    for mt, prm in moves:
        new = P.apply(ref, mt, prm)
        for attr in ("traces", "dies", "wires", "terminals", "signal_wires"):
            assert getattr(new, attr) is not getattr(ref, attr), (mt, attr)
        assert all(a is not b and a.pads is not b.pads for a, b in zip(ref.dies, new.dies, strict=True)), mt
        assert all(a is not b and not np.shares_memory(a.points, b.points)
                   for a, b in zip(ref.wires, new.wires, strict=True)), mt
        assert all(new.terminals[k] is not t for k, t in ref.terminals.items()), mt
        fp = ref.fingerprint()
        for w in new.wires:  # mutating the output leaves the reference alone
            w.points[:] += 1.0
        new.terminals[DC_PLUS].cx += 1.0
        new.dies[0].pads["source"] = (0, 0, 0, 0)
        assert ref.fingerprint() == fp, mt


def test_default_rules_in_draw_are_the_measured_ones(c4mod):
    ref = c4mod.build("base")  # raw measured rules are violated by the reference: draw refuses instead of substituting
    with pytest.raises(ValueError, match="not DRC-clean"):
        P.draw(ref, {"wire_landing": 1}, seed=1)


def test_draw_raises_when_redraws_are_exhausted(case4, monkeypatch):
    ref, rules = case4
    monkeypatch.setattr(P, "MAX_REDRAWS", 5)
    monkeypatch.setattr(P, "DIE_SHIFT_MM", (40, 40))  # every die lands off the substrate
    with pytest.raises(RuntimeError, match="die_row_shift"):
        P.draw(ref, {"die_row_shift": 1}, seed=1, rules=rules)
    monkeypatch.setattr(P, "COMPOUND_SIZES", (3,))  # every compound has three of the four types: one is a die-row shift
    monkeypatch.setattr(P, "TRACE_DELTA_MM", (40, 40))  # ... or a trace move that crosses the substrate edge
    with pytest.raises(RuntimeError, match="consecutive draws"):
        P.draw(ref, {P.COMPOUND: 1}, seed=1, rules=rules)
    with pytest.raises(ValueError, match="unknown"):
        P.draw(ref, {"nope": 1}, seed=1, rules=rules)


@pytest.mark.parametrize("mt,params", [
    ("die_row_shift", {"switch": "HS", "dx_mm": 0.5, "dy_mm": 0}),
    ("trace_width", {"net": DC_MINUS, "edge": 0, "delta_mm": 1.5}),
    ("terminal_copper", {"net": PHASE, "side": "E", "margin_mm": 1, "delta_mm": 0}),
    ("wire_landing", {"switch": "XX", "dx_mm": 1, "dy_mm": 0}),
    ("nonsense", {}),
    ("compound", {}),
    ("compound", {"moves": [{"move_type": "wire_landing", "params": {"switch": "HS", "dx_mm": 1, "dy_mm": 0}}]}),  # one
    ("compound", {"moves": [{"move_type": "wire_landing", "params": {"switch": "HS", "dx_mm": 1, "dy_mm": 0}},
                            {"move_type": "wire_landing", "params": {"switch": "LS", "dx_mm": 1, "dy_mm": 0}}]}),  # repeat
    ("compound", {"moves": [{"move_type": "wire_landing", "params": {"switch": "HS", "dx_mm": 1, "dy_mm": 0}},
                            {"move_type": "trace_width", "params": {"net": DC_MINUS, "edge": 0, "delta_mm": 1}}]}),  # order
    ("compound", {"moves": [{"move_type": "compound", "params": {}},
                            {"move_type": "trace_width", "params": {"net": DC_MINUS, "edge": 0, "delta_mm": 1}}]}),
    ("compound", {"moves": [{"move_type": mt, "params": {}} for mt in ("die_row_shift", "trace_width", "terminal_copper",
                                                                        "wire_landing")]}),  # four
    ("compound", {"moves": [{"move_type": "trace_width", "params": {"net": DC_MINUS, "edge": 0, "delta_mm": 1}},
                            {"move_type": "wire_landing", "params": {"switch": "HS", "dx_mm": 0.5, "dy_mm": 0}}]}),
])
def test_apply_rejects_malformed_parameters(case4, mt, params):
    with pytest.raises(ValueError):
        P.apply(case4[0], mt, params)


# --------------------------------------------------------------------------------------- each move changes what it declares
def test_row_axis(case4, geo_ref):
    assert P.row_axis(case4[0], "HS") == P.row_axis(case4[0], "LS") == "x"  # dies side by side in x, wires along y
    assert P.row_axis(geo_ref[1], "HS") == P.row_axis(geo_ref[1], "LS") == "x"


def test_die_row_shift_across_the_row_stretches_wires_o006_precedent(case4, c4mod):
    ref, rules = case4
    new = P.apply(ref, "die_row_shift", {"switch": "HS", "dx_mm": 0, "dy_mm": -1})
    _same_but(ref, new, traces=(DC_PLUS,), dies=True, wires=True)
    for a, b in zip(ref.dies, new.dies, strict=True):
        dy = -1e-3 if a.switch == "HS" else 0.0
        assert b.cx == pytest.approx(a.cx, abs=1e-12) and b.cy == pytest.approx(a.cy + dy, abs=1e-12)
        assert all(np.allclose(b.pads[k], np.add(a.pads[k], (0, dy, 0, dy)), atol=1e-12) for k in a.pads)
        assert (a.w, a.h) == (b.w, b.h)
    for a, b in zip(ref.wires, new.wires, strict=True):  # HS wires: start moves, landing stays; LS wires untouched
        if a.net == PHASE:
            assert np.allclose(b.points[0, :2], a.points[0, :2] - (0, 1e-3), atol=1e-12)
            assert np.allclose(b.points[-1], a.points[-1], atol=1e-12)
            assert b.length < a.length  # 16 mm -> 15 mm, as in O006's die_shift
        else:
            assert np.array_equal(a.points, b.points)
    # the host copper only grows, to the reference's own enclosure (2 mm) around the moved dies
    old, grown = _nets(ref)[DC_PLUS], _nets(new)[DC_PLUS]
    assert grown.contains(old.buffer(-1e-9)) and grown.area > old.area
    # the independent O006 variant (dies and wire starts moved, copper untouched) has the same dies and wires
    o6 = c4mod.build("die_shift")
    assert [(d.cx, d.cy) for d in o6.dies] == pytest.approx([(d.cx, d.cy) for d in new.dies], abs=1e-12)
    assert np.allclose([w.points for w in o6.wires], [w.points for w in new.wires], atol=1e-12)
    assert check(new, rules) == []


def test_die_row_shift_along_the_row_is_rigid(case4):
    ref, rules = case4
    new = P.apply(ref, "die_row_shift", {"switch": "HS", "dx_mm": 3, "dy_mm": 0})
    _same_but(ref, new, traces=(DC_PLUS,), dies=True, wires=True)
    for a, b in zip(ref.wires, new.wires, strict=True):
        if a.net == PHASE:  # every point of an HS wire moves by exactly (3, 0, 0) mm: same length, same shape
            assert np.allclose(b.points, a.points + (3e-3, 0, 0), atol=1e-12)
            assert b.length == pytest.approx(a.length, rel=1e-12)
        else:
            assert np.array_equal(a.points, b.points)
    # host copper: the 32 mm DC+ band already encloses the dies at x 31..45 mm by >= 2 mm, so nothing is added
    assert _poly_equal(_nets(new)[DC_PLUS], _nets(ref)[DC_PLUS])
    assert check(new, rules) == []


def test_die_row_shift_moves_signal_wires_with_the_die(geo_ref):
    name, ref, rules = geo_ref
    new = P.apply(ref, "die_row_shift", {"switch": "LS", "dx_mm": 2, "dy_mm": 1})  # along-row 2 mm, across 1 mm
    for a, b in zip(ref.signal_wires, new.signal_wires, strict=True):
        moved = ref.dies[a.die].switch == "LS"
        assert np.allclose(b.points[0, :2], a.points[0, :2] + ((2e-3, 1e-3) if moved else (0, 0)), atol=1e-12)
        assert np.allclose(b.points[-1, :2], a.points[-1, :2] + ((2e-3, 0) if moved else (0, 0)), atol=1e-12)
        assert b.points[-1, 2] == a.points[-1, 2] and (b.pad, b.net, b.die) == (a.pad, a.net, a.die)
    for a, b in zip(ref.wires, new.wires, strict=True):
        moved = a.net == DC_MINUS  # LS power wires land on DC-
        assert np.allclose(b.points[0, :2], a.points[0, :2] + ((2e-3, 1e-3) if moved else (0, 0)), atol=1e-12)
        assert np.allclose(b.points[-1, :2], a.points[-1, :2] + ((2e-3, 0) if moved else (0, 0)), atol=1e-12)


def test_trace_width_declared_changes_closed_form(case4, c4mod):
    ref, rules = case4
    sides = P.long_sides(_nets(ref)[DC_MINUS])
    assert ("h", 45, 20, 52) in sides  # the lower edge of T4 (y = 45 mm, x 20..52): a long side of a 5 mm band
    e = sides.index(("h", 45, 20, 52))
    new = P.apply(ref, "trace_width", {"net": DC_MINUS, "edge": e, "delta_mm": 2})
    _same_but(ref, new, traces=(DC_MINUS,))
    assert _poly_equal(_nets(new)[DC_MINUS], _nets(c4mod.build("trace_width"))[DC_MINUS])  # O006's 5 -> 7 mm widening
    assert _nets(new)[DC_MINUS].area - _nets(ref)[DC_MINUS].area == pytest.approx(32e-3 * 2e-3, rel=1e-9)
    assert check(new, rules) == []  # measured rules allow it
    inward = P.apply(ref, "trace_width", {"net": DC_MINUS, "edge": e, "delta_mm": -1})
    _same_but(ref, inward, traces=(DC_MINUS,))
    assert _nets(ref)[DC_MINUS].area - _nets(inward)[DC_MINUS].area == pytest.approx(32e-3 * 1e-3, rel=1e-9)


def test_long_sides_exclude_end_caps(case4):
    ref, _ = case4
    sides = P.long_sides(_nets(ref)[DC_MINUS])
    # DC- is T9 (x 10..20, y 10..50) + T4 (x 20..52, y 45..50): the 10 mm cap at y = 10 is far shorter than the 40 mm band it
    # closes and the 5 mm end at x = 52 shorter than the 32 mm band: neither is a long side; the four band sides are
    # (T0438: the top side y = 50 is one edge x 10..52 once collinear vertices are removed; it used to be read as 20..52
    # because T9 and T4 meet there, a split of the vertex list and not of the geometry)
    assert sides == [("h", 45, 20, 52), ("h", 50, 10, 52), ("v", 10, 10, 50), ("v", 20, 10, 45)]
    assert all(a1 - a0 >= P.LONG_SIDE_MIN_MM for _, _, a0, a1 in sides)


def test_terminal_copper_declared_changes_closed_form(case4):
    ref, rules = case4
    t = ref.terminals[DC_PLUS]  # lead at x 12..15, y 63..66 inside T10 (x 10..20, y 55..80): window margin 1 -> 11..16 x 62..67
    new = P.apply(ref, "terminal_copper", {"net": DC_PLUS, "side": "W", "margin_mm": 1, "delta_mm": -1})
    _same_but(ref, new, traces=(DC_PLUS,))
    assert _nets(ref)[DC_PLUS].area - _nets(new)[DC_PLUS].area == pytest.approx(5e-3 * 1e-3, rel=1e-9)  # slab 1 x 5 mm
    assert _nets(new)[DC_PLUS].contains(box(t.cx - t.w / 2, t.cy - t.h / 2, t.cx + t.w / 2, t.cy + t.h / 2).buffer(-1e-9))
    assert not _nets(new)[DC_PLUS].intersects(box(11.1e-3, 62.1e-3, 11.9e-3, 66.9e-3))  # the removed slab x 11..12 minus margin
    grown = P.apply(ref, "terminal_copper", {"net": PHASE, "side": "S", "margin_mm": 0, "delta_mm": 2})
    _same_but(ref, grown, traces=(PHASE,))
    assert _nets(grown)[PHASE].area >= _nets(ref)[PHASE].area


def test_wire_landing_declared_changes(case4):
    ref, rules = case4
    new = P.apply(ref, "wire_landing", {"switch": "HS", "dx_mm": 3, "dy_mm": 1})
    _same_but(ref, new, wires=True)
    for a, b in zip(ref.wires, new.wires, strict=True):
        assert np.allclose(b.points[0], a.points[0], atol=1e-12)  # start stays on the die pad
        if a.net == PHASE:  # HS wires land on PHASE
            assert np.allclose(b.points[-1, :2], a.points[-1, :2] + (3e-3, 1e-3), atol=1e-12)
            assert b.points[-1, 2] == a.points[-1, 2] and (b.diameter, b.loop_height) == (a.diameter, a.loop_height)
        else:
            assert np.array_equal(a.points, b.points)


# ------------------------------------------------------------------------------------------------------ compound (I0217)
def _compound(*parts):
    return {"moves": [{"move_type": mt, "params": prm} for mt, prm in parts]}


def test_compound_is_its_components_in_sequence_closed_form(case4):
    """PHASE T5 (x 25..55, y 55..60) widened 7 mm at its top edge (y 60 -> 67) and the HS landings moved (1, 9) mm onto the
    widened copper: PHASE gains exactly 30 x 7 mm^2, every HS wire keeps its start and lands (1, 9) mm further, nothing
    else changes; the compound is the second move applied to the first one's result."""
    ref, rules = case4
    assert P.long_sides(_nets(ref)[PHASE])[3] == ("h", 60, 25, 55)
    tw = ("trace_width", {"net": PHASE, "edge": 3, "delta_mm": 7})
    wl = ("wire_landing", {"switch": "HS", "dx_mm": 1, "dy_mm": 9})
    new = P.apply(ref, P.COMPOUND, _compound(tw, wl))
    assert P.geometry_key(new) == P.geometry_key(P.apply(P.apply(ref, *tw), *wl))
    assert P.components(P.COMPOUND, _compound(tw, wl)) == [tw, wl] and P.components(*tw) == [tw]
    _same_but(ref, new, traces=(PHASE,), wires=True)
    assert _nets(new)[PHASE].area - _nets(ref)[PHASE].area == pytest.approx(30e-3 * 7e-3, rel=1e-9)
    assert _poly_equal(_nets(new)[PHASE], _nets(ref)[PHASE].union(box(25e-3, 60e-3, 55e-3, 67e-3)))
    for a, b in zip(ref.wires, new.wires, strict=True):
        assert np.allclose(b.points[0], a.points[0], atol=1e-12)
        if a.net == PHASE:  # HS wires: 16 mm -> 7 mm
            assert np.allclose(b.points[-1, :2], a.points[-1, :2] + (1e-3, 9e-3), atol=1e-12)
            assert np.hypot(*(b.points[-1, :2] - b.points[0, :2])) == pytest.approx(np.hypot(1e-3, 7e-3), rel=1e-9)
        else:
            assert np.array_equal(a.points, b.points)
    assert check(new, rules) == [] and all(P.on_lattice(new, c) for c in CELLS)
    assert new.family.startswith(f"{ref.family}|perturb:{P.COMPOUND}:")
    # the landing alone, on the reference's 5 mm T5, is off its copper: the compound reaches what neither move does alone
    assert check(P.apply(ref, *wl), rules) != []


def _chain_ok(ref, mv, rules):
    """Every component of a drawn compound changes the geometry and leaves a DRC-clean layout; returns the final layout."""
    parts = P.components(mv.move_type, mv.params)
    assert len(parts) in P.COMPOUND_SIZES
    types = [t for t, _ in parts]
    assert types == [t for t in P.MOVE_TYPES if t in types]  # distinct, in MOVE_TYPES order
    cur = ref
    for mt, prm in parts:
        nxt = P.apply(cur, mt, prm)
        assert P.geometry_key(nxt) != P.geometry_key(cur), (mt, prm)
        assert check(nxt, rules) == [], (mt, prm)
        cur = nxt
    final = P.apply(ref, mv.move_type, mv.params)
    assert P.geometry_key(final) == P.geometry_key(cur)
    return final


def test_case4_compound_draws_are_clean_chains_with_parameters_in_range(case4):
    ref, rules = case4
    mvs = P.draw(ref, {P.COMPOUND: 12}, seed=4, rules=rules)
    assert [m.move_type for m in mvs] == [P.COMPOUND] * 12
    assert {len(m.params["moves"]) for m in mvs} == set(P.COMPOUND_SIZES)  # both sizes are drawn
    rg = P.ranges()
    for mv in mvs:
        final = _chain_ok(ref, mv, rules)
        assert all(P.on_lattice(final, c) for c in CELLS), mv
        for mt, q in P.components(mv.move_type, mv.params):
            if mt in ("die_row_shift", "wire_landing"):
                lo, hi = rg["die_shift_mm" if mt == "die_row_shift" else "landing_shift_mm"]
                assert lo <= q["dx_mm"] <= hi and lo <= q["dy_mm"] <= hi
            elif mt == "trace_width":
                assert rg["trace_delta_mm"][0] <= q["delta_mm"] <= rg["trace_delta_mm"][1]
            else:
                assert rg["terminal_margin_mm"][0] <= q["margin_mm"] <= rg["terminal_margin_mm"][1]
                assert rg["terminal_delta_mm"][0] <= q["delta_mm"] <= rg["terminal_delta_mm"][1]


# --------------------------------------------------------------------------------------------- lattice and DRC of the draws
def test_case4_draws_on_all_lattices_and_drc_clean(case4):
    ref, rules = case4
    for mv in P.draw(ref, {m: 4 for m in P.PAIR_KINDS}, seed=3, rules=rules):
        new = P.apply(ref, mv.move_type, mv.params)
        assert check(new, rules) == [], (mv, [v.rule for v in check(new, rules)])
        assert all(P.on_lattice(new, c) for c in CELLS), mv
        assert new.family != ref.family and P.geometry_key(new) != P.geometry_key(ref)


def test_geometry_only_on_2r_and_case6(geo_ref, monkeypatch):
    """Buildable, on the lattice, DRC-clean on 2D_Case_2R / 2D_Case_6, development seed, every move type (die-row shift
    included) and compounds; NO inductance is computed (the L1 and L2 entry points fail the test if they are called)."""
    name, ref, rules = geo_ref

    def boom(*a, **k):
        raise AssertionError("an inductance was computed on a judged reference")

    from moduleforge.physics.peec import model as peec
    from moduleforge.solvers import l2_layout as l2
    for mod, fn in ((peec, "loop_inductance"), (l2, "loop_inductance"), (l2, "build_layout_system")):
        monkeypatch.setattr(mod, fn, boom)
    assert all(P.on_lattice(ref, c) for c in CELLS)
    mvs = P.draw(ref, {m: 3 for m in P.PAIR_KINDS}, seed=7, rules=rules)
    assert [m.move_type for m in mvs] == [m for m in P.PAIR_KINDS for _ in range(3)]
    for mv in mvs:
        new = _chain_ok(ref, mv, rules) if mv.move_type == P.COMPOUND else P.apply(ref, mv.move_type, mv.params)
        assert check(new, rules) == [], (name, mv)
        assert all(P.on_lattice(new, c) for c in CELLS), (name, mv)
        assert len(new.dies) == len(ref.dies) and len(new.wires) == len(ref.wires)
        assert len(new.signal_wires) == len(ref.signal_wires)
        new.to_conductors()  # buildable (no solve)


# ------------------------------------------------------------------------------------------- development test on 2D_Case_4
@pytest.fixture(scope="module")
def l1_case4(case4):
    from moduleforge.physics.peec import model as peec
    ref, _ = case4
    f = [20e6]
    l0 = float(peec.loop_inductance(ref, f).L_H[0])
    return lambda lay: float(peec.loop_inductance(lay, f).L_H[0]) / l0


@pytest.fixture(scope="module")
def case4_ratios(case4, l1_case4):
    ref, rules = case4
    return [(mv.move_type, l1_case4(P.apply(ref, mv.move_type, mv.params)))
            for mv in P.draw(ref, {m: 12 for m in P.PAIR_KINDS}, seed=1, rules=rules)]


def test_case4_every_move_type_and_high_ratio_pair(case4_ratios):
    """Development test (F7(c), registration span [0.75, 0.98]): every move type and compounds yield pairs at L1, 20 MHz,
    and at least one has r >= 0.98."""
    assert {m for m, _ in case4_ratios} == set(P.PAIR_KINDS)
    assert max(r for _, r in case4_ratios) >= 0.98


@pytest.mark.parametrize("mt,params,lo,hi", [
    ("die_row_shift", {"switch": "HS", "dx_mm": 8, "dy_mm": -7}, 0.80, 0.94),  # HS wires 16 -> 9 mm
    ("trace_width", {"net": PHASE, "edge": 3, "delta_mm": 7}, 0.85, 0.94),
    ("terminal_copper", {"net": DC_PLUS, "side": "E", "margin_mm": 8, "delta_mm": -8}, 1.06, 1.20),  # cut beside the pad
    ("wire_landing", {"switch": "LS", "dx_mm": 11, "dy_mm": 0}, 1.06, 1.20),
])
def test_case4_each_move_type_reaches_the_6_percent_effect(case4, l1_case4, mt, params, lo, hi):
    """O004 covers a move type only with a pair of |1 - r| >= 6 % at L1: on the development reference each type's frozen
    ranges contain a DRC-clean draw that reaches it (found by an exhaustive integer scan on Case 4)."""
    ref, rules = case4
    rg = P.ranges()
    for k, v in params.items():
        if isinstance(v, int):
            key = {"dx_mm": "die_shift_mm" if mt == "die_row_shift" else "landing_shift_mm",
                   "dy_mm": "die_shift_mm" if mt == "die_row_shift" else "landing_shift_mm",
                   "delta_mm": "trace_delta_mm" if mt == "trace_width" else "terminal_delta_mm",
                   "margin_mm": "terminal_margin_mm", "edge": None}[k]
            assert key is None or rg[key][0] <= v <= rg[key][1], (k, v)
    new = P.apply(ref, mt, params)
    assert check(new, rules) == [] and all(P.on_lattice(new, c) for c in CELLS)
    r = l1_case4(new)
    assert abs(1 - r) >= 0.06 and lo <= r <= hi, r


# The lowest DRC-clean compound L1 ratio found on Case 4 (T0386 development scans, L1 at 20 MHz, E008 dev rules): exhaustive
# single scans, coordinate descent over all ten 2- and 3-type combinations from the best singles, and a full landing scan on
# 112 (die-row shift, trace width) chains drawn from all 7672 clean ones.  Its components are each within the frozen ranges.
LOWEST_COMPOUND = ((("die_row_shift", {"switch": "LS", "dx_mm": -3, "dy_mm": 2}),  # LS wires 12 -> 10 mm, row 3 mm west
                    ("trace_width", {"net": PHASE, "edge": 3, "delta_mm": 7}),  # T5 top edge y 60 -> 67 (3 mm from DC+)
                    ("wire_landing", {"switch": "HS", "dx_mm": 1, "dy_mm": 9})),  # HS wires 16 -> 7 mm onto the widened T5
                   0.7616)


def test_case4_lowest_compound_found_is_a_clean_chain_below_every_single_move(case4, l1_case4):
    """Compounds widen the development span below the singles' floor (best single 0.873, die-row shift), but the lowest
    compound found stays above 0.75: the HS wires cannot shorten below 7 mm because the 10 mm T5-T6 gap less the 3 mm
    DC+/PHASE spacing bounds the die shift plus the T5 widening, whichever way it is split."""
    ref, rules = case4
    parts, r_found = LOWEST_COMPOUND
    mv = P.Move(P.COMPOUND, _compound(*parts))
    new = _chain_ok(ref, mv, rules)
    assert all(P.on_lattice(new, c) for c in CELLS)
    r = l1_case4(new)
    assert r == pytest.approx(r_found, abs=5e-4)
    assert 0.75 < r < 0.873 - 0.05


@pytest.mark.xfail(strict=True, reason="T0386 finding, founder decision needed (I0217: the span is not changed here): no DRC-clean "
                   "single move reaches r <= 0.75 on 2D_Case_4 under its E008 dev rules (exhaustive integer scans at L1, 20 MHz: "
                   "die-row shift best 0.873, trace width 0.915, wire landing 0.963, terminal copper 0.981) and no compound "
                   "found does either (lowest 0.7616, LOWEST_COMPOUND)")
def test_case4_low_ratio_pair(case4_ratios):
    assert min(r for _, r in case4_ratios) <= 0.75


# ------------------------------------------------------------------------------------------------------------- T0438 fixes
def test_rules_sha256_covers_nets_signal_nets_and_the_geometry_properties(monkeypatch):
    """Review T0416 item 1: NETS (indexed by the rng), SIGNAL_NET, SIGNAL_PADS and the Die.box / BondWire.length /
    SignalWire.length sources are hashed."""
    names = dict(P._rule_sources())
    for need in ("geometry.layout.NETS", "geometry.layout.SIGNAL_NET", "geometry.layout.SIGNAL_PADS",
                 "geometry.layout.Die.box", "geometry.layout.BondWire.length", "geometry.layout.SignalWire.length"):
        assert need in names, need
    assert "box(" in names["geometry.layout.Die.box"] and "norm" in names["geometry.layout.BondWire.length"]
    h = P.rules_sha256()
    for attr, val in (("NETS", tuple(reversed(NETS))), ("SIGNAL_NET", {**SIGNAL_NET, ("gate", "HS"): "X"}),
                      ("SIGNAL_PADS", ("kelvin", "gate"))):
        with monkeypatch.context() as m:
            m.setattr(P, attr, val)
            assert P.rules_sha256() != h, attr


def test_long_sides_do_not_depend_on_collinear_splits(case4):
    ref, _ = case4
    for net, poly in _nets(ref).items():
        base = P.long_sides(poly)
        assert base == P.long_sides(P._canonical(poly))
        # split every edge at its midpoint (a collinear vertex, same geometry): the same edge set
        xy = list(poly.exterior.coords)
        split = []
        for a, b in zip(xy[:-1], xy[1:], strict=True):
            split += [a, ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)]
        poly2 = type(poly)(split)
        assert poly2.equals(poly) and len(poly2.exterior.coords) > len(xy)
        assert P.long_sides(poly2) == base, net


def test_whole_mm_assertion_in_draw_and_measured_rules(case4):
    ref, rules = case4
    P.require_whole_mm(ref)  # Case 4 is on the 1 mm lattice
    tr = [Trace(t.net, t.polygon.union(box(65e-3, 60e-3, 67e-3, 63.5e-3))) if t.net == PHASE else t for t in ref.traces]
    off = dataclasses.replace(ref, traces=tr)
    with pytest.raises(ValueError, match="whole-mm"):
        P.require_whole_mm(off)
    with pytest.raises(ValueError, match="whole-mm"):
        P.measured_rules(off, CASE4_OVERRIDES)
    with pytest.raises(ValueError, match="whole-mm"):
        P.draw(off, {"wire_landing": 1}, 1, rules)
    d = ref.dies[0]  # a die box half a mm off, and a terminal
    dies = [dataclasses.replace(d, cx=d.cx + 0.5e-3)] + list(ref.dies[1:])
    with pytest.raises(ValueError, match="die 0"):
        P.require_whole_mm(dataclasses.replace(ref, dies=dies))
    t = ref.terminals[DC_PLUS]
    terms = {**ref.terminals, DC_PLUS: dataclasses.replace(t, cx=t.cx + 0.5e-3)}
    with pytest.raises(ValueError, match="terminal DC"):
        P.require_whole_mm(dataclasses.replace(ref, terminals=terms))


def test_geo_references_are_whole_mm(geo_ref):
    P.require_whole_mm(geo_ref[1])


def test_terminal_copper_positive_delta_adds_copper_closed_form(case4):
    ref, rules = case4
    t = ref.terminals[DC_PLUS]  # lead x 12..15, y 63..66 in T10 (x 10..20, y 55..80); window margin 1: x 11..16, y 62..67
    # side W, delta +3: slab x 8..11, y 62..67; T10 starts at x = 10, so x 8..10 (2 mm wide, 5 mm tall) is new copper
    new = P.apply(ref, "terminal_copper", {"net": DC_PLUS, "side": "W", "margin_mm": 1, "delta_mm": 3})
    _same_but(ref, new, traces=(DC_PLUS,))
    gain = _nets(new)[DC_PLUS].area - _nets(ref)[DC_PLUS].area
    assert gain == pytest.approx(2e-3 * 5e-3, rel=1e-9) and gain > 0
    assert _nets(new)[DC_PLUS].contains(box(8.1e-3, 62.1e-3, 9.9e-3, 66.9e-3))
    assert not _nets(ref)[DC_PLUS].intersects(box(8.1e-3, 62.1e-3, 9.9e-3, 66.9e-3))
    assert t.cx - t.w / 2 == pytest.approx(12e-3)


def _gen2_0():
    return _load("e008_run_for_perturb_test", "experiments/runners/e008_run.py")


def test_long_sides_on_a_both_sided_edge_and_draw_params_avoid_it(case4):
    """T0387: a net whose long side has copper on both sides must not make every trace_width draw fail.  Synthetic: Case 4
    with DC- widened by 0.5 mm along T9 (its new side x = 20.5 mm is read as x = 20 mm, inside the copper on both sides)."""
    ref, _ = case4
    tr = [Trace(t.net, t.polygon.union(box(10e-3, 10e-3, 20.5e-3, 50e-3))) if t.net == DC_MINUS else t for t in ref.traces]
    syn = dataclasses.replace(ref, traces=tr)
    with pytest.raises(ValueError, match="both sides"):
        P.long_sides(_nets(syn)[DC_MINUS])
    assert P.long_sides(_nets(syn)[DC_PLUS]) and P.long_sides(_nets(syn)[PHASE])  # the other nets are readable
    rng = np.random.default_rng(5)
    got, failed = set(), 0
    for _ in range(300):
        try:
            p = P._draw_params(syn, "trace_width", rng)
        except ValueError:
            failed += 1
            continue
        got.add(p["net"])
        assert p["net"] != DC_MINUS and 0 <= p["edge"] < len(P.long_sides(_nets(syn)[p["net"]]))
    assert got == {DC_PLUS, PHASE} and 0 < failed < 300  # only the unreadable net's draws are lost, and they are redrawn


@pytest.mark.slow
def test_gen2_0_long_sides_and_draw_params():
    """T0387 on gen2_0 (development geometry; off the 1 mm lattice, so ``draw`` refuses it by item 3 -- tested at the
    long_sides / _draw_params level only)."""
    R = _gen2_0()
    ref = R.dev_reference("gen2_0", R.load_spec()["config"]).reference
    polys = _nets(ref)
    with pytest.raises(ValueError, match="both sides"):
        P.long_sides(polys[DC_PLUS])
    with pytest.raises(ValueError, match="both sides"):
        P.long_sides(polys[PHASE])
    assert P.long_sides(polys[DC_MINUS])
    with pytest.raises(ValueError, match="whole-mm"):
        P.draw(ref, {"trace_width": 1}, 1)
    rng = np.random.default_rng(3)
    nets = set()
    for _ in range(200):
        try:
            nets.add(P._draw_params(ref, "trace_width", rng)["net"])
        except ValueError:
            pass
    assert nets == {DC_MINUS}


# ------------------------------------------------------------------------------------------------------------- T0451 fixes
def test_rules_sha256_covers_die_bounds_and_ring_ints(monkeypatch):
    """Review T0446 item 1: Die.box only calls box(*self.bounds), so Die.bounds (the geometry) and Layout's normalise-and-round
    helper ``_ring_ints`` (the distinctness key) must be hashed too."""
    from moduleforge.geometry import layout as geo
    names = dict(P._rule_sources())
    assert "geometry.layout.Die.bounds" in names and "geometry.layout._ring_ints" in names
    h = P.rules_sha256()
    with monkeypatch.context() as m:
        m.setattr(geo.Die, "bounds", property(lambda self: (self.cx - self.w, self.cy - self.h, self.cx + self.w,
                                                            self.cy + self.h)))
        assert P.rules_sha256() != h
    assert P.rules_sha256() == h
    with monkeypatch.context() as m:
        m.setattr(geo, "_ring_ints", lambda poly: [[int(round(v * 1e6)) for c in poly.exterior.coords for v in c]])
        assert P.rules_sha256() != h
    assert P.rules_sha256() == h


def test_draw_single_redraws_only_the_long_side_error(case4, monkeypatch):
    """Review T0446 item 2: a reference defect (a power net without exactly one trace) fails loudly instead of a silent
    redraw; the long-side error is still redrawn."""
    ref, rules = case4
    dup = dataclasses.replace(ref, traces=[*ref.traces, Trace(DC_PLUS, box(0, 0, 1e-3, 1e-3))])
    with pytest.raises(ValueError, match="exactly one trace"):
        P._draw_single(dup, "trace_width", np.random.default_rng(1), rules, set())
    real = P._draw_params
    calls = []

    def flaky(reference, move_type, rng):
        calls.append(1)
        if len(calls) < 3:
            raise P.LongSideError("edge has copper on both sides")
        return real(reference, move_type, rng)

    monkeypatch.setattr(P, "_draw_params", flaky)
    params, new = P._draw_single(ref, "trace_width", np.random.default_rng(2), rules, set())
    assert len(calls) >= 3 and params["net"] in NETS


def test_long_sides_tolerate_whole_mm_noise(case4):
    """Review T0446 item 3: vertices built as k/1000 (1e-6 mm of float noise, which ``require_whole_mm`` accepts) merge their
    collinear splits like exact ones."""
    ref, _ = case4
    for net, poly in _nets(ref).items():
        base = P.long_sides(poly)
        xy = list(poly.exterior.coords)
        split = []
        for a, b in zip(xy[:-1], xy[1:], strict=True):
            split += [a, ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)]
        # whole-mm coordinates built as k / 1000 with different float noise of order 1e-13 mm per vertex
        rng = np.random.default_rng(0)
        noisy = [(round(x / 1e-3) / 1000 + rng.normal(0, 1e-16), round(y / 1e-3) / 1000 + rng.normal(0, 1e-16))
                 for x, y in [*split, split[0]]]
        # exact collinearity is lost, whole mm is not
        assert any(x != round(x / 1e-3) * 1e-3 for x, _ in noisy)
        assert P.long_sides(Polygon(noisy)) == base, net
