# 47. Affected and observer experience

Part of: Intent Centre v2. Depends on: 04 (home and lanes), 05 (areas and visibility), 06 (people and roles), 13 (Pulse lines), 21 (backlog, the "I feel this" tap), 24 (card model), 03 and 22 (start screens that host the creation switch). Feeds: 09 (closure draft reads the notes and counts), 19 (centre counters), 14 (permissions matrix).

## Purpose (three sentences)

Everybody tagged to an intent's areas must know there is an ongoing intent and, later, the charter or outcome that came out of it, either as a participant or as somebody affected. This feature specifies what the affected person and the observer see and may do: two quiet Pulse lines, an "Affects you" chip on the Intent home, a read view of the intent, a one-tap "I feel this", a note to the organiser, and a way to ask to join. It keeps the organiser in control: the content stays closed to affected people unless the organiser opens it with a switch that is off by default.

## Who uses it and when (role, moment, trigger)

| Role | Moment | Trigger |
|---|---|---|
| Affected person (Harvey in Operations, Grace in Finance) | Learning that something touches their area; checking what came out | Pulse watch line when the intent opens; the "Affects you" chip on the Intent home; Pulse watch line when it closes |
| Affected person | Saying "this hurts me too" | "I feel this" on a card or on a problem |
| Affected person | Telling the organiser something without joining | "A note to the organiser" box |
| Affected person | Wanting a seat | "Ask to join" on the intent page |
| Observer (Katie, invited to watch) | Reading along | Invitation as observer (06); same two Pulse lines |
| Organiser (Janet) | Opening an intent; later reading what affected people said | Switch on the start screen; "From affected people" panel; a request line on her Pulse |
| Sponsor (Daniel) | Seeing how many people feel a problem | Count in the panel |
| Company admin | Seeing counts only | Intent counters (19) |
| North, Nira | Writing the two lines, summarising notes into the closure draft | State change to `open` and to `closed` or `cancelled` |

## Entry points (every route, link, Pulse line, button that leads here)

- Pulse watch line "An intent touches your area" (row A1 below). Href `/centre/intent/<id>`.
- Pulse watch line "What came out of <title>" (row A2). Href `/centre/intent/<id>#outcome`.
- Intent home `/centre/intent` (04): the card in the viewer's area lane with the chip "Affects you". Whole card is the link to `/centre/intent/<id>`.
- Closed items on `/centre/intent/past` (04): the same chip on rows where the viewer is affected.
- Organiser: the people panel (06) gets one new row "Affected people may read the wall" (switch). The start screens (03, 22) show the same switch at "Who is in this?".
- Organiser Pulse line "<n> things from affected people" (row A3) and "<name> asks to join <title>" (row A4). Href `/centre/intent/<id>/people`.
- The person's Pulse line "Janet answered your request" (row A5), href `/centre/intent/<id>`.
- Route note: the organiser's panel is a section of the people view `/centre/intent/<id>/people` (06), not a new route.

## Screens, element by element

### Screen A. Pulse page, affected and observer lines

Route `/pulse` (existing page), fed by `GET /api/pulse`. Layout at 1280: the lines sit in the Watch strip (existing `WatchCard`, `ui/src/pages/PulsePage.tsx` L56-L61), one card per line. At 390: cards stack full width. Both lines are `kind: watch`-strip lines of kind `outcome` (new kind, defined in 13) so no new icon is needed for the first line beyond the `outcome` entry.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| A1 "Opening" line | Agent line (Nira) | Title: the intent title. Detail: "Janet opened a <type> that touches Operations. For your information." Action: "Have a look" | Opens the intent page. The line goes the first time the person opens the intent (their status becomes Joined, 06) | Affected people, observers | No line when the person was already a participant |
| A2 "Closing" line | Agent line (Nira) | Title: "What came out of <title>". Detail: `closure.summary`, first lines (length: Open question 1); for cancelled: "Cancelled: <reason>". Action: "Read what came out" | Opens the outcome (for an Initiative, the charter, read-only). The line goes when opened (`closed_seen_at` written) | Affected people, observers | No line while the intent is open |
| A5 "Reply" line | Agent line (Nira) | "Janet answered your request to join <title>: accepted as participant" or "declined: <reason>" | Opens the intent page | The person who asked | None |
| "Follow this intent" effect | Agent line | Only for people who switched Follow on: one line per stage change, "<title> moved to Define strategically", replacing the earlier one | Opens the intent page | People who chose Follow | Nothing between open and close unless Follow is on |

One line per person per intent applies (13). A1 and A2 rank last, with row 12 of 13 (outcome shared), and A2 replaces row 12 for an affected person.

### Screen B. Intent home card (affected viewer)

Route `/centre/intent` (04). At 1280 the card sits in its area lane in the 04 grid; at 390 lanes stack and the card is full width (both as built in 04). This feature adds one element to the card.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| "Affects you" chip | Chip | The words "Affects you", with the area name on hover or focus ("because you are tagged to Operations") | None; the card is the link | The viewer, on cards where they are in `people.affected` and in no stronger role | Not rendered otherwise |

The chip replaces the word "Affected" in 04's "Your role tag" for the viewer only. A person who is also a participant sees the stronger tag (04 order) and no chip. Observers see the tag "Observer". Everybody tagged to the area sees the card in their area lane because tagging puts them in `people.affected` by default (06, via `area`). Mine / All: affected cards appear under "Mine" (04).

### Screen C. The intent page as an affected person sees it

Route `/centre/intent/<id>`. Layout at 1280: one column of 760 px beside a 320 px aside. Main: header, purpose, stage and clock, people, content panel, outcome panel. Aside: "Your part" panel (follow, note, ask to join). At 390: the aside moves under the people list; the note box and "Ask to join" become full-width buttons.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Header | Text | Title, type chip, state pill, "Affects you" chip | None | Affected, observers | Not applicable |
| Purpose | Text | `purpose` | None | Affected, observers | "The organiser has not written a purpose yet." |
| Stage and clock | Panel | Current stage label, "6 days left" or "Ends Friday", counted from `time_box.ends` and `stages`, in the company's time zone from the profile, else UTC (04 wording) | None | Affected, observers | "Not started" for a draft (a draft is not shown to affected people at all, 05 rule 3) |
| People list | List | Names and role chips: Organiser, Sponsor, Participant, Observer. Affected people are shown as a count ("11 affected, 6 in Operations", counted from `people_detail` where role is affected, grouped by area), and the viewer sees "You" | None | Affected, observers | "Just the organiser so far." |
| Content panel, closed | Panel | "The organiser has kept the wall to the people taking part. You can see what came out when it closes. You can send a note or ask to join." | None | Affected people, when `affected_access.read_content` is false and the person is not named on a share | Not applicable |
| Content panel, open | Panel | The wall, the answers or the thread, read-only, by the rules of 23 and 24 (sealed cards as silhouettes, anonymous cards without author) | A card opens in place; the "I feel this" button sits on each card | Affected people, when `read_content` is true or the person is named on a share (read-only, `/centre/intent/<id>/share`) | "Nothing on the wall yet." |
| "I feel this" on a problem | Button (toggle) | Hand icon, the words "I feel this", and the viewer's own state ("You tapped") | Writes or removes the viewer's tap on the intent (opens the sign choice, Screen E) | Affected people on a Problem intent (the statement is always visible) | Not applicable |
| "Follow this intent" | Switch | "Tell me when it changes stage" | Sets `follow` for the person; default off | Affected, observers | Off |
| "A note to the organiser" | Field and button | Placeholder "Tell Janet what you know or what worries you." Length limit: Open question 1. Option "Send without my name". Button "Send note" | Writes a note; field clears and shows "Sent. Janet can read it." | Affected people. Not observers | Button disabled until text is typed |
| "Ask to join" | Button | The words "Ask to join" | Opens Screen F | Affected people and observers, while state is `open` or `in_session` | Replaced by "You asked on 9 Oct. Waiting for Janet." while a request is open; by "Declined: <reason>" after a decline |
| Outcome panel | Panel | Only when closed: `closure.summary`, `what_came_out`, `next` (initiative, backlog, problem, nothing, each with its reason), and for an Initiative the "Open the charter" link (read-only) | Opens the charter | Affected, observers, any viewer who sees existence (05) | While open: "The outcome appears here when it closes." |

### Screen D. The organiser's panel "From affected people"

Route `/centre/intent/<id>/people` section "From affected people". At 1280 a panel in the right column under people, "Open" goes full width. At 390 a link row "From affected people (n)", where n is open notes plus open requests, counted from `notes_to_organiser` and `join_requests`. Organiser and sponsor see it. Sponsor reads, cannot answer requests.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Switch "Affected people may read the <wall>" | Switch | Label by type: wall (Initiative, Brainstorm), answers (Weekly check-in), notes (Problem), views (Decision). Default off. Under it: "Off: they see the title, purpose, stage, clock, people and the outcome. On: they also read the content, but never sealed cards or anonymous authors." | Writes `affected_access.read_content`. Set at creation on the start screens (03, 22), default off. Turning it on or off is allowed while the intent is not closed; each change is kept in history | Organiser (set), sponsor (read) | Always shows a value |
| Tab "Feel this" | List | Per card or for the problem: the count from `feel_taps`, split "4 affected, 2 taking part", and the names of those who chose to sign | Click a row opens the card | Organiser, sponsor (count and signed names); participants see counts only; company admin counts only | "No one has tapped yet." |
| Tab "Notes" | List | Each note: text, date, "from Harvey" or "from someone affected", Seen mark | "Mark seen"; "Reply" opens a one-line field (signed notes only) | Organiser. Sponsor reads. Company admin never | "No notes from affected people." |
| Tab "Asks to join" | List | Name, area, asked role (participant or observer), their reason, date | "Accept" opens a role choice then confirms; "Decline" opens a required reason field | Organiser | "Nobody has asked to join." |
| "Accept" | Button | None | Writes the request accepted, moves the person to the chosen role (06 "Change role", `via` stays `area`, `role_history` entry), writes A5 line | Organiser | Disabled when state is `closing`, `closed` or `cancelled` |
| "Decline" with reason | Button and field | Placeholder "Why not? A short line helps Harvey understand." Required | Writes the request declined with the reason; writes A5 line | Organiser | "Send reason" disabled until a reason is typed |
| "Draft a reply" | Agent line (North) | A short reply in the organiser's voice for a note; never sent | Organiser edits then presses "Reply" | Organiser | Hidden when no note is open |

### Screen E. The sign choice for "I feel this"

Route: none (a popover). At 1280: a popover anchored under the button. At 390: a bottom sheet.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Choice | Radio pair | "Count me without my name" (default) and "Add my name" | Selects how the tap is stored | The tapper | Default: without name |
| "I feel this" confirm | Button | The words "I feel this" | Writes the tap; the button shows "You tapped" | The tapper | Not applicable |
| "Take it back" | Button | Shown after a tap | Removes the tap (an unsigned tap is removed by its one-way mark, see Fields) | The tapper | Not shown before a tap |

### Screen F. Ask to join dialog

Route: a dialog over Screen C. At 1280: 480 px, centred. At 390: full sheet.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Role choice | Radio pair | "Take part" (participant) and "Read along" (observer). Observers see only "Take part" | Sets `asked_role` | The asker | Defaults to "Take part" |
| Reason field | Field | "Why would you like to join? One line." Required, length limit: Open question 1 | Typing | The asker | "Send request" disabled until text is typed |
| "Send request" | Button | None | Writes `join_requests`, writes Pulse line A4 for the organiser | The asker | Not applicable |
| "Cancel" | Button | None | Closes the dialog | The asker | Not applicable |

### Screen G. The observer view

Route `/centre/intent/<id>` and its views (`wall`, `define`, `charter`, `session`, as the participant sees them; 23, 24 and the stage screens). Layout at 1280 and 390 is the participant's, with these differences: the "Your part" aside holds only "Follow this intent" and "Ask to join"; at 390 it sits under the people list.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Role note | Text | "You are watching this intent. You can read what a participant reads. You do not add, tap or vote." | None | Observer | Not applicable |
| Content | Panels | Everything a participant reads: the content, sealed cards by the same rule (S), anonymous cards without author (A), votes as counts | Read only | Observer | As the stage screen |
| Contribution controls | Buttons | "Add a card", "I feel this", "Vote", "Answer", "I'm done" and the note box are not drawn | None | Not rendered for observers | Not applicable |
| Observer chip | Chip | "Observer" in the people list beside the name, never counted in the people count (04) | None | Everyone who sees the people list | Not applicable |
| "Ask to join" | Button | As Screen C, "Take part" only | Opens Screen F | Observer, while open | As Screen C |

## User journey (numbered steps from arriving to leaving, with what the agent does between the person's steps)

1. Janet starts the initiative "Faster month-end close", tags Finance and Operations, names Aaron as a participant and Katie as an observer. At "Who is in this?" she sees "Affected people may read the wall" and leaves it off. (Person.)
2. She presses "Open this intent". The record becomes `open`. Nira lists everyone tagged to Finance and Operations who is in no stronger role as affected, 11 people, `via: area`. (Agent.)
3. Nira writes line A1 for each of the 11 and for Katie. (Agent.)
4. Harvey opens Pulse and sees "Faster month-end close. Janet opened an Initiative that touches Operations. For your information." He presses "Have a look". His status becomes Joined and the line goes. (Person, then agent.)
5. He reads title, purpose, stage "Think unfiltered", "8 days left", the people (Janet, Daniel, Aaron, Katie as observer, "11 affected"). The content panel says the wall is kept to participants. He presses "I feel this" on nothing: there is no card to tap, so he writes a note instead: "Packing-list sign-off is the slow step for us." He leaves it with his name. (Person.)
6. Nira writes a line for Janet: "1 thing from affected people." She reads the note, presses "Draft a reply", edits, presses "Reply". Harvey sees line A5 "Janet answered your note". (Agent, person, agent.)
7. Janet decides the wall helps. She turns the switch on. Affected people now see the wall, read-only, minus sealed cards and anonymous authors. Nobody gets a new line. (Person.)
8. Grace opens the intent from the Intent home (chip "Affects you"), reads a card about custody reconciliation and taps "I feel this", choosing "Count me without my name". Janet's panel shows "Custody reconciliation: 1 affected". (Person, then agent updates the count.)
9. Harvey presses "Ask to join", picks "Take part", writes "I run the packing list", presses "Send request". North puts a line on Janet's Pulse. (Person, agent.)
10. Janet presses "Accept" and chooses Participant. Harvey moves from affected to participant, a `role_history` entry is written, and he gets line A5. (Person, agent.)
11. Near the end North drafts the closure: it counts the notes and taps ("4 notes, 9 people felt a card") and lists any request still open. Janet closes it with Daniel's approval (09). (Agent, person.)
12. On close Nira writes A2 for all affected people and Katie: "What came out of Faster month-end close". Grace presses "Read what came out" and opens the charter, read-only. (Agent, person.)
13. Any request still open at close is set to withdrawn with the note "Intent closed". (Agent.)
14. Grace leaves the charter and returns to Pulse; line A2 is gone and `closed_seen_at` holds the time. Harvey and Katie leave the same way. The journey ends when each person leaves the intent. (Person.)

## States and transitions (table: state, who moves it, to what, what is written)

Per-person status inside an intent is owned by 06. This feature adds three small machines.

Join request.

| State | Who moves it | To what | What is written |
|---|---|---|---|
| (none) | The affected person or observer, "Send request" | `open` | `join_requests[]` entry: `by`, `asked_role`, `reason`, `at` |
| `open` | Organiser, "Accept" with a role | `accepted` | `answered_by`, `answered_at`, `role_given`; person moves role (06); `role_history` entry |
| `open` | Organiser, "Decline" with a reason | `declined` | `answered_by`, `answered_at`, `decline_reason` |
| `open` | The asker, "Withdraw" | `withdrawn` | `answered_at`, `answered_by` is the asker |
| `open` | Intent moves to `closed` or `cancelled` (North writes it) | `withdrawn` | `decline_reason: "Intent closed"` |

"I feel this" tap.

| State | Who moves it | To what | What is written |
|---|---|---|---|
| (none) | The tapper | `tapped`, signed or unsigned | `feel_taps[]` entry |
| `tapped` | The same person, "Take it back" | (none) | The entry is removed; a count of removals is not kept |
| `tapped` | Intent closes | Frozen | Counts are copied into the closure draft by North; the entries stay |

Content access.

| State | Who moves it | To what | What is written |
|---|---|---|---|
| `read_content: false` (default) | Organiser, switch on | `read_content: true` | `affected_access.history[]` entry: by, at, to |
| `read_content: true` | Organiser, switch off | `false` | Same entry. The wall disappears for affected people at once |
| Either | Intent closes | Locked at its value | The value at close is the one shared on later reads; the outcome is open to affected people whatever the value |

A cancelled intent: affected people see the title, purpose and the reason, never content, whatever the switch said.

## Records read and written (file or route, fields; mark Existing or New)

| Record or route | Fields | Mark |
|---|---|---|
| `intents/<id>/intent.json`, keys `people`, `people_detail` | Role, status, `via`, `follow`, `closed_seen_at` | New (06 owns the shape; this feature adds the two fields below) |
| `intents/<id>/intent.json`, key `affected_access` | `read_content`, `set_by`, `set_at`, `history` | New |
| `intents/<id>/intent.json`, key `feel_taps` | See Fields | New |
| `intents/<id>/intent.json`, key `notes_to_organiser` | See Fields | New |
| `intents/<id>/intent.json`, key `join_requests` | See Fields | New |
| `sh_platform/profile/view.py`: `Viewer`, `norm`, `allows`, `_passes`, `_bound`, `_cards` | Named-person matching, sealed silhouettes, anonymous author removal | Existing, reused as is |
| `intents/<id>/events.jsonl` (16) | One event per tap, note, request and answer; the record holds counts only | New (16 owns it) |
| `view.may_open_content(intent, viewer)` (named in 05 rule 7) | Returns true for organiser, sponsor, participant, observer, share-named, and affected only when `affected_access.read_content` is true or named on a share | New (defined in 05; this feature fixes the affected and observer branches) |
| `GET /api/intents/<id>` | Intent record filtered for the viewer; affected people receive no `feel_taps` of others, no `notes_to_organiser`, no `join_requests` of others | New |
| `PUT /api/intents/<id>/affected-access` | `{read_content}` | New. Organiser only |
| `POST /api/intents/<id>/feel` and `DELETE` | `{item: "intent"\|<card id>, signed: bool}` | New. Affected and participant; never observer |
| `POST /api/intents/<id>/notes` | `{text, signed}` | New. Affected only |
| `POST /api/intents/<id>/notes/<nid>/seen`, `/reply` | `seen_at`, `reply` | New. Organiser |
| `POST /api/intents/<id>/join-requests`, `/<rid>/answer`, `/<rid>/withdraw` | See state table | New |
| `POST /api/intents/<id>/follow` | `{follow}` | New. Affected, observer |
| `GET /api/pulse` | Lines A1 to A5; the share visitor entry stays `POST /api/modules/m1_intent/shared/view` (14) | Existing route, new sources in `sh_platform/pulse/lines.py` |
| Wall cards in `sh_platform/profile/cards.py` and the profile `cards` | Read only; taps are not written onto the card | Existing, not changed |

Every route is declared in the module manifest with its role rule (default deny, `contracts.md`).

## Fields this feature adds to the intent record

One record per intent at `intents/<id>/intent.json`.

```
affected_access: {read_content: false, set_by, set_at, history: [{by, at, to}]}   # default false, set at creation

feel_taps: [{
  id, item: "intent" | <card id>,
  signed: true|false,
  by: person id | null,                  # only when signed
  anon_key: "anon-<random>" | null,      # only when unsigned, never linked to a seat or account (as an anonymous card)
  once_key: <one-way mark> | null,       # lets the same person take the tap back and stops a second tap; see Open questions
  relation: affected | participant,      # at the time of the tap
  at
}]

notes_to_organiser: [{
  id, text, signed: true|false,
  from: person id | null, anon_key|null,
  at, seen_at|null, reply: {by, at, text}|null   # reply only to a signed note
}]

join_requests: [{
  id, by, asked_role: participant|observer, reason, at,
  state: open|accepted|declined|withdrawn,
  answered_by|null, answered_at|null, role_given|null, decline_reason|null
}]

people_detail[].follow: false          # per person, set by "Follow this intent"
people_detail[].closed_seen_at: null   # written when the person opens the outcome (clears line A2)
```

The brief's `people.affected` and `people.observers` are unchanged. `people_detail[].role` gains no new value.

## Agent behaviour (North, Lens, Nira: what each drafts, when, and the moment a person acts)

- **Nira** writes A1 when the intent moves to `open`, for each person in `people.affected` and `people.observers` who has no stronger role, with the sentence "<Organiser> opened a <type> that touches <area>. For your information." She writes A2 when the intent moves to `closed` or `cancelled`, from `closure.summary` or the cancel reason. She writes A3 (the organiser's "things from affected people") and A4 (a request) as the records change, and A5 on an answer. She names a count, never a person, in A3. In A4 she names the asker, because a request is signed by nature. A person acts by opening the line.
- **North** drafts the closure addition: a count of notes, taps and requests, a one-line theme per group of notes with the words the person used, and any request still open. North drafts the reply to a signed note when the organiser presses "Draft a reply". North never sends it, never accepts a request, never switches the content on. The organiser acts. North does not change who is affected.
- **Lens**: none. The affected experience contains no definitions.
- Agents read affected material as the system. What they write shows to a viewer only through the same filter as content: a note's text is shown to the organiser and the sponsor, never to participants or company admin.
- Agents never sign. A named person taps, writes, accepts or declines.

## Rules (visibility, time box, who may do what)

Settled by ruling 4 of the brief (section 10): this spec's model is adopted. The switch "affected people may read" is default off, and an observer reads like a participant and never writes or votes. Files 05, 06 and 23 are being corrected to match this file.

1. Tagging an area makes every person tagged to it affected by default (06, `via: area`). Nobody tagged is left outside. A person in a stronger role keeps it.
2. An affected person sees: title, purpose, stage, clock (time box), the people list (names and roles; affected people as a count), and once closed, the outcome (`closure.summary`, `what_came_out`, `next`) and the charter, read-only. Content opens to an affected person only when `affected_access.read_content` is true or the person is named on a share.
3. The switch "affected people may read the wall" is default off and is set at creation. Only the organiser sets it. When on (or when the person is named on a share), affected people read what a participant reads, minus anything sealed to them (S) and anonymous authors (A, D-013). It never opens a restricted area or a private room.
4. An observer reads everything a participant reads, by the participant's rules, and never contributes or votes. The server refuses writes from an observer on cards, answers, taps, notes, votes and confirms. An observer is shown in the people list as Observer and is not in the people count.
5. "I feel this": one tap per person per item. Affected people and participants may tap; observers may not; the person who raised an item does not tap (their raise counts as the first, as in 21). An affected person may tap a card only when the wall is open to them (switch on); on a Problem intent they may tap the intent itself without the switch (Open question 6).
6. Who sees a tap count: organiser, sponsor, participants. The affected person sees only their own state. Company admin sees counts only (19). Names appear only for a tap the person chose to sign, and only to the organiser and the sponsor. An unsigned tap is never traced to a person for anyone, the super admin and company admin included. The super admin sees existence only (ruling 5) and never taps, notes or requests.
7. A note to the organiser is read by the organiser and the sponsor only. An unsigned note carries no name and cannot be replied to. A note never reaches participants or the wall unless the organiser copies words into the intent as a card of their own.
8. A join request goes to the organiser alone. The organiser accepts into Participant or Observer, or declines with a reason; the sponsor cannot answer. One open request per person per intent. After a decline the button shows the reason and the request cannot be repeated unless the organiser invites the person (06 "Invite again").
9. Nothing between open and close: no line for stage changes, taps, notes or reads unless the person switched "Follow this intent" on.
10. Time box: affected people and observers do not extend, close or cancel. A late request to a closed intent is refused with "This intent has closed."
11. A draft, and a cancelled intent's content, are never shown to affected people. Past intents keep the chip and the outcome.
12. No numbers in the lines other than counts from the record. Counts are exact; any mean, median or per-person figure shows "Fewer than five" below five records (ruling 8). Dates and clocks use the company's time zone from the profile, else UTC.
13. A draft intent is visible only to the person who started it. A cancelled intent keeps its reason and is shown in Past (ruling 14).

## Counters and measures of this feature (numbers only, each traced to a record)

| Counter | Counted from | Shown to |
|---|---|---|
| Affected people told per intent | `people_detail` where role is affected | Organiser, company admin |
| Of them, how many opened it | Same, where `status` is joined or later | Organiser, company admin |
| Affected people who opened the outcome | `closed_seen_at` not null | Organiser, company admin |
| "I feel this" taps per card or problem, signed and unsigned | `feel_taps` grouped by `item`, `signed` | Organiser, sponsor, participants (counts) |
| Notes to the organiser | `notes_to_organiser` length; how many have `seen_at`; how many have a `reply` | Organiser, sponsor |
| Join requests, by state | `join_requests` grouped by `state` | Organiser; company admin counts |
| Intents with the switch on | `affected_access.read_content` | Company admin, as a count |
| Followers | `people_detail.follow` true | Organiser |

Every counter that has no record yet reads "Not available yet: no <thing> recorded." There is no "reach" or "engagement" score and nothing is ranked.

## Reuse check (what exists today: file paths and line ranges found with graft; copied, reshaped or not used, and why)

| Existing | Use |
|---|---|
| `sh_platform/profile/view.py` L27-L76 (`Viewer`, `norm`, `allows`, `_passes`, `_bound`) | Reused as is for named-person matching of organiser, sponsor, participant, observer and the signing person |
| `sh_platform/profile/view.py` L171-L184 (`_cards`: sealed silhouette, anonymous `author` dropped) | Reused as is for what an affected reader and an observer see on the wall. No new filter |
| `sh_platform/profile/cards.py` L28-L31 (`anon-*` key, no author) and `modules/m1_intent/store/notes.py` L121-L130 (`anon_key` made from a random id, "nothing links it to a seat") | The method for unsigned taps and unsigned notes is copied: a random `anon-*` key, no link to account or seat |
| `sh_platform/pulse/lines.py` L22 (`MINUTES`), L350 (`running`) | Reshaped: new line sources A1 to A5 beside the existing ones; `outcome` kind is the one defined in 13. `running` counts "who has not written" as a number only; A3 follows the same count-not-name rule |
| `ui/src/pages/PulsePage.tsx` L56-L61 (`WatchCard`; page route `/pulse`, `ui/src/App.tsx` L126) | Reused as is for A1, A2, A5 in the Watch strip |
| `ui/src/modules/m1_intent/wall/InvitePanel.tsx` L9 and the 06 people panel | Not used for this feature; the organiser panel "From affected people" sits beside the 06 panel and reuses its panel chrome |
| 06 people panel, `people_detail`, "Change role", `role_history` | Reused: "Accept" on a request is a "Change role" with a recorded reason |
| 21 backlog "I feel this" button, count, and tap list (21 L44-L45, L63; names to the lead and company admin there, reshaped here to organiser and sponsor, company admin counts only) | Reshaped: same words and the same one-per-person rule; here the tap can be signed or unsigned and counts show to the organiser, sponsor and participants |
| `INTENT-CENTRE-SPEC.md` section 3 L44-L51 (anonymous per card, names only where the author chose) and section 5 row "Affected downstream" (L96, "who feels this" taps) | Reused as the source of the tap idea and the anonymity rule; Define reads the counts as "affected downstream" for the owner, counts only |
| 04 intent card and "Your role tag" | Reshaped: one chip, "Affects you" |
| `view.may_open_content` in 05 | Extended with the two branches in Rules 2 and 4 |

Searched: `graft ask` over "affected", "observer", "who feels this", "feel" and "join request" in `sh_platform`, `modules`, `ui/src`: no tap, note-to-organiser or join-request code exists. The v1 seat and join-link code (`modules/m1_intent/store/room.py`) is for seats and is not used.

Genuinely new: the two lines, the chip, the content switch, the tap with a sign choice, the note box, the join request, the observer's write refusals, the counters.

## Not in this feature

- Inviting, removing and changing roles by the organiser (06).
- Areas, tagging and the visibility matrix itself (05); this spec states two cells to change.
- The wall, cards, sealing (23, 24) and the backlog (21).
- A chat or comment thread between affected people and the organiser. The note is one way, with one optional reply.
- Email or message sending. Nothing is sent by the system.
- Ranking, scoring or sorting by taps. Taps are counts.
- Rating the outcome (10). An affected person who read the outcome may be offered a rating by 10; not specified here.

## Open questions

1. Length limits for a note (proposed 500 characters), a join reason (300) and the A2 summary line (140) are not in the brief. Nitin to confirm or change.
2. Unsigned taps and one tap per person: a one-way `once_key` (hash of account and intent salt) stops duplicates but could be reversed by someone holding the salt and the account list. Alternative: allow duplicates for unsigned taps. Which does Nitin prefer for D-013?
3. Should a count of taps be shown to affected people, or only their own state (proposed)? Showing it may help people feel heard and may also pressure them.
4. Counts are exact (ruling 8), so an unsigned tap in a very small area is nearly named. Accept, or hide per-area splits below five?
5. Do tap counts from a wall card carry over to a backlog item when the card becomes one (21)? Proposed: carry the count as a note ("6 people felt this on the wall"), not as taps.
6. On a Problem intent, may affected people tap without the switch? Proposed yes, on the intent itself, but ruling 4 lists no problem statement among what affected people see. Is the statement (`what`) part of the existence view?
7. A way for an area member to say "this does not affect me" and mute the lines? Not in this spec. Needs a decision, because the brief says everybody tagged should see the intent.
8. How long do A1 and A2 stay if never opened? Proposed: until opened, no time limit.
9. May an observer leave a note to the organiser? Proposed: no (they never contribute), they use "Ask to join" instead.
10. May the sponsor also answer join requests? Proposed: organiser only, as 06 lets only the organiser change roles.
11. Who may switch content on after a closure draft exists? Proposed: nobody once closed; the value at close stays.
12. Do taps, notes and requests live inside `intent.json` or in a sibling file in `intents/<id>/`? Proposed: `intent.json`; 01 and 16 to confirm.
