"""Reach mode of the derivative sampler, ``in_domain`` and the reach moves of the twin (T0377, O008 item 1; T0349 section 2.2).

Development geometry only: 2D_Case_2R is a PowerSynth public benchmark used as development geometry under D0023, 2D_Case_4 the
O006 pilot geometry; no judged reference.  Both are built the way E010's prepare does (``experiments/runners/e010_run.py``
and ``research/scripts/o003_powersynth_references.py``, imported by path).
"""
import importlib.util
import hashlib
import re
import sys
from pathlib import Path

import numpy as np
import pytest
import yaml

from moduleforge.drc import check
from moduleforge.generate import derivative as D
from moduleforge.generate import twin as W

ROOT = Path(__file__).resolve().parents[3]
DEV_SEED = 20261110  # E010 config.dev.dev_seed
RATE_SEED, RATE_DRAWS = 3770001, 20000

# Fingerprints of fixed streams recorded from the UNMODIFIED sampler (before T0377): sha256 prefix of the concatenated
# parameter vectors of 2000 / 3000 raw ``_sample`` draws (None draws count as b"N") with the number of None draws, and the
# Layout fingerprints of the first ``generate`` layouts.  Seed: the dev seed.
BASELINE = {
    "housing_k1": {
        "raw": ("5c78aed0cb38aa2c", 1522),
        "gen": (
            "175c80624f76887552cf4f10a11fb11c93942e2c87f86ff61d04d48b91b5aca6",
            "a1bd9543b8dbb5ca2d22d1c263d825ac18446568fc432cae1c5b3ac70ac3b4ed",
            "52446e7073c0019f43fa2e5cd1e89be32c21d4c4b0fc71e16b7bd7dc3cf7713a",
            "8371d1ed8d6fa9fbfdd2dc59d3a8ec685c1413b36afd0c01bec12ade305430b3",
            "1e8144537d02c8c53cbe5ef56b2b929698682bed1f1574fa9e190db81f3bad82",
            "a2f251cb1f0ca5e5418193546528ee4863c7cbabc0ee319520b4f79e808466c1",
        ),
    },
    "housing_k3": {
        "raw": ("c635c5417b23cc74", 1482),
        "gen": (
            "29838a6d48c60fcc182a858fe6b734731fd214151658ce625c8eb7ae2cc24a88",
            "10fa83d57308ecc543c23c8ecf3af40fd1737fa76fc1800ce7f1569cdcbe7602",
            "65103da2cd6e3ea8bdbb1a7dbc1eadcfc0597880fab788e32b33b10a45e1af6f",
            "5aac958f2546dddef4f5fd208a675a736532cce5ff620aa9d173c88ff346f394",
            "8462202791a02c75bb819be143efa6963347d0e357bb8fac94cee16e80197ec8",
            "e682afa4f63ac7cba34b2f436682cc1dfe43c45280d3acf1c4f57ae4b8ee54b3",
        ),
    },
    "case4": {
        "raw": ("8d0ba74f920b707b", 2640),
        "gen": (
            "001f2b89f5d864f470de63771139212bd587995319c16a3a679b8a52bc42d441",
            "a904164c7d02160ac21e8c1f63345c8a8963f2a2a308a47015cbffa05d1f6681",
            "48f23e4164eb64311af4bea41d7609ff19f6ccca4602fefd187a9b5cbeca37b2",
            "0201b7552742f030224af23d67053d4fbda8de8552bc9b0abaae281e6982219b",
        ),
    },
}


def _e010():
    name = "e010_run_for_reach_test"
    if name in sys.modules:
        return sys.modules[name]
    sp = importlib.util.spec_from_file_location(name, ROOT / "experiments" / "runners" / "e010_run.py")
    m = importlib.util.module_from_spec(sp)
    sys.modules[name] = m
    sp.loader.exec_module(m)
    return m


@pytest.fixture(scope="module")
def cfg():
    return yaml.safe_load((ROOT / "experiments" / "specs" / "E010.yaml").read_text())["config"]


@pytest.fixture(scope="module")
def case4(cfg):
    """2D_Case_4's development spec under its measured rules (E010 dev_reference) and its twin as prepare() builds it."""
    rc = _e010().dev_reference("case4", cfg)
    tw, p, _ = W.twin(rc.reference, rc.spec, with_l1=False)
    return rc.spec, tw, p


@pytest.fixture(scope="module")
def twoR(cfg):
    """2D_Case_2R's spec (judged_reference: e008_rules on the reconstruction) and its twin as prepare() builds it."""
    entry = next(x for x in cfg["references"] if x["reference_id"] == "2D_Case_2R")
    rc = _e010().judged_reference(entry, cfg)
    tw, p, _ = W.twin(rc.reference, rc.spec, with_l1=False)
    return rc.spec, tw, p


@pytest.fixture(scope="module")
def housing_specs():
    return {k: D.halfbridge_housing_spec(3, wires_per_die=k) for k in (1, 3)}


def _raw_hash(spec, seed, n):
    cx = D._Ctx(spec)
    rng = np.random.default_rng(seed)
    h, none = hashlib.sha256(), 0
    for _ in range(n):
        p = D._sample(spec, cx, rng)
        if p is None:
            none += 1
            h.update(b"N")
        else:
            h.update(p.to_vector().tobytes())
    return h.hexdigest()[:16], none


# -------------------------------------------------------------------------------------------------------- 1. reach off
@pytest.mark.parametrize("k", [1, 3])
def test_reach_off_streams_are_bit_identical_housing(housing_specs, k):
    spec, base = housing_specs[k], BASELINE[f"housing_k{k}"]
    assert _raw_hash(spec, DEV_SEED, 2000) == base["raw"]
    assert tuple(lay.fingerprint() for lay in D.generate(spec, 6, DEV_SEED)) == base["gen"]
    assert tuple(lay.fingerprint() for lay in D.generate(spec, 6, DEV_SEED, reach=False)) == base["gen"]


def test_reach_off_streams_are_bit_identical_case4_measured_rules(case4):
    spec, base = case4[0], BASELINE["case4"]
    assert _raw_hash(spec, DEV_SEED, 3000) == base["raw"]
    assert tuple(lay.fingerprint() for lay in D.generate(spec, 4, DEV_SEED)) == base["gen"]


def test_reach_on_is_a_different_stream(housing_specs):
    spec = housing_specs[1]
    cx = D._Ctx(spec, reach=True)
    rng = np.random.default_rng(DEV_SEED)
    h = hashlib.sha256()
    for _ in range(2000):
        p = D._sample(spec, cx, rng)
        h.update(b"N" if p is None else p.to_vector().tobytes())
    assert h.hexdigest()[:16] != BASELINE["housing_k1"]["raw"][0]


# -------------------------------------------------------------------------------------------------------- 2. soundness
@pytest.mark.parametrize("reach", [False, True])
@pytest.mark.parametrize("k", [1, 3])
def test_every_housing_draw_is_in_its_own_domain(housing_specs, k, reach):
    spec = housing_specs[k]
    cx = D._Ctx(spec, reach=reach)
    lays = D.generate(spec, 200, DEV_SEED + 1, reach=reach)
    assert len(lays) == 200
    bad = [(i, why) for i, lay in enumerate(lays) if not (r := D.in_domain(spec, D.params_of(lay), reach, ctx=cx))[0]
           for why in [r[1]]]
    assert not bad, bad[:5]


@pytest.mark.parametrize("reach", [False, True])
def test_every_case4_draw_is_in_its_own_domain(case4, reach):
    spec = case4[0]
    cx = D._Ctx(spec, reach=reach)
    lays = D.generate(spec, 20, DEV_SEED + 2, reach=reach)
    bad = [D.in_domain(spec, D.params_of(lay), reach, ctx=cx) for lay in lays]
    assert all(ok for ok, _ in bad), bad


def test_reach_domain_contains_the_legacy_domain(housing_specs):
    spec = housing_specs[1]
    cx = D._Ctx(spec, reach=True)
    for lay in D.generate(spec, 60, DEV_SEED + 3):
        assert D.in_domain(spec, D.params_of(lay), True, ctx=cx)[0]


def test_in_domain_rejects_a_context_of_the_other_mode(housing_specs):
    spec = housing_specs[1]
    p = D.params_of(D.generate(spec, 1, 1)[0])
    with pytest.raises(ValueError):
        D.in_domain(spec, p, True, ctx=D._Ctx(spec, reach=False))


# ---------------------------------------------------------------------------------------------------------- 3. the twins
def _check_twin(spec, tw, p):
    assert D.build(spec, p).fingerprint() == tw.fingerprint()
    assert check(tw, spec.rules) == []
    assert check(D.build(spec, D.params_of(tw)), spec.rules) == []
    assert D.build(spec, D.params_of(tw)).fingerprint() == tw.fingerprint()


def test_case4_twin_is_in_the_reach_domain(case4):
    spec, tw, p = case4
    _check_twin(spec, tw, p)
    assert D.in_domain(spec, D.params_of(tw), reach=True) == (True, "")


def test_2r_twin_is_in_the_reach_domain_and_outside_the_legacy_one(twoR):
    spec, tw, p = twoR
    _check_twin(spec, tw, p)
    assert D.in_domain(spec, D.params_of(tw), reach=True) == (True, "")
    ok, why = D.in_domain(spec, D.params_of(tw), reach=False)
    assert not ok
    # T0349: the PHASE column's outer edge is at 47 mm (legacy: at most pad edge + 1.5 = 45.5 mm) and the DC+ / DC- slots
    # straddle their columns; the first failing constraint is one of a column's edges or a slot's attachment
    assert re.fullmatch(r"col_(DC\+|DC-|PHASE)_(outer|inner|v)_edge|slot\d_attach", why), why
    assert why == "col_PHASE_outer_edge"
    assert p.cols[2][2] == 47.0


def test_2r_attached_form_of_t0349_is_outside_the_legacy_domain_for_two_reasons(twoR):
    """T0349 attached-form test (research/diagnoses/T0349/attached_twin.py): W with every slot attached at its column's inner
    edge.  T0349 named one obstacle, the PHASE column's outer edge (47 mm against the legacy limit 45.5 mm) and said the
    support argument was 'not checked through _sample's full joint constraints'.  Checked here: with the edge at 45.5 mm the
    layout is still outside the legacy domain, because the LS die row starts 11 mm from the PHASE column's inner edge (legacy:
    at most dem + 6 mm).  Reach covers both."""
    spec, tw, p = twoR
    v = p.to_vector()
    names = D.Params.NAMES
    for n, x in (("col_DC+_u0", 7.5), ("col_DC-_u0", 7.5), ("slot0_u0", 12.0), ("slot2_u0", 12.0), ("slot1_u1", 37.0),
                 ("slot3_u1", 37.0), ("col_DC+_v0", 37.0), ("col_DC+_v1", 45.0), ("col_DC-_v0", 7.0), ("col_DC-_v1", 13.0),
                 ("col_PHASE_v0", 15.0), ("col_PHASE_v1", 51.0)):
        v[names.index(n)] = x
    assert D.in_domain(spec, D.Params.from_vector(v), reach=False) == (False, "col_PHASE_outer_edge")  # at 47 mm
    v[names.index("col_PHASE_u1")] = 45.5
    q = D.Params.from_vector(v)
    assert D.in_domain(spec, q, reach=False) == (False, "row_LS_u0")
    assert D.in_domain(spec, q, reach=True) == (True, "")


# ----------------------------------------------------------------------------------------------------------- 4. the rate
def _features(spec, cx, p):
    """(has a straddling slot, has a column outer edge beyond pad edge + 1.5 mm) of a parameter vector."""
    fr = D._Frame(p.orient)
    seq = p.sequence()
    strad = outer = False
    for net, c in zip(D.NETS, p.cols, strict=True):
        pu0, _, pu1, _ = (x * 1e3 for x in fr.lrect(*cx.pads[net]))
        mine = [s for (n, _, _), s in zip(seq, p.slots, strict=True) if n == net]
        low = sum(0.5 * (s[0] + s[2]) for s in mine) / len(mine) >= 0.5 * (c[0] + c[2])  # slots run towards +u
        if low and c[0] < D._g_dn(pu0) - 1.5 - 1e-9 or not low and c[2] > D._g_up(pu1) + 1.5 + 1e-9:
            outer = True
        for s in mine:
            if (low and s[0] < c[2] - 1e-9) or (not low and s[2] > c[0] + 1e-9):
                strad = True
    return strad, outer


def _rate(spec, reach):
    cx = D._Ctx(spec, reach=reach)
    rng = np.random.default_rng(RATE_SEED)
    n = s = o = 0
    for _ in range(RATE_DRAWS):
        p = D._sample(spec, cx, rng)
        if p is None:
            continue
        n += 1
        a, b = _features(spec, cx, p)
        s, o = s + a, o + b
    return n, s, o


def test_reach_emits_straddling_slots_and_far_column_edges_on_2r(twoR):
    """MEASURED (T0377, 2R spec, seed 3770001, 20000 raw ``_sample`` draws): reach off 232 non-None draws, 0 straddling slots,
    0 outer edges beyond pad + 1.5 mm; reach on 208 non-None draws, 188 with a straddling slot (0.94 % of the raw draws), 93
    with an outer edge beyond pad + 1.5 mm (0.47 %)."""
    spec = twoR[0]
    n0, s0, o0 = _rate(spec, False)
    n1, s1, o1 = _rate(spec, True)
    print(f"2R reach off: {n0} non-None, {s0} straddling, {o0} far outer edges; reach on: {n1} non-None, {s1} straddling, "
          f"{o1} far outer edges, of {RATE_DRAWS} raw draws")
    assert (s0, o0) == (0, 0)
    assert s1 > 0 and o1 > 0
    assert s1 >= 50 and o1 >= 25  # far above chance of a fluke; measured 188 and 93


def test_generate_reach_returns_drc_clean_straddling_layouts_on_2r(twoR):
    spec = twoR[0]
    cx = D._Ctx(spec, reach=True)
    lays = D.generate(spec, 20, 3770002, reach=True)
    assert all(check(lay, spec.rules) == [] for lay in lays)
    feats = [_features(spec, cx, D.params_of(lay)) for lay in lays]
    assert any(a for a, _ in feats) and any(b for _, b in feats)


# ------------------------------------------------------------------------------------------ 5. hand-made out-of-support
def _edit(p, **kw):
    v = p.to_vector()
    for n, x in kw.items():
        v[D.Params.NAMES.index(n)] = x
    return D.Params.from_vector(v)


def test_hand_made_vectors_outside_the_support(twoR):
    spec, tw, p = twoR
    cx = {r: D._Ctx(spec, reach=r) for r in (False, True)}
    assert D.in_domain(spec, p, True, ctx=cx[True]) == (True, "")
    cases = [
        (_edit(p, orient=2), "flags"),
        (_edit(p, hs_first=-1), "flags"),
        (_edit(p, slot1_v1=p.slots[1][3] - 3.0), "slot1_height"),        # a die slot shorter than die + margins
        (_edit(p, slot1_v0=p.slots[1][1] + 0.25), "slot1_height"),       # off the 0.5 mm grid
        (_edit(p, slot2_v0=23.0, slot2_v1=31.0), "slot1_gap"),     # touches the previous slot of another net: gap < spacing
        (_edit(p, col_PHASE_u1=48.5), "col_PHASE_outer_edge"),           # beyond the outline's edge-margin limit (48 mm)
        (_edit(p, col_PHASE_u1=47.25), "col_PHASE_outer_edge"),          # off the grid
        (_edit(p, row_HS_gap=4.25), "row_HS_gap"),
        (_edit(p, land_HS=48.0625), "land_HS"),                          # off the 0.125 mm grid
        (_edit(p, foot_HS_fv=p.feet[0][3] + 0.1), "feet_HS_fv"),
    ]
    for q, expected in cases:
        for reach in (True,):
            ok, why = D.in_domain(spec, q, reach, ctx=cx[reach])
            assert not ok and why == expected, (expected, why)
    # reach off: the PHASE column's 47 mm edge is the first constraint to fail, whatever else is edited later
    assert D.in_domain(spec, _edit(p, row_HS_gap=4.25), False, ctx=cx[False]) == (False, "col_PHASE_outer_edge")
    ok, why = D.in_domain(spec, np.zeros(3))
    assert not ok and why.startswith("vector")


def test_in_domain_needs_the_layout_to_build_and_be_clean(housing_specs):
    spec = housing_specs[1]
    lay = D.generate(spec, 1, 11)[0]
    p = D.params_of(lay)
    assert D.in_domain(spec, p) == (True, "")
    # a legacy-sampled vector whose spec is stricter than the one it was drawn for: the replay passes, the DRC does not
    strict = D.halfbridge_housing_spec(3, wires_per_die=1)
    import dataclasses
    strict = dataclasses.replace(strict, rules=dataclasses.replace(strict.rules, min_spacing=60e-3))
    ok, why = D.in_domain(strict, p)
    assert not ok


# --------------------------------------------------------------------------------------------------- (c) twin reach moves
def test_reach_moves_extend_the_enumeration_without_changing_the_legacy_one(twoR):
    spec, tw, p = twoR
    legacy = [(n, d, q.to_vector().tolist()) for n, d, q in W._walk_candidates(p)]
    assert legacy == [(n, d, q.to_vector().tolist()) for n, d, q in W._walk_candidates(p, spec, False)]
    both = list(W._walk_candidates(p, spec, True))
    assert [(n, d, q.to_vector().tolist()) for n, d, q in both[:len(legacy)]] == legacy
    extra = {n: (d, q) for n, d, q in both[len(legacy):]}
    # moves of slot extents across columns and of column outer edges exist (2R: columns at 9..12 / 37..47, outline limit 7 / 48)
    assert {"slot0_attach>col_inner", "slot2_attach>col_inner", "slot0_free>limit", "col_PHASE_outer>limit",
            "col_PHASE_outer>pad"} <= set(extra)
    base = p.to_vector()
    for n, (d, q) in extra.items():
        diff = np.flatnonzero(np.abs(q.to_vector() - base) > 1e-12)
        assert len(diff) == 1 and abs(abs(q.to_vector()[diff[0]] - base[diff[0]]) - abs(d)) < 1e-9, n
    d, q = extra["col_PHASE_outer>pad"]
    assert q.cols[2][2] == 44.0 and d == -3.0
    d, q = extra["slot0_attach>col_inner"]
    assert q.slots[0][0] == 12.0 and d == 5.0
    # every reach move that builds, is _quick_ok and DRC-clean is in the reach domain (it moves one coordinate inside the
    # intervals the reach sampler draws from); the others (a free end past another net's column, ...) are the DRC's to reject
    cx = D._Ctx(spec, reach=True)
    n_valid = 0
    for n, (_d, q) in extra.items():
        lay, _ = W._try(spec, q)
        if lay is None or not D._quick_ok(spec, cx, lay):
            continue
        n_valid += 1
        assert D.in_domain(spec, q, True, ctx=cx) == (True, ""), n
    assert n_valid >= 3
    with pytest.raises(ValueError):
        list(W._walk_candidates(p, None, True))


def test_reach_move_families_are_appended_after_the_legacy_ones(twoR):
    spec, tw, p = twoR
    legacy = [n for n, _, _ in W._moves()]
    both = [n for n, _, _ in W._moves(True)]
    assert both[:len(legacy)] == legacy and both[len(legacy):] == [
        "straddle[0]", "straddle[1]", "straddle[2]", "straddle[3]", "outer[DC+]", "outer[DC-]", "outer[PHASE]"]
    fam = {n: f for n, _, f in W._moves(True)}
    q = fam["outer[PHASE]"](p, spec, 3)  # 3 steps of 0.5 mm: the outer edge 47 -> 48 (the limit), clipped
    assert q.cols[2][2] == 48.0
    q = fam["straddle[0]"](p, spec, 2)  # slot 0 (DC-, side -1): the attached end 7 stays at the limit 7
    assert q.slots[0][0] == 7.0
    q = fam["straddle[1]"](p, spec, 2)  # slot 1 (PHASE die, side +1): the attached end 47 -> 48 at the limit
    assert q.slots[1][2] == 48.0
