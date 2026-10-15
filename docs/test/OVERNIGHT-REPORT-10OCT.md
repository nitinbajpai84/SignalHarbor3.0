# Overnight report, 9–10 October 2026

## Where to look
- **Server:** http://127.0.0.1:8502 (fresh ten-use-case data, demo date pinned to 9 Oct, Testing mode). Logins: `.sh-tmp/testenv/nitin3/data/_control/seed_credentials.txt` (the `…evergreen@example.test` rows).
- 8400 is the live server on `data/` (not reloaded). 8501 is yesterday's session.
- **Guides:** `docs/guides/DEMO-GUIDE-10UC.md` (verified click paths, 12 screenshots), `docs/guides/NEW-USE-CASE-WALKTHROUGH.md`.
- **Website:** https://claude.ai/artifact/Tj6oCLoyYURNrJ8fBPq8ye (private until shared).
- **Video, first cut:** `docs/video/out/signal-harbor-sponsor.mp4` (4:50, voiceover, captions). It predates this morning's changes; a re-record is pending.

## Built
| Area | What | Where to see it |
|---|---|---|
| Build | Three rooms in this order: Architecture (layers, tables, links, lineage, Span), Pipelines (sources to gold, run status, schedule, Try it on a copy, Go live), Dashboard studio | Build, then any project |
| Dashboard studio | Grid with empty slots, widget library, a Talk to Lumen conversation (proposal, Accept / Not this, follow-ups), submit, someone other than the maker approves and publishes; header shows the last and next refresh | Build › Dashboard studio |
| One place to build | Consume shows ready (published) dashboards only. Lumen there answers questions and points build requests to the studio. Older personal dashboards moved into the studio as drafts | Consume |
| Consume daily numbers | NAV (total, by entity, issued against known now), performance against the benchmark, key levers, market drivers, liquidity; every figure has its trail | Top of Consume |
| Comments | On dashboards, widgets, Office view lines and Brief lines. History is kept, mentions notify on Today, and "Raise as a case" links both ways | Any dashboard or Office line |
| Shared with you | Dashboards others shared with you, plus the latest CIO Brief | Consume |
| Agents | Two fix waves (about 100 findings): layer and lineage knowledge, egress shape, access leaks, injection, memory, the billing note, and an outage breaker (no retries on a credit refusal). North starts intents by rules when no model is reachable | Talk to any agent |
| Fixes | Demo date pinned to 9 Oct; every role can open Consume; Signed register; one company time zone; SOP as .docx; "Try it on a copy" no longer fails on a locked file; returns shown as percentages | — |

## Tested
| Test | Result |
|---|---|
| Ten use-case checkers (fresh seed, after cycle-2 fixes) | **246 / 246 pass** |
| Ten use-case regression, cycle 2 | 26 testers (10 analysts, 16 journeys), 9 fix packages, all reviewed and accepted. The per-case table in `docs/test/TRIAGE-cycle-2.md` was taken **before** the fixes |
| UI tests | 1,605 / 1,605 earlier tonight; affected folders re-run after each change |
| Backend suite | 3,702 passed, 5 failed (from 41 failed and 163 errors). The FastAPI pin is now installed (auth 71/71). **Left:** "Ardmore" named in 44 pack files (to be renamed to a neutral firm, per the local-only rule), and one picture-speed timing test (5.5 s against a 5 s bound under load). See `docs/test/BACKEND-SUITE-10OCT.md` |
| Agents, live | Cycle 1 scorecard: every line failed on the live model (`docs/test/AGENT-TRIAGE.md`). Two fix waves landed offline. **Cycle 2 live retest is running now, in Testing mode** |

## Money and models
- Google: credit restored (SGD 27.50). Testing mode runs every tier on Gemini Flash and Flash-Lite. All automated testing uses Testing mode only.
- OpenRouter: the account has $45, but **the key's own credit limit is $20, with $0.32 left**. Raise it under Keys before using Real use.

## Open, needing your call
1. Approvers: any head of data or sponsor except the maker, versus only the project's named people.
2. "Ardmore" in the pack: rename to a neutral firm (recommended, per your rule).
3. When to reload the live 8400 data, after a backup.

## Next
1. Live agent campaign: cycle 2 result, fixes, cycle 3.
2. A journey re-run on the fixed build, to confirm the cycle-2 FAIL rows now pass.
3. Video re-record with the latest features, once the agents are final.
