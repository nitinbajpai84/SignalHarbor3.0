# Review: Fixes 2 (G1 gate) and T1b templates as documents (8 Oct)

**Summary.** Fixes 2 closes the self-join hole (`assigned_on` now needs a giver who holds "full" and is not the viewer; the run book needs live + ops seat + such a ticket) and gates or filters the six non-iid routes; the remaining leak is X5 handing out a K1-locked company document's lines to anyone with project read, and three of the new "filtered" assertions pass vacuously. T1b is sound on seeding, derived fields and the sign check, but a signed intent's companion template can still be switched (backend and UI), and `choose` pins a retired template where `switch` refuses one. Ship the gate; ship T1b after the two one-line fixes.

**Checks run.** `SH_MODEL_PROVIDER=off python -m pytest tests/v1 -q`: 122 passed (2:16). `cd ui && npx tsc --noEmit -p .`: clean. Read-only; no code edited.

## (A) Fixes 2, the gate

### Closed, confirmed by reading
- Self-join: `t2_tickets.py:482-496` counts a ticket only when the last raised/assigned/delegated entry's `by` is not the viewer and `G1.named_full` (team by name, or an enabled company admin) holds; `start:278-282` and `reassign:217-234` write `by = viewer.name` from the session, so a "read" person raising to themselves, or two "read" people passing a ticket between them, never promotes anyone. `f1_routes._gate:43` and `g2_routes._gate:21-28` both go through it; the run book additionally needs `stage == live` and the ops seat, so an Open project's "read" no longer opens it. `test_g1_gate.py:78-94` proves the self-raise and the non-live run book.
- `/consume` filtered by `can_read_intent` (`c1_routes.py:17`); `/consume/offers` and `.../have` gate `intent`/`intent_id` and the newest-intent default (`c2_routes.py:27-36`); `/extract/queue` filtered, `/extract/{doc_id}` gated on the record's intent (`x5_routes.py:97-116`); `/ops/tickets` gates `pid` with 403 (`p5_routes.py:33-39`); `/ops/live` filtered (`p5_routes.py:27`).
- The walk (`test_g1_gate.py:19-41`) asserts 403 on every `{iid}` route, never 404, and counts 40+ gate sentences: it does prove the path-keyed routes. The new T1b route `PUT /intents/{iid}/template/{kind}` is caught by it (the literal `{kind}` still matches) and by `intent_gate` as a write ("full").

### Should fix
**A1. X5 reads a K1-locked document for anyone with project read.** `x5_extract.detail:597-604` reads `rec["file"]` straight from `documents/` via `_lines`; neither `x5_routes.detail:108-116` nor `run:538` asks `c4_library.readable`/`k1_access.can_read`. Scenario: Arjun marks `documents/board-pack.md` Confidential in K1 (grants only); Leela, on the project team but with no grant, GETs `/api/v1/extract/{doc_id}` and receives every line of the document, and can run a new extraction on it. This is what the builder meant by "project read but not K1 readable"; it is what a person can see that they should not. Smallest fix: in `x5_routes.detail` (and `run`), look the file up in `c4_library._index` by `path` and `raise Refused(403, ...)` when `not L.readable(item, viewer)`; one helper, two call sites. Pre-existing (X5 predates K1), so not a blocker for the gate.

**A2. Three of the "filtered" assertions prove nothing.** `test_g1_gate.py:104-105`: the Restricted intent from `_restricted` is unsigned, has no extraction and its project is not live, so `c1_cards.build:100` (`signed_sows`), `x5_extract.queue:593` (`status == review`) and `p5_handover.board:204` (live projects) never list it with or without the filter. Fix: pick an intent that `signed_sows(plane)` already lists, restrict its project, and assert it drops from `/consume`; for the queue and the board, write one `review` record and one live project (or assert the filter directly with a stubbed list). The four 403 assertions on line 101-103 are real.

### Notes
- `assigned_on:494` tests `by not in AGENTS`, but `AGENTS` is a dict keyed `"watcher"` while history entries carry `"Watcher"` (`p5_handover.py:188`, `t2_tickets.py:30`); the agent branch never fires. Fail-closed, so harmless; use `AGENTS.values()` if agent-given tickets are meant to join someone.
- `named_full` matches by name: two accounts with one name share the giver's standing. `_me` guards the viewer side only.
- The positive run-book path (live project, ops seat, ticket from the builder, then `G1.join` as "ops") has no test; `test_g1_gate.py:93-94` covers only the refusals.
- Still open from the re-check, as declared: 7 (pick-up widens Internal without the owner; say so in `G1.md`), 8 (`_OPEN_PATHS` substring match, `g1_access.py:156`), 10 (every sponsor on every new team).

**Verdict: ship the gate to 8400, yes.** A1 is X5's, not G1's, and the gate itself holds; do A1 and A2 in the next round.

## (B) T1b, templates as documents

### Confirmed
- Seeding: `ensure:172-178` keyed on `seed == 2`, `_seed:152-169` writes only missing records and renames seeded-only ones; per company through `_p(plane, ...)`; `test_t1b.py:56-70` runs it twice on two companies.
- Derived fields: seeds (`_record:129-137`), admin `edit:352-373` (sections -> `fields_from`, or fields -> `sections_from_fields`) and `with_sections:183-187` for old records all keep one `fields` list, so `goals_from:412-425`, `required_keys:428` and `missing_required:450-466` read the same keys as before; `required` comes from the section (`t1_seeds.py:30-42`).
- Sign check: `sign_block:533-544` reads the pinned intent template at its pinned version (immutable: `choose:482-496` returns an existing pin) plus the companions the pin names; drafts cannot be pinned (`template_for:212-227` gives None at version 0); `i4_sow.t1_block:75-87` fails closed. An old record (no pin) is not checked, as documented.
- Who may switch: `PUT /intents/{iid}/template/{kind}` is a write, so `intent_gate` demands "full" on the project; yaml allows admin, sponsor, analyst. A "read" grantee cannot switch. Content: `switch:499-512` writes only `template.json`; the SOW is untouched, so nothing signed is dropped (`test_t1b.py:132-150`).
- Exports: `/sow/download` sits under `/intents/{iid}` (gate, "read"); `p1_project.export:404-415` is behind `export_allowed`. `t1_layout` renders only SOW slots and `template_fields`; the `from` file names are the SOW's own sources. Nothing beyond the SOW reaches an export.

### Should fix
**B1. A signed intent's companion template can still be switched.** `t1_templates.switch:499-512` never reads `sow["state"]`; `i4_sow.py:102-103` freezes the SOW but `template.json` is a separate file. UI: `ConversationPage.tsx:237,240` passes `onSwitch` whatever `canEdit`, so the select stays live after signing. Scenario: Priya signs; Leela (team) switches the process map from Swim lane to Step list; the signed intent's Markdown/Word/xlsx export now carries different headings and drops the "Hand-overs" section (still in the SOW, no longer shown). Rule 7 says signed is read-only. Fix: in `switch`, `if record_for_intent(plane, iid).get("state") == "signed": raise Refused(409, "The intent of work is signed. Its templates can no longer change.")`; in `ConversationPage.tsx` pass `onSwitch={canEdit ? ... : undefined}`.

**B2. `choose` pins a retired template; `switch` refuses one.** `choose:489` calls `template_for(plane, "intent_of_work", template_id)`, which returns the last adopted snapshot of a retired record (`template_for:216-220` checks kind only); `switch:504` adds `_working(...).state != "adopted"`. Scenario: the admin retires "Quick data request" because it asks too little; a sponsor who knows the id PUTs `/intents/{iid}/template {template_id: "quick-data-request"}` and starts on it (the welcome no longer offers it, `listing:252-266`). Not a sign-around of anything the company never adopted, but it is the admin's retirement being ignored. Fix: the same one-line state check in `choose`.

### Notes
- Switching a companion to a looser adopted template (Swim lane -> Step list drops "Lanes and steps" as required) is by design and admin-approved; `T1b.md` says so. Likewise `template_fields[key]` free text satisfies a required table section (`missing_required:462`, I4 `edit:111`): the text shows in the layout, so it is not hidden; pre-T1b behaviour.
- `adopt:385` and `retire:402` rewrite `settings.json` without the `seed` key, so the next read re-runs `_seed` (writes nothing, re-reads every file and rewrites the sample company's examples). Cost only; keep the key with `{**_read(settings), "standard": ...}`.
- `switch:505` calls `choose(plane, iid)` for an old intent, which pins the standard and from then on applies its required sections to a record that began without them. Intended, worth a sentence in `T1b.md`.
- `layout:151` offers `choices` (every adopted template of the kind) to any reader; company-wide names only, fine.

**Verdict: ship T1b, yes, after B1 and B2** (three lines, no new tests needed beyond one assert each).

## Fixes (8 Oct)
- B1: `t1_templates.switch` refuses a signed intent (409); `ConversationPage.tsx` passes no `onSwitch` once signed, so the select is hidden. Test: `test_t1b.py::test_signed_intent_and_retired_template_cannot_be_pinned_or_switched`.
- B2: `choose` refuses a retired template as `switch` does (same test).
- A1: `x5_routes.detail` looks the file up in the library index and, when `c4_library.readable` is false, returns the lock and preview only (`lines: []`, `locked: true`). `run` not changed. Test line in `test_x5.py`.
- A2: `test_g1_gate.py` now signs the Restricted intent, writes a review record and takes the project live, asserts each would be listed, then asserts it is absent for the off-team viewer (the board as the engineer, since the ops seat reads a live project).
- Note: `adopt` and `retire` keep the `seed` key in `settings.json` (asserted after retire).
