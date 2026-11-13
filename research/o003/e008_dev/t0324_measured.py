"""T0324: measured per-solve wall time and peak memory of the full-fidelity dev run (founder's VM, 2026-11-13) against
the --plan cost model the runner attached to each job (Run.estimate: est_s, mem_model_GB, and mem_GB, the scheduling
value with its priors), from the saved job files only (no solve).  Usage:
  uv run python research/o003/e008_dev/t0324_measured.py <workdir copy> [out.json]
Per (reference, type, level): n, measured wall_s and peak_GB (min / median / max), the model's est_s and mem_model_GB
(median), and the ratios measured / model (median and max).  Reads <workdir>/<ref>/solves/*.job.json and the result next
to each; the source directory is never written."""
from __future__ import annotations

import json
import statistics as st
import sys
from pathlib import Path


def main() -> int:
    wd = Path(sys.argv[1])
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else None
    groups: dict[str, list[dict]] = {}
    for jf in sorted(wd.glob("*/solves/*.job.json")):
        j = json.loads(jf.read_text())
        rf = jf.with_name(jf.name.replace(".job.json", ".json"))
        if not rf.exists():
            continue
        r = json.loads(rf.read_text())
        k = f"{j.get('ref')}:{j['type']}:{j.get('level', '')}"
        groups.setdefault(k, []).append({"wall_s": r.get("job_wall_s", r.get("wall_s")), "peak_GB": r.get("peak_GB"),
                                         "est_s": j.get("est_s"), "mem_model_GB": j.get("mem_model_GB"),
                                         "mem_sched_GB": j.get("mem_GB"), "size": r.get("n_unknowns", r.get("nodes"))})
    res = {}
    for k, v in sorted(groups.items()):
        def col(c, v=v):
            return [x[c] for x in v if isinstance(x[c], (int, float))]
        w, p, e, m = col("wall_s"), col("peak_GB"), col("est_s"), col("mem_model_GB")
        rw = [x["wall_s"] / x["est_s"] for x in v if x["wall_s"] and x["est_s"]]
        rp = [x["peak_GB"] / x["mem_model_GB"] for x in v if x["peak_GB"] and x["mem_model_GB"]]
        res[k] = {"n": len(v), "size_median": st.median(col("size")) if col("size") else None,
                  "wall_s": [min(w), st.median(w), max(w)] if w else None,
                  "peak_GB": [min(p), st.median(p), max(p)] if p else None,
                  "model_est_s_median": st.median(e) if e else None, "model_mem_GB_median": st.median(m) if m else None,
                  "wall_over_model": [st.median(rw), max(rw)] if rw else None,
                  "peak_over_model": [st.median(rp), max(rp)] if rp else None}
    tot = sum(x["wall_s"] or 0 for v in groups.values() for x in v)
    doc = {"task": "T0324", "source": "saved job files of the 2026-11-13 dev run (copy)", "n_solves": sum(map(len, groups.values())),
           "sum_solve_wall_h": tot / 3600, "groups": res}
    txt = json.dumps(doc, indent=1)
    if out:
        out.write_text(txt)
    for k, r in res.items():
        print(k, r["n"], "wall", [round(x) for x in r["wall_s"] or []], "model", r["model_est_s_median"],
              "peak", [round(x, 1) for x in r["peak_GB"] or []], "model", r["model_mem_GB_median"] and round(r["model_mem_GB_median"], 2),
              "ratios w", r["wall_over_model"] and [round(x, 2) for x in r["wall_over_model"]],
              "p", r["peak_over_model"] and [round(x, 2) for x in r["peak_over_model"]])
    print("solves", doc["n_solves"], "sum wall h", round(doc["sum_solve_wall_h"], 2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
