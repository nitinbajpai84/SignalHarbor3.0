# W3-wave2-mount landing

## Mounted
- Connectors (C5) and pain-point demo (K12): backend already mounts by glob (`v1.install`); nothing to add.
- MCP: `sh_platform/app.py` includes `sh_platform.mcp.routes.router`; permissions copied to `sh_platform/v1/mcp.permissions.yaml`.
- Settings (`ui/src/v1/s1/SettingsPage.tsx`): sections "Connectors" (renders ConnectorsPage; the C5 own route is removed so it opens inside Settings), "Outside assistants" (new `s1/McpTokens.tsx`: issue, show once, revoke), "Demo" (link to /centre/demo/painpoints). All three sit behind the existing admin/analyst Settings gate.
- Consume (`k10/ConsumeRoom.tsx`): seventh tab "Attribution" -> /centre/consume/analytics.
- requirements.txt: paramiko, python-pptx added (reportlab already there). The `mcp` SDK is not used (minimal JSON-RPC), so not added.
- Backups: `.sh-tmp/*.bak-w3`.

## Tests
pytest tests/mcp + test_c5_connect + test_k12_painpoints + test_k11: 38 passed. vitest c5, k10, k11, k12, s1, App: 86 passed (k10 tab test updated to seven tabs). tests/auth + contracts: pass. tests/smoke: test_smoke_egress fails its "repo tree changed during run" guard (other agents write to the repo concurrently); not caused by this card.

## Differences for Nitin's approval
- The v5 designs do not show Connectors, Outside assistants, Demo or an Attribution tab; these use existing Settings/Consume styling. The Attribution page itself does not show the Consume tab bar (it is its own route).
- Demo link is in Settings (admin/analyst), not in the main nav.

## Open
- Accepting MCP drafts, the Map-health merge of connector lateness and the `run_due` scheduler call (W2-connectors mount lines 4 and 5) are not wired.

## Review
- Verdict: accept. No defects needing a fix; no files changed by the review.
- Access: /mcp is public to the cookie check but refuses without a bearer token (hashed, constant-time compare, roles read fresh); token routes and connectors carry role lines; the Settings gate (admin/analyst) is stricter than the API for tokens, which only ever act as the issuer.
- Failure/concurrency: token and draft files use lock_for plus atomic writes; body capped at 256 KB; errors give plain messages. Minor: the issued token stays on screen until the page is left (acceptable, shown once).
- Tests re-run: tests/mcp + tests/auth + tests/contracts 156 passed, 46 skipped. Smoke egress failure is the shared-tree guard, not this card.
- Designs: none show these screens, so the listed differences stand for Nitin's approval; the three unwired items (MCP draft accept, Map-health merge, run_due) remain open.
