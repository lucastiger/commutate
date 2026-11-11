"""T0311: mutation check of the E008 runner selftest after review T0310 (experiments/runners/e008_run.py --selftest).

Same method as t0309_mutations.py (whose run_mutant this imports): each mutant puts back one behaviour by a text
substitution in the runner source, executes the mutated source as a module with the runner's own __file__, runs
selftest() and records its return code and FAIL lines.  The selftest protects a fix only if the mutant makes it fail
(rc 1).  N1-N10 are the behaviours T0310 findings 0-3 say the selftest could not tell apart; M1-M8 are T0309's mutants,
re-run on the changed runner (M2's pattern follows the renamed signature key).  Fake solvers only; nothing is solved.
Run: uv run python research/o003/e008_dev/t0311_mutations.py [--out research/o003/e008_dev/t0311_mutations.json]
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
_sp = importlib.util.spec_from_file_location("t0309_mutations", HERE / "t0309_mutations.py")
T9 = importlib.util.module_from_spec(_sp)
_sp.loader.exec_module(T9)
RUNNER = T9.RUNNER

MUTANTS = {
    # T0310 finding 0: any admissible reference instead of the first one
    "N1_spot_ref_last_admissible (T0310 f0)": (
        "rid = next((rc.rid for rc in refs if rc.stack_type == st and rc.admissible), None)",
        "rid = next((rc.rid for rc in reversed(refs) if rc.stack_type == st and rc.admissible), None)"),
    # T0310 finding 1: a finite-volume record without picard_dT_K counted as 0 K instead of NaN
    "N2_missing_picard_counts_zero (T0310 f1)": (
        'pc_vals += [f.get("picard_dT_K", math.nan) for f in fv]',
        'pc_vals += [f.get("picard_dT_K", 0.0) for f in fv]'),
    # T0310 finding 2: plain max() in the F6(e) maxima, a NaN-unsafe aggregate, no non-finite guard
    "N3_per_type_a3_plain_max_over_dies (T0310 f2)": (
        "a3s[st] = _worst(_a3_die(", "a3s[st] = max(_a3_die("),
    "N4_aggregate_value_plain_max (T0310 f2)": (
        'all(_within(v, g["a3_max"]) for v in a3s.values()), _worst(a3s.values()),',
        'all(_within(v, g["a3_max"]) for v in a3s.values()), max(a3s.values()),'),
    "N5_aggregate_pass_nan_unsafe (T0310 f2)": (
        'ck("F6e_stack_type_spot_check", all(_within(v, g["a3_max"]) for v in a3s.values()),',
        'ck("F6e_stack_type_spot_check", max(a3s.values()) <= g["a3_max"],'),
    "N6_no_nonfinite_guard_in_a3 (T0310 f2)": (
        "    if not all(math.isfinite(v) for v in vals):\n        return math.nan\n", ""),
    # T0310 finding 3: the signature rounding rule
    "N7_thickness_exact_float (T0310 f3)": (
        "return int(round(float(t) / SIG_THICKNESS_QUANTUM_M))", "return float(t)"),
    "N8_k_exact_float (T0310 f3)": (
        'return format(float(k), f".{SIG_K_SIGNIFICANT_DIGITS - 1}e")', "return repr(float(k))"),
    "N9_thickness_quantum_10um (T0310 f3)": (
        "SIG_THICKNESS_QUANTUM_M = 1e-9", "SIG_THICKNESS_QUANTUM_M = 1e-5"),
    "N10_k_5_digits (T0310 f3)": (
        "SIG_K_SIGNIFICANT_DIGITS = 9", "SIG_K_SIGNIFICANT_DIGITS = 5"),
    **{k: v for k, v in T9.MUTANTS.items() if not k.startswith("M2_")},
    "M2_stack_type_ignores_per_die_thickness (T0308 f1)": (
        '"die_thickness_attach_nm": _die_thicknesses(dies)})', '"die_thickness_attach_nm": []})'),
}


def main() -> int:
    out_path = Path(sys.argv[sys.argv.index("--out") + 1]) if "--out" in sys.argv else None
    base = RUNNER.read_text()
    res = {"runner_sha256_of_unmutated": hashlib.sha256(base.encode()).hexdigest(),
           "unmutated": T9.run_mutant(base, "base"), "mutants": {}}
    for name, (a, b) in MUTANTS.items():
        if base.count(a) != 1:
            res["mutants"][name] = {"error": f"pattern found {base.count(a)} times", "caught": False}
            continue
        r = T9.run_mutant(base.replace(a, b), name)
        res["mutants"][name] = r | {"caught": r["rc"] != 0}
        print(name, "rc", r["rc"], "fails", r["n_fail"], "raised", r["raised"], flush=True)
    ok = res["unmutated"]["rc"] == 0 and all(m.get("caught") for m in res["mutants"].values())
    res["all_caught_and_base_passes"] = ok
    if out_path:
        out_path.write_text(json.dumps(res, indent=1) + "\n")
    print("all_caught_and_base_passes", ok)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
