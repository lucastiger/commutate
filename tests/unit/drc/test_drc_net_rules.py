"""Per-net design rules, gate/Kelvin signal wires, bondability DRC and ``measure_rules`` (T0256).

All fixtures are hand-built (``fixture``) or generator layouts; nothing here reads external reference data.
Lengths in the fixture are written in mm and converted with ``mm_to_m``; the expected gaps, widths, margins and
distances in the comments are derived by hand from the rectangle coordinates.

Gate and Kelvin nets are per switch position: HS and LS gates are driven separately, the HS Kelvin source sits at
PHASE potential and the LS one at DC- potential. So the fixture has four separate signal islands, and a layout that
lands an HS and an LS signal wire on one shared island (a short) must be flagged under every labelling.
"""
from __future__ import annotations

import dataclasses
import itertools
import math

import numpy as np
import pytest
from shapely.geometry import LineString, box
from shapely.ops import unary_union

from moduleforge.drc import DEFAULT_RULES, DesignRules, check, measure_rules
from moduleforge.drc.rules import spacing_class
from moduleforge.generate.halfbridge import generate_layouts
from moduleforge.geometry import (
    GATE_HS,
    GATE_LS,
    KELVIN_HS,
    KELVIN_LS,
    SIGNAL_NET,
    SIGNAL_NETS,
    Die,
    Layout,
    SignalWire,
    Terminal,
    Trace,
    arc_wire,
    default_dbc_stack,
    mm_to_m,
)

M = mm_to_m


def mmbox(x0, y0, x1, y1):
    return box(M(x0), M(y0), M(x1), M(y1))


def rect(*v):
    return tuple(M(x) for x in v)


def power_wire(x0, y0, x1, y1, net, z0):
    return arc_wire((M(x0), M(y0)), (M(x1), M(y1)), z0, 0.0, M(0.5), M(0.3), net)


def signal_wire(die, pad, net, p0, p1, z0, loop=0.5, diam=0.1):
    w = arc_wire((M(p0[0]), M(p0[1])), (M(p1[0]), M(p1[1])), z0, 0.0, M(loop), M(diam), net)
    return SignalWire(die, pad, net, w.points, w.diameter, w.loop_height)


def poly_signal_wire(die, pad, net, pts_mm, diam=0.1):
    p = np.array([[M(x), M(y), 0.0] for x, y in pts_mm])
    return SignalWire(die, pad, net, p, M(diam), 0.0)


def fixture(g1=2.0, w1=2.0, g2=2.0, w2=2.0, g3=2.0, w3=2.0, g4=2.0, w4=2.5, xa=12.1, xb=12.1, yc=12.3, xd=29.1,
            diam=0.1, loop=0.5) -> Layout:
    """Substrate 40 x 30 mm. Power copper: DC+ (3..17 x 5.5..15.5), PHASE (20..34 x 5.5..15.5), DC- (20..34 x
    18.5..26.5). Signal copper, one island per net: GATE_HS (3..17, g1 above DC+, w1 tall), KELVIN_HS (3..17, g2
    below DC+, w2 tall), KELVIN_LS (20..34, g3 below PHASE, w3 tall), GATE_LS (g4 right of PHASE, w4 wide,
    y 5.5..15.5). HS die at (10, 10.5), LS die at (27, 10.5), both 5 x 5 mm with source, gate and Kelvin pads.
    Signal wires: 0 HS gate, 1 HS Kelvin, 2 LS gate, 3 LS Kelvin, straight in plan from the pad centre to the
    middle of the strip at x = xa / xb / (GATE_LS centre) / xd and y = (strip centre) / (strip centre) / yc /
    (strip centre). Defaults: every strip 2 mm from its power copper, 2 mm wide (GATE_LS 2.5 mm)."""
    stack = default_dbc_stack()
    y_gh = (15.5 + g1, 15.5 + g1 + w1)
    y_kh = (5.5 - g2 - w2, 5.5 - g2)
    y_kl = (5.5 - g3 - w3, 5.5 - g3)
    x_gl = (34.0 + g4, 34.0 + g4 + w4)
    traces = [
        Trace("DC+", mmbox(3, 5.5, 17, 15.5)),
        Trace("PHASE", mmbox(20, 5.5, 34, 15.5)),
        Trace("DC-", mmbox(20, 18.5, 34, 26.5)),
        Trace(GATE_HS, mmbox(3, y_gh[0], 17, y_gh[1])),
        Trace(KELVIN_HS, mmbox(3, y_kh[0], 17, y_kh[1])),
        Trace(KELVIN_LS, mmbox(20, y_kl[0], 34, y_kl[1])),
        Trace(GATE_LS, mmbox(x_gl[0], 5.5, x_gl[1], 15.5)),
    ]
    dies = [
        Die(M(10), M(10.5), M(5), M(5), "HS", {"source": rect(8.25, 8.75, 11.75, 12.25),
                                              "gate": rect(11.9, 12.1, 12.3, 12.5),
                                              "kelvin": rect(11.9, 8.5, 12.3, 8.9)}),
        Die(M(27), M(10.5), M(5), M(5), "LS", {"source": rect(25.25, 8.75, 28.75, 12.25),
                                              "gate": rect(28.9, 12.1, 29.3, 12.5),
                                              "kelvin": rect(28.9, 8.6, 29.3, 9.0)}),
    ]
    zd = stack.z_top("top_cu") + dies[0].attach_thickness + dies[0].thickness
    wires = [power_wire(10, y, 22, y, "PHASE", zd) for y in (9.5, 10.5, 11.5)]
    wires += [power_wire(x, 11.75, x, 19.0, "DC-", zd) for x in (26.0, 27.0, 28.0)]
    mid = lambda a: 0.5 * (a[0] + a[1])  # noqa: E731
    sig = [
        signal_wire(0, "gate", GATE_HS, (12.1, 12.3), (xa, mid(y_gh)), zd, loop, diam),
        signal_wire(0, "kelvin", KELVIN_HS, (12.1, 8.7), (xb, mid(y_kh)), zd, loop, diam),
        signal_wire(1, "gate", GATE_LS, (29.1, 12.3), (mid(x_gl), yc), zd, loop, diam),
        signal_wire(1, "kelvin", KELVIN_LS, (29.1, 8.8), (xd, mid(y_kl)), zd, loop, diam),
    ]
    terms = {"DC+": Terminal("DC+", M(5.0), M(10.5), M(2.5), M(3.0)),
             "DC-": Terminal("DC-", M(32.0), M(22.5), M(3.0), M(3.0))}
    return Layout("fixture", 1, mmbox(0, 0, 40, 30), traces, dies, wires, terms, mmbox(-8, -8, 48, 38),
                  stack=stack, signal_wires=sig)


@pytest.fixture()
def fx():
    return fixture()


def viol(lay, rules=DEFAULT_RULES, rule=None):
    return [v for v in check(lay, rules) if rule is None or v.rule == rule]


def rule_names(lay, rules=DEFAULT_RULES):
    return {v.rule for v in check(lay, rules)}


def with_sig(lay, k, **kw):
    sw = list(lay.signal_wires)
    sw[k] = dataclasses.replace(sw[k], **kw)
    return dataclasses.replace(lay, signal_wires=sw)


def with_pts(lay, k, pts):
    return with_sig(lay, k, points=np.array(pts, dtype=float))


def replace_trace(lay, net, new):
    """``lay`` with the trace(s) of ``net`` replaced by ``new`` (a list of Traces)."""
    return dataclasses.replace(lay, traces=[t for t in lay.traces if t.net != net] + list(new))


def r(**kw):
    return dataclasses.replace(DesignRules(), **kw)


def pair(v):
    """The two nets named in a min_spacing violation message, as a set (trace order does not matter)."""
    return frozenset(v.message.split("(")[1].split(")")[0].split("/"))


# ---------------------------------------------------------------- defaults / fixture sanity

def test_fixture_is_clean_under_defaults(fx):
    assert check(fx) == []
    assert {t.net for t in fx.traces} >= set(SIGNAL_NETS)


def test_signal_net_map_is_per_switch():
    assert SIGNAL_NET == {("gate", "HS"): GATE_HS, ("gate", "LS"): GATE_LS,
                          ("kelvin", "HS"): KELVIN_HS, ("kelvin", "LS"): KELVIN_LS}
    assert len(set(SIGNAL_NETS)) == 4


def test_defaults_are_unchanged():
    d = DesignRules()
    for f in ("spacing_dcp_phase", "spacing_phase_dcm", "spacing_dcp_dcm", "spacing_other",
              "spacing_signal_dcp", "spacing_signal_phase", "spacing_signal_dcm", "spacing_signal_source",
              "spacing_signal_hs_ls", "min_width_power", "min_width_other", "min_signal_wire_diameter",
              "max_signal_wire_diameter", "min_signal_wire_length", "max_signal_wire_length", "max_gate_wire_length",
              "max_kelvin_wire_length"):
        assert getattr(d, f) is None
    assert d.min_spacing == 1e-3 and d.min_trace_width == 1e-3 and d.wire_pitch_diameters == 2.0


@pytest.mark.parametrize("seed", range(4))
@pytest.mark.parametrize("sp,w", [(0.5, 1.0), (1.5, 3.0), (2.5, 6.0)])
def test_explicit_values_equal_to_scalars_give_identical_verdicts(seed, sp, w):
    # the per-pair / per-class values, set equal to the scalar ones, reproduce the scalar verdicts, also on failing
    # layouts (2.5 mm spacing and 6 mm width fail on most generator layouts)
    lay = generate_layouts(1, seed=seed)[0]
    scalar = r(min_spacing=M(sp), min_trace_width=M(w))
    explicit = dataclasses.replace(scalar, spacing_dcp_phase=M(sp), spacing_phase_dcm=M(sp), spacing_dcp_dcm=M(sp),
                                   spacing_other=M(sp), min_width_power=M(w), min_width_other=M(w))
    assert check(lay, explicit) == check(lay, scalar)
    fxl = fixture()
    assert check(fxl, explicit) == check(fxl, scalar)


# ---------------------------------------------------------------- per-pair spacing

# gaps in the fixture: DC+/PHASE 3.0, PHASE/DC- 3.0, DC+/DC- sqrt(3^2 + 3^2) (corner (17, 15.5) to (20, 18.5));
# other pairs: GATE_HS/DC+, KELVIN_HS/DC+, KELVIN_LS/PHASE, GATE_LS/PHASE 2.0; KELVIN_LS/GATE_LS sqrt(8);
# GATE_HS/DC-, KELVIN_HS/KELVIN_LS 3.0; the rest larger
@pytest.mark.parametrize("field,nets,gap", [
    ("spacing_dcp_phase", ("DC+", "PHASE"), 3.0),
    ("spacing_phase_dcm", ("PHASE", "DC-"), 3.0),
    ("spacing_dcp_dcm", ("DC+", "DC-"), math.sqrt(18.0)),
])
def test_power_pair_spacing_fail_and_pass(fx, field, nets, gap):
    assert viol(fx, r(**{field: M(gap)}), "min_spacing") == []
    bad = viol(fx, r(**{field: M(gap + 0.01)}), "min_spacing")
    assert len(bad) == 1 and pair(bad[0]) == set(nets)


def test_other_pair_spacing_fail_and_pass(fx):
    assert viol(fx, r(spacing_other=M(2.0)), "min_spacing") == []
    bad = viol(fx, r(spacing_other=M(2.01)), "min_spacing")
    assert len(bad) == 4  # the four 2 mm signal/power gaps, and no power pair
    assert all(not pair(v) <= {"DC+", "PHASE", "DC-"} for v in bad)
    assert len(viol(fx, r(spacing_other=M(2.9)), "min_spacing")) == 5  # + KELVIN_LS/GATE_LS sqrt(8) = 2.83


def test_pair_spacing_can_be_looser_than_the_fallback(fx):
    loose = r(min_spacing=M(3.5), spacing_dcp_phase=M(1.0), spacing_phase_dcm=M(1.0), spacing_dcp_dcm=M(1.0),
              spacing_other=M(1.0))
    assert viol(fx, loose, "min_spacing") == []
    assert viol(fx, r(min_spacing=M(3.5)), "min_spacing")  # the fall-back value applies when nothing is set


def test_min_spacing_fallback_applies_to_unset_pairs(fx):
    vs = viol(fx, r(min_spacing=M(3.5), spacing_dcp_phase=M(1.0)), "min_spacing")
    assert vs and all("DC+/PHASE" not in v.message for v in vs)
    assert any("PHASE/DC-" in v.message for v in vs)  # 3.0 < 3.5, falls back


def test_hv_gap_cannot_shrink_to_a_signal_gap(fx):
    # T0252: a DC+/PHASE gap of 2.5 mm violates a 3 mm DC+/PHASE rule even though 2.5 mm exceeds the 2 mm rule that
    # governs the gate / Kelvin gaps
    narrow = replace_trace(fx, "DC+", [Trace("DC+", mmbox(3, 5.5, 17.5, 15.5))])
    rules = r(spacing_dcp_phase=M(3.0), spacing_other=M(2.0))
    bad = viol(narrow, rules, "min_spacing")
    assert len(bad) == 1 and pair(bad[0]) == {"DC+", "PHASE"}


def test_same_net_split_copper_uses_other_spacing(fx):
    lay = dataclasses.replace(fx, traces=fx.traces + [Trace("DC+", mmbox(36, 18, 38.5, 22))])
    # second DC+ piece: 2 mm right of DC- (34 -> 36), 2.5 mm above GATE_LS (15.5 -> 18)
    assert viol(lay, DEFAULT_RULES, "min_spacing") == []
    assert "net_split" in rule_names(lay)
    bad = viol(lay, r(spacing_other=M(2.0), spacing_dcp_dcm=M(2.1)), "min_spacing")
    assert len(bad) == 1 and pair(bad[0]) == {"DC+", "DC-"}  # the new DC+ piece vs DC-: a power pair
    same = viol(lay, r(spacing_other=M(30.0), spacing_dcp_phase=0.0, spacing_phase_dcm=0.0, spacing_dcp_dcm=0.0),
                "min_spacing")
    assert any(pair(v) == {"DC+"} for v in same)  # two pieces of one net count as an 'other' pair


# ---------------------------------------------------------------- per-class width

def test_width_per_class(fx):
    # power copper: DC+ and PHASE 10 mm, DC- 8 mm; other: GATE_HS, KELVIN_HS, KELVIN_LS 2 mm, GATE_LS 2.5 mm
    assert viol(fx, r(min_width_other=M(1.99), min_width_power=M(7.99)), "min_trace_width") == []
    bad_other = viol(fx, r(min_width_other=M(2.2)), "min_trace_width")
    assert sorted(v.message.split("(")[1].split(")")[0] for v in bad_other) == sorted([GATE_HS, KELVIN_HS, KELVIN_LS])
    assert len(viol(fx, r(min_width_other=M(2.6)), "min_trace_width")) == 4
    bad_power = viol(fx, r(min_width_power=M(9.0)), "min_trace_width")
    assert len(bad_power) == 1 and "(DC-)" in bad_power[0].message
    assert len(viol(fx, r(min_width_power=M(10.1)), "min_trace_width")) == 3


def test_width_class_can_relax_and_is_independent(fx):
    thin = replace_trace(fx, GATE_HS, [Trace(GATE_HS, mmbox(3, 17.5, 17, 18.3))])  # 0.8 mm
    assert viol(thin, DEFAULT_RULES, "min_trace_width")
    assert viol(thin, r(min_width_other=M(0.79)), "min_trace_width") == []
    assert viol(thin, r(min_width_other=M(0.79), min_width_power=M(7.99)), "min_trace_width") == []
    # a 0.8 mm neck in the DC+ copper is flagged by the power rule, not relaxed by the other-net rule
    necked = replace_trace(fx, "DC+", [Trace("DC+", mmbox(3, 5.5, 17, 15.5).difference(mmbox(6, 5.5, 7, 14.7)))])
    assert viol(necked, r(min_width_other=M(0.5)), "min_trace_width")
    assert viol(necked, r(min_width_power=M(0.79)), "min_trace_width") == []


# ---------------------------------------------------------------- bondability

# pad-to-own-copper plan distances: HS gate 17.5 - 12.5 = 5.0; HS Kelvin 8.5 - 3.5 = 5.0;
# LS gate 36.0 - 29.3 = 6.7; LS Kelvin 8.6 - 3.5 = 5.1
def test_gate_bondability(fx):
    assert viol(fx, r(max_gate_wire_length=M(6.7)), "signal_bondability") == []
    bad = viol(fx, r(max_gate_wire_length=M(6.69)), "signal_bondability")
    assert len(bad) == 1 and "die 1 (LS) gate" in bad[0].message and GATE_LS in bad[0].message
    assert len(viol(fx, r(max_gate_wire_length=M(4.99)), "signal_bondability")) == 2


def test_kelvin_bondability(fx):
    assert viol(fx, r(max_kelvin_wire_length=M(5.1)), "signal_bondability") == []
    bad = viol(fx, r(max_kelvin_wire_length=M(5.09)), "signal_bondability")
    assert len(bad) == 1 and "die 1 (LS) kelvin" in bad[0].message and KELVIN_LS in bad[0].message
    assert len(viol(fx, r(max_kelvin_wire_length=M(4.99)), "signal_bondability")) == 2


def test_gate_and_kelvin_limits_are_independent(fx):
    bad = viol(fx, r(max_gate_wire_length=M(4.0), max_kelvin_wire_length=M(50)), "signal_bondability")
    assert len(bad) == 2 and all("gate" in v.message and "kelvin" not in v.message for v in bad)


def test_bondability_counts_only_the_own_switch_copper(fx):
    # GATE_LS moved far right is out of reach of the LS gate pad (36 -> 37.5: 8.2 mm) while GATE_HS stays 12.9 mm
    # away; with the old shared-net semantics the nearest gate copper of either switch would have counted
    far = replace_trace(fx, GATE_LS, [Trace(GATE_LS, mmbox(37.5, 5.5, 39, 15.5))])
    assert viol(far, r(max_gate_wire_length=M(8.2)), "signal_bondability") == []
    assert viol(far, r(max_gate_wire_length=M(8.1)), "signal_bondability")
    # the LS gate pad next to HS gate copper does not count as bondable: relabel GATE_LS as a second GATE_HS
    # island 6.7 mm from it; the LS die then has no gate copper of its own at all
    relabelled = replace_trace(fx, GATE_LS, [Trace(GATE_HS, mmbox(36, 5.5, 38.5, 15.5))])
    bad = viol(relabelled, r(max_gate_wire_length=M(50)), "signal_bondability")
    assert len(bad) == 1 and "die 1 (LS)" in bad[0].message and f"no {GATE_LS} copper" in bad[0].message


def test_bondability_missing_copper_or_pad(fx):
    no_cu = dataclasses.replace(replace_trace(fx, KELVIN_LS, []), signal_wires=fx.signal_wires[:3])
    assert check(no_cu) == []  # not enforced by default
    bad = viol(no_cu, r(max_kelvin_wire_length=M(50)), "signal_bondability")
    assert len(bad) == 1 and f"no {KELVIN_LS} copper" in bad[0].message
    # a die without a Kelvin pad is not checked for Kelvin bondability (the pad set belongs to the die)
    d1 = fx.dies[1]
    no_pad = dataclasses.replace(no_cu, dies=[fx.dies[0], dataclasses.replace(
        d1, pads={k: v for k, v in d1.pads.items() if k != "kelvin"})])
    assert viol(no_pad, r(max_kelvin_wire_length=M(5.0)), "signal_bondability") == []
    assert viol(no_pad, r(max_kelvin_wire_length=M(4.9)), "signal_bondability")  # die 0 still checked


def test_signal_wire_length_limit(fx):
    gate_lens = [fx.signal_wires[k].length for k in (0, 2)]
    # the LS gate wire is the longer: plan chord 37.25 - 29.1 = 8.15 mm vs 18.5 - 12.3 = 6.2 mm, same loop
    assert gate_lens[1] > gate_lens[0] > M(6.2)
    assert viol(fx, r(max_gate_wire_length=gate_lens[1] + 1e-6), "signal_wire_length") == []
    bad = viol(fx, r(max_gate_wire_length=gate_lens[1] - 1e-6), "signal_wire_length")
    assert len(bad) == 1 and "signal wire 2" in bad[0].message


# ---------------------------------------------------------------- signal wire start / landing / net

def test_signal_wires_pass(fx):
    assert [v for v in check(fx) if v.rule.startswith("signal_") or v.rule == "wire_pitch"] == []


def test_signal_wire_start_off_pad(fx):
    pts = fx.signal_wires[0].points.copy()
    pts[0, 0] += M(1.0)  # 1 mm to the side, off the gate pad
    assert [v.rule for v in viol(with_pts(fx, 0, pts))] == ["signal_wire_start"]


def test_signal_wire_start_on_wrong_pad(fx):
    pts = fx.signal_wires[0].points.copy()
    pts[0, :2] = [M(12.1), M(8.7)]  # a gate wire starting on the die's Kelvin pad
    assert "signal_wire_start" in rule_names(with_pts(fx, 0, pts))


def test_signal_wire_start_edge_margin(fx):
    pts = fx.signal_wires[0].points.copy()
    pts[0, :2] = [M(11.92), M(12.3)]  # on the pad but 20 um from its edge (< 150 um foot margin)
    assert [v.rule for v in viol(with_pts(fx, 0, pts))] == ["signal_wire_start"]


def test_signal_wire_landing_on_power_copper(fx):
    pts = fx.signal_wires[0].points.copy()
    pts[-1, :2] = [M(12.1), M(14.0)]  # on DC+ copper, not GATE_HS
    assert [v.rule for v in viol(with_pts(fx, 0, pts))] == ["signal_wire_landing"]


def test_signal_wire_landing_margin(fx):
    pts = fx.signal_wires[0].points.copy()
    pts[-1, :2] = [M(12.1), M(17.6)]  # 0.1 mm inside the GATE_HS edge < 0.3 mm landing margin
    assert [v.rule for v in viol(with_pts(fx, 0, pts))] == ["signal_wire_landing"]


def test_hs_gate_wire_on_ls_gate_copper_is_flagged(fx):
    # HS gate wire re-routed (around the LS die, below it) onto GATE_LS copper
    path = [(12.1, 12.3), (12.9, 13.5), (35.0, 17.0), (37.25, 14.0)]
    as_hs = dataclasses.replace(fx, signal_wires=[poly_signal_wire(0, "gate", GATE_HS, path)] + fx.signal_wires[1:])
    assert "signal_wire_landing" in rule_names(as_hs)
    as_ls = dataclasses.replace(fx, signal_wires=[poly_signal_wire(0, "gate", GATE_LS, path)] + fx.signal_wires[1:])
    assert "signal_wire_net" in rule_names(as_ls)


@pytest.mark.parametrize("kind", ["gate", "kelvin"])
def test_shared_signal_island_shorting_hs_and_ls_is_flagged_under_every_labelling(fx, kind):
    """One island for both switches' gate (or Kelvin) wires shorts the HS and LS gate drives (or PHASE to DC-
    through the Kelvin sources). No choice of island net or wire nets makes such a layout clean."""
    hs_net, ls_net = SIGNAL_NET[(kind, "HS")], SIGNAL_NET[(kind, "LS")]
    k_hs, k_ls = (0, 2) if kind == "gate" else (1, 3)
    if kind == "kelvin":
        island = mmbox(3, 1.5, 34, 3.5)  # KELVIN_HS and KELVIN_LS strips merged
        ends = {k_hs: (12.1, 2.5), k_ls: (29.1, 2.5)}
    else:
        island = mmbox(3, 17.5, 17, 19.5)  # the GATE_HS strip; the LS gate wire is routed onto it around DC-
        ends = {k_hs: (12.1, 18.5), k_ls: (16.0, 18.5)}
    base = dataclasses.replace(fx, traces=[t for t in fx.traces if t.net not in (hs_net, ls_net)])
    n_checked = 0
    for island_net in (hs_net, ls_net, "GATE" if kind == "gate" else "KELVIN"):
        for net_hs, net_ls in itertools.product((hs_net, ls_net), repeat=2):
            lay = dataclasses.replace(base, traces=base.traces + [Trace(island_net, island)])
            sw = list(fx.signal_wires)
            for k, net in ((k_hs, net_hs), (k_ls, net_ls)):
                p0 = (sw[k].points[0, 0] / M(1), sw[k].points[0, 1] / M(1))
                path = ([p0, ends[k]] if kind == "kelvin" or k == k_hs
                        else [p0, (35.0, 17.0), (35.0, 27.5), (18.0, 27.5), ends[k]])
                sw[k] = poly_signal_wire(sw[k].die, kind, net, path)
            lay = dataclasses.replace(lay, signal_wires=sw)
            names = rule_names(lay)
            assert names & {"signal_wire_net", "signal_wire_landing"}, (island_net, net_hs, net_ls, names)
            n_checked += 1
    assert n_checked == 12


def test_separate_hs_and_ls_islands_are_clean_and_shared_per_switch_island_is_clean(fx):
    # the fixture: four separate islands, each wire on its own switch's copper -> clean (test above: shared -> not)
    assert check(fx) == []
    # two wires from the HS gate pad on one GATE_HS island (same net) are fine at a legal pitch
    # foot (12.14, 12.34): inside the 0.15 mm start margin of the 0.4 mm HS gate pad (allowed 12.05..12.15 x 12.25..12.35)
    extra = signal_wire(0, "gate", GATE_HS, (12.14, 12.34), (11.0, 18.5), fx.signal_wires[0].points[0, 2])
    pts = extra.points.copy()
    lay = dataclasses.replace(fx, signal_wires=fx.signal_wires + [dataclasses.replace(extra, points=pts)])
    assert viol(lay, r(min_wire_pitch=0.0, wire_pitch_diameters=0.0)) == []


def test_signal_wire_net_mismatch(fx):
    assert "signal_wire_net" in rule_names(with_sig(fx, 0, net=KELVIN_HS))  # gate pad, Kelvin net
    assert "signal_wire_net" in rule_names(with_sig(fx, 0, net=GATE_LS))  # HS die, LS net
    assert "signal_wire_net" in rule_names(with_sig(fx, 0, net="GATE"))  # not a per-switch net
    assert "signal_wire_net" in rule_names(with_sig(fx, 0, pad="source"))
    assert "signal_wire_net" in rule_names(with_sig(fx, 0, die=7))


# ---------------------------------------------------------------- crossing and pitch

def test_signal_wire_crossing_power_wire(fx):
    # LS gate wire bent across the LS power wires (x = 26..28, y 11.75..19) before reaching GATE_LS
    bent = [(29.1, 12.3), (26.5, 15.0), (37.25, 12.3)]
    lay = dataclasses.replace(fx, signal_wires=fx.signal_wires[:2] + [poly_signal_wire(1, "gate", GATE_LS, bent)]
                              + fx.signal_wires[3:])
    cross = viol(lay, rule="signal_wire_cross")
    assert cross and all(GATE_LS in v.message and "DC-" in v.message for v in cross)


def test_gate_wire_crossing_kelvin_wire_of_same_switch(fx):
    # HS Kelvin wire routed round the right end of the HS power wires and back across the HS gate wire (x = 12.1,
    # y 12.3..18.5) at y ~ 14.8, landing on KELVIN_HS: the only violation is that crossing
    path = [(12.1, 8.7), (23.0, 8.7), (23.0, 13.0), (11.0, 15.0), (5.0, 2.5)]
    lay = dataclasses.replace(fx, signal_wires=[fx.signal_wires[0], poly_signal_wire(0, "kelvin", KELVIN_HS, path)]
                              + fx.signal_wires[2:])
    vs = viol(lay)
    assert [v.rule for v in vs] == ["signal_wire_cross"]
    assert GATE_HS in vs[0].message and KELVIN_HS in vs[0].message


def test_same_net_signal_wires_overlapping_are_pitch_not_crossing(fx):
    sw = list(fx.signal_wires)
    sw.append(dataclasses.replace(sw[0], points=sw[0].points.copy()))
    names = rule_names(dataclasses.replace(fx, signal_wires=sw))
    assert "signal_wire_cross" not in names and "wire_pitch" in names


def test_wire_pitch_applies_between_signal_wires(fx):
    sw = list(fx.signal_wires)
    p = sw[0].points.copy()
    p[:, 0] += M(0.04)  # a second HS gate wire 0.04 mm beside the first; foot x 12.14 is within the start margin
    sw.append(SignalWire(0, "gate", GATE_HS, p, sw[0].diameter, sw[0].loop_height))
    lay = dataclasses.replace(fx, signal_wires=sw)
    bad = viol(lay)
    assert [v.rule for v in bad] == ["wire_pitch"] and "signal wire 4 / signal wire 0" in bad[0].message
    assert check(lay, r(min_wire_pitch=M(0.039), wire_pitch_diameters=0.0)) == []
    assert viol(lay, r(min_wire_pitch=M(0.01), wire_pitch_diameters=0.5), "wire_pitch")  # 0.5 x 0.1 mm > 0.04 mm


def test_wire_pitch_applies_between_signal_and_power_wires(fx):
    # HS power wire 0 moved from y = 9.5 to y = 9.1 (still >= 0.15 mm inside the source pad): 0.4 mm from the HS
    # Kelvin wire's foot at (12.1, 8.7), below the 0.6 mm default pitch
    w0 = power_wire(10, 9.1, 22, 9.1, "PHASE", fx.wires[0].points[0, 2])
    lay = dataclasses.replace(fx, wires=[w0] + fx.wires[1:])
    bad = viol(lay)
    assert [v.rule for v in bad] == ["wire_pitch"] and "signal wire 1 / wire 0" in bad[0].message
    assert check(lay, r(min_wire_pitch=M(0.39), wire_pitch_diameters=1.3)) == []  # 1.3 x 0.3 = 0.39 mm


# ---------------------------------------------------------------- IR: fingerprint and conductors

def test_fingerprint_covers_signal_wires(fx):
    base = fx.fingerprint()
    assert dataclasses.replace(fx, signal_wires=[]).fingerprint() != base
    pts = fx.signal_wires[0].points.copy()
    pts[-1, 0] += 2e-9
    assert with_pts(fx, 0, pts).fingerprint() != base
    assert with_sig(fx, 0, die=1).fingerprint() != base
    assert with_sig(fx, 0, pad="kelvin").fingerprint() != base
    assert with_sig(fx, 0, net=GATE_LS).fingerprint() != base
    assert with_sig(fx, 0, diameter=2e-4).fingerprint() != base
    assert with_sig(fx, 0, loop_height=9e-3).fingerprint() == base  # redundant with the points (documented)
    swapped = list(fx.signal_wires)
    swapped[0], swapped[1] = swapped[1], swapped[0]
    assert dataclasses.replace(fx, signal_wires=swapped).fingerprint() != base
    assert fixture().fingerprint() == base


def test_kelvin_pad_is_fingerprinted(fx):
    d0 = fx.dies[0]
    pads = dict(d0.pads)
    pads["kelvin"] = tuple(v + 1e-6 for v in pads["kelvin"])
    other = dataclasses.replace(fx, dies=[dataclasses.replace(d0, pads=pads), fx.dies[1]])
    assert other.fingerprint() != fx.fingerprint()


def test_to_conductors_excludes_signal_wires_only(fx):
    no_wires = dataclasses.replace(fx, signal_wires=[])
    a, b = fx.to_conductors(), no_wires.to_conductors()
    assert a == b  # signal wires do not enter the conductor model
    assert len(a.wires) == sum(len(w.points) - 1 for w in fx.wires) and len(a.shorts) == 2
    # the fixed gate / Kelvin copper stays in the model like any other copper (floating, as before T0256)
    assert {c.net for c in a.rects} == {"DC+", "PHASE", "DC-", *SIGNAL_NETS}
    assert sum(c.area for c in a.rects if c.net in SIGNAL_NETS) == pytest.approx(
        M(1) ** 2 * (14 * 2 + 14 * 2 + 14 * 2 + 2.5 * 10), rel=1e-12)


# ---------------------------------------------------------------- measure_rules

def test_measure_fixture_values(fx):
    rules, rec = measure_rules(fx)
    assert rec["gap_dcp_phase"] == pytest.approx(3e-3, abs=1e-12)
    assert rec["gap_phase_dcm"] == pytest.approx(3e-3, abs=1e-12)
    assert rec["gap_dcp_dcm"] == pytest.approx(math.sqrt(18.0) * 1e-3, abs=1e-12)
    # signal-to-power gaps (own rule classes, by voltage): every strip is 2 mm from the power copper it is not
    # referenced to (HS strips to DC+, LS strips to PHASE); HS signal to DC- is GATE_HS (y 17.5..19.5) to DC- (x 20..,
    # y 18.5..) 3.0; signal to its own source (GATE_HS/KELVIN_HS to PHASE, GATE_LS to DC-) sqrt(3^2 + 2^2); HS-LS
    # signal KELVIN_HS/KELVIN_LS 3.0; the remaining (same-switch) pairs are tightest at KELVIN_LS/GATE_LS, sqrt(8)
    for k in ("gap_signal_dcp", "gap_signal_phase"):
        assert rec[k] == pytest.approx(2e-3, abs=1e-12)
    assert rec["gap_signal_dcm"] == pytest.approx(3e-3, abs=1e-12)
    assert rec["gap_signal_source"] == pytest.approx(math.sqrt(13.0) * 1e-3, abs=1e-12)
    assert rec["gap_signal_hs_ls"] == pytest.approx(3e-3, abs=1e-12)
    assert rec["gap_other_min"] == pytest.approx(math.sqrt(8.0) * 1e-3, abs=1e-12)
    assert rec["min_width_power"] == pytest.approx(8e-3, abs=1.2e-6)  # DC- is 8 mm tall
    assert rec["min_width_other"] == pytest.approx(2e-3, abs=1.2e-6)
    assert rec["die_spacing"] == pytest.approx(12e-3, abs=1e-12)  # 24.5 - 12.5
    assert rec["die_edge_margin"] == pytest.approx(2.5e-3, abs=2e-9)  # die y 8..13 in copper y 5.5..15.5
    assert rec["edge_margin"] == pytest.approx(1.5e-3, abs=2e-9)  # Kelvin strips at y = 1.5, GATE_LS to x = 38.5
    lines = [LineString(w.points[:, :2]) for w in list(fx.wires) + list(fx.signal_wires)]
    brute = min(a.distance(b) for a, b in itertools.combinations(lines, 2))
    # closest pairs: the HS gate / Kelvin wire feet (12.1, 12.3) / (12.1, 8.7) to the HS power wires at y = 11.5 / 9.5
    assert brute == pytest.approx(0.8e-3, abs=1e-12)
    assert rec["min_wire_pitch"] == pytest.approx(0.8e-3, abs=1e-12)
    # smallest pitch / larger diameter: 0.8 / 0.3 (signal-power); power-power 1.0 / 0.3, signal-signal >= 3.5 / 0.1
    assert rec["min_wire_pitch_diameters"] == pytest.approx(0.8 / 0.3, rel=1e-9)
    assert rec["longest_gate_wire"] == fx.signal_wires[2].length
    assert rec["longest_kelvin_wire"] == max(fx.signal_wires[1].length, fx.signal_wires[3].length)
    assert rec["max_gate_pad_to_copper"] == pytest.approx(6.7e-3, abs=1e-12)
    assert rec["max_kelvin_pad_to_copper"] == pytest.approx(5.1e-3, abs=1e-12)
    assert rec["signal_unmeasured"] == {}
    assert rules.spacing_dcp_phase == pytest.approx(3e-3, abs=1e-9)
    assert rules.spacing_other == pytest.approx(math.sqrt(8.0) * 1e-3, abs=1e-9)
    assert rules.spacing_signal_dcp == pytest.approx(2e-3, abs=1e-9)
    assert rules.spacing_signal_phase == pytest.approx(2e-3, abs=1e-9)
    assert rules.spacing_signal_dcm == pytest.approx(3e-3, abs=1e-9)
    assert rules.spacing_signal_source == pytest.approx(math.sqrt(13.0) * 1e-3, abs=1e-9)
    assert rules.spacing_signal_hs_ls == pytest.approx(3e-3, abs=1e-9)
    assert rules.min_signal_wire_diameter == pytest.approx(0.1e-3, abs=1e-9) == rules.max_signal_wire_diameter
    assert rules.min_wire_pitch == pytest.approx(0.8e-3, abs=1e-9)
    assert rules.wire_pitch_diameters == pytest.approx(0.8 / 0.3, abs=1e-9)
    assert rules.max_gate_wire_length == pytest.approx(fx.signal_wires[2].length, abs=1e-9)
    assert check(fx, rules) == []


def test_measured_pitch_ratio_keeps_thick_wires_at_their_own_pitch(fx):
    # A wider HS gate pad (11.0..12.4 x 12.3..12.7, above the source pad) carries two gate wires 0.65 mm apart
    # (d = 0.1 mm): the layout's smallest pitch is now between thin wires, while its smallest pitch / diameter
    # ratio stays 0.8 / 0.3 (HS Kelvin foot to the 0.3 mm HS power wire).
    d0 = fx.dies[0]
    zd = fx.signal_wires[0].points[0, 2]
    sw = [signal_wire(0, "gate", GATE_HS, (x, 12.5), (x, 18.5), zd) for x in (11.3, 11.95)] + fx.signal_wires[1:]
    lay = dataclasses.replace(fx, dies=[dataclasses.replace(d0, pads=dict(d0.pads, gate=rect(11.0, 12.3, 12.4, 12.7))),
                                        fx.dies[1]], signal_wires=sw)
    assert check(lay) == []
    rules, rec = measure_rules(lay)
    assert rec["min_wire_pitch"] == pytest.approx(0.65e-3, abs=1e-12)
    assert rec["min_wire_pitch_diameters"] == pytest.approx(0.8 / 0.3, rel=1e-9)
    assert check(lay, rules) == []
    # HS power wire 1 moved from y = 10.5 to 10.2: 0.7 mm from wire 0. That meets the default (max(0.6, 2 x 0.3))
    # and the measured 0.65 mm, but not the measured ratio: 0.7 < (0.8 / 0.3) x 0.3 = 0.8 mm
    w1 = power_wire(10, 10.2, 22, 10.2, "PHASE", fx.wires[0].points[0, 2])
    tight = dataclasses.replace(lay, wires=[lay.wires[0], w1] + lay.wires[2:])
    assert check(tight) == []
    bad = viol(tight, rules)
    assert [v.rule for v in bad] == ["wire_pitch"] and "wires 0/1" in bad[0].message
    assert check(tight, dataclasses.replace(rules, wire_pitch_diameters=0.0)) == []  # the pitch alone would pass


def test_measure_without_signal_elements_leaves_those_rules_unset():
    lay = generate_layouts(1, seed=2)[0]
    rules, rec = measure_rules(lay)
    assert rules.spacing_other is None and rules.min_width_other is None
    assert rules.max_gate_wire_length is None and rules.max_kelvin_wire_length is None
    assert rec["gap_other_min"] is None and rec["longest_gate_wire"] is None
    assert rec["n_signal_wires"] == 0
    # generator dies have gate pads but the layout has no gate copper: recorded, limit unset
    assert "gate" in rec["signal_unmeasured"] and GATE_HS in rec["signal_unmeasured"]["gate"]


SIGNAL_SPACING_FIELDS = ("spacing_signal_dcp", "spacing_signal_phase", "spacing_signal_dcm", "spacing_signal_source",
                         "spacing_signal_hs_ls")
MIN_FIELDS = ("spacing_dcp_phase", "spacing_phase_dcm", "spacing_dcp_dcm", "spacing_other", *SIGNAL_SPACING_FIELDS,
              "min_width_power", "min_width_other", "min_signal_wire_diameter", "min_signal_wire_length",
              "min_wire_pitch", "die_spacing", "die_edge_margin", "edge_margin", "min_spacing", "min_trace_width")
STRICT_FIELDS = ("spacing_dcp_phase", "spacing_phase_dcm", "spacing_dcp_dcm", "spacing_other", *SIGNAL_SPACING_FIELDS,
                 "min_wire_pitch", "min_signal_wire_diameter", "min_signal_wire_length", "die_spacing",
                 "die_edge_margin", "edge_margin")  # measured to <= 1 nm: +1 um must fail
WIDTH_FIELDS = ("min_width_power", "min_width_other")  # bisected to 1 um: +3 um must fail
MAX_FIELDS = ("max_gate_wire_length", "max_kelvin_wire_length", "max_signal_wire_diameter", "max_signal_wire_length")


def assert_self_consistent(lay):
    """``lay`` (DRC-clean under the defaults) is clean under its own measured rules and under every rule moved 1 um
    to the safe side; moving any measured rule past the layout's own feature (1 um stricter; 3 um for the widths,
    which are bisected to 1 um; 1e-5 relative for the dimensionless pitch ratio) makes it fail."""
    assert check(lay) == []
    rules, rec = measure_rules(lay)
    assert check(lay, rules) == []
    for f in MIN_FIELDS:
        v = getattr(rules, f)
        if v is not None:
            assert check(lay, dataclasses.replace(rules, **{f: v - 1e-6})) == [], f
    for f in MAX_FIELDS:
        v = getattr(rules, f)
        if v is not None:
            assert check(lay, dataclasses.replace(rules, **{f: v + 1e-6})) == [], f
    k = rules.wire_pitch_diameters
    assert check(lay, dataclasses.replace(rules, wire_pitch_diameters=k * (1 - 1e-6))) == []
    for f in STRICT_FIELDS:
        v = getattr(rules, f)
        if v is not None:
            assert check(lay, dataclasses.replace(rules, **{f: v + 1e-6})), f
    for f in WIDTH_FIELDS:
        v = getattr(rules, f)
        if v is not None:
            assert check(lay, dataclasses.replace(rules, **{f: v + 3e-6})), f
    for f in MAX_FIELDS:
        v = getattr(rules, f)
        if v is not None:
            assert check(lay, dataclasses.replace(rules, **{f: v - 1e-6})), f
    if rec["min_wire_pitch_diameters"] is not None:
        assert check(lay, dataclasses.replace(rules, wire_pitch_diameters=k * (1 + 1e-5)))
    return rules, rec


@pytest.mark.parametrize("seed", range(20))
def test_generator_layouts_clean_under_own_rules(seed):
    assert_self_consistent(generate_layouts(1, seed=seed)[0])


def test_fixture_clean_under_own_rules(fx):
    rules, _ = assert_self_consistent(fx)
    assert rules.max_gate_wire_length is not None and rules.max_kelvin_wire_length is not None


@pytest.mark.parametrize("seed", range(20))
def test_random_fixture_variants_clean_under_own_rules(seed):
    """Seeded jitter of strip gaps and widths, landing points, wire diameter and loop height; each variant is
    DRC-clean under the defaults by construction (asserted) and then measured."""
    rng = np.random.default_rng(seed)
    kw = dict(g1=rng.uniform(1.2, 2.5), w1=rng.uniform(1.2, 2.5), g2=rng.uniform(1.2, 2.2), w2=rng.uniform(1.2, 2.2),
              g3=rng.uniform(1.2, 2.2), w3=rng.uniform(1.2, 2.2), g4=rng.uniform(1.2, 2.4), w4=rng.uniform(1.2, 2.5),
              xa=rng.uniform(11.0, 13.0), xb=rng.uniform(11.0, 13.0), yc=rng.uniform(9.0, 14.0),
              xd=rng.uniform(28.0, 31.0), diam=rng.uniform(0.08, 0.2), loop=rng.uniform(0.3, 1.0))
    rules, rec = assert_self_consistent(fixture(**kw))
    # g1..g4 are the high-voltage signal-to-power gaps (HS strips to DC+, LS strips to PHASE); the others are larger
    sp = [rec[k] for k in ("gap_signal_dcp", "gap_signal_phase", "gap_signal_dcm")]
    assert min(sp) == pytest.approx(M(min(kw["g1"], kw["g2"], kw["g3"], kw["g4"])), abs=1e-12)
    assert rec["min_width_other"] == pytest.approx(M(min(kw["w1"], kw["w2"], kw["w3"], kw["w4"])), abs=1.2e-6)
    assert rules.max_gate_wire_length is not None and rules.max_kelvin_wire_length is not None


def test_mixed_pad_sets_are_self_consistent(fx):
    # die 1 without a Kelvin pad (and wire): the Kelvin limit is measured on die 0 only and die 1 is not checked
    d1 = fx.dies[1]
    lay = dataclasses.replace(fx, dies=[fx.dies[0], dataclasses.replace(
        d1, pads={k: v for k, v in d1.pads.items() if k != "kelvin"})], signal_wires=fx.signal_wires[:3])
    rules, rec = assert_self_consistent(lay)
    assert rules.max_kelvin_wire_length == pytest.approx(fx.signal_wires[1].length, abs=1e-9)
    assert rec["signal_unmeasured"] == {}


def test_pad_without_own_copper_leaves_that_limit_unset(fx):
    # LS die keeps its Kelvin pad but KELVIN_LS copper and the LS Kelvin wire are gone: no Kelvin limit can be met
    # by this layout, so it stays unset (with the reason recorded); the gate limit is still measured
    lay = dataclasses.replace(replace_trace(fx, KELVIN_LS, []), signal_wires=fx.signal_wires[:3])
    rules, rec = assert_self_consistent(lay)
    assert rules.max_kelvin_wire_length is None and rules.max_gate_wire_length is not None
    assert "die 1 (LS)" in rec["signal_unmeasured"]["kelvin"] and KELVIN_LS in rec["signal_unmeasured"]["kelvin"]


def _with_top_band_signals(lay):
    """Generator layout plus four signal strips in two 1 mm bands above the copper (GATE_HS x 10..34 and GATE_LS
    x 36..60, then KELVIN_HS / KELVIN_LS 1 mm higher), a Kelvin pad on every die (top-left corner, mirroring the
    generator's gate pad), and every straight gate / Kelvin wire from a die pad to its own switch's strip that
    keeps the layout DRC-clean under the defaults (LS dies first: they are nearer the bands). None if no room."""
    top = max(t.polygon.bounds[3] for t in lay.traces)
    y0 = top + M(1.0)
    if y0 + M(3.0) > lay.outline.bounds[3] - M(1.0):
        return None
    xs = {"HS": (M(10), M(34)), "LS": (M(36), M(60))}
    ys = {"gate": y0, "kelvin": y0 + M(2.0)}
    strips = [Trace(SIGNAL_NET[(pad, sw)], box(xs[sw][0], ys[pad], xs[sw][1], ys[pad] + M(1.0)))
              for pad in ys for sw in xs]
    dies = []
    for d in lay.dies:
        s = d.w
        pads = dict(d.pads, kelvin=(d.cx - 0.47 * s, d.cy + 0.36 * s, d.cx - 0.36 * s, d.cy + 0.47 * s))
        dies.append(dataclasses.replace(d, pads=pads))
    out = dataclasses.replace(lay, traces=lay.traces + strips, dies=dies)
    assert check(out) == []
    zd = lay.wires[0].points[0, 2]
    order = sorted(range(len(dies)), key=lambda k: dies[k].switch != "LS")
    for k in order:
        d = dies[k]
        for pad in ("gate", "kelvin"):
            g = d.pads[pad]
            x0, y_start = 0.5 * (g[0] + g[2]), 0.5 * (g[1] + g[3])
            lo, hi = xs[d.switch]
            x1 = min(max(x0, lo + M(0.5)), hi - M(0.5))
            net = SIGNAL_NET[(pad, d.switch)]
            w = arc_wire((x0, y_start), (x1, ys[pad] + M(0.5)), zd, 0.0, M(0.5), M(0.1), net)
            trial = dataclasses.replace(out, signal_wires=out.signal_wires + [
                SignalWire(k, pad, net, w.points, w.diameter, w.loop_height)])
            if check(trial) == []:
                out = trial
    return out


def test_synthetic_signal_layouts_on_generator_geometry():
    n_layouts = 0
    kept: dict[str, int] = {}
    for seed in range(20):
        lay = _with_top_band_signals(generate_layouts(1, seed=seed)[0])
        if lay is None:
            continue
        n_layouts += 1
        for w in lay.signal_wires:
            kept[w.net] = kept.get(w.net, 0) + 1
        rules, rec = assert_self_consistent(lay)
        assert rec["signal_unmeasured"] == {}
        assert rules.max_gate_wire_length is not None and rules.max_kelvin_wire_length is not None
    assert n_layouts >= 3
    # wires of all four nets were kept, several per net (paralleled dies of one switch share its island)
    assert all(kept.get(n, 0) >= 5 for n in SIGNAL_NETS), kept



# ---------------------------------------------------------------- T0270: signal-to-power classes, signal-wire ranges

# Potential of each net: DC+, PHASE, DC-; the HS gate/Kelvin nets sit at PHASE potential and the LS ones at DC-
# potential (up to the gate-drive voltage). A gap sees the full DC link unless both sides share a potential.
POTENTIAL = {"DC+": "DC+", "PHASE": "PHASE", "DC-": "DC-",
             GATE_HS: "PHASE", KELVIN_HS: "PHASE", GATE_LS: "DC-", KELVIN_LS: "DC-"}
SIGNAL_POWER_CLASSES = ("signal_dcp", "signal_phase", "signal_dcm", "signal_source", "signal_hs_ls")


@pytest.mark.parametrize("a,b", list(itertools.combinations_with_replacement(
    ("DC+", "PHASE", "DC-", GATE_HS, KELVIN_HS, GATE_LS, KELVIN_LS), 2)))
def test_spacing_class_never_mixes_high_and_low_voltage(a, b):
    # every rule class holds only full-DC-link pairs or only same-potential pairs; the expected class is written
    # out by hand from the potential table above
    expect = {
        frozenset(("DC+", "PHASE")): "dcp_phase", frozenset(("PHASE", "DC-")): "phase_dcm",
        frozenset(("DC+", "DC-")): "dcp_dcm",
        frozenset((GATE_HS, "DC+")): "signal_dcp", frozenset((KELVIN_HS, "DC+")): "signal_dcp",
        frozenset((GATE_LS, "DC+")): "signal_dcp", frozenset((KELVIN_LS, "DC+")): "signal_dcp",
        frozenset((GATE_LS, "PHASE")): "signal_phase", frozenset((KELVIN_LS, "PHASE")): "signal_phase",
        frozenset((GATE_HS, "DC-")): "signal_dcm", frozenset((KELVIN_HS, "DC-")): "signal_dcm",
        frozenset((GATE_HS, "PHASE")): "signal_source", frozenset((KELVIN_HS, "PHASE")): "signal_source",
        frozenset((GATE_LS, "DC-")): "signal_source", frozenset((KELVIN_LS, "DC-")): "signal_source",
        frozenset((GATE_HS, GATE_LS)): "signal_hs_ls", frozenset((GATE_HS, KELVIN_LS)): "signal_hs_ls",
        frozenset((KELVIN_HS, GATE_LS)): "signal_hs_ls", frozenset((KELVIN_HS, KELVIN_LS)): "signal_hs_ls",
    }.get(frozenset((a, b)), "other")
    assert spacing_class(a, b) == spacing_class(b, a) == expect
    hv = POTENTIAL[a] != POTENTIAL[b]
    assert hv == (expect not in ("signal_source", "other"))
    # spacing_for reads exactly that field: give every class a distinct value
    vals = {k: M(1.0 + 0.1 * i) for i, k in enumerate(("dcp_phase", "phase_dcm", "dcp_dcm", "other")
                                                       + SIGNAL_POWER_CLASSES)}
    rules = r(min_spacing=M(9.0), **{f"spacing_{k}": v for k, v in vals.items()})
    assert rules.spacing_for(a, b) == vals[expect]


def tight_lv_reference():
    """Fixture with tight gate-drive-voltage gaps and unchanged high-voltage gaps (hand-computed, mm):
    GATE_LS gets a 1 mm arm 1.0 above its own source DC- (x 20..38.5, y 27.5..28.5, joined by extending the strip to
    y 28.5); KELVIN_LS gets a step (x 36..38.5, y 3.5..4.5) 1.0 below GATE_LS (same switch). The step's corner
    (36, 4.5) is sqrt(5) from PHASE (34, 5.5) and the arm 3.0 / 8.5 from DC+ / GATE_HS, so the high-voltage gaps stay
    those of the fixture: signal-DC+ 2.0, LS signal-PHASE 2.0, HS signal-DC- 3.0, HS-LS signal 3.0."""
    lay = replace_trace(fixture(), GATE_LS, [Trace(GATE_LS, unary_union([mmbox(36, 5.5, 38.5, 28.5),
                                                                         mmbox(20, 27.5, 38.5, 28.5)]))])
    return replace_trace(lay, KELVIN_LS, [Trace(KELVIN_LS, unary_union([mmbox(20, 1.5, 38.5, 3.5),
                                                                         mmbox(36, 3.5, 38.5, 4.5)]))])


def lumped_per_power_net(lay, power):
    """The rejected T0270 model: min gap from any gate/Kelvin copper to ``power`` copper."""
    pw = unary_union([t.polygon for t in lay.traces if t.net == power])
    return min(t.polygon.distance(pw) for t in lay.traces if t.net in SIGNAL_NETS)


def test_tight_lv_reference_measures_each_class_separately():
    ref = tight_lv_reference()
    assert check(ref) == []
    rules, rec = measure_rules(ref)
    expect = {"gap_signal_dcp": 2.0, "gap_signal_phase": 2.0, "gap_signal_dcm": 3.0, "gap_signal_source": 1.0,
              "gap_signal_hs_ls": 3.0, "gap_other_min": 1.0, "gap_dcp_phase": 3.0, "gap_phase_dcm": 3.0}
    for k, v in expect.items():
        assert rec[k] == pytest.approx(M(v), abs=1e-12), k
    for f, v in (("spacing_signal_source", 1.0), ("spacing_signal_dcm", 3.0), ("spacing_signal_hs_ls", 3.0),
                 ("spacing_other", 1.0)):
        assert M(v) - 2e-9 <= getattr(rules, f) <= M(v), f  # floored to whole nm (<= 1 nm + float round-off)
    assert check(ref, rules) == []
    # the lumped model would have given signal-to-DC- 1.0 mm (the LS gate arm to its own source)
    assert lumped_per_power_net(ref, "DC-") == pytest.approx(1e-3, abs=1e-12)


def test_gate_trace_closer_to_dcp_than_reference_fails():
    # task deliverable: reference signal-to-DC+ gap 2.0 mm (every other signal gap of this reference is <= 1.0 mm
    # or not a DC+ gap); derivative GATE_HS 1.0 mm above DC+ (y 16.5..18.5): to DC- 3.0, to PHASE sqrt(10)
    ref = tight_lv_reference()
    rules, _ = measure_rules(ref)
    der = replace_trace(ref, GATE_HS, [Trace(GATE_HS, mmbox(3, 16.5, 17, 18.5))])
    bad = viol(der, rules, "min_spacing")
    assert len(bad) == 1 and pair(bad[0]) == {GATE_HS, "DC+"}
    assert "1.000e-03" in bad[0].message and "2.000e-03" in bad[0].message
    ok = replace_trace(ref, GATE_HS, [Trace(GATE_HS, mmbox(3, 17.5, 17, 19.5))])  # the reference's 2.0 mm passes
    assert viol(ok, rules, "min_spacing") == []
    near = replace_trace(ref, GATE_HS, [Trace(GATE_HS, mmbox(3, 17.49, 17, 19.49))])  # 1.99 mm fails
    assert len(viol(near, rules, "min_spacing")) == 1


def test_hv_signal_gap_cannot_shrink_to_a_gate_drive_gap():
    # review blocker: the reference's LS gate runs 1.0 mm from its own source DC-. A derivative moving the HS gate to
    # 1.0 mm from DC- (x 3..19: to DC- 1.0, DC+ 2.0, PHASE sqrt(5)) puts the full DC link across 1.0 mm.
    ref = tight_lv_reference()
    rules, _ = measure_rules(ref)
    der = replace_trace(ref, GATE_HS, [Trace(GATE_HS, mmbox(3, 17.5, 19, 19.5))])
    bad = viol(der, rules, "min_spacing")
    assert len(bad) == 1 and pair(bad[0]) == {GATE_HS, "DC-"}
    assert "3.000e-03" in bad[0].message
    # the per-power-net lumped value (1.0 mm) would have accepted it
    lumped = dataclasses.replace(rules, spacing_signal_dcm=_floor(lumped_per_power_net(ref, "DC-")))
    assert viol(der, lumped, "min_spacing") == []


def test_hs_ls_signal_gap_cannot_shrink_to_a_same_switch_gap():
    # review major: the reference's tightest signal-signal gap is KELVIN_LS/GATE_LS 1.0 mm (one switch, gate-drive
    # voltage); KELVIN_HS/KELVIN_LS (PHASE vs DC- potential) is 3.0. A derivative with KELVIN_HS extended to
    # x = 18.5 (to KELVIN_LS 1.5, DC+ 2.0, PHASE 2.5) is flagged by the HS-LS class only.
    ref = tight_lv_reference()
    rules, _ = measure_rules(ref)
    der = replace_trace(ref, KELVIN_HS, [Trace(KELVIN_HS, mmbox(3, 1.5, 18.5, 3.5))])
    bad = viol(der, rules, "min_spacing")
    assert len(bad) == 1 and pair(bad[0]) == {KELVIN_HS, KELVIN_LS}
    assert viol(der, dataclasses.replace(rules, spacing_signal_hs_ls=None), "min_spacing") == []  # 1.5 >= other 1.0


def test_gate_drive_gap_may_shrink_to_the_reference_gate_drive_gap():
    # the gate-drive class is not over-strict. Under the tight reference's rules (signal_source 1.0), KELVIN_HS gets a
    # step 1.0 mm below its own source PHASE: strip x 3..33 y 1.5..3.5 plus step x 19..33 y 3.5..4.5 (corner (19, 4.5)
    # to DC+ corner (17, 5.5) sqrt(5) > 2.0). KELVIN_LS moves out of the way to x 36..38.5 y 1.0..3.0 (to KELVIN_HS
    # 3.0, GATE_LS 2.5, PHASE sqrt(2^2 + 2.5^2)).
    rules, _ = measure_rules(tight_lv_reference())
    lay = replace_trace(fixture(), KELVIN_HS, [Trace(KELVIN_HS, unary_union([mmbox(3, 1.5, 33, 3.5),
                                                                             mmbox(19, 3.5, 33, 4.5)]))])
    lay = replace_trace(lay, KELVIN_LS, [Trace(KELVIN_LS, mmbox(36, 1.0, 38.5, 3.0))])
    kh = next(t for t in lay.traces if t.net == KELVIN_HS).polygon
    assert kh.distance(next(t for t in lay.traces if t.net == "PHASE").polygon) == pytest.approx(1e-3, abs=1e-12)
    assert viol(lay, rules, "min_spacing") == []
    bad = viol(lay, dataclasses.replace(rules, spacing_signal_source=M(1.01)), "min_spacing")
    assert len(bad) == 1 and pair(bad[0]) == {KELVIN_HS, "PHASE"}


def _floor(v):
    return math.floor(v * 1e9) / 1e9


def test_signal_to_power_is_per_power_net(fx):
    rules, _ = measure_rules(fx)
    # fixture: signal-to-DC+ and LS-signal-to-PHASE gaps are 2 mm, HS-signal-to-DC- 3 mm (GATE_HS)
    assert rules.spacing_signal_dcm > rules.spacing_signal_dcp
    # GATE_HS moved up to y 18.5..20.5 and lengthened to x 17.5: to DC- 2.5 (< 3.0), to DC+ 3.0, to PHASE
    # sqrt(2.5^2 + 3^2) = 3.9 (>= the gate-drive class sqrt(13) = 3.61): fails the DC- value only
    lay = replace_trace(fx, GATE_HS, [Trace(GATE_HS, mmbox(3, 18.5, 17.5, 20.5))])
    bad = viol(lay, rules, "min_spacing")
    assert len(bad) == 1 and pair(bad[0]) == {GATE_HS, "DC-"}


def test_signal_fields_fall_back_to_spacing_other_then_min_spacing(fx):
    # unset: the old behaviour (spacing_other governs every non-power pair, min_spacing under it)
    assert len(viol(fx, r(spacing_other=M(2.01)), "min_spacing")) == 4
    assert len(viol(fx, r(min_spacing=M(2.01)), "min_spacing")) >= 4
    # set: the signal values govern their pairs, spacing_other only the remaining ones
    bad = viol(fx, r(spacing_other=M(2.0), spacing_signal_dcp=M(2.01), spacing_signal_phase=M(2.01)),
               "min_spacing")
    assert len(bad) == 4
    loose = dict(spacing_signal_dcp=M(1.0), spacing_signal_phase=M(1.0), spacing_signal_dcm=M(1.0),
                 spacing_signal_source=M(1.0), spacing_signal_hs_ls=M(1.0))
    only_other = viol(fx, r(spacing_other=M(2.9), **loose), "min_spacing")
    assert len(only_other) == 1 and pair(only_other[0]) == {GATE_LS, KELVIN_LS}  # same switch, sqrt(8) < 2.9
    # unset HS-LS / gate-drive classes fall back to spacing_other: KELVIN_HS/KELVIN_LS 3.0, signal-source sqrt(13)
    assert len(viol(fx, r(spacing_other=M(3.01), spacing_signal_dcp=M(1.0), spacing_signal_phase=M(1.0),
                          spacing_signal_dcm=M(1.0)), "min_spacing")) == 2
    assert len(viol(fx, r(spacing_other=M(3.7), spacing_signal_dcp=M(1.0), spacing_signal_phase=M(1.0),
                          spacing_signal_dcm=M(1.0)), "min_spacing")) == 2 + 3  # + GATE_HS, KELVIN_HS to PHASE, GATE_LS to DC-


def test_signal_wire_diameter_range(fx):
    for bad_d in (0.0, -M(0.1), M(0.6)):
        lay = with_sig(fx, 0, diameter=bad_d)
        assert "signal_wire_diameter" in rule_names(lay), bad_d
    assert "signal_wire_diameter" not in rule_names(with_sig(fx, 0, diameter=M(0.025)))  # thin gate wire is fine
    assert "signal_wire_diameter" in rule_names(with_sig(fx, 0, diameter=0.0), r(min_signal_wire_diameter=-1.0))
    rr = r(min_signal_wire_diameter=M(0.11))
    assert [v.rule for v in viol(fx, rr, "signal_wire_diameter")] == ["signal_wire_diameter"] * 4
    rr = r(max_signal_wire_diameter=M(0.09))
    assert len(viol(fx, rr, "signal_wire_diameter")) == 4
    rr = r(min_signal_wire_diameter=M(0.1), max_signal_wire_diameter=M(0.1))
    assert viol(fx, rr, "signal_wire_diameter") == []


def test_signal_wire_length_range(fx):
    lens = [w.length for w in fx.signal_wires]
    lo, hi = min(lens), max(lens)
    assert viol(fx, r(min_signal_wire_length=lo, max_signal_wire_length=hi), "signal_wire_length") == []
    assert len(viol(fx, r(max_signal_wire_length=hi - 1e-6), "signal_wire_length")) >= 1
    assert len(viol(fx, r(min_signal_wire_length=lo + 1e-6), "signal_wire_length")) >= 1
    assert viol(fx, DEFAULT_RULES, "signal_wire_length") == []  # not enforced by default


def test_general_signal_length_limit_does_not_loosen_a_per_pad_limit(fx):
    # review minor: the upper bound is the smaller of the general and the per-pad limit
    gate = max(w.length for w in fx.signal_wires if w.pad == "gate")
    tight = r(max_gate_wire_length=gate - 1e-6, max_signal_wire_length=1.0)  # 1 m general limit
    assert len(viol(fx, tight, "signal_wire_length")) >= 1
    assert tight.signal_length_range("gate") == (-math.inf, gate - 1e-6)
    assert r(max_gate_wire_length=1.0, max_signal_wire_length=0.5).signal_length_range("gate")[1] == 0.5
    assert r(max_signal_wire_length=0.5).signal_length_range("kelvin")[1] == 0.5
    assert r().signal_length_range("gate") == (-math.inf, math.inf)


def test_measure_rules_reports_signal_wire_ranges(fx):
    rules, rec = measure_rules(fx)
    lens = [w.length for w in fx.signal_wires]
    assert rec["signal_wire_length_range"] == (min(lens), max(lens))
    assert rules.min_signal_wire_length == pytest.approx(min(lens), abs=2e-9)
    assert rules.min_signal_wire_length <= min(lens)
    assert rules.max_signal_wire_length == pytest.approx(max(lens), abs=2e-9)
    assert rules.max_signal_wire_length >= max(lens)
    assert rec["signal_wire_diameter_range"] == (M(0.1), M(0.1))
    # a derivative with a 0.2 mm gate wire is outside the reference's measured range
    assert [v.rule for v in viol(with_sig(fx, 0, diameter=M(0.2)), rules, "signal_wire_diameter")] == \
        ["signal_wire_diameter"]
    # a derivative with a shorter wire than any reference signal wire
    short = with_pts(fx, 0, [list(p) for p in fx.signal_wires[0].points[:2]])
    assert "signal_wire_length" in rule_names(short, rules)


@pytest.mark.parametrize("d", [0.0, -M(0.1)])
def test_measure_rules_survives_degenerate_signal_wire_diameters(fx, d):
    lay = fx
    for k in range(4):
        lay = with_sig(lay, k, diameter=d)
    assert "signal_wire_diameter" in rule_names(lay)  # flagged by the DRC ...
    rules, rec = measure_rules(lay)  # ... and measuring neither raises nor returns a non-physical value
    assert rec["min_wire_pitch_diameters"] is None or rec["min_wire_pitch_diameters"] > 0
    assert rules.wire_pitch_diameters > 0
    assert rec["n_nonpositive_signal_wire_diameters"] == 4
    assert rec["signal_wire_diameter_range"] is None
    assert rules.min_signal_wire_diameter is None and rules.max_signal_wire_diameter is None
    assert "signal_wire_diameter" in rule_names(lay, rules)  # still flagged under the measured rules
    # one degenerate wire among valid ones: the measured range is that of the valid ones
    _, rec1 = measure_rules(with_sig(fx, 0, diameter=d))
    assert rec1["signal_wire_diameter_range"] == (M(0.1), M(0.1))
    assert rec1["n_nonpositive_signal_wire_diameters"] == 1


def test_measure_rules_values_are_physical_with_signal_wires(fx):
    rules, rec = measure_rules(fx)
    assert 0 < rec["min_wire_pitch"] < 0.05
    assert 0 < rec["min_wire_pitch_diameters"] < 100
    for k in ("gap_signal_dcp", "gap_signal_phase", "gap_signal_dcm", "gap_signal_source", "gap_signal_hs_ls"):
        assert 0 < rec[k] < 0.04, k  # inside the 40 x 30 mm substrate
    assert rules.wire_pitch_diameters > 0 and rules.min_signal_wire_diameter > 0
    assert 0 < rules.min_signal_wire_length <= rules.max_signal_wire_length < 0.05


def test_fingerprint_independent_of_die_index_type(fx):
    base = fx.fingerprint()
    assert with_sig(fx, 0, die=np.int64(0)).fingerprint() == base
    assert with_sig(fx, 0, die=np.int32(0)).fingerprint() == base
    assert with_sig(fx, 0, die=1).fingerprint() != base  # still sensitive to the value
    assert check(with_sig(fx, 0, die=np.int64(0))) == []
