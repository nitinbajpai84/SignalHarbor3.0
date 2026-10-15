# Signal Harbor feature coverage matrix

As of 12 Oct 2026, product on main. Sources: `docs/plan/v6-landings/*.md` (ACT1, MAP1, CONS1, API1, FIX1, DM1, RUN1, V6*), `docs/plan/BUILD-FLOW-V6.md`.
Checked against: Deck (`docs/demo/showcase/index.html`, 16 slides), Run sheet (`docs/demo/showcase/RUN-SHEET.md`), User guide (`docs/guides/USER-GUIDE.md`), Film (`docs/video/SCRIPT-V4.md`), Demo data (the seeded demo).

Key: ✔ covered. partial = mentioned but thin, wrong or out of date. ✘ not mentioned. "tonight" = on the DEMO1 list, being added tonight (silver tables, TEST/PRODUCTION runs, live API rows, figure to confirm, model extension proposal, published dashboard in Reports, delivery in Operations). ONT1 and ROLE1 landing notes were not on disk at the time of writing, so ontology zoom and per-role menus are taken from code (`OntoGraph.tsx`, `roles.ts`) and are marked as such.

## Action

| Feature | Deck | Run sheet | User guide | Film | Demo data |
|---|---|---|---|---|---|
| One page: greeting, count chips, groups | partial: slide 8 lists groups, no chips | ✔ Action step (Raj) | ✔ group table | ✔ scene 9 | ✔ (act1 shot) |
| Cases to handle (take / open) | ✔ | partial: "open one case" | ✔ | partial | ✔ |
| Reconciliations; Close as timing | ✘ not named | ✘ | ✔ | ✔ cash break closed as timing (FIX1) | ✔ Entity B break, after reseed (FIX1 note: rebuild the film snapshot) |
| Statements to chase, Draft a follow-up (never sent) | ✔ one line | ✘ | ✔ | ✔ 63 business days late | ✔ |
| Figures to confirm (Confirm / Correct) | partial: "figures to confirm" in a bullet | ✘ | ✔ | ✔ revised NAV from a PDF | tonight: figure to confirm |
| Waiting for my approval (packs, plans, dashboards, deliveries, Map review) | ✔ | partial: not shown as a step | ✔ | partial | partial: packs and plans yes; Map review items for the head of data yes (19 waiting in the walk) |
| Done today (company day) | ✘ | ✘ | ✔ | ✔ "grows" | ✔ after FIX1 |
| Ask Tally, tickets, Since yesterday | partial: Tally only | ✘ | ✔ | ✘ | ✔ |

## Build

| Feature | Deck | Run sheet | User guide | Film | Demo data |
|---|---|---|---|---|---|
| Build landing, four steps, projects | ✘ | ✘ | ✔ | ✘ | ✔ |
| Intent with North (chat, SOW, process map, sign page, read-only after signing) | ✔ slide 4 | ✔ | ✔ | ✔ scene 4 | ✔ signed intent |
| Never ask twice (systems "from the intent", confirm) | partial: slide 5 "asks only what it does not know" | ✘ | ✔ | ✔ scene 5 | ✔ |
| Hand-over to the data engineer; builder card | ✘ | ✘ | partial: in the 21-step table | ✘ | ✔ |
| Architecture / design pack with Span (questions, samples, pack versions, mapping sheet, approve) | ✔ slide 5 | ✔ | ✔ | ✔ scene 5 | ✔ pack v2 approved |
| Pipelines / builder: connect, run on a copy | ✔ slide 6 | ✔ | ✔ | ✔ scene 6 | ✔ |
| Benchmark check against last month's report, send back to architect, pack v2 | ✔ slide 6 | ✔ | ✔ | ✔ | ✔ walkthrough numbers 4.17 / 2.71 / 1.46 |
| Go live (schedule from the pack, day shown, FIX1) | ✔ | partial: slide 6 only, no Go live click | ✔ | ✔ | partial: Operations "Live pipelines" shows "No pipeline is live yet" in a fresh test env |
| Dashboard studio: Lumen starter, Accept, Add something specific, Send for approval | ✘ | ✘ | ✔ | ✔ scene 8 | ✔ |
| Delete / archive drafts in the studio | ✘ | ✘ | ✘ | ✘ | ✔ in code (`StudioPage.tsx`: Delete this draft, Show archived drafts); seed has few drafts |
| Delivery channels (Consume, email digest; each approved) | ✘ | partial: "council email is a preview" | ✔ | ✘ | tonight: delivery in Operations |
| Operations: tiles, sources, live pipelines | ✘ | ✘ | ✔ | ✘ | partial: sources yes; pipelines "No pipeline is live yet" |
| Operations: Deliveries (email and Slack previews, outbox) | ✘ | ✘ | ✔ | ✘ | tonight |
| Operations: Runs with run IDs, TEST / PRODUCTION badge, steps | ✘ slide 12 says "being added" (now live) | ✘ run sheet says "being added" (known gap 9, now live) | ✘ | ✘ | tonight: TEST/PRODUCTION runs |
| Connect an API: Frankfurter, FRED, Finnhub, MAS (SGS yields) | ✔ slide 10 | ✔ | ✔ | ✘ | tonight: live API rows |
| Connect an API: test with real rows and timing, Save, Connectors list | partial | partial | ✔ | ✘ | tonight |
| Head of data approvals (pack, plan, Map review); maker never checks | partial: slide 12 | partial | ✔ | ✔ | ✔ Anita holds the seat |

## Consume

| Feature | Deck | Run sheet | User guide | Film | Demo data |
|---|---|---|---|---|---|
| Today (Morning Note, four numbers, what moved) | ✔ slide 7 | ✔ | ✔ | ✔ | ✔ cons1-today |
| Financial health (By portfolio / entity / fund, trust column) | partial: one bullet | ✔ | ✔ | partial | ✔ |
| Markets with FILE / LIVE API source tags | ✔ | ✔ | ✔ | ✔ market signals | partial: seeded rows read "Market data file (demo data)"; LIVE API rows tonight |
| Reports (library, shared with you, published dashboards) | partial: "approved dashboards" on slide 3 | ✘ | ✔ | ✔ approved dashboard appears | tonight: published dashboard in Reports |
| What if (attribution) | ✘ | ✘ | partial: one line | ✘ | ✔ page exists |
| USD / SGD switch | ✘ | ✘ | ✔ | ✘ | ✔ |
| Comments on the note, Ask Lumen | ✘ | ✘ | ✔ | ✘ | ✔ |

## Map

| Feature | Deck | Run sheet | User guide | Film | Demo data |
|---|---|---|---|---|---|
| Ontology, whole company graph, filters, node card | partial: slide 9 bullet | partial: "show Ontology" | ✔ | ✘ | ✔ |
| Ontology zoom (+ / − / Fit, ctrl-wheel, drag; code) | ✘ | ✘ | ✘ | ✘ | n/a |
| Process map | ✘ | ✘ | ✔ | partial: appears in intent | ✔ |
| Data model (bronze, silver, gold, impact "If this table changes") | partial: slide 9 says the impact view "is the graph today" (out of date, DM1 is built) | partial: "pick a silver table" | partial: marked "being added" (out of date) | ✘ | tonight: silver tables (alias views exist; the Loaded view needs silver rows) |
| Model extension: proposal shown / "Added for this office" | ✘ | ✘ | ✘ | ✘ | tonight: model extension proposal (DM1: a pending proposal is not drawn until approved) |
| Business glossary | partial: "Definitions" | ✘ | ✔ | ✘ | ✔ |
| Map review queue (head of data) | ✘ | ✘ | partial | ✘ | ✔ |

## Roles, settings and trust

| Feature | Deck | Run sheet | User guide | Film | Demo data |
|---|---|---|---|---|---|
| Roles and what each person sees (sponsor, business owner, head of data, data engineer, admin) | partial: slide 11 lists four roles | partial: four people, no menus | partial: role table, no per-role menus | partial: lower thirds | ✔ Daniel, Mei, Raj, Anita, Leo, Grace seeded; per-role menus pending ROLE1 |
| Data team only: Operations and full data model | ✘ | ✘ | ✔ | ✘ | ✔ |
| Settings per role (Egress internet switch, Connectors, access) | ✘ | partial: "keys status" only | partial | ✘ | ✔ |
| Testing vs Real use mode | ✘ | partial: "test mode" in numbers | ✔ | partial: recording note | ✔ Testing |
| Security / egress: one exit, names masked, allowlist, keys by name | ✔ slides 11, 12 | ✔ questions | ✔ | ✔ trust scene | ✔ |
| Lineage: file → batch → record → bronze load_id → gold run_id | ✘ | ✘ | ✘ | partial: "traces to a file and a person" | tonight: silver tables and runs. Pending in RUN1: bronze `_load_id` is not written by the observation loader; `run_id` not on silver |
| "Where is this from?" trail on a figure | ✔ | ✔ | ✔ | ✔ | ✔ |

## Gaps list (to close in phase 2 unless stated)

1. Run IDs are live (RUN1) but the deck (slide 12), run sheet (known gap 9) and guide say "being added" or say nothing. Update and show Operations › Runs.
2. Operations has no slide, no run-sheet step and no film scene; Deliveries likewise.
3. Map › Data model with impact: deck slide 9 and the guide describe it as not built. Rewrite with the dm1 screenshot.
4. Lineage chain (file → batch → record → bronze → gold) is not told anywhere. Add one slide. Say plainly that `run_id` is on gold only and bronze `_load_id` is pending for the observation loader (RUN1 pending).
5. Ontology zoom, Process map, Glossary and Map review are not in the run sheet or deck.
6. Roles and per-role menus: no document says what each person sees. Wait for ROLE1, else use `roles.ts`.
7. Close as timing, Done today and Figures to confirm are in guide and film but not in the deck or run sheet.
8. Reports (published dashboards), What if, USD/SGD, Comments and Ask Lumen are missing from deck and run sheet.
9. Dashboard studio, delete/archive drafts and delivery channels are missing from deck and run sheet. Delete/archive is in no document.
10. Connect API: the deck lists the providers but not the Test step with real rows, the Singapore sources (SGS auction yields; SORA not connected) or the LIVE API row in Markets. Film has none.
11. Run sheet "Known gaps" list still holds items now fixed or changed (run IDs, approved dashboard in Consume, starter tiles). Re-verify against the new demo data before keeping any. It is internal and does not go in the client guide.
12. Demo data not yet showing (tonight): silver tables, TEST/PRODUCTION runs, live API rows, figure to confirm, model extension proposal, published dashboard in Reports, delivery in Operations. Slides must not claim them until `docs/demo/DEMO-DATA.md` lands.
13. Film (`SCRIPT-V4.md`) has no scene for Map, Operations or Connect an API. Out of scope for this task (the script is approved and fixed).
14. Film end card: "Live at 06:00 / every morning" does not match a monthly pack (FIX1 item 2). Film owner's call.
15. Known product limits to keep honest: starter dashboard regenerates only once per project; the P&L "issued against known now" tables are off Financial health; SORA not connected; no email is sent at go-live.

## Status after the phase 2 refresh (12 Oct, evening)

Deck (20 slides, HTML and editable PPTX), run sheet and user guide were refreshed using ROLE1 and DEMO-DATA, which had landed. Closed: gaps 1 to 10 and 12 (run IDs live, Operations, Data model with impact, lineage slide, ontology zoom, roles and Settings per role, Close as timing, Reports, What if, USD/SGD, studio delete/archive in the guide, Connect an API with Singapore sources, demo data now present).
Remaining:
- Film (`SCRIPT-V4.md`): no Map, Operations or Connect an API scene; end card "every morning" vs a monthly pack (gaps 13, 14). Film owner's call.
- Lineage: bronze `_load_id` on the market-data loader and `run_id` on silver are pending (RUN1). The deck says so.
- Demo data: Live pipelines on Operations reads "Not run yet" (seeded runs are pipeline and reconciliation runs, not file-connector loads); FRED and Finnhub rows need the service keys; the pending model proposal is not drawn on the Data model until approved.
- Not in deck or run sheet: Process map, Business glossary and the Map review queue are mentioned but not demonstrated; delivery channel approval is in the guide only.
- Run sheet role mapping follows ROLE1; one inconsistency to check on the day: DEMO-DATA lists Mei and Daniel for Statements to chase and Figures to confirm, while ROLE1 hides those groups from the business owner. The run sheet uses Anita for Action.
