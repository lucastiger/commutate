"""O008 draft, pre-approval development probe (founder session, 2026-11-15; reviews T0352 and T0354). L1 only, development
geometry only (2D_Case_2R and 2D_Case_4 are development geometry under D0023), development seeds only.

Two questions, under the reference's own measured rules (spec.rules, the rules the search runs under; no relaxed floor):
  Q1  Can a degradation that is DRC-clean under those rules reach L1(D) / L1(W) >= 1.25 (and the frozen L1 target
      1.25 x 1.11 = 1.3875)?  (a) the frozen twin.degrade; (b) a randomised family: a stochastic L1 ascent from W by
      joint moves of 2-4 copper parameters, 0.5-2 mm each.
  Q2  From each degraded start D_j, how close to W do three searches get, all over twin._walk_candidates (single copper
      parameter, +-0.5 mm, DRC-clean under spec.rules), steepest step, at most MAX_STEPS steps:
        guided   minimise L1 (a stand-in for the seeded local search);
        compact  null (d) of review T0354, inductance-blind: maximise power copper area minus power-wire length
                 (m^2 per mm^2 against mm of wire, see score()), a step only if it does not lose copper or lengthen wires;
        widen    null (b), inductance-blind: maximise power copper area only.
      Shortfall s = L1(result) / L1(W) - 1.

Usage: uv run python research/o008_probe/probe.py {2R|Case4} OUT.json [draws] [proxy]
  proxy: first optimise the twin by a long L1-guided descent (PROXY_STEPS) and use that layout W* in place of W
"""
import json
import pickle
import sys
import time

import numpy as np
from shapely.ops import unary_union

from moduleforge.drc.rules import check
from moduleforge.generate import derivative as D
from moduleforge.generate import twin as T
from moduleforge.geometry.layout import NETS

CTX = {"2R": "experiments/results/E010/E010-20261114T202413-80c1/work/2D_Case_2R/ctx.pkl",
       "Case4": "research/o003/e008_dev/full_work/2D_Case_4/ctx.pkl"}
SEED0 = 20261115  # development seeds, unrelated to any sealed seed
MAX_STEPS = 60
ASCENT_PROPOSALS = 400
PROXY_STEPS = 200
BARE, FROZEN_TARGET = T.DEGRADE_RATIO, T.DEGRADE_RATIO * (1 + T.DEGRADE_MARGIN)


def clean(spec, p):
    try:
        lay = D.build(spec, p)
    except ValueError:
        return None
    return lay if not check(lay, spec.rules) else None


def copper_mm2(lay):
    return sum(unary_union([t.polygon for t in lay.traces if t.net == n]).area for n in NETS) * 1e6


def wire_mm(lay):
    return sum(w.length for w in lay.wires if w.net in NETS) * 1e3


def ascent(spec, W, l_w, rng):
    """Randomised degradation: accept a joint move of 2-4 copper parameters if it is DRC-clean and raises L1; stop at the
    frozen L1 target or after ASCENT_PROPOSALS proposals."""
    p, lay, cur = D.params_of(W), W, l_w
    for _ in range(ASCENT_PROPOSALS):
        if cur / l_w >= FROZEN_TARGET:
            break
        v = p.to_vector().copy()
        for i in rng.choice(np.arange(T.WALK_FIRST, T.WALK_END), size=int(rng.integers(2, 5)), replace=False):
            v[i] += float(rng.choice([-1, 1]) * rng.choice([0.5, 1.0, 1.5, 2.0]))
        q = D.Params.from_vector(v)
        if any(c[0] >= c[2] - 1e-9 or c[1] >= c[3] - 1e-9 for c in q.cols + q.slots):
            continue
        cl = clean(spec, q)
        if cl is None:
            continue
        li = T._l1(cl)
        if li > cur:
            p, lay, cur = q, cl, li
    w0 = D.params_of(W).to_vector()
    changed = int(np.sum(np.abs(p.to_vector()[T.WALK_FIRST:T.WALK_END] - w0[T.WALK_FIRST:T.WALK_END]) > 1e-9))
    dist = float(np.sum(np.abs(p.to_vector()[T.WALK_FIRST:T.WALK_END] - w0[T.WALK_FIRST:T.WALK_END])))
    return p, lay, cur / l_w, changed, dist


def descend(spec, p, lay, l_w, mode, max_steps=None, keep=False):
    """Steepest single-parameter steps until none improves the mode's objective, or max_steps (MAX_STEPS).  ``keep``:
    also return the final params and layout."""
    max_steps = MAX_STEPS if max_steps is None else max_steps
    def score(cl):
        if mode == "guided":
            return -T._l1(cl)
        if mode == "widen":
            return copper_mm2(cl)
        return copper_mm2(cl) - wire_mm(cl)  # compact: 1 mm^2 of copper against 1 mm of power wire

    cur, area, wl, steps = score(lay), copper_mm2(lay), wire_mm(lay), 0
    for _ in range(max_steps):
        best = None
        for _, _, q in T._walk_candidates(p):
            cl = clean(spec, q)
            if cl is None:
                continue
            if mode == "compact" and (copper_mm2(cl) < area - 1e-9 or wire_mm(cl) > wl + 1e-9):
                continue
            sc = score(cl)
            if sc > cur + 1e-12 and (best is None or sc > best[0]):
                best = (sc, q, cl)
        if best is None:
            break
        cur, p, lay = best
        area, wl, steps = copper_mm2(lay), wire_mm(lay), steps + 1
    out = {"s": T._l1(lay) / l_w - 1, "steps": steps, "hit_step_cap": steps == max_steps}
    return (out, p, lay) if keep else out


def main():
    ref, out = sys.argv[1], sys.argv[2]
    draws = int(sys.argv[3]) if len(sys.argv) > 3 else 5
    proxy = len(sys.argv) > 4 and sys.argv[4] == "proxy"
    c = pickle.load(open(CTX[ref], "rb"))
    spec, W = c["spec"], c["twin"]
    l_w = T._l1(W)
    res = {"reference": ref, "ctx": CTX[ref], "l1_W_nH": l_w * 1e9, "bare_target": BARE, "frozen_l1_target": FROZEN_TARGET,
           "rules_min_width_power_mm": spec.rules.min_width_power * 1e3, "max_steps": MAX_STEPS}
    t0 = time.time()
    if proxy:
        # designer proxy W*: a long L1-guided descent from the twin; degradations, searches and shortfalls are then
        # relative to W*, not W (reviews T0353/T0354: a twin that blind compaction beats is a low bar)
        rec, _, W = descend(spec, D.params_of(W), W, l_w, "guided", max_steps=PROXY_STEPS, keep=True)
        res["proxy"] = {"steps": rec["steps"], "hit_step_cap": rec["hit_step_cap"], "l1_proxy_over_twin": 1 + rec["s"]}
        l_w = T._l1(W)
        res["l1_proxy_nH"] = l_w * 1e9
        print(json.dumps(res["proxy"]), flush=True)
    try:
        Dl, rec = T.degrade(W, spec)
        res["frozen_degrade"] = {"ratio": T._l1(Dl) / l_w, "moves": rec["moves"][:12], "walk_terminal":
                                 (rec.get("walk") or {}).get("terminal")}
    except T.DegradeError as e:
        walk = (getattr(e, "record", {}) or {}).get("walk") or {}
        res["frozen_degrade"] = {"error": str(e)[:300], "walk_terminal_ratio": walk.get("l1_ratio"),
                                 "walk_terminal": walk.get("terminal")}
    res["draws"] = []
    for j in range(draws):
        rng = np.random.default_rng(SEED0 + j)
        p, lay, ratio, changed, dist = ascent(spec, W, l_w, rng)
        row = {"draw": j, "seed": SEED0 + j, "R_D_l1": ratio, "reaches_1.25": ratio >= BARE,
               "reaches_frozen_target": ratio >= FROZEN_TARGET, "coords_changed": changed, "manhattan_mm": dist}
        for mode in ("guided", "compact", "widen"):
            row[mode] = descend(spec, p, lay, l_w, mode)
        res["draws"].append(row)
        print(json.dumps(row), flush=True)
    res["wall_s"] = time.time() - t0
    with open(out, "w") as f:
        json.dump(res, f, indent=1)


if __name__ == "__main__":
    main()
