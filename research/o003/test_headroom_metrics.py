"""Hand-computed cases for the O003 headroom metrics draft (T0261). The body below the marker is appended verbatim to
tests/mfos/test_metrics.py by make_patch.py, where ``mx`` is mfos.metrics."""
import importlib.util
import math
from pathlib import Path

import numpy as np
import pytest

import headroom_metrics as mx

REPO = Path(__file__).resolve().parents[2]

# >>> shared tests


# ------------------------------------------------------------------------------------------------ O003 headroom
NH = 1e-9


def _o3_layout(rid, lid, role, l_nh, band=(0.0, 0.0, 0.0, 0.0)):
    """band = (dl, dc, df, dw) in nH: L(0.5 mm) = L + dl, L(5/3/3) = L(0.5) + dc, L(20/12/12) = L(0.5) + df,
    L(wire) = L(0.5) + dw; None leaves the band columns empty."""
    row = {"kind": "layout", "reference_id": rid, "layout_id": lid, "role": role, "L_sub_H": l_nh * NH}
    if band is not None:
        dl, dc, df, dw = band
        c05 = l_nh + dl
        row.update(L_sub_c05_H=c05 * NH, L_sub_thk_c_H=(c05 + dc) * NH, L_sub_thk_f_H=(c05 + df) * NH,
                   L_sub_wire_f_H=(c05 + dw) * NH)
    return row


def _o3_dies(rid, lid, dies):
    return [{"kind": "die", "reference_id": rid, "layout_id": lid, "die_id": f"d{i}", "Tj_l0_K": d[0],
             "Tj_l1_K": d[1], "Tj_l2_K": d[2]} for i, d in enumerate(dies)]


def _o3_case(rid="R1", *, twin=10.0, recon=None, cands=(), l_term=7.0, admissible=True, s_ref=None, l1=(10.0, 10.0),
             tw_dies=((350.0,) * 3,) * 2, rec_dies=None, cand_t=350.0, cand_dies=None, no_dies=()):
    """One reference: twin and reconstruction (zero band), ``cands`` = [(L_nH, band)] padded to the 16-candidate
    shortlist with candidates at 1.2 x twin + k x 0.01 nH; candidate dies at cand_t unless cand_dies[k] gives them;
    s_ref = None puts the reference on the 0.5 mm grid, else off-grid with L(0.25 snap) / L(0.5 snap) = 1 + s_ref / 2."""
    ref = {"kind": "reference", "reference_id": rid, "admissible": admissible, "L_term_H": l_term * NH,
           "on_grid": s_ref is None, "L1_min_first5000_H": l1[0] * NH, "L1_min_all_H": l1[1] * NH}
    if s_ref is not None:
        ref.update(L_snap025_H=(1.0 + s_ref / 2) * 10 * NH, L_snap05_H=10 * NH, L_snapchk0125_H=None,
                   L_snapchk05_H=None)
    rows = [ref]
    if not admissible:
        return rows
    rows += [_o3_layout(rid, "twin", "twin", twin), _o3_layout(rid, "recon", "reconstruction", recon or twin)]
    rows += _o3_dies(rid, "twin", tw_dies) + _o3_dies(rid, "recon", rec_dies or tw_dies)
    full = list(cands) + [(1.2 * twin + 0.01 * k, (0.0, 0.0, 0.0, 0.0)) for k in range(16 - len(cands))]
    for k, (lk, band) in enumerate(full):
        lid = f"c{k:02d}"
        rows.append(_o3_layout(rid, lid, "candidate", lk, band))
        if k not in no_dies:
            rows += _o3_dies(rid, lid, (cand_dies or {}).get(k, ((cand_t,) * 3,) * 2))
    return rows


def test_o003_ratio_band_estimate_by_hand_and_against_p3():
    one = [1.0] * 5
    # monotone thickness: e21 = 0.001, e32 = 0.004, r^p = 4 -> 1.25 x 0.001 x 4 / 3
    assert mx.ratio_band_estimate([0.8, 0.8, 0.804, 0.799, 0.8], one) == pytest.approx(1.25 * 0.001 * 4 / 3)
    # oscillatory thickness 3 max(|e21|, |e32|) = 0.006; lateral 3 x 0.002; wire 3 x 0.001
    assert mx.ratio_band_estimate([0.802, 0.8, 0.802, 0.801, 0.801], one) == pytest.approx(0.006 + 0.006 + 0.003)
    assert mx.ratio_band_estimate([8.0, 8.0, 8.0, 8.0, 8.0], [10.0] * 5) == 0.0  # ratios equal at every level
    spec = importlib.util.spec_from_file_location("o006_p3", REPO / "research" / "scripts" / "o006_p3_em_convergence.py")
    p3 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(p3)
    rng = np.random.default_rng(20261109)
    for fc, fm, ff in 1.0 + 1e-3 * rng.normal(size=(500, 3)):
        assert mx.ratio_middle_term(fc, fm, ff) == pytest.approx(p3.middle_term(fc, fm, ff, 2.0)[1], rel=1e-9)
    with pytest.raises(ValueError):
        mx.ratio_band_estimate([1.0] * 4, one)


def test_o003_snapping_bias_and_tj_bounds_by_hand():
    assert mx.snapping_bias(True, None, None) == 0.0
    assert mx.snapping_bias(False, 10.1, 10.0) == pytest.approx(0.02)
    assert mx.snapping_bias(False, 10.1, 10.0, 10.3, 10.0) == pytest.approx(0.03)  # the snapping check is larger
    assert mx.snapping_bias(False, 10.1, 10.0, 10.05, 10.0) == pytest.approx(0.02)
    with pytest.raises(ValueError):
        mx.snapping_bias(False, 10.1, 10.0, 10.3, None)
    # die 0: rho 1/2 -> GCI 1.25 x 0.25 = 0.3125; die 1: divergent (rho = 1) -> +inf, drops out of the lower bound
    t = mx.tj_bounds([(350.0, 350.5, 350.75), (351.0, 352.0, 353.0)])
    assert t == (353.0, math.inf, math.inf, pytest.approx(350.75 - 0.3125), 1)
    assert mx.tj_bounds([(351.0, 352.0, 353.0)])[3] == -math.inf  # nothing bounds W from below


def test_o003_twin_case_gives_minus_and_plus_a_sref():
    rows = _o3_case(s_ref=0.02, cands=[(12.0, (0.0, 0.0, 0.0, 0.0))])
    a = 10.0 / 17.0
    assert mx.headroom_min_lo(rows) == pytest.approx(-a * 0.02)
    assert mx.headroom_max_hi_ind(rows) == pytest.approx(a * 0.02)
    per = mx.headroom_per_reference(rows)["R1"]
    assert per["best_id"] is None and per["r"] == 1.0 and per["e_R"] == 0.0 and per["near_tie_h_hi"] == {}


def test_o003_no_eligible_candidate():
    # every checked candidate is 10 K hotter than the twin: 8 checked (two batches), none eligible -> twin rule for A1;
    # K1 ignores Tj: inductance-only best 8 nH, e_R 0, w_ind 0.02, h_hi = a (1 - 0.8 x 0.98)
    rows = _o3_case(s_ref=0.02, cands=[(8.0, (0.0, 0.0, 0.0, 0.0))], cand_t=360.0)
    a = 10.0 / 17.0
    per = mx.headroom_per_reference(rows)["R1"]
    assert per["n_thermal_checked"] == 8 and per["n_tj_rejected"] == 8 and per["best_id"] is None
    assert mx.headroom_min_lo(rows) == pytest.approx(-a * 0.02)
    assert mx.headroom_max_hi_ind(rows) == pytest.approx(a * (1 - 0.8 * 0.98))


def test_o003_non_levelled_is_inf_and_checked_before_the_twin_rule():
    a = 10.0 / 17.0
    twin_wins = dict(s_ref=0.02, cands=[(12.0, (0.0, 0.0, 0.0, 0.0))])
    assert mx.headroom_max_hi_ind(_o3_case(**twin_wins, l1=(10.5, 10.0))) == math.inf  # 10.5 > 1.02 x 10.0
    assert mx.headroom_max_hi_ind(_o3_case(**twin_wins, l1=(10.19, 10.0))) == pytest.approx(a * 0.02)  # levelled
    assert mx.headroom_min_lo(_o3_case(**twin_wins, l1=(10.5, 10.0))) == pytest.approx(-a * 0.02)  # A1 unaffected
    with pytest.raises(ValueError):  # first-5,000 minimum below the all-20,000 minimum is inconsistent data
        mx.headroom_max_hi_ind(_o3_case(**twin_wins, l1=(9.9, 10.0)))


def test_o003_near_tie_takes_the_largest_h_hi():
    # w_ind = 0 + 0.02: near ties up to 8.16 nH. c01 at 8.1 nH has L(0.5) = 8.15 nH: e_R = 3 x 0.005 = 0.015, w = 0.05,
    # h_hi = a (1 - 0.81 x 0.95) = a 0.2305 > c00's a (1 - 0.8 x 0.98) = a 0.216; c02 at 8.2 nH is outside despite its
    # wide band
    rows = _o3_case(s_ref=0.02, cands=[(8.0, (0.0, 0.0, 0.0, 0.0)), (8.1, (0.05, 0.0, 0.0, 0.0)),
                                       (8.2, (1.0, 0.0, 0.0, 0.0))])
    a = 10.0 / 17.0
    per = mx.headroom_per_reference(rows)["R1"]
    assert sorted(per["near_tie_h_hi"]) == ["c00", "c01"]
    assert per["near_tie_h_hi"]["c00"] == pytest.approx(a * 0.216)
    assert mx.headroom_max_hi_ind(rows) == pytest.approx(a * (1 - 0.81 * 0.95))
    assert mx.headroom_min_lo(rows) == pytest.approx(a * (1 - 0.8 * 1.02))  # A1 best is c00 (meets the Tj test)


def test_o003_inf_gci_on_candidate_fails_and_on_twin_drops_out():
    a, s = 10.0 / 17.0, 0.02
    best = [(8.0, (0.0, 0.0, 0.0, 0.0))]
    # on C: die (350, 350.5, 351) has rho = 1 -> +inf -> fails; with (350, 350.5, 350.75) it passes (351.06 - 350 <= 2)
    bad = _o3_case(s_ref=s, cands=best, cand_dies={0: [(350.0, 350.5, 351.0)]})
    good = _o3_case(s_ref=s, cands=best, cand_dies={0: [(350.0, 350.5, 350.75)]})
    assert mx.headroom_min_lo(bad) == pytest.approx(-a * s)
    assert mx.headroom_per_reference(bad)["R1"]["n_tj_inf"] == 1
    assert mx.headroom_min_lo(good) == pytest.approx(a * (1 - 0.8 * (1 + s)))
    # on W: die B (383, 383.5, 384) diverges and drops out, so W's lower bound is die A's 380 K and a 383 K candidate
    # fails (3 K > 2 K); were B counted at 384 K it would pass. The optimistic test passes (W's upper bound is +inf).
    tw = [(380.0, 380.0, 380.0), (383.0, 383.5, 384.0)]
    rows = _o3_case(s_ref=s, cands=best, tw_dies=tw, rec_dies=[(380.0,) * 3], cand_dies={0: [(383.0,) * 3]})
    per = mx.headroom_per_reference(rows)["R1"]
    assert per["gate_a2"] and per["best_id"] is None and per["h_lo"] == pytest.approx(-a * s)
    assert per["opt_id"] == "c00" and per["h_opt_hi"] == pytest.approx(a * (1 - 0.8 * (1 - s)))


def test_o003_f3_batches_and_extra_thermal_rows():
    a = 10.0 / 17.0
    cands = [(8.0 + 0.1 * k, (0.0, 0.0, 0.0, 0.0)) for k in range(6)]
    hot = {k: [(360.0,) * 3] for k in range(4)}
    rows = _o3_case(cands=cands, cand_dies=hot)  # batch 1 all fail; c04 (8.4 nH) in batch 2 is best
    per = mx.headroom_per_reference(rows)["R1"]
    assert per["best_id"] == "c04" and per["n_thermal_checked"] == 8
    assert per["h_lo"] == pytest.approx(a * (1 - 0.84))
    # c02 passes in batch 1: stop after it; batch 2 needs no thermal rows; best is the lowest eligible, c02
    rows = _o3_case(cands=cands, cand_dies={0: [(360.0,) * 3], 1: [(360.0,) * 3]}, no_dies=range(4, 16))
    assert mx.headroom_per_reference(rows)["R1"]["best_id"] == "c02"
    with pytest.raises(ValueError):  # a candidate F3 must check has no thermal rows
        mx.headroom_min_lo(_o3_case(cands=cands, no_dies=(1,)))


def test_o003_counted_references_and_twin_gates():
    a = 10.0 / 17.0
    r1 = _o3_case("R1", s_ref=0.02, cands=[(7.0, (0.0, 0.0, 0.0, 0.0))])  # h_lo = a (1 - 0.7 x 1.02)
    excluded = _o3_case("R0", admissible=False)
    a1_fail = _o3_case("R2", s_ref=0.02, recon=10.5, cands=[(9.5, (0.0, 0.0, 0.0, 0.0))])  # |1 - 10/10.5| > 0.02
    a1_pass = _o3_case("R2", s_ref=0.02, recon=10.15, cands=[(9.5, (0.0, 0.0, 0.0, 0.0))])  # 0.0148 <= 0.02
    a2_fail = _o3_case("R3", cands=[(9.5, (0.0, 0.0, 0.0, 0.0))], rec_dies=[(353.0,) * 3])  # 3 K > G sum 0
    single = r1 + excluded + a1_fail + a2_fail
    per = mx.headroom_per_reference(single)
    assert [k for k, v in per.items() if v["counted"]] == ["R1"]
    assert not per["R2"]["gate_a1"] and per["R2"]["gate_a2"] and not per["R3"]["gate_a2"]
    assert mx.headroom_min_lo(single) == pytest.approx(a * (1 - 0.7 * 1.02))
    assert mx.headroom_max_hi_ind(single) == pytest.approx(a * (1 - 0.7 * 0.98))
    both = r1 + a1_pass
    assert mx.headroom_min_lo(both) == pytest.approx(a * (1 - 0.95 * 1.02))  # R2 counted and lower
    with pytest.raises(ValueError):  # no counted reference: INVALID
        mx.headroom_min_lo(excluded + a1_fail + a2_fail)


@pytest.mark.parametrize("l_sub, l_term, pass_from, kill_below", [(10.0, 0.0, 0.216, 0.082), (10.0, 7.0, 0.353, 0.153),
                                                                    (20.0, 7.0, 0.284, 0.117)])
def test_o003_verdict_region_examples_of_the_notes(l_sub, l_term, pass_from, kill_below):
    """O003 notes: a = 1, w = 0.02: PASS from 0.216, kill below 0.082; 10 nH + 7 nH: 0.353 / 0.153; 20 nH: 0.284 / 0.117."""
    w = 0.02
    a = l_sub / (l_sub + l_term)
    h_pass, h_kill = 1 - (1 - 0.20 / a) / (1 + w), 1 - (1 - 0.10 / a) / (1 - w)
    assert round(h_pass, 3) == pass_from and round(h_kill, 3) == kill_below

    def rows(h_sub):
        return _o3_case(twin=l_sub, l_term=l_term, s_ref=w, l1=(l_sub, l_sub),
                        cands=[(l_sub * (1 - h_sub), (0.0, 0.0, 0.0, 0.0))])
    assert mx.headroom_min_lo(rows(h_pass + 1e-6)) >= 0.20 > mx.headroom_min_lo(rows(h_pass - 1e-6))
    assert mx.headroom_max_hi_ind(rows(h_kill - 1e-6)) < 0.10 <= mx.headroom_max_hi_ind(rows(h_kill + 1e-6))


def test_o003_sensitivity_and_reconstruction_based_secondary():
    rows = _o3_case(s_ref=0.02, recon=10.1, cands=[(8.0, (0.0, 0.0, 0.0, 0.0))])
    assert mx.headroom_min_lo(rows, params={"L_term_H": 0.0}) == pytest.approx(1 - 0.8 * 1.02)
    assert mx.headroom_min_lo(rows, params={"L_term_H": 17.5e-9}) == pytest.approx(10 / 27.5 * (1 - 0.8 * 1.02))
    assert mx.headroom_max_hi_ind(rows, params={"L_term_H": 0.0}) == pytest.approx(1 - 0.8 * 0.98)
    ar = 10.1 / 17.1
    assert mx.headroom_min_lo(rows, params={"comparator": "reconstruction"}) == pytest.approx(
        ar * (1 - 8.0 / 10.1 * 1.02))
    assert mx.headroom_max_hi_ind(rows, params={"comparator": "reconstruction"}) == pytest.approx(
        ar * (1 - 8.0 / 10.1 * 0.98))
    with pytest.raises(ValueError):
        mx.headroom_min_lo(rows, params={"L_term": 0.0})  # mistyped key


def test_o003_dispatch_and_declared_null():
    rows = _o3_case(s_ref=0.02, cands=[(8.0, (0.0, 0.0, 0.0, 0.0))])
    for r in rows:  # the null column of the row contract: the twin's L_sub on candidate rows, the row's own elsewhere
        r["L_sub_null_H"] = 10.0 * NH if r.get("role") == "candidate" else r.get("L_sub_H", 10.0 * NH)
    a = 10.0 / 17.0
    assert mx.compute("headroom_min_lo", rows, pred="L_sub_H") == pytest.approx(a * (1 - 0.8 * 1.02))
    assert mx.compute("headroom_max_hi_ind", rows, params={"L_term_H": 0.0}) == pytest.approx(1 - 0.8 * 0.98)
    nrows = [{**r, "__null__": v} for r, v in zip(rows, mx.null_column(rows, "column", None, column="L_sub_null_H"),
                                                  strict=True)]
    assert mx.compute("headroom_min_lo", nrows, pred="__null__") == pytest.approx(-a * 0.02)  # fails A1 by construction


@pytest.mark.parametrize("mutate", [
    lambda rows: rows.append(dict(rows[1])),  # a second twin row (duplicate layout id)
    lambda rows: rows.append(dict(rows[0])),  # a second reference row
    lambda rows: [r.update(role="candidate") for r in rows if r.get("layout_id") == "recon"],  # no reconstruction
    lambda rows: [r.pop("L_sub_c05_H") for r in rows if r.get("layout_id") == "c00" and r["kind"] == "layout"],
    lambda rows: rows[0].update(admissible="yes"),
    lambda rows: [rows.remove(r) for r in [r for r in rows if r.get("layout_id") == "c15" and r["kind"] == "layout"]],
    lambda rows: rows[0].pop("L1_min_all_H"),
    lambda rows: rows[0].update(L_term_H=math.nan),
])
def test_o003_fail_closed(mutate):
    rows = _o3_case(s_ref=0.02, cands=[(8.0, (0.0, 0.0, 0.0, 0.0))])
    mutate(rows)
    with pytest.raises(ValueError):  # at least one of the two metrics must refuse the rows
        mx.headroom_min_lo(rows)
        mx.headroom_max_hi_ind(rows)
