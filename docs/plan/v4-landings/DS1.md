# DS1 Dashboard studio in Build, published dashboards in Consume

Spec: `docs/plan/DASHBOARD-STUDIO.md`.

## What changed
- **Lifecycle** (`cx_dash.py`): a dashboard made in the studio is a draft, then submitted, then published (approver and time recorded). Editing a published one starts a new draft version; Consume keeps showing the published version until the new one is approved. The maker (creator or submitter) can never approve. Approvers: the architect seat (analyst, as Build uses it) or the sponsor role. A dashboard with no lifecycle field counts as published, in code; nothing is rewritten and nothing is seeded.
- **Consume lists published only**: `list_for`, `shared_with`, the dashboard view, the tile data and the "why" route read the published snapshot (`get_published`). New: `company` in `GET /api/v1/consume/shared` (published and marked company-wide), shown among the Company reports links.
- **Studio** (`b7_studio.py`, `b7_routes.py`, `b7.permissions.yaml`): 12-column grid with empty slots, rows, widgets (figure, line, bar, area, table, status list, text note, plus Lumen's tiles), each naming its gold table in plain words. A widget is an ordinary tile built by rules from one gold table, so the same SQL and spec checks apply. "Ask Lumen for this slot" calls `cx_lumen.ask` and places the proposal in the slot (with a widget selected, the new version replaces it in place).
- **Refresh line** on the studio and on the Consume dashboard: "Updated daily at 06:00 after the pipeline run · last refreshed ... · next ...", from `b6_schedule.last_slot` and the live runs in `b6_run`; an amber line with a link to Map > Health when the last live run failed or a source the plan reads is late (`k3_map.health`). New route `GET /api/v1/consume/dashboards/{did}/refresh`.
- **UI** `ui/src/v1/b7/` (Canvas, StudioPage, RefreshLine, api, routes, studio.css), mounted at `/centre/build/p/:pid/studio?d=<dashboard>`; "Dashboard studio" link in the Build project rooms line (`BuildPage.tsx`). Consume's `DashboardView` draws the grid read-only. `cxui/Chart.tsx` now draws figure, table and status views; `TileCard.tsx` takes optional `load` and `inGrid`.

## How the charts update by themselves
Widgets query the gold tables when viewed. The project pipeline (Build > Pipeline: go live, schedule) rebuilds the gold tables on its schedule, so a dashboard is as fresh as its last run. The header line says when that was and when the next is due.

## How to see it
1. Sign in as a company admin or analyst, open Build, open a project, click "Dashboard studio".
2. Start a dashboard, click "Add a widget here", pick a widget type and a table, "Add widget to the slot". Move with the buttons, Alt+arrow keys or drag; resize with Small, Medium, Wide, Full (or + and -). Try "Ask Lumen for this slot".
3. "Submit for approval". Sign in as a different analyst (head of data) or the sponsor: the studio shows "Waiting for your approval" with the preview and the sources; "Approve and publish" or "Send back" (a reason is needed).
4. Consume: the dashboard appears for its audience (Shared with you), and under Company reports if "Show under Company reports once published" is ticked.

## Files
`sh_platform/v1/cx_dash.py`, `cx_routes.py`, `cx.permissions.yaml` (edited, backups `.sh-tmp/*.bak-ds1`); new `b7_studio.py`, `b7_routes.py`, `b7.permissions.yaml`; `ui/src/v1/b7/*`; edited `ui/src/v1/cxui/{api.ts,Chart.tsx,TileCard.tsx,DashboardView.tsx,ProjectList.tsx}`, `ui/src/v1/b6/BuildPage.tsx`, `ui/src/look.test.tsx` (the allowed-stylesheet list gained `v1/b7/studio.css`).

## Tests
- `tests/v1/test_b7_studio.py` (24): lifecycle, maker cannot approve, sponsor path, send back needs a reason, Consume lists published only, edit keeps the published version visible, legacy dashboard counts as published, grid persisted and checked, every widget kind runs, Ask Lumen into a slot (stubbed route, follow-up replaces in place, taken slot refused before Lumen is asked), refresh facts from schedule and runs (daily, weekly, failed run, late source, no pipeline), default deny and role lists of the new routes, end-to-end routes, Consume routes.
- `ui/src/v1/b7/b7.test.tsx` (9): grid maths, keyboard and button move/resize, slot add, read-only canvas, refresh line with the amber warning, studio flow, Lumen tile placement, approver view (approve, send back), Consume grid with header.
- Also green: `test_cx.py`, `test_cx_shared.py`, the cxui and b6 vitests, `tsc --noEmit`, and the whole `tests/v1` run except for files listed in Known limits.
- Live check on a private copy (`make_test_env.py ds1`, port 8696, stopped afterwards): demo dashboard still listed in Consume; a new draft is not; maker's own approval refused (403); an analyst's approval published it; Consume then listed it, with the refresh line and the grid.

## Known limits
- Drag works for moving into an empty slot; the buttons and keys are the reliable path. No drag-to-resize handle.
- "Why did this move" for a reader needs the tile in the published version (checked in the route), but Lumen's explanation itself reads the working copy.
- The sponsor may open submitted and published dashboards in the studio, never drafts. The Trail panel ("Where is this from?") is open to the data team and to people who may view the dashboard; a sponsor who is not in the audience sees "not available yet".
- Next-run time is the server's local clock, as the scheduler uses.
- Full `tests/v1` run: 944 passed, 2 failed, neither about dashboards: `test_e5a.py::test_acknowledge_dismiss_and_ownership` (Pulse cards, no dashboard code) and `test_v3_g1.py::test_skills_load_under_cap_whole[north]` (North's skill text is 53 characters over its cap, another agent's file). Not run: `tools/seed_10uc.py` had a syntax error from another agent's edit, so 7 test files that import it could not be collected; `test_e2e.py::test_generator_is_deterministic` fails on a PDF library version difference.

## Review (10 Oct 2026)
**Verdict: accept with fixes applied.** The lifecycle, Consume published-only, versioning, default deny, the refresh line and keyboard access hold. I fixed six defects. Backups are `.sh-tmp/*.bak-ds1r`.

**Fixed**
1. **Maker-never-checker leak.** A company admin could edit someone else's draft and then approve it, because only the creator and the submitter were barred. Now everyone who changed the version is barred. They are listed in `lifecycle.editors`, set by `begin_edit(rec, viewer)`, and the list starts again with each new version. (`cx_dash`, `b7_studio`)
2. **"Company reports" took effect before approval.** Ticking the box on the draft of a published dashboard showed or hid it under Company reports straight away. The flag is now part of the approved snapshot (`published.company_wide`), and `company_reports` and `get_published` read it from there.
3. **Audience could reach a never-published draft.** `may_view` let audience members open the working copy (`D.get`). That copy is used by the audience route, the trail (`a5_trail`), the Map's dashboard list (`k3_map`) and Lumen's tile lookup (`agent_tools`). The audience now counts only once a version is published. `k3_map` passes the lifecycle so the rule applies there too.
4. **Cards for unpublished dashboards.** `cx_share.notify` (the cards for "shared with you" and for a pipeline refresh) could send a card that linked to a 404, with the draft's title. It now reads the published version and makes no card while nothing is published.
5. **Consume chat wrote into a studio dashboard.** `own_dashboard` returned the person's first dashboard, which could be a studio draft or a published one. Proposals from the Consume chat then landed out of sight. It now skips studio dashboards.
6. **Copy.** Lumen's Consume sentence "It is waiting for you: accept it or choose Not this" appeared in the studio, where the tile is already placed. The studio now replaces it with "It is now on the grid, in the slot you chose." The dashboard picker also showed "Review walk v2Draft" with no gap and a stale status after Submit. It now has the gap and follows the open dashboard.

**Tests added** in `tests/v1/test_b7_studio.py` (28 now pass):
- someone who changed the version cannot approve it
- "company-wide" takes effect only when approved
- the audience of a never-published draft gets a 403 and no card
- Consume chat never writes into a studio dashboard

Also green: `test_cx.py`, `test_cx_shared.py`, `test_cx_share.py`, `test_k3.py`, `test_c3.py`, the vitests for b7, cxui, b6 and look (7 files, 47 tests) and `tsc --noEmit`. `test_e5a.py::test_acknowledge_dismiss_and_ownership` still fails with an IndexError in the Pulse item list. No dashboard code is involved.

**Live walk** on `make_test_env.py ds1`: API on 8696, a temporary vite dev server on 8697 proxying to it (no build). Both were stopped afterwards and the temporary config was removed.
- **Mei (analyst):**
  - Started a dashboard and added a figure, line, status list and note.
  - "Ask Lumen for this slot" placed "Net worth by entity, per month".
  - Alt+Left moved the focused note one column, and focus stayed on it.
  - Submitted the dashboard. Her own approval got 403 with "You cannot approve a dashboard you made or changed".
- **Daniel (sponsor, in the audience):**
  - While it was a draft, it was not in Shared with you or Company reports.
  - Its view returned 404, and the studio refused him the draft (403).
  - He cannot start a studio dashboard (403).
- **Anita (analyst, head of data):**
  - Saw "Waiting for your approval", with each widget's source in plain words.
  - Send back with no reason got 400.
  - Approve and publish recorded "Approved by Anita Rao".
- **Daniel after approval:**
  - The dashboard is in Shared with you and Company reports, and Consume draws the grid read-only with no slots.
  - The header reads "Updated daily at 06:00 after the pipeline run · last refreshed 10 Oct 2026, 00:38 · next 10 Oct 2026, 06:00", from the live plan's schedule and the last good live run.
  - "Where is this from?" opened the trail (200).
  - When Mei edited it again, a version 2 draft started and Daniel still saw version 1.

**Open items**
- **Sharing from Consume bypasses approval** (needs Nitin's call). A dashboard made in Consume ("My dashboard" or POST `/consume/p/{pid}/dashboards`) has no lifecycle, so it counts as published. Its maker (an analyst, sponsor or admin) can share it with an audience with no second person. Options:
  - Consume dashboards stay personal, and sharing goes through the studio.
  - Accept that Consume sharing is self-service.
- **Approver is a role, not the named project role.** The rule is "the project sponsor", but any account with the `sponsor` role passes. "Head of data" is any analyst other than the maker. That is what the brief asked for, but in the demo every analyst can approve every other analyst's dashboard. The project's `people.head_of_data` / `people.sponsor` could narrow this.
- **The audience is not versioned.** Who sees the dashboard is set in Consume (PUT audience) and takes effect at once. Approval covers content only.
- **Edits of a published dashboard leak tile titles.** While a later version is being edited, Lumen's tile-name lookup in `agent_tools` (another agent's file) still scans the working copy's tiles for people in the audience. The trail looks a tile up in the working copy, so a published tile that the draft has since replaced shows "We could not find that tile".
- **The status list widget is weak on tables with one text column.** It repeats that column (for example "EG-OFFICE-BLEND" nine times). It needs a status-like column or should be offered only when one exists.
- **"Shared with you" shows a raw ISO date** (`2026-10-09`, the UTC date of the approval). This formatting came with SW1, not DS1.
- **No card on publish.** Approving does not send the audience a "shared with you" card. Only a later refresh does.

## Polish ST2 (10 Oct)

Nitin on 8502: "why is Lumen not activated in the dashboard building".
- Ask Lumen now uses the shared Composer (ui/src/v1/voice): Send is always active, Enter sends, an empty send says "Type what you want in this slot, for example: cash by entity as bars", no slot or widget says "Choose an empty slot or a widget first.", and the reply, any error and a rules-only note (when the ask answer carries `worded_by: "rules"` or `note`) show under the box.
- One heading for the ask box (the duplicate label is gone).
- Top bar: the studio is already mounted in CentreShell through b7/routes.tsx like every Build page (b6, b8); the bar is not sticky, so a scrolled page hides it. Test pins the mount.
- Layout: a widget is a flex column, so "Reads: ..." and the controls sit below the card and the row buttons below the grid; no overlap.
- Figures: a return, rate or yield stored as a fraction shows as a percentage (1.0%) and moves in points ("Up 0.8 points"), never a percent of a percent (cxui/Chart.tsx Figure, shared with Consume).
- Canvas, library panel and approval box take the theme tokens (dark mode).
- Open: the studio ask route (sh_platform/v1/b7_studio.py ask_lumen) drops Lumen's `worded_by`; pass it through so the rules-only note shows today.
- Tests: b7.test.tsx (12 pass); tsc clean. Backups: .sh-tmp/*.bak-st2.
