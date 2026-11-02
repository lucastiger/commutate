"""Print markdown tables of research/o006_gci/part_pairs.json (T0181; research, not evidence).

Columns: values at levels 0/1/2 (K), p_obs (levels 0-1-2; 'osc' if not monotone), Richardson error estimate RE,
frozen O006 GCI, candidate GCI (Fs 3, p = clip(p_obs, 0.5, 2) outside [1.5, 2.5]) and, post hoc and labelled as such,
a 'theory-order' GCI 3|d21|/(2^p_t - 1) with p_t = min(p_obs, 2*lam_min) = 1.04 (lam_min = 0.519, Cu on Al2O3 corner).
"""
from __future__ import annotations

import json
from pathlib import Path

OUT = Path(__file__).resolve().parents[3] / "research" / "o006_gci"
P_T = 2 * 0.5187


def theory_gci(e: dict) -> float:
    f3, f2, f1 = e["values"]
    d21 = abs(f1 - f2)
    p = P_T if e["p_obs"] is None else min(e["p_obs"], P_T)
    return 3.0 * d21 / (2.0**p - 1.0)


def row(name: str, e: dict) -> str:
    v = " / ".join(f"{x:.3f}" for x in e["values"])
    p = "osc" if e["p_obs"] is None else f"{e['p_obs']:.2f}"
    re = "n/a" if e["richardson_err"] is None else f"{e['richardson_err']:.3f}"
    return (f"| {name} | {v} | {e['abs_d21']:.3f} | {p} | {re} | {e['gci_frozen']:.3f} | {e['gci_candidate']:.3f} | "
            f"{theory_gci(e):.3f} |")


def main() -> None:
    d = json.loads((OUT / "part_pairs.json").read_text())
    hdr = ("| value | levels 0 / 1 / 2 (K) | abs d21 | p_obs | RE | GCI frozen | GCI candidate | GCI p=1.04 (post hoc) |\n"
           "|---|---|---|---|---|---|---|---|")
    for pr in d["pairs"]:
        print(f"\n**{pr['family']}** ({pr['selection']} pair, gen #{pr['pair_gen_indices']}), die {pr['die_size_mm']} mm, {pr['power_per_die_W']} W/die\n")
        print(hdr)
        for lay in pr["layouts"]:
            cells = "/".join(f"{x['n_cells'] / 1e6:.2f}" for x in lay["levels"])
            if "p_obs" in lay["tj_max"]:
                print(row(f"{lay['tag']} (gen #{lay['index_in_generation']}, {cells} M cells) layout tj_max", lay["tj_max"]))
            for pd in lay["per_die"]:
                if "p_obs" in pd:
                    print(row(f"{lay['tag']} die{pd['die']} ({pd['switch']}) tj_max", pd))
        for k, e in pr.get("differences", {}).items():
            if "p_obs" in e:
                print(row(k, e))


if __name__ == "__main__":
    main()
