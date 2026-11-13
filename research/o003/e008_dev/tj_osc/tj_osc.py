"""T0325: 2D_Case_4's non-monotone Tj over the frozen thermal levels -- stack variants V0-V4 on Case 4's twin.

Development geometry only (2D_Case_4, O006 pilot geometry). Never a judged reference: this script refuses any layout whose
fingerprint does not start with Case 4's reference (f4862196) or twin (d0dd6090) prefix before a variant is applied.
Research diagnosis input, NOT evidence (no ExperimentRun): the frozen thermal rule (research/o007_dev3/frozen_config.json
through the runner's config.fem_rule and rule_from) is used unchanged; only the stack is varied, as a dev-only input.

Layouts are rebuilt from committed code with the runner's dev path (e008_run.dev_reference('case4') then e008_run.prepare,
which calls generate.twin.twin exactly as the dev run did), never from a saved ctx.pkl.

Variants (thermal inputs only; the in-plane geometry is unchanged):
  V0  as in the dev run of 2026-11-13: die attach 0 um, 1 um 'solder' layer (PowerSynth 'none (M5)' -> SAC305, k 58).
  V1  V0 with a 50 um SAC305 die attach (stack.die_attach = SAC305, k 58 W/(m K) at 300 K, every die attach_thickness 50 um).
  V2  V0 with the 1 um layer removed: the 'solder' layer's thickness is set to 0 after construction (LayerStack refuses a
      zero thickness, so the frozen dataclass field is overwritten here, dev-only). layout_grid then merges the coincident
      z lines, so the z grid is exactly the four-layer stack's and no cell is solder (checked in grid_stats).
  V3  V1 + V2.
  V4  2D_Case_2R's recorded stack recipe (research/o003/references/2D_Case_2R.json 'stack' layers with their k, and 'spec'
      die_thickness_mm / attach_thickness_mm) on Case 4's geometry. Die and die-attach materials are not in that record:
      LayerStack's defaults (4H-SiC k 370, SAC305 k 58) are used, as for every Case 4 variant.

Subcommands:
  grid     --variants ... --which ... --levels ...       grid counts per level, no solve (cells across the 1 um layer, the
                                                         die and the attach; lateral cells across each die; nesting)
  run      --variants ... --which ... --levels ... --workdir DIR [--threads N] [--mem-cap-GB X] [--max-procs N]
           one subprocess per solve, result file per solve (resumable: an existing ok result is never re-solved);
           a job whose memory estimate exceeds the cap is skipped and recorded as such, never started
  summary  --workdir DIR                                 per variant and layout: per-die Tj per level, steps, gci_capped
                                                         and tj_bounds (mfos.metrics, floor 1e-3 K) when 3 levels exist
  saved    --saved DIR                                   read-only table of a saved dev-run work directory
  child    JOB.json                                      (internal) one solve
"""
from __future__ import annotations

import argparse
import dataclasses
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[4]
RUNNER = ROOT / "experiments/runners/e008_run.py"
REF_2R = ROOT / "research/o003/references/2D_Case_2R.json"
FP_PREFIX = {"reference": "f4862196", "twin": "d0dd6090"}
# Operating point of the 2026-11-13 dev run, read from its job files (2D_Case_4/solves/*thermal*.job.json): the frozen-rule
# calibration of Case 4's reference (config.operating_point: 60 K rise of the hottest die above 338.15 K at h = 5000).
POWER_W = 70.46451569603781
DEV_RUN_PHYS = {0: "ba3045ba8e", 1: "940de6f270", 2: "93700938d8"}  # the dev run's physics hashes (job file names)
ATTACH_M = 50e-6
VARIANTS = ("V0", "V1", "V2", "V3", "V4")
GCI_FLOOR_K = 1e-3  # config.gci.floor (O006: ten times the Picard tolerance)
# memory model of one Q1 solve, from the dev run's Case 4 solves (peak RSS 0.36 / 1.50 / 9.27 GB at 51 k / 365 k / 2.75 M
# nodes: ~3.2 kB per node + 0.3 GB); the estimate below is about 25 % above those measurements
MEM_BASE_GB, MEM_PER_NODE_GB = 0.5, 4.0e-6


def runner():
    if "e008_run" in sys.modules:
        return sys.modules["e008_run"]
    sp = importlib.util.spec_from_file_location("e008_run", RUNNER)
    R = importlib.util.module_from_spec(sp)
    sys.modules[sp.name] = R
    sp.loader.exec_module(R)
    return R


def fem():
    from moduleforge.solvers import thermal_fem
    return thermal_fem


def config() -> dict:
    return runner().load_spec()["config"]


def op_point(cfg: dict) -> tuple[float, float]:
    op = cfg["operating_point"]
    return float(op["h_W_m2K"]), float(op["coolant_K"])


def phys_hash(level: int, cfg: dict) -> str:
    """The runner's Driver.job physics hash of a thermal job (every physics input except the layout)."""
    h, tc = op_point(cfg)
    kw = {"level": level, "power_W": POWER_W, "fem_rule": dict(cfg["fem_rule"]), "h": h, "T_c": tc}
    return hashlib.sha256(json.dumps(kw, sort_keys=True, default=str).encode()).hexdigest()[:10]


def case4_layouts(cfg: dict) -> dict:
    """Reference and twin of 2D_Case_4, rebuilt from committed code by the runner's dev path; prefixes checked."""
    R = runner()
    rc = R.dev_reference("case4", cfg)
    rc = R.prepare(rc, cfg, 0, 0)
    out = {"reference": rc.reference, "twin": rc.twin}
    for k, lay in out.items():
        if lay is None or not lay.fingerprint().startswith(FP_PREFIX[k]):
            fp = None if lay is None else lay.fingerprint()
            raise SystemExit(f"Case 4 {k} fingerprint {fp} does not start with {FP_PREFIX[k]}: refusing (dev geometry only)")
    return out


def _with_attach(lay, t: float, stack):
    dies = [dataclasses.replace(d, attach_thickness=t) for d in lay.dies]
    return dataclasses.replace(lay, dies=dies, stack=stack)


def variant(lay, vid: str):
    """Variant ``vid`` of Case 4 layout ``lay`` (thermal inputs only)."""
    from moduleforge.geometry.stack import SIGMA_SOLDER, Layer
    st = lay.stack
    if vid == "V0":
        return lay
    if vid in ("V1", "V3"):
        att = Layer("die_attach", "SAC305", ATTACH_M, SIGMA_SOLDER, 58.0)
        lay = _with_attach(lay, ATTACH_M, dataclasses.replace(st, die_attach=att))
        st = lay.stack
    if vid in ("V2", "V3"):
        layers = []
        for la in st.layers:
            la = dataclasses.replace(la)  # a fresh object, so the shared stack is never mutated
            if la.name == "solder":
                object.__setattr__(la, "thickness", 0.0)  # LayerStack refuses 0; dev-only removal, see module docstring
            layers.append(la)
        new = dataclasses.replace(st)
        object.__setattr__(new, "layers", tuple(layers))
        return dataclasses.replace(lay, stack=new)
    if vid == "V4":
        rec = json.loads(REF_2R.read_text())
        old = {la.name: la for la in st.layers}
        layers = tuple(Layer(e["name"], e["material"], float(e["thickness_mm"]) * 1e-3, old[e["name"]].sigma, float(e["k"]))
                       for e in rec["stack"])
        sp = rec["spec"]
        t_die, t_att = float(sp["die_thickness_mm"]) * 1e-3, float(sp["attach_thickness_mm"]) * 1e-3
        new = dataclasses.replace(st, layers=layers, die_attach=Layer("die_attach", "SAC305", t_att, SIGMA_SOLDER, 58.0),
                                  die=dataclasses.replace(st.die, thickness=t_die))
        dies = [dataclasses.replace(d, attach_thickness=t_att, thickness=t_die) for d in lay.dies]
        return dataclasses.replace(lay, dies=dies, stack=new)
    if vid == "V1":
        return lay
    raise ValueError(vid)


def stack_record(lay) -> dict:
    st = lay.stack
    return {"layers": [[la.name, la.material, la.thickness, la.k] for la in st.layers],
            "die_attach": [st.die_attach.material, st.die_attach.k], "die": [st.die.material, st.die.k],
            "die_thickness_m": sorted({d.thickness for d in lay.dies}),
            "attach_thickness_m": sorted({d.attach_thickness for d in lay.dies})}


def layout_key(lay) -> str:
    """Fingerprint of the variant: the layout fingerprint plus the thermal stack numbers (V2's zero thickness included)."""
    s = json.dumps([lay.fingerprint(), stack_record(lay)], sort_keys=True, default=float)
    return hashlib.sha256(s.encode()).hexdigest()


def rule(cfg: dict):
    return runner().rule_from(dict(cfg["fem_rule"]))


# ------------------------------------------------------------------------------------------------ grid counts (no solve)
def _count(lines: np.ndarray, lo: float, hi: float) -> list[float]:
    d = np.diff(lines)
    mid = 0.5 * (lines[1:] + lines[:-1])
    return [float(v) for v in d[(mid > lo) & (mid < hi)]]


def grid_stats(lay, cfg: dict, level: int) -> dict:
    F = fem()
    h, tc = op_point(cfg)
    g = F.layout_grid(lay, POWER_W, h, tc, rule(cfg), level)
    st = lay.stack
    zb = [0.0]
    for la in st.layers:
        zb.append(zb[-1] + la.thickness)
    zl = np.asarray(g.z)
    per_layer = {}
    for i, la in enumerate(st.layers):
        c = _count(zl, zb[i], zb[i + 1])
        per_layer[la.name] = {"thickness_m": la.thickness, "cells": len(c), "dz_m": c[0] if c else None}
    d0 = lay.dies[0]
    zt = zb[-1]
    att = _count(zl, zt, zt + d0.attach_thickness) if d0.attach_thickness > 0 else []
    die = _count(zl, zt + d0.attach_thickness, zt + d0.attach_thickness + d0.thickness)
    dies = []
    for d in lay.dies:
        x0, y0, x1, y1 = d.bounds
        cx, cy = _count(np.asarray(g.x), x0, x1), _count(np.asarray(g.y), y0, y1)
        dies.append({"cells_x": len(cx), "cells_y": len(cy), "min_dx_m": min(cx), "max_dx_m": max(cx), "min_dy_m": min(cy),
                     "max_dy_m": max(cy),
                     "centre_is_node": bool(np.min(np.abs(np.asarray(g.x) - d.cx)) < 1e-9
                                            and np.min(np.abs(np.asarray(g.y) - d.cy)) < 1e-9)})
    mat = np.asarray(g.mat)
    lat = np.concatenate([np.diff(g.x), np.diff(g.y)])
    thin = per_layer["solder"]["dz_m"]
    return {"level": level, "nodes": int(F._count_nodes(mat)), "cells_xyz": list(mat.shape),
            "solder_cells_present": int((mat == 1).sum()), "z_per_layer": per_layer,
            "die_attach_cells": len(att), "die_attach_dz_m": att[0] if att else None,
            "die_cells_z": len(die), "die_dz_m": die[0], "dies": dies,
            "lateral_min_m": float(lat.min()), "lateral_max_m": float(lat.max()),
            "max_aspect_thin_layer": (float(lat.max() / thin) if thin else None),
            "x_lines": np.asarray(g.x).tolist(), "y_lines": np.asarray(g.y).tolist(), "z_lines": zl.tolist(),
            "grading_x": [float(v) for v in g.grading["x"]], "grading_y": [float(v) for v in g.grading["y"]]}


def _nested(coarse: list[float], fine: list[float]) -> bool:
    f = np.asarray(fine)
    return bool(all(np.min(np.abs(f - v)) < 1e-12 for v in coarse))


def cmd_grid(a) -> int:
    cfg = config()
    lays = case4_layouts(cfg)
    out = {}
    for vid in a.variants:
        for which in a.which:
            lay = variant(lays[which], vid)
            recs = [grid_stats(lay, cfg, lv) for lv in a.levels]
            for r0, r1 in zip(recs[:-1], recs[1:], strict=True):
                r1["nests_previous"] = {ax: _nested(r0[f"{ax}_lines"], r1[f"{ax}_lines"]) for ax in ("x", "y", "z")}
            for r in recs:
                if not a.keep_lines:
                    for k in ("x_lines", "y_lines", "z_lines"):
                        r.pop(k)
            out[f"{vid}/{which}"] = {"stack": stack_record(lay), "levels": recs}
            for r in recs:
                d = r["dies"][0]
                print(f"{vid} {which} L{r['level']}: nodes {r['nodes']:,} 1um-layer cells {r['z_per_layer']['solder']['cells']}"
                      f" die z {r['die_cells_z']} attach z {r['die_attach_cells']} die0 x {d['cells_x']} y {d['cells_y']}"
                      f" (dx {d['min_dx_m'] * 1e3:.4f}-{d['max_dx_m'] * 1e3:.4f} mm) centre node {d['centre_is_node']}"
                      f" nests {r.get('nests_previous')}", flush=True)
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(json.dumps(out, indent=1, default=float))
    return 0


# ------------------------------------------------------------------------------------------------ solves
def child(path: str) -> int:
    job = json.loads(Path(path).read_text())
    R, F = runner(), fem()
    t0 = time.perf_counter()
    try:
        cfg = config()
        lay = variant(case4_layouts(cfg)[job["which"]], job["variant"])
        if layout_key(lay) != job["layout_key"]:
            raise RuntimeError("variant layout key differs from the job's")
        ru = rule(cfg)
        h, tc = op_point(cfg)
        r = F.solve_layout(lay, POWER_W, h, tc, rule=ru, level=job["level"])
        rec = R._fem_rec(r, lay, job["level"], ru.amg_gs_sweeps)
        rec["tj_mean"] = [float(v) for v in r.tj_mean]
        rec["tj_centre"] = [F.node_value(r, d.cx, d.cy) for d in lay.dies]
        rec["q_W"] = float(np.sum(POWER_W * len(lay.dies)))
        rec.update(peak_GB=R._rss_gb(), threads=R._prov(), variant=job["variant"], which=job["which"],
                   layout_key=job["layout_key"], status="ok", job_wall_s=time.perf_counter() - t0)
    except Exception as e:  # recorded; the summary reports it
        rec = {"status": "failed", "error": f"{type(e).__name__}: {e}"[:3000], "variant": job["variant"],
               "which": job["which"], "level": job["level"]}
    out = Path(job["out"])
    tmp = out.with_suffix(".tmp")
    tmp.write_text(json.dumps(rec, default=float))
    tmp.replace(out)
    return 0 if rec["status"] == "ok" else 1


def _mem_total_GB() -> float:
    try:
        return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 1e9
    except (ValueError, OSError):
        return 16.0


def _rss_GB(pid: int) -> float:
    try:
        out = subprocess.run(["ps", "-o", "rss=", "-p", str(pid)], capture_output=True, text=True).stdout.strip()
        return float(out) * 1024 / 1e9 if out else 0.0
    except (OSError, ValueError):
        return 0.0


def make_jobs(a, cfg: dict) -> list[dict]:
    lays = case4_layouts(cfg)
    wd = Path(a.workdir)
    (wd / "solves").mkdir(parents=True, exist_ok=True)
    jobs = []
    for vid in a.variants:
        for which in a.which:
            lay = variant(lays[which], vid)
            key = layout_key(lay)
            for lv in a.levels:
                nodes = fem().estimate_dofs(lay, rule(cfg), lv)
                ph = phys_hash(lv, cfg)
                out = wd / "solves" / f"{vid}__{which}__L{lv}__{key[:12]}__{ph}.json"
                jobs.append({"variant": vid, "which": which, "level": lv, "layout_key": key, "phys": ph,
                             "fingerprint": lay.fingerprint(), "nodes_est": nodes,
                             "mem_GB": MEM_BASE_GB + MEM_PER_NODE_GB * nodes, "out": str(out), "stack": stack_record(lay)})
    return jobs


def done(job: dict) -> bool:
    p = Path(job["out"])
    if not p.exists():
        return False
    try:
        return json.loads(p.read_text()).get("status") == "ok"
    except json.JSONDecodeError:
        return False


def cmd_run(a) -> int:
    cfg = config()
    for lv in a.levels:
        if phys_hash(lv, cfg) != DEV_RUN_PHYS[lv]:
            raise SystemExit(f"level {lv}: physics hash {phys_hash(lv, cfg)} is not the dev run's {DEV_RUN_PHYS[lv]}")
    cap = a.mem_cap_GB if a.mem_cap_GB else 0.85 * _mem_total_GB()
    slots = a.max_procs if a.max_procs else 1  # explicit --max-procs only (never sized from the CPU count)
    kill = a.kill_GB if a.kill_GB else cap
    jobs = make_jobs(a, cfg)
    wd = Path(a.workdir)
    (wd / "jobs.json").write_text(json.dumps(jobs, indent=1, default=float))
    todo = [j for j in jobs if not done(j)]
    skipped = [j for j in todo if j["mem_GB"] > cap]
    for j in skipped:
        Path(j["out"]).write_text(json.dumps({"status": "skipped: memory", "mem_GB": j["mem_GB"], "cap_GB": cap,
                                              "variant": j["variant"], "which": j["which"], "level": j["level"]}))
        print(f"skip {Path(j['out']).name}: estimate {j['mem_GB']:.1f} GB > cap {cap:.1f} GB", flush=True)
    todo = sorted((j for j in todo if j["mem_GB"] <= cap), key=lambda j: -j["mem_GB"])  # largest first
    print(f"{len(jobs)} jobs, {len(jobs) - len(todo) - len(skipped)} done, {len(todo)} to run; cap {cap:.1f} GB,"
          f" {slots} slots x {a.threads} threads", flush=True)
    R = runner()
    env = R.child_env(a.threads)
    running: list[tuple[dict, subprocess.Popen, float]] = []
    fails = 0
    while todo or running:
        used = sum(j["mem_GB"] for j, _, _ in running)
        for j in list(todo):
            if len(running) < slots and used + j["mem_GB"] <= cap:
                jp = Path(j["out"]).with_suffix(".job.json")
                jp.write_text(json.dumps(j, default=float))
                log = open(Path(j["out"]).with_suffix(".log"), "w")  # noqa: SIM115
                p = subprocess.Popen([sys.executable, __file__, "child", str(jp)], env=env, stdout=log,
                                     stderr=subprocess.STDOUT, cwd=str(ROOT))
                running.append((j, p, time.time()))
                todo.remove(j)
                used += j["mem_GB"]
                print(f"start {Path(j['out']).name} (est {j['mem_GB']:.1f} GB)", flush=True)
        time.sleep(2.0)
        for item in list(running):
            j, p, t0 = item
            rss = _rss_GB(p.pid)
            if p.poll() is None and rss > kill:
                p.kill()
                p.wait()
                Path(j["out"]).write_text(json.dumps({"status": "failed", "error": f"killed: RSS {rss:.2f} GB > {kill} GB",
                                                      "variant": j["variant"], "which": j["which"], "level": j["level"]}))
            if p.poll() is not None:
                running.remove(item)
                ok = done(j)
                fails += 0 if ok else 1
                print(f"{'ok  ' if ok else 'FAIL'} {Path(j['out']).name} {time.time() - t0:.0f} s", flush=True)
    return 1 if fails else 0


# ------------------------------------------------------------------------------------------------ summary
def _metrics():
    from mfos import metrics
    return metrics


def summarise(recs: dict) -> dict:
    """recs: {(variant, which): {level: record}} -> per-die sequences, steps, GCI and tj_bounds."""
    M = _metrics()
    out = {}
    for (vid, which), by in sorted(recs.items()):
        lvls = sorted(by)
        tj = [by[lv]["tj"] for lv in lvls]
        nd = len(tj[0])
        dies = []
        for i in range(nd):
            seq = [t[i] for t in tj]
            e = {"tj": seq, "steps": [b - a for a, b in zip(seq[:-1], seq[1:], strict=True)]}
            for k in ("tj_centre", "tj_mean"):
                if all(k in by[lv] for lv in lvls):
                    s = [by[lv][k][i] for lv in lvls]
                    e[k] = s
                    e[k + "_steps"] = [b - a for a, b in zip(s[:-1], s[1:], strict=True)]
            e["node"] = [by[lv]["tj_node"][i] for lv in lvls]
            if lvls == [0, 1, 2]:
                g = M.gci_capped(*seq, floor=GCI_FLOOR_K)
                e["gci_capped"] = g
                e["rho"] = e["steps"][1] / e["steps"][0] if e["steps"][0] else None
            dies.append(e)
        s = {"levels": lvls, "nodes": [by[lv]["nodes"] for lv in lvls], "dies": dies,
             "energy_balance": [by[lv]["energy_balance"] for lv in lvls],
             "picard": [[by[lv]["picard_iters"], by[lv]["picard_residual_K"]] for lv in lvls],
             "cg": [[by[lv].get("cg_max_iterations"), by[lv].get("cg_hit_maxiter")] for lv in lvls],
             "peak_GB": [by[lv].get("peak_GB") for lv in lvls], "wall_s": [by[lv].get("wall_s") for lv in lvls]}
        if all("tj_mean" in by[lv] for lv in lvls):
            pm = [float(np.mean(by[lv]["tj_mean"])) for lv in lvls]  # equal power per die: power-weighted mean
            s["tj_mean_powerweighted"] = pm
        if lvls == [0, 1, 2]:
            b = M.tj_bounds([d["tj"] for d in dies], floor=GCI_FLOOR_K, n_dies=nd)
            s["tj_bounds"] = {"t_max": b[0], "gci_max": b[1], "upper": b[2], "lower": b[3], "n_inf": b[4]}
        out[f"{vid}/{which}"] = s
    return out


def _load(dirpath: Path, saved: bool) -> dict:
    recs: dict = {}
    for f in sorted(dirpath.glob("*.json")):
        if f.name.endswith(".job.json"):
            continue
        r = json.loads(f.read_text())
        if r.get("status") != "ok":
            continue
        if saved:
            if "thermal" not in f.name:
                continue
            j = json.loads((f.parent / (f.name[:-5] + ".job.json")).read_text())
            key = (f.name[:8], j["which"])
        else:
            key = (r["variant"], r["which"])
        recs.setdefault(key, {})[int(r["level"])] = r
    return recs


def cmd_summary(a) -> int:
    wd = Path(a.workdir)
    s = summarise(_load(wd / "solves", saved=False))
    bad = []
    for f in sorted((wd / "solves").glob("*.json")):
        if not f.name.endswith(".job.json"):
            st = json.loads(f.read_text()).get("status")
            if st != "ok":
                bad.append([f.name, st])
    s["_not_ok"] = bad
    (wd / "summary.json").write_text(json.dumps(s, indent=1, default=float))
    _print(s)
    return 0


def _print(s: dict) -> None:
    for k, v in s.items():
        if k.startswith("_"):
            if v:
                print("not ok:", v)
            continue
        print(f"== {k} levels {v['levels']} nodes {v['nodes']} EB {['%.1e' % x for x in v['energy_balance']]}")
        for i, d in enumerate(v["dies"]):
            g = d.get("gci_capped")
            line = f"  die {i}: Tj {[round(x, 3) for x in d['tj']]} steps {[round(x, 4) for x in d['steps']]}"
            if "tj_centre" in d:
                line += f" centre steps {[round(x, 4) for x in d['tj_centre_steps']]}"
            if "tj_mean" in d:
                line += f" mean steps {[round(x, 4) for x in d['tj_mean_steps']]}"
            if g is not None:
                line += f" GCI {g:.4g}"
            print(line)
        if "tj_bounds" in v:
            print("  tj_bounds", v["tj_bounds"])


def cmd_saved(a) -> int:
    root = Path(a.saved)
    out = {}
    for geom in sorted(p for p in root.iterdir() if (p / "solves").is_dir()):
        s = summarise(_load(geom / "solves", saved=True))
        out[geom.name] = s
        print(f"######## {geom.name}")
        _print(s)
    if a.out:
        Path(a.out).write_text(json.dumps(out, indent=1, default=float))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p):
        p.add_argument("--variants", type=lambda s: s.split(","), default=list(VARIANTS))
        p.add_argument("--which", type=lambda s: s.split(","), default=["twin"])
        p.add_argument("--levels", type=lambda s: [int(v) for v in s.split(",")], default=[0, 1])

    g = sub.add_parser("grid")
    common(g)
    g.add_argument("--out")
    g.add_argument("--keep-lines", action="store_true")
    r = sub.add_parser("run")
    common(r)
    r.add_argument("--workdir", required=True)
    r.add_argument("--threads", type=int, default=2)
    r.add_argument("--mem-cap-GB", type=float, default=None)
    r.add_argument("--max-procs", type=int, default=None)
    r.add_argument("--kill-GB", type=float, default=None)
    s = sub.add_parser("summary")
    s.add_argument("--workdir", required=True)
    sv = sub.add_parser("saved")
    sv.add_argument("--saved", required=True)
    sv.add_argument("--out")
    c = sub.add_parser("child")
    c.add_argument("job")
    a = ap.parse_args(argv)
    for v in getattr(a, "variants", []):
        if v not in VARIANTS:
            ap.error(f"unknown variant {v}")
    for w in getattr(a, "which", []):
        if w not in FP_PREFIX:
            ap.error(f"--which must be reference and/or twin, got {w}")
    return {"grid": cmd_grid, "run": cmd_run, "summary": cmd_summary, "saved": cmd_saved,
            "child": lambda a: child(a.job)}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
