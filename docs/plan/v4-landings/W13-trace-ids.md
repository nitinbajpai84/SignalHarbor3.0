# W13-trace-ids: hashed person part for Lumen, Span Build and Tally trace ids (9 Oct 2026)

No code changed. The id is not made in `mem_wire.py`: `Wire` only records steps. It is made by `e6_trace.turn_trace_id(plane, viewer, agent)` (`tr-<agent>-<hash>-<random>`)
and North (`i6_chat.py:585`) and Span Design (`a1_chat.py:283`) already wrap their `run_agent` call in it. The other three agents run without a wrapper, so `loop._trace_id()` falls back to `e6_trace.new_trace_id()` (`tr-<random>`).
Those three files are outside this card. Exact lines for their owners (same wrapper as North, `viewer` is already in scope in each):

```python
from sh_platform.v1 import e6_trace
with e6_trace.trace(e6_trace.turn_trace_id(plane, viewer, "<agent>") if viewer is not None else None):
    res = run_agent(...)   # the existing call, indented
```

| Agent | File and call | `<agent>` | Note |
|---|---|---|---|
| Lumen | `cx_lumen.py:257` `return run_agent(routed, LT.lumen_registry(...` in `_run_loop` | `"lumen"` | confirm `viewer` is a parameter of `_run_loop` (it is passed to `lumen_registry`) |
| Span Build | `b6_span.py:297` `res = run_agent(route(model, "span", "plan", ...` | `"span-build"` | `viewer` is passed through `_ask_model(..., viewer=viewer)` |
| Tally | `n1_tally.py:806` `res = run_agent(model, reg, ..., "Tally", ...` in `_model_text` | `"tally"` | `viewer` is a parameter of `_model_text` |

Tests: `tests/v1/test_int2.py` covers the id form with three new assertions:
- `test_trace_id_format_for_all_four_agents`: verifies `tr-<agent>-<hash>-<random>` format for North, Lumen, Span Build, Tally; checks that no name appears in any ID.
- `test_person_tag_stable_and_hashed`: confirms the hashed person part is stable per person per company, is valid hex, and contains no name or account_id.
- Existing tests verify North's recorded turn traces start `tr-north-`. When Lumen, Span Build and Tally wrappers land in their own files, each will generate recorded traces starting `tr-lumen-`, `tr-span-build-`, `tr-tally-` respectively.

## Status (9-10 Oct 2026)

**Completed this card:**
- Confirmed mem_wire.py does not generate trace IDs (no changes needed).
- Added `test_trace_id_format_for_all_four_agents` to verify `tr-<agent>-<hash>-<random>` format and that no names appear in IDs for all four agents.
- Added `test_person_tag_stable_and_hashed` to verify the hashed person tag is stable per company and contains no PII.
- Updated landing note with test descriptions.

**Open items (outside this card):**
1. The three agent files (Lumen, Span Build, Tally) still need the wrapper above (their owners).
2. Once wrappers land, their recorded traces will start `tr-lumen-`, `tr-span-build-`, `tr-tally-`; existing tests verify North's format.

## Review (9 Oct 2026)

Verdict: pass with one open item. test_int2.py: 7 passed. mem_wire.py unchanged (matches backup); scope held to the card's files. The id is made in `e6_trace.turn_trace_id`, so the card's correct output is the exact-lines note above. Tests prove the form (8-hex person hash, 8-hex random, stable hash, no name or account id) for all four agent names, but only through `turn_trace_id`; they cannot show Lumen, Span Build or Tally record such ids until their owners add the wrapper. No defects fixed.
