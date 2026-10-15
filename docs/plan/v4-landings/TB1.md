# TB1: everyone can talk to Span and Lumen, as a conversation (10 Oct 2026)

Why: Mei, on the Build landing, could not "talk to Span". The button stayed grey until text was typed, the box was white with faint text in dark mode, it was one question and one block of text, and the answer was fixed wording listing all 42 tables.

## What changed
- **Composer.** Both landings (Talk to Span on Build, Talk to Lumen on Consume) use the shared `Composer` (`ui/src/v1/voice`). Enter sends, Shift+Enter adds a line. Send is always active; an empty send shows "Type a question first." Composer gained an optional `onEmpty` prop (without it nothing changes for the project chats) and its text box now uses design tokens (`--ds-ground`, `--ds-ink`, `--ds-line-2`), so it reads in dark and light.
- **Thread.** `ui/src/v1/talk/TalkBox.tsx` keeps person and agent turns on the page for the visit, newest last. The pages `ProjectsPage.tsx` and `ProjectList.tsx` are unchanged (they already render TalkBox).
- **Answer.** `talk.ask(plane, viewer, agent, text, pid, model)` runs `run_agent` with `tools_for(plane, viewer, "span"|"lumen")` through `route` (router and egress), with the `mem_wire.Wire` context (`context_for`, conversation id `company`, so keyed by agent + person + "company") and `mem_context.after_turn` keeps the turns for follow-ups. The prompt asks for groups and counts then "Ask about a table for detail", never a dump.
- **Rules.** Model off, unreachable or unfinished: the reply starts "Rules-only reply:" and is short (groups with counts, how many projects can be read, lock line). A project picked or named in the words (readable or locked) skips the loop and gets the deterministic project or lock words, so access wording is unchanged.
- **Routes.** `POST /api/v1/build/chat` and `POST /api/v1/consume/chat` return `{reply, rules_only}`; Build passes `get_model`, Consume uses `build_model_client` as Lumen's project chat does.

## Files
`sh_platform/v1/talk.py`, `b6_routes.py`, `cx_routes.py`, `ui/src/v1/talk/TalkBox.tsx`, `ui/src/v1/voice/index.tsx` (small, additive; outside the listed files, needed for the always-active button), tests `tests/v1/test_talk_to_all.py` (+3), `ui/src/v1/talk/talk.test.tsx` (3). Backups: `.sh-tmp/*.bak-tb1`.

## Checked
pytest test_talk_to_all (9 pass), test_context_egress_shape, test_span_loop, test_lumen_loop all pass; vitest talk, b6, cxui, voice 26 pass; tsc clean. Not run: live server on 8680 (light testing), full suite.

## Open
- `test_talk_to_all::test_every_v1_route_has_a_permission_line` fails on `POST /api/v1/build/p/{pid}/chat/files` (a new route with no permission line; not from this card). Add the line next to the intents one.
- The thread is not reloaded after a page refresh (the server keeps the short-term memory, the page does not list it).

## Review (10 Oct 2026)
Verdict: pass. Ran test_talk_to_all (now 10/10), test_context_egress_shape, test_span_loop, test_lumen_loop: 50 pass. Confirmed in code: `talk._loop` calls `run_agent` with `tools_for(plane, viewer, agent)` through `route` and `fit(wire.sections())`; the stub-model test asserts `list_tables`/`describe_table` calls; the rules reply is prefixed "Rules-only reply:" and short. Composer text box uses `--ds-ground/--ds-ink/--ds-line-2` tokens.
Fixed: added the missing permission line `POST /api/v1/build/p/{pid}/chat/files` to `sh_platform/v1/b6.permissions.yaml` (the open item above is closed).
Not run: live server on 8680, vitest/tsc re-run (builder reported 26 pass, tsc clean).
