"""RESEARCH ONLY, NOT EVIDENCE (T0388 attempt 2).  Counter-tests showing that E004's registration checks can fail.

Development geometry only (O004 F2, D0024 item 5): 2D_Case_4 and gen2_0, development seeds, L1 only.  Nothing is drawn
and no inductance is computed on 2D_Case_2R or 2D_Case_6.  Each case perturbs one input of a check and asserts that the
check reports a failure; the unperturbed input must pass.  Run:

    uv run python research/o004_e004/check_registration_checks.py
"""
from __future__ import annotations

import copy
import dataclasses
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sp = importlib.util.spec_from_file_location("e004_run", ROOT / "experiments" / "runners" / "e004_run.py")
E = importlib.util.module_from_spec(sp)
sys.modules["e004_run"] = E
sp.loader.exec_module(E)

import yaml  # noqa: E402

from moduleforge.generate import perturb as P  # noqa: E402

CFG = yaml.safe_load(E.SPEC_DRAFT.read_text())["config"]
results: list[tuple[str, bool, str]] = []


def case(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, bool(ok), detail))


# 1. freeze: unchanged passes; a dropped file, an altered hash, an unrelated pinned commit, a wrong scipy pin all fail
base = E.freeze_record(CFG)["failures"]
case("freeze: frozen config passes", not base, json.dumps(base))
c = copy.deepcopy(CFG)
c["freeze"]["files"].pop("src/moduleforge/physics/peec/kernels.py")
f = E.freeze_record(c)["failures"]
case("freeze: kernels.py left out is flagged as loaded but not frozen", any("kernels.py is loaded" in x for x in f), f[0])
c = copy.deepcopy(CFG)
c["freeze"]["files"]["src/moduleforge/geometry/conductors.py"] = "0" * 64
f = E.freeze_record(c)["failures"]
case("freeze: an altered conductors.py hash fails (live and at the pinned commit)",
     sum("conductors.py" in x for x in f) == 2, "; ".join(f))
c = copy.deepcopy(CFG)
c["freeze"]["commit"] = "aea691831d6df248a052961e1ad85e7d63bc07c8"  # attempt 1's pin: an ancestor, same src blobs
f = E.freeze_record(c)["failures"]
case("freeze: an older ancestor with identical src blobs passes (the blob check is about content)", not f, json.dumps(f))
c = copy.deepcopy(CFG)
c["freeze"]["commit"] = "38744b25"  # T0386's merge: perturb.py differs from the frozen one
f = E.freeze_record(c)["failures"]
case("freeze: a pinned commit whose blobs differ fails", any("at the pinned commit" in x for x in f), "; ".join(f[:2]))
c = copy.deepcopy(CFG)
c["freeze"]["packages"]["scipy"] = "0.0.0"
f = E.freeze_record(c)["failures"]
case("freeze: a wrong scipy pin fails", any(x.startswith("packages") for x in f), "; ".join(f))

# 2. seed provenance: a replay from the drawing seed reproduces; a replay from another seed does not
ref, rules = E.case4_reference()
slots = [("dev0", ref, rules), ("dev1", ref, rules)]
drawn = {rid: P.draw(lay, CFG["allocation"], E.reference_seed(E.DEV_SEED, k), r) for k, (rid, lay, r) in enumerate(slots)}
case("seed: replay from the drawing seed matches", not E.replay_mismatches(slots, CFG["allocation"], E.DEV_SEED, drawn))
m = E.replay_mismatches(slots, CFG["allocation"], E.DEV_SEED + 1, drawn)
case("seed: replay from a different seed is flagged on both slots", len(m) == 2, "; ".join(m))

# 3. stagewise DRC: every compound step is checked; with rules no copper meets, the steps are flagged
strict = dataclasses.replace(rules, min_trace_width=1.0, min_width_power=1.0)  # no copper meets 1 m
recs = E.pair_records("dev0", 0, ref, strict, drawn["dev0"], CFG["l1"])
comp = [p for p in recs if p["kind"] == P.COMPOUND]
case("stagewise: every compound step carries its own DRC result",
     all(len(p["steps"]) == len(p["components"]) for p in comp) and bool(comp))
chk = E.registration_checks(CFG, recs, ["dev0"], {"dev0": {"1mm": True}}, {"status": "pending"}, "dev0")
case("stagewise: strict rules make layouts_drc_clean_distinct fail", not chk["layouts_drc_clean_distinct"]["passed"],
     chk["layouts_drc_clean_distinct"]["detail"][:160])
case("stagewise: compound intermediates are flagged, not only the final layouts",
     all(any(st["drc_violations"] for st in p["steps"][:-1]) for p in comp if len(p["steps"]) > 1))

# 4. reference checks on gen2_0 (off the 1 mm lattice, not whole mm; review T0416 item 3)
from moduleforge.generate import derivative as D  # noqa: E402

gen = D.generate(D.halfbridge_housing_spec(2), 1, 20261110)[0]
lat = {f"{c / E.MM:g}mm": P.on_lattice(gen, c) for c in E.LATTICES_M}
case("references: gen2_0 is off the 1 mm lattice", not lat["1mm"], json.dumps(lat))
case("references: gen2_0 fails whole mm", bool(E.whole_mm_failures(gen)), json.dumps(E.whole_mm_failures(gen)))

# 5. the proxy record is keyed by its slot (review T0441: KeyError in smoke once built)
rec0 = dict(recs[0], pair="proxy", kind="die_row_shift")
recs_s = [dict(p, reference="2D_Case_2R<-dev:2D_Case_4") for p in recs]
chk = E.registration_checks(CFG, recs_s, ["2D_Case_2R<-dev:2D_Case_4"], {}, {"status": "built", "record": rec0},
                            "2D_Case_2R<-dev:2D_Case_4")
case("proxy: a built proxy in smoke counts toward its slot without KeyError",
     json.loads(chk["pairs_per_reference"]["detail"])["2D_Case_2R<-dev:2D_Case_4"] == len(recs_s) + 1)

# 6. L1 mesh report: synthetic values on each side of a threshold
syn = [{"pair": "a", **{f"r_L1_{k}": 0.903 for k in E.FK}, **{f"r_L1_check_{k}": 0.899 for k in E.FK}},
       {"pair": "b", **{f"r_L1_{k}": 0.95 for k in E.FK}, **{f"r_L1_check_{k}": 0.951 for k in E.FK}}]
rep = E.l1_mesh_report(syn, E.SPAN, CFG["coverage_min_effect"], CFG["l1"]["near_threshold_abs"])
case("mesh: a ratio crossing 0.90 between meshes is flagged; one far from thresholds is not",
     {f["pair"] for f in rep["flagged"]} == {"a"}, json.dumps(rep["flagged"][:1]))

w = max(len(n) for n, _, _ in results)
for n, ok, d in results:
    print(f"{'PASS' if ok else 'FAIL'}  {n:<{w}}  {d[:150]}")
print(f"{sum(ok for _, ok, _ in results)}/{len(results)} counter-tests behave as expected")
sys.exit(0 if all(ok for _, ok, _ in results) else 1)
