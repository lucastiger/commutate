"""T0316 (D0018 decision 1): does narrowing D's power strips to the floor inflate the band estimate e_R(D, W)?

l2_layout band solves at 0.5 mm cells (packet limit: no 0.25 mm solve, no Case-4-size solve) on one generator housing layout
of gen2_0 size, for the twin W (= the generator layout itself) and D built by the frozen degrade() under the runner's floor
rule (e008_run.d_spec) at the reference's own power rule ("rule") and at the candidate floors.  Levels (P3's): lat0.5
(production layers), thk_c (5/3/3), thk_f (20/12/12).  No lateral term: 0.25 mm is outside the packet's limits, and a
1.0 mm level (P3's supplementary lat1.0) cannot run on generator layouts: l2_layout requires every feature on a cell
boundary and the generator's features lie on the 0.5 mm grid (first attempt, l2_strip_check.log: "the DC+ trace is not on
the lattice ... cell 1 x 1 mm").  fil_f (wire annuli) is not run: D and W carry the same wires, and its
5.5-5.7 GB peak on gen2_0 is above this agent's 5 GB budget.  Per D: R(level) = L(D)/L(W) and the e_R terms of
mfos.metrics.ratio_band_estimate that can be formed at 0.5 mm: the thickness term ratio_middle_term(R(thk_c), R(0.5),
R(thk_f)).

Each solve runs in its own subprocess (module constants overridden as e008_run.child_em does; src/ unchanged), one at a
time, and writes one JSON file under l2_solves/ (checkpoint: an existing file is not re-solved).
Usage: uv run python research/o003/e008_dev/d_floor/l2_strip_check.py [--layout gen2x1_w2_s11] [--floors 1.0,1.5]
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import pickle
import resource
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
LEVELS = {"lat0.5": (0.5, (10, 6, 6)), "thk_c": (0.5, (5, 3, 3)), "thk_f": (0.5, (20, 12, 12))}
E0 = (0, .35, .6, .8, .93, 1)


def runner():
    sp = importlib.util.spec_from_file_location("e008_run", ROOT / "experiments/runners/e008_run.py")
    R = importlib.util.module_from_spec(sp)
    sys.modules[sp.name] = R
    sp.loader.exec_module(R)
    return R


def solve(pkl: str, level: str, out: str) -> int:
    sys.path[:0] = [str(ROOT / "src")]
    from moduleforge.solvers import l2_layout as L
    cell, layers = LEVELS[level]
    L.CELL = (cell * 1e-3,) + tuple(L.CELL[1:])
    for attr, n in zip(("LAYERS_TOP", "LAYERS_BACK", "LAYERS_BASE"), layers, strict=True):
        setattr(L, attr, (n,) + tuple(getattr(L, attr)[1:]))
    L.WIRE_EDGES = (E0,) + tuple(L.WIRE_EDGES[1:])
    lay = pickle.loads(Path(pkl).read_bytes())
    t0 = time.perf_counter()
    r = L.loop_inductance(lay, [20e6], refinement=0)
    Path(out).write_text(json.dumps({"L_H": float(r.L_H[0]), "n_unknowns": int(r.meta["n_unknowns"]), "level": level,
                                     "fingerprint": lay.fingerprint(), "wall_s": time.perf_counter() - t0,
                                     "peak_GB": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e9}))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--solve", nargs=3)
    ap.add_argument("--layout", default="gen2x1_w2_s11")
    ap.add_argument("--floors", default="1.0,1.5")
    a = ap.parse_args()
    if a.solve:
        return solve(*a.solve)
    R = runner()
    MX = R.MX
    from moduleforge.drc.rules import DesignRules, check
    from moduleforge.generate import derivative as D
    from moduleforge.generate import twin as W
    n, k, w, seed = a.layout[3:].replace("x", " ").replace("_w", " ").replace("_s", " ").split()
    spec = D.halfbridge_housing_spec(int(n), rules=DesignRules(min_width_power=float(w) * 1e-3), wires_per_die=int(k))
    tw = D.generate(spec, 1, seed=int(seed))[0]  # a generator layout is its own twin (twin mode fit, symdiff 0)
    lays = {"W": tw}
    meta = {"layout": a.layout, "reference_min_width_power_mm": float(w), "W_narrowest_mm": R.narrowest_power_strip_m(tw) * 1e3}
    for fl in ["rule", *a.floors.split(",")]:
        dsp, _ = R.d_spec(spec, spec.rules.min_width_power if fl == "rule" else float(fl) * 1e-3)
        try:
            d, rec = W.degrade(tw, dsp)
        except W.DegradeError as e:
            meta[f"D_{fl}"] = {"DegradeError": str(e)[:200]}
            continue
        lays[f"D_{fl}"] = d
        meta[f"D_{fl}"] = {"l1_ratio": rec["l1_ratio"], "narrowest_mm": R.narrowest_power_strip_m(d) * 1e3,
                           "moves_non_walk": [m for m in rec["moves"] if not m.startswith("walk[")],
                           "walk_steps": sum(m.startswith("walk[") for m in rec["moves"]),
                           "drc_clean_under_D_rules": not check(d, dsp.rules)}
    print(json.dumps(meta), flush=True)
    sd = HERE / "l2_solves"
    sd.mkdir(exist_ok=True)
    L = {}
    for name, lay in lays.items():
        pk = sd / f"{a.layout}_{name}.pkl"
        pk.write_bytes(pickle.dumps(lay))
        for lv in LEVELS:
            out = sd / f"{a.layout}_{name}_{lv}_{lay.fingerprint()[:12]}.json"
            if not out.exists():
                print(time.strftime("%H:%M:%S"), "solve", name, lv, flush=True)
                subprocess.run([sys.executable, __file__, "--solve", str(pk), lv, str(out)], check=True, cwd=ROOT)
            L.setdefault(name, {})[lv] = json.loads(out.read_text())
        pk.unlink()
    res = {"meta": meta, "solves": L, "per_D": {}}
    for name in lays:
        if name == "W":
            continue
        r = {lv: L[name][lv]["L_H"] / L["W"][lv]["L_H"] for lv in LEVELS}
        res["per_D"][name] = {"R": r, "thickness_term": MX.ratio_middle_term(r["thk_c"], r["lat0.5"], r["thk_f"]),
                              "L_rel_thk_c_vs_0p5": L[name]["thk_c"]["L_H"] / L[name]["lat0.5"]["L_H"] - 1,
                              "L_rel_thk_f_vs_0p5": L[name]["thk_f"]["L_H"] / L[name]["lat0.5"]["L_H"] - 1}
    res["W_L_rel_thk_c_vs_0p5"] = L["W"]["thk_c"]["L_H"] / L["W"]["lat0.5"]["L_H"] - 1
    res["W_L_rel_thk_f_vs_0p5"] = L["W"]["thk_f"]["L_H"] / L["W"]["lat0.5"]["L_H"] - 1
    (HERE / f"l2_strip_check_{a.layout}.json").write_text(json.dumps(res, indent=1))
    print(json.dumps(res["per_D"], indent=1), res["W_L_rel_thk_c_vs_0p5"], res["W_L_rel_thk_f_vs_0p5"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
