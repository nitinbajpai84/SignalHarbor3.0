# 01. The intent record and its lifecycle

Part of: Intent Centre v2. Depends on: `00-BRIEF.md` only. Feeds: every other file in this folder (each type file, the start page, the Pulse lines, closure, sharing).

## Purpose (three sentences)

Every intent, whatever its type, is one record with one id and one state machine, kept in a folder of its own. This file defines that record, who writes each field, the six states and who moves between them, how the record refers to walls, charters, baselines and assessments without copying them, and the routes that read and change it. Everything type-specific (stages, outcome shape, screens, start questions) lives in the type files and plugs into the fields named here.

## Who uses it and when (role, moment, trigger)

| Role | Moment | Trigger |
|---|---|---|
| Any signed-in company person | Starts an intent | "Start an intent" on `/centre/intent` leads to `/centre/intent/new`; the type file asks the questions |
| Organiser (Janet) | Opens, runs, extends, closes or cancels her intent | Buttons on her intent; North's nudges |
| Sponsor (Daniel) | Named in `people.sponsor` where the type has one | Whether a sponsor may extend, close or cancel is open question 10 |
| Participant (Aaron), observer | Opens the content of an intent they are in. An observer reads and never writes or votes | Invitation, "what is waiting for you", share link |
| Affected person (Katie), or anyone tagged to an area | Sees that the intent exists | The centre lists, filtered by area. Content only if the organiser switched on "affected people may read", or a share names them |
| Company admin | Sees every intent exists, and its outcome | `/centre/intent/admin` |
| Super admin | Sees that intents exist, never content | `/centre/control/intents`, read through the kernel on request |
| North (agent) | Keeps the clock, drafts the closure, nudges, proposes extend, close with what we have, or cancel | Time box thresholds; every stage change |

## Entry points (every route, link, Pulse line, button that leads here)

- `/centre/intent` (home): button **Start an intent** goes to `/centre/intent/new?type=<type>&from=<id>`, the chooser and start questions. Choosing a type calls `POST /api/intents` and then opens `/centre/intent/<id>`.
- The lists on `/centre/intent` and `/centre/intent/past`: `GET /api/intents`.
- `/centre/intent/<id>` (the stage view opens by default), reached from a list row, a Pulse line, a "waiting for you" item or a share link. It reads `GET /api/intents/{intent_id}`. The share visitor does not use this route (file 14).
- State buttons on the intent page (table below), each calling one route.
- North's proposals (extend, close with what we have, cancel) end at the same buttons and routes. A person presses the button.

## Screens, element by element

None. The start page, lists, each type's intent page and the closure screen are in other files, and each has its own route, layouts and element table. This file fixes only the seven button names that map to transitions. No other file may rename them.

| Button | Shown on | Click calls | Result | Visible to |
|---|---|---|---|---|
| **Open** | `/centre/intent/<id>` while `draft` | `PATCH /api/intents/{id}/state` `to=open` | Intent opens, first stage opens, people named are told | Organiser |
| **Start session** | the type's `session` view while `open` | `PATCH /api/intents/{id}/state` `to=in_session` | A live session starts | Organiser |
| **Move to closing** | `/centre/intent/<id>` while `open` or `in_session` | `PATCH /api/intents/{id}/state` `to=closing` | North writes the closure draft | Organiser |
| **Close intent** | `/centre/intent/<id>/close` while `closing` | `POST /api/intents/{id}/close` | Closure signed by the person pressing; record read-only | Organiser. A per-type confirmer signs first where the type names one: sponsor (Initiative), decider (Decision), owner then reporter (Problem); Brainstorm and Weekly check-in have none |
| **Send back to open** | `/centre/intent/<id>/close` while `closing` | `PATCH /api/intents/{id}/state` `to=open` | Closure kept as a draft | Organiser |
| **Cancel intent** | `/centre/intent/<id>` before `closed`; asks for a reason | `POST /api/intents/{id}/cancel` | Intent cancelled, reason kept, shown in Past | Organiser (open question 10 for others) |
| **Extend time box** | `/centre/intent/<id>` while `open`, `in_session` or `closing`; asks for a new end and a reason | `POST /api/intents/{id}/extend` | New end written, extension named | Organiser (open question 10 for others) |

Empty state of every button: hidden when the transition is not allowed for that person from that state. A refused call shows "This intent cannot move there from where it is now."

## User journey (numbered steps from arriving to leaving, with what the agent does between the person's steps)

1. A person presses **Start an intent** on `/centre/intent`, chooses a type at `/centre/intent/new`, and answers that type's start questions. The server creates `intents/<id>/intent.json` in state `draft`, with `people.organiser` set to them and `outcome` already an object shaped for the type. North drafts `title`, `purpose` and `areas` from what they said.
2. The organiser confirms `areas`, names who is affected, and chooses whether affected people may read the content (default off). A draft is seen by its organiser only.
3. The organiser presses **Open**. The server sets the first stage, writes `time_box`, and North tells the people named.
4. The type's work happens (wall, session, week record, root-cause thread, options). The record gains `refs`, `stages` and `outcome` content as the type file says. State is `open`, or `in_session` while a live session runs. North keeps the clock and nudges the person whose turn it is.
5. When the time box ends or the last stage closes, North drafts `closure` and moves the intent to `closing`. If it will not finish in time, North proposes extend, close with what we have, or cancel, and a named person picks.
6. The organiser reads the draft, edits it, and presses **Close intent**. The person who pressed signs. State is `closed`; the record is read-only.
7. Anyone tagged to the area sees it under finished, with its outcome. The organiser may share it (sharing file). The person leaves to `/centre/intent` or `/centre/intent/past`, or starts a follow-up with `from=<id>`.

## States and transitions (table: state, who moves it, to what, what is written)

| From | To | Who moves it | What is written |
|---|---|---|---|
| (none) | `draft` | Any company person, by POST | whole record; `created_by`, `created_at`, `company`; `people.organiser`; `history[0]` |
| `draft` | `open` | Organiser (**Open**) | `state`; `time_box.starts`, `time_box.ends`; `stages[0].state=open`, `opened_at`; `history` |
| `draft` | `cancelled` | Organiser | `state`; `closure: {cancel_reason}` (required); `history` |
| `open` | `in_session` | Organiser (**Start session**) | `state`; the running stage's `opened_at`; `refs` to the session (written by the type's own start route, not by hand); `history` |
| `in_session` | `open` | Organiser, or North when the session ends without the intent finishing | `state`; session stage `closed_at`; `history` |
| `open` or `in_session` | `closing` | North (time box ended, or last stage closed) or the organiser (**Move to closing**). For Initiative: at charter signature (file 32) | `state`; `closure` draft (`closed_by`, `closed_at`, `cancel_reason` stay null); `history.by` shows `north` or the person |
| `closing` | `open` | Organiser (**Send back to open**) | `state`; `closure` kept as a draft; `history` with the reason. Window: open question 4 |
| `closing` | `closed` | A named person, never North (**Close intent**) | `state`; `closure.closed_by`, `closed_at`, `summary`, `why_it_happened`, `what_came_out`, `next[]`; every open stage gets `closed_at`; `history` |
| `open`, `in_session` or `closing` | `cancelled` | Organiser (**Cancel intent**) | `state`; `closure: {cancel_reason}` (required); `history`. Content is kept |
| `closed`, `cancelled` | none | nobody | Terminal. A follow-up is a new intent with `links.from` set |

Rules of the table: a move not listed is refused with "This intent cannot move there from where it is now." Moves are written under the lock in one step. Nothing is deleted (brief section 4): an abandoned draft is cancelled with a reason (open question 11). North moves `closing` and may move `in_session` back to `open`; it never moves to `closed` or `cancelled` (agents never sign). Cancelled intents keep their reason and are shown in Past.

## Records read and written (file or route, fields; mark Existing or New)

| What | Where | Status |
|---|---|---|
| The intent record | `intents/<id>/intent.json` in the company plane (`plane.path("intents", id, "intent.json")`) | **New** |
| The intent list | `intents/index.json`: `{"intents": [{id, type, state, title, areas, organiser, updated_at}]}`; rebuilt by scanning `intents/*/intent.json` if damaged | **New** (same pattern as the M1 session index) |
| Events | `intents/<id>/events.jsonl`, owned by file 16. The record holds a count only | **New**, referenced only |
| Weeks of a Weekly check-in | `intents/<id>/weeks/<week_key>.json`, owned by file 38 | **New**, referenced only |
| Id scheme (proposed, open question 12) | `<prefix>-<32 lowercase hex>`; prefix `ini`, `bra`, `pul`, `prb`, `dec`; hex from `secrets.token_hex(16)`; whole id checked by a pattern before any path is built | **New** (hex part reshaped from `SessionStore.create`, `_hex`) |
| Wall (session) | `intents/m1_intent/sessions/<session_id>.json` | Existing, referenced only |
| Charter and outcome | `intents/m1_intent/outcomes/<outcome_id>.json`; `intents/m2_baseline/outcomes/<outcome_id>.json` | Existing, referenced only |
| Baseline | `intents/m2_baseline/<baseline_id>/` | Existing, referenced only |
| Assessment | `intents/m3_connect/assessments/<assessment_id>` | Existing, referenced only |
| Company profile people (for areas) | `sh_platform/profile/store.py` `load(plane)`, the `people` part | Existing, read only |
| Company time zone | `profile.company.time_zone` (ruling 22) | **New**, used to calculate working days and display times |
| Company switch "titles private to the company" | where it is stored is open question 1 | **New**, not drafted |
| Process record | `sh_platform/process_record.py` | Existing, not mirrored (open question 5) |
| Routes | the nine API routes below | **New** |

The folder `intents/` already holds `m1_intent/`, `m2_baseline/`, `m3_connect/`. An intent folder name always starts with a type prefix and a hyphen, so it cannot collide with them.

### The full record (from brief section 3, as ruled in section 10), with type and writer

| Field | Type | Written by |
|---|---|---|
| `id` | string, scheme above | Server at create, never changed |
| `type` | `initiative`, `brainstorm`, `pulse`, `problem`, `decision`. On screen `pulse` reads "Weekly check-in" (ruling 3) | Server at create from the person's choice, never changed |
| `title` | string | Organiser (North drafts a suggestion) while `draft` or `open`. Length limit: open question 12 |
| `purpose` | string, one line | Organiser (North drafts) while `draft` or `open` |
| `created_by` | account id | Server at create |
| `created_at` | ISO 8601 | Server at create |
| `company` | company id | Server from the signed-in plane, never from the request |
| `areas` | list of strings (department or ops area tags) | Organiser while `draft` or `open`; drives visibility |
| `people.organiser` | person object | Server at create (the creator); hand-over rule is open question 10 |
| `people.sponsor` | person object or null; optional per type | Organiser |
| `people.decider` (Decision), `people.owner`, `people.reporter` (Problem) | person object or null; named slots (ruling 21) | Organiser, as the type file says |
| `people.advisers` | list of person objects (Decision, Problem) | Organiser |
| `people.participants` | list of person objects | Organiser (North suggests from the profile; the organiser confirms) |
| `people.affected` | list of person objects | Organiser (North suggests from the profile; the organiser confirms) |
| `people.observers` | list of person objects | Organiser (observers read only, never write or vote; ruling 21) |
| `state` | `draft`, `open`, `in_session`, `closing`, `closed`, `cancelled` | Server only, through the transition table |
| `time_box.starts`, `time_box.ends` | ISO 8601 | Server at **Open** from the type default; the organiser may set a shorter end at Open (open question 4) |
| `time_box.extended_by` | list of `{by, at, reason}` | Server, on **Extend time box**; `by` is the person pressing |
| `stages` | list of `{key, state, opened_at, closed_at}`; `state` is `waiting`, `open`, `closed` | Server, as the type's routes open and close stages; keys per type are in the type files |
| `outcome` | object shaped per type (file 02), never null (ruling 6) | Created empty at `draft`; filled by the type's own routes |
| `closure.closed_by`, `closed_at` | account id, ISO time | Server, on **Close intent**, from the signed-in person |
| `closure.cancel_reason` | string or null | Server, on **Cancel intent**; required when cancelling |
| `closure.summary`, `why_it_happened`, `what_came_out` | strings | North drafts; the closer edits and confirms |
| `closure.next[]` | `{kind: initiative|problem|decision|backlog|handled|nothing, ref, reason}` (ruling 19) | North proposes; the closer picks; `ref` is an intent id for `initiative`, `problem` and `decision` |
| `ratings` | list of `{by|anonymous, score 1-5, note}`. Anonymous by default (ruling 15); an anonymous row has no `by` and no account id anywhere in the file. A person's own file keeps the link to what they gave. No per-person averages exist. A Weekly check-in series and its weeks are not rated (ruling 3) | Closure and rating file's route |
| `links.from` | intent id or null | Server at create (when started from another intent) |
| `links.to` | list of intent ids | Server, when `closure.next` creates a follow-up |
| `links.build` | ref or null | Hand-off route of the Initiative type (Build side), never by hand |
| `share.link`, `share.who_may_open` | string or null; list of person objects | Organiser, via the sharing file's route. `link` is an opaque token, resolved on the server |
| `record` | `"intents/<id>/intent.json"` (brief section 3 shows a flat file; ruling 12 moves it into a folder) | Server at create |

A Decision may link to any type as source or target (ruling 7); `links.from` and `links.to` carry no type restriction here.

A **person object** is `{account_id, name}`. `account_id` is set when the person has an account; `name` is kept for display. A guest participant has `account_id: null` until they sign in; matching then falls back to the display name, as `sh_platform/profile/view.py` already does for people bound to a name.

Unknown fields are refused on write. The strict key set is section 3 fields plus every field listed under "Fields this feature adds" (ruling 28), not section 3 alone. A file that cannot be read or fails the key check is never overwritten; the route answers "This intent could not be read. Please tell your administrator." and the intent drops out of lists.

## Fields this feature adds to the intent record

| Field | Type | Why | Written by |
|---|---|---|---|
| `version` | integer, starts at 1 | Detects two people saving over each other; incremented on every write | Server |
| `updated_at` | ISO 8601 | List ordering, "last changed" | Server |
| `history` | list of `{at, by, from, to, note}`; `by` is an account id or `north` | The state trail; also hand-overs and extensions. Append only | Server |
| `closure.cancel_reason` | string or null | Cancelled intents say why; lives in closure only (ruling 27) | Server, on cancel |
| `affected_may_read` | boolean, default false | Ruling 4: affected people open the content only when this is on | Organiser, at creation |
| `refs` | `{wall_session_ids: [], charter_outcome_id: null, baseline_ids: [], assessment_ids: []}` | Pointers into `m1_intent`, `m2_baseline`, `m3_connect`. Ids only, never copies. Distinct from `links`, which point to other intents | Written by the type's routes that create or attach the thing; read-only to the organiser |
| `event_count` | integer | Ruling 12: the record holds counts only; the events are in `events.jsonl` (file 16) | Server |
| `closure.draft_by` | `north` or account id | Says who wrote the current closure text | Server |
| `closure.signed` | boolean | True only once a person pressed **Close intent**; a draft never reads as signed (CLAUDE.md rule 7) | Server |

## Agent behaviour (North, Lens, Nira: what each drafts, when, and the moment a person acts)

- **North** drafts `title`, `purpose` and `areas` from what the person says; the person confirms by pressing **Open**. North moves `open` or `in_session` to `closing` when the time box ends or the last stage closes, and writes the closure draft in the same write. North nudges the person whose turn it is at moments still to be set (open question 3). When North judges the intent will not finish, it proposes extend, close with what we have, or cancel; a named person presses one. North never signs, closes or cancels.
- **Lens** does not touch the record. It drafts definitions inside the referenced m2 stores; the intent only holds the ids.
- **Nira** reads `state`, `people` and `time_box` to build "waiting for you" and Pulse lines. Nira writes nothing here.

## Rules (visibility, time box, who may do what)

**Visibility, three tiers, decided on the server by one function** (**New**: `sh_platform/intents/view.py`, built on the existing `Viewer`, `norm` and `allows` from `sh_platform/profile/view.py`; `profile.view.read` returns the company profile and is not reused whole):

| Tier | Who | They get |
|---|---|---|
| `content` | organiser, sponsor, participants, observers (read only, never write or vote), affected people when `affected_may_read` is on, and anyone a share link names | the whole record; `ratings` and notes keep the D-013 and seal rules, and anonymous rows never carry an author |
| `card` | affected people (by area or named) and anyone whose areas overlap `areas`, when they are not in `content` | `id, type, title, purpose, state, stages (key, state), areas, people (names), time_box`, and `outcome` once `closed`; no `closure.why_it_happened`, no `ratings`, no `refs` |
| `exists` | Company admin: every intent's existence and outcome, never anonymous notes. Super admin: title, type, state, areas, people count, dates, time box status, per company, read through the kernel on request; no copy is kept in the control plane | nothing of content. If the company switch "titles private to the company" is on (default off), the super admin view carries no titles |

A viewer outside every tier does not see the intent, not even as a stub (as `profile.view` drops a hidden area). A draft is tier `content` for its organiser and invisible to everyone else, including the company admin (ruling 14). The viewer's own areas come from the company profile (`profile.store.load(plane)["people"]`); the `Viewer` dataclass has no areas today, so a small `areas_of(plane, viewer)` is **New**. A person with no known area sees only intents they are named in. Account ids are removed from every response outside `content`.

**Who may do what.** Route roles are the coarse gate (default deny, as in `route_permissions.yaml`). The handler then checks the person's part in this intent:

- Edit `title`, `purpose`, `areas`, `people`: organiser, while `draft` or `open`. After `closing` begins, nothing but `closure` text changes.
- **Open**, **Start session**, **Move to closing**, **Send back to open**: organiser.
- **Extend time box**: organiser. Whether the sponsor, decider, owner or company admin may also extend is open question 10.
- **Close intent**: organiser. A per-type confirmer signs first where named: sponsor (Initiative), decider (Decision), owner then reporter (Problem). Brainstorm and Weekly check-in have no confirmer (ruling 25).
- **Cancel intent**: organiser. Whether the sponsor, decider, owner or company admin may also cancel is open question 10.
- A closed record is read-only. A draft by North never overwrites a human edit (CLAUDE.md rule 7): if `closure.draft_by` is a person, North's redraft is refused and offered as a suggestion.
- Nothing is deleted.

**Time box.** `time_box.ends` is `starts` plus the type default in working days (Monday to Friday; ruling 22), computed by a date-returning sibling of `window_minutes` in `modules/m1_intent/domain/timer.py` (reshaped into `sh_platform/intents/`). Defaults from the brief: Initiative 10, Brainstorm 3, Problem 5, Decision 2; a Weekly check-in is one week, recurring, and its next week opens by the clock on the next working day after the close day (ruling 3). Times are shown in the company's time zone from `profile.company.time_zone`, else UTC (ruling 8, 22). Each extension appends `{by, at, reason}`; the new end is written to `time_box.ends` and the old end stays in `history`. Any cap on extensions is open question 4.

**Concurrency.**

- The store holds one lock per company intents folder: `lock_for(plane.path("intents"))` from `sh_platform/jsonfile.py`, taken for every read-modify-write, as `SessionStore._lock` does. The lock is re-entrant so a transition can call the index update inside it.
- Write order: record first with `write_json_atomic`, then the index entry. A crash between them leaves a record with a stale index row; the index is rebuilt from the files on the next list.
- Every PATCH, state, close, cancel and extend body carries `version`. If it differs from the file's, the route answers 409 "Someone changed this intent. Please reload." and writes nothing. Create has no version.
- `jsonfile.py` documents that the lock covers threads in one process only. One backend process is assumed (open question 6).

**The API** (declared in `sh_platform/route_permissions.yaml`, default deny; the kernel router sits beside `sh_platform/outcomes.py`, not inside a module, because an intent crosses modules). Guest routes stay where the kernel allows them (ruling 24): `/api/modules/m1_intent/shared/*`, `/api/modules/m1_intent/approver/*`, `/approve/<token>`, `/join/<code>`, `/owner-answer/<token>`. These are the listed exceptions to routing rule 1.

```yaml
  # Intent Centre v2: the intent record (platform router sh_platform/intents/api.py)
  GET /api/intents: {roles: [company_admin, sponsor, analyst, approver, participant, owner]}
  POST /api/intents: {roles: [company_admin, sponsor, analyst, approver, participant, owner]}
  GET /api/intents/{intent_id}: {roles: [company_admin, sponsor, analyst, approver, participant, owner]}
  PATCH /api/intents/{intent_id}: {roles: [company_admin, sponsor, analyst, approver, participant, owner]}
  PATCH /api/intents/{intent_id}/state: {roles: [company_admin, sponsor, analyst, approver, participant, owner]}
  POST /api/intents/{intent_id}/extend: {roles: [company_admin, sponsor, analyst, approver, participant, owner]}
  POST /api/intents/{intent_id}/close: {roles: [company_admin, sponsor, analyst, approver, participant, owner]}
  POST /api/intents/{intent_id}/cancel: {roles: [company_admin, sponsor, analyst, approver, participant, owner]}
  GET /api/intents/control: {roles: [super_admin]}
```

| Route | Does | Body | Answers |
|---|---|---|---|
| `GET /api/intents` | list, filtered to the viewer's tiers; query `type`, `state`, `area`, `mine=1`, `view=running|finished|past` | none | `[{id, type, title, purpose, state, areas, organiser, time_box.ends, tier}]`, newest first; an empty list is `[]`, never an error |
| `POST /api/intents` | create a draft | `type`, `title?`, `purpose?`, `areas?`, `links.from?` | 201 and the record (tier `content`) |
| `GET /api/intents/{id}` | one intent at the viewer's tier | none | the record cut to the tier, plus `refs_resolved` (below); 404 when the viewer has no tier |
| `PATCH /api/intents/{id}` | edit the organiser-owned fields | `version` and any of `title, purpose, areas, people, affected_may_read` | the new record; 409 on stale `version`; 403 when not the organiser |
| `PATCH /api/intents/{id}/state` | one transition from the table, except to `closed` and `cancelled` | `version`, `to`, `note?` | the new record; 409 "cannot move there" when not listed |
| `POST /api/intents/{id}/extend` | extend the time box | `version`, `to` (new end), `reason` (required) | the new record |
| `POST /api/intents/{id}/close` | `closing` to `closed` | `version`, `summary, why_it_happened, what_came_out, next[]` | the closed record; refuses an empty `summary` |
| `POST /api/intents/{id}/cancel` | to `cancelled` | `version`, `cancel_reason` (required) | the cancelled record |
| `GET /api/intents/control` | existence list for `/centre/control/intents`; query `company_id`; read through the kernel on request | none | `[{id, type, state, areas, people_count, starts, ends, time_box_status, title?}]`; `title` absent when the company switch is on. Spelling is open question 14 |

Why `close` and `cancel` are separate from `state`: they sign. They require a named person and carry text, and North can never call them.

**References, not copies.** `refs_resolved` is built at read time: for each id in `refs`, the server asks the owning module's store for a one-line summary (wall: topic and state; charter: signed or not; baseline: version and state; assessment: state). A missing target returns `{"ref": "<id>", "status": "Not available yet", "missing": "wall session not found"}`. The intent never stores the title or text of a wall, charter, baseline or assessment.

## Counters and measures of this feature (numbers only, each traced to a record)

Counts are exact. A median shows "Fewer than five" below five records (ruling 8).

| Measure | Source |
|---|---|
| Intents by type and by state | count of `intents/<id>/intent.json` grouped by `type`, `state` |
| Closed in time box | closed intents where `closure.closed_at <= time_box.ends` (final end after extensions) |
| Extended at least once | `time_box.extended_by` not empty |
| Cancelled, with reasons present | `state = cancelled` and `cancel.reason` not empty |
| Median working days from open to close | `history` (the `open` and `closed` entries); "Fewer than five" below five closed intents |

If there are no closed intents the screen says "Not available yet: no intent has closed."

## Reuse check (what exists today: file paths and line ranges found with graft; copied, reshaped or not used, and why)

Searches run: `graft ask "session store m1_intent" --source`; `graft skeleton` on `modules/m1_intent/store/sessions.py`, `sh_platform/jsonfile.py`, `sh_platform/profile/view.py`. Every path below was checked to exist with `ls` on 7 October 2026. Where a first-draft reference was wrong it is corrected here (`profile.store.raw` does not exist; `load(plane)` does).

| Found | Decision |
|---|---|
| `modules/m1_intent/store/sessions.py` L42-L297 `SessionStore`: one file per record, index file, `_lock` over the folder, `_read` strict key set, `_save` (file then index), `transition` through one table, `_mine` ownership check | **Reshaped** into `sh_platform/intents/store.py`. Same shape; module-free (the kernel cannot import a module). Not used as is: its states are wall stages, its index keys are fixed to sessions, and it keeps a flat file per session where intents need a folder |
| `modules/m1_intent/domain/states.py` L1-L39: one `_MOVES` table, `can_move`, `move`, `IllegalMove` | **Copied** as the pattern for the intent table (`sh_platform/intents/states.py`) with the six states above |
| `sh_platform/jsonfile.py` L19-L61: `lock_for`, `read_json_strict`, `write_json_atomic` | **Used as is** |
| `sh_platform/plane.py` L51-L72 `CompanyPlane.path`; L7 `AREAS` includes `intents` | **Used as is**; no new area |
| `sh_platform/profile/view.py` L27-L44 `Viewer`, `norm`, `allows`; L116-L199 `read` | `Viewer`, `norm`, `allows` **used as is**. `read` **not used**: it returns the company profile. The intent filter is **New** and small |
| `sh_platform/profile/store.py` L78 `load(plane)` | **Used as is**, read only, for people and areas |
| `modules/m1_intent/domain/timer.py` L35-L41 `window_minutes` (Monday to Friday, UTC) | **Reshaped**: a sibling that returns an end date and uses the company's time zone, else UTC |
| `sh_platform/outcomes.py` router; `_plane` (L23) and `_viewer` (L35) in `sh_platform/profile/api.py` | **Used as is** for the router pattern and the signed-in plane and viewer |
| `sh_platform/route_permissions.yaml` (default deny) | **Used**; nine routes added |
| `sh_platform/process_record.py` | **Not used** for intents (open question 5) |
| `modules/m1_intent/store/notes.py` L36 `NoteStore`, L66 `mark_anonymous` (authors apart from notes) | **Not used here**; the rule is carried over: ratings and anonymous notes never carry an author inside the intent record |
| `modules/m1_intent/store/charter.py`, `modules/m2_baseline/store/signoff.py`, `modules/m3_connect/` | **Not used**; only their record paths are referenced by id |

Genuinely new: the intent record and its index, the id scheme, the transition table with six states, `areas_of`, the tiered filter, the nine routes.

## Not in this feature

- Screens: the start page, lists, intent pages, the closure screen (other files).
- Each type's stages, outcome shape, start questions and agent drafts.
- The share route and link tokens, and the ratings route (they write `share` and `ratings`; the sharing and closure files own them).
- The event log (file 16) and the weekly files (file 38).
- Creating a wall, charter, baseline or assessment (the existing modules do; this file only stores their ids).
- Gap analysis, which is room 0 of the Build centre at `/centre/build/gap-analysis?from=<id>`, and the Moment of truth (Build).
- Migrating existing walls into intent records (open question 7).

## Open questions

1. **Where the "titles private to the company" switch lives.** Ruling 5 adds the switch (default off) but not its store. The company profile is the obvious place. The ruling also asks Nitin for a request (A-074 in the brief) that the super admin may read intent existence through the kernel; `docs/decisions.md` already uses A-074 for another decision, so the number needs checking.
2. **Who may start an intent.** The brief says anyone. All six company roles are listed on create. Should an `owner` or `approver` start an Initiative, or only a Brainstorm, Problem or Decision?
3. **North's nudge moments.** When does North nudge (for example half time, a working day left)? No rule exists yet.
4. **Extension cap, shorter end at Open, and Send back to open.** Is there a cap on extensions? May the organiser set a shorter end at Open? Is there a window after `closing` begins in which the organiser may send it back?
5. **Process record mirror.** `ProcessRecords` mirrors a session state for the landing logic. Should intents mirror to it, or does the intent list replace it for the new centre?
6. **Single process.** `lock_for` is per process. A second backend process needs a file lock first (the name vault has one). Confirm one process for the demo.
7. **Existing walls.** A wall made before this change has no intent record. Create an Initiative record on first open (backfill), or leave old walls outside the centre lists?
8. **Where a viewer's areas come from.** `Viewer` has no areas. Drafted: the profile `people` entry's team. A person missing from the profile sees only intents they are named in.
9. **Company time zone field.** Ruling 22 adds `profile.company.time_zone` as the source for displaying times and calculating working days; if absent, use UTC. The profile code shows no time zone field today. Add it, or always UTC until then?
10. **Who may extend, close, cancel or hand over.** Drafted: the organiser only. Should the sponsor, the decider (Decision), the owner (Problem) or the company admin (a stuck intent) also be able to, and how is a stuck intent defined? Who may hand the organiser role over?
11. **Abandoned drafts.** The brief says nothing is deleted. Drafted: an abandoned draft is cancelled with a reason and shown only to its organiser until opened. Confirm, or allow deleting a draft that was never opened.
12. **Id scheme and field limits.** The id scheme above is a proposal. Is there a length limit on `title` and `purpose`?
13. **Holiday calendar.** Working days are Monday to Friday (ruling 22) until the company profile has a calendar. Does the company calendar or profile define holidays?
14. **Super admin route spelling.** Ruling 1 gives the page `/centre/control/intents` and says API routes live under `/api/intents/...`. `GET /api/intents/control` with `company_id` is drafted; confirm the spelling.
15. **Brief section 3 against rulings.** Section 3 shows `outcome` as `| null` and `record` as `intents/<id>.json`. Rulings 6 and 12 win and this file follows them.
