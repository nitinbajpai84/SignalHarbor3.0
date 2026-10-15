# I6a North's conversation (backend): landing

## Reuse check
- `sh_platform/v1/i2_north.py` (I2) **imported, not copied**: records and paths (`_path`, `read_thread`, `read_sow`, `empty_sow`, `_turn`, `_id`), file saving (`save_file`, `stored_file`), `_company_page` (the I1 page and context_docs passages), `file_preview`, `_system()` (2.0 North role and rules plus `documents_rules`), the fallback parser (`_fallback`, `parse`), `pack_suggestions`, the hooks `_scan` (I5) and `_room` (X1), `Refused`, the names `NORTH` and `FALLBACK_NAME`.
- `sh_platform/v1/i2_routes.py` **imported**: `_json_body`, `_decode`, `_answer`, `_model` (`get_model`: honours `SH_MODEL_PROVIDER=off` and the test `build_model_factory`), `_pack`, the body limits.
- The model call has the same shape as I2's `_ask_model`: `run_agent` + `ToolRegistry(OpenGate())` + `RunRegistry`, with `register_names`. `private_room.figures` supplies the guard's facts.
- `sh_platform/v1/egress_fit.fit` flattens the context (no list of records; trimmed to 11,000 characters) before facts are added. The facts fill the message up to 19,000 characters.
- The idea of an edit mark comes from B3 (`build/mapping/<iid>.meta.json` "edited"). I4 keeps no edit marks, so see below.
- New: the conversation prompt, the patch merge, the process redraw, the start, pending-reply and open-intent paths.

## What landed
- `sh_platform/v1/i6_chat.py`
  - `chat(plane, iid, viewer, text, files, model, pack)`: adds the person's turn, scans any files (I5), asks the model, merges the patch, writes the thread and SOW, and posts the room hand-over when the SOW becomes ready.
  - `start(...)` creates the intent from the first message (with optional files) and runs the first model turn.
  - `answer_pending(...)` and `pending(thread)` cover the case where North owes an answer (see below).
  - `open_intent(plane, viewer)` and `greeting(plane, viewer)` serve the open-intent route.
  - `merge(sow, patch, steps, last, by)` merges the patch: KPIs and sources match by name, the catalogue by table, governance by rule text, unclear points by question, process steps by name. Rows are renumbered, and new KPIs get the next free `Kxx` code.
  - Model reply shape: `{reply, sow_patch, process_steps, covered, ready}`. There are 9 goals: goal, process, result, frequency, inputs, documents, kpis, rules, unclear. `needs_done` holds the goals covered, in that order. When the SOW is ready, North's reply is the closing line from the card.
- `sh_platform/v1/i6_routes.py` with `sh_platform/v1/i6.permissions.yaml`:
  - `GET /api/v1/intents/open` → `{id | null, greeting}`. Read by the decision maker and the analyst.
  - `POST /api/v1/intents/chat` `{text, files?: [{name, data (base64), kind}]}` → a new intent with North's first reply from the model. Decision maker only.
  - `GET /api/v1/intents/{iid}/chat` → `{id, intent_id, turns, needs_done, state, sow, process_map}`. Read also by the analyst. For the decision maker it first answers any pending turn.
  - `POST /api/v1/intents/{iid}/chat` `{text, files?}` → the same shape after North's reply. Files are base64 or stored records, as in I2.
  - `POST /api/v1/intents/{iid}/chat/files` → `{name, path, kind}`, as in I2.
- `tests/v1/test_i6a.py`, 4 tests:
  1. A stubbed model starts an intent with a CSV and returns a patch with `ready: true`. The test checks the SOW, KPI source links, pack-suggested KPIs, the numbered process map, `sow_ready` and the room hand-over. Every message sent to the model passes `egress.rows.json_findings` (no rows, under the size limit).
  2. A person's edit made through I4's PUT survives North's next patch.
  3. An intent started through I2 gets North's own first reply on GET, answered once.
  4. With the model off, North (rules only) asks the next goal, and an analyst can read but not post (403). This is the refusal.

## Results
- `SH_MODEL_PROVIDER=off python -m pytest tests/v1/test_i6a.py -q`: 4 passed.
- `tests/v1 tests/auth`: 172 passed, 9 failed. The 9 failures are in `tests/auth`: `test_role_matrix` ×6 (KeyError) and `test_auth` ×3. They fail the same way with my I6 route files moved out, so they are not from this card.

## The orchestrator's two requests
1. **The first reply comes from the model.** Both paths work, and no shared edit is needed:
   - The screen can call `POST /api/v1/intents/chat {text, files?}`, which uses `i6_chat.start`.
   - Or it can keep calling I2's `POST /api/v1/intents {line}` and then **GET `/api/v1/intents/{iid}/chat`** (not `/thread`). When the only North turn is I2's fixed opening question, that GET removes it and puts the model's reply in its place. It does the same for any person turn left unanswered. This happens only for the decision maker, and only once.
2. **Open intent:** `GET /api/v1/intents/open` → `{id, greeting}`. `id` is null when there is none. "Open" means the SOW is still a draft and the person wrote the first turn; the latest one wins. The greeting names the company from I1's page.

## How to test by hand (8400, model on)
1. Sign in as Arjun Mehta (Neera) and open `/centre/intent`. The screen calls `GET /api/v1/intents/open` and shows the greeting.
2. Type "A monthly performance pack net of fees for the investment committee". North (named "North", not "rules only") should answer with one question that builds on the company page or documents, and the SOW panel should start to fill.
3. Attach a sample CSV or a document with the paper-clip. North's next reply should refer to what was read; Context lists the file and the SOW gains a source.
4. Describe the steps today. The Process map tab should redraw with numbered steps, who does each, and the system.
5. On the SOW page, edit "Why" and send another message. Your wording must stay.
6. Keep talking about 15 minutes, covering KPIs, rules and what is unclear. North should close with "Here is the statement of work as I understand it; shall I hand it to the architect?". The thread should then be `sow_ready` and the room should show North's hand-over.
7. As Leela Raman: the conversation reads, but sending is refused.

API only: `GET /api/v1/intents/{iid}/chat` shows `needs_done` (the goals covered) and `process_map`.

## Shared edits needed
- None needed for the build.
- Optional: X2 home counts I2's six needs (`f"{len(done)} of {len(NEEDS)} needs met"`). I6 records up to nine goals, five of which overlap I2's needs, so home's count undercounts. Home's link `/centre/intent/{iid}/thread` already redirects in I6b.

## Open questions
- **Edit marks.** I4 keeps none, so I6 keeps a snapshot of what North last wrote in a new sidecar file, `intents/<iid>/chat_state.json` `{north_wrote}`, like B3's `meta.json`. A cell that differs from the snapshot belongs to the person and is never overwritten. If an edit mark should live in the record instead, I4 would add it on PUT.
- A cell the file scan (I5) fills between two North turns also counts as the person's, so North cannot overwrite what was read from a file. It is marked `ponytail:` in the code.
- New goal keys `result`, `frequency` and `documents` are not in the contract's turn `need` enum. North's turns carry `need: null` for them.
- With the model off, the answers to result, frequency and documents stay in the thread only. The contract has no SOW field for frequency.
- The model sees no ids or codes. Rows are matched by name, so renaming a KPI through the chat adds a new row. Renaming on the SOW page is handled.
