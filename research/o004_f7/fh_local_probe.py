"""T0457 item 13 (RESEARCH ONLY, NOT EVIDENCE; O004 F2: 2D_Case_4 development geometry only).

Full local multipole solves of the small Case 4 FastHenry decks of the F7(a) job list (k0, projected at or below 3 GB),
one at a time, within the Mac policy (one process, cap 4.6 GB < the 5 GB budget), recording wall time and peak memory
against the job list's projection.  Runs in-process (the runner is imported once at start, so later edits of the runner
do not affect a running probe); checkpointed per deck to research/o004_f7/fh_local_probe.json (resumes).

    uv run python research/o004_f7/fh_local_probe.py [job_id[@tag] ...]

A ``@tag`` (attempt 2: ``@solo``) re-solves the same deck under its own key, to separate CPU contention from the deck
(attempt 1's two k0 solves ran beside the band simulation).  The 1-, 5- and 15-minute load averages before and after each
solve are recorded.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import time
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "research" / "o004_f7" / "fh_local_probe.json"
DEFAULT_IDS = ("case4_base__fh_k0_nh5", "dev03_trace_width__fh_k0_nh5")
LOCAL_CAP_MB = 4600.0  # Mac policy: one process, below the 5 GB total budget
# Attempt 2 level factorial (decks NOT in the job list): which feature of the g decks (cell 0.5 mm, nh 1, wire_sub 2; Case 4
# g1 timed out at 13.4x its projection, gen2_0 g1 needed 15x to reach GMRES) makes them slow, and so whether the k1 / k2
# decks (cell 0.5 / 0.25 mm, wire_sub 2 / 4, nh 3-9) inherit the miss.  Base B = k0's lateral (cell 1 mm, plane 2 mm),
# nh 1, wire 2/1; each variant changes one feature toward g1.  Timeout 8 x the raw projection (min 900 s): a timeout is
# read as 'slow, factor >= 8', a finish below ~2x as 'the feature is not the cause'.
_B = dict(cell_mm=1.0, plane_cell_mm=2.0, nh_trace=1, nh_plane=1, rh=2.0, nw_trace=1, wire_n=2, wire_sub=1)
CUSTOM = {"case4_base__fhx_B_k0lat_nh1_w2s1": ("case4_base", _B),
          "case4_base__fhx_B_plus_wiresub2": ("case4_base", dict(_B, wire_sub=2)),
          "case4_base__fhx_B_plus_cell0.5": ("case4_base", dict(_B, cell_mm=0.5)),
          # k1's own lateral level (cell 0.5, plane 1 mm: trace / plane 1:2 as on every k level; g decks are 1:4) at nh 1
          "case4_base__fhx_k1lat_nh1": ("case4_base", dict(_B, cell_mm=0.5, plane_cell_mm=1.0, wire_n=4, wire_sub=2))}
CUSTOM_TIMEOUT_FACTOR, CUSTOM_MIN_TIMEOUT_S = 8.0, 900.0


def main() -> int:
    import yaml
    sp = importlib.util.spec_from_file_location("e004_run_probe", ROOT / "experiments" / "runners" / "e004_run.py")
    R = importlib.util.module_from_spec(sp)
    sys.modules["e004_run_probe"] = R
    sp.loader.exec_module(R)
    from moduleforge.solvers import fasthenry_run as FR
    from moduleforge.solvers.fasthenry import FHLevel, export
    cfg = yaml.safe_load((ROOT / "experiments" / "drafts" / "E004.yaml").read_text())["config"]
    ids = tuple(sys.argv[1:]) or DEFAULT_IDS
    jobs, lays = R.f7a_jobs(cfg)
    by_id = {j["id"]: j for j in jobs}
    state = json.loads(OUT.read_text()) if OUT.exists() else {"decks": {}}
    state["label"] = ("RESEARCH ONLY, NOT EVIDENCE (T0457 item 13): full local multipole solves of the small Case 4 decks "
                      "(development geometry, O004 F2), one at a time, against the job list's projection")
    state["host"] = os.uname().nodename
    state["local_cap_mb"] = LOCAL_CAP_MB
    for key in ids:
        jid, _, tag = key.partition("@")
        if jid in CUSTOM and jid not in by_id:
            lay_name, kw = CUSTOM[jid]
            d0, f0 = export(lays[lay_name], FHLevel(**kw), die_model=cfg["solve"]["fasthenry"]["die_model"],
                            terminal_model=cfg["solve"]["fasthenry"]["terminal_model"])
            import hashlib
            f = cfg["solve"]["fasthenry"]
            by_id[jid] = dict(id=jid, layout=lay_name, level="custom", fh_level=kw, mode=f["mode"], order=f["order"],
                              tol=f["tol"], die_model=f["die_model"], terminal_model=f["terminal_model"],
                              deck_sha256=hashlib.sha256(d0.encode()).hexdigest(), custom=True,
                              **R.fh_sizing(cfg, f0["n_filaments"]))
        j = by_id[jid]
        if key in state["decks"] and state["decks"][key].get("deck_sha256") == j["deck_sha256"]:
            continue
        if j["mem_proj_gb"] > 3.05:
            state["decks"][key] = {"skipped": f"projected {j['mem_proj_gb']:.2f} GB > 3 GB"}
            continue
        # the job list's time_proj_s is calibrated by earlier probes (time_calibration); the ratio uses the raw rule
        t_raw = j["time_proj_s"] / j.get("time_calibration", 1.0)
        load0 = os.getloadavg()
        deck, facts = export(lays[j["layout"]], FHLevel(**j["fh_level"]), die_model=j["die_model"],
                             terminal_model=j["terminal_model"])
        print(f"solve {key}: {facts['n_filaments']} filaments, projected {j['mem_proj_gb']:.2f} GB, "
              f"{t_raw:.0f} s, load {load0}", flush=True)
        t0 = time.time()
        res = FR.solve_deck(deck, mode=j["mode"], order=j["order"], tol=j["tol"], max_retries=3,
                            timeout_s=(max(CUSTOM_MIN_TIMEOUT_S, CUSTOM_TIMEOUT_FACTOR * t_raw) if j.get("custom")
                                       else max(3600.0, 10 * t_raw)), mem_cap_mb=LOCAL_CAP_MB, facts=facts)
        ok = [a for a in res.attempts if a.status == "ok"]
        rec = dict(id=jid, tag=tag or None, custom=bool(j.get("custom")), load_avg_before=load0, load_avg_after=os.getloadavg(), layout=j["layout"], level=j["level"], fh_level=j["fh_level"], deck_sha256=j["deck_sha256"],
                   n_filaments_exporter=facts["n_filaments"], n_filaments_refined=res.n_filaments_refined,
                   status=res.status, reason=res.reason, binary_sha256=res.binary_sha256,
                   L_H={f"{f / 1e6:g}MHz": v for f, v in (res.L_H or {}).items()} if res.ok else None,
                   wall_s_total=time.time() - t0, wall_s_ok=ok[-1].wall_s if ok else None,
                   peak_mem_mb=max((a.peak_mem_mb for a in res.attempts), default=None),
                   attempts=[{k: v for k, v in asdict(a).items() if k != "log_tail"} for a in res.attempts],
                   time_proj_s=t_raw, mem_proj_gb=j["mem_proj_gb"], mem_raw_gb=j["mem_raw_gb"])
        if ok:
            rec["time_ratio_measured_over_projected"] = ok[-1].wall_s / t_raw
        if rec["peak_mem_mb"]:
            rec["mem_ratio_measured_over_raw"] = rec["peak_mem_mb"] / 1024 / j["mem_raw_gb"]
            rec["mem_ratio_measured_over_projected"] = rec["peak_mem_mb"] / 1024 / j["mem_proj_gb"]
        state["decks"][key] = rec
        OUT.write_text(json.dumps(state, indent=1, default=str))
        print(json.dumps({k: v for k, v in rec.items() if k != "attempts"}, default=str), flush=True)
    OUT.write_text(json.dumps(state, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
