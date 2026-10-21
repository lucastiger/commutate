import math
from fractions import Fraction

import pytest

from moduleforge.canary import harmonic, harmonic2

# Euler-Mascheroni constant, OEIS A001620.
GAMMA = 0.57721566490153286061


def test_exact_small():
    assert harmonic(1) == 1.0
    assert harmonic(2) == 1.5


def test_matches_exact_rational():
    exact = float(sum(Fraction(1, k) for k in range(1, 11)))
    assert abs(harmonic(10) - exact) / exact <= 1e-15


@pytest.mark.parametrize("n", [1000, 10000, 100000, 1000000])
def test_asymptotic_expansion(n):
    # H_n ~ ln n + gamma + 1/(2n) - 1/(12 n^2) + 1/(120 n^4)
    # (Concrete Mathematics, §9.6).
    ref = math.log(n) + GAMMA + 1 / (2 * n) - 1 / (12 * n**2) + 1 / (120 * n**4)
    assert abs(harmonic(n) - ref) / ref <= 1e-12


def test_type_and_monotone():
    vals = [harmonic(n) for n in (1, 2, 3, 10, 100, 1000)]
    assert all(type(v) is float for v in vals)
    assert all(a < b for a, b in zip(vals, vals[1:], strict=False))


@pytest.mark.parametrize("n", [0, -1])
def test_value_error(n):
    with pytest.raises(ValueError):
        harmonic(n)


@pytest.mark.parametrize("n", [2.5, True])
def test_type_error(n):
    with pytest.raises(TypeError):
        harmonic(n)


def test_harmonic2_exact_small():
    assert harmonic2(1) == 1.0
    assert harmonic2(2) == 1.25


@pytest.mark.parametrize("n", [3, 10, 50, 200])
def test_harmonic2_matches_exact_rational(n):
    exact = float(sum(Fraction(1, k * k) for k in range(1, n + 1)))
    assert abs(harmonic2(n) - exact) / exact <= 1e-15


def _harmonic2_ref(n):
    # H_n^(2) ~ pi^2/6 - 1/n + 1/(2n^2) - 1/(6n^3)  (Euler-Maclaurin; next term 1/(30 n^5)).
    return math.pi**2 / 6 - 1 / n + 1 / (2 * n**2) - 1 / (6 * n**3)


def _check_asymptotic(n):
    assert abs(harmonic2(n) - _harmonic2_ref(n)) / (math.pi**2 / 6) < 1e-12


def test_harmonic2_asymptotic_1e4():
    _check_asymptotic(10_000)


@pytest.mark.slow
def test_harmonic2_asymptotic_1e6():
    _check_asymptotic(1_000_000)


def test_harmonic2_type_and_monotone():
    vals = [harmonic2(n) for n in (1, 2, 3, 10, 100, 1000)]
    assert all(type(v) is float for v in vals)
    assert all(a < b for a, b in zip(vals, vals[1:], strict=False))
    assert vals[-1] < math.pi**2 / 6


@pytest.mark.parametrize("n", [0, -1])
def test_harmonic2_value_error(n):
    with pytest.raises(ValueError):
        harmonic2(n)


@pytest.mark.parametrize("n", [2.5, True])
def test_harmonic2_type_error(n):
    with pytest.raises(TypeError):
        harmonic2(n)
