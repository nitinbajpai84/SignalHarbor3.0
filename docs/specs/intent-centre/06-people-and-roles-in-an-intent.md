# 06. People and roles in an intent

Part of: Intent Centre v2. Depends on: 01 (intent record and lifecycle), 02 (type catalogue), 05 (areas and visibility), 22, 35, 38, 41 and 43 (per-type start questions and stage screens that host the panel). Feeds: 07 (clock), 09 (closure draft: who took part), 11 (share), 13 (Pulse lines), 16 (events), 47 (affected and observer experience), 48 (admin views).

## Purpose (three sentences)

Every intent has people, and this feature says who they are, what role each holds, how they got in and where each stands. It gives the organiser one panel on every intent screen to invite, change a role, remove a person and see who has not yet done their part, and it gives an invited person a calm invitation they can accept, decline with a reason, or ignore without penalty. It gives North a record of whose turn it is so it can nudge the right person.

## Who uses it and when (role, moment, trigger)

| Role | Moment | Trigger |
|---|---|---|
| Organiser (Janet) | Opening an intent, then any time until it closes | "Add people" on the start screen, or "Invite" in the people panel |
| Sponsor (Daniel), where the type has one | Accepting the sponsor seat; later asking for a person to be added | Invitation on the Pulse page; "Ask the organiser to add someone" in the panel |
| Decider (Decision type) | Making the one decision | Organiser names the decider on the start screen of a Decision |
| Participant (Aaron) | Contributing cards, answers or views | Invitation on Pulse, email draft, or a join link |
| Affected person | Told an intent touches their area or them by name | The intent's areas or the organiser's affected list |
| Observer | Reading along without contributing | Organiser adds them as observer |
| Adviser (Decision type) | Giving a view on the one decision | Organiser adds them as adviser |
| Reporter and owner (Problem type, Harvey as owner) | Reporter raised it; owner fixes it | Reporter is whoever opened it; organiser (or North's suggestion) names the owner |
| Company admin | Seeing who is in what, never anonymous notes | Intent list, people count column |
| Super admin | Seeing the people count only | Existence view at `/centre/control/intents` |
| North | Keeping the invited list current and nudging | Every state change in the panel, and a daily check of open intents |

## Entry points (every route, link, Pulse line, button that leads here)

- Route `/centre/intent/<id>` and every view under it show the people panel (right column at 1280, a bar at 390).
- Route `/centre/intent/<id>/people` (a view named in brief ruling 1): the full people screen. Reached from "Open people" in the panel.
- Invitation: a panel on `/centre/intent/<id>?view=invitation` (ruling 18). An invited person sees the invitation card (Screen D) instead of the stage view. After "Accept" the same route shows the stage view.
- Start screen of every type (files 22, 35, 38, 41, 43): the "Who is in this?" question writes into the same people list; it has no store of its own.
- Join link: `/join/<code>` (listed guest route exception per ruling 24), the existing route in `ui/src/App.tsx`, with `POST /api/modules/m1_intent/join`. Extended so a code can name an intent.
- Pulse lines (SHAPES section 1, kind `invite`, strip `invited`): "You are invited to <title>", "You have been told about <title>", "<title> is waiting for your card". Href is `/centre/intent/<id>`.
- Pulse line for the organiser (strip `watch`, kind `ops`): "<n> invited people have not answered <title>". Href `/centre/intent/<id>/people`.
- Email draft: Nira drafts it; the organiser copies it from "Draft the email". Nothing is sent by the system.

## Screens, element by element

### Screen A. People panel (on every intent screen)

Route: any `/centre/intent/<id>` or `/centre/intent/<id>/<view>`. Layout at 1280: right column, 320 px, under the stage bar; header, list, footer actions. At 390: collapses to one line under the title ("6 people, 4 joined, 2 contributed"); tapping opens Screen B. Link, role change and remove controls appear only on Screen B at 390.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Panel header "People" with count | Panel | "People (6)" and "4 joined, 2 contributed, 1 confirmed". Numbers read from `people_detail` in `intents/<id>/intent.json` (see Counters) | Click opens Screen B | Everyone who may see the intent (affected and observers included; brief section 4, ruling 4) | "Just you so far. Invite people to start." (organiser); "Nobody else has been added yet." (others) |
| Person row | List item | Name, role chip, status chip, areas of the person | Click opens that person's drawer on Screen B (organiser); other viewers: no click | Organiser sees all rows. Participants and observers see names, roles and status. Affected people see names and roles only | See header |
| Role chip | Chip | Organiser, Sponsor, Decider, Participant, Affected, Observer, Adviser, Reporter, Owner | Organiser only: opens "Change role" menu | Everyone who sees the panel | Never empty |
| Status chip | Chip | Invited, Joined, Contributed, Confirmed, Declined (reason on hover for organiser only), Removed | None | Everyone who sees the panel except Affected, who see roles only | Never empty |
| "Invite" | Button | Opens Screen C | Opens dialog | Organiser. Sponsor sees "Ask the organiser to add someone", which writes a note to the history and sends nothing | Hidden once the intent is closed or cancelled |
| "Open people" | Link | "Open people" | Goes to `/centre/intent/<id>/people` | Everyone who sees the panel | Not applicable |
| "Waiting for" line | Agent line (North) | "North is waiting for Aaron and Katie to add a card. Last reminder 8 Oct." Date from `people_detail.reminders` in the company time zone, else UTC | "Remind them" drafts a reminder (see Agent behaviour); nothing is sent | Organiser | "Nobody is holding this up." |
| "Draft the email" | Button | Opens Nira's invite email draft in a copy box | "Copy" copies; nothing is sent | Organiser | Disabled when nobody is in Invited status |

### Screen B. Full people screen

Route `/centre/intent/<id>/people`. Layout at 1280: table of people on the left (8 of 12 columns), "Invite by link" and "Draft the email" on the right, a history strip along the bottom. At 390: table becomes cards, right-hand regions stack below, history collapses to "Show history".

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| People table | List | Name, role, status, invited by, invited on, last activity | Row click opens the person drawer (organiser only) | As panel | "Nobody has been added." |
| Filter chips "All, Invited, Joined, Contributed, Confirmed, Declined, Removed" | Chip row | Counts per status from `people_detail.status` | Filters the table | Organiser, participants, observers (Declined and Removed chips organiser only) | Chips with zero show "0" and stay |
| Person drawer | Panel | Role, status, how they arrived (picked, link or area), dates, reminders sent, decline reason, role history | Buttons below | Organiser. Others never see the drawer | Not applicable |
| "Change role" | Button then menu | Roles allowed for this intent type (see Rules) | Pick a role; a one-line reason is required when moving someone out of Participant to Observer or Affected; "Save" writes `role_history` and the event | Organiser | Menu lists only allowed roles |
| "Remind" | Button | None | Drafts a reminder for this person; nothing is sent | Organiser | Disabled when the person is Affected, Declined or Removed |
| "Remove" | Button | Dialog: "Remove Aaron? Their cards stay in the record." with a required reason field | "Remove and keep in record" writes a removal; "Cancel" closes | Organiser | Not applicable |
| "Invite again" | Button | Shown on a Declined or Removed person | Writes status Invited with new `invited_at` | Organiser | Not shown otherwise |
| "Invite by link" | Panel | Join link read-only, "Copy link", "New link", note "A new link ends the old one" (InvitePanel wording) | "Copy link" copies; "New link" calls the link route | Organiser | "No link yet. Make a link." with a "Make a link" button that calls the link route |
| Seat list | List | "Seat 1: Aaron", "Seat 2: free", "Seat 3: revoked", each with "Take back" | "Take back" calls the revoke route | Organiser | "No seats. Seats open when you make a link." |
| "Show history" | Button (390 only) | Opens the history strip | Expands it | Organiser | Not applicable |
| History strip | List | Every invitation, acceptance, decline, role change and removal in time order, with who and why. Read from `intents/<id>/events.jsonl` (file 16) | None | Organiser. Company admin sees existence of each change, no notes | "Nothing has changed yet." |

### Screen C. Invite dialog

Route: a dialog over Screen A or B (no route of its own). At 1280: 560 px wide, centred. At 390: full-screen sheet.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| "Pick from your company" | Field with list | Search over the company people list: name, role in the company, area | Select one or many; each becomes a chip | Organiser | "No one matches. Use a link instead." |
| Role selector per picked person | Field | Roles allowed for this intent type | Changes the role for that person | Organiser | Defaults to Participant. Decision: Adviser. Problem: Owner when none is named, else Affected |
| Named slots (Decision: "Decider"; Problem: "Owner") | Field | Single-person picker for the named slot | Writes `people.decider` or `people.owner` | Organiser | "Choose a decider." / "Choose an owner, or let North suggest one." |
| "Tell people in these areas" | Field | The intent's areas as chips, with the count of people in each area from the company people list | Ticking an area adds every person in it as Affected, `via: area` | Organiser | "No areas chosen. Choose areas on the first screen." |
| Range note | Agent line (North) | "Brainstorm works best with 4 to 8 invited people. You have 5." Range from brief section 2; count is the picked list | None | Organiser | Hidden for types without a stated range |
| "Send invitations" | Button | Writes the invitations as Invited, creates Pulse lines and email drafts | Saves; closes dialog; panel updates | Organiser | Disabled until one person is picked |
| "Use a join link instead" | Button | Switches to the link panel of Screen B | Makes a link if none exists | Organiser | Not applicable |
| "Cancel" | Button | Nothing | Closes without saving | Organiser | Not applicable |

### Screen D. Invitation card (what an invited person sees)

Route `/centre/intent/<id>?view=invitation`, shown while the viewer's status is Invited. Layout at 1280: one column, 640 px, centred. At 390: same column, full width, buttons stacked.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Heading | Text | "Janet has invited you to <title>" | None | The invited person | Not applicable |
| Purpose and what is asked | Text | `purpose`, the person's role in words ("You are asked to add ideas on the wall"), the end date from `time_box.ends` in the company time zone else UTC, and minutes expected from the existing `MINUTES["invite"]` constant in `sh_platform/pulse/lines.py` | None | The invited person | "The organiser has not written a purpose yet." |
| Role note | Text | Affected: "You are told because this touches Operations. You do not have to do anything." Observer: "You can read along. You do not add cards." | None | The invited person | Not applicable |
| "Accept" | Button | None | Writes status Joined; shows the stage view | The invited person | Not applicable |
| "Decline" | Button | None | Opens the reason field and "Send my reason" | The invited person | Not applicable |
| Reason field | Field | Placeholder "Why not? A short line helps Janet plan." Optional for Affected and Observer, required for Sponsor, Decider, Participant, Adviser, Owner | Typing | The invited person | Not applicable |
| "Send my reason" | Button | None | Writes Declined with the reason; shows "Thank you. Janet has been told." | The invited person | Disabled when a required reason is empty |
| "Ask for a different role" | Button | None | Opens a one-line field; "Send request" writes a note to the history; the organiser decides | The invited person | Not applicable |
| Closed or cancelled note | Text | "This intent has closed. You can read the outcome." plus the closure summary; for a cancelled intent, the reason | None | The invited person | Not applicable |

### Screen E. Pulse line and email draft

Route: none of its own. The line appears on the Pulse page (the daily page); the draft appears in a copy box on Screens A and B. Layout: a Pulse line follows SHAPES section 1; at 390 it is the same single row. The copy box is 560 px at 1280 and full width at 390.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Invite line | Pulse line | `kind invite`, `title` the intent title, `detail` the sentence for the role ("You are asked to add ideas by 10 Oct"), `due` the end of `time_box`, `source.record` `intents/<id>` | The `action` "Open the invitation" goes to `/centre/intent/<id>` | The invited person | No line when nothing is waiting |
| Affected line | Pulse line | `detail` "For your information", `action` "Read it" | Goes to `/centre/intent/<id>` | The affected person | No line |
| Organiser line | Pulse line | "<n> invited people have not answered <title>" with n from Counters | Goes to `/centre/intent/<id>/people` | Organiser | No line when n is 0 |
| Email draft box | Panel | Subject and body with organiser name, purpose, end date and link | "Copy" copies subject and body | Organiser | "Nothing to draft." |
| Reminder draft box | Panel | Subject and body from the `reminder` writer | "Copy" copies | Organiser | Not shown until "Remind them" or "Remind" is pressed |

## User journey (numbered steps from arriving to leaving, with what the agent does between the person's steps)

1. Janet opens a Brainstorm through `/centre/intent/new?type=brainstorm` and reaches "Who is in this?". She picks Aaron, Katie, Harvey and two others from the company people list, and ticks Operations as an area. Picks on a draft are held on her screen only (brief ruling 14); nobody is invited yet.
2. North counts the picked list: five picked, within the stated 4 to 8, and says so. Nira lists the people tagged to Operations who will be told as Affected, with the count from the company people list.
3. Janet opens the intent and presses "Send invitations". The system writes five people as Invited and the Operations people as Affected-told, and writes one Pulse line for each.
4. Nira drafts one invite email for the five and one "for your information" email for the Affected. Janet copies them from "Draft the email" if she wants to send mail herself.
5. Aaron opens Pulse, sees "Janet invited you to Cutting month-end close time", opens `/centre/intent/<id>`, reads the invitation card and presses "Accept". Status becomes Joined and he lands on the wall.
6. Katie presses "Decline", writes "On leave until 14 Oct", presses "Send my reason". Status becomes Declined with the reason. Janet sees it in the panel at once.
7. North notes a seat is now empty against the stated range and drafts a line for Janet: "Katie cannot join. You have four others. Add someone, or carry on." Janet picks add or carry on.
8. A person arrives by join link instead. They sign in, or join as a guest by name and role, take a seat, and appear in the panel as Joined with "via link".
9. Aaron adds his first card. Status becomes Contributed. When the stage asks each person to confirm (for example "I'm done"), status becomes Confirmed.
10. Midway through the time box North finds people still Invited or Joined with no contribution and drafts a reminder for each. Janet presses "Remind them", or does not. North never sends.
11. Janet changes Harvey from Participant to Observer ("Harvey is covering a deadline"). The change is recorded in history; his existing cards stay.
12. Janet removes a person who should not be there, with a reason. The person stays in the record as Removed; their cards stay, marked "from a person later removed".
13. On close, the closure draft lists everyone who took part with their final status. Nobody is deleted. Janet leaves the screen through "Close" (file 09).

## States and transitions (table: state, who moves it, to what, what is written)

Person status inside an intent. Each write also appends an event to `intents/<id>/events.jsonl`.

| State | Who moves it | To what | What is written |
|---|---|---|---|
| (none) | Organiser, by picking | Invited | A `people_detail` entry with role, `invited_by`, `invited_at`, `via: picked` |
| (none) | The person, by taking a seat through the join link | Joined | An entry with `via: link`, `joined_at`, and the seat reference |
| (none) | Organiser, by choosing an area | Invited (Affected only) | An entry with role Affected, `required: false`, `via: area` |
| Invited | The person, "Accept" | Joined | `joined_at` |
| Invited | The person, "Decline" with reason | Declined | `declined: {at, reason}` |
| Joined | The person's first card, answer or view | Contributed | `first_contribution_at` |
| Contributed | The person's own confirm at a stage that asks for it | Confirmed | `confirmed_at`, stage key |
| Joined or Contributed | Organiser, "Change role" | Same state, new role | An entry in `role_history`: from, to, by, at, reason |
| Any | Organiser, "Remove" with reason | Removed | `removed: {by, at, reason}`; seat set to revoked through the existing route |
| Declined or Removed | Organiser, "Invite again" | Invited | New `invited_at`; earlier decline or removal stays in events |
| Any | Intent closes or is cancelled | Status frozen | Nothing changes after; a late join is refused with "This intent has closed." |

Affected people have the same chips but are never counted as "waiting". An Affected person who opens the intent is shown Joined; Confirmed does not apply to them. Observers have no Contributed or Confirmed state: they read, so they stay Joined.

## Records read and written (file or route, fields; mark Existing or New)

| Record or route | Fields | Mark |
|---|---|---|
| `intents/<id>/intent.json`, keys `people` and `people_detail`, written through `sh_platform/jsonfile.py` | See next section | New |
| `intents/<id>/events.jsonl` | One event per invitation, answer, role change, removal, reminder (file 16) | New (written here, owned by 16) |
| `POST /api/modules/m1_intent/sessions/{id}/link` (new link) | code, state | Existing, extended so the code can name an intent |
| `GET /api/modules/m1_intent/sessions/{id}/join-link` | current link, shown again | Existing |
| `POST /api/modules/m1_intent/sessions/{id}/seats/{n}/revoke` | seat state to revoked | Existing |
| `POST /api/modules/m1_intent/join` | code, seat, name, role | Existing, extended to write a `people_detail` entry |
| Seat record in `modules/m1_intent/store/room.py`: `n, state, participant_id, name, role, account_id, token_hash, late, joined_at` | Seat | Existing, not changed |
| `JoinIndex` (code to company and session) | code hash, company, session | Existing, entry gains an optional intent id |
| `GET /api/intents/<id>/people` | People list filtered for the viewer through `sh_platform/profile/view.py` | New |
| `POST /api/intents/<id>/people` | Add by pick: person ids, roles | New |
| `POST /api/intents/<id>/people/<person>/answer` | accept or decline, reason | New |
| `POST /api/intents/<id>/people/<person>/role` | role, reason | New |
| `POST /api/intents/<id>/people/<person>/remove` | reason | New |
| `POST /api/intents/<id>/people/<person>/remind` | drafts a reminder; writes a `reminders` entry | New |
| Company people list | name, role in company, areas | Existing store (`sh_platform/profile/store.py`); route to be confirmed, see Open question 1 |
| `GET /api/pulse` | LINE with `kind invite` | Existing, new line source |
| Invite and reminder drafts | subject, body | Existing writers in `sh_platform/pulse/templates.py` |

## Fields this feature adds to the intent record

The brief's `people` object keeps its keys (`organiser, sponsor, participants, affected, observers`), written as person ids per role so other specs keep reading it. Brief ruling 13 adds three named slots, each a single person id or null, and they are separate keys, never a relabelled sponsor. `sponsor` stays and is optional per type (null where the type has none). This feature adds one further key, `advisers`.

```
people.decider: person id | null      # Decision type; the named slot, not the sponsor
people.owner: person id | null        # Problem type
people.reporter: person id | null     # Problem type
people.advisers: [person id]          # Decision type
people_detail: [{
  person_id, name,
  role: organiser|sponsor|decider|participant|affected|observer|adviser|reporter|owner,
  status: invited|joined|contributed|confirmed|declined|removed,
  required: true|false,                       # false for affected and observer
  via: picked|link|area,                      # area = told because of an area tag
  invited_by, invited_at,
  joined_at|null, first_contribution_at|null, confirmed_at|null,
  declined: {at, reason}|null,
  removed: {by, at, reason}|null,
  role_history: [{from, to, by, at, reason}],
  reminders: [{at, drafted_by: "north", sent_note: "organiser copied"|null}],
  seat_ref: {session_id, n}|null              # points at the existing seat, never copies it
}]
```

## Agent behaviour (North, Lens, Nira: what each drafts, when, and the moment a person acts)

| Agent | Drafts | When | Person acts |
|---|---|---|---|
| North | Whose turn it is, per person, from `people_detail` and the stage | On every change, and once a day for open intents | Organiser presses "Remind them" or ignores it |
| North | A suggested owner on a Problem, from the area tag | When the Problem is opened without an owner | Organiser accepts or names someone else |
| North | A line when declines leave too few people for the type's stated range | After a decline or removal | Organiser adds, carries on, or extends (recorded in `time_box.extended_by`) |
| North | A reminder to a person whose turn it is: invited and not answered, joined and not contributed, contributed and not confirmed | Per the reminder rule (Open question 2) | Organiser copies it; the system does not send |
| Nira | The Pulse lines for each person (invited, told, waiting for your card) and the organiser's "not answered" line | On every change to `people_detail` | The person opens the line |
| Nira | The invite and reminder email drafts | On "Draft the email" or "Remind" | Organiser copies and sends from their own mail |
| Lens | Nothing in this feature | Not applicable | Not applicable |

Agents never invite, remove, change a role or accept for anyone. A named person does each of those.

## Rules (visibility, time box, who may do what)

**Named slots per type (brief ruling 13).**

| Type | Named slots and roles available |
|---|---|
| Initiative | organiser; sponsor (optional); participant, affected, observer |
| Brainstorm | organiser; participant, observer; affected optional (they read the outcome only unless the organiser switches on reading) |
| Weekly check-in (record key `pulse`) | organiser; participant, observer, affected |
| Problem | organiser; reporter and owner (both named slots); affected, observer |
| Decision | organiser; decider (named slot); adviser, affected, observer |

**Who may do what.**
- Only the organiser invites, changes a role, removes a person, makes or ends a join link and takes back a seat. A sponsor may ask; the ask is recorded as a note and the organiser acts.
- Only the person themselves accepts, declines or confirms. Nobody does it for them, and agents never do.
- A person may be removed with a reason that is kept; there is no hard delete. The record shows the name, the role they had, the date and the reason.
- Removing a person revokes the seat through the existing revoke route. Their earlier cards and comments stay, marked.
- The organiser cannot remove or demote themselves; they hand over by changing the organiser role to another person, which needs that person to be Joined.
- The reporter slot is set to whoever opened the Problem and is not changed by the organiser except to correct a mistake, with a reason.
- Invitations are written only when the intent is open. A draft intent is visible only to the person who started it (brief ruling 14), so picks on a draft are held and sent when it opens.

**Affected rule (brief ruling 4).** An affected person, by area or named, sees existence, title, purpose, stage, clock, people (names and roles) and the outcome once closed. They open content only when the organiser has switched on "affected people may read" at creation (default off) or when they are named on a share. They never write or comment unless moved to Participant. They are never counted as "waiting", are not reminded after the first telling (Open question 3), never block closing, and are `required: false`.

**Observer rule (brief ruling 4).** An observer reads what a participant reads. They never write or vote. They are `required: false`.

**Decline.** A reason is required for Sponsor, Decider, Participant, Adviser and Owner, optional for Affected and Observer. A decline closes that person's seat if they had one. A Decider or Owner decline sends North's line to the organiser to name another person before the intent can move on.

**Visibility.** Everyone tagged to the intent's areas sees that the intent exists and who organised it (brief section 4). Participants and observers see names, roles and status of everyone; they never see decline reasons, role history or removal reasons (organiser and company admin only; the company admin never sees anonymous notes). Affected people see names and roles only. A super admin sees the people count and never names or reasons (brief ruling 5). Anonymous and sealed material keeps the v1 rules (D-013, seal): the panel shows that a person contributed, never what an anonymous contribution said.

**Time box.** The invitation card shows the end date from `time_box`. Accepting does not extend it. Late joiners are allowed until the intent is closing; after that the join link says "This intent has closed."

**Share link.** The people list is not part of a share view beyond "who said it" for non-anonymous items. Removal and decline reasons never appear in a share view.

**Numbers and dates.** Dates show in the company time zone from the profile, else UTC. Counts are exact. A median or mean shows "Fewer than five" below five records (brief ruling 8).

**Company.** Everything resolves from the signed-in company; a join code from another company fails closed with the existing message.

## Counters and measures of this feature (numbers only, each traced to a record)

| Measure | Traced to | Where shown |
|---|---|---|
| People in the intent | Count of `people_detail` where status is not Removed, in `intents/<id>/intent.json` | Panel header |
| Joined, Contributed, Confirmed counts | `people_detail.status` | Panel summary |
| Invited and not answered | `people_detail` with status Invited and `required` true | Organiser's "waiting for" line and Pulse line |
| Declined count | `people_detail.declined` not null | Filter chip |
| Removed count | `people_detail.removed` not null | Filter chip |
| Told as affected | `people_detail` where role is Affected | Panel summary |
| Time from invited to joined (median, per intent) | `joined_at` minus `invited_at` | Company admin intent view; "Fewer than five" when under five joins |
| Reminders drafted and copied | `people_detail.reminders` | History strip |

Nothing is shown as a rate or a score. Counts are exact even under five, because the people are named inside the intent. Aggregates across intents follow brief ruling 8.

## Reuse check (what exists today: file paths and line ranges found with graft; copied, reshaped or not used, and why)

All paths below were checked to exist in this repo.

| What exists | Where | Verdict |
|---|---|---|
| Join link create, show again, revoke seat | `modules/m1_intent/api/room.py` lines 195 to 233 (`new_link` at 197, `current_link` at 207, `revoke_seat` at 223) | Reused as is for wall-backed intents. Reshaped for the others: the code maps to an intent id in `JoinIndex`. No second link mechanism is built. |
| Join by code, seat taking, guest token | `modules/m1_intent/api/room.py` lines 350 to 392 (`join` at 352) | Reused; extended so a successful join also writes the intent's `people_detail` entry. |
| Seat store, `JoinIndex`, seat states | `modules/m1_intent/store/room.py` (`JoinIndex` at 40, `RoomStore.revoke` at 156, `take` at 181) | Reused. The seat stays the truth for who sits at a wall; `seat_ref` points at it. |
| Session create and read | `modules/m1_intent/api/session.py` | Reused; the session stays where it is and the intent record points at it. |
| Organiser invite panel (link, copy, new link, seat list, revoke) | `ui/src/modules/m1_intent/wall/InvitePanel.tsx` lines 1 to 70, wording in `wall/copy.ts` | Copied and reshaped into "Invite by link" and the seat list on Screen B. Wording kept ("A new link ends the old one"). People list, role chips and status chips are new. |
| Pulse line shape, `invited` reader, `MINUTES` and `SILENT` | `sh_platform/pulse/lines.py` (`line` at 71, `invited` at 113, `running` at 350, `waiting` at 386; constants at 21 and 22); SHAPES section 1 in `docs/plan/SHAPES.md` | Reused. A new reader `intent_people` is added in the same style (viewer filtered, `safe`). `MINUTES["invite"]` supplies "minutes expected". |
| Invite and reminder email drafts | `sh_platform/pulse/templates.py` (`invite` at 16, `reminder` at 23) | Reshaped: the `purpose` and `closes` keys fit; a new writer is added only for the "for your information" email. |
| Viewer filtering | `sh_platform/profile/view.py` (`Viewer` at 27, `allows` at 38) | Reused for who sees the people list and reasons. |
| One JSON file per record | `sh_platform/jsonfile.py` | Reused for `intent.json`. |
| Company people list store | `sh_platform/profile/store.py` | Candidate only; whether it holds a pickable people list is Open question 1. |
| Charter signer roles | `modules/m1_intent/api/charter.py` lines 55 to 62 | Not used; signing is not a people role. |
| Approver link | `modules/m1_intent/api/approver.py` | Not used; separate signing flow. |

Searches run: invite, seat, revoke, join, link across `modules/m1_intent/api`; the full read of `InvitePanel.tsx`; the function list of `sh_platform/pulse/lines.py`; `templates.py` in full; the file list of `sh_platform/profile`. Nothing exists for named people slots beyond organiser and seat, for decline with reason, for removal with a kept record, or for affected-but-not-required people. Those are the new parts.

## Not in this feature

- The content of any stage (cards, answers, views). This feature only reads "has contributed".
- Signing, approval and the approver link. Separate flow.
- Sending email. Drafts only; the organiser sends.
- Company people list administration (creating accounts, changing company roles).
- Rating an intent, and the closure draft text.
- Visibility and share-link rules beyond what the people panel shows (files 05 and 11).
- Anonymous or sealed contribution rules (v1 rules stay).
- Gap analysis and Build roles (Build centre).

## Open questions

1. Where is the company people list read from today? The reuse pass found no route for "pick a person". Proposed: a read-only list from company accounts through `sh_platform/profile`, filtered by the viewer.
2. Reminder cadence. The brief gives no threshold. Proposed: one reminder at half the time box, then none unless the organiser asks. The existing `SILENT` (3 days) is used only for the organiser's "waiting on others" line. Needs Nitin's decision.
3. Do Affected people get a reminder at all after the first telling? Proposed: no.
4. Decision type: ruling 13 gives `decider` as its own slot, so there is no sponsor relabelling. Should a Decision also allow an optional sponsor? Proposed: no.
5. Should a declined Sponsor stop the intent opening, or only warn? Proposed: warn; the organiser may carry on without a sponsor where the type allows.
6. May an Observer be moved to Participant after the time box has half run? Proposed: yes, with a reason.
7. The join link `/join/<code>` is an existing route outside the `/centre/intent/...` convention. Keep it as the guest entry, as the share visitor entry is kept (ruling 1)?
8. Join link for intents with no wall (Problem, Decision): signed-in only, since there is no seat room to hold a guest token? Proposed: yes.
9. Can a person tagged Affected by two areas be told twice? Proposed: once, with both areas named.
10. Seat limits. The v1 room has a fixed seat count; the Brainstorm range of 4 to 8 is a guide, not a cap. Confirm no hard cap applies to Initiative or the Weekly check-in.
11. Draft intents hold picks without inviting (ruling 14). Confirm that "Send invitations" is available only once the intent is open.
12. The invitation card shares the route `/centre/intent/<id>` instead of a new view, because ruling 1 lists no `invitation` view. Confirm, or add the view to ruling 1.
13. This file adds `people.advisers` and `people_detail` to the record, beyond the three slots in ruling 13. Confirm file 01 carries them.
