# SK1: Span knows the layers and the data model

Complaint: asked about the silver layer, Span answered statically; the data model and the three layers were not fed to it.

## What landed
- `agent_tools.describe_layers(project)` (shared, so Span, Lumen and North all get it): what bronze, silver and gold mean here, then per layer the tables of this company with purpose, row count and last load (aggregates, as text lines). Bronze and gold come from the registry (`register_bronze`, `register_gold`), silver is the core model plus approved additions. Gold purpose comes from the project's build plan. `project` empty means every project the person may see; a project they may not see is refused.
- `describe_table` now also gives notes, primary key, `points_to` and `pointed_to_by` (from the 151 Ref lines), and `fed_by` / `feeds` (from the `depends_on` of build plans of projects the person may see).
- `span_tools.get_lineage(table)`: chains bronze source -> silver -> gold -> dashboards for the project (dashboards by the tables their tiles read, only those the person may open).
- `skills/span/playbook.md`: the "Three layers" paragraph became "Layers and the model" (meaning, flow, answer from the tools, never from memory). To stay under the 6,000 character cap (now 5,941) four low-value lines were trimmed from traps, questions and examples. `span_tools.PROMPT` names the new tools.
- Tests: `tests/v1/test_span_model_knowledge.py` (6). `tests/v1/test_agent_tools.py` updated from seven to eight tools.

## Notes
- The core DBML has no table-level notes (only column notes), so a silver purpose reads "core model, <group> group". Add table notes to the DBML to enrich it; the tools pick them up unchanged.
- A viewer sees silver for everyone; counts are aggregates, no rows. Gold and bronze follow project access (G1).
- Backups: `.sh-tmp/*.bak-sk1`.

## Review
Verdict: pass, after small fixes.
- Answers come from data. On the seeded `sk1` plane the results show its own silver row counts (42 core tables), its two bronze landings and its three `gold_investment_report_*` tables, each with a purpose from the plan. The b6 test plane returns a different gold table (`gold_monthly_investment_report_valuation_monthly`) and different counts. Nothing is hard-coded except the three-sentence layer meaning.
- Relationships match the DBML. All 151 Refs are inline `ref: >`, with the child on the left. `valuation_observations` shows all seven of its outgoing references (the builder's report said three; the code was right) and its one self-reference coming in.
- Access holds. Gold and bronze follow G1. `fed_by` and `feeds` come only from plans the person can see. An outsider sees silver but nothing of the restricted project (tested). Every result passes `json_findings`.
- Fixed: `agent_tools.py` had `LAYER_ITEMS` and `LAYER_MEANING` twice, a broken first `_ref` (returning five fields, later shadowed) and an unused `_group`. These leftovers are removed. In `span_tools._paths` the walk now stops once it reaches its chain limit, so a wide plan no longer walks every path. Pre-review copies are in `.sh-tmp/*.rev-sk1`.
- Tests pass: test_span_model_knowledge, test_agent_tools, test_span_loop, test_context_egress_shape and test_v3_g1 (70). The skill is under the cap.
- Still open: silver purpose text stays generic until the core DBML gets table notes. The tools have not been tried through the live chat.
