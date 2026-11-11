"""O003 / O004 public fallback references (D0010): PowerSynth 2D_Case_2R and 2D_Case_6 re-modelled as ModuleForge Layouts (T0263).

Research script (frozen reconstructions shared with O004), written after the F3 freeze of E008.  Per D0007 the GPL-3.0
sample files are never committed, copied or imported: this file holds only geometry FACTS (numbers) transcribed by hand from
the files listed in SOURCES_SHA256, which were downloaded to a temporary directory outside the repository and hashed there.
Nothing here reads a PowerSynth file (``--check --sources DIR`` only re-hashes them).  Pattern: research/scripts/
o006_case4_layout.py (D0007).  No inductance or thermal solve is run here; ``--write`` runs the fast L1 model only inside
twin() / degrade() (founder session 2026-11-09, TWIN-SPACE CHECK), and mesh-only unknown counts.

Source: e3da/PowerSynth2-pkg, commit a1de7ced949c0fd0105d166767b1de8705eb65ab ("250616 v2.2 stable release", 2025-06-17),
work/Sample_Designs/2D_Case_2R and work/Sample_Designs/2D_Case_6 (GPL-3.0), downloaded 2026-11-10 from
raw.githubusercontent.com.  Coordinates: PowerSynth (x, y, w, h) = lower-left corner and size in mm, absolute in the
baseplate frame (inference, as for 2D_Case_4: every trace lies inside the substrate rectangle of layer_stack.csv at (5, 5)).

FACTS, 2D_Case_2R (README: SiC half-bridge, wire-bonded, single-sided cooling, "Kelvin source connection is not available";
used in Evans et al., IEEE TPEL 34(6) 2019):
  layer_stack.csv   baseplate Cu 55 x 60 x 1.0 at (0, 0); bottom metal Cu 45 x 50 x 0.2 at (5, 5); AlN ("Al_N") 0.835;
                    top Cu (I1) 0.2; device layer C1 0.18
  layout_geometry_script.txt  ("+" starts an island, "-" joins the previous one)
                    T1 power (7,7,40,6): bond points B1 (15,12.5), B2 (23,12.5); power lead L1 (9,8)
                    T2 power (7,15,30,8) - T3 power (37,15,10,32) - T4 power (7,47,40,4): B3 (21,48), B4 (29,48); L2 (41,31);
                      dies D1 (13,16) [B5 signal (15,20), B6 power (15,17)], D2 (22,16) [B7 signal (23,20), B8 power (23,17)]
                    T5 signal (7,25,26,4): B9 (15,26), B10 (23,26); signal lead L3 (9,26)
                    T6 signal (7,31,26,4): B11 (21,33), B12 (29,33); signal lead L4 (9,32)
                    T10 power (7,37,26,8): L5 (9,38); dies D3 (19,38) [B13 power (21,42), B14 signal (21,39)],
                      D4 (27,38) [B15 power (29,42), B16 signal (29,39)]; every bond point 0.25 x 0.25
  bond_wires_setup.txt  power BW3 D1_Source_B6 -> B1, BW4 D2_Source_B8 -> B2, BW5 D3_Source_B13 -> B3,
                    BW6 D4_Source_B15 -> B4; gate BW1 D1_Gate_B5 -> B9, BW2 D2_Gate_B7 -> B10, BW7 D3_Gate_B14 -> B11,
                    BW8 D4_Gate_B16 -> B12; all Wire1, "1 0.1" (one wire each)
  constraint.csv    every min spacing / enclosure 0.5; voltages T10 15000 (highest), T2 7500, T1 0 (DC magnitude column)
  macro_script.txt  inductance Source L5 -> Sink L1; ParaPower thermal, 10 W per device D1..D4
FACTS, 2D_Case_6 (README: SiC half-bridge, wire-bonded, single-sided cooling, "Kelvin source connection is not available";
used in Le et al., IEEE ECCE 2021, pp. 1358-1365):
  layer_stack.csv   baseplate Cu 60 x 40 x 1.0 at (0, 0); bottom metal Cu 50 x 30 x 0.2 at (5, 5); AlN 0.64; top Cu 0.2;
                    device layer C1 0.18
  layout_geometry_script.txt
                    T1 power (7,6,21,11) - T2 power (28,14,6,3) - T3 power (34,14,19,8): L1 (23,8); dies D3 (39,15)
                      [B11 signal (40,16), B12 power (40,19)], D4 (45,15) [B14 signal (46,16), B15 power (46,19)];
                      power bond points B21 (13,15), B22 (19,15)
                    T4 power (7,18,26,8) - T5 power (27,26,6,8): L2 (28,29); dies D1 (12,19) [B1 power (13,20),
                      B2 signal (13,22)], D2 (18,19) [B4 signal (19,22), B5 power (19,20)]
                    T6 power (34,23,19,11): L3 (35,29); B23 (40,24), B24 (46,24)
                    T8 signal (29,6,24,3) (nothing on it); T7 signal (29,10,24,3): L7 (51,11), B17 (40,12.5), B18 (46,12.5)
                    T9 signal (7,27,19,3): B7 (13,27.5), B8 (19,27.5), L6 (8,28); T10 signal (7,31,19,3) (nothing on it)
                    power / die bond points 1 x 1, signal landing points 0.25 x 0.25
  bond_wires_setup.txt  power BW2 D1_Source_B1 -> B21, BW5 D2_Source_B5 -> B22, BW7 D3_Source_B12 -> B23,
                    BW11 D4_Source_B15 -> B24, each "2 0.5" (2 wires, 0.5 mm spacing); gate BW1 D1_Gate_B2 -> B7,
                    BW4 D2_Gate_B4 -> B8, BW8 D3_Gate_B11 -> B17, BW10 D4_Gate_B14 -> B18, each "1 0.1"
  constraint.csv    every min spacing / enclosure 1.0 (no voltage table)
  macro_script.txt  inductance Source L2 -> Sink L3 at "1000 #kHz"; ParaPower thermal, 10 W per device
FACTS common to both: Part_Lib/MOSFET.part CPM2-1200-0025B, footprint 4 x 6, thickness 0.18, source pad (0.335, 0.35, 3.5,
  4.5), gate pad (1.03, 5, 0.5, 0.5) (die-relative); power_lead.part footprint 3 x 3 (post height 2 mm, not modelled);
  signal_lead.part 1 x 1; Wire_Lib/bond_wire_info.wire "JEDEC-4 points", radius 0.15.  Each layout script defines only
  power_lead, signal_lead and MOS parts: no diode die (admissibility, scope_in).

NETS (inference from the connectivity, consistent with a half-bridge and with each macro's measure):
  2D_Case_2R  T10 holds the drains of D3/D4 and L5 (the macro Source, highest voltage) -> DC+, D3/D4 = HS; island
              T2-T3-T4 holds the D1/D2 drains and receives the D3/D4 source wires -> PHASE (lead L2), D1/D2 = LS; T1 receives
              the D1/D2 source wires -> DC- (L1, the macro Sink).  The PHASE island is a C-shaped ring around T5, T6, T10.
              Gate copper: T5 -> GATE_LS (D1/D2 gates), T6 -> GATE_HS (D3/D4 gates).
  2D_Case_6   T4-T5 holds the D1/D2 drains and L2 (macro Source) -> DC+, D1/D2 = HS; T1-T2-T3 holds the D3/D4 drains and
              receives the D1/D2 source wires -> PHASE (L1), D3/D4 = LS; T6 receives the D3/D4 source wires -> DC- (L3, the
              macro Sink).  Gate copper: T9 -> GATE_HS, T7 -> GATE_LS.  T8 and T10 carry nothing (no wire, no lead) and the
              README says there is no Kelvin source: kept as fixed keep-out copper under their own nets SIG_T8, SIG_T10.
  The macro measures (L5 -> L1, L2 -> L3) are both DC+ -> DC-, the ModuleForge commutation-loop port (PHASE open).

MODELLING CHOICES (stated, not facts of the source; M-numbers as in o006_case4_layout.py):
  M1 die orientation.  The layout scripts give no die rotation and the dies must be identical (spec_from_layout).  PowerSynth
     places its gate bond points without regard to the part's gate pad (every one of them lies in the source-pad region), and
     for one switch per case (2D_Case_2R HS D3/D4, 2D_Case_6 LS D3/D4) on the die edge opposite the part's gate pad, i.e.
     as if that switch's dies were turned by 180 degrees.  One uniform orientation is chosen per reference by a geometric
     rule fixed before any rule measurement or L1: the orientation in {0, 180 degrees about the die centre} whose smallest
     plan-view distance between a gate wire and a power wire is larger (larger = bondable at the DRC default 2 wire
     diameters).  Result (``--write`` records both values): 2D_Case_2R 0 degrees (part as drawn), 2D_Case_6 180 degrees
     (source pad (0.165, 1.15, 3.5, 4.5), gate pad (2.47, 0.5, 0.5, 0.5), die-relative).  Footprint, power-wire feet and
     the die short are unchanged by the choice; only gate pads and gate wires move.
  M2 gate wires are SignalWires (not conductors) from the gate-pad centre to the centre of PowerSynth's signal landing point;
     diameter 0.30 mm (Wire1, as in the source); no Kelvin wire (none in either source).
  M3 power-wire feet at the bond-point centres: 2D_Case_2R one wire per die (0.25 mm points, x + 0.125); 2D_Case_6 two wires
     per die 0.5 mm apart, centred on the 1 x 1 mm points (x + 0.5 +- 0.25 across the wire direction, which is y).
  M4 wire shape arc_wire (sine profile), loop height 1.0 mm for power and gate wires (assumption, as Case 4: the JEDEC
     4-point height is not in the files read); Al sigma (stack.SIGMA_AL_WIRE).
  M5 LayerStack requires a solder layer between baseplate and backside Cu; PowerSynth's stack has none: SAC305, 1 um (about
     0.4 % of the AlN layer's thermal resistance; E008 dev applies the same law to Case 4's 1 um placeholder).
  M6 die attach (C1 sits on I1 in the source, no attach): SAC305, 50 um (geometry default DIE_ATTACH_THICKNESS and
     stack.die_attach), so thermal_fem has a non-zero attach layer; die 4H-SiC 0.18 mm (fact = DIE_THICKNESS).  The die top,
     and so the wire start height, is 50 um higher than with a zero attach.
  M7 backside Cu = the full substrate outline (backside_inset = 0), as in layer_stack.csv.
  M8 power leads are not modelled; the port terminals are the 3 x 3 mm lead footprints (centres) on the top Cu.  Signal leads
     (1 x 1) are not modelled.
  M9 conductivities: Cu 385 W/(m K); AlN 170 W/(m K) at 300 K with the AlN law of geometry/stack.py (K_LAWS, docstring:
     sintered substrate AlN typically 170-180); PowerSynth's own material table was not read.
  M10 signal traces are fixed keep-out copper (GATE_*, SIG_T8, SIG_T10); L_term = 7 nH (E008 config.L_term.public_H, S3).

    uv run python research/scripts/o003_powersynth_references.py --check [--sources DIR]   # exit 0 iff every check passes
    uv run python research/scripts/o003_powersynth_references.py --write                   # (re)write research/o003/references
"""
from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np
from shapely.geometry import LineString, Polygon, box
from shapely.ops import unary_union

from moduleforge.geometry import DC_MINUS, DC_PLUS
from moduleforge.geometry.layout import GATE_HS, GATE_LS, PHASE, Die, Layout, SignalWire, Terminal, Trace, arc_wire
from moduleforge.geometry.stack import DIE_ATTACH_THICKNESS, SIGMA_CU, SIGMA_SOLDER, Layer, LayerStack

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "research/o003/references"
POWERSYNTH_REPO = "e3da/PowerSynth2-pkg"
POWERSYNTH_COMMIT = "a1de7ced949c0fd0105d166767b1de8705eb65ab"
FILES_READ = ("README.txt", "layout_geometry_script.txt", "layer_stack.csv", "bond_wires_setup.txt", "constraint.csv",
              "macro_script.txt", "Trace_Ori.txt", "Part_Lib/MOSFET.part", "Part_Lib/power_lead.part",
              "Part_Lib/signal_lead.part", "Wire_Lib/bond_wire_info.wire")
# sha256 of every file read (downloaded at POWERSYNTH_COMMIT on 2026-11-10 to $TMPDIR, outside the repository)
SOURCES_SHA256 = {
    "2D_Case_2R": {
        "README.txt": "af2df9df7fc70c9989a6ffc657d68a24bf063882e65eb79a10164a693d806342",
        "layout_geometry_script.txt": "972984bec3df2564c4d0f9c9cf27b737d3f57093df60ba89d8a87aa81e20eda1",
        "layer_stack.csv": "668b391d5a059d0f0460de32ae29b18d4ff4a197afebbea17220231cb5da4699",
        "bond_wires_setup.txt": "5ae694adc276f02e2c2ca68874603167fbdaf8cb723c1591e45b2cddb49b867a",
        "constraint.csv": "35b842ae590eca0f55fab7792080500a38d7a87b18edde0369e5d26b2f55695e",
        "macro_script.txt": "e9097e120c64425dff2d3f1f28a5e01c2f2254a09279af106514f21dae8418d5",
        "Trace_Ori.txt": "b75cfc2681d215fdedbe8cd410a98d21cb0145c0b5a93400e05c5c9dacb971b4",
        "Part_Lib/MOSFET.part": "ae226bc07c737c25a13f28212b2c711633a375df408e6d6114d4fc8c26ec1533",
        "Part_Lib/power_lead.part": "416ec39693c0535f2424da7ffc61cc8b3c40a479d0ba81d0a1a307164caf53ee",
        "Part_Lib/signal_lead.part": "aee35aed62b5917ae066b05cf1c1142014d3451f178cd037068d63a1fef2e232",
        "Wire_Lib/bond_wire_info.wire": "b03a77ca662fa66d28f0e8074e9ca6d2fdaf588c5ba13af369e56269100e3ed1",
    },
    "2D_Case_6": {
        "README.txt": "01b492c503e655a69ee83c102c668948f346d881877ecab9250c5dba4e74fc81",
        "layout_geometry_script.txt": "33abe28bd959fb960e70fd4a372e3d31e94fcdef4b3f0a65bd5c974919bfd7fb",
        "layer_stack.csv": "e646fffc576047e525b3b2b6ceac048d07d569924c0b0dc0132831e5b883f45d",
        "bond_wires_setup.txt": "d75f633a7cdbef609212b63e8e6d1d0c4a9a494c728d46a4a5c708056407be6e",
        "constraint.csv": "7d9c18bb462864e1d0c42ed61bb9da446c8fa9763315a1d42f3d519653bfee86",
        "macro_script.txt": "241831d6352a6b41dafefa3ec73c39959345de7bc7a1108463f6289c1aabcc63",
        "Trace_Ori.txt": "f9647668330aa18bd0df2e5f6672730cd8cc13bfa7f96fe23ada7ae094960bdd",
        "Part_Lib/MOSFET.part": "ae226bc07c737c25a13f28212b2c711633a375df408e6d6114d4fc8c26ec1533",
        "Part_Lib/power_lead.part": "416ec39693c0535f2424da7ffc61cc8b3c40a479d0ba81d0a1a307164caf53ee",
        "Part_Lib/signal_lead.part": "aee35aed62b5917ae066b05cf1c1142014d3451f178cd037068d63a1fef2e232",
        "Wire_Lib/bond_wire_info.wire": "b03a77ca662fa66d28f0e8074e9ca6d2fdaf588c5ba13af369e56269100e3ed1",
    },
}
# file names that must never appear inside research/ (README.txt is too generic to test)
FORBIDDEN_NAMES = ({Path(f).name for f in FILES_READ} | {"initial_layout_I1.png", "output.log"}) - {"README.txt"}

MM = 1e-3
L_TERM_H = 7e-9  # E008 config.L_term.public_H (Z. Chen, PhD diss., Virginia Tech 2013; research/notes/o003-public-benchmarks.md)
GRIDS_MM = (0.5, 0.25, 0.125)
# --- facts common to both (mm)
T_BASE, T_BACK, T_TOP, T_DIE = 1.0, 0.2, 0.2, 0.18
DIE_FOOT = (4.0, 6.0)
PART_PADS = {"source": (0.335, 0.35, 3.5, 4.5), "gate": (1.03, 5.0, 0.5, 0.5)}  # MOSFET.part, die-relative (x, y, w, h)
LEAD_FOOT = 3.0
WIRE_DIAMETER = 0.30  # Wire_Lib radius 0.15
LOOP_HEIGHT = 1.0  # M4
SOLDER_T = 1e-3  # mm (M5)

# --- per-reference facts (mm).  power wires: (die, foot pad (x, y, size), landing pad (x, y, size), landing net, n, spacing)
REFS = {
    "2D_Case_2R": dict(
        baseplate=(0.0, 0.0, 55.0, 60.0), substrate=(5.0, 5.0, 45.0, 50.0), t_cer=0.835,
        islands={DC_MINUS: [(7, 7, 40, 6)], PHASE: [(7, 15, 30, 8), (37, 15, 10, 32), (7, 47, 40, 4)],
                 DC_PLUS: [(7, 37, 26, 8)]},
        signal={GATE_LS: (7, 25, 26, 4), GATE_HS: (7, 31, 26, 4)},
        dies={"D1": ((13, 16), "LS"), "D2": ((22, 16), "LS"), "D3": ((19, 38), "HS"), "D4": ((27, 38), "HS")},
        leads={DC_MINUS: (9, 8), PHASE: (41, 31), DC_PLUS: (9, 38)},
        power_wires=[("D1", (15, 17, 0.25), (15, 12.5, 0.25), DC_MINUS, 1, 0.1),
                     ("D2", (23, 17, 0.25), (23, 12.5, 0.25), DC_MINUS, 1, 0.1),
                     ("D3", (21, 42, 0.25), (21, 48, 0.25), PHASE, 1, 0.1),
                     ("D4", (29, 42, 0.25), (29, 48, 0.25), PHASE, 1, 0.1)],
        # gate wires: die, PowerSynth's own gate bond point (recorded, not used: M1/M2), landing point
        gate_wires=[("D1", (15, 20, 0.25), (15, 26, 0.25)), ("D2", (23, 20, 0.25), (23, 26, 0.25)),
                    ("D3", (21, 39, 0.25), (21, 33, 0.25)), ("D4", (29, 39, 0.25), (29, 33, 0.25))],
        exp_area={DC_MINUS: 240.0, PHASE: 240.0 + 320.0 + 160.0, DC_PLUS: 208.0},
        constraint_min_spacing=0.5),
    "2D_Case_6": dict(
        baseplate=(0.0, 0.0, 60.0, 40.0), substrate=(5.0, 5.0, 50.0, 30.0), t_cer=0.64,
        islands={PHASE: [(7, 6, 21, 11), (28, 14, 6, 3), (34, 14, 19, 8)], DC_PLUS: [(7, 18, 26, 8), (27, 26, 6, 8)],
                 DC_MINUS: [(34, 23, 19, 11)]},
        signal={"SIG_T8": (29, 6, 24, 3), GATE_LS: (29, 10, 24, 3), GATE_HS: (7, 27, 19, 3), "SIG_T10": (7, 31, 19, 3)},
        dies={"D1": ((12, 19), "HS"), "D2": ((18, 19), "HS"), "D3": ((39, 15), "LS"), "D4": ((45, 15), "LS")},
        leads={PHASE: (23, 8), DC_PLUS: (28, 29), DC_MINUS: (35, 29)},
        power_wires=[("D1", (13, 20, 1.0), (13, 15, 1.0), PHASE, 2, 0.5),
                     ("D2", (19, 20, 1.0), (19, 15, 1.0), PHASE, 2, 0.5),
                     ("D3", (40, 19, 1.0), (40, 24, 1.0), DC_MINUS, 2, 0.5),
                     ("D4", (46, 19, 1.0), (46, 24, 1.0), DC_MINUS, 2, 0.5)],
        gate_wires=[("D1", (13, 22, 1.0), (13, 27.5, 0.25)), ("D2", (19, 22, 1.0), (19, 27.5, 0.25)),
                    ("D3", (40, 16, 1.0), (40, 12.5, 0.25)), ("D4", (46, 16, 1.0), (46, 12.5, 0.25))],
        exp_area={PHASE: 231.0 + 18.0 + 152.0, DC_PLUS: 208.0 + 48.0, DC_MINUS: 209.0},
        constraint_min_spacing=1.0),
}
KEEPOUT_NETS = {"2D_Case_2R": [GATE_LS, GATE_HS], "2D_Case_6": ["SIG_T8", GATE_LS, GATE_HS, "SIG_T10"]}
SIG_LANDING_NET = {"HS": GATE_HS, "LS": GATE_LS}


def _stack(ref: str) -> LayerStack:
    f = REFS[ref]
    return LayerStack((
        Layer("baseplate", "Cu", T_BASE * MM, SIGMA_CU, 385.0),
        Layer("solder", "SAC305", SOLDER_T * MM, SIGMA_SOLDER, 58.0),  # M5
        Layer("backside_cu", "Cu", T_BACK * MM, SIGMA_CU, 385.0),
        Layer("ceramic", "AlN", f["t_cer"] * MM, 0.0, 170.0),  # M9
        Layer("top_cu", "Cu", T_TOP * MM, SIGMA_CU, 385.0),
    ), kind=f"PowerSynth_{ref}")


def _rect(x, y, w, h):
    return box(x * MM, y * MM, (x + w) * MM, (y + h) * MM)


def _pads(rot: int) -> dict:
    """Die-relative pad rectangles (x0, y0, x1, y1) in mm for orientation ``rot`` (0 or 180 degrees about the centre)."""
    W, H = DIE_FOOT
    out = {}
    for k, (x, y, w, h) in PART_PADS.items():
        out[k] = (x, y, x + w, y + h) if rot == 0 else (W - x - w, H - y - h, W - x, H - y)
    return out


def _wire_feet(pw) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    """(start, end) plan points in mm of the wires of one bond-wire entry (M3): n wires ``spacing`` apart, centred on the
    bond points, offset across the wire direction."""
    _, (ax, ay, sa), (bx, by, sb), _, n, sp = pw
    a = np.array([ax + sa / 2, ay + sa / 2])
    b = np.array([bx + sb / 2, by + sb / 2])
    d = (b - a) / np.linalg.norm(b - a)
    perp = np.array([d[1], -d[0]]) if abs(d[0]) > 1e-12 else np.array([1.0, 0.0])
    offs = [0.0] if n == 1 else [sp * (i - (n - 1) / 2) for i in range(n)]
    return [(tuple(a + o * perp), tuple(b + o * perp)) for o in offs]


def orientation_score(ref: str, rot: int) -> float:
    """M1 rule: smallest plan-view distance (mm) between any gate wire and any power wire under orientation ``rot``."""
    f = REFS[ref]
    pads = _pads(rot)
    gx0, gy0, gx1, gy1 = pads["gate"]
    pl = [LineString(s_e) for pw in f["power_wires"] for s_e in _wire_feet(pw)]
    best = math.inf
    for dname, _, (lx, ly, ls) in f["gate_wires"]:
        (x, y), _sw = f["dies"][dname]
        g = LineString([(x + (gx0 + gx1) / 2, y + (gy0 + gy1) / 2), (lx + ls / 2, ly + ls / 2)])
        best = min(best, min(g.distance(p) for p in pl))
    return best


def orientation(ref: str) -> int:
    s0, s180 = orientation_score(ref, 0), orientation_score(ref, 180)
    return 0 if s0 >= s180 else 180


def build(ref: str) -> Layout:
    """The reconstruction of ``ref`` (unsnapped; every coordinate of the source is on the 0.5 mm grid)."""
    f = REFS[ref]
    stack = _stack(ref)
    rot = orientation(ref)
    traces = []
    for net, rects in f["islands"].items():
        poly = unary_union([_rect(*r) for r in rects])
        if not isinstance(poly, Polygon):
            raise ValueError(f"{ref}: {net} island is not one polygon")
        traces.append(Trace(net, poly))
    for net, r in f["signal"].items():
        traces.append(Trace(net, _rect(*r)))
    dies, idx = [], {}
    rel = _pads(rot)
    for name, ((x, y), sw) in f["dies"].items():
        w, h = DIE_FOOT
        pads = {k: tuple(v * MM for v in (x + r[0], y + r[1], x + r[2], y + r[3])) for k, r in rel.items()}
        idx[name] = len(dies)
        dies.append(Die((x + w / 2) * MM, (y + h / 2) * MM, w * MM, h * MM, sw, pads, thickness=T_DIE * MM,
                        attach_thickness=DIE_ATTACH_THICKNESS))  # M6
    z_top = stack.z_top("top_cu")
    wires = []
    for pw in f["power_wires"]:
        d = dies[idx[pw[0]]]
        for a, b in _wire_feet(pw):
            wires.append(arc_wire((a[0] * MM, a[1] * MM), (b[0] * MM, b[1] * MM), z_top + d.attach_thickness + d.thickness,
                                  z_top, LOOP_HEIGHT * MM, WIRE_DIAMETER * MM, pw[3]))
    sws = []
    for dname, _ps_point, (lx, ly, ls) in f["gate_wires"]:
        k = idx[dname]
        d = dies[k]
        x0, y0, x1, y1 = d.pads["gate"]
        bw = arc_wire(((x0 + x1) / 2, (y0 + y1) / 2), ((lx + ls / 2) * MM, (ly + ls / 2) * MM),
                      z_top + d.attach_thickness + d.thickness, z_top, LOOP_HEIGHT * MM, WIRE_DIAMETER * MM, "")
        sws.append(SignalWire(k, "gate", SIG_LANDING_NET[d.switch], bw.points, WIRE_DIAMETER * MM, LOOP_HEIGHT * MM))
    terminals = {net: Terminal(net, (x + LEAD_FOOT / 2) * MM, (y + LEAD_FOOT / 2) * MM, LEAD_FOOT * MM, LEAD_FOOT * MM)
                 for net, (x, y) in f["leads"].items()}
    return Layout(family=f"powersynth_{ref}", dies_per_switch=2, outline=_rect(*f["substrate"]), traces=traces, dies=dies,
                  wires=wires, terminals=terminals, baseplate_outline=_rect(*f["baseplate"]), stack=stack,
                  backside_inset=0.0, signal_wires=sws)


def snapped(ref: str) -> tuple[Layout, dict]:
    """(reconstruction = the layout snapped to 0.5 mm, {grid_mm: SnapResult}) for the three scope_in grids."""
    from moduleforge.geometry.snap import snap_layout
    lay = build(ref)
    res = {g: snap_layout(lay, g * MM) for g in GRIDS_MM}
    if res[0.5].records:
        return res[0.5].layout, res
    # already on the 0.5 mm grid (no snap record, s_ref = 0): the snapped layout equals the input up to float noise below
    # snap.RECORD_TOL (snap_layout re-derives die w / h from the snapped edges, 1-ulp differences that would fail
    # spec_from_layout's exact die-identity test), so the reconstruction is the built layout; same fingerprint (checked)
    if res[0.5].layout.fingerprint() != lay.fingerprint():
        raise ValueError(f"{ref}: no snap record but the snapped fingerprint differs")
    return lay, res


def spec_of(lay: Layout):
    """The per-reference spec as E008 builds it: spec_from_layout with the measured rules of the snapped reconstruction."""
    from moduleforge.drc.rules import measure_rules
    from moduleforge.generate import derivative as D
    rules, rec = measure_rules(lay)
    ref = lay.family.removeprefix("powersynth_")
    return D.spec_from_layout(lay, rules, KEEPOUT_NETS[ref]), rules, rec


def l2_unknowns(lay: Layout, refinement: int = 1, fmax: float = 20e6) -> dict:
    """Unknown count of an l2_layout system at CELL[refinement] (mesh and filaments only: no coupling, no solve).  Mirrors
    l2_layout.build_layout_system up to the Grid and the wire filaments (LayoutSystem.n = nfil + n_g)."""
    from moduleforge.solvers import l2_layout as L2
    cm = lay.to_conductors()
    planes = {p.name: p for p in cm.planes}
    xmin, ymin, ax, ay, nx, ny = L2.layout_lattice(cm, refinement)
    fill = L2.cell_fill(cm, xmin, ymin, ax, ay, nx, ny)
    top_frac, top_lab, _nets = fill["top"]
    z0t, z1t = lay.top_cu_z()
    s = cm.stack.layer("top_cu").sigma
    slabs = [L2.SlabSpec("top_cu", top_frac > 0, L2.graded_layers(z0t, z1t, L2.LAYERS_TOP[refinement], fmax, s, True), s,
                         top_lab)]
    for name, nl, two in (("backside_cu", L2.LAYERS_BACK[refinement], True), ("baseplate", L2.LAYERS_BASE[refinement], False)):
        p = planes[name]
        slabs.append(L2.SlabSpec(name, fill[name] > 0, L2.graded_layers(p.z_bottom, p.z_bottom + p.thickness, nl, fmax,
                                                                         p.sigma, two), p.sigma))
    grid = L2.Grid(xmin, ymin, ax, ay, nx, ny, slabs)
    by_w: dict[int, list] = {}
    for sgm in cm.wires:
        by_w.setdefault(sgm.wire_index, []).append(sgm)
    wins = [L2.WireIn(f"w{i}", np.array([sg[0].p0] + [q.p1 for q in sg], float), sg[0].diameter, sg[0].sigma)
            for i, sg in sorted(by_w.items())]
    fs = L2.build_filaments(wins, refinement, z_floor=z1t + L2.LANDING_GAP * max(w.diameter for w in wins))
    return {"cell_mm": ax / MM, "nx": nx, "ny": ny, "n_grid": int(grid.n_g), "n_filaments": int(fs.nfil),
            "n_unknowns": int(grid.n_g + fs.nfil)}


def _on_lattice(lay: Layout, cell: float) -> float:
    """Max relative represented-area error on the l2_layout lattice of ``cell`` (m); ValueError if not on the lattice."""
    from moduleforge.solvers import l2_layout as L2
    cm = lay.to_conductors()
    saved = L2.CELL
    try:
        L2.CELL = (cell,) + tuple(saved[1:])
        lat = L2.layout_lattice(cm, 0)
        fill = L2.cell_fill(cm, *lat)
        for d in cm.shorts:
            L2.check_on_lattice(d.x - d.w / 2, d.x + d.w / 2, d.y - d.h / 2, d.y + d.h / 2, *lat[:4], f"die {d.die_index}")
    finally:
        L2.CELL = saved
    return max(abs(rep - ex) / ex for rep, ex in fill["area"].values())


def _thermal_level0(lay: Layout) -> dict:
    """thermal_fem.layout_grid at level 0 under E008's frozen rule (grid only, no solve)."""
    from moduleforge.solvers import thermal_fem as F
    fr = json.loads((ROOT / "research/o007_dev3/frozen_config.json").read_text())
    eg = fr["edge_grading"]
    rule = F.GridRule(h0=float(fr["h0_m"]), nz={}, default_nz=int(fr["nz_min"]), zrefine=bool(fr["zrefine"]),
                      near_margin=float(fr["near_margin_m"]), min_cells=int(fr["min_cells"]),
                      element_order=int(fr["element_order"]), dz_max=float(fr["dz_max_m"]),
                      edge_grading=(float(eg["first_offset_m"]), float(eg["ratio"]), float(eg["max_offset_m"]),
                                    float(eg["min_gap_fraction"])), amg_gs_sweeps=int(fr["amg_gs_sweeps"]))
    F.layout_grid(lay, 10.0, 5000.0, 300.0, rule=rule, level=0)
    return {"accepted": True, "estimate_dofs_level0": int(F.estimate_dofs(lay, rule, 0))}


def _rec(r) -> dict:
    return {"element": r.element, "kind": r.kind, "before_mm": [round(v / MM, 6) for v in np.ravel(r.before)],
            "after_mm": [round(v / MM, 6) for v in np.ravel(r.after)], "displacement_mm": round(r.displacement / MM, 6)}


def _jsonable(o):
    if isinstance(o, dict):
        return {str(k): _jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_jsonable(v) for v in o]
    if isinstance(o, (np.floating, float)):
        return None if not math.isfinite(float(o)) else float(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (str, int, bool)) or o is None:
        return o
    return repr(o)


def twin_report(lay: Layout, spec) -> dict:
    """TWIN-SPACE CHECK (founder session 2026-11-09, review T0299): E008's own prepare() with no _quick_ok draws (n_quick=0,
    so no generator sample is drawn), i.e. twin(), the midpoint record, the twin-copper symmetric difference and degrade(),
    with L1 (the fast model) only; no l2_layout or thermal solve."""
    import importlib.util
    sp = importlib.util.spec_from_file_location("e008_run_t0263", ROOT / "experiments/runners/e008_run.py")
    E = importlib.util.module_from_spec(sp)
    sys.modules[sp.name] = E
    sp.loader.exec_module(E)
    from moduleforge.drc.rules import measure_rules
    rc = E.RefCtx(lay.family, "public", spec, lay, info={"measured_rules": measure_rules(lay)[1]})
    rc.stack_type = E._stack_type(spec.stack, [*lay.dies, spec.die])
    rc = E.prepare(rc, {}, 0, 0, with_l1=True)
    out = {"stack_type": rc.stack_type, "fail_fast": rc.info.get("fail_fast"), "twin_s": rc.info.get("twin_s"),
           "degrade_s": rc.info.get("degrade_s"), "midpoint_decided_splits": rc.info.get("midpoint_decided_splits"),
           "twin_copper": rc.info.get("twin_copper"), "walk": rc.info.get("walk"),
           "rule_strictness": rc.info.get("rule_strictness")}
    if rc.twin is not None:
        tr = rc.twin_rec
        out["twin_mode"] = tr.get("mode")
        out["twin_record"] = tr
        out["twin_fingerprint"] = rc.twin.fingerprint()
        l1w, l1r = tr.get("L1_twin_H") or tr.get("l1_twin"), tr.get("L1_reference_H") or tr.get("l1_reference")
        out["L1_W_over_ref"] = (l1w / l1r) if (l1w and l1r) else tr.get("L1_ratio")
    if rc.D is not None or rc.d_rec:
        out["degrade_record"] = rc.d_rec
        if rc.D is not None:
            out["D_fingerprint"] = rc.D.fingerprint()
    return _jsonable(out)


def reference_record(ref: str, with_twin: bool = True) -> dict:
    from moduleforge.drc.rules import check
    lay0 = build(ref)
    lay, res = snapped(ref)
    spec, rules, rec = spec_of(lay)
    f = REFS[ref]
    tr = {t.net: t.polygon for t in lay.traces}
    out = {
        "reference": ref, "kind": "public", "label": "public benchmarks, low power, indicative",
        "source": {"repo": POWERSYNTH_REPO, "commit": POWERSYNTH_COMMIT, "dir": f"work/Sample_Designs/{ref}",
                   "license": "GPL-3.0 (facts only, D0007)", "sha256": SOURCES_SHA256[ref]},
        "admissibility": {"admissible": True, "diode_dies": 0, "dies": {k: s for k, (_, s) in f["dies"].items()},
                          "reason": "public reference; only MOS dies (layout script defines power_lead, signal_lead, MOS)"},
        "L_term_H": L_TERM_H,
        "orientation_deg": orientation(ref),
        "orientation_scores_mm": {"0": orientation_score(ref, 0), "180": orientation_score(ref, 180)},
        "fingerprint_unsnapped": lay0.fingerprint(),
        "reconstruction_hash": lay.fingerprint(),
        "on_grid_0p5": len(res[0.5].records) == 0,
        "s_ref_zero": len(res[0.5].records) == 0,
        "snap": {f"{g}mm": {"fingerprint": r.layout.fingerprint(), "n_records": len(r.records),
                            "records": [_rec(x) for x in r.records],
                            "violations_default_rules": [{"rule": v.rule, "message": v.message, "origin": v.origin}
                                                         for v in r.violations]} for g, r in res.items()},
        "measured_rules": _jsonable(dataclasses.asdict(rules)),
        "measured_rules_record": _jsonable(rec),
        "drc_own_rules": [f"{v.rule}: {v.message}" for v in check(lay, rules)],
        "keepout_nets": KEEPOUT_NETS[ref],
        "spec": {"wires_per_die": spec.wires_per_die, "dies_per_switch": spec.dies_per_switch,
                 "wire_diameter_mm": spec.wire_diameter / MM, "loop_height_mm": spec.loop_height / MM,
                 "signal_wire_diameter_mm": spec.signal_wire_diameter / MM, "die_pads_rel_centre_mm":
                 {k: [round(v / MM, 6) for v in r] for k, r in spec.die.pads.items()},
                 "die_thickness_mm": spec.die.thickness / MM, "attach_thickness_mm": spec.die.attach_thickness / MM,
                 "keepouts": [t.net for t in spec.keepouts], "terminals": sorted(spec.terminals)},
        "copper_mm2": {n: round(p.area / MM**2, 6) for n, p in tr.items()},
        "wire_lengths_mm": [round(w.length / MM, 4) for w in lay.wires],
        "signal_wire_lengths_mm": [round(w.length / MM, 4) for w in lay.signal_wires],
        "stack": [{"name": la.name, "material": la.material, "thickness_mm": la.thickness / MM, "k": la.k}
                  for la in lay.stack.layers],
        "l2_unknowns_0p25mm": l2_unknowns(lay, 1),
        "lattice_area_rel_err": {f"{c}mm": _on_lattice(lay, c * MM) for c in (0.5, 0.25)},
        "thermal_level0": _thermal_level0(lay),
    }
    if with_twin:
        out["twin_space_check"] = twin_report(lay, spec)
    return out


# ------------------------------------------------------------------------------------------------------------- checks
def check(sources: str | None = None) -> int:
    from moduleforge.drc.rules import check as drc
    from moduleforge.drc.rules import measure_rules
    errs: list[str] = []
    info = {}
    for ref, f in REFS.items():
        try:
            lay, res = snapped(ref)
            rules, _ = measure_rules(lay)
            v = drc(lay, rules)
            if v:
                errs.append(f"{ref}: not DRC-clean under its own measured rules: {[x.rule + ' ' + x.message for x in v]}")
            spec_of(lay)  # spec_from_layout must accept it
            for c in (0.5, 0.25):
                try:
                    e = _on_lattice(lay, c * MM)
                    if e > 1e-12:
                        errs.append(f"{ref}: represented area off by {e:.2e} at {c} mm")
                except ValueError as ex:
                    errs.append(f"{ref}: not on the {c} mm l2_layout lattice: {ex}")
            try:
                _thermal_level0(lay)
            except Exception as ex:  # noqa: BLE001 - any refusal of the grid is a failed check
                errs.append(f"{ref}: thermal_fem.layout_grid level 0 refused: {type(ex).__name__}: {ex}")
            tr = {t.net: t.polygon for t in lay.traces}
            for n, a in f["exp_area"].items():
                if abs(tr[n].area / MM**2 - a) > 1e-6:
                    errs.append(f"{ref}: {n} area {tr[n].area / MM**2} != transcribed {a}")
            if any(d.attach_thickness <= 0 for d in lay.dies):
                errs.append(f"{ref}: zero die attach")
            if len([d for d in lay.dies if d.switch == "HS"]) != 2 or len([d for d in lay.dies if d.switch == "LS"]) != 2:
                errs.append(f"{ref}: expected 2 HS and 2 LS MOS dies, no diode")
            if lay.stack.layer("ceramic").material != "AlN":
                errs.append(f"{ref}: ceramic is not AlN")
            sha = SOURCES_SHA256[ref]
            if set(sha) != set(FILES_READ) or not all(len(h) == 64 and int(h, 16) >= 0 for h in sha.values()):
                errs.append(f"{ref}: sha256 list incomplete: {sorted(set(FILES_READ) ^ set(sha))}")
            if sources:
                for rel, h in sha.items():
                    p = Path(sources) / ref / rel
                    got = hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None
                    if got != h:
                        errs.append(f"{ref}: sha256 mismatch for {rel}: {got}")
            jf = OUT_DIR / f"{ref}.json"
            if not jf.exists():
                errs.append(f"{ref}: {jf.relative_to(ROOT)} missing (run --write)")
            else:
                j = json.loads(jf.read_text())
                if j.get("reconstruction_hash") != lay.fingerprint():
                    errs.append(f"{ref}: recorded reconstruction_hash differs from the rebuilt layout")
            info[ref] = {"reconstruction_hash": lay.fingerprint(), "snap_records": {g: len(r.records) for g, r in res.items()},
                         "drc_own_rules": len(v)}
        except Exception as ex:  # noqa: BLE001
            errs.append(f"{ref}: {type(ex).__name__}: {ex}")
    for p in (ROOT / "research").rglob("*"):
        if p.is_file() and p.name in FORBIDDEN_NAMES:
            errs.append(f"PowerSynth file name found in the repository: {p.relative_to(ROOT)}")
    print(json.dumps({"ok": not errs, "errors": errs, "references": info}, indent=1))
    return 0 if not errs else 1


def write(with_twin: bool = True) -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for ref in REFS:
        r = reference_record(ref, with_twin)
        (OUT_DIR / f"{ref}.json").write_text(json.dumps(r, indent=1, sort_keys=False) + "\n")
        print(ref, r["reconstruction_hash"], "twin:", (r.get("twin_space_check") or {}).get("twin_mode"),
              (r.get("twin_space_check") or {}).get("fail_fast"))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="run every check; exit 0 iff all pass")
    ap.add_argument("--sources", help="directory holding the downloaded <ref>/ files (re-hash them; optional)")
    ap.add_argument("--write", action="store_true", help="write research/o003/references/<ref>.json (L1 inside twin only)")
    ap.add_argument("--no-twin", action="store_true", help="with --write: skip the twin-space check")
    a = ap.parse_args()
    if a.write:
        return write(not a.no_twin)
    if a.check:
        return check(a.sources)
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
