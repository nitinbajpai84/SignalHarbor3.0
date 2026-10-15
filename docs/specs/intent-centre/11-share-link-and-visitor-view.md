# 11. Share link and visitor view

Part of: Intent Centre v2. Depends on: the intent record (00-BRIEF section 3), the wall and seal rules (v1 spec, D-013), the Pulse page. Feeds: the closure screen (what a visitor reads when an intent is closed), the organiser's Pulse (notes and opens).

## Purpose (three sentences)

The organiser shares an intent with people who were not in it, so they can see what was done, what was discussed, who said what (unless anonymous) and what came out. The share is explicit, per intent, read-only, time limited and can be withdrawn at any moment. It reuses the approver-by-link mechanism (hashed token, expiry, revoke, failure lock, header-only travel) and adds no second one.

## Who uses it and when (role, moment, trigger)

| Role | Moment | Trigger |
|---|---|---|
| Organiser (Janet) | Intent is open, in session, closing or closed; she wants someone outside it to see it | Button "Share" on the intent page |
| Visitor, named (Harvey, owner, named in the share or tagged to the shared area) | A Pulse line says an intent was shared with him | He opens the line |
| Visitor, by link (any signed-in person of the company) | The organiser sent him the link herself, in her own message | He opens the address; if not signed in he signs in first, then lands on the page |
| Organiser | Wants to know whether it was read and whether anyone replied | Share log on the Share panel; Pulse line "a note on your intent" |

A person from outside the company (no account) cannot open a share. The approver link serves that case for a charter only; this feature does not widen it (Open questions).

## Entry points (every route, link, Pulse line, button that leads here)

- Intent page, header button **Share** (organiser only). Opens the Share panel, route `/centre/intent/<id>/share`.
- Intent list row menu, item **Share** (organiser only). Same panel.
- Closure screen, button **Share this outcome** (organiser only). Same panel, with the closure already attached.
- Visitor, named: Pulse line (kind `shared`) at `/centre/shared/<id>`; the Centre list "Shared with me" at `/centre/shared`. These visitor page routes are outside the 00-BRIEF section 8 convention (Open questions 11).
- Visitor, by link: the address `/centre/shared/t/<token>` (same open question). The token is read from the address by the page and sent only in the `X-Session-Token` header with the visitor's own session to `POST /api/modules/m1_intent/shared/view`; no API route takes it in a URL, query or body (same rule as `/approve/<token>`).
- Organiser: Pulse line on a new note, at `/centre/intent/<id>/share#notes`.

## Screens, element by element

### Screen A. Share panel

Route `/centre/intent/<id>/share`. Visible to the organiser only; everyone else gets "Not available", with no hint that the intent exists beyond what the visibility rule already gives them.

Layout at 1280: three regions. Left (7 columns): "Share with" (people picker, area picker, link maker) and the Expiry field. Right (5 columns): "Shared now" list and "Who opened it" log. Bottom strip: notes from visitors. At 390: one column, in that order; the log collapses to a count line that opens on tap; the picker becomes a full-screen sheet.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Panel title | panel | "Share: <intent title>", state chip (open, in session, closing, closed) | None | Organiser | Not applicable |
| Draft and cancelled guard | agent line (North) | "This intent is a draft. Open it before you share it." or "This intent was cancelled. A share shows the reason." | None | Organiser | Hidden when state is open, in_session, closing or closed |
| People picker | field (search list) | Company people: name, role, department. Already-shared people are ticked and greyed. Participants and observers show "Already in this intent" and cannot be picked. Affected people can be picked: naming one on a share is what opens content to them (00-BRIEF section 10, ruling 4); if the switch "affected people may read" is on, they show "Already in this intent" | Tick adds to the pending list | Organiser | "No one else to pick. Everyone in the company is already in this intent or already shared." |
| Area picker | field (multi-select of areas) | Areas of the company (departments and ops areas) with the head count of people tagged | Tick adds the area to the pending list | Organiser | "No areas set up yet. Ask your company admin to set them up." |
| Link maker | button **Make a link for anyone signed in to the company** | A line saying who can open it: "Any signed-in person of <company>. They sign in first." | Adds a pending "link" row | Organiser | Not applicable |
| Pending list | list | Rows of what will be shared, each with a remove cross | Cross removes the row | Organiser | "Nothing chosen yet." Button Share stays off |
| Expiry | field (date) | A required date, shown and counted in the company's time zone from the profile, else UTC. Earliest and latest allowed dates are not decided (Open questions 2) | Change sets `expires_at` for every row in this batch | Organiser | Empty blocks the Share button with "Choose when this share ends." |
| What a visitor sees | panel (read-only preview) | The list from Screen B, with the state-specific lines and the "never shown" list | None | Organiser | Not applicable |
| Button **Share** | button | "Share" | Writes the rows (see States). For people and areas, sends Pulse lines. For a link, shows the address once with button **Copy link** | Organiser | Disabled until a row and an expiry exist |
| Link result | panel | The full address, shown once, built with `public_link.full_url`; "We keep only a fingerprint. If you lose it, make a new one." | **Copy link** copies; **Done** closes the panel | Organiser | Not applicable |
| Shared now | list | One row per share: kind (person, area, link), who or which area, made by, made on, ends on, state (live, ended, withdrawn), opens | Row button **Withdraw** | Organiser | "Nothing is shared." |
| Button **Withdraw** | button | Row action, with a confirm line "Withdraw this share? People who have it will see 'This share has ended'." | Sets row state to `revoked` and writes the log line | Organiser | Hidden on rows already ended |
| Button **Withdraw all** | button | Same, for every live row | As above, in one write | Organiser | Hidden when no live row |
| Counts strip | list of numbers | "Shared with N people, M areas, K links", "Opened by X of them", "Notes: Y". Counts are exact | None | Organiser | "Not available yet: nothing has been shared." |
| Who opened it | list | Person name, first opened, last opened, times opened, through (named, area or link) | None | Organiser | "No one has opened it yet." |
| Notes | list | Visitor name, time (company time zone, else UTC), note text, button **Mark read** | **Mark read** sets `read_at` and `read_by` | Organiser | "No notes yet." |

### Screen B. Visitor view

Routes `/centre/shared/<id>` (named and area) and `/centre/shared/t/<token>` (link). Guest-style frame: the company header and theme choice, no module menu, a banner at the top: "Shared with you by <organiser>. Read only. <organiser> can see that you opened it. This share ends <date>."

Layout at 1280: a header block, then a main column (8 columns) with the content and a right column (4 columns) with "People" and "A note to <organiser>". At 390: single column; "People" collapses to a count that opens; the note box sits at the end.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Share banner | panel | Organiser name, read-only line, the opened-and-logged line, end date | None | Visitor | Not applicable |
| Title and purpose | panel | `title`, `purpose`, type, areas | None | Visitor | Not applicable |
| Stage strip | chip row | Stage chips from `stages`, current one marked, opened and closed dates | None | Visitor | "Not available yet: stages are not recorded." |
| People | list | Organiser and every named slot of `people` (sponsor, decider, owner, reporter where the type has them), participants, observers, affected, by name and role | None | Visitor | "Not available yet: no people are recorded." |
| Wall or session, read only | panel | Initiative, brainstorm: the wall by lane (cards with author name only where the author chose it, otherwise "Anonymous"). Weekly check-in: the week items (ran, broke, thought) with their fates and reasons. Problem: the statement, root cause and fix. Decision: the options table. Cards cannot be opened for edit; no seal, no vote, no add | None | Visitor | "Nothing was put on the wall." |
| Sealed line | panel | "N sealed cards are not shown." Count only, no topic, no lane | None | Visitor | Hidden when N is zero |
| Restricted measures line | panel | "N measures are restricted and are not shown." | None | Visitor | Hidden when N is zero |
| Closure block (closed only) | panel | `closure.summary`, `why_it_happened`, `what_came_out`, and `next` rows with kind and reason | None | Visitor | For open states: "Not closed yet. The outcome will appear here when it closes." |
| Cancelled block | panel | "Cancelled by <name> on <date>. Reason: <text>" | None | Visitor | Not applicable |
| Charter or outcome link | list | For an initiative with a charter: the signed charter rendered by `CharterPaper`, read only | None | Visitor | Hidden when none |
| Note box | field (text, length limit per Open questions 12) | Label "A note to <organiser>". Help: "This goes to <organiser>'s record. It does not go into the session." | Typing enables **Send note** | Visitor | Empty and button off |
| Button **Send note** | button | "Send note" | Writes the note (see Records). Box clears; line "Sent to <organiser>." | Visitor | Disabled when the box is empty or the share has ended |
| Ended panel | panel | "This share has ended." for expired, withdrawn or replaced shares; "This link is not working. Please ask for a new one." for any link that does not match | None | Visitor | Not applicable |

## User journey (numbered steps from arriving to leaving, with what the agent does between the person's steps)

1. Janet opens the intent "Quarterly valuation review" (closed) and presses **Share**.
2. North checks the state. A draft or a cancelled intent shows its guard line (draft cannot be shared).
3. Janet ticks Harvey in the people picker and the area "Operations" in the area picker, chooses an expiry date, and reads the preview of what visitors see.
4. Janet presses **Share**. The system writes two share rows and sends a Pulse line to Harvey and to everyone tagged to Operations. Nira writes the lines; nobody is emailed.
5. Janet also presses **Make a link**, shares the address with Aaron in her own message, and presses **Copy link**. The address is shown once.
6. Harvey opens his Pulse line, which loads `/centre/shared/<id>` and calls `POST /api/modules/m1_intent/shared/view`. The system checks the share row, his account and the date, writes one log line, and renders Screen B through his own viewer rights (`view.py`), so he sees only what he may see.
7. Harvey reads the closure and the wall. He types a note: "Which fund did the second valuation use?" and presses **Send note**.
8. Nira writes a Pulse line for Janet: "Harvey left a note on Quarterly valuation review". Janet opens the Share panel, reads the note, and presses **Mark read**. She answers in her own way; the note is not a chat and North does not answer it.
9. A week later Janet sees "Opened by 3 of 4" in the counts strip, and presses **Withdraw** on Aaron's link. Aaron's next open shows "This share has ended."
10. On the expiry date every remaining row ends by itself. The log and notes stay in the record.

## States and transitions (table: state, who moves it, to what, what is written)

Share row states:

| State | Who moves it | To what | What is written |
|---|---|---|---|
| (none) | Organiser, button Share | `live` | A row in `share.entries` with kind, target, `created_by`, `created_at`, `expires_at`; for a link the SHA-256 hash only |
| `live` | Organiser, **Withdraw** | `revoked` | `state`, `revoked_by`, `revoked_at` on the row |
| `live` | The clock, at `expires_at` | `expired` | Computed on read; no write needed (as `_approver_ground` does) |
| `live` | Organiser, **Withdraw all** | `revoked` for each | As above, one write |
| `live` | Intent goes to `cancelled` | stays `live` | Nothing. The visitor sees the Cancelled block with the reason |
| `live` | Organiser re-shares the same target | previous row `revoked`, new row `live` | A new row; old one marked `replaced_by`. One live row per person, area or link maker batch (as `send` closes earlier links) |

Intent state seen by the visitor:

| Intent state | Visitor sees |
|---|---|
| draft | Nothing. Share is refused; a stale share opened after a reversal shows "This link is not working." |
| open, in_session, closing | Title, purpose, stage, people, the wall or session read only, banner "Not closed yet" |
| closed | The above plus the closure block and the outcome |
| cancelled | Title, purpose, people, the Cancelled block with the reason |

## Records read and written (file or route, fields; mark Existing or New)

| Item | Kind | Detail |
|---|---|---|
| `intents/<id>/intent.json`, field `share` | New fields on a New record (the record itself is defined in 01; this feature adds fields only) | `entries`, `log`, `notes` (see "Fields this feature adds") |
| `sh_platform/jsonfile.py` read and atomic write with `lock_for` | Existing | The only writer of the intent file |
| `sh_platform/profile/view.py` `read`, `allows`, `sees_area`, `sees_rule`, `Viewer` | Existing | Every visitor read is filtered by the visitor's own `Viewer`, never the organiser's |
| `m1_intent` session, room and notes files | Existing | Read only, by reference from the intent record; the wall comes from here |
| `modules/m1_intent/store/charter.py` `digest`, `_match`, link record shape, `send`, `revoke`, `_approver_ground` | Existing, reshaped | Moved to a shared function that both the charter and the intent share call (see Reuse check) |
| `sh_platform/public_link.py` `full_url` | Existing | Builds the address in the Link result |
| `sh_platform/auth/sessions.py` `LoginThrottle` | Existing | The failure lock on the link read route |
| `_control/` link index (as `JoinIndex.company_of`) | New file `_control/share_index.json` | Maps a token's intent id to its company, so the route can find the plane before it reads anything; holds no hash and no name |
| `GET /api/intents/people` | New route | Company people for the picker: name, role, department; organiser only |
| `GET /api/intents/areas` | New route | Areas with head counts; organiser only |
| `POST /api/intents/<id>/share` | New route | Create rows; organiser only |
| `POST /api/intents/<id>/share/withdraw` | New route | One row or all; organiser only |
| `GET /api/intents/<id>/share` | New route | Rows, counts, log, notes; organiser only |
| `POST /api/modules/m1_intent/shared/view` | New route (path settled by 00-BRIEF section 10, ruling 1) | Visitor view; id in the body for named shares, token in `X-Session-Token` for links. Guest routes may only live under `/api/modules/<module>/`; this one still needs sign-in |
| `POST /api/modules/m1_intent/shared/note` | New route (path proposed, Open questions 11) | Visitor note; same ground check; body size counted as it arrives, as `_decision_body` does (limit not decided, Open questions 12) |
| `POST /api/intents/<id>/share/notes/<nid>/read` | New route | Mark a note read; organiser only |
| `sh_platform/route_permissions.yaml` | Existing, edited | Each route above declared (default deny). The two visitor routes need sign-in, so they are not `entry` routes: roles are every signed-in role of the company |
| `sh_platform/pulse/lines.py` `line`, `MINUTES` | Existing, edited | New kinds `shared` and `share_note` |

## Fields this feature adds to the intent record

Inside `share` (the brief's `link` and `who_may_open` stay; `link` holds the id of the live link row or null, and `who_may_open` is rebuilt from live person and area rows):

```
share: {
  link, who_may_open,
  entries: [{id, kind: person|area|link, target (person id | area tag | null),
             created_by, created_at, expires_at,
             state: live|revoked, revoked_by|null, revoked_at|null, replaced_by|null,
             hash (link rows only), version_seen (closed_at of the closure at share time | null)}],
  log:     [{entry_id, account_id, at}],                       # one line per open
  notes:   [{id, entry_id, by (account id), at, text, read_at|null, read_by|null}]
}
```

A log line is written at most once per account per de-duplication window, so a page refresh does not inflate the counts. The window is not decided (Open questions 6).

## Agent behaviour (North, Lens, Nira: what each drafts, when, and the moment a person acts)

- **North** drafts the guard lines on the Share panel (draft, cancelled) and, at closure, asks the organiser once: "Share this outcome with the areas you tagged?" with a ready pending list of the intent's `areas`. The organiser presses **Share** or does nothing. North never shares by itself. North does not read or answer visitor notes.
- **Lens** does nothing in this feature. It never reads a note, a log line, or the visitor view.
- **Nira** writes the Pulse lines: to each named person and each person tagged to a shared area, kind `shared` ("Janet shared <title> with you", action "Open"); to the organiser, kind `share_note` ("<name> left a note on <title>", action "Read the note"). A line is made from the share row and note record, never from the content of the intent.
- The person who acts: the organiser shares, withdraws and marks read; the visitor opens and writes a note. No agent signs, shares or replies.

## Rules (visibility, time box, who may do what)

1. **Who shares.** Only the organiser of the intent. The sponsor, company admin and super admin cannot share an intent they did not organise (Open questions for the sponsor).
2. **Who may open.** A named person (an affected person named on a share reads content, per ruling 4; an observer already reads what a participant reads); a person tagged to a shared area; any signed-in person of the same company when holding a live link. A person of another company never opens it: the company is resolved from the signed-in session and the intent's own plane, and a mismatch fails closed with the same plain answer as a bad link.
3. **Read only.** No route in this feature changes the wall, the session, the charter or the closure. The only write a visitor makes is a note and a log line.
4. **What a visitor never sees.**
   - Sealed cards: a count only, no topic, lane or author. This is stricter than the v1 wall silhouette, which names the topic.
   - Anonymous authors: shown as "Anonymous". The author id, `anon-*` ids and the order of anonymous cards in time are not sent to the browser at all, so a network read cannot reveal them. The company admin rule (never anonymous notes) holds here too.
   - Restricted measures and sources the visitor may not see: dropped by `view.py` for the visitor's `Viewer`; the visitor sees a count line only.
   - Other intents, links to them (`links.to` shows titles only for intents the visitor is already allowed to see), the share log, other visitors' notes, ratings by name, the hash, entry ids and the organiser's other shares.
5. **A named share does not widen rights.** A visitor who is not in the intent sees what the share allows; seeing an intent through a share never makes someone a participant or affected person.
6. **Expiry is required.** A share row has an end date. No share lasts for ever. The allowed range is not decided (Open questions 2).
7. **Withdraw is immediate.** The next read after the write fails with "This share has ended." Pages already open show it on their next request.
8. **Link safety (as the approver link).** The token is "sh-<intent id>-<secret>" (secret length as the approver token's, taken from the shared function); only its SHA-256 hash is stored; it is compared in constant time against every row; it travels in the header only; failures before the hash matches give one answer and count against the caller's address; repeated failures lock that address for a wait through `LoginThrottle`, with the threshold and wait it already has; the token is never logged, raised or shown again.
9. **Notes.** Plain text, length limit not decided (Open questions 12), named by the visitor's account, written to the record, never into the session, never read into an agent draft as an instruction. The visitor cannot edit or delete a note.
10. **The visitor is told.** The banner says the organiser can see that the visitor opened it.
11. **Time box.** The share never extends the intent's time box and nothing a visitor writes reopens a closed intent.
12. **Past intents are kept.** Shares and logs remain after expiry; nothing is deleted.

## Counters and measures of this feature (numbers only, each traced to a record)

| Number | Where shown | Traced to |
|---|---|---|
| Shares made (people, areas, links) | Share panel counts strip | Rows in `share.entries` by `kind` |
| Live shares | Counts strip | Rows in state `live` whose `expires_at` is in the future |
| Visitors who opened | Counts strip: "Opened by X of N" | Distinct `account_id` in `share.log` against the people the share names or the area head count at share time |
| Times opened | Who opened it | Lines in `share.log` per account |
| Notes, unread notes | Counts strip, Pulse | Rows in `share.notes`, where `read_at` is null |
| Withdrawn shares | Shared now | Rows in state `revoked` |

Where the area head count at share time is not recorded, the screen says "Not available yet: the area head count was not recorded." The organiser's counts never appear on the visitor view. No counter is shown for a comparison across intents.

## Reuse check (what exists today: file paths and line ranges found with graft; copied, reshaped or not used, and why)

Searches run: read of `sh_platform/public_link.py` (1-24), `modules/m1_intent/api/approver.py` (1-147), `modules/m1_intent/store/charter.py` (30-39, 196-262), `modules/m1_intent/store/room.py` JoinIndex (40-65), `ui/src/pages/ApproverPage.tsx` (1-110), `ui/src/pages/JoinPage.tsx` (1-15), `sh_platform/pulse/lines.py` (22, 56-78, 113-128), `sh_platform/profile/view.py` (27-120), `sh_platform/route_permissions.yaml` (91-92). A grep for a people picker component in `ui/src`, `modules` and `sh_platform` found none.

| Existing | Decision | Why |
|---|---|---|
| `sh_platform/public_link.py` `full_url` (1-24) | Copied unchanged, called | The one definition of an address that leaves the app |
| `charter.py` `digest`, `_match`, link record `{hash, issued_at, expires_at, state}`, `send` and `revoke` (30-39, 196-262) | Reshaped | The token shape, hashing, constant-time match, one-live-link rule, revoke and the `link_invalid` and `link_gone` split are right. They are lifted into one function that takes the record owner (a charter document or an intent record) so there is one link mechanism. The charter keeps its `ap-` prefix and approver-only rules; the intent share uses `sh-`. No second implementation |
| `approver.py` `_ground`, `_Refuse`, throttle, `_decision_body` (40-110) | Reshaped | Same defence order, same failure lock, same body counting. Changed: the visitor routes need sign-in, so they are normal routes and check the session first, then the token. The company is found through the new `share_index.json`, following `JoinIndex.company_of` |
| `JoinIndex` (`room.py` 40-65) | Copied as pattern | A control index with one lock per file; the new index maps token intent id to company only |
| `LoginThrottle` | Called | Failure lock |
| `ApproverPage.tsx` | Reshaped | Header (brand, theme control), `useLoad`, `ScreenState`, `linkProblem` mapping (429 gets its own sentence), the "token read from the address, sent only in a header" pattern, and the comment box with its help line become Screen B. The Approve and Decline buttons are not used |
| `CharterPaper` | Called | Renders the signed charter read only in Screen B |
| `JoinPage.tsx` with `GuestShell` | Reshaped | The guest frame is reused for the visitor page; the visitor is signed in, so the shell shows the company header and the person's name, not the module bar |
| `sh_platform/profile/view.py` | Called | Visitor reads go through `read` with the visitor's own `Viewer`; no new filter |
| `pulse/lines.py` `line`, `invited` | Reshaped | `shared` and `share_note` lines follow the `invited` pattern. `MINUTES` needs two entries, so that file is edited |
| `sh_platform/jsonfile.py` | Called | Storage |
| People picker, area picker, share panel, visitor view | New | Nothing equivalent found |

## Not in this feature

- Sharing with a person who has no company account (Open questions).
- Email, chat or any message sent from the centre; the organiser sends a link herself.
- Replying to a note inside the product, or a thread; a note is one way.
- Editing, commenting on, rating or voting in the shared intent from the visitor view.
- Downloading or printing the view as a file.
- Sharing a single card, a single charter or a single measure; the unit is the intent.
- Sharing to a mailing list or a public page.
- Changing the visibility rule in 00-BRIEF section 4.

## Open questions

1. **People outside the company.** Should an external person (an auditor, an investor) be able to read a share? It needs an account-less link like the approver's, and a stronger anonymity check. Not decided; this spec excludes it.
2. **Expiry limits.** What is the longest a share may run, and is there a default? The approver link takes its hours from the charter settings; no value exists for shares. Needs a settings entry and Nitin's number.
3. **Can the sponsor share?** The brief says the organiser. A sponsor of a closed initiative may want to. Proposed answer: no, until asked.
4. **Anonymity in small rooms.** In a brainstorm of five people, "Anonymous" plus a count of cards by lane may let a visitor guess the author. Should anonymous cards be hidden from link visitors when the intent had fewer than a set number of participants? The number is not decided.
5. **Anonymous notes.** Should a visitor be allowed to send a note without a name? D-013 says anonymous is real, but the log already names who opened the share. This spec says no.
6. **Log de-duplication window.** Proposal: about ten minutes per account. No value is decided.
7. **Ratings.** Should the visitor see the average rating of a closed intent? This spec shows none.
8. **Pulse expiry of a `shared` line.** The line goes when the visitor opens the intent. Should it also go after the expiry date or after seven days? Not decided.
9. **People list source.** The company people list for the picker appears to live in the company profile (`sh_platform/profile`), whose read route is company admin only. A read route for the organiser is needed; confirm whether the organiser may see the whole list or only their areas.
10. **Area head count.** Whether the number of people in an area is stored at share time, so that "Opened by X of N" stays true after people move.
11. **Visitor routes.** The pages `/centre/shared`, `/centre/shared/<id>` and `/centre/shared/t/<token>`, and the note route `POST /api/modules/m1_intent/shared/note`, are not named in 00-BRIEF section 10 ruling 1. Confirm them, or move the pages under `/centre/intent/<id>/<view>` (the view list would need a `shared` entry).
12. **Note limits.** Maximum note length (proposal 1000 characters) and request body size (proposal 16384 bytes, as the approver comment) are not decided.
13. **Link for anyone signed in.** 00-BRIEF section 4 says a share opens to "the people it names". A link any signed-in person of the company can open widens that. Keep it, or limit links to named people?
14. **Small shares.** Counts are exact (ruling 8). Whether "Opened by X of N" should show "Fewer than five" for a small share is not decided.
