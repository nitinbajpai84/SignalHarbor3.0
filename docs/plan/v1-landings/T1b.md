# T1b Templates as documents you choose, which North then fills

Summary (five lines):
1. Every company now has two templates per output kind (benchmarks keeps one): Reporting automation / Quick data request, Swim lane / Step list, KPI glossary / KPI cards, and a full and a short version of system design, data model, build pack, run book and consumption brief. Seeding tops up companies seeded before T1b and is idempotent (`settings.json` carries `seed: 2`).
2. A template is now an ordered list of sections (heading, grey instruction, example, required, type, columns, view); `fields` are derived from the sections, so `goals_from`, `required_keys` and the sign check read the same keys as before. Records written before T1b get their sections derived on read.
3. The welcome shows visual template cards (thumbnail drawn from the sections, "Comes with" companions, Preview of the whole skeleton); the intent template names its process map and definitions templates, pinned with the intent.
4. The three workbench documents open pre-laid-out from the pinned templates: grey instructions, examples and empty tables; North's patch fills the matching section (the highlight stays until "Looks right"); the process map and definitions template switch from a select at the top of the document, content kept.
5. Signing names any required section still grey (companions named with their document); download as Markdown, Word (real tables, headings) and spreadsheet keeps the template's layout.

## Reuse check
- 2.0 swimlane: the existing `ui/src/v1/i6/Swimlane.tsx` (copied from 2.0 in I6b) is reused as the "swimlane" view; nothing new copied from 2.0.
- Reused here: `t1_templates.py` (records, versions, seeds, `goals_from`, `check_sign`, `choose`, `for_intent`), `i6_chat.merge` (North's patch already writes the SOW slots and `template_fields[key]`; the layout reads them, so no second copy of the content exists), I4's `edit` PUT for line edits (`section: "template_fields"` was already allowed), I4's docx/md download, openpyxl for the spreadsheet.
- New: `t1_seeds.py` (the section data of every seed), `t1_layout.py` (layout and the three exports), `ui/src/v1/t1/DocumentLayout.tsx`, `TemplateCards.tsx`, `templates.css`, `ui/src/v1/i6/Line.tsx` (the old inline `Line`, moved out so both pages share it).

## What landed (files)
Backend
- `sh_platform/v1/t1_seeds.py` (new), `sh_platform/v1/t1_layout.py` (new).
- `sh_platform/v1/t1_templates.py`: sections derived on read (`with_sections`), `_seed` writes only what is missing, `ensure` keyed on `seed` version, `choose` pins companions, `switch(plane, iid, kind, template_id)`, `for_intent(plane, iid, kind)`, `companions_of`, `sign_block` checks the intent template and both companions, `missing_required` knows the slots of the process map and definitions, admin `edit` accepts `sections` (or `fields`, from which sections are rebuilt), summaries carry `outline` and `companions`.
- `sh_platform/v1/t1_routes.py` + `t1.permissions.yaml`: `PUT /api/v1/intents/{iid}/template/{kind}` {template_id} (company_admin, sponsor, analyst).
- `sh_platform/v1/i6_chat.py`: `view()` now also returns `layout` (null if it cannot be made).
- `sh_platform/v1/i4_sow.py`, `i4_routes.py`: download takes the layout (Markdown, Word, new `format=xlsx`); an intent with no pinned template still gets the plain eight sections.
- `sh_platform/v1/p1_project.py`: the intent artefact's Markdown/Word export uses the layout (the spreadsheet stays refused for the intent, as test_p1 expects).
- Tests: `tests/v1/test_t1b.py` (6 tests).

UI
- `ui/src/v1/t1/api.ts` (types, `switchTemplate`), `DocumentLayout.tsx`, `TemplateCards.tsx`, `templates.css`, `t1b.test.tsx` (2 tests).
- `ui/src/v1/p3/IntentWelcome.tsx`: template cards replace the radio list (examples kept).
- `ui/src/v1/i6/ConversationPage.tsx`, `api.ts`, `Line.tsx`: the three documents render from `chat.layout` when present, else the previous plain sections.

## How to test by hand
1. Sign in as Arjun Mehta (company_admin) on `neera`, open `/centre/intent`. Under "Start from a template" you see two cards, "Reporting automation" (marked as your company's standard, selected) and "Quick data request", each with a thumbnail and "Comes with: ...". Click Preview: the whole skeleton opens, with grey instructions, examples and empty tables.
2. Pick "Quick data request", type a first line, Start. The workbench opens with the three documents already laid out: Intent of work (What is needed and why, By when, The figures wanted, Where the data is, Who may see it, Anything else), Process map (Step list) and Definitions (KPI cards). Required grey sections carry a "Required" tag; the bar says how many are still to fill in.
3. Talk to North. As it learns the figures, sources and rules, the matching section turns from grey to content, highlighted with "North just filled this in. Looks right"; sources read from a file say "From <file>". The same figures also appear in Definitions.
4. On the Process map, change "Template" to Swim lane (and back): the steps stay; only the layout changes. Same for Definitions (KPI glossary / KPI cards).
5. Hand to the architect and try to sign while a required section is grey: the message names it ("Still to fill in: The figures wanted; ..."; companion sections read "Process map: Lanes and steps").
6. Download a copy: `/api/v1/intents/<iid>/sow/download?format=md|docx|xlsx` shows the template's headings, tables and grey instructions for empty sections.

Tests run: `SH_MODEL_PROVIDER=off python -m pytest tests/v1` 122 passed (6 of them the new `tests/v1/test_t1b.py`); `npx tsc --noEmit` clean; `npx vitest run src/v1/t1 src/v1/i6 src/v1/p3 src/v1/workbench` 15 passed.

## Shared edits needed
None for the orchestrator: no change to app.py, route_permissions.yaml, App.tsx, the shell or styles. The new route sits in T1's own permissions file.

## Open questions
- "What good looks like" on a KPI card has no slot in the SOW contract (a KPI has no such field). The card shows it as a grey example line; it is not stored. If it should be stored, the contract needs a `good` field on a KPI (and North's patch an instruction to fill it).
- "Highlighted until accepted under L2": the workbench's ChangeBar proposals (L2) are not wired for North's page, so the highlight is local to the page ("Looks right" per section, remembered until reload). Wire it to the L2 proposals when North's page uses them.
- "Pre-filled from the company page or library": North reads those and fills sections through its patch; the only "from <file>" marker is on sources North read from a file. A direct section-by-section prefill from the library before North speaks would need a rule for which library item answers which section.
- The admin console edits `fields`, which rebuilds the sections; a section editor (instruction, example, view) is not in the console yet (the API accepts `sections`).
- A companion template only blocks signing when the intent template names it or the person switched it (a custom intent template that names none is not held up by the standard process map).
- Quick data request's companions (Step list, KPI cards) do not require steps; switching its process map to Swim lane makes "Lanes and steps" required, as that template says.
