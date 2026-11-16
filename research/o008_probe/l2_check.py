"""T0376 (O008): kill shot. Do the probe's designer proxy W* and its null gap survive l2_layout?

Indicative only, not evidence for any criterion: development geometry (2D_Case_2R and 2D_Case_4, D0023), development
seeds (20261115 + j), the probe's parameter domain (no reach), l2_layout cells as coarse as 0.5 mm (E011 uses 0.25 mm).
No sealed seed, no judged reference, no production code change.

Pre-declared readings (task packet T0376, stated before any L2 solve):
  KILL-A fires on a layout if L_sub(W*) >= L_sub(W): the proxy rule then returns W (and on 2R blind compaction recovered
         W at L1, research/notes/o008-control-probe.md).
  KILL-B fires on a layout if a solved compaction or widen endpoint has L2 s = L_sub(x) / L_sub(W*) - 1 <= 0.02.
  Otherwise "kill shot did not fire".

Steps
  regen REF   Re-run the probe's die-rows-free proxy run (research/o008_probe/probe.py imported unchanged; its functions
              ascent and descend, PROXY_STEPS, MAX_STEPS, SEED0) and keep the parameter vectors of W, W*, every degraded
              start D_j and every guided / compact / widen endpoint.  2R: E010's committed ctx.pkl.  Case 4: rebuilt with
              e010_run.dev_reference('case4', cfg) from E010's registered spec config, then twin.twin (as e010_run.prepare).
              Every regenerated number is compared with probe_{2R,Case4}_proxy.json at MATCH_REL relative; any mismatch
              is recorded and blocks the solve step.
  solve       l2_layout solves, one at a time, each in a fresh process with OPENBLAS / OMP / MKL_NUM_THREADS and
              MF_L2_FFT_WORKERS pinned (project/memory/lessons.md 2026-11-09; e010_run.child_env), through
              e010_run.child_em (E010's frozen level definitions, 20 MHz).  Level per reference: the finest cell whose
              e010_run.em_cost memory estimate (from em_unknowns on the baseplate box) fits MEM_FIT_GB.  Mandatory per
              reference: W, W*, the compaction endpoint with the lowest L1 s and the guided endpoint of the same draw; then
              further endpoints ordered by |L1 s - 0.02| while the summed solve wall stays within BUDGET_S.  Memory policy
              of this machine: a solve estimated above BASE_BUDGET_GB starts only if memory_pressure reports >= 50 % free
              and swap in use is < 4 GB; a watchdog stops the solve if swap passes 8 GB or the child passes 10 GB.  Swap in
              use is bounded above by the total size of the swapfiles (sysctl vm.swapusage is not readable in this
              sandbox).  Every solve is checkpointed (l2_work/solves/), so a rerun resumes.
  report      research/o008_probe/l2_check.json.

Usage: uv run python research/o008_probe/l2_check.py {regen 2R|regen Case4|solve|report}
"""
import argparse
import ctypes
import glob
import importlib.util
import json
import math
import os
import pickle
import re
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
HERE = ROOT / "research" / "o008_probe"
WORK = HERE / "l2_work"
SOLVES = WORK / "solves"
OUT_JSON = HERE / "l2_check.json"
RID = {"2R": "2D_Case_2R", "Case4": "2D_Case_4"}
PROBE_JSON = {k: HERE / f"probe_{k}_proxy.json" for k in RID}
CTX_2R = ROOT / "experiments/results/E010/E010-20261114T202413-80c1/work/2D_Case_2R/ctx.pkl"
E010_SOLVES_2R = CTX_2R.parent / "solves"
MATCH_REL = 1e-9
MODES = ("guided", "compact", "widen")
NULL_MODES = ("compact", "widen")
KILL_B_LINE = 0.02
BUDGET_S = 3 * 3600.0
MEM_FIT_GB = 8.0
BASE_BUDGET_GB = 5.0
SOLO_CAP_GB = 10.0
FREE_PCT_MIN = 50.0
SWAP_START_GB = 4.0
SWAP_STOP_GB = 8.0
WAIT_S = 180.0
LEVEL_MM = {"lat0.25": 0.25, "lat0.5": 0.5}


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def _load(name: str, path: Path):
    sp = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(sp)
    sys.modules[name] = m
    sp.loader.exec_module(m)
    return m


def probe_module():
    """probe.py unchanged.  It reads DIES_FIXED from sys.argv[4:] at import: import it with a clean argv (die rows free)."""
    argv, sys.argv = sys.argv, [str(HERE / "probe.py")]
    try:
        P = _load("o008_probe_probe", HERE / "probe.py")
    finally:
        sys.argv = argv
    if P.DIES_FIXED:
        raise RuntimeError("probe imported with die rows fixed")
    return P


def e010():
    return sys.modules.get("e010_run") or _load("e010_run", ROOT / "experiments" / "runners" / "e010_run.py")


def rel(a: float, b: float) -> float:
    return abs(a - b) / abs(b) if b != 0 else abs(a - b)


# ------------------------------------------------------------------------------------------------ memory (this Mac)
def free_pct() -> float:
    out = subprocess.run(["memory_pressure"], capture_output=True, text=True).stdout
    m = re.search(r"free percentage:\s*(\d+)%", out)
    return float(m[1]) if m else math.nan


def swap_bound_gb() -> float:
    """Upper bound on swap in use: the total size of the swapfiles (vm.swapusage 'total'; 'used' <= total)."""
    return sum(os.path.getsize(p) for p in glob.glob("/System/Volumes/VM/swapfile*") + glob.glob("/private/var/vm/swapfile*")) / 1e9


class _TaskInfo(ctypes.Structure):  # struct proc_taskinfo (sys/proc_info.h): virtual size, resident size, ...
    _fields_ = [("virtual_size", ctypes.c_uint64), ("resident_size", ctypes.c_uint64)] + \
               [(f"_r{i}", ctypes.c_uint64) for i in range(10)]


_LIBPROC = ctypes.CDLL("/usr/lib/libproc.dylib") if sys.platform == "darwin" else None


def rss_gb(pid: int) -> float:
    if _LIBPROC is None:
        try:
            return int(Path(f"/proc/{pid}/statm").read_text().split()[1]) * os.sysconf("SC_PAGE_SIZE") / 1e9
        except OSError:
            return math.nan
    t = _TaskInfo()
    n = _LIBPROC.proc_pidinfo(pid, 4, 0, ctypes.byref(t), ctypes.sizeof(t))  # 4 = PROC_PIDTASKINFO
    return t.resident_size / 1e9 if n > 0 else math.nan


def own_rss_gb() -> float:
    return rss_gb(os.getpid())


# ------------------------------------------------------------------------------------------------ step 1: regenerate
def layout_entry(lay, spec, l1: float, **kw) -> dict:
    from moduleforge.drc.rules import check
    from moduleforge.generate import derivative as D
    p = D.params_of(lay)
    rb = D.build(spec, D.Params.from_vector(p.to_vector()))
    return {"params": p.to_vector().tolist(), "names": list(D.Params.NAMES), "family": lay.family,
            "fingerprint": lay.fingerprint(), "rebuild_fingerprint_equal": rb.fingerprint() == lay.fingerprint(),
            "drc_violations": sorted({v.rule for v in check(lay, spec.rules)}), "L1_H": l1, **kw}


def regen(ref: str) -> int:
    from moduleforge.generate import derivative as D
    from moduleforge.generate import twin as T
    P = probe_module()
    WORK.mkdir(parents=True, exist_ok=True)
    old = json.loads(PROBE_JSON[ref].read_text())
    t0, c0 = time.perf_counter(), time.process_time()
    if ref == "2R":
        c = pickle.load(open(CTX_2R, "rb"))
        spec, W, ctx = c["spec"], c["twin"], CTX_2R
        src = {"ctx": str(CTX_2R.relative_to(ROOT)), "how": "E010 committed ctx.pkl"}
    else:
        E = e010()
        cfg = E.load_spec()["config"]
        rc = E.dev_reference("case4", cfg)
        W, _, trec = T.twin(rc.reference, rc.spec, with_l1=True)
        spec, ctx = rc.spec, WORK / "ctx_Case4.pkl"
        with open(ctx, "wb") as f:  # the fields e010_run.layout_of / child_em read
            pickle.dump({"spec": spec, "reference": rc.reference, "twin": W, "D": None, "snap025": None}, f)
        src = {"ctx": str(ctx.relative_to(ROOT)), "how": "e010_run.dev_reference('case4', E010 spec config) + twin.twin",
               "spec_file": str(E.REGISTERED.relative_to(ROOT)), "spec_sha256": E.sha256_file(E.REGISTERED),
               "twin_mode": trec.get("mode"), "reference_fingerprint": rc.reference.fingerprint()}
    n_draws = len(old["draws"])
    l_w = T._l1(W)
    rec, _, Ws = P.descend(spec, D.params_of(W), W, l_w, "guided", max_steps=P.PROXY_STEPS, keep=True)
    l_ws = T._l1(Ws)
    log(f"{ref}: L1(W) {l_w * 1e9:.9f} nH, W* after {rec['steps']} steps {l_ws * 1e9:.9f} nH")
    lays = {"W": layout_entry(W, spec, l_w, kind="twin"),
            "Wstar": layout_entry(Ws, spec, l_ws, kind="proxy", steps=rec["steps"], hit_step_cap=rec["hit_step_cap"])}
    cmp = [("l1_W_nH", l_w * 1e9, old["l1_W_nH"]), ("l1_proxy_nH", l_ws * 1e9, old["l1_proxy_nH"]),
           ("proxy.l1_proxy_over_twin", 1 + rec["s"], old["proxy"]["l1_proxy_over_twin"]),
           ("proxy.steps", rec["steps"], old["proxy"]["steps"])]
    draws = []
    for j in range(n_draws):
        rng = np.random.default_rng(P.SEED0 + j)
        p, lay, ratio, changed, dist = P.ascent(spec, Ws, l_ws, rng)
        lays[f"D{j}"] = layout_entry(lay, spec, T._l1(lay), kind="degraded", draw=j, seed=P.SEED0 + j, R_D_l1=ratio)
        o = old["draws"][j]
        cmp += [(f"draws[{j}].seed", P.SEED0 + j, o["seed"]), (f"draws[{j}].R_D_l1", ratio, o["R_D_l1"]),
                (f"draws[{j}].coords_changed", changed, o["coords_changed"]),
                (f"draws[{j}].manhattan_mm", dist, o["manhattan_mm"])]
        row = {"draw": j, "seed": P.SEED0 + j, "R_D_l1": ratio}
        for mode in MODES:
            out, _, le = P.descend(spec, p, lay, l_ws, mode, keep=True)
            row[mode] = out
            lays[f"{mode}{j}"] = layout_entry(le, spec, T._l1(le), kind=mode, draw=j, L1_s=out["s"], steps=out["steps"],
                                              hit_step_cap=out["hit_step_cap"])
            cmp += [(f"draws[{j}].{mode}.s", out["s"], o[mode]["s"]), (f"draws[{j}].{mode}.steps", out["steps"],
                                                                         o[mode]["steps"])]
        draws.append(row)
        log(f"{ref}: draw {j} R_D {ratio:.6f} " + " ".join(f"{m} {row[m]['s']:+.5f}" for m in MODES))
    checks = [{"quantity": k, "regenerated": a, "probe": b, "rel": rel(float(a), float(b)),
               "ok": (a == b) if isinstance(b, int) else rel(float(a), float(b)) <= MATCH_REL} for k, a, b in cmp]
    # the 1 + s form as well (s near 0 makes a relative comparison of s itself the stricter test)
    s_plus1 = max([rel(1 + c["regenerated"], 1 + c["probe"]) for c in checks if c["quantity"].endswith(".s")] or [0.0])
    bp = W.baseplate_outline.bounds
    res = {"reference": ref, "rid": RID[ref], "source": src, "ctx_for_solves": str(Path(ctx).relative_to(ROOT)),
           "probe_json": str(PROBE_JSON[ref].relative_to(ROOT)), "dies_fixed": P.DIES_FIXED,
           "probe_constants": {"SEED0": P.SEED0, "MAX_STEPS": P.MAX_STEPS, "PROXY_STEPS": P.PROXY_STEPS,
                               "ASCENT_PROPOSALS": P.ASCENT_PROPOSALS},
           "baseplate_box_m2": (bp[2] - bp[0]) * (bp[3] - bp[1]), "rules_min_width_power_mm": spec.rules.min_width_power * 1e3,
           "match": {"tolerance_rel": MATCH_REL, "all_ok": all(c["ok"] for c in checks),
                     "max_rel": max(c["rel"] for c in checks), "max_rel_1_plus_s": s_plus1,
                     "mismatches": [c for c in checks if not c["ok"]], "checks": checks},
           "draws": draws, "layouts": lays, "wall_s": time.perf_counter() - t0, "cpu_s": time.process_time() - c0,
           "peak_rss_GB": own_rss_gb()}
    (WORK / f"regen_{ref}.json").write_text(json.dumps(res, indent=1))
    log(f"{ref}: match all_ok {res['match']['all_ok']} max_rel {res['match']['max_rel']:.3g}; "
        f"rebuild ok {all(v['rebuild_fingerprint_equal'] for v in lays.values())}; wall {res['wall_s']:.0f} s")
    return 0 if res["match"]["all_ok"] else 2


# ------------------------------------------------------------------------------------------------ step 2: solve
def load_regen() -> dict:
    out = {}
    for ref in RID:
        p = WORK / f"regen_{ref}.json"
        if not p.exists():
            raise SystemExit(f"{p} missing: run regen {ref} first")
        out[ref] = json.loads(p.read_text())
    return out


def level_choice(rg: dict, cm: dict) -> dict:
    """The finest cell (0.25 mm, else 0.5 mm) whose em_cost memory estimate fits MEM_FIT_GB (packet T0376 step 2)."""
    E = e010()
    est = {}
    for lv in ("lat0.25", "lat0.5"):
        n = E.em_unknowns(rg["baseplate_box_m2"], LEVEL_MM[lv], lv, cm)
        t, gb = E.em_cost(n, lv, cm)
        est[lv] = {"unknowns": n, "mem_GB": gb, "vm_wall_s_model": t}
    lv = "lat0.25" if est["lat0.25"]["mem_GB"] <= MEM_FIT_GB else "lat0.5"
    return {"level": lv, "level_mm": LEVEL_MM[lv], "estimates": est, "fit_GB": MEM_FIT_GB}


def queue(regs: dict) -> tuple[list, list]:
    mand, opt = [], []
    for ref, rg in regs.items():
        L = rg["layouts"]
        nd = len(rg["draws"])
        best = min(range(nd), key=lambda j: (L[f"compact{j}"]["L1_s"], j))
        m = ["W", "Wstar", f"compact{best}", f"guided{best}"]
        mand += [(ref, x) for x in m]
        opt += [(abs(L[f"{md}{j}"]["L1_s"] - KILL_B_LINE), ref, f"{md}{j}") for j in range(nd) for md in MODES
                if f"{md}{j}" not in m]
    return mand, [(ref, lab) for _, ref, lab in sorted(opt)]


def solve_path(ref: str, lab: str) -> Path:
    return SOLVES / f"{ref}__{lab}.json"


def done_solves() -> dict:
    return {(r["ref"], r["label"]): r for r in (json.loads(p.read_text()) for p in sorted(SOLVES.glob("*__*.json"))
                                                if not p.name.endswith(".job.json"))}


def may_start(est_gb: float) -> tuple[bool, dict]:
    fp, sw = free_pct(), swap_bound_gb()
    st = {"est_GB": est_gb, "free_pct": fp, "swap_bound_GB": sw, "own_rss_GB": own_rss_gb()}
    if sw >= SWAP_STOP_GB:  # the watchdog would stop it at once (2026-11-15 18:27: three solves killed this way)
        return False, st | {"rule": "swap bound >= 8 GB: no start"}
    if est_gb + st["own_rss_GB"] <= BASE_BUDGET_GB:
        return True, st | {"rule": "within the 5 GB total budget"}
    if est_gb > SOLO_CAP_GB:
        return False, st | {"rule": "above the 10 GB single-process cap"}
    ok = fp >= FREE_PCT_MIN and sw < SWAP_START_GB
    return ok, st | {"rule": "single process up to 10 GB: needs >= 50 % free and swap < 4 GB"}


def run_one(ref: str, lab: str, rg: dict, lvc: dict, threads: int, max_wait_s: float) -> dict | None:
    E = e010()
    lay = rg["layouts"][lab]
    lv = lvc["level"]
    est_gb = lvc["estimates"][lv]["mem_GB"]
    waited, t_w = 0.0, time.time()
    while True:
        ok, st = may_start(est_gb)
        if ok:
            break
        with open(WORK / "gate_log.jsonl", "a") as f:
            f.write(json.dumps({"t": time.strftime("%Y-%m-%dT%H:%M:%S"), "ref": ref, "label": lab, "level": lv} | st)
                    + "\n")
        if time.time() - t_w > max_wait_s:
            log(f"{ref} {lab}: memory gate still closed after {time.time() - t_w:.0f} s: {st}")
            return None
        log(f"{ref} {lab}: waiting for memory: {st}")
        time.sleep(WAIT_S)
    waited = time.time() - t_w
    SOLVES.mkdir(parents=True, exist_ok=True)
    out = solve_path(ref, lab)
    if out.exists():  # a failed or killed earlier attempt: keep its record before it is overwritten
        with open(WORK / "failed_attempts.jsonl", "a") as f:
            f.write(json.dumps(json.loads(out.read_text())) + "\n")
    job = {"type": "em", "ctx": str(ROOT / rg["ctx_for_solves"]), "which": "candidate", "family": lay["family"],
           "fp": lay["fingerprint"], "level": lv, "freq_hz": float(E.load_spec()["config"]["em"]["freq_hz"]),
           "out": str(out.with_suffix(".child.json"))}
    jp = out.with_suffix(".job.json")
    jp.write_text(json.dumps(job, indent=1))
    env = E.child_env(threads)
    t0 = time.perf_counter()
    with open(out.with_suffix(".log"), "w") as lf:
        pr = subprocess.Popen([sys.executable, __file__, "child", str(jp)], env=env, stdout=lf, stderr=subprocess.STDOUT)
        peak, peak_sw, killed = 0.0, st["swap_bound_GB"], None
        while pr.poll() is None:
            r = rss_gb(pr.pid)
            peak = max(peak, r if math.isfinite(r) else 0.0)
            sw = swap_bound_gb()
            peak_sw = max(peak_sw, sw)
            if sw > SWAP_STOP_GB or peak > SOLO_CAP_GB:
                killed = f"swap bound {sw:.2f} GB, child RSS {peak:.2f} GB"
                pr.kill()
                break
            time.sleep(5)
        pr.wait()
    job_wall = time.perf_counter() - t0
    rec = {"ref": ref, "rid": RID[ref], "label": lab, "kind": lay["kind"], "draw": lay.get("draw"),
           "fingerprint": lay["fingerprint"], "level": lv, "level_mm": LEVEL_MM[lv], "threads": threads,
           "est_GB": est_gb, "start_state": st, "waited_s": waited, "job_wall_s": job_wall,
           "peak_rss_sampled_GB": peak, "peak_swap_bound_GB": peak_sw, "returncode": pr.returncode, "killed": killed}
    cp = Path(job["out"])
    if pr.returncode == 0 and cp.exists():
        rec |= {"status": "ok", **json.loads(cp.read_text())}
        cp.unlink()
    else:
        rec["status"] = "failed"
    out.write_text(json.dumps(rec, indent=1))
    log(f"{ref} {lab} [{lv}]: {rec['status']} L {rec.get('L_H', math.nan) * 1e9:.6f} nH wall {rec.get('wall_s', 0):.0f} s "
        f"cpu {rec.get('cpu_s', 0):.0f} s peak {rec.get('peak_GB', peak):.2f} GB (sampled {peak:.2f})")
    return rec


def solve(args) -> int:
    E = e010()
    cfg = E.load_spec()["config"]
    cm = cfg["compute"]["cost_model"]
    regs = load_regen()
    bad = [ref for ref, rg in regs.items() if not rg["match"]["all_ok"]]
    if bad:
        log(f"regeneration mismatch on {bad}: no solve (packet step 1: stop and report)")
        return 2
    threads, why = E.thread_count(cfg)
    lvc = {ref: level_choice(rg, cm) for ref, rg in regs.items()}
    if args.level_2r:  # only when the machine's memory rule keeps the packet's level from starting (see the note)
        lvc["2R"] |= {"level": args.level_2r, "level_mm": LEVEL_MM[args.level_2r], "override": "--level-2r",
                      "override_reason": args.override_reason}
    (WORK / "levels.json").write_text(json.dumps({"levels": lvc, "threads": [threads, why]}, indent=1))
    mand, opt = queue(regs)
    order = sorted(mand, key=lambda x: (x[0] != "Case4",)) if args.case4_first else mand
    done = done_solves()
    for ref, lab in order:
        if (ref, lab) in done and done[(ref, lab)]["status"] == "ok":
            continue
        dup = [r for (rf, _), r in done.items() if rf == ref and r["status"] == "ok"
               and r["fingerprint"] == regs[ref]["layouts"][lab]["fingerprint"] and r["level"] == lvc[ref]["level"]]
        if dup:
            continue
        rec = run_one(ref, lab, regs[ref], lvc[ref], threads, args.max_wait_s)
        if rec is None:
            return 3
        done[(ref, lab)] = rec
    spent = spent_s(done)
    log(f"mandatory solves done; {spent:.0f} s of {BUDGET_S:.0f} s spent")
    for ref, lab in opt:
        if (ref, lab) in done and done[(ref, lab)]["status"] == "ok":
            continue
        fp = regs[ref]["layouts"][lab]["fingerprint"]
        if any(r["ref"] == ref and r["fingerprint"] == fp and r["status"] == "ok" for r in done.values()):
            continue  # the same layout as a solved endpoint (e.g. compact and widen stopping at one layout)
        walls = [r["job_wall_s"] for r in done.values() if r["ref"] == ref and r["status"] == "ok"]
        est = max(walls) if walls else math.inf
        spent = spent_s(done)
        if spent + est > BUDGET_S:
            log(f"skip {ref} {lab}: {spent:.0f} s + {est:.0f} s > {BUDGET_S:.0f} s budget")
            continue
        rec = run_one(ref, lab, regs[ref], lvc[ref], threads, args.max_wait_s)
        if rec is None:
            return 3
        done[(ref, lab)] = rec
    return 0


def spent_s(done: dict) -> float:
    """Solve wall spent: every finished record plus every killed or failed attempt (failed_attempts.jsonl)."""
    fa = WORK / "failed_attempts.jsonl"
    old = [json.loads(x) for x in fa.read_text().splitlines()] if fa.exists() else []
    return sum(r["job_wall_s"] for r in list(done.values()) + old)


def child(path: str) -> int:
    E = e010()
    job = json.loads(Path(path).read_text())
    r = E.child_em(job)
    Path(job["out"]).write_text(json.dumps(r, indent=1))
    return 0


# ------------------------------------------------------------------------------------------------ step 3: report
def e010_2r_bands() -> dict:
    """E010's five-level band on the 2R layouts it solved at every level (committed run): lateral shift of layout ratios
    between 0.25 and 0.5 mm, and mfos.metrics.ratio_band_estimate, as the discretisation scale of an L2 ratio here."""
    from mfos import metrics as MX
    E = e010()
    fps = {}
    for p in E010_SOLVES_2R.glob("*__em*.json"):
        if p.name.endswith(".job.json"):
            continue
        j = json.loads(p.with_name(p.name.replace(".json", ".job.json")).read_text())
        fps.setdefault(p.name.split("__")[0], {})[j["level"]] = json.loads(p.read_text())["L_H"]
    five = {fp: [v[lv] for lv in E.BAND] for fp, v in fps.items() if all(lv in v for lv in E.BAND)}
    keys = sorted(five)
    pairs = [(a, b) for i, a in enumerate(keys) for b in keys[i + 1:]]
    lat = [abs((five[a][0] / five[b][0]) / (five[a][1] / five[b][1]) - 1) for a, b in pairs]
    er = [MX.ratio_band_estimate(five[a], five[b]) for a, b in pairs]
    return {"layouts": len(keys), "pairs": len(pairs), "lateral_ratio_shift_0p25_vs_0p5_max": max(lat),
            "lateral_ratio_shift_0p25_vs_0p5_median": float(np.median(lat)), "e_R_max": max(er),
            "e_R_median": float(np.median(er)),
            "W_L_sub_by_level_H": next((dict(zip(E.BAND, v, strict=True)) for fp, v in five.items()
                                        if fp.startswith("f95383")), None)}


def report(_args) -> int:
    regs = load_regen()
    done = done_solves()
    lv = json.loads((WORK / "levels.json").read_text())
    band = e010_2r_bands()
    out = {"task": "T0376", "objective": "O008", "indicative_only": True,
           "not_evidence": "development geometry, development seeds, probe domain without reach, cells as coarse as 0.5 mm "
                           "(E011: 0.25 mm); not evidence for any O008 criterion",
           "readings": {"KILL_A": "L_sub(W*) >= L_sub(W)", "KILL_B": f"a solved compact or widen endpoint has L2 s <= {KILL_B_LINE}",
                        "L2_s": "L_sub(x) / L_sub(W*) - 1", "L1_s": "L1(x) / L1(W*) - 1 (probe)"},
           "regen_match": {RID[r]: {k: g["match"][k] for k in ("tolerance_rel", "all_ok", "max_rel", "max_rel_1_plus_s")}
                           | {"n_checks": len(g["match"]["checks"]), "mismatches": g["match"]["mismatches"],
                              "source": g["source"], "wall_s": g["wall_s"], "peak_rss_GB": g["peak_rss_GB"]}
                           for r, g in regs.items()},
           "levels": lv, "discretisation_scale_2R_from_E010": band, "layouts": {}, "solves": []}
    total_wall = 0.0
    for ref, rg in regs.items():
        L = rg["layouts"]
        sol = {lab: r for (rf, lab), r in done.items() if rf == ref and r["status"] == "ok"}
        for lab, x in L.items():  # an endpoint identical to a solved layout takes its value
            if lab not in sol:
                same = [r for r in sol.values() if r["fingerprint"] == x["fingerprint"]]
                if same:
                    sol[lab] = same[0] | {"label": lab, "same_layout_as": same[0]["label"], "job_wall_s": 0.0}
        if "W" not in sol or "Wstar" not in sol:
            raise SystemExit(f"{ref}: W or W* not solved")
        lw, lws = sol["W"]["L_H"], sol["Wstar"]["L_H"]
        rows = []
        for lab, x in L.items():
            if x["kind"] == "degraded" and lab not in sol:
                continue
            r = sol.get(lab)
            row = {"label": lab, "kind": x["kind"], "draw": x.get("draw"), "L1_H": x["L1_H"], "L1_s": x.get("L1_s"),
                   "solved": r is not None}
            if r is not None:
                row |= {"L_sub_H": r["L_H"], "L2_over_L1": r["L_H"] / x["L1_H"], "L2_s": r["L_H"] / lws - 1,
                        "same_layout_as": r.get("same_layout_as")}
            rows.append(row)
        nd = len(rg["draws"])
        best = min(range(nd), key=lambda j: (L[f"compact{j}"]["L1_s"], j))
        cb = next(rw for rw in rows if rw["label"] == f"compact{best}")
        gb = next(rw for rw in rows if rw["label"] == f"guided{best}")
        nulls = [rw for rw in rows if rw["kind"] in NULL_MODES and rw["solved"]]
        kill_a = lws >= lw
        kill_b = any(rw["L2_s"] <= KILL_B_LINE for rw in nulls)
        ent = {"L_sub_W": lw, "L_sub_Wstar": lws, "level_mm": sol["W"]["level_mm"], "level": sol["W"]["level"],
               "L1_W": L["W"]["L1_H"], "L1_Wstar": L["Wstar"]["L1_H"],
               "L2_Wstar_over_W": lws / lw, "L1_Wstar_over_W": L["Wstar"]["L1_H"] / L["W"]["L1_H"],
               "compact_best": {"label": cb["label"], "draw": best, "L1_s": cb["L1_s"], "L2_s": cb.get("L2_s")},
               "guided_same_draw": {"label": gb["label"], "L1_s": gb["L1_s"], "L2_s": gb.get("L2_s")},
               "null_L2_s_min": min((rw["L2_s"] for rw in nulls), default=None),
               "null_endpoints_solved": len(nulls),
               "null_endpoints_unsolved": [(rw["label"], rw["L1_s"]) for rw in rows if rw["kind"] in NULL_MODES
                                           and not rw["solved"]],
               "kill": {"A": bool(kill_a), "B": bool(kill_b)},
               "verdict": "kill shot fired" if (kill_a or kill_b) else "kill shot did not fire",
               "endpoints": rows}
        out["layouts"][RID[ref]] = ent
        for r in sol.values():
            if r.get("same_layout_as"):
                continue
            total_wall += r["job_wall_s"]
            out["solves"].append({k: r.get(k) for k in ("rid", "label", "kind", "level", "level_mm", "fingerprint", "L_H",
                                                        "n_unknowns", "gmres_iters", "gmres_flags", "solver_tol_rel_L_max",
                                                        "wall_s", "cpu_s", "job_wall_s", "peak_GB", "peak_rss_sampled_GB",
                                                        "threads", "start_state", "waited_s")})
    s = out["solves"]
    w_e010 = (band.get("W_L_sub_by_level_H") or {}).get(out["layouts"]["2D_Case_2R"]["level"])
    out["sanity"] = {
        "regen_matches_probe_1e-9": all(g["match"]["all_ok"] for g in regs.values()),
        "every_layout_rebuilds_to_its_fingerprint": all(x["rebuild_fingerprint_equal"] for g in regs.values()
                                                        for x in g["layouts"].values()),
        "every_layout_drc_clean_under_spec_rules": all(not x["drc_violations"] for g in regs.values()
                                                       for x in g["layouts"].values()),
        "every_solve_converged_gmres_flag_0": all(all(f == 0 for f in r["gmres_flags"]) for r in s),
        "solver_tol_max": max(r["solver_tol_rel_L_max"] for r in s),
        "2R_W_reproduces_E010_committed": None if w_e010 is None else {
            "E010_H": w_e010, "here_H": out["layouts"]["2D_Case_2R"]["L_sub_W"],
            "rel": rel(out["layouts"]["2D_Case_2R"]["L_sub_W"], w_e010)},
        "total_solve_wall_s": total_wall, "budget_s": BUDGET_S}
    OUT_JSON.write_text(json.dumps(out, indent=1))
    (WORK / "tables.md").write_text(tables(out))
    for rid, e in out["layouts"].items():
        log(f"{rid} [{e['level_mm']} mm]: L2 W*/W {e['L2_Wstar_over_W']:.5f} (L1 {e['L1_Wstar_over_W']:.5f}); compact_best "
            f"L1 s {e['compact_best']['L1_s']:+.4f} L2 s {e['compact_best']['L2_s']}; kill {e['kill']}; {e['verdict']}")
    return 0


def _pc(x) -> str:
    return "-" if x is None else f"{100 * x:+.2f} %"


def tables(out: dict) -> str:
    """Markdown tables of the report (pasted into research/notes/o008-l2-check.md)."""
    t = ["| | " + " | ".join(out["layouts"]) + " |", "|---|" + "---|" * len(out["layouts"])]
    L = list(out["layouts"].values())
    rows = [("cell (mm)", lambda e: f"{e['level_mm']}"), ("L_sub(W) (nH)", lambda e: f"{e['L_sub_W'] * 1e9:.4f}"),
            ("L_sub(W*) (nH)", lambda e: f"{e['L_sub_Wstar'] * 1e9:.4f}"),
            ("L_sub(W*) / L_sub(W)", lambda e: f"{e['L2_Wstar_over_W']:.4f}"),
            ("L1(W*) / L1(W)", lambda e: f"{e['L1_Wstar_over_W']:.4f}"),
            ("best compaction endpoint (lowest L1 s)", lambda e: e["compact_best"]["label"]),
            ("  its L1 s / L2 s", lambda e: f"{_pc(e['compact_best']['L1_s'])} / {_pc(e['compact_best']['L2_s'])}"),
            ("  guided endpoint of that draw, L1 s / L2 s",
             lambda e: f"{_pc(e['guided_same_draw']['L1_s'])} / {_pc(e['guided_same_draw']['L2_s'])}"),
            ("lowest L2 s of solved null endpoints", lambda e: _pc(e["null_L2_s_min"])),
            ("null endpoints solved / unsolved", lambda e: f"{e['null_endpoints_solved']} / {len(e['null_endpoints_unsolved'])}"),
            ("KILL-A / KILL-B", lambda e: f"{e['kill']['A']} / {e['kill']['B']}"), ("reading", lambda e: e["verdict"])]
    t += [f"| {k} | " + " | ".join(f(e) for e in L) + " |" for k, f in rows]
    t += ["", "| layout | endpoint | kind | L1 s | L2 s | L2 s - L1 s | L2/L1 |", "|---|---|---|---|---|---|---|"]
    for rid, e in out["layouts"].items():
        for r in e["endpoints"]:
            if not r["solved"] and r["kind"] not in MODES:
                continue
            l2s, l1s = r.get("L2_s"), r.get("L1_s")
            d = None if l2s is None or l1s is None else l2s - l1s
            same = f" (= {r['same_layout_as']})" if r.get("same_layout_as") else ""
            t.append(f"| {rid} | {r['label']}{same} | {r['kind']} | {_pc(l1s)} | {_pc(l2s)} | {_pc(d)} | "
                     f"{'-' if not r['solved'] else format(r['L2_over_L1'], '.4f')} |")
    t += ["", "| layout | layout id | cell (mm) | unknowns | wall (s) | cpu (s) | peak RSS (GB) | threads |",
          "|---|---|---|---|---|---|---|---|"]
    for r in out["solves"]:
        t.append(f"| {r['rid']} | {r['label']} | {r['level_mm']} | {r['n_unknowns']} | {r['wall_s']:.0f} | {r['cpu_s']:.0f} | "
                 f"{r['peak_GB']:.2f} | {(r.get('threads') or {}).get('OPENBLAS_NUM_THREADS')} |")
    return "\n".join(t) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("regen")
    g.add_argument("ref", choices=sorted(RID))
    s = sub.add_parser("solve")
    s.add_argument("--max-wait-s", type=float, default=3600.0)
    s.add_argument("--case4-first", action="store_true", help="mandatory Case 4 solves before 2R's")
    s.add_argument("--level-2r", choices=sorted(LEVEL_MM), default=None)
    s.add_argument("--override-reason", default=None)
    sub.add_parser("report")
    c = sub.add_parser("child")
    c.add_argument("job")
    a = ap.parse_args(argv)
    if a.cmd == "regen":
        return regen(a.ref)
    if a.cmd == "solve":
        return solve(a)
    if a.cmd == "child":
        return child(a.job)
    return report(a)


if __name__ == "__main__":
    sys.exit(main())
