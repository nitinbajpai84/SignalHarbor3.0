# FIXD: North's claims match what it does, it fills result and success, and it stops re-asking

Evidence: `docs/test/uc-live/UC6-REPORT.md` (M1, M2) and `UC8-REPORT.md` (M1, M2, m4); transcript `D:/Temp/uc6r2/m1_north_turns.json`.

## What changed

| Issue | Fix | Where |
|---|---|---|
| North says "I have added the result / removed the KPI" but nothing landed | Each claim sentence ("I have added / noted / removed X") is checked against what landed this turn: the changes it proposed, the ones the person accepted, rows withdrawn, figures written. A claim with no matching change is cut. A removal claim needs a removal. This works alongside the existing `unclaim` guard (nothing landed at all). | `i6_chat.true_claims`, called in `_reply` |
| A KPI already in the intent cannot be removed by North | `withdraw` now covers rows already in the intent of work. Those rows, and a row the person names after "remove / drop / don't need", are proposed for removal (`sow_patch.remove`, applied by `merge` once the person says yes). The tail reads "I have drafted the removal of KPI X". | `i6_chat.remove_rows`, `merge`, `named`, CHAT_PROMPT `withdraw` |
| Result and success never filled from the chat | "the result looks like ...", "Result: ...", "we will know it worked when ...", "Success: ..." in the person's message are drafted into `template_fields.result` / `.success` in their own words (they wait for a yes, like every draft). `propose_intent_section` also takes `result`, `success` or `template_fields`. North now sees `template_fields` in the intent so far and in `get_intent`. | `i6_chat.fill_stated`, `_sow_view`; `north_tools._template` |
| Last month's figures asked every turn | The model is told which KPIs already have figures (`figures_already_given`). A reply that asks for last period's figures when every KPI has one, or after the person already answered that ask with numbers, asks the next open goal instead. "Needs figure" rows are dropped from the sheet once that KPI has a figure or has left the intent, so the product's own ask line stops. The ask line is never added a second time. | `i6_chat.no_figure_reask`, `figures_given`, `open_gaps`, `asked_figures_before` |
| Duplicate KPIs and sources | Names are matched loosely. Case, brackets, filler words, plurals, a currency and an amount in a currency are ignored: "Net break (USD)" = "Net break in USD", and "Breaks above 5,000 USD allowance" = "Breaks above allowance". For sources, a bracketed note is ignored and a name whose words (two or more) all appear in the other name counts as the same source. A near-name draft updates the existing row instead of adding a second one, both within one turn and across turns. | `i6_chat._find`, `same_name`, `_loose`, `_dedupe` |
| A money KPI with unit `count` | A KPI whose name is about money (cash, amount, value, commitment, calls due, net break, fees, a currency) and whose unit is empty or count-like gets the currency the person used (else "currency"). A count stays a count, for example "count of breaks above 5,000 USD". | `i6_chat.money_units` |
| Latency | See below. | `mem_context.after_turn`, `router.RoutedModel.complete` |

The largest North system prompt plus the loop rules is 17,960 characters, under the test's 18,000 ceiling (20,000 at the gateway, less 2,000 of room). A skill line about claims was tried and taken out: it pushed the prompt to 18,236. The program enforces the rule, so the line is not needed.

## Latency: where the 37 to 146 seconds go

- With the fake model, each turn makes **1 model call**. Our own work in a turn takes about **1.3 s** once the process is warm. The first turn in a process also loads the embedding model once (5.6 s). The prompt is 19,600 to 22,200 characters in all.
- In the logs from the earlier runs (UC5-run2 `model_costs.jsonl`), the reply call on `openai/gpt-oss-120b` took **35 to 55 s**, and once 98 s. Some turns also made a memory-summary call (`qwen3.7-flash`, **28 s**) **inside** the turn, before the reply was returned. `sweep` could add up to two more such calls.
- **Cut 1 (ours):** with a live model, the context-map and summary work in `mem_context.after_turn` (`S.maybe` and `S.sweep`) now runs on a background thread after the reply. The memory lines shown in the reply (`MEM.after_turn`) still run before it. Stub models in the tests still run this work inline.
- **Cut 2 (ours):** in Testing mode the specialist and the manager are the same model. After a transport failure (a timeout), the router used to ask that same model again as "the next tier", so the person waited out a second timeout. It now skips a model that has just timed out (logged as `same_model_failed`) and goes on to the next different model.
- **Live Testing-mode turn, after the fix** (one turn; synthetic company in `D:/Temp/fixd-env`, since deleted):
  - **23.8 s** for the whole turn. The reply call took 19.1 s (6,543 tokens in, 590 out).
  - The memory summary that this turn triggered took **35.5 s** on the background thread. Before the fix it ran inside the turn, which would have made the turn about **56 s**.
  - Cost **USD 0.00065** for 2 calls.
  - The reply drafted `template_fields/result` and `template_fields/success` from Mei's words.
- **Not ours, left as it is:** the provider's own time for gpt-oss-120b (19 to 55 s per call, mostly reasoning tokens). A next step, if wanted: send `reasoning: {effort: "low"}` for gpt-oss in Testing mode from the OpenRouter adapter (`sh_platform/egress/providers/openrouter.py`). This was not changed here because it could affect answer quality.

## How to test

```
python -m pytest tests/v1/test_fixd_north.py tests/v1/test_router.py -q
python -m pytest tests/v1 -k "north or i6 or i4 or sow or v6b" -q
python -m pytest tests/agents -q
```

Live, in the UI: tell North "To finish: the result looks like one page per month ... We will know it worked when ...". Two drafts should appear (result, success). Accept them, and the sign gate no longer lists those sections. Then say "please remove the X KPI": a removal draft should appear, and accepting it removes the row.

## Test results (13 Oct)

- `tests/v1/test_fixd_north.py`: 9 passed. All 9 fail on the old code (checked on a copy with the backed-up files).
- `tests/v1/test_router.py`, `test_aq1_shared_runtime`, `test_mem_agent`, `test_mem_graph`, `test_r1_run_log`: 76 passed. The new router test passes too.
- `tests/agents`: 151 passed.
- `tests/v1 -k "north or i6 or i4 or sow or v6b"`: 110 passed, 3 failed, 9 errors. None of these come from this change:
  - `test_g1::test_folder_map_and_north` was already failing before this change ("unknown node type 'Measure'").
  - The 9 errors come from the seed's xlsx read (`e0b_tools.read_grid`, from `k6_liquidity.commitments`), in files other fixers are changing.
  - `test_nm1` (a 10 s timing check) failed only under parallel load and passes when run alone.
  - The prompt-size test passes after the skill line was taken out (run alone: 11 passed, together with `test_nm1` and the new tests).

## Files

`sh_platform/v1/i6_chat.py`, `sh_platform/v1/north_tools.py`, `sh_platform/v1/mem_context.py`, `sh_platform/v1/router.py`, `tests/v1/test_fixd_north.py` (new, 9 tests), `tests/v1/test_router.py` (+1 test). Backups: `D:/Temp/bak-fixd/`. Not committed. `i4_sow.py` was not changed: signing already counts `template_fields`.
