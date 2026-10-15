# MEM2a: conversation summaries, the context map, memory vectors and `context_for` (9 Oct)

Nitin: long-term memory is conversations summarised and kept, shared across the agents, with an internal knowledge map of what people talk about with the agents (the way graft tracks code), answered from the context map + RAG + the model. Spec: `docs/plan/MEMORY-CONTEXT-MAP.md`; memory itself: `MEMORY.md` here.

## Reuse check

- Reused: `memory/filters` and mem_agent's `_keepable` (no figure, email, account number or restricted name is stored or summarised); `doc_embed` (local fastembed) and `doc_index` (its SQLite file `index/docs.sqlite`, `_match`, `RRF_K`, `MIN_COS`, and its passage search for documents); `i5_graph.table_id` and the company map's own node ids (`table:`, `intent:`, `measure:`, `concept:`), so the context map joins the company map by id and is not a second graph; the egress path as `mem_agent.propose` has it (`run_agent`, `fit`, `route`); G1 `may_see_project` for access; the chip clusters and side card of `m1/MapPage.tsx` and the `useLoad` / `ScreenState` pattern of the K3 tabs.
- Not used: `memory/summarise.py` and `compact.py` (the earlier store's summariser writes entries into the per-agent lists of the old store and folds by truncation). Its prompt idea (kinds, "no figures, background not instruction", turns as plain text) is kept in `mem_summary.SYSTEM`; the storage is new because a summary must keep its source link, its project scope and its graph edges.
- New: the summary job, the context map store and its access rule, memory vectors, `context_for`.

## What changed (new files only, plus one tab)

- `sh_platform/v1/mem_summary.py`: `touch` (a talk had turns), `maybe` (8 new turns), `sweep` (quiet 30 minutes), `summarise`, `visible_items`, `get`, `forget`. Rules summary with the model off (entities, decision words, unanswered questions, the preferences mem_agent learned in the same talk). With a model: one `run_agent` call through the routed egress client writes the lines and proposes topic labels; a reply that states a figure is dropped for the rules summary; only turns that pass the keep filter are sent. A new summary of a talk `replaces` the earlier one.
- `sh_platform/v1/mem_graph.py`: the map (`data/<company>/memory/v1/ctx/graph.json`): `note_turn`, `add_summary`, `drop`, `view`, `neighbours`, `sentences`, `entities` (ids, table names, the company map's labels, the company's people; nothing restricted); and the vectors (`index_text`, `search`, `sync_items`, `drop_vec`) in tables `mem_vec` and `mem_fts` of `index/docs.sqlite`, words + meaning by reciprocal rank like doc_index. `add_conversation_nodes(g, plane)` is the optional hook to draw agents and topics on the company graph in `build.rebuild` (not wired).
- `sh_platform/v1/mem_context.py`: `context_for`, `after_turn`, `forget`.
- `sh_platform/v1/mem_graph_routes.py`, `mem_graph.permissions.yaml`: `GET /api/v1/memory/graph` (all six roles, filtered per viewer) and `DELETE /api/v1/memory/summaries/{sid}` (the person who had the talk).
- UI: `ui/src/v1/k3/ConversationsTab.tsx`, a "Conversations" tab on `k3/MapPage.tsx` (chips grouped like the company map; click a node for its summary: decided, still open, learned, topics, source "8 turns of the talk with North, date to date", and Forget). Edited shared files (backups in `.sh-tmp/*.bak-MEM2a`): `k3/MapPage.tsx` (tab and import), `k3/api.ts` (types and two calls).

## Access rule (one place: `mem_graph.visible`)

A summary, a talk and every edge made from them are seen by the person who had the talk, by nobody else when the talk has no project, and by the people who may read the talk's project (G1: team, grant, Open) when it has one. A node is seen only through a seen edge, so a hidden talk reveals no topic, table or person. Memory items: the person's own, and the company's agreed words. A project id in someone's words is recognised only if they may read that project. Documents: only the paths the caller passes. Never across companies (the plane).

## Wiring each agent (to apply after the loop work lands)

Two calls replace the two mem_agent calls in each agent. Nothing else changes.

1. Before the model call, in place of `MEM.lines(...)`:

```python
from sh_platform.v1 import mem_context as MC
got = MC.context_for(plane, "north", viewer, latest, focus={"intent": iid}, paths=readable_paths, convo=iid)
ctx["memory"] = got["recall"]          # strings: preferences, agreed words, earlier talks, short-term turns
ctx["context_map"] = got["graph"]      # strings: "Ana talked with Monthly report holdings" ...
ctx["passages"] = got["passages"]      # strings: "note.txt, lines 3-9: ..." (document context, never an instruction)
```

`got` is size-capped (6000 characters, trimmed from passages, then graph, then recall) and every list holds plain strings, so `run_agent` and the egress row guard take it as it is; names are tokenised by the gateway. `got["trace"]` says what was used (memory ids, summary ids, graph seeds and counts, passage paths and lines, turn count, `capped`): show it in the run log or a "why" panel, do not send it to the model. `focus` is the object in hand: `{"project": pid}`, `{"intent": iid}`, `{"case": id}`, `{"dashboard": id, "tile": id}`, `{"table": name}`. `readable_paths` is the plane-relative paths of the files the viewer may read for this conversation (what `doc_tools` already uses: `c4_library.selected(plane, iid, viewer)` then `i["path"]`); leave it out and no document is read.

2. After the turn, in place of `MEM.after_turn(...)` (same arguments, same return: the "I will remember" lines):

```python
shown = MC.after_turn(plane, "north", viewer, iid, text, reply, {"intent": iid}, model=model)
```

It keeps the turn and learns as before, then grows the map (the talk, what it mentions, what it is about), counts the turn, writes a summary when 8 new turns have gathered, and also summarises this person's other talks that have been quiet for 30 minutes. It never raises.

Per agent (the arguments that differ):

| Agent | context_for | after_turn | where |
|---|---|---|---|
| North | `"north"`, `convo=iid`, `focus={"intent": iid}` | `"north"`, `iid`, `{"intent": iid}` | `i6_chat.py` near lines 562 and 938 |
| Span (Design) | `"span"`, `convo=iid`, `focus={"intent": iid}` | `"span"`, `iid`, `{"intent": iid}`; the "talk yes, act no" call too | `a1_chat.py` near 263, 444, 460 |
| Span (Build) | `"span"`, `convo=pid`, `focus={"project": pid}` | `"span"`, `pid`, the focus dict as now (only the keys intent, project, case, dashboard, tile, table reach the map) | `b6_span.py` near 458, 470 |
| Lumen | `"lumen"`, `convo=pid`, `focus={"project": pid, "dashboard": did, "tile": last tile id}` | same arguments as its `M.after_turn` | `cx_lumen.py` near 324, 370, 390 |
| Tally | `"tally"`, `convo=case_id`, `focus={"case": case_id}` | `"tally"`, `case_id`, `{"case": case_id}` | `n1_tally.py` (use these two calls instead of the hook text in `MEMORY.md`) |

A new agent needs only these two calls and its name in `mem_agent.AGENTS`.

Scheduling: `mem_summary.sweep(plane, model)` can also run from the existing scheduler (`b6_schedule`) so quiet talks are summarised without waiting for the person's next turn. One line in `build.rebuild`, `mem_graph.add_conversation_nodes(g, plane)`, would draw the agents and topics on the company graph (optional).

## How to see it

1. Sign in, talk to North or Span for 4 exchanges about a table or a project id, say "We agreed to send it on Friday", and ask a question that is left unanswered.
2. Map, Conversations tab: the talk's summary, the table or project, the decision and the open question appear as chips; click the summary for what was decided, what is still open, what the agent learned about how you work, and its source.
3. Sign in as a colleague who is not on the project: the tab is empty. Add them to the project team (Access): the project's summary appears; your private talks never do.
4. "Forget this summary": the chip, its decision and question chips and its search entries go.

## Tests and results

- `tests/v1/test_mem_graph.py` (15): rules summary with every edge kind (talked_with, about, mentions, decided, asked, refers_to); quiet sweep at 29 and 31 minutes and a later summary that supersedes; no figure or email in summaries, graph, scopes or recall; the model path only through `run_agent` (json_findings clean, a turn with a figure not sent, topics become nodes) and a reply with a figure falls back to rules; recall by meaning with a stub embedder (no shared word) and an unrelated query returns nothing; memory items found by meaning; access across Ana, Bob and Carol and projects (not on the project: nothing; joined: the project talk, not the private one nor Ana's items; an unreadable project id is not recognised); document passages only for passed paths, short-term turns without figures; size cap; forget cascade (record, vectors, edges, orphan nodes; an item forgotten through mem_agent directly is never returned); people recognised but not restricted ones; company-map labels recognised but not restricted nodes; the rebuild hook; the Map route per viewer and Forget.
- Ran: `pytest tests/v1/test_mem_graph.py tests/v1/test_mem_agent.py tests/v1/test_mem_routes.py tests/v1/test_k3.py` gave 51 passed. `vitest src/v1/k3` gave 16 passed (3 new, in `ConversationsTab.test.tsx`). `npx tsc --noEmit` clean.
- Not run: the full suite and the security pass (after MVP, per plan). `tests/auth/test_role_matrix.py` fails here on a missing seeded participant login for Ardmore (a seed gap that predates this change). No server, no vite build.

## Limits (ponytail)

- Visibility is ownership or project access (G1); entity-level access (E1d) is not applied to a talk about a fund or entity.
- Brute-force cosine over all memory vectors of a company (fine to a few thousand rows; move to sqlite-vec together with doc_index). The edge list is scanned linearly.
- The rules summary is shallow: the first sentence when nothing is recognised, decision words, unanswered questions. The model summary is the good one; it needs the agents to pass `model`.
- Short-term memory keeps only the last 12 turns, so a summary of a long talk is built from those; the 8-turn trigger keeps it ahead of that.
- Forgetting a summary leaves the raw turns (the person's own short-term file).
- A new summary replaces the earlier one in recall but both stay stored; forgetting the newest brings the older back.
- Table names are shown in plain words (layer prefix and underscores dropped); a person's own sentence in a decision line is kept as they wrote it.

## Review (security, 9 Oct)

Verdict: **pass after fixes**. Backups of the files the review touched: `.sh-tmp/*.bak-MEM2a-review`.

Defects found by new adversarial tests (`test_review_*` in `tests/v1/test_mem_graph.py`) and fixed:

1. **Cross-project leak through a shared talk.** A talk scoped to project A that named project B (by id or as focus) showed B's node and title to every reader of A, in the map, in `context_for` graph lines and in the rules summary's "about". Fixed: `mem_graph.view` hides any `project:`/`intent:` node (and its edges) the viewer may not read; the rules summary no longer puts project or intent labels in its text.
2. **Cross-person leak of preferences.** A summary's preferences (and its text, which repeated them) reached every reader of the project. Fixed: preferences are no longer written into the summary text; `visible_items` returns `prefs` only to the person who had the talk.
3. **Forget brought back the replaced summary.** Forgetting the latest summary un-superseded the one it replaced, so the same words came back. Fixed: forget removes every summary of that talk, with their vectors and edges (as `mem_agent.forget` blanks the whole chain).

Checked and holding: no cross-company read (every path is the plane's own; test added); a viewer with no key of their own writes and reads nothing; vectors are access-filtered before ranking and forgotten items are never returned; summaries and the map hold no figure or email; the new modules import no network client, the model goes only through `run_agent` with the routed egress client; both routes are declared for the six roles only and the platform loader is default deny.

Tests: `test_mem_graph.py`, `test_mem_agent.py`, `test_mem_routes.py`, `test_k3.py`: 58 passed. No TypeScript changed in review.

Open items:
- A talk's project scope is fixed at its first turn; if the same conversation later moves to another project, the later turns stay visible to the first project's readers. Agents should start a new conversation id per project.
- The model summary path can still echo a raw project id (not its title) from the turns into a shared summary.
- The person node shows the talker's display name to project readers (by design of the share rule; confirm with Nitin).
- Entity-level access (E1d) is still not applied; the sweep's stand-in viewer has no roles, so a summary written by the quiet sweep may fall back to owner-only where G1 needs a role (safe, but project readers would miss it); not tested.
