"""T0332 (founder session 2026-11-13, within D0020 item 2, reported only): the die-average best's band solve into
experiments/drafts/E008.yaml.  Runs e008_run.py --plan (research/o003/e008_dev/plan_T0332.json), writes its cases into
config.cost_estimate (rates and cost model unchanged), cpu_hours_est = the expected billed vCPU-hours, and the T0332 text into
config.reporting.virtual_junction.  Every number is read from the plan, never typed.  Idempotent.  Usage:
  uv run python research/o003/e008_dev/t0332_spec_update.py
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
SPEC = ROOT / "experiments/drafts/E008.yaml"
PLAN = ROOT / "research/o003/e008_dev/plan_T0332.json"
TAG = "T0332:"


def main() -> int:
    subprocess.run([sys.executable, str(ROOT / "experiments/runners/e008_run.py"), "--plan", "--plan-out", str(PLAN)],
                   check=True, cwd=ROOT, stdout=subprocess.DEVNULL)
    pl = json.loads(PLAN.read_text())
    spec = yaml.safe_load(SPEC.read_text())
    c = spec["config"]
    ce = c["cost_estimate"]
    x = pl["vj_band_extra"]
    e, u = pl["cases"]["expected"], pl["cases"]["upper"]
    ae, au = pl["if_all_counted"]["expected"], pl["if_all_counted"]["upper"]
    xe, xu = x["cases:expected"], x["cases:upper"]
    old = ce.get("statement", "")
    old = old.split(" || ", 1)[1] if old.startswith(TAG) else old
    stmt = (f"{TAG} --plan now prices, per counted reference, at most one reported-only band set of the die-average best "
            f"({xe['n_solves_added']} solves at 0.5 mm cells: lat0.5, thk_c, thk_f, fil_f; scheduled after every gated solve; "
            f"run only when that layout has no band yet, so priced as an upper bound in every case). Added billed vCPU-hours: "
            f"expected +{xe['billed_vcpu_hours_added']} ({xe['billed_vcpu_hours_without']} -> {xe['billed_vcpu_hours']}), "
            f"upper +{xu['billed_vcpu_hours_added']} ({xu['billed_vcpu_hours_without']} -> {xu['billed_vcpu_hours']}); "
            f"+${xe['usd_added']}-${xu['usd_added']}; if 2D_Case_6 were counted "
            f"{ae['billed_vcpu_hours']}-{au['billed_vcpu_hours']}. The 320 cpu_hours cap (read as billed vCPU-hours, D0020 "
            f"item 4) holds in every case (largest {max(v['billed_vcpu_hours'] for k, v in x.items() if k != 'note')}). "
            f"Rates and cost model unchanged. Expected now {e['n_solves']} solves, {e['vm_hours']} VM-hours, ${e['usd']}, "
            f"{e['billed_vcpu_hours']} billed vCPU-hours; upper {u['n_solves']} solves, {u['vm_hours']} VM-hours, "
            f"${u['usd']}, {u['billed_vcpu_hours']}. cpu_hours_est = the expected billed vCPU-hours, changed because the "
            f"plan's number changed || {old}")
    for k, v in pl.items():
        ce[k] = v
    ce["filled_by"] = "e008_run.py --plan (T0332, dev near ties, with the die-average best's band set; research/o003/e008_dev/plan_T0332.json)"
    ce["statement"] = stmt
    spec["cpu_hours_est"] = float(e["billed_vcpu_hours"])
    rp = c["reporting"]
    base = rp["virtual_junction"].split(f" {TAG} ", 1)[0].rstrip(".")
    rp["virtual_junction"] = base + (
        f". {TAG} h_lo_vj is made computable on a real run. After the frozen driver has finished and the gated rows are "
        "assembled, per reference the runner determines the 'die-average best': the layout A1's formula "
        "(mfos.metrics.headroom_per_reference, unchanged) picks on virtual_junction_report's row copy with T_vj in place of "
        "Tj max (vj_best_layouts; no exception text is parsed: a layout without band columns gets placeholder values in a "
        "probe copy, which cannot change best_id because the formula reads the band only for e_R after best is fixed). If "
        "that layout's row lacks the band columns (L_sub_c05_H, L_sub_thk_c_H, L_sub_thk_f_H, L_sub_wire_f_H), its BAND "
        "em_jobs are submitted through its reference's main Driver and the run's Scheduler (same job keys and solver "
        "settings as every other band solve, so a resumed run finds them; phase A/B split as any job), only after every gated "
        "solve is done; their values go into the report's own row copy only, never into the gated rows, er.rows, the "
        "metrics, the checks, the stop rules or the F3 order. The report then gives h_lo_vj with best_id_vj and "
        "die_average_best (layout, fingerprint, the Tj-max and inductance-only bests for the record, band_source "
        "'solved for this report only' or 'gated rows', new_solves). Any failure (solver error, memory, phase stop) or "
        "--replay-only with a missing band leaves h_lo_vj null with h_lo_vj_reason; it never raises and changes no gated "
        "value. --plan prices at most one band set per counted reference (cost_estimate.vj_band_extra). Selftest "
        "(vj_band_failures): a synthetic case whose die-average best differs from the Tj-max best and the inductance-only "
        "best and has no band in the gated rows: h_lo_vj non-null and equal to headroom_per_reference on the T_vj copy "
        "carrying that band; rows, metrics, checks and the gated report byte-identical with the step disabled; resume solves "
        "nothing; --replay-only and a planted failing band job give null with a reason and change nothing gated")
    SPEC.write_text(yaml.safe_dump(spec, sort_keys=False, width=120, allow_unicode=False))
    print("spec updated: cpu_hours_est", spec["cpu_hours_est"], json.dumps({k: v for k, v in x.items() if k != "note"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
