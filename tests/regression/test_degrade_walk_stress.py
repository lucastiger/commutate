"""Stress test of the degradation rule's fallback walk (T0293, T0291 caveat 1): 72 generator housing layouts at a 2 mm
minimum copper width (n = 2, 3, 4 dies x k = 1, 2, 3 wires per die x 8 layouts, seed 1000 n + 10 k + 7).

Result (locked): 63 of 72 reach L1(D)/L1(W) >= 1.25 (1 + 0.11) and are DRC-clean (ratios min 1.3875, median 1.3943, max
2.0866); the other 9 end in ``DegradeError`` with the walk's terminal kind ``local_maximum`` (no DRC-valid single-parameter
change raises L1 further) at the terminal ratios below.  Before the walk, 45 of the 72 ended in ``DegradeError`` (T0287).
About 16 minutes, so it is marked slow; ``tests/unit/generate/test_twin.py`` locks one of the terminal states (2, 1, 1) and
one walk that reaches the target in the fast suite."""
import numpy as np
import pytest

from moduleforge.drc import DesignRules, check
from moduleforge.generate import derivative as D
from moduleforge.generate import twin as W

pytestmark = pytest.mark.slow

# (n, k, index) -> L1 ratio at the walk's terminal state (a local maximum of the hill-climb)
TERMINAL = {(2, 1, 1): 1.3382, (2, 2, 0): 1.2857, (2, 3, 0): 1.3225, (2, 3, 2): 1.3136, (2, 3, 4): 1.2227,
            (3, 2, 1): 1.2058, (4, 1, 4): 1.3717, (4, 1, 5): 1.3679, (4, 2, 6): 1.2279}
# ... and at the walk's start (after moves 1-3); every one of them took 48-64 walk steps
START = {(2, 1, 1): 1.1904, (2, 2, 0): 1.1735, (2, 3, 0): 1.1385, (2, 3, 2): 1.1681, (2, 3, 4): 1.1130,
         (3, 2, 1): 1.1175, (4, 1, 4): 1.2251, (4, 1, 5): 1.1873, (4, 2, 6): 1.0025}


def test_walk_on_72_layouts_at_2mm_minimum_width():
    target = W.DEGRADE_RATIO * (1 + W.DEGRADE_MARGIN)
    reached, failed = [], {}
    for n in (2, 3, 4):
        for k in (1, 2, 3):
            spec = D.halfbridge_housing_spec(n, rules=DesignRules(min_trace_width=2e-3), wires_per_die=k)
            for idx, ref in enumerate(D.generate(spec, 8, seed=1000 * n + 10 * k + 7, max_failures=3000)):
                try:
                    d, rec = W.degrade(ref, spec)
                except W.DegradeError as e:
                    wk = e.record["walk"]
                    assert wk is not None and wk["terminal"] == W.WALK_LOCAL_MAX, (n, k, idx, e)
                    assert wk["terminal_state"] in str(e)
                    # the terminal ratio is the walk's own (the state after moves 1-3 if it took no step)
                    last = wk["steps"][-1]["l1_ratio"] if wk["steps"] else wk["start_l1_ratio"]
                    assert wk["l1_ratio"] == pytest.approx(last, rel=1e-12) and wk["l1_ratio"] >= wk["start_l1_ratio"]
                    failed[(n, k, idx)] = wk["l1_ratio"]
                    assert wk["start_l1_ratio"] == pytest.approx(START[(n, k, idx)], abs=1e-3)
                    print(f"stuck {(n, k, idx)}: start {wk['start_l1_ratio']:.4f} -> {wk['l1_ratio']:.4f} "
                          f"after {len(wk['steps'])} steps")
                    continue
                assert check(d, spec.rules) == [] and rec["l1_ratio"] >= target
                assert rec["walk"] is None or rec["walk"]["terminal"] == W.WALK_TARGET
                reached.append(rec["l1_ratio"])
    assert len(reached) + len(failed) == 72
    assert set(failed) == set(TERMINAL)
    for key, r in failed.items():
        assert r == pytest.approx(TERMINAL[key], abs=1e-3)
        assert r < target
    lo, med, hi = min(reached), float(np.median(reached)), max(reached)
    print(f"2 mm: {len(reached)} reached, {len(failed)} stuck; ratios min {lo:.4f} median {med:.4f} max {hi:.4f}")
    assert len(reached) == 63
    assert (lo, med, hi) == pytest.approx((1.3875, 1.3943, 2.0866), abs=1e-3)
