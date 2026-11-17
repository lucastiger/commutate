# D0026 — O008 before E011's registration: one parameter set (columns, slots, die rows, landing lines; no foot offsets); the proxy frozen in-domain with reach jumps; development rows from the code that will be frozen. The search budget and the VM shape stay open
Date: 2026-11-17 · Status: accepted (drafted by the founder session; accepted as drafted) · Decider: founder · Relates to: O008 (scope_in, F-nulls, F5), I0222, I0226, I0234, I0205; T0376, T0378, T0379, T0380, T0382, T0413, T0421, T0422, T0425, T0426, T0430-T0432, T0437

## Context
- These decisions were taken in founder sessions on 2026-11-16 and 2026-11-17. They are recorded in O008's state log,
  in merge notes (I0222, I0226) and in task briefs, which blinded reviewers do not all see.
- The L1 development probe (research/notes/o008-control-probe.md) reached 0.898 (2D_Case_2R) and 0.628 (2D_Case_4)
  of the twins at L1. Reviews T0421 and T0422 of T0379 found the probe's 2R optimum outside the search's domain: it
  widens the low-side die-row gap past the cap of the minimum gap plus 2 mm.

## Decision
1. **One parameter set** (2026-11-16). The search, the designer proxy and every null move
   Params.NAMES[twin.WALK_FIRST:twin.WALK_END] (indices 4-39: columns, slots, die rows, landing lines). That is O008's
   scope_in "one parameter set ... (columns, slots, die rows, landing lines)". The four power-wire foot offsets
   foot_{HS,LS}_land_{du,dv} are not in it (T0378 merge I0222, T0379 merge I0226). Each row's provenance records
   movable_indices().
2. **The proxy rule** (2026-11-16 20:30 UTC). E011 freezes control.proxy_descent with reach=True, which means
   in-domain moves plus the reach jumps, with min gain MIN_GAIN_H = 1e-12 H.
   - It reaches an L1 ratio of 0.914 on 2D_Case_2R (25 steps, 0.9138, T0382) and 0.653 on 2D_Case_4. The probe's deeper
     optimum lies outside the search's domain.
   - The null margins (b), (d), and (d) compaction on 2R in particular, and the joint operating characteristic are
     re-measured against this proxy on development draws (I0205). T0376's figures against the probe proxy do not
     carry over.
3. **Development rows come from the code that will be frozen** (2026-11-17, I0234).
   - Builder task T0437 tags the seed streams in control.py first: numpy's SeedSequence drops trailing zero words, so
     untagged streams could coincide. The same task fixes the nulls (T0425, T0426) and pins the proxy in tests.
   - T0382's third attempt then reruns the development L1 run from scratch, with code-stamped checkpoints, and writes
     the freeze hashes and the complete I0205 job list.
4. **Replans declined** (2026-11-16). The replan set off by T0376's merge (T0413) was stopped. The approved plan
   T0378-T0383 stands, with T0437 and T0382's rescoped attempt added on 2026-11-17.

## Open, not decided here
- **The search's L1 budget** (2000 evaluations). On 2R, T0382's first attempt was still improving in the last 10 % of
  it. The founder decides before registration from T0382's improvement curve per layout; the budget is frozen in
  E011's spec (F5).
- **The registered run's VM shape and timeout.** T0382 modelled 2D_Case_4's 0.25 mm solves at about 25 GB each, so
  2-3 run at once on n2d-custom-8-81920. That gives about 91-136 h of makespan against timeout_min = 120 h, and about
  $80-105, which is well above the plan's $10-25 VM for O008. The founder decides with I0205's development results.

## Consequences
- E011's spec cites D0026 for items 1-3. The open items are recorded as amendments of this record before
  registration.
