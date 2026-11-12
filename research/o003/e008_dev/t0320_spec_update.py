"""T0320 (D0019): write config.references, the reconstruction script's freeze hash, config.f3_declared_deviation, the real
reference sizes in config.compute.plan_references, the --plan result (cost_estimate, cpu_hours_est) and the founder-item
updates into experiments/drafts/E008.yaml.  Every hash, fingerprint and size is read from the files or from the runner's
own outputs, never typed:

  research/o003/references/<ref>.json      the frozen T0263 records (fingerprints, L_term, grid flag, keep-outs, source)
  research/o003/e008_dev/check_references.json   e008_run.py --check-references --out (mesh counts, fingerprints)
  research/o003/e008_dev/plan_T0320.json   e008_run.py --plan --plan-out (both scenarios)

Usage (in this order; each step re-reads the spec, so the script is idempotent):
  uv run python research/o003/e008_dev/t0320_spec_update.py refs     # references, freeze, deviation, D0019 citations
  uv run python experiments/runners/e008_run.py --check-references --out research/o003/e008_dev/check_references.json
  uv run python research/o003/e008_dev/t0320_spec_update.py sizes    # plan_references from check_references.json
  uv run python experiments/runners/e008_run.py --plan --plan-out research/o003/e008_dev/plan_T0320.json
  uv run python research/o003/e008_dev/t0320_spec_update.py cost     # cost_estimate, cpu_hours_est, founder items
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
SPEC = ROOT / "experiments/drafts/E008.yaml"
REFS = ("2D_Case_2R", "2D_Case_6")  # D0010 order
SCRIPT = "research/scripts/o003_powersynth_references.py"
DEV = ROOT / "research/o003/e008_dev"


def sha(p: str) -> str:
    return hashlib.sha256((ROOT / p).read_bytes()).hexdigest()


def load() -> dict:
    return yaml.safe_load(SPEC.read_text())


def save(spec: dict) -> None:
    SPEC.write_text(yaml.safe_dump(spec, sort_keys=False, width=120, allow_unicode=False))


def entry(ref: str) -> dict:
    p = f"research/o003/references/{ref}.json"
    r = json.loads((ROOT / p).read_text())
    if r["reconstruction_hash"] != r["snap"]["0.5mm"]["fingerprint"] or r["snap"]["0.5mm"]["n_records"]:
        raise SystemExit(f"{ref}: record inconsistent (reconstruction vs 0.5 mm snap)")
    adm = r["admissibility"]
    src = r["source"]
    return {
        "reference_id": ref, "kind": r["kind"], "label": r["label"], "vault_id": None,
        "reconstruction_sha256": r["reconstruction_hash"],
        "reconstruction_sha256_meaning": "Layout.fingerprint() of the reconstruction the frozen script's snapped() returns "
                                         "(T0263); the loader checks it before anything else (mismatch: refused, run void)",
        "reconstruction_script": SCRIPT, "reconstruction_record": p, "reconstruction_record_sha256": sha(p),
        "source": {"repo": src["repo"], "commit": src["commit"], "dir": src["dir"], "license": src["license"],
                   "files_sha256": src["sha256"]},
        "sic_mosfet_half_bridge": True,
        "sic_mosfet_half_bridge_basis": (
            "[F] README of the source dir: 'SiC half-bridge, wire-bonded, single-sided cooling' (script docstring FACTS); "
            "Part_Lib/MOSFET.part CPM2-1200-0025B is the only die part; the layout script defines only power_lead, "
            f"signal_lead and MOS parts; dies {adm['dies']}. [I] the HS/LS assignment and the nets come from the "
            "connectivity (o003-reference-reconstructions.md section 2, net assignment [I]); the part's datasheet was not "
            "read, so 'SiC' rests on the README sentence, not on a die record"),
        "separate_antiparallel_diode_dies": adm["diode_dies"] != 0,
        "separate_antiparallel_diode_dies_basis": (
            f"[F] diode_dies {adm['diode_dies']} in the T0263 record: the layout script defines only power_lead, "
            "signal_lead and MOS parts (no diode part). Whether the MOSFET's body diode or an external diode carries the "
            "freewheeling current is not stated by the files and does not enter the field (it concerns diode dies in the "
            "layout)"),
        "nda_permits_cloud_vm": None,
        "nda_permits_cloud_vm_note": "customer only; not applicable to a public reference",
        "admissible": bool(adm["admissible"]),
        "reason": f"{adm['reason']}; set by D0019 item 1 (the D0010 public fallback, no customer reference was admitted)",
        "decided_at": "2026-11-12 (founder decision D0019, founder session)",
        "L_term_H": float(r["L_term_H"]),
        "L_term_source": "config.L_term.public_H: public reference -> 7 nH (Z. Chen, PhD dissertation, Virginia Tech, 2013, Q3D "
                         "of the CPES laminated DC terminals; research/notes/o003-public-benchmarks.md line 61; D0011)",
        "on_grid_0p5mm": bool(r["on_grid_0p5"]),
        "snapping_check": "not required: on the 0.5 mm grid, s_ref = 0 (O003 notes: the check applies only to a reference not "
                          "on the 0.5 mm grid); T0263 snap records 0 / 0 / 0 at 0.5 / 0.25 / 0.125 mm",
        "keepout_nets": list(r["keepout_nets"]),
        "expected": ("twin and D at L0/L1 under E008's rules (T0314 variant R1, before the D0018 floor): twin exact on the "
                     "power copper, L1(D)/L1(W) 1.395 >= 1.388. Expected counted (inference, not a result)"
                     if ref == "2D_Case_2R" else
                     "TwinError expected (T0263, T0314: 'no (orientation, sequence) of the generator space matches the "
                     "reference geometry' under every rule variant; D0018 fix-list item 3) -> excluded under F1(a), "
                     "reported with the reason; inference until the registered run's prepare() raises it"),
    }


DEVIATION = {
    "decision": "D0019 item 2 (founder session 2026-11-12)",
    "statement": ("DECLARED F3 DEVIATION (D0019): both judged references (2D_Case_2R, 2D_Case_6) were loaded at L0/L1 "
                  "before E008's freeze (T0263 twin check, T0314 diagnosis), and E008's runner and spec changed afterwards "
                  "(T0316, T0317); no inductance (l2_layout), thermal or search result of either reference existed; the "
                  "removed rule is a lower bound on gate/Kelvin-wire length, no power-copper, power-wire or die rule "
                  "changed; src/ unchanged since T0300"),
    "loaded_before_freeze": [
        {"task": "T0263", "commit": "6e96ca9b", "date": "2026-11-11 01:01:50 -0800",
         "what": "reconstructions, snapping, measure_rules, twin-space check (L0, L1 inside twin only): 2R TwinError "
                 "signal_wire_length, Case 6 TwinError no (orientation, sequence)"},
        {"task": "T0314", "commit": "e9c7fa90", "date": "2026-11-11 10:26:59 -0800",
         "what": "twin and degradation coverage at L0/L1 on 2R, Case 6 and Case 4 (which rule binds; 2R under R1: twin "
                 "exact, L1(W)/L1(ref) 1.0000, L1(D)/L1(W) 1.395)"}],
    "changed_after": [
        {"task": "T0316", "commit": "79363620", "date": "2026-11-11 20:39:45 -0800",
         "what": "D0018 decisions 1-2 (D as a yardstick under the 1.5 mm power-width floor; exclusion when no valid D "
                 "exists), found on the dev layout 2D_Case_4"},
        {"task": "T0317", "commit": "8cebdb56", "date": "2026-11-12 07:24:06 -0800",
         "what": "D0018 fix-list item 1 (min_signal_wire_length dropped from E008's rules), prompted by 2R; solver "
                 "failures in D's band solves -> INVALID (T0318 finding 0)"},
        {"task": "T0320", "commit": "this task", "date": "2026-11-12",
         "what": "judged-reference loader, T0319 guard, registered path of full(), --check-references, real sizes in "
                 "--plan; no rule, gate, tolerance, generator, twin, degradation or search change"}],
    "src_unchanged_since": {"task": "T0300", "commit": "096b127b",
                            "git_date": "2026-11-10 11:31:43 -0800 (19:31 UTC; D0019 as restated in the T0320 packet says "
                                        "11:31 UTC, git records 11:31 local time, -0800)"},
    "known_before_freeze": ["L0: reconstruction geometry, fingerprints, snap records, measured rules, DRC under own rules, "
                            "mesh-only unknown / DOF counts, stack types",
                            "L1 (physics.peec inside twin()/degrade()): 2R L1(W)/L1(ref) and L1(D)/L1(W) under R1 (T0314)",
                            "twin outcomes: 2R TwinError under raw measure_rules, twin under R1; Case 6 TwinError under "
                            "every variant"],
    "not_known_before_freeze": ["any l2_layout L_sub or band solve", "any thermal solve (scikit-fem or finite volume), "
                                "P_ref", "any search, screen or candidate", "D of 2R under the D0018 floor", "twin gates"],
    "rules_changed": "only min_signal_wire_length (a lower bound on gate/Kelvin-wire length, D0018 item 1); no power-copper, "
                     "power-wire or die rule changed (D0019 item 2); O003 scope_in's enumerated rules are the complete "
                     "meaning of 'at least as strict as the reference's own' (D0019 item 5)",
    "carried_by": "deviation_tag(cfg) -> every row (column f3_declared_deviation), the evaluation report, the result notes",
}


def refs() -> None:
    spec = load()
    c = spec["config"]
    c["references"] = [entry(r) for r in REFS]
    c["freeze"]["files"][SCRIPT] = sha(SCRIPT)
    c["freeze"]["rule"] = ("F3: code hashes recorded before any judged reference is loaded; a change voids the run. The twin "
                           "construction and the degradation rule are both in twin.py; the judged references are rebuilt "
                           f"only by the frozen T0263 script ({SCRIPT}, D0019). --verify-freeze recomputes them.")
    c["reference_set_rule"] = (
        "D0010: customer reference layouts shared under NDA by 2026-11-12 and admissible; otherwise, or if none is "
        "admissible, the public PowerSynth 2D_Case_2R and 2D_Case_6 with the label 'public benchmarks, low power, "
        "indicative'. Customer and public references are never mixed in one verdict. Excluded customer references are "
        "reported by vault id and reason only (D0011). D0019 (2026-11-12): the reference set is D0010's public fallback, "
        "2D_Case_2R and 2D_Case_6 in that order (config.references); 2D_Case_6 is expected to be excluded under F1(a) "
        "(TwinError; D0018 fix-list item 3), so 2D_Case_2R is expected to be the only counted reference and any verdict "
        "goes to the founder review; O003 scope_in's enumerated design rules are the complete meaning of 'design rules at "
        "least as strict as the reference's own' (D0019 item 5)")
    c["f3_declared_deviation"] = DEVIATION
    c["judged_reference_loader"] = {
        "function": "e008_run.judged_reference (rebuild_reconstruction, e008_rules, spec_from_layout with the entry's "
                    "keepout_nets)",
        "order": "fingerprint and grid flag checked first (ReferenceRefused: the run is void); then e008_rules (no "
                 "overrides) and the spec; prepare() refuses any spec without e008_rules' rules_record or with "
                 "min_signal_wire_length set (review T0319 finding 0, RulesGuardError)",
        "seeds": "config.seeds: reference index i in config.references order (derive_seed(sealed, purpose, i))",
        "resume": "every solve writes one result file under the workdir (--workdir, else $E008_WORKDIR, else "
                  "<run_dir>/work); a rerun re-solves nothing that exists; run_manifest.json refuses a workdir written "
                  "under another config or seed",
        "d0019_item_4": "until this loader is frozen in a registered spec, 2D_Case_2R and 2D_Case_6 are only rebuilt "
                        "(--check-references: fingerprints and mesh counts); tested end to end on fake layouts (selftest) "
                        "and on the dev layouts"}
    save(spec)
    print("refs: written", [e["reference_id"] for e in c["references"]], "freeze +", SCRIPT[:40])


CAND_RATIO_BASIS = ("candidate DOFs = the reference's own frozen-rule DOFs x the per-level candidate/reference ratio "
                    "measured on 2D_Case_4 (research/o003/e008_dev/probe_dofs.json via the earlier proxy: 98698/51098, "
                    "708819/365435, 5350885/2752565); no candidate of 2R or Case 6 may be generated before the freeze "
                    "(D0019 item 4)")


def sizes() -> None:
    spec = load()
    c = spec["config"]
    cr = json.loads((DEV / "check_references.json").read_text())["references"]
    old = {r["name"]: r for r in c["compute"]["plan_references"]}
    c4_ref, c4_cand = (old["2D_Case_2R"]["fem_dofs"][k] for k in ("reference", "candidate"))
    if c4_ref[0] != 51098:  # already replaced: take the ratios from the stored basis numbers
        c4_ref, c4_cand = [51098, 365435, 2752565], [98698, 708819, 5350885]
    ratio = [b / a for a, b in zip(c4_ref, c4_cand, strict=True)]
    new = []
    for e in c["references"]:
        rid = e["reference_id"]
        m = cr[rid]
        if not m["fingerprint_ok"] or m["fingerprint"] != e["reconstruction_sha256"]:
            raise SystemExit(f"{rid}: check_references fingerprint mismatch")
        new.append({
            "name": rid, "area_m2": m["baseplate_area_m2"], "on_grid": m["on_grid_0p5mm"], "spot": True,
            "expected_excluded_at_twin": rid == "2D_Case_6",
            "em_unknowns": m["l2_layout_unknowns"],
            "fem_dofs": {"reference": m["fem_dofs_frozen_rule"],
                         "candidate": [int(round(d * q)) for d, q in zip(m["fem_dofs_frozen_rule"], ratio, strict=True)]},
            "fv_cells": m["fv_cells"],
            "screen_s_per_candidate": old[rid]["screen_s_per_candidate"],
            "size": ("REAL (T0320, --check-references on the frozen reconstruction, fingerprint "
                     f"{e['reconstruction_sha256'][:8]}...): l2_layout unknowns per band level, scikit-fem DOFs per level "
                     "(frozen rule), FV box cells levels 1-2 built, level 3 = level 2 x 8; " + CAND_RATIO_BASIS
                     + "; screen rate still the 0.45 s slow end (no candidate generated, D0019 item 4)"),
            "spot_note": ("own non-default stack type (AlN 0.835 mm), the F6(e) spot-check reference of its type"
                          if rid == "2D_Case_2R" else
                          "own non-default stack type (AlN 0.64 mm); excluded at its twin in the expected scenario, so "
                          "the runner runs no spot check of its type then (see founder_decisions_before_registration)")})
    c["compute"]["plan_references"] = new
    cm = c["compute"]["cost_model"]
    cm["em_level_mem_prior_basis"] = cm["em_level_mem_prior_basis"].replace(
        "--plan uses the model (Case 4 proxies)", "--plan uses the model on the references' real unknown counts (T0320)")
    save(spec)
    print("sizes: plan_references real for", [r["name"] for r in new])

def _fmt(v: dict) -> str:
    return (f"{v['vm_hours']} VM-hours, ${v['usd']}, {v['billed_vcpu_hours']} billed vCPU-hours, {v['process_cpu_hours']} "
            f"process CPU-hours")


def cost() -> None:
    spec = load()
    c = spec["config"]
    pl = json.loads((DEV / "plan_T0320.json").read_text())
    cr = json.loads((DEV / "check_references.json").read_text())["references"]
    e, u = pl["cases"]["expected"], pl["cases"]["upper"]
    ae, au = pl["if_all_counted"]["expected"], pl["if_all_counted"]["upper"]
    for v in pl["if_all_counted"].values():
        v["per_solve_on_vm"] = "as in cases (2D_Case_2R sizes)"
    b2r = e["phase_b_big_memory_jobs"][0]
    sp6 = pl["f6e_spot_check_of_excluded_type"]["2D_Case_6"]
    b6 = sp6["phase_b_big_memory_jobs"][0]
    r2, r6 = cr["2D_Case_2R"], cr["2D_Case_6"]
    stmt = (
        f"REAL SIZES (T0320, --check-references on the frozen reconstructions, D0019 item 4: rebuild, fingerprint and mesh "
        f"counts only). 2D_Case_2R: l2_layout {r2['l2_layout_unknowns']['lat0.25']:,} unknowns at 0.25 mm (Case 4 proxy "
        f"4,108,580), scikit-fem DOFs {r2['fem_dofs_frozen_rule']} at levels 0-2 (proxy [51098, 365435, 2752565]: the real "
        f"thermal grids are 1.5x larger), FV box cells {r2['fv_cells']} (level 3 = level 2 x 8; proxy 234.8 M). 2D_Case_6: "
        f"{r6['l2_layout_unknowns']['lat0.25']:,}, {r6['fem_dofs_frozen_rule']}, {r6['fv_cells']}. Candidate DOFs: the "
        f"reference's x the Case 4 candidate/reference ratio (no candidate generated, D0019 item 4); screens at the 0.45 s "
        f"slow end. EXPECTED SET (D0019: 2D_Case_6 excluded at its twin, TwinError in prepare() before any solve, so no "
        f"job of it): expected (near ties {e['near_ties']}, {e['thermal_batches']} batch) {_fmt(e)}; upper (15 near ties, "
        f"2 batches, 8 null checks) {_fmt(u)}. IF 2D_Case_6 WERE NOT EXCLUDED: expected {_fmt(ae)}; upper {_fmt(au)}. "
        f"Phase B is inside these: the F6(e) finite-volume level-3 solve of 2D_Case_2R ({b2r['n']:,} cells, peak "
        f"{b2r['peak_GB']} GB at E009's 1,500 B/cell) runs alone on the VM resized to {b2r['machine']} ({b2r['ram_GB']:.0f} "
        f"GB, ${b2r['usd_per_h']}/h): {b2r['hours']} h, ${b2r['usd']} (range {b2r['sensitivity']['low']['hours']}-"
        f"{b2r['sensitivity']['high']['hours']} h, ${b2r['sensitivity']['low']['usd']}-${b2r['sensitivity']['high']['usd']}). "
        f"F6(e) ON 2R DOES NOT FIT IN 150 GB (needs ~{b2r['ram_GB']:.0f} GB; N2D allows 768 GB); every other solve peaks "
        f"at or below {max(e['peak_GB_per_reference']['2D_Case_2R']['em'], e['peak_GB_per_reference']['2D_Case_2R']['thermal'])} "
        f"GB (phase A, {pl['usable_GB']:.1f} GB usable). F6(e) OF 2D_Case_6's OWN STACK TYPE when 2D_Case_6 is excluded: the "
        f"runner runs NEITHER a spot check NOR a report of that type (Run.drive takes the types from the references that "
        f"reach it; the exclusion itself is reported); a spot check would cost {sp6['vm_hours']} VM-hours, ${sp6['usd']} "
        f"(calibration, scikit-fem levels 0-2 and FV levels 1-3 of the reconstruction; FV level 3 {b6['n']:,} cells, "
        f"{b6['peak_GB']} GB on {b6['machine']}), a report costs nothing. BUDGET: USD fits (E008 ${e['usd']}-${au['usd']} "
        f"over both scenarios, budget.usd 250); cpu_hours 320 holds on every reading for E008 alone: billed vCPU-hours "
        f"{e['billed_vcpu_hours']}-{u['billed_vcpu_hours']} (expected set) or {ae['billed_vcpu_hours']}-"
        f"{au['billed_vcpu_hours']} (if 2D_Case_6 were counted); process CPU-hours {e['process_cpu_hours']}-"
        f"{au['process_cpu_hours']}. Not included: the full-fidelity dev run (~10-12 VM-hours, ~80-96 billed "
        f"vCPU-hours) and no snapping check (both references on the 0.5 mm grid, D0019). DATE: E008 ends "
        f"{e['end_date_if_start']}-{au['end_date_if_start']} if started {c['compute']['vm']['earliest_start']}, provided "
        f"the ~{b2r['ram_GB']:.0f} GB resize is allowed (founder item F6(e) memory).")
    est = {"filled_by": "e008_run.py --plan (T0320, real reference sizes; research/o003/e008_dev/plan_T0320.json)",
           **{k: v for k, v in pl.items()}, "peak_memory_per_reference_GB": ae["peak_GB_per_reference"], "statement": stmt}
    c["cost_estimate"] = est
    spec["cpu_hours_est"] = float(e["billed_vcpu_hours"])
    fd = c["founder_decisions_before_registration"]
    keep, settled = [], c["founder_decisions_settled"]
    g2, g6 = r2["fem_dofs_frozen_rule"], r6["fem_dofs_frozen_rule"]
    growth = lambda d: [round(b / a, 3) for a, b in zip(d[:-1], d[1:], strict=True)]  # noqa: E731
    add = {
        "the band check": "2R's records settle nothing here: no l2_layout result of 2R exists (D0019 item 2); its band "
                          f"levels have {r2['l2_layout_unknowns']} unknowns (--check-references)",
        "before registration the same full-fidelity": f"2R's records: no thermal solve exists, so attainability is open; "
                          f"mesh only: frozen-rule DOFs {g2} (growth {growth(g2)} per step, inside 8 +/- 15 %), 2D_Case_6 "
                          f"{g6} (growth {growth(g6)})",
        "if any dev e_R": "2R's records settle nothing here (dev geometry only)",
        "twin-copper areas": "moot for D0019's set (public references only; F5 concerns customer geometry); kept for a "
                             "future customer set",
        "T0262 finding": "2R's records (L0, 2D_Case_2R.json): judged references take measure_rules less "
                         "min_signal_wire_length with NO override (D0019 item 5, judged_reference); 2R's max_wire_length is "
                         "the unmeasured 15 mm default (power wires 5.0-6.39 mm), so Case 4's 'twin power wire a few um over "
                         "the measured longest' cannot arise on 2R; min_wire_pitch 0.749 mm (2.50 diameters) is measured on a "
                         "gate/power wire pair; under these rules T0314 (R1, L0/L1, before the D0018 floor) built the 2R twin "
                         "exact on the power copper. Only the registered prepare() decides (D0019 item 4)",
        "row contract": "2R's records settle nothing here",
        "F6(e) reading": "D0019's set has no inadmissible reference (both admissible: no diode dies, public), so this "
                         "reading does not arise for it; an admissible reference EXCLUDED at its twin is the separate item "
                         "below",
        "stack-type rounding": "2R AlN 0.835 mm (T0263 type other:13fbac2ad296), 2D_Case_6 AlN 0.64 mm (other:d34d9682c1b0): "
                               "two non-default types under the rule (they differ by 195 um)",
        "_quick_ok report": "2R: no sample drawn before the freeze (D0019 item 4)",
        "2D_Case_4 fail-fast": "2R (T0314 R1, L0/L1, before the D0018 floor, D at 2R's own 4.0 mm power minimum): D reached "
                               "L1(D)/L1(W) 1.395 >= 1.388 after 16 walk steps; under the 1.5 mm floor D may differ; not "
                               "re-run (D0019 item 4)",
        "E009-registered smoke": "2R's records settle nothing here (dev rows only)",
    }
    for it in fd:
        if it.startswith(("the snapping check", "config.references")):
            continue
        if it.startswith("budget:"):
            it = (f"budget: with the real sizes (T0320) cpu_hours 320 holds for E008 on either reading: billed vCPU-hours "
                  f"{e['billed_vcpu_hours']}-{u['billed_vcpu_hours']} (2D_Case_6 excluded, expected) or "
                  f"{ae['billed_vcpu_hours']}-{au['billed_vcpu_hours']} (if counted), process CPU-hours "
                  f"{e['process_cpu_hours']}-{au['process_cpu_hours']} (cost_estimate.statement); which reading the cap "
                  f"uses stays the founder's (with the dev run, all VM work is about {e['billed_vcpu_hours'] + 80:.0f}-"
                  f"{au['billed_vcpu_hours'] + 96:.0f} billed vCPU-hours)")
        elif it.startswith("F6(e) at Case 4 size"):
            it = (f"F6(e) memory on the real 2D_Case_2R (T0320, supersedes the Case 4 proxy): the finite-volume level-3 grid "
                  f"has {b2r['n']:,} box cells ({r2['fv_cells'][1]:,} built at level 2, x 8), peak {b2r['peak_GB']} GB at "
                  f"E009's 1,500 B/cell: it does NOT fit in 150 GB; it fits on the same 8-vCPU VM resized to "
                  f"{b2r['machine']} ({b2r['ram_GB']:.0f} GB; N2D allows 768 GB), {b2r['hours']} h, ${b2r['usd']}. 2R is "
                  f"the only reference of its type expected to be counted, so no smaller AlN spot-check reference exists in "
                  f"D0019's set. Choose: allow ~{b2r['ram_GB']:.0f} GB; or a memory-lean FV level 3 under a new spec; "
                  f"if ~150 GB is the ceiling, F6(e) cannot run and E008 gives no verdict (F6e: INVALID)")
        elif it.startswith("EM memory model"):
            it = (it.split(" Re-run --plan on T0263")[0] + f" T0320: --plan now uses the references' counted unknowns "
                  f"(2D_Case_2R {r2['l2_layout_unknowns']['lat0.25']:,} at 0.25 mm, 2D_Case_6 "
                  f"{r6['l2_layout_unknowns']['lat0.25']:,}; the 0.25 mm solve peaks at "
                  f"{e['per_solve_on_vm']['solves']['em:lat0.25']['peak_GB']} GB by the model); no 0.5 mm peak of either "
                  f"reference may be measured before the freeze (D0019 item 4), so the priors x the model schedule them "
                  f"until Scheduler.learn measures one")
        else:
            for k, v in add.items():
                if it.startswith(k) and "(T0320)" not in it:
                    it = f"{it} (T0320) {v}"
                    break
        keep.append(it)
    keep.append(
        f"F6(e) for an admissible reference EXCLUDED at its twin (2D_Case_6, expected; T0320 fact): the runner runs NEITHER "
        f"a spot check NOR a report of its stack type (Run.drive collects the types from the references that reach it; "
        f"evaluate reports the exclusion under 'excluded' only); verified by the selftest (full_orchestration). Readings: "
        f"(a) neither (as implemented): $0; (b) report the type as 'reference excluded, no spot check' (not gated): $0; "
        f"(c) spot check the excluded reference's reconstruction (calibration, scikit-fem L0-2, FV L1-3): "
        f"{sp6['vm_hours']} VM-hours, ${sp6['usd']} (range ${sp6['phase_b_sensitivity']['low']['usd']}-"
        f"${sp6['phase_b_sensitivity']['high']['usd']}), FV level 3 {b6['n']:,} cells, {b6['peak_GB']} GB on "
        f"{b6['machine']}. The founder chooses one at registration")
    c["founder_decisions_before_registration"] = keep
    s_new = ("D0019 (founder session 2026-11-12): config.references is the D0010 public fallback 2D_Case_2R, 2D_Case_6 with "
             "admissibility, L_term 7 nH, fingerprints and the judged-reference loader (judged_reference, frozen T0263 "
             "script in config.freeze), --plan re-run on the real reconstructions (T0320); the snapping check is not "
             "required (both references on the 0.5 mm grid, s_ref = 0); declared F3 deviation in "
             "config.f3_declared_deviation (D0019 item 2)")
    if not any(x.startswith("D0019") for x in settled):
        settled.append(s_new)
    save(spec)
    print("cost: cpu_hours_est", spec["cpu_hours_est"], "| items", len(keep))


def main() -> int:
    step = sys.argv[1] if len(sys.argv) > 1 else ""
    if step == "refs":
        refs()
    elif step == "sizes":
        sizes()
    elif step == "cost":
        cost()
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
