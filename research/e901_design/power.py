"""E901 design check: would the decade-stratified sample catch plausible wrong implementations of harmonic2?

Exact enumeration over every n in [1, 10^6] (no Monte Carlo): for each candidate implementation, the share f_s of
integers in decade stratum s whose relative error exceeds a threshold. With 10 uniform draws with replacement per
stratum, P(at least one sampled n exceeds it) = 1 - prod_s (1 - f_s)^10. For comparison, 60 uniform draws on
[1, 10^6]: 1 - (1 - f)^60. Reference: the runner's own decimal_reference (50 digits) rounded to float64.

Run: uv run python research/e901_design/power.py | tee research/e901_design/power.log
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "experiments" / "runners"))
from e901_canary import PER_STRATUM, STRATA, decimal_reference, stratum_bounds  # noqa: E402

N = 10**6
A1, K1 = 1e-13, 1e-9
n = np.arange(1, N + 1)
ref_dec = decimal_reference(list(range(1, N + 1)))
ref = np.array([float(ref_dec[i]) for i in range(1, N + 1)])
k = n.astype(np.float64)
terms = 1.0 / (k * k)
z2 = math.pi**2 / 6


def shift(a: np.ndarray, by: int) -> np.ndarray:
    out = np.empty_like(a)
    if by < 0:
        out[0], out[1:] = 0.0, a[:-1]
    else:
        out[:-1], out[-1] = a[1:], a[-1] + 1.0 / (N + 1) ** 2
    return out


with np.errstate(divide="ignore"):
    k32 = n.astype(np.int32)
    wrapped = (k32 * k32).astype(np.float64)  # int32 overflow of k*k for k > 46340
    int32_terms = 1.0 / wrapped
candidates = {
    "naive forward float64 cumsum": np.cumsum(terms),
    "float32 forward summation": np.cumsum(terms.astype(np.float32), dtype=np.float32).astype(np.float64),
    "off by one: H_(n-1)": shift(ref, -1),
    "off by one: H_(n+1)": shift(ref, +1),
    "int32 overflow in k*k": np.cumsum(int32_terms),
    "loop capped at 65536 terms": np.cumsum(terms)[np.minimum(n, 65536) - 1],
    "asymptotic 3 terms (z2 - 1/n + 1/2n^2)": z2 - 1 / k + 1 / (2 * k**2),
    "asymptotic 4 terms (... - 1/6n^3)": z2 - 1 / k + 1 / (2 * k**2) - 1 / (6 * k**3),
    "NULL pi^2/6 - 1/n": z2 - 1 / k,
}

edges = [stratum_bounds(d) for d in range(len(STRATA))]
print(f"{'candidate':45s} {'max err':>10s} {'P(A1 fails) strat':>18s} {'P unif60':>9s} {'P(K1) strat':>12s}")
for name, pred in candidates.items():
    with np.errstate(invalid="ignore", divide="ignore"):
        err = np.abs(pred / ref - 1.0)
    err = np.where(np.isfinite(err), err, np.inf)
    row = []
    for thr in (A1, K1):
        bad = err > thr
        f_s = [bad[lo - 1:hi].mean() for lo, hi in edges]
        row.append((1 - np.prod([(1 - f) ** PER_STRATUM for f in f_s]), 1 - (1 - bad.mean()) ** 60, f_s))
    print(f"{name:45s} {err.max():10.3e} {row[0][0]:18.6f} {row[0][1]:9.4f} {row[1][0]:12.6f}")
    print(f"{'':45s} per-stratum share > A1: " + " ".join(f"{f:.3f}" for f in row[0][2]))
null_err = np.abs((z2 - 1 / k) / ref - 1.0)
print(f"min over all n<=1e6 of the null's relative error: {null_err.min():.3e} at n={int(n[null_err.argmin()])}"
      f" (A1 threshold {A1:g}); the null fails A1 on every single row, for any seed")
