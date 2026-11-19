# D0028 — FastHenry build: one source fix for the matStats overflow behind the Linux crash and D0002's intermittent crash
Date: 2026-11-19 · Status: proposed (drafted by the founder session) · Decider: founder · Amends: D0002 (build; scope of "unmodified tool") · Relates to: O004 (F7(a), E004), I0209

## Context
- O004's FastHenry measurement burst (2026-11-19, e2-highmem-8, Linux x86-64, gcc) crashed every deck it ran, on
  every attempt, with SIGSEGV just after "Forming sparse matrix preconditioner":
  - k0_nh5: case4_base, standin_compound and dev03_trace_width, 6 or more attempts each.
  - k1_nh5: dev03_trace_width and standin_compound, up to 11 attempts each.
  The same k0 decks complete on the Mac (case4_base k0_nh5: 1115 s, 3.0 GB, 24.30 nH at 10 MHz;
  research/o004_f7/fh_local_probe.json). The k0_nh5 deck is byte-identical on both hosts (sha256 c786df44...).
- An AddressSanitizer build of the pinned tarball on the Mac (clang -O1 -fsanitize=address) stops at the same point on
  the 14 436-filament k0_nh1 deck: a heap-buffer-overflow READ in `matStats` (src/sparse/spBuild.c:526), called from
  `indPrecond` (src/fasthenry/Precond.c:773). The overflowed buffer is the 40-byte `spm` wrapper from `matCreate`
  (src/fasthenry/solver_sparse.c:46).
- The cause: `matStats` in spBuild.c expects the sparse package's own `MatrixPtr`, but FastHenry passes it the `spm`
  wrapper. It reads `Size` and `ElementHashTab` from memory past the wrapper's end, then dereferences that pointer.
  - On macOS that memory has been zero: every Mac log prints "matsize 0, nonzero 0 recalls 0", so nothing is
    dereferenced.
  - Under glibc it holds a live non-null value, so the process segfaults.
  - The stdout buffer is lost in the crash, which is why the VM logs end before the "Block A runtime" line.
  - The values feed only the "Precond build time" printf. No computed quantity depends on them.
- D0002's known issue "intermittent crash" (pin-con7, about 1 run in 8, root cause unknown) has the same signature.
  Repeat runs of pin-con7 on the Mac (2026-11-19): the unpatched binary crashed in 13 of 40 runs (exit 139, empty
  Zc.mat), the patched binary in 0 of 40. All 67 completed runs wrote the same Zc.mat (sha256 f36d4e21...).
- Both files the fix touches permit modification: Whiteley Research's MIT terms (solver_sparse.c), and Kundert/UC
  Berkeley's "Permission to use, copy, modify, and distribute" (spBuild.c).

## Decision
1. **Provisioning applies one source fix to the pinned tarball before `make all`.** It renames spBuild.c's `matStats`
   to `spMatStats`, and adds to solver_sparse.c a `matStats` that unwraps the `spm` and calls `spMatStats` on its
   `matrix`. `scripts/provision_compute.sh` applies it as an anchored edit that stops the build if either anchor does
   not occur exactly once. The tarball, its sha256, the compatibility flags, the bundled Sparse solver and KLU/MKL off
   are unchanged.
2. **D0002's license acceptance extends to this patched build,** on D0002's other terms: internal research use as a
   separate executable, never vendored into this repository, linked, imported or redistributed. The repository
   stores no FastHenry source; the edit names only two function signatures.
3. **The self-test also confirms the fix is in the binary.** The 10 mm bar runs through the same preconditioner path.
   The patched build prints "matsize 1"; the unpatched build prints "matsize 0". Provisioning fails if the line does
   not report a matsize of at least 1.
4. **Binaries.** The Mac arm64 patched build is sha256 `efe594de72daaa1a02713f94852d062e52d9c4fb9f2ec9cb9bf8989fbb56e3d4`
   (the unpatched rebuild reproduces the installed `eaa6d6fc...` exactly). The Linux x86-64 sha256 is recorded by the
   next VM self-test. A single binary pin cannot hold across platforms. E004's draft pin
   (`config.solve.fasthenry.pinned_binary_sha256`) must become a per-platform pin, or a pin on tarball plus fix with
   each host's binary sha256 recorded. That is an E004 design change, made before registration.

## Consequences
- O004's FastHenry k0/k1 measurement can run on burst VMs; the crashed burst is rerun after this lands.
- Results are unchanged. On the 14 436-filament Case 4 deck, the patched and unpatched Mac builds write a
  byte-identical Zc.mat (25.56 nH at 10 MHz, as research/o004_f7/fh_local_probe.json). The patched AddressSanitizer
  build runs that deck to the end with no further memory error and the same Zc.mat. Earlier FastHenry results (crashed runs were never parsed, D0002) stand.
- The Mac binary is rebuilt with `scripts/provision_compute.sh --force`.
- Any further change of pin, build or solver package is still a new decision (D0002).
