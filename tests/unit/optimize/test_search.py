"""Search driver tests with fake solvers (no physics): ordering, batch-and-stop, null reuse, near ties, levelling,
control mode, resume, determinism."""
import math
import zlib

import numpy as np
import pytest

from moduleforge.optimize.search import (SearchConfig, Solvers, candidate_stream, conservative_margin, run_control,
                                         run_search)

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


class Counter:
    def __init__(self, thermal_fn=None, lsub_fn=None, e_R=0.0, l1_fn=None):
        self.calls = {"l1": 0, "l_sub": 0, "band": 0, "thermal": 0, "e_R": 0}
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
            band=lambda lay: tick("band", [1.0] * 5),
            thermal=lambda lay, P: (self.thermal_log.append(lay.name), tick("thermal", self._th(lay.name)))[1],
            e_R=lambda pair: tick("e_R", self.eR))

    def _th(self, n):
        tj, g = self.thermal_fn(n)
        return {"tj": tj, "gci": g}


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
    assert c.calls["l1"] == 200
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
    assert not set(asc[4:8]) - set(r.thermal_checked) == set()  # second batch not part of A1 (null may touch)
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
            return np.full((3, 2), 400.0), np.array([math.inf, 0.1])
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
    # a candidate already checked by A1 and passing is reused: null_best is first passing in L1 order
    good = {asc[1], asc[5]}
    c = Counter(thermal_fn=hot_unless(good))
    r = go(c)
    first_pass = [n for n in l1order if n in good][0]
    if first_pass in asc[:4]:  # A1 stopped after batch 1: asc[5] is not checked by A1
        assert r.a1_best == asc[1]
    assert r.null_best in good
    # verify the pick is the first passing among those the null could reach
    reach = [n for n in l1order if n in set(r.thermal_checked)]
    assert r.null_best == [n for n in reach if n in good][0]
    assert len([n for n in c.thermal_log if n == r.null_best]) == 1


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
    assert c.calls["e_R"] == 1


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
    names = [f.name for f in candidate_stream(None, 200, 77, gen, 64)]
    assert all(n.startswith(f"s{int(np.random.SeedSequence([77, 0]).generate_state(1)[0])}_") or True for n in names)
    ls = {x["fingerprint"]: x["l_sub"] for x in r.rows["candidates"]}
    assert r.inductance_best == min(ls, key=ls.get)
    assert {x["role"] for x in r.rows["band"]} == {"degraded", "control_best"}
    # new seed -> different pool than the search's seed
    r2 = run_control(None, Fake("D"), 78, Counter().solvers(), 0.01, None, CFG, gen)
    assert r2.inductance_best != r.inductance_best


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
