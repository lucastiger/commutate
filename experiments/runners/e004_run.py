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
  solve         (T0389) on every registered layout (references, drawn pairs, the proxy pair once built):
      a. l2_layout 1.0 / 0.5 / 0.25 mm (1.0 mm by E010's mesh-constant pattern, CELL[0] patched at refinement 0; 0.5 mm the
         unpatched refinement 0; the judged 0.25 mm the unpatched refinement 1) and P3's thickness (5/3/3, 20/12/12 layers)
         and filament (bisected annuli) levels at 0.5 mm, each solve its own child process;
      b. FastHenry (moduleforge.solvers.fasthenry export, fasthenry_run.solve_deck, multipole, up to 10 retries, no direct
         fallback): lateral k0 / k1 / k2 (trace cell 1 / 0.5 / 0.25 mm, plane 2 / 1 / 0.5 mm, wire 2x2 / 4x4 / 8x8 filaments
         and 1 / 2 / 4 pieces) at nh_lateral, and the thickness ladder nh 3 / 5 / 9 at k1; self_test() once per host
         (stored by binary sha256), explicit timeout_s and mem_cap_mb per job, every attempt's peak memory and wall time;
      c. estimators: gci_capped for every L sequence, the ratio-step rule (mfos.metrics.gci_step_floor, 0.1 %) for every
         ratio sequence, plus the thickness (and l2's filament) terms, on L and on ratios; a missing level -> +inf;
      d. F1 (caps relative to the ratio, D0024 item 1), rows, A1 / A2 / K1 / K2, the INVALID rule (a pair lacking a finest
         value and no completed pair firing K1), coverage after exclusion, per-type zero-failure bounds, F8.
      Child processes are packed by projected memory (MF_E004_MEM_GB), never by CPU count; results are checkpointed.

Modes
  (no flag)                    registered: `mfos exp run E004` sets MFOS_SEED (sealed), MFOS_SPEC_JSON, MFOS_RUN_DIR.
                               A failed registration check raises RegistrationRefused before any solve (run status error).
  --smoke --stage registration the whole registration stage on a development seed with L1 only, on development geometry:
                               2D_Case_4 stands in for both judged slots (F2: no draw, long_sides or L1 on 2D_Case_2R or
                               2D_Case_6; their fingerprints are checked).  Checks are recorded, never raised; exit 0.
  --dev-span-sim N             research only (not evidence): the registration span check on 2D_Case_4 with the frozen
                               allocation on N development seeds, checkpointed to --out (resumes).
  --print-freeze               print the freeze values of the current tree (the act of freezing; not evidence).
  --smoke                      (stage all) also the solve stage at the coarsest level of each ladder (l2 1.0 mm, FastHenry
                               k0 at nh 3) on one Case 4 development pair and 2D_Case_4, through the metrics (labelled).
  --dev-fh-plan / --dev-fh-probe GB / --dev-fh-direct-mem / --dev-fh-run FILE
                               research only (F7(a), development geometry): the FastHenry job list, the multipole
                               preconditioner probe, the direct-mode memory runs, and the job list's runner (burst VM).

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
import shutil
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

# ---------------------------------------------------------------------------------------------------------------- stages
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


# ================================================================================================ solve stage (T0389)
# Facts this section relies on (sources):
#  * l2_layout levels: O006 P3 / E010 child_em's mesh-constant pattern (research/o004_f7/pilot_l2.py LEVELS): lat1.0 =
#    CELL[0] patched to 1.0 mm at refinement 0; lat0.5 = unpatched refinement 0; lat0.25 = unpatched refinement 1;
#    thk_c / thk_f = 0.5 mm with layers 5/3/3 and 20/12/12; fil_f = 0.5 mm with the bisected annuli E1.
#  * Estimators: mfos.metrics.gci_capped (D0012, D0013), gci_step_floor (O004 scope_in, founder), ratio_middle_term (O006
#    P3's thickness term); F1 caps relative to the ratio (D0024 item 1).
#  * FastHenry sizing: O006 P4 multipole runs (research/notes/o006-p4-fasthenry-feasibility.md section 3.2): 0.56-0.78 GB at
#    25,056 filaments and 2.43-2.87 GB at 102,192 (22-31 kB per filament); 1203-1246 s at 102,192 filaments, time exponent
#    1.40 in the filament count (k0 -> k1, +-25 % under contention).
SOLVE_CHECKS = ("ratio_step_rule_validated", "fasthenry_binary_pinned", "fasthenry_closed_form_validated",
                "exported_geometry_identical", "finest_values_present")
L2_LADDER = ("lat1.0", "lat0.5", "lat0.25")
L2_ALL = L2_LADDER + ("thk_c", "thk_f", "fil_f")
FH_LADDER = ("k0", "k1", "k2")
STEP_FLOOR_REL = 1e-3  # O004 scope_in: ratio steps all below 0.1 % count as converged (relative to the finest ratio)
P3_EXAMPLE_R = 0.9692  # O006 P3's trace-width pair ratio (l2_layout 0.9692 +- 0.0011, P4 note section 3.4)
P3_EXAMPLE_STEPS = (-7e-5, 2.5e-4)  # its relative steps 0.007 % and 0.025 % (O004 notes; gci_capped gave +inf)
SOLVE_TAG = "e004-solve-v1"
INF = math.inf


def _gci_step_floor_local(f0: float, f1: float, f2: float, step_floor: float, relative: bool = False) -> float:
    """SMOKE-ONLY, labelled runner-local copy of the ratio-step rule (O004 scope_in), used only if mfos.metrics lacks
    gci_step_floor; registered mode refuses without the mfos.metrics function.  Same rule: both steps below the floor ->
    3 max|d|, else gci_capped."""
    from mfos.metrics import gci_capped
    d1, d2 = float(f1) - float(f0), float(f2) - float(f1)
    lim = step_floor * abs(float(f2)) if relative else step_floor
    if abs(d1) < lim and abs(d2) < lim:
        return 3.0 * max(abs(d1), abs(d2))
    return gci_capped(f0, f1, f2)


def step_rule(smoke: bool):
    """(function, source label): mfos.metrics.gci_step_floor; in smoke mode only, the labelled local copy if it is absent."""
    try:
        from mfos.metrics import gci_step_floor
        return gci_step_floor, "mfos.metrics.gci_step_floor"
    except ImportError:
        if not smoke:
            raise RegistrationRefused("registered mode needs mfos.metrics.gci_step_floor") from None
        return _gci_step_floor_local, "runner-local copy (smoke only, labelled; mfos.metrics lacks gci_step_floor)"


def step_rule_check(smoke: bool) -> dict:
    """ratio_step_rule_validated: on P3's trace-width example (relative steps 0.007 % and 0.025 %) gci_capped gives +inf
    and the ratio-step rule gives exactly 3 max|d| (finite); the local copy agrees with the function used."""
    from mfos.metrics import gci_capped
    fn, src = step_rule(smoke)
    r0 = P3_EXAMPLE_R
    r1 = r0 * (1 + P3_EXAMPLE_STEPS[0])
    r2 = r1 * (1 + P3_EXAMPLE_STEPS[1])
    want = 3.0 * max(abs(r1 - r0), abs(r2 - r1))
    got, loc, cap = fn(r0, r1, r2, STEP_FLOOR_REL, relative=True), _gci_step_floor_local(r0, r1, r2, STEP_FLOOR_REL, True), \
        gci_capped(r0, r1, r2)
    # a sequence with one step above the floor must still go to gci_capped (here: +inf, |rho| > 1)
    big = fn(r0, r0 * 1.002, r0 * 1.002 * 1.003, STEP_FLOOR_REL, relative=True)
    ok = math.isinf(cap) and math.isclose(got, want, rel_tol=1e-12) and math.isclose(loc, got, rel_tol=1e-12) and \
        math.isinf(big)
    return dict(passed=ok, value=got, threshold=want, detail=f"{src}: P3 example ({r0}, {r1:.7f}, {r2:.7f}) -> {got:.3e} "
                f"(3 max|d| = {want:.3e}); gci_capped -> {cap}; local copy -> {loc:.3e}; steps 0.2 %/0.3 % -> {big}")


# ------------------------------------------------------------------------------------------------------------- levels
def l2_level(cfg: dict, name: str) -> dict:
    return cfg["solve"]["l2_layout"]["levels"][name]


def fh_level(cfg: dict, k: str, nh: int, smoke_nh: bool = False) -> dict:
    """FHLevel kwargs of lateral level ``k`` at ``nh`` thickness filaments (traces and planes alike)."""
    f = cfg["solve"]["fasthenry"]
    lv = f["lateral"][k]
    if lv["wire_n"] == 1 and lv["wire_sub"] == 1:  # T0385: NaN impedance at wire_n = wire_sub = 1
        raise ValueError(f"FastHenry level {k}: wire_n = wire_sub = 1 is never used (T0385)")
    return dict(cell_mm=lv["cell_mm"], plane_cell_mm=lv["plane_cell_mm"], nh_trace=int(nh), nh_plane=int(nh), rh=f["rh"],
                nw_trace=f["nw_trace"], wire_n=lv["wire_n"], wire_sub=lv["wire_sub"])


def fh_sizing(cfg_or_sizing: dict, n_fil: int) -> dict:
    """Projected multipole peak (GB, with the stated margin), wall time (s), and the explicit mem_cap_mb / timeout_s passed
    to the adapter (review T0427/T0428 B(2)); frozen rule config.solve.fasthenry.sizing (P4's measured runs)."""
    s = cfg_or_sizing["solve"]["fasthenry"]["sizing"] if "solve" in cfg_or_sizing else cfg_or_sizing
    mem = s["kb_per_filament"] * n_fil * 1e3 / 1e9
    t = s["t_ref_s"] * (n_fil / s["f_ref"]) ** s["exponent"]
    return dict(mem_raw_gb=mem, mem_proj_gb=mem * s["mem_margin"], time_proj_s=t,
                mem_cap_mb=max(s["min_mem_cap_mb"], mem * s["mem_margin"] * 1024),
                timeout_s=max(s["min_timeout_s"], s["timeout_factor"] * t))


def solve_jobs(cfg: dict, layouts: dict, smoke: bool) -> list[dict]:
    """Every solve of the stage: l2_layout's ladder and P3 terms, FastHenry's lateral ladder at nh_lateral and its thickness
    ladder at the thickness level.  Smoke: the coarsest level of each ladder only (l2 lat1.0, FastHenry k0 at the lowest nh)."""
    from moduleforge.solvers.fasthenry import FHLevel, export
    f = cfg["solve"]["fasthenry"]
    nh_lat, nh_list, at = int(f["nh_lateral"]), [int(x) for x in f["thickness"]["nh"]], f["thickness"]["at"]
    if 1 in nh_list or nh_lat == 1 or nh_lat not in nh_list:
        raise ValueError("FastHenry nh = 1 is a smoke-test level (T0417): never in E004's ladder; nh_lateral must be in it")
    jobs = []
    for name, lay in layouts.items():
        for lv in (("lat1.0",) if smoke else L2_ALL):
            jobs.append(dict(id=f"{name}__l2_{lv}", solver="l2_layout", layout=name, level=lv, key=lv,
                             spec=l2_level(cfg, lv), mem_proj_gb=cfg["solve"]["l2_layout"]["peak_gb"][lv],
                             fingerprint=lay.fingerprint()))
        fh = [("k0", min(nh_list))] if smoke else [(k, nh_lat) for k in FH_LADDER] + \
            [(at, nh) for nh in nh_list if nh != nh_lat]
        for k, nh in fh:
            kw = fh_level(cfg, k, nh)
            _deck, facts = export(lay, FHLevel(**kw), die_model=f["die_model"], terminal_model=f["terminal_model"])
            sz = fh_sizing(cfg, facts["n_filaments"])
            key = k if (nh == nh_lat or smoke) else f"t{nh}"
            jobs.append(dict(id=f"{name}__fh_{k}_nh{nh}", solver="fasthenry", layout=name, level=f"{k}_nh{nh}", key=key,
                             fh_level=kw, mode=f["mode"], order=f["order"], tol=f["tol"], max_retries=f["max_retries"],
                             die_model=f["die_model"], terminal_model=f["terminal_model"],
                             n_filaments_exporter=facts["n_filaments"], deck_sha256=facts["deck_sha256"]
                             if "deck_sha256" in facts else hashlib.sha256(_deck.encode()).hexdigest(),
                             fingerprint=lay.fingerprint(), **sz))
    return jobs


# ------------------------------------------------------------------------------------------------------------ children
def _job_hash(job: dict) -> str:
    return hashlib.sha256(json.dumps({k: v for k, v in job.items() if k not in ("time_proj_s",)}, sort_keys=True,
                                     default=str).encode()).hexdigest()


def child_solve(job_path: str) -> int:
    """One solve in this (child) process: reads the job JSON (with 'layout_pickle' and 'out'), writes the result JSON.
    l2_layout's module constants are patched here (E010's mesh-constant pattern), so every l2 solve has its own process."""
    import pickle
    import resource
    job = json.loads(Path(job_path).read_text())
    lay = pickle.loads(Path(job["layout_pickle"]).read_bytes())
    fp = lay.fingerprint()
    rec = dict(id=job["id"], job_hash=job["job_hash"], fingerprint=fp, fingerprint_ok=fp == job["fingerprint"],
               host=os.uname().nodename, time_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    t0 = time.perf_counter()
    if job["solver"] == "l2_layout":
        from moduleforge.solvers import l2_layout as L
        sp = job["spec"]
        if sp.get("cell_mm_patch") is not None:  # E010 child_em: patch slot 0, solve at refinement 0
            L.CELL = (sp["cell_mm_patch"] * MM,) + tuple(L.CELL[1:])
            for attr, n in zip(("LAYERS_TOP", "LAYERS_BACK", "LAYERS_BASE"), sp["layers"], strict=True):
                setattr(L, attr, (int(n),) + tuple(getattr(L, attr)[1:]))
            L.WIRE_EDGES = (tuple(sp["annuli"]),) + tuple(L.WIRE_EDGES[1:])
        cell = float(L.CELL[sp["refinement"]])
        if abs(cell - sp["cell_mm"] * MM) > 1e-12:
            raise RuntimeError(f"{job['id']}: l2_layout CELL[{sp['refinement']}] = {cell} m, level wants {sp['cell_mm']} mm")
        r = L.loop_inductance(lay, list(FREQS_HZ), refinement=sp["refinement"])
        m = r.meta
        flags = [int(x) for x in m["gmres_flags"]]
        rec.update(ok=all(x == 0 for x in flags), status="ok" if all(x == 0 for x in flags) else "gmres_flag",
                   L_H=dict(zip(FK, map(float, r.L_H), strict=True)), R_ohm=dict(zip(FK, map(float, r.R_ohm), strict=True)),
                   cell_m=cell, n_unknowns=int(m["n_unknowns"]), gmres_flags=flags,
                   gmres_iters=[int(x) for x in m["gmres_iters"]], solver_tol_rel_L_max=float(m["solver_tol_rel_L_max"]),
                   source_sha256=m["source_sha256"], tool_version=m["tool_version"])
    else:
        from dataclasses import asdict

        from moduleforge.solvers import fasthenry_run as FR
        from moduleforge.solvers.fasthenry import FHLevel, export
        lev = FHLevel(**job["fh_level"])
        deck, facts = export(lay, lev, die_model=job["die_model"], terminal_model=job["terminal_model"])
        res = FR.solve_deck(deck, mode=job["mode"], order=job["order"], tol=job["tol"], max_retries=job["max_retries"],
                            timeout_s=float(job["timeout_s"]), mem_cap_mb=float(job["mem_cap_mb"]), facts=facts)
        rec.update(ok=res.ok, status=res.status, reason=res.reason, binary_sha256=res.binary_sha256,
                   binary_path=res.binary_path, deck_sha256=res.deck_sha256, n_filaments_exporter=res.n_filaments_exporter,
                   n_filaments_refined=res.n_filaments_refined, nh_trace=res.nh_trace, nh_plane=res.nh_plane,
                   wire_n=lev.wire_n, wire_sub=lev.wire_sub, die_model=job["die_model"], args=res.args,
                   L_H=dict(zip(FK, (res.L_H[f] for f in FREQS_HZ), strict=True)) if res.ok else None,
                   R_ohm=dict(zip(FK, (res.R_ohm[f] for f in FREQS_HZ), strict=True)) if res.ok else None,
                   attempts=[{k: v for k, v in asdict(a).items() if k != "log_tail"} | {"log_tail": a.log_tail[-300:]}
                             for a in res.attempts],
                   crashed_every_attempt=bool(res.attempts) and all(a.status == "crash" for a in res.attempts),
                   peak_mem_mb_max=max((a.peak_mem_mb for a in res.attempts), default=None))
        if res.ok and not all(math.isfinite(v) and v > 0 for v in rec["L_H"].values()):
            rec.update(ok=False, status="nonpositive_or_nan_L")
    ru = resource.getrusage(resource.RUSAGE_SELF)
    rec.update(wall_s=time.perf_counter() - t0, peak_GB_self=ru.ru_maxrss * (1.0 if sys.platform == "darwin" else 1024.0)
               / 1e9, threads={k: os.environ.get(k) for k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MF_L2_THREADS")})
    tmp = Path(job["out"]).with_suffix(".tmp")
    tmp.write_text(json.dumps(rec, indent=1, default=str))
    tmp.replace(job["out"])
    return 0


def run_jobs(jobs: list[dict], layouts: dict, work: Path, mem_budget_gb: float, log=print) -> dict:
    """Run every job not already done (checkpoint and resume: a result whose job hash matches is reused), as child
    processes packed by PROJECTED MEMORY (never by CPU count): a job starts only while the running jobs' projected peaks
    plus its own stay within ``mem_budget_gb``.  A job projected above the budget refuses the stage before any solve."""
    import pickle
    too_big = [j["id"] for j in jobs if j["mem_proj_gb"] > mem_budget_gb]
    if too_big:
        raise RuntimeError(f"jobs projected above the memory budget {mem_budget_gb} GB (set MF_E004_MEM_GB on a larger "
                           f"machine): {too_big[:5]}")
    (work / "layouts").mkdir(parents=True, exist_ok=True)
    (work / "solves").mkdir(parents=True, exist_ok=True)
    for name, lay in layouts.items():
        p = work / "layouts" / f"{name}.pkl"
        if not p.exists():
            p.write_bytes(pickle.dumps(lay))
    out, pending = {}, []
    for j in jobs:
        j = dict(j, job_hash=_job_hash(j), layout_pickle=str(work / "layouts" / f"{j['layout']}.pkl"),
                 out=str(work / "solves" / f"{j['id']}.json"))
        if Path(j["out"]).exists() and json.loads(Path(j["out"]).read_text()).get("job_hash") == j["job_hash"]:
            out[j["id"]] = json.loads(Path(j["out"]).read_text())
        else:
            pending.append(j)
    pending.sort(key=lambda j: -j["mem_proj_gb"])
    running: dict = {}
    while pending or running:
        for j in list(pending):
            if sum(r["mem_proj_gb"] for r in running.values()) + j["mem_proj_gb"] <= mem_budget_gb:
                jp = work / "solves" / f"{j['id']}.job.json"
                jp.write_text(json.dumps(j, default=str))
                fh = open(work / "solves" / f"{j['id']}.log", "w")  # noqa: SIM115 (closed when the child ends)
                p = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "--child", str(jp)], stdout=fh,
                                     stderr=subprocess.STDOUT, cwd=ROOT)
                running[p] = dict(j, _fh=fh, _t0=time.time())
                pending.remove(j)
                log(f"start {j['id']} (projected {j['mem_proj_gb']:.1f} GB)")
        time.sleep(1.0)
        for p in list(running):
            if p.poll() is None:
                continue
            j = running.pop(p)
            j["_fh"].close()
            if Path(j["out"]).exists():
                out[j["id"]] = json.loads(Path(j["out"]).read_text())
            else:  # the child died before writing (e.g. killed): a missing value, recorded
                out[j["id"]] = dict(id=j["id"], ok=False, status=f"child_exit_{p.returncode}", job_hash=j["job_hash"],
                                    log_tail=(work / "solves" / f"{j['id']}.log").read_text()[-1500:])
            log(f"done {j['id']}: {out[j['id']].get('status')} ({time.time() - j['_t0']:.0f} s)")
    return out


# ---------------------------------------------------------------------------------------------------------- estimators
def _v(res: dict, jobs_by_key: dict, layout: str, key: str, fk: str):
    """L (H) of ``layout`` at level key ``key`` and frequency ``fk``, or None if the solve is missing or not ok."""
    jid = jobs_by_key.get((layout, key))
    r = res.get(jid) if jid else None
    return float(r["L_H"][fk]) if r and r.get("ok") and r.get("L_H") else None


def _ratio(x, y):
    return None if x is None or y is None else x / y


def l2_terms(v: dict, ratio: bool, step_fn) -> dict:
    """l2_layout estimate of the finest (0.25 mm) value: lateral (gci_capped for L, the ratio-step rule for ratios) +
    P3's thickness term (ratio_middle_term) + P3's filament term 3 |fil_f - lat0.5|.  A missing level -> that term +inf."""
    from mfos.metrics import gci_capped, ratio_middle_term
    lat = [v.get(k) for k in L2_LADDER]
    e_lat = INF if None in lat else (step_fn(*lat, STEP_FLOOR_REL, relative=True) if ratio else gci_capped(*lat))
    thk = (v.get("thk_c"), v.get("lat0.5"), v.get("thk_f"))
    e_thk = INF if None in thk else ratio_middle_term(*thk)
    e_fil = INF if None in (v.get("fil_f"), v.get("lat0.5")) else 3.0 * abs(v["fil_f"] - v["lat0.5"])
    return dict(finest=lat[2], lateral=e_lat, thickness=e_thk, filament=e_fil, total=e_lat + e_thk + e_fil)


def fh_terms(v: dict, nh_lat: int, nh_list: list[int], ratio: bool, step_fn) -> dict:
    """FastHenry estimate of the finest (k2 at nh_lateral) value: lateral (as l2) + thickness term from the 3 / 5 / 9 ladder
    at the thickness level: |f(nh_lateral) - f(9)| + gci_capped(f3, f5, f9) (the ratio-step rule for ratios; O004 scope_in:
    gci_capped on the thickness ladder stays conservative while its steps contract, T0368).  Missing -> +inf."""
    from mfos.metrics import gci_capped
    lat = [v.get(k) for k in FH_LADDER]
    e_lat = INF if None in lat else (step_fn(*lat, STEP_FLOOR_REL, relative=True) if ratio else gci_capped(*lat))
    thk = [v.get("k1" if nh == nh_lat else f"t{nh}") for nh in nh_list]
    if None in thk:
        e_thk = INF
    else:
        fin = step_fn(*thk, STEP_FLOOR_REL, relative=True) if ratio else gci_capped(*thk)
        e_thk = abs(thk[nh_list.index(nh_lat)] - thk[-1]) + fin
    return dict(finest=lat[2], lateral=e_lat, thickness=e_thk, total=e_lat + e_thk)


def zero_failure_bound(n: int, conf: float = 0.95) -> float:
    """One-sided upper bound on a failure share after n passes and 0 failures: 1 - (1 - conf)^(1/n) (exact binomial,
    Clopper-Pearson with k = 0); 1.0 for n = 0."""
    return 1.0 - (1.0 - conf) ** (1.0 / n) if n > 0 else 1.0


def assemble(cfg: dict, pairs: list[dict], ref_of: dict, res: dict, jobs: list[dict], smoke: bool, step_fn) -> dict:
    """Rows (pair x frequency, layout x frequency), F1 exclusions, the criteria's inputs and the reported diagnostics.
    ``ref_of``: pair layout name -> reference layout name.  Smoke: every ladder has one level, so 'finest' is the coarsest
    level solved (labelled) and every estimate is +inf (missing levels), which F1 turns into exclusions."""
    f = cfg["solve"]["fasthenry"]
    nh_lat, nh_list = int(f["nh_lateral"]), [int(x) for x in f["thickness"]["nh"]]
    by_key = {(j["layout"], j["key"]): j["id"] for j in jobs}
    l2_keys = ("lat1.0",) if smoke else L2_ALL
    fh_keys = ("k0",) if smoke else FH_LADDER + tuple(f"t{n}" for n in nh_list if n != nh_lat)
    fin_l2, fin_fh = ("lat1.0", "k0") if smoke else ("lat0.25", "k2")
    layouts = sorted({j["layout"] for j in jobs})
    vals = {lay: {fk: {"l2": {k: _v(res, by_key, lay, k, fk) for k in l2_keys},
                       "fh": {k: _v(res, by_key, lay, k, fk) for k in fh_keys}} for fk in FK} for lay in layouts}

    def terms(l2v, fhv, ratio):
        if smoke:
            return (dict(finest=l2v.get(fin_l2), total=INF, note="smoke: one level"),
                    dict(finest=fhv.get(fin_fh), total=INF, note="smoke: one level"))
        return l2_terms(l2v, ratio, step_fn), fh_terms(fhv, nh_lat, nh_list, ratio, step_fn)
    cap_l2, cap_fh = cfg["f1_caps"]["l2_layout"], cfg["f1_caps"]["fasthenry"]
    layout_rows, pair_rows = [], []
    for lay in layouts:
        for fk in FK:
            a, b = terms(vals[lay][fk]["l2"], vals[lay][fk]["fh"], ratio=False)
            done = a["finest"] is not None and b["finest"] is not None
            layout_rows.append(dict(row_kind="layout", layout=lay, freq=fk, L_l2=a["finest"] if done else math.nan,
                                    L_fh=b["finest"] if done else math.nan, E_l2=a["total"] if done else INF,
                                    E_fh=b["total"] if done else INF, finest_complete=done, terms_l2=a, terms_fh=b))
    for p in pairs:
        lay, ref = p["name"], ref_of[p["name"]]
        for fk in FK:
            rl2, rfh = ({k: _ratio(vals[lay][fk][sv][k], vals[ref][fk][sv][k]) for k in keys}
                        for sv, keys in (("l2", l2_keys), ("fh", fh_keys)))
            a, b = terms(rl2, rfh, ratio=True)
            done = a["finest"] is not None and b["finest"] is not None
            rel_l2 = a["total"] / a["finest"] if done and a["finest"] else INF
            rel_fh = b["total"] / b["finest"] if done and b["finest"] else INF
            excl = not (rel_l2 <= cap_l2 and rel_fh <= cap_fh)  # +inf or nan fails
            pair_rows.append(dict(row_kind="pair", pair=lay, reference=ref, kind=p["kind"], components=p["components"],
                                  freq=fk, r_l2=a["finest"] if done else math.nan, r_fh=b["finest"] if done else math.nan,
                                  r_L1=p[f"r_L1_{fk}"], E_R_l2=a["total"], E_R_fh=b["total"], E_R_l2_rel=rel_l2,
                                  E_R_fh_rel=rel_fh, excluded_f1=bool(excl), finest_complete=done,
                                  ratio_per_level_l2=rl2, ratio_per_level_fh=rfh, terms_l2=a, terms_fh=b))
    return dict(layout_rows=layout_rows, pair_rows=pair_rows, finest_levels={"l2_layout": fin_l2, "fasthenry": fin_fh},
                smoke_label="SMOKE: coarsest levels only; 'finest' = the one level solved; not evidence" if smoke else "")


def criteria(asm: dict, cfg: dict) -> dict:
    """A1, A2, K1, K2 exactly as O004 freezes them (mfos.metrics functions, the same the recompute block names), and the
    INVALID rule's inputs."""
    from mfos.metrics import max_consistency_capped, max_rel_err, max_rel_err_or_inf
    pr, lr = asm["pair_rows"], asm["layout_rows"]
    out: dict = {}
    if pr:
        out["A1"] = max_rel_err_or_inf([r["r_l2"] for r in pr], [r["r_fh"] for r in pr], [r["excluded_f1"] for r in pr])
        done = [r for r in pr if r["finest_complete"]]
        out["K1"] = max_rel_err([r["r_l2"] for r in done], [r["r_fh"] for r in done]) if done else math.nan
        out["K1_fires"] = bool(done) and out["K1"] > cfg["kill"]["K1"]
        out["pairs_missing_finest"] = sorted({r["pair"] for r in pr if not r["finest_complete"]})
    if lr:
        out["A2"] = max_consistency_capped([r["L_l2"] for r in lr], [r["L_fh"] for r in lr], [r["E_l2"] for r in lr],
                                           [r["E_fh"] for r in lr], cfg["a2_cap_rel"])
        done = [r for r in lr if r["finest_complete"]]
        out["K2"] = max_rel_err([r["L_l2"] for r in done], [r["L_fh"] for r in done]) if done else math.nan
    return out


def ratio_band(rows: list[dict], key: str, ekeys: tuple[str, str]) -> tuple[float, float] | None:
    """Discretisation band of a max-type ratio criterion (reported beside the point value, O004 uses point values):
    [max_i max(0, |d_i| - u_i), max_i (|d_i| + u_i)], u_i = the two solvers' relative estimates; None if not finite."""
    lo, hi = 0.0, 0.0
    for r in rows:
        d = abs(r[key[0]] / r[key[1]] - 1.0)
        u = r[ekeys[0]] + r[ekeys[1]]
        if not (math.isfinite(d) and math.isfinite(u)):
            return None
        lo, hi = max(lo, max(0.0, d - u)), max(hi, d + u)
    return (lo, hi) if rows else None


def diagnostics(asm: dict, cfg: dict) -> dict:
    """Reported, not judged: coverage after exclusion per move type with one-sided zero-failure bounds (per type, pooled,
    and the clustered bound by reference), the covered ratio range on FastHenry's finest ratios beside the L1 span, and
    F8 (L1's ratio agreement with FastHenry beside l2_layout's)."""
    from moduleforge.generate import perturb as P
    pr = asm["pair_rows"]
    counted = {}
    for r in pr:
        counted.setdefault(r["pair"], {"kind": r["kind"], "components": r["components"], "reference": r["reference"],
                                       "ok": True})
        counted[r["pair"]]["ok"] &= not r["excluded_f1"]
    ok = {k: v for k, v in counted.items() if v["ok"]}
    per_type = {}
    for t in [*P.MOVE_TYPES, P.COMPOUND]:
        n_all = sum(v["kind"] == t for v in counted.values())
        n_ok = sum(v["kind"] == t for v in ok.values())
        per_type[t] = {"pairs": n_all, "counted": n_ok, "excluded": n_all - n_ok,
                       "zero_failure_bound95": zero_failure_bound(n_ok)}
    refs = sorted({v["reference"] for v in ok.values()})
    rfh = [r["r_fh"] for r in pr if not r["excluded_f1"] and math.isfinite(r["r_fh"])]
    rl1 = [r["r_L1"] for r in pr]
    l1_vs_fh = [abs(r["r_L1"] / r["r_fh"] - 1) for r in pr if math.isfinite(r["r_fh"])]
    return {"n_pairs": len(counted), "n_counted": len(ok), "coverage_after_exclusion": len(ok) / max(1, len(counted)),
            "per_move_type": per_type, "pooled_zero_failure_bound95": zero_failure_bound(len(ok)),
            "clustered_zero_failure_bound95": zero_failure_bound(len(refs)),
            "covered_range_fh_finest": [min(rfh), max(rfh)] if rfh else None,
            "registered_range_l1": [min(rl1), max(rl1)] if rl1 else None,
            "F8_l1_max_ratio_diff_vs_fasthenry": max(l1_vs_fh) if l1_vs_fh else None}


def fh_selftest_record(work: Path) -> dict:
    """fasthenry_run.self_test() once on this host (review T0427/T0428 B(1)), stored keyed by binary_sha256 under the run
    directory; {'ok': False, 'error': ...} if the binary is missing or the self-test fails."""
    from moduleforge.solvers import fasthenry_run as FR
    host = os.uname().nodename
    try:
        rec = FR.self_test()
        rec.update(ok=True, host=host)
    except Exception as e:  # SelfTestError, FileNotFoundError (not provisioned)
        rec = {"ok": False, "host": host, "error": f"{type(e).__name__}: {e}"}
    d = work / "fh_selftest"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{host}__{str(rec.get('binary_sha256', 'none'))[:16]}.json").write_text(json.dumps(rec, indent=1, default=str))
    return rec


def stage_solve(run, cfg: dict, smoke: bool, reg: dict) -> dict:
    """Solve stage (T0389): l2_layout ladder and P3 terms, FastHenry ladder and thickness ladder on every layout (smoke:
    the coarsest level of each ladder on one Case 4 development pair and its reference), estimators, F1, rows, criteria,
    INVALID rule, diagnostics.  F2: in smoke nothing is solved on 2D_Case_2R or 2D_Case_6."""
    from moduleforge.generate import perturb as P
    from moduleforge.solvers.fasthenry import FHLevel, export
    work = run.run_dir / "solve"
    work.mkdir(parents=True, exist_ok=True)
    rec: dict = {"mode": "smoke" if smoke else "registered"}
    chk = step_rule_check(smoke)
    run.sanity("ratio_step_rule_validated", passed=chk["passed"], value=chk["value"], threshold=chk["threshold"],
               detail=chk["detail"])
    step_fn, rec["step_rule_source"] = step_rule(smoke)
    # layouts: rebuilt from the registration records (fingerprints checked below)
    if smoke:
        ref, _rules = case4_reference()
        refs = {"2D_Case_4": ref}
        pick = [p for p in reg["pairs"] if p["slot"] == 0][:1]
        if not pick:  # review T0447/T0448 (3): no pair drawn -> a failed draw, recorded, not a crash
            rec["failed_draw"] = "no development pair drawn in slot 0"
        pairs = [dict(p, name="dev_pair0", ref_name="2D_Case_4") for p in pick]
    else:
        refs = {}
        recon = recon_module()
        for e in cfg["references"]:
            refs[e["reference_id"]] = recon.snapped(e["reference_id"])[0]
        pairs = [dict(p, name=p["pair"].replace("#", "_p"), ref_name=p["reference"]) for p in reg["pairs"]]
        if reg["proxy"].get("status") == "built":
            pairs.append(dict(reg["proxy"]["record"], name="2D_Case_2R_proxy", ref_name="2D_Case_2R"))
    layouts = dict(refs)
    geo_bad = []
    for p in pairs:
        lay = P.apply(refs[p["ref_name"]], p["kind"], p["params"]) if p["kind"] != "proxy" else p["layout"]
        if lay.fingerprint() != p["fingerprint"]:
            geo_bad.append(f"{p['name']}: rebuilt fingerprint differs from the registration record")
        layouts[p["name"]] = lay
    jobs = solve_jobs(cfg, layouts, smoke)
    rec["jobs"] = jobs
    budget = float(os.environ.get("MF_E004_MEM_GB", cfg["solve"]["mem_budget_gb_default"]))
    st = fh_selftest_record(work)
    rec["fh_selftest"] = {st.get("binary_sha256", "none"): st}
    fh_jobs = [j for j in jobs if j["solver"] == "fasthenry"]
    run_list = jobs if st["ok"] else [j for j in jobs if j["solver"] != "fasthenry"]
    res = run_jobs(run_list, layouts, work, budget) if run_list else {}
    rec["results"] = res
    # checks that depend on no compared value
    pinned = cfg["solve"]["fasthenry"]["pinned_binary_sha256"]
    shas = {r.get("binary_sha256") for j in fh_jobs if (r := res.get(j["id"])) and r.get("binary_sha256")}
    pin_ok = st["ok"] and st.get("binary_sha256") == pinned and shas <= {pinned}
    run.sanity("fasthenry_binary_pinned", passed=bool(pin_ok), value=None, threshold=None,
               detail=f"self-test on {st.get('host')}: {st.get('ok')} ({st.get('error', st.get('banner', ''))}); binary "
                      f"{st.get('binary_sha256')}; FHResult binaries {sorted(shas)}; pinned {pinned}")
    hl = st.get("L_nH_1kHz")
    cf_ok = hl is not None and abs(hl - cfg["solve"]["fasthenry"]["self_test_exact_nH"]) <= \
        cfg["solve"]["fasthenry"]["self_test_exact_tol_nH"]
    run.sanity("fasthenry_closed_form_validated", passed=bool(cf_ok), value=hl,
               threshold=cfg["solve"]["fasthenry"]["self_test_exact_nH"],
               detail="D0002 bar at 1 kHz against the exact uniform-current (Hoer-Love) 5.704254 nH, recomputed here from "
                      "the self-test record")
    for j in fh_jobs:  # the deck each FHResult solved is the one the layout exports now (identical geometry)
        r = res.get(j["id"])
        if r and r.get("deck_sha256"):
            d, _f = export(layouts[j["layout"]], FHLevel(**j["fh_level"]), die_model=j["die_model"],
                           terminal_model=j["terminal_model"])
            if hashlib.sha256(d.encode()).hexdigest() != r["deck_sha256"]:
                geo_bad.append(f"{j['id']}: solved deck sha256 differs from the layout's export")
    for j in jobs:
        r = res.get(j["id"])
        if r and r.get("fingerprint") not in (None, layouts[j["layout"]].fingerprint()):
            geo_bad.append(f"{j['id']}: solved fingerprint differs")
    run.sanity("exported_geometry_identical", passed=not geo_bad, value=len(geo_bad), threshold=0,
               detail=geo_bad[:20] or "every l2_layout and FastHenry solve read the registered layout (fingerprint), "
                                      "every FastHenry deck re-exported to the same sha256")
    ref_of = {p["name"]: p["ref_name"] for p in pairs}
    asm = assemble(cfg, [dict(p) for p in pairs], ref_of, res, jobs, smoke, step_fn)
    crit = criteria(asm, cfg) if pairs else {}
    missing = crit.get("pairs_missing_finest", [p["name"] for p in pairs])
    k1_fires = crit.get("K1_fires", False)
    run.sanity("finest_values_present", passed=(not missing and bool(pairs)) or k1_fires, value=len(missing), threshold=0,
               detail=("every pair has both finest values" if not missing else
                       f"pairs lacking a finest value: {missing}; K1 fires on a completed pair: {k1_fires}") +
                      " (F1: INVALID only if a pair lacks a finest value and no completed pair fires K1)")
    gm = [r["id"] for r in res.values() if r.get("status") == "gmres_flag"]
    crashed = [r["id"] for r in res.values() if r.get("crashed_every_attempt")]
    rec.update(assembly=asm, criteria=crit, l2_gmres_flagged_as_missing=gm, fh_crashed_every_attempt_as_missing=crashed)
    if pairs:
        diag = diagnostics(asm, cfg)
        rec["diagnostics"] = diag
        pr = asm["pair_rows"]
        cnt = [r for r in pr if r["finest_complete"]]
        b1 = ratio_band([r for r in pr if not r["excluded_f1"]], ("r_l2", "r_fh"), ("E_R_l2_rel", "E_R_fh_rel"))
        run.metric("max_ratio_diff_vs_fasthenry", crit["A1"], ci=b1 if math.isfinite(crit["A1"]) else None, n=len(pr))
        run.metric("max_ratio_diff_vs_fasthenry_all", crit["K1"],
                   ci=ratio_band(cnt, ("r_l2", "r_fh"), ("E_R_l2_rel", "E_R_fh_rel")), n=len(cnt))
        run.metric("max_abs_consistency", crit["A2"], n=len(asm["layout_rows"]))
        lcnt = [dict(r, el=r["E_l2"] / r["L_l2"], ef=r["E_fh"] / r["L_fh"]) for r in asm["layout_rows"]
                if r["finest_complete"]]
        run.metric("max_rel_diff_vs_fasthenry", crit["K2"], ci=ratio_band(lcnt, ("L_l2", "L_fh"), ("el", "ef")),
                   n=len(lcnt))
        run.metric("n_counted_pairs", diag["n_counted"], n=diag["n_pairs"])
        run.metric("pooled_zero_failure_bound95", diag["pooled_zero_failure_bound95"], n=diag["n_counted"])
        if diag["F8_l1_max_ratio_diff_vs_fasthenry"] is not None:
            run.metric("l1_max_ratio_diff_vs_fasthenry", diag["F8_l1_max_ratio_diff_vs_fasthenry"], n=len(cnt))
    run.metric("n_l2_gmres_flagged", len(gm), n=sum(j["solver"] == "l2_layout" for j in jobs))
    run.metric("n_fh_decks_crashed_every_attempt", len(crashed), n=len(fh_jobs))
    rows = [{k: v for k, v in r.items() if not k.startswith(("terms_", "ratio_per_level"))}
            for r in asm["pair_rows"] + asm["layout_rows"]]
    run.rows(rows)
    out = work / "solve.json"
    out.write_text(json.dumps(rec, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o)))
    run.artifact("solve.json", out)
    return rec


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


# ======================================================================== F7(a) FastHenry development mode (T0389)
F7_DIR = ROOT / "research" / "o004_f7"
GEN_DEV_SEED = 20261110  # E010 dev.dev_seed: gen2_0 = derivative.generate(halfbridge_housing_spec(2), 1, seed)[0]
F7A_LADDER_LAYOUTS = ("case4_base", "standin_compound", "dev03_trace_width")  # D0024 item 2 stand-in; a trace-edge move
F7A_WIRE_FINE = ("case4_base", "dev03_trace_width")  # k1 with the wire section refined once more (wire_n 8, wire_sub 4)
GEN2_DIAG = {"cell_mm": 0.5, "plane_cell_mm": 2.0, "wire_n": 2, "wire_sub": 2, "nh": (1, 3, 5)}  # founder T0417/T0418
VM = {"machine": "e2-highmem-16", "ram_gib": 128, "usable_gb": 108.0, "usd_per_h": 0.73,
      "source": "project/memory/lessons.md 2026-11-04 (e2-highmem-16 $0.73/h; n2-highmem-32 $2.10/h)"}


def dev_layout(name: str):
    """Development layouts only (F2): 2D_Case_4's base, a T0387 development pair (dev_pairs.json, fingerprint checked),
    or gen2_0 (E010's generator housing layout, development seed)."""
    from moduleforge.generate import derivative as D
    from moduleforge.generate import perturb as P
    if name == "case4_base":
        return case4_reference()[0]
    if name == "gen2_0":
        return D.generate(D.halfbridge_housing_spec(2), 1, GEN_DEV_SEED)[0]
    pr = next(p for p in json.loads((F7_DIR / "dev_pairs.json").read_text())["pairs"] if p["name"] == name)
    lay = P.apply(case4_reference()[0], pr["move_type"], pr["params"])
    if lay.fingerprint() != pr["fingerprint"]:
        raise RuntimeError(f"{name}: rebuilt fingerprint differs from dev_pairs.json (rules changed)")
    return lay


def stack_summary(lay) -> dict:
    st = lay.stack
    return {"kind": st.kind, "layers_mm": {la.name: round(la.thickness / MM, 4) for la in st.layers}}


def f7a_jobs(cfg: dict) -> tuple[list[dict], dict]:
    """The F7(a) job list: E004's FastHenry ladder (k0/k1/k2 at nh_lateral) and thickness ladder (3/5/9 at k1) on 2D_Case_4's
    base, the r <= 0.75 stand-in and a trace-edge move; k1 with a finer wire section on the trace-edge pair; the founder's
    gen2_0 thickness diagnostic (nh 1/3/5 at cell 0.5 mm, plane 2 mm, wire_sub 2) on gen2_0 and, at identical levels, on
    Case 4's base; l2_layout lat0.5 on gen2_0 for the gap rule.  Die model 'short' everywhere (no direct solve needed)."""
    from moduleforge.solvers.fasthenry import FHLevel, export
    names = sorted(set(F7A_LADDER_LAYOUTS) | {"gen2_0"})
    lays = {n: dev_layout(n) for n in names}
    jobs = [j for j in solve_jobs(cfg, {n: lays[n] for n in F7A_LADDER_LAYOUTS}, smoke=False) if j["solver"] == "fasthenry"]
    f = cfg["solve"]["fasthenry"]
    extra = [(n, "k1w", dict(fh_level(cfg, "k1", f["nh_lateral"]), wire_n=8, wire_sub=4)) for n in F7A_WIRE_FINE]
    extra += [(n, f"g{nh}", dict(cell_mm=GEN2_DIAG["cell_mm"], plane_cell_mm=GEN2_DIAG["plane_cell_mm"], nh_trace=nh,
                                 nh_plane=nh, rh=f["rh"], nw_trace=f["nw_trace"], wire_n=GEN2_DIAG["wire_n"],
                                 wire_sub=GEN2_DIAG["wire_sub"])) for n in ("gen2_0", "case4_base") for nh in GEN2_DIAG["nh"]]
    for n, key, kw in extra:
        _d, facts = export(lays[n], FHLevel(**kw), die_model=f["die_model"], terminal_model=f["terminal_model"])
        jobs.append(dict(id=f"{n}__fh_{key}", solver="fasthenry", layout=n, level=key, key=key, fh_level=kw, mode=f["mode"],
                         order=f["order"], tol=f["tol"], max_retries=f["max_retries"], die_model=f["die_model"],
                         terminal_model=f["terminal_model"], n_filaments_exporter=facts["n_filaments"],
                         deck_sha256=hashlib.sha256(_d.encode()).hexdigest(), fingerprint=lays[n].fingerprint(),
                         **fh_sizing(cfg, facts["n_filaments"])))
    jobs.append(dict(id="gen2_0__l2_lat0.5", solver="l2_layout", layout="gen2_0", level="lat0.5", key="lat0.5",
                     spec=l2_level(cfg, "lat0.5"), mem_proj_gb=cfg["solve"]["l2_layout"]["peak_gb"]["lat0.5"],
                     fingerprint=lays["gen2_0"].fingerprint()))
    return jobs, lays


def probe_deck(deck: str, args: list[str], mem_cap_mb: float, timeout_s: float, max_attempts: int = 3) -> dict:
    """Review T0427/T0428 A: run a multipole deck only until FastHenry prints 'Calling gmres' (past 'Forming sparse matrix
    preconditioner', where T0428's deterministic SIGSEGV happened), then stop it.  A crash is retried up to max_attempts;
    a deck that crashes on every attempt is recorded as such.  Peak RSS (ps) and wall time per attempt."""
    from moduleforge.solvers import fasthenry_run as FR
    b = FR.find_binary()
    atts = []
    for n in range(1, max_attempts + 1):
        d = Path(tempfile.mkdtemp(prefix="fhprobe_", dir=os.environ.get("TMPDIR")))
        (d / "deck.inp").write_text(deck)
        t0, peak, status = time.time(), 0.0, None
        with open(d / "run.log", "w") as log:
            p = subprocess.Popen([str(b), "deck.inp", *args], cwd=d, stdout=log, stderr=subprocess.STDOUT)
            while status is None:
                time.sleep(0.5)
                txt = (d / "run.log").read_text(errors="replace")
                rss = FR._rss_mb(p.pid) if p.poll() is None else 0.0
                peak = max(peak, rss)
                if "Calling gmres" in txt:
                    status = "past_preconditioner"
                elif p.poll() is not None:
                    status = "exited_ok_before_gmres" if p.returncode == 0 else "crash"
                elif rss > mem_cap_mb:
                    status = "killed_memory"
                elif time.time() - t0 > timeout_s:
                    status = "timeout"
            if p.poll() is None:
                p.kill()
                p.wait()
        atts.append(dict(n=n, status=status, wall_s=round(time.time() - t0, 2), peak_rss_mb=round(peak, 1),
                         exit_code=p.returncode, log_tail=txt[-300:]))
        shutil.rmtree(d, ignore_errors=True)
        if status != "crash":
            break
    return dict(attempts=atts, result=atts[-1]["status"] if atts[-1]["status"] != "crash" else
                f"crashed_every_attempt ({len(atts)} of {len(atts)})", binary=str(b))


def dev_fh_probe(cfg: dict, max_local_gb: float) -> dict:
    """Probe every multipole deck of the F7(a) job list whose projected peak fits ``max_local_gb``, one at a time; the rest
    are marked 'vm_first' (the first VM job probes them).  Checkpointed to research/o004_f7/fh_probe.json."""
    from moduleforge.solvers.fasthenry import FHLevel, export
    from moduleforge.solvers.fasthenry_run import mode_args
    out_p = F7_DIR / "fh_probe.json"
    state = json.loads(out_p.read_text()) if out_p.exists() else {"decks": {}}
    state["label"] = "RESEARCH ONLY, NOT EVIDENCE (T0389): multipole preconditioner probe, development geometry (F2)"
    jobs, lays = f7a_jobs(cfg)
    # E004's own ladder decks (Case 4) first, then the gen2_0 diagnostic (its preconditioner is ~15x slower per filament)
    for j in sorted((j for j in jobs if j["solver"] == "fasthenry"),
                    key=lambda j: (j["layout"] == "gen2_0", j["n_filaments_exporter"])):
        if j["deck_sha256"] in state["decks"]:
            continue
        if j["mem_proj_gb"] > max_local_gb:
            state["decks"][j["deck_sha256"]] = dict(id=j["id"], result="vm_first", mem_proj_gb=j["mem_proj_gb"],
                                                    n_filaments=j["n_filaments_exporter"])
            continue
        deck, _f = export(lays[j["layout"]], FHLevel(**j["fh_level"]), die_model=j["die_model"],
                          terminal_model=j["terminal_model"])
        print(f"probe {j['id']} ({j['n_filaments_exporter']} filaments)", flush=True)
        r = probe_deck(deck, mode_args(j["mode"], j["order"], j["tol"]), mem_cap_mb=max_local_gb * 1024,
                       timeout_s=j["timeout_s"])
        state["decks"][j["deck_sha256"]] = dict(id=j["id"], n_filaments=j["n_filaments_exporter"], **r)
        out_p.write_text(json.dumps(state, indent=1))
    return state


def dev_fh_direct_mem(out_p: Path) -> dict:
    """Review T0445: direct FastHenry runs above 5k filaments, peak_mem_mb / (direct_mem_est_gb x 1024) per run, so the
    adapter's MEM_MARGIN can be refitted on an in-repo basis (research/o004_f7/fh_direct_mem.json)."""
    from moduleforge.solvers import fasthenry_run as FR
    from moduleforge.solvers.fasthenry import FHLevel, export
    runs = []
    for name, kw in (("case4_base", dict(cell_mm=1.0, plane_cell_mm=4.0, wire_n=2, wire_sub=1)),
                     ("standin_compound", dict(cell_mm=1.0, plane_cell_mm=4.0, wire_n=2, wire_sub=2)),
                     ("case4_base", dict(cell_mm=1.0, plane_cell_mm=3.0, wire_n=2, wire_sub=1))):
        lay = dev_layout(name)
        deck, facts = export(lay, FHLevel(**kw))
        r = FR.solve_deck(deck, mode="direct", facts=facts, timeout_s=1800, mem_cap_mb=4500)
        a = r.attempts[-1] if r.attempts else None
        runs.append(dict(layout=name, level=kw | {"nh_trace": 1, "nh_plane": 1}, status=r.status,
                         filaments=facts["n_filaments"], direct_mem_est_gb=facts["direct_mem_est_gb"],
                         peak_mem_mb=a.peak_mem_mb if a else None, mem_polled=a.mem_polled if a else None,
                         wall_s=a.wall_s if a else None, ratio=(a.peak_mem_mb / (facts["direct_mem_est_gb"] * 1024))
                         if a else None, binary_sha256=r.binary_sha256, host=os.uname().nodename))
        print(runs[-1], flush=True)
    rec = {"label": "RESEARCH ONLY (T0389, review T0445): direct-mode peak memory against the exporter's dense estimate",
           "ratio_definition": "peak_mem_mb / (direct_mem_est_gb * 1024); peak_mem_mb is the adapter's max(ps RSS poll, "
                               "ru_maxrss)", "runs": runs,
           "ratio_max": max((r["ratio"] for r in runs if r["ratio"]), default=None)}
    out_p.write_text(json.dumps(rec, indent=1))
    return rec


def makespan(jobs: list[dict], budget_gb: float) -> float:
    """Greedy list schedule by projected memory (largest first) on one machine: projected wall time (s)."""
    t, running, pend = 0.0, [], sorted(jobs, key=lambda j: -j["mem_proj_gb"])
    while pend or running:
        for j in list(pend):
            if sum(m for _e, m in running) + j["mem_proj_gb"] <= budget_gb:
                running.append((t + j["time_proj_s"], j["mem_proj_gb"]))
                pend.remove(j)
        if not running:
            raise RuntimeError("a job does not fit the machine")
        running.sort()
        t = running.pop(0)[0]
    return t


def dev_fh_plan(cfg: dict) -> dict:
    """Write research/o004_f7/vm_jobs_fasthenry.json: the F7(a) job list with deck facts, explicit caps, projections, the
    preconditioner probe's result per deck, the gap rule, and E004's cost plan (filament counts of the judged references'
    decks: geometry export only, no solve, F2)."""
    from moduleforge.solvers.fasthenry import FHLevel, export
    jobs, lays = f7a_jobs(cfg)
    probe = json.loads((F7_DIR / "fh_probe.json").read_text())["decks"] if (F7_DIR / "fh_probe.json").exists() else {}
    for j in jobs:
        if j["solver"] == "fasthenry":
            pr = probe.get(j["deck_sha256"], {"result": "vm_first: not probed locally (T0389's wall time), probed by the "
                                                         "first VM step"})
            j["precond_probe"] = pr["result"]
            j["probe_peak_rss_mb"] = max((a["peak_rss_mb"] for a in pr.get("attempts", [])), default=None)
            if pr["result"].startswith("crashed_every_attempt"):
                j["on_crash"] = ("no direct fallback (O004 F1; direct needs ~%.0f GB): a missing value, +inf estimate "
                                 "(F1 exclusion); never another level" % (8 * j["n_filaments_exporter"] ** 2 / 1e9))
        else:
            j.update(time_proj_s=cfg["solve"]["l2_layout"]["wall_s"]["lat0.5"], precond_probe="n/a (l2_layout)")
    # per-layout time calibration from the local probes: measured wall time to 'Calling gmres' over the projected total
    # (a lower bound on the true factor); applied to that layout's projections and timeouts (gen2_0: ~15x, T0389)
    s = cfg["solve"]["fasthenry"]["sizing"]
    fac: dict = {}
    for j in jobs:
        pr = probe.get(j.get("deck_sha256"), {})
        for a in pr.get("attempts", []):
            if a["status"] == "past_preconditioner":
                fac[j["layout"]] = max(fac.get(j["layout"], 1.0), a["wall_s"] / j["time_proj_s"])
    for j in jobs:
        if j["solver"] == "fasthenry" and fac.get(j["layout"], 1.0) > 1.0:
            j["time_calibration"] = fac[j["layout"]]
            j["time_proj_s"] *= fac[j["layout"]]
            j["timeout_s"] = max(s["min_timeout_s"], s["timeout_factor"] * j["time_proj_s"])
    fh = [j for j in jobs if j["solver"] == "fasthenry"]
    span = makespan(jobs, VM["usable_gb"])
    # E004 cost plan: per judged reference, the k2 / t9 deck sizes (export only); 15 layouts (2 references, 12 pairs, proxy)
    recon = recon_module()
    ref_sizes = {}
    for e in cfg["references"]:
        lay = recon.snapped(e["reference_id"])[0]
        ref_sizes[e["reference_id"]] = {"stack": stack_summary(lay)}
        for k, nh in [(k, cfg["solve"]["fasthenry"]["nh_lateral"]) for k in FH_LADDER] + [("k1", 3), ("k1", 9)]:
            _d, fc = export(lay, FHLevel(**fh_level(cfg, k, nh)))
            ref_sizes[e["reference_id"]][f"{k}_nh{nh}"] = dict(n_filaments=fc["n_filaments"],
                                                                **fh_sizing(cfg, fc["n_filaments"]))
    e004_jobs = []
    for rid, s in ref_sizes.items():
        n_lay = 7 if rid == "2D_Case_6" else 8  # 6 pairs + reference (+ the 2R proxy pair)
        for key, v in s.items():
            if key != "stack":
                e004_jobs += [dict(mem_proj_gb=v["mem_proj_gb"], time_proj_s=v["time_proj_s"])] * n_lay
        l2 = cfg["solve"]["l2_layout"]
        e004_jobs += [dict(mem_proj_gb=l2["peak_gb"][lv], time_proj_s=l2["wall_s"][lv]) for lv in L2_ALL] * n_lay
    e_span = makespan(e004_jobs, VM["usable_gb"])
    plan = {
        "label": "F7(a) FastHenry job list for the founder's burst VM (T0389). RESEARCH / DEVELOPMENT ONLY (O004 F2): "
                 "2D_Case_4 and gen2_0, development seeds; no FastHenry on 2D_Case_2R or 2D_Case_6 before registration",
        "command": "uv run python experiments/runners/e004_run.py --dev-fh-run research/o004_f7/vm_jobs_fasthenry.json "
                   "(on the VM: MF_E004_MEM_GB=108; resumes from research/o004_f7/fh_solves)",
        "first_vm_step": "the probe of every deck marked precond_probe = vm_first: `e004_run.py --dev-fh-probe 108` "
                         "before the full runs (review T0427/T0428 A)",
        "binary": {"pinned_sha256": cfg["solve"]["fasthenry"]["pinned_binary_sha256"],
                   "rule": "fasthenry_run.self_test() once per host, stored keyed by binary_sha256 beside every result"},
        "levels": cfg["solve"]["fasthenry"], "gen2_diag_levels": GEN2_DIAG,
        "die_model": "short on every job (no distributed-die deck: no direct solve is needed or projected, T0385 (2))",
        "wire_rule": "no job uses wire_n = 1 with wire_sub = 1 (T0385 (1)); each job records wire_n and wire_sub",
        "layouts": {n: {"fingerprint": lay.fingerprint(), "stack": stack_summary(lay)} for n, lay in lays.items()},
        "gap_rule": {
            "quantity": "g(X) = L_FH(X, nh 5 at cell 0.5 mm, plane 2 mm, wire 2/2) / L_l2(X, lat0.5) - 1 at 10 and 20 MHz, "
                        "X in {gen2_0, case4_base}; T(X) = 3 |L_FH(nh 5) - L_FH(nh 3)| / L_FH(nh 5) (two-level, p = 1)",
            "closes_if": "|g(gen2_0)| <= |g(case4_base)| + 0.02 (Case 4's few percent, measured at identical levels) AND "
                         "T(gen2_0) <= 0.01 (the thickness term inside the 1 % estimate), at both frequencies",
            "otherwise": "the thin-stack gap stays open: no non-Case-4 FastHenry deck is relied on and E004's nh_lateral is "
                         "revisited by the founder before registration (T0417/T0418)"},
        "always_crash_rule": "a multipole deck that crashes on every attempt (retries up to 10; the adapter stops early "
                             "on a repeated identical exit) has no value: no direct fallback (O004 F1: direct needs "
                             "8 F^2 bytes, far above any machine for these decks), no other level substituted; F1 makes "
                             "the affected estimate +inf (exclusion), a missing finest value goes to the INVALID rule",
        "memory_rule": "mem_proj_gb = kb_per_filament x exporter filaments x mem_margin (config.solve.fasthenry.sizing; "
                       "margin covers FastHenry's post-refinement growth, unknown before the run, T0385 (3)); every "
                       "attempt's peak_mem_mb and wall_s are recorded",
        "jobs": jobs,
        "projection": {"vm": VM, "n_jobs": len(jobs), "fh_cpu_h": sum(j["time_proj_s"] for j in fh) / 3600,
                       "makespan_h": span / 3600, "usd": span / 3600 * VM["usd_per_h"],
                       "uncertainty": "time +-25 % (P4 contention) and the 1.40 exponent extrapolated from 25k-102k "
                                      "filaments to ~1M: treat k2 times as +-50 %"},
        "e004_cost_plan": {"reference_deck_sizes": ref_sizes, "n_layouts": 15,
                           "cpu_h": sum(j["time_proj_s"] for j in e004_jobs) / 3600, "makespan_h": e_span / 3600,
                           "usd": e_span / 3600 * VM["usd_per_h"],
                           "note": "pairs sized as their reference; l2_layout at the measured Case 4 peaks (15.9 GB at "
                                   "0.25 mm, T0387), a conservative bound for 2R / Case 6 (Case 6 0.25 mm: 4.75 GB)"},
        "direct_mem": "research/o004_f7/fh_direct_mem.json",
    }
    (F7_DIR / "vm_jobs_fasthenry.json").write_text(json.dumps(plan, indent=1, default=str))
    return plan["projection"] | {"e004": {k: v for k, v in plan["e004_cost_plan"].items() if k != "reference_deck_sizes"}}


def dev_fh_run(job_file: Path) -> None:
    """Run the job list (burst VM, the founder): self-test once per host, then every job not yet done, packed by memory
    (MF_E004_MEM_GB), results checkpointed under research/o004_f7/fh_solves/."""
    plan = json.loads(job_file.read_text())
    lays = {n: dev_layout(n) for n in plan["layouts"]}
    for n, v in plan["layouts"].items():
        if lays[n].fingerprint() != v["fingerprint"]:
            raise RuntimeError(f"{n}: fingerprint differs from the job list")
    work = F7_DIR / "fh_solves"
    st = fh_selftest_record(work)
    if not st["ok"]:
        raise RuntimeError(f"FastHenry self-test failed on this host: {st}")
    run_jobs(plan["jobs"], lays, work, float(os.environ.get("MF_E004_MEM_GB", "5")))


# ------------------------------------------------------------------------------------------------------------------ main
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--smoke", action="store_true", help="development seed, development geometry, L1 only, temp run dir")
    ap.add_argument("--stage", choices=("registration", "solve", "all"), default="all")
    ap.add_argument("--dev-span-sim", type=int, default=0, metavar="N", help="research: span check on N dev seeds")
    ap.add_argument("--out", default=str(ROOT / "research" / "o004_e004" / "span_sim_case4.json"))
    ap.add_argument("--print-freeze", action="store_true", help="print the current tree's freeze values (not evidence)")
    ap.add_argument("--child", metavar="JOB_JSON", help=argparse.SUPPRESS)
    ap.add_argument("--dev-fh-plan", action="store_true", help="research: write research/o004_f7/vm_jobs_fasthenry.json")
    ap.add_argument("--dev-fh-probe", type=float, default=0.0, metavar="GB",
                    help="research: preconditioner probe of the F7(a) decks projected below GB")
    ap.add_argument("--dev-fh-direct-mem", action="store_true", help="research: direct-mode peak / estimate runs")
    ap.add_argument("--dev-fh-run", metavar="JOB_LIST", help="research (burst VM): run the F7(a) job list")
    a = ap.parse_args()
    if a.child:
        return child_solve(a.child)
    if a.dev_fh_plan or a.dev_fh_probe or a.dev_fh_direct_mem or a.dev_fh_run:
        import yaml
        cfg = yaml.safe_load(SPEC_DRAFT.read_text())["config"]
        if a.dev_fh_probe:
            st = dev_fh_probe(cfg, a.dev_fh_probe)
            print(json.dumps({v["id"]: v["result"] for v in st["decks"].values()}, indent=1))
        if a.dev_fh_direct_mem:
            print(json.dumps(dev_fh_direct_mem(F7_DIR / "fh_direct_mem.json"), indent=1, default=str))
        if a.dev_fh_plan:
            print(json.dumps(dev_fh_plan(cfg), indent=1, default=str))
        if a.dev_fh_run:
            dev_fh_run(Path(a.dev_fh_run))
        return 0
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
        sol = {}
        if a.stage in ("solve", "all"):
            sol = stage_solve(run, cfg, a.smoke, rec)
        else:
            for name in SOLVE_CHECKS:
                run.sanity(name, passed=False, detail="not run: --stage registration")
        print(json.dumps({"run_dir": str(run.run_dir), "checks": {k: v["passed"] for k, v in rec["checks"].items()},
                          "coverage": {k: v["covered"] for k, v in rec["coverage"].items()},
                          "proxy": rec["proxy"]["status"], "wall_s": round(rec["wall_s"], 1),
                          "solve": {k: v for k, v in sol.get("criteria", {}).items()},
                          "solve_status": {r["id"]: r.get("status") for r in sol.get("results", {}).values()}},
                         indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
