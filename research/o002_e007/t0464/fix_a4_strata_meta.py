"""T0464, review T0463 (4): rename dev_rows_a4_strata.json meta.reference_cpu_wall keys of T0456's 36 level-1 solves to
the *_t456jNN layout names its rows use (run_extra.py renames rows with layout.replace('_j', '_t456j') but not the solve
keys, which collided with T0398's keys in E007.dev_rows.json), and record the 36 solves. The three cal__ keys are the
stratum development layouts' P_ref calibrations (seed 20261101, pref_equal_to_T0398: true): T0398's records reused,
identical cpu/wall/DOF, not new solves. Idempotent."""
import json
import sys
from pathlib import Path

P = Path(__file__).resolve().parents[1] / "dev_rows_a4_strata.json"
d = json.loads(P.read_text())
m = d["meta"]
old = m["reference_cpu_wall"]
new = {}
for k, v in old.items():
    nk = k if (k.startswith("cal__") or "_t456j" in k) else k.replace("_j", "_t456j", 1)
    new[nk] = v
rows_layouts = {r["layout"] for r in d["rows"]}
l1 = [k for k in new if k.endswith("__L1")]
assert len(l1) == 36 and all(k.split("__")[0] in rows_layouts for k in l1), (len(l1), l1[:3])
t398 = json.loads((P.parents[2] / "experiments/drafts/E007.dev_rows.json").read_text())["meta"]["reference_cpu_wall"]
assert not set(l1) & set(t398), "keys still collide with T0398"
cal = sorted(k for k in new if k.startswith("cal__"))
assert all(new[k] == t398[k] for k in cal), "cal records differ from T0398's"
m["reference_cpu_wall"] = new
m["new_solves"] = len(l1)
m["new_solves_note"] = ("T0464 (review T0463 (4)): 36 new level-1 reference solves by T0456 (6 layouts x 3 strata x 2 loads, "
                        "seed 20261456), keys renamed to the rows' *_t456jNN names (were *_jNN, colliding with T0398's keys); "
                        "the 3 cal__ entries are T0398's P_ref calibration records reused (pref_equal_to_T0398), not new "
                        "solves. The value 0 written by run_extra.py counted only solves not already checkpointed in its "
                        "resumed work directory")
m["new_solves_cpu_s"] = round(sum(new[k]["cpu_s"] for k in l1), 3)
P.write_text(json.dumps(d, indent=1) + "\n")
print(f"renamed {len(l1)} keys; new_solves={len(l1)}; cpu_s={m['new_solves_cpu_s']}; cal reused {cal}")
sys.exit(0)
