# W3-agent-handoffs

## Built
- `sh_platform/agents/handoff.py`: `propose_handoff` tool (a propose tool, nothing written in the run). Routes: Tally to Span `new_check`, Lumen to Span `missing_data`, North to Span `build_brief` (only once the intent is signed, only on a project). The addressee is fixed by the route. Fields: question (400 chars), up to 6 facts, up to 4 links (`/centre/...` paths only); planted instructions are refused.
- After the run each agent calls `handoff.take(plane, viewer, pid, res.proposals)`: it files hand-offs as PENDING in `handoffs/log.jsonl` (append-only: propose, accept, decline) and returns the other proposals untouched.
- Receiving person: the project's builder, else the data team (analysts). A needs-me card via an e5_pulse source (so it is on the Action page's "needs me") and a `handoffs` list in `p2_assign.history` for the project timeline.
- Nothing happens until `handoff.decide(plane, viewer, id, accept, pid=None)` by a data-team person, admin or the named receiver. `handoff.context` gives Span the accepted ones as quoted material (`handed_over_to_you`) in its chat and plan-draft context.
- Hooks: `n1_tally.py` (register, take), `cx_lumen.py` (register, take; keeps hand-offs out of the tile list), `i6_chat.py` (register, take), `b6_span.py` (context in two places), `p2_assign.py` (import, `handoffs` in history). Backups `.sh-tmp/<name>.py.bak-w3`.

## Tests
`python -m pytest tests/v1/test_handoff.py`: 18 passed (stub models). Neighbours `test_agent_tools.py`, `tests/agents/test_propose_sink.py` pass.

## Open items for integration
- No route or screen yet for accept/decline (`handoff.decide`) and the timeline UI does not yet read `history.handoffs`; a route needs a `g1.permissions.yaml` line.
- `tests/v1/test_p2_assign.py` currently fails (7) in `_append` on `events.badge(...)`: another W3 card's edit, not this one.
- Design: the v5 designs show no hand-off screen, so there is no design to match; nothing differs silently.

## Difference for Nitin's approval
- None in shipped screens (no UI built). The card wording ("Tally asks Span for ...", "Open project") is new and unapproved.

## Review
- Checked: hooks, access, failure handling, tests. Fixed in `handoff.py` (backup `.sh-tmp/handoff.py.bak-w3`): filing (dedupe check plus append) and `decide` (state check plus append) now run under one lock, so two runs cannot file the same request twice and two clicks cannot both decide it; `decide` now checks who may answer before revealing the state (403 before 409).
- Holds: addressee fixed by route; build_brief only after sign-off; facts quoted as untrusted for Span; `file` never breaks the answer; timeline read gated by project read access.
- Limits: the lock is per process (several workers would need a file lock). The pulse card counts toward the per-person card cap, so a full cap can hide it. The `p2_assign` `badge()` failures (7) belong to another card. Backups of `cx_lumen`, `i6_chat`, `b6_span`, `p2_assign` may have overwritten earlier ones; compare before restoring.
- Still open: accept/decline route (needs a `g1.permissions.yaml` line) and timeline UI. Difference for Nitin's approval: the card wording ("Tally asks Span for ...", "Open project" / "Open Build") is new; no hand-off screen exists in the v5 designs.
