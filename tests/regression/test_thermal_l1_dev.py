"""L1 thermal model against n1's cached level-1 reference values on the development layouts (T0392 design study).

Layouts: the two C004 development layouts (E009 dev seed 20261101) plus, per stratum, the first 5 DRC-valid layouts of
development seed 20261115 with the same die size (as research/o002_l1/design_study.py builds them); reference values
(``thermal_fem.solve_layout``, level 1, frozen E009 rule) are the cached per-solve summaries copied to
tests/regression/data/o002_l1_dev/.  Statistics are the study's point estimates (numpy linear p95):

* A1-type: p95 over same-stratum layout pairs of |model - reference| of the difference of the two layouts' reference-
  hottest die average;
* A2-type: p95 over dies of |model - reference| / (reference - T_bp), T_bp = T_c + P_tot / (h A_bottom).

Tolerances are 0.6 x the A1 (0.5 K) and A2 (0.03) thresholds, F3's power design point, fixed by T0395: never widen.

The frozen calibration table ``moduleforge.thermal.CALIBRATION`` is re-derived here from the cached level-1 references of its
development calibration layouts (tests/regression/data/o002_l1_cal/ and, for 5.0 mm, o002_l1_dev/), as
benchmarks/thermal_l1_calibration.py derives it.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
import yaml

from moduleforge.generate.halfbridge import generate_layouts
from moduleforge.thermal import CALIBRATION, evaluate

ROOT = Path(__file__).resolve().parents[2]
DATA = Path(__file__).parent / "data" / "o002_l1_dev"
CAL = Path(__file__).parent / "data" / "o002_l1_cal"
E009 = ROOT / "experiments" / "specs" / "E009.yaml"
DEV_SEED, NEW_SEED, N_NEW, N_DRAW = 20261101, 20261115, 5, 40
H, TC = 5000.0, 338.15
A1_TOL_K, A2_TOL = 0.3, 0.018
LOADS = {"P_ref": 1.0, "half_P_ref": 0.5}


def _size(lay):
    return round(lay.dies[0].w * 1e3, 6)


def _rows():
    spec = yaml.safe_load(E009.read_text())["config"]
    p_ref = spec["dev_regression_guard"]["calibrated_power_W_per_die"]
    rows = []
    for name, fam, k in spec["dev_layouts"]:
        dev = generate_layouts(1, DEV_SEED, family=fam, dies_per_switch=k)[0]
        assert dev.fingerprint() == spec["dev_fingerprints"][name]
        lays, seen = [(name, dev)], {dev.fingerprint()}
        for lay in generate_layouts(N_DRAW, NEW_SEED, family=fam, dies_per_switch=k):
            if len(lays) > N_NEW:
                break
            if _size(lay) == _size(dev) and lay.fingerprint() not in seen:
                seen.add(lay.fingerprint())
                lays.append((f"{fam}_{k}_n{len(lays) - 1}", lay))
        assert len(lays) == N_NEW + 1
        for nm, lay in lays:
            ref = {}
            for ld in LOADS:
                d = json.loads((DATA / f"{lay.fingerprint()[:16]}__L1__{ld}.json").read_text())
                assert d["fingerprint"] == lay.fingerprint()
                assert abs(d["power_W_per_die"] - LOADS[ld] * p_ref[name]) < 1e-9
                ref[ld] = np.array(d["tj_mean_K"])
            rows.append({"name": nm, "layout": lay, "stratum": f"{fam}/{k}", "P": {ld: f * p_ref[name] for ld, f in LOADS.items()},
                         "ref": ref, "groups": _groups(lay), "dies": k})
    return rows


def _groups(lay):
    g = {}
    for i, d in enumerate(lay.dies):
        g.setdefault(d.switch, []).append(i)
    return {k: np.array(v) for k, v in g.items()}


def _p95(v):
    return float(np.percentile(np.asarray(v, float), 95))


@pytest.fixture(scope="module")
def evaluated():
    rows = _rows()
    for r in rows:
        r["pred"], r["tbp"] = {}, {}
        for ld, p in r["P"].items():
            o = evaluate(r["layout"], p, h=H, T_c=TC)
            r["pred"][ld], r["tbp"][ld] = o.tj_mean, o.T_bp
    return rows


def _a1(rows, ld):
    out = []
    for s in sorted({r["stratum"] for r in rows}):
        rs = [r for r in rows if r["stratum"] == s]
        for i in range(len(rs)):
            for j in range(i + 1, len(rs)):
                a, b = rs[i], rs[j]
                ha, hb = int(np.argmax(a["ref"][ld])), int(np.argmax(b["ref"][ld]))
                out.append(abs((a["pred"][ld][ha] - b["pred"][ld][hb]) - (a["ref"][ld][ha] - b["ref"][ld][hb])))
    return out


def _a2(rows, ld):
    return [e for r in rows for e in np.abs(r["pred"][ld] - r["ref"][ld]) / (r["ref"][ld] - r["tbp"][ld])]


def _spread_err(r, ld):
    return [abs(np.ptp(r["pred"][ld][g]) - np.ptp(r["ref"][ld][g])) for g in r["groups"].values()]


@pytest.mark.parametrize("ld", list(LOADS))
def test_a1_type_p95(evaluated, ld):
    assert _p95(_a1(evaluated, ld)) <= A1_TOL_K


@pytest.mark.parametrize("ld", list(LOADS))
def test_a2_type_p95(evaluated, ld):
    assert _p95(_a2(evaluated, ld)) <= A2_TOL


def test_a4_type_reported_not_gated(evaluated, capsys):
    """A4-type per die-count band at P_ref (spread error p95 over the stratum-mean-spread null's, leave-one-layout-out).
    Reported only (the packet gates A1, A2 and A5); sanity-bounded so a broken model cannot pass silently."""
    ld = "P_ref"
    for s in sorted({r["stratum"] for r in evaluated}):
        rs = [r for r in evaluated if r["stratum"] == s]
        num, den = [], []
        for r in rs:
            num += _spread_err(r, ld)
            for w, g in r["groups"].items():
                null = np.mean([np.ptp(o["ref"][ld][o["groups"][w]]) for o in rs if o is not r])
                den.append(abs(null - np.ptp(r["ref"][ld][g])))
        ratio = _p95(num) / _p95(den)
        print(f"A4-type {s}: model spread err p95 {_p95(num):.3f} K, null {_p95(den):.3f} K, ratio {ratio:.2f}")
        assert ratio < 1.0  # K3-type sanity: better than the stratum-mean null


def test_calibration_table_rederived_from_cached_references(capsys):
    """c(s) = mean over C004's two development strata (side_by_side/6, u_shaped/2; dev seed 20261101 with the die size
    fixed to s) of the mean over dies of (level-1 reference rise) / (raw coarse-FV rise) at the layout's P_ref (C004's
    rule: hottest die 60 +/- 0.25 K above the coolant at level 0), rise above T_bp = T_c + P_tot / (h A_bottom).
    The table stores 5 decimals, so the tolerance is 5e-6 (the solver's 1e-9 K run-to-run difference is negligible).

    Family agreement is printed.  The design note's refutation line (about 0.005 between families at one size) holds for
    n1's 4 mm rule (max 0.0032) but not for the adopted 1.5 mm rule at 4.0 mm (0.0059; docs/thermal_l1.md, reported to
    the founder).  The assertion below is only a gross-error guard, set after the data were seen: 0.01, i.e. a family
    deviation from the table of at most 0.5 % of the die-local rise, a sixth of A2's 3 % budget."""
    spec = yaml.safe_load(E009.read_text())["config"]
    p_e009 = spec["dev_regression_guard"]["calibrated_power_W_per_die"]
    assert set(CALIBRATION) == {4.0, 4.5, 5.0, 5.5}
    for s, c_table in CALIBRATION.items():
        per = []
        for name, fam, k in spec["dev_layouts"]:
            lay = generate_layouts(1, DEV_SEED, family=fam, dies_per_switch=k, die_size_mm=s)[0]
            fp = lay.fingerprint()[:16]
            if s == 5.0:
                assert lay.fingerprint() == spec["dev_fingerprints"][name]
                p, d = p_e009[name], json.loads((DATA / f"{fp}__L1__P_ref.json").read_text())
            else:
                cal = json.loads((CAL / f"{fp}__Pref.json").read_text())
                assert abs(cal["rise_K"] - 60.0) <= 0.25 and cal["fingerprint"] == lay.fingerprint()
                p, d = cal["P_ref_W_per_die"], json.loads((CAL / f"{fp}__L1__P_ref.json").read_text())
            assert d["fingerprint"] == lay.fingerprint() and abs(d["power_W_per_die"] - p) < 1e-9
            assert d["energy_balance"] <= 1e-6 and d.get("die_size_mm", s) == s
            raw = evaluate(lay, p, h=H, T_c=TC, calibrate=False)
            ref = np.array(d["tj_mean_K"])
            per.append(float(np.mean((ref - raw.T_bp) / (raw.tj_mean - raw.T_bp))))
        print(f"c({s} mm) table {c_table:.5f}, families {per[0]:.5f} / {per[1]:.5f}, spread {max(per) - min(per):.4f}")
        assert c_table == pytest.approx(float(np.mean(per)), abs=5e-6), (s, per)
        assert max(per) - min(per) <= 0.01, (s, per)


def test_fresh_seed_two_die_rows():
    """The T0395 fresh-development-seed rows (seed 20261395, the first 6 two-die layouts with 5.0 mm dies per family,
    P_ref by C004's rule on each stratum's first layout, level-1 references in data/o002_l1_cal/): A1-type <= 0.3 K,
    A2-type <= 0.018, and the pooled A4-type ratio <= 0.3 (0.6 x A4's 0.5, F3's design point).  These rows chose the grid
    rule (benchmarks/thermal_l1_calibration.py), so this is a regression guard, not an out-of-sample check."""
    rows = []
    for fam in ("side_by_side", "interleaved", "u_shaped"):
        lays = generate_layouts(6, 20261395, family=fam, dies_per_switch=2, die_size_mm=5.0)
        p = json.loads((CAL / f"{lays[0].fingerprint()[:16]}__Pref.json").read_text())["P_ref_W_per_die"]
        for lay in lays:
            d = json.loads((CAL / f"{lay.fingerprint()[:16]}__L1__P_ref.json").read_text())
            assert d["fingerprint"] == lay.fingerprint() and abs(d["power_W_per_die"] - p) < 1e-9
            o = evaluate(lay, p, h=H, T_c=TC)
            rows.append({"stratum": f"{fam}/2", "pred": {"P_ref": o.tj_mean}, "tbp": {"P_ref": o.T_bp},
                         "ref": {"P_ref": np.array(d["tj_mean_K"])}, "groups": _groups(lay)})
    ld = "P_ref"
    assert _p95(_a1(rows, ld)) <= A1_TOL_K
    assert _p95(_a2(rows, ld)) <= A2_TOL
    num, den = [], []
    for s in sorted({r["stratum"] for r in rows}):
        rs = [r for r in rows if r["stratum"] == s]
        for r in rs:
            num += _spread_err(r, ld)
            for w, g in r["groups"].items():
                null = np.mean([np.ptp(o["ref"][ld][o["groups"][w]]) for o in rs if o is not r])
                den.append(abs(null - np.ptp(r["ref"][ld][g])))
    assert _p95(num) / _p95(den) <= 0.3
