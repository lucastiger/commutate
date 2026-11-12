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
  (default)        registered run through mfos.evidence.ExperimentRun (sealed seed; config from MFOS_SPEC_JSON): freeze
                   checks, config.references through judged_reference (frozen T0263 script, fingerprint first; D0019),
                   prepare (T0319 guard), Run.drive, assemble_rows, evaluate, declared sanity checks, rows and the
                   evaluation report with the label and the D0019 deviation; resumes from --workdir / $E008_WORKDIR
  --check-references  rebuild every config.references entry, verify its fingerprint, print mesh counts only (D0019 item 4)
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


# ------------------------------------------------------------------------------------------------ D as a yardstick (D0018)
# D0018 decision 1: the degradation rule may make D's power-net copper (DC+, PHASE, DC-) narrower than the reference's own
# minimum power-net width, down to this floor, frozen here and in config.degrade_power_width_floor_m (--verify-freeze
# checks both).  Evidence and reason: research/notes/e008-design.md section "D0018"; research/o003/e008_dev/d_floor/.
# Every other rule applies to D unchanged; W, the candidates and both searches keep the reference's rules.
DEGRADE_POWER_WIDTH_FLOOR_M = 1.5e-3
CELLS_ACROSS_AT_MM = (0.5, 0.25)  # the band solves' 0.5 mm levels and the 0.25 mm production level (BAND, EM_LEVELS)


# ------------------------------------------------------------------------------------------------ E008's per-reference rules
# D0018 model-fix list item 1 (T0317): E008 drops the measured minimum gate/Kelvin-wire length.  O003 scope_in's enumerated
# rules are read as the complete meaning of "design rules at least as strict as the reference's own"; its bondability rule
# bounds gate and Kelvin wires from above only (objective.yaml lines 61-63; T0315 finding 2).  measure_rules sets
# min_signal_wire_length to the reference's shortest signal wire (drc/rules.py line 587), the one rule that stops a twin
# whose gate wires run to the nearest gate copper (T0314 variant R1).  Every upper bound and every other measured rule stays.
DROPPED_MEASURED_RULES = ("min_signal_wire_length",)
KEPT_SIGNAL_UPPER_BOUNDS = ("max_gate_wire_length", "max_kelvin_wire_length", "max_signal_wire_length")


def e008_rules(lay, base=None, overrides: dict | None = None):
    """E008's design rules of one reference (D0018 model-fix list item 1) -> (rules, measure_rules record, rules record).

    drc.rules.measure_rules(lay) with min_signal_wire_length set to None; then ``overrides`` (dev only: E008.yaml
    dev.case4 rule overrides), which may not set a dropped field.  ``base``: generator-housing dev layouts only, whose
    rules are the generator spec's own (``base``) rather than measured ones (unchanged since T0262; their measure_rules
    record still feeds the rule-strictness report); the lower bound is dropped from ``base`` the same way.  The rules
    record (rc.info['rules_record']) states that the field was dropped, the value measure_rules gave it, and the upper
    bounds kept.  Every place the runner builds a reference or dev spec calls this, and the judged-reference loader of
    full() (added before registration) must too.  The candidates, the twin and D all get these rules (D through d_spec),
    so the candidates lose the lower bound too."""
    from moduleforge.drc.rules import measure_rules
    measured, mrec = measure_rules(lay)
    src = measured if base is None else base
    ov = dict(overrides or {})
    if set(ov) & set(DROPPED_MEASURED_RULES):
        raise ValueError(f"an override sets a dropped rule: {sorted(set(ov) & set(DROPPED_MEASURED_RULES))}")
    rules = dataclasses.replace(src, **{k: None for k in DROPPED_MEASURED_RULES}, **ov)
    changed = sorted(f.name for f in dataclasses.fields(rules) if getattr(rules, f.name) != getattr(src, f.name))
    if not set(changed) <= set(DROPPED_MEASURED_RULES) | set(ov):
        raise RuntimeError(f"e008_rules changed {changed}, beyond the dropped fields and the overrides")
    rec = {"function": "e008_run.e008_rules", "decision": "D0018 model-fix list item 1 (T0314 R1, T0315 finding 2)",
           "source": "drc.rules.measure_rules" if base is None else "generator housing spec rules (dev geometry only)",
           "dropped": {k: None for k in DROPPED_MEASURED_RULES},
           "dropped_source_values_m": {k: getattr(src, k) for k in DROPPED_MEASURED_RULES},
           "measured_min_signal_wire_length_m": measured.min_signal_wire_length,
           "overrides": {k: getattr(rules, k) for k in sorted(ov)},
           "kept_upper_bounds_m": {k: getattr(rules, k) for k in KEPT_SIGNAL_UPPER_BOUNDS},
           "fields_changed_from_source": changed}
    return rules, mrec, rec


def d_rules(rules, floor_m: float):
    """D0018 decision 1: ``rules`` with min_width_power replaced by min(the reference's power-net minimum, floor) -> (rules
    of D, the reference's power-net minimum in m).  A reference whose own minimum is below the floor keeps it (D is never
    made wider than the reference allows); every other field is unchanged."""
    from moduleforge.geometry import NETS
    ref_w = {float(rules.width_for(n)) for n in NETS}
    if len(ref_w) != 1:
        raise ValueError(f"power nets with different minimum widths: {sorted(ref_w)}")
    ref_w = ref_w.pop()
    return dataclasses.replace(rules, min_width_power=min(ref_w, float(floor_m))), ref_w


def d_spec(spec, floor_m: float):
    """The spec degrade() builds D under (D0018 decision 1): the reference's spec with ``d_rules`` -> (spec, ref width m)."""
    r, ref_w = d_rules(spec.rules, floor_m)
    return dataclasses.replace(spec, rules=r), ref_w


def narrowest_power_strip_m(lay) -> float:
    """The narrowest strip of power copper (DC+, PHASE, DC-) of ``lay``: per net, the merged copper's largest width w with no
    width problem under the DRC's own predicate (drc.rules._width_problem: the opening with a square of side w loses no area
    and erosion opens no neck), by bisection to 1 um; the minimum over the nets.  Merged per net, because a narrow
    rectangle inside wider copper of the same net is not a strip the current or the lattice sees."""
    from shapely.ops import unary_union

    from moduleforge.drc.rules import _width_problem
    from moduleforge.geometry import NETS
    out = math.inf
    for net in NETS:
        polys = [t.polygon for t in lay.traces if t.net == net]
        if not polys:
            continue
        g = unary_union(polys)
        for poly in getattr(g, "geoms", [g]):
            lo, hi = 0.0, 0.1  # m; no strip is 100 mm wide
            while hi - lo > 1e-6:
                mid = 0.5 * (lo + hi)
                lo, hi = (mid, hi) if _width_problem(poly, mid)[0] is None else (lo, mid)
            out = min(out, lo)
    return out


def _gate_wires(lay) -> list[float]:
    """Lengths (m) of the gate wires of ``lay`` (none for a layout without signal wires or a selftest fake)."""
    return [float(w.length) for w in (getattr(lay, "signal_wires", None) or []) if w.pad == "gate"]


def gate_wire_report(gw: dict) -> dict:
    """T0317 (reported, not gated): the shortest gate wire of the reference, W, D and the DRC-clean _quick_ok samples, now
    that E008's rules carry no lower bound (e008_rules), and how many are shorter than DesignRules.min_wire_length (1.5 mm,
    a placeholder default of drc/rules.py that bounds power wires only, not a cited bondability limit)."""
    from moduleforge.drc.rules import DesignRules
    lim = DesignRules().min_wire_length
    rep = {"placeholder_min_wire_length_m": lim, "gated": False}
    for k, v in gw.items():
        rep[k] = {"n_gate_wires": len(v), "shortest_m": min(v) if v else None,
                  "n_below_placeholder": sum(x < lim for x in v)}
    allv = [x for v in gw.values() for x in v]
    rep["shortest_overall_m"] = min(allv) if allv else None
    rep["any_below_placeholder"] = any(x < lim for x in allv)
    return rep


def band_solve_failures(recs: list[dict], who: str) -> list[str]:
    """T0318 finding 0: the band solves (BAND order) of one layout that are not usable for F1(b)'s definition: L_H not
    finite; no convergence record or a GMRES flag != 0 (l2_layout meta['gmres_flags'], scipy convention 0 = converged; an
    empty list is the dense direct solve); solver_tol_rel_L_max not finite (l2_layout sets inf when Im Z_ii <= 0).  A
    missing key fails closed."""
    out = []
    for lv, r in zip(BAND, recs, strict=True):
        L, fl, tl = r.get("L_H"), r.get("gmres_flags"), r.get("solver_tol_rel_L_max")
        if not _num(L):
            out.append(f"{who} {lv}: L_H {L}")
        if not isinstance(fl, list) or any(int(f) != 0 for f in fl):
            out.append(f"{who} {lv}: not converged (gmres_flags {fl})")
        if not _num(tl):
            out.append(f"{who} {lv}: solver_tol_rel_L_max {tl}")
    return out


def exclude(rc, reason: str, detail: str, stage: str) -> None:
    """D0018 decision 2 (and F1(a) for a TwinError): the reference is excluded and reported with its reason; it gets no
    driver, no rows and no spot check; E008 is INVALID only if no reference remains (at_least_one_counted_reference)."""
    rc.excluded = {"reason": reason, "detail": str(detail), "stage": stage}
    rc.info["excluded"] = rc.excluded


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
    from moduleforge.drc.rules import DesignRules
    fl = cfg.get("degrade_power_width_floor_m")
    add("degrade_power_width_floor", fl == DEGRADE_POWER_WIDTH_FLOOR_M and fl >= DesignRules().min_trace_width,
        f"config {fl} m, runner {DEGRADE_POWER_WIDTH_FLOOR_M} m, generator default minimum width "
        f"{DesignRules().min_trace_width} m (D0018)")
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
    # F6(c) Picard record (T0307 finding 0): solve_layout_level's meta drops it, the ThermalResult's meta keeps it
    # (thermal_fv.solve_steady: the last max |T_{n+1} - T_n|, K; k(T) laws, constant_k False, so a real Picard residual)
    return {"level": job["level"], "tj": [float(v[f"die{i}.tj_max"]) for i in range(len(lay.dies))],
            "energy_balance": float(m["energy_balance"]), "n_cells": int(m["n_cells"]), "peak_GB": _rss_gb(),
            "picard_iters": int(m["picard_iters"]), "picard_dT_K": float(r["result"].meta["picard_dT"]),
            "solver_wall_s": float(m["wall_time_s"]), "fingerprint": lay.fingerprint(), "threads": _prov()}


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
    excluded: dict | None = None  # D0018: {"reason", "detail", "stage"} when the reference is excluded (no rows)


DEFAULT_STACK = "Al2O3_default_dbc"


# stack-type signature rounding (T0310 finding 3): thicknesses to 1 nm, conductivities to 9 significant digits
SIG_THICKNESS_QUANTUM_M = 1e-9
SIG_K_SIGNIFICANT_DIGITS = 9


def _die_thicknesses(dies) -> list[list[int]]:
    """The sorted set of (thickness, attach_thickness) over ``dies``, each rounded to integer nanometres (_sig_nm, T0310
    finding 3), so duplicates, order and float rounding do not matter."""
    return [list(t) for t in sorted({(_sig_nm(d.thickness), _sig_nm(d.attach_thickness)) for d in dies})]


def _sig_nm(t) -> int:
    """A thickness in the stack-type signature (T0310 finding 3): integer nanometres, round(t / 1 nm) with Python's
    round-half-even.  Two thicknesses that differ only by float rounding (2D_Case_4 stores 180 um as
    0.00017999999999999998 m) give the same integer; a 1 nm or larger difference gives a different one.  A NaN or
    infinite thickness raises (fail closed: no stack type, the reference stops)."""
    return int(round(float(t) / SIG_THICKNESS_QUANTUM_M))


def _sig_k(k) -> str:
    """A conductivity in the stack-type signature (T0310 finding 3): 9 significant digits, format '.8e' (correctly rounded
    decimal; float relative rounding is ~1e-16, far below the 5e-9 relative step of the 9th digit)."""
    return format(float(k), f".{SIG_K_SIGNIFICANT_DIGITS - 1}e")


def _stack_signature(stack, dies) -> str:
    """Every thermal input of a LayerStack and of the dies on it: the substrate layers, then the die-attach and die
    layers (geometry/stack.py keeps these two outside ``layers``; T0305 finding 0), each by name, material (its k(T) law,
    stack.K_LAWS), thickness and k at 300 K; then the sorted set of per-die (Die.thickness, Die.attach_thickness), which
    are the thicknesses thermal_fem and thermal_layout actually use for the die and its attach (T0308 finding 1; the
    stack's die / die_attach thickness is only their default and thermal_layout's edge-cell size).  sigma (electrical)
    and the ``kind`` label are not thermal inputs and are left out.  Rounding rule (T0310 finding 3): every thickness
    (layer and per-die) as integer nanometres (_sig_nm), every conductivity to 9 significant digits (_sig_k), so a
    stack that differs from another only by float rounding has the same signature."""
    las = [*stack.layers, stack.die_attach, stack.die]
    return json.dumps({"layers": [[str(la.name), str(la.material), _sig_nm(la.thickness), _sig_k(la.k)] for la in las],
                       "die_thickness_attach_nm": _die_thicknesses(dies)})


def _stack_type(stack, dies) -> str:
    """F6(e) stack type: DEFAULT_STACK iff the signature equals C004's default Al2O3 DBC stack (default_dbc_stack())
    with dies of the default thicknesses (geometry Die defaults DIE_THICKNESS, DIE_ATTACH_THICKNESS), else 'other:' +
    the first 12 hex digits of the signature's sha256 (one spot check per distinct type).  ``dies``: every object
    with .thickness and .attach_thickness that a solve of the reference can carry (dev_reference: the reference
    layout's dies and its derivative spec's DieSpec, which every twin and candidate is built with)."""
    from moduleforge.geometry import default_dbc_stack
    from moduleforge.geometry.layout import Die
    sig = _stack_signature(stack, dies)
    return DEFAULT_STACK if sig == _stack_signature(default_dbc_stack(), [Die(0.0, 0.0, 1.0, 1.0, "HS", {})]) \
        else "other:" + hashlib.sha256(sig.encode()).hexdigest()[:12]


def dev_reference(name: str, cfg: dict) -> RefCtx:
    """Development geometry only (F3): 2D_Case_4 (O006 pilot geometry) or a generator-housing layout from the dev seed."""
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
        from moduleforge.drc.rules import DesignRules
        dflt = DesignRules()
        ov = {k: (getattr(dflt, k) if v == "default" else v) for k, v in a.get("rule_overrides", {}).items()}
        rules, rec, rrec = e008_rules(lay, overrides={"max_gate_wire_length": a["max_signal_wire_m"],
                                                      "max_kelvin_wire_length": a["max_signal_wire_m"], **ov})
        rel = lambda r: tuple(v * 1e-3 for v in (r[0] - 2, r[1] - 3, r[2] - 2, r[3] - 3))  # noqa: E731
        spec = D.spec_from_layout(lay, rules, a["keepout_nets"], extra_pads={k: rel(v) for k, v in a["extra_pads_mm"].items()})
        rc = RefCtx("2D_Case_4", "dev", spec, lay, info={"measured_rules": rec, "rules_record": rrec})
    else:
        m = re.fullmatch(r"gen(\d)_(\d+)", name)
        spec = D.halfbridge_housing_spec(int(m[1]))
        lay = D.generate(spec, int(m[2]) + 1, int(cfg["dev"]["dev_seed"]))[int(m[2])]
        rules, rec, rrec = e008_rules(lay, base=spec.rules)
        spec = dataclasses.replace(spec, rules=rules)
        rc = RefCtx(f"housing70x40_{name}", "dev", spec, lay, info={"measured_rules": rec, "rules_record": rrec})
    bp = rc.reference.baseplate_outline.bounds
    rc.area_m2 = (bp[2] - bp[0]) * (bp[3] - bp[1])
    rc.stack_type = _stack_type(rc.spec.stack, [*rc.reference.dies, rc.spec.die])
    return rc


# ------------------------------------------------------------------------------------------------ judged references (D0019)
# D0019 (founder session 2026-11-12) item 1: O003's judged references are D0010's public fallback, PowerSynth 2D_Case_2R and
# 2D_Case_6, labelled 'public benchmarks, low power, indicative'.  They are rebuilt only through the frozen T0263 script
# (research/scripts/o003_powersynth_references.py, sha256 in config.freeze), imported by path as dev_reference imports
# o006_case4_layout.py; the script is never edited here.
RECON_SCRIPT = "research/scripts/o003_powersynth_references.py"
PUBLIC_LABEL = "public benchmarks, low power, indicative"
ENTRY_FIELDS = ("reference_id", "kind", "vault_id", "reconstruction_sha256", "sic_mosfet_half_bridge",
                "separate_antiparallel_diode_dies", "admissible", "reason", "decided_at", "L_term_H", "L_term_source",
                "on_grid_0p5mm", "snapping_check", "keepout_nets", "label")


class ReferenceRefused(RuntimeError):
    """A judged reference whose rebuilt reconstruction does not match its config.references entry (fingerprint, grid
    flag, kind or a missing field): the run is void (F3), nothing about the reference is computed."""


class RulesGuardError(RuntimeError):
    """Review T0319 finding 0: a spec that was not built by e008_rules (or still carries a dropped rule) reached prepare()."""


def rules_guard_failures(rc) -> list[str]:
    """T0319 finding 0: prepare() refuses a reference whose rc.info has no rules_record written by e008_rules (dropping
    exactly DROPPED_MEASURED_RULES) or whose rc.spec.rules still sets a dropped rule (min_signal_wire_length)."""
    rr = (rc.info or {}).get("rules_record")
    out = []
    if not isinstance(rr, dict) or rr.get("function") != "e008_run.e008_rules":
        out.append(f"{rc.rid}: rc.info has no rules_record from e008_rules ({type(rr).__name__})")
    elif rr.get("dropped") != {k: None for k in DROPPED_MEASURED_RULES}:
        out.append(f"{rc.rid}: rules_record drops {rr.get('dropped')}, want {list(DROPPED_MEASURED_RULES)}")
    rules = getattr(rc.spec, "rules", None)
    for k in DROPPED_MEASURED_RULES:
        v = getattr(rules, k, "missing")
        if v is not None:
            out.append(f"{rc.rid}: spec.rules.{k} = {v} (must be None, D0018 item 1)")
    return out


def recon_module():
    """The frozen T0263 reconstruction script, imported by path (never edited, never copied; its sha256 is in config.freeze
    and freeze_checks verifies it before any reference is loaded)."""
    import importlib.util
    name = "o003_powersynth_references_e008"
    if name in sys.modules:
        return sys.modules[name]
    sp = importlib.util.spec_from_file_location(name, ROOT / RECON_SCRIPT)
    m = importlib.util.module_from_spec(sp)
    sys.modules[sp.name] = m
    sp.loader.exec_module(m)
    return m


def rebuild_reconstruction(entry: dict, recon=None):
    """Rebuild one judged reference through the frozen script and check it against its entry BEFORE anything else ->
    (reconstruction Layout, {grid_mm: SnapResult}).  Refuses (ReferenceRefused, the run is void) on: a missing entry field,
    a kind other than public (the customer/vault loader does not exist; D0010: the public set is the one fixed by D0019),
    a fingerprint different from entry['reconstruction_sha256'], or a 0.5 mm grid flag that the snap records contradict.
    Nothing but L0 geometry is touched (D0019 item 4)."""
    miss = [k for k in ENTRY_FIELDS if k not in entry]
    if miss:
        raise ReferenceRefused(f"config.references entry {entry.get('reference_id')} lacks {miss}")
    rid = entry["reference_id"]
    if entry["kind"] != "public" or entry["vault_id"] is not None:
        raise ReferenceRefused(f"{rid}: kind {entry['kind']} / vault {entry['vault_id']}: only public reconstructions load "
                               "here (D0010, D0019)")
    recon = recon or recon_module()
    lay, snaps = recon.snapped(rid)
    fp = lay.fingerprint()
    if fp != entry["reconstruction_sha256"]:
        raise ReferenceRefused(f"{rid}: reconstruction fingerprint {fp} != config {entry['reconstruction_sha256']}: the run "
                               "is void (F3)")
    on_grid = not snaps[0.5].records
    if on_grid != bool(entry["on_grid_0p5mm"]):
        raise ReferenceRefused(f"{rid}: snap records say on_grid_0p5mm {on_grid}, config says {entry['on_grid_0p5mm']}")
    return lay, snaps


def judged_reference(entry: dict, cfg: dict, recon=None) -> RefCtx:
    """D0019: one judged reference from its config.references entry.  rebuild_reconstruction first (fingerprint check;
    a mismatch refuses), then the spec exactly as for the dev references: e008_rules on the reconstruction (no overrides:
    the reference's own measured rules less min_signal_wire_length, D0018 item 1 / D0019 item 5) and spec_from_layout
    with the entry's keep-out nets.  Off the 0.5 mm grid (not the case for D0019's set) the snapped-to-0.25 mm layout
    and the entry's snapping-check values are required (s_ref, Run.s_ref_of); missing values refuse."""
    from moduleforge.generate import derivative as D
    lay, snaps = rebuild_reconstruction(entry, recon)
    rid = entry["reference_id"]
    rules, rec, rrec = e008_rules(lay)
    spec = D.spec_from_layout(lay, rules, entry["keepout_nets"])
    rc = RefCtx(rid, entry["kind"], spec, lay, on_grid=bool(entry["on_grid_0p5mm"]), L_term_H=float(entry["L_term_H"]),
                admissible=bool(entry["admissible"]),
                info={"measured_rules": rec, "rules_record": rrec, "label": entry["label"],
                      "reference_entry": {k: entry[k] for k in ENTRY_FIELDS if k != "keepout_nets"},
                      "f3_declared_deviation": deviation_tag(cfg)})
    if not rc.on_grid:
        sc = entry.get("snapping_check") or {}
        if not isinstance(sc, dict) or not all(_num(sc.get(k)) for k in ("L_snapchk0125_H", "L_snapchk05_H")):
            raise ReferenceRefused(f"{rid}: off the 0.5 mm grid but the entry has no snapping-check values")
        rc.snap025 = snaps[0.25].layout
        rc.info.update(snapchk0125_H=float(sc["L_snapchk0125_H"]), snapchk05_H=float(sc["L_snapchk05_H"]))
    bp = lay.baseplate_outline.bounds
    rc.area_m2 = (bp[2] - bp[0]) * (bp[3] - bp[1])
    rc.stack_type = _stack_type(rc.spec.stack, [*rc.reference.dies, rc.spec.die])
    return rc


def deviation_tag(cfg: dict) -> str:
    """The one-line statement every verdict of E008 carries (D0019 item 2, config.f3_declared_deviation.statement)."""
    dv = cfg.get("f3_declared_deviation") or {}
    return str(dv.get("statement") or "MISSING: config.f3_declared_deviation (D0019 item 2)")


def _band_unknowns(recon, lay, level: str) -> int:
    """l2_layout unknowns of one band level of ``lay``: the frozen script's mesh-only l2_unknowns (lattice, Grid, wire
    filaments; no coupling, no solve) under exactly child_em's per-level mesh constants (EM_LEVELS), restored after."""
    from moduleforge.solvers import l2_layout as L
    names = ("CELL", "LAYERS_TOP", "LAYERS_BACK", "LAYERS_BASE", "WIRE_EDGES")
    saved = {k: getattr(L, k) for k in names}
    cell, layers, edges = EM_LEVELS[level]
    try:
        L.CELL = (cell * 1e-3,) + tuple(L.CELL[1:])
        for attr, n in zip(names[1:4], layers, strict=True):
            setattr(L, attr, (n,) + tuple(getattr(L, attr)[1:]))
        L.WIRE_EDGES = (tuple(edges),) + tuple(L.WIRE_EDGES[1:])
        return int(recon.l2_unknowns(lay, refinement=0)["n_unknowns"])
    finally:
        for k, v in saved.items():
            setattr(L, k, v)


def check_references(cfg: dict, out_path: str | None = None, recon=None) -> int:
    """--check-references (D0019 item 4): for every config.references entry, rebuild through the frozen script, verify
    the fingerprint (rebuild_reconstruction) and count mesh sizes only: l2_layout unknowns of every band level (0.25 mm
    and the four 0.5 mm-cell levels), scikit-fem DOFs per level 0-2 under the frozen rule (thermal_fem.estimate_dofs,
    grid counts only), and the F6(e) finite-volume box cells (thermal_layout.build_layout_grid) at level 1 and 2, built,
    and level 3 = level 2 x 8 (the runner's convention, Run.size; the level-3 box itself is not built here, its x8 step is
    checked on 1 -> 2).  No spec, rule measurement, twin, degradation, L1, solve or search.  Exit 0 iff every fingerprint
    matches."""
    from moduleforge.solvers import thermal_layout as TL
    recon = recon or recon_module()
    rule = rule_from(cfg["fem_rule"])
    out, ok = {"rule": "D0019 item 4: rebuild + fingerprint + mesh counts only", "references": {}}, True
    for entry in cfg["references"]:
        rid = entry.get("reference_id")
        try:
            lay, snaps = rebuild_reconstruction(entry, recon)
        except ReferenceRefused as e:
            ok = False
            out["references"][rid] = {"fingerprint_ok": False, "error": str(e)}
            continue
        t0 = time.perf_counter()
        em = {lv: _band_unknowns(recon, lay, lv) for lv in BAND}
        fem = [int(FEM().estimate_dofs(lay, rule, lv)) for lv in (0, 1, 2)]
        fv1 = int(np.prod(TL.build_layout_grid(lay, 1).shape))
        fv2 = int(np.prod(TL.build_layout_grid(lay, 2).shape))
        bp = lay.baseplate_outline.bounds
        out["references"][rid] = {
            "fingerprint_ok": True, "fingerprint": lay.fingerprint(), "on_grid_0p5mm": not snaps[0.5].records,
            "baseplate_area_m2": (bp[2] - bp[0]) * (bp[3] - bp[1]), "l2_layout_unknowns": em,
            "fem_dofs_frozen_rule": fem, "fv_cells": [fv1, fv2, fv2 * 8], "fv_level_steps": [fv2 / fv1],
            "fv_cells_note": "levels 1 and 2 built (box cells, voids included, the --plan convention); level 3 = level 2 x 8",
            "wall_s": round(time.perf_counter() - t0, 2), "peak_rss_GB": round(_rss_gb(), 3)}
        log(f"{rid}: fingerprint ok; l2_layout unknowns {em}; scikit-fem DOFs L0-2 {fem}; FV cells L1-3 "
            f"{[fv1, fv2, fv2 * 8]}")
    print(json.dumps(out, indent=1))
    if out_path:
        Path(out_path).write_text(json.dumps(out, indent=1) + "\n")
    return 0 if ok and out["references"] else 1


def prepare(rc: RefCtx, cfg: dict, n_quick: int, quick_seed: int, with_l1: bool = True) -> RefCtx:
    """Fail fast, before any l2_layout solve (L0/L1 only): twin W and degraded copy D, _quick_ok false rejections on a
    fixed sealed sample, rule strictness, the midpoint record and the twin-copper symmetric difference.  Reported, not
    gated, except that W and D must exist.  D0018: D is built under ``d_spec`` (power-net width floor
    config.degrade_power_width_floor_m; every other rule the reference's), and ``info['D_rule']`` records the rule, D's
    narrowest power strip and the lattice cells across it.  A TwinError or DegradeError stops (excludes) that reference,
    not the run (``exclude``; Run.drive gives it no driver, assemble_rows no rows, evaluate reports it)."""
    from moduleforge.drc.rules import check
    from moduleforge.generate import derivative as D
    from moduleforge.generate import twin as W
    bad = rules_guard_failures(rc)  # review T0319 finding 0: only specs built by e008_rules reach the twin
    if bad:
        raise RulesGuardError("; ".join(bad))
    t0 = time.perf_counter()
    try:
        rc.twin, p, rc.twin_rec = W.twin(rc.reference, rc.spec, with_l1=with_l1)
    except W.TwinError as e:
        rc.info["fail_fast"] = f"TwinError: {e}"
        exclude(rc, "TwinError", e, "prepare")
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
    floor = float(cfg["degrade_power_width_floor_m"])
    dsp, ref_w = d_spec(rc.spec, floor)
    rc.info["D_rule"] = {"decision": "D0018", "floor_m": floor, "reference_min_width_power_m": ref_w,
                         "D_min_width_power_m": dsp.rules.min_width_power, "narrowed_below_reference": None,
                         "narrowest_power_strip_m": None, "cells_across": None}
    t0 = time.perf_counter()
    try:
        rc.D, rc.d_rec = W.degrade(rc.twin, dsp, with_l1=with_l1)
    except W.DegradeError as e:
        rc.info["fail_fast"] = f"DegradeError: {e}"
        rc.d_rec = getattr(e, "record", {})
        exclude(rc, "DegradeError", e, "prepare")
    rc.info["degrade_s"] = time.perf_counter() - t0
    rc.info["walk"] = (rc.d_rec or {}).get("walk")
    if rc.D is not None and hasattr(rc.D, "traces"):  # a Layout (the selftest's fake layouts carry no geometry)
        w = narrowest_power_strip_m(rc.D)
        ref_viol = sorted({v.rule for v in check(rc.D, rc.spec.rules)})
        rc.info["D_rule"].update(
            narrowest_power_strip_m=w, narrowed_below_reference=w < ref_w - 1e-6,
            cells_across={f"{h:g}mm": w / (h * 1e-3) for h in CELLS_ACROSS_AT_MM},
            drc_clean_under_D_rules=not check(rc.D, dsp.rules), rules_violated_under_reference_rules=ref_viol)
    rng = np.random.default_rng(quick_seed)
    cx = D._Ctx(rc.spec) if n_quick else None
    n_clean = n_rej = 0
    gw = {"reference": _gate_wires(rc.reference), "twin": _gate_wires(rc.twin), "D": _gate_wires(rc.D),
          "drc_clean_samples": []}
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
            gw["drc_clean_samples"] += _gate_wires(lay)
    rc.info["gate_wires"] = gate_wire_report(gw)
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


def _worst(values) -> float:
    """NaN-aware maximum for the F6(c) and F6(e) maxima: NaN if any value is NaN, else the maximum (+inf stays +inf);
    0.0 for no values.  Python's max() drops a NaN that is not first (T0308 finding 5)."""
    vals = [float(v) for v in values]
    return math.nan if any(math.isnan(v) for v in vals) else max(vals, default=0.0)


def _a3_die(p: list, r: list, g: dict) -> float:
    """F6(e) A3 on one die: max_gci_consistency of the scikit-fem levels 0-2 ``p`` against the finite-volume levels 1-3
    ``r`` (floor a3_floor_K, cap a3_ref_gci_cap_K).  A NaN or infinite Tj on either side gives NaN, which fails the
    per-type check and, through _worst, the aggregate (T0310 finding 2); mfos.metrics would raise on it instead and stop
    evaluate with no F6(e) check written."""
    vals = [float(v) for v in (*p, *r)]
    if not all(math.isfinite(v) for v in vals):
        return math.nan
    return MX.max_gci_consistency(*([v] for v in p), *([v] for v in r), floor=g["a3_floor_K"],
                                  ref_gci_cap=g["a3_ref_gci_cap_K"])


def _within(v: float, tol: float) -> bool:
    """v <= tol for a finite v only: a NaN or infinite value fails the check (T0307 finding 0, T0308 finding 5)."""
    return math.isfinite(v) and v <= tol


# measure_rules keys that match the guard's words but are not a spacing between nets: die_spacing is the die-to-die
# placement distance (T0307 finding 4), which the report does not cover
NOT_NET_SPACING = ("die_spacing",)


def rule_strictness(mr: dict) -> dict:
    """T0280 report (reported, not gated) from the record of drc.rules.measure_rules, whose spacing keys are 'gap_*'
    (gap_dcp_phase, gap_phase_dcm, gap_dcp_dcm, gap_signal_*, gap_other_min; m; T0305 finding 1): every measured class
    beside the reference's smallest DC-link gap (min of DC_LINK_GAPS); flag_2x when the class is more than twice that gap
    (a reference feature that, used as a rule, narrows the search).  Raises if the record holds a measured net gap,
    spacing or clearance value (NOT_NET_SPACING excepted) and the report would be empty, so a renamed key cannot
    silently empty it again."""
    gaps = {k: float(v) for k, v in mr.items() if k.startswith("gap_") and _num(v)}
    link = min([v for k, v in gaps.items() if k in DC_LINK_GAPS] or [math.nan])
    rep = {k: {"value_m": v, "smallest_dc_link_gap_m": link, "flag_2x": bool(math.isfinite(link) and v > 2 * link)}
           for k, v in gaps.items()}
    if not rep and any(re.search(r"gap|spacing|clearance", k) and k not in NOT_NET_SPACING and _num(v)
                       for k, v in mr.items()):
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
        self.spot_none: list[str] = []  # F6(e): non-default stack types with no admissible reference (no spot check)
        self.l1_cache: dict[str, float] = {}
        self.size_cache: dict[tuple, int] = {}
        self.d_failed: dict[str, dict] = {}  # T0318 finding 0: references whose D/W band solves failed (INVALID)

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

    def d_definition(self, refs: list[RefCtx]) -> list[RefCtx]:
        """D0018 decision 2: the band solves of D and W of every admissible reference, then F1(b)'s definition at the
        conservative end of the band; a miss excludes the reference (``exclude``) and drops its drivers -> the remaining."""
        g = self.cfg["gates"]
        jobs = {rc.rid: (self.drivers[(rc.rid, "main")].em_jobs(rc.D, BAND), self.drivers[(rc.rid, "main")].em_jobs(rc.twin, BAND))
                for rc in refs if rc.admissible}
        flat = [j for a, b in jobs.values() for j in a + b]
        while True:
            self.sched.submit(flat)
            if all(Scheduler.done(j) for j in flat):
                break
            if not self.sched.queue and not self.sched.running:
                raise RuntimeError("D definition: band solves pending but no job queued")
            self.sched.step()
        out = []
        for rc in refs:
            if rc.rid in jobs:
                rd, rw = ([Scheduler.done(j) for j in js] for js in jobs[rc.rid])
                bd, bw = [r.get("L_H", math.nan) for r in rd], [r.get("L_H", math.nan) for r in rw]
                with np.errstate(all="ignore"):
                    R = bd[0] / bw[0] if bw[0] != 0 else math.nan
                    try:
                        e = MX.ratio_band_estimate(bd, bw)
                    except (ValueError, ZeroDivisionError, FloatingPointError) as ex:
                        e = math.nan
                        rc.info["D_definition_e_R_error"] = str(ex)
                bad = band_solve_failures(rd, "D") + band_solve_failures(rw, "W")
                if not (math.isfinite(R) and math.isfinite(e)):
                    bad.append(f"R {R} or e_R {e} not finite")
                rc.info["D_definition"] = {"R_D": R, "e_R_D": e, "conservative": R * (1 - 2 * e),
                                           "threshold": g["degrade_ratio"], "L1_ratio": (rc.d_rec or {}).get("l1_ratio"),
                                           "band_failures": bad}
                if bad:
                    # T0318 finding 0: a solver failure is not "no valid D exists": F1b_D_definition fails for this
                    # reference (INVALID, as before T0316); no exclusion, and nothing more is solved (Run.drive stops)
                    self.d_failed[rc.rid] = rc.info["D_definition"]
                    out.append(rc)
                    continue
                if not R * (1 - 2 * e) >= g["degrade_ratio"]:  # a finite, converged miss at the conservative end
                    exclude(rc, "D_misses_1p25_in_L_sub", f"L_sub(D)/L_sub(W) {R:.5f} (1 - 2 e_R {e:.5f}) = "
                            f"{R * (1 - 2 * e):.5f} < {g['degrade_ratio']}", "drive")
                    self.excluded[rc.rid] = rc.excluded
                    for ns in ("main", "control"):
                        self.drivers.pop((rc.rid, ns), None)
                    continue
            out.append(rc)
        return out

    def drive(self, refs: list[RefCtx], seeds: dict, scfg: dict) -> None:
        self.drivers: dict[tuple, Driver] = {}
        self.excluded = {rc.rid: rc.excluded for rc in refs if rc.excluded is not None}  # prepare(): TwinError, DegradeError
        refs = [rc for rc in refs if rc.excluded is None]
        for rc in refs:
            if rc.twin is None or rc.D is None:
                raise RuntimeError(f"{rc.rid}: no W or D but not excluded (fail_fast_twin_and_D)")
            if not rc.on_grid and rc.snap025 is None:
                raise RuntimeError(f"{rc.rid}: off the 0.5 mm grid but no snap025 layout (s_ref needs it)")
            ctx = save_ctx(rc, self.root / rc.rid)
            for ns in ("main", "control"):
                self.drivers[(rc.rid, ns)] = Driver(rc, ns, seeds[(rc.rid, ns)], self.root / rc.rid, ctx, scfg, self)
        # D0018 decision 2: F1(b)'s definition of D, L_sub(D)/L_sub(W) (1 - 2 e_R(D, W)) >= degrade_ratio, from D's and W's
        # band solves (the same result files the drivers read), before any search, spot check or K1: a reference whose D
        # misses is excluded (no driver, no rows) and reported, not INVALID
        refs = self.d_definition(refs)
        if self.d_failed:  # T0318 finding 0: the run is INVALID (F1b_D_definition fails in evaluate); no search is run
            log(f"D definition: band solver failures on {sorted(self.d_failed)}: F1b_D_definition fails, run INVALID")
            return
        # F6(e): one spot-check reference per non-default stack type, the first ADMISSIBLE one of that type in reference
        # order (T0305 finding 0: one per type; T0307 finding 1, T0308 finding 2: an inadmissible first reference must
        # not take the type's spot check from a later admissible one).  A type with no admissible reference gets none:
        # it is listed in spot_none and reported, not failed (D0010: only admissible references are in the reference
        # set, an inadmissible one contributes no rows to the verdict)
        self.spot_refs, self.spot_none = {}, []
        for st in sorted({rc.stack_type for rc in refs} - {DEFAULT_STACK}):
            rid = next((rc.rid for rc in refs if rc.stack_type == st and rc.admissible), None)
            if rid is None:
                self.spot_none.append(st)
            else:
                self.spot_refs[st] = rid
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
    if getattr(run, "d_failed", None):  # T0318 finding 0: Run.drive stopped after D's definition (INVALID); no rows
        return rows, extra
    for rc in refs:
        rid = rc.rid
        if rc.excluded is not None:  # D0018 / F1(a): an excluded reference has no rows; evaluate reports it
            continue
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
                             "energy_balance_max": _worst(rec["energy_balance"]),
                             "picard_residual_max_K": _worst(p["residual_K"] for p in rec["picard"]),
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
    if run.d_failed:
        return _evaluate_d_failed(run, refs, cfg, checks, ck)
    # no reference row at all (every reference excluded, D0018): nothing is counted, the metrics below are NaN and
    # at_least_one_counted_reference fails (INVALID)
    per = MX.headroom_per_reference(rows, "L_sub_H", dict(mp)) if any(r["kind"] == "reference" for r in rows) else {}
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
        if not rc.admissible or rc.excluded is not None:
            continue
        rec, ex = per[rid], extra[rid]
        rm, rcn, bands = ex["main"], ex["control"], ex["bands"]
        counted += bool(rec["counted"])
        fpw, fpd = rc.twin.fingerprint(), rc.D.fingerprint()
        # F1(b) definition of D, conservative end of its band, before K1 is read
        R_D = bands[fpd][0] / bands[fpw][0]
        e_D = MX.ratio_band_estimate(bands[fpd], bands[fpw])
        bad = (rc.info.get("D_definition") or {}).get("band_failures") or []
        ck(f"F1b_D_definition:{rid}", not bad and R_D * (1 - 2 * e_D) >= g["degrade_ratio"], R_D * (1 - 2 * e_D),
           g["degrade_ratio"], f"R_D={R_D:.5f} e_R(D,W)={e_D:.5f} band failures {bad[:5]} "
           f"walk={json.dumps(rc.info.get('walk'), default=str)[:300]}")
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
        bad_a, eb_vals, pc_vals = [], [], []
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
            eb_vals += list(r["energy_balance"])
            pc_vals += [p["residual_K"] for p in r["picard"]]
        for h in run.cal[rid]["history"]:
            eb_vals.append(h["energy_balance"])
            pc_vals.append(h["picard_residual_K"])
        # F6(c) "on every thermal solve": the F6(e) finite-volume spot-check solves of this reference too, energy balance
        # (T0305 finding 5) and the Picard residual child_fv records from the ThermalResult (T0307 finding 0), so the
        # gate is shown on them, not implied by solve_layout_level's default picard_tol; a record without it is NaN
        fv = [Scheduler.done(j) for j in run.spot_jobs(run.drivers[(rid, "main")])]
        eb_vals += [f["energy_balance"] for f in fv]
        pc_vals += [f.get("picard_dT_K", math.nan) for f in fv]
        # NaN-aware maxima (T0308 finding 5): a NaN or infinite value fails F6(c)
        worst_eb, worst_pc = _worst(eb_vals), _worst(pc_vals)
        ck(f"F6a_own_three_grids:{rid}", not bad_a, len(bad_a), 0, bad_a[:10])
        ck(f"F6c_energy_balance:{rid}", _within(worst_eb, g["energy_tol"]), worst_eb, g["energy_tol"],
           f"{len(eb_vals)} values, {len(fv)} finite-volume spot-check solves included; NaN/inf fails")
        ck(f"F6c_picard:{rid}", _within(worst_pc, g["picard_tol_K"]), worst_pc, g["picard_tol_K"],
           f"{len(pc_vals)} values, {len(fv)} finite-volume spot-check solves included; NaN/inf fails")
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
        if rid not in extra:  # cannot happen (spot references are admissible, Run.drive); fails safe if it does
            ck(f"F6e_stack_type_spot_check:{st}", False, detail=f"spot-check reference {rid} has no rows")
            a3s[st] = math.inf
            continue
        fv = [Scheduler.done(j) for j in run.spot_jobs(run.drivers[(rid, "main")])]
        th = next(t["record"] for t in extra[rid]["main"].rows["thermal"] if t["role"] == "reference")
        a3s[st] = _worst(_a3_die([th["tj"][lv][i] for lv in range(3)], [f["tj"][i] for f in fv], g)
                         for i in range(len(th["tj"][0])))  # per die: fem levels 0-2 vs FV levels 1-3
        ck(f"F6e_stack_type_spot_check:{st}", _within(a3s[st], g["a3_max"]), a3s[st], g["a3_max"], f"reference {rid}")
    # a non-default type with no admissible reference: no spot check and no per-type check; reported here (rep F6e with
    # reference None) and in the aggregate's detail, not failed (Run.drive)
    none = {st: {"reference": None, "a3": None, "status": "no admissible reference of this stack type: no spot check "
                 "(not gated; its references contribute no rows)"} for st in run.spot_none}
    if a3s:
        ck("F6e_stack_type_spot_check", all(_within(v, g["a3_max"]) for v in a3s.values()), _worst(a3s.values()),
           g["a3_max"], json.dumps({"checked": {st: [run.spot_refs[st], v] for st, v in a3s.items()},
                                    "no_admissible_reference": run.spot_none}, default=str))
        met["stack_type_a3"] = _worst(a3s.values())
    else:
        ck("F6e_stack_type_spot_check", True, detail="no admissible reference off C004's default Al2O3 DBC stack: not "
           f"required; types without an admissible reference: {run.spot_none}")
    if a3s or none:
        rep["F6e"] = {st: {"reference": run.spot_refs[st], "a3": v, "status": "checked"} for st, v in a3s.items()} | none
    # D0018: excluded references (TwinError / DegradeError in prepare, D's definition missed in Run.drive), with reasons;
    # every other reference reached the drive with W and D (fail_fast_twin_and_D); F1(b)'s definition holds on all of them
    exc = {rc.rid: rc.excluded for rc in refs if rc.excluded is not None}
    rep["excluded"] = exc
    live = [rc for rc in refs if rc.excluded is None]
    ck("fail_fast_twin_and_D", all(rc.twin is not None and rc.D is not None for rc in live) and
       all(set(e) >= {"reason", "detail", "stage"} for e in exc.values()), len(exc), None,
       json.dumps({rid: [e["reason"], e["stage"], e["detail"][:200]] for rid, e in exc.items()}))
    dd = [c for c in checks if c["name"].startswith("F1b_D_definition:")]
    ck("F1b_D_definition", all(c["passed"] for c in dd), len(dd), None,
       f"{len(dd)} counted-path references checked; excluded for D's definition: "
       f"{sorted(r for r, e in exc.items() if e['reason'] != 'TwinError')}")
    ck("at_least_one_counted_reference", counted >= 1, counted, 1, f"excluded: {sorted(exc)}")
    met["n_counted_references"] = float(counted)
    met["n_excluded_references"] = float(len(exc))
    return met, checks, rep


def _evaluate_d_failed(run: Run, refs: list[RefCtx], cfg: dict, checks: list[dict], ck) -> tuple[dict, list[dict], dict]:
    """evaluate() after Run.drive stopped on a band solver failure in D's definition (T0318 finding 0): F1b_D_definition
    fails for each such reference and in aggregate (INVALID, as before T0316); the failing references are not excluded;
    no search ran, so nothing is counted and every metric is NaN."""
    g = cfg["gates"]
    for rid, dd in sorted(run.d_failed.items()):
        ck(f"F1b_D_definition:{rid}", False, dd.get("conservative"), g["degrade_ratio"],
           f"band solver failure, not an exclusion: {dd.get('band_failures', [])[:8]}")
    exc = {rc.rid: rc.excluded for rc in refs if rc.excluded is not None}
    live = [rc for rc in refs if rc.excluded is None]
    ck("fail_fast_twin_and_D", all(rc.twin is not None and rc.D is not None for rc in live) and
       all(set(e) >= {"reason", "detail", "stage"} for e in exc.values()), len(exc), None,
       json.dumps({rid: [e["reason"], e["stage"], e["detail"][:200]] for rid, e in exc.items()}))
    ck("F1b_D_definition", False, len(run.d_failed), 0, f"band solver failures on {sorted(run.d_failed)} (INVALID); "
       f"excluded: {sorted(exc)}")
    ck("at_least_one_counted_reference", False, 0, 1, "no search ran: D's definition failed on a solver failure")
    met = {e["metric"]: math.nan for e in metric_entries(cfg)}
    met.update(n_counted_references=0.0, n_excluded_references=float(len(exc)))
    return met, checks, {"excluded": exc, "D_definition_solver_failures": run.d_failed}


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


def fake_world(scenario: str, hot: set | None = None, fv_bad: set | None = None, fv_eb_bad: set | None = None,
               fv_eb_nan: set | None = None, fv_pc_bad: set | None = None, fv_pc_missing: set | None = None,
               fv_tj_nan: set | None = None, em_nan: set | None = None, em_nc: set | None = None):
    """Deterministic fake solvers keyed by fingerprint.  'twin_best': every candidate is above the twin (twin rule);
    otherwise candidates reach ~0.70 of the twin's L_sub ('levelled': L1 floor reached in the first n_first).  Planted
    faults, filled by the selftest before the drive: ``hot`` fingerprints get +10 K on die 0 at every scikit-fem level
    (fails the conservative test by > 8 K); ``fv_bad`` references get +5 K on every die at every FV level (F6(e) fails);
    ``fv_eb_bad`` references' FV solves report an energy balance of 1e-3 (F6(c) fails); ``fv_eb_nan`` references' FV
    level-2 solve reports a NaN energy balance (not first in the list, so a plain max() drops it; F6(c) must fail);
    ``fv_pc_bad`` references' FV level-3 solve reports a Picard residual of 5e-4 K (F6(c) Picard fails; every other FV
    solve reports 5e-5 K, below the 1e-4 K gate); ``fv_pc_missing`` references' FV level-1 record has no picard_dT_K
    key (a stale record; it counts as NaN, F6(c) Picard must fail; T0310 finding 1); ``fv_tj_nan`` references' FV level-2
    solve reports a NaN Tj on die 1 (not the first die, so a plain max() over dies drops it; F6(e) on its type and the
    aggregate must fail; T0310 finding 2); ``em_nan`` fingerprints' thk_f band solve returns a NaN L and ``em_nc``
    fingerprints' fil_f band solve reports GMRES flag 1 (not converged, finite L) (T0318 finding 0).  'snap*' is the off-grid
    reference snapped to 0.25 mm: L = 20.1 nH against the reconstruction's 20.0 nH, so s_ref = 2 |20.1/20 - 1| = 0.01."""
    lo = 1.05 if scenario == "twin_best" else 0.70
    # 'Dmiss' (D0018 selftest): L_sub(D)/L_sub(W) = 1.2505 >= 1.25 at the point, below it at the band's conservative end
    fixed = {"ref": 20e-9, "twin": 20.0004e-9, "Dmiss": 1.2505 * 20.0004e-9, "D": 27.5e-9, "snap": 20.1e-9}
    hot, fv_bad, fv_eb_bad, fv_eb_nan, fv_pc_bad, fv_pc_missing, fv_tj_nan = (
        set() if x is None else x for x in (hot, fv_bad, fv_eb_bad, fv_eb_nan, fv_pc_bad, fv_pc_missing, fv_tj_nan))

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
            L = lsub(fp) * f * (1 + (2e-3 * _u(fp, 10 + k) if k else 0.0))
            nc = fp in (em_nc or ()) and j["level"] == "fil_f"
            return {"L_H": math.nan if fp in (em_nan or ()) and j["level"] == "thk_f" else L, "n_unknowns": 1000,
                    "gmres_flags": [1 if nc else 0], "solver_tol_rel_L_max": 1e-6, "fingerprint": fp}
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
            if j["type"] == "fv" and fp in fv_tj_nan and lv == 2:
                tj[1] = math.nan
            eb = 1e-3 if j["type"] == "fv" and fp in fv_eb_bad else 1e-9
            if j["type"] == "fv" and fp in fv_eb_nan and lv == 2:
                eb = math.nan
            rec = {"tj": tj, "tj_node": [[0.0, 0.0, 0.0]] * 4, "nodes": 1000 * 8 ** lv,
                   "energy_balance": eb, "picard_iters": 3, "picard_residual_K": 1e-6, "fingerprint": fp}
            if j["type"] == "fv" and not (fp in fv_pc_missing and lv == 1):
                rec["picard_dT_K"] = 5e-4 if fp in fv_pc_bad and lv == 3 else 5e-5
            return rec
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
    # seven references, stack types from the real _stack_type (selftest(), ST_REFS): F6(e) and F6(c) planted on the FV
    # solves; stack_types_nan: the same references with one planted fault only, a NaN FV Tj (T0310 finding 2), so the
    # aggregate F6(e) check can fail for no other reason
    "stack_types": (7, (), {}), "stack_types_nan": (7, (), {}),
}
# stack_types scenario, per reference: (stack, die thickness factor, die attach thickness factor, admissible).  fake1 is the
# first AMB reference and inadmissible, so AMB's spot check must fall on fake2 (T0307 finding 1); fake3 differs from fake2
# only in die thickness and must get its own (T0308 finding 1); fake4 is C004's default stack with thicker die attach on
# the dies only (the stack-level type would call it default); fake5's type (thicker stack-level die-attach layer) has no
# admissible reference: no spot check, reported, not failed.  fake6 is a second ADMISSIBLE AMB reference after fake2, so
# only the first admissible one in reference order matches the expected spot reference (T0310 finding 0).
ST_REFS = (("dbc", 1.0, 1.0, True), ("amb", 1.0, 1.0, False), ("amb", 1.0, 1.0, True), ("amb", 2.0, 1.0, True),
           ("dbc", 1.0, 2.0, True), ("dbc_la2", 1.0, 1.0, False), ("amb", 1.0, 1.0, True))

# Dev thermal report, literal hand case (T0307 finding 3, T0308 finding 0).  Die rows (Tj levels 0, 1, 2 in K), floor
# 1e-3 K, limit 2 K, every value a dyadic fraction so the hand values are exact.  gci_capped (mfos.metrics; Roache 1998
# ch. 5): d1 = f1 - f0, d2 = f2 - f1, rho = d2 / d1; rho = 1/4 or 1/2 -> 1.25 |d2| / (2^1 - 1) = 1.25 |d2|; |rho| >= 1
# -> +inf; d1 = d2 = 0 -> 0.
#   twin    d0 400, 400.5, 400.625    d1 0.5,   d2 0.125   rho 1/4  GCI 0.15625
#           d1 398, 399, 399.5        d1 1,     d2 0.5     rho 1/2  GCI 0.625
#           upper max(400.78125, 400.125) = 400.78125; lower max(400.46875, 398.875) = 400.46875; width 0.3125 <= 2
#   c_div   d0 399, 399.25, 399.3125  rho 1/4 GCI 0.078125; d1 397, 397.5, 398.5 rho 2 GCI +inf (n_gci_inf 1)
#           upper +inf, lower 399.234375: width +inf, not attainable; margin vs twin +inf, fails
#   c_grow  nodes 1000, 9500, 76000: growth 9.5 (|9.5/8 - 1| = 0.1875 > 0.15, flagged) and 8 (ok)
#           d0 399.5, 399.75, 399.8125 GCI 0.078125; d1 396 x3 GCI 0; upper 399.890625, lower 399.734375, width 0.15625;
#           margin vs twin 399.890625 - 400.46875 = -0.578125, passes
#   c_hot   the twin + 10 K on d0 at every level: GCIs 0.15625, 0.625; upper 410.78125, lower 410.46875, width 0.3125
#           (attainable); margin vs twin 410.78125 - 400.46875 = 10.3125 > 2: passes_vs_twin False
TR_ROWS = {"twin": ([1000, 8000, 64000], [[400.0, 400.5, 400.625], [398.0, 399.0, 399.5]]),
           "c_div": ([1000, 8000, 64000], [[399.0, 399.25, 399.3125], [397.0, 397.5, 398.5]]),
           "c_grow": ([1000, 9500, 76000], [[399.5, 399.75, 399.8125], [396.0, 396.0, 396.0]]),
           "c_hot": ([1000, 8000, 64000], [[410.0, 410.5, 410.625], [398.0, 399.0, 399.5]])}
TR_HAND = {
    "twin": {"gci_K": [0.15625, 0.625], "n_gci_inf": 0, "tj_upper_K": 400.78125, "tj_lower_K": 400.46875,
             "self_margin_K": 0.3125, "attainable": True, "growth": [8.0, 8.0], "growth_ok": [True, True]},
    "c_div": {"gci_K": [0.078125, math.inf], "n_gci_inf": 1, "tj_upper_K": math.inf, "tj_lower_K": 399.234375,
              "self_margin_K": math.inf, "attainable": False, "margin_vs_twin_K": math.inf, "passes_vs_twin": False},
    "c_grow": {"gci_K": [0.078125, 0.0], "n_gci_inf": 0, "self_margin_K": 0.15625, "attainable": True,
               "growth": [9.5, 8.0], "growth_ok": [False, True], "margin_vs_twin_K": -0.578125, "passes_vs_twin": True},
    "c_hot": {"gci_K": [0.15625, 0.625], "n_gci_inf": 0, "self_margin_K": 0.3125, "attainable": True,
              "margin_vs_twin_K": 10.3125, "passes_vs_twin": False}}
TR_SUMMARY = {"n_layouts": 4, "n_layouts_growth_fail": 1, "n_gci": 8, "n_gci_inf": 1, "n_attainable": 3}


def _same(a, b) -> bool:
    if isinstance(b, list):
        return isinstance(a, list) and len(a) == len(b) and all(_same(x, y) for x, y in zip(a, b, strict=True))
    if isinstance(b, bool) or isinstance(a, bool):
        return a is b
    return a == b or (math.isfinite(b) and abs(a - b) <= 1e-12)


def thermal_report_literal_failures(fn, g: dict) -> list[str]:
    """Run ``fn`` (thermal_report_from_rows or a mutant) on TR_ROWS and compare every field with TR_HAND / TR_SUMMARY."""
    rows = [{"kind": "die", "reference_id": "hand", "layout_id": lab, "die_id": f"d{i}", "role": lab, "nodes": nodes,
             **{f"Tj_l{lv}_K": tj[lv] for lv in range(3)}} for lab, (nodes, dies) in TR_ROWS.items()
            for i, tj in enumerate(dies)]
    out = []
    try:
        rep = fn(rows, g, 1e-3, 2.0)["hand"]
    except Exception as e:  # noqa: BLE001 - a crashing mutant counts as caught
        return [f"thermal report raised {type(e).__name__}: {e}"]
    for lab, want in TR_HAND.items():
        got = rep["layouts"].get(lab, {})
        out += [f"thermal report {lab}.{k}: {got.get(k)!r} != hand {v!r}" for k, v in want.items()
                if k not in got or not _same(got[k], v)]
    if "margin_vs_twin_K" in rep["layouts"].get("twin", {}):
        out.append("thermal report: the twin carries a margin against itself")
    out += [f"thermal report summary.{k}: {rep['summary'].get(k)!r} != hand {v!r}" for k, v in TR_SUMMARY.items()
            if rep["summary"].get(k) != v]
    return out


def _mutant_all_attainable(rows, g, floor, limit):
    """Falsified report (T0309 item 4): every layout attainable."""
    out = thermal_report_from_rows(rows, g, floor, limit)
    for v in out.values():
        for e in v["layouts"].values():
            e["attainable"] = True
        v["summary"]["n_attainable"] = v["summary"]["n_layouts"]
    return out


def _mutant_t0308(rows, g, floor, limit):
    """T0308's falsified report: every layout attainable, zero margins, zero +inf GCIs, passes_vs_twin True."""
    out = thermal_report_from_rows(rows, g, floor, limit)
    for v in out.values():
        for lab, e in v["layouts"].items():
            e.update(attainable=True, self_margin_K=0.0, n_gci_inf=0)
            if lab != "twin":
                e.update(passes_vs_twin=True, margin_vs_twin_K=0.0)
        v["summary"].update(n_attainable=v["summary"]["n_layouts"], n_gci_inf=0)
    return out


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


def stack_rounding_failures(dbc, d_def) -> list[str]:
    """Stack-type signature rounding (T0310 finding 3): a stack that differs from C004's default only by float rounding
    (every layer thickness and k, and the die and attach thickness, x (1 + 1e-15), and 2D_Case_4's stored die thickness
    0.00017999999999999998 m) is the default type; a 1 um change in any one layer's thickness, a 1 um change in one die's
    thickness or attach, and a 1e-6 relative change in one layer's k are not."""
    from moduleforge.geometry.layout import Die
    out = []
    e = 1.0 + 1e-15

    def lay_all(st, f):
        return dataclasses.replace(st, layers=tuple(f(la) for la in st.layers), die_attach=f(st.die_attach), die=f(st.die))

    def dies(t=None, a=None, n=4):
        return [dataclasses.replace(d_def, cx=float(i), thickness=d_def.thickness if t is None else t,
                                    attach_thickness=d_def.attach_thickness if a is None else a) for i in range(n)]
    if abs(0.00017999999999999998 - d_def.thickness) > 1e-18:
        out.append(f"stack rounding: the default die thickness {d_def.thickness} is not 180 um; the 2D_Case_4 case is void")
    rounded = lay_all(dbc, lambda la: dataclasses.replace(la, thickness=la.thickness * e, k=la.k * e))
    for lab, st, ds in (("every thickness and k x (1 + 1e-15)", rounded, dies(d_def.thickness * e, d_def.attach_thickness * e)),
                        ("die thickness 0.00017999999999999998 m", dbc, dies(0.00017999999999999998)),
                        ("a single die x (1 + 1e-15)", dbc, [Die(0.0, 0.0, 1.0, 1.0, "HS", {}, thickness=d_def.thickness * e)])):
        if _stack_type(st, ds) != DEFAULT_STACK:
            out.append(f"stack rounding: {lab} is {_stack_type(st, ds)}, want {DEFAULT_STACK}")
    names = [la.name for la in (*dbc.layers, dbc.die_attach, dbc.die)]
    for j, nm in enumerate(names):
        bumped = list((*dbc.layers, dbc.die_attach, dbc.die))
        for lab, new in (("+1 um", dataclasses.replace(bumped[j], thickness=bumped[j].thickness + 1e-6)),
                         ("k x (1 + 1e-6)", dataclasses.replace(bumped[j], k=bumped[j].k * (1 + 1e-6)))):
            b2 = list(bumped)
            b2[j] = new
            st = dataclasses.replace(dbc, layers=tuple(b2[:-2]), die_attach=b2[-2], die=b2[-1])
            if _stack_type(st, dies()) == DEFAULT_STACK:
                out.append(f"stack rounding: layer {j} ({nm}) {lab} is still {DEFAULT_STACK}")
    for lab, ds in (("die +1 um", dies(d_def.thickness + 1e-6)), ("attach +1 um", dies(a=d_def.attach_thickness + 1e-6)),
                    ("one of four dies +1 um", [*dies(n=3), dataclasses.replace(d_def, cx=9.0, thickness=d_def.thickness + 1e-6)])):
        if _stack_type(dbc, ds) == DEFAULT_STACK:
            out.append(f"stack rounding: {lab} is still {DEFAULT_STACK}")
    if _sig_nm(0.00017999999999999998) != 180000 or _sig_nm(1e-6) != 1000 or _sig_k(24.0 * e) != _sig_k(24.0) or \
            _sig_k(24.0) == _sig_k(24.0 * (1 + 1e-6)):
        out.append("stack rounding: _sig_nm / _sig_k hand values")
    return out


# D0018 decision 2 selftest cases: name -> (fake world, references, planted DegradeError on, planted D miss on, wanted
# exclusions {rid: reason}, at_least_one_counted_reference passes, a planted control miss on (F1b_control must fail))
# (world, n, DegradeError on, D miss on, want excluded {rid: reason}, at_least_one_counted passes, control misses, extra)
# extra (T0318 findings 0 and 4): twin_err = TwinError on; em_nan / em_nc = planted band faults (fingerprints); d_fail =
# references whose F1b_D_definition must fail (INVALID, not excluded)
EXCLUSION_CASES = {
    "degrade_one_of_two": ("headroom", 2, {1}, set(), {"fake1": "DegradeError"}, True, set(), {}),
    "degrade_only_reference": ("headroom", 1, {0}, set(), {"fake0": "DegradeError"}, False, set(), {}),
    "D_miss_one_of_two": ("headroom", 2, set(), {1}, {"fake1": "D_misses_1p25_in_L_sub"}, True, set(), {}),
    "control_miss_beside_exclusion": ("twin_best", 2, {1}, set(), {"fake1": "DegradeError"}, True, {"fake0"}, {}),
    "twin_error_one_of_two": ("headroom", 2, set(), set(), {"fake1": "TwinError"}, True, set(), {"twin_err": {1}}),
    "D_miss_only_reference": ("headroom", 1, set(), {0}, {"fake0": "D_misses_1p25_in_L_sub"}, False, set(), {}),
    "mixed_stages": ("headroom", 3, {0}, {2}, {"fake0": "DegradeError", "fake2": "D_misses_1p25_in_L_sub"}, True, set(),
                     {}),
    "nan_band_is_invalid": ("headroom", 2, set(), set(), {}, False, set(), {"em_nan": {"D1"}, "d_fail": {"fake1"}}),
    "nonconverged_band_is_invalid": ("headroom", 2, set(), set(), {}, False, set(),
                                     {"em_nc": {"twin0"}, "d_fail": {"fake0"}}),
}
EXCLUSION_STAGE = {"TwinError": "prepare", "DegradeError": "prepare", "D_misses_1p25_in_L_sub": "drive"}


def exclusion_failures(cfg: dict, scfg: dict) -> list[str]:
    """D0018 decision 2 end to end: prepare() (W.twin / W.degrade replaced by planted fakes, so a DegradeError is raised
    inside the real prepare), Run.drive (D's definition from the fake band solves), assemble_rows and evaluate.  An
    excluded reference: no driver, no rows, reported with its reason; at_least_one_counted_reference decides INVALID; a
    control miss stays a failed gated check (INVALID), never an exclusion.  Also: degrade() was handed the floor rule."""
    import tempfile

    from moduleforge.drc.rules import DesignRules
    from moduleforge.generate import derivative as D
    from moduleforge.generate import twin as W
    from moduleforge.optimize import search as S
    out = []
    spec3 = D.halfbridge_housing_spec(2, rules=DesignRules(min_width_power=3e-3), wires_per_die=1)  # power rule 3 mm
    r3, _, rr3 = e008_rules(D.generate(spec3, 1, seed=20261112)[0], base=spec3.rules)  # T0319 guard: e008_rules' spec
    spec3 = dataclasses.replace(spec3, rules=r3)
    floor = float(cfg["degrade_power_width_floor_m"])
    plant: dict = {"err": set(), "miss": set(), "seen": {}, "twin_err": set()}
    fake_p = SimpleNamespace(sequence=lambda: [("DC+", "die", "HS"), ("PHASE", "land", "HS"), ("PHASE", "die", "LS"),
                                               ("DC-", "land", "LS")], slots=[(0, 2 * i, 1, 2 * i + 1) for i in range(4)])

    def twin_(ref, spec, with_l1=True):
        if int(ref.fingerprint()[3:]) in plant["twin_err"]:
            raise W.TwinError("planted TwinError")
        return FakeLay(f"twin{ref.fingerprint()[3:]}", None), fake_p, {"mode": "planted"}

    def degrade_(tw, spec, with_l1=True):
        k = int(tw.fingerprint()[4:])
        plant["seen"][k] = spec.rules.min_width_power
        if k in plant["err"]:
            e = W.DegradeError("planted DegradeError")
            e.record = {"walk": {"terminal": W.WALK_LOCAL_MAX}}
            raise e
        return FakeLay(("Dmiss" if k in plant["miss"] else "D") + str(k), None), {"walk": None, "l1_ratio": 1.4}
    orig = (W.twin, W.degrade, globals()["save_ctx"])
    W.twin, W.degrade = twin_, degrade_
    globals()["save_ctx"] = lambda rc, wd: (wd.mkdir(parents=True, exist_ok=True), str(wd / "ctx.pkl"))[1]
    try:
        for name, (world, n, err, miss, want, want_ok, ctrl_miss, x) in EXCLUSION_CASES.items():
            plant.update(err=err, miss=miss, seen={}, twin_err=x.get("twin_err", set()))
            lsub, l1, fjob = fake_world(world, em_nan=x.get("em_nan"), em_nc=x.get("em_nc"))
            d_fail = x.get("d_fail", set())
            with tempfile.TemporaryDirectory() as td:
                root = Path(td)
                run = Run(cfg, root, Scheduler(1e9, 8, 2, fake=fjob), smoke=False, threads=2, fake={"l1": l1})
                refs = [prepare(RefCtx(f"fake{k}", "dev", spec3, FakeLay(f"ref{k}", None), area_m2=0.008,
                                       stack_type=DEFAULT_STACK, info={"rules_record": rr3}), cfg, 0, 0) for k in range(n)]
                seeds = {(rc.rid, ns): 2000 + 2 * i + j for i, rc in enumerate(refs) for j, ns in enumerate(("main", "control"))}
                for rc in refs:
                    if rc.excluded is not None:
                        continue
                    for ns in ("main", "control"):  # the screens, as the scenario loop of selftest() writes them
                        wd = root / rc.rid / ns
                        wd.mkdir(parents=True, exist_ok=True)
                        chunks = {}

                        def gen(spec_, m, sk, rid=rc.rid, ns=ns, chunks=chunks):
                            lays = [FakeLay(hashlib.sha256(f"{rid}{ns}{sk}{i}".encode()).hexdigest(), f"fam{i}")
                                    for i in range(m)]
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
                run.drive(refs, seeds, scfg)
                rows, extra = assemble_rows(run, refs, smoke=False)
                met, checks, rep = evaluate(run, refs, rows, extra, cfg)
            cmap = {c["name"]: c for c in checks}
            got = {rid: e["reason"] for rid, e in rep.get("excluded", {}).items()}
            if got != want:
                out.append(f"exclusion/{name}: excluded {got}, want {want}")
            if any(r.get("reference_id") in want for r in rows):
                out.append(f"exclusion/{name}: an excluded reference has rows")
            if any(k[0] in want for k in run.drivers):
                out.append(f"exclusion/{name}: an excluded reference kept a search driver {sorted(run.drivers)}")
            stages = {rid: e["stage"] for rid, e in rep.get("excluded", {}).items()}
            if stages != {rid: EXCLUSION_STAGE[r] for rid, r in want.items()}:
                out.append(f"exclusion/{name}: stages {stages}")
            dfc = {c["name"][len("F1b_D_definition:"):] for c in checks
                   if c["name"].startswith("F1b_D_definition:") and not c["passed"]}
            if dfc != d_fail or cmap["F1b_D_definition"]["passed"] != (not d_fail):
                out.append(f"exclusion/{name}: F1b_D_definition failed on {sorted(dfc)} (aggregate "
                           f"{cmap['F1b_D_definition']['passed']}), want {sorted(d_fail)} (a solver failure is INVALID)")
            if cmap["at_least_one_counted_reference"]["passed"] != want_ok or \
                    met.get("n_counted_references") != float(0 if d_fail else n - len(want)):
                out.append(f"exclusion/{name}: at_least_one_counted_reference {cmap['at_least_one_counted_reference']}, "
                           f"n_counted {met.get('n_counted_references')} (want {'pass' if want_ok else 'INVALID'})")
            if want_ok and not math.isfinite(met["headroom_min_lo"]):
                out.append(f"exclusion/{name}: A1 not finite with a counted reference left")
            if not want_ok and math.isfinite(met["headroom_min_lo"]):
                out.append(f"exclusion/{name}: A1 finite with no counted reference")
            for c in ("fail_fast_twin_and_D",) + (() if d_fail else ("F1b_D_definition",)):
                if not cmap[c]["passed"]:
                    out.append(f"exclusion/{name}: {c} failed: {cmap[c]['detail'][:200]}")
            fc = {c["name"][len("F1b_control:"):]: c["passed"] for c in checks if c["name"].startswith("F1b_control:")}
            if {r for r, ok in fc.items() if not ok} != ctrl_miss:
                out.append(f"exclusion/{name}: F1b_control failures {fc}, planted on {sorted(ctrl_miss)} (a control miss "
                           f"must stay a failed gated check, INVALID)")
            if plant["seen"] != {k: min(3e-3, floor) for k in range(n) if k not in plant["twin_err"]}:
                out.append(f"exclusion/{name}: degrade() was handed min_width_power {plant['seen']}, want the floor "
                           f"{min(3e-3, floor)} (reference 3 mm)")
            if miss:  # the planted miss is a conservative-end miss: >= 1.25 at the point, below it at the band's end
                k = min(miss)
                bd = [fjob({"type": "em", "fp": f"Dmiss{k}", "level": lv})["L_H"] for lv in BAND]
                bw = [fjob({"type": "em", "fp": f"twin{k}", "level": lv})["L_H"] for lv in BAND]
                R, e = bd[0] / bw[0], MX.ratio_band_estimate(bd, bw)
                if not (R >= cfg["gates"]["degrade_ratio"] > R * (1 - 2 * e)):
                    out.append(f"exclusion/{name}: planted D is not a conservative-end miss (R {R}, e_R {e})")
    finally:
        W.twin, W.degrade, globals()["save_ctx"] = orig
    log(f"selftest exclusion (D0018): {len(EXCLUSION_CASES)} cases, {len(out)} failures")
    return out


# planted reference for the D0018 floor test: generator housing, 2 dies per switch, 1 wire per die, power rule 3 mm,
# landing bands narrowed to that rule (move 1 under the reference's own rule), so they sit at the reference minimum
FLOOR_PLANT = {"dies_per_switch": 2, "wires_per_die": 1, "power_width_m": 3e-3, "seed": 20261112}


def d_floor_geometry_failures(cfg: dict) -> list[str]:
    """D0018 decision 1 on real geometry: on a planted generator layout whose power bands sit at the reference minimum
    (3 mm), prepare() builds D under the floor rule; D's narrowest power strip must be below 3 mm and not below the floor,
    D DRC-clean under the floor rule, and under the reference's rules only min_trace_width may be violated."""
    from moduleforge.drc.rules import DesignRules, check
    from moduleforge.generate import derivative as D
    from moduleforge.generate import twin as W
    out = []
    fp_ = FLOOR_PLANT
    spec = D.halfbridge_housing_spec(fp_["dies_per_switch"], rules=DesignRules(min_width_power=fp_["power_width_m"]),
                                     wires_per_die=fp_["wires_per_die"])
    lay = D.generate(spec, 1, seed=fp_["seed"])[0]
    p1, widths = W._narrow_landing(D.params_of(lay), spec, centre=False)
    planted = D.build(spec, p1)
    w_ref = narrowest_power_strip_m(planted)
    if check(planted, spec.rules) or abs(w_ref - fp_["power_width_m"]) > 2e-6 or \
            any(abs(v["after_mm"] - 1e3 * fp_["power_width_m"]) > 1e-9 for v in widths.values()):
        out.append(f"floor: planted layout not at the reference minimum (narrowest {w_ref}, bands {widths})")
        return out
    rules, _, rrec = e008_rules(planted, base=spec.rules)  # T0319 guard: only e008_rules' specs reach prepare()
    spec = dataclasses.replace(spec, rules=rules)
    rc = prepare(RefCtx("planted_floor", "dev", spec, planted, info={"rules_record": rrec}), cfg, 0, 0)
    dr, floor = rc.info["D_rule"], float(cfg["degrade_power_width_floor_m"])
    w = dr.get("narrowest_power_strip_m")
    if rc.excluded is not None or w is None:
        out.append(f"floor: no D on the planted layout ({rc.excluded})")
        return out
    if not (floor - 2e-6 <= w < fp_["power_width_m"] - 1e-6) or dr["D_min_width_power_m"] != floor:
        out.append(f"floor: D's narrowest power strip {w} m, want in [{floor}, {fp_['power_width_m']}) (rule {dr})")
    if not dr["drc_clean_under_D_rules"] or not set(dr["rules_violated_under_reference_rules"]) <= {"min_trace_width"} \
            or not dr["narrowed_below_reference"]:
        out.append(f"floor: D under the rules {dr}")
    if check(rc.twin, spec.rules):
        out.append("floor: the twin is not DRC-clean under the reference's rules")
    log(f"selftest floor (D0018): reference minimum {w_ref * 1e3:.3f} mm, D narrowest {w * 1e3:.3f} mm, floor "
        f"{floor * 1e3:g} mm, cells across {dr['cells_across']}, D L1 ratio {rc.d_rec.get('l1_ratio')}")
    return out


# planted reference for the T0317 signal-rule test: a generator layout under 2D_Case_4's dev spec (assumed gate / Kelvin
# pads, its GATE/KELVIN keep-outs), with every gate wire's landing moved LONGER_MM deeper into its gate copper along the
# wire (T0314's 2R mechanism: the reference lands its gate wires beyond the nearest copper; the twin lands on it)
SIGNAL_PLANT = {"seed": 20261112, "longer_mm": 2.0, "beyond_longest_mm": 0.5}


def _lengthen_gate_wires(lay, by_m: dict):
    """``lay`` with gate wire k's landing moved by_m[k] metres further along the wire's plan direction (same foot, loop
    height, diameter and end heights; derivative's arc_wire)."""
    from moduleforge.geometry.layout import SignalWire, arc_wire
    out = []
    for k, w in enumerate(lay.signal_wires):
        if k in by_m:
            s, q = w.points[0, :2], w.points[-1, :2]
            q2 = q + (q - s) / np.linalg.norm(q - s) * by_m[k]
            bw = arc_wire(tuple(s), tuple(q2), float(w.points[0, 2]), float(w.points[-1, 2]), w.loop_height, w.diameter,
                          w.net)
            w = SignalWire(w.die, w.pad, w.net, bw.points, w.diameter, w.loop_height)
        out.append(w)
    return dataclasses.replace(lay, signal_wires=out)


def signal_rule_failures(cfg: dict) -> list[str]:
    """D0018 model-fix item 1 on real geometry (L0 only): on a planted reference whose gate wires land 2 mm beyond the
    nearest gate copper, e008_rules drops the measured lower bound and keeps the upper ones; the twin built under them (gate
    wires to the nearest copper, shorter than the reference's shortest gate wire) is DRC-clean, while under raw
    measure_rules it fails signal_wire_length (the test can see the difference); a twin gate wire made longer than the
    reference's longest gate wire still fails signal_wire_length under E008's rules."""
    from moduleforge.drc.rules import check, measure_rules
    from moduleforge.generate import derivative as D
    from moduleforge.generate import twin as W
    from moduleforge.geometry import GATE_HS, GATE_LS, KELVIN_HS, KELVIN_LS
    out = []
    sp = SIGNAL_PLANT
    base = D.generate(dev_reference("case4", cfg).spec, 1, seed=sp["seed"])[0]
    ref = _lengthen_gate_wires(base, {k: sp["longer_mm"] * 1e-3 for k, w in enumerate(base.signal_wires)
                                      if w.pad == "gate"})
    raw = measure_rules(ref)[0]
    rules, _, rrec = e008_rules(ref)
    ref_g = _gate_wires(ref)
    if not ref_g or check(ref, raw) or check(ref, rules):
        return [f"signal: planted reference not DRC-clean under its own rules or without gate wires ({ref_g})"]
    if rules.min_signal_wire_length is not None or raw.min_signal_wire_length is None or \
            rrec["dropped_source_values_m"]["min_signal_wire_length"] != raw.min_signal_wire_length or \
            any(getattr(rules, k) != getattr(raw, k) for k in KEPT_SIGNAL_UPPER_BOUNDS) or \
            dataclasses.replace(rules, min_signal_wire_length=raw.min_signal_wire_length) != raw:
        out.append(f"signal: e008_rules did not drop exactly the lower bound (record {rrec})")
    spec = D.spec_from_layout(ref, rules, [GATE_HS, GATE_LS, KELVIN_HS, KELVIN_LS])
    try:
        tw = W.twin(ref, spec, with_l1=False)[0]
    except W.TwinError as e:
        return out + [f"signal: no twin under E008's rules: {e}"]
    tw_g = _gate_wires(tw)
    if not min(tw_g) < min(ref_g) - 1e-4:
        out.append(f"signal: the twin's shortest gate wire {min(tw_g)} is not shorter than the reference's {min(ref_g)}")
    if check(tw, rules):
        out.append(f"signal: the twin fails E008's rules: {sorted({v.rule for v in check(tw, rules)})}")
    if "signal_wire_length" not in {v.rule for v in check(tw, raw)}:
        out.append("signal: under raw measure_rules the twin's short gate wire passes (the test cannot see the rule)")
    k = max((i for i, w in enumerate(tw.signal_wires) if w.pad == "gate"), key=lambda i: tw.signal_wires[i].length)
    longer = _lengthen_gate_wires(tw, {k: max(ref_g) - tw.signal_wires[k].length + sp["beyond_longest_mm"] * 1e-3})
    vl = {v.rule for v in check(longer, rules)}
    if not longer.signal_wires[k].length > max(ref_g) or vl & {"signal_wire_landing", "signal_wire_cross"} or \
            "signal_wire_length" not in vl:
        out.append(f"signal: a gate wire of {longer.signal_wires[k].length} m (reference longest {max(ref_g)} m) gives "
                   f"{sorted(vl)} under E008's rules, want signal_wire_length only from length")
    log(f"selftest signal rule (D0018 item 1): reference gate wires {min(ref_g) * 1e3:.3f}-{max(ref_g) * 1e3:.3f} mm, twin "
        f"shortest {min(tw_g) * 1e3:.3f} mm (clean under E008's rules, raw rules: signal_wire_length), longer twin wire "
        f"{longer.signal_wires[k].length * 1e3:.3f} mm -> {sorted(vl)}; {len(out)} failures")
    return out


class FakeER:
    """Selftest recorder with ExperimentRun's recording interface (sanity, metric, rows, artifact, domain, notes)."""

    def __init__(self, spec: dict):
        self.spec, self.sanity_l, self.metrics, self.rows_l, self.artifacts, self.dom, self.notes = spec, [], {}, None, [], {}, ""

    def sanity(self, name, passed, value=None, threshold=None, detail=""):
        self.sanity_l.append({"name": name, "passed": bool(passed), "value": value, "detail": detail})

    def metric(self, name, value, ci=None, n=None, unit="", level=0.95):
        self.metrics[name] = {"value": float(value), "ci": ci, "n": n, "level": level}

    def rows(self, records, name="rows.json"):
        self.rows_l = json.loads(json.dumps(records, default=str))

    def artifact(self, name, path):
        self.artifacts.append((name, json.loads(Path(path).read_text())))

    def domain(self, **values):
        self.dom.update(values)


def _fake_screens(l1):
    """The before_drive hook of registered_run for fake layouts: the frozen driver itself streams the sealed sequence
    with a fake generate and writes the stream file, as child_screen does (the same code as the scenario loop)."""
    from moduleforge.optimize import search as S

    def hook(refs, seeds, scfg, root):
        for rc in refs:
            if rc.excluded is not None:
                continue
            for ns in ("main", "control"):
                wd = root / rc.rid / ns
                wd.mkdir(parents=True, exist_ok=True)
                chunks = {}

                def gen(spec_, m, sk, rid=rc.rid, ns=ns, chunks=chunks):
                    lays = [FakeLay(hashlib.sha256(f"{rid}{ns}{sk}{i}".encode()).hexdigest(), f"fam{i}") for i in range(m)]
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
    return hook


def full_orchestration_failures(spec: dict, scfg: dict) -> list[str]:
    """D0019 / T0320, end to end on the dev layouts with fake solvers and a fake recorder: the loader refuses a wrong
    fingerprint (before any twin); the T0319 guard refuses a spec without e008_rules' record and one with
    min_signal_wire_length set; registered_run loads two judged entries through a fake reconstruction module (the
    generator housing layout gen2_0, counted, and the 2D_Case_4 reconstruction with a planted TwinError, excluded), runs
    prepare, Run.drive, assemble_rows, evaluate and the recorder; every declared sanity check and metric is written; the
    label and the D0019 deviation reach every row, the report and the notes; the excluded reference's own stack type gets
    neither a spot check nor an F6e report; a rerun resumes from the workdir with no new solve; another seed refuses the
    workdir."""
    import tempfile

    from moduleforge.drc.rules import measure_rules
    from moduleforge.generate import twin as W
    out = []
    cfg = json.loads(json.dumps(spec["config"]))
    cfg["quick_ok_draws"] = 5
    cfg["f3_declared_deviation"] = {"statement": "DECLARED F3 DEVIATION (D0019): selftest"}
    g0, c4 = dev_reference("gen2_0", cfg), dev_reference("case4", cfg)
    lays = {"judged_gen": g0.reference, "judged_c4": c4.reference}
    keep = {"judged_gen": [], "judged_c4": cfg["dev"]["case4"]["keepout_nets"]}
    rec = SimpleNamespace(snapped=lambda rid: (lays[rid], {g: SimpleNamespace(records=[], layout=lays[rid])
                                                         for g in (0.5, 0.25, 0.125)}))
    ents = [{"reference_id": rid, "kind": "public", "vault_id": None, "reconstruction_sha256": lays[rid].fingerprint(),
             "sic_mosfet_half_bridge": True, "separate_antiparallel_diode_dies": False, "admissible": True,
             "reason": "selftest", "decided_at": "selftest", "L_term_H": 7e-9, "L_term_source": "selftest",
             "on_grid_0p5mm": True, "snapping_check": "not required", "keepout_nets": keep[rid], "label": PUBLIC_LABEL}
            for rid in lays]
    alias = {lays["judged_gen"].fingerprint(): "ref0", lays["judged_c4"].fingerprint(): "ref1"}
    lsub, l1, fjob = fake_world("headroom")
    calls = {"twin": 0, "jobs": 0}

    def job(j):
        calls["jobs"] += 1
        r = fjob(dict(j, fp=alias.get(j["fp"], j["fp"])))
        return dict(r, fingerprint=j["fp"]) if "fingerprint" in r else r

    def l1a(lay):
        return l1(FakeLay(alias.get(lay.fingerprint(), lay.fingerprint()), None))
    fake_p = SimpleNamespace(sequence=lambda: [("DC+", "die", "HS"), ("PHASE", "land", "HS"), ("PHASE", "die", "LS"),
                                               ("DC-", "land", "LS")], slots=[(0, 2 * i, 1, 2 * i + 1) for i in range(4)])

    def twin_(ref, sp, with_l1=True):
        calls["twin"] += 1
        k = alias[ref.fingerprint()][3:]
        if k == "1":
            raise W.TwinError("planted TwinError (as 2D_Case_6's)")
        return FakeLay(f"twin{k}", None), fake_p, {"mode": "planted"}

    def degrade_(tw, sp, with_l1=True):
        return FakeLay("D" + tw.fingerprint()[4:], None), {"walk": None, "l1_ratio": 1.4}
    # (1) wrong fingerprint: refused before anything else
    bad = dict(ents[0], reconstruction_sha256="0" * 64)
    orig = (W.twin, W.degrade, globals()["save_ctx"])
    W.twin, W.degrade = twin_, degrade_
    globals()["save_ctx"] = lambda rc, wd: (wd.mkdir(parents=True, exist_ok=True), str(wd / "ctx.pkl"))[1]
    try:
        for who, fn in (("judged_reference", lambda: judged_reference(bad, cfg, rec)),
                        ("registered_run", lambda: registered_run(FakeER(spec), dict(cfg, references=[bad, ents[1]]), 7,
                                                                  Path(tempfile.mkdtemp()), rec, {"job": job, "l1": l1a},
                                                                  _fake_screens(l1a), 2))):
            try:
                fn()
                out.append(f"full: {who} accepted a wrong fingerprint")
            except ReferenceRefused:
                pass
        if calls["twin"]:
            out.append(f"full: twin() ran {calls['twin']} times before the fingerprint refusal")
        # (2) T0319 guard: a spec from measure_rules (no rules_record) and one with min_signal_wire_length set
        raw = measure_rules(lays["judged_gen"])[0]
        no_rec = RefCtx("guard_raw", "public", dataclasses.replace(g0.spec, rules=raw), lays["judged_gen"])
        with_lb = RefCtx("guard_lb", "public", dataclasses.replace(g0.spec, rules=dataclasses.replace(
            g0.spec.rules, min_signal_wire_length=5e-3)), lays["judged_gen"], info=dict(g0.info))
        for rc in (no_rec, with_lb):
            try:
                prepare(rc, cfg, 0, 0)
                out.append(f"full: the T0319 guard let {rc.rid} through")
            except RulesGuardError:
                pass
        if rules_guard_failures(judged_reference(ents[0], cfg, rec)):
            out.append("full: judged_reference's spec fails the T0319 guard")
        # (3) the registered path end to end, then a resume and a foreign seed
        cfg_r = dict(cfg, references=ents)
        with tempfile.TemporaryDirectory() as td:
            er = FakeER(spec)
            res = registered_run(er, cfg_r, 20261112, Path(td), rec, {"job": job, "l1": l1a}, _fake_screens(l1a), 2)
            n_jobs = calls["jobs"]
            er2 = FakeER(spec)
            res2 = registered_run(er2, cfg_r, 20261112, Path(td), rec, {"job": job, "l1": l1a}, _fake_screens(l1a), 2)
            if calls["jobs"] != n_jobs or json.dumps(er2.metrics, sort_keys=True) != json.dumps(er.metrics, sort_keys=True):
                out.append(f"full: the rerun solved {calls['jobs'] - n_jobs} jobs or changed the metrics (no resume)")
            try:
                registered_run(FakeER(spec), cfg_r, 20261113, Path(td), rec, {"job": job, "l1": l1a}, _fake_screens(l1a), 2)
                out.append("full: a workdir of another seed was resumed")
            except RuntimeError:
                pass
        del res2
        names = {c["name"]: c for c in er.sanity_l}
        want = {s["name"] for s in spec["sanity_checks"]}
        if want - set(names):
            out.append(f"full: declared sanity checks not recorded: {sorted(want - set(names))}")
        must_pass = want - {"F6e_stack_type_spot_check"}
        failed = sorted(n for n in must_pass if not names.get(n, {}).get("passed"))
        if failed:
            out.append(f"full: declared checks failed on the planted world: {[(n, names[n]['detail'][:120]) for n in failed]}")
        if {m["name"] for m in spec["metrics"]} - set(er.metrics):
            out.append(f"full: metrics not recorded: {sorted({m['name'] for m in spec['metrics']} - set(er.metrics))}")
        rep, met = res["report"], res["metrics"]
        if {k: v["reason"] for k, v in rep.get("excluded", {}).items()} != {"judged_c4": "TwinError"} or \
                met.get("n_counted_references") != 1.0 or not math.isfinite(met["headroom_min_lo"]) or \
                er.metrics["headroom_min_lo"]["value"] != met["headroom_min_lo"]:
            out.append(f"full: excluded {rep.get('excluded')} counted {met.get('n_counted_references')} A1 "
                       f"{met.get('headroom_min_lo')}")
        if not er.rows_l or any(r.get("label") != PUBLIC_LABEL or r.get("f3_declared_deviation") != "D0019 item 2"
                                for r in er.rows_l) or any(r.get("reference_id") == "judged_c4" for r in er.rows_l):
            out.append("full: a row lacks the label or the deviation, or the excluded reference has rows")
        rpt = dict(er.artifacts).get("evaluation_report.json", {})
        if rpt.get("label") != [PUBLIC_LABEL] or "D0019" not in json.dumps(rpt.get("f3_declared_deviation")) or \
                "DECLARED F3 DEVIATION (D0019)" not in er.notes or PUBLIC_LABEL not in er.notes:
            out.append("full: the label or the D0019 deviation did not reach the report and the notes")
        st_c4 = c4.stack_type
        if st_c4 == DEFAULT_STACK or st_c4 in json.dumps(rep.get("F6e", {})) or st_c4 in res["run"].spot_refs or \
                st_c4 in res["run"].spot_none:
            out.append(f"full: the excluded reference's stack type {st_c4} was spot-checked or reported")
    finally:
        W.twin, W.degrade, globals()["save_ctx"] = orig
    log(f"selftest full (D0019): registered path on gen2_0 (counted) + 2D_Case_4 (planted TwinError), {len(er.sanity_l)} "
        f"sanity records, {len(er.metrics)} metrics, {len(er.rows_l or [])} rows, A1 {met.get('headroom_min_lo'):.5f}; "
        f"{len(out)} failures")
    return out


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
    try:  # T0307 finding 4: die_spacing is not a net spacing, so a record with only it gives an empty report, no raise
        if rule_strictness({"die_spacing": 0.002, "gap_dcp_dcm": None}) != {}:
            failures.append("rule_strictness: a die_spacing-only record gave a non-empty report")
    except RuntimeError as e:
        failures.append(f"rule_strictness: the guard still matches die_spacing ({e})")
    # stack types (T0305 finding 0; T0308 finding 1): the die attach and die layers and the per-die thicknesses
    from moduleforge.geometry.layout import Die
    dbc = default_dbc_stack()
    d_def = Die(0.0, 0.0, 1.0, 1.0, "HS", {})
    stacks = {"dbc": dbc, "amb": default_amb_stack(), "dbc_la2": dataclasses.replace(dbc, die_attach=dataclasses.replace(
        dbc.die_attach, thickness=2 * dbc.die_attach.thickness))}

    def dies_of(ft, fa):
        return [dataclasses.replace(d_def, cx=float(i), thickness=ft * d_def.thickness,
                                    attach_thickness=fa * d_def.attach_thickness) for i in range(4)]
    st_of = [_stack_type(stacks[s], dies_of(ft, fa)) for s, ft, fa, _ in ST_REFS]
    st_amb, st_amb_thick, st_attach, st_la2 = st_of[2], st_of[3], st_of[4], st_of[5]
    if st_of[0] != DEFAULT_STACK or len({st_of[0], st_amb, st_amb_thick, st_attach, st_la2}) != 5 or \
            st_of[1] != st_amb or st_of[6] != st_amb:
        failures.append(f"stack types: {st_of} (want default, AMB x2, three distinct non-default types, AMB)")
    failures += stack_rounding_failures(dbc, d_def)
    mixed = [*dies_of(2.0, 1.0)[:1], *dies_of(1.0, 1.0)]
    if _stack_type(dbc, mixed) != _stack_type(dbc, mixed[::-1] + mixed[:1]) or _stack_type(dbc, mixed) in (
            DEFAULT_STACK, _stack_type(dbc, dies_of(2.0, 1.0))):
        failures.append("stack types: the per-die thickness set is not order/duplicate free or a mixed set is not its own type")
    # dev thermal report against literal hand values; two falsified versions must fail this check (T0307 f3, T0308 f0)
    failures += thermal_report_literal_failures(thermal_report_from_rows, cfg["gates"])
    for mutant in (_mutant_all_attainable, _mutant_t0308):
        if not thermal_report_literal_failures(mutant, cfg["gates"]):
            failures.append(f"thermal report literal check passes the falsified {mutant.__name__}")
    scfg = dict(n_candidates=200, n_first=50, shortlist=16, batch=4, max_checks=8, tj_margin=2.0, chunk=50)
    for scenario, (n_refs, offgrid, n_hot) in SCENARIOS.items():
        hot, fv_bad, fv_eb_bad, fv_eb_nan, fv_pc_bad, fv_pc_missing, fv_tj_nan = (set() for _ in range(7))
        lsub, l1, fjob = fake_world(scenario, hot, fv_bad, fv_eb_bad, fv_eb_nan, fv_pc_bad, fv_pc_missing, fv_tj_nan)
        st_scn = scenario.startswith("stack_types")
        types = st_of if st_scn else [DEFAULT_STACK, "other:fakeAlN"]
        adm = [a for *_, a in ST_REFS] if st_scn else [True] * n_refs
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
                rc.stack_type, rc.admissible = types[k], adm[k]
                refs.append(rc)
            refs_a = [rc for rc in refs if rc.admissible]
            s_hand = {rc.rid: (S_REF_HAND if not rc.on_grid else 0.0) for rc in refs}
            if st_scn:
                # the spot-check references by hand: the first admissible reference of each non-default type (fake2,
                # not fake1 (inadmissible) nor fake6 (a later admissible AMB reference))
                want = {st_amb: "fake2", st_amb_thick: "fake3", st_attach: "fake4"}
                # NaN FV Tj (die 1, level 2) on the LAST checked type in sorted order, so a plain max() over the types
                # drops it whenever an earlier type's value is finite (T0310 finding 2)
                nan_t = max(want)
                fv_tj_nan.add(f"ref{want[nan_t][4:]}")
                first, fail_e, planted_c = None, {nan_t}, set()
            if scenario == "stack_types":
                # F6(e) planted on the first checked type in sorted order too (a single overwritten spot_ref, T0305
                # finding 0, checked only the last one); F6(c): energy balance 1e-3 on fake2, a NaN energy balance on
                # fake3's level-2 FV solve, a Picard residual 5e-4 K on fake4's level-3 FV solve, and fake2's level-1 FV
                # record without picard_dT_K (counts as NaN; T0310 finding 1)
                first = min(want)
                fail_e = {first, nan_t}
                fv_bad.add(f"ref{want[first][4:]}")
                fv_eb_bad.add("ref2")
                fv_eb_nan.add("ref3")
                fv_pc_bad.add("ref4")
                fv_pc_missing.add("ref2")
                planted_c = {"F6c_energy_balance:fake2", "F6c_energy_balance:fake3", "F6c_picard:fake4", "F6c_picard:fake2"}
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
            for rc in refs_a:  # an inadmissible reference has only its reference row
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
            for rc in refs_a:
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
            if rep.get("excluded"):  # D0018: no reference of these scenarios is excluded (a control miss is not)
                failures.append(f"{scenario}: references excluded {rep['excluded']}")
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
                # dev thermal report on the planted hot candidates (T0308 finding 0): the twin's own width is the hand
                # value 2 x 1.25 x max(|0.01 - 0.05|, |0.05 - 0.25| / 4) = 0.125 K (fake levels +0.25 / +0.05 / +0.01 K on
                # every die: rho = 0.2 < 1/4); every hot candidate (+10 K on die 0) fails against the twin by > 2 K
                trh = thermal_report_from_rows(rows, cfg["gates"], 1e-3, 2.0)
                fp_of = {(r["reference_id"], r["layout_id"]): r["fingerprint"] for r in rows if r["kind"] == "die"}
                n_hot_seen = 0
                for rid in ("fake0", "fake1"):
                    tw_e = trh[rid]["layouts"]["twin"]
                    if abs(tw_e["self_margin_K"] - 0.125) > 1e-9 or not tw_e["attainable"]:
                        failures.append(f"offgrid_tj/{rid}: twin self margin {tw_e['self_margin_K']} != hand 0.125 K")
                    for lab, e in trh[rid]["layouts"].items():
                        if fp_of[(rid, lab)] in hot:
                            n_hot_seen += 1
                            if e["passes_vs_twin"] or not e["margin_vs_twin_K"] > 2.0:
                                failures.append(f"offgrid_tj/{rid}: hot {lab} passes_vs_twin {e['passes_vs_twin']} margin "
                                                f"{e['margin_vs_twin_K']}")
                if n_hot_seen != sum(n_hot.values()):
                    failures.append(f"offgrid_tj: {n_hot_seen} planted hot candidates in the thermal report, want {sum(n_hot.values())}")
            if st_scn:
                sn = scenario
                if run.spot_refs != want or run.spot_none != [st_la2]:
                    failures.append(f"{sn}: spot refs {run.spot_refs} != {want} or no-admissible types "
                                    f"{run.spot_none} != {[st_la2]}")
                for st, rid in want.items():
                    fv = [Scheduler.done(j) for j in run.spot_jobs(run.drivers[(rid, "main")])]
                    if len(fv) != 3 or any(f is None for f in fv):
                        failures.append(f"{sn}: {rid} ({st}) has no complete FV levels 1-3")
                    c = cmap.get(f"F6e_stack_type_spot_check:{st}")
                    if c is None or c["passed"] != (st not in fail_e):
                        failures.append(f"{sn}: F6e for {st} {c} (planted failures on {sorted(fail_e)} only)")
                # the NaN FV Tj: its type's check fails with the value NaN, not a finite maximum over the other dies
                c = cmap.get(f"F6e_stack_type_spot_check:{nan_t}")
                if c is None or c["passed"] or c["value"] is None or not math.isnan(c["value"]):
                    failures.append(f"{sn}: F6e for {nan_t} with a planted NaN FV Tj: {c} (want failed, value NaN)")
                # fake1, fake5 inadmissible; fake6 admissible but not its type's first: no FV solve was ever scheduled
                for rid in ("fake1", "fake5", "fake6"):
                    if any(Path(j["out"]).exists() for j in run.spot_jobs(run.drivers[(rid, "main")])) or \
                            any(Path(p_).name.startswith("ref" + rid[4:]) and "__fv" in p_.name
                                for p_ in [Path(x) for x in (root / rid / "solves").glob("*")]):
                        failures.append(f"{sn}: {rid} (not a spot-check reference) has finite-volume spot-check solves")
                # the type without an admissible reference: no per-type check, reported with reference None, not failed
                if f"F6e_stack_type_spot_check:{st_la2}" in cmap or rep.get("F6e", {}).get(st_la2, {}).get(
                        "reference", "missing") is not None or st_la2 not in cmap["F6e_stack_type_spot_check"]["detail"]:
                    failures.append(f"{sn}: type {st_la2} without an admissible reference: check "
                                    f"{cmap.get(f'F6e_stack_type_spot_check:{st_la2}')}, report {rep.get('F6e', {}).get(st_la2)}")
                # aggregate: fails, and its value is NaN (a NaN per-type value; _worst, not a plain max).  In
                # stack_types_nan the NaN is the only F6(e) fault, so the aggregate can fail for no other reason
                agg = cmap["F6e_stack_type_spot_check"]
                if agg["passed"] or agg["value"] is None or not math.isnan(agg["value"]) or \
                        not math.isnan(met.get("stack_type_a3", 0.0)):
                    failures.append(f"{sn}: aggregate F6e {agg}, stack_type_a3 {met.get('stack_type_a3')} (planted per-type "
                                    f"failures on {sorted(fail_e)}, NaN on {nan_t}: want failed, NaN)")
                if rep.get("F6e", {}).get(nan_t, {}).get("status") != "checked":
                    failures.append(f"{sn}: report F6e.{nan_t} {rep.get('F6e', {}).get(nan_t)}")
                # F6(c) on the spot checks: exactly the planted ones fail, each for its own reason, NaN included;
                # fake6 (no spot check) includes no FV solve
                planted = planted_c
                for rid in ("fake0", "fake2", "fake3", "fake4", "fake6"):
                    for kind in ("energy_balance", "picard"):
                        name = f"F6c_{kind}:{rid}"
                        if cmap[name]["passed"] == (name in planted_c):
                            failures.append(f"{sn}: {name} passed={cmap[name]['passed']} (planted: {sorted(planted_c)})")
                        n_fv = 3 if rid in want.values() else 0
                        if f"{n_fv} finite-volume spot-check solves included" not in cmap[name]["detail"]:
                            failures.append(f"{sn}: {name} does not include {n_fv} FV solves: {cmap[name]['detail']}")
                if scenario == "stack_types":
                    if not math.isnan(cmap["F6c_energy_balance:fake3"]["value"]):
                        failures.append(f"{sn}: fake3's NaN energy balance reported as {cmap['F6c_energy_balance:fake3']['value']}")
                    if cmap["F6c_picard:fake4"]["value"] != 5e-4:
                        failures.append(f"{sn}: fake4's FV Picard residual reported as {cmap['F6c_picard:fake4']['value']}")
                    # fake2's level-1 FV record has no picard_dT_K: it counts as NaN (every other Picard value of fake2
                    # is 5e-5 K or below, so the failure comes from the missing key alone; T0310 finding 1)
                    if not math.isnan(cmap["F6c_picard:fake2"]["value"]):
                        failures.append(f"{sn}: fake2's FV record without picard_dT_K reported as "
                                        f"{cmap['F6c_picard:fake2']['value']} (want NaN)")
            for c in checks:
                if c["name"].startswith(("recompute_agrees", "F6a", "F6c", "F6d", "F1c", "at_least", "driver_s_ref",
                                         "fail_fast_twin_and_D", "F1b_D_definition")) \
                        and not c["passed"] and c["name"] not in planted:
                    failures.append(f"{scenario}: {c['name']} {c['detail'][:200]}")
            n_c = sum(r["kind"] == "layout" and r["role"] == "candidate" for r in rows)
            if n_c != 16 * len(refs_a):
                failures.append(f"{scenario}: {n_c} candidate rows, want 16 per reference")
            if any(not math.isfinite(float(r["L_sub_null_H"])) for r in rows):
                failures.append("a row without a finite L_sub_null_H")
            tr = thermal_report_from_rows(rows, cfg["gates"], 1e-3, 2.0)
            if sorted(tr) != sorted(rc.rid for rc in refs_a) or any(v["summary"]["n_layouts_growth_fail"] for v in tr.values()):
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
    failures += exclusion_failures(cfg, scfg)
    failures += d_floor_geometry_failures(cfg)
    failures += signal_rule_failures(cfg)
    failures += full_orchestration_failures(spec, scfg)
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
        for lv in levels:  # the reference's own counted unknowns (--check-references, T0320) where given, else the area model
            n = int(r["em_unknowns"][lv]) if "em_unknowns" in r else em_unknowns(area, EM_LEVELS[lv][0], lv, cm)
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


def _cost_jobs(J: list[dict], cm: dict, vm: dict, vcpus: int, cap: float, overhead: bool = True) -> dict:
    """Phase A (list scheduling of the jobs that fit in the cap) and phase B (each larger job alone on the VM resized with
    N2D extended memory) of ``J`` -> hours, $, billed vCPU-hours, process CPU-hours and the phase-B rows with the FV range."""
    big = [j for j in J if j["mem_GB"] > cap]
    small = [j for j in J if j["mem_GB"] <= cap]
    for j in small:  # a phase-A job that waits on a phase-B group is released at the start
        j["after"] = [a for a in j["after"] if not any(b["group"] == a for b in big)]
    a_h = (simulate(small, vcpus, cap) / 3600.0 if small else 0.0) + (vm["overhead_h"] if overhead else 0.0)
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
        b_rows.append({"job": j["name"], "n": j["n"], "peak_GB": round(j["mem_GB"], 1),
                       "machine": f"n2d-custom-8-{int(ram * 1024)}-ext", "ram_GB": ram, "fits_n2d_768GB": ram <= 768,
                       "fits_150GB": ram <= 150, "hours": round(h, 2), "usd": round(h * usd_h, 2),
                       "usd_per_h": round(usd_h, 4), "sensitivity": sens})
        b_h, b_usd = b_h + h, b_usd + h * usd_h
    vm_h = a_h + b_h
    cpu_h = sum(j["est_s"] * (cm["cores_per_2thread_solve"] if j["threads"] == 2 else 1.0) for j in J) / 3600.0
    return {"n_solves": len(J), "phase_a_hours": round(a_h, 2), "phase_b_big_memory_jobs": b_rows,
            "phase_b_hours": round(b_h, 2), "phase_b_usd": round(b_usd, 2),
            "phase_b_sensitivity": {t: {"phase_b_hours": round(v[0], 2), "phase_b_usd": round(v[1], 2),
                                        "vm_hours": round(a_h + v[0], 2), "usd": round(a_h * vm["usd_per_h"] + v[1], 2),
                                        "billed_vcpu_hours": round((a_h + v[0]) * vcpus, 1)} for t, v in b_rng.items()},
            "vm_hours": round(vm_h, 2), "usd": round(a_h * vm["usd_per_h"] + b_usd, 2),
            "billed_vcpu_hours": round(vm_h * vcpus, 1), "process_cpu_hours": round(cpu_h, 1)}


def _plan_case(refs: list[dict], case: tuple, cm: dict, vm: dict, threads: int, vcpus: int, cap: float, cfg: dict,
               args) -> dict:
    """One --plan case (near ties, thermal batches, null checks) over the plan references ``refs``."""
    n_near, batches, n_null = case
    J = []
    for r in refs:
        J += plan_jobs(r, cm, threads, n_near, batches, n_null, cfg["search"]["n_candidates"])
    res = _cost_jobs(J, cm, vm, vcpus, cap)
    per_ref = {}
    for r in refs:
        jr = [j for j in J if j["name"].startswith(r["name"] + ":")]
        per_ref[r["name"]] = {k: round(max(j["mem_GB"] for j in jr if j["kind"] == k), 1)
                              for k in ("em", "thermal", "fv") if any(j["kind"] == k for j in jr)}
    per_solve = {}  # founder constraint: per-solve wall and memory on the 8-vCPU VM (first plan reference's sizes)
    r0 = refs[0]["name"]
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
    if args.verbose:
        for j in J:
            print(f"{j['name']:<44} {j['kind']:<8} n={j['n']:>11} {j['mem_GB']:7.1f} GB {j['est_s'] / 3600:7.2f} h")
    return {"references": [r["name"] for r in refs], "near_ties": n_near, "thermal_batches": batches,
            "null_extra_checks": n_null, **res, "peak_GB_per_reference": per_ref,
            "per_solve_on_vm": {"reference_sizes": r0, "note": "wall at the scheduled concurrency (four 0.25 mm solves at "
                                "once, two threads each); n = unknowns / DOFs / cells / candidates", "solves": per_solve},
            "end_date_if_start": (dt.datetime.fromisoformat(vm["earliest_start"])
                                  + dt.timedelta(hours=res["vm_hours"])).date().isoformat()}


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
    refs_all = cfg["compute"]["plan_references"]
    refs_exp = [r for r in refs_all if not r.get("expected_excluded_at_twin")]
    cases = {"expected": tuple(exp), "upper": tuple(cm["plan_upper"])}
    # D0019: the expected set excludes the references expected to stop at their twin (TwinError in prepare(), before any
    # solve: no job at all); 'if_all_counted' prices the set as if none were excluded
    out["scenario"] = {"cases": f"references expected to be counted: {[r['name'] for r in refs_exp]} (D0019: "
                                f"{[r['name'] for r in refs_all if r.get('expected_excluded_at_twin')]} expected excluded "
                                "at the twin, no solve)", "if_all_counted": [r["name"] for r in refs_all]}
    out["cases"] = {c: _plan_case(refs_exp, v, cm, vm, threads, vcpus, cap, cfg, args) for c, v in cases.items()}
    out["if_all_counted"] = {c: _plan_case(refs_all, v, cm, vm, threads, vcpus, cap, cfg, args) for c, v in cases.items()}
    # the F6(e) spot check of an excluded reference's own stack type, if it were run (the runner does not: Run.drive
    # derives the spot-check types from the references that reach it): calibration, scikit-fem levels 0-2 of the
    # reconstruction and finite-volume levels 1-3, alone on the VM (phase A part) plus phase B for any job above the cap
    out["f6e_spot_check_of_excluded_type"] = {}
    for r in refs_all:
        if r.get("expected_excluded_at_twin"):
            J = [j for j in plan_jobs(r, cm, threads, 0, 0, 0, 0) if j["name"].split(":", 1)[1].startswith(
                ("calibration", "reference:T", "fv:"))]
            out["f6e_spot_check_of_excluded_type"][r["name"]] = _cost_jobs(J, cm, vm, vcpus, cap, overhead=False)
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
        if rc.rid not in gate_only or gates_ok:
            # D0018: an excluded searched reference goes through Run.drive / assemble_rows / evaluate (no driver, no rows,
            # reported); s_ref: Run.drive (s_ref_of) for searched references; dev geometry is on the grid
            refs.append(rc)
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
        if rc.excluded is not None:
            continue
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


# names of the declared sanity checks evaluate() writes per reference ('<name>:<rid>'): the declared check passes iff one
# per-reference check exists for every reference that reached the rows and all pass (declared_sanity)
PER_REF_DECLARED = ("F1b_control", "F1c_band_width", "F6a_own_three_grids", "F6c_energy_balance", "F6c_picard",
                    "F6d_operating_point", "driver_s_ref_matches_rows")


def declared_sanity(checks: list[dict], rep: dict, refs: list[RefCtx], fr: list[dict]) -> list[dict]:
    """The spec's declared sanity checks from the freeze checks ``fr`` and evaluate()'s checks: freeze_hashes (every
    config.freeze file, the reconstruction script included, and the D0018 floor), grid_rule_frozen (file sha256 and key
    for key), thermal_fem_sha256 and metric_params_exact as freeze_checks gives them; the per-reference ones
    (PER_REF_DECLARED) as all-of over the references that reached the rows (a missing one fails); F1a1_F1a2_twin_gates:
    both twin gates computed (booleans) for every such reference (a failed gate excludes the reference, F1(a), it does not
    fail this check; the detail lists the gates); the rest as evaluate() wrote them."""
    out = []
    fm = {c["name"]: c for c in fr}
    cm = {c["name"]: c for c in checks}

    def add(name, ok, value=None, threshold=None, detail=""):
        out.append({"name": name, "passed": bool(ok), "value": value, "threshold": threshold, "detail": str(detail)[:4000]})
    fz = [c for n, c in fm.items() if n.startswith("freeze:") or n == "degrade_power_width_floor"]
    add("freeze_hashes", fz and all(c["passed"] for c in fz), len(fz), None,
        json.dumps({c["name"]: c["passed"] for c in fz}))
    gr = [fm.get("grid_rule_file_sha256"), fm.get("grid_rule_key_for_key")]
    add("grid_rule_frozen", all(c is not None and c["passed"] for c in gr), detail=[c and c["detail"][:200] for c in gr])
    for n in ("thermal_fem_sha256", "metric_params_exact"):
        c = fm.get(n)
        add(n, c is not None and c["passed"], detail=(c or {}).get("detail", "missing"))
    live = [rc.rid for rc in refs if rc.excluded is None and rc.admissible and rc.rid in rep]
    for n in PER_REF_DECLARED:
        per = {rid: cm.get(f"{n}:{rid}") for rid in live}
        add(n, all(c is not None and c["passed"] for c in per.values()), sum(c is None or not c["passed"]
            for c in per.values()), 0, json.dumps({rid: (c or {}).get("passed", "missing") for rid, c in per.items()}))
    gates = {rid: {k: rep[rid]["record"].get(k) for k in ("gate_a1", "gate_a2", "counted")} for rid in live}
    add("F1a1_F1a2_twin_gates", all(isinstance(g["gate_a1"], bool) and isinstance(g["gate_a2"], bool)
                                    for g in gates.values()), sum(not g["counted"] for g in gates.values()), None,
        "per reference (a failed gate excludes it, F1(a), not INVALID): " + json.dumps(gates))
    for n in ("fail_fast_twin_and_D", "F1b_D_definition", "at_least_one_counted_reference", "F6e_stack_type_spot_check",
              "recompute_agrees"):
        c = cm.get(n)
        if c is None:  # _evaluate_d_failed writes no F6(e) or recompute check: no search ran, the run is INVALID anyway
            add(n, False, detail="not reached (the run stopped before it; see F1b_D_definition)")
        else:
            out.append(dict(c))
    return out


def _manifest(workdir: Path, cfg: dict, seed: int) -> None:
    """Resume guard: the workdir belongs to one (config, sealed seed); a rerun with either changed refuses (the result
    files would mix runs).  Only hashes are stored (the seed itself stays sealed)."""
    key = hashlib.sha256(json.dumps(cfg, sort_keys=True, default=str).encode()).hexdigest()
    sk = hashlib.sha256(f"E008-seed:{int(seed)}".encode()).hexdigest()
    p = workdir / "run_manifest.json"
    workdir.mkdir(parents=True, exist_ok=True)
    if p.exists():
        m = json.loads(p.read_text())
        if m.get("config_sha256") != key or m.get("seed_sha256") != sk:
            raise RuntimeError(f"{workdir} holds a run under another config or seed: refusing to resume into it")
        log(f"resuming from {workdir}")
    else:
        p.write_text(json.dumps({"config_sha256": key, "seed_sha256": sk, "created": dt.datetime.now().isoformat()}))


def registered_run(er, cfg: dict, seed: int, workdir: Path, recon=None, fake: dict | None = None, before_drive=None,
                   threads: int | None = None) -> dict:
    """The registered path (D0019).  Order: freeze checks (F3, F6(b)) before any reference is loaded, a failure voids the
    run; config.references in D0010 order through judged_reference (fingerprint first, e008_rules, the entry's
    keep-outs); prepare() per reference with the _quick_ok seed derive_seed(s, 2, i) (TwinError / DegradeError exclude
    that reference, D0018); search seeds derive_seed(s, 0, i) (main) and derive_seed(s, 1, i) (control); Run.drive (D's
    definition first; band solver failures -> INVALID, T0318), assemble_rows, evaluate; rows, metrics and the declared
    sanity checks through ``er`` (mfos.evidence.ExperimentRun).  Every row and the evaluation report carry the label and
    the D0019 deviation.  Resumes from ``workdir`` (result files per solve; run_manifest.json).  ``recon``, ``fake``,
    ``before_drive`` and ``threads``: selftest only (fake reconstruction module, fake solvers, the screens hook)."""
    spec = getattr(er, "spec", {}) or {}
    fr = freeze_checks(cfg)
    if not all(c["passed"] for c in fr):
        for c in declared_sanity([], {}, [], fr)[:4]:
            er.sanity(c["name"], c["passed"], detail=c["detail"])
        raise RuntimeError(f"frozen hashes or values differ: the run is void (F3, F6(b)): "
                           f"{[c['name'] for c in fr if not c['passed']]}")
    entries = cfg.get("references") or []
    if not entries:
        raise RuntimeError("config.references is empty: the reference set of D0010 / D0019 is fixed before registration")
    if len({e.get("kind") for e in entries}) != 1:
        raise RuntimeError("customer and public references are never mixed in one verdict (D0010)")
    tag, label = deviation_tag(cfg), sorted({str(e.get("label")) for e in entries})
    _manifest(workdir, cfg, seed)
    refs = []
    for i, entry in enumerate(entries):
        rc = judged_reference(entry, cfg, recon)
        refs.append(prepare(rc, cfg, int(cfg["quick_ok_draws"]), derive_seed(seed, cfg["seeds"]["purposes"]["quick_ok"], i)))
        log(f"{rc.rid}: twin {rc.twin_rec.get('mode')} excluded {rc.excluded}")
    seeds = {(rc.rid, ns): derive_seed(seed, cfg["seeds"]["purposes"][ns], i)
             for i, rc in enumerate(refs) for ns in ("main", "control")}
    scfg = search_cfg(cfg, False)
    if threads is None:
        threads = thread_count(cfg)[0]
    vm = cfg["compute"]["vm"]
    sched = Scheduler(1e9, 8, threads, fake=fake["job"]) if fake else \
        Scheduler(vm["ram_GB"] * vm["memory_fraction"], vm["vcpus"], threads)
    run = Run(cfg, workdir, sched, smoke=False, threads=threads, fake={"l1": fake["l1"]} if fake else None)
    if before_drive is not None:
        before_drive(refs, seeds, scfg, workdir)
    run.drive(refs, seeds, scfg)
    rows, extra = assemble_rows(run, refs, smoke=False)
    for r in rows:
        r.update(label=" / ".join(label), f3_declared_deviation="D0019 item 2")
    met, checks, rep = evaluate(run, refs, rows, extra, cfg)
    rep.update(label=label, f3_declared_deviation=cfg.get("f3_declared_deviation"), deviation_statement=tag,
               references=[{k: e.get(k) for k in ("reference_id", "reconstruction_sha256", "admissible", "L_term_H")}
                           for e in entries])
    dec = declared_sanity(checks, rep, refs, fr)
    names = {s["name"] for s in spec.get("sanity_checks", [])} or {c["name"] for c in dec}
    for c in dec + [c for c in checks if c["name"] not in {d["name"] for d in dec}] + \
            [c for c in fr if c["name"] not in {d["name"] for d in dec}]:
        v, t = c.get("value"), c.get("threshold")
        er.sanity(c["name"], c["passed"], value=float(v) if _num(v) else None,
                  threshold=float(t) if _num(t) else None, detail=str(c.get("detail", ""))[:4000])
    n_counted = int(met.get("n_counted_references", 0) or 0)
    declared_metrics = [m["name"] for m in spec.get("metrics", [])] or sorted(k for k, v in met.items()
                                                                             if isinstance(v, float))
    for name in declared_metrics:  # interval-form metrics: the band is inside the value (spec: level 0, no CI)
        v = met.get(name, math.nan)
        er.metric(name, float(v) if isinstance(v, (int, float)) else math.nan, n=n_counted, level=0.0)
    er.rows(rows)
    rp = workdir / "evaluation_report.json"
    rp.write_text(json.dumps({"label": label, "f3_declared_deviation": rep["f3_declared_deviation"], "metrics": met,
                              "checks": checks, "declared": dec, "report": rep}, indent=1, default=str))
    er.artifact("evaluation_report.json", rp)
    er.domain(reference=[rc.rid for rc in refs], label=label, stack_type=sorted({rc.stack_type for rc in refs}),
              freq_hz=[float(cfg["em"]["freq_hz"])])
    er.notes = (getattr(er, "notes", "") or "") + f"\nLABEL: {' / '.join(label)}\n{tag}\n"
    missing = names - {c["name"] for c in dec} - {c["name"] for c in checks}
    if missing:
        raise RuntimeError(f"declared sanity checks not written: {sorted(missing)}")
    return {"metrics": met, "checks": checks, "declared": dec, "report": rep, "rows": rows, "refs": refs, "run": run}


def full(workdir: str | None = None) -> int:
    from mfos.evidence import ExperimentRun
    with ExperimentRun(experiment_id=EID) as er:
        if er.seed is None:
            raise RuntimeError("E008 needs the sealed seed (spec sealed_seed: true)")
        wd = Path(workdir or os.environ.get("E008_WORKDIR") or (er.run_dir / "work"))
        registered_run(er, er.config, int(er.seed), wd)
    return 0


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
    ap.add_argument("--check-references", action="store_true")
    ap.add_argument("--out")
    ap.add_argument("--verbose", action="store_true")
    a = ap.parse_args(argv)
    os.chdir(ROOT)
    if a.child:
        return child_main(a.child)
    if a.selftest:
        return selftest()
    if a.verify_freeze:
        return verify_freeze()
    if a.check_references:
        return check_references(load_spec()["config"], a.out)
    if a.plan:
        return plan(a, load_spec()["config"])
    if a.dev:
        return dev(a)
    return full(a.workdir)


if __name__ == "__main__":
    sys.exit(main())
