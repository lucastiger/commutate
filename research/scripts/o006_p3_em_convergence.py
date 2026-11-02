"""O006 pilot P3 (T0154): discretisation study of solvers.l2_layout.loop_inductance on PowerSynth 2D_Case_4 and two
perturbations (research note, NOT evidence; O006 F4).

Each solve runs in a fresh process; the mesh constants of ``moduleforge.solvers.l2_layout`` are overridden in that process
only (module attributes, as research/scripts/l2_layout_lateral_diag.py does; ``src/`` is not modified), then
``loop_inductance(layout, [10 MHz, 20 MHz], refinement=0)`` is called, so the refinement-0 slot carries the level's values.
The thickness layers stay graded to the skin depth at F_MESH = 100 MHz (first layer = min(0.5 delta, uniform)) at every level.

Levels (frozen before the first solve; production = l2_layout's CELL / LAYERS_* / WIRE_EDGES):
  lat1.0    cell 1.0 mm,   layers top/back/base 10/6/6, wire annuli edges E0 (supplementary: all Case 4 features are on 1 mm)
  lat0.5    cell 0.5 mm,   10/6/6, E0   (production refinement 0)
  lat0.25   cell 0.25 mm,  10/6/6, E0   (production refinement 1 = K_STAR, O003's level)
  lat0.125  cell 0.125 mm, 10/6/6, E0   (production refinement 2)
  thk_c     cell 0.5 mm,   5/3/3,  E0   (thickness layer counts halved)
  thk_f     cell 0.5 mm,   20/12/12, E0 (thickness layer counts doubled)
  fil_f     cell 0.5 mm,   10/6/6, E1   (every wire annulus bisected radially: radial annulus width ratio 2)
  E0 = (0, .35, .6, .8, .93, 1) x r: 5 annuli, 1 + 4 x 6 = 25 filaments per wire (WIRE_PHI = 6 fixed)
  E1 = (0, .175, .35, .475, .6, .7, .8, .865, .93, .965, 1) x r: 10 annuli, 1 + 9 x 6 = 55 filaments per wire

Estimators (fixed before the first solve; see research/notes/o006-p3-em-convergence.md):
  three levels, constant ratio r, f1 finest: e21 = f2 - f1, e32 = f3 - f2.  Monotone iff e21 e32 > 0 and |e21| < |e32|.
    monotone: p_obs = ln(e32 / e21) / ln r, f_ext = f1 + (f1 - f2) / (r^p_obs - 1), GCI = 1.25 |e21| / (r^p_obs - 1)
    otherwise: p_obs = None, f_ext = None, GCI = 3 max(|e21|, |e32|)
  two levels (f1 fine, f2 coarse): p_obs = None, f_ext = None, GCI = 3 |f2 - f1| / (r - 1)  (Fs = 3, assumed order 1)
  thickness term (production 10/6/6 is the MIDDLE of thk_c / lat0.5 / thk_f): error of the middle value,
    monotone: 1.25 |e21| r^p / (r^p - 1);  otherwise 3 max(|e21|, |e32|)
  filament term (two levels, production is the coarse one): 3 |f_E1 - f_E0|
  abs_est = GCI_lateral (at the finest lateral level run) + thickness term + filament term (linear sum, conservative).
  pair ratio R = L_pert / L_base per level: the same formulas applied to R.

    uv run python research/scripts/o006_p3_em_convergence.py --run lat0.5 [--geoms case4_base] [--jobs 1] [--max-gb 9]
    uv run python research/scripts/o006_p3_em_convergence.py --assemble
"""
from __future__ import annotations

import argparse
import json
import math
import resource
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "research" / "o006_p3"
SOLVES = OUT / "solves"
FREQS = (1.0e7, 2.0e7)
E0 = (0, .35, .6, .8, .93, 1)
E1 = (0, .175, .35, .475, .6, .7, .8, .865, .93, .965, 1)
LEVELS = {
    "lat1.0": dict(cell_mm=1.0, layers=(10, 6, 6), edges=E0),
    "lat0.5": dict(cell_mm=0.5, layers=(10, 6, 6), edges=E0),
    "lat0.25": dict(cell_mm=0.25, layers=(10, 6, 6), edges=E0),
    "lat0.125": dict(cell_mm=0.125, layers=(10, 6, 6), edges=E0),
    "thk_c": dict(cell_mm=0.5, layers=(5, 3, 3), edges=E0),
    "thk_f": dict(cell_mm=0.5, layers=(20, 12, 12), edges=E0),
    "fil_f": dict(cell_mm=0.5, layers=(10, 6, 6), edges=E1),
    # POST HOC diagnostic, added after fil_f was seen (T0154): E1 with WIRE_PHI 12 (sector aspect kept); not in the estimators
    "fil_f_phi12": dict(cell_mm=0.5, layers=(10, 6, 6), edges=E1, phi=12),
}
# observed lateral order of l2_layout on the six aligned generator ladders 0.5 / 0.25 / 0.125 mm (research/l2_layout_vm,
# l2_layout_vm2, l2_layout_diag; 20 MHz): 0.69, 0.71, 0.71, 0.73, 0.79, 0.80 -> median 0.72 (prior data, not Case 4)
P_ASSUMED = 0.72
GEOMS = ("case4_base", "case4_die_shift", "case4_trace_width")


def _layouts():
    sys.path.insert(0, str(ROOT / "research" / "scripts"))
    import o006_case4_layout as c4
    return c4


def child(geom: str, level: str, out: Path) -> None:
    from moduleforge.solvers import l2_layout as L
    lv = LEVELS[level]
    L.CELL = (lv["cell_mm"] * 1e-3,) + tuple(L.CELL[1:])
    for attr, n in zip(("LAYERS_TOP", "LAYERS_BACK", "LAYERS_BASE"), lv["layers"], strict=True):
        setattr(L, attr, (n,) + tuple(getattr(L, attr)[1:]))
    L.WIRE_EDGES = (tuple(lv["edges"]),) + tuple(L.WIRE_EDGES[1:])
    L.WIRE_PHI = int(lv.get("phi", L.WIRE_PHI))
    lay = _layouts().build(geom.removeprefix("case4_").replace("base", "base"))
    t0 = time.perf_counter()
    r = L.loop_inductance(lay, list(FREQS), refinement=0)
    ru = resource.getrusage(resource.RUSAGE_SELF)
    m = r.meta
    rec = dict(geom=geom, level=level, params=dict(lv, wire_phi=L.WIRE_PHI, f_mesh_hz=L.F_MESH,
                                                   filaments_per_wire=m["mesh_params"]["filaments_per_wire"]),
               L_H={f"{f:.0f}": float(v) for f, v in zip(FREQS, r.L_H, strict=True)},
               R_ohm={f"{f:.0f}": float(v) for f, v in zip(FREQS, r.R_ohm, strict=True)},
               wall_s=time.perf_counter() - t0, cpu_s=ru.ru_utime + ru.ru_stime,
               peak_mem_mb=ru.ru_maxrss * (1.0 if sys.platform == "darwin" else 1024.0) / 1e6,
               n_unknowns=int(m["n_unknowns"]), n_filaments=int(m["n_filaments"]), gmres_iters=[int(x) for x in m["gmres_iters"]],
               gmres_flags=[int(x) for x in m["gmres_flags"]], solver_tol=float(m["solver_tol"]),
               solver_tol_rel_L_max=float(m["solver_tol_rel_L_max"]), layers=m["mesh_params"]["layers"],
               nx=m["mesh_params"]["nx"], ny=m["mesh_params"]["ny"], area_rel_err=m["mesh_params"]["area_rel_err"],
               clamped_vertices=int(m["mesh_params"]["clamped_vertices"]), fingerprint=lay.fingerprint(),
               tool_version=m["tool_version"], source_sha256=m["source_sha256"], status="ok")
    out.write_text(json.dumps(rec, indent=1, default=str))


def run_one(geom: str, level: str) -> dict:
    SOLVES.mkdir(parents=True, exist_ok=True)
    f = SOLVES / f"{geom}__{level}.json"
    if f.exists() and json.loads(f.read_text()).get("status") == "ok":
        return json.loads(f.read_text())
    print(f"solve {geom} {level}", flush=True)
    r = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--child", geom, level, str(f)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        rec = {"geom": geom, "level": level, "status": "failed", "error": (r.stdout + r.stderr)[-3000:]}
        f.write_text(json.dumps(rec, indent=1))
        return rec
    rec = json.loads(f.read_text())
    print(f"{geom} {level}: L = {[round(v * 1e9, 5) for v in rec['L_H'].values()]} nH, {rec['wall_s']:.0f} s, "
          f"{rec['peak_mem_mb']:.0f} MB, {rec['n_unknowns']} unknowns", flush=True)
    return rec


# ------------------------------------------------------------------------------------------------------- estimators
def three_level(f3, f2, f1, r):
    """(p_obs, f_ext, gci, kind) for coarse f3, medium f2, fine f1 at constant ratio r (module docstring)."""
    e21, e32 = f2 - f1, f3 - f2
    if e21 * e32 > 0 and abs(e21) < abs(e32):
        p = math.log(e32 / e21) / math.log(r)
        return p, f1 + (f1 - f2) / (r**p - 1), 1.25 * abs(e21) / (r**p - 1), "monotone"
    return None, None, 3.0 * max(abs(e21), abs(e32)), "oscillatory" if e21 * e32 < 0 else "non-contracting"


def two_level(f2, f1, r):
    return None, None, 3.0 * abs(f2 - f1) / (r - 1), "two-level"


def middle_term(fc, fm, ff, r):
    """Error estimate of the MIDDLE value fm (thickness study: production is the middle count)."""
    e21, e32 = fm - ff, fc - fm
    if e21 * e32 > 0 and abs(e21) < abs(e32):
        p = math.log(e32 / e21) / math.log(r)
        return p, 1.25 * abs(e21) * r**p / (r**p - 1), "monotone"
    return None, 3.0 * max(abs(e21), abs(e32)), "oscillatory" if e21 * e32 < 0 else "non-contracting"


def estimate(get):
    """Apply the estimators to a quantity get(level) -> float | None (L or a ratio).  Returns a dict per the docstring."""
    lat = [lv for lv in ("lat0.5", "lat0.25", "lat0.125") if get(lv) is not None]
    out = {"lateral_levels_used": lat}
    if len(lat) == 3:
        p, fe, g, kind = three_level(get("lat0.5"), get("lat0.25"), get("lat0.125"), 2.0)
        out.update(ladder="0.5/0.25/0.125 mm")
    else:
        # fewer than three requested levels ran (T0154: 0.25 / 0.125 mm do not fit this Mac): the finest two consecutive
        # levels of the nested ladder 1.0 / 0.5 / 0.25 / 0.125 mm (all Case 4 features lie on 1.0 mm), two-level formula
        lat = [lv for lv in ("lat1.0", "lat0.5", "lat0.25", "lat0.125") if get(lv) is not None][-2:]
        if len(lat) == 2:
            p, fe, g, kind = two_level(get(lat[0]), get(lat[1]), 2.0)
            out.update(ladder="/".join(str(LEVELS[x]["cell_mm"]) for x in lat) + " mm")
            # assumed-order Richardson (added after the 0.5 mm results; order from six earlier aligned generator ladders)
            f2, f1 = get(lat[0]), get(lat[1])
            out.update(p_assumed=P_ASSUMED, extrap_assumed_p=f1 + (f1 - f2) / (2.0**P_ASSUMED - 1),
                       extrap_p1=2 * f1 - f2, extrap_p2=f1 + (f1 - f2) / 3.0)
        else:
            p, fe, g, kind = None, None, None, "insufficient"
    out.update(p_obs=p, extrap=fe, gci_lateral=g, lateral_kind=kind, finest_level=lat[-1] if lat else None,
               lateral_levels_used=lat)
    # supplementary coarse ladder 1.0 / 0.5 / 0.25 mm (diagnostic of the asymptotic range; not the requested ladder)
    if all(get(x) is not None for x in ("lat1.0", "lat0.5", "lat0.25")):
        ps, fs_, gs, ks = three_level(get("lat1.0"), get("lat0.5"), get("lat0.25"), 2.0)
        out["supp_1.0_0.5_0.25"] = dict(p_obs=ps, extrap=fs_, gci=gs, kind=ks)
    elif all(get(x) is not None for x in ("lat1.0", "lat0.5")):
        out["supp_1.0_0.5"] = dict(change=get("lat0.5") - get("lat1.0"), rel_change=get("lat0.5") / get("lat1.0") - 1)
    if all(get(x) is not None for x in ("thk_c", "lat0.5", "thk_f")):
        pt, tt, kt = middle_term(get("thk_c"), get("lat0.5"), get("thk_f"), 2.0)
        out.update(p_thickness=pt, thickness_term=tt, thickness_kind=kt, thickness_change_f=get("thk_f") - get("lat0.5"),
                   thickness_change_c=get("lat0.5") - get("thk_c"))
    else:
        out.update(p_thickness=None, thickness_term=None, thickness_kind="not run")
    if get("fil_f") is not None and get("lat0.5") is not None:
        out.update(filament_term=3.0 * abs(get("fil_f") - get("lat0.5")), filament_change=get("fil_f") - get("lat0.5"))
    else:
        out.update(filament_term=None)
    parts = [out["gci_lateral"], out["thickness_term"], out["filament_term"]]
    out["abs_est"] = sum(parts) if all(x is not None for x in parts) else None
    # POST HOC (not the frozen estimator): filament term on the E1 + WIRE_PHI 12 path, which keeps the sector aspect ratio
    if get("fil_f_phi12") is not None and get("lat0.5") is not None:
        out["filament_change_phi12"] = get("fil_f_phi12") - get("lat0.5")
        out["filament_term_phi12_posthoc"] = 3.0 * abs(out["filament_change_phi12"])
        alt = [out["gci_lateral"], out["thickness_term"], out["filament_term_phi12_posthoc"]]
        out["abs_est_posthoc_phi12"] = sum(alt) if all(x is not None for x in alt) else None
    return out


def cost_projection(recs: dict) -> dict:
    """Not-run levels (projection, not measurement).  Unknowns x4 per lateral halving at fixed layers.  Memory: range of
    (a) the measured Case 4 0.5 mm peak times the generator ladder's per-step memory ratios and (b) the generator ladder's
    largest bytes per unknown at that level times the projected unknowns.  Wall: (a) this Mac's 0.5 mm wall times the
    generator per-step wall ratios, (b) the generator VM wall at that level times the unknowns ratio (research/l2_layout_vm,
    research/l2_layout_vm2: five layouts solved at 0.5 / 0.25 / 0.125 mm on an n2-highmem-32 VM, 4 jobs x 8 threads)."""
    b = recs.get(("case4_base", "lat0.5"))
    if not b or b.get("status") != "ok":
        return {}
    gen = {}
    for f in list((ROOT / "research" / "l2_layout_vm").glob("solve_s*_d*_r?.json")) + \
            list((ROOT / "research" / "l2_layout_vm2").glob("solve_s*_d*_r?.json")):
        d = json.loads(f.read_text())
        gen.setdefault(f.stem.rsplit("_r", 1)[0], {})[int(f.stem[-1])] = d
    gen = {k: v for k, v in gen.items() if set(v) == {0, 1, 2}}
    mem, wall, n = b["peak_mem_mb"], b["wall_s"], b["n_unknowns"]
    out = {}
    for lv, k in (("lat0.25", 1), ("lat0.125", 2)):
        mr = [math.prod(v[j]["peak_rss_gb"] / v[j - 1]["peak_rss_gb"] for j in range(1, k + 1)) for v in gen.values()]
        wr = [math.prod(v[j]["wall_s"] / v[j - 1]["wall_s"] for j in range(1, k + 1)) for v in gen.values()]
        bpu = max(v[k]["peak_rss_gb"] * 1e9 / v[k]["n_unknowns"] for v in gen.values())
        nk = n * 4**k
        vm_wall = [v[k]["wall_s"] * nk / v[k]["n_unknowns"] for v in gen.values()]
        m_lo, m_hi = mem * min(mr), max(mem * max(mr), bpu * nk / 1e6)
        w_lo, w_hi = wall * min(wr), max(wall * max(wr), max(vm_wall))
        own = [d["peak_mem_mb"] * 1e6 / d["n_unknowns"] for (g, lv_), d in recs.items()
               if g == "case4_base" and d.get("status") == "ok" and LEVELS[lv_]["cell_mm"] == 0.5]
        out[lv] = dict(n_unknowns_est=nk, peak_mem_mb_est=[m_lo, m_hi], wall_s_est=[w_lo, w_hi],
                       peak_mem_mb_case4_bytes_per_unknown=[min(own) * nk / 1e6, max(own) * nk / 1e6],
                       generator_layouts_used=sorted(gen), reason="projected peak memory exceeds what this 16 GB Mac can "
                       "hold beside the agents; agents may not launch burst VMs (docs/INFRASTRUCTURE.md: the founder runs "
                       "scripts/burst*.sh with the founder's cloud credentials)")
    return out


def assemble() -> int:
    c4 = _layouts()
    recs = {}
    for f in sorted(SOLVES.glob("*.json")):
        d = json.loads(f.read_text())
        recs[(d["geom"], d["level"])] = d
    proj = cost_projection(recs)
    G = c4.geometries()
    geoms, est = [], {}
    for g in GEOMS:
        levels = []
        for lv, spec in LEVELS.items():
            d = recs.get((g, lv))
            row = dict(level=lv, cell_mm=spec["cell_mm"], params=dict(layers_top_back_base=list(spec["layers"]),
                       wire_annulus_edges_r=list(spec["edges"]), filaments_per_wire=1 + spec.get("phi", 6) * (len(spec["edges"]) - 2),
                       wire_phi=spec.get("phi", 6)))
            if d and d.get("status") == "ok":
                row.update(L_H=d["L_H"], wall_s=d["wall_s"], peak_mem_mb=d["peak_mem_mb"], status="ok",
                           cpu_s=d["cpu_s"], n_unknowns=d["n_unknowns"], gmres_iters=d["gmres_iters"],
                           solver_tol_rel_L_max=d["solver_tol_rel_L_max"], R_ohm=d["R_ohm"])
            else:
                row.update(L_H={f"{f:.0f}": None for f in FREQS}, wall_s=None, peak_mem_mb=None,
                           status=(d or {}).get("status", "not_run"), cost_estimate=proj.get(lv))
            levels.append(row)
        per_f = {}
        for f in FREQS:
            k = f"{f:.0f}"
            per_f[k] = estimate(lambda lv, g=g, k=k: (recs.get((g, lv)) or {}).get("L_H", {}).get(k))
        est[g] = per_f
        geoms.append(dict(name=g, fingerprint=G[g].fingerprint(), levels=levels,
                          p_obs={k: v["p_obs"] for k, v in per_f.items()},
                          L_extrap_H={k: v["extrap"] if v["extrap"] is not None else v.get("extrap_assumed_p")
                                      for k, v in per_f.items()},
                          L_extrap_kind={k: "observed-order" if v["extrap"] is not None else
                                         f"assumed-order p={P_ASSUMED} (two levels)" for k, v in per_f.items()},
                          abs_est_H={k: v["abs_est"] for k, v in per_f.items()},
                          abs_est_posthoc_phi12_H={k: v.get("abs_est_posthoc_phi12") for k, v in per_f.items()},
                          estimates=per_f))
    pairs = []
    for g in GEOMS[1:]:
        for f in FREQS:
            k = f"{f:.0f}"

            def ratio(lv, g=g, k=k):
                a = (recs.get((g, lv)) or {}).get("L_H", {}).get(k)
                b = (recs.get(("case4_base", lv)) or {}).get("L_H", {}).get(k)
                return a / b if a is not None and b is not None else None
            e = estimate(ratio)
            pairs.append(dict(pert=g.removeprefix("case4_"), freq_hz=f,
                              ratio_per_level={lv: ratio(lv) for lv in LEVELS}, ratio_est=e["abs_est"],
                              ratio_est_posthoc_phi12=e.get("abs_est_posthoc_phi12"), estimates=e))
    c = c4
    res = dict(powersynth_commit=c.POWERSYNTH_COMMIT, powersynth_repo=c.POWERSYNTH_REPO, sources_sha256=c.SOURCES_SHA256,
               note="research note, not evidence (O006 F4); see research/notes/o006-p3-em-convergence.md",
               solver="moduleforge.solvers.l2_layout.loop_inductance", freqs_hz=list(FREQS),
               perturbations=c.PERTURBATIONS, levels_def={k: dict(v, edges=list(v["edges"])) for k, v in LEVELS.items()},
               estimator_formulas=__doc__.split("Estimators")[1].split("    uv run")[0].strip(),
               geometries=geoms, pair_ratios=pairs, cost_projection_not_run=proj)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "results.json").write_text(json.dumps(res, indent=1, default=str))
    (OUT / "tables.md").write_text(tables(res))
    print(json.dumps({g["name"]: {"abs_est_H": g["abs_est_H"], "p_obs": g["p_obs"]} for g in geoms}, indent=1))
    return 0


def tables(res: dict) -> str:
    """Markdown tables of results.json (generated; the note cites them)."""
    def nh(v, d=4):
        return "-" if v is None else f"{v * 1e9:.{d}f}"
    lines = ["# O006 P3 tables (generated by o006_p3_em_convergence.py --assemble; research note, not evidence)", "",
             "## L per level (nH) at 10 / 20 MHz; wall s; peak MB", "",
             "| level | cell mm | layers | fil/wire | " + " | ".join(g["name"] for g in res["geometries"]) + " |",
             "|---|---|---|---|" + "---|" * len(res["geometries"])]
    for i, lv in enumerate(res["geometries"][0]["levels"]):
        cells = []
        for g in res["geometries"]:
            r = g["levels"][i]
            if r["status"] == "ok":
                cells.append(f"{nh(r['L_H']['10000000'])} / {nh(r['L_H']['20000000'])} ({r['wall_s']:.0f} s, "
                             f"{r['peak_mem_mb']:.0f} MB)")
            else:
                cells.append(r["status"])
        p = lv["params"]
        lines.append(f"| {lv['level']} | {lv['cell_mm']} | {'/'.join(map(str, p['layers_top_back_base']))} | "
                     f"{p['filaments_per_wire']} | " + " | ".join(cells) + " |")
    lines += ["", "## Estimates (nH)", "", "| geometry | f MHz | lateral (kind, ladder) | GCI lat | p_thk | thk term | "
              "fil change | fil term | abs_est | abs_est % | L_extrap (kind) | L_ext p=1 / p=2 | post hoc: fil change phi12 | "
              "abs_est with phi12 fil term |", "|---" * 14 + "|"]
    for g in res["geometries"]:
        for k, e in g["estimates"].items():
            l05 = next(r for r in g["levels"] if r["level"] == "lat0.5")["L_H"][k]
            pct = "-" if e["abs_est"] is None or l05 is None else f"{100 * e['abs_est'] / l05:.2f}"
            pt = "-" if e["p_thickness"] is None else f"{e['p_thickness']:.2f}"
            lines.append(f"| {g['name']} | {float(k) / 1e6:g} | {e['lateral_kind']}, {e.get('ladder')} | "
                         f"{nh(e['gci_lateral'])} | {pt} | {nh(e['thickness_term'])} | {nh(e.get('filament_change'))} | "
                         f"{nh(e['filament_term'])} | {nh(e['abs_est'])} | {pct} | {nh(g['L_extrap_H'][k])} "
                         f"({g['L_extrap_kind'][k]}) | {nh(e.get('extrap_p1'))} / {nh(e.get('extrap_p2'))} | "
                         f"{nh(e.get('filament_change_phi12'))} | {nh(e.get('abs_est_posthoc_phi12'))} |")
    lines += ["", "## Pair ratios L_pert / L_base", "", "| pert | f MHz | " + " | ".join(res["levels_def"]) +
              " | lateral GCI | thk term | fil term | ratio_est | post hoc: ratio_est with phi12 fil term |",
              "|---|---|" + "---|" * (len(res["levels_def"]) + 5)]
    for pr in res["pair_ratios"]:
        e = pr["estimates"]

        def f6(v):
            return "-" if v is None else f"{v:.6f}"
        lines.append(f"| {pr['pert']} | {pr['freq_hz'] / 1e6:g} | " + " | ".join(f6(pr["ratio_per_level"][lv])
                     for lv in res["levels_def"]) + f" | {f6(e['gci_lateral'])} | {f6(e['thickness_term'])} | "
                     f"{f6(e['filament_term'])} | {f6(pr['ratio_est'])} | {f6(e.get('abs_est_posthoc_phi12'))} |")
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--child", nargs=3)
    ap.add_argument("--run", nargs="*")
    ap.add_argument("--geoms", nargs="*", default=list(GEOMS))
    ap.add_argument("--jobs", type=int, default=1)
    ap.add_argument("--assemble", action="store_true")
    a = ap.parse_args()
    if a.child:
        child(a.child[0], a.child[1], Path(a.child[2]))
        return 0
    if a.run:
        tasks = [(g, lv) for lv in a.run for g in a.geoms]
        with ThreadPoolExecutor(a.jobs) as ex:
            list(ex.map(lambda t: run_one(*t), tasks))
    if a.assemble:
        return assemble()
    return 0


if __name__ == "__main__":
    sys.exit(main())
