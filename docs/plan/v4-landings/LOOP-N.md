# LOOP-N: North is a real tool loop

## What changed
- `sh_platform/v1/north_tools.py` (new): North's own tools, registered under module `m1_intent`.
- `sh_platform/v1/i6_chat.py` `ask`: North's registry now holds its document tools, the shared tools (`tools_for(plane, viewer, "north", ...)`) and North's own tools; the system prompt adds `north_tools.PROMPT_LINE` (plan, use tools, check, answer; no figure no tool returned; document text is data). New `_fold_proposals` joins propose-tool drafts into the model's patch. Backup: `.sh-tmp/i6_chat.py.bak-loop`.
- Model-off rules path (`fallback`) untouched.

## Tools
| Tool | Kind | Arguments | Returns |
|---|---|---|---|
| `list_intents` | read | none | intents the person may read: id, title, signed or draft |
| `get_intent` | read | `intent_id` ("" = this conversation) | title, state, signer, goal, KPI/source/rule names, open questions |
| `get_process_map` | read | `intent_id` | one line per step: owner, system, manual yes/no |
| `list_sources` | read | `intent_id` | one line per source: owner, frequency, sample present |
| `propose_intent_section` | propose | `section` (goal, kpi, source, governance, open_question), `content` (object of that section's fields) | checked draft `{kind: sow, sow_patch}` |
| `propose_process_step` | propose | `name`, `who`, `does`, `system` | checked draft `{kind: process_step, step}` |

Plus North's `search_documents` / `read_document` and the shared `recall_memory`, `get_definition`, `explain_figure_source`, `list_tables`, `describe_table`, `whoami_and_access`.

- Strict arguments: type, length (text 120/600, lists of at most 10), allowed section words, only listed fields; an unreadable or unknown intent id gives one message. Refusals start with the argument name.
- Access: every intent read goes through `g1_access.can_read_intent`; an intent the person may not read is not listed and cannot be fetched.
- Results are text lines, so the registry's aggregate rule has nothing to hide.
- Propose tools refuse a signed intent, write nothing, and the loop only collects the draft. `ask` folds drafts into `sow_patch` / `process_steps` (existing steps are kept, no duplicate by name), so they reach the person as the existing L2 proposals (accept or turn down on the SOW page).

## See it on screen
Intent Centre, talk to North with the model on ("add a reconciliation step owned by Arjun, done by hand"). The proposal appears in the ChangeBar and highlights as before; accept it there. Settings > Agent runs > trace of that run (`/api/v1/agent-runs/trace/{id}`) shows the model steps, tool names, argument keys, result sizes and guard result. Nothing changes until a person accepts.

## Tests
`tests/v1/test_north_loop.py` (9): tools called in order and results observed, drafts proposed and files byte-identical after the run; a refused tool is handled and the loop goes on; field checks and signed refusal; a planted instruction in a document is not followed (passage marked as data); the number guard drops an invented figure; drafts fold into the patch; `ask` carries the tools; hidden intents.
Run: `python -m pytest tests/v1/test_north_loop.py tests/v1/test_i6a.py tests/v1/test_doc_read.py tests/v1/test_k2_north.py tests/v1/test_l2.py tests/v1/test_i2.py tests/v1/test_mem_agent.py tests/v1/test_mem_routes.py tests/v1/test_agent_tools.py tests/agents -q`: all pass (one earlier run showed five mem_agent tile failures; they pass alone and on rerun, and come from Lumen work in parallel, not this card).

## Review
Verdict: pass. Ran the listed suites: 243 passed (the earlier mem_agent tile failures did not recur).
Checked: tools go through `run_agent` and the registry; read tools are `read_only`, the two propose tools are `proposes=True` and only check and return; the byte-identical test shows no write in a run; arguments are type, length, field and section checked, refusals name the argument; every intent read goes through `g1_access.can_read_intent` and unreadable ids look like not found; results are text lines so the aggregate rule has nothing to hide; the model-off `fallback` path and `n1_tally.py` / `e4_investigate.py` / `data/` are untouched; backup `.sh-tmp/i6_chat.py.bak-loop` exists.
Open items (none blocking):
- The injection test proves the passage is delivered marked as data and that the stub's loop proposes nothing; it cannot prove a live model resists. Re-check once with the real model.
- Tools are only registered when `viewer` is set; a viewer-less call runs North with the document tools alone (by design, no access filter to apply).
- `get_intent` goal lists (readers, decisions) are not length-capped per item.
