"""Writes experiments/drafts/E010.yaml (T0339; founder decision D0021 items 2-4 and 7, id E010 by D0022) and
research/o003/e010_dev/spec_diff.md.

Start: the REGISTERED experiments/specs/E008.yaml (D0021 item 2: E010 = E008 with three changes only), not
research/o003/e008_dev/make_spec.py's output: E008's registered content was built by that script plus the T0320-T0336 update
scripts, so regenerating from make_spec.py alone would not reproduce it.  Changes, and nothing else:
  (a) the repaired generator sampler (T0338): its sha256 enters config.freeze;
  (b) SearchInfeasible: a reference whose main or control screen cannot draw a DRC-valid candidate is excluded and reported
      (failure_consequences, the at_least_one_counted_reference description, the deviation record);
  (c) new freeze hashes: every config.freeze file and every other recorded sha256 recomputed from the files here;
  the id and its paths (runner, dev rows, code_under_test's runner); the --plan cost lines (plan.json from
  `e010_run.py --plan --plan-out research/o003/e010_dev/plan.json`) and D0021 item 4's screen rate of each reference from
  `e010_run.py --check-references --out research/o003/e010_dev/check_references.json`.
Every key that differs from the registered E008 spec is listed in spec_diff.md with its reason; an unlisted difference
stops this script.  Run: uv run python research/o003/e010_dev/make_spec.py
"""
import copy
import hashlib
import json
import math
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
DEV = ROOT / "research/o003/e010_dev"
H = lambda p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest()  # noqa: E731
E8 = yaml.safe_load((ROOT / "experiments/specs/E008.yaml").read_text())
spec = copy.deepcopy(E8)
for k in ("registered_by", "registered_at", "spec_hash", "runner_files"):  # written by mfos at registration
    spec.pop(k, None)
spec.update(id="E010", status="draft", runner="uv run python experiments/runners/e010_run.py",
            dev_rows="experiments/drafts/E010.dev_rows.json",
            title=E8["title"] + " - E010: E008 with the repaired generator sampler and the SearchInfeasible exclusion "
                                "(D0021, id D0022)")
spec["code_under_test"] = [p.replace("experiments/runners/e008_run.py", "experiments/runners/e010_run.py")
                           for p in E8["code_under_test"]]
c = spec["config"]

# (c) every recorded hash from the files
c["freeze"]["files"] = {p: H(p) for p in E8["config"]["freeze"]["files"]}
assert c["fem_rule_file_sha256"] == H(c["fem_rule_path"]) and c["thermal_fem_sha256"] == H(c["thermal_fem_path"])
for e in c["references"]:
    assert e["reconstruction_record_sha256"] == H(e["reconstruction_record"]), e["reference_id"]
changed = sorted(p for p, h in c["freeze"]["files"].items() if h != E8["config"]["freeze"]["files"][p])
assert changed == ["src/moduleforge/generate/derivative.py"], changed  # only (a) may move a frozen file

# (b) SearchInfeasible
SI = ("D0021 item 2(b): a reference whose main or control screen cannot draw a DRC-valid candidate (derivative.generate "
      "raises 'no DRC-valid candidate in 20000 consecutive draws') is excluded and reported (reason SearchInfeasible, stage "
      "screen) like a TwinError: no driver, no rows, no spot check; E010 is INVALID only if no reference remains. Any other "
      "failed solve or screen still stops the run (e010_run.SearchInfeasible, Run.search_infeasible; selftest "
      "search_infeasible_failures)")
c["failure_consequences"]["SearchInfeasible"] = SI
sc = next(x for x in spec["sanity_checks"] if x["name"] == "at_least_one_counted_reference")
sc["description"] += " E010 (D0021 item 2(b)): a SearchInfeasible exclusion (stage screen) counts like a TwinError."

# the deviation record: D0021 where E008 records D0019/D0020, with review T0341's support finding (packet item 5a)
fz = json.loads((DEV / "feasibility_2r.json").read_text()) if (DEV / "feasibility_2r.json").exists() else None
dv = c["f3_declared_deviation"]
old_tail = "; src/ unchanged since T0300"
assert dv["statement"].endswith(old_tail), dv["statement"][-80:]
dv["statement"] = dv["statement"][: -len(old_tail)] + (
    "; src/ unchanged since T0300 except src/moduleforge/generate/derivative.py. DECLARED F3 DEVIATION (D0021, E010): the "
    "generator sampler was changed after 2D_Case_2R was loaded (T0338: a slot stack may straddle split free windows); "
    "before E010's registration 2R and 2D_Case_6 were used only for generator/DRC feasibility (no L1, l2_layout, EM, "
    "thermal, FV, degrade() or search; no solve value of run E008-20261114T095904-2c22 read); E010 reuses no E008 run data")
mix = (f"measured (research/o003/e010_dev/feasibility_2r.py, unsealed seeds, {fz['n_draws']:,} draws per seed): 2R "
       f"orientation mix of DRC-clean draws {fz['orientation_mix']}, (orient, hs_first, hs_die_first, ls_die_first) mix "
       f"{fz['config_mix']}, topology mix {fz['topology_mix']}; gen2_0 (dev): {fz['gen2_0']['same_topology_as_twin']} of "
       f"{fz['gen2_0']['n']} DRC-clean candidates share the twin's topology") if fz else "PENDING: run feasibility_2r.py"
dv["d0021"] = {
    "decision": "D0021 items 2-4 and 7 (founder session 2026-11-14); successor id E010 by D0022 (D0021's text says E009)",
    "changes": ["(a) generator sampler: a slot stack may be placed across more than one free window where no single "
                "window holds the minimal stack (_Ctx.split; T0338, merged 242a6d7a)",
                "(b) " + SI, "(c) new freeze hashes (config.freeze.files: derivative.py changed, the others equal)"],
    "unchanged": "O003's thresholds and comparators, gated criteria and parameters, metrics and recompute entries, null "
                 "baselines, stop rules, F3 order, budgets, bands, D0019's reference set, D0020's Tj rule and readings, "
                 "twin.py (twin and degradation), the search driver, the cost-model rates, the sealed-seed policy (a new "
                 "mint gives E010 its own seeds); 2D_Case_6 is still expected to be excluded (TwinError)",
    "loaded_before_freeze": [{"task": "D0021 diagnosis", "date": "2026-11-14", "what": "founder session: generator/DRC "
                              "only on 2R, 0 DRC-clean in 312 000 draws under E008's sampler"},
                             {"task": "T0338 / T0341 / T0339", "date": "2026-11-14", "what": "generator/DRC feasibility on "
                              "2R (sampling, build, drc.check, twin() geometry fit with_l1=False, spec_from_layout); "
                              "--check-references' draw-rate check on 2R and 2D_Case_6"}],
    "dev_streams": "D0021 item 3: the sealed gen2_0 main and control streams of the E008 dev run (2 x 20 000 candidates) "
                   "are byte-identical under the new sampler (T0338, T0341, T0339 DoD), so E008's development rows carry "
                   "over (experiments/drafts/E010.dev_rows.json, rebuilt by --replay-only, no solve)",
    "support_on_2R": ("REVIEW T0341 FINDING (a statement of the support, not a metric, check or criterion): on 2D_Case_2R "
                      "every DRC-clean candidate has the twin's discrete configuration (orientation 0, sequence 0/1/0; "
                      "orientation 1 yields none), so E010's 2R search varies geometry only inside the reference's own "
                      "topology, while on gen2_0 about a quarter of candidates share the twin's topology. The cross-window "
                      "support applies only to orientations where _Ctx.split is True (2R: {0: True, 1: False}). " + mix),
}
dv["changed_after"] = dv["changed_after"] + [
    {"task": "T0338", "commit": "242a6d7a", "date": "2026-11-14", "what": "D0021 item 2(a): generator sampler across split "
     "free windows (src/moduleforge/generate/derivative.py)"},
    {"task": "T0339", "commit": "this task", "date": "2026-11-14", "what": "E010 design: D0021 item 2(b) SearchInfeasible "
     "exclusion, new freeze hashes, --check-references draw-rate check (item 4), dev rows replayed"}]

# D0021 item 4: the measured draw rate of every judged reference with a twin, in --plan's screen time
cr = json.loads((DEV / "check_references.json").read_text()) if (DEV / "check_references.json").exists() else None
cm = c["compute"]["cost_model"]
if cr:
    for r in c["compute"]["plan_references"]:
        f = cr["references"].get(r["name"], {}).get("feasibility")
        if f and f.get("ok"):
            r["screen_s_per_candidate"] = f["plan_screen_s_per_candidate"]
            r["screen_feasibility"] = {k: f[k] for k in ("draws", "drc_clean", "p", "p_lo999", "s_per_candidate_mac",
                                                         "draw_s_20000_mac_h", "p_abort_20000", "plan_rule")}
    cm["screen_rate_basis"] += (" E010 (D0021 item 4): each judged reference with a twin uses 0.45 s plus its own measured "
                                "draw time per DRC-clean candidate (e010_run.py --check-references, the numbers of "
                                "research/o003/e010_dev/feasibility_2r.py) times the largest measured Mac -> VM factor "
                                "(fv_sensitivity.high.vm_factor); plan_references[*].screen_feasibility")
plan = DEV / "plan.json"
if plan.exists():
    p = json.loads(plan.read_text())
    ex, up = p["cases"]["expected"], p["cases"]["upper"]
    ce = c["cost_estimate"]
    for k in ("cases", "if_all_counted", "vj_band_extra", "f6e_spot_check_of_excluded_type", "scenario"):
        if k in p:
            ce[k] = p[k]
    ce["filled_by"] = "e010_run.py --plan (research/o003/e010_dev/plan.json)"
    ce["peak_memory_per_reference_GB"] = ex["peak_GB_per_reference"]
    ce["e010_statement"] = (f"E010 (T0339, D0021 item 4): expected {ex['billed_vcpu_hours']} billed vCPU-hours "
                            f"({ex['vm_hours']} VM-hours, ${ex['usd']}), upper {up['billed_vcpu_hours']} ({up['vm_hours']} "
                            f"VM-hours, ${up['usd']}); the 320 vCPU-hour cap "
                            f"{'holds' if up['billed_vcpu_hours'] <= 320 else 'DOES NOT hold'} for E010 "
                            f"(E008 registered: {E8['config']['cost_estimate']['cases']['expected']['billed_vcpu_hours']} / "
                            f"{E8['config']['cost_estimate']['cases']['upper']['billed_vcpu_hours']})")
    spec["cpu_hours_est"] = round(ex["billed_vcpu_hours"], 1)

# ---------------------------------------------------------------------------------------------------- the diff guard
REASONS = [  # (path prefix, reason); the first match wins
    ("id", "the experiment's own id (D0022)"), ("status", "draft until registered"),
    ("title", "the experiment's own id and the D0021 changes in the title"),
    ("runner", "the experiment's own runner (packet item 2; e008_run.py unchanged)"),
    ("dev_rows", "the experiment's own dev rows (packet item 3)"),
    ("code_under_test", "the experiment's own runner path"),
    ("registered_by", "registration fields, written by mfos at E010's registration"),
    ("registered_at", "registration field"), ("spec_hash", "registration field"), ("runner_files", "registration field"),
    ("config.freeze.files.src/moduleforge/generate/derivative.py", "(a)/(c): the repaired sampler's new hash (T0338)"),
    ("config.failure_consequences.SearchInfeasible", "(b) SearchInfeasible (D0021 item 2(b))"),
    ("sanity_checks[7].description", "(b): at_least_one_counted_reference also counts a SearchInfeasible exclusion"),
    ("config.f3_declared_deviation.statement", "(a)/(b): the declared deviation now states D0021 and that derivative.py "
     "changed (the E008 text said src/ unchanged since T0300)"),
    ("config.f3_declared_deviation.d0021", "D0021 recorded where E008 records D0019/D0020, with review T0341's support "
     "finding (packet items 1, 5a)"),
    ("config.f3_declared_deviation.changed_after", "(a)/(b): T0338 and T0339 in the change record"),
    ("config.compute.plan_references", "D0021 item 4: measured draw rate in --plan's screen time (cost line)"),
    ("config.compute.cost_model.screen_rate_basis", "D0021 item 4: basis of the screen rate (cost line)"),
    ("config.cost_estimate", "cost lines that --plan changes"), ("cpu_hours_est", "cost line that --plan changes"),
]


def walk(a, b, path=""):
    if isinstance(a, dict) and isinstance(b, dict):
        for k in list(a) + [k for k in b if k not in a]:
            yield from walk(a.get(k, "<absent>"), b.get(k, "<absent>"), f"{path}.{k}" if path else str(k))
    elif isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        for i, (x, y) in enumerate(zip(a, b, strict=True)):
            yield from walk(x, y, f"{path}[{i}]")
    elif json.dumps(a, sort_keys=True, default=str) != json.dumps(b, sort_keys=True, default=str):
        if not (isinstance(a, float) and isinstance(b, float) and math.isnan(a) and math.isnan(b)):
            yield path


diffs = list(walk(E8, spec))
lines, bad = [], []
for d in diffs:
    why = next((r for pre, r in REASONS if d == pre or d.startswith(pre + ".") or d.startswith(pre + "[")), None)
    (lines if why else bad).append(f"| `{d}` | {why} |")
assert not bad, "differences without a reason (D0021: nothing may differ beyond (a)-(c)):\n" + "\n".join(bad)
assert spec["sanity_checks"][7]["name"] == "at_least_one_counted_reference"
(ROOT / "experiments/drafts/E010.yaml").write_text(yaml.safe_dump(spec, sort_keys=False, width=120, allow_unicode=False))
(DEV / "spec_diff.md").write_text(
    "# E010 vs the registered E008 spec: every differing key (generated by research/o003/e010_dev/make_spec.py)\n\n"
    "Compared key by key (lists element by element) against experiments/specs/E008.yaml; any difference without a reason "
    "below stops make_spec.py. Allowed (D0021, packet T0339): (a) the repaired sampler, (b) SearchInfeasible, (c) new freeze "
    "hashes, the experiment's own id and paths, and the cost lines that --plan changes. `<absent>` = the key exists on one "
    "side only.\n\n| key | reason |\n|---|---|\n" + "\n".join(lines) + "\n\nUnchanged (checked by the same walk): the gated "
    "criteria and their parameters, metrics, recompute entries, null baselines, stop rules, F3 order, budgets, bands, "
    "config.references (D0019), D0020's Tj rule and readings, the twin construction, the degradation rule, the search "
    "driver, the cost-model rates, the sealed-seed policy, every other freeze hash (equal to E008's).\n")
print(f"wrote experiments/drafts/E010.yaml and spec_diff.md: {len(diffs)} differing keys, all with a reason")
