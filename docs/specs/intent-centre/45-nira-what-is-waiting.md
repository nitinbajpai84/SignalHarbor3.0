# 45. Nira: what is waiting for you

Part of: Intent Centre v2. Depends on: 00-BRIEF, 01 (intent record), 02 (types and stages), 06 (people and roles), 07 (time box), 13 (Pulse lines and notifications), 14 (permissions). Feeds: 04 (Intent home), 13 (Pulse), 19 (counters).

## Purpose (three sentences)

Nira keeps one list per person of everything across all intents that waits on that person, built fresh from the intent records and never stored. The list is ordered so that signatures and decisions come first (a vote and a backing count as decisions), then by due date, and Pulse shows its top seven lines while the "Your turn" strip on the Intent home shows all of it. The organiser gets a second view: for each intent, who has not acted, by name and since when, with a nudge button that drafts the message and sends nothing.

## Who uses it and when (role, moment, trigger)

| Role | Moment | Trigger |
|---|---|---|
| Any person in an intent | Opens Pulse, or the Intent home | A record names them: invited, a question, a card, a vote, a definition, a process, a signature, a rating, a week entry, a problem, a decision, a review |
| Organiser (Janet) | Opens an intent's "Who has not acted" panel | The clock is running and some people have been quiet |
| Sponsor (Daniel), approver (Grace), owner (Harvey), reader (Katie), participant (Aaron) | Same as any person | Same |
| Nira (agent) | Each read of Pulse or of the list | Computes the list; drafts a nudge when the organiser clicks |

Agents decide and draft. A person acts at every line: answers, confirms, votes, signs, rates, accepts, decides, reviews.

## Entry points (every route, link, Pulse line, button that leads here)

- `GET /api/pulse`: the top seven lines of the person's list, in the existing strips (spec 13 supplies the intent readers).
- `GET /api/intents/waiting` (New): the person's whole list, used by the "Your turn" strip.
- `GET /api/intents/<id>/who-has-not-acted` (New): the organiser's view for one intent.
- Intent home `/centre/intent` (spec 04): the "Your turn" strip, and the existing Nira side card (`ui/src/pages/CentrePage.tsx` 233-247), which is reshaped into this strip.
- Intent screen `/centre/intent/<id>`: the "Who has not acted" panel, shown to the organiser only.
- Pulse card "And N more in the Intent Centre" (spec 13): links to `/centre/intent#your-turn`.
- The Pulse line "See who to remind" (spec 13 row 16): opens `/centre/intent/<id>#who-has-not-acted`, the panel above.

## Screens, element by element

### Screen A: the "Your turn" strip on the Intent home

Route: `/centre/intent`, region "Your turn", above the intents list. Layout at 1280: a full-width strip of line cards, three across, wrapping; an "Open" button on each. At 390: one column; the due date moves under the line; the strip is collapsed to the top three with a "Show all" button.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Strip heading | panel | "Your turn" and the count, "5 things wait for you" (count of lines in the list Nira just built) | None | Everyone signed in | Heading stays; body reads "Nothing waits for you in the Intent Centre." |
| Line | list item | The line (see element table below) | Opens the line's `href` | The person the line is for | Not shown |
| Line text | agent line | One plain sentence, for example "Confirm the term: Net asset value" | None | As above | Not shown |
| Action button | button | The action label, for example "Confirm", "Sign", "Vote", "Rate it" | Opens the line's `href`, always a ruled route: `/centre/intent/<id>/<view>` with view `wall`, `define`, `charter`, `build-ready`, `session`, `week`, `review` or `close` (see "Line kinds", column Href) | As above | Not shown |
| Due chip | chip | "Due Thu 9 Oct", or "Overdue since Mon 6 Oct" in the warning colour, or no chip when there is no due date | None | As above | Not shown |
| Source link | list item | The intent title and type, for example "Brainstorm: faster month-end close" | Opens `/centre/intent/<id>` (stage view) | As above | Not shown |
| Kind filter | chip row | "All", "Signatures and decisions", "Questions", "Ratings" | Filters the strip; no write | As above | Hidden when fewer than four lines |
| Show all | button | "Show all 12" | Expands the strip from three to every line | As above | Hidden when three or fewer lines |
| Reason line | panel | When the strip has lines Nira cannot read: "2 intents could not be read. Reload to try again." | "Reload" re-requests | As above | Not shown |
| Loading | panel | "Checking what waits for you." | None | As above | Not applicable |
| Error | panel | "Nira could not read your list. Reload to try again." and a "Reload" button | Re-requests | As above | Not applicable |

The strip replaces the existing Nira side card. The old card showed up to three asks from the wall readiness check; those asks stay as lines of kind `ask` (see "Line kinds").

### Screen B: the organiser's "Who has not acted" panel

Route: `/centre/intent/<id>`, panel "Who has not acted", beside the stage clock. Layout at 1280: a right-hand panel under the stage header; a table with three columns (name, owes, has not acted since). At 390: below the stage header; each person becomes a two-line row (name, then what they owe and since when).

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Panel heading | panel | "Who has not acted" and "3 of 6 in this stage" (read from `people` and `stages[]` of the intent) | None | The organiser of this intent and the company admin | Panel hidden when the intent is not open |
| Name | list item | The person's name, for example "Katie" | None | As above | See empty row below |
| Owes | list item | What they owe: "Add your ideas", "Vote", "Give your view", "Add your week" | None | As above | As above |
| Has not acted since | list item | "Has not acted since Mon 6 Oct" (the date their turn opened, from the stage `opened_at`) | None | As above | As above |
| Select | field (checkbox) | One per person; all ticked at first | Changes who the nudge goes to | As above | As above |
| Nudge button | button | "Nudge" and the count, "Nudge 3" | Asks Nira to draft one message for the ticked people; opens the draft in the drafts list | As above | Disabled when no one is ticked: "Tick at least one person." |
| Draft preview | panel | Subject, body and the short chat line (length set in spec 13) | None | As above | Not shown until Nudge is clicked |
| Edit text | field | The draft subject and body, editable | Changes the draft text only; nothing sent | As above | Not shown until Nudge is clicked |
| Copy text | button | "Copy text" | Copies the chat line to the clipboard | As above | Not shown until Nudge is clicked |
| Send | button | "Send" | Existing send route; answers 503 and the draft stays until an email path exists | As above | Not shown until Nudge is clicked |
| Nudged earlier | chip | "Nudged yesterday" in place of the Nudge button count while the cooldown runs (Open question 5) | None | As above | Not shown when no nudge was made |
| Everyone has acted | panel | "Everyone has acted in this stage." | None | As above | This is the empty state |
| Anonymous note | panel | "Anonymous ideas are counted, not named." Shown when the stage allows anonymous input | None | As above | Not shown |

The panel gives names and the date each person's turn opened. It does not say whether a person has opened the intent: "last opened" is dropped. Pulse never gives names: row 16 of spec 13 shows a count only, and the line leads here.

## Line kinds (what Nira lists)

One line kind per stage the person can owe. Each reads the intent record. Where spec 13 already has a row, this spec uses that row and its wording; it adds only the fields and the grouping.

| # | Kind (spec 45) | The record says | Spec 13 row | Action | Due | Href (`/centre/intent` prefix; `<id>` is the intent) | Group |
|---|---|---|---|---|---|---|---|
| 1 | `invited` | Invited and not joined: the person is in `people` and has no entry in the open stage | 1 | "Add your ideas" and per type wording | End of the open stage | `/centre/intent/<id>/wall` (Initiative, Brainstorm), `/centre/intent/<id>/session` (Brainstorm live), `/centre/intent/<id>/week` (Weekly check-in), else `/centre/intent/<id>` | Question |
| 2 | `start_question` | Your start question: state `draft`, `created_by` is the person, a required answer is empty | 3 | "Answer them" | None | `/centre/intent/new?type=<type>` | Question |
| 3 | `card_confirm` | Your card to confirm: `drafts_to_confirm[]` has the person as author and `confirmed_by` is empty | 4 | "Check the card" | End of the open stage | `/centre/intent/<id>/wall` | Question |
| 4 | `vote` | Your vote or backing: an open vote or backing round lists the person in `voters` and not in `cast_by` | 5 | "Vote" | `votes[].closes` | `/centre/intent/<id>/session` | Decision |
| 5 | `definition_confirm` | Your definition to confirm: `definitions_waiting[]` names the person as owner | 6 | "Confirm" | End of the open stage | `/centre/intent/<id>/define` | Question |
| 6 | `process_confirm` | Your process to confirm: a process step or lane drafted by Lens names the person as owner and `confirmed_by` is empty (field added below) | New | "Check the step" | End of the open stage | `/centre/intent/<id>/define` | Question |
| 7 | `signature` | Your signature: an Initiative charter is awaiting the person as approver, or a closure is waiting on the closer | 7, 10 | "Review and sign", "Review and close" | None, or none | `/centre/intent/<id>/charter` or `/centre/intent/<id>/close` | Signature |
| 8 | `rating` | Your rating: the intent closed within the rating window and the person has no entry in `ratings` | 11 | "Rate it" | End of the rating window | `/centre/intent/<id>/close` | Rating |
| 9 | `week_entry` | Your week entry: a Weekly check-in in `collect` and the person has no items this week | 13 | "Add your week" | End of `collect` | `/centre/intent/<id>/week` | Question |
| 10 | `problem_accept` | Your problem to accept: a Problem intent names the person as owner and `owner_accepted_at` is empty | 14 | "Take it" | `time_box.ends` | `/centre/intent/<id>` | Decision |
| 11 | `decision` | Your decision: a Decision intent, stage `decide` open, the person is the decider; also North's "your turn" (`waiting_on`) for any other stage | 15, 2 | "Decide" | `time_box.ends` | `/centre/intent/<id>` | Decision |
| 12 | `review` | Your review: a Weekly check-in in `review` or a Problem in `confirm`, `waiting_on` names the person as reader or reporter; or a build-ready check for the sponsor | 2 | "Read the week", "Confirm it is gone", "Check the build-ready list" | End of the open stage | `/centre/intent/<id>/week`, `/centre/intent/<id>/review` or `/centre/intent/<id>/build-ready` | Question |

Also listed: `overdue` and `clock` (spec 13 rows 8 and 9) for the organiser and closer, as kind Decision; and `ask` (wall readiness asks, existing) as kind Question.

New line kinds named: `start_question`, `card_confirm`, `vote`, `definition_confirm`, `process_confirm`, `week_entry`, `problem_accept`, `review`. Mapped to existing Pulse kinds on the wire: `invite`, `decision`, `request`, `signature`, `rating`, `clock` (spec 13); the strip uses its own `kind` for the filter chips only.

## The line (the "Your turn" element)

Four parts, no more. The shape is the existing LINE shape of SHAPES section 1, so no field is added to it.

| Part | Field | Rule |
|---|---|---|
| Line | `title` and `detail` | One plain sentence a business person reads without help |
| Action | `action` | A verb phrase that names what the person does; never "FYI", never "Open" alone |
| Due | `due` | An ISO date or null, taken from the record named in the table above |
| Source | `source.record` and `source.at` | The intent file and the time its record changed to make the line true |

`id` is `intent:<intent id>:<kind>:<ref>`, where `<ref>` is the card, term, vote, step or sign id when there is one. The id is stable across reads so a card never flickers.

## The priority rule

1. **Group first.** Signatures and decisions (groups Signature and Decision) come before everything else. A vote and a backing count as a decision (group Decision), settled by the brief's ruling. A signature sorts before a decision, then the other kinds.
2. **Due soonest first within a group.** An overdue line has a past date and so comes first. A line with no due date follows lines with a due date. The tie is broken by the newest `source.at`.
3. **Never by who asks.** The sort reads kind, due and `source.at` only. The organiser's rank, the sponsor's seniority, the number of nudges, and the name on the intent are never inputs.
4. **One line per person per intent on Pulse.** When several lines are true for one person in one intent, Pulse shows the highest by the order in spec 13 "One line per person per intent". The strip on the Intent home shows all of them, so nothing is lost; it is only not repeated on Pulse.
5. **Pulse cap.** At most seven lines a day, as `CAP = 7` today. Nira drops from the end of the order, so the last to go are signatures and decisions. What is dropped: the lines past the seventh, counted into `more` (spec 13). Where the rest is seen: the "Your turn" strip on the Intent home, reached by "And N more in the Intent Centre".
6. **The strip has no cap.** It shows every line the person owes, after the kind filter.

Example. Aaron has a vote closing Friday, a rating due next Monday, and a week entry due Thursday. Nira orders: vote (Decision), week entry (Thursday), rating (Monday). Daniel has a charter to sign with no due date and a decision due Wednesday: the signature goes first, the decision second, because a signature sorts before a decision.

## How Nira marks a line done

Nira never marks a line done. The line is a reading of the record, and the record is the only source.

- A line exists while its record says so (for example `cast_by` does not hold the person).
- A person acts on the intent screen. That act writes the intent record (`cast_by` gains the person). The next read does not make the line, so it is gone.
- Nothing like `done: true` is stored beside the record. There is no tick, no "snooze", and no "dismiss". A person who wants a line gone does the thing it asks, or says "not me" on the intent (hands a turn back with a reason, spec 06), which changes the record.
- A line whose record is cancelled, closed or edited so it no longer holds disappears the same way. The strip says nothing about it.
- The record can be wrong, for example a vote closed by the clock. Then the line is gone and the intent screen says what happened.

## User journey (numbered steps from arriving to leaving, with what the agent does between the person's steps)

Example one: Aaron.

1. Aaron opens Pulse. Nira reads every intent record that names him and builds his list. Pulse shows his top seven.
2. He sees "Vote: which idea to take forward", due Friday. He clicks "Vote".
3. He casts the vote on the intent screen. The record writes his id into `cast_by`.
4. He returns to Pulse. The next read does not make the vote line. Nira writes nothing.
5. He sees "And 3 more in the Intent Centre" and clicks it. The Intent home opens at "Your turn" with all of his lines.

Example two: Janet (organiser).

1. Janet opens her Brainstorm. The panel "Who has not acted" lists Katie and Aaron, with what each owes and since when.
2. She leaves both ticked and clicks "Nudge 2". Nira drafts one message with the subject, body and chat line (spec 13 `intent_nudge`) and stores it in the drafts list. The panel opens the preview.
3. She reads it, edits the text if she wishes, and clicks "Copy text" (or "Send"; today it answers 503 and the draft stays).
4. The next day Katie adds her ideas. The panel no longer lists her. Aaron stays.
5. Nira offers no second nudge until the cooldown (Open question 4) has passed since the last, read from `nudges` (spec 13). The button shows "Nudged yesterday" until then.

## States and transitions (table: state, who moves it, to what, what is written)

Lines hold no state. These are the only states.

| State | Who moves it | To what | What is written |
|---|---|---|---|
| Line true | The record changes (a person acts, a stage opens, the clock passes) | Line present | Nothing |
| Line false | A person acts, or the record changes again | Line gone | Nothing |
| Nudge draft | Nira, on the organiser's click | `draft` | `pulse/messages.json`: one message with `kind: intent_nudge`, `to` (the ticked people), `from_record: intents/<id>#nudge:<stage>:<date>` |
| Nudge draft | The organiser clicks "Send", an email path exists | `sent` | `sent_by`, `sent_at` (existing) |
| Nudge draft | The same click, no email path | stays `draft` | Nothing; answer 503 (existing) |
| Nudge recorded | The organiser creates a draft | One entry in the intent's `nudges` | `{kind: "who_has_not_acted", at, message_id, to: [account_id]}` |

## Records read and written (file or route, fields; mark Existing or New)

| Record | Mode | Fields | Mark |
|---|---|---|---|
| `GET /api/pulse` | read | strips, lines, `minutes`, `map`, `panels`, `more` | Existing (`more` is New in spec 13) |
| `sh_platform/pulse/lines.py` readers | read | as today (wall invites, charters, measures, asks, silent owners) | Existing |
| `sh_platform/pulse/intent_lines.py` | read | the intent readers of spec 13 | New (spec 13) |
| `sh_platform/pulse/waiting.py` | read | one function: collect every reader's lines for a viewer, then order them | New |
| `GET /api/intents/waiting` | read | the person's list: `lines[]` in LINE shape, `kind_group`, `count` | New |
| `GET /api/intents/<id>/who-has-not-acted` | read | `people: [{account_id, name, owes, since}]`, `count_stage`, `nudged_at` | New |
| `POST /api/intents/<id>/nudge` | write | body `{to: [account_id]}`; creates one draft, appends to `nudges` | New |
| `intents/<id>/intent.json` | read | `people`, `stages`, `waiting_on`, `votes`, `drafts_to_confirm`, `definitions_waiting`, `owner_accepted_at`, `ratings`, `closure`, `time_box`, `nudges` | New (record), fields from spec 13 |
| `pulse/messages.json` | read, write | message fields of spec 13 | Existing |
| `accounts` (`app.state.account_store`) | read | `email`, `account_id` | Existing |

## Fields this feature adds to the intent record

- `process_waiting`: `[{id, step, owner: account_id, drafted_by: "Lens", confirmed_by: account_id|null, state: open|confirmed}]`. Row 6 of the table reads it. The process map spec (27) owns the content; this spec only names the field Nira reads.
- `nudges` (spec 13): this spec adds the entry shape `{kind, at, message_id, to: [account_id]}`.

Nothing else. No `done` field, no `dismissed` field, no `read` field.

## Agent behaviour (North, Lens, Nira: what each drafts, when, and the moment a person acts)

- **Nira** reads the intent records and builds the list on each request. It never stores the list. It drafts one nudge when the organiser clicks "Nudge", from words and dates only, with no figure and no row. Person acts: every line has an action; the organiser clicks Nudge, then Copy or Send.
- **North** writes the fields Nira reads (`waiting_on`, `drafts_to_confirm`, the stage clock). It writes the "what" sentence that becomes the line detail for a "your turn" line. North does not nudge someone because the organiser clicked; that is Nira's draft. North's own daily nudge (spec 13) is a separate draft.
- **Lens** writes `definitions_waiting` and `process_waiting`. Person acts: the named owner confirms or rewrites.
- No agent signs, votes, rates, accepts, decides or reviews.

## Rules (visibility, time box, who may do what)

- A line is for the person it names only, matched by `account_id` as `_mine` and `invited` do today. Nobody sees another person's list. The company admin and super admin do not see lines for intents they are not part of.
- Names appear only in the organiser's panel, and only to the organiser of that intent and the company admin. They never appear on Pulse or the strip.
- Anonymous input is counted and never named, in the panel and in every line (v1 rules, D-013, seal). A person who contributed anonymously still shows as having acted, by count only: the panel shows "Anonymous ideas are counted, not named" and does not list who wrote them. If an intent allows only anonymous input, the panel lists no one as "not acted" by name; it shows the count.
- Nira orders by group, due and `source.at`. It never reorders by who asks, who organised, rank, or the number of nudges.
- Nira never acts for a person: it never votes, confirms, signs, rates, accepts, decides or reviews, and never marks a line done.
- Nudges go only to people the panel lists, and no more often than the cooldown in Open question 4. A person with no address on their account gets no message; the draft says so.
- The panel is shown while the intent is `open` or `in_session`. It is hidden once the intent is `closing`, `closed` or `cancelled`.
- Dates and due chips use the company's time zone from the profile, else UTC.
- An observer never owes a line and is not listed in the panel: an observer never writes or votes. An affected person who may not read content gets no content lines, only the existence the home shows.
- Time box: the clock counts working days as spec 07 says. The "has not acted since" on a name is the date the person's turn opened, from the stage `opened_at`.

## Counters and measures of this feature (numbers only, each traced to a record)

| Counter | Where | Traced to |
|---|---|---|
| Lines waiting for me | Strip heading | The list Nira just built; not stored |
| Lines shown on Pulse, lines cut (`more`) | Pulse response | The same list the cap acted on |
| Not acted in this stage, of the people in it | Panel heading | `people`, `stages[]` of the intent |
| Nudges sent for this intent | Intent screen footer | `nudges[]` of the intent |

Where a figure cannot be worked out (for example the intent has no stage `opened_at`), the screen says "Not available yet" and names the missing record.

## Reuse check (what exists today: file paths and line ranges found with graft; copied, reshaped or not used, and why)

Read directly from the files named; ranges as read on 7 October 2026.

Exists today and is reused:
- `sh_platform/pulse/__init__.py` (Existing): `CAP = 7` (13), `_order` (16-19, due first then newest), `_strips` (31-44), `build` (58-69, repeat rule at 63), `GET /api/pulse` (82-88). Reused for the Pulse cap, order and de-duplication. One edit for `more` (spec 13). The existing `_order` has no group rule, so the "signatures and decisions first" rule is new: it adds a group key ahead of the existing two stable passes (reshaped, three lines).
- `sh_platform/pulse/lines.py` (Existing): `line()` (71-74), `safe` (60-68), `MINUTES` (23), `invited` (113-127), `measures` (144-160), `signatures` (175-195), `purpose_asks` (244-252), `requests` (266-279), `waiting` (386-391, silent baseline owners, organiser only), `_silent` (374-382). Reused as they are. Their lines carry over to the strip as the kinds `invited`, `definition_confirm`, `signature`, `ask` and `request`.
- `sh_platform/pulse/messages.py` and `templates.py` (Existing): `draft`, `_may`, the send route, `intent_nudge` writer from spec 13. The nudge reuses them.
- `ui/src/pages/CentrePage.tsx` (via graft): `waiting` (203-208, the three asks from the wall readiness check) and the Nira `SideCard` (233-247). Reshaped: the three asks become `ask` lines in the strip; the numbered list and the "Ask for these" link (organiser) stay as they are for the wall. The strip is a new component beside the side card, built from the same `SideCard`, `ol`, `ds-warn` classes.
- `ui/src/pages/PulsePage.tsx` and `pulseCopy.ts`: `Card`, `WatchCard`, the kind icons and copy (spec 13 adds the three kinds). The strip reuses `Card` for each line so a line looks the same on Pulse and on the Intent home.

New:
- `sh_platform/pulse/waiting.py`: one function that calls the existing readers and the intent readers, adds the group key, sorts, and returns the whole list.
- The panel route and the nudge route (small, one file each on the intents API).
- The strip component and the panel component.
- Eight line kinds named above, and the field `process_waiting`.

Searches run: `graft ask` for "waiting list for a person", "pulse strips", "nira waiting" in this repo; `GET /api/pulse` and the Intent home. No earlier version of a per-person list across intents or of "who has not acted" by name was found. The earlier repo's Nira list is the wall asks only, which is the existing card above.

## Not in this feature

- Building the intent readers or the Pulse page itself (spec 13).
- A bell, push, digest, read receipt, snooze, or dismiss.
- The intent screens, vote screen, rating screen, charter screen (other specs; this feature links to them).
- Sending email or chat (503 until an email path exists).
- Lines for people with no account.
- Acting on a person's behalf, ever.

## Open questions

1. Reconciling spec 13 with this one: spec 13 gives one line per person per intent on Pulse; this spec lets the strip show all. Confirm Nira builds the whole list first, then Pulse takes the top line per intent.
2. `people` entries need `account_id` as well as the name (spec 13 open question 2); this spec assumes it.
3. The rating window (7 days) and the chat line length are placeholders, each held in one constant.
4. The nudge cooldown (one working day) and "no nudge to a person with no address" are placeholders, held in one constant.
5. The brief's view list has no `rating` or `vote` view. This spec sends ratings to `/close` and votes to `/session`; confirm, or add views.
6. Whether the organiser who is not a company admin may open the panel (spec 13 open question 7).
7. "Not me" (handing a turn back) is assumed in spec 06; if it does not exist, a line can only leave by being done.
8. Whether a company admin who is not in an intent sees the panel for it, or only its existence (assumed: sees the panel, per brief section 4; confirm names are allowed).
9. A backing is treated like a vote; confirm the record field name with the Brainstorm spec (35).
