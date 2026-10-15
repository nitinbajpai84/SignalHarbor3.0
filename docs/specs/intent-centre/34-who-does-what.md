# 34. Who does what (Build roles named at the charter)

Part of: Intent Centre v2. Depends on: 01 (intent record), 06 (people and roles in an intent), 13 (Pulse lines and notifications), the Initiative charter (v1 spec, Define). The six Build roles are the list in SHAPES section 12 (architect, developer, tester, sponsor, ops, informed); the six roles in TESTING-INTENT-CENTRE section 7 are superseded by it. Feeds: Build centre hand-overs (gap analysis first), UAT sign-off, Pulse, 09 (closure and sign-off), 19 (counters).

## Purpose (three sentences)

An Initiative that needs a build must say, before Build starts, which real person will do each part. This feature gives the charter a "Who does what" panel with six Build roles, drafted by Lens from the company people list and confirmed by the organiser, and it asks each named person to accept or decline so nobody finds out in Build that they were given a job. The accepted roles are kept in the charter roles block, and the Build centre and Pulse read that block to address every hand-over to a named person.

## Who uses it and when (role, moment, trigger)

| Role | Moment | Trigger |
|---|---|---|
| Organiser (Janet) | Finishing the charter, before the build-ready check | Opens the "Who does what" panel on the charter; Lens has already drafted it |
| Named person (for example Katie as developer, Harvey as ops) | Told they are named for a Build role | A Pulse line "You are named as <role> for <title>" |
| Sponsor (Daniel) | Seeing who will do the work before he signs the charter | Reads the panel; sponsor is a role in the panel but is not picked here (see Rules) |
| Company admin | Checking the Initiative has people for Build | Reads the panel, never edits |
| Build centre | Starting gap analysis, addressing a hand-over | Reads the accepted roles |
| Lens | Charter opened or the people list changed | Drafts roles, marked guessed |
| North | Roles named but not answered | Nudges the named person, tells the organiser when a role is declined |

## Entry points (every route, link, Pulse line, button that leads here)

- Charter view `/centre/intent/<id>/charter`: the "Who does what" panel in the side column (Existing component `RolesPanel`, rendered by `CharterView.tsx`). The built stub route `/centre/intent/charter/<session_id>` is the same screen under its old spelling; Open question 11.
- Charter view with the panel full width: `/centre/intent/<id>/charter?focus=roles`. Reached from "Open who does what" on the Build-ready view and from the Build-ready line "Roles named: 4 of 6".
- Build-ready view `/centre/intent/<id>/build-ready` (stage 3 of an Initiative): the row "Who does what" links to the panel.
- Pulse line for a named person (strip `act`, kind `role_ask`): "You are named as developer for <title>. Accept or decline." Href `/centre/intent/<id>/charter?role=<role>`.
- Pulse line for the organiser (strip `act`, kind `ops`): "Katie declined the developer role on <title>. Name someone else." Href `/centre/intent/<id>/charter?focus=roles`.
- Pulse line for the organiser (strip `watch`): "2 roles on <title> are waiting for an answer."
- Build centre: the hand-over header on `/centre/build/blueprint`, `/centre/build/prove` and `/centre/build/ops` shows the name for the role it needs and links back here.

## Screens, element by element

### Screen A. "Who does what" panel on the charter

Route: `/centre/intent/<id>/charter` (side card) and `/centre/intent/<id>/charter?focus=roles` (full width). Layout at 1280: side card, 320 px wide, under the problems list; one row per role, then a footer line. On the full-width route the rows sit in two columns with the "What this person will be asked to do" line beside each. At 390: the card moves below the signature section; each row is full width, buttons wrap under the name, the "will be asked to do" line sits under the role label.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Card title "Who does what" | Panel | Title and one line: "These people get the Build hand-overs on their pulse." | None | Everyone who may open the charter | Never empty |
| Role label (Architect, Developer, Tester, Sponsor, Operations, Kept informed) | Label | The role name | None | Everyone who may open the charter | Never empty |
| "Will be asked to" line | Label | The one-line duty for the role (table in Rules) | None | Everyone who may open the charter | Never empty |
| Person field | Picker (one name, or several for Kept informed) | A person from the company people list, searched by name, with their company role beside the name | Pick saves the change as stated (no Save button needed on pick; a typed name with no match shows "Not in the people list") | Organiser edits; others read | "Not named yet" |
| Mark chip | Chip | Guessed (with the reason, for example "Role in the profile reads engineer"), Stated (and by whom), or Left open | None | Everyone who may open the charter | "Left open" when the organiser cleared it |
| "Confirm" | Button | Appears on a guessed row | Writes the same name as stated, by the organiser | Organiser | Hidden when stated or empty |
| "Edit" | Button | Opens the picker on that row | Opens picker | Organiser | Hidden for non-organisers |
| "Clear" | Button | Appears in the picker | Sets the role to Left open (allowed for Architect, Developer, Tester, Operations and Kept informed) | Organiser | Not applicable |
| Answer chip | Chip | Waiting for answer, Accepted (date), Declined (date), Not asked yet | None; hover shows the reason on Declined | Organiser and company admin see reasons; others see the chip only | "Not asked yet" until the organiser confirms |
| "Ask them" | Button | Appears when a role is stated and not yet asked, or after a changed name | Sends the Pulse line to that person; writes `asked_at` | Organiser | Hidden once asked |
| "Ask everyone named" | Button | Footer; counts the stated, unasked roles | Asks them all in one go | Organiser | Disabled with "Nobody to ask yet" |
| "Name someone else" | Button | Appears on a Declined row, with the decline reason above it | Opens the picker; a new pick resets the answer to Not asked yet | Organiser | Hidden unless declined |
| "Hand over anyway" | Button | On the Build-ready view only, beside "Roles waiting"; asks for a reason | Pending Open question 4: hands over with a required role unaccepted and keeps the reason | Organiser | Hidden when every required role is accepted |
| Roles counts line | Label | "Roles named: 4 of 6", "Accepted 3, waiting 1, declined 0" (records in the Counters table) | None | Organiser, sponsor, company admin | "Not available yet: no roles have been drafted." |
| Footer line | Agent line (Lens) | "Lens drafted 4 roles from the people list. Check them." or "All six roles are stated." | None | Organiser | "No roles drafted: the people list is empty. Add people in the profile first." |
| Gap line | Agent line (North) | "The Build-ready check needs a tester and a developer. Neither is named." | Click opens the picker for the first gap | Organiser | Hidden when nothing is missing |

### Screen B. Role request (what the named person sees)

Route: `/centre/intent/<id>/charter?role=<role>` (request page for one role; the query form is Open question 11). Layout at 1280: single column, 640 px, centred. At 390: full width, buttons stacked, "Decline" below "Accept".

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Title | Label | "Janet has named you as developer for <title>" | None | The named person only | Not applicable |
| "What you will be asked to do" | Panel | The one-line duty, plus the Initiative purpose (`intent.purpose`) and time box end date (`intent.time_box.ends`, company time zone from the profile, else UTC) | None | The named person, organiser | Never empty |
| "Who else is named" | List | The other roles and names, and their answers as chips | None | The named person, organiser | "You are the first to be named." |
| "Accept" | Button | Label "Accept the <role> role" | Writes accepted, by the person, with the date | The named person only | Hidden after answering; replaced by "You accepted on 9 Oct. Change your answer" |
| "Decline" | Button | Opens a reason field | Reason is required (one line; length limit is Open question 10); "Send decline" writes it | The named person only | Disabled until a reason is typed |
| "Change your answer" | Link | Appears after an answer while the Initiative is not handed to Build | Reopens Accept and Decline | The named person | Hidden after hand-over to Build |
| "Not now" | Link | Goes back to Pulse | The line stays | The named person | Always shown |
| "Got it" | Button | Kept informed only, replaces Accept and Decline | Writes `seen`, by the person, with the date | The named person | Hidden after pressing; shows "You saw this on 9 Oct" |

For Kept informed there is no Accept or Decline. The person sees "You will be kept informed of <title>" and the "Got it" button above. Kept informed is never a blocker.

## User journey (numbered steps from arriving to leaving, with what the agent does between the person's steps)

1. Janet reaches the charter. Lens (agent) has already drafted the roles from the people list; each row shows a Guessed chip and its reason.
2. Janet reads each row. For a good guess she presses "Confirm"; for a wrong one she presses "Edit" and picks another person from the list. Each change is saved as stated, by Janet.
3. Where Lens found nobody, the row says "Not named yet". North (agent) adds the gap line naming the Build roles still needed.
4. Janet presses "Ask everyone named". Nira (agent) writes one Pulse line per person. Janet acts, not an agent.
5. Katie sees "You are named as developer for <title>" on Pulse, opens Screen B, reads what she will be asked to do and presses "Accept".
6. Harvey cannot take the operations role. He types "On leave until 21 Oct" and presses "Send decline". The role returns to Janet: the row shows Declined and the reason; North writes the organiser Pulse line.
7. Janet presses "Name someone else", picks another person and asks again.
8. When every required role is accepted, North updates the Build-ready check: "Roles named and accepted: 5 of 5 required." Janet may now hand over to Build.
9. At hand-over the roles block is frozen into the charter record the Build centre reads. A later change goes through "Change roles after hand-over" (Open question 9). Janet leaves for the Build centre hand-over; each other named person leaves to Pulse when they press "Not now", "Accept", "Send decline" or "Got it".

## States and transitions (table: state, who moves it, to what, what is written)

Per role (not per Initiative):

| State | Who moves it | To what | What is written |
|---|---|---|---|
| open (no name) | Lens drafts, or organiser picks | guessed or stated | `roles.<role>`, `provenance.<role>` |
| guessed | Organiser presses Confirm or picks another | stated | `provenance.<role>` = stated, by organiser, at |
| stated, not asked | Organiser presses Ask them | asked | `answer.state = waiting`, `asked_at`, Pulse line |
| waiting | The named person | accepted | `answer.state = accepted`, `answer.at`, `answer.by` |
| waiting | The named person | declined | `answer.state = declined`, `answer.reason`, `answer.at`; role goes back to organiser |
| declined | Organiser names someone else | stated, not asked | name replaced; old answer kept in `answer_history` |
| accepted | Organiser names someone else | stated, not asked | old answer kept in `answer_history`; the previous person is told |
| any | Lens redraft | no change if stated; a guess is refreshed only while it is guessed | nothing for stated rows (rule 7: a draft never overwrites a human edit) |

Informed has one more answer value: `seen`. Sponsor is `accepted` when the sponsor person signs the charter or presses Accept on the invitation (see mapping below).

## Records read and written (file or route, fields; mark Existing or New)

| Record or route | Fields | Mark |
|---|---|---|
| `intents/m1_intent/roles/<session id>.json`: `roles` (six keys), `provenance` (mark, by, from, at) | The six roles and where each came from | Existing |
| `modules/m1_intent/domain/roles.py`: `ROLES`, `draft`, `merge`, `state`, `clean` | Drafting, merge, organiser set, body check | Existing; `draft` reshaped, `clean` tightened (see Reuse check) |
| `GET /api/modules/m1_intent/sessions/{id}/roles` | roles, provenance, can_edit | Existing (id is the charter's session id; the intent record points at it); response gains `answers` and `people_ids` |
| `PUT /api/modules/m1_intent/sessions/{id}/roles` | Organiser sets roles | Existing; refuses a name that is not in the people list |
| `POST /api/intents/{id}/roles/ask` | roles to ask (or all) | New (ruling 1: new routes sit under `/api/intents/...`) |
| `POST /api/intents/{id}/roles/{role}/answer` | accept or decline, reason | New |
| Company people list (`sh_platform/profile/store.py raw(plane)["people"]`, filtered for the viewer by `sh_platform/profile/view.py`) | name, role, team, passage | Existing |
| Wall cards and seats (`modules/m1_intent/store/room.py` seats; wall cards) | who took part, what each wrote | Existing, read only |
| `sh_platform/build/uat.py _role(plane, "tester")` | Reads the roles file of the latest signed charter | Existing; reads accepted answers once this feature lands |
| `GET /api/pulse` | LINE with kind `role_ask` | Existing route, new line source (see 13) |
| `intents/<id>/intent.json` key `build_roles` (reference only) | `{session_id, roles_ref}` pointing at the roles file | New |
| `intents/<id>/intent.json` keys `purpose`, `time_box.ends`, `people.organiser`, `people.sponsor` | Shown on Screen B; the sponsor sets `roles.sponsor` | Existing (brief section 3), read only |

## Fields this feature adds to the intent record

The roles file keeps its two existing keys. This feature adds, per role, an `answers` block and a hand-over stamp. The intent record gets a reference only; it never copies the roles.

```
roles.json (existing keys unchanged):
  roles:       {architect, developer, tester, sponsor, ops: person id|null, informed: [person id]}
  provenance:  {<role>: {mark: guessed|stated|unknown, by, from, at}}
  # added by this feature:
  names:       {<role>: display name | [display name]}      # display copy so a rename in the profile does not break old charters
  answers:     {<role>: {state: not_asked|waiting|accepted|declined|seen,
                         asked_at|null, at|null, by: person id|null, reason|null}}
  answer_history: [{role, person_id, state, reason, at}]
  handed_over_at: iso|null                                  # set when the Initiative goes to Build

intent.build_roles: {session_id, roles_ref: "intents/m1_intent/roles/<session id>.json"} | null
```

Note: existing files store names as text. Existing rows are read as a name; a name that matches no person id in the people list is shown as "Not in the people list. Pick again" and counts as not named.

## Agent behaviour (North, Lens, Nira: what each drafts, when, and the moment a person acts)

- **Lens drafts.** When the charter opens and whenever the people list changes, Lens drafts any role that is open or guessed, never one that is stated. It reads the people list (role, team, passage), the skills a person shows on the wall (what they wrote on cards in this Initiative), and the seats of the people who took part. Every draft is marked guessed with the reason in words ("Wrote 3 cards about the nightly feed", "Role in the profile reads operations"). Existing draft rules (head of data to architect, engineer or data role to developer, operations role to ops, approver to sponsor, participants to informed) stay; Lens adds the wall evidence. Whether one person may be drafted into two Build roles is Open question 5; until settled Lens drafts each person into one role at most and says "No one else to suggest" where the list runs out.
- **Lens does not decide.** The organiser confirms; only then is the role stated. Lens cannot ask anyone.
- **Nira writes the Pulse lines.** The role ask to the named person, the decline line to the organiser, the waiting line on the organiser's watch strip. Lines use plain words: "You are named as developer for <title>."
- **North watches.** North computes the gap line (roles required for this Initiative that are not accepted), nudges a named person once when no answer has come in the nudge period (Open question 7), and tells the organiser. North does not change a name.
- **People act at named moments.** The organiser picks, confirms, asks and replaces. The named person accepts or declines. Nobody answers for another person and no agent signs.

## Rules (visibility, time box, who may do what)

**A role names a real person.** Each Build role holds a person id from the company people list. There is no free text. A typed name that is not in the list is refused with "Pick someone from the people list. If they are missing, add them in the profile." The people list is the profile's People and roles table; a person who has no account yet may still be named, and the Pulse line waits for them (Open questions).

**What each role will be asked to do in Build (shown as the one line the person accepts).**

| Role | One line | Required |
|---|---|---|
| Architect | Check the gap analysis and design the blueprint, and sign that the design fits what the charter asked for. | Yes, for a build Initiative |
| Developer | Build the pipelines and measures from the blueprint and run them against the baseline. | Yes, for a build Initiative |
| Tester | Check each measure against the benchmark and sign the user acceptance test or send it back with what needs fixing. | Yes. With none named, the existing fallback (sponsor or company admin signs) stays, and the panel says so |
| Sponsor | Own the outcome, sign the charter, and approve the release. | Yes, always |
| Operations | Run the release and watch it once live; take the first call when it breaks. | Yes before release, may be named later |
| Kept informed | Read the hand-overs and the release note. You are not asked to do anything. | No |

**Who may do what.** Only the organiser names, confirms, clears, asks and replaces. Only the named person answers for their own role. The sponsor is set from the Initiative's `people.sponsor` and is not a separate pick (one source, no two sponsors). Company admin reads and cannot edit. A super admin sees nothing of this panel.

**Visibility.** The organiser, the sponsor, company admin and the named people see the names, marks and answers. Decline reasons are seen by the organiser and company admin only. An affected person sees the panel only when the organiser switched on "affected people may read" at creation or names them on a share (brief ruling 4); they see names and chips, never reasons. An observer reads what a participant reads and never writes. Each named person sees their own role request; others' roles appear on Screen B as names and answer chips only.

**Acceptance gate.** A required role that is not accepted holds the Build-ready check at "Roles waiting". Whether the organiser may hand over anyway, with a reason kept, is Open question 4. Kept informed never holds it.

**Time box.** A role ask carries the Initiative's end date. An answer does not extend the time box. North nudges once (period in Open question 7). Dates and working days use the company time zone from the profile, else UTC.

**Reasons.** A decline requires a reason. Accepting needs none.

**After hand-over.** Roles are frozen on `handed_over_at`. A change after that is a new organiser pick plus a new ask, and the previous person is told.

## Initiative-internal roles and how they map to the Build roles

The Initiative has its own people (brief section 3; spec 06): organiser, sponsor, committee, governance lead. They govern the Initiative; the Build roles do the work. They are different lists. The governance lead maps to no Build role by default and stays an Initiative-internal role. The mapping:

| Initiative role | What they do in the Initiative | Maps to Build role | How |
|---|---|---|---|
| Organiser (Janet) | Runs the Initiative, owns the charter, names the Build roles | None automatically | The organiser may also be picked as any Build role. The panel marks it "Janet is both organiser and developer" and does not hide it |
| Sponsor (Daniel) | Owns the outcome, signs the charter | Sponsor | Same person, one record. Setting `people.sponsor` sets `roles.sponsor`; the sponsor's signature on the charter counts as accepted |
| Committee (members) | Reviews and advises; not named in Build | Kept informed (default) | Lens drafts committee members into Kept informed. They may be moved to another role by the organiser |
| Governance lead | Confirms the governed state (what is signed and kept) in Define | None | Stays an Initiative-internal role. Lens does not draft the governance lead into any Build role; the organiser may still pick them like any other person |

Participants and affected people have no Build role unless the organiser names them.

## Counters and measures of this feature (numbers only, each traced to a record)

| Counter | Source | Where shown |
|---|---|---|
| Roles named, of six | Count of non-empty keys in `roles.json roles` | Build-ready check, panel footer |
| Roles stated, guessed | Count of `provenance.<role>.mark` | Panel footer |
| Roles accepted, waiting, declined, of those asked | Count of `answers.<role>.state` | Build-ready check, organiser Pulse line |
| Days from ask to answer (mean) | `answers.<role>.at` minus `asked_at` | Mean shown as "Fewer than five" below five answers (brief ruling 8) |
| Roles declined on this Initiative | `answer_history` entries with state declined | Panel footer, only to organiser |

If the roles file does not exist, every counter shows "Not available yet: no roles have been drafted."

## Reuse check (what exists today: file paths and line ranges found with graft; copied, reshaped or not used, and why)

Searches run: `grep -i roles` over `modules/m1_intent`, `sh_platform/build`, `ui/src`; reading of SHAPES section 12 and `sh_platform/pulse/messages.py`. Every path below was checked to exist on 7 Oct 2026.

| Existing | Where | Decision |
|---|---|---|
| Domain rules: `ROLES`, `draft`, `merge`, `state`, `clean` | `modules/m1_intent/domain/roles.py` (1 to 81) | Existing, kept. Reshaped: `clean` checks person ids against the people list instead of accepting any text; `draft` reads wall evidence too |
| Roles routes GET and PUT | `modules/m1_intent/api/roles.py` (1 to 63) | Existing, kept. Extended with `ask` and `answer`, and the people-list check on PUT |
| Roles file `intents/m1_intent/roles/<session id>.json` | written by `api/roles.py` `_file` | Existing, kept; gains `names`, `answers`, `answer_history`, `handed_over_at` |
| Roles panel component | `ui/src/modules/m1_intent/charter/RolesPanel.tsx` (1 to 76), with `roles.test.tsx` | Existing, kept. Reshaped: free-text input becomes a people picker; adds answer chip, "Ask them", "Name someone else". Marks and "Confirm" already exist |
| Panel placed on the charter | `ui/src/pages/CharterView.tsx` line 86 (import at 24) | Existing (via graft). Not rebuilt; the panel is already rendered here |
| Build reads the tester | `sh_platform/build/uat.py` `_role`, `_tester` (about 24 to 45), with the sponsor or company admin fallback | Existing, kept. Reshaped to read accepted answers and the person id; other Build files (`blueprint.py`, `prove.py`, `ops.py`) do not read roles today and need the same read |
| Pulse draft messages and templates | `sh_platform/pulse/messages.py`, `templates.py` (KINDS, WRITERS) | Existing; new kind `role_ask` follows the same pattern |
| Profile people and view filter | `sh_platform/profile/store.py`, `view.py`, `contract.yaml` (People and roles table) | Existing, read only |
| Seats and join | `modules/m1_intent/store/room.py` | Existing, read only |
| Invitation accept and decline pattern | Spec 06 Screen D (a sibling spec, not code) | Pattern copied in words; the code is new here because it answers a role, not a seat |

Genuinely new: the answer states and routes, the role request page (Screen B), the Pulse kind `role_ask`, the people-list check, and the reads in `blueprint.py`, `prove.py` and `ops.py`.

## Not in this feature

- Intent-wide people (participants, affected, observers): spec 06.
- Who signs the charter and how: spec 09 and the v1 charter.
- Gap analysis and the Build screens themselves: Build centre.
- Rota, cover for leave, or a second person per role.
- Changing roles after the Build has started.
- Any pay, hours or workload data.

## Open questions

1. The testing guide section 7 list (owner, architect, builder, tester, releaser, analyst liaison) is superseded by SHAPES section 12. The guide still shows the old list and needs the same correction, outside this folder.
2. The people list has name, role, team and passage but no skills field. Lens reads skills from the role text, the passage and the wall. Is a "skills" column wanted in the profile?
3. May a person with no account yet be named? This spec says yes and waits for them. A named person with no sign-in can never answer.
4. Can the organiser hand over with a required role unaccepted ("Hand over anyway" with a reason), or is acceptance a hard gate?
5. Who takes a role when the profile has too few people (a family office of three)? This spec allows one person in several roles with a visible note; the rule needs confirming.
6. Is a governance lead a defined role elsewhere? No definition was found in the v1 spec, and the brief's `people` object has no slot for it. Where is it stored?
7. How many nudges, after how many working days? Neither number is justified.
8. Should the committee be required to take part at all? Spec 02 asks the same about committee size.
9. How is a role changed after hand-over, and who must agree?
10. Decline reason length limit (a draft figure of 200 characters was removed as unjustified).
11. Routes: brief ruling 1 lists no `roles` view, so the request page uses `/centre/intent/<id>/charter?role=<role>` and the full-width panel `?focus=roles`. Is the query form right? Should the built stub `/centre/intent/charter/<session_id>` be re-pointed to `/centre/intent/<id>/charter`?
12. `people.sponsor` is optional per type (ruling 13). With no sponsor, is the sponsor role left open, and does it hold the Build-ready check?
13. Roles sit in a per-session roles file today. Should they move under `intents/<id>/` once the intent record exists?
14. Which roles are required before hand-over? The table in Rules (architect, developer, sponsor always, tester with fallback, ops before release) is a drafted default, not a settled rule.
