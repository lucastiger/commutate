# O008 draft: development probe of the planted-headroom control (L1 only)

Founder session, 2026-11-15, after O008's second draft reviews (T0353 statistics, T0354 physics), both reject. The
founder chose to settle two empirical questions before revising: whether a degradation that is DRC-clean under the
reference's own rules reaches the 1.25 target, and whether an inductance-blind heuristic passes the control.

**Scope and limits.** L1 only (`twin._l1`, as E010's runner). Development geometry only: 2D_Case_2R and 2D_Case_4 (both
development geometry under D0023), from their saved contexts (2R: E010's `ctx.pkl`; Case 4: E008's development run,
`research/o003/e008_dev/full_work/2D_Case_4/ctx.pkl`, not in the repository). Development seeds only (20261115+j).
Rules: each reference's `spec.rules` (E010's `e008_rules`: measured, `min_signal_wire_length` dropped), with no relaxed
power-width floor. No l2_layout, thermal, sealed seed or judged reference. C002 supports L1 ranking on generator
families on the default stack, not on these PowerSynth geometries, and L1 is biased low by 5-14 % and not
mesh-converged, so every number below is indicative until confirmed at L2.

Script: `research/o008_probe/probe.py` (docstring has the method). Outputs: `research/o008_probe/probe_{2R,Case4}.json`
(control target the twin W) and `probe_{2R,Case4}_proxy.json` (control target a designer proxy W*).

## Method
- Degradation: the frozen `twin.degrade`, and a randomised family (stochastic L1 ascent by joint moves of 2-4 copper
  parameters, 0.5-2 mm each, DRC-clean, up to 400 proposals, stop at the frozen L1 target 1.3875).
- From each degraded start, three searches over `twin._walk_candidates` (single copper parameter, +-0.5 mm, DRC-clean),
  steepest step, at most 60 steps: **guided** (minimise L1, a stand-in for the seeded search), **compact** (review
  T0354's null (d): inductance-blind, more power copper and shorter power wires) and **widen** (null (b): copper only).
- Shortfall s = L1(result) / L1(target) - 1.
- Designer proxy W*: a guided descent from the twin W (at most 200 steps; both stopped at a local optimum).

## Results

### Target = the twin W
| | 2D_Case_2R | 2D_Case_4 |
|---|---|---|
| frozen degrade under own rules | 1.395 (target reached) | DegradeError at 1.232 (local maximum) |
| random draws reaching 1.25 / 1.3875 | 5 / 3 of 5 (1.35-1.44) | 0 / 0 of 5 (1.13-1.18) |
| guided s | -10.6 % to -5.5 % | -27 % to -22 % (step cap) |
| compact s (null d) | -5.4 % to +1.3 % | -10 % to -4 % |
| widen s (null b) | +6 % to +15 % | -10 % to -4 % |

Blind compaction gets back to the twin's level on every 2R draw, as T0354 predicted: a control that asks for recovery
to W does not discriminate. Case 4 cannot supply a 1.25 degradation of W under its own rules.

### Target = the designer proxy W*
| | 2D_Case_2R | 2D_Case_4 |
|---|---|---|
| L1(W*) / L1(W) | 0.898 (27 steps) | 0.628 (120 steps) |
| frozen degrade of W* | 1.402 | 1.391 |
| random draws reaching 1.25 / 1.3875 | 5 / 4 of 5 (1.37-1.44) | 5 / 4 of 5 (1.36-1.40) |
| guided s | -3.7 % to +0.8 %; 5 of 5 within 2 % | +1.2 % to +3.6 %; 2 of 5 within 2 %, all at the step cap |
| compact s (null d) | +3.1 % to +8.8 %; 0 of 5 within 2 % | +14 % to +19 %; 0 of 5 |
| widen s (null b) | +8 % to +24 % | +14 % to +21 % |

With W* as the target, degradations reach the target on both references, and both inductance-blind nulls fail on
every draw by a wide margin, while the guided search recovers to within 2 % on 2R and comes close on Case 4 within 60
steps.

### Target = the designer proxy W*, die rows held fixed everywhere (after review T0358)
Run on 2026-11-15 with `diesfixed`: the die-row parameters (row_*) never move, in the proxy, the degradation or any
search. Outputs `probe_{2R,Case4}_proxy_diesfixed.json`.

| | 2D_Case_2R | 2D_Case_4 |
|---|---|---|
| L1(W*) / L1(W) | 0.934 (12 steps) | 0.670 (73 steps) |
| frozen degrade of W* | 1.391 | 1.392 |
| random draws reaching 1.25 / 1.3875 | 5 / 5 of 5 | 5 / 5 of 5 |
| guided s | -0.3 % to +1.1 %; 5 of 5 within 2 % | -0.4 % to +5.3 %; 3 of 5 within 2 %, all at the step cap |
| compact s (null d) | -0.0 % to +1.5 %; **5 of 5 within 2 %** | +12 % to +21 %; 0 of 5 |
| widen s (null b) | +7 % to +17 % | +12 % to +21 % |

With die rows fixed, 2R's copper-only optimum is shallower (6.6 % below the twin, against 10.2 % with die rows free)
and blind compaction reaches it on every draw: the control does not discriminate on 2R. With die rows free in the
proxy, the degradation, the search and the nulls alike (the previous table), compaction failed on every draw on both
layouts. Most of Case 4's L1 gain is copper (33 % of the 37 %).

## What follows for O008 (proposals)
1. The control's target is a designer proxy W*, found by a frozen, long L1-guided descent from the twin under the
   reference's own rules and confirmed at l2_layout (the lower of W and W* by L_sub), not the twin itself. Die rows
   move in the proxy, the degradation, the search and the nulls alike: held fixed, the control does not discriminate
   on 2R.
2. Nulls (b) and (d) are judged per layout and must fail; the probe suggests they do by 3-19 %.
3. Case 4 becomes usable (degradations of W* reach 1.25); the synthetic housings can be dropped from the count.
4. The search budget matters: on Case 4 all guided runs were still improving at 60 steps.

## A finding for the thesis review (hypothesis-generating, not evidence)
Under each reference's own measured rules, a local search seeded at the twin finds layouts 10 % (2R) and 37 % (Case 4)
below the twin at L1. If that held at L2, it would be substantial loop-inductance headroom on public references, the
quantity A-T3 asks about. It is not evidence: L1 only (outside C002's scope), development geometry whose E010 values
were seen (D0023), unsealed, no thermal check (dies may move), and possibly exploiting L1's known bias or an unmodelled
constraint. An l2_layout check of W against W* on both references is the cheap next test.
