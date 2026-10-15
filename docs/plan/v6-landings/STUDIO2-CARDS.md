# STUDIO2: the dashboard studio shaped by conversation (13 Oct, land by 09:30)

Design: https://claude.ai/artifact/NvY3SDbMbULtEXeR4kDCYe (boards 1-5). DASH = /api/v1/build/p/{pid}/studio/{did}. Existing: b7_studio.py, b7_routes.py, b7.permissions.yaml, ui/src/v1/b7/*.
Rules for every card: never drop an existing control or route; no commit/push (Nitin integrates); synthetic data; pytest with --basetemp=D:/Temp/pyt-<card> -p no:cacheprovider; vitest only your files; tsc clean; no Claude attribution; no paid model calls in tests (stub the model); don't touch port 8530 or D:/Temp/sh-local.
New backend routes go in YOUR OWN routes module and permissions file (copy how b7_routes.py + b7.permissions.yaml are discovered/registered; if registration needs a shared list, add one line only).

## Contracts
- A talk: POST DASH/talk {text, widget?, reading?} -> {reply, changed:[widget ids], step:int}. Lumen's proposals are PLACED at once (replace the selected widget's tile, else first free slot). Every change (talk, layout, inspector edit, option, check fix, sketch build) records a step.
- A history: GET DASH/history -> {steps:[{n, at, by, said, summary}], now:int}; POST DASH/undo; POST DASH/history/{n}/restore; GET DASH/history/{n}/compare -> {added:[title], removed:[title], changed:[title]}; POST DASH/withdraw (submitted -> draft). Steps live with the dashboard record (cap 50).
- A inspector: PATCH DASH/tiles/{tid} {kind?, measure?, split?, when?, only?:{column, values}, title?} -> {ok, step}; POST DASH/widgets/{wid}/duplicate; DELETE DASH/widgets/{wid}.
- B checks: GET DASH/checks -> {checks:[{id, widget, kind: counted_twice|flattened_trend|space|house_style|too_many, message, fix?:{label, patch}}]}. A fix is applied by the client with PATCH DASH/tiles/{tid} (patch) or the layout route.
- C options: POST DASH/tiles/{tid}/options -> {options:[{label, why, patch, pick:boolean}]} (3 options, one marked Lumen's pick, from the question words and the table's columns).
- D sketch: POST DASH/sketch {name, data(base64 image or pdf)} -> {boxes:[{id,label,row,col,status: possible|needs_definition|not_possible, maps_to?:{table, measure, kind}, why, question?}]}; POST DASH/sketch/build {boxes:[ids or boxes]} -> {placed:int, step}; POST DASH/sketch/request {boxes} -> {request_id} (a Build request/ticket for the data team with the missing items). The picture is read ON THE MACHINE with the existing picture reader (OCR); never sent out.
- E chart kinds: bullet, waterfall, small_multiples, calendar, treemap, kpi_strip rendered in ui/src/v1/cxui/Chart.tsx; build_tile accepts them; each has a data shape documented in the code.
- UI components (props): Inspector {pid, did, item, onChanged:()=>void}; OptionsPanel {pid, did, tid, onChanged}; ChecksPanel {pid, did, onChanged}; SketchPanel {pid, did, onChanged}. Files in ui/src/v1/b7/. Create your component file with its props in the first minutes so StudioPage compiles.
