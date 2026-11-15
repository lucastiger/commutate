"""T0349: is the twin W's copper (not its parameter vector) reachable by derivative._sample?  Builds W re-expressed
with every slot attached to its column's edge as _sample constructs it (DC+/DC- columns from u 7.5 mm, the lowest
_sample can draw for a pad at u 9 mm: pad u0 - 1.5), and a variant with the PHASE column's outer edge at 45.5 mm (the
largest value drawn in the 40 000 run candidates).  Reports L1 (twin._l1, as e010_run.l1_of), DRC and copper area per
net against W.  Usage: uv run python research/diagnoses/T0349/attached_twin.py OUT.json"""
import json
import pickle
import sys
from pathlib import Path

from moduleforge.drc.rules import check
from moduleforge.generate import derivative as D
from moduleforge.generate import twin as T

ctx = pickle.load(open("experiments/results/E010/E010-20261114T202413-80c1/work/2D_Case_2R/ctx.pkl", "rb"))
spec, W = ctx["spec"], ctx["twin"]
w = D.params_of(W).to_vector()


def variant(phase_u1):
    v = w.copy()
    v[4:8] = [7.5, 37, 12, 45]  # DC+ column
    v[24:28] = [12, 37, 33, 45]  # slot2 (DC+ die)
    v[8:12] = [7.5, 7, 12, 13]  # DC- column
    v[16:20] = [12, 7, 47, 13]  # slot0 (DC- land)
    v[12:16] = [37, 15, phase_u1, 51]                                 # PHASE column covers both PHASE slots
    v[20:24] = [7, 15, 37, 23]  # slot1 (PHASE die)
    v[28:32] = [7, 47, 37, 51]  # slot3 (PHASE land)
    return v


def copper(lay):
    from shapely.ops import unary_union
    out = {}
    for n in ("DC+", "DC-", "PHASE"):
        polys = [t.polygon for t in lay.traces if getattr(t, "net", None) == n]
        out[n] = unary_union(polys) if polys else None
    return out


res = {"W": {"l1_H": T._l1(W)}}
cw = copper(W)
for name, u1 in (("attached_phase47", 47.0), ("attached_phase45p5", 45.5)):
    r = {}
    try:
        lay = D.build(spec, D.Params.from_vector(variant(u1)))
        r["drc_violations"] = [str(x) for x in check(lay, spec.rules)][:8]
        r["quick_ok"] = bool(D._quick_ok(spec, D._Ctx(spec), lay))
        r["l1_H"] = T._l1(lay)
        r["l1_over_W"] = r["l1_H"] / res["W"]["l1_H"]
        c = copper(lay)
        r["symdiff_mm2"] = {n: (c[n].symmetric_difference(cw[n]).area * 1e6 if c[n] is not None else None) for n in c}
    except Exception as e:  # report, do not hide
        r["error"] = f"{type(e).__name__}: {e}"
    res[name] = r
Path(sys.argv[1]).write_text(json.dumps(res, indent=1))
print(json.dumps(res, indent=1))
