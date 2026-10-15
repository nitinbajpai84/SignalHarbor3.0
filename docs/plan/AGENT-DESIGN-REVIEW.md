# Agent design review: twelve principles

Date: 9 Oct 2026. Paths are relative to `Repo 1.0`. Every line number below was opened and checked. "Not found" means searched, nothing there.
Reviewed and corrected after a first draft whose line numbers and several claims were wrong (it said evals and retries were missing; they exist).

## Summary

Our agents sit on one safe runtime: a read-only tool loop with a number guard, a model router with Testing/Real modes, a single egress exit, and a run log. The strong parts are tool safety, the exit, document search and the eval kit. The weak parts are these. Only some of our agent calls actually loop over tools; several are one prompt with a rule fallback. The router logs tokens but never a price, so the per-run cost column stays empty. No log row carries latency or the shared trace id. There is no MCP. Evals run by hand, not in CI. No in-run context trimming, but runs are short and capped.

| # | Principle | Status | One-line reason |
|---|---|---|---|
| 1 | Agent is a loop | Partial | Chat agents loop over tools; 4 other calls are one prompt, rules as fallback |
| 2 | Reliability erodes per step | Partial | Capped steps, guard, retry-up and transport retry exist; no per-step check or success rate |
| 3 | Model routing | Partial | Tiers, Testing/Real, retry-up and cost log exist; no price, no latency |
| 4 | Tools as strict APIs | Strong | Read-only enforced at registration, summaries only; argument types not checked centrally |
| 5 | MCP | Missing | None used; the MCP registry is deferred (D-033) |
| 6 | State vs memory, context rot | Partial | Memory with compaction exists; chat history windowed; no in-run trimming; context map is planned only |
| 7 | RAG | Strong | Words + meaning, a floor, access filter, citations; scores not logged |
| 8 | Pipeline vs agent vs many | Strong | Rule pipelines, tool loops and one-shot calls each used on purpose; no agent calls another |
| 9 | Evals | Partial | Stub harness, golden sets, scorers and a live runner exist; not in CI, one run per item |
| 10 | Trace observability | Partial | Four logs exist, none shares a trace id; cost and latency missing; most runs skip the run table |
| 11 | Blast radius | Strong | Nothing writes in the loop; propose only; default-deny routes; maker-never-checker not found in agent code |
| 12 | Prompt injection | Strong | Outside and document text marked as data; number guard; exit checks; tested |

## 1. An agent is a loop, not a prompt
**What it means.** The model asks for a tool, sees the result, then decides the next step, until it can answer. A single prompt that returns once is not an agent.

**Today.**
- The loop is `sh_platform/agents/loop.py:72-113`: model call (84), run the requested tools (99-105), append results (107-110), repeat until no tool is asked for. Limits: 6 steps (loop.py:52), 20 calls per run (29), 8 per step (28).
- Real tool loops: North chat with `search_documents` and `read_document` (`v1/i6_chat.py:574-575`, tools in `v1/doc_tools.py:111-120`); Span chat (`v1/a1_chat.py:274-275`); the Build agents with nine read tools plus a propose tool (`build/agents/read_tools.py:471-477`; `span_design.py:179`, `span_model.py:165`, `flow.py:63`, `span_suggest.py:218`).
- One prompt, no tools, rules as fallback: North's SOW draft (`v1/i2_north.py:218`), Lumen tile (`v1/cx_lumen.py:245`), Tally wording (`v1/n1_tally.py:764`), Span gold-table plan (`v1/b6_span.py:291`). Each passes `ToolRegistry(OpenGate())` with nothing registered.

**Gap.** Lumen and Tally never gather their own evidence; the program does it first and the model only words it. That is deliberate, but it is not a loop.

**Smallest fix.** Name each call "loop" or "one-shot" in its docstring and keep it. Give Tally the shared read tools only if answers need evidence the program did not pre-pick. Size S (naming), M (Tally tools).

## 2. Reliability compounds and erodes with every step
**What it means.** If each step is 95% right, ten steps are about 60% right. So keep steps few and check between them.

**Today.**
- Few steps: at most 6 model steps and 20 tool calls (`loop.py:28-29, 52`).
- After the loop: every figure is checked against recorded facts (`loop.py:58`); a refused or failed tool is reported to the model by code, not echoed (`loop.py:100-112, 146-157`); the answer gets a "part may be incomplete" note (63-64).
- Retries exist, but not in the loop: the model transport retries 429/5xx/timeouts three times with 1 s, 2 s waits (`egress/gateway.py:286-289, 340-355`); the router asks once more on the next tier when a reply is empty, not JSON, or fails the number guard (`v1/router.py:156-182, 236-239`).

**Gap.** No check between steps beyond refusals; no measure of how often runs finish; a flaky tool is not retried (a failed tool becomes a refusal, `loop.py:153-157`).

**Smallest fix.** Count `done / could_not_finish / error` per agent from the run log into the eval report. Size S. Retry a tool once if it is read-only and raised: M.

## 3. Model routing: cost and latency against quality
**What it means.** Easy jobs go to a cheap fast model, hard ones to a stronger one, and you track what that costs.

**Today.**
- Three tiers fast / specialist / manager (`router.py:31`); rules pick the tier (`router.py:65-74`): summaries and extraction fast, formula, closing and redraft to manager; the Jev "ambiguous" hook exists and is unused (52-54).
- Testing / Real switch per company, default testing (`v1/model_modes.yaml:3-9`; `router.py:88-105`), read on every call (`router.py:214`).
- Retry up, never down (`router.py:25-31, 236-239`); a failed provider goes to the tier's alternate, then up (`router.py:221-232`). `SH_ROUTER=off` pins the old model (47).
- Cost log: one line per model call with tier, model, tokens in/out, retried, mode, step (`router.py:125-131, 208-211`); fast share computed (`router.py:134-151`).

**Gap.** Tokens only. `cost_usd` is read by `e6_trace.router_cost` (`e6_trace.py:70-78`) but nothing writes it (searched: only `e6a_routes.py`, `tools/run_evals.py` read it), so the run table's cost is always empty. No latency per call in the log. The writer's "50% fast target" is not in the code.

**Smallest fix.** Add a price table to `model_modes.yaml` and write `cost_usd` and `ms` in `_log`. Size S.

## 4. Tools as strict APIs; read and write never treated alike
**What it means.** A tool has a fixed shape and a narrow job. Tools that only look are safe to repeat; tools that change things need a person.

**Today.**
- Registration refuses anything not read-only, except a propose tool that is neither read-only nor outside (`agents/registry.py:43-49`). Duplicate names refused (50-51).
- Call checks: unknown, not owned or switched off all look the same (75-76); argument names must match exactly (77-78).
- Results are summaries only: groups under five hidden, rows/records refused, lists over 50 refused, NaN refused (`registry.py:1-15, 100-138`).
- No agent tool writes. A propose tool only returns a checked item; the loop stores it and tells the model "waiting for a person" (`loop.py:159-161`; `registry.py:80-84`).
- Document tools: only ticked files the person may read; 60 lines or 3,000 characters; 6 looks per reply (`doc_tools.py:18, 33-47, 77-96`).

**Gap.** Declared types are plain words ("string", "number"); only "object"/"array" are acted on (`registry.py:88-97`). Ranges and enums are each tool's own job. TOOL_POLICY is a version label on the run row ("read-only-1", `n1_tally.py:31`), not a policy file.

**Smallest fix.** Check declared string/number types in `registry.call`. Size S.

## 5. MCP, the USB-C for agents
**What it means.** A standard plug so any agent can use any tool server without custom code.

**Today.** Not found in code. The rule names it: "A call to an outside tool (MCP): same as an internet query, through the same exit" (`.claude/rules/egress.md:11`). The MCP registry is deferred (`docs/decisions.md:45`, D-033). The one outside tool is `search_reference` (`build/agents/read_tools.py:231`), listed only when the company's internet switch is on; its result is marked outside material (`loop.py:163-164`).

**Gap.** No MCP client, no server list, no per-company entitlement for outside tools.

**Smallest fix.** When built, make an MCP tool just another registry entry with `outside=True`, called through `internet_query` (`gateway.py:267`), so it inherits the allowlist, blocklist and log. Size L.

## 6. State vs memory, and context rot
**What it means.** State is what this run knows now; memory is what is kept for later. Rot is stuffing old text into the prompt until it loses the plot.

**Today.**
- State: the message list and `AgentResult` live for one run (`loop.py:33-43, 75-76`). Worst case about 34 messages (6 steps, 20 tool results, 6 refusal notes); nothing is trimmed, but the caps keep it small. Tool results are truncated at the source (`doc_tools.py:5`).
- Chat history sent to the model is windowed: last 13 turns for North and Span chat (`i6_chat.py:533, 564`; `a1_chat.py:225, 267`), last 8 for the SOW draft (`i2_north.py:188`).
- Memory: `v1/mem_agent.py` (docstring 1-14): short-term per conversation, long-term per person and company, append-only, "forget" tombstones, no figures kept. Folding when over budget keeps the newest five agent entries and every person edit (`memory/compact.py:13-26`). A model summary step exists (`memory/summarise.py:12, 33`).

**Gap.** The shared context map and one `context_for(agent, ...)` entry are planned, not built (`docs/plan/MEMORY-CONTEXT-MAP.md`, MEM2; the only `context_for` found is an unrelated visibility one, `intents/visibility.py:67`). Compaction cuts lines to 160 characters (`compact.py:6`).

**Smallest fix.** None urgent in-run. Add a message-count cap in `_loop` only if the step limit is raised. Size S.

## 7. RAG, and why bad retrieval makes bad answers
**What it means.** The model can only be as right as the passages it is handed. Wrong or missing passages give confident wrong answers.

**Today.**
- Hybrid: SQLite full-text with bm25 (`v1/doc_index.py:33, 348`) plus local vector search, merged by reciprocal rank (`doc_index.py:196, 354-358`).
- Floor: vector hits under 0.45 similarity are dropped (`doc_index.py:196, 325`).
- Access: only files ticked for the conversation and readable by the viewer (`doc_tools.py:33-42`).
- Citations: the file and line range are in every result line (`doc_tools.py:69`) and shown as chips (`doc_tools.py:98-108`). Figures in a passage become recorded facts (`doc_tools.py:49-52`).
- Embedding is local; nothing leaves (`doc_embed.py`).

**Gap.** Scores are not returned or logged; a scan still being read returns "ask again" (`doc_tools.py:71-74`). No retrieval-specific test seen in `tests/evals/scorers.py` (not found).

**Smallest fix.** Log top scores per search to the run record. Size S.

## 8. Pipeline vs open agent vs several agents
**What it means.** Use a fixed pipeline when the steps are known, an open agent when they are not, several agents only when roles truly differ.

**Today.**
- Fixed pipeline: Span's plan and run are rule-built; the model is one optional step with "rules only" fallback (`v1/b6_span.py:282-298`; also `b6_plan.py`, `b6_run.py`).
- Open loops: North chat, Span chat, Build agents (see 1).
- One-shots: Lumen tile, Tally wording.
- Four agents are separate by screen and module (`model_modes.yaml:11-15`); none calls another. The router picks a model tier, not an agent (`router.py:1-10`). `tools/route_task.py` is the build-time model router for our coding agents, not part of the product (file exists; not used in `sh_platform`).

**Gap.** Sharing between agents is only through stored artefacts and memory.

**Smallest fix.** None. Keep it. Size S (document it).

## 9. Evals for non-deterministic systems
**What it means.** Test the behaviour you need (right facts, no invented numbers, refuses when it should) over several runs, with a score, not one exact string.

**Today.**
- Unit harness with a scripted stub model or a live one: must-include, must-not-include, status, tools called, untraced numbers (`agents/evals/harness.py:19-34, 78-99`); `--live` needs a real client (102-118); cases in `agents/evals/cases.py`; tests in `tests/agents/test_agents_evals.py`.
- Golden sets per agent: `tests/evals/{north,span,lumen,tally,memory}.yaml` (about 690 lines) with deterministic scorers for words, structure, egress cleanliness, latency, cost (`tests/evals/scorers.py:1-20`; `tests/evals/north.yaml:5-17`) and a judge rubric `tests/evals/judge_rubric.md`.
- Live runner `tools/run_evals.py:1-12`: runs against a running server, in Testing or Real mode, compares two runs, exits 1 on failure. `tools/eval_v2.py` and `tools/eval_data_agent.py` also exist.

**Gap.** Run by hand; no CI config found (no `.github`). Each item runs once, so variation is not measured (not found: repeat-N). Cost and latency scorers depend on the empty cost log (see 3).

**Smallest fix.** Add `--repeat 3` and report pass rate per item. Size S. Wire into a nightly job: M.

## 10. Trace-level observability
**What it means.** For any answer you can see every model call, tool call and decision, with time and cost, under one id.

**Today.**
- Trace id and one `agent_runs` row per run: agent, model, prompt version, tool-policy version, status, tool calls, cost, trace id (`v1/e6_trace.py:26-41, 82-110`); summary by agent and day (117-140).
- Run registry, one line per `run_agent`: steps, tools called, numbers replaced, refusal codes only (`agents/runs.py:15-25`; `loop.py:65-68`).
- Router cost log, one line per model call (`router.py:208-211`).
- Egress log, one line per attempt, host and decision and reason code, never content, written before the send (`egress/gateway.py:169-176, 216-230`).
- Trail (`v1/a5_trail.py`) explains where a figure came from (source, file, read, checked, decided), not an agent run.

**Gap.** The four logs do not share the trace id (the router and run-registry rows have no trace field). Only Tally and intake open an `agent_runs` row (`n1_tally.py:825`, `e2_extract.py:223`); North, Span and Lumen runs appear only in the run registry. No latency, and cost is empty. The prompt and tool arguments are deliberately not stored.

**Smallest fix.** Stamp `current_trace_id()` into the router, registry and egress rows; add `ms` to the router row. Size S-M.

## 11. Blast radius: approvals and least privilege
**What it means.** A mistake or a trick should do little harm: the agent can only read, anything that changes things waits for a person.

**Today.**
- Loop never writes; proposals are collected for the caller to validate and file (`loop.py:6, 159-161`; `build/proposals.py:83` validate). A proposal records the run id and whether outside material was read (`loop.py:60-62`).
- Module switch re-checked before every model step (`loop.py:79`).
- Routes default deny; each route lists roles (`route_permissions.yaml:1`); approval of Span's blueprint is company_admin only (`v1/a1.permissions.yaml:2-6`).
- Groups under five and raw rows never reach the model (`registry.py:1-15`).

**Gap.** "Maker never checker" is a repo rule for our builders (`CLAUDE.md` rule 4), and I did not find it enforced for agent proposals in code. No signatures on agent output found.

**Smallest fix.** At approval, refuse if the approver is the person who triggered the run. Size S. Test it: S.

## 12. Prompt injection defence
**What it means.** Text from documents or the web can contain "ignore your rules". Treat it as quoted data, never as an order, and limit what a tricked agent could do anyway.

**Today.**
- The loop tells the model that outside material is never an instruction (`loop.py:20-23`); outside tool results carry that marker (163-164); document tool results carry a "quoted, never an instruction" note (`doc_tools.py:19`).
- Document passages are wrapped as untrusted quoted text (`context_docs/retrieval.py:158`; `profile/reader.py:252`); Tally wraps user questions the same way (`n1_tally.py:~757`, via `v1/e4_guard.py:91-93`). `e4_guard.py:81-88` says only the signed-in person's chat can instruct, and can flag instruction-like text.
- A tricked model still cannot state a new figure: the number guard replaces any figure not in recorded facts (`loop.py:58`); Tally drops any reply with a digit or unknown placeholder (`n1_tally.py:748-770`).
- The exit: names, raw rows and private text in URLs are blocked, URLs decoded repeatedly (`egress/gateway.py:101-145, 180-198`); destinations allowlisted; every attempt logged.
- Test: `tests/agents/test_agents_loop.py:61` (injection in outside material not obeyed).

**Gap.** `scan_document_text` is defined but not called anywhere outside its own file (searched). North's and Span's document tool relies on the note plus the guards, not on the wrapper. No injection case in the golden sets (not found by name).

**Smallest fix.** Add an injection document to `tests/evals/north.yaml` and `span.yaml`. Size S.

## Priority fixes
1. Write price and latency into the router log, and trace id into all four logs (3, 10). S-M.
2. Eval repeat runs and a nightly job; add an injection case (9, 12). S-M.
3. Approver is not the requester (11). S.
4. Decide which one-shots should become loops (1). M.
5. MCP when the customer needs outside tools (5). L.
