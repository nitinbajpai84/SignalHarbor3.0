# 14. Permissions matrix

Part of: Intent Centre v2. Depends on: 00-BRIEF (visibility rule, intent record, section 10 rulings 1, 4, 5, 13, 14), 02 (types, people, closers). Feeds: every spec that adds a route or a page (they adopt the route names below, or rename them here first).

## Purpose (three sentences)

This file is the one table of who may reach which route and page of the Intent Centre v2: seven accounts (six company roles and the super admin) against every API route and page, then the per-intent roles against every action inside one intent. It keeps the existing rule of `sh_platform/route_permissions.yaml` (default deny, role check first) and adds one more check after it: is this person in this intent, and in what role. It also owns the route list (pages and API, as settled in brief section 10 ruling 1), fixes the top bar per role, the tests that must change, and the exact words a refused person reads.

## Who uses it and when (role, moment, trigger)

| Who | Moment | Trigger |
|---|---|---|
| Builder of any Intent Centre route | Declares the route | Adds a line to the yaml block below and to `route_permissions.yaml`, never anywhere else |
| Reviewer | Reviews a package | Compares the route's yaml line, its handler's per-intent check and the matrix rows |
| Every signed-in person | Opens the centre | The role check, then the per-intent check, decide what they see |
| Share visitor (no account) | Opens a link from an organiser | One entry route, one token, read only |
| Company admin | Asks "who can see this?" | Reads the Rules section; nothing here is configurable per company in this round except the two switches in route "settings" |
| Super admin | Opens Control | Sees that intents exist, per company, and nothing inside them |

People act at named moments; agents never hold a role in this table. North, Lens and Nira run as the signed-in person who triggered them and see only what that person may see.

## Entry points (every route, link, Pulse line, button that leads here)

- `sh_platform/route_permissions.yaml`: the block "Intent Centre v2" (below) is appended there.
- `ui/src/shell/roles.ts`: the role table gains the `intent` centre for the four roles that lack it.
- Every spec's "Entry points" and "Records read and written" list their routes; each must appear in the route list here, or the build fails `test_every_route_is_declared`. This file was checked against all 54 files with `grep` for `/api/intents` and `/centre/intent`; the routes it found are rows 1 to 141 below, spelled the way brief section 10 ruling 1 requires.
- Refused states reached from: a typed URL, an old Pulse line, a revoked share link, a role change during a session.

## Screens, element by element

This feature owns one screen, the refused panel, and the top bar and section links. Everything else is a page owned by another spec; this file only fixes who may open it. Page routes are under `/centre/intent` (the shell's own prefix; `ui/src/App.tsx` lines 105 to 143 today).

### Screen 1: the refused panel

Route: any page below. Layout at 1280: one panel in the main column under the top bar, centred, with the cause line, the hint line and one button. At 390: the same panel full width, the top bar collapsed to the existing menu, the button full width.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Cause line | panel | The words from "Error copy" for the cause | None | Whoever was refused | Never empty; falls back to the `forbidden` words |
| Hint line | agent line (North) | "Ask {organiser name} to add you", drawn from the record's organiser; never names content | None | Area members and company admin on a refused content call | Hidden when no organiser is resolvable |
| Back to the Intent Centre | button | "Back to the Intent Centre" | Goes to `/centre/intent` | Whoever was refused | Never hidden |

### Screen 2: the top bar and section links

Route: every `/centre/intent/...` page. Layout at 1280: top bar across the page, section links in the Intent Centre's own header row. At 390: both collapse into the existing menu; Start something stays visible as a button.

| Element | Kind | Shows | On click | Visible to | State when empty |
|---|---|---|---|---|---|
| Home | link | "What is happening" | `/centre/intent` | all six | Never empty |
| Start something | button | "Start something" | `/centre/intent/new` | all six | Never hidden |
| Past | link | "Past" | `/centre/intent/past` | all six | "No past intents in your areas yet." |
| Backlog | link | "Backlog" | `/centre/intent/backlog` | all six | "Nothing in the backlog yet." |
| Admin | link | "Admin" | `/centre/intent/admin` | company_admin | Hidden for others |
| Bring what you have | link | existing | `/centre/intent/bring` | company_admin, sponsor, analyst | Hidden for others |
| Outcomes | link | existing | `/centre/intent/outcomes` | company_admin, sponsor, analyst, approver, owner | Hidden for participant |

### Pages

CA company_admin, SP sponsor, AN analyst, PA participant, OW owner, AP approver, SA super admin. "six" means CA, SP, AN, PA, OW and AP pass `RoleGate centre="intent"`; the super admin is refused and redirected to `/centre/control`. The last column is layer 2.

| Page route | Purpose | Company roles | SA | Per-intent check (layer 2) |
|---|---|---|---|---|
| `/centre/intent` | Home: "What do you want to do?" and what is happening in my areas | six | - | None; the lists are filtered per viewer |
| `/centre/intent/new?type=<type>&from=<id>` | Chooser and the start questions for one type | six | - | `type=initiative` also needs the organiser capability. `from` must name an intent the person may see |
| `/centre/intent/<id>` | The intent screen; the stage view opens by default | six | - | Draft: creator only. Existence view for M, X; F sees clock and people too; content view for O, D, P, B and for F only when "affected people may read" is on |
| `/centre/intent/<id>/wall` | Think unfiltered | six | - | Content readers; write: O, P |
| `/centre/intent/<id>/define` | Define strategically | six | - | Content readers; write: O (and the named owners for their own rows) |
| `/centre/intent/<id>/charter` | Charter and signature | six | - | Content readers; sign: the sponsor, or CA for the sponsor |
| `/centre/intent/<id>/build-ready` | Build-ready check and hand-off | six | - | Content readers; hand-off: D |
| `/centre/intent/<id>/session` | Live session (Brainstorm, or a check-in session) | six | - | O, P; B and open F read |
| `/centre/intent/<id>/week` | A week of a Weekly check-in | six | - | O, P; open F read |
| `/centre/intent/<id>/review` | Review a week | six | - | O |
| `/centre/intent/<id>/close` | Closure draft, confirm, ratings | six | - | Draft O, D; confirm D only; rate P |
| `/centre/intent/<id>/share` | Share links (create, list, revoke) | six | - | O only |
| `/centre/intent/<id>/events` | Transcript and audit trail | six | - | O, D (open question: P) |
| `/centre/intent/<id>/people` | People and roles (edit) | six | - | Read as route "GET people"; edit: O only |
| `/centre/intent/<id>/projector` | Projector view | six | - | O |
| `/centre/intent/past` | Past intents, filtered per viewer (cancelled ones show their reason) | six | - | Existence rows only |
| `/centre/intent/past/<id>/chain` | The chain of linked intents | six | - | As the intent screen; hidden steps counted |
| `/centre/intent/backlog` | The backlog | six | - | Filtered per viewer |
| `/centre/intent/admin` | Company admin views and settings | CA | - | None |
| `/centre/control/intents` | Intents per company, existence only | - | Y | None; reads through the kernel |
| `/centre/build/gap-analysis?from=<id>` | Room 0 of Build (the Moment of truth, moved) | CA, AN | - | `RoleGate centre="build"`, unchanged; the analyst receives the charter reference, not membership of the intent |
| `/centre/intent/bring`, `/centre/intent/outcomes` | Existing; unchanged | bring: CA, SP, AN. outcomes: CA, SP, AN, AP, OW | - | None |
| `/centre/intent/wall/:sessionId`, `define/:sessionId`, `charter/:sessionId`, `baseline/:baselineId`, `truth/:assessmentId` | Existing rooms; kept until each owning spec moves them under `/centre/intent/<id>/<view>` | by seat or role | - | Outside `RoleGate` so an invite link works; existing handlers |
| `/centre/build/*`, `/centre/control/*` | Build and Control | Build: CA, AN. Control: CA | Control: Y | Unchanged |

### Top bar per role (the one table: `roles.ts`, mirrored in the yaml)

| Role | Top bar, in order | Lands on | Change from today |
|---|---|---|---|
| participant | Pulse, Intent, Map | Pulse | adds Intent |
| owner | Pulse, Intent, Consume, Map | Pulse | adds Intent |
| approver | Pulse, Intent, Consume, Map | Pulse | adds Intent |
| sponsor | Pulse, Intent, Consume, Map | Pulse | none |
| analyst | Pulse, Intent, Build, Consume, Map | Pulse | adds Intent |
| company_admin | Pulse, Intent, Build, Consume, Map, Control | Pulse | none |
| super_admin | Control | Control | none |

Everyone sees "Intent Centre" except the super admin. Build stays analyst and company admin. This changes QUALITY-PASS section 1 (owner, approver and participant had no Intent). That file is outside this folder, so the change is an open question for Nitin; this spec assumes yes.

## User journey (numbered steps from arriving to leaving, with what the agent does between the person's steps)

1. The person asks for a page or route by typing a URL, clicking a link, or following a Pulse line. The shell reads the role table and shows or hides the link; the server never trusts the link.
2. Layer 0, module check (`ModuleGate`): does the company own `m1_intent`? A miss returns `module_not_available`. This runs before layer 1.
3. Layer 1, role check (`AuthMiddleware`, default deny): the account's role must be in the yaml line. A miss returns the existing 403 body `{"error": "forbidden", "message": "You do not have access to this."}`.
4. Layer 2, per-intent check (the handler, `intent_access(intent, account) -> role set`): is this person the creator of a draft, named in the intent, tagged to its areas, or a company admin? The result sets what the handler returns.
5. Layer 3, state check: is the action allowed in the intent's state (closed and cancelled are read only)?
6. Between steps, North, Lens and Nira act inside layer 2 as the triggering person. If a person is removed from an intent, an agent draft already written stays; the next call is refused.
7. The person sees the result, or the refused panel (Screen 1). Nothing in the panel names content they may not see.
8. The person leaves by the one button, "Back to the Intent Centre", or by any link in the top bar.

## States and transitions (table: state, who moves it, to what, what is written)

A person's access to one intent changes as the record changes. Nothing here is a new stored state; it is derived on every call from `intent.people`, `intent.areas`, `intent.state`, `intent.share` and the intent's `affected_may_read` switch.

| Access state | Who moves it | To what | What is written |
|---|---|---|---|
| none (not tagged, not named) | Organiser tags an area the person belongs to | area member | `areas` |
| area member | Organiser names them participant, affected, observer, decider, owner or reporter | that role | `people.*` |
| any role | Organiser removes them | area member or none | `people.*`; an audit line in the run log, never the content |
| affected, content closed | Organiser switches "affected people may read" on, or names the person on a share | affected, content open | `affected_may_read`, or `share.who_may_open` |
| draft, creator only | Creator opens the intent | visible per the visibility rule | `state` |
| any | Organiser mints a share token for a person | share visitor (read only, closed or open intent) | `share.who_may_open` entry with token hash and expiry |
| share visitor | Organiser revokes, or the token expires | none | token marked revoked with `at` and `by` |
| any | `intent.state` becomes `closed` or `cancelled` | writes refused for everyone; reads unchanged; a cancelled intent stays in Past with its reason | none |

## Records read and written (file or route, fields; mark Existing or New)

| Record | Mode | Fields | Mark |
|---|---|---|---|
| `sh_platform/route_permissions.yaml` | write | the block below | Existing file, new lines |
| `ui/src/shell/roles.ts` role table | write | `intent` added to participant, owner, approver, analyst | Existing file |
| `sh_platform/modulegate.py` | write | `ModuleGate` also judges `/api/intents/...` as module `m1_intent` (one prefix table, see Rules) | Existing file, small change |
| `intents/<id>/intent.json` | read | `people`, `areas`, `state`, `share`, `outcome`, `created_by`, `affected_may_read` | New (brief section 3, ruling 12) |
| `settings/intent_centre.json` (company plane) | read | `titles_private` (default false); written only through `PUT /api/intents/settings` | New (48) |
| profile people and areas (`sh_platform/profile/store.py`, `view.py`) | read | person id, account link, areas of the person | Existing |
| `GET /api/profile/links` (LI-LINK) | read | account to person | Existing |
| Kernel read for Control (route 28 and summary) | read | the projection of route 28 only; the control plane stores nothing | New (request A-074) |
| Run log | write | one line per refused per-intent call: who, intent id, route, reason code. No content | Existing log, new line kind |

## Fields this feature adds to the intent record

- `people.<role>[]` entries carry `person_id` and, where linked, `account_id` (server side only; never sent to a browser). The slots are those of ruling 13: `organiser`, `sponsor` (optional per type), `decider` (Decision), `owner` and `reporter` (Problem), `participants`, `affected`, `observers`.
- `affected_may_read`: bool, set by the organiser at creation, default off (ruling 4). Owned by 47; read here.
- `share.who_may_open[]`: `{person_id|null, label, token_hash, expires_at, revoked_at|null, created_by}`. A token is per named person, so the organiser can revoke one without ending the others.
- `access_log`: none. Refusals go to the run log, not the record.

## Route list and matrix

Collected from the brief, ruling 1, and every other file's "Entry points" and "Records read and written". Where a route is mine to name, it sits under `/api/intents/...`. The owning spec for each group may rename a route here, never in its own file alone. Literal segments (`types`, `areas`, `people`, `home`, `waiting`, `measures`, `settings`, `backlog`) are reserved: no intent id may equal one, and they are declared before the `{intent_id}` lines.

Column key: Roles: "six" is the six company roles (CA, SP, AN, PA, OW, AP), CA is company admin only, SA is super admin only; any role not named is refused by the guard with 403. Per-intent letters: O organiser, D named closer or decider (sponsor, decider, owner), P participant (a Problem's reporter counts as P), F affected, B observer, M area member, X company admin, V share visitor, N the named person, CA company admin. Content readers are O, D, P, B, and F when "affected people may read" is on.

| # | Method and path | Roles | Per-intent check | Spec |
|---|---|---|---|---|
| 1 | GET `/api/intents/types` | six | None. Same catalogue for all (02 says `/intent-types`; it adopts this name) | 02 |
| 2 | GET `/api/intents/areas` | six | None. Area names of the company only | 05, 11 |
| 3 | GET `/api/intents/people` | six | None. Names and areas only, for the pickers; never emails | 06, 11 |
| 4 | GET `/api/intents` | six | Filtered per viewer. A draft: its creator only. O, D, P, F, B, M, X see existence rows, cancelled ones too with the reason (Past is the same call with `view=past`). Content never in a list | 04, 12, 15 |
| 5 | POST `/api/intents` | six | Caller becomes creator and organiser. `type: initiative` also needs the organiser capability | 03, 22, 35, 38, 41, 43 |
| 6 | GET `/api/intents/{intent_id}` | six | Draft: creator only, else 404. M, X: existence view (title, purpose, stage, organiser, outcome once closed). F: existence plus clock and people. O, D, P, B: plus `access: "content"`. None: 404 | 01, 05, 47 |
| 7 | PUT `/api/intents/{intent_id}` | six | O, state `draft` or `open` (not state-only; see row 29) | 01 |
| 8 | POST `/api/intents/{intent_id}/open` | six | O, state `draft` | 01, 38 |
| 9 | PUT `/api/intents/{intent_id}/people` | six | O; not after `closed`. Slots: organiser, sponsor (optional), decider, owner, reporter, participants, affected, observers | 06 |
| 10 | POST `/api/intents/{intent_id}/stages/{stage_key}/open` | six | O | 01, 08 |
| 11 | POST `/api/intents/{intent_id}/stages/{stage_key}/close` | six | O (Initiative stage `build_ready`: O or D) | 01, 08 |
| 12 | POST `/api/intents/{intent_id}/extend` | six | O, with a reason (`time_box.extended_by`) | 07 |
| 13 | POST `/api/intents/{intent_id}/cancel` | six | O; Initiative: D (the sponsor). A reason is required and kept | 01 |
| 14 | GET `/api/intents/{intent_id}/content` | six | O, D, P, B. F only when the organiser switched on "affected people may read" (default off) or the person is named on a share. Sealed and anonymous material per v1 rules. M and X refused | 05, 47 |
| 15 | POST `/api/intents/{intent_id}/contributions` | six | O, P (a Problem's reporter counts as P). F on a Problem (evidence) is an open question. B never. Not after close | 24, 42 |
| 16 | POST `/api/intents/{intent_id}/north/turns` | six | The person whose turn it is, or any seat for a group question | 08 |
| 17 | GET `/api/intents/{intent_id}/closure` | six | Draft: O, D. Confirmed closure: as the existence view | 09 |
| 18 | PUT `/api/intents/{intent_id}/closure` | six | O, D; state `closing` | 09 |
| 19 | POST `/api/intents/{intent_id}/closure/confirm` | six | The named closer D only. Not the organiser unless the same person | 09 |
| 20 | POST `/api/intents/{intent_id}/ratings` | six | P, once each; anonymous by default; no per-person average exists anywhere | 10 |
| 21 | POST `/api/intents/{intent_id}/next` | six | D or O. Starts a linked intent from `closure.next`; a Decision may link to any type. `handled` and `decision` as closure next kinds: no route change, carried by this row | 20 |
| 22 | POST `/api/intents/{intent_id}/build-ready/check` | six | Initiative only; O or D | 33 |
| 23 | POST `/api/intents/{intent_id}/handoff` | six | Initiative only; D (the sponsor signs). Writes `links.build`. Build's own routes stay `/api/company/build/*`; gap analysis opens at `/centre/build/gap-analysis?from=<id>` | 33 |
| 24 | GET `/api/intents/{intent_id}/share` | six | O | 11 |
| 25 | POST `/api/intents/{intent_id}/share` | six | O; never on a cancelled intent or a draft | 11 |
| 26 | DELETE `/api/intents/{intent_id}/share/{token_id}` | six | O | 11 |
| 27 | POST `/api/modules/m1_intent/shared/view` | six | `guest: true, entry: true`. Token valid, unexpired, unrevoked, names a person. V only. Read only | 11 |
| 28 | GET `/api/control/companies/{company_id}/intents` | SA | Existence only, read through the kernel on request, no copy in the control plane. Keys exactly: `id`, `type`, `state`, `areas`, `people_count`, `starts`, `ends`, `time_box_status`, and `title` (left out when `titles_private` is on). Drafts left out. Never content, outcome or names | 05, 48 |
| 29 | PUT `/api/intents/{intent_id}/state` | six | O. One listed transition, never to `closed` or `cancelled` | 01 |
| 30 | GET `/api/intents/{intent_id}/people` | six | Content readers see the full list; F and M names and roles only; filtered by `profile/view.py` | 06 |
| 31 | POST `/api/intents/{intent_id}/people` | six | O. Add by pick, with roles | 06 |
| 32 | POST `/api/intents/{intent_id}/people/{person_id}/answer` | six | N, the person asked. Accept or decline with a reason | 06 |
| 33 | POST `/api/intents/{intent_id}/people/{person_id}/role` | six | O. Role and reason | 06 |
| 34 | POST `/api/intents/{intent_id}/people/{person_id}/remove` | six | O. Reason; an audit line, never the content | 06 |
| 35 | GET `/api/intents/{intent_id}/clock` | six | As route 6 (the existence view is enough) | 07 |
| 36 | POST `/api/intents/{intent_id}/extend/{n}/decide` | six | D (the sponsor). A second extension by the organiser waits for this | 07 |
| 37 | GET `/api/intents/{intent_id}/north` | six | O, D, P, B; F when content is open to them | 08 |
| 38 | POST `/api/intents/{intent_id}/north/drafts/{draft_id}/confirm` | six | The person named on the draft | 08 |
| 39 | POST `/api/intents/{intent_id}/north/drafts/{draft_id}/discard` | six | The person named on the draft | 08 |
| 40 | POST `/api/intents/{intent_id}/north/proposals/{draft_id}/pick` | six | The person named on the proposal | 08 |
| 41 | POST `/api/intents/{intent_id}/north/clock-check` | six | Any content reader; idempotent per day | 08 |
| 42 | GET `/api/intents/{intent_id}/ratings` | six | O, D: counts, and an aggregate only from three ratings; signed entries only when not anonymous. P: own. Others nothing | 10 |
| 43 | POST `/api/intents/{intent_id}/rating/waive` | six | P | 10 |
| 44 | POST `/api/intents/{intent_id}/outcome-used` | six | P, or the person the outcome was made for; yes, partly or no | 10, 19 |
| 45 | GET `/api/intents/{intent_id}/chain` | six | As route 6; steps the viewer may not see are counted, not shown | 12, 20 |
| 46 | POST `/api/intents/{intent_id}/history-notes` | six | O. A note on a past intent (12 names `POST /api/company/intents/{id}/note`) | 12 |
| 47 | POST `/api/intents/{intent_id}/share-request` | six | M or F on a closed intent. Asks the organiser through a Pulse line | 12 |
| 48 | GET `/api/intents/{intent_id}/transcript/download` | six | O, D (open question: P) | 16 |
| 49 | GET `/api/intents/{intent_id}/events` | six | O, D (open question: P). Anonymous authors masked | 16 |
| 50 | GET `/api/intents/measures` | six | Company admin sees the panel; the route returns counts only. Means, medians and per-person figures show "Fewer than five" below five records | 19 |
| 51 | GET `/api/intents/home` | six | Per viewer. Counters and Your turn lines from the viewer's own intents (04 names `/api/centre/home`) | 04 |
| 52 | GET `/api/intents/waiting` | six | The caller's own lines only | 45 |
| 53 | GET `/api/intents/{intent_id}/who-has-not-acted` | six | O | 45 |
| 54 | POST `/api/intents/{intent_id}/nudge/{person_id}` | six | O or D. Nudge a named person; one draft is created and sent | 43, 45 |
| 55 | POST `/api/intents/{intent_id}/links/proposal` | six | O or D. Writes nothing | 20 |
| 56 | POST `/api/intents/{intent_id}/links` | six | O or D. Creates the target draft; the caller becomes its organiser | 20 |
| 57 | POST `/api/intents/{intent_id}/links/{link_id}/checked` | six | O. "I have checked" on a cancelled-source banner | 20 |
| 58 | GET `/api/intents/backlog` | six | Company wide; each row shows only what the viewer may see | 21 |
| 59 | GET `/api/intents/backlog/{item_id}` | six | As the list row | 21 |
| 60 | PATCH `/api/intents/backlog/{item_id}` | six | Who raised it, or CA | 21 |
| 61 | POST `/api/intents/backlog/{item_id}/{act}` | six | `act` is open, merge, park, drop, bring-back or tap. Open, merge, park, drop: CA, SP, AN (open question). Tap: any of the six, once each | 21 |
| 62 | GET `/api/intents/{intent_id}/glossary-start` | six | O (Initiative start and Define) | 22, 29 |
| 63 | GET `/api/intents/{intent_id}/wall` | six | O, P (resolves the wall session id) | 23 |
| 64 | GET `/api/intents/{intent_id}/cards` | six | Content readers | 24 |
| 65 | GET `/api/intents/{intent_id}/cards/{card_id}` | six | Content readers; anonymous and sealed per v1 | 24 |
| 66 | POST `/api/intents/{intent_id}/cards` | six | O, P | 24 |
| 67 | PATCH `/api/intents/{intent_id}/cards/{card_id}` | six | The author; the organiser may move or group only | 24 |
| 68 | POST `/api/intents/{intent_id}/cards/{card_id}/withdraw` | six | The author | 24 |
| 69 | POST `/api/intents/{intent_id}/cards/{card_id}/move` | six | O; the author for their own card | 24 |
| 70 | POST `/api/intents/{intent_id}/cards/{card_id}/replies` | six | O, P | 36 |
| 71 | GET `/api/intents/{intent_id}/session` | six | O, P (polled every three seconds); F and B read where content is open to them | 36 |
| 72 | POST `/api/intents/{intent_id}/session/open` | six | O | 36 |
| 73 | POST `/api/intents/{intent_id}/session/{act}` | six | O. `act` is pause, resume, phase or close | 36 |
| 74 | POST `/api/intents/{intent_id}/session/group` | six | O (North groups when the organiser asks) | 36 |
| 75 | GET `/api/intents/{intent_id}/converge` | six | O, P; B reads | 37 |
| 76 | POST `/api/intents/{intent_id}/converge/open` | six | O | 37 |
| 77 | POST `/api/intents/{intent_id}/converge/back` | six | P only, never B; at most three; refused when closed | 37 |
| 78 | POST `/api/intents/{intent_id}/converge/close` | six | O | 37 |
| 79 | POST `/api/intents/{intent_id}/converge/round2` | six | O | 37 |
| 80 | POST `/api/intents/{intent_id}/outcome/draft` | six | O | 37 |
| 81 | PUT `/api/intents/{intent_id}/outcome` | six | O | 37 |
| 82 | POST `/api/intents/{intent_id}/outcome/confirm` | six | O | 37 |
| 83 | POST `/api/intents/{intent_id}/late-thoughts` | six | P; refused when frozen | 37 |
| 84 | PUT `/api/intents/{intent_id}/series` | six | O | 38 |
| 85 | POST `/api/intents/{intent_id}/series/{act}` | six | O. `act` is pause, resume or end | 38 |
| 86 | GET `/api/intents/{intent_id}/weeks` | six | O, P; F when content is open to them | 38, 40 |
| 87 | GET `/api/intents/{intent_id}/weeks/{week_key}` | six | As the intent's content rule; 40 spells the key `week_of` | 40 |
| 88 | GET `/api/intents/{intent_id}/weeks/{week_key}/mine` | six | P, own items | 40 |
| 89 | POST `/api/intents/{intent_id}/weeks/{week_key}/answers` | six | P | 38 |
| 90 | POST `/api/intents/{intent_id}/weeks/{week_key}/items/{item_id}/fate` | six | O (fate and reason) | 38, 40 |
| 91 | POST `/api/intents/{intent_id}/weeks/{week_key}/digest` | six | North, as the organiser; refused for a person | 40 |
| 92 | POST `/api/intents/{intent_id}/weeks/{week_key}/session` | six | O. start, extend, end | 40 |
| 93 | POST `/api/intents/{intent_id}/weeks/{week_key}/close` | six | O (the closer) | 38, 40 |
| 94 | GET `/api/intents/{intent_id}/trends` | six | O, P | 40 |
| 95 | GET `/api/intents/{intent_id}/pulse/entry` | six | P. Weekly check-in entry; 39 uses `pulse` in the path, the record key stays `pulse` | 39 |
| 96 | PUT `/api/intents/{intent_id}/pulse/entry` | six | P, own entry | 39 |
| 97 | POST `/api/intents/{intent_id}/pulse/entry/submit` | six | P, own entry | 39 |
| 98 | GET `/api/intents/{intent_id}/pulse/prefill` | six | P, own | 39 |
| 99 | GET `/api/intents/{intent_id}/pulse/mine` | six | P, own | 39 |
| 100 | GET `/api/intents/{intent_id}/pulse/record` | six | O | 39 |
| 101 | GET `/api/intents/{intent_id}/notes` | six | O, D, P; anonymous per v1 | 42, 43 |
| 102 | POST `/api/intents/{intent_id}/notes` | six | O, P; F per 47. One route, one rule (open question) | 42, 43, 47 |
| 103 | POST `/api/intents/{intent_id}/notes/{note_id}/decide` | six | The decider D | 43 |
| 104 | POST `/api/intents/{intent_id}/notes/{note_id}/seen` | six | O | 47 |
| 105 | POST `/api/intents/{intent_id}/notes/{note_id}/reply` | six | O | 47 |
| 106 | POST `/api/intents/{intent_id}/problem/cause` | six | The problem owner D, or O | 42 |
| 107 | POST `/api/intents/{intent_id}/problem/fix` | six | The problem owner D, or O | 42 |
| 108 | POST `/api/intents/{intent_id}/problem/confirm-tap` | six | P or F, one tap each | 42 |
| 109 | POST `/api/intents/{intent_id}/problem/reopen` | six | O or D | 42 |
| 110 | POST `/api/intents/{intent_id}/problem/to-initiative` | six | O or D; the new organiser must hold the organiser capability | 42 |
| 111 | POST `/api/intents/{intent_id}/options` | six | O, P | 43 |
| 112 | POST `/api/intents/{intent_id}/options/{option_id}/notes` | six | O, P; never B | 43 |
| 113 | POST `/api/intents/{intent_id}/decide` | six | The decider D only (choose, later, none) | 43 |
| 114 | PUT `/api/intents/{intent_id}/affected-access` | six | O. `{read_content}`; default off | 47 |
| 115 | POST `/api/intents/{intent_id}/feel` | six | F, P; never B | 47 |
| 116 | DELETE `/api/intents/{intent_id}/feel` | six | F, P, own | 47 |
| 117 | POST `/api/intents/{intent_id}/join-requests` | six | F, M | 47 |
| 118 | POST `/api/intents/{intent_id}/join-requests/{request_id}/answer` | six | O | 47 |
| 119 | POST `/api/intents/{intent_id}/join-requests/{request_id}/withdraw` | six | The person who asked | 47 |
| 120 | POST `/api/intents/{intent_id}/follow` | six | F, B | 47 |
| 121 | PUT `/api/intents/{intent_id}/build-team` | six | O or D | 33 |
| 122 | PUT `/api/intents/{intent_id}/build-needed` | six | O or D, with a reason | 33 |
| 123 | GET `/api/intents/{intent_id}/build-ready` | six | O, D, P | 33 |
| 124 | GET `/api/intents/{intent_id}/processes` | six | Content readers, cut to the viewer's tier | 27 |
| 125 | POST `/api/intents/{intent_id}/processes` | six | O (organiser capability) | 27 |
| 126 | POST `/api/intents/{intent_id}/processes/draft` | six | O. Lens runs as the caller | 27, 44 |
| 127 | PATCH `/api/intents/{intent_id}/processes/{process_id}` | six | O | 27 |
| 128 | POST `/api/intents/{intent_id}/processes/{process_id}/confirm` | six | The named business owner of the process only | 27, 31 |
| 129 | POST `/api/intents/{intent_id}/processes/{process_id}/handover` | six | The named business owner ("not mine") | 27 |
| 130 | DELETE `/api/intents/{intent_id}/processes/{process_id}` | six | O; soft remove with a reason | 27 |
| 131 | POST `/api/intents/{intent_id}/process-questions/{question_id}/answer` | six | The person asked; at most three open questions per person across Define (A-045) | 27 |
| 132 | GET `/api/intents/{intent_id}/processes/charter-page` | six | Content readers | 27 |
| 133 | GET `/api/intents/settings` | CA | None. Company admin only (48 names `/api/company/intent-settings`) | 48 |
| 134 | PUT `/api/intents/settings` | CA | None. Company admin only. Holds `titles_private`, `affected_may_read` default per type, time boxes | 48 |
| 135 | GET `/api/control/intents/summary` | SA | Existence counts per company, read through the kernel; no title when `titles_private` | 48 |
| 136 | POST `/api/modules/m1_intent/approver/closure` | six | `guest: true, entry: true`. Approver link token, read only | 09 |
| 137 | POST `/api/modules/m1_intent/approver/decision` | six | `guest: true, entry: true`. Approver decision by token, the one guest write, kept from the charter flow | 09 |

Why route 27 sits under `/api/modules/m1_intent/`: `permissions.py` `_check_guest` allows a guest or entry route only as a plain HTTP route under `/api/modules/<module>/` with the participant role. The token travels in the POST body, as the approver routes do. No other `/api/intents` route may be marked guest.

Spellings found in other files and not adopted (ruling 1): `/api/centre/...`, `/api/intent/backlog/...`, `/api/company/intents/...`, `/api/intent-centre/...`, `/api/intents/<id>/people/<person>/...` with angle brackets (the same routes, written with braces above), and the wall, roles and Define module routes `/api/modules/m1_intent/sessions/...` which stay as they are.

### Existing routes whose behaviour changes (yaml line stays as it is)

| Group | Today | Added per-intent rule |
|---|---|---|
| `GET/POST/PUT /api/modules/m1_intent/sessions/...` (wall, room, board, together, charter) | organiser trio plus seat holders | If the session is the Initiative's wall (`intent.stages[0]` points at it), the caller must also pass layer 2 as O (trio routes) or P (seat routes). A seat the organiser gives always wins for that session |
| `GET /api/modules/m2_baseline/baselines/{baseline_id}/...` | roles per route, unchanged | If the baseline belongs to an intent, X, M and a closed-content F never reach content through it; roles unchanged for named people |
| `GET /api/pulse` | all six | Nira's intent lines list only intents where the caller is O, D, P, F or B, or an intent that needs their act. Drafts of others never appear |
| `GET /api/company/outcomes` | five roles | Unchanged. Intent outcomes appear only if closed and the caller passes route 6 |
| `/api/company/build/*`, and the Moment of truth routes `/api/modules/m3_connect/...` | analyst, company admin (acts: sponsor, approver, owner) | Unchanged. The page moves to `/centre/build/gap-analysis?from=<id>` (ruling 10); an Initiative hand-off gives the analyst the charter reference, not membership of the intent |
| All other existing routes | see yaml | Unchanged |

## Agent behaviour (North, Lens, Nira: what each drafts, when, and the moment a person acts)

- **North** drafts: refused-state hints ("Ask Janet to add you") from the organiser name in the record, and the nudge to a closer who has not yet acted. It reads an intent only for the person it is working for. A person acts: names, removes, shares, confirms.
- **Lens** drafts definitions only inside an Initiative the caller is O or P in. Its drafts are written to the intent's records, not to the caller's account.
- **Nira** builds Pulse lines from `access` results: a line appears only if layer 2 passes for that person today.
- No agent may mint, widen or revoke a share token, add a person to an intent, or switch "affected people may read".

## Rules (visibility, time box, who may do what)

1. **Default deny.** Every route in the table is declared in the yaml. An undeclared route returns 403 for everyone.
2. **Role check does not decide content.** The six company roles are all allowed on `/api/intents/*` because anyone in the company may start something and see their areas. Layer 2 decides content. A handler that skips layer 2 fails `test_intent_access.py` (below).
3. **Per-intent role** is computed, in this order, as a set: creator of a draft (the only reader of a draft), organiser (`people.organiser`), closer (sponsor, decider or problem owner: the named closer), participant (a reporter counts here), affected, observer, area member (tagged by `areas` in the profile, not named), company admin (company role), share visitor (route 27 only), super admin (rows 28 and the summary only).
4. **Affected and observer (ruling 4).** An affected person sees existence, title, purpose, stage, clock, people, and the outcome once closed. Content opens only when the organiser switched "affected people may read" on at creation (default off) or the person is named on a share. An observer reads what a participant reads and never writes or votes. Area members and company admin see the existence view: title, purpose, stage, organiser, and the outcome once closed. Company admin never sees anonymous notes. Sealed and anonymous material keep the v1 rules (D-013, seal).
5. **Contribute** (route 15): organiser and participant; nobody after `closed`. Affected people have their own small writes (feel, notes, join requests, follow; rows 107 to 123) that never open the content. Observer never writes.
6. **Confirm closure** (ruling 25): the per-type closer acts, then the organiser closes. Closers are sponsor (Initiative), decider (Decision), owner then reporter (Problem); for Brainstorm and Weekly check-in, nobody (organiser acts directly). A role in the company table does not stand in for the named person, except that `company_admin` may act for the sponsor on `handoff` of an Initiative, as the yaml already lets `company_admin` act for the sponsor on charter sign and baseline settle.
7. **Initiative organiser** needs the existing organiser capability (A-025: company_admin, sponsor, analyst) because the wall and Define routes stay organiser-only. Participant, owner and approver may start the other four types. See Open questions.
8. **Super admin (ruling 5)** has no company; routes under `/api/intents` refuse. Row 28 and the Control summary return existence only, built by one projection function with a test that its keys are exactly the nine named in row 28 (eight when `titles_private` is on). The company switch `titles_private` (default off) removes titles from that view; only the company admin sets it. Request A-074 asks Nitin to let the super admin read intent existence through the kernel; the control plane still stores no company data. Drafts never appear.
9. **Drafts and cancellation (ruling 14).** A draft is visible only to the person who started it: lists, Pulse lines, counts, the super admin view and the company admin view all leave it out, and any other caller gets 404. A cancelled intent keeps its reason and is shown in Past to everyone who could see it before.
10. **Share link**: read only, per named person, expiry set by the organiser, revocable. A visitor sees what was done, what was said, who said it (unless anonymous) and what came out. Never another intent, never the people list's contact details.
11. **Module gate.** `ModuleGate` today judges only `/api/modules/<id>/...`. Add a one-line prefix table, `{"/api/modules/": segment, "/api/intents": "m1_intent"}`, so a company without `m1_intent` gets `module_not_available` on `/api/intents/*` before any role is read. Row 27 is already covered.
12. **No existence leak.** A person with no per-intent role and no area tag gets 404 `intent_not_found`, the same as an id that does not exist.
13. **Role change mid-session.** The next call re-reads the roles; a cached page shows the refused panel after its next request.
14. **Numbers (ruling 8).** Counts are exact. Means, medians and any per-person figure show "Fewer than five" below five records. Ratings aggregate from three. No per-person average exists (ruling 15).

### The yaml block to append (default deny, same style as `route_permissions.yaml`)

```yaml
  # ---- Intent Centre v2 (spec 14). All six company roles pass the role check; the handler's per-intent check does the rest.
  GET /api/intents/types: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  GET /api/intents/areas: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  GET /api/intents/people: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  GET /api/intents: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  POST /api/intents: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  GET /api/intents/{intent_id}: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  PUT /api/intents/{intent_id}: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  POST /api/intents/{intent_id}/open: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  PUT /api/intents/{intent_id}/people: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  POST /api/intents/{intent_id}/stages/{stage_key}/open: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  POST /api/intents/{intent_id}/stages/{stage_key}/close: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  POST /api/intents/{intent_id}/extend: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  POST /api/intents/{intent_id}/cancel: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  GET /api/intents/{intent_id}/content: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  POST /api/intents/{intent_id}/contributions: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  GET /api/intents/{intent_id}/closure: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  PUT /api/intents/{intent_id}/closure: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  POST /api/intents/{intent_id}/closure/confirm: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  POST /api/intents/{intent_id}/ratings: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  POST /api/intents/{intent_id}/next: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  POST /api/intents/{intent_id}/build-ready/check: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  POST /api/intents/{intent_id}/handoff: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  GET /api/intents/{intent_id}/share: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  POST /api/intents/{intent_id}/share: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  DELETE /api/intents/{intent_id}/share/{token_id}: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  POST /api/modules/m1_intent/shared/view: {roles: [participant, owner, company_admin, sponsor, analyst, approver], guest: true, entry: true}
  GET /api/control/companies/{company_id}/intents: {roles: [super_admin]}
  PUT /api/intents/{intent_id}/state: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  GET /api/intents/{intent_id}/people: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  POST /api/intents/{intent_id}/people: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  POST /api/intents/{intent_id}/people/{person_id}/answer: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  POST /api/intents/{intent_id}/people/{person_id}/role: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  POST /api/intents/{intent_id}/people/{person_id}/remove: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  GET /api/intents/{intent_id}/clock: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  POST /api/intents/{intent_id}/extend/{n}/decide: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  GET /api/intents/{intent_id}/north: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  POST /api/intents/{intent_id}/north/turns: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  POST /api/intents/{intent_id}/north/drafts/{draft_id}/confirm: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  POST /api/intents/{intent_id}/north/drafts/{draft_id}/discard: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  POST /api/intents/{intent_id}/north/proposals/{draft_id}/pick: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  POST /api/intents/{intent_id}/north/clock-check: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  GET /api/intents/{intent_id}/ratings: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  POST /api/intents/{intent_id}/rating/waive: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  POST /api/intents/{intent_id}/outcome-used: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  GET /api/intents/{intent_id}/chain: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  POST /api/intents/{intent_id}/history-notes: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  POST /api/intents/{intent_id}/share-request: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  GET /api/intents/{intent_id}/transcript/download: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  GET /api/intents/{intent_id}/events: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  GET /api/intents/measures: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  GET /api/intents/home: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  GET /api/intents/waiting: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  GET /api/intents/{intent_id}/who-has-not-acted: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  POST /api/intents/{intent_id}/nudge/{person_id}: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  POST /api/intents/{intent_id}/links/proposal: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  POST /api/intents/{intent_id}/links: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  POST /api/intents/{intent_id}/links/{link_id}/checked: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  GET /api/intents/backlog: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  GET /api/intents/backlog/{item_id}: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  PATCH /api/intents/backlog/{item_id}: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  POST /api/intents/backlog/{item_id}/{act}: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  GET /api/intents/{intent_id}/glossary-start: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  GET /api/intents/{intent_id}/wall: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  GET /api/intents/{intent_id}/cards: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  GET /api/intents/{intent_id}/cards/{card_id}: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  POST /api/intents/{intent_id}/cards: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  PATCH /api/intents/{intent_id}/cards/{card_id}: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  POST /api/intents/{intent_id}/cards/{card_id}/withdraw: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  POST /api/intents/{intent_id}/cards/{card_id}/move: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  POST /api/intents/{intent_id}/cards/{card_id}/replies: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  GET /api/intents/{intent_id}/session: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  POST /api/intents/{intent_id}/session/open: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  POST /api/intents/{intent_id}/session/{act}: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  POST /api/intents/{intent_id}/session/group: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  GET /api/intents/{intent_id}/converge: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  POST /api/intents/{intent_id}/converge/open: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  POST /api/intents/{intent_id}/converge/back: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  POST /api/intents/{intent_id}/converge/close: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  POST /api/intents/{intent_id}/converge/round2: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  POST /api/intents/{intent_id}/outcome/draft: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  PUT /api/intents/{intent_id}/outcome: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  POST /api/intents/{intent_id}/outcome/confirm: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  POST /api/intents/{intent_id}/late-thoughts: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  PUT /api/intents/{intent_id}/series: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  POST /api/intents/{intent_id}/series/{act}: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  GET /api/intents/{intent_id}/weeks: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  GET /api/intents/{intent_id}/weeks/{week_key}: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  GET /api/intents/{intent_id}/weeks/{week_key}/mine: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  POST /api/intents/{intent_id}/weeks/{week_key}/answers: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  POST /api/intents/{intent_id}/weeks/{week_key}/items/{item_id}/fate: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  POST /api/intents/{intent_id}/weeks/{week_key}/digest: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  POST /api/intents/{intent_id}/weeks/{week_key}/session: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  POST /api/intents/{intent_id}/weeks/{week_key}/close: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  GET /api/intents/{intent_id}/trends: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  GET /api/intents/{intent_id}/pulse/entry: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  PUT /api/intents/{intent_id}/pulse/entry: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  POST /api/intents/{intent_id}/pulse/entry/submit: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  GET /api/intents/{intent_id}/pulse/prefill: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  GET /api/intents/{intent_id}/pulse/mine: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  GET /api/intents/{intent_id}/pulse/record: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  GET /api/intents/{intent_id}/notes: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  POST /api/intents/{intent_id}/notes: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  POST /api/intents/{intent_id}/notes/{note_id}/decide: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  POST /api/intents/{intent_id}/notes/{note_id}/seen: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  POST /api/intents/{intent_id}/notes/{note_id}/reply: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  POST /api/intents/{intent_id}/problem/cause: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  POST /api/intents/{intent_id}/problem/fix: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  POST /api/intents/{intent_id}/problem/confirm-tap: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  POST /api/intents/{intent_id}/problem/reopen: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  POST /api/intents/{intent_id}/problem/to-initiative: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  POST /api/intents/{intent_id}/options: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  POST /api/intents/{intent_id}/options/{option_id}/notes: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  POST /api/intents/{intent_id}/decide: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  PUT /api/intents/{intent_id}/affected-access: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  POST /api/intents/{intent_id}/feel: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  DELETE /api/intents/{intent_id}/feel: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  POST /api/intents/{intent_id}/join-requests: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  POST /api/intents/{intent_id}/join-requests/{request_id}/answer: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  POST /api/intents/{intent_id}/join-requests/{request_id}/withdraw: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  POST /api/intents/{intent_id}/follow: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  PUT /api/intents/{intent_id}/build-team: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  PUT /api/intents/{intent_id}/build-needed: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  GET /api/intents/{intent_id}/build-ready: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  GET /api/intents/{intent_id}/processes: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  POST /api/intents/{intent_id}/processes: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  POST /api/intents/{intent_id}/processes/draft: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  PATCH /api/intents/{intent_id}/processes/{process_id}: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  POST /api/intents/{intent_id}/processes/{process_id}/confirm: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  POST /api/intents/{intent_id}/processes/{process_id}/handover: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  DELETE /api/intents/{intent_id}/processes/{process_id}: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  POST /api/intents/{intent_id}/process-questions/{question_id}/answer: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  GET /api/intents/{intent_id}/processes/charter-page: {roles: [participant, owner, company_admin, sponsor, analyst, approver]}
  GET /api/intents/settings: {roles: [company_admin]}
  PUT /api/intents/settings: {roles: [company_admin]}
  GET /api/control/intents/summary: {roles: [super_admin]}
  POST /api/modules/m1_intent/approver/closure: {roles: [participant, owner, company_admin, sponsor, analyst, approver], guest: true, entry: true}
  POST /api/modules/m1_intent/approver/decision: {roles: [participant, owner, company_admin, sponsor, analyst, approver], guest: true, entry: true}
```

### Per-intent role against action (layer 2)

Reporter counts as participant. "Closer" is the sponsor (Initiative), organiser (Brainstorm, Weekly check-in), owner (Problem) or decider (Decision).

| Action | Organiser | Closer | Participant | Affected | Observer | Area member | Company admin | Share visitor | Super admin |
|---|---|---|---|---|---|---|---|---|---|
| See that it exists (title, purpose, stage, organiser) | Y | Y | Y | Y | Y | Y | Y | named only | Y (existence keys only) |
| See the clock and the people | Y | Y | Y | Y | Y | - | - | - | - |
| See the outcome once closed | Y | Y | Y | Y | Y | Y | Y | Y | - |
| Open the content | Y | Y | Y | only when switched on, or named on a share | Y | - | - | Y (read) | - |
| See a draft | creator only | creator only | - | - | - | - | - | - | - |
| See anonymous notes | v1 rule | v1 rule | v1 rule | v1 rule when open | v1 rule | - | never | never | - |
| Add a card, idea, answer, evidence | Y | if also participant | Y | Problem evidence (open question) | - | - | - | - | - |
| Feel, note, ask to join, follow | - | - | feel only | Y | follow only | join request only | - | - | - |
| Edit title, purpose, areas, people, "affected may read" | Y | - | - | - | - | - | - | - | - |
| Open or close a stage | Y | build_ready only | - | - | - | - | - | - | - |
| Extend the time box | Y | decides a second extension | - | - | - | - | - | - | - |
| Cancel | Y (not Initiative) | Y (Initiative) | - | - | - | - | - | - | - |
| Confirm the closure | if also closer | Y | - | - | - | - | - | - | - |
| Rate | - | if also participant | Y | - | - | - | - | - | - |
| Share, revoke | Y | - | - | - | - | - | - | - | - |
| Start a linked intent | Y | Y | - | - | - | - | - | - | - |
| Hand to Build | - | Y (sponsor) | - | - | - | - | Y for the sponsor | - | - |
| Set `titles_private` | - | - | - | - | - | - | Y | - | never |

## Error copy

| Where | Cause | Words shown |
|---|---|---|
| Guard 403 (any route or page) | Role not in the yaml line | "You do not have access to this. Ask your administrator." (existing `copy.ts` `noAccess`; the API body keeps "You do not have access to this.") |
| Module not owned | `module_not_available` | "This module is not part of your plan." (existing) |
| Existence view only, content asked | Area member, company admin, or affected with the switch off, on route 14 | "You can see that this exists. You can open it if the organiser adds you. Organiser: {name}." Code `intent_content_closed` (403) |
| No role, no area; or someone else's draft | 404 | "We could not find that." Code `intent_not_found` |
| Action not for your role in this intent | e.g. observer contributes | "You can read this intent but not change it." Code `intent_read_only` (403) |
| Not the named closer | Route 19 | "Only {name} can close this. North has told them it is waiting." Code `intent_not_your_close` (403) |
| Closed or cancelled | Any write | "This intent is closed. It is kept as it was and cannot be changed." Code `intent_closed` (409) |
| Initiative by a non-organiser role | Route 5 | "An Initiative runs the wall, which needs an organiser. Ask your company admin, or start a Brainstorm, Problem or Decision." Code `initiative_needs_organiser` (403) |
| Share link not open | Route 27: unknown, expired, revoked | "This link is not open. Ask the person who sent it for a new one." Code `share_not_open` (403), same body for all three causes |
| Super admin on a company page | `/centre/intent*` | Redirect to `/centre/control`, no message |
| Anonymous author asked | Company admin | The note shows "Anonymous". No error |

Per-intent refusals use codes other than `forbidden` and `module_not_available`, so `test_role_matrix.py` (which counts only the guard's 403) never mistakes a handler refusal for a guard one.

## Counters and measures of this feature (numbers only, each traced to a record)

- Refused per-intent calls per code and week: count of run log lines of kind `intent_refused`. "Not available yet" when the log has none.
- Share tokens live, expired, revoked: count of `intents/<id>/intent.json` `share.who_may_open` by state.
- Intents visible to a company admin but not opened by them: not counted (would need per-person reading history; not stored).

## Reuse check (what exists today: file paths and line ranges found with graft; copied, reshaped or not used, and why)

Searches run: `Read` of `sh_platform/route_permissions.yaml` (340 lines), `modulegate.py` (176), `auth/permissions.py` (lines 40 to 80, the guest rule), `auth/guest.py` (25 to 75), `entitlements.py` (symbol list), `ui/src/shell/roles.ts` (the table), `tests/auth/test_role_matrix.py` (172) and `test_role_table.py` (100), `docs/plan/QUALITY-PASS.md` section 1 (lines 23 to 32), and `ui/src/App.tsx` lines 105 to 143. Paths re-checked on 7 October 2026 with `ls`: all exist. Route names were gathered with `grep -E "/api/intents|/centre/intent"` over `docs/specs/intent-centre/*.md`.

| Existing | Decision |
|---|---|
| `sh_platform/route_permissions.yaml` default deny, `roles`, `guest`, `entry` | Reused as is; the lines below are appended in its own style |
| `sh_platform/modulegate.py` `ModuleGate`, `may_use_module` (lines 36 to 100) | Reshaped: one prefix table so `/api/intents` is gated as `m1_intent`. No new gate |
| `sh_platform/entitlements.py` `EntitlementStore.is_enabled` | Reused through `may_use_module`; not changed |
| `sh_platform/auth/permissions.py` `_check_guest` | Not changed; it forces the share route under `/api/modules/m1_intent/` |
| `sh_platform/auth/guest.py` seat-token guests | Not used for share visitors: a share token names a person and travels in the body, like the approver routes |
| `ui/src/shell/roles.ts` role table (lines 8 to 17) and `RoleGate` | Reused; four rows gain `intent` |
| `sh_platform/profile/view.py` `Viewer`, `sees_area`, `allows` | Reused for the area-member test and the per-viewer list filter |
| `sh_platform/profile/store.py`, `sh_platform/jsonfile.py` | Reused for people and areas and for the one-file-per-intent read |
| `docs/plan/QUALITY-PASS.md` section 1 role table | Reshaped through the new top bar table; needs Nitin's confirmation |
| `GUARD_403`, `ACTS`, `expected()` in `tests/auth/test_role_matrix.py` | Extended, below |

Genuinely new: the per-intent role function `intent_access`, the routes above, the share token fields, the `affected_may_read` check and the refusal codes.

### Tests to extend and add

`tests/auth/test_role_table.py`:
- `CENTRE_ROUTES["intent"] = ("/api/intents",)`, so `test_centre_routes_agree_with_the_table` checks that every `/api/intents` line lists exactly `seers("intent")` (the six company roles). The `settings` lines list `company_admin` only, so they are listed as exceptions in that test.
- Add `"POST /api/modules/m1_intent/shared/view"` to `ACTS` with the six roles (it carries `guest`), and keep `test_super_admin_reads_no_company_centre` covering `/api/intents`.
- New `test_build_stays_data_team`: `seers("build") == {"analyst", "company_admin"}`.
- New `test_everyone_but_the_super_admin_sees_intent`: `seers("intent") == set(PERMS.roles) - {"super_admin"}`.
- New `test_intent_routes_have_no_guest_except_the_share_view`: only the share view and the two approver routes have `guest`, among keys containing `intent` or `approver`.
- `test_bar_order_and_landing` stays as it is (order already holds `intent` second).

`tests/auth/test_role_matrix.py`:
- `INTENTS = ("/api/intents",)`; in `expected()`, before the `MODULES` branch: `if under(path, INTENTS): return role != "super_admin"` (with `settings` as company admin only).
- Add to `ACTS`: `"GET /api/control/companies/{company_id}/intents": {"super_admin"}`, `"GET /api/control/intents/summary": {"super_admin"}` and `"POST /api/modules/m1_intent/shared/view": ROLES minus super_admin`.
- `NO_COMPANY_OK` is unchanged: `/api/control` is already in it.
- The matrix runs the routes with `x` ids; handler refusals use the new codes, so only guard refusals count as denied.

New `tests/intents/test_intent_access.py` (synthetic Ardmore data: Janet organiser, Daniel sponsor, Katie analyst, Aaron participant, Harvey owner, Grace approver):
- For each route and each per-intent role: the table above, row by row (parametrised from one dict, not hand-written).
- Area member gets the existence view and `intent_content_closed` on route 14; so does an affected person while the switch is off, and the same person reads once it is on; an observer reads and every observer write is `intent_read_only`.
- A draft: its creator reads it, the organiser-by-name and the company admin get 404, the super admin projection leaves it out.
- A cancelled intent appears in Past with its reason.
- Company admin never gets anonymous notes; a stranger gets 404 identical to a missing id.
- Super admin projection has exactly the keys of row 28; with `titles_private` on, `title` is absent; another company's intent id is unreachable.
- Share: revoked, expired and unknown tokens give the same body; a token for intent A never opens intent B; no write route accepts a token except the approver decision.
- Module off: `/api/intents/*` returns `module_not_available` before any role check.
- Closed intent: every write route returns `intent_closed`.
- Roles removed mid-session: the next call is refused.

## Not in this feature

- Any screen other than the refused panel and the section links, and any route's body shape (each owning spec).
- Changing roles in the UI, or a new role such as head of data (the table says it does not exist yet).
- The Moment of truth and Build permissions (unchanged).
- Per-person reading history (who opened what).
- Editing permissions per company; the table is fixed for all companies.

## Open questions

1. QUALITY-PASS section 1 says owner and approver never see Intent except by invite. The task for this round says everyone sees the centre. This file assumes the new table; Nitin to confirm and update that file.
2. Initiative organiser: the wall and Define routes are organiser-only (A-025). Default here: only company_admin, sponsor and analyst may start an Initiative. Alternative: widen the wall routes to any intent organiser. Which?
3. Request A-074 (ruling 5): the super admin may read intent existence through the kernel. Is the key list in row 28 right, in particular `id` and `time_box_status`? The earlier five-key list is replaced.
4. Share token expiry: the organiser picks a date and none is enforced. Is a maximum wanted?
5. May `company_admin` act for the named closer when that person is away? Default: only for the Initiative sponsor's hand-off and closure.
6. Who is "in an area"? This file reads the profile's person and area records via the account link (LI-LINK). A company with no linked accounts gives no area members; confirm this is acceptable for the demo.
7. Methods and duplicates between files, to be settled by their owners: 01 says PATCH for edit (here PUT); `close` and `closure/confirm`; `north/ask` and `north/turns`; `build-ready/check` and `build-ready/recheck`; `nudge` and `nudge/{person_id}`; people PUT (whole list) and POST (add by pick); weeks routes of 38 and 40 and the `pulse/*` routes of 39 (ruling 3 says "Pulse" alone means the daily page, so 39's path word should change); `notes` for 42, 43 and 47.
8. Routes found that ruling 1 does not list and so wait for a decision: `/centre/intent/shared/:token` (11), `/centre/intent/map/:id` (12), `/centre/intent/charter/<id>` and `/centre/intent/i/...` spellings (wrong, to be corrected), `/centre/intent/<id>/{ideas, room, options, triage, record, series, trends, roles, decide, notes, invitation, affected}` (views outside the twelve of ruling 1; 36, 37, 38, 41, 43 and 47 should fold them into the twelve or ask for more), and `/centre/intents/<id>/...` (typo for `/centre/intent/`).
9. Visitor notes: 11 wants a share visitor to write notes (`shared/note`) and the organiser to mark them read. The brief says a share is read only and this file refuses writes by token (the approver decision is the one kept exception). Not added until Nitin rules.
10. May an affected person add evidence to a Problem (route 15) when content is closed to them? Ruling 4 gives content on the switch only; evidence is a write, so default kept as "open question, off".
11. Who may read the transcript and events (rows for `events` and `transcript/download`)? Default: organiser and closer.
12. Backlog acts (row `backlog/{item_id}/{act}`): default open, merge, park, drop by company admin, sponsor and analyst; tap by anyone. The brief gives no rule for backlog rights.
13. A named business owner confirming a process (row `processes/{process_id}/confirm`) may not be a participant of the intent. Default: the named owner reads and confirms their own process rows only.
14. Request A-075 (ruling 10) amends BUILD-CENTRE-SPEC.md for gap analysis; not applied here.
15. Draft visibility (ruling 14): if the creator and the organiser differ, only the creator sees the draft until it opens. Confirm this is wanted for drafts started on behalf of someone.
