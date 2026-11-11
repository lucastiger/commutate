"""E008 runner (O003): module-level loop-inductance headroom of reference layouts inside their own housing at <= +2 K Tj.

Design: experiments/drafts/E008.yaml (T0262).  Objective: project/objectives/O003/objective.yaml v5 (D0015-D0017).  Row
contract: research/o003/e008_row_contract.md.  SI units, float64; inductance in H, temperature in K.

The search itself is the frozen driver ``moduleforge.optimize.search`` (run_search / run_control) with real solvers:
L1 = ``physics.peec`` in process; L_sub and the band levels = ``solvers.l2_layout.loop_inductance`` with the mesh constants
overridden per subprocess as research/scripts/o006_p3_em_convergence.py does (src/ is never modified); Tj = production
``solvers.thermal_fem`` with the GridRule built key for key from research/o007_dev3/frozen_config.json; the stack-type spot
check also runs ``solvers.thermal_layout`` (the finite-volume L2) at its levels 1-3.  Every l2_layout and thermal solve
runs in its own subprocess with OPENBLAS/OMP/MKL_NUM_THREADS and MF_L2_FFT_WORKERS set to the per-solve thread count of
research/l2_thread_calib/summary.txt (1 if absent; MF_L2_THREADS = 1), recorded in each solve's provenance, and writes
one JSON result file (the checkpoint: a rerun re-solves nothing that exists).

Concurrency without touching the driver: the driver is replayed until it completes.  Its injected solvers read result
files; a missing result raises ``Pending`` with the jobs it needs, which the scheduler runs concurrently (as many as fit
in the memory cap by their --plan estimates and in the vCPU count), mixing EM, band, thermal and control solves of every
reference.  A stage mirror (``prefetch``) submits the solves the driver will certainly ask for next, so no stage waits
for an unrelated one; the driver alone decides what is used.  The candidate screens (main and control, every reference)
run first, each in its own 1-thread subprocess that streams the sealed sequence through the driver itself and records
the fingerprints and family strings of each chunk; replays then stream lightweight stubs (fingerprint + family), so the
sealed sequence never depends on the schedule.

Modes
  (default)        registered run through mfos.evidence.ExperimentRun (sealed seed; config from MFOS_SPEC_JSON)
  --selftest       fake solvers and fake layouts, the full replay/scheduler/row/recompute path, planted outcomes checked
                   against hand values and against research/o003/headroom_metrics.py and mfos.metrics; exit 0 iff all pass
  --verify-freeze  recompute every frozen hash (freeze block, GridRule file and keys, thermal_fem.py) and the exact metric
                   parameters floor = 1e-3 K and tj_limit_K = 2.0 K; exit 0 iff all match
  --dev            development geometry only (generator housings, 2D_Case_4); writes experiments/drafts/E008.dev_rows.json
                   (smoke rows when --smoke: EM production slot at 0.5 mm, coarsened thermal rule, reduced budget)
  --plan           every solve with its memory and time estimate, the VM schedule, VM-hours, $ and the date
  --child JOB      internal: one solve in a subprocess
References for the cited formulas: P3's band estimator and Roache (1998) ch. 5 via mfos.metrics.ratio_band_estimate and
gci_capped; the operating point and the Tj tests are O003 scope_in (no new formula here).
"""
from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import gzip
import hashlib
import json
import math
import os
import pickle
import re
import resource
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "tools" / "mfos"), str(ROOT / "src")]

import yaml  # noqa: E402
from mfos import metrics as MX  # noqa: E402

EID = "E008"
DRAFT = ROOT / "experiments" / "drafts" / "E008.yaml"
REGISTERED = ROOT / "experiments" / "specs" / "E008.yaml"
DEV_ROWS = ROOT / "experiments" / "drafts" / "E008.dev_rows.json"
E0 = (0, .35, .6, .8, .93, 1)
E1 = (0, .175, .35, .475, .6, .7, .8, .865, .93, .965, 1)
# EM levels (P3's, frozen): name -> (cell mm, layers top/back/base, wire annulus edges)
EM_LEVELS = {"lat0.25": (0.25, (10, 6, 6), E0), "lat0.5": (0.5, (10, 6, 6), E0), "thk_c": (0.5, (5, 3, 3), E0),
             "thk_f": (0.5, (20, 12, 12), E0), "fil_f": (0.5, (10, 6, 6), E1), "lat0.125": (0.125, (10, 6, 6), E0)}
BAND = ("lat0.25", "lat0.5", "thk_c", "thk_f", "fil_f")  # search.Solvers.band order = headroom_metrics HR_BAND order
BAND_COLS = ("L_sub_H", "L_sub_c05_H", "L_sub_thk_c_H", "L_sub_thk_f_H", "L_sub_wire_f_H")
THREAD_VARS = ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "MF_L2_FFT_WORKERS")


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def sha256_file(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def load_spec() -> dict:
    env = os.environ.get("MFOS_SPEC_JSON")
    if env:
        return json.loads(Path(env).read_text()) if Path(env).exists() else json.loads(env)
    return yaml.safe_load((REGISTERED if REGISTERED.exists() else DRAFT).read_text())


def FEM():
    from moduleforge.solvers import thermal_fem
    return thermal_fem


def rule_from(fr: dict):
    """The one scikit-fem GridRule of E008, key for key from the frozen configuration (as E009's rule_from)."""
    eg = fr["edge_grading"]
    return FEM().GridRule(h0=float(fr["h0_m"]), nz={}, default_nz=int(fr["nz_min"]), zrefine=bool(fr["zrefine"]),
                          near_margin=float(fr["near_margin_m"]), min_cells=int(fr["min_cells"]),
                          element_order=int(fr["element_order"]), dz_max=float(fr["dz_max_m"]),
                          edge_grading=(float(eg["first_offset_m"]), float(eg["ratio"]), float(eg["max_offset_m"]),
                                        float(eg["min_gap_fraction"])), amg_gs_sweeps=int(fr["amg_gs_sweeps"]))


def l1_of(layout) -> float:
    from moduleforge.generate import twin as W
    return W._l1(layout)


def derive_seed(sealed: int, purpose: int, ref_index: int) -> int:
    return int(np.random.SeedSequence([int(sealed), int(purpose), int(ref_index)]).generate_state(1)[0])


# ------------------------------------------------------------------------------------------------ freeze (F3, F6(b))
def freeze_checks(cfg: dict) -> list[dict]:
    """Every frozen hash and value: the freeze block, the GridRule file (sha256 and key for key), thermal_fem.py, and
    the metric parameters floor = 1e-3 K and tj_limit_K = 2.0 K in every headroom recompute entry."""
    out = []

    def add(name, ok, detail):
        out.append({"name": name, "passed": bool(ok), "detail": detail})
    for path, want in cfg["freeze"]["files"].items():
        got = sha256_file(ROOT / path) if (ROOT / path).exists() else "missing"
        add(f"freeze:{path}", got == want, f"{got} vs {want}")
    fr = ROOT / cfg["fem_rule_path"]
    add("grid_rule_file_sha256", sha256_file(fr) == cfg["fem_rule_file_sha256"], sha256_file(fr))
    frozen = json.loads(fr.read_text())
    add("grid_rule_key_for_key", frozen == cfg["fem_rule"],
        "equal" if frozen == cfg["fem_rule"] else f"differs in {sorted(k for k in set(frozen) | set(cfg['fem_rule']) if frozen.get(k) != cfg['fem_rule'].get(k))}")
    tf = sha256_file(ROOT / cfg["thermal_fem_path"])
    add("thermal_fem_sha256", tf == cfg["thermal_fem_sha256"] and tf.startswith("a216d5fe"), tf)
    mp = cfg["metric_params"]
    add("metric_params_exact", mp.get("floor") == 1e-3 and mp.get("tj_limit_K") == 2.0, json.dumps(mp))
    return out


def verify_freeze() -> int:
    spec = load_spec()
    cfg = spec["config"]
    res = freeze_checks(cfg)
    bad = []
    for e in spec.get("recompute", []):
        if e["fn"] in ("headroom_min_lo", "headroom_max_hi_ind"):
            p = e.get("params", {})
            if p.get("floor") != 1e-3 or p.get("tj_limit_K") != 2.0:
                bad.append(e["metric"])
    res.append({"name": "recompute_params_exact", "passed": not bad, "detail": f"entries without floor 1e-3 and "
                f"tj_limit_K 2.0: {bad}"})
    cm = [c.get("path") for c in spec.get("code_must_match", []) if c.get("objective") == "O007"]
    res.append({"name": "code_must_match_O007", "passed": cfg["thermal_fem_path"] in cm
                and "O007" in spec.get("requires_passed", []), "detail": f"{cm} {spec.get('requires_passed')}"})
    for r in res:
        print(("OK   " if r["passed"] else "FAIL ") + r["name"] + "  " + str(r["detail"])[:160])
    return 0 if all(r["passed"] for r in res) else 1


# ------------------------------------------------------------------------------------------------ compute settings
def thread_count(cfg: dict) -> tuple[int, str]:
    """Per-solve thread count: 2 if research/l2_thread_calib/summary.txt shows the two-thread 0.25 mm solves (C_two_*)
    faster on average than the pinned ones (B_pinned_*), else 1; 1 if the file is absent (founder run plan, 2026-11-09)."""
    p = ROOT / cfg["compute"]["thread_calib_summary"]
    if not p.exists():
        return 1, "summary absent: 1 thread"
    walls: dict[str, list[float]] = {"B": [], "C": []}
    for line in p.read_text().splitlines():
        m = re.match(r"([BC])_\S+_lat0\.25\s+wall\s+(\d+) s", line)
        if m:
            walls[m[1]].append(float(m[2]))
    if walls["B"] and walls["C"] and np.mean(walls["C"]) < np.mean(walls["B"]):
        return 2, f"two threads: mean wall {np.mean(walls['C']):.0f} s vs pinned {np.mean(walls['B']):.0f} s"
    return 1, "pinned (one thread) not slower"


def child_env(n: int) -> dict:
    env = dict(os.environ)
    for k in THREAD_VARS:
        env[k] = str(n)
    env["MF_L2_THREADS"] = "1"
    return env


def em_unknowns(area_m2: float, cell_mm: float, level: str, cm: dict) -> int:
    """Unknown count of an l2_layout solve from the baseplate lattice area (P3 calibration, 2D_Case_4: 4,108,580 unknowns
    on 80 x 110 mm at 0.25 mm, i.e. 29.18 per lattice cell; thickness levels scale with the layer counts as P3 measured)."""
    cells = area_m2 / (cell_mm * 1e-3) ** 2
    return int(cm["em_unknowns_per_cell"] * cells * cm["em_level_unknown_factor"].get(level, 1.0))


def em_cost(n: int, level: str, cm: dict) -> tuple[float, float]:
    """(wall s, peak GB) of one l2_layout solve with n unknowns at the scheduled thread count, from the founder's VM
    calibration (n2d-custom-8, four 0.25 mm Case 4 solves at once, two threads: 5,678-5,862 s, 15.9 GB at 4.11 M
    unknowns; 0.5 mm pinned alone 846 s at 1.02 M) with wall ~ n^alpha, alpha = em_alpha = 1.44, and P3's wall ratios
    of the 0.5 mm-cell band variants; memory linear in n (P3: 3.9 / 8.1 / 15.8 GB at 1.0 / 2.0 / 4.1 M).  The two points
    named here give alpha = ln(5770 / 846) / ln 4 = 1.385, not 1.44; pinned against pinned (6,364 s vs 846 s) gives
    1.456 (T0304 finding 2).  1.44 lies between them; at 0.5 mm it predicts 5770 x 0.25^1.44 = 784 s against 765-846 s
    observed, so the choice moves the plan by well under 1 %."""
    t = cm["em_ref_wall_s"] * (n / cm["em_ref_unknowns"]) ** cm["em_alpha"] * cm["em_level_time_factor"].get(level, 1.0)
    return t, cm["em_mem_base_GB"] + cm["em_mem_GB_per_Munknown"] * n / 1e6


def fem_cost(dofs: float, cm: dict) -> tuple[float, float]:
    """(wall s, peak GB) of one scikit-fem k(T) solve: E009's 4,964 B/DOF x 1.15 (memory) and the measured Mac k(T) rate
    (1.18e-4 s/DOF: MMS level 2, 1.58 M DOFs, 186 s; gen2_0 smoke level 1, 0.68 M DOFs, 80 s) x the VM/Mac factor."""
    return cm["fem_s_per_dof"] * dofs, cm["fem_mem_base_GB"] + cm["fem_bytes_per_dof"] * cm["fem_memory_margin"] * dofs / 1e9


def fv_cost(cells: float, cm: dict, beta: float | None = None, s_per_cell: float | None = None) -> tuple[float, float]:
    """(wall s, peak GB) of one finite-volume L2 solve (thermal_layout; ``cells`` = the box-grid count of
    build_layout_grid, void cells included).  Wall: the measured rate fv_s_per_cell at fv_ref_cells, scaled as
    (cells / fv_ref_cells)^fv_beta (T0306: 2D_Case_4 level 1, 3,669,120 cells, 20.13 and 21.06 s in two runs on one Mac
    core, mean taken, x fv_vm_factor, the FV solver's Mac -> VM wall ratio measured on identical O007 level-1 solves
    (e2-highmem-16 vs Mac, 4.66-5.55, research/o003/e008_dev/fv_vm_factor.json); fv_beta from Case 4's level 0 -> 1 step
    on the mean walls; research/o003/e008_dev/fv_rate_*.json, cost_model.fv_rate_basis).
    ``beta`` and ``s_per_cell`` override the two for the sensitivity range.  Memory: E009's 1,500 B/cell (T0306 measured
    1,199 B/cell peak RSS at Case 4 level 1, interpreter included, so the E009 figure is kept as the conservative one)."""
    b = cm["fv_beta"] if beta is None else beta
    s = cm["fv_s_per_cell"] if s_per_cell is None else s_per_cell
    return (s * cm["fv_ref_cells"] * (cells / cm["fv_ref_cells"]) ** b,
            cm["fem_mem_base_GB"] + cm["fv_bytes_per_cell"] * cells / 1e9)


# ------------------------------------------------------------------------------------------------ child solves
def _load_ctx(path: str) -> dict:
    with open(path, "rb") as f:
        return pickle.load(f)


def layout_of(job: dict):
    ctx = _load_ctx(job["ctx"])
    if job["which"] in ("reference", "twin", "D", "snap025"):
        lay = ctx[job["which"]]
    else:
        from moduleforge.generate import derivative as D
        lay = D.build(ctx["spec"], D.params_of(SimpleNamespace(family=job["family"])))
    if lay.fingerprint() != job["fp"]:
        raise RuntimeError(f"layout fingerprint {lay.fingerprint()} is not the job's {job['fp']}")
    return lay


def _rss_gb() -> float:
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * (1.0 if sys.platform == "darwin" else 1024.0) / 1e9


def _prov() -> dict:
    return {k: os.environ.get(k) for k in THREAD_VARS + ("MF_L2_THREADS",)} | {"host": os.uname().nodename}


def child_em(job: dict) -> dict:
    from moduleforge.solvers import l2_layout as L
    cell, layers, edges = EM_LEVELS[job["level"]]
    L.CELL = (cell * 1e-3,) + tuple(L.CELL[1:])
    for attr, n in zip(("LAYERS_TOP", "LAYERS_BACK", "LAYERS_BASE"), layers, strict=True):
        setattr(L, attr, (n,) + tuple(getattr(L, attr)[1:]))
    L.WIRE_EDGES = (tuple(edges),) + tuple(L.WIRE_EDGES[1:])
    lay = layout_of(job)
    t0, c0 = time.perf_counter(), time.process_time()
    r = L.loop_inductance(lay, [job["freq_hz"]], refinement=0)
    m = r.meta
    return {"L_H": float(r.L_H[0]), "R_ohm": float(r.R_ohm[0]), "n_unknowns": int(m["n_unknowns"]),
            "gmres_iters": [int(x) for x in m["gmres_iters"]], "gmres_flags": [int(x) for x in m["gmres_flags"]],
            "solver_tol_rel_L_max": float(m["solver_tol_rel_L_max"]), "wall_s": time.perf_counter() - t0,
            "cpu_s": time.process_time() - c0, "peak_GB": _rss_gb(), "source_sha256": m["source_sha256"],
            "tool_version": m["tool_version"], "fingerprint": lay.fingerprint(), "threads": _prov()}


def _die_top_max(res, lay) -> tuple[list[float], list[list[float]]]:
    """Per die: the maximum nodal value on the die top face and its node (C004: Tj max = max nodal value on the die top
    face).  The top face is the highest node plane inside the die footprint."""
    X, T = np.asarray(res.nodes), np.asarray(res.T)
    vals, nodes = [], []
    for d in lay.dies:
        x0, y0, x1, y1 = d.bounds
        m = (X[:, 0] >= x0 - 1e-9) & (X[:, 0] <= x1 + 1e-9) & (X[:, 1] >= y0 - 1e-9) & (X[:, 1] <= y1 + 1e-9)
        idx = np.flatnonzero(m)
        top = idx[np.abs(X[idx, 2] - X[idx, 2].max()) < 1e-9]
        k = top[np.argmax(T[top])]
        vals.append(float(T[k]))
        nodes.append([float(v) for v in X[k]])
    if np.max(np.abs(np.asarray(vals) - np.asarray(res.tj_max, float))) > 1e-9:
        raise RuntimeError("die top-face maxima differ from thermal_fem's tj_max")
    return vals, nodes


def _fem_rec(r, lay, level: int, sweeps: int) -> dict:
    if r.meta.get("amg_gs_sweeps") != sweeps:
        raise RuntimeError(f"amg_gs_sweeps {r.meta.get('amg_gs_sweeps')} is not the frozen {sweeps}")
    tj, nodes = _die_top_max(r, lay)
    return {"level": level, "tj": tj, "tj_node": nodes, "nodes": int(r.dofs), "energy_balance": float(r.energy_balance),
            "picard_iters": int(r.picard_iters), "picard_residual_K": float(r.picard_residual),
            "cg_max_iterations": r.meta.get("cg_max_iterations"), "cg_hit_maxiter": r.meta.get("cg_hit_maxiter"),
            "wall_s": float(r.wall_s), "fingerprint": lay.fingerprint()}


def child_thermal(job: dict) -> dict:
    lay = layout_of(job)
    rule = rule_from(job["fem_rule"])
    r = FEM().solve_layout(lay, job["power_W"], job["h"], job["T_c"], rule=rule, level=job["level"])
    return _fem_rec(r, lay, job["level"], rule.amg_gs_sweeps) | {"peak_GB": _rss_gb(), "threads": _prov()}


def child_calibrate(job: dict) -> dict:
    """P_ref (O003 scope_in): equal power per die from level-0 solves of the reconstruction so that its hottest die rises
    target +/- calibration_tol above the coolant (proportional update, as E009's calibrate_power); the record at exactly
    P_ref is returned, so F6(d) checks the rise computed at that power."""
    lay = layout_of(job)
    rule = rule_from(job["fem_rule"])
    p, hist = float(job["power_start_W"]), []
    for _ in range(int(job["max_iters"])):
        r = FEM().solve_layout(lay, p, job["h"], job["T_c"], rule=rule, level=0)
        rec = _fem_rec(r, lay, 0, rule.amg_gs_sweeps)
        rise = max(rec["tj"]) - job["T_c"]
        hist.append({"power_W": p, "rise_K": rise, "energy_balance": rec["energy_balance"],
                     "picard_residual_K": rec["picard_residual_K"]})
        if abs(rise - job["target_K"]) <= job["tol_K"]:
            return {"P_ref_W": p, "rise_K": rise, "history": hist, "record": rec, "peak_GB": _rss_gb(), "threads": _prov()}
        p *= job["target_K"] / rise
    raise RuntimeError(f"calibration did not converge: {hist}")


def child_fv(job: dict) -> dict:
    from moduleforge.solvers import thermal_layout as TL
    lay = layout_of(job)
    r = TL.solve_layout_level(lay, level=job["level"], power_W=job["power_W"], h=job["h"], T_c=job["T_c"])
    v, m = r["values"], r["meta"]
    return {"level": job["level"], "tj": [float(v[f"die{i}.tj_max"]) for i in range(len(lay.dies))],
            "energy_balance": float(m["energy_balance"]), "n_cells": int(m["n_cells"]), "peak_GB": _rss_gb(),
            "picard_iters": int(m["picard_iters"]), "solver_wall_s": float(m["wall_time_s"]),
            "fingerprint": lay.fingerprint(), "threads": _prov()}


class _ScreenDone(Exception):
    pass


def child_screen(job: dict) -> dict:
    """Stream the sealed sequence through the frozen driver itself (its own _screen, L1 in its checkpoint) and record the
    (fingerprint, family) of every candidate per chunk; stops when the driver asks for the first L_sub."""
    from moduleforge.generate import derivative as D
    from moduleforge.optimize import search as S
    ctx = _load_ctx(job["ctx"])
    chunks: dict[str, list] = {}
    t0 = time.perf_counter()

    def gen(spec, m, sk):
        lays = D.generate(spec, m, sk)
        chunks[f"{m}:{sk}"] = [(lay.fingerprint(), lay.family) for lay in lays]
        return lays

    def stop(*_):
        raise _ScreenDone
    sv = S.Solvers(l1=l1_of, l_sub=stop, band=stop, thermal=stop)
    cfg = S.SearchConfig(**job["search"])
    try:
        if job["ns"] == "main":
            S.run_search(ctx["spec"], ctx["reference"], ctx["twin"], job["seed"], sv, None, 0.0, job["wd"], cfg, gen)
        else:
            S.run_control(ctx["spec"], ctx["D"], job["seed"], sv, 0.0, job["wd"], cfg, gen)
    except _ScreenDone:
        pass
    with gzip.open(Path(job["wd"]) / "stream.json.gz", "wt") as f:
        json.dump(chunks, f)
    n = sum(len(v) for v in chunks.values())
    return {"n_candidates": n, "wall_s": time.perf_counter() - t0, "s_per_candidate": (time.perf_counter() - t0) / max(n, 1),
            "peak_GB": _rss_gb(), "threads": _prov()}


CHILD = {"em": child_em, "thermal": child_thermal, "calibrate": child_calibrate, "fv": child_fv, "screen": child_screen}


def child_main(path: str) -> int:
    job = json.loads(Path(path).read_text())
    t0 = time.perf_counter()
    try:
        rec = CHILD[job["type"]](job)
        rec.update(status="ok", job_wall_s=time.perf_counter() - t0)
    except Exception as e:  # recorded, never a verdict: the parent stops on a failed job
        rec = {"status": "failed", "error": f"{type(e).__name__}: {e}"[:3000]}
    out = Path(job["out"])
    tmp = out.with_suffix(".tmp")
    tmp.write_text(json.dumps(rec, default=float))
    tmp.replace(out)
    return 0 if rec["status"] == "ok" else 1


# ------------------------------------------------------------------------------------------------ scheduler
class Pending(Exception):
    def __init__(self, jobs: list[dict]):
        super().__init__(f"{len(jobs)} solve(s) pending")
        self.jobs = jobs


def _free_pct() -> float:
    """macOS memory_pressure 'free percentage' (100 elsewhere: the VM's limit is the 0.85 x RAM cap)."""
    if sys.platform != "darwin":
        return 100.0
    try:
        out = subprocess.run(["memory_pressure"], capture_output=True, text=True, timeout=30).stdout
        return float(re.search(r"free percentage:\s*(\d+)", out)[1])
    except (OSError, subprocess.SubprocessError, TypeError):
        return 0.0


class Scheduler:
    """Runs jobs concurrently in subprocesses, as many as fit in ``mem_cap_GB`` by their estimates and in ``vcpus`` by
    their thread counts.  A job whose result file exists is done.  ``fake`` (selftest) computes results in process."""

    def __init__(self, mem_cap_GB: float, vcpus: int, threads: int, fake=None, solo_cap_GB: float | None = None):
        self.cap, self.vcpus, self.threads, self.fake = mem_cap_GB, vcpus, threads, fake
        self.solo = max(solo_cap_GB or mem_cap_GB, mem_cap_GB)  # a job above cap runs only alone, up to solo
        self.queue: dict[str, dict] = {}
        self.running: dict[str, tuple] = {}
        self.log: list[dict] = []
        self.mem_ratio: dict[tuple, float] = {}  # (reference, type, level) -> max measured peak / model peak

    @staticmethod
    def _mkey(j: dict) -> tuple:
        return j.get("ref"), j["type"], str(j.get("level", ""))

    def learn(self, j: dict, rec: dict | None) -> None:
        """Record the measured peak of a finished (or cached) job against its model peak (T0262 attempt 5: on gen2_0 the
        0.5 mm-cell band solves peaked at 1.1-2.6x the per-unknown model, fil_f worst; P3's Case 4 at 0.86-1.04x)."""
        if rec and rec.get("peak_GB") and j.get("mem_model_GB"):
            k = self._mkey(j)
            self.mem_ratio[k] = max(self.mem_ratio.get(k, 0.0), float(rec["peak_GB"]) / j["mem_model_GB"])

    def mem_of(self, j: dict) -> float:
        """Scheduling peak of a job: the model x 1.1 x the largest measured ratio of the same reference, type and level once
        one has finished; before that the prior (model x per-level prior factor, set by Run.estimate)."""
        k = self._mkey(j)
        if j.get("mem_model_GB") and k in self.mem_ratio:
            return j["mem_model_GB"] * 1.1 * self.mem_ratio[k]
        return j["mem_GB"]

    @staticmethod
    def done(job: dict) -> dict | None:
        p = Path(job["out"])
        if not p.exists():
            return None
        rec = json.loads(p.read_text())
        if rec.get("status") != "ok":
            raise RuntimeError(f"job {job['out']} failed: {rec.get('error')}")
        return rec

    def submit(self, jobs: list[dict]) -> None:
        for j in jobs:
            if j["out"] in self.queue or j["out"] in self.running:
                continue
            rec = self.done(j)
            if rec is not None:
                self.learn(j, rec)  # a cached result (resume) teaches the same as a finished one
            else:
                j["mem_GB"] = self.mem_of(j)
                if j["mem_GB"] > self.solo:
                    raise RuntimeError(f"job {j['out']} needs {j['mem_GB']:.1f} GB > cap {self.solo:.1f} GB")
                self.queue[j["out"]] = j

    def _launch(self) -> None:
        for key, j in sorted(self.queue.items(), key=lambda kv: (-kv[1].get("priority", 0), -kv[1]["mem_GB"])):
            if self.fake is not None:
                Path(j["out"]).write_text(json.dumps(self.fake(j) | {"status": "ok"}))
                del self.queue[key]
                continue
            j["mem_GB"] = self.mem_of(j)  # estimates learned since the job was queued
            used = sum(r[1]["mem_GB"] for r in self.running.values())
            thr = sum(r[1]["threads"] for r in self.running.values())
            alone = not self.running and j["mem_GB"] <= self.solo
            if (used + j["mem_GB"] > self.cap and not alone) or thr + j["threads"] > self.vcpus:
                continue
            if j["mem_GB"] > self.cap and _free_pct() < 50.0:  # local house rule: a large job only with >= 50 % free
                log(f"wait: {Path(j['out']).name} needs {j['mem_GB']:.1f} GB alone, memory free {_free_pct():.0f} % < 50 %")
                self.waited = True
                continue
            jf = Path(j["out"]).with_suffix(".job.json")
            jf.write_text(json.dumps(j))
            lf = open(Path(j["out"]).with_suffix(".log"), "w")
            pr = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "--child", str(jf)],
                                  env=child_env(j["threads"]), stdout=lf, stderr=subprocess.STDOUT, cwd=ROOT)
            self.running[key] = (pr, j, time.time(), lf)
            del self.queue[key]
            log(f"start {j['type']} {j.get('level', '')} {Path(j['out']).name} ({j['mem_GB']:.1f} GB est)")

    def step(self) -> None:
        """Launch what fits, then block until at least one running job ends (or return if nothing runs)."""
        self.waited = False
        self._launch()
        if self.waited and not self.running:
            time.sleep(60.0)
        while self.running:
            for key, (pr, j, t0, lf) in list(self.running.items()):
                if pr.poll() is not None:
                    lf.close()
                    del self.running[key]
                    self.log.append({"out": Path(j["out"]).name, "type": j["type"], "wall_s": time.time() - t0,
                                     "rc": pr.returncode})
                    self.learn(j, self.done(j))  # done() raises on a failed job
                    return
            time.sleep(2.0)


# ------------------------------------------------------------------------------------------------ references
@dataclasses.dataclass
class RefCtx:
    rid: str
    kind: str  # dev | public | customer
    spec: Any
    reference: Any
    twin: Any = None
    twin_rec: dict = dataclasses.field(default_factory=dict)
    D: Any = None
    d_rec: dict = dataclasses.field(default_factory=dict)
    on_grid: bool = True
    snap025: Any = None
    L_term_H: float = 7e-9
    admissible: bool = True
    info: dict = dataclasses.field(default_factory=dict)
    stack_type: str = ""
    area_m2: float = 0.0


DEFAULT_STACK = "Al2O3_default_dbc"


def _stack_signature(stack) -> str:
    """Every thermal input of a LayerStack: the substrate layers, then the die-attach and die layers (geometry/stack.py
    keeps these two outside ``layers``; T0305 finding 0), each by name, material (its k(T) law, stack.K_LAWS), thickness
    and k at 300 K.  sigma (electrical) and the ``kind`` label are not thermal inputs and are left out."""
    las = [*stack.layers, stack.die_attach, stack.die]
    return json.dumps([[str(la.name), str(la.material), float(la.thickness), float(la.k)] for la in las])


def _stack_type(stack) -> str:
    """F6(e) stack type: DEFAULT_STACK iff the signature equals C004's default Al2O3 DBC stack (default_dbc_stack()),
    else 'other:' + the first 12 hex digits of the signature's sha256 (one spot check per distinct type)."""
    from moduleforge.geometry import default_dbc_stack
    sig = _stack_signature(stack)
    return DEFAULT_STACK if sig == _stack_signature(default_dbc_stack()) else "other:" + hashlib.sha256(
        sig.encode()).hexdigest()[:12]


def dev_reference(name: str, cfg: dict) -> RefCtx:
    """Development geometry only (F3): 2D_Case_4 (O006 pilot geometry) or a generator-housing layout from the dev seed."""
    from moduleforge.drc.rules import measure_rules
    from moduleforge.generate import derivative as D
    if name == "case4":
        import importlib.util
        sp = importlib.util.spec_from_file_location("o006_case4_layout_e008", ROOT / "research/scripts/o006_case4_layout.py")
        c4 = importlib.util.module_from_spec(sp)
        sys.modules[sp.name] = c4
        sp.loader.exec_module(c4)
        lay = c4.build("base")
        a = cfg["dev"]["case4"]
        sub = a.get("thermal_material_substitutions", {})
        if sub:  # dev only: the PowerSynth stack's 1 um placeholder solder has no k(T) law (stack.K_LAWS)
            st = lay.stack
            lay = dataclasses.replace(lay, stack=dataclasses.replace(st, layers=tuple(
                dataclasses.replace(la, material=sub.get(la.material, la.material)) for la in st.layers)))
        rules, rec = measure_rules(lay)
        from moduleforge.drc.rules import DesignRules
        dflt = DesignRules()
        ov = {k: (getattr(dflt, k) if v == "default" else v) for k, v in a.get("rule_overrides", {}).items()}
        rules = dataclasses.replace(rules, max_gate_wire_length=a["max_signal_wire_m"],
                                    max_kelvin_wire_length=a["max_signal_wire_m"], **ov)
        rel = lambda r: tuple(v * 1e-3 for v in (r[0] - 2, r[1] - 3, r[2] - 2, r[3] - 3))  # noqa: E731
        spec = D.spec_from_layout(lay, rules, a["keepout_nets"], extra_pads={k: rel(v) for k, v in a["extra_pads_mm"].items()})
        rc = RefCtx("2D_Case_4", "dev", spec, lay, info={"measured_rules": rec})
    else:
        m = re.fullmatch(r"gen(\d)_(\d+)", name)
        spec = D.halfbridge_housing_spec(int(m[1]))
        lay = D.generate(spec, int(m[2]) + 1, int(cfg["dev"]["dev_seed"]))[int(m[2])]
        rc = RefCtx(f"housing70x40_{name}", "dev", spec, lay, info={"measured_rules": measure_rules(lay)[1]})
    bp = rc.reference.baseplate_outline.bounds
    rc.area_m2 = (bp[2] - bp[0]) * (bp[3] - bp[1])
    rc.stack_type = _stack_type(rc.spec.stack)
    return rc


def prepare(rc: RefCtx, cfg: dict, n_quick: int, quick_seed: int, with_l1: bool = True) -> RefCtx:
    """Fail fast, before any l2_layout solve (L0/L1 only): twin W and degraded copy D (DegradeError / TwinError stop the
    reference and are recorded), _quick_ok false rejections on a fixed sealed sample, rule strictness, the midpoint record
    and the twin-copper symmetric difference.  Reported, not gated, except that W and D must exist."""
    from moduleforge.drc.rules import check
    from moduleforge.generate import derivative as D
    from moduleforge.generate import twin as W
    t0 = time.perf_counter()
    try:
        rc.twin, p, rc.twin_rec = W.twin(rc.reference, rc.spec, with_l1=with_l1)
    except W.TwinError as e:
        rc.info["fail_fast"] = f"TwinError: {e}"
        return rc
    rc.info["twin_s"] = time.perf_counter() - t0
    seq = p.sequence()
    mid = []
    for i in range(3):
        a, b = p.slots[i], p.slots[i + 1]
        # the documented condition (twin.py _best_split): a merged band of one net with equal u-extents is rectangular,
        # its copper does not fix the boundary and the midpoint-of-needs rule decides (T0297 note 2)
        if seq[i][0] == seq[i + 1][0] and abs(b[1] - a[3]) < 1e-9 and abs(a[0] - b[0]) < 1e-9 and abs(a[2] - b[2]) < 1e-9:
            mid.append({"slots": [i, i + 1], "net": seq[i][0], "boundary_v_mm": a[3]})
    rc.info["midpoint_decided_splits"] = mid
    sd, area = rc.twin_rec.get("symdiff_area_mm2", {}), rc.twin_rec.get("copper_area_mm2", {})
    rc.info["twin_copper"] = {"mode": rc.twin_rec.get("mode"), "per_net": {
        n: {"symdiff_mm2": sd[n], "fraction": sd[n] / area[n]["reference"] if area[n]["reference"] else math.inf} for n in sd}}
    t0 = time.perf_counter()
    try:
        rc.D, rc.d_rec = W.degrade(rc.twin, rc.spec, with_l1=with_l1)
    except W.DegradeError as e:
        rc.info["fail_fast"] = f"DegradeError: {e}"
        rc.d_rec = getattr(e, "record", {})
    rc.info["degrade_s"] = time.perf_counter() - t0
    rc.info["walk"] = (rc.d_rec or {}).get("walk")
    rng = np.random.default_rng(quick_seed)
    cx = D._Ctx(rc.spec)
    n_clean = n_rej = 0
    for _ in range(n_quick):
        pp = D._sample(rc.spec, cx, rng)
        if pp is None:
            continue
        try:
            lay = D.build(rc.spec, pp)
        except ValueError:
            continue
        if not check(lay, rc.spec.rules):
            n_clean += 1
            n_rej += not D._quick_ok(rc.spec, cx, lay)
    # exact one-sided 95 % upper bound on the false-rejection rate (Clopper and Pearson, Biometrika 26 (1934) 404); 1.0
    # when no DRC-clean sample was drawn, i.e. the sample says nothing (T0262 attempt 5: 0 of 100 draws on 2D_Case_4)
    from scipy.stats import beta
    ub = 1.0 if n_clean == 0 or n_rej == n_clean else float(beta.ppf(0.95, n_rej + 1, n_clean - n_rej))
    rc.info["quick_ok"] = {"draws": n_quick, "drc_clean": n_clean, "rejected_clean": n_rej, "flag": n_rej > 0,
                           "rejection_rate_ub95": ub}
    rc.info["rule_strictness"] = rule_strictness(rc.info.get("measured_rules") or {})
    return rc


DC_LINK_GAPS = ("gap_dcp_phase", "gap_phase_dcm", "gap_dcp_dcm")  # the power-net gaps of the commutation loop


def _num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def rule_strictness(mr: dict) -> dict:
    """T0280 report (reported, not gated) from the record of drc.rules.measure_rules, whose spacing keys are 'gap_*'
    (gap_dcp_phase, gap_phase_dcm, gap_dcp_dcm, gap_signal_*, gap_other_min; m; T0305 finding 1): every measured class
    beside the reference's smallest DC-link gap (min of DC_LINK_GAPS); flag_2x when the class is more than twice that gap
    (a reference feature that, used as a rule, narrows the search).  Raises if the record holds a measured gap or
    spacing value and the report would be empty, so a renamed key cannot silently empty it again."""
    gaps = {k: float(v) for k, v in mr.items() if k.startswith("gap_") and _num(v)}
    link = min([v for k, v in gaps.items() if k in DC_LINK_GAPS] or [math.nan])
    rep = {k: {"value_m": v, "smallest_dc_link_gap_m": link, "flag_2x": bool(math.isfinite(link) and v > 2 * link)}
           for k, v in gaps.items()}
    if not rep and any(re.search(r"gap|spacing|clearance", k) and _num(v) for k, v in mr.items()):
        raise RuntimeError(f"rule_strictness is empty although measure_rules measured {sorted(mr)}")
    return rep


def save_ctx(rc: RefCtx, wd: Path) -> str:
    wd.mkdir(parents=True, exist_ok=True)
    p = wd / "ctx.pkl"
    with open(p, "wb") as f:
        pickle.dump({"spec": rc.spec, "reference": rc.reference, "twin": rc.twin, "D": rc.D, "snap025": rc.snap025}, f)
    return str(p)


# ------------------------------------------------------------------------------------------------ driver replay
class Stub:
    """A candidate of a recorded chunk: the driver only calls fingerprint(); the family rebuilds it in a child."""
    __slots__ = ("fp", "family")

    def __init__(self, fp, family):
        self.fp, self.family = fp, family

    def fingerprint(self):
        return self.fp


class Driver:
    """One frozen-driver search (``main``: run_search; ``control``: run_control) of one reference, replayed until done."""

    def __init__(self, rc: RefCtx, ns: str, seed: int, root: Path, ctx_path: str, scfg: dict, run: "Run"):
        self.rc, self.ns, self.seed, self.wd, self.ctx, self.scfg, self.run = rc, ns, seed, root / ns, ctx_path, scfg, run
        self.wd.mkdir(parents=True, exist_ok=True)
        self.result = None
        self.chunks: dict | None = None
        self.asc: list | None = None

    # -- identities
    def which(self, lay) -> str:
        fp = lay.fingerprint()
        for w in ("reference", "twin", "D", "snap025"):  # snap025: layout_of must load it from ctx, not rebuild a family
            o = getattr(self.rc, w)
            if o is not None and o.fingerprint() == fp:
                return w
        return "candidate"

    def job(self, lay, typ: str, **kw) -> dict:
        fp = lay.fingerprint()
        w = self.which(lay)
        tag = kw.get("level", "")
        # every physics input of the solve is in the file name, so a changed rule, power or level never reuses a result
        phys = hashlib.sha256(json.dumps({k: v for k, v in kw.items() if k != "priority"}, sort_keys=True,
                                         default=str).encode()).hexdigest()[:10]
        out = self.run.root / self.rc.rid / "solves" / f"{fp[:24]}__{typ}{tag}__{phys}.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        j = {"type": typ, "ctx": self.ctx, "which": w, "fp": fp, "family": getattr(lay, "family", None),
             "out": str(out), "threads": self.run.threads, "ref": self.rc.rid} | kw
        j["mem_GB"], j["est_s"] = self.run.estimate(self.rc, j, lay)
        return j

    def em_jobs(self, lay, levels) -> list[dict]:
        return [self.job(lay, "em", level=self.run.em_level(lv), freq_hz=self.run.cfg["em"]["freq_hz"], priority=1)
                for lv in levels]

    def th_jobs(self, lay) -> list[dict]:
        if self.run.P.get(self.rc.rid) is None:
            return [self.run.calib_job(self.rc)]
        return [self.job(lay, "thermal", level=lv, power_W=self.run.P[self.rc.rid], fem_rule=self.run.fem_rule,
                         h=self.run.op["h_W_m2K"], T_c=self.run.op["coolant_K"], priority=2) for lv in (0, 1, 2)]

    # -- injected solvers (read result files; missing -> Pending)
    def _get(self, jobs: list[dict]) -> list[dict]:
        recs = [Scheduler.done(j) for j in jobs]
        miss = [j for j, r in zip(jobs, recs, strict=True) if r is None]
        if miss:
            raise Pending(miss)
        return recs

    def l1(self, lay):
        if type(lay) is Stub:
            raise RuntimeError("an L1 of a screened candidate is missing from the checkpoint")
        return self.run.l1(lay)

    def l_sub(self, lay):
        return self._get(self.em_jobs(lay, ["lat0.25"]))[0]["L_H"]

    def band(self, lay):
        try:
            return [r["L_H"] for r in self._get(self.em_jobs(lay, BAND))]
        except Pending as p:
            raise Pending(p.jobs + self.near_tie_hint(lay)) from None

    def thermal(self, lay, P):
        jobs = self.th_jobs(lay)
        if jobs[0]["type"] == "calibrate":
            raise Pending(jobs)
        try:
            recs = self._get(jobs)
        except Pending as p:
            raise Pending(p.jobs + self.batch_hint(lay)) from None
        return {"tj": [r["tj"] for r in recs], "tj_max_node": [r["tj_node"] for r in recs], "nodes": [r["nodes"] for r in recs],
                "fingerprint": lay.fingerprint(), "energy_balance": [r["energy_balance"] for r in recs],
                "picard": [{"iters": r["picard_iters"], "residual_K": r["picard_residual_K"]} for r in recs]}

    # -- stream and stage mirror (prefetch hints only; the driver decides)
    def screen_job(self) -> dict:
        out = self.wd / "screen.json"
        sc = self.scfg
        return {"type": "screen", "ns": self.ns, "ctx": self.ctx, "wd": str(self.wd), "seed": self.seed, "search": sc,
                "out": str(out), "threads": 1, "mem_GB": self.run.cm["screen_mem_GB"], "priority": 3,
                "est_s": self.run.screen_s(self.rc) * sc["n_candidates"], "ref": self.rc.rid}

    def load_stream(self) -> bool:
        if self.chunks is None and Scheduler.done(self.screen_job()) is not None:
            with gzip.open(self.wd / "stream.json.gz", "rt") as f:
                self.chunks = json.load(f)
        return self.chunks is not None

    def generate(self, spec, m, sk):
        return [Stub(fp, fam) for fp, fam in self.chunks[f"{m}:{sk}"]]

    def _l1_store(self) -> dict:
        out = {}
        p = self.wd / "checkpoint.jsonl"
        for line in p.read_text().splitlines() if p.exists() else []:
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if rec["k"].endswith(":l1"):
                out[rec["k"].split(":")[1]] = rec["v"]
        return out

    def shortlist(self) -> list:
        """The driver's step 2 rule (lowest L1, ties by index, de-duplicated by fingerprint), for prefetch only."""
        l1 = self._l1_store()
        keep, idx = [], 0
        for key in self._chunk_keys():
            for fp, fam in self.chunks[key]:
                v = l1[fp]
                if all(t[2].fp != fp for t in keep):
                    keep.append((v, idx, Stub(fp, fam)))
                    keep.sort(key=lambda t: (t[0], t[1]))
                    del keep[self.scfg["shortlist"]:]
                idx += 1
        return [(i, s, v) for v, i, s in keep]

    def _chunk_keys(self) -> list[str]:
        n, c, k, out = self.scfg["n_candidates"], self.scfg["chunk"], 0, []
        done = 0
        while done < n:
            m = min(c, n - done)
            out.append(f"{m}:{int(np.random.SeedSequence([self.seed, k]).generate_state(1)[0])}")
            done += m
            k += 1
        return out

    def batch_hint(self, lay) -> list[dict]:
        if not self.asc or self.run.P.get(self.rc.rid) is None:
            return []
        fps = [s.fp for _, s, _ in self.asc]
        if lay.fingerprint() not in fps:
            return []
        b0 = fps.index(lay.fingerprint()) // self.scfg["batch"] * self.scfg["batch"]
        return [j for _, s, _ in self.asc[b0:b0 + self.scfg["batch"]] for j in self.th_jobs(s)]

    def near_tie_hint(self, lay) -> list[dict]:
        """All near ties at once (the driver's union window), once the bands it depends on exist."""
        if self.ns != "main" or not self.asc:
            return []
        try:
            ind = self.band(self.asc[0][1]) if lay.fingerprint() != self.asc[0][1].fp else None
            if ind is None:
                return []
            tw, ref = self.band(self.rc.twin), self.band(self.rc.reference)
        except Pending:
            return []
        s_ref = self.run.s_ref.get(self.rc.rid, 0.0)
        w = max(2 * MX.ratio_band_estimate(ind, tw), 2 * MX.ratio_band_estimate(ind, ref)) + s_ref
        lsub = {s.fp: self.l_sub(s) for _, s, _ in self.asc}
        return [j for _, s, _ in self.asc[1:] if lsub[s.fp] <= (1 + w) * lsub[self.asc[0][1].fp]
                for j in self.em_jobs(s, BAND)]

    def prefetch(self) -> list[dict]:
        rc, jobs = self.rc, []
        if self.ns == "main":
            jobs += self.em_jobs(rc.reference, BAND) + self.em_jobs(rc.twin, BAND)
            if rc.snap025 is not None:
                jobs += self.em_jobs(rc.snap025, ["lat0.25"])
            jobs += self.th_jobs(rc.reference) + self.th_jobs(rc.twin)
            jobs += self.run.spot_jobs(self)
        else:
            jobs += self.em_jobs(rc.D, BAND)
        if not self.load_stream():
            return jobs + [self.screen_job()]
        sl = self.shortlist()
        jobs += [j for _, s, _ in sl for j in self.em_jobs(s, ["lat0.25"])]
        if all(Scheduler.done(j) for _, s, _ in sl for j in self.em_jobs(s, ["lat0.25"])):
            ls = {s.fp: self.l_sub(s) for _, s, _ in sl}
            self.asc = sorted(sl, key=lambda t: (ls[t[1].fp], t[0]))
            jobs += self.em_jobs(self.asc[0][1], BAND)
            if self.ns == "main" and self.run.P.get(rc.rid) is not None:
                jobs += [j for _, s, _ in self.asc[:self.scfg["batch"]] for j in self.th_jobs(s)]
        return jobs

    def replay(self) -> bool:
        """One replay of the frozen driver; True when it completed."""
        from moduleforge.optimize import search as S
        if self.result is not None:
            return True
        if not self.load_stream():
            raise Pending([self.screen_job()])
        sv = S.Solvers(l1=self.l1, l_sub=self.l_sub, band=self.band, thermal=self.thermal)
        cfg = S.SearchConfig(**self.scfg)
        s_ref = self.run.s_ref.get(self.rc.rid, 0.0)
        if self.ns == "main":
            self.result = S.run_search(self.rc.spec, self.rc.reference, self.rc.twin, self.seed, sv,
                                       self.run.P.get(self.rc.rid), s_ref, self.wd, cfg, self.generate)
        else:
            self.result = S.run_control(self.rc.spec, self.rc.D, self.seed, sv, s_ref, self.wd, cfg, self.generate)
        return True


class Run:
    """Holds the configuration, the scheduler, the per-reference operating points and the drivers."""

    def __init__(self, cfg: dict, root: Path, sched: Scheduler, smoke: bool, threads: int, fake: dict | None = None):
        self.cfg, self.root, self.sched, self.smoke, self.threads, self.fake = cfg, root, sched, smoke, threads, fake
        self.cm = cfg["compute"]["cost_model"]
        self.op = cfg["operating_point"]
        self.fem_rule = dict(cfg["fem_rule"])
        if smoke:
            sm = cfg["dev"]["smoke"]["fem_overrides"]
            self.fem_rule.update(sm)
        self.P: dict[str, float] = {}
        self.cal: dict[str, dict] = {}
        self.s_ref: dict[str, float] = {}  # per reference, set by s_ref_of before the main driver's first replay
        self.spot_refs: dict[str, str] = {}  # F6(e): non-default stack type -> the reference carrying its spot check
        self.l1_cache: dict[str, float] = {}
        self.size_cache: dict[tuple, int] = {}

    def em_level(self, lv: str) -> str:
        return self.cfg["dev"]["smoke"]["em_map"].get(lv, lv) if self.smoke else lv

    def l1(self, lay) -> float:
        fp = lay.fingerprint()
        if fp not in self.l1_cache:
            self.l1_cache[fp] = self.fake["l1"](lay) if self.fake else l1_of(lay)
        return self.l1_cache[fp]

    def screen_s(self, rc: RefCtx) -> float:
        return float(self.cm["screen_s_per_candidate"].get(rc.rid, self.cm["screen_s_per_candidate"]["default"]))

    def _real(self, rc: RefCtx, lay):
        if type(lay) is Stub:
            from moduleforge.generate import derivative as D
            return D.build(rc.spec, D.params_of(SimpleNamespace(family=lay.family)))
        return lay

    def size(self, rc: RefCtx, lay, kind: str, level: int) -> int:
        """Grid size of one thermal solve from the layout's own grid (thermal_fem.estimate_dofs; FV: level-1 cell count
        x 8 per level), never from the outline area: generator candidates carry 1.8x the Case 4 reconstruction's DOFs
        (research/o003/e008_dev/probe_dofs.json).  Fake layouts (selftest) use the area model."""
        fr = self.fem_rule
        key = (lay.fingerprint(), kind, level, json.dumps(fr, sort_keys=True))
        if key not in self.size_cache:
            if self.fake is not None or rc.spec is None:
                per = self.cm["fake_sizes_per_m2"][kind]
                v = int(per[str(level)] * rc.area_m2)
            elif kind == "fem":
                v = int(FEM().estimate_dofs(self._real(rc, lay), rule_from(fr), level))
            else:
                from moduleforge.solvers import thermal_layout as TL
                v = int(np.prod(TL.build_layout_grid(self._real(rc, lay), 1).shape)) * 8 ** (level - 1)
            self.size_cache[key] = v
        return self.size_cache[key]

    def estimate(self, rc: RefCtx, j: dict, lay=None) -> tuple[float, float]:
        """(peak GB, wall s) of one job: the --plan cost model on the job's own unknown / DOF / cell count."""
        if j["type"] == "em":
            n = em_unknowns(rc.area_m2, EM_LEVELS[j["level"]][0], j["level"], self.cm)
            t, m = em_cost(n, j["level"], self.cm)
            mg = self.cm["em_mem_margin_local"]
            prior = self.cm.get("em_level_mem_prior", {}).get(j["level"], 1.0)  # until a solve of this level is measured
            j["mem_model_GB"] = m
            return m * max(prior, mg.get(rc.rid, mg["default"]) if self.smoke else 1.0), t
        if j["type"] in ("thermal", "calibrate"):
            dofs = self.size(rc, lay, "fem", int(j.get("level", 0)))
            t, m = fem_cost(dofs, self.cm)
            j["mem_model_GB"] = m
            return m, t * (self.cm["calibration_solves"] if j["type"] == "calibrate" else 1)
        if j["type"] == "fv":
            cells = self.size(rc, lay, "fv", int(j["level"]))
            return fv_cost(cells, self.cm)[::-1]
        return 1.0, 60.0

    def calib_job(self, rc: RefCtx) -> dict:
        d = self.drivers[(rc.rid, "main")]
        return d.job(rc.reference, "calibrate", fem_rule=self.fem_rule, h=self.op["h_W_m2K"], T_c=self.op["coolant_K"],
                     target_K=self.op["target_rise_K"], tol_K=self.op["calibration_tol_K"],
                     max_iters=self.op["calibration_max_iters"], power_start_W=self.op["power_start_W"], priority=4)

    def spot_jobs(self, d: Driver) -> list[dict]:
        """F6(e): on one reference of each non-default stack type (self.spot_refs), FV L2 levels 1-3 at P_ref (scikit-fem
        levels 0-2 of the reconstruction are the main thermal solves)."""
        rc = d.rc
        if rc.rid not in self.spot_refs.values() or self.P.get(rc.rid) is None:
            return []
        return [d.job(rc.reference, "fv", level=lv, power_W=self.P[rc.rid], h=self.op["h_W_m2K"], T_c=self.op["coolant_K"],
                      priority=2) for lv in self.cfg["gates"]["fv_levels"]]

    def s_ref_of(self, d: Driver) -> float:
        """s_ref of O003 A1 for the driver (mfos.metrics.snapping_bias, the function the metric applies to the reference
        row): 0 on the 0.5 mm grid; else from L(snapped to 0.25 mm) and L(reconstruction = snapped to 0.5 mm), both at
        0.25 mm cells (the rows' L_snap025_H and L_snap05_H), and the pre-registration snapping check in rc.info.  It is
        fixed before the main driver's first replay, so its near-tie window and w values use the same s_ref as the
        metric; Pending until both solves exist."""
        rc = d.rc
        if rc.on_grid:
            return 0.0
        jobs = d.em_jobs(rc.snap025, ["lat0.25"]) + d.em_jobs(rc.reference, ["lat0.25"])
        l025, l05 = (r["L_H"] for r in d._get(jobs))
        return MX.snapping_bias(False, l025, l05, rc.info.get("snapchk0125_H"), rc.info.get("snapchk05_H"))

    def drive(self, refs: list[RefCtx], seeds: dict, scfg: dict) -> None:
        self.drivers: dict[tuple, Driver] = {}
        for rc in refs:
            if not rc.on_grid and rc.snap025 is None:
                raise RuntimeError(f"{rc.rid}: off the 0.5 mm grid but no snap025 layout (s_ref needs it)")
            ctx = save_ctx(rc, self.root / rc.rid)
            for ns in ("main", "control"):
                self.drivers[(rc.rid, ns)] = Driver(rc, ns, seeds[(rc.rid, ns)], self.root / rc.rid, ctx, scfg, self)
        # F6(e): one spot-check reference per non-default stack type, the first of that type in reference order (T0305
        # finding 0: a single spot_ref was overwritten, so only the last type was checked)
        self.spot_refs = {st: next(rc.rid for rc in refs if rc.stack_type == st)
                          for st in sorted({rc.stack_type for rc in refs} - {DEFAULT_STACK})}
        while True:
            for (rid, _ns), d in self.drivers.items():
                if rid not in self.P:
                    rec = Scheduler.done(self.calib_job(d.rc)) if d.ns == "main" else None
                    if rec is not None:
                        self.P[rid], self.cal[rid] = rec["P_ref_W"], rec
            pend = 0
            for d in self.drivers.values():
                self.sched.submit(d.prefetch())
                try:
                    if d.ns == "main" and d.rc.rid not in self.s_ref:
                        self.s_ref[d.rc.rid] = self.s_ref_of(d)
                    d.replay()
                except Pending as p:
                    self.sched.submit(p.jobs)
                    pend += 1
            # the spot-check solves are not asked for by any driver: the loop also waits for them (evaluate reads them)
            spot = [j for rid in self.spot_refs.values() for j in self.spot_jobs(self.drivers[(rid, "main")])]
            self.sched.submit(spot)
            if not pend and all(Scheduler.done(j) for j in spot):
                break
            if not self.sched.queue and not self.sched.running:
                raise RuntimeError("drivers pending but no job queued")
            self.sched.step()


# ------------------------------------------------------------------------------------------------ rows
def _null(rid_twin: dict, rid: str) -> float:
    return rid_twin.get(rid, 1e-8)


def assemble_rows(run: Run, refs: list[RefCtx], smoke: bool) -> tuple[list[dict], dict]:
    """Rows per research/o003/e008_row_contract.md (kinds reference / layout / die), plus per-reference extras.  F5: ids,
    fingerprints (sha256), inductance, power, temperature and scalar rule values only; no geometry."""
    rows, extra = [], {}
    for rc in refs:
        rid = rc.rid
        if not rc.admissible:
            rows.append({"kind": "reference", "reference_id": rid, "admissible": False, "L_sub_null_H": 1e-8})
            continue
        dm, dc = run.drivers[(rid, "main")], run.drivers[(rid, "control")]
        rm, rcn = dm.result, dc.result
        fpw, fpr, fpd = rc.twin.fingerprint(), rc.reference.fingerprint(), rc.D.fingerprint()
        bands = {}
        for r in rm.rows["band"] + rcn.rows["band"]:
            bands[r["fingerprint"]] = r["band"]
        L_tw = bands[fpw][0]
        lid = {fpw: "twin", fpr: "reconstruction", fpd: "D"}
        cand = {}
        for c in rm.rows["candidates"]:
            lid[c["fingerprint"]] = f"c{c['index']:06d}"
            cand[c["fingerprint"]] = c
        ctrl_best = rcn.inductance_best
        ctrl_c = {c["fingerprint"]: c for c in rcn.rows["candidates"]}

        def lrow(fp, role, lsub, lab=None, rid=rid, lid=lid, bands=bands, L_tw=L_tw):
            r = {"kind": "layout", "reference_id": rid, "layout_id": lab or lid[fp], "role": role, "fingerprint": fp,
                 "L_sub_H": float(lsub), "smoke": smoke}
            if fp in bands:
                r.update({c: float(v) for c, v in zip(BAND_COLS[1:], bands[fp][1:], strict=True)})
            r["L_sub_null_H"] = L_tw if role == "candidate" else float(lsub)
            return r
        rows.append(lrow(fpw, "twin", L_tw))
        rows.append(lrow(fpr, "reconstruction", bands[fpr][0]))
        for fp, c in cand.items():
            r = lrow(fp, "candidate", c["l_sub"])
            r.update(l1_H=c["l1"], l1_rank=c["l1_rank"], gen_index=c["index"])
            rows.append(r)
        rows.append(lrow(fpd, "degraded", bands[fpd][0]))
        rows.append(lrow(ctrl_best, "control_best", ctrl_c[ctrl_best]["l_sub"], f"ctrl_c{ctrl_c[ctrl_best]['index']:06d}"))
        for t in rm.rows["thermal"]:
            fp, rec = t["fingerprint"], t["record"]
            for i in range(len(rec["tj"][0])):
                rows.append({"kind": "die", "reference_id": rid, "layout_id": lid[fp], "die_id": f"d{i}", "fingerprint": fp,
                             "role": t["role"], "Tj_l0_K": rec["tj"][0][i], "Tj_l1_K": rec["tj"][1][i],
                             "Tj_l2_K": rec["tj"][2][i], "GCI_K": rec["gci"][i],
                             "tj_node_l0": rec["tj_max_node"][0][i], "tj_node_l1": rec["tj_max_node"][1][i],
                             "tj_node_l2": rec["tj_max_node"][2][i], "nodes": rec["nodes"],
                             "energy_balance_max": max(rec["energy_balance"]),
                             "picard_residual_max_K": max(p["residual_K"] for p in rec["picard"]),
                             "power_W": run.P[rid], "L_sub_null_H": L_tw, "smoke": smoke})
        lev = rm.levelling
        ref = {"kind": "reference", "reference_id": rid, "admissible": True, "L_term_H": rc.L_term_H, "on_grid": rc.on_grid,
               "L1_min_first5000_H": lev["l1_min_first"], "L1_min_all_H": lev["l1_min_all"], "L_sub_null_H": L_tw,
               "stack_type": rc.stack_type, "P_ref_W": run.P[rid], "reference_kind": rc.kind, "smoke": smoke}
        if not rc.on_grid:
            ref.update(L_snap025_H=Scheduler.done(dm.em_jobs(rc.snap025, ["lat0.25"])[0])["L_H"], L_snap05_H=bands[fpr][0],
                       L_snapchk0125_H=rc.info.get("snapchk0125_H"), L_snapchk05_H=rc.info.get("snapchk05_H"))
        rows.append(ref)
        extra[rid] = {"main": rm, "control": rcn, "bands": bands, "L_twin": L_tw}
    return rows, extra


HR = ("headroom_min_lo", "headroom_max_hi_ind")


def metric_entries(cfg: dict) -> list[dict]:
    mp = cfg["metric_params"]
    out = []
    for fn in HR:
        out.append({"metric": fn, "fn": fn, "params": dict(mp)})
        for tag, lt in (("Lterm0", 0.0), ("Lterm17p5", 1.75e-8)):
            out.append({"metric": f"{fn}_{tag}", "fn": fn, "params": dict(mp, L_term_H=lt)})
        out.append({"metric": f"{fn}_recon", "fn": fn, "params": dict(mp, comparator="reconstruction")})
    return out


def evaluate(run: Run, refs: list[RefCtx], rows: list[dict], extra: dict, cfg: dict) -> tuple[dict, list[dict], dict]:
    """Metrics (mfos.metrics, cross-checked against research/o003/headroom_metrics.py), gated sanity checks, report."""
    sys.path.insert(0, str(ROOT / "research" / "o003"))
    import headroom_metrics as HM
    g = cfg["gates"]
    checks: list[dict] = []

    def ck(name, ok, value=None, threshold=None, detail=""):
        checks.append({"name": name, "passed": bool(ok), "value": value, "threshold": threshold, "detail": str(detail)})
    mp = cfg["metric_params"]
    per = MX.headroom_per_reference(rows, "L_sub_H", dict(mp))
    met, agree = {}, []
    for e in metric_entries(cfg):
        try:
            v = MX.compute(e["fn"], rows, pred="L_sub_H", params=e["params"])
            v2 = HM.compute(e["fn"], rows, pred="L_sub_H", params=e["params"])
            agree.append(v == v2 or abs(v - v2) <= 1e-9 * max(abs(v), 1e-30))
        except ValueError as ex:
            v = math.nan
            met[f"{e['metric']}_error"] = str(ex)
        met[e["metric"]] = v
    ck("recompute_agrees", all(agree), detail="mfos.metrics vs research/o003/headroom_metrics.py, rel 1e-9")
    try:
        nul = MX.compute("headroom_min_lo", rows, pred="L_sub_null_H", params=dict(mp))
    except ValueError:
        nul = math.nan
    met["null_twin_as_best_h_lo"] = nul
    rep: dict[str, dict] = {}
    counted = 0
    for rc in refs:
        rid = rc.rid
        if not rc.admissible:
            continue
        rec, ex = per[rid], extra[rid]
        rm, rcn, bands = ex["main"], ex["control"], ex["bands"]
        counted += bool(rec["counted"])
        fpw, fpd = rc.twin.fingerprint(), rc.D.fingerprint()
        # F1(b) definition of D, conservative end of its band, before K1 is read
        R_D = bands[fpd][0] / bands[fpw][0]
        e_D = MX.ratio_band_estimate(bands[fpd], bands[fpw])
        ck(f"F1b_D_definition:{rid}", R_D * (1 - 2 * e_D) >= g["degrade_ratio"], R_D * (1 - 2 * e_D), g["degrade_ratio"],
           f"R_D={R_D:.5f} e_R(D,W)={e_D:.5f} walk={json.dumps(rc.info.get('walk'), default=str)[:300]}")
        L_D, L_cb = bands[fpd][0], bands[rcn.inductance_best][0]
        h_plant, h_ctrl = 1 - bands[fpw][0] / L_D, 1 - L_cb / L_D
        ck(f"F1b_control:{rid}", h_ctrl >= h_plant - rcn.w_ctrl, h_ctrl, h_plant - rcn.w_ctrl,
           f"h_plant={h_plant:.5f} h_ctrl={h_ctrl:.5f} w_ctrl={rcn.w_ctrl:.5f}")
        # reported L1-only null (F1, not gated): its first passing candidate in L1 order, judged like A1 against W
        a_ = bands[fpw][0] / (bands[fpw][0] + rc.L_term_H)
        # s_ref: the metric's own (snapping_bias of this reference row), never an assigned 0 (T0304 finding 3); the
        # driver's s_ref (its near-tie window and w) must be the same number, else its band solves miss metric inputs
        s_ref = rec["s_ref"]
        ck(f"driver_s_ref_matches_rows:{rid}", run.s_ref.get(rid) == s_ref, run.s_ref.get(rid), s_ref,
           f"on_grid={rc.on_grid}")
        cl = {c["fingerprint"]: c["l_sub"] for c in rm.rows["candidates"]}
        nb = rm.null_best
        if nb is None or bands[fpw][0] <= cl[nb]:
            h_null, w_src = -a_ * s_ref, "twin rule"
        else:
            own = nb in bands
            w_n = (2 * MX.ratio_band_estimate(bands[nb], bands[fpw]) + s_ref) if own else rm.w_a1
            w_src = "own band" if own else "A1 best's w (F3 runs no band solve on the null's candidate)"
            h_null = a_ * (1 - cl[nb] / bands[fpw][0] * (1 + (w_n if w_n is not None else math.nan)))
        if rec["counted"]:
            met["l1_only_null_h_lo"] = min(met.get("l1_only_null_h_lo", math.inf), h_null)
        ws = {"w_ind": rm.w_ind, "w_a1": rm.w_a1}
        ck(f"F1c_band_width:{rid}", all(v is None or v <= g["w_max"] for v in ws.values()),
           max([v for v in ws.values() if v is not None]), g["w_max"], json.dumps(ws))
        # F6(a), (c): every thermal record of this reference
        bad_a, bad_c, worst_eb, worst_pc = [], [], 0.0, 0.0
        for t in rm.rows["thermal"]:
            r = t["record"]
            if r["fingerprint"] != t["fingerprint"]:
                bad_a.append(f"{t['fingerprint'][:8]} fingerprint")
            n = r["nodes"]
            for a, b in zip(n[:-1], n[1:], strict=True):
                if abs(b / a / g["node_growth_factor"] - 1) > g["node_growth_tol"]:
                    bad_a.append(f"{t['fingerprint'][:8]} growth {b / a:.3f}")
            for i, gc in enumerate(r["gci"]):
                if MX.gci_capped(r["tj"][0][i], r["tj"][1][i], r["tj"][2][i], floor=mp["floor"]) != gc:
                    bad_a.append(f"{t['fingerprint'][:8]} gci die {i}")
            worst_eb = max(worst_eb, max(r["energy_balance"]))
            worst_pc = max(worst_pc, max(p["residual_K"] for p in r["picard"]))
        for h in run.cal[rid]["history"]:
            worst_eb, worst_pc = max(worst_eb, h["energy_balance"]), max(worst_pc, h["picard_residual_K"])
        # F6(c) "on every thermal solve": the F6(e) finite-volume spot-check solves of this reference too (T0305
        # finding 5); thermal_layout reports no Picard residual, so they enter the energy balance only
        fv_eb = [Scheduler.done(j)["energy_balance"] for j in run.spot_jobs(run.drivers[(rid, "main")])]
        worst_eb = max([worst_eb, *fv_eb])
        if worst_eb > g["energy_tol"] or worst_pc > g["picard_tol_K"]:
            bad_c.append(f"eb {worst_eb:.2e} picard {worst_pc:.2e}")
        ck(f"F6a_own_three_grids:{rid}", not bad_a, len(bad_a), 0, bad_a[:10])
        ck(f"F6c_energy_balance:{rid}", worst_eb <= g["energy_tol"], worst_eb, g["energy_tol"],
           f"{len(fv_eb)} finite-volume spot-check solves included")
        ck(f"F6c_picard:{rid}", worst_pc <= g["picard_tol_K"], worst_pc, g["picard_tol_K"])
        rise = run.cal[rid]["rise_K"]
        ck(f"F6d_operating_point:{rid}", abs(rise - run.op["target_rise_K"]) <= run.op["operating_point_tol_K"], rise,
           run.op["target_rise_K"], f"P_ref={run.P[rid]:.4f} W per die")
        rep[rid] = {"record": {k: v for k, v in rec.items() if not isinstance(v, (list, dict)) or k in ("checked_ids",)},
                    "levelling": rm.levelling, "h_plant": h_plant, "h_ctrl": h_ctrl, "w_ctrl": rcn.w_ctrl, "R_D": R_D,
                    "e_R_D": e_D, "near_ties": len(rm.near_ties), "null_new_checks": rm.null_new_checks,
                    "l1_only_null_best": rm.null_best, "l1_only_null_h_lo": h_null,
                    "l1_only_null_w_source": w_src, "info": rc.info, "twin_mode": rc.twin_rec.get("mode")}
    # F6(e) stack-type spot check: one per non-default stack type, every one gated (T0305 finding 0)
    a3s: dict[str, float] = {}
    for st, rid in sorted(run.spot_refs.items()):
        if rid not in extra:  # an inadmissible reference cannot carry its type's spot check
            ck(f"F6e_stack_type_spot_check:{st}", False, detail=f"reference {rid} of this type is not admissible")
            a3s[st] = math.inf
            continue
        fv = [Scheduler.done(j) for j in run.spot_jobs(run.drivers[(rid, "main")])]
        th = next(t["record"] for t in extra[rid]["main"].rows["thermal"] if t["role"] == "reference")
        a3s[st] = max(MX.max_gci_consistency(*(  # per die: fem levels 0-2 vs FV levels 1-3
            [th["tj"][lv][i]] for lv in range(3)), *([f["tj"][i]] for f in fv), floor=g["a3_floor_K"],
            ref_gci_cap=g["a3_ref_gci_cap_K"]) for i in range(len(th["tj"][0])))
        ck(f"F6e_stack_type_spot_check:{st}", a3s[st] <= g["a3_max"], a3s[st], g["a3_max"], f"reference {rid}")
    if a3s:
        ck("F6e_stack_type_spot_check", all(v <= g["a3_max"] for v in a3s.values()), max(a3s.values()), g["a3_max"],
           json.dumps({st: [run.spot_refs[st], v] for st, v in a3s.items()}, default=str))
        met["stack_type_a3"] = max(a3s.values())
        rep["F6e"] = {st: {"reference": run.spot_refs[st], "a3": v} for st, v in a3s.items()}
    else:
        ck("F6e_stack_type_spot_check", True, detail="every reference on C004's default Al2O3 DBC stack: not required")
    ck("at_least_one_counted_reference", counted >= 1, counted, 1)
    met["n_counted_references"] = float(counted)
    return met, checks, rep


def thermal_report_from_rows(rows: list[dict], g: dict, floor: float, limit: float) -> dict:
    """Dev-run thermal report (reported, not gated; T0304 findings 0 and 1, T0305 finding 4) from the die rows, per
    reference and thermally solved layout: F6(a)'s node growth for each level step against node_growth_factor +/-
    node_growth_tol; the per-die GCI (mfos.metrics.gci_capped, floor) and the count that are +inf; and whether O003's
    conservative +2 K test is attainable on that layout.  Attainable means the layout's own interval width
    max_i(T_i + GCI_i) - max_j(T_j - GCI_j) (tj_bounds upper - lower) is <= tj_limit_K: that width is the conservative
    margin of a candidate with this layout's Tj and GCIs against a twin equal to it, so above the limit even a candidate
    thermally identical to the twin fails (one +inf GCI makes it unattainable).  Layouts other than the twin also get
    their conservative margin against the twin."""
    by: dict[str, dict[str, dict]] = {}
    for r in rows:
        if r.get("kind") == "die":
            lay = by.setdefault(r["reference_id"], {}).setdefault(r["layout_id"], {"dies": {}, "nodes": r["nodes"],
                                                                                    "role": r.get("role", r["layout_id"])})
            lay["dies"][r["die_id"]] = [float(r[f"Tj_l{lv}_K"]) for lv in range(3)]
    out = {}
    lo_f, hi_f = g["node_growth_factor"] * (1 - g["node_growth_tol"]), g["node_growth_factor"] * (1 + g["node_growth_tol"])
    for rid, lays in by.items():
        dies_of = {lab: [v["dies"][k] for k in sorted(v["dies"])] for lab, v in lays.items()}
        tw = MX.tj_bounds(dies_of["twin"], floor=floor) if "twin" in lays else None
        per = {}
        for lab, v in lays.items():
            n = [int(x) for x in v["nodes"]]
            growth = [b / a for a, b in zip(n[:-1], n[1:], strict=True)]
            gci = [MX.gci_capped(*d, floor=floor) for d in dies_of[lab]]
            b = MX.tj_bounds(dies_of[lab], floor=floor)
            e = {"role": v["role"], "nodes": n, "growth": growth,
                 "growth_ok": [bool(abs(x / g["node_growth_factor"] - 1) <= g["node_growth_tol"]) for x in growth],
                 "gci_K": gci, "n_gci_inf": sum(math.isinf(x) for x in gci), "tj_max_l2_K": b[0], "tj_upper_K": b[2],
                 "tj_lower_K": b[3], "self_margin_K": b[2] - b[3], "attainable": bool(b[2] - b[3] <= limit)}
            if tw is not None and lab != "twin":
                e.update(margin_vs_twin_K=b[2] - tw[3], passes_vs_twin=bool(b[2] - tw[3] <= limit))
            per[lab] = e
        out[rid] = {"layouts": per, "summary": {
            "growth_window": [lo_f, hi_f], "n_layouts": len(per),
            "n_layouts_growth_fail": sum(not all(e["growth_ok"]) for e in per.values()),
            "n_gci": sum(len(e["gci_K"]) for e in per.values()), "n_gci_inf": sum(e["n_gci_inf"] for e in per.values()),
            "n_attainable": sum(e["attainable"] for e in per.values()), "tj_limit_K": limit, "floor_K": floor}}
    return out


# ------------------------------------------------------------------------------------------------ fake world (selftest)
def _u(s: str, k: int = 0) -> float:
    return int(hashlib.sha256(f"{s}:{k}".encode()).hexdigest()[:12], 16) / 16 ** 12


class FakeLay(Stub):
    __slots__ = ()


def fake_world(scenario: str, hot: set | None = None, fv_bad: set | None = None, fv_eb_bad: set | None = None):
    """Deterministic fake solvers keyed by fingerprint.  'twin_best': every candidate is above the twin (twin rule);
    otherwise candidates reach ~0.70 of the twin's L_sub ('levelled': L1 floor reached in the first n_first).  Planted
    faults, filled by the selftest before the drive: ``hot`` fingerprints get +10 K on die 0 at every scikit-fem level
    (fails the conservative test by > 8 K); ``fv_bad`` references get +5 K on every die at every FV level (F6(e) fails);
    ``fv_eb_bad`` references' FV solves report an energy balance of 1e-3 (F6(c) fails).  'snap*' is the off-grid
    reference snapped to 0.25 mm: L = 20.1 nH against the reconstruction's 20.0 nH, so s_ref = 2 |20.1/20 - 1| = 0.01."""
    lo = 1.05 if scenario == "twin_best" else 0.70
    fixed = {"ref": 20e-9, "twin": 20.0004e-9, "D": 27.5e-9, "snap": 20.1e-9}
    hot, fv_bad, fv_eb_bad = (set() if x is None else x for x in (hot, fv_bad, fv_eb_bad))

    def lsub(fp):
        for k, v in fixed.items():
            if fp.startswith(k):
                return v
        u = _u(fp)
        return 20.2e-9 * (lo + 0.5 * (max(u, 0.04) if scenario == "levelled" else u))

    def l1(lay):
        fp = lay.fingerprint()
        if fp[:3] in ("ref", "twi", "D") or scenario == "levelled":  # levelled: L1 floor reached in the first n_first
            return lsub(fp) * 0.92
        return lsub(fp) * (0.9 + 0.04 * _u(fp, 7))

    def job(j):
        fp = j["fp"]
        if j["type"] == "em":
            f = {"lat0.25": 1.0, "lat0.5": 1.004, "thk_c": 1.003, "thk_f": 0.9995, "fil_f": 1.0008}[j["level"]]
            k = BAND.index(j["level"])  # layout-dependent band levels, so e_R is O(1e-3) and the twin gate is testable
            return {"L_H": lsub(fp) * f * (1 + (2e-3 * _u(fp, 10 + k) if k else 0.0)), "n_unknowns": 1000,
                    "fingerprint": fp}
        if j["type"] == "calibrate":
            return {"P_ref_W": 42.0, "rise_K": 60.1, "history": [{"power_W": 42.0, "rise_K": 60.1, "energy_balance": 1e-9,
                                                                   "picard_residual_K": 1e-6}]}
        if j["type"] in ("thermal", "fv"):
            lv = j["level"]
            key = "W" if fp.startswith(("ref", "twin")) else fp  # twin gate (a2): the twin is near-identical in Tj
            base = [338.15 + 60.0 + 1.5 * _u(key, i) for i in range(4)]
            off = {0: 0.25, 1: 0.05, 2: 0.01, 3: 0.0}[lv] if j["type"] == "thermal" else {1: 0.06, 2: 0.012, 3: 0.0024}[lv]
            tj = [b + off for b in base]
            if j["type"] == "thermal" and fp in hot:
                tj[0] += 10.0
            if j["type"] == "fv" and fp in fv_bad:
                tj = [t + 5.0 for t in tj]
            eb = 1e-3 if j["type"] == "fv" and fp in fv_eb_bad else 1e-9
            return {"tj": tj, "tj_node": [[0.0, 0.0, 0.0]] * 4, "nodes": 1000 * 8 ** lv,
                    "energy_balance": eb, "picard_iters": 3, "picard_residual_K": 1e-6, "fingerprint": fp}
        if j["type"] == "screen":
            raise RuntimeError("screens are run by the selftest itself")
        raise RuntimeError(j["type"])
    return lsub, l1, job


def _hand_e_R(x, c) -> float:
    """e_R written out again from O006 P3's text (research/notes/o006-p3-em-convergence.md; O003 A1), not through
    mfos.metrics: on the ratio R = x / c per level [0.25 mm, 0.5 mm, 5/3/3, 20/12/12, wire], lateral 3 |R025 - R05|;
    thickness: middle value R05 between R533 (coarse) and R201212 (fine), Richardson 1.25 |e21| q / (q - 1), q = e32 / e21,
    if monotone (e21 e32 > 0, |e21| < |e32|), else 3 max(|e21|, |e32|); filaments 3 |Rwire - R05|; summed linearly."""
    R = [a / b for a, b in zip(x, c, strict=True)]
    e21, e32 = R[1] - R[3], R[2] - R[1]
    thick = 1.25 * abs(e21) * (e32 / e21) / (e32 / e21 - 1) if e21 * e32 > 0 and abs(e21) < abs(e32) else 3 * max(abs(e21), abs(e32))
    return 3 * abs(R[0] - R[1]) + thick + 3 * abs(R[4] - R[1])


# Literal e_R pairs (T0305 finding 3, T0304 finding 3), worked by hand.  Pair 1: R = x / c = [0.5, 0.51, 0.53, 0.505,
# 0.515]; lateral 3 x 0.01 = 0.03; thickness e21 = 0.51 - 0.505 = 0.005, e32 = 0.53 - 0.51 = 0.02, monotone, q = 4,
# 1.25 x 0.005 x 4 / 3 = 0.025 / 3; filaments 3 x 0.005 = 0.015; e_R = 0.045 + 0.025 / 3 = 0.0533333...  Pair 2: R =
# [0.5, 0.51, 0.505, 0.52, 0.51]; lateral 0.03; e21 = -0.01, e32 = -0.005, |e21| > |e32|: 3 x 0.01 = 0.03; filaments 0;
# e_R = 0.06.
E_R_LITERALS = (([10.0, 12.75, 5.3, 20.2, 10.3], [20.0, 25.0, 10.0, 40.0, 20.0], 0.053333333333333333),
                ([10.0, 12.75, 5.05, 20.8, 10.2], [20.0, 25.0, 10.0, 40.0, 20.0], 0.06))
# s_ref by its definition (O003 A1) on fake_world's 'snap' and 'ref' values: 2 |20.1 / 20.0 - 1| = 0.01 up to rounding.
# Written as the expression, not the literal 0.01, so the direct driver below receives the same float the runner computes
# (the replay comparison is exact); the literal 0.01 is checked separately with a 1e-12 tolerance.
S_REF_HAND = 2.0 * abs(20.1e-9 / 20.0e-9 - 1.0)
# rule strictness on gen2_0's measure_rules record (experiments/drafts/E008.dev_rows.json): smallest DC-link gap 1.5 mm;
# DC+/PHASE 6 mm > 2 x 1.5 mm is flagged, DC+/DC- 2.5 mm and PHASE/DC- 1.5 mm are not
RS_RECORD = {"gap_dcp_phase": 0.006, "gap_phase_dcm": 0.0015, "gap_dcp_dcm": 0.0025, "gap_signal_dcp": None,
             "gap_other_min": None, "min_wire_pitch": 0.01, "n_dies": 4}
RS_EXPECT = {"gap_dcp_phase": True, "gap_phase_dcm": False, "gap_dcp_dcm": False}
SCENARIOS = {  # name: (number of references, off-grid reference indices, planted Tj failures per reference: the n lowest L_sub)
    "headroom": (2, (), {}), "twin_best": (2, (), {}), "levelled": (2, (), {}),
    "offgrid_tj": (2, (0,), {0: 1, 1: 4}),  # ref 0: off-grid, lowest-L_sub fails; ref 1: whole first batch fails
    "stack_types": (3, (), {}),  # default, AMB, DBC differing only in die attach; F6(e) and F6(c) planted on the FV solves
}


def _hand_asc(chunks: dict, l1, lsub, n_short: int) -> list[str]:
    """Steps 1-2 of the driver redone by hand from the recorded stream: the n_short lowest L1 (ties by generation index),
    first occurrence of a fingerprint only, then ascending L_sub (ties by index)."""
    seen, allc = set(), []
    for key in chunks:
        for fp, _fam in chunks[key]:
            allc.append((l1(FakeLay(fp, None)), len(allc), fp))
    short = []
    for _v, i, fp in sorted(allc):
        if fp not in seen:
            seen.add(fp)
            short.append((i, fp))
        if len(short) == n_short:
            break
    return [fp for i, fp in sorted(short, key=lambda t: (lsub(t[1]), t[0]))]


def selftest() -> int:
    import tempfile

    from moduleforge.geometry import default_amb_stack, default_dbc_stack
    from moduleforge.optimize import search as S
    spec = load_spec()
    cfg = json.loads(json.dumps(spec["config"]))
    failures = []
    # literal e_R pairs: the metric and the selftest's own e_R must both give the hand values
    for x, c, want in E_R_LITERALS:
        for who, v in (("mfos.metrics", MX.ratio_band_estimate(x, c)), ("_hand_e_R", _hand_e_R(x, c))):
            if abs(v - want) > 1e-12:
                failures.append(f"e_R literal: {who} {v!r} != hand {want!r}")
    # rule strictness from measure_rules' gap_* keys (T0305 finding 1)
    rs = rule_strictness(RS_RECORD)
    if {k: v["flag_2x"] for k, v in rs.items()} != RS_EXPECT or any(v["smallest_dc_link_gap_m"] != 0.0015 for v in rs.values()):
        failures.append(f"rule_strictness {rs} != {RS_EXPECT} with link 1.5 mm")
    for bad in ({"spacing_dcp_dcm": 0.002}, {"clearance_dcp_dcm": 0.002}):  # T0305's 'spacing_' prefix, another name
        try:
            rule_strictness(bad)
            failures.append(f"rule_strictness: a measured spacing under an unknown key did not raise: {bad}")
        except RuntimeError:
            pass
    if rule_strictness({"min_wire_pitch": 0.01, "gap_dcp_dcm": None}) != {}:
        failures.append("rule_strictness: a record without a measured gap gave a non-empty report")
    # stack types (T0305 finding 0): the die attach and the die belong to the signature
    dbc = default_dbc_stack()
    st_die_attach = _stack_type(dataclasses.replace(dbc, die_attach=dataclasses.replace(
        dbc.die_attach, thickness=2 * dbc.die_attach.thickness)))
    st_amb = _stack_type(default_amb_stack())
    if _stack_type(default_dbc_stack()) != DEFAULT_STACK or DEFAULT_STACK in (st_die_attach, st_amb) or st_die_attach == st_amb:
        failures.append(f"stack types: default {_stack_type(dbc)}, die attach only {st_die_attach}, AMB {st_amb}")
    scfg = dict(n_candidates=200, n_first=50, shortlist=16, batch=4, max_checks=8, tj_margin=2.0, chunk=50)
    for scenario, (n_refs, offgrid, n_hot) in SCENARIOS.items():
        hot, fv_bad, fv_eb_bad = set(), set(), set()
        lsub, l1, fjob = fake_world(scenario, hot, fv_bad, fv_eb_bad)
        types = [DEFAULT_STACK, st_amb, st_die_attach] if scenario == "stack_types" else [DEFAULT_STACK, "other:fakeAlN"]
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            sched = Scheduler(1e9, 8, 2, fake=fjob)
            run = Run(cfg, root, sched, smoke=False, threads=2, fake={"l1": l1})
            refs = []
            for k in range(n_refs):
                rc = RefCtx(f"fake{k}", "dev", None, FakeLay(f"ref{k}", None), twin=FakeLay(f"twin{k}", None),
                            D=FakeLay(f"D{k}", None), area_m2=0.008)
                if k in offgrid:
                    rc.on_grid, rc.snap025 = False, FakeLay(f"snap{k}", None)
                rc.stack_type = types[k]
                refs.append(rc)
            s_hand = {rc.rid: (S_REF_HAND if not rc.on_grid else 0.0) for rc in refs}
            if scenario == "stack_types":  # planted on the first non-default type in sorted order: a single overwritten
                first = min(types[1:])  # spot_ref (T0305 finding 0) checked only the last one
                fv_bad.add(f"ref{types.index(first)}")
                eb_rid, ok_rid = (f"fake{types.index(t)}" for t in (max(types[1:]), first))  # F6(c) on the other type
                fv_eb_bad.add(f"ref{types.index(max(types[1:]))}")
            run.drivers = {}
            seeds = {(rc.rid, ns): 1000 + i for i, (rc, ns) in enumerate((r, n) for r in refs for n in ("main", "control"))}

            # screens: the frozen driver itself, with a fake generate, writing the stream file as child_screen does
            def gen_for(rid, ns):
                def gen(spec_, m, sk):
                    return [FakeLay(hashlib.sha256(f"{rid}{ns}{sk}{i}".encode()).hexdigest(), f"fam{i}") for i in range(m)]
                return gen
            orig_save = save_ctx
            globals()["save_ctx"] = lambda rc, wd: (wd.mkdir(parents=True, exist_ok=True), str(wd / "ctx.pkl"))[1]
            asc_hand = {}
            try:
                for rc in refs:
                    for ns in ("main", "control"):
                        wd = root / rc.rid / ns
                        wd.mkdir(parents=True, exist_ok=True)
                        chunks = {}
                        g0 = gen_for(rc.rid, ns)

                        def gen(spec_, m, sk, g0=g0, chunks=chunks):
                            lays = g0(spec_, m, sk)
                            chunks[f"{m}:{sk}"] = [(x.fp, x.family) for x in lays]
                            return lays

                        def stop(*_):
                            raise _ScreenDone
                        sv = S.Solvers(l1=l1, l_sub=stop, band=stop, thermal=stop)
                        try:
                            if ns == "main":
                                S.run_search(None, rc.reference, rc.twin, seeds[(rc.rid, ns)], sv, None, 0.0, wd,
                                             S.SearchConfig(**scfg), gen)
                            else:
                                S.run_control(None, rc.D, seeds[(rc.rid, ns)], sv, 0.0, wd, S.SearchConfig(**scfg), gen)
                        except _ScreenDone:
                            pass
                        with gzip.open(wd / "stream.json.gz", "wt") as f:
                            json.dump(chunks, f)
                        (wd / "screen.json").write_text(json.dumps({"status": "ok"}))
                        if ns == "main":
                            asc_hand[rc.rid] = _hand_asc(chunks, l1, lsub, scfg["shortlist"])
                            hot.update(asc_hand[rc.rid][:n_hot.get(int(rc.rid[4:]), 0)])
                run.drive(refs, seeds, scfg)
            finally:
                globals()["save_ctx"] = orig_save
            rows, extra = assemble_rows(run, refs, smoke=False)
            met, checks, rep = evaluate(run, refs, rows, extra, cfg)
            cmap = {c["name"]: c for c in checks}
            # independent hand values: rebuild h_lo of every reference from the rows with the rule text, own e_R
            hand_lo, hand_hi, hand_best = [], [], {}
            five = lambda r: [r[c] for c in BAND_COLS]  # noqa: E731
            for rc in refs:
                rr = [r for r in rows if r.get("reference_id") == rc.rid and r["kind"] == "layout"]
                tw = next(r for r in rr if r["role"] == "twin")
                cands = sorted([r for r in rr if r["role"] == "candidate"], key=lambda r: (r["L_sub_H"], r["layout_id"]))
                if [c["fingerprint"] for c in cands] != asc_hand[rc.rid]:
                    failures.append(f"{scenario}/{rc.rid}: shortlist L_sub order differs from the hand screen")
                a, s = tw["L_sub_H"] / (tw["L_sub_H"] + 7e-9), s_hand[rc.rid]
                # F3 by hand: batches of 4 in ascending L_sub, at most 8; fake Tj passes unless planted hot
                best = next((c for c in cands[:8] if c["fingerprint"] not in hot), None)
                hand_best[rc.rid] = best
                if best is None or tw["L_sub_H"] <= best["L_sub_H"]:
                    hand_lo.append(-a * s)
                else:
                    r_ = best["L_sub_H"] / tw["L_sub_H"]
                    hand_lo.append(a * (1 - r_ * (1 + 2 * _hand_e_R(five(best), five(tw)) + s)))
            # K1 by hand from the rows (rule text: levelling, twin rule, near ties incl. the inductance-only best)
            for rc in refs:
                rr = [r for r in rows if r.get("reference_id") == rc.rid]
                tw = next(r for r in rr if r["kind"] == "layout" and r["role"] == "twin")
                ref_row = next(r for r in rr if r["kind"] == "reference")
                cands = sorted([r for r in rr if r["kind"] == "layout" and r["role"] == "candidate"],
                               key=lambda r: (r["L_sub_H"], r["layout_id"]))
                a, s, ind = tw["L_sub_H"] / (tw["L_sub_H"] + 7e-9), s_hand[rc.rid], cands[0]
                w = 2 * _hand_e_R(five(ind), five(tw)) + s
                if not ref_row["L1_min_first5000_H"] <= (1 + w) * ref_row["L1_min_all_H"]:
                    hh = math.inf
                elif tw["L_sub_H"] <= ind["L_sub_H"]:
                    hh = a * s
                else:
                    hh = max(a * (1 - c["L_sub_H"] / tw["L_sub_H"] * (1 - 2 * _hand_e_R(five(c), five(tw)) - s))
                             for c in cands if c["L_sub_H"] <= (1 + w) * ind["L_sub_H"])
                hand_hi.append(hh)
            k1 = met["headroom_max_hi_ind"]
            if not (k1 == max(hand_hi) or abs(k1 - max(hand_hi)) <= 1e-12):
                failures.append(f"{scenario}: K1 {k1} vs hand {max(hand_hi)}")
            if scenario == "levelled" and not math.isfinite(k1):
                failures.append("levelled: K1 is not finite, the near-tie path was not exercised")
            # the replayed, scheduled driver must choose exactly what a direct single-process driver run chooses
            for rc in refs:
                for ns in ("main", "control"):
                    def em1(lay, lv, fjob=fjob):
                        return fjob({"type": "em", "fp": lay.fingerprint(), "level": lv})["L_H"]

                    def th1(lay, P, fjob=fjob):
                        recs = [fjob({"type": "thermal", "fp": lay.fingerprint(), "level": lv}) for lv in (0, 1, 2)]
                        return {"tj": [r["tj"] for r in recs], "tj_max_node": [r["tj_node"] for r in recs],
                                "nodes": [r["nodes"] for r in recs], "fingerprint": lay.fingerprint(),
                                "energy_balance": [r["energy_balance"] for r in recs],
                                "picard": [{"iters": r["picard_iters"], "residual_K": r["picard_residual_K"]} for r in recs]}
                    sv = S.Solvers(l1=l1, l_sub=lambda lay: em1(lay, "lat0.25"),
                                   band=lambda lay: [em1(lay, lv) for lv in BAND], thermal=th1)
                    if ns == "main":
                        ref_res = S.run_search(None, rc.reference, rc.twin, seeds[(rc.rid, ns)], sv, 42.0, s_hand[rc.rid],
                                               None, S.SearchConfig(**scfg), gen_for(rc.rid, ns))
                    else:
                        ref_res = S.run_control(None, rc.D, seeds[(rc.rid, ns)], sv, 0.0, None, S.SearchConfig(**scfg),
                                                gen_for(rc.rid, ns))
                    got = run.drivers[(rc.rid, ns)].result
                    for fld in ("inductance_best", "a1_best", "null_best", "near_ties", "w_ind", "w_ind_recon", "w_ctrl",
                                "w_a1", "thermal_checked", "null_new_checks", "levelling"):
                        if getattr(got, fld) != getattr(ref_res, fld):
                            failures.append(f"{scenario}: replay != direct driver in {rc.rid}/{ns}.{fld}")
            if abs(met["headroom_min_lo"] - min(hand_lo)) > 1e-12:
                failures.append(f"{scenario}: h_lo {met['headroom_min_lo']} vs hand {min(hand_lo)}")
            if scenario == "twin_best" and any(c["passed"] for c in checks if c["name"].startswith("F1b_control")):
                failures.append("twin_best: the planted F1(b) failure (search cannot reach the twin) was not caught")
            if not met["null_twin_as_best_h_lo"] <= 0.0:
                failures.append(f"{scenario}: null h_lo {met['null_twin_as_best_h_lo']} > 0")
            if not math.isfinite(met.get("l1_only_null_h_lo", math.nan)):
                failures.append(f"{scenario}: l1_only_null_h_lo {met.get('l1_only_null_h_lo')} is not finite")
            planted = set()
            if scenario == "offgrid_tj":
                rec0, rec1 = rep["fake0"]["record"], rep["fake1"]["record"]
                ref0 = next(r for r in rows if r["kind"] == "reference" and r["reference_id"] == "fake0")
                if abs(rec0["s_ref"] - S_REF_HAND) > 1e-12 or abs(run.s_ref["fake0"] - S_REF_HAND) > 1e-12:
                    failures.append(f"offgrid_tj: s_ref metric {rec0['s_ref']} driver {run.s_ref['fake0']} != {S_REF_HAND}")
                if ref0.get("L_snap025_H") != 20.1e-9 or ref0.get("L_snap05_H") != 20e-9 or ref0.get("on_grid") is not False:
                    failures.append(f"offgrid_tj: snapping columns {[ref0.get(c) for c in ('on_grid', 'L_snap025_H', 'L_snap05_H')]}")
                if run.drivers[("fake0", "main")].which(refs[0].snap025) != "snap025":
                    failures.append("offgrid_tj: Driver.which does not recognise snap025")
                for rid, rec, n_chk in (("fake0", rec0, 4), ("fake1", rec1, 8)):
                    if hand_best[rid] is None or rec["best_id"] != hand_best[rid]["layout_id"]:
                        failures.append(f"offgrid_tj/{rid}: A1 best {rec['best_id']} != hand {hand_best[rid]['layout_id']}")
                    if rec["n_tj_rejected"] < n_hot[int(rid[4:])] or rec["n_thermal_checked"] != n_chk:
                        failures.append(f"offgrid_tj/{rid}: {rec['n_tj_rejected']} Tj rejections, {rec['n_thermal_checked']} "
                                        f"checked (want >= {n_hot[int(rid[4:])]}, {n_chk})")
                if len(run.drivers[("fake1", "main")].result.rows["checks"]) < 8:
                    failures.append("offgrid_tj: the second thermal batch did not run")
            if scenario == "stack_types":
                want = {st_amb: "fake1", st_die_attach: "fake2"}
                if run.spot_refs != want:
                    failures.append(f"stack_types: spot refs {run.spot_refs} != {want}")
                for st, rid in want.items():
                    fv = [Scheduler.done(j) for j in run.spot_jobs(run.drivers[(rid, "main")])]
                    if len(fv) != 3 or any(f is None for f in fv):
                        failures.append(f"stack_types: {rid} ({st}) has no complete FV levels 1-3")
                    c = cmap.get(f"F6e_stack_type_spot_check:{st}")
                    if c is None or c["passed"] != (st != first):
                        failures.append(f"stack_types: F6e for {st} {c} (planted failure on {first} only)")
                if cmap["F6e_stack_type_spot_check"]["passed"]:
                    failures.append("stack_types: the aggregate F6e check passed with a planted per-type failure")
                planted = {f"F6c_energy_balance:{eb_rid}"}
                if cmap[f"F6c_energy_balance:{eb_rid}"]["passed"] or not cmap[f"F6c_energy_balance:{ok_rid}"]["passed"]:
                    failures.append(f"stack_types: the planted FV energy-balance failure ({eb_rid} only) was not caught "
                                    f"by F6(c), or {ok_rid} failed")
            for c in checks:
                if c["name"].startswith(("recompute_agrees", "F6a", "F6c", "F6d", "F1c", "at_least", "driver_s_ref")) \
                        and not c["passed"] and c["name"] not in planted:
                    failures.append(f"{scenario}: {c['name']} {c['detail'][:200]}")
            n_c = sum(r["kind"] == "layout" and r["role"] == "candidate" for r in rows)
            if n_c != 16 * n_refs:
                failures.append(f"{scenario}: {n_c} candidate rows, want 16 per reference")
            if any(not math.isfinite(float(r["L_sub_null_H"])) for r in rows):
                failures.append("a row without a finite L_sub_null_H")
            tr = thermal_report_from_rows(rows, cfg["gates"], 1e-3, 2.0)
            if sorted(tr) != sorted(rc.rid for rc in refs) or any(v["summary"]["n_layouts_growth_fail"] for v in tr.values()):
                failures.append(f"{scenario}: thermal report {json.dumps({k: v['summary'] for k, v in tr.items()})[:300]}")
            log(f"selftest {scenario}: h_lo {met['headroom_min_lo']:.5f} (hand {min(hand_lo):.5f}), K1 "
                f"{met['headroom_max_hi_ind']}, null {met['null_twin_as_best_h_lo']:.5f}, L1-only null "
                f"{met.get('l1_only_null_h_lo', math.nan):.5f}, {len(rows)} rows, {len(checks)} checks "
                f"({sum(not c['passed'] for c in checks)} failing), F6e "
                f"{[(c['name'][26:] or 'all', round(c['value'], 4)) for c in checks if c['name'].startswith('F6e') and c['value'] is not None]}")
    # memory learning (attempt 5): prior until measured, then model x 1.1 x the largest measured ratio, also from a cache
    with tempfile.TemporaryDirectory() as td:
        sc = Scheduler(10.0, 8, 2, solo_cap_GB=10.0)
        j1 = {"type": "em", "level": "fil_f", "ref": "r", "out": str(Path(td) / "a.json"), "mem_GB": 5.2, "mem_model_GB": 2.0}
        j2 = dict(j1, out=str(Path(td) / "b.json"))
        if sc.mem_of(j2) != 5.2:
            failures.append(f"mem_of before any measurement: {sc.mem_of(j2)} != prior 5.2")
        Path(j1["out"]).write_text(json.dumps({"status": "ok", "peak_GB": 5.0}))
        sc.submit([j1, j2])  # j1 is cached: learned on submit; j2 queued with the learned estimate
        if abs(sc.queue[j2["out"]]["mem_GB"] - 2.0 * 1.1 * 2.5) > 1e-12 or sc.mem_of(dict(j1, ref="other", mem_GB=5.2)) != 5.2:
            failures.append(f"memory learning: {sc.queue.get(j2['out'], {}).get('mem_GB')} != 5.5 or leaked across refs")
    fr = freeze_checks(cfg)
    failures += [f"freeze {c['name']}" for c in fr if not c["passed"]]
    for f in failures:
        print("FAIL", f)
    print("selftest", "passed" if not failures else f"failed ({len(failures)})")
    return 0 if not failures else 1


# ------------------------------------------------------------------------------------------------ plan
def simulate(jobs: list[dict], vcpus: int, cap: float) -> float:
    """List-scheduling makespan (s): a job starts when its group dependencies are done and it fits in vCPUs and memory;
    longest first among ready jobs."""
    groups: dict[str, list] = {}
    for j in jobs:
        groups.setdefault(j["group"], []).append(j)
    left = {g: len(v) for g, v in groups.items()}
    t, running, done, pending = 0.0, [], set(), list(jobs)
    while pending or running:
        ready = [j for j in pending if all(d in done for d in j["after"])]
        ready.sort(key=lambda j: -j["est_s"])
        for j in ready:
            if sum(r["threads"] for _, r in running) + j["threads"] <= vcpus and sum(r["mem_GB"] for _, r in running) + j["mem_GB"] <= cap:
                running.append((t + j["est_s"], j))
                pending.remove(j)
        if not running:
            raise RuntimeError(f"unschedulable: {[j['name'] for j in ready][:3]}")
        running.sort(key=lambda x: x[0])
        t, j = running.pop(0)
        left[j["group"]] -= 1
        if left[j["group"]] == 0:
            done.add(j["group"])
    return t


def plan_jobs(r: dict, cm: dict, threads: int, n_near: int, batches: int, n_null: int, n_cand: int) -> list[dict]:
    """Every solve of one reference with its (wall s, peak GB) from the cost model on that reference's own sizes:
    l2_layout unknowns from the lattice area (P3: 29.18 per 0.25 mm cell on Case 4), scikit-fem DOFs and FV cells as
    measured by thermal_fem.estimate_dofs / thermal_layout.build_layout_grid (plan_references; candidates use the
    largest DOF count of the probed generator candidates)."""
    name, area, J = r["name"], r["area_m2"], []

    def add(group, after, role, kind, t, m, n, thr=threads):
        J.append({"name": f"{name}:{role}", "group": f"{name}:{group}", "after": [f"{name}:{x}" for x in after],
                  "est_s": t, "mem_GB": m, "threads": thr, "kind": kind, "n": int(n)})

    def em(group, after, role, levels):
        for lv in levels:
            n = em_unknowns(area, EM_LEVELS[lv][0], lv, cm)
            add(group, after, f"{role}:{lv}", "em", *em_cost(n, lv, cm), n)

    def th(group, after, role, which, levels=(0, 1, 2), mult=1):
        for lv in levels:
            d = r["fem_dofs"][which][lv]
            t, m = fem_cost(d, cm)
            add(group, after, f"{role}:T{lv}", "thermal", t * mult, m, d)
    for ns in ("main", "control"):
        add(f"screen_{ns}", [], f"screen_{ns}", "screen", r["screen_s_per_candidate"] * n_cand, cm["screen_mem_GB"],
            n_cand, 1)
    for role in ("reference", "twin", "D"):
        em("base", [], role, BAND)
    if not r["on_grid"]:
        em("base", [], "snap025", ["lat0.25"])
    th("cal", [], "calibration", "reference", (0,), cm["calibration_solves"])
    th("therm_base", ["cal"], "reference", "reference")
    th("therm_base", ["cal"], "twin", "reference")
    if r["spot"]:
        for lv in (1, 2, 3):
            c = r["fv_cells"][lv - 1]
            add("spot", ["cal"], f"fv:L{lv}", "fv", *fv_cost(c, cm), c)
    for k in range(16):
        em("short_main", ["screen_main"], f"cand{k}", ["lat0.25"])
        em("short_ctrl", ["screen_control"], f"ctrl{k}", ["lat0.25"])
    em("band_ind", ["short_main"], "ind_best", BAND[1:])
    em("band_ctrl", ["short_ctrl"], "ctrl_best", BAND[1:])
    for b in range(batches):
        for k in range(4):
            th(f"batch{b}", ["short_main", "cal"] + ([f"batch{b - 1}"] if b else []), f"b{b}c{k}", "candidate")
    for k in range(n_near):
        em("near", ["band_ind", "base"], f"near{k}", BAND[1:])
    for k in range(n_null):
        th("null", [f"batch{batches - 1}"], f"null{k}", "candidate")
    return J


def _dev_near_ties() -> int | None:
    """Near-tie union size seen in the dev rows (max over searched dev references), if any."""
    if not DEV_ROWS.exists():
        return None
    meta = json.loads(DEV_ROWS.read_text()).get("meta", {})
    n = [v.get("near_ties") for v in meta.get("per_reference", {}).values() if isinstance(v.get("near_ties"), int)]
    return max(n) if n else None


def plan(args, cfg: dict) -> int:
    """Schedule of every solve on the one 8-vCPU VM (founder constraint, 2026-11-09).  Phase A: list scheduling on the
    configured machine (memory_fraction x RAM, vCPUs by thread count).  Phase B: any job larger than phase A's usable
    memory runs alone on the same VM resized with N2D extended memory to fit it (stop, set machine type, start).
    VM-hours, $, billed vCPU-hours and process CPU-hours per case; the near-tie count at the dev rows' value
    (expected) and at its maximum of 15 (upper)."""
    cm = cfg["compute"]["cost_model"]
    vm = cfg["compute"]["vm"]
    threads, why = thread_count(cfg)
    vcpus, cap = vm["vcpus"], vm["ram_GB"] * vm["memory_fraction"]
    n_dev = _dev_near_ties()
    exp = list(cm["plan_expected"])
    if n_dev is not None:
        exp[0] = n_dev
    out = {"threads_per_solve": threads, "why": why, "vm": vm, "usable_GB": cap,
           "near_ties_expected_source": "dev rows" if n_dev is not None else "default (no dev search rows)", "cases": {}}
    for case, (n_near, batches, n_null) in {"expected": tuple(exp), "upper": tuple(cm["plan_upper"])}.items():
        J = []
        for r in cfg["compute"]["plan_references"]:
            J += plan_jobs(r, cm, threads, n_near, batches, n_null, cfg["search"]["n_candidates"])
        big = [j for j in J if j["mem_GB"] > cap]
        small = [j for j in J if j["mem_GB"] <= cap]
        for j in small:  # a phase-A job that waits on a phase-B group is released at the start
            j["after"] = [a for a in j["after"] if not any(b["group"] == a for b in big)]
        mk = simulate(small, vcpus, cap)
        a_h = mk / 3600.0 + vm["overhead_h"]
        b_rows, b_h, b_usd = [], 0.0, 0.0
        b_rng = {t: [0.0, 0.0] for t in cm["fv_sensitivity"]}  # phase B (hours, $) at each end of the FV rate range
        for j in big:
            ram = math.ceil(j["mem_GB"] / vm["memory_fraction"] / 8.0) * 8.0
            usd_h = vm["usd_per_h"] + vm["ext_usd_per_GB_h"] * (ram - vm["ram_GB"])
            h = j["est_s"] / 3600.0 + vm["resize_overhead_h"]
            sens = {}
            for t, sv in cm["fv_sensitivity"].items():  # T0306: the FV time model's stated range (fv_rate_basis)
                hs = (fv_cost(j["n"], cm, beta=sv["beta"], s_per_cell=cm["fv_s_per_cell_mac"] * sv["vm_factor"])[0]
                      if j["kind"] == "fv" else j["est_s"]) / 3600.0 + vm["resize_overhead_h"]
                sens[t] = {"hours": round(hs, 2), "usd": round(hs * usd_h, 2)}
                b_rng[t][0] += hs
                b_rng[t][1] += hs * usd_h
            b_rows.append({"job": j["name"], "peak_GB": round(j["mem_GB"], 1), "machine": f"n2d-custom-8-{int(ram * 1024)}-ext",
                           "fits_n2d_768GB": ram <= 768, "hours": round(h, 2), "usd": round(h * usd_h, 2),
                           "usd_per_h": round(usd_h, 4), "sensitivity": sens})
            b_h, b_usd = b_h + h, b_usd + h * usd_h
        vm_h = a_h + b_h
        per_ref = {}
        for r in cfg["compute"]["plan_references"]:
            jr = [j for j in J if j["name"].startswith(r["name"] + ":")]
            per_ref[r["name"]] = {k: round(max(j["mem_GB"] for j in jr if j["kind"] == k), 1)
                                  for k in ("em", "thermal", "fv") if any(j["kind"] == k for j in jr)}
        cpu_h = sum(j["est_s"] * (cm["cores_per_2thread_solve"] if j["threads"] == 2 else 1.0) for j in J) / 3600.0
        per_solve = {}  # founder constraint: per-solve wall and memory on the 8-vCPU VM (first plan reference's sizes)
        r0 = cfg["compute"]["plan_references"][0]["name"]
        for j in J:
            if j["name"].startswith(r0 + ":"):
                role = j["name"].split(":", 1)[1]
                if j["kind"] == "em":
                    key = f"em:{role.rsplit(':', 1)[1]}"
                elif j["kind"] == "thermal":
                    who = role.split(":")[0]
                    who = who if who in ("calibration", "reference", "twin") else "candidate"
                    key = f"thermal:{who}:{role.rsplit(':', 1)[1]}"
                else:
                    key = f"{j['kind']}:{role}"
                per_solve.setdefault(key, {"n": j["n"], "wall_h": round(j["est_s"] / 3600.0, 3),
                                           "peak_GB": round(j["mem_GB"], 2), "threads": j["threads"]})
        out["cases"][case] = {
            "near_ties": n_near, "thermal_batches": batches, "null_extra_checks": n_null, "n_solves": len(J),
            "phase_a_hours": round(a_h, 2), "phase_b_big_memory_jobs": b_rows, "phase_b_hours": round(b_h, 2),
            "phase_b_usd": round(b_usd, 2),
            "phase_b_sensitivity": {t: {"phase_b_hours": round(v[0], 2), "phase_b_usd": round(v[1], 2),
                                        "vm_hours": round(a_h + v[0], 2), "usd": round(a_h * vm["usd_per_h"] + v[1], 2),
                                        "billed_vcpu_hours": round((a_h + v[0]) * vcpus, 1)} for t, v in b_rng.items()},
            "vm_hours": round(vm_h, 2),
            "usd": round(a_h * vm["usd_per_h"] + b_usd, 2), "billed_vcpu_hours": round(vm_h * vcpus, 1),
            "process_cpu_hours": round(cpu_h, 1), "peak_GB_per_reference": per_ref,
            "per_solve_on_vm": {"reference_sizes": r0, "note": "wall at the scheduled concurrency (four 0.25 mm solves at "
                                "once, two threads each); n = unknowns / DOFs / cells / candidates", "solves": per_solve},
            "end_date_if_start": (dt.datetime.fromisoformat(vm["earliest_start"]) + dt.timedelta(hours=vm_h)).date().isoformat()}
        if args.verbose:
            for j in J:
                print(f"{j['name']:<44} {j['kind']:<8} n={j['n']:>11} {j['mem_GB']:7.1f} GB {j['est_s'] / 3600:7.2f} h")
    print(json.dumps(out, indent=1, default=str))
    if args.plan_out:
        Path(args.plan_out).write_text(json.dumps(out, indent=1, default=str))
    return 0


# ------------------------------------------------------------------------------------------------ dev and full runs
def search_cfg(cfg: dict, smoke: bool) -> dict:
    s = dict(cfg["search"])
    if smoke:
        s.update(cfg["dev"]["smoke"]["search"])
    return {k: s[k] for k in ("n_candidates", "n_first", "shortlist", "batch", "max_checks", "tj_margin", "chunk")}


def dev_pairs(rc: RefCtx, n: int, dseed: int, i: int) -> list:
    """Random DRC-valid candidates of the reference's outline for the band check (dev seed, purpose 3, geometry i)."""
    from moduleforge.generate import derivative as D
    return [Stub(x.fingerprint(), x.family) for x in D.generate(rc.spec, n, derive_seed(dseed, 3, i))] if n else []


def twin_gates_only(run: Run, gates: list[RefCtx], n_pairs: dict, dseed: int, smoke: bool) -> tuple[list[dict], dict]:
    """Pre-registration dev rows without a search (O003 notes): the twin gates F1(a1), (a2) on the frozen twin of the
    reference, and e_R of the twin against ``n_pairs`` random DRC-valid candidates of the same outline (dev seed)."""
    rows, rep = [], {}
    run.drivers = getattr(run, "drivers", {})
    for rc in gates:
        ctx = save_ctx(rc, run.root / rc.rid)
        d = Driver(rc, "main", 0, run.root / rc.rid, ctx, {}, run)
        run.drivers[(rc.rid, "main")] = d
        pairs = dev_pairs(rc, n_pairs[rc.rid], dseed, run.geom_index[rc.rid])
        while True:
            if rc.rid not in run.P:
                rec = Scheduler.done(run.calib_job(rc))
                if rec is not None:
                    run.P[rc.rid], run.cal[rc.rid] = rec["P_ref_W"], rec
            jobs = [j for lay in (rc.reference, rc.twin) for j in d.em_jobs(lay, BAND) + d.th_jobs(lay)]
            jobs += [j for p in pairs for j in d.em_jobs(p, BAND)]
            run.sched.submit(jobs)
            if all(Scheduler.done(j) for j in jobs if j["type"] != "calibrate") and rc.rid in run.P:
                break
            run.sched.step()
        five = {lay.fingerprint(): [Scheduler.done(j)["L_H"] for j in d.em_jobs(lay, BAND)]
                for lay in [rc.reference, rc.twin] + pairs}
        th = {lay.fingerprint(): [Scheduler.done(j) for j in d.th_jobs(lay)] for lay in (rc.reference, rc.twin)}
        b = {fp: MX.tj_bounds([[t[lv]["tj"][k] for lv in range(3)] for k in range(len(t[0]["tj"]))], floor=1e-3)
             for fp, t in th.items()}
        fw, fr = rc.twin.fingerprint(), rc.reference.fingerprint()
        if not rc.on_grid:
            raise RuntimeError(f"{rc.rid}: the dev gates path takes s_ref = 0 and needs a geometry on the 0.5 mm grid")
        a1 = MX.twin_gate_inductance(five[fw], five[fr], 0.0)
        a2 = MX.twin_gate_thermal(b[fw], b[fr])
        e_tr = MX.ratio_band_estimate(five[fw], five[fr])
        pe = [{"candidate": p.fp, "e_R": MX.ratio_band_estimate(five[p.fp], five[fw]), "R": five[p.fp][0] / five[fw][0]}
              for p in pairs]
        for fp, role, lab in ((fw, "twin", "twin"), (fr, "reconstruction", "reconstruction")):
            rows.append({"kind": "layout", "reference_id": rc.rid, "layout_id": lab, "role": role, "fingerprint": fp,
                         **dict(zip(BAND_COLS, five[fp], strict=True)), "L_sub_null_H": five[fp][0], "smoke": smoke})
            for k in range(len(th[fp][0]["tj"])):
                rows.append({"kind": "die", "reference_id": rc.rid, "layout_id": lab, "die_id": f"d{k}", "fingerprint": fp,
                             **{f"Tj_l{lv}_K": th[fp][lv]["tj"][k] for lv in range(3)},
                             "nodes": [t["nodes"] for t in th[fp]], "power_W": run.P[rc.rid],
                             "L_sub_null_H": five[fw][0], "smoke": smoke})
        for p in pairs:
            rows.append({"kind": "layout", "reference_id": rc.rid, "layout_id": f"pair_{p.fp[:12]}", "role": "dev_pair",
                         "fingerprint": p.fp, **dict(zip(BAND_COLS, five[p.fp], strict=True)),
                         "L_sub_null_H": five[p.fp][0], "smoke": smoke})
        rep[rc.rid] = {"gate_a1": a1, "gate_a2": a2, "a1_lhs": abs(1 - five[fw][0] / five[fr][0]), "a1_rhs": 2 * e_tr,
                       "a2_lhs": abs(b[fw][0] - b[fr][0]), "a2_rhs": b[fw][1] + b[fr][1], "tj_bounds_twin": b[fw],
                       "tj_bounds_recon": b[fr], "band_pairs": pe, "P_ref_W": run.P[rc.rid],
                       "calibration": run.cal[rc.rid], "info": rc.info, "twin_mode": rc.twin_rec.get("mode")}
        log(f"{rc.rid}: gates a1 {a1} a2 {a2}; pairs e_R {[round(x['e_R'], 5) for x in pe]}")
    return rows, rep


def dev(args) -> int:
    spec = load_spec()
    cfg = spec["config"]
    smoke = args.smoke
    threads, why = thread_count(cfg) if not smoke else (1, "local smoke: one thread")
    root = Path(args.workdir or ROOT / "experiments" / "drafts" / "E008_dev_work")
    if (root / "HOLD").exists():  # pause switch for long local runs: remove <workdir>/HOLD to run
        log(f"{root / 'HOLD'} exists: dev run held before any solve")
        return 3
    cap = args.mem_cap_gb or cfg["compute"]["vm"]["ram_GB"] * cfg["compute"]["vm"]["memory_fraction"]
    sched = Scheduler(cap, args.vcpus or cfg["compute"]["vm"]["vcpus"], threads, solo_cap_GB=args.solo_cap_gb)
    run = Run(cfg, root, sched, smoke, threads)
    dseed = int(cfg["dev"]["dev_seed"])
    names = args.geoms.split(",") if args.geoms else cfg["dev"]["geometries"]
    refs, fail_fast, gate_only = [], {}, set()
    n_pairs, run.geom_index = {}, {}
    for i, name in enumerate(names):  # name[:gates[:n_pairs]]; the index i seeds the geometry's samples
        parts = name.split(":")
        rc = dev_reference(parts[0], cfg)
        run.geom_index[rc.rid] = i
        n_pairs[rc.rid] = int(parts[2]) if len(parts) > 2 else args.band_pairs
        if len(parts) > 1 and parts[1] == "gates":
            gate_only.add(rc.rid)
        rc = prepare(rc, cfg, cfg["dev"]["smoke"]["quick_ok_draws"] if smoke else cfg["quick_ok_draws"],
                     derive_seed(dseed, 2, i))
        log(f"{rc.rid}: twin {rc.twin_rec.get('mode')} D walk {bool(rc.info.get('walk'))} fail_fast "
            f"{rc.info.get('fail_fast')} quick_ok {rc.info.get('quick_ok')}")
        (fail_fast if rc.info.get("fail_fast") else {}).update({rc.rid: rc.info.get("fail_fast")})
        gates_ok = rc.rid in gate_only and rc.twin is not None  # the twin gates need W only, not D
        if not rc.info.get("fail_fast") or gates_ok:
            refs.append(rc)  # s_ref: Run.drive (s_ref_of) for searched references; dev geometry is on the grid
    gates = [rc for rc in refs if rc.rid in gate_only]
    refs = [rc for rc in refs if rc.rid not in gate_only]
    seeds = {(rc.rid, ns): derive_seed(dseed, k, i) for i, rc in enumerate(refs) for k, ns in ((0, "main"), (1, "control"))}
    scfg = search_cfg(cfg, smoke)
    gate_rows, gate_rep = twin_gates_only(run, gates, n_pairs, dseed, smoke) if gates else ([], {})
    if refs:
        run.drive(refs, seeds, scfg)
        rows, extra = assemble_rows(run, refs, smoke)
        met, checks, rep = evaluate(run, refs, rows, extra, cfg)
    else:
        rows, met, checks, rep = [], {}, [], {}
    rows += gate_rows
    rep.update(gate_rep)
    # pre-registration band check: e_R of the twin against random DRC-valid candidates of the same outline
    pairs = [{"reference_id": rid, **pe} for rid, v in gate_rep.items() for pe in v["band_pairs"]]
    for rc in refs:
        d = run.drivers[(rc.rid, "main")]
        ps = dev_pairs(rc, n_pairs[rc.rid], dseed, run.geom_index[rc.rid])
        jobs = [j for x in ps for j in d.em_jobs(x, BAND)]
        sched.submit(jobs)
        while not all(Scheduler.done(j) for j in jobs):
            sched.step()
        tw = extra[rc.rid]["bands"][rc.twin.fingerprint()]
        for x in ps:
            b5 = [Scheduler.done(j)["L_H"] for j in d.em_jobs(x, BAND)]
            pairs.append({"reference_id": rc.rid, "candidate": x.fp, "e_R": MX.ratio_band_estimate(b5, tw),
                          "R": b5[0] / tw[0]})
    for r in rows:
        r["dev_row"] = True
    # T0304 findings 0-1, T0305 finding 4: F6(a) node growth per level step, per-die GCI and its +inf count, and whether
    # the conservative +2 K test is attainable, for every thermally solved dev layout (gates and searched alike)
    therm = {"rule": "E009 smoke rule (NOT the frozen rule)" if smoke else "frozen rule (config.fem_rule)",
             "per_reference": thermal_report_from_rows(rows, cfg["gates"], cfg["metric_params"]["floor"],
                                                       cfg["metric_params"]["tj_limit_K"])}
    for rid, v in therm["per_reference"].items():
        log(f"{rid} thermal report ({therm['rule']}): {json.dumps(v['summary'])}")
    doc = {"schema": "mfos.rows/1", "rows": rows, "meta": {
        "thermal_report": therm,
        "smoke": smoke, "note": ("SMOKE ROWS (local): EM production slot solved at 0.5 mm cells (so the lateral term of "
                                 "e_R is zero), coarsened thermal rule, reduced candidate budget; not evidence"
                                 if smoke else "full-fidelity dev rows"),
        "search": scfg, "threads": [threads, why], "metrics": met, "checks": checks,
        "band_check_pairs": pairs, "band_check_max_e_R": max([p["e_R"] for p in pairs] or [math.nan]),
        "fail_fast": fail_fast, "per_reference": rep, "solve_log": sched.log[-400:]}}
    out = Path(args.rows_out or DEV_ROWS)
    out.write_text(json.dumps(doc, indent=1, default=lambda o: o if not hasattr(o, "__dict__") else str(o)))
    log(f"dev rows -> {out}: metrics {json.dumps({k: v for k, v in met.items() if isinstance(v, float)})}")
    return 0


def full() -> int:
    from mfos.evidence import ExperimentRun
    with ExperimentRun(experiment_id=EID) as er:
        cfg = er.config
        if er.seed is None:
            raise RuntimeError("E008 needs the sealed seed (spec sealed_seed: true)")
        fr = freeze_checks(cfg)
        for c in fr:
            er.sanity(c["name"], c["passed"], detail=c["detail"][:4000])
        if not all(c["passed"] for c in fr):
            raise RuntimeError("frozen hashes or values differ: the run is void (F3, F6(b))")
        if not cfg["references"]:
            raise RuntimeError("config.references is empty: the reference set of D0010 is fixed before registration")
        raise NotImplementedError("judged-reference loading (T0263 reconstructions, vault) is added under a new draft "
                                  "before registration; see the spec's 'founder decisions before registration'")
    return 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--verify-freeze", action="store_true")
    ap.add_argument("--dev", action="store_true")
    ap.add_argument("--plan", action="store_true")
    ap.add_argument("--child")
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--geoms")
    ap.add_argument("--workdir")
    ap.add_argument("--rows-out")
    ap.add_argument("--mem-cap-gb", type=float)
    ap.add_argument("--vcpus", type=int)
    ap.add_argument("--solo-cap-gb", type=float)
    ap.add_argument("--band-pairs", type=int, default=2)
    ap.add_argument("--plan-out")
    ap.add_argument("--verbose", action="store_true")
    a = ap.parse_args(argv)
    os.chdir(ROOT)
    if a.child:
        return child_main(a.child)
    if a.selftest:
        return selftest()
    if a.verify_freeze:
        return verify_freeze()
    if a.plan:
        return plan(a, load_spec()["config"])
    if a.dev:
        return dev(a)
    return full()


if __name__ == "__main__":
    sys.exit(main())
