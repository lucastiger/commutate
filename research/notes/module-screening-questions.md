# Module screening questions (fact-only), for PREES and customer contacts

Drafted by the founder session, 2026-11-15, as the founder's checklist for screening calls (plan section 2, step 2). It is not sent by email: the short emails, which ask for a call, are in `research/notes/outreach-drafts.md`. Source: T0314's 14
screening questions (`research/notes/o003-twin-coverage.md`, section 4) plus the plan's five additions (substrates per
module, die array, die rotation, separate diode dies, terminal pads per net), merged where they overlap.

Leakage rule (plan section 6): we ask for facts only, never geometry, until the 12-28 freeze. Every answer used in a
screen or a coverage table is recorded with its source and declared as a fact-only screening answer.

## Part A: questions for the call (not for email)

> We are surveying how wire-bonded SiC half-bridge power modules are built. The questions below can be answered from
> a datasheet or a short verbal description. Please do not send drawings, layout files, photos or copper dimensions:
> we only need yes/no answers and counts at this stage. If a question does not apply, or the answer is not known,
> say so.
>
> **Module and substrate**
> 1. How many ceramic substrates (DBC or AMB tiles) carry the power circuit?
> 2. How many power terminals does the module have, and on which nets (DC+, DC-, phase, other)? How many terminal
>    pads or tabs does each power net have on the substrate?
> 3. Is each power net (DC+, DC-, phase) a single connected piece of copper on the substrate, or several islands
>    joined by wires or clips?
> 4. Does any power net's copper form a closed ring, that is, copper that completely surrounds an opening?
> 5. Does any power net branch into more than two copper strips, or have more than one copper path feeding it from
>    its terminal?
>
> **Dies**
> 6. Which switch die is used (part number or die size in mm), and are all switch dies the same part?
> 7. How many switch dies are there per switch, and how are they arranged (rows x dies per row)?
> 8. Do all switch dies face the same way (gate pad on the same edge), or are some turned by 90 or 180 degrees?
> 9. Are there separate antiparallel (freewheeling) diode dies? If so, how many per switch?
>
> **Wire bonds**
> 10. Does every switch die carry the same number of power wires, all bonded on its source pad? How many per die?
> 11. Do each switch's power wires all land on one copper strip of the other net, along a single line?
> 12. Do the high-side and low-side switches sit side by side, each with its own die row and landing strip, with
>     their power wires running in opposite directions?
> 13. Does any power wire run die to die, or land directly on another die or on a terminal?
> 14. Are there Kelvin-source wires? Where do the gate (and Kelvin) wires land on their copper: at its nearest edge,
>     or further along the strip or over the die?
> 15. Are the dies' power connections bond wires, or clips, ribbons or a planar (sintered or soldered) interconnect?

## Part B: scoring key (internal, not sent)

"Excluding answer" is the answer that puts the module outside today's generator family (T0314, section 4). Additions
without an excluding answer are recorded for the coverage table (plan section 2), which counts how many modules each
missing feature blocks.

| sent # | T0314 # / addition | excluding answer today | feature it maps to |
|---|---|---|---|
| 1 | addition: substrates per module | more than one | multi-substrate modules |
| 2 | 1; addition: terminal pads per net | not exactly three power terminals; pads per net recorded | terminal layout |
| 3 | 8 | not one piece | net topology |
| 4 | 9 | yes | copper rings |
| 5 | 10 | yes | multi-column or multi-strip nets |
| 6 | 2 (same part), 3 (outline a multiple of 0.5 mm) | mixed parts; outline off the 0.5 mm grid | die library |
| 7 | 5; addition: die array | more than one row per switch | dies in several rows |
| 8 | 2 (orientation); addition: die rotation | mixed orientation; 90 degrees is not representable, 180 degrees only uniformly | quarter-turned dies (plan section 3) |
| 9 | 13; addition: separate diode dies | yes | diode dies (out of O003 scope) |
| 10 | 4 | no | wire count per die |
| 11 | 7 | no | landing line |
| 12 | 6 | yes | side-by-side switch blocks (plan section 3) |
| 13 | 14 | yes | die-to-die or terminal wires |
| 14 | 12 (Kelvin: supported), 11 (gate landing beyond nearest edge) | gate landing beyond the nearest edge, under rule R0 | signal-wire landing |
| 15 | addition (coverage census, 2026-11-15) | no bond wires | outside the wire-bonded scope |

Notes:
- T0314 found that questions 6 and 11 (sent 12 and 14) decided 2R, 2D_Case_6 and 2D_Case_4; question 2 was hidden by
  the M1 reconstruction step, so sent question 8 asks about orientation directly.
- Sent question 14's gate-landing item depends on the open finding 2 of review T0315 (whether the measured minimum
  gate-wire length is a criterion); record the answer either way.
- Sent question 15 was added after the coverage census (`research/notes/coverage-census.md`): no free source stated
  wire-bonding for any of its 14 commercial modules.
