---
name: mf-evidence
description: How ModuleForge experiments produce admissible evidence - spec format, runner pattern with mfos.evidence.ExperimentRun, sanity checks, uncertainty, sealed seeds, forbidden practices. Use when designing, implementing, or running any experiment.
user-invocable: false
---

# Producing admissible evidence

Evidence is admissible only if the deterministic evaluator accepts it: registered spec with an
unchanged hash, clean git tree at a commit on main, every declared sanity check reported and
passing, and a confidence interval on every metric an acceptance criterion reads with `use: ci`.

## Spec (`experiments/drafts/<EID>.yaml`, schema `mfos.models.ExperimentSpec`)
```yaml
id: E002
title: L1 vs L2 loop-inductance ranking on generated half-bridge layouts
objective: O001
runner: uv run python experiments/runners/e002_ranking.py
config: {n_layouts: 60, freq_hz: 2.0e7, generator: random_valid_v1, families: [A, B, C]}
sealed_seed: true
metrics:
  - {name: spearman_rho_Lloop, description: Spearman rank correlation L1 vs L2}
  - {name: mape_Lloop, description: mean absolute percentage error of L1 vs L2}
sanity_checks:
  - {name: l2_converged, description: every L2 solve changes < 1% under one mesh refinement}
  - {name: sample_diverse, description: coefficient of variation of L2 values >= 0.3}
timeout_min: 240
cpu_hours_est: 6
```

## Runner pattern
```python
import argparse
import tempfile
from mfos.evidence import ExperimentRun
from mfos.stats import bootstrap_ci, spearman

def main(smoke: bool) -> None:
    with ExperimentRun(run_dir=tempfile.mkdtemp(prefix="smoke-") if smoke else None) as run:
        n = 6 if smoke else run.config["n_layouts"]
        layouts = generate(n, seed=run.seed)            # seed is sealed and unseen by you
        l1, l2, converged = evaluate_both(layouts, run.config["freq_hz"])
        run.sanity("l2_converged", passed=all(converged))
        run.sanity("sample_diverse", passed=cv(l2) >= 0.3, value=cv(l2), threshold=0.3)
        rho, ci = bootstrap_ci(spearman, l1, l2, n_boot=2000, seed=7)
        run.metric("spearman_rho_Lloop", rho, ci=ci, n=n)

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--smoke", action="store_true")
    main(ap.parse_args().smoke)
```
Every runner supports `--smoke` (tiny, fast, writes to a temp dir). A design task's definition of
done includes `uv run mfos exp check <EID>` and the runner's `--smoke` invocation.

## Evidence rules v2 (every spec registered since 2026-10-19)
The evaluator no longer takes a runner's numbers on trust. A design must give it what it needs:
- **Rows.** Write one flat record per sampled unit with `run.rows(records)` (e.g. `{"layout": 17,
  "family": "u_shaped", "dies": 4, "L1": ..., "L2": ...}`) and declare `rows: {artifact: rows.json}`.
- **Recompute.** For every metric an acceptance criterion reads, add a `recompute` entry naming an
  `mfos.metrics` function and its columns, with the same `ci` (scheme, n_boot, seed) the runner uses,
  e.g. `{metric: spearman_rho_Lloop, fn: spearman, pred: L1, ref: L2, ci: {scheme: stratified,
  strata: [family, dies], n_boot: 2000, seed: 7}}`. The evaluator recomputes it and judges on its own
  value; a disagreeing runner value makes the evidence INVALID. Compute the metric in the runner with
  `mfos.metrics` too, so the two agree. A metric that cannot be recomputed from rows needs a written
  `recompute_exempt: {metric: reason}`.
- **Nulls.** Declare `null_baselines` for every pass criterion a predictor could meet without the
  decision-relevant information, e.g. `{name: stratum_mean, kind: stratum_mean, strata: [family, dies],
  applies_to: [spearman_rho_Lloop]}` (O001's A2/A3 were met by exactly that predictor). A criterion
  the null also meets is `non_discriminating`. Commit dev-seed rows and set `dev_rows: <path>`;
  `uv run mfos exp check <EID> --rows <path>` must show every null failing before registration.
- **Domain.** Record what was actually sampled with `run.domain(stack=[...], dies=[...], freq_hz=[...],
  cpu=[...])`. The claim's scope is generated from it, never from the hypothesis text.
- **Code identity.** List the modules whose behaviour the experiment measures in `code_under_test`
  (files or globs). An experiment that relies on code validated by another objective declares
  `code_must_match: [{path: ..., objective: O004}]` and `requires_passed: [O004]`.
- **Runs.** Every run is minted in `experiments/registry.jsonl` first; the first minted run counts.
  Never rerun a sealed experiment to get a better draw: every run stays on the record.

## Rules
- Validate the reference before comparing against it. A comparison experiment declares a sanity
  check proving the reference is trustworthy on this run.
- Sanity checks must be able to fail. `passed=True` constants are forbidden.
- Decide exclusions, outlier handling, and metrics before registration. Never after seeing data.
- Never tune a model on the evaluation sample. Sealed seeds exist so you cannot.
- Large outputs go through `run.artifact(...)` (content-addressed), never into git. The rows file is small and
  stays in the run directory, which is committed with the result.
- A changed design is a new experiment id. Registered specs are immutable, and so are the runner files the
  `runner` command names: registration records their sha256 and `mfos exp run` refuses a changed one. Keep
  every design decision (cases, tolerances, error models) in the spec or in those files.
