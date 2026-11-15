"""T0349 diagnosis: is the E010 twin W of 2D_Case_2R inside the support of derivative._sample?

Read-only use of frozen src code (moduleforge.generate.derivative). Loads the spec, twin W and yardstick D that run
E010-20261114T202413-80c1 pickled (e010_run.save_ctx). Draws raw proposals (no build, no DRC) and DRC-valid
candidates with seeds unrelated to the sealed seed, and compares their parameter vectors to W's.
Usage: uv run python research/diagnoses/T0349/sampler_support.py N_PROPOSALS N_VALID OUT.json
"""
from __future__ import annotations

import json
import pickle
import resource
import sys
import time
from pathlib import Path

import numpy as np

from moduleforge.drc.rules import check
from moduleforge.generate import derivative as D

RUN = Path("experiments/results/E010/E010-20261114T202413-80c1/work/2D_Case_2R/ctx.pkl")
SEED = 349_0001  # diagnostic seed, unrelated to the sealed seed


def main(n_prop: int, n_valid: int, out: str) -> int:
    t0 = time.time()
    ctx = pickle.load(open(RUN, "rb"))
    spec, W, Dl = ctx["spec"], ctx["twin"], ctx["D"]
    pw, pd = D.params_of(W), D.params_of(Dl)
    w, dvec = pw.to_vector(), pd.to_vector()
    names = D.Params.NAMES
    seq = pw.sequence()
    # W's own facts: DRC under the reference spec, _quick_ok, and slot-vs-column attachment
    cx = D._Ctx(spec)
    rebuilt = D.build(spec, pw)
    w_facts = {
        "topology": pw.topology(), "sequence": seq,
        "drc_violations_of_build_W": [str(v) for v in check(rebuilt, spec.rules)][:10],
        "quick_ok_W": bool(D._quick_ok(spec, cx, rebuilt)),
        "rebuilt_fingerprint_equals_W": rebuilt.fingerprint() == W.fingerprint(),
        "cols": {n: list(c) for n, c in zip(D.NETS, pw.cols, strict=True)},
        "slots": [{"net": s[0], "role": s[1], "sw": s[2], "u0v0u1v1": list(pw.slots[i])} for i, s in enumerate(seq)],
    }
    # raw proposals (no build, no DRC)
    rng = np.random.default_rng(SEED)
    P, n_none = [], 0
    for _ in range(n_prop):
        p = D._sample(spec, cx, rng)
        if p is None:
            n_none += 1
            continue
        P.append(p.to_vector())
    P = np.array(P)
    # slot extent relative to the attached column: does any proposal's slot reach past its column's outer edge?
    def outer_overhang(vec):
        pp = D.Params.from_vector(vec)
        sq = pp.sequence()
        cols = dict(zip(D.NETS, pp.cols, strict=True))
        res = []
        for i, s in enumerate(sq):
            c0, _, c1, _ = cols[s[0]]
            u0, _, u1, _ = pp.slots[i]
            res.append(max(c0 - u0, u1 - c1, 0.0) if (u0 < c0 - 1e-9 and u1 > c1 + 1e-9) else 0.0)
        return res
    ovW = outer_overhang(w)
    ovP = np.array([outer_overhang(v) for v in P]) if len(P) else np.zeros((0, 4))
    # DRC-valid candidates through the frozen generate()
    V = np.array([D.params_of(lay).to_vector() for lay in D.generate(spec, n_valid, SEED + 1)]) if n_valid else np.zeros((0, len(w)))
    geo = slice(4, 40)
    def summary(A):
        if not len(A):
            return {}
        lo, hi = A.min(0), A.max(0)
        outside = [names[i] for i in range(4, 40) if not (lo[i] - 1e-9 <= w[i] <= hi[i] + 1e-9)]
        dist = np.abs(A[:, geo] - w[geo]).sum(1)
        return {"n": int(len(A)), "W_outside_range": outside, "n_W_outside": len(outside),
                "manhattan_to_W_mm": {"min": float(dist.min()), "median": float(np.median(dist))},
                "range": {names[i]: [float(lo[i]), float(hi[i]), float(w[i])] for i in range(4, 40)}}
    res = {
        "seed": SEED, "W": w_facts, "D_manhattan_to_W_mm": float(np.abs(dvec[geo] - w[geo]).sum()),
        "proposals": dict(summary(P), n_draws=n_prop, n_none=n_none,
                          slot_outer_overhang_W_mm=ovW,
                          n_proposals_with_any_outer_overhang=int((ovP > 0).any(1).sum()) if len(ovP) else 0),
        "drc_valid": summary(V),
        "wall_s": time.time() - t0, "maxrss_MB": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 2**20,
    }
    Path(out).write_text(json.dumps(res, indent=1, default=str))
    p = res["proposals"]
    print(json.dumps({k: res[k] for k in ("D_manhattan_to_W_mm", "wall_s", "maxrss_MB")}))
    print("W:", json.dumps({k: w_facts[k] for k in ("topology", "drc_violations_of_build_W", "quick_ok_W",
                                                   "rebuilt_fingerprint_equals_W")}))
    print("W slots:", json.dumps(w_facts["slots"]), "cols:", json.dumps(w_facts["cols"]))
    print("proposals:", json.dumps({k: p.get(k) for k in ("n", "n_none", "n_W_outside", "W_outside_range",
                                                         "manhattan_to_W_mm", "slot_outer_overhang_W_mm",
                                                         "n_proposals_with_any_outer_overhang")}))
    v = res["drc_valid"]
    print("drc_valid:", json.dumps({k: v.get(k) for k in ("n", "n_W_outside", "manhattan_to_W_mm")}))
    return 0


if __name__ == "__main__":
    sys.exit(main(int(sys.argv[1]), int(sys.argv[2]), sys.argv[3]))
