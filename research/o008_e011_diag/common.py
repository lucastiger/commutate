"""Shared loaders for the T0475 diagnosis of E011's development miss on 2D_Case_2R (research/diagnoses/e011-2r-dev-miss.md).

Read-only over committed files: the L1 manifest ``experiments/drafts/E011.dev_jobs.json`` (parameter vectors and purposes of
every solved layout), the burst's L2 results ``research/o008_e011_dev/dev_l2/solves/em_<level>_<fp>.json`` and the dev rows
``research/o008_e011_dev/dev_l2/dev_rows.json``.  Development geometry and development seeds only; no sealed seed, nothing
under data/holdout/.  L1 is recomputed with the frozen ``twin._l1`` on layouts rebuilt from their parameter vectors, and every
rebuild is checked against the manifest's fingerprint.  Units: inductance in H, parameters in mm.
"""
from __future__ import annotations

import json
import sys
from functools import cache
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "experiments" / "runners"), str(ROOT / "src"), str(ROOT / "tools" / "mfos")]

MANIFEST = ROOT / "experiments" / "drafts" / "E011.dev_jobs.json"
L2DIR = ROOT / "research" / "o008_e011_dev" / "dev_l2"
ROWS = L2DIR / "dev_rows.json"
OUT = ROOT / "research" / "o008_e011_diag"
LAYOUT = "2D_Case_2R"
N_DRAWS = 8
MOVABLE = tuple(range(4, 40))  # local.movable_indices(): Params.NAMES[4:40]


def group_of(name: str) -> str:
    """Parameter group of a movable parameter name (columns, slots, die rows, landing lines)."""
    if name.startswith("col_"):
        return "column"
    if name.startswith("slot"):
        return "slot"
    if name.startswith("row_"):
        return "die_row"
    if name.startswith("land_"):
        return "landing"
    return "other"


@cache
def manifest() -> dict:
    return json.loads(MANIFEST.read_text())


@cache
def dev_rows() -> dict:
    return json.loads(ROWS.read_text())


@cache
def params_by_fp(layout: str = LAYOUT) -> dict[str, list[float]]:
    out: dict[str, list[float]] = {}
    for j in manifest()["jobs"]:
        if j["layout"] == layout:
            out[j["fingerprint"]] = j["params"]
    return out


@cache
def purposes(layout: str = LAYOUT) -> dict[str, list[tuple[str, int | None]]]:
    """purpose -> [(fingerprint, rank)], from every job of the layout (one entry per distinct fingerprint)."""
    out: dict[str, list[tuple[str, int | None]]] = {}
    for j in manifest()["jobs"]:
        if j["layout"] != layout:
            continue
        for p in j["purposes"]:
            lst = out.setdefault(p["purpose"], [])
            if (j["fingerprint"], p["rank"]) not in lst:
                lst.append((j["fingerprint"], p["rank"]))
    return out


def l2(fp: str, level: str = "lat0.5") -> float | None:
    """L_H of a burst result (status ok), else None."""
    f = L2DIR / "solves" / f"em_{level}_{fp}.json"
    if not f.exists():
        return None
    r = json.loads(f.read_text())
    return float(r["L_H"]) if r.get("status") == "ok" else None


def one(purpose: str, layout: str = LAYOUT) -> str:
    fps = {fp for fp, _ in purposes(layout)[purpose]}
    if len(fps) != 1:
        raise ValueError(f"{purpose}: {len(fps)} fingerprints")
    return fps.pop()


def shortlist(prefix: str, j: int, layout: str = LAYOUT) -> list[tuple[int, str]]:
    """[(rank, fingerprint)] of a shortlist (search_short / rs_short / alt_short) of draw j, by rank."""
    return sorted((r, fp) for fp, r in purposes(layout)[f"{prefix}_d{j}"])


def roles_of_draw(j: int, layout: str = LAYOUT) -> dict[str, str]:
    """Role -> fingerprint of the layouts scored for draw j (D_j = the seed null's layout)."""
    rows = [r for r in dev_rows()["rows"] if r["layout"] == layout and r["draw"] == j]
    out = {r["role"]: r["fingerprint"] for r in rows}
    out["D"] = out["seed"]
    return out


class L1:
    """Frozen L1 (twin._l1) on layouts rebuilt from manifest parameter vectors; fingerprint-checked; memoised."""

    def __init__(self, layout: str = LAYOUT):
        import e011_run as R

        self.ops = R.RealOps()
        self.lc = self.ops.load(layout)
        self.M = self.ops.M
        self.names = list(self.M.D.Params.NAMES)
        self.memo: dict[bytes, tuple[str | None, float | None]] = {}

    def build(self, vec):
        return self.ops.rebuild(self.lc, np.asarray(vec, float))

    def drc_ok(self, lay) -> bool:
        return self.ops.drc_clean(self.lc, lay)

    def in_domain(self, lay) -> bool:
        return bool(self.ops.in_domain(self.lc, lay, reach=True)[0])

    def __call__(self, vec, fp_expected: str | None = None) -> float:
        key = np.asarray(vec, float).tobytes()
        if key not in self.memo:
            lay = self.build(vec)
            self.memo[key] = (lay.fingerprint(), self.ops.l1(lay))
        fp, v = self.memo[key]
        if fp_expected is not None and fp != fp_expected:
            raise AssertionError(f"rebuild fingerprint {fp} != manifest {fp_expected}")
        return float(v)

    def valid(self, vec) -> tuple[bool, str]:
        """(ok, reason): builds, DRC-clean under spec.rules and in in_domain(reach=True) (the search's move constraint)."""
        try:
            lay = self.build(vec)
        except ValueError as e:
            return False, f"build: {e}"[:120]
        if not self.drc_ok(lay):
            return False, "drc"
        if not self.in_domain(lay):
            return False, "domain"
        return True, "ok"


def diff_params(a, b, names) -> list[dict]:
    """Movable parameters where a and b differ: name, group, a, b, b - a (mm)."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    return [{"name": names[i], "group": group_of(names[i]), "a": float(a[i]), "b": float(b[i]),
             "delta": float(b[i] - a[i])} for i in MOVABLE if abs(b[i] - a[i]) > 1e-9]


def dump(obj, path: Path) -> None:
    def js(o):
        if isinstance(o, (np.floating, np.integer)):
            return o.item()
        if isinstance(o, np.ndarray):
            return o.tolist()
        raise TypeError(type(o))

    path.write_text(json.dumps(obj, indent=1, default=js, sort_keys=False) + "\n")
