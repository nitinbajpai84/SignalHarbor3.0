# EG1: agent context and tool results must pass the egress row check

Files: `sh_platform/v1/l2_proposals.py`, `sh_platform/v1/n1_tally.py`, `ui/src/v1/p1/ProjectPage.tsx`, new `tests/v1/test_context_egress_shape.py`. Backups in `.sh-tmp/*.bak-eg1`.

1. `L2.facts` now returns strings ("<line> (reason: <why>)") for `turned_down_by_the_person`. This fixes North, Span Design (a1_chat adds the facts after `fit`), Flow and Brief (f1/c3 use it too). The `i6_chat` per-agent workaround is now redundant (its isinstance check passes strings through) but harmless; left as is.
2. Tally's real cause was different: the Tally skill text (`skills/tally`) has three example answers, each one JSON object on its own line. The gateway counts one JSON value per line, so two or more read as raw rows and the whole system message was refused (module m4_action, raw_rows, 0 bytes). `n1_tally._no_json_lines` prefixes such lines with "Example answer: " before the skill goes into the system prompt. Tally's facts, `placeholders` and its own tool results were already strings. Lumen, Span build and the wire sections (`mem_wire`) were already flat; no change needed.
3. Guard test `tests/v1/test_context_egress_shape.py`: North, Span Design, Span Build, Lumen and Tally each run a real turn with a capturing model (two or three turned-down proposals and a memory item seeded where the agent reads them) and every message sent, system prompt included, goes through `egress.rows.json_findings` and must give `(None, [])`. The Tally case failed before the fix. Also asserts `L2.facts` is strings.
4. `ProjectPage.tsx` subline shows the project title, not "Project {id}".

Not done (outside the allowed files): shared tool results still hold lists of objects, which the gateway scans in tool messages (`agent_tools`: `list_tables`, `describe_table`, `get_definition`, `whoami_and_access` with 2+ projects; `span_tools` plan and run log; `north_tools`; `lumen_tools.list` tables). Each will be refused once a result holds 2+ objects. One-line fix for the shared ones: wrap their return in `egress_fit.flatten` (in `agent_tools._plain`) and do the same in the span, north and lumen tools. The remaining Tally blocks in Nitin's log may include these too.

Run: new test 6, test_ni1, test_l2, test_tally_loop, test_n1_tally, test_lumen_loop, test_span_loop, test_context_wiring, test_a1 (93 passed before the last test was trimmed); vitest src/v1/p1 3 passed; tsc clean.

## Review

Verdict: pass, no code changes made in review.

- The guard test imports `json_findings` from `sh_platform/egress/rows.py`, the same function `gateway._check_structure` runs on every message `content`. It covers North, Span Design, Span Build, Lumen and Tally, with real turns and every message, system prompt included. Turned-down proposals are seeded only for North and Span Design. That is correct because only i6/a1/f1/c3 read `L2.facts`, and b6_span, cx_lumen and n1_tally do not. The Span Design case goes through `a1_chat` with no workaround, so it guards the `L2.facts` change itself. North alone would not, because the i6 workaround masks it.
- No new exposure. `turned_down_by_the_person` carries the same `line(p)` text, which has no digits, plus the person's own reason as before, now joined into one string. `_no_json_lines` only adds a prefix to static skill example lines. `n1_tally` uses no new data.
- `test_l2` and `test_ni1` already assert the string shape. No other test or caller depends on the `{what, reason}` shape. f1/c3 pass the value through.
- Re-run after the trim: the new test plus the eight listed files gave 93 passed. vitest src/v1/p1 passed 3/3 and tsc is clean. `test_f1` passes. `test_c3::test_model_shapes_the_brief_and_an_end_user_adds_to_it` fails on "Questions worth asking" missing from the Lumen skill (`skills/lumen/questions.md`, edited 9 Oct 22:13). That failure is not from EG1.
- Item 4: the subline now repeats the title that PageFrame already shows as the heading. That is literal to the brief. Use the pill alone if the repeat reads oddly.
- Still open (agreed): shared tool results that come back as a list of 2+ objects (`agent_tools` list_tables/describe_table/get_definition/whoami, span/north/lumen tools) are refused when they reach `loop._run_tool`. Flattening them in `agent_tools._plain` is the follow-up.
