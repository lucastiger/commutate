"""Adding thermal layers/materials to ``LayerStack`` must not change any electromagnetic quantity (T0148).

``data/em_before_thermal_stack.json`` was captured from the commit *before* the thermal stack extension
(``generate_layouts(1, seed=7, family=f, dies_per_switch=n)`` for every family at n = 2 and 6): the full
``to_conductors()`` output (rectangles, wire segments, planes, die shorts, port, the five EM layers) and the
L1 PEEC loop inductance/resistance at three frequencies. This test recomputes them and requires equality to
rtol 1e-14 (they are in fact bit-identical, since no EM code path reads the new fields).

Regenerating the file is only legitimate from a commit whose EM code is known-good:
``python tests/regression/test_em_unchanged_by_thermal_stack.py --capture``.
"""
from __future__ import annotations

import dataclasses
import json
import platform
import sys
from pathlib import Path

import numpy as np
import pytest

from moduleforge.generate.halfbridge import FAMILIES, generate_layouts
from moduleforge.physics.peec import loop_inductance

DATA = Path(__file__).parent / "data" / "em_before_thermal_stack.json"
FREQS = [5e6, 2e7, 8e7]
CASES = [(f, n) for f in FAMILIES for n in (2, 6)]
SEED = 7
RTOL = 1e-14
# The baseline was captured on the founder's Apple-silicon Mac. The geometry is plain float arithmetic and must match
# everywhere; L_H and R_ohm come from dense linear solves whose last bits depend on the BLAS/LAPACK build (Accelerate
# on macOS, OpenBLAS on Linux CI), so the stored-value check for them holds only on the capture platform. The
# platform-independent claim of this file (no EM path reads the thermal fields) is tested exactly, on every
# platform, by test_em_outputs_do_not_depend_on_thermal_fields.
CAPTURE_PLATFORM = ("darwin", "arm64")
SOLVER_KEYS = ("L_H", "R_ohm")
ON_CAPTURE_PLATFORM = (sys.platform, platform.machine()) == CAPTURE_PLATFORM


def _key(family, n):
    return f"{family}_{n}"


def snapshot(layout) -> dict:
    """JSON-able record of the EM-relevant outputs of ``layout`` (floats keep full float64 precision)."""
    cm = layout.to_conductors()
    r = loop_inductance(layout, FREQS)
    st = cm.stack
    return {
        "stack_kind": st.kind,
        "stack_em_layers": [[la.name, la.material, la.thickness, la.sigma, la.k] for la in st.layers],
        "rects": [[c.net, c.x0, c.y0, c.x1, c.y1, c.z, c.thickness, c.sigma] for c in cm.rects],
        "wires": [[w.wire_index, w.net, *w.p0, *w.p1, w.diameter, w.sigma] for w in cm.wires],
        "planes": [[p.name, p.outline.tolist(), p.z_bottom, p.thickness, p.sigma] for p in cm.planes],
        "shorts": [[s.die_index, s.switch, s.x, s.y, s.w, s.h, s.z_bottom, s.z_top, s.bottom_net, list(s.pad)]
                   for s in cm.shorts],
        "port": [list(cm.port.p_pos), list(cm.port.p_neg), cm.port.phase_open],
        "L_H": [float(v) for v in r.L_H],
        "R_ohm": [float(v) for v in r.R_ohm],
    }


def _layout(family, n):
    return generate_layouts(1, seed=SEED, family=family, dies_per_switch=n)[0]


def _compare(a, b, path=""):
    if isinstance(b, (int, float)) and not isinstance(b, bool):
        assert np.isclose(a, b, rtol=RTOL, atol=0.0), f"{path}: {a!r} != {b!r}"
    elif isinstance(b, list):
        assert len(a) == len(b), f"{path}: length {len(a)} != {len(b)}"
        for i, (x, y) in enumerate(zip(a, b, strict=True)):
            _compare(x, y, f"{path}[{i}]")
    elif isinstance(b, dict):
        assert set(a) == set(b), path
        for k in b:
            _compare(a[k], b[k], f"{path}.{k}")
    else:
        assert a == b, f"{path}: {a!r} != {b!r}"


def test_baseline_file_covers_every_family_at_2_and_6_dies():
    ref = json.loads(DATA.read_text())
    assert ref["meta"]["seed"] == SEED
    assert set(ref["cases"]) == {_key(f, n) for f, n in CASES}


@pytest.mark.parametrize("family,n", CASES)
def test_em_geometry_identical_to_pre_thermal_commit(family, n):
    ref = json.loads(DATA.read_text())["cases"][_key(family, n)]
    now = json.loads(json.dumps(snapshot(_layout(family, n))))
    _compare({k: v for k, v in now.items() if k not in SOLVER_KEYS},
             {k: v for k, v in ref.items() if k not in SOLVER_KEYS}, _key(family, n))


@pytest.mark.skipif(not ON_CAPTURE_PLATFORM, reason="L/R baseline holds bit-for-bit only on the capture platform "
                    f"{CAPTURE_PLATFORM} (BLAS-dependent last bits); test_em_outputs_do_not_depend_on_thermal_fields "
                    "checks the invariant on every platform")
@pytest.mark.parametrize("family,n", CASES)
def test_em_solver_outputs_identical_to_pre_thermal_commit(family, n):
    ref = json.loads(DATA.read_text())["cases"][_key(family, n)]
    now = json.loads(json.dumps(snapshot(_layout(family, n))))
    _compare({k: now[k] for k in SOLVER_KEYS}, {k: ref[k] for k in SOLVER_KEYS}, _key(family, n))


@pytest.mark.parametrize("family,n", CASES)
def test_em_outputs_do_not_depend_on_thermal_fields(family, n):
    """Changing only the thermal fields (die_attach, die layers) must leave every EM output bit-identical."""
    lay = _layout(family, n)
    st = lay.stack
    other = dataclasses.replace(
        st,
        die_attach=dataclasses.replace(st.die_attach, material="Ag-sinter", thickness=2 * st.die_attach.thickness,
                                       k=3 * st.die_attach.k),
        die=dataclasses.replace(st.die, thickness=0.5 * st.die.thickness, k=0.5 * st.die.k))
    assert other.die_attach != st.die_attach and other.die != st.die
    a = json.loads(json.dumps(snapshot(lay)))
    b = json.loads(json.dumps(snapshot(dataclasses.replace(lay, stack=other))))
    assert a == b, "an EM output changed when only thermal fields changed"


if __name__ == "__main__":
    if "--capture" not in sys.argv:
        raise SystemExit("pass --capture to (re)generate the baseline from the current commit")
    out = {"meta": {"seed": SEED, "freqs_hz": FREQS, "note": "captured before the thermal LayerStack extension"},
           "cases": {_key(f, n): snapshot(_layout(f, n)) for f, n in CASES}}
    DATA.write_text(json.dumps(out))
    print("wrote", DATA, DATA.stat().st_size, "bytes")
