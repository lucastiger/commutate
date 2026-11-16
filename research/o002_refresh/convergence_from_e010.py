"""O002 refresh (founder session, 2026-11-16; reviews T0369 and T0370): how well do die-average Tj values, their
layout-to-layout differences and per-switch spreads converge on the frozen thermal_fem ladder (levels 0-2)?
Reads E010's stored solves on 2D_Case_2R (development geometry under D0023; same thermal_fem bytes as EV-O007-01,
C004's operating point, one power per die for all layouts). No new solve.  Estimator: mfos.metrics.gci_capped of the
finest (level 2) value.  Pair difference: hottest die by the level-2 die average of each layout, as A1 would define it.
Usage: uv run python research/o002_refresh/convergence_from_e010.py OUT.json"""
import glob
import itertools
import json
import sys
from collections import defaultdict

import numpy as np

from mfos.metrics import gci_capped

RUN = "experiments/results/E010/E010-20261114T202413-80c1/work/2D_Case_2R/solves"
lev = defaultdict(dict)
for f in glob.glob(f"{RUN}/*__thermal[012]__*.json"):
    if f.endswith(".job.json"):
        continue
    d = json.load(open(f))
    if d.get("status") != "ok":
        continue
    fp = f.split("/")[-1].split("__")[0]
    lev[fp][d["level"]] = {"tj_mean": d["tj_mean"], "wall_s": d.get("wall_s"), "peak_GB": d.get("peak_GB"),
                           "nodes": d.get("nodes")}
lays = sorted(fp for fp, v in lev.items() if all(k in v for k in (0, 1, 2)))


def seq(fn, fp):
    return [fn(np.asarray(lev[fp][k]["tj_mean"])) for k in (0, 1, 2)]


die = [gci_capped(*[lev[fp][k]["tj_mean"][i] for k in (0, 1, 2)]) for fp in lays
       for i in range(len(lev[fp][2]["tj_mean"]))]
hot = {fp: int(np.argmax(lev[fp][2]["tj_mean"])) for fp in lays}
pairs = []
for a, b in itertools.combinations(lays, 2):
    s = [lev[a][k]["tj_mean"][hot[a]] - lev[b][k]["tj_mean"][hot[b]] for k in (0, 1, 2)]
    pairs.append({"gci": gci_capped(*s), "diff_l2": s[2], "d1": s[1] - s[0], "d2": s[2] - s[1]})
n_die = len(lev[lays[0]][2]["tj_mean"])
half = n_die // 2  # two switches with equal die counts (2R: 2 dies per switch)
spread = []
for fp in lays:
    for sw in (slice(0, half), slice(half, n_die)):
        spread.append(gci_capped(*seq(lambda t, sw=sw: float(t[sw].max() - t[sw].min()), fp)))


def summ(x):
    x = np.asarray(x, float)
    fin = x[np.isfinite(x)]
    return {"n": int(x.size), "n_inf": int((~np.isfinite(x)).sum()),
            "median": float(np.median(fin)) if fin.size else None,
            "p95": float(np.percentile(fin, 95)) if fin.size else None, "max": float(fin.max()) if fin.size else None}


out = {"layouts": len(lays), "dies_per_layout": n_die,
       "die_average_gci_K": summ(die),
       "pair_difference_gci_K": summ([p["gci"] for p in pairs]),
       "pair_abs_diff_l2_K": summ([abs(p["diff_l2"]) for p in pairs]),
       "switch_spread_gci_K": summ(spread),
       "level2_wall_s": summ([lev[fp][2]["wall_s"] for fp in lays]),
       "level2_peak_GB": summ([lev[fp][2]["peak_GB"] for fp in lays]),
       "level1_wall_s": summ([lev[fp][1]["wall_s"] for fp in lays]),
       "level2_nodes": summ([lev[fp][2]["nodes"] for fp in lays])}
json.dump(out, open(sys.argv[1], "w"), indent=1)
print(json.dumps(out, indent=1))

# level-1 adequacy and the divergent cases (appended): |d2| = level-2 minus level-1 value bounds what judging at
# level 1 would leave out at the finest step; the divergent (+inf) pairs' steps show whether they are tiny-step cases.
d2 = np.abs([p["d2"] for p in pairs])
inf_steps = [(round(p["d1"], 4), round(p["d2"], 4)) for p in pairs if not np.isfinite(p["gci"])]
extra = {"pair_abs_d2_K": summ(d2), "pair_abs_d1_K": summ(np.abs([p["d1"] for p in pairs])),
         "divergent_pair_steps_K": inf_steps}
out.update(extra)
json.dump(out, open(sys.argv[1], "w"), indent=1)
print(json.dumps(extra, indent=1))
