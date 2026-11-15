# Outreach drafts: PREES and design-partner prospects

Drafted by the founder session, 2026-11-15, for the founder to send (plan sections 2 and 10). Two short emails that ask
for a call, and a call guide. The full screening list (`research/notes/module-screening-questions.md`) is a checklist
for the calls, not for email.

Rules behind the wording:
- no headroom or performance claim (none is supported before O009); the capability brief
  (`research/notes/capability-brief-draft.md`) states only recorded claims C002 and C004;
- no geometry before the 12-28 freeze (plan section 6): PREES files are asked for "from late December", and the emails
  say no drawings or files are needed now;
- customer files never go to an AI service unless the NDA allows it (standing rule), so email 2 can promise that.

## Email 1: NC State PREES (Prof. D. C. Hopkins)

**Subject:** Your lab's SiC modules: a 20-minute call?

> Dear Professor Hopkins,
>
> I'm Lucas, founder of Commutate. We're building software that re-lays out wire-bonded SiC power modules (for a new
> die, a second-source die or a different die count in the same housing) to lower loop inductance at bounded junction
> temperature.
>
> We'd like to test it on your lab's published modules. Could we have a 20-minute call in the next two weeks? I'd like
> to learn which modules you could share with us from late December, in which file formats, and on what terms.
>
> If email is easier, three quick questions about those modules:
> 1. Are the dies wire-bonded, and are there separate antiparallel diode dies?
> 2. How many dies per switch, how are they arranged, and do they all face the same way?
> 3. How many terminal pads does each power net (DC+, DC-, phase) have on the substrate?
>
> No drawings or files are needed at this stage.
>
> Best regards,
> Lucas
> Commutate

## Email 2: module makers and OEMs (design-partner pilot)

**Subject:** New die in an existing SiC module? A 20-minute call

> Hi [first name],
>
> I'm Lucas, founder of Commutate. When a power module moves to a new die generation, a second-source die or a
> different die count, someone has to re-lay out the substrate inside the same housing. We're building software that
> does that re-layout and ranks the candidates by loop inductance, junction temperature and current sharing, so you can
> check the results in your own Q3D or Icepak flow.
>
> We're looking for one or two design partners for a fixed-scope pilot on a real module early next year. Would you
> have 20 minutes in the next two weeks to see whether one of your modules fits?
>
> Your files would stay under NDA and would not be sent to any AI service unless you agree.
>
> Best,
> Lucas
> Commutate

## Call guide (for the founder; not sent)

Partner call, about 20 minutes, in this order:
1. **Their derivative problem** [A-T5]: new die generation, second source or die count? Which module, which housing,
   and by when? Who owns the budget?
2. **Fit check**, the questions that decided the census (`research/notes/coverage-census.md`) first:
   - wire-bonded, or clips, ribbons or planar interconnect?
   - separate antiparallel diode dies, and how many per switch?
   - dies per switch, their arrangement (rows x dies per row), and do they all face the same way?
   - how many ceramic substrates carry the power circuit?
   - how many terminal pads does each power net have on the substrate?

   The remaining questions of `module-screening-questions.md` (Part A) only if time allows; Part B is internal.
3. **Verification** [A-T4]: which tools do they use to check a layout (Q3D, Icepak, others)? Would they accept a
   software-generated layout that they verify in that flow?
4. **Data access**: which formats hold their layouts (DXF, STEP, Gerber, native CAD) and simulations (Q3D, Icepak
   projects)? Does their NDA allow cloud compute, and AI processing?
5. **Next step**: would they sign an LOI for a pilot? The target is a signed LOI by 12-18.

PREES call: points 2 and 4, plus which modules they could share from late December and under which licence.

## After each call
- Write the note in `project/customers/` as its README says (`YYYY-MM-DD-<company-or-alias>.md`, statements tagged
  with the assumption id, for example `[A-T4]`). The charter counts customer evidence only when it is recorded there.
- Send the session the fact-only answers to the fit-check questions, as text. Never send files or drawings; if a
  prospect sends any, keep them outside the repository and out of AI tools.
