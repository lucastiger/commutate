# E007 row contract (O002; T0396)

What E007's runner writes to its rows artifact (`{"schema": "mfos.rows/1", "rows": [...]}`, flat records) so that the
evaluator can recompute A1-A5 and K1-K3 with `mfos.metrics` (commit 2fea4a6e, plus `e007_metrics.patch` for the bound).
Every temperature is in kelvin (float64); time in seconds; ratios are dimensionless. One die size per stratum, so
`(family, dies)` is the stratum key. The runner builds the layout and switch rows from its die rows with
`e007_metrics.layout_rows` and `e007_metrics.switch_rows` (tested in test_e007_metrics.py), so the hottest die, the
spreads and the null are defined in one place.

## Row kinds and columns

Common to every row: `kind` (`"die"`, `"switch"`, `"layout"`), `layout` (str, unique over the whole run, also the
cluster unit of every bound), `family` (one of `side_by_side`, `interleaved`, `u_shaped`), `dies` (int, dies per
switch, 2-6), `load` (`"P_ref"` or `"half_P_ref"`). Pair rows are **not** written: same-stratum pairs are formed inside
`pairwise_diff_error_quantile` from layout rows (self-pairs skipped by `params.unit`), so there is no second source.

| kind | column | unit | meaning | read by |
|---|---|---|---|---|
| die | `switch` | - | `"HS"` or `"LS"` | helpers |
| die | `die_index` | - | 0-based index within the switch, layout.dies order | helpers |
| die | `tj_ref_K` | K | reference die-average Tj (Galerkin integral over the die top face), judged level | A2, helpers |
| die | `tj_l1_K` | K | L1's die-average Tj, same die and load | A2, helpers |
| die | `tb_ref_K` | K | reference mean baseplate-bottom temperature of that solve | (reported) |
| die | `rise_ref_K` | K | die-local rise `tj_ref_K - tb_ref_K` (> 0; A2's scale) | A2 |
| switch | `switch` | - | `"HS"` or `"LS"` | A3, A4 |
| switch | `spread_ref_K`, `spread_l1_K` | K | max - min of the die averages over the switch's paralleled dies | A3, A4 |
| switch | `spread_null_K` | K | stratum-mean-spread null: mean `spread_ref_K` of the other layouts of the same (family, dies, load, switch), leave-one-layout-out (F2 (d)) | A4, K3 |
| layout | `tj_hot_ref_K` | K | the reference's largest die average (its hottest die) | A1, K1 |
| layout | `tj_hot_l1_K` | K | L1's die average **at the reference's hottest die** | A1, K1 |
| layout | `tj_ownhot_l1_K` | K | L1's largest die average (own-hottest variant, reported beside A1) | A1-own |
| layout | `hot_switch`, `hot_die_index` | - | which die the reference ranks hottest (ties: first in (switch, die_index) order) | (reported) |
| layout | `l1_eval_s` | s | wall time of the L1 evaluation for this (layout, load), one core | A5 |

## Recompute entries (spec `recompute`, all with `ci: {scheme: woodruff, level: 0.94, cluster: layout}` except A5)

`level: 0.94` makes `lo` and `hi` one-sided 97 % bounds (K1-K3 use `lo`; under max over loads each load's `lo` is
at 98.5 %, Bonferroni). This is F3's selection (f3_simulation.json, variant V4): at one-sided 95 % the bound covers
at about its nominal level, which the simulation cannot certify as >= 0.95 in every cell, so the selected bound is
conservative relative to the objective's "upper 95 % bound" (a 97 % bound is also a valid 95 % bound).

| metric | fn | pred / ref | strata | params | where |
|---|---|---|---|---|---|
| `dtj_pair_err_p95_K_max_load` (A1, K1) | `max_over_groups` | `tj_hot_l1_K` / `tj_hot_ref_K` | `[family, dies]` | `{fn: pairwise_diff_error_quantile, by: load, inner: {q: 0.95, unit: layout}}` | `{kind: layout}` |
| `dtj_pair_err_ownhot_p95_K_max_load` (reported) | same | `tj_ownhot_l1_K` / `tj_hot_ref_K` | same | same | same |
| `tjavg_local_rel_err_p95_max_load` (A2, K2) | `max_over_groups` | `tj_l1_K` / `tj_ref_K` | - | `{fn: quantile_rel_err, by: load, inner: {q: 0.95, scale: rise_ref_K}}` | `{kind: die}` |
| `switch_spread_err_p95_K_max_load` (A3) | `max_over_groups` | `spread_l1_K` / `spread_ref_K` | - | `{fn: quantile_abs_err, by: load, inner: {q: 0.95}}` | `{kind: switch}` |
| `switch_spread_err_ratio_vs_stratum_mean` (A4, K3) | `quantile_abs_err_ratio` | `spread_l1_K` / `spread_ref_K` | - | `{null: spread_null_K, q: 0.95}` | `{kind: switch, load: P_ref}` |
| `l1_eval_s_p50` (A5, point) | `median_col` | `l1_eval_s` | - | - | `{kind: layout}` |

F1's step-floor rule (`max_gci_step_floor`, `params: {levels: [<level-0>, <level-1>, <level-2> columns], step_floor:
0.01}`) reads three level columns per subset row; its row layout belongs to the F1 subset rows and is not fixed here.

## What the bound assumes of the rows (T0396, f3_simulation.json)
- Layouts are the independent units: errors may be correlated within a layout (all its dies, switches, loads and
  pairs), never across layouts. Every row carries its `layout`; a pair term belongs to both of its layouts.
- Each `layout` appears once per (load, switch, die) and is in exactly one stratum.
- Every (stratum, load, switch) has at least 2 layouts (the leave-one-layout-out null); the selected allocation has
  the same number of layouts in every stratum (`layouts_per_stratum` in f3_simulation.json), fixed before any solve.
- No NaN or infinity anywhere; `rise_ref_K > 0` (the metric functions fail closed otherwise).
