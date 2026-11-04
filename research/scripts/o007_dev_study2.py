"""O007 development study 2 (T0228): pre-registered freeze of the graded scikit-fem rule (production GridRule.edge_grading).

Pre-registration: research/notes/o007-dev-study2.md section 0, committed before any solve of this study; its hash is
recorded in research/o007_dev2/preregistration.json and copied to dev_study.json as ``preregistration_commit``.
Research only: moduleforge.solvers.thermal_fem is used unchanged. Reused by import (T0207 / T0225 code, read-only):
o007_dev_study (load_refs with the sha256 gate, box_problem, mms_extra, dev_layout with the E006 fingerprint check, the
per-solve worker body ``solve``, the 'cg_only' CG logger, the watchdog, the memory gate, calibration, the three-level
study loop, the per-case / per-layout analysis and the selection summary) and o007_probe (its cache, its emulated
grading grid for the line-identity assertion, measured bytes/DOF, cell-ratio statistics). The T0207 helpers are bound to
this study's candidate, grid rule and cache by ``_bind`` (module attributes; nothing in those files is edited).

Modes
  --plan     grid-only DOF counts of every problem and level (no solve) -> research/o007_dev2/plan.json (with the burst
             command)
  (default)  local study under the T0207/T0225 memory rule (one child process at a time, <= 5 GB, or <= 10 GB when
             memory_pressure shows >= 50 % free and swap < 4 GB; watchdog at 10 GB RSS / 8 GB swap); cache in
             research/o007_dev2/cache/; then --report
  --full     the same at every level under 0.85 x physical memory (founder burst), then --report:
             scripts/burst_gcp.sh --cmd "uv run python research/scripts/o007_dev_study2.py --full" research/o007_dev2
  --report   deterministic: apply the pre-registered rule to the cached solves -> dev_study.json, frozen_config.json
  --worker   internal: one solve
SI units, kelvin, float64. Estimator: mfos.metrics.gci_capped (O006 A4, D0012/D0013; Roache 1998 ch. 5), floor 1e-3 K.
"""
from __future__ import annotations

import argparse
import hashlib
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
import o007_probe as PR  # noqa: E402  (T0225 helpers and cache, read-only use)

FEM = DS.FEM
OUT = ROOT / "research" / "o007_dev2"
CACHE = OUT / "cache"
PREREG = OUT / "preregistration.json"
CID = "a_q1h4_graded"
NL = "nlayer_dbc"
GRADING = (1.0e-4, 2.5, 4.0e-3, 0.5)  # (first_offset_m, ratio, max_offset_m, min_gap_fraction): T0225 option (a)
CANDIDATES = {CID: {"element_order": 1, "h0_m": 4e-3, "near_margin_m": 2e-3, "dz_max_m": 1.0e-3,
                    "edge_grading": GRADING}}  # pre-registered (note sec. 0.1); candidate 2 not used (sec. 0.1)
BURST_USABLE_GB = 0.85 * 256.0  # 217.6 GB, n2-highmem-32
BURST_COMMAND = 'scripts/burst_gcp.sh --cmd "uv run python research/scripts/o007_dev_study2.py --full" research/o007_dev2'
REUSE_TOL_K = 1e-9  # L0 re-solve of the reused N-layer probe case must agree to this (bitwise expected)
WALL_GROWTH = 1.3  # wall-time growth per level beyond the measured one (CG growth, as T0207) [S]
FV_JSON = ROOT / "research" / "o007_l2" / "full.json"  # T0204 FV L2 levels 1-3, founder burst (measured)
FV_PREVIEW = ROOT / "research" / "o007_l2" / "preview.json"
assert PR.GRADING == dict(zip(("first_offset_m", "ratio", "max_offset_m", "min_gap_fraction"), GRADING, strict=True))


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def rule_of(cid: str) -> FEM.GridRule:
    c = CANDIDATES[cid]
    return FEM.GridRule(h0=c["h0_m"], nz={}, default_nz=DS.NZ_MIN, zrefine=True, near_margin=c["near_margin_m"],
                        element_order=c["element_order"], dz_max=c["dz_max_m"], edge_grading=tuple(c["edge_grading"]))


def _bind() -> None:
    """Route the T0207 helpers (grid_of, solve, Runner.result, analyse_*) to this study's rule and cache."""
    DS.CANDIDATES = CANDIDATES
    DS.rule_of = rule_of
    DS.CACHE = CACHE
    DS.OUT = OUT


_bind()


def _rec_files() -> list[Path]:
    return [p for p in sorted(CACHE.glob("*.json")) if not p.name.endswith((".spec.json", "calibration.json"))]


def _ok_records() -> list[dict]:
    return [d for p in _rec_files() for d in [json.loads(p.read_text())] if d.get("status") == "ok"]


def bpd_max(order: int = 1) -> float:
    """Max measured whole-process peak bytes/DOF of this order over solves with >= 1 M DOF (T0207, T0225, this study)."""
    vals = [PR.measured_bpd(order)]
    vals += [d["peak_rss_bytes"] / d["dofs"] for d in _ok_records()
             if d["dofs"] >= 1e6 and CANDIDATES[d["spec"]["cid"]]["element_order"] == order]
    return max(vals)


def proc_wall(d: dict) -> float:
    return float(d.get("process_wall_s", d["wall_s"]))


# ------------------------------------------------------------------------------------------------ worker
_LAST: dict = {}


def _capture(fn):
    def wrapped(*a, **k):
        r = fn(*a, **k)
        _LAST["r"] = r  # the outermost call returns last
        return r
    return wrapped


def _lines_stats(r) -> dict:
    out = {}
    for ax in ("x", "y", "z"):
        w = np.diff(np.asarray(r.meta["lines"][ax]))
        out[f"min_ratio_{ax}"] = float(np.min(np.minimum(w[1:], w[:-1]) / np.maximum(w[1:], w[:-1])))
        out[f"min_cell_{ax}_m"] = float(w.min())
    return out


def centroid_nodes(name: str, ser: dict, mms: dict) -> list[dict]:
    """Die-centroid node of every die (sec. 0.3): the level-0 line nearest the die's area centroid in x and in y; level-0
    lines are lines at every level (bisection), so the node persists at every level."""
    g0 = DS.grid_of(CID, name, 0, ser, mms)
    out = []
    for d in DS.dev_layout(name).dies:
        b = d.bounds
        cx, cy = 0.5 * (b[0] + b[2]), 0.5 * (b[1] + b[3])
        xn, yn = float(g0.x[np.argmin(np.abs(g0.x - cx))]), float(g0.y[np.argmin(np.abs(g0.y - cy))])
        out.append({"x_c": cx, "y_c": cy, "x_node": xn, "y_node": yn, "offset_m": math.hypot(xn - cx, yn - cy)})
    return out


def worker(spec_path: str) -> int:
    spec = json.loads(Path(spec_path).read_text())
    threading.Thread(target=DS._watchdog, args=(spec["hard_cap_gb"] * 1e9,), daemon=True).start()
    DS.install_cg_logger()
    for nm in ("solve_layout", "solve_box_stack", "_solve_grid"):
        setattr(FEM, nm, _capture(getattr(FEM, nm)))
    base = DS.peak_rss_bytes()
    t0 = time.perf_counter()
    out = DS.solve(spec)  # T0207 worker body (points, stencils, layer means, constant-k, tj_max_xyz)
    r = _LAST["r"]
    out["grid"] = _lines_stats(r)
    out["meta_cg_iterations"] = [int(v) for v in r.meta["cg_iterations"]]  # T0222 production counter (cross-check)
    out["grading_lines"] = r.meta["grading_lines"]
    out["edge_grading_meta"] = r.meta["edge_grading"]
    if spec["problem"] in DS.LAYOUTS and spec["variant"] == "kT":
        ser, mms = json.loads(DS.SERIES_PATH.read_text())["payload"], json.loads(DS.MMS_PATH.read_text())
        cn = centroid_nodes(spec["problem"], ser, mms)
        for i, c in enumerate(cn):
            c["z"] = float(r.meta["tj_max_xyz"][i][2])  # the die's top face (argmax node lies on it)
            c["T"] = FEM.node_value(r, c["x_node"], c["y_node"], c["z"])
        out["centroid_nodes"] = cn
    out.update(status="ok", spec={k: v for k, v in spec.items() if k != "kconst"}, base_rss_bytes=base,
               peak_rss_bytes=DS.peak_rss_bytes(), process_wall_s=time.perf_counter() - t0, cg=DS.CG_LOG,
               cg_max_iters=max((c["iters"] for c in DS.CG_LOG), default=0),
               cg_max_true_rel=max((c["true_rel"] or 0.0 for c in DS.CG_LOG), default=0.0), platform=sys.platform)
    Path(spec["out"]).write_text(json.dumps(out))
    return 0


# ------------------------------------------------------------------------------------------------ orchestration
class Runner2(DS.Runner):
    """T0207 Runner (memory gate, calibration, level loop, constant-k nulls) with this script as the child worker."""

    def bpd(self, order: int) -> float:
        return bpd_max(order)

    def run(self, cid: str, prob: str, lv: int, var: str = "kT", tag: str = "", **extra) -> dict:
        key = f"{cid}__{prob}__L{lv}__{var}{tag}"
        path = CACHE / f"{key}.json"
        if path.exists():
            d = json.loads(path.read_text())
            if d.get("status") == "ok" or not self.full:
                return d
        dofs = DS.count_dofs(DS.grid_of(cid, prob, lv, self.ser, self.mms))
        est_gb = dofs * self.bpd(1) * PR.EST_MARGIN / 1e9
        ok, why = self.gate(est_gb)
        if not ok:
            log(f"  SKIP {key}: {dofs} DOF, {why}")
            return {"status": "skipped_memory", "dofs": dofs, "est_gb": est_gb, "reason": why}
        hard = 0.9 * self.phys_gb if self.full else DS.LOCAL_HARD_GB
        spec = {"cid": cid, "problem": prob, "level": lv, "variant": var, "out": str(path), "hard_cap_gb": hard, **extra}
        sp = CACHE / f"{key}.spec.json"
        sp.write_text(json.dumps(spec))
        log(f"  solve {key}: {dofs} DOF, {why}")
        t0 = time.perf_counter()
        pr = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--worker", str(sp)], capture_output=True,
                            text=True, timeout=8 * 3600)
        if pr.returncode != 0 or not path.exists():
            st = {3: "killed_memory", 4: "killed_swap"}.get(pr.returncode, "failed")
            rec = {"status": st, "returncode": pr.returncode, "dofs": dofs, "est_gb": est_gb,
                   "wall_s": time.perf_counter() - t0, "stderr_tail": (pr.stdout + pr.stderr)[-3000:],
                   "spec": {k: v for k, v in spec.items() if k != "kconst"}}
            path.write_text(json.dumps(rec))
            log(f"  {st.upper()} {key}: rc {pr.returncode}: {rec['stderr_tail'][-300:]}")
            return rec
        d = json.loads(path.read_text())
        log(f"  done {key}: {d['dofs']} DOF, {proc_wall(d):.1f} s, peak {d['peak_rss_bytes'] / 1e9:.2f} GB, "
            f"CG max {DS.cg_max(d)}, eb {d['energy_balance']:.1e}")
        return d


def _stencil_from_lines(lines: tuple, x: float, y: float) -> list:
    """FEM.node_stencil's per-axis record (index, coord, lo, hi) from the grid lines, z on the top face."""
    out = []
    for ln, v in zip(lines, (x, y, float(lines[2][-1])), strict=True):
        i = int(np.argmin(np.abs(ln - v)))
        if abs(ln[i] - v) > FEM.NODE_TOL_M:
            raise ValueError(f"{v} is not a line")
        out.append({"index": i, "coord": float(ln[i]), "lo": float(ln[i - 1]) if i > 0 else None,
                    "hi": float(ln[i + 1]) if i < ln.size - 1 else None})
    return out


def reuse_probe(ser: dict, mms: dict) -> dict:
    """Sec. 0.5: T0225's a_q1h4_graded N-layer solves enter this cache only if the production graded grid (GridRule with
    edge_grading) equals the probe's emulated grid line for line (x, y, z lines and material map) at that level."""
    info = {}
    for lv in DS.LEVELS:
        dst = CACHE / f"{CID}__{NL}__L{lv}__kT.json"
        if dst.exists():
            info[lv] = json.loads(dst.read_text()).get("reuse")
            continue
        src = PR.CACHE / f"{CID}__{NL}__L{lv}.json"
        d = json.loads(src.read_text())
        gp, ge = DS.grid_of(CID, NL, lv, ser, mms), PR.box_grid(CID, NL, lv, ser)
        same = {a: bool(np.array_equal(getattr(gp, a), getattr(ge, a))) for a in ("x", "y", "z", "mat")}
        if d.get("status") != "ok" or not all(same.values()):
            raise SystemExit(f"reuse refused at L{lv}: status {d.get('status')}, identical {same}")
        for p in d["points"]:
            p["stencil"] = None if p["x_used"] is None else _stencil_from_lines((gp.x, gp.y, gp.z), p["x_used"], p["y_used"])
        d["cg_max_true_rel"] = max(c["true_rel"] or 0.0 for c in d["cg"])
        d["reuse"] = {"source": str(src.relative_to(ROOT)), "source_sha256": hashlib.sha256(src.read_bytes()).hexdigest(),
                      "lines_identical": same, "n_lines": {"x": int(gp.x.size), "y": int(gp.y.size), "z": int(gp.z.size)},
                      "probe_spec": d["spec"]}
        d["spec"] = {"cid": CID, "problem": NL, "level": lv, "variant": "kT", "reused_from_T0225": True}
        dst.write_text(json.dumps(d))
        info[lv] = d["reuse"]
        log(f"  reused {src.name}: lines identical {same}")
    return info


def study(full: bool) -> None:
    ser, mms, hashes = DS.load_refs()
    log(f"references verified: {hashes['series_sha256'][:8]} / {hashes['mms_sha256'][:8]}")
    for n in DS.LAYOUTS:
        log(f"dev layout {n}: fingerprint {DS.dev_layout(n).fingerprint()[:12]} (E006 spec)")
    CACHE.mkdir(parents=True, exist_ok=True)
    reuse_probe(ser, mms)
    run = Runner2(ser, mms, full)
    run.run(CID, NL, 0, "kT", tag="_reusecheck")  # sec. 0.5: the L0 re-solve must reproduce the reused L0
    run.study([CID], list(DS.CASES + DS.LAYOUTS))


# ------------------------------------------------------------------------------------------------ analysis
def reuse_check() -> dict:
    a = Runner2.result(CID, NL, 0)
    p = CACHE / f"{CID}__{NL}__L0__kT_reusecheck.json"
    b = json.loads(p.read_text()) if p.exists() else None
    if not (a and b and b.get("status") == "ok"):
        return {"status": "not_run", "ok": False}
    dt = max(abs(u["T"] - v["T"]) for u, v in zip(a["points"], b["points"], strict=True))
    return {"status": "ok", "max_abs_dT_K": dt, "tol_K": REUSE_TOL_K, "ok": dt <= REUSE_TOL_K,
            "bitwise": all(u["T"] == v["T"] for u, v in zip(a["points"], b["points"], strict=True)),
            "levels_reused": [lv for lv in DS.LEVELS if (Runner2.result(CID, NL, lv) or {}).get("reuse")]}


def _meta_cg_mismatch(d: dict) -> int | None:
    m = d.get("meta_cg_iterations")
    if m is None:
        return None
    return max((abs(a - DS.cg_iters(c)) for a, c in zip(m, d["cg"], strict=False)), default=0)


def extend_case(v: dict, prob: str) -> dict:
    runs = [Runner2.result(CID, prob, lv) for lv in v["levels_run"]]
    v["cg_max_per_level"] = list(v.get("cg_max_iters", []))
    v["meta_cg_max_abs_mismatch"] = [_meta_cg_mismatch(d) for d in runs]
    v["grid_per_level"] = [d.get("grid") for d in runs]
    v["reused_levels"] = [lv for lv, d in zip(v["levels_run"], runs, strict=True) if d.get("reuse")]
    return v


def extend_layout(v: dict, name: str) -> dict:
    v = extend_case(v, name)
    runs = [Runner2.result(CID, name, lv) for lv in v["levels_run"]]
    for i, die in enumerate(v["dies"]):
        cn = [d["centroid_nodes"][i] for d in runs]
        f = [c["T"] for c in cn]
        die["centroid_node"] = {"x_node": cn[0]["x_node"], "y_node": cn[0]["y_node"], "z": cn[0]["z"],
                                "offset_from_centroid_m": cn[0]["offset_m"], "values_K": f, **DS.a4(f),
                                "same_node_all_levels": all(c["x_node"] == cn[0]["x_node"] and c["y_node"] == cn[0]["y_node"]
                                                            and abs(c["z"] - cn[0]["z"]) <= FEM.NODE_TOL_M for c in cn)}
    gc = [DS._gnum(d["centroid_node"]["gci_K"]) for d in v["dies"]]
    v["centroid_node_max_gci_K"] = max(gc) if len(v["levels_run"]) == 3 and gc else None
    v["centroid_node_branches"] = [d["centroid_node"]["a4_branch"] for d in v["dies"]]
    return v


def fv_rows() -> list[dict]:
    """E009's FV L2 cross-check (levels 1-3 of its frozen rule): T0204 founder burst (research/o007_l2/full.json,
    measured on the VM) for the dev layouts; fresh layouts at 1.5 x the larger dev layout (extrapolated [S])."""
    fv = json.loads(FV_JSON.read_text())["layouts"]
    rows = []
    for name, v in sorted(fv.items()):
        for lv, s in sorted(v["solves"].items()):
            w = float(s["solve_wall_s"]) + float(s.get("build_s", 0.0))
            rows.append({"solver": "FV L2", "problem": name, "level": int(lv), "n_solves": 1, "cells": s["n_cells"],
                         "peak_GB": s["peak_rss_gb"], "wall_s_each": w, "basis": "measured (T0204 burst, Linux)"})
    big = max(fv, key=lambda n: fv[n]["solves"]["3"]["n_cells"])
    for k in range(3):
        for lv, s in sorted(fv[big]["solves"].items()):
            rows.append({"solver": "FV L2", "problem": f"fresh layout {k + 1} (1.5 x {big})", "level": int(lv), "n_solves": 1,
                         "cells": int(1.5 * s["n_cells"]), "peak_GB": 1.5 * s["peak_rss_gb"],
                         "wall_s_each": 1.5 * (float(s["solve_wall_s"]) + float(s.get("build_s", 0.0))),
                         "basis": "extrapolated [S]: 1.5 x the larger dev layout (cells, peak, wall)"})
    return rows


def e009_table(ser: dict, mms: dict) -> dict:
    """Every E009 scikit-fem solve (sec. 0.6): exact DOF from the grid; peak and wall measured where this exact solve
    was run, else DOF x bpd_max and wall from s/DOF of the reference solves x 1.3 per level beyond them [S]."""
    bpd = bpd_max(1)
    meas = _ok_records()
    rows = []

    def ext_wall(problem: str, lv: int, dofs: int) -> float:
        refs = [m for m in meas if m["spec"]["problem"] == problem]
        cands = [max(refs, key=lambda m: m["dofs"])] if refs else []
        cands.append(max(meas, key=lambda m: m["dofs"]))
        return max(proc_wall(m) * dofs / m["dofs"] * WALL_GROWTH ** max(0, lv - m["spec"]["level"]) for m in cands)

    def add(problem: str, lv: int, n: int, label: str = "", scale: float = 1.0, var: str = "kT", src: str | None = None):
        dofs = int(DS.count_dofs(DS.grid_of(CID, src or problem, lv, ser, mms)) * scale)
        d = Runner2.result(CID, problem, lv, var) if scale == 1.0 else None
        if d and d.get("status") == "ok":
            gb, wall, basis = d["peak_rss_bytes"] / 1e9, proc_wall(d), f"measured ({d.get('platform')})"
        else:
            gb, wall = dofs * bpd / 1e9, ext_wall(src or problem, lv, dofs)
            basis = f"extrapolated [S]: DOF x {bpd:.0f} B/DOF; wall s/DOF x {WALL_GROWTH}/level"
        rows.append({"solver": "scikit-fem", "problem": problem + label, "level": lv, "n_solves": n, "dofs": dofs,
                     "peak_GB": gb, "wall_s_each": wall, "basis": basis})

    for name in DS.CASES:
        for lv in DS.LEVELS:
            add(name, lv, 1)
    add("mms", 2, 1, " constant-k null", var="constk")
    for name in DS.LAYOUTS:
        for lv in DS.LEVELS:
            add(name, lv, 3 if lv == 0 else 1)
        add(name, 2, 1, " constant-k column", var="constk")
    big = max(DS.LAYOUTS, key=lambda n: DS.count_dofs(DS.grid_of(CID, n, 0, ser, mms)))
    for k in range(3):
        for lv in DS.LEVELS:
            add(f"fresh layout {k + 1}", lv, 3 if lv == 0 else 1, f" (1.5 x {big})", DS.FRESH_ALLOWANCE, src=big)
        add(f"fresh layout {k + 1}", 2, 1, f" (1.5 x {big}) constant-k", DS.FRESH_ALLOWANCE, src=big)
    rows += fv_rows()
    for r in rows:
        r["cpu_hours"] = r["n_solves"] * r["wall_s_each"] / 3600.0
        r["recommended_timeout_s"] = int(max(1800, math.ceil(3.0 * r["wall_s_each"] / 60.0) * 60))
    sk = [r for r in rows if r["solver"] == "scikit-fem"]
    fvr = [r for r in rows if r["solver"] == "FV L2"]
    tot = sum(r["cpu_hours"] for r in rows)
    return {"rows": rows, "bytes_per_dof_used": bpd, "skfem_peak_GB": max(r["peak_GB"] for r in sk),
            "skfem_peak_row": max(sk, key=lambda r: r["peak_GB"])["problem"],
            "fv_peak_GB": max(r["peak_GB"] for r in fvr), "fits_burst": max(r["peak_GB"] for r in rows) <= BURST_USABLE_GB,
            "burst_usable_GB": BURST_USABLE_GB, "skfem_cpu_hours": sum(r["cpu_hours"] for r in sk),
            "fv_cpu_hours": sum(r["cpu_hours"] for r in fvr), "total_cpu_hours": tot,
            "recommended_total_timeout_h": max(2.0, math.ceil(3.0 * tot)),
            "note": "CPU-hours = wall-hours (assembly and AMG-CG essentially single-threaded); wall extrapolations [S] mix "
                    "macOS (local) and Linux (burst) timings; FV L2 from research/o007_l2/full.json (T0204 burst)."}


def _gate_constant_k(s: dict) -> None:
    """Sec. 0.2 criterion 2 covers every L0-L2 solve, but ``DS.summarise`` (T0207) gates only the k(T) level runs and the
    calibration runs. The constant-k nulls are gated here the same way: over 300 CG iterations rules the candidate out,
    and a null missing or unfinished at the finest level run leaves it unverified, like an unfinished k(T) level. Added
    before the burst, after review T0232; it can only make the decision stricter."""
    recs = [json.loads(p.read_text()) for p in _rec_files() if p.name.endswith("__constk.json")]
    cg = max((DS.cg_max(d) for d in recs if d.get("status") == "ok"), default=0)
    missing = []
    for prob in ["mms", *DS.LAYOUTS]:
        lvs = [lv for lv in DS.LEVELS if (Runner2.result(CID, prob, lv) or {}).get("status") == "ok"]
        if lvs and (Runner2.result(CID, prob, lvs[-1], "constk") or {}).get("status") != "ok":
            missing.append(f"{prob} L{lvs[-1]}")
    s.update(constk_cg_max_iters=cg, constk_missing_or_unfinished=missing, cg_max_iters=max(s["cg_max_iters"], cg))
    if cg > DS.CG_FLAG:
        s.update(eligible=False, ruled_out=True, cg_over_300=True,
                 verdict="ineligible: CG > 300 iterations (constant-k null)")
    elif missing and s["eligible"]:
        s.update(eligible=False, verdict=f"unverified: constant-k null missing or unfinished on {missing}")


def report() -> int:
    ser, mms, hashes = DS.load_refs()
    cases = {p: extend_case(DS.analyse_case(CID, p, ser, mms), p) for p in DS.CASES}
    lays = {n: extend_layout(DS.analyse_layout(CID, n), n) for n in DS.LAYOUTS}
    s = DS.summarise(CID, cases, lays)
    _gate_constant_k(s)
    plan = e009_table(ser, mms)
    rc = reuse_check()
    allv = list(cases.values()) + list(lays.values())
    complete = all(v["levels_run"] == [0, 1, 2] for v in allv)
    s["fits_burst"] = plan["fits_burst"]
    s["reuse_check_ok"] = rc["ok"]
    s["all_levels_measured"] = complete
    feasible = bool(s["eligible"] and plan["fits_burst"] and rc["ok"] and complete)
    missing = {k: [lv for lv in DS.LEVELS if lv not in v["levels_run"]] for k, v in {**cases, **lays}.items()}
    missing = {k: v for k, v in missing.items() if v}
    if feasible:
        why = "candidate 1 verified eligible on every criterion at level 2 (sec. 0.2); cheapest eligible (only candidate)"
    elif s["ruled_out"]:
        why = f"candidate 1 ruled out by measured data: {s['verdict']}"
    else:
        why = f"not yet verifiable: level 2 missing on {sorted(missing)} (founder burst: {BURST_COMMAND})"
    prereg = json.loads(PREREG.read_text())["preregistration_commit"] if PREREG.exists() else "MISSING"
    c = CANDIDATES[CID]
    study_out = {
        "task": "T0228", "objective": "O007", "preregistration_commit": prereg,
        "meta": {"references": hashes, "dev_seed": DS.DEV_SEED,
                 "thermal_fem_sha256": hashlib.sha256((ROOT / "src/moduleforge/solvers/thermal_fem.py").read_bytes()).hexdigest(),
                 "margins": DS.MARGIN, "thresholds": DS.THRESH, "cg_flag": DS.CG_FLAG, "cg_cap": DS.CG_CAP,
                 "burst_command": BURST_COMMAND, "grading": GRADING},
        "reuse_check": rc,
        "chosen": {"id": CID, "feasible": feasible, "why": why, "levels_missing": missing, "summary": s,
                   "cases": cases, "layouts": lays, "e009_plan": plan},
        "candidates_considered": [CID]}
    (OUT / "dev_study.json").write_text(json.dumps(study_out, indent=1, default=float, sort_keys=True))
    frozen = {"element_order": c["element_order"], "h0_m": c["h0_m"], "near_margin_m": c["near_margin_m"],
              "dz_max_m": c["dz_max_m"], "nz_min": DS.NZ_MIN, "min_cells": 2, "zrefine": True,
              "edge_grading": dict(zip(("first_offset_m", "ratio", "max_offset_m", "min_gap_fraction"), GRADING, strict=True)),
              "refinement_ratio": FEM.REFINEMENT_RATIO, "snap_fraction": FEM.SNAP_FRACTION, "amg_seed": FEM.AMG_SEED,
              "mandatory_lines": DS.MANDATORY_POLICY + (" Edge grading: production GridRule.edge_grading in both modes; in "
                                                        "layout mode the fixed set also holds every layout geometry line "
                                                        "(T0227/T0231)."),
              "quadrature": {"stiffness": "2x2x2 Gauss (Q1)", "faces": "3x3 Gauss (intorder 4)",
                             "manufactured_data": "4x4x4 / 4x4 Gauss (intorder 7)"},
              "linear_rtol": FEM.LINEAR_RTOL, "cg_maxiter": FEM.CG_MAXITER, "cg_eligibility_limit": DS.CG_FLAG,
              "picard_tol_K": FEM.PICARD_TOL_K, "levels": list(DS.LEVELS), "candidate_id": CID, "feasible": feasible,
              "levels_missing": missing,
              "rationale": f"{why}. Pre-registered rule: research/notes/o007-dev-study2.md sec. 0 (commit {prereg})."}
    (OUT / "frozen_config.json").write_text(json.dumps(frozen, indent=1, default=float, sort_keys=True))
    log(f"{CID}: feasible={feasible}; {why}")
    log(f"  summary {json.dumps(s, default=float)}")
    return 0


def plan() -> int:
    ser, mms, hashes = DS.load_refs()
    bpd = bpd_max(1)
    rows = []
    for prob in DS.CASES + DS.LAYOUTS:
        for lv in DS.LEVELS:
            g = DS.grid_of(CID, prob, lv, ser, mms)
            n = DS.count_dofs(g)
            est = n * bpd * PR.EST_MARGIN / 1e9
            rows.append({"problem": prob, "level": lv, "dofs": n, "cells": list(g.mat.shape),
                         "min_cell_ratio_lateral": DS.min_cell_ratio(g), "grading_lines": {k: len(v) for k, v in g.grading.items()},
                         "snaps": {k: len(v) for k, v in g.snaps.items()}, "local_est_GB": est,
                         "local": "yes" if est <= DS.LOCAL_SOFT_GB else "if memory_pressure allows" if est <= DS.LOCAL_HARD_GB
                         else "no (burst)"})
            log(f"{prob} L{lv}: {n} DOF, est {est:.1f} GB, {rows[-1]['local']}")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "plan.json").write_text(json.dumps({"task": "T0228", "candidate": CID, "grading": GRADING, "references": hashes,
                                               "local_bytes_per_dof": bpd, "local_est_margin": PR.EST_MARGIN,
                                               "burst_command": BURST_COMMAND, "rows": rows}, indent=1))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--plan", action="store_true")
    ap.add_argument("--full", action="store_true")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--worker")
    a = ap.parse_args(argv)
    if a.worker:
        return worker(a.worker)
    if a.plan:
        return plan()
    if a.report:
        return report()
    study(a.full)
    return report()


if __name__ == "__main__":
    sys.exit(main())
