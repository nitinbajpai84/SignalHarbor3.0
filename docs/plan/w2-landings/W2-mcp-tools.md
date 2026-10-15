# W2-mcp-tools landing

## Built
`sh_platform/mcp/`: `tokens.py` (issue, list, revoke, verify; sha256-hashed, scoped, expiring), `server.py` (JSON-RPC 2.0: initialize, ping, tools/list, tools/call; 26 tools reusing agent_tools, north_tools, lumen_tools, span_tools; drafts; egress row and name rules; run log), `routes.py` (POST /mcp and the Settings token routes), `mcp.permissions.yaml`, `__main__.py` (stdio). `docs/MCP.md`. The official `mcp` SDK is not in the venv, so this is minimal JSON-RPC per spec.

## How to see it
Issue a token with `POST /api/v1/mcp/tokens` (signed in), then `POST /mcp` with `Authorization: Bearer <token>` and `{"jsonrpc":"2.0","id":1,"method":"tools/list"}`. Or run stdio: `SH_MCP_TOKEN=... python -m sh_platform.mcp --data-root <data>`.

## Tests
`python -m pytest tests/mcp -q`: 6 pass (listing by scope, access refused, no raw rows and small groups, token revoke and expiry and hashing, proposals as drafts with names tokenised and logged, HTTP default-deny and bearer).

## Mount lines (integration step; nothing edited outside sh_platform/mcp)
1. `sh_platform/app.py` (after the v1 install): `from sh_platform.mcp.routes import router as mcp_router` then `app.include_router(mcp_router)`.
2. Permissions: copy `sh_platform/mcp/mcp.permissions.yaml` to `sh_platform/v1/mcp.permissions.yaml` (v1 `extra_permission_files` globs `*.permissions.yaml` there), or add its 6 routes to the kernel file. Without it every route is refused (default deny).
3. Settings screen (ui, not built here): list/issue/revoke over `/api/v1/mcp/tokens`, show the token once; drafts list over `/api/v1/mcp/drafts`.

## Open items
- Accepting a draft in the app is not built here: case -> `e4_cases.open`, ticket -> `t2_tickets.raise_ticket` (needs `to`), tile and pipeline change -> the existing L2 accept paths. Drafts wait in `context/mcp_drafts.json`.
- Per-company entitlement uses an open gate (as the v1 routes check it before the agent runs); add the module switch check at the mount if MCP should be a switchable module.
- Tally case tools (need a case bundle) and North's propose tools (need a live conversation) are not exposed.
- No rate limit on POST /mcp yet.
- Per D-006 an outside assistant is outside the plane: the customer chooses to issue tokens; the company-level on/off for issuing is not built.

## Review (security, 11 Oct)
Checked: token issue/verify/revoke (256-bit secret, sha256 at rest, constant-time compare, company id validated, unknown company refused without creating a folder), fresh roles and disabled accounts per call, scope refusal identical to unknown tool, extra-argument refusal, registry `_summary_only` on every read result (rows and groups under five), vault name rule on every text result, drafts stored only in the company plane, run log holds tool name and reason only, default-deny permissions file, no secrets or client data in repo.
Fixed:
- `export_report_pdf`: the PDF prints the signer's name, which the brief check did not cover. The signer's name is now part of the name check (fail closed).
- Refusal text from an inner tool was sent out untokenised; it now passes the name rule too.
- `tokens.issue`: a non-list or non-string `scopes` raised a 500; it is now a 400.
Backups: `.sh-tmp/*.bak-w2b`. `python -m pytest tests/mcp -q`: 6 passed.
Still open (not blocking): results do not pass through the egress gateway's own call log (the run log covers it); no rate limit on `POST /mcp`; `POST /api/v1/mcp/tokens` with a broken JSON body returns 500; no test yet for the two name-rule fixes.
