"""E006 F5 feasibility on DEVELOPMENT geometry only (T0196; research, never evidence, never the sealed seed).

Question: on the two development A3 layouts (dev seed 20261101: side_by_side with 6 dies per switch, u_shaped with 2),
at O003's operating point, is scikit-fem's own F5 estimate on its frozen E006 rule at most 0.25 K for every die?
    estimate = mfos.metrics.gci_capped(skfem_lv0, skfem_lv1, skfem_lv2, floor 1e-3 K)
               + mfos.metrics.two_grid_term(skfem_lv1, skfem_z1)          (2.5 |z1 - z0|, z0 = level 1)
with the frozen rule of the spec (config skfem_rule: h0 0.5 mm, near margin 1.5 mm, nz per layer, z held over levels
0-2) and skfem_z1 = level 1 with every nz doubled, exactly as e006_run.run_layout builds them.

Blindness (task packet T0196): no L2 Tj value, no L2-vs-scikit-fem difference and no A3/A4 value is computed, printed
or recorded.  The only L2 computation is e006_run.calibrate_power (L2 level-0 solves), which is how O003's operating
point is defined (O006 scope_in: equal power per die from an L2 level-0 solve so that the hottest die rises 60 K); the
child keeps only the returned power and discards the rise (by construction within 0.25 K of 60 K, or it raises).

Memory (agent memory rule): every solve runs in its own subprocess, one at a time, and is checkpointed to
research/e006/f5_dev_ckpt/ (rerunning resumes).  Before each solve the parent estimates its peak from the DOF count
(thermal_fem.estimate_dofs x 6.5 kB/DOF, the highest measured figure at 0.9-1.5 M DOF, benchmarks/results/
thermal_fem_convergence.json) and refuses it above 10 GB; above 5 GB it waits until memory_pressure reports >= 50 % free
and the swap files total < 4 GB (sysctl vm.swapusage is blocked by the sandbox; allocated swap files bound the swap
used from above).  While a child runs the parent kills it if the swap files exceed 8 GB.

Run:  uv run python experiments/runners/e006_f5_dev.py            (writes research/e006/f5_dev_check.json)
"""
from __future__ import annotations

import argparse
import json
import re
import resource
import subprocess
import sys
import time
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "experiments" / "runners"), str(ROOT / "tools" / "mfos"), str(ROOT / "src")]

CKPT = ROOT / "research" / "e006" / "f5_dev_ckpt"
OUT = ROOT / "research" / "e006" / "f5_dev_check.json"
BYTES_PER_DOF = 6.5e3  # highest measured whole-process figure at 0.9-1.5 M DOF (u_shaped_2 level 2: 6.02 GB / 0.93 M)
MAX_GB, WAIT_GB = 10.0, 5.0
SWAP_START_GB, SWAP_KILL_GB = 4.0, 8.0
DEV_SEED = 20261101


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def mem_free_pct() -> int:
    out = subprocess.run(["memory_pressure"], capture_output=True, text=True).stdout
    m = re.search(r"free percentage:\s*(\d+)%", out)
    return int(m.group(1)) if m else -1


def swap_files_gb() -> float:
    return sum(p.stat().st_size for p in Path("/private/var/vm").glob("swapfile*")) / 1e9


# ------------------------------------------------------------------------------------------------ child
def child(step: str, name: str, out: Path) -> None:
    import e006_run as R

    from moduleforge.solvers import thermal_fem as FEM

    cfg = R.load_config()
    assert cfg["dev_seed"] == DEV_SEED
    lay = dict(R.dev_layouts(cfg))[name]
    assert lay.fingerprint() == cfg["dev_fingerprints"][name], "dev fingerprint mismatch"
    t0 = time.time()
    if step == "power":
        P, _ = R.calibrate_power(lay, cfg)  # L2 level-0 solves define the operating point; the rise is discarded
        doc = {"power_W": P, "calibrated_within_tol": True}
    else:
        P = json.loads((CKPT / f"{name}_power.json").read_text())["power_W"]
        sk = cfg["skfem_rule"]
        rule = FEM.GridRule(h0=sk["h0_m"], nz=dict(sk["nz"]), zrefine=False, near_margin=sk["near_margin_m"])
        if step == "L1z2":
            rule, lv = replace(rule, nz={k: 2 * v for k, v in sk["nz"].items()}), 1
        else:
            lv = int(step[1:])
        r = FEM.solve_layout(lay, P, cfg["h_W_m2K"], cfg["coolant_K"], rule=rule, level=lv)
        doc = {"tj_max_K": [float(v) for v in r.tj_max], "dofs": int(r.dofs), "level": lv,
               "nz": dict(rule.nz), "energy_balance": float(r.energy_balance),
               "picard_residual_K": float(r.picard_residual), "picard_iters": int(r.picard_iters)}
    doc.update(step=step, layout=name, wall_s=round(time.time() - t0, 1),
               peak_rss_gb=round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e9, 3))
    out.write_text(json.dumps(doc, indent=1) + "\n")


# ------------------------------------------------------------------------------------------------ parent
def estimate_gb(name: str, step: str) -> float:
    import e006_run as R

    from moduleforge.solvers import thermal_fem as FEM

    if step == "power":
        return 1.0
    cfg = R.load_config()
    lay = dict(R.dev_layouts(cfg))[name]
    sk = cfg["skfem_rule"]
    rule = FEM.GridRule(h0=sk["h0_m"], nz=dict(sk["nz"]), zrefine=False, near_margin=sk["near_margin_m"])
    if step == "L1z2":
        rule, lv = replace(rule, nz={k: 2 * v for k, v in sk["nz"].items()}), 1
    else:
        lv = int(step[1:])
    return FEM.estimate_dofs(lay, rule, lv) * BYTES_PER_DOF / 1e9


def run_step(name: str, step: str, gates: list) -> dict:
    out = CKPT / (f"{name}_power.json" if step == "power" else f"{name}_{step}.json")
    if out.exists():
        log(f"{name} {step}: checkpoint found, skipped")
        return json.loads(out.read_text())
    est = estimate_gb(name, step)
    if est > MAX_GB:
        raise MemoryError(f"{name} {step}: estimated {est:.1f} GB > {MAX_GB} GB (single-process limit)")
    for _ in range(40):
        free, swp = mem_free_pct(), swap_files_gb()
        if est <= WAIT_GB or (free >= 50 and swp < SWAP_START_GB):
            break
        log(f"{name} {step}: est {est:.1f} GB, memory free {free} %, swap files {swp:.1f} GB; waiting 180 s")
        time.sleep(180)
    else:
        raise RuntimeError("memory never became available")
    gates.append({"step": f"{name}/{step}", "estimated_gb": round(est, 2), "mem_free_pct": free,
                  "swap_files_gb": round(swp, 2)})
    log(f"{name} {step}: start (est {est:.1f} GB, memory free {free} %, swap files {swp:.2f} GB)")
    p = subprocess.Popen([sys.executable, __file__, "--child", step, name, str(out)], cwd=ROOT)
    while p.poll() is None:
        time.sleep(10)
        if swap_files_gb() > SWAP_KILL_GB:
            p.kill()
            raise RuntimeError(f"{name} {step}: swap files > {SWAP_KILL_GB} GB, child killed")
    if p.returncode != 0:
        raise RuntimeError(f"{name} {step}: child exited {p.returncode}")
    doc = json.loads(out.read_text())
    log(f"{name} {step}: done in {doc['wall_s']} s, peak RSS {doc['peak_rss_gb']} GB"
        + (f", {doc['dofs']} DOF, balance {doc['energy_balance']:.1e}, Picard {doc['picard_residual_K']:.1e} K"
           if step != "power" else ""))
    return doc


def main() -> int:
    from mfos import metrics as MX

    import e006_run as R

    cfg = R.load_config()
    CKPT.mkdir(parents=True, exist_ok=True)
    gates, dies, solves = [], [], []
    floor, lim = cfg["gci_floor_K"], cfg["f5_max_K"]
    for name, fam, dps in cfg["dev_layouts"]:
        pw = run_step(name, "power", gates)
        lv = [run_step(name, f"L{i}", gates) for i in (0, 1, 2)]
        z = run_step(name, "L1z2", gates)
        for d in (*lv, z):
            solves.append({k: d[k] for k in ("step", "layout", "dofs", "energy_balance", "picard_residual_K",
                                             "picard_iters", "wall_s", "peak_rss_gb")})
        for i in range(len(lv[0]["tj_max_K"])):
            f0, f1, f2 = (lv[j]["tj_max_K"][i] for j in range(3))
            g = MX.gci_capped(f0, f1, f2, floor)
            zt = float(MX.two_grid_term([f1], [z["tj_max_K"][i]])[0])
            br = R.a4(f0, f1, f2, floor)
            dies.append({"layout": name, "family": fam, "dies_per_switch": dps, "die": i, "skfem_gci": g,
                         "z_term": zt, "estimate": g + zt, "skfem_lv0": f0, "skfem_lv1": f1, "skfem_lv2": f2,
                         "skfem_z1": z["tj_max_K"][i], "a4_branch": br["a4_branch"], "p_obs": br["p_obs"],
                         "d1": br["d1"], "d2": br["d2"], "rise_skfem_lv2_K": f2 - cfg["coolant_K"]})
        log(f"{name}: power {pw['power_W']:.4f} W per die")
    mx = max(d["estimate"] for d in dies)
    worst = max(dies, key=lambda d: d["estimate"])
    eb = max(s["energy_balance"] for s in solves)
    pic = max(s["picard_residual_K"] for s in solves)
    doc = {"task": "T0196", "experiment": "E006", "mode": "F5 feasibility, development layouts only (dev seed "
           f"{DEV_SEED}); not evidence; no L2 value, L2-vs-scikit-fem difference or A3/A4 value computed or recorded",
           "estimator": "mfos.metrics.gci_capped(skfem_lv0, skfem_lv1, skfem_lv2, floor 1e-3 K) + "
                        "mfos.metrics.two_grid_term(skfem_lv1, skfem_z1)",
           "skfem_rule": cfg["skfem_rule"], "operating_point": {
               "coolant_K": cfg["coolant_K"], "h_W_m2K": cfg["h_W_m2K"], "target_rise_K": cfg["target_rise_K"],
               "power_W_per_die": {n: json.loads((CKPT / f"{n}_power.json").read_text())["power_W"]
                                   for n, _, _ in cfg["dev_layouts"]},
               "note": "power from e006_run.calibrate_power (L2 level-0, the operating point's definition); the "
                       "calibration rise is not recorded"},
           "dies": dies, "max_estimate": mx, "worst": {k: worst[k] for k in ("layout", "die", "skfem_gci", "z_term")},
           "f5_limit": lim, "f5_met": bool(mx <= lim), "margin_K": lim - mx,
           "max_skfem_gci": max(d["skfem_gci"] for d in dies), "max_z_term": max(d["z_term"] for d in dies),
           "n_branch": {b: sum(d["a4_branch"] == b for d in dies)
                        for b in ("exact", "monotone", "fast", "oscillatory", "divergent")},
           "f2_gates_on_these_solves": {"max_energy_balance": eb, "energy_tol": cfg["energy_tol"],
                                        "max_picard_residual_K": pic, "picard_tol_K": cfg["picard_tol_K"],
                                        "passed": bool(eb <= cfg["energy_tol"] and pic < cfg["picard_tol_K"])},
           "solves": solves, "memory_gates": gates}
    OUT.write_text(json.dumps(doc, indent=1) + "\n")
    log(f"wrote {OUT}: max estimate {mx:.4f} K vs limit {lim} K ({'met' if mx <= lim else 'EXCEEDED: stop'})")
    return 0 if mx <= lim else 3


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--child", nargs=3, metavar=("STEP", "LAYOUT", "OUT"))
    a = ap.parse_args()
    if a.child:
        child(a.child[0], a.child[1], Path(a.child[2]))
        sys.exit(0)
    sys.exit(main())
