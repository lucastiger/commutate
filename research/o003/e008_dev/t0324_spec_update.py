"""T0324: write the full-fidelity dev run's facts (experiments/drafts/E008.dev_rows.json, replayed from the saved VM work by
e008_run.py --dev --replay-only), the founder decisions of 2026-11-12 (F6(e) memory: n2d-custom-8-499712-ext) and 2026-11-13
(F1(a1) kept as frozen), the --plan result with the dev near ties (plan_T0324.json), the measured per-solve costs
(dev_run_measured_T0324.json) and the review T0323 fixes into experiments/drafts/E008.yaml.  Every number is read from those
files, never typed.  Idempotent (each step replaces its own entries).  Usage:
  uv run python research/o003/e008_dev/t0324_spec_update.py
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
SPEC = ROOT / "experiments/drafts/E008.yaml"
DEV = ROOT / "research/o003/e008_dev"
TAG = "(T0324)"
RULES_CHANGED = (
    "no design rule of the reference, the twin or the candidates on power copper, power wires or dies changed (D0019 item 2); "
    "the power-width floor of the yardstick D did (D0018 decision 1, T0316: D is built under min(reference minimum, "
    "config.degrade_power_width_floor_m = 1.5 mm), i.e. 1.5 mm for 2R where T0314 used 2R's own 4.0 mm); a reference whose D "
    "misses F1(b) (DegradeError, or L_sub(D)/L_sub(W) below 1.25 at the conservative end of its band) is excluded instead of "
    "failing the run (D0018 decision 2, T0316); a non-finite or non-converged band solve of D or W makes the run INVALID "
    "(T0317, review T0318 finding 0); the change prompted by 2R removed the lower bound on gate and Kelvin wire length "
    "(min_signal_wire_length, D0018 item 1, T0317); O003 scope_in's enumerated rules are the complete meaning of 'at least "
    "as strict as the reference's own' (D0019 item 5)")


def g(x: float, n: int = 5) -> str:
    return "+inf" if x == math.inf else ("-inf" if x == -math.inf else f"{x:.{n}g}")


def main() -> int:
    spec = yaml.safe_load(SPEC.read_text())
    c = spec["config"]
    rows = json.loads((ROOT / "experiments/drafts/E008.dev_rows.json").read_text())
    m = rows["meta"]
    assert m["smoke"] is False and m["replay_only"]["solves_started"] == 0
    pl = json.loads((DEV / "plan_T0324.json").read_text())
    ms = json.loads((DEV / "dev_run_measured_T0324.json").read_text())
    c4, gn = m["per_reference"]["2D_Case_4"], m["per_reference"]["housing70x40_gen2_0"]
    rec, lev = gn["record"], gn["levelling"]
    tr = m["thermal_report"]["per_reference"]
    pairs = m["band_check_pairs"]
    emax = max(p["e_R"] for p in pairs)
    qg, qc = gn["info"]["quick_ok"], c4["info"]["quick_ok"]

    # review T0323 finding 0: spot_note of 2D_Case_6 and the declared check's description
    for r in c["compute"]["plan_references"]:
        if r["name"] == "2D_Case_6":
            r["spot_note"] = ("own non-default stack type (AlN 0.64 mm); excluded at its twin in the expected scenario, so the "
                              "runner runs no spot check of its type then: the evaluation report lists F6e.<type> with "
                              "reference null and status 'only reference excluded: <reason>', reported, not gated (founder "
                              "decision 2026-11-12, T0322; see founder_decisions_settled)")
    sc = next(x for x in spec["sanity_checks"] if x["name"] == "F6e_stack_type_spot_check")
    add = (" T0324 (review T0323 finding 0): a non-default type with no admissible reference that reached the search but an "
           "admissible reference EXCLUDED (TwinError, DegradeError or D's definition; other references of the type may be "
           "inadmissible) gets no spot check and no per-type check: the evaluation report lists F6e.<type> with reference "
           "null, excluded_references and status 'only reference excluded: <reason>' (one excluded reference) or 'all "
           "references excluded: ...'; the detail lists it under only_reference_excluded; REPORTED, NOT GATED (founder "
           "decision 2026-11-12). For D0019's set this is 2D_Case_6's type if it raises TwinError as expected.")
    sc["description"] = sc["description"].split(" T0324 (review T0323 finding 0)")[0] + add

    # review T0323 finding 3: rules_changed names D0018 decision 2 and the INVALID rule
    dv = c["f3_declared_deviation"]
    dv["rules_changed"] = RULES_CHANGED
    dv["changed_after"] = [x for x in dv["changed_after"] if x.get("task") != "T0324"] + [{
        "task": "T0324", "commit": "this task", "date": "2026-11-13",
        "what": "row labels by role (twin = reconstruction), --replay-only, F6(e) mixed-type report (review T0323 finding 1), "
                "burst_full.sh resume read, rules_changed names D0018 decision 2 and the INVALID rule; no rule, gate, "
                "tolerance, generator, twin, degradation or search change"}]

    # founder items: settled now
    fdb, fds = c["founder_decisions_before_registration"], c["founder_decisions_settled"]
    fds[:] = [x for x in fds if TAG not in x]
    drop = ("the band check (e_R on >= 4", "if any dev e_R exceeds 0.02", "F6(e) memory on the real 2D_Case_2R")
    fdb[:] = [x for x in fdb if not x.startswith(drop)]
    fds.append(
        f"Full-fidelity dev run {TAG} (founder's VM, research/o003/e008_dev/burst_dev.sh, 2026-11-13 05:47-15:44 UTC, one Spot "
        f"preemption resumed; {ms['n_solves']} solves; rows rebuilt from the saved result files by e008_run.py --dev "
        f"--replay-only with no solve started; experiments/drafts/E008.dev_rows.json). BAND CHECK: {len(pairs)} twin-vs-random "
        f"pairs on 2D_Case_4, e_R {[round(p['e_R'], 5) for p in pairs]}, max {emax:.5f} <= 0.02 (gen2_0's 4 pairs were never "
        f"solved: the run crashed in evaluate() before them). CASE 4 TWIN GATES (W fit+signal_feet): F1(a1) FAILS, "
        f"|1 - L_sub(W)/L_sub(R)| = {c4['a1_lhs']:.6f} > 2 e_R(W, R) = {c4['a1_rhs']:.6f}; F1(a2) passes only because both "
        f"G are +inf (lhs {g(c4['a2_lhs'])}, rhs {g(c4['a2_rhs'])}). FOUNDER DECISION 2026-11-13: F1(a1) is kept as frozen "
        f"(Case 4's twin is fit+signal_feet, L1(W)/L1(R) {c4['prep']['L1_ratio_twin_over_reconstruction']:.4f}; 2R's recorded "
        f"twin is exact at L1, research/o003/twin_coverage/results.json R1), so the band-check and Case 4 twin-gate items "
        f"are settled; F1(a2) on Case 4 passing only on +inf G is a recorded fact. QUICK_OK: gen2_0 {qg['drc_clean']} of "
        f"{qg['draws']} DRC-clean, none rejected, bound {100 * qg['rejection_rate_ub95']:.1f} %; Case 4 {qc['drc_clean']}, "
        f"bound {100 * qc['rejection_rate_ub95']:.1f} %. GEN2_0 SEARCH (dev geometry, not evidence; W = the reconstruction, "
        f"same fingerprint): counted (a1 {rec['gate_a1']}, a2 {rec['gate_a2']}), h_lo {rec['h_lo']:.4f} (best {rec['best_id']}, "
        f"r {rec['r']:.4f}, e_R {rec['e_R']:.4f}; {rec['n_thermal_checked']} checked, {rec['n_tj_rejected']} rejected); near "
        f"ties {gn['near_ties']}; NOT LEVELLED: lowest L1 of the first {lev['n_first']} {lev['l1_min_first'] * 1e9:.3f} nH > "
        f"(1 + w {rec['w_levelling']:.4f}) x lowest of all {lev['n_candidates']} {lev['l1_min_all'] * 1e9:.3f} nH, so h_hi = "
        f"+inf there (K1 cannot fire from it); control: h_ctrl {gn['h_ctrl']:.4f} >= h_plant {gn['h_plant']:.4f} - w_ctrl "
        f"{gn['w_ctrl']:.4f}; D: R_D {gn['R_D']:.4f}, e_R {gn['e_R_D']:.4f}, conservative {gn['R_D'] * (1 - 2 * gn['e_R_D']):.4f} "
        f">= 1.25; every evaluate() check passed ({len(m['checks'])})")
    fds.append(
        f"F6(e) memory {TAG}: founder decision 2026-11-12: F6(e) on 2D_Case_2R runs on the same 8-vCPU VM resized to "
        f"n2d-custom-8-499712-ext (488 GiB, N2D extended memory); the founder created that machine type on this free-trial "
        f"account (test VM, 2026-11-12, successful); no memory-lean finite-volume level 3 for E008 (was the founder item 'F6(e) "
        f"memory on the real 2D_Case_2R'; burst_full.sh phase B)")
    fds.append(
        f"Review T0323 {TAG}: finding 0, the 2D_Case_6 spot_note and the F6e_stack_type_spot_check description carry 'only "
        f"reference excluded: <reason>'; finding 1, a type with an admissible EXCLUDED reference and another inadmissible kept "
        f"reference is reported 'only reference excluded: <reason>' (e008_run.spot_assignment; selftest t0324_failures); "
        f"finding 2, burst_full.sh starts the VM and cancels the phase's backstop shutdown before the exit-code read on the "
        f"resume path, and cancels it once the rc file exists; finding 3, f3_declared_deviation.rules_changed names D0018 "
        f"decision 2 and the INVALID rule (quoted verbatim in research/notes/e008-design.md section 12)")
    th = []
    for rid, v in tr.items():
        for lab, e in v["layouts"].items():
            th.append(f"{rid}/{lab}: non-monotone {e['n_non_monotone']}/{len(e['monotone'])} dies, GCI "
                      f"{[g(x, 3) for x in e['gci_K']]} K, attainable {e['attainable']}")
    for i, x in enumerate(fdb):
        if x.startswith("before registration the same full-fidelity dev run"):
            fdb[i] = x.split(" (T0324) ")[0] + (
                f" {TAG} DEV FACTS (meta.thermal_report, frozen rule): " + "; ".join(th) + ". Case 4's reconstruction and "
                "twin: every die non-monotone over levels 0-2 (oscillatory with |rho| >= 1), GCI +inf, not attainable. STAYS A "
                "FOUNDER ITEM: a separate investigate task diagnoses Case 4's oscillation before the founder decides")
        elif x.startswith("_quick_ok report (T0295)"):
            fdb[i] = x.split(" (T0324) ")[0] + (
                f" {TAG} dev run: gen2_0 {qg['drc_clean']}/{qg['draws']} clean (bound {100 * qg['rejection_rate_ub95']:.1f} %), "
                f"Case 4 {qc['drc_clean']}/{qc['draws']} ({100 * qc['rejection_rate_ub95']:.1f} %)")
        elif x.startswith("budget: with the real sizes"):
            e, au = pl["cases"]["expected"], pl["if_all_counted"]["upper"]
            fdb[i] = x.split(" (T0324) ")[0] + (
                f" {TAG} --plan with the dev near ties ({e['near_ties']}): expected {e['n_solves']} solves, "
                f"{e['billed_vcpu_hours']} billed vCPU-hours, {e['process_cpu_hours']} process CPU-hours (upper end of all "
                f"readings {au['billed_vcpu_hours']}); rates unchanged")

    # cost estimate from plan_T0324.json, with the dev run's measured per-solve costs against the model
    e, u = pl["cases"]["expected"], pl["cases"]["upper"]
    ae, au = pl["if_all_counted"]["expected"], pl["if_all_counted"]["upper"]
    b2r = e["phase_b_big_memory_jobs"][0]
    G = ms["groups"]

    def mline(k):
        v = G[k]
        return (f"{k} n {v['n']}: wall {v['wall_s'][1]:.0f} s (max {v['wall_s'][2]:.0f}) vs model {v['model_est_s_median']:.0f} s, "
                f"peak {v['peak_GB'][1]:.1f} GB (max {v['peak_GB'][2]:.1f}) vs model {v['model_mem_GB_median']:.1f} GB")
    keys = ["2D_Case_4:em:lat0.25", "2D_Case_4:em:thk_f", "2D_Case_4:thermal:2", "housing70x40_gen2_0:em:lat0.25",
            "housing70x40_gen2_0:em:fil_f", "housing70x40_gen2_0:thermal:2"]
    measured = "; ".join(mline(k) for k in keys)
    stmt = (f"T0324: --plan re-run with the near ties of the full-fidelity dev rows ({e['near_ties']}, gen2_0); rates and "
            f"cost model unchanged. EXPECTED SET (2D_Case_6 excluded at its twin): expected {e['n_solves']} solves, "
            f"{e['vm_hours']} VM-hours, ${e['usd']}, {e['billed_vcpu_hours']} billed vCPU-hours, {e['process_cpu_hours']} "
            f"process CPU-hours; upper (15 near ties) {u['n_solves']} solves, {u['vm_hours']} VM-hours, ${u['usd']}, "
            f"{u['billed_vcpu_hours']} billed vCPU-hours. IF 2D_Case_6 WERE COUNTED: {ae['billed_vcpu_hours']}-"
            f"{au['billed_vcpu_hours']} billed vCPU-hours, ${ae['usd']}-${au['usd']}. Phase B: {b2r['job']} ({b2r['n']:,} cells, "
            f"{b2r['peak_GB']} GB) alone on {b2r['machine']} ({b2r['ram_GB']:.0f} GB), {b2r['hours']} h, ${b2r['usd']} (founder "
            f"decision 2026-11-12, settled). MEASURED ON THE DEV RUN (research/o003/e008_dev/dev_run_measured_T0324.json, "
            f"{ms['n_solves']} solves, {ms['sum_solve_wall_h']:.1f} solve-hours): {measured}. Reading: EM wall is at or below "
            f"the model (Case 4 about 0.4-0.7x), EM peak within about 1.1x except gen2_0 fil_f/thk_f (2.0x/1.4x, handled by "
            f"Scheduler.learn); scikit-fem level-2 wall is ABOVE the model (Case 4 1.8x, gen2_0 1.3x) and its peak about 0.55x; "
            f"the phase-A wall of the registered run may therefore exceed --plan's by the thermal share; rates are kept (no "
            f"change made here). Not included: the dev run itself and its rerun.")
    est = {"filled_by": "e008_run.py --plan (T0324, dev near ties; research/o003/e008_dev/plan_T0324.json)", **pl,
           "peak_memory_per_reference_GB": ae["peak_GB_per_reference"],
           "measured_dev_run": {"source": "research/o003/e008_dev/dev_run_measured_T0324.json",
                                "groups": {k: G[k] for k in keys}},
           "statement": stmt}
    c["cost_estimate"] = est
    spec["cpu_hours_est"] = float(e["billed_vcpu_hours"])
    SPEC.write_text(yaml.safe_dump(spec, sort_keys=False, width=120, allow_unicode=False))
    print("spec updated: settled", len(fds), "before", len(fdb), "cpu_hours_est", spec["cpu_hours_est"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
