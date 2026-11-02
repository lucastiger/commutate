"""O006 pilot P4 (T0155): run FastHenry 3.0wr on the Case 4 decks of fh_export.py (research, NOT evidence, O006 F4).

FastHenry is the provisioned external binary (D0002: built outside the uv environment by scripts/provision_compute.sh;
resolved from MF_FASTHENRY_BIN, then PATH, then ~/.local/bin).  Every run executes in a fresh temporary directory; a run
counts only if the process exits 0 and Zc.mat parses with both frequencies (D0002: never parse Zc.mat of a crashed run).
Peak memory is the child's ru_maxrss from os.wait4 (bytes on macOS); a watchdog polls RSS with ps and kills the run above
--mem-cap-mb or after --timeout-s.  Each finished run is appended to research/o006_p4/runs.jsonl (resumable).

Modes: direct = ``-s ludecomp -m direct`` (dense LU); multipole = ``-s iterative -m multi -t TOL`` (FastHenry's
default preconditioner and expansion order).  A direct run whose estimated dense memory exceeds the cap is recorded as
``not_run`` with the estimate.

    uv run python research/scripts/o006_p4/run_fh.py --binary-check
    uv run python research/scripts/o006_p4/run_fh.py --plan ladder [--only-geometry case4_base]
    uv run python research/scripts/o006_p4/run_fh.py --summarise      # -> research/o006_p4/results.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fh_export as fx  # noqa: E402

ROOT = fx.ROOT
OUT = ROOT / "research" / "o006_p4"
RUNS = OUT / "runs.jsonl"

# Refinement plan, fixed before the first Case 4 solve (see research/notes/o006-p4-fasthenry-feasibility.md §2).
# Lateral ladder (ratio 2 in trace cell, plane cell and wire segmentation) at fixed thickness filaments nh = 3, rh = 2.
LEVELS = {
    "k0": fx.FHLevel(cell_mm=1.0, plane_cell_mm=4.0, nh_trace=3, nh_plane=3, wire_n=2, wire_sub=1),
    "k1": fx.FHLevel(cell_mm=0.5, plane_cell_mm=2.0, nh_trace=3, nh_plane=3, wire_n=2, wire_sub=2),
    "k2": fx.FHLevel(cell_mm=0.25, plane_cell_mm=1.0, nh_trace=3, nh_plane=3, wire_n=2, wire_sub=4),
    # thickness study at k0's lateral mesh
    "k0_nh1": fx.FHLevel(cell_mm=1.0, plane_cell_mm=4.0, nh_trace=1, nh_plane=1, wire_n=2, wire_sub=1),
    "k0_nh5": fx.FHLevel(cell_mm=1.0, plane_cell_mm=4.0, nh_trace=5, nh_plane=5, wire_n=2, wire_sub=1),
    "k0_nh9": fx.FHLevel(cell_mm=1.0, plane_cell_mm=4.0, nh_trace=9, nh_plane=9, wire_n=2, wire_sub=1),
    # POST-HOC diagnostic (added after the ladder results; never used in the estimators): k0 with k1's plane pitch
    "k0_p2": fx.FHLevel(cell_mm=1.0, plane_cell_mm=2.0, nh_trace=3, nh_plane=3, wire_n=2, wire_sub=1),
    # direct-solve ladder (thin: nh = 1) for the direct vs multipole comparison
    "d0": fx.FHLevel(cell_mm=1.0, plane_cell_mm=4.0, nh_trace=1, nh_plane=1, wire_n=1, wire_sub=1),
    "d1": fx.FHLevel(cell_mm=1.0, plane_cell_mm=2.0, nh_trace=1, nh_plane=1, wire_n=1, wire_sub=1),
    "d2": fx.FHLevel(cell_mm=0.5, plane_cell_mm=2.0, nh_trace=1, nh_plane=1, wire_n=1, wire_sub=2),
}
PLANS = {
    "solver": [("direct", "d0"), ("multipole", "d0"), ("direct", "d1"), ("multipole", "d1"), ("direct", "d2"),
               ("multipole", "d2")],
    "ladder": [("multipole", "k0"), ("multipole", "k1"), ("multipole", "k2")],
    "thickness": [("multipole", "k0_nh1"), ("multipole", "k0_nh5"), ("multipole", "k0_nh9")],
    "main": [("multipole", "k0"), ("multipole", "k0_nh1"), ("multipole", "k0_nh5"), ("multipole", "k0_nh9"),
             ("multipole", "k1"), ("multipole", "k2")],
    "solver_o4": [("multipole", "d0"), ("multipole", "d1")],
    "posthoc": [("multipole", "k0_p2")],
}


def binary() -> str:
    for cand in (os.environ.get("MF_FASTHENRY_BIN"), shutil.which("fasthenry"), str(Path.home() / ".local/bin/fasthenry")):
        if cand and Path(cand).is_file() and os.access(cand, os.X_OK):
            return cand
    raise FileNotFoundError("FastHenry not provisioned (scripts/provision_compute.sh, D0002)")


def _rss_mb(pid: int) -> float:
    try:
        out = subprocess.run(["ps", "-o", "rss=", "-p", str(pid)], capture_output=True, text=True, timeout=5).stdout
        return float(out.strip() or 0) / 1024
    except Exception:
        return 0.0


def run_deck(deck: str, args: list[str], timeout_s: float, mem_cap_mb: float) -> dict:
    d = Path(tempfile.mkdtemp(prefix="fh_", dir=os.environ.get("TMPDIR")))
    (d / "deck.inp").write_text(deck)
    log = open(d / "run.log", "w")
    t0 = time.perf_counter()
    p = subprocess.Popen([binary(), "deck.inp", *args], cwd=d, stdout=log, stderr=subprocess.STDOUT)
    peak_poll, killed, status_code, ru = 0.0, None, None, None
    while True:
        pid, st, ru = os.wait4(p.pid, os.WNOHANG)
        if pid == p.pid:
            status_code = st
            break
        rss = _rss_mb(p.pid)
        peak_poll = max(peak_poll, rss)
        el = time.perf_counter() - t0
        if rss > mem_cap_mb or el > timeout_s:
            killed = "killed_memory" if rss > mem_cap_mb else "timeout"
            p.send_signal(signal.SIGKILL)
        time.sleep(0.5)
    p.returncode = 0  # reaped by wait4
    wall = time.perf_counter() - t0
    log.close()
    text = (d / "run.log").read_text(errors="replace")
    rec = {"wall_s": wall, "peak_mem_mb": max(ru.ru_maxrss / 2**20, peak_poll), "cpu_s": ru.ru_utime + ru.ru_stime,
           "log_tail": text[-600:]}
    if killed:
        rec["status"] = killed
    elif os.WIFSIGNALED(status_code):
        rec["status"], rec["signal"] = "crash", os.WTERMSIG(status_code)
    elif os.WEXITSTATUS(status_code) != 0:
        rec["status"], rec["exit"] = "crash", os.WEXITSTATUS(status_code)
    else:
        z = fx.parse_zc((d / "Zc.mat").read_text()) if (d / "Zc.mat").exists() else {}
        if len(z) != 2:
            rec["status"] = "parse_error"
        else:
            rec["status"] = "ok"
            rec["Z"] = {f"{f:.6g}": [v.real, v.imag] for f, v in sorted(z.items())}
            rec["L_H"] = {f"{f:.6g}": v.imag / (2 * math.pi * f) for f, v in sorted(z.items())}
    shutil.rmtree(d, ignore_errors=True)
    return rec


MULTIPOLE_ORDER = 4  # FastHenry's default (2) read L 0.78 % low vs direct LU on d0; order 4 / 6: -3.5e-4 (note §3.1)


def mode_args(mode: str, tol: float) -> list[str]:
    if mode == "direct":
        return ["-s", "ludecomp", "-m", "direct"]
    return ["-s", "iterative", "-m", "multi", "-t", f"{tol:g}", "-o", str(MULTIPOLE_ORDER)]


def projected_mb(mode: str, nfil: int) -> float | None:
    """Peak memory projected linearly in filaments from the largest completed run of this mode (the ps watchdog
    cannot see the child inside the agent sandbox, so a run is screened before it starts)."""
    if not RUNS.exists():
        return None
    ok = [j for j in map(json.loads, RUNS.read_text().splitlines()) if j["mode"] == mode and j["status"] == "ok"]
    if not ok:
        return None
    big = max(ok, key=lambda j: j["n_filaments"])
    return big["peak_mem_mb"] * nfil / big["n_filaments"]


def binary_check() -> dict:
    """D0002 self-test bar (10 x 1 x 1 mm Cu, 1 kHz): 5.704 nH recorded on the pinned build; 5.695 nH closed form."""
    deck = (".units m\n.default sigma=5.8e7\nN1 x=0 y=0 z=0\nN2 x=0.010 y=0 z=0\nE1 N1 N2 w=0.001 h=0.001 nwinc=1 nhinc=1\n"
            ".external N1 N2\n.freq fmin=1e3 fmax=2e3 ndec=3.3219280982\n.end\n")
    r = run_deck(deck, [], 60, 1000)
    b = binary()
    r.update({"binary": b, "binary_sha256": hashlib.sha256(Path(b).read_bytes()).hexdigest(),
              "L_nH_1kHz": r.get("L_H", {}).get("1000", float("nan")) * 1e9})
    r["pass"] = r["status"] == "ok" and abs(r["L_nH_1kHz"] - 5.704) < 0.0015
    return r


def done_keys() -> set:
    if not RUNS.exists():
        return set()
    return {(j["geometry"], j["mode"], j["level"], j.get("attempt", 1), j.get("order"))
            for j in map(json.loads, RUNS.read_text().splitlines()) if j.get("status") != "aborted"}


def run_plan(plan: str, geoms, timeout_s: float, mem_cap_mb: float, tol: float, retries: int) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    G = fx.case4.geometries()
    have = done_keys()
    for mode, lvl in PLANS[plan]:
        for g in geoms:
            if (g, mode, lvl, 1, None if mode == "direct" else MULTIPOLE_ORDER) in have:
                continue
            deck, facts = fx.export(G[g], LEVELS[lvl], title=f"{g} {lvl}")
            base = {"geometry": g, "mode": mode, "level": lvl, "params": asdict(LEVELS[lvl]), "tol": tol if mode != "direct" else None,
                    "order": MULTIPOLE_ORDER if mode != "direct" else None,
                    "n_filaments": facts["n_filaments"], "n_nodes": facts["n_nodes"], "deck_sha256": facts["deck_sha256"],
                    "direct_mem_est_gb": facts["direct_mem_est_gb"]}
            if mode == "direct" and facts["direct_mem_est_gb"] * 1024 > mem_cap_mb:
                rec = {**base, "attempt": 1, "status": "not_run",
                       "reason": f"estimated dense memory {facts['direct_mem_est_gb']:.1f} GB > cap {mem_cap_mb / 1024:.1f} GB"}
                _append(rec)
                continue
            pm = projected_mb(mode, facts["n_filaments"])
            if mode != "direct" and pm is not None and pm > mem_cap_mb:
                _append({**base, "attempt": 1, "status": "not_run", "projected_mem_mb": pm,
                         "reason": f"projected peak memory {pm / 1024:.1f} GB > cap {mem_cap_mb / 1024:.1f} GB (linear in filaments)"})
                continue
            for attempt in range(1, retries + 2):
                print(f"[{time.strftime('%H:%M:%S')}] {g} {mode} {lvl} attempt {attempt} F={facts['n_filaments']}", flush=True)
                rec = {**base, "attempt": attempt, **run_deck(deck, mode_args(mode, tol), timeout_s, mem_cap_mb)}
                _append(rec)
                print(f"   -> {rec['status']} {rec['wall_s']:.1f} s {rec['peak_mem_mb']:.0f} MB {rec.get('L_H')}", flush=True)
                if rec["status"] != "crash":
                    break


# ---------------------------------------------------------------------------------------------------------- summary
# Estimators and the usability criterion, fixed before the first ladder / thickness run (note §2):
#  lateral (multipole k0 > k1 > k2, r = 2, f1 finest): three levels monotone (e21 e32 > 0, |e21| < |e32|):
#    p = ln(e32/e21)/ln 2, f_ext = f1 + (f1 - f2)/(2^p - 1), GCI = 1.25 |e21|/(2^p - 1); three levels otherwise:
#    f_ext = f1, GCI = 3 max(|e21|, |e32|); two levels: f_ext = f1 + (f1 - f2) (assumed p = 1), GCI = 3 |f2 - f1|.
#  thickness (k0 lateral mesh, nh = 3, 5, 9; nh - 1 doubles): correction D = L(nh9) - L(nh3) added to f_ext;
#    term = 1.25 |t9 - t5|/(2^pt - 1) if monotone-contracting, else 3 max(|t5 - t3|, |t9 - t5|).
#  L_extrap = f_ext + D, abs_est = GCI + term.  Pair ratio R = L_pert / L_base: same formulas on R per level.
#  usable  <=> for every geometry and frequency: (U1) >= 2 lateral levels and all thickness runs completed (a crash
#    that recurs on retry counts as not completed); (U2) multipole within 1e-3 (relative) of direct on every deck run
#    in both modes; (U3) abs_est_FH <= P3's l2_layout abs_est_H (otherwise FastHenry's own discretisation error
#    exceeds the quantity it is meant to check, and D0009's fallback (doubled l2 estimate) is no less informative).
FREQ_KEYS = ("1e+07", "2e+07")


def _lateral(f3, f2, f1):
    if f1 is None:  # finest level not run: two-level estimate on (f3 = coarse, f2 = fine)
        f3, f2, f1 = None, f3, f2
    if f1 is None or f2 is None:
        return None, None, "insufficient"
    if f3 is None:
        return f1 + (f1 - f2), 3 * abs(f2 - f1), "two-level, assumed p=1"
    e21, e32 = f2 - f1, f3 - f2
    if e21 * e32 > 0 and abs(e21) < abs(e32):
        p = math.log(e32 / e21) / math.log(2)
        return f1 + (f1 - f2) / (2**p - 1), 1.25 * abs(e21) / (2**p - 1), f"three-level monotone p_obs={p:.3f}"
    return f1, 3 * max(abs(e21), abs(e32)), "three-level non-monotone"


def _thickness(t3, t5, t9):
    if None in (t3, t5, t9):
        return None, None, "insufficient"
    a, b = t5 - t3, t9 - t5
    if a * b > 0 and abs(b) < abs(a):
        pt = math.log(a / b) / math.log(2)
        return t9 - t3, 1.25 * abs(b) / (2**pt - 1), f"monotone p={pt:.3f}"
    return t9 - t3, 3 * max(abs(a), abs(b)), "non-monotone"


def summarise() -> dict:
    recs = [json.loads(s) for s in RUNS.read_text().splitlines()]
    for r in recs:  # the first d0/d1 multipole runs used FastHenry's default expansion order 2 (no "order" recorded)
        if r["mode"] == "multipole" and not r.get("order"):
            r["mode"], r["order"] = "multipole_o2", 2
    p3 = json.loads((ROOT / "research/o006_p3/results.json").read_text())
    l2 = {g["name"]: g for g in p3["geometries"]}
    bc = json.loads((OUT / "binary_check.json").read_text())

    def L(g, mode, lvl, fk):
        ok = [r for r in recs if (r["geometry"], r["mode"], r["level"], r["status"]) == (g, mode, lvl, "ok")]
        return ok[-1]["L_H"][fk] if ok else None

    geoms, U1, U2, U3 = [], True, True, True
    agree = []
    for g in fx.case4.GEOMETRY_NAMES:
        runs = []
        for r in recs:
            if r["geometry"] != g:
                continue
            for fk in FREQ_KEYS:
                runs.append({"mode": r["mode"], "refinement": r["level"], "params": r["params"], "attempt": r.get("attempt", 1),
                             "freq_hz": float(fk), "status": r["status"], "wall_s": r.get("wall_s"),
                             "peak_mem_mb": r.get("peak_mem_mb"), "cpu_s": r.get("cpu_s"), "n_filaments": r["n_filaments"],
                             "L_H": (r.get("L_H") or {}).get(fk), **({"reason": r["reason"]} if "reason" in r else {})})
        Lx, est, kinds, dabs, drel, drel_unc = {}, {}, {}, {}, {}, {}
        for fk in FREQ_KEYS:
            fe, gci, kl = _lateral(*(L(g, "multipole", k, fk) for k in ("k0", "k1", "k2")))
            D, term, kt = _thickness(L(g, "multipole", "k0", fk), L(g, "multipole", "k0_nh5", fk), L(g, "multipole", "k0_nh9", fk))
            l2x, l2e = l2[g]["L_extrap_H"][str(int(float(fk)))], l2[g]["abs_est_H"][str(int(float(fk)))]
            kinds[fk] = {"lateral": kl, "thickness": kt}
            if fe is None or D is None:
                U1 = False
                Lx[fk] = est[fk] = dabs[fk] = drel[fk] = drel_unc[fk] = None
                continue
            Lx[fk], est[fk] = fe + D, gci + term
            dabs[fk], drel[fk] = Lx[fk] - l2x, (Lx[fk] - l2x) / l2x
            drel_unc[fk] = (est[fk] + l2e) / l2x
            U3 &= est[fk] <= l2e
            kinds[fk].update({"f_ext_lateral_H": fe, "gci_lateral_H": gci, "thickness_corr_H": D, "thickness_term_H": term,
                              "l2_L_extrap_H": l2x, "l2_abs_est_H": l2e})
        for lvl in {r["level"] for r in recs if r["geometry"] == g}:
            for fk in FREQ_KEYS:
                ld, lm = L(g, "direct", lvl, fk), L(g, "multipole", lvl, fk)
                if ld is not None and lm is not None:
                    agree.append({"geometry": g, "level": lvl, "freq": fk, "rel": (lm - ld) / ld})
                    U2 &= abs((lm - ld) / ld) <= 1e-3
        geoms.append({"name": g, "runs": runs, "L_extrap_H": Lx, "abs_est_H": est, "diff_vs_l2_abs_H": dabs,
                      "diff_vs_l2_rel": drel, "diff_vs_l2_rel_unc": drel_unc, "estimates": kinds})
    ratio_diff = {}
    for pert in ("die_shift", "trace_width"):
        for fk in FREQ_KEYS:
            def R(lvl, pert=pert, fk=fk):
                a, b = L(f"case4_{pert}", "multipole", lvl, fk), L("case4_base", "multipole", lvl, fk)
                return a / b if a is not None and b is not None else None
            fe, gci, kl = _lateral(R("k0"), R("k1"), R("k2"))
            D, term, kt = _thickness(R("k0"), R("k0_nh5"), R("k0_nh9"))
            p3r = [x for x in p3["pair_ratios"] if x["pert"] == pert and x["freq_hz"] == float(fk)][0]
            r_l2 = p3r["estimates"]["extrap_assumed_p"]
            Rfh = None if fe is None or D is None else fe + D
            ratio_diff[f"{pert}@{fk}"] = {
                "R_fh": Rfh, "R_fh_est": None if Rfh is None else gci + term, "R_l2_extrap": r_l2, "R_l2_est": p3r["ratio_est"],
                "diff": None if Rfh is None else Rfh - r_l2, "kinds": {"lateral": kl, "thickness": kt},
                "R_fh_per_level": {k: R(k) for k in ("k0", "k1", "k2", "k0_nh5", "k0_nh9")}}
    usable = bool(U1 and U2 and U3)
    return {"note": "research note, not evidence (O006 F4); see research/notes/o006-p4-fasthenry-feasibility.md",
            "fasthenry_version": "FastHenry 3.0wr (29Sep96, mod 031424), fasthenry-3.0wr-031424 pinned by D0002",
            "binary": {"path": bc["binary"], "sha256": bc["binary_sha256"], "selftest_L_nH_1kHz": bc["L_nH_1kHz"],
                       "selftest_pass": bc["pass"]},
            "usable": usable, "usable_criteria": {"U1_levels_completed": U1, "U2_direct_vs_multipole_1e-3": U2,
                                                  "U3_fh_est_le_l2_est": U3},
            "direct_vs_multipole": agree, "levels": {k: asdict(v) for k, v in LEVELS.items()},
            "geometries": geoms, "ratio_diff": ratio_diff}


def _append(rec: dict) -> None:
    with open(RUNS, "a") as fh:
        fh.write(json.dumps(rec) + "\n")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--binary-check", action="store_true")
    ap.add_argument("--plan", choices=sorted(PLANS))
    ap.add_argument("--only-geometry", action="append")
    ap.add_argument("--timeout-s", type=float, default=3600)
    ap.add_argument("--mem-cap-mb", type=float, default=6000)
    ap.add_argument("--tol", type=float, default=1e-4)
    ap.add_argument("--retries", type=int, default=1, help="re-runs after a crash (D0002 intermittent segfault)")
    ap.add_argument("--summarise", action="store_true")
    a = ap.parse_args()
    if a.summarise:
        d = summarise()
        (OUT / "results.json").write_text(json.dumps(d, indent=1) + "\n")
        print(json.dumps({k: d[k] for k in ("usable", "usable_criteria", "direct_vs_multipole", "ratio_diff")}, indent=1))
        for g in d["geometries"]:
            print(g["name"], g["L_extrap_H"], g["abs_est_H"], g["diff_vs_l2_rel"], g["estimates"])
        return 0
    if a.binary_check:
        r = binary_check()
        print(json.dumps(r, indent=1))
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / "binary_check.json").write_text(json.dumps(r, indent=1) + "\n")
        return 0 if r["pass"] else 1
    if a.plan:
        run_plan(a.plan, a.only_geometry or list(fx.case4.GEOMETRY_NAMES), a.timeout_s, a.mem_cap_mb, a.tol, a.retries)
        return 0
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
