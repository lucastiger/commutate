"""O006 pilot P3 (T0154): PowerSynth 2D_Case_4 re-modelled as a ModuleForge Layout, plus two documented perturbations.

Research script, NOT evidence (O006 F4: 2D_Case_4 and its perturbations are pilot geometry, excluded from O003's and O004's
judged sets).  Per D0007 the GPL-3.0 sample files are never committed, copied or imported: this file holds only geometry
FACTS (numbers) transcribed by hand from the files listed in SOURCES, which were downloaded to a temporary directory outside
the repository and hashed there.  Nothing here reads a PowerSynth file (``--check --sources DIR`` only re-hashes them).

Source: e3da/PowerSynth2-pkg, commit a1de7ced949c0fd0105d166767b1de8705eb65ab ("250616 v2.2 stable release", 2025-06-17),
work/Sample_Designs/2D_Case_4 (GPL-3.0).

Geometry facts used (all mm; PowerSynth's (x, y, w, h) = lower-left corner and size, absolute coordinates in the baseplate
frame: the axes of Figs/initial_layout_I1.png span the 70 x 100 mm substrate at origin (5, 5), inference from that figure):
  layer_stack.csv   baseplate Cu 80 x 110 x 1.0 at (0, 0); bottom metal Cu 70 x 100 x 0.2 at (5, 5); AlN 70 x 100 x 0.835;
                    top Cu (I1) 70 x 100 x 0.2; device layer C1 0.18
  layout_geometry_script.txt  ("+" starts a copper island, "-" joins the previous one; Trace_ori.txt only sets orientation)
                    island A = T3 (25,30,30,10) u T11 (55,30,10,68) u T5 (25,55,30,5); holds D1, D2 (drain) and power lead L4
                    island B = T4 (20,45,32,5) u T9 (10,10,10,40); power lead L2
                    island C = T6 (20,70,32,10) u T10 (10,55,10,25); holds D3, D4 (drain) and power lead L3
                    signal traces T1 (25,10,40,8), T2 (25,20,40,8), T7 (10,82,42,8), T8 (10,93,42,5)
                    dies D1 (28,32), D2 (38,32), D3 (28,72), D4 (38,72); leads L2 (12,35), L3 (12,63), L4 (57,67)
                    bond points (0.25 x 0.25 pads): B3 (29,47), B4 (40,47), B5 (29,57), B6 (40,57), B11 (29,35),
                    B12 (40,35), B13 (29,73), B15 (40,73)
  bond_wires_setup.txt  power wires BW3 D1_Source_B11 -> B3, BW4 D2_Source_B12 -> B4, BW5 D3_Source_B13 -> B5,
                    BW6 D4_Source_B15 -> B6, one wire each ("1 0.1" = 1 wire, 0.1 mm pitch); gate wires BW1, BW2, BW7, BW8;
                    Kelvin-source wires BW9..BW12
  Part_Lib/MOSFET.part  CPM2-1200-0025B, footprint 4 x 6, thickness 0.18, source pad (0.335, 0.35, 3.5, 4.5) on the die
  Part_Lib/power_lead.part  footprint 3 x 3 (lead post height 2 mm: not modelled)
  Wire_Lib/bond_wire_info.wire  radius 0.15 (JEDEC 4-point shape; its loop height is not in the files read)

Net assignment (inference from the connectivity, consistent with a half-bridge): island C carries the drains of D3/D4 and
lead L3 -> DC+ (D3, D4 high side); island A carries the drains of D1/D2 and receives the D3/D4 source wires -> PHASE (lead L4);
island B receives the D1/D2 source wires -> DC- (lead L2).  The ModuleForge port is the commutation loop DC+ (L3 centre) ->
D3/D4 -> BW5/BW6 -> PHASE -> D1/D2 -> BW3/BW4 -> DC- (L2 centre), phase open (Layout docstring).  PowerSynth's own
macro_script measure (Source L4 -> Sink L2 at 1 MHz) is a different loop (phase to DC-); 2D_Case_4 has no published value.

Modelling choices (stated, not facts of the source):
  M1 gate wires (BW1, BW2, BW7, BW8) are omitted: the die is an ideal short of its footprint, so a gate wire would short the
     gate net to the power path, which the gate oxide does not.
  M2 Kelvin-source wires (BW9..BW12) are omitted: in the ideal-short die model they would join the drain node and form a
     >= 34 mm wire path in parallel with the phase / DC+ copper between paralleled dies.
  M3 signal traces T1, T2, T7, T8 are kept as floating copper (nets SIG_*; eddy currents only, one grounded node each).
  M4 wire feet at the 0.25 mm pad centres (x + 0.125, y + 0.125); wire shape arc_wire (sine profile) with loop height 1.0 mm
     (assumption: the JEDEC 4-point height is not given in the files read); diameter 0.30 mm; Al sigma (stack.SIGMA_AL_WIRE).
  M5 LayerStack requires a solder layer between baseplate and backside Cu; PowerSynth's stack has none, so it is 1 um thick
     (not a conductor in Layout.to_conductors(): only a 1 um z offset).  Die attach thickness 0 (C1 sits on I1 in the source).
  M6 backside Cu = the full 70 x 100 substrate outline (backside_inset = 0), as in layer_stack.csv.
  M7 power leads are not modelled; the port terminals sit at the lead-footprint centres on the top-Cu surface.

Perturbations (frozen in this file before any solve; integer-mm moves so every geometry stays on the 1.0 / 0.5 / 0.25 / 0.125
mm lattices; both keep constraint.csv's 1 mm minimum spacing and enclosure):
  die_shift   high-side dies D3, D4 (and their source-wire start points) moved -1.0 mm in y (die y 72 -> 71, enclosure in T6
              2 -> 1 mm); wire feet on T5 unchanged, so BW5 / BW6 shorten from 16.0 to 15.0 mm.
  trace_width DC- trace T4 widened from 5 to 7 mm by moving its lower edge from y = 45 to 43 mm (gap to T3 5 -> 3 mm); wire feet
              unchanged.

    uv run python research/scripts/o006_case4_layout.py --check [--sources DIR]   # exit 0 iff every check passes
    uv run python research/scripts/o006_case4_layout.py --facts                   # print fingerprints and key numbers
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
from shapely.geometry import Polygon, box
from shapely.ops import unary_union

from moduleforge.geometry import DC_MINUS, DC_PLUS
from moduleforge.geometry.layout import PHASE, Die, Layout, Terminal, Trace, arc_wire
from moduleforge.geometry.stack import SIGMA_CU, SIGMA_SOLDER, Layer, LayerStack

POWERSYNTH_REPO = "e3da/PowerSynth2-pkg"
POWERSYNTH_COMMIT = "a1de7ced949c0fd0105d166767b1de8705eb65ab"
SOURCE_DIR = "work/Sample_Designs/2D_Case_4"
# sha256 of every file read (downloaded at POWERSYNTH_COMMIT from raw.githubusercontent.com on 2026-11-01, outside the repo)
SOURCES_SHA256 = {
    f"{SOURCE_DIR}/README.txt": "624a2251f18fa90f2502abeaed4d6fbb33bf633333c5b69ebdd20d28ce71ce41",
    f"{SOURCE_DIR}/layout_geometry_script.txt": "14ae3d2018dedfdfa1494c71b10afd59afbebbd759d06b0ba448c2962471b312",
    f"{SOURCE_DIR}/layer_stack.csv": "bc47fe942b59247672b31252c13550c047d0fb1dcc1608c02f70ff8e899ec678",
    f"{SOURCE_DIR}/bond_wires_setup.txt": "ad2c2e93c559e3b8c5c38b54befbbd740c0f6843df2cb541cd2dce53c0aef678",
    f"{SOURCE_DIR}/constraint.csv": "670d9c7ff7ed147841c110c68f7b2442c5933e5d90c3a642a18daf43975abbba",
    f"{SOURCE_DIR}/macro_script.txt": "5492a038f08ab76cc3bc12834ac867eeda317742f1ac0dc2d1daf17951daf566",
    f"{SOURCE_DIR}/Trace_ori.txt": "f808683b16ee2a7eba3fc2018822e5a790d25e352fe9430f2418aaa4b2f269eb",
    f"{SOURCE_DIR}/Part_Lib/MOSFET.part": "ae226bc07c737c25a13f28212b2c711633a375df408e6d6114d4fc8c26ec1533",
    f"{SOURCE_DIR}/Part_Lib/power_lead.part": "416ec39693c0535f2424da7ffc61cc8b3c40a479d0ba81d0a1a307164caf53ee",
    f"{SOURCE_DIR}/Part_Lib/signal_lead.part": "aee35aed62b5917ae066b05cf1c1142014d3451f178cd037068d63a1fef2e232",
    f"{SOURCE_DIR}/Wire_Lib/bond_wire_info.wire": "b03a77ca662fa66d28f0e8074e9ca6d2fdaf588c5ba13af369e56269100e3ed1",
    f"{SOURCE_DIR}/Figs/initial_layout_I1.png": "ee6e1e260268b15ba04cb04e94582a780d2a360bcba856286e2dbf8c08e0a63a",
}

MM = 1e-3
# --- facts (mm), see the module docstring
BASEPLATE = (0.0, 0.0, 80.0, 110.0)  # x0, y0, w, h
SUBSTRATE = (5.0, 5.0, 70.0, 100.0)
T_BASE, T_BACK, T_CER, T_TOP, T_DIE = 1.0, 0.2, 0.835, 0.2, 0.18
ISLANDS = {  # net: list of (x, y, w, h)
    PHASE: [(25, 30, 30, 10), (55, 30, 10, 68), (25, 55, 30, 5)],  # T3, T11, T5
    DC_MINUS: [(20, 45, 32, 5), (10, 10, 10, 40)],  # T4, T9
    DC_PLUS: [(20, 70, 32, 10), (10, 55, 10, 25)],  # T6, T10
}
SIGNAL = {"SIG_LS_KS": (25, 10, 40, 8), "SIG_LS_G": (25, 20, 40, 8), "SIG_HS_G": (10, 82, 42, 8),
          "SIG_HS_KS": (10, 93, 42, 5)}  # T1, T2, T7, T8 (floating, M3)
DIE_FOOT = (4.0, 6.0)
SOURCE_PAD = (0.335, 0.35, 3.5, 4.5)  # relative to the die's lower-left corner
DIES = {"D1": ((28, 32), "LS"), "D2": ((38, 32), "LS"), "D3": ((28, 72), "HS"), "D4": ((38, 72), "HS")}
LEADS = {DC_MINUS: (12, 35), DC_PLUS: (12, 63), PHASE: (57, 67)}  # L2, L3, L4; 3 x 3 footprint
LEAD_FOOT = 3.0
PAD = 0.25  # bond point pad size
POWER_WIRES = [  # name, die, start bond point (on die source pad), end bond point, landing net
    ("BW3", "D1", (29, 35), (29, 47), DC_MINUS),
    ("BW4", "D2", (40, 35), (40, 47), DC_MINUS),
    ("BW5", "D3", (29, 73), (29, 57), PHASE),
    ("BW6", "D4", (40, 73), (40, 57), PHASE),
]
WIRE_DIAMETER = 0.30  # Wire_Lib radius 0.15
LOOP_HEIGHT = 1.0  # M4 assumption
MIN_SPACING = MIN_ENCLOSURE = 1.0  # constraint.csv

PERTURBATIONS = {
    "die_shift": "high-side dies D3, D4 and their source-wire start points moved -1.0 mm in y; wire feet fixed (16 -> 15 mm)",
    "trace_width": "DC- trace T4 widened 5 -> 7 mm (lower edge y 45 -> 43 mm); wire feet fixed",
}
GEOMETRY_NAMES = ("case4_base", "case4_die_shift", "case4_trace_width")


def case4_stack() -> LayerStack:
    return LayerStack((
        Layer("baseplate", "Cu", T_BASE * MM, SIGMA_CU, 385.0),
        Layer("solder", "none (M5)", 1e-6, SIGMA_SOLDER, 58.0),
        Layer("backside_cu", "Cu", T_BACK * MM, SIGMA_CU, 385.0),
        # k of AlN is not used by the EM solver (placeholder 170 W/(m K), typical sintered AlN)
        Layer("ceramic", "AlN", T_CER * MM, 0.0, 170.0),
        Layer("top_cu", "Cu", T_TOP * MM, SIGMA_CU, 385.0),
    ), kind="PowerSynth_2D_Case_4")


def _rect(x, y, w, h):
    return box(x * MM, y * MM, (x + w) * MM, (y + h) * MM)


def _facts(variant: str):
    """Deep copies of the fact tables with the perturbation applied (mm)."""
    islands = {k: [tuple(r) for r in v] for k, v in ISLANDS.items()}
    dies = {k: (tuple(p), s) for k, (p, s) in DIES.items()}
    wires = [tuple(w) for w in POWER_WIRES]
    if variant == "die_shift":
        for k in ("D3", "D4"):
            (x, y), s = dies[k]
            dies[k] = ((x, y - 1.0), s)
        wires = [(n, d, (a[0], a[1] - 1.0) if d in ("D3", "D4") else a, b, net) for n, d, a, b, net in wires]
    elif variant == "trace_width":
        x, y, w, h = islands[DC_MINUS][0]
        islands[DC_MINUS][0] = (x, y - 2.0, w, h + 2.0)
    elif variant != "base":
        raise ValueError(variant)
    return islands, dies, wires


def build(variant: str = "base") -> Layout:
    """The Case 4 Layout ('base') or one of PERTURBATIONS."""
    islands, dies_f, wires_f = _facts(variant)
    stack = case4_stack()
    traces = []
    for net, rects in islands.items():
        poly = unary_union([_rect(*r) for r in rects])
        if not isinstance(poly, Polygon):
            raise ValueError(f"{net} island is not one polygon")
        traces.append(Trace(net, poly))
    for net, r in SIGNAL.items():
        traces.append(Trace(net, _rect(*r)))
    dies, by_name = [], {}
    for name, ((x, y), sw) in dies_f.items():
        w, h = DIE_FOOT
        sx, sy, sw_, sh = SOURCE_PAD
        pads = {"source": tuple(v * MM for v in (x + sx, y + sy, x + sx + sw_, y + sy + sh))}
        d = Die((x + w / 2) * MM, (y + h / 2) * MM, w * MM, h * MM, sw, pads, thickness=T_DIE * MM, attach_thickness=0.0)
        dies.append(d)
        by_name[name] = d
    z_top = stack.z_top("top_cu")
    wires = []
    for _, dname, a, b, net in wires_f:
        d = by_name[dname]
        p0 = ((a[0] + PAD / 2) * MM, (a[1] + PAD / 2) * MM)
        p1 = ((b[0] + PAD / 2) * MM, (b[1] + PAD / 2) * MM)
        wires.append(arc_wire(p0, p1, z_top + d.attach_thickness + d.thickness, z_top, LOOP_HEIGHT * MM,
                              WIRE_DIAMETER * MM, net))
    terminals = {net: Terminal(net, (x + LEAD_FOOT / 2) * MM, (y + LEAD_FOOT / 2) * MM, LEAD_FOOT * MM, LEAD_FOOT * MM)
                 for net, (x, y) in LEADS.items()}
    return Layout(family="powersynth_2D_Case_4" + ("" if variant == "base" else f"_{variant}"), dies_per_switch=2,
                  outline=_rect(*SUBSTRATE), traces=traces, dies=dies, wires=wires, terminals=terminals,
                  baseplate_outline=_rect(*BASEPLATE), stack=stack, backside_inset=0.0)


def geometries() -> dict[str, Layout]:
    return {"case4_base": build("base"), "case4_die_shift": build("die_shift"), "case4_trace_width": build("trace_width")}


# ------------------------------------------------------------------------------------------------------------- checks
def _check_layout(name: str, lay: Layout, errs: list[str]) -> dict:
    from shapely.geometry import Point

    from moduleforge.solvers import l2_layout as L2
    tr = {t.net: t.polygon for t in lay.traces}
    # traces disjoint with >= MIN_SPACING between different nets
    nets = list(tr)
    for i in range(len(nets)):
        for j in range(i + 1, len(nets)):
            gap = tr[nets[i]].distance(tr[nets[j]]) / MM
            if gap < MIN_SPACING - 1e-9:
                errs.append(f"{name}: {nets[i]} / {nets[j]} spacing {gap:.3f} mm < {MIN_SPACING}")
    sub = lay.outline
    for n, p in tr.items():
        if not sub.contains(p):
            errs.append(f"{name}: trace {n} leaves the substrate")
    # dies on their drain net with >= MIN_ENCLOSURE
    want = {"HS": DC_PLUS, "LS": PHASE}
    for k, d in enumerate(lay.dies):
        enc = tr[want[d.switch]].buffer(-MIN_ENCLOSURE * MM + 1e-12, join_style="mitre")
        if not enc.contains(d.box):
            errs.append(f"{name}: die {k} ({d.switch}) not enclosed by >= {MIN_ENCLOSURE} mm of {want[d.switch]}")
        x0, y0, x1, y1 = d.pads["source"]
        if not d.box.contains(box(x0, y0, x1, y1)):
            errs.append(f"{name}: die {k} source pad outside the die")
    # wires: start on a die source pad at die-top height, end on the landing net's trace at the top-Cu surface
    z_top = lay.top_cu_z()[1]
    for k, w in enumerate(lay.wires):
        p0, p1 = w.points[0], w.points[-1]
        on_die = [d for d in lay.dies if box(*d.pads["source"]).contains(Point(p0[0], p0[1]))]
        if len(on_die) != 1 or abs(p0[2] - lay.die_z_range(on_die[0])[1]) > 1e-12:
            errs.append(f"{name}: wire {k} does not start on exactly one die source pad at die-top height")
        if not tr[w.net].contains(Point(p1[0], p1[1])) or abs(p1[2] - z_top) > 1e-12:
            errs.append(f"{name}: wire {k} does not land on its net {w.net}")
        if on_die and {"HS": PHASE, "LS": DC_MINUS}[on_die[0].switch] != w.net:
            errs.append(f"{name}: wire {k} lands on {w.net}, not the commutation-loop net of its die")
    for net, t in lay.terminals.items():
        if not tr[net].contains(box(t.cx - t.w / 2, t.cy - t.h / 2, t.cx + t.w / 2, t.cy + t.h / 2)):
            errs.append(f"{name}: terminal {net} footprint not on its trace")
    # commutation loop: DC+ -> HS dies -> PHASE -> LS dies -> DC- (graph over nets via dies and wires)
    hs = [d for d in lay.dies if d.switch == "HS"]
    ls = [d for d in lay.dies if d.switch == "LS"]
    if len(hs) != 2 or len(ls) != 2 or len(lay.wires) != 4:
        errs.append(f"{name}: expected 2 HS, 2 LS dies and 4 power wires")
    # on the 0.5 / 0.25 / 0.125 mm lattices (and 1.0 mm, the supplementary level): cells full or empty, areas exact
    cm = lay.to_conductors()
    areas = {}
    for cell in (1.0e-3, 0.5e-3, 0.25e-3, 0.125e-3):
        saved = L2.CELL
        try:
            L2.CELL = (cell,) + tuple(saved[1:])
            fill = L2.cell_fill(cm, *L2.layout_lattice(cm, 0))
            lat = L2.layout_lattice(cm, 0)
            for d in cm.shorts:
                L2.check_on_lattice(d.x - d.w / 2, d.x + d.w / 2, d.y - d.h / 2, d.y + d.h / 2, *lat[:4], f"die {d.die_index}")
        except ValueError as e:
            errs.append(f"{name}: not on the {cell * 1e3:g} mm lattice: {e}")
            continue
        finally:
            L2.CELL = saved
        rel = max(abs(rep - ex) / ex for rep, ex in fill["area"].values())
        areas[f"{cell * 1e3:g}mm"] = rel
        if rel > 1e-12:
            errs.append(f"{name}: represented area off by {rel:.2e} at {cell * 1e3:g} mm")
    return {"fingerprint": lay.fingerprint(), "area_rel_err": areas,
            "copper_mm2": {n: round(p.area / MM**2, 6) for n, p in tr.items()},
            "wire_lengths_mm": [round(w.length / MM, 4) for w in lay.wires]}


def check(sources: str | None = None) -> int:
    errs: list[str] = []
    G = geometries()
    info = {n: _check_layout(n, lay, errs) for n, lay in G.items()}
    fps = [v["fingerprint"] for v in info.values()]
    if len(set(fps)) != 3:
        errs.append("geometries do not have three distinct fingerprints")
    # each perturbation changes exactly what it documents
    b, ds, tw = (info[n] for n in GEOMETRY_NAMES)
    if ds["copper_mm2"] != b["copper_mm2"]:
        errs.append("die_shift changed copper areas")
    dl = [round(x - y, 6) for x, y in zip(ds["wire_lengths_mm"], b["wire_lengths_mm"], strict=True)]
    if not (abs(dl[0]) < 1e-9 and abs(dl[1]) < 1e-9 and dl[2] < -0.9 and dl[3] < -0.9):
        errs.append(f"die_shift wire length changes {dl} (expected 0, 0, ~-1, ~-1 mm)")
    dA = {n: round(tw["copper_mm2"][n] - b["copper_mm2"][n], 6) for n in b["copper_mm2"]}
    if dA != {n: (64.0 if n == DC_MINUS else 0.0) for n in dA}:
        errs.append(f"trace_width copper changes {dA} (expected +64 mm^2 on DC- only)")
    if tw["wire_lengths_mm"] != b["wire_lengths_mm"]:
        errs.append("trace_width changed wires")
    # the transcribed numbers: island areas from the script (mm^2)
    exp = {PHASE: 300 + 680 + 150, DC_MINUS: 160 + 400, DC_PLUS: 320 + 250}
    for n, a in exp.items():
        if abs(b["copper_mm2"][n] - a) > 1e-6:
            errs.append(f"base {n} area {b['copper_mm2'][n]} != {a}")
    # no PowerSynth file inside the repository
    root = Path(__file__).resolve().parents[2]
    names = {Path(p).name for p in SOURCES_SHA256} - {"README.txt"}
    for p in (root / "research").rglob("*"):
        if p.is_file() and p.name in names:
            errs.append(f"PowerSynth file name found in the repository: {p.relative_to(root)}")
    if sources:
        base = Path(sources)
        for rel, h in SOURCES_SHA256.items():
            f = base / Path(rel).relative_to(SOURCE_DIR)
            got = hashlib.sha256(f.read_bytes()).hexdigest() if f.exists() else None
            if got != h:
                errs.append(f"sha256 mismatch for {rel}: {got}")
    print(json.dumps({"ok": not errs, "errors": errs, "geometries": info}, indent=1))
    return 0 if not errs else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="run every geometry check; exit 0 iff all pass")
    ap.add_argument("--sources", help="directory holding the downloaded 2D_Case_4 files (re-hash them; optional)")
    ap.add_argument("--facts", action="store_true")
    a = ap.parse_args()
    if a.check:
        return check(a.sources)
    if a.facts:
        for n, lay in geometries().items():
            print(n, lay.fingerprint(), [tuple(np.round(np.array(t.polygon.bounds) / MM, 3)) for t in lay.traces])
        return 0
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
