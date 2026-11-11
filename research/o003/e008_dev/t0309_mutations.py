"""T0309: mutation check of the E008 runner selftest (experiments/runners/e008_run.py --selftest).

Each mutant puts back one behaviour that reviews T0307/T0308 flagged (or a falsified dev thermal report) by a text
substitution in the runner source, executes the mutated source as a module with the runner's own __file__ (so ROOT and
the spec resolve as usual; nothing on disk changes), runs selftest() and records its return code and FAIL lines.  The
selftest protects a fix only if the mutant makes it fail (rc 1).  Fake solvers only; no layout is solved.
Run: uv run python research/o003/e008_dev/t0309_mutations.py [--out research/o003/e008_dev/t0309_mutations.json]
"""
from __future__ import annotations

import contextlib
import io
import json
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RUNNER = ROOT / "experiments/runners/e008_run.py"

MUTANTS = {
    "M1_spot_ref_ignores_admissibility (T0307 f1, T0308 f2)": (
        "rid = next((rc.rid for rc in refs if rc.stack_type == st and rc.admissible), None)",
        "rid = next((rc.rid for rc in refs if rc.stack_type == st), None)"),
    "M2_stack_type_ignores_per_die_thickness (T0308 f1)": (
        '"die_thickness_attach_m": _die_thicknesses(dies)})',
        '"die_thickness_attach_m": []})'),
    "M3_plain_max_drops_nan (T0308 f5)": (
        "return math.nan if any(math.isnan(v) for v in vals) else max(vals, default=0.0)",
        "return max(vals, default=0.0)"),
    "M4_fv_picard_not_folded (T0307 f0)": (
        'pc_vals += [f.get("picard_dT_K", math.nan) for f in fv]',
        "pc_vals += []"),
    "M5_within_ignores_nan (T0308 f5)": (
        "return math.isfinite(v) and v <= tol",
        "return not v > tol"),
    "M6_thermal_report_all_attainable (T0309 item 4)": (
        '"self_margin_K": b[2] - b[3], "attainable": bool(b[2] - b[3] <= limit)}',
        '"self_margin_K": b[2] - b[3], "attainable": True}'),
    "M7_thermal_report_t0308_falsified (T0308 f0)": (
        "e.update(margin_vs_twin_K=b[2] - tw[3], passes_vs_twin=bool(b[2] - tw[3] <= limit))",
        "e.update(margin_vs_twin_K=0.0, passes_vs_twin=True)"),
    "M8_guard_matches_die_spacing (T0307 f4)": (
        "and k not in NOT_NET_SPACING and _num(v)",
        "and _num(v)"),
}


def run_mutant(src: str, name: str) -> dict:
    mod = types.ModuleType(f"e008_mut_{abs(hash(name))}")
    mod.__file__ = str(RUNNER)
    sys.modules[mod.__name__] = mod
    buf = io.StringIO()
    err = None
    with contextlib.redirect_stdout(buf):
        exec(compile(src, str(RUNNER), "exec"), mod.__dict__)  # noqa: S102 - the repository's own runner source
        try:
            rc = mod.selftest()
        except Exception as e:  # noqa: BLE001 - a selftest that raises does not pass (exit status 1 from the CLI)
            rc, err = 1, f"{type(e).__name__}: {e}"
    fails = [ln for ln in buf.getvalue().splitlines() if ln.startswith("FAIL")]
    return {"rc": rc, "raised": err, "n_fail": len(fails), "fail_lines": fails[:8]}


def main() -> int:
    out_path = Path(sys.argv[sys.argv.index("--out") + 1]) if "--out" in sys.argv else None
    base = RUNNER.read_text()
    res = {"runner_sha256_of_unmutated": __import__("hashlib").sha256(base.encode()).hexdigest(),
           "unmutated": run_mutant(base, "base"), "mutants": {}}
    for name, (a, b) in MUTANTS.items():
        if base.count(a) != 1:
            res["mutants"][name] = {"error": f"pattern found {base.count(a)} times"}
            continue
        res["mutants"][name] = run_mutant(base.replace(a, b), name) | {"caught": None}
        res["mutants"][name]["caught"] = res["mutants"][name]["rc"] != 0
        print(name, "rc", res["mutants"][name]["rc"], "fails", res["mutants"][name]["n_fail"], flush=True)
    ok = res["unmutated"]["rc"] == 0 and all(m.get("caught") for m in res["mutants"].values())
    res["all_caught_and_base_passes"] = ok
    print(json.dumps(res, indent=1))
    if out_path:
        out_path.write_text(json.dumps(res, indent=1))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
