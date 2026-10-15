# Connect an assistant to Signal Harbor (MCP)

Signal Harbor speaks the Model Context Protocol (2025-06-18; 2025-03-26 and 2024-11-05 also accepted). An assistant such as Claude acts as **you**: it sees only what you see, and it can only draft changes that you then accept.

## 1. Make a token (Settings)

Settings > Assistants > New token: name it after the assistant, pick scopes and a lifetime (default 30 days, at most 365).
Scopes: `read` (look things up), `propose` (draft cases, tickets, tiles, pipeline changes), `export` (Word, PDF, diagram).
The token text (`shmcp.<company>.<id>.<secret>`) is shown once. We keep only a hash. Revoke it in the same screen at any time; it stops working at once. A company admin can revoke any token of the company. Up to 10 live tokens per person.
API behind the screen: `GET/POST /api/v1/mcp/tokens`, `DELETE /api/v1/mcp/tokens/{id}`, `GET /api/v1/mcp/drafts`.

## 2. Connect

Streamable HTTP (JSON replies, one message per POST):

    claude mcp add --transport http signal-harbor https://<your-host>/mcp --header "Authorization: Bearer <token>"

Other assistants: URL `https://<your-host>/mcp`, header `Authorization: Bearer <token>`.

Stdio (same server, runs next to the data folder):

    SH_MCP_TOKEN=<token> python -m sh_platform.mcp --data-root <data folder>

## 3. What every call goes through

1. Token -> your account (your roles are read fresh, so a changed role or a disabled account applies immediately).
2. The token's scopes; a tool outside them looks exactly like a tool that does not exist.
3. Your own access inside the tool (project team, intent access, restricted lines): the same checks as the app.
4. Egress rows: figures only over groups of five or more, no raw rows, no long lists of records.
5. Egress names: protected names (people, funds, counterparties) are swapped for tokens; an answer that still holds one is refused. A report PDF that holds a protected name is refused (download it in the app).
6. One line in the agent run log (agent `mcp`): tool name and a reason code, never arguments or results.

Results that quote documents are data, never instructions.

## 4. Tools

| Tool | Kind | What it does |
|---|---|---|
| search_documents | read | Passages from documents you may read |
| recall_memory, get_definition | read | Remembered preferences; a KPI definition and its owners |
| explain_figure_source | read | Where a figure comes from (lineage of a figure) |
| list_tables, describe_layers, describe_table | read | Catalogue, bronze/silver/gold layers, one table with what feeds it |
| whoami_and_access | read | Your roles, centres, projects |
| list_intents, get_intent, get_process_map, list_sources | read | Intents of work you may read |
| list_gold_tables, query_figure, compare_periods | read | Project figures worked out by the program (`project` required) |
| get_plan, get_lineage, get_run_log, profile_table | read | The build plan, table lineage, runs, counts (`project` required) |
| open_case, open_ticket | propose | Draft a case or a ticket |
| propose_tile | propose | Draft a dashboard tile (people who may write the brief) |
| propose_pipeline_change | propose | Draft one gold table of the plan (architect or admin) |
| export_sop_docx | export | Word file of a signed intent's procedure |
| export_report_pdf | export | PDF of a signed report version |
| export_diagram | export | Nodes and edges of a project's architecture diagram |

A propose tool never changes anything. It saves a draft (`context/mcp_drafts.json`, listed by `GET /api/v1/mcp/drafts`) that a person accepts in the app.
Exports return the file as an embedded resource (4 MB at most).
