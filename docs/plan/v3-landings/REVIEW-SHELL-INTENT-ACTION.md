# Review: Shell + Intent + Action (S1, I1, A1, A2, G1) · 9 Oct 2026

**Verdict: not ready. One fix round needed.** The shell, the trail and the Intent conversation work on their own; the two hand-offs between cards are broken (old links into Action land on the wrong tab; "Send to Build" never puts a card in front of the head of data), three App tests fail, and the old agent names are still on screens the new shell reaches.

Tests run (no code edited, no servers, no live data):
- `SH_MODEL_PROVIDER=off python -m pytest tests/v1/test_i1.py tests/v1/test_i6a.py tests/v1/test_a5.py tests/v1/test_v3_g1.py -q` → **24 passed**.
- `cd ui && npx vitest run src/shell src/v1/a5 src/v1/a5trail src/v1/i6 src/v1/s1 src/App.test.tsx` → **79 passed, 3 failed** (all three `next=… is ignored` in `App.test.tsx:285`, blocker 3). `src/v1/s1` has no test file.
- `npx tsc --noEmit -p .` → clean.

## Journey results

### Action (a non-technical person)

| Step | Result | Where |
|---|---|---|
| Sign in → lands on Action | **Works.** `Gate` → `landingFor` → `/centre/action` for every company role (super admin → Control). | `ui/src/App.tsx:79`, `ui/src/shell/roles.ts:39` |
| Bar shows Intent · Action · Build · Consume per role | **Works.** Settings behind the avatar for admin and analyst only. | `CentreShell.tsx:43-47,78`, `roles.ts:25,36` |
| Today cards | **Works** for E5 cards (`GET /api/v1/pulse2/items`). Only exception cards get "Where is this from?" (matched by headline to `case_id`); document and data cards have none. | `a5/ActionCentre.tsx:39-64`, `e5/api.ts:49-53` |
| Open a case from a card | **Works.** Card link is `/centre/desk/<id>`; `Stay` rewrites it to `/centre/action/cases/<id>`. | `e5_pulse.py:112`, `ActionCentre.tsx:23-36` |
| Evidence inside the case | **Partly.** The case page is followed by the *whole* company evidence list, not the case's statements. Links rewrite to `/centre/action/evidence/<id>` correctly. | `ActionCentre.tsx:66-75` |
| "Where is this from?" → six steps | **Works.** `kind=case&id=` → `_case` → metric or latest valuation → six steps; restricted steps carry only the one sentence. | `a5_trail.py:308-328`, `TrailPanel.tsx` |
| Old link `/centre/desk/<id>` (bookmark, P2 card, e-mail) | **Breaks.** Redirect emits `?tab=cases&case=<id>`; A1 ignores both and shows Today. | Blocker 2 |

### Intent

| Step | Result | Where |
|---|---|---|
| Start a conversation | **Works.** `POST /api/v1/intents/chat` → `C.start` → `create_project` (errors swallowed). | `i6_chat.py:760-764` |
| Project id shown | **Works**, as "Project prj-xxxxxxxx" linking to `/centre/project/<pid>`. | `p1/ProjectTag.tsx:19` |
| Swim lane visible by default | **Works.** "Process map" is the second stacked document; `Swimlane` renders lanes by team. | `ConversationPage.tsx:273-278` |
| Sources captured | **Works.** `SourcesBlock` shows structure, owner, arrival, samples. | `ConversationPage.tsx:45-69` |
| Sign | **Works.** "Hand to the architect" → `/centre/intent/<iid>/sow` (I4), signer = raiser, sponsor or admin; crumb "North's thread" → `/thread` → back to the conversation. | `i4_routes.py:28-38`, `i3/routes.tsx` |
| Send to Build (button) | **Works** as a record: `send_to_build.json`, once, signer only. | `i6_routes.py:101-106`, `i6_chat.py:211-227` |
| …creates a card for the head of data in Action | **Breaks.** Nothing reaches `/centre/action`. | Blocker 1 |
| Return to a signed, not-yet-sent intent | **Weak.** `/centre/intent` only reopens an *unsigned* intent; once signed the conversation is reachable by URL only. | `i6_chat.open_intent`, `p3/IntentWelcome.tsx:42-44` |

## Blockers

### 1. "Send to Build" never shows a card to the head of data
- `sh_platform/v1/i6_chat.py:224-226` writes a P1 comment `by="north", to="head_of_data", kind="handover"`.
- `sh_platform/v1/p1_project.py:223-227` `_person`: `people.head_of_data` is empty until a *design* is signed, so the comment is addressed to the raiser (the person who just pressed the button).
- `sh_platform/v1/p2_pulse.py:113` skips every hand-over whose `by` is an agent key, so even P2 Pulse drops it.
- Action Today reads `GET /api/v1/pulse2/items` (`ui/src/v1/a5/ActionCentre.tsx:10,43`), built by `e5_pulse.generate` from five fixed sources (`e5_pulse.py:216-218`); P1 comments are never read there, and nothing in the new shell shows P2 Pulse at all.
- Scenario: Ann signs "Monthly investment report", presses Send to Build, reads "The head of data has a card in Action". Mei (analyst) opens Action: nothing.
- Fix (two lines of wiring): in `e5_pulse.generate` add a sixth source `_build_cards(plane, con)` that reads `intents/*/send_to_build.json` not yet carded and yields one card per active `analyst`/`company_admin` user (`recipient=uid`, headline "<title> is ready for Build", `link=f"/centre/build/p/{pid}"`, `action="Open in Build"`), and have `send_to_build` call `e5_pulse.generate(plane)` after writing the file. Drop the P1 comment or keep it as a record; either way address it to the analyst by name, not the empty `head_of_data` part.

### 2. S1 redirects emit query params A1 does not read
- `ui/src/shell/redirects.ts:10-12` → `/centre/action?tab=today|cases&case=<id>`.
- `ui/src/v1/a5/routes.tsx:5-7` are path routes (`action`, `action/cases`, `action/cases/:caseId`); `ActionCentre.tsx` never calls `useSearchParams`, so `?tab=cases&case=…` renders the Today tab.
- Scenario: a P2 card, a bookmark or the `/centre/tickets` link opens `/centre/desk/ex-123` → Today, case lost. `/centre/evidence/<docId>` also goes to the cases list, not the document.
- Fix: in `redirects.ts` return A1's real paths: `today` → `/centre/action`; `desk` → `b ? /centre/action/cases/${b} : /centre/action/cases`; `evidence` → `b ? /centre/action/evidence/${b} : /centre/action/cases`; `tickets` → `/centre/action/cases`. Update the three expectations in `shell.test.tsx:130-146`.

### 3. App tests still expect "HOME"
- `ui/src/App.test.tsx:285`: `findByRole("link", { name: "HOME" })` → three failures (`next=https://evil.example`, `//evil.example`, `/\evil.example`).
- Fix: `{ name: "ACTION" }` (the landing is `/centre/action`; the NavLink is already `aria-current="page"`).

### 4. P3 still registers `build` and `consume`; B1/C2 win, and Build loses its role gate
- `ui/src/v1/p3/routes.tsx:21-22` registers `build` (wrapped in a role `Gate`) and `consume`; `b6/routes.tsx:6` and `cxui/routes.tsx:7` register the same literal paths. `import.meta.glob` keys are sorted (`b6`, `cxui` before `p3`) and React Router picks the first of equal-score siblings (checked with `matchRoutes`: `/centre/build` → B6, `/centre/consume` → CX). So `BuildEntry`/`ConsumeEntry` are dead, and `/centre/build` now renders B1's project list for a participant with no client-side gate (the server still refuses the data, so the person sees an error page instead of "back on your start page").
- Fix: delete lines 21-22 of `p3/routes.tsx` (keep `intent`) and wrap B1's two `build` elements in `p3`'s `Gate centre="build"` (export it) so the refusal line still shows.

### 5. G1: old agent names on screens the new shell reaches; `AgentChip` cannot name Span or Lumen
- `ui/src/components/shellCopy.ts:19` `agent.roles` has only `North`, `Nira`, `Lens`, and `AgentChip.name` is `keyof` that map (`AgentChip.tsx:3,7`). `<AgentChip name="Span">` is a type error. tsc is clean today only because B1 and C2 pass `agent="Span"|"Lumen"` as plain strings to `Workbench`/`Composer` (`b6/BuildPage.tsx:68,76`, `cxui/ProjectPage.tsx:97,110`) and render no chip, so Span and Lumen have no avatar or role word where North has one. Fix: add `Span: "the build agent", Lumen: "the consume agent"` to `shellCopy.agent.roles` (and drop `Nira`, `Lens` once nothing renders them).
- Visible "Flow": `ui/src/pages/MemoryPage.tsx:12,90` (now inside Settings at `/centre/settings/memory`: "North, Lens, Nira, Span … and Flow (the data engineer)"); `ui/src/v1/f1/EngineerPage.tsx:188,206` ("Flow asks about every doubt", `Composer agent="Flow"`, reachable at `/centre/build/:iid/engineer`); `ui/src/v1/b4/RunsPage.tsx:34,120,124` ("Flow's note", `/centre/build/:iid/runs`); `sh_platform/v1/p2_pulse.py:140` ("Flow asked you to confirm…").
- Python labels still "Flow" (key `flow` may stay; the word people read must be Span): `p1_project.py:25`, `t2_tickets.py:30`, `l2_proposals.py:34`, `f1_chat.py:37`, `g2_runbook.py:75` (`drafted_by`), `g4_deviations.py:117`, `sh_platform/build/agents/runtime.py:21`, `sh_platform/build/proposals.py:39-42,413`.
- Fix: one-word edits, `"Flow"` → `"Span"` in the label positions above; `MemoryPage` `AGENTS = ["North", "Span", "Lumen"]`.

## Should-fixes

1. **`/centre/pulse` is not redirected** (`App.tsx:153-155`, `redirects.ts`): the old `PulsePage` with the HOME / TICKETS / COMPANY MAP bar is still one URL away. Add `if (a === "pulse") return "/centre/action";`. `GraphPage` is safe (its path is redirected) but P2 cards that link `/centre/intent/graph?node=…` lose the node.
2. **Evidence in the case page is the whole list** (`ActionCentre.tsx:72`): `EvidenceList` takes no filter. Show the case's instrument documents (CasePage already knows the instrument) or pass a filter prop.
3. **`Stay` misses `/centre/data/intake?batch=…` links** on data cards (`e5_pulse.py:149,154`): the redirect drops the query and lands on the Build project list. Add `["/centre/data/intake", "/centre/build"]` or point data cards at Build's Sources step once B1 has a route for it.
4. **A2 tile audience by group refused** (`a5_trail.py:370-372`): `audience` may hold group ids (`cx_dash.set_audience`), but the trail matches only `account_id`/name, so a group member gets 403. Reuse `cx_dash`'s may-view rule (`cx_dash.py:294`) instead of a second one.
5. **A2 restricted step leaks a date** (`a5_trail.py:156-157`): when the document is restricted the Source step's `when` is still `doc.received_at`. Use the batch date or `None` when `doc and not doc_ok`.
6. **Roles are approximations, written down nowhere a person reads**: no Operations role exists; `analyst` is Operations *and* head of data (`roles.ts:4,24`; `a5_trail.WORKERS`), CIO = `sponsor`. Fine for the demo; put the mapping in the Settings "People and access" page copy so nobody expects an Operations seat.
7. **`ROLE_TABLE.lands` still says `/centre/home`** (`roles.ts:8-13`) and `tests/auth/test_role_table.py:60` asserts it; `landingFor` overrides to Action. Change both to `/centre/action` so the table is the truth again.
8. **Signed-but-unsent intent is only reachable by URL** (`open_intent` returns unsigned only): the welcome page should list the person's recent intents with their state ("Signed, not sent to Build").
9. **"Where is this from?" only on exception cards** (`ActionCentre.tsx:43`): document and data cards get none; spec says every card. Add `kind="valuation"` for document cards (the `pulse_items` row has no document id, so the E5 raw card would need to carry it).
10. **Settings "Agent runs and cost"** is a placeholder sentence (`SettingsPage.tsx:21`); the Testing/Real switch is correctly only in Settings (`ModeSwitch` imported there alone; conversation screens show the read-only `ModeLine`).
11. **G1 wiring not yet done**: old `skills/{data,flow,intake,investigation,briefing,consumer}` folders still exist (aliased); `tests/v1/test_e0b1.py::test_skill_files_exist` pins `skills/data`.

## Fixes after review (v3 fix round A)

Blockers
1. Send to Build: `e5_pulse` has a documented extension point (`SOURCES`, `register_source(fn)`, `card(...)`, `user_ids_with_roles(...)`). A built-in source `_build_cards` makes one card per analyst, head of data and admin account ("<title> is ready for Build", link `/centre/build/p/{pid}`, key `build:{pid}`, once). `i6_chat.send_to_build` calls `e5_pulse.generate`; the unaddressed P1 comment is dropped (the record is `send_to_build.json`). Recipients are compared as text so a UUID user id and a string match.
2. `redirects.ts` now emits A1's real paths (`/centre/action`, `/action/cases[/id]`, `/action/evidence/id`); `/centre/pulse` also goes to Action.
3. `App.test.tsx` expects "ACTION".
4. P3 `build` and `consume` entries deleted; `Gate` is exported from `p3/routes.tsx`. Build role gate: see "Needs another card".
5. `shellCopy.agent.roles` gained Span and Lumen (North kept as "the industry expert", pinned by a components test). `MemoryPage`, `EngineerPage`, `RunsPage`, `p2_pulse`, `f1_chat`, `g2_runbook`, `g4_deviations`, `p1_project`, `t2_tickets`, `l2_proposals` and two Build proposal titles now say Span; the key `flow` and the stored agent identity `Flow` in `build/agents/runtime.py` and `build/proposals.py` stay as aliases.

Should-fix: 1 done. 2 the case page lists only statements of the fund the case names. 3 `/centre/data/intake*` links stay mapped to Build. 4 the tile trail uses `cx_dash.may_view` (named and group audience, E1d access; test added). 5 a restricted document no longer gives its date. 6 Settings "People and access" says which seat is Operations / head of data / CIO. 7 role table and `tests/auth/test_role_table.py` say `/centre/action`. 8 `GET /api/v1/intents/open` returns `recent` with a state word; the welcome page lists them. 9 not done: a pending statement has no stored fact to trail; needs a trail kind "document" in A2. 10 left (note only, honest). 11 left: old skill folders are aliased and `test_e0b1` pins `skills/data`.

Also: `skills/span/questions.md` regained the "Default:" lines (test_a1); `test_x5` expects North's new heading; `l2_proposals._write` keeps creation order (a same-second sort made `recent[-1]` flaky, test_l2); Flow-to-Span label updates in test_f1, test_t2, test_sf02; `pulsePage.test` expects the TICKETS tab the role table gives owners.
