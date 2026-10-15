# 16. Transcript and audit trail ("What happened")

Part of: Intent Centre v2. Depends on: 00-BRIEF, 01 (intent record and lifecycle), 06 (people and roles), 07 (time box and stage clock), 09 (closure and sign-off). Feeds: 04 (home counters), the share and rating files, the Build hand-off (the trail travels with the charter).

## Purpose (three sentences)

Every intent keeps a plain, append-only log of what was said and done, so a later visitor can see what kind of talk happened and who said what. Every intent screen has a read-only "What happened" tab that shows this log as a timeline, cut to what the viewer may see, and a closed intent can be downloaded as a transcript in Markdown and PDF. The log tells apart what an agent drafted and what a person did: a draft is logged as a draft, and only a person's confirmation, signature, close or rating is logged as the act.

## Who uses it and when (role, moment, trigger)

| Role | Moment | Trigger |
|---|---|---|
| Participant, affected person | During or after an intent, to check what was agreed and who proposed it | Opens the **What happened** tab |
| Organiser, sponsor | Before closing ("did we cover it?") and after closing (to share or download) | Opens the tab; presses **Download transcript** on a closed intent |
| Later visitor named by a share link | Months later, to learn how a decision was reached | Opens the share link, then the tab |
| Company admin | Checks that an intent ran as it should, without reading anyone's words | Opens the tab; sees milestones and counts only |
| Super admin | Nothing here | Sees no tab (event count appears nowhere either) |
| North | Writes `north_drafted` events when it drafts; reads the log to write the closure draft and its "why it happened" line | Each draft, each stage change, closure |
| Lens | Writes `lens_drafted` events when it drafts a definition | Each definition draft |

People act at named moments (they confirm, sign, close, rate, move a card). Agents draft; the log keeps that line visible.

## Entry points (every route, link, Pulse line, button that leads here)

- The **What happened** tab on every intent screen (the intent page of spec 01, every stage screen, the closing screen of spec 09, the closed view): `/centre/intent/<id>/events`.
- The same tab in a share link's read-only view: the share view of spec 14 (`/centre/intent/<id>/share`) with the tab at `/centre/intent/<id>/events`, entered through `POST /api/modules/m1_intent/shared/view` (see Open questions 10).
- Closing screen (spec 09): the line "Not sure it covers everything? See what happened" links to the tab.
- Closed view: the button **Download transcript** (organiser, sponsor, participants; share-link people who were named).
- Nira's "waiting for you" line for an organiser of a closed intent without a share: "Nothing was shared from this intent yet. See what happened" (link to the tab). Nira only lists it; the person decides.
- Intent home (spec 04), a closed card: the small line "42 things recorded" links to the tab (the counter in "Counters" below).

## Screens, element by element

### Screen 1: What happened (tab)

Route: `/centre/intent/<id>/events` (share view: same screen inside the share view of spec 14, read-only by nature). The tab is named "What happened"; `events` is only the route view name (ruling 1).

Layout at 1280: three regions under the intent header and its tab row. Left (280 px): filter panel. Centre (flexible, max 720 px): the timeline, grouped under day headings, newest day first, newest event first inside a day. Right (300 px): "What kind of talk happened" summary panel. At 390: one column. The filter panel collapses to one **Filter** button that opens a bottom sheet. The summary panel becomes a one-line strip above the timeline ("31 recorded: 12 cards, 9 votes, 5 answers, 5 other"), tap to expand. Timeline lines wrap; the kind chip moves above the sentence.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Tab label "What happened" | button (tab) | Label, and a small number: events the viewer may see | Opens the tab; keeps the filters from the last visit in this browser tab only | Content tier, share-link people, company admin (milestones only) | Number hidden when 0 |
| Kind filter | chip group | One chip per kind group (below), each with its count for this viewer; all on by default | Toggle a chip: timeline and summary refilter in the browser; no request | Content tier, share-link people | Chips with 0 are greyed and cannot be turned on |
| Person filter | list with search | "Everyone", then each named person who has at least one visible event, then "Anonymous (n)" | Pick one: only that person's events. "Anonymous (n)" shows the anonymous events as a group, never by person | Content tier, share-link people | "Everyone" only, with "No one has said or done anything yet." |
| Stage filter | chip group | The stages of this intent's type (spec 02), plus "Before the first stage" and "After closing" | Toggle: refilters | Content tier, share-link people | One chip, "Before the first stage" |
| Clear filters | button | "Clear filters" (shown only when a filter is on) | Resets all three filters | Same | Hidden |
| Timeline event line | list item | Time (hh:mm, day heading above), kind chip, who ("Aaron", "Anonymous", "North (draft)"), one sentence built from kind and the resolved record (for example "Aaron added a card to Processes: Month-end close takes six days") | Click: opens the record the event refers to, in place, read-only (card, definition, outcome, closure), if the viewer may open it. Otherwise the line is not a link | Same | "Nothing has happened in this intent yet." |
| Draft chip | chip | "Draft by North" or "Draft by Lens" on a line from an agent | None. Hover or focus names the person who later confirmed it, if anyone: "Confirmed by Janet, 14:02" (link to that event) | Same | Not shown |
| Confirmed link | link | On a person's confirm event: "Confirms the draft from 13:41" | Scrolls to and highlights the draft event | Same | Not shown |
| Hidden stub | list item | "An anonymous card was added" or "A sealed card was added" (kind and time only, no author, no text) | None | Same, for events the viewer may not read in full | Not shown |
| Day heading | heading | "Tuesday 6 October" with the count for that day | Click: collapse that day | Same | Not shown |
| Show more | button | "Show 50 more" (the timeline loads 100 lines, then 50 per press) | Loads the next page from the server | Same | Hidden when all are shown |
| Summary: by kind | panel | A bar row per kind group with a number; a line such as "Mostly cards and votes; 5 answers" is NOT written (no judgement without a rule, see Open questions) | Click a row: sets the kind filter to that group | Same | "Not available yet: nothing has been recorded." |
| Summary: by person | panel | Per named person: events they did (not drafts). Anonymous events as one row "Anonymous". Hidden entirely when the session mode is anonymous (see Rules) | Click a person: sets the person filter | Content tier, share-link people | Hidden |
| Summary: agent and people | panel | "Drafted by agents: 9. Done by people: 22" | None | Same | "Not available yet" |
| Download transcript | button | Visible only when state is `closed` or `cancelled` | Opens Screen 2 | Organiser, sponsor, participants, share-link people the organiser allowed | Hidden while the intent is open; tooltip on a disabled button: "Available when the intent is closed" |
| Read-only note | text | "This is a record. It cannot be changed." | None | Everyone who sees the tab | Always shown |

Kind groups used by the chips: Opened and closed (opened, closed, cancelled, state_changed), People (person_invited, joined), Stages (stage_opened, stage_closed, extended), Talk (question_answered, card_added, card_moved, vote_cast), Definitions (definition_confirmed), Agent drafts (north_drafted, lens_drafted), Sign-off (signed), Sharing and rating (shared, rated).

### Screen 2: Download transcript (dialog over Screen 1)

Route: none (a dialog). Layout at 1280: centred dialog, 480 px. At 390: full-width bottom sheet.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Preview line | text | "Transcript of: <title>, closed <date>. 42 events. Cut to what you may see." | None | As above | "Nothing was recorded." and both buttons disabled |
| Include agent drafts | checkbox (on) | Whether agent draft lines are in the file | Changes the preview count | Same | On |
| Download Markdown | button | `<company>-<intent>-transcript-<date>.md` | `GET /api/intents/{id}/transcript/download`; browser saves the file | Same | Disabled when nothing was recorded |
| Download PDF | button | The same file as printable HTML, sent to the browser's print dialog "Save as PDF" (same method as `ui/src/modules/m1_intent/summary/SummaryScreen.tsx`) | Opens the printable HTML in a new tab and calls print | Same | Disabled when nothing was recorded |
| Close | button | "Close" | Closes the dialog | Same | n/a |

## User journey (numbered steps from arriving to leaving, with what the agent does between the person's steps)

1. Aaron, a participant, opens an intent and presses **What happened**. The server reads `events.jsonl`, cuts it to his tier (see Rules), and returns the first 100 lines with counts.
2. He sees today's lines. Between his steps, North and the screens keep appending events; the tab shows a "3 new events" bar every 30 seconds while open (a poll, not a push), and he presses it to load them.
3. He turns off every chip except Talk and picks Janet in the person filter. He reads what she said and which cards she moved.
4. He clicks a `definition_confirmed` line. A read-only panel opens with the definition as it stands today and a link "Version history" to the version trail (versions.json, below).
5. He clicks a Draft chip on a North line ("North drafted the closure summary"). The hover says "Confirmed by Janet, 14:02" and he follows it to Janet's `closed` event.
6. Months later, a person named by a share link opens the share link and then the **What happened** tab. The same screen shows, with no Download button unless the organiser allowed it.
7. After closing, Janet presses **Download transcript**, leaves "Include agent drafts" on, and presses **Download PDF**. The browser opens the printable page; she saves it as PDF and attaches it to the Build hand-off.

## States and transitions (table: state, who moves it, to what, what is written)

The log has no state of its own; it follows the intent's state (spec 01). What each intent state means for the log:

| Intent state | Who moves it | Effect on the log | What is written |
|---|---|---|---|
| (none) to `draft` | Creator | File is created with the first line. A draft intent and its log are visible only to the person who started it (ruling 14) | `opened` event (by the creator, ref `intents/<id>/intent.json`) |
| `draft` to `open` | Organiser | Appending continues | `state_changed` (from draft, to open); `stage_opened` for the first stage |
| `open` to `in_session` and back | Organiser, or North at session end | Appending continues | `state_changed` each way |
| `open` or `in_session` to `closing` | North or organiser | Appending continues | `state_changed`; `north_drafted` (closure draft) |
| `closing` to `closed` | Organiser, after: sponsor (Initiative), decider (Decision), owner then reporter (Problem), none (Brainstorm, Weekly check-in) | Appending of work events stops. Only `rated` and `shared` may still be appended | `signed`, then `closed`, then `stage_closed` for each stage still open |
| any to `cancelled` | Organiser or sponsor, or company admin for a stuck intent | Same as closed | `cancelled` with the reason from `closure.cancel_reason` |
| Any of the above | Server | Each line gets the next `seq` (1, 2, 3, ...) | One line per act |

A Weekly check-in (record key `pulse`) keeps one log for the whole series; each week's events carry the week key in `detail.week` and the stage filter lists weeks for that type (ruling 3). A cancelled intent keeps its reason and its log, shown in Past (ruling 14).

A line is never edited, reordered or removed. A correction is a new line that points at the old one (`corrects: <seq>`), for example a card moved by mistake and moved back.

## Records read and written (file or route, fields; mark Existing or New)

| Record | Where | Fields | Status |
|---|---|---|---|
| Event log | `intents/<id>/events.jsonl` in the company plane (`plane.path("intents", id, "events.jsonl")`) | One JSON object per line, see the event shape below | **New** |
| Intent record | `intents/<id>/intent.json` (spec 01; the folder `intents/<id>/` holds the record and `events.jsonl`, ruling 12) | Read for the people, areas, state, refs and share. One pointer field added (below) | Existing (spec 01), field New |
| `history` in the intent record | spec 01 | The state trail. Kept as is; each entry also produces a `state_changed` event. The log is the full trail, `history` is the quick state list | Existing (spec 01) |
| Wall notes, cards, votes, comments | `modules/m1_intent/store/notes.py`, `store/sessions.py`, board store | Read only, to resolve the text of a line for this viewer. Never copied into the log | Existing |
| Version trail | `<plane>/graph/versions.json` via `sh_platform/graph/versions.py` `append_version` | A `definition_confirmed` or measure change event carries `ref: {store: "graph_versions", node, v}`; the screen links to it. No second copy of the change | Existing |
| Charter and charter export | `modules/m1_intent/api/charter.py` L296-L352, `domain/charter_export.py` | Read for the download pattern and helpers | Existing |
| Profile view | `sh_platform/profile/view.py` `Viewer`, `allows`, `sees_rule` | Read, to decide whether a viewer may see a restricted measure's event | Existing |
| Download route | `GET /api/intents/{id}/transcript/download` | Returns `{files: [{format, filename, mime, content}]}` like the charter route | **New** |
| Timeline route | `GET /api/intents/{id}/events?after=<seq>&kind=&by=&stage=&limit=` | The cut page, counts, and `next` | **New** |
| Share timeline route | `GET /api/modules/m1_intent/shared/events?after=<seq>&kind=&by=&stage=&limit=` | Same cut as a share-link viewer (guest routes may only live under `/api/modules/<module>/`, ruling 1; the token is sent as `shared/view` does) | **New** |

### Choice: a separate JSONL file, not an events list inside the record

Chosen: `intents/<id>/events.jsonl`, one line per event, appended.

Why, in order:
1. **Volume and write rate.** A live wall produces dozens of cards and votes a minute. The record is rewritten whole by `write_json_atomic` and guarded by `version` (spec 01 answers 409 on a stale version). An events list inside it would make every card move a record write, and two people voting at once would collide with each other and with the organiser.
2. **Append is cheap and safe.** One line appended under `lock_for(path)` never rewrites old lines. A crash can leave one torn last line; the reader skips an unreadable last line and never rewrites the file. A whole-file JSON rewrite risks losing everything on a crash.
3. **The record stays small and fast to list.** The home page (spec 04) reads many records; it must not read every vote of every intent.
4. **Closed means read-only (spec 01) but ratings and shares still arrive.** A separate file can accept those two kinds after close without reopening the record's write path.
5. **Anonymous rule.** The log is its own file with its own cut function, so the "no account id anywhere in the file" rule for anonymous lines is checkable in one place.

Cost: two files to keep in step. The act's own record is written first, then the event. If the event write fails, the act stands, the server logs "event not recorded" with the act's id, and the next read shows a gap notice to the organiser only ("1 act has no line in the log"; see Open questions 2).

### The event shape

```
{ "seq": 17,
  "at": "2026-10-06T09:14:03Z",
  "kind": "card_added",
  "status": "act",                       // "act" or "draft"
  "by": {"account": "<id>", "name": "Aaron", "role": "participant"}   // or null
  "anonymous": false,                    // true: "by" is null and no account id is anywhere on the line
  "agent": null,                         // "north" | "lens" | "nira" on a draft; null on an act
  "stage": "wall",                       // the stage key that was open
  "ref": {"store": "m1_wall", "id": "card_8f2", "version": null},
  "detail": {"lane": "processes"},       // short facts only: keys, lane names, from/to, score. Never free text
  "confirms": null,                      // seq of the draft this act confirms
  "corrects": null,                      // seq of the line this one corrects
  "sealed": false }
```

Rules on the shape: `detail` holds only keys, enum values and numbers. Free text (card text, answers, comments, closure text, rating notes) stays in its own record and is read through `ref` at view time. This is what lets sealed, anonymous and restricted content be cut per viewer without rewriting the log, and keeps a person's words from living in two places.

## Fields this feature adds to the intent record

| Field | Type | Why | Written by |
|---|---|---|---|
| `events` | `{path: "intents/<id>/events.jsonl", count: int, last_seq: int, last_at: ISO 8601 UTC}` | Lets the home page show "42 things recorded" and a stage screen show "last change" without opening the log | Server, after each append (best effort; the log is the truth, the counters are rebuilt from it on mismatch) |

The `events` pointer changes on every append, so the server writes it with the same lock-free "counter only" approach as `SessionStore.count` (`modules/m1_intent/store/sessions.py` L127-L140): it does not bump `version` and does not move `updated_at`.

## Agent behaviour (North, Lens, Nira: what each drafts, when, and the moment a person acts)

- **North** drafts and logs `north_drafted` with `detail.draft_of` from this closed list: `question`, `next_step`, `nudge`, `stage_summary`, `closure`, `proposal` (extend, close with what we have, cancel). The line says "North drafted the closure summary". The line is `status: draft`, `agent: north`, `by: null`. North also writes `stage_opened` and `stage_closed` when the clock says so; these are server acts on a rule the organiser accepted at open (spec 07) and read "Stage opened (clock)" with `agent: north` in `detail.by_clock: true`. North writes no `signed`, `closed`, `cancelled`, `extended` or `rated` event, ever. If North proposes to extend, that is a `north_drafted` (`draft_of: proposal`); the person's press is the `extended` event with `confirms` pointing at it.
- **Lens** drafts and logs `lens_drafted` with `detail.draft_of` in `business_term`, `technical_term`, `catalogue_entry`, `process_map`, `data_source`, `governed_state`. The person's `definition_confirmed` carries `confirms: <seq>` and `ref` to the confirmed record and the `graph_versions` row. A definition that is never confirmed keeps showing as a draft with no "Confirmed" link.
- **Nira** writes no event. It reads the counters only for the Pulse line named in Entry points.
- The moment a person acts: they press Confirm, Sign, Close, Cancel, Extend, Share, Rate, drop or move a card, cast a vote, or type an answer. Each is one `act` line with that person's name (or anonymous where the rule allows).
- A draft never overwrites a human edit (CLAUDE.md rule 7): if a person edited an agent's draft and confirmed it, the log shows the draft line, then the confirm line, and `detail.edited: true` on the confirm. The record holds the edited text; the log never holds either text.
- Redrafts: a second North draft of the same thing is a new line; the earlier draft stays and is shown as superseded in the transcript (`corrects`).

### Event kinds

Each row: who, the record it changed, and the short facts in `detail`.

| Kind | Status | Who | At | Reference to the record it changed | Detail |
|---|---|---|---|---|---|
| `opened` | act | The creator (becomes organiser) | Server time at create | `intents/<id>/intent.json` | `type` |
| `person_invited` | act | The organiser (or sponsor) | At invite | `people` entry in the record (key `participants` or `affected`) | `role`, `required` |
| `joined` | act | The person who joined (name, never anonymous) | At first join | `people` entry | `role`, `how` (account or guest link) |
| `question_answered` | act | The person who answered (anonymous only where the session mode allows) | At submit | The start-question answer in the record, or the Define-stage question store | `question_key` |
| `card_added` | act | The author, or anonymous | At submit | Wall note id in `modules/m1_intent` notes | `lane` |
| `card_moved` | act | The person who moved it | At drop | The card id | `from_lane`, `to_lane`, `corrects` if undone |
| `vote_cast` | act | The voter, or anonymous when the session mode is anonymous or choice-hidden | At cast | The cluster id | none |
| `definition_confirmed` | act | The person who confirmed (never an agent) | At confirm | Glossary or catalogue record id, plus `graph_versions` row | `kind` (business, technical, catalogue, process, source), `edited` |
| `stage_opened` | act | The organiser, or the clock (North, `by_clock`) | At open | The `stages[]` entry key in the record | `stage` |
| `stage_closed` | act | The organiser, or the clock | At close | The `stages[]` entry key | `stage`, `closed_by` (person or clock) |
| `extended` | act | The organiser or sponsor | At extend | `time_box.extended_by` entry | `old_end`, `new_end`; the reason is read from the record |
| `north_drafted` | draft | North | At draft | The record holding the draft (for example `closure`) | `draft_of` |
| `lens_drafted` | draft | Lens | At draft | The m2 record being drafted | `draft_of` |
| `signed` | act | The signing person | At sign | The charter version or closure signature | `what` (charter, closure) |
| `closed` | act | Organiser, after per-type confirmer acts (sponsor for Initiative, decider for Decision, owner and reporter for Problem; none for Brainstorm, Weekly check-in) | At close | `closure` in the record | `incomplete` (true when closed with what we have) |
| `cancelled` | act | Organiser or sponsor, or company admin for a stuck intent | At cancel | `closure` in the record | `cancel_reason` (from `closure.cancel_reason`) |
| `shared` | act | The organiser | At create or withdraw | `share` in the record | `action` (created, withdrawn), `people_count` |
| `rated` | act | The rater; anonymous by default (`by` null, ruling 15), and the person's own file keeps the link | At rate | The `ratings[]` row | `score` is in the row, not in the line |
| `state_changed` | act | Whoever moved it (person, or North `by_clock`) | At move | `history` entry | `from`, `to` |

`state_changed` is added beside the list in the task so that the log holds every move the `history` field holds; no other kinds are added.

## Rules (visibility, time box, who may do what)

**Who writes.** Only the server writes the log, through one function `append_event(plane, intent_id, event)` called by the routes that make the acts (not by the browser, never by a route of its own). There is no route to edit or delete a line. Default deny in `route_permissions.yaml` for the three read routes: roles are the coarse gate; the handler applies the tier.

**Append checks.** The function refuses a line when: `status` is `act` and `agent` is set; `status` is `draft` and `by` is set; the kind is `signed`, `closed`, `cancelled`, `extended`, `rated` or `definition_confirmed` and the actor is not a person; `detail` holds a string longer than 80 characters or a key not on the kind's list; the intent is closed or cancelled and the kind is not `rated` or `shared`. A refused line is a server error that is logged; the act's own route does not fail because of it (it writes the "event not recorded" warning instead).

**Who sees what (cut at read time, by the server, never in the browser).**

| Viewer | Tab | What the cut returns |
|---|---|---|
| Organiser, sponsor, participants, observers (content tier, spec 01). Affected people only when the organiser switched on "affected people may read" at creation, or when named on a share (ruling 4) | Full tab (observers read what a participant reads) | All lines except those hidden by the rules below |
| Share-link person | Read-only tab (same screen, no Download unless allowed) | Same cut as a participant, minus: decline and removal reasons (never in the log anyway), rating scores (counts only; ratings are anonymous by default, ruling 15), the `person_invited` lines for people who did not join |
| Area member, and affected person without read access (exists tier) | No tab. The intent screen says "The history is open to the people in this intent." | Nothing |
| Company admin | Tab shows "Milestones and counts only" | Only `opened`, `stage_opened`, `stage_closed`, `extended`, `signed`, `closed`, `cancelled`, `shared`, with the summary counts. Never `question_answered`, `card_added`, `card_moved`, `vote_cast`, never any anonymous or sealed line |
| Super admin | No tab, no count (existence only, ruling 5; the `events` counter is not in the existence view) | Nothing |

**What is hidden inside a visible tab.**
1. **Anonymous authors.** A line with `anonymous: true` has no `by`, no account id and no name in the file, so no cut can leak it. A note anonymous at the wall stays anonymous in the log for everyone, including the organiser and the company admin (D-013). Where the v1 session mode (`named`, `choice`, `anonymous`, as read in `modules/m1_intent/api/summary.py` `_contributions`) is `anonymous`, every `card_added`, `question_answered`, `vote_cast` and `card_moved` line of that session is written with `anonymous: true` at append time and the "by person" summary is not shown. In `choice` mode a line is anonymous only if its author chose so.
2. **Sealed content.** A line about a sealed card has `sealed: true`. A viewer the seal does not open sees the stub "A sealed card was added" with time and lane, no author, no text, and no link. Same cut as v1 seal (`modules/m1_intent/tests/test_m1_seal.py` pins it).
3. **Restricted measures and fields.** A `definition_confirmed` or `lens_drafted` line whose record is restricted in the profile (a measure or field rule that `sh_platform/profile/view.py` `sees_rule` or `sees_area` refuses this viewer) is dropped from the cut. It is not shown as a stub, because the profile rule is that nobody learns a hidden thing exists. Counts and summary panels are computed after this cut, so a hidden line never shows in a number.
4. **Text.** The sentence is built at read time from `kind`, `detail` and the record read through `ref` with the viewer's own cut. If the record was deleted or the viewer cannot open it, the sentence ends with "(content not available to you)".
5. **Small numbers.** Counts are exact. A per-person figure in the by-person panel with fewer than five records shows "Fewer than five" (ruling 8). No per-person average or rating exists anywhere (ruling 15). Whether the by-person panel stays on in a small session is Open question 3.

**Time box.** The log carries no clock of its own. Times are stored in UTC; the screen shows the company's time zone from the profile, else UTC, with the zone named in the footer (ruling 8). Events after `time_box.ends` are normal (an extension is itself a line).

**Retention.** Kept as long as the intent is kept (brief section 4: nothing is deleted). A cancelled intent keeps its log.

**Export rules.** Only for `closed` or `cancelled` intents (the charter download refuses an unsigned charter the same way, with a plain 409 "The transcript can be downloaded once the intent is closed."). The file is cut to the downloader's tier; two people may get different files. The file header says "Cut to what <name> may see." Draft lines are included by the checkbox. No download route exists for the company admin or the super admin.

**Transcript file layout (Markdown; the printable HTML follows the same order).**
```
# Transcript: <company>   (Illustrative, when the company name says so)
**Intent:** <title>   **Type:** <type>   **Closed:** <date>   **Cut to:** <viewer name>
## Summary            counts by kind group, by person (named only), drafts and acts
## What happened      one section per stage; under each, a bullet per event: hh:mm, who, sentence
## How it ended       the closure summary, why it happened, what came out, next steps (read from the record)
## Signed by          named signers and the time of each `signed` line
<the Illustrative line, as the charter has it>
```

## Counters and measures of this feature (numbers only, each traced to a record)

| Number | Where shown | Traced to |
|---|---|---|
| Events recorded in this intent | Tab label, home card line | `events.count` in the record, rebuilt from `events.jsonl` line count when they differ |
| Events visible to me | Tab label | Count of the cut returned by the timeline route |
| By kind group | Summary panel, filter chips | Count per `kind` in the cut |
| By named person | Summary panel | Count of `status: act` lines with `by.account` equal to that person, in the cut; "Fewer than five" below five lines |
| Anonymous | Summary panel | Count of lines with `anonymous: true`, in the cut |
| Drafted by agents / done by people | Summary panel | Count of `status: draft` / `status: act` lines in the cut |
| Gaps | Organiser only, one line | Acts in the record (cards, votes, extensions, signatures) minus matching `ref` ids in the log. Written only if it can be worked out; else "Not available yet: the record cannot be compared with the log." |
| Last change | Stage header | `events.last_at` |

Counters from the session store that already exist (`inputs`: actions, free text, cards confirmed, new and sealed, `SessionStore.count`) are not repeated; this tab shows events, those show typing effort.

## Reuse check (what exists today: file paths and line ranges found with graft; copied, reshaped or not used, and why)

| Found | Verdict |
|---|---|
| `modules/m1_intent/store/sessions.py` L26 `NO_INPUTS`, L127-L140 `count`: per-session counters of actions, free text, cards confirmed, new, sealed; numbers only, written without moving `updated_at` | **Reshaped** as the model for the `events` pointer (counter-only write that does not bump `version`). Not used as the log: counts say how much was done, not what, by whom or in what order |
| `modules/m1_intent/domain/timer.py` L13-L48 `is_timed`, `ends_at`, `window_minutes`, `status`; stage start and end times | **Used** (read only) to put `stage_opened`/`stage_closed` lines at the clock's own times and to say "by clock"; the log duplicates no timing rule. Timer stays the source for deadlines |
| `sh_platform/graph/versions.py` L40-L50 `append_version(plane, node_id, what, by, ref)`: append-only row with `v`, `what`, `by`, `at`, `ref`, under `lock_for` | **Reshaped**: same append-only, same lock, same row shape idea (what, by, at, ref) in a new file, because that file is per graph node and one JSON dict, which cannot hold a per-intent stream. **Used** for definitions: a `definition_confirmed` line points at the version row, so the change record is not stored twice |
| `sh_platform/jsonfile.py` L19 `lock_for`, L25 `read_json_strict`, L41 `write_json_atomic` | `lock_for` **used**. JSON-lines append is **new** (one small function beside it: open for append under the lock, write one line, flush); `write_json_atomic` does not fit an append-only stream |
| `modules/m1_intent/api/charter.py` L296-L352 (`_signed_view`, `download_charter` returning `{files: [...]}`), `domain/charter_export.py` L14-L111 (`md`, `one_line`, `to_markdown`, `to_html`, `safe_filename`) | **Reshaped** via graft into `sh_platform/intents/transcript_export.py`: copy `md`, `one_line`, `safe_filename`, the printable-HTML head and print CSS, the "Illustrative" tag and the "Signed by" block; new body (events by stage). The kernel cannot import a module, so it is a copy, not an import. Same file-list response shape |
| `ui/src/modules/m1_intent/summary/SummaryScreen.tsx` (`window.print`) | **Used** as the PDF method: no PDF library exists in the repo (searched `reportlab`, `weasyprint`, `fpdf`; none), so PDF is browser print of the printable HTML |
| `modules/m1_intent/api/summary.py` L55-L85 `_contributions` (modes `named`, `choice`, `anonymous`, counts per person) | **Reshaped**: the same mode rule decides whether a line is written anonymous; its per-person counts are the model for the summary panel. Not reused as is: it counts the final records, not the sequence |
| `modules/m1_intent/store/notes.py` L61-L70 `_authors`, `mark_anonymous` (authors apart from notes; one-way anonymous flag) | **Reshaped** as the rule (authors never beside anonymous text); the log keeps no account id on an anonymous line at all |
| `sh_platform/profile/view.py` L34-L99 (`Viewer`, `allows`, `sees_area`, `sees_rule`) | **Used** to cut `definition_confirmed` lines for restricted measures; hidden lines are dropped, not stubbed |
| `sh_platform/route_permissions.yaml` | **Used**; three routes added, default deny |
| Intent record `history` (spec 01) | **Kept**. The log does not replace it; each `history` entry produces a `state_changed` line |
| Searches run: graft for "event log", "audit trail", "transcript", "append" in `sh_platform/` and `modules/m1_intent`. No intent-level audit log exists. The agent run log in `sh_platform` records agent runs, not what people said | Genuinely new: `events.jsonl`, `append_event` and its checks, the cut function, the three routes, the tab, the transcript layout |

## Not in this feature

- Editing, hiding or deleting a line (nothing is deleted).
- Search across all intents' logs (home search is spec 04).
- Showing the text of a card or answer inside the log (it is read from its own record).
- Real-time push (the tab polls every 30 seconds).
- Analytics of "tone" or sentiment of the talk. Only counts by kind.
- Replay of a live session as video-like playback.
- Server-side PDF generation.
- Migrating old walls into logs (they have no events before this ships; the tab says "No history was kept before <date>").

## Open questions

1. **Company admin view.** The brief says the company admin sees existence and outcome, never anonymous notes. This spec gives them milestones and counts only. Should they see the full timeline of named events, as they see people lists?
2. **Write order and gaps.** The act is written first, the event second. A failure leaves an act without a line. Is a "gap" notice to the organiser acceptable, or must the act and the line be written together (record then events inside one lock, at a cost to speed)?
3. **Small sessions.** Ruling 8 shows "Fewer than five" for a per-person figure below five records. With fewer than five people in the session, should the by-person panel and the person filter also be off for the share link? Needs Nitin's ruling.
4. **Share link and ratings.** Should share-link people see rating scores, or only the count? Suggested: count only, notes never; ratings aggregate only from three (ruling 8).
5. **Server-side PDF.** Browser print is used because no PDF library exists. If an archive PDF with fixed layout is wanted, which library is approved?
6. **Vote lines.** Votes carry little meaning one at a time. Show each as a line, or roll up per cluster per minute? Suggested: show each; roll-up only if a screen proves slow.
7. **Agent stage events.** Are "stage opened by the clock" lines North's act or the organiser's? This spec records them as acts of the rule the organiser accepted, flagged `by_clock`.
8. **Tone summary.** "What kind of talk happened" is counts by kind only. A one-line wording ("mostly questions") needs a threshold; none is invented here.
9. **Retention after company offboarding.** The log leaves with the plane. Is a separate archive needed?
10. **Share view route.** Ruling 1 gives the share visitor entry (`POST /api/modules/m1_intent/shared/view`) and the page view `share`. The exact visitor route for the events read (`GET /api/modules/m1_intent/shared/events` here) and whether the tab sits at `/centre/intent/<id>/events` for a guest are for file 14 to confirm.
11. **Numbers this spec chose without a brief rule.** First page of 100 lines then 50 per press, the 30-second poll, the 80-character limit on `detail` strings, and the `draft_of` and `kind` lists. Each needs approval or a different value.
12. **Company admin and rulings.** Ruling 4 and the brief's section 4 let the admin see outcome; this spec still limits the admin to milestones and counts (Open question 1).
