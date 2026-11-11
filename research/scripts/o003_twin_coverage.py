"""T0314 (O003): twin and degradation coverage of 2D_Case_2R, 2D_Case_6 and 2D_Case_4 -- which rule binds (L0/L1 only).

Diagnosis and prototypes only.  No frozen code is edited: twin(), degrade() and the DRC are called from ``src`` as frozen
(E008 freeze hashes); the only runtime wrapper is around ``twin._walk``, to record the walk's terminal Params (the
DegradeError record does not carry them).  No l2_layout, thermal or FastHenry solve and no search; generator calls happen
only inside twin(), degrade() and the prototype walk below.  L1 = physics.peec at 20 MHz (twin._l1).

Layouts (built only from the repository):
* 2D_Case_2R, 2D_Case_6: research/scripts/o003_powersynth_references.py (``snapped``), spec as E008 builds it:
  spec_from_layout(reconstruction, measure_rules(reconstruction)[0], KEEPOUT_NETS).
* 2D_Case_4: E008's own dev construction, experiments/runners/e008_run.py ``dev_reference('case4', cfg)`` (measure_rules
  plus the E008.yaml dev overrides: pitch defaults, max_wire_length 18 mm, assumed gate / Kelvin pads, 25 mm signal limit).

Variants of the rules (packet item 1):
* R0  the construction above.
* R1  R0 without ``min_signal_wire_length``.
* R2  skipped: no citable physical minimum gate-wire length was found (note section 1).
* R3:<field>  diagnostic: one measured field of R0 relaxed to its effective DRC default (``EFFECTIVE_DEFAULT``).  When the
  relaxed rules give the same effective rules as a variant already run (``effective_signature``), its result is reused.
* X:max_wire_length  diagnostic outside R3 (Case 4 only): the power-wire length cap lifted to 1 m.

Prototypes (item 2), all checked DRC-clean under R0 of the same layout:
* P1  continue from the frozen walk's terminal state with an extended candidate set: the walk's single +-0.5 mm steps,
  single-parameter jumps of +-1.0 ... +-5.0 mm, and rigid slot moves (one slot with the row / landing line it carries).
* P2  the same extended walk, started from the frozen walk's start state (after moves 1-3).

Output: ``--out`` JSON with floats rounded to 10 significant digits and no timings, so a re-run is byte-identical.
"""
from __future__ import annotations

import argparse
import collections
import dataclasses
import importlib.util
import itertools
import json
import math
import re
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
LAYOUTS = ("2D_Case_2R", "2D_Case_6", "2D_Case_4")
MM = 1e-3
SIG_DIGITS = 10
R2_NOTE = ("skipped: no citable physical minimum gate-wire length for 0.30 mm Al wedge bonds was found (one web search; "
           "the Tyndall design-rule PDF returned 404); DesignRules.min_wire_length 1.5 mm is a placeholder, not a source")
P_JUMP_MAX_MM = 5.0
P_MAX_STEPS = 80


def _load(name: str, rel: str):
    sp = importlib.util.spec_from_file_location(name, ROOT / rel)
    m = importlib.util.module_from_spec(sp)
    sys.modules[name] = m
    sp.loader.exec_module(m)
    return m


R = _load("e008_run_t0314", "experiments/runners/e008_run.py")
PS = _load("o003_powersynth_references_t0314", "research/scripts/o003_powersynth_references.py")

from moduleforge.drc.rules import DesignRules, check, measure_rules  # noqa: E402
from moduleforge.generate import derivative as D  # noqa: E402
from moduleforge.generate import twin as W  # noqa: E402
from moduleforge.geometry import NETS  # noqa: E402

TARGET = W.DEGRADE_RATIO * (1.0 + W.DEGRADE_MARGIN)
_DFLT = DesignRules()
# the value DEFAULT_RULES applies to each measured field (per-class None fields fall back to min_spacing / min_trace_width)
EFFECTIVE_DEFAULT = {f.name: getattr(_DFLT, f.name) for f in dataclasses.fields(DesignRules)}
EFFECTIVE_DEFAULT.update({k: _DFLT.min_spacing for k in EFFECTIVE_DEFAULT if k.startswith("spacing_")})
EFFECTIVE_DEFAULT.update(min_width_power=_DFLT.min_trace_width, min_width_other=_DFLT.min_trace_width)
# the DesignRules fields measure_rules sets (drc/rules.py measure_rules, the DesignRules(...) call)
MEASURED_FIELDS = ("min_trace_width", "min_spacing", "edge_margin", "die_edge_margin", "die_spacing", "min_wire_pitch",
                   "wire_pitch_diameters", "spacing_dcp_phase", "spacing_phase_dcm", "spacing_dcp_dcm", "spacing_other",
                   "spacing_signal_dcp", "spacing_signal_phase", "spacing_signal_dcm", "spacing_signal_source",
                   "spacing_signal_hs_ls", "min_signal_wire_diameter", "max_signal_wire_diameter",
                   "min_signal_wire_length", "max_signal_wire_length", "min_width_power", "min_width_other",
                   "max_gate_wire_length", "max_kelvin_wire_length")


# ------------------------------------------------------------------------------------------------------------ helpers
def _j(o):
    """JSON-safe, deterministic: floats to SIG_DIGITS significant digits, tuples to lists, numpy to python."""
    if isinstance(o, dict):
        return {str(k): _j(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_j(v) for v in o]
    if isinstance(o, (np.floating, float)):
        x = float(o)
        return x if not math.isfinite(x) else float(f"{x:.{SIG_DIGITS}g}")
    if isinstance(o, np.integer):
        return int(o)
    return o


def _rules_of(text: str) -> list[str]:
    return sorted(set(re.findall(r"rule='(\w+)'", text)))


def _compress(moves: list[str]) -> list[str]:
    return [f"{m} x{n}" if n > 1 else m for m, n in ((k, len(list(g))) for k, g in itertools.groupby(moves))]


def effective_signature(spec: D.ReferenceSpec, rules: DesignRules) -> tuple:
    """Everything the DRC reads from ``rules`` for the nets of ``spec`` (per-class fall-backs resolved)."""
    nets = sorted(set(NETS) | {t.net for t in spec.keepouts})
    sig = [("width", n, rules.width_for(n)) for n in nets]
    sig += [("spacing", a, b, rules.spacing_for(a, b)) for a, b in itertools.combinations(nets, 2)]
    sig += [("spacing_self", n, rules.spacing_for(n, n)) for n in nets]
    sig += [("sig_len", p, rules.signal_length_range(p)) for p in ("gate", "kelvin")]
    sig += [("sig_d", rules.signal_diameter_range())]
    skip = {"min_trace_width", "min_spacing", "min_width_power", "min_width_other", "min_signal_wire_length",
            "max_signal_wire_length", "max_gate_wire_length", "max_kelvin_wire_length", "min_signal_wire_diameter",
            "max_signal_wire_diameter"} | {k for k in EFFECTIVE_DEFAULT if k.startswith("spacing_")}
    sig += [(f.name, getattr(rules, f.name)) for f in dataclasses.fields(DesignRules) if f.name not in skip]
    return tuple(sig)


# --------------------------------------------------------------------------------------------------- layouts and rules
def build_layouts() -> dict:
    """{name: (reconstruction, spec_R0, construction text)} built exactly as E008 builds them."""
    out = {}
    for ref in ("2D_Case_2R", "2D_Case_6"):
        lay, _ = PS.snapped(ref)
        spec = D.spec_from_layout(lay, measure_rules(lay)[0], PS.KEEPOUT_NETS[ref])
        out[ref] = (lay, spec, "spec_from_layout(snapped reconstruction, measure_rules(...)[0], KEEPOUT_NETS)")
    cfg = R.load_spec()["config"]
    rc = R.dev_reference("case4", cfg)
    out["2D_Case_4"] = (rc.reference, rc.spec, "e008_run.dev_reference('case4', E008.yaml config): measure_rules + dev "
                                               "rule_overrides, assumed gate/Kelvin pads, 25 mm signal limit")
    return out


def variants(name: str, spec: D.ReferenceSpec) -> list[tuple[str, DesignRules, dict]]:
    r0 = spec.rules
    out = [("R0", r0, {}), ("R1", dataclasses.replace(r0, min_signal_wire_length=None),
                            {"min_signal_wire_length": [r0.min_signal_wire_length, None]})]
    for f in MEASURED_FIELDS:
        cur, dflt = getattr(r0, f), EFFECTIVE_DEFAULT[f]
        if cur != dflt:
            out.append((f"R3:{f}", dataclasses.replace(r0, **{f: dflt}), {f: [cur, dflt]}))
    if name == "2D_Case_4":
        out.append(("X:max_wire_length", dataclasses.replace(r0, max_wire_length=1.0),
                    {"max_wire_length": [r0.max_wire_length, 1.0]}))
    return out


# ------------------------------------------------------------------------------------------------- walk instrumentation
_LAST_WALK: dict = {}
_FROZEN_WALK = W._walk


def _walk_capture(spec, p, lay, l_tw, target):
    _LAST_WALK.clear()
    _LAST_WALK["start"] = p
    res = _FROZEN_WALK(spec, p, lay, l_tw, target)
    _LAST_WALK["terminal"] = res[0]
    return res


W._walk = _walk_capture  # runtime wrapper only (records Params); the frozen function does the work


def walk_blockers(spec: D.ReferenceSpec, p: D.Params, l_tw: float) -> dict:
    """Every single-parameter walk candidate at ``p``: DRC rule(s) that reject it, or clean and L1 up / down."""
    cur = W._l1(D.build(spec, p))
    counts, per = collections.Counter(), []
    for name, d, q in W._walk_candidates(p):
        try:
            lay = D.build(spec, q)
        except ValueError as e:
            counts["build_error"] += 1
            per.append([name, d, "build_error: " + str(e)[:80]])
            continue
        v = check(lay, spec.rules)
        if v:
            kinds = "+".join(sorted({x.rule for x in v}))
            counts[kinds] += 1
            per.append([name, d, kinds])
        else:
            li = W._l1(lay)
            k = "clean_up" if li > cur * (1 + 1e-12) else "clean_not_up"
            counts[k] += 1
            per.append([name, d, f"{k} {li / l_tw:.4f}"])
    rule_counts = collections.Counter()
    for k, n in counts.items():
        for r in k.split("+"):
            rule_counts[r] += n
    return {"ratio": cur / l_tw, "n_candidates": len(per), "outcomes": dict(sorted(counts.items())),
            "per_rule": dict(sorted(rule_counts.items())), "candidates": per}


# ---------------------------------------------------------------------------------------------------------- variant run
def run_variant(lay, spec: D.ReferenceSpec, with_blockers: bool) -> tuple[dict, D.Params | None, object]:
    out = {}
    try:
        tw, p, tr = W.twin(lay, spec)
    except W.TwinError as e:
        msg = str(e)
        out["twin_mode"] = None
        out["error"] = "TwinError: " + msg
        out["error_rules"] = _rules_of(msg)
        return out, None, None
    area = tr["copper_area_mm2"]
    out["twin_mode"] = tr["mode"]
    out["topology"] = tr["topology"]
    out["difference_record"] = {k: tr[k] for k in ("symdiff_area_mm2", "symdiff_area_total_mm2", "copper_area_mm2",
                                                   "die_centre_displacement_mm", "max_die_displacement_mm",
                                                   "max_wire_displacement_mm")}
    out["symdiff_per_net"] = {n: {"mm2": tr["symdiff_area_mm2"][n], "fraction": tr["symdiff_area_mm2"][n]
                                  / area[n]["reference"]} for n in NETS}
    out["l1_reference_nH"] = tr["l1_reference_H"] * 1e9
    out["l1_twin_nH"] = tr["l1_twin_H"] * 1e9
    out["l1_W_over_ref"] = tr["l1_twin_H"] / tr["l1_reference_H"]
    out["twin_signal_wire_lengths_mm"] = [w.length / MM for w in tw.signal_wires]
    _LAST_WALK.clear()
    try:
        _, dr = W.degrade(tw, spec)
        out["error"] = None
    except W.DegradeError as e:
        dr = e.record
        out["error"] = "DegradeError: " + str(e)
    wk = dr.get("walk")
    out["degrade"] = {
        "moves": _compress(dr.get("moves", [])), "n_walk_steps": len(wk["steps"]) if wk else 0,
        "skipped": [{"move": s.split(":")[0], "rules": _rules_of(s) or [s.split(": ", 1)[1][:60]]}
                    for s in dr.get("skipped", [])],
        "stopped": [{"move": s.split(":")[0], "rules": _rules_of(s)} for s in dr.get("stopped", [])],
        "widths": dr.get("widths_by_move", {}),
        "walk_start_ratio": wk["start_l1_ratio"] if wk else None, "walk_terminal": wk["terminal"] if wk else None,
        "l1_D_over_W": wk["l1_ratio"] if wk else dr.get("l1_ratio"), "target": TARGET,
        "reaches_target": out["error"] is None}
    term = _LAST_WALK.get("terminal")
    if with_blockers and out["error"] and term is not None:
        out["degrade"]["walk_terminal_blockers"] = walk_blockers(spec, term, tr["l1_twin_H"])
    return out, p, (tw, tr["l1_twin_H"], dict(_LAST_WALK))


# ----------------------------------------------------------------------------------------------------- item 2 prototype
def _rigid(p: D.Params):
    for i, (_, role, sw) in enumerate(p.sequence()):
        for d in (-W.WALK_STEP_MM, W.WALK_STEP_MM):
            s, rows, land = [list(x) for x in p.slots], [list(r) for r in p.rows], list(p.land)
            s[i][1] += d
            s[i][3] += d
            if role == "die":
                rows[0 if sw == "HS" else 1][1] += d
            else:
                land[0 if sw == "HS" else 1] += d
            yield f"rigid_slot{i}", d, W._replace_slots(p, s, rows=tuple(map(tuple, rows)), land=tuple(land))


def _extended(p: D.Params):
    vec = p.to_vector()
    kmax = int(P_JUMP_MAX_MM / W.WALK_STEP_MM + 1e-9)
    for i in range(W.WALK_FIRST, W.WALK_END):
        for k in range(1, kmax + 1):
            for sg in (-1, 1):
                v = vec.copy()
                v[i] += sg * k * W.WALK_STEP_MM
                q = D.Params.from_vector(v)
                if any(c[0] >= c[2] - 1e-9 or c[1] >= c[3] - 1e-9 for c in q.cols + q.slots):
                    continue
                yield D.Params.NAMES[i], sg * k * W.WALK_STEP_MM, q
    yield from _rigid(p)


def prototype_walk(spec: D.ReferenceSpec, rules0: DesignRules, p: D.Params, l_tw: float) -> dict:
    """Greedy best-L1 walk over ``_extended`` candidates (DRC-clean under ``spec.rules``) until TARGET, a local maximum
    or P_MAX_STEPS.  Ties: the first candidate in the fixed order."""
    lay = D.build(spec, p)
    cur = W._l1(lay)
    start, steps, kind = cur / l_tw, [], "step_limit"
    for _ in range(P_MAX_STEPS):
        if cur / l_tw >= TARGET:
            kind = "target_reached"
            break
        best = None
        for name, d, q in _extended(p):
            cl, _ = W._try(spec, q)
            if cl is None:
                continue
            li = W._l1(cl)
            if li > cur * (1 + 1e-12) and (best is None or li > best[0]):
                best = (li, name, d, q, cl)
        if best is None:
            kind = "local_maximum"
            break
        cur, name, d, p, lay = best
        steps.append(f"{name}{d:+g}mm")
    else:
        kind = "target_reached" if cur / l_tw >= TARGET else "step_limit"
    clean_r0 = not check(lay, rules0)
    return {"start_ratio": start, "ratio": cur / l_tw, "terminal": kind, "n_steps": len(steps),
            "steps": _compress(steps), "drc_clean_under_R0": clean_r0, "reaches_target": cur / l_tw >= TARGET,
            "terminal_params": p.to_vector().tolist()}


# ----------------------------------------------------------------------------------------------------- item 3 (Case 6)
def candidate_filter_trace(lay, spec: D.ReferenceSpec) -> dict:
    """twin.py's candidate filter, step by step, for each (orientation, sequence): why the pair is kept or not."""
    out = {}
    for o in (0, 1):
        rows = W._rows_of(lay, spec, o)
        if rows is None:
            fr = D._Frame(o)
            vs = {sw: sorted(round(W._loc(fr, d.cx / MM, d.cy / MM)[1], 3) for d in lay.dies if d.switch == sw)
                  for sw in ("HS", "LS")}
            out[f"orient{o}"] = {"rows": None, "reason": "_rows_of: die centres of a switch differ in v by > 0.3 mm",
                                 "die_centre_v_mm": vs}
            continue
        feet, land, landu = W._feet_of(lay, spec, o, rows)
        sig = W._sigfeet_of(lay, spec, o)
        du, dv = (x / MM for x in D._Frame(o).size(spec.die.w, spec.die.h))
        rec = {"rows": rows, "landing_line_v_mm": land, "landing_mean_u_mm": landu, "pairs": {}}
        for hf, hdf, ldf in itertools.product((0, 1), repeat=3):
            seq = D._sequence(hf, hdf, ldf)
            anchors = []
            for net, role, sw in seq:
                u0, v0, _ = rows[sw]
                anchors.append([f"{sw}_{role}({net})", v0 + dv / 2 if role == "die" else land[sw]])
            bad = [i for i in range(3) if anchors[i][1] > anchors[i + 1][1] + 1e-9]
            p = W._fit(lay, spec, o, hf, hdf, ldf, rows, feet, land, sig, landu)
            why = (f"v-order violated between slot {bad[0]} and {bad[0] + 1}" if bad
                   else ("kept" if p is not None else "probe line / chord / column test failed"))
            rec["pairs"][f"hs_first={hf},hs_die_first={hdf},ls_die_first={ldf}"] = {
                "slot_anchor_v_mm": anchors, "kept": p is not None, "reason": why}
        out[f"orient{o}"] = rec
    return out


# ----------------------------------------------------------------------------------------------------- item 4 facts
def checklist_facts(lay, spec: D.ReferenceSpec) -> dict:
    from shapely.geometry import Point
    from shapely.ops import unary_union
    rows_any = [o for o in (0, 1) if W._rows_of(lay, spec, o) is not None]
    per_die = collections.Counter()
    for w in lay.wires:
        for k, d in enumerate(lay.dies):
            x0, y0, x1, y1 = d.pads["source"]
            if x0 - 1e-9 <= w.points[0, 0] <= x1 + 1e-9 and y0 - 1e-9 <= w.points[0, 1] <= y1 + 1e-9:
                per_die[k] += 1
    pw = {n: unary_union([t.polygon for t in lay.traces if t.net == n]) for n in NETS}
    gate_excess = []
    for w in lay.signal_wires:
        cu = unary_union([t.polygon for t in lay.traces if t.net == w.net])
        gate_excess.append(Point(w.points[-1, 0], w.points[-1, 1]).distance(Point(w.points[0, 0], w.points[0, 1]))
                           / MM - Point(w.points[0, 0], w.points[0, 1]).distance(cu) / MM)
    return {
        "n_dies": len(lay.dies), "dies_per_switch": lay.dies_per_switch, "identical_dies": True,
        "die_rows_collinear_in_orientation": rows_any,
        "power_wires_per_die": sorted(set(per_die.values())),
        "islands_per_power_net": {n: len(getattr(g, "geoms", [g])) for n, g in pw.items()},
        "holes_per_power_net": {n: sum(len(x.interiors) for x in getattr(g, "geoms", [g])) for n, g in pw.items()},
        "terminals": sorted(lay.terminals), "n_signal_wires": len(lay.signal_wires),
        "kelvin_pads": "kelvin" in spec.die.pads, "keepout_nets": sorted({t.net for t in spec.keepouts}),
        "signal_wire_plan_excess_over_nearest_copper_mm": gate_excess,
    }


# ----------------------------------------------------------------------------------------------------------------- main
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", required=True)
    ap.add_argument("--layouts", default=",".join(LAYOUTS))
    a = ap.parse_args()
    lays = build_layouts()
    res = {"task": "T0314", "target_l1_ratio": TARGET, "degrade_ratio": W.DEGRADE_RATIO, "margin": W.DEGRADE_MARGIN,
           "R2": R2_NOTE, "effective_default": {k: EFFECTIVE_DEFAULT[k] for k in MEASURED_FIELDS}, "layouts": {}}
    for name in a.layouts.split(","):
        lay, spec, how = lays[name]
        print(f"[{name}]", file=sys.stderr, flush=True)
        L = {"construction": how, "reconstruction_fingerprint": lay.fingerprint(),
             "rules_R0": {f.name: getattr(spec.rules, f.name) for f in dataclasses.fields(DesignRules)},
             "checklist_facts": checklist_facts(lay, spec), "variants": {}}
        seen: dict[tuple, str] = {}
        ctx = {}
        for vname, rules, changed in variants(name, spec):
            sv = dataclasses.replace(spec, rules=rules)
            key = effective_signature(sv, rules)
            if key in seen:
                L["variants"][vname] = {"changed": changed, "same_effective_rules_as": seen[key]}
                continue
            seen[key] = vname
            print(f"  {vname}", file=sys.stderr, flush=True)
            out, p, c = run_variant(lay, sv, with_blockers=vname in ("R0", "R1"))
            L["variants"][vname] = {"changed": changed, **out}
            if c is not None:
                ctx[vname] = (sv, c)
        L["variants"]["R2"] = {"skipped": R2_NOTE}
        # item 2: prototypes on the first variant whose twin builds and whose D misses the target (R0, else R1)
        for vname in ("R0", "R1"):
            v = L["variants"].get(vname, {})
            if vname in ctx and v.get("error", "").startswith("DegradeError") if v.get("error") else False:
                sv, (tw, l_tw, walk) = ctx[vname]
                print(f"  prototypes on {vname}", file=sys.stderr, flush=True)
                L["prototypes"] = {"base_variant": vname,
                                   "P1_extended_walk_from_frozen_terminal": prototype_walk(sv, sv.rules,
                                                                                           walk["terminal"], l_tw),
                                   "P2_extended_walk_from_walk_start": prototype_walk(sv, sv.rules, walk["start"], l_tw)}
                break
        if name == "2D_Case_6":
            L["candidate_filter_trace"] = candidate_filter_trace(lay, spec)
        res["layouts"][name] = L
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(_j(res), indent=1, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
