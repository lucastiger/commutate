# ModuleForge

Physics-first layout compiler for wire-bonded SiC/IGBT power modules. First product: reference-anchored
derivative re-layouts (new die generation, second source, or die count inside a fixed housing) that
optimize loop inductance, current sharing, gate-loop symmetry, and junction temperature under hard
manufacturing rules. The first 90 days are a falsification program: objectives are hypotheses tested
by pre-registered experiments, and the thesis can die.

## How work happens in this repository
- The repository is the source of truth. `mfos` (tools/mfos) orchestrates; state lives in `project/`
  and `experiments/`; policy lives in `.mfos/policy.toml`.
- Headless runs receive a task packet (`.mfos/packets/…`). The packet is the complete brief.
- Outcomes are decided by deterministic checks: definition-of-done commands, `mfos gate`, and the
  acceptance evaluator. An agent's own report is never evidence.
- If something is ambiguous, stop and say so. Do not invent requirements.

## Map
- `src/moduleforge/` product code: geometry, drc, generate, physics/peec (L1), solvers (L2: l2, l2_core, l2_dd,
  l2_layout). thermal, optimize and io do not exist yet
- `tests/unit/`, `tests/regression/` engineering tests · `tests/acceptance/` locked, founder-approved
- `experiments/specs/` registered, immutable · `drafts/` proposals · `runners/` experiment code · `results/` evidence
- `project/charter.md` thesis and assumptions · `objectives/<OID>/objective.yaml` frozen hypotheses ·
  `tasks/` · `decisions/` ADRs · `claims/` supported/refuted claims · `memory/` curated knowledge ·
  `STATUS.md` generated · `customers/` interview notes (confidential)
- `research/` analyses and diagnoses · `docs/` documentation, `docs/ARCHITECTURE.md` explains this system

## Commands
- `uv sync --all-groups` · fast tests: `uv run pytest -q -m 'not slow' tests/unit` · all tests: `uv run pytest -q tests`
  · `uv run ruff check .` · `uv run mfos gate --fast`
- `uv run mfos status` · `uv run mfos inbox` · `uv run mfos task list` · `uv run mfos exp check E0xx`
- Founder slash commands: /status /inbox /objective /work /investigate /thesis-review /resume

## Non-negotiables
- SI units and float64 internally; explicit seeds; cite every closed-form formula (skill mf-conventions).
- Evidence only through `mfos.evidence.ExperimentRun` with confidence intervals and sanity checks (skill mf-evidence).
- Physics code is tested against analytic values, limits, symmetry/conservation, and scaling.
- Never weaken a test or tolerance to make it pass. Never read `data/holdout/`.
- Protected paths (listed in `.mfos/policy.toml`) change only with founder approval.
- Agents never push, merge, rebase, or use `gh`. Permissive licenses only.

## Glossary
L0 geometry/DRC · L1 fast models (numpy PEEC in `physics.peec`; thermal planned) · L2 reference solvers (in-house
PEEC `solvers.l2` and `solvers.l2_layout`; FastHenry only as an optional external cross-check, D0002/D0004; a
permissively licensed thermal reference still to be chosen; ngspice double-pulse) · L3 customer Q3D/Icepak decks ·
L4 hardware.
DBC/AMB: direct-bonded / active-metal-brazed copper on ceramic. Commutation loop: DC+ → high-side
switch → phase → low-side switch → DC−. Tj: junction temperature.
