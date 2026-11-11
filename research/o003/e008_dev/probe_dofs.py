"""T0262 thermal-size probe (research, not evidence; L0 geometry only, no solve).

Grid sizes of the frozen scikit-fem rule (research/o007_dev3/frozen_config.json, levels 0-2, thermal_fem.estimate_dofs)
and of the finite-volume L2 at levels 1-3 (thermal_layout.build_layout_grid) on development geometry only (F3):
2D_Case_4 (reconstruction and frozen twin) and the 70 x 40 mm generator housing 2 (dev layout gen2_0), plus random
DRC-valid generator candidates in each outline (dev seed 20261110, purpose 4). The thermal cost of E008 is set by the
candidates' DOF counts, not by the outline area: E009 measured 3.95-9.48 M DOFs at level 2 on two generator layouts of
the same 70 x 40 mm housing.

Usage: uv run python research/o003/e008_dev/probe_dofs.py [n_candidates_per_outline] > research/o003/e008_dev/probe_dofs.log
Writes research/o003/e008_dev/probe_dofs.json. Single process, peak a few GB (FV level 3 of Case 4 is a 235 M-cell
material array, so it is skipped for candidates and computed only for the reconstruction).
"""
import json
import resource
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tools" / "mfos"), str(ROOT / "experiments" / "runners")]
import e008_run as R  # noqa: E402


def rss_gb() -> float:
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * (1.0 if sys.platform == "darwin" else 1024.0) / 1e9


def main() -> None:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 8
    cfg = R.load_spec()["config"]
    FEM = R.FEM()
    rule = R.rule_from(cfg["fem_rule"])
    from moduleforge.generate import derivative as D
    from moduleforge.generate import twin as W
    from moduleforge.solvers import thermal_layout as TL
    out: dict = {"rule": cfg["fem_rule"]["candidate_id"], "n_candidates": n, "outlines": {}}
    for name in ("case4", "gen2_0"):
        rc = R.dev_reference(name, cfg)
        lays = {"reconstruction": rc.reference}
        try:
            lays["twin"] = W.twin(rc.reference, rc.spec, with_l1=False)[0]
        except Exception as e:  # recorded; the probe is not a gate
            out.setdefault("errors", []).append(f"{name} twin: {type(e).__name__}: {e}"[:300])
        seed = R.derive_seed(int(cfg["dev"]["dev_seed"]), 4, 0 if name == "case4" else 1)
        for k, lay in enumerate(D.generate(rc.spec, n, seed)):
            lays[f"cand{k}"] = lay
        rec = {"area_m2": rc.area_m2, "layouts": {}}
        for lab, lay in lays.items():
            t0 = time.perf_counter()
            d = {f"fem_dofs_L{lv}": int(FEM.estimate_dofs(lay, rule, lv)) for lv in (0, 1, 2)}
            if lab == "reconstruction":
                for lv in (1, 2, 3):
                    d[f"fv_cells_L{lv}"] = int(np.prod(TL.build_layout_grid(lay, lv).shape))
            d["s"] = time.perf_counter() - t0
            d["n_traces"] = len(lay.traces)
            rec["layouts"][lab] = d
            print(name, lab, d, f"rss {rss_gb():.2f} GB", flush=True)
        c2 = [v["fem_dofs_L2"] for k, v in rec["layouts"].items() if k.startswith("cand")]
        rec["candidates_L2"] = {"min": min(c2), "median": float(np.median(c2)), "max": max(c2),
                                "ratio_L2_L1": float(np.median([v["fem_dofs_L2"] / v["fem_dofs_L1"]
                                                                 for v in rec["layouts"].values()]))}
        out["outlines"][rc.rid] = rec
    out["peak_rss_GB"] = rss_gb()
    (Path(__file__).parent / "probe_dofs.json").write_text(json.dumps(out, indent=1))
    print(json.dumps({k: v.get("candidates_L2") for k, v in out["outlines"].items()}), flush=True)


if __name__ == "__main__":
    main()
