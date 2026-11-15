"""T0349: recompute F1(b) for 2D_Case_2R of run E010-20261114T202413-80c1 from the raw checkpoints (no solver), and
summarise the lower tail of the L1 pool relative to the twin. Usage: python recompute_f1b.py OUT.json"""
import json
import sys
from pathlib import Path

RUN = Path("experiments/results/E010/E010-20261114T202413-80c1/work/2D_Case_2R")
TWIN = "f95383d84d9ae16de209ed4cb967425284a478474233266326c7047fc60b36b1"
RECON = "66cb1e191c9f88396125cfd87227865d209ea6cf4c5f4306082c5ccee2ad696a"
DEG = "a25edf2fcab30764392bd9d05aac72d1b2b2363ba99dcf32b8b3f6040e81c1d5"


def load(ns):
    l1, lsub, band = {}, {}, {}
    for line in open(RUN / ns / "checkpoint.jsonl"):
        r = json.loads(line)
        _, fp, kind = r["k"].split(":")
        {"l1": l1, "lsub": lsub, "band": band}.get(kind, {})[fp] = r["v"]
    return l1, lsub, band


m_l1, m_lsub, m_band = load("main")
c_l1, c_lsub, c_band = load("control")
rep = json.load(open(RUN.parent / "evaluation_report.json"))["report"]["2D_Case_2R"]
L_W = m_lsub[TWIN]
L_D = c_band[DEG][0]
cands = {f: v for f, v in c_lsub.items() if f != DEG}
best = min(cands, key=cands.get)
L_cb = c_band[best][0]
h_plant, h_ctrl = 1 - L_W / L_D, 1 - L_cb / L_D
w_ctrl = rep["w_ctrl"]
need = L_D * (1 - h_plant + w_ctrl)  # largest control-best L_sub that passes
lt = 7e-9
l1W = m_l1[TWIN]
tail = {}
for ns, l1 in (("main", m_l1), ("control", c_l1)):
    x = sorted(v / l1W - 1 for f, v in l1.items() if f not in (TWIN, RECON))
    tail[ns] = {"n": len(x), "min_rel_excess": x[0],
                **{f"n_within_{p}pct": sum(v <= p / 100 for v in x) for p in (2, 3, 5, 7, 10, 15)}}
out = {
    "L_sub_W_H": L_W, "L_sub_D_H": L_D, "control_best": best, "L_sub_control_best_H": L_cb,
    "control_best_is_min_of_shortlist": L_cb == min(cands.values()), "n_control_shortlist": len(cands),
    "h_plant": h_plant, "h_ctrl": h_ctrl, "w_ctrl": w_ctrl, "threshold": h_plant - w_ctrl,
    "matches_report": abs(h_plant - rep["h_plant"]) < 1e-12 and abs(h_ctrl - rep["h_ctrl"]) < 1e-12,
    "pass_needs_L_cb_le_H": need, "pass_needs_L_cb_over_L_W_le": need / L_W, "observed_L_cb_over_L_W": L_cb / L_W,
    "main_best_L2_over_L_W": min(v for f, v in m_lsub.items() if f not in (TWIN, RECON)) / L_W,
    "module_level_with_Lterm_7nH_for_reference_only": {
        "h_plant_mod": 1 - (L_W + lt) / (L_D + lt), "h_ctrl_mod": 1 - (L_cb + lt) / (L_D + lt),
        "note": "not what the runner computes (both h use bands[..][0] = L_sub); shown because the substrate and "
                "module values happen to be close"},
    "twin_equals_reconstruction_L2_rel": abs(m_lsub[TWIN] / m_lsub[RECON] - 1),
    "L1_tail_relative_to_twin": tail,
}
Path(sys.argv[1]).write_text(json.dumps(out, indent=1))
print(json.dumps(out, indent=1))
