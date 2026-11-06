"""O007 development study 3 (T0243): pre-registered re-freeze of T0228 candidate 1 with GridRule.amg_gs_sweeps = 2.

Pre-registration: research/notes/o007-dev-study3.md section 0, committed before any solve of this study; its hash is
recorded in research/o007_dev3/preregistration.json and copied to dev_study.json as ``preregistration_commit``.
Research only: moduleforge.solvers.thermal_fem is used unchanged. The production option GridRule.amg_gs_sweeps (T0242)
is the only difference from T0228's candidate 1; every solve carries it through the GridRule (no patching of
``_sa_solver``). Reused by import, read-only: o007_dev_study2 (T0228: Runner2 and its memory gate, the worker body, the
per-case / per-layout extensions, the constant-k CG gate, the E009 cost table and FV rows), and through it
o007_dev_study (T0207) and o007_probe (T0225). Their module attributes are re-bound to this study's candidate, rule and
cache by ``_bind`` (nothing in those files is edited).

No reuse: every level of every problem is solved again in this study's cache (research/o007_dev3/cache/). T0228's cache
(research/o007_dev2/cache/) is read only by the consistency diagnostic (sec. 0.5 of the note; never a criterion) and by
the burst plan's wall estimate (T0228's measured L2 wall x the two-sweep wall ratio measured here) [S].

Modes
  --plan     grid-only: DOF counts of every problem and level, and line-for-line identity of each grid with T0228's
             (amg_gs_sweeps does not touch the grid) -> research/o007_dev3/plan.json (no solve)
  (default)  local study under the T0207/T0228 memory rule (one child process at a time, <= 5 GB, or <= 10 GB when
             memory_pressure shows >= 50 % free and swap < 4 GB; watchdog at 10 GB RSS / 8 GB swap); then --report
  --full     the same at every level under 0.85 x physical memory (founder burst), then --report:
             scripts/burst_gcp.sh --cmd "uv run python research/scripts/o007_dev_study3.py --full" research/o007_dev3
  --report   deterministic: apply the pre-registered rule to this study's cache -> dev_study.json, frozen_config.json,
             plan.json (burst list)
  --worker   internal: one solve
SI units, kelvin, float64. Estimator: mfos.metrics.gci_capped (O006 A4, D0012/D0013; Roache 1998 ch. 5), floor 1e-3 K.
"""
from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import math
import statistics
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "research" / "scripts")]

import o007_dev_study2 as D2  # noqa: E402  (T0228 machinery, read-only use)

DS, PR, FEM = D2.DS, D2.PR, D2.FEM
OUT = ROOT / "research" / "o007_dev3"
CACHE = OUT / "cache"
PREREG = OUT / "preregistration.json"
NOTE = ROOT / "research" / "notes" / "o007-dev-study3.md"
CID = "a_q1h4_graded_gs2"
AMG_GS_SWEEPS = 2  # the founder's value (I0128); not tuned
T0228_CID, T0228_CACHE, T0228_DIR = D2.CID, D2.CACHE, D2.OUT  # captured before _bind
T0228_RULE = D2.rule_of(D2.CID)
CANDIDATES = {CID: {**D2.CANDIDATES[D2.CID], "amg_gs_sweeps": AMG_GS_SWEEPS}}  # sec. 0.1: candidate 1 + two sweeps
FROZEN_FREE = ("candidate_id", "feasible", "levels_missing", "rationale")  # the only keys that may differ from T0228
BURST_COMMAND = 'scripts/burst_gcp.sh --cmd "uv run python research/scripts/o007_dev_study3.py --full" research/o007_dev3'
CONSIST_FLAG_K = 1e-6  # sec. 0.5: diagnostic flag where the Picard counts agree (not a criterion, not a gate)


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def rule_of(cid: str) -> FEM.GridRule:
    c = CANDIDATES[cid]
    return FEM.GridRule(h0=c["h0_m"], nz={}, default_nz=DS.NZ_MIN, zrefine=True, near_margin=c["near_margin_m"],
                        element_order=c["element_order"], dz_max=c["dz_max_m"], edge_grading=tuple(c["edge_grading"]),
                        amg_gs_sweeps=c["amg_gs_sweeps"])


# the rule is T0228's rule with the smoother option and nothing else
assert rule_of(CID) == dataclasses.replace(T0228_RULE, amg_gs_sweeps=AMG_GS_SWEEPS), "rule differs from T0228 + gs2"


def _bind() -> None:
    """Route the T0207 / T0228 helpers to this study's candidate, rule and cache (module attributes only)."""
    for m in (DS, D2):
        m.CANDIDATES, m.rule_of, m.CACHE, m.OUT = CANDIDATES, rule_of, CACHE, OUT
    D2.CID, D2.PREREG, D2.BURST_COMMAND = CID, PREREG, BURST_COMMAND


_bind()


# ------------------------------------------------------------------------------------------------ worker
def worker(spec_path: str) -> int:
    """T0228's worker body (D2.worker), then the production meta of the outermost result: amg_gs_sweeps (must be 2),
    cg_max_iterations and linear_rel_residual_max (T0222)."""
    rc = D2.worker(spec_path)
    spec = json.loads(Path(spec_path).read_text())
    m = D2._LAST["r"].meta
    out = json.loads(Path(spec["out"]).read_text())
    out.update(amg_gs_sweeps=m.get("amg_gs_sweeps"), rule_amg_gs_sweeps=DS.rule_of(spec["cid"]).amg_gs_sweeps,
               cg_max_iterations=int(m["cg_max_iterations"]), linear_rel_residual_max=float(m["linear_rel_residual_max"]),
               cg_hit_maxiter=bool(m["cg_hit_maxiter"]))
    if out["amg_gs_sweeps"] != AMG_GS_SWEEPS:
        out["status"] = "failed_amg_gs_sweeps"
        Path(spec["out"]).write_text(json.dumps(out))
        return 5
    Path(spec["out"]).write_text(json.dumps(out))
    return rc


# ------------------------------------------------------------------------------------------------ orchestration
class Runner3(D2.Runner2):
    """T0228's Runner2 (memory gate, calibration, level loop, constant-k nulls); the child is this script's worker."""

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
            st = {3: "killed_memory", 4: "killed_swap", 5: "failed_amg_gs_sweeps"}.get(pr.returncode, "failed")
            rec = {"status": st, "returncode": pr.returncode, "dofs": dofs, "est_gb": est_gb,
                   "wall_s": time.perf_counter() - t0, "stderr_tail": (pr.stdout + pr.stderr)[-3000:],
                   "spec": {k: v for k, v in spec.items() if k != "kconst"}}
            path.write_text(json.dumps(rec))
            log(f"  {st.upper()} {key}: rc {pr.returncode}: {rec['stderr_tail'][-300:]}")
            return rec
        d = json.loads(path.read_text())
        log(f"  done {key}: {d['dofs']} DOF, {D2.proc_wall(d):.1f} s, peak {d['peak_rss_bytes'] / 1e9:.2f} GB, "
            f"CG max {DS.cg_max(d)} (meta {d['cg_max_iterations']}), amg_gs_sweeps {d['amg_gs_sweeps']}, "
            f"eb {d['energy_balance']:.1e}")
        return d


def _prereg_commit() -> str:
    return json.loads(PREREG.read_text())["preregistration_commit"] if PREREG.exists() else "MISSING"


def study(full: bool) -> None:
    c = _prereg_commit()
    if c == "MISSING":
        raise SystemExit("no pre-registration record: commit note sec. 0 and write preregistration.json first")
    try:
        anc = subprocess.run(["git", "merge-base", "--is-ancestor", c, "HEAD"], cwd=ROOT, capture_output=True).returncode
        log(f"pre-registration commit {c}: ancestor of HEAD: {anc == 0}")
        if anc == 1:
            raise SystemExit(f"pre-registration commit {c} is not an ancestor of HEAD")
    except OSError:
        log(f"pre-registration commit {c}: git unavailable, ancestry not checked")
    ser, mms, hashes = DS.load_refs()
    log(f"references verified: {hashes['series_sha256'][:8]} / {hashes['mms_sha256'][:8]}")
    for n in DS.LAYOUTS:
        log(f"dev layout {n}: fingerprint {DS.dev_layout(n).fingerprint()[:12]} (E006 spec)")
    CACHE.mkdir(parents=True, exist_ok=True)
    Runner3(ser, mms, full).study([CID], list(DS.CASES + DS.LAYOUTS))


# ------------------------------------------------------------------------------------------------ analysis
def _records(prob: str) -> list[tuple[str, dict]]:
    """Every solve of one problem in this study's cache (level runs, calibration, constant-k), by cache key."""
    out = []
    for p in sorted(CACHE.glob(f"{CID}__{prob}__L*.json")):
        if not p.name.endswith(".spec.json"):
            out.append((p.stem, json.loads(p.read_text())))
    return out


def t0228_result(prob: str, lv: int, var: str = "kT") -> dict | None:
    """T0228's record of one solve (its cache, read only; DS.Runner.result's logic on T0228's paths)."""
    if prob in DS.LAYOUTS and lv == 0 and var == "kT":
        cp = T0228_CACHE / f"{T0228_CID}__{prob}__calibration.json"
        c = json.loads(cp.read_text()) if cp.exists() else {}
        if c.get("status") != "ok":
            return None
        p = T0228_CACHE / f"{T0228_CID}__{prob}__L0__kT{c['l0_tag']}.json"
    else:
        p = T0228_CACHE / f"{T0228_CID}__{prob}__L{lv}__{var}.json"
    d = json.loads(p.read_text()) if p.exists() else None
    return d if d and d.get("status") == "ok" else None


def _values(d: dict, prob: str) -> dict:
    if prob in DS.LAYOUTS:
        v = {f"die{i}_tj_max": t for i, t in enumerate(d["tj_max"])}
        v |= {f"die{i}_tj_mean": t for i, t in enumerate(d["tj_mean"])}
        v |= {f"die{i}_centroid_node": c["T"] for i, c in enumerate(d.get("centroid_nodes", []))}
        return v
    return {(p["id"] if prob == "mms" else f"{p['source']}/{p['point']}"): p["T"] for p in d["points"]}


def consistency(prob: str, levels: list[int]) -> dict:
    """Sec. 0.5 diagnostic: |T_new - T_T0228| per level and reported value wherever T0228 measured it, with both Picard
    counts; flagged above 1e-6 K where the Picard counts agree. Never a criterion or a gate."""
    rows, cg = [], []
    pairs = [(lv, "kT") for lv in levels]
    pairs += [(lv, "constk") for lv in DS.LEVELS if (DS.Runner.result(CID, prob, lv, "constk") or {}).get("status") == "ok"]
    for lv, var in pairs:
        a, b = DS.Runner.result(CID, prob, lv, var), t0228_result(prob, lv, var)
        if not (a and a.get("status") == "ok" and b):
            continue
        va, vb = _values(a, prob), _values(b, prob)
        same_p = int(a["picard_iters"]) == int(b["picard_iters"])
        cg.append({"level": lv, "variant": var, "cg_max_new": DS.cg_max(a), "cg_max_T0228": DS.cg_max(b),
                   "cg_ratio": DS.cg_max(a) / DS.cg_max(b), "picard_new": a["picard_iters"],
                   "picard_T0228": b["picard_iters"], "power_W_new": a.get("power_W"), "power_W_T0228": b.get("power_W"),
                   "platform_T0228": b.get("platform"), "wall_ratio": D2.proc_wall(a) / D2.proc_wall(b)
                   if a.get("platform") == b.get("platform") else None})
        for k in sorted(set(va) & set(vb)):
            dt = abs(va[k] - vb[k])
            rows.append({"level": lv, "variant": var, "value": k, "T_new_K": va[k], "T_T0228_K": vb[k], "abs_dT_K": dt,
                         "picard_new": a["picard_iters"], "picard_T0228": b["picard_iters"],
                         "flag": bool(dt > CONSIST_FLAG_K and same_p)})
    return {"n_compared": len(rows), "max_abs_dT_K": max((r["abs_dT_K"] for r in rows), default=None),
            "n_flagged": sum(r["flag"] for r in rows), "flag_tol_K": CONSIST_FLAG_K, "per_solve": cg, "rows": rows}


def extend3(v: dict, prob: str) -> dict:
    """This study's per-record additions: amg_gs_sweeps from the production meta of every solve of the problem, the
    T0222 counters per level and per solve, reused_levels, and the consistency diagnostic."""
    recs = _records(prob)
    ok = [(k, d) for k, d in recs if d.get("status") == "ok"]
    amg = sorted({str(d.get("amg_gs_sweeps")) for _, d in ok})
    v["amg_gs_sweeps"] = AMG_GS_SWEEPS if amg == [str(AMG_GS_SWEEPS)] else amg
    runs = [DS.Runner.result(CID, prob, lv) for lv in v["levels_run"]]
    v["cg_max_iterations_per_level"] = [d["cg_max_iterations"] for d in runs]
    v["linear_rel_residual_max_per_level"] = [d["linear_rel_residual_max"] for d in runs]
    v["solves"] = [{"key": k, "status": d.get("status"), "dofs": d.get("dofs"), "cg_only_max": DS.cg_max(d),
                    "cg_max_iterations": d.get("cg_max_iterations"), "linear_rel_residual_max": d.get("linear_rel_residual_max"),
                    "amg_gs_sweeps": d.get("amg_gs_sweeps"), "picard_iters": d.get("picard_iters"),
                    "process_wall_s": D2.proc_wall(d) if d.get("status") == "ok" else None,
                    "peak_rss_GB": d["peak_rss_bytes"] / 1e9 if d.get("status") == "ok" else None,
                    "platform": d.get("platform")} for k, d in recs]
    v["reused_levels"] = sorted({d["spec"]["level"] for _, d in ok if d.get("reuse") or d["spec"].get("reused_from_T0225")})
    v["consistency_vs_T0228"] = consistency(prob, v["levels_run"])
    return v


def protocol(cases: dict, lays: dict) -> dict:
    """Sec. 0.3 protocol conditions (validity, not eligibility): every solve with 2 sweeps, no reuse, counters agree."""
    allv = {**cases, **lays}
    amg_bad = sorted(k for k, v in allv.items() if v["amg_gs_sweeps"] != AMG_GS_SWEEPS and v["levels_run"])
    reuse = sorted(k for k, v in allv.items() if v["reused_levels"])
    mism = sorted(k for k, v in allv.items() if any(x not in (0, None) for x in v.get("meta_cg_max_abs_mismatch", [])))
    return {"amg_gs_sweeps_not_2": amg_bad, "reused": reuse, "cg_counter_mismatch": mism,
            "ok": not (amg_bad or reuse or mism)}


def guard(cases: dict, lays: dict) -> dict:
    """E009 K1/K2 regression guard (sec. 0.6): dev A1 / A2 / A4 per problem at the finest level run, L2 marked."""
    rows = {k: {"level": c["levels_run"][-1] if c["levels_run"] else None, "at_L2": c["levels_run"] == [0, 1, 2],
                "A1_scaled_err": c.get("max_scaled_err"), "A2_abs_err_K": c.get("max_abs_err_K"),
                "A4_gci_K": c.get("max_gci_K")} for k, c in cases.items()}
    rows |= {k: {"level": v["levels_run"][-1] if v["levels_run"] else None, "at_L2": v["levels_run"] == [0, 1, 2],
                 "A4_gci_K": v.get("max_gci_K")} for k, v in lays.items()}
    l2 = [r for r in rows.values() if r["at_L2"]]
    return {"per_problem": rows, "K1_threshold": DS.THRESH["K1"], "K2_threshold_K": DS.THRESH["K2_K"],
            "A1_max_at_L2": max((r["A1_scaled_err"] for r in l2 if "A1_scaled_err" in r), default=None),
            "A2_max_at_L2_K": max((r["A2_abs_err_K"] for r in l2 if "A2_abs_err_K" in r), default=None),
            "A4_max_at_L2_K": max((DS._gnum(r["A4_gci_K"]) for r in l2), default=None),
            "complete_at_L2": all(r["at_L2"] for r in rows.values())}


def frozen_config(feasible: bool, missing: dict, why: str, prereg: str) -> dict:
    """T0228's frozen_config.json copied key for key (only FROZEN_FREE may differ), plus amg_gs_sweeps. Every copied
    value is checked against this candidate and the production constants first."""
    c2 = json.loads((T0228_DIR / "frozen_config.json").read_text())
    c = CANDIDATES[CID]
    expect = {"element_order": c["element_order"], "h0_m": c["h0_m"], "near_margin_m": c["near_margin_m"],
              "dz_max_m": c["dz_max_m"], "nz_min": DS.NZ_MIN,
              "edge_grading": dict(zip(("first_offset_m", "ratio", "max_offset_m", "min_gap_fraction"), c["edge_grading"],
                                       strict=True)),
              "refinement_ratio": FEM.REFINEMENT_RATIO, "snap_fraction": FEM.SNAP_FRACTION, "amg_seed": FEM.AMG_SEED,
              "linear_rtol": FEM.LINEAR_RTOL, "cg_maxiter": FEM.CG_MAXITER, "cg_eligibility_limit": DS.CG_FLAG,
              "picard_tol_K": FEM.PICARD_TOL_K, "levels": list(DS.LEVELS)}
    bad = {k: (c2.get(k), v) for k, v in expect.items() if c2.get(k) != v}
    if bad:
        raise SystemExit(f"T0228 frozen_config differs from candidate / production constants: {bad}")
    out = {k: v for k, v in c2.items() if k not in FROZEN_FREE}
    out.update(amg_gs_sweeps=AMG_GS_SWEEPS, candidate_id=CID, feasible=feasible, levels_missing=missing,
               rationale=f"{why}. Pre-registered rule: research/notes/o007-dev-study3.md sec. 0 (commit {prereg}); T0228 "
                         f"candidate 1 (research/o007_dev2/frozen_config.json) key for key plus amg_gs_sweeps = 2.")
    return out


def report() -> int:
    ser, mms, hashes = DS.load_refs()
    cases = {p: extend3(D2.extend_case(DS.analyse_case(CID, p, ser, mms), p), p) for p in DS.CASES}
    lays = {n: extend3(D2.extend_layout(DS.analyse_layout(CID, n), n), n) for n in DS.LAYOUTS}
    s = DS.summarise(CID, cases, lays)
    D2._gate_constant_k(s)
    plan = D2.e009_table(ser, mms)
    pc = protocol(cases, lays)
    allv = list(cases.values()) + list(lays.values())
    complete = all(v["levels_run"] == [0, 1, 2] for v in allv)
    s.update(fits_burst=plan["fits_burst"], protocol_ok=pc["ok"], all_levels_measured=complete)
    feasible = bool(s["eligible"] and plan["fits_burst"] and pc["ok"] and complete)
    missing = {k: [lv for lv in DS.LEVELS if lv not in v["levels_run"]] for k, v in {**cases, **lays}.items()}
    missing = {k: v for k, v in missing.items() if v}
    if feasible:
        why = "candidate a_q1h4_graded_gs2 verified eligible on every criterion at level 2 (sec. 0.2); only candidate"
    elif s["ruled_out"]:
        why = f"candidate a_q1h4_graded_gs2 ruled out by measured data: {s['verdict']}"
    elif not pc["ok"]:
        why = f"protocol condition violated (sec. 0.3): {pc}"
    else:
        why = f"not yet verifiable: level 2 missing on {sorted(missing)} (founder burst: {BURST_COMMAND})"
    prereg = _prereg_commit()
    c = CANDIDATES[CID]
    study_out = {
        "task": "T0243", "objective": "O007", "preregistration_commit": prereg,
        "meta": {"references": hashes, "dev_seed": DS.DEV_SEED,
                 "thermal_fem_sha256": hashlib.sha256((ROOT / "src/moduleforge/solvers/thermal_fem.py").read_bytes()).hexdigest(),
                 "margins": DS.MARGIN, "thresholds": DS.THRESH, "cg_flag": DS.CG_FLAG, "cg_cap": DS.CG_CAP,
                 "burst_command": BURST_COMMAND, "grading": list(c["edge_grading"]), "amg_gs_sweeps": AMG_GS_SWEEPS,
                 "baseline": {"task": "T0228", "candidate": T0228_CID, "cache": str(T0228_CACHE.relative_to(ROOT))}},
        "reuse_check": {"status": "no reuse (sec. 0.3)", "levels_reused": {k: v["reused_levels"] for k, v in
                                                                           {**cases, **lays}.items()}, "ok": not pc["reused"]},
        "protocol": pc,
        "chosen": {"id": CID, "feasible": feasible, "why": why, "levels_missing": missing, "summary": s,
                   "cases": cases, "layouts": lays, "e009_plan": plan, "e009_regression_guard": guard(cases, lays),
                   "consistency_vs_T0228": {k: {x: v["consistency_vs_T0228"][x] for x in ("n_compared", "max_abs_dT_K",
                                                                                         "n_flagged")}
                                            for k, v in {**cases, **lays}.items()}},
        "candidates_considered": [CID]}
    (OUT / "dev_study.json").write_text(json.dumps(study_out, indent=1, default=float, sort_keys=True))
    frozen = frozen_config(feasible, missing, why, prereg)
    (OUT / "frozen_config.json").write_text(json.dumps(frozen, indent=1, default=float, sort_keys=True))
    write_plan(ser, mms)
    log(f"{CID}: feasible={feasible}; {why}")
    log(f"  summary {json.dumps(s, default=float)}")
    return 0


# ------------------------------------------------------------------------------------------------ plan
def grid_with(rule, prob: str, lv: int, ser: dict, mms: dict):
    """DS.grid_of with an explicit rule (T0228's or this study's)."""
    if prob in DS.BOX:
        b = DS.box_problem(ser, prob)
        return FEM.box_stack_grid(b["a"], b["b"], b["layers"], b["h"], b["Tc"], b["srcs"], rule=rule, level=lv,
                                  extra_lines=b["extra"])
    if prob == "mms":
        return FEM.layout_grid(DS.R.mms_layout(), 0.0, 1.0, DS.MMS_TC, rule, lv, DS.mms_extra(mms))
    return FEM.layout_grid(DS.dev_layout(prob), 1.0, DS.H_OP, DS.COOLANT_K, rule, lv)


def grid_rows(ser: dict, mms: dict) -> list[dict]:
    bpd = D2.bpd_max(1)
    rows = []
    for prob in DS.CASES + DS.LAYOUTS:
        for lv in DS.LEVELS:
            g, g0 = grid_with(rule_of(CID), prob, lv, ser, mms), grid_with(T0228_RULE, prob, lv, ser, mms)
            same = {a: bool(np.array_equal(getattr(g, a), getattr(g0, a))) for a in ("x", "y", "z", "mat")}
            n = DS.count_dofs(g)
            est = n * bpd * PR.EST_MARGIN / 1e9
            rows.append({"problem": prob, "level": lv, "dofs": n, "cells": list(g.mat.shape),
                         "grid_amg_gs_sweeps": g.amg_gs_sweeps, "identical_to_T0228_grid": same,
                         "min_cell_ratio_lateral": DS.min_cell_ratio(g), "local_est_GB": est,
                         "local": "yes" if est <= DS.LOCAL_SOFT_GB else "if memory_pressure allows"
                         if est <= DS.LOCAL_HARD_GB else "no (burst)"})
            log(f"{prob} L{lv}: {n} DOF, est {est:.1f} GB, {rows[-1]['local']}, identical to T0228 {same}")
            del g, g0
    return rows


def _wall_ratio() -> dict:
    """Two-sweep wall ratio measured locally: process wall of this study / T0228 on the same platform, L1 k(T) solves
    (the largest local solves of both studies)."""
    r = []
    for prob in DS.CASES + DS.LAYOUTS:
        a, b = DS.Runner.result(CID, prob, 1), t0228_result(prob, 1)
        if a and a.get("status") == "ok" and b and a.get("platform") == b.get("platform"):
            r.append({"problem": prob, "wall_new_s": D2.proc_wall(a), "wall_T0228_s": D2.proc_wall(b),
                      "ratio": D2.proc_wall(a) / D2.proc_wall(b)})
    rs = [x["ratio"] for x in r]
    return {"per_problem_L1": r, "median": statistics.median(rs) if rs else None, "max": max(rs) if rs else None,
            "used": max(rs) if rs else 1.10,
            "basis": "measured max over L1 solves" if rs else "founder diagnostic +7-10 % (no local L1 yet) [S]"}


def burst_list(ser: dict, mms: dict) -> list[dict]:
    """Every solve the burst must run: each level run or constant-k null of sec. 0.2 not 'ok' in this study's cache.
    Memory: T0228's burst-measured peak of the same solve (the GS smoother adds no stored operator [I]) and the local
    estimate rule (criterion 4); wall: T0228's measured wall of that solve x the measured two-sweep ratio [S]."""
    wr = _wall_ratio()["used"]
    bpd = D2.bpd_max(1)
    want = [(p, lv, "kT") for p in DS.CASES + DS.LAYOUTS for lv in DS.LEVELS]
    want += [(p, 2, "constk") for p in ("mms", *DS.LAYOUTS)]
    rows = []
    for prob, lv, var in want:
        if prob in DS.LAYOUTS and lv == 0:
            done = (DS.Runner.result(CID, prob, 0) or {}).get("status") == "ok"
        else:
            done = (DS.Runner.result(CID, prob, lv, var) or {}).get("status") == "ok"
        if done:
            continue
        n = DS.count_dofs(DS.grid_of(CID, prob, lv, ser, mms))
        b = t0228_result(prob, lv, var)
        rows.append({"solve": f"{CID}__{prob}__L{lv}__{var}", "dofs": n, "est_GB_rule": n * bpd * PR.EST_MARGIN / 1e9,
                     "T0228_peak_GB": b["peak_rss_bytes"] / 1e9 if b else None,
                     "T0228_platform": b.get("platform") if b else None,
                     "T0228_wall_s": D2.proc_wall(b) if b else None,
                     "est_wall_s": D2.proc_wall(b) * wr if b else None,
                     "basis": "[S] T0228 measured (same solve, burst) x two-sweep wall ratio" if b else "[S] no T0228 record"})
    return rows


def write_plan(ser: dict, mms: dict) -> None:
    p = OUT / "plan.json"
    old = json.loads(p.read_text()) if p.exists() else {}
    rows = old.get("rows") or grid_rows(ser, mms)
    bl = burst_list(ser, mms)
    walls = [r["est_wall_s"] for r in bl if r["est_wall_s"] is not None]
    peaks = [r["T0228_peak_GB"] for r in bl if r["T0228_peak_GB"] is not None]
    OUT.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({
        "task": "T0243", "candidate": CID, "amg_gs_sweeps": AMG_GS_SWEEPS, "grading": list(CANDIDATES[CID]["edge_grading"]),
        "local_est_margin": PR.EST_MARGIN, "burst_command": BURST_COMMAND,
        "burst_note": "Run after this branch is merged (the bundle defaults to main) or with MF_REF=<branch>; the burst "
                      "resumes from the committed cache and runs only the solves listed in burst_solves.",
        "rows": rows, "burst_solves": bl, "two_sweep_wall_ratio": _wall_ratio(),
        "burst_totals": {"n_solves": len(bl), "est_wall_h_sum": sum(walls) / 3600.0 if walls else None,
                         "max_T0228_peak_GB": max(peaks) if peaks else None,
                         "max_est_GB_rule": max((r["est_GB_rule"] for r in bl), default=None),
                         "recommended_timeout_h": math.ceil(3.0 * sum(walls) / 3600.0) if walls else None,
                         # post-data addition (note sec. 7), plan output only: --full skips a solve whose rule estimate
                         # exceeds 0.85 x physical memory, so the burst machine needs at least this much
                         "min_physical_GB_for_full_gate": max((r["est_GB_rule"] for r in bl), default=0.0) / 0.85}},
        indent=1, default=float, sort_keys=True))


def plan() -> int:
    ser, mms, _ = DS.load_refs()
    p = OUT / "plan.json"
    if p.exists():
        p.unlink()
    write_plan(ser, mms)
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
