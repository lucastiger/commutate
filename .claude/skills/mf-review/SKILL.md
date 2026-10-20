---
name: mf-review
description: Adversarial review checklists by lens (general, physics, numerics, statistics) and evidence-provenance checks. Use when acting as a critic.
user-invocable: false
---

# Adversarial review

Always: restate the claim and its implied scope; name the three likeliest failure routes; perform
independent checks; report findings with severity, impact and evidence. Test the tests: a test that
recomputes the implementation's own formula proves nothing.

Materiality: only a blocker whose impact is `evidence` or `correctness` rejects. Second-order points
(a tighter estimator, a nicer bound) are `major`/`minor` findings with impact `scope` or
`maintainability`, or caveats. Ask whether the finding could change the decision the work feeds,
given the margin by which it passes. After two rejected rounds the founder decides.

## objective drafts (target OBJ-<OID>)
Would each pass criterion also be met by a predictor that ignores the decision-relevant information
(e.g. one that knows only the topology or die count)? Do the thresholds follow from the decision, or
from what is easy to pass? Can the sample and its strata resolve the claim? Can the kill criteria
actually fire? Is every metric recomputable from rows? Is the scope what will really be sampled?

## Running checks (sandboxed shell)
Your shell commands run inside Claude Code's sandbox and are approved automatically there: the checkout
and `$TMPDIR` are writable, nothing else is, and there is no network. So: put scratch files in
`$TMPDIR` or `$(mktemp -d)`; run scripts as `uv run python - <<'EOF' … EOF` or from `$TMPDIR`; never
start a command with `VAR=value` (that form needs a permission prompt, which headless runs deny); use
WebFetch/WebSearch, not curl, for sources. The virtual environment is already built.

## general / software
Behavior vs implementation tests · edge cases (empty, degenerate geometry, zero current) · swallowed
exceptions · tolerances loose enough to pass wrong answers · changes outside the stated scope ·
deleted or weakened tests · hidden global state · performance regressions in hot paths.

## physics
Units and dimensional consistency · sign/orientation conventions · boundary conditions · limiting
cases (thin wire, widely separated conductors → dipole-like mutual coupling, DC vs high frequency,
skin depth vs copper thickness) · reciprocity (M_ij = M_ji) and passivity (inductance matrix positive
definite; resistances non-negative) · complete current return paths including baseplate and
eddy/image currents · bond-wire models and their validity ranges · thermal: energy balance, boundary
conditions, temperature-dependent properties.

## numerics
Convergence under refinement (show the numbers) · discretization dependence of rankings, not only of
values · conditioning of linear solves · float32 vs float64 · seed sensitivity · agreement with an
independent method on a case neither was tuned on.

## statistics
Sample size and the width of the intervals · representativeness and diversity of the sample ·
leakage between development and evaluation data · number of evaluations performed (forking paths) ·
appropriateness of the CI method for n · whether the metric matches the decision it supports
(ranking vs absolute accuracy vs top-k selection) · pre-registration respected.

## evidence provenance (for evaluation reviews)
Result commits are on main and clean · spec hashes match registered specs · seeds recorded and
sealed where required · sanity checks are real (could have failed) · artifacts exist · evaluator
verdict reproduces from the result files.
