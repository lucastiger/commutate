# Capability brief, draft for the founder (plan section 10, step 2)

Drafted by the founder session, 2026-11-15. Edit before sending. It states only recorded claims (`project/claims/C002.yaml`,
`project/claims/C004.yaml`, both supported) with their recorded limits, and makes no headroom claim (none before O009).
The "In progress" items are plan targets, not results. Everything below the line is the text to send.

---

# Commutate: re-layout of wire-bonded SiC power modules

## The problem
When a power module moves to a new die generation, a second-source die or a different die count, the substrate has to
be re-laid out inside the same housing. Loop inductance, current sharing between paralleled dies and junction
temperature all change, and each layout iteration costs a round of manual design and field-solver runs.

## What a pilot delivers (planned; first pilots early 2027)
For one of your existing half-bridge modules and your new dies:
- 3-5 ranked re-layouts inside the same housing;
- for each, loop inductance from a converged field solver, die-average junction temperature and current sharing, each
  with an uncertainty band, and a design-rule report;
- Q3D and Icepak files, so you verify every result in your own flow.

Your files stay under NDA and are not sent to any AI service unless you agree.

## What is verified today
- **Fast inductance model.** It ranks wire-bonded half-bridge layouts on a single DBC substrate (2-6 parallel dies per
  switch) by commutation-loop inductance at 20 MHz consistently with a converged reference solver, in under 50 ms per
  layout on one CPU core (about 25 ms measured), so a search can screen thousands of candidates. Limits: the ranking is
  reliable for layouts whose inductances differ by about 5 % or more; it is verified on one DBC stack (Al2O3 0.38 mm,
  0.3 mm Cu); its absolute values run 5-14 % low, so every number we report comes from the reference solver.
- **Thermal reference.** A finite-element solver reproduces published analytic solutions for layered stacks (Muzychka,
  Culham and Yovanovich, 2003, and an N-layer series) within 1 % of each case's scale and within 0.05 K. It agrees with
  an independent finite-volume solver on generated layouts within their combined discretisation estimates, and each
  reported temperature carries a discretisation estimate of at most 0.5 K. Limits: steady state, one DBC stack, one
  operating point (hottest die 60 K above a 65 °C coolant).

## In progress (no results claimed yet)
- An independent cross-check of the inductance reference against FastHenry on real module geometry (December).
- A search that starts from your own layout and improves on it, tested on planted problems before any customer sees
  its output (December).
- Validation on modules our tools have never seen (January).

## What we do not claim yet
We make no claim yet about how much inductance or temperature headroom real modules leave; the January validation and
a pilot measure that. Every number we deliver comes with its uncertainty band, and you check it in your own tools.

Contact: Lucas, founder, Commutate, [email]
