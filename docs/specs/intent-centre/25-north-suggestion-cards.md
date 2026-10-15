# 25. North's suggestion cards (wall and brainstorm)

Part of: Intent Centre v2. Depends on: 01 (intent record), 02 (intent types), 07 (time box and stage clock). Feeds: 04 (home, "waiting for you" lines), 09 (closure counts).

## Purpose (three sentences)

A blank wall is hard to start, so North drafts dashed suggestion cards from the industry pack, the company's own documents and the person's own interview notes, at most three per lane on an Initiative wall and at most three in total in a Brainstorm (file 36 gives a Brainstorm one lane). A suggestion is only a draft: it is not a card, not counted and not seen by anyone else until the person picks it up, and it is dropped when the wall freezes. North never states a figure, never reads a sealed file and never suggests from another person's private notes.

## Who uses it and when (role, moment, trigger)

| Role | Moment | Trigger |
|---|---|---|
| Participant (Aaron) and organiser (Janet), as a person with a private room | Opening the wall in an Initiative (Think unfiltered) or the Think alone stage of a Brainstorm | North seeds the person's suggestions the first time they open their room |
| Same person | A new document lands in Bring what you have while the window is open | North tops up that person's suggestions, within the same cap |
| Analyst (Katie), sponsor (Daniel) | As participants, the same as above | Same |
| Company admin, super admin | Never as a picker | They see the counters only (section "Counters"), never a person's suggestions |

North drafts. The person decides: Pick it up, Not this one, or leave it alone.

## Entry points (every route, link, Pulse line, button that leads here)

- Wall screen at `/centre/intent/<id>/wall`, own lane view: dashed cards appear in the lane they belong to (`ui/src/modules/m1_intent/wall/Lane.tsx`).
- Brainstorm, Think alone stage: the same wall component at the same route, opened from the Brainstorm intent page (spec 02, stage `think_alone`; one lane, file 36).
- Intent Centre home (04), "Waiting for you" line: "North has N suggestions for your wall" (N is the count of the person's `offered` rows in `wall_suggestions/<session>.json`) is shown only while the person has at least one unhandled suggestion and the window is open. The line opens the wall.
- Bring what you have (context shelves): after an upload, a toast "North may add suggestions to your wall" with the button "Open the wall". Shown to the organiser and the uploader only.
- Routes. Existing wall routes stay where they are:
  - `GET /api/modules/m1_intent/sessions/{session_id}/room` seeds and returns the person's suggestions (Existing, `private_room.py`, seed call at line 423).
  - `POST /api/modules/m1_intent/sessions/{session_id}/room/notes` with `{from_suggestion: id}` picks one up (Existing, `private_room.py` line 474, `_pick_up` at 503).
  - New routes follow the brief's convention (`/api/intents/...`):
    - `POST /api/intents/{intent_id}/suggestions/{id}/hide` New: the Not this one tap.
    - `POST /api/intents/{intent_id}/suggestions/{id}/unhide` New: Undo.
    - `POST /api/intents/{intent_id}/suggestions/refresh` New: called by the UI when Bring what you have reports a new document; North tops up.
  - Whether these wrap the session routes or replace them is Open question 8.

## Screens, element by element

No new screen. The suggestion card sits inside the wall's own lane view. The Brainstorm Think alone stage uses the same wall.

### Screen: Wall, own lane view

Route: `/centre/intent/<id>/wall` (brief section 10, ruling 1; today `WallScreen.tsx`). In a Brainstorm the same route shows one lane.

Layout at 1280: three regions. Left, the lane columns (Intent, Pain point, Future signal, Lever: `LANES` in `WallScreen.tsx` line 18; a Brainstorm shows its single idea lane, file 36). The rule and footer below repeat in each lane drawn. Right, the North panel (`NorthPanel.tsx`). Top, the stage bar. Suggestion cards sit under the person's own cards in each lane, below a thin rule titled "Suggested by North".

Layout at 390: one lane at a time with swipe between lanes; the North panel is a sheet. Suggestion cards stack under the person's cards; Pick it up and Not this one sit on one row, as full-width tap targets (minimum height is Open question 7). The source line wraps to two lines.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Suggestion card | list item, dashed border, no quarter edge | The suggestion text (one or two sentences, words only) | Nothing on card tap | The one person it was drafted for | The group "Suggested by North" is not drawn when the lane has none |
| Source line | chip under the text | "Suggested by North, from <document>" (existing word from `contracts/wall_questions.yaml`, `suggested_label`). For a pack: "Suggested by North, from the Family office pack". For an interview: "Suggested by North, from your interview" | Tap opens a small popover: document title, the shelf it sits on, and for a document, the opening of the passage North used (length is Open question 5; names masked as in `retrieval.mask_names`) | Same person | Never empty: a suggestion with no source is not shown (existing rule in `notes_quarters.suggest`) |
| Pick it up | button | "Pick it up" (while sending: "Picking it up") | Calls the pick-up route. The suggestion vanishes and a real card appears in the person's lane, unconfirmed, with q1 filled as a draft; North then asks the other questions as for any card | Same person | Disabled while the window is closed; the group is not drawn once the wall is frozen |
| Not this one | text button | "Not this one" | Hides the suggestion for this person only. The card fades out with an "Undo" link for a short time (Open question 6). North does not draft it again for this person | Same person | Not drawn when there is no suggestion |
| Lane footer line | agent line (North) | "No more suggestions in this lane" when the person has handled all they were offered; "North has nothing to suggest here yet. Add a document in Bring what you have, or write your own." when the lane has none and the person has shared nothing | Link "Bring what you have" opens the context shelves | Same person | This is the empty state (a Brainstorm shows it once, under its one lane) |
| North panel line | agent line (North) | After a top-up: "I added 2 suggestions from Board paper 2026.pdf." After a hide: nothing | None | Same person | Not drawn when no top-up happened. N is the count of rows North wrote in that run |
| Pack label | chip | "Industry practice (suggestion): what others in the industry usually track" (existing `SUGGESTION_LABEL` in `sh_platform/packs.py`) | None | Same person, on pack suggestions only | Not drawn without a pack (no pack, no pack cards) |

Picked-up card: the existing card with a quarter edge (`Card.tsx`), dashed border gone, a small line "From a suggestion, <document>" kept under the text. The card is unconfirmed until the person taps Keep, Change or Anonymous, exactly as today.

## User journey (numbered steps from arriving to leaving, with what the agent does between the person's steps)

1. Aaron opens the wall for the first time. The room route runs.
2. North (agent, no model call needed for the pack part) gathers candidates from three sources (section "Agent behaviour"), drops any whose text matches a card or a hidden suggestion, and keeps at most three per lane (three in total in a Brainstorm, which has one lane). It writes them as the person's suggestions.
3. Aaron sees up to three dashed cards in the Lever lane, each with its source line. In a Brainstorm he would see up to three in total, in its one lane.
4. Aaron taps "Pick it up" on one. The card becomes his own, unconfirmed. North asks the next question on that card.
5. Aaron taps "Not this one" on another. It fades; Undo is offered briefly (Open question 6); North never offers it to him again.
6. Janet uploads "Board paper 2026.pdf" in Bring what you have. The context layer finishes reading it. The wall of every person who may see that shelf is marked "has new documents".
7. When Aaron next has the wall open (or opens it), the UI calls refresh. North reads only the shelves Aaron may see, drafts new candidates, and fills the lane up to the cap, counting his picked-up and hidden ones against nothing (a picked-up suggestion is a card, so it leaves the cap).
8. Aaron picks or ignores. Nothing he ignores is counted.
9. The window closes (frozen wall, spec 07). North drops every unhandled suggestion for everyone. The counters keep numbers only.

## States and transitions (table: state, who moves it, to what, what is written)

| State of one suggestion | Who moves it | To what | What is written |
|---|---|---|---|
| (none) | North, at wall open or top-up | `offered` | Row in `wall_suggestions/<session>.json` under the person's seat; counter `suggested` +1 (see Counters) |
| `offered` | The person taps Pick it up | `picked_up` (the row is taken out) | A real card in the person's transcript (`source: {kind: "suggestion", from: <source>}`); counter `picked_up` +1; `cards_new` +1 as for any new card |
| `offered` | The person taps Not this one | `hidden` | Suggestion id added to the person's hidden list; the row is removed from what the person sees; counter `hidden` +1 |
| `hidden` | The person taps Undo within the Undo time | `offered` | Hidden entry removed; counter `hidden` -1 |
| `offered` | The window closes (stage `wall` ends) | `dropped` | The file is deleted (`SuggestionStore.drop`); `suggested` and `hidden` counts stay in the intent's counters; nothing else remains |
| `picked_up` card | The person, as for any card | Keep, Change, Anonymous, seal | Existing note rules; no special treatment |

A suggestion is never a card, never on the shared wall, never sent to the board and never in the charter. Only the picked-up card is.

## Records read and written (file or route, fields; mark Existing or New)

| Record | Read or written | Fields | Status |
|---|---|---|---|
| `wall_suggestions/<session>.json` in the company plane (`SuggestionStore`, `modules/m1_intent/store/notes.py:180`) | Read, write, delete at close | `{seat: [{id, text, kind, suggested: true, from, label}]}` | Existing. This feature adds `source_kind` (pack, document, interview) and `doc_id` to each row |
| Same file, new key `hidden` per seat | Write | `{seat: {hidden: [id]}}` or a sibling `wall_suggestions_hidden/<session>.json` | New (Open question 1) |
| Hide keys | Read at each draft | Suggestion ids are a hash of `kind` and normalised text (existing `notes_quarters.suggest`), so a hidden id blocks the same text from any source | Existing id, new list |
| `packs/<industry>/` through `PackLoader` (`sh_platform/packs.py`), via `tools/pack_tools.kind_suggestions` | Read | Pack problems and measures as words | Existing |
| Company documents: `sh_platform/context_docs` `DocStore.documents_for(agent, restricted_ok=False)` and the profile `inputs.*.findings` cells read through `sh_platform/profile/view.py` | Read | Document title, shelf, Lens findings (`kind`, `text`, `from`) | Existing |
| Interview notes: `domain/interview_notes.py` and `ctx.interview_answers()` | Read, the viewer's own only | The person's own answers | Existing |
| The person's transcript (`TranscriptStore`) | Written on pick-up | A normal note | Existing |
| `SessionStore.count` and the intent's counters (`store/sessions.py:127`) | Written | Numbers only | Existing, three new keys (`suggested`, `picked_up`, `hidden`) |
| Run log (`sh_platform` run log) | Written | One line per draft run: person seat, source kinds used, count kept. No text | Existing log, new event name `suggestions_drafted` |

## Fields this feature adds to the intent record

Under `outcome`-independent counters on the intent (spec 01 allows added fields, never renamed ones):

```
intent.suggestions: {
  suggested: int, picked_up: int, hidden: int,
  by_source: {pack: {suggested, picked_up}, document: {suggested, picked_up}, interview: {suggested, picked_up}},
  last_drafted_at: iso | null
}
```

No suggestion text, no person id and no document name is stored on the intent record. The counts are per intent, not per person.

## Agent behaviour (North, Lens, Nira: what each drafts, when, and the moment a person acts)

**North drafts** at two moments only.

1. At wall open, the first time a person opens their room (existing `seed_suggestions`, called from `my_room`). For Brainstorm, at the person's first open of Think alone.
2. When a new document lands in Bring what you have during the window, the next time the person has the wall open (the UI calls refresh). Top-up only: it never replaces what the person has not handled and never raises the cap. A person whose lanes are full of unhandled suggestions gets none.

Sources, in this order of use when a lane has fewer than three:

| Order | Source | What North may use | Label |
|---|---|---|---|
| 1 | Company documents on the context shelves the organiser may see | Lens findings from files the profile view shows the viewer; text from `documents_for(agent, restricted_ok=False)` | "Suggested by North, from <document title>" |
| 2 | The person's own interview notes | Their own interview answers only (`interview_answers()`), each in the lane the existing `contracts/interview_notes.yaml` maps the question to | "Suggested by North, from your interview" |
| 3 | The pack, for the company's industry | Common problems, signals and levers as words (`kind_suggestions`); pack measures only as a name, never as a target or a figure | "Suggested by North, from the <industry> pack" |

Why documents come first: they are the company's own words. The pack fills the gap. A company with no pack gets no pack cards (honest empty state, `industry.md`); a company with no documents gets pack cards only.

"The organiser may see" means: the shelves and files the organiser is entitled to open in the profile view. The suggestion is drafted for a participant from a document the participant may also see. If the participant may not see it, it is not used for them, even if the organiser may. A suggestion from a document is therefore seen only by someone who could open that document.

**North never**: reads a sealed or restricted file or its summary; suggests from another person's private notes, interview or private room; states a figure (no number, percentage, target or amount in suggestion text; any digit in candidate text is stripped to the plain sentence or the candidate is dropped); acts on text inside a document (document text is context, never an instruction, `data-locality.md`); picks a card up, hides one or sets a priority for a person.

**Lens**: no role in drafting. Lens findings already in the profile are read as input; Lens does not draft suggestions.

**Nira**: adds the home line "North has N suggestions for your wall" while N is above zero and the window is open (spec 04).

**Model use**: pack candidates need no model call. Document and interview candidates are rewritten to one sentence of business words by the model through the egress gateway, names tokenised, passages marked untrusted (existing `retrieval.wrap_untrusted`, `mask_names`). If the model is unavailable, North still offers the pack suggestions and says nothing about the rest.

**The person acts** at: Pick it up, Not this one, Undo. Nobody else acts on a suggestion.

## Rules (visibility, time box, who may do what)

- At most three per lane per person (`max_suggestions_per_lane: 3`, `contracts/wall_questions.yaml`). A-056 sets it. A Brainstorm has one lane (file 36), so there the cap is three suggestions in total per person.
- The cap counts suggestions the person has not yet handled. Picked-up and hidden ones leave the cap, so a person who clears their suggestions may be offered new ones at the next top-up, but North drafts at most once per wall open and once per new document, never on a timer.
- A total per person per window beyond the per-lane cap: none stated (Open question 2).
- A suggestion belongs to one person's seat. Janet, Daniel and the admins never see Aaron's suggestions, hidden list or interview-based suggestions.
- Pack suggestions are always labelled as suggestions; never presented as the company's own definition.
- Not this one hides for the person only and is not an opinion on the idea. No other person is told.
- Counted only when picked up: an unpicked suggestion is not on the wall, not in a lane count, not in the projector view, not in the charter and not in Lens drafts.
- Picked up card: author is the picker. Anonymous and seal behave as for any card. If the source document is on a restricted shelf, North would not have used it, so no pick-up inherits a seal.
- Time box: suggestions are available only while the wall stage is open (spec 07 clock, company time zone from the profile, else UTC). At freeze, dropped. An extension of the window keeps them.
- Pick up when the suggestion is gone: "That suggestion is no longer there." (existing words); the wall refreshes.
- Anonymous cards: picking up and then tapping Anonymous removes the author name from the card as usual; the counters never carry a person.

## Counters and measures of this feature (numbers only, each traced to a record)

| Measure | Traced to | Shown where |
|---|---|---|
| Suggested (offered) | `intent.suggestions.suggested`, incremented in `SessionStore.count` when North writes rows | Closure summary (09) as "North offered N suggestions" |
| Picked up | `intent.suggestions.picked_up`, incremented when `_pick_up` takes a row | Closure summary: "N were picked up" |
| Picked-up share | `picked_up` divided by `suggested`; shown as a percentage only from five suggestions, otherwise "Fewer than five" (brief section 10, ruling 8) | Closure summary, company admin view |
| Hidden (Not this one) | `intent.suggestions.hidden` | Company admin view only |
| By source kind: pack, document, interview | `intent.suggestions.by_source.<kind>` | Closure summary, one line per kind, a kind with 0 suggested is not shown |
| Cards from suggestions that survived to the frozen wall | Count of notes with `source.kind == "suggestion"` on the frozen wall | Charter page one footer: "N cards began as suggestions" |

Rules for the numbers: they are counts, never names or text; nothing is split by person. Where a record is missing the screen says "Not available yet" and names the missing record (for example "Not available yet: this wall was frozen before suggestions were recorded").

## Reuse check (what exists today: file paths and line ranges found with graft; copied, reshaped or not used, and why)

All paths below were checked to exist on 7 Oct 2026. Searches run: `graft ask "suggestion cards pick up"`, `graft ask "wall suggestions store"`, `graft callers seed_suggestions`, `graft skeleton` on the files below.

| Existing | Where | Decision |
|---|---|---|
| Cap and filter: `suggest`, `from_pack`, `pick_up`, `drop_suggestions` | `modules/m1_intent/domain/notes_quarters.py` (the four functions named; lines not re-checked, find with `graft skeleton`) | Copied as is. Pick-up already writes a card with `source: {kind: "suggestion", from}` and `confirmed: False`. Reshaped: add `source_kind` and `doc_id` to rows; add a `hidden` filter argument |
| Per-session store | `modules/m1_intent/store/notes.py:180` (`SuggestionStore`: get, put, take, drop) | Reused. Reshaped: add `hide` and `hidden` helpers; `submit_all` already drops the file at close |
| Seed at room open | `modules/m1_intent/api/private_room.py:200` (`seed_suggestions`, called at line 423) | Reshaped. It uses only the profile's findings and the pack today. Add the interview source and the top-up call; keep the "once per person" guard for the first seed only |
| Pick-up route | `modules/m1_intent/api/private_room.py:480` and `_pick_up` at 503 | Reused unchanged apart from the counter write |
| Wording | `modules/m1_intent/contracts/wall_questions.yaml` (`suggested_label`, `max_suggestions_per_lane`) | Reused. One new words key: `not_this_one`, `undo` |
| Pack text | `modules/m1_intent/tools/pack_tools.py:82` (`kind_suggestions`), `sh_platform/packs.py` (`SUGGESTION_LABEL`, `PackLoader`) | Reused; this spec uses the pack for problems and levers as words. Pack measures as suggestion cards are New and limited to the measure's name |
| Company documents | `sh_platform/context_docs/store.py` (`documents_for`, restricted flag), `retrieval.py` (`wrap_untrusted`, `mask_names`, `retrieve`) | Reused for the document source and the passage popover. Not reshaped |
| Profile view limits | `sh_platform/profile/view.py` (`sees_source`, restricted-file filter around lines 155 to 160) | Reused as the visibility gate for document candidates |
| Interview source | `modules/m1_intent/domain/interview_notes.py`, `private_room.py` `interview_answers`, `seed_from_interview` | Reused. Today the interview becomes the person's own drafts; this spec adds none of that again. Interview suggestions are for answers North has not already drafted as cards |
| UI | `ui/src/modules/m1_intent/wall/Card.tsx`, `wall/copy.ts`, `ui/src/modules/m1_intent/private_room/roomApi.ts` (`pickUpSuggestion`), `WallScreen.tsx` (`handlePickUp`) | Reused. Reshaped: add Not this one, Undo and the lane footer line |
| Tests | `modules/m1_intent/tests/test_m1_wall_questions.py` (cap, two industries and an empty company, drop at close); `ui/src/modules/m1_intent/wall/wall.test.tsx` (pick up, error) | Ported and extended; not rewritten |
| Nothing exists for | Hide for the person, top-up on a new document, interview as a suggestion source, source-kind counters, Brainstorm entry | New, small. Searched: "dismiss", "hide", "refresh suggestions" in `modules/m1_intent` and `ui/src/modules/m1_intent`: no hits |

## Not in this feature

- A suggestion shown on the shared wall, the projector view or to the organiser for other people.
- Suggestions on Define, Charter, Pulse, Problem or Decision screens.
- Nira or Lens drafting suggestion cards.
- A figure, target or owner in a suggestion.
- A global "Not this one" that teaches North across companies; hiding is per person per wall.
- Reading sealed or restricted files, in full or in summary.
- The wall's own lanes, quarter edge, seal tap and charter page (existing, unchanged).

## Open questions

1. Where should "hidden" live: a key inside `wall_suggestions/<session>.json` or a sibling file? A sibling file keeps the existing store shape; the builder picks.
2. Should the window have a cap on total suggestions per person (for example, at most three top-ups)? The v1 rule caps only what is on the screen. No number is invented here.
3. Brainstorm has one lane (file 36), so three suggestions in total. Which pack kinds (problem, signal, lever) feed that lane is not settled; confirm with 36.
4. Should the organiser see, as a number only, how many suggestions each lane has been offered, to judge whether the pack is useful? Counters are per intent today.
5. Passage popover: is a 200-character passage from a shared document acceptable, given D-032 limits what may leave? It stays on the screen and does not leave the machine, but the document owner may not expect it. Confirm. The passage length is not set (200 characters was drafted earlier, not a rule).
6. How long should Undo last, and does it survive a page refresh? 8 seconds was drafted earlier, not a rule. This spec says it does not survive a refresh.
7. Minimum tap-target height at 390: confirm the house UI rule and state it.
8. Do the new hide, unhide and refresh routes live under `/api/intents/...` as written, or wrap the existing session routes? File 01 decides.
9. Observers never write (ruling 4): this spec assumes no suggestions are drafted for observers. Confirm.
