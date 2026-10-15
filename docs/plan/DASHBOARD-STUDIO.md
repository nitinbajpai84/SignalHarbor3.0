# Dashboard studio in Build, published dashboards in Consume (Nitin, 10 Oct 2026)

Nitin: "Consume is where people see the final dashboard; the dashboard component should be in Build and the final approved dashboard in Consume. There is no placeholder where I can add all these widgets to finalise the dashboard. How will these charts update automatically?"

## Lifecycle (one rule: makers build in Build, readers read in Consume)
1. **Draft** (Build › project › Dashboard studio): a maker (analyst, data team) arranges widgets on a canvas. Lumen helps: "add net worth by month here".
2. **Submit for approval**: the maker sends it; the approver (head of data or the project sponsor, never the maker) sees a preview with live data and the list of widgets with their sources.
3. **Approved → Published**: the dashboard appears in Consume for its audience (Shared with you) and, if marked company-wide, under Company reports. Consume shows the **published version only**.
4. **Change later**: editing creates a new draft version in Build; Consume keeps showing the published version until the new one is approved.

## The studio canvas
- A 12-column grid with **empty slots** ("Add a widget here") the maker clicks or drops into; rows can be added; widgets can be moved (drag, plus Move up/down/left/right buttons for keyboard users) and resized (Small, Medium, Wide, Full).
- **Widget library** beside the canvas: figure (single number with change), line, bar, area, table, status list, text note, and every tile Lumen has proposed for this project. Each widget shows which gold table it reads.
- **Ask Lumen in the studio**: "add cash by entity as bars in this slot"; follow-ups edit the selected widget.
- Live preview with real data; the trail ("Where is this from?") on every widget.

## Automatic updates (pipelines)
- Widgets query the project's gold tables when viewed, so a dashboard is as fresh as its last pipeline run.
- The project pipeline (Build › Pipeline: sandbox run, go live, schedule daily/weekly/on arrival, Airflow export) refreshes the gold tables. Already built; the demo project runs daily at 06:00.
- Every dashboard header says it plainly: "Updated daily at 06:00 after the pipeline run · last refreshed 10 Oct 2026, 06:02 · next 11 Oct, 06:00". If the last run failed or a source is late: an amber line "Not refreshed since 9 Oct: the administrator file is late", linking to Map › Health.

## Permissions
Draft and submit: company_admin, analyst (makers). Approve and publish: head of data (analyst seat with the architect role) or the project sponsor, never the maker. Read published: its audience. Default deny on every new route.
