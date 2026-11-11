"""Writes experiments/drafts/E008.yaml (T0262). The fem_rule block is copied from research/o007_dev3/frozen_config.json
key for key and every freeze hash is computed here from the files, so the draft cannot carry a hand-typed value.
Cost-model numbers are updated from research/o003/e008_dev/probe_costs.json when it exists. Run: uv run python research/o003/e008_dev/make_spec.py"""
import hashlib
import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
H = lambda p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest()  # noqa: E731
FROZEN = ["src/moduleforge/generate/derivative.py", "src/moduleforge/generate/twin.py", "src/moduleforge/optimize/search.py",
          "src/moduleforge/geometry/snap.py", "src/moduleforge/drc/rules.py", "src/moduleforge/geometry/stack.py"]
probe = ROOT / "research/o003/e008_dev/probe_costs.json"
pc = json.loads(probe.read_text()) if probe.exists() else {}
A4 = 0.080 * 0.110  # 2D_Case_4 baseplate lattice, m2 (research/scripts/o006_case4_layout.py BASEPLATE)
dofs = {str(v): pc.get(f"dofs_L{v}", {0: 6.0e4, 1: 4.5e5, 2: 3.5e6}[v]) / A4 for v in (0, 1, 2)}
s_dof = pc.get("fem_s_per_dof_vm", 2.0e-4)
fvc = {str(v): pc.get(f"fv_cells_L{v}", {1: 2e5, 2: 1.6e6, 3: 1.3e7}[v]) / A4 for v in (1, 2, 3)}
scr = pc.get("screen_s_per_candidate_case4", 0.45)
# measured grid sizes of the frozen thermal rule on development geometry (research/o003/e008_dev/probe_dofs.py)
pdp = ROOT / "research/o003/e008_dev/probe_dofs.json"
pd = json.loads(pdp.read_text())["outlines"]["2D_Case_4"]["layouts"]
c4_ref = [pd["reconstruction"][f"fem_dofs_L{v}"] for v in (0, 1, 2)]
c4_cand = [max(v[f"fem_dofs_L{k}"] for n, v in pd.items() if n.startswith("cand")) for k in (0, 1, 2)]
c4_fv = [pd["reconstruction"][f"fv_cells_L{v}"] for v in (1, 2, 3)]
# measured FV (thermal_layout) wall time on 2D_Case_4, one Mac core (T0306, research/o003/e008_dev/fv_rate.py)
import math  # noqa: E402
# two runs per level (the second, _rep, repeats the first on the same grid and power); the model takes the mean wall
fv_runs = {v: [json.loads((ROOT / f"research/o003/e008_dev/fv_rate_case4_L{v}{s}.json").read_text()) for s in ("", "_rep")]
           for v in (0, 1)}
fv0, fv1 = fv_runs[0][0], fv_runs[1][0]
FV_T = {v: sum(r["wall_s"] for r in fv_runs[v]) / len(fv_runs[v]) for v in (0, 1)}
FV_MAC = FV_T[1] / fv1["n_cells_grid"]
FV_BETA = math.log(FV_T[1] / FV_T[0]) / math.log(fv1["n_cells_grid"] / fv0["n_cells_grid"])
FV_BETAS = [math.log(b["wall_s"] / a["wall_s"]) / math.log(fv1["n_cells_grid"] / fv0["n_cells_grid"])
            for a in fv_runs[0] for b in fv_runs[1]]
fv_cal = json.loads((ROOT / "research/o003/e008_dev/fv_cal_case4.json").read_text())
# Mac -> VM factor of the FV solver, measured on identical level-1 solves (research/o003/e008_dev/fv_vm_factor.py:
# the founder's e2-highmem-16 O007 burst vs this Mac, same code, layout, power, one thread).  Until T0306's second
# attempt the l2_layout factor 1.8 was borrowed; the FV solver (sparse AMG-CG) measured 4.66-5.55.
fvf = json.loads((ROOT / "research/o003/e008_dev/fv_vm_factor.json").read_text())
FV_VM = round(fvf["summary"]["mean"], 2)
FV_VM_HI = round(fvf["summary"]["max"], 2)
FV_LO_BETA = round(min(fvf["summary"]["vm_beta_steps_all"]), 3)  # the VM's smallest measured level step (O007 layouts)
FV_HI_BETA = round(1.0 + 2.0 * (FV_BETA - 1.0), 3)
# cross-check by a second route: the VM's own level-3 time per active cell on the O007 layouts, times Case 4's Mac time
# per active cell over theirs (geometry), scaled to Case 4's level-3 active cells by their own VM level 1 -> 3 exponent
FV_ACT = fv1["n_cells"] / fv1["n_cells_grid"]  # active fraction (exact under bisection: level 0 357,976 x 8 = level 1)
_c4_mac_act = FV_T[1] / fv1["n_cells"]
_c4_l3_act = c4_fv[2] * FV_ACT
FV_DIRECT_H = sorted(
    v["vm_s_per_cell"][2] * (_c4_mac_act / v["mac_s_per_cell_L1"]) * _c4_l3_act
    * (_c4_l3_act / v["vm_cells"][2]) ** (v["vm_beta_L1_L3"] - 1.0) / 3600.0 for v in fvf["layouts"].values())
cm = {
    "source": "P3 (research/o006_p3/solves) and the founder's VM calibration (research/l2_thread_calib/summary.txt); thermal "
              "and screen rates from research/o003/e008_dev/probe_costs.json (Mac, scaled to the VM by the measured EM "
              "speed ratio) where present, else stated placeholders",
    "em_unknowns_per_cell": 4108580 / 140800, "em_level_unknown_factor": {"thk_c": 0.5, "thk_f": 2.0},
    "em_ref_wall_s": 5770.0, "em_ref_unknowns": 4108580, "em_alpha": 1.44,
    "em_level_time_factor": {"thk_c": 1.36, "thk_f": 1.53, "fil_f": 2.10},
    "em_mem_base_GB": 0.8, "em_mem_GB_per_Munknown": 3.65,
    "fake_sizes_per_m2": {"fem": dofs, "fv": fvc}, "fem_s_per_dof": 2.1e-4,
    "fem_s_per_dof_basis": "Mac k(T) solves 1.18e-4 s/DOF (O007 dev3 MMS level 2: 1.58 M DOFs 186 s; gen2_0 smoke level "
                           "1: 0.68 M nodes 80 s) x 1.8 (one Mac core ~ 1.8 VM vCPUs on l2_layout, research/notes/e008-design.md)",
    "em_level_mem_prior": {"lat0.25": 1.6, "lat0.5": 1.6, "thk_c": 1.5, "thk_f": 1.8, "fil_f": 2.6},
    "em_level_mem_prior_basis": "scheduling only, until a solve of the same reference and level has finished (then model "
                                "x 1.1 x the largest measured ratio, Scheduler.learn). Max measured/model peak over 5 "
                                "gen2_0-housing layouts at 0.5 mm cells (Mac smoke rows; table research/o003/e008_dev/em_mem_ratios.json): "
                                "lat0.5 1.10-1.51, thk_c 1.28-1.46, thk_f 1.19-1.77, fil_f 2.32-2.57, rounded up; lat0.25 "
                                "takes the lat0.5 value (not measured). P3's Case 4 0.5 mm solves: 0.86-1.04 of the model. "
                                "--plan uses the model (Case 4 proxies)",
    "em_mem_margin_local": {"default": 1.45, "2D_Case_4": 1.05}, "fem_bytes_per_dof": 4964.065014991321, "fem_memory_margin": 1.15,
    "fem_mem_base_GB": 0.5, "fv_cells_per_m2": fvc, "fv_bytes_per_cell": 1500.0, "fv_s_per_cell": FV_MAC * FV_VM,
    "fv_s_per_cell_mac": FV_MAC, "fv_vm_factor": FV_VM, "fv_ref_cells": fv1["n_cells_grid"], "fv_beta": FV_BETA,
    "fv_sensitivity": {"low": {"beta": FV_LO_BETA, "vm_factor": 1.8}, "high": {"beta": FV_HI_BETA, "vm_factor": FV_VM_HI}},
    "fv_rate_basis": f"measured (T0306, research/o003/e008_dev/fv_rate_case4_L0.json, _L1.json and their _rep "
                     f"repeats, fv_rate.py): thermal_layout on 2D_Case_4 at P_ref (frozen-rule calibration, "
                     f"{fv_cal['calibration']['P_ref_W']:.2f} W per die, research/o003/e008_dev/fv_cal_case4.json), one Mac "
                     f"core, cells = build_layout_grid box cells (the --plan size convention): level 1 "
                     f"{fv1['n_cells_grid']:,} cells {fv_runs[1][0]['wall_s']:.2f} / {fv_runs[1][1]['wall_s']:.2f} s, mean "
                     f"{FV_MAC:.3e} s/cell, {fv1['picard_iters']} Picard iterations, peak RSS {fv1['peak_GB']:.2f} GB = "
                     f"{fv1['peak_GB'] * 1e9 / fv1['n_cells_grid']:.0f} B/cell; level 0 {fv0['n_cells_grid']:,} cells "
                     f"{fv_runs[0][0]['wall_s']:.3f} / {fv_runs[0][1]['wall_s']:.3f} s; wall ~ cells^beta, beta = ln(t1/t0)/ln(n1/n0) "
                     f"= {FV_BETA:.3f} on the means ({min(FV_BETAS):.3f}-{max(FV_BETAS):.3f} over the four run pairs; "
                     f"gen2_0: 1.056); "
                     f"x {FV_VM} Mac -> VM: the FV solver's measured factor, VM wall / Mac wall on identical level-1 "
                     f"solves of the O007 dev layouts (e2-highmem-16 burst 2026-11-04 vs this Mac, same code: "
                     f"{fvf['summary']['min']:.2f} and {fvf['summary']['max']:.2f}, mean; research/o003/e008_dev/"
                     f"fv_vm_factor.json). The VM is E2, E008 runs on N2D: the N2D factor is not measured (inference: not "
                     f"larger, N2D is not slower per thread than E2). The l2_layout factor 1.8 used before does not hold "
                     f"for this sparse solver. Replaces the 1e-4 s/cell placeholder (T0304 finding 2, T0305 finding 6). "
                     f"On the VM the same solver's level steps 1 -> 2 -> 3 scale with exponents "
                     f"{min(fvf['summary']['vm_beta_steps_all']):.3f}-{max(fvf['summary']['vm_beta_steps_all']):.3f} "
                     f"(below Case 4's {FV_BETA:.3f}, which the model keeps). Cross-check by a second route (the VM's "
                     f"level-3 s per active cell on the O007 layouts x Case 4's Mac s per active cell over theirs, at "
                     f"Case 4's {_c4_l3_act / 1e6:.1f} M level-3 active cells): {FV_DIRECT_H[0]:.2f}-{FV_DIRECT_H[1]:.2f} h "
                     f"on E2, against the model's level-3 solve below. Range for phase B: low = the VM's smallest level "
                     f"step (beta {FV_LO_BETA}) and the l2_layout factor 1.8 (a faster N2D, inference); high = twice "
                     f"Case 4's measured excess over linear (beta {FV_HI_BETA}) and the largest measured factor "
                     f"{FV_VM_HI}. Not measured: any level 2-3 solve of Case 4 (29 M and 235 M cells exceed the Mac); "
                     f"FV on N2D",
    "calibration_solves": 4, "screen_mem_GB": 1.5, "cores_per_2thread_solve": 1.5,
    "screen_s_per_candidate": {"default": scr, "2D_Case_4": scr},
    "screen_rate_basis": "0.45 s per candidate = T0288's slow end (3 wires per die, machine under load), used for every "
                         "reference until --plan is re-run on T0263's reconstructions (they cannot be loaded here). Measured "
                         "on the 2D_Case_4 dev spec: 0.022 s generation + 0.013 s L1 = 0.035 s per candidate "
                         "(research/o003/e008_dev/probe_costs.json). Sensitivity of the plan (attempt 5): 0.035 / 0.45 / "
                         "1.0 s per candidate give 44.67 / 45.68 / 47.22 VM-hours (expected) and 58.53 / 59.68 / 61.20 "
                         "(upper); the screens run beside the t = 0 base band solves",
    "plan_expected": [3, 1, 0], "plan_upper": [15, 2, 8],
}
cfg = {
    "fem_rule_path": "research/o007_dev3/frozen_config.json", "fem_rule_file_sha256": H("research/o007_dev3/frozen_config.json"),
    "fem_rule": json.loads((ROOT / "research/o007_dev3/frozen_config.json").read_text()),
    "thermal_fem_path": "src/moduleforge/solvers/thermal_fem.py", "thermal_fem_sha256": H("src/moduleforge/solvers/thermal_fem.py"),
    "freeze": {"rule": "F3: code hashes recorded before any judged reference is loaded; a change voids the run. The twin "
               "construction and the degradation rule are both in twin.py. --verify-freeze recomputes them.",
               "files": {p: H(p) for p in FROZEN}},
    "metric_params": {"floor": 1.0e-3, "tj_limit_K": 2.0},
    "operating_point": {"rule": "O003 scope_in / D0011: equal power per die P_ref, fixed from level-0 scikit-fem solves of the "
                        "reconstructed reference (frozen rule) so that its hottest die rises 60 +/- 1 K above the 65 C "
                        "coolant at uniform h = 5000 W/(m2 K); then used unchanged on every layout and grid of that "
                        "reference, twin included; the same rule for every reference; a customer's own operating point "
                        "is not judged", "coolant_K": 338.15, "h_W_m2K": 5000.0, "target_rise_K": 60.0,
                        "operating_point_tol_K": 1.0, "calibration_tol_K": 0.25, "calibration_max_iters": 10,
                        "power_start_W": 30.0},
    "L_term": {"rule": "D0011, O003 scope_in: one constant per reference, the same for the reference and every candidate, "
               "fixed here before any solve. Customer: the terminal inductance recorded in the vault; else the stated "
               "module stray inductance minus L_sub(reference), floored at 0; public reference or customer with neither: "
               "7 nH (Z. Chen, PhD dissertation, Virginia Tech, 2013, Q3D of the CPES laminated DC terminals; "
               "research/notes/o003-public-benchmarks.md line 61). Reported sensitivity at 0 and 17.5 nH.",
               "public_H": 7.0e-9, "sensitivity_H": [0.0, 1.75e-8]},
    "reference_set_rule": "D0010: customer reference layouts shared under NDA by 2026-11-12 and admissible; otherwise, or if "
                          "none is admissible, the public PowerSynth 2D_Case_2R and 2D_Case_6 with the label 'public "
                          "benchmarks, low power, indicative'. Customer and public references are never mixed in one "
                          "verdict. Excluded customer references are reported by vault id and reason only (D0011).",
    "admissibility_fields": ["reference_id", "kind (customer|public)", "vault_id", "vault_sha256 or reconstruction_sha256",
                             "sic_mosfet_half_bridge (bool)", "separate_antiparallel_diode_dies (bool; true -> excluded)",
                             "nda_permits_cloud_vm (bool, customer only)", "admissible (bool)", "reason", "decided_at",
                             "L_term_H and its source", "on_grid_0p5mm (bool)", "snapping check values"],
    "references": [],
    "search": {"n_candidates": 20000, "n_first": 5000, "shortlist": 16, "batch": 4, "max_checks": 8, "tj_margin": 2.0,
               "chunk": 250, "driver": "moduleforge.optimize.search.run_search / run_control (frozen)"},
    "seeds": {"rule": "sealed seed s (orchestrator); per reference index i (order of config.references): candidate stream "
              "SeedSequence([s, 0, i]), F1(b) control SeedSequence([s, 1, i]), _quick_ok sample SeedSequence([s, 2, i]); "
              "the stream is chunked by the driver (SeedSequence([seed, chunk])) and never depends on the schedule",
              "purposes": {"main": 0, "control": 1, "quick_ok": 2}},
    "quick_ok_draws": 2000,
    "em": {"freq_hz": 2.0e7, "production": "lat0.25", "band_order": ["lat0.25", "lat0.5", "thk_c", "thk_f", "fil_f"],
           "levels": "P3 (research/scripts/o006_p3_em_convergence.py): lat0.25 0.25 mm 10/6/6 E0; lat0.5 0.5 mm 10/6/6 E0; "
                     "thk_c 0.5 mm 5/3/3; thk_f 0.5 mm 20/12/12; fil_f 0.5 mm 10/6/6 E1 (annuli bisected, 12 filaments "
                     "per ring); lat0.125 only for the pre-registration snapping check"},
    "gates": {"w_max": 0.05, "degrade_ratio": 1.25, "node_growth_factor": 8.0, "node_growth_tol": 0.15, "energy_tol": 1.0e-6,
              "picard_tol_K": 1.0e-4, "a3_max": 1.0, "a3_ref_gci_cap_K": 0.25, "a3_floor_K": 1.0e-3, "fv_levels": [1, 2, 3]},
    "compute": {"thread_calib_summary": "research/l2_thread_calib/summary.txt", "cost_model": cm,
                "vm": {"machine": "n2d-custom-8-81920-ext (regular, not Spot, for the registered run)", "vcpus": 8,
                       "ram_GB": 78.0, "memory_fraction": 0.85, "usd_per_h": 0.612, "overhead_h": 0.5,
                       "ext_usd_per_GB_h": 0.0086, "resize_overhead_h": 0.25,
                       "pricing_note": "0.612 $/h at 80 GB is the founder's figure; 0.0086 $/GB-h for N2D extended memory "
                                       "is an assumption to check in the console. N2D extended memory reaches 768 GB per VM "
                                       "(cloud.google.com/compute/docs/instances/creating-instance-with-custom-machine-type)",
                       "earliest_start": "2026-11-16"},
                "plan_references": [
                    {"name": "2D_Case_2R", "area_m2": A4, "on_grid": False, "spot": True,
                     "fem_dofs": {"reference": c4_ref, "candidate": c4_cand}, "fv_cells": c4_fv,
                     "screen_s_per_candidate": scr, "size": "PROXY: 2D_Case_4's 80 x 110 mm lattice until T0263's "
                     "reconstruction exists (not loaded here); --plan is re-run on the reconstruction before registration"},
                    {"name": "2D_Case_6", "area_m2": A4, "on_grid": False, "spot": False,
                     "fem_dofs": {"reference": c4_ref, "candidate": c4_cand}, "fv_cells": c4_fv,
                     "screen_s_per_candidate": scr, "size": "PROXY as above"}]},
    "dev": {"rule": "F3: development geometry only (generator housings and 2D_Case_4), never a judged reference",
            "dev_seed": 20261110, "geometries": ["gen2_0", "case4"],
            "case4": {"keepout_nets": {"SIG_HS_G": "GATE_HS", "SIG_HS_KS": "KELVIN_HS", "SIG_LS_G": "GATE_LS",
                                       "SIG_LS_KS": "KELVIN_LS"},
                      "extra_pads_mm": {"gate": [0.5, 4.8, 1.5, 5.8], "kelvin": [2.5, 4.8, 3.5, 5.8]},
                      "max_signal_wire_m": 0.025,
                      "thermal_material_substitutions": {"none (M5)": "SAC305"},
                      "thermal_material_reason": "dev only: research/scripts/o006_case4_layout.py gives the PowerSynth "
                          "stack a 1 um solder placeholder named 'none (M5)' (k 58 W/(m K)) that has no k(T) law in "
                          "geometry/stack.py K_LAWS; the SAC305 law is used (same k, 1 um: about 0.5 % of the AlN layer's "
                          "thermal resistance). The fingerprint changes with it.",
                      "rule_overrides": {"min_wire_pitch": "default", "wire_pitch_diameters": "default",
                                         "max_wire_length": 0.018},
                      "rule_overrides_reason": "dev only (T0262 finding): under raw measure_rules the frozen twin of "
                          "2D_Case_4 is not DRC-clean (TwinError: twin power wires 16.15x mm > measured longest 16.151 "
                          "mm; measured min_wire_pitch 10 mm is the pitch between different dies, as the derivative "
                          "docstring notes). Pitch at the DesignRules defaults and 18 mm wire length as in "
                          "tests/unit/generate/test_twin.py. For judged references this is a founder decision.",
                      "assumptions": "gate / Kelvin pads and the 25 mm signal-wire limit are assumed (the PowerSynth "
                                     "files give none; as tests/unit/generate/test_twin.py); other rules measure_rules"},
            "smoke": {"em_map": {"lat0.25": "lat0.5"}, "fem_overrides": {"h0_m": 0.016, "near_margin_m": 0.001, "dz_max_m": 0.004,
                                                                    "edge_grading": {"first_offset_m": 0.002, "ratio": 2.5,
                                                                                     "max_offset_m": 0.004,
                                                                                     "min_gap_fraction": 0.5}},
                      "fem_overrides_source": "E009 smoke_fem_overrides (registered); level 2 <= 0.97 M DOFs on the probed "
                                              "dev layouts. The earlier draft's h0/dz_max doubling kept the edge grading and "
                                              "gave ~5 M DOFs (~30 GB) at its level 2 (probe_dofs, T0262 attempt 4)",
                      "search": {"n_candidates": 64, "n_first": 16, "chunk": 32}, "quick_ok_draws": 100,
                      "meaning": "local smoke rows (16 GB Mac): the 0.25 mm production slot is solved at 0.5 mm (lateral "
                                 "term of e_R zero), thermal levels 0-2 of E009's registered smoke rule (its level 2 is "
                                 "about the size of the frozen level 1; packet: 'thermal levels 0-1'), 64 candidates, "
                                 "one thread per solve. Not evidence; does not decide the band check or the twin gates."}},
    "reporting": {
        "rule_strictness": "T0280: per reference each measured spacing class beside the reference's smallest DC-link gap; "
                           "a class more than 2x stricter is flagged (narrows the search). Reported, not gated.",
        "quick_ok": "T0295: DRC-clean samples _quick_ok rejects over a fixed sealed sample (quick_ok_draws, L0 only), "
                    "flagged when non-zero. Reported, not gated.",
        "midpoint": "T0297 note 2: whether the twin's midpoint-of-needs rule decided a merged-band split, and which.",
        "twin_copper": "T0299: symmetric difference twin W vs snapped reconstruction per net, mm2 and fraction of the "
                       "net's area, with the twin mode. Scalar areas only (F5). Reported, not gated.",
        "degradation": "T0296: per reference whether the walk ran (rec['walk']) and its steps; D's L_sub ratio gated.",
        "near_ties": "T0292: the near-tie union count is reported; --plan gives the cost at its expected and upper end."},
    "twin_limitations": [
        "rectangular merged bands are split by the midpoint-of-needs convention; the copper does not fix the boundary (T0297)",
        "a column that fills the gap beside the narrower slot leaves no step, so the tie rule decides the split (T0300)",
        "a neck from below or above that covers a slot's probe u enters the band's v-interval and counts as band copper, "
        "so the split can be wrong end to end (T0302 finding 0)",
        "copper is assumed axis-parallel (non-rectilinear copper is staircased by the snapping rule first)"],
    "failure_consequences": {
        "F1a_twin_gate_fails": "objective: the reference is excluded and reported; INVALID only if no reference remains",
        "F1b_control_fails": "objective: experimental failure, E008 INVALID",
        "D_misses_1p25_in_L_sub": "implied by the objective: D does not meet F1(b)'s definition, so (b) cannot be "
                                  "completed for that reference and F1's response applies: INVALID. Open: exclusion of "
                                  "only that reference (see founder decisions)",
        "DegradeError": "implied: no D exists, (b) cannot run, INVALID by the same reading; detected before any VM solve "
                        "(fail fast). Open: see founder decisions",
        "F1c_band_too_wide": "objective: INVALID", "F6a_to_d": "objective: INVALID",
        "F6e_spot_check_fails": "objective: no verdict (INVALID), diagnosis and a founder decision"},
    "founder_decisions_before_registration": [
        "D below 1.25 L_sub(twin) at the conservative end of its band, or DegradeError: INVALID for E008 (implied reading) "
        "or exclusion of that reference only (the objective gives exclusion only for the twin gates)",
        "the band check (e_R on >= 4 twin-vs-random pairs) and Case 4's twin gates come from the full-fidelity dev run on "
        "the VM (research/o003/e008_dev/burst_dev.sh); the local rows are smoke rows and do not decide either",
        "before registration the same full-fidelity dev run (burst_dev.sh: gen2_0 with the full frozen search, 2D_Case_4 "
        "twin gates) answers reviews T0304 (findings 0, 1) and T0305 (finding 4): Run.drive, assemble_rows and evaluate "
        "run once end to end on real solvers, and meta.thermal_report gives, for every dev layout at the frozen rule, "
        "F6(a)'s node growth per level step, the per-die GCI with the count of gci_capped returning +inf, and whether the "
        "conservative +2 K test is attainable (own interval width <= 2 K). If it is not attainable on the twin or most "
        "candidates, A1 may be unreachable by construction: the founder decides before registration. No local "
        "full-fidelity run is needed (T0306)",
        "if any dev e_R exceeds 0.02, or either Case 4 twin gate fails: the founder decides (objective notes)",
        "the snapping check (0.125 mm, ~61 GB and ~12 h per solve at Case 4 size, two solves per off-grid reference)",
        "config.references: the D0010 set with admissibility per reference, L_term, the reconstruction loader and hashes "
        "(T0263); --plan re-run on the real reconstructions (sizes here are Case 4 proxies)",
        "twin-copper areas of a customer reference in the rows (F5: scalar areas, no geometry) or vault-only",
        "T0262 finding: on 2D_Case_4 the frozen twin fails the DRC under the reference's own measured rules (power-wire "
        "length a few um over the measured longest wire; measure_rules' min_wire_pitch is the pitch between different "
        "dies). Which rule values apply to judged references (measured, with a stated tolerance, or the defaults for "
        "wire pitch) must be decided before registration, since a TwinError stops the reference",
        "row contract interpretations 1-9 (research/o003/e008_row_contract.md section 5)",
        "budget: cpu_hours 320 holds for E008 only as process CPU time (240-314 h); as billed vCPU-hours E008 needs "
        "366-477 and all VM work about 650-770 (cost_estimate.statement): which reading applies, or raise it",
        "F6(e) at Case 4 size: the finite-volume level-3 grid has 235 M cells (~350 GB at E009's 1,500 B/cell); it fits "
        "only on the same 8-vCPU VM resized to ~416 GB of N2D extended memory (N2D allows 768 GB). This is above the "
        "'~150+ GB' the founder's constraint (2026-11-09) names. If the account cannot exceed ~150 GB, F6(e) cannot run "
        "on a Case-4-sized AlN reference and E008 gives no verdict (F6e: INVALID). Choose: confirm ~416 GB is allowed; "
        "or a smaller AlN spot-check reference (FV level 3 <= ~85 M cells, i.e. 0.85 x 150 GB at 1,500 B/cell) once "
        "T0263's reconstructions exist (the objective requires one reference per non-default stack type, not a "
        "particular one); or a memory-lean FV level 3 under a new spec",
        "EM memory model (T0262 attempt 5, fact): on 5 gen2_0-housing layouts at 0.5 mm cells the measured peaks were "
        "1.1-2.6x the per-unknown model that --plan uses (fil_f 2.3-2.6x, thk_f up to 1.8x); on P3's Case 4 they were "
        "0.86-1.04x. The runner schedules with per-level priors until a solve of the same reference and level is "
        "measured, then by the measured ratio (Scheduler.learn), so packing is safe; but --plan's concurrency (four "
        "0.25 mm solves at once) holds only if the public references behave like Case 4. Re-run --plan on T0263's "
        "reconstructions with their measured 0.5 mm peaks before registration",
        "_quick_ok report (T0295) power: on 2D_Case_4 the smoke sample (100 draws) gave 0 DRC-clean samples; the "
        "registered 2,000 draws gave 33, none rejected, so the false-rejection rate is <= 8.7 % (exact one-sided 95 % "
        "bound, now reported by the runner; research/o003/e008_dev/case4_prep.log). Whether quick_ok_draws should instead "
        "fix the number of DRC-clean samples (e.g. 100 clean -> bound 3 %) is a design choice for registration (reported, "
        "not gated, either way)",
        "2D_Case_4 fail-fast facts (dev, L0/L1 only, attempt 5): twin mode fit+signal_feet with zero copper symmetric "
        "difference on DC+, DC- and PHASE, L1(W)/L1(reconstruction) = 1.0017; degrade() raises DegradeError (L1 ratio "
        "1.232 < 1.388 after the walk reached a local maximum). Case 4 is a PowerSynth layout like both public "
        "references, so a DegradeError on them is a live risk: under the implied reading E008 would be INVALID before "
        "any VM spend. The DegradeError consequence above should be decided with this in view",
        "E009-registered smoke thermal rule for local smoke rows; the earlier smoke rule did not fit the Mac "
        "(research/notes/e008-design.md section 3)"],
    "cost_estimate": {"filled_by": "uv run python experiments/runners/e008_run.py --plan (see research/notes/e008-design.md)"},
}
spec = {
    "id": "E008", "objective": "O003", "status": "draft",
    "title": "Module-level loop-inductance headroom of the D0010 references inside their own housing at <= +2 K Tj "
             "(frozen D0008 search, l2_layout 0.25 mm band, scikit-fem C004 thermal reference; O003 A1/K1, F1-F6)",
    "runner": "uv run python experiments/runners/e008_run.py", "config": cfg, "sealed_seed": True,
    "metrics": [
        {"name": "headroom_min_lo", "unit": "", "description": "A1. min over counted references of h_lo = a (1 - r (1 + w)), "
         "twin rule first, conservative interval Tj test against the twin (mfos.metrics.headroom_min_lo). The band is inside "
         "the value (interval form; objective uncertainty: point), level 0.0, no CI."},
        {"name": "headroom_max_hi_ind", "unit": "", "description": "K1. max over counted references of h_hi from the "
         "inductance-only best, levelling first, twin rule, near ties (mfos.metrics.headroom_max_hi_ind). May be +inf."},
        *[{"name": f"{fn}_{t}", "unit": "", "description": f"secondary: {fn} with {d}"} for fn in ("headroom_min_lo", "headroom_max_hi_ind")
          for t, d in (("Lterm0", "L_term = 0"), ("Lterm17p5", "L_term = 17.5 nH"), ("recon", "the reconstruction as comparator (row contract item 9)"))],
        {"name": "null_twin_as_best_h_lo", "unit": "", "description": "declared A1 null: L_sub_null_H in place of L_sub_H; -a s_ref <= 0 by construction"},
        {"name": "l1_only_null_h_lo", "unit": "", "description": "reported null (F1, not gated): min over counted references "
         "of h_lo of the L1-only search (top 8 by L1 checked in L1 order, batch-and-stop, the first candidate meeting the "
         "conservative test), against the twin, twin rule first; w from its own band if F3 solved one, else the A1 best's "
         "w (stated per reference). Expected at or below headroom_min_lo"},
        {"name": "n_counted_references", "unit": "", "description": "admissible references passing both twin gates"},
        {"name": "stack_type_a3", "unit": "", "description": "F6(e): max over the non-default stack types of max_gci_consistency "
         "on that type's spot-check reference"}],
    "sanity_checks": [
        {"name": "freeze_hashes", "description": "F3: every freeze file sha256 equals config.freeze; checked before any reference is loaded"},
        {"name": "grid_rule_frozen", "description": "F6(b): the GridRule file sha256 0226b770...0e9a and key for key equal config.fem_rule"},
        {"name": "thermal_fem_sha256", "description": "F6(b): thermal_fem.py has the bytes EV-O007-01 evaluated (a216d5fe...)"},
        {"name": "metric_params_exact", "description": "floor = 1e-3 K and tj_limit_K = 2.0 K exactly (T0283/T0284)"},
        {"name": "fail_fast_twin_and_D", "description": "W and D of every reference built (L1 only) before the first l2_layout solve; TwinError / DegradeError stop the run with the reason"},
        {"name": "F1b_D_definition", "description": "per reference: L_sub(D)/L_sub(W) (1 - 2 e_R(D, W)) >= 1.25 from the stored band solves, before K1 is read"},
        {"name": "F1a1_F1a2_twin_gates", "description": "per reference (exclusion, not INVALID): inductance and thermal twin gates as headroom_per_reference computes them"},
        {"name": "at_least_one_counted_reference", "description": "F1(a): E008 INVALID if no reference remains"},
        {"name": "F1b_control", "description": "h_ctrl >= h_plant - w_ctrl per reference (new sealed seed, same budget, inductance only)"},
        {"name": "F1c_band_width", "description": "w <= 0.05 for the A1 best and w_ind for the inductance-only best, every reference"},
        {"name": "F6a_own_three_grids", "description": "per thermal solve: fingerprint of the layout, node counts x8 +/- 15 % per level, every GCI recomputed by gci_capped"},
        {"name": "F6c_energy_balance", "description": "|Q_out/Q_in - 1| <= 1e-6 on every thermal solve: scikit-fem levels 0-2, the calibration and the F6(e) finite-volume spot-check solves (T0305 finding 5)"},
        {"name": "F6c_picard", "description": "last Picard max|dT| <= 1e-4 K on every thermal solve"},
        {"name": "F6d_operating_point", "description": "the reconstruction's level-0 hottest-die rise at P_ref within 60 +/- 1 K before any candidate solve"},
        {"name": "F6e_stack_type_spot_check", "description": "max_gci_consistency (scikit-fem L0-2 vs thermal_fv L1-3, cap 0.25 K, floor 1e-3 K) <= 1 on every die of one reference per non-default stack type (AlN). Stack type = the substrate layers, the die attach and the die, each by name, material, thickness and k (T0305 finding 0). One check F6e_stack_type_spot_check:<type> per non-default type, every one gated; this declared check passes only if all of them pass"},
        {"name": "driver_s_ref_matches_rows", "description": "per reference: the s_ref the frozen driver was given (its near-tie window and w) equals snapping_bias of the reference row, so the band solves the metric needs exist (T0304 finding 3)"},
        {"name": "recompute_agrees", "description": "runner metrics equal mfos.metrics and research/o003/headroom_metrics.py (rel 1e-9)"}],
    "timeout_min": 6000, "cpu_hours_est": 0.0,
    "evidence_rules": 2,
    "code_under_test": ["src/moduleforge/solvers/l2_layout.py", "src/moduleforge/solvers/l2_core.py",
                        "src/moduleforge/solvers/thermal_fem.py", "src/moduleforge/solvers/thermal_layout.py",
                        "src/moduleforge/solvers/thermal_fv.py", "src/moduleforge/physics/peec.py", *FROZEN,
                        "experiments/runners/e008_run.py"],
    "code_must_match": [{"path": "src/moduleforge/solvers/thermal_fem.py", "objective": "O007"}],
    "requires_passed": ["O007"],
    "rows": {"artifact": "rows.json"},
    "recompute": [],
    "null_baselines": [{"name": "twin_as_best", "kind": "column", "column": "L_sub_null_H", "applies_to": ["headroom_min_lo"]}],
    "dev_rows": "experiments/drafts/E008.dev_rows.json",
}
for fn in ("headroom_min_lo", "headroom_max_hi_ind"):
    spec["recompute"].append({"metric": fn, "fn": fn, "pred": "L_sub_H", "params": {"floor": 1.0e-3, "tj_limit_K": 2.0}})
    for t, extra in (("Lterm0", {"L_term_H": 0.0}), ("Lterm17p5", {"L_term_H": 1.75e-8}), ("recon", {"comparator": "reconstruction"})):
        spec["recompute"].append({"metric": f"{fn}_{t}", "fn": fn, "pred": "L_sub_H",
                                  "params": {"floor": 1.0e-3, "tj_limit_K": 2.0, **extra}})
STATEMENT = (
    "Sizes are 2D_Case_4 proxies for both public references (2D_Case_2R and 2D_Case_6 were not loaded; re-run --plan on "
    "T0263's reconstructions). One 8-vCPU VM at a time (founder, 2026-11-09), two threads per solve, four 0.25 mm solves "
    "at once. Phase A on n2d-custom-8-81920-ext (66 GB usable); phase B = the F6(e) finite-volume level-3 solve "
    "(Case 4 size: 235 M cells, ~350 GB at E009's 1,500 B/cell; nothing else exceeds 31 GB) alone on the same VM resized "
    "to ~416 GB of N2D extended memory (N2D allows 768 GB; the free-trial quota must allow it, founder to check; it is "
    "above the '~150+ GB' named in the founder's constraint: if ~150 GB is the ceiling, F6(e) cannot run at Case 4 size "
    "and E008 gives no verdict, so the date then waits on a founder decision, see founder_decisions_before_registration). "
    "PHASE B TIME (T0306, replaces the unmeasured 1e-4 s/cell): {pb[hours]} h incl. 0.25 h resize, ${pb[usd]} at "
    "{pb[usd_per_h]} $/h, from the measured finite-volume rate (2D_Case_4 level 1 on one Mac core, mean of two runs, {fvr:.3e} s/cell, "
    "wall ~ cells^{fvb:.3f} from its level 0 -> 1 step, x {fvvm} Mac -> VM measured on identical FV solves (E2); "
    "cost_model.fv_rate_basis; a second route from the VM's own level-3 rate gives {fvd0:.2f}-{fvd1:.2f} h for the solve); "
    "range {pl[hours]}-{ph[hours]} h, ${pl[usd]}-${ph[usd]} (low: exponent {fvlb} and x 1.8; high: exponent {fvhb} and "
    "x {fvvmhi}), i.e. E008 "
    "{exl[vm_hours]}-{exh[vm_hours]} VM-hours expected. Before T0306 phase B was 6.77 h, $23.83. "
    "Expected (near ties {ex[near_ties]}, {ex[thermal_batches]} thermal batch): {ex[vm_hours]} VM-hours, ${ex[usd]}, "
    "{ex[billed_vcpu_hours]} billed vCPU-hours, {ex[process_cpu_hours]} process CPU-hours, end {ex[end_date_if_start]} "
    "if started 2026-11-16. Upper (15 near ties, 2 batches, 8 null checks): {up[vm_hours]} VM-hours, ${up[usd]}, "
    "{up[billed_vcpu_hours]} billed vCPU-hours, {up[process_cpu_hours]} process CPU-hours, end {up[end_date_if_start]}. "
    "Before registration, on the same VM: the full-fidelity dev run (~10-12 VM-hours, Spot allowed, ~$7) and the "
    "snapping check for each off-grid reference (two 0.125 mm solves, ~61 GB and ~12 h each; two at once on ~144 GB, "
    "~24 h, ~$28). DATE: 2026-11-24 is reachable (E008 ends 2026-11-17/18 if it starts 2026-11-16, six days of slack) "
    "provided the reconstructions, the snapping checks and registration are done by 2026-11-16 and phase B's ~416 GB is "
    "allowed (or the spot check moves to a smaller AlN reference); the earliest E008 end is about 2026-11-17. If neither "
    "holds, 2026-11-24 is unreachable and no earliest date exists until the founder decides F6(e). BUDGET: USD fits (E008 ${ex[usd]}-${up[usd]}, all VM work ~${allu_lo:.0f}-{allu_hi:.0f} (the earlier ~$95-110 less the phase-B change of ${dpb:.2f}), budget.usd 250; the "
    "free-trial credit balance is not in the repository). CPU-HOURS IS THE ITEM THAT BREAKS: budget.cpu_hours 320 "
    "holds for E008 alone only as process CPU time ({ex[process_cpu_hours]}-{up[process_cpu_hours]} h, the upper end "
    "{cpu_room:.0f} % below 320); counted as billed vCPU-hours (8 x VM-hours, what the cap and the bill measure) E008 needs "
    "{ex[billed_vcpu_hours]}-{up[billed_vcpu_hours]} and, with the dev run (8 x 10-12 VM-hours) and the snapping checks "
    "(8 x 24 h), about {allc_lo:.0f}-{allc_hi:.0f}. "
    "Founder decision: which reading of cpu_hours applies, or raise it.")
plan = ROOT / "research/o003/e008_dev/plan.json"
if plan.exists():
    p = json.loads(plan.read_text())
    cfg["cost_estimate"] = {"filled_by": "e008_run.py --plan", **p}
    spec["cpu_hours_est"] = round(p["cases"]["expected"]["billed_vcpu_hours"], 1)
    up, ex = p["cases"]["upper"], p["cases"]["expected"]
    cfg["cost_estimate"]["peak_memory_per_reference_GB"] = ex["peak_GB_per_reference"]
if plan.exists() and "phase_b_sensitivity" not in ex:  # plan.json predates T0306's FV model: run --plan, then this again
    cfg["cost_estimate"]["statement"] = "STALE: re-run e008_run.py --plan and then make_spec.py"
    print("plan.json has no phase-B sensitivity (pre-T0306): run e008_run.py --plan, then make_spec.py again")
elif plan.exists():
    pb = ex["phase_b_big_memory_jobs"][0]
    dpb = 23.83 - pb["usd"]  # phase B before T0306: 6.77 h, $23.83 (git 62e8fbe2, cost_estimate)
    allc_lo, allc_hi = ex["billed_vcpu_hours"] + 8 * 10 + 8 * 24, up["billed_vcpu_hours"] + 8 * 12 + 8 * 24
    cfg["cost_estimate"]["statement"] = STATEMENT.format(
        ex=ex, up=up, pb=pb, pl=pb["sensitivity"]["low"], ph=pb["sensitivity"]["high"], fvr=FV_MAC, fvb=FV_BETA,
        fvhb=FV_HI_BETA, fvvm=FV_VM, fvvmhi=FV_VM_HI, fvlb=FV_LO_BETA, fvd0=FV_DIRECT_H[0], fvd1=FV_DIRECT_H[1], exl=ex["phase_b_sensitivity"]["low"], exh=ex["phase_b_sensitivity"]["high"],
        allu_lo=95 - dpb, allu_hi=110 - dpb, dpb=dpb, allc_lo=allc_lo, allc_hi=allc_hi,
        cpu_room=100 * (1 - up["process_cpu_hours"] / 320))
    fd = cfg["founder_decisions_before_registration"]
    k = next(i for i, x in enumerate(fd) if x.startswith("budget: cpu_hours 320"))
    fd[k] = (f"budget: cpu_hours 320 holds for E008 only as process CPU time ({ex['process_cpu_hours']}-"
             f"{up['process_cpu_hours']} h); as billed vCPU-hours E008 needs {ex['billed_vcpu_hours']}-"
             f"{up['billed_vcpu_hours']} (phase B at the measured FV rate, T0306) and all VM work about {allc_lo:.0f}-"
             f"{allc_hi:.0f} (cost_estimate.statement): which reading applies, or raise it")
(ROOT / "experiments/drafts/E008.yaml").write_text(yaml.safe_dump(spec, sort_keys=False, width=120, allow_unicode=False))
print("wrote experiments/drafts/E008.yaml")
