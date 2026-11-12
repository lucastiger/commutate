"""T0316 (D0018 decision 1): the power-width floor of E008's degraded copy D, L0/L1 only.

For 2D_Case_4 (E008's own dev reference, e008_run.dev_reference) and generator housing layouts with a 2-5 mm power-width
rule, D is built by the frozen degrade() under the runner's floor rule (e008_run.d_spec: min_width_power = min(reference
minimum, floor)) for floors 1.0, 1.5 and 2.0 mm and at the reference minimum (the rule before D0018).  Per (layout, floor):
the L1 ratio degrade() reaches (or its DegradeError terminal ratio), the moves (non-walk moves, walk step count), the walk's
terminal kind, D's narrowest power strip (e008_run.narrowest_power_strip_m, the DRC's own width predicate) and the
lattice cells across it at the band solves' 0.5 mm cells and at 0.25 mm.

Generator layouts are planted at the hard case: the reference's landing bands are narrowed to its own power rule (move 1
under the reference rule, twin.py _narrow_landing), so they sit at the reference minimum as on 2D_Case_4.  Layouts:
halfbridge_housing_spec(n, DesignRules(min_width_power=w), wires_per_die=k), first layout of D.generate(seed).
Deterministic: no timing in the output except wall_s.  Usage: uv run python research/o003/e008_dev/d_floor/floor_study.py
"""
from __future__ import annotations

import importlib.util
import json
import math
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).with_name("floor_study.json")
FLOORS_MM = (1.0, 1.5, 2.0)
# (dies per switch, wires per die, power rule mm, seed): 7 generator housing layouts, rules 2-5 mm
GEN = ((2, 1, 2.0, 11), (3, 2, 2.0, 12), (2, 2, 3.0, 13), (3, 1, 3.0, 14), (2, 1, 4.0, 15), (3, 1, 4.0, 16), (2, 1, 5.0, 17))


def main() -> int:
    sp = importlib.util.spec_from_file_location("e008_run", ROOT / "experiments/runners/e008_run.py")
    R = importlib.util.module_from_spec(sp)
    sys.modules[sp.name] = R
    sp.loader.exec_module(R)
    from moduleforge.drc.rules import DesignRules, check
    from moduleforge.generate import derivative as D
    from moduleforge.generate import twin as W
    cfg = R.load_spec()["config"]
    only = sys.argv[1:]  # optional subset of layout names
    lays = []
    if not only or "2D_Case_4" in only:
        rc = R.dev_reference("case4", cfg)
        tw, _, trec = W.twin(rc.reference, rc.spec)
        lays.append(("2D_Case_4", rc.spec, tw, {"twin_mode": trec.get("mode"), "source": "e008_run.dev_reference"}))
    for n, k, w, seed in GEN:
        name = f"gen{n}x{k}_w{w:g}_s{seed}"
        if only and name not in only:
            continue
        spec = D.halfbridge_housing_spec(n, rules=DesignRules(min_width_power=w * 1e-3), wires_per_die=k)
        try:
            lay = D.generate(spec, 1, seed=seed)[0]
        except Exception as e:  # noqa: BLE001 - recorded, not hidden
            lays.append((name, None, None, {"error": f"generate: {e}"}))
            continue
        try:
            p1, widths = W._narrow_landing(D.params_of(lay), spec, centre=False)
            planted = D.build(spec, p1)
            planted = planted if not check(planted, spec.rules) else lay
        except (W.DegradeError, ValueError):
            planted, widths = lay, {}
        lays.append((name, spec, planted, {"planted_landing_widths_mm": {b: v["after_mm"] for b, v in widths.items()},
                                           "planted_is_narrowed": planted is not lay}))
    res = {}
    for name, spec, tw, meta in lays:
        rec = {"meta": meta, "floors": {}}
        res[name] = rec
        if spec is None:
            continue
        ref_w = R.d_rules(spec.rules, 1.0)[1]
        rec["reference_min_width_power_mm"] = ref_w * 1e3
        rec["reference_narrowest_power_strip_mm"] = R.narrowest_power_strip_m(tw) * 1e3
        for fl in [*FLOORS_MM, "reference"]:
            f_m = ref_w if fl == "reference" else fl * 1e-3
            dsp, _ = R.d_spec(spec, f_m)
            t0 = time.perf_counter()
            try:
                d, drec = W.degrade(tw, dsp)
                err = None
            except W.DegradeError as e:
                d, drec, err = None, getattr(e, "record", {}), str(e)[:300]
            wk = drec.get("walk") or {}
            moves = drec.get("moves", [])
            r = {"D_min_width_power_mm": dsp.rules.min_width_power * 1e3, "DegradeError": err,
                 "l1_ratio": drec.get("l1_ratio", wk.get("l1_ratio")), "target": W.DEGRADE_RATIO * (1 + W.DEGRADE_MARGIN),
                 "moves_non_walk": [m for m in moves if not m.startswith("walk[")],
                 "walk_steps": sum(m.startswith("walk[") for m in moves), "walk_terminal": wk.get("terminal"),
                 "walk_start_ratio": wk.get("start_l1_ratio"), "skipped": drec.get("skipped", []),
                 "stopped": drec.get("stopped", []), "wall_s": round(time.perf_counter() - t0, 1)}
            if d is not None:
                wn = R.narrowest_power_strip_m(d)
                r.update(narrowest_power_strip_mm=wn * 1e3, cells_across_0p5mm=wn / 0.5e-3, cells_across_0p25mm=wn / 0.25e-3,
                         drc_clean_under_D_rules=not check(d, dsp.rules),
                         rules_violated_under_reference_rules=sorted({v.rule for v in check(d, spec.rules)}),
                         landing_widths_mm={b: v["after_mm"] for b, v in drec.get("widths", {}).items()})
            rec["floors"][str(fl)] = r
            print(f"{name} floor {fl}: ratio {r['l1_ratio']} err {bool(err)} walk {r['walk_steps']} {r['walk_terminal']} "
                  f"narrowest {r.get('narrowest_power_strip_mm')} ({r['wall_s']} s)", flush=True)
            OUT.write_text(json.dumps(res, indent=1, default=str))
    OUT.write_text(json.dumps(res, indent=1, default=str))
    return 0 if all(math.isfinite(v["floors"][f]["l1_ratio"] or math.nan) for v in res.values() for f in v["floors"]) else 1


if __name__ == "__main__":
    sys.exit(main())
