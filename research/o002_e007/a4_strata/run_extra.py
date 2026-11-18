"""T0456 step 2 (O002, E007 development, never evidence): 6 more development layouts in each of interleaved/2,
side_by_side/2 and u_shaped/6 on a fresh development seed, both loads, level 1 judged, through e007_run.execute.

The registered pipeline is used unchanged; only the stratum list is narrowed (e007_run.all_strata / cells patched in this
process, restored for the freeze checks, which compare the 15-stratum allocation). Die sizes = config.dev.die_size_mm
(T0398's: 4.5 / 4.0 / 5.5 mm). P_ref = T0398's level-0 calibration records (same development layout of seed 20261101,
same die size, same code hashes; copied, then validated by Jobs._valid). Consequence: allocation_fixed is reported as
failed (3 strata, not 15) -- expected for this design and not a defect.

Writes research/o002_e007/dev_rows_a4_strata.json: rows = the 6 new layouts per stratum (nulls leave-one-layout-out within
the 6); meta.combined_9 = per-stratum statistics on T0398's 3 + these 6 layouts (9 layouts, 18 switch rows; nulls
recomputed leave-one-layout-out over the 9).

usage: uv run python research/o002_e007/a4_strata/run_extra.py [--cap-gb 7.5] [--analyse-only]"""
from __future__ import annotations

import argparse
import copy
import json
import math
import shutil
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "experiments" / "runners"))
import e007_run as E  # noqa: E402

SEED = 20261456  # T0456 development seed: not in config.seeds.forbidden before this task (added by it), not 20261395/20261398
STRATA = [("interleaved", 2), ("side_by_side", 2), ("u_shaped", 6)]
CELLS = [("interleaved", "2-3"), ("side_by_side", "2-3"), ("u_shaped", "4-6")]
M_NEW = 6
WD = ROOT / "research" / "o002_e007" / "a4_strata" / "work"
OUT = ROOT / "research" / "o002_e007" / "dev_rows_a4_strata.json"
T0398 = ROOT / "experiments" / "drafts" / "E007.dev_rows.json"


def patch():
    orig_all, orig_fc = E.all_strata, E.freeze_checks

    def fc(cfg):
        E.all_strata = orig_all
        try:
            return orig_fc(cfg)
        finally:
            E.all_strata = lambda: list(STRATA)
    E.freeze_checks = fc
    E.all_strata = lambda: list(STRATA)
    E.cells = lambda: list(CELLS)
    orig_sc = E.sample_checks

    def sc(cfg, sample, mode):  # the cell-coverage test indexes every stratum of a band: narrow the bands meanwhile
        bands = E.BANDS
        E.BANDS = {"2-3": (2,), "4-6": (6,)}
        try:
            return orig_sc(cfg, sample, mode)
        finally:
            E.BANDS = bands
    E.sample_checks = sc


def per_stratum(rows: list, spec: dict, cfg: dict) -> dict:
    """Per stratum: A4 (P_ref; point and V4 bound), A4 at half P_ref (point), A2 (max load; point and bound), A3, the
    isolated-die null's A4, HS/LS bias per load, reference-spread diversity, and the numerator/denominator of A4."""
    lev = float(cfg["bound"]["ci_spec"]["level"])
    Ent = {e["metric"]: e for e in E.recompute_entries(spec)}
    A2, A3, A4 = (cfg["metric_names"][k] for k in ("A2", "A3", "A4"))
    dev = E.l1_dev_check(rows, cfg, Ent[A2], Ent[A4], Ent[cfg["metric_names"]["A1"]])
    out = {}
    for sn in sorted({r["stratum"] for r in rows if r["kind"] == "die"}):
        sub = [r for r in rows if r.get("stratum") == sn]
        a4, a4ci, n4 = E.metric_with_bound(sub, Ent[A4], lev)
        a2, a2ci, n2 = E.metric_with_bound(sub, Ent[A2], lev)
        a3, a3ci, _ = E.metric_with_bound(sub, Ent[A3], lev)
        a4h = E.compute_point(sub, {**Ent[A4], "where": {**Ent[A4]["where"], "load": "half_P_ref"}})
        iso = E.compute_point(sub, {**Ent[A4], "pred": "null_iso"})
        sw = [r for r in sub if r["kind"] == "switch" and r["load"] == "P_ref"]
        num = float(np.quantile([abs(r["spread_l1_K"] - r["spread_ref_K"]) for r in sw], 0.95))
        den = float(np.quantile([abs(r["spread_null_K"] - r["spread_ref_K"]) for r in sw], 0.95))
        sp = np.array([r["spread_ref_K"] for r in sw])
        d = dev[sn]
        out[sn] = {"n_layouts": len({r["layout"] for r in sub}), "n_switch_rows_P_ref": len(sw),
                   "A4_P_ref": a4, "A4_bound_V4": a4ci, "A4_bound_finite": bool(a4ci and math.isfinite(a4ci[1])),
                   "A4_above_0.3": bool(a4 > 0.3), "A4_half_P_ref": a4h, "A4_num_p95_K": num, "A4_den_p95_K": den,
                   "A2_max_load": a2, "A2_bound_V4": a2ci, "A3_max_load_K": a3, "A3_bound_V4": a3ci,
                   "isolated_die_A4_P_ref": iso,
                   "bias_HS_K": {ld: d[f"bias_HS_K_{ld}"] for ld in cfg["loads"]},
                   "bias_LS_K": {ld: d[f"bias_LS_K_{ld}"] for ld in cfg["loads"]},
                   "implied_c_P_ref": d["implied_c_P_ref"], "c_table": d["c_table"],
                   "spread_ref_P_ref_mean_K": float(sp.mean()), "spread_ref_P_ref_sd_K": float(sp.std(ddof=1)),
                   "spread_ref_P_ref_cv": float(sp.std(ddof=1) / sp.mean())}
    return out


def combine(new_rows: list) -> list:
    """T0398's die rows of the 3 strata + the new die rows; nulls and switch/layout rows rebuilt over all 9 layouts."""
    old = json.load(open(T0398))["rows"]
    keep = {E.stratum_name(f, k) for f, k in STRATA}
    die = [copy.deepcopy(r) for r in old if r["kind"] == "die" and r["stratum"] in keep]
    die += [copy.deepcopy(r) for r in new_rows if r["kind"] == "die"]
    assert len({(r["layout"], r["load"], r["switch"], r["die_index"]) for r in die}) == len(die), "duplicate die rows"
    wall = {(r["layout"], r["load"]): r["l1_eval_s"] for r in old + new_rows if r["kind"] == "layout"}
    E.add_lolo_nulls(die)
    lay, sw = E.assemble(die, wall)
    return die + lay + sw


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cap-gb", type=float, default=7.5)
    ap.add_argument("--analyse-only", action="store_true")
    a = ap.parse_args()
    spec = E.load_spec()
    cfg = copy.deepcopy(spec["config"])
    if SEED in {int(v) for v in cfg["seeds"]["forbidden"]} - {SEED}:
        raise SystemExit("seed reused")
    assert SEED not in (20261395, 20261398)
    cfg["dev"]["dev_seed"] = SEED
    patch()
    (WD / "solves").mkdir(parents=True, exist_ok=True)
    for f, k in STRATA:  # T0398's P_ref calibrations (same job: layout, die size, code hashes)
        src = ROOT / cfg["dev"]["workdir"] / "solves" / f"cal__{f}_{k}_pref.json"
        dst = WD / "solves" / src.name
        if not dst.exists():
            shutil.copy2(src, dst)
    E.FAKE = False
    res = E.execute(cfg, spec, SEED, "dev", WD, m=M_NEW, max_procs=1, cap_gb=a.cap_gb)
    rows = E.report_rows(res)
    for r in rows:  # T0398's layouts are also named <family>_<dies>_j00..: rename so the two sets never collide
        r["dev_seed"], r["source"], r["layout"] = SEED, "T0456", r["layout"].replace("_j", "_t456j")
    old_pref = json.load(open(T0398))["meta"]["pref_W_per_die"]
    pref_same = all(math.isclose(res["pref"][sn], old_pref[sn], rel_tol=1e-12) for sn in res["pref"])
    comb = combine(rows)
    meta = {"experiment": E.EID, "task": "T0456", "smoke": False, "fake": E.FAKE, "seed_role": "development",
            "dev_seed": SEED, "strata": [E.stratum_name(f, k) for f, k in STRATA], "layouts_per_stratum_new": M_NEW,
            "judged_level": cfg["judged_level"], "pref_W_per_die": res["pref"], "pref_equal_to_T0398": pref_same,
            "die_size_mm": {k: v["die_size_mm"] for k, v in res["sample"]["strata"].items()},
            "sub_seeds": res["sample"]["sub_seeds"],
            "fingerprints": [d["fingerprint"] for st in res["sample"]["strata"].values() for d in st["judged"]],
            "checks": res["checks"],
            "checks_note": "allocation_fixed fails by design (3 strata x 6 layouts, not 15 x m); every other check must pass",
            "new_6": per_stratum(res["rows"], spec, cfg), "combined_9": per_stratum(comb, spec, cfg),
            "f2_nulls_new_6": {k: {"A4_point": v["A4_point"], "A1_P_ref_K": v["A1_P_ref_K"]}
                               for k, v in res["reports"]["nulls"].items()},
            "reference_cpu_wall": {k: {"cpu_s": v.get("cpu_s", sum(h["cpu_s"] for h in v.get("history", []))),
                                       "wall_s": v.get("wall_s", sum(h["wall_s"] for h in v.get("history", []))),
                                       "dofs": v.get("dofs", v.get("level0", {}).get("dofs")),
                                       "peak_rss_GB": v["peak_rss_GB"]} for k, v in res["recs"].items()},
            "new_solves": res["new_solves"], "l1_phase_host": res["l1"].get("host")}
    E.write_json(OUT, {"schema": "mfos.rows/1", "rows": rows, "meta": meta})
    E.write_json(WD / "combined_9_rows.json", {"rows": comb})
    bad = [c["name"] for c in res["checks"] if not c["passed"]]
    E.log(f"wrote {OUT}: {len(rows)} rows; failing checks {bad}")
    for part in ("new_6", "combined_9"):
        for sn, v in meta[part].items():
            E.log(f"{part} {sn}: A4 {v['A4_P_ref']:.3f} bound {v['A4_bound_V4']} (half {v['A4_half_P_ref']:.3f}); A2 "
                  f"{v['A2_max_load']:.4f} bound {v['A2_bound_V4']}; iso A4 {v['isolated_die_A4_P_ref']:.2f}; bias HS "
                  f"{v['bias_HS_K']} LS {v['bias_LS_K']}; spread cv {v['spread_ref_P_ref_cv']:.3f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
