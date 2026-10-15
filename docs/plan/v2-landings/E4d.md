# E4d Refusal guard

## What changed
`sh_platform/v1/e4_guard.py`: rule-based, no model, no I/O.
- `check_request(text)` returns None or `{refused: True, code, reason, review_path: "Opens a case for the authorised approver"}`. Codes: change_official, approve_for_other, send_out, bypass_rule.
- `check_action(action, target_table)` refuses an agent write to nav_snapshots, report_versions, calculation_runs, metric_values, approvals, rule_versions, access_grants, and approve/issue/send on those.
- Document policy: `DOCUMENT_POLICY`, `is_instruction_source(source)` (only "user"/"chat"/"person"), `scan_document_text(text)` (instruction-like snippets, for E6b's injection test), `wrap_untrusted(text)`.

## Files
`sh_platform/v1/e4_guard.py`, `tests/v1/test_e4d.py` (44 tests: 22 refused, 20 allowed, action, document policy).

## How to test
1. `SH_MODEL_PROVIDER=off python -m pytest tests/v1/test_e4d.py -q`
2. `python -c "from sh_platform.v1 import e4_guard as g; print(g.check_request('Increase official NAV by $180,000'))"`

## Known limits
Regex wording, English only; a determined rephrasing can slip past, so it is the first line, not the only one (the tool layer still blocks protected writes via `check_action`). A "Mark ... as approved" phrase is refused even in a harmless question about marking.

## Wiring for the orchestrator
- In each chat engine (`i6_chat.ask`, `a1_chat`, `f1_chat`, `c3_chat`), call `e4_guard.check_request(question)` before any retrieval or model call; if it returns a dict, answer with `reason` and `review_path` and, if E4a exists, offer to open a case.
- In the agent tool dispatcher, call `e4_guard.check_action(action, table)` before every warehouse write by an agent and refuse on a dict.
- Wrap document text with `wrap_untrusted` when building prompts; run `scan_document_text` on extracted text and log a warning when it finds hits.
