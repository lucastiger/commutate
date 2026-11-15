# E010 generator: a slot stack across split free windows (T0338 change, checked in T0339; D0021 item 2(a))

Generator/DRC feasibility only, with unsealed seeds. No L1, EM, thermal, FV, degrade(), twin() or search was run on
2D_Case_2R, and 2D_Case_6 was not used here. The builder's draft (git show 21bbf29a:research/notes/e009-generator.md) was
checked against the merged derivative.py (242a6d7a). Its counts are reproduced exactly: seed 20261114 gives 1028 DRC-clean
draws in 300 000 in both runs.

**What split the region [F].** On 2D_Case_2R the fixed gate and Kelvin copper forms two bars along u (GATE_LS v 25..29 mm,
GATE_HS v 31..35 mm). With the nets' spacing to them, the PHASE free region in orientation 0 has v windows (7, 23) and
(39, 53) mm. The smallest four-slot stack is taller than either window, so the old sampler, which put the whole stack into
one window, returned None on every orientation-0 draw: 0 DRC-clean in 312 000 draws (D0021). The twin's stack spans both
windows.

**New rule [F, derivative.py].** `_Ctx.split[o]` is True when no window of orientation o holds the minimal stack. Only
then does `_place_split` place each slot in a window of its own net. Die slots must also fall inside the gate/Kelvin reach
window. A backward pass gives the latest feasible starts and a forward pass draws the starts. `limit()` clips a slot's u end
at the net's free region (`_Ctx.reach`). `build`, `_quick_ok` and drc.check still judge every draw.

**Scope (review T0341 [F]).** Cross-window placement applies only where `split` is True. On 2R that is {0: True, 1: False}.
A housing that is split but has one window that still holds the minimal stack keeps the old single-window rule.

**Why development draws are unchanged [F].** The new code runs only where `split[o]` is True. Elsewhere the RNG calls are the
old ones, in the old order. `split` is False in both orientations of gen2_0 and 2D_Case_4. E008's sealed gen2_0 main and
control dev streams (2 x 20 000 candidates) regenerate byte-identically (fingerprint and family) under the merged code.
That is a DoD command of T0339, and T0341 also ran it.

## Output of research/o003/e010_dev/feasibility_2r.py (log: research/o003/e010_dev/feasibility_2r.log)
```
housing powersynth_2D_Case_2R: split orientations {0: True, 1: False}; v windows {0: [(7.0, 23.0), (39.0, 53.0)], 1: [(7.0, 48.0)]}
[main, seed 20261114] 300000 draws in 13.99 s; outcomes {'sampler None': 296171, '_quick_ok': 2648, 'DRC-clean': 1028, 'DRC': 153}
  DRC-clean mix (orient, hs_first, hs_die_first, ls_die_first): {'(0, 0, 1, 0)': 1028}; orientation {'0': 1028}; topology {'x/DC-l-PHASEd-DC+d-PHASEl/split': 1028}
  twin configuration (0, 0, 1, 0) drawn 1028 times; longest failure run 3138; generate(spec, 20) ok True
  p = 3.427e-03 (99.9 % Wilson lower bound 3.112e-03); draws per candidate 292; wall per candidate 13.61 ms; P(20000-candidate screen hits 20000 consecutive failures) <= 1.673e-23 (q 8.366e-28)
[control, seed 20261115] 300000 draws in 14.52 s; outcomes {'sampler None': 296132, '_quick_ok': 2742, 'DRC-clean': 998, 'DRC': 128}
  DRC-clean mix (orient, hs_first, hs_die_first, ls_die_first): {'(0, 0, 1, 0)': 998}; orientation {'0': 998}; topology {'x/DC-l-PHASEd-DC+d-PHASEl/split': 998}
  twin configuration (0, 0, 1, 0) drawn 998 times; longest failure run 2011; generate(spec, 20) ok True
  p = 3.327e-03 (99.9 % Wilson lower bound 3.017e-03); draws per candidate 301; wall per candidate 14.55 ms; P(20000-candidate screen hits 20000 consecutive failures) <= 1.129e-22 (q 5.646e-27)
estimated wall time for 2 x 20000 candidates (main + control), drawing only, this Mac: 9.4 min
counts equal to --check-references (research/o003/e010_dev/check_references.json): True
gen2_0 (dev): 56 of 200 DRC-clean candidates share the twin's topology x/PHASEl-DC+d-PHASEd-DC-l/split
wrote research/o003/e010_dev/feasibility_2r.json
```
Reading [F]: every DRC-clean 2R draw has the twin's discrete configuration (0, 0, 1, 0), meaning orientation 0 and
sequence 0/1/0, and one topology. Orientation 1 yields none. So E010's 2R search varies geometry only inside the
reference's own topology. On gen2_0, 56 of 200 candidates (seed 7) share the twin's topology. The bound P(abort) <= 1e-22 per
screen assumes i.i.d. draws [I: each draw takes fresh numbers from one rng, and _Ctx is fixed]. The draw time is Mac wall
time for generation only. The screen's L1 cost is extra, and it was not measured on 2R (not allowed before registration).
