"""O007 benchmark (T0242, founder path A, I0128): opt-in order-1 AMG smoother ``GridRule.amg_gs_sweeps``.

Reproduces the level-0 rows of the founder diagnostic (research/o007_sliver/founder_amg_diagnostic.json) through the
production API instead of a monkeypatch: Muzychka Cases 1a and 1b under T0228's candidate 1 exactly
(research/o007_dev2/frozen_config.json, max_lines), solved by ``solve_box_stack`` once with the default rule and once with
``dataclasses.replace(rule, amg_gs_sweeps=2)``. Not an evidence run (no criterion, no reference comparison). Run from the
repository root; writes benchmarks/o007_amg_sweeps.json."""
from __future__ import annotations

import dataclasses
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "research" / "scripts")]

import o007_sliver as S  # noqa: E402

FEM, DS, D2 = S.FEM, S.DS, S.D2
OUT = ROOT / "benchmarks" / "o007_amg_sweeps.json"


def main() -> None:
    ser = DS.load_refs()[0]
    rule = D2.rule_of(S.CID)
    rows = []
    for case in S.CASES:
        b = S.variant_problem(ser, case, "max_lines")
        T_default = None
        for sweeps in (None, 2):
            r = FEM.solve_box_stack(b["a"], b["b"], b["layers"], b["h"], b["Tc"], b["srcs"],
                                    rule=dataclasses.replace(rule, amg_gs_sweeps=sweeps), level=0, extra_lines=b["extra"])
            if sweeps is None:
                T_default = r.T
            rows.append(dict(case=case, level=0, amg_gs_sweeps=sweeps, meta_amg_gs_sweeps=r.meta["amg_gs_sweeps"],
                             dofs=int(r.dofs), cg_max=int(r.meta["cg_max_iterations"]),
                             linear_rel_residual_max=float(r.meta["linear_rel_residual_max"]),
                             max_abs_dT_vs_default_K=float(abs(r.T - T_default).max()),
                             energy_balance=float(r.energy_balance), solve_wall_s=round(float(r.wall_s), 2)))
            print(json.dumps(rows[-1]), flush=True)
    OUT.write_text(json.dumps({"rows": rows}, indent=1) + "\n")


if __name__ == "__main__":
    main()
