# Commutate

**A physics-first layout compiler for SiC and IGBT power modules.** Give it an existing module layout and a die change. It
returns manufacturable re-layouts with lower loop inductance and bounded junction temperature, plus decks the customer
can verify in their own Ansys Q3D/Icepak flow.

> The Python package and internal tooling are still called `moduleforge` (the working name before Commutate).

---

## The problem

Every EV inverter, solar inverter and industrial drive contains power modules: silicon-carbide (SiC) or IGBT dies
wire-bonded onto a copper-on-ceramic substrate inside a fixed plastic housing. The layout of that copper decides the
**commutation loop**, the path the switching current takes. SiC switches so fast that a few nanohenries in that loop
set the voltage overshoot (V = L·di/dt), the switching losses and the EMI.

Module makers re-lay out an existing module whenever the die changes: **a new die generation, a second-source supplier,
or a different number of paralleled dies, inside the same housing and pins.** Today an engineer redraws it by hand in
CAD and iterates through field-solver runs (Q3D for parasitics, Icepak for thermal) and prototype builds. Each
derivative takes several design–build–test loops.

## What Commutate does

```
reference layout + housing + stack + design rules + new dies
                         │
         fast physics models (screen thousands of candidates)
                         │
       converged reference solvers (audit the finalists)
                         │
  DRC-clean re-layouts  ·  loop L, current sharing, Tj per die  ·  Q3D/Icepak decks to verify
```

- **Search with physics in the loop.** A fast electromagnetic model (partial-element equivalent circuit, about 22 ms
  per layout on one core) ranks thousands of candidate layouts. Converged in-house reference solvers then check the
  finalists for inductance and junction temperature.
- **Hard manufacturing rules, not suggestions.** Every candidate passes design-rule checks (trace width, spacing,
  wire-bond pitch and length) inside the customer's own outline, terminals and stack.
- **Verification the customer trusts.** The output is meant to be checked in the customer's existing sign-off tools,
  not taken on faith.

The first product is a **derivative re-layout sprint**: same housing, new dies, a better layout in days rather than
several hardware iterations.

## What is proven so far (5 weeks in)

The two solver results below are pre-registered experiments with sealed seeds, declared null baselines and an
independent recomputation of every metric. Each row links to its evidence.

| result | evidence |
|---|---|
| The in-house reference inductance solver matches closed-form inductances to **0.013 %** (max relative error) across 7 geometry classes | [E001](experiments/results/E001) |
| On **90 sealed, design-rule-clean half-bridge layouts**, the fast model ranks loop inductance like the converged reference: Spearman **ρ = 0.996** (95 % CI 0.990–0.998), top-decile recall 1.0, median **22 ms** per layout on one core | [E002](experiments/results/E002), claim [C002](project/claims/C002.yaml) |
| The fast model's limits are stated, not hidden: it is biased low by 5–14 % in absolute terms, reliable for ranking only when layouts differ by about 5 % or more, and validated on one substrate stack | [C002 caveats](project/claims/C002.yaml) |
| No commercial product found that re-lays out wire-bonded modules against parasitic and thermal objectives. The nearest are a general-purpose optimizer from Siemens (method unpublished) and an academic GPL tool (PowerSynth 2) | [competitive landscape](research/notes/a-t6-competitive-landscape.md) |

**In progress:** verifying the thermal reference solver (junction temperature) against analytic solutions and an
independent FEM code ([O006](project/objectives/O006/objective.yaml)).

## The test that decides the company

The thesis can fail, and the plan says so. By **2026-11-27** (day 60) the company runs one experiment that decides
whether it continues ([O003](project/objectives/O003/objective.yaml), [charter](project/charter.md)):

> Inside the reference module's own housing, terminals, dies and wire bonds, can search find a layout with **≥ 20 %
> lower commutation-loop inductance** at **≤ +2 K** junction temperature?

The kill line is below 10 %. The one public comparison against a commercial module implies about 18 % headroom (an
inference, [notes](research/notes/o003-public-benchmarks.md)), so the outcome is genuinely open. Customer reference
layouts shared under NDA come first; public benchmark modules are the fallback.

## How a solo founder runs a physics R&D program

Commutate is built by one founder working with a team of AI agents. The agents work under rules strict enough that their
results can be trusted:

- **`mfos`** ([tools/mfos](tools/mfos), [architecture](docs/ARCHITECTURE.md)) is an in-repo operating system. It turns
  frozen, founder-approved hypotheses into tasks for builder, scientist and critic agents. Each agent works in its own
  git worktree under a budget cap.
- **Evidence is mechanical, not narrative.** Experiments are registered before they run. The evaluator recomputes every
  metric from raw rows. Blinded critic agents review designs and claims adversarially, and an agent's own report never
  counts as evidence.
- **Decisions are on the record.** Changed criteria, failed checks and course corrections are written up as decision
  records ([project/decisions](project/decisions)). Claims carry their caveats ([project/claims](project/claims)).

In five weeks this produced about 960 commits, around 190 agent tasks and two validated solvers, for under $450 of
model usage.

## Repository map

| path | contents |
|---|---|
| [`src/moduleforge/`](src/moduleforge) | product code: geometry and design-rule checks, layout generator, fast PEEC model, reference EM and thermal solvers |
| [`tests/`](tests) | unit and regression tests against analytic values, limits, symmetry and scaling |
| [`experiments/`](experiments) | registered specs, runners and results |
| [`project/`](project) | charter and assumptions, objectives, decision records, claims, task state, generated [STATUS](project/STATUS.md) |
| [`research/`](research) | literature notes, competitive landscape, diagnoses |
| [`tools/mfos/`](tools/mfos) | the research operating system |

## Quick start

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync --all-groups
uv run pytest -q -m 'not slow' tests/unit   # fast tests
uv run mfos status                          # objectives, tasks and spend
```

## Working with us

We're looking for **design partners**: module makers, Tier-1s and OEMs with an upcoming derivative (a die change in an
existing housing). Customer layouts are processed under NDA and never enter this repository.
