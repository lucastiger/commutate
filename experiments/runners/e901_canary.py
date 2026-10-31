"""E901 canary runner: harmonic2(n) against a 50-significant-digit decimal reference (objective O901).

Design (frozen at registration together with this file's sha256):
- Sample: the sealed seed seeds ``numpy.random.default_rng``; for each decade stratum, in order
  [10^0,10^1), [10^1,10^2), ..., [10^4,10^5), [10^5,10^6] (the last closed), it draws PER_STRATUM integers
  uniformly with replacement (``integers(lo, hi, endpoint=True)``). 6 x 10 = 60 rows, stratum = decade label.
  With replacement is forced: the first decade has only 9 integers.
- Reference: H_n^(2) = sum_{k=1}^{n} 1/k^2 (Graham, Knuth, Patashnik, Concrete Mathematics, 2nd ed., §6.3)
  summed in ``decimal`` arithmetic in a local context of 50 significant digits, ROUND_HALF_EVEN, as one
  cumulative pass over the sorted distinct n. Recursive-summation bound (Higham, Accuracy and Stability of
  Numerical Algorithms, 2nd ed., 2002, eq. 4.4): |error| <= (n-1) u_d sum|t_k| + O(u_d^2) with
  u_d = 0.5e-49, i.e. < 1e-43 relative for n <= 10^6, far below float64 resolution.
- Metric: max_rel_err = max |pred/ref - 1| over the rows, computed with ``mfos.metrics.max_rel_err``, the
  function the evaluator uses to recompute it from rows.json. ``ref`` is the decimal reference rounded to
  float64 (``float(Decimal)`` is correctly rounded).
- Uncertainty: the hypothesis is about the sealed sample itself, so the only uncertainty in the metric is
  floating-point evaluation error. The interval reported is a rigorous bound (level 1.0), not a bootstrap:
  a bootstrap of a sample maximum is inconsistent (Bickel and Freedman, Ann. Statist. 9 (1981) 1196-1217).
  Derivation: ref_f = H (1 + d1), |d1| <= u + 1e-40; q = fl(pred/ref_f) = (pred/ref_f)(1 + d2), |d2| <= u;
  q - 1 is exact for q in [1/2, 2] (Sterbenz lemma, Higham §2.5). Hence per row
  |e_computed - e_true| <= (1 + e_true)(2u + 1e-40)(1 + 2u) <= 3u (1 + max_rel_err) + 1e-40 =: b,
  with u = 2^-53 (IEEE 754 binary64 unit roundoff, Higham §2.1). Reported ci = (max(0, m - b), m + b).
- Null predictor (column null_pred): pi^2/6 - 1/n, the Basel limit (Euler 1735) minus the leading tail term.
- Sanity: exact_small_cases (harmonic2(1) == 1.0 and harmonic2(2) == 1.25, both exact in binary64) and
  reference_valid (the decimal reference equals the exact fractions.Fraction sum within 1e-40 relative for
  every n <= 200). The detail of reference_valid also reports an independent large-n check against the
  asymptotic expansion of the trigamma function (informational; it does not enter the pass rule).

``--smoke`` uses a small fixed n set and writes only under ``tempfile.gettempdir()``.
"""
from __future__ import annotations

import argparse
import decimal
import math
import os
import tempfile
from decimal import Decimal
from fractions import Fraction
from pathlib import Path

import numpy as np

from mfos.evidence import ExperimentRun
from mfos.metrics import max_rel_err

PER_STRATUM = 10
STRATA = ["[10^0,10^1)", "[10^1,10^2)", "[10^2,10^3)", "[10^3,10^4)", "[10^4,10^5)", "[10^5,10^6]"]
REFERENCE_DIGITS = 50
REFERENCE_VALID_N_MAX = 200
REFERENCE_VALID_REL_TOL = 1e-40
# Must equal the spec's config exactly; a non-smoke run refuses to start otherwise.
CONFIG = {
    "per_stratum": PER_STRATUM,
    "strata": STRATA,
    "reference_digits": REFERENCE_DIGITS,
    "reference_valid_n_max": REFERENCE_VALID_N_MAX,
    "reference_valid_rel_tol": REFERENCE_VALID_REL_TOL,
}
# Smoke only: every decade's ends and neighbours, including n = 1 and n = 10^6.
SMOKE_NS = [1, 2, 3, 9, 10, 11, 99, 100, 101, 999, 1000, 1001, 9999, 10000, 99999, 100000, 999999, 1000000]

U = 2.0**-53  # unit roundoff of IEEE 754 binary64 (Higham 2002, §2.1)
# pi to 63 significant digits (OEIS A000796); used only in the informational asymptotic cross-check.
PI_63 = "3.14159265358979323846264338327950288419716939937510582097494459"


def stratum_bounds(d: int) -> tuple[int, int]:
    """Inclusive integer bounds of decade stratum d (0..5); the last stratum includes 10^6."""
    return 10**d, (10 ** (d + 1) - 1 if d < len(STRATA) - 1 else 10 ** len(STRATA))


def stratum_of(n: int) -> str:
    return STRATA[min(len(str(n)) - 1, len(STRATA) - 1)]


def draw_sample(seed: int) -> list[tuple[int, str]]:
    """PER_STRATUM uniform draws with replacement per decade, strata in order, from default_rng(seed)."""
    rng = np.random.default_rng(seed)
    out: list[tuple[int, str]] = []
    for d, label in enumerate(STRATA):
        lo, hi = stratum_bounds(d)
        out += [(int(n), label) for n in rng.integers(lo, hi, size=PER_STRATUM, endpoint=True)]
    return out


def decimal_reference(ns: list[int]) -> dict[int, Decimal]:
    """sum_{k=1}^{n} 1/k^2 for every n in ns: one cumulative pass, REFERENCE_DIGITS significant digits."""
    out: dict[int, Decimal] = {}
    with decimal.localcontext() as ctx:
        ctx.prec = REFERENCE_DIGITS
        ctx.rounding = decimal.ROUND_HALF_EVEN
        one, s, k = Decimal(1), Decimal(0), 0
        for n in sorted(set(ns)):
            while k < n:
                k += 1
                s += one / Decimal(k * k)  # k*k <= 10^12 is an exact 13-digit integer
            out[n] = s
    return out


def reference_validation(ref: dict[int, Decimal]) -> float:
    """max over n <= REFERENCE_VALID_N_MAX of |ref(n) - H_n^(2)| / H_n^(2), H exact as a Fraction."""
    exact, worst = Fraction(0), Fraction(0)
    for n in range(1, REFERENCE_VALID_N_MAX + 1):
        exact += Fraction(1, n * n)
        worst = max(worst, abs(Fraction(ref[n]) - exact) / exact)  # Fraction(Decimal) is exact
    return float(worst)


def asymptotic_check(ref: dict[int, Decimal], ns: list[int]) -> tuple[float, float]:
    """Independent check of the reference for large n. H_n^(2) = pi^2/6 - psi'(n+1), psi'(z) = sum_k 1/(z+k)^2
    (DLMF 5.15.1), and psi'(z) ~ 1/z + 1/(2z^2) + sum_j B_2j / z^(2j+1) (DLMF 5.15.8) with psi'(n+1) = psi'(n) - 1/n^2
    give H_n^(2) ~ pi^2/6 - 1/n + 1/(2n^2) - 1/(6n^3) + 1/(30n^5) - 1/(42n^7) + 1/(30n^9); the remainder is below
    the first omitted term 5/(66 n^11) (B_10 = 5/66; DLMF 5.15(ii)). Returns (max rel diff, max allowed)."""
    worst, allowed = 0.0, 0.0
    with decimal.localcontext() as ctx:
        ctx.prec = 60
        z2 = Decimal(PI_63) ** 2 / 6
        for n in sorted({x for x in ns if x >= 1000}):
            x = Decimal(n)
            asym = (z2 - 1 / x + 1 / (2 * x**2) - 1 / (6 * x**3) + 1 / (30 * x**5) - 1 / (42 * x**7)
                    + 1 / (30 * x**9))
            worst = max(worst, float(abs(ref[n] - asym) / ref[n]))
            allowed = max(allowed, float(Decimal(5) / (66 * x**11) / ref[n]) + REFERENCE_VALID_REL_TOL)
    return worst, allowed


def main(smoke: bool) -> None:
    from moduleforge.canary import harmonic2

    if smoke:
        smoke_dir = Path(tempfile.gettempdir()) / "e901-smoke"
        os.environ.setdefault("MFOS_ARTIFACT_STORE", str(smoke_dir / "artifacts"))
        run_ctx = ExperimentRun(experiment_id="E901", run_dir=str(smoke_dir), config=CONFIG)
    else:
        run_ctx = ExperimentRun()
    with run_ctx as run:
        if smoke:
            sample = [(n, stratum_of(n)) for n in SMOKE_NS]
        else:
            if run.config != CONFIG:
                raise RuntimeError(f"spec config {run.config!r} differs from the runner design {CONFIG!r}")
            if run.seed is None:
                raise RuntimeError("E901 needs the sealed seed (MFOS_SEED); refusing to draw a sample without it")
            sample = draw_sample(run.seed)
        ns = [n for n, _ in sample]

        # sanity 1: exact small cases (both values are exactly representable in binary64)
        h1, h2 = harmonic2(1), harmonic2(2)
        run.sanity("exact_small_cases", passed=(h1 == 1.0 and h2 == 1.25),
                   detail=f"harmonic2(1)={h1!r}, harmonic2(2)={h2!r}")

        # reference: one cumulative decimal pass shared by the sample and the validation range
        ref = decimal_reference(ns + list(range(1, REFERENCE_VALID_N_MAX + 1)))
        ref_err = reference_validation(ref)
        asym_err, asym_allowed = asymptotic_check(ref, ns)
        run.sanity("reference_valid", passed=ref_err <= REFERENCE_VALID_REL_TOL, value=ref_err,
                   threshold=REFERENCE_VALID_REL_TOL,
                   detail=(f"max rel |decimal - Fraction| over n<= {REFERENCE_VALID_N_MAX}: {ref_err:.3e}. "
                           f"Informational, not in the pass rule: max rel |decimal - asymptotic| over sampled "
                           f"n>=1000: {asym_err:.3e} (truncation bound {asym_allowed:.3e}; "
                           f"within: {asym_err <= asym_allowed})"))

        # rows: one record per draw (duplicates kept), model under test evaluated once per distinct n
        pred_of = {n: harmonic2(n) for n in sorted(set(ns))}
        rows = [{"n": n, "stratum": s, "pred": pred_of[n], "ref": float(ref[n]),
                 "null_pred": math.pi**2 / 6 - 1 / n} for n, s in sample]
        run.rows(rows)
        ref_path = run.run_dir / "reference_decimal.json"
        ref_path.write_text("{\n" + ",\n".join(f'  "{n}": "{ref[n]}"' for n in sorted(set(ns))) + "\n}\n")
        run.artifact("reference_decimal.json", ref_path)

        pred = [r["pred"] for r in rows]
        ref_f = [r["ref"] for r in rows]
        value = max_rel_err(pred, ref_f)
        bound = 3 * U * (1 + value) + REFERENCE_VALID_REL_TOL
        run.metric("max_rel_err", value, ci=(max(0.0, value - bound), value + bound), n=len(rows), level=1.0)

        # diagnostics for the record (facts about this run; none of them enters a verdict)
        with decimal.localcontext() as ctx:
            ctx.prec = 60
            exact_max = float(max(abs(Decimal(pred_of[n]) / ref[n] - 1) for n in set(ns)))
        null_value = max_rel_err([r["null_pred"] for r in rows], ref_f)
        per_stratum = {s: (len({n for n, t in sample if t == s}),
                           max_rel_err([r["pred"] for r in rows if r["stratum"] == s],
                                       [r["ref"] for r in rows if r["stratum"] == s]),
                           max_rel_err([r["null_pred"] for r in rows if r["stratum"] == s],
                                       [r["ref"] for r in rows if r["stratum"] == s]))
                       for s in STRATA if any(t == s for _, t in sample)}
        run.domain(n_min=[1], n_max=[1000000], strata=STRATA)
        run.notes += "\n".join([
            f"mode: {'smoke (fixed n set, not evidence)' if smoke else f'drawn sample, seed {run.seed}'}; "
            f"rows {len(rows)}, "
            f"distinct n {len(set(ns))}; sampled n range [{min(ns)}, {max(ns)}]; "
            f"log10 span {math.log10(max(ns)) - math.log10(min(ns)):.3f}",
            f"max_rel_err (float64, as recomputed) {value!r}; error bound b {bound:.3e}; "
            f"max exact |pred/ref_decimal - 1| {exact_max!r}; within ci: {abs(exact_max - value) <= bound}",
            f"null pi^2/6 - 1/n: max_rel_err {null_value!r} (A1 threshold 1e-13)",
            "per stratum (distinct n, max_rel_err, null max_rel_err): "
            + "; ".join(f"{s} ({k}, {e:.3e}, {z:.3e})" for s, (k, e, z) in per_stratum.items()),
        ])


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true", help="small fixed n set; writes only under the system temp dir")
    main(ap.parse_args().smoke)
