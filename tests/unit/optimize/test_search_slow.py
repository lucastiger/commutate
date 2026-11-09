"""Real generator and real L1 on the 70 x 40 mm housing, 300-candidate budget."""
import numpy as np
import pytest

from moduleforge.generate.derivative import generate, halfbridge_housing_spec
from moduleforge.optimize.search import SearchConfig, Solvers, run_search
from moduleforge.physics.peec import loop_inductance


@pytest.mark.slow
def test_real_generator_real_l1_300_candidates(tmp_path):
    spec = halfbridge_housing_spec(3)
    cfg = SearchConfig(n_candidates=300, n_first=100, shortlist=16, chunk=50)
    lays = generate(spec, 2, 1)
    twin, ref = lays

    def l1(lay):
        return float(loop_inductance(lay, [20e6]).L_H[0])

    def lsub(lay):  # stand-in for l2_layout: L1 with a layout-dependent offset (tests the driver, not the solver)
        return l1(lay) * 1.01

    s = Solvers(l1=l1, l_sub=lsub, band=lambda lay: [l1(lay)] * 5,
                thermal=lambda lay, P: {"tj": np.full((3, 6), 400.0), "gci": np.full(6, 0.1)}, e_R=lambda p: 0.01)
    r = run_search(spec, ref, twin, 123, s, 50.0, 0.0, tmp_path, cfg)
    assert r.levelling["n_candidates"] == 300
    ls = [x["l1"] for x in r.rows["candidates"]]
    assert len(ls) == 16 and ls == sorted(ls) and r.levelling["l1_min_all"] == ls[0]
    assert all(1e-9 < v < 1e-6 for v in ls)
    assert r.a1_best is not None
