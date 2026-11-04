"""O007 development study (T0207): choose and freeze the scikit-fem configuration for E009; E009 memory and cost plan.

Pre-registration (candidates, selection criterion, margins, local memory rule): research/notes/o007-dev-study.md sec. 0,
written and committed before any solve. Production solver only: moduleforge.solvers.thermal_fem (box-stack mode for the
Muzychka and N-layer cases, layout mode for the manufactured case and the dev layouts). Nothing in src/ is modified.

Modes
  --plan          grid-only DOF counts of every candidate, problem and level (no solve) -> research/o007_dev/plan.json
  (default)       local study: every candidate and problem at the levels the local memory rule allows; each solve in
                  its own child process (peak RSS per solve), results checkpointed in research/o007_dev/cache/, so a
                  re-run resumes; then --report
  --full          the same at every level 0-2 under the packet's rule only (0.85 x physical memory), for a founder burst:
                  scripts/burst_gcp.sh --cmd "uv run python research/scripts/o007_dev_study.py --full" research/o007_dev
  --report        rebuild dev_study.json and frozen_config.json from the cache (no solve)
  --worker SPEC   internal: one solve

Measurements per solve: DOFs, wall time, peak RSS (ru_maxrss of the child), CG iterations and final relative residual of
every linear solve (pyamg ``residuals``, recorded by wrapping ``_Solver.solve`` from the outside; the solver and its
limits are unchanged, founder note T0218), energy balance, Picard residual. Estimator: mfos.metrics.gci_capped (O006 A4,
D0012/D0013; Roache 1998 ch. 5), floor 1e-3 K. References: frozen O006 files (sha256 checked first). SI units, kelvin.
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import math
import os
import re
import resource
import subprocess
import sys
import threading
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "experiments" / "runners"), str(ROOT / "tools" / "mfos"), str(ROOT / "src")]

import e006_run as R  # noqa: E402  read-only use: mms_layout, canon_sha, e006_mms via R.MMS
import yaml  # noqa: E402
from mfos import metrics as MX  # noqa: E402

from moduleforge.generate.halfbridge import generate_layouts  # noqa: E402
from moduleforge.solvers import thermal_fem as FEM  # noqa: E402

OUT = ROOT / "research" / "o007_dev"
CACHE = OUT / "cache"
SERIES_PATH = ROOT / "research" / "e006_refs" / "series_values.json"
MMS_PATH = ROOT / "research" / "e006_refs" / "mms_values.json"
SERIES_SHA = "befc5efaf2d50e3c096b41521814e2949885279d702cf38b921a090b80667151"
MMS_SHA = "ca05847b71c54a618c469c52216523b6a376368fa25a427e90cf4f9fdc22fd6b"
DEV_SEED = 20261101
DEV = (("side_by_side_6", "side_by_side", 6), ("u_shaped_2", "u_shaped", 2))
BOX = ("case1a", "case1b", "case2", "case3", "nlayer_dbc")
CASES = BOX + ("mms",)
LAYOUTS = tuple(d[0] for d in DEV)
COOLANT_K, H_OP, TARGET_K, CAL_TOL_K, P_START_W = 338.15, 5000.0, 60.0, 1.0, 30.0  # O003 operating point (O007 scope)
MMS_TC = 340.0  # Picard start / rise reference of the manufactured case (its physics is in T_inf(x, y))
MMS_Q_REF_W = 64.6482773100492  # frozen integral of the manufactured Robin outflow (mms_values.json balance.robin_W)
GCI_FLOOR_K = 1e-3
LEVELS = (0, 1, 2)
NZ_MIN = 1
CANDIDATES = {  # pre-registered (note sec. 0.1); lengths in m
    "q1_h4": {"element_order": 1, "h0_m": 4e-3, "near_margin_m": 2e-3, "dz_max_m": 1.0e-3},
    "q1_h2": {"element_order": 1, "h0_m": 2e-3, "near_margin_m": 2e-3, "dz_max_m": 0.5e-3},
    "q2_h4": {"element_order": 2, "h0_m": 4e-3, "near_margin_m": 2e-3, "dz_max_m": 5.0e-3},
    "q2_h4z2": {"element_order": 2, "h0_m": 4e-3, "near_margin_m": 2e-3, "dz_max_m": 2.0e-3},
}
MARGIN = {"A1": 0.008, "A2_K": 0.040, "A4_cases_K": 0.40, "A4_layouts_K": 0.25}  # pre-registered (note sec. 0.2)
THRESH = {"A1": 0.01, "A2_K": 0.05, "A4_K": 0.5, "K1": 0.05, "K2_K": 0.25}
CG_FLAG, CG_CAP = 300, 400
RATIO_LO, RATIO_HI = 8 * 0.85, 8 * 1.15
BURST = {"machine": "n2-highmem-32", "memory_GB": 256.0, "usable_fraction": 0.85}
FRESH_ALLOWANCE = 1.5  # fresh-layout DOF allowance relative to the larger dev layout (E009 plan; fresh layouts unseen)
LOCAL_SOFT_GB, LOCAL_HARD_GB, SWAP_STOP_GB = 5.0, 10.0, 8.0
MANDATORY_POLICY = ("box-stack mode: x and y lines through every source centroid (built in) and through the frozen "
                    "reference maximum of every source (extra_lines); layout mode (manufactured case): x and y lines "
                    "through every frozen reported point and maximum, z lines at their (interface) heights; generator "
                    "layouts: none (Tj max = max nodal value on the die top face). Snapping: production SNAP_FRACTION "
                    "1e-2 of the level-0 cell; every snap recorded and the node at the snapped coordinate reported.")


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


# ------------------------------------------------------------------------------------------------ machine
def peak_rss_bytes() -> float:
    r = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return float(r) if sys.platform == "darwin" else float(r) * 1024.0


def swap_used_gb() -> float | None:
    """macOS: total size of /private/var/vm/swapfile* (proxy; sysctl vm.swapusage is denied in the agent sandbox).
    Linux: SwapTotal - SwapFree."""
    if sys.platform == "darwin":
        return sum(os.path.getsize(p) for p in glob.glob("/private/var/vm/swapfile*")) / 1e9
    try:
        kv = dict(ln.split(":", 1) for ln in Path("/proc/meminfo").read_text().splitlines())
        return (int(kv["SwapTotal"].split()[0]) - int(kv["SwapFree"].split()[0])) / 1e6
    except (OSError, KeyError, ValueError):
        return None


def mem_free_pct() -> float | None:
    if sys.platform == "darwin":
        try:
            out = subprocess.run(["memory_pressure"], capture_output=True, text=True, timeout=60).stdout
            m = re.search(r"free percentage:\s*(\d+)%", out)
            return float(m.group(1)) if m else None
        except (OSError, subprocess.SubprocessError):
            return None
    try:
        kv = dict(ln.split(":", 1) for ln in Path("/proc/meminfo").read_text().splitlines())
        return 100.0 * int(kv["MemAvailable"].split()[0]) / int(kv["MemTotal"].split()[0])
    except (OSError, KeyError, ValueError):
        return None


# ------------------------------------------------------------------------------------------------ inputs
def load_refs() -> tuple[dict, dict, dict]:
    """Frozen O006 references; sha256 of the canonical payloads (as e006_run.load_refs) checked before anything else."""
    ser = json.loads(SERIES_PATH.read_text())
    mms = json.loads(MMS_PATH.read_text())
    s_sha, m_sha = R.canon_sha(ser["payload"], allow_nan=False), R.canon_sha(mms["payload"])
    chk = {"series_sha256": s_sha, "series_ok": s_sha == SERIES_SHA == ser["sha256"],
           "mms_sha256": m_sha, "mms_ok": m_sha == MMS_SHA == mms["sha256_payload"],
           "file_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (SERIES_PATH, MMS_PATH)}}
    if not (chk["series_ok"] and chk["mms_ok"]):
        raise SystemExit(f"frozen reference hash mismatch: {chk}")
    return ser["payload"], mms, chk


def rule_of(cid: str) -> FEM.GridRule:
    c = CANDIDATES[cid]
    return FEM.GridRule(h0=c["h0_m"], nz={}, default_nz=NZ_MIN, zrefine=True, near_margin=c["near_margin_m"],
                        element_order=c["element_order"], dz_max=c["dz_max_m"])


def box_problem(ser: dict, name: str) -> dict:
    c = ser["cases"][name]
    srcs = [(s["xc_m"] - s["c_m"] / 2, s["yc_m"] - s["d_m"] / 2, s["xc_m"] + s["c_m"] / 2, s["yc_m"] + s["d_m"] / 2,
             s["Q_W"]) for s in c["sources"]]
    rows = [r for r in ser["rows"] if r["case"] == name]
    mx = [r for r in rows if r["point"] == "max"]
    return {"a": c["a_m"], "b": c["b_m"], "h": c["h_W_m2K"], "Tc": c["Tf_K"], "scale": c["scale_K"], "srcs": srcs,
            "names": [s["name"] for s in c["sources"]], "rows": rows,
            "layers": [FEM.BoxLayer(la["t_m"], la["k_W_mK"], NZ_MIN, la["name"]) for la in c["layers_bottom_up"]],
            "extra": ([r["x_m"] for r in mx], [r["y_m"] for r in mx], None)}


def mms_extra(mms: dict) -> tuple:
    pts = [p for p in mms["payload"]["reported_points"] if p["kind"] != "area_mean"]
    return [p["x"] for p in pts], [p["y"] for p in pts], [p["z"] for p in pts]


_LAY: dict = {}


def dev_layout(name: str):
    if name not in _LAY:
        fam, dps = {d[0]: d[1:] for d in DEV}[name]
        lay = generate_layouts(1, DEV_SEED, family=fam, dies_per_switch=dps)[0]
        fp = yaml.safe_load((ROOT / "experiments" / "specs" / "E006.yaml").read_text())["config"]["dev_fingerprints"]
        if lay.fingerprint() != fp[name]:
            raise SystemExit(f"F4: dev layout {name} fingerprint {lay.fingerprint()} != E006 spec {fp[name]}")
        _LAY[name] = lay
    return _LAY[name]


def grid_of(cid: str, prob: str, level: int, ser: dict, mms: dict):
    rule = rule_of(cid)
    if prob in BOX:
        b = box_problem(ser, prob)
        return FEM.box_stack_grid(b["a"], b["b"], b["layers"], b["h"], b["Tc"], b["srcs"], rule=rule, level=level,
                                  extra_lines=b["extra"])
    if prob == "mms":
        return FEM.layout_grid(R.mms_layout(), 0.0, 1.0, MMS_TC, rule, level, mms_extra(mms))
    return FEM.layout_grid(dev_layout(prob), 1.0, H_OP, COOLANT_K, rule, level)


def count_dofs(g) -> int:
    return FEM._count_nodes(g.mat) if g.order == 1 else FEM._count_nodes_q2(g.mat)


def min_cell_ratio(g) -> float:
    """Smallest ratio of neighbouring lateral cell widths (slivers slow AMG-CG, T0218)."""
    out = 1.0
    for v in (g.x, g.y):
        w = np.diff(v)
        out = min(out, float(np.min(np.minimum(w[1:], w[:-1]) / np.maximum(w[1:], w[:-1]))))
    return out


# ------------------------------------------------------------------------------------------------ worker (one solve)
CG_LOG: list[dict] = []


def install_cg_logger() -> None:
    """Count the CG iterations of every linear solve without changing the solve: the production ``_Solver.solve`` runs
    unchanged; only a counting ``callback`` (called once per iteration by pyamg.krylov.cg) is added to its ``ml.solve``
    call. pyamg's ``residuals`` list is NOT used: through MultilevelSolver.solve it came back with 2-3 entries for a
    solve of 309 iterations (checked 2026-11-03, pyamg 5.4.1). The final relative residual is recomputed as
    ||b - A x|| / ||b|| on the returned x."""
    orig = FEM._Solver.solve

    def logged(self, b, x0):
        calls: list = []
        inner = self.ml.solve

        def wrapped(*a, **k):
            # only the outer (accelerated) call: the AMG preconditioner's matvec calls ml.solve(maxiter=1) on the same
            # object, and counting those too gave 2 x iterations + 1 (found 2026-11-03; entries without
            # "counter": "cg_only" are converted by (n - 1) / 2 in the analysis, checked by a re-solve)
            if k.get("accel") == "cg":
                k["callback"] = lambda xk: calls.append(1)  # one call per CG iteration (pyamg.krylov.cg)
            return inner(*a, **k)

        self.ml.solve = wrapped
        try:
            x = orig(self, b, x0)
        except RuntimeError as e:
            CG_LOG.append({"iters": len(calls), "counter": "cg_only", "true_rel": None, "hit_cap": len(calls) >= CG_CAP, "error": str(e)})
            raise
        finally:
            del self.ml.solve
        nb = float(np.linalg.norm(b))
        CG_LOG.append({"iters": len(calls), "counter": "cg_only", "true_rel": float(np.linalg.norm(b - self.A @ x) / nb) if nb > 0 else 0.0,
                       "hit_cap": len(calls) >= CG_CAP})
        return x

    FEM._Solver.solve = logged


def _watchdog(cap_bytes: float) -> None:
    n = 0
    while True:
        if peak_rss_bytes() > cap_bytes:
            print(f"watchdog: peak RSS {peak_rss_bytes() / 1e9:.2f} GB > cap {cap_bytes / 1e9:.2f} GB", flush=True)
            os._exit(3)
        if n % 5 == 0:
            s = swap_used_gb()
            if s is not None and s > SWAP_STOP_GB:
                print(f"watchdog: swap {s:.1f} GB > {SWAP_STOP_GB} GB", flush=True)
                os._exit(4)
        n += 1
        time.sleep(1.0)


def _used(r, ax: str, v: float) -> float:
    for a, b in r.meta["snapped_lines"].get(ax, []):
        if abs(a - v) <= 1e-12:
            return float(b)
    return float(v)


def _stencil(r, x, y, z=None) -> list:
    return [{k: s[k] for k in ("index", "coord", "lo", "hi")} for s in FEM.node_stencil(r, x, y, z)]


def _layer_means(r, g, n_mat: int) -> list:
    """Volume-mean temperature per material: element mean of its 8 vertex values x element volume."""
    ci, cj, ck = np.nonzero(g.mat >= 0)
    em = g.mat[ci, cj, ck]
    vol = np.diff(g.x)[ci] * np.diff(g.y)[cj] * np.diff(g.z)[ck]
    Te = r.T[r.field_eval.mesh.t].mean(axis=0)
    return [float(np.sum(Te[em == m] * vol[em == m]) / np.sum(vol[em == m])) if np.any(em == m) else None
            for m in range(n_mat)]


def _const_grid(g, kconst: list):
    g.kfun = [(lambda T, k=k: np.full_like(T, k)) for k in kconst]
    return g


def solve(spec: dict) -> dict:
    ser, mms = json.loads(SERIES_PATH.read_text())["payload"], json.loads(MMS_PATH.read_text())
    cid, prob, lv, var = spec["cid"], spec["problem"], spec["level"], spec["variant"]
    rule = rule_of(cid)
    out: dict = {}
    if prob in BOX:
        b = box_problem(ser, prob)
        r = FEM.solve_box_stack(b["a"], b["b"], b["layers"], b["h"], b["Tc"], b["srcs"], rule=rule, level=lv,
                                extra_lines=b["extra"])
        pts = []
        for row in b["rows"]:
            si = b["names"].index(row["source"])
            p = {"source": row["source"], "point": row["point"], "x_req": row["x_m"], "y_req": row["y_m"]}
            if row["point"] == "mean":
                p.update(T=float(r.tj_mean[si]), x_used=None, y_used=None, stencil=None)
            else:
                xu, yu = _used(r, "x", row["x_m"]), _used(r, "y", row["y_m"])
                p.update(T=FEM.node_value(r, xu, yu), x_used=xu, y_used=yu, stencil=_stencil(r, xu, yu))
            pts.append(p)
        out["points"] = pts
    elif prob == "mms":
        case, lay = R.MMS.build_case(), R.mms_layout()
        ex = mms_extra(mms)
        if var == "kT":
            r = FEM.solve_layout(lay, 0.0, case.h, MMS_TC, rule=rule, level=lv, source=case.source, flux=case.flux,
                                 T_inf=case.T_inf, extra_lines=ex)
        else:
            g = _const_grid(FEM.layout_grid(lay, 0.0, case.h, MMS_TC, rule, lv, ex), spec["kconst"])
            g.source, g.flux, g.T_inf = case.source, case.flux, case.T_inf
            r = FEM._solve_grid(g, constant_k=True)
        pts = []
        for p in mms["payload"]["reported_points"]:
            q = {"id": p["id"], "kind": p["kind"], "x_req": p["x"], "y_req": p["y"], "z": p["z"]}
            if p["kind"] == "area_mean":
                q.update(T=float(r.tj_mean[0]), x_used=None, y_used=None, stencil=None)
            else:
                xu, yu = _used(r, "x", p["x"]), _used(r, "y", p["y"])
                q.update(T=FEM.node_value(r, xu, yu, p["z"]), x_used=xu, y_used=yu, stencil=_stencil(r, xu, yu, p["z"]))
            pts.append(q)
        out["points"] = pts
        out["q_out_vs_reference"] = abs(r.meta["q_out_W"] / MMS_Q_REF_W - 1.0)
        if var == "kT":
            g = FEM.layout_grid(lay, 0.0, case.h, MMS_TC, rule, lv, ex)
            mats = FEM._materials(lay)
            tm = _layer_means(r, g, len(mats))
            out["layer_mean_T_K"] = tm
            out["kconst"] = [float(la.k_at(t)) if t is not None else float(la.k) for la, t in zip(mats, tm, strict=True)]
    else:
        lay, P = dev_layout(prob), float(spec["power_W"])
        if var == "kT":
            r = FEM.solve_layout(lay, P, H_OP, COOLANT_K, rule=rule, level=lv)
            g = FEM.layout_grid(lay, P, H_OP, COOLANT_K, rule, lv)
            mats = FEM._materials(lay)
            tm = _layer_means(r, g, len(mats))
            out["layer_mean_T_K"] = tm
            out["kconst"] = [float(la.k_at(t)) if t is not None else float(la.k) for la, t in zip(mats, tm, strict=True)]
        else:
            r = FEM._solve_grid(_const_grid(FEM.layout_grid(lay, P, H_OP, COOLANT_K, rule, lv), spec["kconst"]),
                                constant_k=True)
        out.update(tj_max=[float(v) for v in r.tj_max], tj_mean=[float(v) for v in r.tj_mean],
                   tj_max_xyz=r.meta["tj_max_xyz"], power_W=P)
    m = r.meta
    out.update(dofs=int(r.dofs), n_elements=m["n_elements"], n_vertices=m["n_vertices"], wall_s=float(r.wall_s),
               energy_balance=float(r.energy_balance), picard_iters=int(r.picard_iters),
               picard_residual=float(r.picard_residual), q_out_W=m["q_out_W"], q_in_W=m["q_in_W"],
               n_lines=m["n_lines"], snapped_lines=m["snapped_lines"], max_snap_m=m["max_snap_m"])
    return out


def worker(spec_path: str) -> int:
    spec = json.loads(Path(spec_path).read_text())
    threading.Thread(target=_watchdog, args=(spec["hard_cap_gb"] * 1e9,), daemon=True).start()
    install_cg_logger()
    base = peak_rss_bytes()
    t0 = time.perf_counter()
    out = solve(spec)
    out.update(status="ok", spec={k: v for k, v in spec.items() if k != "kconst"}, base_rss_bytes=base,
               peak_rss_bytes=peak_rss_bytes(), process_wall_s=time.perf_counter() - t0, cg=CG_LOG,
               cg_max_iters=max((c["iters"] for c in CG_LOG), default=0),
               cg_max_true_rel=max((c["true_rel"] or 0.0 for c in CG_LOG), default=0.0),
               platform=sys.platform)
    Path(spec["out"]).write_text(json.dumps(out))
    return 0


# ------------------------------------------------------------------------------------------------ orchestration
class Runner:
    def __init__(self, ser: dict, mms: dict, full: bool):
        self.ser, self.mms, self.full = ser, mms, full
        self.phys_gb = FEM.physical_memory_bytes() / 1e9
        CACHE.mkdir(parents=True, exist_ok=True)

    def bpd(self, order: int) -> float:
        """Peak bytes/DOF of the largest completed solve of this order (whole process), else the module's bound."""
        best = None
        for p in CACHE.glob("*.json"):
            if p.name.endswith((".spec.json", "calibration.json")):
                continue
            d = json.loads(p.read_text())
            if d.get("status") == "ok" and CANDIDATES[d["spec"]["cid"]]["element_order"] == order:
                if best is None or d["dofs"] > best[0]:
                    best = (d["dofs"], d["peak_rss_bytes"] / d["dofs"])
        return best[1] if best and best[0] >= 2e5 else FEM.BYTES_PER_DOF_BY_ORDER[order]

    def gate(self, est_gb: float) -> tuple[bool, str]:
        if self.full:
            ok = est_gb <= 0.85 * self.phys_gb
            return ok, f"full: est {est_gb:.1f} GB vs 0.85 x {self.phys_gb:.0f} GB"
        if est_gb <= LOCAL_SOFT_GB:
            return True, f"est {est_gb:.2f} GB <= {LOCAL_SOFT_GB} GB"
        if est_gb > LOCAL_HARD_GB:
            return False, f"est {est_gb:.1f} GB > {LOCAL_HARD_GB} GB local cap"
        for _ in range(4):
            free, swap = mem_free_pct(), swap_used_gb()
            if free is not None and free >= 50 and swap is not None and swap < 4:
                return True, f"est {est_gb:.1f} GB; memory_pressure free {free:.0f}%, swap(proxy) {swap:.1f} GB"
            log(f"  waiting: est {est_gb:.1f} GB, free {free}%, swap {swap} GB")
            time.sleep(180)
        return False, f"est {est_gb:.1f} GB: memory_pressure/swap condition not met after 12 min"

    def run(self, cid: str, prob: str, lv: int, var: str = "kT", tag: str = "", **extra) -> dict:
        key = f"{cid}__{prob}__L{lv}__{var}{tag}"
        path = CACHE / f"{key}.json"
        if path.exists():
            return json.loads(path.read_text())
        order = CANDIDATES[cid]["element_order"]
        dofs = count_dofs(grid_of(cid, prob, lv, self.ser, self.mms))
        est_gb = dofs * self.bpd(order) * 1.15 / 1e9
        ok, why = self.gate(est_gb)
        if not ok:
            log(f"  SKIP {key}: {dofs} DOF, {why}")
            return {"status": "skipped_memory", "dofs": dofs, "est_gb": est_gb, "reason": why}
        hard = 0.9 * self.phys_gb if self.full else LOCAL_HARD_GB
        spec = {"cid": cid, "problem": prob, "level": lv, "variant": var, "out": str(path), "hard_cap_gb": hard,
                **extra}
        sp_path = CACHE / f"{key}.spec.json"
        sp_path.write_text(json.dumps(spec))
        log(f"  solve {key}: {dofs} DOF, {why}")
        t0 = time.perf_counter()
        pr = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--worker", str(sp_path)],
                            capture_output=True, text=True, timeout=4 * 3600)
        if pr.returncode != 0 or not path.exists():
            st = {3: "killed_memory", 4: "killed_swap"}.get(pr.returncode, "failed")
            rec = {"status": st, "returncode": pr.returncode, "dofs": dofs, "est_gb": est_gb,
                   "wall_s": time.perf_counter() - t0, "stderr_tail": (pr.stdout + pr.stderr)[-3000:],
                   "spec": {k: v for k, v in spec.items() if k != "kconst"}}
            path.write_text(json.dumps(rec))
            log(f"  {st.upper()} {key}: rc {pr.returncode}: {rec['stderr_tail'][-300:]}")
            return rec
        d = json.loads(path.read_text())
        log(f"  done {key}: {d['dofs']} DOF, {d['wall_s']:.1f} s, peak {d['peak_rss_bytes'] / 1e9:.2f} GB, "
            f"CG max {d['cg_max_iters']}, eb {d['energy_balance']:.1e}")
        return d

    def calibrate(self, cid: str, name: str) -> dict:
        """Equal power per die from level-0 solves: hottest-die rise TARGET +/- CAL_TOL K (proportional update)."""
        p, hist = P_START_W, []
        for it in range(10):
            d = self.run(cid, name, 0, "kT", tag=f"_cal{it}", power_W=p)
            if d.get("status") != "ok":
                return {"status": d.get("status"), "history": hist}
            rise = max(d["tj_max"]) - COOLANT_K
            hist.append({"power_W": p, "rise_K": rise, "key": f"{cid}__{name}__L0__kT_cal{it}"})
            if abs(rise - TARGET_K) <= CAL_TOL_K:
                return {"status": "ok", "power_W": p, "rise_K": rise, "history": hist, "l0_tag": f"_cal{it}"}
            p *= TARGET_K / rise
        return {"status": "failed", "history": hist}

    def study(self, cids, probs) -> None:
        cal = {}
        for lv in LEVELS:
            for cid in cids:
                for prob in probs:
                    if prob in LAYOUTS:
                        if lv == 0:
                            cal[(cid, prob)] = self.calibrate(cid, prob)
                            (CACHE / f"{cid}__{prob}__calibration.json").write_text(json.dumps(cal[(cid, prob)]))
                            continue
                        c = cal[(cid, prob)]
                        if c["status"] == "ok":
                            self.run(cid, prob, lv, power_W=c["power_W"])
                    else:
                        self.run(cid, prob, lv)
        for cid in cids:  # F3 / constant-k nulls at the finest level run, k at that solve's layer-mean temperature
            for prob in [p for p in probs if p == "mms" or p in LAYOUTS]:
                runs = [(lv, self.result(cid, prob, lv)) for lv in LEVELS]
                runs = [(lv, d) for lv, d in runs if d and d.get("status") == "ok"]
                if runs:
                    lv, d = runs[-1]
                    extra = {"power_W": d["power_W"]} if prob in LAYOUTS else {}
                    self.run(cid, prob, lv, "constk", kconst=d["kconst"], **extra)

    @staticmethod
    def result(cid: str, prob: str, lv: int, var: str = "kT") -> dict | None:
        if prob in LAYOUTS and lv == 0 and var == "kT":
            cp = CACHE / f"{cid}__{prob}__calibration.json"
            if not cp.exists():
                return None
            c = json.loads(cp.read_text())
            if c.get("status") != "ok":
                return None
            p = CACHE / f"{cid}__{prob}__L0__kT{c['l0_tag']}.json"
        else:
            p = CACHE / f"{cid}__{prob}__L{lv}__{var}.json"
        return json.loads(p.read_text()) if p.exists() else None


# ------------------------------------------------------------------------------------------------ analysis
def a4(f: list) -> dict:
    """O006 A4 estimator (mfos.metrics.gci_capped, floor 1e-3 K) with branch, p_obs, d1, d2 (as e006_run.a4)."""
    if len(f) < 3:
        return {"gci_K": None, "a4_branch": f"n/a ({len(f)} levels)", "p_obs": None,
                "d1": f[1] - f[0] if len(f) > 1 else None, "d2": None}
    d1, d2 = f[1] - f[0], f[2] - f[1]
    e1 = 0.0 if abs(d1) < GCI_FLOOR_K else d1
    e2 = 0.0 if abs(d2) < GCI_FLOOR_K else d2
    if e1 == 0.0 and e2 == 0.0:
        br, rho = "exact", None
    elif e1 == 0.0:
        br, rho = "divergent", None
    else:
        rho = e2 / e1
        br = "divergent" if abs(rho) >= 1 else "oscillatory" if rho < 0 else "fast" if rho < 0.25 else "monotone"
    p_obs = math.log2(1.0 / rho) if rho is not None and 0 < rho < 1e300 else None
    g = MX.gci_capped(f[0], f[1], f[2], GCI_FLOOR_K)
    return {"gci_K": g if math.isfinite(g) else "inf", "a4_branch": br, "p_obs": p_obs, "d1": d1, "d2": d2}


def _gnum(v) -> float:
    return math.inf if v == "inf" else (math.nan if v is None else float(v))


def cg_iters(c: dict) -> int:
    """CG iterations of one logged linear solve (older entries counted preconditioner calls too: 2 n + 1)."""
    return int(c["iters"]) if c.get("counter") == "cg_only" else (int(c["iters"]) - 1) // 2


def cg_max(d: dict) -> int:
    return max((cg_iters(c) for c in d.get("cg", [])), default=0)


def _solve_stats(runs: list) -> dict:
    dofs = [d["dofs"] for d in runs]
    return {"dofs": dofs, "node_count_ratio": [b / a for a, b in zip(dofs[:-1], dofs[1:], strict=False)],
            "wall_s": [round(d["wall_s"], 2) for d in runs], "peak_rss_GB": [round(d["peak_rss_bytes"] / 1e9, 3) for d in runs],
            "bytes_per_dof": [round(d["peak_rss_bytes"] / d["dofs"], 1) for d in runs],
            "energy_balance": [d["energy_balance"] for d in runs], "picard_residual_K": [d["picard_residual"] for d in runs],
            "picard_iters": [d["picard_iters"] for d in runs], "cg_iters": [[cg_iters(c) for c in d["cg"]] for d in runs],
            "cg_max_iters": [cg_max(d) for d in runs], "cg_final_true_rel_resid": [d["cg_max_true_rel"] for d in runs],
            "cg_over_300": [cg_max(d) > CG_FLAG for d in runs], "max_snap_m": [d["max_snap_m"] for d in runs],
            "snapped_lines": runs[0]["snapped_lines"] if runs else {}}


def _gates(st: dict, extra_eb: list | None = None) -> dict:
    eb = st["energy_balance"] + (extra_eb or [])
    return {"energy_ok": all(v <= 1e-6 for v in eb), "picard_ok": all(v < 1e-4 for v in st["picard_residual_K"]),
            "ratio_ok": all(RATIO_LO <= v <= RATIO_HI for v in st["node_count_ratio"]),
            "cg_ok": not any(st["cg_over_300"])}


def analyse_case(cid: str, prob: str, ser: dict, mms: dict) -> dict:
    runs, lv_run, skipped = [], [], {}
    for lv in LEVELS:
        d = Runner.result(cid, prob, lv)
        if d and d.get("status") == "ok":
            runs.append(d)
            lv_run.append(lv)
        else:
            skipped[lv] = (d or {}).get("status", "not_run")
            break
    out = {"levels_run": lv_run, "levels_not_run": skipped, **_solve_stats(runs)}
    if not runs:
        return out
    if prob == "mms":
        scale = mms["payload"]["case_scale_K"]
        refs = {p["id"]: p["T_K"] for p in mms["payload"]["reported_points"]}
        keyf = lambda p: p["id"]  # noqa: E731
        out["q_out_vs_reference"] = [d["q_out_vs_reference"] for d in runs]
    else:
        scale = ser["cases"][prob]["scale_K"]
        refs = {(r["source"], r["point"]): r["T_K"] for r in ser["rows"] if r["case"] == prob}
        keyf = lambda p: (p["source"], p["point"])  # noqa: E731
    out["gates"] = _gates(out, out.get("q_out_vs_reference"))
    pts = []
    for i, p0 in enumerate(runs[0]["points"]):
        f = [d["points"][i]["T"] for d in runs]
        tref = refs[keyf(p0)]
        err = f[-1] - tref
        node_ok = all(d["points"][i]["x_used"] == p0["x_used"] and d["points"][i]["y_used"] == p0["y_used"] for d in runs)
        pts.append({**{k: p0[k] for k in p0 if k not in ("T", "stencil")}, "values_K": f, "T_ref_K": tref,
                    "abs_err_K": abs(err), "signed_err_K": err, "scaled_err": abs(err) / scale, "err_level": lv_run[-1],
                    **a4(f), "node_same_coords_all_levels": node_ok,
                    "stencil_per_level": [d["points"][i]["stencil"] for d in runs]})
    out.update(case_scale_K=scale, points=pts, max_abs_err_K=max(p["abs_err_K"] for p in pts),
               max_scaled_err=max(p["scaled_err"] for p in pts),
               max_gci_K=max((_gnum(p["gci_K"]) for p in pts), default=math.nan) if len(lv_run) == 3 else None)
    if prob == "mms":
        nul = Runner.result(cid, prob, lv_run[-1], "constk")
        if nul and nul.get("status") == "ok":
            e = [abs(q["T"] - refs[q["id"]]) for q in nul["points"]]
            out["f3_null"] = {"level": lv_run[-1], "kconst_W_mK": runs[-1]["kconst"],
                              "layer_mean_T_K": runs[-1]["layer_mean_T_K"], "max_abs_err_K": max(e),
                              "max_scaled_err": max(e) / scale, "fails_A1": max(e) / scale > THRESH["A1"],
                              "fails_A2": max(e) > THRESH["A2_K"], "cg_max_iters": cg_max(nul),
                              "energy_balance": nul["energy_balance"]}
    return out


def analyse_layout(cid: str, name: str) -> dict:
    cp = CACHE / f"{cid}__{name}__calibration.json"
    cal = json.loads(cp.read_text()) if cp.exists() else {"status": "not_run"}
    runs, lv_run, skipped = [], [], {}
    for lv in LEVELS:
        d = Runner.result(cid, name, lv)
        if d and d.get("status") == "ok":
            runs.append(d)
            lv_run.append(lv)
        else:
            skipped[lv] = (d or {}).get("status", "not_run")
            break
    calruns = [json.loads((CACHE / f"{h['key']}.json").read_text()) for h in cal.get("history", [])]
    out = {"levels_run": lv_run, "levels_not_run": skipped, "calibration": cal,
           "calibration_cg_max_iters": [cg_max(d) if d.get("status") == "ok" else None for d in calruns],
           "fingerprint": dev_layout(name).fingerprint(), **_solve_stats(runs)}
    if not runs:
        out["dies"] = []
        return out
    out["gates"] = _gates(out)
    out["gates"]["cg_ok"] &= all((c or 0) <= CG_FLAG for c in out["calibration_cg_max_iters"])
    nul = Runner.result(cid, name, lv_run[-1], "constk")
    lay = dev_layout(name)
    dies = []
    for i, dd in enumerate(lay.dies):
        f = [d["tj_max"][i] for d in runs]
        xyz = [d["tj_max_xyz"][i] for d in runs]
        moves = sum(1 for a, b in zip(xyz[:-1], xyz[1:], strict=False) if max(abs(u - v) for u, v in zip(a, b, strict=True)) > 1e-9)
        e = a4(f)
        dies.append({"die": i, "switch": dd.switch, "tj_max_K": f, **e, "argmax_xyz": xyz, "argmax_moves": moves,
                     "direction": (None if len(f) < 2 else "from_above" if f[-1] < f[-2] else "from_below"),
                     "tj_max_const_k_K": nul["tj_max"][i] if nul and nul.get("status") == "ok" else None,
                     "dT_const_k_K": (nul["tj_max"][i] - f[-1]) if nul and nul.get("status") == "ok" else None})
    out.update(dies=dies, power_W=runs[0]["power_W"], rise_lv0_K=max(runs[0]["tj_max"]) - COOLANT_K,
               n_divergent=sum(d["a4_branch"] == "divergent" for d in dies),
               n_oscillatory=sum(d["a4_branch"] == "oscillatory" for d in dies),
               n_argmax_moved=sum(d["argmax_moves"] > 0 for d in dies),
               max_gci_K=max(_gnum(d["gci_K"]) for d in dies) if len(lv_run) == 3 else None,
               const_k_null_level=lv_run[-1] if nul and nul.get("status") == "ok" else None)
    return out


def summarise(cid: str, cases: dict, lays: dict) -> dict:
    allc = list(cases.values())
    full3 = all(len(c["levels_run"]) == 3 for c in allc) and all(len(v["levels_run"]) == 3 for v in lays.values())
    cg = [x for c in allc for x in c.get("cg_max_iters", [])] + [x for v in lays.values() for x in v.get("cg_max_iters", [])]
    cg += [x for v in lays.values() for x in v.get("calibration_cg_max_iters", []) if x is not None]
    a1 = max((c.get("max_scaled_err", math.nan) for c in allc), default=math.nan)
    a2 = max((c.get("max_abs_err_K", math.nan) for c in allc), default=math.nan)
    a4c = max((_gnum(c.get("max_gci_K")) for c in allc), default=math.nan)
    a4l = max((_gnum(v.get("max_gci_K")) for v in lays.values()), default=math.nan)
    gates = all(all(c.get("gates", {"x": False}).values()) for c in allc + list(lays.values()))
    cg_ok = max(cg, default=0) <= CG_FLAG
    meets = (a1 <= MARGIN["A1"] and a2 <= MARGIN["A2_K"] and a4c <= MARGIN["A4_cases_K"]
             and a4l <= MARGIN["A4_layouts_K"])
    # measured misses: a case or layout whose three levels were run and whose level-2 values already miss a margin
    miss = [k for k, c in cases.items() if len(c["levels_run"]) == 3 and (
        c["max_scaled_err"] > MARGIN["A1"] or c["max_abs_err_K"] > MARGIN["A2_K"]
        or _gnum(c["max_gci_K"]) > MARGIN["A4_cases_K"])]
    miss += [k for k, v in lays.items() if len(v["levels_run"]) == 3 and _gnum(v["max_gci_K"]) > MARGIN["A4_layouts_K"]]
    return {"levels_complete": full3, "A1_max_scaled_err": a1, "A2_max_abs_err_K": a2, "A4_cases_max_gci_K": a4c,
            "A4_layouts_max_gci_K": a4l, "errors_at_level": {k: c["levels_run"][-1] if c["levels_run"] else None
                                                          for k, c in cases.items()},
            "cg_max_iters": max(cg, default=0), "cg_over_300": not cg_ok, "gates_ok": gates,
            "meets_margins": bool(meets) if full3 else None,
            "eligible": bool(full3 and gates and cg_ok and meets),
            "margin_misses_measured_at_level_2": miss,
            "ruled_out": bool((not cg_ok) or (not gates) or bool(miss) or (full3 and not meets)),
            "verdict": ("eligible" if full3 and gates and cg_ok and meets else
                        "ineligible: CG > 300 iterations" if not cg_ok else
                        "ineligible: a gate failed" if not gates else
                        f"ineligible: margins missed at level 2 on {miss}" if miss or full3 else
                        "unverified: level 2 not run locally")}


def e009_plan(cid: str, ser: dict, mms: dict, cases: dict, lays: dict) -> dict:
    """E009 solve table for one candidate: DOFs (exact grid counts), peak memory and wall time (measured where run,
    else DOF x measured bytes/DOF and wall/DOF x CG growth, labelled extrapolated)."""
    order = CANDIDATES[cid]["element_order"]
    meas = [d for p in CACHE.glob(f"{cid}__*.json") if not p.name.endswith((".spec.json", "calibration.json"))
            for d in [json.loads(p.read_text())] if d.get("status") == "ok"]
    allm = [d for p in CACHE.glob("*.json") if not p.name.endswith((".spec.json", "calibration.json"))
            for d in [json.loads(p.read_text())] if d.get("status") == "ok"
            and CANDIDATES[d["spec"]["cid"]]["element_order"] == order]
    big = max(allm, key=lambda d: d["dofs"]) if allm else None
    bpd = big["peak_rss_bytes"] / big["dofs"] if big else FEM.BYTES_PER_DOF_BY_ORDER[order]
    rows = []

    def add(problem, lv, n_solves, d=None, scale=1.0, label=""):
        dofs = int(count_dofs(grid_of(cid, problem, lv, ser, mms)) * scale)
        if d is not None and scale == 1.0:
            gb, wall, how = d["peak_rss_bytes"] / 1e9, d["wall_s"], "measured"
        else:
            ref = max((m for m in meas if m["spec"]["problem"] == problem), key=lambda m: m["dofs"], default=None)
            ref = ref or max(meas, key=lambda m: m["dofs"], default=None)
            gb = dofs * bpd / 1e9
            if ref:
                lvl_gap = max(0, lv - ref["spec"]["level"])
                wall = ref["wall_s"] * dofs / ref["dofs"] * (1.3 ** lvl_gap)
            else:
                wall = math.nan
            how = f"extrapolated (bytes/DOF {bpd:.0f} of the largest measured Q{order} solve; wall x DOF ratio x 1.3/level)"
        rows.append({"problem": problem + label, "level": lv, "n_solves": n_solves, "dofs": dofs, "peak_GB": gb,
                     "wall_s_each": wall, "basis": how})

    for name in CASES:
        for lv in LEVELS:
            add(name, lv, 1, Runner.result(cid, name, lv) if Runner.result(cid, name, lv) and
                Runner.result(cid, name, lv).get("status") == "ok" else None)
    add("mms", 2, 1, None, 1.0, " constant-k null")
    for name in LAYOUTS:
        for lv in LEVELS:
            d = Runner.result(cid, name, lv)
            add(name, lv, 3 if lv == 0 else 1, d if d and d.get("status") == "ok" else None)
        add(name, 2, 1, None, 1.0, " constant-k column")
    big_lay = max(LAYOUTS, key=lambda n: count_dofs(grid_of(cid, n, 0, ser, mms)))
    for k in range(3):
        for lv in LEVELS:
            add(big_lay, lv, 3 if lv == 0 else 1, None, FRESH_ALLOWANCE, f" (fresh layout {k + 1} allowance)")
        add(big_lay, 2, 1, None, FRESH_ALLOWANCE, f" (fresh layout {k + 1} constant-k)")
    peak = max(r["peak_GB"] for r in rows)
    total_s = sum(r["n_solves"] * r["wall_s_each"] for r in rows if math.isfinite(r["wall_s_each"]))
    cap = BURST["memory_GB"] * BURST["usable_fraction"]
    return {"rows": rows, "peak_GB": peak, "fits_burst": peak <= cap, "burst": {**BURST, "usable_GB": cap},
            "total_wall_h": total_s / 3600, "cpu_hours_est": total_s / 3600,
            "recommended_timeout_h": max(2.0, math.ceil(3.0 * total_s / 3600)),
            "note": "scikit-fem solves only; E009's finite-volume L2 cross-check (levels 1-3 of its rule) is costed "
                    "separately (research/notes/o007-l2-crosscheck-preview.md). CPU-hours = wall-hours: the "
                    "assembly and AMG-CG are essentially single-threaded."}


def report() -> int:
    ser, mms, hashes = load_refs()
    cands = {}
    for cid in CANDIDATES:
        cases = {p: analyse_case(cid, p, ser, mms) for p in CASES}
        lays = {n: analyse_layout(cid, n) for n in LAYOUTS}
        s = summarise(cid, cases, lays)
        plan = e009_plan(cid, ser, mms, cases, lays)
        s["fits_burst"] = plan["fits_burst"]
        s["eligible"] = bool(s["eligible"] and plan["fits_burst"])
        cands[cid] = {"config": CANDIDATES[cid], "summary": s, "cases": cases, "layouts": lays, "e009_plan": plan}
    order = sorted(CANDIDATES, key=lambda c: cands[c]["e009_plan"]["peak_GB"])
    elig = [c for c in order if cands[c]["summary"]["eligible"]]
    open_ = [c for c in order if not cands[c]["summary"]["ruled_out"]]
    if elig:
        chosen, feasible, why = elig[0], True, "cheapest verified-eligible candidate by E009 finest-level peak memory"
    elif open_:
        chosen, feasible, why = open_[0], False, ("no candidate verified eligible; provisional choice: cheapest "
                                                 "candidate not ruled out by the data (level 2 incomplete)")
    else:
        chosen, feasible, why = order[0], False, ("every candidate ruled out by measured data; 'chosen' lists the cheapest candidate (complete three-level data) "
                                         "for the record only, not as a recommendation (case not pre-specified)")
    q2 = [{"key": p.stem, "dofs": d["dofs"], "peak_GB": d["peak_rss_bytes"] / 1e9,
           "bytes_per_dof": d["peak_rss_bytes"] / d["dofs"]}
          for p in sorted(CACHE.glob("q2*.json")) if not p.name.endswith((".spec.json", "calibration.json"))
          for d in [json.loads(p.read_text())] if d.get("status") == "ok"]
    study = {"meta": {"task": "T0207", "objective": "O007", "references": hashes, "dev_seed": DEV_SEED,
                      "thermal_fem_sha256": hashlib.sha256((ROOT / "src/moduleforge/solvers/thermal_fem.py").read_bytes()).hexdigest(),
                      "machine_physical_GB": FEM.physical_memory_bytes() / 1e9, "platform": sys.platform,
                      "margins": MARGIN, "thresholds": THRESH, "cg_flag": CG_FLAG, "cg_cap": CG_CAP,
                      "local_rule_GB": {"soft": LOCAL_SOFT_GB, "hard": LOCAL_HARD_GB},
                      "full_command": 'scripts/burst_gcp.sh --cmd "uv run python research/scripts/o007_dev_study.py '
                                      '--full" research/o007_dev'},
             "candidates": cands, "selection_order_by_peak_GB": order,
             "chosen": {"id": chosen, "feasible": feasible, "why": why, "summary": cands[chosen]["summary"],
                        "cases": cands[chosen]["cases"], "layouts": cands[chosen]["layouts"],
                        "e009_plan": cands[chosen]["e009_plan"]},
             "q2_bytes_per_dof": q2}
    (OUT / "dev_study.json").write_text(json.dumps(study, indent=1, default=float))
    c = CANDIDATES[chosen]
    s = cands[chosen]["summary"]
    frozen = {"element_order": c["element_order"], "h0_m": c["h0_m"], "near_margin_m": c["near_margin_m"],
              "dz_max_m": c["dz_max_m"], "nz_min": NZ_MIN, "min_cells": 2, "zrefine": True,
              "refinement_ratio": FEM.REFINEMENT_RATIO, "snap_fraction": FEM.SNAP_FRACTION, "amg_seed": FEM.AMG_SEED,
              "mandatory_lines": MANDATORY_POLICY,
              "quadrature": {"stiffness": "2x2x2 Gauss (Q1)" if c["element_order"] == 1 else "3x3x3 Gauss (Q2)",
                             "faces": "3x3 Gauss (intorder 4)", "manufactured_data": "4x4x4 / 4x4 Gauss (intorder 7)"},
              "linear_rtol": FEM.LINEAR_RTOL, "cg_maxiter": CG_CAP, "cg_eligibility_limit": CG_FLAG,
              "picard_tol_K": FEM.PICARD_TOL_K, "levels": list(LEVELS), "candidate_id": chosen, "feasible": feasible,
              "rationale": (f"{why}. Summary: {json.dumps(s, default=float)}. Pre-registered criterion: "
                            "research/notes/o007-dev-study.md sec. 0.")}
    (OUT / "frozen_config.json").write_text(json.dumps(frozen, indent=1, default=float))
    log(f"chosen {chosen} feasible={feasible}: {why}")
    for cid in order:
        log(f"  {cid}: {json.dumps(cands[cid]['summary'], default=float)} peak {cands[cid]['e009_plan']['peak_GB']:.1f} GB")
    return 0


def plan() -> int:
    ser, mms, hashes = load_refs()
    rows = []
    for cid in CANDIDATES:
        for prob in CASES + LAYOUTS:
            for lv in LEVELS:
                g = grid_of(cid, prob, lv, ser, mms)
                rows.append({"cid": cid, "problem": prob, "level": lv, "dofs": count_dofs(g), "cells": list(g.mat.shape),
                             "min_cell_ratio": min_cell_ratio(g),
                             "snaps": {k: len(v) for k, v in g.snaps.items()}})
                log(f"{cid} {prob} L{lv}: {rows[-1]}")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "plan.json").write_text(json.dumps({"references": hashes, "rows": rows}, indent=1))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--plan", action="store_true")
    ap.add_argument("--full", action="store_true")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--worker")
    ap.add_argument("--candidates", default=",".join(CANDIDATES))
    ap.add_argument("--problems", default=",".join(CASES + LAYOUTS))
    a = ap.parse_args(argv)
    if a.worker:
        return worker(a.worker)
    if a.plan:
        return plan()
    if a.report:
        return report()
    ser, mms, hashes = load_refs()
    log(f"references verified: {hashes['series_sha256'][:8]} / {hashes['mms_sha256'][:8]}")
    for n in LAYOUTS:
        log(f"dev layout {n}: fingerprint {dev_layout(n).fingerprint()[:12]} (E006 spec)")
    Runner(ser, mms, a.full).study(a.candidates.split(","), a.problems.split(","))
    return report()


if __name__ == "__main__":
    sys.exit(main())
