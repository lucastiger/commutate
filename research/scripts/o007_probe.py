"""O007 feasibility probe (T0225): N-layer source-edge resolution, Q2 CG sliver-vs-conditioning discriminator, E009 cost.

Pre-registration: research/notes/o007-probe.md section 0 (configurations, grading offsets, go/no-go rule), committed
before any solve; its hash is recorded in probe.json as ``preregistration_commit``. Research only: the production solver
``moduleforge.solvers.thermal_fem`` is used unchanged (CG cap 400, LINEAR_RTOL, SNAP_FRACTION untouched). Reused by
import from research/scripts/o007_dev_study.py (T0207): load_refs (sha256 gate), box_problem, the CG logger with the
'cg_only' counter, the child-process watchdog, min_cell_ratio (lateral), a4 (mfos.metrics.gci_capped, floor 1e-3 K).

Modes
  --plan     grid-only DOF counts of every configuration (no solve) -> research/o007_probe/plan.json
  (default)  probe solves within the local memory rule (one child process at a time, <= 5 GB, or <= 10 GB when
             memory_pressure shows >= 50 % free and swap < 4 GB); cached in research/o007_probe/cache/; then --report
  --full     every level under 0.85 x physical memory, for a founder burst:
             scripts/burst_gcp.sh --cmd "uv run python research/scripts/o007_probe.py --full" research/o007_probe
  --report   rebuild research/o007_probe/probe.json from the cache (no solve)
  --worker   internal: one solve
SI units, kelvin, float64.
"""
from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
import threading
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "research" / "scripts")]

import o007_dev_study as DS  # noqa: E402  (T0207 helpers, read-only use)

FEM, R = DS.FEM, DS.R
OUT = ROOT / "research" / "o007_probe"
CACHE = OUT / "cache"
NOTE = ROOT / "research" / "notes" / "o007-probe.md"
DEV_JSON = ROOT / "research" / "o007_dev" / "dev_study.json"
NL = "nlayer_dbc"
BURST_USABLE_GB = 0.85 * 256.0  # n2-highmem-32
GO_ABS_K, CG_FLAG, P_LO, P_HI = 0.040, 300, 0.5, 2.0  # section 0.4
LOCAL_SOFT_GB, LOCAL_HARD_GB = 5.0, 10.0
EST_MARGIN = 1.15
WALL_GROWTH = 1.3  # per level beyond the measured one (CG growth, as T0207) [S]

# ---- pre-registered configurations (note sec. 0.1); lengths in m. At most four in total across parts 1 and 2.
GRADING = {"first_offset_m": 0.1e-3, "ratio": 2.5, "max_offset_m": 4.0e-3, "min_gap_fraction": 0.5}
CONFIGS = {
    "p1_q2h4_maxlines": {"part": 1, "order": 2, "h0": 4e-3, "near_margin": 2e-3, "dz_max": 5e-3, "lines": "production",
                         "grading": False, "problems": ("case1a", "case2"), "levels": (0, 1)},
    "p1_q2h4_centroid": {"part": 1, "order": 2, "h0": 4e-3, "near_margin": 2e-3, "dz_max": 5e-3, "lines": "centroid",
                         "grading": False, "problems": ("case1a", "case2"), "levels": (0, 1)},
    "a_q1h4_graded": {"part": 2, "option": "option_a", "order": 1, "h0": 4e-3, "near_margin": 2e-3, "dz_max": 1e-3,
                      "lines": "production", "grading": True, "problems": (NL,), "levels": (0, 1, 2)},
    "b_q2h1": {"part": 2, "option": "option_b", "order": 2, "h0": 1e-3, "near_margin": 0.5e-3, "dz_max": 5e-3,
               "lines": "production", "grading": False, "problems": (NL,), "levels": (0, 1, 2)},
}
E009_CASES = ("case1a", "case1b", "case2", "case3", NL, "mms")


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def rule(cid: str) -> FEM.GridRule:
    c = CONFIGS[cid]
    return FEM.GridRule(h0=c["h0"], nz={}, default_nz=DS.NZ_MIN, zrefine=True, near_margin=c["near_margin"],
                        element_order=c["order"], dz_max=c["dz_max"])


# ------------------------------------------------------------------------------------------------ grading (option a)
def offsets() -> list[float]:
    o, out = GRADING["first_offset_m"], []
    while o <= GRADING["max_offset_m"] * (1 + 1e-9):
        out.append(o)
        o *= GRADING["ratio"]
    return out


def grading_lines(extents: list[tuple[float, float]], lo: float, hi: float, fixed: list[float]) -> list[float]:
    """Geometric offsets on both sides of every source edge along one axis (fixed by geometry only). Outward offsets
    up to max_offset; inward offsets only below the half-width. Candidates are taken finest first; one is dropped if it
    lies closer than min_gap_fraction x its own offset step to a fixed line (domain ends, source edges, centroids,
    mandatory point lines) or to an accepted grading line (no slivers from overlapping gradings)."""
    offs = offsets()
    steps = [offs[0]] + [b - a for a, b in zip(offs[:-1], offs[1:], strict=True)]
    cand = []
    for e0, e1 in extents:
        half = 0.5 * (e1 - e0)
        for o, s in zip(offs, steps, strict=True):
            cand += [(s, e0 - o), (s, e1 + o)]
            if o < half - GRADING["min_gap_fraction"] * s:
                cand += [(s, e0 + o), (s, e1 - o)]
    acc = [float(v) for v in fixed] + [lo, hi] + [v for e in extents for v in e]
    out: list[float] = []
    for s, v in sorted(cand):
        if not lo < v < hi:
            continue
        if min(abs(v - w) for w in acc) < GRADING["min_gap_fraction"] * s:
            continue
        acc.append(v)
        out.append(v)
    return sorted(out)


def box_setup(cid: str, prob: str, ser: dict) -> dict:
    b = DS.box_problem(ser, prob)
    c = CONFIGS[cid]
    xs, ys = (list(b["extra"][0]), list(b["extra"][1])) if c["lines"] == "production" else ([], [])
    if c["grading"]:
        cx = [0.5 * (s[0] + s[2]) for s in b["srcs"]]
        cy = [0.5 * (s[1] + s[3]) for s in b["srcs"]]
        xs += grading_lines([(s[0], s[2]) for s in b["srcs"]], 0.0, b["a"], cx + xs)
        ys += grading_lines([(s[1], s[3]) for s in b["srcs"]], 0.0, b["b"], cy + ys)
    b["extra"] = (xs, ys, None)
    return b


def box_grid(cid: str, prob: str, lv: int, ser: dict):
    b = box_setup(cid, prob, ser)
    return FEM.box_stack_grid(b["a"], b["b"], b["layers"], b["h"], b["Tc"], b["srcs"], rule=rule(cid), level=lv,
                              extra_lines=b["extra"])


def layout_grid(cid: str, prob: str, lv: int, mms: dict):
    """E009 layout-mode grids (cost only): manufactured case with its point lines, dev layouts without; the same die-edge
    grading as box-stack mode when the configuration grades."""
    lay = R.mms_layout() if prob == "mms" else DS.dev_layout(prob)
    ex = list(DS.mms_extra(mms)) if prob == "mms" else [[], [], None]
    if CONFIGS[cid]["grading"]:
        bx, by = lay.baseplate_outline.bounds[0::2], lay.baseplate_outline.bounds[1::2]
        ext_x, ext_y = [(d.bounds[0], d.bounds[2]) for d in lay.dies], [(d.bounds[1], d.bounds[3]) for d in lay.dies]
        ex[0] = list(ex[0]) + grading_lines(ext_x, bx[0], bx[1], list(ex[0]))
        ex[1] = list(ex[1]) + grading_lines(ext_y, by[0], by[1], list(ex[1]))
    if prob == "mms":
        return FEM.layout_grid(lay, 0.0, 1.0, DS.MMS_TC, rule(cid), lv, tuple(ex))
    return FEM.layout_grid(lay, 1.0, DS.H_OP, DS.COOLANT_K, rule(cid), lv, tuple(ex) if CONFIGS[cid]["grading"] else None)


def cell_ratio_xyz(g) -> dict:
    """Smallest neighbour cell-width ratio per axis, and the smallest cell width per axis [m]."""
    out = {}
    for ax, v in (("x", g.x), ("y", g.y), ("z", g.z)):
        w = np.diff(v)
        out[f"min_ratio_{ax}"] = float(np.min(np.minimum(w[1:], w[:-1]) / np.maximum(w[1:], w[:-1])))
        out[f"min_cell_{ax}_m"] = float(w.min())
    out["min_ratio_lateral"] = DS.min_cell_ratio(g)
    return out


# ------------------------------------------------------------------------------------------------ worker
def solve(spec: dict) -> dict:
    ser = json.loads(DS.SERIES_PATH.read_text())["payload"]
    cid, prob, lv = spec["cid"], spec["problem"], spec["level"]
    b = box_setup(cid, prob, ser)
    r = FEM.solve_box_stack(b["a"], b["b"], b["layers"], b["h"], b["Tc"], b["srcs"], rule=rule(cid), level=lv,
                            extra_lines=b["extra"])
    pts = []
    for row in b["rows"]:
        si = b["names"].index(row["source"])
        p = {"source": row["source"], "point": row["point"], "x_req": row["x_m"], "y_req": row["y_m"]}
        if row["point"] == "mean":
            p.update(T=float(r.tj_mean[si]), x_used=None, y_used=None)
        elif row["point"] == "max" and CONFIGS[cid]["lines"] == "centroid":
            p.update(T=None, x_used=None, y_used=None, note="no maximum line in the centroid-only variant (CG count only)")
        else:
            xu, yu = DS._used(r, "x", row["x_m"]), DS._used(r, "y", row["y_m"])
            p.update(T=FEM.node_value(r, xu, yu), x_used=xu, y_used=yu)
        pts.append(p)
    m = r.meta
    return {"points": pts, "dofs": int(r.dofs), "wall_s": float(r.wall_s), "energy_balance": float(r.energy_balance),
            "picard_iters": int(r.picard_iters), "picard_residual": float(r.picard_residual), "n_lines": m["n_lines"],
            "snapped_lines": m["snapped_lines"], "max_snap_m": m["max_snap_m"],
            "grid": cell_ratio_xyz(box_grid(cid, prob, lv, ser))}


def worker(spec_path: str) -> int:
    spec = json.loads(Path(spec_path).read_text())
    threading.Thread(target=DS._watchdog, args=(spec["hard_cap_gb"] * 1e9,), daemon=True).start()
    DS.install_cg_logger()
    base = DS.peak_rss_bytes()
    out = solve(spec)
    out.update(status="ok", spec=spec, base_rss_bytes=base, peak_rss_bytes=DS.peak_rss_bytes(), cg=DS.CG_LOG,
               cg_max_iters=max((c["iters"] for c in DS.CG_LOG), default=0),
               cg_final_true_rel=[c["true_rel"] for c in DS.CG_LOG], platform=sys.platform)
    Path(spec["out"]).write_text(json.dumps(out))
    return 0


# ------------------------------------------------------------------------------------------------ orchestration
def measured_bpd(order: int) -> float:
    """Whole-process peak bytes/DOF of this element order: max over measured solves with >= 1 M DOF (T0207
    dev_study.json, every candidate's cases and layouts, and this probe's cache)."""
    dev = json.loads(DEV_JSON.read_text())["candidates"]
    vals = []
    for c in dev.values():
        if c["config"]["element_order"] != order:
            continue
        for grp in ("cases", "layouts"):
            for v in c[grp].values():
                vals += [b for n, b in zip(v.get("dofs", []), v.get("bytes_per_dof", []), strict=False) if n >= 1e6]
    for p in CACHE.glob("*.json"):
        if p.name.endswith(".spec.json"):
            continue
        d = json.loads(p.read_text())
        if d.get("status") == "ok" and d["dofs"] >= 1e6 and CONFIGS[d["spec"]["cid"]]["order"] == order:
            vals.append(d["peak_rss_bytes"] / d["dofs"])
    return max(vals)


def gate(est_gb: float, full: bool) -> tuple[bool, str]:
    if full:
        phys = FEM.physical_memory_bytes() / 1e9
        return est_gb <= 0.85 * phys, f"full: est {est_gb:.1f} GB vs 0.85 x {phys:.0f} GB"
    if est_gb <= LOCAL_SOFT_GB:
        return True, f"est {est_gb:.2f} GB <= {LOCAL_SOFT_GB} GB"
    if est_gb > LOCAL_HARD_GB:
        return False, f"est {est_gb:.1f} GB > {LOCAL_HARD_GB} GB local cap"
    for _ in range(4):
        free, swap = DS.mem_free_pct(), DS.swap_used_gb()
        if free is not None and free >= 50 and swap is not None and swap < 4:
            return True, f"est {est_gb:.1f} GB; memory_pressure free {free:.0f} %, swap(proxy) {swap:.1f} GB"
        log(f"  waiting: est {est_gb:.1f} GB, free {free} %, swap {swap} GB")
        time.sleep(180)
    return False, f"est {est_gb:.1f} GB: memory_pressure/swap condition not met after 12 min"


def run_one(cid: str, prob: str, lv: int, ser: dict, full: bool) -> dict:
    key = f"{cid}__{prob}__L{lv}"
    path = CACHE / f"{key}.json"
    if path.exists():
        d = json.loads(path.read_text())
        if d.get("status") == "ok" or not full:
            return d
    dofs = DS.count_dofs(box_grid(cid, prob, lv, ser))
    est = dofs * measured_bpd(CONFIGS[cid]["order"]) * EST_MARGIN / 1e9
    ok, why = gate(est, full)
    if not ok:
        log(f"  SKIP {key}: {dofs} DOF, {why}")
        return {"status": "skipped_memory", "dofs": dofs, "est_gb": est, "reason": why}
    hard = 0.9 * FEM.physical_memory_bytes() / 1e9 if full else LOCAL_HARD_GB
    spec = {"cid": cid, "problem": prob, "level": lv, "out": str(path), "hard_cap_gb": hard}
    sp = CACHE / f"{key}.spec.json"
    sp.write_text(json.dumps(spec))
    log(f"  solve {key}: {dofs} DOF, {why}")
    t0 = time.perf_counter()
    pr = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--worker", str(sp)], capture_output=True,
                        text=True, timeout=6 * 3600)
    if pr.returncode != 0 or not path.exists():
        st = {3: "killed_memory", 4: "killed_swap"}.get(pr.returncode, "failed")
        rec = {"status": st, "returncode": pr.returncode, "dofs": dofs, "est_gb": est, "spec": spec,
               "wall_s": time.perf_counter() - t0, "stderr_tail": (pr.stdout + pr.stderr)[-3000:]}
        path.write_text(json.dumps(rec))
        log(f"  {st.upper()} {key}: rc {pr.returncode}: {rec['stderr_tail'][-300:]}")
        return rec
    d = json.loads(path.read_text())
    log(f"  done {key}: {d['dofs']} DOF, {d['wall_s']:.1f} s, peak {d['peak_rss_bytes'] / 1e9:.2f} GB, "
        f"CG max {DS.cg_max(d)}, eb {d['energy_balance']:.1e}")
    return d


def study(full: bool) -> None:
    ser, _, _ = DS.load_refs()
    CACHE.mkdir(parents=True, exist_ok=True)
    for lv in (0, 1, 2):  # coarse to fine, one solve at a time
        for cid, c in CONFIGS.items():
            if lv in c["levels"]:
                for prob in c["problems"]:
                    prev = [json.loads((CACHE / f"{cid}__{prob}__L{q}.json").read_text()).get("status")
                            if (CACHE / f"{cid}__{prob}__L{q}.json").exists() else None for q in range(lv)]
                    if all(s == "ok" for s in prev):
                        run_one(cid, prob, lv, ser, full)


# ------------------------------------------------------------------------------------------------ analysis
def load(cid: str, prob: str, lv: int) -> dict | None:
    p = CACHE / f"{cid}__{prob}__L{lv}.json"
    return json.loads(p.read_text()) if p.exists() else None


def cg_part(ser: dict) -> dict:
    out: dict = {}
    for prob, short in (("case1a", "case1a"), ("case2", "case2")):
        out[short] = {}
        for cid, var in (("p1_q2h4_maxlines", "with_max_lines"), ("p1_q2h4_centroid", "centroid_only")):
            runs = {lv: load(cid, prob, lv) for lv in CONFIGS[cid]["levels"]}
            ok = {lv: d for lv, d in runs.items() if d and d.get("status") == "ok"}
            per = {f"L{lv}": {"dofs": d["dofs"], "cg_iters_per_picard": [DS.cg_iters(c) for c in d["cg"]],
                              "cg_max_iterations": DS.cg_max(d),
                              "final_rel_residual": max(c["true_rel"] or 0.0 for c in d["cg"]),
                              "hit_cap": any(c["hit_cap"] for c in d["cg"]), "grid": d["grid"],
                              "n_lines": d["n_lines"], "wall_s": d["wall_s"], "peak_rss_GB": d["peak_rss_bytes"] / 1e9,
                              "energy_balance": d["energy_balance"]} for lv, d in ok.items()}
            out[short][var] = {"config": cid, "levels_run": sorted(ok), "per_level": per,
                               "cg_max_iterations": int(max((v["cg_max_iterations"] for v in per.values()), default=-1)),
                               "final_rel_residual": max((v["final_rel_residual"] for v in per.values()), default=None),
                               "min_cell_ratio": min((v["grid"]["min_ratio_lateral"] for v in per.values()), default=None)}
        w, c = out[short]["with_max_lines"]["cg_max_iterations"], out[short]["centroid_only"]["cg_max_iterations"]
        if w < 0 or c < 0:
            rd = "incomplete"
        elif w > CG_FLAG and c <= CG_FLAG:
            rd = "slivers (fixable by the line or snap policy)"
        elif w > CG_FLAG and c > CG_FLAG:
            rd = "conditioning (weak-Robin plates; needs a preconditioner change)"
        elif w <= CG_FLAG and c <= CG_FLAG:
            rd = "no headroom loss at levels 0-1 (not discriminating at these levels)"
        else:
            rd = "centroid-only worse than with maximum lines (neither reading)"
        out[short]["reading"] = rd
    return out


def nlayer_part(ser: dict) -> dict:
    cs = ser["cases"][NL]
    scale = cs["scale_K"]
    rows = [r for r in ser["rows"] if r["case"] == NL]
    out = {}
    for cid, c in CONFIGS.items():
        if c["part"] != 2:
            continue
        runs = [(lv, load(cid, NL, lv)) for lv in c["levels"]]
        ok = []
        for lv, d in runs:
            if d and d.get("status") == "ok":
                ok.append((lv, d))
            else:
                break
        not_run = {f"L{lv}": {k: (d or {"status": "not_run"}).get(k) for k in ("status", "dofs", "est_gb", "reason")}
                   for lv, d in runs if lv not in [q for q, _ in ok]}
        pts = []
        for i, row in enumerate(rows):
            vals = [d["points"][i]["T"] for _, d in ok]
            assert all(d["points"][i]["source"] == row["source"] and d["points"][i]["point"] == row["point"] for _, d in ok)
            err = [v - row["T_K"] for v in vals]
            e = {"source": row["source"], "point": row["point"], "T_ref_K": row["T_K"], "values_K": vals,
                 "signed_err_K": err, "abs_err_K": [abs(v) for v in err], "scaled_err": [abs(v) / scale for v in err],
                 "x_used": [d["points"][i]["x_used"] for _, d in ok], "y_used": [d["points"][i]["y_used"] for _, d in ok]}
            if len(vals) >= 2 and err[-2] * err[-1] > 0 and abs(err[-1]) > 0:
                e["p_ref"] = math.log2(abs(err[-2]) / abs(err[-1]))
            else:
                e["p_ref"] = None
            if len(vals) >= 3:
                e.update({k: v for k, v in DS.a4(vals).items()})
            pts.append(e)
        mae = [max(p["abs_err_K"][j] for p in pts) for j in range(len(ok))]
        mse = [max(p["scaled_err"][j] for p in pts) for j in range(len(ok))]
        arg = [max(pts, key=lambda p, j=j: p["abs_err_K"][j]) for j in range(len(ok))]
        rec = {"config": {k: v for k, v in c.items() if k != "problems"}, "grading": GRADING if c["grading"] else None,
               "levels_run": [lv for lv, _ in ok], "levels_not_run": not_run,
               "dof": [d["dofs"] for _, d in ok], "max_abs_err_K": mae, "max_scaled_err": mse,
               "argmax_point": [f"{p['source']} {p['point']}" for p in arg],
               "peak_rss_GB": [d["peak_rss_bytes"] / 1e9 for _, d in ok], "wall_s": [d["wall_s"] for _, d in ok],
               "cg_max_iterations_per_level": [DS.cg_max(d) for _, d in ok],
               "cg_max_iterations": max((DS.cg_max(d) for _, d in ok), default=None),
               "cg_final_rel_residual": [max(c2["true_rel"] or 0.0 for c2 in d["cg"]) for _, d in ok],
               "energy_balance": [d["energy_balance"] for _, d in ok], "grid": [d["grid"] for _, d in ok],
               "n_lines": [d["n_lines"] for _, d in ok], "max_snap_m": [d["max_snap_m"] for _, d in ok],
               "points": pts}
        if len(ok) >= 3:
            g = [p["gci_K"] for p in pts]
            gn = [DS._gnum(v) for v in g]
            rec["gci_K"] = max(gn) if all(math.isfinite(v) for v in gn) else "inf"
            rec["gci_per_point"] = {f"{p['source']} {p['point']}": {"gci_K": p["gci_K"], "branch": p["a4_branch"],
                                                                    "p_obs": p["p_obs"]} for p in pts}
        else:
            rec["gci_K"] = None
            rec["gci_note"] = f"n/a ({len(ok)} levels run; gci_capped needs three)"
        # observed order of the A2 metric from the reference errors of the two finest measured levels; extrapolation [S]
        if len(mae) >= 2 and mae[-1] > 0:
            p = math.log2(mae[-2] / mae[-1])
            rec["observed_order_A2"] = p
            rec["extrapolated_next_level_err_K_S"] = mae[-1] * 2.0 ** (-p)
            rec["extrapolated_level"] = rec["levels_run"][-1] + 1
            rec["extrapolation_label"] = "[S] Richardson from reference errors at the two finest measured levels"
        out[cid] = rec
    return out


def count_cost(cid: str, ser: dict, mms: dict) -> dict:
    """Part 3: exact DOF of every E009 scikit-fem solve under this configuration's rule (no solve)."""
    cache = OUT / "cost_dofs.json"
    allc = json.loads(cache.read_text()) if cache.exists() else {}
    key = json.dumps({"cfg": CONFIGS[cid], "grading": GRADING}, sort_keys=True)
    if allc.get(cid, {}).get("key") != key:
        d: dict = {}
        for prob in E009_CASES + DS.LAYOUTS:
            for lv in (0, 1, 2):
                g = box_grid(cid, prob, lv, ser) if prob in DS.BOX else layout_grid(cid, prob, lv, mms)
                d[f"{prob}__L{lv}"] = DS.count_dofs(g)
                del g
        allc[cid] = {"key": key, "dofs": d}
        cache.write_text(json.dumps(allc, indent=1))
    return allc[cid]["dofs"]


def cost_part(ser: dict, mms: dict, nl: dict) -> dict:
    out = {}
    for cid in nl:
        bpd = measured_bpd(CONFIGS[cid]["order"])
        d = count_cost(cid, ser, mms)
        fresh = {f"fresh_L{lv}": int(math.ceil(1.5 * max(d[f"{n}__L{lv}"] for n in DS.LAYOUTS))) for lv in (0, 1, 2)}
        solves = dict(d)
        for k, v in fresh.items():  # three fresh layouts, one per generator family
            for i in range(3):
                solves[f"fresh{i + 1}__{k.split('_')[1]}"] = v
        peak = {k: v * bpd / 1e9 for k, v in solves.items()}
        worst = max(peak, key=peak.get)
        # wall time: s/DOF of the largest measured probe solve of this configuration, x 1.3 per level beyond it [S]
        meas = [(x["dofs"], x["wall_s"], lv) for lv in (0, 1, 2) if (x := load(cid, NL, lv)) and x.get("status") == "ok"]
        if meas:
            n0, w0, l0 = max(meas)
            spd = w0 / n0
        else:
            spd, l0 = None, 0
        hours = (sum(v * spd * WALL_GROWTH ** max(0, int(k[-1]) - l0) for k, v in solves.items()) / 3600.0
                 if spd else None)
        out[cid] = {"bytes_per_dof": bpd, "bytes_per_dof_rule": "max measured whole-process bytes/DOF of the same element "
                    "order at >= 1 M DOF (dev_study.json and this probe)", "dofs": solves,
                    "e009_finest_peak_GB": peak[worst], "e009_finest_peak_solve": worst,
                    "max_dof": solves[worst], "cpu_hours": hours,
                    "cpu_hours_label": "[S] s/DOF of the largest measured N-layer probe solve x DOF x 1.3 per level "
                                       "beyond it; single-process solves, so CPU-hours = wall-hours; excludes the FV L2 "
                                       "cross-check and the calibration/constant-k extra solves",
                    "fits_burst_vm": bool(peak[worst] <= BURST_USABLE_GB), "burst_usable_GB": BURST_USABLE_GB,
                    "solves_over_10GB_local": sorted(k for k, v in peak.items() if v > LOCAL_HARD_GB)}
    return out


def decide(nl: dict, cost: dict, cg: dict) -> dict:
    gng = {}
    for cid, v in nl.items():
        opt = CONFIGS[cid]["option"]
        cg_ok = v["cg_max_iterations"] is not None and v["cg_max_iterations"] <= CG_FLAG
        fits = cost[cid]["fits_burst_vm"]
        meas_ok = any(e <= GO_ABS_K for e in v["max_abs_err_K"])
        p = v.get("observed_order_A2")
        ext = v.get("extrapolated_next_level_err_K_S")
        prov = (2 not in v["levels_run"] and v.get("extrapolated_level") == 2 and p is not None
                and P_LO <= p <= P_HI and ext is not None and ext <= GO_ABS_K)
        if meas_ok and cg_ok and fits:
            verdict = "go"
        elif prov and cg_ok and fits:
            verdict = "provisional_go"
        else:
            verdict = "no_go"
        gng[opt] = verdict
        gng[f"{opt}_basis"] = {"config": cid, "measured_min_max_abs_err_K": min(v["max_abs_err_K"]),
                               "levels_run": v["levels_run"], "cg_max": v["cg_max_iterations"], "cg_ok": cg_ok,
                               "fits_burst_vm": fits, "observed_order_A2": p, "extrapolated_L2_err_K_S": ext,
                               "provisional_conditions_met": bool(prov)}
    rd = {k: cg[k]["reading"] for k in ("case1a", "case2")}
    gng["option_b_cg_headroom_without_solver_change"] = (
        "yes (slivers)" if any(r.startswith("slivers") for r in rd.values()) and not any(
            r.startswith("conditioning") for r in rd.values()) else
        "no (conditioning)" if any(r.startswith("conditioning") for r in rd.values()) else "undetermined at levels 0-1")
    gng["cg_readings"] = rd
    return gng


def report() -> int:
    ser, mms, chk = DS.load_refs()
    prereg = None
    pj = OUT / "preregistration.json"
    if pj.exists():
        prereg = json.loads(pj.read_text())["preregistration_commit"]
    cg = cg_part(ser)
    nl = nlayer_part(ser)
    cost = cost_part(ser, mms, nl)
    out = {"task": "T0225", "objective": "O007", "preregistration_commit": prereg, "reference_hashes": chk,
           "configs": {k: {kk: vv for kk, vv in v.items()} for k, v in CONFIGS.items()}, "grading": GRADING,
           "grading_offsets_m": offsets(), "go_rule": {"abs_K": GO_ABS_K, "cg_max": CG_FLAG, "p_range": [P_LO, P_HI],
                                                       "burst_usable_GB": BURST_USABLE_GB},
           "cg_discriminator": cg, "nlayer": nl, "cost": cost, "go_no_go": decide(nl, cost, cg),
           "burst_command": 'scripts/burst_gcp.sh --cmd "uv run python research/scripts/o007_probe.py --full" '
                            'research/o007_probe',
           "labels": "[F] measured or counted; [S] extrapolated (extrapolated_* keys, cpu_hours)"}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "probe.json").write_text(json.dumps(out, indent=1, default=float))
    g = out["go_no_go"]
    log(f"go_no_go: option_a {g['option_a']}, option_b {g['option_b']}; CG readings {g['cg_readings']}")
    return 0


def plan() -> int:
    ser, mms, _ = DS.load_refs()
    out = {}
    for cid, c in CONFIGS.items():
        out[cid] = {f"{p}__L{lv}": DS.count_dofs(box_grid(cid, p, lv, ser)) for p in c["problems"] for lv in c["levels"]}
        out[cid]["grid_L0"] = {p: cell_ratio_xyz(box_grid(cid, p, 0, ser)) for p in c["problems"]}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "plan.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", action="store_true")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--full", action="store_true")
    ap.add_argument("--worker")
    a = ap.parse_args(argv)
    if a.worker:
        return worker(a.worker)
    if a.plan:
        return plan()
    if a.report:
        return report()
    if a.full:
        print('burst: scripts/burst_gcp.sh --cmd "uv run python research/scripts/o007_probe.py --full" '
              'research/o007_probe', flush=True)
    study(a.full)
    return report()


if __name__ == "__main__":
    sys.exit(main())
