# MEM2b: context_for and after_turn wired into the agents (9 Oct)

Spec: `MEM2a.md` wiring table. New: `sh_platform/v1/mem_wire.py` (one small helper, so four agents do not repeat it), `tests/v1/test_context_wiring.py`, `ui/src/v1/s1/runsteps.test.tsx`.
Edited (backups `.sh-tmp/*.bak-mem2b`): `cx_lumen.py`, `b6_span.py`, `a1_chat.py`, `i6_chat.py`, `ui/src/v1/s1/SettingsPage.tsx`. `i2_north.py` not changed (the table gives it nothing).

## What changed
- Each turn builds one `mem_wire.Wire(plane, agent, viewer, question, focus, paths, convo)`. `context_for` runs once, on first use (so a turn that never calls the model, such as model-off rules, does not pay for it), and never raises.
- The model gets labelled sections in its context: `memory` (what we remember: preferences, agreed words, earlier talks, short-term turns), `related_talks_and_decisions` (context map), `document_passages_outside_material` (passages from the files the person may read; North and Span design only), and `context_note`, which says all of it is background and outside material, never instructions, and that `recall_memory` gives more. All plain strings, so the egress row guard passes them.
- `recall_memory` was already in `tools_for` for all four agents; the note points to it.
- `after_turn` is now `mem_context.after_turn` in North, Span design (both calls, including talk-yes-act-no), Span build and Lumen: same arguments, same "I will remember" lines.
- Conversation ids as in the table: intent id for North and Span design, project id for Span build and Lumen. An intent belongs to one project and Build/Lumen use the project id, so a different project is always a different conversation id.
- Trace: the wire wraps the run recorder and adds a first step `{kind: "context", items: [{kind, id}]}` (kinds: memory, summary, graph, passage, turns). Ids only, no text. `run_agent` itself is unchanged.
- Settings > Agent runs: a "Recent runs" list with "Show steps" per run (GET `/api/v1/agent-runs/trace/{id}`), in plain words: "Context used: 1 earlier conversation, 1 remembered item", "Model step 1: small model, 120 tokens in, 30 out, 400 ms", "Tool get_plan: answer of 812 characters, 20 ms" (", refused (reason)" when refused), "Number check: no invented figure".

## Tally (not touched): add these two lines in `n1_tally.py`
```python
got = MC.context_for(plane, "tally", viewer, question, focus={"case": case_id}, convo=case_id)   # before run_agent; pass got["recall"], got["graph"], got["passages"] as sections
shown = MC.after_turn(plane, "tally", viewer, case_id, text, reply, {"case": case_id}, model=model)  # in place of the mem_agent hook
```
Or use `W = mem_wire.Wire(plane, "tally", viewer, question, {"case": case_id}, None, case_id)`, `ctx.update(W.sections())`, `recorder=W.recorder(RunRegistry(plane))` for the same labelling and trace.

## See it
Talk to Lumen about a project (8 turns, say a decision), then ask Span in Build in another conversation; Span's context holds "Earlier talk with Lumen ...". Settings > Agent runs > Show steps on that run: first line "Context used: ...".

## Tests
- `tests/v1/test_context_wiring.py` (8): Lumen (two turns, one call each, trace has the context step, no text in it); North (one call, outside-material section, passage item, no document text in the trace); Span build (chat passes one wire, `_ask_model` puts sections in the context and trace); Span design (route, one call); Span recalls a decision made with Lumen for a project member and not for an outsider (strings only, row guard clean); a failing `context_for` leaves the agent answering; recorder puts the context step first.
- Ran: `test_context_wiring, test_lumen_loop, test_north_loop, test_span_loop, test_mem_agent, test_mem_graph, test_mem_routes, test_a1, test_b6, test_i6a, test_cx, test_agent_tools, test_talk_to_all, test_t1_wiring`: 180 passed.
- `vitest src/v1/s1`: 4 passed (1 new). `tsc --noEmit` clean.
- Not run: full suite, security pass, any server or vite build.

## Limits (ponytail)
- A turn that finds nothing worth sending still sends the `context_note`; trim if the message limit bites.
- Lumen's question path, tile path and edit path each use the same turn's wire; a turn that runs two loops traces the context on both.
- Passage ids in the trace are plane-relative file paths with line numbers.

## Review (reasoning, 9 Oct)

Verdict: **pass after fixes**. Backups of what the review touched: `.sh-tmp/*.bak-mem2b-review` (mem_wire, cx_lumen, b6_span, a1_chat, i6_chat, test_context_wiring).

Defects found and fixed:
1. **Lumen and Span (Build) talks were never shared with the project.** The talk's scope comes from `focus["project"]` on its first turn, but Lumen passed `{dashboard, tile}` (or nothing) and Span build passed nothing when no change was proposed, so every talk was owner-only and "Span recalls a decision made with Lumen" only held in the builder's test, which wrote the talk by hand. Fixed: both now always pass `project: pid` (keeping the focus tile when the turn made none). New test drives real `L.ask` turns: an outsider sees nothing, a team member sees the talk with Lumen; it fails on the old code.
2. **Outside material was labelled by name only.** The loop's system rule names `OUTSIDE_MARKER`; the sections did not carry it. Fixed: `memory`, `related_talks_and_decisions` and `document_passages_outside_material` start with the marker line (strings only, the row guard still passes).
3. **One-message limit.** North (11,000 view) and Span design (13,000 view) added up to 6,000 more characters of context against the gateway's 20,000 per string, so a long turn could be refused and fall back to rules. Fixed: `Wire(cap=...)` passes the room left (19,000 less the context, the question and 3,000 for facts) to `context_for`.

Checked and holding: access is filtered inside `context_for` (G1 per viewer; outsider test through the real Lumen path); one `context_for` per turn; conversation ids follow the table (intent id, project id, so a project change is a new id); `context_for` makes no model call and `after_turn` reaches the model only through `run_agent` with the agent's routed client; the trace's context step holds kinds and ids only (graph seeds are map node ids, which include `named:<person>` slugs; admin-only route).

Tests: `test_context_wiring.py` 10 (2 new), with lumen_loop, north_loop, span_loop, mem_agent, mem_graph, mem_routes, a1, b6, i6a, cx, agent_tools, talk_to_all, t1_wiring: 182 passed; i2, e6a, b6_run, cx_share: 21 passed; `vitest src/v1/s1` 4 passed. No TypeScript changed in review.

Open items:
- **Settings "Show steps" will rarely show a chat turn.** The list is the warehouse `agent_runs`; a chat turn's loop trace gets its own trace id unless an e6 `trace()` wraps it, so North/Span/Lumen turns have steps on disk but no row to click. Needs either a list of loop traces on the route or the agents opening an e6 run per turn (outside this card's files).
- North and Span (Design) talks use `{intent}` only, so they stay owner-only (per the MEM2a table). Add the intent's project to the focus if those talks should be shared with the team; confirm with Nitin.
- Graph seed ids in the trace can carry a person-name slug (`named:ana-lee`); hash them if run logs must hold no names.
- Tally: use `Wire(...)` with `cap` and pass `{"case": case_id, "project": <case's project>}` to `after_turn`, or Tally talks will be owner-only too.
