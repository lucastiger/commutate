# E901 design note (T0116, attempt 2)

Draft spec: `experiments/drafts/E901.yaml`. Runner: `experiments/runners/e901_canary.py`.
Dev rows: `experiments/drafts/E901.dev_rows.json` (seed 901, a dev seed, not the sealed seed).
Power analysis: `power.py`, output in `power.log`.

## Facts (each reproducible with the command given)
- Smoke run (`uv run python experiments/runners/e901_canary.py --smoke`, 18 fixed n from 1 to 10^6):
  max_rel_err = 1.11e-16. reference_valid: 2.11e-49 against the 1e-40 limit. Null max_rel_err = 0.355.
- Dev-seed run (seed 901, 60 rows, 55 distinct n, n from 1 to 883935): max_rel_err = 1.11e-16. The exact
  decimal error max |pred/ref_dec - 1| is 7.35e-17, inside the reported bound interval [0, 4.44e-16].
- `uv run mfos exp check E901 --rows experiments/drafts/E901.dev_rows.json`: A1 is satisfied by the dev
  value and `not_satisfied` by the null (0.355). Negative control: rows with null_pred := pred make the
  same command report A1 as non-discriminating (exit 1). So the check can fail.
- Independent large-n check of the reference: the trigamma asymptotic expansion (DLMF 5.15.1, 5.15.8)
  agrees with the decimal reference to 4.6e-35 at n = 1000. That equals the first omitted term
  5/(66 n^11) / H, which is what the derived series predicts.
- Negative controls in `power.log`, by exact enumeration over every n <= 10^6:
  - The design catches each of these with probability 1, and K1 fires for each: float32 summation, H_(n-1),
    H_(n+1), int32 overflow of k*k, a loop capped at 65536 terms, and the 3- and 4-term asymptotic formulas.
  - 60 unstratified uniform draws would catch the 3- and 4-term formulas only with probability 0.454 and 0.011.
- The null pi^2/6 - 1/n has relative error >= 3.04e-13 at every n <= 10^6 (minimum at n = 999995). It
  therefore fails A1 on every possible row, for every seed. The margin is only about 3x, at the top decade.
- Mutation run of the runner (harmonic2 replaced by naive forward float64 summation): max_rel_err = 2.6e-14,
  so A1 passes.

## Inferences
- A1 (<= 1e-13) cannot tell fsum from naive forward float64 summation (worst 2.75e-14 for n <= 10^6).
  A PASS means "within 1e-13 for the sampled n", not "correctly rounded".
- `exact_small_cases` exercises the code under test, not the apparatus. A harmonic2 that is wrong at
  n = 1 or 2 (for example H_(n+1)) fails this sanity check, which makes the evidence INVALID rather than
  firing K1. Under O901 that outcome is treated as an infrastructure failure. The check was prescribed,
  so it was kept.
- The metric's uncertainty is floating-point evaluation error only, because the hypothesis is about the
  sealed sample itself. The runner reports a rigorous bound of level 1.0, b = 3u(1 + m) + 1e-40. It does
  not report a bootstrap interval, because a bootstrap of a sample maximum is inconsistent (Bickel &
  Freedman 1981). A1 and K1 use the point value.

## Speculation
- None that affects the design.
