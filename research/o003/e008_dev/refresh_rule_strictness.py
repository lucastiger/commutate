"""T0306 item 3: refresh the T0280 rule-strictness report in experiments/drafts/E008.dev_rows.json (L0 only, no solve).

For every dev geometry in the rows (housing70x40_gen2_0, 2D_Case_4; development geometry only, F3): rebuild the reference
with the runner's own dev_reference (which calls drc.rules.measure_rules on the layout, L0), require that its
measure_rules record equals the record stored in the rows (so the report is computed from the same measurement the smoke
run made), then write rule_strictness(record) from the runner (T0305 finding 1: the 'gap_*' keys) into
meta.per_reference[rid].info.rule_strictness and a provenance entry into meta.rule_strictness_refresh.  Nothing else in
the rows changes.  T0309 (review T0307 finding 2): re-run after the last runner edit to re-stamp runner_sha256; the
previous provenance entry is kept under 'previous' and 'report_unchanged' records whether rule_strictness gave the same
report as stored.  Run: uv run python research/o003/e008_dev/refresh_rule_strictness.py [TASK]
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ROWS = ROOT / "experiments/drafts/E008.dev_rows.json"
NAMES = {"housing70x40_gen2_0": "gen2_0", "2D_Case_4": "case4"}


def _jsonable(o):
    return json.loads(json.dumps(o, default=lambda x: x if not hasattr(x, "__dict__") else str(x)))


def main() -> int:
    sp = importlib.util.spec_from_file_location("e008_run", ROOT / "experiments/runners/e008_run.py")
    R = importlib.util.module_from_spec(sp)
    sys.modules["e008_run"] = R
    sp.loader.exec_module(R)
    cfg = R.load_spec()["config"]
    doc = json.loads(ROWS.read_text())
    per = doc["meta"]["per_reference"]
    old_prov = doc["meta"].get("rule_strictness_refresh")
    prov = {"task": sys.argv[1] if len(sys.argv) > 1 else "T0306", "script": "research/o003/e008_dev/refresh_rule_strictness.py",
            "runner_sha256": hashlib.sha256((ROOT / "experiments/runners/e008_run.py").read_bytes()).hexdigest(),
            "rules_py_sha256": hashlib.sha256((ROOT / "src/moduleforge/drc/rules.py").read_bytes()).hexdigest(),
            "method": "measure_rules re-run on each dev layout (L0), equal to the stored record, then rule_strictness()",
            "references": {}}
    for rid, v in per.items():
        if rid in ("excluded", "F6e"):  # T0324: evaluate()'s report keys in the full-fidelity dev rows, not references
            continue
        if rid not in NAMES:
            raise RuntimeError(f"{rid}: not a known development geometry (F3: dev geometry only)")
        rc = R.dev_reference(NAMES[rid], cfg)
        if rc.rid != rid:
            raise RuntimeError(f"{NAMES[rid]} built {rc.rid}, rows say {rid}")
        new = _jsonable(rc.info["measured_rules"])
        old = v["info"]["measured_rules"]
        if new != old:
            diff = sorted(k for k in set(new) | set(old) if new.get(k) != old.get(k))
            raise RuntimeError(f"{rid}: measure_rules now differs from the stored record in {diff}")
        rs = R.rule_strictness(old)
        unchanged = rs == v["info"].get("rule_strictness")
        n_gaps = sum(k.startswith("gap_") and R._num(x) for k, x in old.items())
        if n_gaps and not rs:
            raise RuntimeError(f"{rid}: {n_gaps} measured gaps but an empty report")
        v["info"]["rule_strictness"] = rs
        prov["references"][rid] = {"fingerprint": rc.reference.fingerprint(), "measured_rules_equal_stored": True,
                                   "n_measured_gaps": n_gaps, "n_reported": len(rs),
                                   "flag_2x": sorted(k for k, x in rs.items() if x["flag_2x"]),
                                   "report_unchanged": unchanged}
        print(rid, json.dumps(rs))
    if old_prov:
        prov["previous"] = {k: old_prov[k] for k in ("task", "runner_sha256", "rules_py_sha256") if k in old_prov}
    doc["meta"]["rule_strictness_refresh"] = prov
    ROWS.write_text(json.dumps(doc, indent=1))
    print(f"wrote {ROWS.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
