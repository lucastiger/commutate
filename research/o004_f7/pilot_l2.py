"""O004 F7(b)-(d) l2_layout pilot on 2D_Case_4 development pairs (T0387).  RESEARCH ONLY, NOT EVIDENCE.

Development geometry only (O004 F2): 2D_Case_4 (research/scripts/o006_case4_layout.py) and gen2_0 (E010's generator
housing layout, dev seed 20261110), development seeds only.  On the judged references nothing is drawn and no inductance is
computed, except the F7(b) l2_layout 0.25 mm solve of 2D_Case_6's reconstruction, which ran locally (1.10 M unknowns,
4.75 GB, solves/case6_recon__lat0.25.json) and is listed for the burst VM only if that file is missing.

The development pairs were drawn under perturb.rules_sha256() 70307210... (dev_pairs.json).  T0438 and later changes to the
rules (canonical long sides renumber the trace_width edges) mean the current rules may no longer rebuild a pair from its move
parameters; the pairs are fixed geometries, identified by the fingerprints recorded in dev_pairs.json and in every solve file,
and --check verifies those instead of a rebuild when the rules hash has changed.

Modes (each writes only under research/o004_f7/):
  --pairs        draw the F7(c) development pairs on Case 4, L1 ratios at 10 / 20 MHz -> dev_pairs.json
  --span REF     structured L1 span search (REF in case4, gen2_0) -> span_work/REF.json (checkpointed)
  --run-local    l2_layout lat1.0 + lat0.5 on every dev layout, thk_c + fil_f on base and the stand-in (one at a time)
  --solve-one NAME LEVEL   one l2_layout solve in this process -> solves/NAME__LEVEL.json
  --run-vm --parallel N --threads T   every job of vm_jobs_l2.json not yet solved, N at a time (burst VM only)
  --assemble     f7c_local.json, vm_jobs_l2.json, span_reach.json from the solve and span files
  --check        validate the JSON outputs against each other and the layouts' fingerprints, without solving

Levels (O006 P3, research/scripts/o006_p3_em_convergence.py LEVELS; E010 EM_LEVELS): lat1.0 = CELL[0] patched to 1.0 mm
at refinement 0 (E010's mesh-constant pattern, e010_run.child_em); lat0.5 = unpatched refinement 0; lat0.25 = unpatched
refinement 1 (CELL[1] = 0.25 mm with the same 10/6/6 layers and E0 annuli, so equal to P3's patched lat0.25); thk_c /
thk_f = 0.5 mm with layers 5/3/3 and 20/12/12; fil_f = 0.5 mm with the bisected annuli E1.

Ratio estimate of a pair (O004 scope_in and F1; O006 P3 for the thickness and filament terms):
  E_R = gci_step_floor(R_1.0, R_0.5, R_0.25, 0.001, relative=True)       (mfos.metrics, on main, packet note (iii))
        + ratio_middle_term(R_thk_c, R_0.5, R_thk_f)                       (mfos.metrics; P3 thickness term)
        + 3 |R_fil_f - R_0.5|                                              (P3 filament term)
A missing level makes E_R = +inf (O004 F1); in this pilot such a pair is 'pending' while the level is a VM job, not
'excluded'.  F1 excludes a pair with E_R / r > 0.005, r the finest (0.25 mm) ratio: the caps
are relative to the ratio (founder decision 2026-11-17, D0024 item 1; review T0429 finding 6).  T0387 first applied E_R > 0.005.
"""
from __future__ import annotations

import argparse
import glob
import importlib.util
import itertools
import json
import math
import os
import resource
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tools" / "mfos")]
OUT = ROOT / "research" / "o004_f7"
SOLVES = OUT / "solves"
SPAN_WORK = OUT / "span_work"
P3_SOLVES = ROOT / "research" / "o006_p3" / "solves"
FREQS = (10e6, 20e6)
FK = ("10MHz", "20MHz")
DEV_SEED = 20261116  # development seed for the F7(c) draw (T0387); not E004's sealed seed, never used for judgement
GEN_DEV_SEED = 20261110  # E010 dev.dev_seed: gen2_0 = derivative.generate(halfbridge_housing_spec(2), 1, seed)[0]
ALLOC = {"die_row_shift": 2, "trace_width": 2, "terminal_copper": 2, "wire_landing": 2, "compound": 2}
# E008.yaml dev.case4.rule_overrides, as tests/unit/test_perturb.py CASE4_OVERRIDES (dev only)
CASE4_OVERRIDES = {"min_wire_pitch": 0.6e-3, "wire_pitch_diameters": 2.0, "max_wire_length": 0.018}
# Founder decision 2026-11-16 (i): T0386's lowest compound (tests/unit/test_perturb.py LOWEST_COMPOUND), the stand-in
STANDIN_LABEL = "lowest reachable, r = 0.7616, stands in for r <= 0.75"
STANDIN = {"moves": [{"move_type": "die_row_shift", "params": {"switch": "LS", "dx_mm": -3, "dy_mm": 2}},
                     {"move_type": "trace_width", "params": {"net": "PHASE", "edge": 3, "delta_mm": 7}},
                     {"move_type": "wire_landing", "params": {"switch": "HS", "dx_mm": 1, "dy_mm": 9}}]}
STANDIN_R20 = 0.7616
E0 = (0, .35, .6, .8, .93, 1)
E1 = (0, .175, .35, .475, .6, .7, .8, .865, .93, .965, 1)
LEVELS = {  # name -> (cell mm patched into CELL[0] or None, refinement, layers top/back/base, annulus edges)
    "lat1.0": (1.0, 0, (10, 6, 6), E0), "lat0.5": (None, 0, None, None), "lat0.25": (None, 1, None, None),
    "thk_c": (0.5, 0, (5, 3, 3), E0), "thk_f": (0.5, 0, (20, 12, 12), E0), "fil_f": (0.5, 0, (10, 6, 6), E1)}
F1_CAP = 0.005  # O004 F1: l2_layout ratio estimate at most 0.5 % of the ratio (E_R / r, D0024 item 1)
STEP_FLOOR = 1e-3  # O004 scope_in: ratio steps all below 0.1 % count as converged
N_JUDGED = 13
THREAD_VARS = ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "MF_L2_FFT_WORKERS", "MF_L2_THREADS")
# Measured sizing (facts, research/notes/l2-thread-calibration.md, Case 4 base / die_shift / trace_width, 4.11 M unknowns):
# 0.25 mm pinned on n2d: 6,268-6,519 s, peak 15.8-15.9 GB; two threads: 5,678-5,862 s; 0.5 mm pinned 846 s (1.02 M).
CAL = {"lat0.25_peak_GB": 15.9, "lat0.25_unknowns": 4108580, "lat0.25_wall_s_2thr": 5862.0, "lat0.25_wall_s_pinned": 6519.0,
       "lat0.5_wall_s_pinned_vm": 846.0, "lat0.5_unknowns": 1023000, "thk_f_peak_GB_mac": 8.1, "thk_f_unknowns": 2040000}
VM_MACHINE, VM_ZONE, VM_PRICE = "n2d-custom-8-81920-ext", "us-central1-a", 0.40  # $/h, regular N2D 8 vCPU 80 GB (approx.)


def _load(name: str, rel: str):
    sp = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(sp)
    sys.modules[sp.name] = mod
    sp.loader.exec_module(mod)
    return mod


def c4mod():
    return _load("o006_case4_layout_t0387", "research/scripts/o006_case4_layout.py")


def case4():
    from moduleforge.generate import perturb as P
    ref = c4mod().build("base")
    return ref, P.measured_rules(ref, CASE4_OVERRIDES)


def gen2_0():
    from moduleforge.generate import derivative as D
    from moduleforge.generate import perturb as P
    lay = D.generate(D.halfbridge_housing_spec(2), 1, GEN_DEV_SEED)[0]
    return lay, P.measured_rules(lay)


def l1(lay) -> list[float]:
    from moduleforge.physics.peec import model as peec
    return [float(v) for v in peec.loop_inductance(lay, list(FREQS)).L_H]


def jdump(p: Path, obj) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, indent=1, default=str))
    tmp.replace(p)


def jload(p: Path):
    return json.loads(Path(p).read_text())


# ------------------------------------------------------------------------------------------------------------ layouts
def layout_of(name: str, pairs: dict | None = None):
    """Rebuild a named layout: case4_base, a dev pair of dev_pairs.json, P3's case4_die_shift / case4_trace_width, or
    case6_recon (2D_Case_6's frozen T0263 reconstruction; F7(b) only)."""
    from moduleforge.generate import perturb as P
    if name == "case4_base":
        return c4mod().build("base")
    if name in ("case4_die_shift", "case4_trace_width"):
        return c4mod().build(name.removeprefix("case4_"))
    if name == "case6_recon":
        return _load("o003_refs_t0387", "research/scripts/o003_powersynth_references.py").snapped("2D_Case_6")[0]
    pairs = pairs or jload(OUT / "dev_pairs.json")
    pr = next(p for p in pairs["pairs"] if p["name"] == name)
    return P.apply(c4mod().build("base"), pr["move_type"], pr["params"])


def all_dev_layouts(pairs: dict) -> list[str]:
    return ["case4_base"] + [p["name"] for p in pairs["pairs"]]


# -------------------------------------------------------------------------------------------------------------- pairs
def cmd_pairs() -> None:
    from moduleforge.drc import check
    from moduleforge.generate import perturb as P
    ref, rules = case4()
    l0 = l1(ref)
    mvs = P.draw(ref, ALLOC, seed=DEV_SEED, rules=rules)
    rows, seen = [], {P.geometry_key(ref)}
    for i, mv in enumerate(mvs):
        rows.append(dict(name=f"dev{i:02d}_{mv.move_type}", move_type=mv.move_type, params=mv.params, seed=DEV_SEED,
                         origin=f"perturb.draw(case4, {ALLOC}, seed={DEV_SEED}) item {i}"))
    # the stand-in (founder decision 2026-11-16 (i)), not drawn: T0386's pinned compound
    rows.append(dict(name="standin_compound", move_type="compound", params=STANDIN, seed=None, label=STANDIN_LABEL,
                     origin="tests/unit/test_perturb.py LOWEST_COMPOUND (T0386 structured search); founder decision (i)"))
    for r in rows:
        lay = P.apply(ref, r["move_type"], r["params"])
        if check(lay, rules):
            raise RuntimeError(f"{r['name']} is not DRC-clean")
        if P.geometry_key(lay) in seen:
            raise RuntimeError(f"{r['name']} repeats a geometry")
        seen.add(P.geometry_key(lay))
        L = l1(lay)
        r.update(fingerprint=lay.fingerprint(), geometry_key=P.geometry_key(lay),
                 on_lattice={f"{c * 1e3:g}mm": P.on_lattice(lay, c) for c in P.LATTICES_M},
                 L1_H=dict(zip(FK, L, strict=True)), r_L1=dict(zip(FK, (a / b for a, b in zip(L, l0, strict=True)), strict=True)))
    r20 = [r["r_L1"]["20MHz"] for r in rows]
    jdump(OUT / "dev_pairs.json", dict(
        label="RESEARCH ONLY, NOT EVIDENCE (T0387, O004 F7(c)/(d)); development geometry 2D_Case_4, development seed",
        reference=dict(name="case4_base", fingerprint=ref.fingerprint(), geometry_key=P.geometry_key(ref),
                       L1_H=dict(zip(FK, l0, strict=True)), rules="perturb.measured_rules(case4, CASE4_OVERRIDES)",
                       rule_overrides=CASE4_OVERRIDES),
        dev_seed=DEV_SEED, allocation=ALLOC, rules_sha256=P.rules_sha256(), l1_model="moduleforge.physics.peec loop_inductance",
        pairs=rows,
        summary=dict(n_pairs=len(rows), kinds=sorted({r["move_type"] for r in rows}), min_r20=min(r20), max_r20=max(r20),
                     n_below_0p90=sum(v < 0.90 for v in r20), has_r_ge_0p98=any(v >= 0.98 for v in r20),
                     standin_r20=rows[-1]["r_L1"]["20MHz"], standin_r10=rows[-1]["r_L1"]["10MHz"])))
    print(json.dumps(jload(OUT / "dev_pairs.json")["summary"]))


# --------------------------------------------------------------------------------------------------------------- span
SKIPPED_NETS: dict[str, str] = {}


def _grid(ref, kind: str):
    from moduleforge.geometry import NETS
    from moduleforge.generate import perturb as P
    rg = P.ranges()
    if kind in ("die_row_shift", "wire_landing"):
        lo, hi = rg["die_shift_mm"] if kind == "die_row_shift" else rg["landing_shift_mm"]
        for sw, dx, dy in itertools.product(P.SWITCHES, range(lo, hi + 1), range(lo, hi + 1)):
            if dx or dy:
                yield {"switch": sw, "dx_mm": dx, "dy_mm": dy}
    elif kind == "trace_width":
        lo, hi = rg["trace_delta_mm"]
        for net in NETS:
            try:
                n = len(P.long_sides(P._net_poly(ref, net)))
            except ValueError as e:  # gen2_0: perturb.long_sides raises on a net, so perturb.draw cannot draw trace_width
                SKIPPED_NETS.setdefault(net, str(e))
                continue
            for e, d in itertools.product(range(n), range(lo, hi + 1)):
                if d:
                    yield {"net": net, "edge": e, "delta_mm": d}
    else:
        (mlo, mhi), (lo, hi) = rg["terminal_margin_mm"], rg["terminal_delta_mm"]
        for net, side, m, d in itertools.product(NETS, P.SIDES, range(mlo, mhi + 1), range(lo, hi + 1)):
            if d:
                yield {"net": net, "side": side, "margin_mm": m, "delta_mm": d}


class Evaluator:
    def __init__(self, ref, rules):
        from moduleforge.generate import perturb as P
        self.P, self.ref, self.rules = P, ref, rules
        self.l0 = l1(ref)
        self.key0 = P.geometry_key(ref)
        self.cache: dict[str, list[float]] = {}
        self.n_l1 = 0

    def step(self, lay, kind, params):
        """Apply one move to ``lay``; None unless it applies, changes the geometry and is DRC-clean."""
        from moduleforge.drc import check
        try:
            new = self.P.apply(lay, kind, params)
        except ValueError:
            return None
        if self.P.geometry_key(new) == self.P.geometry_key(lay) or check(new, self.rules):
            return None
        return new

    def ratio(self, lay) -> list[float]:
        k = self.P.geometry_key(lay)
        if k not in self.cache:
            self.cache[k] = [a / b for a, b in zip(l1(lay), self.l0, strict=True)]
            self.n_l1 += 1
        return self.cache[k]

    def chain(self, comps):
        cur = self.ref
        for kind, p in comps:
            cur = self.step(cur, kind, p)
            if cur is None:
                return None
        return None if self.P.geometry_key(cur) == self.key0 else cur


def cmd_span(name: str, sweeps: int = 3) -> None:
    from moduleforge.generate import perturb as P
    ref, rules = case4() if name == "case4" else gen2_0()
    ev = Evaluator(ref, rules)
    path = SPAN_WORK / f"{name}.json"
    st = jload(path) if path.exists() else {}
    st.setdefault("reference", dict(name=name, fingerprint=ref.fingerprint(), L1_H=dict(zip(FK, ev.l0, strict=True)),
                                    on_lattice={f"{c * 1e3:g}mm": P.on_lattice(ref, c) for c in P.LATTICES_M},
                                    rules="measured_rules(case4, CASE4_OVERRIDES)" if name == "case4" else
                                    "perturb.measured_rules(gen2_0) (plain measured rules)"))
    t0 = time.time()
    st.pop("done", None)
    if "singles" not in st:
        singles = {}
        for kind in P.MOVE_TYPES:
            rows = []
            for p in _grid(ref, kind):
                new = ev.step(ref, kind, p)
                if new is not None:
                    rows.append((ev.ratio(new), p))
            r10, r20 = [r[0][0] for r in rows], [r[0][1] for r in rows]
            imin, imax = min(range(len(rows)), key=lambda i: r20[i]), max(range(len(rows)), key=lambda i: r20[i])
            singles[kind] = dict(n_grid=sum(1 for _ in _grid(ref, kind)), n_clean=len(rows),
                                 min={"10MHz": min(r10), "20MHz": min(r20)}, max={"10MHz": max(r10), "20MHz": max(r20)},
                                 argmin_20=dict(params=rows[imin][1], r=rows[imin][0]),
                                 argmax_20=dict(params=rows[imax][1], r=rows[imax][0]),
                                 n_below_0p90=sum(v < 0.90 for v in r20), n_ge_0p98=sum(v >= 0.98 for v in r20),
                                 ranked_low=[p for _, p in sorted(rows, key=lambda t: t[0][1])[:40]],
                                 ranked_high=[p for _, p in sorted(rows, key=lambda t: -t[0][1])[:40]])
            print(f"{name} {kind}: {len(rows)} clean, r20 {min(r20):.4f}..{max(r20):.4f} ({time.time() - t0:.0f} s)", flush=True)
        st["singles"] = singles
        st["trace_width_nets_skipped"] = dict(SKIPPED_NETS)
        jdump(path, st)
    st.setdefault("compounds", {})
    combos = [c for k in P.COMPOUND_SIZES for c in itertools.combinations(P.MOVE_TYPES, k)]
    for combo in combos:
        for sense in ("min", "max"):
            key = f"{'+'.join(combo)}|{sense}"
            if key in st["compounds"]:
                continue
            sgn = 1.0 if sense == "min" else -1.0
            ranked = {k: st["singles"][k]["ranked_low" if sense == "min" else "ranked_high"] for k in combo}
            # start: best singles, falling back down each component's ranking until the chain is clean
            comps, cur = [], ev.ref
            for k in combo:
                for p in ranked[k]:
                    nxt = ev.step(cur, k, p)
                    if nxt is not None:
                        comps.append([k, p])
                        cur = nxt
                        break
                else:
                    comps = None
                    break
            if comps is None:
                st["compounds"][key] = dict(status="no clean start")
                continue
            best = ev.ratio(cur)
            n_sweeps, below = 0, set()
            for _sw in range(sweeps if sense == "min" else 1):
                n_sweeps += 1
                improved = False
                for i, (k, _p0) in enumerate(comps):
                    for p in _grid(ref, k):
                        trial = [list(c) for c in comps]
                        trial[i][1] = p
                        lay = ev.chain(trial)
                        if lay is None:
                            continue
                        r = ev.ratio(lay)
                        if r[1] < 0.90:
                            below.add(P.geometry_key(lay))
                        if sgn * r[1] < sgn * best[1] - 1e-12:
                            best, comps, improved = r, trial, True
                if not improved:
                    break
            st["compounds"][key] = dict(status="ok", sense=sense, r={"10MHz": best[0], "20MHz": best[1]},
                                        moves=[{"move_type": k, "params": p} for k, p in comps], sweeps=n_sweeps,
                                        n_distinct_below_0p90_seen=len(below))
            st["n_l1_evals"] = ev.n_l1
            st["wall_s"] = st.get("wall_s", 0.0) + (time.time() - t0)
            t0 = time.time()
            jdump(path, st)
            print(f"{name} {key}: r20 {best[1]:.4f} ({st['wall_s']:.0f} s total)", flush=True)
    # joint stage (T0386's extra step, added before gen2_0 was searched): for each 3-type combo, the top-15 x top-15 clean
    # chains of its first two components (from the single rankings), a full scan of the third on the best 8 of them, then
    # coordinate descent from the best; on Case 4 the pinned T0386 compound is a further start (recomputed, not assumed)
    for combo in [c for c in itertools.combinations(P.MOVE_TYPES, 3)]:
        key = f"{'+'.join(combo)}|min_joint"
        if key in st["compounds"]:
            continue
        a, b, c = combo
        heads = []
        for pa in st["singles"][a]["ranked_low"][:15]:
            for pb in st["singles"][b]["ranked_low"][:15]:
                lay = ev.chain([(a, pa), (b, pb)])
                if lay is not None:
                    heads.append((ev.ratio(lay)[1], pa, pb))
        heads.sort(key=lambda t: t[0])
        cands = []
        for _r, pa, pb in heads[:8]:
            for pc in _grid(ref, c):
                lay = ev.chain([(a, pa), (b, pb), (c, pc)])
                if lay is not None:
                    cands.append((ev.ratio(lay), [[a, pa], [b, pb], [c, pc]]))
        if name == "case4" and combo == ("die_row_shift", "trace_width", "wire_landing"):
            pin = [[m["move_type"], m["params"]] for m in STANDIN["moves"]]
            lay = ev.chain(pin)
            if lay is not None:
                cands.append((ev.ratio(lay), pin))
        if not cands:
            st["compounds"][key] = dict(status="no clean start")
            jdump(path, st)
            continue
        best, comps = min(cands, key=lambda t: t[0][1])
        for _sw in range(sweeps):
            improved = False
            for i, (k, _p0) in enumerate(comps):
                for p in _grid(ref, k):
                    trial = [list(q) for q in comps]
                    trial[i][1] = p
                    lay = ev.chain(trial)
                    if lay is not None and ev.ratio(lay)[1] < best[1] - 1e-12:
                        best, comps, improved = ev.ratio(lay), trial, True
            if not improved:
                break
        n90 = sum(1 for rr, _ in cands if rr[1] < 0.90)
        st["compounds"][key] = dict(status="ok", sense="min", r={"10MHz": best[0], "20MHz": best[1]},
                                    moves=[{"move_type": k, "params": p} for k, p in comps], n_heads=len(heads),
                                    n_distinct_below_0p90_seen=n90, stage="joint")
        st["n_l1_evals"] = ev.n_l1
        jdump(path, st)
        print(f"{name} {key}: r20 {best[1]:.4f}", flush=True)
    st["done"] = True
    jdump(path, st)


# -------------------------------------------------------------------------------------------------------------- solves
def solve_path(name: str, level: str) -> Path:
    return SOLVES / f"{name}__{level}.json"


def cmd_solve_one(name: str, level: str) -> None:
    from moduleforge.solvers import l2_layout as L
    cell, refinement, layers, edges = LEVELS[level]
    if cell is not None:  # E010 child_em's mesh-constant pattern: patch slot 0, solve at refinement 0
        L.CELL = (cell * 1e-3,) + tuple(L.CELL[1:])
        for attr, n in zip(("LAYERS_TOP", "LAYERS_BACK", "LAYERS_BASE"), layers, strict=True):
            setattr(L, attr, (n,) + tuple(getattr(L, attr)[1:]))
        L.WIRE_EDGES = (tuple(edges),) + tuple(L.WIRE_EDGES[1:])
    lay = layout_of(name)
    t0, c0 = time.perf_counter(), time.process_time()
    r = L.loop_inductance(lay, list(FREQS), refinement=refinement)
    m = r.meta
    ru = resource.getrusage(resource.RUSAGE_SELF)
    jdump(solve_path(name, level), dict(
        name=name, level=level, refinement=refinement, cell_m=float(L.CELL[refinement]),
        L_H=dict(zip(FK, map(float, r.L_H), strict=True)), R_ohm=dict(zip(FK, map(float, r.R_ohm), strict=True)),
        n_unknowns=int(m["n_unknowns"]), gmres_iters=[int(x) for x in m["gmres_iters"]],
        gmres_flags=[int(x) for x in m["gmres_flags"]], solver_tol_rel_L_max=float(m["solver_tol_rel_L_max"]),
        wall_s=time.perf_counter() - t0, cpu_s=time.process_time() - c0,
        peak_GB=ru.ru_maxrss * (1.0 if sys.platform == "darwin" else 1024.0) / 1e9, fingerprint=lay.fingerprint(),
        tool_version=m["tool_version"], source_sha256=m["source_sha256"],
        threads={k: os.environ.get(k) for k in THREAD_VARS}, host=os.uname().nodename,
        time_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())))


def free_pct() -> float:
    out = subprocess.run(["memory_pressure"], capture_output=True, text=True).stdout
    for line in out.splitlines():
        if "free percentage" in line:
            return float(line.split(":")[1].strip().rstrip("%"))
    return float("nan")


def swap_bound_gb() -> float:
    """Upper bound on swap in use (sysctl vm.swapusage is denied in the sandbox, project/memory/lessons.md 2026-11-15)."""
    return sum(os.path.getsize(p) for p in glob.glob("/System/Volumes/VM/swapfile*")) / 1e9


def _child(name: str, level: str, threads: int) -> int:
    env = dict(os.environ, **{k: str(threads) for k in THREAD_VARS[:4]}, MF_L2_THREADS="1")
    return subprocess.run([sys.executable, __file__, "--solve-one", name, level], env=env).returncode


LOCAL_EST_GB = {"lat1.0": 1.8, "lat0.5": 4.1, "thk_c": 2.6, "fil_f": 4.6}  # measured on Case 4 (P3, calibration note)


def cmd_run_local(stop_file: Path = OUT / "STOP") -> None:
    pairs = jload(OUT / "dev_pairs.json")
    names = all_dev_layouts(pairs)
    queue = [(n, "lat1.0") for n in names] + [(n, "lat0.5") for n in names]
    queue += [(n, lv) for n in ("case4_base", "standin_compound") for lv in ("thk_c", "fil_f")]
    queue += [(n, "lat1.0") for n in ("case4_die_shift", "case4_trace_width")]  # P3 reuse check
    log = OUT / "run_local.log"
    for name, level in queue:
        if solve_path(name, level).exists():
            continue
        while True:
            if stop_file.exists():
                return
            fp, sw = free_pct(), swap_bound_gb()
            if fp >= 30.0 and sw < 8.0 and LOCAL_EST_GB[level] <= 5.0:
                break
            with log.open("a") as f:
                f.write(f"{time.strftime('%H:%M:%S')} wait {name} {level}: free {fp}% swap<= {sw:.1f} GB\n")
            time.sleep(120)
        rc = _child(name, level, 2)
        with log.open("a") as f:
            rec = jload(solve_path(name, level)) if solve_path(name, level).exists() else {}
            f.write(f"{time.strftime('%H:%M:%S')} {name} {level} rc={rc} wall={rec.get('wall_s', 0):.0f}s "
                    f"peak={rec.get('peak_GB', 0):.2f}GB\n")


def cmd_run_vm(parallel: int, threads: int) -> None:
    """Burst VM only: run every job of vm_jobs_l2.json that has no solve file, ``parallel`` at a time (sized by memory:
    16 GB per 0.25 mm solve, so 4 on an 80 GB VM)."""
    jobs = [j for j in jload(OUT / "vm_jobs_l2.json")["jobs"] if not solve_path(j["name"], j["level"]).exists()]
    jobs.sort(key=lambda j: -j["proj_wall_s"])
    running: list[tuple[subprocess.Popen, dict]] = []
    while jobs or running:
        while jobs and len(running) < parallel:
            j = jobs.pop(0)
            env = dict(os.environ, **{k: str(threads) for k in THREAD_VARS[:4]}, MF_L2_THREADS="1")
            running.append((subprocess.Popen([sys.executable, __file__, "--solve-one", j["name"], j["level"]], env=env), j))
        time.sleep(20)
        for pr, j in list(running):
            if pr.poll() is not None:
                print(time.strftime("%H:%M:%S"), j["name"], j["level"], "rc", pr.returncode, flush=True)
                running.remove((pr, j))


# ------------------------------------------------------------------------------------------------------------ assembly
def solve_value(name: str, level: str):
    """(L at 10, 20 MHz, source) from this task's solve, else P3's solve of the same fingerprint (P3 reuse, checked)."""
    p = solve_path(name, level)
    if p.exists():
        d = jload(p)
        return [d["L_H"]["10MHz"], d["L_H"]["20MHz"]], str(p.relative_to(ROOT)), d["fingerprint"]
    q = P3_SOLVES / f"{name}__{level}.json"
    if name.startswith("case4_") and q.exists():
        d = jload(q)
        return [d["L_H"]["10000000"], d["L_H"]["20000000"]], str(q.relative_to(ROOT)), d["fingerprint"]
    return None, None, None


def ratio_estimate(R: dict) -> dict:
    """E_R per frequency from the per-level ratios R[level] = [r10, r20] (None if missing)."""
    from mfos.metrics import gci_capped, gci_step_floor, ratio_middle_term
    out = {}
    for i, f in enumerate(FK):
        g = lambda lv, i=i: None if R.get(lv) is None else R[lv][i]  # noqa: E731
        lat = (g("lat1.0"), g("lat0.5"), g("lat0.25"))
        e_lat = gci_step_floor(*lat, STEP_FLOOR, relative=True) if None not in lat else math.inf
        e_gci = gci_capped(*lat) if None not in lat else math.inf
        thk = (g("thk_c"), g("lat0.5"), g("thk_f"))
        e_thk = ratio_middle_term(*thk) if None not in thk else math.inf
        e_fil = 3.0 * abs(g("fil_f") - g("lat0.5")) if None not in (g("fil_f"), g("lat0.5")) else math.inf
        prov = 3.0 * abs(g("lat0.5") - g("lat1.0")) if None not in lat[:2] else math.inf
        steps = [None if None in (a, b) else (b - a) / b for a, b in ((lat[0], lat[1]), (lat[1], lat[2]))]
        tot = e_lat + e_thk + e_fil
        rel = (tot / lat[2]) if lat[2] else math.inf
        missing = None in lat or None in thk or g("fil_f") is None  # a level not solved yet (a VM job), not divergence
        out[f] = dict(E_lateral_step_floor=e_lat, E_lateral_gci_capped=e_gci, E_thickness=e_thk, E_filament=e_fil,
                      E_R=tot, E_R_over_r=rel, rel_steps=steps,
                      E_lateral_two_level_provisional=prov,
                      F1=("pending" if missing else "counted" if rel <= F1_CAP else "excluded"))
    return out


def _fmt_inf(x):
    return "inf" if isinstance(x, float) and math.isinf(x) else x


def _clean(o):
    if isinstance(o, dict):
        return {k: _clean(v) for k, v in o.items()}
    if isinstance(o, list):
        return [_clean(v) for v in o]
    return _fmt_inf(o)


def ladder(name: str) -> dict:
    out = {}
    for lv in LEVELS:
        v, src, fp = solve_value(name, lv)
        out[lv] = None if v is None else dict(L_H=dict(zip(FK, v, strict=True)), source=src, fingerprint=fp)
    return out


def pair_block(name: str, fp_expected: str, base_lad: dict) -> dict:
    lad = ladder(name)
    for lv, d in lad.items():  # P3's Mac solves carry the pre-change fingerprint; admitted only via the reuse check
        if d is not None and d["fingerprint"] != fp_expected and not d["source"].startswith("research/o006_p3"):
            raise RuntimeError(f"{name} {lv}: fingerprint {d['fingerprint']} is not {fp_expected}")
    R = {lv: (None if lad[lv] is None or base_lad[lv] is None else
              [lad[lv]["L_H"][f] / base_lad[lv]["L_H"][f] for f in FK]) for lv in LEVELS}
    return dict(ladder=lad, ratio_per_level={lv: (None if v is None else dict(zip(FK, v, strict=True))) for lv, v in R.items()},
                estimate=ratio_estimate(R))


def unknowns_025(name: str) -> tuple[int, str]:
    """0.25 mm unknown count: Case 4 layouts from their own lat0.5 count x the base's measured lat0.25 / lat0.5 ratio (P3's
    VM solve 4,108,580 over this task's base lat0.5 count); case6_recon by a mesh count (o003 l2_unknowns, no solve), cached."""
    if name != "case6_recon":
        base05 = jload(solve_path("case4_base", "lat0.5"))["n_unknowns"]
        own05 = jload(solve_path(name, "lat0.5"))["n_unknowns"]
        return round(own05 * CAL["lat0.25_unknowns"] / base05), "lat0.5 count x base lat0.25/lat0.5 (measured)"
    cache = OUT / "unknowns_cache.json"
    c = jload(cache) if cache.exists() else {}
    fp = layout_of(name).fingerprint()
    if c.get(name, {}).get("fingerprint") != fp:
        o3 = _load("o003_refs_t0387u", "research/scripts/o003_powersynth_references.py")
        t0 = time.perf_counter()
        c[name] = dict(fingerprint=fp, n=int(o3.l2_unknowns(layout_of(name), refinement=1)["n_unknowns"]),
                       count_s=time.perf_counter() - t0)
        jdump(cache, c)
    return c[name]["n"], "mesh count (o003 l2_unknowns at refinement 1, no solve)"


def projection(blocks: dict) -> dict:
    """INFERENCE, not F1's rule: E_R / r of each pending pair if its missing 0.25 mm step d2 = rho d1 (d1 its own measured
    1.0 -> 0.5 mm ratio step), with rho = 0.56 (P3 die_shift's observed step ratio; both of its steps are below the 0.1 % floor,
    so this rho is a noisy contraction estimate) and rho = 0.8 (the cautious case); thickness term taken as P3's larger pair
    value 3.2e-4 where missing, and the filament term as measured where present, else P3's larger 3.7e-4."""
    from mfos.metrics import gci_step_floor
    out = {}
    for n, b in blocks.items():
        R = b["ratio_per_level"]
        if R["lat1.0"] is None or R["lat0.5"] is None:
            continue
        row = {}
        for rho in (0.56, 0.8):
            e = []
            for f in FK:
                r1, r05 = R["lat1.0"][f], R["lat0.5"][f]
                r025 = r05 + rho * (r05 - r1)
                lat = gci_step_floor(r1, r05, r025, STEP_FLOOR, relative=True)
                fil = 3 * abs(R["fil_f"][f] - r05) if R.get("fil_f") else 3.7e-4
                e.append((lat + 3.2e-4 + fil) / r025)
            row[f"rho={rho}"] = dict(E_R_over_r_max_over_f=max(e), excluded=max(e) > F1_CAP)
        out[n] = row
    return out


def cmd_assemble() -> None:
    from moduleforge.generate import perturb as P
    pairs = jload(OUT / "dev_pairs.json")
    fps = {p["name"]: p["fingerprint"] for p in pairs["pairs"]} | {"case4_base": pairs["reference"]["fingerprint"]}
    base_lad = ladder("case4_base")
    # --- P3 reuse check: the current solver reproduces P3's lat1.0 / lat0.5 on the same fingerprints
    reuse = {}
    for n in ("case4_base", "case4_die_shift", "case4_trace_width"):
        for lv in ("lat1.0", "lat0.5"):
            mine, p3 = solve_path(n, lv), P3_SOLVES / f"{n}__{lv}.json"
            if mine.exists() and p3.exists():
                a, b = jload(mine), jload(p3)
                reuse[f"{n}|{lv}"] = dict(max_rel_diff=max(abs(a["L_H"][f] / b["L_H"][str(int(q))] - 1)
                                                           for f, q in zip(FK, FREQS, strict=True)),
                                          fingerprint_now=a["fingerprint"], fingerprint_p3=b["fingerprint"])
    p3_025 = {n: jload(P3_SOLVES / f"{n}__lat0.25.json")["fingerprint"] == layout_of(n).fingerprint()
              for n in ("case4_base", "case4_die_shift", "case4_trace_width")}
    reuse_ok = (all(f"{n}|lat1.0" in reuse for n in p3_025) and all(v["max_rel_diff"] < 1e-9 for v in reuse.values())
                and all(p3_025.values()))
    # base ladder: this task's solves first; P3's solves fill the levels this task did not run (lat0.25, thk_f) only if reuse_ok
    if not reuse_ok:
        base_lad = {lv: (d if d and d["source"].startswith("research/o004_f7") else None) for lv, d in base_lad.items()}
    blocks = {}
    for p in pairs["pairs"]:
        blk = pair_block(p["name"], p["fingerprint"], base_lad)
        blk["ladder"] = {lv: (d if d and d["source"].startswith("research/o004_f7") else None) for lv, d in blk["ladder"].items()}
        R = {lv: (None if blk["ladder"][lv] is None or base_lad[lv] is None else
                  [blk["ladder"][lv]["L_H"][f] / base_lad[lv]["L_H"][f] for f in FK]) for lv in LEVELS}
        blk.update(ratio_per_level={lv: (None if v is None else dict(zip(FK, v, strict=True))) for lv, v in R.items()},
                   estimate=ratio_estimate(R), move_type=p["move_type"], r_L1=p["r_L1"], label=p.get("label"))
        blocks[p["name"]] = blk
    prec = {}
    if reuse_ok:  # P3's two pairs with complete ladders (precedent, not drawn by the frozen rules' seed)
        ref = c4mod().build("base")
        from moduleforge.geometry import DC_MINUS
        tw = [{"net": DC_MINUS, "edge": e, "delta_mm": 2} for e in range(len(P.long_sides(P._net_poly(ref, DC_MINUS))))]
        tw = next((q for q in tw if P.geometry_key(P.apply(ref, "trace_width", q)) == P.geometry_key(layout_of(
            "case4_trace_width"))), tw[0])
        eq = {"case4_die_shift": ("die_row_shift", {"switch": "HS", "dx_mm": 0, "dy_mm": -1}),
              "case4_trace_width": ("trace_width", tw)}
        for n in ("case4_die_shift", "case4_trace_width"):
            lay = layout_of(n)
            blk = pair_block(n, lay.fingerprint(), base_lad)
            mt, pp = eq[n]
            blk["frozen_rule_equivalent"] = None
            if pp is not None:
                blk["frozen_rule_equivalent"] = dict(move_type=mt, params=pp,
                                                     same_geometry=P.geometry_key(P.apply(ref, mt, pp)) == P.geometry_key(lay))
            Ls = l1(lay)
            blk["r_L1"] = dict(zip(FK, (a / b for a, b in zip(Ls, l1(ref), strict=True)), strict=True))
            prec[n] = blk
    # --- (2) distributions at L1 and at 0.5 mm
    dist = []
    for n, b in blocks.items():
        r05 = b["ratio_per_level"]["lat0.5"]
        dist.append(dict(name=n, move_type=b["move_type"], r_L1=b["r_L1"], r_lat1p0=b["ratio_per_level"]["lat1.0"], r_lat0p5=r05,
                         d_l2_minus_l1_20MHz=None if r05 is None else r05["20MHz"] - b["r_L1"]["20MHz"]))
    st = blocks["standin_compound"]
    status = {n: b["estimate"]["20MHz"]["F1"] for n, b in blocks.items()} | {n: b["estimate"]["20MHz"]["F1"] for n, b in prec.items()}
    # worst case over both frequencies
    status = {n: ("excluded" if "excluded" in [b["estimate"][f]["F1"] for f in FK] else
                  "pending" if "pending" in [b["estimate"][f]["F1"] for f in FK] else "counted")
              for n, b in list(blocks.items()) + list(prec.items())}
    judged = {n: s for n, s in status.items() if s != "pending"}
    k, n = sum(s == "excluded" for s in judged.values()), len(judged)
    rate = dict(n_complete=n, n_excluded=k, n_pending=sum(s == "pending" for s in status.values()), per_pair=status,
                rate=(k / n) if n else None,
                p_no_exclusion_13_at_rate=((1 - k / n) ** N_JUDGED) if n else None,
                upper95_rate_if_zero=(1 - 0.05 ** (1 / n)) if n and k == 0 else None,
                p_no_exclusion_13_at_upper95=((0.05 ** (1 / n)) ** N_JUDGED) if n and k == 0 else None,
                note="complete = every level of the F1 estimate present; pending pairs lack the 0.25 mm level (VM)")
    low_r = [nm for nm, b in list(blocks.items()) + list(prec.items())
             if b["r_L1"]["20MHz"] <= 0.90 and status[nm] == "excluded"]
    trigger = dict(excluded_with_r_le_0p90=low_r, n_excluded=k, fires=bool(low_r) or k > 1,
                   undecided_pending=[nm for nm, s in status.items() if s == "pending"])
    f7c = dict(label="RESEARCH ONLY, NOT EVIDENCE (T0387, O004 F7(c)/(d)); development geometry 2D_Case_4",
               estimator=__doc__.split("Ratio estimate of a pair")[1].split('"""')[0].strip(), F1_cap=F1_CAP,
               levels={k2: dict(cell_mm=v[0], refinement=v[1], layers=v[2], edges=v[3]) for k2, v in LEVELS.items()},
               p3_reuse_check=dict(ok=reuse_ok, rows=reuse, p3_lat0p25_fingerprint_is_current=p3_025,
                                   fingerprint_note=("P3's Mac solves (lat1.0, lat0.5, thk_*, fil_f) carry an older "
                                                     "Layout.fingerprint than its VM lat0.25 solves and the current code; the "
                                                     "geometry is the same, shown by this task's lat1.0 / lat0.5 solves of the "
                                                     "current layouts reproducing P3's L to < 1e-9 (rows)"),
                                   rule="P3 solves (research/o006_p3/solves) are reused for a level this task did not run only if "
                                        "this task's lat1.0 (and, for the base, lat0.5) solves of the same geometry agree with P3's to < 1e-9"),
               base=dict(ladder=base_lad), standin=dict(st, label=STANDIN_LABEL), pairs=blocks, p3_precedent_pairs=prec,
               distribution_L1_vs_0p5mm=dist, exclusion=rate, f7_trigger=trigger,
               projection_inference=dict(label="INFERENCE, not F1's rule and not a result (docstring of pilot_l2.projection)",
                                         rows=projection(blocks)),
               local_0p25mm=dict(run=False, reason=(
                   "a Case 4 0.25 mm solve peaks at 15.8-15.9 GB per process (measured, research/notes/l2-thread-calibration.md "
                   "and research/o006_p3/solves/*__lat0.25.json), above this Mac's 10 GB single-process cap; the packet's "
                   "'about 8 GB each' is not what was measured. No memory knob exists in l2_layout without editing src/. "
                   "Listed in vm_jobs_l2.json")))
    jdump(OUT / "f7c_local.json", _clean(f7c))
    # --- (4) VM manifest
    jobs = []
    for nm in all_dev_layouts(pairs):
        need = ["lat0.25", "thk_c", "thk_f", "fil_f"]
        for lv in need:
            have = solve_path(nm, lv).exists() or (nm == "case4_base" and reuse_ok and (P3_SOLVES / f"{nm}__{lv}.json").exists())
            if have:
                continue
            jobs.append(dict(name=nm, level=lv, group="F7(c)", fingerprint=fps[nm]))
    if not solve_path("case6_recon", "lat0.25").exists():  # F7(b): run locally if it fits (1.10 M unknowns, ~4.2 GB)
        jobs.append(dict(name="case6_recon", level="lat0.25", group="F7(b)", fingerprint=layout_of("case6_recon").fingerprint()))
    nu_cache = {}
    for j in jobs:
        if j["level"] == "lat0.25":
            if j["name"] not in nu_cache:
                nu_cache[j["name"]] = unknowns_025(j["name"])
            nu, how = nu_cache[j["name"]]
            j.update(n_unknowns_0p25=nu, n_unknowns_basis=how, proj_peak_GB=round(CAL["lat0.25_peak_GB"] * nu / CAL["lat0.25_unknowns"], 2),
                     proj_wall_s=round(CAL["lat0.25_wall_s_2thr"] * (nu / CAL["lat0.25_unknowns"]) ** 1.44))
        elif j["level"] == "thk_f":
            j.update(proj_peak_GB=CAL["thk_f_peak_GB_mac"], proj_wall_s=round(CAL["lat0.5_wall_s_pinned_vm"] * 2.0 ** 1.44))
        else:
            j.update(proj_peak_GB=LOCAL_EST_GB[j["level"]], proj_wall_s=round(CAL["lat0.5_wall_s_pinned_vm"] * 1.1))
        j["cmd"] = f"uv run python research/o004_f7/pilot_l2.py --solve-one {j['name']} {j['level']}"
    gb = sum(j["proj_peak_GB"] for j in jobs)
    # 4 slots of 16 GB on 78 GB usable; greedy longest-first makespan
    slots = [0.0] * 4
    for j in sorted(jobs, key=lambda x: -x["proj_wall_s"]):
        slots[slots.index(min(slots))] += j["proj_wall_s"]
    mk = max(slots)
    vm = dict(label="RESEARCH ONLY (T0387): l2_layout jobs for the founder's burst VM; agents never start VMs",
              jobs=jobs, n_jobs=len(jobs), sum_peak_GB_if_serial_max=max((j["proj_peak_GB"] for j in jobs), default=0.0),
              machine=VM_MACHINE, zone=VM_ZONE, parallel=4, threads_per_solve=2,
              projection=dict(makespan_s=round(mk), makespan_h=round(mk / 3600, 2), price_usd_per_h=VM_PRICE,
                              cost_usd=round(mk / 3600 * VM_PRICE + 0.3, 2), sum_GB_all_jobs=round(gb, 1),
                              basis=("0.25 mm: peak 15.9 GB x n/4.11 M and 5,862 s (two threads, n2d) x (n/4.11 M)^1.44 "
                                     "(exponent from the pinned 0.5 -> 0.25 mm step 846 -> 6,310 s at 1.02 -> 4.11 M unknowns); "
                                     "thk_f: 8.1 GB (Mac, P3) and 846 s x 2^1.44 (2.04 M unknowns); thk_c / fil_f: P3 Mac peaks, "
                                     "846 s x 1.1. Price approximate (regular N2D custom 8 vCPU / 80 GB); "
                                     "calibration: research/notes/l2-thread-calibration.md")),
              command=("MF_GCP_PROVISION=0 MF_GCP_SPOT=auto MF_GCP_RESUME=1 MF_GCP_MAX_HOURS="
                       f"{max(2, math.ceil(mk / 3600 * 1.3) + 1)} "
                       "scripts/burst_gcp.sh --cmd \"uv sync --all-groups && uv run python research/o004_f7/pilot_l2.py "
                       "--run-vm --parallel 4 --threads 2\" research/o004_f7/solves " + VM_MACHINE + " " + VM_ZONE
                       + "  (burst_gcp.sh stops at MF_GCP_MAX_HOURS, default 6: the first burst stopped there with 10 jobs left)"),
              after=("uv run python research/o004_f7/pilot_l2.py --assemble && uv run python research/o004_f7/pilot_l2.py "
                     "--check"),
              f2_note="case6_recon: only its l2_layout 0.25 mm solve (F7(b)); its unknown count was taken locally (mesh count, "
                      "no inductance); nothing drawn on 2D_Case_6 or 2D_Case_2R")
    jdump(OUT / "vm_jobs_l2.json", vm)
    # --- span reach
    span = {}
    for nm in ("case4", "gen2_0"):
        p = SPAN_WORK / f"{nm}.json"
        if not p.exists():
            continue
        s = jload(p)
        per = {k2: dict(min=v["min"], max=v["max"], n_clean=v["n_clean"], n_grid=v["n_grid"], n_below_0p90=v["n_below_0p90"],
                        argmin_20=v["argmin_20"], argmax_20=v["argmax_20"]) for k2, v in s["singles"].items()}
        cps = {k2: v for k2, v in s.get("compounds", {}).items() if v.get("status") == "ok"}
        cmin = min(cps.values(), key=lambda v: v["r"]["20MHz"]) if cps else None
        cmax = max(cps.values(), key=lambda v: v["r"]["20MHz"]) if cps else None
        per["compound"] = dict(min=None if cmin is None else cmin["r"], max=None if cmax is None else cmax["r"],
                               argmin_20=cmin, argmax_20=cmax, n_combos_searched=len(cps), complete=bool(s.get("done")))
        lo = min([v["min"]["20MHz"] for v in per.values() if v["min"]])
        hi = max([v["max"]["20MHz"] for v in per.values() if v["max"]])
        n90 = sum(v["n_below_0p90"] for k2, v in s["singles"].items()) + sum(
            v.get("n_distinct_below_0p90_seen", 0) for v in cps.values())
        span[nm] = dict(reference=s["reference"], per_kind=per, lowest_20MHz=lo, highest_20MHz=hi,
                        lowest_10MHz=min([v["min"]["10MHz"] for v in per.values() if v["min"]]),
                        highest_10MHz=max([v["max"]["10MHz"] for v in per.values() if v["max"]]),
                        n_distinct_below_0p90_found_lower_bound=n90, span_0p75_0p98_with_3_below_0p90=bool(
                            lo <= 0.75 and hi >= 0.98 and n90 >= 3), lowest_reachable_lower_end=lo,
                        n_l1_evals=s.get("n_l1_evals"), search_complete=bool(s.get("done")))
    jdump(OUT / "span_reach.json", _clean(dict(
        label="RESEARCH ONLY, NOT EVIDENCE (T0387): L1 span reachable by the frozen rules on the development layouts only "
              "(founder correction 2026-11-16 17:55 UTC, O004 F2); nothing drawn on 2D_Case_2R or 2D_Case_6",
        method=("T0386's structured search: exhaustive integer scans of each single move's frozen range (DRC-clean, changed); "
                "then for each of the ten 2- and 3-type compounds (MOVE_TYPES order, stagewise: every intermediate DRC-clean "
                "and changed) coordinate descent at 20 MHz from the best clean singles, each coordinate a full scan of one "
                "component's frozen range, up to 3 sweeps for the minimum and 1 for the maximum. Counts below 0.90 are "
                "distinct geometries seen (a lower bound on what the rules reach)."),
        l1_model="moduleforge.physics.peec loop_inductance", rules_sha256=P.rules_sha256(), references=span)))
    print("assembled", json.dumps(rate), json.dumps(trigger))


# --------------------------------------------------------------------------------------------------------------- check
def cmd_check() -> int:
    from moduleforge.generate import perturb as P
    errs = []
    need = ("dev_pairs.json", "f7c_local.json", "vm_jobs_l2.json", "span_reach.json")
    for f in need:
        if not (OUT / f).exists():
            errs.append(f"missing {f}")
    if errs:
        print("\n".join(errs))
        return 1
    pairs, f7c, vm, span = (jload(OUT / f) for f in need)
    ref = c4mod().build("base")
    if pairs["reference"]["fingerprint"] != ref.fingerprint():
        errs.append("Case 4 base fingerprint differs")
    same_rules = pairs["rules_sha256"] == P.rules_sha256()
    if not same_rules:  # the pairs are fixed geometries: identified by fingerprint, not rebuilt under newer rules
        print(f"note: perturb.rules_sha256 is now {P.rules_sha256()[:8]}..., the pairs were drawn under "
              f"{pairs['rules_sha256'][:8]}...; checking them by recorded fingerprint, not by rebuild")
    kinds = {p["move_type"] for p in pairs["pairs"]}
    if kinds != set(P.PAIR_KINDS):
        errs.append(f"dev pairs miss kinds {set(P.PAIR_KINDS) - kinds}")
    if not any(p["r_L1"]["20MHz"] >= 0.98 for p in pairs["pairs"]):
        errs.append("no dev pair with r >= 0.98 at L1")
    st = next((p for p in pairs["pairs"] if p["name"] == "standin_compound"), None)
    if st is None or st.get("label") != STANDIN_LABEL or abs(st["r_L1"]["20MHz"] - STANDIN_R20) > 5e-4:
        errs.append("stand-in compound missing, mislabelled or not at r = 0.7616")
    for p in pairs["pairs"]:  # layouts rebuild to their recorded fingerprints (no solve), while the rules are unchanged
        if same_rules and P.apply(ref, p["move_type"], p["params"]).fingerprint() != p["fingerprint"]:
            errs.append(f"{p['name']}: fingerprint does not rebuild")
    names = set(all_dev_layouts(pairs))
    if set(f7c["pairs"]) != names - {"case4_base"}:
        errs.append("f7c_local.json pairs differ from dev_pairs.json")
    if f7c["standin"]["label"] != STANDIN_LABEL:
        errs.append("f7c stand-in label")
    fps = {p["name"]: p["fingerprint"] for p in pairs["pairs"]} | {"case4_base": pairs["reference"]["fingerprint"]}
    for f in sorted(SOLVES.glob("*.json")):  # every solve file belongs to a known layout and matches its fingerprint
        d = jload(f)
        if d["name"] in fps and d["fingerprint"] != fps[d["name"]]:
            errs.append(f"{f.name}: fingerprint mismatch")
    # every stored ladder value equals its solve file, and the ratios, estimates and F1 statuses of the drawn pairs and of
    # P3's precedent pairs recompute from the solve files (reviews T0429 finding 4, T0433 finding 2)
    def _lad_ok(nm, lad):
        for lv, d in lad.items():
            if d is None:
                continue
            v, src, fp = solve_value(nm, lv)
            if v is None or src != d["source"] or [d["L_H"][f] for f in FK] != v:
                errs.append(f"{nm} {lv}: stored ladder value differs from {d['source']}")
    base_lad = f7c["base"]["ladder"]
    _lad_ok("case4_base", base_lad)
    status = {}
    for group in ("pairs", "p3_precedent_pairs"):
        for nm, b in f7c[group].items():
            _lad_ok(nm, b["ladder"])
            R = {lv: (None if b["ladder"].get(lv) is None or base_lad.get(lv) is None else
                      [b["ladder"][lv]["L_H"][f] / base_lad[lv]["L_H"][f] for f in FK]) for lv in LEVELS}
            for lv in LEVELS:
                st_r = b["ratio_per_level"].get(lv)
                if (st_r is None) != (R[lv] is None) or (st_r is not None and any(
                        abs(st_r[f] - R[lv][i]) > 1e-15 for i, f in enumerate(FK))):
                    errs.append(f"{nm} {lv}: stored ratio does not recompute from the solve files")
            e = _clean(ratio_estimate(R))
            for f in FK:
                a, c = e[f]["E_R"], b["estimate"][f]["E_R"]
                if (a == "inf") != (c == "inf") or (a != "inf" and abs(a - c) > 1e-15):
                    errs.append(f"{nm} {f}: E_R does not recompute")
                if e[f]["F1"] != b["estimate"][f]["F1"]:
                    errs.append(f"{nm} {f}: F1 status does not recompute")
            fs = [e[f]["F1"] for f in FK]
            status[nm] = "excluded" if "excluded" in fs else "pending" if "pending" in fs else "counted"
            if group == "pairs" and abs(b["r_L1"]["20MHz"] - next(
                    p for p in pairs["pairs"] if p["name"] == nm)["r_L1"]["20MHz"]) > 1e-15:
                errs.append(f"{nm}: L1 ratio differs between files")
    ex, trig = f7c["exclusion"], f7c["f7_trigger"]
    if ex["per_pair"] != status:
        errs.append("exclusion per-pair statuses do not recompute")
    judged = {n: s for n, s in status.items() if s != "pending"}
    k = sum(s == "excluded" for s in judged.values())
    if (ex["n_excluded"], ex["n_complete"]) != (k, len(judged)):
        errs.append("exclusion counts do not recompute")
    rl = {n: b["r_L1"]["20MHz"] for g in ("pairs", "p3_precedent_pairs") for n, b in f7c[g].items()}
    low = sorted(n for n, s in status.items() if s == "excluded" and rl[n] <= 0.90)
    if sorted(trig["excluded_with_r_le_0p90"]) != low or trig["fires"] != (bool(low) or k > 1):
        errs.append("F7 trigger does not recompute")
    # every level a dev layout's F1 estimate still lacks is in the VM manifest, and the F7(b) Case 6 job is there
    jobset = {(j["name"], j["level"]) for j in vm["jobs"]}
    for nm in names:
        lad = base_lad if nm == "case4_base" else f7c["pairs"][nm]["ladder"]
        for lv in ("lat0.25", "thk_c", "thk_f", "fil_f"):
            if lad.get(lv) is None and (nm, lv) not in jobset:
                errs.append(f"{nm}: no {lv} value and no VM job")
    if ("case6_recon", "lat0.25") not in jobset and not solve_path("case6_recon", "lat0.25").exists():
        errs.append("F7(b) Case 6 0.25 mm job missing")
    for j in vm["jobs"]:
        if j["name"] in fps and j["fingerprint"] != fps[j["name"]]:
            errs.append(f"VM job {j['name']}: fingerprint mismatch")
        if j["level"] not in LEVELS or not j["cmd"].endswith(f"--solve-one {j['name']} {j['level']}"):
            errs.append(f"VM job {j['name']} {j['level']}: bad level or command")
    # exclusion figures recompute
    ex = f7c["exclusion"]
    k, n = ex["n_excluded"], ex["n_complete"]
    if n and abs(ex["p_no_exclusion_13_at_rate"] - (1 - k / n) ** N_JUDGED) > 1e-12:
        errs.append("exclusion probability does not recompute")
    if set(span["references"]) != {"case4", "gen2_0"}:
        errs.append("span_reach.json must cover case4 and gen2_0 only")
    c4s = span["references"].get("case4")
    if c4s and c4s["lowest_20MHz"] > STANDIN_R20 + 5e-4:
        errs.append("Case 4 span search lowest is above the pinned 0.7616 compound (search weaker than T0386's)")
    note = ROOT / "research" / "notes" / "o004-f7-l2-pilot.md"
    if not note.exists():
        errs.append("note missing")
    print("\n".join(errs) if errs else "check OK")
    return 1 if errs else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--pairs", action="store_true")
    g.add_argument("--span")
    g.add_argument("--run-local", action="store_true")
    g.add_argument("--solve-one", nargs=2)
    g.add_argument("--run-vm", action="store_true")
    g.add_argument("--assemble", action="store_true")
    g.add_argument("--check", action="store_true")
    ap.add_argument("--parallel", type=int, default=4)
    ap.add_argument("--threads", type=int, default=2)
    a = ap.parse_args()
    if a.pairs:
        cmd_pairs()
    elif a.span:
        cmd_span(a.span)
    elif a.run_local:
        cmd_run_local()
    elif a.solve_one:
        cmd_solve_one(*a.solve_one)
    elif a.run_vm:
        cmd_run_vm(a.parallel, a.threads)
    elif a.assemble:
        cmd_assemble()
    else:
        return cmd_check()
    return 0


if __name__ == "__main__":
    sys.exit(main())
