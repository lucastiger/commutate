"""Founder-session diagnostic, 2026-11-05 (NOT pre-registered, not evidence; run from the repository root).

T0235's centroid_only variant with the outermost graded interval (2.34375 mm, split in two by min_cells = 2) left as one
cell, which lifts the 0.081 neighbour ratio to 0.161 (review T0240). Levels 0 and 1, Cases 1a and 1b; CG counted by
T0207's cg_only logger, as in T0235. Result: research/o007_sliver/founder_merged_variant.json, note sec. 4."""
import json
import sys

sys.path.insert(0, "research/scripts")
import o007_sliver as S  # noqa: E402

FEM, DS, D2 = S.FEM, S.DS, S.D2
ser = S.DS.load_refs()[0]
W = 2.34375e-3
orig = FEM._base_cells


def merged(length, h0, min_cells=2):
    return 1 if abs(length - W) < 1e-9 else orig(length, h0, min_cells)


DS.install_cg_logger()
rows = []
for case in ("case1a", "case1b"):
    for name, fn in (("centroid_only", orig), ("centroid_merged", merged)):
        FEM._base_cells = fn
        st = S.grid_stats(S.grid(ser, case, "centroid_only", 0))
        for lv in (0, 1):
            DS.CG_LOG.clear()
            b = S.variant_problem(ser, case, "centroid_only")
            r = FEM.solve_box_stack(b["a"], b["b"], b["layers"], b["h"], b["Tc"], b["srcs"], rule=D2.rule_of(S.CID),
                                    level=lv, extra_lines=b["extra"])
            cg = max(c["iters"] for c in DS.CG_LOG)
            rows.append(dict(case=case, variant=name, level=lv, min_ratio_l0=round(st["min_ratio_lateral"], 4),
                             dofs=int(r.dofs), cg_max=cg, meta_cg=max(r.meta["cg_iterations"]),
                             eb=float(r.energy_balance), wall_s=round(float(r.wall_s), 1),
                             tj=[round(float(v), 4) for v in r.tj_max] if hasattr(r, "tj_max") else None))
            print(json.dumps(rows[-1]), flush=True)
FEM._base_cells = orig
json.dump(rows, open("research/o007_sliver/founder_merged_variant.json", "w"), indent=1)
