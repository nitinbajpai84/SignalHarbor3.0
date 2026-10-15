# OP1: one place to build dashboards (10 Oct 2026)

Nitin: "Lumen should act like how it is acting in Consume, and in Consume there should be only the ready dashboards. People shouldn't have two places to build or define dashboards."

## Before and after

| | Before | After |
|---|---|---|
| Where a dashboard is built | Two places: Consume's project page (Lumen proposes tiles, Accept, Not this, "My dashboard" personal draft) and the Build studio (grid, widget library, "Ask Lumen for this slot") | One place: Build > Dashboard studio |
| Lumen in the studio | A single-shot "Ask Lumen for this slot" that placed the tile at once | The Consume conversation, moved: thread per dashboard (kept on reload), proposals shown as tile previews with Accept and Not this, follow-ups ("make it dots", "only Cedarpoint and Kestrel", "in SGD"), memory line, fresh talk, picture, rules-only note |
| Lumen in Consume | Built tiles on a personal dashboard | Answers questions about what is shown (figures, why it moved, where from). A build or change request, or a picture, gets "Dashboards are built in Build > Dashboard studio." with a link to the project's studio (people who may build) or "Ask the project's analyst to build or change it." |
| Consume lists | Published dashboards plus the person's personal drafts | Published dashboards only |

## Where each moved feature lives now

| Feature | Was | Now |
|---|---|---|
| Talk with Lumen, thread per dashboard, reload shows it | `cxui/ProjectPage.tsx` | Studio: "Talk to Lumen" panel under the canvas (`b7/StudioPage.tsx`); the thread comes with `GET .../studio/{did}` (`talk`). Shared pieces in `cxui/LumenChat.tsx` (head, thread, picture box), used by both pages |
| Tile proposal with Accept and Not this | Consume tile list | Studio: preview cards in the thread (`TileCard` with `load` from the studio data route); `POST .../studio/{did}/tiles/{tid}/accept|reject` |
| Accept places the tile | Joined the dashboard's tile list | Chosen slot, else the first free slot, adding a row when none; a new version of a placed tile replaces it in place (`b7_studio.accept_tile`) |
| Follow-up edits the last tile | Lumen focus memory | Same Lumen memory; with a widget selected the follow-up is about that widget's tile (`ask_lumen` sets the focus) |
| "Add a picture" (read on this machine, 5 MB cap, tick) | Consume | Studio composer (`b7_routes._with_reading`) |
| "Start a fresh talk", "Lumen remembers", mode line | Consume chat head | Both: `ChatHead` |
| Rules-only / model-trouble note | Consume reply | Studio: note under the box (`worded_by`, `note` passed through) |
| "My dashboard" personal draft (CL1) | `POST /consume/p/{pid}/dashboards`, `cx_dash.own_dashboard` | Studio draft of the maker (see Server) |
| "Send for approval in Build" Share-tab text for a personal dashboard | Consume Share tab | Not needed: a dashboard that is not published is not in Consume |
| Lumen's tile list | Studio library | Unchanged: "Lumen's tiles for this project", Place in the slot |
| Reading, tables drawer, share (audience), "Why did this move", "Where is this from?", comments, refresh line | Consume | Unchanged in Consume. A grid dashboard gets "Why did <tile> move" buttons under the grid |
| Consume landing "Open the project to build a dashboard" | `ProjectList.tsx` | "Open the project"; empty text points to the studio |

## Server

- `cx_routes.py`: `POST /consume/p/{pid}/dashboards` and `POST .../tiles/{tid}/accept|reject` answer 409 `conflict` with the pointer and a `link` (null for people who may not build). `POST .../dashboards/{did}/ask` answers questions with `cx_lumen.ask`, and points everything else (not a question, or with a picture) to the studio, keeping the line in the thread. `POST /consume/chat` points build requests the same way. The picture reading (OCR) code moved to `b7_routes.py`.
- `b7_studio.py`: `adopt(plane, pid)` runs when the studio lists or opens a project and when Consume lists or opens one. A personal dashboard (no lifecycle) becomes a draft of its maker with its accepted tiles on the grid and its proposed tiles waiting in the thread. A dashboard shared before the studio keeps showing in Consume (it counts as published, as in DS1) and gets a grid so the studio can open it; editing it starts a version 2 draft. Nothing is deleted; talk files stay beside the dashboard.
- `b7_studio.ask_lumen` no longer places anything: it returns Lumen's reply and proposals. New `accept_tile`, `reject_tile`. Routes and permission lines: `POST .../studio/{did}/tiles/{tid}/accept|reject` (company_admin, analyst). `ask` also takes `{new_talk: true}` and `picture`.
- A dashboard in the studio is edited by its maker or the admin only (`D._editor`), so Lumen's ask in the studio can never fall back to a "My dashboard" of the asker.
- `cx_dash.create(personal=True)` and `own_dashboard` stay in code for old callers; no route reaches them.

## Tests

- `tests/v1/test_b7_studio.py`: studio conversation (proposal not placed, Accept in the chosen slot, accepted once only), follow-up on a selected widget replaces in place, Not this and a taken slot refused before accepting, first free slot and added row, ask refused for a non-editor and no stray dashboard, real rules end to end with the thread and fresh talk, Consume build routes refuse (409, pointer, link only for builders), Consume Lumen answers questions and points build requests (and pictures), published-only listing with old personal drafts adopted into the studio and a pre-studio shared dashboard kept, studio ask/accept/reject routes are for makers.
- `tests/v1/test_cx.py`: the pidless route test no longer builds from a picture.
- `ui/src/v1/b7/b7.test.tsx`: Talk to Lumen (always active, empty-send hint, rules-only note), proposal then Accept in the chosen slot and in the first free slot, Not this, follow-up on a selected widget replaces in place, thread kept and fresh talk, library placement, flow.
- `ui/src/v1/cxui/cxui.test.tsx`: Consume shows published tiles only and none of Accept, Not this, new dashboard, Add a widget, Add a picture, Move; nothing published says where dashboards are built and creates nothing; a question is answered and a build request gets the studio link; tables and share stay.

## Known limits

- In Consume, a statement that is not a question ("I prefer blue lines") is also pointed to the studio, where Lumen's memory takes it.
- Share (audience) is still editable from Consume for a published dashboard: it is who reads, not what is built. Approval still covers content only (DS1 open item).
- The company-wide chat (`/consume/chat`) points only clear build requests ("show ...", "add a chart").
- `lumen_tools` propose_tile reached through other agents' flows was not changed.

Backups: `.sh-tmp/*.bak-op1`.

## Checked

- pytest `test_b7_studio` (b7), `test_cx`, `test_cx_shared`, `test_cx_share`, `test_talk_to_all`: pass. `test_k3.py::test_flow_box_tells_owner_last_load_what_feeds_it_and_what_it_feeds` fails on the dashboard owner (`None`, not `Ada`); it reads `k3_map.py`, which another agent edited during this run, and no OP1 file feeds it.
- vitest `b7 cxui talk b6 a5 voice look n2 k4 p3`: 115 pass. `tsc --noEmit`: clean. No vite build.
- Live, on a private copy (`make_test_env.py op1`, port 8697, stopped afterwards; API only): Mei (analyst) started a studio dashboard, asked for net worth by entity per month, got one proposal and nothing on the grid, Accept put it at row 1, column 1 (first free slot), "make it dots" on the selected widget produced a new version that replaced it in place (one widget, same id), the thread kept four turns, a second proposal was dropped with Not this. The Consume route to create a dashboard answered 409 with the studio pointer and link, and the Consume list showed no draft.

## Review (10 Oct, reasoning reviewer)

Walked live on `op1` (port 8697, API only, stopped afterwards; the production UI bundle is stale because there is no vite build, so the screens are covered by vitest only).

- **Mei (analyst, builds):** studio create, then "show net worth by entity per month" gave one proposal and an empty grid. Accept with a slot placed it at row 2, column 7. "make it dots" with the widget selected, then Accept, replaced it in place (same widget, new tile). "only Cedarpoint and Kestrel" with no selection edited the last tile, and Not this dropped it. Accept with no slot used the first free slot (row 1, column 1). A question in the studio was answered with no proposal. A reload kept 10 turns. Mei could not approve her own dashboard (403). Daniel (sponsor) approved it, and it was then listed in Consume for Mei.
- **Daniel (sponsor, reads):** Consume lists only the published dashboard he may read. Questions ("total cash", "why did net worth move") were answered from figures, with no proposals and no tile written. "make it dots", "can you show me cash by entity as bars?" and the company chat build request all got "Dashboards are built in Build › Dashboard studio. Ask the project's analyst…" with no link. Consume create and accept returned 409. Studio ask and accept returned 403. Comments, tables, why and share are unchanged.
- **Migration:** an old CL1 personal dashboard was planted in the env. It left Consume and opened in Mei's studio as a draft: the accepted tile is on the grid, and the proposed tile is waiting. Accepting that tile placed it at row 1, column 7. The seeded pre-studio dashboard stays published with a grid. Nothing was deleted.
- **Pytest:** `test_b7_studio`, `test_cx`, `test_cx_shared`, `test_cx_share` and `test_talk_to_all` passed (83). **Vitest:** b7 and cxui passed (32). **tsc:** clean.

**Defect fixed: an access rule had changed.** Before OP1, a CL1 personal dashboard could be seen and changed only by its maker, not even by the admin (`cx_dash.may_view`). `adopt` dropped the `personal` flag, so after migration every analyst and admin could list, open and edit someone's private draft in the studio.
- Fix: `adopt` now keeps `personal`, which is inert once a lifecycle exists. `b7_studio._private` hides such a draft from anyone but its maker while it is a draft.
- `open_rec`, `_may_list` and a studio `_editor` wrapper used by layout, widgets, ask and accept apply the rule, and so does the submit route (`b7_routes`).
- Test: the migration test in `test_b7_studio` now checks that another analyst and another admin can neither list, open nor ask on it. Live: Leo (analyst) and Grace (admin) got 403, and Mei got 200.
- Backups: `.sh-tmp/*.bak-op1-review`.

**Open, not fixed:**
- `tests/evals/lumen.yaml` and other eval yaml files still send tile-building turns to the Consume ask route. They will now get the studio pointer, so they need to point at `POST /api/v1/build/p/{pid}/studio/{did}/ask` on a maker's studio draft.
- A reader who made a CL1 personal dashboard (for example a participant) keeps the data as a studio draft but cannot open the studio. An analyst would have to rebuild it, because the draft is private.
- The other known limits listed above stand.
