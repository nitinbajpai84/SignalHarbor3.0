# Intent Centre v2: the brief every spec agent reads first

Date: 7 October 2026. Author of the vision: Nitin (product owner). This folder holds one spec file per sub-feature. Each file is written by one agent against this brief. Read this whole file, then `docs/specs/INTENT-CENTRE-SPEC.md` (the v1 spec: wall, Define, Moment of truth, governed state), then `docs/plan/SHAPES.md`, then the sections of `docs/guides/TESTING-INTENT-CENTRE.md` that match your feature. Use `graft ask "<need>" --source` before opening source files.

## 1. What the Intent Centre is for (the vision, in Nitin's words, tidied)

The Intent Centre is where anyone in a small or mid-size company starts something and where everyone can see what the company is working on. It answers two questions:

1. **"I want to do something. Where do I start?"** A person opens the centre with an intent, not a form. The centre asks what they intend to do and runs the right workflow for it.
2. **"What is happening in the company?"** Everyone sees the intents in their area: running, finished, and past. What people are discussing, what is high value in operations, what ideas people are thinking about, which projects are running. That gives the company clarity.

Today the centre starts at the wall. That is wrong. It must start at **what you intend to do**.

## 2. The intent types (fixed for this spec round)

Five types. Each has its own start questions, its own workflow, its own outcome record, and its own time box. The first three are Nitin's; the last two are added because the pulse and brainstorm flows produce them and they need somewhere to go.

| Type | Why someone opens it | Who is in it | Produces | Time box (default) |
|---|---|---|---|---|
| **Initiative** (a project or new initiative) | "I want to run X." Needs a clear goal, the people, whether a build is needed, whether definitions already exist | sponsor, organiser, committee, affected people | charter, business glossary, technical glossary and catalogue, process map, data sources map, build-ready flag, hand-off to Build (where gap analysis is step 1) | 10 working days |
| **Brainstorm** | "I have an idea or a problem statement and I want six or seven people to think with me" | organiser plus 4 to 8 invited people | one chosen idea or solution, with the thinking kept; it may become an Initiative or go to the backlog | 3 working days, one live session |
| **Weekly pulse** | "Every week my ops people say what ran, what broke, what is on their mind" | an ops area's people, recurring | a week record; each item becomes an ops problem, a backlog item, or nothing, with the reason | one week, recurring |
| **Problem** (an ops problem) | "Something is wrong in operations and it needs an owner and a fix" | reporter, owner, affected people | root cause, fix, owner, closure; may become an Initiative if it is bigger than a fix | 5 working days |
| **Decision** | "One decision needs to be made and recorded with its options" | decider, advisers | the decision, options considered, who decided, why | 2 working days |

An Initiative has three sub-stages (the v1 rooms, re-ordered under the type): **Think unfiltered** (the wall), **Define strategically** (clusters, shelves, process map, data sources, glossary, catalogue, governed state, charter), and **Build-ready** (a check, not a room: do we have what Build needs?). **Gap analysis is the first step of Build, not part of the Intent Centre.** The Moment of truth screen stays as it is built but is reached from Build; Intent hands over a build-ready charter.

## 3. What every intent has in common (the intent record)

One record per intent, one id, whatever the type. Fields every spec must respect (an agent that needs more adds a field in its own spec under "Fields this feature adds" and never renames these):

```
intent: {
  id, type: initiative|brainstorm|pulse|problem|decision,
  title, purpose (one line: why this is happening),
  created_by, created_at, company,
  areas: [department or ops area tags],          # who is affected; drives visibility
  people: {organiser, sponsor|null, participants: [], affected: [], observers: []},
  state: draft|open|in_session|closing|closed|cancelled,
  time_box: {starts, ends, extended_by: [{by, at, reason}]},
  stages: [{key, state, opened_at, closed_at}],   # per type
  outcome: {...per type...} | null,
  closure: {closed_by, closed_at, summary, why_it_happened, what_came_out, next: [{kind: initiative|backlog|problem|nothing, ref, reason}]},
  ratings: [{by|anonymous, score 1-5, note}],
  links: {from: intent id|null, to: [intent ids], build: ref|null},
  share: {link|null, who_may_open: [...]},
  record: "intents/<id>.json"                      # one file in the company plane
}
```

Storage: one JSON file per intent in the company data plane, through `sh_platform/jsonfile.py`, read and filtered per viewer with `sh_platform/profile/view.py`. Walls, charters, baselines and assessments that exist today (`modules/m1_intent` sessions, `m2_baseline`, `m3_connect`) stay where they are; the intent record points at them by reference. It never duplicates them.

## 4. Visibility rule

- The person who opens an intent names its **areas** (departments or ops areas) and who is **affected**. Everyone tagged to those areas sees the intent exists, its title, purpose, stage, who organised it, and the outcome once closed. They open the content only if they are a participant, affected, or the share link names them.
- Participants see everything in the intent except sealed and anonymous material, which keep the v1 rules (D-013, seal).
- A **super admin** sees that every intent exists (title, type, state, areas, people count) and never its content.
- The **company admin** sees every intent's existence and outcome, never anonymous notes.
- A **share link** opens a read-only view of a closed or open intent to the people it names: what was done, what was said, who said it (unless anonymous), what came out. Sharing is explicit, per intent, by the organiser.
- Past intents are kept. Nothing is deleted; cancelled intents say why.

## 5. Agents in the centre (agents decide and draft; people act at named moments)

- **North** runs the workflow. For each type North knows the stages, keeps the clock, drafts the next step, asks the missing question, nudges the person whose turn it is, and writes the closure draft. North is responsible for the intent reaching an outcome inside its time box; if it will not, North says so and proposes extend, close with what we have, or cancel, and a named person picks.
- **Lens** drafts definitions: business glossary, technical glossary, catalogue entries, process map, data sources, governed state. People confirm.
- **Nira** keeps "what is waiting for you" and feeds the Pulse page lines.
- Agents never sign. A named person signs, confirms, decides, rates.

## 6. Hard rules for every spec (no exceptions)

- No game words (no quest, level, player, badge, points, hoops). Lanes, cards, shelves, seals, rooms, walls.
- No model or vendor names in copy. Agents are North, Lens, Nira.
- Every number on a screen traces to a record or the screen says "Not available yet" and names what is missing.
- Agents decide and draft; people act at named moments. Say which.
- Each person sees only act, shared and context information for them.
- Synthetic data only in examples; use the Ardmore demo company names (Janet organiser, Daniel sponsor, Katie analyst, Aaron participant, Harvey owner, Grace approver) and the family office pack.
- Reuse first (D-031): name what exists in `modules/m1_intent`, `m2_baseline`, `m3_connect`, `sh_platform`, `ui/src` and reuse it. A spec that rebuilds an existing screen is rejected.
- British spelling. No em dashes. Short sentences.
- Do not invent thresholds or business rules you cannot justify; put them under Open questions.
- Do not edit `.claude/`, `docs/decisions.md`, or any file outside `docs/specs/intent-centre/`.

## 7. The file you write

Write exactly one file: `docs/specs/intent-centre/<NN>-<slug>.md` as named in your task. Use this skeleton; every heading is required, "None" is an acceptable body.

```
# <NN>. <Feature name>

Part of: Intent Centre v2. Depends on: <other NN files>. Feeds: <other NN files>.

## Purpose (three sentences)
## Who uses it and when (role, moment, trigger)
## Entry points (every route, link, Pulse line, button that leads here)
## Screens, element by element
For each screen: route; layout at 1280 (regions) and at 390 (what collapses); then a table:
| Element | Kind (button, field, list, chip, panel, agent line) | Shows | On click or change | Visible to | State when empty |
## User journey (numbered steps from arriving to leaving, with what the agent does between the person's steps)
## States and transitions (table: state, who moves it, to what, what is written)
## Records read and written (file or route, fields; mark Existing or New)
## Fields this feature adds to the intent record
## Agent behaviour (North, Lens, Nira: what each drafts, when, and the moment a person acts)
## Rules (visibility, time box, who may do what)
## Counters and measures of this feature (numbers only, each traced to a record)
## Reuse check (what exists today: file paths and line ranges found with graft; copied, reshaped or not used, and why)
## Not in this feature
## Open questions
```

Length: 150 to 400 lines. Concrete over general. Every button named. Every empty state named.

## 8. Definition of done (a spec file is done only when every line holds)

1. The file exists at the named path and every heading in section 7 is present, in order, with a body or "None".
2. Every screen has a route, a 1280 layout, a 390 layout and an element table with all six columns filled.
3. Every button, link, chip and field on every screen is named and says what happens on click.
4. The user journey is numbered, starts at the entry point and ends at leaving the screen or the intent, and says what the agent does between the person's steps.
5. Every number shown on screen names the record it is read from, or the screen copy says "Not available yet" and names what is missing.
6. Every record read or written names the file or route and is marked Existing or New.
7. The Reuse check names real files that exist in this repo (paths checked), each marked copied, reshaped or not used, with the reason. "Nothing exists" names the searches run.
8. Every number, threshold or rule the brief did not give is under Open questions, not stated as fact.
9. No game words, no model or vendor names, no em dashes, British spelling, Ardmore synthetic names only.
10. The file does not contradict sections 2 to 5 of this brief; where it must, it says so under Open questions.
11. The intent record fields it adds are listed under "Fields this feature adds" and none of the brief's section 3 fields are renamed.
12. Routes follow the convention: pages under `/centre/intent/...` with the intent screen at `/centre/intent/<id>`, the chooser at `/centre/intent/new`; API under `/api/intents/...`. Any other route is an Open question.

## 10. Settled conflicts (orchestrator's decisions after the first wave, 7 Oct 2026)

The first wave of 54 files disagreed on the points below. These rulings win; every file is corrected to match them in the review wave. Where a ruling changes a decision in `docs/decisions.md` it is listed as requests (A-074 onward) for Nitin, not applied.

1. **Routes.** Pages: `/centre/intent` (home), `/centre/intent/new?type=<type>&from=<id>` (chooser and start questions), `/centre/intent/<id>` (the intent screen; the stage view opens by default), `/centre/intent/<id>/<view>` where view is one of `wall`, `define`, `charter`, `build-ready`, `session`, `week`, `review`, `close`, `share`, `events`, `people`, `projector`; `/centre/intent/past`, `/centre/intent/past/<id>/chain`, `/centre/intent/backlog`, `/centre/intent/admin`; super admin at `/centre/control/intents`. API: `/api/intents/...` for everything new; the share visitor entry stays at `POST /api/modules/m1_intent/shared/view` because guest routes may only live under `/api/modules/<module>/` (file 14). Any `/intents/...`, `/intent/...`, `/centre/intent/i/<id>`, `/intent-centre/...` or `/centre/intent/start` spelling is wrong.
2. **Start questions.** The per-type files are canonical: 22 (Initiative, six questions), 35 (Brainstorm, five), 38 (Weekly check-in, four), 41 (Problem, five), 43 (Decision, five). File 03 is the chooser frame only and hands over to the per-type questions. File 02's YAML is corrected to match the per-type files exactly, including field names (`what` for the Problem statement; `thought` for the third check-in kind).
3. **Weekly check-in.** On screen the type is "Weekly check-in"; "Pulse" alone always means the daily page. Record key stays `pulse`. One intent record for the series plus one file per week at `intents/<id>/weeks/<week_key>.json`. A new week opens by the clock on the next working day after the close day, even if the review is unfinished. Item kinds `ran | broke | thought`. Fates `problem | backlog | handled | nothing`, each with a reason; every `broke` item needs a fate before the week closes; `ran` and `thought` items left undecided close as `nothing` with reason "Not reviewed this week". Series are not rated; weeks are not rated.
4. **Affected and observer.** An affected person (by area or named) sees existence, title, purpose, stage, clock, people, and the outcome once closed. Content opens only when the organiser switches on "affected people may read" at creation (default off) or when they are named on a share. An observer reads what a participant reads and never writes or votes. File 05's matrix is corrected to this; 06 and 23 follow.
5. **Super admin.** Sees existence only: title, type, state, areas, people count, dates, time box status, per company, read through the kernel on request (no copy in the control plane). A company switch "titles private to the company" (default off) removes titles from that view. Request A-074: the super admin may read intent existence through the kernel; the control plane still stores no company data.
6. **Outcome.** `outcome` is an object from the moment the intent opens, shaped per type (02), never null.
7. **Links.** A Decision may link to any type as source or target; 02 widens `can_become`.
8. **Numbers.** Time zone: the company's from the profile, else UTC, in every file. Counts are exact. Means, medians and any per-person figure show "Fewer than five" below five records. Ratings aggregate from three.
9. **Questions to people.** The cap is three open questions per person across Define (process map, glossary, catalogue, governed state together). Cite A-045 (at most 3 questions per owner); the brief's earlier "A-043" was a wrong number.
10. **Gap analysis** is room 0 of the Build centre at `/centre/build/gap-analysis?from=<id>`; it is `modules/m3_connect` as built, moved, not rebuilt. BUILD-CENTRE-SPEC.md is to be amended (request A-075).
11. **Owners.** Three owner kinds everywhere: business owner, data owner, source owner. The governed state's "process owner" is the business owner of the process (31 and 28 agree on this wording).
12. **Events.** One `intents/<id>/events.jsonl` per intent (16); the intent record holds counts only. Files per intent therefore live in a folder `intents/<id>/` with `intent.json` as the record; 01 is corrected from a flat file.
13. **People.** `people` gains `decider` (Decision) and `owner` and `reporter` (Problem) as named slots; `sponsor` stays optional per type.
14. **Draft intents** are visible only to the person who started them. Cancelled intents keep their reason and are shown in Past.
15. **Ratings.** Anonymous by default; a person's own file keeps the link so they can see what they gave; no per-person averages exist anywhere.

## 11. Residual rulings after the review wave (7 Oct 2026, second pass)

16. **Outcome shape is flat per type.** `outcome.what`, `outcome.goal`, `outcome.statement`, `outcome.chosen` and so on, as file 02's YAML writes them. No `outcome.problem.*`, `outcome.initiative.*` or `outcome.brainstorm.*` nesting. 02 owns the shape; 22, 35, 37, 41, 43 follow it.
17. **Week file shape.** `intents/<id>/weeks/<week_key>.json` holds `{week_key, opens, closes, state, items: [{id, by|anonymous, kind: ran|broke|thought, text, severity|null, count|null, amount|null, ref|null, fate|null, fate_reason|null, decided_by|null}], review: {...}, closed_at}`. File 38 owns it; 39 and 40 follow. The organiser's optional fourth question produces kind `thought`.
18. **Query parameters are allowed on the twelve views.** Sub-panels never get a new view; they use a query key on the owning view: `?tab=` (define: clusters, process-map, data-sources, glossary, catalogue), `?card=`, `?week=`, `?turn=`, `?draft=`, `?view=`, `?focus=`, `?process=`. `/centre/intent/<id>` is the stage view and holds triage, notes, options and record as panels. No `/triage`, `/roles`, `/rate`, `/invitation` views.
19. **Closure next kinds** are `initiative | problem | decision | backlog | handled | nothing`, each with a reason.
20. **Decision requests are numbered from the next free A-number in `docs/decisions.md` and `docs/ledger/autonomous.md`**; the integrator checks and renames A-059 and A-060 if taken.
21. **People slots.** `people: {organiser, sponsor|null, decider|null, owner|null, reporter|null, participants: [], advisers: [], affected: [], observers: []}`. Advisers are a list, not a slot.
22. **Working days** are Monday to Friday until the profile has a calendar; the company time zone field is `profile.company.time_zone` (New), else UTC.
23. **Weekly check-in series** closes "with what we have" only by ending the series; a week never closes with an undecided `broke` item.
24. **Guest routes** stay where the kernel allows them: `/api/modules/m1_intent/shared/*`, `/api/modules/m1_intent/approver/*`, `/approve/<token>`, `/join/<code>`, `/owner-answer/<token>`. They are the listed exceptions to ruling 1.

## 12. Rulings after integration (7 Oct 2026, third pass)

25. **Who closes.** The organiser presses "Close this intent" for every type. A per-type confirmer must act first where the type names one: sponsor (Initiative), decider (Decision), owner then reporter (Problem), nobody (Brainstorm, Weekly check-in week). Files 02, 13, 14, 16 follow 01 and 09.
26. **When an Initiative reaches `closing`.** At charter signature (32). Define close (26) moves nothing; build-ready and hand-off (33) happen inside `closing`; `closed` is written by the organiser after hand-off or after a "build needed: no" closure.
27. **Cancel reason** lives in one place: `closure.cancel_reason`, with `closure.closed_by`, `closure.closed_at` and `state: cancelled`. No other field.
28. **Record keys.** The record accepts the section 3 fields plus every field a feature file lists under "Fields this feature adds". 01's strict key set is that union, not section 3 alone; unknown keys outside the union are refused.
29. **Decision numbers.** A-059 and A-060 are taken. The requests are A-074 to A-090 as 00-INDEX.md section 8 numbers them; every file that cites A-059 or A-060 cites A-074 or A-075 instead.
30. **Seed names.** Mei Ling, Ravi and Rahul are allowed synthetic names for extra reporters and participants; the demo seed adds their accounts.

31. **Enhancements to a running project are Initiatives.** A change or addition someone wants to a project already built or in Build is opened as a new Initiative with `links.from` pointing at the earlier Initiative (or at the Build release). It is never a Problem; a Problem is only for something that is wrong in operations today.
32. **Data-backed opportunities (file 56).** The Ops agent (the Watcher in the Build centre) may draft an opportunity when the records show a pattern (a measure drifting for several periods, repeated check-in items, alerts on one process); the analyst adds or disputes evidence; North judges whether it merits an Initiative and says why; the result is a suggested Initiative on the home and the backlog, dashed, picked up only by a person. Three agents talk; no agent opens an intent.

## 9. Guardrails for every agent in this folder

- Write only your one file. Never edit another agent's spec, `.claude/`, `docs/decisions.md`, code or contracts.
- Read before you write: the brief, the v1 spec, SHAPES, the matching testing-guide section, and graft for the code.
- Do not run servers, seeds, tests or anything that mutates the data plane.
- Do not invent: a missing fact is an Open question, never a guess stated as a rule.
- Report at the end: what you wrote, what you reused, what you could not find, and your open questions, in that order, in under 300 words.
