# 46. Agent memory in intents

Part of: Intent Centre v2. Depends on: 01 (intent record and lifecycle), 08 (North workflow runner), 09 (closure and sign-off), 24 (card model, seal and anonymous), 29 and 30 (glossaries), 32 (charter). Feeds: 03 (create-intent chooser, North's opening line), 22 (initiative start), 19 (centre counters).

## Purpose (three sentences)

When an intent closes, North, Lens and Nira write a few short, filtered lines into the memory the platform already has, per person and per company. The next time the same person opens an intent, North uses those lines and says so in its first sentence, so the person can see what it remembers and correct it. The person owns their lines (read, correct, delete) and the company admin owns the company lines; sealed content, anonymous notes, figures and ratings by name never get in.

## Who uses it and when (role, moment, trigger)

| Role | Moment | Trigger |
|---|---|---|
| Organiser (Janet) | Opens a new intent and reads North's first line | Create-intent chooser (03) opens; North has person entries for her |
| Organiser or sponsor (Janet, Daniel) | Presses **Close intent** | State goes `closing` to `closed` (09); the closure memory pass runs after it |
| Any person (Aaron, Katie, Harvey, Grace) | Checks, corrects or deletes what an agent remembers about them | Avatar menu, Memory; or the link inside North's first line |
| Company admin | Reads and corrects company memory | Memory, tab "Company memory" |
| Lens (agent) | Closure of an Initiative with confirmed glossary or catalogue entries | Closure memory pass |
| North (agent) | Closure of any intent | Closure memory pass; also reads at intent start |
| Nira (agent) | Closure of an intent with signatures | Closure memory pass (default: writes nothing, see Agent behaviour) |
| Super admin | Never | Has no memory page and no access to either layer |

## Entry points (every route, link, Pulse line, button that leads here)

- Avatar menu, "Memory" (existing, route `/centre/memory`).
- North's first line in the create-intent chooser (03) and in each type's start questions (22 for Initiative): the words "Memory" at the end of the line link to `/centre/memory?agent=north&topic=intent`.
- The closure confirmation toast after **Close intent**: "North noted two things about how you run sessions. See them in Memory." Link to the same route.
- Memory page row, link "From: <intent title>" opens the intent when the viewer may open it (visibility rule, 00-BRIEF section 4); otherwise the line shows the title only.
- Pulse (13): no new line type. One quiet line to the company admin the first time company memory gets an entry from an intent: "Lens added company facts from <intent title>. Review them in Memory." (Nira feeds it.)

## Screens, element by element

### Screen A. North's opening line (inside the chooser, 03, and each start questions page)

Route: `/centre/intent/new` (chooser, 03) and `/centre/intent/new?type=<type>&from=<id>` (start questions, 22 for Initiative). Layout at 1280: one agent line above the type cards, under the greeting. At 390: the same line, full width, two lines at most, link on its own row.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Opening line | Agent line (North) | "Last time you ran a brainstorm with five people. Want the same shape again?" built from person entries (the cap is an Open question), then ", from what North remembers about you." The count in words ("five") is the entry's own text, written at closure from `people.participants` in `intents/<id>/intent.json` | None | The signed-in person only | No person entries: the line is the plain v2 line from 03 and nothing is said about memory |
| "Memory" link | Link | The word "Memory" | Opens `/centre/memory?agent=north&topic=intent` | Same | Hidden when the line is plain |
| "Same shape again" chip | Chip | Shown only when the matching entry names a type | Pre-selects that type and fills the people count as a suggestion (the person edits it) | Same | Hidden |
| "Not this time" chip | Chip | "Not this time" | Hides the line for this visit only; deletes nothing | Same | Hidden |
| Preference line | Agent line (North) | A second line only when a preference entry exists: "You like to keep sessions to one sitting." | None | Same | Hidden |

### Screen B. Memory page, intent view (existing page, extended)

Route: `/centre/memory` (existing `ui/src/pages/MemoryPage.tsx`). Layout at 1280: header with agent tabs (North, Lens, Nira) and, for a company admin, the tabs "About me" and "Company memory"; list in the main column; aside cards on the right. At 390: tabs scroll sideways, the aside moves under the list, each memory card is full width with the two buttons side by side.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Agent tabs | Chip tabs (existing) | North, Lens, Nira | Loads `GET /api/memory/me/<agent>` | Everyone with a profile link | "North does not remember anything about you yet." (existing text) |
| "About me" tab | Chip tab (existing) | The person's own memory, all agents | Loads `GET /api/memory/me/<agent>` for the last agent chosen | Company admin (other roles see only the agent tabs) | Same empty text as the agent tabs |
| Topic filter | Chip row (new) | "All", "Intents", "Other conversations" | Filters by `topic` (starts with `intent:` or not) | Same | Chips shown; list shows the tab's empty text |
| Memory card | List item (existing) | Kind and date, "edited by a person" when `by` is person, the text | None | Owner of the file (or company admin for company memory) | Not applicable |
| Provenance line | Text (new) | "From: <intent title>, <date>" taken from `from[].conversation` that starts `intent:` | Click opens the intent if the viewer may; otherwise plain text | Same | Hidden for entries from other conversations |
| Edit | Button (existing) | "Edit" then "Save" | `PUT /api/memory/me/<agent>`; entry becomes `by: person` | Owner | Not applicable |
| Delete | Button (existing, extended) | "Delete" | Same PUT without the entry; also stores a tombstone (see Records) so the agent does not write it back | Owner | Not applicable |
| Forget everything | Button (existing) | "Forget everything North remembers about me" with a confirm | `DELETE /api/memory/me/north`; file removed, tombstones removed | Owner | Hidden when the list is empty |
| Footnote | Text (existing, extended) | "Anonymous notes, restricted areas, figures and contact details are never kept. Sealed cards are never read. Your edits are never overwritten, and a line you delete is not written again." | None | Everyone | Always shown |

### Screen C. Company memory (existing tab, extended)

Route: `/centre/memory`, tab "Company memory". Layout at 1280: tab row, list in the main column, aside cards on the right. At 390: the aside moves under the list and cards are full width.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Company memory tab | Chip tab (existing) | "Company memory" | Loads `GET /api/company/memory/<agent>` | Company admin only | Tab absent for others; direct URL returns 403 (existing) |
| Memory card | List item | Kind, date, text with no names and no quotes | None | Company admin | "No company memory yet" (existing) |
| Edit | Button (existing) | "Edit" then "Save" | `PUT /api/company/memory/<agent>`; entry becomes `by: person` and is never overwritten by an agent | Company admin | Not applicable |
| Delete | Button (existing) | "Delete" | Same PUT without the entry; tombstone stored in the company file | Company admin | Not applicable |
| Source line | Text (new) | "From: <intent title>, closed <date>" or "From: company digest" | Opens the intent (the admin sees existence and outcome of every intent) | Company admin | Hidden |
| "Added by Lens" chip | Chip (new) | The agent that wrote it, or "A person" after an edit | None | Company admin | Hidden |
| Retire button | Button (new) | "Retire" on a fact whose glossary entry was later superseded | Sets `retired_at`; the agent stops using it, the line stays visible, greyed | Company admin | Hidden |

### Screen D. Closure notice (inside 09)

Route: `/centre/intent/<id>/close` (09), after **Close intent**. Layout at 1280: one toast across the top of the content column, above the closure summary. At 390: the same text as a full-width bar under the header; the link drops to its own row.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Memory toast | Agent line (North) | "North noted two things about how you run sessions. See them in Memory." Counts (in words) come from the lengths of `memory.by_agent` in `intents/<id>/intent.json` | Link to Screen B | The person who pressed Close | Nothing noted: no toast. If the `memory` block is missing the bar says "Not available yet: the memory pass for this intent has not run" |
| Filtered note | Text | "Some lines were left out because they could not be kept." Only when `memory.filtered` in `intents/<id>/intent.json` is above zero. No content and no count are shown | None | Same | Hidden |

## User journey (numbered steps from arriving to leaving, with what the agent does between the person's steps)

1. Janet arrives at `/centre/intent/<id>/close` (09) for a brainstorm with five people and presses **Close intent**. She confirms the closure text herself.
2. After the state becomes `closed`, North, Lens and Nira each run a closure memory pass. Each pass builds its lines from the closure record and outcome only (never the cards), runs them through the filters, writes them, and records counts on the intent. A failure is logged and never blocks closure.
3. North writes to Janet's person memory: she ran a brainstorm with five people, it closed in one session, what she decided at closure (the chosen idea's title, if the title passes the filters), and how she ran it (one sitting, within the time box).
4. Janet sees the toast and opens Memory. She finds the lines under North, edits one ("one sitting" becomes "two short sittings"), and deletes another.
5. A week later Janet opens the chooser. North reads her entries and says: "Last time you ran a brainstorm with five people, from what North remembers about you. Memory." She taps **Same shape again**.
6. For an Initiative, Katie and Daniel confirm glossary terms and owners. When Daniel closes the Initiative, Lens writes company facts and accepted ambiguities (see below). The company admin opens Company memory, sees them with "From: <intent title>", and retires one that was superseded.
7. Aaron wrote a sealed card about pay. At every step above nothing about it reaches any file, any prompt or any memory line (see Test).
8. Janet leaves Memory by the avatar menu or by a "From:" link back to the intent. The agents do nothing further until the next intent closes or the next chooser opens.

## States and transitions (table: state, who moves it, to what, what is written)

| State | Who moves it | To what | What is written |
|---|---|---|---|
| Intent `closing` | Organiser or sponsor (**Close intent**) | `closed` | Intent state (09). Then the closure memory pass is queued |
| Pass `queued` | North, Lens, Nira (automatic) | `written` | Entries into `context/memory/<agent>/...`; `memory` counts and `written_at` in `intents/<id>/intent.json` |
| Pass `queued` | Same | `skipped` | Nothing; reason in the run log ("no model", "no profile link", "cancelled intent") |
| Pass `queued` | Same | `failed` | Nothing; logged as a warning; North may re-run it at the next start of that person's session (idempotent by `written_at`; the number of retries is an Open question) |
| Entry `agent` | A person edits it | Entry `person` | `by: person`, new `updated_at`; never overwritten again |
| Entry `agent` or `person` | The owner deletes it | Gone | Tombstone `{hash, at}` in the file's `deleted` list |
| Entry `agent` | Company admin retires it | `retired_at` set | Field on the entry; no longer sent to prompts |
| Intent `cancelled` | Organiser | No pass | Nothing is written (cancelled intents teach no preference; see Open questions) |

## Records read and written (file or route, fields; mark Existing or New)

| Record | Fields | Mark |
|---|---|---|
| `context/memory/<agent>/people/<pid>.json` | `entries[{id, kind: fact\|preference\|decision\|open, text, from[{conversation, at}], updated_at, by}]`, `budget: 4000` | Existing (`sh_platform/memory/__init__.py`) |
| `context/memory/<agent>/company.json` | Same shape | Existing |
| Entry field `topic` | `intent:<type>` or absent | New (optional, ignored by old code) |
| Entry field `retired_at` | ISO time or absent | New |
| File field `deleted` | `[{hash, at}]` tombstones, hash of the normalised text | New |
| `GET/PUT/DELETE /api/memory/me/{agent}` | As above | Existing (`sh_platform/memory/api.py`); PUT writes a tombstone for each dropped entry; DELETE removes tombstones |
| `GET/PUT /api/company/memory/{agent}` | As above, company admin only | Existing; PUT accepts `retired_at` |
| `sh_platform/memory/intent_close.py` | `closure_pass(plane, intent) -> {north, lens, nira: [entry ids], filtered: n}` builds entries by code from the closure record, calls `filters.clean`, then `remember` (people) or `remember_company` (company) | New |
| `memory.remember_company(plane, agent, entries)` | Same merge as `remember` for the company file; `by: person` entries kept; skips tombstones | New |
| `memory.for_prompt` | `{"person": [...], "company": [...]}` within budget; skips retired entries | Existing, small change |
| `summarise.background` | Wrapped background text for a prompt | Existing, read by North, Lens and Nira today |
| `intents/<id>/intent.json` (01, the record; read through `sh_platform/jsonfile.py`) | Read: `type`, `people`, `state`, `time_box`, `closure`, `outcome`, `links`. Never read: cards, `ratings`, notes | New (defined in 01) |
| `intents/<id>/intent.json` field `memory` (counts block) | See next section | New |
| Counter line for "opening line used memory" | One line, no text; file not yet named (Open question 11) | New |
| `profile.json` cards (24) | Read only for `sealed` and `anonymous` ids and sealed text, to build the exclusion set the filter checks against; never as input to an entry | Existing |

## Fields this feature adds to the intent record

Held in `intents/<id>/intent.json` (ruling 12). No brief field is renamed.

```
memory: {
  written_at: iso|null,                    # set once; makes the pass idempotent
  by_agent: {north: [entry id], lens: [entry id], nira: [entry id]},
  filtered: int,                           # lines dropped by the filters; a count, never the text
  state: queued|written|skipped|failed
}
```

Counts only. The record never holds the memory text; the memory files do.

## Agent behaviour (North, Lens, Nira: what each drafts, when, and the moment a person acts)

The pass is the agents drafting. The person acts before it (confirming the closure) and after it (correcting or deleting in Memory). Entry text is built by code from named record fields, not by a free model summary, so nothing outside those fields can enter. Counts are written in words ("five", not a digit) because the existing number guard drops any digit.

**North** (person memory of the closer, and of the organiser if different; slots `decider`, `owner`, `reporter` are Open question 13)
- How this person likes to run sessions: preference, from the time box and session record. Example: "Prefers one sitting for a brainstorm."
- Which types they open: fact, from the type and the participant count in words. Example: "Ran a brainstorm with five people." `topic: intent:brainstorm`.
- What they decided at closure: decision, only when the closer signed it; the title of the chosen idea or decision, if it passes the filters. Example: "Chose to pilot the weekly cash view."
- Open: an unfinished `next` item the closer named. Example: "Wants a follow-up on the treasury glossary."
- For participants who are not the organiser: North writes nothing at closure. Their memory grows only from the private interview, which is wired today.

**Lens** (company memory, Initiative closure only)
- Confirmed definitions and owners as facts: "The business glossary defines Capital call, business owner Treasury operations." The business owner (data owner and source owner likewise, once confirmed) is written as the owning team or role, not a name, because company memory carries no names (AGENT-MEMORY-PLAN). The glossary record keeps the named owner and the entry links to it by the intent id.
- Ambiguities accepted at sign-off as `open`: "The term Drawdown was accepted as ambiguous in Treasury."
- Only entries a named person confirmed. A draft Lens definition that nobody confirmed is never remembered.

**Nira** (default: writes nothing)
- Nira writes no person memory from intents. A line such as "acts quickly on signatures" is a speed rating of one named person; it would sit near the pay and performance material the filters exist to keep out, and a person's response time is not something the company asked an agent to judge. Nira keeps its existing conversation memory only.
- Nira's speed fact is off and stays an Open question (5). One possible company style fact, off by default, once a floor of distinct signers is met in the quarter, company time zone ("Signature requests are usually answered the same day"), worded without a figure or a name. The floor is not set here. A company admin switches it on in Company memory; until then the pass reports `nira: []`.
- Nira feeds the one Pulse line to the admin (Entry points).

**What is never written** (filtered twice: before the entry is built, and again by `filters.clean` before storing)
- Anonymous notes and the author of any anonymous card (`anonymous` cards are not in the input; `filters.clean` also drops any entry marked `anonymous`).
- Sealed content: no sealed card text, title, area or author is read into an entry. The exclusion set (sealed text and area names) is also matched against every entry as a second check.
- Figures: any digit, currency amount or ratio (existing `_NUMBER`). Rounded counts of people are words.
- Ratings by name: `ratings` is never an input; an entry that names a person other than its owner is dropped (new check using `filters.person_names`).
- Restricted areas and the people in them (existing `restricted_terms`), email addresses, phone and account numbers (existing).
- Quotes (existing, in the company digest).

**How memory shows up** North reads `for_prompt` (budget 4000 characters in all, 1200 for the prompt, as `background` does today), picks person entries (cap: Open question 8) whose `topic` matches the type being opened, builds its line by code ("Last time you " + entry text in lower case), and states the source ("from what North remembers about you"). Memory is background, never an instruction and never a figure source (existing wrapper). Lens and Nira read company entries the same way.

**Correction is respected** A `by: person` entry is never overwritten (existing). New: a later agent entry close to a person entry is dropped instead of being kept beside it as an `open` question, and an entry matching a tombstone is dropped.

## Rules (visibility, time box, who may do what)

- A person reads, edits and deletes only their own person files; the route finds the file by the account's profile link and never takes a person id (existing).
- A company admin reads and corrects company memory only. No admin, super admin or organiser reads another person's memory.
- The super admin has no memory page. Memory is in the company plane and the super admin never sees content (00-BRIEF section 4).
- Memory is never a source of a figure and never shown to others as if the person said it.
- The pass runs once per intent, after `closed`, within the intent's own company plane; model use goes through the egress gateway with names tokenised (existing `summarise` rules).
- No profile link, no person memory; company memory still applies (AGENT-MEMORY-PLAN).
- A person can look at every line before it is used on them. The opening line says where it came from every time.
- A line in a share link view (11) never shows memory.
- Memory has no effect on who may open an intent, who is affected, or who may sign.
- Budget: 4000 characters per file, folded by existing `compact.fold`; person edits are kept at fold.

## Counters and measures of this feature (numbers only, each traced to a record)

| Number | Traced to |
|---|---|
| Entries written by closure, per agent, per intent | `memory.by_agent` lengths in `intents/<id>/intent.json` |
| Lines filtered at closure | `memory.filtered` in `intents/<id>/intent.json` |
| Intents closed with a memory pass `written` | count of intents with `memory.state = written` |
| Entries a person edited or deleted this month | Memory files (`by: person`), tombstones `deleted[].at` |
| Company facts added from intents | company file entries whose `from[].conversation` starts `intent:` |
| Times North's opening line used memory | Counter line written when the line is shown (New, no text). Screen says "Not available yet" until its file is named |

Counts are exact and company-wide, with no per-person figure. "This month" uses the company time zone from the profile, else UTC. Where a record is missing the screen says "Not available yet" and names the intent or file.

### Test: a sealed card never reaches memory

File: `tests/memory/test_memory_intent_close.py` (New). Seed the Ardmore family office pack.

1. Seed a brainstorm and an Initiative. Aaron adds a sealed card with a marker no real text contains ("ZEBRA-PAYROLL-SEAL") in q2, area Payroll (restricted), and a second sealed card, anonymous. Katie adds one ordinary card ("weekly cash view").
2. Run the closure pass with a stub model that returns the whole input and, adversarially, the marker and a paraphrase of the sealed card on every call.
3. Assert, across every file under `context/memory/` (all agents, people and company): no match for the marker, the paraphrase (similarity at or above 0.6), the area name "Payroll", Aaron's name next to the sealed text, or any digit.
4. Assert the stub model's recorded input never contained the marker: the pass does not read cards.
5. Assert `for_prompt` and `summarise.background` for Janet, Aaron and the company never return the marker.
6. Negative control: the ordinary closure line ("Ran a brainstorm with five people") is present, and the pass reports `filtered` above zero when the stub injects the marker, so the test cannot pass by writing nothing.
7. Run the same test with the sealed card sealed after the intent opened, and with `anonymous` set, to cover both taps.
8. Corrections: Janet edits a line, runs a second closed intent; the line is unchanged. Janet deletes a line; a third pass does not write it back.

## Reuse check (what exists today: file paths and line ranges found with graft; copied, reshaped or not used, and why)

- `sh_platform/memory/__init__.py` (123 lines): `remember`, `compact`, `company_digest`, `for_prompt`, merge rules (SAME 0.92, CLOSE 0.6), person edits never overwritten. **Reused as is**; reshaped only in `_merge` (drop close-to-person) and `for_prompt` (skip retired); `remember_company` is a thin copy of `remember` on the company path.
- `sh_platform/memory/api.py` (131 lines): the five routes, `person_id` by profile link, `_merge` marking edits as person, company admin gate. **Reused**; PUT gains tombstones, company PUT accepts `retired_at`.
- `sh_platform/memory/filters.py` (49 lines): `clean`, `allowed`, `restricted_terms`, `person_names`, `depersonalise`. **Reused**; adds one function for sealed text and other-person names.
- `sh_platform/memory/compact.py` (28 lines) and `summarise.py` (65 lines): `fold`, `summarise_and_remember`, `remember_for_account`, `background`. **Reused**; the closure pass does not use the model summary (code-built entries), so `summarise` stays for conversations.
- `ui/src/pages/MemoryPage.tsx` (104 lines): tabs, edit, delete, forget everything, footnote, company tab. **Reused**; adds the topic filter, provenance line, retire button and footnote words.
- `docs/specs/AGENT-MEMORY-PLAN.md` (32 lines, found with graft): the two layers, never-remembered list, packages MEM-1 and MEM-2. **Followed**; MEM-3 (cross-company lessons) untouched.
- Wiring today, from the code: North reads memory in the private room (`modules/m1_intent/api/private_room.py:335`) and writes it when an interview ends (`sh_platform/interview/api.py:115-127`); Lens reads and writes in its chat (`modules/m2_baseline/api/lens_chat.py:289-293`); Nira reads on ask and writes every eight turns (`modules/m1_intent/api/briefing.py:391-401`). Route `memory` is registered in `ui/src/App.tsx:133` and `sh_platform/app.py:73` (all paths checked). Tests exist in `tests/memory/` (`test_memory_api.py`, `test_memory_store.py`, `test_memory_wiring.py`). `sh_platform/jsonfile.py` (61 lines) is reused for the record. A single run log file was searched for in `sh_platform` and not found, so the counter location is open.
- The testing guide (`docs/guides/TESTING-INTENT-CENTRE.md`, lines 100 and 776 checked) says agents do not write memory yet. The code shows conversation writes exist; that note is out of date for conversations (doc fix for Nitin, Open question 9). **Nothing writes memory at intent closure today and North's opening line does not exist**: both are New here. Verify live behaviour before correcting the guide.

## Not in this feature

- Cross-company lessons into packs (MEM-3).
- Memory of cancelled intents, or of participants who never talked to North.
- A free-text model summary of an intent. Entries are built from record fields.
- Memory export, shared memory between two people, or an admin reading a person's memory.
- Editing glossary or catalogue definitions from Memory. Those stay in 29 and 30.

## Open questions

1. Should a person be able to switch off learning for an agent ("Stop remembering"), beyond delete and forget? Today a deleted line is not rewritten (tombstone) but new topics still are.
2. Company memory carries no names (AGENT-MEMORY-PLAN) so business, data and source owners are written as teams. Does Nitin want the named owner in Lens's company facts, accepting that names then appear in company memory?
3. Entry `topic` is an optional new field on a SHAPES section 9 shape. Acceptable, or must the type live in `text` only?
4. Should a cancelled intent write one decision entry ("cancelled, with reason") for the organiser? Default here is nothing.
5. Nira's speed fact (how quickly a person signs) is off and is not written. Should a company-level style fact exist at all, with what floor of signers, and on or off for a new company? Any floor beyond the brief's group-of-five rule is not set here.
6. Should the closure screen show the lines North is about to note, with a per-line "Do not remember this", before **Close intent**? Default here is after only.
7. Does the opening line also appear for a participant who joins someone else's intent? Default: no, only when the person opens their own.
8. The opening line uses at most two person entries and the pass retries once. The brief gives neither number; what should they be?
9. Doc fix for Nitin: `docs/guides/TESTING-INTENT-CENTRE.md` says agents do not write memory yet. Conversation writes exist in code; the guide needs correcting after live behaviour is verified. Not edited here.
10. Memory lives at `/centre/memory`, `/api/memory/...` and `/api/company/memory/...`, outside the brief's `/centre/intent/...` and `/api/intents/...` convention. Keep them as existing routes?
11. Where does the "opening line used memory" counter live? The run log has no single file and `events.jsonl` is per intent.
12. Does closing a weekly check-in series, or one week, write memory? Default here: no pass for check-in weeks.
13. Should a Decision or Problem also write memory for `decider`, `owner` or `reporter`? Default: closer and organiser only.
