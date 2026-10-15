# 29. Business glossary

Part of: Intent Centre v2. Depends on: 01 (intent record), 05 (areas and visibility), 06 (people and roles), 08 (North), 22 (check at initiative start). Feeds: 09 (closure and sign-off, charter page), the Register, the technical glossary and catalogue spec, Build hand-off.

## Purpose (three sentences)

An Initiative produces a business glossary: the terms its cards, interviews and documents use, each with a business definition, a named owner, and any ambiguity that was accepted as a known risk. Lens drafts every term, the owner confirms or corrects it, and the governance lead settles every term that means more than one thing. A term has one definition company-wide, so the Initiative reuses what the company already holds and may only propose a change, which becomes a version on that term.

## Who uses it and when (role, moment, trigger)

| Role | Moment | Trigger |
|---|---|---|
| Organiser (Janet) | During Define strategically, and before the charter is signed | Opens the Glossary tab to see what is still draft |
| Analyst (Katie) | Before the Define session | Reads Lens's drafts, edits wording, uploads the company's own glossary file |
| Term owner (Harvey; the business owner of the term. Data owner and source owner belong to the catalogue) | When Lens names them as owner | A "Confirm my terms" line in "what is waiting for you" (Nira) |
| Governance lead (the company admin by default; see Open questions) | In or after the Define session | Terms flagged ambiguous, shown as "Waiting for you" |
| Sponsor (Daniel) | At charter signature | The charter carries the glossary page; open ambiguities show as blockers |
| Participant (Aaron) | Any time | Reads the confirmed terms of an Initiative he is in; confirms nothing unless he is an owner |
| Super admin | Never in content | Sees only the counts on the Initiative card (spec 05) |

## Entry points (every route, link, Pulse line, button that leads here)

- Right panel of Define on an Initiative: tab "Glossary" (route `/centre/intent/<id>/define?tab=glossary`). Tabs in order: Clusters, Process map, Data sources, Glossary, Catalogue, Governed state.
- Nira line "Confirm my terms (2 of 3 questions)" for a named owner, linking to the owner screen (Screen B).
- Nira line "Settle 4 ambiguous terms" for the governance lead, linking to Screen C.
- North line on the stage bar: "Glossary: 9 of 14 terms confirmed. Next: Harvey owns 3 terms."
- Charter page "Business glossary" (Screen D), reached from the charter sign-off screen.
- Register: a term row opens the term page (Screen E) at `/register/terms/{term_id}`. The glossary page in the Register is a new line in `RegisterPage` (NEW). The Register change is owned by file 12's "Intents I was in" and file 32's charter pages, not by this file.
- Initiative start check (spec 22): "Terms the company already holds" opens the same term page read-only.

## Screens, element by element

### Screen A: Glossary tab in Define's right panel

Route `/centre/intent/<id>/define?tab=glossary`. Reuses the m2_baseline glossary screen (`ui/src/modules/m2_baseline/glossary/GlossaryScreen.tsx`) inside the right panel; the baseline id comes from `links.build`-style reference `outcome.glossary.baseline_id` (see Fields).

Layout at 1280: Define keeps its two columns (clusters left, 60 percent; right panel 40 percent). The right panel stacks: header strip, filter chips, term list, term detail drawer that slides over the list. At 390: the right panel becomes a full-screen sheet opened by a "Glossary" button on the Define bar; the term detail replaces the list with a Back button; chips scroll sideways.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Header strip | panel | "Business glossary", counts "14 terms: 9 confirmed, 3 draft, 2 ambiguous accepted" (read from `glossary.json` `counts()` and `outcome.glossary`), the source line "Lens read 22 cards, 3 interviews, 2 documents" (read from the wall record and `glossary.json` `documents`; shows "Not available yet. Sources not counted." if either is missing) | None | Participants, affected, organiser, sponsor, governance lead | "No terms yet. Lens drafts them when the wall closes." with a "Ask Lens to draft now" button |
| "Ask Lens to draft now" | button | Same as the existing Build action | `POST .../glossary/build`; strip shows "Lens is drafting" then the counts | Organiser, analyst, company admin | Hidden once built; "Update draft" shows instead |
| "Update draft" | button | Re-reads new cards and documents | Same route; a person's wording is never overwritten, a later draft appears beside it as a proposal | Organiser, analyst, company admin | Disabled with "Nothing new to read" when no new card or document |
| "Upload your own glossary" | button | A file picker (xlsx, csv, docx, pdf as the existing upload accepts) | `POST .../glossary/upload`; terms found in it are matched by name then by meaning | Organiser, analyst, company admin | Hint: "Optional. Lens will also match against the company's terms." |
| State chips | chip row | All, Draft, Confirmed, Ambiguous, Accepted as risk, Reused, Mine | Filters the list in the browser (tens of rows) | All who open the tab | "Mine" shows 0 for a non-owner and is greyed |
| Search box | field | Type a term | Filters by term and alias | All who open the tab | "No term matches" |
| Term row | list item | Term (and aliases), one line of the draft definition, owner, state chip, an ambiguity dot if open, a "Reused from the company" tag if it already exists company-wide | Opens the term drawer | As rows: terms of a restricted measure appear to those who may not see it only as "A restricted measure" without id or count | "No term matches this filter" |
| Ambiguity dot | chip | "3 meanings found" | Opens the drawer on the Meanings block | Participants | Not shown when none |
| Term drawer, Definition block | panel | Business definition draft, how sure ("A guess by Lens", "Stated by Harvey"), the previous wording when a provided glossary had one | None | Same as the row | "Not available yet. No source gave a wording." |
| Drawer, Source block | list | Where Lens found it: "Card 12 (Operations lane)", "Interview, Aaron, 4 Oct", "Document: Fund report pack, page 3". Anonymous or sealed cards appear as "an anonymous card", never quoted | Each source links to the card or document, only if the viewer may open it | Participants | "No source. Added by hand." |
| Drawer, Owner block | field | Proposed owner and why ("named as owner in the RACI"), or "No owner yet" | Organiser and governance lead: "Change owner" opens a person picker over the intent's people and profile people (accounts linked as in A-043, profile people linked to accounts) | As row | "No owner yet. Lens asks the sponsor." |
| Drawer, Meanings block | list | One line per meaning found, each with where it was found (the "return" case: "return on assets in the finance pack", "return of capital in the board minutes", "returns of goods in the ops log") | Governance lead and owner see "Pick this meaning" beside each line | Participants see the lines; only the settlers see the buttons | "One meaning found." |
| "Edit wording" | button | Opens a text box, up to 2000 characters | `PUT .../glossary/entries/{kpi_id}` with `choice: edited` (Existing); becomes stated by the editor | Organiser, analyst, owner | Disabled on a confirmed term for everyone but the owner |
| "Keep Lens's wording" / "Keep the provided wording" | button | One or both, as the existing screen | Same route with `ours` or `provided` | Same | The "provided" button hidden when no provided wording exists |
| "Not the same term" | button | Undoes a match | Same route with `not_same` (Existing `reject_match`) | Organiser, analyst | Hidden when there is no match |
| Proposal strip | agent line | "Lens has a newer draft: ..." beside a person's wording | "Use it" or "Dismiss" | Whoever owns the wording | Not shown |
| "Confirm all unchanged" | button | Count of unchanged terms not yet confirmed | `POST .../glossary/review-unchanged` (Existing) | Organiser, governance lead | Disabled, "No unchanged terms waiting" |
| Download | button | Excel, printable page | `GET .../glossary/export`, `.../print` (Existing) | Organiser, analyst, sponsor | None |

### Screen B: owner's confirm or correct ("Confirm my terms")

Route `/centre/intent/<id>/define?tab=glossary&view=mine` (a query on the `define` view; the brief's view list has no glossary sub-view, see Open questions). Reuses the owner Confirm page logic (m2_baseline `api/requests.py` `/answer/confirm`, `/answer/question`; ownership by the sign-off rules, A-044b). One screen, one term at a time, a single column at 1280 (max 640 px, centred); at 390 the same column fills the width and the buttons stack.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Progress line | text | "Term 2 of 3. You have 1 question left of 3." | None | The owner | "Nothing waiting for you." with a link back to the Initiative |
| Term card | panel | Term, Lens's business definition draft, the sources in one line, the proposed owner (you) | None | The owner | None |
| "Mine, wording is right" | button | Confirms the term as it stands | `POST .../answer/confirm`; term becomes confirmed by the owner, with name and time | The owner | None |
| "Mine, change the wording" | button | Opens the wording box | Saves as stated by the owner, then confirms | The owner | None |
| "Not mine, it is" | field + button | A person picker, with "I do not know" | Releases the owner cell; the term returns to the organiser as "No owner"; if the term was owner-named by the sponsor the screen says "Ask the sponsor, Daniel" and changes nothing (A-044b) | The owner | None |
| Question card | panel | One ambiguity question, written by Lens in plain words, with Lens's suggested answer labelled "Suggestion" | Pick one of the meanings, or "Both are used" | The owner | Not shown when no open question |
| "Both are used, send to the governance lead" | button | Passes the ambiguity up | Sets the ambiguity to `asked` with the owner's note; the governance lead settles it (Screen C) | The owner | None |
| "Ask me later" | button | Leaves the term draft | Writes nothing; Nira reminds on day 3 and day 7 (the existing request rhythm) | The owner | None |

### Screen C: governance lead settles ambiguities

Route `/centre/intent/<id>/define?tab=glossary&view=ambiguities` (same note). Layout at 1280: list left (36 percent), decision panel right. At 390: list, then decision panel as a full screen.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Ambiguity list | list | One row per ambiguous term: term, number of meanings, owner's reply if any, age | Opens the decision panel | Governance lead, company admin, organiser (read only) | "No ambiguous terms. Every term has one meaning." |
| Meanings table | table | Each meaning: wording, where found, how many cards or documents use it | None | Same | None |
| "Pick one meaning" | button (one per row) | The chosen wording | `POST .../ambiguities/{amb_id}/answer` (Existing); the term takes that wording, status `settled`, term moves to confirmed once the owner has confirmed it | Governance lead | Disabled when the lead is also the only owner and has not confirmed |
| "Keep both, name the second term" | button | A field for the second term's name | Creates a new draft term from the other meaning, owner proposed by Lens; the first term is settled | Governance lead | Optional; hidden if only one meaning remains |
| "Accept as a known risk" | button | A reason field (required, at most 2000 characters) | `POST .../ambiguities/{amb_id}/accept` (Existing; organiser or sponsor or company admin role in the route list, the governance lead role is added, see Rules); term state becomes "ambiguous accepted"; the accepted ambiguity is written as a known risk with reason, name and date | Governance lead | Reason box shows "A reason is required" when empty |
| "Reopen" | button | Visible on a settled or accepted row | Existing `reopen`, with a reason; term returns to draft | Governance lead | Hidden when open |

### Screen D: glossary page in the charter

Route `/centre/intent/<id>/charter`. Embedded in the charter pages owned by file 32 (the page number is file 32's; spec 09 owns sign-off) and in the printed charter. Read only. One column at 1280 (A4 print width), same at 390.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Confirmed terms table | list | Term, business definition, owner, confirmed on, "Reused unchanged" or "Version 3 proposed here" | Row links to the term page (Screen E) | Anyone who may open the charter | "No terms were confirmed in this Initiative." |
| Known risks block | list | Each accepted ambiguity: term, the meanings, who accepted, why, when | None | Anyone who may open the charter | "No ambiguities were accepted." |
| Still open block | list | Draft terms and open ambiguities | None | Participants; a count only for others | Not shown when none |
| Sign-off gate line | agent line | "3 terms are still draft. The charter can be signed with them marked draft." or "Signed with 0 open ambiguities" | None | Sponsor, organiser | Not shown when none |

### Screen E: term page in the Register

Route `/register/terms/{term_id}` (a Register route outside `/centre/intent/...`, so an Open question; NEW line in `RegisterPage`, beside measures). Layout at 1280: two columns, the current definition and owner left, versions and used-by right. At 390: stacked.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Current definition | panel | The company-wide wording, owner, last confirmed on | None | Everyone in the company, except a restricted term (spec 05 rules) | "Not available yet." |
| Versions list | list | `v`, what changed, by, at, which Initiative proposed it (from `sh_platform/graph/versions.py` rows `{v, what, by, at, ref}`) | A row opens the Initiative's charter glossary page if the viewer may open it | Everyone who may see the term | "Version 1. No change since it was first confirmed." |
| Used by | list | Initiatives and measures that use the term | Opens the Initiative card (existence only if not a participant) | Everyone who sees the Initiative | "Not used yet." |
| "Propose a change" | button | Opens the wording box with a reason field | Creates a proposal on the term (not a version yet) | Organiser or participant of an open Initiative, and the owner | Hidden if the viewer is in no open Initiative and is not the owner |
| Proposals | list | Each pending proposal, with who and the owning Initiative | Owner: "Confirm as new version" or "Decline" | Owner, governance lead | "No proposals." |

## User journey (numbered steps from arriving to leaving, with what the agent does between the person's steps)

1. Janet opens an Initiative. At start, the check (spec 22) lists company terms that look related and Janet ticks "Reuse". Reused terms enter the Initiative's glossary as confirmed, tagged "Reused from the company".
2. Agent: when the wall closes, Lens reads the cards, interviews and documents, drafts every term, a definition, a source line, and an owner proposal from the RACI and interviews.
3. Agent: Lens matches each draft term with the company's terms by name, then by meaning. A match with the same wording is "Reused, unchanged". A match with a different wording becomes a proposal and the term shows "Changed".
4. Agent: Lens finds terms with more than one meaning and writes the questions, grouped, one per owner first, never more than three open per person across all of Define (process map, glossary, catalogue and governed state together). The rest go to the governance lead.
5. Agent: Nira puts "Confirm my terms" in Harvey's waiting list and "Settle ambiguities" in the governance lead's list.
6. Katie reads Screen A, edits two wordings, and uploads the family office's own glossary file. Lens re-matches; her wording stays and Lens's newer draft sits beside it as a proposal.
7. Harvey opens Screen B. He confirms two terms, corrects one wording, and answers one question by picking the meaning he uses. He has one question left of three.
8. Harvey marks one term "Not mine, it is Aaron". Aaron's waiting list gets the term; the term is draft until he confirms.
9. Agent: when an owner says "both are used", Lens sends the ambiguity to the governance lead with the owner's note.
10. In the Define session the governance lead opens Screen C. For "return" she picks one meaning for the Initiative's fund reports and names the second term "return of capital". For "exposure" she accepts the risk with a reason.
11. Agent: North updates the stage bar: "Glossary: 12 of 14 confirmed, 2 ambiguous accepted". When nothing is draft, North says "Glossary ready" and unlocks the Glossary line on the build-ready check.
12. Janet opens the charter. Screen D lists the confirmed terms and the known risks. Daniel signs.
13. At closure, each term that changed company-wide enters the company record: the owner confirms the change and a version is added to the term. Janet closes the Initiative.
14. Later, anyone reads the term in the Register (Screen E) and sees the versions and which Initiative made them.

## States and transitions (table: state, who moves it, to what, what is written)

A term in an Initiative has one of three stored states. "Ambiguous open" is a flag (an open ambiguity on a draft term), not a fourth state. Mapping to the existing file: draft means `reviewed` is null; confirmed means `reviewed` is set; ambiguous accepted means an ambiguity with `status: accepted`.

| State | Who moves it | To what | What is written |
|---|---|---|---|
| (none) | Lens, on build or update | draft | An entry in `glossary.json` with provenance "guessed by Lens", source, owner proposal, `change` new, changed or unchanged |
| draft | Owner ("Mine, wording is right") | confirmed | `reviewed {by, at}`; `decided {choice: ours, by, at}` when wording kept |
| draft | Owner or analyst (edit wording) | confirmed (if by the owner) or draft (if by anyone else, with the owner still to confirm) | Wording stated by the editor; `decided {choice: edited}` |
| draft | Organiser or governance lead ("Confirm all unchanged") | confirmed | `reviewed` on each unchanged entry; counted separately in the measure |
| draft | Governance lead ("Pick one meaning") | draft until the owner confirms, then confirmed | Ambiguity `settled`, `resolution`, `by`, `at`; wording updated through `with_chosen_definition` |
| draft | Governance lead ("Accept as a known risk") | ambiguous accepted | Ambiguity `status accepted`, `reason`, `by`, `at` |
| confirmed | Governance lead or organiser ("Reopen", with a reason) | draft | `reviewed` cleared; reason in the entry's history |
| ambiguous accepted | Governance lead ("Reopen") | draft | Ambiguity `reopen`; reason written |
| any | Owner ("Not mine, it is X") | draft with a new or empty owner | Owner cell changed or released; confirmation withdrawn (A-044b) |
| confirmed (Initiative) | Owner of the company term, at closure | a version on the company term | `append_version(plane, term_node_id, what, by, ref)`; ref is the intent id |

A signed charter makes the Initiative's glossary read-only (Existing `SignedGuard`). A change after signature starts a new baseline version, as the existing sign-off does.

## Records read and written (file or route, fields; mark Existing or New)

| Record | Fields | Mark |
|---|---|---|
| `intents/m2_baseline/<baseline id>/glossary.json` (`store/glossary.py`) | `baseline_version`, `provided`, `entries[]` (`kpi_id`, `term`, `aliases`, `business_definition`, `owner`, `frequency`, `data_source`, `who_may_see`, `personal`, `sensitive`, `change`, `previous`, `assumption`, `source_document`, `reviewed`, optional `match`, `matched_term`, `decided`, `proposal`), `matches`, `unmatched_terms`, `rejected`, `documents` | Existing |
| Ambiguities, kept on the measure in `kpis` (`domain/ambiguities.py`, `store/ambiguities.py`) | `id`, `kind`, `text`, `question`, `where`, `raised_by`, `status` open, settled, accepted, `resolution`, `by`, `at`, optional `reason`, `role`, `asked`, `suggestion` | Existing |
| Routes `GET/POST/PUT /api/modules/m2_baseline/baselines/{baseline_id}/glossary...` (build, upload, entries, review, review-unchanged, export, print) | As above | Existing |
| Routes `.../kpis/{kpi_id}/ambiguities/{amb_id}/answer`, `/ask`, `/accept` | As above | Existing |
| Owner answer routes `/answer/confirm`, `/answer/question` (`api/requests.py`) | The owner's reply to a term or a question | Existing |
| Intent record `outcome.glossary` | `{baseline_id, terms, confirmed, draft, ambiguous_accepted, reused, changed}` as numbers and a reference only | New (a pointer and counts, never the terms) |
| Company term store `glossary/company-terms.json` through `sh_platform/jsonfile.py` | `{term_id, term, aliases, definition, owner, state, restricted, created_from (intent id), confirmed_by, confirmed_at}` per term; one record per term | New |
| Company term proposals, in the same file | `proposals[]` of `{id, wording, reason, by, at, intent_id, status pending, confirmed, declined}` | New |
| `graph/versions.json` through `append_version` | `{v, what, by, at, ref}` keyed by term node id (`term:<key>`) | Existing store, new node kind |
| `GET /api/company/graph/node/{id}` | Trail, owner, steward, versions of the node | Existing; extended to serve term nodes |
| `GET /api/intents/{id}/glossary-start` | Company terms matching the Initiative's title, purpose and areas, for spec 22 | New |
| `GET /api/intents/glossary/terms`, `GET /api/intents/glossary/terms/{term_id}`, `POST /api/intents/glossary/terms/{term_id}/proposals`, `POST .../proposals/{id}/confirm` and `/decline` (company-wide, so not keyed by an intent id; see Open questions) | Register and proposal flow | New |

## Fields this feature adds to the intent record

```
# outcome is an object from the moment the intent opens (ruling 6): counts start at 0, baseline_id null
outcome.glossary: {
  baseline_id,                # reference to the m2_baseline baseline; the terms stay in glossary.json
  terms, confirmed, draft, ambiguous_accepted, reused, changed,   # counts only, written on each change
  questions_asked: {<account_id>: n},          # the three-question limit per person, in this Initiative
  governance_lead: account_id|null,
  settled_at: timestamp|null                   # when no term was draft
}
stages[define_strategically].checks.glossary: ready|not_ready   # read by the build-ready check
```

Nothing is renamed. `links.build` is untouched.

## Agent behaviour (North, Lens, Nira: what each drafts, when, and the moment a person acts)

- **Lens** drafts the terms when the wall closes and again whenever a card, interview or document is added: term, aliases, business definition, source line, owner proposal from the RACI and interviews, and the meanings it found. It matches to company terms by name, then by meaning (existing glossary matcher), writes the question for each ambiguity in plain words with a labelled suggestion, and never overwrites a person's wording. Lens never confirms. A person acts: the owner confirms, the governance lead settles.
- **Lens and the question limit (A-045, at most 3 questions per owner):** the cap is three open questions per person across Define, shared with the process map, catalogue and governed state files. Glossary questions count in `outcome.glossary.questions_asked`, which feeds the shared count. It groups ambiguities that share a term, orders them by the number of cards that use the term, asks the person who owns the term, and sends what is left to the governance lead. A-045 sets the limit "per owner in total" and wins when a person owns terms in several Initiatives.
- **North** keeps the glossary line on the stage bar, writes "Glossary: x of y confirmed", nudges the owner whose turn it is on day 3 and day 7 of the time box's share, and tells the organiser when the glossary will not be ready in time with three choices: extend, close with draft terms marked draft, or cancel. A named person picks.
- **Nira** puts "Confirm my terms" and "Settle ambiguities" into the right waiting lists and sends the existing reminder rhythm. She never writes a term.
- **Reuse at start:** at initiative start (spec 22), Lens lists the company terms that match the title, purpose and areas. A person ticks "Reuse". North never ticks it.
- Agents never sign and never accept a risk.

## Rules (visibility, time box, who may do what)

- Visibility follows the intent (spec 05 as corrected by the brief's ruling 4). A participant or observer (reads, never writes) sees terms. An affected person sees the glossary counts only, and the terms only when the organiser switched on "affected people may read" at creation (default off) or the person is named on a share. A draft intent is visible only to who started it. A person sees a term only if they may open the Initiative, and a term of a restricted measure shows as "A restricted measure" without id or count to anyone the measure does not admit (Existing `sees` rule).
- Sealed and anonymous cards are never quoted in a source line. The line says "an anonymous card".
- A term has one definition company-wide. An Initiative that finds a different wording makes a proposal. The proposal becomes a version only when the term's owner confirms it (the governance lead when the term has no owner), at closure of the Initiative or earlier.
- An owner confirms only a term they hold (sign-off ownership logic). A name-only owner holds a term only when exactly one account has that name or the profile person is linked (A-043 and A-044b).
- "Not mine" acts only on the cell that made the person the owner. A sponsor-named owner is told to ask the sponsor.
- Only the governance lead, the sponsor or the company admin may settle or accept an ambiguity. Accepting needs a reason. Everyone else reads the decision.
- At most three open questions per person across Define, all four areas together (A-045). A fourth goes to the governance lead.
- The glossary is ready for the build-ready check when no term is draft and no ambiguity is open. A term accepted as a known risk counts as ready.
- The charter can be signed with draft terms only if the sponsor ticks "Sign with draft terms marked as draft"; the page then prints them in a "Still open" block.
- Time box: the glossary lives inside Define strategically (default 6 working days of the 10). An extension is the intent's extension (spec 07).
- Dates and times use the company's time zone from the profile, else UTC.
- Past Initiatives keep their glossary, read only, as part of the closed record.
- A signed baseline is read-only; every write route is refused by `SignedGuard`.
- Real client data never leaves the machine. Model calls go through the egress gateway with names tokenised (existing `glossary_lens`).

## Counters and measures of this feature (numbers only, each traced to a record)

| Measure | Definition | Trace | When there is no data |
|---|---|---|---|
| Terms drafted | Count of `entries` plus `unmatched_terms` | `glossary.json` | "Not available yet. Lens has not drafted." |
| Terms confirmed | Entries with `reviewed` set | `glossary.json` (`counts().reviewed`) | Same |
| Ambiguous terms raised, settled, accepted | Count of ambiguities by `status` | kpis in the baseline | "0" |
| Questions asked per person | `questions_asked` per account (a count for that person only; no per-person average or ranking exists, ruling 15 spirit) | intent record | "0" |
| Reused terms | Terms whose entry has `matched_term` and a company term id | `glossary.json` and `company-terms.json` | "No company terms yet." |
| **Definitions confirmed unchanged** | Reused terms whose `change` is `unchanged` and `reviewed` is set, over reused terms. Shown as "7 of 9". Terms with a proposal count as "changed" | `glossary.json` (`change`, `reviewed`) | "Not available yet. No term was reused." |
| Versions added | Count of `append_version` rows with `ref` = this intent id | `graph/versions.json` | "0" |
| Time to confirm | Days from Lens's first draft (`at`) to `reviewed.at` for the last term | `glossary.json` | "Not available yet." |

Counts are exact. Any mean or median (such as time to confirm over several Initiatives) shows "Fewer than five" below five records. No figure is shown without its record. Groups below five are shown as a count, never a name (egress rule 1) in the super admin and counters view.

## Reuse check (what exists today: file paths and line ranges found with graft; copied, reshaped or not used, and why)

Paths checked with `ls` and `wc -l` on 7 Oct 2026: all files below exist. Searches run: `graft ask` on glossary, ambiguity and versions; direct reads of the files below; grep for "not mine", "three questions", "A-043", "A-045".

| Found | Decision |
|---|---|
| `modules/m2_baseline/domain/glossary.py` (381 lines): `build_entries` 272 to 296, `decide` 303 to 318, `reviewed` 332 to 335, `counts` 363 to 365, `glossary_ready` 368 to 381, `flat` 349 to 360 | Existing. Reused unchanged: states, matching, provenance, counts, readiness |
| `modules/m2_baseline/store/glossary.py` (311 lines): `build`, `view` 158 to 176, `review_unchanged` 292, `reject_match` 269, `glossary_ready` 305 | Existing. Reused unchanged |
| `modules/m2_baseline/api/glossary.py` (176 lines): routes 91 to 173 | Existing. Reused; the Initiative calls them with its baseline id |
| `modules/m2_baseline/domain/ambiguities.py` (202 lines): `make`, `settle` 136, `accept` 142, `reopen` 186, `open_count` 157; `store/ambiguities.py` `answer` 87, `accept` 105, `for_owner` 119, `mark_asked` 158 | Existing. Reused unchanged: the "three meanings of return" case, accept as a known risk, reopen |
| `modules/m2_baseline/agent/glossary_lens.py` `match_by_meaning` | Existing. Reused; extended to match against company terms as well as the provided glossary |
| `modules/m2_baseline/api/requests.py` `/answer/confirm`, `/answer/question`, `_owner_questions` 269 | Existing. Reused for Screen B; no second owner page |
| `ui/src/modules/m2_baseline/glossary/GlossaryScreen.tsx`, `glossaryApi.ts`, `copy.ts` | Existing. Grafted into the Define right panel as the tab body |
| `ui/src/pages/BaselinePage.tsx` lines 130 to 160 (`GlossaryCard`, "Glossary term" side card) | Existing. Grafted as the term summary on a cluster or measure card; no rebuild |
| `sh_platform/graph/versions.py` `append_version` 40 to 49, `plain_versions` 110, `GET /api/company/graph/node/{id}` 180 | Existing. Reused for term versions; term nodes added |
| `sh_platform/graph/register.py` and `ui/src/pages/RegisterPage.tsx` | Existing. Reshaped: the glossary page in the Register is a new line in `RegisterPage` (NEW); change owned by files 12 and 32 |
| `sh_platform/jsonfile.py`, `sh_platform/profile/view.py` | Existing. Reused for the new company term file and per-viewer filtering |
| A company-wide term store with one definition per term | Not found. New: `glossary/company-terms.json` and the proposal flow |
| A governance lead role | Not found as a named role. Open question |
| Per-Initiative question counter | Not found. New: `questions_asked` on the intent record |

## Not in this feature

- The technical glossary, catalogue and process map (other specs in this folder).
- Settling ambiguities in the technical definition (period, currency, calculation); those stay on the catalogue side.
- Importing a whole company glossary system by connector.
- Translating terms.
- Deleting a term. Nothing is deleted; a term is retired with a reason.
- Choosing an industry pack's glossary as company policy. Pack terms are suggestions only.
- Voting on definitions.

## Open questions

1. Who is the governance lead? Proposed: the company admin by default, or the person the sponsor names in the Initiative's people. The route list for accept names organiser, sponsor and company admin only; a named governance lead needs the route role added.
2. Settled by ruling 9: the limit is A-045 (at most 3 questions per owner), shared across Define. Open: does an owner's count span several Initiatives? Proposed: yes, as A-045 says "in total".
3. Ranking of questions when a person owns more than three ambiguous terms. Proposed: by number of cards that use the term. No threshold invented.
4. Routes outside the brief's convention: `/register/terms/{term_id}`, `define?tab=glossary&view=mine|ambiguities`, and company-wide `/api/intents/glossary/terms...`. The Register change is owned by file 12 ("Intents I was in") and file 32 (charter pages); the glossary page in the Register is a new line in `RegisterPage`. Orchestrator to confirm the spellings.
5. Who may retire or merge a company term? Proposed: the owner with the governance lead.
6. Does a version need both the owner and the governance lead, or the owner alone? Proposed: the owner alone, with the governance lead named for a term with no owner.
7. Can a term exist company-wide without a measure? The existing glossary has one entry per measure; terms found in cards that map to no measure sit in `unmatched_terms`. Proposed: allow a term record without a measure id, shown "Not yet a measure".
8. Should an accepted ambiguity expire and come back for review? Proposed: a review date of one quarter, as the Future shelf does. Not set until Nitin decides.
