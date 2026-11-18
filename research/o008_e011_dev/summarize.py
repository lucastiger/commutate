"""Summarise E011's development L1 run (T0382 attempt 4) from experiments/drafts/E011.dev_jobs.json into markdown tables.

Reads only the manifest the runner wrote (its ``layouts`` records and ``vm_sizing``); computes nothing new except
medians and counts.  Usage: uv run python research/o008_e011_dev/summarize.py [manifest] > out.md
"""
from __future__ import annotations

import json
import pickle
import sys
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from moduleforge.generate import derivative as D  # noqa: E402


def f(x, nd=4):
    if x is None:
        return "-"
    if isinstance(x, float):
        return f"{x:.{nd}f}"
    return str(x)


def main(path: str) -> None:
    m = json.loads(Path(path).read_text())
    print(f"manifest status: {m['status']}; generated {m['generated']}; git {m['git_commit'][:10]}; dev_seed {m['dev_seed']}")
    print(f"code_stamp tree {m['code_stamp']['code_tree_sha256'][:16]}, config {m['code_stamp']['config_sha256'][:16]}\n")
    for r in m["layouts"].values():
        name = r["layout"]
        print(f"## {name}\n")
        f2 = r["f2"]
        print(f"- in_domain(W, reach) {f2['in_domain_reach'][0]}; counted {r['counted']}")
        p = r["proxy"]
        print(f"- frozen proxy (reach=True, min_gain 1e-12 H): steps {p['steps']}, kind {p['kind']}, "
              f"L1(W*)/L1(W) {f(p['l1_ratio'])}, W* in domain {r['Wstar']['in_domain_reach']}, DRC-clean {r['Wstar']['drc_clean']}")
        for k, v in r.get("proxy_sensitivity", {}).items():
            print(f"  - sensitivity {k}: steps {v['steps']}, kind {v['kind']}, L1 ratio {f(v['l1_ratio'])}, "
                  f"same layout as frozen {v['same_as_frozen']}")
        print(f"- Tj (K, level 0): " + ", ".join(f"{k} {v:.2f}" for k, v in r["tj_K"].items()) + f"; P_ref {f(r['P_ref_W'], 1)} W")
        dr = r["degradation_report"]
        l1d = [a["l1_ratio"] for d in r["draws"] for a in d["attempt_log"]]
        print(f"- degradation: {dr['n_attempts']} attempts, L1 stop ratio min/median/max {f(dr['l1_stop_ratio']['min'])}/"
              f"{f(dr['l1_stop_ratio']['median'])}/{f(dr['l1_stop_ratio']['max'])}, rate reaching the L1 target "
              f"{f(dr['rate_reached_l1_target'], 3)}, attempts missing it (would still cost an L2 call) "
              f"{dr['attempts_missing_l1_target_with_l2_call']}, out-of-domain defects {len(r['degradation_defects_out_of_domain'])}")
        print(f"  - per-draw L1(D_j)/L1(W*): {', '.join(f(x, 3) for x in l1d)}\n")
        st = Path(m["workdir"]) / "stages" / name  # the run's own code-stamped stage checkpoints (rows are not in the manifest)
        mv = list(r["movable_indices"])
        ws = np.asarray(r["Wstar"]["params"], float)
        vec = lambda lay: D.params_of(lay).to_vector()  # noqa: E731

        def dist(v, w):
            d = np.abs(np.asarray(v, float)[mv] - np.asarray(w, float)[mv])
            return int(np.sum(d > 1e-9)), float(np.sum(d))

        acc = [d["draw"] for d in r["draws"] if d["accepted"]]
        si = r["search_improvement"]
        print("### Search (budget %d L1 evaluations)\n" % si["budget_l1_evals"])
        print("| draw | L1 gain rel | share last 10 % [lo] | exact | share last 25 % [lo] | exact | last improving eval | "
              "steps | l1_evals | stop | seed in domain | changed from D | changed from W* | Manhattan from W* mm |")
        print("|" + "---|" * 14)
        for j in acc:
            c = si["per_draw"][str(j)]
            srch, _ = pickle.loads((st / f"d{j}_search.pkl").read_bytes())
            Dv = vec(pickle.loads((st / f"d{j}_seed.pkl").read_bytes()).layout)
            v = vec(srch.best)  # LocalResult.best: the lowest-L1 layout (L2 selection pending on the burst VM)
            chD, _ = dist(v, Dv)
            chW, mhW = dist(v, ws)
            t = srch.stats
            print(f"| {j} | {f(c['l1_gain_rel'])} | {f(c['gain_share_last10'], 3)} [{f(c['gain_share_last10_lo'], 3)}] | "
                  f"{c['gain_share_last10_exact']} | {f(c['gain_share_last25'], 3)} [{f(c['gain_share_last25_lo'], 3)}] | "
                  f"{c['gain_share_last25_exact']} | {c.get('last_improve_eval')} | {t['steps']} | {t['l1_evals']} | "
                  f"{t['stop_reason']} | {t['seed_in_domain']} | {chD} | {chW} | {f(mhW, 1)} |")
        print(f"\nmedian share last 10 %: {f(si['median_gain_share_last10'], 3)}; last 25 %: "
              f"{f(si['median_gain_share_last25'], 3)}; draws with stats improving_last10: "
              f"{si['draws_still_improving_last10']} of {len(si['per_draw'])} (search end point = its lowest-L1 layout)\n")
        print("### Nulls (b) widen, (d) compact, NULL_STEP_LIMIT 200\n")
        print("| draw | L1(D_j)/L1(W*) | role | steps | terminal | seed_in_domain | n_neighbours step 0 | "
              "changed from D | Manhattan from D mm | changed from W* | Manhattan from W* mm |")
        print("|" + "---|" * 11)
        l1_by_draw = {d["draw"]: d["attempt_log"][-1]["l1_ratio"] for d in r["draws"]}
        kinds = Counter()
        for role in ("widen", "compact"):
            for j in acc:
                nr = pickle.loads((st / f"d{j}_{role}.pkl").read_bytes())
                Dv = vec(pickle.loads((st / f"d{j}_seed.pkl").read_bytes()).layout)
                v = vec(nr.layout)
                chD, mhD = dist(v, Dv)
                chW, mhW = dist(v, ws)
                kinds[(role, nr.terminal)] += 1
                print(f"| {j} | {f(l1_by_draw.get(j), 3)} | {role} | {nr.steps} | {nr.terminal} | "
                      f"{nr.stats.get('seed_in_domain')} | {nr.stats.get('n_neighbours_step0')} | {chD} | {f(mhD, 1)} | "
                      f"{chW} | {f(mhW, 1)} |")
        print("\nterminal kinds: " + ", ".join(f"{k[0]} {k[1]}: {v}" for k, v in sorted(kinds.items())) + "\n")
        print("### Ablations\n")
        print("| draw | (c) random screen l1_evals | (c) n_draws | (e) proxy alone steps | (e) kind | (e) L1 evals |")
        print("|---|---|---|---|---|---|")
        for j in acc:
            rs, _ = pickle.loads((st / f"d{j}_rs.pkl").read_bytes())
            pa = pickle.loads((st / f"d{j}_pa.pkl").read_bytes())
            print(f"| {j} | {rs.stats.get('l1_evals')} | {rs.stats.get('n_draws')} | {pa.steps} | "
                  f"{getattr(pa, 'kind', getattr(pa, 'terminal', None))} | "
                  f"{(getattr(pa, 'stats', None) or {}).get('l1_evals')} |")
        rep = r.get("dcm_alt_search") or []
        if rep:
            print("\n### DC- reading, search of draw 0\n")
            for x in rep:
                rel = (x["lowest_l1_alt"] - x["lowest_l1_frozen"]) / x["lowest_l1_frozen"]
                print(f"- draw {x['draw']}: lowest L1 frozen {x['lowest_l1_frozen']:.6e} H, alt {x['lowest_l1_alt']:.6e} H "
                      f"(relative {rel:+.2e}); shortlist identical {x['shortlist_same']}")
        st = r.get("streams", {})
        ents = st.get("degrade_entropy") or []
        print(f"\n- degradation entropy lists start with DEGRADE_TAG: {all(e and e[0] == 0x4D460D01 for e in ents)} "
              f"({len(ents)} lists)\n")
    vs = m["vm_sizing"]
    print("## VM sizing\n")
    print(json.dumps({k: vs[k] for k in ("machine", "usable_GB", "vcpus", "threads_per_solve", "at_once_by_vcpus",
                                         "largest_solve_GB", "largest_fit_at_once", "measured_mem_ratio")}, indent=1))
    print("\n| layout | level | unknowns | jobs | wall h each | model GB | sched GB prior | at once prior | sched GB learned | at once learned |")
    print("|" + "---|" * 10)
    for k, e in sorted(vs["per_layout_level"].items()):
        lay, lv = k.split("|")
        print(f"| {lay} | {lv} | {e['unknowns']} | {e['jobs']} | {e['est_wall_h_each']} | {e.get('model_GB')} | "
              f"{e.get('sched_GB_prior')} | {e.get('at_once_prior')} | {e.get('sched_GB_learned')} | {e.get('at_once_learned')} |")
    print("\ndev burst: " + json.dumps(vs.get("dev_burst")))
    rr = vs.get("registered_run", {})
    print("\nregistered run (timeout %s h): %s" % (rr.get("timeout_h"), json.dumps(rr.get("by_scenario"))))
    print("\nregistered solves: " + json.dumps(rr.get("solves")))
    print("\ntotals: " + json.dumps(m["totals"]))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else str(ROOT / "experiments" / "drafts" / "E011.dev_jobs.json"))
