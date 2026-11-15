"""Generator/DRC feasibility of 2D_Case_2R under the D0021 sampler (T0339, packet item 6; from the T0338 builder's draft
git show 21bbf29a:research/o003/e009_dev/feasibility_2r.py, checked against the merged derivative.py).

Loads the committed 2R spec and twin from E008's run ctx.pkl (keys spec, reference, twin; nothing under solves/ is read) and
runs experiments/runners/e010_run.py's draw_feasibility with its constants (FEAS_DRAWS, FEAS_SEEDS), the function
--check-references uses, so both report the same counts: derivative._sample, build, _quick_ok and drc.check only; no L1, EM,
thermal, FV, degrade(), twin() or search.  Unsealed seeds: a rate estimate, not evidence.  For the support statement
(review T0341) it also counts, on the dev geometry housing70x40_gen2_0 (dev run ctx.pkl, read only), how many of 200
generated candidates share the twin's topology.

P(abort) model: draws are i.i.d. Bernoulli(p) (fresh rng numbers per draw, fixed _Ctx); a screen of N candidates has N
success gaps, each longer than the limit with probability q = (1 - p_lo)^(limit + 1), p_lo the 99.9 % Wilson lower bound
(Wilson, JASA 22 (1927) 209); P(abort) <= 1 - (1 - q)^N.  Writes research/o003/e010_dev/feasibility_2r.json.
Run: uv run python research/o003/e010_dev/feasibility_2r.py
"""
import importlib.util
import json
import pickle
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CTX = ROOT / "experiments/results/E008/E008-20261114T095904-2c22/work/2D_Case_2R/ctx.pkl"
GEN2 = Path("/Users/lukeskywalker/mf/drafts/e008-dev-run-2026-11-13/full_work/housing70x40_gen2_0/ctx.pkl")
OUT = ROOT / "research/o003/e010_dev/feasibility_2r.json"


def main() -> int:
    sp = importlib.util.spec_from_file_location("e010_run", ROOT / "experiments/runners/e010_run.py")
    R = importlib.util.module_from_spec(sp)
    sys.modules[sp.name] = R
    sys.argv = sys.argv[:1]
    sp.loader.exec_module(R)
    from moduleforge.drc.rules import check
    from moduleforge.generate import derivative as D
    c = pickle.load(open(CTX, "rb"))
    spec, twin = c["spec"], c["twin"]
    cx = D._Ctx(spec)
    print(f"housing {spec.name}: split orientations {cx.split}; v windows {cx.vwin}")
    assert not check(twin, spec.rules), "twin not DRC-clean"
    assert not check(D.build(spec, D.params_of(twin)), spec.rules), "build(params_of(twin)) not DRC-clean"
    res = {ns: R.draw_feasibility(spec, twin, R.FEAS_DRAWS, s) for ns, s in R.FEAS_SEEDS.items()}
    for ns, f in res.items():
        print(f"[{ns}, seed {f['seed']}] {f['draws']} draws in {f['wall_s']} s; outcomes {f['outcomes']}")
        print(f"  DRC-clean mix (orient, hs_first, hs_die_first, ls_die_first): {f['config_mix']}; orientation "
              f"{f['orientation_mix']}; topology {f['topology_mix']}")
        print(f"  twin configuration {f['twin_config']} drawn {f['twin_config_draws']} times; longest failure run "
              f"{f['longest_failure_run']}; generate(spec, 20) ok {f['generate_20']['ok']}")
        print(f"  p = {f['p']:.3e} (99.9 % Wilson lower bound {f['p_lo999']:.3e}); draws per candidate "
              f"{f['draws_per_candidate']:.0f}; wall per candidate {f['s_per_candidate_mac'] * 1e3:.2f} ms; "
              f"P(20000-candidate screen hits 20000 consecutive failures) <= {f['p_abort_20000']:.3e} (q {f['q_gap']:.3e})")
        assert f["drc_clean"] > 0 and f["twin_config_draws"] > 0 and f["generate_20"]["ok"]
        assert f["p_abort_20000"] < 1e-6, f["p_abort_20000"]
    t2 = sum(f["s_per_candidate_mac"] for f in res.values()) * R.FEAS_N_CAND
    print(f"estimated wall time for 2 x {R.FEAS_N_CAND} candidates (main + control), drawing only, this Mac: {t2 / 60:.1f} min")
    tot = Counter()
    for f in res.values():
        tot.update(f["orientation_mix"])
    out = {"n_draws": R.FEAS_DRAWS, "seeds": R.FEAS_SEEDS, "namespaces": res, "draw_s_2x20000_mac": t2,
           "orientation_mix": dict(tot), "config_mix": dict(sum((Counter(f["config_mix"]) for f in res.values()), Counter())),
           "topology_mix": dict(sum((Counter(f["topology_mix"]) for f in res.values()), Counter())),
           "split": {str(k): bool(v) for k, v in cx.split.items()}}
    cr = ROOT / "research/o003/e010_dev/check_references.json"
    if cr.exists():  # the same numbers as --check-references (same function, constants and spec)
        f2 = json.loads(cr.read_text())["references"]["2D_Case_2R"]["feasibility"]["namespaces"]
        same = all(f2[ns][k] == res[ns][k] for ns in res for k in ("outcomes", "config_mix", "topology_mix", "drc_clean"))
        print(f"counts equal to --check-references (research/o003/e010_dev/check_references.json): {same}")
        assert same
        out["equal_to_check_references"] = same
    g = pickle.load(open(GEN2, "rb"))
    tt = D.topology_of(g["twin"])
    cands = D.generate(g["spec"], 200, 7)
    n_same = sum(D.topology_of(x) == tt for x in cands)
    out["gen2_0"] = {"n": len(cands), "same_topology_as_twin": n_same, "seed": 7, "twin_topology": tt}
    print(f"gen2_0 (dev): {n_same} of {len(cands)} DRC-clean candidates share the twin's topology {tt}")
    OUT.write_text(json.dumps(out, indent=1) + "\n")
    print(f"wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
