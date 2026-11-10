"""Search driver tests with fake solvers (no physics): ordering, batch-and-stop, null reuse, near ties, levelling,
control mode, resume, determinism."""
import math
import zlib

import numpy as np
import pytest

from moduleforge.optimize.search import (SearchConfig, Solvers, Store, band_e_R, candidate_stream, conservative_margin,
                                         run_control, run_search)

CFG = SearchConfig(n_candidates=200, n_first=50, shortlist=16, batch=4, max_checks=8, chunk=64)


class Fake:
    def __init__(self, name):
        self.name = name

    def fingerprint(self):
        return self.name


def _u(name, salt):
    return float(np.random.default_rng(zlib.crc32((name + salt).encode())).random())


def gen(spec, m, seed):
    return [Fake(f"s{seed}_{j}") for j in range(m)]


def thermal_result(name, tj, gci):
    """A thermal result with every field the driver requires."""
    return {"tj": tj, "gci": gci, "tj_max_node": [[[0.0, 0.0, 0.0]] * 2] * 3, "nodes": [100, 800, 6400],
            "fingerprint": name, "energy_balance": 1e-4, "picard": {"converged": True, "iters": 3}}


class Counter:
    def __init__(self, thermal_fn=None, lsub_fn=None, e_R=0.0, l1_fn=None):
        self.calls = {"l1": 0, "l_sub": 0, "band": 0, "thermal": 0}
        self.thermal_fn = thermal_fn or (lambda n: (np.full((3, 2), 400.0), np.full(2, 0.1)))
        self.lsub_fn = lsub_fn or (lambda n: 10e-9 * (1 + _u(n, "l1")) * (1 + 0.05 * _u(n, "d")))
        self.l1_fn = l1_fn or (lambda n: 10e-9 * (1 + _u(n, "l1")))
        self.eR = e_R
        self.thermal_log = []

    def solvers(self):
        def tick(k, v):
            self.calls[k] += 1
            return v
        return Solvers(
            l1=lambda lay: tick("l1", self.l1_fn(lay.name)),
            l_sub=lambda lay: tick("l_sub", self.lsub_fn(lay.name)),
            band=lambda lay: tick("band", self._band(lay.name)),
            thermal=lambda lay, P: (self.thermal_log.append(lay.name), tick("thermal", self._th(lay.name)))[1])

    def _band(self, n):
        # band_e_R(candidate, comparator) = 3 |R(0.25) - R(0.5)| = self.eR for every search candidate; reference,
        # twin and degraded layouts have a flat band
        if n in ("ref", "twin", "D"):
            return [1.0] * 5
        return [1.0 + self.eR / 3.0, 1.0, 1.0, 1.0, 1.0]

    def _th(self, n):
        tj, g = self.thermal_fn(n)
        return thermal_result(n, tj, g)


def hot_unless(good):
    """Tj 400 K for the twin/ref, 500 K for any candidate not in ``good``."""
    def f(n):
        if n.startswith("s") and n not in good:
            return np.full((3, 2), 500.0), np.full(2, 0.1)
        return np.full((3, 2), 400.0), np.full(2, 0.1)
    return f


def shortlist_by_l1(seed, cnt, cfg=CFG):
    c = Counter()
    names = [f.name for f in candidate_stream(None, cnt, seed, gen, cfg.chunk)]
    return sorted(names, key=lambda n: (c.l1_fn(n), names.index(n)))[:cfg.shortlist]


def go(c, seed=5, cfg=CFG, wd=None, s_ref=0.01):
    return run_search(None, Fake("ref"), Fake("twin"), seed, c.solvers(), 50.0, s_ref, wd, cfg, gen)


def test_conservative_margin_formula_and_inf():
    w = {"tj": [[0] * 2, [0] * 2, [400.0, 390.0]], "gci": [1.0, 2.0]}
    c = {"tj": [[0] * 2, [0] * 2, [401.0, 395.0]], "gci": [0.5, 0.25]}
    # max(401.5, 395.25) - max(399, 388) = 2.5
    assert conservative_margin(c, w) == pytest.approx(2.5)
    c["gci"] = [math.inf, 0.0]
    assert conservative_margin(c, w) == math.inf
    # twin die with inf GCI drops out of the lower bound: max(-inf, 388) = 388
    w["gci"] = [math.inf, 2.0]
    c["gci"] = [0.5, 0.25]
    assert conservative_margin(c, w) == pytest.approx(401.5 - 388.0)
    w["gci"] = [math.inf, math.inf]
    assert conservative_margin(c, w) == math.inf


def test_stream_determinism_and_count():
    a = [x.name for x in candidate_stream(None, 150, 9, gen, 64)]
    assert len(a) == 150 and len(set(a)) == 150
    assert a == [x.name for x in candidate_stream(None, 150, 9, gen, 64)]
    assert a != [x.name for x in candidate_stream(None, 150, 10, gen, 64)]


def test_shortlist_and_levelling_record():
    c = Counter()
    r = go(c)
    names = [f.name for f in candidate_stream(None, 200, 5, gen, 64)]
    l1 = [c.l1_fn(n) for n in names]
    assert c.calls["l1"] == 200 + 1  # pool + the twin (pool statistics)
    assert r.levelling["l1_min_all"] == min(l1)
    assert r.levelling["l1_min_first"] == min(l1[:50])
    assert r.levelling["l1_min_first"] >= r.levelling["l1_min_all"]
    rows = r.rows["candidates"]
    assert [x["fingerprint"] for x in rows] == shortlist_by_l1(5, 200)
    assert [x["l1"] for x in rows] == sorted(x["l1"] for x in rows)
    assert all(x["l_sub"] == c.lsub_fn(x["fingerprint"]) for x in rows)
    assert c.calls["l_sub"] == 16 + 2  # shortlist + reference + twin
    exp_lev = r.levelling["l1_min_first"] <= (1 + r.w_ind) * r.levelling["l1_min_all"]
    assert r.levelling["levelled"] == exp_lev


def test_levelling_flag_false_when_best_comes_late():
    # best L1 only after the first 50 candidates
    names = [f.name for f in candidate_stream(None, 200, 5, gen, 64)]
    late = names[120]
    c = Counter(l1_fn=lambda n: 5e-9 if n == late else 20e-9 + 1e-9 * _u(n, "x"))
    r = go(c, s_ref=0.0)
    assert r.levelling["l1_min_all"] == 5e-9 and r.levelling["levelled"] is False
    # best inside the first 50 -> levelled
    early = names[3]
    c = Counter(l1_fn=lambda n: 5e-9 if n == early else 20e-9 + 1e-9 * _u(n, "x"))
    assert go(c, s_ref=0.0).levelling["levelled"] is True


def test_a1_checks_in_ascending_lsub_batches_stop_after_first_passing_batch():
    c0 = Counter()
    r0 = go(c0)
    by_lsub = sorted((x["l_sub"], x["fingerprint"]) for x in r0.rows["candidates"])
    asc = [n for _, n in by_lsub]
    assert r0.inductance_best == asc[0]
    # pass only the 2nd-in-batch of the first batch -> stops after batch 1 (4 checks); best = asc[1]
    c = Counter(thermal_fn=hot_unless({asc[1]}))
    r = go(c)
    a1 = [n for n in c.thermal_log if n in asc][:4]
    assert a1 == asc[:4]
    assert r.a1_best == asc[1]
    # all four of the first batch were solved even though asc[1] passed
    assert set(asc[:4]) <= set(c.thermal_log)
    # the second batch is not part of A1: no A1 row for asc[4:8]
    assert not {x["fingerprint"] for x in r.rows["checks"] if x["role"] == "a1"} & set(asc[4:8])
    a1_rows = [x for x in r.rows["checks"] if x["role"] == "a1"]
    assert [x["fingerprint"] for x in a1_rows] == asc[:4]


def test_a1_second_batch_and_cap_of_eight():
    c0 = Counter()
    asc = [n for _, n in sorted((x["l_sub"], x["fingerprint"]) for x in go(c0).rows["candidates"])]
    c = Counter(thermal_fn=hot_unless({asc[6]}))
    r = go(c)
    a1_rows = [x["fingerprint"] for x in r.rows["checks"] if x["role"] == "a1"]
    assert a1_rows == asc[:8] and r.a1_best == asc[6]
    # none pass: exactly 8 A1 checks, never a ninth
    c = Counter(thermal_fn=hot_unless(set()))
    r = go(c)
    a1_rows = [x["fingerprint"] for x in r.rows["checks"] if x["role"] == "a1"]
    assert a1_rows == asc[:8] and r.a1_best is None


def test_inf_gci_candidate_fails():
    c0 = Counter()
    asc = [n for _, n in sorted((x["l_sub"], x["fingerprint"]) for x in go(c0).rows["candidates"])]

    def f(n):
        if n == asc[0]:
            # die 0 stagnant (d1 = 0 < |d2|): gci_capped = +inf, computed by the driver from these Tj values
            return np.array([[400.0, 400.0], [400.0, 400.0], [401.0, 400.0]]), np.zeros(2)
        return hot_unless({asc[2]})(n)
    r = go(Counter(thermal_fn=f))
    assert r.a1_best == asc[2]


def test_twin_and_reconstruction_always_solved_thermally():
    c = Counter(thermal_fn=hot_unless(set()))
    go(c)
    assert "twin" in c.thermal_log and "ref" in c.thermal_log


def test_null_orders_by_l1_reuses_thermal_and_caps_new_checks():
    c0 = Counter()
    r0 = go(c0)
    l1order = [x["fingerprint"] for x in r0.rows["candidates"]]
    asc = [n for _, n in sorted((x["l_sub"], x["fingerprint"]) for x in r0.rows["candidates"])]
    # nothing passes: A1 checks 8 (asc[:8]); null may add at most 8 more, never re-solving
    c = Counter(thermal_fn=hot_unless(set()))
    r = go(c)
    cand_log = [n for n in c.thermal_log if n not in ("twin", "ref")]
    assert len(cand_log) == len(set(cand_log))  # no candidate solved twice
    assert len(cand_log) <= 16 and r.null_new_checks <= 8
    assert set(cand_log) <= set(l1order)
    assert r.null_best is None
    # null only solves the first not-yet-checked ones in L1 order
    new = [n for n in cand_log if n not in asc[:8]]
    assert new == [n for n in l1order if n not in asc[:8]][:len(new)]


def test_null_is_first_pass_in_l1_order_and_reuses_a1_results():
    c0 = Counter()
    r0 = go(c0)
    l1order = [x["fingerprint"] for x in r0.rows["candidates"]]
    # l1order[2] (pos 3) and l1order[6] pass; the null returns l1order[2] whatever A1 did
    good = {l1order[2], l1order[6]}
    c = Counter(thermal_fn=hot_unless(good))
    r = go(c)
    assert r.null_best == l1order[2]
    # solved at most once, and only the first batch of L1 positions needs looking at
    assert c.thermal_log.count(l1order[2]) == 1


def _l1_scenario():
    """T0278's scenario: L1 order c0..c15 (the real shortlist), L_sub puts c0, c1, c11, c15 first; c10 and c11 pass."""
    c0 = Counter()
    l1order = [x["fingerprint"] for x in go(c0).rows["candidates"]]
    rank = {n: i for i, n in enumerate(l1order)}
    first = [l1order[0], l1order[1], l1order[11], l1order[15]]

    def lsub(n):
        if n in ("ref", "twin"):
            return 30e-9
        if n in first:
            return (10 + first.index(n)) * 1e-9
        return (20 + rank[n]) * 1e-9
    return l1order, lsub


def test_null_never_passes_over_an_unchecked_lower_l1_candidate_t0278():
    l1order, lsub = _l1_scenario()
    good = {l1order[10], l1order[11]}
    c = Counter(thermal_fn=hot_unless(good), lsub_fn=lsub)
    r = go(c)
    # A1 solved c0, c1, c11, c15 (all fail but c11 passes -> a1_best = c11 after the first batch)
    assert r.a1_best == l1order[11]
    # F1: the null looks at positions 1-8 only; none of c0..c7 passes -> None (old code returned c11)
    assert r.null_best is None
    assert r.null_new_checks <= 8
    assert l1order[10] not in c.thermal_log and l1order[8] not in c.thermal_log
    # c10 is the first passing candidate if it is within the first 8 positions
    good = {l1order[5], l1order[11]}
    c = Counter(thermal_fn=hot_unless(good), lsub_fn=lsub)
    assert go(c).null_best == l1order[5]


def test_null_stops_after_first_batch_with_a_pass_and_returns_first_in_l1_order():
    l1order, lsub = _l1_scenario()
    good = {l1order[3], l1order[2]}
    c = Counter(thermal_fn=hot_unless(good), lsub_fn=lsub)
    r = go(c)
    assert r.null_best == l1order[2]
    null_rows = [x["fingerprint"] for x in r.rows["checks"] if x["role"] == "null"]
    assert not set(null_rows) & set(l1order[4:])  # second batch never touched by the null
    assert l1order[3] in c.thermal_log  # the whole first batch is checked
    # an A1-cached passing candidate is reused, not re-solved: c1 passes in A1's first batch
    c = Counter(thermal_fn=hot_unless({l1order[1]}), lsub_fn=lsub)
    r = go(c)
    assert r.a1_best == l1order[1] and r.null_best == l1order[1]
    assert c.thermal_log.count(l1order[1]) == 1


def test_null_batch_stop_in_l1_order():
    c0 = Counter()
    l1order = [x["fingerprint"] for x in go(c0).rows["candidates"]]
    asc = [n for _, n in sorted((x["l_sub"], x["fingerprint"]) for x in go(c0).rows["candidates"])]
    # a candidate that is in A1's first 8 but late in L1 order, plus none other: null = it, within new<=8
    good = {l1order[1]}
    c = Counter(thermal_fn=hot_unless(good))
    r = go(c)
    assert r.null_best == l1order[1]
    null_rows = [x["fingerprint"] for x in r.rows["checks"] if x["role"] == "null"]
    # null stopped after the batch (4 L1 positions) containing l1order[1]
    seen = set(asc[:8] if r.a1_best is None else asc[:4]) | set(null_rows)
    assert set(l1order[:4]) <= seen


def test_near_ties_selection_and_bands():
    # candidates' L_sub spread; e_R=0.02, s_ref=0.01 -> w_ind = 0.05
    c = Counter(e_R=0.02)
    r = go(c, s_ref=0.01)
    assert r.w_ind == pytest.approx(0.05)
    ls = {x["fingerprint"]: x["l_sub"] for x in r.rows["candidates"]}
    best = min(ls, key=ls.get)
    exp = sorted(n for n in ls if n != best and ls[n] <= 1.05 * ls[best])
    assert sorted(r.near_ties) == exp
    # band solves: reference, twin, A1 best (if any), inductance-only best, near ties
    roles = sorted(x["role"] for x in r.rows["band"])
    n_a1 = 1 if r.a1_best else 0
    assert roles.count("near_tie") == len(exp) and roles.count("inductance_best") == 1
    # distinct layouts band-solved (the A1 best may coincide with the inductance-only best: one solve)
    distinct = {x["fingerprint"] for x in r.rows["band"]}
    assert c.calls["band"] == len(distinct) == 3 + (n_a1 if r.a1_best != r.inductance_best else 0) + len(exp)


def test_near_ties_respect_threshold_exactly():
    names = [f.name for f in candidate_stream(None, 200, 5, gen, 64)]
    sl = shortlist_by_l1(5, 200)
    # hand-set L_sub: best 10, one at exactly 1.05*10? use 10.4 (in) and 10.6 (out), others far
    vals = {sl[0]: 10.0, sl[1]: 10.4, sl[2]: 10.6}
    c = Counter(e_R=0.02, lsub_fn=lambda n: vals.get(n, 20.0) * 1e-9 if n not in ("ref", "twin") else 30e-9)
    r = go(c, s_ref=0.01)
    assert r.inductance_best == sl[0] and r.near_ties == [sl[1]]
    assert names  # stream consumed


def test_twin_not_counted_in_search_and_rows_per_die():
    c = Counter(thermal_fn=hot_unless(set()))
    r = go(c)
    tj = r.rows["tj"]
    roles = {x["role"] for x in tj}
    assert {"twin", "reference"} <= roles
    twin_rows = [x for x in tj if x["role"] == "twin"]
    assert [x["die"] for x in twin_rows] == [0, 1]
    assert set(twin_rows[0]) >= {"fingerprint", "tj0", "tj1", "tj2", "gci"}
    assert twin_rows[0]["fingerprint"] == "twin"


def test_control_mode_has_no_thermal_and_uses_d():
    c = Counter(e_R=0.01)
    r = run_control(None, Fake("D"), 77, c.solvers(), 0.01, None, CFG, gen)
    assert c.calls["thermal"] == 0 and r.a1_best is None and r.null_best is None
    assert c.calls["l1"] == 200 and c.calls["l_sub"] == 16 + 1
    names = {f.name for f in candidate_stream(None, 200, 77, gen, 64)}
    assert set(ls_names(r)) <= names  # candidates come from the control's own seed
    ls = {x["fingerprint"]: x["l_sub"] for x in r.rows["candidates"]}
    assert r.inductance_best == min(ls, key=ls.get)
    assert {x["role"] for x in r.rows["band"]} == {"degraded", "control_best"}
    # new seed -> different pool than the search's seed
    r2 = run_control(None, Fake("D"), 78, Counter().solvers(), 0.01, None, CFG, gen)
    assert r2.inductance_best != r.inductance_best


def ls_names(r):
    return [x["fingerprint"] for x in r.rows["candidates"]]


def test_control_w_is_2_eR_without_s_ref_and_has_no_levelling_flag():
    for s_ref in (0.0, 0.01, 0.2):
        c = Counter(e_R=0.01)
        r = run_control(None, Fake("D"), 77, c.solvers(), s_ref, None, CFG, gen)
        assert r.w_ctrl == pytest.approx(0.02)
        assert r.levelling["w_ctrl"] == pytest.approx(0.02)
        assert "w_ind" not in r.levelling and "levelled" not in r.levelling and r.w_ind is None


def test_resume_after_interruption_does_not_resolve(tmp_path):
    c1 = Counter(thermal_fn=hot_unless(set()))
    r1 = go(c1, wd=tmp_path)
    c2 = Counter(thermal_fn=hot_unless(set()))
    r2 = go(c2, wd=tmp_path)
    assert sum(c2.calls.values()) == 0
    assert r2.inductance_best == r1.inductance_best and r2.rows["tj"] == r1.rows["tj"]
    assert r2.null_best == r1.null_best and r2.levelling == r1.levelling


class Boom(Exception):
    pass


def test_resume_mid_run_matches_uninterrupted(tmp_path):
    ref = go(Counter(thermal_fn=hot_unless(set())))
    c = Counter(thermal_fn=hot_unless(set()))
    s = c.solvers()
    n = {"k": 0}
    orig = s.thermal

    def flaky(lay, P):
        n["k"] += 1
        if n["k"] == 4:
            raise Boom
        return orig(lay, P)
    s.thermal = flaky
    with pytest.raises(Boom):
        run_search(None, Fake("ref"), Fake("twin"), 5, s, 50.0, 0.01, tmp_path, CFG, gen)
    # torn trailing line must not break resume
    with open(tmp_path / "checkpoint.jsonl", "a") as f:
        f.write('{"k": "x:l1", "v": ')
    c2 = Counter(thermal_fn=hot_unless(set()))
    r = go(c2, wd=tmp_path)
    assert c2.calls["l1"] == 0 and c2.calls["l_sub"] == 0
    assert c2.calls["thermal"] <= ref_calls(ref) - 3
    assert r.rows["tj"] == ref.rows["tj"] and r.thermal_checked == ref.thermal_checked
    assert r.rows["checks"] == ref.rows["checks"]


def ref_calls(r):
    return len(r.rows["tj"]) // 2


def test_determinism_across_runs():
    a = go(Counter(thermal_fn=hot_unless(set())))
    b = go(Counter(thermal_fn=hot_unless(set())))
    assert a.rows == b.rows and a.levelling == b.levelling and a.thermal_checked == b.thermal_checked


def test_e_R_recorded_for_a1_best_and_every_near_tie_from_band_solves():
    c0 = Counter()
    asc = [n for _, n in sorted((x["l_sub"], x["fingerprint"]) for x in go(c0).rows["candidates"])]
    c = Counter(thermal_fn=hot_unless({asc[2]}))
    # band solves differ per layout: L(0.25), L(0.5), thk 5/3/3, thk 20/12/12, wire 12/ring
    def band(lay):
        c.calls["band"] += 1
        if lay.name == "twin":
            return [10.0, 10.0, 10.0, 10.0, 10.0]
        return [10.0 + 0.1, 10.0, 10.0, 10.0, 10.0 + 0.2]  # R = 1.01, 1, 1, 1, 1.02
    s = c.solvers()
    s.band = band
    r = run_search(None, Fake("ref"), Fake("twin"), 5, s, 50.0, 0.01, None, CFG, gen)
    assert r.a1_best == asc[2] and r.near_ties
    assert r.w_ind == pytest.approx(2 * 0.09 + 0.01)  # the inductance-only best's e_R is band_e_R too
    rows = {(x["candidate"], x["role"]): x for x in r.rows["e_R"] if x.get("source") == "band"}
    assert len(rows) == 2 + len(r.near_ties)  # A1 best, inductance-only best, every near tie
    assert all(x["estimator"] == "band_e_R" for x in r.rows["e_R"])
    for key in [(asc[2], "a1_best")] + [(t, "near_tie") for t in r.near_ties]:
        assert rows[key]["other"] == "twin"
        # 3 |1.01 - 1| + 0 (R equal at the three thickness levels) + 3 |1.02 - 1| = 0.09
        assert rows[key]["e_R"] == pytest.approx(0.09)
    assert r.w_a1 == pytest.approx(2 * 0.09 + 0.01)
    ind = [x for x in r.rows["e_R"] if x["role"] == "inductance_best"]
    assert len(ind) == 1 and ind[0]["estimator"] == "band_e_R" and ind[0]["e_R"] == pytest.approx(0.09)


def test_band_e_R_hand_computed():
    one = [2.0] * 5
    assert band_e_R(one, one) == 0.0
    # lateral only: R(0.25) = 1.1, others 1 -> 3 * 0.1
    assert band_e_R([2.2, 2.0, 2.0, 2.0, 2.0], one) == pytest.approx(0.3)
    # wire only: R(wire) = 0.95 -> 3 * 0.05
    assert band_e_R([2.0, 2.0, 2.0, 2.0, 1.9], one) == pytest.approx(0.15)
    # monotone thickness: R(5/3/3)=1.04, R(10/6/6)=1.01, R(20/12/12)=1.00 -> e32 = .03, e21 = .01, rp = 3,
    # term = 1.25 * .01 * 3 / (3 - 1) = 0.01875; R(0.25) = R(0.5) and R(wire) = R(0.5) contribute nothing
    x = [2.02, 2.02, 2.08, 2.0, 2.02]
    assert band_e_R(x, one) == pytest.approx(0.01875)
    # oscillatory thickness: R = 1.00, 1.03, 1.01 -> e21 = .02, e32 = -.03 -> 3 x max = 0.09
    assert band_e_R([2.06, 2.06, 2.0, 2.02, 2.06], one) == pytest.approx(0.09)
    # not converging (monotone but |e21| > |e32|): R = 1.04, 1.03, 1.00 -> 3 x .03 = 0.09
    assert band_e_R([2.06, 2.06, 2.08, 2.0, 2.06], one) == pytest.approx(0.09)
    # all three terms add linearly: 0.3 + 0.01875 + 0.15 (wire R = 1.03 - 0.05 = 0.98 -> |0.98 - 1.03|... use 1.0)
    x = [2.0 * 1.1, 2.0, 2.0 * 1.03, 2.0 * 1.0, 2.0 * 0.95]  # R = 1.1, 1, 1.03, 1.00, 0.95
    # thickness: e21 = 1 - 1 = 0, e32 = .03 -> product 0 -> 3 max = 0.09
    assert band_e_R(x, one) == pytest.approx(0.3 + 0.09 + 0.15)
    # it is a ratio: a non-trivial denominator
    assert band_e_R([4.4, 2.0, 2.0, 2.0, 2.0], [4.0, 2.0, 2.0, 2.0, 2.0]) == pytest.approx(0.3)
    with pytest.raises(ValueError):
        band_e_R([1.0] * 4, [1.0] * 4)
    with pytest.raises(ValueError):
        band_e_R([1.0, 1.0, 1.0, 1.0, math.nan], one)


def test_thermal_record_checkpointed_in_full_and_gci_computed_by_driver(tmp_path):
    rec = {"tj": np.array([[400.0, 399.0], [400.5, 399.2], [400.75, 399.3]]), "gci": np.array([99.0, 99.0]),
           "nodes": [100, 800, 6400], "tj_max_node": [[1, 2], [3, 4], [5, 6]], "energy_balance": 1e-4,
           "picard": {"converged": True, "iters": 4}, "fingerprint": "xyz"}
    c = Counter()
    s = c.solvers()
    s.thermal = lambda lay, P: dict(rec)
    run_search(None, Fake("ref"), Fake("twin"), 5, s, 50.0, 0.01, tmp_path, CFG, gen)
    r = go(Counter(), wd=tmp_path)  # resumed: every thermal solve comes from the checkpoint
    twin = next(x for x in r.rows["thermal"] if x["fingerprint"] == "twin")["record"]
    for k in ("nodes", "tj_max_node", "energy_balance", "picard", "fingerprint"):
        assert twin[k] == rec[k] if not isinstance(rec[k], np.ndarray) else True
    assert twin["tj_max_node"] == [[1, 2], [3, 4], [5, 6]] and twin["nodes"] == [100, 800, 6400]
    assert twin["picard"] == {"converged": True, "iters": 4} and twin["fingerprint"] == "xyz"
    assert twin["gci_reported"] == [99.0, 99.0]
    # gci_capped on die 0: d1 = .5, d2 = .25, rho = .5 -> p = 1 -> 1.25 * .25 / 1 = 0.3125
    assert twin["gci"][0] == pytest.approx(0.3125)
    # die 1: d1 = .2, d2 = .1 -> 1.25 * .1 = 0.125
    assert twin["gci"][1] == pytest.approx(0.125)


def test_batch_stop_uses_driver_gci_not_the_callable_gci():
    c0 = Counter()
    asc = [n for _, n in sorted((x["l_sub"], x["fingerprint"]) for x in go(c0).rows["candidates"])]
    # callable claims gci = 0 for every layout, but the candidate's own levels diverge (gci_capped = inf): fails
    def f(n):
        if n == asc[0]:
            return np.array([[400.0, 400.0], [400.0, 400.0], [401.0, 400.0]]), np.zeros(2)
        return np.full((3, 2), 400.0), np.zeros(2)
    r = go(Counter(thermal_fn=f))
    chk = {x["fingerprint"]: x for x in r.rows["checks"]}
    assert chk[asc[0]]["margin"] == math.inf and not chk[asc[0]]["passes"]
    assert r.a1_best == asc[1]
    # and a callable reporting a huge gci does not make a converged candidate fail
    r = go(Counter(thermal_fn=lambda n: (np.full((3, 2), 400.0), np.full(2, 50.0))))
    assert r.a1_best == asc[0]


def test_store_truncates_torn_line_and_survives_two_reloads(tmp_path):
    path = tmp_path / "cp.jsonl"
    st = Store(path)
    st.get("a", lambda: 1)
    with path.open("a") as f:
        f.write('{"k": "torn", "v": ')
    st2 = Store(path)  # reload 1: truncates the torn tail
    assert st2.data == {"a": 1}
    st2.get("b", lambda: 2)  # appended on a fresh line
    st3 = Store(path)  # reload 2: b must survive
    assert st3.data == {"a": 1, "b": 2}
    st3.get("c", lambda: 3)
    assert Store(path).data == {"a": 1, "b": 2, "c": 3}
    # a complete record that only lacks its newline is kept
    with path.open("a") as f:
        f.write('{"k": "d", "v": 4}')
    st4 = Store(path)
    assert st4.data["d"] == 4
    st4.get("e", lambda: 5)
    assert Store(path).data == {"a": 1, "b": 2, "c": 3, "d": 4, "e": 5}


def test_duplicate_fingerprints_take_one_shortlist_slot_and_never_tie_with_the_best():
    def dgen(spec, m, seed):  # every layout appears twice
        return [Fake(f"s{seed}_{j // 2}") for j in range(m)]
    c = Counter(e_R=0.2)  # huge band: every shortlisted candidate is a near tie of the best
    r = run_search(None, Fake("ref"), Fake("twin"), 5, c.solvers(), 50.0, 0.0, None, CFG, dgen)
    fps = [x["fingerprint"] for x in r.rows["candidates"]]
    assert len(fps) == 16 == len(set(fps))
    assert r.inductance_best not in r.near_ties
    assert len(set(r.near_ties)) == len(r.near_ties)
    # the kept copy is the first in generation order
    names = [f.name for f in candidate_stream(None, 200, 5, dgen, 64)]
    idx = {x["fingerprint"]: x["index"] for x in r.rows["candidates"]}
    assert all(idx[n] == names.index(n) for n in fps)


def test_pool_statistics_and_separate_control_namespace(tmp_path):
    l1fn = lambda n: 10e-9 * (1 + _u(n, "l1"))  # noqa: E731
    c = Counter(l1_fn=l1fn, thermal_fn=hot_unless(set()))
    r = go(c, wd=tmp_path)
    names = [f.name for f in candidate_stream(None, 200, 5, gen, 64)]
    med = float(np.median([l1fn(n) for n in names]))
    assert r.levelling["l1_twin"] == l1fn("twin")
    assert r.levelling["l1_pool_median"] == pytest.approx(med)
    assert r.levelling["l1_pool_median_headroom"] == pytest.approx(1 - med / l1fn("twin"))
    # control run in the same directory: separate namespace, so nothing of the main run is reused or overwritten
    cc = Counter(l1_fn=l1fn, e_R=0.01)
    run_control(None, Fake("D"), 5, cc.solvers(), 0.0, tmp_path, CFG, gen)  # same seed on purpose
    assert cc.calls["l1"] == 200 and cc.calls["l_sub"] == 16 + 1
    keys = Store(tmp_path / "checkpoint.jsonl").data
    assert any(k.startswith("main:") for k in keys) and any(k.startswith("control:") for k in keys)
    assert all(k.split(":")[0] in ("main", "control") for k in keys)
    # and the main run still resumes cleanly with no solves
    c2 = Counter(l1_fn=l1fn, thermal_fn=hot_unless(set()))
    go(c2, wd=tmp_path)
    assert sum(c2.calls.values()) == 0


def test_w_ind_w_ctrl_and_near_ties_come_from_band_e_R_not_from_any_callable():
    # a band set whose band_e_R is 0.09 against the flat twin / D (3 |1.01 - 1| + 3 |1.02 - 1|); Solvers has no e_R
    assert "e_R" not in Solvers.__dataclass_fields__

    def band(lay):
        return [1.0] * 5 if lay.name in ("ref", "twin", "D") else [1.01, 1.0, 1.0, 1.0, 1.02]
    c = Counter()
    s = c.solvers()
    s.band = band
    r = run_search(None, Fake("ref"), Fake("twin"), 5, s, 50.0, 0.01, None, CFG, gen)
    assert r.w_ind == pytest.approx(0.19)
    ls = {x["fingerprint"]: x["l_sub"] for x in r.rows["candidates"]}
    best = min(ls, key=ls.get)
    assert sorted(r.near_ties) == sorted(n for n in ls if n != best and ls[n] <= 1.19 * ls[best])
    assert r.near_ties  # the 19 % window holds ties that a 1 % window would not
    rc = run_control(None, Fake("D"), 77, s, 0.5, None, CFG, gen)
    assert rc.w_ctrl == pytest.approx(0.18)
    assert all(x["estimator"] == "band_e_R" for x in r.rows["e_R"] + rc.rows["e_R"])


def test_torn_line_repair_never_rewrites_the_file(tmp_path, monkeypatch):
    path = tmp_path / "cp.jsonl"
    st = Store(path)
    for i in range(5):
        st.get(f"k{i}", lambda i=i: i)
    with path.open("a") as f:
        f.write('{"k": "torn", "v": ')
    good = path.read_bytes().rsplit(b"\n", 1)[0] + b"\n"
    # a full rewrite (write_text / write_bytes / open "w") would fail here; the repair must only truncate
    def no_rewrite(*a, **k):
        raise AssertionError("full rewrite of the checkpoint")
    monkeypatch.setattr(type(path), "write_text", no_rewrite)
    monkeypatch.setattr(type(path), "write_bytes", no_rewrite)
    seen = []
    real_truncate = __import__("os").truncate
    monkeypatch.setattr("moduleforge.optimize.search.os.truncate", lambda p, n: (seen.append(n), real_truncate(p, n)))
    assert Store(path).data == {f"k{i}": i for i in range(5)}
    assert seen == [len(good)] and path.read_bytes() == good


def test_torn_multibyte_line_truncates_at_the_byte_offset(tmp_path):
    path = tmp_path / "cp.jsonl"
    Store(path).get("é", lambda: "ü")
    with path.open("ab") as f:
        f.write('{"k": "ö", "v": '.encode())
    assert Store(path).data == {"é": "ü"}
    assert Store(path).data == {"é": "ü"}


def _tr(name="x"):
    return thermal_result(name, np.full((3, 2), 400.0), np.zeros(2))


def test_thermal_record_requires_every_field_and_names_the_missing_one():
    from moduleforge.optimize.search import THERMAL_REQUIRED, _thermal_record
    for k in THERMAL_REQUIRED:
        bad = _tr()
        del bad[k]
        with pytest.raises(ValueError, match=k):
            _thermal_record(bad)


def test_thermal_record_is_a_whitelist_and_rejects_large_arrays():
    from moduleforge.optimize.search import MAX_RECORD_ARRAY, _thermal_record
    res = _tr()
    res["T"] = np.zeros(10 * MAX_RECORD_ARRAY)  # nodal field: dropped, not serialised
    res["field_eval"] = object()
    rec = _thermal_record(res)
    assert set(rec) == {"tj", "tj_max_node", "nodes", "fingerprint", "energy_balance", "picard", "gci", "gci_reported"}
    big = _tr()
    big["nodes"] = np.zeros(MAX_RECORD_ARRAY + 1)
    with pytest.raises(ValueError, match="10000"):
        _thermal_record(big)
    big = _tr()
    big["tj_max_node"] = np.zeros((MAX_RECORD_ARRAY // 2 + 1, 3))
    with pytest.raises(ValueError, match="exceeds"):
        _thermal_record(big)
    big = _tr()
    big["picard"] = object()
    with pytest.raises(TypeError):
        _thermal_record(big)


def test_thermal_record_accepts_mappings_namedtuples_and_attribute_objects():
    from collections import namedtuple
    from types import SimpleNamespace

    from moduleforge.optimize.search import THERMAL_REQUIRED, _thermal_record
    base = _tr("fp")
    want = _thermal_record(base)
    del want["gci_reported"]  # attribute objects below carry no gci
    NT = namedtuple("NT", [*THERMAL_REQUIRED, "T"])
    nt = NT(*[base[k] for k in THERMAL_REQUIRED], np.zeros(5))
    assert _thermal_record(nt) == want
    assert _thermal_record(SimpleNamespace(**{k: base[k] for k in THERMAL_REQUIRED})) == want

    class Slots:
        __slots__ = THERMAL_REQUIRED

        def __init__(self):
            for k in THERMAL_REQUIRED:
                setattr(self, k, base[k])
    assert _thermal_record(Slots()) == want
    # a namedtuple missing a field raises naming it
    with pytest.raises(ValueError, match="picard"):
        _thermal_record(namedtuple("B", "tj tj_max_node nodes fingerprint energy_balance")(*[base[k] for k in
                        THERMAL_REQUIRED[:5]]))


def test_driver_runs_with_namedtuple_thermal_and_fresh_equals_resumed(tmp_path):
    from collections import namedtuple

    from moduleforge.optimize.search import THERMAL_REQUIRED
    NT = namedtuple("NT", THERMAL_REQUIRED)
    c = Counter()
    s = c.solvers()
    s.thermal = lambda lay, P: NT(**{k: v for k, v in thermal_result(lay.name, np.full((3, 2), 400.0),
                                                                      np.zeros(2)).items() if k in THERMAL_REQUIRED})
    a = run_search(None, Fake("ref"), Fake("twin"), 5, s, 50.0, 0.01, tmp_path, CFG, gen)
    b = run_search(None, Fake("ref"), Fake("twin"), 5, s, 50.0, 0.01, tmp_path, CFG, gen)
    assert a.rows == b.rows and a.rows["thermal"]
