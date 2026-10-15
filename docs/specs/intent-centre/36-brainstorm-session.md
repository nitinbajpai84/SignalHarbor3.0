# 36. The Brainstorm session screen

Part of: Intent Centre v2. Depends on: 00-BRIEF, 01 (intent record), 02 (types catalogue, Brainstorm), 06 (people and roles), 07 (time box and stage clock), 17 (phone and projector views), 24 (card model, Screen D). Feeds: 37 (converge and choose), 09 (closure), 10 (ratings).

## Purpose (three sentences)

The Brainstorm session is the live stage of a Brainstorm intent: six or seven people look at one problem statement, add ideas to one open lane, see North group them as they land, and build on each other's ideas, with a clock the organiser runs. It is a configuration of the existing wall, not a new screen: the same lane, card, North panel and projector components, with one lane, one-quarter cards, a session bar and three phases. The first two phases (diverge and group) are specified here; the third (converge) hands over to 37.

## Who uses it and when (role, moment, trigger)

| Role | Moment | Trigger |
|---|---|---|
| Organiser (Janet) | Opens the session at the slot set in the start questions, runs the clock, moves the phases, closes it | Intent in stage `live_session`, button "Open the session" |
| Participant (Aaron, Katie, 4 to 8 invited) | Adds ideas, builds on ideas, moves cards in the group phase | Invitation link, or Pulse line "Your brainstorm is open, join now" |
| Observer | Reads the lane, adds nothing | Named in `people.observers` (06) |
| North (agent) | Drafts the prompts, groups and names ideas as they land, nudges quiet seats | Session opens; each new card; "Group again" |
| Nira (agent) | Sends the Pulse lines "session opens in 15 minutes" and "session is open" | Session slot, open |
| Super admin, company admin | Not in the session. Admin sees the intent exists and its outcome, never an anonymous card's author (brief section 4) | None |

## Entry points (every route, link, Pulse line, button that leads here)

- Route `/centre/intent/<intent_id>/session` (the live session; the intent page of a Brainstorm shows the stage "Live session" with the button "Join the session" once open). Today's wall route `/m1/sessions/<id>/wall` is not reused as a URL, only its components.
- Invitation link from 06 (opens the session when it is live; before it is live shows "The session opens <when>").
- Pulse line from Nira: "Your brainstorm opens at <time>" and "Your brainstorm is open. Join now."
- Intent page button "Open the session" (organiser), which also opens this route.
- Projector page `/centre/intent/<intent_id>/projector` (copy link from the session bar; the local toggle in `WallScreen.tsx` also switches display mode on the session route).
- Route family (New, thin, over the existing card and board routes): `POST /api/intents/{id}/session/open`, `/pause`, `/resume`, `/phase` (body: `group` or `converge`), `/close`; `POST /api/intents/{id}/session/group` (North groups); `POST /api/intents/{id}/cards/{card_id}/replies`; `GET /api/intents/{id}/session` (phase, clock, prompt, counts, groups, polled every 3 seconds).

## Screens, element by element

### Screen A: the live session (`/centre/intent/<id>/session`)

Layout at 1280, four regions:
1. Top: crumb, the problem statement (large, two lines), the phase strip (Diverge, Group, Converge), the clock, "Live" and "5 / 7 people".
2. Left, wide: North's drafted prompt for this phase, then the single idea lane. In the group phase the lane becomes group columns.
3. Right, 360 px: North panel (the groups so far with names and counts, and North's lines). The organiser's session bar sits above it.
4. Bottom of the lane: the idea box "Add your idea" (a Screen D card form, inline, not a drawer).

At 390 (see 17, Family 5): sticky top 64 px with clock and problem statement (one line, tap to expand); phase strip as a one-line chip; the lane below, cards stacked; North panel becomes a sheet; the bottom bar holds the primary "Add an idea" and secondary "Talk to North". The organiser's controls move into a "More" menu in the bottom bar.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Problem statement | Heading, two lines | `intent.title` and `intent.purpose` (drafted by North from start question 1 and confirmed by the organiser), under the lead "What are we thinking about:" | Tap at 390 expands the full text and the good outcome (start question 2, `outcome.brainstorm`, 35) | Everyone in the session | "The organiser has not written the problem yet." (cannot happen after start; shown in a draft) |
| Phase strip | Three chips (Diverge, Group, Converge), current one lit, earlier ones ticked | The phase now and the two rules for it ("Everyone adds. No judging.") | None. Moved only by the organiser's controls | Everyone in the session | Before opening: all three grey, line "The session has not opened." |
| Session clock | Large time (existing `StageTimer.tsx`) | Time left in this phase, `mm:ss` | None | Everyone in the session | "Not available yet. The session has no end set." |
| Live dot and people count | Chip and text (existing `t.live`, `t.people`) | "Live" while open and not paused; "Paused" in amber while paused; "5 / 7 people" (people who have the screen open of those invited) | None | Everyone in the session | Count hidden when the server does not give it; "Live" hidden before opening |
| North's prompt | Agent line | The prompt for this phase (see Agent behaviour), labelled "North suggests" and, once the organiser has edited it, "Edited by Janet" | Organiser: "Edit the prompt" opens a text field, "Use it" or "Reset to North's words". Others read only | Everyone in the session | Not shown until North has drafted it |
| Idea lane | List (existing `Lane.tsx`, one lane) | Idea cards newest first in diverge; in the group phase the cards sit in their groups. "Nothing here yet." until the first card | Tap a card to open it (Screen B) | Everyone in the session | "No ideas yet. The first idea you add appears here at once." |
| Idea card | Card (existing `Card.tsx`, one quarter) | The idea text, initials or "Anonymous", the reply count, the group name chip (group phase), no four-segment edge | Tap opens Screen B | Per card rules | Not applicable |
| Idea box | Field plus button (Screen D of 24) | Placeholder "Add your idea in a sentence or two"; optional second field "Why it would work" behind a link "Say why (optional)"; tap "Hide my name" (only if allowed, see Rules) | "Add" writes the card (see Records) and clears the field. Voice button as today | Participants, while phase is diverge or group and the session is not paused | Add stays off until the idea field has words. Paused: "The session is paused." and the field is read-only. Converge: hidden |
| Hide my name | Toggle | "Hide my name. Nobody can see who wrote this, not Janet, not an admin." | Sets `anonymous` on that card only | Participant, only when the organiser allowed anonymous ideas at open (`outcome.anonymous_ideas`, 35) | Off by default; not drawn when anonymous ideas are not allowed |
| Group panel | List in the North panel | North's groups: group name, count, first line of its newest idea. Updates after each new card (see Agent behaviour). A line "Not grouped yet" for cards North has not placed | Tap a group scrolls the lane to it (group phase) or filters the lane to it (diverge) | Everyone in the session | "North starts grouping when there are enough ideas." (the threshold is the existing `min_notes`, see Open question 2) |
| Group again | Button | "Group again" | Organiser only. North regroups all current cards. Asks "Group again? People's moves are kept as moves, not undone." Yes or No | Organiser | Disabled with "Add ideas first" when fewer than `min_notes` cards (value: Open question 2) |
| Move to group | Menu on a card, drag on 1280 | The group names and "A new group" | Group phase only. Writes the move (see Records). Everyone sees it on the next poll | Participants and organiser, group phase | Not shown in diverge or converge |
| Rename group | Link beside a group name | "Rename" | Group phase. Opens a one-line field, Enter saves | Organiser and participants in the group phase | Not shown outside the group phase |
| Organiser's session bar | Panel (reshaped `StageBar.tsx`) | Phase chips, then one primary button per state (see Session bar below), and "Projector view" | Each button asks "Are you sure?" with Yes or No, as `StageBar` does today | Organiser only | Before opening: only "Open the session" |
| Projector view | Chip (existing `t.projector`) | "Projector view" or "Back to the full view" | Toggles display mode and fullscreen (see Screen C) | Organiser only | Hidden for everyone else |
| Error line | Text | "That did not work. Try again." with Try again (`wallCopy.failed`, `retry`) | Repeats the call | Everyone in the session | Not shown |

Session bar, button by state (the organiser's controls):

| State of the session | Primary button | Other buttons | What it does |
|---|---|---|---|
| Not opened | Open the session | none | Starts phase Diverge and the clock; writes `session.opened_at` |
| Diverge, running | Move to group | Pause, Projector view | Ends diverge, starts group |
| Group, running | Move to converge | Pause, Group again, Projector view | Ends group, hands over to 37 |
| Diverge or group, paused | Resume | Move to group or converge (as above), Close the session | Clock stops while paused; adding is read-only |
| Converge | (37 owns its buttons) | Close the session | Ends the live stage; the intent moves to stage `choose` |
| Any open phase | Close the session | none | Asks "Close the session now? Ideas are kept." Ends it early with what exists, shown to 37 and the closure draft |

### Screen B: an idea opened (a panel over the lane; full page at 390)

Route: none of its own. It opens over the session route as `/centre/intent/<id>/session?card=<card_id>` (a query on the same page, so no new route; Open question 11). This is Screen C of 24, cut down to one quarter, plus the replies.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Idea text | Text | The full idea, then "Why it would work" if given | None | Everyone in the session | "(No words)" never shown, an idea needs words |
| Author line | Text | The person's name where they chose a name (full name here, initials on the lane); "Anonymous" otherwise | None | Everyone in the session, organiser included, under the anonymous rule | "Anonymous" |
| Group chip | Chip | The group name | Group phase: opens Move to group | Everyone in the session | "Not grouped yet" |
| Replies | List | Each "build on this" reply: text, initials or "Anonymous", time. Oldest first | None | Everyone in the session | "No one has built on this yet." |
| Build on this | Field plus button | Label "Build on this", placeholder "Add to this idea, do not judge it", button "Add to the idea", tap "Hide my name" (only if allowed, see Rules) | Writes a reply under this card (see Records). Replies are not cards: they do not appear in the lane and are not counted as ideas | Participants, diverge and group phase, session not paused | Add stays off until words. Paused or converge: hidden |
| Edit, Withdraw | Buttons (Screen C of 24) | Edit, Withdraw on the person's own idea | Same rules as 24: author only, until the live session closes | Author | Not shown after the session closes |
| Close | Button | Close | Returns to the lane | Everyone | None |

### Screen C: projector view (`/centre/intent/<id>/projector`, per 17)

At 1280 and above, 1920 by 1080 on a projector. Top strip: problem statement left, clock right (72 px). Middle: in diverge the count of ideas (56 px) under the lane heading; in group the group names with a count each. Bottom strip: join box with QR (left), people count and Live (right).

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Problem statement | Text, 40 px | As Screen A | None | Display | "No question is set yet." |
| Phase and prompt | Text | Current phase name and North's prompt, up to three lines | None | Display | Hidden when no prompt |
| Idea count | Number, 56 px | Ideas in the lane, not withdrawn | None | Display | "0" is a real count |
| Group names and counts | List, large | Group name and number of ideas | None | Display, group phase only | "Not grouped yet" |
| Clock, Live, people count, join box | As 17 | As 17 | None | Display | As 17 |

The projector never shows idea text, replies, authors, initials, avatars, the North panel, the idea box, the session bar or any admin control (17, "What the projector never shows"). Whether it may show idea text in the group phase is Open question 4.

## User journey (numbered steps from arriving to leaving, with what the agent does between the person's steps)

1. Nira sends the six invited people "Your brainstorm opens at 10:00" (company time zone from the profile, else UTC). North has already drafted the diverge prompt from Janet's start answers.
2. Janet opens the session route and presses "Open the session", then Yes. Phase Diverge starts, the clock runs, the problem statement and North's prompt show for everyone. Nira's second line goes out: "Your brainstorm is open. Join now."
3. Aaron opens the link on his phone. He sees the clock, the prompt and an empty lane. He types "Pay custodians by a morning cash sweep" and presses Add. The card appears for everyone within three seconds, with "A" on it (initials are shown by default only if he did not tap Hide my name).
4. Janet allowed anonymous ideas at open. Katie taps Hide my name and adds an idea. Her card shows "Anonymous". Janet cannot see who wrote it and has no control that would show it.
5. North (agent) groups the ideas as they land. After the third idea the group panel shows two named groups; each new card is placed into a group or listed "Not grouped yet". Groups are suggestions.
6. Harvey opens Aaron's card and adds "Build on this: only for balances over a set amount". The reply sits under the card. No one votes; there is no vote control in this phase.
7. Janet sees the lane has settled and presses "Move to group", then Yes. Phase Group starts with its own clock. North's group prompt appears ("These are the groups I see. Move any card that sits wrong, rename any group.").
8. People move cards between groups and rename groups. Janet presses "Group again" once; North regroups, and moves already made stay in the move history.
9. Janet presses "Move to converge", then Yes. The screen hands over to 37 (the same session route, converge phase). The clock for converge starts.
10. After 37 chooses an idea, Janet presses "Close the session" (or 37's own close). The ideas, replies and groups are kept in the record; the intent moves to stage `choose`.
11. Janet may pause at any time ("Pause"); the clock stops, adding is read-only, and "Paused" shows to everyone. "Resume" continues.

## States and transitions (table: state, who moves it, to what, what is written)

The session has its own state inside the intent's stage `live_session` (02). The intent `state` is `open` before the session, `in_session` from opening, and `closing` once the session is closed (01).

| State | Who moves it | To what | What is written |
|---|---|---|---|
| `not_opened` | Organiser, "Open the session" | `diverge` | `session.opened_at`, `session.phase = diverge`, `session.phase_started_at`; `intent.state = in_session`; `stages[live_session].opened_at` |
| `diverge` | Organiser, "Move to group" | `group` | `session.phases[] += {phase: diverge, started, ended}`; `phase = group` |
| `group` | Organiser, "Move to converge" | `converge` | Same pattern; `phase = converge`; 37 takes over |
| `diverge` or `group` | Organiser, "Pause" | same phase, `paused: true` | `session.pauses[] += {by, at}`; clock stops |
| paused | Organiser, "Resume" | same phase, `paused: false` | `pauses[last].ended = at`; clock continues with the time that remained |
| any open phase | Organiser, "Close the session" | `closed` | `session.closed_at`, `session.closed_by`, `session.closed_early: true` if before converge ended; `stages[live_session].closed_at`; `intent.state = closing` once 37 and closure start |
| any open phase | North, on the clock reaching zero | phase stays, flag `over_time` | A North line "The clock is at zero. Move on, add time or close." No automatic move: a person moves it (brief section 5, North nudges, people act) |
| any | Organiser, "Add time" (minutes, in a small prompt) | same | `session.extended_by[] += {by, at, minutes, reason}`; the intent's `time_box.extended_by` is only for days (07) |

Backward moves (group back to diverge) do not exist. If more ideas are needed, the organiser opens a second Brainstorm (Open question 6).

## Records read and written (file or route, fields; mark Existing or New)

| Record | Fields | Mark |
|---|---|---|
| `intents/<id>/intent.json` (01) | `state`, `stages[live_session]`, `people`, `title`, `purpose`, `outcome`, `closure` | Existing (defined in 01) |
| `intents/<id>/intent.json` `session` block | `{phase, paused, opened_at, phase_started_at, phases[], pauses[], extended_by[], prompts{diverge, group, converge}, closed_at, closed_by, closed_early}` | New (see "Fields this feature adds") |
| `profile.json` section `cards` through `sh_platform/profile/store.py` | One card per idea: `q1` (idea), `q2` (why it would work, optional), `q3` and `q4` stored as empty cells, `lane` (a single lane value), `anonymous`, `author` or `anon_key`, `cluster` (group), `intent_id`, `session_kind: brainstorm` (the profile value 24), `on_wall: true`, `placed_at`, `withdrawn`, `edits[]`, `moves[]` | Existing section and fields; `intent_id`, `session_kind`, `on_wall`, `placed_at`, `withdrawn`, `edits[]`, `moves[]` are New in 24, used here as defined there |
| Card `replies[]` | `[{id, text, anonymous, author|anon-*, at}]` | New (24 says comments and replies are not in the card feature; this feature adds this one field) |
| Profile read filter `sh_platform/profile/view.py` `_cards` | Drops `author` on an anonymous card for every viewer, including the organiser | Existing. Extended to filter `replies[].author` the same way |
| Groups, in the intent record's board file: `modules/m1_intent/store/board.py` (`clusters`, `edits`) | Group id, name, colour, note ids, `by` (north or person), `fallback` flag; edits as `{by, kind}` | Existing. Written under the intent id instead of a session id (reshape: key by intent) |
| Group routes: `board/group`, `board/notes/{id}/move`, `board/clusters/{id}/rename`, `board/clusters/{id}/split`, `board/restore` in `modules/m1_intent/api/board.py` | North grouping, move a note, rename, split, restore | Existing. Reshaped, see Reuse check |
| Counts poll `getBoardCounts` / `board_counts` (`api/board.py` line 147) | Cards per lane, extended with `groups` and `phase` and `clock` | Existing, extended |
| `modules/m1_intent/contracts/intent_types.yaml` brainstorm block (02) | stage keys, people limits | New (proposed in 02; the file does not exist yet, checked) |
| `intents/<id>/events.jsonl` (16) | One line per phase move, pause, resume, add time, close, regroup and prompt edit; the intent record holds counts only | New (defined in 16) |
| Run log (`RunRegistry`) | Each North grouping and prompt draft, with company id | Existing |

Anonymous rule in the record: an anonymous idea or reply carries `anon-<id>`, never a name (D-013, as 24). A person who edits or moves their own anonymous card is written as the `anon-*` key. A move by another person on an anonymous card names the mover.

## Fields this feature adds to the intent record

```
session: {
  phase: not_opened|diverge|group|converge|closed,
  paused: bool,
  opened_at, phase_started_at,
  phases: [{phase, started, ended}],
  pauses: [{by, at, ended}],
  extended_by: [{by, at, minutes, reason}],
  prompts: {diverge, group, converge: {text, drafted_by: north, edited_by|null, edited_at|null}},
  anonymous_ideas: bool,              # read from outcome.anonymous_ideas (35); not a new field
  closed_at, closed_by, closed_early
}
```

On a card (profile `cards`): `replies: [{id, text, anonymous, author, at}]` (New). All other card fields are those of 24. `outcome` (`ideas_kept`, `dropped`, `chosen`) is written by 37 and 09, not here; this feature only provides the cards, groups and replies that `ideas_kept` points at, by reference (01: the record points, never duplicates).

## Agent behaviour (North, Lens, Nira: what each drafts, when, and the moment a person acts)

North's drafted prompts, shown as "North suggests". The organiser may edit any of them before or during the phase; the edit is kept with name and time and North never overwrites it (hard rule 7).

| Phase | North's drafted prompt (filled from the problem statement) |
|---|---|
| Diverge | "Add as many ideas as you can for: <problem statement>. One idea per card. Short is fine. Do not judge or reject any idea, yours or anyone's. You may build on an idea; you may not argue with it." |
| Group | "These are the groups I can see. Read them. Move any card that sits in the wrong group. Rename any group that is badly named. Do not add new ideas now; add a build-on note if one occurs to you." |
| Converge | Drafted in 37. |

- **North groups as ideas land.** Once there are at least `min_notes` ideas, North groups every new card by calling the existing grouping on the intent's cards (single kind, so one pass), after each batch of cards, at an interval not yet set (Open question 2). North gives each group a short plain name (length limit: Open question 2). North works on the idea text only, never the author, and never reads a withdrawn card. It marks a grouping made by the keyword fallback ("Grouped by shared words, check it", existing `fallback` flag). Groups are suggestions; in the group phase people move cards and rename groups and their edit stands.
- **Group again.** The organiser's button reruns North on all current cards. People's earlier moves stay in `moves[]`; North may move a card again, and says so in a line ("I moved 3 ideas. 2 were moved by people before.").
- **Quiet seat nudge.** North may say, in the organiser's North panel only, "Two people have not added an idea yet" (a count, never names) at a point the organiser sets (Open question 3). It never says who.
- **Closing draft.** On close North drafts the thinking-kept summary for 37 and the closure draft (09), listing groups and counts. A person edits and confirms it.
- **Lens** does not act in this feature.
- **Nira** puts two Pulse lines (15 minutes before the slot; at opening) and one for the organiser when the session closes with no chosen idea ("Your brainstorm closed without a chosen idea. Pick one or cancel."). Nira does not read idea text.
- Agents never add an idea, never vote, never move the phase, never delete. The organiser moves the phase; people add and move cards.

## Rules (visibility, time box, who may do what)

- **No votes in diverge.** No vote, tick, star or ranking control exists in the diverge phase. Voting belongs to converge (37). The same holds in the group phase.
- **Anonymous is real.** A card or reply marked "Hide my name" never carries the name in the record (D-013), so no screen, export or admin view can show it. The organiser cannot see who wrote an anonymous card: there is no control or route for it, and `view.py` drops the author for the organiser as for everyone. The text of an anonymous card is masked of names as `wall_anonymous` does today. The projector shows counts and group names only.
- **Names rule.** Follows 35: "Hide my name" is offered only when the organiser set `outcome.anonymous_ideas` at open (default off). When off, every card carries its author's name. A fixed-anonymous session is not offered (Open question 12).
- **No seal in a brainstorm.** Ideas are about solutions; the seal tap does not exist here (24, Open question 3, same answer as 24 until confirmed).
- **Who may add:** participants (4 to 8 invited, 02) and the organiser, while the phase is diverge or group and the session is not paused. Observers read only. Observers read what a participant reads and never write or vote. Affected people (by area or named) see that the intent exists, its stage and clock, but not the session, unless the organiser switched on "affected people may read" at creation (default off) or named them on a share (brief section 10, ruling 4). Draft intents are visible only to their organiser.
- **Who may edit or withdraw:** the author of an idea, until the live session closes (24). Nobody else edits another person's words.
- **Who may move cards and rename groups:** participants and the organiser, group phase only. This widens 24's "committee only" for the brainstorm, because the group phase is where the whole room moves cards. Every move is kept with the mover's name unless the mover moved their own anonymous card.
- **Phases:** only the organiser moves a phase, pauses, resumes, extends or closes. North nudges at zero; it does not move.
- **Time box:** the live session has its own clock (`session`), set by the organiser at opening (suggested minutes drafted by North; see Open question 1). It sits inside the one-day `live_session` stage and the three-day Brainstorm box (07). North warns when the stage clock will pass the intent's end (07).
- **Counts:** idea counts exclude withdrawn cards. Every number traces to the cards record or reads "Not available yet".
- **Everything is kept.** Withdrawn ideas stay in the record, marked withdrawn. Closing the session deletes nothing.
- **Phone:** every action reachable by tap; moving a card on a phone is the menu "Move to group", never a drag-only gesture (17).

## Counters and measures of this feature (numbers only, each traced to a record)

| Number | Source |
|---|---|
| Ideas added, total (exact). Per person: never for anonymous cards, and "Fewer than five" where the person has fewer than five ideas (brief section 10, ruling 8) | `profile.cards` where `intent_id` and `session_kind: brainstorm`, `on_wall`, not withdrawn |
| Ideas added in diverge, in group | `placed_at` against `session.phases[]` |
| Anonymous ideas | cards with `anonymous: true` (a count only) |
| Build-on replies | `cards[].replies[]` count |
| Groups made by North, groups renamed or created by people | board `clusters[].by` and `edits[]` |
| Cards moved by people | `moves[]` where `kind: cluster`, by person |
| Phase durations, pauses, minutes added | `session.phases[]`, `pauses[]`, `extended_by[]` |
| People who added at least one idea of those invited | cards by author (named or anonymous key) against `people.participants` count; shown as a count, never names |
| Ideas per participant in the first five minutes (a per-person figure: "Fewer than five" below five records) | `placed_at` against `opened_at`; feeds 10 and 19 |

## Reuse check (what exists today: file paths and line ranges found with graft; copied, reshaped or not used, and why)

Searches run: `graft ask "wall lanes and card"`, `graft ask "north groups the notes"`, `graft find "StageTimer"`, `graft find "usePolled"`, and a read of the files below. This screen is a configuration of the wall (one component tree), not a new screen.

| Existing | Where | Decision |
|---|---|---|
| Wall screen: header, lanes, tabs, projector toggle, North aside or sheet | `ui/src/modules/m1_intent/wall/WallScreen.tsx` (whole file, 185 lines; `LANES` line 18, phone width 700 line 19, projector state line 102, phone tabs lines 158 to 166, North sheet lines 173 to 180) | Existing. Used as is, with a mode (see "The configuration" below). Not forked |
| Lane component | `wall/Lane.tsx` (24 lines, `SHOWN` 6) | Existing. Used as is for the one lane; the lane heading is replaced by the problem statement through a `showHead` prop |
| Card component | `wall/Card.tsx` (109 lines; `Edge` 33 to 39) | Existing. Used with `quarters: null` and `kind: "idea"`, so no edge shows (24, Screen D). Reshape: foot to initials (24), reply count, group chip |
| North panel | `wall/NorthPanel.tsx` (144 lines; four-question flow, quarter bars, answer box) | Existing. The four-question flow does not apply. Reshaped: a `variant="session"` that shows the phase prompt and the group panel instead of the interview; the voice bar and "Talk to North" are kept |
| Stage bar | `wall/StageBar.tsx` (the `STAGES` and `NEXT` tables, lines 8 to 19, "Are you sure?" pattern) | Existing. Reshaped: `stages` and `next` become props, so the same bar draws Diverge, Group, Converge for the session. The "Are you sure?" dialog is reused |
| Invite panel | `wall/InvitePanel.tsx` | Existing. Used as is for late joiners and the link |
| Wall copy | `wall/copy.ts` (79 lines; `lanes`, `anonymous`, `needTwo`, `projector`, `live`, `people`, `failed`) | Existing. Used; new strings in a `brainstormCopy` block beside it (prompts, "Build on this", "Hide my name", "Group again", "Not grouped yet") |
| Projector mode (CSS and local toggle, counts only, no initials) | `WallScreen.tsx` line 102 and 156; `wall.css` `.ds-wall--projector` | Existing. Extended with the problem statement, phase, clock and group names (17, Screen C) |
| Poll every 3 seconds | `ui/src/modules/m1_intent/board/usePolled.ts` (`POLL_MS = 3000`) and `getBoardCounts` | Existing. Used for the lane and groups poll (17 refresh rule) |
| Stage clock | `ui/src/modules/m1_intent/timer/StageTimer.tsx` (server time every 15 s, local tick 1 s) | Existing. Used as is for the session clock |
| North grouping with names, keyword fallback, `min_notes`, colours | `modules/m1_intent/api/board.py` `group` (lines 182 to 224); `modules/m1_intent/domain/board.py` `apply_grouping` (110), `keyword_groups` (288), `by_kind` (225), `move_note` (243), `rename` (255) | Existing. Reshaped, three changes: (a) `group` requires stage `board` and the organiser only, so the brainstorm calls it from the intent's `session.phase`; (b) it refuses a second pass ("North has already grouped these notes"), which blocks "Group again", so a brainstorm may regroup without restore; (c) the move and rename routes are organiser-only today and open to participants in the group phase |
| Board store with edits `{by, kind}` | `modules/m1_intent/store/board.py` `edit` (lines 74 to 78) | Existing. Used; keyed by intent id |
| Card write, anonymous key, profile filter | `modules/m1_intent/store/notes.py`, `sh_platform/profile/view.py` `_cards` | Existing. Used as in 24 |
| Voice controls | `ui/src/modules/m1_intent/voice/VoiceControls.tsx` | Existing. Used on the idea box |
| Replies under a card (build on this) | Searched `graft find "reply"` and `"replies"` in `modules/m1_intent` and `sh_platform/profile`: nothing | New: the `replies[]` field and `POST .../replies` |
| Session bar controls Pause, Resume, Add time | `modules/m1_intent/domain/states.py` `move` (line 34) handles stage moves; no pause | New: `session.pauses[]` and the routes |
| Swipe on lanes | None (17 says swipe is new). A one-lane screen needs none | Not used |

### The configuration: exactly what differs from the wall

The brainstorm is `<WallScreen>` with a mode. One new prop and one table; nothing is copied.

| Wall setting today | Brainstorm setting |
|---|---|
| `LANES` four values (`WallScreen.tsx` line 18) | `LANES = ["idea"]`, one lane; the phone lane tabs (line 158) are not drawn |
| Lane heading from `t.lanes[l]` | Heading replaced by the problem statement (`showHead={false}` on `Lane`) |
| `Card`: `quarters` 0 to 4, `Edge`, `sealed`, `suggestionFrom`, `draft` | `quarters: null` (no edge), `sealed: false`, no suggestion cards, `replyCount` and `groupName` added |
| Title and sentence from `t.title`, `t.sentence` | The problem statement and North's prompt (`brainstormCopy`) |
| `StageBar` with the seven v1 stages | `StageBar` with `stages = [Diverge, Group, Converge]` and the session buttons, plus Pause, Resume |
| `NorthPanel` interview of four questions | `NorthPanel variant="session"`: prompt, groups, nudges; no quarter bars, no "Put it on the wall" |
| Card form: four quarters, lane chooser, seal | One idea field (q1), optional "Why it would work" (q2), "Hide my name"; no lane chooser, no seal, no "North, fill this" (24, Screen D) |
| "Show only mine" chip | Kept (the person sees their own ideas) |
| Projector: counts per lane only | Projector: count in diverge, group names and counts in group; plus problem statement, phase, clock, join box (17) |
| `data.live` shows North only while `private_rooms` is open | North panel shows while the session is open and not closed |
| Board served only after the rooms close (409 before) | Board served from the moment the session opens; cards are visible to everyone in the session as they land (no private room first, because Think alone is stage 1 of the intent, 02) |

## Not in this feature

- Choosing the idea, voting and the converge phase (37).
- The Think alone stage of a Brainstorm, where each person adds ideas privately before the session (the private room of the wall; a separate file for the brainstorm intent's first stage).
- The closure and sign-off of the intent (09), the rating (10), share link (11).
- The four-quarter card, seal, lanes and Define (24, wall file, Define file).
- Votes on cards in the Initiative wall.
- A second live session inside one Brainstorm.
- Video or audio calling. The session is a screen the room looks at together or on phones.

## Open questions

1. How long is each phase? The catalogue gives the live session a day but no minutes (02, Open question 4), and the existing presets (5, 10, 20, 30 minutes) are too short for six or seven people. Proposed, not decided: North drafts 15 minutes for diverge, 10 for group, 15 for converge and Janet edits. Confirm or set another default.
2. How often does North regroup while ideas land, and how long may a group name be? Proposed, not decided: after each batch, at most once every 30 seconds, names up to six words. The existing threshold `min_notes` (`domain/board.py` line 61) applies; its value for a brainstorm is not set here. Confirm.
3. Should North's "quiet seat" nudge exist at all? It gives only a count. Confirm, and say when.
4. May the projector show idea text in the group phase (no names, anonymous stays anonymous)? 17 says lanes show counts only. Without text the room cannot read the groups together.
5. Should anyone be able to press "Group again", or only Janet? Proposed: Janet only, because it moves many cards.
6. If the room runs dry, may the organiser go back from group to diverge? Proposed: no; start a second Brainstorm linked to the first (01, `links`).
7. Can a person undo "Hide my name" on their own idea? Same answer as 24, Open question 1 (no, because the name is dropped from the record).
8. Do replies need their own withdrawal rule? Proposed: the same as an idea (author only, until the session closes).
9. Does the organiser's own idea count as one of the 4 to 8, and can the organiser add ideas? Proposed: yes, the organiser may add ideas as a participant would, and the organiser's anonymous cards are as hidden as anyone's.
10. Where do people who join late see ideas added earlier? Proposed: the full lane at once, in the order they were added.
11. Screen B has no route of its own (`?card=<card_id>` on the session route), because the brief's route list has no card view. Confirm, or add a view.
12. 35 offers anonymous ideas as an organiser choice at open, default off. The first draft of this file allowed a per-card choice always. Aligned to 35; confirm that a fixed-anonymous session is not needed.
13. 35 (Open question 4) asks whether the lane shows ideas in random order. This file shows newest first. Confirm or switch to random.
14. Person-level counts in a room of four to eight people will often be under five, so they show "Fewer than five". Confirm that is acceptable for the first-five-minutes measure (10, 19).
