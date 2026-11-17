"""Tests of the FastHenry run adapter (T0385; O004, D0002).

Real-binary tests run the locally provisioned FastHenry 3.0wr (skipped, with a reason, when it is not provisioned); the
retry / crash / timeout logic runs against fake binaries (shell scripts).  No 2D_Case_2R or 2D_Case_6 geometry (O004 F2).

Tolerances, each derived where it is set:
* bar vs Hoer-Love: Zc.mat prints 6 significant digits, so a printed Im Z is off by at most 5e-6 relative (mantissa 1.00000);
  the quadrature of the exact uniform-current partial self inductance is converged to < 1e-9.  Frequency 10 Hz: the Cu skin
  depth is 21 mm, 5 x the largest bar side (4 mm), so the current is uniform to the printed digits (FastHenry's L does not
  move with the number of filaments at 10 Hz, test_bar_partial_inductance_against_hoer_love_under_filament_refinement).
* loop vs Grover: see ``test_loop_converges_to_grover``.
* multipole vs direct: 3.3e-4, P4 section 3.1 (order-4 multipole within 3.3e-4 of direct LU on the thin d0 / d1 decks).
"""
from __future__ import annotations

import hashlib
import math
import os
import stat
from pathlib import Path

import pytest
from scipy import integrate
from shapely.geometry import box

from moduleforge.geometry.layout import DC_MINUS, DC_PLUS, PHASE, Die, Layout, Terminal, Trace, arc_wire
from moduleforge.geometry.stack import default_dbc_stack
from moduleforge.solvers import fasthenry_run as R
from moduleforge.solvers.fasthenry import FHLevel, export

MU0 = 4e-7 * math.pi
MM = 1e-3


@pytest.fixture(scope="module")
def real_binary():
    try:
        return R.find_binary()
    except FileNotFoundError:
        pytest.skip("FastHenry is not provisioned (scripts/provision_compute.sh, D0002)")


# ----------------------------------------------------------------------------------------------------- fake binaries
ZC = ("Row 1:  n1  to  n2\nImpedance matrix for frequency = 1e+07 1 x 1\n   0.002  +0.2j \n"
      "Impedance matrix for frequency = 2e+07 1 x 1\n   0.002  +0.4j\n")
L_FAKE_10MHZ = 0.2 / (2 * math.pi * 1e7)


BANNER = "Running FastHenry 3.0wr (29Sep96, mod 031424)"


def fake(tmp_path: Path, *, crashes: int = 0, how: str = "exit", zc: str = ZC, pre: str = "", name: str = "fake_fh",
         banner: str = BANNER) -> Path:
    """Shell script posing as FastHenry: runs ``crashes`` times as a crash ('exit' = exit 139, 'signal' = SIGSEGV; both
    leave a VALID-looking Zc.mat behind, which must never be parsed), then writes ``zc`` and exits 0."""
    cnt = tmp_path / f"{name}.count"
    crash = "exit 139" if how == "exit" else "kill -SEGV $$"
    p = tmp_path / name
    p.write_text(f"""#!/bin/sh
N=$(cat '{cnt}' 2>/dev/null || echo 0); N=$((N+1)); echo $N > '{cnt}'
echo '{banner}'
pwd >> '{tmp_path}/{name}.cwds'; ls >> '{tmp_path}/{name}.ls'
{pre}
cat > Zc.mat <<'EOF'
{zc}EOF
if [ "$N" -le {crashes} ]; then {crash}; fi
echo "Total number of filaments after multipole refine: 17"
exit 0
""")
    p.chmod(p.stat().st_mode | stat.S_IXUSR)
    return p


BAR_1KHZ = ZC.replace("1e+07", "1000").replace("2e+07", "2000")


def bar_zc(l_nh: float) -> str:
    """Zc.mat of a bar with inductance ``l_nh`` at 1 and 2 kHz (R = 0.002 ohm)."""
    return "".join(f"Impedance matrix for frequency = {f} 1 x 1\n   0.002  +{2 * math.pi * f * l_nh * 1e-9:.9e}j\n"
                   for f in (1000, 2000))


# ----------------------------------------------------------------------------------------------------- binary lookup
def test_binary_lookup_order(tmp_path, monkeypatch):
    for d in "abc":
        (tmp_path / d).mkdir()
    a, b, c = (fake(tmp_path / d, name="fasthenry") for d in "abc")
    home = tmp_path / "home"
    (home / ".local" / "bin").mkdir(parents=True)
    (home / ".local" / "bin" / "fasthenry").write_bytes(c.read_bytes())
    (home / ".local" / "bin" / "fasthenry").chmod(0o755)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("PATH", str(tmp_path / "b"))
    monkeypatch.setenv("MF_FASTHENRY_BIN", str(a))
    assert R.find_binary() == a  # 1. MF_FASTHENRY_BIN
    monkeypatch.delenv("MF_FASTHENRY_BIN")
    assert R.find_binary() == b  # 2. PATH
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))
    assert R.find_binary() == home / ".local" / "bin" / "fasthenry"  # 3. ~/.local/bin
    (home / ".local" / "bin" / "fasthenry").chmod(0o644)  # not executable: not found
    with pytest.raises(FileNotFoundError):
        R.find_binary()
    monkeypatch.setenv("MF_FASTHENRY_BIN", str(tmp_path / "nonexistent"))
    with pytest.raises(FileNotFoundError):
        R.find_binary()


# ----------------------------------------------------------------------------------------------------- self-test
def test_self_test_passes_on_the_pinned_build(real_binary):
    rec = R.self_test()
    assert rec["pass"] and rec["binary"] == str(real_binary)
    assert rec["binary_sha256"] == hashlib.sha256(real_binary.read_bytes()).hexdigest()
    assert abs(rec["L_nH_1kHz"] - 5.704) <= R.SELF_TEST_TOL_NH
    assert abs(rec["L_nH_1kHz"] / 5.695 - 1) <= R.SELF_TEST_CLOSED_FORM_TOL
    assert abs(rec["L_nH_1kHz"] - 5.704254) <= R.SELF_TEST_HOER_LOVE_TOL_NH
    assert "FastHenry 3.0wr" in rec["banner"] and "mod 031424" in rec["banner"]


def test_self_test_requires_the_pinned_version_banner(tmp_path):
    good = bar_zc(5.704254)
    assert R.self_test(fake(tmp_path, zc=good))["banner"] == BANNER
    for i, other in enumerate(("Running FastHenry2 3.0 (build x)", "Running FastHenry 3.0wr (29Sep96, mod 999999)", "")):
        with pytest.raises(R.SelfTestError, match="banner"):
            R.self_test(fake(tmp_path, zc=good, banner=other, name=f"other{i}"))


def test_self_test_bound_is_the_exact_hoer_love_value():
    # independent of the adapter: Hoer-Love (1965) partial self L of a 10 x 1 x 1 mm bar from the Ruehli series
    # (5.695 nH, 0.16 % low) is within 1e-3 of the exact value; the recorded 5.704 is within the print rounding of it
    assert abs(R.SELF_TEST_HOER_LOVE_NH - R.SELF_TEST_L_NH) <= 5e-4
    # the constant is the exact value, by this file's own Hoer-Love quadrature (not a comparison of two module constants)
    assert R.SELF_TEST_HOER_LOVE_NH == pytest.approx(bar_self_L(10e-3, 1e-3, 1e-3) * 1e9, abs=1e-6)
    assert R.SELF_TEST_HOER_LOVE_TOL_NH < R.SELF_TEST_TOL_NH  # the exact bound is the tighter one, so it can fire


def test_self_test_hoer_love_bound_fires_inside_the_recorded_bound(tmp_path):
    # 5.7050 nH is within D0002's 1.5e-3 nH of 5.704 but 7.5e-4 nH from the exact value: only the new bound catches it
    with pytest.raises(R.SelfTestError, match="Hoer-Love"):
        R.self_test(fake(tmp_path, zc=bar_zc(5.7050)))
    R.self_test(fake(tmp_path, zc=bar_zc(5.7042), name="ok"))


def test_self_test_raises_on_a_wrong_build_and_on_a_crash(tmp_path):
    wrong = ZC.replace("+0.2j", "+3.6e-5j").replace("+0.4j", "+7.2e-5j").replace("1e+07", "1000").replace("2e+07", "2000")
    # L = 3.6e-5 / (2 pi 1e3) = 5.730 nH: outside D0002's 1.5e-3 nH
    with pytest.raises(R.SelfTestError, match="D0002 recorded"):
        R.self_test(fake(tmp_path, zc=wrong))
    with pytest.raises(R.SelfTestError, match="failed"):
        R.self_test(fake(tmp_path, crashes=1, name="crashing"))


def test_self_test_bar_value_is_pinned_to_the_closed_form():
    # D0002's numbers are consistent with each other: 5.704 nH is +0.16 % from the 5.695 nH closed form
    ruehli = 2e-7 * 0.01 * (math.log(2 * 0.01 / 0.002) + 0.5 + 0.2235 * 0.002 / 0.01) * 1e9
    assert ruehli == pytest.approx(R.SELF_TEST_CLOSED_FORM_NH, abs=5e-4)
    assert abs(R.SELF_TEST_L_NH / R.SELF_TEST_CLOSED_FORM_NH - 1) < R.SELF_TEST_CLOSED_FORM_TOL


# ----------------------------------------------------------------------------------------------------- retry logic
@pytest.mark.parametrize("how", ["exit", "signal"])
def test_multipole_retries_a_crash_and_logs_every_attempt(tmp_path, how):
    b = fake(tmp_path, crashes=3, how=how)
    r = R.solve_deck(".end\n", mode="multipole", binary=b)
    assert r.ok and r.status == "ok" and r.n_attempts == 4
    assert [a.status for a in r.attempts] == ["crash"] * 3 + ["ok"]
    assert [a.n for a in r.attempts] == [1, 2, 3, 4]
    if how == "exit":
        assert [a.exit_code for a in r.attempts[:3]] == [139] * 3
    else:
        assert [a.signal for a in r.attempts[:3]] == [11] * 3
    assert r.L_H[1e7] == pytest.approx(L_FAKE_10MHZ, rel=1e-12) and r.R_ohm[1e7] == pytest.approx(0.002)
    assert r.L_H[2e7] == pytest.approx(L_FAKE_10MHZ, rel=1e-12)  # Im Z doubles with f: L is flat
    assert r.n_filaments_refined == 17
    assert r.args == ["-s", "iterative", "-m", "multi", "-t", "0.0001", "-o", "4"]
    assert r.binary_path == str(b) and r.binary_sha256 == hashlib.sha256(b.read_bytes()).hexdigest()


def test_ten_retries_are_allowed_and_an_eleventh_crash_is_a_failure(tmp_path):
    ok = R.solve_deck(".end\n", binary=fake(tmp_path, crashes=10, name="c10"))
    assert ok.ok and ok.n_attempts == 11  # first run + 10 retries (O004 F1)
    bad = R.solve_deck(".end\n", binary=fake(tmp_path, crashes=11, name="c11"))
    assert not bad.ok and bad.status == "crash" and bad.n_attempts == 11
    assert bad.L_H == {} and bad.R_ohm == {} and bad.Z == {}  # the crashed runs' (valid-looking) Zc.mat was never parsed
    with pytest.raises(R.FastHenryError, match="crash"):
        bad.require_ok()
    with pytest.raises(ValueError):
        R.solve_deck(".end\n", max_retries=11, binary=fake(tmp_path, name="c0"))


def test_direct_mode_never_retries_and_never_falls_back(tmp_path):
    r = R.solve_deck(".end\n", mode="direct", binary=fake(tmp_path, crashes=1))
    assert not r.ok and r.n_attempts == 1 and r.args == ["-s", "ludecomp", "-m", "direct"]
    # a failing multipole run is never re-run with the direct solver
    r = R.solve_deck(".end\n", mode="multipole", max_retries=2, binary=fake(tmp_path, crashes=99, name="always"))
    assert r.n_attempts == 3 and "direct" not in r.args
    assert "FastHenry" in r.log  # the failed run's log is kept, not only the successful one's
    with pytest.raises(ValueError):
        R.mode_args("hybrid")


def test_exit_0_without_both_frequencies_or_with_nan_is_not_a_result(tmp_path):
    one = ZC.split("Impedance matrix for frequency = 2e+07")[0]
    r = R.solve_deck(".end\n", binary=fake(tmp_path, zc=one, name="one"))
    assert not r.ok and r.status == "parse_error" and r.n_attempts == 1  # not retried: exit 0 is not a crash
    r = R.solve_deck(".end\n", binary=fake(tmp_path, zc=ZC.replace("0.002  +0.2j", "nan  nanj"), name="nan"))
    assert not r.ok and r.status == "parse_error"
    r = R.solve_deck(".end\n", binary=fake(tmp_path, zc=ZC.replace("1e+07", "3e+07"), name="wrongf"))
    assert not r.ok and r.status == "parse_error"  # a frequency other than the requested one


def test_timeout_kills_and_is_not_retried(tmp_path):
    b = fake(tmp_path, pre="exec sleep 30")
    r = R.solve_deck(".end\n", binary=b, timeout_s=0.4)
    assert not r.ok and r.status == "timeout" and r.n_attempts == 1 and r.attempts[0].wall_s < 10


def test_memory_watchdog_kills_above_the_cap(tmp_path):
    b = fake(tmp_path, pre="exec sleep 30")
    r = R.solve_deck(".end\n", binary=b, mem_cap_mb=0.5, timeout_s=20)  # any process holds more than 0.5 MB
    if r.attempts and not r.attempts[0].mem_polled:
        pytest.skip("ps cannot see the child (sandbox): the RSS watchdog is blind here")
    assert not r.ok and r.status == "killed_memory" and r.n_attempts == 1 and r.attempts[0].peak_mem_mb > 0.5


def test_every_run_has_its_own_fresh_directory(tmp_path):
    b = fake(tmp_path, crashes=2)
    before = set(os.listdir(Path.cwd()))
    R.solve_deck(".end\n", binary=b)
    cwds = (tmp_path / "fake_fh.cwds").read_text().split()
    assert len(cwds) == 3 and len(set(cwds)) == 3  # a fresh directory per attempt
    assert not any(Path(c).exists() for c in cwds)  # removed afterwards
    # at start only the deck and the adapter's own log: no Zc.mat left over from the crashed attempt before
    assert set(tmp_path.joinpath("fake_fh.ls").read_text().split()) == {"deck.inp", "run.log"}
    assert set(os.listdir(Path.cwd())) == before


def test_dense_memory_screen_has_a_margin(tmp_path):
    b = fake(tmp_path)
    facts = {"direct_mem_est_gb": 1.0, "n_filaments": 100}
    # 1.0 GB = 1024 MB fits a 1300 MB cap, but not with the margin (T0428: peak = 1.24-1.26 x the estimate above 5k filaments)
    r = R.solve_deck(".end\n", mode="direct", facts=facts, mem_cap_mb=1300, binary=b)
    assert not r.ok and r.status == "not_run" and r.attempts == [] and "margin" in r.reason
    assert R.MEM_MARGIN >= 1.26 * 1.02  # covers T0428's worst measured ratio with headroom
    assert R.solve_deck(".end\n", mode="direct", facts=facts, mem_cap_mb=1400, binary=b).ok
    # multipole has no dense estimate: it is limited by the watchdog only
    assert R.solve_deck(".end\n", mode="multipole", facts=facts, mem_cap_mb=1100, binary=b).ok


def test_external_sigkill_is_not_retried(tmp_path):
    # SIGKILL not sent by our watchdog (Linux OOM killer): the same deck is killed again, so one attempt only
    r = R.solve_deck(".end\n", binary=fake(tmp_path, pre="kill -KILL $$", name="oom"))
    assert not r.ok and r.n_attempts == 1 and r.status == "killed_external" and r.attempts[0].signal == 9
    r = R.solve_deck(".end\n", binary=fake(tmp_path, pre="exit 137", name="w137"))  # a wrapper reporting 128 + 9
    assert not r.ok and r.n_attempts == 1 and r.status == "killed_external"


def test_identical_nonzero_exit_twice_is_not_retried_but_a_segfault_still_is(tmp_path):
    r = R.solve_deck(".end\n", binary=fake(tmp_path, pre="exit 1", name="e1"))
    assert not r.ok and r.status == "crash" and r.n_attempts == 2 and [a.exit_code for a in r.attempts] == [1, 1]
    # a deterministic error that changes is still retried until it repeats: 2, 3, 3
    b = fake(tmp_path, pre='[ "$N" -eq 1 ] && exit 2; exit 3', name="e23")
    r = R.solve_deck(".end\n", binary=b)
    assert [a.exit_code for a in r.attempts] == [2, 3, 3]
    # SIGSEGV (the intermittent D0002 crash) is retried through many identical failures
    r = R.solve_deck(".end\n", binary=fake(tmp_path, crashes=5, how="signal", name="segv"))
    assert r.ok and r.n_attempts == 6


def test_zc_with_negative_inductance_or_nonpositive_r_or_a_2x2_matrix_is_a_parse_error(tmp_path):
    for name, zc in (("negl", ZC.replace("+0.2j", "-0.2j")), ("zerol", ZC.replace("+0.4j", "+0.0j")),
                     ("negr", ZC.replace("0.002  +0.2j", "-0.002  +0.2j")), ("zeror", ZC.replace("0.002  +0.2j", "0  +0.2j"))):
        r = R.solve_deck(".end\n", binary=fake(tmp_path, zc=zc, name=name))
        assert not r.ok and r.status == "parse_error" and r.n_attempts == 1, name
    two = ("Impedance matrix for frequency = 1e+07 2 x 2\n   0.002  +0.2j   0.0001 +0.01j\n   0.0001 +0.01j   0.002 +0.2j\n"
           "Impedance matrix for frequency = 2e+07 2 x 2\n   0.002  +0.4j   0.0001 +0.02j\n   0.0001 +0.02j   0.002 +0.4j\n")
    r = R.solve_deck(".end\n", binary=fake(tmp_path, zc=two, name="two"))
    assert not r.ok and r.status == "parse_error"


def test_refined_count_is_parsed_from_the_log():
    assert R.refined_filaments("x\nTotal number of filaments before multipole refine: 8816\n"
                               "Total number of filaments after multipole refine: 8912\n") == 8912
    assert R.refined_filaments("no such line") is None


# ----------------------------------------------------------------------------------------------------- exporter fixes
def test_export_refuses_more_than_two_frequencies_instead_of_dropping_them():
    lay = mini_layout()
    lev = FHLevel(cell_mm=1.0, plane_cell_mm=3.0, wire_n=2)
    with pytest.raises(ValueError, match="at most two"):
        export(lay, lev, freqs=(1e7, 1.5e7, 2e7))
    deck, _ = export(lay, lev, freqs=(1e7, 2e7))
    assert ".freq fmin=10000000 fmax=20000000" in deck


def test_fhlevel_docstring_flags_nh1_as_smoke_test_only():
    assert "SMOKE-TEST" in FHLevel.__doc__ and "nh = 1" in FHLevel.__doc__


# ----------------------------------------------------------------------------------------------------- closed forms
def bar_self_L(length: float, w: float, t: float) -> float:
    """Partial self inductance [H] of a length x w x t bar, uniform current along length (Hoer & Love, J. Res. NBS 69C (1965) 127;
    Ruehli, IBM J. Res. Dev. 16 (1972) 470), by quadrature of Neumann's formula over both volumes:
        L = mu0 / (4 pi) / (w t)^2 * int dV dV' / |r - r'|.
    For two identical boxes the six-fold integral reduces to
    8 int_0^length int_0^w int_0^t (length - x)(w - y)(t - z) / |d| d^3 d;
    the z integral is closed form: int_0^t (t - z) / sqrt(rho^2 + z^2) dz = t asinh(t / rho) - sqrt(rho^2 + t^2) + rho."""
    def f(y, x):
        rho = math.hypot(x, y)
        return (length - x) * (w - y) * (t * math.asinh(t / rho) - math.hypot(rho, t) + rho) if rho > 0 else 0.0
    v, _ = integrate.dblquad(f, 0, length, 0, w, epsabs=0, epsrel=1e-11)
    return MU0 / (4 * math.pi) * 8 * v / (w * t) ** 2


def ruehli_bar(length: float, w: float, t: float) -> float:
    """Ruehli (1972) / Grover closed form for length >> w, t:
    mu0 / (2 pi) length [ln(2 length / (w + t)) + 1/2 + 0.2235 (w + t) / length]."""
    return 2e-7 * length * (math.log(2 * length / (w + t)) + 0.5 + 0.2235 * (w + t) / length)


@pytest.mark.parametrize("length", [0.1, 0.5])
def test_quadrature_reference_matches_ruehli_for_long_thin_bars(length):
    # Ruehli's constant 1/2 is -ln(0.2235) - 1 = 0.4985 rounded (GMD of a square 0.22353 (w + t)): a relative offset of
    # 0.0015 / (ln(2 length / (w + t)) + 1/2) = 3e-4 at length = 0.1 m (w = t = 1 mm), the bound used here; measured
    # 2.0e-4 and 2.4e-4
    w = t = 1e-3
    assert ruehli_bar(length, w, t) / bar_self_L(length, w, t) - 1 == pytest.approx(0.0, abs=3e-4)


def bar_deck(length, w, t, n, f=(10, 20)):
    return (f".units m\n.default sigma=5.8e7\nN1 x=0 y=0 z=0\nN2 x={length} y=0 z=0\nE1 N1 N2 w={w} h={t} nwinc={n} nhinc={n}\n"
            f".external N1 N2\n.freq fmin={f[0]} fmax={f[1]} ndec=3.3219280982\n.end\n")


@pytest.mark.parametrize("dims", [(10e-3, 1e-3, 1e-3), (20e-3, 4e-3, 1e-3), (5e-3, 2e-3, 3e-3)])
def test_bar_partial_inductance_against_hoer_love_under_filament_refinement(real_binary, dims):
    exact = bar_self_L(*dims)
    nfil = []
    for n in (1, 2, 4):  # filaments per side
        r = R.solve_deck(bar_deck(*dims, n), mode="direct", freqs=(10, 20)).require_ok()
        nfil.append(r.n_filaments_refined)
        assert r.L_H[10] / exact - 1 == pytest.approx(0.0, abs=5e-6), (dims, n)
        assert r.L_H[20] == pytest.approx(r.L_H[10], rel=1e-5)  # no frequency dependence at 10-20 Hz
        # DC resistance length / (sigma w t) (Zc.mat prints 6 digits)
        assert r.R_ohm[10] == pytest.approx(dims[0] / (5.8e7 * dims[1] * dims[2]), rel=5e-6)
    assert nfil == sorted(nfil) and nfil[-1] > 4 * nfil[0]  # the refinement really refined


def grover_rectangle(a: float, b: float, s: float) -> float:
    """Grover, Inductance Calculations (1946), rectangle of sides a, b, d = sqrt(a^2 + b^2), made of conductors whose
    cross-section has geometric mean distance R (square of side s: R = 0.44705 s, Grover's tables):
        L = mu0 / pi [a ln(2a / R) + b ln(2b / R) - 2 (a + b) + 2 d - a ln((a + d) / b) - b ln((b + d) / a)]
    (R replaces the radius-plus-internal-inductance term: uniform current, no skin effect)."""
    d = math.hypot(a, b)
    R_ = 0.44705 * s
    return 4e-7 * (a * math.log(2 * a / R_) + b * math.log(2 * b / R_) - 2 * (a + b) + 2 * d
                   - a * math.log((a + d) / b) - b * math.log((b + d) / a))


def loop_deck(a, b, s, n):
    seg = f"w={s} h={s} nwinc={n} nhinc={n}"
    return (f".units m\n.default sigma=5.8e7\nN1a x=0 y=0 z=0\nN1b x=0 y=0 z=0\nN2 x={a} y=0 z=0\nN3 x={a} y={b} z=0\n"
            f"N4 x=0 y={b} z=0\nE1 N1a N2 {seg}\nE2 N2 N3 {seg}\nE3 N3 N4 {seg}\nE4 N4 N1b {seg}\n.external N1a N1b\n"
            ".freq fmin=10 fmax=20 ndec=3.3219280982\n.end\n")


def test_loop_converges_to_grover(real_binary):
    # 20 x 10 mm centre-line rectangle of square-section conductors, 10 Hz (uniform current).  Grover's formula is for
    # thin conductors: FastHenry's bars overlap at the corners (and the formula uses centre-line spacings), a first-order
    # effect in s / b that vanishes as s -> 0.  The tolerance 0.15 s / b is a bound on the first-order coefficient: the
    # same sweep, run before this test was written, gave (error / (s / b)) = 0.12, 0.097, 0.082, 0.071 for s / b = 0.08,
    # 0.04, 0.02, 0.01, i.e. below 0.15 and falling, as O(s ln s) corner terms do.  The test also asserts the error falls
    # with s, so the closed form is approached rather than bracketed.
    a, b = 20e-3, 10e-3
    errs = []
    for s in (0.4e-3, 0.2e-3, 0.1e-3):
        r = R.solve_deck(loop_deck(a, b, s, 1), mode="direct", freqs=(10, 20)).require_ok()
        err = r.L_H[10] / grover_rectangle(a, b, s) - 1
        assert 0 < err <= 0.15 * s / b, (s, err)
        errs.append(err)
    assert errs[0] > errs[1] > errs[2] and errs[2] < 1e-3
    r2 = R.solve_deck(loop_deck(a, b, 0.2e-3, 2), mode="direct", freqs=(10, 20)).require_ok()
    assert r2.L_H[10] == pytest.approx(R.solve_deck(loop_deck(a, b, 0.2e-3, 1), mode="direct", freqs=(10, 20)).L_H[10],
                                       rel=1e-4)  # filament refinement does not move the uniform-current value


# ----------------------------------------------------------------------------------------------------- end to end
def mini_layout() -> Layout:
    """DC+ / PHASE / DC- traces of a 5 mm wide substrate on the 1 mm lattice, one 2 x 2 mm die per switch, two wires each."""
    st = default_dbc_stack()
    zt = st.z_top("top_cu")
    traces = [Trace(DC_PLUS, box(0, 0, 5 * MM, 2 * MM)), Trace(PHASE, box(0, 3 * MM, 5 * MM, 7 * MM)),
              Trace(DC_MINUS, box(0, 8 * MM, 5 * MM, 10 * MM))]
    dies, wires = [], []
    for sw, cy, land, net in (("HS", 1.0, 3.5, PHASE), ("LS", 6.0, 9.0, DC_MINUS)):
        d = Die(2 * MM, cy * MM, 2 * MM, 2 * MM, sw, {"source": (1.5 * MM, (cy - .5) * MM, 2.5 * MM, (cy + .5) * MM)})
        dies.append(d)
        for x in (1.5, 2.5):
            wires.append(arc_wire((x * MM, cy * MM), (x * MM, land * MM), zt + d.attach_thickness + d.thickness, zt,
                                  1.0 * MM, 0.3 * MM, net))
    terms = {DC_PLUS: Terminal(DC_PLUS, 0.5 * MM, 0.5 * MM, MM, MM), DC_MINUS: Terminal(DC_MINUS, 4.5 * MM, 9.5 * MM, MM, MM)}
    return Layout("mini", 1, box(0, 0, 5 * MM, 10 * MM), traces, dies, wires, terms,
                  box(-2 * MM, -2 * MM, 7 * MM, 12 * MM), st)


@pytest.mark.parametrize("nh", [1, 3])
def test_layout_end_to_end_multipole_agrees_with_direct(real_binary, nh):
    from moduleforge.solvers.fasthenry_run import solve_layout
    lev = FHLevel(cell_mm=1.0, plane_cell_mm=3.0, nh_trace=nh, nh_plane=nh, wire_n=2)
    m = solve_layout(mini_layout(), lev, mode="multipole").require_ok()
    d = solve_layout(mini_layout(), lev, mode="direct").require_ok()
    for res in (m, d):
        assert set(res.L_H) == {1e7, 2e7} and set(res.R_ohm) == {1e7, 2e7}
        assert all(math.isfinite(v) and v > 0 for v in (*res.L_H.values(), *res.R_ohm.values()))
        assert res.L_H[1e7] == pytest.approx(res.Z[1e7].imag / (2 * math.pi * 1e7), rel=1e-12)
        assert 1e-9 < res.L_H[1e7] < 1e-7  # a few nH for a 10 mm loop, not a unit error
        assert res.nh_trace == nh and res.nh_plane == nh  # recorded beside L (review T0418)
        assert res.n_filaments_refined >= res.n_filaments_exporter > 0  # FastHenry's count is after its own refinement
        assert res.binary_sha256 == hashlib.sha256(real_binary.read_bytes()).hexdigest()
        assert res.deck_sha256 == m.deck_sha256
    # P4 section 3.1: order-4 multipole within 3.3e-4 of direct LU (same bound for R: the GMRES tolerance 1e-4 acts on both)
    for f in (1e7, 2e7):
        assert m.L_H[f] / d.L_H[f] - 1 == pytest.approx(0.0, abs=3.3e-4)
        assert m.R_ohm[f] / d.R_ohm[f] - 1 == pytest.approx(0.0, abs=3.3e-4)
    assert m.attempts[-1].status == "ok" and m.n_attempts <= 1 + R.MAX_RETRIES


def test_distributed_die_deck_is_refused_for_multipole(real_binary):
    lev = FHLevel(cell_mm=1.0, plane_cell_mm=3.0, wire_n=2)
    with pytest.raises(R.FastHenryError, match="distributed"):
        R.solve_layout(mini_layout(), lev, mode="multipole", die_model="distributed")
