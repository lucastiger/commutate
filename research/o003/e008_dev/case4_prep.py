"""T0262 attempt 5: 2D_Case_4's L0/L1 pre-registration record (no l2_layout or thermal solve) merged into the dev rows.

Why: Case 4's twin gates need its thk_f band solve (0.5 mm, 20/12/12 layers), measured at 8.1 GB on this Mac by P3
(research/notes/o006-p3-em-convergence.md line 130). That is above the agent's 5 GB budget, and the larger-process
exception needs swap < 4 GB, which the sandbox cannot read (sysctl vm.swapusage is denied). So the gates stay with the
full-fidelity dev run (research/o003/e008_dev/burst_dev.sh). What runs here is the runner's own fail-fast path
(e008_run.prepare: twin W, degraded copy D, _quick_ok sample, rule strictness, midpoint record, twin-copper symdiff) on
development geometry only, with the registered quick_ok_draws (2,000) rather than the smoke 100, which drew no DRC-clean
sample on Case 4 (attempt 1). Seeds: the dev seed, purpose 2, geometry index 1 (config.dev.geometries order).

T0316 (D0018): D is built under the runner's power-width floor (config.degrade_power_width_floor_m); the record carries
D's rule, its narrowest power strip, its L1 ratio and moves, any exclusion, and the runner's sha256.

Usage: uv run python research/o003/e008_dev/case4_prep.py [--draws N]
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--draws", type=int, default=None)
    ap.add_argument("--rows", default=str(ROOT / "experiments/drafts/E008.dev_rows.json"))
    a = ap.parse_args()
    sp = importlib.util.spec_from_file_location("e008_run", ROOT / "experiments/runners/e008_run.py")
    R = importlib.util.module_from_spec(sp)
    sys.modules[sp.name] = R
    sp.loader.exec_module(R)
    cfg = R.load_spec()["config"]
    draws = a.draws or int(cfg["quick_ok_draws"])
    i = cfg["dev"]["geometries"].index("case4")
    t0 = time.perf_counter()
    rc = R.dev_reference("case4", cfg)
    rc = R.prepare(rc, cfg, draws, R.derive_seed(int(cfg["dev"]["dev_seed"]), 2, i))
    wall = time.perf_counter() - t0
    scal = {k: v for k, v in (rc.twin_rec or {}).items() if isinstance(v, (int, float, str, bool))}
    l1 = {}
    for name, lay in (("reconstruction", rc.reference), ("twin", rc.twin), ("D", rc.D)):
        l1[name] = R.l1_of(lay) if lay is not None else None
    rec = {"prep_only": True,
           "twin_gates": "PENDING: needs the 0.5 mm thk_f band solve (8.1 GB on this Mac, P3); full-fidelity dev run "
                         "research/o003/e008_dev/burst_dev.sh decides F1(a1)/(a2) on Case 4",
           "twin_mode": (rc.twin_rec or {}).get("mode"), "twin_record_scalars": scal,
           "fingerprints": {"reconstruction": rc.reference.fingerprint(),
                            "twin": rc.twin.fingerprint() if rc.twin is not None else None,
                            "D": rc.D.fingerprint() if rc.D is not None else None},
           "L1_H": l1,
           "L1_ratio_twin_over_reconstruction": (l1["twin"] / l1["reconstruction"]) if l1["twin"] else None,
           "info": rc.info, "quick_ok_draws": draws, "wall_s": wall,
           "D_l1_ratio_over_twin": (rc.d_rec or {}).get("l1_ratio"), "D_target_l1_ratio": (rc.d_rec or {}).get("target_l1_ratio"),
           "D_moves": (rc.d_rec or {}).get("moves"), "D_landing_widths": (rc.d_rec or {}).get("widths"),
           "excluded": rc.excluded, "D_rule": rc.info.get("D_rule"),
           "runner_sha256": hashlib.sha256((ROOT / "experiments/runners/e008_run.py").read_bytes()).hexdigest(),
           "script": "research/o003/e008_dev/case4_prep.py", "run_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
    p = Path(a.rows)
    doc = json.loads(p.read_text())
    m = doc["meta"]
    m.setdefault("per_reference", {})["2D_Case_4"] = rec
    m.setdefault("fail_fast", {}).pop("2D_Case_4", None)  # T0316: the earlier DegradeError entry is replaced, not kept
    if rc.info.get("fail_fast"):
        m["fail_fast"]["2D_Case_4"] = rc.info["fail_fast"]
    m["merged"] = [x for x in m.get("merged", []) if x.get("reference_id") != "2D_Case_4"] + [
        {"reference_id": "2D_Case_4", "by": rec["script"], "what": "L0/L1 fail-fast record only; no rows added"}]
    p.write_text(json.dumps(doc, indent=1, default=lambda o: o if not hasattr(o, "__dict__") else str(o),
                            allow_nan=True))
    q = rc.info.get("quick_ok", {})
    print(f"D0018: D rule {json.dumps(rc.info.get('D_rule'), default=str)}; D L1/W L1 {rec['D_l1_ratio_over_twin']} moves "
          f"{rec['D_moves']} excluded {rc.excluded}")
    print(f"2D_Case_4: twin {rec['twin_mode']} L1 W/R {rec['L1_ratio_twin_over_reconstruction']} fail_fast "
          f"{str(rc.info.get('fail_fast'))[:160]} walk_steps {len(rc.info.get('walk') or [])} quick_ok {q} "
          f"midpoint {rc.info.get('midpoint_decided_splits')} wall {wall:.0f} s")
    flags = {k: v for k, v in rc.info.get("rule_strictness", {}).items() if v.get("flag_2x")}
    print("rule strictness flags (>2x the smallest DC-link gap):", flags or "none")
    print("twin copper:", json.dumps(rc.info.get("twin_copper"), default=str)[:600])
    return 0 if math.isfinite(wall) else 1


if __name__ == "__main__":
    sys.exit(main())
