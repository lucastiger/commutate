"""T0181 pair runs split into one process per (layout, level) so that memory is released and partial results survive.

Same pairs, power calibration, frozen grid rule and estimators as ``gci_study.py`` (attempt 1); results are appended to
``research/o006_gci/pairs_jobs.jsonl`` and assembled into ``research/o006_gci/part_pairs.json``.

* ``cells``                -- grid cell counts of the six layouts at levels 0-2 (no solve) + calibrated powers.
* ``job FAM TAG LEVEL``    -- solve one layout at one level, append one JSON line.
* ``assemble``             -- build part_pairs.json (estimators per die, per layout, and for the A-B differences).

Research, not evidence.  Development seed 1181 only.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gci_study as gs  # noqa: E402
from moduleforge.solvers import thermal_layout as tl  # noqa: E402

JOBS = gs.OUT / "pairs_jobs.jsonl"
POWERS = gs.OUT / "pairs_powers.json"
# Memory cap for one solve on the shared 16 GB host: measured ~1.0-1.2 kB per active cell at level 2 (B layouts, 4.4 M
# active / 7.1 M grid cells, 4.4-5.4 GB); the 16.8 M-grid-cell A layouts swapped (attempt 1: 4789 s; attempt 2 likewise).
GRID_CAP = int(os.environ.get("O006_GRID_CAP", 8_000_000))  # raised to 17 M after side_by_side A level 2 (16.8 M grid,
# 9.96 M active cells) measured 6.5 GB peak / 888 s on this host (attempt 2)
FIT_CAP = 8_000_000  # fixed cap of the declared replacement selection (independent of GRID_CAP overrides)


def _level0_grid(lay) -> int:
    g = tl.build_layout_grid(lay, 0)
    return int(g.shape[0] * g.shape[1] * g.shape[2])


def find_fit_pairs():
    """Replacement selection, declared before any solve of the selected layouts: per family, the first pair in
    generation order (same generator call as ``gs.find_pairs``) of equal die size whose level-2 grids (64 x level 0)
    are both <= FIT_CAP (8 M).  Cost-driven, outcome-blind; biased towards layouts with fewer grid lines (disclosed)."""
    from moduleforge.generate.halfbridge import generate_layouts

    assert gs.DEV_SEED != gs.FORBIDDEN_SEED
    pairs = []
    for fam in gs.FAMILIES:
        lays = generate_layouts(16, gs.DEV_SEED, family=fam, dies_per_switch=2)
        seen = {}
        for i, lay in enumerate(lays):
            if 64 * _level0_grid(lay) > FIT_CAP:
                continue
            s = round(lay.dies[0].w / gs.MM, 3)
            if s in seen:
                pairs.append((fam, s, (seen[s], lays[seen[s]]), (i, lay)))
                break
            seen[s] = i
    return pairs


def _pairs(sel: str = "first"):
    src = gs.find_pairs() if sel == "first" else find_fit_pairs()
    return {fam: (s, a, b) for fam, s, a, b in src}


def cmd_cells() -> None:
    pw = json.loads(POWERS.read_text()) if POWERS.exists() else {}
    for fam, (s, (ia, la), (ib, lb)) in _pairs().items():
        if fam not in pw:
            pw[fam] = gs.calibrate(la)
        for tag, idx, lay in (("A", ia, la), ("B", ib, lb)):
            n = []
            for lv in range(3):
                g = tl.build_layout_grid(lay, lv)
                n.append(int(g.shape[0] * g.shape[1] * g.shape[2]))
                del g
            print(fam, tag, idx, s, lay.fingerprint(), pw[fam], n, flush=True)
    POWERS.write_text(json.dumps(pw, indent=1) + "\n")


def cmd_job(fam: str, tag: str, level: int, sel: str = "first") -> None:
    s, (ia, la), (ib, lb) = _pairs(sel)[fam]
    idx, lay = (ia, la) if tag == "A" else (ib, lb)
    n_grid = 8**level * _level0_grid(lay)
    if n_grid > GRID_CAP:
        print(fam, tag, level, "skipped: grid", n_grid, "> GRID_CAP", GRID_CAP, flush=True)
        return
    P = json.loads(POWERS.read_text())[fam]  # one power per family (calibrated on gen #0), shared by both selections
    t0 = time.perf_counter()
    r = tl.solve_layout_level(lay, level=level, power_W=P, h=gs.H, T_c=gs.T_C)
    rec = {"family": fam, "selection": sel, "tag": tag, "index_in_generation": idx, "die_size_mm": s, "fingerprint": lay.fingerprint(),
           "power_per_die_W": P, "level": level, "n_cells": int(r["meta"]["n_cells"]),
           "wall_s": time.perf_counter() - t0, "peak_rss_gb": gs.rss_gb(),
           "energy_balance": r["meta"]["energy_balance"], "picard_iters": r["meta"]["picard_iters"],
           "linear_residual": r["meta"]["linear_residual"], "switch_of_die": [d.switch for d in lay.dies],
           "values": r["values"]}
    with JOBS.open("a") as fh:
        fh.write(json.dumps(gs._clean(rec)) + "\n")
    print(fam, tag, level, rec["n_cells"], round(rec["wall_s"], 1), round(rec["peak_rss_gb"], 2), flush=True)


def _layout_entry(lv: list[dict]) -> dict:
    nd = len(lv[0]["switch_of_die"])
    per_die = []
    for d in range(nd):
        f = [x["values"][f"die{d}.tj_max"] for x in lv]
        per_die.append({"die": d, "switch": lv[0]["switch_of_die"][d], "tj_max_K": f,
                        **(gs.estimators(*f) if len(f) == 3 else {})})
    ft = [x["values"]["tj_max"] for x in lv]
    return {"index_in_generation": lv[0]["index_in_generation"], "fingerprint": lv[0]["fingerprint"],
            "levels": [{k: v for k, v in x.items() if k not in ("values", "family", "tag", "selection")} for x in lv],
            "per_die": per_die, "tj_max": {"tj_max_K": ft, **(gs.estimators(*ft) if len(ft) == 3 else {})}}


def cmd_assemble() -> None:
    recs = {}
    for line in JOBS.read_text().splitlines():
        r = json.loads(line)
        recs[(r["family"], r["index_in_generation"], r["level"])] = r  # last write wins
    out = []
    for sel, src in (("first", gs.find_pairs()), ("fit", find_fit_pairs())):
        for fam, s, (ia, _), (ib, _) in src:
            lv = {i: [recs[(fam, i, k)] for k in range(3) if (fam, i, k) in recs] for i in (ia, ib)}
            rec = {"family": fam, "selection": sel, "dies_per_switch": 2, "die_size_mm": s, "pair_gen_indices": [ia, ib],
                   "power_per_die_W": json.loads(POWERS.read_text())[fam],
                   "layouts": [dict(tag=t, **_layout_entry(lv[i])) for t, i in (("A", ia), ("B", ib)) if lv[i]],
                   "complete_levels_0_2": all(len(lv[i]) == 3 for i in (ia, ib))}
            if rec["complete_levels_0_2"]:
                va, vb = [x["values"] for x in lv[ia]], [x["values"] for x in lv[ib]]
                diffs = {"diff_tj_max_A_minus_B": [a["tj_max"] - b["tj_max"] for a, b in zip(va, vb, strict=True)]}
                for d in range(min(len(lv[ia][0]["switch_of_die"]), len(lv[ib][0]["switch_of_die"]))):
                    diffs[f"diff_die{d}_tj_max_A_minus_B"] = [a[f"die{d}.tj_max"] - b[f"die{d}.tj_max"]
                                                             for a, b in zip(va, vb, strict=True)]
                rec["differences"] = {k: {"values_K": v, **gs.estimators(*v)} for k, v in diffs.items()}
            out.append(rec)
    doc = {"dev_seed": gs.DEV_SEED, "status": "research, not evidence",
           "selection_first": "first equal-die-size pair in generation order, generate_layouts(16, 1181, family=f, "
           "dies_per_switch=2) (attempt-1 rule)",
           "selection_fit": find_fit_pairs.__doc__, "fit_cap_cells": FIT_CAP, "pairs": out}
    (gs.OUT / "part_pairs.json").write_text(json.dumps(gs._clean(doc), indent=1) + "\n")
    print("wrote part_pairs.json with", len(out), "pairs")


if __name__ == "__main__":
    c = sys.argv[1]
    if c == "cells":
        cmd_cells()
    elif c == "job":
        cmd_job(sys.argv[2], sys.argv[3], int(sys.argv[4]), sys.argv[5] if len(sys.argv) > 5 else "first")
    elif c == "fitcells":
        for fam, (s, (ia, la), (ib, lb)) in _pairs("fit").items():
            print(fam, s, ia, ib, 64 * _level0_grid(la), 64 * _level0_grid(lb), flush=True)
    elif c == "assemble":
        cmd_assemble()
