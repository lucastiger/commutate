"""T0317: the gen2_0 smoke prep (L0/L1 only, no solve) under the current runner, merged into the dev rows' meta.

Runs the runner's own dev_reference('gen2_0') and prepare() with the smoke quick_ok draws (config.dev.smoke.quick_ok_draws)
and the seed the smoke run used (dev seed, purpose 2, geometry index 0: --geoms gen2_0:gates:4,case4:gates:0).  Records the
E008 rules record (e008_rules: min_signal_wire_length dropped, D0018 model-fix item 1), the gate-wire report, D's rule, and
whether the reference and twin fingerprints equal the stored smoke rows' (if so, those rows stay valid under this runner).
Writes meta.per_reference['housing70x40_gen2_0'].prep; nothing else changes.  Development geometry only (F3).
Usage: uv run python research/o003/e008_dev/gen2_0_prep.py
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ROWS = ROOT / "experiments/drafts/E008.dev_rows.json"
RID = "housing70x40_gen2_0"


def main() -> int:
    sp = importlib.util.spec_from_file_location("e008_run", ROOT / "experiments/runners/e008_run.py")
    R = importlib.util.module_from_spec(sp)
    sys.modules[sp.name] = R
    sp.loader.exec_module(R)
    cfg = R.load_spec()["config"]
    draws = int(cfg["dev"]["smoke"]["quick_ok_draws"])
    t0 = time.perf_counter()
    rc = R.prepare(R.dev_reference("gen2_0", cfg), cfg, draws, R.derive_seed(int(cfg["dev"]["dev_seed"]), 2, 0))
    doc = json.loads(ROWS.read_text())
    stored = {r["role"]: r["fingerprint"] for r in doc["rows"] if r.get("reference_id") == RID and r.get("kind") == "layout"
              and r.get("role") in ("twin", "reconstruction")}
    fps = {"reconstruction": rc.reference.fingerprint(), "twin": rc.twin.fingerprint() if rc.twin is not None else None,
           "D": rc.D.fingerprint() if rc.D is not None else None}
    keep = ("rules_record", "gate_wires", "D_rule", "quick_ok", "fail_fast", "excluded")
    rec = {"task": "T0317", "script": "research/o003/e008_dev/gen2_0_prep.py", "quick_ok_draws": draws,
           "fingerprints": fps, "stored_rows_fingerprints": stored,
           "smoke_rows_match": all(stored.get(k) == fps[k] for k in ("twin", "reconstruction")) and len(stored) == 2,
           "info": {k: rc.info.get(k) for k in keep}, "D_l1_ratio_over_twin": (rc.d_rec or {}).get("l1_ratio"),
           "wall_s": time.perf_counter() - t0,
           "runner_sha256": hashlib.sha256((ROOT / "experiments/runners/e008_run.py").read_bytes()).hexdigest(),
           "run_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
    doc["meta"]["per_reference"][RID]["prep"] = rec
    ROWS.write_text(json.dumps(doc, indent=1, default=lambda o: o if not hasattr(o, "__dict__") else str(o)))
    print(json.dumps(rec, default=str))
    return 0 if rec["smoke_rows_match"] else 1


if __name__ == "__main__":
    sys.exit(main())
