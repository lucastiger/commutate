"""A3 convergence and cost benchmark of the scikit-fem thermal cross-check (``moduleforge.solvers.thermal_fem``, T0152).

Two generator layouts by rule (dev seed 20261101, the first DRC-valid ``generate_layouts(1, seed, family=..., dies_per_switch=...)``
of each): ``side_by_side`` with 6 dies per switch and ``u_shaped`` with 2 dies per switch. Coolant 65 C, h = 5000 W/(m2 K), k(T)
(``Layer.k_at``), the same power in every die. The power is chosen per layout so that the *maximum* Tj rise lies in the
60-110 K band (calibrated on the level-0 mesh to ``TARGET_RISE_K`` and rounded to 1 W; the measured rise of the finest
solved level is recorded). Each level of the three-level study (constant refinement ratio 2) is solved in a fresh
subprocess, which reports its own wall time and peak RSS; a level whose estimated memory (estimated DOFs x
``BYTES_PER_DOF``) exceeds the budget is not run and is recorded as ``skipped: memory`` with null values.

Output (``benchmarks/results/thermal_fem_convergence.json``): ``{mode, layouts: [{name, fingerprint, power_per_die_W,
levels: [{level, dofs, wall_s, peak_rss_mb, energy_balance, status}], dies: [{id, tj_max_K: [3 values or null], gci_K,
p_obs}]}]}`` plus extra context keys. ``tj_max_K`` lists the absolute Tj max [K] of levels 0, 1, 2 (coarse -> fine). The
GCI (Roache, same formula as O006 A4, ``thermal_fem.gci``) is taken from the finest, middle and coarsest values; it is
null when a level was skipped. A3 requires ``max gci_K <= 0.025 K``; ``--check`` prints that verdict.

Run: ``uv run python benchmarks/thermal_fem_convergence.py`` (full, writes the JSON); ``--smoke`` runs a coarse rule in a
few seconds and writes nothing unless ``--out`` is given.

Options (T0172, review T0171; defaults reproduce the local run): ``--zrefine`` refines z with the same ratio 2 as lateral
(z counts x2 per level), so the three-grid GCI covers all three directions (the default holds z and reports
``z_sensitivity_K``, 0.020-0.026 K at level 0, which is the size of the A3 limit); ``--h0 MM`` is the lateral size of the
FINEST level near the dies (default 0.125 mm, i.e. 0.5 / 0.25 / 0.125 mm); ``--mem-gb GB`` is the per-solve memory budget
(default 70 % of the host's RAM; levels above DOFs x 7.7 kB are recorded as ``skipped: memory``).

Sizing for an n2-highmem-32 (251 GB), ``--zrefine --h0 0.0625 --mem-gb 235`` (estimate_dofs; 7.7 kB/DOF bound; the
measured peak was 4.4 kB/DOF at 1.5 M DOF; wall from the measured ~70 us/DOF of the lateral-only run, one process per level,
assumed to degrade up to 2x with size, so a range):

    layout          level  DOFs        bound @7.7 kB   expected @4.4 kB   wall
    side_by_side_6  0      0.33 M      2.5 GB          1.4 GB             < 1 min
                    1      2.48 M      19 GB           11 GB              3-6 min
                    2      19.36 M     149 GB          85 GB              25-50 min
    u_shaped_2      0      0.20 M      1.6 GB          0.9 GB             < 1 min
                    1      1.54 M      12 GB           6.8 GB             2-4 min
                    2      11.96 M     92 GB           53 GB              15-30 min

Total about 1-1.7 h including power calibration (level 0 solves); every level fits the 235 GB budget at the bound.
The same run lateral-only (no ``--zrefine``) is 5.1 M / 3.2 M DOF at level 2. Exact command for the burst VM::

    MF_GCP_MAX_HOURS=4 scripts/burst_gcp.sh --cmd "uv run python benchmarks/thermal_fem_convergence.py --zrefine --h0 0.0625 --mem-gb 235 --out benchmarks/results/thermal_fem_convergence_zrefine.json" benchmarks/results
"""
from __future__ import annotations

import argparse
import json
import os
import resource
import subprocess
import sys
import tempfile
import time
from pathlib import Path

T_COOLANT_K = 338.15  # 65 C
H_W_M2K = 5000.0
SEED = 20261101
LAYOUT_RULES = (("side_by_side_6", "side_by_side", 6), ("u_shaped_2", "u_shaped", 2))
TARGET_RISE_K = 85.0  # centre of the 60-110 K band
RISE_BAND_K = (60.0, 110.0)
GCI_LIMIT_K = 0.025
MEMORY_FRACTION = 0.7  # of physical memory a single solve may use (the machine also runs the rest)
DEFAULT_OUT = Path(__file__).resolve().parent / "results" / "thermal_fem_convergence.json"


def _rule(smoke: bool, h0_finest_mm: float | None = None, zrefine: bool = False):
    """Grid rule of the study. ``h0_finest_mm`` is the lateral size [mm] of the FINEST level (level 2) near the dies; the
    level-0 ``GridRule.h0`` is ``REFINEMENT_RATIO**2`` times larger. ``zrefine`` doubles the z counts with the level too."""
    from dataclasses import replace

    from moduleforge.solvers.thermal_fem import LEVELS, REFINEMENT_RATIO, GridRule
    rule = GridRule(**(SMOKE_RULE if smoke else FULL_RULE))
    if h0_finest_mm is not None:
        rule = replace(rule, h0=h0_finest_mm * 1e-3 * REFINEMENT_RATIO ** (len(LEVELS) - 1))
    return replace(rule, zrefine=bool(zrefine))


# The rule of the full run (thermal_fem.GridRule): lateral cells halve at each level (at most 0.5, 0.25, 0.125 mm within
# 1.5 mm of a die, 2x and 4x coarser farther away, an even number of cells per interval); z is held at the counts below at every level (the z error, dominated by
# the 3 mm baseplate, was measured separately: ``z_sensitivity_K`` in the JSON, same pattern as the l2_layout benchmark).
Z_COUNTS = {"baseplate": 6, "solder": 2, "backside_cu": 2, "ceramic": 2, "top_cu": 2, "die_attach": 2, "die": 2}
FULL_RULE = dict(h0=0.5e-3, nz=Z_COUNTS, zrefine=False, near_margin=1.5e-3)
SMOKE_RULE = dict(h0=8.0e-3, nz={k: 1 for k in Z_COUNTS}, zrefine=False)


def get_layout(family: str, dies: int):
    from moduleforge.generate.halfbridge import generate_layouts
    return generate_layouts(1, seed=SEED, family=family, dies_per_switch=dies)[0]


def run_child(family: str, dies: int, level: int, power: float, smoke: bool, out: Path,
              h0_mm: float | None = None, zrefine: bool = False) -> None:
    from moduleforge.solvers import thermal_fem as F
    lay = get_layout(family, dies)
    t0 = time.perf_counter()
    r = F.solve_layout(lay, power, H_W_M2K, T_COOLANT_K, rule=_rule(smoke, h0_mm, zrefine), level=level)
    wall = time.perf_counter() - t0
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * (1.0 if sys.platform == "darwin" else 1024.0)
    out.write_text(json.dumps(dict(dofs=int(r.dofs), wall_s=wall, peak_rss_mb=rss / 1e6, energy_balance=r.energy_balance,
                                   picard_iters=r.picard_iters, picard_residual_K=r.picard_residual,
                                   tj_max_K=[float(v) for v in r.tj_max], tj_mean_K=[float(v) for v in r.tj_mean])))


def solve_in_subprocess(family: str, dies: int, level: int, power: float, smoke: bool, tmp: Path,
                        h0_mm: float | None = None, zrefine: bool = False) -> dict:
    f = tmp / f"{family}_{dies}_{level}.json"
    f.unlink(missing_ok=True)
    cmd = [sys.executable, str(Path(__file__).resolve()), "--child", family, str(dies), str(level), repr(power), str(f)]
    if smoke:
        cmd.append("--smoke")
    if h0_mm is not None:
        cmd += ["--h0", repr(h0_mm)]
    if zrefine:
        cmd.append("--zrefine")
    print("solve", family, dies, "level", level, "P =", power, flush=True)
    subprocess.run(cmd, check=True)
    return json.loads(f.read_text())


def z_sensitivity(family: str, dies: int, power: float, smoke: bool, h0_mm: float | None = None) -> float:
    """Max over dies of |Tj max(z counts doubled) - Tj max(rule)| [K] at level 0 (the z error is level-independent)."""
    from dataclasses import replace

    from moduleforge.solvers import thermal_fem as F
    lay = get_layout(family, dies)
    rule = _rule(smoke, h0_mm)
    fine = replace(rule, nz={k: 2 * v for k, v in rule.nz.items()})
    a = F.solve_layout(lay, power, H_W_M2K, T_COOLANT_K, rule=rule, level=0)
    b = F.solve_layout(lay, power, H_W_M2K, T_COOLANT_K, rule=fine, level=0)
    return float(abs(a.tj_max - b.tj_max).max())


def calibrate_power(family: str, dies: int, smoke: bool, h0_mm: float | None = None, zrefine: bool = False) -> float:
    """Per-die power [W] (rounded to 1 W) giving ``TARGET_RISE_K`` for the hottest die on the level-0 mesh, k(T)."""
    from moduleforge.solvers import thermal_fem as F
    lay = get_layout(family, dies)
    rule = _rule(smoke, h0_mm, zrefine)
    p = 40.0
    for _ in range(4):  # the rise is nearly linear in P; the secant-free fixed point converges in a few steps
        r = F.solve_layout(lay, p, H_W_M2K, T_COOLANT_K, rule=rule, level=0)
        p *= TARGET_RISE_K / float(r.tj_max.max() - T_COOLANT_K)
    return float(max(1.0, round(p)))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--smoke", action="store_true", help="coarse rule, a few seconds; mode = 'smoke'")
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--zrefine", action="store_true",
                    help="refine z with the same ratio 2 as lateral (z counts x2 per level), so the GCI covers all three "
                    "directions; default: lateral only, z held (its error is reported as z_sensitivity_K)")
    ap.add_argument("--h0", type=float, default=None, metavar="MM",
                    help="lateral cell size [mm] of the FINEST level (level 2) within the near-die margin; levels 1 and 0 "
                    "are 2x and 4x coarser. Default: 0.125 (full) i.e. the current 0.5 mm level 0")
    ap.add_argument("--mem-gb", type=float, default=None, metavar="GB",
                    help="memory budget [GB] of one solve: a level whose DOFs x 7.7 kB exceeds it is skipped. Default: "
                    f"{MEMORY_FRACTION * 100:.0f}%% of the host's RAM")
    ap.add_argument("--check", action="store_true", help="exit 1 unless the A3 GCI limit is met by every die")
    ap.add_argument("--child", nargs=5, metavar=("FAMILY", "DIES", "LEVEL", "POWER", "FILE"))
    a = ap.parse_args()
    if a.child:
        run_child(a.child[0], int(a.child[1]), int(a.child[2]), float(a.child[3]), a.smoke, Path(a.child[4]), a.h0, a.zrefine)
        return 0
    from moduleforge.solvers import thermal_fem as F
    mem = F.physical_memory_bytes()
    budget = MEMORY_FRACTION * mem if a.mem_gb is None else a.mem_gb * 1e9
    rule = _rule(a.smoke, a.h0, a.zrefine)
    mode = "smoke" if a.smoke else "full"
    res = dict(mode=mode, seed=SEED, coolant_K=T_COOLANT_K, h_W_m2K=H_W_M2K, k_of_T=True,
               grid_rule=dict(h0_m=rule.h0, nz=rule.nz, zrefine=rule.zrefine, near_margin_m=rule.near_margin,
                          min_cells=rule.min_cells,
                          lateral_ratio=F.REFINEMENT_RATIO),
               physical_memory_gb=mem / 1e9, mem_gb_option=a.mem_gb, memory_budget_gb=budget / 1e9, bytes_per_dof_assumed=F.BYTES_PER_DOF,
               max_dofs_this_machine=F.max_dofs(budget), target_rise_K=TARGET_RISE_K, rise_band_K=list(RISE_BAND_K),
               gci_limit_K=GCI_LIMIT_K, layouts=[])
    with tempfile.TemporaryDirectory() as td:
        for name, family, dies in LAYOUT_RULES:
            lay = get_layout(family, dies)
            P = calibrate_power(family, dies, a.smoke, a.h0, a.zrefine)
            print(name, "fingerprint", lay.fingerprint()[:12], "power per die", P, "W", flush=True)
            levels, vals, mean_vals = [], [], []
            for lv in F.LEVELS:
                est = F.estimate_dofs(lay, rule, lv)
                est_mb = est * F.BYTES_PER_DOF / 1e6
                if est * F.BYTES_PER_DOF > budget:
                    levels.append(dict(level=lv, dofs=None, estimated_dofs=int(est), estimated_memory_mb=est_mb,
                                       wall_s=None, peak_rss_mb=None, energy_balance=None,
                                       status="skipped: memory"))
                    vals.append(None)
                    mean_vals.append(None)
                    continue
                c = solve_in_subprocess(family, dies, lv, P, a.smoke, Path(td), a.h0, a.zrefine)
                levels.append(dict(level=lv, dofs=c["dofs"], estimated_dofs=int(est), estimated_memory_mb=est_mb,
                                   wall_s=c["wall_s"], peak_rss_mb=c["peak_rss_mb"], energy_balance=c["energy_balance"],
                                   picard_iters=c["picard_iters"], picard_residual_K=c["picard_residual_K"],
                                   bytes_per_dof_measured=c["peak_rss_mb"] * 1e6 / c["dofs"],
                                   status="ok" if c["energy_balance"] <= 1e-6 and c["picard_residual_K"] < 1e-4
                                   else "failed: balance or Picard"))
                vals.append(c["tj_max_K"])
                mean_vals.append(c["tj_mean_K"])
            dies_out = []
            for i in range(len(lay.dies)):
                tj = [None if v is None else v[i] for v in vals]
                tm = [None if v is None else v[i] for v in mean_vals]
                if None in tj:
                    g, p = None, None
                else:
                    g, p = F.gci([tj[2], tj[1], tj[0]])
                    p = None if p != p else p
                dies_out.append(dict(id=i, switch=lay.dies[i].switch, tj_max_K=tj, tj_mean_K=tm, gci_K=g, p_obs=p))
            fine = [d["tj_max_K"][2] for d in dies_out if d["tj_max_K"][2] is not None]
            rise = (max(fine) - T_COOLANT_K) if fine else None
            res["layouts"].append(dict(name=name, family=family, dies_per_switch=dies, fingerprint=lay.fingerprint(),
                                       power_per_die_W=P, z_sensitivity_K=None if a.zrefine else z_sensitivity(family, dies, P, a.smoke, a.h0),
                                       tj_rise_max_K_finest=rise,
                                       rise_in_band=None if rise is None else bool(RISE_BAND_K[0] <= rise <= RISE_BAND_K[1]),
                                       levels=levels, dies=dies_out))
    gcis = [d["gci_K"] for x in res["layouts"] for d in x["dies"]]
    res["max_gci_K"] = None if any(g is None for g in gcis) else max(gcis)
    res["a3_gci_met"] = None if res["max_gci_K"] is None else bool(res["max_gci_K"] <= GCI_LIMIT_K)
    out = a.out if a.out is not None else (None if a.smoke else DEFAULT_OUT)
    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(res, indent=1))
        print("wrote", out)
    print("max GCI [K]:", res["max_gci_K"], "A3 limit", GCI_LIMIT_K, "met:", res["a3_gci_met"])
    if a.check and not res["a3_gci_met"]:
        return 1
    return 0


if __name__ == "__main__":
    os.environ.setdefault("PYTHONHASHSEED", "0")
    raise SystemExit(main())
