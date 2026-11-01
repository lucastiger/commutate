# D0007 — PowerSynth 2 (GPL-3.0): sample designs as benchmark inputs; the tool as an unmodified external comparison
Date: 2026-10-31 · Status: accepted · Decider: founder (founder session, 2026-10-31)

## Context
O003's day-60 criterion needs public reference layouts. `research/notes/o003-public-benchmarks.md` found no public
re-layout benchmark; the most reconstructable inputs are PowerSynth's sample designs (e3da/PowerSynth2-pkg,
`work/Sample_Designs`, e.g. 2D_Case_2R and 2D_Case_6), licensed GPL-3.0. `research/notes/a-t6-competitive-landscape.md`
identifies PowerSynth 2 (GPL-3.0, v2.2, June 2025) as the closest functional competitor. Policy allows permissive
licences only inside the product; D0002 set the precedent for using a tool as a separate, unmodified executable.

## Decision
- PowerSynth sample designs may be used as external benchmark inputs. Their geometry facts (dimensions, layer stack,
  die and bond-wire placement) are re-modelleout format. The GPL files themselves are never
  committed to this repository, imported or redistributed. Each experiment that uses them records the repository
  commit and the sha256 of every file it read
- PowerSynth 2 may be run unmodified as a separate executable, installed outside the project's uv environment, for
  internal head-to-head comparison on public d, linked, imported or redistributed. Pin the
  commit at first use.
- This is the founder's reading of the licencot legal advice. Revisit it before any
  customer-facing use or distribution of results derived from these files.

## Consequences
O003's benchmark set may include the PowerSyne the UTK, CPES and Aalborg reconstructions.
`scripts/check_licenses.py` is unaffected because nothing is installed into the environment.
