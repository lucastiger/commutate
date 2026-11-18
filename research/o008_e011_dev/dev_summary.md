manifest status: complete: L1 stages done, L2 pending (burst VM); generated 2026-11-17T21:10:19+00:00; git 8a8b8fc136; dev_seed 20261116
code_stamp tree 33dac5c7b2fc7a5e, config 96d37c745505fde9

## 2D_Case_2R

- in_domain(W, reach) True; counted True
- frozen proxy (reach=True, min_gain 1e-12 H): steps 25, kind local_optimum, L1(W*)/L1(W) 0.9138, W* in domain True, DRC-clean True
  - sensitivity threshold_free: steps 35, kind local_optimum, L1 ratio 0.9136, same layout as frozen False
  - sensitivity reach_false_probe: steps 27, kind local_optimum, L1 ratio 0.8979, same layout as frozen False
  - sensitivity dies_fixed: steps 17, kind local_optimum, L1 ratio 0.9302, same layout as frozen False
  - sensitivity dcm_alt_reading: steps 23, kind local_optimum, L1 ratio 0.9149, same layout as frozen False
- Tj (K, level 0): W 398.10, Wstar 396.49, dies_fixed 397.96; P_ref 59.5 W
- degradation: 8 attempts, L1 stop ratio min/median/max 1.3092/1.4034/1.5377, rate reaching the L1 target 0.875, attempts missing it (would still cost an L2 call) 1, out-of-domain defects 0
  - per-draw L1(D_j)/L1(W*): 1.403, 1.309, 1.395, 1.434, 1.538, 1.421, 1.404, 1.392

### Search (budget 2000 L1 evaluations)

| draw | L1 gain rel | share last 10 % [lo] | exact | share last 25 % [lo] | exact | last improving eval | steps | l1_evals | stop | seed in domain | changed from D | changed from W* | Manhattan from W* mm |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | 0.2831 | 0.009 [0.005] | False | 0.025 [0.005] | False | 1984 | 34 | 2000 | budget | True | 17 | 17 | 36.5 |
| 1 | 0.2016 | 0.000 [0.000] | False | 0.001 [0.000] | False | 1897 | 37 | 2000 | budget | True | 18 | 17 | 27.5 |
| 2 | 0.2663 | 0.000 [0.000] | False | 0.001 [0.000] | False | 1860 | 40 | 2000 | budget | True | 19 | 12 | 21.0 |
| 3 | 0.2642 | 0.003 [0.001] | False | 0.030 [0.001] | False | 2000 | 38 | 2000 | budget | True | 19 | 16 | 31.5 |
| 4 | 0.3445 | 0.004 [0.000] | False | 0.030 [0.000] | False | 1996 | 33 | 2000 | budget | True | 22 | 23 | 34.0 |
| 5 | 0.2988 | 0.003 [0.000] | False | 0.012 [0.000] | False | 1987 | 40 | 2000 | budget | True | 22 | 13 | 15.0 |
| 6 | 0.2796 | 0.000 [0.000] | False | 0.002 [0.000] | False | 1976 | 38 | 2000 | budget | True | 20 | 18 | 30.5 |
| 7 | 0.2826 | 0.000 [0.000] | False | 0.015 [0.000] | False | 1956 | 40 | 2000 | budget | True | 26 | 13 | 25.0 |

median share last 10 %: 0.001; last 25 %: 0.013; draws with stats improving_last10: 8 of 8 (search end point = its lowest-L1 layout)

### Nulls (b) widen, (d) compact, NULL_STEP_LIMIT 200

| draw | L1(D_j)/L1(W*) | role | steps | terminal | seed_in_domain | n_neighbours step 0 | changed from D | Manhattan from D mm | changed from W* | Manhattan from W* mm |
|---|---|---|---|---|---|---|---|---|---|---|
| 0 | 1.403 | widen | 25 | local_optimum | True | 66 | 11 | 25.5 | 17 | 27.5 |
| 1 | 1.309 | widen | 16 | local_optimum | True | 59 | 11 | 23.0 | 18 | 23.5 |
| 2 | 1.395 | widen | 16 | local_optimum | True | 60 | 8 | 14.0 | 13 | 23.0 |
| 3 | 1.434 | widen | 18 | local_optimum | True | 62 | 11 | 20.5 | 21 | 29.0 |
| 4 | 1.538 | widen | 23 | local_optimum | True | 72 | 12 | 25.0 | 19 | 35.5 |
| 5 | 1.421 | widen | 24 | local_optimum | True | 58 | 10 | 19.5 | 16 | 23.5 |
| 6 | 1.404 | widen | 26 | local_optimum | True | 59 | 10 | 25.5 | 15 | 24.5 |
| 7 | 1.392 | widen | 14 | local_optimum | True | 56 | 7 | 10.5 | 17 | 35.5 |
| 0 | 1.403 | compact | 36 | local_optimum | True | 66 | 13 | 31.0 | 15 | 22.0 |
| 1 | 1.309 | compact | 21 | local_optimum | True | 59 | 13 | 25.5 | 16 | 21.0 |
| 2 | 1.395 | compact | 24 | local_optimum | True | 60 | 10 | 18.0 | 11 | 19.0 |
| 3 | 1.434 | compact | 22 | local_optimum | True | 62 | 14 | 22.5 | 21 | 28.0 |
| 4 | 1.538 | compact | 34 | local_optimum | True | 72 | 15 | 30.5 | 19 | 32.0 |
| 5 | 1.421 | compact | 33 | local_optimum | True | 58 | 12 | 24.0 | 14 | 19.0 |
| 6 | 1.404 | compact | 35 | local_optimum | True | 59 | 12 | 30.0 | 13 | 20.0 |
| 7 | 1.392 | compact | 25 | local_optimum | True | 56 | 9 | 16.0 | 15 | 30.0 |

terminal kinds: compact local_optimum: 8, widen local_optimum: 8

### Ablations

| draw | (c) random screen l1_evals | (c) n_draws | (e) proxy alone steps | (e) kind | (e) L1 evals |
|---|---|---|---|---|---|
| 0 | 2000 | 2000 | 36 | budget | None |
| 1 | 2000 | 2000 | 28 | local_optimum | None |
| 2 | 2000 | 2000 | 28 | local_optimum | None |
| 3 | 2000 | 2000 | 39 | budget | None |
| 4 | 2000 | 2000 | 34 | budget | None |
| 5 | 2000 | 2000 | 35 | local_optimum | None |
| 6 | 2000 | 2000 | 35 | local_optimum | None |
| 7 | 2000 | 2000 | 42 | budget | None |

### DC- reading, search of draw 0

- draw 0: lowest L1 frozen 1.026752e-08 H, alt 1.026752e-08 H (relative +0.00e+00); shortlist identical False

- degradation entropy lists start with DEGRADE_TAG: True (8 lists)

## 2D_Case_4

- in_domain(W, reach) True; counted True
- frozen proxy (reach=True, min_gain 1e-12 H): steps 73, kind local_optimum, L1(W*)/L1(W) 0.6533, W* in domain True, DRC-clean True
  - sensitivity threshold_free: steps 81, kind local_optimum, L1 ratio 0.6532, same layout as frozen False
  - sensitivity reach_false_probe: steps 120, kind local_optimum, L1 ratio 0.6280, same layout as frozen False
  - sensitivity dies_fixed: steps 63, kind local_optimum, L1 ratio 0.7014, same layout as frozen False
  - sensitivity dcm_alt_reading: steps 73, kind local_optimum, L1 ratio 0.6533, same layout as frozen True
- Tj (K, level 0): W 398.08, Wstar 396.05, dies_fixed 397.97; P_ref 70.5 W
- degradation: 8 attempts, L1 stop ratio min/median/max 1.3900/1.3950/1.4212, rate reaching the L1 target 1.000, attempts missing it (would still cost an L2 call) 0, out-of-domain defects 0
  - per-draw L1(D_j)/L1(W*): 1.390, 1.397, 1.392, 1.400, 1.421, 1.393, 1.407, 1.390

### Search (budget 2000 L1 evaluations)

| draw | L1 gain rel | share last 10 % [lo] | exact | share last 25 % [lo] | exact | last improving eval | steps | l1_evals | stop | seed in domain | changed from D | changed from W* | Manhattan from W* mm |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | 0.2704 | 0.043 [0.004] | False | 0.132 [0.004] | False | 1998 | 32 | 2000 | budget | True | 17 | 17 | 26.0 |
| 1 | 0.2888 | 0.024 [0.004] | False | 0.096 [0.004] | False | 1957 | 31 | 2000 | budget | True | 22 | 29 | 35.5 |
| 2 | 0.2857 | 0.039 [0.013] | False | 0.122 [0.013] | False | 1995 | 30 | 2000 | budget | True | 21 | 22 | 38.5 |
| 3 | 0.2785 | 0.021 [0.003] | False | 0.091 [0.003] | False | 1989 | 34 | 2000 | budget | True | 23 | 22 | 25.5 |
| 4 | 0.2956 | 0.029 [0.005] | False | 0.128 [0.005] | False | 1975 | 27 | 2000 | budget | True | 21 | 27 | 38.0 |
| 5 | 0.2791 | 0.027 [0.003] | False | 0.079 [0.003] | False | 1993 | 32 | 2000 | budget | True | 24 | 24 | 53.5 |
| 6 | 0.2850 | 0.014 [0.002] | False | 0.085 [0.002] | False | 1977 | 30 | 2000 | budget | True | 25 | 13 | 16.0 |
| 7 | 0.2766 | 0.060 [0.005] | False | 0.162 [0.005] | False | 1996 | 31 | 2000 | budget | True | 19 | 26 | 30.0 |

median share last 10 %: 0.028; last 25 %: 0.109; draws with stats improving_last10: 8 of 8 (search end point = its lowest-L1 layout)

### Nulls (b) widen, (d) compact, NULL_STEP_LIMIT 200

| draw | L1(D_j)/L1(W*) | role | steps | terminal | seed_in_domain | n_neighbours step 0 | changed from D | Manhattan from D mm | changed from W* | Manhattan from W* mm |
|---|---|---|---|---|---|---|---|---|---|---|
| 0 | 1.390 | widen | 30 | local_optimum | True | 65 | 11 | 18.0 | 17 | 32.0 |
| 1 | 1.397 | widen | 45 | local_optimum | True | 68 | 14 | 31.0 | 21 | 40.5 |
| 2 | 1.392 | widen | 49 | local_optimum | True | 66 | 18 | 41.5 | 23 | 42.5 |
| 3 | 1.400 | widen | 44 | local_optimum | True | 69 | 15 | 27.5 | 24 | 33.0 |
| 4 | 1.421 | widen | 49 | local_optimum | True | 74 | 16 | 29.0 | 28 | 35.0 |
| 5 | 1.393 | widen | 58 | local_optimum | True | 66 | 18 | 45.0 | 23 | 47.5 |
| 6 | 1.407 | widen | 36 | local_optimum | True | 71 | 16 | 24.0 | 19 | 30.5 |
| 7 | 1.390 | widen | 44 | local_optimum | True | 62 | 16 | 34.0 | 23 | 33.5 |
| 0 | 1.390 | compact | 53 | local_optimum | True | 65 | 15 | 29.5 | 16 | 24.5 |
| 1 | 1.397 | compact | 70 | local_optimum | True | 68 | 18 | 43.5 | 22 | 30.0 |
| 2 | 1.392 | compact | 66 | local_optimum | True | 66 | 21 | 50.0 | 20 | 34.0 |
| 3 | 1.400 | compact | 55 | local_optimum | True | 69 | 18 | 33.0 | 24 | 29.5 |
| 4 | 1.421 | compact | 63 | local_optimum | True | 74 | 20 | 36.0 | 29 | 32.0 |
| 5 | 1.393 | compact | 73 | local_optimum | True | 66 | 21 | 52.5 | 22 | 43.0 |
| 6 | 1.407 | compact | 55 | local_optimum | True | 71 | 19 | 33.5 | 18 | 25.0 |
| 7 | 1.390 | compact | 62 | local_optimum | True | 62 | 19 | 43.0 | 22 | 27.5 |

terminal kinds: compact local_optimum: 8, widen local_optimum: 8

### Ablations

| draw | (c) random screen l1_evals | (c) n_draws | (e) proxy alone steps | (e) kind | (e) L1 evals |
|---|---|---|---|---|---|
| 0 | 2000 | 2000 | 35 | budget | None |
| 1 | 2000 | 2000 | 33 | budget | None |
| 2 | 2000 | 2000 | 33 | budget | None |
| 3 | 2000 | 2000 | 34 | budget | None |
| 4 | 2000 | 2000 | 29 | budget | None |
| 5 | 2000 | 2000 | 35 | budget | None |
| 6 | 2000 | 2000 | 31 | budget | None |
| 7 | 2000 | 2000 | 35 | budget | None |

### DC- reading, search of draw 0

- draw 0: lowest L1 frozen 1.282598e-08 H, alt 1.282598e-08 H (relative +0.00e+00); shortlist identical False

- degradation entropy lists start with DEGRADE_TAG: True (8 lists)

## VM sizing

{
 "machine": "n2d-custom-8-81920-ext (regular, not Spot, for the registered run)",
 "usable_GB": 66.3,
 "vcpus": 8,
 "threads_per_solve": 2,
 "at_once_by_vcpus": 4,
 "largest_solve_GB": 25.27,
 "largest_fit_at_once": 2,
 "measured_mem_ratio": {
  "lat0.5": 0.9013,
  "lat0.25": 1.0066
 }
}

| layout | level | unknowns | jobs | wall h each | model GB | sched GB prior | at once prior | sched GB learned | at once learned |
|---|---|---|---|---|---|---|---|---|---|
| 2D_Case_2R | fil_f | 385179 | 34 | 0.111 | 2.21 | 5.74 | 4 | 5.74 | 4 |
| 2D_Case_2R | lat0.25 | 1540717 | 34 | 0.39 | 6.42 | 10.28 | 4 | 7.11 | 4 |
| 2D_Case_2R | lat0.5 | 385179 | 168 | 0.053 | 2.21 | 3.53 | 4 | 2.19 | 4 |
| 2D_Case_2R | thk_c | 192589 | 34 | 0.027 | 1.5 | 2.25 | 4 | 2.25 | 4 |
| 2D_Case_2R | thk_f | 770358 | 34 | 0.22 | 3.61 | 6.5 | 4 | 6.5 | 4 |
| 2D_Case_4 | fil_f | 1027145 | 34 | 0.457 | 4.55 | 11.83 | 4 | 11.83 | 4 |
| 2D_Case_4 | lat0.25 | 4108580 | 34 | 1.603 | 15.8 | 25.27 | 2 | 17.49 | 3 |
| 2D_Case_4 | lat0.5 | 1027145 | 171 | 0.218 | 4.55 | 7.28 | 4 | 4.51 | 4 |
| 2D_Case_4 | thk_c | 513572 | 34 | 0.109 | 2.67 | 4.01 | 4 | 4.01 | 4 |
| 2D_Case_4 | thk_f | 2054290 | 34 | 0.904 | 8.3 | 14.94 | 4 | 14.94 | 4 |

dev burst: {"prior": {"makespan_h": 71.45, "usd": 44.03}, "learned": {"makespan_h": 61.42, "usd": 37.9}, "basis": "wave 1 (every manifest job) then wave 2 (the band of each shortlist's best), list scheduling by memory and vCPUs; usd = (makespan + overhead_h) x usd_per_h"}

registered run (timeout 120.0 h): {"prior|no_redraws": {"makespan_h": 212.3, "usd": 130.22, "fits_timeout": false}, "prior|max_redraws": {"makespan_h": 246.4, "usd": 151.12, "fits_timeout": false}, "learned|no_redraws": {"makespan_h": 170.2, "usd": 104.49, "fits_timeout": false}, "learned|max_redraws": {"makespan_h": 198.0, "usd": 121.46, "fits_timeout": false}}

registered solves: {"2D_Case_2R": {"source": "dev manifest", "P": {"lat0.25": 2, "lat0.5": 2, "thk_c": 2, "thk_f": 2, "fil_f": 2}, "D_wave0": {"lat0.25": 8}, "redraw_waves_max": 4, "S1": {"lat0.25": 152}, "S1_nominal": 152, "S2": {"lat0.5": 48, "thk_c": 48, "thk_f": 48, "fil_f": 48}, "L1_wall_h_mac": 1.05, "unknowns": {"lat0.25": 1540717, "lat0.5": 385179, "thk_c": 192589, "thk_f": 770358, "fil_f": 385179}}, "2D_Case_4": {"source": "dev manifest", "P": {"lat0.25": 2, "lat0.5": 2, "thk_c": 2, "thk_f": 2, "fil_f": 2}, "D_wave0": {"lat0.25": 8}, "redraw_waves_max": 4, "S1": {"lat0.25": 152}, "S1_nominal": 152, "S2": {"lat0.5": 48, "thk_c": 48, "thk_f": 48, "fil_f": 48}, "L1_wall_h_mac": 0.674, "unknowns": {"lat0.25": 4108580, "lat0.5": 1027145, "thk_c": 513572, "thk_f": 2054290, "fil_f": 1027145}}, "gen2_0": {"source": "nominal (no dev run)", "P": {"lat0.25": 2, "lat0.5": 2, "thk_c": 2, "thk_f": 2, "fil_f": 2}, "D_wave0": {"lat0.25": 8}, "redraw_waves_max": 4, "S1": {"lat0.25": 152}, "S1_nominal": 152, "S2": {"lat0.5": 48, "thk_c": 48, "thk_f": 48, "fil_f": 48}, "L1_wall_h_mac": null, "unknowns": {"lat0.25": 2248513, "lat0.5": 562128, "thk_c": 281064, "thk_f": 1124256, "fil_f": 562128}}}

totals: {"jobs_wave1": 611, "shortlist_jobs": 264, "shortlist_groups": 34, "jobs_by_level": {"fil_f": 68, "lat0.25": 68, "lat0.5": 339, "thk_c": 68, "thk_f": 68}, "sum_est_wall_h_vm": 176.07, "makespan_h_wave1": 50.84, "usd_wave1": 31.12, "wave2_sum_wall_h_vm": 69.57, "usd_wave2_upper_serial_share": 21.29}
