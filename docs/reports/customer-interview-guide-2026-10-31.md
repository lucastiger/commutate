# Customer discovery guide — derivative re-layout (day 33 → day-45 gate on 2026-11-12)

Purpose: produce charter evidence for A-T3, A-T4 and A-T5, and meet the day-45 kill criterion ("a customer willing to
share a reference layout under NDA"). Proposal from the thesis review of 2026-10-31; the founder runs every
conversation. Agents never contact anyone.

## Whom to talk to
Roles, not names: power-module layout or packaging engineers and their managers at module makers; inverter or
traction-drive teams at automotive tier-1s and OEMs that design or specify their own modules; packaging groups at
SiC/IGBT die suppliers; independent power-electronics design consultancies. Prefer people who personally did a
derivative re-layout (new die generation, second source, or die count change) in the last two years.

## Questions (tag each answer in the note with the assumption it bears on)
1. Walk me through your last derivative: what changed (die generation, supplier, count), what stayed fixed
   (housing, substrate, terminals)? How many design–build–test iterations, and how many weeks each? Quote numbers
   verbatim. `[A-T3]`
2. What limited the result — loop inductance, current sharing between paralleled dies, gate-loop symmetry, Tj, or
   manufacturing rules? Did you leave performance on the table because of time? `[A-T3]`
3. Which tools and checks does a layout have to pass before you build it (Q3D, Icepak, in-house scripts, DRC)?
   Would you accept a layout you did not draw if it came with decks you can run in that flow? What would make you
   reject it? `[A-T4]`
4. Who owns the budget for a derivative, and what does one iteration cost you (time, prototypes, test)? Would you
   pay for a fixed-price "derivative layout sprint" delivered in weeks? In what range, and who signs? `[A-T5]`
5. Could you share one past reference layout (housing, stack, design rules, die data) under NDA so we can show a
   re-layout on your problem? What would legal need? `[day-45 gate]` `[A-T4]`
6. Who else does this for you today — vendor tools, consultancies, in-house automation? `[A-T6]`

## Recording (per `project/customers/README.md`)
One file per conversation, `project/customers/YYYY-MM-DD-<company-or-alias>.md`: who (role), context, current
process, iteration counts and cycle times quoted verbatim, tools, willingness to share a reference layout, budget
owner, objections, follow-ups. Tag statements with `[A-T3]`…`[A-T6]`. Never paste customer files, drawings or data
into the repository; reference them by an ID stored in the private data vault. Commit notes as the founder
(`project/customers` is excluded from the loop's state commits).

If earlier interviews were held and their notes were lost with the stolen laptop, reconstruct each from memory into
the same format, mark it `Reconstructed on <date> from memory`, and commit it.
