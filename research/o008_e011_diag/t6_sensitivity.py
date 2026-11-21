"""Test T6 (local l2_layout at 0.5 mm): one-at-a-time sensitivity of L1 and L2 to every movable parameter at W*.

For each of the 36 movable parameters and each sign, the largest valid move of at most 2 mm (2.0, 1.5, 1.0, 0.5 mm tried
in that order; valid = builds, DRC-clean, in_domain(reach=True)) is applied to W*.  Reported per move: L1 at hmax 4 mm and
1 mm and L2 at lat0.5, each as a ratio to W* at the same model.  The question: is L1's under-weighting confined to some
parameters (H1/H4 localised), or is it a uniform scale factor (the global L2/L1 slope of about 0.71)?

Run: ``uv run python research/o008_e011_diag/t6_sensitivity.py [--plan] [--jobs 2]`` -> research/o008_e011_diag/t6_sensitivity.json
"""
from __future__ import annotations

import argparse
import json

import numpy as np

import common as C
import t4_l2_local as T4

MAGS = (2.0, 1.5, 1.0, 0.5)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--jobs", type=int, default=2)
    ap.add_argument("--plan", action="store_true")
    ap.add_argument("--max-cpu-h", type=float, default=6.0)
    a = ap.parse_args()
    from moduleforge.generate.twin import L1_FREQ_HZ
    from moduleforge.physics.peec import loop_inductance

    l1 = C.L1()
    names = l1.names
    lay = C.manifest()["layouts"][C.LAYOUT]
    w = np.asarray(lay["Wstar"]["params"], float)
    Lw4 = l1(w, lay["Wstar"]["fingerprint"])
    Lw1 = float(loop_inductance(l1.build(w), [L1_FREQ_HZ], hmax=1e-3).L_H[0])
    recs, jobs = [], []
    for i in C.MOVABLE:
        for sgn in (1.0, -1.0):
            for m in MAGS:
                v = w.copy()
                v[i] += sgn * m
                ok, _ = l1.valid(v)
                if ok:
                    lay_ = l1.build(v)
                    fp = lay_.fingerprint()
                    l1_1 = float(loop_inductance(lay_, [L1_FREQ_HZ], hmax=1e-3).L_H[0]) / Lw1
                    recs.append({"param": names[i], "group": C.group_of(names[i]), "delta_mm": sgn * m,
                                 "fingerprint": fp, "l1_ratio_4mm": l1(v) / Lw4, "l1_ratio_1mm": l1_1})
                    jobs.append(T4.job_of(lay_, fp))
                    break
    print(len(recs), "valid one-at-a-time moves;", len({r["param"] for r in recs}), "parameters", flush=True)
    if not a.plan:
        spent = 0.0
        for p in (T4.L2W / "solves").glob("em_*.json"):
            if not p.name.endswith(".job.json"):
                spent += float(json.loads(p.read_text()).get("cpu_s", 0.0))
        T4.run_jobs(jobs, a.jobs, a.max_cpu_h * 3600.0, spent)
    f = T4.L2W / "solves" / f"em_{T4.LEVEL}_{lay['Wstar']['fingerprint']}.json"
    Lw2 = json.loads(f.read_text())["L_H"]
    for r in recs:
        g = T4.L2W / "solves" / f"em_{T4.LEVEL}_{r['fingerprint']}.json"
        if g.exists():
            x = json.loads(g.read_text())
            if x.get("status") == "ok":
                r["l2_ratio"] = x["L_H"] / Lw2
    done = [r for r in recs if "l2_ratio" in r]
    x1 = np.log([r["l1_ratio_1mm"] for r in done])
    x4 = np.log([r["l1_ratio_4mm"] for r in done])
    y = np.log([r["l2_ratio"] for r in done])
    summ = {}
    if len(done) >= 3:
        for key, x in (("1mm", x1), ("4mm", x4)):
            k = float(x @ y / (x @ x))  # through the origin: both ratios are 1 at W*
            res = y - k * x
            summ[key] = {"slope_through_origin": k, "residual_sd": float(res.std()),
                         "pearson": float(np.corrcoef(x, y)[0, 1])}
            for r, e in zip(done, res, strict=True):
                r[f"resid_{key}"] = float(e)
    C.dump({"level": T4.LEVEL, "mags_mm": MAGS, "summary": summ, "moves": recs}, C.OUT / "t6_sensitivity.json")
    print(json.dumps(summ, indent=1))
    for r in sorted(done, key=lambda r: -abs(r.get("resid_1mm", 0.0)))[:14]:
        print(f"{r['param']:14s} {r['delta_mm']:+.1f}  L1 4mm {r['l1_ratio_4mm']:.4f} 1mm {r['l1_ratio_1mm']:.4f} "
              f"L2 {r['l2_ratio']:.4f}  resid {r.get('resid_1mm', 0):+.4f}")


if __name__ == "__main__":
    main()
