import dataclasses

import numpy as np
import pytest

from moduleforge.drc import check
from moduleforge.generate import halfbridge
from moduleforge.generate.halfbridge import FAMILIES, generate_layouts, loop_area_proxy
from moduleforge.geometry import Terminal


@pytest.fixture(scope="module")
def sixty():
    return generate_layouts(60, seed=12345)


def test_all_drc_valid(sixty):
    assert len(sixty) == 60
    assert all(check(lay) == [] for lay in sixty)


def test_seeded_determinism(sixty):
    again = generate_layouts(60, seed=12345)
    assert [x.fingerprint() for x in sixty] == [x.fingerprint() for x in again]
    other = generate_layouts(60, seed=54321)
    assert [x.fingerprint() for x in sixty] != [x.fingerprint() for x in other]


def test_coverage_of_families_and_die_counts(sixty):
    assert {x.family for x in sixty} == set(FAMILIES)
    assert {x.dies_per_switch for x in sixty} == {2, 3, 4, 5, 6}
    for x in sixty:
        assert sum(d.switch == "HS" for d in x.dies) == x.dies_per_switch == sum(d.switch == "LS" for d in x.dies)


def test_families_topologically_distinct():
    by = {f: generate_layouts(1, seed=1, family=f, dies_per_switch=3)[0] for f in FAMILIES}
    # number of polygon exteriors/concavity differs: PHASE is convex in side_by_side, non-convex otherwise
    def convex(lay):
        p = next(t for t in lay.traces if t.net == "PHASE").polygon
        return abs(p.convex_hull.area - p.area) < 1e-12
    assert not convex(by["interleaved"]) and not convex(by["u_shaped"])
    # DC+/DC- adjacency: interleaved rows are separated only by the min gap, u_shaped by a PHASE row
    def gap(lay):
        a, b = (next(t for t in lay.traces if t.net == n).polygon for n in ("DC+", "DC-"))
        return a.distance(b)
    assert gap(by["interleaved"]) < 3e-3 < gap(by["u_shaped"])


def test_fixed_housing_terminals(sixty):
    ref = {n: (t.cx, t.cy, t.w, t.h) for n, t in sixty[0].terminals.items()}
    assert set(ref) == {"DC+", "DC-", "PHASE"}
    for x in sixty:
        assert {n: (t.cx, t.cy, t.w, t.h) for n, t in x.terminals.items()} == ref


def test_family_and_count_filters():
    ls = generate_layouts(5, seed=2, family="u_shaped", dies_per_switch=4)
    assert {x.family for x in ls} == {"u_shaped"} and {x.dies_per_switch for x in ls} == {4}
    with pytest.raises(ValueError):
        generate_layouts(1, seed=0, family="nope")
    with pytest.raises(ValueError):
        generate_layouts(1, seed=0, dies_per_switch=7)


def test_reject_and_resample_bounded(monkeypatch):
    monkeypatch.setattr(halfbridge, "check", lambda lay: ["always bad"])
    with pytest.raises(RuntimeError):
        generate_layouts(1, seed=0, max_tries=5)


@pytest.mark.parametrize("seed", [12345, 1, 2])
def test_loop_area_proxy_spread(seed):
    a = np.array([loop_area_proxy(x) for x in generate_layouts(60, seed=seed)])
    assert (a > 0).all()
    assert a.std(ddof=1) / a.mean() >= 0.3  # E002 sample_diverse early check (F2)


def test_loop_area_proxy_known_value():
    # hand-built: DC+ (0,0), DC- (0,3 mm), HS dies at (4,0) mm, LS dies at (4,3) mm -> 4 x 3 mm rectangle
    lay = generate_layouts(1, seed=3, family="side_by_side", dies_per_switch=3)[0]
    hs = [dataclasses.replace(d, cx=4e-3, cy=0.0) for d in lay.dies if d.switch == "HS"]
    ls = [dataclasses.replace(d, cx=4e-3, cy=3e-3) for d in lay.dies if d.switch == "LS"]
    terms = {**lay.terminals, "DC+": Terminal("DC+", 0.0, 0.0, 1e-3, 1e-3),
             "DC-": Terminal("DC-", 0.0, 3e-3, 1e-3, 1e-3)}
    rect = dataclasses.replace(lay, dies=hs + ls, terminals=terms)
    assert loop_area_proxy(rect) == pytest.approx(12e-6, rel=1e-12)
    # a right triangle: HS and LS centroids coincide -> DC+ (0,0), P (4,0), P, DC- (0,3): area 0.5*4*3 = 6 mm^2
    ls_at_hs = [dataclasses.replace(d, cx=4e-3, cy=0.0) for d in ls]
    tri = dataclasses.replace(lay, dies=hs + ls_at_hs, terminals=terms)
    assert loop_area_proxy(tri) == pytest.approx(6e-6, rel=1e-12)


def test_every_trace_edge_and_die_footprint_on_the_design_grid(sixty):
    """T0075 (founder re-scope I0039): every free parameter is snapped to the 0.5 mm design grid, so every trace polygon
    vertex and every die footprint edge is a multiple of 0.5 mm (the layout L2 meshes them exactly with cells that divide
    it); the die-row start may sit anywhere on the grid, not only at X_DIE_MIN."""
    q = halfbridge.DESIGN_GRID_MM * 1e-3

    def on_grid(v):
        return abs(v / q - round(v / q)) < 1e-9

    starts = set()
    for lay in sixty:
        for t in lay.traces:
            assert all(on_grid(x) and on_grid(y) for x, y in t.polygon.exterior.coords), (lay.family, t.net)
        for d in lay.dies:
            assert all(on_grid(v) for v in (d.cx - d.w / 2, d.cx + d.w / 2, d.cy - d.h / 2, d.cy + d.h / 2)), lay.family
            assert 4e-3 - 1e-12 <= d.w <= 5.5e-3 + 1e-12 and d.w == d.h
        starts.add(round(min(d.cx - d.w / 2 for d in lay.dies) * 1e3, 6))
    assert len(starts) > 5, starts


# ---- T0394: fixed die size per stratum ----------------------------------------------------------------------------

# Fingerprints captured from the generator BEFORE die_size_mm existed: die_size_mm=None must reproduce them.
_PINNED = {
    ("side_by_side", 2): ["adce19664901edce46a97f475ee52862fe3d65cdf99fe23ec389a804225edbec",
                          "a593fda0dfb21e44c14ac772620396e9a698f52df0d3978fdc9b1fddd5764f7d"],
    ("side_by_side", 4): ["18ad2efd7c6dd2adccfb89e91705f3e633f2e2b141d42374520c417aede8223b",
                          "32c972f7db0b28158b24baf09d5a29cfa2b4e908c7d15e6835140761ca676967"],
    ("side_by_side", 6): ["0056a5e17d6f3b7793e112d582abc9cddc3050c9315786fb5d6df0a34d7277f7",
                          "bf40adeb881ccd1ffe86a0cae15e4a2672fc372883cc0e71a22adc2e361ad50d"],
    ("interleaved", 2): ["286ec5c01228672c3ff0602651758afe85a606f28725934125052006f0f8a24d",
                         "d596d1eebe46996440383bc056ecccd3038a019c2af0ac470cca669b814ee35d"],
    ("interleaved", 4): ["6c6534f3c2a4c66856991f3fab28b00c795d8412319d1da581dba0fad2f15619",
                         "37c59e59c255dadcbf055ce6e359e368cfef41e8f3618f2c8f6ad1fc18929adf"],
    ("interleaved", 6): ["e30b62c8626c27d0b0393c4caca63a3b74cb6d2183f27091e9a276e6fa546ddd",
                         "2126333817dea35774b8f989fd830b37fe52c27b5a4432ea1b8a7f921a300ceb"],
    ("u_shaped", 2): ["23377391669d9c95cd1eb035c935d5cb988fceb4a921b26cfe49d0cdea2f6a5b",
                      "b9d4564df41d09998b93bbdd15283622c08209ba55250a9f365510f5ff445b7d"],
    ("u_shaped", 4): ["d8e20ebffdf7e466c0e28ff192e7af5dc98250b451c53101aa54045195a9333a",
                      "13a154d2d9ed482e0cf4c3350414cc0c278c7b6b54dd6dbb5728d0efd4c10ba3"],
    ("u_shaped", 6): ["f9c22e03d70d60b3eea5b164fa286f1b00001f55e31dddf61b956826e40efac7",
                      "da50c75dc7f64640eca52f8cb886961c7d63455fe73aefbd3b6410745d9a8a8b"],
}
_PINNED_MIXED_SEED5 = ["4db5cf7e1edd404c9cd6367a985e46729502baca70fb6a39e56dbc8c2a65b495",
                       "c480b556d0072e79a98bc30d07bac9be7582e2c46b7f766cccb989866de39b76",
                       "04d8b7f4d5af8191f788ba19a55153f3bf72c896000c12dd7a77e5af79734cde",
                       "f3632b0106fadd8f022e5d6b4efed12838a95a8b3dc6f7e53d6ebc7268be7591"]


@pytest.mark.parametrize("fam,n", sorted(_PINNED))
def test_die_size_none_is_byte_identical_to_before(fam, n):
    got = [x.fingerprint() for x in generate_layouts(2, seed=11, family=fam, dies_per_switch=n)]
    assert got == _PINNED[(fam, n)]
    got = [x.fingerprint() for x in generate_layouts(2, seed=11, family=fam, dies_per_switch=n, die_size_mm=None)]
    assert got == _PINNED[(fam, n)]


def test_die_size_none_mixed_strata_pinned():
    assert [x.fingerprint() for x in generate_layouts(4, seed=5)] == _PINNED_MIXED_SEED5


@pytest.mark.parametrize("size", [4.0, 5.0, 5.5])
@pytest.mark.parametrize("fam", FAMILIES)
@pytest.mark.parametrize("n", [2, 3, 4, 5, 6])
def test_fixed_die_size_on_every_die(fam, n, size):
    lays = generate_layouts(3, seed=7, family=fam, dies_per_switch=n, die_size_mm=size)
    assert len(lays) == 3
    for lay in lays:
        assert check(lay) == []
        assert len(lay.dies) == 2 * n
        assert all(abs(d.w - size * 1e-3) < 1e-12 and abs(d.h - size * 1e-3) < 1e-12 for d in lay.dies)


def test_fixed_die_size_leaves_other_layouts_varying():
    lays = generate_layouts(6, seed=3, family="interleaved", dies_per_switch=3, die_size_mm=4.5)
    assert len({x.fingerprint() for x in lays}) == 6


@pytest.mark.parametrize("bad", [3.5, 3.9999, 5.6, 6.0, 0.0, -4.5, 4.25, 4.1, 5.4, float("nan"), float("inf")])
def test_die_size_validation_errors(bad):
    with pytest.raises(ValueError):
        generate_layouts(1, seed=0, die_size_mm=bad)


def test_die_size_determinism_in_seed():
    a = generate_layouts(5, seed=9, family="u_shaped", dies_per_switch=5, die_size_mm=5.0)
    b = generate_layouts(5, seed=9, family="u_shaped", dies_per_switch=5, die_size_mm=5.0)
    c = generate_layouts(5, seed=10, family="u_shaped", dies_per_switch=5, die_size_mm=5.0)
    assert [x.fingerprint() for x in a] == [x.fingerprint() for x in b]
    assert [x.fingerprint() for x in a] != [x.fingerprint() for x in c]


def test_draw_die_size_support_and_distribution():
    rng = np.random.default_rng(0)
    draws = np.array([halfbridge.draw_die_size_mm(rng) for _ in range(4000)])
    assert set(np.unique(draws)) == {4.0, 4.5, 5.0, 5.5}
    # uniform(4, 5.5) snapped to 0.5: the end bins have probability 1/6, the middle ones 1/3
    frac = {v: float(np.mean(draws == v)) for v in (4.0, 4.5, 5.0, 5.5)}
    assert frac[4.0] == pytest.approx(1 / 6, abs=0.03) and frac[5.5] == pytest.approx(1 / 6, abs=0.03)
    assert frac[4.5] == pytest.approx(1 / 3, abs=0.04) and frac[5.0] == pytest.approx(1 / 3, abs=0.04)
    # same stream as _build's own draw: the first draw of a Generator equals the size _build uses unfixed
    lay = halfbridge._build("side_by_side", 2, np.random.default_rng(42))
    assert lay.dies[0].w == pytest.approx(halfbridge.draw_die_size_mm(np.random.default_rng(42)) * 1e-3, abs=1e-15)
