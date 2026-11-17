"""E004 (O004): l2_layout 0.25 mm against the pinned FastHenry on the ratios of re-layouts of PowerSynth 2D_Case_2R and
2D_Case_6.  Part 1 (T0388): the registration stage.  Part 2 (T0389): the solve stage, estimators, metrics, INVALID rules.

Stages
  registration  (before any solve; F2, F4, F5) in this order:
      1. freeze: the frozen T0263 reconstruction script's sha256, then every file hash of config.freeze (which must cover
         every moduleforge source file the stage loads, reviews T0440/T0441), perturb.rules_sha256(), this runner's
         supplementary rules hash (rules_supplement_sha256, T0416 item 1), l2_layout.source_sha256(), the numpy / scipy /
         shapely versions, and the pinned commit (an ancestor of HEAD, whose blobs carry the frozen file hashes);
      2. the judged references rebuilt by the frozen script, fingerprints checked (a sanity check that depends on no solve);
         no PowerSynth file is read or present in the tree (D0007, F5);
      3. each reference's coordinates whole mm (T0416 item 3) and each reference on the 1.0 / 0.5 / 0.25 mm lattices,
         both gated BEFORE any draw; a reference whose measured rules raise refuses with the cause;
      4. pairs drawn by perturb.draw from the seed (registered: E004's sealed seed, run.seed, only; smoke / dev: a
         development seed, nothing drawn from the sealed seed) with the frozen allocation; a draw that raises refuses and
         names the net; the draws are then replayed from the seed read independently (MFOS_SEED or DEV_SEED) and must
         reproduce every pair's parameters and fingerprint (seed_provenance);
      5. the 2D_Case_2R designer-proxy pair (I0207: proxy descent in 1 mm steps; ratio against the frozen reconstruction):
         registered mode refuses without it; smoke records it as pending with the reason;
      6. registration checks (F4) on L1 (physics.peec, not the tool under test): >= 2 references, >= 6 pairs per reference,
         each of the four single move types on each reference, every layout on the three lattices, every layout and every
         compound intermediate DRC-clean (stagewise rule, D0024 item 4) and distinct, the pooled L1 span; the coverage
         rule reported per move type; L1 at config.l1.hmax_m (the gate) and at hmax_check_m (reported), with every value
         near a threshold flagged (review T0441); finally, every moduleforge source file loaded is frozen.
  solve         a stub (T0389).

Modes
  (no flag)                    registered: `mfos exp run E004` sets MFOS_SEED (sealed), MFOS_SPEC_JSON, MFOS_RUN_DIR.
                               A failed registration check raises RegistrationRefused before any solve (run status error).
  --smoke --stage registration the whole registration stage on a development seed with L1 only, on development geometry:
                               2D_Case_4 stands in for both judged slots (F2: no draw, long_sides or L1 on 2D_Case_2R or
                               2D_Case_6; their fingerprints are checked).  Checks are recorded, never raised; exit 0.
  --dev-span-sim N             research only (not evidence): the registration span check on 2D_Case_4 with the frozen
                               allocation on N development seeds, checkpointed to --out (resumes).
  --print-freeze               print the freeze values of the current tree (the act of freezing; not evidence).

Units: SI internally (H, Hz, m); perturbation parameters in whole mm (perturb's convention).
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import inspect
import json
import math
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
EID = "E004"
SPEC_DRAFT = ROOT / "experiments" / "drafts" / f"{EID}.yaml"
OBJECTIVE = ROOT / "project" / "objectives" / "O004" / "objective.yaml"
RECON_SCRIPT = "research/scripts/o003_powersynth_references.py"  # frozen T0263 script (D0019), imported by path, never edited
CASE4_SCRIPT = "research/scripts/o006_case4_layout.py"  # development geometry only (O006 F4, O004 F2)
DEV_SEED = 20261117  # development seed for smoke / dev modes; never E004's sealed seed, never used for judgement
FREQS_HZ = (10e6, 20e6)
FK = ("10MHz", "20MHz")
LATTICES_M = (1.0e-3, 0.5e-3, 0.25e-3)
MM = 1e-3
WHOLE_MM_TOL_M = 1e-9
# E008.yaml dev.case4.rule_overrides (= tests/unit/test_perturb.py CASE4_OVERRIDES, research/o004_f7/pilot_l2.py): dev only,
# never applied to a judged reference (perturb.measured_rules docstring)
CASE4_OVERRIDES = {"min_wire_pitch": 0.6e-3, "wire_pitch_diameters": 2.0, "max_wire_length": 0.018}
# Every module the registration and solve stages import.  The freeze must hash every moduleforge source file these load
# (reviews T0440 / T0441: kernels.py, conductors.py, units.py and the package __init__ files were missed by attempt 1).
FREEZE_IMPORTS = ("moduleforge.generate.perturb", "moduleforge.physics.peec.model", "moduleforge.drc",
                  "moduleforge.solvers.l2_layout", "moduleforge.solvers.fasthenry", "moduleforge.solvers.fasthenry_run",
                  "moduleforge.optimize.control", "moduleforge.optimize.local", "moduleforge.geometry.snap")
FREEZE_PACKAGES = ("numpy", "scipy", "shapely")


class RegistrationRefused(RuntimeError):
    """A registration check failed (F2 / F4 / F5): the design is refused before any solve."""


# ------------------------------------------------------------------------------------------------- the span (one place)
_SPAN_RE = re.compile(r"must span at least \[(?P<lo>[0-9.]+), (?P<hi>[0-9.]+)\] with at least (?P<n>\d+) below "
                      r"(?P<below>[0-9.]+)")


def objective_span() -> dict:
    """O004 scope_in's registration span, read from the objective's text (the only place the runner takes it from; a founder
    amendment of that sentence changes it, and the spec's config.span assertion must then be changed to match)."""
    import yaml
    obj = yaml.safe_load(OBJECTIVE.read_text())
    text = " ".join(" ".join(obj["scope_in"]).split())
    m = _SPAN_RE.search(text)
    if not m:
        raise RegistrationRefused("O004 scope_in has no 'must span at least [lo, hi] with at least n below x' sentence")
    return {"lower_end": float(m["lo"]), "upper_end": float(m["hi"]), "n_below": int(m["n"]), "below": float(m["below"])}


SPAN = objective_span()
SPAN_LOWER_END = SPAN["lower_end"]  # the span's lower end: O004's frozen 0.75 until the founder amends the objective


# --------------------------------------------------------------------------------------------------------------- config
def spec_config(run_config: dict) -> dict:
    """The spec's config: from MFOS_SPEC_JSON when `mfos exp run` sets it, else the draft (smoke / dev)."""
    if run_config:
        return run_config
    import yaml
    return yaml.safe_load(SPEC_DRAFT.read_text())["config"]


def sha256_file(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _load(name: str, rel: str):
    if name in sys.modules:
        return sys.modules[name]
    sp = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(sp)
    sys.modules[name] = mod
    sp.loader.exec_module(mod)
    return mod


# --------------------------------------------------------------------------------------------------------------- freeze
def rules_supplement_sha256() -> str:
    """T0416 item 1, measured here because src/ is outside this task's scope: the inputs that decide which layouts a seed
    yields but that perturb.rules_sha256() does not cover (NETS, whose order the rng indexes; SIGNAL_NET; SIGNAL_PADS; the
    sources of Die.bounds / Die.box, BondWire.length and SignalWire.length).  Frozen in config.freeze beside it."""
    from moduleforge.geometry import layout as G

    def src(prop):
        return inspect.getsource(getattr(prop, "fget", prop))
    parts = [("NETS", json.dumps(list(G.NETS))),
             ("SIGNAL_NET", json.dumps(sorted([list(k), v] for k, v in G.SIGNAL_NET.items()))),
             ("SIGNAL_PADS", json.dumps(list(G.SIGNAL_PADS))),
             ("Die.bounds", src(G.Die.bounds)), ("Die.box", src(G.Die.box)),
             ("BondWire.length", src(G.BondWire.length)), ("SignalWire.length", src(G.SignalWire.length))]
    h = hashlib.sha256()
    for name, text in parts:
        h.update(f"{name}\n{len(text)}\n".encode())
        h.update(text.encode())
    return h.hexdigest()


def moduleforge_sources() -> dict[str, str]:
    """{repo-relative path: sha256} of every moduleforge source file loaded in this process now (sys.modules)."""
    out = {}
    for name, m in list(sys.modules.items()):
        if (name == "moduleforge" or name.startswith("moduleforge.")) and getattr(m, "__file__", None):
            rel = Path(m.__file__).resolve().relative_to(ROOT).as_posix()
            out[rel] = sha256_file(ROOT / rel)
    return dict(sorted(out.items()))


def unfrozen_sources(fz: dict) -> list[str]:
    """Loaded moduleforge files missing from config.freeze.files: a change to one would pass every freeze check (F2)."""
    return [f"{rel} is loaded but not in config.freeze.files" for rel in moduleforge_sources() if rel not in fz["files"]]


def live_freeze() -> dict:
    """The live identities config.freeze pins, after importing FREEZE_IMPORTS (no layout is built, no draw, no solve)."""
    for name in FREEZE_IMPORTS:
        importlib.import_module(name)
    from moduleforge.generate import perturb as P
    from moduleforge.solvers import l2_layout as L2
    return {"perturb_rules_sha256": P.rules_sha256(), "perturb_rules_supplement_sha256": rules_supplement_sha256(),
            "l2_layout_source_sha256": L2.source_sha256(),
            "packages": {k: importlib.import_module(k).__version__ for k in FREEZE_PACKAGES}}


def blob_sha256(commit: str, rel: str) -> str:
    """sha256 of ``rel`` as committed at ``commit`` ('missing' if absent)."""
    r = subprocess.run(["git", "show", f"{commit}:{rel}"], cwd=ROOT, capture_output=True)
    return hashlib.sha256(r.stdout).hexdigest() if r.returncode == 0 else "missing"


def freeze_record(cfg: dict) -> dict:
    """Every frozen identity, recomputed now, and the failures against config.freeze (F2).  The reconstruction script's
    sha256 is checked first; nothing is imported from it before that."""
    fz = cfg["freeze"]
    out: dict = {"failures": [], "values": {}}
    recon_h = sha256_file(ROOT / RECON_SCRIPT)
    out["values"]["reconstruction_script_sha256"] = recon_h
    if recon_h != fz["reconstruction_script_sha256"]:
        out["failures"].append(f"{RECON_SCRIPT} sha256 {recon_h} != frozen {fz['reconstruction_script_sha256']}")
        return out  # nothing else is loaded once the reconstruction script differs
    live = live_freeze()
    for k in ("perturb_rules_sha256", "perturb_rules_supplement_sha256", "l2_layout_source_sha256", "packages"):
        out["values"][k] = live[k]
        if live[k] != fz[k]:
            out["failures"].append(f"{k} {live[k]} != frozen {fz[k]}")
    for rel, want in fz["files"].items():
        got = sha256_file(ROOT / rel) if (ROOT / rel).exists() else "missing"
        out["values"][rel] = got
        if got != want:
            out["failures"].append(f"{rel} sha256 {got} != frozen {want}")
    out["failures"] += unfrozen_sources(fz)
    anc = subprocess.run(["git", "merge-base", "--is-ancestor", fz["commit"], "HEAD"], cwd=ROOT, capture_output=True)
    out["values"]["head"] = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                                           text=True).stdout.strip()
    if anc.returncode != 0:
        out["failures"].append(f"pinned commit {fz['commit']} is not an ancestor of HEAD")
    for rel in [RECON_SCRIPT, *fz["files"]]:  # the hashes were taken at the pinned commit
        want = fz["reconstruction_script_sha256"] if rel == RECON_SCRIPT else fz["files"][rel]
        if blob_sha256(fz["commit"], rel) != want:
            out["failures"].append(f"{rel} at the pinned commit {fz['commit'][:12]} does not have the frozen sha256")
    sp = cfg["span"]
    if (sp["lower_end"], sp["upper_end"], sp["n_below"], sp["below"]) != (SPAN["lower_end"], SPAN["upper_end"],
                                                                          SPAN["n_below"], SPAN["below"]):
        out["failures"].append(f"config.span {sp} differs from O004's text {SPAN}")
    return out


def print_freeze() -> dict:
    """The freeze block of the current tree: the act of freezing (paste into config.freeze), not evidence.  Imports the
    stage's modules and the reconstruction script and rebuilds the judged references (geometry only: no draw, no
    long_sides, no inductance, F2), so the files list covers what those load."""
    import yaml
    cfg = yaml.safe_load(SPEC_DRAFT.read_text())["config"]
    live = live_freeze()
    recon = recon_module()
    for e in cfg["references"]:
        recon.snapped(e["reference_id"])
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    return {"head": head, "reconstruction_script_sha256": sha256_file(ROOT / RECON_SCRIPT), **live,
            "files": moduleforge_sources()}


# ----------------------------------------------------------------------------------------------------------- references
def recon_module():
    return _load("o003_powersynth_references_e004", RECON_SCRIPT)


def judged_references(cfg: dict) -> tuple[dict, list[str]]:
    """{reference_id: Layout} rebuilt by the frozen script's snapped() (as E010's rebuild_reconstruction), and failures:
    a fingerprint different from config.references[*].reconstruction_fingerprint refuses (F2).  Geometry only."""
    recon = recon_module()
    out, bad = {}, []
    for e in cfg["references"]:
        lay, _snaps = recon.snapped(e["reference_id"])
        fp = lay.fingerprint()
        if fp != e["reconstruction_fingerprint"]:
            bad.append(f"{e['reference_id']}: fingerprint {fp} != frozen {e['reconstruction_fingerprint']}")
        out[e["reference_id"]] = lay
    return out, bad


def gpl_files_in_tree() -> list[str]:
    """D0007 / F5: tracked files whose name is one of the PowerSynth sample files the T0263 script read (FORBIDDEN_NAMES)."""
    names = set(recon_module().FORBIDDEN_NAMES)
    ls = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.split()
    return sorted(p for p in ls if Path(p).name in names)


def case4_reference():
    """2D_Case_4 (development geometry) and its rules with E008's dev overrides."""
    from moduleforge.generate import perturb as P
    ref = _load("o006_case4_layout_e004", CASE4_SCRIPT).build("base")
    return ref, P.measured_rules(ref, CASE4_OVERRIDES)


def _whole(v: float) -> bool:
    return abs(v / MM - round(v / MM)) * MM <= WHOLE_MM_TOL_M


def whole_mm_failures(lay) -> list[str]:
    """T0416 item 3: the coordinates perturb's whole-mm construction rounds (``perturb._mm``) must be whole mm on the
    reference, or a move would shift them by the rounding: trace vertices (long_sides, trace_width strips), die bounds
    (die_row_shift's host-copper growth) and terminal boxes (terminal_copper windows).  Pads and wire end points are moved
    by exact whole-mm offsets, never rounded, so they are not required to be whole mm."""
    bad = []
    for t in lay.traces:
        if not all(_whole(x) and _whole(y) for x, y in t.polygon.exterior.coords):
            bad.append(f"trace {t.net}")
    for k, d in enumerate(lay.dies):
        if not all(_whole(c) for c in d.bounds):
            bad.append(f"die {k}")
    for n, t in lay.terminals.items():
        if not all(_whole(c) for c in (t.cx - t.w / 2, t.cy - t.h / 2, t.cx + t.w / 2, t.cy + t.h / 2)):
            bad.append(f"terminal {n}")
    return bad


# ---------------------------------------------------------------------------------------------------------------- draws
def reference_seed(seed: int, slot: int) -> int:
    """The draw seed of reference slot ``slot`` (config.references order): SeedSequence(seed, spawn_key=(slot,)), so the two
    references' draws are independent streams of one seed."""
    return int(np.random.SeedSequence(entropy=int(seed), spawn_key=(int(slot),)).generate_state(1, dtype=np.uint64)[0])


def both_sided_nets(lay) -> list[str]:
    """Nets whose long-side scan raises 'edge has copper on both sides' (T0387): named when a draw on a reference raises."""
    from moduleforge.generate import perturb as P
    from moduleforge.geometry import NETS
    out = []
    for n in NETS:
        try:
            P.long_sides(P._net_poly(lay, n))
        except ValueError as e:
            out.append(f"{n} ({e})")
    return out


def draw_pairs(rid: str, ref, rules, allocation: dict, seed: int) -> list:
    """perturb.draw on one reference; a draw that raises refuses the design and names the net (T0387)."""
    from moduleforge.generate import perturb as P
    try:
        return P.draw(ref, allocation, seed, rules)
    except ValueError as e:
        nets = both_sided_nets(ref) if "both sides" in str(e) else []
        raise RegistrationRefused(f"{rid}: perturb.draw raised ValueError({e}); nets with a both-sided long side: "
                                  f"{nets or 'none found'}") from e
    except RuntimeError as e:
        raise RegistrationRefused(f"{rid}: perturb.draw raised RuntimeError({e})") from e


def l1_H(lay, hmax_m: float) -> list[float]:
    """L1 loop inductance (H) at FREQS_HZ: moduleforge.physics.peec loop_inductance at mesh size ``hmax_m`` (the fast
    model, not under test; config.l1 fixes the gate's mesh)."""
    from moduleforge.physics.peec import model as peec
    return [float(v) for v in peec.loop_inductance(lay, list(FREQS_HZ), hmax=float(hmax_m)).L_H]


def pair_records(rid: str, slot: int, ref, rules, moves, l1cfg: dict, with_geometry_checks: bool = True) -> list[dict]:
    """One record per drawn pair: kind, components, fingerprint, L1 and r_L1 per frequency at config.l1.hmax_m and (with
    the geometry checks) at hmax_check_m, and the re-checks on the materialised layout: DRC under the reference's rules
    of the final layout and of every compound intermediate (stagewise rule, D0024 item 4), each step changing the
    geometry, the stepwise result equal to perturb.apply's, distinct geometry, the three lattices.  The DRC re-check is
    the same drc.check the draw used, run again on the materialised geometry; it is not an independent DRC."""
    from moduleforge.drc import check
    from moduleforge.generate import perturb as P
    h, h2 = l1cfg["hmax_m"], l1cfg["hmax_check_m"]
    l_ref = l1_H(ref, h)
    l_ref2 = l1_H(ref, h2) if with_geometry_checks else None
    keys = {P.geometry_key(ref)}
    out = []
    for i, mv in enumerate(moves):
        lay = P.apply(ref, mv.move_type, mv.params)
        lv = l1_H(lay, h)
        rec = {"reference": rid, "slot": slot, "pair": f"{rid}#{i}", "kind": mv.move_type,
               "components": [t for t, _ in P.components(mv.move_type, mv.params)], "params": mv.params,
               "fingerprint": lay.fingerprint(), **{f"L1_ref_H_{k}": v for k, v in zip(FK, l_ref, strict=True)},
               **{f"L1_H_{k}": v for k, v in zip(FK, lv, strict=True)},
               **{f"r_L1_{k}": v / r for k, v, r in zip(FK, lv, l_ref, strict=True)}}
        if with_geometry_checks:
            lv2 = l1_H(lay, h2)
            rec.update({f"r_L1_check_{k}": v / r for k, v, r in zip(FK, lv2, l_ref2, strict=True)})
            cur, steps = ref, []
            for t, q in P.components(mv.move_type, mv.params):
                nxt = P.apply(cur, t, q)
                steps.append({"move_type": t, "drc_violations": [v.rule for v in check(nxt, rules)],
                              "changes_geometry": P.geometry_key(nxt) != P.geometry_key(cur)})
                cur = nxt
            gk = P.geometry_key(lay)
            rec["steps"] = steps
            rec["stepwise_equals_apply"] = P.geometry_key(cur) == gk
            rec["drc_violations"] = [v.rule for v in check(lay, rules)]
            rec["distinct"] = gk not in keys
            keys.add(gk)
            rec["on_lattice"] = {f"{c / MM:g}mm": P.on_lattice(lay, c) for c in LATTICES_M}
        out.append(rec)
    return out


def replay_mismatches(slots: list, alloc: dict, source_seed: int, drawn: dict) -> list[str]:
    """seed_provenance: the draws replayed from ``source_seed`` (read independently of the seed the stage drew with:
    MFOS_SEED in registered mode, DEV_SEED in smoke) must reproduce every slot's moves and their geometry exactly."""
    from moduleforge.generate import perturb as P
    bad = []
    for slot, (rid, lay, rules) in enumerate(slots):
        if rid not in drawn:
            continue
        try:
            again = P.draw(lay, alloc, reference_seed(source_seed, slot), rules)
        except (ValueError, RuntimeError) as e:
            bad.append(f"{rid}: replay raised {e!r}")
            continue
        a = [(m.move_type, json.dumps(m.params, sort_keys=True)) for m in drawn[rid]]
        b = [(m.move_type, json.dumps(m.params, sort_keys=True)) for m in again]
        if a != b:
            bad.append(f"{rid}: replayed moves differ from the drawn ones")
        elif any(P.geometry_key(P.apply(lay, m.move_type, m.params)) != P.geometry_key(P.apply(lay, n.move_type, n.params))
                 for m, n in zip(drawn[rid], again, strict=True)):
            bad.append(f"{rid}: replayed geometry differs")
    return bad


# ---------------------------------------------------------------------------------------------------------------- proxy
def proxy_pair_status() -> dict:
    """I0207: the 2D_Case_2R proxy pair is O008's proxy descent from the twin in 1 mm steps (on the 1 mm lattice by
    construction), its ratio against the frozen 2R reconstruction.  The step must be a parameter of O008's implementation
    (not a copy of its code).  Until optimize.control.proxy_descent exposes it, the pair is pending."""
    try:
        from moduleforge.optimize import control
    except ImportError as e:
        return {"status": "pending", "reason": f"moduleforge.optimize.control not importable ({e})"}
    params = inspect.signature(control.proxy_descent).parameters
    if "step_mm" not in params:
        return {"status": "pending", "reason": "optimize.control.proxy_descent fixes step_mm = 0.5 (it passes step_mm=0.5 "
                "to local.descend) and exposes no step parameter; I0207 needs the descent in 1 mm steps through a step "
                "parameter of O008's implementation (a src change outside T0388's scope). The pair's build is wired once "
                "that parameter exists; registered mode refuses until then"}
    return {"status": "pending", "reason": "proxy_descent exposes step_mm, but this runner does not yet build the pair "
            "(twin of 2D_Case_2R -> 1 mm descent -> pair against the frozen reconstruction): to be wired before "
            "registration, and the proxy rule's sources re-frozen in config.freeze"}


# --------------------------------------------------------------------------------------------------- registration checks
def span_check(ratios: list[float], span: dict, lower_end: float | None = None) -> dict:
    """O004 scope_in / F4 on L1 ratios: min <= lower end, max >= upper end, at least n_below strictly below ``below``."""
    lo = span["lower_end"] if lower_end is None else lower_end
    r = [float(x) for x in ratios]
    n_b = sum(x < span["below"] for x in r)
    ok_lo, ok_hi, ok_n = min(r) <= lo, max(r) >= span["upper_end"], n_b >= span["n_below"]
    return {"passed": bool(ok_lo and ok_hi and ok_n), "min": min(r), "max": max(r), "n_below": n_b,
            "lower_end": lo, "reaches_lower": ok_lo, "reaches_upper": ok_hi, "enough_below": ok_n}


def registration_checks(cfg: dict, pairs: list[dict], ref_ids: list[str], ref_lattice: dict, proxy: dict,
                        proxy_slot: str) -> dict:
    """F4 checks (name -> dict(passed, value, threshold, detail)), all on L0 geometry and L1 values.  ``proxy_slot`` is
    the slot id of the proxy's reference (in smoke a development stand-in's id, review T0441)."""
    from moduleforge.generate import perturb as P
    c: dict = {}
    n_ref = len(ref_ids)
    c["n_references"] = dict(passed=n_ref >= cfg["min_references"], value=n_ref, threshold=cfg["min_references"],
                             detail=f"references {ref_ids}")
    per = {r: [p for p in pairs if p["reference"] == r] for r in ref_ids}
    if proxy.get("status") == "built":
        per[proxy_slot].append(proxy["record"])
    n_min = min((len(v) for v in per.values()), default=0)
    c["pairs_per_reference"] = dict(passed=n_min >= cfg["min_pairs_per_reference"], value=n_min,
                                    threshold=cfg["min_pairs_per_reference"],
                                    detail=json.dumps({r: len(v) for r, v in per.items()}))
    missing = {r: [t for t in P.MOVE_TYPES if not any(p["kind"] == t for p in v)] for r, v in per.items()}
    missing = {r: v for r, v in missing.items() if v}
    c["move_type_per_reference"] = dict(passed=not missing, value=sum(len(v) for v in missing.values()), threshold=0,
                                        detail=f"single move types missing per reference: {missing}" if missing else
                                        "each single move type on each reference (compounds not counted, I0217)")
    off = [p["pair"] for p in pairs if not all(p["on_lattice"].values())]
    off += [f"{r} (reference)" for r, ok in ref_lattice.items() if not all(ok.values())]
    c["layouts_on_lattice"] = dict(passed=not off, value=len(off), threshold=0,
                                   detail=f"off a lattice of {[f'{x / MM:g} mm' for x in LATTICES_M]}: {off}")
    dirty = [p["pair"] for p in pairs if p["drc_violations"] or not p["distinct"] or not p["stepwise_equals_apply"]
             or any(st["drc_violations"] or not st["changes_geometry"] for st in p["steps"])]
    c["layouts_drc_clean_distinct"] = dict(passed=not dirty, value=len(dirty), threshold=0,
                                           detail=f"a step or the final layout not DRC-clean, a step not changing the "
                                                  f"geometry, or a repeated geometry: {dirty}" if dirty else
                                                  "every final layout and every compound step DRC-clean (stagewise "
                                                  "rule), every step changes the geometry, all distinct")
    ratios = {k: [p[f"r_L1_{k}"] for p in pairs] + ([proxy["record"][f"r_L1_{k}"]] if proxy.get("status") == "built"
                                                     else []) for k in FK}
    sc = {k: span_check(v, SPAN) for k, v in ratios.items()}
    c["l1_span"] = dict(passed=all(s["passed"] for s in sc.values()), value=min(s["min"] for s in sc.values()),
                        threshold=SPAN_LOWER_END, detail=json.dumps({"pooled_over": "every registered pair of every "
                                                                     "reference (proxy included once built)", **sc}))
    c["proxy_pair_built"] = dict(passed=proxy.get("status") == "built", value=None, threshold=None,
                                 detail=f"{cfg['proxy']['reference']} designer-proxy pair: {proxy.get('status')}: "
                                        f"{proxy.get('reason', '')}")
    return c


def coverage(pairs: list[dict], ref_ids: list[str], min_effect: float) -> dict:
    """Coverage rule (review T0366), reported, not a check: per move type, whether a single pair of that type has
    |1 - r_L1| >= min_effect at both frequencies, pooled and per reference; compounds containing the type listed apart."""
    from moduleforge.generate import perturb as P

    def big(p):
        return all(abs(1.0 - p[f"r_L1_{k}"]) >= min_effect for k in FK)
    out = {}
    for t in P.MOVE_TYPES:
        singles = [p for p in pairs if p["kind"] == t]
        comps = [p for p in pairs if p["kind"] == P.COMPOUND and t in p["components"]]
        out[t] = {"covered": any(big(p) for p in singles),
                  "per_reference": {r: any(big(p) for p in singles if p["reference"] == r) for r in ref_ids},
                  "singles_max_effect": max((min(abs(1 - p[f"r_L1_{k}"]) for k in FK) for p in singles), default=None),
                  "compounds_with_type_covered": any(big(p) for p in comps)}
    return out


def l1_mesh_report(pairs: list[dict], span: dict, min_effect: float, tol: float) -> dict:
    """Review T0441, reported, not a check: the F4 gates and the coverage rule are decided on L1 at config.l1.hmax_m
    (deterministic and frozen; L1 is not the tool under test).  The ratios at hmax_check_m are reported beside them, and
    every (pair, frequency) whose ratio lies within max(tol, |r_hmax - r_check|) of a threshold, or on the other side of
    it at hmax_check_m, is flagged: a gate or coverage verdict that rests on such a value is mesh-sensitive."""
    thr = {"span_lower_end": span["lower_end"], "span_below": span["below"], "span_upper_end": span["upper_end"],
           "coverage_low": 1.0 - min_effect, "coverage_high": 1.0 + min_effect}
    flagged, shifts = [], []
    for p in pairs:
        for k in FK:
            r, r2 = p[f"r_L1_{k}"], p[f"r_L1_check_{k}"]
            shifts.append(abs(r - r2))
            for name, t in thr.items():
                if abs(r - t) <= max(tol, abs(r - r2)) or (r - t) * (r2 - t) < 0:
                    flagged.append({"pair": p["pair"], "freq": k, "threshold": name, "t": t, "r": r, "r_check": r2})
    at_h = {k: span_check([p[f"r_L1_{k}"] for p in pairs], span)["passed"] for k in FK} if pairs else {}
    at_h2 = {k: span_check([p[f"r_L1_check_{k}"] for p in pairs], span)["passed"] for k in FK} if pairs else {}
    return {"max_abs_ratio_shift": max(shifts, default=0.0), "flagged": flagged, "span_passed_at_hmax": at_h,
            "span_passed_at_hmax_check": at_h2, "span_verdict_mesh_stable": at_h == at_h2}


def diversity(pairs: list[dict]) -> dict:
    """Diversity statistic of the drawn sample: spread of r_L1 at 20 MHz and the kind counts."""
    r = np.array([p["r_L1_20MHz"] for p in pairs], dtype=float)
    kinds: dict = {}
    for p in pairs:
        kinds[p["kind"]] = kinds.get(p["kind"], 0) + 1
    return {"r_L1_20MHz_std": float(r.std(ddof=1)) if r.size > 1 else 0.0, "r_L1_20MHz_iqr":
            float(np.subtract(*np.percentile(r, [75, 25]))) if r.size else 0.0, "kinds": kinds}


# ---------------------------------------------------------------------------------------------------------------- stages
SOLVE_CHECKS = ("fasthenry_binary_pinned", "fasthenry_closed_form_validated", "exported_geometry_identical",
                "l2_solver_health", "finest_values_present")


def stage_registration(run, cfg: dict, smoke: bool, seed: int) -> dict:
    """Registration (F2, F4, F5), in the module docstring's order.  Registered: any failure raises RegistrationRefused;
    smoke: every check is recorded and the stage completes."""
    from moduleforge.generate import perturb as P
    t0 = time.time()
    rec: dict = {"mode": "smoke" if smoke else "registered", "seed_source": "development seed" if smoke else "sealed"}

    def gate(name, passed, value=None, threshold=None, detail=""):
        run.sanity(name, passed=bool(passed), value=value, threshold=threshold, detail=str(detail)[:4000])
        rec.setdefault("checks", {})[name] = dict(passed=bool(passed), value=value, threshold=threshold, detail=detail)
        if not passed and not smoke:
            raise RegistrationRefused(f"{name}: {detail}")

    # 1. freeze (reconstruction script first)
    fr = freeze_record(cfg)
    rec["freeze"] = fr
    gate("freeze_hashes_match", not fr["failures"], value=len(fr["failures"]), threshold=0,
         detail=fr["failures"] or "every frozen hash, version and the pinned commit match; every loaded moduleforge "
                                  "file is frozen")
    # 2. judged references (fingerprints), D0007
    refs, bad = judged_references(cfg)
    rec["judged_fingerprints"] = {r: lay.fingerprint() for r, lay in refs.items()}
    gate("references_fingerprints_match", not bad, value=len(bad), threshold=0,
         detail=bad or f"{sorted(refs)} rebuilt by the frozen T0263 script, fingerprints as frozen")
    gpl = gpl_files_in_tree()
    gate("no_powersynth_files_in_tree", not gpl, value=len(gpl), threshold=0, detail=gpl or "none tracked (D0007)")
    # the slots: judged references (registered) or development stand-ins (smoke, F2)
    if smoke:
        c4, c4_rules = case4_reference()
        slots = [(f"{e['reference_id']}<-dev:2D_Case_4", c4, c4_rules) for e in cfg["references"]]
    else:
        slots = []
        for e in cfg["references"]:
            rid = e["reference_id"]
            try:
                rules = P.measured_rules(refs[rid])
            except ValueError as err:  # review T0440: refused with its cause, not a bare ValueError
                raise RegistrationRefused(f"{rid}: perturb.measured_rules raised ValueError({err})") from err
            slots.append((rid, refs[rid], rules))
    slot_of = {e["reference_id"]: sl[0] for e, sl in zip(cfg["references"], slots, strict=True)}
    rec["slots"] = [sl[0] for sl in slots]
    # 3. reference coordinates whole mm, and each reference on the three lattices: both gated before any draw
    wmm = {rid: whole_mm_failures(lay) for rid, lay, _ in slots}
    gate("references_whole_mm", not any(wmm.values()), value=sum(map(len, wmm.values())), threshold=0,
         detail={r: v for r, v in wmm.items() if v} or "every reference coordinate perturb rounds is whole mm")
    ref_lattice = {rid: {f"{c / MM:g}mm": P.on_lattice(lay, c) for c in LATTICES_M} for rid, lay, _ in slots}
    off = {r: [k for k, ok in v.items() if not ok] for r, v in ref_lattice.items()}
    off = {r: v for r, v in off.items() if v}
    gate("references_on_lattice", not off, value=sum(map(len, off.values())), threshold=0,
         detail=f"references off a lattice: {off}" if off else "every reference on the 1.0, 0.5 and 0.25 mm lattices")
    # 4. draws (seed per slot), then the replay from the independently read seed, L1 and the geometry re-checks
    alloc = cfg["allocation"]
    drawn, draw_errors = {}, []
    rec["slot_seeds"] = {rid: reference_seed(seed, k) for k, (rid, _, _) in enumerate(slots)}
    for slot, (rid, lay, rules) in enumerate(slots):
        try:
            drawn[rid] = draw_pairs(rid, lay, rules, alloc, reference_seed(seed, slot))
        except RegistrationRefused as e:
            draw_errors.append(str(e))
    gate("draws_complete", not draw_errors, value=len(draw_errors), threshold=0,
         detail=draw_errors or f"allocation {alloc} drawn on every reference")
    source_seed = DEV_SEED if smoke else int(os.environ["MFOS_SEED"])
    mism = replay_mismatches(slots, alloc, source_seed, drawn)
    seed_ok = (seed == DEV_SEED and source_seed == DEV_SEED) if smoke else (seed == run.seed == source_seed)
    if not seed_ok:
        seed_detail = f"draw seed {seed} is not the expected source"
    elif mism:
        seed_detail = mism
    elif smoke:
        seed_detail = "smoke: drawn from DEV_SEED, MFOS_SEED never read; a replay from DEV_SEED reproduces every move"
    else:
        seed_detail = "registered: drawn from run.seed (sealed); a replay from MFOS_SEED reproduces every move"
    gate("seed_provenance", seed_ok and not mism and bool(drawn), value=len(mism), threshold=0, detail=seed_detail)
    pairs = []
    for slot, (rid, lay, rules) in enumerate(slots):
        if rid in drawn:
            pairs += pair_records(rid, slot, lay, rules, drawn[rid], cfg["l1"])
    # 5. proxy pair
    proxy = proxy_pair_status()
    rec["proxy"] = proxy
    # 6. F4 checks, the coverage report and the L1 mesh report
    for name, c in registration_checks(cfg, pairs, rec["slots"], ref_lattice, proxy,
                                       slot_of[cfg["proxy"]["reference"]]).items():
        gate(name, c["passed"], c["value"], c["threshold"], c["detail"])
    rec["coverage"] = coverage(pairs, rec["slots"], cfg["coverage_min_effect"])
    rec["l1_mesh"] = l1_mesh_report(pairs, SPAN, cfg["coverage_min_effect"], cfg["l1"]["near_threshold_abs"])
    rec["diversity"] = diversity(pairs) if pairs else {}
    rec["pairs"] = pairs
    # 7. every moduleforge source file loaded by the whole stage is frozen (lazy imports included)
    unf = unfrozen_sources(cfg["freeze"])
    gate("freeze_covers_loaded_sources", not unf, value=len(unf), threshold=0,
         detail=unf or f"{len(moduleforge_sources())} moduleforge files loaded, all in config.freeze.files")
    rec["wall_s"] = time.time() - t0
    n_cov = sum(v["covered"] for v in rec["coverage"].values())
    run.metric("n_registered_pairs", len(pairs) + (proxy.get("status") == "built"), n=len(pairs))
    if pairs:
        r20 = [p["r_L1_20MHz"] for p in pairs]
        run.metric("l1_ratio_min", min(r20), n=len(r20))
        run.metric("l1_ratio_max", max(r20), n=len(r20))
        run.metric("l1_n_below_0p90", sum(x < SPAN["below"] for x in r20), n=len(r20))
        run.metric("l1_ratio_std", rec["diversity"]["r_L1_20MHz_std"], n=len(r20))
        run.metric("l1_n_near_threshold", len({f["pair"] for f in rec["l1_mesh"]["flagged"]}), n=len(r20))
    run.metric("n_move_types_covered_l1", n_cov, n=len(rec["coverage"]))
    out = run.run_dir / "registration.json"
    out.write_text(json.dumps(rec, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o)))
    run.artifact("registration.json", out)
    return rec


def stage_solve(run, cfg: dict, smoke: bool) -> None:
    """Stub (T0389): exporter -> FastHenry ladder + thickness ladder, l2_layout 1.0 / 0.5 / 0.25 mm ladder, estimators
    (gci_step_floor), F1 exclusions (caps relative to the ratio, founder 2026-11-17), rows, A1/A2/K1/K2 metrics."""
    if not smoke:
        raise NotImplementedError("E004 solve stage: T0389")
    for name in SOLVE_CHECKS:
        run.sanity(name, passed=False, detail="not run: --stage registration (the solve stage is T0389's stub)")


# ------------------------------------------------------------------------------------------------------------ dev span
def dev_span_sim(n_seeds: int, out: Path, cfg: dict) -> dict:
    """Research only (F2: 2D_Case_4, development seeds, L1 only).  For development seed i = DEV_SEED + 1000 + k, the
    registration draw of both slots (reference_seed(i, 0), reference_seed(i, 1)) on 2D_Case_4 with the frozen allocation;
    each slot's draw is a single-reference sample, and the two slots pooled stand for the two-reference pooled check
    (without the proxy pair).  Checkpointed per seed to ``out`` (resumes)."""
    from moduleforge.generate import perturb as P
    ref, rules = case4_reference()
    state = json.loads(out.read_text()) if out.exists() else {"seeds": {}}
    state.update({"label": "RESEARCH ONLY, NOT EVIDENCE (T0388): 2D_Case_4, development seeds, L1 only (O004 F2)",
                  "allocation": cfg["allocation"], "rules_sha256": P.rules_sha256(), "seed_rule":
                  "seed_k = DEV_SEED + 1000 + k; slot draws use reference_seed(seed_k, slot)", "dev_seed": DEV_SEED,
                  "reference_fingerprint": ref.fingerprint(), "rule_overrides": CASE4_OVERRIDES})
    for k in range(n_seeds):
        sk = DEV_SEED + 1000 + k
        if str(sk) in state["seeds"]:
            continue
        t0, rec = time.time(), {}
        for slot in (0, 1):
            try:
                moves = P.draw(ref, cfg["allocation"], reference_seed(sk, slot), rules)
                prs = pair_records("2D_Case_4", slot, ref, rules, moves, cfg["l1"], with_geometry_checks=False)
                rec[f"slot{slot}"] = [{"kind": p["kind"], "components": p["components"],
                                       **{f"r_L1_{f}": p[f"r_L1_{f}"] for f in FK}} for p in prs]
            except (ValueError, RuntimeError) as e:
                rec[f"slot{slot}"] = {"error": repr(e)}
        rec["wall_s"] = time.time() - t0
        state["seeds"][str(sk)] = rec
        out.write_text(json.dumps(state, indent=1))
        print(f"seed {sk}: {rec['wall_s']:.1f} s", flush=True)
    state["summary"] = summarize_span_sim(state)
    out.write_text(json.dumps(state, indent=1))
    return state["summary"]


def summarize_span_sim(state: dict, lower_ends=(0.75, 0.78, 0.80, 0.85)) -> dict:
    """Fraction of draws meeting the span check per lower end (both frequencies, upper end and n_below as O004), with a
    Wilson 95 % interval; and the distribution of each draw's lowest L1 ratio (20 MHz)."""
    from statistics import NormalDist
    z = NormalDist().inv_cdf(0.975)

    def wilson(k, n):
        if n == 0:
            return (math.nan, math.nan)
        p, d = k / n, 1 + z * z / n
        c, h = (p + z * z / (2 * n)) / d, z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
        return (max(0.0, c - h), min(1.0, c + h))

    single, pooled = [], []
    for rec in state["seeds"].values():
        ok = [rec[s] for s in ("slot0", "slot1") if isinstance(rec.get(s), list)]
        single += ok
        if len(ok) == 2:
            pooled.append(ok[0] + ok[1])
    res: dict = {"n_single_draws": len(single), "n_pooled_draws": len(pooled),
                 "n_failed_draws": sum(isinstance(r.get(s), dict) for r in state["seeds"].values()
                                       for s in ("slot0", "slot1"))}
    for name, draws in (("single_reference", single), ("pooled_two_slots", pooled)):
        res[name] = {}
        for lo in lower_ends:
            k = sum(all(span_check([p[f"r_L1_{f}"] for p in d], SPAN, lo)["passed"] for f in FK) for d in draws)
            res[name][f"{lo:.2f}"] = {"k": k, "n": len(draws), "fraction": k / len(draws) if draws else math.nan,
                                      "wilson95": wilson(k, len(draws))}
        mins = np.array([min(p["r_L1_20MHz"] for p in d) for d in draws]) if draws else np.array([])
        nb = np.array([sum(p["r_L1_20MHz"] < SPAN["below"] for p in d) for d in draws]) if draws else np.array([])
        mx = np.array([max(p["r_L1_20MHz"] for p in d) for d in draws]) if draws else np.array([])
        if draws:
            res[name]["lowest_r_L1_20MHz"] = {q: float(np.quantile(mins, float(q))) for q in
                                              ("0.0", "0.05", "0.25", "0.5", "0.75", "0.95", "1.0")}
            res[name]["n_below_0p90_counts"] = {str(i): int((nb == i).sum()) for i in range(int(nb.max()) + 1)}
            res[name]["fraction_max_ge_upper"] = float((mx >= SPAN["upper_end"]).mean())
    return res


# ------------------------------------------------------------------------------------------------------------------ main
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--smoke", action="store_true", help="development seed, development geometry, L1 only, temp run dir")
    ap.add_argument("--stage", choices=("registration", "solve", "all"), default="all")
    ap.add_argument("--dev-span-sim", type=int, default=0, metavar="N", help="research: span check on N dev seeds")
    ap.add_argument("--out", default=str(ROOT / "research" / "o004_e004" / "span_sim_case4.json"))
    ap.add_argument("--print-freeze", action="store_true", help="print the current tree's freeze values (not evidence)")
    a = ap.parse_args()
    if a.print_freeze:
        print(json.dumps(print_freeze(), indent=1))
        return 0
    if a.dev_span_sim:
        import yaml
        cfg = yaml.safe_load(SPEC_DRAFT.read_text())["config"]
        out = Path(a.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        print(json.dumps(dev_span_sim(a.dev_span_sim, out, cfg), indent=1))
        return 0
    from mfos.evidence import ExperimentRun
    run_dir = tempfile.mkdtemp(prefix="e004-smoke-") if a.smoke else None
    with ExperimentRun(experiment_id=EID, run_dir=run_dir) as run:
        cfg = spec_config(run.config)
        if a.smoke:
            seed = DEV_SEED  # nothing is drawn from the sealed seed in smoke mode
        else:
            if os.environ.get("MFOS_SEED") is None or run.seed is None:
                raise RegistrationRefused("registered mode needs E004's sealed seed (MFOS_SEED, set by the mfos runner)")
            seed = int(run.seed)  # the seed ExperimentRun records in result.json; replayed from MFOS_SEED in the stage
        run.domain(freq_hz=list(FREQS_HZ), references=[e["reference_id"] for e in cfg["references"]],
                   lattices_m=list(LATTICES_M))
        rec = stage_registration(run, cfg, a.smoke, seed)
        if not a.smoke:
            if rec["proxy"].get("status") != "built":
                raise RegistrationRefused(f"the 2D_Case_2R proxy pair is not built: {rec['proxy'].get('reason')}")
        if a.stage in ("solve", "all") or a.smoke:
            stage_solve(run, cfg, a.smoke)
        print(json.dumps({"run_dir": str(run.run_dir), "checks": {k: v["passed"] for k, v in rec["checks"].items()},
                          "coverage": {k: v["covered"] for k, v in rec["coverage"].items()},
                          "proxy": rec["proxy"]["status"], "wall_s": round(rec["wall_s"], 1)}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
