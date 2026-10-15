# 24. The card model

Part of: Intent Centre v2. Depends on: 00-BRIEF, 01 (intent record), 06 (people and roles), 07 (time box and stage clock). Feeds: the wall file, Define (clusters and shelves), 36 (brainstorm session), 09 (closure), the frozen wall in the charter.

## Purpose (three sentences)

A card is one thought from one person: the unit of a wall in an Initiative and the unit of a brainstorm. This file defines the card record, the form a person fills, the seal and anonymous taps, who may edit, withdraw or move a card, how a card looks on the wall and opened, and the single-quarter card used in a brainstorm. It reuses the profile `cards` section (A-053) and the v1 wall card component and adds only what edit, withdraw, move history and the intent link need.

## Who uses it and when (role, moment, trigger)

| Role | Moment | Trigger |
|---|---|---|
| Any participant (Aaron, Katie) | Adds, edits, withdraws, seals or anonymises their own card while the wall is open | "Add a card", "Talk to North" (North drafts from the interview) |
| Organiser (Janet) | Reads cards, moves none in Think unfiltered, closes the wall | Wall stage bar |
| Committee (Janet, Daniel, Katie) | Moves a card to another cluster in Define (Initiative) | Drag, or "Move to" menu on the open card |
| Brainstorm participant (Aaron, Katie) and organiser | Moves a card between groups in the group phase of a brainstorm session. File 36 owns this rule and its screen | "Move to group" menu or drag in the session (36) |
| Sponsor (Daniel), company admin | Reads cards the seal and anonymous rules allow | Wall, frozen wall |
| North (agent) | Drafts a card from an interview answer or a document; fills a quarter marked guessed; adds suggestion cards | Interview answer, "North, fill this from the files" |
| Lens (agent) | Reads cards (never sealed ones into drafts others see) to propose clusters and shelves in Define | Define opens |

## Entry points (every route, link, Pulse line, button that leads here)

- Wall screen, button "Add a card" in each lane header, and "Talk to North" (the conversation panel, `NorthPanel.tsx`) which ends in "Put it on the wall now".
- A suggestion card from North, button "Pick it up to make it yours" (opens the form prefilled).
- Own card on the wall, menu "Edit" or "Withdraw"; any visible card, click to open it.
- Define board, "Move to" menu on a card (committee only).
- Brainstorm live session (36), the idea box "Add your idea" (single-quarter card), reached at `/centre/intent/<id>/session`. In the group phase 36 also offers "Move to group" on a card; the move record is defined here, the rule and screen are 36's.
- Pulse line from Nira: "You have a card North drafted. Confirm it or drop it."
- Route family: `POST /api/intents/{intent_id}/cards`, `PATCH .../cards/{card_id}`, `POST .../cards/{card_id}/withdraw`, `POST .../cards/{card_id}/move`, `GET .../cards`, `GET .../cards/{card_id}`. Existing wall routes in `modules/m1_intent/api/private_room.py` and `notes.py` stay; the new routes wrap them (see Reuse check).

## Screens, element by element

### Screen A: the card form (a drawer on the wall, a full page at 390)

Route: a drawer on `/centre/intent/<id>/wall` (no page route of its own at 1280); at 390 the same view shows it full screen. Drawer state is carried as `?card=new` and `?card=<card_id>&edit=1`. Any separate page route is Open question 9.
Layout at 1280: right-hand drawer, 480 px wide, wall still visible. Top: lane chooser. Middle: four quarter fields stacked. Bottom: seal and anonymous taps, then the action row. At 390: full-screen page, same order, action row pinned to the bottom, each quarter collapses to a one-line header that expands when tapped.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Lane chooser | Segmented control (4) | TRACKING NOW, MISSING, WATCH, LEVERS with their one-line meaning (`wallCopy.lanes`) | Sets `lane`. Disabled in edit when the card is already on the wall, with the note "Change the lane from the card menu" | Author | "Choose a lane" until one is picked; Put it on the wall stays off |
| Quarter 1 field | Text field, with voice button | The wall question for q1 (business words: what is it called and means), from `wall_questions.yaml` | Saves as a cell `{value, mark: stated, by, from: "Typed by you"}` | Author | Empty, hint "Type, or press the microphone" |
| Quarter 2 field | Text field | q2: where it bites | Same | Author | Same |
| Quarter 3 field | Text field | q3: tracked today, and the source | Same | Author | Same |
| Quarter 4 field | Text field | q4: technical definition | Same | Author | Same |
| "North, fill this from the files" | Button, one per quarter | Label; while running "North is reading your files" | North looks only at documents on the author's own shelf (`_passage` in `private_room.py`). On a hit the field fills with the passage, mark becomes `guessed`, and a line names the document ("Read from: Treasury policy 2025"). On no hit: "North found nothing in your files for this. Type it, or leave it empty." | Author | Disabled with "No documents shared yet" when the author has none |
| Guessed tag | Chip on a filled quarter | "Guessed, from <document name>" | Opens the document title. "Yes, still right" turns mark to `stated`. Editing the words also turns it to `stated` | Author | Not shown |
| Count line | Text | "n of 4 answered" and "k guessed" | None | Author | "0 of 4 answered" |
| Seal tap | Toggle | "About people, pay or personal data (seal it)" | Sets `sealed`. Shows the silhouette preview under the toggle: "Others will see: A sealed card about <area>" | Author | Off |
| Anonymous tap | Toggle | "Hide my name". Under it: "Nobody can see who wrote this, not the organiser, not an admin" (D-013) | Sets `anonymous`. Shown only when the intent's names rule is "choice"; when the rule is fixed the tap shows its fixed value, disabled, with the reason | Author | Off. Hidden or disabled as above |
| Put it on the wall | Button | Primary | Needs two of four answered (A-055). Writes the card and closes the drawer. Below two: the button is off and the line reads "Answer at least two of the four questions first, then it can go on the wall." (`wallCopy.needTwo`) | Author | Off |
| Save as draft | Button | Secondary | Keeps a private draft (`on_wall: false`); only the author sees it | Author | Off when nothing typed |
| Cancel | Button | Text | Closes. If anything typed: "Keep this as a draft?" Keep or Discard | Author | None |
| Error line | Text | "That did not work. Try again." with Try again | Repeats the save | Author | Not shown |

### Screen B: the card on the wall (component, in a lane)

Route: part of `/centre/intent/<id>/wall` (the Define board at `/centre/intent/<id>/define` reuses the same component). At 1280 a lane column of cards; at 390 one lane at a time with the lane switcher.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Edge | Four-segment bar, left | The first n segments filled from the bottom in the lane colour, n = quarters answered (guessed ones count). Quarters that are `unknown` are not filled | None | Everyone who sees the card | Zero segments filled (a draft with nothing) |
| Card text | Text | The q1 words; if q1 is empty, the first answered quarter | Click opens the card (Screen C) | Everyone who sees the card | "(No words yet)" on a draft the author sees |
| Foot line | Text | Initials of the author, or nothing. Then "n / 4" and "· k guessed" | None | Everyone who sees the card | Anonymous card: foot shows "Anonymous" and no initials. Names rule "anonymous": same |
| Sealed silhouette | Card variant, striped | "A sealed card about <area>" and "Sealed". No words, author, quarters or source reach the page | Click does nothing for those not allowed; for those allowed (see Rules) it opens as a normal card | Everyone not allowed to see it | "A sealed card about a restricted area" when no area is named |
| Withdrawn mark | Chip | "Withdrawn" and a grey card, words hidden from everyone but the author and company admin | Click opens a read-only view | See Rules | Not shown |
| Draft mark | Chip | "Draft, only you see it" | Click opens the form | Author | Not shown |
| Card menu | Menu (three dots) | Edit, Withdraw, Change lane (own card); Move to cluster (Define, committee); in a brainstorm group phase, Move to group (36) | Opens the matching form or confirm | Author, committee as stated; participants and organiser in a brainstorm group phase | Not shown when the wall is frozen or the viewer has no action |
| Suggestion card | Card variant, dashed | "Suggested by North, from <document>" and "Pick it up to make it yours" | Opens the form prefilled; the suggestion is not a card until the person puts it on the wall (A-056) | The person it was drafted for | Not shown |

### Screen C: the card opened

Route: a panel on `/centre/intent/<id>/wall` or `/centre/intent/<id>/define`, opened by `?card=<card_id>` (see Open question 9). At 1280 a centred panel over the wall. At 390 a full page.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Lane and cluster line | Chips | Lane name; cluster name once Define has set it; shelf once set | Cluster chip opens the cluster in Define for the committee | Everyone who sees the card | "Not clustered yet" |
| Four quarter blocks | Panels | Each wall question and its answer; mark chip stated or guessed with the document named; `unknown` shows "Not answered" | None | Per Rules | "Not answered" |
| Author line | Text | Full name where the author chose a name; "Anonymous" otherwise; "North drafted, <person> confirmed" when `from_interview` is set | None | Per Rules | "Anonymous" |
| Dates | Text | Added, last edited, withdrawn (when), in the company's time zone from the profile, else UTC | None | Everyone who sees the card | Edited line absent when never edited |
| Move history | List | Each lane or cluster move: from, to, person, time | None | Committee, organiser, company admin. The author sees moves of their own card | "Not moved" |
| Edit history | Count line | "Edited n times". The earlier words are kept in the record and shown only to the author | "See earlier versions" opens a list (author only) | Author (list); everyone sees the count | Hidden when 0 |
| Edit / Withdraw buttons | Buttons | Edit, Withdraw | Edit opens Screen A; Withdraw asks "Withdraw this card? It stays in the record, marked withdrawn." Yes or No | Author while the wall is open | Not shown after freeze |
| Move to cluster | Select | Cluster names of this intent (in a brainstorm group phase: the group names, owned by 36) | Calls the move route; asks for nothing else | Committee in Define; for session kind brainstorm, every participant and the organiser in the group phase only (36) | Not shown elsewhere |
| Close | Button | Close | Returns to the wall | Everyone | None |

### Screen D: the brainstorm card (36)

Route: a drawer on `/centre/intent/<id>/session` (36). The same Screen A with only the idea field. Layout at 1280 and 390: one text field, "Add your idea", "Hide my name" tap if the session allows it, Add. Quarters q2 to q4 do not exist on screen. No lane chooser (brainstorm has no lanes). No "North, fill this" button (the idea is the person's own thought; see Open questions). No seal tap in a brainstorm (see Open questions).

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Idea field | Text field, voice button | The prompt set by the organiser | Saves into q1 | Author | Add stays off |
| Add | Button | Primary | Writes the card with `session_kind: brainstorm`; text appears on the shared board when the session says ideas are open | Author | Off |
| Idea card on the board | Card | Idea text, initials or nothing, no edge (nothing to fill) | Opens the idea (the full text and, where named, the author) | Participants | "No ideas yet" |

## User journey (numbered steps from arriving to leaving, with what the agent does between the person's steps)

1. Aaron opens the wall and taps "Add a card" in MISSING.
2. The form opens with the lane chosen. Aaron types q1: "We cannot see cash by custodian before 9am."
3. North (agent) checks the words against his shelf and offers "North, fill this from the files" on q2 to q4. Aaron presses it on q3. North reads "Treasury policy 2025", fills the quarter and marks it guessed, naming the document.
4. Aaron reads it, edits one word, so the mark becomes stated. He leaves q4 empty and q2 answered. The count reads 3 of 4.
5. Aaron sees the card mentions pay in q2, taps seal. The preview shows the silhouette.
6. Aaron presses "Put it on the wall". The card is written to the profile and linked to the intent. His edge shows three segments.
7. Later Aaron sees a typo, opens his card, presses Edit, fixes it. The edit is kept with time; the earlier words stay in the record.
8. Aaron decides the card is wrong and presses Withdraw, then Yes. The card shows greyed with "Withdrawn" and leaves every count.
9. Janet closes the wall. The cards freeze; Edit and Withdraw disappear. North posts the frozen snapshot (existing `wall_snapshot.py`).
10. In Define, Lens proposes clusters. Katie, on the committee, moves a card from one cluster to another. The move is kept with her name and the time.
11. Brainstorm path: the person opens the idea box, types one idea, presses Add. Nothing else is asked.

## States and transitions (table: state, who moves it, to what, what is written)

| State | Who moves it | To what | What is written |
|---|---|---|---|
| (none) | Author | `draft` (private) | Card record with `on_wall: false`, each filled quarter as a cell |
| `draft` | Author, with two of four answered | `on_wall` | `on_wall: true`, `placed_at`, counter `cards_new` |
| `draft` | Author | `discarded` | Draft removed; not a card, so not kept (no one else ever saw it). Counted in nothing |
| `on_wall` | Author, wall open | `on_wall` (edited) | New cell values with provenance, entry in `edits[]`: `{by, at, quarter, kind: edit}`, earlier words kept in `versions[]` |
| `on_wall` | Author, wall open | `withdrawn` | `withdrawn: {by, at}`; words kept; excluded from counts and the frozen wall's lanes, listed in its "withdrawn" tally |
| `on_wall` | Author, wall open | `on_wall` (new lane) | `lane`, entry in `moves[]`: `{kind: lane, from, to, by, at}` |
| `on_wall` | Committee person, Define open | `on_wall` (new cluster) | `cluster`, entry in `moves[]`: `{kind: cluster, from, to, by, at}` |
| `on_wall` (`session_kind: brainstorm`) | Any participant or the organiser, group phase open | `on_wall` (new group) | Same `moves[]` entry. The rule, the phase check and where the group name is kept are 36's; this file defines only the entry shape |
| `on_wall` | Author, wall open | sealed or unsealed | `sealed`; entry in `edits[]` kind `seal` or `unseal`. Counters `cards_sealed` |
| `on_wall` | Author, wall open | anonymous or named | `anonymous`; the `author` key is replaced by `anon-<id>` and the name is dropped from the record (D-013), so un-hiding is not possible once set (see Open questions) |
| any | Organiser, closing the wall | frozen | Wall snapshot written; edit, withdraw, lane change refused from then |
| `withdrawn` | (nobody) | stays | A withdrawn card is never restored; the author adds a new one |

## Records read and written (file or route, fields; mark Existing or New)

| Record | Fields | Mark |
|---|---|---|
| `profile.json` section `cards` through `sh_platform/profile/store.py` (`record`, `set_cell`, `mutate`, depth 3) | `lane`, `q1..q4`, `sealed`, `anonymous`, `author`, `from_interview`, `cluster`, `shelf`, plus written today by `modules/m1_intent/store/notes.py`: `room`, `topic`, `anon_key` | Existing |
| Profile read filter `sh_platform/profile/view.py` `_cards` | Silhouette for a sealed card the viewer may not see; `author` dropped on an anonymous card for everyone | Existing |
| `cards_summary` in `view.py` | Per-lane and total counts over the same filter | Existing, to add a withdrawn exclusion |
| `modules/m1_intent/store/wall_snapshot.py` | Frozen wall: lanes with neutral cards, filtered by `served` | Existing |
| Card fields added by this feature | `intent_id`, `session_kind`, `on_wall`, `placed_at`, `withdrawn`, `edits[]`, `versions[]`, `moves[]` | New (the section is written only by the wall routes, A-053) |
| `intents/<id>/intent.json` | `links` unchanged; the card count is read, not stored (see Fields this feature adds) | Existing |
| Wall question text | `wall_questions.yaml` (q1 to q4 leads) via `Q.load` | Existing |

Lane values: the profile stores `tracking | missing | watch | levers`. The wall component names the lanes `intent | pain_point | future_signal | lever`; the mapping stays as it is today (`LANE_OF` in `notes.py`). This spec does not rename either.

## Fields this feature adds to the intent record

None to the intent record itself. Counts are derived from `profile.cards` filtered by `intent_id`. The card gets these new fields:

```
cards.<card_id>: {
  lane, q1..q4 (provenance cells: {value, mark: stated|guessed|unknown, by, at, from, ref?, agent?}),
  sealed, anonymous, author (person id or anon-*), from_interview, cluster, shelf,   # A-053, existing
  room, topic,                                                                       # existing, written by notes.py
  intent_id,            # the intent this card belongs to (new)
  session_kind,         # wall | brainstorm (new); `room` keeps the v1 session id
  on_wall,              # false while a private draft (new)
  placed_at,            # time it went on the wall (new)
  withdrawn,            # null | {by, at} (new)
  edits: [{by, at, quarter|null, kind: edit|seal|unseal}],        # new
  versions: [{quarter, value, at}],                               # earlier words, author-only (new)
  moves: [{kind: lane|cluster, from, to, by, at}]                 # new
}
```

On an anonymous card `edits[].by`, `moves[].by` for the author's own actions and `author` are written as the `anon-*` key, never a name. A committee move on an anonymous card names the mover (the mover is not the author).

## Agent behaviour (North, Lens, Nira: what each drafts, when, and the moment a person acts)

- **North** drafts a card from the person's interview answer (`from_interview` set) and shows it as a draft. It fills a quarter from the person's own documents only when the person presses "North, fill this from the files"; that quarter is marked guessed with the document named. It never fills a quarter on its own and never fills the idea in a brainstorm. It adds at most three suggestion cards per lane (A-056). The person acts: confirms, edits, puts on the wall, or drops. A draft never overwrites a human edit (hard rule 7).
- **Lens** reads cards in Define to propose clusters and shelves. It does not read a sealed card into any draft others see, and it never sees the author of an anonymous card. People confirm clusters; a committee person moves a card.
- **Nira** puts one line on the Pulse page for a person who holds an unconfirmed North draft, and one for the organiser when the wall closes with cards unplaced. Nira does not edit cards.
- Agents never withdraw, seal, move or anonymise a card. Only a named person does.

## Rules (visibility, time box, who may do what)

- **Who may edit or withdraw:** the author only, and only while the wall is open (stage `Think unfiltered` open, `time_box` not ended, state not closing). No one else can edit another person's words, the organiser and admin included. After the wall freezes, edit, withdraw and lane change are refused.
- **Withdrawn cards** stay in the record marked withdrawn, with who and when. They leave lane counts and Define. The author and the company admin can open them. Others see a grey card reading "Withdrawn" with no words. They are not deleted (brief section 4).
- **Lane change:** the author, while the wall is open. Kept in `moves[]`.
- **Cluster change (session kind wall):** committee people only, in Define, kept with person and time. The author does not move their own card after Define opens.
- **Group move (session kind brainstorm):** any participant and the organiser may move any card between groups, in the group phase only, kept with person and time. File 36 owns this rule; this file only widens the move route to accept it. Edit, withdraw and seal stay author-only.
- **Two of four** quarters needed to place (A-055). Empty and `unknown` quarters show as empty. A guessed quarter counts as answered but shows its mark.
- **Seal:** the author sets it. A sealed card is whole to a viewer who may see every restricted area its words name (the existing `_cards` rule); everyone else, the organiser and company admin included, sees the silhouette. Lens does not read it into shared drafts. The seal can be removed only by the author while the wall is open.
- **Anonymous:** per card, real (D-013). The record never carries the name, so no screen, export or admin view can show it. Quarter text is masked of names as `wall_anonymous` does today. Projector view shows counts per lane only, never names.
- **Who sees what:** participants see cards except sealed silhouettes and anonymous authors. Affected people see no card words unless the organiser switched on "affected people may read" at creation (default off) or they are named on a share (brief section 10, ruling 4). Observers read what a participant reads and never write, move or vote. People tagged to the area only see no cards. Super admin sees no card. Company admin sees cards by the same rules as a participant, never anonymous authors.
- **While the rooms are open** (private rooms stage) another person's card is a silhouette "Someone's card, words show when the rooms close", as today (`other` variant).
- **Time box:** a card carries no clock of its own. The wall's window (from 07) decides when edit and withdraw stop.
- **Brainstorm card:** q1 only; q2 to q4 are stored as empty cells, not missing. Edit and withdraw follow the same author-only rule until the live session closes.

## Counters and measures of this feature (numbers only, each traced to a record)

| Number | Source |
|---|---|
| Cards on the wall, per lane | `profile.cards` where `on_wall` and not withdrawn, by `intent_id`, via `cards_summary` |
| Cards withdrawn | `profile.cards[].withdrawn` not null |
| Cards sealed | existing `cards_sealed` counter (per `notes.py` `counters`) |
| Cards confirmed, new | existing `cards_confirmed`, `cards_new` |
| Cards with two, three, four quarters answered | quarters whose mark is not `unknown`, per card |
| Quarters guessed | cells with `mark: guessed` |
| Cards moved between clusters | `moves[]` where `kind: cluster` |
| Cards edited | `edits[]` entries of kind `edit`. The opened card shows "Edited n times" from `len(edits)` of that card |
| Cards placed in the first five minutes (LI-OUTCOMES), exact count | `placed_at` against the wall's open time, per intent. Never split by person (a per-person figure shows "Fewer than five" below five records, and none is shown for anonymous cards). The five minutes is Open question 10 |

Any figure with no record shows "Not available yet" and names the missing record.

## Reuse check (what exists today: file paths and line ranges found with graft; copied, reshaped or not used, and why)

Searches run: `graft ask "profile cards section"`, `graft ask "wall card component"`, `graft find "record_card"`, and a read of the files below.

| Existing | Where | Decision |
|---|---|---|
| `cards` section in the profile, depth 3, empty default | `sh_platform/profile/store.py` lines 25, 32 | Used as is. This is the store |
| Provenance cell (`value, mark, by, at, from, ref, agent`) | `sh_platform/profile/store.py` `cell`, lines 44 to 64 | Used as is for q1..q4 |
| Card read filter: silhouette, author dropped when anonymous | `sh_platform/profile/view.py` `_cards`, lines 171 to 184; `cards_summary` 187 to 195 | Used as is. One change: `cards_summary` must skip `withdrawn` and `on_wall: false` |
| Card write from a submitted note: `lane, sealed, anonymous, author or anon_key, q1..q4, from_interview, room, topic` | `modules/m1_intent/store/notes.py` `_card` (about 125 to 131), `_write_cards` 134 to 145 | Used. New fields `intent_id`, `session_kind`, `on_wall`, `placed_at` are written here |
| Four wall questions, A-055 minimum two, drafts from interview and documents, anonymous masking | `modules/m1_intent/api/private_room.py` lines 147 to 200 (`wall_drafts`, `_passage`, `wall_start`, `wall_anonymous`) | Used. "North, fill this from the files" is a button over `wall_drafts` for one quarter. The `guessed` mark and named document already exist |
| Suggestion cards, at most three per lane | `private_room.py` `seed_suggestions` (from line 201) | Used as is |
| Note cards from conversation | `modules/m1_intent/agent/north.py` `propose_cards` (179), `draft_card` (213); `domain/interview_notes.py` `card_note` | Used as is |
| Frozen wall | `modules/m1_intent/store/wall_snapshot.py` (48 to 73) | Used as is; add the withdrawn tally |
| Card component: edge of four segments, initials-or-name foot, sealed silhouette, suggestion variant, draft variant, `other` variant | `ui/src/modules/m1_intent/wall/Card.tsx` (whole file, about 100 lines) | Copied. Add `withdrawn` variant, card menu, opened view. The `WallCard` type gains `withdrawn`, `clusterName`, `placed`. Foot shows initials; today it shows the author's name, so reshape to initials per the brief |
| Wall copy | `ui/src/modules/m1_intent/wall/copy.ts` (`lanes`, `sealed`, `needTwo`, `answered`, `guessed`, `readFrom`, `stillRight`, `putOnWall`, `sealBox`) | Used as is. New strings: withdraw, edit, move, withdrawn, hide my name |
| North panel and its answer flow | `ui/src/modules/m1_intent/wall/NorthPanel.tsx` | Used as is; the card form (Screen A) is the form view of the same four questions |
| Lane component | `ui/src/modules/m1_intent/wall/Lane.tsx` | Used as is |
| Edit, withdraw, move history, `intent_id`, `session_kind` | Not found by `graft find "withdraw"`, `"moves"` in `modules/m1_intent` and `sh_platform/profile` | New. The card has no edit or withdraw path today, and `board.py` `edit` records cluster edits by `by` and `kind` only for a session, not per card |
| Cluster edit record | `modules/m1_intent/store/board.py` `edit`, lines 74 to 78 | Reshaped: the per-card `moves[]` mirrors its `{by, kind}` shape, written next to the board edit so both agree |

Fields that exist on a card today: `lane`, `q1` to `q4`, `sealed`, `anonymous`, `author` (or `anon_key`), `from_interview`, `room`, `topic`. Fields in A-053 not yet written by any route: `cluster`, `shelf` (written by Define). Fields new here: `intent_id`, `session_kind`, `on_wall`, `placed_at`, `withdrawn`, `edits`, `versions`, `moves`.

## Not in this feature

- The wall screen, lanes layout, stage bar, invite panel, projector view (wall file).
- Clustering, shelving and the Define screens (Define file). Only the card's cluster move is here.
- The brainstorm session flow, voting and choosing an idea (36). Only the single-quarter card is here.
- Votes, ticks and charter "so that" (existing board and charter code).
- Comments or replies on a card.
- Deleting a card. Nothing is deleted.

## Open questions

1. Can an author un-hide their name after setting anonymous? The rule as written says no, because the name is dropped from the record. Confirm.
2. Withdrawn card words: should the company admin see them, or only the author? This spec says author and company admin. Confirm.
3. Should a brainstorm idea be allowed to be sealed? This spec says no, because brainstorm ideas are about solutions. Confirm.
4. Should "North, fill this from the files" exist on a brainstorm idea? This spec says no. Confirm.
5. Edit after a card has been clustered in Define: not possible as written, since the wall is frozen by then. Confirm the wall always freezes before Define opens.
6. A card edited after another person has read it: the count "Edited n times" is public. Confirm that is acceptable, or show nothing.
7. The wall foot shows the full name today (`Card.tsx`); the brief asks for initials. Confirm initials only, with the full name in the opened card.
8. How many edits are allowed per card? None set; no limit proposed.
9. Card form and opened card have no page route under `/centre/intent/<id>/<view>`; this file uses `?card=` on `wall`, `define` and `session`. Confirm, or name a route.
10. "First five minutes" comes from LI-OUTCOMES, not the brief. Confirm the window.
11. In a brainstorm group phase the move entry reuses `moves[]` with `kind: cluster` and a group name as `to`. Confirm with 36, which owns it, or add `kind: group`.
12. Time zone: dates follow ruling 8 (company profile, else UTC); confirm the profile field name with 07.
