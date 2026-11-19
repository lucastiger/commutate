"""E011 runner (O008): a seeded local search recovers planted loop-inductance headroom from degraded copies of a designer
proxy W*, where inductance-blind heuristics do not.  Design: experiments/drafts/E011.yaml (T0382).  Objective:
project/objectives/O008/objective.yaml.  Row schema: experiments/runners/e011_metrics.py (n7, T0381).  SI units, float64;
inductance in H, temperature in K, parameters in mm (derivative.Params).

Reuse (by import, never copied): experiments/runners/e010_run.py for the references (judged_reference for 2D_Case_2R through
the frozen T0263 script, dev_reference for 2D_Case_4 and gen2_0, both with e008_rules: the reference's own measured rules,
no relaxed floor), the EM levels and band order (EM_LEVELS, BAND), the cost model (em_unknowns, em_cost, fem_cost),
thread pinning (thread_count, child_env), the Scheduler (memory-capped subprocess solves, one JSON result file per solve =
the checkpoint) and the phase split (NeedsLargerMachine / phase_stop, PHASE_B_EXIT).  Every l2_layout and thermal solve is
E010's child (``e010_run.py --child``) on a pickled layout {"D": layout}.

Pipeline per layout (``run_layout``; the same code in every mode, solvers and stages injected):
  F2   W rebuilt from params_of(W): DRC-clean, fingerprint; in_domain(W) under reach and under E010's legacy generator;
       twin-versus-reconstruction symmetric difference; T0349's coordinate-range test (W against the legacy pool's drawn
       range) and attached-form test (slots that straddle or overlap their column); the L1 lower tail of the random
       screen's pool relative to W (D0023), legacy and reach samplers
  P    the frozen proxy rule (control.proxy_descent, reach=True, min_gain = control.MIN_GAIN_H) from W; L2 of W and of the
       descent's end; W* = control.choose_proxy; hottest-die Tj of W and W* at the thermal reference's level 0; the 2 K
       fallback to the dies-fixed descent (O008 scope_in)
  D    control.draw_degradations from W* on the degradation sub-seed; a D_j outside in_domain(reach=True) is a defect of the
       family (T0414), returned as out of window (redrawn, never scored); R_D at L2 in waves (each wave solves the
       attempts the previous replay asked for; the replay is deterministic)
  S    per accepted draw: the search (local.local_search, search sub-seed), nulls (a) seed, (b) widen, (d) compact,
       ablations (c) random screen and (e) proxy alone; then L2 of the shortlists and end points, the best by
       local_search's own rule (lowest L_sub, ties by L1 rank), the band levels of every scored layout and of W*
  rows one per (layout, role, draw), n7's columns plus reported columns; s_j = L_sub(best_j) / L_sub(W*) - 1 and
       b_j = 2 e_R(best_j, W*) (D0008 band rule, mfos.metrics.ratio_band_estimate)

Modes
  (default)   registered run through mfos.evidence.ExperimentRun (sealed seed, config from MFOS_SPEC_JSON); resumes from
              --workdir / $E011_WORKDIR; phase B (a solve above this machine's memory) exits PHASE_B_EXIT
  --selftest  fake solvers and fake stages, the full L2-file, row, metric, recompute and artifact path; planted outcomes:
              PASS; a null recovering W* on one layout -> INCONCLUSIVE; a seed null meeting A1 -> INVALID; fewer than two
              counted layouts -> INVALID.  Exit 0 iff all hold
  --smoke     real code on gen2_0 locally: reduced budgets, one draw, L2 at E010's coarsest valid level (thk_c: 0.5 mm
              cells, 5/3/3 layers; 0.5 mm is the coarsest cell the 0.5 mm design grid allows); b_j = 0 by construction
              there (one level stands in for all five)
  --dev       development seeds only, 2D_Case_2R and 2D_Case_4: the L1 stages locally (checkpointed in --workdir), Tj at
              level 0 locally, then experiments/drafts/E011.dev_jobs.json, the L2 job manifest for a burst VM with a cost
              estimate per job (rewritten after every stage; ``status`` says whether it is complete)
  --dev-solve MANIFEST  on the burst VM: solve every wave-1 job (one per (fingerprint, level), count asserted), select
              each shortlist's best by (L, L1 rank) from every job's purposes, solve its band; refuses a manifest that
              is not complete (schema e011.dev_jobs/2) or whose code stamp differs; exit 3 unless all results converge
  --dev-rows MANIFEST  (T0471) development rows from the burst's L2 results in --workdir (default
              research/o008_e011_dev/dev_l2), no solve: W* by choose_proxy at L2, R_D measured, s and b per role and draw,
              the gated metrics, band bound, ranking stability, joint operating characteristic, measured VM sizing
  Work directories carry code_stamp.json (code_stamp): a resumed run refuses checkpoints from other code or config.
  --child JOB internal: E010's child (one solve in a subprocess)
"""
from __future__ import annotations

import argparse
import contextlib
import dataclasses
import datetime as dt
import hashlib
import json
import math
import os
import pickle
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(ROOT / "tools" / "mfos"), str(ROOT / "src"), str(HERE)]

import yaml  # noqa: E402
from mfos import metrics as MX  # noqa: E402

import e010_run as E  # noqa: E402  (references, rules, cost model, scheduler, phase split, thread pinning)
import e011_metrics as N7  # noqa: E402  (n7: the row schema and the reference metric implementations)

EID = "E011"
DRAFT = ROOT / "experiments" / "drafts" / "E011.yaml"
REGISTERED = ROOT / "experiments" / "specs" / "E011.yaml"
DEV_JOBS = ROOT / "experiments" / "drafts" / "E011.dev_jobs.json"
E010_SPEC = ROOT / "experiments" / "specs" / "E010.yaml"
OBJECTIVE = ROOT / "project" / "objectives" / "O008" / "objective.yaml"
CODE = ("src/moduleforge/generate/derivative.py", "src/moduleforge/generate/twin.py",
        "src/moduleforge/optimize/local.py", "src/moduleforge/optimize/control.py", "src/moduleforge/optimize/nulls.py")
METRICS = ("control_layout_pass_min", "reach_outside_max", "null_beaten_min", "control_shortfall_median_max")
TAGS = {"degrade": 0x0E011D01, "search": 0x0E011D02, "random_screen": 0x0E011D03}  # nonzero domain tags, first entry
log = E.log


def sha256_file(p) -> str:
    return hashlib.sha256((ROOT / p).read_bytes()).hexdigest()


def canon_sha(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def load_spec() -> dict:
    env = os.environ.get("MFOS_SPEC_JSON")
    if env:
        return json.loads(Path(env).read_text()) if Path(env).exists() else json.loads(env)
    return yaml.safe_load((REGISTERED if REGISTERED.exists() else DRAFT).read_text())


def cfg10() -> dict:
    return yaml.safe_load(E010_SPEC.read_text())["config"]


def sub_seed(seed: int, purpose: str, *k: int) -> int:
    """A purpose's integer seed from the run seed: SeedSequence([tag, seed, *k]) with a nonzero tag first, so no stream
    can equal another purpose's (numpy drops trailing zero words: [s, li, j, 0] == [s, li, j], founder 2026-11-16)."""
    return int(np.random.SeedSequence([TAGS[purpose], int(seed), *map(int, k)]).generate_state(1)[0])


def objective_criteria():
    acc = yaml.safe_load(OBJECTIVE.read_text())["acceptance"]
    ns = lambda c: SimpleNamespace(**c)  # noqa: E731
    return [ns(c) for c in acc["pass_all"]], [ns(c) for c in acc["fail_any"]]


# ------------------------------------------------------------------------------------------------ real stages
def _mods():
    from moduleforge.drc.rules import check
    from moduleforge.generate import derivative as D
    from moduleforge.generate import twin as T
    from moduleforge.optimize import control as C
    from moduleforge.optimize import local as L
    from moduleforge.optimize import nulls as NU
    from moduleforge.optimize import search as S
    return SimpleNamespace(check=check, D=D, T=T, C=C, L=L, NU=NU, S=S)


@contextlib.contextmanager
def dc_minus_reading(side: int | None):
    """Sensitivity only (T0379 finding 1): force twin._net_side's reading of the DC- column to ``side`` (None: the frozen
    reading, twin._net_side unchanged).  The reach jumps (_straddle, _outer_edge) read the side through this function."""
    if side is None:
        yield
        return
    M = _mods()
    from moduleforge.geometry.layout import DC_MINUS
    orig, i = M.T._net_side, M.D.NETS.index(DC_MINUS)
    M.T._net_side = lambda p, net_i: int(side) if net_i == i else orig(p, net_i)
    try:
        yield
    finally:
        M.T._net_side = orig


@dataclasses.dataclass
class LayCtx:
    name: str
    spec: Any
    reference: Any
    W: Any
    area_m2: float
    info: dict


class RealOps:
    fake = False

    def __init__(self):
        self.M = _mods()
        self._c10 = None

    @property
    def c10(self):
        if self._c10 is None:
            self._c10 = cfg10()
        return self._c10

    def l1(self, lay) -> float:
        return float(self.M.T._l1(lay))

    def vec(self, lay) -> np.ndarray:
        return self.M.D.params_of(lay).to_vector()

    def drc_clean(self, lc, lay) -> bool:
        return not self.M.check(lay, lc.spec.rules)

    def in_domain(self, lc, lay, reach: bool = True) -> tuple[bool, str]:
        return self.M.D.in_domain(lc.spec, self.M.D.params_of(lay), reach=reach)

    def load(self, name: str) -> LayCtx:
        c = self.c10
        if name == "2D_Case_2R":
            rc = E.judged_reference(next(x for x in c["references"] if x["reference_id"] == name), c)
        elif name == "2D_Case_4":
            rc = E.dev_reference("case4", c)
        elif name == "gen2_0":
            rc = E.dev_reference("gen2_0", c)
        else:
            raise ValueError(f"not an E011 development layout: {name}")
        W = self.M.T.twin(rc.reference, rc.spec, with_l1=False)[0]
        bp = rc.reference.baseplate_outline.bounds
        return LayCtx(name, rc.spec, rc.reference, W, (bp[2] - bp[0]) * (bp[3] - bp[1]),
                      {"rules_record": rc.info.get("rules_record"), "reference_fingerprint": rc.reference.fingerprint()})

    def f2(self, lc: LayCtx, pool_n: int, seed: int) -> dict:
        """F2 facts of one layout (objective F2; T0349 section 2.2; D0023)."""
        M, D = self.M, self.M.D
        p = D.params_of(lc.W)
        w = p.to_vector()
        out: dict[str, Any] = {}
        try:
            rb = D.build(lc.spec, p)
            out["rebuild_drc"] = [str(v) for v in M.check(rb, lc.spec.rules)][:8]
            out["rebuild_fingerprint_equal"] = rb.fingerprint() == lc.W.fingerprint()
        except ValueError as e:
            out["rebuild_error"] = str(e)
        out["in_domain_reach"] = list(D.in_domain(lc.spec, p, reach=True))
        out["in_domain_legacy"] = list(D.in_domain(lc.spec, p, reach=False))
        dr = M.T.difference_record(lc.reference, lc.W)
        out["symdiff_total_mm2"], out["symdiff_mm2"] = dr["symdiff_area_total_mm2"], dr["symdiff_area_mm2"]
        out["reference_copper_mm2"] = dr["reference_copper_mm2"]
        out["max_die_displacement_mm"] = dr["max_die_displacement_mm"]
        # attached-form test (T0349 test 3's premise): slots whose extent straddles or overlaps their column's u range
        cols = dict(zip(D.NETS, p.cols, strict=True))
        strad = []
        for i, s in enumerate(p.sequence()):
            c0, _, c1, _ = cols[s[0]]
            u0, _, u1, _ = p.slots[i]
            if u0 < c1 - 1e-9 and u1 > c0 + 1e-9:
                strad.append({"slot": i, "net": s[0], "u": [u0, u1], "col_u": [c0, c1]})
        out["slots_overlapping_column"] = strad
        out["read_sides"] = list(self.M.C.read_sides(p))
        out["feasible_sides"] = [list(x) for x in self.M.C.feasible_sides(lc.spec, p)]
        l1w = self.l1(lc.W)
        out["l1_W_H"] = l1w
        for kind, reach in (("legacy", False), ("reach", True)):
            def gen(spec, n, sd, reach=reach):
                return D.generate(spec, n, sd, reach=reach)
            pool = list(M.S.candidate_stream(lc.spec, pool_n, sub_seed(seed, "random_screen", 999, int(reach)), gen))
            ex = np.array([self.l1(x) / l1w - 1.0 for x in pool])
            rec = {"n": len(pool), "min_excess": float(ex.min()) if len(ex) else math.nan,
                   "within": {f"{t:g}": int(np.sum(ex <= t)) for t in (0.0, 0.02, 0.03, 0.05, 0.07, 0.10, 0.15)}}
            if kind == "legacy" and len(pool):  # T0349 coordinate-range test against the drawn pool
                A = np.array([self.vec(x) for x in pool])
                lo, hi = A.min(0), A.max(0)
                rec["W_outside_range"] = [D.Params.NAMES[i] for i in range(4, 40)
                                          if not (lo[i] - 1e-9 <= w[i] <= hi[i] + 1e-9)]
                rec["manhattan_to_W_min_mm"] = float(np.abs(A[:, 4:40] - w[4:40]).sum(1).min())
            out[f"pool_{kind}"] = rec
        return out

    def proxy(self, lc, step_limit: int, dies_fixed=False, reach=True, min_gain=None, side=None):
        kw = {} if min_gain is None else {"min_gain": float(min_gain)}
        with dc_minus_reading(side):
            return self.M.C.proxy_descent(lc.spec, self.M.D.params_of(lc.W), self.M.T._l1, step_limit,
                                          dies_fixed=dies_fixed, reach=reach, **kw)

    def degrade(self, lc, Wstar, seed: int, li: int, n: int, r_d, redraw_limit: int, dcfg: dict, window):
        C = self.M.C
        cfg = C.DegradeConfig(**{k: (tuple(v) if isinstance(v, list) else v) for k, v in dcfg.items()})
        return C.draw_degradations(lc.spec, Wstar, seed, li, n, r_d, redraw_limit, self.M.T._l1, cfg, tuple(window))

    def lcfg(self, d: dict):
        return self.M.L.LocalConfig(**d)

    def search(self, lc, Dl, seed: int, lcfg: dict, l_sub, tag: str, side=None):
        L = self.M.L
        with dc_minus_reading(side):
            return L.local_search(lc.spec, Dl, seed, L.LocalSolvers(self.M.T._l1, l_sub, tag), self.lcfg(lcfg), None)

    def null(self, role: str, lc, Dl, step_limit: int):
        NU = self.M.NU
        if role == "seed":
            return NU.null_seed(lc.spec, Dl)
        return (NU.null_widen if role == "widen" else NU.null_compact)(lc.spec, Dl, step_limit=step_limit)

    def random_screen(self, lc, Dl, seed: int, lcfg: dict, l_sub, tag: str):
        L = self.M.L
        return self.M.NU.ablation_random_screen(lc.spec, Dl, seed, L.LocalSolvers(self.M.T._l1, l_sub, tag),
                                                self.lcfg(lcfg))

    def proxy_alone(self, lc, Dl, budget: int, step_limit: int):
        return self.M.C.proxy_alone(lc.spec, Dl, self.M.T._l1, budget, step_limit=step_limit)

    def movable(self) -> tuple[int, ...]:
        return tuple(self.M.L.movable_indices())

    def rebuild(self, lc: LayCtx, params) -> Any:
        return self.M.D.build(lc.spec, self.M.D.Params.from_vector(np.asarray(params, float)))

    def choose(self, W, desc, l_sub):
        return self.M.C.choose_proxy(W, desc, l_sub)

    def search_select(self, short: list[dict], lsub: list[float]) -> int:
        """local_search's rule (local.py): the lowest L_sub, ties by rank."""
        return min(range(len(short)), key=lambda i: (lsub[i], i))

    def spearman(self, a, b) -> float:
        return self.M.L.spearman(a, b)


# ------------------------------------------------------------------------------------------------ solves (L2, thermal)
class Solves:
    """l2_layout and thermal solves as E010 jobs: one JSON result per (fingerprint, level) under <wd>/solves.  ``mode``:
    'solve' runs them through E010's Scheduler; 'record' (dev, local) only records them for the manifest."""

    def __init__(self, wd: Path, cm: dict, sched, threads: int, mode: str = "solve", fake_area: dict | None = None,
                 freq_hz: float | None = None):
        self.wd, self.cm, self.sched, self.threads, self.mode = Path(wd), cm, sched, threads, mode
        self.freq_hz = freq_hz  # config.levels.freq_hz (review item 5: never hard-coded); em_job refuses None
        self.wanted: dict[str, dict] = {}  # out path -> job (record mode and the cost report)
        self.area: dict[str, float] = dict(fake_area or {})
        (self.wd / "solves").mkdir(parents=True, exist_ok=True)
        (self.wd / "lay").mkdir(parents=True, exist_ok=True)

    def _ctx(self, lay) -> str:
        p = self.wd / "lay" / f"{lay.fingerprint()}.pkl"
        if not p.exists():
            tmp = p.with_suffix(".tmp")
            tmp.write_bytes(pickle.dumps({"D": lay}))
            tmp.replace(p)
        return str(p)

    def out(self, fp: str, typ: str, level) -> Path:
        return self.wd / "solves" / f"{typ}_{level}_{fp}.json"

    def em_job(self, lay, level: str, lname: str, purpose: str, params=None, rank: int | None = None) -> dict:
        """One l2_layout job; ``rank``: the layout's L1 rank inside the shortlist named by ``purpose`` (None elsewhere)."""
        fp = lay.fingerprint()
        if self.freq_hz is None:
            raise RuntimeError("Solves.freq_hz is not set (config.levels.freq_hz)")
        n = E.em_unknowns(self.area[lname], E.EM_LEVELS[level][0], level, self.cm)
        t, m = E.em_cost(n, level, self.cm)
        prior = self.cm.get("em_level_mem_prior", {}).get(level, 1.0)
        return {"type": "em", "ctx": self._ctx(lay), "which": "D", "fp": fp, "family": None,
                "out": str(self.out(fp, "em", level)), "threads": self.threads, "ref": lname, "level": level,
                "freq_hz": float(self.freq_hz), "mem_GB": m * prior, "mem_model_GB": m, "est_s": t, "unknowns": n, "priority": 1,
                "purpose": purpose, "rank": rank, "params": params}

    def th_job(self, lay, lname: str, typ: str, kw: dict, purpose: str) -> dict:
        fp = lay.fingerprint()
        dofs = self.area[lname] * float(self.cm["fake_sizes_per_m2"]["fem"]["0"])
        t, m = E.fem_cost(dofs, self.cm)
        lv = "cal" if typ == "calibrate" else str(kw.get("level", 0))
        return {"type": typ, "ctx": self._ctx(lay), "which": "D", "fp": fp, "family": None,
                "out": str(self.out(fp, typ, lv)), "threads": 1, "ref": lname, "mem_GB": m * 1.5, "mem_model_GB": m,
                "est_s": t * (self.cm["calibration_solves"] if typ == "calibrate" else 1), "priority": 2,
                "purpose": purpose} | kw

    @staticmethod
    def rec(job: dict) -> dict | None:
        return E.Scheduler.done(job)

    def run(self, jobs: list[dict], local: bool = False) -> None:
        """Solve the jobs that have no result (record mode: record them; ``local`` jobs run even in record mode)."""
        for j in jobs:  # one entry per (fingerprint, level); every purpose that asked for it, with its rank (T0430/T0431)
            w = self.wanted.setdefault(j["out"], dict(j, purposes=[]))
            tag = {"purpose": j["purpose"], "rank": j.get("rank")}
            if tag not in w["purposes"]:
                w["purposes"].append(tag)
        todo = [j for j in jobs if self.rec(j) is None]
        if not todo or (self.mode == "record" and not local):
            return
        self.sched.submit(todo)
        while self.sched.queue or self.sched.running:
            self.sched.step()

    def L(self, lay, level: str) -> float | None:
        r = self.rec({"out": str(self.out(lay.fingerprint(), "em", level))})
        return None if r is None else float(r["L_H"])

    def em_ok(self) -> tuple[bool, int, list[str]]:
        """Every em result file is usable under E010's predicate (em_failures); a failed solve record counts as bad."""
        bad, n = [], 0
        for p in sorted((self.wd / "solves").glob("em_*.json")):
            if p.name.endswith(".job.json"):
                continue  # E010's Scheduler writes the child's job spec beside its result as <out>.job.json
            r = json.loads(p.read_text())
            n += 1
            why = ([f"status {r.get('status')}"] if r.get("status") != "ok" else []) + em_failures(r)
            if why:
                bad.append(f"{p.name}: {'; '.join(why)}")
        return not bad, n, bad


def em_failures(r: dict) -> list[str]:
    """E010's convergence predicate (e010_run.band_solve_failures, T0318 finding 0) on one l2_layout result: L_H not
    finite; no convergence record or a GMRES flag != 0; solver_tol_rel_L_max not finite.  A missing key fails closed.
    band_solve_failures takes one record per BAND level, so the record is passed once per level and the per-level
    messages are merged (the predicate itself is E010's, not a copy)."""
    return sorted({m.split(": ", 1)[1] for m in E.band_solve_failures([r] * len(E.BAND), "x")})


# ------------------------------------------------------------------------------------------------ helpers
def cached(path: Path, fn):
    """Stage checkpoint: the pickled result of ``fn`` at ``path`` (computed once; a resumed run reuses it)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return pickle.loads(path.read_bytes())
    t0 = time.time()
    v = fn()
    tmp = path.with_suffix(".tmp")
    tmp.write_bytes(pickle.dumps(v))
    tmp.replace(path)
    path.with_suffix(".wall").write_text(f"{time.time() - t0:.3f}\n")  # compute wall s of this stage (L1 cost model)
    return v


class StaleCheckpoint(RuntimeError):
    """A work directory's checkpoints were written by other code or another frozen block (founder 2026-11-17 item 3)."""


STAMP_KEYS = ("frozen", "levels", "dev", "smoke", "layout_index", "layouts", "counted_layouts")


def code_stamp(spec: dict) -> dict:
    """What a stage checkpoint depends on: every src/moduleforge module, the two runners (E010's references and rules,
    this file's sub-seed tags and stage calls), and the config blocks that set the stages (STAMP_KEYS; not the recorded
    hashes or the cost text, which --freeze-report refreshes)."""
    files = sorted(str(q.relative_to(ROOT)) for q in (ROOT / "src" / "moduleforge").rglob("*.py"))
    files += ["experiments/runners/e010_run.py", "experiments/runners/e011_run.py"]
    h = hashlib.sha256()
    for f in files:
        h.update(f.encode() + b"\0" + sha256_file(f).encode() + b"\n")
    cfg = spec["config"]
    return {"code_tree_sha256": h.hexdigest(), "n_files": len(files),
            "code_under_test": {q: sha256_file(q) for q in CODE},
            "config_sha256": canon_sha({k: cfg.get(k) for k in STAMP_KEYS})}


def check_stamp(wd: Path, stamp: dict) -> None:
    """Refuse a work directory whose checkpoints carry another stamp, or checkpoints with no stamp (attempt 1's)."""
    wd = Path(wd)
    p = wd / "code_stamp.json"
    if p.exists():
        old = json.loads(p.read_text())
        if old != stamp:
            diff = sorted(k for k in stamp if old.get(k) != stamp[k])
            raise StaleCheckpoint(f"{wd}: checkpoints were written with another code stamp (differs in {diff}); move "
                                  "the directory aside and rerun, never mix stages from two code versions")
        return
    if any((wd / "stages").rglob("*.pkl")) or any((wd / "solves").glob("*.json")):
        raise StaleCheckpoint(f"{wd}: checkpoints without a code stamp (written before T0382 attempt 2); move it aside")
    wd.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(stamp, indent=1))


def terminal(role: str, obj) -> tuple[str, bool, str]:
    """(n7 terminal_kind, capped, raw) of a role's run.  The search: 'budget' -> capped; 'max_iters' -> step_limit;
    'no_moves' (its perturbation found no valid layout) -> no_moves, capped.  Nulls (b), (d): local_optimum /
    step_limit; 'no_moves' (nulls.NO_MOVES, T0425: the first neighbourhood was empty, the null never moved) -> no_moves,
    capped, so it is never a resolved failure for A3 and is reported (review T0444; the founder confirms with the
    spec).  (a): seed.  (c): budget.  (e): the descent's."""
    if role == "seed":
        return "seed", False, "seed"
    if role == "random_screen":
        return "budget", True, "budget"
    if role == "search":
        raw = obj.stats["stop_reason"]
        return {"budget": ("budget", True), "max_iters": ("step_limit", True),
                "no_moves": ("no_moves", True)}.get(raw, ("local_optimum", False)) + (raw,)
    raw = obj.kind if hasattr(obj, "kind") else obj.terminal
    return {"step_limit": ("step_limit", True), "budget": ("budget", True),
            "no_moves": ("no_moves", True)}.get(raw, ("local_optimum", False)) + (raw,)


def dist(v, w, idx) -> tuple[int, float]:
    d = np.abs(np.asarray(v, float)[list(idx)] - np.asarray(w, float)[list(idx)])
    return int(np.sum(d > 1e-9)), float(np.sum(d))


class Recorder:
    """The l_sub a search or the random screen is given: it records each shortlist layout and returns the stored L2 value
    (NaN before it is solved).  The runner then solves the shortlist and applies local_search's own selection rule."""

    def __init__(self, sv: Solves, level: str):
        self.sv, self.level, self.lays = sv, level, {}

    def __call__(self, lay) -> float:
        self.lays[lay.fingerprint()] = lay
        v = self.sv.L(lay, self.level)
        return math.nan if v is None else v


# ------------------------------------------------------------------------------------------------ the pipeline
@dataclasses.dataclass
class RunCtx:
    cfg: dict  # spec config
    fr: dict  # config.frozen (or the smoke override)
    mode: str  # full | smoke | dev | selftest
    wd: Path
    ops: Any
    sv: Solves
    seed: int
    prod: str  # production L_sub level
    band: tuple  # band levels, BAND order
    screen: str  # level for the shortlists and R_D (dev: lat0.5)
    n_draws: int
    window: tuple
    th: dict  # thermal job kwargs (E010 operating point and GridRule)


def tj_of(rx: RunCtx, lc: LayCtx, lays: dict[str, Any], P: dict) -> dict:
    """Hottest-die Tj (K) at the thermal reference's level 0 (E010's scikit-fem GridRule) at the reference's P_ref."""
    sv = rx.sv
    if "P" not in P:
        cj = sv.th_job(lc.reference, lc.name, "calibrate", {k: rx.th[k] for k in (
            "fem_rule", "h", "T_c", "target_K", "tol_K", "max_iters", "power_start_W")}, "P_ref")
        sv.run([cj], local=True)
        P["P"] = float(sv.rec(cj)["P_ref_W"])
    jobs = {k: sv.th_job(v, lc.name, "thermal", {"level": 0, "power_W": P["P"], "fem_rule": rx.th["fem_rule"],
                                                 "h": rx.th["h"], "T_c": rx.th["T_c"]}, f"Tj_{k}") for k, v in lays.items()}
    sv.run(list(jobs.values()), local=True)
    return {k: float(max(sv.rec(j)["tj"])) for k, j in jobs.items()}


def _draw_stages(rx: RunCtx, lc: LayCtx, st: Path, li: int, j: int, Dl) -> dict:
    """The L1 stages of one accepted draw D_j: the search, nulls (a), (b), (d), ablations (c), (e) (checkpointed)."""
    ops, sv, fr, name = rx.ops, rx.sv, rx.fr, lc.name
    lcfg, nl = fr["search"], fr["nulls"]
    sd = sub_seed(rx.seed, "search", li, j)
    d = {"D": Dl, "seed_search": sd, "seed_rs": sub_seed(rx.seed, "random_screen", li, j)}
    rec = Recorder(sv, rx.screen)
    log(f"{name}: draw {j} search")
    d["search"], d["search_short"] = cached(st / f"d{j}_search.pkl", lambda: (
        ops.search(lc, Dl, sd, lcfg, rec, f"lsub_{rx.screen}"), rec.lays))
    for role in ("seed", "widen", "compact"):
        log(f"{name}: draw {j} null {role}")
        d[role] = cached(st / f"d{j}_{role}.pkl", lambda role=role: ops.null(role, lc, Dl, int(nl["step_limit"])))
    rec2 = Recorder(sv, rx.screen)
    log(f"{name}: draw {j} random screen")
    d["random_screen"], d["rs_short"] = cached(st / f"d{j}_rs.pkl", lambda: (
        ops.random_screen(lc, Dl, d["seed_rs"], fr["ablation_c"], rec2,
                          f"lsub_{rx.screen}"), rec2.lays))
    log(f"{name}: draw {j} proxy alone")
    d["proxy_alone"] = cached(st / f"d{j}_pa.pkl", lambda: ops.proxy_alone(
        lc, Dl, int(fr["ablation_e"]["budget"]), int(fr["ablation_e"]["step_limit"])))
    if rx.mode == "dev" and j == 0:  # T0379 finding 1: the search under the other DC- reading, paired on D_0
        rec3 = Recorder(sv, rx.screen)
        d["search_dcm_alt"], d["alt_short"] = cached(st / f"d{j}_search_dcm_alt.pkl", lambda: (
            ops.search(lc, Dl, sd, lcfg, rec3, f"lsub_{rx.screen}", side=+1), rec3.lays))
    srch = d["search"]
    d["curve"] = improvement_curve(srch.trajectory, float(cached(st / f"d{j}_seed_l1.pkl", lambda: ops.l1(Dl))),
                                   srch.shortlist, int(lcfg["budget"]), srch.stats.get("last_improve_eval"),
                                   getattr(srch, "visited", None))
    return d


def run_layout(rx: RunCtx, name: str, li: int, counted: bool) -> dict:
    """One development layout through F2, P, D and S (module docstring) -> its record (rows, facts, reports)."""
    ops, sv, fr, st = rx.ops, rx.sv, rx.fr, rx.wd / "stages" / name
    lc = ops.load(name)
    sv.area[name] = lc.area_m2
    out: dict[str, Any] = {"layout": name, "counted": counted, "layout_index": li, "info": lc.info,
                           "movable_indices": list(ops.movable())}
    log(f"{name}: F2")
    out["f2"] = f2 = cached(st / "f2.pkl", lambda: ops.f2(lc, int(fr["f2_pool_n"]), rx.seed))
    in_dom_W = bool(f2["in_domain_reach"][0])
    pr = fr["proxy"]
    log(f"{name}: proxy descent")
    desc = cached(st / "proxy.pkl", lambda: ops.proxy(lc, int(pr["step_limit"])))
    out["proxy"] = {"steps": desc.steps, "kind": desc.kind, "l1_ratio": desc.l1_ratio,
                    "fingerprint": desc.layout.fingerprint()}
    sens = {}
    if rx.mode == "dev":  # sensitivity rows (T0379 item 2, founder decision 2026-11-16 items 2-3): not part of the rule
        for key, kw in (("threshold_free", {"min_gain": 0.0}), ("reach_false_probe", {"reach": False}),
                        ("dies_fixed", {"dies_fixed": True}), ("dcm_alt_reading", {"side": +1})):
            log(f"{name}: proxy sensitivity {key}")
            sens[key] = cached(st / f"proxy_{key}.pkl", lambda kw=kw: ops.proxy(lc, int(pr["step_limit"]), **kw))
        out["proxy_sensitivity"] = {k: {"steps": v.steps, "kind": v.kind, "l1_ratio": v.l1_ratio,
                                        "fingerprint": v.layout.fingerprint(),
                                        "same_as_frozen": v.layout.fingerprint() == desc.layout.fingerprint()}
                                    for k, v in sens.items()}
        sv.run([sv.em_job(v.layout, rx.screen, name, f"proxy_{k}", ops.vec(v.layout).tolist())
                for k, v in sens.items()])
    sv.run([sv.em_job(x, lv, name, f"{who}_band", ops.vec(x).tolist())
            for who, x in (("W", lc.W), ("descent", desc.layout)) for lv in rx.band])
    P: dict = {}
    if sv.L(lc.W, rx.prod) is not None and sv.L(desc.layout, rx.prod) is not None:
        ch = ops.choose(lc.W, desc, lambda x: sv.L(x, rx.prod))
        Wstar, provisional = ch.layout, False
        out["choice"] = {k: getattr(ch, k) for k in ("chosen", "l1_ratio", "l_sub_ratio", "l_sub_W", "l_sub_descent",
                                                     "steps", "terminal")}
    else:  # dev: the L2 values are on the burst VM; W* is provisionally the descent's end (T0376: lower at 0.5 mm)
        Wstar, provisional = desc.layout, True
        out["choice"] = {"chosen": "descent (provisional: L2 pending)", "l1_ratio": desc.l1_ratio}
    lays_tj = {"W": lc.W, "Wstar": Wstar} | ({"dies_fixed": sens["dies_fixed"].layout} if "dies_fixed" in sens else {})
    tj = tj_of(rx, lc, lays_tj, P)
    out["tj_K"], out["P_ref_W"] = tj, P.get("P")
    out["tj_fallback_due"] = due = tj_fallback_due(tj, fr["tj_fallback_K"])  # review item 9: evaluated in every mode
    if due and provisional:  # dev: choose_proxy needs L2, so the burst solves the dies-fixed descent's band (T0471)
        log(f"{name}: Tj(W*) - Tj(W) = {tj['Wstar'] - tj['W']:.2f} K > 2 K on the provisional W*: dies-fixed band jobs")
        dfd = cached(st / "proxy_diesfixed.pkl", lambda: ops.proxy(lc, int(pr["step_limit"]), dies_fixed=True))
        sv.run([sv.em_job(x, lv, name, "descent_diesfixed_band", ops.vec(x).tolist())
                for x in (dfd.layout,) for lv in rx.band])
        out["tj_fallback_pending_l2"] = {"dies_fixed_fingerprint": dfd.layout.fingerprint(), "steps": dfd.steps,
                                         "l1_ratio": dfd.l1_ratio}
    if due and not provisional:  # O008 scope_in: the die-fixed proxy
        log(f"{name}: Tj(W*) - Tj(W) = {tj['Wstar'] - tj['W']:.2f} K > 2 K: dies-fixed proxy")
        dfd = cached(st / "proxy_diesfixed.pkl", lambda: ops.proxy(lc, int(pr["step_limit"]), dies_fixed=True))
        sv.run([sv.em_job(x, lv, name, "descent_diesfixed_band", ops.vec(x).tolist())
                for x in (dfd.layout,) for lv in rx.band])
        ch = ops.choose(lc.W, dfd, lambda x: sv.L(x, rx.prod))
        Wstar = ch.layout
        out["choice_fallback"] = {"chosen": ch.chosen, "l1_ratio": ch.l1_ratio, "l_sub_ratio": ch.l_sub_ratio}
        out["tj_K"] |= {"Wstar_fallback": tj_of(rx, lc, {"Wstar": Wstar}, P)["Wstar"]}
    out["tj_fallback_fired"] = "choice_fallback" in out
    out["Wstar"] = {"fingerprint": Wstar.fingerprint(), "drc_clean": ops.drc_clean(lc, Wstar),
                    "in_domain_reach": bool(ops.in_domain(lc, Wstar)[0]), "provisional": provisional,
                    "params": ops.vec(Wstar).tolist()}
    w_star_vec = ops.vec(Wstar)
    L_ws = sv.L(Wstar, rx.prod)
    L_ws_screen = sv.L(Wstar, rx.screen)

    # ---- D: degradations in waves (deterministic replay; each wave solves the attempts the previous one asked for)
    dg = fr["degradation"]
    dseed = sub_seed(rx.seed, "degrade")
    defects: list[str] = []
    recs = None
    prov_fp: set[str] = set()  # attempts whose R_D is the in-window placeholder (record mode: L2 pending)
    for wave in range(int(dg["redraw_limit"]) + 2):
        pend: list = []
        prov_fp.clear()

        def r_d(Dl, pend=pend):
            if not ops.in_domain(lc, Dl)[0]:  # T0414: a defect of the family, out of window, never scored
                defects.append(Dl.fingerprint())
                return math.inf
            v, base = sv.L(Dl, rx.screen), L_ws_screen
            if v is None or base is None:
                pend.append(Dl)
                prov_fp.add(Dl.fingerprint())
                return 0.5 * (rx.window[0] + rx.window[1])  # control flow only: the attempt is provisionally kept
            return v / base

        log(f"{name}: degradation wave {wave}")
        recs = ops.degrade(lc, Wstar, dseed, li, rx.n_draws, r_d, int(dg["redraw_limit"]),
                           {k: dg[k] for k in ("target_ratio", "max_proposals", "k_lo", "k_hi", "mags_mm")}, rx.window)
        if not pend or sv.mode == "record":
            sv.run([sv.em_job(x, rx.screen, name, "D_R_D", ops.vec(x).tolist()) for x in pend])
            break
        sv.run([sv.em_job(x, rx.screen, name, "D_R_D", ops.vec(x).tolist()) for x in pend])
    acc = [r for r in recs if r.accepted]
    # review item 4: a placeholder R_D (record mode, L2 pending) is recorded as None with r_d_provisional true, never as
    # a number; the dev L2 analysis (--dev-rows) fills the measured R_D from the burst's solve of D_j
    prov = {r.draw: (r.layout is not None and r.layout.fingerprint() in prov_fp) for r in recs}
    rd_meas = {r.draw: (None if prov[r.draw] else r.r_d) for r in recs}
    out["draws"] = [{"draw": r.draw, "accepted": r.accepted, "attempts": r.attempts, "r_d": rd_meas[r.draw],
                     "r_d_provisional": prov[r.draw],
                     "attempt_log": [dict(a, r_d=None, r_d_provisional=True) if prov[r.draw] and a.get("in_window")
                                     else a for a in r.attempt_log]} for r in recs]
    out["degradation_defects_out_of_domain"] = sorted(set(defects))
    l1s = [a["l1_ratio"] for r in recs for a in r.attempt_log]
    stops = [a["stop"] for r in recs for a in r.attempt_log]
    out["degradation_report"] = {
        "n_attempts": len(l1s), "l1_stop_ratio": {"min": min(l1s), "median": float(np.median(l1s)), "max": max(l1s)},
        "rate_reached_l1_target": float(np.mean([s == "target" for s in stops])),
        "redraws": sum(r.attempts - 1 for r in recs), "excluded_draws": [r.draw for r in recs if not r.accepted],
        "attempts_missing_l1_target_with_l2_call": sum(1 for s in stops if s != "target")}
    if len(acc) < rx.n_draws:
        out["F6_excluded"] = {"accepted": len(acc), "needed": rx.n_draws,
                              "achieved_r_d": [a["r_d"] for r in recs for a in r.attempt_log]}
        counted = out["counted"] = False

    # ---- S: per draw, the search, the nulls and the ablations (L1 stages)
    res: dict[int, dict] = {}
    for r in acc:
        res[r.draw] = _draw_stages(rx, lc, st, li, r.draw, r.layout)
        _manifest_hook(rx)
    # L2: shortlists and end points
    jobs = []
    for j, d in res.items():
        for key, short in shortlists(d):  # every member under its own shortlist's purpose and L1 rank (T0430/T0431)
            jobs += [sv.em_job(d[key][e["fingerprint"]], rx.screen, name, f"{key}_d{j}",
                               ops.vec(d[key][e["fingerprint"]]).tolist(), rank=int(e.get("rank", r)))
                     for r, e in enumerate(short)]
        jobs += [sv.em_job(d[k].layout, rx.screen, name, f"{k}_d{j}", ops.vec(d[k].layout).tolist())
                 for k in ("widen", "compact", "proxy_alone")]
    sv.run(jobs)
    best: dict[int, dict] = {}
    for j, d in res.items():
        b = best[j] = {"seed": d["seed"].layout, "widen": d["widen"].layout, "compact": d["compact"].layout,
                       "proxy_alone": d["proxy_alone"].layout}
        for role, short, lays in (("search", d["search"].shortlist, d["search_short"]),
                                  ("random_screen", d["random_screen"].stats["shortlist"], d["rs_short"])):
            ls = [sv.L(lays[e["fingerprint"]], rx.screen) for e in short]
            b[role] = None if any(v is None for v in ls) else lays[short[ops.search_select(short, ls)]["fingerprint"]]
    sv.run([sv.em_job(x, lv, name, f"{role}_d{j}_band", ops.vec(x).tolist())
            for j, b in best.items() for role, x in b.items() if x is not None for lv in rx.band])
    if rx.mode != "dev":
        sb = {j: b["search"] for j, b in best.items() if b["search"] is not None}
        out["tj_K"] |= {f"best_{j}": v for j, v in tj_of(rx, lc, {str(j): x for j, x in sb.items()}, P).items()}
    # ---- rows
    rows, reps = [], []
    for j, d in res.items():
        for role in N7.ROLES:
            x = best[j][role]
            obj = d[role]
            kind, capped, raw = terminal(role, obj)
            L, Lb = (None, None) if x is None else (sv.L(x, rx.prod), [sv.L(x, lv) for lv in rx.band])
            Wb = [sv.L(Wstar, lv) for lv in rx.band]
            ok = L is not None and L_ws is not None and None not in Lb and None not in Wb
            s = L / L_ws - 1.0 if ok else None
            b = 2.0 * MX.ratio_band_estimate(Lb, Wb) if ok else None
            v = ops.vec(x) if x is not None else None
            ch_d, mh_d = dist(v, ops.vec(d["D"]), ops.movable()) if v is not None else (None, None)  # review item 5
            ch_w, mh_w = dist(v, w_star_vec, ops.movable()) if v is not None else (None, None)
            row = {"layout": name, "counted": counted, "draw": int(j), "role": role, "s": s, "b": b, "capped": capped,
                   "terminal_kind": kind, "in_domain_W": in_dom_W, "reach_outside": 1.0 - float(in_dom_W),
                   "terminal_raw": raw, "L_sub_H": L, "L_sub_Wstar_H": L_ws, "e_R": None if b is None else b / 2,
                   "R_D": rd_meas[j], "R_D_provisional": prov[j], "fingerprint": None if x is None else x.fingerprint(),
                   "changed_from_D": ch_d, "manhattan_from_D_mm": mh_d, "changed_from_Wstar": ch_w,
                   "manhattan_from_Wstar_mm": mh_w, "l_sub_level": rx.prod, "band_levels": list(rx.band),
                   "movable_indices": list(ops.movable())}
            if role == "search":
                stt = obj.stats
                short = obj.shortlist
                ls = [sv.L(d["search_short"][e["fingerprint"]], rx.screen) for e in short]
                row |= {"steps": stt["steps"], "moves": stt["moves"], "l1_evals": stt["l1_evals"],
                        "stopped_at_budget": stt["stopped_at_budget"], "seed_in_domain": stt["seed_in_domain"],
                        "improving_last10": stt["improving_last10"], "cfg_hash": stt["cfg_hash"],
                        "last_improve_eval": stt.get("last_improve_eval"), **d["curve"],
                        "spearman_l1_lsub": (ops.spearman([e["l1"] for e in short], ls) if None not in ls else None),
                        "l2_l1_min": (min(a / e["l1"] for a, e in zip(ls, short, strict=True)) if None not in ls else None),
                        "l2_l1_max": (max(a / e["l1"] for a, e in zip(ls, short, strict=True)) if None not in ls else None)}
            elif role in ("widen", "compact"):
                nst = getattr(obj, "stats", None) or {}  # T0437 (nulls.py): seed_in_domain, n_neighbours_step0
                row |= {"steps": obj.steps, "seed_in_domain": nst.get("seed_in_domain"),
                        "n_neighbours_step0": nst.get("n_neighbours_step0")}
            elif role == "proxy_alone":
                row |= {"steps": obj.steps}
            elif role == "random_screen":
                row |= {"l1_evals": obj.stats["l1_evals"], "n_draws": obj.stats["n_draws"]}
            rows.append(row)
        if "search_dcm_alt" in d:
            a, f = d["search_dcm_alt"], d["search"]
            reps.append({"draw": j, "lowest_l1_frozen": f.shortlist[0]["l1"], "lowest_l1_alt": a.shortlist[0]["l1"],
                         "shortlist_same": [e["fingerprint"] for e in a.shortlist] == [e["fingerprint"] for e in
                                                                                         f.shortlist]})
    out["rows"], out["dcm_alt_search"] = rows, reps
    out["null_steps"] = {role: [{"draw": j, "steps": d[role].steps, "terminal": d[role].terminal,
                                 "seed_in_domain": (getattr(d[role], "stats", None) or {}).get("seed_in_domain"),
                                 "n_neighbours_step0": (getattr(d[role], "stats", None) or {}).get("n_neighbours_step0")}
                                for j, d in res.items()]
                         for role in ("widen", "compact")}
    # T0425: a null run whose D_j is outside in_domain(reach=True) is never scored; T0379's family cannot produce one
    bad_null = [(role, e["draw"]) for role, es in out["null_steps"].items() for e in es if e["seed_in_domain"] is False]
    if bad_null:
        raise RuntimeError(f"{name}: null runs seeded outside in_domain(reach=True): {bad_null}")
    out["search_seed_in_domain"] = {j: bool(d["search"].stats["seed_in_domain"]) for j, d in res.items()}
    out["streams"] = {"degrade_seed": dseed, "search": {j: d["seed_search"] for j, d in res.items()},
                      "random_screen": {j: d["seed_rs"] for j, d in res.items()},
                      "degrade_entropy": [a.get("entropy") for r in recs for a in r.attempt_log]}
    cv = {k: [d["curve"][k] for d in res.values()] for k in ("gain_share_last10", "gain_share_last25")}
    out["search_improvement"] = {
        "budget_l1_evals": int(fr["search"]["budget"]),
        "per_draw": {j: d["curve"] | {"last_improve_eval": d["search"].stats.get("last_improve_eval")}
                     for j, d in res.items()},
        "median_gain_share_last10": float(np.median(cv["gain_share_last10"])) if res else None,
        "median_gain_share_last25": float(np.median(cv["gain_share_last25"])) if res else None,
        "draws_still_improving_last10": sum(bool(d["search"].stats.get("improving_last10")) for d in res.values()),
        "rule": improvement_curve.__doc__.split("\n")[0]}
    return out


def shortlists(d: dict) -> list[tuple[str, list[dict]]]:
    """(key, entries in L1-rank order) of the shortlists of one draw's stages that exist."""
    get = {"search_short": lambda: d["search"].shortlist, "rs_short": lambda: d["random_screen"].stats["shortlist"],
           "alt_short": lambda: d["search_dcm_alt"].shortlist}
    return [(k, list(f())) for k, f in get.items() if k in d]


def improvement_curve(traj: list[dict], seed_l1: float, short: list[dict], budget: int, last_improve: int | None,
                      visited: list | None = None) -> dict:
    """Share of the search's final L1 gain made in the last 10 % and 25 % of its L1-evaluation budget (founder 2026-11-17
    item 4).  gain(n) = L1(D_j) - best(n), best(n) = the lowest L1 among the first n evaluations; final = the lowest L1 in
    the shortlist; share_x = (best(n_x) - final) / (L1(D_j) - final) at n_x = (1 - x) budget (the score is L1,
    local.default_score).  Exact when the last improvement (stats last_improve_eval) is at or before n_x (share 0), or
    when a shortlist member was evaluated by n_x: the shortlist holds the K lowest-L1 visited layouts, so best(n_x) is
    the lowest of those members (``visited`` is in evaluation order, entry i = evaluation i + 1).  Otherwise best(n_x)
    lies between the shortlist's highest L1 and the running minimum of the trajectory's scores (recorded at the end of
    each neighbourhood scan); share_x is then that upper end, share_x_lo the lower, exact False."""
    l1s = [float(e["l1"]) for e in short]
    final = min(l1s)
    G = seed_l1 - final
    order = {fp: i + 1 for i, (fp, _) in enumerate(visited or [])}
    out: dict[str, Any] = {}
    for x, key in ((0.10, "gain_share_last10"), (0.25, "gain_share_last25")):
        n_x = (1.0 - x) * budget
        if not (G > 0) or (last_improve is not None and last_improve <= n_x):
            out[key] = out[f"{key}_lo"] = 0.0
            out[f"{key}_exact"] = True
            continue
        mem = [float(e["l1"]) for e in short if order.get(e["fingerprint"], math.inf) <= n_x]
        if mem:
            hi = lo = min(mem)
        else:
            hi = min([seed_l1] + [float(t["score"]) for t in traj if t["n_l1"] <= n_x])
            lo = max(l1s) if order else final
        f = lambda b: float(min(1.0, max(0.0, (b - final) / G)))  # noqa: E731
        out[key], out[f"{key}_lo"], out[f"{key}_exact"] = f(hi), f(min(lo, hi)), bool(mem)
    out["l1_gain_rel"] = float(G / seed_l1) if seed_l1 > 0 else math.nan
    return out


_HOOK: dict = {}


def _manifest_hook(rx: RunCtx) -> None:
    if rx.mode == "dev" and "fn" in _HOOK:
        _HOOK["fn"]()


# ------------------------------------------------------------------------------------------------ metrics, checks
def metric_values(rows: list[dict], n_draws: int) -> dict:
    """The four gated metrics from n7 (e011_metrics) and from mfos.metrics (the founder's port), with intervals."""
    out = {}
    cnt = [r for r in rows if r["counted"]]
    s_rows = [r for r in cnt if r["role"] == "search"]
    if not cnt:
        return {k: {"value": math.nan, "port": math.nan, "ci": None} for k in METRICS}
    v = {"control_layout_pass_min": N7.control_layout_pass_min(rows, n_draws=n_draws),
         "reach_outside_max": N7.reach_outside_max(rows, n_draws=n_draws),
         "null_beaten_min": N7.null_beaten_min(rows, n_draws=n_draws),
         "control_shortfall_median_max": N7.control_shortfall_median_max(rows, n_draws=n_draws)}
    port = {"control_layout_pass_min": MX.control_layout_pass_min(s_rows, n_draws=n_draws),
            "reach_outside_max": MX.max_col([r["reach_outside"] for r in rows]),
            "null_beaten_min": MX.null_beaten_min(cnt, nulls=list(N7.GATING_NULLS), n_draws=n_draws),
            "control_shortfall_median_max": MX.control_shortfall_median_max(s_rows, n_draws=n_draws)}
    iv = N7.layout_pass_intervals(rows, n_draws=n_draws)
    ci = {"control_layout_pass_min": (min(x[1] for x in iv.values()), min(x[2] for x in iv.values())),
          "reach_outside_max": (v["reach_outside_max"],) * 2, "null_beaten_min": (v["null_beaten_min"],) * 2}
    med = []
    for lay in sorted({r["layout"] for r in s_rows}):  # order-statistic CI of each median: (x(1), x(n)), >= 99.2 % at n=8
        s = sorted(N7._shortfall(r["s"], "") for r in s_rows if r["layout"] == lay)
        med.append((s[0], s[-1]))
    ci["control_shortfall_median_max"] = (max(a for a, _ in med), max(b for _, b in med))
    for k in METRICS:
        out[k] = {"value": float(v[k]), "port": float(port[k]), "ci": ci[k]}
    return out


def recompute_check(spec: dict, rows: list[dict], met: dict, n_draws: int) -> list[str]:
    """Recompute every spec recompute entry as mfos.evaluate does (RecomputeSpec, _where, metric_value)."""
    from mfos import evaluate as EV
    from mfos import models as MM
    bad = []
    for rc in spec.get("recompute", []):
        r = MM.RecomputeSpec.model_validate(rc | {"params": {**rc.get("params", {}), **(
            {"n_draws": n_draws} if "n_draws" in rc.get("params", {}) else {})}})
        try:
            mv = EV.metric_value(r, EV._where(rows, r.where), r.pred).value
        except Exception as e:  # noqa: BLE001 - a failed recompute is a failed check
            bad.append(f"{r.metric}: {type(e).__name__}: {e}")
            continue
        if not (mv == met[r.metric]["value"] or abs(mv - met[r.metric]["value"]) <= r.abs_tol + r.rel_tol * abs(mv)):
            bad.append(f"{r.metric}: recomputed {mv} != runner {met[r.metric]['value']}")
    return bad


def artifacts_resolve(run_dir: Path, artifacts: list) -> list[str]:
    """Every registered artifact resolves exactly as tools/mfos/mfos/evaluate.py resolves it: <run_dir>/<name> with the
    recorded sha256 (the content store of the VM is not fetched, T0349 finding 2)."""
    from mfos.store import file_sha256
    bad = []
    for a in artifacts:
        p = Path(run_dir) / a.name
        if not p.exists():
            bad.append(f"{a.name} missing from the run directory")
        elif file_sha256(p) != a.sha256:
            bad.append(f"{a.name} sha256 changed")
    return bad


GATED = ("F1a_seed_null_fails_A1", "F2_W_rebuild", "F2_in_domain_reach", "F2_legacy_outside_2R", "F2_symdiff_reported",
         "F2_coordinate_range_attached_form_2R", "F2_l1_lower_tail_reported", "F6_two_counted_layouts", "Wstar_drc_clean",
         "draws_seed_in_domain", "seed_streams_distinct", "metrics_agree", "recompute_agrees", "l2_converged",
         "band_bound", "F5_frozen_and_code")


def sanity(recs: list[dict], rows: list[dict], met: dict, spec: dict, sv: Solves | None, n_draws: int,
           smoke: bool = False) -> list[dict]:
    """Every declared sanity check: (name, passed, value, threshold, detail)."""
    ck = []

    def add(name, passed, value=None, threshold=None, detail=""):
        ck.append({"name": name, "passed": bool(passed), "value": value, "threshold": threshold, "detail": str(detail)[:900]})

    cnt = [r for r in recs if r["counted"]]
    try:
        ok, v = N7.seed_null_check(rows, n_draws=n_draws)
    except ValueError as e:
        ok, v = False, math.nan
        add("F1a_seed_null_fails_A1", False, detail=str(e))
    else:
        add("F1a_seed_null_fails_A1", ok, v, N7.MIN_PASS / N7.N_DRAWS, "A1 of null (a) must be below 7/8")
    f2 = {r["layout"]: r["f2"] for r in recs}
    add("F2_W_rebuild", all(not f.get("rebuild_drc") and f.get("rebuild_fingerprint_equal") for f in f2.values()),
        detail={k: (f.get("rebuild_drc"), f.get("rebuild_fingerprint_equal"), f.get("rebuild_error")) for k, f in f2.items()})
    add("F2_in_domain_reach", all(f["in_domain_reach"][0] for f in f2.values()),
        detail={k: f["in_domain_reach"] for k, f in f2.items()})
    r2 = f2.get("2D_Case_2R")
    add("F2_legacy_outside_2R", r2 is not None and not r2["in_domain_legacy"][0],
        detail=None if r2 is None else r2["in_domain_legacy"])
    add("F2_symdiff_reported", all(math.isfinite(f["symdiff_total_mm2"]) for f in f2.values()),
        detail={k: round(f["symdiff_total_mm2"], 4) for k, f in f2.items()})
    add("F2_coordinate_range_attached_form_2R", r2 is not None and bool(r2["pool_legacy"].get("W_outside_range"))
        and bool(r2["slots_overlapping_column"]),
        detail=None if r2 is None else {"outside": r2["pool_legacy"].get("W_outside_range"),
                                        "overlapping": len(r2["slots_overlapping_column"])})
    add("F2_l1_lower_tail_reported", all(f[f"pool_{k}"]["n"] >= 1 and math.isfinite(f[f"pool_{k}"]["min_excess"])
                                         for f in f2.values() for k in ("legacy", "reach")),
        detail={k: {q: f[f"pool_{q}"]["min_excess"] for q in ("legacy", "reach")} for k, f in f2.items()})
    add("F6_two_counted_layouts", len(cnt) >= (1 if smoke else 2), len(cnt), 2,
        {r["layout"]: r.get("F6_excluded") for r in recs})
    add("Wstar_drc_clean", all(r["Wstar"]["drc_clean"] and r["Wstar"]["in_domain_reach"] for r in recs),
        detail={r["layout"]: r["Wstar"] for r in recs})
    add("draws_seed_in_domain", all(all(r["search_seed_in_domain"].values()) for r in recs),
        detail={r["layout"]: r["search_seed_in_domain"] for r in recs})
    ok, info = streams_distinct(recs)
    add("seed_streams_distinct", ok, info["n_streams"], detail=info)
    add("metrics_agree", all(m["value"] == m["port"] or (math.isnan(m["value"]) and math.isnan(m["port"]))
                             or abs(m["value"] - m["port"]) <= 1e-12 for m in met.values()),
        detail={k: (m["value"], m["port"]) for k, m in met.items()})
    bad = recompute_check(spec, rows, met, n_draws) if cnt else ["no counted layout"]
    add("recompute_agrees", not bad, detail=bad)
    if sv is not None:
        ok, n, badl = sv.em_ok()
        add("l2_converged", ok and n > 0, n, detail=badl[:10])
    else:
        add("l2_converged", False, detail="no solves")
    bb = spec["config"]["frozen"]["band_bound"]
    per = {}
    for r in cnt:
        bs = [x["b"] for x in r["rows"] if x["role"] == "search" and x["b"] is not None]
        per[r["layout"]] = (float(np.median(bs)) if bs else math.inf, max(bs) if bs else math.inf)
    add("band_bound", bool(per) and all(m <= bb["median_max"] and x <= bb["max_max"] for m, x in per.values()),
        detail={k: {"median_b": v[0], "max_b": v[1]} for k, v in per.items()})
    fz = freeze_report(spec["config"])
    add("F5_frozen_and_code", fz["ok"] or smoke, detail=fz)
    return ck


def streams_distinct(recs: list[dict]) -> tuple[bool, dict]:
    """The streams this run used (T0432: the run's own seeds, not a constant): the integer sub-seeds of every purpose,
    layout and draw are pairwise distinct; every degradation attempt's SeedSequence state is distinct from every other
    and from the first streams of every search (local.py: SeedSequence([seed, 1, it]), [seed, 2, n]) and random screen
    (search.candidate_stream: SeedSequence([seed, k]) per chunk k); the runner's domain tags are nonzero and distinct.  Reported: whether control.py's entropy lists
    start with a domain tag (first word not the degradation seed itself; T0414 item 4, a source fix in control.py)."""
    ints, states, tagged, n_ent = [], [], [], 0
    st = lambda ent: tuple(int(x) for x in np.random.SeedSequence(ent).generate_state(4))  # noqa: E731
    for r in recs:
        S = r.get("streams") or {}
        if "degrade_seed" not in S:
            continue
        if all(v != S["degrade_seed"] for k, _, v in ints if k == "degrade"):  # one per run; li enters the entropy
            ints += [("degrade", r["layout"], S["degrade_seed"])]
        for k in ("search", "random_screen"):
            ints += [(k, r["layout"], int(v)) for v in S[k].values()]
        for v in S["search"].values():
            states += [st([int(v), 1, 1]), st([int(v), 2, 0])]
        for v in S["random_screen"].values():
            states += [st([int(v), 0])]
        for ent in S["degrade_entropy"]:
            if ent is None:
                continue
            n_ent += 1
            states.append(st([int(x) for x in ent]))
            tagged.append(int(ent[0]) != int(S["degrade_seed"]))
    vals = [v for _, _, v in ints]
    ok = (len(vals) > 0 and len(set(vals)) == len(vals) and n_ent > 0 and len(set(states)) == len(states)
          and len(set(TAGS.values())) == len(TAGS) and all(t != 0 for t in TAGS.values()))
    return ok, {"n_streams": len(vals) + n_ent, "n_int_seeds": len(vals), "n_distinct_int": len(set(vals)),
                "n_degrade_entropies": n_ent, "n_states": len(states), "n_distinct_states": len(set(states)),
                "control_entropy_domain_tagged": (all(tagged) if tagged else None)}


def freeze_report(cfg: dict) -> dict:
    """F5: the frozen block's hash and the code_under_test hashes against the values the spec records."""
    fr = cfg["frozen"]
    got = canon_sha(fr)
    code = {p: sha256_file(p) for p in CODE}
    want = cfg.get("code_sha256", {})
    mism = [p for p in CODE if want.get(p) != code[p]]
    try:
        lc_hash = _mods().L.LocalConfig(**fr["search"]).hash()
    except Exception as e:  # noqa: BLE001
        lc_hash = f"error {e}"
    return {"ok": got == cfg.get("frozen_sha256") and not mism and lc_hash == fr["search_cfg_hash"],
            "frozen_sha256": got, "recorded": cfg.get("frozen_sha256"), "code_mismatch": mism, "code_sha256": code,
            "search_cfg_hash": lc_hash, "search_cfg_hash_recorded": fr.get("search_cfg_hash")}


def verdict(met: dict, checks: list[dict]) -> str:
    if any(not c["passed"] for c in checks if c["name"] in GATED):
        return "INVALID"
    pa, fa = objective_criteria()
    return N7.verdict({f"{EID}.{k}": m["value"] for k, m in met.items()}, pa, fa)


# ------------------------------------------------------------------------------------------------ run setup
def thermal_kw(c10: dict) -> dict:
    op = c10["operating_point"]
    return {"fem_rule": c10["fem_rule"], "h": op["h_W_m2K"], "T_c": op["coolant_K"], "target_K": op["target_rise_K"],
            "tol_K": op["calibration_tol_K"], "max_iters": op["calibration_max_iters"],
            "power_start_W": op["power_start_W"]}


def make_ctx(spec: dict, mode: str, wd: Path, seed: int, ops=None, fake=None, mem_cap=5.0, vcpus=4) -> RunCtx:
    cfg = spec["config"]
    check_stamp(wd, code_stamp(spec))  # before Solves creates the directories
    fr = json.loads(json.dumps(cfg["frozen"]))
    c10 = cfg10()
    cm = c10["compute"]["cost_model"]
    threads = 1 if fake else E.thread_count(c10)[0]
    vm = c10["compute"]["vm"]
    if mode == "full":
        mem_cap, vcpus = vm["memory_fraction"] * (E._mem_total_GB() or vm["ram_GB"]), int(vm["vcpus"])  # never cpu_count
    sched = E.Scheduler(mem_cap, vcpus, threads, fake=fake, solo_cap_GB=E.solo_cap_from_env(vm) if mode == "full" else None,
                        defer_big=mode == "full")
    sv = Solves(wd, cm, sched, threads, "record" if mode == "dev" else "solve", freq_hz=float(cfg["levels"]["freq_hz"]))
    lv = cfg["levels"]
    prod, band, screen = lv["production"], tuple(lv["band"]), lv["production"]
    n_draws, window = int(fr["n_draws"]), tuple(fr["degradation"]["window"])
    if mode == "smoke":
        sm = cfg["smoke"]
        for k, v in sm["frozen_overrides"].items():
            fr[k] = fr[k] | v if isinstance(v, dict) else v
        prod = screen = sm["level"]
        band, n_draws, window = (sm["level"],) * 5, int(sm["n_draws"]), tuple(sm["window"])
    if mode == "dev":
        screen = cfg["dev"]["screen_level"]
    return RunCtx(cfg, fr, mode, wd, ops or RealOps(), sv, int(seed), prod, band, screen, n_draws, window,
                  thermal_kw(c10))


def run_all(rx: RunCtx, layouts: list[tuple[str, bool]]) -> list[dict]:
    idx = rx.cfg["layout_index"]
    return [run_layout(rx, name, int(idx[name]), counted) for name, counted in layouts]


def finish(er, rx: RunCtx, recs: list[dict], spec: dict, smoke: bool = False) -> tuple[str, dict, list[dict]]:
    rows = [r for rec in recs for r in rec["rows"]]
    met = metric_values(rows, rx.n_draws)
    rows_ref = er.rows(rows) if rows else None
    checks = sanity(recs, rows, met, spec, rx.sv, rx.n_draws, smoke)
    for k, m in met.items():
        er.metric(k, m["value"], ci=m["ci"], n=sum(1 for r in rows if r["counted"] and r["role"] == "search"))
    for c in checks:
        er.sanity(c["name"], c["passed"], value=c["value"], threshold=c["threshold"], detail=c["detail"])
    v = verdict(met, checks)
    report = {"verdict_preview": v, "metrics": met, "checks": checks, "layouts": [{k: x for k, x in r.items() if k != "rows"}
                                                                                for r in recs],
              "reported": reported(rows, rx.n_draws)}
    rp = er.run_dir / "evaluation_report.json"
    rp.write_text(json.dumps(report, indent=1, default=_js))
    arts = [er.artifact(rp.name, rp)]
    bad = artifacts_resolve(er.run_dir, ([rows_ref] if rows_ref else []) + arts)
    er.sanity("artifacts_resolve", not bad, detail="; ".join(bad))
    checks.append({"name": "artifacts_resolve", "passed": not bad, "detail": bad})
    return v, met, checks


def _js(o):
    if isinstance(o, (np.floating, np.integer, np.bool_)):
        return o.item()
    if isinstance(o, (tuple, set)):
        return list(o)
    return str(o)


def reported(rows: list[dict], n_draws: int) -> dict:
    """Reported, not gated (n7's helpers): conservative A1, draws within their band of the line, pooled bound, per null
    the resolved/paired counts, ablations (c) and (e) with their A1 and A3 values."""
    if not any(r["counted"] for r in rows):
        return {}
    out = {"A1_conservative": N7.control_layout_pass_min_conservative(rows, n_draws=n_draws),
           "within_band_of_line": N7.unresolved_counts(rows, n_draws=n_draws), "pooled_lower_bound": N7.pooled_pass_lower_bound(
               rows, n_draws=n_draws), "null_table": {f"{a}|{b}": v for (a, b), v in N7.null_beaten_table(
                   rows, n_draws=n_draws).items()}}
    for abl in ("random_screen", "proxy_alone"):
        rr = [dict(r, role="search") if r["role"] == abl else dict(r, role="_x") if r["role"] == "search" else r
              for r in rows]
        rr = [r for r in rr if r["role"] != "_x"]
        try:
            out[f"ablation_{abl}"] = {"A1": N7.control_layout_pass_min(rr, n_draws=n_draws),
                                      "A3": N7.null_beaten_min(rr, n_draws=n_draws),
                                      "K1": N7.control_shortfall_median_max(rr, n_draws=n_draws)}
        except ValueError as e:
            out[f"ablation_{abl}"] = {"error": str(e)}
    return out


# ------------------------------------------------------------------------------------------------ selftest
FAKE_L: dict[str, float] = {}
FAKE_VEC: dict[tuple, str] = {}  # parameter vector -> fingerprint (FakeOps.rebuild)
FAKE_UNCONVERGED: set[str] = set()
FAKE_TJ = {"delta_K": 0.5}  # hottest-die Tj of W* above W's in the fake thermal results


@dataclasses.dataclass
class FakeLay:
    fp: str
    vec: tuple

    def fingerprint(self) -> str:
        return self.fp


def _fl(fp: str, L: float, vec=None) -> FakeLay:
    """A fake layout with its L and a parameter vector unique to its fingerprint (so a rebuild from params is real)."""
    FAKE_L[fp] = L
    if vec is None:
        hb = hashlib.sha256(fp.encode()).digest()
        vec = [0.0] * 4 + [0.5 * (b % 16) for b in hb[:36]] + [0.0] * 8
    FAKE_VEC[tuple(vec)] = fp
    return FakeLay(fp, tuple(vec))


LEVEL_EPS = {"lat0.25": 0.0, "lat0.5": 0.0005, "thk_c": -0.0004, "thk_f": 0.0003, "fil_f": 0.0002}


def fake_job(j: dict) -> dict:
    """Fake E010 child results: L(level) = L x (1 + eps_level x h(fp)), h in [0, 1) from the fingerprint, so bands are
    small but nonzero; thermal: P_ref 50 W, hottest die 400 K (W* +0.5 K)."""
    if j["type"] == "calibrate":
        return {"P_ref_W": 50.0, "rise_K": 60.0}
    if j["type"] == "thermal":
        return {"tj": [400.0 + (FAKE_TJ["delta_K"] if "star" in j["fp"] or "Wd" in j["fp"] else 0.0)]}
    h = int(hashlib.sha256(j["fp"].encode()).hexdigest()[:6], 16) / 16**6
    if j["fp"] in FAKE_UNCONVERGED:
        return {"L_H": FAKE_L[j["fp"]], "peak_GB": 0.1}  # no convergence record: E010's predicate must fail it
    return {"L_H": FAKE_L[j["fp"]] * (1.0 + LEVEL_EPS[j["level"]] * h), "gmres_flags": [0],
            "solver_tol_rel_L_max": 1e-6, "peak_GB": 0.1}


class FakeOps:
    """Planted outcomes per layout (scenario): s of each role at the production level; the stages return FakeLays."""
    fake = True

    def __init__(self, plan: dict[str, dict]):
        self.plan = plan
        self.LW = 20e-9

    def movable(self):
        return tuple(range(4, 40))

    def l1(self, lay):
        return 2.0  # the seed's L1 in the planted improvement curve (FakeOps.search)

    def rebuild(self, lc, params):
        return FakeLay(FAKE_VEC[tuple(float(x) for x in params)], tuple(float(x) for x in params))

    def vec(self, lay):
        return np.asarray(lay.vec, float)

    def drc_clean(self, lc, lay):
        return True

    def in_domain(self, lc, lay, reach=True):
        return (True, "")

    def load(self, name):
        return LayCtx(name, None, _fl(f"{name}_ref", self.LW), _fl(f"{name}_W", self.LW), 0.003, {})

    def f2(self, lc, pool_n, seed):
        leg = lc.name != "2D_Case_2R"
        return {"rebuild_drc": [], "rebuild_fingerprint_equal": True, "in_domain_reach": [True, ""],
                "in_domain_legacy": [leg, "" if leg else "col_PHASE_outer_edge"], "symdiff_total_mm2": 0.5,
                "slots_overlapping_column": [] if leg else [{"slot": 0}],
                "pool_legacy": {"n": 5, "min_excess": 0.03, "W_outside_range": [] if leg else ["slot0_u0"]},
                "pool_reach": {"n": 5, "min_excess": 0.01}}

    def proxy(self, lc, step_limit, **kw):
        return SimpleNamespace(layout=_fl(f"{lc.name}_Wd_star", self.LW * 0.9), l1_ratio=0.9, steps=10,
                               kind="local_optimum")

    def choose(self, W, desc, l_sub):
        return _mods().C.choose_proxy(W, desc, l_sub)

    def degrade(self, lc, Wstar, seed, li, n, r_d, redraw_limit, dcfg, window):
        out = []
        p = self.plan[lc.name]
        for j in range(n):
            log_, rec = [], SimpleNamespace(draw=j, layout=None, accepted=False, attempts=0, r_d=None, attempt_log=None)
            for a in range(redraw_limit + 1):
                lay = _fl(f"{lc.name}_D{j}_a{a}", FAKE_L[Wstar.fp] * p.get("R_D", 1.40))
                r = r_d(lay)
                ok = window[0] <= r <= window[1]
                log_.append({"attempt": a, "entropy": [int(seed), int(li), j, a], "l1_ratio": 1.39, "r_d": r,
                             "in_window": ok, "stop": "target"})
                rec.attempts = a + 1
                if ok:
                    rec.layout, rec.accepted, rec.r_d = lay, True, r
                    break
            rec.attempt_log = log_
            out.append(rec)
        return out

    def _best(self, lc, Dl, role):
        p = self.plan[lc.name]
        ws = self.LW * 0.9
        s = p[role] if not callable(p[role]) else p[role](int(Dl.fp.split("_D")[1].split("_")[0]))
        return _fl(f"{Dl.fp}_{role}", ws * (1.0 + s) if role != "seed" else FAKE_L[Dl.fp])

    def search(self, lc, Dl, seed, lcfg, l_sub, tag, side=None):
        a = self._best(lc, Dl, "search")
        b = _fl(a.fp + "_2nd", FAKE_L[a.fp] * 1.01)
        short = [{"rank": 0, "fingerprint": b.fp, "l1": 1.0, "l_sub": l_sub(b)},
                 {"rank": 1, "fingerprint": a.fp, "l1": 1.1, "l_sub": l_sub(a)}]
        st = {"steps": 5, "moves": 6, "l1_evals": 100, "stopped_at_budget": True, "seed_in_domain": True,
              "improving_last10": True, "cfg_hash": "fake", "stop_reason": "budget", "last_improve_eval": 1900}
        B = int(lcfg["budget"])  # planted curve: seed L1 2.0, final 1.0; shares 0.1 (last 10 %) and 0.2 (last 25 %)
        traj = [{"n_l1": int(B * f), "score": sc} for f, sc in ((0.05, 1.5), (0.75, 1.2), (0.8, 1.1), (0.95, 1.0))]
        return SimpleNamespace(shortlist=short, stats=st, best=a, trajectory=traj)

    def null(self, role, lc, Dl, step_limit):
        lay = Dl if role == "seed" else self._best(lc, Dl, role)
        if role == "seed" and self.plan[lc.name].get("seed_defect"):
            lay = _fl(f"{Dl.fp}_seeddefect", self.LW * 0.9)  # planted defect: the seed null returns W*'s level
        return SimpleNamespace(layout=lay, steps=3, terminal="local_optimum" if role != "seed" else "none")

    def random_screen(self, lc, Dl, seed, lcfg, l_sub, tag):
        a = self._best(lc, Dl, "random_screen")
        return SimpleNamespace(layout=a, stats={"shortlist": [{"fingerprint": a.fp, "l1": 1.0, "l_sub": l_sub(a)}],
                                                "l1_evals": 50, "n_draws": 60}, terminal="none", steps=0)

    def proxy_alone(self, lc, Dl, budget, step_limit):
        return SimpleNamespace(layout=self._best(lc, Dl, "proxy_alone"), steps=7, kind="budget")

    def search_select(self, short, lsub):
        return min(range(len(short)), key=lambda i: (lsub[i], i))

    def spearman(self, a, b):
        return _mods().L.spearman(a, b)


BASE_PLAN = {"search": 0.005, "widen": 0.09, "compact": 0.07, "random_screen": 0.05, "proxy_alone": 0.012, "seed": None}
SCENARIOS = {  # name: (layouts with plan overrides, expected verdict)
    "pass": ({"2D_Case_2R": {}, "2D_Case_4": {}}, "PASS"),
    "null_recovers_on_one_layout": ({"2D_Case_2R": {"compact": 0.004}, "2D_Case_4": {}}, "INCONCLUSIVE"),
    "seed_null_meets_A1": ({"2D_Case_2R": {"seed_defect": True}, "2D_Case_4": {"seed_defect": True}}, "INVALID"),
    "fewer_than_two_layouts": ({"2D_Case_2R": {}, "2D_Case_4": {"R_D": 1.80}}, "INVALID"),
    "search_misses_on_2R": ({"2D_Case_2R": {"search": lambda j: 0.03 if j < 2 else 0.005}, "2D_Case_4": {}},
                            "INCONCLUSIVE"),
    "kill_K1": ({"2D_Case_2R": {"search": 0.06, "widen": 0.2, "compact": 0.2}, "2D_Case_4": {}}, "FAIL"),
}


def _selftest_spec() -> dict:
    spec = yaml.safe_load(DRAFT.read_text())
    fz = freeze_report(spec["config"])  # the selftest checks the F5 machinery; the run's own spec decides at run time
    spec["config"]["frozen_sha256"] = fz["frozen_sha256"]
    spec["config"]["code_sha256"] = fz["code_sha256"]
    spec["config"]["frozen"]["search_cfg_hash"] = fz["search_cfg_hash"]
    spec["config"]["frozen_sha256"] = canon_sha(spec["config"]["frozen"])
    return spec


def _scratch_store() -> None:
    """Selftest and smoke: the content-addressed copies go to a temp store, never into the checkout's .mfos/."""
    os.environ.setdefault("MFOS_ARTIFACT_STORE", tempfile.mkdtemp(prefix="e011-store-"))


def selftest() -> int:
    from mfos.evidence import ExperimentRun
    _scratch_store()
    spec = _selftest_spec()
    fails: list[str] = []
    for name, (plan, want) in SCENARIOS.items():
        FAKE_L.clear()
        plans = {k: BASE_PLAN | v for k, v in plan.items()}
        wd = Path(tempfile.mkdtemp(prefix=f"e011-st-{name}-"))
        rx = make_ctx(spec, "selftest", wd / "work", 20261116, ops=FakeOps(plans), fake=fake_job, mem_cap=1e6)
        recs = run_all(rx, [(k, True) for k in plans])
        with ExperimentRun(experiment_id=EID, run_dir=str(wd / "run")) as er:
            v, met, checks = finish(er, rx, recs, spec)
        failed = [c["name"] for c in checks if not c["passed"]]
        print(f"{'OK  ' if v == want else 'FAIL'} {name}: verdict {v} (want {want}); failed checks {failed}; "
              + ", ".join(f"{k}={m['value']:.4g}" for k, m in met.items()))
        if v != want:
            fails.append(name)
        if name == "pass":
            fails += _hand_checks(recs, met, er, wd / "run")
        if name == "fewer_than_two_layouts" and "F6_two_counted_layouts" not in failed:
            fails.append("F6 check did not fire")
        if name == "seed_null_meets_A1" and "F1a_seed_null_fails_A1" not in failed:
            fails.append("F1a check did not fire")
        if v == want and want != "INVALID" and failed:
            fails.append(f"{name}: unexpected failed checks {failed}")
    fails += _unit_checks()
    fails += _manifest_check(spec)
    print("SELFTEST", "PASS" if not fails else f"FAIL {fails}")
    return 0 if not fails else 1


def _hand_checks(recs, met, er, run_dir: Path) -> list[str]:
    """Hand values on the PASS scenario: s and b of one row from the fake levels; the selection rule; artifacts."""
    bad = []
    r = next(x for x in recs[0]["rows"] if x["role"] == "widen" and x["draw"] == 3)
    ws = FAKE_L["2D_Case_2R_Wd_star"]
    fp = r["fingerprint"]
    if abs(r["s"] - 0.09) > 1e-12:
        bad.append(f"hand s {r['s']} != 0.09")
    lv = list(LEVEL_EPS)
    h = lambda f: int(hashlib.sha256(f.encode()).hexdigest()[:6], 16) / 16**6  # noqa: E731
    x = [FAKE_L[fp] * (1 + LEVEL_EPS[k] * h(fp)) for k in lv]
    c = [ws * (1 + LEVEL_EPS[k] * h("2D_Case_2R_Wd_star")) for k in lv]
    if abs(r["b"] - 2 * MX.ratio_band_estimate(x, c)) > 1e-15:
        bad.append("hand b")
    srch = next(x for x in recs[0]["rows"] if x["role"] == "search" and x["draw"] == 0)
    if abs(srch["gain_share_last10"] - 0.1) > 1e-12 or abs(srch["gain_share_last25"] - 0.2) > 1e-12:
        bad.append(f"improvement curve {srch['gain_share_last10']}, {srch['gain_share_last25']} != planted 0.1, 0.2")
    if not srch["fingerprint"].endswith("_search") or abs(srch["s"] - 0.005) > 1e-12:
        bad.append(f"selection rule picked {srch['fingerprint']} (L1 rank 0 is the higher L_sub)")
    if met["control_layout_pass_min"]["value"] != 1.0 or met["null_beaten_min"]["value"] != 1.0:
        bad.append("planted PASS metrics")
    res = json.loads((run_dir / "result.json").read_text())
    names = {a["name"] for a in res["artifacts"]}
    if not {"rows.json", "evaluation_report.json"} <= names:
        bad.append(f"artifact names {names}")
    from mfos.models import ArtifactRef
    if artifacts_resolve(run_dir, [ArtifactRef(**a) for a in res["artifacts"]]):
        bad.append("artifacts do not resolve from result.json")
    for b in bad:
        print("FAIL hand:", b)
    return bad


def _unit_checks() -> list[str]:
    """Real-code checks that need no solve: the selection rule equals local_search's on a planted shortlist, the
    terminal mapping, sub-seed distinctness, and that the DC- reading context restores twin._net_side."""
    bad = []
    M = _mods()
    if RealOps.search_select(None, [{}, {}, {}], [2.0, 1.0, 1.0]) != 1:
        bad.append("search_select tie rule")
    if terminal("search", SimpleNamespace(stats={"stop_reason": "no_moves"}))[:2] != ("no_moves", True):
        bad.append("terminal search no_moves")
    if terminal("widen", SimpleNamespace(terminal="no_moves"))[:2] != ("no_moves", True):
        bad.append("terminal null no_moves")
    if terminal("compact", SimpleNamespace(terminal="local_optimum"))[:2] != ("local_optimum", False):
        bad.append("terminal null local_optimum")
    if terminal("compact", SimpleNamespace(terminal="step_limit"))[:2] != ("step_limit", True):
        bad.append("terminal step_limit")
    # review T0444: a no_moves null draw is capped, never a resolved failure; no_moves with capped false is refused
    nm = []
    for j in range(N7.N_DRAWS):
        base = {"layout": "L", "counted": True, "draw": j, "in_domain_W": True, "reach_outside": 0.0}
        nm.append(base | {"role": "search", "s": 0.0, "b": 0.001, "capped": True, "terminal_kind": "budget"})
        kind = "no_moves" if j < 5 else "local_optimum"
        nm.append(base | {"role": "widen", "s": 0.2, "b": 0.001, "capped": kind == "no_moves", "terminal_kind": kind})
    tab = N7.null_beaten_table(nm, nulls=("widen",))[("L", "widen")]
    if (tab["resolved"], tab["paired"], tab["beaten"]) != (3, 8, False):
        bad.append(f"no_moves null counted as a resolved failure: {tab}")
    try:
        N7.null_beaten_table([r | {"capped": False} if r["terminal_kind"] == "no_moves" else r for r in nm],
                             nulls=("widen",))
        bad.append("validator accepted no_moves with capped false")
    except ValueError:
        pass
    if len({sub_seed(1, "degrade"), sub_seed(1, "search", 0, 0), sub_seed(1, "random_screen", 0, 0)}) != 3:
        bad.append("sub_seed collision")
    sh = [{"fingerprint": "a", "l1": 1.0}, {"fingerprint": "b", "l1": 1.3}]  # b at evaluation 10, a at 1950
    vis = [(f"v{i}", None) for i in range(9)] + [("b", None)] + [(f"w{i}", None) for i in range(1939)] + [("a", None)]
    c = improvement_curve([], 2.0, sh, 2000, 1950, vis)
    near = lambda a, b: abs(a - b) <= 1e-12  # noqa: E731
    if not (near(c["gain_share_last10"], 0.3) and near(c["gain_share_last25"], 0.3) and c["gain_share_last10_exact"]):
        bad.append(f"improvement_curve exact path {c}")
    # no shortlist member by either cut (a at evaluation 1940, b at 1950): bracket [max short L1, trajectory minimum]
    c = improvement_curve([{"n_l1": 1700, "score": 1.6}], 2.0, sh, 2000, 1950, vis[10:] + vis[:10])
    if c["gain_share_last10_exact"] or not (near(c["gain_share_last10"], 0.6) and near(c["gain_share_last10_lo"], 0.3)
                                            and near(c["gain_share_last25"], 1.0)):
        bad.append(f"improvement_curve bracket path {c}")
    if tj_fallback_due({"W": 400.0, "Wstar": 401.9}, 2.0) or not tj_fallback_due({"W": 400.0, "Wstar": 402.5}, 2.0):
        bad.append("tj_fallback_due")
    # joint OC on planted rows (T0471): search passes on 4 of 8 draws, nulls fail far above their bands, so per layout
    # P(A1) = P(Bin(8, 1/2) >= 7) = 9/256 exactly; the vectorised form must agree with e011_metrics replicate by replicate
    pr = []
    for lay in ("L1", "L2"):
        for j in range(8):
            base = {"layout": lay, "counted": True, "draw": j, "in_domain_W": True, "reach_outside": 0.0}
            pr.append(base | {"role": "search", "s": 0.005 if j % 2 else 0.03, "b": 0.001, "capped": True,
                              "terminal_kind": "budget"})
            for nu in N7.GATING_NULLS:
                pr.append(base | {"role": nu, "s": 0.2, "b": 0.002, "capped": False, "terminal_kind": "local_optimum"})
    oc = joint_oc(pr, 8, 20000, 1, check_n7=300)
    se = math.sqrt(9 / 256 * (1 - 9 / 256) / 20000)
    if oc["n7_check"]["mismatches"] or any(abs(oc["per_layout"][x]["P_A1_layout"] - 9 / 256) > 4 * se
                                           for x in ("L1", "L2")) or oc["P_A3"] != 1.0 or oc["P_FAIL"] != 0.0:
        bad.append(f"joint_oc planted case {oc['per_layout']} {oc['n7_check']} A3 {oc['P_A3']} FAIL {oc['P_FAIL']}")
    lb = oc_lower_bounds(pr, 8)
    if not (abs(lb["each"]["events"]["L1|A1"]["p_L"] - N7.clopper_pearson_lower(4, 8)) < 1e-15
            and lb["P_PASS_lower_bonferroni"] == 0.0):
        bad.append("oc_lower_bounds")
    orig = M.T._net_side
    with dc_minus_reading(+1):
        moved = M.T._net_side is not orig
    if not moved or M.T._net_side is not orig:
        bad.append("dc_minus_reading")
    for b in bad:
        print("FAIL unit:", b)
    return bad


def _manifest_check(spec: dict) -> list[str]:
    """--dev and --dev-solve on fakes (T0430/T0431): write_manifest then dev_solve on a small manifest.  Every
    (fingerprint, level) job is submitted and solved, at every band level; a layout in two shortlists (draw 0's search
    and its DC- alt search share their members) is in both groups; each best is chosen by (L, L1 rank); wave 2 bands
    every best; a partial manifest, a manifest with another code stamp and an unstamped work directory are refused;
    E010's predicate fails a result without a convergence record and one with a non-finite L_H."""
    bad: list[str] = []
    FAKE_L.clear()
    FAKE_VEC.clear()
    plans = {"2D_Case_2R": dict(BASE_PLAN), "2D_Case_4": dict(BASE_PLAN)}
    root = Path(tempfile.mkdtemp(prefix="e011-st-manifest-"))
    rx = make_ctx(spec, "dev", root / "dev", 20261116, ops=FakeOps(plans), fake=fake_job, mem_cap=1e6)
    recs = run_all(rx, [(k, True) for k in plans])
    mp = root / "dev_jobs.json"
    man = write_manifest(rx, recs, "complete: selftest", path=mp, spec=spec)
    keys = {(j["fingerprint"], j["level"]) for j in man["jobs"]}
    levels = {j["level"] for j in man["jobs"]}
    if len(keys) != man["totals"]["jobs_wave1"] or not set(rx.band) <= levels:
        bad.append(f"manifest: {len(keys)} (fp, level) pairs vs {man['totals']['jobs_wave1']}; levels {sorted(levels)}")
    lays = man.get("layouts")
    if not (isinstance(lays, dict) and set(lays) >= set(plans)
            and all(len(v.get("rows_l1", [])) == len(N7.ROLES) * spec["config"]["frozen"]["n_draws"]
                    for v in lays.values())):
        bad.append("manifest layouts is not keyed by layout name with rows_l1 for every role and draw")
    vs = man.get("vm_sizing", {})
    if not (vs.get("largest_solve_GB", 0) > 0 and isinstance(vs.get("fits"), bool) and vs.get("per_layout_level")):
        bad.append(f"manifest vm_sizing {vs}")
    shared = [j for j in man["jobs"] if {"search_short_d0", "alt_short_d0"} <= {q["purpose"] for q in j["purposes"]}]
    if len(shared) != 2 * len(plans):
        bad.append(f"{len(shared)} jobs carry both search_short_d0 and alt_short_d0 (want {2 * len(plans)})")
    rs = vs.get("registered_run", {}).get("by_scenario", {})
    if not (vs.get("dev_burst", {}).get("learned", {}).get("makespan_h", 0) > 0 and len(rs) == 4
            and all(isinstance(v.get("fits_timeout"), bool) and v["makespan_h"] > 0 for v in rs.values())):
        bad.append(f"manifest vm_sizing: dev_burst {vs.get('dev_burst')} registered {rs}")
    dry = root / "vm_dry"  # --dev-solve --dry-run: every (fingerprint, level) job would be submitted, nothing solved
    rcd = dev_solve(str(mp), str(dry), ops=FakeOps(plans), fake=fake_job, spec=spec, dry=True)
    sd = json.loads((dry / "dev_solve_dryrun.json").read_text())
    if rcd != 0 or not sd["complete"] or sd["wave1_submitted"] != man["totals"]["jobs_wave1"] \
            or sd["shortlist_groups"] != man["totals"]["shortlist_groups"] or any((dry / "solves").glob("em_*.json")):
        bad.append(f"dry run rc {rcd}: {sd}")
    vm = root / "vm"
    rc = dev_solve(str(mp), str(vm), ops=FakeOps(plans), fake=fake_job, spec=spec)
    sm = json.loads((vm / "dev_solve_summary.json").read_text())
    if rc != 0 or sm["wave1_submitted"] != man["totals"]["jobs_wave1"] or sm["wave1_missing"] or sm["wave2_missing"]:
        bad.append(f"dev_solve rc {rc}: submitted {sm['wave1_submitted']} of {man['totals']['jobs_wave1']}, missing "
                   f"{sm['wave1_missing'][:3]} {sm['wave2_missing'][:3]}")
    k0 = next(iter(keys))  # E010's real Scheduler writes <out>.job.json beside each result: not a result (smoke, T0382)
    (vm / "solves" / f"em_{k0[1]}_{k0[0]}.job.json").write_text(json.dumps({"type": "em", "out": "x"}))
    if not Solves(vm, {}, None, 1, freq_hz=2.0e7).em_ok()[0]:
        bad.append("em_ok counts a scheduler .job.json file as a result")
    missing = [k for k in keys if not (vm / "solves" / f"em_{k[1]}_{k[0]}.json").exists()]
    if missing:
        bad.append(f"{len(missing)} manifest (fingerprint, level) jobs have no result, e.g. {missing[:2]}")
    g = sm.get("groups", {})
    for lname in plans:
        if g.get(f"{lname}|alt_short_d0", {}).get("n") != 2:
            bad.append(f"{lname}: alt_short_d0 group {g.get(f'{lname}|alt_short_d0')} (want both shared members)")
        sg = g.get(f"{lname}|search_short_d1", {})
        if sg.get("best_rank") != 1 or not str(sg.get("best_fingerprint", "")).endswith("_search"):
            bad.append(f"{lname}: search_short_d1 best {sg} (want rank 1, the lower L)")
        for k, v in g.items():
            if k.startswith(lname):
                bad += [f"{k}: best not banded at {lv}" for lv in rx.band
                        if not (vm / "solves" / f"em_{lv}_{v['best_fingerprint']}.json").exists()]
    if sm.get("wave2_jobs") != sm.get("wave2_expected") or not sm.get("l2_converged"):
        bad.append(f"wave 2 {sm.get('wave2_jobs')} vs {sm.get('wave2_expected')}; converged {sm.get('l2_converged')}")
    dr = dev_rows(str(mp), str(vm), out=str(root / "dev_rows.json"), spec=spec, n_boot=500)  # T0471
    srs = [r for r in dr["rows"] if r["role"] == "search"]
    if not (len(dr["rows"]) == len(plans) * len(N7.ROLES) * spec["config"]["frozen"]["n_draws"]
            and all(abs(r["s"] - BASE_PLAN["search"]) < 1e-12 for r in srs)
            and all(abs(r["R_D"] - 1.40) < 1e-12 and r["R_D_in_window"] for r in dr["rows"])
            and not dr["recompute_check"] and dr["joint_oc"]["n7_check"]["mismatches"] == 0
            and dr["joint_oc"]["P_PASS"] == 1.0 and all(p["Wstar_equals_provisional"] for p in dr["per_layout"].values())
            and all(r["changed_from_D"] is not None for r in dr["rows"])
            and set(dr["rank_stability"]) == set(plans) and dr["metrics"]["null_beaten_min"]["value"] == 1.0):
        bad.append(f"dev_rows: {len(dr['rows'])} rows, recompute {dr['recompute_check']}, oc {dr['joint_oc']['P_PASS']}")
    FAKE_TJ["delta_K"] = 3.0  # Tj(W*) - Tj(W) = 3 K > 2 K on the provisional W*: dev mode must record the fallback
    try:
        rxt = make_ctx(spec, "dev", root / "dev_tj", 20261116, ops=FakeOps(plans), fake=fake_job, mem_cap=1e6)
        rt = run_layout(rxt, "2D_Case_2R", 1, True)
    finally:
        FAKE_TJ["delta_K"] = 0.5
    if not (rt.get("tj_fallback_due") and "tj_fallback_pending_l2" in rt and any(
            q["purpose"] == "descent_diesfixed_band" for w in rxt.sv.wanted.values() for q in w["purposes"])):
        bad.append("Tj fallback not reachable in dev mode")
    if not all(d["r_d"] is None and d["r_d_provisional"] for d in rt["draws"]):
        bad.append("dev mode records a placeholder R_D as a number")
    for label, edit, exc in (("partial status", {"status": "partial: L1 stages running"}, RuntimeError),
                             ("other code stamp", {"code_stamp": dict(man["code_stamp"], code_tree_sha256="0")},
                              StaleCheckpoint)):
        q = root / f"bad_{len(label)}.json"
        q.write_text(json.dumps(man | edit, default=_js))
        try:
            dev_solve(str(q), str(root / f"vm_{len(label)}"), ops=FakeOps(plans), fake=fake_job, spec=spec)
            bad.append(f"dev_solve accepted a manifest with {label}")
        except exc:
            pass
    stale = root / "stale"
    (stale / "stages" / "x").mkdir(parents=True)
    (stale / "stages" / "x" / "f2.pkl").write_bytes(b"")
    for label, prep in (("unstamped", lambda: None),
                        ("other stamp", lambda: (stale / "code_stamp.json").write_text('{"code_tree_sha256": "0"}'))):
        prep()
        try:
            check_stamp(stale, code_stamp(spec))
            bad.append(f"check_stamp accepted an {label} work directory")
        except StaleCheckpoint:
            pass
    good = {"status": "ok", "L_H": 1e-8, "gmres_flags": [0], "solver_tol_rel_L_max": 1e-6}
    if em_failures(good) or not em_failures({"status": "ok", "L_H": 1e-8}) \
            or not em_failures(good | {"L_H": math.nan}) or not em_failures(good | {"gmres_flags": [0, 1]}):
        bad.append("em_failures does not apply E010's predicate")
    FAKE_UNCONVERGED.add(next(iter(keys))[0])  # one manifest layout returns no convergence record: dev_solve exits 3
    try:
        rc3 = dev_solve(str(mp), str(root / "vm_unconv"), ops=FakeOps(plans), fake=fake_job, spec=spec)
    finally:
        FAKE_UNCONVERGED.clear()
    if rc3 != 3:
        bad.append(f"dev_solve exit {rc3} with an unconverged result (want 3)")
    for b in bad:
        print("FAIL manifest:", b)
    print(f"{'OK  ' if not bad else 'FAIL'} manifest: {man['totals']['jobs_wave1']} wave-1 jobs at {sorted(levels)}, "
          f"{man['totals']['shortlist_groups']} shortlist groups, {sm.get('wave2_jobs')} wave-2 jobs, dev_solve rc {rc}")
    return bad


# ------------------------------------------------------------------------------------------------ smoke, dev, full
def smoke() -> int:
    from mfos.evidence import ExperimentRun
    _scratch_store()
    spec = _selftest_spec()
    wd = Path(os.environ.get("E011_SMOKE_DIR") or tempfile.mkdtemp(prefix="e011-smoke-"))
    rx = make_ctx(spec, "smoke", wd / "work", int(spec["config"]["dev"]["dev_seed"]), mem_cap=5.0, vcpus=4)
    t0 = time.time()
    recs = run_all(rx, [("gen2_0", True)])
    with ExperimentRun(experiment_id=EID, run_dir=str(wd / "run")) as er:
        v, met, checks = finish(er, rx, recs, spec, smoke=True)
    failed = [c["name"] for c in checks if not c["passed"]]
    print(json.dumps({"verdict_preview": v, "metrics": {k: m["value"] for k, m in met.items()}, "failed_checks": failed,
                      "rows": len(recs[0]["rows"]), "wall_s": round(time.time() - t0, 1), "dir": str(wd)},
                     default=_js))
    # smoke must exercise the real path end to end: rows for every role, finite s and b, the artifacts resolvable
    need = {"metrics_agree", "recompute_agrees", "l2_converged", "artifacts_resolve", "F2_W_rebuild", "Wstar_drc_clean",
            "draws_seed_in_domain", "seed_streams_distinct"}
    ok = len(recs[0]["rows"]) == len(N7.ROLES) and all(r["s"] is not None for r in recs[0]["rows"]) \
        and not (need & set(failed))
    return 0 if ok else 1


SHORT_KEYS = ("search_short", "rs_short", "alt_short")
ROW_L1_KEYS = ("draw", "role", "terminal_kind", "terminal_raw", "capped", "steps", "moves", "l1_evals", "n_draws",
               "stopped_at_budget", "seed_in_domain", "n_neighbours_step0", "improving_last10", "last_improve_eval",
               "changed_from_D", "manhattan_from_D_mm", "changed_from_Wstar", "manhattan_from_Wstar_mm", "fingerprint",
               "movable_indices")  # the L1-stage columns of a row (the manifest's rows_l1; s and b wait for L2)
MANIFEST_SCHEMA = "e011.dev_jobs/2"


def write_manifest(rx: RunCtx, recs: list[dict], status: str, path: Path | None = None, spec: dict | None = None) -> dict:
    """The burst-VM job manifest: one job per (fingerprint, level), with every purpose (and shortlist rank) that asked for
    it; the code stamp of the L1 stages; wave 2 (the band of each shortlist's best) as counts per layout and level."""
    c10 = cfg10()
    sp = spec or yaml.safe_load(DRAFT.read_text())
    vm, cm = c10["compute"]["vm"], c10["compute"]["cost_model"]
    cap = vm["memory_fraction"] * vm["ram_GB"]
    jobs = []
    for j in rx.sv.wanted.values():
        if j["type"] != "em":
            continue
        share = max(j["mem_GB"] / cap, j["threads"] * cm.get("cores_per_2thread_solve", 1.5) / 2 / vm["vcpus"])
        jobs.append({"id": Path(j["out"]).stem, "layout": j["ref"], "fingerprint": j["fp"], "level": j["level"],
                     "purpose": j["purpose"], "purposes": j["purposes"], "params": j["params"], "unknowns": j["unknowns"],
                     "est_wall_s_vm": round(j["est_s"], 1), "est_peak_GB": round(j["mem_GB"], 2),
                     "est_usd": round(j["est_s"] / 3600 * vm["usd_per_h"] * share, 4)})
    sim = [{"name": x["id"], "group": "g", "after": [], "est_s": x["est_wall_s_vm"], "threads": rx.sv.threads,
            "mem_GB": x["est_peak_GB"]} for x in jobs]
    mk = E.simulate(sim, vm["vcpus"], cap) if sim else 0.0
    keys = [(x["fingerprint"], x["level"]) for x in jobs]
    if len(set(keys)) != len(keys):
        raise RuntimeError("manifest: a (fingerprint, level) pair appears twice")
    groups = {(x["layout"], q["purpose"]) for x in jobs for q in x["purposes"] if q["purpose"].startswith(SHORT_KEYS)}
    n_short = sum(1 for x in jobs if any(q["purpose"].startswith(SHORT_KEYS) for q in x["purposes"]))
    wave2 = []  # the band of each shortlist's best is known only after wave 1 (one layout per search / screen draw)
    for rec in recs:
        n = sum(1 for d in rec.get("draws", []) if d["accepted"]) * 2 + (1 if rec.get("dcm_alt_search") else 0)
        for lv in rx.band:
            nu = E.em_unknowns(rx.sv.area[rec["layout"]], E.EM_LEVELS[lv][0], lv, cm)
            t, m = E.em_cost(nu, lv, cm)
            wave2.append({"layout": rec["layout"], "level": lv, "count": n, "est_wall_s_vm_each": round(t, 1),
                          "est_peak_GB": round(m * cm.get("em_level_mem_prior", {}).get(lv, 1.0), 2)})
    w2_s = sum(x["count"] * x["est_wall_s_vm_each"] for x in wave2)
    out = {"schema": MANIFEST_SCHEMA, "experiment": EID, "status": status,
           "code_stamp": code_stamp(sp),
           "generated": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
           "git_commit": subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip(),
           "workdir": str(rx.wd),
           "dev_seed": rx.seed, "sealed": False, "screen_level": rx.screen, "band_levels": list(rx.band),
           "rule": "development geometry and development seeds only (O008 F5); never the sealed draws",
           "how_to_run": "on the burst VM: uv run python experiments/runners/e011_run.py --dev-solve "
                         "experiments/drafts/E011.dev_jobs.json --workdir <dir> (rebuilds every layout from its params "
                         "and checks the fingerprint; wave 1 = these jobs, one per (fingerprint, level); wave 2 = the "
                         "band of each shortlist's best, by (L at screen_level, L1 rank); refuses a manifest whose "
                         "status is not complete or whose code_stamp differs from the checkout's)",
           "vm": {k: vm[k] for k in ("machine", "vcpus", "ram_GB", "memory_fraction", "usd_per_h")},
           "totals": {"jobs_wave1": len(jobs), "shortlist_jobs": n_short, "shortlist_groups": len(groups),
                      "jobs_by_level": {lv: sum(1 for x in jobs if x["level"] == lv) for lv in sorted({x["level"]
                                                                                                  for x in jobs})},
                      "sum_est_wall_h_vm": round(sum(x["est_wall_s_vm"] for x in jobs) / 3600, 2),
                      "makespan_h_wave1": round(mk / 3600, 2),
                      "usd_wave1": round(mk / 3600 * vm["usd_per_h"], 2),
                      "wave2_sum_wall_h_vm": round(w2_s / 3600, 2),
                      "usd_wave2_upper_serial_share": round(w2_s / 3600 * vm["usd_per_h"] * 0.5, 2)},
           "vm_sizing": vm_sizing(jobs, wave2, cap, vm, cm, rx.sv.threads,
                                  registered_model(jobs, recs, sp, rx.sv.area, cm, rx.prod, rx.screen, rx.band,
                                                   l1_walls(rx.wd, [r["layout"] for r in recs])),
                                  rx.sv.area, sp.get("timeout_min")),
           "wave2": wave2,
           "layouts": {r["layout"]: {k: v for k, v in r.items() if k != "rows"}  # keyed by layout name
                       | {"rows_l1": [{k: x[k] for k in ROW_L1_KEYS if k in x} for x in r.get("rows", [])]}
                       for r in recs},
           "jobs": jobs}
    Path(path or DEV_JOBS).write_text(json.dumps(out, indent=1, default=_js))
    return out


CALIB_SUMMARY = ROOT / "research" / "l2_thread_calib" / "summary.txt"
MAC_TO_VM_L1 = 1.8  # one Mac core ~ 1.8 VM vCPUs (E010 cost_model fem_s_per_dof_basis); applied to the L1 stage wall
REG_PHASES = ("P", "D", "L1", "S1", "S2")


def measured_mem_ratio(cm: dict) -> dict[str, float]:
    """Measured peak RSS / E010 model peak of l2_layout on 2D_Case_4 (P3's calibration layout) per level, from the founder's
    VM thread calibration (research/l2_thread_calib/summary.txt: 'rss X GB' of the *_lat0.25 and *_lat0.5 rows; the
    unknowns are em_ref_unknowns at 0.25 mm and a quarter of it at 0.5 mm).  Empty if the file is absent."""
    if not CALIB_SUMMARY.exists():
        return {}
    rss: dict[str, float] = {}
    for line in CALIB_SUMMARY.read_text().splitlines():
        m = re.match(r"\S+_(lat0\.25|lat0\.5)\s.*\srss\s+([\d.]+) GB", line)
        if m:
            rss[m[1]] = max(rss.get(m[1], 0.0), float(m[2]))
    n = {"lat0.25": cm["em_ref_unknowns"], "lat0.5": cm["em_ref_unknowns"] / 4}
    return {lv: v / E.em_cost(int(n[lv]), lv, cm)[1] for lv, v in rss.items()}


def _mem(model: float, lv: str, cm: dict, scen: str, ratio: dict) -> float:
    """Scheduling peak of one solve: 'prior' = model x em_level_mem_prior (E010's Scheduler before a solve of the same
    reference and level has finished); 'learned' = model x 1.1 x the measured ratio (Scheduler.mem_of afterwards) where
    a measured ratio exists (Case 4 at lat0.25 / lat0.5), else the prior."""
    prior = model * cm.get("em_level_mem_prior", {}).get(lv, 1.0)
    return model * 1.1 * ratio[lv] if scen == "learned" and lv in ratio else prior


def _solve(area: float, lv: str, cm: dict) -> tuple[int, float, float]:
    n = E.em_unknowns(area, E.EM_LEVELS[lv][0], lv, cm)
    t, m = E.em_cost(n, lv, cm)
    return n, t, m


DEV_ONLY_STAGES = ("proxy_threshold_free", "proxy_reach_false_probe", "proxy_dies_fixed", "proxy_dcm_alt_reading",
                   "d0_search_dcm_alt")


def l1_walls(wd: Path, layouts: list[str]) -> dict[str, float]:
    """Per layout, the summed compute wall (s) of its stage checkpoints (cached() writes <stage>.wall), dev-only stages
    excluded; a layout with no .wall file is absent."""
    out = {}
    for name in layouts:
        fs = [f for f in (Path(wd) / "stages" / name).glob("*.wall") if f.stem not in DEV_ONLY_STAGES]
        if fs:
            out[name] = sum(float(f.read_text()) for f in fs)
    return out


def registered_model(jobs: list[dict], recs: list[dict], spec: dict, area: dict, cm: dict, prod: str, screen: str,
                     band: tuple, l1_wall_s: dict) -> dict:
    """Solve counts of the registered run per layout and phase, from the development structure (the code path of
    run_layout in full mode, where screen = production = lat0.25): P = W and the descent at the band levels; D = one R_D
    solve per degradation attempt at production (wave 0: n_draws; with redraws up to (1 + redraw_limit) x n_draws in
    1 + redraw_limit waves); L1 = the draws' L1 stages (the dev run's measured stage wall x MAC_TO_VM_L1, dev-only stages
    excluded); S1 = the search and random-screen shortlist members and the widen / compact / proxy-alone end points at
    production (the dev run's distinct fingerprints at screen level; the nominal n_draws x (2 K + 3) where there is no
    dev run); S2 = the band of the six scored layouts per draw at the non-production band levels.  Phases run in this
    order and layouts one after another (run_all is sequential; each sv.run blocks)."""
    fr = spec["config"]["frozen"]
    nd, K = int(fr["n_draws"]), int(fr["search"]["shortlist"])
    rdl = int(fr["degradation"]["redraw_limit"])
    out: dict[str, Any] = {}
    for name in spec["config"]["layouts"]:
        if name not in area:
            out[name] = {"omitted": "no area (layout not loaded)"}
            continue
        mine = [x for x in jobs if x["layout"] == name]
        purp = lambda x: {q["purpose"] for q in x["purposes"]}  # noqa: E731
        d_fp = {x["fingerprint"] for x in mine if "D_R_D" in purp(x)}
        p_fp = {x["fingerprint"] for x in mine if purp(x) & {"W_band", "descent_band"}}
        s1 = {x["fingerprint"] for x in mine if x["level"] == screen and any(
            q.startswith(("search_short", "rs_short")) or re.fullmatch(r"(widen|compact|proxy_alone)_d\d+", q)
            for q in purp(x))} - d_fp - p_fp
        dev = bool(mine)
        n_s1 = len(s1) if dev else nd * (2 * K + 3)
        out[name] = {"source": "dev manifest" if dev else "nominal (no dev run)",
                     "P": {lv: 2 for lv in band}, "D_wave0": {prod: nd}, "redraw_waves_max": rdl,
                     "S1": {prod: n_s1}, "S1_nominal": nd * (2 * K + 3),
                     "S2": {lv: 6 * nd for lv in band if lv != prod},
                     "L1_wall_h_mac": round(l1_wall_s.get(name, 0.0) / 3600, 3) if name in l1_wall_s else None,
                     "unknowns": {lv: _solve(area[name], lv, cm)[0] for lv in band}}
    return out


def _simulate_registered(model: dict, area: dict, cm: dict, vm: dict, cap: float, threads: int, scen: str,
                         ratio: dict, redraws: bool, l1_default_h: float) -> float:
    sim, prev = [], None
    for name, m in model.items():
        if "omitted" in m:
            continue
        phases = [("P", m["P"]), ("D", m["D_wave0"])]
        if redraws:  # upper bound: every draw redrawn in every one of the redraw_limit further waves
            phases += [(f"D{w + 1}", m["D_wave0"]) for w in range(int(m["redraw_waves_max"]))]
        phases += [("L1", None), ("S1", m["S1"]), ("S2", m["S2"])]
        for ph, counts in phases:
            g = f"{name}|{ph}"
            if counts is not None and sum(counts.values()) == 0:
                continue  # an empty phase (mid-run manifest): no group, or simulate would wait on it forever
            if counts is None:
                h = m["L1_wall_h_mac"] if m["L1_wall_h_mac"] is not None else l1_default_h
                sim.append({"name": g, "group": g, "after": [prev] if prev else [], "est_s": h * 3600 * MAC_TO_VM_L1,
                            "threads": 1, "mem_GB": 0.0})
            else:
                for lv, c in counts.items():
                    _, t, mm = _solve(area[name], lv, cm)
                    sim += [{"name": f"{g}|{lv}|{i}", "group": g, "after": [prev] if prev else [], "est_s": t,
                             "threads": threads, "mem_GB": _mem(mm, lv, cm, scen, ratio)} for i in range(c)]
            prev = g
    return E.simulate(sim, int(vm["vcpus"]), cap) if sim else 0.0


def vm_sizing(jobs: list[dict], wave2: list[dict], cap: float, vm: dict, cm: dict | None = None, threads: int = 1,
              reg: dict | None = None, area: dict | None = None, timeout_min: float | None = None) -> dict:
    """VM sizing from the manifest's own jobs (E010's cost model on each layout's unknowns, em_unknowns / em_cost): per
    (layout, level) the unknowns, the model peak, the scheduling peak under the prior and after learning (measured
    ratio, measured_mem_ratio), and how many fit at once by memory and by vCPUs; the development burst's makespan and
    cost (wave 1 then wave 2, list scheduling, E010.simulate) under both; the registered run's makespan, cost and
    whether it fits timeout_min (registered_model; phases sequential, layouts sequential), with and without the maximum
    redraw waves.  Billing: whole VM, (makespan + overhead_h) x usd_per_h.  A solve above ``cap`` cannot run on this VM
    (E010's phase B)."""
    cm = cm or {}
    ratio = measured_mem_ratio(cm) if cm else {}
    by_cpu = max(1, int(vm["vcpus"]) // max(1, threads))
    per: dict[str, dict] = {}
    for x in jobs:
        e = per.setdefault(f"{x['layout']}|{x['level']}", {"unknowns": x["unknowns"], "peak_GB": 0.0, "jobs": 0,
                                                          "est_wall_h_each": round(x["est_wall_s_vm"] / 3600, 3)})
        e["peak_GB"], e["jobs"] = max(e["peak_GB"], x["est_peak_GB"]), e["jobs"] + 1
    for k, e in per.items():
        if cm:
            lv = k.split("|")[1]
            model = E.em_cost(int(e["unknowns"]), lv, cm)[1]
            e["model_GB"] = round(model, 2)
            for sc in ("prior", "learned"):
                g = _mem(model, lv, cm, sc, ratio)
                e[f"sched_GB_{sc}"] = round(g, 2)
                e[f"at_once_{sc}"] = int(min(cap // g, by_cpu)) if g > 0 else by_cpu
    big = max([x["est_peak_GB"] for x in jobs] + [x["est_peak_GB"] for x in wave2], default=0.0)
    out: dict[str, Any] = {"machine": vm["machine"], "ram_GB": vm["ram_GB"], "usable_GB": round(cap, 1),
                           "vcpus": vm["vcpus"], "threads_per_solve": threads, "at_once_by_vcpus": by_cpu,
                           "per_layout_level": per, "largest_solve_GB": big,
                           "largest_fit_at_once": int(cap // big) if big > 0 else None, "fits": bool(big <= cap)}
    if not cm:
        return out
    out["measured_mem_ratio"] = {k: round(v, 4) for k, v in ratio.items()}
    out["measured_basis"] = (f"{CALIB_SUMMARY.relative_to(ROOT)}: peak RSS of 2D_Case_4 solves on the VM (lat0.25 "
                             "15.8-15.9 GB at 4.11 M unknowns) against E010's model peak; scheduling peak after learning "
                             "= model x 1.1 x ratio (Scheduler.mem_of)")
    oh, usd = float(vm.get("overhead_h", 0.0)), float(vm["usd_per_h"])
    burst = {}
    for sc in ("prior", "learned"):
        sim = [{"name": x["id"], "group": "w1", "after": [], "est_s": x["est_wall_s_vm"], "threads": threads,
                "mem_GB": _mem(E.em_cost(int(x["unknowns"]), x["level"], cm)[1], x["level"], cm, sc, ratio)}
               for x in jobs]
        sim += [{"name": f"w2|{w['layout']}|{w['level']}|{i}", "group": "w2", "after": ["w1"],
                 "est_s": w["est_wall_s_vm_each"], "threads": threads,
                 "mem_GB": _mem(E.em_cost(int(_solve(area[w["layout"]], w["level"], cm)[0]), w["level"], cm)[1],
                                w["level"], cm, sc, ratio)}
                for w in wave2 for i in range(int(w["count"]))] if area else []
        mk = E.simulate(sim, int(vm["vcpus"]), cap) / 3600 if sim else 0.0
        burst[sc] = {"makespan_h": round(mk, 2), "usd": round((mk + oh) * usd, 2)}
    out["dev_burst"] = burst | {"basis": "wave 1 (every manifest job) then wave 2 (the band of each shortlist's best), "
                                         "list scheduling by memory and vCPUs; usd = (makespan + overhead_h) x usd_per_h"}
    if reg and area:
        l1_known = [m["L1_wall_h_mac"] for m in reg.values() if m.get("L1_wall_h_mac")]
        l1_def = float(np.mean(l1_known)) if l1_known else 1.0
        regd: dict[str, Any] = {}
        for sc in ("prior", "learned"):
            for rd in (False, True):
                try:  # the sizing model must never stop the L1 stages that call write_manifest
                    mk = _simulate_registered(reg, area, cm, vm, cap, threads, sc, ratio, rd, l1_def) / 3600
                except Exception as e:  # noqa: BLE001
                    regd[f"{sc}|{'max_redraws' if rd else 'no_redraws'}"] = {"error": repr(e)}
                    continue
                tot = mk + oh
                regd[f"{sc}|{'max_redraws' if rd else 'no_redraws'}"] = {
                    "makespan_h": round(mk, 1), "usd": round(tot * usd, 2),
                    "fits_timeout": None if timeout_min is None else bool(tot <= timeout_min / 60)}
        out["registered_run"] = {"timeout_h": None if timeout_min is None else timeout_min / 60, "by_scenario": regd,
                                 "solves": reg, "l1_wall_h_mac_default": round(l1_def, 3),
                                 "basis": registered_model.__doc__.split("\n")[0] + " ... (registered_model)"}
    return out


def dev(workdir: str | None) -> int:
    spec = yaml.safe_load(DRAFT.read_text())
    cfg = spec["config"]
    wd = Path(workdir or os.environ.get("E011_WORKDIR") or ROOT / "research" / "o008_e011_dev" / "work")
    rx = make_ctx(spec, "dev", wd, int(cfg["dev"]["dev_seed"]), mem_cap=5.0, vcpus=4)
    for name in cfg["layouts"]:  # areas of the registered run's other layouts (gen2_0), for the sizing model only
        if name not in cfg["dev"]["layouts"]:
            try:
                rx.sv.area[name] = rx.ops.load(name).area_m2
            except Exception as e:  # noqa: BLE001
                log(f"{name}: not loaded for the sizing model ({e})")
    recs: list[dict] = []
    _HOOK["fn"] = lambda: write_manifest(rx, recs, "partial: L1 stages running", spec=spec)
    write_manifest(rx, recs, "partial: started; resume with --dev --workdir " + str(wd), spec=spec)
    for name in cfg["dev"]["layouts"]:
        recs.append(run_layout(rx, name, int(cfg["layout_index"][name]), True))
        write_manifest(rx, recs, "partial: L1 stages running", spec=spec)
    m = write_manifest(rx, recs, "complete: L1 stages done, L2 pending (burst VM)", spec=spec)
    print(json.dumps(m["totals"], indent=1))
    return 0


def _short_groups(table: dict, man: dict) -> dict[tuple[str, str], list]:
    """Shortlist groups rebuilt from every wave-1 job's ``purposes`` at the screen level: (layout, purpose) -> [(layout
    object, L1 rank)]; a layout in two shortlists belongs to both.  The count and rank contiguity (0..n-1) are asserted."""
    groups: dict[tuple[str, str], list] = {}
    for lay, j in table.values():
        if j["level"] != man["screen_level"]:
            continue
        for q in j["purposes"]:
            if q["purpose"].startswith(SHORT_KEYS):
                groups.setdefault((j["layout"], q["purpose"]), []).append((lay, int(q["rank"])))
    if len(groups) != int(man["totals"]["shortlist_groups"]):
        raise RuntimeError(f"{len(groups)} shortlist groups rebuilt, manifest says {man['totals']['shortlist_groups']}")
    for k, g in sorted(groups.items()):
        ranks = sorted(r for _, r in g)
        if ranks != list(range(len(g))):
            raise RuntimeError(f"shortlist {k}: ranks {ranks} are not 0..{len(g) - 1}")
    return groups


def dev_solve(manifest: str, workdir: str | None, ops=None, fake=None, spec: dict | None = None,
              dry: bool = False) -> int:
    """Burst VM: rebuild every manifest layout from its params (fingerprint checked), solve wave 1 (every job: one per
    (fingerprint, level), the count asserted against totals.jobs_wave1), then the band of each shortlist's best.  The
    shortlist groups come from every job's ``purposes`` (a layout shared by two shortlists is a member of both); the best
    is local_search's rule, the lowest L at screen_level, ties by L1 rank.  Refuses a manifest that is not complete or
    whose code stamp differs from this checkout.  Writes <workdir>/dev_solve_summary.json.  Exit 0 iff every wave-1 and
    wave-2 job has a result and every result passes E010's convergence predicate (em_failures); 3 otherwise.
    ``dry`` (--dev-solve MANIFEST --dry-run): the same refusals, rebuilds and count assertions, the shortlist groups and
    the wave-2 count, but no solve; writes <workdir>/dev_solve_dryrun.json and exits 0 iff every (fingerprint, level)
    job would be submitted exactly once and the groups and wave 2 match the manifest."""
    man = json.loads(Path(manifest).read_text())
    spec = spec or yaml.safe_load(DRAFT.read_text())
    if man.get("schema") != MANIFEST_SCHEMA or not str(man.get("status", "")).startswith("complete"):
        raise RuntimeError(f"{manifest}: schema {man.get('schema')} / status {man.get('status')!r}: not a complete "
                           f"{MANIFEST_SCHEMA} manifest; rerun --dev until its status reads complete")
    if man.get("code_stamp") != code_stamp(spec):
        raise StaleCheckpoint(f"{manifest}: its code_stamp differs from this checkout's; the L1 stages that chose these "
                              "layouts were run with other code")
    wd = Path(workdir or os.environ.get("E011_WORKDIR") or Path(tempfile.gettempdir()) / "e011_dev_l2")
    if fake is not None:
        rx = make_ctx(spec, "selftest", wd, int(man["dev_seed"]), ops=ops, fake=fake, mem_cap=1e6)
    else:
        rx = make_ctx(spec, "full", wd, int(man["dev_seed"]), ops=ops)
    ops, sv = rx.ops, rx.sv
    lcs = {n: ops.load(n) for n in sorted({j["layout"] for j in man["jobs"]})}
    for n, lc in lcs.items():
        sv.area[n] = lc.area_m2
    byfp: dict[str, Any] = {}
    table: dict[tuple[str, str], tuple[Any, dict]] = {}  # (fingerprint, level) -> (layout, manifest job)
    for j in man["jobs"]:
        key = (j["fingerprint"], j["level"])
        if key in table:
            raise RuntimeError(f"{j['id']}: (fingerprint, level) {key} listed twice")
        if j["fingerprint"] not in byfp:
            lay = ops.rebuild(lcs[j["layout"]], j["params"])
            if lay.fingerprint() != j["fingerprint"]:
                raise RuntimeError(f"{j['id']}: rebuilt fingerprint {lay.fingerprint()} != {j['fingerprint']}")
            byfp[j["fingerprint"]] = lay
        table[key] = (byfp[j["fingerprint"]], j)
    w1 = [sv.em_job(lay, j["level"], j["layout"], j["purpose"], j["params"]) for lay, j in table.values()]
    n_want = int(man["totals"]["jobs_wave1"])
    if not (len(w1) == n_want == len(man["jobs"]) == len({x["out"] for x in w1})):
        raise RuntimeError(f"wave 1: {len(w1)} jobs built, {len({x['out'] for x in w1})} distinct outputs, "
                           f"totals.jobs_wave1 {n_want}, manifest lists {len(man['jobs'])}")
    summary: dict[str, Any] = {"manifest": str(manifest), "wave1_submitted": len(w1), "jobs_wave1": n_want}
    want2 = sum(int(x["count"]) for x in man["wave2"])  # one entry per (layout, band level), count = groups
    if dry:
        groups = _short_groups(table, man)
        w2n = len(groups) * len(man["band_levels"])
        by_lv: dict[str, int] = {}
        for x in w1:
            by_lv[x["level"]] = by_lv.get(x["level"], 0) + 1
        summary |= {"dry_run": True, "wave1_distinct_outputs": len({x["out"] for x in w1}),
                    "wave1_by_level": by_lv, "jobs_by_level_manifest": man["totals"]["jobs_by_level"],
                    "fingerprints_rebuilt": len(byfp), "shortlist_groups": len(groups), "wave2_would_submit": w2n,
                    "wave2_expected": want2,
                    "complete": by_lv == man["totals"]["jobs_by_level"] and w2n == want2}
        wd.mkdir(parents=True, exist_ok=True)
        (wd / "dev_solve_dryrun.json").write_text(json.dumps(summary, indent=1, default=_js))
        print(json.dumps(summary, default=_js))
        return 0 if summary["complete"] else 3
    try:
        sv.run(w1)
        summary["wave1_missing"] = [Path(x["out"]).name for x in w1 if sv.rec(x) is None]
        groups = _short_groups(table, man)
        best, gsum = {}, {}
        for k, g in sorted(groups.items()):
            lay, rank = min(g, key=lambda t: (sv.L(t[0], man["screen_level"]), t[1]))
            best[k] = lay
            gsum["|".join(k)] = {"n": len(g), "best_fingerprint": lay.fingerprint(), "best_rank": rank,
                                 "best_L_H": sv.L(lay, man["screen_level"])}
        w2 = [sv.em_job(x, lv, k[0], f"best_band|{k[1]}", ops.vec(x).tolist())
              for k, x in best.items() for lv in man["band_levels"]]
        summary |= {"groups": gsum, "wave2_jobs": len(w2), "wave2_expected": want2,
                    "wave2_already_solved": sum(1 for x in w2 if sv.rec(x) is not None)}
        sv.run(w2)
        summary["wave2_missing"] = [Path(x["out"]).name for x in w2 if sv.rec(x) is None]
    except E.NeedsLargerMachine as e:
        print(json.dumps(E.phase_stop(e, wd, cfg10()["compute"]["vm"])))
        return E.PHASE_B_EXIT
    ok, n, bad = sv.em_ok()
    summary |= {"em_results": n, "l2_converged": ok, "unconverged": bad}
    good = ok and not summary["wave1_missing"] and not summary["wave2_missing"] and len(w2) == want2
    summary["complete"] = good
    (wd / "dev_solve_summary.json").write_text(json.dumps(summary, indent=1, default=_js))
    print(json.dumps({k: v for k, v in summary.items() if k != "groups"}, default=_js))
    return 0 if good else 3


# ------------------------------------------------------------------------------------------------ dev L2 analysis (T0471)
DEV_L2 = ROOT / "research" / "o008_e011_dev" / "dev_l2"
DEV_ROWS_SCHEMA = "e011.dev_rows/1"
L1_STAGE_COLS = ("terminal_raw", "steps", "moves", "l1_evals", "n_draws", "stopped_at_budget", "seed_in_domain",
                 "n_neighbours_step0", "improving_last10", "last_improve_eval")


class L2Table:
    """The burst's l2_layout results under <l2dir>/solves (em_<level>_<fingerprint>.json), read on demand; a missing
    result, a status other than ok or a result failing E010's predicate (em_failures) raises: no row is built on it."""

    def __init__(self, l2dir: Path):
        self.dir, self.cache = Path(l2dir) / "solves", {}

    def rec(self, fp: str, lv: str) -> dict:
        k = (fp, lv)
        if k not in self.cache:
            p = self.dir / f"em_{lv}_{fp}.json"
            if not p.exists():
                raise RuntimeError(f"no l2_layout result {p.name}")
            r = json.loads(p.read_text())
            why = ([f"status {r.get('status')}"] if r.get("status") != "ok" else []) + em_failures(r)
            if why:
                raise RuntimeError(f"{p.name}: {'; '.join(why)}")
            self.cache[k] = r
        return self.cache[k]

    def L(self, fp: str, lv: str) -> float:
        return float(self.rec(fp, lv)["L_H"])

    def has(self, fp: str, lv: str) -> bool:
        return (self.dir / f"em_{lv}_{fp}.json").exists()


def _groups_from_manifest(man: dict) -> dict[tuple[str, str], list[tuple[str, int]]]:
    """(layout, shortlist purpose) -> [(fingerprint, L1 rank)], from every wave-1 job's purposes at the screen level
    (the same rebuild as _short_groups, on fingerprints)."""
    g: dict[tuple[str, str], list[tuple[str, int]]] = {}
    for j in man["jobs"]:
        if j["level"] == man["screen_level"]:
            for q in j["purposes"]:
                if q["purpose"].startswith(SHORT_KEYS):
                    g.setdefault((j["layout"], q["purpose"]), []).append((j["fingerprint"], int(q["rank"])))
    return g


def tj_fallback_due(tj: dict, limit_K: float) -> bool:
    """O008 scope_in: the proxy falls back to the dies-fixed descent when Tj(W*) - Tj(W) > limit (hottest die, level 0)."""
    return bool(tj["Wstar"] - tj["W"] > float(limit_K))


def dev_rows(manifest: str, l2dir: str, out: str | None = None, spec: dict | None = None, n_boot: int = 20000,
             boot_seed: int = 20261119) -> dict:
    """T0471: development rows from the burst's L2 results (no solve).  Inputs: the complete L1 manifest (its
    ``layouts`` records and ``rows_l1``; every job's params and purposes), <l2dir>/code_stamp.json (must equal the
    manifest's stamp: the L2 results belong to these L1 stages, whatever the checkout's code is now),
    <l2dir>/dev_solve_summary.json (complete, converged) and every result file used.  Per counted layout: W* by
    control.choose_proxy's rule at the production level (the descent only if its L_sub is strictly lower than W's);
    each shortlist's best re-derived by local_search's rule at the screen level (lowest L, ties by L1 rank) and
    asserted equal to the burst's; one row per (layout, role, draw) with n7's columns, s and b at the production level
    from the band levels exactly as run_layout computes them, R_D = L_sub(D_j) / L_sub(W*) at the production level and
    at the screen level, distances over movable_indices.  Then the gated metrics (n7 and mfos.metrics), the reported
    helpers, the band bound per role, ranking stability, the joint operating characteristic and the measured sizing.
    Writes ``out`` (default <l2dir>/dev_rows.json, {'rows': [...], ...}: mfos exp check --rows reads it)."""
    man = json.loads(Path(manifest).read_text())
    l2 = Path(l2dir)
    spec = spec or yaml.safe_load(DRAFT.read_text())
    cfg = spec["config"]
    stamp = json.loads((l2 / "code_stamp.json").read_text())
    summ = json.loads((l2 / "dev_solve_summary.json").read_text())
    if man.get("schema") != MANIFEST_SCHEMA or not str(man.get("status", "")).startswith("complete"):
        raise RuntimeError(f"{manifest}: not a complete {MANIFEST_SCHEMA} manifest")
    if man["code_stamp"] != stamp:
        raise StaleCheckpoint(f"{l2}/code_stamp.json differs from the manifest's stamp: the L2 results are not these "
                              "L1 stages' solves")
    if not (summ.get("complete") and summ.get("l2_converged") and not summ.get("wave1_missing")
            and not summ.get("wave2_missing")):
        raise RuntimeError(f"{l2}/dev_solve_summary.json is not complete and converged")
    T = L2Table(l2)
    prod, screen, band = cfg["levels"]["production"], man["screen_level"], tuple(man["band_levels"])
    if band != tuple(cfg["levels"]["band"]) or band[0] != prod:
        raise RuntimeError(f"band levels {band} differ from the spec's {cfg['levels']['band']}")
    n_draws = int(cfg["frozen"]["n_draws"])
    lo, hi = (float(x) for x in cfg["frozen"]["degradation"]["window"])
    params = {j["fingerprint"]: j["params"] for j in man["jobs"]}
    groups = _groups_from_manifest(man)
    best: dict[tuple[str, str], tuple[str, int]] = {}
    for k, g in sorted(groups.items()):
        best[k] = min(g, key=lambda t: (T.L(t[0], screen), t[1]))
        sg = summ["groups"]["|".join(k)]
        if (sg["best_fingerprint"], int(sg["best_rank"])) != best[k]:
            raise RuntimeError(f"{k}: best {best[k]} differs from the burst's selection {sg}")
    spear = _mods().L.spearman
    rows: list[dict] = []
    per: dict[str, dict] = {}
    for name, rec in man["layouts"].items():
        mv = [int(i) for i in rec["movable_indices"]]
        wfp = [j["fingerprint"] for j in man["jobs"] if j["layout"] == name
               and any(q["purpose"] == "W_band" for q in j["purposes"])]
        if len(set(wfp)) != 1:
            raise RuntimeError(f"{name}: {len(set(wfp))} W_band fingerprints")
        wfp, dfp = wfp[0], rec["proxy"]["fingerprint"]
        lw, ld = T.L(wfp, prod), T.L(dfp, prod)
        ws = dfp if ld < lw else wfp  # control.choose_proxy (F3): the descent's end only if strictly lower
        Wb = [T.L(ws, lv) for lv in band]
        L_ws, L_ws_scr = Wb[0], T.L(ws, screen)
        by = {(r["role"], int(r["draw"])): r for r in rec["rows_l1"]}
        draws = sorted({int(r["draw"]) for r in rec["rows_l1"]})
        Dfp = {j: by[("seed", j)]["fingerprint"] for j in draws}
        curve = {int(k): v for k, v in rec["search_improvement"]["per_draw"].items()}
        for j in draws:
            for role in N7.ROLES:
                l1 = by[(role, j)]
                rank = None
                if role in ("search", "random_screen"):
                    fp, rank = best[(name, f"{'search_short' if role == 'search' else 'rs_short'}_d{j}")]
                else:
                    fp = l1["fingerprint"]
                Lb = [T.L(fp, lv) for lv in band]
                b = 2.0 * MX.ratio_band_estimate(Lb, Wb)
                ch_d, mh_d = dist(params[fp], params[Dfp[j]], mv)
                ch_w, mh_w = dist(params[fp], params[ws], mv)
                rd = T.L(Dfp[j], prod) / L_ws
                row = {"layout": name, "counted": bool(rec["counted"]), "draw": j, "role": role,
                       "s": Lb[0] / L_ws - 1.0, "b": b, "capped": bool(l1["capped"]),
                       "terminal_kind": l1["terminal_kind"], "in_domain_W": bool(rec["f2"]["in_domain_reach"][0]),
                       "reach_outside": 1.0 - float(bool(rec["f2"]["in_domain_reach"][0])),
                       "L_sub_H": Lb[0], "L_sub_Wstar_H": L_ws, "e_R": b / 2.0, "L_band_H": Lb,
                       "s_screen": T.L(fp, screen) / L_ws_scr - 1.0, "R_D": rd,
                       "R_D_screen": T.L(Dfp[j], screen) / L_ws_scr, "R_D_in_window": bool(lo <= rd <= hi),
                       "R_D_provisional": False, "fingerprint": fp, "best_rank": rank,
                       "changed_from_D": ch_d, "manhattan_from_D_mm": mh_d, "changed_from_Wstar": ch_w,
                       "manhattan_from_Wstar_mm": mh_w, "l_sub_level": prod, "band_levels": list(band),
                       "selection_level": screen if rank is not None else None, "movable_indices": mv,
                       "source": "dev L2 (T0471): research/o008_e011_dev/dev_l2"}
                row |= {k: l1[k] for k in L1_STAGE_COLS if k in l1}
                if role == "search":
                    g = sorted(groups[(name, f"search_short_d{j}")], key=lambda t: t[1])
                    ls = [T.L(f, screen) for f, _ in g]
                    row |= {"spearman_l1rank_lscreen": spear([float(r) for _, r in g], ls),
                            "shortlist_screen_gap_rel": (sorted(ls)[1] / sorted(ls)[0] - 1.0) if len(ls) > 1 else None,
                            **{k: curve[j][k] for k in curve.get(j, {}) if k.startswith(("gain_share", "l1_gain"))}}
                rows.append(row)
        alt = best.get((name, "alt_short_d0"))
        s0 = next(r for r in rows if r["layout"] == name and r["role"] == "search" and r["draw"] == 0)
        sens = {k: {"l1_ratio": v["l1_ratio"], "same_as_frozen": v["same_as_frozen"],
                    "L_screen_over_Wstar": T.L(v["fingerprint"], screen) / L_ws_scr}
                for k, v in rec.get("proxy_sensitivity", {}).items() if T.has(v["fingerprint"], screen)}
        lr = [r for r in rows if r["layout"] == name]
        per[name] = {
            "W_fingerprint": wfp, "descent_fingerprint": dfp, "Wstar_fingerprint": ws,
            "Wstar_equals_provisional": ws == rec["Wstar"]["fingerprint"],
            "choice": "descent" if ws == dfp else "W", "L_sub_W_H": lw, "L_sub_descent_H": ld,
            "L_sub_ratio_Wstar_W": L_ws / lw, "l1_ratio_Wstar_W": rec["proxy"]["l1_ratio"],
            "ratio_Wstar_W_by_level": {lv: T.L(ws, lv) / T.L(wfp, lv) for lv in band},
            "R_D": [r["R_D"] for r in lr if r["role"] == "seed"],
            "R_D_screen": [r["R_D_screen"] for r in lr if r["role"] == "seed"],
            "l1_ratio_D": [a["l1_ratio"] for d in rec["draws"] for a in d["attempt_log"]],
            "R_D_in_window": sum(r["R_D_in_window"] for r in lr if r["role"] == "seed"),
            "proxy_sensitivity_screen": sens,
            "dcm_alt_draw0": None if alt is None else {
                "fingerprint": alt[0], "same_best_as_frozen": alt[0] == s0["fingerprint"],
                "s_alt": T.L(alt[0], prod) / L_ws - 1.0 if T.has(alt[0], prod) else None, "s_frozen": s0["s"]},
            "tj_K": rec.get("tj_K"), "tj_fallback_due": tj_fallback_due(rec["tj_K"], cfg["frozen"]["tj_fallback_K"])}
    met = metric_values(rows, n_draws)
    out_d: dict[str, Any] = {
        "schema": DEV_ROWS_SCHEMA, "experiment": EID, "sealed": False, "dev_seed": man["dev_seed"],
        "rule": "development seeds and development draws only; nothing here has seen a sealed draw",
        "provenance": {"manifest": str(manifest), "manifest_sha256": hashlib.sha256(Path(manifest).read_bytes())
                       .hexdigest(), "l2dir": str(l2), "code_stamp_l1_and_l2": stamp,
                       "code_stamp_checkout_now": code_stamp(spec),
                       "dev_solve_summary_sha256": hashlib.sha256((l2 / "dev_solve_summary.json").read_bytes())
                       .hexdigest(),
                       "results_used": len(T.cache), "results_sha256": canon_sha(
                           {f"{lv}|{fp}": hashlib.sha256((T.dir / f"em_{lv}_{fp}.json").read_bytes()).hexdigest()
                            for fp, lv in sorted(T.cache)}),
                       "generator": "e011_run.py --dev-rows (T0471)"},
        "levels": {"production": prod, "screen": screen, "band": list(band)},
        "per_layout": per, "metrics": met, "reported": reported(rows, n_draws),
        "recompute_check": recompute_check(spec, rows, met, n_draws),
        "band_bound": band_bound_table(rows, cfg["frozen"]["band_bound"]),
        "rank_stability": rank_stability(T, man, groups, best, prod, screen),
        "joint_oc": joint_oc(rows, n_draws, n_boot, boot_seed, tau={
            lay: float(T.rec(p["Wstar_fingerprint"], prod).get("solver_tol_rel_L_max", 0.0)) for lay, p in per.items()}),
        "oc_lower_bounds": oc_lower_bounds(rows, n_draws),
        "measured_sizing": measured_sizing(l2, man, spec, q_out=float(np.mean(
            [not r["R_D_in_window"] for r in rows if r["counted"] and r["role"] == "seed"]))),
        "measured_sizing_full_load": measured_sizing(l2, man, spec, q_out=float(np.mean(
            [not r["R_D_in_window"] for r in rows if r["counted"] and r["role"] == "seed"])),
            wall_override={"2D_Case_4|lat0.25": 5900.0}),  # lessons 2026-11-09: four at once on the 8-vCPU N2D
        "rows": rows}
    p = Path(out or l2 / "dev_rows.json")
    p.write_text(json.dumps(out_d, indent=1, default=_js))
    return out_d


def band_bound_table(rows: list[dict], bb: dict) -> dict:
    """Per (counted layout, role): median and max b_j over the draws, and whether the frozen bound holds."""
    out: dict[str, Any] = {}
    for lay in sorted({r["layout"] for r in rows if r["counted"]}):
        for role in ("search", "widen", "compact", "seed", "random_screen", "proxy_alone"):
            bs = [float(r["b"]) for r in rows if r["layout"] == lay and r["role"] == role and r["b"] is not None]
            if bs:
                med, mx = float(np.median(bs)), max(bs)
                out[f"{lay}|{role}"] = {"median_b": med, "max_b": mx, "min_b": min(bs), "n": len(bs),
                                        "holds": bool(med <= bb["median_max"] and mx <= bb["max_max"])}
    return out


def rank_stability(T: L2Table, man: dict, groups: dict, best: dict, prod: str, screen: str) -> dict:
    """Review item 3: dev selection (and the sensitivity proxies) at the screen level, the registered rule at the
    production level.  Facts: per layout, the shortlist members solved at both levels; the ratio q = L(prod) / L(screen)
    over every layout solved at both; per group, the relative screen-level gap between the best and the runner-up.
    The best by the production level can differ from the screen-level best only if some member's q is lower than the
    best's by more than that gap (L_prod(m) < L_prod(best) <=> q_m / q_best < L_screen(best) / L_screen(m)); with the
    observed q range the bound on s's selection error is max(0, (max q / min q - 1) - gap).  By construction the
    production-level best has L_sub no higher than the screen-selected member's, so a dev s_j is an upper bound on the
    registered rule's s_j for the same shortlist (min property)."""
    out: dict[str, Any] = {}
    for name in sorted({k[0] for k in groups}):
        fps = sorted({j["fingerprint"] for j in man["jobs"] if j["layout"] == name} |
                     {fp for (lay, _), (fp, _) in best.items() if lay == name})
        q = {fp: T.L(fp, prod) / T.L(fp, screen) for fp in fps if T.has(fp, prod) and T.has(fp, screen)}
        qa = np.array(list(q.values()))
        gs = {k[1]: g for k, g in groups.items() if k[0] == name}
        both = {p: sum(1 for fp, _ in g if fp in q) for p, g in gs.items()}
        gap, bound = {}, {}
        spread = float(qa.max() / qa.min() - 1.0)
        for p, g in gs.items():
            ls = sorted(T.L(fp, screen) for fp, _ in g)
            gap[p] = ls[1] / ls[0] - 1.0 if len(ls) > 1 else math.inf
            bound[p] = max(0.0, spread - gap[p])
        extra = [(fp, p) for p, g in gs.items() for fp, _ in g if fp not in q]
        out[name] = {"n_solved_both_levels": len(q), "q_median": float(np.median(qa)), "q_min": float(qa.min()),
                     "q_max": float(qa.max()), "q_spread_rel": spread, "q_sd_rel": float(qa.std(ddof=1) / qa.mean()),
                     "shortlist_members_solved_at_both": both,
                     "groups_with_two_or_more_at_both": sum(1 for v in both.values() if v >= 2),
                     "screen_gap_best_to_second": gap, "selection_error_bound": bound,
                     "groups_bound_positive": sorted(p for p, v in bound.items() if v > 0),
                     "extra_jobs_for_direct_measure": len({fp for fp, _ in extra}),
                     "extra_jobs_by_group": {p: sum(1 for fp, _ in g if fp not in q) for p, g in gs.items()}}
    return out


def joint_oc(rows: list[dict], n_draws: int, B: int, seed: int, tau: dict | None = None,
             shift: dict | None = None, check_n7: int = 200) -> dict:
    """Joint operating characteristic of A1, A3 and K1 (review item 1, T0462).  Estimand: the probability, over the
    sealed seed (degradation draws, search and screen seeds), that the registered run's verdict is PASS (and A1 met, A3
    met, K1 not firing, INCONCLUSIVE, FAIL), judged as the evaluator judges it (L_sub at the production level), with W*,
    the code and the solver fixed.  It is not P(PASS) against continuum-exact inductance ratios.
    c: s*_kj = (1 + s_kj) / (1 + c) - 1, c_k = L_sub,run(W*_k) / L_sub,dev(W*_k) - 1, the relative difference between the
    registered run's single solve of W*_k and the development solve of the same layout at the same level.  W* is
    deterministic (frozen descent, frozen code), so c_k is zero up to the iterative solve's error: c_k ~ U(-tau_k,
    tau_k), tau_k = that solve's solver_tol_rel_L_max, drawn once per layout per replicate and applied to every role's
    s on the layout (all share the one W* solve).  ``shift`` adds a fixed c_k (a stress sensitivity, not an estimate).
    Method: per layout independently, resample n_draws development draws with replacement, each as its whole tuple
    (search, widen, compact: s, b, capped; paired on D_j), B replicates, seed ``seed``; A1, A3 and K1 per replicate by
    a vectorised form of e011_metrics, checked against e011_metrics on the first ``check_n7`` replicates."""
    rng = np.random.default_rng(seed)
    lays = sorted({r["layout"] for r in rows if r["counted"]})
    roles = ("search",) + N7.GATING_NULLS
    arr: dict[str, dict[str, np.ndarray]] = {}
    for lay in lays:
        d = {}
        for role in roles:
            rr = sorted((r for r in rows if r["layout"] == lay and r["role"] == role), key=lambda r: r["draw"])
            d[role] = np.array([[N7._shortfall(r["s"], ""), float(r["b"]), float(bool(r["capped"]))] for r in rr])
        arr[lay] = d
    nd = {lay: len(arr[lay]["search"]) for lay in lays}
    idx = {lay: rng.integers(0, nd[lay], size=(B, n_draws)) for lay in lays}
    cc = {lay: (rng.uniform(-tau[lay], tau[lay], size=B) if tau and tau.get(lay) else np.zeros(B))
          + (shift or {}).get(lay, 0.0) for lay in lays}
    tol = N7.TOL
    a1 = np.ones(B, bool)
    a3 = np.ones(B, bool)
    k1 = np.zeros(B, bool)
    per_lay: dict[str, Any] = {}
    reps: dict[str, dict[str, np.ndarray]] = {}
    for lay in lays:
        sel = {role: arr[lay][role][idx[lay]] for role in roles}  # (B, n, 3)
        s = {role: (1.0 + sel[role][..., 0]) / (1.0 + cc[lay][:, None]) - 1.0 for role in roles}
        reps[lay] = s
        pa = (s["search"] <= tol).sum(1) >= N7.MIN_PASS
        med = np.median(s["search"], axis=1)
        a1 &= pa
        k1 |= med > 0.05
        beat = {}
        for nu in N7.GATING_NULLS:
            res = ((sel[nu][..., 2] == 0) & (s[nu] - sel[nu][..., 1] > tol)).sum(1) >= N7.MIN_RESOLVED
            pair = ((s[nu] - s["search"]) > (sel["search"][..., 1] + sel[nu][..., 1])).sum(1) >= N7.MIN_PAIRED
            beat[nu] = res & pair
            a3 &= beat[nu]
            per_lay[f"{lay}|{nu}"] = {"P_resolved_ok": float(res.mean()), "P_paired_ok": float(pair.mean()),
                                      "P_beaten": float(beat[nu].mean())}
        per_lay[lay] = {"P_A1_layout": float(pa.mean()), "P_K1_fires_layout": float((med > 0.05).mean())}
    pas = a1 & a3 & ~k1
    mism = 0
    for b in range(min(check_n7, B)):  # the vectorised form against e011_metrics on the same replicate rows
        rr = []
        for lay in lays:
            for jn, jo in enumerate(idx[lay][b]):
                for role in roles:
                    sb, bb, cap = arr[lay][role][jo]
                    rr.append({"layout": lay, "counted": True, "draw": jn, "role": role, "s": float(reps[lay][role][b, jn]),
                               "b": float(bb), "capped": bool(cap),
                               "terminal_kind": "budget" if (cap and role == "search") else ("step_limit" if cap else
                                                                                           "local_optimum"),
                               "in_domain_W": True, "reach_outside": 0.0})
        v1 = N7.control_layout_pass_min(rr, n_draws=n_draws) >= N7.MIN_PASS / N7.N_DRAWS
        v3 = N7.null_beaten_min(rr, n_draws=n_draws) >= 1.0
        vk = N7.control_shortfall_median_max(rr, n_draws=n_draws) > 0.05
        mism += int((v1, v3, vk) != (bool(a1[b]), bool(a3[b]), bool(k1[b])))
    p_draw = {lay: float((arr[lay]["search"][:, 0] <= tol).mean()) for lay in lays}
    return {"estimand": "P over the sealed seed of the registered run's outcome as judged (L_sub at the production "
                        "level), W*, code and solver fixed; not P(PASS) against continuum-exact ratios",
            "c_definition": "c_k = L_sub,run(W*_k) / L_sub,dev(W*_k) - 1 ~ U(-tau_k, tau_k), tau_k = solver_tol_rel_L_max "
                            "of the W* solve" + (f"; plus a fixed shift {shift}" if shift else ""),
            "tau": tau, "B": B, "seed": seed, "n_dev_draws": nd,
            "P_PASS": float(pas.mean()), "P_A1": float(a1.mean()), "P_A3": float(a3.mean()),
            "P_K1_not_fired": float((~k1).mean()), "P_FAIL": float(k1.mean()),
            "P_INCONCLUSIVE": float((~k1 & ~(a1 & a3)).mean()),
            "mc_se_P_PASS": float(np.sqrt(pas.mean() * (1 - pas.mean()) / B)), "per_layout": per_lay,
            "p_draw_pass_hat": p_draw,
            "A1_only_independent_draws_at_p_hat": {lay: N7.a1_operating_characteristic(p) for lay, p in p_draw.items()},
            "n7_check": {"replicates": min(check_n7, B), "mismatches": mism}}


def oc_lower_bounds(rows: list[dict], n_draws: int, level: float = 0.95) -> dict:
    """Per counted layout and event, the one-sided Clopper-Pearson lower bound on the per-draw rate from the development
    draws and the binomial tail it implies (A1: P(Bin(n, p_L) >= 7); resolved: >= 4; paired: >= 7; K1 not firing,
    sufficient: >= 5 draws with s <= 0.05).  These assume draws independent given W*; with 8 development draws they show
    how little a perfect development record certifies.  Also the union (Bonferroni) lower confidence bound on P(PASS)."""
    lays = sorted({r["layout"] for r in rows if r["counted"]})
    ev: dict[str, tuple[int, int]] = {}  # event -> (successes, k needed)
    for lay in lays:
        g = {(r["role"], r["draw"]): r for r in rows if r["layout"] == lay}
        js = sorted({d for (ro, d) in g if ro == "search"})
        ss = [N7._shortfall(g[("search", j)]["s"], "") for j in js]
        ev[f"{lay}|A1"] = (sum(x <= N7.TOL for x in ss), N7.MIN_PASS)
        ev[f"{lay}|K1_not"] = (sum(x <= 0.05 for x in ss), 5)
        for nu in N7.GATING_NULLS:
            ev[f"{lay}|{nu}|resolved"] = (sum(1 for j in js if not g[(nu, j)]["capped"]
                                             and g[(nu, j)]["s"] - g[(nu, j)]["b"] > N7.TOL), N7.MIN_RESOLVED)
            ev[f"{lay}|{nu}|paired"] = (sum(1 for j in js if g[(nu, j)]["s"] - g[("search", j)]["s"]
                                           > g[("search", j)]["b"] + g[(nu, j)]["b"]), N7.MIN_PAIRED)
    from scipy import stats as st
    m = len(ev)
    out: dict[str, Any] = {}
    for lv_name, lev in (("each", level), ("bonferroni", 1.0 - (1.0 - level) / m)):
        tails = {}
        for e, (k, need) in ev.items():
            pl = N7.clopper_pearson_lower(k, n_draws, lev)
            tails[e] = {"k": k, "n": n_draws, "p_L": pl, "P_event_at_p_L": float(st.binom.sf(need - 1, n_draws, pl))}
        out[lv_name] = {"level": lev, "events": tails}
    out["P_PASS_lower_bonferroni"] = max(0.0, 1.0 - sum(1.0 - t["P_event_at_p_L"] for t in out["bonferroni"]["events"]
                                                        .values()))
    out["n_events"] = m
    return out


def measured_sizing(l2: Path, man: dict, spec: dict, q_out: float | None = None,
                    wall_override: dict | None = None) -> dict:
    """Review item 2: per (layout, level) the burst's measured wall, CPU and peak RSS of every l2_layout result (with
    its job file), against E010's model; then the registered run's makespan and cost on VM options, by list scheduling
    (E010.simulate) with the measured walls (p90) and peaks (max x 1.1, the Scheduler's learned admission), the phase
    order of registered_model (layouts one after another; the L1 phase from the dev run's stage walls x MAC_TO_VM_L1).
    gen2_0 has no measurement: E010's model scaled by 2D_Case_2R's measured / model ratio per level (stated)."""
    meas: dict[str, dict] = {}
    for p in sorted((Path(l2) / "solves").glob("em_*.job.json")):
        jb = json.loads(p.read_text())
        rp = p.with_name(p.name.replace(".job.json", ".json"))
        if not rp.exists():
            continue
        r = json.loads(rp.read_text())
        if "wall_s" not in r or "peak_GB" not in r or "est_s" not in jb:
            continue  # fake results (selftest) carry no measurement
        e = meas.setdefault(f"{jb['ref']}|{jb['level']}", {"wall": [], "cpu": [], "peak": [], "est": [], "model_GB": []})
        e["wall"].append(float(r["wall_s"]))
        e["cpu"].append(float(r.get("cpu_s", math.nan)))
        e["peak"].append(float(r["peak_GB"]))
        e["est"].append(float(jb["est_s"]))
        e["model_GB"].append(float(jb["mem_model_GB"]))
    if not meas:
        return {}
    per = {}
    for k, e in meas.items():
        w = np.array(e["wall"])
        per[k] = {"n": len(w), "wall_s_median": float(np.median(w)), "wall_s_p90": float(np.percentile(w, 90)),
                  "wall_s_max": float(w.max()), "cpu_over_wall_median": float(np.nanmedian(np.array(e["cpu"]) / w)),
                  "peak_GB_median": float(np.median(e["peak"])), "peak_GB_max": float(max(e["peak"])),
                  "model_wall_s": float(np.median(e["est"])), "model_GB": float(np.median(e["model_GB"])),
                  "wall_over_model": float(np.median(w) / np.median(e["est"])),
                  "peak_over_model": float(max(e["peak"]) / np.median(e["model_GB"]))}
    c10 = cfg10()
    cm, vm = c10["compute"]["cost_model"], c10["compute"]["vm"]
    reg = man["vm_sizing"]["registered_run"]["solves"]

    def cost(name: str, lv: str) -> tuple[float, float]:
        k = f"{name}|{lv}"
        if wall_override and k in wall_override:
            return float(wall_override[k]), per[k]["peak_GB_max"] * 1.1
        if k in per:
            return per[k]["wall_s_p90"], per[k]["peak_GB_max"] * 1.1
        ref = per.get(f"2D_Case_2R|{lv}")  # gen2_0: E010's model on its unknowns x 2R's measured / model ratio
        n = int(reg[name]["unknowns"][lv])
        t, m = E.em_cost(n, lv, cm)
        return t * ref["wall_over_model"], m * ref["peak_over_model"] * 1.1

    def sim(vcpus: int, cap: float, q: float) -> float:
        """q: per-attempt probability that R_D falls outside the window; redraw wave w solves ceil(n q^w) attempts
        (q = 1: every draw redrawn in every wave, the upper bound)."""
        jobs, prev = [], None
        for name, m in reg.items():
            if "omitted" in m:
                continue
            phases = [("P", m["P"]), ("D", m["D_wave0"])]
            for w in range(1, int(m["redraw_waves_max"]) + 1):
                cw = {lv: math.ceil(c * q ** w - 1e-9) for lv, c in m["D_wave0"].items()}
                if sum(cw.values()):
                    phases.append((f"D{w}", cw))
            phases += [("L1", None), ("S1", m["S1"]), ("S2", m["S2"])]
            for ph, counts in phases:
                g = f"{name}|{ph}"
                if counts is None:
                    h = m["L1_wall_h_mac"] or 1.0
                    jobs.append({"name": g, "group": g, "after": [prev] if prev else [], "est_s": h * 3600 * MAC_TO_VM_L1,
                                 "threads": 1, "mem_GB": 0.0})
                else:
                    for lv, c in counts.items():
                        t, mm = cost(name, lv)
                        jobs += [{"name": f"{g}|{lv}|{i}", "group": g, "after": [prev] if prev else [], "est_s": t,
                                  "threads": 2, "mem_GB": mm} for i in range(int(c))]
                prev = g
        return E.simulate(jobs, vcpus, cap) / 3600

    opts = {"A: n2d-custom-8-81920-ext (current shape)": (8, 78.0, float(vm["usd_per_h"])),
            "B: n2d-custom-8-98304-ext (+16 GB extended memory)": (8, 94.0, float(vm["usd_per_h"]) + 16 * float(
                vm["ext_usd_per_GB_h"])),
            "C: n2d-custom-16-163840-ext (all 16 vCPUs; only when no other burst runs)": (16, 158.0,
                                                                                            2 * float(vm["usd_per_h"]))}
    res = {}
    for oname, (vc, ram, usd) in opts.items():
        cap = float(vm["memory_fraction"]) * ram
        r = {"vcpus": vc, "ram_GB": ram, "usable_GB": round(cap, 1), "usd_per_h": round(usd, 3)}
        for scen, q in (("no_redraws", 0.0), ("max_redraws", 1.0)) + (
                (("measured_out_of_window_rate", float(q_out)),) if q_out else ()):
            mk = sim(vc, cap, q)
            r[scen] = {"makespan_h": round(mk, 1), "vm_h": round(mk + float(vm["overhead_h"]), 1),
                       "usd": round((mk + float(vm["overhead_h"])) * usd, 1),
                       "billed_vcpu_h": round((mk + float(vm["overhead_h"])) * vc, 0)}
        res[oname] = r
    cpu_h = 0.0  # process CPU-hours of the registered run's solves (no redraws): count x wall x measured cpu / wall
    for name, m in reg.items():
        if "omitted" in m:
            continue
        cnt: dict[str, int] = {}
        for ph in ("P", "D_wave0", "S1", "S2"):
            for lv, c in m[ph].items():
                cnt[lv] = cnt.get(lv, 0) + int(c)
        for lv, c in cnt.items():
            k = f"{name}|{lv}" if f"{name}|{lv}" in per else f"2D_Case_2R|{lv}"
            cpu_h += c * cost(name, lv)[0] * per[k]["cpu_over_wall_median"] / 3600
        cpu_h += (m["L1_wall_h_mac"] or 1.0) * MAC_TO_VM_L1
    return {"per_layout_level": per, "registered_solves": reg, "options": res, "cpu_hours_no_redraws": round(cpu_h, 1),
            "wall_override": wall_override,
            "basis": measured_sizing.__doc__.split("\n")[0] + " (measured_sizing)",
            "redraw_model": "wave w solves ceil(n_draws q^w) attempts, q per attempt; q_out = the development draws' "
                            "out-of-window fraction at the production level", "q_out": q_out,
            "pricing_basis": vm.get("pricing_note"), "vm_config": {k: vm[k] for k in ("machine", "usd_per_h",
                                                                                     "ext_usd_per_GB_h", "overhead_h")}}


def full(workdir: str | None) -> int:
    from mfos.evidence import ExperimentRun
    spec = load_spec()
    wd = Path(workdir or os.environ.get("E011_WORKDIR") or Path(os.environ.get("MFOS_RUN_DIR", ".")) / "work")
    with ExperimentRun(experiment_id=EID) as er:
        if er.seed is None:
            raise RuntimeError("no sealed seed (MFOS_SEED)")
        rx = make_ctx(spec, "full", wd, int(er.seed))
        try:
            recs = run_all(rx, [(n, n in spec["config"]["counted_layouts"]) for n in spec["config"]["layouts"]])
        except E.NeedsLargerMachine as e:
            print(json.dumps(E.phase_stop(e, wd, cfg10()["compute"]["vm"])))
            sys.exit(E.PHASE_B_EXIT)
        er.domain(layouts=[r["layout"] for r in recs], freq_hz=[float(spec["config"]["levels"]["freq_hz"])],
                  movable=["Params.NAMES[4:40]"])
        v, _, _ = finish(er, rx, recs, spec)
        er.notes = f"runner verdict preview {v} (the evaluator decides)"
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--selftest", action="store_true")
    g.add_argument("--smoke", action="store_true")
    g.add_argument("--dev", action="store_true")
    g.add_argument("--dev-solve", metavar="MANIFEST")
    g.add_argument("--child", metavar="JOB")
    g.add_argument("--freeze-report", action="store_true")
    g.add_argument("--dev-rows", metavar="MANIFEST", help="T0471: development rows from the burst's L2 results in "
                   "--workdir (default research/o008_e011_dev/dev_l2); no solve")
    ap.add_argument("--out", help="with --dev-rows: output path (default <workdir>/dev_rows.json)")
    ap.add_argument("--workdir")
    ap.add_argument("--dry-run", action="store_true", help="with --dev-solve: check every job would be submitted, solve none")
    a = ap.parse_args(argv)
    if a.child:
        return E.child_main(a.child)
    if a.selftest:
        return selftest()
    if a.smoke:
        return smoke()
    if a.dev:
        return dev(a.workdir)
    if a.dev_solve:
        return dev_solve(a.dev_solve, a.workdir, dry=a.dry_run)
    if a.dev_rows:
        d = dev_rows(a.dev_rows, a.workdir or str(DEV_L2), a.out)
        print(json.dumps({"metrics": {k: m["value"] for k, m in d["metrics"].items()},
                          "joint_oc": {k: v for k, v in d["joint_oc"].items() if k.startswith("P_")},
                          "recompute_check": d["recompute_check"], "rows": len(d["rows"])}, default=_js))
        return 0 if not d["recompute_check"] else 3
    if a.freeze_report:
        print(json.dumps(freeze_report(yaml.safe_load(DRAFT.read_text())["config"]), indent=1))
        return 0
    return full(a.workdir)


if __name__ == "__main__":
    sys.exit(main())
