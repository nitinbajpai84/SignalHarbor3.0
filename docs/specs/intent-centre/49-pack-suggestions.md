# 49. Industry pack suggestions for the Intent Centre

Part of: Intent Centre v2. Depends on: 01 (intent record), 02 (types catalogue), 03 (chooser), 05 (areas), 18 (empty states), 25 (North suggestion cards), 38 (weekly check-in setup). Feeds: 03 (first intents on the chooser), 04 (home), 18 (first-run cards), 22 (initiative start hints), 38 (check-in question suggestions).

## Purpose (three sentences)

A new company opens an empty Intent Centre, and the industry pack gives it a head start: a few first intents, areas, check-in questions, start question hints, and the problems and measures the industry usually works on. Everything the pack offers is drawn dashed and carries the label held in the existing `SUGGESTION_LABEL` constant, whose value for this surface is the brief's phrase "Suggested from what others in the industry usually do" (open question 3); it is never company policy, never counted and never stored as the company's own until a named person picks it up. A company with no pack sees an honest empty state, never another industry's content (rule: the industry is a parameter).

## Who uses it and when (role, moment, trigger)

| Role | Moment | Trigger |
|---|---|---|
| Company admin (Grace, first person in a new company) | First sign-in, no intents yet | Opens `/centre/intent`; the "Suggested first intents" strip shows under the five type cards |
| Organiser (Janet) | Starting an intent | Opens `/centre/intent/new?type=<type>`; a hint line sits under each start question that has one |
| Organiser of a Weekly check-in (Harvey for operations) | Setting up the check-in | Opens `/centre/intent/new?type=pulse` (38); a "Suggested questions" panel sits beside the question list |
| Company admin | Setting up departments | Suggested areas panel (owned by 05); this file only fixes where the data comes from |
| Any participant on the wall | Blank lane | Sees North's dashed pack cards (owned by 25) |
| North (agent) | Builds the strip, hints and cards | Reads the pack through the loader; nothing is generated |

## Entry points (every route, link, Pulse line, button that leads here)

- `/centre/intent` (home, 04): strip "Suggested first intents" under the type cards. Shown to the company admin and to any organiser. Hidden once the viewer has dismissed or picked up every card; shown again only through the link "Show suggestions again".
- `/centre/intent/new?type=<type>` (03 and 22): hint line under each start question that has one.
- `/centre/intent/new?type=pulse` (38): panel "Suggested questions" next to the check-in question list.
- First-run cards (18): the same strip, same loader call, same marks.
- Suggested areas (05): panel owned by 05, data from `areas.yaml` (this file fixes only the loader).
- `/centre/intent/<id>/wall` (23, 25) and a Brainstorm session (36): North's pack cards come from the same loader call.
- No Pulse line. A suggestion never asks for anyone's attention; Nira does not list it under "waiting for you".

## Screens, element by element

### Screen 1. Suggested first intents strip (on 04 and 18)

Route `/centre/intent`. At 1280: one row of dashed cards under the type cards, label above the row, "Show suggestions again" link at the right. At 390: cards stack one per row; the label stays above; buttons are full width; the preview panel opens as a bottom sheet.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Strip label | agent line | `SUGGESTION_LABEL` (value "Suggested from what others in the industry usually do") and under it the pack label from `pack.yaml`, for example "Family office, version 1, illustrative" | None | Company admin and any organiser | Strip not drawn when nothing is left to show; see the empty company below |
| Suggestion card | list item, dashed border, muted text | Type chip (Initiative, Weekly check-in, Decision), title, purpose in one line, areas as chips, line "Why others start here" from `why` | Whole card opens the preview panel | Same | Not drawn |
| Start this | button | "Start this" | Opens `/centre/intent/new?type=<type>` with title, purpose and areas filled as a draft; the suggestion id travels in page state (open question 7). Nothing is saved until the person presses the chooser's create button ("Open this intent", 18) | Only people allowed to create that type (06); others see the card as text | Not drawn |
| Not for us | button | "Not for us" | Hides the card for this person and writes a dismissal; asks nothing | Company admin and organisers | Not drawn |
| Preview panel | panel | The start answers the pack would pre-fill, each marked "Suggested" | Closes with its Close button | Same | Not drawn |
| Close (preview) | button | "Close" | Closes the preview panel, nothing written | Same | Not drawn |
| Show suggestions again | link | "Show 2 dismissed suggestions" (count of this person's dismissed rows) | Deletes this person's dismissal rows; cards return | Same | Not drawn when the person has no dismissals |
| Source chip | chip | "Pack: Family office, version 1" | Opens a popover with pack label, status (proposed or adopted) and, when the pack says so, "Illustrative, not reviewed by a practitioner" | Same | Not drawn without a pack |

### Screen 2. Start question hints (on 03 and 22)

Route `/centre/intent/new?type=<type>`. At 1280: one muted line under the question field, dashed underline, button to its right. At 390: line and button stack under the field. A hint never fills the field.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Hint line | agent line | "Others often say: Report to the family each quarter with one set of numbers." then the chip "Suggested" | None | The organiser starting that type | No line when the pack has no hint for that question |
| Use this wording | button | "Use this wording" | Copies the hint into the field as a draft answer; it counts as stated only after the person presses Next | Organiser | Not drawn without a hint |
| Hide suggestions | toggle | "Hide suggestions" | Hides all hints for this person on this device for this session | Organiser | Not drawn when no hint exists for the type |

### Screen 3. Suggested check-in questions (on 38)

Route `/centre/intent/new?type=pulse`. At 1280: panel to the right of the question list. At 390: panel collapses under the list to a bar "Suggested questions" that opens on tap.

| Element | Kind | Shows | On click or change | Visible to | State when empty |
|---|---|---|---|---|---|
| Suggested questions panel | list, dashed rows | Questions for the chosen area, each with the suggestion label | None | Organiser of the check-in | "No suggested questions for this area. Write your own." With no pack: "No industry suggestions are available for your industry yet." |
| Add to my check-in | button | "Add to my check-in" | Appends the text as the organiser's own question (an ordinary question; source kept in `from_pack`); the row leaves the panel | Organiser | Not drawn |
| Not for us | button | "Not for us" | Hides the row for this person and writes a dismissal | Organiser | Not drawn |

### Screen 4. North's problem and measure cards (on the wall)

Route `/centre/intent/<id>/wall`. Layout at 1280 and 390 is 25's. Rows come from `problems.yaml` and `kpi_tree.yaml`; measures appear as a name only, never a target or a figure (25). This file adds only the loader call `suggestions_for(pack, "wall", lane)` so 25 and this file share one path. Elements, click behaviour and empty states are 25's (dashed card, "Pick up", source line).

### The empty company with no pack

Route `/centre/intent`. At 1280 and 390 the strip is replaced by one quiet line (agent line, not dashed). Its text is the existing `EmptyPack.message`: "No industry knowledge is available yet for this industry. You can still work from your own company's information." The five type cards, start questions without hints and the check-in editor without a suggestions panel all work. Nothing from another industry appears anywhere.

## User journey (numbered steps from arriving to leaving, with what the agent does between the person's steps)

1. Grace opens `/centre/intent` in a new Ardmore workspace. No intents exist.
2. North reads the company's industry from the profile, loads the pack, reads `intents/first_intents.yaml`, drops any card Grace dismissed or already picked up, and shows the rest. It generates no text.
3. Grace reads "Report to the family on one page every quarter" and presses Start this.
4. The chooser opens at `/centre/intent/new?type=initiative` with title, purpose and areas pre-filled as a draft, each marked "Suggested" until she presses Next.
5. Under the build question a hint reads "Others often say: yes, if reports are rebuilt by hand every quarter." Grace ignores it and answers "not sure".
6. Grace presses "Open this intent". Only now an intent record exists, with `from_pack` set. North writes the pick-up mark; the card leaves Grace's strip.
7. Later Harvey sets up the Weekly check-in for operations and presses "Add to my check-in" on two suggested questions. They become his own questions.
8. Janet presses "Not for us" on the "Decide whether to consolidate custodians" card. It stays hidden for her; Grace still sees it.
9. A second company in the asset management pack opens the same screen and sees only that pack's cards. A third company with no pack sees the honest line.
10. Grace leaves the home screen by opening her new intent at `/centre/intent/<id>`. Suggestions play no further part.

## States and transitions (table: state, who moves it, to what, what is written)

A suggestion has its own small state per person. It is not an intent state and never reaches the intent record's `state`.

| State | Who moves it | To what | What is written |
|---|---|---|---|
| offered (derived, not stored) | North on render | shown | Nothing |
| picked up | The person, by Start this then "Open this intent" (or Add to my check-in) | gone from strip | Row in the person's marks file with `mark: picked_up`, `intent_id`; the new intent carries `from_pack` |
| dismissed | The person, by Not for us | hidden for that person | Row with `mark: dismissed`, `at` |
| restored | The person, by Show suggestions again | offered | Dismissal rows for that person deleted from that person's marks file (the one place a mark is removed; the intent record is never touched) |
| abandoned draft | The person leaves the chooser without creating | offered again | Nothing; the draft was never saved |
| stale | The pack version changes and the row id is gone | not shown | Mark kept, harmless; nothing counted |

## Records read and written (file or route, fields; mark Existing or New)

| Record | Use | Fields | Mark |
|---|---|---|---|
| `packs/<industry>/<v>/pack.yaml` | Read: label, status, `illustrative` flag | `label, status, illustrative` | Existing |
| `packs/family_office/1/problems.yaml`, `kpi_tree.yaml`, `intent_examples.yaml` | Read: wall cards (25) | As today | Existing |
| `packs/<industry>/<v>/areas.yaml` | Read: suggested areas (05 owns the shape) | `areas: [{id, name, kind, note}]` | New (defined in 05) |
| `packs/<industry>/<v>/intents/first_intents.yaml` | Read: suggested first intents | `suggestions: [{id, type, title, purpose, areas: [area id], why, start_answers: {q: text}}]`; `type` is a record key: initiative, brainstorm, pulse, problem or decision (shown as "Weekly check-in" for `pulse`) | New |
| `packs/<industry>/<v>/intents/start_hints.yaml` | Read: hints per type and question | `hints: {initiative: {1: text}, decision: {...}}`; the number is the question's `order` in 02 | New |
| `packs/<industry>/<v>/intents/checkin_questions.yaml` | Read: suggested check-in questions | `questions: [{id, area, text}]`; `area` is a pack area id or `any` | New |
| `sh_platform/packs.py` | Add `Pack.intents_section(name)` and `EmptyPack.intents_section(name)` | Reads `intents/<name>.yaml`; same cache | Existing file, small addition |
| `sh_platform/intents/pack_suggestions.py` | `suggestions_for(pack, kind, viewer, marks)` returns cards with `label`, `source`, marks filtered | See Agent behaviour | New |
| `intents/_suggestion_marks/<person_id>.json` in the company plane, via `sh_platform/jsonfile.py` | Read and write marks | `{marks: [{suggestion_id, pack: "family_office@1", mark: picked_up\|dismissed, intent_id\|null, at}]}`; `at` in the company time zone from the profile, else UTC | New |
| `GET /api/intents/suggestions?kind=first&type=` | Strip data | `{label, pack: {industry, version, label, illustrative}\|null, items: [...], dismissed_count, empty_message\|null}` | New |
| `POST /api/intents/suggestions/{id}/dismiss` and `POST /api/intents/suggestions/{id}/restore` | Marks | Same row shape | New |
| `GET /api/intents/hints/{type}` | Hints for one type | `{label, hints: {q: text}}` | New |
| `intents/<id>/intent.json` | Written only on create, by 01's route | adds `from_pack` | Existing record (01), new field |

### Final pack file names (one table, so 18 and 38 can match)

All under `packs/<industry>/<v>/`. Version folder is flat except `intents/`. File 18 calls the first-intents file `intent_starters.yaml`; the final name is `first_intents.yaml` (18's own body already uses it).

| Path | Owner | Read by | Loader call |
|---|---|---|---|
| `areas.yaml` | 05 | 05, 49 | `section("areas")` |
| `intents/first_intents.yaml` | 49 | 04, 18, 49 | `intents_section("first_intents")` |
| `intents/start_hints.yaml` | 49 | 03, 22, 35, 41, 43 | `intents_section("start_hints")` |
| `intents/checkin_questions.yaml` | 49 | 38 | `intents_section("checkin_questions")` |
| `problems.yaml`, `kpi_tree.yaml`, `intent_examples.yaml` | existing | 25 | `section(name)` |

### Pack content (synthetic, illustrative; family office)

`intents/first_intents.yaml` (three cards):

| id | type (key) | title | purpose | areas |
|---|---|---|---|---|
| fo-initiative-family-reporting | initiative | Report to the family on one page every quarter | One trusted set of numbers for the family instead of several files | reporting, investments |
| fo-checkin-operations | pulse | Weekly check-in for operations | Hear each week what ran, what broke and what is on people's minds | operations |
| fo-decision-custodian | decision | Decide whether to consolidate custodians | Record one decision on custodian consolidation with the options considered | operations, investments |

`intents/start_hints.yaml` examples: Initiative question 1 "Report to the family each quarter with one set of numbers"; Initiative build question "Others often say yes when reports are rebuilt by hand each quarter"; Decision options question "Others often list: keep as is, consolidate to one, consolidate to two".

`intents/checkin_questions.yaml` examples (area operations): "Which capital call notices arrived this week, and were they seen in time?"; "What did you rebuild by hand that you did not expect to?"; "What is on your mind that you have not said yet?"

## Fields this feature adds to the intent record

```
intent.from_pack: {
  pack: "family_office@1", suggestion_id, kind: first_intent|checkin_question|hint,
  edited: bool      # true when the person changed the suggested text before create
} | null
```

`from_pack` is provenance only. It is `null` for an intent the person wrote from scratch, and no behaviour depends on it. It is read-only after create. It renames no field of the brief's section 3.

## Agent behaviour (North, Lens, Nira: what each drafts, when, and the moment a person acts)

- **North** assembles the strip, the hints and the check-in suggestions. It reads the company's industry from the profile, never from the request, loads the pack through `PackLoader`, filters by the person's marks and role (an organiser sees first intents; a participant sees none on the home page), and returns the cards. Text is read as written in the pack; nothing is generated. The person acts at Start this, Use this wording, Add to my check-in and Not for us. North never creates an intent, never fills a field on its own and never changes an answer. How many cards, hints and questions it returns is open question 1.
- **North on the wall (25)** keeps its own cap and drop rules.
- **Lens** is not used. A suggested area (05) is accepted by the company admin only.
- **Nira** writes nothing about suggestions.
- No agent signs, creates or accepts. A named person does.

## Rules (visibility, time box, who may do what)

1. Pack content is always shown with `SUGGESTION_LABEL`, dashed, with the pack name and version in the source chip. It is never styled as the company's own.
2. A suggestion is not an intent, not a card, not a participant's answer. It is not counted in any counter, not listed in search (15), not shown to a super admin (existence rule, brief section 4 and ruling 5), not in the audit trail until picked up. The pick up is the create press, which writes the intent and its audit line.
3. Dismissals are private to the person. They do not hide the card from anyone else and are not visible to the company admin.
4. The industry comes from the signed-in company's profile only. A request that names another industry is ignored. A missing pack, missing file, unreadable file or version the loader does not know returns `EmptyPack` behaviour or an empty list, never a default pack.
5. Suggested text is words only: no figures, no targets, no thresholds, no real names. Sample content in the family office pack is synthetic and flagged `illustrative: true`.
6. A suggestion carries no time box. The type's default time box (02) applies from create, as for any intent.
7. Hint text and suggested answers are copied into a field only by a button press, never on load.
8. Who may do what: any signed-in company person sees hints and may dismiss their own cards; only people allowed to create an intent of that type (06) may press Start this; only the company admin accepts suggested areas.
9. Files in `intents/` carry no permission keys, no roles, no agent or vendor names and no company names; the pack test fails on any of these.
10. Licensed or outside material is never put in `intents/`; it arrives through the tool registry (`industry.md`).
11. On screen the check-in type is "Weekly check-in"; the word "pulse" appears only as the record key in pack files and never in copy (ruling 3).
12. A draft started from a suggestion is visible only to the person who started it (ruling 14) and exists only after create.

## Counters and measures of this feature (numbers only, each traced to a record)

| Measure | Source | Where shown |
|---|---|---|
| Suggestions offered to a person | Derived at render from the pack file minus marks; not stored | Not shown as a number; the strip shows cards |
| Intents started from a suggestion, by pack | Count of intents with `from_pack != null`, grouped by `from_pack.pack` (exact count) | Company admin home line: "4 intents started from industry suggestions" |
| Of those, edited before create | `from_pack.edited` true (exact count) | Same line, second figure, only when the first is 1 or more |
| Dismissed, per person | Marks rows with `mark: dismissed` in that person's file | The "Show 2 dismissed suggestions" link, to that person only |
| Pack present or absent | `PackLoader.load(...).empty` | Strip label or the empty line |

Where no intent has `from_pack`, the line is not drawn. The screen never shows 0 as if it were a finding. The "4" above is example copy, not data.

## Reuse check (what exists today: file paths and line ranges found with graft; copied, reshaped or not used, and why)

Paths below were checked to exist on 7 October 2026.

| What | Where | Verdict |
|---|---|---|
| Pack folder layout `packs/family_office/1/` (`pack.yaml`, `problems.yaml`, `kpi_tree.yaml`, `intent_examples.yaml`, `north.yaml`, `roles/`) | `packs/family_office/1/`, `packs/README.md` | Existing, kept. New files go in the same version folder; `areas.yaml` flat, the rest in `intents/` |
| `Pack`, `EmptyPack`, `PackLoader`, `SUGGESTION_LABEL` | `sh_platform/packs.py` lines 9 to 98 | Reused. `Pack.__init__` lists only files directly in the folder (lines 22 to 28), so `intents/` is not seen today. Reshaped: add `intents_section(name)` through the same `_read_section` cache (lines 42 to 46). `EmptyPack.intents_section` raises KeyError like `section` (lines 63 to 64). `SUGGESTION_LABEL` value differs from the brief's phrase today (open question 3) |
| Empty pack message | `sh_platform/packs.py` lines 53 to 58 | Reused word for word for the empty company |
| Unknown industry or version returns `EmptyPack` | `sh_platform/packs.py` lines 85 to 93 | Reused; the guarantee behind rule 4 |
| `PackLoader` on the app | `sh_platform/app.py` lines 31 and 52 (`request.app.state.packs`) | Reused |
| Defensive pack read returning empty on error | `modules/m1_intent/tools/pack_tools.py` lines 82 to 95 (`kind_suggestions`) | Reshaped: `pack_suggestions.py` catches KeyError, OSError, ValueError, YAMLError, logs, returns empty |
| Dashed suggestion card with source line and pick up button | `ui/src/modules/m1_intent/wall/Card.tsx` lines 79 to 90; `wall.css` line 53 (`ds-wall-card--suggestion`) | Copied as the visual pattern; the strip card adds type chip, areas and Not for us |
| Pick up on the wall | `ui/src/modules/m1_intent/wall/WallScreen.tsx` lines 116 to 119 | Same pattern, different call: here pick up opens the chooser and writes no card |
| "Industry practice (suggestion)" prefix and chip | `ui/src/components/MessageBubble.tsx` line 6; `ui/src/modules/m1_intent/copy.ts` line 405 | Not used for the strip (the strip takes `SUGGESTION_LABEL`); kept for wall chat text |
| Per-person mark files | `sh_platform/jsonfile.py` | Reused for the marks file |
| Nothing reads `packs/<industry>/<v>/intents/`, first intents, start hints or check-in questions | Searched `intents`, `first_intent`, `start_hint`, `checkin` across `sh_platform`, `modules`, `packs` | New: three pack files, one small module, one marks file, three routes |

### Test plan (two industries and an empty company)

New file `tests/intents/test_pack_suggestions.py`. Fixture: Ardmore family office, a second company on `asset_management` with its own small `intents/` files, and an empty company (industry with no pack folder). Packs root is a temporary folder.

1. `test_family_office_strip`: cards each with label, type chip and source; no figures.
2. `test_second_industry_own_content`: no family office id appears in the asset management response.
3. `test_empty_company`: `pack: null`, no items, the exact `EmptyPack.message`; hints and check-in routes return empty lists, not 404.
4. `test_unknown_industry_or_version`: another industry in the query is ignored; version 99 returns the empty answer.
5. `test_never_counted_until_picked_up`: offering and dismissing change no intent count; create from a suggestion raises the `from_pack` count by one; an abandoned draft changes nothing.
6. `test_dismiss_is_private`: Janet's dismissal does not hide the card from Grace; the company admin cannot read Janet's marks.
7. `test_hint_never_prefills`: loading the chooser leaves every field empty until Use this wording is pressed.
8. `test_pack_files_clean`: every `intents/*.yaml` parses, has no key named like a permission or agent vendor, and `illustrative` packs say so.
9. `test_loader_intents_section`: `Pack.intents_section` reads and caches; `EmptyPack.intents_section` raises KeyError; a missing `intents/` folder gives an empty list.
10. Screenshot check against the artboard for the strip at 1280 and 390, dashed border visible, label present.

## Not in this feature

- The shape of areas and the accept flow (05).
- The wall's card cap, pick up and drop rules (25).
- The check-in question editor and its recurrence (38).
- The start question list and wording (02, 22, 35, 41, 43).
- Writing or editing pack files from the product. Packs change by a reviewed pack release.
- Learning from one company into the pack (the distillation gate in `packs/README.md`).
- Licensed industry data and knowledge connectors.

## Open questions

1. How many cards, hints per question and check-in questions per area may North return? The brief gives no number. This draft assumes three first intents, one hint per question and five check-in questions per area; the product owner should confirm.
2. Should a participant (not an organiser) see the strip? Shown here to the company admin and organisers only.
3. `SUGGESTION_LABEL` in `sh_platform/packs.py` today reads "What others in the industry usually track (a suggestion, not your company's own definition)", not the brief's phrase. Changing its value to the brief's phrase is a one-line edit outside this file. Align the wall chip text ("Industry practice (suggestion)") in the same pass?
4. Who reviews the first-intent text in the family office pack before status moves from proposed to adopted?
5. Are dismissals per person (as here) or per company?
6. After a pack version upgrade adds new suggestions, should the strip return for a person who dismissed everything? Here only restored suggestions return; new ids are offered.
7. The chooser needs the suggestion id to set `from_pack`, but ruling 1 gives only `?type=` and `?from=<id>` (18 asks the same). Page state is assumed; a new query parameter would need a ruling.
8. Hints are keyed by question `order` because 02's keys are not final. A key is safer if questions are reordered.
9. The create button is called "Open this intent" in 18; confirm that is the chooser's final label (03).
10. The check-in question panel assumes the question list sits at `/centre/intent/new?type=pulse`; confirm with 38.
11. Check-in questions have no item kind (`ran`, `broke`, `thought`). Should a suggested question carry one?
12. The suggestion marks file sits in `intents/_suggestion_marks/`, beside per-intent folders (ruling 12). Confirm with 01 that an underscore folder is acceptable.
13. Suggested areas are read by 05 from a flat `areas.yaml`; 05's page route is outside the `/centre/intent/...` convention and is 05's question.
