# CL1: Consume landing order, comments mounted, personal drafts

## What changed
- **Landing order** (`cxui/ProjectList.tsx`): `<DailyNumbers />` first, then "Department and project reports" (published dashboards from Shared with you and Company reports, grouped by department where the project row has `department`, then by project), then Shared with you, Company reports, Outside data and insights, then "Your projects", the talk box and the project picker.
- **Comments** (collapsed, closed button reads "3 comments" when there are any): each report in the reports section and the whole dashboard and each accepted tile in `DashboardView`; each holding line in `k4/OfficePage.tsx` (`office_line`, `<portfolio>/<instrument>`); each CIO Brief line in `e5/BriefPage.tsx` (`brief_line`, `<portfolio_id or company>/<key>`).
- **Personal drafts**: a dashboard made in Consume (POST `/consume/p/{pid}/dashboards`, or Lumen's "My dashboard") is stored with `personal: true`. `may_view` is its maker only (not even an admin), `set_audience` refuses with 403 "A dashboard started in Consume is personal. To share it, send it for approval in Build." The Share tab in `ProjectPage.tsx` shows that sentence with the link "Send for approval in Build" (to the project's studio). Records without the flag (all existing ones) are unchanged.

## Files outside the card, minimal edits (backups `.sh-tmp/*.bak-w3`)
- `sh_platform/v1/cx_routes.py`: one argument, `personal=True`, on the Consume POST route.
- `ui/src/v1/n2/Comments.tsx`: new optional `eager` prop (reads the thread once on mount so the closed button can show the count); closed label is now "3 comments" (was "Comments (3)"). Without `eager` nothing changes.
- `ui/src/v1/e5/api.ts`: `BriefLine.portfolio_id` (optional) passed through when the server sends it.
- `ui/src/v1/cxui/api.ts`: `Dashboard.personal?`.

## Limits
- Eager count costs one comments read per mounted line (Office view, Brief). A batch counts route in n2 would replace it.
- Brief lines: `e5_brief` does not send `portfolio_id` yet, so the key is `company/<key>` (only people who see every portfolio can open it).
- Widgets inside the studio grid (`b7/Canvas.tsx`) carry no comment button yet (not in this card); the whole dashboard does. Tiles in the plain list do.
- No lineage from a department to the project exists in the server yet: grouping uses an optional `department` on the project row; without it, reports group by project only.
- The Pulse/Shared with you item for a personal dashboard never appears (no audience).

## Tests
- `pytest tests/v1/test_cx.py tests/v1/test_cx_shared.py tests/v1/test_b7_studio.py`: 59 passed (2 new: personal cannot be shared or seen by others and lists for its maker; legacy dashboards still share).
- `npx vitest run src/v1/cxui src/v1/k4 src/v1/e5 src/v1/n2 src/v1/k9 src/v1/b7 src/look`: 71 passed (5 new: landing order, grouping and count, dashboard and widget comments, personal Share tab, Office lines, Brief lines).
- `tsc --noEmit`: no errors in cxui, k4, e5, n2.

## Review
- Re-ran: pytest test_cx, test_cx_shared, test_b7_studio 60 passed (1 added); vitest cxui, k4, e5, n2 38 passed; tsc clean in those folders.
- Defect fixed (`cx_dash.py`): the personal flag blocked sharing for ever, so a dashboard sent to Build and approved could still never get an audience. The rule now applies only while the record has no studio lifecycle (`_personal`); once it enters the studio, DS1 approval rules govern.
- Defect fixed: `_editor` let any admin change a personal draft they cannot see; it is now maker-only while personal.
- Scope: edits outside the card (`cx_routes.py`, `n2/Comments.tsx`, `e5/api.ts`, `cxui/api.ts`) are one-line or optional-prop changes, backed up, accepted. Brief comment keys fail closed (company scope) until `e5_brief` sends `portfolio_id`.
- Backups of review edits: `.sh-tmp/cx_dash.py.bak-w3-review`, `.sh-tmp/test_cx.py.bak-w3-review`.
- Verdict: pass with the two fixes above.
