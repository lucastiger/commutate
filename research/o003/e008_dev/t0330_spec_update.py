"""T0330: founder decision D0020 (founder session 2026-11-13) into experiments/drafts/E008.yaml.

Item 1: the expected outcome under the frozen Tj rule, stated before registration (an inference: 2D_Case_2R is not solved before
the freeze), from T0325's level-2 VM results (research/o003/e008_dev/tj_osc/vm_level2, copied from the untracked main-checkout
vm_work). Item 2: the reported, not gated, die-average Tj ('virtual junction temperature'). Items 3-4: the band check and the
readings confirmed as implemented. Item 5: every settled item moves from founder_decisions_before_registration to
founder_decisions_settled. Every number is read from files (the dev rows, the VM result files, the spec), never typed.
Idempotent (each step replaces its own entries; a second run changes nothing).  Usage:
  uv run python research/o003/e008_dev/t0330_spec_update.py
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import mfos.metrics as MX
import yaml

ROOT = Path(__file__).resolve().parents[3]
SPEC = ROOT / "experiments/drafts/E008.yaml"
ROWS = ROOT / "experiments/drafts/E008.dev_rows.json"
VM = "research/o003/e008_dev/tj_osc/vm_level2"
TAG = "(T0330, D0020)"
FLOOR = 1e-3


def g(x: float, n: int = 4) -> str:
    return "+inf" if x == math.inf else ("-inf" if x == -math.inf else f"{x:.{n}g}")


def vm_facts() -> dict:
    sol = {}
    for p in sorted((ROOT / VM / "solves").glob("*.json")):
        if p.name.endswith(".job.json"):
            continue
        r = json.loads(p.read_text())
        assert r["status"] == "ok" and r["which"] == "twin", p.name
        sol[(r["variant"], r["level"])] = r
    assert len(sol) == 15, len(sol)
    out = {}
    for v in ("V0", "V1", "V2", "V3", "V4"):
        n = len(sol[(v, 0)]["tj"])
        seq = {k: [[sol[(v, lv)][k][i] for lv in range(3)] for i in range(n)] for k in ("tj", "tj_mean", "tj_centre")}
        rho = [(t[2] - t[1]) / (t[1] - t[0]) for t in seq["tj"]]
        gmax = [MX.gci_capped(*t, floor=FLOOR) for t in seq["tj"]]
        gmean = [MX.gci_capped(*t, floor=FLOOR) for t in seq["tj_mean"]]
        gcen = [MX.gci_capped(*t, floor=FLOOR) for t in seq["tj_centre"]]
        bm = MX.tj_bounds(seq["tj_mean"], floor=FLOOR)
        out[v] = {"rho": rho, "gci_max": gmax, "gci_mean": gmean, "gci_centre": gcen, "n_inf_max": sum(map(math.isinf, gmax)),
                  "self_width_mean": bm[2] - bm[3], "max_minus_mean_l2": [t[2] - m[2] for t, m in
                                                                          zip(seq["tj"], seq["tj_mean"], strict=True)],
                  "tj_l2": [t[2] for t in seq["tj"]], "nodes": [sol[(v, lv)]["nodes"] for lv in range(3)],
                  "mean_le_max": all(m <= t for k in range(n) for t, m in zip(seq["tj"][k], seq["tj_mean"][k], strict=True))}
    return {"v": out, "sol": sol}


def main() -> int:
    spec = yaml.safe_load(SPEC.read_text())
    c = spec["config"]
    rows = json.loads(ROWS.read_text())
    m = rows["meta"]
    assert m["smoke"] is False and m["replay_only"]["solves_started"] == 0
    F = vm_facts()
    V = F["v"]
    # sanity first: V0 is the dev run's 2D_Case_4 twin (same physics hashes); its three levels equal the saved dev rows'
    tw = sorted((r for r in rows["rows"] if r["kind"] == "die" and r["reference_id"] == "2D_Case_4" and
                 r["layout_id"] == "twin"), key=lambda r: r["die_id"])
    rep_err = max(abs(F["sol"][("V0", lv)]["tj"][i] - r[f"Tj_l{lv}_K"]) for i, r in enumerate(tw) for lv in range(3))
    assert rep_err < 1e-6, rep_err
    gn = m["per_reference"]["housing70x40_gen2_0"]
    lev = gn["levelling"]
    above = lev["l1_min_first"] / lev["l1_min_all"] - 1.0
    pairs = m["band_check_pairs"]
    eRs = [p["e_R"] for p in pairs]
    rec = gn["record"]
    qg, qc = gn["info"]["quick_ok"], m["per_reference"]["2D_Case_4"]["info"]["quick_ok"]
    stmt = c["cost_estimate"]["statement"]
    rng = lambda xs, n=3: f"{g(min(xs), n)}-{g(max(xs), n)}"  # noqa: E731
    v4 = V["V4"]
    allv = list(V.values())

    # ---- item 1: expected outcome (inference, before registration)
    c["expected_outcome"] = {
        "decision": "D0020 item 1 (founder session 2026-11-13); written by T0330",
        "status": ("INFERENCE stated before registration: 2D_Case_2R is not solved before the freeze (no twin(), degrade(), "
                   "prepare(), L1, l2_layout, thermal or search run on 2D_Case_2R or 2D_Case_6). It changes no criterion"),
        "tj_rule": ("unchanged: O003's frozen Tj = the maximum nodal value on the die top face, its three-level gci_capped "
                    "(D0013), the conservative test max_i(T_i(C) + GCI_i(C)) - max_j(T_j(W) - GCI_j(W)) <= 2 K; every gated "
                    "criterion (A1, K1, F1-F6) unchanged"),
        "evidence": (f"T0325 (research/diagnoses/T0325.md): 2D_Case_4's twin at the frozen rule, stack variants V0-V4, levels "
                     f"0-2, solved on the founder's VM; results copied by T0330 to {VM}/ (summary.json, summary.txt, run.log, "
                     f"jobs.json, solves/*.json; sha256 list {VM}/MANIFEST.sha256). Sanity: V0 equals the saved dev run's "
                     f"Case 4 twin at levels 0-2 to {rep_err:.1e} K"),
        "case4_facts": (f"[fact, {VM}] on every die of V0-V4 the step of Tj max changes sign between levels (rho from "
                        f"{g(min(x for v in allv for x in v['rho']), 3)} to {g(max(x for v in allv for x in v['rho']), 3)}), "
                        f"so gci_capped is +inf on {sum(v['n_inf_max'] for v in allv)}"
                        f" of {sum(len(v['rho']) for v in allv)} dies; the hottest node moves one level-2 cell off the die centre "
                        f"at level 2; the die-centre node and the die-top mean converge (die-centre GCI "
                        f"{rng([x for v in allv for x in v['gci_centre']])} K, die-top mean GCI "
                        f"{rng([x for v in allv for x in v['gci_mean']])} K). V4 is 2D_Case_2R's recorded stack recipe "
                        f"(= V1 bitwise): Tj max at level 2 {rng(v4['tj_l2'], 6)} K, GCI {[g(x) for x in v4['gci_max']]}. "
                        f"[inference] T0325's H3 (hot-spot migration) is supported"),
        "expected": {
            "2D_Case_2R": ("every twin and candidate die is expected to get gci_capped +inf: same 4 x 6 mm die footprint "
                           "(CPM2-1200-0025B pads) and the same stack recipe as V4, whose four dies all gave +inf on Case 4"),
            "A1": ("expected unreachable on 2R: a +inf GCI on a candidate fails the conservative test, so no candidate is "
                   "eligible, best = twin and h_lo = -a s_ref (= 0 with D0019's s_ref = 0), below 0.20. 2R's F1(a2) is "
                   "expected to pass only because both G are +inf (row contract reading, D0020 item 4)"),
            "K1": (f"may be unavailable: gen2_0's dev search was not levelled (lowest L1 of the first {lev['n_first']:,} "
                   f"{lev['l1_min_first'] * 1e9:.3f} nH, {100 * above:.1f} % above the lowest of all {lev['n_candidates']:,} "
                   f"{lev['l1_min_all'] * 1e9:.3f} nH, window w {100 * lev['w_ind']:.2f} %), so h_hi = +inf there; if 2R's "
                   f"registered search is not levelled either, headroom_max_hi_ind = +inf and K1 (< 0.10) cannot fire"),
            "verdict": "INCONCLUSIVE (expected): A1 not met (expected unreachable on 2R), K1 not fired (expected unavailable)",
            "measured_and_reported": ("2R's inductance-only headroom: headroom_max_hi_ind and its reconstruction "
                                      "(headroom_max_hi_ind_recon) and L_term = 0 (headroom_max_hi_ind_Lterm0) columns, with "
                                      "Lterm17p5; and the die-average analogue (config.reporting.virtual_junction, not gated)"),
            "die_average": (f"[inference from {VM}] the reported-only die-average Tj (virtual junction temperature) is "
                            f"expected to stay assessable on 2R: on Case 4 its GCI is finite on all 20 dies "
                            f"({rng([x for v in allv for x in v['gci_mean']])} K) and its own interval width is "
                            f"{rng([v['self_width_mean'] for v in allv])} K <= 2 K; it decides nothing"),
        },
        "would_contradict": ("a finite gci_capped Tj max on any 2R twin die; a 2R candidate passing the conservative test; "
                             "a levelled 2R search (then K1 is available and the verdict may be PASS or FAIL); 2R excluded "
                             "(then the run is INVALID if no reference remains)"),
    }

    # ---- item 2: reported, not gated
    rp = c["reporting"]
    rp["virtual_junction"] = (
        "D0020 item 2 (T0330): REPORTED, NOT GATED. Die-average Tj ('virtual junction temperature'): per die and scikit-fem "
        "level, T_vj = (1/A) * integral over the die top face of T dA, the area-weighted mean of the FE solution over the "
        "die's top face (the heat-source face, A = the die footprint), as thermal_fem computes ThermalResult.tj_mean: the "
        "facet load vector of the top face (FacetBasis, intorder 4) restricted to the face DOFs and divided by its sum A "
        "(checked against the footprint to 1e-6), dotted with the nodal temperatures (the method of T0325's tj_osc.py). "
        "Die-row columns Tvj_l0_K, Tvj_l1_K, Tvj_l2_K and GCI_vj_K = gci_capped(levels 0-2, floor 1e-3 K); the evaluation "
        "report's 'virtual_junction' section (labelled as not the registered criterion) gives per reference and layout "
        "tj_bounds on T_vj, per thermally checked candidate the conservative-test analogue upper_vj(C) - lower_vj(W) "
        "against 2 K, and the h_lo that A1's formula (mfos.metrics.headroom_per_reference, unchanged) gives when every "
        "die row of that reference carries T_vj in place of Tj max (so F1(a2) is then read on T_vj too). No gated "
        "metric, sanity check, stop rule or F3 order reads it: mfos.metrics reads only Tj_l0..2_K and the frozen search "
        "keeps only its THERMAL_REQUIRED fields. The solve's physics inputs and result-file key are unchanged (the "
        "dev rows were replayed with no solve started); development results solved before T0330 carry null for it. "
        "Selftest: a uniform die gives its own temperature (zero-power solves at two coolant temperatures), mean <= max on "
        "every die (real solves and T0325's level-2 data), and mutation: NaN, +/-100 K, null or absent columns change no "
        "gated metric, check or report value, with a positive control")

    # ---- items 3-5: settled
    fdb = c["founder_decisions_before_registration"]
    keep, moved = [], []
    reason = {
        "full-fidelity dev run": "D0020 item 1 (register with the frozen Tj rule; expected outcome in config.expected_outcome)",
        "twin-copper areas": ("D0020 item 5: no founder decision needed before registration (moot for D0019's public set; "
                              "kept for a future customer set)"),
        "T0262 finding": "D0020 item 4 (judged references: measure_rules less min_signal_wire_length, no override, D0019 item 5)",
        "row contract interpretations": "D0020 item 4 (interpretations 1-9 confirmed as implemented)",
        "budget:": ("D0020 item 4 (the 320 cpu_hours cap is read as billed vCPU-hours; expected 97.0, upper 145.4, from "
                    "cost_estimate)"),
        "F6(e) reading": "D0020 item 4 (an all-inadmissible non-default stack type is reported, not gated, F6(e))",
        "stack-type rounding": "D0020 item 4 (the stack-type rounding rule as implemented)",
        "EM memory model": ("D0020 item 5: a fact with its mitigation (Scheduler.learn), no founder decision needed before "
                            "registration"),
        "_quick_ok report": "D0020 item 4 (quick_ok_draws stays a fixed 2,000 draws)",
        "2D_Case_4 fail-fast": ("D0020 item 1 (its only open part was the full-fidelity dev run, now read; consequence of a "
                                "DegradeError settled by D0018)"),
        "E009-registered smoke": "D0020 item 5: dev-only smoke rule, no founder decision needed before registration",
    }
    for it in fdb:
        if it.startswith("NONE"):
            continue
        hit = next((v for k, v in reason.items() if k in it[:200]), None)
        (moved if hit else keep).append((it, hit))
    assert "97.0 billed vCPU-hours" in stmt and "145.4 billed vCPU-hours" in stmt
    old = c["founder_decisions_settled"]
    fds = [x for x in old if not x.startswith(("D0020 item", "MOVED"))]
    fds += [
        (f"D0020 item 1 {TAG}: E008 is registered with O003's frozen Tj definition (maximum nodal value on the die top face, "
         f"three-level gci_capped, D0013) and every gated criterion unchanged. The expected outcome, stated before "
         f"registration as an INFERENCE (2R not solved before the freeze), is in config.expected_outcome: on 2D_Case_2R "
         f"every twin and candidate die +inf, A1 unreachable (best = twin, h_lo = -a s_ref), K1 possibly unavailable "
         f"(gen2_0 not levelled: {100 * above:.1f} % against w {100 * lev['w_ind']:.2f} %), expected verdict INCONCLUSIVE, "
         f"2R's inductance-only headroom (h_hi_ind, its reconstruction and L_term = 0 columns) measured and reported. "
         f"Evidence: T0325, {VM}/ (copied from the untracked main-checkout vm_work; MANIFEST.sha256)"),
        (f"D0020 item 2 {TAG}: die-average Tj (virtual junction temperature) reported, NOT gated: config.reporting."
         f"virtual_junction; dev results solved before T0330 carry null for it (experiments/drafts/E008.dev_rows.json "
         f"rebuilt by --replay-only, no solve started)"),
        (f"D0020 item 3 {TAG} (I0184 option 1, resolved): the pre-registration band check is 2D_Case_4's {len(pairs)} pairs, "
         f"e_R {[round(x, 5) for x in eRs]}, max {max(eRs):.5f} < 0.02, with gen2_0's search estimate (e_R "
         f"{rec.get('e_R', float('nan')):.4f} for its A1 best, w {rec.get('w', float('nan')):.4f}); gen2_0's 4 random pairs "
         f"were not solved (the VM run crashed first, T0324). RISK to F1(c): both are close to 0.02 (max pair "
         f"{100 * max(eRs) / 0.02:.0f} % of the limit, gen2_0's A1 best {100 * rec.get('e_R', float('nan')) / 0.02:.0f} %)"),
        (f"D0020 item 4 {TAG}, readings confirmed as implemented: row-contract interpretations 1-9 (research/o003/"
         f"e008_row_contract.md section 5; under item 1, 2R's F1(a2) is expected to pass only because both G are +inf); "
         f"judged references use measure_rules less min_signal_wire_length with no override (D0019 item 5); the 320 "
         f"cpu_hours cap is read as billed vCPU-hours (expected 97.0, upper 145.4); an all-inadmissible non-default stack "
         f"type is reported, not gated (F6(e)); the stack-type rounding rule as implemented; quick_ok_draws stays a fixed "
         f"2,000 draws (gen2_0 bound {100 * qg['rejection_rate_ub95']:.1f} %, Case 4 {100 * qc['rejection_rate_ub95']:.1f} %)"),
    ]
    fds += [x for x in old if x.startswith("MOVED")]  # a re-run keeps them, in order
    fds += [f"MOVED {TAG} from founder_decisions_before_registration, settled by {why}: {it}" for it, why in moved]
    c["founder_decisions_settled"] = fds
    c["founder_decisions_before_registration"] = [it for it, _ in keep] or [
        f"NONE {TAG}: after D0020 no item before registration needs the founder; every former item is in "
        f"founder_decisions_settled (D0020 items 1-4, or item 5 where no decision was needed)"]

    # ---- F3 change log
    dv = c["f3_declared_deviation"]
    lst = next(k for k, v in dv.items() if isinstance(v, list) and any(isinstance(e, dict) and e.get("task") == "T0324"
                                                                        for e in v))
    dv[lst] = [e for e in dv[lst] if not (isinstance(e, dict) and e.get("task") == "T0330")] + [{
        "task": "T0330", "commit": "this task", "date": "2026-11-13",
        "what": ("D0020: reported-only die-average Tj (result files carry tj_mean; die-row columns Tvj_l0..2_K, GCI_vj_K; "
                 "evaluation report 'virtual_junction'); Driver.out_path factored out of job() unchanged (the replay found "
                 "every saved result); expected outcome stated; no rule, gate, tolerance, generator, twin, degradation or "
                 "search change")}]
    SPEC.write_text(yaml.safe_dump(spec, sort_keys=False, width=120, allow_unicode=False))
    print("spec updated: settled", len(fds), "moved", len(moved), "before", len(c["founder_decisions_before_registration"]),
          "kept", [it[:60] for it, _ in keep], "V0 reproduction", f"{rep_err:.1e}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
