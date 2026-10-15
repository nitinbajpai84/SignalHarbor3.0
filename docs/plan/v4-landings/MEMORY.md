# Agent memory landing (9 Oct)

Nitin: "Lumen have no short term or long term memory building? its essential build it" and "that should be through for the agents".

## Reuse check

- Found: the earlier repo's agent memory, already ported here as `sh_platform/memory/` (MEM-1/2: one entries list per agent and person, merged by text similarity) and its Settings page `ui/src/pages/MemoryPage.tsx`. Reused: `memory/filters.py` (no figures, emails, account numbers or restricted names are ever kept), `jsonfile` lock and atomic write, `plane.path`, the Settings section and its page. Not used as the store: its shape is one replaced list per agent, with no per-item source, agent, certainty or supersedes, and no memory shared across agents. So `mem_agent.py` is a new store beside it; the old lists stay and the Settings page shows both.
- Nothing in either repo kept a conversation focus (the last tile, plan change, case) or edited a tile from a follow-up; that is new.

## What changed

- `sh_platform/v1/mem_agent.py`, one memory for North, Span, Lumen and Tally, in `data/<company>/memory/v1/`:
  - Short term, per conversation (agent + person + project/intent/case): the last 12 turns and the focus object. Files `convo/<hash>.json`.
  - Long term per person (`people/<hash of person>.json`): preferences (colour, currency, period, chart type, answer style), facts, corrections. Each item keeps the words that caused it, the agent, time, and how sure (`said`, `inferred`, `model`). Append-only: a change adds an item that supersedes the old one; forgetting adds a tombstone and blanks the old words.
  - Long term per company (`company.json`): free notes, and agreed words stored as a link to a K2 concept (the definition stays in K2 and is spelled out at recall time). Everyone in the company reads them; company_admin and analyst write.
  - `recall(agent, viewer, context)` returns the few items that matter (a preference keyed for another agent is skipped; facts and corrections are shared by all agents), `lines(...)` the same as plain strings for a prompt.
  - Writing is by rules first (`learn`): lasting words ("always", "from now on", "I prefer"), corrections ("no, I meant..."), and style follow-ups. The model proposes items only through `run_agent` (the egress client), only for a message that states something about the person, and only when its reply states no figure; whatever it proposes is shown as "I will remember: ...".
  - Never kept: figures, emails, account numbers, restricted names (the old memory filters).
- Lumen (`cx_lumen.py`): every tile now carries the recipe it was made from. A follow-up that changes style or period edits the focus tile as a new proposed version (`replaces` the old; the old one goes when the new one is accepted, or at once if it was never accepted). Handled: dots/points, bar, area, line, "in blue" (and other colours), "monthly rather than daily", "by entity", "no split", "in SGD" (switches to the `<figure>_sgd` column when the project has one; says so when it does not), "last 12 months". SQL and spec are built by the program; no figure is typed. Questions are still answered in words (TALK-TO-ALL). Colour, period and currency from a follow-up are remembered ("I will remember: ...") and applied to new tiles, and Lumen says so ("I used what I remember about you: blue lines and figures in SGD"). A chart type is remembered only when said to be lasting.
- North (`i6_chat`), Span in Design (`a1_chat`), Span in Build (`b6_span`): recall goes into the model context as strings (`memory`), the turn and focus are kept, and what is learned is appended as "I will remember: ...".
- Routes (`mem_routes.py`, `mem.permissions.yaml`): `GET /api/v1/memory/me`, `PATCH|DELETE /api/v1/memory/me/{id}`, `GET /api/v1/memory/company`, `POST /api/v1/memory/company`, `PATCH|DELETE /api/v1/memory/company/{id}`. All six roles for their own items; company writes company_admin and analyst.
- UI: Settings, "What the agents remember about you" now opens with "Learned from your conversations" (by agent, Correct, Forget this; a company tab with Add for those who may); the Lumen chat head shows "Lumen remembers: ... Change this".
- Edited shared files (backups in `.sh-tmp/*.bak-mem`): `cx_dash.py` (tiles keep `recipe`; `replaces` handled on propose and accept), `cx_lumen.py`, `i6_chat.py`, `a1_chat.py`, `b6_span.py`, `MemoryPage.tsx`, `ProjectPage.tsx`, `cxui.test.tsx`, `docs/reuse-inventory.md`.

## How to see it

1. Sign in, Consume, open the project, ask Lumen: "show net worth per month".
2. Say "make it dots" (the proposed tile is replaced by a dots version), then "line in blue" (a line, blue; Lumen says "I will remember: you like blue for chart lines"), then "monthly rather than daily", "by entity", "in SGD" if the project has an SGD column.
3. Sign out and back in, ask a new tile ("net worth per month"): it comes in blue and Lumen says it used what it remembers. The chat head shows "Lumen remembers: ...".
4. Settings, What the agents remember about you: see the lines by agent, correct one ("I like green"), or Forget this; ask a new tile again to see it gone.
5. Tell North "Always keep answers short" in an intent chat: North ends its reply with "I will remember: you like short answers", and the next turn's model context carries it.

## Tests and results

- `tests/v1/test_mem_agent.py` (15 + 1 Span hook): dots, blue, monthly edit the last tile; accepting a new version replaces the accepted old one; by entity, last N months, SGD; a question stays words; preference persists across sessions and new tiles use it; a mark is kept only when lasting; person A never sees person B; another company never sees it; forgetting removes it from recall and blanks the file; supersedes and correct keep history; corrections and lasting words are learned, figures and emails are not; short-term turns and focus; company rights and K2 link; the model sees memory only through `run_agent` and in a shape `json_findings` passes, and not another person's; a model-proposed item is shown, a reply with a figure keeps nothing.
- `tests/v1/test_mem_routes.py` (2): North remembers over HTTP, the person lists, corrects and forgets; a colleague and another company see nothing; company items read by all, written by admin and analyst only.
- Ran: `pytest tests/v1/test_mem_agent.py tests/v1/test_mem_routes.py tests/v1/test_cx.py tests/v1/test_cx_share.py tests/v1/test_b6.py tests/v1/test_b6_diagram.py tests/v1/test_b6_run.py tests/v1/test_a1.py tests/v1/test_i6a.py` -> 74 passed.
- vitest: `src/pages/agentMemory.test.tsx` (6, new), `memoryPage.test.tsx`, `src/v1/cxui` (6, one new for the chat-head line), `src/v1/s1` all pass; `npx tsc --noEmit` clean.
- Not run: the full suite and the security pass (after MVP, per plan); no server started, no vite build.

## Limits (ponytail)

- A tile written by the model (model on) has no recipe; a follow-up reads it back from its SQL and spec, and refuses what it cannot read.
- Colour applies to a single series; a split tile keeps its series colours and Lumen says so.
- Currency changes the figure only when the project has a `<figure>_<currency>` column; no conversion is invented.
- Company terms store the link and show the K2 concept's name; they do not copy its definition text.
- Short-term memory is per conversation and not cleared by "forget"; it holds the last 12 turns only.

## Hook for Tally (do not edit n1_tally.py or e4_investigate.py here)

In the case chat of Tally, with the viewer and the case id:

```python
from sh_platform.v1 import mem_agent as MEM
context["memory"] = MEM.lines(plane, "tally", viewer, {"convo": case_id, "text": latest})   # strings, put in the model context before run_agent
...
shown = MEM.after_turn(plane, "tally", viewer, case_id, latest, reply, {"case": case_id})   # after the turn; focus = the case
if shown:
    reply += " " + MEM.remember_line(shown)    # "I will remember: ..." shown to the person
```

`lines` never raises and returns `[]` when nothing is stored; `after_turn` never raises. Pass `model=` (the routed egress client) to `after_turn` only if the model may propose items; leave it out for rules only. A different focus object (the open check, the draft reply) can be passed as the dict in `after_turn` and read back with `MEM.focus(plane, viewer, "tally", case_id)`.

## Review (security, 9 Oct)

Verdict: **pass after fixes**. I checked it adversarially and wrote a test for each finding. Four of the five new tests failed on the code as it was handed over. All pass now.

What held as built:
- **People.** The memory file name comes only from the signed-in person, so no route names another person. Correcting or forgetting another person's item id returns 404.
- **Companies.** The plane comes from the session, so another company sees nothing (unit and HTTP tests).
- **Company items.** Writing, correcting and forgetting are refused (403) for anyone but `company_admin` and `analyst`, both in the logic and in `mem.permissions.yaml`. The new yaml lines cover only `/api/v1/memory/...` and do not clash with the old `/api/memory/...` stubs. Every other route stays default-deny.
- **Egress.** Memory reaches a model only as strings in the `run_agent` context. That covers North, Span in Design, Span in Build, Lumen and `propose`, all through the routed gateway client, and the stub asserts it (`json_findings` is clean). Recall never sends the short-term turns, and the focus line holds only ids.

Fixed in `sh_platform/v1/mem_agent.py` (backup `.sh-tmp/mem_agent.py.bak-memreview`):
1. **Forget left the earlier versions.** It blanked only the live item, so the version it had corrected away kept the original words on disk. It now blanks the whole supersedes chain.
2. **Two people could share one memory.** A viewer without an account id was keyed by display name, so two people with the same name shared one memory. With a shared name and no account, the person now has no memory: reads are refused and learning keeps nothing.
3. **Figures were kept as the source.** The message that caused a preference was stored as `source.said` even when it held a figure or name, for example "in blue, net worth was 4.2m". That text is now kept only when it passes the same filters. The preference is still learned.
4. **The filter failed open.** If the restricted-name list could not be read, the code treated it as empty. Nothing free is kept now. A missing profile still reads as empty, so only a broken profile triggers this.
5. **Company words were not filtered.** A company term's word now goes through the same filter.

Tests: 5 added to `tests/v1/test_mem_agent.py` (`test_review_*`).
- pytest: `tests/v1/test_{a1,b6,b6_diagram,b6_run,cx,cx_share,i6a,mem_agent,mem_routes}.py`: **79 passed**.
- vitest: `agentMemory.test.tsx` and `memoryPage`: **9 passed**.
- `tsc --noEmit`: clean.

Open items:
- The short-term turns (`convo/*.json`) keep the raw words of the last 12 turns, which can include figures. They stay in the company plane, are never sent to a model and are never shown, but forgetting an item does not clear them. Either scrub figures there or clear a conversation on request.
- The Tally hook is documented, not wired in (n1_tally.py and e4_investigate.py are owned by another agent).
- Names that are not in the restricted list (an ordinary colleague) can be kept in a fact. They are tokenised by the gateway on the way out.
- `correct()` reads outside the file lock (the write is locked). Two corrections at the same moment could both land, the last one winning. It is not a leak.
