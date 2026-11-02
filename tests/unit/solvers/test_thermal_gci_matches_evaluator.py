"""The thermal L2's own discretisation estimate equals the evaluator's O006 A4 estimator (mfos.metrics.gci_capped with
the 1e-3 K floor of D0013 addendum 2), for the finite-volume solver (thermal_layout) and the scikit-fem cross-check
(thermal_fem)."""
from __future__ import annotations

import itertools
import math

import numpy as np
import pytest
from mfos.metrics import gci_capped

from moduleforge.solvers import thermal_fem as F
from moduleforge.solvers import thermal_layout as tl

FLOOR = 1e-3  # K, O006 A4 (ten times the Picard tolerance)
BRANCHES = {"exact", "divergent", "oscillatory", "fast", "monotone"}


def _sequences() -> list[tuple[float, float, float]]:
    seqs = []
    # step magnitudes around and far from the floor (zero, round-off, Picard noise, just below / at / above 1e-3 K)
    steps = [0.0, 1e-9, 4e-5, 9.999e-4, 1e-3, 1.0001e-3, 0.002, 0.01, 0.1, 0.3, 1.0, 2.5]
    signed = [-x for x in steps[:0:-1]] + steps
    for f0 in (0.0, 410.0):
        for s1, s2 in itertools.product(signed, repeat=2):
            seqs.append((f0, f0 + s1, f0 + s1 + s2))
    # ratios straddling every branch boundary: rho = 0, 1/4 -/+, 1/2, 1 -/+, -1 -/+, 4, -4 for both signs of d1
    for sgn in (1.0, -1.0):
        for rho in (0.0, 0.2499999, 0.25, 0.2500001, 0.5, 0.9, 0.9999999, 1.0, 1.0000001, 4.0,
                    -0.2, -0.9999999, -1.0, -1.0000001, -4.0, 2 ** -1.5, 2 ** -0.3):
            seqs.append((410.0, 410.0 + 0.3 * sgn, 410.0 + 0.3 * sgn * (1.0 + rho)))
    rng = np.random.default_rng(20261102)  # explicit seed
    for _ in range(2000):
        d1 = rng.choice([-1.0, 1.0]) * 10.0 ** rng.uniform(-4, 1)
        rho = rng.choice([-1.0, 1.0]) * 10.0 ** rng.uniform(-4, 0.7)
        seqs.append((410.0, 410.0 + d1, 410.0 + d1 * (1.0 + rho)))
    # re-review and packet examples: divergent, lucky grid, oscillatory, sub-floor noise of both signs
    seqs += [(410.0, 410.25, 410.75), (410.0, 410.3, 410.31), (410.0, 410.4, 410.2),
             (410.0, 410.4, 410.4 - 4e-5), (410.0, 410.4, 410.4 + 4e-5)]
    return seqs


def _assert_equal(got: float, ref: float, seq) -> None:
    if math.isinf(ref):
        assert got == math.inf, seq
    else:
        assert got == pytest.approx(ref, rel=1e-12, abs=0.0), seq


def test_grid_is_large_and_covers_every_branch_and_both_signs():
    seqs = _sequences()
    assert len(seqs) >= 2000
    branches = {tl.gci_three_grid(*s, floor=FLOOR)["branch"] for s in seqs}
    assert branches == BRANCHES
    for branch in BRANCHES - {"exact"}:
        for sgn in (1.0, -1.0):  # sign of the coarse step d1 (of d2 when d1 is below the floor)
            assert any(tl.gci_three_grid(*s, floor=FLOOR)["branch"] == branch
                       and ((s[1] - s[0]) if abs(s[1] - s[0]) >= FLOOR else (s[2] - s[1])) * sgn > 0
                       for s in seqs), (branch, sgn)
    # the floor is exercised: some sequences change branch when it is removed
    assert any(tl.gci_three_grid(*s, floor=FLOOR)["branch"] != tl.gci_three_grid(*s, floor=0.0)["branch"]
               for s in seqs)


def test_thermal_layout_matches_evaluator():
    for s in _sequences():
        _assert_equal(tl.gci_three_grid(*s, floor=FLOOR)["gci"], gci_capped(*s, floor=FLOOR), s)
        _assert_equal(tl.gci_three_grid(*s)["gci"], gci_capped(*s, floor=FLOOR), s)  # the default floor is A4's


def test_thermal_layout_matches_evaluator_without_floor():
    for s in _sequences():
        _assert_equal(tl.gci_three_grid(*s, floor=0.0)["gci"], gci_capped(*s, floor=0.0), s)


def test_thermal_fem_matches_evaluator():
    for f0, f1, f2 in _sequences():
        got, _ = F.gci([f2, f1, f0])  # (finest, middle, coarsest)
        _assert_equal(got, gci_capped(f0, f1, f2, floor=FLOOR), (f0, f1, f2))
        got_private, _ = F._gci([f2, f1, f0])
        _assert_equal(got_private, gci_capped(f0, f1, f2, floor=FLOOR), (f0, f1, f2))


def test_p_obs_is_the_evaluators_log2_of_one_over_rho():
    # bit-identical to gci_capped's math.log2(1.0 / rho) on the monotone branch, where the evaluator uses it
    for s in _sequences():
        g = tl.gci_three_grid(*s)
        if g["branch"] == "monotone":
            d1, d2 = s[1] - s[0], s[2] - s[1]
            assert g["p_obs"] == math.log2(1.0 / (d2 / d1)), s
