"""Mutation check of research/o003/test_headroom_metrics.py against research/o003/headroom_metrics.py (T0269).

Each mutant is a textual edit of the draft, applied to an in-memory copy (the file on disk is never touched), exec'd as the
module ``headroom_metrics`` and tested by running the test file. The script exits 0 only if every mutant makes at least one
test fail. A mutant whose anchor text is not found exactly the stated number of times, one that does not compile, and a
pytest run that ends in anything but "passed" (0) or "tests failed" (1) are errors (exit 2), never counted as killed.
Run from the repository root: uv run python research/o003/check_mutants.py"""
from __future__ import annotations

import contextlib
import io
import sys
import types
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
SOURCE = HERE / "headroom_metrics.py"
TESTS = HERE / "test_headroom_metrics.py"
TEST_MODULE = "test_headroom_metrics"

# (name, old text, new text, occurrences of old text). The first eleven stand for T0266's 11 surviving mutants. T0266's
# text names ten of them explicitly (A1 w = e_R + s_ref; F1(a1) e_R not doubled; F1(a1) on the 0.5 mm column; F1(a2)
# max instead of sum; levelling w = s_ref; levelling with the comparator pair; reconstruction secondary testing Tj
# against the reconstruction; reversed tie-break; floor ignored; tj_limit_K ignored). The eleventh is not named there;
# a1_best_eR_ignores_comparator is attempt 1's reconstruction of it. The other plausible readings of the eleventh
# (another dropped, undoubled or mis-paired band term in A1 or K1) are in the list below as well.
MUTANTS: list[tuple[str, str, str, int]] = [
    # --- T0266's 11 survivors ---------------------------------------------------------------------------------------
    ("a1_w_is_eR_plus_sref", "h_lo=headroom_lo(a, r, 2.0 * e + s_ref))", "h_lo=headroom_lo(a, r, e + s_ref))", 1),
    ("gate_a1_eR_not_doubled", "<= 2.0 * ratio_band_estimate(twin5, recon5) + s_ref",
     "<= ratio_band_estimate(twin5, recon5) + s_ref", 1),
    ("gate_a1_reads_0p5mm_column", "float(twin5[0]) / float(recon5[0])", "float(twin5[1]) / float(recon5[1])", 1),
    ("gate_a2_max_instead_of_sum", "<= twin[1] + recon[1]", "<= max(twin[1], recon[1])", 1),
    ("levelling_drops_eR", "w_lev = 2.0 * ratio_band_estimate(five(ind), five(twin)) + s_ref", "w_lev = s_ref", 1),
    ("levelling_uses_comparator_pair", "w_lev = 2.0 * ratio_band_estimate(five(ind), five(twin)) + s_ref",
     "w_lev = 2.0 * ratio_band_estimate(five(ind), five(comp)) + s_ref", 1),
    ("recon_secondary_tj_against_comparator", "if tj_conservative_ok(cb, tw_b, limit):",
     "if tj_conservative_ok(cb, tw_b if comp is twin else rec_b, limit):", 1),
    ("reversed_tie_break", 'key=lambda c: (lsub(c), str(c["layout_id"])))',
     'key=lambda c: (lsub(c), [-ord(ch) for ch in str(c["layout_id"])]))', 1),
    ("floor_param_ignored", 'floor = float(params.get("floor", 1e-3))', "floor = 1e-3", 1),
    ("tj_limit_param_ignored", 'limit = float(params.get("tj_limit_K", 2.0))', "limit = 2.0", 1),
    ("a1_best_eR_ignores_comparator", "e = ratio_band_estimate(five(best), five(comp))",
     "e = ratio_band_estimate(five(best), five(twin))", 1),
    # --- added: A1, K1 and the band estimator -------------------------------------------------------------------------
    ("a1_w_drops_eR", "h_lo=headroom_lo(a, r, 2.0 * e + s_ref))", "h_lo=headroom_lo(a, r, s_ref))", 1),
    ("a1_w_drops_sref", "h_lo=headroom_lo(a, r, 2.0 * e + s_ref))", "h_lo=headroom_lo(a, r, 2.0 * e))", 1),
    ("a_from_twin_always", "lc = lsub(comp)", "lc = lsub(twin)", 1),
    ("a_ignores_l_term", "a = lc / (lc + l_term)", "a = 1.0", 1),
    ("levelling_eR_not_doubled", "w_lev = 2.0 * ratio_band_estimate", "w_lev = 1.0 * ratio_band_estimate", 1),
    ("levelling_drops_sref", "(five(ind), five(twin)) + s_ref", "(five(ind), five(twin))", 1),
    ("levelling_strict", "levelled = l1_first <= (1.0 + w_lev) * l1_all", "levelled = l1_first < (1.0 + w_lev) * l1_all", 1),
    ("near_tie_w_ind_drops_eR", "w_ind = 2.0 * ratio_band_estimate(five(ind), five(comp)) + s_ref", "w_ind = s_ref", 1),
    ("near_tie_w_ind_eR_not_doubled", "w_ind = 2.0 * ratio_band_estimate", "w_ind = 1.0 * ratio_band_estimate", 1),
    ("near_tie_candidate_w_drops_eR", "wc = 2.0 * ratio_band_estimate(five(c), five(comp)) + s_ref", "wc = s_ref", 1),
    ("near_tie_candidate_w_shares_ind", "wc = 2.0 * ratio_band_estimate(five(c), five(comp)) + s_ref", "wc = w_ind", 1),
    ("near_tie_candidate_w_eR_not_doubled", "wc = 2.0 * ratio_band_estimate", "wc = 1.0 * ratio_band_estimate", 1),
    ("near_tie_vs_twin_not_comparator", "wc = 2.0 * ratio_band_estimate(five(c), five(comp))",
     "wc = 2.0 * ratio_band_estimate(five(c), five(twin))", 1),
    ("near_tie_band_strict", "if lsub(c) <= (1.0 + w_ind) * lsub(ind):", "if lsub(c) < (1.0 + w_ind) * lsub(ind):", 1),
    ("near_tie_takes_min", "h_hi=max(ties.values())", "h_hi=min(ties.values())", 1),
    ("a1_twin_rule_strict", "if best is None or lc <= lsub(best):", "if best is None or lc < lsub(best):", 1),
    ("k1_twin_rule_strict", "elif lc <= lsub(ind):", "elif lc < lsub(ind):", 1),
    ("a1_twin_rule_h_lo_sign", "h_lo=headroom_lo(a, 1.0, s_ref))", "h_lo=headroom_lo(a, 1.0, 0.0))", 1),
    ("k1_twin_rule_h_hi_no_sref", "h_hi=headroom_hi(a, 1.0, s_ref))\n        else:", "h_hi=headroom_hi(a, 1.0, 0.0))\n        else:", 1),
    ("f3_no_batch_stop", "            if eligible:\n                break\n", "", 1),
    ("f3_checks_twelve", "HR_SHORTLIST, HR_BATCH, HR_MAX_CHECKED = 16, 4, 8", "HR_SHORTLIST, HR_BATCH, HR_MAX_CHECKED = 16, 4, 12", 1),
    ("f3_batches_of_three", "HR_SHORTLIST, HR_BATCH, HR_MAX_CHECKED = 16, 4, 8", "HR_SHORTLIST, HR_BATCH, HR_MAX_CHECKED = 16, 3, 8", 1),
    ("a1_best_is_highest_eligible", "best = eligible[0] if eligible else None", "best = eligible[-1] if eligible else None", 1),
    ("a1_tj_tested_against_comparator_always", "if tj_conservative_ok(cb, tw_b, limit):",
     "if tj_conservative_ok(cb, tw_b if comp is twin else rec_b, limit) or True:", 1),
    ("conservative_test_uses_upper_of_twin", "return cand[2] - twin[3] <= limit_k", "return cand[2] - twin[2] <= limit_k", 1),
    ("conservative_test_strict", "return cand[2] - twin[3] <= limit_k", "return cand[2] - twin[3] < limit_k", 1),
    ("gate_a1_drops_sref", "<= 2.0 * ratio_band_estimate(twin5, recon5) + s_ref", "<= 2.0 * ratio_band_estimate(twin5, recon5)", 1),
    ("gate_a1_eR_twin_with_itself", "2.0 * ratio_band_estimate(twin5, recon5) + s_ref",
     "2.0 * ratio_band_estimate(twin5, twin5) + s_ref", 1),
    ("gate_a2_uses_twin_gci_only", "<= twin[1] + recon[1]", "<= twin[1]", 1),
    ("gate_a2_uses_lower_tj", "abs(twin[0] - recon[0])", "abs(twin[0] - recon[3])", 1),
    ("band_estimator_drops_lateral", "return 3.0 * abs(r025 - r05) + ratio_middle_term", "return ratio_middle_term", 1),
    ("band_estimator_lateral_factor_2", "return 3.0 * abs(r025 - r05)", "return 2.0 * abs(r025 - r05)", 1),
    ("band_estimator_drops_wire", "+ 3.0 * abs(r_wire - r05)", "", 1),
    ("band_estimator_wire_factor_2", "+ 3.0 * abs(r_wire - r05)", "+ 2.0 * abs(r_wire - r05)", 1),
    ("band_estimator_drops_thickness", "ratio_middle_term(r_thk_c, r05, r_thk_f) + ", "", 1),
    ("middle_term_factor_1", "return 1.25 * abs(e21) * rp / (rp - 1.0)", "return 1.0 * abs(e21) * rp / (rp - 1.0)", 1),
    ("middle_term_oscillatory_factor_2", "return 3.0 * max(abs(e21), abs(e32))", "return 2.0 * max(abs(e21), abs(e32))", 1),
    ("snapping_bias_factor_1", "s = 2.0 * abs(", "s = 1.0 * abs(", 1),
    ("snapping_check_min", "s = max(s, abs(", "s = min(s, abs(", 1),
    ("headroom_lo_sign", "return a * (1.0 - r * (1.0 + w))", "return a * (1.0 - r * (1.0 - w))", 1),
    ("headroom_hi_sign", "return a * (1.0 - r * (1.0 - w))", "return a * (1.0 - r * (1.0 + w))", 1),
    ("tj_lower_bound_uses_min", "lower = max(lower, f2 - g)", "lower = min(lower, f2 - g)", 1),
    ("tj_inf_gci_die_bounds_lower_at_its_t", "            n_inf += 1\n        else:", "            n_inf += 1\n            lower = max(lower, f2)\n        else:", 1),
    # --- added: die count (T0269) -------------------------------------------------------------------------------------
    ("die_count_unchecked_in_tj_bounds", "if n_dies is not None and len(dies) != n_dies:", "if False:", 1),
    ("die_count_not_passed_to_bounds", "floor, n_dies)", "floor)", 1),
    ("die_count_only_fewer_rejected", "len(dies) != n_dies", "len(dies) < n_dies", 1),
    ("die_count_only_more_rejected", "len(dies) != n_dies", "len(dies) > n_dies", 1),
    # --- added: fail closed ---------------------------------------------------------------------------------------------
    ("fail_open_inconsistent_l1", "        if l1_first < l1_all:\n            raise ValueError", "        if False:\n            raise ValueError", 1),
    ("fail_open_unknown_params", "    if unknown:\n        raise ValueError", "    if False:\n        raise ValueError", 1),
    ("fail_open_no_counted_a1", "    vals = [v[\"h_lo\"] for v in per.values() if v[\"counted\"]]\n    if not vals:\n        raise",
     "    vals = [v[\"h_lo\"] for v in per.values() if v[\"counted\"]]\n    if False:\n        raise", 1),
    ("fail_open_no_counted_k1", "    vals = [v[\"h_hi\"] for v in per.values() if v[\"counted\"]]\n    if not vals:\n        raise",
     "    vals = [v[\"h_hi\"] for v in per.values() if v[\"counted\"]]\n    if False:\n        raise", 1),
    ("fail_open_shortlist_size", "    if len(cands) != HR_SHORTLIST:\n        raise", "    if False:\n        raise", 1),
    ("fail_open_missing_candidate_dies", '        raise ValueError(f"reference {rid}: a candidate F3 checks has no die rows")',
     "        break", 1),
    ("fail_open_negative_l_term", "    if l_term < 0.0:\n        raise", "    if False:\n        raise", 1),
    # --- added by T0269 attempt 2: an independent probe. Each of these SURVIVED attempt 1's tests; the tests in the
    # section "T0269 attempt 2 gaps" of test_headroom_metrics.py were added to kill them --------------------------
    ("k1_min_over_references", "    return float(max(vals))", "    return float(min(vals))", 1),
    ("shortcut_never", "                if lc <= lsub(order[0]):  # the comparator", "                if False:  # the comparator", 1),
    ("shortcut_strict", "                if lc <= lsub(order[0]):  # the comparator", "                if lc < lsub(order[0]):  # the comparator", 1),
    ("snap_key_guard_open", "if on_grid is False and any(c not in ref for c in snap_cols):", "if False:", 1),
    ("dup_die_overwrites", "            if did in dies:\n", "            if False:\n", 1),
    ("comparator_validation_open", "    if comparator not in (\"twin\", \"reconstruction\"):\n        raise", "    if False:\n        raise", 1),
    ("a1_twin_rule_vs_twin_in_recon", "if best is None or lc <= lsub(best):", "if best is None or lsub(twin) <= lsub(best):", 1),
    ("k1_twin_rule_vs_twin_in_recon", "elif lc <= lsub(ind):", "elif lsub(twin) <= lsub(ind):", 1),
    ("k1_w_ind_vs_twin", "w_ind = 2.0 * ratio_band_estimate(five(ind), five(comp)) + s_ref", "w_ind = 2.0 * ratio_band_estimate(five(ind), five(twin)) + s_ref", 1),
    ("pos_allows_zero", "    if x <= 0.0:\n        raise ValueError(f\"{name}: {v!r} is not positive\")", "    if x < 0.0:\n        raise ValueError(f\"{name}: {v!r} is not positive\")", 1),
    ("num_accepts_bool", "if v is None or isinstance(v, bool):", "if v is None:", 1),
    ("on_grid_bool_check_open", "    if not isinstance(on_grid, bool):\n        raise", "    if False:\n        raise", 1),
    ("opt_eR_not_doubled", "headroom_hi(a, lsub(opt) / lc, 2.0 * eo + s_ref)", "headroom_hi(a, lsub(opt) / lc, eo + s_ref)", 1),
    ("near_ties_only_first_two", "            for c in order:\n                if lsub(c)", "            for c in order[:2]:\n                if lsub(c)", 1),
    ("f3_any_has_dies", "if not all(has_dies(c) for c in batch):", "if not any(has_dies(c) for c in batch):", 1),
    ("middle_monotone_le", "if e21 * e32 > 0.0 and abs(e21) < abs(e32):", "if e21 * e32 > 0.0 and abs(e21) <= abs(e32):", 1),
    ("hi_secondary_fail_raise", "                except ValueError:  # no band solves", "                except KeyError:  # no band solves", 1),
    # --- added by T0269 attempt 2: probe mutants attempt 1's tests already killed (kept so they stay killed) ------
    ("a1_twin_rule_vs_ind_best", "if best is None or lc <= lsub(best):", "if best is None or lc <= lsub(order[0]):", 1),
    ("admissible_bool_open", "    if not isinstance(admissible, bool):\n        raise", "    if False:\n        raise", 1),
    ("levelling_swapped", "levelled = l1_first <= (1.0 + w_lev) * l1_all", "levelled = l1_all <= (1.0 + w_lev) * l1_first", 1),
    ("tj_T_from_level0", "t_max, g_max, upper = max(t_max, f2), max(g_max, g), max(upper, f2 + g)", "t_max, g_max, upper = max(t_max, f0), max(g_max, g), max(upper, f2 + g)", 1),
    ("tj_upper_no_gci", "max(upper, f2 + g)", "max(upper, f2)", 1),
    ("tj_lower_no_gci", "lower = max(lower, f2 - g)", "lower = max(lower, f2)", 1),
    ("opt_uses_conservative", "if tj_optimistic_ok(cb, tw_b, limit)), None)", "if tj_conservative_ok(cb, tw_b, limit)), None)", 1),
    ("optimistic_test_wrong_bounds", "return cand[3] - twin[2] <= limit_k", "return cand[3] - twin[3] <= limit_k", 1),
    ("dup_layout_overwrites", "            if lid in t[\"layouts\"]:\n", "            if False:\n", 1),
    ("l_term_param_ignored", "params[\"L_term_H\"] if \"L_term_H\" in params else ref.get(\"L_term_H\")", "ref.get(\"L_term_H\")", 1),
    ("default_comparator_recon", "comparator = params.get(\"comparator\", \"twin\")", "comparator = params.get(\"comparator\", \"reconstruction\")", 1),
    ("snap_check_and", "if l_chk0125 is not None or l_chk05 is not None:", "if l_chk0125 is not None and l_chk05 is not None:", 1),
    ("gate_a2_strict", "<= twin[1] + recon[1]", "< twin[1] + recon[1]", 1),
    ("gate_a1_strict", ") <= 2.0 * ratio_band_estimate(twin5, recon5)", ") < 2.0 * ratio_band_estimate(twin5, recon5)", 1),
    ("near_tie_vs_best_not_ind_r", "ties[str(c[\"layout_id\"])] = headroom_hi(a, lsub(c) / lc, wc)", "ties[str(c[\"layout_id\"])] = headroom_hi(a, lsub(ind) / lc, wc)", 1),
    ("middle_monotone_drop_sign", "if e21 * e32 > 0.0 and abs(e21) < abs(e32):", "if abs(e21) < abs(e32):", 1),
    ("inadmissible_counted_as_raise", "    if not admissible:\n        return out", "    if not admissible:\n        raise ValueError('x')", 1),
    ("kind_filter_raises", "        if kind not in (\"reference\", \"layout\", \"die\"):\n            continue", "        if kind not in (\"reference\", \"layout\", \"die\"):\n            raise ValueError('x')", 1),
    ("roles_other_raise", "    cands = roles.get(\"candidate\", [])\n", "    cands = roles.get(\"candidate\", [])\n    if set(roles) - {'twin', 'reconstruction', 'candidate'}:\n        raise ValueError('x')\n", 1),
]


def _run_pytest() -> int:
    for name in [m for m in sys.modules if m == TEST_MODULE]:
        del sys.modules[name]
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        code = pytest.main(["-q", "-x", "-p", "no:cacheprovider", "-p", "no:randomly", str(TESTS)])
    return int(code)


def run_against(source: str, label: str) -> int:
    """Run the test file against ``source`` as module ``headroom_metrics``; returns pytest's exit code."""
    mod = types.ModuleType("headroom_metrics")
    mod.__file__ = str(SOURCE)
    sys.modules["headroom_metrics"] = mod
    exec(compile(source, f"<{label}>", "exec"), mod.__dict__)  # noqa: S102
    return _run_pytest()


def main() -> int:
    sys.path.insert(0, str(HERE))
    src = SOURCE.read_text()
    code = run_against(src, "unmutated")
    if code != 0:
        print(f"the unmutated draft does not pass its tests (pytest exit {code}); fix that first")
        return 2
    names = [m[0] for m in MUTANTS]
    if len(set(names)) != len(names):
        print("duplicate mutant names")
        return 2
    results: list[tuple[str, str]] = []
    errors = 0
    for name, old, new, count in MUTANTS:
        if src.count(old) != count:
            results.append((name, f"ERROR anchor found {src.count(old)} x, expected {count}"))
            errors += 1
            continue
        mutated = src.replace(old, new)
        try:
            code = run_against(mutated, name)
        except Exception as exc:  # a mutant that cannot even be loaded is not a test failure
            results.append((name, f"ERROR {type(exc).__name__}: {exc}"))
            errors += 1
            continue
        if code == 1:
            results.append((name, "yes"))
        elif code == 0:
            results.append((name, "NO (survived)"))
        else:
            results.append((name, f"ERROR pytest exit {code}"))
            errors += 1
    width = max(len(n) for n, _ in results)
    print(f"{'mutant'.ljust(width)}  killed")
    for n, r in results:
        print(f"{n.ljust(width)}  {r}")
    survived = [n for n, r in results if r.startswith("NO")]
    killed = sum(r == "yes" for _, r in results)
    print(f"\n{killed} of {len(results)} mutants killed; {len(survived)} survived; {errors} errors")
    return 0 if not survived and not errors else (1 if survived else 2)


if __name__ == "__main__":
    raise SystemExit(main())
