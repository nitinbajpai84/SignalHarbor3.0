# Shared shapes for the MVP wave (step 0, 7 Oct 2026)

Thirty builders run at once. Each owns only the files named in its brief. These shapes are fixed so the pieces fit. A builder that needs a field not listed here adds it to its own file and notes it under Open questions; it never edits another builder's file, `sh_platform/app.py`, `ui/src/App.tsx`, `sh_platform/route_permissions.yaml` or `ui/src/shell/CentreShell.tsx` (P3 alone edits the shell). Routes and page stubs already exist; builders replace the stub bodies.

Conventions: FastAPI routers follow `sh_platform/outcomes.py` (`_plane(request)`, `_viewer(request)` from `sh_platform.profile.api`; a missing plane is 403). Files in the company plane are read and written with `sh_platform/jsonfile.py` (`lock_for`, `read_json_strict`, `write_json_atomic`). Provenance cells use `sh_platform/profile/store.py` `cell()` and `record()`. Screens use `Panel`, `ScreenState`, `apiGet`/`apiPost` from `ui/src/api/client.ts`, the design tokens (dark default) and the layout of `ui/src/pages/CentrePage.tsx`. Numbers an agent states must trace to a record; otherwise "Not available yet". No game words. No model names or Claude attribution anywhere. Ponytail: shortest working change, reuse before writing, one small test file per package. Graft first: `graft ask "<need>" --source` before reading files.

## 1. Pulse line (P1 writes, P2 reads, P4 sends)
`GET /api/pulse` → `{"date": "2026-10-07", "person": {"name", "roles": [...]}, "minutes": 12, "strips": [{"key": "invited|decide|give|watch", "lines": [LINE]}], "map": {"new_this_week": [str], "owned_changes": int}}`
LINE = `{"id": str, "kind": "invite|decision|request|measure|brief|ops|signature", "title": str, "detail": str, "href": "/centre/...", "action": str, "due": "2026-10-10"|null, "source": {"record": "sessions/<id>", "at": iso}}`
Rules: at most 7 lines a day across strips; an empty strip is omitted; a line exists only while its record says so. Reads: `modules/m1_intent` sessions and walls (`store/sessions.py`, `/api/modules/m1_intent/walls`), `m2_baseline` baselines and governed state, `m3_connect` assessments and requests, `graph/company.json`, `warehouse/runs.json` (shape 4), `packs/<industry>/<v>/market_briefs/*.md`, `build/blueprint.json` (shape 2). Filtered by viewer with `sh_platform/profile/view.py` helpers. Restricted and sealed items never appear to anyone outside their list.

## 2. Blueprint (agent 10 writes, 11 shows, 12 reads)
File `build/blueprint.json` in the plane: `{"version": 1, "state": "draft|signed", "signed_by": [{"name", "role", "at"}], "band": "now|next|later", "model": {"facts": [{"name", "grain", "keys": [str], "measures": [code]}], "dimensions": [{"name", "keys": [str], "attributes": [str], "scd": 1|2}]}, "lineage": [{"measure": code, "source": str, "fields": [str], "transform": str, "mart": "gold.<table>.<column>"}], "rules": [{"measure": code, "rule": str, "severity": "block|warn|inform", "from": "scan|trial"}], "access": [{"mart": str, "may_see": [name]|null}], "schedule": [{"source": str, "expected": "D+2 09:00", "sla": "WD8", "depends_on": [str]}], "infra": {"warehouse": "plane", "runner": "builtin"}, "provenance": {...per field: {"mark": "guessed|stated", "from": str}}}`
Gold tables are named `gold.<measure_code_lowercase>` unless the catalogue names a mart; silver `silver.<source>`; bronze `bronze.<source>` (already written by `sh_platform/warehouse`).

## 3. Pipeline contract (agent 12 writes and reads, 13 shows)
File `build/pipelines/<source>.json`: `{"source": str, "lands_at": str, "pattern": str, "expected": "D+2 09:00", "sla": "WD8", "schema": [{"field", "type"}], "rules": [rule ids from blueprint], "depends_on": [str], "owner": name, "marts": ["gold.x"]}`

## 4. Run log (12 writes; 15, 17, P1 read)
File `warehouse/runs.json`: `{"runs": [{"id", "source", "started", "ended", "on_time": bool, "rows": int, "schema_ok": bool, "rules": [{"rule", "passed": bool, "count": int}], "marts_ready": iso|null, "sla_met": bool|null, "owner": name, "status": "ok|late|failed"}]}`. Newest last. `counts_only` from `sh_platform/warehouse` for row counts; never rows.

## 5. Prove result (15 writes; 16 shows; R2 and P1 read)
File `build/prove.json`: `{"band": str, "measures": [{"code", "periods": [{"period": "2026-09", "ours": number|null, "reported": number|null, "result": "match|gap|not_yet", "reason": str|null, "accepted_by": name|null}], "uat": {"state": "pending|signed|sent_back", "by", "at", "note"}, "release_ready": bool}], "release": {"state": "draft|signed", "by", "at"}}`. The reported figure comes from the profile's reported figures (module 3 trial logic in `modules/m3_connect`).

## 6. Feeds (18 reads gold; 14 seeds it)
`GET /api/company/feeds` → `{"measures": [{"code", "name", "owner", "latest": {"period", "value"}|null, "trend": [{"period", "value"}], "range_break": bool, "may_see": bool}]}`. Value is shown only when the viewer passes the measure's access list (shape 2 `access`); otherwise `latest: null, may_see: false`. Demo gold data: `packs/family_office/1/demo_warehouse/<gold_table>.csv` loaded by `tools/seed_demo_warehouse.py` into `gold.*` of the demo company's `warehouse/company.duckdb`.

## 7. Market (19)
`GET /api/company/market` → `{"briefs": [{"id", "title", "summary", "measures": [code], "source": str, "outside": true}]}` from `packs/<industry>/<v>/market_briefs/*.md` and `market_sources.yaml`. Always labelled outside material. Internet off by default: pack content only.

## 8. What-if (20)
`POST /api/company/whatif {"driver": code, "change_pct": number}` → `{"driver", "moved": [{"code", "path": [code], "change_pct"}], "basis": "graph edges of type moves|measured_by; linear"}`. One driver at a time. Uses `graph/company.json` edges and gold values when present, else says "Not available yet".

## 9. Memory (8 writes the store; 9 wires it)
Files `context/memory/<agent>/people/<pid>.json` and `context/memory/<agent>/company.json`: `{"entries": [{"id", "kind": "fact|preference|decision|open", "text", "from": [{"conversation", "at"}], "updated_at", "by": "agent|person"}], "budget": 4000}`. Filters before store: anonymous notes, restricted areas, figures, contact details. Person edits are never overwritten. Routes: `GET/PUT/DELETE /api/memory/me/{agent}`, `GET/PUT /api/company/memory/{agent}` (company admin). Prompt read: `memory.for_prompt(plane, agent, pid) -> {"person": [...], "company": [...]}` within budget.

## 10. Map node, versions, comments (M1, M2, M4 write; NodePage shows)
`GET /api/company/graph/node/{id}` → `{"id", "type", "label", "owner", "steward", "trail": [{"step": "asked|defined|supplied|built|released", "label", "ref", "by", "at"}], "definition": {...} | null, "versions": [{"v": int, "what", "by", "at", "ref"}], "commits": [{"id", "when", "what", "by"}], "may_see_figure": bool}`
Versions file `graph/versions.json`: `{"<node id>": [VERSION]}`; a version is appended whenever a record that feeds the node changes (M1 hooks `sh_platform/graph/hooks.py` mark).
Comments file `graph/comments.json`: `{"<node id>": [{"id", "kind": "comment|suggestion|ambiguity", "text", "by": name|"Anonymous", "at", "state": "open|accepted|declined|answered", "decided_by", "decided_at", "answer"}]}`. Routes: `GET/POST /api/company/graph/node/{id}/comments`, `POST .../comments/{cid}/decide {"state", "answer"}` (owner or steward only). An open suggestion or ambiguity is a `decision` line on the owner's pulse.
Steward: `graph/steward.json` `{"name", "account_id"}`; default the head of data from the profile, else the company admin.
Build nodes (M4): types `Pipeline`, `Blueprint`, `Release`; edges `built_by` (Measure→Pipeline), `designed_by` (Blueprint→Person), `tested_by`, `released_by`; a Pipeline node carries `commits`. Added through `sh_platform/graph/build_nodes.py add_build_nodes(g, plane, people)` called from `build.py`.

## 11. Signed register (M3)
`GET /api/company/register` → `{"rows": [{"code", "name", "kind": "measure|definition", "owner", "pipeline": str|null, "signed": {"charter": {"by", "at"}|null, "baseline": ..., "blueprint": ..., "uat": ..., "release": ...}, "version": int, "href": "/centre/intent/map/<node id>"}]}`. Names and links only; no figures.

## 12. Build roles at the charter (R1)
Charter record gains `roles: {"architect": name|null, "developer": name|null, "tester": name|null, "sponsor": name, "ops": name|null, "informed": [name]}`, drafted by Lens from the people list (guessed) and confirmed by the organiser (stated). `sh_platform/build/*` reads them to address each hand-over; the pulse puts the task on the named person.

## 13. Wall invite and stages (agents 1 and 2)
Existing routes: `POST /api/modules/m1_intent/sessions/{id}/link`, `.../seats/{n}/revoke`, `.../briefing`, `.../rooms/open`, `.../rooms/close`, `.../together` (check `modules/m1_intent/api/room.py` and `session.py` for exact names). Components `ui/src/modules/m1_intent/wall/InvitePanel.tsx` and `StageBar.tsx` are rendered by `WallScreen.tsx` for the organiser only; stubs exist.

## 14. Routes and pages that already exist as stubs
Backend routers (each file holds `router = APIRouter()`, registered in `app.py`): `sh_platform/pulse/__init__.py`, `sh_platform/pulse/messages.py`, `sh_platform/build/blueprint.py`, `runner.py`, `prove.py`, `uat.py`, `ops.py`, `whatif.py`, `sh_platform/consume/feeds.py`, `market.py`, `sh_platform/memory/__init__.py`, `sh_platform/memory/api.py`, `sh_platform/graph/versions.py`, `comments.py`, `register.py`, `build_nodes.py`.
Pages (`ui/src/pages/`): `PulsePage.tsx` (route `/pulse`, the landing), `BlueprintPage.tsx` (`/centre/build/blueprint`), `PipelinesPage.tsx` (`/centre/build/pipelines`), `ProvePage.tsx` (`/centre/build/prove`), `OpsPage.tsx` (`/centre/build/ops`), `ConsumeCentre.tsx` (`/centre/consume`), `FeedsPage.tsx` (`/centre/consume/feeds`), `MarketPage.tsx` (`/centre/consume/market`), `WhatIfPage.tsx` (`/centre/consume/what-if`), `NodePage.tsx` (`/centre/intent/map/:nodeId`), `RegisterPage.tsx` (`/centre/register`), `MemoryPage.tsx` (`/centre/memory`), `BaselinePage.tsx` (`/centre/intent/baseline/:baselineId`), `BaselineSignoff.tsx` (component), `CharterView.tsx` (`/centre/intent/charter/:sessionId`).

## 15. Intent Centre v2 shapes
Source: `docs/specs/intent-centre/` (00-BRIEF section 3 and rulings 12, 13, 16, 17, 21, 27, 28; files 01, 02, 15, 16, 21, 56). Company plane, through `sh_platform/jsonfile.py`. The spec files win where this summary is shorter.

**Intent record** `intents/<id>/intent.json`. Strict key set: these keys plus every "Fields this feature adds" of a spec file (ruling 28). `outcome` is an object from open, flat per type (rulings 6, 16; keys from file 02's YAML).
```json
{"id": "", "type": "initiative|brainstorm|pulse|problem|decision", "title": "", "purpose": "",
 "created_by": "", "created_at": "", "company": "", "areas": [],
 "people": {"organiser": null, "sponsor": null, "decider": null, "owner": null, "reporter": null,
            "participants": [], "advisers": [], "affected": [], "observers": []},
 "state": "draft|open|in_session|closing|closed|cancelled",
 "time_box": {"starts": "", "ends": "", "extended_by": [{"by": "", "at": "", "reason": ""}]},
 "stages": [{"key": "", "state": "", "opened_at": null, "closed_at": null}],
 "outcome": {"kind": "initiative", "goal": "", "why": "", "build_needed": "", "definitions_exist": "", "build_ready": null},
 "closure": {"closed_by": null, "closed_at": null, "summary": "", "why_it_happened": "", "what_came_out": "",
             "next": [{"kind": "initiative|problem|decision|backlog|handled|nothing", "ref": null, "reason": ""}],
             "cancel_reason": null, "draft_by": null, "signed": false},
 "ratings": [{"by": "account id|anonymous", "score": 1, "note": ""}],
 "links": {"from": null, "to": [], "build": null},
 "share": {"link": null, "who_may_open": [{"person_id": null, "label": "", "token_hash": "", "expires_at": "", "revoked_at": null, "created_by": ""}]},
 "version": 1, "updated_at": "", "history": [{"at": "", "by": "", "from": "", "to": "", "note": ""}],
 "affected_may_read": false, "catalogue_version": "", "start_answers": {},
 "refs": {"wall_session_ids": [], "charter_outcome_id": null, "baseline_ids": [], "assessment_ids": []},
 "event_count": 0, "events": {"path": "intents/<id>/events.jsonl", "count": 0, "last_seq": 0, "last_at": null}}
```
Outcome keys per type (besides `kind`): initiative `goal, why, build_needed, definitions_exist, build_ready`; brainstorm `statement, good_outcome, session_at, chosen, backed, runners_up, ideas_kept, dropped`; pulse (Weekly check-in series) `weeks`; problem `what, saw, bites, count, amount, owner_accepted_at, root_cause, fix`; decision `question, options, chosen, why`. `event_count` (01) and `events` (16) both count the log; builders of B01 and B10 keep them in step.

**Events line** `intents/<id>/events.jsonl` (16), one object per line, appended under `lock_for`; `detail` holds keys, enums and numbers only, never free text.
```json
{"seq": 17, "at": "2026-10-06T09:14:03Z", "kind": "card_added", "status": "act|draft",
 "by": {"account": "", "name": "", "role": ""}, "anonymous": false, "agent": null, "stage": "wall",
 "ref": {"store": "m1_wall", "id": "card_8f2", "version": null}, "detail": {}, "confirms": null, "corrects": null, "sealed": false}
```

**Week file** `intents/<id>/weeks/<week_key>.json` (ruling 17, file 38).
```json
{"week_key": "", "opens": "", "closes": "", "state": "",
 "items": [{"id": "", "by": "account id|anonymous", "kind": "ran|broke|thought", "text": "", "severity": null, "count": null,
            "amount": null, "ref": null, "fate": "problem|backlog|handled|nothing|null", "fate_reason": null, "decided_by": null}],
 "review": {}, "closed_at": null}
```

**Opportunity record** `intents/opportunities/<id>.json` (56).
```json
{"id": "", "title": "", "state": "noticed|under_review|proposed|picked_up|parked|dismissed", "noticed_by": "watcher|account id", "noticed_at": "",
 "areas": [], "touches": {"measures": [], "processes": [], "sources": []},
 "pattern": {"text": "", "periods": [], "numbers": [{"label": "", "value": 0, "unit": "", "trace": {"kind": "run|alert|week_item|feed|range_break|edge", "ref": "", "at": ""}}]},
 "evidence": [{"id": "", "text": "", "kind": "supports|disputes", "source": {"kind": "", "ref": ""}, "by": "lens|watcher|account id", "at": ""}],
 "judgement": {"fits": true, "why": "", "confidence": "fairly_sure|not_sure|unlikely", "start_answers": {"goal": "", "people": "", "build": "", "definitions": "", "areas": "", "deadline": ""}, "at": ""},
 "picked_up_by": null, "picked_up_at": null, "became": null, "parked": null, "dismissed": null, "history": [{"at": "", "by": "", "action": "", "note": ""}]}
```

**Backlog item** one of `items` in `intents/backlog.json` (21).
```json
{"id": "", "title": "", "kind": "idea|ops_problem|request", "area": null,
 "source": {"intent_id": "", "type": "", "stage_ref": null, "week_key": null, "week_item_id": null},
 "raised_by": "account id|anonymous", "raised_at": "", "why_it_matters": {"text": "", "drafted_by": "north", "edited_by": null, "edited_at": null},
 "source_quote": "", "taps": [{"by": "", "at": ""}], "review_date": "", "status": "", "parked": null, "dropped": null,
 "merged_into": null, "merged_from": [], "opened_intent": null, "reminded_at": [], "history": [{"at": "", "by": "", "action": "", "note": ""}]}
```

**Index file** `intents/_index.json` (15), rebuilt from `intents/*/intent.json` only; one row per intent, a draft row only for its creator.
```json
{"schema": 1, "built_at": "", "rebuilt_reason": "",
 "rows": [{"id": "", "type": "", "title": "", "purpose": "", "state": "", "stage_key": "", "stage_name": "", "areas": [], "created_by": "",
           "organiser": {"name": ""}, "people": {"organiser": null, "sponsor": null, "decider": null, "owner": null, "reporter": null,
           "participants": [], "affected": [], "observers": [], "share_named": []}, "affected_may_read": false, "people_count": 0,
           "starts": "", "ends": "", "extended": false, "closed_at": null, "cancelled_at": null, "outcome_text": "", "next_kinds": [],
           "rating_n": 0, "rating_avg": null, "rev": "", "body_text": ""}]}
```
