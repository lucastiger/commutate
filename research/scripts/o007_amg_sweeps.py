"""Founder-session diagnostic, 2026-11-05 (NOT pre-registered, not evidence; run from the repository root).

After the sliver discriminator read `conditioning` (research/o007_sliver/discriminator.json): does the Q1 AMG
preconditioner, not the grid, set T0228's CG counts on Muzychka Cases 1a/1b? Candidate 1 exactly as frozen
(research/o007_dev2/frozen_config.json, max_lines), levels 0 and 1, three preconditioners built by thermal_fem._sa_solver
(same seed): pyamg's default (one symmetric Gauss-Seidel sweep, theta 0, as in production), thermal_fv's settings
(theta 0.05, filtered Jacobi smoothing, forward/backward GS), and two symmetric GS sweeps per level. CG is counted by
T0207's cg_only logger. The temperature change against the default is reported. Output:
research/o007_sliver/founder_amg_diagnostic.json; note research/notes/o007-sliver.md sec. 5."""
import json
import sys

sys.path.insert(0, "research/scripts")
import o007_sliver as S  # noqa: E402

FEM, DS, D2 = S.FEM, S.DS, S.D2
ser = S.DS.load_refs()[0]
orig = FEM._sa_solver
FV = dict(symmetry="symmetric", strength=("symmetric", {"theta": 0.05}), smooth=("jacobi", {"filter_entries": True}),
          improve_candidates=None, presmoother=("gauss_seidel", {"sweep": "forward"}),
          postsmoother=("gauss_seidel", {"sweep": "backward"}))
GS2 = ("gauss_seidel", {"sweep": "symmetric", "iterations": 2})
VARIANTS = {"default": orig,
            "fv_theta0.05": lambda A, **kw: orig(A, **{**kw, **FV}),
            "gs_symmetric_x2": lambda A, **kw: orig(A, **{**kw, "presmoother": GS2, "postsmoother": GS2})}

DS.install_cg_logger()
rows, ref = [], {}
for case in ("case1a", "case1b"):
    for name, fn in VARIANTS.items():
        FEM._sa_solver = fn
        for lv in (0, 1):
            DS.CG_LOG.clear()
            b = S.variant_problem(ser, case, "max_lines")
            r = FEM.solve_box_stack(b["a"], b["b"], b["layers"], b["h"], b["Tc"], b["srcs"], rule=D2.rule_of(S.CID),
                                    level=lv, extra_lines=b["extra"])
            if name == "default":
                ref[(case, lv)] = r.T
            rows.append(dict(case=case, amg=name, level=lv, dofs=int(r.dofs),
                             cg_max=max(c["iters"] for c in DS.CG_LOG), meta_cg=max(r.meta["cg_iterations"]),
                             max_true_rel=max(c["true_rel"] or 0.0 for c in DS.CG_LOG),
                             max_abs_dT_vs_default_K=float(abs(r.T - ref[(case, lv)]).max()),
                             energy_balance=float(r.energy_balance), solve_wall_s=round(float(r.wall_s), 1)))
            print(json.dumps(rows[-1]), flush=True)
FEM._sa_solver = orig
json.dump(rows, open("research/o007_sliver/founder_amg_diagnostic.json", "w"), indent=1)
