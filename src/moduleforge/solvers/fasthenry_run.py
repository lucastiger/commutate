"""FastHenry run adapter (O004, D0002, D0004): runs the decks of ``moduleforge.solvers.fasthenry`` with the pinned binary.

Ported from ``research/scripts/o006_p4/run_fh.py`` (O006 pilot P4, T0155).  FastHenry 3.0wr is an external, provisioned
executable (D0002: built by ``scripts/provision_compute.sh``, never fetched or built here).  This module

* finds it through ``MF_FASTHENRY_BIN``, then ``PATH``, then ``~/.local/bin`` and records its path and sha256 in every
  result (``binary_info``);
* ``self_test()`` runs D0002's self-test bar (10 x 1 x 1 mm Cu bar at 1 kHz) and raises ``SelfTestError`` unless the
  result is D0002's recorded 5.704 nH (within ``SELF_TEST_TOL_NH``) and within ``SELF_TEST_CLOSED_FORM_TOL`` of the
  5.695 nH closed form;
* runs every solve in a fresh temporary directory.  A run counts only if the process exits 0 and Zc.mat parses with
  every expected frequency; a crashed run's Zc.mat is never read (D0002: the pinned build segfaults intermittently);
* multipole mode (``-s iterative -m multi -t TOL -o ORDER``) retries a crash up to ``MAX_RETRIES`` = 10 times (O004 F1)
  and logs every attempt.  There is NO direct-solver fallback for a large deck: ``mode='direct'`` (``-s ludecomp -m
  direct``) is a solver check on thin decks and is refused when its dense-memory estimate, with a margin, exceeds the cap;
* a watchdog polls the child's resident memory and kills it above ``mem_cap_mb`` or after ``timeout_s`` (a killed run is
  not retried: the same deck would be killed again);
* returns R and L = Im(Z) / (2 pi f) at each frequency (10 and 20 MHz for the exporter's decks).

Fixes from the T0384 review (T0417 / T0418): the exporter counts filaments before FastHenry's own 'multipole refine'
(8816 -> 8912 on Case 4's distributed deck), so the memory screen multiplies the exporter's estimate by ``MEM_MARGIN`` and
the result records the post-refinement count FastHenry reports (``n_filaments_refined``); the result also records the
thickness filaments ``nh_trace`` / ``nh_plane`` beside L, because nh = 1 (the ``FHLevel`` default) is a smoke-test level.

    from moduleforge.solvers.fasthenry import FHLevel
    from moduleforge.solvers.fasthenry_run import solve_layout
    res = solve_layout(layout, FHLevel(cell_mm=0.5, nh_trace=3, nh_plane=3), mode="multipole")
    res.L_H[1e7], res.R_ohm[1e7], res.attempts, res.binary_sha256
"""
from __future__ import annotations

import ctypes
import ctypes.util
import hashlib
import math
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

from moduleforge.solvers.fasthenry import FREQS_HZ, FHLevel, export, parse_zc

MAX_RETRIES = 10  # O004 F1: a crashed multipole run is re-run up to 10 times
MEM_MARGIN = 1.10  # review T0417: the exporter's filament count is before 'multipole refine' (8816 -> 8912 = +1.1 %)
MULTIPOLE_ORDER = 4  # P4 section 3.1: order 4 read within 3.3e-4 of direct LU (FastHenry's default order 2: 7.8e-3)
MULTIPOLE_TOL = 1e-4  # P4's GMRES tolerance
MODES = ("multipole", "direct")
FREQ_MATCH_RTOL = 1e-4  # a parsed frequency must match the requested one to this relative tolerance

# D0002 self-test bar: 10 x 1 x 1 mm Cu, 1 kHz.  Recorded: 5.704 nH on the pinned build; closed form 5.695 nH,
# mu0/(2 pi) l [ln(2 l / (w + t)) + 1/2 + 0.2235 (w + t) / l] (Ruehli, IBM J. Res. Dev. 16 (1972) 470; Grover 1946).
SELF_TEST_DECK = (".units m\n.default sigma=5.8e7\nN1 x=0 y=0 z=0\nN2 x=0.010 y=0 z=0\n"
                  "E1 N1 N2 w=0.001 h=0.001 nwinc=1 nhinc=1\n.external N1 N2\n"
                  ".freq fmin=1e3 fmax=2e3 ndec=3.3219280982\n.end\n")
SELF_TEST_FREQS_HZ = (1.0e3, 2.0e3)
SELF_TEST_L_NH = 5.704  # D0002, pinned build (printed to 4 significant digits)
SELF_TEST_CLOSED_FORM_NH = 5.695  # D0002
# The recorded value is printed to 3 decimals (rounding 5e-4 nH) and Zc.mat to 6 significant digits; P4's check allowed
# 1.5e-3 nH.  The closed form is an approximation (D0002: the build is +0.16 % from it); 0.3 % (about twice that) keeps
# the check from passing a build that is wrong in the first digit.
SELF_TEST_TOL_NH = 1.5e-3
SELF_TEST_CLOSED_FORM_TOL = 3e-3


class FastHenryError(RuntimeError):
    """The adapter could not produce a trusted FastHenry result."""


class SelfTestError(FastHenryError):
    """D0002's self-test bar did not reproduce."""


# ------------------------------------------------------------------------------------------------------ the binary
def find_binary() -> Path:
    """The provisioned binary: ``MF_FASTHENRY_BIN``, then ``PATH``, then ``~/.local/bin`` (D0002).  Never downloads."""
    cands = (os.environ.get("MF_FASTHENRY_BIN"), shutil.which("fasthenry"), str(Path.home() / ".local" / "bin" / "fasthenry"))
    for c in cands:
        if c and Path(c).is_file() and os.access(c, os.X_OK):
            return Path(c)
    raise FileNotFoundError("FastHenry is not provisioned (scripts/provision_compute.sh, D0002); set MF_FASTHENRY_BIN")


def binary_info(binary: str | os.PathLike | None = None) -> dict:
    """``{'path', 'sha256'}`` of the binary (resolved when ``binary`` is None)."""
    b = Path(binary) if binary is not None else find_binary()
    return {"path": str(b), "sha256": hashlib.sha256(b.read_bytes()).hexdigest()}


# ------------------------------------------------------------------------------------------------------ results
@dataclass
class Attempt:
    """One process run: ``status`` in ok / crash / parse_error / killed_memory / timeout."""

    n: int
    status: str
    wall_s: float
    peak_mem_mb: float
    cpu_s: float
    exit_code: int | None = None
    signal: int | None = None
    log_tail: str = ""
    mem_polled: bool = False  # False: the RSS poll (ps) saw nothing (e.g. inside a sandbox), so only ru_maxrss limits memory


@dataclass
class FHResult:
    ok: bool
    status: str  # ok / crash (retries exhausted) / parse_error / killed_memory / timeout / not_run
    mode: str
    args: list[str]
    freqs_hz: tuple[float, ...]
    R_ohm: dict[float, float]
    L_H: dict[float, float]
    Z: dict[float, complex]
    attempts: list[Attempt]
    binary_path: str
    binary_sha256: str
    deck_sha256: str
    n_filaments_exporter: int | None = None  # the exporter's count, BEFORE FastHenry's 'multipole refine' (review T0417)
    n_filaments_refined: int | None = None  # FastHenry's own 'after multipole refine' count, parsed from its log
    nh_trace: int | None = None  # review T0418: record the thickness filaments beside L (nh = 1 is smoke-test only)
    nh_plane: int | None = None
    reason: str = ""
    facts: dict = field(default_factory=dict)

    @property
    def n_attempts(self) -> int:
        return len(self.attempts)

    def require_ok(self) -> FHResult:
        if not self.ok:
            raise FastHenryError(f"FastHenry run {self.status} after {self.n_attempts} attempt(s): {self.reason}")
        return self


# ------------------------------------------------------------------------------------------------------ one process
class _TaskInfo(ctypes.Structure):  # struct proc_taskinfo of <sys/proc_info.h> (96 bytes)
    _fields_ = [(n, ctypes.c_uint64) for n in ("pti_virtual_size", "pti_resident_size", "pti_total_user", "pti_total_system",
                                               "pti_threads_user", "pti_threads_system")] + [
        (n, ctypes.c_int32) for n in ("pti_policy", "pti_faults", "pti_pageins", "pti_cow_faults", "pti_messages_sent",
                                      "pti_messages_received", "pti_syscalls_mach", "pti_syscalls_unix", "pti_csw",
                                      "pti_threadnum", "pti_numrunning", "pti_priority")]


def _rss_mb(pid: int) -> float:
    """Resident set of ``pid`` in MB, 0.0 when it cannot be read.  macOS: libproc (works where ``ps`` is blocked by a
    sandbox); Linux: /proc/<pid>/statm; otherwise ``ps``."""
    try:
        if sys.platform == "darwin":
            lib = ctypes.CDLL(ctypes.util.find_library("proc"))
            ti = _TaskInfo()
            if lib.proc_pidinfo(pid, 4, 0, ctypes.byref(ti), ctypes.sizeof(ti)) == ctypes.sizeof(ti):  # PROC_PIDTASKINFO
                return ti.pti_resident_size / 2**20
        elif sys.platform.startswith("linux"):
            return int(Path(f"/proc/{pid}/statm").read_text().split()[1]) * os.sysconf("SC_PAGE_SIZE") / 2**20
        out = subprocess.run(["ps", "-o", "rss=", "-p", str(pid)], capture_output=True, text=True, timeout=5).stdout
        return float(out.strip() or 0) / 1024
    except Exception:
        return 0.0


_REFINED_RE = re.compile(r"Total number of filaments after multipole refine:\s*(\d+)")


def refined_filaments(log: str) -> int | None:
    """FastHenry's reported filament count after 'multipole refine' (None when its log has no such line)."""
    m = _REFINED_RE.search(log)
    return int(m.group(1)) if m else None


def _run_once(binary: str, deck: str, args: list[str], freqs: tuple[float, ...], timeout_s: float, mem_cap_mb: float,
              n: int, poll_s: float = 0.02) -> tuple[Attempt, dict[float, complex], str]:
    """One run in a fresh temporary directory.  Zc.mat is read only after exit code 0 (D0002)."""
    d = Path(tempfile.mkdtemp(prefix="fh_", dir=os.environ.get("TMPDIR")))
    try:
        (d / "deck.inp").write_text(deck)
        t0 = time.perf_counter()
        with open(d / "run.log", "w") as log:
            p = subprocess.Popen([binary, "deck.inp", *args], cwd=d, stdout=log, stderr=subprocess.STDOUT)
            peak_poll, killed, ru, status_code, next_ps, polled = 0.0, None, None, None, 0.0, False
            while True:
                pid, st, ru = os.wait4(p.pid, os.WNOHANG)
                if pid == p.pid:
                    status_code = st
                    break
                el = time.perf_counter() - t0
                if killed is None:
                    if el >= next_ps:  # ps is slow: poll memory about every 0.25 s, the clock every poll_s
                        rss = _rss_mb(p.pid)
                        peak_poll = max(peak_poll, rss)
                        polled = polled or rss > 0
                        next_ps = el + 0.25
                        if rss > mem_cap_mb:
                            killed = "killed_memory"
                    if killed is None and el > timeout_s:
                        killed = "timeout"
                    if killed:
                        p.send_signal(signal.SIGKILL)
                time.sleep(poll_s)
        p.returncode = 0  # reaped by wait4
        wall = time.perf_counter() - t0
        text = (d / "run.log").read_text(errors="replace")
        # ru_maxrss: bytes on macOS, kilobytes on Linux
        peak = max(ru.ru_maxrss / (2**20 if os.uname().sysname == "Darwin" else 2**10), peak_poll)
        att = Attempt(n=n, status="ok", wall_s=wall, peak_mem_mb=peak, cpu_s=ru.ru_utime + ru.ru_stime, log_tail=text[-600:],
                      mem_polled=polled)
        z: dict[float, complex] = {}
        if killed:
            att.status = killed
        elif os.WIFSIGNALED(status_code):
            att.status, att.signal = "crash", os.WTERMSIG(status_code)
        elif os.WEXITSTATUS(status_code) != 0:
            att.status, att.exit_code = "crash", os.WEXITSTATUS(status_code)
        else:
            att.exit_code = 0
            zc = d / "Zc.mat"
            z = parse_zc(zc.read_text()) if zc.exists() else {}
            if not _freqs_match(z, freqs):
                att.status = "parse_error"
        return att, (z if att.status == "ok" else {}), text
    finally:
        shutil.rmtree(d, ignore_errors=True)


def _freqs_match(z: dict[float, complex], freqs: tuple[float, ...]) -> bool:
    return len(z) == len(freqs) and all(
        any(abs(f - g) <= FREQ_MATCH_RTOL * g for f in z) for g in freqs) and all(math.isfinite(v.real) and math.isfinite(v.imag) for v in z.values())


def mode_args(mode: str, order: int = MULTIPOLE_ORDER, tol: float = MULTIPOLE_TOL) -> list[str]:
    if mode == "direct":
        return ["-s", "ludecomp", "-m", "direct"]
    if mode == "multipole":
        return ["-s", "iterative", "-m", "multi", "-t", f"{tol:g}", "-o", str(int(order))]
    raise ValueError(f"mode must be one of {MODES}")


# ------------------------------------------------------------------------------------------------------ solve
def solve_deck(deck: str, *, mode: str = "multipole", freqs: tuple[float, ...] = FREQS_HZ, order: int = MULTIPOLE_ORDER,
               tol: float = MULTIPOLE_TOL, max_retries: int = MAX_RETRIES, timeout_s: float = 3600.0,
               mem_cap_mb: float = 6000.0, facts: dict | None = None, binary: str | os.PathLike | None = None,
               ) -> FHResult:
    """Run one deck.  ``mode='multipole'`` retries a crash up to ``max_retries`` (<= ``MAX_RETRIES``) times; ``'direct'``
    runs once.  ``facts`` (the exporter's) enables the dense-memory screen of direct mode and the recorded ``nh_*`` / counts.
    ``freqs`` are the frequencies the deck's ``.freq`` line must produce (all of them must parse)."""
    if not isinstance(max_retries, int) or isinstance(max_retries, bool) or not 0 <= max_retries <= MAX_RETRIES:
        raise ValueError(f"max_retries must be an int in [0, {MAX_RETRIES}]")
    args = mode_args(mode, order, tol)
    freqs = tuple(sorted(float(f) for f in freqs))
    b = binary_info(binary)
    facts = facts or {}
    lev = facts.get("level", {})
    base = dict(mode=mode, args=args, freqs_hz=freqs, binary_path=b["path"], binary_sha256=b["sha256"],
                deck_sha256=hashlib.sha256(deck.encode()).hexdigest(), n_filaments_exporter=facts.get("n_filaments"),
                nh_trace=lev.get("nh_trace"), nh_plane=lev.get("nh_plane"), facts=facts)
    est = facts.get("direct_mem_est_gb")
    if mode == "direct" and est is not None and est * MEM_MARGIN * 1024 > mem_cap_mb:
        return FHResult(ok=False, status="not_run", R_ohm={}, L_H={}, Z={}, attempts=[], **base,
                        reason=f"estimated dense memory {est:.2f} GB x {MEM_MARGIN} margin > cap {mem_cap_mb / 1024:.2f} GB")
    attempts: list[Attempt] = []
    refined = None
    z: dict[float, complex] = {}
    for n in range(1, (max_retries if mode == "multipole" else 0) + 2):
        att, z, text = _run_once(str(b["path"]), deck, args, freqs, timeout_s, mem_cap_mb, n)
        attempts.append(att)
        refined = refined_filaments(text) or refined
        if att.status != "crash":  # ok, parse_error, killed_memory, timeout: a retry would repeat it
            break
    last = attempts[-1]
    if last.status != "ok":
        return FHResult(ok=False, status=last.status, R_ohm={}, L_H={}, Z={}, attempts=attempts, **base,
                        n_filaments_refined=refined,
                        reason=f"last attempt {last.status} (exit {last.exit_code}, signal {last.signal}): {last.log_tail[-200:]!r}")
    zs = {g: next(v for f, v in z.items() if abs(f - g) <= FREQ_MATCH_RTOL * g) for g in freqs}
    return FHResult(ok=True, status="ok", R_ohm={f: v.real for f, v in zs.items()},
                    L_H={f: v.imag / (2 * math.pi * f) for f, v in zs.items()}, Z=zs, attempts=attempts, **base,
                    n_filaments_refined=refined)


def solve_layout(layout, lev: FHLevel, *, mode: str = "multipole", die_model: str = "short",
                 terminal_model: str = "point", title: str = "", **kw) -> FHResult:
    """Export ``layout`` at level ``lev`` (``moduleforge.solvers.fasthenry.export``) and solve it at 10 and 20 MHz."""
    deck, facts = export(layout, lev, FREQS_HZ, title, die_model=die_model, terminal_model=terminal_model)
    if mode == "multipole" and facts.get("solver_notes") and die_model == "distributed":
        raise FastHenryError("the distributed-die deck crashes the multipole solver (review T0409): " + facts["solver_notes"][0][:120])
    return solve_deck(deck, mode=mode, freqs=FREQS_HZ, facts=facts, **kw)


def self_test(binary: str | os.PathLike | None = None) -> dict:
    """D0002's self-test bar: 10 x 1 x 1 mm Cu at 1 kHz, 5.704 nH recorded on the pinned build, 5.695 nH closed form.
    Returns the record (binary path and sha256 included); raises ``SelfTestError`` otherwise."""
    r = solve_deck(SELF_TEST_DECK, mode="direct", freqs=SELF_TEST_FREQS_HZ, timeout_s=60, mem_cap_mb=1000, binary=binary)
    if not r.ok:
        raise SelfTestError(f"self-test run failed: {r.status}: {r.reason}")
    L_nh = r.L_H[1.0e3] * 1e9
    rec = {"binary": r.binary_path, "binary_sha256": r.binary_sha256, "L_nH_1kHz": L_nh, "recorded_nH": SELF_TEST_L_NH,
           "closed_form_nH": SELF_TEST_CLOSED_FORM_NH, "pass": True}
    if abs(L_nh - SELF_TEST_L_NH) > SELF_TEST_TOL_NH:
        raise SelfTestError(f"self-test L = {L_nh:.4f} nH, D0002 recorded {SELF_TEST_L_NH} nH (tolerance {SELF_TEST_TOL_NH} nH)")
    if abs(L_nh / SELF_TEST_CLOSED_FORM_NH - 1) > SELF_TEST_CLOSED_FORM_TOL:
        raise SelfTestError(f"self-test L = {L_nh:.4f} nH is not within {SELF_TEST_CLOSED_FORM_TOL:.1%} of the "
                            f"{SELF_TEST_CLOSED_FORM_NH} nH closed form")
    return rec
