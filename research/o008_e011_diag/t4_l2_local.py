"""Test T4 (local l2_layout at 0.5 mm, E010's child, 2 threads): the discriminating L2 solves of the diagnosis.

Each case is a layout built from a committed parameter vector (W* or a 2R search end point b_j, from the manifest) with
named parameters set to stated values.  Per case: validity (build, DRC under the reference's measured rules,
in_domain(reach=True)), L1 at hmax 4 mm (the frozen screen) and 1 mm, and L2 = l2_layout at E010's level lat0.5 through
``e010_run.py --child`` (exactly the burst's job format and level settings).  Ratios are to the local W* solve; the two
determinism cases (W*, b_7) compare the local solve with the burst's.

The packet caps local 0.5 mm solves at 6 CPU-hours in all; ``--max-cpu-h`` enforces it from the recorded cpu_s.

Run: ``uv run python research/o008_e011_diag/t4_l2_local.py [--only NAME ...] [--jobs 2]``
     -> research/o008_e011_diag/l2/solves/em_lat0.5_<fp>.json and research/o008_e011_diag/t4_l2_local.json
"""
from __future__ import annotations

import argparse
import json
import pickle
import subprocess
import sys
import time

import numpy as np

import common as C

L2W = C.OUT / "l2"
LEVEL = "lat0.5"
FREQ_HZ = 20e6  # E011 config.levels.freq_hz (the burst's job files carry 2e7)


def cases(names: list[str], P: dict, w: np.ndarray) -> list[dict]:
    def b(j: int) -> np.ndarray:
        return np.asarray(P[C.roles_of_draw(j)["search"]], float)

    def at(base: np.ndarray, **kw) -> np.ndarray:
        v = base.copy()
        for k, x in kw.items():
            v[names.index(k)] = x
        return v

    def W(k: str) -> float:
        return float(w[names.index(k)])

    def plus(base: np.ndarray, **kw) -> np.ndarray:
        v = base.copy()
        for k, d in kw.items():
            v[names.index(k)] += d
        return v

    return [
        {"name": "A0_Wstar", "why": "determinism: local vs burst", "vec": w},
        {"name": "A1_b7", "why": "determinism: local vs burst", "vec": b(7)},
        {"name": "B1_Wstar_rowLS+6", "why": "H1: L2 cost of the LS die-row shift the search leaves on draws 4, 7",
         "vec": plus(w, row_LS_u0=6.0)},
        {"name": "B2_Wstar_rowLS+3", "why": "H1: linearity of the same", "vec": plus(w, row_LS_u0=3.0)},
        {"name": "B3_b7_rowLS=W*", "why": "H1: draw 7's end point with the LS die row back at W*'s position",
         "vec": at(b(7), row_LS_u0=W("row_LS_u0"))},
        {"name": "B4_b4_slot1,rowLS=W*", "why": "H1: draw 4's end point with slot1_u0 and the LS die row at W*'s",
         "vec": at(b(4), slot1_u0=W("slot1_u0"), row_LS_u0=W("row_LS_u0"))},
        {"name": "B4b_b4_slot1=W*", "why": "confound: slot1_u0 alone (L1 is flat in it)",
         "vec": at(b(4), slot1_u0=W("slot1_u0"))},
        {"name": "B5_Wstar_slot1+3", "why": "confound: slot1_u0 at W* (L1 flat)", "vec": plus(w, slot1_u0=3.0)},
        {"name": "C1_b2_triple-0.5", "why": "H2: draw 2's blocked coupled move (col_PHASE_u0, row_HS_u0, slot2_u1)",
         "vec": plus(b(2), col_PHASE_u0=-0.5, row_HS_u0=-0.5, slot2_u1=-0.5)},
        {"name": "C2_b2_triple-1.0", "why": "H2: the same, two steps",
         "vec": plus(b(2), col_PHASE_u0=-1.0, row_HS_u0=-1.0, slot2_u1=-1.0)},
        {"name": "C3_b3_triple-0.5", "why": "H2: draw 3's blocked coupled move",
         "vec": plus(b(3), col_PHASE_u0=-0.5, row_HS_u0=-0.5, slot2_u1=-0.5)},
        {"name": "D1_b1_rows=W*", "why": "H2/ruggedness: draw 1's end point with row_HS_u0, row_LS_u0, row_LS_gap at W*'s",
         "vec": at(b(1), row_HS_u0=W("row_HS_u0"), row_LS_u0=W("row_LS_u0"), row_LS_gap=W("row_LS_gap"))},
        {"name": "E0_b0_slot1,rowLS=W*", "why": "H1/H2: draw 0's end point with slot1_u0 and the LS die row at W*'s",
         "vec": at(b(0), slot1_u0=W("slot1_u0"), row_LS_u0=W("row_LS_u0"))},
        {"name": "C4_b3_triple-2.0", "why": "H2: draw 3's coupled move, four steps (col_PHASE_u0 back at W*'s)",
         "vec": plus(b(3), col_PHASE_u0=-2.0, row_HS_u0=-2.0, slot2_u1=-2.0)},
        {"name": "D2_b1_rows=W*,pair-1.0", "why": "H2: D1 plus col_PHASE_u0 and slot2_u1 by -1 mm (row_HS_u0 already at W*'s)",
         "vec": plus(at(b(1), row_HS_u0=W("row_HS_u0"), row_LS_u0=W("row_LS_u0"), row_LS_gap=W("row_LS_gap")),
                     col_PHASE_u0=-1.0, slot2_u1=-1.0)},
    ]


def job_of(lay, fp: str) -> dict:
    (L2W / "lay").mkdir(parents=True, exist_ok=True)
    (L2W / "solves").mkdir(parents=True, exist_ok=True)
    ctx = L2W / "lay" / f"{fp}.pkl"
    if not ctx.exists():
        ctx.write_bytes(pickle.dumps({"D": lay}))
    out = L2W / "solves" / f"em_{LEVEL}_{fp}.json"
    return {"type": "em", "ctx": str(ctx.relative_to(C.ROOT)), "which": "D", "fp": fp, "family": None,
            "out": str(out.relative_to(C.ROOT)), "threads": 2, "ref": C.LAYOUT, "level": LEVEL, "freq_hz": FREQ_HZ}


def run_jobs(jobs: list[dict], n_at_once: int, cpu_cap_s: float, spent_s: float) -> None:
    import e010_run as E

    env = E.child_env(2)
    todo = [j for j in jobs if not (C.ROOT / j["out"]).exists()]
    running: list[tuple[subprocess.Popen, dict]] = []
    while todo or running:
        while todo and len(running) < n_at_once and spent_s < cpu_cap_s:
            j = todo.pop(0)
            jf = C.ROOT / (j["out"][:-5] + ".job.json")
            jf.write_text(json.dumps(j))
            log = open(C.ROOT / (j["out"][:-5] + ".log"), "w")  # noqa: SIM115
            pr = subprocess.Popen([sys.executable, str(C.ROOT / "experiments/runners/e010_run.py"), "--child", str(jf)],
                                  cwd=C.ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
            running.append((pr, j))
            print(time.strftime("%H:%M:%S"), "start", j["fp"][:10], flush=True)
        if not running:
            print("CPU cap reached; stopping with", len(todo), "jobs left", flush=True)
            return
        time.sleep(5)
        for pr, j in list(running):
            if pr.poll() is not None:
                running.remove((pr, j))
                r = json.loads((C.ROOT / j["out"]).read_text())
                spent_s += float(r.get("cpu_s", 0.0))
                print(time.strftime("%H:%M:%S"), "done", j["fp"][:10], r.get("status"), r.get("L_H"),
                      f"wall {r.get('wall_s', 0):.0f} s cpu {r.get('cpu_s', 0):.0f} s peak {r.get('peak_GB', 0):.2f} GB",
                      f"(spent {spent_s / 3600:.2f} CPU-h)", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--jobs", type=int, default=2)
    ap.add_argument("--max-cpu-h", type=float, default=6.0)
    ap.add_argument("--plan", action="store_true", help="validity and L1 only; solve nothing")
    a = ap.parse_args()
    from moduleforge.generate.twin import L1_FREQ_HZ
    from moduleforge.physics.peec import loop_inductance

    l1 = C.L1()
    P = C.params_by_fp()
    lay = C.manifest()["layouts"][C.LAYOUT]
    w = np.asarray(lay["Wstar"]["params"], float)
    Lw4 = l1(w, lay["Wstar"]["fingerprint"])
    Lw1 = float(loop_inductance(l1.build(w), [L1_FREQ_HZ], hmax=1e-3).L_H[0])
    cs = cases(l1.names, P, w)
    if a.only:
        cs = [c for c in cs if c["name"] in a.only or c["name"] == "A0_Wstar"]
    jobs, recs = [], []
    for c in cs:
        lay_ = l1.build(c["vec"])
        fp = lay_.fingerprint()
        ok, why = l1.valid(c["vec"])
        l1_1 = float(loop_inductance(lay_, [L1_FREQ_HZ], hmax=1e-3).L_H[0]) / Lw1
        rec = {"name": c["name"], "why": c["why"], "fingerprint": fp, "valid": ok, "valid_why": why,
               "l1_ratio_4mm": l1(c["vec"]) / Lw4, "l1_ratio_1mm": l1_1,
               "diff_from_Wstar": C.diff_params(w, c["vec"], l1.names)}
        recs.append(rec)
        jobs.append(job_of(lay_, fp))
        print(f"{c['name']:24s} valid {ok!s:5s} ({why}) L1 4mm {rec['l1_ratio_4mm']:.4f} 1mm {l1_1:.4f}", flush=True)
    if not a.plan:
        spent = 0.0
        for p in (L2W / "solves").glob("em_*.json"):
            if not p.name.endswith(".job.json"):
                spent += float(json.loads(p.read_text()).get("cpu_s", 0.0))
        run_jobs(jobs, a.jobs, a.max_cpu_h * 3600.0, spent)
    # summary over every case with a result
    ws_fp = lay["Wstar"]["fingerprint"]
    f = L2W / "solves" / f"em_{LEVEL}_{ws_fp}.json"
    loc_ws = json.loads(f.read_text())["L_H"] if f.exists() else None
    burst_ws = C.l2(ws_fp, LEVEL)
    cpu = 0.0
    for rec in recs:
        f = L2W / "solves" / f"em_{LEVEL}_{rec['fingerprint']}.json"
        r = json.loads(f.read_text()) if f.exists() else None
        rec["l2_local"] = r and {k: r.get(k) for k in ("status", "L_H", "n_unknowns", "gmres_flags",
                                                       "solver_tol_rel_L_max", "wall_s", "cpu_s", "peak_GB")}
        rec["l2_burst_H"] = C.l2(rec["fingerprint"], LEVEL)
        if r and r.get("status") == "ok" and loc_ws:
            rec["l2_ratio"] = r["L_H"] / loc_ws
            cpu += float(r["cpu_s"])
        if rec["l2_burst_H"] and burst_ws:
            rec["l2_ratio_burst"] = rec["l2_burst_H"] / burst_ws
    C.dump({"level": LEVEL, "freq_hz": FREQ_HZ, "Wstar_local_H": loc_ws, "Wstar_burst_H": burst_ws,
            "cpu_h_total": cpu / 3600.0, "cases": recs}, C.OUT / "t4_l2_local.json")
    for rec in recs:
        print(f"{rec['name']:24s} L1 4mm {rec['l1_ratio_4mm']:.4f} 1mm {rec['l1_ratio_1mm']:.4f} "
              f"L2 {rec.get('l2_ratio', float('nan')):.4f} (burst {rec.get('l2_ratio_burst', float('nan')):.4f})")


if __name__ == "__main__":
    main()
