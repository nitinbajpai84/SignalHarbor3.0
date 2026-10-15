# 05. Areas and visibility

Part of: Intent Centre v2. Depends on: 00-BRIEF (the intent record, section 4 visibility). Feeds: every file that shows, lists, shares or reads an intent.

## Purpose (three sentences)

An area is a department or operations area, kept as a tag on intents and on people. The tag decides who learns an intent exists and what they may open, by one table applied in one place (`sh_platform/profile/view.py`), so no screen, route or agent decides visibility for itself. A person who is not in an intent's areas, and not named in it, cannot tell it exists, and a draft is seen by the person who started it and nobody else.

## Who uses it and when (role, moment, trigger)

| Role | Moment | Trigger |
|---|---|---|
| Company admin | Set-up, then when people join, move or leave | Opens Company areas, accepts suggestions, tags people |
| Organiser (Janet) | Creating an intent, or changing who it touches | The area picker in the start flow; "Change areas" on an intent |
| Anyone tagged to an area | Wanting to know what the company is working on in their area | The Intents in your areas list; Pulse lines from Nira |
| Participant, observer, sponsor | Opening an intent they are in | Intent page; the filter returns their full view |
| Affected person | Seeing what touches them | Intent page; the filter returns existence, title, purpose, stage, clock, people and outcome, and content only when the organiser allows it |
| Super admin | Checking that intents exist for a company, never reading them | `/centre/control/intents` (existence, read through the kernel on request) |
| Share-link visitor | Opening what an organiser named them for | The link, signed in as a named person |

## Entry points (every route, link, Pulse line, button that leads here)

- Settings, Company areas (company admin only): `/company/settings/areas`.
- Settings, People and areas: `/company/settings/areas/people`.
- Area picker: inside the start flow of every intent type (field "Who is this about?") and on the intent page, button "Change areas" (organiser only).
- Intents in your areas: `/centre/intent` (home, with the list and filters). Whether roles whose role table has no Intent centre reach it is an Open question.
- Past intents, cancelled ones with their reason: `/centre/intent/past`.
- Pulse line from Nira: "3 intents are running in Finance" opens `/centre/intent?area=finance`.
- Share link: opens `/centre/intent/<id>/share`; the page sends the token to `POST /api/modules/m1_intent/shared/view` (the guest entry of ruling 1). How the token rides in the link is an Open question.
- Super admin: `/centre/control/intents`.
- Company admin privacy switch: on Company areas (Screen A), "Keep intent titles private to the company".
- Nira line to the company admin: "4 people have no area yet" opens People and areas filtered to untagged.

## Screens, element by element

### Screen A. Company areas

Route `/company/settings/areas`. At 1280: left, the company's areas as a table; right, a panel "Suggested for a family office" (from the pack). At 390: the panel drops below the table, table rows become cards, buttons stay full width.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Areas table | list | Name, kind (Department or Operations area), people tagged (count of `people.*.areas` in the profile), intents (count, `total` of `GET /api/intents` per area for this viewer), status. Without a people file the people cell reads "Not available yet: no people file read" | Row click opens the row editor | Company admin | "No areas yet. Add one, or accept the suggestions." |
| Add area | button | A name field and a kind select | Writes one area; refuses a name that matches an existing one when spaces and case are ignored | Company admin | n/a |
| Rename | button (row) | Name field | Changes the name only; the id stays, so past intents keep matching | Company admin | n/a |
| Retire | button (row) | Confirm: "People and past intents keep this area. It will not be offered for new intents." | Sets status retired; nothing is deleted | Company admin | n/a |
| Bring back | button (retired row) | n/a | Sets status active | Company admin | n/a |
| Suggested panel | panel | Pack areas, each with a checkbox, headed "What others in a family office usually have" and labelled "Suggestion" | None until Add selected | Company admin | Pack has none: "No suggestions for this industry yet. Add your own." |
| Add selected | button | n/a | Writes the ticked ones as company areas, marked "Accepted from suggestions" | Company admin | disabled while none ticked |
| Lens line | agent line | "Your people file lists teams not yet areas: Treasury, Reporting. Add them?" with Add and Not now | Add writes them as active areas; Not now hides the line for this list | Company admin | Hidden when no team value is missing |
| Show retired | chip | Toggle | Shows retired rows | Company admin | n/a |
| Titles private | field (switch) | "Keep intent titles private to the company", default off | Saves the company setting; when on, the super admin view omits titles (ruling 5) | Company admin | n/a |

### Screen B. People and areas

Route `/company/settings/areas/people`. At 1280: table of the company's people with an area multi-select per row. At 390: each person is a card with the select below the name.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| People table | list | Name, role, team (from the profile), account link state, areas | Row click focuses the select | Company admin | "No people in the profile yet. Bring what you have first." with a link to the profile page |
| Areas select | field (multi) | Active areas as chips | Change saves at once to `people.<pid>.areas`; the toast says "Janet now sees intents in Operations" | Company admin | "No area" chip, amber |
| Untagged filter | chip | Count of people with no area (`people` against `people.*.areas`) | Filters the table | Company admin | Count 0: chip reads "Everyone is tagged" |
| Lens line | agent line | "Team says Finance for Aaron. Tag him to Finance?" | Accept tags; the person's own choice of a different area is kept | Company admin | Hidden |
| Not linked note | chip | "No sign-in account linked: this person sees nothing yet" | Link opens the existing link picker (`GET /api/profile/links`) | Company admin | Hidden |

### Component C. Area picker

Used in the start flow of every type and in "Change areas". At 1280: a chip field with a dropdown and, below it, the "Who will see this" strip. At 390: the dropdown is a full-screen sheet, the strip sits under the field.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Picker field | field (multi chip) | Active company areas, searchable | Adds or removes a chip; at least one is required to continue | Organiser | Company has no areas: "Your admin has not set up areas yet." plus, for an admin, the link "Set up areas" |
| North suggestion | agent line | "Aaron and Katie are in Finance and Operations. Add both?" with Add and No | Add adds the chips; nothing is added without the click | Organiser | Hidden when no participant is named yet |
| Who will see this | panel | "People in Finance and Investments will see that this exists, its title, purpose, stage and outcome: 14 people. Only people you name open the content." With the switch below on it adds "Affected people may read it too." The count is exact, of tagged accounts (profile `people.*.areas` linked by `account_id`) | None | Organiser | "Pick an area to see how many people it reaches."; no people file: "Not available yet: no people file read" |
| Affected | field (people) | Names, from the profile | Adds to `people.affected`; they see existence, title, purpose, stage, clock, people and outcome once closed | Organiser | "Nobody affected named yet" |
| Affected people may read | field (switch) | Default off, set at creation | Sets `affected_may_read`; on lets affected people open the content (sealed and anonymous rules still apply) | Organiser | n/a |
| Change areas (existing intent) | button | n/a | Opens the picker; save shows "N more people will see this" or "N people will stop seeing this" and asks Confirm | Organiser | n/a |

### Screen D. Intents in your areas

Route `/centre/intent`. At 1280: filter row, then the list, one row per intent. At 390: rows become cards, filters become a sheet. The row set is exactly what the filter returns for this viewer, and nothing more.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Area chips | chip | Your areas; admin sees all areas | Filters by area | Everyone signed in | See "No area" below |
| Type, State | chip | Five types (Initiative, Brainstorm, Weekly check-in, Problem, Decision); open, closed | Filters | Everyone | n/a |
| Past | button | n/a | Opens `/centre/intent/past`, where closed and cancelled intents sit, cancelled ones with their reason | Everyone | "Nothing past in your areas yet." |
| Intent row | list | Type, title, purpose, stage, clock (`time_box`), organiser, areas; for closed ones the outcome. Your own drafts show marked Draft, to you alone | Opens the intent page | By matrix | "Nothing running in your areas. Anything you start will appear here." |
| Locked note | panel (on the intent page) | "You can see that this exists. You open the content only if you take part, are named in a share link, or the organiser lets affected people read." | None | Same-area people, affected people (switch off) and the company admin | Hidden for anyone with content |
| Shared with you | list | Intents shared to you by link | Opens the read-only view | Named visitors | Hidden when none |
| No area banner | panel | "You are not tagged to an area yet. You see intents you are named in. Ask your company admin." | None | A person with no area | Hidden when tagged |

### Screen E. Super admin intents (existence)

Route `/centre/control/intents`. At 1280: a company picker above one table. At 390: rows become cards, the picker is full width. Existence only, read through the kernel on request; the control plane keeps no copy (request A-074). Drafts never appear.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Company picker | field (select) | Companies | Loads that company's rows through the kernel | Super admin | "No companies yet." |
| Existence table | list | Title (omitted when the company switch "titles private" is on), type, state, areas, people count, dates, time box status | None. No row opens | Super admin | "This company has no intents yet." |
| Private title cell | chip | "Title private to the company" | None | Super admin | Hidden when titles are not private |

## User journey (numbered steps from arriving to leaving, with what the agent does between the person's steps)

1. Admin opens Company areas. The page lists nothing and shows the family office suggestions (Finance, Investments, Operations, Compliance), labelled as suggestions.
2. Admin ticks the four and clicks Add selected. Lens, having read the people file, adds a line offering Treasury, a team value no area matches. Admin clicks Not now.
3. Admin opens People and areas. Lens suggests tags from each person's team value. Admin accepts, then tags Janet to Operations, Daniel to Investments, Katie to Operations and Finance, Aaron to Finance, Harvey to Operations, Grace to Compliance.
4. Nira drops "4 people have no area" from the admin's waiting list as the count reaches zero.
5. Janet starts a Brainstorm. At "Who is this about?" North reads the named participants' tags and suggests Finance and Operations. Janet clicks Add, then reads "People in Finance and Operations will see that this exists: 9 people."
6. Janet names Katie and Aaron as participants and Harvey as affected, leaves "Affected people may read" off, then clicks Open. Until now the draft was visible to Janet alone. The intent moves from draft to open and appears in the lists of everyone tagged to Finance or Operations. Harvey sees its title, purpose, stage, clock, people and, once closed, the outcome, but not the content.
7. Grace (Compliance) opens Intents in your areas. The brainstorm is absent. She cannot learn it exists, by list or by id.
8. A Finance colleague who is not in the intent sees the row, opens it, and sees the locked note and no content.
9. The brainstorm closes. The organiser clicks Share and names Grace. Grace opens the link signed in, sees what was done and said, silhouettes for sealed cards, anonymous cards without names, and what came out.
10. Daniel, the sponsor, opens it any time and sees all content except what the seal and anonymity rules withhold.
11. Daniel clicks Back to intents and returns to `/centre/intent`, which leaves the intent.

## States and transitions (table: state, who moves it, to what, what is written)

| Subject | State | Who moves it | To | What is written |
|---|---|---|---|---|
| Area | suggested (pack, never stored) | Company admin: Add selected | active | `areas.<id>` cells: name, kind, status active, `from` "Accepted from suggestions" |
| Area | active | Company admin: Retire | retired | `areas.<id>.status`; nothing else changes |
| Area | retired | Company admin: Bring back | active | same cell |
| Person tag | none or set | Company admin | set or none | `people.<pid>.areas` cell, by admin, mark stated |
| Intent visibility | draft | Organiser opens | open | State only. From now area people see it. In draft only the person who started it (`created_by`) sees it; sponsor, company admin and super admin do not (ruling 14) |
| Intent visibility | any | Organiser: Change areas, Confirm | same state | `areas`, plus an entry in `areas_changed` |
| Intent visibility | cancelled | North proposes, a named person picks | cancelled | Follows the matrix and is listed in Past with its reason; the reason shows in the row |
| Share | none | Organiser: Share | active | `share.link` (token hash), `who_may_open`, `expires_at` |
| Share | active | Organiser: Stop sharing, or expiry | revoked | `share.revoked_at`; the link then answers "We could not find that." |

Visibility is worked out at read time from the record and the viewer. It is never stored per person, so a change to a tag or to `areas` applies at once.

## Records read and written (file or route, fields; mark Existing or New)

| Record | Fields | Mark |
|---|---|---|
| `context/profile/profile.json` (`sh_platform/profile/store.py`) | New section `areas.<id>.{name, kind, status, from}` as provenance cells; new cell `people.<pid>.areas` (list of area ids). `store.DEPTH` gains `"areas": 3`; `store.empty()` gains `"areas": {}` | Existing file, New section |
| `people.<pid>.account_id` | Link from account to person; this is how a viewer gets areas | Existing |
| `intents/<id>/intent.json` | The intent record of the brief, read only here, plus the fields below | New (written by the intent store) |
| `packs/family_office/1/areas.yaml` | `areas: [{id, name, kind, note}]`, read with `packs.load(industry).section("areas")` | New |
| `GET /api/company/areas` (path is an Open question) | Active and retired areas, id, name, kind, status (no counts) | New. All company roles |
| `POST /api/profile/areas`, `PUT /api/profile/areas/{area_id}`, `POST /api/profile/areas/{area_id}/retire`, `POST /api/profile/areas/{area_id}/restore` | Add, rename, retire, restore | New. Company admin |
| `POST /api/profile/areas/accept` | `{ids: [pack area ids]}` | New. Company admin |
| `PUT /api/profile/people/{pid}/areas` | `{areas: [ids]}` | New. Company admin, beside the existing `.../account` route |
| `GET /api/intents` | Query `area, type, state, shared, after, limit`. Returns `{items: [filtered record], total}` where `total` counts only what this viewer may see | New. All company roles |
| `GET /api/intents/{id}` | One filtered record. Not visible and not existing both answer 404 "We could not find that." | New. All company roles |
| `PUT /api/intents/{id}/areas` | `{areas, affected, affected_may_read}` | New. Organiser, checked in the handler |
| `POST /api/intents/{id}/share`, `DELETE /api/intents/{id}/share` | Create, revoke | New |
| `POST /api/modules/m1_intent/shared/view` | Visitor opens a share by token | New (file 14 owns it) |
| `GET /api/control/companies/{company_id}/intents` (path is an Open question) | Existence projection read through the kernel: title (unless private), type, state, areas, people count, dates, time box status. Nothing stored in control | New. Super admin |
| Company setting `titles_private` | Default off | New. Company admin sets, kernel reads |

## Fields this feature adds to the intent record

```
intent.areas: [area id]                       # in the brief; here: ids, not names; at least one to open
intent.areas_changed: [{by, at, from: [ids], to: [ids]}]
intent.rated_by: [account id]                 # server only; one rating per person; dropped by the filter; never joined to a score
intent.affected_may_read: bool                # default false, set at creation by the organiser
intent.share: {link: token hash|null, who_may_open: [account id], expires_at, created_by, created_at, revoked_at|null}
```

`share.link` in the brief holds the token hash here, never the token, and `expires_at` sits beside it. The token is shown once to the organiser, as in `asks.mint` (hash only stored). An anonymous rating is stored with `by: null`.

## Agent behaviour (North, Lens, Nira: what each drafts, when, and the moment a person acts)

- **North** drafts the area chips from the named participants' tags and from the purpose line, once per start flow. The organiser clicks Add. North also drafts the "N more people will see this" warning on Change areas. North never edits `areas`.
- **Lens** drafts area names from the `team` values of the profile people (`reader.py` reads "team" or "department" columns) and drafts tags from each person's `team`. These are guessed cells with `agent: lens`. The admin accepts. A tag the admin set is never replaced (rule 7 of CLAUDE.md, enforced by `store.set_cell`).
- **Nira** writes "4 people have no area" for the admin, and "3 intents are running in Finance" for area people. A Pulse line for a viewer without content carries only title, type, stage and area (title omitted for the super admin when titles are private). It never names a participant or quotes content. Nira reads through the same filter as a person, so a draft never reaches a Pulse line except for its starter.
- Agents reading an intent to draft inside it (North writing a closure draft) read as the system. What they write becomes content, so it is filtered like content when shown.
- Agents never tag, never share, never change a visibility. A named person does each.

## Rules (visibility, time box, who may do what)

1. Relations a viewer can hold on an intent: organiser, sponsor, participant, observer, affected, same-area, company admin, super admin, share visitor. A viewer holds many; each column is granted if any relation grants it (union). Named slots decider, owner and reporter (ruling 13) read as participant (Open question).
2. **Matrix.** Key: Y yes. N no, and the whole intent is absent (404). S sealed cards: whole to a viewer who may see every restricted area their words name, otherwise a silhouette, by `view._cards`. A anonymous cards, shown without an author for everyone, admin included (D-013). Counts are numbers from the record. "Closed" means state closed.

| Viewer | Existence | Title, purpose | Stage, clock | People list | Content | Sealed cards | Anonymous cards | Outcome | Closure | Ratings |
|---|---|---|---|---|---|---|---|---|---|---|
| Organiser | Y | Y | Y | All names | Y | S | A | Y | Y | Y, anonymous without name |
| Sponsor | Y | Y | Y | All names | Y | S | A | Y | Y | Y, anonymous without name |
| Participant | Y | Y | Y | All names | Y | S | A | Y | Y | Y, anonymous without name |
| Observer (reads like a participant, never writes or votes) | Y | Y | Y | All names | Y | S | A | Y | Y | Y, anonymous without name |
| Affected, "may read" off (default) | Y | Y | Y | All names | N | N | N | Y once closed | `what_came_out` and `next` once closed | N |
| Affected, "may read" on | Y | Y | Y | All names | Y | S | A | Y | Y | Y, anonymous without name |
| Same-area non-participant | Y | Y | Y | Organiser only | N | N | N | Y once closed | `what_came_out` and `next` once closed | N |
| Other-area person (or no area) | N | N | N | N | N | N | N | N | N | N |
| Company admin | Y | Y | Y | Organiser, then counts | N | N | N | Y | `what_came_out` and `next` | Count always; average from three ratings |
| Super admin | Y, existence only, per company | Title only; hidden when the company sets titles private | State, dates and time box status only | Count only | N | N | N | N | N | N |
| Share-link visitor (also an affected person named on a share) | Y, this intent only | Y | Y | Organiser, sponsor, and participants who spoke by name | Y read-only | S | A | Y | Y | N |

   The super admin also sees type and areas. An affected person named on a share holds the share-link row too, so content opens for them by union.

3. A draft intent shows to the person who started it (`created_by`) and to nobody else: not the sponsor, not the company admin, not the super admin (ruling 14). Every row above reads N for a draft except that person. Cancelled intents follow the table, carry their reason and are listed in Past.
4. Affected people (by area or named) see existence, title, purpose, stage, clock, people and the outcome once closed. They open content only when the organiser switched on "Affected people may read" at creation (default off) or when a share names them (ruling 4). Observers read what participants read and never write or vote: every write route refuses an observer.
5. A tag grants sight of existence only. It never grants a restricted area (`governance.restricted_areas`); the two are different things. The screens say "Area" for departments and "Restricted area" for the sealed lists, never one word for both.
6. Who may do what: company admin edits areas, tags and the titles-private switch (company admin only, as `PUT /api/profile/people/{pid}/account` already is); the organiser sets the intent's areas, affected, "may read" switch and share; nobody else.
7. Content routes of the modules (`modules/m1_intent`, `m2_baseline`, `m3_connect`) that serve an intent's walls, charters, baselines or assessments call `view.may_open_content(intent, viewer)` before answering. Without it a record id would bypass the matrix.
8. A hidden intent is never a 403. Totals, counts per area and search results never include it for that viewer.
9. A person leaving an area stops seeing that area's intents at once. Nothing is deleted.
10. Pack areas are suggestions. An industry with no pack gets an empty suggestion panel, not another industry's list (industry rule).
11. Dates and clocks show in the company's time zone from the profile, else UTC. Counts are exact; no mean or per-person figure appears in this feature.

## Counters and measures of this feature (numbers only, each traced to a record)

| Counter | Source | Shown to |
|---|---|---|
| Areas active, retired | `areas.*.status` in the profile | Company admin |
| People tagged, people with no area | `people.*.areas` against `people` | Company admin |
| People per area | `people.*.areas` | Company admin |
| Intents per area, running and closed | `intents/*/intent.json` `areas`, `state`, counted over the viewer's own filtered set (drafts only for their starter) | Each viewer, own set only |
| People who will see this (picker) | accounts whose person's `areas` meets the pick | Organiser |
| Intents with no area | `intents/*/intent.json` where `areas` is empty and state is not draft | Company admin. Expected 0 |
| Shares active | `share.revoked_at` null and `expires_at` in the future | Organiser, own intents |

A figure with nothing behind it reads "Not available yet" and names the missing record (for example "No people file read yet").

## Reuse check (what exists today: file paths and line ranges found with graft; copied, reshaped or not used, and why)

| Found | Decision |
|---|---|
| `sh_platform/profile/view.py` 22-23, 26-31 (`ROLE_PASS`, `ADMIN`, `Viewer`) | Reused. `Viewer` gains `areas: frozenset[str] = frozenset()` and `person_id: str \| None = None` with defaults, so every existing caller is untouched. `api.py` `_viewer` (lines 33-37) fills them from the account link |
| `view.py` 34-76 (`norm`, `allows`, `_passes`, `_bound`) | Reused as is for named-person matching (organiser, sponsor, participant, affected, share list). Account-bound matching stays, so a name two accounts share does not match by name |
| `view.py` 167-184 (`_cards`, `SILHOUETTE`) | Reused unchanged for the S and A columns. No second sealed or anonymous rule |
| `view.py` 116-164 (`read`) | Reshaped: a new function `read_intent(plane, intent, viewer) -> dict \| None` beside it, and `"areas"` added to the section list in `read` so the area list reaches the screens. Restricted-area logic is not touched |
| `view.py` 198-203 (`NOBODY`) | Reused as the viewer for "unauthenticated" tests |
| `sh_platform/profile/store.py` 78-132 (`mutate`, `set_cell`, `record`) | Reused for areas and tags: provenance cells, agent never overwrites a person |
| `store.py` 25-26 (`DEPTH`) | Reshaped: one entry added |
| `sh_platform/profile/links.py` (account to person link, admin only) | Reused to find a viewer's person; the link picker is reused on Screen B |
| `sh_platform/profile/api.py` 141 lines (`_plane`, `_viewer`, `_answer`, `NOT_FOUND`) | Reused: new routes follow the same shape and refusal words |
| `sh_platform/profile/reader.py` 99 (`team`/`department` column read) | Reused as Lens's source for area suggestions |
| `sh_platform/entitlements.py` (`Catalogue`, `Centre`, `EntitlementStore.centres_for`) | Not used for visibility. It switches modules and centres per company, which says nothing about one intent. Whether a role without Intent in its role table reaches `/centre/intent` is an Open question |
| `sh_platform/route_permissions.yaml` (lines 263-271, profile block) | Reshaped: new lines added; default deny means an undeclared route is refused |
| `sh_platform/jsonfile.py` (`read_json_strict`, `write_json_atomic`, `lock_for`) | Reused for `intents/<id>/intent.json` |
| `sh_platform/packs.py` 20-66 (`Pack.section`, `EmptyPack`) | Reused; `areas.yaml` is picked up as a section with no code change |
| `sh_platform/profile/asks.py` (`mint`, token whose hash only is stored, `link_hours` in `contract.yaml`) | Reshaped for the share token; expiry default is an open question |
| `tests/auth/test_role_matrix.py` 29-83 (`ACTS`, `expected`, `fill`, `world`, `results_for`) | Reused by graft: new `ACTS` lines only, no new harness |
| `ui/src/shell/roles.ts` role table | Reused; unchanged. Unchanged here; the home route question is open |
| Nothing in the repo stores departments for accounts or intents (searched `areas`, `department`, `team` across `sh_platform` and `packs`) | The area section and tag cell are genuinely new |

### Tests that prove the matrix

New file `tests/intents/test_visibility_matrix.py` (fixture: synthetic Ardmore company, one second company on the asset management pack, one empty company).

1. `test_matrix_cells`: parametrised over the eleven rows and ten columns, drafts included, calling `view.read_intent`. The expected table is typed out in the test, independent of the code, and a change to either shows as a failure.
2. `test_matrix_over_api`: signs in as eleven personas (Janet organiser, Daniel sponsor, Katie participant, a named observer, Harvey affected with the switch off, a second intent with it on, a second Finance colleague same-area, Grace other-area, the company admin, the super admin, a named share visitor) and checks `GET /api/intents` and `.../{id}` against the same table.
3. `test_hidden_is_absent`: other-area `GET` and a made-up id return identical 404 bodies; list `total` excludes it; `?area=` filter does not leak it.
4. `test_anonymous_never_named`: serialises every persona's response and asserts no author account id, name or email of an anonymous card or rating appears, the company admin included; `rated_by` never leaves the server.
5. `test_sealed_silhouette`: a sealed card naming a restricted area the viewer is not on is a silhouette for participant and share visitor.
6. `test_union_of_relations`: a person who is same-area and participant gets participant columns; an admin who is also a participant gets content.
7. `test_draft_hidden`: a draft answers 200 to its starter only; sponsor, company admin and super admin get the same 404 as a made-up id.
   `test_observer_never_writes`: an observer reads like a participant and every write route refuses them.
   `test_affected_switch`: with "may read" off an affected person gets no content and sees the outcome once closed; with it on, content opens.
8. `test_tag_change_applies_at_once`: remove the second Finance colleague from Finance, the intent disappears from the list in the next call; retired area still matches past intents.
9. `test_share_link`: named visitor reads, an unnamed one gets 404, revoked and expired get 404, the token is absent from the stored file (hash only), a link from company A fails closed in company B.
10. `test_content_routes_check_matrix`: every module route whose path carries an intent or session id is called as same-area and other-area personas and returns no content.
11. `test_areas_admin`: only the company admin writes areas and tags; a participant gets the guard's 403; rename keeps the id; a duplicate name is refused; pack areas are not stored until accepted; the empty company and the second industry show the right suggestions (none, or their own).
12. `test_super_admin_projection`: exactly title, type, state, areas, people count, dates and time box status, and never purpose, stage, clock or names; with `titles_private` on the title is absent; drafts never appear; the kernel read leaves no copy in the control plane.

In `tests/auth/test_role_matrix.py`, add to `ACTS`: `GET /api/company/areas`, `GET /api/intents`, `GET /api/intents/{intent_id}` for all six company roles and not the super admin (the share visitor entry is a guest route tested under file 14); `POST /api/profile/areas`, `PUT /api/profile/areas/{area_id}`, `PUT /api/profile/people/{pid}/areas` for `{"company_admin"}`; `PUT /api/intents/{intent_id}/areas` and the share routes for all six company roles (the handler returns 404 to a non-organiser, which the harness reads as the guard letting the role in). The existing `test_every_route_is_declared` then fails until every new route has a line in `route_permissions.yaml`.

## Not in this feature

- The intent record's creation, stages, closure and rating screens (other files); this file only filters them.
- Groups, teams as nested areas, area owners, per-area approval flows.
- Email notice to people who gain sight of an intent.
- Guests with no account opening a share link.
- Walls, charters and baselines themselves: filtered by their own modules, which call `may_open_content`.

## Open questions

1. Routes outside ruling 1: `/company/settings/areas`, `/company/settings/areas/people`, `GET /api/company/areas`, the `/api/profile/areas...` routes and `GET /api/control/companies/{company_id}/intents`. They are area, profile or control routes, not intent pages. Do they stay, or move?
2. May roles whose role table has no Intent centre (participant, owner, approver) open `/centre/intent`? Files 03 and 06 decide.
3. How does the share token ride in `/centre/intent/<id>/share` (fragment or query)? File 14 decides.
4. Company admin and closure: the brief gives existence and outcome. Should the admin also see `closure.summary` and `why_it_happened`? Default: no.
5. Same-area and affected (switch off) people see `what_came_out` and `next` but not `summary` and `why_it_happened`. Is that the right cut of "the outcome once closed"?
6. Ratings: ruling 15 keeps the link in the person's own file, while this file keeps `rated_by` on the record to stop double votes. Which one, and where does the own-file link live? The company admin sees the count and an average from three ratings, as ruling 8 gives for ratings.
7. Where does the `titles_private` company setting live (profile, governance or entitlements), and may the company admin change it after intents exist?
8. Share link expiry (default here 14 days, as the profile ask link) and whether an unnamed external person with no account may ever open one (default: signed-in named accounts only).
9. Who may start an intent: every role, or the organiser trio only (`ORGANISER` in the role matrix)?
10. A person who moves area: should past intents they saw stay visible? Default here: no, they follow the tag.
11. `people` in the intent record: profile person ids (assumed, resolved to accounts through the link) or account ids.
12. Named slots decider, owner and reporter read as participant here. Ruling 13 adds the slots but not their access.
13. Is at least one area required to open an intent (assumed here)? The brief only says the opener names areas.
14. May the organiser change "Affected people may read" after creation, and does Change areas then ask Confirm?
15. The brief's section 4 says affected people open the content; ruling 4 overrides it (switch off by default). The brief itself needs the same correction.
16. A draft started on someone else's behalf is seen by its starter only (ruling 14). Is that wanted when the organiser differs?
