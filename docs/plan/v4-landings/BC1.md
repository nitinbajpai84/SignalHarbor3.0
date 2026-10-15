# BC1 Build as three rooms

Nitin, 10 Oct: Build is where people build pipelines, dashboards and the architecture. Three rooms, one click each from the Build page and from every project.

## What changed (UI only)
- New `ui/src/v1/b8/`: `RoomSwitcher.tsx` (three large tiles: drawn mark, purpose line, live count; `ProjectRooms` wrapper), `PipelinesRoom.tsx`, `DashboardsRoom.tsx`, `ArchitectureRoom.tsx`, `stages.ts` (stage states and schedule maths), `useFacts.ts`, `api.ts`, `routes.tsx` (Build role gate), `b8.test.tsx`.
- Routes: `/centre/build/p/:pid/pipelines`, `/dashboards`, `/architecture`. The studio stays at `/studio`.
- **Pipelines**: four cards (Sources, Bronze, Silver, Gold) joined by a moving dashed line, each with a state (new, approved, running, ok, late, failed), last run and next run. Under them the existing `Pipeline` block: Try it on a copy, Go live, Airflow file under "For engineers", schedule, last runs, Full run log. Next run is worked out in the browser from the schedule (no route for it).
- **Dashboard studio**: the project's dashboards with state, version, maker and approver (read once per published one); each opens the studio at `?d=`; "Open the studio".
- **Architecture**: Bronze, Silver, Gold with their tables (`/model/projects/{pid}/tables` plus the plan's tables); a table opens columns, relationships and lineage (plan lineage and `depends_on`; `/model/tables/{name}` for silver); the existing diagram; "Ask Span about the model" beside it (same Span chat and file attach as the plan page).
- `BuildPage.tsx`: tiles above the old Rooms line, which is kept with the Dashboard studio link. `ProjectsPage.tsx`: tiles for a chosen project, a Pipelines / Dashboards / Architecture links per row, old Rooms links kept (links test passes).
- Styles appended to `b7/studio.css` (tokens only, both themes, 860px single column, `prefers-reduced-motion` turns off hover lift and animation). Backups `.sh-tmp/*.bak-bc1`.

## Tests
`b8.test.tsx` (7): stage states and slots, switcher with counts and links, each room with fixture data, table opens details. vitest b8, b6, b7 and look: 44 passed; `tsc --noEmit` clean.

## Screenshots
`docs/plan/v4-landings/bc1-shots/`: pipelines, dashboards, architecture (dark, 1440x900, full page), projects, pipelines-390 (no sideways scroll). Taken on `make_test_env.py bc1`, serve_test 8699, temporary vite 8698 (stopped, config removed).

## Known limits
- "Late" and "failed" follow the latest run only; a failed run marks later stages late, earlier ones stay ok.
- The test env has no dashboards, so the dashboards screenshot shows the empty state; the list is covered by the vitest fixture.
- Tile counts need four reads per page; no combined route.

## Review (product designer, 10 Oct)

Verdict: pass with fixes. The three tiles are bold and clear, the flow reads at a glance, the switcher appears on the Build page, the plan page and every room. Nothing was dropped: the old rooms links remain, and links.test passes.

Fixed in review:
- Pipelines: the schedule time field was light text on a white box in dark (unreadable). The same was true of "Find a project". Both now take the theme (`.b8-tools`, studio.css).
- Architecture: duplicate relationship lines (for example "decision_intents points to users" twice) were deduplicated, which also removes a React duplicate-key warning. An empty "From" column is now hidden.
- Room tiles: removed `role="status"` from the three counts, because it gave three live regions inside a nav. Added a visible focus ring for keyboard users. RoomSwitcher now imports studio.css itself, so the rooms do not depend on the studio being in the bundle.

Open, outside this card:
- b6diagram (`PlanDiagram`): two empty white bars above the picture, a white canvas in dark mode, and the Consumers column clipped at the right in the 1440 split.
- Shell header at 390px: "Signal Harbor" wraps, and the company badge is cut to "EC".
- No light-theme screenshot was taken. The b8 styles use only `--ds-` tokens.

Checks: vitest for b6, b7, b8, look and links: 42 passed. tsc clean.
